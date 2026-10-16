# -*- coding: utf-8 -*-
"""UI tozalash: sarlavha chegarasi, kartalar, pastki havolalar, fon."""
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FAILS = []


def check(cond, msg):
    print(("  \u2705 " if cond else "  \u274c ") + msg)
    if not cond:
        FAILS.append(msg)


def section(t):
    print("\n" + "=" * 77)
    print(t)
    print("=" * 77)


def read(p):
    return io.open(os.path.join(ROOT, p), encoding="utf-8").read()


CSS = read("src/index.css")
HDR = read("src/components/Header.tsx")
HOME = read("src/components/views/HomeView.tsx")
APP = read("src/App.tsx")
SRV = read("server.ts")
GRID = read("src/lib/gridBackdrop.ts")
COMP = read("src/components/GridBackdrop.tsx")

# =============================================================================
section("1) SARLAVHA CHegarasi - FAQAT PASTDA")
# =============================================================================
check("glass-bottom-edge" in CSS, "`.glass-bottom-edge` qoidasi bor")
check("border-top: 0" in CSS, "tepa chegarasi YO'Q")
check("border-right: 0" in CSS, "ong chegarasi YO'Q")
check("border-left: 0" in CSS, "chap chegarasi YO'Q")
check("border-bottom: 1px solid var(--lg-edge)" in CSS,
      "past chegarasi SAQLANGAN")
check("glass-bottom-edge" in HDR, "sarlavhada klass qo'llangan")

# 🔴🔴🔴 SPECIFICITY - bu yerda ASOSIY nuqson bo'ldi:
#   `html body .glass-bottom-edge` = (0,1,2)  ← birinchi urinish
#   `.dark .liquid-glass-nav`      = (0,2,0)  ← BU YUTARDI
#   CSS avval ID, keyin KLASS, keyin ELEMENT solishtiradi:
#   1 klass < 2 klass. Shuning uchun `.dark`/`.light` ham ichida.
check("html body .dark .glass-bottom-edge" in CSS,
      "🔴🔴🔴 `.dark` qoidasi ichida - (0,2,2) > (0,2,0)")
check("html body .light .glass-bottom-edge" in CSS,
      "🔴🔴🔴 `.light` qoidasi ham (yorug' rejim)")

# 📌 `!important` faqat DEKLARATSIYADA tekshiriladi (izoh emas)
_decl = CSS.split("html body .dark .glass-bottom-edge", 1)[-1].split("}", 1)[0]
check("!important" not in _decl, "`!important` kerak emas (spesifisitka yetadi)")

# =============================================================================
section("2) KARTALAR - TIQILISHLIK BARBOLDI")
# =============================================================================
# 🔴 NIMA BO'LGAN EDI?
#   Karta gorizontal `items-center justify-between` edi: matn + pill
#   bir qatorda. Matn CHEKLANMAGAN uchun pill OSTIGA kirib ketardi
#   (rasmdagi «doira yozuv ustida turibdi» holati).
check(HOME.count("flex flex-col gap-3") == 4,
      "🔴🔴🔴 4 ta karta ustma-ust tikildi (2 qator)")
check(HOME.count("min-w-0") >= 8, "matn konteyneri `min-w-0` (chekiladi)")
check(HOME.count("line-clamp-2") == 4, "tavsif 2 qator bilan cheklangan")
check(HOME.count("whitespace-nowrap shrink-0") == 4,
      "🔴🔴🔴 pill qisqarmaydi (`whitespace-nowrap`)")

# 📌 Eski BIR QATORLI layout qolmaganligi
check("flex items-center justify-between apple-spring" not in HOME,
      "🔴🔴🔴 eski bir qatorli karta layout YO'Q")
check(HOME.count('className="flex items-center justify-between gap-2"') == 4,
      "pill qatori (pill + strelka) 4 tilda - to'g'ri ajratilgan")

# =============================================================================
section("3) PASTKI HAVOLALAR")
# =============================================================================
check("FooterLinks" in HOME, "`FooterLinks` komponenti bor")
check("<FooterLinks" in HOME, "bosh sahifaga ulandi")
for key, fallback in [("support_username", "normuzb"),
                      ("news_channel", "Shop_NeonChannel"),
                      ("orders_channel", "Shop_NeonOrders")]:
    check("'%s'" % key in HOME, "📄📄 `%s` havolasi" % key)
    check("'%s'" % fallback in HOME, "📄📄 zaxira: `%s`" % fallback)

