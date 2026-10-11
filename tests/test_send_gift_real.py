"""Haqiqiy pyrofork send_gift kodini mock'li client bilan chaqirib,
'object of type NoneType has no len()' xatosining QAYERDA kelishini
ko'rsatadi.

Ishga tushishi uchun pyrofork o'rnatilgan bo'lishi kerak
(production Dockerfile uni o'rnatadi).
"""
import asyncio
import sys
import traceback
import types as pytypes

sys.path.insert(0, '.')
import bot as B  # noqa: E402

try:
    import pyrogram
    from pyrogram.raw import types as raw_types, functions as raw_fn
    from pyrogram.methods.payments.send_gift import SendGift
    LIB = f"{pyrogram.__name__} {getattr(pyrogram, '__version__', '?')}"
except ImportError:  # pragma: no cover
    print("❌ pyrogram o'rnatilmagan — reproni ishga tushirib bo'lmaydi")
    sys.exit(2)


class MockParser:
    """pyrogram.parser.Parser namunasi (haqiqiy kod bilan bir xil)."""

    def __init__(self):
        from pyrogram.parser import Parser
        self._p = Parser(None)

    async def parse(self, text, mode=None):
        return await self._p.parse(text, mode)


class MockSession:
    def __init__(self):
        self.calls = []
        self.last_bytes = None

    def __bytes__(self):
        return b""


class MockStorage:
    async def get_peer_by_id(self, peer_id):
        raise KeyError(peer_id)

    async def get_peer_by_username(self, name):
        raise KeyError(name)

    async def get_peer_by_phone_number(self, num):
        raise KeyError(num)


class MockClient:
    """send_gift ichidagi barcha qo'ng'iroqlarni ushlaydi."""

    def __init__(self):
        self.is_connected = True
        self.storage = MockStorage()
        self.parser = MockParser()
        self.parse_mode = None
        self.session = MockSession()
        self.invoked = []

    # --- resolve_peer ni almashtiramiz (tarmoqqa chiqmaydi) ---
    async def resolve_peer(self, chat_id):
        return raw_types.InputPeerUser(user_id=12345, access_hash=67890)

    # --- invoke: GetPaymentForm / SendStarsForm ---
    async def invoke(self, query):
        self.invoked.append(type(query).__name__)
        if isinstance(query, raw_fn.payments.GetPaymentForm):
            return pytypes.SimpleNamespace(form_id=999)
        return pytypes.SimpleNamespace(updates=[])

    # --- serialize: haqiqiy MTProto kodini ishlatamiz ---
    async def invoke_raw(self, query):
        return await self.invoke(query)


def try_call(label, **kwargs):
    print(f"\n--- {label} ---")
    print(f"    args: {kwargs}")
    c = MockClient()
    try:
        res = asyncio.run(SendGift.send_gift(c, **kwargs))
        print(f"    ✅ muvaffaqiyat: {res}, invoke: {c.invoked}")
        return True
    except Exception as exc:  # noqa: BLE001
        tb = traceback.format_exc()
        print(f"    ❌ {type(exc).__name__}: {exc}")
        # oxirgi 6 qator — asil sabab ko'rinadi
        for ln in tb.strip().splitlines()[-6:]:
            print(f"       {ln}")
        return False


print("=" * 68)
print(f"Lib: {LIB}")
print("=" * 68)

ok = True

# 1) Eski chaqiruv: text berilmagan (production'dagi xato shu edi)
ok &= try_call("text yo'q, hide_my_name=True", chat_id="bobur", gift_id=101,
               hide_my_name=True)
# 2) text berilmagan, hide_my_name=False
ok &= try_call("text yo'q, hide_my_name=False", chat_id="bobur", gift_id=101,
               hide_my_name=False)
# 3) hide_my_name umuman berilmagan (None)
ok &= try_call("hide_my_name=None", chat_id="bobur", gift_id=101)
# 4) text bilan (yangi kod)
ok &= try_call("text='Sizga omad!'", chat_id="bobur", gift_id=101,
               text="Sizga omad!", hide_my_name=True)
