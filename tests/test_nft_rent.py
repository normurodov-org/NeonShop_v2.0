"""NFT RENT — narx hisobi va admin qo'shish oqimi.

Rasmdagi talab:
  • Mijozga: per day, rent (N days), network fee 1 700, TOTAL
  • Muddat: 3–50 kun, tez tanlash 3/7/14/30
  • Bot admin panelida: "➕ NFT qo'shish" -> link -> 1 kunlik narx
    (nom/raqam/rasm linkdan AVTOMATIK olinadi)
  • WebApp NFT bo'limida faqat 1 kunlik narx + linkdan olingan rasm
"""
import asyncio
import re
import sys
import time

sys.path.insert(0, '.')
import bot as B  # noqa: E402

SRV = open("server.ts", encoding="utf-8").read()
BUY = open("src/components/views/BuyView.tsx", encoding="utf-8").read()
NFT_VIEW = open("src/components/views/NftRentView.tsx", encoding="utf-8").read()
B_SRC = open("bot.py", encoding="utf-8").read()

ok = True


def check(cond, msg):
    global ok
    ok &= bool(cond)
    print(f"  {'✅' if cond else '❌'} {msg}")


print("=" * 68)
print("1) HISOB — rasmga mos (Per day / Rent / Network fee / Total)")
print("=" * 68)
check(B.NFT_MIN_DAYS == 3, f"min muddat = {B.NFT_MIN_DAYS} kun")
check(B.NFT_MAX_DAYS == 50, f"max muddat = {B.NFT_MAX_DAYS} kun")
check(B.NFT_NETWORK_FEE == 1700, f"network fee = {B.NFT_NETWORK_FEE} UZS")
check(B.NFT_QUICK_DAYS == (3, 7, 14, 30), f"tez tanlash = {B.NFT_QUICK_DAYS}")

# Sizning talabingiz: network fee = 1 700 so'm.
# (1-rasmdagi "1 400" boshqa ilovaning qiymati — biz siznikini qo'llaymiz)
# 84 UZS/kun, 3 kun:  84×3 = 252  +  1 700  =  1 952
q = B.nft_rent_quote(84, 3)
print(f"      84 UZS × 3 kun: per_day={q['per_day']} rent={q['rent']} "
      f"fee={q['network_fee']} TOTAL={q['total']}")
check(q["per_day"] == 84, "Per day = 84")
check(q["rent"] == 252, "Rent (3 days) = 84 × 3 = 252")
check(q["network_fee"] == 1700, "Network fee = 1 700 (sizning talabingiz)")
check(q["total"] == 1952, "Total = Rent + Network fee = 1 952")
check(q["total"] == q["rent"] + q["network_fee"], "Total = Rent + Network fee")

q30 = B.nft_rent_quote(84, 30)
check(q30["rent"] == 84 * 30, "Rent (30 kun) = kunlik × 30 = 2 520")
check(q30["total"] == 84 * 30 + 1700, "Total = rent + fee")

print()
print("  Chegara tekshiruvi:")
check(B.nft_rent_quote(100, 1)["days"] == 3, "1 kun -> 3 ga chiqariladi")
check(B.nft_rent_quote(100, 999)["days"] == 50, "999 kun -> 50 ga tushiriladi")
check(B.nft_rent_quote(100, -5)["days"] == 3, "manfiy -> 3")
check(B.nft_rent_quote(None, 5)["per_day"] == 0, "narx yo'q -> 0 (xato emas)")
check(B.nft_rent_quote("84", 3)["total"] == 1952, "matn '84' ham ishlaydi")
check(B.nft_rent_quote("84 so'm", 3)["total"] == 1952, "'84 so'm' ham ishlaydi")
check(B.num("1 000") == 1000, "num('1 000') = 1000")
check(B.num("1 234,50") == 1234, "num('1 234,50') = 1234")
check(B.num("84.5") == 84, "num('84.5') = 84")
check(B.num("abc") == 0, "num('abc') = 0 (xato emas)")

print()
print("=" * 68)
print("2) server.ts — API va XUDDIY narx")
print("=" * 68)
check("const NFT_NETWORK_FEE = 1700;" in SRV, "network fee 1700")
check("const NFT_MIN_DAYS = 3;" in SRV and "const NFT_MAX_DAYS = 50;" in SRV,
      "3–50 kun")
