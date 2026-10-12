"""Gift avtomatik yuborilishi — tuzatilgan muammolar.

MUAMMOLAR (shu fayl tekshiradi):
1. Mijoz matni Pyrogram tomonidan markdown/HTML deb talqin qilinardi
   ("<b>salom" -> entity) -> Telegram rad qilardi -> sovg'a UMUMAN
   yuborilmay qolardi. Endi parse_mode=DISABLED (verbatim).
2. Qabul qiluvchi noto'g'ri tozalangan: "https://t.me/bobur" yoki
   "@bobur " kabi shakllar Telegram'da topilmaydi -> yuborilmaydi.
3. Dasturiy xatolar (masalan "NoneType has no len()") buyurtmani
   yopib qo'yardi -> mijoz pulini to'lab giftini olmay qolardi.
   Endi userbot ulanganda avtomatik tiklanadi.
4. Qisqarib qolgan gift'lar hech qanday ogohlantirish bermasdi.
"""
import asyncio
import re
import sys

sys.path.insert(0, '.')
import bot as B  # noqa: E402

SRC = open("bot.py", encoding="utf-8").read()
SRV = open("server.ts", encoding="utf-8").read()

ok = True


def check(cond, msg):
    global ok
    ok &= bool(cond)
    print(f"  {'✅' if cond else '❌'} {msg}")


print("=" * 68)
print("1) clean_gift_text — mijoz matni xavfsiz")
print("=" * 68)
cases = [
    ("Sizga omad! 🌸", "oddiy matn"),
    ("  ko'p   bo'sh  joy ", "bo'sh joylar siqiladi"),
    ("<b>salom", "HTML teglari SAQLANADI (verbatim)"),
    ("A*B*C_", "markdown belgilari saqlanadi"),
    ("birinchi\nikkinchi", "qator uzilishi"),
    ("nul\x00belgi", "boshqaruv belgisi"),
    ("x" * 300, "uzunlik 200"),
]
for raw, label in cases:
    got = B.clean_gift_text(raw)
    print(f"      {label:42} -> {got[:40]!r}")
check(B.clean_gift_text("Sizga omad!") == "Sizga omad!", "oddiy matn o'zgarmaydi")
check("<b>" in B.clean_gift_text("<b>salom"), "HTML teglari olib tashlanMAYdi")
check("\x00" not in B.clean_gift_text("nul\x00belgi"), "boshqaruv belgisi tozalandi")
check(len(B.clean_gift_text("x" * 300)) == 200, "200 belgiga qisqartirildi")
check(B.clean_gift_text(None) == "", "None -> bo'sh matn")

print()
print("=" * 68)
print("2) normalize_gift_recipient — barcha shakllar bir xil")
print("=" * 68)
for raw, exp in (
    ("@bobur", "bobur"), ("bobur", "bobur"), ("  @bobur  ", "bobur"),
    ("https://t.me/bobur", "bobur"), ("http://t.me/bobur", "bobur"),
    ("t.me/bobur", "bobur"), ("telegram.dog/bobur", "bobur"),
    ("t.me/bobur/", "bobur"), ("bobur_1", "bobur_1"),
    ("@bob ur", "bobur"), ("https://t.me/bobur?start=1", "boburstart1"),
):
    got = B.normalize_gift_recipient(raw)
    print(f"      {raw!r:32} -> {got!r}")
    check(got == exp, f"{raw!r} -> {exp!r}")
check(B.normalize_gift_recipient("") == "", "bo'sh -> bo'sh")
check(B.normalize_gift_recipient(None) == "", "None -> bo'sh")

print()
print("=" * 68)
print("3) send_gift parse_mode=DISABLED (mijoz matni verbatim)")
print("=" * 68)
check("parse_mode=" in SRC, "send_gift ga parse_mode beriladi")
check("UbParseMode.DISABLED" in SRC, "DISABLED ishlatiladi")
check("text=gift_text or None" in SRC, "matn uzatiladi")
check(SRC.count("await gclient.send_gift(") == 1, "bitta send_gift chaqiruvi")

# endi haqiqiy chaqiruvni tekshiramiz
calls = []


class FS:
    def __init__(self, e):
        self.emoji = e


class G:
    def __init__(self, i, e, p):
        self.id, self.sticker, self.price = i, FS(e), p


class UB:
    async def get_available_gifts(self):
        return [G(102, "🧸", 15)]

    async def send_gift(self, chat_id, gift_id, text=None, parse_mode=None,
                        hide_my_name=None):
        calls.append({"chat": chat_id, "gift": gift_id, "text": text,
                      "pm": str(parse_mode), "anon": hide_my_name})
        return True


