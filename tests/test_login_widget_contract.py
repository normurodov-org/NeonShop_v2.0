"""Telegram orqali kirish KONTRAKTI.

🔴🔴 ESKI YECHIM ISHLAMADI — sababi va yangi yechim:

ESKI: Telegram'ning `telegram-widget.js?23` skripti.
    Skript o'z ichida `window.open` bilan popup ochadi, `postMessage` bilan
    natija kutadi va `checkClose()` bilan har 100 ms da `popup.closed` ni
    tekshiradi:

        function checkClose() {
          if (!activePopup || activePopup.closed) {
            return TWidgetLogin.onClose();   // → getAuth() (XHR)
          }
          setTimeout(checkClose, 100);
        }

    Agar popup bir zumda yopilgan deb hisoblansa — `getAuth()` chaqiriladi,
    u hali tasdiqlanmagan natija qaytaradi (`{"error":"NOT_AUTHORIZED"}`),
    `authFinished = true` bo'ladi va butun oqim o'ladi. Natijada:

        tugma bosiladi → popup ochiladi → yopiladi → HECH NARSA

    Bu Telegram'ning ICHKI ishi — skriptni tuzatish mumkin emas.

✅ YANGI: Telegram'ning RASMIY OAuth sahifasi (popup yo'q).

    1. `https://oauth.telegram.org/auth?bot_id=…&origin=…&return_to=…`
    2. Mijoz Telegram'da tasdiqlaydi
    3. Telegram `return_to#tgAuthResult=<base64url(JSON)>` ga qaytaradi
    4. 🔴 Qaytishni TUGINKI O'ZIMIZ qaytaramiz

    Bu bir xil rasmiy mexanizm, bir xil `SHA256(bot_token)` imzosi va
    bir xil `/api/auth/telegram` endpointi — faqat popup va uning zaif
    tomonlari yo'q.
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
LOGIN_CODE = strip_code(LOGIN)

# =============================================================================
section("1) 🔴 `#tgAuthResult` — TAYINLANUVCHI FORMAT")
# =============================================================================
check("readTelegramAuthResult" in LOGIN, "🔴 hash o'quvchi funksiya bor")
check(r"/[#?&]tgAuthResult=([A-Za-z0-9\-_=]*)$/" in LOGIN,
      "🔴 regex Telegram skripti bilan BIR XIL (manzili bo'yicha)")
check("location.hash = location.hash.replace" in LOGIN,
      "🔴 hash darhol tozalanadi (sahifa yangilanganda eskirgan natija)")
check("window.atob(b64)" in LOGIN, "base64url -> base64 -> JSON")

# 🔴 ENG MUHIM: server `parseInitData` ishlatadi — BUZILGAN QUERY STRING
#    kutadi. `k=v\n` formatida yuborsak, server «hash yo'q» deydi.
check("parts.join('&')" in LOGIN, "🔴🔴 QUERY STRING yig'iladi (`k=v&k=v`)")
check("encodeURIComponent(String(obj[k]))" in LOGIN, "🔴 qiymatlar URL-kodlanadi")
check("parts.push(`hash=" in LOGIN, "🔴 `hash` maydoni qo'shiladi")

# =============================================================================
section("2) 🔴 RASMIY OAUTH URL")
# =============================================================================
check("telegramAuthUrl" in LOGIN, "URL quruvchi funksiya bor")
check("https://oauth.telegram.org/auth?" in LOGIN,
      "🔴 Telegram'ning RASMIY OAuth manzili")
check("bot_id:" in LOGIN, "🔴 `bot_id` (nomi emas, RAQAM) beriladi")
check("origin," in LOGIN, "🔴 `origin` — sayt manzili")
# 📖 Telegram 🌟️ YANGI OYNADA ochiladi.
#    🔴 sababi: `location.href = oauth...` bilan ASL TAB Telegram'ga
#    ketar, mijoz esa telefon/SMS orqali qaytishi kerak bo'lardi —
#    tab «yopilib qaytmay qolgan» degan taassurot paydo bo'lardi.
check("window.open(" in LOGIN, "📖 Telegram YANGI OYNADA ochiladi")
check("width=560,height=640" in LOGIN, "📖 oyna o'lchami beriladi")
check("pollRef" in LOGIN and "setInterval" in LOGIN,
      "📖 asl tab localStorage ni kutib turadi")
# 🔴 `popup.closed` ISHLATILMASIN — u ishonchsiz: boshqa origin
# dan ochilgan popup da brauzer `WindowProxy` ni kesadi va `.closed`
# DARHOL `true` qaytaradi → mijoz hech narsa qilmagan holda
# «bekor qilindi» xabarini olardi.
check("popup.closed" not in LOGIN_CODE, "🔴🔴 `popup.closed` tekshiruvi KODDA YO'Q")
check("OPEN_TIMEOUT_MS" in LOGIN, "📖 vaqt chegarasi bilan")
check("window.close()" in LOGIN, "📖 qaytgan oyna o'zini yopadi")
check("M9.78 18.65" in LOGIN, "📖 RASMIY Telegram icon (qogʻoz-nokurasi)")
check("Bekor qilish" in LOGIN, "🛑️ mijoz istalgan paytda bekor qila oladi")
check("data-testid=\"tg-login-retry\"" in LOGIN, "🔄 xatodan keyin qayta urinish")
check("window.location.href = url" in LOGIN,
      "📖 popup bloklansa — asl tabga qaytish (zaxira)")

# =============================================================================
section("3) 🔒 SERVER TOMONI")
# =============================================================================
check("app.post(\"/api/auth/telegram\"" in SERVER, "kirish endpointi mavjud")
check("verifyTelegramLoginWidget" in SERVER, "imzo tekshiruvchi")
check("parseInitData(data)" in SERVER, "🔴 `parseInitData` — query string")
check('createHash("sha256").update(token' in SERVER,
      "🔴 kalit `SHA256(bot_token)` (WebApp HMAC emas)")

# =============================================================================
section("4) 📌 bot_id — server orqali + zaxira")
# =============================================================================
check("resolveBotId" in SERVER, "🔴 server `getMe` orqali bot_id aniqlaydi")
check("bot_id: botId" in SERVER, "📌 `/api/config` da qaytariladi")
check("FALLBACK_BOT_ID" in APP,
      "📌 zaxira qiymat (server ishlamasa ham tugma o'lmaydi)")
check("else if (FALLBACK_BOT_ID) setBotId(FALLBACK_BOT_ID)" in APP_CODE,
      "📌 fallback ishlatiladi")

# =============================================================================
section("5) 🔄 IKKITA YO'L — HAMMOSI ISHLASHI SHART")
# =============================================================================
check("useEffect" in LOGIN and "readTelegramAuthResult()" in LOGIN,
      "📌 1) hash orqali qaytish (asosiy)")
check("addEventListener('message'" in LOGIN,
      "📌 2) Telegram skriptining `postMessage` orqali natijasi (zaxira)")
check("auth_user" in LOGIN, "🔴 `auth_user` hodisasi qayd etiladi")
check("unauthorized" in LOGIN, "🔴 `unauthorized` hodisasi qayd etiladi")
check("TG_AUTH_ORIGIN" in LOGIN, "🔴 xabar faqat Telegram'dan qabul qilinadi")

# =============================================================================
section("6) 🧹 TOZA LIK")
# =============================================================================
check("removeEventListener('message'" in LOGIN, "🔴 listener tozalanadi")
check("setBusy(true)" in LOGIN, "🔴 qayta yuborish bloklanadi")
check("setSessionToken" in LOGIN, "sessiya saqlanadi")

# =============================================================================
section("7) 🔴 ESKI WIDGET YO'LI OLIB TASHLANGAN")
# =============================================================================
check("telegram-widget.js" not in LOGIN_CODE,
      "🔴 zaif `telegram-widget.js` skripti ishlatilmaydi")
check("TelegramDeepLogin" not in APP_CODE, "🔴 deep-link komponenti yo'q")
check("Botga o'tish" not in APP_CODE, "🔴 «Botga o'tish» tugmasi yo'q")
check("data-testid=\"tg-login\"" in LOGIN, "📌 tugma testlanadi (`data-testid`)")

print()
print("=" * 70)
print("NATIJA: ✅ BARCHASI TO'G'RI" if ok else "NATIJA: ❌ MUAMMO BOR")
print("=" * 70)
raise SystemExit(0 if ok else 1)