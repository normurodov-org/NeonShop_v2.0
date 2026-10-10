# -*- coding: utf-8 -*-
"""
NEON STORE BOT — Telegram Stars savdo boti (Fragment.com + TON)
=================================================================

TO'LOV QOIDASI:
  * Balans SO'M (UZS) da to'ldiriladi — userbot bank xabarini avtomatik aniqlaydi.
  * Stars esa FAQAT USDT (TON zanjiri) orqali Fragment.com dan xarid qilinadi.
    Gram / TON / boshqa to'lov usullari yo'q (FRAGMENT_PAYMENT_METHOD majburiy "usdt").
  * WebApp buyurtmalari ham shu yagona USDT kodini ishlatadi
    (star_order_worker -> buy_stars_via_fragment).

Imkoniyatlar:
  * aiogram 3.x  — asosiy bot (menyu, FSM, to'lovlar, admin panel)
  * pyrofork     — userbot: bank botidan (humocardbot) kelgan xabarlarni kuzatib,
                   balansni avtomatik to'ldiradi va Telegram Gift'larni avtomatik yuboradi
  * pytoniq      — TON blokcheyn (LiteBalancer, WalletV4R2, Cell)
  * cloudscraper — Fragment.com Cloudflare himoyasidan o'tish
  * httpx        — USDT/UZS live kursi
  * JSON baza    — /data/users_db.json (atomik yozish + .bak zaxira)

O'rnatish:
  pip install aiogram pyrofork tgcrypto pytoniq cloudscraper httpx

Ishga tushirish:
  python bot.py
"""

# =============================================================================
# 0. EVENT LOOP PATCH
# =============================================================================
import asyncio
import sys
import warnings

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    _BasePolicy = (
        asyncio.WindowsSelectorEventLoopPolicy
        if sys.platform == "win32"
        else asyncio.DefaultEventLoopPolicy
    )


class CustomEventLoopPolicy(_BasePolicy):  # type: ignore[misc, valid-type]
    def get_event_loop(self):
        try:
            loop = super().get_event_loop()
            if loop.is_closed():
                raise RuntimeError("Event loop is closed")
            return loop
        except RuntimeError:
            loop = self.new_event_loop()
            self.set_event_loop(loop)
            return loop


with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    asyncio.set_event_loop_policy(CustomEventLoopPolicy())

if sys.platform == "win32":
    try:
        from asyncio.proactor_events import _ProactorBasePipeTransport

        _orig_del = _ProactorBasePipeTransport.__del__

        def _silent_del(self, _warn=warnings.warn):
            try:
                _orig_del(self, _warn)
            except RuntimeError as exc:
                if str(exc) != "Event loop is closed":
                    raise

        _ProactorBasePipeTransport.__del__ = _silent_del
    except Exception:  # noqa: BLE001
        pass

# =============================================================================
# 1. IMPORTLAR
# =============================================================================
import base64
import contextlib
import hmac
import html
import json
import logging
import os
import random
import re
import shutil
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Awaitable, Callable, Optional
from urllib.parse import urlencode, urlsplit

import cloudscraper
import httpx

from premium_emoji import PREMIUM_EMOJI, render_text
from aiogram import BaseMiddleware, Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.middlewares.base import BaseRequestMiddleware
from aiogram.methods import EditMessageCaption, EditMessageText, SendMessage, SendPhoto
from aiogram.enums import ChatMemberStatus, ParseMode
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)
from aiogram.filters import Command, CommandObject, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.web_app import safe_parse_webapp_init_data
from aiohttp import web
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    MenuButtonWebApp,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    TelegramObject,
    WebAppInfo,
)
from pyrogram import Client as UserbotClient
from pyrogram import idle as ub_idle
from pyrogram import filters as ub_filters
from pyrogram import raw as ub_raw
from pyrogram.errors import BadRequest as UbBadRequest
from pyrogram.errors import PhoneCodeExpired as UbPhoneCodeExpired
from pyrogram.errors import PhoneCodeInvalid as UbPhoneCodeInvalid
from pyrogram.errors import RPCError as UbRPCError
from pyrogram.errors import SessionPasswordNeeded as UbSessionPasswordNeeded
from pyrogram.handlers import MessageHandler as UbMessageHandler
from pytoniq import LiteBalancer, WalletV4R2, begin_cell
from pytoniq_core import Address, Cell
from pytoniq_core.crypto.keys import mnemonic_is_valid
from pytoniq_core.crypto.keys import words as TON_WORDLIST

# =============================================================================
# 2. SOZLAMALAR
# =============================================================================
def _load_dotenv(path: str = ".env") -> None:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip().removeprefix("export ").strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


_load_dotenv()

# BOT_TOKEN FAQAT Railway ENV dan olinadi. Kod ichiga token yozish XAVFSIZ EMAS
# (repo ochiq — token o'g'rilishi mumkin). Bo'sh bo'lsa bot aniq xato bilan to'xtaydi.
TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "8307046273"))
ADMIN_IDS = {ADMIN_ID}
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "neon2025")

ORDERS_CHANNEL = os.getenv("ORDERS_CHANNEL", "@Shop_NeonOrders").strip()
CASHBACK_RATE = 0.001
CARD_NUMBER = os.getenv("CARD_NUMBER", "9860 1701 1569 3682")
CARD_HOLDER = os.getenv("CARD_HOLDER", "O. N (HUMO)")

# --- Userbot (pyrofork) ---
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
SESSION_STRING = os.getenv("SESSION_STRING", "")
TOPUP_SOURCE_CHAT = os.getenv("TOPUP_SOURCE_CHAT", "@humocardbot")

# --- TON / Fragment ---
WALLET_SEED = os.getenv("WALLET_SEED", "")


def parse_wallet_seed(raw: str) -> list[str]:
    text = re.sub(r"\d+\s*[.)]?", " ", (raw or "").lower())
    return re.findall(r"[a-z]+", text)


def wallet_seed_problem(words: list[str]) -> Optional[str]:
    if not words:
        return "WALLET_SEED sozlanmagan"
    if len(words) != 24:
        return (f"WALLET_SEED {len(words)} ta so'zdan iborat, 24 ta bo'lishi kerak "
                f"(12 so'zli hamyonlar ishlamaydi — Tonkeeper/MyTonWallet'ning 24 so'zini kiriting)")
    wordset = set(TON_WORDLIST)
    bad = [str(i) for i, w in enumerate(words, start=1) if w not in wordset]
    if bad:
        return f"WALLET_SEED dagi {', '.join(bad)}-so'z(lar) xato yozilgan — tekshiring"
    if not mnemonic_is_valid(words):
        return ("WALLET_SEED TON hamyon so'zlari emas yoki so'zlar tartibi noto'g'ri. "
                "Tonkeeper, MyTonWallet yoki Telegram TON Space'ning 24 so'zini kiriting")
    return None


WALLET_WORDS = parse_wallet_seed(WALLET_SEED)
WALLET_SEED_ERROR = wallet_seed_problem(WALLET_WORDS)
FRAGMENT_ADDRESS = os.getenv("FRAGMENT_ADDRESS", "UQCFJEP4WZ_mpdo0_kMEmsTgvrMHG7K_tWY16pQhKHwoOtFz")
FRAGMENT_COOKIES = {
    "stel_ssid": os.getenv("FRAGMENT_STEL_SSID", ""),
    "stel_dt": os.getenv("FRAGMENT_STEL_DT", "-300"),
    "stel_token": os.getenv("FRAGMENT_STEL_TOKEN", ""),
    "stel_ton_token": os.getenv("FRAGMENT_STEL_TON_TOKEN", ""),
}
FRAGMENT_USER_AGENT = os.getenv("FRAGMENT_USER_AGENT", "")
FRAGMENT_COOKIE_HEADER = os.getenv("FRAGMENT_COOKIE_HEADER", "")
FRAGMENT_API_HASH = os.getenv("FRAGMENT_API_HASH", "")
FRAGMENT_PROXY = os.getenv("FRAGMENT_PROXY", "")
USERBOT_START_DELAY = int(os.getenv("USERBOT_START_DELAY", "30"))

_webapp_env = os.getenv("WEBAPP_URL", "")
_railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "")
# URLni tozalash: scheme va boshidagi "//" ni olib tashlaymiz
WEBAPP_URL = (_webapp_env or (f"{_railway_domain}" if _railway_domain else "") or "ais-dev-ffdnmkh7ixsl5w6yf5m34t-532430849464.asia-southeast1.run.app").strip()
WEBAPP_URL = WEBAPP_URL.replace("https://", "").replace("http://", "").lstrip("/").rstrip("/")
WEBAPP_URL = "https://" + WEBAPP_URL

WEBAPP_API_PORT = int(os.getenv("PORT", "3000") or 3000)
WEBAPP_API_URL = (os.getenv("WEBAPP_API_URL") or (os.getenv("RAILWAY_PUBLIC_DOMAIN") or "") or WEBAPP_URL.replace("https://", "")).strip()
WEBAPP_API_URL = WEBAPP_API_URL.replace("https://", "").replace("http://", "").lstrip("/").rstrip("/")
WEBAPP_API_URL = ("https://" + WEBAPP_API_URL) if WEBAPP_API_URL else WEBAPP_URL


def webapp_api_enabled() -> bool:
    return bool(WEBAPP_API_PORT and WEBAPP_API_URL)


# Baza yo'li: agar /data papkasi bo'lsa yoki yozish mumkin bo'lsa /data/users_db.json
def get_db_path() -> str:
    env_p = os.getenv("DB_PATH")
    if env_p:
        return env_p
    try:
        if os.path.exists("/data") or os.access("/", os.W_OK):
            os.makedirs("/data", exist_ok=True)
            return "/data/users_db.json"
    except Exception:
        pass
    local_data = os.path.join(os.getcwd(), "data")
    os.makedirs(local_data, exist_ok=True)
    return os.path.join(local_data, "users_db.json")


DB_PATH = get_db_path()

# --- Narxlar va limitlar (UZS) ---
STAR_BUY_PRICE_UZS = 200
STAR_SELL_PRICE_UZS = 125
MIN_STARS_BUY = 50
MAX_STARS_BUY = 1_000_000
MIN_STARS_SELL = 50
MAX_STARS_SELL = 100_000
REF_BONUS_STARS = 1
REF_MIN_WITHDRAW = 50
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "normuzb").lstrip("@")

PREMIUM_PLANS = {
    "login": {1: 40_000, 12: 285_000},
    "nologin": {3: 155_000, 6: 205_000, 12: 375_000},
}
PREMIUM_MODE_NAMES = {"login": "akkauntga kirib", "nologin": "akkauntga kirmasdan"}

GIFTS = [
    ("bear", "🧸 Ayiqcha", 15, 3_000),
    ("heart", "💝 Yurakcha", 15, 3_000),
    ("box", "🎁 Sovg'a qutisi", 25, 6_000),
    ("rose", "🌹 Atirgul", 25, 6_000),
    ("cake", "🎂 Tort", 50, 10_000),
    ("bouquet", "💐 Gul dastasi", 50, 10_000),
    ("rocket", "🚀 Raketa", 50, 10_000),
    ("cup", "🏆 Kubok", 100, 20_000),
    ("ring", "💍 Uzuk", 100, 20_000),
    ("diamond", "💎 Olmos", 100, 20_000),
    ("champagne", "🍾 Shampan", 50, 10_000),
]
GIFTS_BY_KEY = {g[0]: g for g in GIFTS}
MANUAL_FALLBACK = os.getenv("MANUAL_FALLBACK", "1").strip().lower() not in ("0", "false", "no", "")
MIN_TOPUP = 1_000
MAX_TOPUP = 10_000_000
TOPUP_TIMEOUT_SEC = 5 * 60
TOPUP_GRACE_SEC = 60
TON_FEE_RESERVE_NANO = 50_000_000

# =============================================================================
# TO'LOV USULI: FAQAT USDT (TON zanjiri)
# =============================================================================
# Bot Stars'ni Fragment'dan FAQAT USDT (TON jetton) orqali oladi.
# Gram / TON / boshqa turlar butunlay yo'q — ataylab shunday qilingan.
#
# MUHIM: Fragment "payment_method" uchun KO'RSATILGAN nomni emas, ICHKI KODni
# yuboradi. Masalan GRAM -> "ton". USDT esa boshqa kod (ko'pincha "crypto").
# "usdt" deb yozish Fragment'da "Access denied" keltiradi.
#
# Aniq kodni qayerdan ko'rish:
#   fragment.com/stars -> DevTools -> Network -> "api" filteri ->
#   initBuyStarsRequest so'rovi -> Payload -> payment_method
#
# Birinchi ishlagan kod ishlatiladi, qolganlari zaxira sifatida sinanadi.
# MUHIM: Fragment "payment_method" uchun ICHKI KOD yuboradi va zanjir bo'yicha
# farqlanadi. Haqiqiy qiymatlar (brauzerdan tasdiqlandi):
#   GRAM / Toncoin -> "ton"
#   USDT (TON zanjiri) -> "usdt_ton"   ← bizning ushimiz shu
#   boshqa zanjirlar (ETH/BSC/...) -> boshqa kodlar
FRAGMENT_PAYMENT_METHODS = ["usdt_ton", "crypto", "usdt", "jetton"]
FRAGMENT_PAYMENT_METHOD = (
    os.getenv("FRAGMENT_PAYMENT_METHOD", "").strip().lower() or FRAGMENT_PAYMENT_METHODS[0]
)
# `balance` parametrini yuborish kerakmi? Brauzer yubormaydi (tasdiqlandi),
# shuning uchun odatda yuborilmaydi. FRAGMENT_SEND_BALANCE=1 bilan yoqiladi.
FRAGMENT_SEND_BALANCE = os.getenv("FRAGMENT_SEND_BALANCE", "0").strip().lower() in ("1", "true", "yes")
_env_method = os.getenv("FRAGMENT_PAYMENT_METHOD", "").strip().lower()

# USDT jetton master (TON zanjiri) — O'Zgartiring (ixtiyoriy)
USDT_MASTER = os.getenv("USDT_MASTER", "EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs")
USDT_DECIMALS = 6
# 1 Stars uchun taxminiy USDT narxi (ko'rsatish va bashorat uchun).
# 50 Stars ≈ 0.75 USDT  ->  0.015 USDT/Stars
STAR_USDT_RATE = Decimal(os.getenv("STAR_USDT_RATE", "0.015"))
# Fragment bozori qimmatlashsa, tekshiruv chegarasi (faqat nazorat uchun)
USDT_MAX_PER_STAR = Decimal(os.getenv("USDT_MAX_PER_STAR", "0.03"))
JETTON_TRANSFER_OP = 0x0F8A7EA5

# TON lite-server ishonch darajasi:
#   1 — tez, lekin server shard "out of sync" bo'lsa butun xaridni hal qiladi
#   2 — bloklarni tekshiradi, barqaror ("Liteserver crashed with 651" oldini oladi)
TON_TRUST_LEVEL = int(os.getenv("TON_TRUST_LEVEL", "2"))

# USDT -> UZS kursi. Asosiy manba: live API, zaxira: ENV (offline holat uchun)
USDT_RATE_FALLBACK = Decimal(os.getenv("USDT_RATE_UZS", "13000"))
USDT_RATE_TTL = int(os.getenv("USDT_RATE_TTL", "300"))  # 5 daqiqa kesh
_history_LIMIT = None  # (ixtiyoriy marker)
HISTORY_LIMIT = 100
TZ = timezone(timedelta(hours=5))

# =============================================================================
# 3. LOGGING
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
log = logging.getLogger("neon_store")
for _noisy in ("LiteClient", "LiteBalancer", "pytoniq", "BlockStore"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

if _env_method and _env_method != "usdt":
    log.warning(
        "FRAGMENT_PAYMENT_METHOD=%s bekor qilindi — bot faqat USDT (TON) orqali to'laydi.",
        _env_method,
    )
log.info("💎 To'lov usuli: FAQAT USDT (TON) — Fragment")


# =============================================================================
# 4. YORDAMCHI FUNKSIYALAR
# =============================================================================
def now() -> datetime:
    return datetime.now(TZ)


def now_iso() -> str:
    return now().isoformat(timespec="seconds")


def fmt(n: int | float) -> str:
    return f"{int(n):,}".replace(",", " ")


def esc(text: Any) -> str:
    return html.escape(str(text if text is not None else ""))


def new_id(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:10]}"


USERNAME_RE = re.compile(r"^@?([A-Za-z][A-Za-z0-9_]{3,31})$")


def normalize_username(raw: str) -> Optional[str]:
    m = USERNAME_RE.match((raw or "").strip())
    return m.group(1) if m else None


def parse_uzs_amount(raw: str) -> Optional[int]:
    s = re.sub(r"[\s  ']", "", raw or "")
    if not s:
        return None
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".") if re.search(r",\d{1,2}$", s) else s.replace(",", "")
    elif "." in s and not re.search(r"\.\d{1,2}$", s):
        s = s.replace(".", "")
    try:
        return int(Decimal(s))
    except (InvalidOperation, ValueError):
        return None


def to_nano(value: Any) -> int:
    return int(Decimal(str(value)) * Decimal(10**9))


def from_nano(value: int) -> str:
    return f"{Decimal(value) / Decimal(10**9):.4f}"


def b64decode_padded(data: str) -> bytes:
    data = (data or "").strip().replace("\n", "")
    data += "=" * (-len(data) % 4)
    if "-" in data or "_" in data:
        return base64.urlsafe_b64decode(data)
    return base64.b64decode(data)


