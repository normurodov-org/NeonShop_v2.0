"""Gift xatolari: DOIMIY (mijoz) va ICHKI (dasturiy) — farqi.

Muammo: "object of type 'NoneType' has no len()" kabi ichki xato oldin
5 urinishdan keyin buyurtmani YOPARDI — mijoz pulini to'lab giftini
olmay qolardi. Endi ichki xatolar urinishni hisoblamaydi.
"""
import asyncio
import sys

sys.path.insert(0, '.')
import bot as B  # noqa: E402

B.GIFT_POLL_INTERVAL = 0.05
B.GIFT_RETRY_DELAY = 0.0


class FakeSticker:
    def __init__(self, e):
        self.emoji = e


class G:
    def __init__(self, i, e, p):
        self.id, self.sticker, self.price = i, FakeSticker(e), p


TELEGRAM = [G(101, "💝", 15), G(102, "🧸", 15), G(103, "🌹", 25)]

MODE = {"v": "ok"}


class UB:
    async def get_available_gifts(self):
        if MODE["v"] == "list_error":
            raise TypeError("object of type 'NoneType' has no len()")
        return TELEGRAM

    async def send_gift(self, chat_id, gift_id, text=None, hide_my_name=None):
        if MODE["v"] == "send_error":
            raise TypeError("object of type 'NoneType' has no len()")
        if MODE["v"] == "permanent":
            # Telegram'ning haqiqiy "doimiy" xatosi
            from pyrogram.errors import RPCError

            class Err(RPCError):
                def __init__(self):
                    super().__init__("GIFT_NOT_AVAILABLE")

            raise Err()
        return True


ok = True


def check(cond, msg):
    global ok
    ok &= bool(cond)
    print(f"  {'✅' if cond else '❌'} {msg}")


async def cycle(mid, wait_keys=("gift_sent", "gift_needs_review", "gift_failed"),
                max_wait=3.0, fresh=True):
    """Bitta worker sikli: buyurtma yakunlanguncha kutadi."""
    if fresh or f"o{mid}" not in B.db.data.get("orders", {}):
        B.db.data["orders"] = {f"o{mid}": {
            "id": f"o{mid}", "user_id": 555, "kind": "gift", "gift": "bear",
            "stars": 15, "title": "\U0001F9F8 Ayiqcha", "recipient": "bobur",
            "status": "completed", "anon": True,
        }}
        B.db.save()
    task = asyncio.create_task(B.process_gift_orders())
    key = f"o{mid}"
    waited = 0.0
    while waited < max_wait:
        await asyncio.sleep(0.02)
        waited += 0.02
        o = B.db.data.get("orders", {}).get(key) or {}
        if any(o.get(k) for k in wait_keys):
            break
        # "doimiy xato" holda urinishlar soni oshishi bilan sekinlashadi
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    return B.db.data.get("orders", {}).get(key, {})


