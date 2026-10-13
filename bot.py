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
import contextvars
import traceback
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
    TelegramConflictError,
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
from pyrogram.enums import ParseMode as UbParseMode
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

# === SESSION_STRING yordamchilari (ENV dan yuqorida chaqiriladi) ===
def normalize_env_session(name: str) -> str:
    """ENV dan olgan session string'ni tozalaydi.

    Railway'ga qo'ygan session Telegram xabaridan nusxa olingan bo'ladi —
    u yerida qator uzilishi yoki qo'shtirnoq bo'lishi mumkin. Bu esa
    base64 uzunligini buzadi va "unpack requires a buffer of 271 bytes"
    xatosini keltiradi (bu xato hech qanday ma'no bermaydi va
    administratorni chalkashtiradi).
    """
    raw = os.getenv(name, "")
    if not raw:
        return ""
    cleaned = "".join(raw.split())
    if cleaned != raw.strip():
        log.warning(
            "%s da qo'shimcha bo'sh joy topildi va tozalandi "
            "(odatda Telegram'dan nusxa olganda qoladi).", name,
        )
    return cleaned


# ---------------------------------------------------------------------------
# SESSION_STRING tekshiruvi
# ---------------------------------------------------------------------------
# Pyrofork session string'i struct ">BI?256sQ?" formatida paketlanadi:
#   dc_id(1) + api_id(4) + test_mode(1) + auth_key(256) + user_id(8) + is_bot(1)
#   = 271 bayt  ->  base64 = 362 belgi
# Eski formatlar: 351 belgi (263 bayt) va 356 belgi (267 bayt).
#
# Nima uchun bu muhim:
#   Noto'g'ri uzunlikdagi session string'i ulanganda xato bo'ladi —
#   "unpack requires a buffer of 271 bytes" — va bu xato NIMA uchun
#   bo'lganini tushuntirmaydi, admin esa qayta-qayta urinib
#   hayotdan bezor bo'ladi. Shu sababli startup'da tekshiramiz va
#   aniq, tuzatiladigan xabar beramiz.
SESSION_STRING_EXPECTED = 362
SESSION_STRING_LEGACY = (351, 356)


def normalize_session_string(raw: Any) -> str:
    """Session string'ni tozalaydi.

    Eng ko'p uchraydigan xato — Telegram'dan nusxa olganda satr oxirida
    yoki boshida qolgan bo'sh joy / qator uzilishi / qo'shtirnoq.
    Ular base64 uzunligini buzadi va "unpack requires a buffer of 271
    bytes" xatosini keltiradi.
    """
    if not isinstance(raw, str):
        return ""
    s = raw.strip().strip("\"'")
    # DIQQAT: base64 ichida BO'SH JOY BO'LMAYDI — shuning uchun uni
    # qisqartirib (collapse) qilish emas, butunlay OLIB TASHLASH kerak.
    # Aks holda Telegram'dan nusxa olganda qolgan bo'sh joy yoki qator
    # uzilishi base64 uzunligini buzadi va "unpack requires a buffer of
    # 271 bytes" xatosi chiqadi.
    return "".join(s.split())


def diagnose_session_string(raw: Any) -> tuple[bool, str]:
    """(to'g'rimi?, tushuntirish) — admin uchun o'zbekcha."""
    s = normalize_session_string(raw)
    if not s:
        return False, "bo'sh"
    n = len(s)
    if n == SESSION_STRING_EXPECTED:
        return True, f"to'g'ri ({n} belgi)"
    if n in SESSION_STRING_LEGACY:
        return True, f"eski format ({n} belgi) — ishlaydi, yangilashni tavsiya qilamiz"
    # Texnik ma'lumotni (base64 xatosi va h.k.) yashiramiz — u
    # administratorga hech nima bermaydi. Faqat: nechta belgi, nechta
    # bayt, va QANDAY tuzatish kerakligi.
    try:
        import base64 as _b64
        decoded = _b64.urlsafe_b64decode(s + "=" * (-n % 4))
        got = f"{len(decoded)} bayt"
    except Exception:  # noqa: BLE001
        got = "tabiiy base64 satri emas"
    return False, (
        f"Siz kiritgan qiymat <b>{n} belgi</b> ({got}), "
        f"lekin to'g'ri session <b>{SESSION_STRING_EXPECTED} belgi</b> bo'lishi kerak.\n\n"
        "🔧 <b>Qanday tuzatiladi:</b>\n"
        "1) <code>/admin → 🔑 Userbot ulash (QR)</code> yoki "
        "<code>📱 Raqam bilan ulash</code>\n"
        "2) <code>/admin → 📤 Session zaxirasi</code>\n"
        "3) O'sha qiymatni Railway ENV ga <b>SESSION_STRING</b> nomi bilan qo'ying\n\n"
        "⚠️ <i>Tashqi saytlardan (telethon, online generator) yoki eski "
        "backupdan olingan session <b>ishlamaydi</b> — format boshqa. "
        "Session faqat shu bot orqali olinadi.</i>"
    )



# =============================================================================
# SESSION_STRING — Railway ENV ga qo'yish SHART EMAS (bazada saqlanadi)
# =============================================================================
# MUAMMO: session faqat Railway ENV da saqlanganda har bir redeploy'da
# uni qayta kiritish kerak edi. Telefondan yangi session olib ENV'ga
# yozib redeploy qilsangiz — eski session (ENV'dagi) baribir qo'llanilib
# qoladi va yangisi "eskirgan" bo'lib tuyuladi.
#
# YECHIM: telefon/QR orqali ulangan akkauntning session string'i
# AVTOMATIK bazaga yoziladi. Baza (/data/users_db.json) Railway'da
# saqlanadi — redeploy'da ham joyida qoladi, ENV kerak bo'lmaydi.
SESSION_KEY = "userbot_session"


def save_session_to_db(session: str) -> bool:
    """Session string'ni bazaga saqlaydi (kalit hech qayerga yuborilmaydi)."""
    session = normalize_session_string(session)
    if not session:
        return False
    try:
        settings = db.data.setdefault("settings", {})
        if settings.get(SESSION_KEY) == session:
            return False  # o'zgarmagan
        settings[SESSION_KEY] = session
        db.save()
        # Kalitning o'zi logga TUSHMAYDI — faqat uzunligi
        log.info("🔐 Session bazaga saqlandi (%d belgi) — Railway ENV kerak emas",
                 len(session))
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("Sessionni bazaga saqlab bo'lmadi: %s", exc)
        return False


def get_session_from_db() -> str:
    try:
        return normalize_session_string(
            (db.data.get("settings", {}) or {}).get(SESSION_KEY, "")
        )
    except Exception:  # noqa: BLE001
        return ""


def delete_session_from_db() -> bool:
    settings = db.data.setdefault("settings", {})
    if settings.pop(SESSION_KEY, None) is None:
        return False
    db.save()
    return True


def resolve_session_string() -> tuple[str, str]:
    """Qaysi session ishlatilishini aniqlaydi.

    QAYTA QATIK: bazadagi session ENG YANGISI (telefon/QR orqali ulangan),
    shuning uchun u birinchi turadi. Railway ENV zaxira sifatida qoladi —
    faqat baza bo'sh bo'lsa ishlatiladi.

    Qaytaradi: (session, manba) — manba: "db" | "env" | "yo'q"
    """
    from_db = get_session_from_db()
    if from_db:
        return from_db, "db"
    return SESSION_STRING, ("env" if SESSION_STRING else "yo'q")


# --- Userbot (pyrofork) ---
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
SESSION_STRING = normalize_env_session("SESSION_STRING")
# DIQQAT: sovg'a yuborish va bank xabarlarini tekshirish BITTA userbot
# orqali amalga oshiriladi — alohida session ENV kaliti kerak emas.
TOPUP_SOURCE_CHAT = os.getenv("TOPUP_SOURCE_CHAT", "@humocardbot")
# Gift worker tekshiruv oraliqi (soniya). Test uchun kichik qilinishi mumkin.
GIFT_POLL_INTERVAL = float(os.getenv("GIFT_POLL_INTERVAL", "15"))
# Necha sikldan keyin butunlay to'xtaymiz (cheksiz retry + admin spam bo'lmasligi uchun)
GIFT_MAX_ATTEMPTS = int(os.getenv("GIFT_MAX_ATTEMPTS", "5"))
# Urinishlar orasidagi tanaffus (s). Test uchun 0 qilinishi mumkin.
GIFT_RETRY_DELAY = float(os.getenv("GIFT_RETRY_DELAY", "3"))

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

# (kalit, nom, stars, narx, TELEGRAM_EMOJI)
#
# DIQQAT: Telegram'da bir necha gift bir xil narxda bo'ladi
# (masalan Ayiqcha va Yurakcha ikkalasi ham 15 ⭐). Agar faqat `price`
# bo'yicha solishtirsak, doim birinchisi (Yurakcha) tanlanadi va
# mijoz barcha sovg'alarni yurakcha sifatida oladi — shuning uchun
# EMOSI bo'yicha moslashtirish asosiy usul, price faqat zaxira.
GIFTS = [
    ("bear", "🧸 Ayiqcha", 15, 3_000, "🧸"),
    ("heart", "💝 Yurakcha", 15, 3_000, "💝"),
    ("box", "🎁 Sovg'a qutisi", 25, 6_000, "🎁"),
    ("rose", "🌹 Atirgul", 25, 6_000, "🌹"),
    ("cake", "🎂 Tort", 50, 10_000, "🎂"),
    ("bouquet", "💐 Gul dastasi", 50, 10_000, "💐"),
    ("rocket", "🚀 Raketa", 50, 10_000, "🚀"),
    ("cup", "🏆 Kubok", 100, 20_000, "🏆"),
    ("ring", "💍 Uzuk", 100, 20_000, "💍"),
    ("diamond", "💎 Olmos", 100, 20_000, "💎"),
    ("champagne", "🍾 Shampan", 50, 10_000, "🍾"),
]
# Telegram'dagi rasmiy sovg'a emojilari (moslashtirish uchun)
GIFT_EMOJI: dict[str, str] = {g[0]: g[4] for g in GIFTS}
GIFTS_BY_KEY = {g[0]: g for g in GIFTS}
MANUAL_FALLBACK = os.getenv("MANUAL_FALLBACK", "1").strip().lower() not in ("0", "false", "no", "")
MIN_TOPUP = 1_000
MAX_TOPUP = 10_000_000
TOPUP_TIMEOUT_SEC = 60 * 60  # 60 daqiqa (eski: 5 min — yetarli emas edi)
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

log.info("🐍 Python %s", sys.version.split()[0])

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


# =============================================================================
# NFT RENT (ijara) — narx hisobi
# =============================================================================
# Ijara muddati cheklovlari (mijoz tanlaydi)
NFT_MIN_DAYS = 3
NFT_MAX_DAYS = 50
# Telegram tarmog'ida bir tranzaksiya uchun to'lanadigan xarajat.
# Bu foydalanuvchiga alohida ko'rsatiladi — u ijaraga QO'SHILMAYDI.
NFT_NETWORK_FEE = 1700
# Tez tanlash uchun qulay muddatlar
NFT_QUICK_DAYS = (3, 7, 14, 30)


# =============================================================================
# TELEGRAM NFT SAHIFASIDAN RASM OLISH
# =============================================================================
# Mijoz/admin `https://t.me/nft/FinePen-18272` yuborsa, Telegram shu
# sahifa uchun server tomonda preview yaratadi:
#   <meta property="og:image" content="https://cdn4.telesco.pe/file/....jpg">
#   <meta property="og:title" content="Fine Pen #18272">
#
# DIQQAT: raqamsiz havola (`/nft/FinePen`) 302 bilan telegram.org ga
# qaytaradi va rasm YO'Q. Raqam bilan (`/nft/FinePen-18272`) esa
# 200 qaytaradi. Ya'ni haqiqiy NFT bo'lishi shart.
#
# Bu funksiya:
#   • rasm havolasini (cdn*.telesco.pe) qaytaradi
#   • nom va raqamni og:title dan avtomatik ajratadi
#   • muvaffaqiyatsiz bo'lsa hech nima buzmaydi (None qaytaradi)

NFT_PAGE_HOSTS = ("t.me", "telegram.me", "telegram.dog", "nft.telegram.org")
# Brauzer kabi User-Agent — Telegram bot/curl User-Agent larini
# redirect qiladi (302 -> telegram.org), bu esa preview bermaydi.
NFT_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def is_nft_page_url(url: str) -> bool:
    """Havola Telegram NFT sahifasi mi? (t.me/nft/...)"""
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return False
    if parts.scheme not in ("http", "https"):
        return False
    host = (parts.hostname or "").lower()
    if not any(host == h or host.endswith("." + h) for h in NFT_PAGE_HOSTS):
        return False
    # Faqat /nft/<slug> turidagi sahifalar
    return bool(re.match(r"^/nft/", parts.path or ""))


def nft_slug_from_url(url: str) -> tuple:
    """`.../nft/FinePen-18272` -> ("FinePen", 18272)

    Telegram slug'i `Nom-Raqam` shaklida. Nom ichida chiziqcha
    bo'lishi mumkin (Jack-in-the-Box-9999), shuning uchun OXIRGI
    chiziqchadan ajratamiz.
    """
    try:
        path = urlsplit(url.strip()).path or ""
    except ValueError:
        return ("", None)
    m = re.search(r"/nft/([^/?#]+)", path)
    if not m:
        return ("", None)
    slug = m.group(1)
    m2 = re.match(r"^(.*?)[-_](\d+)$", slug)
    if m2:
        name = m2.group(1)
        try:
            return (name, int(m2.group(2)))
        except ValueError:
            return (name, None)
    return (slug, None)


async def resolve_nft_page(url: str) -> Optional[dict]:
    """Telegram NFT sahifasidan rasm + nom + tavsifni oladi.

    `t.me/nft/<slug>-<raqam>` server tomonda `og:image` beradi.
    Raqam yo'q bo'lsa yoki NFT mavjud bo'lmasa 302 qaytaradi —
    u holda `None` qaytariladi va mijozga placeholder ko'rsatiladi.
    """
    if not is_nft_page_url(url):
        return None
    try:
        async with httpx.AsyncClient(
            timeout=12.0, follow_redirects=False, headers={"User-Agent": NFT_UA}
        ) as client:
            resp = await client.get(url.strip())
    except Exception as exc:  # noqa: BLE001
        log.warning("NFT sahifasi yuklanmadi: %s", exc)
        return None
    if resp.status_code != 200 or "text/html" not in resp.headers.get("content-type", ""):
        return None
    html_body = resp.text[:200_000]

    def meta(prop: str) -> str:
        m = re.search(
            r'<meta[^>]+property=["\']' + re.escape(prop) + r'["\'][^>]+content=["\']([^"\']+)',
            html_body, re.I,
        )
        if not m:
            m = re.search(
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']' + re.escape(prop) + r'["\']',
                html_body, re.I,
            )
        return m.group(1).strip() if m else ""

    image = meta("og:image")
    if not image or not image.startswith("http"):
        return None

    title = meta("og:title")            # "Fine Pen #18272"
    number = None
    if title:
        m = re.search(r"#(\d+)\s*$", title)
        if m:
            try:
                number = int(m.group(1))
            except ValueError:
                number = None
        title = re.sub(r"\s*#\d+\s*$", "", title).strip()

    if not number:
        _, number = nft_slug_from_url(url)

    return {
        "image": image,
        "title": title or "",
        "number": number,
        "description": meta("og:description"),
    }


def nft_has_viewable_image(item: dict) -> bool:
    """NFT rasmi WebApp'da ko'rinadimi?

    DIQQAT: Telegram `file_id` brauzerda to'g'ridan-to'g'ri ochilmaydi —
    shuning uchun server uni `/api/nft-image/<id>` orqali proxy qiladi
    (server.ts). Shuning uchun file_id ham "ko'rinadi" deb hisoblanadi.
    Faqat `t.me/nft/...` kabi link rasm EMAS.
    """
    img = str(item.get("image") or "").strip()
    if not img:
        return False
    if img.startswith("http://") or img.startswith("https://"):
        return True
    # Telegram file_id — server proxy orqali ko'rsatadi
    if not any(c.isspace() or c in "/." for c in img) and len(img) >= 20:
        return True
    return False


def nft_rent_quote(daily: Any, days: Any) -> dict:
    """Ijaraning to'liq hisobini qaytaradi.

    Rasmdagi kabi:
        Per day        = kunlik narx
        Rent (N days) = kunlik × muddat
        Network fee    = 1 700
        Total          = Rent + Network fee
    """
    d = max(NFT_MIN_DAYS, min(NFT_MAX_DAYS, num(days, NFT_MIN_DAYS)))
    per_day = max(0, num(daily))
    rent = per_day * d
    total = rent + NFT_NETWORK_FEE
    return {
        "days": d,
        "per_day": per_day,
        "rent": rent,
        "network_fee": NFT_NETWORK_FEE,
        "total": total,
    }


def active_nfts() -> list[dict]:
    """WebApp va botda ko'rsatiladigan NFT'lar (arzon xilidan)."""
    items = [
        n for n in db.data.get("nfts", {}).values()
        if n.get("active", True)
    ]
    return sorted(items, key=lambda n: num(n.get("daily"), 10 ** 9))


def now_ms() -> float:
    """Hozirgi vaqt — MILLISEKUND.

    Nima uchun: server.ts va WebApp `Date.now()` ishlatadi (ms), lekin
    bot.py avval `time.time()` (sekund) ishlatardi. Bitta DB maydoniga
    ikki xil birlik yozilardi va natijada:
      • botda yaratilgan so'rovni server.ts DARHOL "expired" deb hisoblar
        (1.79e9 < 1.79e12)
      • WebApp'da yaratilgan so'rov bot.py hech qachon muddati
        o'tgan deb hisoblamaydi
    Bu — "qabul qilish" tugmasi "eskirgan" deydigan asl sabab edi.
    Endi HAMMA joyda ms.
    """
    return time.time() * 1000


def to_ms(value: Any, default: float = 0.0) -> float:
    """DB'dan olingan muddatni ms ga keltiradi (eski sekund qiymatlar uchun)."""
    v = num(value, 0)
    if v <= 0:
        return default
    # 10^11 dan kichik = sekund (1973-yildan keyingi vaqt sekundda)
    return v * 1000 if v < 1e11 else v


def now_iso() -> str:
    return now().isoformat(timespec="seconds")


def fmt(n: Any) -> str:
    """Sonni 1 234 5 67 ko'rinishida formatlaydi.

    None / bo'sh / noto'g'ri qiymat kelganda XATO TOSHLAYDI — bu
    /start menyusining butunlay chiqmasiga olib keladi (foydalanuvchi
    hech narsani ko'rmaydi). Shuning uchun himoya qilamiz.
    """
    if n is None or n == "":
        return "0"
    try:
        return f"{int(n):,}".replace(",", " ")
    except (TypeError, ValueError):
        return "0"


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
# Foydalanuvchi hisobidagi sonli maydonlar. Bulardagi null / "" / "abc"
# qiymat butun botni buzadi (masalan int(None) -> TypeError -> /start
# menyusining umuman chiqmasligi).
USER_NUM_FIELDS = (
    "balance", "total_spent", "total_topup", "referrals_count",
    "ref_stars", "ref_stars_earned", "bonus_claimed", "stars_bought",
)


def normalize_user_numbers(user: dict) -> dict:
    """Foydalanuvchi dict'idagi sonli maydonlarni int qiladi.

    Nima uchun kerak: ma'lumotlar bazasi, WebApp va eski yozuvlardan
    keladi — u yerda `null` yoki matn bo'lishi mumkin. Bunday bitta
    noto'g'ri qiymat foydalanuvchiga menyuning umuman ko'rinmasiga
    olib keladi. Shu sababli foydalanuvchi ma'lumotlari O'QILGANDA
    (get_user / get_or_create_user) avtomatik tozalaymiz — shunda
    25+ joydagi `int(...)` xavfsiz bo'lib qoladi.
    """
    for f in USER_NUM_FIELDS:
        if f in user:
            user[f] = num(user.get(f))
    return user


class JsonDB:
    def __init__(self, path: str):
        self.path = path
        self._file_lock = threading.Lock()
        self.data: dict[str, Any] = self._load()
        for key in ("users", "topups", "sales", "orders", "nfts"):
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
                        # DIQQAT: bu PUL bilan bog'liq voqea. Asosiy baza
                        # buzilgani va zaxiraga QAYTISH natijada oxirgi
                        # yozuvlar (balanslar, buyurtmalar, bekor qilingan
                        # gift'lar va qaytarilgan pullar) YO'QOLADI.
                        # Shuning uchun admin'ga darhol xabar beramiz.
                        log.error(
                            "Asosiy baza buzilgan, zaxiradan tiklandi: %s — "
                            "oxirgi yozuvlar yo'q bo'lishi mumkin!", candidate,
                        )
                        DB_RESTORED_FROM_BACKUP["path"] = candidate
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
        u = self.users.get(str(user_id))
        if u is not None:
            normalize_user_numbers(u)
        return u

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
        normalize_user_numbers(user)
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


# Baza zaxiradan tiklanganmi? (pulgа xavfi bor — admin ga xabar beriladi)
DB_RESTORED_FROM_BACKUP: dict[str, str] = {"path": ""}

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
# BITTA userbot ikkala vazifani ham bajaradi:
#   1) @humocardbot bank xabarlarini kuzatadi -> balansni to'ldiradi
#   2) sovg'alarni (gift) yuboradi
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


class NftStates(StatesGroup):
    link = State()      # NFT linki / rasmi
    photo = State()     # ALDIYI NFT ga rasm biriktirish
    title = State()    # nomi (ixtiyoriy)
    number = State()    # raqami (ixtiyoriy)
    daily = State()     # 1 kunlik narx


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
    ub_password = State()


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
        # DIQQAT: GIFTS tuple'i 5 ta elementli (emoji oxirida).
        # Guruhlab ochish (unpack) o'rniga INDEKS bilan olamiz — kelajakda
        # yana element qo'shilsa ham bu qator buzilmaydi.
        "gifts": [[g[0], g[1], g[2], g[3]] for g in GIFTS],
        "sup": SUPPORT_USERNAME,
    }


