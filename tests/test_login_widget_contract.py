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
section("1) 🔴🔴🔴 JAMOI TAB HEQ QACHON KOʼCHMAYDI / YOPILMAYDI")
# =============================================================================
# 📜📜📜 ASOSIY TUGMA — Telegram ILOVASI orqali (deep link).
#    🔴 `oauth.telegram.org/auth` brauzerda TAB ichida ochilganda Telegram
#    uni oʼzini yopadi → shuning uchun bu zaxira yoʽl, asosiy emas.
check('data-testid="tg-login"' in LOGIN, "📜 asosiy tugma bormi")
check("onClick={deepStart}" in LOGIN,
      "📜📜 ASOSIY tugma deep link ga ulangan (Telegram ilovasi)")
check("/api/auth/telegram/start" in LOGIN, "📜 kod soʸraladi (`/start`)")
check("telegram_url" in LOGIN, "📜 Telegram ilova havolasi")

# 🔴🔴🔴 MIJOZGA QOʸLDA: «bosdim → tab yopildi»
#    — BU BOʸLMAYDI. Jamiy tab hech qachon `location` ga yozilmaydi.
check("window.location.href = telegramAuthUrl" not in LOGIN,
      "🔴🔴🔴 jamiy tab Telegram ga KOʼCHMAYDI")
check("location.assign" not in LOGIN and "location.replace(" not in LOGIN,
      "🔴🔴🔴 jamiy tab boshqa manzilga YUBORILMAYDI")
check("window.open('', '_blank')" in LOGIN,
      "🔴🔴🔴 Telegram YANGI oynada ochiladi (boʸsh oyna avval)")

# 🔴 Popup bloklanmasligi uchun `window.open` `await` DAN OLDIN
check(LOGIN.index("const w = openBlank();")
      < LOGIN.index("await fetch('/api/auth/telegram/start'"),
      "🔴🔴 oyna `await` dan OLDIN ochiladi (popup bloklanmasin)")

# 🔴 Natija `localStorage` orqali uzatiladi (postMessage/COOP yoʸq)
check("waitForResult" in LOGIN, "🔴 natija kutiladi")
check("sessionToken()" in LOGIN, "🔴🔴 `localStorage` orqali sezish")
check("postMessage" not in LOGIN_CODE,
      "🔴🔴🔴 `postMessage` yoʸq (COOP/COEP muammosi boʸlmaydi)")
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

# 🔴 Popup bloklanganda — havola koʸrsatiladi, jamiy tab qoladi
check("setFallbackUrl" in LOGIN, "🔴 bloklanganda havola koʸrsatiladi")
check('data-testid="tg-login-fallback"' in LOGIN, "🔴 zaxira havola testlanadi")

# 🟡 ZAXIRA — Telegram web (oauth.telegram.org)
check('data-testid="tg-login-oauth"' in LOGIN, "🟡 zaxira tugmasi (web) bor")
check("oauthStart" in LOGIN, "🟡 zaxira OAuth funksiyasi bor")
check("pointWindow(w, url)" in LOGIN and "telegramAuthUrl(botId)" in LOGIN,
      "🟡 zaxira OAuth HAM yangi oynada ochiladi")

# 🔴 Qaytishni oʸzimiz oʸqitamiz
check("readTelegramAuthResult" in LOGIN, "📖 qaytishni oʸzimiz oʸqitamiz")
check("Telegram tasdiqlamadi" in LOGIN,
      "🔴🔴 tasdiqlamasa xabar beriladi (jimgina qolmaydi)")
check("parts.join('&')" in LOGIN, "🔴🔴 QUERY STRING (server kutadi)")
check("M9.78 18.65" in LOGIN, "📖 rasmiy Telegram icon")
section("2) 🔴 RASMIY OAUTH URL")
# =============================================================================
check("telegramAuthUrl" in LOGIN, "URL quruvchi funksiya bor")
check("TG_AUTH_ORIGIN = 'https://oauth.telegram.org'" in LOGIN
      and "/auth?" in LOGIN, "🔴 RASMIY manzil")
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
check("{wait ? (" in LOGIN, "📢 qayta bosish bloklanadi (kutish holati)")
check("setSessionToken" in LOGIN, "sessiya saqlanadi")
check("Bekor qilish" in LOGIN, "🛑️ bekor qilish (orqaga qaytish)")
check("onClick={stopWaiting}" in LOGIN,
      "📖 bekor qilish — kutishni toʸxtatadi (orqaga QAYTMAYDI)")
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