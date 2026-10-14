"""RED TELEGRAM WIDGET `data-onauth` KONTRAKTI.

XABAR: «Tugmani bosganimda bir ekran ochiladiyu yopiladi lekin kirmaydi.»

RED SABAB — Telegram'ning o'z skriptida (telegram-widget.js):

    if (widgetEl.hasAttribute('data-onauth')) {
      onInitAuthUser = onAuthUser =
        __parseFunction(widgetEl.getAttribute('data-onauth'), ['user']);
    } else if (widgetEl.hasAttribute('data-auth-url')) {
      // ...fallback
    }
    // data-onauth YO'Q bo'lsa -> onAuthUser = undefined

`__parseFunction(name, ['user'])` quyidagini yig'adi va `eval` qiladi:

    (function(user){ <name> })(user)
      -> window.<name>(user)

Natija (data-onauth yo'q bo'lganda):
  tugma bosiladi -> popup ochiladi -> Telegram ruxsat beradi
  -> popup YOPILADI -> hech narsa chaqirilmaydi -> kirish YO'Q.

RED BU XATO TESTDAN O'TIB KETGAN EDI: test `window.onTelegramAuth` ni
qo'lda chaqirdi (real popup oqimi emas), shuning uchun yoqish
ko'rinmadi.

Bu test skript haqiqiy mazmunini TEKSHIRADI va atribut mavjudligini
kafolatlaydi.
"""
import io
import os
import re
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGIN = open(os.path.join(ROOT, "src/components/TelegramLogin.tsx"),
             encoding="utf-8").read()
WIDGET_JS = "/tmp/tw.js"
WIDGET_URL = "https://telegram.org/js/telegram-widget.js?23"

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


