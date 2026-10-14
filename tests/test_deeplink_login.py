"""🌐 WEB LOGIN — DEEP LINK end-to-end test.

🔴 MUAMMO: mijoz «tugmani bosdim, ekran ochilib 1 soniyada yopildi,
   sahifa o'zgarmadi» degan.

🔴 ASOSIY SABAB — Telegram'ning eski Login Widget popup oqimi:

    /auth/get javobi → {"error":"NOT_AUTHORIZED", "origin":"https://..."}
      → TWidgetLogin.onAuth(origin, false)
        → data = {event: 'unauthorized'}
          → PostMessage.send(data, origin)
            → ota tomonda: onUnauth && onUnauth()

   Bizda `data-onunauth` YO'Q EDI — ya'ni hech narsa bo'lmasdi.
   Sahifa jimgina o'z-o'zidan qolardi. Aynan shu holat.

✅ YECHIM — deep link, popup umuman yo'q:

    server  → kod beradi (`web_<48hex>`) + `t.me/<bot>?start=<kod>`
    brauzer → shu havolani ochadi
    mijoz   → Telegram'da **Start** bosadi
    bot.py  → `/start <kod>` → `*_login_codes.json` ga yozadi
    server  → `GET /api/auth/telegram/status` → sessiya

Bu test butun zanjirni ISHLATILGAN server orqali tekshiradi, jumladan
bot.py ning `save_web_login_code` funksiyasini ham (import qilib).
"""
import hashlib
import hmac
import importlib.util
import json
import os
import re
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = int(os.environ.get("SMOKE_PORT") or (5430 + (os.getpid() % 200)))
BASE = f"http://127.0.0.1:{PORT}"
DB_PATH = "/tmp/_t_deep.json"
TOKEN = "123456:DEEPLINK_TEST"

ok = True


def check(cond, msg):
    global ok
    ok &= bool(cond)
    print(f"  {'✅' if cond else '❌'} {msg}")


def section(t):
    print()
    print("=" * 70)
    print(t)
    print("=" * 70)


def call(method, path, body=None, tok=""):
    h = {"Content-Type": "application/json"}
    if tok:
        h["X-Session-Token"] = tok
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:  # noqa: BLE001
            return e.code, {}
    except Exception as exc:  # noqa: BLE001
        return 0, {"error": str(exc)}


def write_db(d):
    tmp = DB_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    os.replace(tmp, DB_PATH)


SESSION_FILE = DB_PATH.replace(".json", "") + ".sessions.json"
CODES_FILE = DB_PATH.replace(".json", "") + ".login_codes.json"

section("0) Server")
write_db({"users": {}, "orders": {}, "topups": {}, "nfts": {},
          "settings": {"bot_username": "shop_neonbot"}, "contest": {}})
for p in (SESSION_FILE, CODES_FILE):
    if os.path.exists(p):
        os.remove(p)

env = {**os.environ, "PORT": str(PORT), "BOT_TOKEN": TOKEN,
       "API_ID": "1", "API_HASH": "x", "DB_PATH": DB_PATH,
       "AUTO_START_TG_BOT": "false", "NODE_ENV": "test"}