# =============================================================================
# 5. JSON MA'LUMOTLAR BAZASI
# =============================================================================
class JsonDB:
    def __init__(self, path: str):
        self.path = path
        self._file_lock = threading.Lock()
        self.data: dict[str, Any] = self._load()
        for key in ("users", "topups", "sales", "orders"):
            self.data.setdefault(key, {})
        self.data.setdefault("processed_bank_msgs", [])
        self.data.setdefault("settings", {"bot_active": True})
        self._last_mtime = self._file_mtime()

    def _file_mtime(self) -> float:
        try:
            return os.path.getmtime(self.path)
        except OSError:
            return 0.0

    def reload_if_changed(self) -> bool:
        """Fayl tashqaridan (WebApp/server.ts) o'zgargan bo'lsa, xotirani yangilaydi.

        Bot va WebApp bitta JSON faylda ishlaydi. WebApp buyurtma yaratganda bot
        shu o'zgarishni ko'rishi kerak, aks holda buyurtma "yo'q" bo'lib qoladi.
        """
        mtime = self._file_mtime()
        if mtime <= self._last_mtime:
            return False
        fresh = self._load()
        if not fresh:
            return False
        with self._file_lock:
            self.data = fresh
            for key in ("users", "topups", "sales", "orders"):
                self.data.setdefault(key, {})
            self.data.setdefault("processed_bank_msgs", [])
            self.data.setdefault("settings", {"bot_active": True})
            self._last_mtime = mtime
        log.info("Baza tashqaridan yangilandi (WebApp yozuvi)")
        return True

    def _load(self) -> dict:
        for candidate in (self.path, self.path + ".bak"):
            if not os.path.exists(candidate):
                continue
            try:
                with open(candidate, "r", encoding="utf-8-sig") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    if candidate != self.path:
                        log.warning("Asosiy baza buzilgan, zaxiradan tiklandi: %s", candidate)
                    return data
            except (OSError, json.JSONDecodeError) as exc:
                log.error("Bazani o'qib bo'lmadi (%s): %s", candidate, exc)
        return {}

    def save(self) -> None:
        with self._file_lock:
            tmp = self.path + ".tmp"
            try:
                folder = os.path.dirname(os.path.abspath(self.path))
                os.makedirs(folder, exist_ok=True)
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(self.data, f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                if os.path.exists(self.path):
                    shutil.copy2(self.path, self.path + ".bak")
                os.replace(tmp, self.path)
                self._last_mtime = self._file_mtime()
            except OSError as exc:
                log.exception("Bazani saqlashda xato: %s", exc)

    @property
    def users(self) -> dict[str, dict]:
        return self.data["users"]

    def get_user(self, user_id: int) -> Optional[dict]:
        return self.users.get(str(user_id))

    def get_or_create_user(self, user_id: int, username: Optional[str], full_name: str) -> tuple[dict, bool]:
        user = self.get_user(user_id)
        created = False
        if user is None:
            user = {
                "id": user_id,
                "username": username,
                "full_name": full_name,
                "balance": 0,
                "history": [],
                "joined_at": now_iso(),
                "referrals_count": 0,
                "invited_by": None,
                "ref_rewarded": False,
                "banned": False,
                "total_topup": 0,
                "total_spent": 0,
                "pending_sale_card": None,
                "captcha_ok": False,
            }
            self.users[str(user_id)] = user
            created = True
            self.save()
        elif user.get("username") != username or user.get("full_name") != full_name:
            user["username"] = username
            user["full_name"] = full_name
            self.save()
        return user, created

    def find_user(self, query: str) -> Optional[dict]:
        q = (query or "").strip()
        if q.lstrip("-").isdigit():
            return self.get_user(int(q))
        name = q.lstrip("@").lower()
        for u in self.users.values():
            if (u.get("username") or "").lower() == name:
                return u
        return None

    def add_history(self, user: dict, htype: str, amount: int, details: str = "", unit: str = "UZS") -> None:
        entry = {"type": htype, "amount": int(amount), "details": details, "date": now_iso()}
        if unit != "UZS":
            entry["unit"] = unit
        user.setdefault("history", []).append(entry)
        user["history"] = user["history"][-HISTORY_LIMIT:]

    def change_balance(self, user_id: int, delta: int, htype: str, details: str = "") -> int:
        user = self.get_user(user_id)
        if user is None:
            raise KeyError(f"User {user_id} not found")
        new_balance = int(user.get("balance", 0)) + int(delta)
        if new_balance < 0:
            raise ValueError("Insufficient balance")
        user["balance"] = new_balance
        self.add_history(user, htype, delta, details)
        self.save()
        return new_balance


db = JsonDB(DB_PATH)
log.info(f"Baza fayli: {DB_PATH}")
# Eski bazadan qolib ketgan o'chirilgan holatni tuzatish:
# agar settings.bot_active old botda False qilib qoldirilgan bo'lsa, True qilamiz
if not db.data.get("settings", {}).get("bot_active", True):
    log.warning("Eski bazada bot_active False edi — True qilindi")
    db.data["settings"]["bot_active"] = True
    db.save()

bot: Optional[Bot] = None
userbot: Optional[UserbotClient] = None
DP: Optional[Dispatcher] = None
PURCHASE_LOCK = asyncio.Lock()
ADMIN_SESSIONS: dict[int, float] = {}
ADMIN_FAILED: dict[int, list[float]] = {}
ADMIN_SESSION_TTL = 12 * 3600

# =============================================================================
# 6. FRAGMENT.COM
# =============================================================================
FRAGMENT_BASE = "https://fragment.com"


class FragmentError(Exception):
    pass


@dataclass
class FragmentTx:
    destination: str
    amount_nano: int
    payload_type: str
    payload: str
    req_id: Optional[str] = None
    messages_count: int = 1
    payment_method: str = ""


def _wallet_balance_nano() -> int:
    """TON hamyon balansini nano birlikda oladi (sinxron — Fragment oqimi uchun)."""
    async def _get() -> int:
        provider, wallet = await connect_wallet(retries=2)
        try:
            return await wallet.get_balance()
        finally:
            try:
                await provider.close_all()
            except Exception:  # noqa: BLE001
                pass

    return asyncio.run(_get())


def _wallet_addresses() -> dict[str, str]:
    """TON hamyon va uning USDT jetton manzilini qaytaradi (sinxron)."""
    async def _get() -> dict[str, str]:
        provider, wallet = await connect_wallet(retries=2)
        try:
            jetton = await usdt_wallet_address(provider, wallet.address)
            return {
                "wallet": wallet.address.to_str(is_user_friendly=True),
                "usdt": jetton.to_str(is_user_friendly=True),
            }
        finally:
            try:
                await provider.close_all()
            except Exception:  # noqa: BLE001
                pass

    return asyncio.run(_get())


def parse_fragment_transaction(resp: dict) -> FragmentTx:
    if not isinstance(resp, dict):
        raise FragmentError("Fragment javobi noto'g'ri formatda")

    tx = resp.get("transaction") if isinstance(resp.get("transaction"), dict) else resp
    messages = tx.get("messages") or []
    msg = messages[0] if messages and isinstance(messages[0], dict) else {}
    count = max(1, len(messages))

    destination = msg.get("address") or tx.get("destination") or tx.get("address") or resp.get("destination") or ""

    if msg.get("amount") is not None:
        # Fragment miqdorni ham nano (butun son), ham decimal TON ("0.015") ko'rinishida
        # qaytarishi mumkin. int(Decimal("0.015")) == 0 bo'lgani uchun alohata
        # tekshiramiz — aks holda to'lov "noto'g'ri miqdor" deb rad etiladi.
        raw_amount = Decimal(str(msg["amount"]))
        amount_nano = int(raw_amount * 10**9) if raw_amount < 10**6 else int(raw_amount)
    elif tx.get("ton_amount") is not None or resp.get("ton_amount") is not None:
        amount_nano = to_nano(tx.get("ton_amount", resp.get("ton_amount")))
    elif tx.get("amount") is not None:
        raw = str(tx["amount"])
        amount_nano = to_nano(raw) if "." in raw or int(Decimal(raw)) < 10**6 else int(Decimal(raw))
    else:
        raise FragmentError("Fragment javobida TON miqdori yo'q")

    if amount_nano <= 0:
        raise FragmentError("Fragment noto'g'ri TON miqdori qaytardi")

    for src in (msg, tx, resp):
        if src.get("text"):
            return FragmentTx(destination, amount_nano, "text", str(src["text"]), messages_count=count)
        if src.get("bin"):
            return FragmentTx(destination, amount_nano, "bin", str(src["bin"]), messages_count=count)
        if src.get("payload"):
            return FragmentTx(destination, amount_nano, "bin", str(src["payload"]), messages_count=count)
    return FragmentTx(destination, amount_nano, "none", "", messages_count=count)


def build_comment_payload(payload_type: str, payload: str) -> Cell:
    if payload_type == "text":
        text = payload
        builder = begin_cell().store_uint(0, 32)
        if len(text.encode("utf-8")) <= 123:
            builder = builder.store_string(text)
        else:
            builder = builder.store_snake_string(text)
        return builder.end_cell()

    if payload_type == "bin":
        raw = b64decode_padded(payload)
        try:
            return Cell.one_from_boc(raw)
        except Exception as exc:  # noqa: BLE001
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                raise FragmentError(f"Fragment payload'ini o'qib bo'lmadi: {exc}") from exc
            return build_comment_payload("text", text)

    return begin_cell().end_cell()


def describe_payload(body: Cell) -> str:
    try:
        sl = body.begin_parse()
        if sl.remaining_bits >= 32 and sl.load_uint(32) == 0:
            return sl.load_snake_string()
        return f"<binary payload, {len(body.to_boc())} bayt>"
    except Exception:  # noqa: BLE001
        return "<o'qib bo'lmadi>"


class FragmentClient:
    def __init__(self, cookies: dict[str, str]):
        self.scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "desktop": True}
        )
        clean = {k: str(v).strip().strip('"').strip("'") for k, v in cookies.items()}
        for part in FRAGMENT_COOKIE_HEADER.strip().strip('"').strip("'").split(";"):
            if "=" in part:
                name, value = part.split("=", 1)
                if name.strip():
                    clean[name.strip()] = value.strip()
        self.auth_cookies = {k: v for k, v in clean.items() if v}
        self.rejected_cookies: set[str] = set()
        self._pin_cookies()
        self.missing_cookies = [k for k in ("stel_ssid", "stel_token", "stel_ton_token") if not clean.get(k)]
        if FRAGMENT_USER_AGENT:
            self.scraper.headers["User-Agent"] = FRAGMENT_USER_AGENT
        if FRAGMENT_PROXY:
            self.scraper.proxies = {"http": FRAGMENT_PROXY, "https": FRAGMENT_PROXY}
        self.api_hash: Optional[str] = FRAGMENT_API_HASH.strip() or None
        self._lock = threading.Lock()
        self.last_page_html = ""
        # Fragment brauzerda `dh` ni butun sahifa davomida BIR XIL saqlaydi
        # (kuzatuv: 20+ so'rov, barchasi dh=395299368). Biz ham shunday qilamiz —
        # har chaqiruvda yangilash sessiyani buzishi mumkin.
        self._buy_dh: Optional[str] = None

    def _pin_cookies(self) -> None:
        jar = self.scraper.cookies
        for c in list(jar):
            if c.name in self.auth_cookies and "fragment.com" in (c.domain or ""):
                if c.value != self.auth_cookies[c.name] and c.name != "stel_dt":
                    if c.name not in self.rejected_cookies:
                        log.warning("Fragment %s cookie'sini almashtirmoqchi bo'ldi", c.name)
                    self.rejected_cookies.add(c.name)
                jar.clear(c.domain, c.path, c.name)
        for name, value in self.auth_cookies.items():
            jar.set(name, value, domain="fragment.com", path="/")

    def _ajax_headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": FRAGMENT_BASE,
            "Referer": f"{FRAGMENT_BASE}/stars/buy",
            "X-Requested-With": "XMLHttpRequest",
        }

    def fetch_api_hash(self) -> str:
        last_error = "unknown"
        for url in (f"{FRAGMENT_BASE}/stars", f"{FRAGMENT_BASE}/stars/buy"):
            try:
                self._pin_cookies()
                r = self.scraper.get(url, timeout=30)
                self._pin_cookies()
            except Exception as exc:  # noqa: BLE001
                last_error = f"{url}: {exc}"
                continue
            if r.status_code != 200:
                last_error = f"{url}: HTTP {r.status_code}"
                continue
            m = (
                re.search(r'data-api-hash="([A-Za-z0-9]+)"', r.text)
                or re.search(r"api\?hash=([A-Za-z0-9]+)", r.text)
                or re.search(r'"apiHash"\s*:\s*"([A-Za-z0-9]+)"', r.text)
            )
            if m:
                self.api_hash = m.group(1)
                self.last_page_html = r.text
                log.info("Fragment api_hash olindi: %s…", self.api_hash[:6])
                return self.api_hash
            last_error = f"{url}: api hash sahifada topilmadi"
        raise FragmentError(f"Fragment api_hash olinmadi ({last_error})")

    def api(self, method: str, **params: Any) -> dict:
        with self._lock:
            if not self.api_hash:
                self.fetch_api_hash()
            payload = {**params, "method": method}
            for attempt in range(2):
                try:
                    self._pin_cookies()
                    r = self.scraper.post(
                        f"{FRAGMENT_BASE}/api",
                        params={"hash": self.api_hash},
                        data=payload,
                        headers=self._ajax_headers(),
                        timeout=40,
                    )
                except Exception as exc:  # noqa: BLE001
                    raise FragmentError(f"Fragment tarmoq xatosi: {exc}") from exc

                try:
                    data = r.json()
                except ValueError:
                    if attempt == 0 and r.status_code in (400, 403):
                        self.fetch_api_hash()
                        continue
                    raise FragmentError(f"Fragment JSON qaytarmadi (HTTP {r.status_code})")

                if isinstance(data, dict) and data.get("error"):
                    err = str(data["error"])
                    lower = err.lower()
                    # "Access denied" — bu sessiya/holat muammosi, HASH muammosi emas.
                    # Hashni qayta skrap qilish to'g'ri ishlagan hashni buzadi,
                    # shuning uchun faqat hash bilan bog'liq xatolarda yangilanadi.
                    if attempt == 0 and "hash" in lower and "access denied" not in lower:
                        self.fetch_api_hash()
                        continue
                    self._pin_cookies()
                    hint = ""
                    if "access denied" in lower:
                        hint = (" — Fragment sessiyasi yoki xarid holati to'g'ri emas. "
                                "Cookie muddati o'tgan bo'lishi mumkin (fragment.com'da "
                                "qayta kiring) yoki updateStarsBuyState muvaffaqiyatsiz.")
                    raise FragmentError(f"Fragment [{method}]: {err}{hint}")
                if not isinstance(data, dict):
                    raise FragmentError("Fragment javobi noto'g'ri formatda")
                return data
            raise FragmentError("Fragment so'rovi muvaffaqiyatsiz")

    async def probe_init_variants(self, recipient: str, amount: int,
                                 balance_nano: Optional[int]) -> list[str]:
        """initBuyStarsRequest ning turli kombinatsiyalarini sinab ko'radi.

        Maqsad — Fragment'ning talab qiladigan aniq parametrlarni avtomatik topish.
        Har bir kombinatsiya xavfsiz: muvaffaqiyatsiz bo'lsa hech narsa yaratilmaydi.
        """
        lines: list[str] = []
        methods = FRAGMENT_PAYMENT_METHODS + ["ton"]
        variants = [
            ("balance bilan", {"balance": str(int(balance_nano))} if balance_nano else {}),
            ("balansiz", {}),
        ]

        for label, extra in variants:
            for method in methods:
                params: dict[str, Any] = {
                    "recipient": recipient,
                    "quantity": amount,
                    "payment_method": method,
                    **extra,
                }
                try:
                    self.update_buy_state(amount)
                    init = self.api("initBuyStarsRequest", **params)
                except FragmentError as exc:
                    msg = str(exc).replace("\n", " ")[:70]
                    lines.append(f"❌ {method:7} + {label:12} — {msg}")
                    continue
                req_id = init.get("req_id")
                if req_id:
                    lines.append(f"✅✅ {method:7} + {label:12} — req_id={req_id} ISHLADI!")
                else:
                    lines.append(f"⚠️ {method:7} + {label:12} — req_id yo'q: {json.dumps(init)[:70]}")
        return lines

    async def diagnose(self, username: str) -> list[str]:
        lines = []
        lines.append(f"🍪 Cookie'lar: {', '.join(sorted(self.auth_cookies)) or 'YO‘Q'}")
        if self.missing_cookies:
            lines.append(f"⚠️ Yetishmayotgan: {', '.join(self.missing_cookies)}")
        try:
            self.api_hash = None
            h = self.fetch_api_hash()
            lines.append(f"✅ api_hash olindi ({h[:10]}…)")
        except Exception as exc:  # noqa: BLE001
            lines.append(f"❌ api_hash: {exc}")
            lines.append("💡 Sahifa bloklangan bo'lishi mumkin — FRAGMENT_API_HASH ni qo'lda kiriting")
            return lines

        # 1) Xarid holati (majburiy qadam)
        try:
            self.update_buy_state(MIN_STARS_BUY)
            lines.append("✅ updateStarsBuyState (xarid holati)")
        except FragmentError as exc:
            lines.append(f"❌ updateStarsBuyState: {exc}")
            lines.append("💡 Bu qadam uzilmasa, initBuyStarsRequest 'Access denied' beradi")

        # 2) Qabul qiluvchi
        try:
            found = self.api("searchStarsRecipient", query=username, quantity=MIN_STARS_BUY)
            recipient = (found.get("found") or {}).get("recipient")
            lines.append(f"{'✅' if recipient else '⚠️'} searchStarsRecipient(@{username}): "
                         f"{'topildi' if recipient else 'topilmadi'}")
        except Exception as exc:  # noqa: BLE001
            lines.append(f"❌ searchStarsRecipient: {exc}")
            return lines

        # 3) initBuyStarsRequest — eng ko'p rad etiladigan bosqich.
        #    Haqiqiy TON balans talab qilinadi, shuning uchun WALLET_SEED kerak.
        if not recipient:
            lines.append("⏭️ initBuyStarsRequest: tekshirilmadi (qabul qiluvchi topilmadi)")
            return lines
        if not WALLET_WORDS:
            lines.append("⚠️ WALLET_SEED yo'q — init tekshiruvi o'tkazilmaydi")
            return lines

        # Hamyon manzillari: USDT alohida jetton manzilida saqlanadi
        try:
            balance = await asyncio.to_thread(_wallet_balance_nano)
            addresses = await asyncio.to_thread(_wallet_addresses)
            lines.append(f"💰 TON manzil:  <code>{addresses['wallet']}</code>")
            lines.append(f"💵 USDT manzil: <code>{addresses['usdt']}</code>")
            lines.append(f"   (USDT shu jetton manzilida saqlanadi — aynan shu yerga yuboring)")
        except Exception as exc:  # noqa: BLE001
            lines.append(f"⚠️ Hamyon manzillarini olib bo'lmadi: {str(exc)[:80]}")

        try:
            balance = await asyncio.to_thread(_wallet_balance_nano)
            req_id, method = await asyncio.to_thread(
                self.init_buy_stars_request, recipient, MIN_STARS_BUY, balance
            )
            lines.append(f"✅ initBuyStarsRequest: req_id={req_id}")
            lines.append(f"💎 To'lov usuli kodi: <code>{esc(method)}</code>")
        except FragmentError as exc:
            lines.append(f"❌ initBuyStarsRequest: {str(exc)[:150]}")
            lines.append("")
            lines.append("🔬 <b>Barcha kombinatsiyalar sinanmoqda:</b>")
            try:
                probe = await self.probe_init_variants(recipient, MIN_STARS_BUY, balance)
                lines.extend(probe[:12])
                if not any("ISHLADI" in x for x in probe):
                    lines.append("")
                    lines.append(
                        "💡 Hech biri ishlamadi. Brauzerdan aniq so'rovni oling:\n"
                        "fragment.com/stars → F12 → Console → quyidagini yozing va "
                        "xaridni boshlang:\n"
                        "<code>const f=window.fetch;window.fetch=function(...a){"
                        "console.log('REQ',a[1]?.body);return f(...a)};"
                        "const s=XMLHttpRequest.prototype.send;"
                        "XMLHttpRequest.prototype.send=function(b){"
                        "console.log('REQ',b);return s.apply(this,arguments)}</code>"
                    )
            except Exception as exc:  # noqa: BLE001
                lines.append(f"❌ Sinov xatosi: {exc}")
        return lines

    def update_buy_state(self, amount: int) -> None:
        """Fragment'da Stars xaridi holatini yangilaydi — MAJBURIY QADAM.

        Fragment sayfasida har safar "Xarid qilish" ochilganda avval shu so'rov
        yuboriladi. `initBuyStarsRequest` faqat shundan KEYIN ishlaydi.

        Haqiqiy brauzer so'rovi (Network -> Payload):
            method=updateStarsBuyState, mode=new, lv=false, dh=<9 xonali son>

        Bu qadam muvaffaqiyatsiz bo'lsa, keyingi so'rov "Access denied" oladi —
        shuning uchun xatoni jimgina o'tkazmaymiz, darhol ko'taramiz.
        """
        last_error: Optional[Exception] = None
        for attempt in range(2):
            # `dh` butun sessiya davomida bir xil qoladi (brauzerdagidek)
            if self._buy_dh is None:
                self._buy_dh = str(random.randint(100000000, 9999999999))
            try:
                self.api("updateStarsBuyState", mode="new", lv="false", dh=self._buy_dh)
                log.debug("Fragment updateStarsBuyState yangilandi (dh=%s)", self._buy_dh)
                return
            except FragmentError as exc:
                last_error = exc
                log.warning("updateStarsBuyState muvaffaqiyatsiz (%d/2): %s", attempt + 1, exc)
                self._buy_dh = None      # muvaffaqiyatsiz bo'lsa — yangi qiymat
                if attempt == 0:
                    time.sleep(1.2)
        raise FragmentError(f"Fragment xarid holatini yangilab bo'lmadi: {last_error}")

    def init_buy_stars_request(
        self,
        recipient: str,
        amount: int,
        balance_nano: Optional[int] = None,
    ) -> tuple[str, str]:
        """Buyurtmani yaratadi va (req_id, payment_method) qaytaradi.

        Fragment `initBuyStarsRequest` da to'lovchining TON balansini (`balance`)
        yuborishni talab qiladi — gaz to'lovi yetarliligini tekshiradi.

        "Access denied" bo'lsa ikki narsa sinab ko'riladi:
          1) Fragment ichki `payment_method` kodi (crypto/usdt/jetton)
          2) xarid holatini tiklash (updateStarsBuyState) va hash'ni qayta olish
        """
        candidates = [FRAGMENT_PAYMENT_METHOD] + [
            m for m in FRAGMENT_PAYMENT_METHODS if m != FRAGMENT_PAYMENT_METHOD
        ]
        last_error: Optional[str] = None

        for index, method in enumerate(candidates):
            params: dict[str, Any] = {
                "recipient": recipient,
                "quantity": amount,
                "payment_method": method,
            }
            # Brauzer `balance` parametrini YUBORMAYDI (2026-10 da tekshirilgan),
            # shuning uchun biz ham standart holatda yubormaymiz.
            # FRAGMENT_SEND_BALANCE=1 bo'lsa yuboriladi.
            if balance_nano is not None and FRAGMENT_SEND_BALANCE:
                params["balance"] = str(int(balance_nano))

            try:
                init = self.api("initBuyStarsRequest", **params)
            except FragmentError as exc:
                last_error = str(exc)
                if "access denied" not in last_error.lower():
                    raise
                log.warning(
                    "initBuyStarsRequest 'Access denied' (payment_method=%s) — "
                    "keyingi kod sinanadi", method,
                )
                if index + 1 < len(candidates):
                    time.sleep(0.8)
                    self.update_buy_state(amount)
                continue

            req_id = init.get("req_id")
            if not req_id:
                last_error = f"req_id yo'q: {json.dumps(init)[:160]}"
                log.warning("initBuyStarsRequest req_id bermadi (%s)", method)
                if index + 1 < len(candidates):
                    time.sleep(0.8)
                    self.update_buy_state(amount)
                continue

            if index == 0:
                log.info("Fragment to'lov usuli: %s ✅", method)
            else:
                log.info("Fragment to'lov usuli '%s' ishlamadi, '%s' ishladi ✅", FRAGMENT_PAYMENT_METHOD, method)
            return str(req_id), method

        raise FragmentError(
            "Fragment USDT to'lov usuli topilmadi. Aniq kodni ko'rish uchun: "
            "fragment.com/stars → DevTools → Network → initBuyStarsRequest → Payload "
            f"→ payment_method. Sinangan kodlar: {', '.join(candidates)}. "
            f"Oxirgi javob: {last_error}"
        )

    def create_stars_order(
        self,
        username: str,
        amount: int,
        account: dict,
        device: dict,
        balance_nano: Optional[int] = None,
    ) -> FragmentTx:
        username = username.lstrip("@")

        # 1) Xarid holatini yangilash (MAJBURIY — init dan oldin)
        self.update_buy_state(amount)

        # 2) Qabul qiluvchini topish
        found = self.api("searchStarsRecipient", query=username, quantity=amount)
        recipient = (found.get("found") or {}).get("recipient")
        if not recipient:
            raise FragmentError(f"@{username} Fragment'da topilmadi")

        # 3) Buyurtma — FAQAT USDT (TON), balans bilan
        req_id, used_method = self.init_buy_stars_request(recipient, amount, balance_nano)

        link = self.api(
            "getBuyStarsLink",
            account=json.dumps(account, separators=(",", ":")),
            device=json.dumps(device, separators=(",", ":")),
            transaction=1,
            id=req_id,
            show_sender=0,
        )
        if not link.get("ok", True) and not link.get("transaction"):
            raise FragmentError("Fragment tranzaksiya ma'lumotini qaytarmadi")

        tx = parse_fragment_transaction(link)
        tx.req_id = str(req_id)
        tx.payment_method = used_method
        return tx


