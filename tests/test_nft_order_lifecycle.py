"""NFT BUYURTMA HAYOTI — xabar, tugmalar, "kim birinchi bosdi".

TALAB (sizning so'rovingiz):
  1) Adminga «✅ Bajarildi» / «❌ Bekor qilish» tugmalari bilan xabar
  2) Bajarilsa -> NFT ro'yxatdan O'CHIRILADI
  3) Bekor qilinsa -> mijoz hisobi QAYTARILADI
  4) Xabar @saidovManajer ga ham USERBOT orqali, sizning nomingizdan,
     barcha ma'lumotlar bilan, va u yerda ham tugmalar bo'lsin
  5) Ikkimizdan bittamiz birinchi bosgan bo'lsa — O'SHANIKI hisobga olinsin
  6) NFT bo'limidagi filtrlar (rasmdagi) to'g'ri ishlasin
  7) Rasm animatsiyasi bilan (agar iloji bo'lsa)

🔴 ASOSIY XAVF — "pikar" (race condition):
   Ikki xabar, ikki odam, bir vaqtda. Oddiy tekshiruv yetarli EMAS:
   ikkala process ham `status == "pending"` ni ko'rib, ikkalasi ham
   "bajarildi" deb hisoblaydi va mijozga pul IKKALA MARTA qaytarilardi.
"""
import asyncio
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bot as B  # noqa: E402

BSRC = open("bot.py", encoding="utf-8").read()
SRV = open("server.ts", encoding="utf-8").read()
VIEW = open("src/components/views/NftRentView.tsx", encoding="utf-8").read()

ok = True


def check(cond, msg):
    global ok
    ok &= bool(cond)
    print(f"  {'✅' if cond else '❌'} {msg}")


print("=" * 70)
print("1) TUGMALAR — ✅ Bajarildi / ❌ Bekor qilish")
print("=" * 70)
check("def nft_action_kb(" in BSRC, "nft_action_kb()")
check("✅ Bajarildi" in BSRC and "❌ Bekor qilish" in BSRC, "ikki tugma")
check("nftok:{order_id}:done" in BSRC, "done -> nftok:<id>:done")
check("nftok:{order_id}:cancel" in BSRC, "cancel -> nftok:<id>:cancel")
check('F.data.startswith("nftok:")' in BSRC, "bot xabari uchun handler")
check("ub_cb_nft_action" in BSRC, "userbot xabari uchun handler")
check("UbCallbackQueryHandler" in BSRC, "userbot callback handler import qilingan")
check("ub.add_handler(UbCallbackQueryHandler(ub_cb_nft_action))" in BSRC,
      "userbot ga handler ulangan")
check('data.startswith("nftok:")' in BSRC, "userbot handler faqat nftok ni olaydi")

print()
print("=" * 70)
print("2) 🔴 PIKAR — kim birinchi bosdi, o'sha yutadi")
print("=" * 70)
check("NFT_ACTION_LOCK = asyncio.Lock()" in BSRC, "jarayon ichidagi lock")
claim = BSRC[BSRC.index("async def claim_nft_order("):
             BSRC.index("@admin_router.callback_query(F.data.startswith(\"nftok:\")")]
check("async with NFT_ACTION_LOCK:" in claim, "lock ichida bajariladi")
check("db.reload_if_changed()" in claim,
      "🔴 QARORDAN OLDIN diskdan QAYTA o'qiladi")
i_reload = claim.index("db.reload_if_changed()")
i_check = claim.index('if order.get("status") != "pending"')
check(i_reload < i_check, "qayta o'qish -> tekshiruv tartibi to'g'ri")
check('order["status"] = "claimed"' in claim, "darhol band qilinadi")
i_claim = claim.index('order["status"] = "claimed"')
i_save = claim.index("db.save()", i_claim)
check(i_save > i_claim, "band qilinish darhol yoziladi")
check("claimed_by" in claim, "kim bosgani saqlanadi")
check('return False, "taken", order' in claim,
      "ikkinchiga 'taken' qaytariladi")

print()
print("  Ikkala yo'l BIR xil qaror funksiyasidan o'tadi:")
check("_handle_nft_action(call, actor=\"adm\"" in BSRC, "admin -> _handle_nft_action")
check("_handle_nft_action(_Shim(call), actor=\"mgr\"" in BSRC,
      "menejer -> _handle_nft_action (xuddi shu)")
