"""server.ts HAQIQATAN ISHGA TUSHADIMI?

Nima uchun bu test kerak:
  `npm run build` va `tsc --noEmit` TypeScript sintaksisini tekshiradi,
  LEKIN runtime xatolarini (masalan TDZ — "Cannot access 'X' before
  initialization") YO'Q. O'xshash xato production'da serverni butunlay
  o'ldirdi: "Server crashed" — bot ishlagan, lekin WebApp butunlay o'lik.

  Bu test server.ts ni haqiqiy ishga tushirib, barcha endpoint'lar
  javob berishini tekshiradi.
"""
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Dinamik port: avvalgi test qoldirgan server bilan to'qnashuvni
# oldini oladi (masalan 24678 — Vite HMR porti band bo'lishi mumkin)
PORT = int(os.environ.get("SMOKE_PORT") or (4600 + (os.getpid() % 400)))
BASE = f"http://127.0.0.1:{PORT}"
DB_PATH = "/tmp/_t_smoke_server.json"


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
    "BOT_TOKEN": "123456:TEST_TOKEN_FOR_SMOKE_ONLY",
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
print("3) Konkurs WebApp uchun OCHILGANMI?")
print("=" * 68)
status, body = get("/api/health")
check(status == 200, "/api/health 200")
try:
    st = json.loads(body)
    check(st.get("ok") is True, "health ok")
except Exception as exc:  # noqa: BLE001
    check(False, f"health JSON emas: {exc}")

# /api/me — konkursni ko'rsatadi
status, body = get("/api/me")
check(status == 200, "/api/me 200")
if status == 200:
    try:
        d = json.loads(body)
        c = d.get("contest") or {}
        print(f"      konkurs: active={c.get('active')} "
              f"prize={c.get('prize_stars')} g'ol={c.get('winners')} "
              f"min={c.get('min')}")
        check(bool(c.get("text")), "konkurs matni bor")
        check(c.get("active") is True, "konkurs FAOL (active=true)")
        check((c.get("prize_stars") or 0) > 0, "sovqa berilgan")
        check("yaratilmagan" not in str(c.get("text")),
              "placeholder emas — haqiqiy konkurs")
    except Exception as exc:  # noqa: BLE001
        check(False, f"store JSON emas: {exc}")

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
status, body = get("/api/nfts/quote?id=nft_q&days=7")
check(status == 200, "/api/nfts/quote 200")
try:
    j = json.loads(body)
    q = j.get("quote", {})
    check(j.get("ok") is True, "quote ok")
    check(q.get("per_day") == 84, f"1 kunlik = {q.get('per_day')}")
    check(q.get("rent") == 588, f"ijara (7 kun) = {q.get('rent')}")
    check(q.get("network_fee") == 1700, f"network fee = {q.get('network_fee')}")
    check(q.get("total") == 2288, f"JAMI = {q.get('total')}")
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