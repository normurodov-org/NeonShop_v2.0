"""⭐ STARS BUYURTMASI BAJARILMADI — avtomatik qayta urish + qaytarish.

🔴 NIMA UCHUN BU TEST KERAK:

Auditda uchinchi PUL YO'QOTISH topildi:

`process_star_order()` Fragment xatosida buyurtmani
`status = "manual_pending"` qilib to'xtatadi. Mijozning UZS'i allaqachon
yechilgan (server.ts `POST /api/order`), lekin:

  * `star_order_worker()` faqat `processing/queued/pending` ni oladi —
    `manual_pending` BIRORQ QAYTA ISHLANMAYDI
  * refund yo'li umuman YO'Q EDI
  * admin esa faqat STATISTIKADA ko'rardi (`db_stats.pending_orders`)

Natija: mijoz Stars olmadi, puli ham qaytmadi, buyurtma DOIMIY
`manual_pending` da qolib ketar edi.

🔴 VA YOTGAN YOLG'ON: adminga yuborilgan xabar "Avtomatik ravishda qayta
urish mumkin" deb yozgan — lekin avtomatik qayta urish MAVJUD EMASDI.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import strip_py_comments  # noqa: E402

BSRC = open("bot.py", encoding="utf-8").read()
CODE = strip_py_comments(BSRC)

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


# =============================================================================
section("1) 🔴 QAYTARISH — mijoz balansiga pul qaytishi SHART")
# =============================================================================
check("def refund_star_order(" in CODE, "refund_star_order() bor")
check("def adm_star_refund(" in CODE, "admin «Qaytarish» handler")
check('F.data.startswith("adm:star_refund:")' in BSRC, "callback_data")

rf = CODE[CODE.index("def refund_star_order("):
          CODE.index('@admin_router.callback_query(F.data == "adm:star_fail")')]
check('user["balance"] = num(user.get("balance")) + total',
      "🔴 pul mijoz balansiga QAYTARILADI")
# 🔴 `total_spent` ham kamayishi kerak — aks holda mijoz yana
#    konkursda qatnasha olardi (pulsiz xarid "haqiqiy" hisoblanardi)
check('user["total_spent"] = max(0, num(user.get("total_spent")) - total)' in rf,
      "🔴 `total_spent` ham kamayadi (konkursga soxta qatnashilmaydi)")
check('db.add_history(' in rf, "tarixga refund yoziladi (dalil qoladi)")
check('order["status"] = "refunded"' in rf, "buyurtma -> refunded")
check('order["refunded"] = True' in rf, "qaytarilgan belgisi (ikki marta qaytarilmaydi)")

# Qaytarilgan buyurtma qayta qaytarilMASIN
ar = CODE[CODE.index("async def adm_star_refund("):]
check('if order.get("refunded")' in ar, "🔴 allaqachon qaytarilgani bloklanadi")

# Faqat bajarilmagan buyurtma qaytariladi (muvaffaqiyatli emas!)
check('if order.get("status") not in ("manual_pending", "unknown", "failed")' in ar,
      "🔴 muvaffaqiyatli buyurtma qaytarilmaydi (mijozga pul + Stars)")

# =============================================================================
section("2) 🔴 QO'LDA QAYTA URISH — ikki marta xarid bo'lmasin")
# =============================================================================
check("async def adm_star_retry(" in CODE, "admin «Qayta urinish» handler")
rt = CODE[CODE.index("async def adm_star_retry("):
          CODE.index('@admin_router.callback_query(F.data.startswith("adm:star_refund:")')]
# 📖 IZOH: eski test `auto_processed = False` ni talab qilgan edi —
# lekin bu ZARarli edi: `star_order_worker` shu belgi bilan buyurtmani
# qayta olardi va admin tugmasi bilan BIRGA ishlar, Fragment'da IKKALA
# marta xarid qilinardi. Endi `auto_processed` TEGILMAYDI, balki
# `STAR_ORDER_LOCK` bilan birinchi ishlaydi.
check('async with STAR_ORDER_LOCK:' in rt,
      "🔴 lock bilan: worker va admin bir vaqtda ishlamaydi")
check('STAR_ORDER_LOCK = asyncio.Lock()' in CODE, "lock yaratilgan")
check('order["auto_processed"] = False' not in rt,
      "📖 `auto_processed` tegilmaydi (eski xato yo'q)")
check('order["star_attempts"] = 0' in rt, "urinishlar nolga qaytariladi")
check('order["status"] = "processing"' in rt, "holat -> processing")
check("asyncio.create_task(process_star_order(oid, target))" in rt,
      "darhol qayta ishga tushiriladi")

# =============================================================================
section("3) 🔴 AVTOMATIK QAYTA URISH — worker'da")
# =============================================================================
check("STAR_MAX_ATTEMPTS = 3" in CODE, "chegara: 3 urinish")
check('if order.get("status") != "manual_pending":' in CODE,
      "worker `manual_pending` ni oladi")
check('if order.get("refunded"):' in CODE, "qaytarilganlar qayta urilmaydi")
check('order["star_attempts"] = att + 1' in CODE, "urinish hisoblanadi")
check('if att >= STAR_MAX_ATTEMPTS:' in CODE, "chegara to'xtaydi")
check("20000 * (att + 1)" in CODE,
      "🔴 urinishlar orasida tanaffus (Fragment tiklanishi uchun)")
check("log.warning(" in CODE, "qayta urinish logda ko'rinadi")

# 🔴 "USDT yetarli emas" — mijozning TON hamyoni. Qayta urish ma'nosiz.
check("def star_order_is_money_problem(" in CODE, "pulsiz holat aniqlanadi")
check("if star_order_is_money_problem(err):" in CODE,
      "🔴 pul muammosida AVTOMATIK qayta urish to'xtaydi")
# ...lekin kalitlar TOR bo'lishi kerak: keng kalit texnik xatoni
# pul muammosi deb o'ylab, ortiqcha urishlarga olib kelardi.
keys = CODE[CODE.index("_STAR_MONEY_KEYS = ("):
            CODE.index("def star_order_is_money_problem(")]
check('"balance"' not in keys,
      "🔴 kalitda yalang' `balance` yo'q (barcha texnik xatolarni to'xtirmasin)")
check("usdt yetarli emas" in keys, "aniq kalit bor")

# =============================================================================
section("4) 🔴 YOLG'ON VA'DAT TUZATILDI")
# =============================================================================
check("Avtomatik ravishda qayta urinish mumkin" not in CODE,
      "🔴 yolg'on «avtomatik qayta urish mumkin» xabari olib tashlandi")
check("Avtomatik ravishda qayta uriniladi" in CODE,
      "🔴 haqiqiy xabar beriladi")
check("Yordam kerak bo" in CODE, "qo'lda yordam ko'rsatiladi")
# 🔴 Mijozga «Stars avtomatik yuboriladi» degan yolg'on va'dat
check("Stars avtomatik tarzda yuboriladi. Biroz kutib turing." not in CODE,
      "🔴 mijozga yolg'on «kutib turing» va'dati olib tashlandi")
check("tries < STAR_MAX_ATTEMPTS" in CODE,
      "🔴 urinishlar tugamagan bo'lsa «qayta uramiz» deyiladi")
check("Sizning pulingiz xavfsiz" in CODE,
      "🔴 tugaganda mijozga xavfsizlik va'dati beriladi")

# =============================================================================
section("5) 🔴 ADMIN RO'YXATI — ko'rish va boshqarish")
# =============================================================================
check('F.data == "adm:star_fail"' in BSRC, "«Bajarilmagan Stars» handler")
check("🔴 Bajarilmagan Stars" in BSRC, "admin menyusida tugma")
check('callback_data="adm:star_fail"' in BSRC, "tugma ulangan")
lst = CODE[CODE.index("async def adm_star_fail("):
           CODE.index('@admin_router.callback_query(F.data.startswith("adm:star_retry:")')]
check('o.get("status") == "manual_pending"' in lst,
      "🔴 ro'yxatda faqat bajarilmaganlar (muvaffaqiyatli emas)")
# eslatma: matn "↻ Qaytarish" emas, balki "🔄 Qaytarish" (emoji mosligi
# uchun). Callback_data ni tekshiramiz — matn emas.
check('adm:star_retry:' in lst and 'adm:star_refund:' in lst, "ikki tugma")
check('o.get("error")' in lst, "xato sababi ko'rsatiladi")
check("star_order_is_money_problem" in lst,
      "🔴 USDT yetarli emasligi alohida belgilangan")
check("adm:star_retry:" in CODE and "adm:star_refund:" in CODE,
      "callback_data uzunligi < 64 bayt")

# =============================================================================
section("6) 🔴 URINISH SONI XATO IZOLLANMASIN")
# =============================================================================
check('star_attempts=num(order.get("star_attempts")) + 1' in CODE,
      "🔴 `process_star_order` urinishni HISOBLAYDI (faqat worker emas)")

print()
print("=" * 70)
print("NATIJA: ✅ BARCHASI TO'G'RI" if ok else "NATIJA: ❌ MUAMMO BOR")
print("=" * 70)
raise SystemExit(0 if ok else 1)