def webapp_history(user: dict) -> list[dict]:
    return [
        {"t": h.get("type"), "a": h.get("amount"), "d": (h.get("date") or "")[:16], "u": h.get("unit") or "UZS"}
        for h in (user.get("history") or [])[-10:]
    ]


def num(value: Any, default: int = 0) -> int:
    """Qiymatdan xavfsiz butun son oladi.

    Nima uchun kerak: ma'lumotlar baza yoki WebApp dan keladi, u yerda
    null / "" / "abc" bo'lishi mumkin. `int(None)` esa TypeError beradi
    va butun menyuni (masalan /start) YO'Q QILADI — foydalanuvchi hech
    narsani ko'rmaydi. Shu sababli har joyda himoya qilamiz.
    """
    try:
        if value is None or value == "":
            return default
        if isinstance(value, str):
            # "84 so'm", "1 000", "84.5", "84,5" kabi matnlarni tozalaymiz.
            # Aks holda int("84 so'm") xato berib, butun bo'lim ishlamaydi.
            v = re.sub(r"[^0-9.,]", "", value)
            if not v:
                return default
            # "1 000,50" / "1,000.50" ni bitta kasr separatorga keltiramiz
            if "," in v and "." in v:
                v = v.replace(",", "") if v.rindex(".") > v.rindex(",") else v.replace(".", "").replace(",", ".")
            elif "," in v:
                # vergul: agar 3 ta raqamli qism bo'lsa -> minglar, aks holda kasr
                v = v.replace(",", "") if len(v.split(",")[-1]) == 3 else v.replace(",", ".")
            return int(float(v))
        return int(float(value))
    except (TypeError, ValueError):
        return default


def build_webapp_url(user: dict) -> str:
    params = {
        "uid": user["id"],
        "un": user.get("username") or "",
        "photo_url": user.get("photo_url") or "",
        "balance": num(user.get("balance")),
        "refs": num(user.get("referrals_count")),
        "rs": num(user.get("ref_stars")),
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
        # make_button matndagi oddiy emojini olib, o'rniga animatsiyalangan
        # premium emoji ikonkasini qo'yadi (Telegram Bot API 9.0+)
        return make_button(text, callback_data=f"m:{action}", style=st)

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [b("⭐ Stars sotib olish", "buy", "success")],
            [b("💸 Stars sotish", "sell", "primary"), b("💎 Premium", "premium", "primary")],
            [b("🎁 Giftlar", "gifts", "danger")],
            [b("💳 Balans to'ldirish", "topup", "success"), b("👥 Referal", "ref", "primary")],
            [make_button("📱 Web App ❐", web_app=WebAppInfo(url=build_webapp_url(user)), style="primary")],
            [b("👤 Profil", "profile"), b("📜 Tarix", "history")],
            [make_button("🎭 NFT Gift ijarasi", callback_data="m:nft", style="primary")],
            [make_button("💬 Support", url=f"https://t.me/{SUPPORT_USERNAME}", style="danger")],
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
            [InlineKeyboardButton(text="🩺 Userbot holati", callback_data="adm:ub_status"),
             InlineKeyboardButton(text="📤 Session zaxirasi", callback_data="adm:ub_export")],
            [InlineKeyboardButton(text="🔎 Gift diagnostikasi", callback_data="adm:gift_diag"),
             InlineKeyboardButton(text="♻️ Gift qayta yuborish", callback_data="adm:gift_retry")],
            [InlineKeyboardButton(text="➕ NFT qo'shish", callback_data="adm:nft_add"),
             InlineKeyboardButton(text="📋 NFT ro'yxati", callback_data="adm:nft_list")],
            [InlineKeyboardButton(text="🚫 Kutayotgan gift'larni bekor qilish",
                                  callback_data="adm:gift_cancel:gone", style="danger")],
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
# TUGMALARDAGI PREMIUM (ANIMATSIYALANGAN) EMOJILAR
# -----------------------------------------------------------------------------
# Telegram Bot API 9.0+ da `icon_custom_emoji_id` maydoni qo'shildi —
# endi tugma belgisida ANIMATSIYALANGAN premium emoji chiqadi
# (oddiy matn emojisi emas).
#
# Muhim: bu maydon Telegram'da (bot ichida) ishlaydi, WebApp brauzerida emas.
# WebApp uchun alohida animatsiya tizimi bor (src/components/AEmoji.tsx).
#
# Xavfsizlik: Telegram yangi maydonni qabul qilmasa yoki ID noto'g'ri
# bo'lsa, xabar yuborilmaydi. Shuning uchun barcha tugmalar avval
# premium ikonka bilan yuboriladi, xato bo'lsa — oddiy matnli variant
# bilan qayta yuboriladi (SafeIconMiddleware).
# =============================================================================
from premium_emoji import PREMIUM_EMOJI

# Tugma matni → premium emoji belgisi
MENU_EMOJI: dict[str, str] = {
    "Stars sotib olish": "⭐",   # yulduz
    "Stars sotish": "💸",        # pul uchqun
    "Premium": "💎",             # olmos
    "Giftlar": "🎁",             # sovg'a
    "Balans to'ldirish": "💳",   # karta
    "Referal": "👥",             # odamlar
    "Web App": "🌐",             # global tarmoq
    "Web App ❐": "🌐",
    "Profil": "👤",              # odam
    "Tarix": "📜",               # hujjat
    "Support": "🆘",             # yordam
    "NFT Gift ijarasi": "🎁",   # NFT (premium sovg'a belgisi)
}


def _icon_to_emoji() -> dict[str, str]:
    """ID → emoji (faqat MENU_EMOJI orqali, aniq moslik)."""
    out: dict[str, str] = {}
    for label, ch in MENU_EMOJI.items():
        eid = PREMIUM_EMOJI.get(ch)
        if eid:
            out[str(eid)] = ch
    return out


ICON_TO_EMOJI: dict[str, str] = {}


def premium_icon(text: str) -> Optional[str]:
    """Tugma matnidan premium emoji ID'sini oladi (yo'q bo'lsa None)."""
    clean = strip_leading_emoji(text)
    key = clean if clean in MENU_EMOJI else text.strip()
    ch = MENU_EMOJI.get(key)
    if not ch:
        return None
    eid = PREMIUM_EMOJI.get(ch)
    return str(eid) if eid else None


def strip_leading_emoji(text: str) -> str:
    """Matn boshidagi emojini olib tashlaydi (premium ikonkasi bilan almashtirish uchun)."""
    import re as _re
    return _re.sub(r"^[\U0001F000-\U0001FAFF☀-➿⬀-⯿️]+\s*", "", text or "").strip()


def make_button(text: str, **kwargs: Any) -> InlineKeyboardButton:
    """Premium emoji ikonkasi bilan tugma yaratadi.

    `icon_custom_emoji_id` beriladi va matndagi oddiy emoji olib tashlanadi
    (Telegram ikonkani o'zi ko'rsatadi). Telegram qabul qilmasa —
    SafeIconMiddleware oddiy variantga qaytaradi.
    """
    icon = premium_icon(text)
    if icon:
        return InlineKeyboardButton(
            text=strip_leading_emoji(text),
            icon_custom_emoji_id=icon,
            **kwargs,
        )
    return InlineKeyboardButton(text=text, **kwargs)


ICON_TO_EMOJI.update(_icon_to_emoji())


class SafeIconMiddleware(BaseRequestMiddleware):
    """`icon_custom_emoji_id` qabul qilinmasa — oddiy tugma bilan qayta yuboradi.

    Telegram/API versiyasi yangi maydonni qo'llamasa yoki emoji ID
    noto'g'ri bo'lsa, butun bot ishlashini to'xtatmasligi kerak —
    shuning uchun xatoda ikonkalar olib tashlanib, matn emojilari
    tiklanib, xabar qayta yuboriladi.
    """

    _methods = (SendMessage, EditMessageText, SendPhoto, EditMessageCaption)

    @staticmethod
    def _strip(method: Any) -> Any:
        """Tugmalardan ikonkalarni olib, matn emojilarini tiklaydi."""
        markup = getattr(method, "reply_markup", None)
        if markup is None:
            return method

        def fix_markup(mk: Any) -> Any:
            rows = []
            changed = False
            for row in getattr(mk, "inline_keyboard", []) or []:
                new_row = []
                for btn in row:
                    icon = getattr(btn, "icon_custom_emoji_id", None)
                    if icon:
                        changed = True
                        ch = ICON_TO_EMOJI.get(str(icon), "⭐")
                        # emoji matnning boshiga qaytamiz
                        new_txt = f"{ch} {btn.text}".strip() if ch not in (btn.text or "") \
                            else btn.text
                        data = btn.model_dump(exclude={"icon_custom_emoji_id", "text"})
                        new_row.append(InlineKeyboardButton(**data, text=new_txt))
                    else:
                        new_row.append(btn)
                rows.append(new_row)
            if not changed:
                return mk
            return markup.__class__(inline_keyboard=rows)

        if hasattr(markup, "inline_keyboard"):
            return method.model_copy(update={"reply_markup": fix_markup(markup)})

        def fix_reply(mk: Any) -> Any:
            rows = []
            changed = False
            for row in getattr(mk, "keyboard", []) or []:
                new_row = []
                for btn in row:
                    icon = getattr(btn, "icon_custom_emoji_id", None)
                    if icon:
                        changed = True
                        ch = ICON_TO_EMOJI.get(str(icon), "⭐")
                        new_txt = f"{ch} {btn.text}".strip() if ch not in (btn.text or "") \
                            else btn.text
                        data = btn.model_dump(exclude={"icon_custom_emoji_id", "text"})
                        new_row.append(KeyboardButton(**data, text=new_txt))
                    else:
                        new_row.append(btn)
                rows.append(new_row)
            if not changed:
                return mk
            return markup.__class__(keyboard=rows, resize_keyboard=getattr(mk, "resize_keyboard", None),
                                   one_time_keyboard=getattr(mk, "one_time_keyboard", None),
                                   input_field_placeholder=getattr(mk, "input_field_placeholder", None),
                                   selective=getattr(mk, "selective", None))

        if hasattr(markup, "keyboard"):
            return method.model_copy(update={"reply_markup": fix_reply(markup)})
        return method

    async def __call__(self, make_request, bot_: Bot, method):  # type: ignore[override]
        if not isinstance(method, self._methods):
            return await make_request(bot_, method)
        markup = getattr(method, "reply_markup", None)
        has_icon = markup is not None and "icon_custom_emoji_id" in str(
            getattr(markup, "model_dump_json", lambda: "")()
        )
        try:
            return await make_request(bot_, method)
        except Exception as exc:  # noqa: BLE001
            if not has_icon:
                raise
            log.warning("Premium emoji ikonkalari qabul qilinmadi, oddiy variantga qaytamiz: %s",
                        str(exc)[:120])
            return await make_request(bot_, self._strip(method))


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


@common_router.callback_query(F.data.startswith("topup_cancel"))
async def cb_topup_cancel(call: CallbackQuery):
    """To'lov so'rovini bekor qiladi.

    MUHIM: bu tugma `cancel_inline_kb(f"topup_cancel:{id}")` orqali
    yuborilardi, lekin HANDLER YO'Q edi — shuning uchun tugma
    hech narsa qilmasdi (mijoz "Bekor qilish" bossa ham so'rov faol
    qolardi). Endi ishlaydi.

    Bekor qilinganda hech qanday pul olinmagan (mijoz hali
    to'lov qilmagan), shuning uchun balansga hech narsa qaytarilmaydi.
    """
    tid = call.data.split(":", 1)[1] if ":" in call.data else ""
    db.reload_if_changed()
    t = db.data.get("topups", {}).get(tid)
    if not t:
        await call.answer("So'rov topilmadi", show_alert=True)
        try:
            await call.message.edit_text("❌ Bu so'rov topilmadi (balki allaqachon yopilgan).")
        except Exception:  # noqa: BLE001
            pass
        return
    # Faqat hali kutilayotgan so'rovni bekor qilamiz
    if t.get("status") != "pending":
        label = {
            "completed": "allaqachon to'ldirilgan",
            "expired": "muddati tugagan",
            "cancelled": "allaqachon bekor qilingan",
        }.get(t.get("status"), t.get("status"))
        await call.answer(f"So'rov {label}", show_alert=True)
        try:
            await call.message.edit_text(
                f"ℹ️ Bu so'rov {label} — bekor qilish shart emas."
            )
        except Exception:  # noqa: BLE001
            pass
        return

    t["status"] = "cancelled"
    t["cancelled_at"] = now_iso()
    db.save()
    await call.answer("Bekor qilindi", show_alert=True)
    try:
        await call.message.edit_text(
            "❌ <b>To'lov so'rovi bekor qilindi</b>\n\n"
            "💰 Summa: <b>{amt} UZS</b>\n"
            "🆔 <code>{tid}</code>\n\n"
            "<i>Xavfsiz — kartadan to'lov qilinmagansiz, pul qaytarilmaydi.</i>\n\n"
            "💳 Balans to'ldirish uchun /start → Balans to'ldirish".format(
                amt=fmt(num(t.get("amount"))), tid=esc(str(tid)),
            )
        )
    except Exception:  # noqa: BLE001
        pass
    log.info("💳 To'lov so'rovi bekor qilindi: %s (%s UZS)",
             tid, fmt(num(t.get("amount"))))


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
    # So'rov WebApp'da yaratilgan bo'lishi mumkin — baza eskirgan bo'lsa,
    # topup topilmadi deb "allaqachon ko'rilgan" xatosi chiqardi.
    db.reload_if_changed()
    t = db.data["topups"].get(tid)
    if not t:
        await call.answer("So'rov topilmadi (baza yangilanmagan bo'lishi mumkin)", show_alert=True)
        return
    if t["status"] != "pending":
        await call.answer(f"Bu so'rov allaqachon yopilgan ({t['status']})", show_alert=True)
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
    db.reload_if_changed()   # WebApp'da yaratilgan so'rovni topish uchun
    t = db.data["topups"].get(tid)
    if not t:
        await call.answer("So'rov topilmadi (baza yangilanmagan bo'lishi mumkin)", show_alert=True)
        return
    if t["status"] != "pending":
        await call.answer(f"Bu so'rov allaqachon yopilgan ({t['status']})", show_alert=True)
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
    # Foydalanuvchi botda ro'yxatdan o'tmagan bo'lishi ham mumkin —
    # shunda ham ismi va profil rasmini ko'rsatamiz (Stars uchun
    # profil rasmi shart emas, faqat ma'lumot uchun).
    prof = await resolve_recipient_profile(username)
    who = f"@{esc(username)}"
    if prof and prof.get("name"):
        who = esc(str(prof["name"]))
    line = f"👤 Qabul qiluvchi: <b>{who}</b>\n"
    if prof and prof.get("from_bot") is False:
        line += f"<i>(@{esc(username)} — botda ro'yxatdan o'tmagan)</i>\n"
    await message.answer(
        line + "\n"
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
    text = format_order_channel_text(
        title=title, who=who, amount_text=amount_text,
        price=price, cashback=cashback,
    )

    # DIQQAT: kanal xabaridagi tugma `callback_data` bo'lishi MUMKIN EMAS —
    # kanalda bot ishlovchi emas, `bonus_claim` hech qachon chaqirilmaydi
    # (o'lik tugma). Shuning uchun bu yerda URL tugma qo'yamiz: mijoz
    # bosganda do'kon WebApp'i ochiladi.
    markup: Optional[InlineKeyboardMarkup] = None
    if cashback:
        markup = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text=f"🎁 Bonus: {fmt(cashback)} so'm (🌸)",
                url=WEBAPP_URL,
            )
        ]])
    buttons: list[list[Any]] = [list(markup.inline_keyboard[0])] if markup else []
    buttons.append([InlineKeyboardButton(text="📊 NeonShop", url=WEBAPP_URL)])
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)  # type: ignore[arg-type]

    try:
        await bot.send_message(ORDERS_CHANNEL, text,
                               reply_markup=markup, disable_web_page_preview=True)
        if not CHANNEL_OK.get("ok"):
            set_runtime_status(orders_channel="connected", channel=ORDERS_CHANNEL)
            CHANNEL_OK.update(ok=True)
    except Exception as exc:  # noqa: BLE001
        # DIQQAT: avval bu xato faqat log'ga yozilardi — admin hech qachon
        # bilmasdi. Endi runtime holatiga yoziladi va admin ogohlantiriladi.
        log.warning("Kanalga xabar yuborilmadi: %s", exc)
        if CHANNEL_OK.get("ok"):
            CHANNEL_OK.update(ok=False)
            set_runtime_status(
                orders_channel="error", channel=ORDERS_CHANNEL,
                channel_error=str(exc)[:300],
            )
            await notify_admins(
                "❌ <b>ORDERS_CHANNEL ga xabar yuborib bo'lmadi!</b>\n\n"
                f"📢 Kanal: <code>{esc(ORDERS_CHANNEL)}</code>\n"
                f"🔍 Sabab: <code>{esc(str(exc)[:200])}</code>\n\n"
                "🔧 <i>Botni kanalga ADMIN qilib qo'shing, yoki kanal "
                "nomini <code>ORDERS_CHANNEL</code> ENV da to'g'rilang.</i>"
            )


# Kanalga xabar yuborilganmi? (bir marta xato bo'lsa admin ogohlantiriladi)
CHANNEL_OK: dict[str, Any] = {"ok": False}


def mask_username(name: Any) -> str:
    """Usernamni kanalda yashiradi: @odilbek -> @ode****

    Nima uchun: ORDERS_CHANNEL kanal ochiq bo'lishi mumkin, mijoz
    usernami ko'rinib qolsa (shaxsiy ma'lumot). Faqat bosh harflar
    ko'rinadi — mijozni aniqlab bo'lmaydi, lekin xabar tushunarli.
    """
    t = str(name or "").strip()
    if not t:
        return "@user"
    t = t.lstrip("@")
    # Juda qisqa nomlarni umuman yashirmaymiz ( "@ab" ni yashirish
    # ma'nosiz — u allaqachon deyarli ochiq)
    if len(t) <= 4:
        return "@" + t[0] + "***"
    return "@" + t[:3] + "****"


def format_order_channel_text(*, title: str, who: str, amount_text: str,
                              price: int, cashback: int = 0) -> str:
    """ORDERS_CHANNEL uchun xabar matni (mijoz rasmidagi format).

        ⭐ Stars olindi
        👤 odilbek
        📦 Miqdor: 50 ⭐
          Summasi: 10 000 so'm
          Keshbek: +10 so'm

    server.ts dagi channelOrderText() bilan BIR XIL bo'lishi shart —
    bot orqali va WebApp orqali xaridlarda format farq qilmasin.
    """
    lines = [
        f"⭐ <b>{esc(title)}</b> ",
        # Kanalda usernam YASHIRILADI (shaxsiy ma'lumot himoyasi)
        f"👤 <b>{esc(mask_username(who))} </b>",
        "",
        f"📦 <b>{esc(amount_text)}</b>",
        f"💵 <b>Summasi:</b> {fmt(price)} so'm",
    ]
    if cashback:
        lines.append(f"  <b>Keshbek:</b> +{fmt(cashback)} so'm")
    return "\n".join(lines)


async def check_orders_channel() -> None:
    """Ishga tushganda kanalga xabar yuborish mumkinligini tekshiradi.

    Sabab: bot kanalga ADMIN bo'lmasa yoki kanal nomi noto'g'ri bo'lsa,
    barcha savdo xabarlari jimgina YO'QOLIB boradi. Shu sababli startup'da
    tekshirib, /api/health va Railway loglarida ko'rsatamiz.
    """
    if bot is None or not ORDERS_CHANNEL:
        set_runtime_status(orders_channel="not_configured")
        return
    try:
        chat = await bot.get_chat(ORDERS_CHANNEL)
        # "administrator" — bot kanalda nima qila olishini aniqlaydi
        member = None
        try:
            me = await bot.get_me()
            member = await bot.get_chat_member(chat.id, me.id)
        except Exception:  # noqa: BLE001
            pass
        perms = getattr(member, "status", None)
        perms_txt = str(getattr(perms, "value", perms) or "?")
        can_post = perms_txt in ("administrator", "creator") or perms is None
        if can_post:
            log.info("📢 ORDERS_CHANNEL (%s) tayyor — savdo xabarlari yuboriladi", ORDERS_CHANNEL)
            set_runtime_status(
                orders_channel="connected", channel=ORDERS_CHANNEL,
                channel_role=perms_txt,
            )
        else:
            log.warning(
                "📢 ORDERS_CHANNEL (%s): bot holati %s — xabar yuborish RAD etilishi mumkin",
                ORDERS_CHANNEL, perms_txt,
            )
            set_runtime_status(
                orders_channel="no_permission", channel=ORDERS_CHANNEL,
                channel_role=perms_txt,
            )
    except Exception as exc:  # noqa: BLE001
        log.warning("ORDERS_CHANNEL tekshirilmadi: %s", exc)
        set_runtime_status(
            orders_channel="unreachable", channel=ORDERS_CHANNEL,
            channel_error=str(exc)[:300],
        )


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
# =============================================================================
# Bank xabarini tahlil qilish (HAQIQIY HUMO formati)
# -----------------------------------------------------------------------------
# @humocardbot xabari shakli:
#
#     💸 To'lov
#     ➖ 2.000,00 UZS          ← TO'LOV summasi  (2 000 so'm)
#     📍 TRANSPORT TOLOV>TOS    ← izoh
#     💳 HUMOCARD *3682        ← karta
#     🕓 15:16 11.10.2026      ← vaqt
#     💰 19.587,36 UZS         ← QOLDIQ BALANS (buni ALMASHMASLIK KERAK!)
#
# DIQQAT: 💰 — qoldiq balans, ➖ — to'lov. Ularni aralashtirish butun
# avto to'ldirishni buzadi. Quyidagi parser avval ➖/➕ ni, keyin boshqani
# qidiradi va 💰/Balans qatorlarini BUTUNLAY tashlab yuboradi.
# =============================================================================

