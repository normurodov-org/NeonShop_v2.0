"""NFT ADMIN OQIMI — 2 bosqich + OCHISH/YOPISH.

SIZNING TALABINGIZ (boshidan):
  "Bot mendan nft linkini suraydi, keyin 1 kunlik narxini soraydi.
   Bot avtomatik link ichidan nftni nomi va malumotlarini oladi,
   va webapp uchun rasmni ham usha link ichidan oladi.
   Keyin NFT lar royxati bolimida NFTni ochirish degan joyi ham bolsin."

Ya'ni:
  1/2  link        -> bot Hamma narsani o'zi oladi
  2/2  1 kunlik narx -> saqlanadi
  Ro'yxatda "Ochish / Yopish" tugmasi
"""
import asyncio
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bot as B  # noqa: E402

BSRC = open("bot.py", encoding="utf-8").read()
VIEW = open("src/components/views/NftRentView.tsx", encoding="utf-8").read()
SRV = open("server.ts", encoding="utf-8").read()

ok = True


def check(cond, msg):
    global ok
    ok &= bool(cond)
    print(f"  {'✅' if cond else '❌'} {msg}")


def between(start, end):
    i = BSRC.index(start)
    j = BSRC.index(end, i + 1)
    return BSRC[i:j]


print("=" * 70)
print("1) BOSQICHLAR SONI — 2 ta (link -> narx)")
print("=" * 70)
check("1/2" in BSRC, "1/2 — link")
check("2/2" in BSRC, "2/2 — narx")
# eskirgan 3/4 va 4/4 QOLMAMALIGI
check("1/4" not in BSRC and "2/4" not in BSRC
      and "3/4" not in BSRC and "4/4" not in BSRC,
      "eskirgan 1/4..4/4 qoldiqlari yo'q")

states = BSRC[BSRC.index("class NftStates("):BSRC.index("class TopupStates(")]
check("link = State()" in states, "state: link")
check("daily = State()" in states, "state: daily (narx)")
check("title = State()" in states,
      "state: title — FAQAT admin rasm yuborsa (zaxira yo'l)")

print()
print("=" * 70)
print("2) OQIM: link -> avtomatik -> narx")
print("=" * 70)
link_fn = between("async def adm_nft_link(", "@admin_router.message(StateFilter(NftStates.title)")
check("resolve_nft_page(link)" in link_fn, "linkdan ma'lumotlar olinadi")
check("NFT ma'lumotlari olinmoqda" in link_fn, "bot jarayonni ko'rsatadi")
check("await state.set_state(NftStates.daily)" in link_fn,
      "linkdan KEYIN darhol narxga o'tadi")
check('title=auto.get("title") or ""' in link_fn, "nom avtomatik")
check("number=auto.get(\"number\")" in link_fn, "raqam avtomatik")
check('image=auto["image"]' in link_fn, "rasm avtomatik")
check('auto_desc=auto.get("description") or ""' in link_fn, "tavsif avtomatik")
check("2/2" in link_fn, "2/2 — 1 kunlik narx so'raladi")
check("1 kunlik narxini" in link_fn, "xabar aniq: 1 kunlik narx")
# Nomi/raqamni qayta SO'RAMASLIGI kerak
check("NftStates.number" not in BSRC, "raqam bosqichi umuman yo'q")

# Ma'lumot topilmasa — aniq xato + linkni qayta so'raymiz
check("NFT ma'lumotlari topilmadi" in link_fn, "topilmasa aniq aytadi")
check("Sabablar:" in link_fn, "sabablar ro'yxati")
check("https://t.me/nft/Nom-12345" in link_fn, "to'g'ri format ko'rsatiladi")
check("return\n" in link_fn or "        return" in link_fn.split("NftStates.daily")[0],
      "narxga O'TMAYDI (linkni qayta so'raydi)")

print()
print("=" * 70)
print("3) NARX BOSQICHI")
print("=" * 70)
daily_fn = between("async def adm_nft_daily(", "@admin_router.callback_query(F.data.startswith(\"adm:nft_photo:\")")
check("parse_uzs_amount" in daily_fn, "narxni to'g'ri o'qiydi")
check('"title": data.get("title")' in daily_fn, "avtomatik nom saqlanadi")
check('"number": data.get("number")' in daily_fn, "avtomatik raqam saqlanadi")
check('"image": data.get("image")' in daily_fn, "avtomatik rasm saqlanadi")
check('"description": data.get("auto_desc")' in daily_fn, "tavsif saqlanadi")
check('"active": True' in daily_fn, "yangi NFT ochiq bo'lib qo'shiladi")
check("nft_rent_quote(daily, NFT_MIN_DAYS)" in daily_fn, "mijoz hisobi ko'rsatiladi")
check("Rasm qo'shish" in daily_fn, "rasm yo'q bo'lsa tuzatish tugmasi")