check("function nftQuote(" in SRV, "nftQuote() bor")
check("app.get('/api/nfts'" in SRV, "/api/nfts ro'yxat")
check("app.get('/api/nfts/quote'" in SRV, "/api/nfts/quote hisob")
check("nfts: new Map<string, any>" in SRV, "store.nfts yaratildi")
check("['nfts', store.nfts]" in SRV, "merge ga qo'shildi (bot yozuvlari yo'qolmaydi)")

print()
print("=" * 68)
print("3) BOT ADMIN: NFT qo'shish (link -> nom -> raqam -> narx)")
print("=" * 68)
check('callback_data="adm:nft_add"' in B_SRC, "admin tugmasi bor")
for st in ("NftStates.link", "NftStates.daily"):
    check(st in B_SRC, f"state: {st}")
check("NftStates.number" not in B_SRC,
      "raqam bosqichi yo'q (linkdan avtomatik olinadi)")
check('F.data == "adm:nft_cancel"' in B_SRC,
      "bekor qilish alohida callback'da (mojarato'qnashuv yo'q)")
check("db.data.setdefault(\"nfts\", {})[nid] = item" in B_SRC,
      "NFT bazaga saqlanadi")
check('callback_data="adm:nft_list"' in B_SRC, "ro'yxat tugmasi")
check('adm:nft_toggle:' in B_SRC, "yoqish/ochish tugmasi")
# "nfts" JsonDB da e'lon qilingan
check('for key in ("users", "topups", "sales", "orders", "nfts")' in B_SRC,
      "JsonDB da nfts e'lon qilingan")

print()
print("=" * 68)
print("4) WEBAPP NFT BO'LIMI (1-rasm dizayni)")
print("=" * 68)
for frag, label in (
    ("Gifts", "tab: Gifts"),
    ("Usernames", "tab: Usernames"),
    ("My rentals", "tab: My rentals"),
    ("All collections", "filtr: All collections"),
    ("Cheapest first", "saralash: Cheapest first"),
    ("All backdrops", "backdrop filtrlari"),
    ("per day", "1 kunlik narx"),
    ("Term", "muddat"),
    ("Network fee", "network fee qatori"),
    ("Top up", "Top up tugmasi"),
):
    check(frag in NFT_VIEW, label)
check("Not enough" in NFT_VIEW or "not enough" in NFT_VIEW,
      "balance yetarli emasligi ko'rsatiladi")
check("grid-cols-2" in NFT_VIEW, "2 ustunli kartalar (rasmdagi kabi)")
check("aspect-square" in NFT_VIEW, "kvadrat rasm")
check("Heart" in NFT_VIEW, "yurakcha (tanlangan) tugmasi")
check("fetch('/api/nfts'" in NFT_VIEW, "ro'yxat serverdan olinadi")
check("/api/nfts/quote" in NFT_VIEW, "hisob serverdan olinadi")
check("NftRentView" in BUY, "BuyView ga ulangan")

print()
print("=" * 68)
print("5) TUGMA -> HANDLER MOS KELISHI")
print("=" * 68)
lines = B_SRC.split("\n")
hs = []
for i, l in enumerate(lines):
    m = re.match(r'@\w+\.callback_query\((.*)\)\s*$', l.strip())
    if m and i + 1 < len(lines):
        f = re.match(r'async def (\w+)', lines[i + 1].strip())
        if f:
            hs.append((m.group(1), f.group(1)))
seen = set()
for data in sorted(set(re.findall(r'callback_data="(adm:nft[^"]*)"', B_SRC))):
    prefix = data.split("{")[0]
    hit = next(
        (n for f, n in hs
         if (f'F.data == "{data}"' in f
             or (re.search(r'startswith\("([^"]+)"\)', f)
                 and data.startswith(re.search(r'startswith\("([^"]+)"\)', f).group(1))))),
        None,
    )
    check(hit is not None, f"{data} -> " + (hit or "HANDLER YO'Q!"))
    seen.add(data)
# takror handler bormi
for filt in ("adm:nft_add", "adm:nft_cancel"):
    n = sum(1 for f, _ in hs if f'F.data == "{filt}"' in f)
    check(n <= 1, f"{filt} faqat 1 ta handler bilan ({n})")

print()
print("=" * 68)
print("NATIJA:", "✅ BARCHASI TO'G'RI" if ok else "❌ MUAMMO BOR")
print("=" * 68)
sys.exit(0 if ok else 1)