# To'lov qatori belgilari (yuqori ustuvorlik)
PAY_MARKERS = ("➖", "➕", "➗", "➤")
# Qoldiq balans belgilari — BU QATORLAR SUMMA EMAS
BALANCE_MARKERS = ("💰", "🏦", "💳💰", "balance", "balans", "qoldiq", "остаток", "kirim")
CURRENCY_WORDS = r"(?:UZS|uzs|so'?m|som|soʻm|сум|сумма|tinyin)"

HUMO_CARD_RX = re.compile(r"HUMOCARD\s*\*(\d+)")
HUMO_CARD_ANY_RX = re.compile(r"(?:HUMOCARD|HUMO)\s*\**\s*(\d{4})", re.IGNORECASE)

# Bir qatorda: belgi + raqam + pul birligi
HUMO_LINE_MONEY_RX = re.compile(
    r"(?P<mark>[^\w\s])?\s*(?P<num>\d[\d.,\s]*\d|\d)\s*(?P<cur>" + CURRENCY_WORDS + r")?",
    re.IGNORECASE,
)


def _normalize_amount(raw: str) -> Optional[int]:
    """Bank formatidagi raqamni butun songa aylantiradi.

    HUMO Yevropa usulini ishlatadi:  nuqta = minglik ajratuvchi,
                                     vergul = kasr belgisi.
        "2.000,00"  -> 2000
        "19.587,36" -> 19587
        "50 000"    -> 50000
        "1.234.567" -> 1234567
    """
    if raw is None:
        return None
    s = str(raw).strip().replace("\u00a0", " ").replace("\u202f", " ")
    s = re.sub(r"[^\d.,]", "", s)
    if not s:
        return None

    has_dot, has_comma = "." in s, "," in s

    if has_dot and has_comma:
        # Oxirgi ajratuvchi — kasr belgisi, qolgani — minglik
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "").replace(".", ".")
    elif has_comma:
        tail = s.split(",")[-1]
        s = s.replace(",", ".") if len(tail) in (1, 2) else s.replace(",", "")
    elif has_dot:
        # "2.000" / "50.000" / "1.234.567" — minglik ajratuvchi
        parts = s.split(".")
        if len(parts) > 1 and all(len(x) == 3 for x in parts[1:]) and len(parts[0]) <= 3:
            s = "".join(parts)
        else:
            tail = parts[-1]
            s = s if len(tail) == 3 else "".join(parts)

    try:
        return int(Decimal(s or "0"))
    except (InvalidOperation, ValueError):
        return None


def _is_balance_line(line: str) -> bool:
    """Bu qator qoldiq balansmi? (💰 19.587,36 UZS)"""
    low = line.lower()
    return any(m in low or m in line for m in BALANCE_MARKERS)


def parse_humo_payment(text: str) -> Optional[tuple[int, Optional[str]]]:
    """@humocardbot xabaridan TO'LOV summasi va karta raqamini ajratadi.

    DIQQAT: xabar ichida ikki raqam bo'ladi — to'lov (➖) va qoldiq
    balans (💰). Biz har doim TO'LOVNI olamiz, qoldiqni esa butunlay
    e'tiborsiz qoldiramiz (aks holda mijozga 19 587 qo'shilirdi).
    """
    text = text or ""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    # 1) Eng ishonchli: ➖ / ➕ bilan boshlanadigan qator (to'lov deltasi)
    for line in lines:
        if _is_balance_line(line):
            continue
        if not any(m in line for m in PAY_MARKERS):
            continue
        m = HUMO_LINE_MONEY_RX.search(line)
        if m:
            amount = _normalize_amount(m.group("num"))
            if amount:
                card = _extract_card(text)
                return amount, card

    # 2) "To'lov: 2.000,00" / "Summa: ..." kabi yozilgan qatorlar
    for line in lines:
        if _is_balance_line(line):
            continue
        if not re.search(r"to'lov|tolov|to‘lov|сумма|summa|amount|оплата",
                         line, re.IGNORECASE):
            continue
        m = HUMO_LINE_MONEY_RX.search(line)
        if m:
            amount = _normalize_amount(m.group("num"))
            if amount:
                return amount, _extract_card(text)

    # 3) Pul birligi bor qator — lekin balans qatorlari emas
    for line in lines:
        if _is_balance_line(line):
            continue
        if not re.search(CURRENCY_WORDS, line, re.IGNORECASE):
            continue
        m = HUMO_LINE_MONEY_RX.search(line)
        if m:
            amount = _normalize_amount(m.group("num"))
            if amount:
                return amount, _extract_card(text)

    # 4) So'nggi chora: belgisiz, faqat son (kartadan keyingi bo'sh qatorlar)
    for line in lines:
        if _is_balance_line(line) or re.search(r"HUMOCARD|\d{2}:\d{2}|\d{4}\.\d{2}\.\d{4}",
                                              line, re.IGNORECASE):
            continue
        m = re.fullmatch(r"\s*(\d[\d.,\s]*)\s*", line)
        if m:
            amount = _normalize_amount(m.group(1))
            if amount:
                return amount, _extract_card(text)

    return None


def _extract_card(text: str) -> Optional[str]:
    m = HUMO_CARD_ANY_RX.search(text) or HUMO_CARD_RX.search(text)
    return m.group(1) if m else None


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
        # AVVAL: faqat "➕" belgisi bo'lsa qayta ishlanardi. Haqiqiy HUMO
        # xabarida esa "➖" (to'lov) va "💰" (qoldiq balans) ishlatiladi —
        # ya'ni eski filtr xabarni BUTUNLAY tashlab yuborardi.
        # Endi: to'lov belgisi, karta yoki "to'lov" so'zi bo'lsa yetarli.
        has_marker = any(m in text for m in PAY_MARKERS + ("💸", "💵"))
        has_word = bool(re.search(r"to'lov|tolov|to‘lov|qabul|payme|оплата|сумма",
                                  text, re.IGNORECASE))
        has_card = bool(re.search(r"HUMOCARD", text, re.IGNORECASE))
        if not has_marker and not has_word and not has_card:
            return
        # Balansga qo'shishni bildirmaydigan xabarlarni tashlab yuboramiz
        if re.search(r"xarajat|chiqarish|withdraw|pullash|soldi", text, re.IGNORECASE):
            return
        # Balansga qo'shishni bildirmaydigan xabarlarni tashlab yuboramiz
        if re.search(r"xarajat|chiqarish|withdraw|pullash|soldi", text, re.IGNORECASE):
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
        now = now_ms()
        # WebApp'dan yaratilgan to'lovlar ham ko'rinishi uchun bazani yangilaymiz
        db.reload_if_changed()

        # Muddati o'tgan so'rovlarni tozalaymiz.
        # DIQQAT: expires_at BIRLIGI — millisekund (server.ts bilan bir xil).
        # Eski sekund qiymatlari to_ms() orqali avtomatik konvert qilinadi.
        for t in db.data["topups"].values():
            if t.get("status") == "pending" and to_ms(t.get("expires_at"), now) < now:
                t["status"] = "expired"

        # Faol so'rovlar: mijoz aynan shu summani to'lashini kutamiz
        pending = [
            t for t in db.data["topups"].values()
            if t.get("status") == "pending" and to_ms(t.get("expires_at"), now) > now
        ]

        # Karta tekshiruvi: o'z kartamizdan tushgan to'lovni tasdiqlaymiz
        our_digits = "".join(ch for ch in str(CARD_NUMBER) if ch.isdigit())
        card_ok = True
        if card and our_digits:
            card_ok = card in our_digits or our_digits.endswith(card)

        # Aniq moslik. DIQQAT: mijoz kartaga `amount_to_send`
        # (so'ralgan summa + ketma-ket raqam) yuboradi, shuning uchun
        # IKKALA qiymat ham tekshiriladi:
        #   1) amount_to_send == kelgan summa  (eng ishonchli)
        #   2) amount == kelgan summa           (eskiroq usul / qo'lda
        #                                        to'lov yuborgan bo'lsa)
        matches_exact = [
            t for t in pending
            if t.get("amount_to_send") and int(t["amount_to_send"]) == amount
            and (card_ok or not card)
        ]
        matches_plain = [
            t for t in pending
            if (not t.get("amount_to_send"))
            and int(t.get("amount", 0)) == amount
            and (card_ok or not card)
        ]
        matches = matches_exact or matches_plain

        # Aniq moslik topilmasa: kartamizga kelgan to'lov bo'lsa va
        # faqat BITTA kutilayotgan so'rov bo'lsa — mijoz to'lagan
        # HAQIQIY summani to'ldiramiz (qisman to'ldirish).
        # Masalan: mijoz 10 000 so'rov qilgan, 5 000 yuborgan.
        # Bunday holda balansga 5 000 qo'shiladi — mijoz pulini
        # yo'qotmaydi, xato tuzatiladi.
        # Bank xabaridan to'lovni yuborgan shaxsni aniqlab bo'lmaydi
        # (faqat summa + karta ma'lum). Shuning uchun to'lov faqat BITTA
        # kutilayotgan so'rov bo'lganda avtomatik bog'lanadi — aks
        # holda chalkashlikni oldi olish uchun admin hal qiladi.
        partial = False
        if not matches and card_ok and len(pending) == 1:
            matches = pending
            partial = True

        if matches:
            # Eng eski so'rovni birinchi yopamiz
            t = min(matches, key=lambda x: x.get("created_at", ""))
            t["status"] = "completed"
            t["completed_at"] = now_iso()
            t["auto_verified"] = True
            t["payment_method"] = "humocard"
            # Balansga MIJOZ TO'LAGAN haqiqiy summa qo'shiladi
            # (qisman to'ldirishda so'ralgan summa emas).
            # To'liq moslik: mijoz kartaga amount_to_send yuborgan
            # (qo'shimcha biz qo'shgan edik) — balansga esa SO'RALGAN
            # summa qo'shiladi. Qisman moslikda — HAQIQIY yuborilgan.
            credit = amount if partial else int(t["amount"])
            t["requested_amount"] = int(t.get("amount", 0))
            t["amount"] = credit
            t["partial"] = partial

            u = db.data["users"].get(str(t["user_id"]))
            if u:
                u["balance"] = int(u.get("balance", 0)) + credit
                u["total_topup"] = int(u.get("total_topup", 0)) + credit
                note = f"Auto: HUMOCARD *{card or '????'}"
                if partial:
                    note += f" (qisman: so'ralgan {fmt(t['requested_amount'])} so'm)"
                db.add_history(u, "topup", credit, note)
                try:
                    if partial:
                        txt = (
                            f"✅ <b>{fmt(credit)} UZS</b> balansingizga qo'shildi!\n\n"
                            f"💳 To'lov avtomatik aniqlanildi.\n"
                            f"ℹ️ Siz so'rovingizni <b>{fmt(t['requested_amount'])} so'm</b> qilib "
                            f"yaratgan edingiz, lekin <b>{fmt(credit)} so'm</b> yubordingiz — "
                            f"kelgan summa qo'shildi.\n"
                            f"💰 Balans: <b>{fmt(u['balance'])} so'm</b>"
                        )
                    else:
                        txt = (
                            f"✅ <b>{fmt(credit)} UZS</b> balansingizga qo'shildi!\n\n"
                            f"💳 To'lov avtomatik aniqlanildi.\n"
                            f"💰 Balans: <b>{fmt(u['balance'])} so'm</b>"
                        )
                    await bot.send_message(u["id"], txt)
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
                f"<i>Bir nechta so'rov kutayotgan bo'lgani uchun avtomatik "
                f"aniqlab bo'lmadi. To'lovni to'g'ri mijozga biriktirish uchun: "
                f"<b>/admin → ➕ Balans qo'shish</b> orqali shu mijozning ID siga "
                f"so'rov ro'yxatidan topib, <b>+{fmt(amount)}</b> qo'shing.</i>"
            )
    except Exception as exc:  # noqa: BLE001
        log.exception("Humo xabarini qayta ishlashda xato")
        await notify_admins(f"❌ Avto-to'lov tekshiruvi xatosi: {exc}")


async def resolve_recipient_profile(username: str) -> Optional[dict]:
    """Berilgan username egasi haqida ism va profil rasmini oladi.

    MUHIM: foydalanuvchi botda RO'YXATDAN O'TMagan bo'lishi mumkin —
    Telegram o'chiringan hisoblarni ham ko'rsatadi. Shu sababli:
      1) avval bazadagi ma'lumotni tekshiramiz
      2) yo'q bo'lsa — userbot orqali Telegram'dan so'raymiz
    Botga kirish shart EMAS.

    Stars xaridida profil rasmi shart emas, giftda ham ixtiyoriy —
    shuning uchun xato bo'lsa ham `None` qaytaramiz, ishni to'xtirmaydi.
    """
    name = (username or "").lstrip("@").strip()
    if not name:
        return None

    # 1) Bazadagi ma'lumot
    local = next(
        (u for u in db.data["users"].values()
         if (u.get("username") or "").lower() == name.lower()),
        None,
    )
    if local and local.get("photo_url"):
        return {
            "name": local.get("first_name") or f"@{name}",
            "photo": local["photo_url"],
            "from_bot": True,
        }

    # 2) Telegram'dan (userbot bo'lmasa ham xato berilmaydi)
    if userbot is None:
        return {
            "name": (local or {}).get("first_name") or f"@{name}",
            "photo": (local or {}).get("photo_url") or "",
            "from_bot": False,
        }
    try:
        chat = await userbot.get_chat(name)
        display = (
            " ".join(x for x in [getattr(chat, "first_name", ""),
                                getattr(chat, "last_name", "")] if x)
            or getattr(chat, "title", "")
            or f"@{name}"
        )
        photo = ""
        try:
            if getattr(chat, "photo", None):
                # Telegram'da har doim boshqa o'lchamli nusxalar bor;
                # eng kichigi (katta) Telegram'da tez yuklanadi.
                for size in ("big", "small", "thumb"):
                    cand = next((s for s in chat.photo.sizes if s.type == size), None)
                    if cand is not None:
                        photo = cand.file_id
                        break
        except Exception:  # noqa: BLE001
            photo = ""

        # Natija bazasiga saqlaymiz — keyingi so'rovlarda tez
        if local is not None:
            local["first_name"] = display
            if photo:
                local["photo_url"] = photo
            db.save()

        return {"name": display, "photo": photo, "from_bot": False}
    except Exception as exc:  # noqa: BLE001
        log.debug("Profilni aniqlab bo'lmadi (%s): %s", name, exc)
        return {
            "name": (local or {}).get("first_name") or f"@{name}",
            "photo": (local or {}).get("photo_url") or "",
            "from_bot": False,
        }


