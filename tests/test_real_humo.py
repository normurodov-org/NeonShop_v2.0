import asyncio, sys, time, types
sys.path.insert(0, '.')
import bot as B


# =============================================================================
# Sizning HAQIQIY bank xabaringiz
# =============================================================================
REAL = """\U0001F4B8 To'lov
➖ 2.000,00 UZS
\U0001F4CD TRANSPORT TOLOV>TOS
\U0001F4B3 HUMOCARD *3682
\U0001F553 15:16 11.10.2026
\U0001F4B0 19.587,36 UZS"""

# Boshqa real ko'rinishlar
VARIANTS = [
    (REAL, 2000, "3682", "asl xabar"),
    ("\U0001F4B8 To'lov\n➖ 50.000,00 UZS\n\U0001F4B3 HUMOCARD *3682\n\U0001F4B0 120.587,36 UZS",
     50000, "3682", "katta summa"),
    ("\U0001F4B8 To'lov\n➖ 1.234,50 UZS\n\U0001F4B3 HUMOCARD *3682\n\U0001F4B0 5.000,00 UZS",
     1234, "3682", "kasrli"),
    ("\U0001F4B8 To'lov\n➖ 3.000,00 UZS\n\U0001F4B3 HUMOCARD *3682\n\U0001F553 15:16 11.10.2026\n\U0001F4B0 0,00 UZS",
     3000, "3682", "qoldiq 0"),
    # Eski formatlar ham ishlashi kerak
    ("✅ To'lov\n\U0001F4B3 HUMOCARD *3682\n➕ 50 000 UZS", 50000, "3682", "eski format"),
    ("✅ To'lov\n\U0001F4B3 HUMOCARD *3682\n💵 75 000 so'm", 75000, "3682", "so'm bilan"),
    ("✅ To'lov\n\U0001F4B3 HUMOCARD *3682\nSumma: 25 000", 25000, "3682", "Summa: bilan"),
]

# Qoldiq balans hech qachon summaga aylanmasligi kerak
BALANCE_TRAPS = [
    (REAL, 2000, "asli — 19587 EMAS, 2000"),
    ("\U0001F4B8 To'lov\n➖ 5.000,00 UZS\n\U0001F4B3 HUMOCARD *3682\n\U0001F4B0 99.999,99 UZS",
     5000, "trap: 99999 EMAS"),
    ("\U0001F4B8 To'lov\n➖ 10.000,00 UZS\n\U0001F4B3 HUMOCARD *3682\n💰 Balans: 1.000.000,00 UZS",
     10000, "trap: balans yozilgan"),
]


class FakeBot:
    async def send_message(self, chat_id, text, **kw):
        return types.SimpleNamespace(message_id=1)


B.bot = FakeBot()


async def notify(t):
    pass


B.notify_admins = notify


class BankMsg:
    def __init__(self, text, mid=1):
        self.text = text
        self.id = mid
        self.chat = types.SimpleNamespace(id=100)


def make_topup(amount, uid=777):
    B.db.data["topups"] = {
        "top_x": {"id": "top_x", "user_id": uid, "amount": amount,
                  "status": "pending", "expires_at": time.time() + 300}
    }
    B.db.data["processed_bank_msgs"] = []
    B.db.save()


async def full_flow(text, amount, mid):
    """To'liq oqim: topup yaratiladi → bank xabari → balans tekshiriladi."""
    B.db.get_or_create_user(777, "sardor", "Sardor")
    B.db.data["users"]["777"]["balance"] = 0
    make_topup(amount)
    await B.on_humo_message(None, BankMsg(text, mid))
    st = B.db.data["topups"]["top_x"]["status"]
    bal = B.db.data["users"]["777"]["balance"]
    return st, bal


