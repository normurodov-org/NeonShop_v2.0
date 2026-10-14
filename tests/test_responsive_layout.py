"""\U0001F5A5\uFE0F WEBSITE KO'RINISHI — planshet/kompyuterda telefon emas.

XABAR: "men buni website qilmoqchiman ... websiteda desktopdan kirgan
mijoz gridlari keng bo'lsin to'liq ekran bo'lsin."

Ikki xil talab:
  1) \U0001F4D1 Telegram ichida (bot WebApp) — \u00abO\u0027ZGARMASIN\u00bb
  2) \U0001F5A5\uFE0F Brauzerda (sayt) — to'liq ekran, keng gridlar,
     chap menyu

🔴 BREYPOINT: 768px (Tailwind `md`).
   Dastlab 1024 (`lg`) qo'yilgan edi \u2014 lekin planshetning ko\u0027p qismi
   768\u20131024px oralig\u0027da bo\u0027ladi. 1024 qo\u0027yilsa, 1000px
   kenglikdagi planshet TELEFON ko\u0027rinishida qolardi (brauzerda
   o\u0021lchab ko\u0021rildi: `mainW = 448px`).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import strip_code  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(rel):
    return open(os.path.join(ROOT, rel), encoding="utf-8").read()


APP = read("src/App.tsx")
NAV = read("src/components/BottomNav.tsx")
HEAD = read("src/components/Header.tsx")
LAY = read("src/lib/useLayout.ts")
HOME = read("src/components/views/HomeView.tsx")
NFT = read("src/components/views/NftRentView.tsx")
BUY = read("src/components/views/BuyView.tsx")
TOPUP = read("src/components/views/TopupView.tsx")
PROF = read("src/components/views/ProfileView.tsx")
RANK = read("src/components/views/RankingView.tsx")
LOGIN = read("src/components/TelegramLogin.tsx")
LOGIN_CODE = strip_code(LOGIN)
AUTH = read("src/lib/tgAuth.ts")

ok = True


def check(cond, msg):
    global ok
    ok &= bool(cond)
    print(f"  {'\u2705' if cond else '\u274c'} {msg}")


def section(t):
    print()
    print("=" * 70)
    print(t)
    print("=" * 70)


# =============================================================================
section("1) \U0001F4D0 BREYPOINT 768px (planshet ham kiradi)")
# =============================================================================
check("DESKTOP_BREAKPOINT = 768" in LAY, "768px")
check("window.innerWidth >= DESKTOP_BREAKPOINT" in LAY, "bitta manba")
check("matchMedia" in LAY, "resize'da ishlaydi")

# 🔴 JS va CSS BIR XIL BO'LISHI SHART. JS 768 da/desktopga o'tsa,
#    lekin CSS `lg:` (1024) bo'lsa -> kontent menyu ostida qoladi.
check("lg:max-w-none" not in APP, "\U0001F510 CSS `lg:` (1024) qolmadi \u2014 `md:` (768)")
check("lg:pl-[124px]" not in APP, "\U0001F510 CSS `lg:pl-` qolmadi")
check("md:pl-[124px]" in APP, "kontent chapga siljishi `md:` bilan")
check("'md:pl-[124px]'" in APP, "JS ham `md:` ishlatadi (CSS bilan mos)")

# =============================================================================
section("2) \U0001F5A5\uFE0F TO'LIQ EKRAN (cheklangan emas)")
# =============================================================================
check("md:max-w-none" in APP, "App konteneri to'liq keng")
check("md:max-w-none" in HOME, "Bosh sahifa to'liq keng")
check("md:max-w-none" in NFT, "NFT Rent to'liq keng")
check("md:max-w-none" in PROF, "Profil to'liq keng")
check("md:max-w-none" in RANK, "Reyting to'liq keng")
check("md:max-w-none" in HEAD, "sarlavha to'liq keng")

# =============================================================================
section("3) \U0001F4D8 FORM sahifalari o\u0027qiladigan ustunda qoladi")
# =============================================================================
# 🔴 To'liq kenglikda FORM matni juda uzun bo\u0027lardi \u2014 o\u0027qib
#    bo\u0021lmaydi. Shuning uchun faqat formalar `md:max-w-3xl`.
check("md:max-w-3xl" in BUY, "Xarid formasi o\u0027qiladigan en/ligi")
check("md:max-w-3xl" in TOPUP, "To\u0027ldirish formasi o\u0027qiladigan en/ligi")
check("md:max-w-3xl" not in HOME, "\U0001F534 Bosh sahifa to'liq keng (cheklanmagan)")

# =============================================================================
section("4) \U0001F5A5\uFE0F GRIDLAR kengroq ustun")
# =============================================================================
check("grid-cols-1 sm:grid-cols-2 xl:grid-cols-4" in HOME,
      "Xizmat kartalari: 1 / 2 / 4 ustun")
check("grid-cols-2 sm:grid-cols-3 md:grid-cols-4 2xl:grid-cols-5" in NFT,
      "\U0001F4D6 NFT: 2 / 3 / 4 / 5 ustun (1000px da 4 ta o\u2018lchadi)")
check("md:grid-cols-4" in PROF, "Profil statistikasi: 4 ustun")

# =============================================================================
section("5) \U0001F4F1 TELEFON KO\u0027RINISHI O\u0027ZGARMAGAN")
# =============================================================================
# 🔴 Eng muhimi: mobil O\u0026ZGARMASIN. Bu bo\u0021limni olib tashlash,
#    ilovani telefon uchun buzadi.
for name, src in (("App", APP), ("Bosh sahifa", HOME), ("Xarid", BUY),
                  ("To\u0027ldirish", TOPUP), ("Profil", PROF), ("NFT", NFT)):
    check("max-w-md" in src, f"{name}: `max-w-md` (telefon) saqlangan")
# 🔴🔴 AVVAL: tashqi `fixed bottom-4 …` + ichki `<nav>` ham
#    `fixed-pos` (position:fixed). Telegram WebView da ichki `fixed`
#    panelni ekran pastidan «kesib» qo'yardi — mijoz rasmida shu.
# ✅ ENDI: tashqi div — faqat JOY (inset + safe-area), ichki nav —
#    `relative` + `mx-auto` (markazlangan).
check("fixed bottom-0 left-0 right-0" in NAV,
      "📱 panel joyi `fixed inset-x-0 bottom-0`")
check("env(safe-area-inset-bottom)" in NAV,
      "📱 iPhone/Home indicator ostida ham toʸgʸri")
check("relative liquid-glass-nav mx-auto max-w-md" in NAV,
      "📱📱 ichki panel `relative` + markazlangan")
# 📜 FAQAT telefon qismi (desktop rail da `fixed-pos` toʸgʸri —
#    u yerda `fixed` qaytarish SHART)
_phone = NAV[NAV.index('TELEFON'):] if 'TELEFON' in NAV else NAV
check("fixed-pos liquid-glass-nav" not in _phone,
      "🔴 telefon panelida `fixed-pos` YOʸQ")
check("fixed-pos" in NAV[:NAV.index('TELEFON')] if 'TELEFON' in NAV else True,
      "📜 desktop rail da `fixed-pos` bor (u yerda SHART)")
check("md:pb-10" in APP, "pastda bo'sh joy faqat telefonda (desktopda lopol emas)")

# =============================================================================
section("6) \U0001F5A5\uFE0F CHAP MENYU")
# =============================================================================
check("fixed left-4 top-1/2" in NAV, "chapga, vertikal markazda")
check('aria-label="Asosiy menyu"' in NAV, "\u00abAsosiy menyu\u00bb (kirish uchun)")
check("aria-current" in NAV, "faol tab belgilangan")

# =============================================================================
section("7) 🔐 📖 WEBSITE KIRISH — Telegram rasmiy OAuth")
# =============================================================================
# 🔴🔴 ESKI WIDGET POPUP OQIMI ISHLAMADI, SABABI ANIQLANDI:
#
#   Telegram'ning `telegram-widget.js` skripti `checkClose()` bilan har
#   100 ms da `popup.closed` ni tekshiradi. Popup bir zumda yopilgan
#   deb hisoblansa → `getAuth()` → `{"error":"NOT_AUTHORIZED"}` →
#   `authFinished = true` → butun oqim o'ladi:
#
#       tugma bosiladi → popup ochiladi → yopiladi → HECH NARSA
#
#   Bu Telegram'ning ICHKI ishi — skriptni tuzatib bo'lmaydi.
#
#   ✅ YANGI: rasmiy OAuth sahifasi (popup yo'q). Telegram foydalanuvchi
#   tasdiqlagach `return_to#tgAuthResult=...` ga qaytaradi, qaytishni
#   TUGINKI o'zimiz qaytaramiz.
check("telegramAuthUrl" in LOGIN, "🌐 rasmiy OAuth URL quruvchisi")
check("TG_AUTH_ORIGIN = 'https://oauth.telegram.org'" in LOGIN
      and "/auth?" in LOGIN, "🔴🔴 RASMIY manzil")

# 📜📜📜 ASOSIY TUGMA — Telegram ILOVASI orqali (deep link).
#    🔴 `oauth.telegram.org/auth` brauzerda TAB ichida ochilganda Telegram
#    uni oʼzini yopadi → shuning uchun bu zaxira yoʽl, asosiy emas.
check('data-testid="tg-login"' in LOGIN, "📜 asosiy tugma bormi")
check("onClick={deepStart}" in LOGIN,
      "📜📜 ASOSIY tugma deep link ga ulangan (Telegram ilovasi)")
check("/api/auth/telegram/start" in LOGIN, "📜 kod soʸraladi (`/start`)")
check("telegram_url" in LOGIN, "📜 Telegram ilova havolasi")

# 🟡 ZAXIRA — Telegram web (oauth.telegram.org)
check('data-testid="tg-login-oauth"' in LOGIN, "🟡 zaxira tugmasi (web) bor")
check("oauthStart" in LOGIN, "🟡 zaxira OAuth funksiyasi bor")

# 🔴🔴🔴 JAMOI TAB HEQ QACHON KOʼCHMAYDI/YOPILMAYDI
check("window.location.href = telegramAuthUrl" not in LOGIN,
      "🔴🔴🔴 jamiy tab Telegram ga KOʼCHMAYDI")
check("location.assign" not in LOGIN and "location.replace(" not in LOGIN,
      "🔴🔴🔴 jamiy tab YUBORILMAYDI")
check("window.open('', '_blank')" in LOGIN,
      "🔴🔴🔴 Telegram YANGI oynada ochiladi")
check(LOGIN.index("const w = openBlank();")
      < LOGIN.index("await fetch('/api/auth/telegram/start'"),
      "🔴🔴 oyna `await` dan OLDIN ochiladi (popup bloklanmasin)")
check("sessionToken()" in LOGIN, "🔴🔴 natija `localStorage` orqali")
check("postMessage" not in LOGIN_CODE, "🔴🔴🔴 `postMessage` yoʸq (COOP xavfsiz)")
check("w.location.href = url" in LOGIN, "🔴 yangi oyna Telegram ga yuboriladi")
# 🔴🔴🔴 DEEP LINK UCHUN `/status` POLLI SHART.
#    `t.me` oynasi saytimizga QAYTMAGANI uchun token faqat server orqali
#    keladi — bu yoʸl boʸlmasa deep link umuman ishlamaydi.
check("/api/auth/telegram/status?code=" in LOGIN,
      "🔴🔴🔴 deep link natijasi server dan olinadi (`/status`)")
check("waitForResult(j.code)" in LOGIN,
      "🔴🔴🔴 kod poller ga uzatiladi")
check("setSessionToken(j.token)" in LOGIN,
      "🔴🔴🔴 token `localStorage` ga yoziladi")
check("sessionToken()" in LOGIN,
      "🔴🔴🔴 OAuth uchun `localStorage` ham tekshiriladi")
check("setFallbackUrl" in LOGIN, "🔴 popup bloklanganda havola koʸrsatiladi")

# 🔴 Qaytishni oʸzimiz oʸqitamiz
check("readTelegramAuthResult" in LOGIN, "📖 qaytishni oʸzimiz oʸqitamiz")
check("Telegram tasdiqlamadi" in LOGIN,
      "🔴🔴 tasdiqlamasa xabar beriladi (jimgina qolmaydi)")
check("parts.join('&')" in LOGIN, "🔴🔴 QUERY STRING (server kutadi)")
check("M9.78 18.65" in LOGIN, "📖 rasmiy Telegram icon")
section("8) 🔐 «BOTGA O'TISH» TUGMASI BO'LMASIN")
# =============================================================================
# Mijozning so'rovi: "bu tugma umuman kerakmas ... Botga o'tishi
# umuman kerakmas."
check("BOT_WEBAPP_URL" not in APP, "🔴 «Botga o'tish» URL o'zgaruvchisi o'chirilgan")
# 📐 FAQAT KOD tekshiriladi (IZOH emas) — aks holda o'z
#    ««Botga o'tish» o'chirilgani» izohimiz testni qizil
#    qilardi. `strip_code` shu uchun ishlatiladi.
APP_CODE = strip_code(APP)
check("Botga o&apos;tish" not in APP_CODE and "Botga o'tish" not in APP_CODE,
      "🔴 «Botga o'tish» TUGMASI butunlay olib tashlandi (kodda)")
check("Yoki Telegram ilovasi orqali oching" not in APP,
      "📖 «Yoki Telegram ilovasi orqali oching» matni ham ketsin")
check("href={BOT_WEBAPP_URL}" not in APP and "href=\"https://t.me/" not in APP,
      "kirish ekranida bot havolasi yo'q")

section("9) 🔐 KIRISH TUGMASI VA XATO HOLATLARI")
# =============================================================================
check("{wait ? (" in LOGIN, "📢 qayta bosish bloklanadi (kutish holati)")
check("setErr(" in LOGIN, "🔔 xato holati bor")
check('data-testid="tg-login-retry"' in LOGIN, "🔄 xatodan keyin qayta urinish")
check("bot_username" in read("server.ts"), "server bot nomini qaytaradi")


print()
print("=" * 70)
print("NATIJA: ✅ BARCHASI TO'G'RI" if ok else "NATIJA: ❌ MUAMMO BOR")
print("=" * 70)
raise SystemExit(0 if ok else 1)
