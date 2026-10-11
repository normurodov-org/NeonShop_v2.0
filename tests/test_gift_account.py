"""Gift akkauntining bank akkauntidan AJRATILISHI va kanal xabari formati."""
import asyncio
import re
import sys

sys.path.insert(0, '.')
import bot as B  # noqa: E402


class FakeMe:
    def __init__(self, uid, username):
        self.id, self.username = uid, username


class FakeClient:
    """Minimal Pyrogram client namunasi."""

    def __init__(self, uid, username, on_stop=None):
        self._me = FakeMe(uid, username)
        self.stopped = False
        self._on_stop = on_stop
        self.handlers = []
        self.session = f"SESSION_FOR_{username}"

    async def get_me(self):
        return self._me

    async def stop(self):
        self.stopped = True
        if self._on_stop:
            self._on_stop(self)

    async def add_handler(self, h):
        self.handlers.append(h)

    async def export_session_string(self):
        return self.session


ok = True


def check(cond, msg):
    global ok
    ok &= bool(cond)
    print(f"  {'✅' if cond else '❌'} {msg}")


print("=" * 66)
print("1) gift_client() — qaysi akkaunt ishlatiladi?")
print("=" * 66)

B.userbot = FakeClient(1, "bank_humo", on_stop=lambda c: setattr(B, "userbot", None))
B.gift_userbot = None
check(B.gift_client() is B.userbot,
      "GIFT akkaunti yo'q -> bank akkaunti (eski tartib saqlanadi)")

B.gift_userbot = FakeClient(2, "neon_shop", on_stop=lambda c: setattr(B, "gift_userbot", None))
check(B.gift_client() is B.gift_userbot,
      "GIFT akkaunti bor -> ALHOHIDA akkaunt (bank emas)")

B.userbot = None
check(B.gift_client() is not None,
      "Bank ulanmagan, gift ulangan -> gift ishlayveradi")

B.gift_userbot = None
check(B.gift_client() is None, "Ikkalasi ham ulanmagan -> None (worker ogohlantiradi)")

print()
print("=" * 66)
print("2) _start_gift_userbot — GIFT_SESSION_STRING qarorlari")
print("=" * 66)


async def t_start():
    global ok

    # (a) GIFT_SESSION_STRING yo'q -> eski tartib
    B.gift_userbot = None
    B.SESSION_STRING = "x" * 40
    B.GIFT_SESSION_STRING = ""
    await B._start_gift_userbot()
    check(B.gift_userbot is None, "GIFT_SESSION_STRING yo'q -> gift akkaunti yaratilmaydi")

    # (b) GIFT_SESSION_STRING == SESSION_STRING -> eski tartib
    B.gift_userbot = None
    B.GIFT_SESSION_STRING = B.SESSION_STRING
    await B._start_gift_userbot()
    check(B.gift_userbot is None, "Ikkalasi bir xil -> alohida client yaratilmaydi")

    # (c) turli akkaunt -> alohida client yaratilishi kerak
    B.gift_userbot = None
    B.GIFT_SESSION_STRING = "y" * 40
    started = {}

    class UB(B.UserbotClient):
        def __init__(self, name, **kw):
            started["name"] = name
            started["session"] = kw.get("session_string")

        async def start(self):
            pass

        async def get_me(self):
            return FakeMe(2, "neon_shop")

    orig = B.UserbotClient
    B.UserbotClient = UB
    try:
        await B._start_gift_userbot()
    finally:
        B.UserbotClient = orig
    check(B.gift_userbot is not None, "Turli akkaunt -> gift client ulandi")
    check(started.get("name") == "neon_gift_userbot",
          f"Alohida session nomi: {started.get('name')}")
    check(started.get("session") == B.GIFT_SESSION_STRING,
          "GIFT_SESSION_STRING ishlatildi (SESSION_STRING emas)")


asyncio.run(t_start())

print()
print("=" * 66)
print("3) ub_finish_login — rolega qarab to'g'ri joyga o'tadi")
print("=" * 66)


