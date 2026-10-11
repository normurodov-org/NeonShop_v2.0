"""MENYULAR TESTI — barcha klaviatura va konfiguratsiyalar chiziladimi?

Nima uchun bu test kerak:
  Bir marta GIFTS tuple'iga emoji qo'shildi (4 -> 5 element), lekin
  webapp_config() va gifts_start() hali 4 ta element kutayotgan edi.
  Natija: "ValueError: too many values to unpack" ->
  /start da faqat "🚀" chiqib darhol o'chib ketdi, ASOSIY MENYU esa
  umuman ko'rinmadi. Foydalanuvchi hech narsani ko'rmadi.

  Bu test barcha menyularni REAL kod orqali chizib, kelajakda tuple
  yoki ma'lumot strukturasi o'zgarsa daroldan ko'rsatadi.
"""
import asyncio
import json
import sys

sys.path.insert(0, '.')
import bot as B  # noqa: E402

ok = True


def check(cond, msg):
    global ok
    ok &= bool(cond)
    print(f"  {'✅' if cond else '❌'} {msg}")


class FakeMsg:
    def __init__(self):
        self.sent = []
        self.bot = FakeBot()

    async def answer(self, text, **kw):
        self.sent.append((text, kw))
        return type("R", (), {"delete": self._noop})()

    async def _noop(self):
        return True

    async def edit_text(self, text, **kw):
        self.sent.append((text, kw))


class FakeBot:
    id = 42

    async def me(self):
        return type("Me", (), {"id": 42, "username": "NeonShopBot"})()


class FakeState:
    async def clear(self):
        pass

    async def set_state(self, *a, **kw):
        pass

    async def get_data(self):
        return {}

    async def update_data(self, **kw):
        pass