async def process_gift_orders() -> None:
    """Gift buyurtmalarini userbot orqali avto-yuboradi.

    Ikkala manbadan oladi:
      • bot ichidagi buyurtmalar (kind=gift)
      • WebApp'dan kelgan buyurtmalar (bazaga yozilgan, source=webapp)
    Xato bo'lsa 3 marta qayta urinadi, keyin adminga yuboriladi.
    """
    log.info("🎁 Gift avto-yetkazuv xizmati ishga tushdi...")
    warned_no_userbot = False
    last_pending = -1
    last_written = False
    stuck_notified_at = 0.0  # qisqarib qolgan gift'lar haqida eslatma
    while True:
        try:
            await asyncio.sleep(GIFT_POLL_INTERVAL)
            gclient = userbot  # BITTA akkaunt: bank xabarlari + gift
            if gclient is None:
                # AVVAL jimgina "continue" edi — admin hech narsani bilmasdi va
                # gift buyurtmalari cheksiz kutib qolardi. Endi ogohlantiramiz.
                pending = sum(
                    1 for o in db.data.get("orders", {}).values()
                    if o.get("kind") == "gift" and not o.get("gift_sent")
                )
                if not warned_no_userbot:
                    warned_no_userbot = True
                    log.error("🎁 Gift worker: userbot ulanmagan — gift yuborilmaydi")
                    set_runtime_status(
                        gift_worker="blocked_userbot_offline", gift_pending=pending
                    )
                    if pending:
                        await notify_admins(
                            "❌ <b>Gift yuborilmayapti</b>\n\n"
                            f"📦 Kutayotgan gift buyurtmalari: <b>{pending}</b>\n"
                            "👤 Sabab: userbot ulanmagan (SESSION_STRING muddati tuggan bo'lishi mumkin).\n"
                            "🔧 <i>/admin → 📱 Raqam bilan ulash orqali yangi SESSION_STRING oling.</i>"
                        )
                elif pending != last_pending:
                    set_runtime_status(gift_pending=pending)
                last_pending = pending
                continue
            if warned_no_userbot:
                # Userbot qayta ulandi — kutayotgan buyurtmalar borligini xabar beramiz
                warned_no_userbot = False
                waiting = sum(
                    1 for o in db.data.get("orders", {}).values()
                    if o.get("kind") == "gift" and not o.get("gift_sent")
                )
                log.info("🎁 Gift worker: userbot ulandi, kutayotgan %d ta gift", waiting)
                if waiting:
                    await notify_admins(
                        "✅ <b>Gift yuborish qayta boshlandi</b>\n\n"
                        f"📦 Kutayotgan: <b>{waiting}</b> ta gift\n"
                        "🤖 Endi avtomatik yuboriladi."
                    )
            db.reload_if_changed()
            for order in list(db.data.get("orders", {}).values()):
                if order.get("kind") != "gift":
                    continue
                if order.get("gift_sent"):
                    continue
                if order.get("gift_processing"):
                    # Jarayon yuborish paytida to'xtab qolgan bo'lsa, buyurtma
                    # butunlay tashlab qolinar edi — flag doim True qolib ketardi.
                    # 5 daqiqadan eskirganini qayta urinishga qaytaramiz.
                    if time.time() - float(order.get("gift_processing_at") or 0) > 300:
                        order["gift_processing"] = False
                        order["gift_error"] = "jarayon to'xtab qoldi, qayta urinish"
                        log.warning("Gift %s: eskirgan flag to'g'rilandi", order.get("id"))
                    else:
                        continue
                if order.get("status") not in ("completed", "pending_admin", "processing"):
                    continue
                gift_key = order.get("gift") or order.get("gift_key") or ""
                gift_def = next((g for g in GIFTS if g[0] == gift_key), None)
                # `gift` maydoni yo'q bo'lsa (eski/webapp yozuvlari) — Stars bo'yicha
                # aniqlaymiz, aks holda hech narsa topilmaydi va gift yuborilmaydi
                stars = gift_def[2] if gift_def else (order.get("stars") or order.get("amount"))
                gift_emoji = GIFT_EMOJI.get(gift_key, "") or str(
                    (gift_def[4] if gift_def and len(gift_def) > 4 else "") or "")
                recipient = normalize_gift_recipient(order.get("recipient"))
                if not recipient or not stars:
                    # Noto'g'ri qabul qiluvchi — cheksiz urinish ham
                    # yordam bermaydi, lekin mijozga xabar beramiz.
                    order["gift_error"] = (
                        f"Qabul qiluvchi topilmadi: {str(order.get('recipient'))[:40]!r}"
                    )
                    order["gift_failed"] = True
                    continue
                if not stars:
                    continue
                # Cheksiz qayta urinishni oldini olish: bir necha urinishdan keyin
                # to'xtaymiz (aks holda har 15 soniyada admin'ga xabar yuborilib,
                # xato butun kanonni spam qilardi).
                if int(order.get("gift_attempts", 0)) >= GIFT_MAX_ATTEMPTS:
                    continue

                order["gift_processing"] = True
                order["gift_processing_at"] = time.time()
                db.save()
                try:
                    _stage("1) sovg'alar ro'yxatini olish (get_available_gifts)")
                    gifts = await gclient.get_available_gifts()
                    _stage("2) sovg'ani tanlash (find_gift)")
                    match = find_gift(gifts, gift_key, stars)
                    if match is None:
                        log.warning("Gift (%s / %s) uchun mos sovg'a topilmadi",
                                    gift_key, gift_emoji)
                        order["gift_processing"] = False
                        order["gift_error"] = (
                            f"Mos sovg'a topilmadi (qidirilgan: {gift_emoji}, "
                            f"{stars} ⭐). Telegram'da mavjud: "
                            + ", ".join(
                                f"{getattr(getattr(g,'sticker',None),'emoji','?')}={g.price}"
                                for g in gifts[:12]
                            )
                        )
                        db.save()
                        await notify_admins(
                            f"⚠️ Gift <code>#{order['id']}</code> ({gift_key} {gift_emoji}) "
                            f"uchun mos sovg'a topilmadi.\n"
                            f"🔍 Telegram'dagi mavjud sovg'alar: "
                            + ", ".join(
                                f"{getattr(getattr(g,'sticker',None),'emoji','?')} ({g.price}⭐)"
                                for g in gifts[:12]
                            )
                        )
                        continue

                    sent = False
                    last_err: Optional[Exception] = None
                    for attempt in range(3):
                        _stage(f"3) send_gift (urinish {attempt + 1}/3)")
                        try:
                            # Telegram: hide_my_name=True -> anonim
                            # (InputInvoiceStarGift.hide_name = flags.0?true)
                            anon = order_is_anonymous(order)
                            await gclient.send_gift(
                                chat_id=recipient,
                                gift_id=match.id,
                                hide_my_name=anon,
                            )
                            sent = True
                            break
                        except Exception as exc:  # noqa: BLE001
                            last_err = exc
                            log.warning("Gift yuborishda xato (%d/3): %s", attempt + 1, exc)
                            await asyncio.sleep(GIFT_RETRY_DELAY * (1 + attempt))

                    if not sent:
                        raise last_err or RuntimeError("noma'lum xato")

                    _stage("4) bazaga yozish va xabar yuborish")
                    order["gift_sent"] = True
                    order["gift_processing"] = False
                    order["gift_sent_at"] = now_iso()
                    order["gift_attempts"] = 0
                    order.pop("gift_processing_at", None)
                    order.pop("gift_error", None)
                    order.pop("gift_failed", None)
                    # WebApp buyurtmalar ro'yxatida "Yuborilmoqda…" deb qolmasligi uchun
                    order["status"] = "completed"
                    db.save()
                    log.info("🎁 Gift %s @%s ga userbot orqali yuborildi", gift_key, recipient)
                    await _safe_send(
                        order["user_id"],
                        f"🎁 <b>Sovg'a yuborildi!</b>\n\n"
                        f"🎉 {esc(str(order.get('title', gift_key)))}\n"
                        f"👤 Qabul qiluvchi: <b>@{esc(recipient)}</b>\n"
                        + ("🕶️ Yuborish: <b>anonim</b>"
                           if order_is_anonymous(order)
                           else "👤 Yuboruvchi: <b>do'kon profili ko'rinadi</b>") + "\n"
                        + f"🆔 Buyurtma: <code>{order['id']}</code>",
                    )
                    await notify_admins(
                        f"🎁 Gift <code>#{order['id']}</code> ({gift_key}) @{esc(recipient)} ga yuborildi."
                    )
                except Exception as exc:  # noqa: BLE001
                    internal = is_internal_gift_error(exc)
                    order["gift_processing"] = False
                    order["gift_error"] = str(exc)
                    # DIQQAT: urinishlar soni faqat DOIMIY xatolarda oshiriladi.
                    # ICHKI xato (masalan "NoneType has no len()") mijozning
                    # gunohi emas — 5 urinishdan keyin ham mijoz pulini to'lab
                    # giftini olmay qolmasligi kerak.
                    if internal:
                        order["gift_internal_errors"] = int(
                            order.get("gift_internal_errors", 0)) + 1
                    else:
                        order["gift_attempts"] = int(order.get("gift_attempts", 0)) + 1
                    order.pop("gift_processing_at", None)
                    # Eslatma: ichki xatodan keyin "gift_attempts" o'zgarmaydi,
                    # shuning uchun uni `.get()` bilan olamiz (KeyError bo'lmasin).
                    last_err = int(order.get("gift_attempts", 0))
                    # QAYERDA xatolashganini aniq bilish uchun traceback.
                    # AVVAL faqat str(exc) yuborilardi ("object of type
                    # 'NoneType' has no len()") — qaysi qatorda sodir bo'lishi
                    # aniq bo'lmaydi, shuning uchun topish imkoni yo'q edi.
                    tb = "".join(traceback.format_exception(exc, limit=8))
                    stage = _gift_stage.get() or "?"
                    order["gift_error_stage"] = stage
                    order["gift_error_trace"] = tb[-1200:]
                    db.save()
                    log.error(
                        "Gift yuborishda xato (%d/%d) [bosqich: %s]: %s\n%s",
                        last_err, GIFT_MAX_ATTEMPTS, stage, exc, tb,
                    )
                    diag = (
                        f"\n🧩 <b>Bosqich:</b> <code>{esc(stage)}</code>"
                        f"\n📍 <code>{esc(_shortest_frame(tb))}</code>"
                        f"\n<code>{esc(tb[-500:])}</code>"
                    )
                    if internal:
                        # Ichki xato: buyurtma YOPILMAYDI — keyingi siklda
                        # qayta urinishiladi. Eng ko'p uchraydigan sabab —
                        # mijozning (yoki Telegram'ning) holati vaqtincha
                        # noto'g'ri; keyingi urinishda o'zi tuziladi.
                        order["gift_needs_review"] = True
                        INTERNAL_GIFT_ERRORS_SEEN["n"] += 1
                        # Har 5 ta ichki xatodan keyin ro'yxatni yangilaymiz
                        # (eskirgan ma'lumot bo'lib qolmasin)
                        if INTERNAL_GIFT_ERRORS_SEEN["n"] % 5 == 1:
                            try:
                                await gclient.get_available_gifts()
                            except Exception:  # noqa: BLE001
                                pass
                        db.save()
                        if last_err == 1:
                            await notify_admins(
                                f"⚠️ Gift <code>#{order['id']}</code> yuborishda "
                                f"<b>dasturiy xato</b> (mijozning gunohi emas).\n"
                                f"🔍 Sabab: <code>{esc(str(exc)[:180])}</code>{diag}\n\n"
                                f"🤖 Avtomatik qayta urinish davom etadi. "
                                f"Agar takrorlansa — <code>/admin → 🎁 Gift qayta yuborish</code>."
                            )
                    elif last_err >= GIFT_MAX_ATTEMPTS:
                        order["gift_failed"] = True
                        db.save()
                        await notify_admins(
                            f"🛑 <b>Gift yuborilmadi — urinishlar tugadi</b>\n\n"
                            f"📦 Buyurtma: <code>#{order['id']}</code>\n"
                            f"🎁 Sovg'a: {esc(str(order.get('title', gift_key)))}\n"
                            f"👤 Qabul qiluvchi: <b>@{esc(recipient)}</b>\n"
                            f"🔍 Sabab: <code>{esc(str(exc)[:200])}</code>{diag}\n\n"
                            f"<i>Qo'lda yuborishingiz yoki buyurtmani bekor qilishingiz kerak.</i>"
                        )
                    else:
                        await notify_admins(
                            f"❌ Gift <code>#{order['id']}</code> yuborishda xato "
                            f"({last_err}/{GIFT_MAX_ATTEMPTS}): {esc(str(exc)[:150])}"
                            + (diag if last_err >= 2 else "")
                        )
            # --- QISQARIB QOLGAN gift'lar: mijozni kutayotiriz, u bilmaydi ---
            # Sabablari: urinish limiti (5), noto'g'ri qabul qiluvchi,
            # yoki status "completed" emas. Bu holda xabar YUBORILMAYDI va
            # mijoz hech narsani bilmaydi — biz esa "ishlayapti" deb o'ylaymiz.
            stuck = [
                o for o in db.data.get("orders", {}).values()
                if o.get("kind") == "gift"
                and not o.get("gift_sent")
                and not o.get("gift_processing")
            ]
            n_stuck = len(stuck)
            now = time.time()
            if n_stuck and now - stuck_notified_at > 300:
                stuck_notified_at = now
                reasons: dict[str, int] = {}
                for o in stuck:
                    if o.get("gift_failed"):
                        r = "urishlar tugagan"
                    elif int(o.get("gift_attempts", 0)) >= GIFT_MAX_ATTEMPTS:
                        r = "urish limiti"
                    elif not normalize_gift_recipient(o.get("recipient")):
                        r = "noto'g'ri qabul qiluvchi"
                    elif o.get("status") not in ("completed", "pending_admin", "processing"):
                        r = f"holat={o.get('status')}"
                    else:
                        r = "kutilmoqda"
                    reasons[r] = reasons.get(r, 0) + 1
                set_runtime_status(gift_stuck=n_stuck)
                log.warning("🎁 Yuborilmagan gift buyurtmalari: %d (%s)",
                            n_stuck, ", ".join(f"{k}: {v}" for k, v in reasons.items()))
                await notify_admins(
                    f"⏳ <b>{n_stuck} ta gift buyurtmasi yuborilmayapti</b>\n\n"
                    + "\n".join(f"• {esc(k)}: <b>{v}</b>" for k, v in reasons.items())
                    + "\n\n🔧 <i>/admin → 🎁 Gift qayta yuborish — ro'yxat va "
                    "qayta urinish tugmasi.</i>"
                )
            elif not n_stuck:
                set_runtime_status(gift_stuck=0)

            # Holatni bazaga yozamiz — /api/health da ko'rinadi
            pending_now = sum(
                1 for o in db.data.get("orders", {}).values()
                if o.get("kind") == "gift" and not o.get("gift_sent")
            )
            sent_now = sum(
                1 for o in db.data.get("orders", {}).values() if o.get("gift_sent")
            )
            if pending_now != last_pending or not last_written:
                set_runtime_status(
                    gift_worker="running", gift_pending=pending_now, gift_sent=sent_now
                )
                last_pending, last_written = pending_now, True
        except Exception as exc:  # noqa: BLE001
            log.error("process_gift_orders xato: %s", exc)
            await asyncio.sleep(5)


def userbot_diagnose() -> list[str]:
    """Userbot ishlashiga nima to'sqinlik qilayotganini aniq ko'rsatadi."""
    # Eslatma: f-string ichida apostrof yoki backslash ishlatmang —
    # Python 3.11 (Railway) buni SYNTAX ERROR beradi va bot umuman ishlamaydi.
    yes = "✅"
    no = "❌"
    set_txt = "to‘ldirilgan"
    missing_txt = "YO‘Q"

    lines = ["🩺 <b>Userbot diagnostikasi</b>\n"]
    lines.append(f"{yes if API_ID else no} API_ID: {set_txt if API_ID else missing_txt}")
    lines.append(f"{yes if API_HASH else no} API_HASH: {set_txt if API_HASH else missing_txt}")

    has_session = bool(SESSION_STRING and len(SESSION_STRING) > 20)
    session_txt = f"{set_txt} ({len(SESSION_STRING)} belgi)" if has_session else missing_txt
    lines.append(f"{yes if has_session else no} SESSION_STRING: {session_txt}")

    return lines


# Eski (ikki-userbot) rejimdan qolgan kalitlar — chalkashtiradi va
# eskirgan ma'lumot ko'rsatadi. Yangi rejimda ular kerak emas.
STALE_RUNTIME_KEYS = ("gift_userbot", "gift_account", "gift_error")


def purge_stale_runtime() -> int:
    """Runtime holatidan eski kalitlarni olib tashlaydi."""
    settings = db.data.setdefault("settings", {})
    rt = settings.get("runtime") or {}
    dead = [k for k in STALE_RUNTIME_KEYS if k in rt]
    if not dead:
        return 0
    for k in dead:
        rt.pop(k, None)
    settings["runtime"] = rt
    db.save()
    log.info("🧹 Runtime dan esriган kalitlar tozalandi: %s", ", ".join(dead))
    return len(dead)


def set_runtime_status(**kwargs: Any) -> None:
    """Botning ish vaqtidagi holatini bazaga yozadi.

    server.ts /api/health shu ma'lumotni o'qib, Railway loglariga
    kirishsiz userbot va worker holatini ko'rsatadi.

    MUHIM: bu funksiya HECH QACHON xato bermasligi kerak — u main()
    ichida chaqiriladi va xatosi butun botni to'xtatib qo'yadi
    (polling umuman boshlanmaydi). Shuning uchun try/except bilan
    o'ralgan: diagnostika yozilmasa ham bot ishlashda davom etadi.
    """
    try:
        settings = db.data.setdefault("settings", {})
        # DIQQAT 1: **str UNPACK qilinmaydi (TypeError).
        # DIQQAT 2: runtime MELDAN qilinadi (merge), almashtirilmaydi — aks holda
        # heartbeat (har 20 soniyada) userbot/gift holatlarini o'chirib qo'yadi
        # va /api/health da ko'rinmaydi.
        prev = settings.get("runtime") or {}
        settings["runtime"] = {**prev, **kwargs, "at": datetime.now(TZ).isoformat()}
        db.save()
    except Exception as exc:  # noqa: BLE001
        log.debug("runtime holatini yozib bo'lmadi: %s", exc)


# Polling ishlayotganini isbotlash uchun update hisoblagichi
UPDATES_RECEIVED = {"count": 0, "last_at": None}


async def update_heartbeat() -> None:
    """Har 20 soniyada runtime holatini yangilaydi.

    /api/health dagi `updates` maydoni orqali polling ishlayotganini
    aniq ko'rish mumkin: soni oshsa — update'lar kelmoqda.
    """
    while True:
        try:
            await asyncio.sleep(20)
            last = UPDATES_RECEIVED["last_at"]
            set_runtime_status(
                bot="polling",
                updates=UPDATES_RECEIVED["count"],
                last_update_at=last,
                last_update_ago_sec=(int(time.time() - last) if last else None),
            )
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            pass


