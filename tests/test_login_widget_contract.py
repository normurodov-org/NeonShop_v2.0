"""Telegram orqali kirish KONTRAKTI.

🔴🔴 ESKI USULLAR VA ULARNING SABABLARI

1) `telegram-widget.js` popup oqimi:
   Skript `checkClose()` bilan har 100 ms da `popup.closed` ni tekshiradi.
   Popup bir zumda yopilgan deb hisoblansa → `getAuth()` →
   `{"error":"NOT_AUTHORIZED"}` → `authFinished = true` → oqim o'ladi:

       tugma bosiladi → popup ochiladi → yopiladi → HECH NARSA

   Bu Telegram'ning ICHKI ishi — tuzatib bo'lmaydi.

2) `window.open(url, 'tg_login', ...)`:
   Brauzer Telegram sahifasini TAB sifatida ochadi, Telegram uni yopadi →
   mijoz «tab ochilib yopildi» deb ko'radi, sayt «kutilayotgan» holatda
   qoladi. ✅ YECHIM: birinchi usul (window.open) butunlay olib tashlandi.

✅ YANGA YECHIM — rasmiy OAuth, BIR TAB:

    1. `https://oauth.telegram.org/auth?bot_id=…&origin=…&return_to=<site>?tg=1`
    2. Mijoz Telegram'da tasdiqlaydi
    3. Telegram `return_to#tgAuthResult=<base64url>` ga QAYTADI
    4. 🔴 Qaytishni TUGINKI o'zimiz o'qitamiz → `/api/auth/telegram`

   `?tg=1` — Telegram'dan qaytganimizni bilish uchun marker
   (`useRef` sahifa qayta yuklanganda nollanadi — ishlamaydi).
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
section("1) 🔴🔴 BIR TAB — ikkinchi tab OCHILMAYDI")
# =============================================================================
# 📜 Asosiy yoʴl BIR TABDA; `window.open` faqat ZAXIRA yoʴlda
#    (Telegram ilovasini ochish uchun) — bu toʸgʸri.
check("window.location.href = telegramAuthUrl(botId)" in LOGIN,
      "📜 asosiy tugma bir tabda (OAuth sahifasi)")
check("/api/auth/telegram/start" in LOGIN, "🌐 zaxira yoʴl: kod soʸraladi")
check("/api/auth/telegram/status" in LOGIN, "🌐 zaxira yoʴl: javob kutiladi")
check('data-testid="tg-login-deep"' in LOGIN, "🌐 zaxira tugmasi bor")
check("window.location.href = telegramAuthUrl(botId)" in LOGIN,
      "📖 asl tab o'zi Telegram'ga boradi")
check("pollRef" not in LOGIN_CODE,
      "🔴 polling kerak emas (bir tabda tabiiy ravishda qaytamiz)")

# =============================================================================
section("2) 🔴 RASMIY OAUTH URL")
# =============================================================================
check("telegramAuthUrl" in LOGIN, "URL quruvchi funksiya bor")
check("https://oauth.telegram.org/auth?" in LOGIN, "🔴 RASMIY manzil")
check("bot_id:" in LOGIN, "🔴 `bot_id` (nomi emas, RAQAM)")
check("origin," in LOGIN, "🔴 `origin` — sayt manzili")
check("return_to:" in LOGIN, "🔴 `return_to` — qaytish manzili")
check("?tg=1" in LOGIN, "📌 `return_to` da `?tg=1` marker")
check("parseInt(VITE_BOT_ID" in APP or "FALLBACK_BOT_ID" in APP,
      "📌 bot_id zaxirasi bor (server ishlamasa ham)")
check("resolveBotId" in SERVER, "🔴 server `getMe` orqali bot_id aniqlaydi")

# =============================================================================
section("3) 🔴 QAYTISHNI O'ZIMIZ QAYTARAMIZ")
# =============================================================================
check("readTelegramAuthResult" in LOGIN, "hash o'quvchi funksiya")
check(r"/[#?&]tgAuthResult=([A-Za-z0-9\-_=]*)$/" in LOGIN,
      "🔴 regex Telegram skripti bilan BIR XIL")
check("location.hash = location.hash.replace" in LOGIN,
      "🔴 hash darhol tozalanadi")
check("window.atob(b64)" in LOGIN, "base64url → base64 → JSON")
check("parts.join('&')" in LOGIN,
      "🔴🔴 QUERY STRING yig'iladi (server `parseInitData` kutadi)")
check("location.hash.replace(/[#?&]tgAuthResult=" in LOGIN,
      "🔴 eskirgan natija qayta kelmaydi")

# =============================================================================
section("4) 🔴 QAYTGANIMIZNI ANIQLASH (`?tg=1`)")
# =============================================================================
# 🔴 `useRef` ishlamaydi: qaytish — to'liq sahifa qayta yuklanishi,
#    ref esa nolga qaytadi. URL markeri esa saqlanib qoladi.
check("cameBack" in LOGIN, "📌 `cameBack` — qaytganimizni aniqlash")
check("URLSearchParams(location.search).get('tg')" in LOGIN, "📌 `?tg=1` o'qiladi")
check("history.replaceState" in LOGIN, "📌 marker tozalanadi")
check("Telegram tasdiqlamadi" in LOGIN,
      "🔴🔴 tasdiqlamasa xabar beriladi (jimgina qolmaydi)")

# =============================================================================
section("5) 🔒 SERVER TOMONI")
# =============================================================================
check('app.post("/api/auth/telegram"' in SERVER, "kirish endpointi mavjud")
check("verifyTelegramLoginWidget" in SERVER, "imzo tekshiruvchi")
check("parseInitData(data)" in SERVER, "🔴 `parseInitData` — query string")
check('createHash("sha256").update(token' in SERVER,
      "🔴 kalit `SHA256(bot_token)` (WebApp HMAC emas)")

# =============================================================================
section("6) 🧹 TOZA LIK va UX")
# =============================================================================
check("setBusy(true)" in LOGIN, "📢 qayta yuborish bloklanadi")
check("setSessionToken" in LOGIN, "sessiya saqlanadi")
check("Bekor qilish" in LOGIN, "🛑️ bekor qilish (orqaga qaytish)")
check("history.back()" in LOGIN, "📖 bekor qilish — orqaga qaytadi")
check('data-testid="tg-login"' in LOGIN, "📌 tugma testlanadi")
check('data-testid="tg-login-retry"' in LOGIN, "📌 qayta urinish testlanadi")

# =============================================================================
section("7) 🎨 TUGMA IKONASI")
# =============================================================================
# 🔴 Eski yo'l chizilgan yo'l «video/play» belgisiga o'xshardi.
check("M9.78 18.65" in LOGIN, "🔴 RASMIY Telegram icon (qogʻoz-nokurasi)")
check('viewBox="0 0 24 24"' in LOGIN, "📌 `viewBox` to'g'ri")

# =============================================================================
section("8) 🔴 ESKI YO'LLAR OLIB TASHLANGAN")
# =============================================================================
check("telegram-widget.js" not in LOGIN_CODE,
      "🔴 zaif `telegram-widget.js` skripti ishlatilmaydi")
check("TelegramDeepLogin" not in APP_CODE, "🔴 deep-link komponenti yo'q")
check("Botga o'tish" not in APP_CODE, "🔴 «Botga o'tish» tugmasi yo'q")

print()
print("=" * 70)
print("NATIJA: ✅ BARCHASI TO'G'RI" if ok else "NATIJA: ❌ MUAMMO BOR")
print("=" * 70)
raise SystemExit(0 if ok else 1)