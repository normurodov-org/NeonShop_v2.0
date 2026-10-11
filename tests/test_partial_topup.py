import asyncio, sys, time, types
sys.path.insert(0, '.')
import bot as B


class FakeMsg:
    def __init__(self, text, mid=1):
        self.text = text
        self.id = mid
        self.chat = types.SimpleNamespace(id=100)


B.bot = types.SimpleNamespace(send_message=lambda *a, **k: asyncio.sleep(0))
adm = []


async def notify(t):
    adm.append(str(t))


B.notify_admins = notify


def reset(topups):
    B.db.data["topups"] = topups
    B.db.data["processed_bank_msgs"] = []
    for uid in (555, 777):
        if str(uid) in B.db.data["users"]:
            B.db.data["users"][str(uid)]["balance"] = 0
    B.db.save()


def mk_topup(tid, uid, amount):
    return {"id": tid, "user_id": uid, "amount": amount,
            "status": "pending", "expires_at": time.time() + 300}


def bank(amount, card="3682", mid=1):
    return FakeMsg(
        "💸 To'lov\n➖ %s UZS\n📍 TRANSPORT TOLOV>TOS\n"
        "💳 HUMOCARD *%s\n🕓 15:16 11.10.2026\n💰 19.587,36 UZS"
        % (f"{amount:,}".replace(",", "."), card),
        mid,
    )


async def run():
    ok = True
    for uid, uname in ((555, "aliy"), (777, "bobur")):
        u, _ = B.db.get_or_create_user(uid, uname, uname)
        u["balance"] = 0
    B.db.save()

    # =====================================================================
    print("=" * 66)
    print("1) SIZNING HOILINGIZ: so'rov 10 000, yuborilgan 5 000")
    print("=" * 66)
    reset({"top_4aiqqiw": mk_topup("top_4aiqqiw", 555, 10000)})
    adm.clear()
    await B.on_humo_message(None, bank(5000, mid=1))
    t = B.db.data["topups"]["top_4aiqqiw"]
    bal = B.db.data["users"]["555"]["balance"]
    good = t["status"] == "completed" and bal == 5000 and t.get("partial")
    ok &= good
    print(f"  status      : {t['status']}")
    print(f"  balans      : {bal}  (kerak 5000 — yuborilgan haqiqiy summa)")
    print(f"  so'ralgan   : {t.get('requested_amount')}  (kerak 10000)")
    print(f"  qisman      : {t.get('partial')}")
    print(" ", "✅ AVTOMATIK BOG'LANDI" if good else "❌")

    # =====================================================================
    print()
    print("=" * 66)
    print("2) Aniq moslik — 10 000 so'rov, 10 000 yuborilgan")
    print("=" * 66)
    reset({"top_a": mk_topup("top_a", 555, 10000)})
    await B.on_humo_message(None, bank(10000, mid=2))
    t = B.db.data["topups"]["top_a"]
    bal = B.db.data["users"]["555"]["balance"]
    good = t["status"] == "completed" and bal == 10000 and not t.get("partial")
    ok &= good
    print(f"  balans: {bal} | qisman: {t.get('partial')}", "✅" if good else "❌")
    ok &= good

    # =====================================================================
    print()
    print("=" * 66)
    print("3) BIR NECHTA so'rov bo'lsa — chalkashlikda admin hal qiladi")
    print("=" * 66)
    B.db.data["users"]["555"]["balance"] = 0
    B.db.data["users"]["777"]["balance"] = 0
    reset({"top_x": mk_topup("top_x", 555, 10000),
           "top_y": mk_topup("top_y", 777, 20000)})
    adm.clear()
    await B.on_humo_message(None, bank(7000, mid=3))
    sx = B.db.data["topups"]["top_x"]["status"]
    sy = B.db.data["topups"]["top_y"]["status"]
    b1 = B.db.data["users"]["555"]["balance"]
    b2 = B.db.data["users"]["777"]["balance"]
    good = sx == "pending" and sy == "pending" and b1 == 0 and b2 == 0
    ok &= good
    print(f"  top_x: {sx} | top_y: {sy} | balans: {b1}/{b2}")
    print(f"  admin xabar yuborildi: {len(adm) > 0}")
    print(" ", "✅ chalkashtirilmadi (xavfsiz)" if good else "❌")

    # =====================================================================
    print()
    print("=" * 66)
    print("4) Begona karta — qisman to'ldirish HECH QACHON")
    print("=" * 66)
    reset({"top_c": mk_topup("top_c", 555, 10000)})
    await B.on_humo_message(None, bank(5000, card="1111", mid=4))
    t = B.db.data["topups"]["top_c"]
    bal = B.db.data["users"]["555"]["balance"]
    good = t["status"] == "pending" and bal == 0
    ok &= good
    print(f"  status: {t['status']} | balans: {bal}", "✅ rad etildi" if good else "❌")

    # =====================================================================
    print()
    print("=" * 66)
    print("5) So'rov yo'q — hech narsa bog'lanmasin")
    print("=" * 66)
    reset({})
    await B.on_humo_message(None, bank(3000, mid=5))
    print(f"  balans: {B.db.data['users']['555']['balance']}", "✅" )

    # =====================================================================
    print()
    print("=" * 66)
    print("6) To'lov so'rovi yo'qligi + keyin yaratilishi")
    print("=" * 66)
    B.db.data["users"]["555"]["balance"] = 0
    reset({})
    await B.on_humo_message(None, bank(8000, mid=6))   # so'rov yo'q -> rad
    print(f"  so'rovsiz 8000 -> balans {B.db.data['users']['555']['balance']}")
    reset({"top_late": mk_topup("top_late", 555, 8000)})
    await B.on_humo_message(None, bank(8000, mid=7))   # endi so'rov bor
    bal = B.db.data["users"]["555"]["balance"]
    good = bal == 8000
    ok &= good
    print(f"  so'rov bilan 8000 -> balans {bal}", "✅" if good else "❌")

    print()
    print("NATIJA:", "✅ BARCHASI TO'G'RI" if ok else "❌ MUAMMO BOR")


asyncio.run(run())