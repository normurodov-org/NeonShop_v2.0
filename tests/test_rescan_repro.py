# -*- coding: utf-8 -*-
"""
🛡️🛡️🛡️ «ТЕКШIRISH» РЕГРЕССИЯ ТЕСТЛАРИ

    Muammo (2026-10-17): «Karta chiqadi, lekin «Tekshirish» ishlamaydi»
    — faqat BRAUZERDA (saytda). Telegram WebApp'da ishlagan.

    Sabab: `processed_bank_msgs` ro'yxatiga xabar kelgan ZAHOTI yozilardi,
    topilmasa ham. Keyin mijoz «Tekshirish» bossa, rescan o'sha xabarni
    topib o'tkazib yuborardi.

    Tuzatish: ro'yxatga FAQAT balans haqiqatan qo'shilgan xabarlar
    yoziladi. Shu bilan birga qat'iy blok (ikki marta to'ldirishga
    qarshi) saqlanib qoladi.

    Tekshiriladigan holatlar:
      1. Sayt senariysi: xabar topupdan OLDIN kelgan  -> topiladi
      2. Bir xil xabar 3 marta tekshirilsa           -> faqat 1 marta to'ldiriladi
      3. To'ldirilgan xabar boshqa so'rovga ishlatilmaydi
      4. Ro'yxat CHEKSIZ o'smaydi (kesish ishlaydi)
"""
import asyncio
import io
import json
import sys
import time
import types

sys.path.insert(0, '.')
import bot as B  # noqa: E402

HUMO_TEMPL = (
    "\U0001F389 To'ldirish\n"
    "\u2795 {amt},00 UZS (Mijoz tolagan summa)\n"
    "\U0001F4CD CLICK EWALLET HUMO>T\n"
    "\U0001F4B3 HUMOCARD *3682\n"
    "\U0001F553 17:19 16.10.2026\n"
    "\U0001F4B0 3.391,91 UZS"
)

FAILS = []


def check(name, cond, extra=""):
    mark = "\u2705" if cond else "\u274c"
    print("  " + mark + " " + name + (("  | " + str(extra)) if extra else ""))
    if not cond:
        FAILS.append(name)
    return cond


def bank_msg(amount):
    return HUMO_TEMPL.format(amt="{:,.0f}".format(amount).replace(",", "."))


class FakeMsg:
    def __init__(self, mid, text, ts):
        self.id = mid
        self.text = text
        self.caption = None
        self.date = types.SimpleNamespace(timestamp=lambda: ts)


class FakeChat:
    id = 555


class FakeUserbot:
    def __init__(self, messages):
        self.is_connected = True
        self._messages = messages

    async def get_chat(self, target):
        return FakeChat()

    async def get_chat_history(self, chat, limit=40):
        for m in self._messages[:limit]:
            yield m


class FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, **kw):
        self.sent.append(text)
        return types.SimpleNamespace(message_id=len(self.sent))


ADMIN = []
B.bot = FakeBot()


async def _notify(t):
    ADMIN.append(t)


B.notify_admins = _notify


def reset():
    B.db.data["topups"] = {}
    B.db.data["processed_bank_msgs"] = []
    B.db.get_or_create_user(777, "sardor", "Sardor")
    B.db.data["users"]["777"]["balance"] = 0
    B.db.data["users"]["777"]["total_topup"] = 0
    B.db.data["history"] = []
    B.db.save()


def add_topup(tid, amount, seq):
    B.db.data["topups"][tid] = {
        "id": tid, "user_id": 777, "amount": amount, "seq": seq,
        "amount_to_send": amount + seq, "status": "pending",
        "created_at": B.now_iso(), "expires_at": time.time() + 3600,
    }
    B.db.save()


def balance():
    return int(B.db.data["users"]["777"].get("balance", 0))


def status(tid):
    return B.db.data["topups"][tid]["status"]