# 5) bo'sh string
ok &= try_call("text=''", chat_id="bobur", gift_id=101, text="", hide_my_name=False)

# =============================================================================
# 2) get_available_gifts — real StarGift obyekti bilan
# =============================================================================
print()
print("=" * 68)
print("get_available_gifts() — Gift/Sticker parsing")
print("=" * 68)

from pyrogram.methods.payments.get_available_gifts import GetAvailableGifts  # noqa: E402
from pyrogram.raw.types import DocumentAttributeSticker  # noqa: E402


# len(None) qayerda sodir bo'lishini ANIQ ko'rsatuvchi tracer
import builtins  # noqa: E402

_ORIG_LEN = builtins.len
_LEN_HITS: list[str] = []


def _len_traced(obj=None, *a, **kw):
    if obj is None:
        _LEN_HITS.append("".join(traceback.format_stack()[-6:]))
        raise TypeError("TRACE: len(None) qayerda?")
    return _ORIG_LEN(obj, *a, **kw)


builtins.len = _len_traced


def make_doc(doc_id, attrs=None):
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
        attributes=attrs if attrs is not None else [
            DocumentAttributeSticker(
                mask=False,
                alt="",
                stickerset=raw_types.InputStickerSetID(id=777, access_hash=888),
            ),
        ],
    )


class MockGiftClient(MockClient):
    def __init__(self, star_gifts):
        super().__init__()
        self._gifts = star_gifts

    async def invoke(self, query):
        self.invoked.append(type(query).__name__)
        if isinstance(query, raw_fn.payments.GetStarGifts):
            return pytypes.SimpleNamespace(gifts=self._gifts, hash=0)
        if isinstance(query, raw_fn.messages.GetStickerSet):
            # set.short_name None bo'lishi MUMKIN (Telegram ba'zan yubormaydi)
            return pytypes.SimpleNamespace(
                set=pytypes.SimpleNamespace(short_name=None, title=None)
            )
        return await super().invoke(query)


def try_gifts(label, star_gifts):
    print(f"\n--- {label} ---")
    c = MockGiftClient(star_gifts)
    try:
        gifts = asyncio.run(GetAvailableGifts.get_available_gifts(c))
        for g in gifts:
            print(f"    ✅ id={g.id} narx={g.price} emoji={g.sticker.emoji!r}")
        return True
    except Exception as exc:  # noqa: BLE001
        tb = traceback.format_exc()
        print(f"    ❌ {type(exc).__name__}: {exc}")
        for ln in tb.strip().splitlines()[-6:]:
            print(f"       {ln}")
        return False


good = [
    raw_types.StarGift(id=101, sticker=make_doc(1), stars=15, convert_stars=15,
                       availability_remains=1000),
    raw_types.StarGift(id=102, sticker=make_doc(2), stars=25, convert_stars=25),
]
ok &= try_gifts("oddiy gift'lar (2 ta)", good)

# Temir: sticker None bo'lsa nima bo'ladi?
ok &= try_gifts("sticker=None", [
    raw_types.StarGift(id=103, sticker=None, stars=15, convert_stars=15),
])

# Temir: Document attributes=None
ok &= try_gifts("Document.attributes=None", [
    raw_types.StarGift(id=104, sticker=make_doc(4, attrs=None), stars=15,
                       convert_stars=15),
])

# Temir: availability_remains None
ok &= try_gifts("availability_remains=None", [
    raw_types.StarGift(id=105, sticker=make_doc(5), stars=15, convert_stars=15,
                       availability_remains=None),
])

print()
if _LEN_HITS:
    print("!!! len(None) TOPILDI — qayerda:")
    for i, st in enumerate(_LEN_HITS, 1):
        print(f"\n--- #{i} ---")
        for ln in st.strip().splitlines():
            print("   ", ln)

print()
print("=" * 68)
print("YAKUNIY NATIJA:", "✅ BARCHASI ISHLADI" if ok else "❌ XATO TOPILDI")
print("=" * 68)
sys.exit(0 if ok else 1)
