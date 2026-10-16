# -*- coding: utf-8 -*-
"""Bot to'xtatilgan holatda HAM xizmatlar ishlamasligi + sayt yo'llari."""
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FAILS = []


def check(cond, msg):
    print(("  ✅ " if cond else "  ❌ ") + msg)
    if not cond:
        FAILS.append(msg)


def section(t):
    print("\n" + "=" * 77)
    print(t)
    print("=" * 77)


def read(p):
    return io.open(os.path.join(ROOT, p), encoding="utf-8").read()


SRV = read("server.ts")
APP = read("src/App.tsx")
ROUTES = read("src/lib/routes.ts")

# =============================================================================
section("1) 🔴🔴🔴 SERVER QALQONI — bot to\u02bcxtatilgan bo\u02b8lsa RAD ETADI")
# =============================================================================
# 🔴 Mijoz shikoyat qilgan edi: «admin paneldan botni to'xtatgan
#    bo'lsam ham, refresh qilmasdan xizmatlardan foydalansam
#    ishlayapti». SABAB: server `bot_active` ni umuman TEKSHIRMAGAN —
#    faqat UI da qalqon bor edi (va `settings` bir marta yuklanardi).
check("function requireBotActive(res: Response)" in SRV,
      "\U0001F534 qalqon funksiyasi bor")
check("res.status(503)" in SRV, "\U0001F534\u0001F534\U0001F534 qalqon `503` qaytaradi")
check("bot_active: false" in SRV, "\U0001F534\u0001F534\U0001F534 javobda `bot_active: false`")
check("reloadSettingsFromDisk" in SRV,
      "\U0001F534\u0001F534\U0001F534 holat DISKDAN qayta o\u02bcqiladi (eskirgan `store` bo\u02b8lmasin)")

# 🔴 Balansga tegadigan HAR BIR endpoint qalqondan o'tishi kerak
MONEY = [
    ("app.post('/api/topup'", "TOP'LDIRISH"),
    ("app.post('/api/order'", "XARID"),
    ("app.post('/api/nfts/rent'", "NFT IJARA"),
    ("app.post('/api/contest/join'", "KONKURS"),
    ("app.post('/api/referral/withdraw'", "REFERAL YECHISH"),
]
for anchor, label in MONEY:
    i = SRV.find(anchor)
    if i == -1:
        check(False, "\U0001F534 %s endpointi topilmadi" % label)
        continue
    body = SRV[i:i + 1200]
    check("requireBotActive(res)" in body,
          "\U0001F534\u0001F534\U0001F534 %s qalqondan o'tadi" % label)

# 🔴 Qalqon balansni O'ZGARTIRISHDAN OLDIN bo'lishi kerak
i = SRV.find("app.post('/api/order'")
seg = SRV[i:i + 1200]
g = seg.find("requireBotActive(res)")
m = seg.find("const user = getUser(req);")
check(g != -1 and g > m and g - m < 400,
      "\U0001F534 xaridda qalqon `getUser` dan KEYIN keladi")

# 🔴 Auth endpointlar qalqondan KECHADI (kirish ishlashi kerak!)
for open_ep in ("app.post('/api/auth/telegram'", "/api/auth/telegram/start"):
    i = SRV.find(open_ep)
    seg = SRV[i:i + 1200] if i != -1 else ""
    check("requireBotActive(res)" not in seg,
          "\U0001F534 kirish endpointi qalqonsiz (\u00abbot to\u02bcxtatilgan\u00bb deb kirmasligi uchun)")

# 🔴 `/api/config` ham ochiq bo'lishi kerak — UI o'zi u yerda
#    bot holatini o'qimaydi, lekin boshqa joylar ishlatishi mumkin
i = SRV.find("app.get('/api/config'")
if i != -1:
    check("requireBotActive(res)" not in SRV[i:i + 900],
          "\U0001F534 `/api/config` qalqonsiz")

