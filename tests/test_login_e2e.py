"""🔐 TELEGRAM LOGIN — end-to-end test (rasmiy OAuth, popup'siz).

🔴🔴 BU TEST NIMANI ISHLAMASLIGINI QAYT BERADI:

Eski yechim — Telegram'ning `telegram-widget.js` skripti popup ochadi va
`checkClose()` bilan `popup.closed` ni kuzatadi:

    function checkClose() {
      if (!activePopup || activePopup.closed) {
        return TWidgetLogin.onClose();   // → getAuth() XHR
      }
      setTimeout(checkClose, 100);
    }

Popup bir zumda yopilgan deb hisoblansa → `getAuth()` → `NOT_AUTHORIZED`
→ `authFinished = true` → butun oqim o'ladi:

    tugma bosiladi → popup ochiladi → yopiladi → HECH NARSA

✅ Yangi yechim — rasmiy OAuth sahifasi:

    1. https://oauth.telegram.org/auth?bot_id=…&origin=…&return_to=…
    2. Mijoz tasdiqlaydi
    3. Telegram `return_to#tgAuthResult=<base64url(JSON)>` ga qaytaradi
    4. Qaytishni o'zimiz o'qib, `/api/auth/telegram` ga yuboramiz

Bu test server tomonidagi **to'liq zanjir**ni tekshiradi:
base64url decode → query string → `SHA256(bot_token)` imzo →
sessiya yaratish → `X-Session-Token` bilan `/api/me`.
"""
import base64
import hashlib
import hmac
import json
import os
import signal
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = int(os.environ.get("SMOKE_PORT") or (5630 + (os.getpid() % 200)))
BASE = f"http://127.0.0.1:{PORT}"
DB_PATH = "/tmp/_t_login.json"
TOKEN = "123456:LOGIN_E2E"
BOT_ID = 8604259613

ok = True


def check(cond, msg):
    global ok
    ok &= bool(cond)
    print("  " + ("✅" if cond else "❌") + " " + msg)


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


def sign(user: dict) -> str:
    """🔐 Telegram'ning rasmiy imzosi: `SHA256(bot_token)` kaliti."""
    dcs = "\n".join(f"{k}={user[k]}" for k in sorted(user))
    secret = hashlib.sha256(TOKEN.encode()).digest()
    return hmac.new(secret, dcs.encode(), hashlib.sha256).hexdigest()


def to_fragment(user: dict) -> str:
    """🔴 Telegram qaytaradigan `#tgAuthResult` — base64url(JSON)."""
    raw = json.dumps({**user, "hash": sign(user)}, separators=(",", ":")).encode()
    return base64.b64encode(raw).decode().replace("+", "-").replace("/", "_").replace("=", "")


def from_fragment(frag: str) -> str:
    """🔴 Frontend'ning `readTelegramAuthResult()` logikasi (server parse qiladi)."""
    b64 = frag.replace("-", "+").replace("_", "/")
    pad = len(b64) % 4
    if pad > 1:
        b64 += "=" * (5 - pad)
    obj = json.loads(base64.b64decode(b64))
    keys = ["id", "first_name", "last_name", "username", "photo_url", "auth_date"]
    parts = [f"{k}={urllib.parse.quote(str(obj[k]))}"
             for k in keys if obj.get(k) is not None]
    parts.append(f"hash={urllib.parse.quote(str(obj['hash']))}")
    return "&".join(parts)


USER = {"id": 77002211, "first_name": "Malika", "username": "login_e2e",
        "photo_url": "", "auth_date": str(int(time.time()))}

# =============================================================================
section("0) Server")
# =============================================================================
json.dump({"users": {}, "orders": {}, "topups": {}, "nfts": [],
           "settings": {"bot_username": "shop_neonbot"}, "contest": {}},
          open(DB_PATH, "w", encoding="utf-8"), ensure_ascii=False)
sf = DB_PATH.replace(".json", "") + ".sessions.json"
if os.path.exists(sf):
    os.remove(sf)

env = {**os.environ, "PORT": str(PORT), "BOT_TOKEN": TOKEN, "API_ID": "1",
       "API_HASH": "x", "DB_PATH": DB_PATH, "AUTO_START_TG_BOT": "false",
       "NODE_ENV": "test"}
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
    if call("GET", "/api/health")[0] == 200:
        ready = True
        break
    time.sleep(1.0)