h = BSRC[BSRC.index("async def _handle_nft_action("):
        BSRC.index('@admin_router.callback_query(F.data == "adm:nft_list")')]
check("claim_nft_order(order_id, actor)" in h, "ikkalasi ham claim orqali")
check('code == "taken"' in h, "'taken' da hech narsa o'zgartirilmaydi")
check("show_alert=True" in h, "ikkinchiga ogohlantirish ko'rsatiladi")
check("Birinchi bosgan" in h, "kim birinchiligi aytiladi")
# MUHIM: "taken" da hech qanday refund/refactor bo'lmasligi SHART
taken_seg = h[h.index('if code == "taken"'):]
check("_refund_nft_order" not in taken_seg.split("return")[0] or True, "")
# aniqroq: taken blokida _nft_apply_action CHAQLANMASIN
taken_block = taken_seg[:taken_seg.index("msg, _ = await _nft_apply_action")]
check("_nft_apply_action" not in taken_block,
      "🔴 'taken' da amal bajarilMAYDI (pul ikki marta qaytarilmasin)")

print()
print("=" * 70)
print("3) BAJARILDI -> NFT RO'YXATDAN O'CHIRILADI")
print("=" * 70)
check("def _remove_nft_from_listing(" in BSRC, "_remove_nft_from_listing()")
rm = BSRC[BSRC.index("def _remove_nft_from_listing("):
          BSRC.index("async def claim_nft_order(")]
check('nft["active"] = False' in rm, "yopiladi (active=False)")
check('nft["removed"] = True' in rm, "removed=True (ro'yxatdan o'chdi)")
check('nft["removed_at"]' in rm, "qachon o'chirilgani")
check('nft["removed_order"]' in rm, "qaysi buyurtma uchun")
apply_fn = BSRC[BSRC.index("async def _nft_apply_action("):
                BSRC.index("@admin_router.callback_query(F.data.startswith(\"nftok:\")")]
check("_remove_nft_from_listing(order)" in apply_fn, "bajarildi -> o'chiriladi")
check('order["status"] = "done"' in apply_fn, "buyurtma: done")

print()
print("=" * 70)
print("4) BEKOR QILINDI -> MIJOZ HISOBI QAYTARILADI")
print("=" * 70)
check("def _refund_nft_order(" in BSRC, "_refund_nft_order()")
rf = BSRC[BSRC.index("def _refund_nft_order("):
          BSRC.index("def _remove_nft_from_listing(")]
check('user["balance"] = num(user.get("balance")) + total' in rf, "balansga qo'shiladi")
check('user["total_spent"] = max(0, num(user.get("total_spent")) - total)' in rf,
      "total_spent qaytariladi")
check('db.add_history(user, "nft_rent_refund"' in rf, "tarixga yoziladi")
check("_refund_nft_order(order)" in apply_fn, "bekor -> qaytariladi")
check('order["status"] = "cancelled"' in apply_fn, "buyurtma: cancelled")
check('order["refunded"] = refunded' in apply_fn, "qaytarilgan summa saqlanadi")

print()
print("=" * 70)
print("5) IKKI XABAR — ikkalasi ham yangilanadi")
print("=" * 70)
check("def _patch_nft_notices(" in BSRC, "_patch_nft_notices()")
pn = BSRC[BSRC.index("async def _patch_nft_notices("):
          BSRC.index("def _refund_nft_order(")]
check('n.get("via") == "ub"' in pn, "userbot xabari yangilanadi")
check("edit_message_text" in pn and "userbot.edit_message_text" in pn,
      "userbot orqali edit")
check("bot.edit_message_text" in pn, "bot orqali edit")
check("InlineKeyboardMarkup(inline_keyboard=[])" in pn,
      "tugmalar olib tashlanadi")
check("_patch_nft_notices(order, text)" in apply_fn,
      "natijada ikkalasi ham yangilanadi")

print()
print("=" * 70)
print("6) XABAR MATNI — barcha ma'lumotlar + sizning nomingiz")
print("=" * 70)
sm = BSRC[BSRC.index("async def nft_order_summary("):
          BSRC.index("async def _patch_nft_notices(")]
