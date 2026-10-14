"""NFT KARTALARI — "rasm uchib qolyapti" (flicker/jitter) muammosi.

XABAR: "webappda nft giftning rasmi ozroq turib uchib qolyapti"

Brauzerda o'lchilgan ASL HOLAT:
  Har bir kartada `apple-view-animate` bor edi:
      animation: appleViewEnter 0.5s both
        0%   { transform: translateY(16px) scale(0.975); filter: blur(8px); }
        100% { transform: translateY(0) scale(1);         filter: blur(0px); }

  Bu 3 ta muammo keltiradi:
  1) `filter: blur()` rasmni HAR KADRDA qayta chizadi — telefon
     ekranida bu aynan "rasm uchib qolyapti" degan taassurot.
  2) `transform` kartani 16px pastga va 2.5% kichiklashtiradi va
     keyin joyiga qaytaradi. O'lchan ko'rinishi:
        holat A: (300, 653, 192x278)
        holat B: (192, 600, 202x293)   <- 108px chapga, 53px tepaga sakrab
  3) `fill-mode: both` oxirgi kadrani DOIM saqlaydi, ya'ni
     `transform` va `filter` hech qachon `none` bo'lmaydi. Bu
     `position: fixed` ni ham buzadi (modal muammosi).

  4) Mobil'da `:hover` yopishib qoladi: barmoq tegsa, `scale-105`
     keyingi tapgacha ushlab turadi -> rasm kattalashib qoladi,
     keyin kichiklashib sakrab ketadi.

YECHIM:
  • kartalar uchun alohida `nft-card-in` animatsiyasi — `filter`
    umuman ishlatilmaydi, `transform` faqat kichik `translateY`
  • `--i` orqali stagger (ketma-ket paydo bo'lish)
  • `@media (hover: none)` — telefonda kattalashuv yo'q
  • `<img width height>` — rasm yuklanganda karta siljimaydi (CLS=0)
  • Butun bo'lim allaqachon bir marta animatsiya oladi
    (BuyView wrapperida `apple-view-animate`) — takrorlash kerak emas
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import strip_code, section  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Izoh va docstring larni tozalaymiz — aks holda test o'z
# izohimizni ("avval shunday edi") xato deb o'ylab qizil bo'lardi.
CSS = strip_code(open(f"{ROOT}/src/index.css", encoding="utf-8").read())
VIEW = strip_code(open(f"{ROOT}/src/components/views/NftRentView.tsx",
                       encoding="utf-8").read())

ok = True


def check(cond, msg):
    global ok
    ok &= bool(cond)
    print(f"  {'✅' if cond else '❌'} {msg}")


print("=" * 70)
print("1) KARTADA apple-view-animate YO'Q (flicker manbai)")
print("=" * 70)
# 📖 GRID SINFI O'ZGARDI (responsive): endi
#    `grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-4`.
#    Aniq matnni qidirish testni har layout o'zgarishida sindiradi —
#    endi `grid` boshlanishini olamiz.
_grid_marker = '<div className="grid grid-cols-2'
card = VIEW[VIEW.index(_grid_marker):VIEW.index("<NftImage")]
check("2xl:grid-cols-5" in card,
      "📖 karta grid'i responsive (telefon 2 / planshet 4 / katta 5 ustun)")
check("nft-card-in" in card, "karta `nft-card-in` sinfini ishlatadi")
check("apple-view-animate" not in card,
      "kartada `apple-view-animate` YO'Q (blur(8px) manbai olib tashlandi)")
check("apple-spring" in card, "`apple-spring` qoladi (bosish hissi saqlanadi)")
check("['--i' as string]" in card, "--i (stagger indeksi) beriladi")

print()
print("  Butun bo'lim animatsiyasi saqlanmoqda (bir marta):")
check("apple-view-animate" in open(f"{ROOT}/src/components/views/BuyView.tsx",
                                   encoding="utf-8").read(),
      "BuyView wrapperida ilk animatsiya bor")

print()
print("=" * 70)
print("2) ANIMATSIYA — blur yo'q, sekin, stagger")
print("=" * 70)
css_rule = section(CSS, ".nft-card-in {", "@keyframes nftCardIn")
css_kf = section(CSS, "@keyframes nftCardIn {", "@media (hover: none)")
check("@keyframes nftCardIn" in CSS, "nftCardIn animatsiyasi")
check("translateY(8px)" in css_kf, "kichik shift (8px — avval 16px+scale 0.975)")
check("scale(" not in css_kf, "scale ISHLATILMAYDI (karta sakramasin)")
check("blur(" not in css_kf, "filter: blur ISHLATILMAYDI (rasm qayta chizilmasin)")
check("animation-delay: calc(var(--i, 0) * 0.035s)" in CSS,
      "stagger — kartalar ketma-ket (0.035s)")
# 🔴 XAVFSIZLIK: `forwards` + `opacity: 0` = animatsiya ishlamasa
# karta KO'rinMAY qoladi. Endi baza holat `opacity: 1`.
check("backwards" in css_rule,
      "🔴 fill-mode: backwards — animatsiya ishlamasa karta ko'rinadi")
check("forwards" not in css_rule, "`forwards` yo'q (xavfli)")
check("opacity: 1;" in css_rule, "bazaviy holat opacity: 1 (fail-safe)")
# va `loading="lazy"` ham olindi (rasm umuman yuklanmasdi)
check('loading="lazy"' not in VIEW,
      '🔴 loading="lazy" yoq — bu layoutda rasmni yuklamaydi')

print()
print("  🔴 Muhim: oxirgi holimada `filter: none` BO'LISHI kerak.")
print("  `apple-view-animate` da `blur(0px)` DOIM qolardi va")
print("  `position: fixed` ni buzardi.")
check("@keyframes nftCardIn" in CSS and "blur" not in css_kf,
      "kartada filter umuman yo'q -> fixed buzilmaydi")

print()
print("=" * 70)
print("3) MOBIL — yopiq hover (jitter)")
print("=" * 70)
check("@media (hover: none)" in CSS, "`hover: none` (telefon) uchun qoida")
check("transform: none !important;" in CSS, "telefonda kattalashuv o'chiriladi")
check("group-hover:scale-105" in VIEW,
      "sichqonchada kattalashuv saqlanadi (hover: hover)")

print()
print("=" * 70)
print("4) RASM — layout shift (CLS) = 0")
print("=" * 70)
img = VIEW[VIEW.index("const NftImage:"):VIEW.index("export const NftRentView")]
check("width={512}" in img and "height={512}" in img,
      "<img width/height> — rasm yuklanganda karta SILJIMAYDI")
check('className={`nft-img w-full h-full object-cover' in img, "nft-img sinfi")
check("decoding=\"async\"" in img, "async decode (main thread bloklanmaydi)")
check(".nft-img {" in CSS, "nft-img CSS qoidasi (object-fit: cover)")
check("aspect-square" in VIEW, "konteyner nisbiy balandlikda (aspect-square)")
check("loading=\"eager\"" in img,
      "🔴 eager yuklash (lazy bu layoutda ishlaydi deb o\'ylangan, lekin YO\'Q)")

print()
print("=" * 70)
print("5) PLACEHOLDER ham xuddi shu o'lchamda")
print("=" * 70)
check("nft-img w-full h-full flex flex-col" in img,
      "placeholder ham `nft-img` (rasm bilan bir xil o'lcham)")
check("Gift" in img, "Gift ikonkasi")

print()
print("=" * 70)
print("6) ESKI MUAMMO QOLMAGANMI?")
print("=" * 70)
check("group-hover:scale-105" in VIEW or "hover:scale" in VIEW,
      "hover effekti mavjud (FAQAT sichqonchada)")
# .nft-card-in da apple-view-animate qolmaganini birga qayta tekshiramiz
all_cards = re.findall(r'nft-card-in[^`]*', VIEW)
check(all("apple-view-animate" not in c for c in all_cards),
      "karta sinflarida apple-view-animate yo'q")

print()
print("=" * 70)
print("TAQQOSLASH")
print("=" * 70)
print("  ESKI:  blur(8px) -> blur(0px)  (har kadrda rasm qayta chiziladi)")
print("         translateY(16px) scale(0.975) -> joyiga qaytadi")
print("         o'lchan: (300,653,192x278) -> (192,600,202x293)  SAKRAB")
print("         mobil'da :hover yopishib qoladi -> yana sakrab")
print("  YANGI: filter butunlay yo'q, translateY 8px, stagger, CLS=0")
print("         mobil'da kattalashuv o'chirilgan")

print()
print("=" * 70)
print("NATIJA:", "✅ BARCHASI TO'G'RI" if ok else "❌ MUAMMO BOR")
print("=" * 70)
sys.exit(0 if ok else 1)