# -*- coding: utf-8 -*-
"""NFT: narx o'zgartirish (admin) + botdan WebApp NFT bo'limiga o'tish."""
import ast
import io
import os
import re
from urllib.parse import parse_qs, urlparse

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

BOT = read("bot.py")
APP = read("src/App.tsx")
BUY = read("src/components/views/BuyView.tsx")

# Python sintaksisini ham tekshiramiz — Dockerfile build'da shuni qiladi
try:
    ast.parse(BOT)
    check(True, "🔴🔴 `bot.py` sintaksisi to'g'ri (Dockerfile shuni tekshiradi)")
except SyntaxError as e:
    check(False, "🔴🔴 `bot.py` sintaksisida xato: %s (qator %s)" % (e.msg, e.lineno))
    print("\nNATIJA: ❌ MUAMMO BOR")
    raise SystemExit(1)

# =============================================================================
section("1) 💰 NFT RO'YXATIDA NARX O'ZGARTIRISH")
# =============================================================================
check("price = State()" in BOT, "🔴 `NftStates.price` holati mavjud")
check("F.data.startswith(\"adm:nft_price:\")" in BOT,
      "🔴 `adm:nft_price:<id>` callback handler bor")
check("StateFilter(NftStates.price), F.text" in BOT,
      "🔴🔴 narx kiritish handleri bor (admin son yuboradi)")
check("adm:nft_price:" in BOT, "🔴 ro'yxatdagi `💰 Narx` tugmasi bor")
check('text="💰 Narx"' in BOT, "🔴 tugma matni `💰 Narx`")

# 🔴 Asosiy: narx HAQIQATAN saqlanishi
set_body = BOT.split("async def adm_nft_price_set", 1)[1][:4000]
check('n["daily"] = int(new)' in set_body, "🔴🔴🔴 `daily` yangilanadi")
check("db.save()" in set_body, "🔴🔴🔴 `db.save()` — bazaga yoziladi")
check("await state.clear()" in set_body, "🔴 holat tozalanadi")

# 🔴 Narx validatsiyasi — bo'sh/ manfiy/ kasr kabul qilinmasin
check("new < 1" in set_body, "🔴🔴 manfiy va 0 narx rad etiladi")
check("parse_uzs_amount" in set_body, "🔴🔴 `parse_uzs_amount` — qo'lda parse emas")
check("old = num(n.get(\"daily\"))" in set_body, "🔴 eski narx saqlanadi (taqqoslash uchun)")

# 🔴 NFT topilmasa — narx O'ZGARMASIN
check("if not n:" in set_body, "🔴🔴 NFT topilmasa narx tegilmaydi")
check("narx o'zgartirilmadi" in set_body, "🔴🔴🔴 admin ogohlantiriladi")

# Ro'yxat narxni ko'rsatadi
check("1 kun: <b>{fmt(num(n.get('daily')))} UZS</b>" in BOT,
      "🔴 ro'yxatda 1 kunlik narx ko'rinadi")
ask_body = BOT.split("async def adm_nft_price_ask", 1)[1][:3000]
check("Hozirgi 1 kunlik narx" in ask_body,
      "🔴🔴 so'rovda JORIY narx ko'rsatiladi")
check("nft_rent_quote(old, NFT_MIN_DAYS)" in ask_body,
      "🔴🔴 jami narx ham ko'rsatiladi (3/7/14/30 kun)")

# =============================================================================
section("2) 🔗 BOTDAN WEBAPP NFT BO'LIMIGA O'TISH")
# =============================================================================
m = re.search(r"def nft_webapp_url\(\) -> str:(.*?)(?=\n\ndef |\n\n# =====)", BOT, re.S)
check(m is not None, "🔴 `nft_webapp_url()` funksiyasi bor")
if m:
    ns = {"WEBAPP_URL": "https://site.example.com/"}
    exec(compile("def _f() -> str:" + m.group(1), "<t>", "exec"), ns)
    url = ns["_f"]()
    print("     → " + url)
    check("tab=buy" in url, "🔴🔴🔴 `tab=buy` — Xarid ekrani ochiladi")
    check("sub=nft" in url, "🔴🔴🔴 `sub=nft` — ichki NFT tabi ochiladi")
    q = parse_qs(urlparse(url).query)
    check(q.get("tab") == ["buy"], "🔴 query `tab=buy` to'g'ri parsed")
    check(q.get("sub") == ["nft"], "🔴 query `sub=nft` to'g'ri parsed")