async def main():
    user, _ = B.db.get_or_create_user(12345, "neon", "Aliy")
    user["balance"] = 100000

    print("=" * 68)
    print("1) GIFTS tuzilmasi — barcha joylar MOS bo'lishi shart")
    print("=" * 68)
    check(all(len(g) == 5 for g in B.GIFTS),
          f"barcha GIFTS 5 elementli (topildi: {set(len(g) for g in B.GIFTS)})")
    check(len(B.GIFTS_BY_KEY) == len(B.GIFTS), "GIFTS_BY_KEY to'g'ri")
    check(len(B.GIFT_EMOJI) == len(B.GIFTS), "GIFT_EMOJI to'g'ri")
    # webapp_config FAQAT 4 element kutadi (JS bilan kelishuv)
    cfg = B.webapp_config()
    check(all(len(x) == 4 for x in cfg["gifts"]),
          "webapp_config gifts[] = 4 element (JS bilan mos)")

    print()
    print("=" * 68)
    print("2) webapp_config() — JSON ga aylanadimi?")
    print("=" * 68)
    try:
        s = json.dumps(cfg, ensure_ascii=False)
        check(len(s) > 100, f"JSON yig'ildi ({len(s)} belgi)")
        check("gifts" in cfg and len(cfg["gifts"]) == len(B.GIFTS),
              f"barcha {len(B.GIFTS)} ta sovg'a kirtilgan")
    except Exception as exc:  # noqa: BLE001
        check(False, f"JSON xatosi: {exc}")

    print()
    print("=" * 68)
    print("3) /start — ASOSIY MENYU (bu bug'da buzilgan edi)")
    print("=" * 68)
    m = FakeMsg()
    try:
        await B.send_main_menu(m, user)
        check(len(m.sent) == 1, "menyu yuborildi")
        kb = m.sent[0][1]["reply_markup"]
        check(len(kb.inline_keyboard) >= 6, f"{len(kb.inline_keyboard)} qator bor")
        check(all(b.text for row in kb.inline_keyboard for b in row),
              "hech bir tugmada bo'sh matn yo'q")
        print("      " + " / ".join(b.text for b in kb.inline_keyboard[0]))
    except Exception as exc:  # noqa: BLE001
        check(False, f"/start menyusi ishlamadi: {type(exc).__name__}: {exc}")

    print()
    print("=" * 68)
    print("4) GIFTlar menyusi (bu ham bug'da buzilgan edi)")
    print("=" * 68)
    m2 = FakeMsg()
    try:
        await B.gifts_start(m2, FakeState())
        kb = m2.sent[0][1]["reply_markup"]
        n = sum(len(r) for r in kb.inline_keyboard)
        check(n >= len(B.GIFTS), f"{n} ta tugma ({len(B.GIFTS)} ta sovg'a + bekor qilish)")
        check(any("Bekor" in b.text for row in kb.inline_keyboard for b in row),
              "bekor qilish tugmasi bor")
        for row in kb.inline_keyboard[:-1]:
            print("      " + " | ".join(b.text.replace("\n", " / ") for b in row))
    except Exception as exc:  # noqa: BLE001
        check(False, f"Giftlar menyusi ishlamadi: {type(exc).__name__}: {exc}")

    print()
    print("=" * 68)
    print("5) Boshqa barcha menyular chiziladimi?")
    print("=" * 68)
    keyboards = {
        "main_menu_kb": lambda: B.main_menu_kb(user),
        "cancel_inline_kb": lambda: B.cancel_inline_kb(),
        "admin_kb": lambda: B.admin_kb(),
        "webapp_inline_kb": lambda: B.webapp_inline_kb(user),
    }
    for nm, fn in keyboards.items():
        try:
            kb = fn()
            rows = len(kb.inline_keyboard)
            check(rows > 0, f"{nm}: {rows} qator")
        except Exception as exc:  # noqa: BLE001
            check(False, f"{nm} XATO: {type(exc).__name__}: {exc}")

    print()
    print("=" * 68)
    print("6) fmt() — None / bo'sh / noto'g'ri qiymatga chidamli")
    print("=" * 68)
    for v, exp in ((10000, "10 000"), (None, "0"), ("", "0"), (0, "0"),
                  ("10000", "10 000"), ("abc", "0")):
        got = B.fmt(v)
        print(f"      fmt({v!r:8}) = {got!r}")
        check(got == exp, f"fmt({v!r}) = {exp}")

    print()
    print("=" * 68)
    print("7) /start menyusi — noto'g'ri user ma'lumotlari bilan")
    print("=" * 68)
    for label, patch in (
        ("balance=None", {"balance": None}),
        ("username=None", {"username": None}),
        ("balance='abc'", {"balance": "abc"}),
        ("balance katta", {"balance": 10 ** 15}),
    ):
        u2 = dict(user)
        u2.update(patch)
        try:
            mm = FakeMsg()
            await B.send_main_menu(mm, u2)
            check(len(mm.sent) == 1, f"{label}: menyu chiqdi")
        except Exception as exc:  # noqa: BLE001
            check(False, f"{label}da menyu chiqmadi: {type(exc).__name__}: {exc}")

    print()
    print("=" * 68)
    print("8) Bazadagi NOTO'G'RI qiymatlar o'qilganda tozalanadimi?")
    print("=" * 68)
    B.db.data["users"]["777"] = {
        "id": 777, "username": "bad", "full_name": "Bad",
        "balance": None, "total_spent": "abc", "total_topup": "",
        "referrals_count": None,
    }
    B.db.save()
    bad = B.db.get_user(777)
    check(bad is not None, "foydalanuvchi topildi")
    for f in ("balance", "total_spent", "total_topup", "referrals_count"):
        check(isinstance(bad.get(f), int) and not isinstance(bad.get(f), bool),
              f"{f} = {bad.get(f)!r} ({type(bad.get(f)).__name__}) — int ga aylantirildi")
    try:
        await B.send_main_menu(FakeMsg(), bad)
        check(True, "noto'g'ri bazadagi foydalanuvchi uchun menyu ham chiqdi")
    except Exception as exc:  # noqa: BLE001
        check(False, f"menyu chiqmadi: {type(exc).__name__}: {exc}")

    print()
    print("=" * 68)
    print("NATIJA:", "✅ BARCHASI TO'G'RI" if ok else "❌ MUAMMO BOR")
    print("=" * 68)
    return 0 if ok else 1


sys.exit(asyncio.run(main()))