class UpdateCounterMiddleware(BaseMiddleware):
    """Har bir kelgan update'ni hisoblaydi (polling ishlayotganini isbotlash uchun)."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        UPDATES_RECEIVED["count"] += 1
        UPDATES_RECEIVED["last_at"] = time.time()
        return await handler(event, data)


def recover_stuck_gifts() -> int:
    """Bizning xatomiz tufayli yutilgan gift buyurtmalarini tiklaydi.

    MUAMMO: avvalgi versiyalarda ichki (dasturiy) xatolar — masalan
    "object of type 'NoneType' has no len()" — urinishlar limitiga
    yetib buyurtmani "muvaffaqiyatsiz" deb YOPARDI. Mijoz pulini
    to'lab giftini olmay qolardi va hech kim sababni ko'rmaydi.

    Endi: userbot ulanganda bunday buyurtmalar avtomatik qayta
    urinishga qo'yiladi. Mijozning GUNAOHI bo'lmagan xatolar uchun
    urinish limiti qo'llanilmasligi to'g'ri.

    Qaytaradi: tiklangan buyurtmalar soni.
    """
    recovered = 0
    for o in db.data.get("orders", {}).values():
        if o.get("kind") != "gift" or o.get("gift_sent"):
            continue
        internal = bool(o.get("gift_needs_review"))
        if not internal:
            # Eski yozuvlar: xato matni ichki xatoga ishora qiladi
            err = str(o.get("gift_error") or "")
            internal = any(
                k in err for k in (
                    "NoneType", "TypeError", "AttributeError", "has no len",
                    "not subscriptable", "unhashable", "object of type",
                )
            )
        if not internal:
            continue
        o["gift_attempts"] = 0
        o["gift_failed"] = False
        o["gift_processing"] = False
        o.pop("gift_processing_at", None)
        o.pop("gift_needs_review", None)
        o.pop("gift_error", None)
        o.pop("gift_error_stage", None)
        o.pop("gift_error_trace", None)
        recovered += 1
    if recovered:
        db.save()
        log.info("🎁 %d ta yutilgan gift buyurtmasi tiklandi (ichki xato sababli)", recovered)
    return recovered


def session_error_kind(exc: BaseException) -> str:
    """Session bilan bog'liq xatoni TUR bo'yicha aniqlaydi.

    Nima uchun kerak: "Userbot ishga tushmadi — SESSION_STRING muddati
    tuggan" degan umumiy xabar administratorga NIMANI qilish kerakligini
    aytmaydi. "401 AUTH_KEY_UNERGISTERED" (kalit bekor qilingan) bilan
    "tarmoq uzildi" butunlay boshqa narsa — birinchisini faqat telefon
    bilan qayta ulash tuzatadi.

    Qaytaradi: "auth_key_unregistered" | "session_revoked" |
               "account_blocked" | "network" | ""
    """
    txt = str(exc).upper()
    name = type(exc).__name__.lower()
    if "AUTH_KEY_UNREGISTERED" in txt or "AUTH_KEY_INVALID" in txt:
        return "auth_key_unregistered"
    if "SESSION_REVOKED" in txt or "SESSION_EXPIRED" in txt:
        return "session_revoked"
    if "USER_DEACTIVATED" in txt or "USER_BANNED" in txt:
        return "account_blocked"
    if any(k in txt or k in name for k in (
        "TIMEOUT", "CONNECTION", "NETWORK", "FLOOD", "SERVER", "UNAVAILABLE",
    )):
        return "network"
    return ""


SESSION_ERROR_HELP: dict[str, str] = {
    "auth_key_unregistered": (
        "\n\n<b>🔍 Bu nima degani?</b>\n"
        "Telegram shu sessiya kalitini BUTUNLAY o'chirib qo'ygan "
        "(AUTH_KEY_UNREGISTERED). Bu \"muddat tugdi\" emas — kalit "
        "bekor qilingan.\n\n"
        "<b>Sabablari:</b>\n"
        "• shu session boshqa joyda (kompyuter/server) ham ishlatilgan\n"
        "• Telegram faol ishlatilmagan sessiyalarni tozalagan\n\n"
        "<b>🔧 Yechim:</b> qayta telefon bilan ulash kerak —\n"
        "<code>/admin → 📱 Raqam bilan ulash</code>\n\n"
        "<i>Yangi session avtomatik bazaga saqlanadi — keyin qayta "
        "qilish shart bo'lmaydi.</i>"
    ),
    "session_revoked": (
        "\n\n<b>🔍 Bu nima degani?</b>\n"
        "Sessiya Telegram tomonidan bekor qilingan.\n\n"
        "<b>🔧 Yechim:</b> <code>/admin → 📱 Raqam bilan ulash</code>"
    ),
    "account_blocked": (
        "\n\n<b>🔍 Bu nima degani?</b>\n"
        "Akkaunt Telegram tomonidan bloklangan. Gift va balans "
        "avtomatik ishlash TO'XTAYDI."
    ),
    "network": (
        "\n\n<i>Tarmoq vaqtinchalik uzilib qolgan bo'lishi mumkin — "
        "avtomatik qayta ulanishga urilmoqda.</i>"
    ),
}


def maybe_start_userbot() -> None:
    global userbot
    missing = []
    # QAYTA QATIK: avval bazadagi (eng yangi) session, keyin Railway ENV.
    # Sabab: telefon/QR orqali ulangan yangi session bazada saqlanadi va
    # u har doim afzal — aks holda eski ENV qiymati qo'llanilib, yangisi
    # "eskirgan" bo'lib tuyulardi.
    session, source = resolve_session_string()
    if not session:
        missing.append("SESSION_STRING")
    elif source == "db":
        log.info("🔐 Session bazadan olinadi (Railway ENV ishlatilmaydi)")
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

    # Session formatini oldindan tekshiramiz — Pyrofork ichidagi
    # "unpack requires a buffer of 271 bytes" xatosi o'rniga aniq
    # va tuzatiladigan xabar beramiz.
    bank_valid, bank_why = diagnose_session_string(session)
    if not bank_valid:
        log.error("SESSION_STRING noto'g'ri: %s", bank_why.splitlines()[0])
        set_runtime_status(userbot="invalid_session", userbot_error=bank_why[:300])
        try:
            asyncio.get_running_loop().create_task(_notify_bad_session(bank_why))
        except RuntimeError:
            pass  # loop yo'q (import payti) — xabarsiz o'tamiz
        return

    async def _start() -> None:
        set_runtime_status(userbot="starting")
        try:
            ub = UserbotClient(
                "humo_userbot",
                api_id=API_ID,
                api_hash=API_HASH,
                session_string=session,
            )
            await ub.start()
            ub.add_handler(
                UbMessageHandler(on_humo_message, ub_filters.chat(TOPUP_SOURCE_CHAT))
            )
            userbot = ub
            # DIQQAT: start() muvaffaqiyatli bo'lishi kalitning
            # ro'yxatda borligini KAFAVATLAYDI. Kalit bekor qilingan
            # bo'lsa (AUTH_KEY_UNREGISTERED), xato FAQAT keyingi
            # chaqiruvda — masalan get_me() yoki bank xabarini
            # kuzatishda — chiqadi va gift yuborish ham to'xtaydi.
            # Shuning uchun ULANGANDAN KEYIN darhol tekshiramiz.
            try:
                me = await asyncio.wait_for(ub.get_me(), timeout=25)
                who = f"@{me.username}" if me.username else str(me.id)
            except Exception as exc:  # noqa: BLE001
                kind = session_error_kind(exc)
                log.error("Userbot ulandi, lekin kalit ishlashdan "
                          "bekor qilingan [%s]: %s", kind or "noma'lum", exc)
                try:
                    await ub.stop()
                except Exception:  # noqa: BLE001
                    pass
                userbot = None
                set_runtime_status(
                    userbot="error", error=str(exc)[:300],
                    error_kind=kind or "unknown",
                    gift_worker="blocked_userbot_offline" if kind else "degraded",
                )
                pend = sum(
                    1 for o in db.data.get("orders", {}).values()
                    if o.get("kind") == "gift" and not o.get("gift_sent")
                )
                await notify_admins(
                    "🛑 <b>Sessiya kaliti Telegram tomonidan bekor qilingan</b>\n\n"
                    f"🔍 Sabab: <code>{esc(str(exc)[:200])}</code>"
                    + SESSION_ERROR_HELP.get(kind, "")
                    + (f"\n\n📦 Kutayotgan gift buyurtmalari: <b>{pend}</b>"
                       if pend else "")
                )
                return
            log.info("👤 Userbot ishga tushdi (%s), bank xabarlari kuzatilmoqda...", who)
            set_runtime_status(userbot="connected", account=who, chat=str(TOPUP_SOURCE_CHAT))
            asyncio.create_task(ub_idle())
            # Bizning xatomiz tufayli yutilgan gift'larni tikla
            n_rec = recover_stuck_gifts()
            if n_rec:
                await notify_admins(
                    f"♻️ <b>{n_rec} ta gift buyurtmasi tiklandi</b>\n\n"
                    "🔍 Ularga noto'g'ri ravishda \"muvaffaqiyatsiz\" deb belgi "
                    "qo'yilgan edi (dasturiy xato sababli, mijozning gunohi emas).\n"
                    "🤖 Endi ular avtomatik qayta yuboriladi."
                )
        except Exception as exc:  # noqa: BLE001
            kind = session_error_kind(exc)
            log.error("Userbot ishga tushmadi [%s]: %s", kind or "noma'lum", exc)
            set_runtime_status(
                userbot="error", error=str(exc)[:300], error_kind=kind or "unknown",
                # Gift worker "running" ko'rinib, ammo yuborilmay qolmasligi
                # mumkin — admin buni aniq bilishi kerak.
                gift_worker="blocked_userbot_offline" if kind else "degraded",
            )
            need_relogin = kind in ("auth_key_unregistered", "session_revoked",
                                    "account_blocked")
            pending = sum(
                1 for o in db.data.get("orders", {}).values()
                if o.get("kind") == "gift" and not o.get("gift_sent")
            )
            head = (
                "🛑 <b>Userbot ulanmadi — balans va gift ISHLAMAYDI</b>"
                if need_relogin else
                "⚠️ <b>Userbot ishga tushmadi</b>"
            )
            tail = (
                f"\n\n📦 Kutayotgan gift buyurtmalari: <b>{pending}</b> "
                "(ular HECH qachon yuborilmaydi)"
                if pending else ""
            )
            await notify_admins(
                f"{head}\n\n"
                f"🔍 Sabab: <code>{esc(str(exc)[:200])}</code>"
                + SESSION_ERROR_HELP.get(kind, "")
                + tail
            )

    asyncio.create_task(_start())


async def userbot_supervisor() -> None:
    """Userbot uzilib qolsa yoki ishga tushmasa — qayta ulash.

    AVVAL: userbot bir marta ishga tushsa, uzilib qolsa ham butunlay
    o'lib qolardi — avto to'ldirish va gift butunlay to'xtardi.
    Endi: har 60 soniyada tekshiriladi va kerak bo'lsa qayta ulanadi.
    """
    log.info("🔄 Userbot supervisor ishga tushdi (avto qayta ulash)")
    retries = 0
    while True:
        try:
            await asyncio.sleep(60)
            if userbot is not None and getattr(userbot, "is_connected", False):
                retries = 0
                continue
            if not (API_ID and API_HASH):
                continue
            retries += 1
            # Kalit Telegram tomonidan BEKOR QILINGAN bo'lsa (401
            # AUTH_KEY_UNREGISTERED) — qayta urinish 100 marta ham
            # natija bermaydi, faqat xato spam qiladi. Shu sabab
            # urinishni to'xtatamiz va faqat ADMINGA yo'naltiramiz.
            rt_kind = str((db.data.get("settings", {}).get("runtime", {}) or {})
                          .get("error_kind") or "")
            if rt_kind in ("auth_key_unregistered", "session_revoked",
                           "account_blocked"):
                if retries in (2, 8):
                    log.error("Userbot: sessiya kaliti bekor qilingan "
                              "(%s) — qayta urinish to'xtatildi", rt_kind)
                    await notify_admins(
                        "🛑 <b>Sessiya kaliti bekor qilingan — "
                        "qayta urinishning ma'nosi yo'q</b>\n\n"
                        "🔧 <b>Yechim:</b> <code>/admin → 📱 Raqam bilan ulash</code>\n"
                        "<i>Yangi session avtomatik saqlanadi — Railway ENV "
                        "kerak bo'lmaydi.</i>"
                    )
                set_runtime_status(gift_worker="blocked_session_revoked")
                continue
            if retries > 10:
                if retries == 11:
                    log.error("Userbot 10 marta urinishdan keyin ham ulanmadi — to'xtatildi")
                    await notify_admins(
                        "🛑 <b>Userbot umuman ulanmayapti</b>\n\n"
                        "🔍 Sabah ehtimoli: tarmoq uzilib qolyapti.\n"
                        "🔧 <i>/admin → 🩺 Userbot holati</i>"
                    )
                continue
            log.warning("Userbot ulanmagan — %d-urinish (avto qayta ulanmoqda)...", retries)
            set_runtime_status(userbot="reconnecting", attempt=retries)
            try:
                maybe_start_userbot()
                # ulanishga vaqt beramiz
                for _ in range(20):
                    await asyncio.sleep(3)
                    if userbot is not None:
                        break
            except Exception as exc:  # noqa: BLE001
                log.warning("Qayta ulashda xato: %s", exc)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            log.warning("userbot_supervisor xato: %s", exc)

    asyncio.create_task(_start())


def order_is_anonymous(order: dict) -> bool:
    """Buyurtma anonim yuboriladimi? (True = anonim)

    Telegram MTProto: InputInvoiceStarGift.hide_name = flags.0?true
        hide_my_name=True  -> yuboruvchi nomi YASHIRILADI (anonim)
        hide_my_name=False -> yuboruvchi profili KO'RINADI

    DIQQAT: bu qiymatni HECH QACHON teskari aylantirmaslik kerak.
    Ma'lumot bazasida aniq semantika saqlanadi: "anon" = True -> anonim.
    Eski buyurtmalar uchun "hide_my_name" maydoni ham o'qiladi
    (u ham xuddi shu qiymatni saqlagan), shuning uchun ular ham to'g'ri ishlaydi.
    """
    if "anon" in order:
        return bool(order["anon"])
    return bool(order.get("hide_my_name", True))


# Gift yuborishning qaysi bosqichi xatolashganini kuzatish uchun.
# "object of type 'NoneType' has no len()" kabi xatolar QAYERDA sodir
# bo'lganini aytmaydi — shuning uchun har bosqichga nom qo'yamiz va
# xatoni ushlaganimizda shu nomni xabarda ko'rsatamiz.
# ContextVar kerak: worker bitta task da yuradi, lekin .get() argumentisiz
# chaqirilishi uchun an'lanadi (oddiy dict.is() TypeError berardi).
_gift_stage = contextvars.ContextVar("gift_stage", default="")


def _stage(name: str) -> None:
    _gift_stage.set(name)


def _shortest_frame(tb: str) -> str:
    """Traceback'dan ENG QISQA fayl/qator ko'rsatadi (odatda asil sabab)."""
    lines = [ln.strip() for ln in tb.splitlines() if ln.strip().startswith("File ")]
    return lines[-1] if lines else "noma'lum"


# Gift yuborishdagi xatolarni ikki turga ajratamiz:
#
#  DOIMIY (mijozga bog'liq) — qayta urinish foyda bermaydi:
#    - username topilmadi / noto'g'ri
#    - Stars yetarli emas
#    - Telegram "gift is not available"
#  Bu xatolar bilan urinishlar SONLANADI (mijozga darhol xabar beriladi).
#
#  ICHKI (dasturiy/tarmoq) — qayta urinish foyda BO'LADI:
#    - TypeError, AttributeError (masalan "NoneType has no len()")
#    - Timeout, ConnectionError, flood kutish
#  Bu xatolar mijozning gunohi emas — ular avtomatik tiklanadi va
#  buyurtma "muvaffaqiyatsiz" deb YOPILMAYDI (faqat urinishlar soni
#  chiqib ketsa, maxsus "gift_needs_review" belgisi qo'yiladi).
INTERNAL_GIFT_ERRORS = (
    TypeError, AttributeError, IndexError, KeyError, ValueError,
    TimeoutError, ConnectionError, OSError,
)


# Ichki xatolar sanaladi (diagnostika uchun /api/health da ko'rinadi)
INTERNAL_GIFT_ERRORS_SEEN = {"n": 0}


def is_internal_gift_error(exc: BaseException) -> bool:
    """Xato dasturiy/tarmoq xarakterida mi?"""
    if isinstance(exc, INTERNAL_GIFT_ERRORS):
        return True
    name = type(exc).__name__
    return any(
        k in name for k in (
            "Timeout", "Connection", "Network", "Flood", "Server", "Timeout",
            "Internal", "ServiceUnavailable",
        )
    )


def normalize_gift_recipient(raw: Any) -> str:
    """Qabul qiluvchini tozalaydi.

    Mijoz kiritgan shakl bo'lishi mumkin:
        @bobur | bobur | https://t.me/bobur | t.me/bobur | t.me/bobur/
        "bobur " (ortida bo'sh joy)
    Hammasi bir xil ishlashi uchun bitta ko'rinishga keltiramiz —
    aks holda "https://t.me/bobur" Telegram'da topilib olmaydi.
    """
    t = str(raw or "").strip()
    t = re.sub(r"^(?:https?://)?(?:t|telegram)\.(?:me|dog)/", "", t, flags=re.I)
    t = re.sub(r"^@+", "", t).strip().rstrip("/")
    t = "".join(ch for ch in t if ch.isalnum() or ch == "_")
    return t[:32]


def gift_sticker_emoji(g: Any) -> str:
    """Telegram Gift obyektidan sticker emojisini oladi."""
    return str(getattr(getattr(g, "sticker", None), "emoji", "") or "")


def find_gift(gifts: list[Any], gift_key: str, stars: int) -> Optional[Any]:
    """Berilgan sovg'ani Telegram ro'yxatidan topadi.

    MUHIM: bir necha sovg'a bir xil narxda (Ayiqcha va Yurakcha ikkalasi
    ham 15 ⭐). Faqat `price` bo'yicha solishtirilsa, ro'yxatdagi birinchi
    mos kelgani doim tanlanadi va mijoz har doim YURAKCHA oladi.
    Shuning uchun tartib:
      1) EMOSI bo'yicha (aniq moslik)      — asosiy usul
      2) nom/slug bo'yicha (zaxira)
      3) narx bo'yicha (oxirgi zaxira)
    """
    if not gifts:
        return None

    want_emoji = GIFT_EMOJI.get(gift_key, "")

    # 1) Emosi bo'yicha
    if want_emoji:
        for g in gifts:
            if gift_sticker_emoji(g) == want_emoji:
                return g
        # Telegram ba'zan boshqa skin tone yoki skin variantini qaytaradi
        # (🧸 vs 🧸🏻). Asosiy emosini olsak yetarli.
        for g in gifts:
            e = gift_sticker_emoji(g)
            if e and want_emoji in e:
                return g

    # 2) Nomi bo'yicha
    for g in gifts:
        name = str(getattr(g, "name", "") or getattr(g, "title", "") or "").lower()
        if name and (name == gift_key or name.replace(" ", "_") == gift_key):
            return g

    # 3) Narx bo'yicha (oxirgi zaxira)
    if stars:
        return next((g for g in gifts if getattr(g, "price", 0) == stars), None)
    return None


def expire_stale_topups() -> int:
    """Muddati o'tgan so'rovlarni "expired" deb belgilaydi.

    Nima uchun kerak: eski kodda muddatni faqat `on_humo_message`
    (bank xabari kelganda) tekszirdi. Mijoz bankdan to'lamasa yoki
    xato kiritsa, so'rov "pending" holatida ABADIY qolardi va mijozga
    "Sizda faol so'rov bor" deb ko'rinib turardi — qolgan vaqt 0:00,
    lekin bekor qilish tugmasi ishlamasdi.
    """
    now = now_ms()
    n = 0
    for t in db.data.get("topups", {}).values():
        if t.get("status") != "pending":
            continue
        exp = to_ms(t.get("expires_at"), 0)
        if exp and exp < now:
            t["status"] = "expired"
            t["expired_at"] = now_iso()
            n += 1
    if n:
        db.save()
        log.info("⏰ %d ta to'lov so'rovi muddati tugagani uchun yopildi", n)
    return n


def pending_topups() -> list[dict]:
    """Faol (kutilayotgan) to'lov so'rovlari.

    DIQQAT: avval faqat `status == "pending"` tekshirilardi — muddati
    o'tgan so'rovlar ham "faol" chiqardi (qolgan vaqt 0:00, bekor qilish
    tugmasi ishlamaydi). Endi avval eskirganlarni tozalaymiz.
    """
    expire_stale_topups()
    now = now_ms()
    return [
        t for t in db.data["topups"].values()
        if t.get("status") == "pending"
        and to_ms(t.get("expires_at"), now) > now
    ]


@router.message(F.text == BTN_GIFTS)
async def gifts_text(message: Message, state: FSMContext):
    await gifts_start(message, state)


@router.message(F.text == BTN_TOPUP)
async def topup_start(message: Message, state: FSMContext, db_user: dict):
    await state.clear()
    existing = next((t for t in pending_topups() if t["user_id"] == db_user["id"]), None)
    if existing:
        left = max(0, int((to_ms(existing.get("expires_at")) - now_ms()) // 1000))
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


def next_topup_seq() -> int:
    """To'lov so'rovi uchun ketma-ket raqam.

    Nima uchun: mijoz so'ragan summa + bu raqam = kartaga yuboriladigan
    summa. Masalan 1 000 so'm so'raydi, #39-so'rov bo'lsa ->
    1 039 so'm yuboradi. Shu bilan bir xil summali to'lovlar chalkashmaydi
    va userbot aniq qaysi mijoz ekanini aniqlaydi.
    """
    settings = db.data.setdefault("settings", {})
    n = int(num(settings.get("topup_seq"))) + 1
    settings["topup_seq"] = n
    return n


@router.message(StateFilter(TopupStates.amount), F.text, NOT_MENU)
async def topup_amount(message: Message, state: FSMContext, db_user: dict):
    amount = parse_uzs_amount(message.text)
    if amount is None or not (MIN_TOPUP <= amount <= MAX_TOPUP):
        await message.answer(f"⚠️ {fmt(MIN_TOPUP)} dan {fmt(MAX_TOPUP)} gacha summa kiriting.")
        return
    await state.clear()
    topup_id = new_id("t")
    seq = next_topup_seq()
    amount_to_send = amount + seq
    topup = {
        "id": topup_id,
        "user_id": db_user["id"],
        "amount": amount,                 # balansga SHU qo'shiladi
        "seq": seq,                       # ketma-ket raqam
        "amount_to_send": amount_to_send,  # kartaga yuborilishi kerak
        "status": "pending",
        "created_at": now_iso(),
        "expires_at": now_ms() + TOPUP_TIMEOUT_SEC * 1000,
    }
    db.data["topups"][topup_id] = topup
    db.save()

    await message.answer(
        f"💳 <b>To'lov ma'lumotlari</b>\n\n"
        f"Karta: <code>{CARD_NUMBER}</code>\n"
        f"Egasi: {esc(CARD_HOLDER)}\n\n"
        f"💰 <b>Kartaga yuboring:</b> <code>{fmt(amount_to_send)} UZS</code>\n"
        f"   <i>(so'ragan: {fmt(amount)} UZS · №{seq})</i>\n\n"
        f"⏱ <b>{TOPUP_TIMEOUT_SEC // 60} daqiqa</b> ichida o'tkazing.\n"
        f"⚠️ <i>Aynan {fmt(amount_to_send)} so'm yuboring — boshqa summa "
        f"avtomatik tanib bo'lmaydi.</i>",
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

    # Sovg'a yuborish va balans tekshiruvi BITTA akkaunt orqali amalga
    # oshiriladi — alohida gift akkaunti yo'q.
    lines.insert(2, "🎁 Sovg'a yuborish: <b>shu akkaunt orqali</b> (alohida emas)")

    await call.message.answer(
        f"🩺 Userbot holati: <b>{status}</b>\n\n" + "\n".join(lines),
        reply_markup=admin_back_kb(),
    )


# =============================================================================
# ADMIN: qurilmagan gift buyurtmalarini qayta yuborish
# =============================================================================
# =============================================================================
# ADMIN: GIFТ DIAGNOSTIKASI — nima uchun yuborilmayapti?
# =============================================================================
def gift_order_price(order: dict) -> int:
    """Gift buyurtmasining narxi (so'm)."""
    return num(order.get("price_uzs") or order.get("price") or 0)


def cancel_gift_order(order_id: str, refund: bool = True) -> tuple[bool, str]:
    """Kutilayotgan gift buyurtmasini bekor qiladi.

    Nima uchun: mijoz pulini to'lab sovg'a ololmagan bo'lsa, uni
    cheksiz kutayotgan qoldirish mumkin emas — bekor qilib pulni
    qaytarish to'g'ri. Aks holda mijoz nafaqat giftini, balki pulini
    ham yo'qotadi.

    Qaytaradi: (muvaffaqiyatmi?, xabar)
    """
    order = db.data.get("orders", {}).get(order_id)
    if not order:
        return False, "Buyurtma topilmadi"
    if order.get("kind") != "gift":
        return False, "Bu gift buyortmasi emas"
    # DIQQAT tartibi: bekor qilinganlikni OLDIN tekshiramiz, aks holda
    # "allaqachon yuborilgan" xabari chiqadi (biz esa o'zimiz belgilagan
    # gift_sent=True qiymati sababidan) — bu chalkash xabar bo'lardi.
    if order.get("gift_cancelled"):
        return False, "Allaqachon bekor qilingan"
    if order.get("gift_sent"):
        return False, "Gift allaqachon yuborilgan — bekor qilinmaydi"

    price = gift_order_price(order)

    # Worker bu buyurtmani qayta ushlab olmasin
    order["gift_sent"] = True          # skip qilish uchun "yuborilgan" belgisi
    order["gift_cancelled"] = True
    order["gift_processing"] = False
    order["status"] = "cancelled"
    order.pop("gift_processing_at", None)
    order.pop("gift_error", None)
    order.pop("gift_error_stage", None)
    order.pop("gift_error_trace", None)
    order.pop("gift_needs_review", None)
    order.pop("gift_failed", None)
    order["gift_attempts"] = 0

    refunded = 0
    if refund and price > 0:
        u = db.get_user(num(order.get("user_id")))
        if u is not None:
            u["balance"] = num(u.get("balance")) + price
            db.add_history(
                u, "refund", price,
                f"Gift bekor qilindi: {order.get('title') or order.get('gift')}",
            )
            refunded = price
    db.save()
    return True, (
        f"Pul qaytarildi: {fmt(refunded)} so'm" if refunded
        else "Pul qaytarilmadi (nomutanoshiblik yoki narx 0)"
    )


def stuck_gift_orders(older_than_days: Optional[float] = None) -> list[dict]:
    """Bekor qilinishi mumkin bo'lgan gift buyurtmalari.

    Yuborilmagan va hali bekor qilinmagan barcha gift'lar. Agar
    `older_than_days` berilgan bo'lsa — faqat shundan ESKINI.
    """
    out: list[dict] = []
    now = datetime.now(TZ)
    for o in db.data.get("orders", {}).values():
        if o.get("kind") != "gift" or o.get("gift_sent") or o.get("gift_cancelled"):
            continue
        if older_than_days is not None:
            raw = str(o.get("created_at") or o.get("date") or "")
            try:
                created = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                if created.tzinfo is None:
                    created = created.replace(tzinfo=TZ)
            except Exception:  # noqa: BLE001
                continue  # sanasi yo'q — "eski" deb hisoblamaymiz
            age = (now - created).total_seconds() / 86400
            if age < older_than_days:
                continue
        out.append(o)
    return out



@admin_router.callback_query(F.data == "adm:gift_diag")
async def adm_gift_diag(call: CallbackQuery):
    """Gift yuborilishining BARCHA bosqichlarini jonli tekshiradi.

    Nima uchun kerak: gift ishlamasa, sabab bir necha joyda bo'lishi
    mumkin (userbot ulanmagan, Stars yo'q, Telegram'da mos sovg'a yo'q,
    buyurtma noto'g'ri holatda). Bu tugma har birini alohida tekshiradi
    va aniq qatorni ko'rsatadi.
    """
    if not await _admin_guard(call):
        return
    await call.answer("🔍 Tekshirilyapti...")
    db.reload_if_changed()
    lines = ["🔎 <b>Gift diagnostikasi</b>\n"]

    # 1) Userbot
    rt = db.data.get("settings", {}).get("runtime", {}) or {}
    kind = str(rt.get("error_kind") or "")
    if userbot is None or not getattr(userbot, "is_connected", False):
        lines.append("❌ <b>Userbot ulanmagan</b> — gift yuborilmaydi\n")
        if kind and kind in SESSION_ERROR_HELP:
            lines.append("🧩 Sabab turi: <code>" + esc(kind) + "</code>\n")
            # Bu matn allaqachon HTML teglari bilan yozilgan
            lines.append(SESSION_ERROR_HELP.get(kind, ""))
        elif rt.get("error"):
            lines.append(f"🔍 <code>{esc(str(rt.get('error'))[:180])}</code>\n")
        lines.append("\n🔧 <b>Yechim:</b> <code>/admin → 📱 Raqam bilan ulash</code>")
        lines.append("\n<i>Yangi session avtomatik saqlanadi.</i>")
        await call.message.answer("\n".join(lines), reply_markup=admin_back_kb())
        return
    lines.append("✅ Userbot ulangan\n")

    # 2) Telegram'da mavjud sovg'alar
    try:
        gifts = await userbot.get_available_gifts()
        lines.append(f"✅ Telegram'da <b>{len(gifts)}</b> ta sovg'a mavjud\n")
        seen: list[str] = []
        for g in gifts[:14]:
            e = getattr(getattr(g, "sticker", None), "emoji", "?")
            seen.append(f"{e} {getattr(g, 'price', '?')}⭐")
        lines.append("🔍 <code>" + esc(", ".join(seen)) + "</code>\n")
    except Exception as exc:  # noqa: BLE001
        lines.append(
            f"❌ <b>Sovg'alar ro'yxatini olib bo'lmadi</b>\n"
            f"<code>{esc(str(exc)[:200])}</code>\n"
            "🔧 <i>Ko'pincha akkauntda Stars yo'q yoki Telegram vaqtinchalik "
            "javob bermayapti.</i>"
        )
        await call.message.answer("\n".join(lines), reply_markup=admin_back_kb())
        return

    # 3) Bizning sovg'alarimiz Telegram'da bormi?
    missing = [g[4] for g in GIFTS if not any(
        gift_sticker_emoji(x) == g[4] for x in gifts
    )]
    if missing:
        lines.append(
            "⚠️ Telegram'da topilmagan sovg'alar: <b>"
            + esc(" ".join(missing))
            + "</b>\n<i>(ular narx bo'yicha zaxira sifatida yuboriladi)</i>\n"
        )
    else:
        lines.append("✅ Barcha sovg'alar Telegram'da topildi\n")

    # 4) Kutayotgan buyurtmalar va ularning holati
    pend = [o for o in db.data.get("orders", {}).values()
            if o.get("kind") == "gift" and not o.get("gift_sent")]
    lines.append(f"📦 Kutayotgan buyurtmalar: <b>{len(pend)}</b>\n")
    reasons: dict[str, int] = {}
    for o in pend:
        if o.get("gift_failed"):
            r = "🛑 urishlar tugagan"
        elif o.get("gift_processing"):
            r = "⏳ yuborilmoqda"
        elif int(o.get("gift_attempts", 0)) >= GIFT_MAX_ATTEMPTS:
            r = "⛔ urish limiti"
        elif not normalize_gift_recipient(o.get("recipient")):
            r = "⚠️ noto'g'ri qabul qiluvchi"
        elif o.get("status") not in ("completed", "pending_admin", "processing"):
            r = f"⚠️ holat={o.get('status')}"
        elif not (o.get("gift") or o.get("gift_key")):
            r = "⚠️ sovg'a turi ko'rsatilmagan"
        else:
            r = "✅ kutilmoqda"
        reasons[r] = reasons.get(r, 0) + 1
    for k, v in reasons.items():
        lines.append(f"  {k}: <b>{v}</b>")
    last = next(
        (o for o in reversed(list(db.data.get("orders", {}).values()))
         if o.get("kind") == "gift" and o.get("gift_error")),
        None,
    )
    if last:
        lines.append(
            f"\n🕐 Oxirgi xato: <code>{esc(str(last.get('gift_error'))[:160])}</code>"
        )
        stage = last.get("gift_error_stage")
        if stage:
            lines.append(f"🧩 Bosqich: <code>{esc(str(stage))}</code>")

    await call.message.answer(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="♻️ Qayta yuborish", callback_data="adm:gift_retry"),
            InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm:home"),
        ]]),
    )