fragment = FragmentClient(FRAGMENT_COOKIES)

TONCONNECT_DEVICE = {
    "platform": "windows",
    "appName": "tonkeeper",
    "appVersion": "3.27.0",
    "maxProtocolVersion": 2,
    "features": ["SendTransaction", {"name": "SendTransaction", "maxMessages": 4}],
}


# =============================================================================
# 7. TON BLOKCHEYN
# =============================================================================
class PurchaseError(Exception):
    pass


@dataclass
class PurchaseResult:
    confirmed: bool
    ton_amount_nano: int
    destination: str
    req_id: Optional[str]
    wallet_balance_after: Optional[int] = None
    usdt_amount: Optional[int] = None


def build_tonconnect_account(wallet: WalletV4R2) -> dict:
    state_init_b64 = ""
    try:
        if wallet.state_init is not None:
            state_init_b64 = base64.b64encode(wallet.state_init.serialize().to_boc()).decode()
    except Exception as exc:  # noqa: BLE001
        log.warning("state_init serializatsiya xatosi: %s", exc)
    return {
        "address": wallet.address.to_str(is_user_friendly=False),
        "chain": "-239",
        "walletStateInit": state_init_b64,
        "publicKey": wallet.public_key.hex() if wallet.public_key else "",
    }


# =============================================================================
# 7.1 USDT -> UZS KURSI (live API + ENV zaxira)
# =============================================================================
# Asosiy manba: CoinGecko (USDT/USD) x frankfurter.app (USD/UZS)
# Kechilgan bo'lsa yoki internet yo'q bo'lsa — USDT_RATE_UZS (ENV) ishlatiladi.
_rate_cache: dict[str, Any] = {"rate": None, "ts": 0.0}
RATE_SOURCES = (
    ("https://api.coingecko.com/api/v3/simple/price?ids=tether&vs_currencies=usd", ("tether", "usd")),
    ("https://api.coingecko.com/api/v3/simple/price?ids=usd&vs_currencies=usdt", ("usd", "usdt")),
)
FX_URL = "https://api.frankfurter.app/latest?from=USD&to=UZS"


async def get_usdt_uzs_rate(force: bool = False) -> Decimal:
    """1 USDT = necha UZS. Kesh 5 daqiqa, xato bo'lsa ENV qiymatiga qaytadi."""
    now = time.time()
    if not force and _rate_cache["rate"] and now - float(_rate_cache["ts"]) < USDT_RATE_TTL:
        return Decimal(str(_rate_cache["rate"]))

    rate: Optional[Decimal] = None
    for url, path in RATE_SOURCES:
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                resp = await client.get(url, headers={"User-Agent": "NeonStore/1.0"})
                data = resp.json()
            value = data
            for key in path:
                value = value[key]
            usd_per_usdt = Decimal(str(value))
            if usd_per_usdt <= 0:
                continue

            async with httpx.AsyncClient(timeout=12) as client:
                resp = await client.get(FX_URL, headers={"User-Agent": "NeonStore/1.0"})
                uzs = Decimal(str(resp.json()["rates"]["UZS"]))
            rate = (usd_per_usdt * uzs).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            break
        except Exception as exc:  # noqa: BLE001
            log.debug("Kurs manbasi %s ishlamadi: %s", url, exc)

    if rate and rate > 0:
        _rate_cache["rate"] = float(rate)
        _rate_cache["ts"] = now
        db.data.setdefault("settings", {})["usdt_rate_uzs"] = float(rate)
        db.data["settings"]["usdt_rate_updated_at"] = now_iso()
        db.save()
        log.info("💱 USDT/UZS kursi yangilandi: %s so'm", fmt(rate))
        return rate

    log.warning("Kurs API'sidan olib bo'lmadi — USDT_RATE_UZS zaxirasi ishlatilmoqda")
    _rate_cache["rate"] = float(USDT_RATE_FALLBACK)
    _rate_cache["ts"] = now
    return USDT_RATE_FALLBACK


async def usdt_to_uzd(usdt: Decimal) -> Decimal:
    """USDT summasini so'mga o'giradi (live/keshli kurs bilan)."""
    return (usdt * await get_usdt_uzs_rate()).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


async def _safe_seqno(wallet: WalletV4R2) -> Optional[int]:
    try:
        return int(await wallet.get_seqno())
    except Exception as exc:  # noqa: BLE001
        log.warning("seqno olinmadi: %s", exc)
        return None


async def _wait_seqno_change(wallet: WalletV4R2, old_seqno: int, timeout: int = 90) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        await asyncio.sleep(4)
        try:
            seqno = await ton_with_retry(wallet.get_seqno, "Seqno kuzatuvi", attempts=2)
        except Exception:  # noqa: BLE001
            continue
        if seqno is not None and int(seqno) > old_seqno:
            return True
    return False


def fmt_usdt(micro: int) -> str:
    return f"{Decimal(micro) / (10 ** USDT_DECIMALS):.2f}"


async def ton_with_retry(operation, name: str = "TON amali", attempts: int = 3):
    """TON RPC amalini vaqtinchalik server xatolarida qayta urinadi.

    "Liteserver crashed with 651 / out of sync" — shard vaqtincha mos emas.
    Bu holda yangi server bilan qayta urinish muammoni hal qiladi.
    """
    last_error: Optional[Exception] = None
    for attempt in range(attempts):
        try:
            return await operation()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            low = str(exc).lower()
            transient = any(
                k in low for k in
                ("liteserver crashed", "lite server", "not in db", "out of sync",
                 "shard", "651", "seqno", "timeout", "timed out", "connection")
            )
            if not transient or attempt + 1 >= attempts:
                if transient:
                    raise PurchaseError(f"{name}: TON tarmog'i barqaror emas — {exc}") from exc
                raise
            log.warning(
                "%s: vaqtinchalik TON xatosi (%d/%d), qayta urinilmoqda: %s",
                name, attempt + 1, attempts, str(exc)[:90],
            )
            await asyncio.sleep(2 + attempt * 2)
    raise PurchaseError(f"{name}: {last_error}")


async def connect_wallet(retries: int = 3):
    """TON tarmog'iga ishonchli ulanadi va WALLET_SEED dan hamyonni yuklaydi.

    `trust_level=1` lite-serverga ishonib qoladi va u shard'dan "out of sync"
    bo'lganda butun xaridni hal qiladi ("Liteserver crashed with 651 code").
    `trust_level=2` server bloklarni tekshiradi — sekinroq, lekin barqaror.
    Qo'shimcha: har bir urinishda YANGI provider yaratiladi (eski yopiladi).
    """
    last_error: Optional[Exception] = None
    for attempt in range(retries):
        provider = None
        try:
            provider = LiteBalancer.from_mainnet_config(trust_level=TON_TRUST_LEVEL)
            await provider.start_up()
            wallet = await WalletV4R2.from_mnemonic(provider, WALLET_WORDS)
            return provider, wallet
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            log.warning(
                "TON ulanishi %d/%d muvaffaqiyatsiz: %s",
                attempt + 1, retries, str(exc)[:120],
            )
            if provider is not None:
                try:
                    await provider.close_all()
                except Exception:  # noqa: BLE001
                    pass
            if attempt + 1 < retries:
                await asyncio.sleep(2 + attempt * 2)
    raise PurchaseError(f"TON tarmog'iga ulanib bo'lmadi: {last_error}")


async def usdt_wallet_address(provider: LiteBalancer, owner: Address) -> Address:
    async def _get() -> Address:
        stack = await provider.run_get_method(
            address=USDT_MASTER, method="get_wallet_address",
            stack=[begin_cell().store_address(owner).end_cell().begin_parse()],
        )
        return stack[0].load_address()

    return await ton_with_retry(_get, "USDT hamyon manzili", attempts=3)


async def usdt_balance(provider: LiteBalancer, jetton_wallet: Address) -> int:
    async def _get() -> int:
        stack = await provider.run_get_method(address=jetton_wallet, method="get_wallet_data", stack=[])
        return int(stack[0])

    try:
        return await ton_with_retry(_get, "USDT balansi", attempts=3)
    except Exception:  # noqa: BLE001
        return 0


def parse_jetton_transfer(body: Cell) -> tuple[int, Address]:
    try:
        cs = body.begin_parse()
        if cs.load_uint(32) != JETTON_TRANSFER_OP:
            raise ValueError("jetton transfer emas")
        cs.load_uint(64)
        return cs.load_coins(), cs.load_address()
    except Exception as exc:  # noqa: BLE001
        raise FragmentError(f"USDT to'lov ma'lumoti noto'g'ri: {exc}") from exc


async def verify_usdt_payment(provider: LiteBalancer, wallet: WalletV4R2, tx: "FragmentTx", body: Cell,
                              stars: int, ton_balance: int) -> int:
    if tx.messages_count != 1:
        raise PurchaseError(f"Fragment {tx.messages_count} ta xabarli tranzaksiya qaytardi")
    try:
        jetton_wallet = await usdt_wallet_address(provider, wallet.address)
    except Exception as exc:  # noqa: BLE001
        raise PurchaseError(f"USDT hamyon manzilini aniqlab bo'lmadi: {exc}") from exc
    try:
        dest = Address(tx.destination)
    except Exception as exc:  # noqa: BLE001
        raise PurchaseError(f"Fragment manzili noto'g'ri: {exc}") from exc
    if dest != jetton_wallet:
        raise PurchaseError("Fragment USDT to'lovini qaytarmadi")
    try:
        usdt_amount, _to = parse_jetton_transfer(body)
    except FragmentError as exc:
        raise PurchaseError(str(exc)) from exc
    limit = int(USDT_MAX_PER_STAR * stars * 10 ** USDT_DECIMALS)
    if usdt_amount <= 0 or usdt_amount > limit:
        raise PurchaseError(f"Kutilmagan USDT summasi: {fmt_usdt(usdt_amount)} USDT")
    have = await usdt_balance(provider, jetton_wallet)
    if have < usdt_amount:
        raise PurchaseError(f"Hamyonda USDT yetarli emas: {fmt_usdt(have)} USDT, kerak: {fmt_usdt(usdt_amount)} USDT")
    if ton_balance < tx.amount_nano + TON_FEE_RESERVE_NANO:
        raise PurchaseError(f"Gaz uchun TON yetarli emas: {from_nano(ton_balance)} TON")
    return usdt_amount


async def buy_stars_via_fragment(username: str, amount: int) -> PurchaseResult:
    if WALLET_SEED_ERROR:
        raise PurchaseError(WALLET_SEED_ERROR)

    async with PURCHASE_LOCK:
        provider = None
        try:
            # Ishonchli ulanish (2-3 marta qayta urinadi, yangi server bilan)
            provider, wallet = await connect_wallet()

            account = build_tonconnect_account(wallet)

            # Balans initBuyStarsRequest dan OLDIN kerak (Fragment "balance" parametrini
            # talab qiladi — u gaz to'lovi yetarliligini tekshiradi)
            balance = await ton_with_retry(
                wallet.get_balance, "Hamyon balansi", attempts=3
            )
            log.info("TON hamyon balansi: %s TON (gaz uchun)", from_nano(balance))

            try:
                tx = await asyncio.to_thread(
                    fragment.create_stars_order, username, amount, account, TONCONNECT_DEVICE, balance
                )
            except FragmentError as exc:
                raise PurchaseError(str(exc)) from exc
            except Exception as exc:  # noqa: BLE001
                raise PurchaseError(f"Fragment xatosi: {exc}") from exc

            destination = tx.destination or FRAGMENT_ADDRESS
            if not destination or "PUT_" in destination:
                raise PurchaseError("Fragment manzili aniqlanmadi")

            if tx.payload_type == "none":
                raise PurchaseError("Fragment to'lov ma'lumotini qaytarmadi")
            try:
                body = build_comment_payload(tx.payload_type, tx.payload)
            except Exception as exc:  # noqa: BLE001
                raise PurchaseError(f"Payload yaratishda xato: {exc}") from exc

            usdt_amount: Optional[int] = None
            # FAQAT USDT (TON) — boshqa to'lov usuli yo'q
            usdt_amount = await verify_usdt_payment(provider, wallet, tx, body, amount, balance)
            log.info(
                "USDT to'lov: %s USDT (gaz %s TON) -> Fragment",
                fmt_usdt(usdt_amount), from_nano(tx.amount_nano),
            )

            old_seqno = await ton_with_retry(wallet.get_seqno, "Seqno", attempts=3)
            old_seqno = int(old_seqno) if old_seqno is not None else None
            if old_seqno is None:
                raise PurchaseError("Hamyon seqno olinmadi")

            log.info(
                "TON transfer: %s TON -> %s (@%s, %s stars)",
                from_nano(tx.amount_nano), destination, username, amount,
            )
            transfer_error: Optional[Exception] = None
            try:
                await ton_with_retry(
                    lambda: wallet.transfer(destination=destination, amount=tx.amount_nano, body=body),
                    "TON transfer", attempts=2,
                )
            except Exception as exc:  # noqa: BLE001
                transfer_error = exc
                log.warning("transfer() xato berdi: %s", exc)

            confirmed = await _wait_seqno_change(wallet, old_seqno)
            if not confirmed and transfer_error is not None:
                raise PurchaseError(f"TON tranzaksiyasi yuborilmadi: {transfer_error}")

            balance_after = None
            try:
                balance_after = await ton_with_retry(wallet.get_balance, "Balans (keyin)", attempts=2)
            except Exception:  # noqa: BLE001
                pass

            return PurchaseResult(confirmed, tx.amount_nano, destination, tx.req_id, balance_after, usdt_amount)
        finally:
            try:
                await provider.close_all()
            except Exception:  # noqa: BLE001
                pass


