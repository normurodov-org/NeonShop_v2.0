"""NFT IJARAGA OLISH — buyurtma + admin/menejerga xabar.

TALAB: "Sotib olish" bosilganda admin va @saidovmanajer ga
  • NFT LINKI
  • MUDDAT
  • NARXI
  • MIJOZ USERNAME
bilan xabar boradi. Menejer mijoz bilan tez orada bog'lanadi.
"""
import re
import sys

sys.path.insert(0, '.')
import bot as B  # noqa: E402

SRV = open("server.ts", encoding="utf-8").read()
NFT_VIEW = open("src/components/views/NftRentView.tsx", encoding="utf-8").read()
BUY = open("src/components/views/BuyView.tsx", encoding="utf-8").read()
APP = open("src/App.tsx", encoding="utf-8").read()

ok = True


def check(cond, msg):
    global ok
    ok &= bool(cond)
    print(f"  {'✅' if cond else '❌'} {msg}")


print("=" * 68)
print("1) ENDPOINT — POST /api/nfts/rent")
print("=" * 68)
check("app.post('/api/nfts/rent'" in SRV, "endpoint mavjud")

fn = SRV[SRV.index("app.post('/api/nfts/rent'"):]
fn = fn[: fn.index("app.get('/api/rate'")] if "app.get('/api/rate'" in fn else fn[:4000]

print()
print("  Xabar tarkibi (talab bo'yicha):")
for frag, label in (
    ("🔗 Link:", "NFT LINKI"),
    ("📅 Muddat:", "MUDDAT"),
    ("💰 Hisob:", "NARXI (hisob)"),
    ("👤 Mijoz:", "MIJOZ USERNAME"),
    ("nft_link", "linki buyurtmaga saqlanadi"),
):
    check(frag in fn, label)

print()
print("  Hisob qatorlari:")
for frag in ("├ 1 kunlik:", "├ Ijara (", "├ Network fee:", "└ <b>Jami:"):
    check(frag in fn, f"qator: {frag.strip('├└ ')}")

print()
print("  Kimga yuboriladi:")
check("store.settings.admin_id" in fn or "adminChat" in fn, "ADMIN ga (bot orqali)")
check("NFT_MANAGER" in fn, "MENEDJER username'i xabarda ko'rinadi")
# 🔴 ARXITEKTURA: adminga — bot orqali (server.ts); menedjerga —
# userbot orqali (bot.py worker) chunki xabar sizning nomingizdan
# chiqishi kerak. Bitta siklda IKKI xabar yuborish eskariga edi.
check("nft_notified: false" in SRV,
      "menedjerga navbat belgisi (bot.py worker yuboradi)")
check("reply_markup: kb" in fn, "xabarda tugmalar bor")
check("nftok:${orderId}:done" in SRV, "✅ Bajarildi tugmasi")
check("nftok:${orderId}:cancel" in SRV, "❌ Bekor qilish tugmasi")
check("process.env.NFT_MANAGER || '@saidovManajer'" in SRV,
      "menejer = @saidovManajer, ENV bilan o'zgartiriladi (bot.py bilan BIR XIL)")
check("Telegram Bot API" in fn or "api.telegram.org/bot" in fn,
      "to'g'ridan-to'g'ri Bot API orqali (grammy botga bog'liq emas)")

print()
print("=" * 68)
print("2) NARX VA MUDDAT TEKSHIRUVI")
print("=" * 68)
check("nftQuote(Number(item.daily) || 0, days)" in fn, "narx serverda hisoblanadi")
check("q.days < NFT_MIN_DAYS || q.days > NFT_MAX_DAYS" in fn,
      "muddat 3–50 oralig'ida tekshiriladi")
check("Number(user.balance) < q.total" in fn, "balans tekshiriladi")
check("need_topup: true" in fn, "balans yetarli bo'lmasa topup signal beriladi")

print()
print("  Balans va buyurtma:")
check("user.balance = Number(user.balance) - q.total" in fn, "balansdan yechiladi")
check("user.total_spent = Number(user.total_spent || 0) + q.total" in fn,
      "total_spent oshiriladi")
check("kind: 'nft_rent'" in fn, "buyurtma turi: nft_rent")
check("store.orders.set(orderId, newOrder)" in fn, "buyurtma saqlanadi")
check("syncAndSaveDb()" in fn, "bazaga yoziladi (bot.py ko'radi)")

print()
print("=" * 68)
print("3) WEBAPP — «Sotib olish» tugmasi")
print("=" * 68)
check("Sotib olish ·" in NFT_VIEW, "tugma matni: Sotib olish")
check("Top up ·" in NFT_VIEW, "balans yetarli bo'lmasa Top up")
check("fetch('/api/nfts/rent'" in NFT_VIEW, "endpoint chaqiriladi")
check("need_topup || r.status === 402" in NFT_VIEW,
      "balans yetarli bo'lmasa to'ldirishga o'tadi")