@admin_router.callback_query(F.data == "adm:gift_retry")
async def adm_gift_retry(call: CallbackQuery):
    """Yuborilmagan / muvaffaqiyatsiz bo'lgan gift'larni ro'yxatlaydi.

    Ichiyki xato (masalan "NoneType has no len()") bo'lsa, buyurtma
    avtomatik yopilMAYdi — shu yerda ko'rib, qayta urinishni
    qo'lda ham boshlash mumkin.
    """
    if not await _admin_guard(call):
        return
    await call.answer("🔎 Qidirilyapti...")
    db.reload_if_changed()
    stuck = [
        o for o in db.data.get("orders", {}).values()
        if o.get("kind") == "gift"
        and not o.get("gift_sent")
        and (o.get("gift_failed") or o.get("gift_error") or o.get("gift_needs_review"))
    ]
    if not stuck:
        await call.message.answer(
            "✅ <b>Muammo yo'q</b> — yuborilmagan gift buyurtmasi topilmadi.",
            reply_markup=admin_back_kb(),
        )
        return
    log.info("🎁 Kutilayotgan gift'lar: %d", len(stuck))

    lines = [
        "🎁 <b>Yuborilmagan gift'lar</b>\n",
    ]
    buttons: list[list[Any]] = []
    row: list[Any] = []
    for o in stuck[-12:]:
        st = ("🛑 urishlar tugagan" if o.get("gift_failed")
              else "🧩 ichki xato" if o.get("gift_needs_review")
              else "⏳ kutilmoqda")
        lines.append(
            f"\n📦 <code>{esc(str(o.get('id')))}</code> — "
            f"{esc(str(o.get('title') or o.get('gift')))} "
            f"→ <b>@{esc(str(o.get('recipient')))}</b>\n"
            f"   holat: {st} · urinish: {o.get('gift_attempts', 0)}/"
            f"{GIFT_MAX_ATTEMPTS}\n"
            f"   xato: <code>{esc(str(o.get('gift_error') or '—')[:120])}</code>"
        )
        row.append(InlineKeyboardButton(
            text=f"♻️ {str(o.get('id'))[-6:]}",
            callback_data=f"adm:gift_retry_one:{o.get('id')}",
        ))
        row.append(InlineKeyboardButton(
            text=f"❌ {str(o.get('id'))[-6:]}",
            callback_data=f"adm:gift_drop:{o.get('id')}",
            style="danger",
        ))
        if len(row) >= 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    # Bekor qilish. XAVFLI amal — avval tasdiq so'raladi va mijozning
    # puli QAYTARILADI (u hech qanday sababsiz pulini yo'qotmasin).
    if len(stuck) > 1:
        buttons.append([
            InlineKeyboardButton(
                text="📅 Faqat 30+ kundikini bekor qilish",
                callback_data="adm:gift_cancel:old",
                style="danger",
            ),
        ])
    buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm:home")])

    await call.message.answer(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),  # type: ignore[arg-type]
    )


# -----------------------------------------------------------------------------
# Bekor qilish — BITTA kirish nuqtasi
#
# MUHIM: callback_data formati DOIM "adm:gift_cancel:<amal>" bo'ladi
# (ikki nuqta). Eski versiya "adm:gift_cancel_" (ost chizig'i) bilan
# ro'yxatlagan edi, lekin tugma "adm:gift_cancel:..." yuborardi —
# shuning uchun tasdiqlash bosilganda HECH QANDAY handler mos kelmasdi
# va tugma jimgina qolardi.
#
# Amallar:
#   gone            → "🚫 Kutayotgan gift'larni bekor qilish" (admin menyu)
#   retry           → "♻️ Gift qayta yuborish" ro'yxatidan bosilganda
#   old             → faqat 30+ kundikini
#   confirm_all     → "✅ Ha, bekor qil" (barchasi)
#   confirm_old     → "✅ Ha, bekor qil" (30+ kundik)
# -----------------------------------------------------------------------------
GIFT_CANCEL_ACTIONS = {"gone", "retry", "old", "confirm_all", "confirm_old"}


@admin_router.callback_query(F.data.startswith("adm:gift_cancel"))
async def adm_gift_cancel(call: CallbackQuery):
    """Kutilayotgan gift'larni bekor qiladi (mijozga pul qaytariladi).

    XAVFLI amal — shuning uchun avval ro'yxat + summa ko'rsatiladi,
    keyin "Ha, bekor qil" bosilgandagina bajariladi.
    """
    if not await _admin_guard(call):
        return

    # action ni xavfsiz ajratamiz: "adm:gift_cancel:confirm_all" -> "confirm_all"
    parts = call.data.split(":")
    action = parts[2] if len(parts) > 2 else "retry"

    # Eski/bo'lishi mumkin bo'lgan formatlar
    if call.data == "adm:gift_cancel_gone":
        action = "gone"
    elif action not in GIFT_CANCEL_ACTIONS:
        action = "retry"

    db.reload_if_changed()

    # --- bajarish bosqichlari ---
    if action in ("confirm_all", "confirm_old"):
        targets = (
            stuck_gift_orders()
            if action == "confirm_all"
            else stuck_gift_orders(older_than_days=30)
        )
        label = "barcha" if action == "confirm_all" else "30+ kundik"
        if not targets:
            await call.answer("Bekor qilinadigan gift qolmadi", show_alert=True)
            await call.message.answer("✅ Qo'shimcha bekor qilinadigan gift qolmadi.")
            return
        done, refund_total, users = 0, 0, set()
        for o in targets:
            if cancel_gift_order(str(o.get("id")), refund=True)[0]:
                done += 1
                users.add(o.get("user_id"))
                refund_total += gift_order_price(o)
        db.save()
        await call.answer(f"✅ {done} ta gift bekor qilindi", show_alert=True)
        await call.message.answer(
            f"✅ <b>{done} ta gift bekor qilindi</b> ({esc(label)})\n\n"
            f"💳 Mijozlarga qaytarilgan: <b>{fmt(refund_total)} so'm</b>\n"
            f"👥 Foydalanuvchilar: <b>{len(users)}</b>",
            reply_markup=admin_back_kb(),
        )
        log.info("🎁 %d ta gift bekor qilindi, %s so'm qaytarildi",
                 done, fmt(refund_total))
        return

    # --- tasdiq so'rash ---
    preview = (
        stuck_gift_orders(older_than_days=30)
        if action == "old" else stuck_gift_orders()
    )
    if not preview:
        await call.answer("Bekor qilinadigan gift yo'q", show_alert=True)
        await call.message.answer(
            "✅ <b>Muammo yo'q</b> — yuborilmagan gift buyurtmasi topilmadi.",
            reply_markup=admin_back_kb(),
        )
        return

    total = sum(gift_order_price(o) for o in preview)
    confirm_cb = (
        "adm:gift_cancel:confirm_old" if action == "old"
        else "adm:gift_cancel:confirm_all"
    )
    await call.answer()
    await call.message.answer(
        "⚠️ <b>Ishonchingiz komilmi?</b>\n\n"
        f"📦 Bekor qilinadi: <b>{len(preview)}</b> ta gift\n"
        f"💳 Mijozlarga qaytariladi: <b>{fmt(total)} so'm</b>\n\n"
        "<i>Bekor qilingan buyurtmalar qaytarib bo'lmaydi "
        "(lekin pul har doim qaytariladi).</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Ha, bekor qil", callback_data=confirm_cb,
                                 style="danger"),
            InlineKeyboardButton(text="↩️ Bekor qilish",
                                 callback_data="adm:gift_retry", style="primary"),
        ]]),
    )


@admin_router.callback_query(F.data.startswith("adm:gift_drop:"))
async def adm_gift_cancel_one(call: CallbackQuery):
    """Bitta gift buyurtmasini bekor qiladi (puli qaytariladi)."""
    if not await _admin_guard(call):
        return
    await call.answer()
    db.reload_if_changed()
    order_id = call.data.split(":", 2)[2] if ":" in call.data[2:] else ""
    order = db.data.get("orders", {}).get(order_id)
    if not order:
        await call.message.answer("❌ Buyurtma topilmadi.")
        return
    okc, msg = cancel_gift_order(order_id, refund=True)
    price = gift_order_price(order)
    if not okc:
        await call.message.answer(f"❌ Bekor qilinmadi: {esc(msg)}")
        return
    await call.message.answer(
        f"✅ <b>Gift bekor qilindi</b>\n\n"
        f"📦 Buyurtma: <code>{esc(order_id)}</code>\n"
        f"🎁 {esc(str(order.get('title') or order.get('gift')))}\n"
        f"💳 {esc(msg)}",
        reply_markup=admin_back_kb(),
    )
    u = db.get_user(num(order.get("user_id")))
    if u is not None:
        await _safe_send(
            u["id"],
            "↩️ <b>Gift buyurtmangiz bekor qilindi</b>\n\n"
            f"🎁 {esc(str(order.get('title') or order.get('gift')))}\n"
            f"🆔 <code>{esc(order_id)}</code>\n"
            f"💳 Balansga qaytarildi: <b>{fmt(price)} so'm</b>\n\n"
            "<i>Xabar bering — yordam beraimiz.</i>",
        )


@admin_router.callback_query(F.data.startswith("adm:gift_retry_one:"))
async def adm_gift_retry_one(call: CallbackQuery):
    """Bitta buyurtmaning urinishlarini tozalaydi — worker qayta yuboradi."""
    if not await _admin_guard(call):
        return
    # DIQQAT: callback_data = "adm:gift_retry_one:<id>" — ikkiта ":" bor.
    # split(":", 1) -> ["adm", "gift_retry_one:<id>"] beradi va <id> OLINMAYDI
    # (buyurtma "Topilmadi" deb chiqadi). Shuning uchun ikkinchidan keyingini
    # olamiz.
    parts = call.data.split(":", 2)
    order_id = parts[2] if len(parts) > 2 else ""
    db.reload_if_changed()
    o = db.data.get("orders", {}).get(order_id)
    if not o:
        await call.answer("Topilmadi", show_alert=True)
        return
    o["gift_attempts"] = 0
    o["gift_failed"] = False
    o["gift_processing"] = False
    o.pop("gift_error", None)
    o.pop("gift_needs_review", None)
    o.pop("gift_error_trace", None)
    o.pop("gift_processing_at", None)
    db.save()
    await call.answer("♻️ Qayta urinishga qo'shildi", show_alert=True)
    await call.message.answer(
        f"♻️ <code>{esc(order_id)}</code> qayta urinishga qo'shildi.\n"
        f"⏳ Gift worker <b>{int(GIFT_POLL_INTERVAL)} soniya</b> ichida yana urinishadi.",
        reply_markup=admin_back_kb(),
    )


# =============================================================================
# ADMIN: NFT qo'shish va ro'yxat
# =============================================================================
@admin_router.callback_query(F.data == "adm:nft_add")
async def adm_nft_add(call: CallbackQuery, state: FSMContext):
    """NFT qo'shishni boshlaydi: link -> nom -> raqam -> kunlik narx."""
    if not await _admin_guard(call):
        return
    db.reload_if_changed()
    await call.answer()
    await state.set_state(NftStates.link)
    await call.message.answer(
        "🖼 <b>NFT qo'shish — 1/4</b>\n\n"
        "🔗 <b>NFT linkini</b> yuboring (t.me/nft/... yoki rasim havolasi).\n\n"
        "<i>Rasm havolasi bo'lsa (https://...) — WebApp'da shu rasm ko'rinadi. "
        "Agar link Telegram'dan bo'lsa, rasmni avval yuklab olib havolani yuboring.</i>",
        reply_markup=cancel_inline_kb("adm:nft_cancel"),
    )


@admin_router.message(StateFilter(NftStates.link), F.photo)
async def adm_nft_photo(message: Message, state: FSMContext):
    """Admin rasm yuborsa — eng katta o'lchamdagi fayl ID olinadi."""
    file_id = message.photo[-1].file_id
    data = await state.get_data()
    await state.set_state(NftStates.title)
    await message.answer(
        "🖼 <b>Rasm qabul qilindi</b>\n\n"
        "📝 <b>2/4</b> — NFT nomini yuboring (masalan: Jack-in-the-Box).\n\n"
        "<i>Rasm Telegram serverida saqlanadi. Bu o'rniga havolaviy rasm "
        "ishlatmoqchi bo'lsangiz /start ni bosing.</i>",
        reply_markup=cancel_inline_kb("adm:nft_cancel"),
    )
    await state.update_data(link=file_id, image=file_id, from_photo=True)


@admin_router.message(StateFilter(NftStates.link), F.text)
async def adm_nft_link(message: Message, state: FSMContext):
    link = (message.text or "").strip()
    if not re.match(r"^(https?://|tg://|t\.me/)", link, re.I):
        await message.answer("⚠️ Havola <code>https://...</code> ko'rinishida bo'lishi kerak.")
        return

    # 🔗 Telegram NFT sahifasi bo'lsa — rasmni O'ZIMIZ topamiz.
    # Sabab: `<img src="https://t.me/nft/...">` hech qachon rasm
    # ko'rsatmaydi (bu SPA sahifa, rasm FAQAT Telegram klientida
    # chiziladi). Lekin Telegram shu sahifa uchun server tomonda
    # `og:image` preview yaratadi — uni yuklab olamiz.
    auto: dict = {}
    if is_nft_page_url(link):
        status = await message.answer("🔍 <i>Rasm qidirilmoqda…</i>")
        auto = await resolve_nft_page(link) or {}
        try:
            await status.delete()
        except Exception:  # noqa: BLE001
            pass

    await state.set_state(NftStates.title)
    await state.update_data(
        link=link,
        image=auto.get("image") or link,
        from_photo=False,
        auto_title=auto.get("title") or "",
        auto_number=auto.get("number"),
        auto_desc=auto.get("description") or "",
    )

    if auto.get("image"):
        t = esc(auto.get("title") or "NFT")
        n = auto.get("number")
        await message.answer(
            "🔗 <b>Havola qabul qilindi</b>\n\n"
            f"🖼 Rasmi topildi: <b>{t}</b>" + (f" <code>#{n}</code>" if n else "") + "\n\n"
            + (f"📝 <b>2/4</b> — Nomni tasdiqlang yoki o'zgartiring:\n"
               f"    <code>{esc(auto.get('title') or '')}</code>\n\n"
               if auto.get("title") else
               "📝 <b>2/4</b> — NFT nomini yuboring (masalan: Jack-in-the-Box)."),
            reply_markup=cancel_inline_kb("adm:nft_cancel"),
        )
    else:
        await message.answer(
            "🔗 <b>Havola qabul qilindi</b>\n\n"
            "⚠️ <b>Rasm topilmadi.</b> Bu Telegram NFT sahifasi bo'lmasa yoki "
            "havolada <b>raqam</b> yo'q bo'lishi mumkin.\n"
            "   To'g'ri format: <code>https://t.me/nft/Nom-12345</code>\n\n"
            "📝 <b>2/4</b> — NFT nomini yuboring.\n"
            "   <i>Rasmni keyin 🖼 Rasm qo'shish orqali yubora olasiz.</i>",
            reply_markup=cancel_inline_kb("adm:nft_cancel"),
        )


@admin_router.message(StateFilter(NftStates.title), F.text)
async def adm_nft_title(message: Message, state: FSMContext):
    title = (message.text or "").strip()[:64]
    data = await state.get_data()
    await state.set_state(NftStates.number)
    await state.update_data(title=title)

    # Raqam Telegram sahifasidan avtomatik olingan bo'lsa —
    # yana so'ramaymiz.
    auto_num = data.get("auto_number")
    if auto_num:
        await state.update_data(number=int(auto_num))
        await message.answer(
            f"🏷 <b>Nom: {esc(title)}</b>\n"
            f"🔢 <b>Raqam: #{auto_num}</b> (Telegram'dan olindi)\n\n"
            "💰 <b>4/4</b> — <b>1 kunlik narxini</b> yuboring (masalan: 84).",
            reply_markup=cancel_inline_kb("adm:nft_cancel"),
        )
        return

    await message.answer(
        "🏷 <b>Nom qabul qilindi</b>\n\n"
        "🔢 <b>3/4</b> — NFT raqamini yuboring (masalan: 22810).",
        reply_markup=cancel_inline_kb("adm:nft_cancel"),
    )


@admin_router.message(StateFilter(NftStates.number), F.text)
async def adm_nft_number(message: Message, state: FSMContext):
    raw = re.sub(r"\D", "", message.text or "")
    await state.set_state(NftStates.daily)
    await state.update_data(number=int(raw) if raw else None)
    await message.answer(
        "🔢 <b>Raqam qabul qilindi</b>\n\n"
        "💰 <b>4/4</b> — <b>1 kunlik narxini</b> yuboring (so'mda, masalan: 84).",
        reply_markup=cancel_inline_kb("adm:nft_cancel"),
    )


@admin_router.message(StateFilter(NftStates.daily), F.text)
async def adm_nft_daily(message: Message, state: FSMContext):
    daily = parse_uzs_amount(message.text or "")
    if daily is None or daily < 1:
        await message.answer("⚠️ Narxni butun son ko'rinishida yuboring (masalan: 84).")
        return
    data = await state.get_data()
    await state.clear()

    nid = new_id("nft")
    item = {
        "id": nid,
        "title": data.get("title") or "NFT sovg'a",
        "number": data.get("number"),
        "link": data.get("link") or "",
        "image": data.get("image") or "",
        # Telegram sahifasidagi "Model / Backdrop / Symbol" matni —
        # WebApp filtrlari uchun saqlanadi.
        "description": data.get("auto_desc") or "",
        "daily": daily,
        "active": True,
        "created_at": now_iso(),
    }
    db.data.setdefault("nfts", {})[nid] = item
    db.save()

    q3 = nft_rent_quote(daily, NFT_MIN_DAYS)
    q30 = nft_rent_quote(daily, 30)
    # Rasm ko'rinadimi? t.me/nft/... — bu sahifa havolasi, rasm EMAS.
    has_img = nft_has_viewable_image(item)
    warn = "" if has_img else (
        "⚠️ <b>Rasm biriktirilmagan</b> — WebApp'da bo'sh kvadrat ko'rinadi.\n"
        f"   <code>{esc(str(item.get('link') or 'link'))}</code> bu rasm EMAS "
        "(Telegram NFT sahifasi).\n"
        "   Rasmni <b>rasm sifatida yuboring</b> yoki rasim havolasi "
        "(https://...jpg) qo'ying.\n\n"
    )
    await message.answer(
        "✅ <b>NFT qo'shildi!</b>\n\n"
        f"🖼 <b>{esc(item['title'])}</b>"
        + (f" <code>#{item['number']}</code>" if item.get("number") else "") + "\n"
        + f"💰 1 kun: <b>{fmt(daily)} UZS</b>\n\n"
        + "📊 <b>Mijozga ko'rinadigan hisob:</b>\n"
        + f"├ 3 kun: <b>{fmt(q3['total'])} UZS</b> "
        + f"({fmt(daily)}×3 + {fmt(NFT_NETWORK_FEE)})\n"
        + f"├ 30 kun: <b>{fmt(q30['total'])} UZS</b>\n"
        + f"├ Muddat: <b>{NFT_MIN_DAYS}–{NFT_MAX_DAYS} kun</b>\n"
        + f"└ Network fee: <b>{fmt(NFT_NETWORK_FEE)} UZS</b>\n\n"
        + warn
        + "<i>WebApp → NFT Rent bo'limida ko'rinadi.</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            # Rasm ko'rinmaydigan bo'lsa — darhol tuzatishga imkon beramiz.
            *([] if has_img else [[
                InlineKeyboardButton(text="🖼 Rasm qo'shish", callback_data=f"adm:nft_photo:{nid}"),
            ]]),
            [InlineKeyboardButton(text="📋 NFT ro'yxati", callback_data="adm:nft_list"),
             InlineKeyboardButton(text="⬅️ Admin", callback_data="adm:home")],
        ]),
    )


@admin_router.callback_query(F.data.startswith("adm:nft_photo:"))
async def adm_nft_photo_ask(call: CallbackQuery, state: FSMContext):
    """ALDIYI bir NFT ga rasm biriktirish (ko'rsatish uchun)."""
    if not await _admin_guard(call):
        return
    db.reload_if_changed()
    await call.answer()
    nid = call.data.split(":", 2)[2]
    n = db.data.get("nfts", {}).get(nid)
    if not n:
        await call.message.answer("❌ NFT topilmadi.")
        return
    await state.set_state(NftStates.photo)
    await state.update_data(nft_id=nid)
    await call.message.answer(
        "🖼 <b>Rasm biriktirish</b>\n\n"
        f"NFT: <b>{esc(str(n.get('title')))}</b>\n\n"
        "Endi <b>rasmni shu yerga yuboring</b> (Telegram'dan).\n\n"
        "<i>Rasm server orqali yuboriladi va WebApp'da ko'rinadi.\n"
        "Bekor qilish uchun /cancel.</i>",
        reply_markup=cancel_inline_kb("adm:nft_list"),
    )