# =============================================================================
# 8. FSM HOLATLARI
# =============================================================================
class BuyStates(StatesGroup):
    username = State()
    amount = State()
    confirm = State()


class SellStates(StatesGroup):
    amount = State()


class TopupStates(StatesGroup):
    amount = State()


class ServiceStates(StatesGroup):
    username = State()
    confirm = State()


class RefStates(StatesGroup):
    username = State()


class AdminStates(StatesGroup):
    password = State()
    broadcast = State()
    balance_user = State()
    balance_amount = State()
    balance_confirm = State()
    ban_user = State()
    unban_user = State()
    contest_text = State()
    contest_prize = State()
    contest_winners = State()
    contest_min = State()
    contest_days = State()
    ub_phone = State()
    ub_code = State()


# =============================================================================
# 9. KLAVIATURALAR VA RANGLI TUGMALAR (Image 1 dagi kabi)
# =============================================================================
BTN_BUY = "Stars sotib olish"
BTN_SELL = "Stars sotish"
BTN_TOPUP = "Balans to'ldirish"
BTN_PROFILE = "Profil"
BTN_REF = "Referal"
BTN_HISTORY = "Tarix"
BTN_WEBAPP = "Web App ❐"
BTN_PREMIUM = "Premium"
BTN_GIFTS = "Giftlar"
BTN_SUPPORT = "Support"
MENU_BUTTONS = {
    BTN_BUY, BTN_SELL, BTN_TOPUP, BTN_PROFILE, BTN_REF, BTN_HISTORY, BTN_PREMIUM, BTN_GIFTS, BTN_SUPPORT,
}
NOT_MENU = ~F.text.in_(MENU_BUTTONS)

BOT_USERNAME = ""


def webapp_config() -> dict:
    return {
        "sp": STAR_BUY_PRICE_UZS,
        "smin": MIN_STARS_BUY,
        "smax": MAX_STARS_BUY,
        "tmin": MIN_TOPUP,
        "tmax": MAX_TOPUP,
        "tm": TOPUP_TIMEOUT_SEC // 60,
        "rb": REF_BONUS_STARS,
        "rmin": REF_MIN_WITHDRAW,
        "prem": {mode: {str(m): p for m, p in plans.items()} for mode, plans in PREMIUM_PLANS.items()},
        "gifts": [[key, name, stars, price] for key, name, stars, price in GIFTS],
        "sup": SUPPORT_USERNAME,
    }


def webapp_history(user: dict) -> list[dict]:
    return [
        {"t": h.get("type"), "a": h.get("amount"), "d": (h.get("date") or "")[:16], "u": h.get("unit") or "UZS"}
        for h in (user.get("history") or [])[-10:]
    ]


def build_webapp_url(user: dict) -> str:
    params = {
        "uid": user["id"],
        "un": user.get("username") or "",
        "photo_url": user.get("photo_url") or "",
        "balance": int(user.get("balance", 0)),
        "refs": int(user.get("referrals_count", 0)),
        "rs": int(user.get("ref_stars", 0)),
        "bot": BOT_USERNAME,
        "history": json.dumps(webapp_history(user), ensure_ascii=False, separators=(",", ":")),
        "cfg": json.dumps(webapp_config(), ensure_ascii=False, separators=(",", ":")),
    }
    if webapp_api_enabled():
        params["api"] = WEBAPP_API_URL
    return f"{WEBAPP_URL}?{urlencode(params)}"


def webapp_menu_url() -> str:
    return f"{WEBAPP_URL}?" + urlencode({
        "bot": BOT_USERNAME, "api": WEBAPP_API_URL,
        "cfg": json.dumps(webapp_config(), ensure_ascii=False, separators=(",", ":")),
    })


def webapp_button(user: dict) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=BTN_WEBAPP, web_app=WebAppInfo(url=build_webapp_url(user)), style="primary")


# --------------------------- Tugma ranglari -----------------------------------
# Telegram 3 xil rang beradi: "success" — yashil, "primary" — ko'k, "danger" — qizil.
MENU_STYLES = {
    "m:buy": "success",      # Stars sotib olish — YASHIL
    "m:sell": "primary",     # Stars sotish — KO'K
    "m:premium": "primary",  # Premium — KO'K
    "m:gifts": "danger",     # Giftlar — QIZIL
    "m:topup": "success",    # Balans to'ldirish — YASHIL
    "m:ref": "primary",      # Referal — KO'K
    "m:webapp": "primary",   # Web App — KO'K
    "m:support": "danger",   # Support — QIZIL
}
SUCCESS_CALLBACKS = {"buy_confirm", "svc_ok", "ref_wd", "buy_self", "svc_self", "refw_self"}
SUCCESS_PREFIXES = ("ord_done:", "sale_pay:")
DANGER_CALLBACKS = {"cancel", "adm:logout", "adm:ban:ban"}
DANGER_PREFIXES = ("ord_refund:", "sale_refund:", "topup_cancel:")


def button_style(button: Any) -> Optional[str]:
    data = getattr(button, "callback_data", None) or ""
    if data in MENU_STYLES:
        return MENU_STYLES[data]
    if data == "adm:toggle":
        return "danger" if "to'xtatish" in button.text else "success"
    if data in SUCCESS_CALLBACKS or data.startswith(SUCCESS_PREFIXES):
        return "success"
    if data in DANGER_CALLBACKS or data.startswith(DANGER_PREFIXES):
        return "danger"
    if getattr(button, "web_app", None) is not None or getattr(button, "url", None):
        return "primary"
    return None


def _with_style(button: Any) -> Any:
    if not isinstance(button, InlineKeyboardButton) or getattr(button, "style", None):
        return button
    style = button_style(button)
    return button.model_copy(update={"style": style}) if style else button


def _without_icon(button: Any) -> Any:
    return button.model_copy(update={"icon_custom_emoji_id": None}) if getattr(button, "icon_custom_emoji_id", None) else button


def _map_markup(markup: Any, fn: Callable[[Any], Any]) -> Any:
    if isinstance(markup, InlineKeyboardMarkup):
        return markup.model_copy(update={"inline_keyboard": [[fn(b) for b in row] for row in markup.inline_keyboard]})
    if isinstance(markup, ReplyKeyboardMarkup):
        return markup.model_copy(update={"keyboard": [[fn(b) for b in row] for row in markup.keyboard]})
    return markup


def main_menu_kb(user: dict) -> InlineKeyboardMarkup:
    """Asosiy menyu — Rasm 1 dagi ranglar va ko'rinish bilan."""
    def b(text: str, action: str, style: Optional[str] = None) -> InlineKeyboardButton:
        st = style or MENU_STYLES.get(f"m:{action}")
        return InlineKeyboardButton(text=text, callback_data=f"m:{action}", style=st)

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [b("⭐ Stars sotib olish", "buy", "success")],
            [b("💸 Stars sotish", "sell", "primary"), b("💎 Premium", "premium", "primary")],
            [b("🎁 Giftlar", "gifts", "danger")],
            [b("💳 Balans to'ldirish", "topup", "success"), b("👥 Referal", "ref", "primary")],
            [InlineKeyboardButton(text="📱 Web App ❐", web_app=WebAppInfo(url=build_webapp_url(user)), style="primary")],
            [b("👤 Profil", "profile"), b("📜 Tarix", "history")],
            [InlineKeyboardButton(text="💬 Support", url=f"https://t.me/{SUPPORT_USERNAME}", style="danger")],
        ]
    )


def webapp_inline_kb(user: dict) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[webapp_button(user)]])


def cancel_inline_kb(cb: str = "cancel") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Bekor qilish", callback_data=cb, style="danger")]])


def bot_active() -> bool:
    return bool(db.data.setdefault("settings", {}).get("bot_active", True))


def admin_panel_text() -> str:
    state = "🟢 ishlayapti" if bot_active() else "🔴 to'xtatilgan"
    settings = db.data.get("settings", {})
    try:
        usdt = float(settings.get("wallet_usdt_balance", 0) or 0)
    except (TypeError, ValueError):
        usdt = 0.0
    try:
        ton = float(settings.get("wallet_ton_balance", 0) or 0)
    except (TypeError, ValueError):
        ton = 0.0
    try:
        rate = float(settings.get("usdt_rate_uzs", 0) or 0) or float(USDT_RATE_FALLBACK)
    except (TypeError, ValueError):
        rate = float(USDT_RATE_FALLBACK)

    wallet = settings.get("wallet_address") or "—"
    usdt_wallet = settings.get("wallet_usdt_address") or "—"

    return (
        f"🛠 <b>Admin panel</b>\n\n"
        f"Bot holati: <b>{state}</b>\n"
        f"💎 To'lov usuli: <b>USDT (TON)</b> — <code>usdt_ton</code>\n"
        f"\n<b>💰 Hamyonlar:</b>\n"
        f"├ TON: <b>{ton:.4f} TON</b> (gaz uchun)\n"
        f"├ USDT: <b>{usdt:.2f} USDT</b> (≈ {fmt(int(usdt * rate))} UZS)\n"
        f"├ TON manzil: <code>{esc(wallet)}</code>\n"
        f"└ USDT manzil: <code>{esc(usdt_wallet)}</code>\n"
        f"\n💱 Kurs: <b>1 USDT = {fmt(int(rate))} UZS</b>\n"
        f"\nℹ️ <i>USDT oddiy TON hamyonida emas, alohida <b>jetton</b> manzilida "
        f"saqlanadi. USDT yuborash uchun yuoridagi <b>USDT manzil</b>ga yuboring.</i>"
    )


def admin_kb() -> InlineKeyboardMarkup:
    active = bot_active()
    toggle = "⏸ Botni to'xtatish" if active else "▶️ Botni ishga tushirish"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=toggle, callback_data="adm:toggle",
                style="danger" if active else "success")],
            [InlineKeyboardButton(text="📊 Statistika", callback_data="adm:stats"),
             InlineKeyboardButton(text="📣 Xabar yuborish", callback_data="adm:bc")],
            [InlineKeyboardButton(text="🏆 Top 20", callback_data="adm:top20"),
             InlineKeyboardButton(text="🎉 Konkurs", callback_data="adm:contest")],
            [InlineKeyboardButton(text="➕ Balans qo'shish", callback_data="adm:bal_add"),
             InlineKeyboardButton(text="➖ Balans ayirish", callback_data="adm:bal_take")],
            [InlineKeyboardButton(text="🚫 Ban", callback_data="adm:ban"),
             InlineKeyboardButton(text="✅ Unban", callback_data="adm:unban")],
            [InlineKeyboardButton(text="💎 TON balans", callback_data="adm:wallet"),
             InlineKeyboardButton(text="🔎 Fragment test", callback_data="adm:diag")],
            [InlineKeyboardButton(text="🔑 Userbot ulash (QR)", callback_data="adm:ub_qr"),
             InlineKeyboardButton(text="📱 Raqam bilan ulash", callback_data="adm:ub_phone")],
            [InlineKeyboardButton(text="🩺 Userbot holati", callback_data="adm:ub_status")],
            [InlineKeyboardButton(text="🚪 Chiqish", callback_data="adm:logout", style="danger")],
        ]
    )


def admin_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm:home")]])


# =============================================================================
# 10. OBUNA, REFERAL, ADMIN YORDAMCHILARI
# =============================================================================
async def reward_referrer_if_needed(b: Bot, user: dict) -> None:
    ref_id = user.get("invited_by")
    if not ref_id or user.get("ref_rewarded"):
        return
    referrer = db.get_user(int(ref_id))
    user["ref_rewarded"] = True
    if referrer is None or referrer.get("banned"):
        db.save()
        return
    referrer["referrals_count"] = int(referrer.get("referrals_count", 0)) + 1
    referrer["ref_stars"] = int(referrer.get("ref_stars", 0)) + REF_BONUS_STARS
    referrer["ref_stars_earned"] = int(referrer.get("ref_stars_earned", 0)) + REF_BONUS_STARS
    db.add_history(referrer, "ref_bonus", REF_BONUS_STARS, f"Referal: {user['id']}", unit="stars")
    db.save()
    try:
        await b.send_message(
            referrer["id"],
            f"🎉 Sizning havolangiz orqali yangi do'stingiz qo'shildi!\n"
            f"⭐ Referal balansingizga <b>{REF_BONUS_STARS} stars</b> qo'shildi "
            f"(jami: {fmt(referrer['ref_stars'])} stars).",
        )
    except Exception as exc:  # noqa: BLE001
        log.info("Referrer'ga xabar yuborilmadi: %s", exc)


def is_admin_authed(user_id: int) -> bool:
    ts = ADMIN_SESSIONS.get(user_id)
    if user_id not in ADMIN_IDS or ts is None:
        return False
    if time.time() - ts > ADMIN_SESSION_TTL:
        ADMIN_SESSIONS.pop(user_id, None)
        return False
    return True


async def notify_admins(text: str, reply_markup: Optional[InlineKeyboardMarkup] = None) -> dict[int, int]:
    sent: dict[int, int] = {}
    if bot is None:
        return sent
    for admin_id in ADMIN_IDS:
        try:
            msg = await bot.send_message(admin_id, text, reply_markup=reply_markup)
            sent[admin_id] = msg.message_id
        except Exception as exc:  # noqa: BLE001
            log.warning("Adminga xabar yuborilmadi (%s): %s", admin_id, exc)
    return sent


async def ref_link(b: Bot, user: dict) -> str:
    me = await b.me()
    return f"t.me/{me.username}?start=u{user['id']}"


async def start_text(b: Bot, user: dict) -> str:
    name = f"@{user['username']}" if user.get("username") else (user.get("full_name") or "")
    return (
        f"👋 Assalomu alaykum, {esc(name)}\n\n"
        f"🆔 User ID: <code>{user['id']}</code>\n"
        f"💳 Balans: <b>{fmt(user.get('balance', 0))} so'm</b>\n\n"
        f"🔗 Referral link: {await ref_link(b, user)}"
    )


async def send_main_menu(message: Message, user: dict, text: Optional[str] = None) -> None:
    await message.answer(
        text or await start_text(message.bot, user),
        reply_markup=main_menu_kb(user),
        disable_web_page_preview=True,
    )


# =============================================================================
# 10b. RANGLI TUGMALAR MIDDLEWARE (Rasm 1)
# =============================================================================
class StyledButtonsMiddleware(BaseRequestMiddleware):
    _methods = (SendMessage, EditMessageText, SendPhoto, EditMessageCaption)

    @staticmethod
    def _transform(method: Any) -> Any:
        update: dict[str, Any] = {}
        if getattr(method, "reply_markup", None) is not None:
            update["reply_markup"] = _map_markup(method.reply_markup, _with_style)
        return method.model_copy(update=update)

    async def __call__(self, make_request, bot_: Bot, method):  # type: ignore[override]
        if not isinstance(method, self._methods):
            return await make_request(bot_, method)
        return await make_request(bot_, self._transform(method))


# =============================================================================
# 10.1 PREMIUM EMOJI MIDDLEWARE
# =============================================================================
class PremiumEmojiMiddleware(BaseRequestMiddleware):
    """Barcha xabarlardagi emojilarni Telegram premium (custom) emojiga aylantiradi.

    Telegram `parse_mode` va `entities` ni birga qabul qilmaydi, shuning uchun
    HTML matn oldindan yalang'och matn + entities ga aylantiriladi.
    Konvertatsiya xato bo'lsa — xabar oddiy HTML holida yuboriladi (xavfsiz).
    """

    _methods = (SendMessage, EditMessageText)

    @staticmethod
    def _transform(method: Any) -> Any:
        source = getattr(method, "text", None)
        if not source:
            return method
        rendered = render_text(source)
        if rendered is None:
            return method
        text, entities = rendered
        if not entities:
            return method.model_copy(update={"text": text, "parse_mode": None, "entities": []})
        return method.model_copy(update={"text": text, "parse_mode": None, "entities": entities})

    async def __call__(self, make_request, bot_: Bot, method):  # type: ignore[override]
        if not isinstance(method, self._methods):
            return await make_request(bot_, method)
        try:
            return await make_request(bot_, self._transform(method))
        except Exception as exc:  # noqa: BLE001
            # Entities bilan yuborilmasa — oddiy HTML bilan qayta urinamiz
            log.warning("Premium emoji yuborilmadi (%s), oddiy rejimga qaytildi", exc)
            return await make_request(bot_, method)


# =============================================================================
# 11. ACCESS MIDDLEWARE
# =============================================================================
class AccessMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        from_user = getattr(event, "from_user", None)
        if from_user is None or from_user.is_bot:
            return await handler(event, data)

        chat = event.chat if isinstance(event, Message) else (event.message.chat if event.message else None)
        if chat is not None and chat.type != "private":
            return None

        user, created = db.get_or_create_user(from_user.id, from_user.username, from_user.full_name)
        data["db_user"] = user
        data["is_new_user"] = created

        if user.get("banned") and from_user.id not in ADMIN_IDS:
            if isinstance(event, CallbackQuery):
                await event.answer("🚫 Siz bloklangansiz.", show_alert=True)
            else:
                await event.answer("🚫 Siz botdan foydalanishdan chetlatilgansiz.")
            return None

        if not bot_active() and from_user.id not in ADMIN_IDS:
            text = "⏸ Bot vaqtincha to'xtatilgan."
            if isinstance(event, CallbackQuery):
                await event.answer(text, show_alert=True)
            else:
                await event.answer(text)
            return None

        return await handler(event, data)


# =============================================================================
# 12. ROUTERLAR
# =============================================================================
common_router = Router(name="common")
router = Router(name="main")
admin_router = Router(name="admin")


@common_router.message(CommandStart())
async def cmd_start(
    message: Message, command: CommandObject, state: FSMContext, bot: Bot, db_user: dict, is_new_user: bool
):
    await state.clear()
    arg = (command.args or "").strip()
    ref_match = re.fullmatch(r"u?(\d+)", arg)
    if is_new_user and ref_match:
        ref_id = int(ref_match.group(1))
        if ref_id != db_user["id"] and db.get_user(ref_id) is not None:
            db_user["invited_by"] = ref_id
            db.save()

    await reward_referrer_if_needed(bot, db_user)

    # Robot emasligi tekshiruvi (captcha) — faqat yangi foydalanuvchilar uchun
    if not db_user.get("captcha_ok") and db_user["id"] not in ADMIN_IDS:
        await send_captcha(message, db_user)
        return

    # Eski ReplyKeyboard (doimiy klaviatura)ni olib tashlash
    try:
        rm = await message.answer("🚀", reply_markup=ReplyKeyboardRemove())
        try:
            await rm.delete()
        except Exception:
            pass
    except Exception:
        pass

    await send_main_menu(message, db_user)


@common_router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext, db_user: dict):
    await state.clear()
    await send_main_menu(message, db_user, "❌ Amal bekor qilindi.")


@common_router.callback_query(F.data == "cancel")
async def cb_cancel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.answer("Bekor qilindi")
    try:
        await call.message.edit_text("❌ Amal bekor qilindi.")
    except Exception:  # noqa: BLE001
        pass


