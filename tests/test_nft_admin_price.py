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
notice = BOT[BOT.index("def nft_notice("):BOT.index("def nft_webapp_url(")]
check("nft_webapp_url()" in nft_start, "🔴🔴🔴 `nft_start` WebApp tugmasidan foydalanadi")
check("web_app=WebAppInfo" in nft_start, "🔴🔴🔴 `WebAppInfo` — haqiqiy Web App tugmasi")
check("NFT ijaraga olish (Web App)" in nft_start, "🔴 tugma matni")
# 🔴🔴🔴 2026-10-16 (mijoz so'ragan): NFT xizmatidan «Rasmiy kanal»
#    butunlay olib tashlandi — ham tugma, ham xabar matni.
#
# 📌 DIQQAT: tekshiruv IZOHLARGA tegilmasligi kerak — aks holda
#    «bu nima uchun olib tashlandi» izohi «hali bor» deb o'qiladi.
#    Shuning uchun koddan `#` qatorlari va `"""..."""` bloklari olib
#    tashlanadi, faqat HAQIQIY kod qoladi.
def _code_only(src: str) -> str:
    out, in_doc = [], False
    for ln in src.split("\n"):
        t = ln.strip()
        if t.startswith('"""') or t.startswith('r"""'):
            if t.count('"""') == 1:
                in_doc = not in_doc
            continue
        if in_doc or t.startswith("#"):
            continue
        out.append(re.sub(r'#.*$', '', ln))
    return "\n".join(out)

NFT_CODE = _code_only(nft_start)
NOTICE_CODE = _code_only(notice)

check("NFT_CHANNEL" not in NFT_CODE,
      "🔴🔴🔴 `NFT_CHANNEL` butunlay yo'q (o'zgaruvchi ham, tugma ham)")
check("kanalini ochish" not in NFT_CODE,
      "🔴🔴🔴 «🔗 ... kanalini ochish» tugmasi olib tashlandi")
check("https://t.me/" not in NFT_CODE,
      "🔴🔴🔴 NFT ekranida tashqi kanal havolasi QOLMADI")

# 🔴🔴🔴 «🎁 Rasmiy kanal: ...» matni ham kadrda bo'lmasin
check("Rasmiy kanal" not in NOTICE_CODE,
      "🔴🔴🔴 «🎁 Rasmiy kanal» matni olib tashlandi")
check("NFT_CHANNEL" not in NOTICE_CODE, "🔴🔴🔴 ogohlantirishda kanal yo'q")
# 📌 Menedjer ogohlantirishi QOLADI — tasdiqlash uchun kerak
check("NFT_MANAGER" in NOTICE_CODE,
      "📌📌📌 menejer ogohlantirishi saqlanib qolgan")

# WebApp tugmasi BIRINCHI bo'lishi kerak
check(NFT_CODE.index("nft_webapp_url()") < NFT_CODE.index('callback_data="m:buy"'),
      "🔴🔴🔴 WebApp tugmasi birinchi, «Orqaga» ikkinchi")

# =============================================================================
section("2b) 🔴🔴🔴 «ORQAGA» YANGI XABAR YUBORMAYDI")
# =============================================================================
# MIJOZ: «1-xabardagi orqaga tugmasini bosganimda 2-xabar junatilyapti.»
check("async def edit_or_answer(" in BOT,
      "🔴🔴🔴 `edit_or_answer` yordamchisi bor")
check("await message.edit_text(text, reply_markup=markup)" in BOT,
      "🔴🔴🔴 avval xabar O'ZIGA tahrirlanadi")
check("await message.answer(text, reply_markup=markup)" in BOT,
      "🔴🔴🔴 tahrirlab bo'lmasa — yangi xabar (zaxira)")
# 📌 `nft_start` va `buy_start` — `answer` EMAS, `edit_or_answer`
check("await edit_or_answer(" in nft_start,
      "🔴🔴🔴 `nft_start` yangi xabar YUBORMAYDI")
check("await message.answer(" not in _code_only(nft_start),
      "🔴🔴🔴 `nft_start` da `message.answer` QOLMADI")
buy_start = BOT.split("async def buy_start", 1)[1][:1200].split("\n\n@router", 1)[0]
check("await edit_or_answer(" in buy_start,
      "🔴🔴🔴 `buy_start` yangi xabar YUBORMAYDI")
check("await message.answer(" not in _code_only(buy_start),
      "🔴🔴🔴 `buy_start` da `message.answer` QOLMADI")

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
# 🔴 2026-10-16: `Route` endi `{ tab, sub }` emas, `{ tab, sections[] }`.
#    `/nft` — kanonik, qolganlari alias (bitta manba: `ALIASES`).
check("['nft']," in ROUTES, "🗺️ /nft — Xarid + NFT (kanonik zanjir)")
for p_ in ("/nftrent", "/nft-rent", "/rent"):
    check("'%s': { tab: 'buy', sections: ['nft'] }" % p_ in ROUTES,
          "🗺️ %-11s -> /nft (alias)" % p_)
# 📌 NFT ichki tabi ham o'z yo'lida
check("['nft', 'gifts']," in ROUTES, "🗺️ /nft/gifts — NFT ichidagi 'Gifts'")
check("['nft', 'usernames']," in ROUTES, "🗺️ /nft/usernames")
check("['nft', 'mine']," in ROUTES, "🗺️ /nft/mine")

# 📌📌 Botning eski `?tab=&sub=` havolalari BUZILMAYDI
check("queryToRoute(window.location.search)" in APP,
      "📌 botning `?tab=&sub=` havolalari qo'llab-quvvatlanadi")
check("url.searchParams.delete('tab')" in APP, "📌📌 `tab` marker tozalanadi")
check("url.searchParams.delete('sub')" in APP, "📌📌 `sub` marker tozalanadi")

# 📌📌 `tab` va `sections` turli darajada — aralashtirilmasin
check("setCurrentTab('nft')" not in APP,
      "📌📌📌 `tab=nft` YO'Q — faqat `sections=['nft']` (bo'sh ekna bo'lmasin)")
check("buySectionOf(route)" in APP,
      "📌📌📌 route.sections -> NFT kichik tabi")
check("nftSectionOf(route)" in APP,
      "📌📌📌 NFT ichki tabi ham URL dan (`/nft/usernames`)")

# BuyView `initialTab` ni qabul qilishi
check("initialTab = 'stars'" in BUY, "🟡 BuyView `initialTab` qabul qiladi")
check("useState<BuySub>(initialTab)" in BUY,
      "🟡 `subTab` `initialTab` dan boshlanadi")

print()
if FAILS:
    print("NATIJA: ❌ MUAMMO BOR  (%d ta)" % len(FAILS))
    for f in FAILS:
        print("   • " + f)
    raise SystemExit(1)
print("NATIJA: ✅ BARCHASI TO'G'RI")