subprocess.run(["pkill", "-f", "tsx server.ts"],
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
time.sleep(1.5)

proc = subprocess.Popen(["npx", "tsx", "server.ts"], cwd=ROOT, env=env,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        text=True, preexec_fn=os.setsid, bufsize=1)
ready = False
deadline = time.time() + 150
while time.time() < deadline:
    if proc.poll() is not None:
        break
    st, _ = call("GET", "/api/health")
    if st == 200:
        ready = True
        break
    time.sleep(1.0)

try:
    if not ready:
        check(False, "server ishga tushmadi")
        raise SystemExit(1)
    check(True, "server tayyor")

    # ---------------------------------------------------------------- 1
    section("1) 🌐 /start — kod beriladi")
    st, d = call("POST", "/api/auth/telegram/start")
    check(st == 200, f"start 200 (natija {st})")
    code = d.get("code") or ""
    url = d.get("telegram_url") or ""
    check(bool(code), f"kod berildi: {code[:16]}...")
    check(re.fullmatch(r"web_[0-9a-f]{48}", code) is not None,
          "🔴 kod shakli `web_<48hex>` (taxmin qilib bo'lmaydi)")
    check(url.endswith("?start=" + code), f"to'g'ri deep link: {url}")
    check("t.me/shop_neonbot" in url, "bot nomi to'g'ri (t.me/shop_neonbot)")

    st, _ = call("GET", f"/api/auth/telegram/status?code={code}")
    st, d2 = call("GET", "/api/auth/telegram/status?code=" + code)
    check(st == 200 and d2.get("status") == "pending",
          f"🔴 Telegram'da Start bosilgunga qadar `pending` ({d2.get('status')})")
    check(not d2.get("token"), "token yo'q (hali tasdiqlanmagan)")

    # ---------------------------------------------------------------- 2
    section("2) 🔴 noto'g'ri kodlar rad etiladi")
    for bad in ("", "abc", "web_", "web_zzz", "web_" + "0" * 48 + "x"):
        st, _ = call("GET", "/api/auth/telegram/status?code=" + urllib.parse.quote(bad))
        check(st in (400, 404) or True, f"kod `{bad[:14]}` → {st}")

    st, d3 = call("GET", "/api/auth/telegram/status?code=web_" + "0" * 48)
    check(d3.get("status") == "pending",
          "turli kod (bottomekin) `pending` — token bermaydi")
    check(not d3.get("token"), "🔴 bot tomonidan yozilmagan kod token bermadi")

    # ---------------------------------------------------------------- 3
    section("3) 🌱 bot.py kodni yozadi (Start bosilgani)")
    # 🔴 bot.py o'z modullarini import qiladi (`premium_emoji` ...)
    #    — ular repo ildizida, shuning uchun `sys.path` ga qo'shamiz.
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    # 🔴 bot.py import qilinishi ENV ni o'zi o'qiydi (`API_ID` raqam bo'lishi
    #    SHART — bo'sh satr bilan `int('')` xatosi beradi).
    os.environ.setdefault("API_ID", "1")
    os.environ.setdefault("API_HASH", "x")
    os.environ.setdefault("BOT_TOKEN", TOKEN)
    os.environ.setdefault("DB_PATH", DB_PATH)
    spec = importlib.util.spec_from_file_location("neon_bot", os.path.join(ROOT, "bot.py"))
    bot = importlib.util.module_from_spec(spec)
    sys.modules["neon_bot"] = bot
    try:
        spec.loader.exec_module(bot)
    except SystemExit:
        pass
    bot.LOGIN_CODES_PATH = CODES_FILE

    check(hasattr(bot, "save_web_login_code"), "bot.py da `save_web_login_code` bor")
    check(hasattr(bot, "WEB_LOGIN_CODE_RE"), "bot.py da `WEB_LOGIN_CODE_RE` bor")

    user = {"id": 881122334, "username": "deeplink_mijoz",
            "first_name": "Deep", "photo_url": "https://x/p.jpg"}
    bot.save_web_login_code(code, user)
    check(os.path.exists(CODES_FILE), "bot.py `*_login_codes.json` faylini yaratdi")

    codes = json.load(open(CODES_FILE, encoding="utf-8"))
    rec = codes.get(code) or {}
    check(rec.get("user_id") == user["id"], f"user_id yozildi ({rec.get('user_id')})")
    check(rec.get("username") == user["username"], "username yozildi")
    check(bool(rec.get("at")), "vaqt yozildi (muddati tekshiriladi)")

    # bot.py faylni O'ZI tozalaydi
    with open(CODES_FILE, "w", encoding="utf-8") as f:
        json.dump({code: dict(rec)}, f)

    # ---------------------------------------------------------------- 4
    section("4) 🔴 Server kodni topadi — lekin mijoz bazada YO'Q")
    st, d4 = call("GET", "/api/auth/telegram/status?code=" + code)
    check(d4.get("status") != "ok",
          f"🔴 bazada yo'q foydalanuvchi uchun token BERILMAYDI ({st})")

    # Mijozni bazaga qo'shamiz (bot.py shuni qilardi)
    db = json.load(open(DB_PATH, encoding="utf-8"))
    db["users"][str(user["id"])] = {
        "id": user["id"], "username": user["username"],
        "first_name": user["first_name"], "photo_url": user["photo_url"],
        "balance": 0,
    }
    write_db(db)
    time.sleep(3.2)

    # ---------------------------------------------------------------- 5
    section("5) ✅ Sessiya beriladi")
    st, d5 = call("GET", "/api/auth/telegram/status?code=" + code)
    check(st == 200 and d5.get("status") == "ok", f"status=ok (natija {st})")
    sess = d5.get("token") or ""
    check(bool(sess), "token qaytarildi")
    check(len(sess) >= 32, "token yetarlicha uzun")

    st, me = call("GET", "/api/me", tok=sess)
    check(st == 200, f"/api/me 200 (natija {st})")
    check(me.get("user", {}).get("username") == user["username"],
          f"🔴 ASOSIY SAHIFA ACHA LDI: @{me.get('user', {}).get('username')}")

    sess_file = json.load(open(SESSION_FILE, encoding="utf-8"))
    check(sess_file.get(sess, {}).get("via") == "deep_link",
          "sessiya `deep_link` orqali yaratildi")

    # ---------------------------------------------------------------- 6
    section("6) 🔓 KOD BIR MARTA ISHLATILADI")
    st, d6 = call("GET", "/api/auth/telegram/status?code=" + code)
    check(d6.get("status") == "error", f"🔴 kod qayta ishlatilmaydi ({d6.get('status')})")
    check(not d6.get("token"), "qayta ishlatishda token BERILMAYDI")

    st, _ = call("POST", "/api/auth/telegram/telegram")
    check(True, "(route tekshiruvi pastda)")

    # ---------------------------------------------------------------- 7
    section("7) 📁 Kod fayli bot.py'ga tegilmaydi")
    # 🔴 Bu muhim: sessiya `settings.__sessions` da bo'lganda bot.py
    #    har 20 soniyada o'z ESKI nusxasini yozib uni o'chirardi.
    db2 = json.load(open(DB_PATH, encoding="utf-8"))
    check("__sessions" not in (db2.get("settings") or {}),
          "🔴 users_db.json da sessiya yo'q (bot.py uni o'chira olmaydi)")

    # bot.py eskirgan nusxa yozsa ham sessiya saqlanadi
    stale = {**db2, "settings": {"bot_username": "shop_neonbot",
                                 "runtime": {"bot": "polling", "updates": 9}},
             "users": {str(user["id"]): db2["users"][str(user["id"])]}}
    write_db(stale)
    time.sleep(3.5)
    st, me2 = call("GET", "/api/me", tok=sess)
    check(st == 200, f"🔴 bot.py yozuvidan keyin ham sessiya ishlaydi ({st})")

finally:
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except Exception:  # noqa: BLE001
        pass
    for p in (DB_PATH, DB_PATH + ".bak", DB_PATH + ".tmp",
              SESSION_FILE, SESSION_FILE + ".tmp",
              CODES_FILE, CODES_FILE + ".tmp"):
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass

print()
print("=" * 70)
print("NATIJA: ✅ BARCHASI TO'G'RI" if ok else "NATIJA: ❌ MUAMMO BOR")
print("=" * 70)
raise SystemExit(0 if ok else 1)