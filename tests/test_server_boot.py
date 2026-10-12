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
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Dinamik port: avvalgi test qoldirgan server bilan to'qnashuvni
# oldini oladi (masalan 24678 — Vite HMR porti band bo'lishi mumkin)
PORT = int(os.environ.get("SMOKE_PORT") or (4600 + (os.getpid() % 400)))
BASE = f"http://127.0.0.1:{PORT}"


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
    req = urllib.request.Request(BASE + path)
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            return r.status, r.read().decode()
    except Exception as exc:  # noqa: BLE001
        return 0, str(exc)


print("=" * 68)
print("1) server.ts ishga tushadimi? (TDZ / runtime xatolar)")
print("=" * 68)

env = {
    **os.environ,
    "PORT": str(PORT),
    "BOT_TOKEN": "123456:TEST_TOKEN_FOR_SMOKE_ONLY",
    "API_ID": "1",
    "API_HASH": "x",
    "DB_PATH": "/tmp/_t_smoke_server.json",
    "AUTO_START_TG_BOT": "false",
    "NODE_ENV": "test",
}
for f in ("/tmp/_t_smoke_server.json", "/tmp/_t_smoke_server.json.bak"):
    if os.path.exists(f):
        os.remove(f)
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
print("NATIJA:", "✅ BARCHASI TO'G'RI" if ok else "❌ MUAMMO BOR")
print("=" * 68)
sys.exit(0 if ok else 1)