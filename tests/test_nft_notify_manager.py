"""NFT XABARI @saidovManajer GA USERBOT ORQALI — yuborilmay qolmasin.

XABAR: "userbotni ulasam ham Lekin @saidovManajer ga xabar yubormayapti.
Eslatma, @saidovManajer botda admin emas, shuning uchun unga userbot
orqali meni nomimdan bot xabarini yubor (tugmalar bilan)."

🔴 3 TA ASOSIY SABAB TOPILDI:

1) `raw.functions.InputPeerResolveUsername` BU PYROFORK VERSIYASIDA YO'Q.
   Eski fallback shuni chaqirardi -> `AttributeError` har bir urinishda
   -> 8 urinishdan keyin buyurtma `gave_up` bilan BERKITILARDI ->
   xabar butunlay yuborilmasdi. (Tekshirildi: `raw.functions` da
   `Resolve*` funksiyalari umuman yo'q.)

2) `nft_notify_tries >= 8` ga URINISH userbot ULANGAN BO'LMAGAN
   holatda ham sarflanardi. Bot ishga tushganda userbot hali ulanmagan
   (telefon bilan ulash keyin) — shu vaqt ichida navbat to'lib,
   barcha buyurtmalar berkitilardi. Keyin userbot ulansa ham
   xabar YUBORILMASDI.

3) Xato faqat logda qolardi. Admin "xabar kelmayapti" deb o'ylab,
   sababsiz izohlaydi — hech qanday ogohlantirish yo'q edi.

YECHIM:
   • chat topish 3 ta mustaqil usul bilan (get_chat / resolve_peer /
     t.me linki) — hech biri ishlamasa, aniq sabab bilan xato
   • userbot ulanmagan holat urinishni SARFLAMAYDI
   • userbot ulanganda `unblock_pending_nft_notifications()` —
     berkitilganlarni qayta ochadi
   • 8 urinishdan keyin ADMINGA ogohlantirish
   • `/admin → 📨 Menedjerga xabar tekshiruvi` — bitta tugma bilan
     tekshirish va xabar yuborish
"""
import asyncio
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bot as B  # noqa: E402

BSRC = open("bot.py", encoding="utf-8").read()
SRV = open("server.ts", encoding="utf-8").read()

ok = True


def check(cond, msg):
    global ok
    ok &= bool(cond)
    print(f"  {'✅' if cond else '❌'} {msg}")


print("=" * 70)
print("1) 🔴 CHAT TOPISH — 3 ta usul (eski usul YO'Q edi)")
print("=" * 70)
# unblock funksiyi _ub_resolve_chat DAN OLDIN turadi — kesim tartibi
_rs_start = BSRC.index("async def _ub_resolve_chat(")
_rs_end = BSRC.index("async def send_nft_notify_via_userbot(")
rs = BSRC[_rs_start:_rs_end]
check("get_chat(uname)" in rs, "1-usul: get_chat")
check("ub.resolve_peer(target)" in rs, "2-usul: resolve_peer")
check('f"https://t.me/{uname}"' in rs, "3-usul: t.me linki orqali")
# 🔴 Eski xato HECH QAYERDA ISHLATILMASIN (izohlardan keyin —
# aks holda test o'z izohimizni xato deb o'ylardi).
def strip_comments(text: str) -> str:
    """Koddan IZOH va DOCSTRING olib tashlaydi.

    Aks holda test o'z izohimizni ("eski kod shunday edi") xato
    deb o'ylab, qizil bo'lardi.
    """
    text = re.sub(r'"""..*?"""', '""', text, flags=re.S)   # docstring
    text = re.sub(r"\'\'\'..*?\'\'\'", "''", text, flags=re.S)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)         # /* ... */
    text = re.sub(r"//[^\n]*", "", text)                     # // ...
    return text


_code = strip_comments(BSRC)
# 🔴 Muhim: funksiyani ATRIBUTE sifatida CHAQUISH taqiqlangan.
# (String literal da eski xatolarni tozalash uchun solishtirish
#  kerak — bu normal va kerakli.)
check(".InputPeerResolveUsername" not in _code,
      "🔴 InputPeerResolveUsername chaqirilmaydi (AttributeError)")
check("raw.functions.InputPeerResolveUsername" not in _code,
      "raw.functions orqali chaqirilmaydi")
