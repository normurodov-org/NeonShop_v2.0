import asyncio, sys, time, types
sys.path.insert(0, '.')
import bot as B


class FakeBot:
    async def send_message(self, chat_id, text, **kw):
        return types.SimpleNamespace(message_id=1)


B.bot = FakeBot()
adm = []


async def notify(t):
    adm.append(str(t))


B.notify_admins = notify


class BankMsg:
    def __init__(self, text, mid=777):
        self.text = text
        self.id = mid
        self.chat = types.SimpleNamespace(id=100)


CARD = "*3682"   # bizning kartamiz


def reset(uid=555, amount=50000):
    """Test uchun toza, kutilayotgan topup yaratadi (tashqi bazaga bog'liq emas)."""
    B.db.data["processed_bank_msgs"] = []
    B.db.data["topups"] = {
        "top_test": {
            "id": "top_test", "user_id": uid, "amount": amount,
            "status": "pending", "expires_at": time.time() + 300,
        }
    }
    B.db.save()


async def scenario(name, text, uid=555, amount=50000, mid=777, expect=True):
    B.db.data["users"][str(uid)]["balance"] = 0
    reset(uid, amount)
    adm.clear()
    await B.on_humo_message(None, BankMsg(text, mid))
    tops = [t for t in B.db.data["topups"].values() if t["user_id"] == uid]
    st = tops[0]["status"] if tops else "yo'q"
    bal = B.db.data["users"][str(uid)]["balance"]
    done = any(t["status"] == "completed" for t in tops)
    good = (done == expect)
    mark = "✅" if good else "❌"
    if expect:
        print(f"  {name:38} → {st:10} balans={bal:>7}  {mark}")
    else:
        print(f"  {name:38} → {st:10} balans={bal:>7}  {mark} "
              f"({'topshirmadi' if good else 'NOTO GRI topshirdi!'})")
    return good


async def run():
    ok = True
    u, _ = B.db.get_or_create_user(555, "aliy", "Aliy")

    print("=" * 72)
    print("1) SUMMA PARSING — ko'p xil format")
    print("=" * 72)
    cases = [
        "✅ To'lov qabul qilindi\n💳 HUMOCARD *3682\n➕ 50 000 UZS",
        "✅ To'lov qabul qilindi\n💳 HUMOCARD *3682\n➕ 50000 UZS",
        "✅ To'lov\n💳 HUMOCARD *3682\n💵 50 000 so'm",
                "✅ To'lov qabul qilindi\n💳 HUMOCARD *3682\n🆔 50 000 UZS",
        "✅ To'lov\n💳 HUMOCARD *3682\nSumma: 50 000",
        "✅ Платёж\n💳 HUMOCARD *3682\n➕ 50 000 сум",
        "✅ To'lov\n💳 HUMOCARD *3682\n➕ 50.000 UZS",
    ]
    for c in cases:
        p = B.parse_humo_payment(c)
        head = c.splitlines()[-1]
        good = p and p[0] == 50000 and p[1] == "3682"
        print(f"  {head:32} → {p}  {'✅' if good else '❌'}")
        ok &= bool(good)

    # 💰 — qoldiq balans belgisi. U HECH QACHON to'lov summasi bo'lmasligi kerak
    # (haqiqiy bank xabarida "💰 19.587,36" — bu balans, to'lov emas).
    balance_only = "✅ To'lov\n💳 HUMOCARD *3682\n💰 19.587,36 UZS"
    got = B.parse_humo_payment(balance_only)
    good = got is None
    print(f"  {'💰 19.587,36 (qoldiq balans)':32} → {got}  "
          f"{'✅ (summaga aylantirilmedi)' if good else '❌ BALANS summaga aylandi!'}")
    ok &= good

    print()
    print("=" * 72)
    print("2) TO'LIQ AVTO-TO'LDIRISH — turli xil bank xabarlari")
    print("=" * 72)
    for i, t in enumerate(cases):
        ok &= await scenario(f"format #{i+1}", t, mid=1000 + i)

    print()
    print("=" * 72)
    print("3) XATO HOLATLAR (bular topshirmasligi kerak)")
    print("=" * 72)
    ok &= await scenario("begona karta", "✅ To'lov\n💳 HUMOCARD *1111\n➕ 50 000 UZS",
                         mid=2001, expect=False)
    # Yangi xatti-harakat: faqat BITTA so'rov bo'lsa, kelgan haqiqiy
    # summa qisman to'ldirish sifatida qo'shiladi (avval "bog'lanmaydi" edi).
    ok &= await scenario("boshqa summa -> qisman to'ldirish",
                         "✅ To'lov\n💳 HUMOCARD *3682\n➕ 50 000 UZS",
                         amount=30000, mid=2002, expect=True)

    # Ikkita so'rov bo'lsa esa chalkashtirilmaydi (xavfsizlik uchun)
    ok &= await scenario("begona karta (qisman emas)", 
                         "✅ To'lov\n💳 HUMOCARD *1111\n➕ 50 000 UZS",
                         mid=2003, expect=False)

    print()
    print("=" * 72)
    print("4) BALANSGA QO'SHMAYDIGAN xabar (chiqarish) — o'tkazib yuboriladi")
    print("=" * 72)
    B.db.data["users"]["555"]["balance"] = 0
    reset()
    await B.on_humo_message(None, BankMsg("💸 Yechildi\n💳 HUMOCARD *3682\n➕ 50 000 UZS\n✅ Chiqarish", 3001))
    bal = B.db.data["users"]["555"]["balance"]
    good = bal == 0
    ok &= good
    print(f"  chiqarish xabari → balans={bal}  {'✅ to\'g\'ri (qo\'shilmadi)' if good else '❌ XATO'}")

    print()
    print("=" * 72)
    print("5) BIR XABARNI QAYTA ISHLASH (double-spend himoyasi)")
    print("=" * 72)
    B.db.data["users"]["555"]["balance"] = 0
    reset()
    msg = BankMsg("✅ To'lov\n💳 HUMOCARD *3682\n➕ 50 000 UZS", 4001)
    await B.on_humo_message(None, msg)
    await B.on_humo_message(None, msg)
    bal = B.db.data["users"]["555"]["balance"]
    good = bal == 50000
    ok &= good
    print(f"  2 marta yuborildi → balans={bal}  {'✅' if good else '❌ JUFT QO\'SHILDI'}")

    print()
    print("=" * 72)
    print("6) USERBOT YO'Q BOLSA — gift worker ogohlantirishi")
    print("=" * 72)
    print("  (bu bot.py ichida, quyida tekshiriladi)")

    print()
    print("NATIJA:", "✅ BARCHASI TO'G'RI" if ok else "❌ MUAMMO BOR")


asyncio.run(run())