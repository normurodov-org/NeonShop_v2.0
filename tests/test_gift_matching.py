"""Gift tanlash (emoji bo'yicha), xabar matni va anonim semantikasi."""
import asyncio
import sys

sys.path.insert(0, '.')
import bot as B

B.GIFT_POLL_INTERVAL = 0.05
B.GIFT_RETRY_DELAY = 0.0


class FakeSticker:
    def __init__(self, e):
        self.emoji = e


class G:
    def __init__(self, i, e, p):
        self.id, self.sticker, self.price = i, FakeSticker(e), p


# Telegram haqiqiy tartibiga O'XSHASH: narxlari aralashib,
# bir xil narxli sovg'alar yonma-yon (yurakcha AYDAN oldin).
TELEGRAM = [
    G(101, "💝", 15),
    G(102, "🧸", 15),
    G(103, "🌹", 25),
    G(104, "🎁", 25),
    G(105, "🚀", 50),
    G(106, "🎂", 50),
    G(107, "💐", 50),
    G(108, "🍾", 50),
    G(109, "🏆", 100),
    G(110, "💍", 100),
    G(111, "💎", 100),
]

calls = []


class UB:
    async def get_available_gifts(self):
        return TELEGRAM

    async def send_gift(self, chat_id, gift_id, text=None, hide_my_name=None):
        calls.append({"chat": chat_id, "gift": gift_id,
                      "text": text, "anon": hide_my_name})
        return True


async def run_order(gift_key, stars, text, anon_flag, mid):
    calls.clear()
    B.db.data["orders"] = {f"o{mid}": {
        "id": f"o{mid}", "user_id": 555, "kind": "gift", "gift": gift_key,
        "stars": stars, "title": "x", "recipient": "bobur",
        "status": "completed", "hide_my_name": anon_flag,
        "gift_text": text,
    }}
    B.db.save()
    task = asyncio.create_task(B.process_gift_orders())
    for _ in range(12):
        await asyncio.sleep(0.08)
        if calls:
            break
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    return calls[0] if calls else None


async def main():
    ok = True

    print("=" * 64)
    print("1) GIFT TANLASH — har bir sovg'a o'zini OLADIMI?")
    print("=" * 64)
    for key, title, stars, price, emoji in B.GIFTS:
        m = B.find_gift(TELEGRAM, key, stars)
        got = B.gift_sticker_emoji(m) if m else None
        good = got == emoji
        ok &= good
        print(f"  {key:10} so'ramiz {emoji}  ->  Telegram {str(got):5} (id {m.id if m else '-'})  {'✅' if good else '❌'}")
    print()
    print("  Eski kod faqat NARX bo'yicha solishtirardi: yurakcha va ayiqcha")
    print("  ikkalasi ham 15 ⭐ bo'lgani uchun DOIM yurakcha tanlanardi —")
    print("  bu endi EMOSI bo'yicha aniqlanadi.")

    print()
    print("=" * 64)
    print("2) ZAXIRA — emos yo'q bo'lsa narx bo'yicha")
    print("=" * 64)
    m = B.find_gift([G(201, "🌹", 25)], "box", 25)
    g = bool(m)
    ok &= g
    print(f"  'box' so'raldi (🎁 yo'q), 25⭐ bo'lgani tanlandi: {m.id if m else '-'}  {'✅' if g else '❌'}")
    m = B.find_gift([], "box", 25)
    g = m is None
    ok &= g
    print(f"  ro'yxat bo'sh -> None: {m}  {'✅' if g else '❌'}")

    print()
    print("=" * 64)
    print("3) XABAR MATNI va ANONIM")
    print("=" * 64)
    B.userbot = UB()
    B.db.get_or_create_user(555, "aliy", "Aliy")

    # UI "🕶️ Anonim" -> hide_my_name=True -> Telegram hide_my_name=True
    # (Telegram MTProto: InputInvoiceStarGift.hide_name = flags.0?true)
    c = await run_order("cake", 50, "Sizga omad! 🌸", True, 1)
    g = bool(c) and c["text"] == "Sizga omad! 🌸" and c["anon"] is True
    ok &= g
    print("  UI: 🕶️ ANONIM tanlangan (hide_my_name=True)")
    print(f"    matn='{c['text'] if c else None}'  Telegram hide_my_name={c['anon'] if c else None}")
    print(f"    (True = profil YASHIRILADI)  {'✅' if g else '❌'}")

    # UI "👤 Do'kon profili" -> hide_my_name=False -> Telegram hide_my_name=False
    c = await run_order("rose", 25, "", False, 2)
    g = bool(c) and c["anon"] is False and not c["text"]
    ok &= g
    print("  UI: 👤 DO'KON PROFILI ko'rinadi (hide_my_name=False)")
    print(f"    matn={c['text'] if c else None!r}  Telegram hide_my_name={c['anon'] if c else None}")
    print(f"    (False = profil KO'RINADI)  {'✅' if g else '❌'}")

    print()
    print("=" * 64)
    print("4) MATN YO'Q bo'lsa — None uzatiladi (xato emas)")
    print("=" * 64)
    c = await run_order("bear", 15, None, True, 3)
    g = bool(c) and c["text"] is None
    ok &= g
    print(f"  matn=None -> send_gift(text=None): {c['text'] if c else 'YUBORILMADI'}  {'✅' if g else '❌'}")

    print()
    print("NATIJA:", "✅ BARCHASI TO'G'RI" if ok else "❌ MUAMMO BOR")


asyncio.run(main())