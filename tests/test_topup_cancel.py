"""TO'LOV SO'ROVI: BEKOR QILISH va MUDDATI.

REAL MUAMMOLAR (rasmdagi):
1. "❌ Bekor qilish" tugmasi BOSILGANDA HECH NARSA BO'LMADI.
   SABAB: tugma `cancel_inline_kb(f"topup_cancel:{id}")` orqali
   yaratilardi, lekin `topup_cancel` uchun HANDLER YO'Q edi —
   aiogram hech narsani ushlamagan.
2. "Qolgan vaqt: 0:00" bo'lsa ham so'rov "faol" qolardi.
   SABAB: `pending_topups()` faqat `status == "pending"` tekshirardi.
   Muddati o'tgan so'rov faqat `on_humo_message` (bank xabari
   kelganda) tozalardi — mijoz bankdan to'lamasa, so'rov ABADIY
   "pending" qolardi.

Bu test ikkalasini ham tekshiradi, va eng muhimi — butun TOG'MALAR
ro'yxatiga mos handler bormi (aiogram shartiga aynan shu).
"""
import asyncio
import re
import sys
import time

sys.path.insert(0, '.')
import bot as B  # noqa: E402

SRC = open("bot.py", encoding="utf-8").read()
SRV = open("server.ts", encoding="utf-8").read()

ok = True


def check(cond, msg):
    global ok
    ok &= bool(cond)
    print(f"  {'✅' if cond else '❌'} {msg}")


def handlers():
    out = []
    lines = SRC.split("\n")
    for i, l in enumerate(lines):
        m = re.match(r'@\w+\.callback_query\((.*)\)\s*$', l.strip())
        if m and i + 1 < len(lines):
            f = re.match(r'async def (\w+)', lines[i + 1].strip())
            if f:
                out.append((m.group(1), f.group(1)))
    return out


def matches(filt: str, data: str) -> bool:
    """filter shartiga mos keladimi?

    DIQQAT: `startswith` uchun `prefix + "X"` usuli ishlaydi, lekin
    `==` uchun ishlamaydi — aniq qiymatni solishtirish kerak.
    """
    if f'F.data == "{data}"' in filt:
        return True
    m = re.search(r'startswith\("([^"]+)"\)', filt)
    if m and data.startswith(m.group(1)):
        return True
    # "{id}" shablonli (f-string) tugmalar uchun
    tmpl = re.search(r'startswith\("([^"]*)"\)', filt)
    return False


print("=" * 68)
print("1) TUGMA -> HANDLER MOS KELISHI (aiogram sharti)")
print("=" * 68)
hs = handlers()
cbs = sorted(set(re.findall(r'cancel_inline_kb\(f?"([^"]+)"', SRC)))
print(f"      topup_cancel tugmalari: {cbs}")
for tmpl in cbs:
    # "{id}" qismi bor yoki yo'qligiga qarab mos filtrni izlaymiz
    hit = None
    for f, n in hs:
        if "{x}" in tmpl or "{" in tmpl:
            prefix = tmpl.split("{")[0]
            if matches(f, prefix + "X"):
                hit = n
                break
        else:
            if matches(f, tmpl):
                hit = n
                break
    check(hit is not None, f"{tmpl} -> " + (hit or "HANDLER YO'Q!"))

check("topup_cancel" in SRC and
      any("topup_cancel" in f for f, _ in hs),
      "topup_cancel uchun handler RO'YXATDAN o'tgan")

print()
print("=" * 68)
print("2) MUDDAT — 'Qolgan vaqt 0:00' bo'lsa so'rov FAOL qolmasin")
print("=" * 68)
check("def expire_stale_topups" in SRC, "expire_stale_topups() bor")
check("expire_stale_topups()\n    now = now_ms()" in SRC or
      "    expire_stale_topups()" in SRC,
      "pending_topups() eskirganlarni tozalaydi")
check("to_ms(t.get(\"expires_at\"), now) > now" in SRC,
      "pending_topups() muddatni ham tekshiradi")