async def main():
    B.userbot = UB()
    B.gift_userbot = None
    B.db.get_or_create_user(555, "aliy", "Aliy")

    print("=" * 66)
    print("1) XATO TURLARINI AJRATISH")
    print("=" * 66)
    check(B.is_internal_gift_error(TypeError("len(None)")), "TypeError -> ichki")
    check(B.is_internal_gift_error(AttributeError("'NoneType'")), "AttributeError -> ichki")
    check(B.is_internal_gift_error(TimeoutError()), "TimeoutError -> ichki")
    check(B.is_internal_gift_error(ConnectionError()), "ConnectionError -> ichki")
    check(B.is_internal_gift_error(ValueError("parsing xatosi")),
          "ValueError (parsing) -> ichki")
    try:
        from pyrogram.errors import RPCError
        class E(RPCError):
            def __init__(self):
                super().__init__("USERNAME_INVALID")
        check(not B.is_internal_gift_error(E()), "RPCError -> doimiy")
    except ImportError:
        print("  ➖ RPCError tekshirilmadi (pyrogram yo'q)")

    print()
    print("=" * 66)
    print("2) ICHKI xato — buyurtma YOPILMASLIGI kerak")
    print("=" * 66)
    MODE["v"] = "send_error"
    o = await cycle(1)
    check(not o.get("gift_sent"), "yuborilmagan (to'g'ri)")
    check(o.get("gift_attempts", 0) == 0,
          f"gift_attempts={o.get('gift_attempts', 0)} — DOIMIY xato hisobiga kirmadi")
    check(o.get("gift_needs_review") is True, "gift_needs_review=True")
    check(not o.get("gift_failed"), "gift_failed=False — mijozga 'muvaffaqiyatsiz' yozilmadi")

    print()
    print("  ... 10 sikl davomida (real hayotdagidek) tekshiramiz ...")
    for i in range(2, 12):
        o = await cycle(i)
    check(not o.get("gift_failed"),
          f"10 sikldan keyin ham gift_failed={o.get('gift_failed')} — yopilmagan")

    print()
    print("  ... keyin xato tuzildi (Telegram tiklandi) ...")
    MODE["v"] = "ok"
    o = await cycle(20)
    check(o.get("gift_sent") is True, "xato tuzilgachayin avtomatik yuborildi ✅")

    print()
    print("=" * 66)
    print("3) DOIMIY xato — urinishlar tugaydi (mijozga bog'liq)")
    print("=" * 66)
    MODE["v"] = "permanent"
    # Bitta buyurtma, takroriy sikllar — urinishlar shu buyurtmada
    # to'planadi (har siklda yangi order yaratib qo'yib bo'lmaydi)
    o = await cycle(30)
    print(f"       [birinchi sikl: attempts={o.get('gift_attempts')} "
          f"failed={o.get('gift_failed')}]")
    # Endi xuddi shu buyurtmani qayta-qayta ishlaymiz
    for _ in range(B.GIFT_MAX_ATTEMPTS + 2):
        o = await cycle(30, fresh=False,
                        wait_keys=("gift_sent", "gift_needs_review", "gift_failed"),
                        max_wait=1.0)
        if o.get("gift_failed"):
            break
    print(f"       [yakuniy: attempts={o.get('gift_attempts')} "
          f"failed={o.get('gift_failed')}]")
    print(f"       [doimiy xato natijasi: attempts={o.get('gift_attempts')} "
          f"failed={o.get('gift_failed')} error={str(o.get('gift_error'))[:40]!r}]")
    check(o.get("gift_attempts", 0) >= B.GIFT_MAX_ATTEMPTS,
          f"gift_attempts={o.get('gift_attempts')} (limit {B.GIFT_MAX_ATTEMPTS})")
    check(o.get("gift_failed") is True, "gift_failed=True — admin xabardor qilindi")
    check(o.get("gift_needs_review") is not True,
          "gift_needs_review=False — bu DOIMIY xato")

    print()
    print("=" * 66)
    print("4) get_available_gifts ichki xatolari ham xuddi shunday")
    print("=" * 66)
    MODE["v"] = "list_error"
    o = await cycle(50)
    print(f"       [ro'yxat xato natijasi: error={o.get('gift_error')!r}]")
    check(not o.get("gift_failed"), "ro'yxat xatosi buyurtmani yopmadi")
    check(o.get("gift_needs_review") is True, "needs_review belgilandi")

    print()
    print("=" * 66)
    print("5) Traceback saqlanadi (keyingi xatoni TIKLASH uchun)")
    print("=" * 66)
    tr = o.get("gift_error_trace") or ""
    check("NoneType" in (o.get("gift_error") or ""),
          "xato matni saqlanadi: " + repr(str(o.get("gift_error"))[:45]))
    check(str(o.get("gift_error_stage", "")).startswith("1)"),
          "bosqich aniq: " + repr(o.get("gift_error_stage")))
    check(len(tr) > 10, f"traceback saqlandi ({len(tr)} belgi)")
    check("File " in tr, "traceback ichida qator raqamlari bor")

    print()
    print("NATIJA:", "✅ BARCHASI TO'G'RI" if ok else "❌ MUAMMO BOR")
    return 0 if ok else 1


sys.exit(asyncio.run(main()))