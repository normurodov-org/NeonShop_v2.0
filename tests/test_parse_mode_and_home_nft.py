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
check("UB_PARSE_HTML = UbParseMode.HTML" in CODE,
      "UB_PARSE_HTML = UbParseMode.HTML (pyrofork ENUM'I)")
check("from pyrogram.enums import ParseMode as UbParseMode" in CODE,
      "UbParseMode import qilingan")

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
print("  🔴 HAQIQIY TEKSHIRUV — pyrofork'ning o'z Parser'i bilan")
print("      (taxmin qilinmaydi, LIBRARIYA JAVOB BERADI)")
try:
    import asyncio

    from aiogram.enums import ParseMode as AiPM
    from pyrogram.enums import ParseMode as UbPM
    from pyrogram.parser import Parser

    TEXT = ("🎁 <b>NFT ijaraga olish so'rovi</b>\n\n"
            "🖼 <b>Fine Pen</b> <code>#18272</code>")

    async def _probe():
        out = {}
        for label, mode in (("pyrofork enum", UbPM.HTML),
                            ("string 'html'", "html"),
                            ("string 'HTML'", "HTML"),
                            ("aiogram enum", AiPM.HTML)):
            try:
                r = await Parser(None).parse(TEXT, mode)
                out[label] = ("OK", len(r["entities"]))
            except Exception as exc:  # noqa: BLE001
                out[label] = ("XATO", str(exc))
        return out

    res = asyncio.run(_probe())
    for label, (status, extra) in res.items():
        print(f"      {label:16} -> {status}: {extra}")

    check(res["pyrofork enum"][0] == "OK",
          f"🔴 UbParseMode.HTML ISHLAYDI ({res['pyrofork enum'][1]} entities)")
    check(res["pyrofork enum"][1] > 0, "HTML teglar entity ga aylangan")
    check(res["string 'html'"][0] == "XATO",
          "\"html\" string ISHLAMAYDI (AutoName enum, str emas)")
    check(res["string 'HTML'"][0] == "XATO", "\"HTML\" string ham ISHLAMAYDI")
    check(res["aiogram enum"][0] == "XATO",
          "🔴 aiogram enum userbotda ISHLAMAYDI")
except Exception as exc:  # noqa: BLE001
    check(False, f"pyrofork parser tekshiruvi: {exc}")

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
# 🔴 2026-10-16: `App` endi `initialBuyCategory` state'ini TUTMAYDI —
#    manba bitta `route` ({tab, sections[]}) bo'ldi va `/nft` ham
#    o'z kanonik yo'li bilan keladi. Zanjir tekshiruvi yangilandi.
check("const [route, setRoute] = useState<Route>" in APP,
      "App: bitta `route` state (nafqat yo'llar uchun)")
check("initialTab={buySection}" in APP, "BuyView ga uzatiladi")
check("initialTab?: BuySub;" in BUY,
      "BuyView prop'ida `BuySub` bor")
check("useState<BuySub>(initialTab)" in BUY,
      "BuyView subTab 'nft' bilan boshlanadi")
check("setSubTab(initialTab)" in BUY, "initialTab o'zgarganda sinxronlanadi")
# NFT ichki tabi 'gifts' dan boshlanadi (ro'yxat ko'rinadi)
NFTV = open(f"{ROOT}/src/components/views/NftRentView.tsx", encoding="utf-8").read()
check("useState<NftSub>('gifts')" in NFTV,
      "NFT bo'limida 'Gifts' ichki tabi ochiladi (ro'yxat ko'rinadi)")
# 📌 Endi ichki tab ham o'z yo'lida: /nft/gifts
check("['nft', 'gifts']," in open(f"{ROOT}/src/lib/routes.ts", encoding="utf-8").read(),
      "📌 `/nft/gifts` — NFT ichidagi 'Gifts' o'z yo'li bilan")

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
print("5) DIAGNOSTIKA — qolsa ham ANIQ sabab ko'rsatadi")
print("=" * 70)
check('callback_data="adm:nft_resend_all"' in BSRC, "📨 Barchasini qayta yuborish")
check("async def adm_nft_resend_all(" in BSRC, "handler")
check('order.pop("nft_notify_gave_up", None)' in BSRC.split("async def adm_nft_resend_all(")[1][:800],
      "berkitilganlar qayta ochiladi")
check("import traceback as _tb" in BSRC, "to'liq traceback")
check("format_exception_only" in BSRC, "xato turi ko'rsatiladi")
pg = BSRC[BSRC.index("async def adm_nft_ping("):
          BSRC.index("async def adm_nft_resend_all(")]
check("format_exception_only" in pg, "ping xatosi batafsil")
check("log.error(" in pg, "xato logga yoziladi")