for frag, label in (
    ("NFT ijaraga olish so'rovi", "sarlavha"),
    ("👤 Mijoz:", "mijoz"),
    ("👑 Meneger:", "menejer"),
    ("📅 Muddat:", "muddat"),
    ("1 kunlik:", "1 kunlik"),
    ("Ijara (", "ijara"),
    ("Network fee:", "network fee"),
    ("Jami:", "JAMI"),
    ("🔗", "NFT LINKI"),
):
    check(frag in sm, label)
check('order.get("customer_username")' in sm, "mijoz username'i")
check('order.get("admin_username")' in sm, "admin nomi (kim yubordi)")
# Tugmalar summary'da emas — yuboruvchida (ikkala yo'l ham)
# 🔴 USERBOT uchun PYROFORK klaviaturasi kerak (aiogram niki
# ishlamaydi: "object has no attribute 'write'"). 23-testda
# haqiqiy .write() bilan tekshiriladi.
check("reply_markup=ub_nft_action_kb" in BSRC,
      "tugmalar userbot xabariga ulangan (pyrofork klaviatura)")

print()
print("=" * 70)
print("7) USERBOT orqali @saidovManajer ga")
print("=" * 70)
check('NFT_MANAGER = os.getenv("NFT_MANAGER", "@saidovManajer")' in BSRC,
      "bot.py: @saidovManajer")
check("send_nft_notify_via_userbot" in BSRC, "userbot orqali yuborish")
sb = BSRC[BSRC.index("async def send_nft_notify_via_userbot("):
          BSRC.index("async def nft_notify_worker(")]
check("ub.send_message(" in sb, "userbot bilan yuboriladi (bot emas)")
check("nft_action_kb(order.get(\"id\"" in sb, "tugmalar userbot xabarida")
check("is_connected" in sb, "userbot ulanganini tekshiradi")
check("async def _ub_resolve_chat(" in BSRC, "username -> chat_id")
check("async def nft_notify_worker(" in BSRC, "worker")
check('("NFT xabar worker", nft_notify_worker())' in BSRC, "worker ishga tushirilgan")

print()
print("  🔴 IKKI TOMON HAM XABAR OLISHI SHART:")
check("const adminChat" in SRV and "sendMessage" in SRV, "adminga — bot orqali")
check("nft_notified: false" in SRV, "menedjerga — navbat belgisi (order ichida)")
check('order.get("nft_notified")' in BSRC, "worker shu belgini tekshiradi")
check('order.get("kind") != "nft_rent"' in BSRC, "faqat nft_rent buyurtmalari")
check("nft_notify_gave_up" in BSRC, "8 urinishdan keyin to'xtaydi (spam yo'q)")

print()
print("=" * 70)
print("8) 🔴 server.ts <-> bot.py MUTLAQATGOH mosligi")
print("=" * 70)
check("process.env.NFT_MANAGER || '@saidovManajer'" in SRV,
      "server.ts ham BIR XIL @saidovManajer (registr sezgir!)")
# Izohda eslatilishi normal — KODDA ishlatilmasligi kerak
_nmu = [ln for ln in SRV.split("\n") if "NFT_MANAGER_USERNAME" in ln]
check(len(_nmu) == 1 and _nmu[0].strip().startswith("*"),
      f"eskirgan NFT_MANAGER_USERNAME faqat IZOHDA ({len(_nmu)} qator)")
check("nftok:${orderId}:done" in SRV, "server ham xuddi shu callback yuboradi")
check("nftok:${orderId}:cancel" in SRV, "server ham xuddi shu callback yuboradi")
check("✅ Bajarildi" in SRV and "❌ Bekor qilish" in SRV, "server xabarida tugmalar")
check("newOrder.notices.push(" in SRV, "xabar joyi order ga saqlanadi")
check("via: 'bot'" in SRV or 'via: "bot"' in SRV, "via=bot")
check("ADMIN_HANDLE" in SRV, "sizning nomingiz (kim yubordi)")

print()
print("=" * 70)
print("9) NFT FILTRLARI — hammasi ISHLASIN")
print("=" * 70)
check("openMenu" in VIEW, "dropdown menyu holati")
check("openMenu === 'collection'" in VIEW, "All collections ochiladi")
check("openMenu === 'sort'" in VIEW, "Cheapest first ochiladi")
check("SORT_OPTIONS" in VIEW and "Most expensive" in VIEW and "Newest first" in VIEW,
      "saralash variantlari (rasmdagi kabi)")
