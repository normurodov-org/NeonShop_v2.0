"""🔐 BROWSER KIRISH (Telegram Login Widget) + SESSIYA.

🔴 NIMA UCHUN BU TEST KERAK:
  * WebApp ichida `initData` bo'ladi — mijoz hech narsa bosmaydi
  * Brauzerda (kompyuter / planshet) `initData` YO'Q — ilova
    «Telegram orqali kiring» ekranida QOLARDI va hech qanday xizmat
    ishlamasdi. Bu mijozning so'rovi edi.
  * Yechim: Telegram'ning rasmiy Login Widget + server tomonda
    SHA256(bot_token) kaliti bilan imzo tekshiruvi.

🔴 DIQQAT — IKKALA KALIT HAM FARQ QILADI:
    WebApp initData : secret = HMAC_SHA256(bot_token, "WebAppData")
    Login Widget    : secret = SHA256(bot_token)
  Agar biri ikkinchisi qo'llansa, hamma brauzer kirishlari rad bo'ladi.

Test HAQIQIY imzo yasaydi va server tomonidan qabul qilinishini,
rad qilinishini ham tekshiradi.
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
PORT = int(os.environ.get("SMOKE_PORT") or (5100 + (os.getpid() % 300)))
BASE = f"http://127.0.0.1:{PORT}"
DB_PATH = "/tmp/_t_login.json"
TOKEN = "123456:LOGIN_WIDGET_TEST_TOKEN"

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


# ---------------------------------------------------------------- imzolar
def widget_data(bot_token: str, user: dict, auth_date: int = 0,
                secret_style: str = "sha256", bad_hash: bool = False) -> str:
    """Telegram Login Widget ma'lumotini HAQIQIY imzo bilan yasaydi."""
    f = {
        "id": str(user["id"]),
        "first_name": user.get("first_name", ""),
        "username": user.get("username", ""),
        "photo_url": user.get("photo_url", ""),
        "auth_date": str(auth_date or int(time.time())),
    }
    dcs = "\n".join(f"{k}={f[k]}" for k in sorted(f))
    if secret_style == "sha256":
        secret = hashlib.sha256(bot_token.encode()).digest()
    else:  # ❌ noto'g'ri: WebApp kaliti
        secret = hmac.new(b"WebAppData", bot_token.encode(),
                          hashlib.sha256).digest()
    sig = hmac.new(secret, dcs.encode(), hashlib.sha256).hexdigest()
    if bad_hash:
        sig = "0" * len(sig)
    parts = [f"{k}={urllib.parse.quote(f[k], safe='')}" for k in sorted(f)]
    parts.append("hash=" + sig)
    return "&".join(parts)


def webapp_init(user: dict, bot_token: str = TOKEN) -> str:
    """WebApp initData (boshqa kalit) — aralashtirib yuborilmasligini
    tekshirish uchun."""
    f = {"auth_date": str(int(time.time())),
         "user": json.dumps(user, separators=(",", ":"))}
    dcs = "\n".join(f"{k}={f[k]}" for k in sorted(f))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    sig = hmac.new(secret, dcs.encode(), hashlib.sha256).hexdigest()
    parts = [f"{k}={urllib.parse.quote(f[k], safe='')}" for k in sorted(f)]
    parts.append("hash=" + sig)
    return "&".join(parts)


