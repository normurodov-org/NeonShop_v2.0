"""Telegram Login Widget KONTRAKTI.

XABAR: «Login as ... ni bosganimda ekran ochilib 1 soniyada yopiladi,
lekin kirmaydi — sahifa o'z-o'zidan qoldi».

🔴 SABAB — Telegram'ning o'z skriptlari (widget-frame.js):

    onAuth: function (origin, authData, init) {
      if (authData) data = {event: 'auth_user', auth_data: authData};
      else          data = {event: 'unauthorized'};   // shu yerga tushadi
      PostMessage.send(data, origin);
    }

Ota tomonda esa:

    else if (data.event == 'unauthorized') {
      onUnauth && onUnauth();      // data-onunauth YO'Q EDI
    }

Natija: hech narsa bo'lmasdi, sahifa jimgina o'z-o'zidan qolardi.

✅ TUZATILGAN: `data-onauth` + `data-onunauth` + `window.open` kuzatuvchisi
   (watchdog) + iframe qayta yaratish (authFinished reset).
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import strip_code  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = open(os.path.join(ROOT, "src/App.tsx"), encoding="utf-8").read()
LOGIN = open(os.path.join(ROOT, "src/components/TelegramLogin.tsx"),
             encoding="utf-8").read()
SERVER = open(os.path.join(ROOT, "server.ts"), encoding="utf-8").read()

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


APP_CODE = strip_code(APP)

# =============================================================================
section("1) 🔴🔴 `data-onauth` — ENG MUHIM")
# =============================================================================
check("setAttribute('data-onauth', 'onTelegramAuth')" in LOGIN,
      "🔴🔴 `data-onauth` = 'onTelegramAuth'")
check("setAttribute('data-telegram-login', botUsername)" in LOGIN,
      "`data-telegram-login` = bot nomi")
check("window.onTelegramAuth = async (data: string) => {" in LOGIN,
      "global `window.onTelegramAuth` mavjud")

# =============================================================================
section("2) 🔴🔴 `data-onunauth` — IKKINCHI YO'L")
# =============================================================================
# {event:'unauthorized'} -> onUnauth && onUnauth(). Bu handler YO'Q EDI
# -> natija kelmasa sahifa JIMGINA o'z-o'zidan qolardi.
check("setAttribute('data-onunauth', 'onTelegramLoginUnauth')" in LOGIN,
      "🔴🔴 `data-onunauth` atributi bor")
check("window.onTelegramLoginUnauth = " in LOGIN,
      "global `onTelegramLoginUnauth` mavjud")
check("setStuck(true)" in LOGIN, "ruxsat berilmaganda xabar beriladi")

# =============================================================================
section("3) 🔒 WATCHDOG — bosilishni aniqlash")
# =============================================================================
# Tugma IFRAME ichida (oauth.telegram.org), lekin `window.open` bizning
# oynamiz orqali o'tadi — shuning uchun bosilishni ANIQLASH mumkin.
check("window.open = function" in LOGIN, "`window.open` o'rnaladi")
check("WATCHDOG_MS" in LOGIN, "watchdog muddati belgilangan")
check("'/auth'" in LOGIN,
      "faqat Telegram `/auth` popup'ini kuzatadi (boshqa `window.open`lar emas)")
check("setStuck(true)" in LOGIN, "natija kelmasa foydalanuvchi xabardan biladi")

# =============================================================================
section("4) 🔄 TIKLASH — `authFinished` reset")
# =============================================================================
# `TWidgetLogin.authFinished` IFRAME ichida yashaydi va bir marta `true`
# bo'lsa, o iframe boshqa hech qachon natija bermaydi.
check("resetWidget" in LOGIN, "reset funksiyasi bor")
check("querySelectorAll('script[data-telegram-login], iframe')" in LOGIN,
      "iframe va skript to'liq olib tashlanadi")
check("setStuck(false)" in LOGIN, "qayta urishda holat tozalanadi")

# =============================================================================
section("5) 🧹 TOZA LIK (memory leak)")
# =============================================================================
check("window.open = origOpen" in LOGIN, "`window.open` tiklanadi (cleanup)")
check("clearTimeout" in LOGIN, "barcha timerlar tozalanadi")

# =============================================================================
section("6) 📖 INJSIYA va KARTA ICHIDA")
# =============================================================================
check("box.appendChild(s)" in LOGIN, "skript karta ichiga qo'shiladi")
check("document.body.appendChild(s)" not in LOGIN,
      "🔴 `document.body` ga qo'shish yo'q (iframe tashqarida chiqardi)")
check("2500" in LOGIN, "iframe chiqmasa QAYTA qo'shish (2.5s)")

# =============================================================================
section("7) 🔒 SERVER tomoni")
# =============================================================================
check("/api/auth/telegram" in SERVER and "verifyTelegramLoginWidget" in SERVER,
      "server endpoint mavjud")
check("verifyTelegramLoginWidget" in SERVER,
      "🔴 SHA256(bot_token) bilan tekshiriladi (initData emas)")
check("/api/auth/telegram" in LOGIN, "frontend serverga imzo yuboradi")
check("JSON.stringify({ data })" in LOGIN,
      "📖 Telegram IZOHLAYDIGAN MATN yuboradi (obyekt emas)")

# =============================================================================
section("8) 🔴 ESKI DEEP-LINK YO'LI OLIB TASHLANGAN")
# =============================================================================
check("TelegramDeepLogin" not in APP_CODE, "🔴 deep-link komponenti yo'q")
check("TelegramLogin" in APP_CODE, "Widget komponenti ishlatilmoqda")
check("Botga o'tish" not in APP_CODE, "🔴 «Botga o'tish» tugmasi yo'q")

print()
print("=" * 70)
print("NATIJA: ✅ BARCHASI TO'G'RI" if ok else "NATIJA: ❌ MUAMMO BOR")
print("=" * 70)
raise SystemExit(0 if ok else 1)