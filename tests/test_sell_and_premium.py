"""⭐ STARS SOTUV va 💎 TELEGRAM PREMIUM — to'liq pul oqimi.

🔴 NIMA UCHUN BU TEST KERAK:

Mijoz «Ko'plab funksiyalar ishlamayapti» deb xabar berdi va auditda
**ikki xil PUL YO'QOTISH** topildi:

1) `💸 Stars sotish`
   Stars Telegram tomonidan yechilib, savdo `awaiting_card` holatida
   YIG'ILIB QOLARDI:
     * karta uchun FSM state yo'q edi
     * savdoni ishlovchi worker yo'q edi
     * admin xabarnoma yo'q edi
   Natija: mijoz Stars'ini yo'qotadi, UZS hech qachon yuborilmaydi.

2) `💎 Telegram Premium`
   WebApp balansni yechib, buyurtmani `status: "completed"` bilan
   yozardi va mijozga «yetkazildi» degan xabar yuborardi — lekin
   Telegram Premium beradigan hech qanday kod yo'q edi
   (`star_order_worker()` faqat `kind == "stars"` ni qayta ishlaydi).
   Natija: mijoz 155 000–375 000 UZS to'laydi va HECH NARSA olmaydi.

Bu test ikkala oqim ham oxirigacha (karta -> to'lash, Premium -> berish
yoki qaytarish) ishlashini tekshiradi.
"""
import asyncio
import os
import re
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bot as B  # noqa: E402

BSRC = open("bot.py", encoding="utf-8").read()
SRV = open("server.ts", encoding="utf-8").read()
# Muhim: izohlarni olib tashlaymiz (helper import qilinishi SHART)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import strip_py_comments  # noqa: E402

# 🔴 `strip_py_comments` (tokenize asosida) — `strip_code` emas:
# u faqat `//` va `/** */` ni olib tashlaydi, Python'dagi `#`
# izohlarni — jumlatan — QOLDIRARDI va test o'z izohimizni
# "xato kod" deb qizil bo'lardi.
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
section("1) 💸 STARS SOTUV — karta qabul qilish bosqichi")
# =============================================================================
check("card = State()" in BSRC, "SellStates.card FSM state mavjud")
check("class SellStates(StatesGroup):" in BSRC, "SellStates guruhi")

# 🔴 ENG MUHIM: to'lov tugagach state o'tkazilishi SHART. Aks holda
#    keyingi xabar `SellStates.card` handler'iga tushmaydi.
pay = CODE[CODE.index("async def on_successful_payment("):
           CODE.index("@router.message(StateFilter(SellStates.card)")]
check("await state.set_state(SellStates.card)" in pay,
      "to'lovdan keyin `SellStates.card` ga o'tkaziladi")
check("await state.set_state(SellStates.card)" in pay,
      "set_state() avvalgi state'ni ALMASHTIRADI (clear kerak emas)")

check("async def adm_sell_card(" in CODE, "karta qabul qiluvchi handler")
card_h = CODE[CODE.index("async def adm_sell_card("):
              CODE.index("@admin_router.callback_query(F.data == \"adm:sales\")")]
check("StateFilter(SellStates.card)" in BSRC, "filtr: SellStates.card + matn")
# NOT_MENU: karta kutilayotgan mijoz menyu tugmasini bosmasin
check("StateFilter(SellStates.card), F.text, NOT_MENU" in BSRC,
      "NOT_MENU bilan filtrlangan (menyu tugmasi kartaga aylantirilmasin)")
check("db_user.get(\"pending_sale_card\")" in card_h,
      "savdo mijozga bog'langan (boshqaning savdosi emas)")
check('sale["status"] = "awaiting_payout"' in card_h,
      "karta kelgach -> awaiting_payout")
check("db_user[\"pending_sale_card\"] = None" in card_h,
      "karta olingach pending tozalanadi")
# savdo yaratilganda ham admin ogohlantirilishi SHART
check("notify_admins(" in pay, "Stars yuborilgach admin darhol xabar oladi")