print()
print("=" * 70)
print("6) HAQIQIY XABAR MATNI — pyrofork parser bilan TEKSHIRILADI")
print("=" * 70)
try:
    import asyncio

    sys.path.insert(0, ROOT)
    import bot as B
    from pyrogram.parser import Parser

    order = {"id": "nft_test1", "user_id": 5, "kind": "nft_rent",
             "nft_id": "n1", "nft_title": "Fine Pen", "nft_number": 18272,
             "nft_link": "https://t.me/nft/FinePen-18272", "days": 7,
             "per_day": 98, "rent": 686, "price": 2386, "price_uzs": 2386,
             "customer_username": "odilbek", "admin_username": "normuzb"}

    text = asyncio.run(B.nft_order_summary(order))
    res = asyncio.run(Parser(None).parse(text, B.UB_PARSE_HTML))
    check(len(res["entities"]) > 0,
          f"🔴 xabar matni parse bo'ldi ({len(res['entities'])} entity)")
    check(res["entities"] is not None, "entity lar to'g'ri")
    # Butun matnni ham validatsiya qilamiz
    text2 = asyncio.run(B.nft_order_summary(order, status_line="✅ <b>Bajarildi</b> (admin)"))
    asyncio.run(Parser(None).parse(text2, B.UB_PARSE_HTML))
    check(True, "natijali xabar ham parse bo'ldi")
except Exception as exc:  # noqa: BLE001
    check(False, f"xabar matni tekshiruvi: {exc}")

print()
print("=" * 70)
print("7) 🔴 KLAVIATURA — aiogram TURI userbotda ISHLAMAYDI")
print("=" * 70)
# XABAR: "'InlineKeyboardMarkup' object has no attribute 'write'"
check("from pyrogram.types import InlineKeyboardMarkup as UbInlineKeyboardMarkup"
      in BSRC, "pyrofork InlineKeyboardMarkup import qilingan")
check("from pyrogram.types import InlineKeyboardButton as UbInlineKeyboardButton"
      in BSRC, "pyrofork InlineKeyboardButton import qilingan")
check("def ub_nft_action_kb(" in BSRC, "ub_nft_action_kb()")
check("def ub_empty_kb(" in BSRC, "ub_empty_kb()")
check("reply_markup=ub_nft_action_kb(" in BSRC, "userbot xabari -> pyrofork klaviatura")
check("reply_markup=ub_empty_kb()" in BSRC, "userbot edit -> pyrofork bo'sh klaviatura")
check("reply_markup=nft_action_kb(" not in send_fn,
      "🔴 userbot ga aiogram klaviaturasi yuborilmaydi")

try:
    import asyncio

    sys.path.insert(0, ROOT)
    import bot as B

    async def _kb():
        out = {}
        for label, kb in (("aiogram", B.nft_action_kb("nft_x")),
                          ("pyrofork", B.ub_nft_action_kb("nft_x")),
                          ("pyrofork_empty", B.ub_empty_kb())):
            try:
                raw_kb = await kb.write(None)   # pyrofork ichida shuni qiladi
                out[label] = ("OK",
                              [b.text for b in raw_kb.rows[0].buttons] if raw_kb.rows else [])
            except Exception as exc:  # noqa: BLE001
                out[label] = ("XATO", type(exc).__name__)
        return out

    kb_res = asyncio.run(_kb())
    print(f"      aiogram (eski)      -> {kb_res['aiogram'][0]}: {kb_res['aiogram'][1]}")
    print(f"      pyrofork (yangi)    -> {kb_res['pyrofork'][0]}: {kb_res['pyrofork'][1]}")
    print(f"      pyrofork (bo'sh)    -> {kb_res['pyrofork_empty'][0]}: {kb_res['pyrofork_empty'][1]}")
    check(kb_res["pyrofork"][0] == "OK",
          f"🔴 pyrofork klaviatura ishlaydi ({kb_res['pyrofork'][1]})")
    check(kb_res["pyrofork"][1] == ["✅ Bajarildi", "❌ Bekor qilish"],
          "ikki tugma ham to'g'ri")
    check(kb_res["pyrofork_empty"][0] == "OK",
          "tugmalarni olib tashlash ishlaydi")
    check(kb_res["aiogram"][0] == "XATO",
          "aiogram klaviatura userbotda ISHLAMAYDI (AttributeError)")
except Exception as exc:  # noqa: BLE001
    check(False, f"klaviatura tekshiruvi: {exc}")

print()
print("=" * 70)
print("NATIJA:", "✅ BARCHASI TO'G'RI" if ok else "❌ MUAMMO BOR")
print("=" * 70)
sys.exit(0 if ok else 1)