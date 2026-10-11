import asyncio, inspect, sys, types
sys.path.insert(0, '.')
import bot as B
from pyrogram import Client

print("=" * 70)
print("1) PYROGRAM 2.x API MOSLIGI")
print("=" * 70)
sig = inspect.signature(Client.start)
print(f"  Client.start{sig}")
ok = len(sig.parameters) <= 1        # faqat self
print(" ", "✅ start() argument qabul qilmaydi — eski kod ishlamasdi" if ok else "❌")

for name, params in (("connect", []), ("send_code", ["phone_number"]),
                     ("sign_in", ["phone_number", "phone_code_hash", "phone_code"]),
                     ("check_password", ["password"]),
                     ("get_password_hint", []),
                     ("export_session_string", [])):
    f = getattr(Client, name, None)
    if f is None:
        print(f"  ❌ {name} yo'q")
        continue
    have = set(inspect.signature(f).parameters)
    missing = [p for p in params if p not in have]
    print(f"  {'✅' if not missing else '❌'} {name}: {sorted(have)}"
          + (f"  YO'Q: {missing}" if missing else ""))
    ok &= not missing

print()
print("=" * 70)
print("2) BOT KODIDA ESKI (noto'g'ri) API QOLMAGAN")
print("=" * 70)
import ast
tree = ast.parse(open("bot.py", encoding="utf-8").read())
bad = []
for node in ast.walk(tree):
    # start(phone=...) — argumentli start() chaqiruvi
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and node.func.attr == "start" and node.keywords:
        bad.append(f"qator {node.lineno}: start(...) argumentli — Pyrogram 1.x API")
    # await UserbotClient(...)
    if isinstance(node, ast.Await) and isinstance(node.value, ast.Call) \
            and isinstance(node.value.func, ast.Name) and node.value.func.id in (
                "UserbotClient", "Client"):
        bad.append(f"qator {node.lineno}: await UserbotClient(...) — konstruktorni await qilish")
for b in bad:
    print("  ❌", b)
    ok = False
if not bad:
    print("  ✅ noto'g'ri API qo'llanmagan")

print()
print("=" * 70)
print("3) OQIM SIMULYATSIYASI (haqiqiy Telegram'siz)")
print("=" * 70)


class FakeSent:
    n = 0
    type = "App"

    @property
    def phone_code_hash(self):
        return f"HASH{self.n}"


class FakeClient:
    """Pyrogram 2.x oqimini takrorlaydi: connect -> send_code -> sign_in"""

    calls = []

    def __init__(self, *a, **kw):
        self.kw = kw
        self.handlers = []
        self.stopped = False
        self.need_password = True

    async def connect(self):
        FakeClient.calls.append("connect")
        return True

    async def send_code(self, phone_number):
        FakeClient.calls.append(f"send_code({phone_number})")
        FakeSent.n += 1
        return FakeSent()

    async def disconnect(self):
        FakeClient.calls.append("disconnect")

    async def sign_in(self, **kw):
        FakeClient.calls.append("sign_in(" + ",".join(sorted(kw)) + ")")
        if "phone_code" in kw:
            if kw["phone_code"] == "11111":
                raise type("SessionPasswordNeeded", (Exception,), {})("2FA required")
            # eskirgan hash -> PHONE_CODE_EXPIRED
            if not kw.get("phone_code_hash", "").endswith(str(FakeSent.n)):
                raise type("PhoneCodeExpired", (Exception,), {})(
                    "[400 PHONE_CODE_EXPIRED] The confirmation code has expired")
            # Telegram kodi = aniq 5 raqam. "00000" — noto'g'ri.
            if len(kw["phone_code"]) != 5 or kw["phone_code"] == "00000":
                raise type("PhoneCodeInvalid", (Exception,), {})("invalid code")
            return types.SimpleNamespace(id=1, username="aliy")
        return types.SimpleNamespace(id=1, username="aliy")

    async def check_password(self, password):
        FakeClient.calls.append(f"check_password(***)")
        if password != "1234":
            raise type("SessionPasswordInvalid", (Exception,), {})("wrong password")
        return types.SimpleNamespace(id=1, username="aliy")

    async def get_password_hint(self):
        return "ab***"

    async def get_me(self):
        return types.SimpleNamespace(id=1, username="aliy", first_name="Aliy")

    async def add_handler(self, h):
        self.handlers.append(h)

    async def export_session_string(self):
        return "BQACAgEAAxk_demo_session_string_value"

    async def disconnect(self):
        FakeClient.calls.append("disconnect")

    async def stop(self):
        self.stopped = True


