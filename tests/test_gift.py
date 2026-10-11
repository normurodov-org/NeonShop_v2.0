import asyncio, sys, time, types
sys.path.insert(0, '.')
import bot as B


adm = []


async def notify(t):
    adm.append(str(t))


B.notify_admins = notify
B.GIFT_POLL_INTERVAL = 0.05
B.GIFT_RETRY_DELAY = 0.0
B._safe_send = lambda uid, text, **kw: asyncio.sleep(0)


class FakeBot:
    async def send_message(self, chat_id, text, **kw):
        return types.SimpleNamespace(message_id=1)


B.bot = FakeBot()


class FakeGift:
    def __init__(self, gid, price):
        self.id = gid
        self.price = price


class FakeUserbot:
    def __init__(self, gifts, fail=False):
        self.gifts = gifts
        self.fail = fail
        self.sent = []

    async def get_available_gifts(self):
        return self.gifts

    async def send_gift(self, chat_id, gift_id, **kw):
        if self.fail:
            raise RuntimeError("PAYMENT_REQUIRED")
        self.sent.append((chat_id, gift_id))
        return True


def add_order(oid, gift="bear", recipient="aliy", status="completed", stars=None):
    B.db.data["orders"][oid] = {
        "id": oid, "user_id": 555, "kind": "gift",
        "title": "🧸 Ayiqcha", "recipient": recipient,
        "stars": stars, "gift": gift, "status": status, "source": "webapp",
    }


async def run_worker(cycles=8, wait=0.15):
    """process_gift_orders ni qisqa sikl bilan ishga tushiramiz."""
    task = asyncio.create_task(B.process_gift_orders())
    for _ in range(cycles):
        await asyncio.sleep(wait)
        if all(o.get("gift_sent")
               for o in B.db.data["orders"].values() if o.get("kind") == "gift"):
            break
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