# =============================================================================
section("2) \U0001F516 UI — ekranni yangilamasdan sezishi")
# =============================================================================
check("window.setInterval(poll, 10_000)" in APP,
      "\U0001F516\u0001F534\U0001F534U0001F516 bot holati har 10 soniyada tekshiriladi")
check("bot_active === next.bot_active" in APP,
      "\U0001F516\u0001F534\U0001F534U0001F516 state faqat \u00abHOLATI O\u02bcZGARGANDA\u00bb yangilanadi")
check("prev && prev.bot_active === next.bot_active" in APP,
      "\U0001F516\u0001F534\U0001F534U0001F516 aks holda butun `settings` qayta chizilmasdi")
check("Bot vaqtincha to" in APP, "\U0001F516\u0001F534\U0001F534U0001F516 \u00abBot to\u02bcxtatilgan\u00bb ekrani bor")

# =============================================================================
section("3) \U0001F5FA\u0001F534\U0001F534FE0F YO'LLAR — har bir xizmat o\u02b8z manzilida")
# =============================================================================
for p, tab, sub in [("/", "home", None), ("/topup", "topup", None),
                    ("/buy", "buy", "stars"), ("/stars", "buy", "stars"),
                    ("/premium", "buy", "premium"), ("/gifts", "buy", "gifts"),
                    ("/nft", "buy", "nft"), ("/nftrent", "buy", "nft"),
                    ("/ranking", "ranking", None), ("/profile", "profile", None),
                    ("/admin", "admin", None)]:
    check("'%s': { tab: '%s', sub: %s }" % (
        p, tab, ("'%s'" % sub) if sub else "null"
    ) in ROUTES, "\U0001F5FA\u0001F534\U0001F534FE0F %-10s -> %s%s" % (
        p, tab, "/" + sub if sub else ""))

# 🔴 Alias'lar kanonik yo'lga qaytarilishi kerak
check("REDIRECTS" not in ROUTES, "📌 bitta kanonik yo'l (redirect alohida emas)")
check("ALIASES: Record<string, Route>" in ROUTES, "🔴 alias jadvali bitta manba")

# 🔴 `?tab=&sub=` (bot havolalari) buzilmasligi kerak
check("queryToRoute" in ROUTES, "🔴 eski `?tab=&sub=` o\u02bcqiladi")
check("stripQuery" in ROUTES, "🔴 markerlar URL dan tozalanadi")

# 🔴 `popstate` — orqaga/oldinga tugmalar
check("addEventListener('popstate'" in APP, "🔴 `popstate` ishlovchi qo\u02b8shildi")
check("removeEventListener('popstate'" in APP, "🔴 `popstate` tozalanadi")
check("window.history.pushState" in APP, "🔴 ilova -> yo\u02b8l `pushState`")
check("window.history.replaceState" in APP, "🔴 alias -> kanonik `replaceState`")

# 🔴🔴🔴 MOUNT XATOSI (ayni shu yerda tuzatildi):
#     `currentTab` birinchi render'da HALI eski qiymatda bo'ladi.
#     Agar `ILOVA -> YO'L` effekti mount'da ishga tushsa, u
#     `currentTab === 'home'` ko'rib, `/nft` ni darhol `/` ga
#     qaytarib yuboradi.
check("skipFirstPathSync" in APP, "🔴🔴🔴 birinchi render o'tkazib yuboriladi")
check("lastPath" in APP, "🔴🔴 `lastPath` — takror yozish va tariq spam yo\u02b8q")
i = APP.find("skipFirstPathSync.current")
check(APP.find("useEffect", i) if i != -1 else -1 != -1, "📌 effekt ichida")

print()
if FAILS:
    print("NATIJA: ❌ MUAMMO BOR  (%d ta)" % len(FAILS))
    for f in FAILS:
        print("   • " + f)
    raise SystemExit(1)
print("NATIJA: ✅ BARCHASI TO'G'RI")