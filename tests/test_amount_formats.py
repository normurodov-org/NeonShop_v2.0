# -*- coding: utf-8 -*-
"""
🔢 SUMMA FORMATLARI — mijoz ko'rsatgan bank ko'rinishi

Mijoz (2026-10-17): «Kutililayotgan summani mana bunday formatda
qidirib ko'r: 1 025 so'm -> 1.025,00 UZS»

Bank xabari:
    🎉 To'ldirish
    ➕ 1.025,00 UZS (Mijoz tolagan summa)
    📍 CLICK EWALLET HUMO>T
    💳 HUMOCARD *3682
    🕓 17:19 16.10.2026
    💰 3.391,91 UZS
"""
import io
import os
import re
import sys
from decimal import Decimal, InvalidOperation
from typing import Optional

sys.path.insert(0, '.')
import bot as B  # noqa: E402

FAILS = []


def check(cond, msg):
    print(("  \u2705 " if cond else "  \u274c ") + msg)
    if not cond:
        FAILS.append(msg)


def section(t):
    print("\n" + "=" * 74)
    print(t)
    print("=" * 74)


BANK = (
    "\U0001F389 To'ldirish\n"
    "\u2795 1.025,00 UZS (Mijoz tolagan summa)\n"
    "\U0001F4CD CLICK EWALLET HUMO>T\n"
    "\U0001F4B3 HUMOCARD *3682\n"
    "\U0001F553 17:19 16.10.2026\n"
    "\U0001F4B0 3.391,91 UZS"
)

# ═════════════════════════════════════════════════════════════════════════════
section("1) \U0001F5FA\u1F534 MIJOZNING ANIQ XABARI")
for l in BANK.splitlines():
    print("     ", l)
p = B.parse_humo_payment(BANK)
print("      parser ->", p)
check(p == (1025, "3682"), "parser: to'lov 1025, karta 3682 (qoldiq 3391 EMAS)")
check(B._text_has_amount(BANK, 1025), "matnli moslik: 1025 topildi")
check(not B._text_has_amount(BANK, 1000), "so'rangan 1000 topilmadi (faqat yuborilgani)")

# ═════════════════════════════════════════════════════════════════════════════
section("2) \U0001F522 SUMMA YOZILISHLARI — hammasi qabul qilinadi")
for txt, n, nm in [
    ("\u2795 1.025,00 UZS", 1025, "HUMO ko'rinishi (mijoz aytgan)"),
    ("\u2795 1 025,00 UZS", 1025, "bo'shli ajratuvchi"),
    ("\u2795 1025 UZS", 1025, "oddiy son"),
    ("\u2795 1,025.00 UZS", 1025, "AQSH format (vergul oldinga)"),
    ("\u2795 1.025,50 UZS", 1025, "qisman to'lov"),
    ("\u2795 1025,00 UZS", 1025, "vergulli"),
    ("\u2795 1.025,99 UZS", 1025, "99 butunlikka"),
]:
    check(B._text_has_amount(txt, n), nm)

# ═════════════════════════════════════════════════════════════════════════════
section("3) \U0001F534 NOTO'G'RI TOPILMASI \u2014 boshqa summa mos bo'lmasin")
for txt, n, nm in [
    ("\u2795 2.000,00 UZS", 1025, "boshqa yaxlit summa"),
    ("\u2795 3.391,91 UZS", 1025, "qoldiq balans"),
    ("\u2795 1.024,00 UZS", 1025, "1 so'm kam (seq mos kelmaydi)"),
]:
    check(not B._text_has_amount(txt, n), nm)

# ═════════════════════════════════════════════════════════════════════════════
section("4) \U0001F41B\u1F537 QISQA SUMMA xarakteri YO'Q (eng muhim)")
# 🔴 1 025 vs 10 250 — agar raqamlar "yirg'ib" tekshirilsa, 10 250 da
#    "1025" BOR va noto'g'ri topib olinadi. Bu xato bo'lmasligi kerak.
for txt, n, nm in [
    ("\u2795 10.250,00 UZS", 1025, "10 250 (1 025 EMAS!)"),
    ("\u2795 102.500,00 UZS", 1025, "102 500"),
    ("\u2795 210.250,00 UZS", 1025, "210 250"),
    ("\u2795 1.025.000,00 UZS", 1025, "1 025 000"),
]:
    check(not B._text_has_amount(txt, n),
          nm + " -> xato moslik YO'Q")

# ═════════════════════════════════════════════════════════════════════════════
section("5) \U0001F517 RESCAN ikki darajali moslik ishlatadi")
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "bot.py"), encoding="utf-8").read()
fn = src.split("async def rescan_humo_for_topup")[1].split("\nasync def ")[0]
code = "\n".join(l for l in fn.split("\n") if not l.strip().startswith("#"))
check("_text_has_amount" in code, "rescan matnli moslikni ham chaqiradi")
check("parsed[0] in (to_send, req)" in code, "sonliq moslik ham saqlangan (asosiy)")

# ═════════════════════════════════════════════════════════════════════════════
section("6) \U0001F5FA\u1F534 BANK CHATI TOPISH — uch usul + zaxira")
fh = src.split("async def _ub_humo_chat")[1].split("\nasync def ")[0]
for nm, frag in [
    ("1) `get_chat`", "ub.get_chat("),
    ("2) `resolve_peer`", "ub.resolve_peer("),
    ("3) `t.me/<username>`", "https://t.me/"),
    ("4) dialoglar ro'yxati (zaxira)", "ub.get_dialogs("),
]:
    check(frag in fh, nm)
check("uname.upper()" in fh, "KATTA harfli variant (@HUMOcardbot) sinanadi")
check("def _ub_humo_chat()" in src, "funksiya chat_id QAYTARADI (Chat obyekti emas)")

print()
if FAILS:
    print("NATIJA: \u274c MUAMMO BOR (%d ta)" % len(FAILS))
    for f in FAILS:
        print("   - " + f)
    raise SystemExit(1)
print("NATIJA: \u2705 BARCHASI TO'G'RI")