# =============================================================================
section("2) 💸 STARS SOTUV — adminga boshqaruv tugmalari")
# =============================================================================
for cb, fn in (("adm:sales", "adm_sales"),
               ("adm:sale_ok:", "adm_sale_ok"),
               ("adm:sale_refund:", "adm_sale_refund"),
               ("adm:sale_nudge:", "adm_sale_nudge")):
    check(f'F.data.startswith("{cb}")' in BSRC or f'F.data == "{cb}"' in BSRC,
          f"handler bor: {cb}")

ok_h = CODE[CODE.index("async def adm_sale_ok("):
            CODE.index("@admin_router.callback_query(F.data.startswith(\"adm:sale_refund:")]
check('sale["status"] = "paid"' in ok_h, "«To'landi» -> paid")
check("db.reload_if_changed()" in ok_h, "diskdan qayta o'qiladi (-race)")

ref_h = CODE[CODE.index("async def adm_sale_refund("):
             CODE.index("@admin_router.callback_query(F.data.startswith(\"adm:sale_nudge:")]
check('sale["status"] = "refunded"' in ref_h, "refund -> refunded")
# 🔴 TO'GRI refund: mijoz STARS beradi, UZS OLADI. Bekor qilinganda
#    UZS "qaytarilmaydi" (u hech qachon yechilmagan) — STARS qaytariladi.
#    Balansni qo'shish xatosi mijozga ham Stars, ham UZS berardi.
check("refund_star_payment" in ref_h,
      "🔴 Telegram Stars refund API chaqiriladi (mijozning Stars'i qaytariladi)")
check('u["balance"]' not in ref_h,
      "🔴 balansga UZS qo'shilmaydi (mijozda UZS yechilmagan — ikki marta to'lash bo'lardi)")
check('sale["status"] = "refunded"' in ref_h, "savdo -> refunded")

check("💸 To'lanuvchi savdolar" in BSRC, "admin menyusida tugma bor")
check('callback_data="adm:sales"' in BSRC, "adm:sales ga ulangan")
check("adm:sale_ok:" in BSRC.split("SUCCESS_PREFIXES")[1][:120],
      "«To'landi» yashil uslubda")

# =============================================================================
section("3) 🔴 NARX MANBAI BITTAGA (PREMIUM_PLANS ni ikki marta e'lon qilish)")
# =============================================================================
n_def = len(re.findall(r"^PREMIUM_PLANS\s*=", BSRC, flags=re.M))
check(n_def == 1,
      f"PREMIUM_PLANS faqat BIR marta e'lon qilinadi (hozir: {n_def})")
check("PREMIUM_PLANS.items()" in BSRC,
      "webapp_config() dict dan foydalanadi (list bo'lsa CRASH)")
check("def _premium_menu_rows(" in CODE,
      "bot menyusi XUDDI shu dict dan quriladi")
check("premium_menu_rows()\n        lines.append" in CODE
      or "_premium_menu_rows():" in CODE, "menyu yordamchisidan foydalanadi")
# narxlar ketma-ket emas (single source of truth)
rows = CODE[CODE.index("def _premium_menu_rows("):
            CODE.index("async def premium_start(")]
check("PREMIUM_PLANS.get(mode)" in rows,
      "narx `PREMIUM_PLANS` dan olinadi (qayta yozilmagan)")

# =============================================================================
section("4) 💎 PREMIUM — yetkazib berish (eskida butunlay yo'q edi)")
# =============================================================================
check("async def premium_order_worker(" in CODE, "premium worker bor")
check('("Premium worker", premium_order_worker())' in BSRC,
      "worker ishga tushiriladilar ro'yxatida")

# Worker funksiyasi `def ...` dan keyingi `def`/`async def` gacha cho'ziladi.
_wi = CODE.index("async def premium_order_worker(")
_ni = CODE.find("\nasync def ", _wi + 10)
_nd = CODE.find("\ndef ", _wi + 10)
_nxt = [i for i in (_ni, _nd) if i != -1]
pw = CODE[_wi:(min(_nxt) if _nxt else len(CODE))]
check('if order.get("kind") != "premium"' in pw,
      "faqat `kind == \"premium\"` ni oladi (stars/gift/nft ga tegmaydi)")
check('if order.get("status") not in ("processing", "queued", "pending")' in pw,
      "faqat bajarilmagan buyurtmalarni oladi")
