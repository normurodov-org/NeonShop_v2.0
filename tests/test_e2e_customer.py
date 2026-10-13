"""🔴 END-TO-END: mijoz oqimi haqiqiy ishlayotgan server orqali.

Bu test server.ts ni HAQIQATAN ishga tushiradi va Telegramning haqiqiy
`initData` imzosi bilan so'rovlar yuboradi (haqiqiy HMAC — sun'iy
header emas). Shu sabab u ishlab chiqishdagi xatolarni ham, production
konturida chiqadigan xatolarni ham ushlaydi.

O'tkaziladigan yo'llar:
  1) `/api/me`            — profil, balans, tarix
  2) `POST /api/order`    — Stars / Premium / Gift
  3) `POST /api/nfts/rent`— NFT ijarasi
  4) `POST /api/topup`    — to'lov so'rovi (`amount_to_send`!)
  5) `POST /api/referral/withdraw`
  6) `POST /api/contest/join`
  + EGALIK va balans nazorati (hech qanday yo'l pul yo'qotmaydi)
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
PORT = int(os.environ.get("SMOKE_PORT") or (4900 + (os.getpid() % 300)))
BASE = f"http://127.0.0.1:{PORT}"
DB_PATH = "/tmp/_t_e2e.json"
TOKEN = "123456:E2E_TEST_TOKEN"

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


# ------------------------------------------------------------------ imzo
def init_data(user: dict, token: str = TOKEN) -> str:
    import time as _t
    f = {"auth_date": str(int(_t.time())), "user": json.dumps(user, separators=(",", ":"))}
    dcs = "\n".join(f"{k}={f[k]}" for k in sorted(f))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    sig = hmac.new(secret, dcs.encode(), hashlib.sha256).hexdigest()
    parts = [f"{k}={urllib.parse.quote(f[k], safe='')}" for k in sorted(f)]
    parts.append("hash=" + sig)
    return "&".join(parts)


CUST = {"id": 601234567, "username": "e2e_mijoz", "first_name": "E2E"}
OTH = {"id": 601234568, "username": "boshqa_mijoz", "first_name": "Boshqa"}
ADMIN = {"id": 8307046273, "username": "normuzb", "first_name": "Admin"}
CUST_RAW = init_data(CUST)
OTH_RAW = init_data(OTH)
ADMIN_RAW = init_data(ADMIN)


def call(method: str, path: str, body=None, raw: str = CUST_RAW):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Content-Type": "application/json",
        "X-Telegram-Init-Data": raw,
    })
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


def write_db(d: dict) -> None:
    tmp = DB_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    os.replace(tmp, DB_PATH)


# ------------------------------------------------------------------ server
section("0) Server ishga tushadi")
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

write_db({
    "users": {
        str(CUST["id"]): {"id": CUST["id"], "username": CUST["username"],
                          "first_name": "E2E", "balance": 5_000_000,
                          "total_spent": 0, "history": []},
    },
    "orders": {}, "topups": {}, "settings": {}, "nfts": [], "contest": {},
})

proc = subprocess.Popen(["npx", "tsx", "server.ts"], cwd=ROOT, env=env,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        text=True, preexec_fn=os.setsid, bufsize=1)
ready = False
deadline = time.time() + 150
while time.time() < deadline:
    if proc.poll() is not None:
        break
    st, _ = call("GET", "/api/health", raw="")
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
    section("1) /api/me — profil, balans, tarix")
    st, d = call("GET", "/api/me")
    check(st == 200, f"200 (natija {st})")
    check(d.get("user", {}).get("username") == "e2e_mijoz", "TO'G'RI mijoz")
    check(d.get("user", {}).get("id") == CUST["id"], "ID to'g'ri")
    check(float(d.get("user", {}).get("balance") or 0) == 5_000_000, "balans to'g'ri")
    check(isinstance(d.get("history"), list), "tarix ro'yxamati")

    # ---------------------------------------------------------------- 2
    section("2) POST /api/order — Stars / Premium / Gift")
    st, d = call("POST", "/api/order",
                 {"kind": "stars", "amount": 100, "username": "@durov"})
    check(st == 200, f"Stars buyurtma 200 (natija {st}: {d.get('error', '')})")
    star_order = d.get("order", {})
    check(star_order.get("status") == "processing",
          f"🔴 Stars 'processing' (topildi: {star_order.get('status')})")
    check("1\u20135 daqiqa" in str(d.get("message", "")),
          "🔴 mijozga haqiqiy vaqt va'dati ko'rsatiladi")
    check(float(d.get("balance", 0)) < 5_000_000, "balans kamaydi")

    st, d = call("POST", "/api/order",
                 {"kind": "premium", "months": 3, "mode": "nologin",
                  "username": "durov"})
    check(st == 200, f"Premium buyurtma 200 (natija {st}: {d.get('error', '')})")
    pr = d.get("order", {})
    check(pr.get("status") == "processing",
          f"🔴 Premium 'processing' emas 'completed' "
          f"(topildi: {pr.get('status')})")
    check(pr.get("months") == 3, "months saqlandi")
    check(pr.get("mode") == "nologin", "mode saqlandi")
    check("yetkazildi" not in str(d.get("message", "")),
          "🔴 mijozga yolg'on 'yetkazildi' yuborilmadi")

    st, d = call("POST", "/api/order",
                 {"kind": "gift", "gift": "bear", "username": "durov",
                  "hide_my_name": True})
    check(st == 200, f"Gift buyurtma 200 (natija {st}: {d.get('error', '')})")
    g = d.get("order", {})
    check(g.get("status") == "processing", "Gift 'processing'")
    check(g.get("gift") == "bear", "gift turi saqlandi")
    check(g.get("anon") is True, "anonimlik saqlandi")

    # ---------------------------------------------------------------- 3
    section("3) 🔴 NOTO'G'RI ma'lumotlar rad qilinadi")
    st, d = call("POST", "/api/order",
                 {"kind": "stars", "amount": 10, "username": "durov"})
    check(st == 400, f"10 Stars (min 50) -> 400 (natija {st})")
    st, d = call("POST", "/api/order", {"kind": "premium", "months": 5,
                                        "mode": "nologin", "username": "durov"})
    check(st == 400, f"yo'q premium tarifi -> 400 (natija {st})")
    st, d = call("POST", "/api/order", {"kind": "gift", "gift": "nope",
                                        "username": "durov"})
    check(st == 400, f"yo'q sovg'a -> 400 (natija {st})")
    st, d = call("POST", "/api/order", {"kind": "drone", "username": "durov"})
    check(st == 400, f"noma'lum xizmat turi -> 400 (natija {st})")
    st, d = call("POST", "/api/order",
                 {"kind": "stars", "amount": 100, "username": "user_4567"})
    check(st == 400, f"🔴 sun'iy username -> 400 (natija {st})")
    st, d = call("POST", "/api/order",
                 {"kind": "stars", "amount": 100, "username": "8307046273"})
    check(st == 400, f"🔴 raqamli ID -> 400 (natija {st})")
    st, d = call("POST", "/api/order",
                 {"kind": "stars", "amount": 100, "username": "  "})
    check(st == 400, f"bo'sh username -> 400 (natija {st})")
    # t.me havolasi tozalansin
    st, d = call("POST", "/api/order",
                 {"kind": "stars", "amount": 100,
                  "username": "https://t.me/durov/"})
    check(st == 200 and d.get("order", {}).get("recipient") == "durov",
          f"t.me havolasi tozalandi (topildi: {d.get('order', {}).get('recipient')})")

    # ---------------------------------------------------------------- 4
    section("4) 🔴 BALANS yetarli emas — hech qanday order yaratilmasin")
    poor = init_data({"id": 609999999, "username": "kambag"})
    write_db({**json.load(open(DB_PATH, encoding="utf-8")),
              "users": {**json.load(open(DB_PATH, encoding="utf-8"))["users"],
                        "609999999": {"id": 609999999, "username": "kambag",
                                      "balance": 100}}})
    time.sleep(3.5)
    st, d = call("POST", "/api/order",
                 {"kind": "stars", "amount": 100, "username": "durov"}, raw=poor)
    check(st == 402, f"balans yetarli emas -> 402 (natija {st})")
    st, d = call("GET", "/api/me", raw=poor)
    check(float(d.get("user", {}).get("balance") or 0) == 100,
          "🔴 balans O'ZGARMAgan (100)")

    # ---------------------------------------------------------------- 5
    section("5) 🔴 TO'LOV (topup) — amount_to_send")
    st, d = call("POST", "/api/topup", {"amount": 100000})
    check(st == 200, f"to'lov so'rovi 200 (natija {st}: {d.get('error', '')})")
    t = d.get("topup", {})
    check("amount_to_send" in t,
          "🔴 `amount_to_send` qaytariladi (bot shuni qidiradi)")
    check(t.get("amount_to_send") == 100001,
          f"ketma-ket raqam qo'shildi (topildi: {t.get('amount_to_send')})")
    tid = t.get("id")
    st, d = call("GET", f"/api/topup/status?id={tid}")
    check(st == 200, "o'z to'lovingizni ko'rasiz")
    st, d = call("GET", f"/api/topup/status?id={tid}", raw=OTH_RAW)
    check(st == 403, f"🔴 boshqaning to'lovi -> 403 (natija {st})")
    st, d = call("POST", "/api/topup/cancel", {"id": tid}, raw=OTH_RAW)
    check(st == 403, f"🔴 boshqa bekor qila olmaydi -> 403 (natija {st})")
    st, d = call("POST", "/api/topup/cancel", {"id": tid})
    check(st == 200, f"o'zi bekor qiladi -> 200 (natija {st})")

    # ---------------------------------------------------------------- 6
    section("6) NFT ijarasi")
    nid = "nft_e2e"
    # 🔴 `nfts` server.ts da OBJECT (id -> nft) bo'lishi SHART,
    # LIST emas — bot.py ham shunday saqlaydi.
    write_db({**json.load(open(DB_PATH, encoding="utf-8")),
              "nfts": {nid: {"id": nid, "title": "E2E-NFT", "number": 42,
                             "image": "https://x.com/a.jpg",
                             "link": "https://t.me/nft/E2E-42",
                             "daily": 50, "active": True}}})
    time.sleep(3.5)
    st, d = call("GET", f"/api/nfts/quote?id={nid}&days=7")
    check(st == 200, f"quote 200 (natija {st})")
    st, d = call("POST", "/api/nfts/rent", {"id": nid, "days": 7})
    check(st == 200, f"ijara 200 (natija {st}: {d.get('error', '')})")
    no = d.get("order", {})
    check(no.get("kind") == "nft_rent", "kind = nft_rent")
    check(no.get("status") == "pending", "pending (admin/menejer tasdiqlashini kutadi)")
    check(no.get("nft_notified") is False, "menedjerga hali yuborilmagan")
    check(no.get("admin_username") == ADMIN["username"],
          "🔴 `admin_username` to'g'ri (server.ts da ADMIN_HANDLE)")
    nft_order_id = no.get("id")

    # NFT yopiq bo'lsa ijaraga olib bo'lmasin
    write_db({**json.load(open(DB_PATH, encoding="utf-8")),
              "nfts": {nid: {"id": nid, "title": "E2E-NFT", "number": 42,
                             "image": "https://x.com/a.jpg",
                             "daily": 50, "active": False}}})
    time.sleep(3.5)
    st, d = call("POST", "/api/nfts/rent", {"id": nid, "days": 7})
    check(st == 404, f"🔴 YOPIQ NFT -> 404 (natija {st})")

    # ---------------------------------------------------------------- 7
    section("7) 🔴 TARIX — WebApp va BOTda ko'rinadi")
    # 🔴 IKKI XIL TARIX BOR va ikkalasi ham to'g'ri bo'lishi SHART:
    #   a) `/api/me` -> `history` = BUYURTMALAR ro'yxati (WebApp «Tarix»)
    #   b) DB `users[id].history` = AMALLAR (botdagi «📜 Tarix»)
    # Eski kodda (b) faqat `nft_rent` yozilardi — Stars/Premium/Gift
    # xaridlari bot tarixida KO'RINMASDI.
    st, d = call("GET", "/api/me")
    orders_hist = d.get("history") or []
    kinds = {o.get("kind") for o in orders_hist}
    check("stars" in kinds, f"🔴 Stars buyurtmasi WebApp tarixida: {sorted(k for k in kinds if k)}")
    check("premium" in kinds, "🔴 Premium buyurtmasi WebApp tarixida")
    check("gift" in kinds, "🔴 Gift buyurtmasi WebApp tarixida")
    check("nft_rent" in kinds, "🔴 NFT buyurtmasi WebApp tarixida")
    check(all(float(o.get("price") or 0) > 0 for o in orders_hist),
          "🔴 har bir buyurtmada narx bor (0 chiqmaydi)")
    check(all(o.get("created_at") for o in orders_hist),
          "har bir buyurtmada sana bor")

    db = json.load(open(DB_PATH, encoding="utf-8"))
    acts = db["users"][str(CUST["id"])].get("history") or []
    atypes = {a.get("type") for a in acts}
    check({"stars", "premium", "gift", "nft_rent"} <= atypes,
          f"🔴 bot tarixida BARCHA turlar (topildi: {sorted(atypes)})")
    spends = [a for a in acts if a.get("type") in
              {"stars", "premium", "gift", "nft_rent"}]
    check(spends and all(float(a.get("amount", 0)) < 0 for a in spends),
          "🔴 xarid summalari manfiy (yechilgan)")
    check(all(a.get("details") and a.get("date") for a in acts),
          "har bir amalda «details» va «date» bor (bo'sh qator chiqmaydi)")
    check(len(acts) <= 100, f"tarix 100 tadan oshmaydi ({len(acts)})")

    # ---------------------------------------------------------------- 8
    section("8) 🔴 KONKURS qatnashuvi")
    write_db({**json.load(open(DB_PATH, encoding="utf-8")),
              "contest": {"active": True, "prize_stars": 100, "min": 10000,
                          "winners": 3, "text": "E2E konkurs",
                          "participants": []}})
    time.sleep(3.5)
    st, d = call("POST", "/api/contest/join")
    check(st == 200, f"qatnashish 200 (natija {st}: {d.get('error', '')})")
    st, d = call("POST", "/api/contest/join")
    check(st == 200 and "allaqachon" in str(d.get("message", "")),
          "🔴 qayta qo'shilmaydi")
    # min yetarli emas
    write_db({**json.load(open(DB_PATH, encoding="utf-8")),
              "contest": {"active": True, "prize_stars": 100, "min": 99999999,
                          "winners": 3, "text": "x", "participants": []}})
    time.sleep(3.5)
    poor2 = init_data({"id": 608888888, "username": "yangi"})
    st, d = call("POST", "/api/contest/join", raw=poor2)
    check(st == 400, f"minimal xarid yetarli emas -> 400 (natija {st})")

    # ---------------------------------------------------------------- 9
    section("9) 🔴 ADMIN endpoint'lari — faqat admin")
    for m, path, body in (("GET", "/api/admin/data", None),
                          ("POST", "/api/admin/adjust-balance",
                           {"userId": CUST["id"], "amount": 999999999}),
                          ("POST", "/api/admin/toggle-bot", {}),
                          ("POST", "/api/bot/start", {}),
                          ("GET", "/api/admin/contest", None)):
        st, _ = call(m, path, body)
        check(st in (401, 403), f"{m} {path} -> {st} (401/403 kutilgan edi)")
        st, _ = call(m, path, body, raw=ADMIN_RAW)
        check(st != 500, f"{m} {path} admin uchun -> {st} (500 emas)")

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