async def t_finish():
    global ok
    B.userbot = FakeClient(1, "bank_humo", on_stop=lambda c: setattr(B, "userbot", None))
    B.gift_userbot = None
    B.PENDING_LOGIN_ROLE = "gift"
    c = FakeClient(2, "neon_shop", on_stop=lambda x: setattr(B, "gift_userbot", None))
    await B.ub_finish_login(c, _Msg(), _State())
    check(B.gift_userbot is not None, "rol=gift -> gift_userbot ga o'tdi")
    check(B.userbot is not None, "rol=gift -> bank akkaunti O'LMADI")
    check(B.userbot.handlers == [], "rol=gift -> bank xabar handler'i qo'shilmadi")

    B.PENDING_LOGIN_ROLE = "bank"
    c2 = FakeClient(3, "bank_new", on_stop=lambda x: setattr(B, "userbot", None))
    await B.ub_finish_login(c2, _Msg(), _State())
    check(B.userbot is not None and B.userbot._me.id == 3, "rol=bank -> userbot ga o'tdi")
    check(len(B.userbot.handlers) == 1, "rol=bank -> bank xabar handler'i qo'shildi")


class _Msg:
    def __init__(self):
        self.answers = []

    async def answer(self, text, **kw):
        self.answers.append(text)

    async def edit_text(self, text, **kw):
        pass


class _State:
    def __init__(self):
        self.data = {}

    async def clear(self):
        self.data = {}

    async def get_data(self):
        return dict(self.data)

    async def update_data(self, **kw):
        self.data.update(kw)


# _Msg/_State oldindan kerak
Msg, State = _Msg, _State
import bot as _b  # noqa: E402

for name, obj in (("_Msg", Msg), ("_State", State)):
    if not hasattr(_b, name):
        setattr(_b, name, obj)

asyncio.run(t_finish())

print()
print("=" * 66)
print("4) ORDERS_CHANNEL xabari formati (mijoz rasmidagi)")
print("=" * 66)
txt = B.format_order_channel_text(
    title="Stars olindi", who="@odilbek",
    amount_text="Miqdor: 50 ⭐", price=10_000, cashback=10,
)
plain = txt.replace("<b>", "").replace("</b>", "").replace("&#x27;", "'")
print(plain)
print()
check(plain.splitlines()[0].strip() == "⭐ Stars olindi", "1-qator: ⭐ Stars olindi")
check(plain.splitlines()[1].strip() == "👤 @odilbek", "2-qator: 👤 mijoz")
check("📦 Miqdor: 50 ⭐" in plain, "📦 Miqdor: 50 ⭐")
check("Summasi: 10 000 so'm" in plain, "  Summasi: 10 000 so'm")
check("Keshbek: +10 so'm" in plain, "  Keshbek: +10 so'm")

txt2 = B.format_order_channel_text(
    title="Gift: 🧸 Ayiqcha (15 ⭐) (🕶️ Anonim)",
    who="@aliy", amount_text="Sovg'a: 🧸 Ayiqcha — 15 ⭐", price=3_000,
)
plain2 = txt2.replace("<b>", "").replace("</b>", "").replace("&#x27;", "'")
print()
print(plain2)
check("Keshbek" not in plain2, "Keshbek yo'q bo'lsa qator qo'shilmaydi")
check("Sovg'a: 🧸 Ayiqcha" in plain2, "esc() apostrofni buzmaydi")

print()
print("=" * 66)
print("5) server.ts bilan format BIR XILMI?")
print("=" * 66)
srv = open("server.ts", encoding="utf-8").read()
fn = re.search(r"function channelOrderText\(.*?\n}\n", srv, re.S)
check(fn is not None, "server.ts da channelOrderText() bor")
if fn:
    js = fn.group(0)
    for frag in ("Stars olindi", "Summasi:", "Keshbek:", "Miqdor"):
        check(frag in js or "amountText" in js, f"server.ts: {frag!r} mavjud")
check("sendTelegramMessage" in srv, "eski (grammy) yo'l o'chirilmagan — fallback sifatida")
check("api.telegram.org/bot${token}/sendMessage" in srv,
      "to'g'ridan-to'g'ri Bot API chaqiriladi (AUTO_START_TG_BOT=false bo'lsa ham)")

print()
print("NATIJA:", "✅ BARCHASI TO'G'RI" if ok else "❌ MUAMMO BOR")
sys.exit(0 if ok else 1)