"""1) USERBOT parse_mode — enum emas STRING kerak
2) HomeView NFT karta — kanal emas, ilova ichidagi NFT bo'limi

XABAR (admin paneldan kelgan xato):
    "⚠️ NFT xabari yuborilmadi
     🔍 Invalid parse mode "ParseMode.HTML""

🔴 SABAB: aiogram'ning `ParseMode.HTML` — bu ENUM. Uni pyrofork
(userbot) ga berilsa, Telegram javob beradi:
    Invalid parse mode "ParseMode.HTML"
va xabar UMUMAN yuborilmaydi. Aiogram enumni qabul qiladi (u
ichida `.value` bor), pyrofork esa qat'iy `str` kutadi.

Ikkinchi xabar:
    "webapp asosiy sahifasidagi NFT Rent tugmani kanalni ochadigan
     emas balki NFT rent xizmatiga yunatirishing kerak"

Avval karta `<a href="https://t.me/rentnftlarr">` edi — ya'ni mijoz
WebApp'dan chiqib kanalga ketardi va NFT xizmatini KO'RA OLMAYDI.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BSRC = open(f"{ROOT}/bot.py", encoding="utf-8").read()
HOME = open(f"{ROOT}/src/components/views/HomeView.tsx", encoding="utf-8").read()
APP = open(f"{ROOT}/src/App.tsx", encoding="utf-8").read()
BUY = open(f"{ROOT}/src/components/views/BuyView.tsx", encoding="utf-8").read()

ok = True


def check(cond, msg):
    global ok
    ok &= bool(cond)
    print(f"  {'✅' if cond else '❌'} {msg}")


def strip_comments(text: str) -> str:
    text = re.sub(r'"""..*?"""', '""', text, flags=re.S)
    text = re.sub(r"'''..*?'''", "''", text, flags=re.S)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//[^\n]*", "", text)
    return text


CODE = strip_comments(BSRC)

print("=" * 70)
print("1) 🔴 USERBOT parse_mode — STRING, enum EMAS")
print("=" * 70)
check('UB_PARSE_HTML = "html"' in CODE,
      "UB_PARSE_HTML = \"html\" konstantasi")

# 🔴 userbot chaqiruvlarida enum bo'lmasin
ub_calls = re.findall(r"(?:userbot|ub)\.(?:send_message|edit_message_text)\([^)]*\)",
                      CODE, flags=re.S)
check(len(ub_calls) >= 2, f"userbot chaqiruvlari topildi ({len(ub_calls)})")
bad = [c for c in ub_calls if "parse_mode=ParseMode" in c]
check(not bad,
      f"🔴 userbot hech qayerda parse_mode=ParseMode olmaydi ({len(bad)} ta xato)")

# aniq: NFT funksiyalari
send_fn = BSRC[BSRC.index("async def send_nft_notify_via_userbot("):
               BSRC.index("async def nft_notify_worker(")]
check("parse_mode=UB_PARSE_HTML" in strip_comments(send_fn),
      "send_nft_notify_via_userbot -> UB_PARSE_HTML")

patch_fn = BSRC[BSRC.index("async def _patch_nft_notices("):
                BSRC.index("def _refund_nft_order(")]
ub_edit = patch_fn[patch_fn.index("if n.get(\"via\") == \"ub\""):
                   patch_fn.index("else:")]
check("parse_mode=UB_PARSE_HTML" in strip_comments(ub_edit),
      "userbot.edit_message_text -> UB_PARSE_HTML")
# bot (aiogram) da esa enum TO'G'RI
check("await bot.edit_message_text(" in patch_fn, "bot.edit_message_text (aiogram)")
bot_edit = patch_fn[patch_fn.index("else:"):]
check("parse_mode=ParseMode.HTML" in bot_edit,
      "🔴 bot uchun enum TO'G'RI (aiogram qabul qiladi)")

print()
print("  Nima uchun enum ishlamaydi:")
print("      aiogram  ParseMode.HTML  -> .value = 'HTML'  (qabul qiladi)")
print("      pyrofork enum obyekti      -> str emas         (RAD)")
print('      Telegram: Invalid parse mode "ParseMode.HTML"')

print()
print("=" * 70)
print("2) 🏠 HOMEVIEW NFT KARTA — kanal emas, NFT bo'limi")
print("=" * 70)
card = HOME[HOME.index("NFT Rent Card"):HOME.index("</button>",
                                                 HOME.index("NFT Rent Card"))]
check("<a" not in card.split(">")[0] + ">",
      "🔴 <a href> emas — <button> bilan almashtirildi")
check('href="https://t.me/rentnftlarr"' not in HOME,
      "🔴 rentnftlarr havolasi butunlay olib tashlandi")
check("onClick={() => onGoToBuy('nft')}" in card,
      "bosilganda NFT bo'limiga olib boradi")
check("@rentnftlarr" not in strip_comments(HOME),
      "kanal nomi ko'rsatilmaydi")
check("3-50 kun" in card, "chip endi muddatni ko'rsatadi (3-50 kun)")
check("onGoToBuy: (initialCategory?: 'stars' | 'premium' | 'gifts' | 'nft') => void;" in HOME,
      "HomeView prop'ida 'nft' qo'shildi")

print()
print("=" * 70)
print("3) ZANJIR ULANISHI — Asosiy → NFT bo'limi")
print("=" * 70)
check("useState<'stars' | 'premium' | 'gifts' | 'nft'>('stars')" in APP,
      "App: initialBuyCategory 'nft' ni qabul qiladi")
check("initialTab={initialBuyCategory}" in APP, "BuyView ga uzatiladi")
check("initialTab?: 'stars' | 'premium' | 'gifts' | 'nft';" in BUY,
      "BuyView prop'ida 'nft' bor")
check("useState<'stars' | 'premium' | 'gifts' | 'nft'>(initialTab)" in BUY,
      "BuyView subTab 'nft' bilan boshlanadi")
check("setSubTab(initialTab)" in BUY, "initialTab o'zgarganda sinxronlanadi")
# NFT ichki tabi 'gifts' dan boshlanadi (ro'yxat ko'rinadi)
NFTV = open(f"{ROOT}/src/components/views/NftRentView.tsx", encoding="utf-8").read()
check("useState<TabId>('gifts')" in NFTV,
      "NFT bo'limida 'Gifts' ichki tabi ochiladi (ro'yxat ko'rinadi)")

print()
print("=" * 70)
print("4) XABAR MATNI — hech qanday parse_mode xatosiz")
print("=" * 70)
sm = BSRC[BSRC.index("async def nft_order_summary("):
          BSRC.index("async def _patch_nft_notices(")]
check("parse_mode" not in sm, "summary matnida parse_mode yo'q (matn toza)")
check("<b>" in sm and "</b>" in sm, "HTML teglar juft (teng)")

print()
print("=" * 70)
print("NATIJA:", "✅ BARCHASI TO'G'RI" if ok else "❌ MUAMMO BOR")
print("=" * 70)
sys.exit(0 if ok else 1)