async def run():
    ok = True

    print("=" * 70)
    print("1) PARSER — sizning haqiqiy xabaringiz")
    print("=" * 70)
    for l in REAL.splitlines():
        print("   ", l)
    print()
    p = B.parse_humo_payment(REAL)
    print(f"   natija: {p}")
    print(f"   to'lov = {p[0] if p else None} (kerak 2000), karta = {p[1] if p else None} (kerak 3682)")
    good = p == (2000, "3682")
    ok &= good
    print("  ", "✅ TO'G'RI" if good else "❌ XATO")

    print()
    print("=" * 70)
    print("2) REAL FORMATLAR (parser)")
    print("=" * 70)
    for text, exp_a, exp_c, name in VARIANTS:
        r = B.parse_humo_payment(text)
        good = r == (exp_a, exp_c)
        ok &= good
        print(f"  {name:22} → {str(r):22} {'✅' if good else '❌ (kutilgan %s)' % (exp_a,)}")

    print()
    print("=" * 70)
    print("3) QOLDIQ BALANS HECH QACHON SUMMA BO'LMASLIGI KERAK")
    print("=" * 70)
    for text, exp_a, name in BALANCE_TRAPS:
        r = B.parse_humo_payment(text)
        good = r and r[0] == exp_a
        ok &= good
        print(f"  {name:28} → {r[0] if r else None:<8} (kerak {exp_a}) {'✅' if good else '❌'}")

    print()
    print("=" * 70)
    print("4) TO'LIQ OQIM — topup → bank xabari → balans")
    print("=" * 70)
    for i, (text, exp_a, _, name) in enumerate(VARIANTS):
        st, bal = await full_flow(text, exp_a, 2000 + i)
        good = st == "completed" and bal == exp_a
        ok &= good
        print(f"  {name:22} status={st:10} balans={bal:>7} {'✅' if good else '❌'}")

    print()
    print("=" * 70)
    print("5) RAQAM NORMALIZATSIYASI")
    print("=" * 70)
    for raw, exp in [("2.000,00", 2000), ("19.587,36", 19587), ("50.000,00", 50000),
                     ("1.234.567,89", 1234567), ("50 000", 50000), ("50000", 50000),
                     ("1,50", 1), ("50,000", 50000), ("2.000", 2000),
                     ("1.500.000", 1500000), ("999", 999), ("0,00", 0)]:
        r = B._normalize_amount(raw)
        good = r == exp
        ok &= good
        print(f"  {raw:16} → {str(r):10} (kerak {exp}) {'✅' if good else '❌'}")

    print()
    print("=" * 70)
    print("6) BOSHQA SUMMA keldi — qisman to'ldirish (kelgan summa qo'shiladi)")
    print("=" * 70)
    st, bal = await full_flow(REAL, 30000, 9001)   # 30 000 so'ralgan, 2 000 keldi
    good = st == "completed" and bal == 2000
    ok &= good
    ok &= good
    res = "kelgan summa qo'shildi" if good else "xato"
    print("  so'ralgan 30 000, keldi 2 000 -> status=%s, balans=%s [%s]"
          % (st, bal, res))

    print()
    print("=" * 70)
    print("7) BEGONA KARTA — rad etilishi kerak")
    print("=" * 70)
    foreign = REAL.replace("*3682", "*1111")
    st, bal = await full_flow(foreign, 2000, 9002)
    good = st == "pending" and bal == 0
    ok &= good
    print(f"  karta *1111 → status={st}, balans={bal} {'✅' if good else '❌'}")

    print()
    print("=" * 70)
    print("8) BIR XABAR — faqat BIR marta hisoblanishi")
    print("=" * 70)
    B.db.get_or_create_user(777, "sardor", "Sardor")
    B.db.data["users"]["777"]["balance"] = 0
    make_topup(2000)
    await B.on_humo_message(None, BankMsg(REAL, 9100))
    await B.on_humo_message(None, BankMsg(REAL, 9100))
    bal = B.db.data["users"]["777"]["balance"]
    good = bal == 2000
    ok &= good
    print(f"  2 marta yuborildi → balans={bal} (kerak 2000) {'✅' if good else '❌'}")

    print()
    print("NATIJA:", "✅ BARCHASI TO'G'RI" if ok else "❌ MUAMMO BOR")


asyncio.run(run())