@common_router.callback_query(F.data.startswith("captcha:"))
async def cb_captcha(call: CallbackQuery, state: FSMContext) -> None:
    uid = call.from_user.id
    user = db.get_user(uid)
    if user is None:
        await call.answer("Xatolik, /start bosing")
        return
    try:
        chosen = int(call.data.split(":", 1)[1])
    except Exception:  # noqa: BLE001
        await call.answer("Noto'g'ri")
        return
    if chosen == user.get("captcha_answer"):
        user["captcha_ok"] = True
        user.pop("captcha_answer", None)
        db.save()
        await call.answer("✅ To'g'ri!")
        try:
            await call.message.edit_text("✅ Robot emasligi tasdiqlandi.")
        except Exception:  # noqa: BLE001
            pass
        await send_main_menu(call.message, user)
    else:
        await call.answer("❌ Noto'g'ri, qayta urinib ko'ring.", show_alert=True)
        try:
            await call.message.edit_reply_markup(reply_markup=None)
        except Exception:  # noqa: BLE001
            pass
        await send_captcha(call.message, user)


@common_router.callback_query(F.data.startswith("adm_topup_ok:"))
async def adm_topup_ok(call: CallbackQuery) -> None:
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("Ruxsat yo'q", show_alert=True)
        return
    tid = call.data.split(":", 1)[1]
    t = db.data["topups"].get(tid)
    if not t or t["status"] != "pending":
        await call.answer("Bu so'rov allaqachon ko'rilgan", show_alert=True)
        return
    t["status"] = "completed"
    t["completed_at"] = now_iso()
    u = db.data["users"].get(str(t["user_id"]))
    if u:
        u["balance"] = int(u.get("balance", 0)) + t["amount"]
        u["total_topup"] = int(u.get("total_topup", 0)) + t["amount"]
        try:
            await bot.send_message(u["id"], f"✅ <b>{fmt(t['amount'])} UZS</b> balansingizga qo'shildi.")
        except Exception:  # noqa: BLE001
            pass
    db.data["settings"]["total_volume_uzs"] = int(db.data["settings"].get("total_volume_uzs", 0)) + t["amount"]
    db.save()
    await call.answer("Tasdiqlandi")
    try:
        await call.message.edit_text(f"✅ To'lov <code>{tid}</code> tasdiqlandi — {fmt(t['amount'])} UZS qo'shildi.")
    except Exception:  # noqa: BLE001
        pass


@common_router.callback_query(F.data.startswith("adm_topup_no:"))
async def adm_topup_no(call: CallbackQuery) -> None:
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("Ruxsat yo'q", show_alert=True)
        return
    tid = call.data.split(":", 1)[1]
    t = db.data["topups"].get(tid)
    if not t or t["status"] != "pending":
        await call.answer("Bu so'rov allaqachon ko'rilgan", show_alert=True)
        return
    t["status"] = "cancelled"
    db.save()
    try:
        await bot.send_message(t["user_id"], f"❌ To'lov so'rovi ({fmt(t['amount'])} UZS) bekor qilindi.")
    except Exception:  # noqa: BLE001
        pass
    await call.answer("Rad etildi")
    try:
        await call.message.edit_text(f"❌ To'lov <code>{tid}</code> rad etildi.")
    except Exception:  # noqa: BLE001
        pass


# --------------------------- Profil / Referal / Tarix ------------------------
@router.message(F.text == BTN_PROFILE)
async def show_profile(message: Message, state: FSMContext, db_user: dict):
    await state.clear()
    await message.answer(
        f"👤 <b>Profil</b>\n\n"
        f"🆔 ID: <code>{db_user['id']}</code>\n"
        f"👤 Username: @{esc(db_user.get('username') or '—')}\n"
        f"💰 Balans: <b>{fmt(db_user.get('balance', 0))} UZS</b>\n"
        f"💳 Jami to'ldirilgan: {fmt(db_user.get('total_topup', 0))} UZS\n"
        f"🛒 Jami sarflangan: {fmt(db_user.get('total_spent', 0))} UZS\n"
        f"👥 Referallar: {db_user.get('referrals_count', 0)} "
        f"(⭐ {fmt(db_user.get('ref_stars', 0))} stars)\n"
        f"📅 Qo'shilgan: {esc((db_user.get('joined_at') or '')[:10])}",
        reply_markup=webapp_inline_kb(db_user),
    )


async def referral_text(b: Bot, user: dict) -> str:
    return (
        f"👥 <b>Referral dasturi</b>\n\n"
        f"🔗 Link: {await ref_link(b, user)}\n"
        f"👥 Takliflaringiz: {fmt(user.get('referrals_count', 0))} ta\n\n"
        f"• Har bir taklif qilgan do'stingiz uchun hisobingizga {REF_BONUS_STARS} ta stars qo'shiladi.\n"
        f"• Balansingiz kamida {REF_MIN_WITHDRAW} taga yetgach, haqiqiy stars ko'rinishida chiqarib olishingiz mumkin.\n\n"
        f"💳 Mavjud balans: {fmt(user.get('ref_stars', 0))} stars"
    )


@router.message(F.text == BTN_REF)
async def show_referral(message: Message, state: FSMContext, bot: Bot, db_user: dict):
    await state.clear()
    await message.answer(await referral_text(bot, db_user), disable_web_page_preview=True)


@router.message(F.text == BTN_SUPPORT)
async def show_support(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        f"🆘 <b>Qo'llab-quvvatlash</b>\n\nSavol va muammolar bo'yicha murojaat qiling: @{SUPPORT_USERNAME}",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="✍️ Yozish", url=f"https://t.me/{SUPPORT_USERNAME}", style="danger")]]
        ),
    )


@router.message(F.text == BTN_HISTORY)
async def show_history(message: Message, state: FSMContext, db_user: dict):
    await state.clear()
    history = (db_user.get("history") or [])[-15:]
    if not history:
        await message.answer("📜 Tarix bo'sh.")
        return
    lines = ["📜 <b>Oxirgi amallar</b>\n"]
    for h in reversed(history):
        sign = "+" if h["amount"] > 0 else ""
        unit = "⭐" if h.get("unit") == "stars" else "UZS"
        lines.append(
            f"<b>{sign}{fmt(h['amount'])} {unit}</b>: {esc(h.get('details', ''))} — {esc(h['date'][:16].replace('T', ' '))}"
        )
    await message.answer("\n".join(lines))


# =============================================================================
# 13. STARS SOTIB OLISH (Fragment USDT orqali)
# =============================================================================
@router.callback_query(F.data == "bonus_claim")
async def bonus_claim(call: CallbackQuery):
    """Kanal xabaridagi bonus tugmasi — mijozni botga olib boradi."""
    await call.answer("🎁 Bonusni olish uchun botga yozing: /start", show_alert=True)


@router.message(F.text == BTN_BUY)
async def buy_start(message: Message, state: FSMContext, db_user: dict):
    await state.clear()
    await state.set_state(BuyStates.username)
    rows = []
    if db_user.get("username"):
        rows.append([InlineKeyboardButton(text=f"🙋 O'zimga (@{db_user['username']})", callback_data="buy_self", style="success")])
    rows.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel", style="danger")])
    await message.answer(
        "⭐ <b>Stars sotib olish</b>\n\nStars kimga yuborilsin? Telegram <b>@username</b> ni yuboring:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


async def _ask_amount(message: Message, state: FSMContext, username: str) -> None:
    await state.update_data(username=username)
    await state.set_state(BuyStates.amount)
    await message.answer(
        f"👤 Qabul qiluvchi: <b>@{esc(username)}</b>\n\n"
        f"Nechta ⭐ kerak? ({fmt(MIN_STARS_BUY)} – {fmt(MAX_STARS_BUY)})\n"
        f"1 ⭐ = {STAR_BUY_PRICE_UZS} UZS (Fragment USDT on TON)",
        reply_markup=cancel_inline_kb(),
    )


@router.callback_query(F.data == "buy_self", StateFilter(BuyStates.username))
async def buy_self(call: CallbackQuery, state: FSMContext, db_user: dict):
    await call.answer()
    username = normalize_username(db_user.get("username") or "")
    if not username:
        await call.message.answer("⚠️ Sizda username yo'q. Iltimos, username kiriting.")
        return
    await _ask_amount(call.message, state, username)


@router.message(StateFilter(BuyStates.username), F.text, NOT_MENU)
async def buy_username(message: Message, state: FSMContext):
    username = normalize_username(message.text)
    if not username:
        await message.answer("⚠️ Noto'g'ri username. Masalan: <code>@durov</code>")
        return
    await _ask_amount(message, state, username)


async def ask_buy_confirmation(message: Message, username: str, amount: int, db_user: dict) -> None:
    price = amount * STAR_BUY_PRICE_UZS
    balance = int(db_user.get("balance", 0))
    enough = balance >= price
    kb_rows = []
    if enough:
        kb_rows.append([InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="buy_confirm", style="success")])
    kb_rows.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel", style="danger")])
    await message.answer(
        f"🧾 <b>Buyurtma</b>\n\n"
        f"👤 Qabul qiluvchi: <b>@{esc(username)}</b>\n"
        f"⭐ Miqdor: <b>{fmt(amount)} Stars</b>\n"
        f"💵 Narx: <b>{fmt(price)} UZS</b>\n"
        f"💰 Balansingiz: <b>{fmt(balance)} UZS</b>\n\n"
        + ("Tasdiqlaysizmi?" if enough else f"❌ Balans yetarli emas. {BTN_TOPUP} bo'limidan to'ldiring."),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows),
    )


@router.message(StateFilter(BuyStates.amount), F.text, NOT_MENU)
async def buy_amount(message: Message, state: FSMContext, db_user: dict):
    text = (message.text or "").replace(" ", "")
    if not text.isdigit() or not (MIN_STARS_BUY <= int(text) <= MAX_STARS_BUY):
        await message.answer(f"⚠️ {fmt(MIN_STARS_BUY)} dan {fmt(MAX_STARS_BUY)} gacha son kiriting.")
        return
    amount = int(text)
    data = await state.get_data()
    await state.update_data(amount=amount)
    await state.set_state(BuyStates.confirm)
    await ask_buy_confirmation(message, data["username"], amount, db_user)


@router.callback_query(F.data == "buy_confirm", StateFilter(BuyStates.confirm))
async def buy_confirm(call: CallbackQuery, state: FSMContext, db_user: dict):
    data = await state.get_data()
    await state.clear()
    username, amount = data.get("username"), int(data.get("amount") or 0)
    if not username or amount < MIN_STARS_BUY:
        await call.answer("Buyurtma ma'lumotlari topilmadi", show_alert=True)
        return
    try:
        order = place_star_order(db_user, username, amount, call.message.chat.id)
    except ValueError:
        await call.answer("❌ Balans yetarli emas!", show_alert=True)
        return

    await call.answer()
    try:
        await call.message.edit_text(
            f"⏳ <b>Buyurtmangiz qabul qilindi!</b>\n\n"
            f"⭐ {fmt(amount)} Stars → @{esc(username)}\n"
            f"💳 Yechilgan: <b>{fmt(amount * STAR_BUY_PRICE_UZS)} so'm</b>\n"
            f"🆔 <code>{order['id']}</code>\n\n"
            f"📦 Stars <b>avtomatik tarzda yuborilmoqda</b> — 1–5 daqiqa ichida "
            f"hisobingizga tushadi.\n"
            f"⏳ Sabr qiling, xabarni kuting."
        )
    except Exception:  # noqa: BLE001
        pass


def place_star_order(user: dict, username: str, amount: int, chat_id: int) -> dict:
    price = amount * STAR_BUY_PRICE_UZS
    db.change_balance(user["id"], -price, "buy_stars", f"{amount} ⭐ -> @{username}")
    order_id = new_id("o")
    order = {
        "id": order_id,
        "user_id": user["id"],
        "recipient": username,
        "stars": amount,
        "price_uzs": price,
        "status": "processing",
        "created_at": now_iso(),
    }
    db.data["orders"][order_id] = order
    user["total_spent"] = int(user.get("total_spent", 0)) + price
    db.save()
    asyncio.create_task(process_star_order(order_id, chat_id))
    return order


async def process_star_order(order_id: str, chat_id: int) -> None:
    order = db.data["orders"].get(order_id)
    if order is None:
        log.warning("Buyurtma %s bazada topilmadi", order_id)
        return

    # WebApp buyurtmalari boshqa maydonga yozadi — moslashtiramiz
    if not order.get("stars") and order.get("amount"):
        order["stars"] = int(order["amount"])
    if not order.get("price_uzs") and order.get("price"):
        order["price_uzs"] = int(order["price"])

    user_id = int(order["user_id"])
    username = order["recipient"]
    amount = int(order.get("stars") or 0)
    price = int(order.get("price_uzs") or order.get("price") or 0)
    if amount <= 0:
        order.update(status="failed", error="Stars miqdori noto'g'ri")
        db.save()
        return

    try:
        result = await buy_stars_via_fragment(username, amount)
    except PurchaseError as exc:
        log.warning("Buyurtma %s muvaffaqiyatsiz: %s", order_id, exc)
        order.update(status="manual_pending", error=str(exc), chat_id=chat_id, finished_at=now_iso())
        db.save()

        # Xatani to'g'ri kategoriyaga ajratamiz:
        #  • tarmoq/sessiya/cookie/holat  -> TEXNIK (admin hal qiladi)
        #  • "yetarli emas" / "Hamyonda"  -> TONGA ZARUR xato
        err_text = str(exc)
        low = err_text.lower()
        technical = any(
            k in low
            for k in (
                "access denied", "cookie", "xarid holati", "api_hash",
                "json qaytarmadi", "tarmo", "liteserver", "lite server",
                "shard", "seqno", "block", "ulana", "sozlan", "purov",
                "fragment xatosi", "req_id", "to'lov usuli",
            )
        )
        # Taxminiy USDT sarfi (haqiqiy kursdan — 50 Stars ≈ 0.75 USDT)
        usdt_needed = (Decimal(amount) * STAR_USDT_RATE).quantize(Decimal("0.01"))

        if technical:
            headline = "🔴 <b>Texnik xato — buyurtma bajarilmadi</b>"
            advice = ("👉 <i>Avtomatik ravishda qayta urinish mumkin. Agar takrorlansa, "
                      "/admin → 🩺 Fragment diagnostika ni bosib ko'ring.</i>")
        else:
            headline = "⚠️ <b>TON hamyonda USDT yetarli emas</b>"
            advice = "👉 <i>Iltimos, TON hamyonga USDT tashlang (Telegram → USDT → TON).</i>"

        await notify_admins(
            f"{headline}\n\n"
            f"📦 <b>Buyurtma ID:</b> <code>#{order_id}</code>\n"
            f"👤 <b>Mijoz ID:</b> <code>{user_id}</code> (@{esc(username)})\n"
            f"⭐ <b>Stars miqdori:</b> {amount} ⭐\n"
            f"💎 <b>Kerakli USDT:</b> ~{usdt_needed} USDT (on TON)\n"
            f"💳 <b>Yechilgan so'm:</b> {fmt(price)} UZS\n"
            f"🔍 <b>Sabab:</b> <code>{esc(err_text)}</code>\n\n"
            f"{advice}"
        )
        await _safe_send(
            chat_id,
            f"⏳ <b>Buyurtmangiz qabul qilindi!</b>\n\n"
            f"⭐ Miqdor: <b>{amount} ta Stars</b>\n"
            f"👤 Qabul qiluvchi: <b>@{esc(username)}</b>\n"
            f"💳 Yechilgan summa: <b>{fmt(price)} UZS</b>\n"
            f"📌 Holat: <b>Yuborilmoqda</b>\n\n"
            + (
                "<i>Do'kon tomonida vaqtincha muammo bor. Administrator tuzatadi va "
                "Stars'ni avtomatik yuboradi.</i>"
                if technical
                else "<i>Stars avtomatik tarzda yuboriladi. Biroz kutib turing.</i>"
            ),
        )
        return
    except Exception as exc:  # noqa: BLE001
        log.exception("Buyurtma %s: kutilmagan xato", order_id)
        order.update(status="unknown", error=str(exc), finished_at=now_iso())
        db.save()
        await _safe_send(
            chat_id,
            f"⚠️ Buyurtma <code>{order_id}</code> holati aniqlanmadi. Admin tekshirib, siz bilan bog'lanadi.",
        )
        return

    order.update(
        status="done" if result.confirmed else "sent_unconfirmed",
        finished_at=now_iso(),
        payment_method="usdt_ton",
        usdt_spent=round(result.usdt_amount / 10 ** USDT_DECIMALS, 3) if result.usdt_amount else None,
    )
    if result.usdt_amount:
        _decrease_wallet_usdt(result.usdt_amount)
    db.save()

    usdt_spent = order.get("usdt_spent")
    await _safe_send(
        chat_id,
        f"✅ <b>Stars yuborildi!</b>\n\n"
        f"⭐ {fmt(amount)} Stars @{esc(username)} ga yetkazildi.\n"
        f"💳 Yechilgan summa: <b>{fmt(price)} UZS</b>\n"
        f"🆔 Buyurtma: <code>{order_id}</code>",
    )

    # Kanalga xabar (har bir xariddan keyin)
    buyer = db.get_user(user_id)
    cashback = int(round(price * CASHBACK_RATE))
    await post_order_to_channel(
        order,
        title="Stars olindi",
        username=(buyer or {}).get("username") or str(user_id),
        amount_text=f"Miqdor: {fmt(amount)} ⭐",
        price=price,
        cashback=cashback,
    )


def _decrease_wallet_usdt(micro: int) -> None:
    settings = db.data.setdefault("settings", {})
    try:
        current = Decimal(str(settings.get("wallet_usdt_balance", 0) or 0))
    except InvalidOperation:
        current = Decimal(0)
    settings["wallet_usdt_balance"] = max(
        Decimal(0), current - (Decimal(micro) / (10 ** USDT_DECIMALS))
    ).quantize(Decimal("0.001"))


