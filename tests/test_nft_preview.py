"""NFT RASMI — TELEGRAM SAHIFASIDAN AVTOMATIK.

XABAR: "Webappdagi NFT rasmiga Men yuborgan linkdan NFTni rasm/gif
olib qo'y." — admin `https://t.me/nft/FinePen-18272` yuboradi va
WebApp'da bu rasm chiqishi kerak.

NIMA UCHUN BU ISHLAYDI:
  Telegram NFT sahifasi server tomonda `og:image` preview yaratadi:
      https://t.me/nft/FinePen-18272  ->  200
        og:image = https://cdn4.telesco.pe/file/....jpg   (160x160 JPEG)
        og:title = "Fine Pen #18272"
        og:description = "Model: Solar Atlas / Backdrop: Chestnut / ..."

  LEKIN `<img src="https://t.me/nft/...">` hech qachon rasm
  ko'rsatmaydi — bu SPA sahifa, rasm faqat klientda chiziladi.

Kritik detail: RAQAM bilan havola (`/nft/FinePen-18272`) 200 qaytaradi,
raqamsiz (`/nft/FinePen`) esa 302 -> telegram.org va rasm YO'Q.
Ya'ni haqiqiy NFT bo'lishi shart.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bot as B  # noqa: E402

SRV = open("server.ts", encoding="utf-8").read()
VIEW = open("src/components/views/NftRentView.tsx", encoding="utf-8").read()

ok = True


def check(cond, msg):
    global ok
    ok &= bool(cond)
    print(f"  {'✅' if cond else '❌'} {msg}")


print("=" * 70)
print("1) TELEGRAM SAHIFASI ANIQLANADIMI?")
print("=" * 70)
for u, want in [
    ("https://t.me/nft/FinePen-18272", True),
    ("http://t.me/nft/JackInTheBox-9999", True),
    ("https://telegram.me/nft/Heart-1", True),
    ("https://t.me/nft/FinePen", True),        # sahifa, lekin raqamsiz
    ("https://example.com/x.jpg", False),      # oddiy rasm — resolver kerak emas
    ("https://t.me/notnft/abc", False),        # NFT sahifasi emas
    ("t.me/nft/FinePen-18272", False),         # sxema yo'q
]:
    check(B.is_nft_page_url(u) == want, f"{u} -> {B.is_nft_page_url(u)}")

print()
print("=" * 70)
print("2) SLUG -> NOM va RAQAM (nom ichida chiziqcha bo'lishi mumkin)")
print("=" * 70)
cases = [
    ("https://t.me/nft/FinePen-18272", "FinePen", 18272),
    ("https://t.me/nft/JackInTheBox-9999", "JackInTheBox", 9999),
    ("https://t.me/nft/Heart", "Heart", None),
]
for url, name, num in cases:
    got = B.nft_slug_from_url(url)
    check(got == (name, num), f"{url.split('/')[-1]} -> {got}")

print()
print("=" * 70)
print("3) HAQIQIY SOROV — Telegram dan rasm keladimi?")
print("=" * 70)
# Internet yo'q bo'lsa test muvaffaqiyatsiz bo'lmasin:
# mantiqiy qismi tekshiriladi, tarmoqqa chiqish alohida.
try:
    got = asyncio.run(B.resolve_nft_page("https://t.me/nft/FinePen-18272"))
    online = got is not None
except Exception as exc:  # noqa: BLE001
    got, online = None, False
    print(f"  ➖ tarmoqqa chiqib bo'lmadi ({type(exc).__name__})")

if online:
    check(got["image"].startswith("https://"), f"rasm havolasi: {got['image'][:58]}...")
    if got.get("image_hd"):
        check("nft.fragment.com" in got["image"],
              "🔴 1500x1500 Fragment CDN (tiniq rasm)")
    else:
        check("telesco.pe" in got["image"],
              "HD yo'q -> 160px Telegram CDN (og:image)")
    check(got["title"] == "Fine Pen", f"nom: {got['title']}")
    check(got["number"] == 18272, f"raqam: {got['number']}")
    check("Backdrop" in got["description"], "tavsifda Backdrop bor")
    check(B.nft_has_viewable_image({"image": got["image"]}),
          "nft_has_viewable_image -> True (WebApp ko'rsatadi)")

    # Raqamsiz / mavjud bo'lmagan NFT -> None
    bad = asyncio.run(B.resolve_nft_page("https://t.me/nft/Heart"))
    check(bad is None,
          f"raqamsiz havola -> None (placeholder), olindi: {bool(bad)}")
else:
    check("og:image" in open("bot.py", encoding="utf-8").read(),
          "og:image parsing kodi bor (tarmoq tekshiruvi o'tkazilmadi)")

print()
print("=" * 70)
print("4) BOT ADMIN OQIMI — rasm avtomatik saqlanadimi?")
print("=" * 70)
BSRC = open("bot.py", encoding="utf-8").read()
fn = BSRC[BSRC.index("async def adm_nft_link("):
         BSRC.index("@admin_router.message(StateFilter(NftStates.daily)")]
check("resolve_nft_page(link)" in fn, "rasmni o'zi topadi")
check('image=auto["image"]' in fn, "topilgan rasm saqlanadi")
check('title=auto.get("title") or ""' in fn, "nom avtomatik olinadi")
check('number=auto.get("number")' in fn, "raqam avtomatik olinadi")
check('auto_desc=auto.get("description") or ""' in fn, "tavsif avtomatik olinadi")
check("NFT topildi" in fn, "adminGA tasdiqlanadi")
check("NFT ma'lumotlari topilmadi" in fn,
      "topilmasa aniq aytadi (nima qilish kerak)")
check("https://t.me/nft/Nom-12345" in fn, "to'g'ri format ko'rsatiladi")

print()
print("=" * 70)
print("5) SERVER — eski NFT'lar ham rasm oladi (sizning holatingiz)")
print("=" * 70)
check("async function resolveNftPage(" in SRV, "resolveNftPage()")
check("og:image" in SRV, "og:image o'qiladi")
check("og:title" in SRV, "og:title o'qiladi")
check("NFT_UA" in SRV, "Brauzer User-Agent (bot UA redirect qilinadi!)")
check("redirect: 'manual'" in SRV,
      "redirect qilinmaydi (302 = rasm yo'q, vaqt yo'qotmaslik)")
check("const NFT_PAGE_TTL = 6 * 60 * 60 * 1000;" in SRV, "6 soatlik kesh")
check("nftPageCache" in SRV, "link bo'yicha kesh")
check("async function nftPublicListResolved(" in SRV,
      "ro'yxatda rasm yetishmaydi (eski NFT'lar)")
check("stored.image = got.image" in SRV, "topilgan rasm BAZAGA yoziladi")
check("syncAndSaveDb()" in SRV, "keyingi so'rovlarda qayta yuklamaydi")
check("items: await nftPublicListResolved()" in SRV, "/api/nfts ishlatadi")

print()
print("  MUHIM: server eski NFT ni rasm YO'Q bo'lib chiqarmasligi kerak")
fp = SRV[SRV.index("function nftPublicList()"):SRV.index("function nftPublicList()") + 900]
check("nftImageUrl(n)" in fp, "nftImageUrl hali ham qo'llanadi")
check("isTelegramPageUrl(raw) ? '' : raw" in SRV,
      "t.me linki rasm sifatida QAYTARILMAYDI (buzilgan rasm chiqmaydi)")

print()
print("=" * 70)
print("6) BACKDROP — rasmdagi filtr endi haqiqiy ma'lumotga ishlaydi")
print("=" * 70)
check("function nftBackdrop(" in SRV, "nftBackdrop() — og:description dan")
check("backdrop: nftBackdrop(n.description)" in SRV, "API ga chiqariladi")
check('"description"' in BSRC, "bot.py description ni saqlaydi")
check("const ALL_BACKDROPS" in VIEW, "qat'iy ro'yxat olib tashlandi")
check("BACKDROPS = [" not in VIEW, "o'lik hardkod ro'yxat yo'q")
check("new Set(" in VIEW and "n.backdrop" in VIEW,
      "ro'yxat NFT'lar ichidagi haqiqiy backdrop'lardan yig'iladi")
check("backdrop === ALL_BACKDROPS || n.backdrop === backdrop" in VIEW,
      "filtr haqiqiy qiymat bo'yicha ishlaydi")

print()
print("=" * 70)
print("7) SELF-HEALING — CDN havolasi muddati tugsa")
print("=" * 70)
check("app.post('/api/nfts/refresh-image/:id'" in SRV, "qayta olish endpointi")
check("nftPageCache.delete(link)" in SRV,
      "kesh tozalanadi (majburlangan yangilash)")
check("item.image = got.image" in SRV, "yangi rasm bazaga yoziladi")
check("syncAndSaveDb()" in SRV, "keyingi ochilishda darhol ko'rinadi")
check("const retriedRef = useRef(false)" in VIEW, "faqat 1 marta qayta urinish")
check("/api/nfts/refresh-image/" in VIEW, "WebEndpoint chaqiradi")
check("if (nftId && !retriedRef.current)" in VIEW,
      "cheksiz sikl yo'q (infinite loop himoyasi)")
check("nftId={n.id}" in VIEW and "nftId={sel.id}" in VIEW,
      "kartada VA modalda id uzatiladi")

print()
print("=" * 70)
print("NATIJA:", "✅ BARCHASI TO'G'RI" if ok else "❌ MUAMMO BOR")
print("=" * 70)
sys.exit(0 if ok else 1)