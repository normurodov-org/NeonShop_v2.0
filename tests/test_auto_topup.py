# -*- coding: utf-8 -*-
"""
💳🔴 AVTO HISOB TO'LDIRISH — MIJOZNING ANIQ XABARI BILAN

Mijoz so'rovi (2026-10-17):
  «mijoz so'ragan summa + buyurtma raqami = kursatgan summani
   to'laganda avtomatik aniqlamayapti»

Bank xabari formati (mijoz bergan):
    🎉 To'ldirish
    ➕ 1.321,00 UZS (Mijoz tolagan summa)
    📍 CLICK EWALLET HUMO>T
    💳 HUMOCARD *3682
    🕓 17:19 16.10.2026
    💰 3.391,91 UZS

Bu test shu oqimning ICHKI MANTIQLINI tekshiradi:
  1) Parser shu formatni TO'G'RI o'qishi (qoldiq balans emas!)
  2) To'liq oqim: so'rov -> to'lov -> balans (so'ragan summa qo'shiladi)
  3) 🔴 seq BIR XIL chiqmasin — ikki mijozga bir xil raqam BERILMASIN
  4) 🔴 seq QAYTA ishlatilmasin (topup tozalandi keyin ham)
  5) To'lov mos kelmasa — adminga TUSHUNARLI diagnostika
"""
import asyncio
import re
import sys
import time
import types

sys.path.insert(0, '.')
import bot as B  # noqa: E402

# ── MIJOZNING ANIQ XABARI ─────────────────────────────────────────────────────
# ⚠️ `➕` — U+2795. Regexda `\+` bilan ALMASHMAYDI, shuning uchun
#    summani `re.sub` bilan emas, qatorlarni qayta qurish bilan almashtiramiz.
HUMO_TEMPL = (
    "\U0001F389 To'ldirish\n"
    "{PAY_LINE}\n"
    "\U0001F4CD CLICK EWALLET HUMO>T\n"
    "\U0001F4B3 HUMOCARD *3682\n"
    "\U0001F553 17:19 16.10.2026\n"
    "\U0001F4B0 {BALANCE_LINE}"
)


def bank_msg(amount: float, balance: float = 3391.91) -> str:
    """Bank xabarini berilgan summa bilan qayta quramiz."""
    return HUMO_TEMPL.format(
        PAY_LINE=f"\u2795 {amount:,.2f} UZS (Mijoz tolagan summa)",
        BALANCE_LINE=f"{balance:,.2f} UZS",
    )


class FakeBot:
    """Xabar yuborish — hech narsani chiqarmaydi, faqat hisoblaydi."""

    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, **kw):
        self.sent.append((chat_id, text))
        return types.SimpleNamespace(message_id=len(self.sent))


ADMIN_MSGS = []


async def _notify(text):
    ADMIN_MSGS.append(text)


FAKE = FakeBot()
B.bot = FAKE
B.notify_admins = _notify


class BankMsg:
    def __init__(self, text, mid):
        self.text = text
        self.id = mid
        self.chat = types.SimpleNamespace(id=100)


# ── Yordamchilar ──────────────────────────────────────────────────────────────
def reset_db():
    B.db.data["topups"] = {}
    B.db.data["processed_bank_msgs"] = []
    B.db.data.setdefault("settings", {}).pop("topup_seq", None)
    for uid, name in ((777, "birinchi"), (888, "ikkinchi"), (999, "uchinchi")):
        B.db.get_or_create_user(uid, name, name)
        B.db.data["users"][str(uid)]["balance"] = 0
    B.db.save()


def add_topup(tid, uid, amount, seq, status="pending"):
    """`amount + seq` — mijoz kartaga yuborishi kerak bo'lgan summa."""
    B.db.data["topups"][tid] = {
        "id": tid, "user_id": uid, "amount": amount, "seq": seq,
        "amount_to_send": amount + seq, "status": status,
        "created_at": B.now_iso(),
        "expires_at": time.time() + 3600,
    }
    B.db.save()