# --- real tekshiruv ---
B.db.data["topups"] = {
    "yangi": {"id": "yangi", "user_id": 1, "amount": 1000, "status": "pending",
              "expires_at": B.now_ms() + 600_000},
    "eskirgan": {"id": "eskirgan", "user_id": 1, "amount": 50000,
                 "status": "pending",
                 "expires_at": B.now_ms() - 1000},
    "sekundda": {"id": "sekundda", "user_id": 1, "amount": 30000,
                 "status": "pending",
                 "expires_at": (B.now_ms() - 60_000) / 1000},  # ESKI format
}
B.db.save()
pend = B.pending_topups()
ids = {t["id"] for t in pend}
check("yangi" in ids, "muddati o'tmagan so'rov faol qoladi")
check("eskirgan" not in ids, "muddati o'tgan so'rov FAOL EMAS")
check("sekundda" not in ids,
      "eski formatdagi (sekund) o'tgan so'rov ham aniqlanadi")
check(B.db.data["topups"]["eskirgan"]["status"] == "expired",
      "o'tgan so'rov 'expired' deb belgilandi")
check(B.db.data["topups"]["sekundda"]["status"] == "expired",
      "eski formatdagi so'rov ham 'expired'")

print()
print("=" * 68)
print("3) BEKOR QILISH — to'liq oqim")
print("=" * 68)


class Msg:
    def __init__(self):
        self.ans = []

    async def answer(self, t, **kw):
        self.ans.append(t)

    async def edit_text(self, t, **kw):
        self.ans.append(t)

    async def edit_reply_markup(self, **kw):
        pass


class Call:
    def __init__(self, data):
        self.data = data
        self.message = Msg()
        self.alerts = []
        self.from_user = type("U", (), {"id": 555})()

    async def answer(self, text="", **kw):
        self.alerts.append(text)


async def main():
    B.db.data["topups"] = {
        "t_abc": {"id": "t_abc", "user_id": 555, "amount": 50000,
                  "status": "pending", "seq": 39, "amount_to_send": 50039,
                  "expires_at": B.now_ms() + 600_000},
    }
    B.db.save()

    c = Call("topup_cancel:t_abc")
    await B.cb_topup_cancel(c)
    t = B.db.data["topups"]["t_abc"]
    check(t["status"] == "cancelled", f"bekor qilindi: {t['status']}")
    check("ekor qilindi" in (c.alerts[0] if c.alerts else ""),
          f"foydalanuvchiga tasdiq: {c.alerts}")
    check("Xavfsiz" in (c.message.ans[0] if c.message.ans else ""),
          "xavfsizlik haqida ogohlantirildi (pul qaytarilmaydi)")

    # takror bekor qilish
    c2 = Call("topup_cancel:t_abc")
    await B.cb_topup_cancel(c2)
    check("allaqachon bekor qilingan" in (c2.alerts[0] if c2.alerts else ""),
          f"takror bekor qilish: {c2.alerts}")

    # yo'q so'rov
    c3 = Call("topup_cancel:yoq")
    await B.cb_topup_cancel(c3)
    check("topilmadi" in (c3.alerts[0] if c3.alerts else ""),
          f"yo'q so'rov: {c3.alerts}")

    # allaqachon to'ldirilgan
    B.db.data["topups"]["t_x"] = {"id": "t_x", "user_id": 555, "amount": 1000,
                                  "status": "completed"}
    B.db.save()
    c4 = Call("topup_cancel:t_x")
    await B.cb_topup_cancel(c4)
    check("to'ldirilgan" in (c4.alerts[0] if c4.alerts else ""),
          f"to'ldirilgan so'rov: {c4.alerts}")

    print()
    print("=" * 68)
    print("4) server.ts — muddat normalizatsiyasi (eski sekund qiymatlar)")
    print("=" * 68)
    check("function expiresMs" in SRV, "expiresMs() bor")
    check("v < 1e11 ? v * 1000 : v" in SRV,
          "sekund qiymatlar ms ga avtomatik konvert qilinadi")
    check("function isExpired" in SRV, "isExpired() bor")
    check(SRV.count("isExpired(t)") + SRV.count("isExpired(topup)") >= 3,
          "isExpired() status/simulate-pay/faol-so'rov joylarida ishlatiladi")
    check("Date.now() > topup.expires_at" not in SRV,
          "eski xavfli solishtirish qolmagan")

    print()
    print("=" * 68)
    print("NATIJA:", "✅ BARCHASI TO'G'RI" if ok else "❌ MUAMMO BOR")
    print("=" * 68)
    return 0 if ok else 1


sys.exit(asyncio.run(main()))