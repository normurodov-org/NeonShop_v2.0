"""NFT RASMI — admin qo'shgandan KEYIN WebApp'da ko'rinishi.

MUAMMO (xabar berilgan): "/admin orqali nft qo'shdim. Lekin WebAppda
ko'rinmayapti rasmi bilan."

Sabablari:
  1) server.ts `store.nfts` faqat BOOT da o'qiladi. Admin keyin NFT
     qo'shsa, server eski (bo'sh) ro'yxatni qaytarib berardi.
     -> `refreshNftsFromDisk()`
  2) Admin RASM yuborsa `image` = Telegram `file_id`. `<img src="AgACAgIAA...">`
     hech qachon rasm ko'rsatmaydi — brauzer undan URL tushunmaydi.
     -> `/api/nft-image/:id` proxy (302 -> Telegram CDN)
  3) WebApp faqat `^https?://` ni tekshirardi, proxy yo'lni
     (`/api/nft-image/...`) YASHIRDI.
     -> `isImageUrl()`
"""
import re
import sys

sys.path.insert(0, '.')
import bot as B  # noqa: E402

SRV = open("server.ts", encoding="utf-8").read()
VIEW = open("src/components/views/NftRentView.tsx", encoding="utf-8").read()

ok = True


def check(cond, msg):
    global ok
    ok &= bool(cond)
    print(f"  {'✅' if cond else '❌'} {msg}")


print("=" * 68)
print("1) SERVER: diskdan yangilanish (admin qo'shgan NFT ko'rinadi)")
print("=" * 68)
check("export function refreshNftsFromDisk()" in SRV, "refreshNftsFromDisk() bor")
check("store.nfts = new Map<string, any>(Object.entries(fresh.nfts || {}))" in SRV,
      "diskdagi nfts store.nfts ga singdiriladi")
check("fs.statSync(DB_FILE).mtimeMs" in SRV,
      "mtime orqali tekshiriladi (har so'rovda o'qilmaydi)")
check("const NFT_SCAN_MS = 3000;" in SRV, "3 soniyada bir — og'ir emas")

# HAR BIR NFT o'quvchi endpointda chaqirilishi SHART
print()
print("  Chaqirilgan endpointlar:")
for ep in ("'/api/nfts'", "'/api/nfts/quote'", "'/api/nfts/rent'", "'/api/nft-image/:id'"):
    i = SRV.find("app.get(" + ep)
    if i < 0:
        i = SRV.find("app.post(" + ep)
    seg = SRV[i:i + 400] if i >= 0 else ""
    check("refreshNftsFromDisk()" in seg, f"{ep} chaqiradi")

print()
print("=" * 68)
print("2) SERVER: rasm proxy (Telegram file_id -> 302)")
print("=" * 68)
check("function isTelegramFileId(" in SRV, "file_id aniqlanadi")
check("function nftImageUrl(" in SRV, "nftImageUrl()")
check("app.get('/api/nft-image/:id'" in SRV, "proxy endpoint")
check("getFile?file_id=" in SRV, "Bot API getFile chaqiriladi")
check("res.redirect(302, url)" in SRV, "302 -> Telegram CDN")
check("const FILE_URL_TTL = 30 * 60 * 1000;" in SRV,
      "havola 30 daqiqa keshlanadi (Telegram ~1 soat beradi)")

print()
print("  file_id va havola farqlanadi:")
fn = SRV[SRV.index("function isTelegramFileId("):SRV.index("function nftPublicList(")]
check("^[A-Za-z0-9_-]{20,}$" in fn, "file_id: base64url, 20+ belgi")
check("/[\\/\\s]/" in fn, "havola (t.me/nft/...) file_id DEGIL deb rad qilinadi")

print()
print("  nftImageUrl qoidalari:")
fn2 = SRV[SRV.index("function nftImageUrl("):SRV.index("function nftPublicList(")]
check("return isTelegramPageUrl(raw) ? '' : raw;" in fn2,
      "http(s) -> to'g'ridan-to'g'ri (t.me sahifalari bundan tashqarida)")
check("/api/nft-image/" in fn2, "file_id -> proxy yo'l")
check("return '';" in fn2, "t.me linki -> bo'sh (placeholder ko'rsatiladi)")

print()
print("=" * 68)
print("3) WEBAPP: proxy rasmni YASHIRMASIN")
print("=" * 68)
check("const isImageUrl = " in VIEW, "isImageUrl() yordamchisi")
check("v.startsWith('/')" in VIEW, "nisbiy yo'l (/api/nft-image/...) qabul qilinadi")
check("/^https?:\\/\\//i.test(v)" in VIEW, "to'g'ridan-to'g'ri havolа ham")
# Endi rasm alohida NftImage komponentida — u ichida ishlaydi
check("const NftImage" in VIEW, "NftImage komponenti")
check(VIEW.count("<NftImage") >= 2, "kartada VA modalda ishlatiladi")
check("isImageUrl(src)" in VIEW, "isImageUrl komponent ichida qo'llanadi")
# eski xato qolmaganligini tekshiramiz
check("/^https?:\\/\\//i.test(n.image)" not in VIEW,
      "eski `^https?://` tekshiruvi QOLMAGAN (proxy ni yashirardi)")

