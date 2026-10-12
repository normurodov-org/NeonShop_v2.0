"""SESSION KALITI BEKOR QILINGAN (AUTH_KEY_UNREGISTERED) — tiklash oqimi.

REAL SABAB (production /api/health dan aniqlangan):
    userbot = error
    error = Telegram says: [401 AUTH_KEY_UNREGISTERED]
    gift_pending = 18
Gift worker "running" ko'rinib, lekin userbot ulanmagan edi —
matn va anonim hech qachon yuborilmasligining SABABI shu edi.

MUHIM: kalit bekor qilinganda qayta urinish 100 marta ham natija
bermaydi (bir xil xato). Shu sababli:
  1) xato TURi aniqlanadi (klassifikatsiya)
  2) admin ga ANIQ, harakatga chorlovchi xabar beriladi
  3) supervisor qayta urinishni TO'XTATADI (spam va xarajatning oldi)
  4) start() dan keyin darhol tekshiriladi (xato kech chiqsa)
"""
import asyncio
import sys

sys.path.insert(0, '.')
import bot as B  # noqa: E402

SRC = open("bot.py", encoding="utf-8").read()

ok = True


def check(cond, msg):
    global ok
    ok &= bool(cond)
    print(f"  {'✅' if cond else '❌'} {msg}")


print("=" * 68)
print("1) XATO TURLARINI ANIQLASH")
print("=" * 68)
real = ('Telegram says: [401 AUTH_KEY_UNREGISTERED] (caused by '
        '"updates.GetState") Pyrogram 2.3.69 thinks: The key is not '
        'registered in the system. Delete your session file and login again')
cases = [
    (real, "auth_key_unregistered", "haqiqiy production xatosi"),
    ("Telegram says: [401 AUTH_KEY_INVALID]", "auth_key_unregistered", "invalid kalit"),
    ("SESSION_REVOKED", "session_revoked", "sessiya bekor qilingan"),
    ("USER_DEACTIVATED", "account_blocked", "akkaunt bloklangan"),
    ("Connection timed out", "network", "tarmoq uzilishi"),
    ("FLOOD_WAIT_30", "network", "flood"),
    ("Nonsense error", "", "noma'lum"),
]
for exc, exp, label in cases:
    got = B.session_error_kind(Exception(exc))
    print(f"      {label:28} -> {got!r}")
    check(got == exp, f"{label}: {exp}")

for k in ("auth_key_unregistered", "session_revoked", "account_blocked", "network"):
    check(k in B.SESSION_ERROR_HELP, f"yordam matni bor: {k}")
check("AUTH_KEY_UNREGISTERED" in B.SESSION_ERROR_HELP["auth_key_unregistered"],
      "yordam matni sababni tushuntiradi")
check("📱 Raqam bilan ulash" in B.SESSION_ERROR_HELP["auth_key_unregistered"],
      "yordam matni aniq harakatni ko'rsatadi")

print()
print("=" * 68)
print("2) ADMIN XABARI — aniq bo'lishi shart")
print("=" * 68)
check("error_kind=kind" in SRC, "runtime ga error_kind yoziladi")
check("gift_worker=\"blocked_userbot_offline\" if kind" in SRC,
      "gift_worker 'blocked' ga o'tadi (running emas!)")
check("balans va gift ISHLAMAYDI" in SRC,
      "xabar: balans va gift ishlamaydi")
check("HECH qachon yuborilmaydi" in SRC,
      "kutayotgan giftlar soni ko'rsatiladi")

print()
print("=" * 68)
print("3) SUPERVISOR — ma'nosiz qayta urishni to'xtatadi")
print("=" * 68)
check("qayta urinishning ma'nosi yo'q" in SRC, "to'xtatish xabari bor")
check("blocked_session_revoked" in SRC, "runtime ga blocked_session_revoked")
check(SRC.index("if retries in (2, 8):") < SRC.index("if retries > 10:"),
      "bekor qilingan kalit tekshiruvi LIMIT dan OLDIN")

print()
print("=" * 68)
print("4) ULANGANDAN KEYIN darhol tekshiriladi")
print("=" * 68)
check("asyncio.wait_for(ub.get_me(), timeout=25)" in SRC,
      "start() dan keyin get_me() bilan tekshiriladi")
check("Sessiya kaliti Telegram tomonidan bekor qilingan" in SRC,
      "kech chiqqan xato uchun alohida xabar")

print()
print("=" * 68)
print("5) Eski (ikki-userbot) runtime kalitlari tozalanadi")
print("=" * 68)
for k in ("gift_userbot", "gift_account", "gift_error"):
    check(k in B.STALE_RUNTIME_KEYS, f"{k} eskirgan sifatida belgilangan")
B.db.data.setdefault("settings", {}).setdefault("runtime", {}).update(
    {"gift_userbot": "connected", "gift_account": "@x", "gift_error": "eski",
     "userbot": "connected", "account": "@normuzb"}
)
B.db.save()
n = B.purge_stale_runtime()
rt = B.db.data["settings"]["runtime"]
check(n == 3, f"3 ta eskirgan kalit tozalandi: {n}")
check("gift_userbot" not in rt and "gift_account" not in rt and "gift_error" not in rt,
      "eskirgan kalitlar yo'qoldi")
check(rt.get("userbot") == "connected" and rt.get("account") == "@normuzb",
      "foydali ma'lumotlar saqlandi")
check(B.purge_stale_runtime() == 0, "ikkinchi marta hech narsa yo'q")

print()
print("=" * 68)
print("6) DIAGNOSTIKA — userbot xatosi ko'rsatiladi")
print("=" * 68)
B.ADMIN_IDS = {8307046273}
import time  # noqa: E402
B.ADMIN_SESSIONS[8307046273] = time.time()


class _Msg:
    def __init__(self):
        self.answers = []

    async def answer(self, t, **kw):
        self.answers.append(t)


class _Call:
    def __init__(self, data):
        self.data = data
        self.message = _Msg()
        self.from_user = type("U", (), {"id": 8307046273})()

    async def answer(self, *a, **kw):
        pass

    async def edit_text(self, t, **kw):
        pass


async def main():
    B.userbot = None
    B.db.data["settings"]["runtime"] = {
        "error_kind": "auth_key_unregistered", "error": real,
    }
    B.db.save()
    c = _Call("adm:gift_diag")
    await B.adm_gift_diag(c)
    t = c.message.answers[0]
    check("Userbot ulanmagan" in t, "userbot ulanmaganligi aytiladi")
    check("auth_key_unregistered" in t, "xato turi ko'rsatilgan")
    check("Raqam bilan ulash" in t, "yechim ko'rsatilgan")
    print()
    for ln in t.splitlines():
        print("      " + ln[:95])

    print()
    print("=" * 68)
    print("NATIJA:", "✅ BARCHASI TO'G'RI" if ok else "❌ MUAMMO BOR")
    print("=" * 68)
    return 0 if ok else 1


sys.exit(asyncio.run(main()))