def call(method: str, path: str, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    h = {"Content-Type": "application/json"}
    h.update(headers or {})
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


# ---------------------------------------------------------------- server
section("0) Server")
env = {
    **os.environ, "PORT": str(PORT), "BOT_TOKEN": TOKEN,
    "API_ID": "1", "API_HASH": "x", "DB_PATH": DB_PATH,
    "AUTO_START_TG_BOT": "false", "NODE_ENV": "test",
}
subprocess.run(["pkill", "-f", "tsx server.ts"],
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
time.sleep(1.5)

for sfx in ("", ".bak", ".tmp"):
    if os.path.exists(DB_PATH + sfx):
        os.remove(DB_PATH + sfx)
write_db({"users": {}, "orders": {}, "topups": {}, "nfts": {},
          "settings": {}, "contest": {}})

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
    section("1) 🔐 LOGIN WIDGET — SHA256(bot_token) kaliti")
    user = {"id": 770011122, "username": "brauzer_mijoz",
            "first_name": "Brauzer", "photo_url": "https://t.me/i/userpic/320/s"}

    st, d = call("POST", "/api/auth/telegram",
                 {"data": widget_data(TOKEN, user)})
    check(st == 200, f"haqiqiy imzo -> 200 (natija {st}: {d.get('error','')})")
    sess = d.get("token") or ""
    check(bool(sess), f"sessiya token qaytarildi ({len(sess)} belgi)")
    check(d.get("user", {}).get("username") == "brauzer_mijoz",
          "foydalanuvchi bazaga yozildi")

    # ---------------------------------------------------------------- 2
    section("2) 🔴 KALIT ARALASHMASI — ikkalasi ham rad bo'lishi SHART")
    st, _ = call("POST", "/api/auth/telegram",
                 {"data": widget_data("999:OTHER", user)})
    check(st == 401, f"boshqa bot tokenga imzo -> 401 (natija {st})")

    st, _ = call("POST", "/api/auth/telegram",
                 {"data": widget_data(TOKEN, user, secret_style="webapp")})
    check(st == 401,
          f"🔴 WebApp kaliti (HMAC WebAppData) -> 401 (natija {st})")

    st, _ = call("POST", "/api/auth/telegram",
                 {"data": widget_data(TOKEN, user, bad_hash=True)})
    check(st == 401, f"buzilgan hash -> 401 (natija {st})")

    st, _ = call("POST", "/api/auth/telegram",
                 {"data": widget_data(TOKEN, user, auth_date=int(time.time()) - 999999)})
    check(st == 401, f"eskirgan kirish -> 401 (natija {st})")

    st, _ = call("POST", "/api/auth/telegram", {"data": ""})
    check(st == 401, f"bo'sh ma'lumot -> 401 (natija {st})")

    # ---------------------------------------------------------------- 3
    section("3) 🔐 SESSIYA bilan ishlash — barcha mijoz endpoint'lari")
    st, d = call("GET", "/api/me", headers={"X-Session-Token": sess})
    check(st == 200, f"/api/me sessiya bilan -> 200 (natija {st})")
    check(d.get("user", {}).get("username") == "brauzer_mijoz",
          "🔴 BRAUZERDA MIJOZ KO'RINDI (admin emas)")
    check(float(d.get("user", {}).get("balance") or 0) == 0.0,
          "balans 0 dan boshlanadi")

    st, _ = call("GET", "/api/me")
    check(st == 401, f"sessiya yo'q -> 401 (natija {st})")

    st, _ = call("GET", "/api/me", headers={"X-Session-Token": "nomiqoztoken"})
    check(st == 401, f"soxta token -> 401 (natija {st})")

    st, d = call("POST", "/api/topup", {"amount": 50000},
                 headers={"X-Session-Token": sess})
    check(st == 200, f"to'lov so'rovi sessiya bilan -> 200 (natija {st})")

    st, d = call("POST", "/api/order",
                 {"kind": "stars", "amount": 100, "username": "durov"},
                 headers={"X-Session-Token": sess})
    check(st == 402,
          f"balans yetarli emas -> 402 (natija {st}) — xarid rad etiladi")

    # admin endpoint'lari sessiya bilan ISHLAMASIN
    st, _ = call("GET", "/api/admin/data", headers={"X-Session-Token": sess})
    check(st == 401, f"🔴 oddiy sessiya admin bo'lmaydi -> 401 (natija {st})")

    # ---------------------------------------------------------------- 4
    section("4) 🔴 WEBAPP IMZOSI LOGIN WIDGET KALITI EMAS")
    # WebApp initData -> /api/auth/telegram uchun ishlatilmasin
    st, _ = call("POST", "/api/auth/telegram", {"data": webapp_init(user)})
    check(st == 401,
          f"🔴 WebApp initData login uchun -> 401 (natija {st})")

    # lekin /api/me uchun ISHLASHI kerak
    st, d = call("GET", "/api/me",
                 headers={"X-Telegram-Init-Data": webapp_init(user)})
    check(st == 200, f"WebApp initData /api/me uchun -> 200 (natija {st})")

    # ---------------------------------------------------------------- 7
    section("7) 💾 SESSIYA bazada saqlanadimi? (redeploy'dan keyin)")
    db = json.load(open(DB_PATH, encoding="utf-8"))
    sessions = (db.get("settings") or {}).get("__sessions") or {}
    check(len(sessions) >= 1,
          f"sessiya bazaga yozildi ({len(sessions)} ta) — redeploy'da yo'qolmaydi")
    if sessions:
        rec = list(sessions.values())[0]
        check(rec.get("expires_at"), "muddati bor")
        check(rec.get("via") == "login_widget", "manbai belgilangan")

    # ---------------------------------------------------------------- 5
    section("6) 🚪 LOGOUT")
    st, _ = call("POST", "/api/auth/logout", headers={"X-Session-Token": sess})
    check(st == 200, f"logout -> 200 (natija {st})")
    st, _ = call("GET", "/api/me", headers={"X-Session-Token": sess})
    check(st == 401, f"🔴 logout'dan keyin token ishlamaydi -> 401 (natija {st})")

    # ---------------------------------------------------------------- 6
    section("7) ⚙️ /api/config — bot nomi")
    st, d = call("GET", "/api/config")
    check(st == 200, f"/api/config -> 200 (natija {st})")
    check("bot_username" in d,
          "bot_username maydoni bor (test token -> getMe ishlamaydi, "
          "bo'sh bo'lishi mumkin)")
finally:
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except Exception:  # noqa: BLE001
        pass
    for sfx in ("", ".bak", ".tmp"):
        if os.path.exists(DB_PATH + sfx):
            try:
                os.remove(DB_PATH + sfx)
            except OSError:
                pass

print()
print("=" * 70)
print("NATIJA: ✅ BARCHASI TO'G'RI" if ok else "NATIJA: ❌ MUAMMO BOR")
print("=" * 70)
raise SystemExit(0 if ok else 1)