print()
print("=" * 68)
print("4) ADMIN: rasm biriktirish + ogohlantirish")
print("=" * 68)
BSRC = open("bot.py", encoding="utf-8").read()
check("def nft_has_viewable_image(" in BSRC, "nft_has_viewable_image()")
check('F.data.startswith("adm:nft_photo:")' in BSRC, "rasm so'rash handleri")
check("NftStates.photo" in BSRC, "photo state")
check('n["image"] = message.photo[-1].file_id' in BSRC, "file_id saqlanadi")
check('adm:nft_photo:{nid}' in BSRC or 'adm:nft_photo:{n.get(' in BSRC,
      "\"🖼 Rasm qo'shish\" tugmasi")
check("Rasm biriktirilmagan" in BSRC, "rasm yo'q bo'lsa ogohlantiriladi")
check("Rasm yo'q" in BSRC, "ro'yxatda 🚫 Rasm yo'q belgisi")
check('db.save()' in BSRC, "o'zgarish bazaga yoziladi")

print()
print("  Rasm turini to'g'ri talqin qilamiz:")
cases = [
    ({"image": "https://x.com/a.jpg"}, True, "https havolа -> ko'rinadi"),
    ({"image": ""}, False, "bo'sh -> ko'rinmaydi"),
    ({"image": "t.me/nft/abc"}, False, "t.me sahifasi -> rasm EMAS"),
    ({"image": "AgACAgIAAxkBAAIBu0Lk3Rt5gq7Zq0Zq0Zq0Zq0"}, True, "file_id -> proxy -> ko'rinadi"),
    ({"image": "short"}, False, "qisqa matn -> file_id emas"),
]
for item, expected, label in cases:
    got = B.nft_has_viewable_image(item)
    check(got == expected, f"{label} (natija: {got})")

print()
print("=" * 68)
print("5) TUGMA -> HANDLER MOS KELISHI")
print("=" * 68)
lines = BSRC.split("\n")
hs = []
for i, l in enumerate(lines):
    m = re.match(r"@\w+\.callback_query\((.*)\)\s*$", l.strip())
    if m and i + 1 < len(lines):
        f = re.match(r"async def (\w+)", lines[i + 1].strip())
        if f:
            hs.append((m.group(1), f.group(1)))


def matches(filt, data):
    if f'F.data == "{data}"' in filt:
        return True
    m = re.search(r'startswith\("([^"]+)"\)', filt)
    return bool(m and data.startswith(m.group(1)))


for data in sorted(set(re.findall(r'callback_data="(adm:nft[^"]*)"', BSRC))):
    if "{" in data:  # f-string shabloni
        prefix = data.split("{")[0]
        hit = next((n for f, n in hs if matches(f, prefix + "X")), None)
        label = f"{data}<id>"
    else:
        hit = next((n for f, n in hs if matches(f, data)), None)
        label = data
    check(hit is not None, f"{label} -> " + (hit or "HANDLER YO'Q!"))

# photo state ga handler borligi
check("StateFilter(NftStates.photo), F.photo" in BSRC, "rasm state handleri")

print()
print("=" * 68)
print("6) TDZ XAVFI (server krashi — ilgari 2 marta bo'lgan)")
print("=" * 68)
# clone() const bilan e'lon qilingan — refresh funksiyasi undan
# KO'PROQ oldin turmasligi kerak (lekin chaqirilishi so'rovda bo'ladi)
i_clone = SRV.index("const clone = <T,>")
i_refresh = SRV.index("export function refreshNftsFromDisk")
check(i_clone < i_refresh, "clone() refresh dan OLDIN e'lon qilingan (TDZ yo'q)")
i_store = SRV.index("export const store = {")
check(i_store < i_refresh, "store refresh dan OLDIN e'lon qilingan (TDZ yo'q)")
# chaqirish faqat so'rov ichida (modul yuklanganda emas)
for ep in ("'/api/nfts'", "'/api/nfts/quote'", "'/api/nfts/rent'", "'/api/nft-image/:id'"):
    i = SRV.find("app.get(" + ep)
    if i < 0:
        i = SRV.find("app.post(" + ep)
    check("refreshNftsFromDisk()" in SRV[i:i + 400] if i >= 0 else False,
          f"{ep} — faqat so'rovda chaqiriladi")

print()
print("=" * 68)
print("NATIJA:", "✅ BARCHASI TO'G'RI" if ok else "❌ MUAMMO BOR")
print("=" * 68)
sys.exit(0 if ok else 1)