@admin_router.message(StateFilter(NftStates.photo), F.photo)
async def adm_nft_photo_save(message: Message, state: FSMContext):
    """Yuborilgan rasmni NFT ga biriktiradi (Telegram file_id)."""
    if not is_admin_authed(message.from_user.id):
        return
    db.reload_if_changed()
    data = await state.get_data()
    nid = str(data.get("nft_id") or "")
    n = db.data.get("nfts", {}).get(nid)
    if not n:
        await state.clear()
        await message.answer("❌ Jarayon eskirgan. \n<i>«📋 NFT ro'yxati» dan qayta boshlang.</i>")
        return
    # Eng katta o'lchamdagi rasmni olamiz
    n["image"] = message.photo[-1].file_id
    n["has_photo"] = True
    db.save()
    await state.clear()
    await message.answer(
        "✅ <b>Rasm biriktirildi!</b>\n\n"
        f"🖼 <b>{esc(str(n.get('title')))}</b>\n\n"
        "<i>WebApp → NFT Rent bo'limida 1–3 soniyada ko'rinadi.\n"
        "Agar ko'rinmasa — sahifani yangilang.\n"
        "</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="📋 NFT ro'yxati", callback_data="adm:nft_list"),
            InlineKeyboardButton(text="⬅️ Admin", callback_data="adm:home"),
        ]]),
    )


@admin_router.callback_query(F.data == "adm:nft_list")
async def adm_nft_list(call: CallbackQuery):
    if not await _admin_guard(call):
        return
    await call.answer()
    db.reload_if_changed()
    items = sorted(db.data.get("nfts", {}).values(),
                   key=lambda n: -num(n.get("daily")))
    if not items:
        await call.message.answer(
            "📋 <b>NFT ro'yxati bo'sh</b>\n\n"
            "➕ NFT qo'shish uchun: <code>/admin → ➕ NFT qo'shish</code>",
            reply_markup=admin_back_kb(),
        )
        return
    lines = [f"📋 <b>NFT'lar</b> ({len(items)} ta)\n"]
    buttons = []
    for i, n in enumerate(items, 1):
        st = "✅" if n.get("active", True) else "⏸"
        has_img = nft_has_viewable_image(n)
        lines.append(
            f"\n{i}. {st} <b>{esc(str(n.get('title')))}</b>"
            + (f" <code>#{n.get('number')}</code>" if n.get("number") else "")
            + f"\n   💰 1 kun: <b>{fmt(num(n.get('daily')))} UZS</b>"
            f" · {NFT_MIN_DAYS} kun: <b>{fmt(nft_rent_quote(n.get('daily'), NFT_MIN_DAYS)['total'])}</b>"
            + ("" if has_img else "\n   🚫 <b>Rasm yo'q</b> — WebApp'da bo'sh kvadrat ko'rinadi")
        )
        row = []
        if not has_img:
            row.append(InlineKeyboardButton(
                text="🖼 Rasm", callback_data=f"adm:nft_photo:{n.get('id')}"))
        row.append(InlineKeyboardButton(
            text=f"{'⏸️' if n.get('active', True) else '▶️'} {str(n.get('title'))[:22]}",
            callback_data=f"adm:nft_toggle:{n.get('id')}"))
        buttons.append(row)
    lines.append("\n\n<i>Bosish orqali yoqish/ochish</i>")
    buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm:home")])
    await call.message.answer(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),  # type: ignore[arg-type]
    )


@admin_router.callback_query(F.data.startswith("adm:nft_toggle:"))
async def adm_nft_toggle(call: CallbackQuery):
    if not await _admin_guard(call):
        return
    await call.answer()
    db.reload_if_changed()
    nid = call.data.split(":", 2)[2]
    n = db.data.get("nfts", {}).get(nid)
    if not n:
        await call.message.answer("❌ NFT topilmadi.")
        return
    n["active"] = not n.get("active", True)
    db.save()
    await call.message.answer(
        f"{'✅ Yoqildi' if n['active'] else '⏸️ To' + chr(39) + 'xtatildi'}: "
        f"<b>{esc(str(n.get('title')))}</b>"
    )


@admin_router.callback_query(F.data == "adm:nft_cancel")
async def adm_nft_add_cancel(call: CallbackQuery, state: FSMContext):
    """«Bekor qilish» — NFT qo'shishdan chiqish."""
    if not await _admin_guard(call):
        return
    await state.clear()
    await call.answer("Bekor qilindi")
    try:
        await call.message.edit_text("❌ NFT qo'shish bekor qilindi.")
    except Exception:  # noqa: BLE001
        pass



@admin_router.callback_query(F.data == "adm:logout")
async def adm_logout(call: CallbackQuery, state: FSMContext):
    ADMIN_SESSIONS.pop(call.from_user.id, None)
    await state.clear()
    await call.answer("Chiqdingiz")
    await call.message.edit_text("🚪 Admin paneldan chiqdingiz.")


# ------------------------------------------------------------------ statistika
def db_stats() -> dict:
    # DIQQAT: "volume" avval settings.total_volume_uzs dan olinardi —
    # bu bitta jamlangan akkumulator, seed qiymati bilan (485 mln) va
    # orderlarning haqiqiy holati bilan mos kelmaydigan raqam edi.
    # ENDI: to'ldirilgan summalar HAQIQIY topups ro'yxatidan yig'iladi.
    users = list(db.data["users"].values())
    orders = list(db.data["orders"].values())
    topups = list(db.data["topups"].values())
    done_topups = [t for t in topups if t.get("status") == "completed"]
    volume = sum(num(t.get("amount")) for t in done_topups)
    completed_orders = [
        o for o in orders
        if o.get("status") == "completed" and not o.get("gift_cancelled")
    ]
    return {
        "users": len(users),
        "active": sum(1 for u in users if num(u.get("total_spent")) > 0),
        "banned": sum(1 for u in users if u.get("banned")),
        "balance": sum(num(u.get("balance")) for u in users),
        "orders": len(orders),
        "completed_orders": len(completed_orders),
        "volume": volume,
        "revenue": sum(
            num(o.get("price_uzs") or o.get("price")) for o in completed_orders
        ),
        "topups_done": len(done_topups),
        "topups_pending": sum(1 for t in topups if t.get("status") == "pending"),
        "pending_orders": sum(1 for o in orders if o.get("status") in
                              ("processing", "pending_admin", "manual_pending")),
        "cancelled_orders": sum(
            1 for o in orders
            if o.get("status") == "cancelled" or o.get("gift_cancelled")
        ),
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
@admin_router.callback_query(F.data == "adm:ub_export")
async def adm_ub_export(call: CallbackQuery, state: FSMContext):
    """Ishlayotgan userbotdan SESSION_STRING ni darhol oladi.

    Bu — telefon/kod umuman KERAKMASDIGAN usul. Agar userbot allaqachon
    ulangan bo'lsa (masalan Railway da SESSION_STRING to'g'ri qo'yilgan),
    shu zahoti zaxira sessiyani olamiz. Kod muddati bilan bog'liq muammo
    butunlay chiqadi.
    """
    if not await _admin_guard(call):
        return
    await call.answer("📤 Olinmoqda...")
    if userbot is None:
        await call.message.answer(
            "❌ Userbot ulanmagan — olish mumkin emas.\n\n"
            "Avval «📱 Raqam bilan ulash» yoki «🔑 QR» orqali ulashing."
        )
        return
    try:
        session = await userbot.export_session_string()
        me = await userbot.get_me()
        who = f"@{me.username}" if getattr(me, "username", None) else str(me.id)
    except Exception as exc:  # noqa: BLE001
        await call.message.answer(f"❌ Olib bo'lmadi:\n<code>{esc(str(exc)[:200])}</code>")
        return
    await call.message.answer(
        f"✅ <b>Session zaxirasi olindi</b> ({esc(who)})\n\n"
        f"🔑 <b>Railway ENV ga saqlang</b> (kalit — hech kimga bermang):\n\n"
        f"<code>SESSION_STRING={esc(session)}</code>\n\n"
        "<i>Ishlayotgan sessiyani olish uchun kod umuman kerak emas. "
        "Uni xotirangizda saqlang — kelajakda shu bilan darhal "
        "qo'ya boshlay olasiz.</i>",
        reply_markup=admin_back_kb(),
        disable_web_page_preview=True,
    )


@admin_router.callback_query(F.data == "adm:ub_qr")
async def adm_ub_qr(call: CallbackQuery, state: FSMContext):
    """QR orqali ulash.

    ESKI KOD: client.export_login_token() / client.import_login_token() —
    bu Pyrogram 1.x metodlari, 2.x da UMUMAN yo'q (AttributeError berardi).
    Endi: raw funksiyalar (auth.ExportLoginToken / auth.ImportLoginToken) va
    Telegram tasdiqlashini kutib olish (30 soniya davomida har 2 sekundda).
    """
    if not await _admin_guard(call):
        return
    await call.answer("🔑 QR tayyorlanmoqda...")
    if not (API_ID and API_HASH):
        await call.message.answer("❌ API_ID va API_HASH o'zgaruvchilari yo'q.")
        return

    import base64 as _b64
    from pyrogram import raw as _raw

    client = None
    try:
        client = UserbotClient(
            "qr_login", api_id=API_ID, api_hash=API_HASH,
            in_memory=True, no_updates=True,
        )
        await client.connect()

        r = await client.invoke(
            _raw.functions.auth.ExportLoginToken(
                api_id=API_ID, api_hash=API_HASH, except_ids=[],
            )
        )
        token_bytes = r.token
        token_urlsafe = token_bytes.hex()
        payload = f"tg://login?token={token_urlsafe}"
        qr_b64 = _b64.urlsafe_b64encode(payload.encode()).decode()
        qr_url = (
            "https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=" + qr_b64
        )

        await call.message.answer(
            "🔑 <b>Userbot QR bilan ulash</b>\n\n"
            "Telefonda <b>Telegra</b>ramni oching:\n"
            "<b>Settings → Devices → Link Desktop Device</b>\n\n"
            "Quyidagi QR kodni skanerlang:\n"
            f"<a href=\"{qr_url}\">🖼 QR kodni ochish</a>\n\n"
            "⏱ Kod <b>60 soniya</b> amal qiladi. Skanerlagandan keyin avtomatik "
            "ulanadi — bu yerga xabar yuborishingiz shart emas.",
            reply_markup=admin_back_kb(),
            disable_web_page_preview=False,
        )

        # Telegram foydalanuvchi tasdiqlaguncha kutamiz
        deadline = time.time() + 60
        me = None
        last_err = ""
        while time.time() < deadline:
            await asyncio.sleep(2)
            try:
                res = await client.invoke(
                    _raw.functions.auth.ImportLoginToken(token=token_bytes)
                )
                me = await client.get_me()
                break
            except Exception as exc:  # noqa: BLE001
                last_err = type(exc).__name__
                continue

        if me is None:
            await call.message.answer(
                f"⏱ Vaqt tugadi yoki tasdiqlanmadi{f' ({last_err})' if last_err else ''}."
                "\n<i>«📱 Raqam bilan ulash» dan foydalanishingiz mumkin.</i>"
            )
            return

        await ub_finish_login(client, call.message, state)
    except Exception as exc:  # noqa: BLE001
        log.exception("QR login xatosi")
        await call.message.answer(
            f"❌ QR login xatosi:\n<code>{esc(str(exc)[:250])}</code>\n\n"
            "<i>«📱 Raqam bilan ulash» dan foydalanishingiz mumkin.</i>"
        )
    finally:
        try:
            if client is not None and client is not B.userbot:
                await client.disconnect()
        except Exception:  # noqa: BLE001
            pass


@admin_router.callback_query(F.data == "adm:ub_phone")
async def adm_ub_phone(call: CallbackQuery, state: FSMContext):
    if not await _admin_guard(call):
        return
    await call.answer()
    if not (API_ID and API_HASH):
        await call.message.answer("❌ API_ID va API_HASH o'zgaruvchilari yo'q.")
        return
    await state.set_state(AdminStates.ub_phone)
    await call.message.answer(
        "📱 <b>Raqam bilan ulash</b>\n\n"
        "Telefon raqamingizni +998 XX XXX XX XX ko'rinishida yuboring.\n\n"
        "<i>Bu akkaunt bank xabarlarini tekshiradi va sovg'alarni yuboradi.</i>",
        reply_markup=admin_back_kb(),
    )


# Telefon bilan ulash vaqtinchalik ma'lumotlari.
# FSM ichida saqlanmaydi — Client obyekti JSON'ga sig'maydi.
def extract_login_code(text: str) -> tuple[Optional[str], str]:
    """Telegram kirish kodi = ANIQ 5 ta raqam.

    Nima uchun bu muhim:
      Telegram noto'g'ri kod yuborilsa urinishni yoqadi. 2-3 urinishdan
      keyin u phone_code_hash'ni butunlay o'ldiradi va keyingi urinishda
      PHONE_CODE_EXPIRED qaytadi — ya'ni foydalanuvchi "muddati tugdi"
      deb o'ylaydi, aslida esa kod NOTO'G'RI edi.

      Shuning uchun:
        1) turli yozishlarni qabul qilamiz  (12.355 / 12 355 / 12355)
        2) lekin Telegram'ga FAQAT aniq 5 raqamli kodni yuboramiz
        3) noto'g'ri uzunlikni umuman yubormaymiz (hash jon qoladi)

    Qaytaradi: (kod | None, tushuntirish)
    """
    raw = (text or "").strip()
    if not raw:
        return None, "Bo‘sh xabar"

    # 1) Butun xabar faqat raqam + ajratuvchilardan iborat
    #    (12.355 / 12 355 / 12355 / 12,355) — Telegram kodni shakllantiradi
    if re.fullmatch(r"[\d\s.,  .\-]+", raw):
        digits = re.sub(r"\D", "", raw)
        if len(digits) == 5:
            return digits, ""
        if not digits:
            return None, "Raqam topilmadi"
        return None, f"{len(digits)} ta raqam keldi, 5 ta kerak"

    # 2) Xabar matni ichidan aynan 5 ketma-ket raqam qidiramiz
    #    ("Your login code is 12345", "15:16 — 12345")
    found = re.findall(r"(?<!\d)(\d{5})(?!\d)", raw)
    if found:
        return found[0], ""
    if re.search(r"\d", raw):
        # raqam bor, lekin 5 ketma-ket emas (masalan sana/aralashgan)
        groups = [g for g in re.findall(r"\d+", raw)]
        joined = "".join(groups)
        if len(joined) == 5:
            return joined, ""
        return None, "5 ketma-ket raqam topilmadi"

    return None, "Raqam yo‘q"


UB_LOGIN = {"client": None, "phone": "", "hash": "", "admin_id": 0, "tries": 0}


async def ub_finish_login(client, admin_msg: Message, state: FSMContext) -> None:
    """Ulangan client'ni userbot qilib o'rnatadi va SESSION_STRING beradi.

    BITTA akkaunt ikkala vazifani ham bajaradi:
      1) @humocardbot bank xabarlarini kuzatadi -> balansni to'ldiradi
      2) sovg'alarni (gift) yuboradi
    """
    global userbot
    try:
        me = await client.get_me()
        who = f"@{me.username}" if getattr(me, "username", None) else str(me.id)
    except Exception:  # noqa: BLE001
        who = "noma'lum"

    if userbot is not None and userbot is not client:
        try:
            await userbot.stop()
        except Exception:  # noqa: BLE001
            pass
    userbot = client
    await client.add_handler(
        UbMessageHandler(on_humo_message, ub_filters.chat(TOPUP_SOURCE_CHAT))
    )
    asyncio.create_task(ub_idle())
    set_runtime_status(userbot="connected", account=who, chat=str(TOPUP_SOURCE_CHAT))

    # Sessionni AVTOMATIK bazaga saqlaymiz — Railway ENV kerak emas.
    # Baza saqlanadigan papkada (/data) turgani uchun redeploy'da ham
    # joyida qoladi: telefon bilan ulaganingizdan keyin hech qachon
    # qayta ulash shart bo'lmaydi.
    session = await client.export_session_string()
    saved = save_session_to_db(session)
    await state.clear()
    await admin_msg.answer(
        "✅ <b>Userbot ulandi!</b>\n\n"
        f"👤 Hisob: <code>{esc(who)}</code>\n"
        f"🏦 Bank xabarlari: <code>{esc(str(TOPUP_SOURCE_CHAT))}</code>\n"
        "🎁 Sovg'a yuborish: shu akkaunt orqali\n\n"
        + (
            "🔐 <b>Session avtomatik saqlandi</b> — Railway ENV ga qo'yish "
            "<b>shart emas</b>.\n"
            "♻️ Redeploy, yangilash yoki qayta ishga tushirishdan keyin ham "
            "shu akkaut avtomatik ulanadi.\n\n"
            if saved else
            "⚠️ Sessionni bazaga saqlab bo'lmadi — Railway ENV ga qo'ying:\n\n"
            f"<code>SESSION_STRING={esc(session)}</code>\n\n"
        )
        + "<i>Ikkalasi ham ishlaydi. Kalitni hech kimga bermang.</i>",
        reply_markup=admin_back_kb(),
        disable_web_page_preview=True,
    )


@admin_router.message(StateFilter(AdminStates.ub_phone), F.text)
async def adm_ub_phone_wait(message: Message, state: FSMContext):
    """Telefonni qabul qiladi va Telegram'dan tasdiqlash kodi so'raydi.

    ESKI KOD: client.start(phone=...) — bu Pyrogram 1.x API edi.
    Pyrogram 2.x da start() argument qabul qilmaydi va
    "unexpected keyword argument 'phone'" xatosi berardi.
    (Yana: ikkinchi handler'da `await UserbotClient(...)` — konstruktorni
     await qilish, ham xato edi.)

    TO'G'RI OQIM:  connect() -> send_code() -> (kod) -> sign_in()
    """
    if not is_admin_authed(message.from_user.id):
        return
    phone = re.sub(r"[\s()\-]", "", message.text or "")
    if not re.fullmatch(r"\+\d{9,15}", phone):
        await message.answer("❌ Format noto'g'ri. Masalan: <code>+998901234567</code>")
        return

    await state.set_state(AdminStates.ub_code)
    await state.update_data(ub_phone=phone)

    # Eslatma: agar userbot ALLAQACHON ulangan bo'lsa, telefon umuman
    # kerak emas — "📤 Session zaxirasi" tugmasi bilan sessiyani darhol
    # olish mumkin (muddatsiz, kod umuman kerak emas).
    if userbot is not None:
        await message.answer(
            "ℹ️ Userbot allaqachon ulangan.\n\n"
            "🔑 Telefon va kod kerak emas —\n"
            "<i>/admin → 📤 Session zaxirasi</i> orqali joriy sessiyani "
            "bir zumda olib, zaxiraga saqlang."
        )
        return

    try:
        client = UserbotClient(
            "phone_login", api_id=API_ID, api_hash=API_HASH,
            in_memory=True, no_updates=True,
        )
        await client.connect()
        sent = await client.send_code(phone)
        UB_LOGIN.update({
            "client": client,
            "phone": phone,
            "hash": getattr(sent, "phone_code_hash", ""),
            "admin_id": message.from_user.id,
            "tries": 0,
        })
        code_type = str(getattr(sent, "type", "") or "")
        extra = ""
        if "CALL" in code_type.upper():
            extra = "\n\n📞 Telegram <b>qo‘ng‘iroq qiladi</b> — kodni eshitib kiriting."
        await message.answer(
            "🔐 Telegram yuborgan <b>tasdiqlash kodi</b>ni kiriting:" + extra
            + "\n\n⏱ Kod bir necha daqiqa amal qiladi — iloji boricha tez yuboring.\n"
            "<i>Kodni olmagan bo'lsangiz, Telegram'dagi xabarni ochib "
            "«🔔 qayta yuborish» ni bosing.</i>",
            reply_markup=admin_back_kb(),
        )
    except Exception as exc:  # noqa: BLE001
        UB_LOGIN["client"] = None
        await state.clear()
        log.exception("Telefon orqali ulash: kod yuborilmadi")
        await message.answer(
            f"❌ Kod yuborilmadi:\n<code>{esc(str(exc)[:300])}</code>\n\n"
            "ℹ️ Raqam to‘g‘ri ekanini va Telegram'dan kelgan xabarni tekshiring."
        )


@admin_router.message(StateFilter(AdminStates.ub_code), F.text)
async def adm_ub_code_wait(message: Message, state: FSMContext):
    if not is_admin_authed(message.from_user.id):
        return
    client = UB_LOGIN.get("client")
    phone = UB_LOGIN.get("phone", "")
    code_hash = UB_LOGIN.get("hash", "")
    if client is None or not phone or not code_hash:
        await state.clear()
        await message.answer(
            "⚠️ Ulash jarayoni eskirgan.\n"
            "<i>/admin → 📱 Raqam bilan ulash</i> dan qayta boshlang."
        )
        return

    code, why = extract_login_code(message.text or "")
    if not code:
        # Telegram'ga YUBORMAYMIZ — noto'g'ri urinish phone_code_hash'ni
        # o'ldiradi va keyin "muddati tugdi" xatosi chiqadi.
        await message.answer(
            "❌ Kodni topib bo'lmadi.\n\n"
            f"🔍 Sabab: {why}\n\n"
            "🔐 Telegram xabaridagi <b>5 ta raqamni</b> yuboring.\n"
            "<i>Nuqta/bo'shliq bo'lsa ham bo'ladi — 12.355 deb yozsangiz "
            "biz 12355 ni o'qiymiz.</i>"
        )
        return

    try:
        await client.sign_in(
            phone_number=phone, phone_code_hash=code_hash, phone_code=code
        )
    except Exception as exc:  # noqa: BLE001
        name = type(exc).__name__
        # 2FA paroli talab qilinsa — alohida qadamga o'tamiz
        if "SessionPasswordNeeded" in name:
            await state.set_state(AdminStates.ub_password)
            hint = ""
            try:
                h = await client.get_password_hint()
                if h:
                    hint = f"\n\n💡 Parol ishorasi: <code>{esc(str(h))}</code>"
            except Exception:  # noqa: BLE001
                pass
            await message.answer(
                "🔐 Bu akkauntda <b>ikki bosqichli tasdiqlash</b> yoqiq.\n\n"
                "🔑 Telegram parolingizni yuboring:" + hint
            )
            return
        msg_text = str(exc)

        # Kod MUDDATI TUGGAN — foydalanuvchidan butun oqimni qayta
        # boshlashini so'ramasdan, o'zimiz yangi kod yuboramiz.
        # Faqat muddati TUGGAN holatda yangi kod kerak.
        # PhoneCodeInvalid (noto'g'ri raqam) da hash hali yaroqli —
        # qayta kod yuborish faqat chalkashlantiradi.
        if ("PhoneCodeExpired" in name or "PHONE_CODE_EXPIRED" in msg_text
                or "PhoneCodeEmpty" in name):
            tries = int(UB_LOGIN.get("tries", 0))
            if tries < 3:
                try:
                    sent = await client.send_code(phone)
                    UB_LOGIN["hash"] = getattr(sent, "phone_code_hash", "")
                    UB_LOGIN["tries"] = tries + 1
                except Exception as send_exc:  # noqa: BLE001
                    log.warning("Yangi kod yuborilmadi: %s", send_exc)
                    await client.disconnect()
                    UB_LOGIN["client"] = None
                    await state.clear()
                    await message.answer(
                        f"❌ Yangi kod ham yuborilmadi:\n<code>{esc(str(send_exc)[:200])}</code>\n\n"
                        "<i>«📱 Raqam bilan ulash» dan qayta boshlang.</i>"
                    )
                    return

                why = ("muddati tugdi" if "Expired" in name or "EXPIRED" in msg_text
                       else "noto'g'ri bo'lib chiqdi")
                await message.answer(
                    f"⏳ Oldingi kod {why} — <b>yangi kod yuborildi</b>.\n\n"
                    f"🔐 Telegram'dagi <b>eng so'nggi</b> xabarni ochib, "
                    f"uning kodini shu yerga yuboring.\n\n"
                    f"<i>Urinish {UB_LOGIN['tries']}/3. Kodni iloji boricha tezroq yuboring.</i>",
                    reply_markup=admin_back_kb(),
                )
                return
            await client.disconnect()
            UB_LOGIN["client"] = None
            await state.clear()
            await message.answer(
                "❌ Kod bir necha marta ishlatilmadi.\n\n"
                "ℹ️ Telegram <b>Settings → Devices</b> dan esk sessiyalarni "
                "tozalang, keyin <i>«📱 Raqam bilan ulash»</i> dan qayta boshlang."
            )
            return

        # Noto'g'ri raqamli kod — hash yaroqli, shuning uchun qayta
        # so'ramasdan, xatoni aniq aytib beramiz.
        if "PhoneCodeInvalid" in name or "PHONE_CODE_INVALID" in msg_text:
            tries = int(UB_LOGIN.get("tries", 0))
            if tries >= 2:
                # Hash ham jihatdan o'lishi mumkin — yangi kod beramiz
                try:
                    sent = await client.send_code(phone)
                    UB_LOGIN["hash"] = getattr(sent, "phone_code_hash", "")
                    UB_LOGIN["tries"] = 0
                    await message.answer(
                        "⚠️ Bir necha marta xato bo'ldi — <b>yangi kod yuborildi</b>.\n\n"
                        "🔐 Telegram'dagi <b>eng so'nggi</b> xabarni ochib, "
                        "uning <b>5 ta raqamini</b> yuboring.\n"
                        "<i>Nuqtali yozsangiz bo'ladi (12.355) — biz to'g'ri o'qiymiz.</i>",
                        reply_markup=admin_back_kb(),
                    )
                    return
                except Exception:  # noqa: BLE001
                    pass
            if tries < 2:
                UB_LOGIN["tries"] = tries + 1
                await message.answer(
                    "❌ Kod <b>noto'g'ri</b>.\n\n"
                    "🔐 Telegram'dagi xabar bilan solishtirib, "
                    "<b>faqat 5 ta raqamni</b> yuboring (bo'sh joysiz).\n"
                    f"<i>Urinish {UB_LOGIN['tries']}/2.</i>\n"
                    "<i>⚠️ Telegram 3 marta xato urinishdan keyin kodni "
                    "bekor qiladi — shuning uchun ehtiyot bo'ling.</i>",
                    reply_markup=admin_back_kb(),
                )
                return

        # Boshqa xatolar (raqam band, flood limit va h.k.)
        try:
            await client.disconnect()
        except Exception:  # noqa: BLE001
            pass
        UB_LOGIN["client"] = None
        await state.clear()
        log.warning("Kod bilan ulash xatosi: %s", exc)
        friendly = ("Flood limit — ko'p urinish. 1 soat kutib turing."
                    if "FLOOD" in msg_text.upper() else str(exc)[:250])
        await message.answer(
            f"❌ Kod qabul qilinmadi:\n<code>{esc(friendly)}</code>\n\n"
            "<i>«📱 Raqam bilan ulash» dan qayta boshlang.</i>"
        )
        return

    await ub_finish_login(client, message, state)


@admin_router.message(StateFilter(AdminStates.ub_password), F.text)
async def adm_ub_password_wait(message: Message, state: FSMContext):
    """2FA paroli (Telegram ikki bosqichli tasdiqlash)."""
    if not is_admin_authed(message.from_user.id):
        return
    client = UB_LOGIN.get("client")
    if client is None:
        await state.clear()
        await message.answer("⚠️ Jarayon eskirgan. Qayta boshlang.")
        return
    password = (message.text or "").strip()
    # DIQQAT: Pyrogram 2.x da sign_in() "password" argumentini qabul qilmaydi.
    # 2FA uchun alohida check_password() metodi bor.
    try:
        await client.check_password(password)
    except Exception as exc:  # noqa: BLE001
        log.warning("2FA parol xatosi: %s", exc)
        await message.answer(
            f"❌ Parol noto‘g‘ri:\n<code>{esc(str(exc)[:200])}</code>"
        )
        return
    await ub_finish_login(client, message, state)


# =============================================================================
# 15b. GIFT BO'LIMI (bot tomoni)
# -----------------------------------------------------------------------------
# Rasm 6: mijoz sovg'a yuborishda IKKITA tanlovga ega bo'lishi kerak:
#   🕶️ Anonim            — yuboruvchining profili ko'rinmaydi
#   👤 Profil ko'rinadi  — yuboruvchining ismi/profili ko'rinadi
#
# Bundan tashqari qabul qiluvchi botda ro'yxatdan o'tmagan bo'lsa ham
# ismi va (ixtiyoriy) profil rasmi ko'rsatiladi.
# =============================================================================


class GiftStates(StatesGroup):
    recipient = State()
    confirm = State()


def _gift_price(key: str) -> int:
    g = GIFTS_BY_KEY.get(key)
    return g[3] if g else 0


async def gifts_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(GiftStates.recipient)
    rows: list[list[InlineKeyboardButton]] = []
    line: list[InlineKeyboardButton] = []
    # DIQQAT: GIFTS tuple'i 5 ta elementli (emoji oxirida) — indeks bilan
    # olamiz, guruhlab ochmaymiz (avval shu sababli Giftlar menyusi ham
    # "too many values to unpack" xatosi bilan ishlamay qolgan edi).
    for g in GIFTS:
        key, title, price = g[0], g[1], g[3]
        line.append(
            InlineKeyboardButton(text=f"{title}\n{fmt(price)} so'm",
                                 callback_data=f"gift_pick:{key}", style="primary")
        )
        if len(line) == 2:
            rows.append(line)
            line = []
    if line:
        rows.append(line)
    rows.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel", style="danger")])
    await message.answer(
        "🎁 <b>Giftlar</b>\n\n"
        "🧸 Sovg'a turini tanlang (Telegram Stars orqali):\n\n"
        "🕶️ Yuborish <b>anonim</b> bo'ladi — profilingiz ko'rinmaydi.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@common_router.callback_query(F.data.startswith("gift_pick:"))
async def gift_pick(call: CallbackQuery, state: FSMContext, db_user: dict):
    await call.answer()
    key = call.data.split(":", 1)[1]
    g = GIFTS_BY_KEY.get(key)
    if not g:
        await call.message.answer("❌ Sovg'a topilmadi.")
        return
    balance = int(db_user.get("balance", 0))
    price = g[3]
    if balance < price:
        await call.message.answer(
            f"❌ Balans yetarli emas.\\n"
            f"💰 Kerak: <b>{fmt(price)} so'm</b>\\n"
            f"💳 Balansingiz: <b>{fmt(balance)} so'm</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Balans to'ldirish", callback_data="m:topup", style="success")],
                [InlineKeyboardButton(text="◀️ Orqaga", callback_data="m:gifts", style="danger")],
            ]),
        )
        return
    await state.set_state(GiftStates.recipient)
    await state.update_data(gift_key=key)
    await call.message.answer(
        f"{g[1]} — <b>{fmt(price)} so'm</b>\n\n"
        "👤 Qabul qiluvchining Telegram <b>@username</b> ni yuboring:",
        reply_markup=cancel_inline_kb(),
    )