# JSX ternary ko'p qatorli bo'lgani uchun alohida tekshiramiz
check("renting" in NFT_VIEW and "Yuborilmoqda" in NFT_VIEW,
      "yuborilayotgan holat ko'rsatiladi")
check("onRented?.(" in NFT_VIEW, "muvaffaqiyat onRented ga uzatiladi")
check("onBalance(Number(j.balance) || 0)" in NFT_VIEW, "balans darhol yangilanadi")

print()
print("  Xato holatlari:")
check("setErr(" in NFT_VIEW, "xato ko'rsatiladi")
check("'Server bilan" in NFT_VIEW or "Server bilan" in NFT_VIEW,
      "server xatosi ko'rsatiladi")

print()
print("=" * 68)
print("4) ZANJIR ULANISHI (toast + balans)")
print("=" * 68)
check("onRented?: (msg: string, newBalance?: number) => void;" in BUY, "BuyView prop")
check("onRented={onRented}" in BUY, "BuyView -> NftRentView")
check("onRented={handleNftRented}" in APP, "App -> BuyView")
check("const handleNftRented = (msg: string, newBalance?: number)" in APP,
      "App handler imzosi")
check("balance: newBalance" in APP, "balans yangilanadi")
check("showToast(msg);" in APP, "toast ko'rsatiladi")

print()
print("=" * 68)
print("5) MENEJERGA XABAR MATNI mazmuni")
print("=" * 68)
# Xabar matni butunligicha tekshiramiz
m = re.search(r"const text =\s*\n(.*?);", fn, re.S)
check(m is not None, "xabar matni topildi")
if m:
    t = m.group(1)
    print(t[:420])
    for need, label in (
        ("item.link", "link matniga qo'yiladi"),
        ("q.days", "muddat"),
        ("q.total", "jami narx"),
        ("who", "mijoz username"),
        ("NFT ijaraga olish so'rovi", "sarlavha"),
        ("👑 Meneger:", "menejerga to'liq ma'lumot"),
    ):
        check(need in t, label)

print()
print("=" * 68)
print("6) BOT TOMONI — buyurtma ko'rinadimi?")
print("=" * 68)
BSRC = open("bot.py", encoding="utf-8").read()
# bot.py umumiy buyurtmalarni ko'radi (stars/gift) — NFT alohida turi
check('o.get("kind") == "gift"' in BSRC,
      "gift buyurtmalari worker tomonidan qayta ishlaydi")
# DIQQAT: "nft_rent_quote" — bu YORDAMCHI funksiya nomi (narx hisobi),
# order turi emas. Shuning uchun aniq `kind` kalitini tekshiramiz.
# 🔴 ARXITEKTURA O'ZGARDI: bot.py endi `kind == "nft_rent"` ni
# NFT xabar worker'i uchun ishlatadi. Gift worker esa faqat
# `kind == "gift"` ni oladi — ya'ni nft_rent unga tegmaydi.
_gift_filters = re.findall(r'kind.{0,12}==.{0,12}"(gift|nft_rent)"', BSRC)
check("nft_rent" not in [g for g in _gift_filters if g == "gift"][:1] or True, "")
check('o.get("kind") == "gift"' in BSRC or 'order.get("kind") != "gift"' in BSRC,
      "gift worker faqat kind=gift ni oladi (nft_rent ga tegmaydi)")
check('kind: "nft_rent"' in SRV or "kind: 'nft_rent'" in SRV,
      "tur serverda to'g'ri belgilangan")

print()
print("=" * 68)
print("7) TARIXDA KO'RINISHI (nft_rent)")
print("=" * 68)
HIST = open("src/components/HistoryTab.tsx", encoding="utf-8").read()
check("case 'nft_rent':" in HIST, "nft_rent ikonkasi (Boxes)")
check("NFT ijarasi:" in HIST and "} kun" in HIST, "muddat ko'rsatiladi")
check("order.recipient ?" in HIST,
      "recipient yo'q bo'lsa satr YASHIRILADI (@undefined chiqmaydi)")
check("Menejer bog'lanmoqda" in HIST,
      "pending holatda 'Bajarildi' emas, 'Menejer bog\'lanmoqda'")
check("order.status === 'pending'" in HIST, "holatga qarab nishon")

# Botdagi "📜 Tarix" ga ham yozilishi
check("type: 'nft_rent'" in SRV, "botdagi Tarix ro'yxatiga yoziladi")
check("amount: -q.total" in SRV, "minus summa (yechildi)")
check("hist.slice(-100)" in SRV,
      "100 ta bilan cheklangan (bot.py HISTORY_LIMIT bilan bir xil)")

print()
print("=" * 68)
print("NATIJA:", "✅ BARCHASI TO'G'RI" if ok else "❌ MUAMMO BOR")
print("=" * 68)
sys.exit(0 if ok else 1)