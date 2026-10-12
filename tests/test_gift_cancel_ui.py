"""BEKOR QILISH TUGMASI — TO'LIQ OQIM (bosilishidan natijagacha).

REAL MUAMMO: "✅ Ha, bekor qil" bosilganda HECH NARSA bo'lmasdi.

SABAB: tasdiqlash tugmasi callback_data "adm:gift_cancel:confirm_all"
yuborardi, lekin handler "adm:gift_cancel_" (OST CHIZIG'I) bilan
ro'yxatlan edi. `"adm:gift_cancel:confirm_all".startswith("adm:gift_cancel_")`
= False -> aiogram butunlay ushladi -> tugma jimgina qoldi.

Ikkinchi mojarrato'qnashuv: jamlash handler'i ("adm:gift_cancel") bitta
buyurtma handler'ini ("adm:gift_cancel_one:") ham ushlab olardi.

Bu test:
  1) HAR BIR tugmaning callback_data si RO'YXATLANGAN handler bilan MOS
     kelishini tekshiradi (aiogram shuni talab qiladi)
  2) to'liq oqimni bosib ko'radi: gone -> confirm_all -> pul qaytadi
  3) mos kelmovchi callback_data larni ANIQ topadi
"""
import asyncio
import re
import sys
import time

sys.path.insert(0, '.')
import bot as B  # noqa: E402

SRC = open("bot.py", encoding="utf-8").read()
ok = True


def check(cond, msg):
    global ok
    ok &= bool(cond)
    print(f"  {'✅' if cond else '❌'} {msg}")


def registered_handlers():
    """(filter, func_name) ro'yxatini deklaratsiya tartibida."""
    out = []
    lines = SRC.split("\n")
    for i, l in enumerate(lines):
        m = re.match(r'@admin_router\.callback_query\((.*)\)\s*$', l.strip())
        if m and i + 1 < len(lines):
            f = re.match(r'async def (\w+)', lines[i + 1].strip())
            if f:
                out.append((m.group(1), f.group(1)))
    return out


def matches(filt: str, data: str) -> bool:
    if f'F.data == "{data}"' in filt:
        return True
    m = re.search(r'startswith\("([^"]+)"\)', filt)
    return bool(m and data.startswith(m.group(1)))


print("=" * 68)
print("1) BARCHA TUGMALAR HANDLERGA MOS KELADIMI?")
print("=" * 68)
handlers = registered_handlers()
cbs = sorted(set(re.findall(r'callback_data="(adm:gift[^"]*)"', SRC))
             | set(re.findall(r'callback_data=f"(adm:gift[^"]*)"', SRC)))
# dinamik ma'lumotli tugmalar ({o.get('id')}) — shablon bo'yicha tekshiramiz
static = [c for c in cbs if "{" not in c]
dynamic = [c for c in cbs if "{" in c]

for data in static:
    hit = next((name for filt, name in handlers if matches(filt, data)), None)
    check(hit is not None, f"{data} -> " + (hit or "HANDLER YO'Q"))

for tmpl in dynamic:
    prefix = tmpl.split("{")[0]
    hit = next((name for filt, name in handlers
                if prefix in filt or matches(filt, prefix + "X")), None)
    check(hit is not None, f"{tmpl}... -> " + (hit or "HANDLER YO'Q"))

print()
print("=" * 68)
print("2) MOJARATO'QNASHUV YO'QMI?")
print("=" * 68)
for i, (f1, n1) in enumerate(handlers):
    for f2, n2 in handlers[i + 1:]:
        if f1 == f2 and n1 != n2:
            check(False, f"{n1} va {n2} bir xil filtr bilan: {f1}")
# aniq mojarrato'qnashuvni tekshiramiz
check(not any(
    "adm:gift_cancel_one" in f for f, _ in handlers
), "eski 'adm:gift_cancel_one:' prefiksi qolmagan")

bulk = next((f for f, n in handlers if n == "adm_gift_cancel"), "")
single = next((f for f, n in handlers if n == "adm_gift_cancel_one"), "")
check("adm:gift_drop" not in bulk or "adm:gift_drop" in single,
      "jamlash va bitta-buyurtma prefikslari ajratilgan")
check("adm:gift_cancel" not in single, "bitta-buyurtma handler'i jamlashni ushlab olmaydi")

print()
print("=" * 68)
print("3) TO'LIQ OQIM: tasdiq -> bekor qilish -> pul qaytadi")
print("=" * 68)


class Msg:
    def __init__(self):
        self.ans = []

    async def answer(self, t, **kw):
        self.ans.append((t, kw))

    async def edit_text(self, t, **kw):
        self.ans.append((t, kw))


class Call:
    def __init__(self, data):
        self.data = data
        self.message = Msg()
        self.alerts = []
        self.from_user = type("U", (), {"id": 8307046273, "username": "boss"})()

    async def answer(self, text="", **kw):
        self.alerts.append(text)

    async def edit_text(self, t, **kw):
        self.message.ans.append((t, kw))

    def buttons(self):
        out = []
        for _, kw in self.message.ans:
            mk = kw.get("reply_markup")
            if mk:
                for row in mk.inline_keyboard:
                    out.append([(b.text, b.callback_data) for b in row])
        return out