def balance(uid):
    return int(B.db.data["users"][str(uid)].get("balance", 0))


def status(tid):
    return B.db.data["topups"][tid]["status"]


# ═════════════════════════════════════════════════════════════════════════════
async def t1_parser():
    """Mijozning ANIQ xabari: to'lov 1 321, qoldiq balans 3 391,91."""
    print("1) PARSER — mijozning aniq xabari")
    txt = bank_msg(1321)
    for line in txt.splitlines():
        print("     ", line)
    r = B.parse_humo_payment(txt)
    print("      ->", r)
    ok = r == (1321, "3682")
    print(("  \u2705 " if ok else "  \u274c ") + "to'lov 1321, karta 3682 (qoldiq 3391 EMAS)")
    return ok


# ═════════════════════════════════════════════════════════════════════════════
async def t2_full_flow():
    """1 000 so'm + №22 = 1 022 yuboriladi -> balansga 1 000 qo'shiladi."""
    print("\n2) TO'LIQ OQIM — 1 000 so'm so'radim, №22 qo'shildi")
    reset_db()
    add_topup("top_x", 777, 1000, 22)
    print("      bot ko'rsatdi: kartaga yuboring 1 022 UZS (so'ragan 1 000 · №22)")
    ADMIN_MSGS.clear()
    await B.on_humo_message(None, BankMsg(bank_msg(1022), 1))
    b = balance(777)
    st = status("top_x")
    ok = st == "completed" and b == 1000
    print(("  \u2705 " if ok else "  \u274c ") + "topup %s · balans %d (kerak: completed · 1000)" % (st, b))
    if not ok:
        print("      \U0001F534 balansga 1022 qo'shilmASI kerak edi — "
              "raqam FAQAT farqlash uchun, mijozga 1 000 beriladi")
    return ok


# ═════════════════════════════════════════════════════════════════════════════
async def t3_seq_collision():
    """🔴 Ikki mijoz bir vaqtda so'raydi — raqamlar BIR XIL bo'lmasin."""
    print("\n3) \U0001F534\U0001F534\U0001F534 SEQ CHALASHMASIN — 2 mijoz, 1 000 so'm")
    reset_db()
    s1 = B.next_topup_seq()
    add_topup("top_a", 777, 1000, s1)
    s2 = B.next_topup_seq()
    add_topup("top_b", 888, 1000, s2)
    a = B.db.data["topups"]["top_a"]["amount_to_send"]
    b = B.db.data["topups"]["top_b"]["amount_to_send"]
    print("      1-mijoz: №%d -> %d UZS" % (s1, a))
    print("      2-mijoz: №%d -> %d UZS" % (s2, b))
    ok = a != b
    print(("  \u2705 " if ok else "  \u274c ") + "turli summalar (bir xil bo'lsa — chalkash!)")

    # Endi 1-mijoz to'ladi — FAQAT u to'ldirilishi kerak
    ADMIN_MSGS.clear()
    await B.on_humo_message(None, BankMsg(bank_msg(a), 2))
    b1, b2 = balance(777), balance(888)
    ok2 = b1 == 1000 and b2 == 0
    print(("  \u2705 " if ok2 else "  \u274c ") + "1-mijoz to'lov qildi: 777=%d, 888=%d (kerak 1000 / 0)" % (b1, b2))

    # 2-mijoz to'ladi — u ham to'ldirilishi kerak
    ADMIN_MSGS.clear()
    await B.on_humo_message(None, BankMsg(bank_msg(b), 3))
    b1, b2 = balance(777), balance(888)
    ok3 = b1 == 1000 and b2 == 1000
    print(("  \u2705 " if ok3 else "  \u274c ") + "2-mijoz to'lov qildi: 777=%d, 888=%d (kerak 1000 / 1000)" % (b1, b2))
    return ok and ok2 and ok3


