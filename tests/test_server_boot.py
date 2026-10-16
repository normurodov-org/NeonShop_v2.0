"""server.ts HAQIQATAN ISHGA TUSHADIMI?

Nima uchun bu test kerak:
  `npm run build` va `tsc --noEmit` TypeScript sintaksisini tekshiradi,
  LEKIN runtime xatolarini (masalan TDZ — "Cannot access 'X' before
  initialization") YO'Q. O'xshash xato production'da serverni butunlay
  o'ldirdi: "Server crashed" — bot ishlagan, lekin WebApp butunlay o'lik.

  Bu test server.ts ni haqiqiy ishga tushirib, barcha endpoint'lar
  javob berishini tekshiradi.
"""
import hashlib
import hmac
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Dinamik port: avvalgi test qoldirgan server bilan to'qnashuvni
# oldini oladi (masalan 24678 — Vite HMR porti band bo'lishi mumkin)
PORT = int(os.environ.get("SMOKE_PORT") or (4600 + (os.getpid() % 400)))
BASE = f"http://127.0.0.1:{PORT}"
DB_PATH = "/tmp/_t_smoke_server.json"
# initData shu token bilan imzolanadi (server.ts ham shuni ishlatadi)
SMOKE_BOT_TOKEN = "123456:TEST_TOKEN_FOR_SMOKE_ONLY"


