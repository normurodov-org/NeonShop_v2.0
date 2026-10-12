"""Eski kutilayotgan gift'larni bekor qilish (mijozga pul qaytariladi).

MUHIM IKKI SHART:
1. Bekor qilingan buyurtma gift worker tomonidan QAYTA ushlanmasin
   (aks holda pul qaytarilgan bo'lishiga qaramay sovg'a yuboriladi —
   mijozga ham, do'kon uchun zarar).
2. Mijozning puli HAR DOIM qaytarilsin — u sovg'a olmagan.
"""
import asyncio
import sys
import time

sys.path.insert(0, '.')
import bot as B  # noqa: E402

ok = True


def check(cond, msg):
    global ok
    ok &= bool(cond)
    print(f"  {'✅' if cond else '❌'} {msg}")


def mk_order(oid, uid, price=3000, age_days=0, **kw):
    from datetime import datetime, timedelta, timezone
    TZ = timezone.utc
    created = (datetime.now(TZ) - timedelta(days=age_days)).isoformat()
    o = {"id": oid, "user_id": uid, "kind": "gift", "gift": "bear",
         "stars": 15, "title": "🧸 Ayiqcha", "recipient": "bobur",
         "price": price, "price_uzs": price, "status": "completed",
         "created_at": created}
    o.update(kw)
    return o


async def main():
    print("=" * 68)
    print("1) Bitta buyurtmani bekor qilish + pul qaytarish")
    print("=" * 68)
    u, _ = B.db.get_or_create_user(555, "aliy", "Aliy")
    u["balance"] = 10_000
    B.db.data["orders"] = {"o1": mk_order("o1", 555, 3000)}
    B.db.save()

    okc, msg = B.cancel_gift_order("o1", refund=True)
    o1 = B.db.data["orders"]["o1"]
    check(okc, f"bekor qilindi: {msg}")
    check(o1.get("gift_cancelled") is True, "gift_cancelled belgilandi")
    check(o1.get("status") == "cancelled", "status = cancelled")
    check(o1.get("gift_sent") is True,
          "gift_sent=True (worker uni QAYTA ushlamaydi)")
    bal = B.db.get_user(555)["balance"]
    check(bal == 13_000, f"balans 10 000 -> {bal} (3 000 qaytarildi)")
    hist = [h for h in B.db.get_user(555).get("history", []) if h["type"] == "refund"]
    check(len(hist) == 1 and hist[0]["amount"] == 3000, "tarixga refund yozildi")

    print()
    print("=" * 68)
    print("2) Qayta bekor qilish / allaqachon yuborilgan")
    print("=" * 68)
    okc2, msg2 = B.cancel_gift_order("o1")
    check(not okc2 and "Allaqachon bekor" in msg2, f"ikkinchi marta: {msg2}")
    check(B.db.get_user(555)["balance"] == 13_000, "pul ikki marta qaytarilmadi")

    B.db.data["orders"]["o2"] = mk_order("o2", 555, 3000, gift_sent=True)
    B.db.save()
    okc3, msg3 = B.cancel_gift_order("o2")
    check(not okc3 and "allaqachon yuborilgan" in msg3.lower(), f"yuborilgan: {msg3}")

    okc4, msg4 = B.cancel_gift_order("yoq")
    check(not okc4 and "topilmadi" in msg4.lower(), f"yo'q buyurtma: {msg4}")

    print()
    print("=" * 68)
    print("3) refund=False — nomutanoshiblik holati")
    print("=" * 68)
    B.db.data["users"][str(555)]["balance"] = 0
    B.db.data["orders"]["o3"] = mk_order("o3", 555, 5000)
    B.db.save()
    okc5, msg5 = B.cancel_gift_order("o3", refund=False)
    check(okc5 and "qaytarilmadi" in msg5, f"{msg5}")
    check(B.db.get_user(555)["balance"] == 0, "pul qo'shilmadi")

    print()
    print("=" * 68)
    print("4) gift worker bekor qilinganni USHLAMAYDI")
    print("=" * 68)
    SENT = []

    class FS:
        def __init__(self, e):
            self.emoji = e

    class G:
        def __init__(self, i, e, p):
            self.id, self.sticker, self.price = i, FS(e), p

    class UB:
        async def get_available_gifts(self):
            return [G(102, "🧸", 15)]

        async def send_gift(self, **kw):
            SENT.append(kw)
            return True

    B.GIFT_POLL_INTERVAL = 0.05
    B.GIFT_RETRY_DELAY = 0.0
    B.userbot = UB()

    B.db.data["orders"] = {
        "keep": mk_order("keep", 555, 3000),        # yuborilishi KERAK
        "gone": mk_order("gone", 555, 3000),        # bekor qilingan
    }
    B.cancel_gift_order("gone", refund=True)
    SENT.clear()
    B.db.save()
    t = asyncio.create_task(B.process_gift_orders())
    for _ in range(25):
        await asyncio.sleep(0.05)
        if SENT:
            break
    t.cancel()
    try:
        await t
    except asyncio.CancelledError:
        pass
    check(len(SENT) == 1, f"faqat 1 ta gift yuborildi (bekor qilingan emas): {len(SENT)}")
    check(B.db.data["orders"]["gone"].get("gift_sent") is True,
          "bekor qilingan buyurtma yuborilgan deb qoldi (skip uchun)")

    print()
    print("=" * 68)
    print("5) stuck_gift_orders — yosh filtr")
    print("=" * 68)
    B.db.data["orders"] = {
        "yangi": mk_order("yangi", 555, 3000, age_days=2),
        "eski": mk_order("eski", 555, 3000, age_days=45),
        "yuborilgan": mk_order("yuborilgan", 555, 3000, age_days=45, gift_sent=True),
        "bekor": mk_order("bekor", 555, 3000, age_days=45,
                          gift_cancelled=True, gift_sent=True),
    }
    B.db.save()
    all_stuck = B.stuck_gift_orders()
    ids = {o["id"] for o in all_stuck}
    check(ids == {"yangi", "eski"},
          f"hammasi (yangi+eski, yuborilgan/bekor qilingan yo'q): {sorted(ids)}")
    old = B.stuck_gift_orders(older_than_days=30)
    check({o["id"] for o in old} == {"eski"},
          f"faqat 30+ kundik: {[o['id'] for o in old]}")
    check(B.stuck_gift_orders(older_than_days=3650) == [],
          "juda eski (3650+ kundik) hech qanday natija bermaydi")

    print()
    print("=" * 68)
    print("6) Narx aniqlash — price_uzs / price / yo'q")
    print("=" * 68)
    check(B.gift_order_price({"price_uzs": 3000, "price": 5000}) == 3000,
          "price_uzs ustun turadi")
    check(B.gift_order_price({"price": 5000}) == 5000, "price ishlatiladi")
    check(B.gift_order_price({}) == 0, "narx yo'q -> 0")
    check(B.gift_order_price({"price": None}) == 0, "null narx -> 0 (xato emas)")

    print()
    print("=" * 68)
    print("NATIJA:", "✅ BARCHASI TO'G'RI" if ok else "❌ MUAMMO BOR")
    print("=" * 68)
    return 0 if ok else 1


sys.exit(asyncio.run(main()))