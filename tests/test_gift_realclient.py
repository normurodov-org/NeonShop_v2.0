"""HAQIQIY pyrofork Client obyekti bilan gift worker'ni sinash.

Maqsad: 'object of type NoneType has no len()' xatosi qayerdan kelishini
topish. Mock klass o'rniga haqiqiy pyrogram.Client yaratiladi — shunda
Client.__init__, storage, session va boshqa ichki kod ham ishlaydi.

Tarmoq yo'q: faqat `invoke` va `resolve_peer` almashtiriladi.
"""
import asyncio
import os
import sys
import traceback
import builtins

sys.path.insert(0, '.')

# --- len(None) izlagichi ---
_LEN_HITS = []
_ORIG_LEN = builtins.len


def _len_traced(obj=None, *a, **kw):
    if obj is None:
        _LEN_HITS.append("".join(traceback.format_stack()[-8:]))
        return _ORIG_LEN(_ORIG_LEN([]))  # xato bermaslik uchun, lekin iz qoldiramiz
    return _ORIG_LEN(obj, *a, **kw)


import bot as B  # noqa: E402

import pyrogram  # noqa: E402
from pyrogram.raw import types as raw_types, functions as raw_fn  # noqa: E402
from pyrogram.methods.payments.send_gift import SendGift  # noqa: E402
from pyrogram.methods.payments.get_available_gifts import GetAvailableGifts  # noqa: E402
from pyrogram.raw.types import DocumentAttributeSticker  # noqa: E402

builtins.len = _len_traced  # faqat o'z ichimizda tekshiramiz


def _doc(doc_id, alt):
    return raw_types.Document(
        id=doc_id,
        access_hash=1234567,
        file_reference=b"\x00" * 16,
        mime_type="image/x-apng",
        size=1000,
        thumbs=[],
        video_thumbs=[],
        dc_id=2,
        date=1700000000,
        attributes=[DocumentAttributeSticker(
            mask=False, alt=alt,
            stickerset=raw_types.InputStickerSetID(id=700 + doc_id, access_hash=800),
        )],
    )


GIFTS_RAW = [
    raw_types.StarGift(id=101, sticker=_doc(1, "💝"), stars=15, convert_stars=15),
    raw_types.StarGift(id=102, sticker=_doc(2, "🧸"), stars=15, convert_stars=15),
    raw_types.StarGift(id=103, sticker=_doc(3, "🌹"), stars=25, convert_stars=25),
]

SENT = []


class RealClientNoNet(pyrogram.Client):
    """Haqiqiy Client, faqat tarmoq qismi almashtirilgan."""

    async def invoke(self, query):
        name = type(query).__name__
        SENT.append(name)
        if name == "GetStarGifts":
            return type("R", (), {"gifts": GIFTS_RAW, "hash": 0})()
        if name == "GetStickerSet":
            return type("R", (), {"set": type("S", (), {"short_name": "Gifts", "title": "G"})()})()
        if name == "GetPaymentForm":
            return type("R", (), {"form_id": 999})()
        if name == "SendStarsForm":
            return type("R", (), {"updates": []})()
        raise RuntimeError(f"kutilmagan: {name}")

    async def resolve_peer(self, chat_id):
        return raw_types.InputPeerUser(user_id=12345, access_hash=67890)


def build():
    return RealClientNoNet(
        "real_test", api_id=1, api_hash="x", session_string=None,
        in_memory=True, no_updates=True,
    )


async def run_case(label, order, expect_skip=False):
    SENT.clear()
    B.db.data["orders"] = {"o1": order}
    B.db.save()
    task = asyncio.create_task(B.process_gift_orders())
    for _ in range(15):
        await asyncio.sleep(0.05)
        if "SendStarsForm" in SENT or B.db.data["orders"]["o1"].get("gift_sent"):
            break
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    o = B.db.data["orders"]["o1"]
    if expect_skip:
        # Skip kutilgan holat: yuborilMAMALIgicha qolishi kerak
        ok = not o.get("gift_sent") and not o.get("gift_error")
    else:
        ok = bool(o.get("gift_sent")) and "SendStarsForm" in SENT
    print(f"\n--- {label} ---")
    print(f"    gift_sent={o.get('gift_sent')}  xato={o.get('gift_error')!r}")
    print(f"    Telegram chaqiruvlari: {SENT}")
    return ok


def order(gift="bear", stars=15, **kw):
    o = {
        "id": "ord_kzkqb5j", "user_id": 555, "kind": "gift", "gift": gift,
        "stars": stars, "title": "🧸 Ayiqcha", "recipient": "bobur",
        "status": "completed", "anon": True, "hide_my_name": True,
        "price": 3000,
    }
    o.update(kw)
    return o


async def main():
    ok = True
    print("=" * 68)
    print(f"Lib: pyrogram {pyrogram.__version__} (real Client obyekti bilan)")
    print("=" * 68)

    B.GIFT_POLL_INTERVAL = 0.05
    B.GIFT_RETRY_DELAY = 0.0
    B.userbot = build()
    B.gift_userbot = None
    B.db.get_or_create_user(555, "aliy", "Aliy")

    ok &= await run_case("ayiqcha (emoji mos), anonim, matnsiz", order())
    ok &= await run_case("matn bilan", order(gift_text="Sizga omad! 🌸"))
    ok &= await run_case("gift='rose' (narx 25)", order(gift="rose", stars=25))
    ok &= await run_case("gift_key yo'q (eski yozuv)",
                         {k: v for k, v in order().items() if k != "gift"}
                         | {"gift_key": "heart"})
    ok &= await run_case("recipient @ bilan", order(recipient="@bobur"))
    ok &= await run_case("recipient bo'sh (skip kutiladi)",
                         order(recipient=""), expect_skip=True)
    ok &= await run_case("stars=None (skip kutiladi)", order(stars=None))
    ok &= await run_case("title yo'q", order(title=None))

    print()
    if _LEN_HITS:
        print("!!! len(None) topildi — qayerda:")
        for i, st in enumerate(_LEN_HITS, 1):
            print(f"\n--- #{i} ---")
            for ln in st.strip().splitlines():
                print("   ", ln)
    else:
        print("✅ Hech qayerda len(None) topilmadi")

    print()
    print("=" * 68)
    print("NATIJA:", "✅ BARCHASI ISHLADI" if ok else "❌ MUAMMO BOR")
    print("=" * 68)
    return 0 if ok else 1


sys.exit(asyncio.run(main()))