async def main():
    global ok
    B.ADMIN_IDS = {8307046273}
    B.ADMIN_SESSIONS[8307046273] = time.time()
    u, _ = B.db.get_or_create_user(555, "aliy", "Aliy")
    u["balance"] = 0
    B.db.data["orders"] = {
        f"o{i}": {"id": f"o{i}", "user_id": 555, "kind": "gift", "gift": "bear",
                  "stars": 15, "title": "Ayq", "recipient": "bobur",
                  "status": "completed", "price": 3000, "price_uzs": 3000,
                  "gift_failed": True, "gift_attempts": 5}
        for i in range(5)
    }
    B.db.save()

    # --- 1-qadam: "🚫 Kutayotgan gift'larni bekor qilish" ---
    c1 = Call("adm:gift_cancel:gone")
    await B.adm_gift_cancel(c1)
    check(len(c1.message.ans) == 1, "1-qadam: tasdiq oynasi ko'rsatildi")
    txt = c1.message.ans[0][0] if c1.message.ans else ""
    check("Ishonchingiz komilmi" in txt, "1-qadam: tasdiq so'raldi")
    check("5</b> ta gift" in txt, "1-qadam: nechta gift ko'rsatildi")
    check("15 000" in txt, "1-qadam: qancha pul qaytariladi ko'rsatildi")

    btns = c1.buttons()
    flat = [b for row in btns for b in row]
    ha = [b for b in flat if "Ha, bekor qil" in b[0]]
    check(bool(ha), "1-qadam: '✅ Ha, bekor qil' tugmasi bor")
    check(bool(ha) and ha[0][1] == "adm:gift_cancel:confirm_all",
          f"tasdiqlash callback_data = {ha[0][1] if ha else None}")
    check(bool(ha) and matches(bulk, ha[0][1]),
          "tasdiqlash callback_data HANDLERGA MOS")

    # --- 2-qadam: "✅ Ha, bekor qil" ---
    c2 = Call(ha[0][1])
    await B.adm_gift_cancel(c2)
    txt2 = c2.message.ans[0][0] if c2.message.ans else ""
    first_line = txt2.splitlines()[0] if txt2 else "(javob yo'q)"
    print(f"      javob: {first_line}")
    check("bekor qilindi" in txt2, "2-qadam: bekor qilindi")
    check("15 000" in txt2, "2-qadam: qaytarilgan summa ko'rsatildi")
    check(B.db.get_user(555)["balance"] == 15000,
          f"2-qadam: balans 0 -> {B.db.get_user(555)['balance']}")
    check(len(B.stuck_gift_orders()) == 0, "2-qadam: qoldiq gift yo'q")
    check(all(o.get("gift_cancelled") for o in B.db.data["orders"].values()),
          "barcha buyurtmalar bekor qilingan")

    # --- boshqa action'lar ham ishlashi kerak ---
    print()
    print("  Boshqa action'lar:")
    u["balance"] = 0
    B.db.data["orders"] = {
        "z1": {"id": "z1", "user_id": 555, "kind": "gift", "gift": "bear",
               "stars": 15, "recipient": "b", "status": "completed",
               "price": 1000, "price_uzs": 1000, "gift_failed": True,
               "created_at": "2020-01-01T00:00:00+00:00"},
        "z2": {"id": "z2", "user_id": 555, "kind": "gift", "gift": "heart",
               "stars": 15, "recipient": "b", "status": "completed",
               "price": 2000, "price_uzs": 2000, "gift_failed": True,
               "created_at": "2026-10-12T00:00:00+00:00"},
    }
    B.db.save()
    c3 = Call("adm:gift_cancel:confirm_old")
    await B.adm_gift_cancel(c3)
    t3 = c3.message.ans[0][0] if c3.message.ans else ""
    check("bekor qilindi" in t3, "confirm_old: faqat eski bekor qilindi")
    check(B.db.data["orders"]["z2"].get("gift_cancelled") is not True,
          "confirm_old: yangi buyurtma tegilmadi")
    check(B.db.data["orders"]["z1"].get("gift_cancelled") is True,
          "confirm_old: eski buyurtma bekor qilindi")

    # --- noto'g'ri action: crash bo'lmasin, xavfsiz "retry" ga qaytadi ---
    c4 = Call("adm:gift_cancel:nonsense")
    await B.adm_gift_cancel(c4)
    t4 = c4.message.ans[0][0] if c4.message.ans else ""
    check(bool(t4), "noma'lum action xatosiz qaytariladi (crash emas)")
    check("Ishonchingiz komilmi" in t4,
          "noma'lum action -> xavfsiz tasdiq oynasi (avtomatik bekor qilmaydi)")
    check(B.db.data["orders"]["z2"].get("gift_cancelled") is not True,
          "noma'lum action hech narsani bekor qilmagan")

    print()
    print("=" * 68)
    print("NATIJA:", "✅ BARCHASI TO'G'RI" if ok else "❌ MUAMMO BOR")
    print("=" * 68)
    return 0 if ok else 1


sys.exit(asyncio.run(main()))