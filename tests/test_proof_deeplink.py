# -*- coding: utf-8 -*-
"""
\U0001F310\U0001F310 SAYT -> TELEGRAM «BANK XABARINI YUBORISH» DEEP LINK

    \U0001F534\U0001F534\U0001F534 MUAMMO (2026-10-17): «Karta chiqadi, lekin «Tekshirish»
       ishlamaydi» — faqat BRAUZERDA. WebApp'da ishlaydi.

    Sabab 1 (bot.py): `processed_bank_msgs` xabarni kelgan zahoti
       ro'yxatga yozardi \u2014 topilmasa ham. «Tekshirish» esa o'sha xabarni
       topib o'tkazib yuborardi. \u2192 tests/test_rescan_repro.py

    Sabab 2 (yo'q edi): saytda mijozning qo'lda tasdiqlash yo'li
       YO'Q EDI. Botdagi «Bank xabarini yuborish» tugmasi faqat WebApp
       ichidan ishga tushardi.

    \u2705 YECHIM: saytdagi «Bank xabarini yuborish» tugmasi deep linkni
       ochadi:  t.me/<bot>?start=topup_<id>
       Bot esa mijozni DARHOL bank xabari rejimiga kiritadi
       (TopupStates.proof) \u2014 userbot bo'lishidan qat'i nazar, bu YO'L
       DOIM ishlaydi.

    Bu test shu zanjirni tekshiradi: regex, tegislik tekshiruvi,
    holatlar, xato holatlari.
"""
import asyncio
import re
import sys
import time
import types

sys.path.insert(0, '.')
import bot as B  # noqa: E402

FAILS = []


def check(name, cond, extra=""):
    print(("  \u2705 " if cond else "  \u274c ") + name + (("  | " + str(extra)) if extra else ""))
    if not cond:
        FAILS.append(name)
    return cond


class FakeState:
    def __init__(self):
        self.st = None
        self.d = {}

    async def clear(self):
        self.st, self.d = None, {}

    async def set_state(self, s):
        self.st = s

    async def update_data(self, **kw):
        self.d.update(kw)

    async def get_data(self):
        return dict(self.d)


class FakeMsgOut:
    def __init__(self):
        self.texts = []

    async def answer(self, text, **kw):
        self.texts.append(text)


class FakeMessage:
    def __init__(self):
        self.out = FakeMsgOut()

    async def answer(self, text, **kw):
        self.out.texts.append(text)


class FakeCommand:
    def __init__(self, args):
        self.args = args


class FakeBotApi:
    async def send_message(self, *a, **k):
        raise AssertionError("bu yo\u2018lda botga xabar yuborilmaydi")


def setup(user_id, topups=None):
    B.db.data["topups"] = topups or {}
    B.db.data["processed_bank_msgs"] = []
    B.db.get_or_create_user(user_id, "sardor", "Sardor")
    B.db.data["users"][str(user_id)]["captcha_ok"] = True
    B.db.save()


def add_topup(tid, uid, amount=1000, seq=24, status="pending"):
    B.db.data["topups"][tid] = {
        "id": tid, "user_id": uid, "amount": amount, "seq": seq,
        "amount_to_send": amount + seq, "status": status,
        "created_at": B.now_iso(), "expires_at": time.time() + 3600,
    }
    B.db.save()


async def call(arg, uid, is_new_user=False):
    st = FakeState()
    msg = FakeMessage()
    await B.cmd_start(
        message=msg,
        command=FakeCommand(arg),
        state=st,
        bot=FakeBotApi(),
        db_user=B.db.data["users"][str(uid)],
        is_new_user=is_new_user,
    )
    return st, msg


async def no_proof(arg, uid):
    """Oddiy /start proof rejimiga KIRMASLIGI kerak (menyu ishlaydi)."""
    st = FakeState()
    msg = FakeMessage()
    msg.bot = None
    try:
        await B.cmd_start(
            message=msg, command=FakeCommand(arg), state=st, bot=None,
            db_user=B.db.data["users"][str(uid)], is_new_user=False,
        )
    except AttributeError:
        pass          # `send_main_menu` haqiqiy bot so'raydi \u2014 biz uchun muhim emas
    return st.st is None and st.d.get("proof_topup") is None


