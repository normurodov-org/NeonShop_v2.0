# -*- coding: utf-8 -*-
"""NFT NETWORK FEE — uchta manba BIR XIL bo'lishi shart.

🔴 NIMA UCHUN BU TEST?
   Network fee uchta joyda yozilgan edi:
       bot.py            NFT_NETWORK_FEE
       server.ts         NFT_NETWORK_FEE
       NftRentView.tsx   qat'iy son (useState(1700))
   Ular farqlansa, mijoz WebApp'da bitta narxni, bot xabarida
   boshqasini ko'radi — va umr oxirida chalkashlik chiqadi.

   Shu sababli:
     1) hammasi bitta qiymatga keltirildi,
     2) `NftRentView` da qat'iy son o'rniga `DEFAULT_NETWORK_FEE`
        nomli o'zgaruvchi qo'ydi (server ustidan yozadi),
     3) bu test har bir deploy'da mosligini tekshiradi.
"""
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


def strip_comments(src, kind="//"):
    """JS/TS blok (/* */) va qator (//) izohlarini olib tashlaydi."""
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    return re.sub(r"//[^\n]*", " ", src)


def strip_py_comments(src):
    return re.sub(r"#[^\n]*", " ", src)


BOT = read("bot.py")
SRV = read("server.ts")
NFTV = read("src/components/views/NftRentView.tsx")

# 🔴 Izohlardagi raqamlar hisobga OLINMAS — aks holda bu izohning
#    o'zigi testni qizil qilardi («eskirgan 1700 yozilgani» uchun).
BOT_C = strip_py_comments(BOT)
SRV_C = strip_comments(SRV)
NFTV_C = strip_comments(NFTV)

# =============================================================================
section("1) 🌐 NETWORK FEE — UCHTA MANBA")
# =============================================================================


def py_val(src, name):
    m = re.search(r"^%s\s*=\s*(\d+)" % name, src, re.M)
    return int(m.group(1)) if m else None


def ts_val(src, name):
    m = re.search(r"^(?:const|export const)\s+%s\s*[:=]\s*(\d+)" % name, src, re.M)
    return int(m.group(1)) if m else None


rows = [
    ("bot.py — NFT_NETWORK_FEE", py_val(BOT_C, "NFT_NETWORK_FEE")),
    ("server.ts — NFT_NETWORK_FEE", ts_val(SRV_C, "NFT_NETWORK_FEE")),
    ("NftRentView.tsx — DEFAULT_NETWORK_FEE",
     ts_val(NFTV_C, "DEFAULT_NETWORK_FEE")),
]
for label, v in rows:
    print("     %-38s = %s" % (label, v))

vals = [v for _, v in rows]
check(None not in vals, "🔴🔴🔴 uchta manba HAM topildi")
if None not in vals:
    check(len(set(vals)) == 1,
          "🔴🔴🔴 uchta manba BIR XIL (%s)" % vals[0])
    check(vals[0] == 2000, "🔴🔴 qiymat 2 000 so'm")

# =============================================================================
section("2) 🔒 QAT'IY SON QOLMAMASIN (faqat nomli o'zgaruvchi)")
# =============================================================================
check("DEFAULT_NETWORK_FEE" in NFTV_C,
      "🔴 `DEFAULT_NETWORK_FEE` nomli o'zgaruvchi bor")
check("useState(DEFAULT_NETWORK_FEE)" in NFTV_C,
      "🔴🔴 `useState` dan foydalaniladi (qat'iy son emas)")
check("d.network_fee ?? DEFAULT_NETWORK_FEE" in NFTV_C,
      "🔴🔴 server javobi ustidan yozadi (`??` bilan)")

# 🔴 Eskirgan 1700 KODDA qolmashi kerak
for bad in ("useState(1700)", "?? 1700", "setNetworkFee(1700)", "= 1700"):
    check(bad not in NFTV_C, "🔴 kodda `%s` yo'q" % bad)

# =============================================================================
section("3) 📐 BOSHQA NFT KONSTANTLALARI HAM MOS BO\u02bcLSIN")
# =============================================================================
# 🔴 Bular ham ikki marta yozilgan — farqlansa muddat/to'lov chalkashadi
for name, want in (("NFT_MIN_DAYS", 3), ("NFT_MAX_DAYS", 50)):
    a, b = py_val(BOT_C, name), ts_val(SRV_C, name)
    print("     %-16s bot.py=%-4s server.ts=%-4s" % (name, a, b))
    check(a == b, "🔴🔴 %s ikkala tomonda bir xil" % name)
    check(a == want, "🔴 %s = %s" % (name, want))

quick_py = re.search(r"^NFT_QUICK_DAYS\s*=\s*\(([^)]*)\)", BOT_C, re.M)
quick_ts = re.search(r"^const NFT_QUICK_DAYS\s*=\s*\[([^\]]*)\]", SRV_C, re.M)
if quick_py and quick_ts:
    p_days = [x.strip() for x in quick_py.group(1).split(",") if x.strip()]
    t_days = [x.strip() for x in quick_ts.group(1).split(",") if x.strip()]
    check(p_days == t_days, "🔴🔴 `NFT_QUICK_DAYS` bir xil (%s)" % p_days)

# =============================================================================
section("4) 🔗 FEE NERDAN KO\u02bcRSATILADI (uzluksizlik)")
# =============================================================================
# 🔴 Network fee alohida qatorda ko\u02brsatilishi va JAMIga QO\u02bcSHILMASLIGI
#    kerak — aks holda mijoz ikki marta to'laydi.
check("NFT_NETWORK_FEE" in BOT, "🔴 bot.py fee ni ishlatadi")
check("network_fee" in SRV_C, "🔴 server /api/nfts da `network_fee` qaytaradi")
check("rent + NFT_NETWORK_FEE" in BOT, "🔴 bot.py: total = rent + fee")
check("rent + NFT_NETWORK_FEE" in SRV, "🔴 server: total = rent + fee")
check("Network fee" in BOT, "🔴 bot xabarida fee alohida yoziladi")

print()
if FAILS:
    print("NATIJA: ❌ MUAMMO BOR  (%d ta)" % len(FAILS))
    for f in FAILS:
        print("   • " + f)
    raise SystemExit(1)
print("NATIJA: ✅ BARCHASI TO'G'RI")