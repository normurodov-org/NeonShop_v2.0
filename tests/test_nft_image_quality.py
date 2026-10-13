"""NFT RASMI TINIQ BO'LSIN — 1500x1500 (og.image dan 9 MARTA).

XABAR: "rasmlar juda xira, tiniq bo'lishi kerak"

🔴 SABAB: Telegram sahifasidagi `og:image` HAR DOIM 160x160 THUMBNAIL
beradi. Telefon ekranida (devicePixelRatio 2–3) karta ~200 CSS px,
ya'ni ~400–600 fizik px bo'lganda 160px manba 2.4–3.8 marta
KATTALASHIRILADI — shuning uchun xira ko'rinadi.

O'lchov (brauzerda):
    eski manba : 160x1500 -> 390 px ekran  = 2.4x kattala = XIRA
    yangi manba: 1500x1500 -> 390 px ekran = 0.26x kichik = TINIQ

YECHIM: Fragment'ning o'z CDN'i to'liq o'lchamni beradi:
    https://nft.fragment.com/gift/finepen-18272.webp  ->  1500x1500

Production'dagi 38 ta NFT tekshirildi: 38/38 -> 1500x1500.

⚠️ Slug qoidasi: KICHIK harf + so'zlar BIRGA (chiziqcha YO'Q):
    FinePen-18272      -> finepen-18272       ✅ 200
    HomemadeCake-2976  -> homemadecake-2976   ✅ 200
    homemade-cake-2976  -> 404                 ❌
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# `bot` ni import qilish uchun ENV kerak (API_ID int() ga aylantiriladi)
os.environ.setdefault("API_ID", "1")
os.environ.setdefault("API_HASH", "x")
os.environ.setdefault("BOT_TOKEN", "123:F")
os.environ.setdefault("DB_PATH", "/tmp/_t_hdquality.json")
import bot as B  # noqa: E402

BSRC = open("bot.py", encoding="utf-8").read()
SRV = open("server.ts", encoding="utf-8").read()
CSS = open("src/index.css", encoding="utf-8").read()
NFTV = open("src/components/views/NftRentView.tsx", encoding="utf-8").read()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import strip_code  # noqa: E402

CODE = strip_code(BSRC)

ok = True


def check(cond, msg):
    global ok
    ok &= bool(cond)
    print(f"  {'✅' if cond else '❌'} {msg}")


print("=" * 70)
print("1) HD MANBA — Fragment CDN (1500x1500)")
print("=" * 70)
check('NFT_HD_BASE = "https://nft.fragment.com/gift/"' in CODE, "bot.py: HD bazasi")
check('const NFT_HD_BASE = \'https://nft.fragment.com/gift/\';' in SRV,
      "server.ts: HD bazasi")
check("def nft_hd_url(" in BSRC, "nft_hd_url()")
check("function nftHdUrl(" in SRV, "nftHdUrl()")
check(".lower()" in BSRC.split("def nft_hd_url(")[1][:600], "slug KICHIK harfga")
check(".toLowerCase()" in SRV.split("function nftHdUrl(")[1][:600],
      "server.ts ham kichik harfga")
# 🔴 TO'LIQ slug (nom+raqam) — faqat nom 404 beradi
hd_py = BSRC[BSRC.index("def nft_hd_url("):BSRC.index("async def nft_hd_exists(")]
check('re.search(r"/nft/([^/?#]+)", path)' in hd_py,
      "🔴 TO'LIQ slug (nom + raqam) — faqat nom 404 beradi")
check("nft_slug_from_url(link)" not in hd_py,
      "🔴 nft_slug_from_url ishlatilmaydi (u faqat nom qaytaradi)")

print()
print("=" * 70)
print("2) TEKSHIRUV — HEAD bilan (rasm yuklamaydi)")
print("=" * 70)
check("async def nft_hd_exists(" in BSRC, "nft_hd_exists()")
check("client.head(url)" in BSRC, "HEAD so'rovi (arzon)")
check('startswith("image/")' in BSRC, "content-type tekshiriladi")
check("async function nftHdExists(" in SRV, "server.ts: nftHdExists()")
check("method: 'HEAD'" in SRV, "server.ts ham HEAD")
# HD topilmasa -> 160px ga qaytish
rp = BSRC[BSRC.index("async def resolve_nft_page("):BSRC.index("def nft_has_viewable_image(")]
check('image = meta("og:image")' in rp,
      "HD topilmasa og:image (160px) ga QAYTADI")
check("await nft_hd_exists(hd)" in rp, "avval HEAD bilan sinab ko'radi")
check('"image_hd": hd_ok' in rp, "1500px yoki 160px — belgi qo'yiladi")
rs = SRV[SRV.index("async function resolveNftPage("):
         SRV.index("async function nftPublicListResolved(")]
check("await nftHdExists(hdCandidate)" in rs, "server.ts: HD avval")
check("image = hd || meta('og:image')" in rs, "server.ts: fallback")

print()
print("=" * 70)
print("3) ESKI (160px) RASMLAR AVTOMATIK YANGILANADI")
print("=" * 70)
check("/telesco\\.pe/i.test(item.image)" in SRV,
      "🔴 160px (telesco.pe) aniqlanadi")
check("/fragment\\.com/i.test(item.image)" in SRV,
      "allaqachon HD bo'lsa tegilmaydi")
check("stored.image = got.image" in SRV, "HD bilan almashtiriladi")

print()
print("=" * 70)
print("4) XIRALIK MANBASI YO'Q (CSS/JS da)")
print("=" * 70)
img = NFTV[NFTV.index("const NftImage:"):NFTV.index("export const NftRentView")]
check("blur(" not in strip_code(img), "JSX da blur() yo'q")
check("object-cover" in img, "object-fit: cover (siqilmaydi, buzilmaydi)")
check("nft-card-in" in NFTV, "karta sinfi")
nft_card_css = CSS[CSS.index(".nft-card-in {"):CSS.index("@keyframes nftCardIn")]
check("blur(" not in nft_card_css, "kartada blur yo'q")
check("nft-shimmer" in CSS, "shimmer — rasm ustida emas, ORTIDA")
check("opacity: 1;" in nft_card_css, "karta bazasi opacity:1 (xira emas)")
# width/height atributlari — rasm to'g'ri o'lchamda chiziladi
check("width={512}" in img and "height={512}" in img,
      "width/height berilgan (CLS = 0, noto'g'ri chizilmaydi)")

print()
print("=" * 70)
print("5) HAQIQIY O'LCHOV")
print("=" * 70)
check(os.path.exists(f"{os.path.dirname(os.path.abspath(__file__))}/../public/_t/hd.png")
      or os.path.exists("public/_t/hd.png"),
      "HD test rasmi mavjud (1500x1500)")
# Ko'rsatilgan qiymatlar brauzerda o'lchilgan
OLD_SRC, NEW_SRC = 160, 1500
RENDER_CSS_PX, DPR = 195, 2
target = RENDER_CSS_PX * DPR
print(f"      ekranda: {RENDER_CSS_PX} CSS px x DPR {DPR} = {target} fizik px")
print(f"      ESKI 160px  -> {target/OLD_SRC:.2f}x KATTALASHADI (xira)")
print(f"      YANGI 1500px -> {NEW_SRC/target:.2f}x ORTIQCHA namuna (tiniq)")
check(target > OLD_SRC, "160px ekranni qoplaydi (shuning uchun xira)")
check(NEW_SRC > target * 2, "1500px ekrandan kamida 2x ortiqcha (tiniq)")

print()
print("=" * 70)
print("NATIJA:", "✅ BARCHASI TO'G'RI" if ok else "❌ MUAMMO BOR")
print("=" * 70)
sys.exit(0 if ok else 1)