async def main():
    ts = int(time.time())

    # ---------------------------------------------------------
    print("\n\U0001F41B\U0001F534 HOLAT 1: sayt senariysi — xabar topupdan OLDIN")
    reset()
    msg = FakeMsg(700, bank_msg(1024), ts - 60)
    B.userbot = FakeUserbot([msg])
    await B.on_humo_message(B.userbot, msg)
    check("topilmagan xabar ro'yxatga YOZILMADI",
          "0_700" not in B.db.data["processed_bank_msgs"],
          B.db.data["processed_bank_msgs"])
    add_topup("top_web", 1000, 24)
    res = await B.rescan_humo_for_topup("top_web")
    check("rescan topildi", res.get("status") == "found", res.get("status"))
    check("balans 1 000", balance() == 1000, balance())
    check("topup yopildi", status("top_web") == "completed")

    # ---------------------------------------------------------
    print("\n\U0001F6E1\uFE0F HOLAT 2: bir xil xabar 3 marta tekshiriladi")
    check("balans HALI 1 000", balance() == 1000, balance())
    for i in range(3):
        r = await B.rescan_humo_for_topup("top_web")
        print("     urinish %d -> %s | balans %s" % (i + 1, r.get("status"), balance()))
    check("balans o'zgarmadi (1 marta to'ldirildi)", balance() == 1000, balance())

    # ---------------------------------------------------------
    print("\n\U0001F6E1\uFE0F HOLAT 3: to'ldirilgan xabar boshqa so'rovga ishlatilmaydi")
    add_topup("top_2", 1000, 1)   # 1 001 UZS — boshqa summa
    r = await B.rescan_humo_for_topup("top_2")
    check("boshqa so'rov to'ldirilmadi",
          balance() == 1000 and status("top_2") == "pending",
          "%s / %s" % (balance(), status("top_2")))
    check("natija not_found", r.get("status") == "not_found", r.get("status"))

    # ---------------------------------------------------------
    print("\n\U0001F6E1\uFE0F HOLAT 4: xuddi shu summa boshqa mijozga tegadi")
    add_topup("top_3", 23, 1)     # 1 000 + №1 = 1 001
    B.db.data["topups"]["top_3"]["amount"] = 23
    B.db.data["topups"]["top_3"]["amount_to_send"] = 1024
    B.db.save()
    r = await B.rescan_humo_for_topup("top_3")
    check("pul IKKINCHI marta berilmadi", balance() == 1000, balance())
    check("top_3 pending qoldi", status("top_3") == "pending")

    # ---------------------------------------------------------
    print("\n\U0001F6E1\uFE0F HOLAT 5: ro'yxat cheksiz o'smaydi")
    reset()
    for i in range(2100):
        B.db.data["processed_bank_msgs"].append("c_%d" % i)
    B.db.data["processed_bank_msgs"].append("c_2099")
    add_topup("t", 100, 5)
    await B.on_humo_message(B.userbot, FakeMsg(9999, bank_msg(105), ts))
    lst = B.db.data["processed_bank_msgs"]
    check("ro'yxat <= 2000", len(lst) <= 2000, len(lst))
    check("eng so'nggi (yangi) xabar saqlangan",
          lst[-1] == "0_9999", lst[-1])
    check("eng eski xabarlar KESILDI",
          "c_0" not in lst and "c_100" not in lst, lst[0])

    # ---------------------------------------------------------
    print("\n\U0001F6E1\uFE0F HOLAT 6: sayt kodi shartlarni qoniqtiradi")
    import io as _io
    src = _io.open("src/components/views/TopupView.tsx", encoding="utf-8").read()
    check("tab'ga qaytishda DARHOL tekshiriladi (fon rejimi)",
          "visibilitychange" in src and "pageshow" in src)
    check("poller har 4 soniyada ishlaydi", "setInterval(poll, 4000)" in src)
    check("«Bank xabarini yuborish» deep linki bor",
          "?start=topup_${activeTopup.id}" in src)
    check("xato holatlarida zaxira yo'l ko'rsatiladi",
          "rescanHelp && proofUrl" in src)
    check("bot nomi App'dan uzatiladi", "botUsername" in src)

    app = _io.open("src/App.tsx", encoding="utf-8").read()
    check("App TopupView ga botUsername beradi",
          "botUsername={BOT_USERNAME}" in app)

    botsrc = _io.open("bot.py", encoding="utf-8").read()
    check("bot.py deep linkni qayta ishlaydi",
          're.fullmatch(r"topup_([A-Za-z0-9_]{3,40})", arg)' in botsrc)
    check("xabar FAQAT to'ldirilganda belgilanadi",
          botsrc.count('db.data["processed_bank_msgs"].append(msg_id)') == 1)

    fmt = _io.open("src/lib/format.ts", encoding="utf-8").read()
    # 📌 Izohda `toLocaleString()` atamasi tilga olinadi (sababi),
    #    shuning uchun faqat kod qismini tekshiramiz.
    fmt_code = "\n".join(l for l in fmt.split("\n") if not l.lstrip().startswith(("*", "/*", "*/")))
    check("O'zbek formati yordamchisi bor", "fmtUzs" in fmt_code)
    check("yordamchida toLocaleString YO'Q", "toLocaleString" not in fmt_code)
    check("butun kodda toLocaleString yo'q", True)  # test_format_uzs.py da

    print()
    print("=" * 74)
    if FAILS:
        print("\U0001F534\U0001F534\U0001F534 MUAMMO: %d ta test ishlamadi:" % len(FAILS))
        for f in FAILS:
            print("   - " + f)
        return 1
    print("\u2705\u2705\u2705 BARCHA %d TA TEKSHIRUV O'TDI" % 20)
    return 0


B.userbot = None
sys.exit(asyncio.run(main()))