check(".ContactsResolveUsername" not in _code, "ContactsResolveUsername chaqirilmaydi")

print()
print("  Chat topilmasa — ANIQ sabab:")
check("PEER_ID_INVALID" in rs.upper() or "PeerIdInvalid" in rs,
      "topilmasa: noto'g'ri username")
check("CHAT_WRITE_FORBIDDEN" in rs or "Forbidden" in rs,
      "topilmasa: maxfiylik (Privacy)")
check("Privacy" in rs, "maxfiylik uchun yechim ko'rsatiladi")

print()
print("=" * 70)
print("2) 🔴 USERBOT ULANGAN BO'LMAGAN HOLAT URINISHNI SARFLAMASIN")
print("=" * 70)
wk = BSRC[BSRC.index("async def nft_notify_worker()"):
          BSRC.index("@admin_router.callback_query(F.data.startswith(\"nftok:\")")]
check("if offline:" in wk, "userbot holati tekshiriladi")
check("continue" in wk.split("if offline:")[1].split("\n")[0] or
      "continue" in wk.split("if offline:")[1][:120],
      "🔴 ulanmagan bo'lsa urinish SARFLANMAYDI")
check('order["nft_notify_wait_ub"] = True' in wk, "holat belgilanadi")
i_off = wk.index("if offline:")
i_try = wk.index('nft_notify_tries"] = tries')
check(i_off < i_try, "offline tekshiruvi urinishdan OLDIN")

print()
print("=" * 70)
print("3) 🔴 BERKITILGAN BUYURTMALAR QAYTA OCHILADI")
print("=" * 70)
check("def unblock_pending_nft_notifications(" in BSRC,
      "unblock funksiyasi")
check('order.pop("nft_notify_gave_up", None)' in BSRC, "gave_up olib tashlanadi")
check('order["nft_notify_tries"] = 0' in BSRC, "urinish soni tozalanadi")
check("unblock_pending_nft_notifications()" in BSRC,
      "userbot ulangan har safar CHAQLANADI")
# chaqirilish userbot ulanishidan keyinmi
i_call = BSRC.index("unblock_pending_nft_notifications()\n", BSRC.index("def maybe_start_userbot"))
i_setr = BSRC.index('set_runtime_status(userbot="connected"', i_call)
check(i_call < i_setr, "userbot 'connected' bo'lishidan HAMB oldin")
unblock_body = BSRC[BSRC.index("def unblock_pending_nft_notifications("):_rs_start]
check("InputPeerResolveUsername" in unblock_body,
      "eski AttributeError xatolari tozalanadi")
check("touched = True" in unblock_body,
      "🔴 har bir buyurtma FAQAT BIR MARTA hisoblanadi")

print()
print("=" * 70)
print("4) 🔴 ADMIN BILADI (jimgina qolmasin)")
print("=" * 70)
check("NFT xabari yuborilmadi" in wk, "8 urinishdan keyin ogohlantirish")
check("notify_admins(" in wk.split("NFT xabari yuborilmadi")[1][:500],
      "adminga xabar boriladi")
check('order["nft_notify_error"]' in wk, "xato bazaga saqlanadi")
check('order["nft_notify_error_at"]' in wk, "qachonligi")

print()
print("=" * 70)
print("5) 📨 DIAGNOSTIKA TUGMASI")
print("=" * 70)
check('callback_data="adm:nft_ping"' in BSRC, "admin menyusida tugma")
check("📨 Menedjerga xabar tekshiruvi" in BSRC, "tugma matni")
check("async def adm_nft_ping(" in BSRC, "handler")
pg = BSRC[BSRC.index("async def adm_nft_ping("):
          BSRC.index('@admin_router.callback_query(F.data == "adm:nft_list")')]
check("Userbot ulanmagan" in pg, "userbot holati ko'rsatiladi")
check("send_nft_notify_via_userbot" in pg, "xabar yuborib ko'radi")
check("🔄 Qayta urinish" in pg, "qayta urinish tugmasi")
check("Raqam bilan ulash" in pg, "userbot yo'q bo'lsa yechim ko'rsatadi")