# ═════════════════════════════════════════════════════════════════════════════
async def t4_seq_no_reuse():
    """🔴 Topuplar tozalandi keyin ham ESKI raqam qayta chiqmasin."""
    print("\n4) \U0001F534 SEQ QAYTA ISHLATILMASIN (topup tozalandi keyin)")
    reset_db()
    s1 = B.next_topup_seq()
    B.db.data["topups"]["old"] = {
        "id": "old", "user_id": 777, "amount": 5000, "seq": s1,
        "amount_to_send": 5000 + s1, "status": "completed",
    }
    B.db.save()
    # 🔴 Topuplar butunlay tozalanadi (arxivlash, DB tozalash)
    B.db.data["topups"] = {}
    B.db.save()
    s2 = B.next_topup_seq()
    print("      №%d ishlatildi -> topuplar tozalandi -> №%d" % (s1, s2))
    ok = s2 > s1
    print(("  \u2705 " if ok else "  \u274c ") + "yangi raqam eskisidan KATTА (qayta ishlatilmadi)")
    return ok


# ═════════════════════════════════════════════════════════════════════════════
async def t5_server_source():
    """🔴 server.ts ham XUDDI shu manbadan o'qisin (xotirada emas)."""
    print("\n5) \U0001F534\U0001F534\U0001F534 server.ts — xotiradagi hisoblagich emas")
    s = open("server.ts", encoding="utf-8").read()
    body = s.split("function nextTopupSequence")[1][:900]
    db_src = "settings" in body and "topup_seq" in body
    boot = s.split("function loadTopupSequence")[1][:900]
    uses_topups = "topups" in boot
    print("      nextTopupSequence -> settings.topup_seq yozadi:", db_src)
    print("      loadTopupSequence -> topuplardan eng kattasi:", uses_topups)
    ok = db_src and uses_topups
    print(("  \u2705 " if ok else "  \u274c ") + "bitta manba (settings.topup_seq)")
    return ok


# ═════════════════════════════════════════════════════════════════════════════
async def t6_diagnostics():
    """Mos kelmasa — admin TUSHARLI diagnostika oladi."""
    print("\n6) MOS KELMASA — admin uchun tushunarli xabar")
    reset_db()
    add_topup("top_a", 777, 1000, 5)
    add_topup("top_b", 888, 2000, 6)
    ADMIN_MSGS.clear()
    await B.on_humo_message(None, BankMsg(bank_msg(999999), 9))
    txt = " ".join(ADMIN_MSGS)
    ok = ("999" in txt.replace("\u202f", " ").replace(" ", "")
          or "999999" in txt.replace(" ", "")) and balance(777) == 0 and balance(888) == 0
    print(("  \u2705 " if ok else "  \u274c ") + "hech kimga pul qo'shilmadi, admin ogohlantirildi")
    for m in ADMIN_MSGS:
        print("      [admin]", m.replace("\n", " | ")[:120])
    return ok


async def main():
    print("=" * 74)
    print("\U0001F4B3\U0001F534 AVTO HISOB TO'LDIRISH — mijozning aniq xabari")
    print("=" * 74)
    results = []
    results.append(("parser", await t1_parser()))
    results.append(("to'liq oqim", await t2_full_flow()))
    results.append(("seq chalkashmasin", await t3_seq_collision()))
    results.append(("seq qayta ishlatilmasin", await t4_seq_no_reuse()))
    results.append(("server bitta manba", await t5_server_source()))
    results.append(("diagnostika", await t6_diagnostics()))

    print()
    print("=" * 74)
    for nom, ok in results:
        print(("  \u2705 " if ok else "  \u274c ") + nom)
    bad = [n for n, o in results if not o]
    print("=" * 74)
    if bad:
        print("NATIJA: \u274c MUAMMO BOR (%d ta): %s" % (len(bad), ", ".join(bad)))
        return 1
    print("NATIJA: \u2705 BARCHASI TO'G'RI")
    return 0


sys.exit(asyncio.run(main()))
