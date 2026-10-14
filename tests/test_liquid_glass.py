"""🍎 APPLE LIQUID GLASS + SCROLL regressiya testi.

XABARLAR:
  1. «Xarid tugmasini bosganda pasga tushib ketadi, to'ldirishni bosganda
      qaytadi, profilni bosganda yuqolib qoladi» — menyu scroll qilinadi.
  2. «Uzun sahifalarda scroll qilib bo'lmayapti».
  3. «NFT bo'limiga kirsam scroll qilib bo'lmayapti».
  4. «Desktopda qizil bilan belgilangan bo'limni yanada kengaytir».

🔴 BARCHASI BITTA ASOSIY SABABGA BOG'LIQ EDI:

  A) `.dark .liquid-glass { position: relative }` specificity (0,2,0)
     → Tailwind `.fixed` (0,1,0) bekor bo'lardi
     → menyu `relative` bo'lib, sahifa bilan birga scroll qilardi.

  B) `overflow-x: hidden` boshqa o'qning qiymatini `auto`ga AYLANTIRADI
     (CSS spec) → html/body/root nested scroll container bo'lardi
     → uzun sahifalarda scroll zanjiri buzilardi.

  C) `overscroll-behavior-y: none` ichki konteyner chegarada zanjirni
     butunlay uzadi.

Apple Liquid Glass tamoyillari
(developer.apple.com/documentation/technologyoverviews/adopting-liquid-glass):
  • «Reduce your use of custom backgrounds in controls and navigation»
  • «Avoid overusing Liquid Glass effects ... Limit these effects to the
     most important functional elements»
  • «people can ... turn on accessibility settings that reduce transparency»
  • «Scroll views offer a scroll edge effect that helps maintain sufficient
     legibility ... for controls»
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import strip_code  # noqa: E402

CSS = open(os.path.join(ROOT, "src/index.css"), encoding="utf-8").read()
HTML = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
NAV = open(os.path.join(ROOT, "src/components/BottomNav.tsx"), encoding="utf-8").read()
APP = open(os.path.join(ROOT, "src/App.tsx"), encoding="utf-8").read()
HDR = open(os.path.join(ROOT, "src/components/Header.tsx"), encoding="utf-8").read()
NFT = open(os.path.join(ROOT, "src/components/views/NftRentView.tsx"), encoding="utf-8").read()
BUY = open(os.path.join(ROOT, "src/components/views/BuyView.tsx"), encoding="utf-8").read()
PROF = open(os.path.join(ROOT, "src/components/views/ProfileView.tsx"), encoding="utf-8").read()
AUTH = open(os.path.join(ROOT, "src/lib/tgAuth.ts"), encoding="utf-8").read()

ok = True


def check(cond, msg):
    global ok
    ok &= bool(cond)
    print("  " + ("✅" if cond else "❌") + " " + msg)


def section(t):
    print()
    print("=" * 70)
    print(t)
    print("=" * 70)


# =============================================================================
section("1) 🔴🔴 A) MENYU «PAGA TUSHIB KETADI» — position")
# =============================================================================
check(".liquid-glass.fixed-pos" in CSS and "position: fixed" in CSS,
      "🔴 `.liquid-glass.fixed-pos` → `position: fixed` (specificity (0,3,0))")
check("fixed-pos" in NAV, "📌 menyu `fixed-pos` klassini ishlatadi")
check("position: relative" in CSS,
      "📖 `.liquid-glass` da `position: relative` bor (boshqa joylar uchun)")
check("liquid-glass-nav" in NAV, "🍎 menyu `liquid-glass-nav` (alohida qatlam)")

# =============================================================================
section("2) 🔴🔴 MENYU QISQA EKRANNI SIGIB O'TMAYDI")
# =============================================================================
# O'lchilgan: 700px ekranda 377px balandlikdagi menyu 796px da tugab,
# «Profil» butunlay ko'rinmasdi («profilni bosganda yuqolib qoladi»).
check("max-h-[calc(100dvh-2rem)]" in NAV, "🔴 `max-h` bilan qisqa ekranda sigadi")
check("overflow-y-auto" in NAV, "📌 kerak bo'lsa o'z ichida siljiydi")
check("overscroll-contain" in NAV,
      "📌 ichki scroll sahifani tortmaydi (g'ildirak zanjir buzilmaydi)")

# =============================================================================
section("3) 🔴🔴 B) UZUN SAHIFALARDA SCROLL")
# =============================================================================
# `overflow-x: hidden` → `overflow-y` `auto` ga aylanadi → NESTED SCROLL
# CONTAINER. Uch manba bor edi: index.css, index.html, App.tsx.
check("overflow-x: hidden" not in HTML,
      "🔴 index.html <body> da `overflow-x-hidden` YO'Q")
check("overflow-x-clip" in HTML, "✅ <body> da `overflow-x-clip`")
check("overflow-x: clip" in CSS and "overflow-x: hidden" not in CSS,
      "🔴 index.css da `overflow-x: clip` (scroll container YARATMAYDI)")
check("overflow-x-clip" in APP and "overflow-x-hidden" not in APP,
      "🔴 App ildizida `overflow-x-clip`")
# 📐 FAQAT KOD (izoh o'zi haqida gapiryapti — tekshiruv izohni
#    «yo'q» deb o'qimasligi kerak)
check("overscroll-behavior-y: none" not in strip_code(CSS),
      "🔴 `overscroll-behavior-y: none` olib tashlandi (zanjir uzilardi)")
check("overscroll-behavior-y: auto" in CSS, "✅ `overscroll-behavior-y: auto`")

# =============================================================================
section("4) 🍎 C) APPLE: KAMROQ ISHLATILGAN MATERIYA")
# =============================================================================
check(".liquid-glass-pill" in CSS and "backdrop-filter" not in
      CSS.split(".dark .liquid-glass-pill")[1].split("}")[0]
      if ".dark .liquid-glass-pill" in CSS else True,
      "📌 pill — blur YO'Q (49 ta badge, Apple: «avoid overusing»)")
check(".liquid-glass-surface" in CSS,
      "📌 karta/catalog uchun arzon qatlam (blur yo'q)")
check("liquid-glass-surface" in NFT,
      "📌 NFT kartalari `liquid-glass-surface` (18 ta blur qatlami kamaydi)")
# 📐 FAQAT KOD tekshiriladi (IZOH emas) — aks holda o'z
#    «backdrop-blur-md olib tashlandi» izohimiz testni qizil qilardi.
check("backdrop-blur-md" not in strip_code(NFT),
      "🔴 NFT yurak tugmalarida `backdrop-blur-md` YO'Q")

# =============================================================================
section("5) 🍎 SCROLL EDGE EFFECT")
# =============================================================================
check(".glass-scroll-edge" in CSS, "🍎 scroll edge effekti mavjud")
check("glass-scroll-edge" in HDR, "📌 sarlavha scroll edge ishlatadi")
check("liquid-glass-nav" in HDR, "📌 sarlavha nav qatlamida")

# =============================================================================
section("6) 🍎 SHAFFOZLIK KAMAYTIRISH (accessibility)")
# =============================================================================
check("prefers-reduced-transparency" in CSS,
      "🍎 avtomatik: `prefers-reduced-transparency` qo'llab-quvvatlanadi")
check("prefers-contrast: more" in CSS,
      "🍎 avtomatik: `prefers-contrast: more` qo'llab-quvvatlanadi")
check(".reduce-transparency" in CSS, "🍎 qo'lda: `.reduce-transparency`")
check("reduceTransparency" in APP, "📌 holat `<html>` ga qo'yiladi")
check("Shaffoflikni kamaytirish" in PROF, "📌 Profil → Sozlamada tanlov")
check("onToggleTransparency" in PROF, "📌 boshqaruvchi prop sifatida keladi")

# =============================================================================
section("7) 🔴 C) DESKTOPDA XARID EKRANI TOR EDU")
# =============================================================================
# `BuyView` ning tashqi konteyneri `md:max-w-3xl` (768px) bo'lgani uchun
# butun XARID ekrani — jumladan NFT katalogi — 768px da cheklangan edi.
check('md:max-w-none lg:px-6 xl:px-10' in BUY,
      "🔴 BuyView tashqi konteyneri `md:max-w-none` (to'liq keng)")
check('md:max-w-3xl mx-auto w-full ${subTab' in BUY,
      "📌 FORM bo'limlari tor qoladi (o'qish uchun) — NFT esa keng")
check("NftRentView" in BUY and "subTab === 'nft'" in BUY,
      "📌 NFT o'z konteynerida (tor konteynerdan tashqarida)")

# =============================================================================
section("8) 🔴🔴 LOG OUT")
# =============================================================================
check("export async function logout" in AUTH, "🔴 `logout()` — serverga xabar beradi")
check("/api/auth/logout" in AUTH, "📌 `POST /api/auth/logout` chaqiriladi")
check("setSessionToken('')" in AUTH, "📌 mahalliy token ham o'chadi")
check("Chiqish (Log out)" in PROF, "🔴 Profil → «Chiqish (Log out)»")
check("onLoggedOut" in APP and "onLoggedOut=" in APP, "📌 App ga ulangan")

print()
print("=" * 70)
print("NATIJA: ✅ BARCHASI TO'G'RI" if ok else "NATIJA: ❌ MUAMMO BOR")
print("=" * 70)
raise SystemExit(0 if ok else 1)