# nft_start da WebApp tugmasi BIRINCHI bo'lishi kerak
nft_start = BOT.split("async def nft_start", 1)[1][:2500].split("\n\n@router", 1)[0]
check("nft_webapp_url()" in nft_start, "🔴🔴🔴 `nft_start` WebApp tugmasidan foydalanadi")
check("web_app=WebAppInfo" in nft_start, "🔴🔴🔴 `WebAppInfo` — haqiqiy Web App tugmasi")
check("NFT ijaraga olish (Web App)" in nft_start, "🔴 tugma matni")
check("https://t.me/" in nft_start, "🟡 kanal tugmasi ZAXIRADA saqlangan")
check(nft_start.index("nft_webapp_url()") < nft_start.index("NFT_CHANNEL"),
      "🔴🔴🔴 WebApp tugmasi birinchi (kanal — ikkinchi)")

# =============================================================================
section("3) 🌐 ILOVA: NFT BO'LIMIGA YO'L QORQALI KIRISH")
# =============================================================================
# 📌 Eski tuzilma «CHUQUR HAVOLA» effekti edi (`?tab=&sub=`).
#    Endi bu mantiqa `src/lib/routes.ts` ga ko'chirilgan — u yagona
#    manba bo'lib, `/nft` kabi HAQIQIY yo'llarni ham qo'llaydi.
ROUTES = read("src/lib/routes.ts")

check("from './lib/routes'" in APP, "📌 ilova routing modulini import qiladi")
for fn in ("pathToRoute", "queryToRoute", "routeToPath", "stripQuery"):
    check(fn in APP, "📌 `%s` ishlatiladi" % fn)
    check("export function %s" % fn in ROUTES,
          "📌📌 `%s` modulda eksport qilingan" % fn)

# 📌📌 NFT yo'llari
for p_, sub in [("/nft", "nft"), ("/nftrent", "nft"),
                ("/nft-rent", "nft"), ("/rent", "nft")]:
    check("'%s': { tab: 'buy', sub: '%s' }" % (p_, sub) in ROUTES,
          "🗺️ %-11s -> Xarid + NFT" % p_)

# 📌📌 Botning eski `?tab=&sub=` havolalari BUZILMAYDI
check("queryToRoute(window.location.search)" in APP,
      "📌 botning `?tab=&sub=` havolalari qo'llab-quvvatlanadi")
check("url.searchParams.delete('tab')" in APP, "📌📌 `tab` marker tozalanadi")
check("url.searchParams.delete('sub')" in APP, "📌📌 `sub` marker tozalanadi")

# 📌📌 `tab` va `sub` turli darajada — aralashtirilmasin
check("setCurrentTab('nft')" not in APP,
      "📌📌📌 `tab=nft` YO'Q — faqat `sub=nft` (bo'sh ekna bo'lmasin)")
check("setInitialBuyCategory(route.sub)" in APP,
      "📌📌📌 route.sub -> NFT kichik tabi")

# BuyView `initialTab` ni qabul qilishi
check("initialTab = 'stars'" in BUY, "🟡 BuyView `initialTab` qabul qiladi")
check("useState<'stars' | 'premium' | 'gifts' | 'nft'>(initialTab)" in BUY,
      "🟡 `subTab` `initialTab` dan boshlanadi")

print()
if FAILS:
    print("NATIJA: ❌ MUAMMO BOR  (%d ta)" % len(FAILS))
    for f in FAILS:
        print("   • " + f)
    raise SystemExit(1)
print("NATIJA: ✅ BARCHASI TO'G'RI")