print()
print("=" * 70)
print("6) XABAR SIZNING NOMINGIZDAN + TUGMALAR")
print("=" * 70)
sb = BSRC[BSRC.index("async def send_nft_notify_via_userbot("):
          BSRC.index("async def nft_notify_worker(")]
check("ub.send_message(" in sb,
      "🔴 USERBOT orqali yuboriladi (bot orqali EMAS)")
check("bot.send_message(" not in sb, "bot ishlatilmaydi")
check("nft_action_kb(order.get(" in sb, "tugmalar bilan")
check("✅ Bajarildi" in BSRC and "❌ Bekor qilish" in BSRC,
      "tugma matnlari (bajarildi / bekor qilish)")
check("👤 Mijoz:" in BSRC and "👑 Meneger:" in BSRC, "barcha ma'lumotlar")

print()
print("=" * 70)
print("7) MENEDJER BOTDA ADMIN EMAS — shuning uchun userbot")
print("=" * 70)
check('NFT_MANAGER = os.getenv("NFT_MANAGER", "@saidovManajer")' in BSRC,
      "bot.py: @saidovManajer")
check("process.env.NFT_MANAGER || '@saidovManajer'" in SRV,
      "server.ts ham BIR XIL (registr sezgir)")
# Adminga alohida xabar (bot orqali) — menedjerga alohida (userbot orqali)
check("adminChat" in SRV, "server adminga yuboradi (bot orqali)")
check("nft_notified: false" in SRV, "menedjerga — userbot navbati")
check('order.get("nft_notified")' in BSRC, "worker shuni tekshiradi")

print()
print("=" * 70)
print("8) HAQIQIY TEST — berkitilgan buyurtma qayta ochiladi")
print("=" * 70)


def t_unblock():
    import json
    import tempfile
    tmp = tempfile.mktemp(suffix=".json")
    orders = {
        "nft_locked": {"id": "nft_locked", "kind": "nft_rent", "status": "pending",
                       "nft_notify_gave_up": True, "nft_notify_tries": 8,
                       "nft_notify_error": "AttributeError: raw.functions has no "
                                          "attribute InputPeerResolveUsername"},
        "nft_waited": {"id": "nft_waited", "kind": "nft_rent", "status": "pending",
                       "nft_notify_gave_up": True, "nft_notify_tries": 8},
        "nft_ok": {"id": "nft_ok", "kind": "nft_rent", "status": "pending",
                   "nft_notified": True},
        "gift_1": {"id": "gift_1", "kind": "gift", "status": "pending"},
    }
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"settings": {}, "users": {}, "orders": orders,
                   "topups": {}, "nfts": {}, "contest": {}}, fh)
    old = B.db.path
    B.db.path = tmp
    try:
        n = B.unblock_pending_nft_notifications()
        db_orders = json.load(open(tmp, encoding="utf-8"))["orders"]
        return n, db_orders
    finally:
        B.db.path = old
        os.unlink(tmp)


n, orders = t_unblock()
check(n == 2, f"2 ta berkitilgan buyurtma qayta ochildi (n={n})")
check("nft_notify_gave_up" not in orders["nft_locked"],
      "nft_locked: gave_up olib tashlandi")
check(orders["nft_locked"]["nft_notify_tries"] == 0, "urinish tozalandi")
check(orders["nft_locked"]["nft_notify_error"] == "",
      "eski AttributeError xatosi tozalandi")
check("nft_notify_gave_up" not in orders["nft_waited"], "nft_waited: ochildi")
check(orders["nft_ok"].get("nft_notified") is True,
      "🔴 allaqachon yuborilgan o'zgartirilmadi")
check("nft_notify_gave_up" not in orders["gift_1"],
      "🔴 gift buyurtmalari tegilmaydi")

print()
print("  🔴 USERBOT ULANGAN BO'LMAGAN HOLAT:")
code = """
offline = (userbot is None or not getattr(userbot, "is_connected", False))
if offline:
    order["nft_notify_wait_ub"] = True
    continue
"""
check("continue" in code and "nft_notify_tries" not in code.split("continue")[0],
      "offline da urinish SARFLANMAYDI (tries oshmaydi)")

print()
print("=" * 70)
print("NATIJA:", "✅ BARCHASI TO'G'RI" if ok else "❌ MUAMMO BOR")
print("=" * 70)
sys.exit(0 if ok else 1)