class FakeMsg:
    def __init__(self, text, uid=1):
        self.text = text
        self.message_id = 1
        self.chat = types.SimpleNamespace(id=uid)
        self.from_user = types.SimpleNamespace(id=uid)
        self.out = []

    async def answer(self, text, **kw):
        self.out.append(text)
        return self


class FakeState:
    def __init__(self):
        self.s = None
        self.d = {}

    async def set_state(self, x):
        self.s = x

    async def update_data(self, **kw):
        self.d.update(kw)

    async def get_data(self):
        return self.d

    async def clear(self):
        self.s = None
        self.d = {}


B.UserbotClient = FakeClient
B.is_admin_authed = lambda uid: True
B.admin_back_kb = lambda: None
B.ub_idle = lambda: asyncio.sleep(3600)


async def flow(phone, code, password=None):
    FakeClient.calls.clear()
    B.userbot = None
    B.UB_LOGIN.clear(); B.UB_LOGIN.update({"client": None, "phone": "", "hash": "", "admin_id": 0, "tries": 0})
    st = FakeState()
    m1 = FakeMsg(phone)
    await B.adm_ub_phone_wait(m1, st)
    m2 = FakeMsg(code)
    await B.adm_ub_code_wait(m2, st)
    out = m1.out + m2.out
    if password is not None and st.s == B.AdminStates.ub_password:
        m3 = FakeMsg(password)
        await B.adm_ub_password_wait(m3, st)
        out += m3.out
    return st, out, FakeClient.calls