@router.message(StateFilter(GiftStates.recipient), F.text)
async def gift_recipient(message: Message, state: FSMContext, db_user: dict):
    username = re.sub(r"[^A-Za-z0-9_]", "", (message.text or "").lstrip("@"))
    if len(username) < 4:
        await message.answer("❌ Username noto'g'ri. Masalan: <code>@username</code>")
        return
    key = (await state.get_data()).get("gift_key", "bear")
    g = GIFTS_BY_KEY.get(key)
    if not g:
        await state.clear()
        await message.answer("❌ Sovg'ani topib bo'lmadi. Qayta boshlang.")
        return

    # Botda ro'yxatdan o'tmagan bo'lsa ham ism/rasmni ko'rsatamiz
    prof = await resolve_recipient_profile(username)
    who = esc(str(prof["name"])) if prof and prof.get("name") else f"@{esc(username)}"
    note = ""
    if prof and prof.get("from_bot") is False:
        note = "\n<i>(botda ro'yxatdan o'tmagan — ma'lumot Telegram'dan olindi)</i>"

    await state.set_state(GiftStates.confirm)
    await state.update_data(gift_recipient=username)
    await message.answer(
        f"{g[1]} <b>{g[2]} ⭐</b> — <b>{fmt(g[3])} so'm</b>\n"
        f"👤 Qabul qiluvchi: <b>{who}</b>\n{note}\n\n"
        "🕶️ Sovg'a <b>anonim</b> tarzda yuboriladi (profilingiz ko'rinmaydi).",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🕶️ Anonim yuborish", callback_data="gift_anon:1", style="success"),
                InlineKeyboardButton(text="👤 Do'kon profili", callback_data="gift_anon:0", style="primary"),
            ],
            [InlineKeyboardButton(text="🎁 Yuborishni tasdiqlash", callback_data="gift_send", style="success")],
            [InlineKeyboardButton(text="◀️ Orqaga", callback_data="m:gifts", style="danger")],
        ]),
    )


@common_router.callback_query(F.data.startswith("gift_anon:"))
async def gift_anon_pick(call: CallbackQuery, state: FSMContext, db_user: dict):
    """Anonim yoki profil ko'rinadigan yuborishni tanlaydi."""
    await call.answer()
    anon = call.data.split(":", 1)[1] == "1"
    data = await state.get_data()
    data["gift_anon"] = anon
    await state.update_data(gift_anon=anon)
    g = GIFTS_BY_KEY.get(data.get("gift_key", ""))
    label = "🕶️ ANONIM — profilingiz yashiriladi" if anon else "👤 Do'kon profili ko'rinadi"
    await call.message.answer(
        f"✅ Yuborish turi tanlandi: <b>{esc(label)}</b>\n\n"
        "🎁 Davom etish uchun tasdiqlang.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎁 Yuborishni tasdiqlash",
                                  callback_data="gift_send", style="success")],
            [InlineKeyboardButton(text="◀️ Orqaga", callback_data="m:gifts", style="danger")],
        ]),
    )


# --- Sovg'a ostidagi matn: so'rash ------------------------------------------
@common_router.callback_query(F.data == "gift_send")
async def gift_send(call: CallbackQuery, state: FSMContext, db_user: dict):
    await call.answer("Yuborilmoqda...")
    await gift_do(call, state, db_user)


async def gift_do(event, state: FSMContext, db_user: dict) -> None:
    """Gift buyurtmasini yaratadi."""
    is_callback = isinstance(event, CallbackQuery)
    data = await state.get_data()
    key = data.get("gift_key", "")
    username = data.get("gift_recipient", "")
    anon = bool(data.get("gift_anon", True))
    g = GIFTS_BY_KEY.get(key)
    if not g or not username:
        await _reply(event, "❌ Ma'lumot topilmadi. Qayta boshlang.")
        await state.clear()
        return

    price = g[3]
    if int(db_user.get("balance", 0)) < price:
        await _reply(event, "❌ Balans yetarli emas.")
        await state.clear()
        return

    order_id = "ord_" + now_iso().replace("-", "").replace(":", "").replace(".", "")[-10:]
    db_user["balance"] = int(db_user.get("balance", 0)) - price
    db_user["total_spent"] = int(db_user.get("total_spent", 0)) + price
    db.data["orders"][order_id] = {
        "id": order_id,
        "user_id": db_user["id"],
        "kind": "gift",
        "gift": key,
        "stars": g[2],
        "title": g[1],
        "recipient": username,
        "price": price,
        "price_uzs": price,
        "amount": g[2],
        "status": "completed",
        "source": "bot",
        # ANONIM semantikasi: True -> profil yashiriladi.
        # Telegram ga to'g'ridan-to'gri hide_my_name=anon beriladi
        # (InputInvoiceStarGift.hide_name = flags.0?true), hech qanday
        # teskari aylantirish yo'q. "hide_my_name" eski buyurtmalar
        # uchun ham saqlanadi (mos semantika).
        "anon": anon,
        "hide_my_name": anon,
        "created_at": now_iso(),
    }
    db.add_history(db_user, "gift", -price, f"Gift: {g[1]} → @{username}")
    db.save()
    await state.clear()

    anon_label = "ANONIM (profil yashiriladi)" if anon else "Do'kon profili ko'rinadi"
    body = (
        "✅ <b>Gift buyurtmasi qabul qilindi!</b>\n\n"
        f"🎁 {g[1]} ({g[2]} ⭐)\n"
        f"👤 Qabul qiluvchi: <b>@{esc(username)}</b>\n"
        f"🕶️ Yuborish: <b>{esc(anon_label)}</b>\n"
        + f"💳 Yechildi: <b>{fmt(price)} so'm</b>\n\n"
        "📦 Sovg'a avtomatik yuborilmoqda — 1–5 daqiqa ichida tushadi."
    )
    if is_callback:
        await event.answer("Buyurtma qabul qilindi", show_alert=True)
        try:
            await event.message.edit_text(body)
        except Exception:  # noqa: BLE001
            pass
    else:
        await event.answer(body)

    await notify_admins(
        f"🎁 <b>Gift buyurtmasi (bot)</b>\n\n"
        f"📦 <code>#{order_id}</code>\n"
        f"👤 Mijoz: @{db_user.get('username') or db_user['id']}\n"
        f"🎯 Qabul qiluvchi: <b>@{esc(username)}</b>\n"
        f"🎁 {g[1]} ({g[2]} ⭐)\n"
        f"🕶️ <b>{esc(anon_label)}</b>\n"

        + f"💳 <b>{fmt(price)} so'm</b>"
    )
    anon_txt = "🕶️ Anonim" if anon else "👤 Do'kon profili"
    await post_order_to_channel(
        db_user,
        title=f"Gift: {g[1]} ({anon_txt})",
        username=username,
        amount_text=f"Sovg'a: {g[1]} — {g[2]} ⭐",
        price=price,
    )


async def _reply(event, text: str) -> None:
    """Callback yoki Message — ikkalasiga ham javob beradi."""
    if isinstance(event, CallbackQuery):
        try:
            await event.message.answer(text)
        except Exception:  # noqa: BLE001
            pass
    else:
        await event.answer(text)


# =============================================================================
# 15c. NFT GIFT IJARASI (boshqa menejer boshqaradi)
# -----------------------------------------------------------------------------
# Bu xizmat NEON STORE da emas — uni @saidovManajer boshqaradi.
# Mijoz tanlaganda biz uni rasmiy @rentnftlarr kanaliga yo'naltiramiz.
# =============================================================================

NFT_CHANNEL = os.getenv("NFT_CHANNEL", "@rentnftlarr")
NFT_MANAGER = os.getenv("NFT_MANAGER", "@saidovManajer")


def nft_notice() -> str:
    """NFT xizmati haqidagi professional ogohlantirish matni."""
    return (
        "⚠️ <b>Xizmat haqida</b>\n\n"
        f"🔹 Bu xizmat <b>{esc(NFT_MANAGER)}</b> ga tegishli.\n"
        "🔹 Bu xizmat bo'yicha biror muammo yuz bersa, "
        f"<b>{esc(NFT_MANAGER)}</b> bilan bog'laning.\n\n"
        f"🎁 Rasmiy kanal: <b>{esc(NFT_CHANNEL)}</b>"
    )


async def nft_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        f"🎭 <b>NFT Gift Ijarasi</b>\n\n"
        "NFT sovg'a vaqtincha ijara qilish xizmati.\n\n"
        f"{nft_notice()}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"🔗 {NFT_CHANNEL} kanalini ochish",
                url=f"https://t.me/{NFT_CHANNEL.lstrip('@')}",
                style="primary",
            )],
            [InlineKeyboardButton(text="◀️ Orqaga", callback_data="m:buy", style="danger")],
        ]),
    )


@router.message(F.text == "NFT Gift Ijarasi")
async def nft_text(message: Message, state: FSMContext):
    await nft_start(message, state)


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
        "gifts": lambda: gifts_start(msg, state),
        "nft": lambda: nft_start(msg, state),
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
    # Premium emoji ikonkalari qabul qilinmasa — oddiy variantga qaytadi
    bot.session.middleware(SafeIconMiddleware())
    dp = Dispatcher(storage=MemoryStorage())
    DP = dp

    access = AccessMiddleware()
    dp.message.outer_middleware(access)
    dp.callback_query.outer_middleware(access)
    dp.message.outer_middleware(UpdateCounterMiddleware())
    dp.callback_query.outer_middleware(UpdateCounterMiddleware())

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

        # Ixtiyoriy bosqichlar — HECH QACHON polling'ni to'xtatmasligi kerak.
        # Har biri alohida himoyalangan: bitta xato butun botni o'ldirmasin.
        async def _safe(coro, label: str) -> None:
            try:
                await coro
            except Exception as exc:  # noqa: BLE001
                log.warning("%s bajarilmadi (davom etamiz): %s", label, exc)

        try:
            await _safe(bot.delete_webhook(drop_pending_updates=False), "Webhook o'chirish")
            # ORDERS_CHANNEL ga xabar yuborish mumkinligini tekshiramiz —
            # aks holda barcha savdo xabarlari jimgina yo'qoladi.
            await _safe(check_orders_channel(), "ORDERS_CHANNEL tekshiruvi")
            # Eski ikki-userbot rejimidan qolgan runtime kalitlarini tozala
            purge_stale_runtime()
            # Baza zaxiradan tiklangan bo'lsa — bu PUL bilan bog'liq voqea
            if DB_RESTORED_FROM_BACKUP.get("path"):
                await _safe(
                    notify_admins(
                        "🚨 <b>Baza buzilgan, zaxiradan tiklandi</b>\n\n"
                        f"📁 <code>{esc(DB_RESTORED_FROM_BACKUP['path'])}</code>\n\n"
                        "⚠️ Oxirgi yozuvlar (balans, buyurtma, bekor qilingan "
                        "gift va qaytarilgan pullar) YO'QOLGAN bo'lishi mumkin.\n"
                        "🔧 <i>Ishga tushgandan keyin balanslar va tarixni "
                        "tekshiring.</i>"
                    ),
                    "DB tiklash ogohlantirishi",
                )
            maybe_start_userbot()
            for label, coro in (
                ("Gift worker", process_gift_orders()),
                ("Stars worker", star_order_worker()),
                ("USDT kursi", get_usdt_uzs_rate()),
                ("Heartbeat", update_heartbeat()),
                ("Userbot supervisor", userbot_supervisor()),
            ):
                try:
                    asyncio.create_task(coro)
                except Exception as exc:  # noqa: BLE001
                    log.warning("%s ishga tushmadi: %s", label, exc)
        except Exception as exc:  # noqa: BLE001
            log.warning("Startup qo'shimchalarida xato (polling davom etadi): %s", exc)

        set_runtime_status(bot="polling_started")

        # Polling'ni o'limaydigan qilamiz: vaqtinchalik xato botni to'xtatmasin
        while True:
            try:
                await dp.start_polling(
                    bot, allowed_updates=dp.resolve_used_update_types(), handle_signals=False
                )
                break
            except asyncio.CancelledError:
                raise
            except TelegramConflictError as exc:
                # Boshqa bot yoki ikkinchi jarayon shu token bilan polling qilmoqda.
                # Bu holatda Telegram update'larni BIRINCHI kelgan jarayonga beradi —
                # ya'ni bizning bot hech narsa olmaydi.
                log.error(
                    "⚠️ CONFLICT: boshqa jarayon shu BOT_TOKEN bilan polling qilmoqda. "
                    "Bu bot javob bermaydi. (%s)",
                    str(exc)[:150],
                )
                set_runtime_status(bot="conflict", error=str(exc)[:200])
                await asyncio.sleep(10)
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