check('order["status"] = "premium_wait"' in pw, "-> premium_wait")
check("notify_admins(" in pw, "adminga xabar beriladi")
_guard_i = pw.index('if order.get("premium_notified")')
_notify_i = pw.index("await notify_admins(")
check(_guard_i < _notify_i,
      "🔴 `premium_notified` tekshiruvidan KEYIN xabar (spam bo'lmasin)")
check('order["premium_notified"] = True' in pw, "double-send himoyasi")

check('F.data == "adm:premium"' in BSRC, "admin ro'yxat handler")
check('F.data.startswith("adm:premium_ok:")' in BSRC, "«Berildi» handler")
check('F.data.startswith("adm:premium_refund:")' in BSRC, "qaytarish handler")

p_ok = CODE[CODE.index("async def adm_premium_ok("):
            CODE.index("@admin_router.callback_query(F.data.startswith(\"adm:premium_refund:")]
check('order["status"] = "completed"' in p_ok, "«Berildi» -> completed")
check("notify_admins" not in p_ok and "bot.send_message" in p_ok,
      "mijozga xabar borad i")

p_ref = CODE[CODE.index("async def adm_premium_refund("):]
check('order["status"] = "refunded"' in p_ref, "qaytarish -> refunded")
check('u["balance"] = num(u.get("balance")) + price' in p_ref,
      "🔴 balans mijozga QAYTARILADI")

# =============================================================================
section("5) 🔴 server.ts — premium 'completed' emas, 'processing' bo'lishi SHART")
# =============================================================================
# Eski kod: orderStatus default 'completed' edi va premium uchun ham
# o'zgarmasdi -> mijozga "yetkazildi" yuborilardi.
# 🔴 DIQQAT: server.ts da `kind === 'premium'` IKKALA marta bor:
#    (1) narx hisoblash (1118), (2) buyurtma yaratish (1225).
#    Biz ikkinchisini tekshiramiz — birinchisida orderStatus yo'q.
_p1 = SRV.index("} else if (kind === 'premium') {")
_p2 = SRV.index("} else if (kind === 'premium') {", _p1 + 1)
assert _p1 < _p2
prem_block = SRV[_p2:SRV.index("} else if (kind === 'gift') {", _p2)]
check("orderStatus = 'processing'" in prem_block,
      "🔴 orderStatus = 'processing' (mijozga yolg'on 'yetkazildi' chiqmaydi)")
check("bir necha soat" in prem_block or "soat" in prem_block,
      "mijozga haqiqiy vaqt va'dati ko'rsatiladi")
check("sendTelegramMessage(" in prem_block, "admin xabar beriladi")
check("Premium berib bo" in prem_block or "Berildi" in prem_block,
      "adminga qanday tugma bosish kerakligi aytiladi")

check("months: kind === 'premium'" in SRV, "buyurtmada `months` saqlanadi")
check("mode: kind === 'premium'" in SRV, "buyurtmada `mode` saqlanadi")

# =============================================================================
section("6) 🔴 m:premium stub emas — haqiqiy menyu")
# =============================================================================
check('"premium": lambda: premium_start(msg, state)' in BSRC,
      "m:premium -> premium_start (stub emas)")
check("Premium bo'limi" not in CODE,
      "🔴 stub xabar KODDA qolmadi (izohda bo'lishi normal)")
check("async def premium_start(" in CODE, "premium_start() bor")
ps = CODE[CODE.index("async def premium_start("):
          CODE.index("async def nft_start(")]
check("Web App orqali xarid qilish" in ps, "WebApp havolasi bor")
check('url=WEBAPP_URL' in ps, "URL tugma (callback emas — xabar yubormasligi uchun)")
check("Balansni to'ldirish" in ps, "to'ldirishga o'tish tugmasi")

# 🔴 `m:home` handler — premium ekranidagi "Orqaga" tugmasi
check('"home": lambda: send_main_menu(msg, db_user)' in BSRC,
      "🔴 `m:home` handler qo'shildi (avval o'lik tugma edi)")

print()
print("=" * 70)
print("NATIJA: ✅ BARCHASI TO'G'RI" if ok else "NATIJA: ❌ MUAMMO BOR")
print("=" * 70)
sys.exit(0 if ok else 1)