async def main():
    global ok
    B.GIFT_POLL_INTERVAL = 0.05
    B.GIFT_RETRY_DELAY = 0.0
    B.userbot = UB()
    B.db.get_or_create_user(555, "aliy", "Aliy")

    async def run(text, anon):
        calls.clear()
        B.db.data["orders"] = {"o1": {
            "id": "o1", "user_id": 555, "kind": "gift", "gift": "bear",
            "stars": 15, "title": "🧸", "recipient": "https://t.me/bobur",
            "status": "completed", "anon": anon, "gift_text": text,
        }}
        B.db.save()
        t = asyncio.create_task(B.process_gift_orders())
        for _ in range(20):
            await asyncio.sleep(0.05)
            if B.db.data["orders"]["o1"].get("gift_sent"):
                break
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass
        return calls[0] if calls else {}

    print()
    c = await run("<b>Sizga omad! _barchasi yaxshi_", True)
    check(bool(c), "gift yuborildi")
    check(c.get("pm", "").endswith("DISABLED"),
          f"parse_mode = DISABLED ({c.get('pm')})")
    check(c.get("text") == "<b>Sizga omad! _barchasi yaxshi_",
          f"matn o'zgarmasdan yuborildi: {c.get('text')!r}")
    check(c.get("anon") is True, "anonim (hide_my_name=True)")
    check(c.get("chat") == "bobur",
          f"t.me havolasi tozalandi: {c.get('chat')!r}")

    c2 = await run("", False)
    check(c2.get("anon") is False, "profil ko'rinadi (hide_my_name=False)")
    check(c2.get("text") is None, "matn yo'q -> None")
    check(c2.get("pm") in ("None", ""),
          f"matn yo'q -> parse_mode berilmadi ({c2.get('pm')})")

    print()
    print("=" * 68)
    print("4) recover_stuck_gifts — yutilgan buyurtmalar tiklanadi")
    print("=" * 68)
    B.db.data["orders"] = {
        "i1": {"id": "i1", "kind": "gift", "gift_sent": False,
               "gift_attempts": 5, "gift_failed": True,
               "gift_needs_review": True,
               "gift_error": "object of type 'NoneType' has no len()"},
        "i2": {"id": "i2", "kind": "gift", "gift_sent": False,
               "gift_attempts": 5, "gift_failed": True,
               "gift_error": "Telegram says: -400"},
        "done": {"id": "done", "kind": "gift", "gift_sent": True},
    }
    B.db.save()
    n = B.recover_stuck_gifts()
    check(n == 1, f"faqat 1 ta tiklandi (ichki xato bo'lgan): {n}")
    o1 = B.db.data["orders"]["i1"]
    check(o1["gift_attempts"] == 0, "i1 urishlar tozalandi")
    check(o1["gift_failed"] is False, "i1 muvaffaqiyatsiz belgisi olib tashlandi")
    check("gift_error" not in o1, "i1 xato tozalandi")
    o2 = B.db.data["orders"]["i2"]
    check(o2["gift_attempts"] == 5, "DOIMIY xato (Telegram -400) tegilmadi")
    check(o2.get("gift_failed") is True, "doimiy xato saqlandi")
    check(B.db.data["orders"]["done"]["gift_sent"] is True,
          "yuborilgan buyurtma tegilmadi")

    # eski yozuv: gift_needs_review yo'q, lekin xato matni ichki
    B.db.data["orders"]["i3"] = {"id": "i3", "kind": "gift", "gift_sent": False,
                                 "gift_attempts": 5, "gift_failed": True,
                                 "gift_error": "TypeError: bad"}
    B.db.save()
    n2 = B.recover_stuck_gifts()
    check(n2 == 1, f"eski yozuv (needs_review yo'q) ham tiklandi: {n2}")

    print()
    print("=" * 68)
    print("5) Qisqarib qolgan gift'lar ogohlantiriladi")
    print("=" * 68)
    check("gift_stuck" in SRC, "runtime da gift_stuck sanaladi")
    check("Yuborilmagan gift buyurtmalari" in SRC, "admin ga xabar yuboriladi")
    check("Gift qayta yuborish" in SRC, "tuzatish yo'li ko'rsatiladi")
    check("stuck_notified_at" in SRC, "eslatma 5 daqiqada bir marta")

    print()
    print("=" * 68)
    print("6) server.ts — qabul qiluvchi va matn")
    print("=" * 68)
    m = re.search(r"let recipient = \(username \|\| ''\)(.*?)slice\(0, 32\);", SRV, re.S)
    check(m is not None, "recipient normalizatsiyasi bor")
    if m:
        js = m.group(1)
        check("t.me" in js or "telegram" in js, "t.me havolasi tozalanadi")
        check("^@+" in js or "@+" in js, "'@' tozalanadi")
        check("user.username" not in js,
              "bo'sh bo'lsa mijozning o'z usernami ishlatilmaydi")
    check(".replace(/[<>&]/g, '')" not in SRV,
          "gift_text dagi teglar olib tashlanmaydi (verbatim)")

    print()
    print("=" * 68)
    print("NATIJA:", "✅ BARCHASI TO'G'RI" if ok else "❌ MUAMMO BOR")
    print("=" * 68)
    return 0 if ok else 1


sys.exit(asyncio.run(main()))