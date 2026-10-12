"""SESSION — bazada saqlanishi (Railway ENV kerak emas) + gift diagnostikasi.

MUAMMO: session faqat Railway ENV da saqlansa, har redeploy'da qayta
kiritish kerak edi. Telefondan yangi session olib ENV'ga yozilsa —
eski ENV qiymati qo'llanilib qolardi va yangisi "eskirgan" bo'lib
tuyulardi.

YECHIM: login qilingandan keyin session AVTOMATIK bazaga yoziladi
(/data/users_db.json Railway'da saqlanadi), startup'da bazadagi session
birinchi turadi.
"""
import asyncio
import sys
import time

sys.path.insert(0, '.')
import bot as B  # noqa: E402

SRC = open("bot.py", encoding="utf-8").read()

ok = True


def check(cond, msg):
    global ok
    ok &= bool(cond)
    print(f"  {'✅' if cond else '❌'} {msg}")


print("=" * 68)
print("1) QAYTA QATIK — bazadagi session eng yangisi")
print("=" * 68)
doc = B.resolve_session_string.__doc__ or ""
check("db" in doc and "eng yangisi" in doc.lower(), "hujjat to'g'ri")

# baza bo'sh -> ENV
B.db.data.setdefault("settings", {}).pop(B.SESSION_KEY, None)
s, src = B.resolve_session_string()
check(src == ("env" if B.SESSION_STRING else "yo'q"),
      f"baza bo'sh -> ENV ({src})")

# bazada bor -> db
sess = "A" * B.SESSION_STRING_EXPECTED
B.save_session_to_db(sess)
s, src = B.resolve_session_string()
check(src == "db", "bazada session bor -> manba 'db'")
check(s == sess, "bazadagi session qaytarildi")

# ENV bilan ziddiyat bo'lsa ham db ustun
B.SESSION_STRING = "B" * B.SESSION_STRING_EXPECTED
s, src = B.resolve_session_string()
check(src == "db" and s == sess,
      "ENV boshqa bo'lsa ham bazadagi session ustun (eng yangi)")

print()
print("=" * 68)
print("2) Kalit hech qayerga yuborilmaydi (logda xavfsiz)")
print("=" * 68)
check("%d belgi" in SRC, "logda faqat UZUNLIK chiqadi")
check('log.info("🔐 Session bazaga saqlandi (%d belgi)' in SRC,
      "kalitning o'zi logga tushmaydi")

print()
print("=" * 68)
print("3) Login -> avtomatik saqlanadi")
print("=" * 68)
check("saved = save_session_to_db(session)" in SRC,
      "ub_finish_login sessionni bazaga saqlaydi")
check("shart emas" in SRC and "bazada saqlandi" in SRC.lower() or "saqlandi" in SRC,
      "admin ga ENV kerak emasligi aytiladi")
check("Railway ENV kerak emas" in SRC, "ENV kerak emasligi aniq yozilgan")


class FakeMe:
    def __init__(self):
        self.id, self.username = 777, "testacc"


class FakeClient:
    def __init__(self):
        self.handlers = []

    async def get_me(self):
        return FakeMe()

    async def add_handler(self, h):
        self.handlers.append(h)

    async def export_session_string(self):
        return "C" * B.SESSION_STRING_EXPECTED


class FakeMsg:
    def __init__(self):
        self.answers = []

    async def answer(self, t, **kw):
        self.answers.append(t)


class FakeState:
    async def clear(self):
        pass


async def main():
    B.userbot = None
    B.db.data.setdefault("settings", {}).pop(B.SESSION_KEY, None)
    await B.ub_finish_login(FakeClient(), FakeMsg(), FakeState())
    stored = B.get_session_from_db()
    check(stored == "C" * B.SESSION_STRING_EXPECTED,
          "login qilingandan keyin bazada saqlandi")
    check(stored != B.SESSION_STRING, "baza qiymati ENV dan farq qiladi")

    print()
    print("=" * 68)
    print("4) O'chirish (akkau ntni almashtirish uchun)")
    print("=" * 68)
    check(B.delete_session_from_db() is True, "session bazadan o'chirildi")
    check(B.get_session_from_db() == "", "baza bo'sh")
    check(B.delete_session_from_db() is False, "ikkinchi marta xato bermaydi")

    print()
    print("=" * 68)
    print("5) GIFТ DIAGNOSTIKASI — sababni aniq ko'rsatadi")
    print("=" * 68)
    B.ADMIN_IDS = {8307046273}
    B.ADMIN_SESSIONS[8307046273] = time.time()

    class FS:
        def __init__(self, e):
            self.emoji = e

    class G:
        def __init__(self, i, e, p):
            self.id, self.sticker, self.price = i, FS(e), p

    class UB:
        async def get_available_gifts(self):
            return [G(102, "🧸", 15), G(101, "💝", 15), G(103, "🌹", 25)]

        async def send_gift(self, **kw):
            return True

    class Call:
        def __init__(self, data):
            self.data = data
            self.message = FakeMsg()
            self.from_user = type("U", (), {"id": 8307046273})()

        async def answer(self, *a, **kw):
            pass

        async def edit_text(self, t, **kw):
            pass

    # a) userbot yo'q
    B.userbot = None
    c = Call("adm:gift_diag")
    await B.adm_gift_diag(c)
    txt = c.message.answers[0]
    check("Userbot ulanmagan" in txt, "userbot yo'q bo'lsa aniq aytiladi")
    print("      " + txt.replace("\n", " ")[:80])

    # b) userbot bor, Telegram'da 3 ta gift
    B.userbot = UB()
    B.db.data["orders"] = {
        "a": {"id": "a", "kind": "gift", "gift": "bear", "stars": 15,
              "recipient": "bobur", "status": "completed"},
        "b": {"id": "b", "kind": "gift", "gift": "cake", "stars": 50,
              "recipient": "bobur", "status": "completed",
              "gift_attempts": 5, "gift_failed": True,
              "gift_error": "xato", "gift_error_stage": "3) send_gift"},
        "c": {"id": "c", "kind": "gift", "gift": "heart", "stars": 15,
              "recipient": "https://t.me/x", "status": "boshqa"},
        "d": {"id": "d", "kind": "gift", "gift": "heart", "stars": 15,
              "recipient": "!!!", "status": "completed"},
    }
    B.db.save()
    c2 = Call("adm:gift_diag")
    await B.adm_gift_diag(c2)
    t2 = c2.message.answers[0]
    check("3</b> ta sovg'a mavjud" in t2, "Telegram'dagi sovg'alar soni ko'rsatildi")
    check("urishlar tugagan" in t2, "urishlar tugagan buyurtma aniqladi")
    check("noto'g'ri qabul qiluvchi" in t2, "noto'g'ri qabul qiluvchi aniqladi")
    check("holat=boshqa" in t2, "noto'g'ri statusdagi buyurtma aniqladi")
    check("Bosqich" in t2, "oxirgi xatoning bosqichi ko'rsatildi")
    check("topilmagan sovg'alar" in t2, "Telegram'da yo'q sovg'alar aytildi")
    print()
    for ln in t2.splitlines():
        print("      " + ln[:90])

    print()
    print("=" * 68)
    print("NATIJA:", "✅ BARCHASI TO'G'RI" if ok else "❌ MUAMMO BOR")
    print("=" * 68)
    return 0 if ok else 1


sys.exit(asyncio.run(main()))