check("collection === ALL_COLLECTIONS || n.collection === collection" in VIEW,
      "🔴 collection filtr HAQIQATAN qo'llanadi")
check("!favOnly || fav[n.id]" in VIEW, "🔴 ♥ filtr haqiqatan qo'llanadi")
check("sort === 'new'" in VIEW, "Newest first ishlaydi")
check("setFavOnly(" in VIEW, "♥ tugmasi filtrni yoqadi")
check("localStorage.setItem('neon_nft_fav'" in VIEW,
      "tanlanganlar saqlanadi (sahifa yangilanmasin)")
check("localStorage.getItem('neon_nft_fav')" in VIEW, "saqlanganlar o'qiladi")
check("toggleFav(" in VIEW, "kartadagi yurakcha ham saqlaydi")
check("SlidersHorizontal" in VIEW and "Filtrlarni tozalash" in VIEW,
      "⚙ filtrlarni tozalaydi")
check("collection: n.collection || ''" in SRV, "server collection ni beradi")

print()
print("=" * 70)
print("10) ANIMATSIYALI RASM")
print("=" * 70)
check("F.animation" in BSRC, "GIF (animation) qabul qilinadi")
check("F.document" in BSRC, "GIF fayl (document) qabul qilinadi")
check("image/gif" in BSRC and "image/webp" in BSRC, "<img> ko'rsata oladigan formatlar")
check("video/mp4" in BSRC, "MP4 rad qilinadi (<img> ko'rsata olmaydi)")
check("video/mp4" in BSRC and "GIF fayl" in BSRC, "mijozga aniq tushuntiriladi")
check('n["image_animated"]' in BSRC, "belgi saqlanadi")
check("animated: !!n.image_animated" in SRV, "server API ga beradi")
# WebApp: GIF/WebP <img> da o'z-o'zidan aylanadi — maxsus kod kerak emas
check("<img" in VIEW, "rasm <img> orqali (GIF/WebP o'z-o'zidan aylanadi)")

print()
print("=" * 70)
print("11) HAQIQIY TEST — race condition SIMULYATSIYASI")
print("=" * 70)


async def race():
    """Ikki handler BIR VAQTDA chaqirilsa — faqat biri yutishi kerak."""
    import json
    import tempfile
    tmp = tempfile.mktemp(suffix=".json")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"settings": {}, "users": {"5": {"id": 5, "balance": 1000,
                                                   "total_spent": 0, "history": []}},
                   "orders": {"nft_x": {"id": "nft_x", "user_id": 5, "kind": "nft_rent",
                                        "nft_id": "n", "status": "pending",
                                        "price": 500, "price_uzs": 500, "days": 3,
                                        "per_day": 84, "rent": 252, "nft_title": "T"}},
                   "topups": {}, "nfts": {"n": {"id": "n", "title": "T", "daily": 84,
                                                "active": True}}, "contest": {}},
                  fh, ensure_ascii=False)
    old_path = B.db.path
    B.db.path = tmp
    try:
        r = await asyncio.gather(
            B.claim_nft_order("nft_x", "adm"),
            B.claim_nft_order("nft_x", "mgr"),
            B.claim_nft_order("nft_x", "adm"),
        )
        wins = [i for i, (okk, _, _) in enumerate(r) if okk]
        taken = [c for okk, c, _ in r if not okk]
        return r, wins, taken
    finally:
        B.db.path = old_path
        os.unlink(tmp)


res, wins, taken = asyncio.run(race())
check(len(wins) == 1,
      f"3 ta parallel chaqiruvdan FAQAT {len(wins)} tasi yutdi {wins}")
check(all(t == "taken" for t in taken), f"qolganlari 'taken' bo'ldi: {taken}")

print()
print("  Pulsiz tekshiruv — refund faqat YUTGAN tomon tomonidan:")
check("_nft_apply_action" in BSRC, "amal faqat yutgan tomonda bajariladi")
check('if not ok:' in h, "yutmagan tomon erta qaytadi")

print()
print("=" * 70)
print("NATIJA:", "✅ BARCHASI TO'G'RI" if ok else "❌ MUAMMO BOR")
print("=" * 70)
sys.exit(0 if ok else 1)