"""Telegram orqali kirish kontrakti (deep link).

XABAR: «tugmani bosdim, ekran ochilib 1 soniyada yopildi, lekin kirmadi —
sahifa o'z-o'zidan qoldi».

SABAB — Telegram'ning eski Login Widget popup oqimi:

    /auth/get javobi -> {"error":"NOT_AUTHORIZED", "origin":"https://..."}
      -> TWidgetLogin.onAuth(origin, false)
        -> data = {event: 'unauthorized'}
          -> PostMessage.send(data, origin)
            -> ota tomonda: onUnauth && onUnauth()

Bizda `data-onunauth` YO'Q EDI — ya'ni hech narsa bo'lmasdi. Shu sababli
eski yo'l BUTUNLAY olib tashlandi va popup'siz yo'lga o'tildi.

YANGI KONTRAKT:

    POST /api/auth/telegram/start -> { code: "web_<48hex>", telegram_url }
    mijoz `t.me/<bot>?start=<kod>` ni ochadi -> Telegram'da **Start** bosadi
    bot.py `/start <kod>` -> kodni `*_login_codes.json` ga yozadi
    GET /api/auth/telegram/status?code=... -> { status: "ok", token }

Popup, CORS va third-party cookie umuman yo'q.
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import strip_code  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = open(os.path.join(ROOT, "src/App.tsx"), encoding="utf-8").read()
DEEP = open(os.path.join(ROOT, "src/components/TelegramDeepLogin.tsx"),
            encoding="utf-8").read()
SERVER = open(os.path.join(ROOT, "server.ts"), encoding="utf-8").read()
BOT = open(os.path.join(ROOT, "bot.py"), encoding="utf-8").read()

ok = True


def check(cond, msg):
    global ok
    ok &= bool(cond)
    print("  %s %s" % ("\u2705" if cond else "\u274c", msg))


def section(t):
    print()
    print("=" * 70)
    print(t)
    print("=" * 70)


# =============================================================================
section("1) ESKI WIDGET BUTUNLAY OLIB TASHLANDI")
# =============================================================================
APP_CODE = strip_code(APP)   # izohlarni olib tashlaydi (helpers.strip_code)
check("TelegramLogin" not in APP_CODE,
      "\U0001F534 App.tsx da eski `TelegramLogin` YO'Q (kodda)")
check("telegram-widget.js" not in APP_CODE,
      "\U0001F534 eski `telegram-widget.js` skripti ishlatilmaydi")
check("Botga o'tish" not in APP_CODE,
      "\U0001F534 «Botga o'tish» tugmasi yo'q (mijoz talabi)")

# =============================================================================
section("2) DEEP LINK komponenti")
# =============================================================================
check("TelegramDeepLogin" in APP_CODE, "App.tsx da `TelegramDeepLogin` bor")
check("/api/auth/telegram/start" in DEEP, "kod so'raydi (`/start`)")
check("/api/auth/telegram/status" in DEEP, "javobni kutadi (`/status`)")
check("setSessionToken" in DEEP, "sessiya saqlanadi")
check("window.open" in DEEP, "Telegram oynasi ochiladi")
check("onSuccess" in DEEP, "muvaffaqiyatda `onSuccess` chaqiriladi")
check("POLL_MS" in DEEP, "javob muntazam tekshiriladi (polling)")
check("MAX_WAIT_MS" in DEEP, "kutish vaqti cheklangan (5 daqiqa)")

# =============================================================================
section("3) FOYDALANUVCHIGA NIMA QILISHNI AYTADI")
# =============================================================================
# Bu eng muhimi: eski yo'lda hech narsa bo'lmasdi — mijoz nima
# qilishini bilmasdi. Endi aniq ko'rsatiladi.
check("Start" in DEEP, "\U0001F510 «Start» tugmasi matnda aytiladi")
check("Bekor qilish" in DEEP, "Bekor qilish bor (u hech qanday oyaga osilmaydi)")
check("'failed'" in DEEP, "\U0001F514 xato holati bor — jimgina qolmaydi")
check("Qayta urinish" in DEEP, "\U0001F504 qayta urinish mumkin")

# =============================================================================
section("4) SERVER endpointlari")
# =============================================================================
check("app.post('/api/auth/telegram/start'" in SERVER, "`/start` route mavjud")
check("app.get('/api/auth/telegram/status'" in SERVER, "`/status` route mavjud")
check("await resolveBotUsername()" in SERVER,
      "\U0001F534 `resolveBotUsername` AWAIT qilingan "
      "(\u201c[object Promise]\u201d bo\u2018lib ketardi)")
check("/^web_[0-9a-f]{48}$/" in SERVER,
      "\U0001F512 kod shakli qattiq tekshiriladi (taxmin qilib bo'lmaydi)")
check("__used_login_codes" in SERVER, "\U0001F512 kod BIR MARTA ishlatiladi")
check("LOGIN_CODES_FILE" in SERVER, "kodlar alohida fayldan o'qiladi")
check("store.users = new Map" in SERVER,
      "\U0001F504 `store.users` fayldan yangilanadi "
      "(bot.py bir necha soniya oldin yozgan bo'lishi mumkin)")

# =============================================================================
section("5) bot.py kodni qabul qiladi")
# =============================================================================
check("def save_web_login_code" in BOT, "`save_web_login_code` bor")
check("WEB_LOGIN_CODE_RE" in BOT, "kod shakli tekshiriladi")
check("if WEB_LOGIN_CODE_RE.match(arg):" in BOT, "`/start` da kod ushlanadi")
check("save_web_login_code(arg, db_user)" in BOT, "kod foydalanuvchiga bog'lanadi")
check("LOGIN_CODES_PATH" in BOT, "kod fayli alohida (eskirgan nusxa yozmaydi)")

# =============================================================================
section("6) FAYLLAR: har birining YAGINA yozuvchisi")
# =============================================================================
# Muhim: `settings.__sessions` da bo'lganda bot.py har 20 soniyada
# uni o'chirdi — mijoz «kirdim, lekin asosiy sahifa ochilmayapti»
# degan edi. Shuning uchun sessiya VA kod alohida fayllarda.
check(".login_codes.json" in SERVER and ".login_codes.json" in BOT,
      "login_codes.json fayli ikkala tomon uchun bir xil")
check(".sessions.json" in SERVER, "sessiya alohida faylda")
# 📐 FAQAT KOD tekshiriladi (IZOH emas) — aks holda o'z
#    «`settings.__sessions` da bo'lganda bot.py o'chirardi» izohimiz
#    testni qizil qilardi.
SERVER_CODE = re.sub(r"//[^\n]*", "", SERVER)
check("__sessions" not in SERVER_CODE,
      "\U0001F534 `settings.__sessions` ISHLATILMAYDI (bot.py o'chirardi)")

print()
print("=" * 70)
print("NATIJA: \u2705 BARCHASI TO'G'RI" if ok else "NATIJA: \u274c MUAMMO BOR")
print("=" * 70)
raise SystemExit(0 if ok else 1)