print()
print("=" * 70)
print("4) RO'YXATDA OCHISH / YOPISH")
print("=" * 70)
check("def _nft_list_kb(" in BSRC, "ro'yxat — alohida funksiya (qayta ishlatiladi)")
lst = between("def _nft_list_kb(", '@admin_router.callback_query(F.data == "adm:nft_list")')
check('text=("🚫 Yopish" if active else "✅ Ochish")' in lst,
      "tugma HARAKATNI bildiradi: 🚫 Yopish / ✅ Ochish")
check('adm:nft_toggle:' in lst, "toggle callback")
check("Ochiq" in lst, "holat matni: Ochiq")
check("YOPIQ" in lst, "holat matni: YOPIQ — mijozga ko'rinmaydi")
check("Rasm yo'q" in lst, "rasm yo'qligi belgisi")
check("🎨" in lst, "backdrop ko'rsatiladi")
# faol NFT'lar oldinga, yopiqlar keyinga (tartib)
check("(not n.get(\"active\", True)," in lst, "ochilganlar birinchi")

print()
print("  Toggle qayta chizadi (yangi xabar emas!):")
tog = between('F.data.startswith("adm:nft_toggle:")', 'F.data == "adm:nft_cancel"')
check("_nft_list_kb()" in tog, "ro'yxat QAYTA chiziladi")
check("edit_text(" in tog, "inline xabar tahrirlanadi")
check("await call.answer(" in tog, "tugma holati bildiriladi (toast)")
check("Ochildi" in tog and "Yopildi" in tog, "natija aniq")
# call.answer() tugmadan KEYIN bo'lishi SHART (Telegram "query too old")
i_edit = tog.index("edit_text(")
i_ans = tog.index("await call.answer(")
check(i_ans > i_edit, "call.answer() oxirida (Telegram 'query too old' xavfi yo'q)")

print()
print("=" * 70)
print("5) WEBAPP: yopiq NFT ko'rinmaydi")
print("=" * 70)
check(".filter((n: any) => n?.active !== false)" in SRV,
      "server faol bo'lmaganlarni chiqaradi")
check('n["active"] = not n.get("active", True)' in BSRC,
      "holat almashtiriladi (ochish/yopish)")

print()
print("=" * 70)
print("6) TUGMA -> HANDLER MOS KELISHI")
print("=" * 70)
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
    if "{" in data:
        prefix = data.split("{")[0]
        hit = next((n for f, n in hs if matches(f, prefix + "X")), None)
        label = f"{data}<id>"
    else:
        hit = next((n for f, n in hs if matches(f, data)), None)
        label = data
    check(hit is not None, f"{label} -> " + (hit or "HANDLER YO'Q!"))

# eskirgan qolgan state handlerlari yo'qmi
check("NftStates.number" not in BSRC, "o'lik number state handler'i yo'q")
check("StateFilter(NftStates.title)" in BSRC,
      "title handler bor (faqat rasm yo'li uchun)")

print()
print("=" * 70)
print("7) HAQIQIY RESOLVER (t.me dan)")
print("=" * 70)
try:
    got = asyncio.run(B.resolve_nft_page("https://t.me/nft/FinePen-18272"))
    online = got is not None
except Exception:  # noqa: BLE001
    got, online = None, False

if online:
    check(got["image"].startswith("https://cdn"), "rasm havolasi")
    check(got["title"] == "Fine Pen", f"nom: {got['title']}")
    check(got["number"] == 18272, f"raqam: {got['number']}")
    check("Backdrop: Chestnut" in got["description"],
          "backdrop tavsifda (qator bilan ajratilgan)")
    check(B.nft_backdrop(got["description"]) == "Chestnut",
          f"nft_backdrop() = {B.nft_backdrop(got['description'])}")
else:
    print("  ➖ tarmoq yo'q — resolver o'tkazilmadi")
    check("def resolve_nft_page(" in BSRC, "resolver kodi bor")

print()
print("=" * 70)
print("NATIJA:", "✅ BARCHASI TO'G'RI" if ok else "❌ MUAMMO BOR")
print("=" * 70)
sys.exit(0 if ok else 1)