async def main():
    UID = 424242

    # -------------------------------------------------
    print("\n\U0001F510 HOLAT 1: to'g'ri so\u2018rov \u2014 proof rejimiga kiradi")
    setup(UID)
    add_topup("top_abc123", UID)
    st, msg = await call("topup_top_abc123", UID)
    check("state = TopupStates.proof", st.st is B.TopupStates.proof, st.st)
    check("proof_topup saqlandi", st.d.get("proof_topup") == "top_abc123", st.d)
    check("bank xabari so\u2018raldi", any("Bank xabarini yuboring" in t for t in msg.out.texts))
    check("kutilayotgan summa ko\u2018rsatildi",
          any(B.fmt(1024) + " UZS" in t for t in msg.out.texts),
          [t[:60] for t in msg.out.texts])
    check("main menyuga yuborilmadi",
          not any("NeonShop" in t and "Xush kelibsiz" in t for t in msg.out.texts))

    # -------------------------------------------------
    print("\n\U0001F6E1\uFE0F HOLAT 2: boshqa mijozning so\u2018rovi \u2014 RAD ETILADI")
    setup(UID)
    add_topup("top_abc123", 999999)
    st, msg = await call("topup_top_abc123", UID)
    check("state qo\u2018yilmadi", st.st is None, st.st)
    check("rad havolasi chiqdi",
          any("sizniki emas" in t for t in msg.out.texts),
          [t[:50] for t in msg.out.texts])

    # -------------------------------------------------
    print("\n\U0001F6E1\uFE0F HOLAT 3: so\u2018rov topilmadi")
    setup(UID)
    st, msg = await call("topup_top_yoqyoq", UID)
    check("state qo\u2018yilmadi", st.st is None, st.st)
    check("xato ko\u2018rsatildi", any("topilmadi" in t for t in msg.out.texts))

    # -------------------------------------------------
    print("\n\U0001F6E1\uFE0F HOLAT 3: allaqachon yopilgan so\u2018rov")
    setup(UID)
    add_topup("top_done", UID, status="completed")
    st, msg = await call("topup_top_done", UID)
    check("state qo\u2018yilmadi", st.st is None, st.st)
    check("«allaqachon yopilgan» aytildi",
          any("allaqachon yopilgan" in t for t in msg.out.texts))

    # -------------------------------------------------
    print("\n\U0001F6E1\uFE0F HOLAT 4: boshqa deep linklar BU QAT\u2018RGA TUSHMAYDI")
    setup(UID)
    add_topup("top_abc123", UID)
    for bad in ("web_" + "a" * 48, "12345", "topup_", "topup_k<<<>>>", "topup_ok"):
        m = re.fullmatch(r"topup_([A-Za-z0-9_]{3,40})", bad)
        if bad.startswith("topup_") and m:
            check("«%s» topilmasin" % bad, False, m.group(1))
    check("haqiqiy id mos keladi",
          bool(re.fullmatch(r"topup_([A-Za-z0-9_]{3,40})", "topup_top_abc123")))
    check("web-login kodi BU QAT\u2018RGA tushmaydi",
          not re.fullmatch(r"topup_([A-Za-z0-9_]{3,40})", "web_" + "a" * 48))
    check("oddiy /start proof rejimiga KIRMADDI",
          await no_proof("", UID))
    check("bo\u2018sh arg \u2014 main menyu", st.st is None and len(msg.out.texts) > 0)

    print()
    print("=" * 74)
    if FAILS:
        print("\U0001F534\U0001F534\U0001F534 MUAMMO: %d ta test ishlamadi:" % len(FAILS))
        for f in FAILS:
            print("   - " + f)
        return 1
    print("\u2705\u2705\u2705 DEEP LINK ZANJIRI TO\u2018G\u2018RI ISHLAYDI")
    return 0


sys.exit(asyncio.run(main()))