check("https://t.me/${raw}" in HOME, "🔐 Telegram havolasi to'g'ri quriladi")
check(".replace(/^@/, '')" in HOME, "📄 `@` olib tashlanadi")
check('target="_blank"' in HOME, "🔐 yangi oynada ochiladi")
check('rel="noopener noreferrer"' in HOME, "📄 xavfsiz `rel`")
check('aria-label="Foydali havolalar"' in HOME, "📏 ekran o'quvchilar uchun `aria-label`")

# Server havolalarni yuborishi kerak (ikki manba bo'lmasin)
check('news_channel: (process.env.NEWS_CHANNEL' in SRV,
      "📦 server `news_channel` ni yuboradi")
check('orders_channel: (process.env.ORDERS_CHANNEL' in SRV,
      "📦 server `orders_channel` ni yuboradi")

# =============================================================================
section("4) FON - OQ-QORA, DOIRA / YORUG'LIK / CHIZIQ YO'Q")
# =============================================================================
check("rgba(255, 255, 255, 0.34)" in GRID, "🎀 nuqta oq")
check("rgba(255, 255, 255, 1)" in GRID, "🎀 kursor ostidagi nuqta to'liq oq")
check("rgba(0, 0, 0, 0.30)" in GRID, "☀ yorug' rejimda nuqta qora")
check("rgba(23, 64, 30" not in GRID, "🔴🔴🔴 yashil rang QOLMADI")
check("glow" not in GRID, "🔴🔴🔴 kursor ostidagi yorug'lik maydoni ham yo'q")
check("waves" not in GRID, "🔴🔴🔴 tolqin/doira tizimi butunlay olib tashlandi")
check("createRadialGradient" not in GRID, "🔴🔴🔴 gradient chizish kodi yo'q")
check("P.wave" not in GRID, "🔴🔴🔴 tolqin rangi ishlatilmaydi")

# 🔴🔴🔴 CHIZIQLAR butunlay olib tashlandi (faqat nuqta qoladi)
check("showLines = false" in GRID, "🔴🔴🔴 sukut bo'yicha chiziq YO'Q")
check("if (showLines) {" in GRID, "📄 chiziqlar shartli - kod saqlangan")
check("prevX = Math.round(n.ox)" in GRID, "📄 vertikal chiziq kodi saqlangan")
check("prevY = Math.round(n.oy)" in GRID, "📄 gorizontal chiziq kodi saqlangan")
check("waves.push(" not in COMP, "🔴 tolqin umuman tug'maydi")
check("stepWaves" not in COMP, "🔴 `stepWaves` ishlatilmaydi")

# =============================================================================
section("5) TUGMA USTIDA FON TO'XTAYDI")
# =============================================================================
check("onOverUI" in COMP, "🔴🔴🔴 `pointerover` ishlovchi bor")
check("button, a, input, select, textarea" in COMP,
      "🔴🔴🔴 tugma / link / input aniqlanadi")
check("stepNodes(geo.nodes, cx, cy, geo.radius, 0, 0.16)" in COMP,
      "🔴🔴🔴🔴 tugma ustida SURISH = 0 (faqat qaytish)")
check("geo.cell * 0.42,   // surish" in COMP,
      "📁 fonda surish (push) ishlaydi")
check("(active && !overUI && !reducedMotion())" in COMP,
      "🔴🔴🔴 tugma ustida animatsiya to'xtaydi")
check("reducedMotion" in COMP, "📁 `prefers-reduced-motion` qo'llab-quvvatlanadi")

# 🔴 TDZ: o'zgaruvchi funksiyadan OLDIN e'lon bo'lishi kerak
check(COMP.index("let overUI = false;") < COMP.index("const onOverUI"),
      "🔴🔴🔴 TDZ yo'q: `overUI` `onOverUI` dan OLDIN")
check(COMP.index("const reducedMotion") < COMP.index("reducedMotion()"),
      "🔴🔴 `reducedMotion` ta'rifidan oldin ishlatilmaydi")

# =============================================================================
section("6) FON butun ekranlarda")
# =============================================================================
check(APP.count("<GridBackdrop") == 3,
      "📍 GridBackdrop 3 ekranda (kirish / bot-to'xtatilgan / asosiy)")
check("aurora-blob" not in APP, "🔴 eski aurora fon YO'Q")

print()
if FAILS:
    print("NATIJA: ❌ MUAMMO BOR  (%d ta)" % len(FAILS))
    for f in FAILS:
        print("   - " + f)
    raise SystemExit(1)
print("NATIJA: ✅ BARCHASI TO'G'RI")