async def refresh_wallet_usdt() -> None:
    """TON hamyondagi haqiqiy USDT balansini olib, settings'ga yozadi (admin panel uchun).

    MUHIM: USDT oddiy TON hamyon manzilida emas, alohida JETTON (keltron)
    manzilida saqlanadi. Bu manzil `USDT_MASTER.get_wallet_address(hamyon)`
    orqali hisoblanadi — ya'ni sizga tegishli, lekin boshqa manzil.
    """
    if WALLET_SEED_ERROR:
        return
    provider = None
    try:
        provider, wallet = await connect_wallet(retries=2)
        jetton_wallet = await usdt_wallet_address(provider, wallet.address)
        balance = await usdt_balance(provider, jetton_wallet)
        try:
            ton_balance = await wallet.get_balance()
        except Exception:  # noqa: BLE001
            ton_balance = 0

        settings = db.data.setdefault("settings", {})
        settings["wallet_address"] = wallet.address.to_str(is_user_friendly=True)
        settings["wallet_usdt_address"] = jetton_wallet.to_str(is_user_friendly=True)
        settings["wallet_usdt_balance"] = round(balance / 10 ** USDT_DECIMALS, 3)
        settings["wallet_ton_balance"] = round(ton_balance / 10 ** 9, 4)
        settings["wallet_usdt_updated_at"] = now_iso()
        db.save()
        log.info(
            "👛 USDT balansi: %s USDT (jetton %s) | TON: %s",
            settings["wallet_usdt_balance"], settings["wallet_usdt_address"],
            settings["wallet_ton_balance"],
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("USDT balansini yangilab bo'lmadi: %s", exc)
    finally:
        if provider is not None:
            try:
                await provider.close_all()
            except Exception:  # noqa: BLE001
                pass


async def star_order_worker() -> None:
    """WebApp'dan kelgan Stars buyurtmalarini USDT (TON) orqali Fragment'da xarid qiladi.

    Bot ichidagi buyurtmalar darhol `process_star_order` chaqiradi, WebApp buyurtmalari esa
    baza orqali (status=processing) shu worker tomonidan olinadi. Shu tariqa IKKALA yo'l
    ham yagona — haqiqiy Fragment USDT kodi orqali ishlaydi.
    """
    log.info("⭐ Stars worker (USDT on TON) ishga tushdi — WebApp buyurtmalari kutilmoqda")
    await asyncio.sleep(4)
    cycle = 0
    while True:
        try:
            await asyncio.sleep(4)
            db.reload_if_changed()
            cycle += 1

            for order_id, order in list(db.data["orders"].items()):
                if order.get("kind") != "stars":
                    continue
                if order.get("auto_processed"):
                    continue
                if order.get("status") not in ("processing", "queued", "pending"):
                    continue
                if order.get("payment_method") not in (None, "", "usdt", "usdt_ton"):
                    continue

                order["auto_processed"] = True
                order["payment_method"] = "usdt_ton"
                db.save()
                target = int(order.get("chat_id") or order["user_id"])
                log.info("⭐ WebApp buyurtmasi %s qayta ishlanmoqda (%s ⭐)", order_id, order.get("amount"))
                asyncio.create_task(process_star_order(order_id, target))

            # Har 5 daqiqada USDT balansini yangilab turamiz
            if cycle % 75 == 0:
                asyncio.create_task(refresh_wallet_usdt())
                asyncio.create_task(get_usdt_uzs_rate(force=True))
        except Exception as exc:  # noqa: BLE001
            log.exception("Stars worker xatosi: %s", exc)
            await asyncio.sleep(5)


async def post_order_to_channel(order: dict, title: str, username: str,
                                 amount_text: str, price: int, cashback: int = 0) -> None:
    """Har bir xariddan keyin ORDERS_CHANNEL kanaliga xabar yuboradi.

    Format (rasmdagidek):
        ⭐ Stars olindi
        👤 odilbek
        📦 Miqdor: 50 ⭐
          Summasi: 10 000 so'm
          Keshbek: +10 so'm
        [🎁 Bonus: 10 so'm (🌸)]  [📊 NeonShop]
    """
    if not ORDERS_CHANNEL or bot is None:
        return

    who = f"@{username}" if username else f"ID {order.get('user_id')}"
    lines = [
        f"⭐ <b>{esc(title)}</b>",
        f"👤 <b>{esc(who)}</b>",
        "",
        f"📦 <b>{esc(amount_text)}</b>",
        f"💵 Summasi: <b>{fmt(price)} so'm</b>",
    ]
    if cashback:
        lines.append(f"🎁 Keshbek: <b>+{fmt(cashback)} so'm</b>")

    markup: Optional[InlineKeyboardMarkup] = None
    if cashback:
        markup = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text=f"🎁 Bonus: {fmt(cashback)} so'm (🌸)",
                callback_data="bonus_claim",
            )
        ]])
    buttons: list[list[Any]] = [list(markup.inline_keyboard[0])] if markup else []
    buttons.append([InlineKeyboardButton(text="📊 NeonShop", url=WEBAPP_URL)])
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)  # type: ignore[arg-type]

    try:
        await bot.send_message(ORDERS_CHANNEL, "\n".join(lines),
                               reply_markup=markup, disable_web_page_preview=True)
    except Exception as exc:  # noqa: BLE001
        log.warning("Kanalga xabar yuborilmadi: %s", exc)


async def _safe_send(chat_id: int, text: str, **kwargs: Any) -> None:
    if bot is None:
        return
    try:
        await bot.send_message(chat_id, text, **kwargs)
    except Exception as exc:  # noqa: BLE001
        log.info("Xabar yuborilmadi (%s): %s", chat_id, exc)


# =============================================================================
# 14. STARS SOTISH (foydalanuvchi -> bot)
# =============================================================================
@router.message(F.text == BTN_SELL)
async def sell_start(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(SellStates.amount)
    await message.answer(
        f"💰 <b>Stars sotish</b>\n\n1 ⭐ = <b>{STAR_SELL_PRICE_UZS} UZS</b>\n"
        f"Nechta ⭐ sotmoqchisiz? ({fmt(MIN_STARS_SELL)} – {fmt(MAX_STARS_SELL)})",
        reply_markup=cancel_inline_kb(),
    )


@router.message(StateFilter(SellStates.amount), F.text, NOT_MENU)
async def sell_amount(message: Message, state: FSMContext, bot: Bot):
    text = (message.text or "").replace(" ", "")
    if not text.isdigit() or not (MIN_STARS_SELL <= int(text) <= MAX_STARS_SELL):
        await message.answer(f"⚠️ {fmt(MIN_STARS_SELL)} dan {fmt(MAX_STARS_SELL)} gacha son kiriting.")
        return
    amt = int(text)
    await state.clear()
    try:
        await bot.send_invoice(
            chat_id=message.chat.id,
            title=f"{fmt(amt)} Telegram Stars sotish",
            description=f"{fmt(amt)} ⭐ evaziga {fmt(amt * STAR_SELL_PRICE_UZS)} UZS kartangizga o'tkaziladi.",
            payload=f"sell:{message.from_user.id}:{amt}:{uuid.uuid4().hex[:8]}",
            currency="XTR",
            prices=[LabeledPrice(label="Stars", amount=amt)],
            provider_token="",
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("Invoice yuborilmadi")
        await message.answer(f"⚠️ Hisob-faktura yaratilmadi: {esc(exc)}")


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    ok = query.invoice_payload.startswith("sell:") and query.currency == "XTR"
    await query.answer(ok=ok)


@router.message(F.successful_payment)
async def on_successful_payment(message: Message, db_user: dict):
    sp = message.successful_payment
    if sp.currency != "XTR" or not sp.invoice_payload.startswith("sell:"):
        return
    amt = int(sp.total_amount)
    uzs = amt * STAR_SELL_PRICE_UZS
    sale_id = new_id("s")
    sale = {
        "id": sale_id,
        "user_id": db_user["id"],
        "stars": amt,
        "uzs": uzs,
        "charge_id": sp.telegram_payment_charge_id,
        "card": None,
        "status": "awaiting_card",
        "created_at": now_iso(),
    }
    db.data["sales"][sale_id] = sale
    db_user["pending_sale_card"] = sale_id
    db.save()

    await message.answer(
        f"✅ <b>{fmt(amt)} ⭐ qabul qilindi!</b>\n\n"
        f"💵 Sizga to'lanadi: <b>{fmt(uzs)} UZS</b>\n\n"
        f"💳 Iltimos, pul o'tkaziladigan <b>karta raqamingizni</b> (16 raqam) yuboring:"
    )


def build_captcha(user: dict) -> InlineKeyboardMarkup:
    a = random.randint(1, 9)
    b = random.randint(1, 9)
    answer = a * b
    user["captcha_answer"] = answer
    options = {answer, answer + random.choice([1, 2, 3, 4, 5]), max(0, answer - random.choice([1, 2, 3])), answer + random.choice([6, 7, 8])}
    opts = list(options)
    random.shuffle(opts)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=str(o), callback_data=f"captcha:{o}", style="primary") for o in opts[:2]],
        [InlineKeyboardButton(text=str(o), callback_data=f"captcha:{o}", style="primary") for o in opts[2:]],
    ])
    return kb, a, b, answer


async def send_captcha(message: Message, db_user: dict) -> None:
    kb, a, b, ans = build_captcha(db_user)
    db.save()
    await message.answer(
        f"🔒 <b>Robot emasligi tekshiruvi</b>\n\nQuyidagi misolning javobini toping:\n\n🔢 <b>{a} × {b} = ?</b>",
        reply_markup=kb,
    )


# =============================================================================
# 15. BALANS TO'LDIRISH
# =============================================================================
HUMO_AMOUNT_RX = re.compile(r"➕\s*([\d\s.,]+)\s*UZS")
HUMO_CARD_RX = re.compile(r"HUMOCARD\s*\*(\d+)")


def parse_humo_payment(text: str) -> Optional[tuple[int, Optional[str]]]:
    """@humocardbot xabaridan summa va karta oxirgi raqamlarini ajratadi."""
    m = HUMO_AMOUNT_RX.search(text or "")
    if not m:
        return None
    raw = m.group(1).replace(" ", "").replace(".", "").replace(",", ".")
    try:
        amount = int(Decimal(raw))
    except (InvalidOperation, ValueError):
        return None
    cm = HUMO_CARD_RX.search(text or "")
    card = cm.group(1) if cm else None
    return amount, card


async def notify_admins(text: str) -> None:
    if bot is None:
        return
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
        except Exception:  # noqa: BLE001
            pass


async def on_humo_message(client: UserbotClient, message) -> None:
    try:
        text = message.text or ""
        if "➕" not in text:
            return
        parsed = parse_humo_payment(text)
        if parsed is None:
            await notify_admins(
                f"⚠️ @humocardbot xabari noto'g'ri formatda keldi, avtomatik tanib bo'lmadi:\n\n{text}"
            )
            return
        amount, card = parsed
        msg_id = f"{message.chat.id}_{message.id}"
        if msg_id in db.data["processed_bank_msgs"]:
            return
        db.data["processed_bank_msgs"].append(msg_id)
        now = time.time()
        # WebApp'dan yaratilgan to'lovlar ham ko'rinishi uchun bazani yangilaymiz
        db.reload_if_changed()

        # Muddati o'tgan so'rovlarni tozalaymiz
        for t in db.data["topups"].values():
            if t.get("status") == "pending" and float(t.get("expires_at", 0)) < now:
                t["status"] = "expired"

        # Faol so'rovlar: mijoz aynan shu summani to'lashini kutamiz
        pending = [
            t for t in db.data["topups"].values()
            if t.get("status") == "pending" and float(t.get("expires_at", 0)) > now
        ]

        # Karta tekshiruvi: o'z kartamizdan tushgan to'lovni tasdiqlaymiz
        our_digits = "".join(ch for ch in str(CARD_NUMBER) if ch.isdigit())
        card_ok = True
        if card and our_digits:
            card_ok = card in our_digits or our_digits.endswith(card)

        matches = [
            t for t in pending
            if int(t.get("amount", 0)) == amount
            and (card_ok or not card)
        ]

        if matches:
            # Eng eski so'rovni birinchi yopamiz
            t = min(matches, key=lambda x: x.get("created_at", ""))
            t["status"] = "completed"
            t["completed_at"] = now_iso()
            t["auto_verified"] = True
            t["payment_method"] = "humocard"
            u = db.data["users"].get(str(t["user_id"]))
            if u:
                u["balance"] = int(u.get("balance", 0)) + t["amount"]
                u["total_topup"] = int(u.get("total_topup", 0)) + t["amount"]
                db.add_history(u, "topup", int(t["amount"]), f"Auto: HUMOCARD *{card or '????'}")
                try:
                    await bot.send_message(
                        u["id"],
                        f"✅ <b>{fmt(t['amount'])} UZS</b> balansingizga qo'shildi!\n\n"
                        f"💳 To'lov avtomatik aniqlanildi.\n"
                        f"💰 Balans: <b>{fmt(u['balance'])} so'm</b>",
                    )
                except Exception:  # noqa: BLE001
                    pass
            db.data["settings"]["total_volume_uzs"] = int(db.data["settings"].get("total_volume_uzs", 0)) + t["amount"]
            db.save()
            await notify_admins(
                f"💰 <b>To'lov avtomatik tasdiqlandi!</b>\n\n"
                f"👤 User: <code>{t['user_id']}</code>\n"
                f"💵 Summa: <b>{fmt(t['amount'])} UZS</b>\n"
                f"💳 Karta: <code>*{card or '????'}</code>\n"
                f"🆔 Topup: <code>{t['id']}</code>"
            )
        elif card and not card_ok:
            # Boshqa kartadan kelgan — tasdiqlamaymiz
            db.save()
            await notify_admins(
                f"🚫 <b>Boshqa kartadan to'lov keldi — tasdiqlanmadi</b>\n\n"
                f"💵 Summa: <b>{fmt(amount)} UZS</b>\n"
                f"💳 Karta: <code>*{card}</code> (bizniki: <code>*{our_digits[-4:]}</code>)\n"
                f"🔍 Ko'rib chiqing — kerak bo'lsa qo'lda tasdiqlang."
            )
        else:
            waiting = ", ".join(
                f"<code>{t['id']}</code> ({fmt(t['amount'])} UZS)" for t in pending[:5]
            )
            db.save()
            await notify_admins(
                f"🔀 <b>To'lov avtomatik bog'lanmadi</b>\n\n"
                f"💵 Kelgan summa: <b>{fmt(amount)} UZS</b>\n"
                f"💳 Karta: <code>*{card or '????'}</code>\n"
                f"📋 Kutayotgan so'rovlar: {waiting or 'yo‘q'}\n\n"
                f"<i>Mijoz boshqa summa to'lagan bo'lishi mumkin. Zarur bo'lsa qo'lda "
                f"tasdiqlang: /api/admin/adjust-balance</i>"
            )
    except Exception as exc:  # noqa: BLE001
        log.exception("Humo xabarini qayta ishlashda xato")
        await notify_admins(f"❌ Avto-to'lov tekshiruvi xatosi: {exc}")


async def process_gift_orders() -> None:
    """Gift buyurtmalarini userbot orqali avto-yuboradi.

    Ikkala manbadan oladi:
      • bot ichidagi buyurtmalar (kind=gift)
      • WebApp'dan kelgan buyurtmalar (bazaga yozilgan, source=webapp)
    Xato bo'lsa 3 marta qayta urinadi, keyin adminga yuboriladi.
    """
    log.info("🎁 Gift avto-yetkazuv xizmati ishga tushdi...")
    while True:
        try:
            await asyncio.sleep(15)
            if userbot is None:
                continue
            db.reload_if_changed()
            for order in list(db.data.get("orders", {}).values()):
                if order.get("kind") != "gift":
                    continue
                if order.get("gift_sent") or order.get("gift_processing"):
                    continue
                if order.get("status") not in ("completed", "pending_admin", "processing"):
                    continue
                gift_key = order.get("gift") or order.get("gift_key") or ""
                gift_def = next((g for g in GIFTS if g[0] == gift_key), None)
                # `gift` maydoni yo'q bo'lsa (eski/webapp yozuvlari) — Stars bo'yicha
                # aniqlaymiz, aks holda hech narsa topilmaydi va gift yuborilmaydi
                stars = gift_def[2] if gift_def else (order.get("stars") or order.get("amount"))
                recipient = (order.get("recipient") or "").lstrip("@")
                if not recipient or not stars:
                    continue

                order["gift_processing"] = True
                db.save()
                try:
                    gifts = await userbot.get_available_gifts()
                    match = next((g for g in gifts if stars and g.price == stars), None)
                    if match is None:
                        log.warning("Gift (%s) uchun mos sovg'a topilmadi", gift_key)
                        order["gift_sent"] = True
                        order["gift_processing"] = False
                        order["gift_error"] = "Mos sovg'a topilmadi"
                        db.save()
                        await notify_admins(
                            f"⚠️ Gift <code>#{order['id']}</code> ({gift_key}) uchun mos sovg'a topilmadi. "
                            f"Sovg'aning narxi o'zgargan bo'lishi mumkin."
                        )
                        continue

                    sent = False
                    last_err: Optional[Exception] = None
                    for attempt in range(3):
                        try:
                            await userbot.send_gift(chat_id=recipient, gift_id=match.id)
                            sent = True
                            break
                        except Exception as exc:  # noqa: BLE001
                            last_err = exc
                            log.warning("Gift yuborishda xato (%d/3): %s", attempt + 1, exc)
                            await asyncio.sleep(3 + attempt * 3)

                    if not sent:
                        raise last_err or RuntimeError("noma'lum xato")

                    order["gift_sent"] = True
                    order["gift_processing"] = False
                    order["gift_sent_at"] = now_iso()
                    db.save()
                    log.info("🎁 Gift %s @%s ga userbot orqali yuborildi", gift_key, recipient)
                    await _safe_send(
                        order["user_id"],
                        f"🎁 <b>Sovg'a yuborildi!</b>\n\n"
                        f"🎉 {esc(str(order.get('title', gift_key)))}\n"
                        f"👤 Qabul qiluvchi: <b>@{esc(recipient)}</b>\n"
                        f"🆔 Buyurtma: <code>{order['id']}</code>",
                    )
                    await notify_admins(
                        f"🎁 Gift <code>#{order['id']}</code> ({gift_key}) @{esc(recipient)} ga yuborildi."
                    )
                except Exception as exc:  # noqa: BLE001
                    order["gift_processing"] = False
                    order["gift_error"] = str(exc)
                    db.save()
                    log.error("Gift yuborishda xato: %s", exc)
                    await notify_admins(f"❌ Gift <code>#{order['id']}</code> yuborishda xato: {exc}")
        except Exception as exc:  # noqa: BLE001
            log.error("process_gift_orders xato: %s", exc)
            await asyncio.sleep(5)


def userbot_diagnose() -> list[str]:
    """Userbot ishlashiga nima to'sqinlik qilayotganini aniq ko'rsatadi."""
    lines = ["🩺 <b>Userbot diagnostikasi</b>\n"]
    lines.append(f"{'✅' if API_ID else '❌'} API_ID: {'to\'ldirilgan' if API_ID else 'YO‘Q'}")
    lines.append(f"{'✅' if API_HASH else '❌'} API_HASH: {'to\'ldirilgan' if API_HASH else 'YO‘Q'}")
    has_session = bool(SESSION_STRING and len(SESSION_STRING) > 20)
    lines.append(
        f"{'✅' if has_session else '❌'} SESSION_STRING: "
        f"{'to‘ldirilgan (' + str(len(SESSION_STRING)) + ' belgi)' if has_session else 'YO‘Q'}"
    )
    lines.append(
        f"{'✅' if userbot is not None else '❌'} Userbot obyekti: "
        f"{'ishlayapti' if userbot is not None else 'yo‘q (avto-start muvaffaqiyatsiz)'}"
    )
    lines.append(f"ℹ️ Bank kuzatuv manzasi: <code>{esc(str(TOPUP_SOURCE_CHAT))}</code>")

    if not (API_ID and API_HASH and has_session):
        lines.append("")
        if not (API_ID and API_HASH):
            lines.append("👉 my.telegram.org → API development tools → ID va API hash olish")
        if not has_session:
            lines.append("👉 Bu yerdan: <b>/admin → 📱 Raqam bilan ulash</b> — kodni kiriting, "
                         "u sizga <code>SESSION_STRING</code> beradi.")
            lines.append("👉 Uni Railway ENV ga qo'ying va redeploy qiling.")
    else:
        lines.append("")
        lines.append("👉 Kalitlar to'g'ri, lekin ulanish muvaffaqiyatsiz. "
                     "Railway loglarida <code>Userbot ishga tushmadi</code> qatorini qarang.")
    return lines


