"""🔴 SESSIYA «BOTPY O'CHIRIB QO'YADI» — regressiya testi.

XABAR: "Telegram bilan uladim lekin asosiy sahifa ochilmayapti."

🔴 ASOSIY SABAB:
  Sessiya avval `users_db.json` ning `settings.__sessions` maydonida
  saqlanardi. LEKIN bot.py har 20 soniyada `db.save()` qiladi
  (`update_heartbeat` → `set_runtime_status`) va u O'Z ESKI XOTIRASIDAN
  yozadi — `reload_if_changed()` chaqirmasdan.

  Ketma-ket:
    1. bot.py ishga tushdi, `users_db.json` ni o'qidi (sessiya yo'q)
    2. Mijoz brauzerda kirdi → server `__sessions` ni yozdi
    3. 20 sekund keyin bot.py o'z eski nusxasini yozdi
       → `__sessions` YO'Q → sessiya O'CHDI
    4. Sahifa yangilanganda `/api/me` 401 → yana kirish ekrani

  Mijoz uchun: «kirdim, lekin asosiy sahifa ochilmayapti».

🔴 YECHIM: sessiyalar ALOHIDA faylda (`*_sessions.json`). Uni faqat
  server.ts ochadi — bot.py umuman tegmaydi, shuning uchun eskirgan
  nusxa uni o'chira olmaydi.

Bu test shu mexanizmni ANIQ simulyatsiya qiladi: bot.py kabi eskirgan
nusxa bilan faylni qayta yozadi va sessiya saqlanishini tekshiradi.
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
PORT = int(os.environ.get("SMOKE_PORT") or (5250 + (os.getpid() % 200)))
BASE = f"http://127.0.0.1:{PORT}"
DB_PATH = "/tmp/_t_sess.json"
TOKEN = "123456:SESSION_PERSIST_TEST"

ok = True


def check(cond, msg):
    global ok
    ok &= bool(cond)
    print(f"  {'\u2705' if cond else '\u274c'} {msg}")


def section(t):
    print()
    print("=" * 70)
    print(t)
    print("=" * 70)


def widget_data(user: dict) -> str:
    f = {"id": str(user["id"]), "first_name": user.get("first_name", ""),
         "username": user.get("username", ""), "photo_url": "",
         "auth_date": str(int(time.time()))}
    dcs = "\n".join(f"{k}={f[k]}" for k in sorted(f))
    secret = hashlib.sha256(TOKEN.encode()).digest()
    sig = hmac.new(secret, dcs.encode(), hashlib.sha256).hexdigest()
    return "&".join([f"{k}={urllib.parse.quote(f[k], safe='')}" for k in sorted(f)]
                    + ["hash=" + sig])


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


USER = {"id": 770099988, "username": "sess_mijoz", "first_name": "Sess"}

section("0) Server")
env = {**os.environ, "PORT": str(PORT), "BOT_TOKEN": TOKEN,
       "API_ID": "1", "API_HASH": "x", "DB_PATH": DB_PATH,
       "AUTO_START_TG_BOT": "false", "NODE_ENV": "test"}
subprocess.run(["pkill", "-f", "tsx server.ts"],
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
time.sleep(1.5)
for sfx in ("", ".bak", ".tmp"):
    if os.path.exists(DB_PATH + sfx):
        os.remove(DB_PATH + sfx)
write_db({"users": {}, "orders": {}, "topups": {}, "nfts": {},
          "settings": {"bot_username": "shop_neonbot"}, "contest": {}})

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
    section("1) Kirish")
    st, d = call("POST", "/api/auth/telegram", {"data": widget_data(USER)})
    check(st == 200, f"kirish 200 (natija {st})")
    sess = d.get("token") or ""
    check(bool(sess), "token qaytarildi")

    st, d = call("GET", "/api/me", tok=sess)
    check(st == 200 and d.get("user", {}).get("username") == USER["username"],
          f"asbosh sahifa ochildi ({st})")

    # ---------------------------------------------------------------- 2
    section("2) 🔴 SESSIYA QAYERDA SAQLANADI")
    sessions_file = DB_PATH.replace(".json", "") + ".sessions.json"
    check(os.path.exists(sessions_file),
          "🔴 alohida fayl yaratildi (bot.py tegmaydi)")
    check("__sessions" not in json.load(open(DB_PATH, encoding="utf-8")).get("settings", {}),
          "🔴 users_db.json da `__sessions` YO'Q "
          "(bot.py uni o'chira olmaydi)")

    # ---------------------------------------------------------------- 3
    section("3) 🔴 bot.py ESKIRGAN YOZUVI (simulyatsiya)")
    # 🔴 BU — ASOSIY SIMULYATSIYA: bot.py o'z ESKI xotirasidan yozadi.
    #    Stale nusxa = foydalanuvchilar buyurtmalari bo'lmagan baza.
    # 📐 DIQQAT: eski versiya bu yerda `users: {}` yozardi —
    # ya'ni mijozni O'CHIRGAN bo!lardi va keyin kelgan 401
    # sessiya xatosi EMAS, o'chirilgan mijoz xatosi bo!lardi
    # (test o(zini noto'g!ri hodisa bilan chalg'shirtardi).
    # Haqiqiy bot.py eskirgan nusxasi MIJOZLARNI SAQLAB qoladi —
    # u faqat `__sessions` kalitini bilmaydi. Shu qaytarilgan.
    stale = {"users": {str(USER["id"]): {"id": USER["id"],
                                         "username": USER["username"],
                                         "balance": 0}},
             "orders": {}, "topups": {}, "nfts": {},
             "settings": {"bot_username": "shop_neonbot",
                          "runtime": {"bot": "polling", "updates": 5}}}
    write_db(stale)
    print("      → bot.py kabi eskirgan nusxa yozildi (heartbeat)")
    time.sleep(3.5)

    st, d = call("GET", "/api/me", tok=sess)
    check(st == 200,
          f"🔴 bot.py yozuvidan KEYIN ham sessiya ishlaydi (natija {st})")
    check(d.get("user", {}).get("username") == USER["username"],
          "🔴 mijoz hali ham ko'rinib turibdi")

    # ---------------------------------------------------------------- 4
    section("4) 🔴 KO'P MARTA bot.py YOZSA")
    for i in range(4):
        write_db({**stale, "settings": {"bot_username": "shop_neonbot",
                                         "runtime": {"updates": i}}})
        time.sleep(2.2)
    st, _ = call("GET", "/api/me", tok=sess)
    check(st == 200, f"🔴 4 marta yozildidan keyin ham saq (natija {st})")

    # ---------------------------------------------------------------- 5
    section("5) 🚪 Logout")
    st, _ = call("POST", "/api/auth/logout", tok=sess)
    check(st == 200, "logout 200")
    st, _ = call("GET", "/api/me", tok=sess)
    check(st == 401, f"🔴 logout'dan keyin ishlamaydi (natija {st})")

    # ---------------------------------------------------------------- 6
    section("6) 🔴 RESTART DAN KEYIN (redeploy)")
    # 📐 Restart testi ham mijozni saqlagan DB bilan ishlaydi —
    # aks holda 401 sessiya uchun emas, o'chirilgan mijoz uchun chiqardi.
    restart_user = {"id": 770099987, "username": "restart_mijoz", "first_name": "R"}
    write_db({**stale, "users": {**stale["users"],
                                 str(restart_user["id"]): {"id": restart_user["id"],
                                                           "username": restart_user["username"],
                                                           "balance": 0}}})
    time.sleep(3.0)
    call("POST", "/api/auth/telegram", {"data": widget_data(restart_user)})
    st, d = call("POST", "/api/auth/telegram", {"data": widget_data(restart_user)})
    restart_sess = d.get("token") or ""
    check(bool(restart_sess), "yangi sessiya yaratildi")

    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    time.sleep(2)
    proc = subprocess.Popen(["npx", "tsx", "server.ts"], cwd=ROOT, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, preexec_fn=os.setsid, bufsize=1)
    ready = False
    deadline = time.time() + 150
    while time.time() < deadline:
        st, _ = call("GET", "/api/health")
        if st == 200:
            ready = True
            break
        time.sleep(1.0)
    check(ready, "server qayta ishga tushdi")
    st, _ = call("GET", "/api/me", tok=restart_sess)
    check(st == 200, f"🔴 REDEPLOY'dan keyin sessiya saq (natija {st})")

finally:
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except Exception:  # noqa: BLE001
        pass
    for p in (DB_PATH, DB_PATH + ".bak", DB_PATH + ".tmp",
              DB_PATH.replace(".json", "") + ".sessions.json",
              DB_PATH.replace(".json", "") + ".sessions.json.tmp"):
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass

print()
print("=" * 70)
print("NATIJA: \u2705 BARCHASI TO'G'RI" if ok else "NATIJA: \u274c MUAMMO BOR")
print("=" * 70)
raise SystemExit(0 if ok else 1)