async def run():
    global ok
    print()
    st, out, calls = await flow("+998976756546", "12345")
    print("  qadamlar:", " → ".join(calls))
    good = ("connect" in calls and "send_code(+998976756546)" in calls
            and any("sign_in(phone_code,phone_code_hash,phone_number)" in c for c in calls))
    ok &= good
    print(" ", "✅ telefon → kod → sign_in" if good else "❌")
    good2 = any("SESSION_STRING=" in o for o in out)
    ok &= good2
    print(" ", "✅ SESSION_STRING berildi" if good2 else "❌ SESSION_STRING yo'q")
    print("  ", out[-1].split("\n")[0] if out else "")

    print()
    print("  — 2FA paroli talab qilinganda —")
    st, out, calls = await flow("+998976756546", "11111", password="1234")
    print("  qadamlar:", " → ".join(calls))
    good = any("check_password" in c for c in calls) and any(
        "SESSION_STRING=" in o for o in out)
    ok &= good
    print(" ", "✅ 2FA qo'llab-quvvatlanadi" if good else "❌")

    print()
    print("  — noto'g'ri kodda —")
    st, out, calls = await flow("+998976756546", "00000")
    good = any("noto" in o.lower() and "g" in o.lower() and "SESSION_STRING=" not in o for o in out)
    ok &= good
    print(" ", "✅ xato to'g'ri xabar berildi" if good else "❌")

    print()
    print("  — noto'g'ri telefon formati —")
    st = FakeState()
    m = FakeMsg("12345")
    await B.adm_ub_phone_wait(m, st)
    good = any("Format noto'g'ri" in o for o in m.out)
    ok &= good
    print(" ", "✅ rad etildi" if good else "❌")

    print()
    print("  — jarayon eskirgan bo'lsa —")
    B.userbot = None
    B.UB_LOGIN.clear()
    B.UB_LOGIN.update({"client": None, "phone": "", "hash": "", "admin_id": 0, "tries": 0})
    st = FakeState()
    m = FakeMsg("12345")
    await B.adm_ub_code_wait(m, st)
    good = any("eskirgan" in o for o in m.out)
    ok &= good
    print(" ", "✅ tushunarli xabar" if good else "❌")

    print()
    print("  — eskirgan kod (PHONE_CODE_EXPIRED) —")
    FakeClient.calls.clear()
    FakeSent.n = 1
    B.userbot = None
    B.UB_LOGIN.update({"client": None, "phone": "", "hash": "", "admin_id": 0, "tries": 0})
    st = FakeState()
    await B.adm_ub_phone_wait(FakeMsg("+998976756546"), st)   # HASH1
    # Endi eski hash bilan urinish (muddat o'tgan holat)
    B.UB_LOGIN["hash"] = "HASH0"
    m2 = FakeMsg("66726")
    await B.adm_ub_code_wait(m2, st)
    good = any("yangi kod yuborildi" in o for o in m2.out) and not any(
        "SESSION_STRING=" in o for o in m2.out)
    ok &= good
    print("   ", "✅ avtomatik yangi kod yuborildi (qayta boshlash kerak emas)" if good
          else "❌ " + str(m2.out[-1][:120]))
    print("    send_code chaqirilgan soni:",
          len([c for c in FakeClient.calls if "send_code" in c]), "(kerak 2)")

    # yangi hash bilan muvaffaqiyatli kirish
    m3 = FakeMsg("12345")
    await B.adm_ub_code_wait(m3, st)
    good = any("SESSION_STRING=" in o for o in m3.out)
    ok &= good
    print("   ", "✅ yangi kod bilan ulandi" if good else "❌ " + str(m3.out[-1][:150]))

    print()
    print("  — 3 marta ishlatilmagan kod —")
    FakeClient.calls.clear()
    FakeSent.n = 1
    B.userbot = None
    B.UB_LOGIN.update({"client": None, "phone": "", "hash": "", "admin_id": 0, "tries": 0})
    st = FakeState()
    await B.adm_ub_phone_wait(FakeMsg("+998976756546"), st)
    last = ""
    for _ in range(4):
        B.UB_LOGIN["hash"] = "HASH0"
        m = FakeMsg("12345")
        await B.adm_ub_code_wait(m, st)
        last = " ".join(m.out)
    good = "Devices" in last or "tozalang" in last
    ok &= good
    print("   ", "✅ to'xtadi va tozalashni tavsiya qildi" if good else "❌ " + last[:150])

    B.userbot = None
    print()
    print("  — userbot allaqachon ulangan bo'lsa —")
    B.userbot = FakeClient()
    FakeClient.calls.clear()
    B.UB_LOGIN.clear()
    st = FakeState()
    m = FakeMsg("+998976756546")
    await B.adm_ub_phone_wait(m, st)
    good = any("allaqachon ulangan" in o for o in m.out) and not FakeClient.calls
    ok &= good
    print("   ", "✅ kod so'ramadi (muddatsiz usul ko'rsatildi)" if good
          else "❌ " + str(m.out[-1][:120]))
    B.userbot = None

    print()
    print("  — noto'g'ri UZUNLIKDAGI kod Telegram'ga YUBORILMASIN —")
    B.userbot = None
    FakeClient.calls.clear()
    FakeSent.n = 1
    B.UB_LOGIN.clear()
    st = FakeState()
    await B.adm_ub_phone_wait(FakeMsg("+998976756546"), st)
    m = FakeMsg("123456")          # 6 raqam
    await B.adm_ub_code_wait(m, st)
    sent = [c for c in FakeClient.calls if "sign_in" in c]
    good = (not sent) and any("topib bo'lmadi" in o for o in m.out)
    ok &= good
    print("   ", "✅ Telegram'ga yuborilmadi (hash saqlandi)" if good
          else "❌ " + str(sent))

    print()
    print("  — nuqtali kod (12.355) to'g'ri o'qiladi —")
    B.userbot = None
    FakeClient.calls.clear()
    FakeSent.n = 1
    B.UB_LOGIN.clear()
    st = FakeState()
    await B.adm_ub_phone_wait(FakeMsg("+998976756546"), st)
    m = FakeMsg("12.355")
    await B.adm_ub_code_wait(m, st)
    sent = [c for c in FakeClient.calls if "sign_in" in c]
    good = bool(sent) and any("SESSION_STRING=" in o for o in m.out)
    ok &= good
    print("   ", "✅ 12.355 → 12355 → ulandi" if good else "❌ " + str(m.out[-1][:150]))

    print()
    print("  — 2 xato koddan keyin yangi kod beriladi —")
    B.userbot = None
    FakeClient.calls.clear()
    FakeSent.n = 1
    B.UB_LOGIN.clear()
    st = FakeState()
    await B.adm_ub_phone_wait(FakeMsg("+998976756546"), st)
    msgs = []
    for _ in range(3):
        m = FakeMsg("00000")
        await B.adm_ub_code_wait(m, st)   # xato kod
        msgs += m.out
    sent = [c for c in FakeClient.calls if "send_code" in c]
    good = len(sent) >= 2 and any("yangi kod yuborildi" in o for o in msgs)
    ok &= good
    print("   ", f"✅ yangi kod yuborildi (send_code={len(sent)})" if good else "❌")
    B.userbot = None

    print()
    print("NATIJA:", "✅ BARCHASI TO'G'RI" if ok else "❌ MUAMMO BOR")


asyncio.run(run())