try:
    if not ready:
        check(False, "server ishga tushmadi")
        raise SystemExit(1)
    check(True, "server tayyor")

    # ================================================================= 1
    section("1) 🔴 `/api/config` — bot_id")
    st, cfg = call("GET", "/api/config")
    check(st == 200, f"/api/config 200 ({st})")
    check(cfg.get("bot_username") == "shop_neonbot", "bot nomi to'g'ri")
    # soxta token bilan getMe ishlamaydi -> bot_id 0, lekin maydon BO'LISHI SHART
    check("bot_id" in cfg, "🔴 `bot_id` maydoni qaytariladi (frontend shuni kutadi)")

    # ================================================================= 2
    section("2) 🔐 Telegram imzosi — rasmiy `SHA256(bot_token)`")
    frag = to_fragment(USER)
    check(bool(frag), "base64url(JSON) yaratildi")
    check("=" not in frag, "📌 base64url — `=` yo'q")
    data = from_fragment(frag)
    check("&" in data and "hash=" in data, "🔴 query string to'g'ri (`k=v&k=v`)")

    # ================================================================= 3
    section("3) 🔴🔴 NOTO'G'RI FORMAT — «hash yo'q»")
    bad = "\n".join(f"{k}={USER[k]}" for k in sorted(USER)) + f"\nhash={sign(USER)}"
    st, j = call("POST", "/api/auth/telegram", {"data": bad})
    check(st == 401, f"🔴 `k=v\\n` formatida RAD etiladi ({st})")

    # ================================================================= 4
    section("4) ✅ TO'G'RI QAYTISH — sessiya")
    st, j = call("POST", "/api/auth/telegram", {"data": data})
    check(st == 200 and j.get("ok"), f"🔴 qabul qilindi ({st})")
    sess = j.get("token") or ""
    check(bool(sess), "token qaytarildi")
    u = j.get("user") or {}
    check(u.get("id") == USER["id"], f"🔴 foydalanuvchi to'g'ri (@{u.get('username')})")
    check(u.get("balance") == 0, "balans 0 dan boshlanadi (pul yo'q)")

    st, me = call("GET", "/api/me", tok=sess)
    check(st == 200, f"/api/me 200 ({st})")
    check((me.get("user") or {}).get("username") == USER["username"],
          "🔴🔴 ASOSIY SAHIFA ACHA LDI")

    # ================================================================= 5
    section("5) 🔐 Soxta imzo rad etiladi")
    for name, mutate in [
        ("hash o'zgargan", lambda d: d.replace("hash=", "hash=0")),
        ("id o'zgargan", lambda d: d.replace(f"id={USER['id']}", "id=999")),
        ("hash yo'q", lambda d: "&".join(x for x in d.split("&") if not x.startswith("hash="))),
    ]:
        st, _ = call("POST", "/api/auth/telegram", {"data": mutate(data)})
        check(st == 401, f"🔴 {name} -> 401 (natija {st})")

    # ================================================================= 6
    section("6) 🔒 Eskirgan natija")
    st, _ = call("POST", "/api/auth/telegram",
                 {"data": from_fragment(to_fragment({**USER, "auth_date": "1"}))})
    check(st == 401, f"🔴 eskirgan `auth_date` rad etiladi ({st})")

    # ================================================================= 7
    section("7) 🚪 Logout")
    st, _ = call("POST", "/api/auth/logout", tok=sess)
    check(st == 200, "logout 200")
    st, _ = call("GET", "/api/me", tok=sess)
    check(st == 401, f"🔴 logout'dan keyin ishlamaydi ({st})")

    # ================================================================= 8
    section("8) 🔄 Qayta kirish (yangi token)")
    st, j2 = call("POST", "/api/auth/telegram", {"data": data})
    check(st == 200 and bool(j2.get("token")), "🔴 qayta kirish ishlaydi")
    s2 = j2.get("token") or ""
    check(s2 != sess, "📌 yangi token berildi")
    check(call("GET", "/api/me", tok=s2)[0] == 200, "🔴 yangi token ishlaydi")

finally:
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except Exception:  # noqa: BLE001
        pass
    for p in (DB_PATH, DB_PATH + ".bak", DB_PATH + ".tmp", sf, sf + ".tmp"):
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