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
check("fixed bottom-4 left-4 right-4" in NAV,
      "\U0001F4F1 pastki panel saqlangan")
check("md:pb-10" in APP, "pastda bo'sh joy faqat telefonda (desktopda lopol emas)")

# =============================================================================
section("6) \U0001F5A5\uFE0F CHAP MENYU")
# =============================================================================
check("fixed left-4 top-1/2" in NAV, "chapga, vertikal markazda")
check('aria-label="Asosiy menyu"' in NAV, "\u00abAsosiy menyu\u00bb (kirish uchun)")
check("aria-current" in NAV, "faol tab belgilangan")

# =============================================================================
section("7) \U0001F310 \U0001F4D6 WEBSITE KIRISH — Telegram Login Widget")
# =============================================================================
check("telegram-widget.js" in LOGIN, "Telegram'ning rasmiy skripti")
check("data-telegram-login" in LOGIN, "bot nomi beriladi")
check("data-request-access" in LOGIN, "\u00abwrite\u00bb so\u0027ralgan (bot xabar yubora oladi)")
check("onTelegramAuth" in LOGIN, "Telegram callback'iga ulangan")
check("/api/auth/telegram" in LOGIN, "serverga imzo yuboriladi")
check("setSessionToken" in LOGIN, "sessiya saqlanadi")

check("isInsideTelegram()" in APP, "Telegram ichimi aniqlanadi")
check("inBrowser" in APP, "brauzer alohida ko\u0027rib chiqiladi")
check("X-Session-Token" in AUTH, "sessiya header'i bor")
check("tgHeadersGet" in AUTH, "GET uchun yordamchi")
check("tgHeaders" in AUTH, "POST uchun yordamchi")

# 🔴 ENG MUHIM: App ning o\u002z so\u002rovi ham sessiya yuborishi SHART.
#    Aks holda brauzerda kirgandan keyin ham \u00abTelegram orqali kiring\u00bb
#    ekranida qolardi (brauzerda aniqlandi: `/api/me` -> 200, lekin UI
#    kirish ekranida qolgan edi).
check("headers: tgHeadersGet(" in APP, "\U0001F534 App\u0021ng asosiy so\u0027rovi sessiya yuboradi")
check(APP.count("x-telegram-init-data") == 0,
      "\U0001F534 qo\u0027lda header bloki qolmadi (sessiya yuborilmas edi)")
check(APP.count("headers: tgHeadersGet(") >= 2,
      "poller ham sessiya yuboradi (avto-to\u0027ldirish ishlaydi)")

# =============================================================================
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

section("9) 🌐 WIDGET DOIM CHIQADI (bot nomi bo'sh bo'lsa ham)")
# =============================================================================
# Mijoz rasmda BO'SH joy ko'rdi — widget chiqmagan edi. Sabab:
# bot nomi `/api/config` dan keladi; u javob bermasa — bo'sh.
check("FALLBACK_BOT_USERNAME" in APP,
      "🔴 qat'iy zaxira bot nomi bor (server javob bermasa ham)")
check("botUsername || BUILD_BOT_USERNAME || FALLBACK_BOT_USERNAME" in APP,
      "🔐 uchta manba ketma-ket sinanadi")
check("BotNameWait" not in APP,
      "📖 «Bot nomi yuklanmoqda» o'lik ekrani olib tashlandi")

# 🔴 Widget QAYERDA chiqishi SHART: skript konteyner ICHIGA
#    qo'shiladi, aks holda iframe kartadan TASHQARIDA chiqadi
#    (mijoz bo'sh joy ko'rdi — bu rasmda bo'lgan muammo).
check("box.appendChild(s)" in LOGIN,
      "🔴 skript konteyner ichiga qo'shiladi (iframe kartada chiqadi)")
check("document.body.appendChild(s)" not in LOGIN,
      "📖 document.body ga qo'shish yo'q (iframe tashqarida chiqardi)")
check("2500" in LOGIN, "iframe chiqmasa QAYTA qo'shish (2.5s)")
check("querySelector('iframe')" in LOGIN,
      "iframe mavjudligi tekshiriladi")

check("bot_username" in read("server.ts"), "server bot nomini qaytaradi")


print()
print("=" * 70)
print("NATIJA: ✅ BARCHASI TO'G'RI" if ok else "NATIJA: ❌ MUAMMO BOR")
print("=" * 70)
raise SystemExit(0 if ok else 1)