def fetch_widget_js():
    """RED Telegram'ning REAL skriptini yuklab oladi.

    Nima uchun lokal nusxa emas? «Atribut qo'yib qo'ydim» degani
    yetarli emas — Telegram skripti qaysi atributni qidirishini
    BIZNING KODIMIZ emas, TUGNING o'z KODI belgilaydi. Shu sabab
    manbani tekshiramiz.

    Internet yo'q bo'lsa test QAYTMAYDI — chunki boshqa testlar
    o'z-o'zidan ishlayveradi.
    """
    if os.path.exists(WIDGET_JS) and os.path.getsize(WIDGET_JS) > 1000:
        return io.open(WIDGET_JS, encoding="utf-8", errors="replace").read()
    # (a) urllib
    try:
        with urllib.request.urlopen(WIDGET_URL, timeout=25) as r:
            raw = r.read()
        with open(WIDGET_JS, "wb") as f:
            f.write(raw)
        return raw.decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    # (b) curl — ba'zi tarmoqlarda Python SSL sertifikatini tekshira
    #     olmaydi (korporativ proxy), lekin curl ishlaydi
    try:
        import subprocess
        subprocess.run(["curl", "-s", "--max-time", "25", WIDGET_URL,
                        "-o", WIDGET_JS],
                       check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
        if os.path.exists(WIDGET_JS) and os.path.getsize(WIDGET_JS) > 1000:
            return io.open(WIDGET_JS, encoding="utf-8", errors="replace").read()
    except Exception:  # noqa: BLE001
        pass
    print("  \u26a0\ufe0f Telegram skriptini yuklab bo'lmadi (internet yo'q?)")
    return ""


# =============================================================================
section("1) RED `data-onauth` — Telegram shu atributga QAT'IY bog'liq")
# =============================================================================
check("setAttribute('data-onauth', 'onTelegramAuth')" in LOGIN,
      "\U0001F534\U0001F534 `data-onauth` = 'onTelegramAuth'")
check("setAttribute('data-telegram-login', botUsername)" in LOGIN,
      "`data-telegram-login` = bot nomi")
check("setAttribute('data-onerror', 'onTelegramLoginError')" in LOGIN,
      "`data-onerror` = xato uchun")

# =============================================================================
section("2) Global funksiyalar (skript ularni shu nom bilan izlaydi)")
# =============================================================================
check("window.onTelegramAuth = async (user: any) => {" in LOGIN,
      "`window.onTelegramAuth` \u2014 asosiy callback")
check("window.onTelegramLoginError = (message: string) => {" in LOGIN,
      "`window.onTelegramLoginError` \u2014 xato callback")

# Funksiya nomi atribut qiymati bilan BIR XIL bo'lishi SHART
attr = re.search(r"setAttribute\('data-onauth',\s*'([^']+)'\)", LOGIN)
check(bool(attr), "atribut qiymati topildi")
if attr:
    name = attr.group(1)
    check("window.%s =" % name in LOGIN,
          "`window.%s` \u2014 atribut bilan bir xil nom" % name)
    err = re.search(r"setAttribute\('data-onerror',\s*'([^']+)'\)", LOGIN)
    if err:
        check("window.%s =" % err.group(1) in LOGIN,
              "`window.%s` \u2014 xato atributi bilan mos" % err.group(1))

# =============================================================================
section("3) RED Telegram skripti HAQIQATAN shuni talab qiladi")
# =============================================================================
js = fetch_widget_js()
if not js:
    print("  \u26a0\ufe0f Telegram skripti topilmadi \u2014 3-bo'lim o'tkazildi")
else:
    check(len(js) > 1000, "Telegram skripti yuklandi (%d bayt)" % len(js))
    check("data-onauth" in js, "skriptda `data-onauth` so'ralgan")
    check("__parseFunction" in js, "skript `__parseFunction` ishlatadi")
    # onAuthUser FAQAT `data-onauth` bor holatda o'rnatiladi
    m = re.search(
        r"if\s*\(widgetEl\.hasAttribute\('data-onauth'\)\)[^;]*?"
        r"onAuthUser\s*=\s*__parseFunction\([^;]*;", js, re.S)
    check(bool(m),
          "\U0001F4D6 `data-onauth` -> `onAuthUser` (faqat shu yo'l bilan)")
    # global izlash
    check("window.execScript ? window.execScript" in js
          or "eval(__func)" in js,
          "global funksiya `eval` orqali topiladi -> `window.onTelegramAuth`")
    check("data-auth-url" not in LOGIN,
          "\U0001F4D6 `data-auth-url` ishlatilmaydi (redirect \u2014 ishlamaydi)")

# =============================================================================
section("4) INJSIYA \u2014 skript karta ICHIDA bo'lishi SHART")
# =============================================================================
# Skript `document.body` ga qo'shilsa, iframe karta tashqarisida
# chiqib ketadi \u2014 foydalanuvchi uni ko'rmaydi.
check("box.appendChild(s)" in LOGIN
      or "boxRef.current.appendChild(s)" in LOGIN,
      "\U0001F534 skript karta ichiga qo'shiladi (ko'rinadigan joyda)")
check("document.body.appendChild(s)" not in LOGIN,
      "\U0001F534 skript `document.body` ga qo'shilmaydi")

# =============================================================================
section("5) /api/auth/telegram \u2014 qabul qilinadigan maydon")
# =============================================================================
SERVER = open(os.path.join(ROOT, "server.ts"), encoding="utf-8").read()
check("/api/auth/telegram" in SERVER, "server endpoint mavjud")
check("verifyTelegramLoginWidget" in SERVER,
      "\U0001F534 SHA256(bot_token) bilan tekshiriladi "
      "(initData emas \u2014 turli kalit!)")
check("initData" in SERVER or "init_data" in SERVER,
      "WebApp initData alohida tekshiriladi (Telegram ichida)")

print()
print("=" * 70)
print("NATIJA: \u2705 BARCHASI TO'G'RI" if ok else "NATIJA: \u274c MUAMMO BOR")
print("=" * 70)
raise SystemExit(0 if ok else 1)