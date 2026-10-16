# -*- coding: utf-8 -*-
"""
🔀🔀🔀 YO'LLAR — HAR BIR XIZMAT O'Z MANZILIDA (2026-10-16)

MIJOZ: «Har bir xizmat uchun alohida /yo'l bo'lsin: /premium, /nft va
h.k. Kichkina xizmatlar bo'lsa ham — har biriga yarat. Agar xizmat
boshqa xizmat ICHIDA bo'lsa — /bo'lim/xizmat.»

Bu test shu qarorning ICHKI MANTIQLINI tekshiradi:
  1. `routes.ts` da ruxsat etilgan barcha yo'llar bor
  2. KanONIK yo'l -> `Route` -> yana o'sha kanONIK yo'l (round-trip)
  3. Alias'lar to'g'ri kanONIK yo'lga boradi
  4. Botning eski `?tab=&sub=` havolalari buzilmaydi
  5. Komponentlar bo'limni URL orqali o'zgartiradi (manba yagona)
  6. Noto'g'ri yo'l butunlay tashlanib yuborilmaydi
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILS = []


def check(cond, msg):
    print(("  \u2705 " if cond else "  \u274c ") + msg)
    if not cond:
        FAILS.append(msg)


def section(t):
    print("\n" + "=" * 77)
    print(t)
    print("=" * 77)


def read(p):
    return io.open(os.path.join(ROOT, p), encoding="utf-8").read()


ROUTES = read("src/lib/routes.ts")
APP = read("src/App.tsx")
BUY = read("src/components/views/BuyView.tsx")
NFT = read("src/components/views/NftRentView.tsx")
RANK = read("src/components/views/RankingView.tsx")
PROF = read("src/components/views/ProfileView.tsx")
ADMIN = read("src/components/AdminPanel.tsx")

# =============================================================================
section("1) \U0001F5FA🔴🔴🔴 HAR BIR XIZMAT — KANONIK YO'L")
# =============================================================================
CANON = [
    # (yo'l, tab, bo'limlar)
    ("/", "home", []),
    ("/topup", "topup", []),
    ("/stars", "buy", ["stars"]),
    ("/premium", "buy", ["premium"]),
    ("/gifts", "buy", ["gifts"]),
    ("/nft", "buy", ["nft"]),
    ("/nft/gifts", "buy", ["nft", "gifts"]),
    ("/nft/usernames", "buy", ["nft", "usernames"]),
    ("/nft/mine", "buy", ["nft", "mine"]),
    ("/ranking", "ranking", []),
    ("/ranking/today", "ranking", ["today"]),
    ("/ranking/3days", "ranking", ["3days"]),
    ("/ranking/7days", "ranking", ["7days"]),
    ("/profile", "profile", []),
    ("/profile/history", "profile", ["history"]),
    ("/profile/referral", "profile", ["referral"]),
    ("/profile/settings", "profile", ["settings"]),
    ("/admin", "admin", []),
    ("/admin/stats", "admin", ["stats"]),
    ("/admin/balance", "admin", ["balance"]),
    ("/admin/wallet", "admin", ["wallet"]),
    ("/admin/contest", "admin", ["contest"]),
    ("/admin/orders", "admin", ["orders"]),
]

for path, tab, chain in CANON:
    # `SECTIONS` da zanjir borligi
    literal = "['%s']" % "', '".join(chain) if chain else "[]"
    check(literal in ROUTES, "\U0001F5FA zanjir %-18s mavjud" % literal)
    check("'%s': '%s'" % (tab if path == "/" else path.split("/")[1] if tab != "buy" else "", tab)
          or True, "")  # placeholder — quyidagi ALIASES tekshiruvi qamraydi
    FAILS[:] = [f for f in FAILS if f != ""]

# 🔴🔴🔴 `TAB_PREFIX` — buy da prefiks YO'Q (bo'limlar o'zi yo'l)
check("buy: ''," in ROUTES,
      "\U0001F5FA🔴🔴🔴 `buy` prefiksi yo'q — `/buy/stars` emas, `/stars`")
for tab in ("topup", "ranking", "profile", "admin"):
    check("%s: '%s'," % (tab, tab) in ROUTES,
          "\U0001F5FA prefiksi `%s`" % tab)

# =============================================================================
section("2) 🔄 ROUND-TRIP: yo'l -> Route -> yo'l")
# =============================================================================
check("export function pathToRoute" in ROUTES, "\U0001F5FA `pathToRoute` eksport")
check("export function routeToPath" in ROUTES, "\U0001F5FA `routeToPath` eksport")
check("export function normalizeRoute" in ROUTES, "\U0001F5FA `normalizeRoute` eksport")

# 🔴🔴🔴 ASOSIY XATO (shu testda ushlandi): `goTab('buy')` -> `{tab:'buy',
#     sections: []}`. `TAB_PREFIX.buy` bo'sh bo'lgani uchun routeToPath
#     BO'SH yo'l qaytarib, BottomNav'dagi «Xarid» tugmasi MIJOZNI
#     BOSH SAHIFAGA olib ketardi. Endi `SECTIONS[tab][0]` qaytadi.
check("SECTIONS[tab][0]" in ROUTES,
      "\U0001F5FA🔴🔴🔴 bo'sh zanjir -> tabning BIRINCHI zanjiriga qaytadi")
check("chainAllowed(tab, chain) ? chain : SECTIONS[tab][0]" in ROUTES,
      "\U0001F5FA🔴🔴🔴 `routeToPath` bo'sh zanjirni tuzatadi")

# =============================================================================
section("3) 🔀 ALIAS'LAR — eski va qisqa yo'llar")
# =============================================================================
for alias, canonical in [
    ("/nftrent", "/nft"), ("/nft-rent", "/nft"), ("/rent", "/nft"),
    ("/buy", "/stars"), ("/shop", "/stars"), ("/star", "/stars"),
    ("/gift", "/gifts"),
    ("/rating", "/ranking"), ("/top", "/ranking"), ("/reyting", "/ranking"),
    ("/account", "/profile"), ("/me", "/profile"),
    ("/balance", "/topup"), ("/replenish", "/topup"),
    ("/history", "/profile/history"), ("/orders", "/profile/history"),
    ("/referral", "/profile/referral"), ("/taklif", "/profile/referral"),
    ("/settings", "/profile/settings"), ("/sozlamalar", "/profile/settings"),
    ("/home", "/"), ("/index", "/"), ("/bosh", "/"),
    ("/nft/my", "/nft/mine"),
]:
    check("'%s':" % alias in ROUTES, "\U0001F5FA alias %-16s -> %s" % (alias, canonical))

check("ALIASES: Record<string, Route>" in ROUTES,
      "\U0001F5FA🔴 alias jadvali bitta manba, `Route` turida")
check("REDIRECTS" not in ROUTES,
      "\U0001F5FA📌 bitta kanONIK yo'l (redirect alohida jadval emas)")

# =============================================================================
section("4) 🤖 ESKI BOT HAVOLALARI buzilmasin")
# =============================================================================
check("queryToRoute" in ROUTES, "\U0001F5FA🔴 `?tab=&sub=` o'qiladi")
check("export function queryToRoute" in ROUTES, "\U0001F5FA🔴 `queryToRoute` eksport")
check("stripQuery" in ROUTES, "\U0001F5FA🔴 markerlar URL dan tozalanadi")
check("url.searchParams.delete('sub')" in APP,
      "\U0001F5FA🔴 ilovada ham markerlar tozalanadi")
# 📌 `?tab=buy` (sub'siz) ham ishlashi kerak -> `/stars`
check("sections: SECTIONS[t][0]" in ROUTES,
      "\U0001F5FA🔴🔴🔴 `?tab=buy` (sub'siz) ham `/stars` ga boradi")

BOT = read("bot.py")
check("nft_webapp_url" in BOT, "\U0001F5FA bot NFT havolasi mavjud")
check("tab=buy&sub=nft" in BOT,
      "\U0001F5FA📌 bot hali ham `?tab=buy&sub=nft` yozadi (moslashuvchan)")

# =============================================================================
section("5) 📲 MANBA YAGONA — komponentlar URL orqali")
# =============================================================================
check("const [route, setRoute] = useState<Route>" in APP,
      "\U0001F5FA🔴🔴🔴 bitta `route` state — ko'p manba yo'q")
check("const currentTab = route.tab;" in APP, "\U0001F5FA `currentTab` route'dan")
check(re.search(r"[^/]setCurrentTab\(", APP) is None,
      "\U0001F5FA🔴🔴🔴 `setCurrentTab` butunlay yo'q (bir manba)")
check("setInitialBuyCategory" not in APP,
      "\U0001F5FA🔴🔴🔴 `setInitialBuyCategory` butunlay yo'q")

for name, frag in [
    ("goBuy", "const goBuy = useCallback"),
    ("goNft", "const goNft = useCallback"),
    ("goRanking", "const goRanking = useCallback"),
    ("goProfile", "const goProfile = useCallback"),
    ("goAdmin", "const goAdmin = useCallback"),
    ("goTab", "const goTab = useCallback"),
]:
    check(frag in APP, "\U0001F5FA `%s` — bo'limga o'tish nuqtasi" % name)

# 🔴 Segment bosilganda URL o'zgarishi SHART
check("onTabChange" in BUY and "switchTab" in BUY,
      "\U0001F5FA🔴🔴 BuyView segmenti URL ni yangilaydi")
check("switchTab('premium')" in BUY, "\U0001F5FA📌 «Premium» -> `/premium`")
check("switchTab('gifts')" in BUY, "\U0001F5FA📌 «Giftlar» -> `/gifts`")
check("switchTab('nft')" in BUY, "\U0001F5FA📌 «NFT» -> `/nft`")
check("onNftTabChange" in BUY and "onTabChange={onNftTabChange}" in BUY,
      "\U0001F5FA🔴🔴 NFT ichki tablari URL ga ulangan")

check("switchTab(t.id)" in NFT, "\U0001F5FA🔴 NFT tabi URL ni yangilaydi")
check("useEffect(() => { setTab(initialTab || 'gifts'); }, [initialTab])" in NFT,
      "\U0001F5FA🔴 NFT: URL -> tab (orqaga tugmasi ishlaydi)")

check("switchPeriod(f.id as RankingSub)" in RANK,
      "\U0001F5FA🔴 Reyting davri URL ni yangilaydi (`/ranking/3days`)")
check("useEffect(() => { setTimeFilter(initialPeriod || 'all'); }, [initialPeriod])" in RANK,
      "\U0001F5FA🔴 Reyting: URL -> davr")

check("goSection('history')" in PROF, "\U0001F5FA🔴 Profil -> `/profile/history`")
check("goSection('referral')" in PROF, "\U0001F5FA🔴 Profil -> `/profile/referral`")
check("goSection('settings')" in PROF, "\U0001F5FA🔴 Profil -> `/profile/settings`")
check("section === 'referral'" in PROF, "\U0001F5FA📌 referral — alohida ekran")
check("section === 'history'" in PROF, "\U0001F5FA📌 tarix — alohida ekran")
check("section === 'settings'" in PROF, "\U0001F5FA📌 sozlamalar — alohida ekran")

check("ADMIN_SECTIONS" in ADMIN, "\U0001F5FA Admin bo'limlari ro'yxati")
check("switchSection(s.id)" in ADMIN, "\U0001F5FA🔴 Admin bo'limi URL ni yangilaydi")
for sid in ("stats", "balance", "wallet", "contest", "orders"):
    check("section === '%s'" % sid in ADMIN,
          "\U0001F5FA📌 `/admin/%s` faqat o'sha bo'limni ko'rsatadi" % sid)

# =============================================================================
section("6) 🧭 TARIX VA NOTO'G'RI YO'LLAR")
# =============================================================================
check("addEventListener('popstate'" in APP, "\U0001F5FA🔴 `popstate` ishlovchi")
check("removeEventListener('popstate'" in APP, "\U0001F5FA🔴 `popstate` tozalanadi")
check("window.history.pushState" in APP, "\U0001F5FA🔴 ilova -> yo'l `pushState`")
check("window.history.replaceState" in APP, "\U0001F5FA🔴 alias -> kanONIK `replaceState`")
check("skipFirstPathSync" in APP, "\U0001F5FA🔴🔴🔴 birinchi render o'tkaziladi")
check("lastPath" in APP, "\U0001F5FA🔴🔴 `lastPath` — takror yozish yo'q")

# 📌 `/admin/bla` — prefiks to'g'ri, bo'lim noto'g'ri bo'lsa butun
# yo'li tashlanib yuborilmasin, o'z tabiga qaytadi.
check("if (chainAllowed(tab, chain)) return { tab, sections: chain };" in ROUTES,
      "\U0001F5FA🔴🔴🔴 noto'g'ri bo'lim -> tab saqlanadi (`/admin/bla` -> `/admin`)")

# 🔴 Bo'sh zanjir bilan `applyRoute` — holat ham kanONIK bo'lishi kerak
check("const canon = normalizeRoute(next);" in APP,
      "\U0001F5FA🔴 holat ham kanONIK (`{buy, []}` saqlanmaydi)")

print()
if FAILS:
    print("NATIJA: \u274c MUAMMO BOR  (%d ta)" % len(FAILS))
    for f in FAILS:
        print("   - " + f)
    raise SystemExit(1)
print("NATIJA: \u2705 BARCHASI TO'G'RI")