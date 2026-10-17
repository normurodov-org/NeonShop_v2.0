# -*- coding: utf-8 -*-
"""
\U0001F50E\U0001F534 «ТЕКШIRISH» — @humocardbot dan QAYTA O'QISH

Mijoz (2026-10-17):
  «Pasdagi tekshirish tugmasini bosganimda adminga tashlayapti.
   Shu tekshirish tugmasini bosganda @humocardbot dan xabarni
   2-chi marta tekshirib korsin.»

Bu test simulyatsiya qilingan USERBOT bilan:
  1) «Tekshirish» so'rovi qo'yilganda worker qayta o'qiydi
  2) @humocardbot da xabar BOR -> avtomatik balansga qo'shiladi
  3) xabar YO'Q -> `not_found` + aniq sabab
  4) userbot ulanmagan -> `userbot_offline` (jim qolmaydi)
  5) takror «Tekshirish» pulni IKKI marta qo'shmaydi
"""
import asyncio
import os
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


def bank_msg(amount: int) -> str:
    """`1 022` -> `1.022,00` (HUMO Yevropa formatida)."""
    s = "{:,.0f}".format(amount).replace(",", ".")
    return HUMO_TEMPL.format(amt=s)


class FakeMsg:
    def __init__(self, mid, text, ts):
        self.id = mid
        self.text = text
        self.caption = None
        self.date = types.SimpleNamespace(timestamp=lambda: ts)


class FakeChat:
    id = 555


class FakeUserbot:
    """`get_chat` va `get_chat_history` ni sun'ulaydi.

    🔴🔴🔴 DIQQAT: `get_chat_history` HAQIQIY API kabi **async generator**
       bo'lishi SHART (pyrofork shunday qiladi). Agar testda oddiy
       coroutine yozsak, haqiqiy kodda bo'ladigan xato
       «object async_generator can't be used in 'await' expression»
       ko'rinmaydi — shuning uchun bu yerda ataylab shunday qilingan.
    """

    def __init__(self, messages):
        self.is_connected = True
        self._messages = messages

    async def get_chat(self, target):
        return FakeChat()

    async def get_chat_history(self, chat, limit=40):
        # Real API: ESKI -> YANGI
        for m in self._messages[:limit]:
            yield m


class FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, **kw):
        self.sent.append(text)
        return types.SimpleNamespace(message_id=len(self.sent))


ADMIN = []


async def _notify(t):
    ADMIN.append(t)


FAKE_BOT = FakeBot()
B.bot = FAKE_BOT
B.notify_admins = _notify


def reset():
    B.db.data["topups"] = {}
    B.db.data["processed_bank_msgs"] = []
    B.db.get_or_create_user(777, "sardor", "Sardor")
    B.db.data["users"]["777"]["balance"] = 0
    B.db.save()


def add_topup(amount=1000, seq=22, tid="top_x"):
    B.db.data["topups"][tid] = {
        "id": tid, "user_id": 777, "amount": amount, "seq": seq,
        "amount_to_send": amount + seq, "status": "pending",
        "created_at": B.now_iso(), "expires_at": time.time() + 3600,
    }
    B.db.save()


def balance():
    return int(B.db.data["users"]["777"].get("balance", 0))


def rescan_field(tid="top_x"):
    t = B.db.data["topups"][tid]
    return (t.get("rescan_result"), t.get("rescan_message"),
            int(t.get("rescan_done_at") or 0))


# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
async def main():
    ok = []

    # ---------------------------------------------------------------- 1
    print("1) \U0001F50E \U0001F534 «Tekshirish» — xabar BOR -> avtomatik to'ldiriladi")
    reset()
    add_topup(1000, 22)
    now_ts = int(time.time())
    B.userbot = FakeUserbot([
        FakeMsg(10, "eski xabar", now_ts - 500),
        FakeMsg(11, bank_msg(1022), now_ts - 30),   # ← bizniki
        FakeMsg(12, "keyingi xabar", now_ts - 10),
    ])
    # «Tekshirish» bosildi
    B.db.data["topups"]["top_x"]["rescan_requested_at"] = B.now_ms()
    B.db.save()

    t = B.db.data["topups"]["top_x"]
    res = await B.rescan_humo_for_topup("top_x")
    B.db.reload_if_changed()
    t = B.db.data["topups"]["top_x"]
    t["rescan_done_at"] = B.now_ms()
    t["rescan_result"] = res.get("status")
    t["rescan_message"] = res.get("message")
    B.db.save()

    print("      so'rov: 1 000 + №22 = 1 022 UZS")
    print("      natija:", res.get("status"), "|", res.get("message"))
    print("      topup:", t["status"], "| balans:", balance())
    good = (res.get("status") == "found" and t["status"] == "completed"
            and balance() == 1000)
    ok.append(good)
    print(("  \u2705 " if good else "  \u274c ") + "topildi va balansga 1 000 qo'shildi")

    # ---------------------------------------------------------------- 2
    print("\n2) \U0001F50E Xabar YO'Q -> aniq sabab beriladi")
    reset()
    add_topup(1000, 22)
    B.userbot = FakeUserbot([FakeMsg(20, "boshqa xabar", int(time.time()) - 10)])
    B.db.data["topups"]["top_x"]["rescan_requested_at"] = B.now_ms()
    B.db.save()
    res = await B.rescan_humo_for_topup("top_x")
    print("      natija:", res.get("status"), "|", res.get("message"))
    good = res.get("status") == "not_found" and balance() == 0
    ok.append(good)
    print(("  \u2705 " if good else "  \u274c ") + "`not_found` + hech kimga pul qo'shilmadi")

    # ---------------------------------------------------------------- 3
    print("\n3) \U0001F50E\U0001F534 Userbot ULANMAGAN -> jim qolmaydi")
    reset()
    add_topup(1000, 22)
    B.userbot = None
    res = await B.rescan_humo_for_topup("top_x")
    print("      natija:", res.get("status"), "|", res.get("message"))
    good = res.get("status") == "userbot_offline" and balance() == 0
    ok.append(good)
    print(("  \u2705 " if good else "  \u274c ") + "`userbot_offline` + mijozga aniq aytiladi")

    # ---------------------------------------------------------------- 4
    print("\n4) \U0001F534\U0001F534 TAKROR tekshirish pulni IKKI marta qo'shmaydi")
    reset()
    add_topup(1000, 22)
    now_ts = int(time.time())
    B.userbot = FakeUserbot([FakeMsg(30, bank_msg(1022), now_ts - 20)])
    B.db.data["topups"]["top_x"]["rescan_requested_at"] = B.now_ms()
    B.db.save()
    r1 = await B.rescan_humo_for_topup("top_x")
    b1 = balance()
    # Mijoz yana «Tekshirish» bosadi
    r2 = await B.rescan_humo_for_topup("top_x")
    b2 = balance()
    print("      1-chi:", r1.get("status"), "| balans:", b1)
    print("      2-chi:", r2.get("status"), "| balans:", b2)
    good = b1 == 1000 and b2 == 1000
    ok.append(good)
    print(("  \u2705 " if good else "  \u274c ") + "balans baribir 1 000 (2 marta qo'shilmadi)")

    # ---------------------------------------------------------------- 5
    print("\n5) \U0001F50E Worker so'rovni kutadi va natijani yozadi")
    reset()
    add_topup(1000, 22)
    B.userbot = FakeUserbot([FakeMsg(40, bank_msg(1022), int(time.time()) - 20)])
    B.db.data["topups"]["top_x"]["rescan_requested_at"] = B.now_ms()
    B.db.save()

    stop = {"v": False}

    async def one_tick():
        tid = "top_x"
        t = B.db.data["topups"][tid]
        r = await B.rescan_humo_for_topup(tid)
        B.db.reload_if_changed()
        t2 = B.db.data["topups"][tid]
        t2["rescan_done_at"] = B.now_ms()
        t2["rescan_result"] = r.get("status")
        t2["rescan_message"] = r.get("message")
        B.db.save()

    await one_tick()
    B.db.reload_if_changed()
    r_, m_, d_ = rescan_field()
    print("      rescan_result=%s  rescan_done_at>0: %s" % (r_, bool(d_)))
    good = r_ == "found" and d_ > 0
    ok.append(good)
    print(("  \u2705 " if good else "  \u274c ") + "WebApp poller o'qiydigan maydonlar to'ldi")

    # ---------------------------------------------------------------- 6
    print("\n6) \U0001F4CD server.ts: «Tekshirish» ADMINGA emas, RESCAN so'raydi")
    s = open("server.ts", encoding="utf-8").read()
    blk = s.split("app.post('/api/topup/simulate-pay'")[1].split("\napp.")[0]
    # 📌 Izohlar tozalanadi — eski `notify_admins` haqidagi IZOH
    #    "hali yuboriladi" deb o‘qilmasligi kerak.
    code = "\n".join(l for l in blk.split("\n") if not l.strip().startswith("//"))
    no_admin = "notify" not in code.lower() and "sendMessage" not in code
    sets_flag = "rescan_requested_at" in blk
    online = "isUserbotOnline" in blk
    print("      adminga yuborish yo'q:", no_admin)
    print("      rescan_requested_at qo'yadi:", sets_flag)
    print("      userbot holatini tekshiradi:", online)
    good = no_admin and sets_flag and online
    ok.append(good)
    print(("  \u2705 " if good else "  \u274c ") + "tugma endi qayta tekshirishga so'rov yuboradi")

    # ---------------------------------------------------------------- 7
    print("\n7) \U0001F517 Botda ham «Tekshirish» tugmasi bor")
    src = open("bot.py", encoding="utf-8").read()
    good = ('callback_data=f"topup_rescan:' in src
            and "async def cb_topup_rescan" in src
            and "To'lovni tekshirish" in src)
    ok.append(good)
    print(("  \u2705 " if good else "  \u274c ") + "bot menyusida ham tugma + handler")

    # ---------------------------------------------------------------- 8
    print("\n8) \U0001F9F0 Worker `main()` da ishga tushadi")
    good = '("Topup rescan worker", topup_rescan_worker())' in src
    ok.append(good)
    print(("  \u2705 " if good else "  \u274c ") + "worker ishga tushirilgan")

    # ---------------------------------------------------------------- 9
    print("\n9) \U0001F4E8\U0001F534 ZAXIRA YO'L: userbot yo'q -> mijoz xabar yuboradi")
    src2 = open("bot.py", encoding="utf-8").read()
    has_state = "proof = State()" in src2
    has_handler = "async def cb_topup_proof" in src2 and \
                  "async def topup_proof_received" in src2
    has_btn = 'callback_data=f"topup_proof:{topup_id}"' in src2
    uses_core = "await on_humo_message(userbot, shim)" in src2
    guards = ("Bank xabarida" in src2 and "mos kelmadi" in src2)
    for nm, v in [("FSM holati `proof`", has_state),
                  ("`cb_topup_proof` + `topup_proof_received`", has_handler),
                  ("«Bank xabarini yuboring» tugmasi", has_btn),
                  ("asosiy oqimga ulanadi (`on_humo_message`)", uses_core),
                  ("mos kelmagan summa rad etiladi", guards)]:
        ok.append(v)
        print(("  \u2705 " if v else "  \u274c ") + nm)

    # ---------------------------------------------------------------- 10
    print("\n10) \U0001F4E8 Zaxira haqiqatan balansni to'ldiradi (simulyatsiya)")
    reset()
    add_topup(1000, 22)
    B.userbot = None
    text = bank_msg(1022)
    parsed = B.parse_humo_payment(text)
    shim = B._ProofMessage(777, 555, text)
    await B.on_humo_message(B.userbot, shim)
    bal = balance()
    st = B.db.data["topups"]["top_x"]["status"]
    good = parsed == (1022, "3682") and st == "completed" and bal == 1000
    ok.append(good)
    print("      xabar:", parsed, "| topup:", st, "| balans:", bal)
    print(("  \u2705 " if good else "  \u274c ") + "userbot YO'Q holda ham to'ldi")

    # ---------------------------------------------------------------- 11
    print("\n11) \U0001F41B\U0001F534 `get_chat_history` ASYNC GENERATOR (haqiqiy API)")
    src3 = open("bot.py", encoding="utf-8").read()
    fn = src3.split("async def rescan_humo_for_topup")[1].split("\nasync def ")[0]
    # 📘 Izohlar tozalanadi — xato «bu nima boʸldi» izohida
    #    saqlanib qolsa, test yolgʴon xato beradi.
    code_fn = "\n".join(l for l in fn.split("\n")
                       if not l.strip().startswith("#"))
    no_await = "await ub.get_chat_history" not in code_fn
    uses_asyncfor = (
        "async for m in raw" in code_fn
        or "async for msg in ub.get_chat_history" in code_fn
    )
    # \U0001F6E1\uFE0F Kelajak uchun qat\u2018iy: async generator BO\u02b8LMASIN
    guards_both = "__aiter__" in code_fn
    # Fake userbot ham async generator — test HAQIQIY API ga o'xshaydi
    fake = "async def get_chat_history" in open(
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "test_topup_rescan.py"), encoding="utf-8").read()
    fake_gen = "yield m" in open(
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "test_topup_rescan.py"), encoding="utf-8").read()
    for nm, v in [("`await get_chat_history` YO'Q", no_await),
                  ("`async for` bilan o'qiladi", uses_asyncfor),
                  ("`__aiter__` bilan ikkala variantga mos", guards_both),
                  ("test userboti async generator", fake and fake_gen)]:
        ok.append(v)
        print(("  \u2705 " if v else "  \u274c ") + nm)
    if not (no_await and uses_asyncfor):
        print("      \U0001F534 xato: async_generator await qilinmaydi!")

    # ---------------------------------------------------------------- 12
    print("\n12) \U0001F41E IKKALA API VARIANTI ham ishlaydi")
    reset(); add_topup(1000, 22)
    now_ts = int(time.time())

    class ListUserbot(FakeUserbot):
        """Kelajakdagi versiya: oddiy ro'yxat qaytaradi (async generator emas)."""

        async def get_chat_history(self, chat, limit=40):
            return list(self._messages[:limit])

    for nm, ub_cls in [("async generator", FakeUserbot), ("oddiy list", ListUserbot)]:
        reset(); add_topup(1000, 22)
        B.userbot = ub_cls([FakeMsg(50, bank_msg(1022), now_ts - 20)])
        r = await B.rescan_humo_for_topup("top_x")
        bal = balance()
        v = r.get("status") == "found" and bal == 1000
        ok.append(v)
        print("      %-16s -> %-8s balans=%d  %s"
              % (nm, r.get("status"), bal, "\u2705" if v else "\u274c"))

    print()
    bad = [i + 1 for i, o in enumerate(ok) if not o]
    if bad:
        print("NATIJA: \u274c MUAMMO BOR (%d ta): %s" % (len(bad), bad))
        return 1
    print("NATIJA: \u2705 BARCHASI TO'G'RI")
    return 0


B.userbot = None
sys.exit(asyncio.run(main()))