def set_runtime_status(**kwargs: Any) -> None:
    """Botning ish vaqtidagi holatini bazaga yozadi.

    server.ts /api/health shu ma'lumotni o'qib, Railway loglariga
    kirishsiz userbot va worker holatini ko'rsatadi.
    """
    settings = db.data.setdefault("settings", {})
    settings["runtime"] = {**datetime.now(TZ).isoformat(), **kwargs}
    db.save()


def maybe_start_userbot() -> None:
    global userbot
    missing = []
    if not SESSION_STRING:
        missing.append("SESSION_STRING")
    if not API_ID:
        missing.append("API_ID")
    if not API_HASH:
        missing.append("API_HASH")
    if missing:
        log.warning(
            "Userbot uchun %s yo'q — avto to'ldirish va gift yuborish ishlamaydi. "
            "/admin → 📱 Raqam bilan ulash orqali SESSION_STRING oling.",
            ", ".join(missing),
        )
        set_runtime_status(userbot="missing_env", missing=missing)
        return

    async def _start() -> None:
        set_runtime_status(userbot="starting")
        try:
            ub = UserbotClient(
                "humo_userbot",
                api_id=API_ID,
                api_hash=API_HASH,
                session_string=SESSION_STRING,
            )
            await ub.start()
            ub.add_handler(
                UbMessageHandler(on_humo_message, ub_filters.chat(TOPUP_SOURCE_CHAT))
            )
            userbot = ub
            try:
                me = await ub.get_me()
                who = f"@{me.username}" if me.username else str(me.id)
            except Exception:  # noqa: BLE001
                who = "noma'lum"
            log.info("👤 Userbot ishga tushdi (%s), bank xabarlari kuzatilmoqda...", who)
            set_runtime_status(userbot="connected", account=who, chat=str(TOPUP_SOURCE_CHAT))
            asyncio.create_task(ub_idle())
        except Exception as exc:  # noqa: BLE001
            log.error("Userbot ishga tushmadi: %s", exc)
            set_runtime_status(userbot="error", error=str(exc)[:300])
            await notify_admins(
                "⚠️ <b>Userbot ishga tushmadi</b>\n\n"
                f"🔍 Sabab: <code>{esc(str(exc)[:200])}</code>\n\n"
                "<i>Odatda sabab: SESSION_STRING muddati tuggan. "
                "/admin → 📱 Raqam bilan ulash orqali yangisini oling.</i>"
            )

    asyncio.create_task(_start())


def pending_topups() -> list[dict]:
    return [t for t in db.data["topups"].values() if t["status"] == "pending"]


@router.message(F.text == BTN_TOPUP)
async def topup_start(message: Message, state: FSMContext, db_user: dict):
    await state.clear()
    existing = next((t for t in pending_topups() if t["user_id"] == db_user["id"]), None)
    if existing:
        left = max(0, int(existing["expires_at"] - time.time()))
        await message.answer(
            f"⏳ Sizda faol so'rov bor: <b>{fmt(existing['amount'])} UZS</b>\n"
            f"💳 Karta: <code>{CARD_NUMBER}</code>\nQolgan vaqt: {left // 60}:{left % 60:02d}",
            reply_markup=cancel_inline_kb(f"topup_cancel:{existing['id']}"),
        )
        return
    await state.set_state(TopupStates.amount)
    await message.answer(
        f"💳 <b>Balans to'ldirish</b>\n\nQancha to'ldirmoqchisiz? (UZS, {fmt(MIN_TOPUP)} – {fmt(MAX_TOPUP)})",
        reply_markup=cancel_inline_kb(),
    )


@router.message(StateFilter(TopupStates.amount), F.text, NOT_MENU)
async def topup_amount(message: Message, state: FSMContext, db_user: dict):
    amount = parse_uzs_amount(message.text)
    if amount is None or not (MIN_TOPUP <= amount <= MAX_TOPUP):
        await message.answer(f"⚠️ {fmt(MIN_TOPUP)} dan {fmt(MAX_TOPUP)} gacha summa kiriting.")
        return
    await state.clear()
    topup_id = new_id("t")
    topup = {
        "id": topup_id,
        "user_id": db_user["id"],
        "amount": amount,
        "status": "pending",
        "created_at": now_iso(),
        "expires_at": time.time() + TOPUP_TIMEOUT_SEC,
    }
    db.data["topups"][topup_id] = topup
    db.save()

    await message.answer(
        f"💳 <b>To'lov ma'lumotlari</b>\n\n"
        f"Karta: <code>{CARD_NUMBER}</code>\n"
        f"Egasi: {esc(CARD_HOLDER)}\n"
        f"Summa: <b>{fmt(amount)} UZS</b>\n\n"
        f"⏱ <b>{TOPUP_TIMEOUT_SEC // 60} daqiqa</b> ichida o'tkazing.",
        reply_markup=cancel_inline_kb(f"topup_cancel:{topup_id}"),
    )


# =============================================================================
# 16. ADMIN PANEL
# =============================================================================
@admin_router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    if is_admin_authed(message.from_user.id):
        await state.clear()
        await message.answer(admin_panel_text(), reply_markup=admin_kb())
        return
    await state.set_state(AdminStates.password)
    await message.answer("🔐 Admin parolini kiriting:")


@admin_router.message(StateFilter(AdminStates.password), F.text, NOT_MENU)
async def admin_password(message: Message, state: FSMContext):
    uid = message.from_user.id
    if hmac.compare_digest(message.text.encode(), ADMIN_PASSWORD.encode()):
        ADMIN_SESSIONS[uid] = time.time()
        await state.clear()
        await message.answer("✅ Xush kelibsiz!\n\n" + admin_panel_text(), reply_markup=admin_kb())
    else:
        await message.answer("❌ Noto'g'ri parol.")


async def _admin_guard(call: CallbackQuery) -> bool:
    if not is_admin_authed(call.from_user.id):
        await call.answer("🔐 Avval /admin orqali kiring.", show_alert=True)
        return False
    return True


@admin_router.callback_query(F.data == "adm:home")
async def adm_home(call: CallbackQuery, state: FSMContext):
    if not await _admin_guard(call):
        return
    await state.clear()
    await call.answer()
    await call.message.edit_text(admin_panel_text(), reply_markup=admin_kb())


@admin_router.callback_query(F.data == "adm:toggle")
async def adm_toggle(call: CallbackQuery):
    if not await _admin_guard(call):
        return
    settings = db.data.setdefault("settings", {})
    settings["bot_active"] = not bot_active()
    db.save()
    await call.answer("🟢 Ishga tushirildi" if settings["bot_active"] else "🔴 To'xtatildi", show_alert=True)
    await call.message.edit_text(admin_panel_text(), reply_markup=admin_kb())


@admin_router.callback_query(F.data == "adm:wallet")
async def adm_wallet(call: CallbackQuery):
    if not await _admin_guard(call):
        return
    await call.answer("🔄 USDT balansi yangilanmoqda...")
    if WALLET_SEED_ERROR:
        await call.message.answer(f"⚠️ {esc(WALLET_SEED_ERROR)}")
        return
    await call.message.answer("🔄 TON tarmog'idan USDT balansi olinmoqda...")
    await refresh_wallet_usdt()
    await call.message.answer(admin_panel_text(), reply_markup=admin_kb())


@admin_router.callback_query(F.data == "adm:diag")
async def adm_diag(call: CallbackQuery):
    if not await _admin_guard(call):
        return
    await call.answer("🔍 Tekshirilmoqda...")
    await call.message.answer("🔍 Fragment diagnostikasi boshlandi, 10-20 soniya kuting...")
    try:
        lines = await fragment.diagnose("normuzb")
    except Exception as exc:  # noqa: BLE001
        lines = [f"❌ Diagnostika xatosi: {exc}"]
    await call.message.answer(
        "<b>🩺 Fragment diagnostikasi</b>\n\n" + "\n".join(esc(x) for x in lines),
        reply_markup=admin_kb(),
    )


@admin_router.callback_query(F.data == "adm:ub_status")
async def adm_ub_status(call: CallbackQuery):
    if not await _admin_guard(call):
        return
    await call.answer()
    status = "✅ Ishlayapti" if userbot is not None else "⚠️ Ishlamayapti"
    lines = userbot_diagnose()
    if userbot is not None:
        lines.insert(2, f"💬 Tuzatilgan xabarlar kuzatilmoqda: <code>{esc(str(TOPUP_SOURCE_CHAT))}</code>")
    await call.message.answer(
        f"🩺 Userbot holati: <b>{status}</b>\n\n" + "\n".join(lines),
        reply_markup=admin_back_kb(),
    )


@admin_router.callback_query(F.data == "adm:logout")
async def adm_logout(call: CallbackQuery, state: FSMContext):
    ADMIN_SESSIONS.pop(call.from_user.id, None)
    await state.clear()
    await call.answer("Chiqdingiz")
    await call.message.edit_text("🚪 Admin paneldan chiqdingiz.")


# ------------------------------------------------------------------ statistika
def db_stats() -> dict:
    users = list(db.data["users"].values())
    orders = list(db.data["orders"].values())
    topups = list(db.data["topups"].values())
    settings = db.data.get("settings", {})
    return {
        "users": len(users),
        "active": sum(1 for u in users if int(u.get("total_spent", 0)) > 0),
        "banned": sum(1 for u in users if u.get("banned")),
        "balance": sum(int(u.get("balance", 0)) for u in users),
        "orders": len(orders),
        "volume": int(settings.get("total_volume_uzs", 0) or 0),
        "topups_done": sum(1 for t in topups if t.get("status") == "completed"),
        "topups_pending": sum(1 for t in topups if t.get("status") == "pending"),
        "pending_orders": sum(1 for o in orders if o.get("status") in
                              ("processing", "manual_pending", "unknown")),
    }


@admin_router.callback_query(F.data == "adm:stats")
async def adm_stats(call: CallbackQuery):
    if not await _admin_guard(call):
        return
    await call.answer()
    db.reload_if_changed()
    s = db_stats()
    wallet = db.data.get("settings", {})
    await call.message.answer(
        "📊 <b>Statistika</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{fmt(s['users'])}</b> (faol {s['active']})\n"
        f"🚫 Banlangan: <b>{s['banned']}</b>\n"
        f"💰 Umumiy balans: <b>{fmt(s['balance'])} so'm</b>\n"
        f"⭐ Buyurtmalar: <b>{fmt(s['orders'])}</b>\n"
        f"💵 Aylanma: <b>{fmt(s['volume'])} so'm</b>\n"
        f"💳 To'ldirishlar: <b>{s['topups_done']}</b> (kutilmoqda {s['topups_pending']})\n"
        f"⏳ Kutilayotgan buyurtma: <b>{s['pending_orders']}</b>\n\n"
        f"💎 USDT: <b>{wallet.get('wallet_usdt_balance', 0)} USDT</b>\n"
        f"🪙 TON: <b>{wallet.get('wallet_ton_balance', 0)} TON</b>",
        reply_markup=admin_back_kb(),
    )


# ------------------------------------------------------------------ broadcast
@admin_router.callback_query(F.data == "adm:bc")
async def adm_broadcast(call: CallbackQuery, state: FSMContext):
    if not await _admin_guard(call):
        return
    await call.answer()
    await state.set_state(AdminStates.broadcast)
    await call.message.answer(
        "📣 <b>Xabar yuborish</b>\n\n"
        "Yubormoqchi bo'lgan xabarni yuboring (rasm, video yoki matn bo'lishi mumkin).\n"
        "🛑 Bekor qilish uchun /cancel yozing.",
        reply_markup=admin_back_kb(),
    )


@admin_router.message(StateFilter(AdminStates.broadcast), F.text)
async def adm_broadcast_wait(message: Message, state: FSMContext):
    if not is_admin_authed(message.from_user.id):
        return
    if message.text.strip().lower() in ("/cancel", "bekor", "cancel"):
        await state.clear()
        await message.answer("🛑 Bekor qilindi.", reply_markup=admin_back_kb())
        return

    users = [int(u["id"]) for u in db.data["users"].values() if not u.get("banned")]
    status = await message.answer(f"📣 Yuborilmoqda... <b>0</b>/{len(users)}")

    sent = failed = 0
    for index, uid in enumerate(users, start=1):
        try:
            await message.bot.send_message(uid, message.html_text or message.text)
            sent += 1
        except TelegramForbiddenError:
            failed += 1
        except Exception:  # noqa: BLE001
            failed += 1
        if index % 25 == 0:
            try:
                await status.edit_text(f"📣 Yuborilmoqda... <b>{index}</b>/{len(users)}")
            except Exception:  # noqa: BLE001
                pass
        await asyncio.sleep(0.05)   # Telegram flood limitdan qat'iy o'tmaslik uchun

    await state.clear()
    try:
        await status.edit_text(
            f"✅ <b>Xabar yuborildi!</b>\n\n"
            f"📤 Yuborildi: <b>{sent}</b>\n"
            f"🚫 Xato: <b>{failed}</b>"
        )
    except Exception:  # noqa: BLE001
        await message.answer(f"✅ Yuborildi: {sent}, xato: {failed}")


# ------------------------------------------------------------------ top 20
@admin_router.callback_query(F.data == "adm:top20")
async def adm_top20(call: CallbackQuery):
    if not await _admin_guard(call):
        return
    await call.answer()
    db.reload_if_changed()
    users = sorted(
        db.data["users"].values(),
        key=lambda u: int(u.get("total_spent", 0) or 0),
        reverse=True,
    )[:20]
    if not users:
        await call.message.answer("📊 Hali ma'lumot yo'q.", reply_markup=admin_back_kb())
        return

    lines = ["🏆 <b>TOP 20 xaridorlar</b>\n"]
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for i, u in enumerate(users, start=1):
        mark = medals.get(i, f"{i}.")
        name = f"@{u.get('username')}" if u.get("username") else str(u.get("id"))
        lines.append(f"{mark} {esc(name)} — <b>{fmt(u.get('total_spent', 0))} so'm</b>")
    lines.append(f"\n💰 Jami: <b>{fmt(sum(int(u.get('total_spent', 0) or 0) for u in users))} so'm</b>")
    await call.message.answer("\n".join(lines), reply_markup=admin_back_kb())


# ------------------------------------------------------------------ balans
def _balance_kb(action: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"adm:bal_do:{action}")],
        [InlineKeyboardButton(text="🛑 Bekor qilish", callback_data="adm:home")],
    ])


@admin_router.callback_query(F.data == "adm:bal_add")
async def adm_bal_add(call: CallbackQuery, state: FSMContext):
    if not await _admin_guard(call):
        return
    await call.answer()
    await state.set_state(AdminStates.balance_user)
    await state.update_data(balance_action="add")
    await call.message.answer("➕ <b>Balans qo'shish</b>\n\nFoydalanuvchi ID yoki @username kiriting:",
                              reply_markup=admin_back_kb())


@admin_router.callback_query(F.data == "adm:bal_take")
async def adm_bal_take(call: CallbackQuery, state: FSMContext):
    if not await _admin_guard(call):
        return
    await call.answer()
    await state.set_state(AdminStates.balance_user)
    await state.update_data(balance_action="take")
    await call.message.answer("➖ <b>Balans ayirish</b>\n\nFoydalanuvchi ID yoki @username kiriting:",
                              reply_markup=admin_back_kb())


@admin_router.message(StateFilter(AdminStates.balance_user), F.text)
async def adm_balance_user(message: Message, state: FSMContext):
    if not is_admin_authed(message.from_user.id):
        return
    if message.text.strip().lower() == "/cancel":
        await state.clear()
        await message.answer("🛑 Bekor qilindi.", reply_markup=admin_back_kb())
        return
    user = db.find_user(message.text.strip())
    if user is None:
        await message.answer("❌ Foydalanuvchi topilmadi. ID yoki @username tekshirib ko'ring.")
        return
    await state.set_state(AdminStates.balance_amount)
    await state.update_data(balance_target=user["id"])
    await message.answer(
        f"👤 Foydalanuvchi: <b>{esc('@' + str(user.get('username'))) if user.get('username') else user['id']}</b>\n"
        f"💰 Hozirgi balans: <b>{fmt(user.get('balance', 0))} so'm</b>\n\n"
        "💵 Summani kiriting (so'mda):"
    )


@admin_router.message(StateFilter(AdminStates.balance_amount), F.text)
async def adm_balance_amount(message: Message, state: FSMContext):
    if not is_admin_authed(message.from_user.id):
        return
    amount = parse_uzs_amount(message.text)
    if amount is None or amount <= 0:
        await message.answer("❌ Noto'g'ri summa. Masalan: <code>50000</code>")
        return
    data = await state.get_data()
    user = db.get_user(int(data.get("balance_target", 0)))
    action = data.get("balance_action", "add")
    if user is None:
        await state.clear()
        await message.answer("❌ Foydalanuvchi topilmadi.")
        return

    await state.set_state(AdminStates.balance_confirm)
    await state.update_data(balance_amount=amount)
    verb = "qo'shish" if action == "add" else "ayirish"
    await message.answer(
        f"✅ Tasdiqlaysizmi?\n\n"
        f"👤 User: <code>{user['id']}</code>\n"
        f"💵 <b>{fmt(amount)} so'm</b> {verb}\n"
        f"💰 Joriy balans: <b>{fmt(user.get('balance', 0))} so'm</b>",
        reply_markup=_balance_kb(action),
    )


@admin_router.callback_query(F.data.startswith("adm:bal_do:"))
async def adm_balance_do(call: CallbackQuery, state: FSMContext):
    if not await _admin_guard(call):
        return
    action = call.data.split(":")[-1]
    data = await state.get_data()
    user = db.get_user(int(data.get("balance_target", 0)))
    amount = int(data.get("balance_amount", 0) or 0)
    if user is None or amount <= 0:
        await call.answer("❌ Ma'lumot topilmadi", show_alert=True)
        await state.clear()
        return

    delta = amount if action == "add" else -amount
    if delta < 0 and int(user.get("balance", 0)) < amount:
        await call.answer("❌ Balansda yetarli mablag' yo'q", show_alert=True)
        return

    user["balance"] = int(user.get("balance", 0)) + delta
    db.add_history(user, "admin_balance", delta, "Admin: qo'shdi" if delta > 0 else "Admin: ayirdi")
    db.save()
    await state.clear()
    await call.answer("✅ Bajarildi")
    await call.message.answer(
        f"✅ <b>Balans o'zgartirildi!</b>\n\n"
        f"👤 User: <code>{user['id']}</code>\n"
        f"💵 {'+' if delta > 0 else ''}{fmt(delta)} so'm\n"
        f"💰 Yangi balans: <b>{fmt(user['balance'])} so'm</b>",
        reply_markup=admin_back_kb(),
    )


# ------------------------------------------------------------------ ban/unban
def _resolve_user_text(user: dict) -> str:
    return f"@{user.get('username')}" if user.get("username") else str(user.get("id"))