def kill_stale() -> None:
    """Avvalki testdan qolgan node/tsx jarayonlarini to'xtatadi."""
    subprocess.run(
        ["pkill", "-f", "tsx server.ts"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )
    time.sleep(1.5)

ok = True


def check(cond, msg):
    global ok
    ok &= bool(cond)
    print(f"  {'✅' if cond else '❌'} {msg}")


def get(path: str):
    """GET qiladi va (status, body) qaytaradi.

    DIQQAT: urllib 404/500 larda istisno tashlaydi. Statusni yutib
    qo'yish kerak — aks holda "404 kutilgan edi" testi ham
    yolg'on "server o'ldi" deb o'ylab qoladi.
    """
    req = urllib.request.Request(BASE + path)
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, exc.read().decode()
        except Exception:  # noqa: BLE001
            return exc.code, ""
    except Exception as exc:  # noqa: BLE001
        return 0, str(exc)


def make_init_data(bot_token: str, user: dict, auth_date: int = 0) -> str:
    """Telegram WebApp `initData` satrini HAQIQIY imzo bilan yasaydi.

    Telegramning rasmiy algoritmi:
        secret_key     = HMAC_SHA256(bot_token, "WebAppData")
        data_check_str = "auth_date=<t>\nquery_id=...\nuser=<json>"
                         (kalitlar bo'sh joy bo'yicha saralangan, hash YO'Q)
        hash           = HMAC_SHA256(data_check_str, secret_key)

    server.ts dagi `verifyTelegramInitData()` bilan BIR XIL. Shu sababli
    bu test haqiqiy Telegram imzosi qabul qilinishini tekshiradi —
    sun'iy `x-telegram-user-id` header'i bilan emas.
    """
    user_json = json.dumps(user, separators=(",", ":"), ensure_ascii=False)
    fields = {
        "auth_date": str(auth_date or int(time.time())),
        "query_id": "AAF_TEST",
        "user": user_json,
    }
    dcs = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    sig = hmac.new(secret, dcs.encode(), hashlib.sha256).hexdigest()
    parts = [f"{k}={urllib.parse.quote(fields[k], safe='')}" for k in sorted(fields)]
    parts.append("hash=" + sig)
    return "&".join(parts)


def get_auth(path: str, init_data: str = "", extra_headers: dict | None = None):
    """`X-Telegram-Init-Data` (yoki boshqa header) bilan GET qiladi."""
    headers = {"Content-Type": "application/json"}
    if init_data:
        headers["X-Telegram-Init-Data"] = init_data
    for k, v in (extra_headers or {}).items():
        headers[k] = v
    req = urllib.request.Request(BASE + path, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, exc.read().decode()
        except Exception:  # noqa: BLE001
            return exc.code, ""
    except Exception as exc:  # noqa: BLE001
        return 0, str(exc)


def write_db(data: dict) -> None:
    """DB fayliga yozadi — bot.py dagi db.save() ga o'xshash.

    DIQQAT: bot.py va server.ts BIR faylda ishlaydi. Admin panel orqali
    NFT qo'shilganda shu fayl yangilanadi, lekin server uni faqat
    o'z xotirasida saqlaydi. Test shu oqimni takrorlaydi.
    """
    tmp = DB_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, DB_PATH)


print("=" * 68)
print("1) server.ts ishga tushadimi? (TDZ / runtime xatolar)")
print("=" * 68)

env = {
    **os.environ,
    "PORT": str(PORT),
    "BOT_TOKEN": SMOKE_BOT_TOKEN,
    "API_ID": "1",
    "API_HASH": "x",
    "DB_PATH": DB_PATH,
    "AUTO_START_TG_BOT": "false",
    "NODE_ENV": "test",
}
for _sfx in ("", ".bak", ".tmp"):
    _p = DB_PATH + _sfx
    if os.path.exists(_p):
        os.remove(_p)
kill_stale()

proc = subprocess.Popen(
    ["npx", "tsx", "server.ts"],
    cwd=ROOT, env=env,
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    text=True, preexec_fn=os.setsid, bufsize=1,
)

deadline = time.time() + 150
ready = False
output = ""
try:
    while time.time() < deadline:
        if proc.poll() is not None:
            output = proc.stdout.read() if proc.stdout else ""
            break
        status, _ = get("/api/health")
        if status == 200:
            ready = True
            break
        if proc.poll() is not None:
            break
        time.sleep(1.0)
except Exception:  # noqa: BLE001
    pass

# --- Hali server ISHLAB turibdi — endpoint'larni tekshiramiz ---
if not ready:
    print("  ❌ Server ishga TUSHMADI")
    tail = "\n     ".join((output or "(chiqish yo'q)").splitlines()[-18:])
    print("     " + tail)
    print()
    print("NATIJA: ❌ SERVER ISHLAMADI")
    sys.exit(1)

check(True, "server.ts ishga tushdi (/api/health javob berdi)")

print()
print("=" * 68)
print("2) TDZ / modul darajasidagi xatolar yo'qmi?")
print("=" * 68)
for bad in (
    "ReferenceError",
    "Cannot access",
    "before initialization",
    "is not defined",
    "SyntaxError",
):
    check(bad not in output, f"chiqishda {bad!r} yo'q")

print()
print("=" * 68)
print("3) 🔐 FOYDALANUVCHI IDENTIFIKATSIYASI — imzo (initData HMAC)")
print("=" * 68)

# 🔴 BU — mijozning 1-rasmdagi asosiy shikoyatining regressiya testi.
#    Eski kod: `getUser(req, defaultId = DEFAULT_USER_ID)` — `x-telegram-user-id`
#    header'i kelmasa yoki noto'g'ri bo'lsa `targetId` ADMINNIKIGA (8307046273)
#    qolardi. Natijada:
#      * Telegram DAN tashqarida ochilgan WebApp → admin profili/balansi
#      * `?uid=<istalgan id>` → boshqa mijoz ma'lumotlari ko'rinardi
#    Endi `verifyTelegramInitData()` imzoni BOT_TOKEN bilan tekshiriladi va
#    imzo yo'q bo'lsa 401 qaytariladi — hech qachon ADMIN emas.

CUSTOMER_ID = 555123456
customer_user = {
    "id": CUSTOMER_ID,
    "username": "test_mijoz",
    "first_name": "Test",
    "last_name": "Mijoz",
    "photo_url": "https://t.me/i/userpic/320/small",
}
cust_init = make_init_data(SMOKE_BOT_TOKEN, customer_user)

# --- 3a) haqiqiy imzo bilan kirish ---
status, body = get_auth("/api/me", cust_init)
check(status == 200, f"imzo bilan /api/me 200 (natija: {status})")
if status == 200:
    try:
        d = json.loads(body)
        me = d.get("user") or {}
        # 🔴 ASOSIY TEKSHIRUV: foydalanuvchi ID'si IMZODAN olinadi
        check(me.get("id") == CUSTOMER_ID,
              f"ID imzodan keldi ({me.get('id')}), admin emas")
        check(me.get("username") == "test_mijoz", "username imzodan keldi")
        check(me.get("photo_url", "").startswith("https://t.me/i/userpic/"),
              "profil rasm havolasi saqlandi")
        # Yangi mijoz 0 dan boshlanishi SHART (eskida admin 357 813 UZS
        # olardi, chunki `targetId === DEFAULT_USER_ID ? 357813 : 0`)
        check(float(me.get("balance") or 0) == 0.0,
              "yangi mijoz balansi 0 (eskida 357813 UZS berilardi)")
        c = d.get("contest") or {}
        print(f"      konkurs: active={c.get('active')} "
              f"prize={c.get('prize_stars')} g'ol={c.get('winners')} "
              f"min={c.get('min')}")
        check(bool(c.get("text")), "konkurs matni bor")
    except Exception as exc:  # noqa: BLE001
        check(False, f"/api/me JSON emas: {exc}")

# --- 3b) header YO'Q -> 401 (admin emas!) ---
status, body = get_auth("/api/me")
check(status == 401, f"header yo'q -> 401 (natija: {status})")
check("dilbek" not in body and "normuzb" not in body,
      "javobda admin ma'lumoti yo'q")

# --- 3c) soxta `x-telegram-user-id` -> rad (spoof) ---
status, _ = get_auth("/api/me", "", {"x-telegram-user-id": "8307046273"})
check(status == 401, f"soxta x-telegram-user-id (admin) -> 401 (natija: {status})")
status, _ = get_auth("/api/me", "", {"x-telegram-user-id": "0"})
check(status == 401, f"'0' id -> 401 (natija: {status})")
status, _ = get_auth("/api/me", "", {"x-telegram-user-id": "-5"})
check(status == 401, f"manfiy id -> 401 (natija: {status})")

# --- 3d) imzo buzilgan (tampered) -> rad ---
bad = cust_init.replace("hash=", "hash=0")[:-40] + "0" * 8
status, _ = get_auth("/api/me", bad)
check(status == 401, f"buzilgan imzo -> 401 (natija: {status})")

# --- 3e) boshqa tokenga imzo -> rad ---
foreign = make_init_data("999999:OTHER_TOKEN", customer_user)
status, _ = get_auth("/api/me", foreign)
check(status == 401, f"boshqa bot tokenga imzo -> 401 (natija: {status})")

# --- 3f) `?uid=` query parami -> rad ---
status, _ = get_auth("/api/me?uid=8307046273")
check(status == 401, f"?uid=<admin> -> 401 (natija: {status})")

# --- 3g) eskirgan initData -> rad ---
old_data = make_init_data(SMOKE_BOT_TOKEN, customer_user,
                          auth_date=int(time.time()) - 999999)
status, _ = get_auth("/api/me", old_data)
check(status == 401, f"eskirgan initData -> 401 (natija: {status})")

# --- 3h) haqiqiy mijoz boshqa mijozning to'lovini ko'ra olmaydi ---
write_db({
    "users": {
        str(CUSTOMER_ID): {"id": CUSTOMER_ID, "username": "test_mijoz",
                           "balance": 50000, "total_spent": 0},
        "777000111": {"id": 777000111, "username": "boshqa", "balance": 1000},
    },
    "topups": {
        "tp_boshqa": {"id": "tp_boshqa", "user_id": 777000111, "amount": 30000,
                      "amount_to_send": 30001, "status": "pending",
                      "card": "9860 1701 1569 3682", "holder": "BOSHA QA",
                      "created_at": "2026-01-01T00:00:00"},
    },
    "orders": {}, "settings": {}, "nfts": [],
})
status, body = get_auth("/api/topup/status?id=tp_boshqa", cust_init)
check(status == 403, f"boshqa mijozning to'lovi -> 403 (natija: {status})")
check("9860" not in body, "karta raqami sizga ko'rinmadi")

# --- 3i) o'z to'lovingizni ko'rasiz ---
status, body = get_auth("/api/topup/status?id=tp_boshqa",
                        make_init_data(SMOKE_BOT_TOKEN,
                                       {"id": 777000111, "username": "boshqa"}))
check(status == 200, f"o'z to'lovingizni ko'rasiz -> 200 (natija: {status})")

print()
print("=" * 68)
print("4) Statistikа endpointlari ishlaydimi?")
print("=" * 68)
# /api/rate TASHQI API (CoinGecko/Frankfurter) ga murojaat qiladi —
# test muhitida internet yo'q bo'lishi mumkin. Shuning uchun uning
# uchun 0 (timeout) ham qabul qilinadi: bu MAHSUL xatosi emas.
EXTERNAL = {"/api/rate"}
for path in ("/api/health", "/api/rate", "/api/ranking", "/api/me",
             "/api/admin/contest"):
    st, _ = get(path)
    if path in EXTERNAL and st == 0:
        print(f"  ➖ {path} -> 0 (tashqi API javob bermadi — mahalliy muammo emas)")
        continue
    check(st in (200, 401, 403), f"{path} -> {st}")

print()
print("=" * 68)
print("5) 🔴 NFT: admin qo'shgandan KEYIN WebApp'da ko'rinadimi?")
print("=" * 68)
# Xabar berilgan xata: "/admin orqali nft qo'shdim. Lekin WebAppda
# ko'rinmayapti rasmi bilan."
#
# Sabab: `store.nfts` faqat BOOT da o'qilardi. Admin keyin NFT
# qo'shsa, server ESKI (bo'sh) ro'yxatni qaytarib berardi va
# WebApp hech narsa ko'rmasdi.
# Bu test aynan shuni takrorlaydi: server ISHLAB turib DB ga NFT
# yoziladi, keyin /api/nfts chaqiriladi.

base_db = {"settings": {"bot_active": True}, "users": {}, "orders": {},
           "topups": {}, "nfts": {}, "contest": {}}
write_db(base_db)
time.sleep(3.5)  # server ning o'z keshi (mtime) yangilanishini kutamiz

status, body = get("/api/nfts")
check(status == 200, "/api/nfts 200")
try:
    check(json.loads(body).get("items") == [], "boshida ro'yxat bo'sh")
except Exception as exc:  # noqa: BLE001
    check(False, f"JSON emas: {exc}")

# --- Mana xataning o'zgartirilgan ko'rinishi ---
db1 = {**base_db, "nfts": {"nft_p1": {
    "id": "nft_p1", "title": "Jack-in-the-Box", "number": 22810,
    # admin Telegram'dan RASM yuborgan — bu Telegram file_id
    "image": "AgACAgIAAxkBAAIBq0Zk3Rt5nq7ZqZqZq0Zq0Zq0Zq",
    "link": "https://t.me/nft/JackInTheBox",
    "daily": 84, "active": True}}}
write_db(db1)
time.sleep(3.5)
status, body = get("/api/nfts")
try:
    items = json.loads(body).get("items", [])
except Exception as exc:  # noqa: BLE001
    items = []
    check(False, f"JSON emas: {exc}")
check(len(items) == 1,
      f"YANGI NFT ko'rindi ({len(items)} ta) — server yosharmagan")
if items:
    n = items[0]
    check(n.get("title") == "Jack-in-the-Box", f"nom to'g'ri: {n.get('title')}")
    check(n.get("number") == 22810, f"raqam to'g'ri: {n.get('number')}")
    check(n.get("daily") == 84, f"1 kunlik narx to'g'ri: {n.get('daily')}")
    # file_id brauzerda ochilmaydi — server proxy orqali berishi SHART
    check(n.get("image") == "/api/nft-image/nft_p1",
          f"file_id -> PROXY yo'l: {n.get('image')}")

# Rasm turlari to'g'ri talqin qilinadimi
db2 = {**base_db, "nfts": {
    "nft_url": {"id": "nft_url", "title": "URL rasm", "number": 1,
                "image": "https://cdn.example.com/a.jpg", "link": "",
                "daily": 50, "active": True},
    "nft_pg": {"id": "nft_pg", "title": "T.me sahifasi", "number": 2,
               "image": "t.me/nft/SomeGift", "link": "t.me/nft/SomeGift",
               "daily": 60, "active": True},
    "nft_off": {"id": "nft_off", "title": "O'chirilgan", "number": 3,
                "image": "https://x.com/b.jpg", "link": "", "daily": 10,
                "active": False},
}}
write_db(db2)
time.sleep(3.5)
status, body = get("/api/nfts")
try:
    items = {i["id"]: i for i in json.loads(body).get("items", [])}
except Exception as exc:  # noqa: BLE001
    items = {}
    check(False, f"JSON emas: {exc}")
check("nft_off" not in items, "active:false NFT chiqariladi")
check(items.get("nft_url", {}).get("image") == "https://cdn.example.com/a.jpg",
      "https havolа to'g'ridan-to'g'ri qaytariladi")
check(items.get("nft_pg", {}).get("image") == "",
      "t.me/nft/... linki rasm EMAS -> bo'sh (placeholder)")

# quote ham yangi NFT ni ko'rishi kerak
write_db({**base_db, "nfts": {"nft_q": {
    "id": "nft_q", "title": "Quote test", "number": 7,
    "image": "https://x.com/c.jpg", "link": "", "daily": 84, "active": True}}})
time.sleep(3.5)
# 🔐 `/api/nfts/quote` mijoz balansini ham qaytaradi — imzo talab qiladi.
# (Avval `get()` bilan chaqirilardi va 200 kutardi; endi 401 keladi.)
status, body = get_auth("/api/nfts/quote?id=nft_q&days=7", cust_init)
check(status == 200, "/api/nfts/quote 200")
try:
    j = json.loads(body)
    q = j.get("quote", {})
    check(j.get("ok") is True, "quote ok")
    check(q.get("per_day") == 84, f"1 kunlik = {q.get('per_day')}")
    check(q.get("rent") == 588, f"ijara (7 kun) = {q.get('rent')}")
    check(q.get("network_fee") == 2000, f"network fee = {q.get('network_fee')}")
    check(q.get("total") == 2588, f"JAMI = {q.get('total')}")
except Exception as exc:  # noqa: BLE001
    check(False, f"JSON emas: {exc}")

# Proxy endpoint
write_db(db1)
time.sleep(3.5)
status, _ = get("/api/nft-image/nft_p1")
# Test tokeni fake — Telegram 404 beradi. Muhim bo'lgani: endpoint
# CRASH qilmasin (500 / istisno yo'q).
check(status in (302, 404), f"/api/nft-image/nft_p1 -> {status} (302/404)")
status, _ = get("/api/nft-image/nonexistent")
check(status == 404, f"yo'q NFT -> 404 ({status})")
status, _ = get("/api/nft-image/nft_pg")
check(status == 404, f"t.me linki (rasm emas) -> 404 ({status})")

for _sfx in ("", ".bak", ".tmp"):
    _p = DB_PATH + _sfx
    if os.path.exists(_p):
        os.remove(_p)

print()
print("=" * 68)
print("NATIJA:", "✅ BARCHASI TO'G'RI" if ok else "❌ MUAMMO BOR")
print("=" * 68)
sys.exit(0 if ok else 1)