async def run():
    ok = True
    B.db.data["users"]["555"] = B.db.data["users"].get("555") or {
        "id": 555, "username": "aliy", "balance": 0}
    B.db.get_or_create_user(555, "aliy", "Aliy")

    print("=" * 72)
    print("1) USERBOT YO'Q — gift worker jimgina o'tmasligi kerak")
    print("=" * 72)
    B.userbot = None
    B.db.data["orders"] = {}
    add_order("ord_g1")
    adm.clear()
    await run_worker(8)
    o = B.db.data["orders"]["ord_g1"]
    warned = any("Gift yuborilmayapti" in a for a in adm)
    good = (not o.get("gift_sent")) and warned
    ok &= bool(good)
    print(f"  yuborildi: {bool(o.get('gift_sent'))} (kerak: False)")
    print(f"  admin ogohlantirildi: {warned} (kerak: True)")
    print(" ", "✅" if good else "❌")
    rt = B.db.data.get("settings", {}).get("runtime", {})
    print(f"  runtime.gift_worker = {rt.get('gift_worker')!r}, pending={rt.get('gift_pending')}")
    print("  ", "✅ holat bazaga yozildi" if rt.get("gift_worker") else "❌ holat yozilmadi")
    ok &= bool(rt.get("gift_worker"))

    print()
    print("=" * 72)
    print("2) USERBOT ULANGAN — gift yuborilishi")
    print("=" * 72)
    B.db.data["orders"] = {}
    add_order("ord_g2", gift="bear", recipient="aliy")
    ub = FakeUserbot([FakeGift(1, 15), FakeGift(2, 25), FakeGift(3, 50)])
    B.userbot = ub
    adm.clear()
    await run_worker(10)
    o = B.db.data["orders"]["ord_g2"]
    good = o.get("gift_sent") and ub.sent == [("aliy", 1)]
    ok &= bool(good)
    print(f"  gift_sent = {o.get('gift_sent')} (kerak: True)")
    print(f"  yuborildi: {ub.sent} (kerak: [('aliy', 1)] — 15⭐ = gift id 1)")
    print(" ", "✅" if good else "❌")

    print()
    print("=" * 72)
    print("3) BIR NECHTA buyurtma ketma-ket")
    print("=" * 72)
    B.db.data["orders"] = {}
    add_order("ord_a", gift="cake")        # 50
    add_order("ord_b", gift="cup")         # 100
    add_order("ord_c", gift="bear")        # 15
    ub = FakeUserbot([FakeGift(1, 15), FakeGift(2, 50), FakeGift(3, 100)])
    B.userbot = ub
    await run_worker(12)
    sent_map = dict(ub.sent)
    good = (B.db.data["orders"]["ord_a"]["gift_sent"]
            and B.db.data["orders"]["ord_b"]["gift_sent"]
            and B.db.data["orders"]["ord_c"]["gift_sent"])
    ok &= bool(good)
    print(f"  yuborilganlar: {sent_map}")
    print(f"  (cake 50⭐→2, cup 100⭐→3, bear 15⭐→1)")
    print(" ", "✅" if good else "❌")

    print()
    print("=" * 72)
    print("4) 'gift' maydoni yo'q (eski/webapp yozuvi) — stars dan topishi")
    print("=" * 72)
    B.db.data["orders"] = {}
    add_order("ord_d", gift=None, stars=25, recipient="bobur")
    ub = FakeUserbot([FakeGift(1, 15), FakeGift(2, 25)])
    B.userbot = ub
    await run_worker(10)
    o = B.db.data["orders"]["ord_d"]
    good = o.get("gift_sent") and ub.sent == [("bobur", 2)]
    ok &= bool(good)
    print(f"  gift maydoni yo'q, stars=25 → yuborildi: {ub.sent}")
    print(" ", "✅" if good else "❌")

    print()
    print("=" * 72)
    print("5) XATO — mos sovg'a topilmadi")
    print("=" * 72)
    B.db.data["orders"] = {}
    add_order("ord_e", gift="diamond")   # 100 stars
    ub = FakeUserbot([FakeGift(1, 15), FakeGift(2, 25)])   # 100 yo'q
    B.userbot = ub
    adm.clear()
    await run_worker(10)
    o = B.db.data["orders"]["ord_e"]
    good = bool(o.get("gift_error")) and bool(adm)
    ok &= bool(good)
    print(f"  gift_error: {o.get('gift_error')!r}")
    print(f"  admin xabari: {'✅ bor' if adm else '❌ yoq'}")
    print(" ", "✅" if good else "❌")

    print()
    print("=" * 72)
    print("6) Yuborish xatosi — retry va xato holati")
    print("=" * 72)
    B.db.data["orders"] = {}
    add_order("ord_f", gift="heart")
    ub = FakeUserbot([FakeGift(9, 15)], fail=True)
    B.userbot = ub
    await run_worker(10, wait=0.1)
    o = B.db.data["orders"]["ord_f"]
    good = (not o.get("gift_sent")) and bool(o.get("gift_error")) and not o.get("gift_processing")
    ok &= bool(good)
    print(f"  gift_sent={o.get('gift_sent')} (kerak False), "
          f"error={o.get('gift_error')!r}")
    print(f"  gift_processing={o.get('gift_processing')} (kerak False — qolib ketmasin)")
    print(" ", "✅" if good else "❌")

    print()
    print("=" * 72)
    print("6a) Cheksiz retry va admin spam yo'qligi")
    print("=" * 72)
    B.db.data["orders"] = {}
    add_order("ord_r", gift="heart")
    B.GIFT_MAX_ATTEMPTS = 3
    ub = FakeUserbot([FakeGift(9, 15)], fail=True)
    B.userbot = ub
    adm.clear()
    await run_worker(30)          # ko'p sikl — limitdan keyin to'xtashi kerak
    o = B.db.data["orders"]["ord_r"]
    err_msgs = [a for a in adm if "yuborishda xato" in a or "urinishlar tugadi" in a]
    stop_msg = [a for a in adm if "urinishlar tugadi" in a]
    good = (
        int(o.get("gift_attempts", 0)) == 3
        and o.get("gift_failed")
        and not o.get("gift_processing")
        and len(stop_msg) == 1
    )
    ok &= bool(good)
    print(f"  urinishlar: {o.get('gift_attempts')} (kerak 3, limitdan oshmasin)")
    print(f"  gift_failed: {o.get('gift_failed')} (kerak True)")
    print(f"  xato xabarlari: {len(err_msgs)} (kerak 3 — 30 siklda emas)")
    print(f"  'to'xtatildi' xabari: {len(stop_msg)} (kerak 1 ta)")
    print(" ", "✅ spam yo'q" if good else "❌ SPAM davom etmoqda")

    print()
    print("=" * 72)
    print("6b) Jarayon o'rtada o'lgan — eskirgan flag tiklanadi")
    print("=" * 72)
    B.db.data["orders"] = {}
    add_order("ord_h", gift="heart")
    B.db.data["orders"]["ord_h"]["gift_processing"] = True
    B.db.data["orders"]["ord_h"]["gift_processing_at"] = time.time() - 3600
    B.db.save()
    ub = FakeUserbot([FakeGift(9, 15)])
    B.userbot = ub
    await run_worker(10)
    o = B.db.data["orders"]["ord_h"]
    good = bool(o.get("gift_sent")) and ub.sent == [("aliy", 9)]
    ok &= bool(good)
    print(f"  gift_sent={o.get('gift_sent')} (kerak True), yuborildi={ub.sent}")
    print(" ", "✅ tiklandi" if good else "❌ DOIM BLOCK QOLIB KETARDI")

    print()
    print("=" * 72)
    print("7) Recipient yo'q bo'lsa — skip")
    print("=" * 72)
    B.db.data["orders"] = {}
    add_order("ord_g", recipient="")
    ub = FakeUserbot([FakeGift(1, 15)])
    B.userbot = ub
    await run_worker(8)
    o = B.db.data["orders"]["ord_g"]
    good = not o.get("gift_processing")
    ok &= bool(good)
    print(f"  gift_processing={o.get('gift_processing')} (kerak False)")
    print(" ", "✅" if good else "❌ QOLIB KETGAN!")

    print()
    print("=" * 72)
    print("8) WebApp ro'yxati — status 'completed' ga o'tadimi?")
    print("=" * 72)
    B.db.data["orders"] = {}
    add_order("ord_w", gift="cake", status="processing")
    ub = FakeUserbot([FakeGift(2, 50)])
    B.userbot = ub
    await run_worker(10)
    o = B.db.data["orders"]["ord_w"]
    good = o.get("gift_sent") and o.get("status") == "completed"
    ok &= bool(good)
    print(f"  gift_sent={o.get('gift_sent')}, status={o.get('status')!r}")
    print(" ", "✅ webapp 'Yuborildi' ko'rsatadi" if good else "❌ webapp 'Yuborilmoqda' da qoladi")


    print()
    print("NATIJA:", "✅ BARCHASI TO'G'RI" if ok else "❌ MUAMMO BOR")


asyncio.run(run())