@admin_router.callback_query(F.data == "adm:ban")
async def adm_ban(call: CallbackQuery, state: FSMContext):
    if not await _admin_guard(call):
        return
    await call.answer()
    await state.set_state(AdminStates.ban_user)
    await call.message.answer("🚫 <b>Ban</b>\n\nBanlash uchun foydalanuvchi ID yoki @username:",
                              reply_markup=admin_back_kb())


@admin_router.message(StateFilter(AdminStates.ban_user), F.text)
async def adm_ban_user(message: Message, state: FSMContext):
    if not is_admin_authed(message.from_user.id):
        return
    if message.text.strip().lower() == "/cancel":
        await state.clear()
        await message.answer("🛑 Bekor qilindi.", reply_markup=admin_back_kb())
        return
    user = db.find_user(message.text.strip())
    if user is None:
        await message.answer("❌ Foydalanuvchi topilmadi.")
        return
    user["banned"] = True
    db.save()
    await state.clear()
    await message.answer(
        f"🚫 <b>{esc(_resolve_user_text(user))}</b> banlandi.\n🆔 <code>{user['id']}</code>",
        reply_markup=admin_back_kb(),
    )
    try:
        await message.bot.send_message(
            user["id"],
            "🚫 <b>Siz botdan bloklandingiz.</b>\n\n"
            "Savollaringiz uchun qo'llab-quvvatlashga murojaat qiling.",
        )
    except Exception:  # noqa: BLE001
        pass


@admin_router.callback_query(F.data == "adm:unban")
async def adm_unban(call: CallbackQuery, state: FSMContext):
    if not await _admin_guard(call):
        return
    await call.answer()
    await state.set_state(AdminStates.unban_user)
    await call.message.answer("✅ <b>Unban</b>\n\nBandan chiqarish uchun foydalanuvchi ID yoki @username:",
                              reply_markup=admin_back_kb())


@admin_router.message(StateFilter(AdminStates.unban_user), F.text)
async def adm_unban_user(message: Message, state: FSMContext):
    if not is_admin_authed(message.from_user.id):
        return
    if message.text.strip().lower() == "/cancel":
        await state.clear()
        await message.answer("🛑 Bekor qilindi.", reply_markup=admin_back_kb())
        return
    user = db.find_user(message.text.strip())
    if user is None:
        await message.answer("❌ Foydalanuvchi topilmadi.")
        return
    user["banned"] = False
    db.save()
    await state.clear()
    await message.answer(
        f"✅ <b>{esc(_resolve_user_text(user))}</b> bandan chiqarildi.",
        reply_markup=admin_back_kb(),
    )


# ------------------------------------------------------------------ konkurs
def contest_data() -> dict:
    contest = db.data.setdefault("contest", {})
    contest.setdefault("id", new_id("c"))
    contest.setdefault("text", "🎉 Konkurs hali yaratilmagan")
    contest.setdefault("prize_stars", 0)
    contest.setdefault("winners", 0)
    contest.setdefault("min", 0)
    contest.setdefault("ends_in", 0)
    contest.setdefault("end_at", "")
    contest.setdefault("participants", [])
    contest.setdefault("active", False)
    return contest


def contest_text(c: dict) -> str:
    if not c.get("active"):
        return "🎉 <b>Hozircha faol konkurs yo'q</b>\n\nYangi konkurs yaratish uchun quyidagi tugmani bosing."
    end = c.get("end_at") or "—"
    return (
        f"🎉 <b>{esc(str(c.get('text', 'Konkurs')))}</b>\n\n"
        f"🏆 Sovrin: <b>{fmt(c.get('prize_stars', 0))} ⭐ Stars</b>\n"
        f"🥇 G'oliblar: <b>{c.get('winners', 0)} ta</b>\n"
        f"💰 Minimal xarid: <b>{fmt(c.get('min', 0))} so'm</b>\n"
        f"📅 Tugash: <b>{esc(end)}</b>\n"
        f"👥 Ishtirokchilar: <b>{len(c.get('participants', []))} ta</b>"
    )


def contest_kb() -> InlineKeyboardMarkup:
    c = contest_data()
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✏️ Tahrirlash" if c.get("active") else "🎉 Konkurs yaratish",
            callback_data="adm:contest_new")],
        [InlineKeyboardButton(text="👥 Ishtirokchilar", callback_data="adm:contest_users"),
         InlineKeyboardButton(text="🛑 Tugatish", callback_data="adm:contest_stop")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm:home")],
    ])


@admin_router.callback_query(F.data == "adm:contest")
async def adm_contest(call: CallbackQuery):
    if not await _admin_guard(call):
        return
    await call.answer()
    db.reload_if_changed()
    await call.message.answer(contest_text(contest_data()), reply_markup=contest_kb())


@admin_router.callback_query(F.data == "adm:contest_new")
async def adm_contest_new(call: CallbackQuery, state: FSMContext):
    if not await _admin_guard(call):
        return
    await call.answer()
    await state.set_state(AdminStates.contest_text)
    await call.message.answer(
        "🎉 <b>Yangi konkurs</b>\n\n"
        "1/5 — Konkurs matnini yuboring (misol: <b>Yangi yil sovg'asi — 1000 Stars!</b>)\n"
        "🛑 /cancel"
    )


@admin_router.message(StateFilter(AdminStates.contest_text), F.text)
async def adm_contest_text(message: Message, state: FSMContext):
    if not is_admin_authed(message.from_user.id):
        return
    await state.update_data(contest_text=message.html_text or message.text)
    await state.set_state(AdminStates.contest_prize)
    await message.answer("2/5 — Sovrami kiriting (Stars miqdori, masalan <code>1000</code>):\n🛑 /cancel")


@admin_router.message(StateFilter(AdminStates.contest_prize), F.text)
async def adm_contest_prize(message: Message, state: FSMContext):
    if not is_admin_authed(message.from_user.id):
        return
    try:
        prize = int(float(re.sub(r"[^\d]", "", message.text or "") or 0))
    except ValueError:
        prize = 0
    if prize <= 0:
        await message.answer("❌ Noto'g'ri son. Masalan: <code>1000</code>")
        return
    await state.update_data(contest_prize=prize)
    await state.set_state(AdminStates.contest_winners)
    await message.answer("3/5 — G'oliblar soni (masalan <code>5</code>):\n🛑 /cancel")


@admin_router.message(StateFilter(AdminStates.contest_winners), F.text)
async def adm_contest_winners(message: Message, state: FSMContext):
    if not is_admin_authed(message.from_user.id):
        return
    try:
        winners = int(re.sub(r"[^\d]", "", message.text or "") or 0)
    except ValueError:
        winners = 0
    if winners <= 0:
        await message.answer("❌ Noto'g'ri son. Masalan: <code>5</code>")
        return
    await state.update_data(contest_winners=winners)
    await state.set_state(AdminStates.contest_min)
    await message.answer("4/5 — Minimal xarid (so'mda, masalan <code>20000</code>):\n🛑 /cancel")


@admin_router.message(StateFilter(AdminStates.contest_min), F.text)
async def adm_contest_min(message: Message, state: FSMContext):
    if not is_admin_authed(message.from_user.id):
        return
    minimum = parse_uzs_amount(message.text)
    if minimum is None:
        await message.answer("❌ Noto'g'ri summa. Masalan: <code>20000</code>")
        return
    await state.update_data(contest_min=minimum)
    await state.set_state(AdminStates.contest_days)
    await message.answer("5/5 — Necha kun davomida (masalan <code>7</code>):\n🛑 /cancel")


@admin_router.message(StateFilter(AdminStates.contest_days), F.text)
async def adm_contest_days(message: Message, state: FSMContext):
    if not is_admin_authed(message.from_user.id):
        return
    try:
        days = int(re.sub(r"[^\d]", "", message.text or "") or 0)
    except ValueError:
        days = 0
    if days <= 0:
        await message.answer("❌ Noto'g'ri son. Masalan: <code>7</code>")
        return

    data = await state.get_data()
    end_dt = datetime.now(TZ) + timedelta(days=days)
    contest = contest_data()
    contest.update(
        id=new_id("c"),
        text=data.get("contest_text", "Konkurs"),
        prize_stars=int(data.get("contest_prize", 0) or 0),
        winners=int(data.get("contest_winners", 1) or 1),
        min=int(data.get("contest_min", 0) or 0),
        ends_in=days * 86400,
        end_at=end_dt.strftime("%d.%m.%Y %H:%M"),
        active=True,
    )
    db.data["contest"] = contest
    db.save()
    await state.clear()
    await message.answer(
        "✅ <b>Konkurs yaratildi!</b>\n\n" + contest_text(contest),
        reply_markup=contest_kb(),
    )
    # WebApp'ga darhol ko'rinishi uchun
    await notify_admins(f"🎉 Yangi konkurs e'lon qilindi: {esc(str(contest['text'])[:120])}")


@admin_router.callback_query(F.data == "adm:contest_users")
async def adm_contest_users(call: CallbackQuery):
    if not await _admin_guard(call):
        return
    await call.answer()
    participants = contest_data().get("participants", [])
    if not participants:
        await call.message.answer("👥 Hali ishtirokchi yo'q.", reply_markup=contest_kb())
        return
    lines = ["👥 <b>Konkurs ishtirokchilari</b>\n"]
    for uid in participants[:50]:
        u = db.get_user(int(uid))
        name = _resolve_user_text(u) if u else str(uid)
        spent = fmt(u.get("total_spent", 0)) if u else "—"
        lines.append(f"• {esc(name)} — {spent} so'm")
    if len(participants) > 50:
        lines.append(f"\n… va yana {len(participants) - 50} ta")
    await call.message.answer("\n".join(lines), reply_markup=contest_kb())


@admin_router.callback_query(F.data == "adm:contest_stop")
async def adm_contest_stop(call: CallbackQuery):
    if not await _admin_guard(call):
        return
    await call.answer("Tugatildi", show_alert=True)
    contest = contest_data()
    contest["active"] = False
    db.data["contest"] = contest
    db.save()
    await call.message.answer("🛑 Konkurs tugatildi.", reply_markup=admin_back_kb())


# ------------------------------------------------------------------ userbot login
@admin_router.callback_query(F.data == "adm:ub_qr")
async def adm_ub_qr(call: CallbackQuery):
    if not await _admin_guard(call):
        return
    await call.answer("🔑 QR tayyorlanmoqda...")
    if not (API_ID and API_HASH):
        await call.message.answer("❌ API_ID va API_HASH o'zgaruvchilari yo'q.")
        return
    try:
        client = UserbotClient("qr_login", api_id=API_ID, api_hash=API_HASH, in_memory=True)
        await client.start()
        token = await client.export_login_token()
        payload = f"tg://login?token={token}"
        import base64 as _b64
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={_b64.urlsafe_b64encode(payload.encode()).decode()}"
        await call.message.answer(
            "🔑 <b>Userbot QR bilan ulash</b>\n\n"
            "Quyidagi QR kodni <b>Telegra</b>ram (Settings → Devices → Link Desktop Device) orqali skanerlang:\n\n"
            f"<a href=\"{qr_url}\">🖼 QR kodni ochish</a>\n\n"
            "⏱ Kod 30 soniya ichida amal qiladi.",
            reply_markup=admin_back_kb(),
            disable_web_page_preview=False,
        )
        await asyncio.sleep(30)
        try:
            me = await client.import_login_token(token)
            await call.message.answer(f"✅ <b>Userbot ulandi!</b>\n👤 {esc(me.first_name or '')} (@{esc(me.username or '—')})")
            global userbot
            if userbot is not None:
                await userbot.stop()
            userbot = client
            await client.add_handler(UbMessageHandler(on_humo_message, ub_filters.chat(TOPUP_SOURCE_CHAT)))
            asyncio.create_task(ub_idle())
        except Exception as exc:  # noqa: BLE001
            await call.message.answer(f"⏱ Vaqt tugadi yoki tasdiqlanmadi: {exc}")
    except Exception as exc:  # noqa: BLE001
        await call.message.answer(f"❌ QR login xatosi: {exc}")


@admin_router.callback_query(F.data == "adm:ub_phone")
async def adm_ub_phone(call: CallbackQuery, state: FSMContext):
    if not await _admin_guard(call):
        return
    await call.answer()
    if not (API_ID and API_HASH):
        await call.message.answer("❌ API_ID va API_HASH o'zgaruvchilari yo'q.")
        return
    await state.set_state(AdminStates.ub_phone)
    await call.message.answer("📱 <b>Raqam bilan ulash</b>\n\nTelefon raqamingizni +998 XX XXX XX XX ko'rinishida yuboring:",
                              reply_markup=admin_back_kb())


@admin_router.message(StateFilter(AdminStates.ub_phone), F.text)
async def adm_ub_phone_wait(message: Message, state: FSMContext):
    if not is_admin_authed(message.from_user.id):
        return
    phone = re.sub(r"[^\d+]", "", message.text or "")
    if not re.fullmatch(r"\+\d{9,15}", phone):
        await message.answer("❌ Format noto'g'ri. Masalan: <code>+998901234567</code>")
        return
    await state.set_state(AdminStates.ub_code)
    await state.update_data(ub_phone=phone)
    try:
        client = UserbotClient("phone_login", api_id=API_ID, api_hash=API_HASH, in_memory=True)
        await client.start(phone=phone)
        await state.update_data(ub_client_id="phone_login")
    except Exception as exc:  # noqa: BLE001
        await state.clear()
        await message.answer(f"❌ Xato: {exc}")
        return
    await message.answer("🔐 Telegram yuborgan <b>tasdiqlash kodi</b>ni kiriting:")


@admin_router.message(StateFilter(AdminStates.ub_code), F.text)
async def adm_ub_code_wait(message: Message, state: FSMContext):
    if not is_admin_authed(message.from_user.id):
        return
    code = re.sub(r"[^\d]", "", message.text or "")[:5]
    if not code:
        await message.answer("❌ Kodni to'g'ri kiriting.")
        return
    try:
        client = await UserbotClient("phone_login", api_id=API_ID, api_hash=API_HASH, in_memory=True)
        await client.start(phone=(await state.get_data()).get("ub_phone"), code=code)
        global userbot
        if userbot is not None:
            try:
                await userbot.stop()
            except Exception:  # noqa: BLE001
                pass
        userbot = client
        await client.add_handler(UbMessageHandler(on_humo_message, ub_filters.chat(TOPUP_SOURCE_CHAT)))
        asyncio.create_task(ub_idle())
        session = await client.export_session_string()
        await state.clear()
        await message.answer(
            f"✅ <b>Userbot ulandi!</b>\n\n"
            f"🔑 <b>Railway ENV ga qo'ying</b> (bu sessiya kaliti — uni hech kimga bermang):\n\n"
            f"<code>SESSION_STRING={esc(session)}</code>",
            reply_markup=admin_back_kb(),
            disable_web_page_preview=True,
        )
    except Exception as exc:  # noqa: BLE001
        await state.clear()
        await message.answer(f"❌ Kod noto'g'ri: {exc}")


# =============================================================================
# 16b. ASOSIY MENYU CALLBACK
# =============================================================================
@router.callback_query(F.data.startswith("m:"))
async def main_menu_callback(call: CallbackQuery, state: FSMContext, bot: Bot, db_user: dict):
    await call.answer()
    msg = call.message
    actions = {
        "buy": lambda: buy_start(msg, state, db_user),
        "sell": lambda: sell_start(msg, state),
        "premium": lambda: msg.answer("💎 Premium bo'limi"),
        "gifts": lambda: msg.answer("🎁 Giftlar bo'limi"),
        "topup": lambda: topup_start(msg, state, db_user),
        "ref": lambda: show_referral(msg, state, bot, db_user),
        "profile": lambda: show_profile(msg, state, db_user),
        "history": lambda: show_history(msg, state, db_user),
        "support": lambda: show_support(msg, state),
    }
    action = actions.get(call.data.split(":", 1)[1])
    if action is not None:
        await action()


# =============================================================================
# 17. MAIN
# =============================================================================
async def main() -> None:
    global bot, BOT_USERNAME, DP

    if not TOKEN:
        log.error("BOT_TOKEN topilmadi!")
        return

    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    bot.session.middleware(StyledButtonsMiddleware())
    bot.session.middleware(PremiumEmojiMiddleware())
    dp = Dispatcher(storage=MemoryStorage())
    DP = dp

    access = AccessMiddleware()
    dp.message.outer_middleware(access)
    dp.callback_query.outer_middleware(access)

    dp.include_router(common_router)
    dp.include_router(admin_router)
    dp.include_router(router)

    try:
        # TOKEN tekshiruvi — xato bo'lsa bot O'LMASIN, kutib turadi.
        # Oldingi kodda get_me() xatosi butun jarayonni tugatirdi,
        # shuning uchun /start ga javob bo'lmasdi.
        me = None
        for attempt in range(1, 31):
            try:
                me = await bot.get_me()
                break
            except Exception as exc:  # noqa: BLE001
                log.error(
                    "Telegram bilan ulanib bo'lmadi (%d/30): %s — BOT_TOKEN to'g'rimi?",
                    attempt, exc,
                )
                await asyncio.sleep(10)

        if me is None:
            log.error("BOT_TOKEN noto'g'ri yoki bekor qilingan. Bot ishga tushmadi.")
            log.error("Railway ENV da BOT_TOKEN ni yangiling (mas'alan @BotFather orqali yangi token).")
            return

        BOT_USERNAME = me.username or ""
        try:
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(text="Web App ❐", web_app=WebAppInfo(url=WEBAPP_URL))
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("Menyu tugmasi o'rnatilmadi: %s", exc)

        log.info("🤖 Bot muvaffaqiyatli ishga tushdi: @%s (WebApp: %s)", me.username, WEBAPP_URL)
        set_runtime_status(
            bot="online",
            username=me.username,
            fragment_cookies=bool(FRAGMENT_COOKIES.get("stel_token") and FRAGMENT_COOKIES.get("stel_ssid")),
            fragment_hash=bool(FRAGMENT_API_HASH),
            wallet_seed=bool(WALLET_WORDS and not WALLET_SEED_ERROR),
        )
        try:
            await bot.delete_webhook(drop_pending_updates=False)
        except Exception as exc:  # noqa: BLE001
            log.warning("Webhook o'chirilmadi (davom etamiz): %s", exc)

        maybe_start_userbot()
        asyncio.create_task(process_gift_orders())
        asyncio.create_task(star_order_worker())
        asyncio.create_task(get_usdt_uzs_rate())

        # Polling'ni o'limaydigan qilamiz: vaqtinchalik xato botni to'xtatmasin
        while True:
            try:
                await dp.start_polling(
                    bot, allowed_updates=dp.resolve_used_update_types(), handle_signals=False
                )
                break
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                log.exception("Polling xatosi, 10 soniyadan keyin qayta uriniladi: %s", exc)
                set_runtime_status(bot="polling_error", error=str(exc)[:200])
                await asyncio.sleep(10)
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001
        log.exception("Bot ishlashida kutilmagan xato: %s", exc)
    finally:
        db.save()
        try:
            await bot.session.close()
        except Exception:  # noqa: BLE001
            pass
        log.info("Bot to'xtatildi.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Chiqish...")
