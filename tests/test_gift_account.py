"""BITTA userbot rejimi: gift yuborish + bank xabarlarini tekshirish.

Sovg'a yuborish va balansni avtomatik to'ldirish BITTA akkaunt orqali
amalga oshiriladi (SESSION_STRING). Alohida GIFT_SESSION_STRING yo'q.

Shu test quyidagilarni kafolatlaydi:
  - ortiqcha akkaunt qoldig'i (gift_userbot, gift_client, alohida ENV)
    kodda QOLMAGAN
  - sovg'a aynan `userbot` orqali yuboriladi
  - sovg'a xabari matni va anonimlik saqlanadi
  - ORDERS_CHANNEL formati server.ts bilan bir xil
  - SESSION_STRING validatsiyasi ishlaydi
"""
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
print("1) BITTA userbot — ortiqcha akkaunt qolmagan")
print("=" * 68)
for gone in ("gift_client", "_start_gift_userbot", "PENDING_LOGIN_ROLE",
             "GIFT_SESSION_STRING", "adm:gift_qr", "adm:gift_phone",
             "adm:gift_export", "neon_gift_userbot"):
    check(gone not in SRC, f"bot.py da {gone!r} yo'q")
# gift_userbot so'z qolgan bo'lsa — u FAQAT eski kalitlar ro'yxatida
# (tozalash uchun), real ishlatilmaydi
import re as _re
uses = [m for m in _re.finditer(r"gift_userbot", SRC)]
check(len(uses) == 1 and "STALE_RUNTIME_KEYS" in SRC,
      f"gift_userbot faqat STALE_RUNTIME_KEYS da ({len(uses)} marta)")
check("UserbotClient(\n                \"neon_gift_userbot\"" not in SRC,
      "gift uchun ikkinchi client yaratilmaydi")

check("gift_session_string" not in SRV, "server.ts da gift_session_string yo'q")
check(SRC.count(".send_gift(") == 1 and "gclient = userbot" in SRC,
      "sovg'a aynan BITTA userbot orqali yuboriladi (1 marta)")
check("GIFT_SESSION_STRING" not in SRV, "server.ts da GIFT_SESSION_STRING yo'q")

print()
print("=" * 68)
print("2) Admin menyusi — eskirgan tugmalar yo'q")
print("=" * 68)
for gone in ("adm:gift_qr", "adm:gift_phone", "adm:gift_export"):
    check(gone not in SRC, f"{gone} tugmasi olib tashlandi")
check("adm:ub_qr" in SRC and "adm:ub_phone" in SRC, "userbot ulash tugmalari saqlandi")
check("adm:gift_retry" in SRC, "🎁 Gift qayta yuborish (muammo tiklash) saqlandi")

print()
print("=" * 68)
print("3) SESSION_STRING validatsiyasi")
print("=" * 68)
check(B.SESSION_STRING_EXPECTED == 362, "kutilgan uzunlik: 362 belgi")
for n, valid, label in (
    (362, True, "to'g'ri"),
    (351, True, "eski format"),
    (0, False, "bo'sh"),
    (21, False, "telethon qisqasi"),
    (100, False, "qirqilgan"),
    (300, False, "to'liq emas"),
):
    got, why = B.diagnose_session_string("A" * n)
    print(f"    {n:4} belgi ({label:16}) -> {'✅' if got == valid else '❌'}")
    check(got == valid, f"{n} belgi -> {'to' + chr(39) + 'g' + chr(39) + 'ri' if got else 'noto' + chr(39) + 'g' + chr(39) + 'ri'}")

_, why = B.diagnose_session_string("A" * 21)
check("SESSION_STRING" in why and "GIFT_SESSION_STRING" not in why,
      "xabar faqat SESSION_STRING ga ishora qiladi")
check("362 belgi" in why, "kutilgan uzunlik ko'rsatilgan")
check("unpack requires" not in why, "pyrofork ichki xatosi takrorlanmadi")

check(B.normalize_session_string("  abc\r\ndef  ") == "abcdef",
      "bo'sh joy / qator uzilishi tozalanadi")

print()
print("=" * 68)
print("4) ORDERS_CHANNEL formati (mijoz rasmidagi)")
print("=" * 68)
txt = B.format_order_channel_text(
    title="Stars olindi", who="@odilbek",
    amount_text="Miqdor: 50 ⭐", price=10_000, cashback=10,
)
plain = txt.replace("<b>", "").replace("</b>", "").replace("&#x27;", "'")
print(plain)
lines = plain.splitlines()
check(lines[0].strip() == "⭐ Stars olindi", "1-qator: ⭐ Stars olindi")
check(lines[1].strip() == "👤 @odilbek", "2-qator: 👤 mijoz")
check("📦 Miqdor: 50 ⭐" in plain, "📦 Miqdor: 50 ⭐")
check("Summasi: 10 000 so'm" in plain, "  Summasi: 10 000 so'm")
check("Keshbek: +10 so'm" in plain, "  Keshbek: +10 so'm")

txt2 = B.format_order_channel_text(
    title="Gift: 🧸 Ayiqcha (🕶️ Anonim)", who="@aliy",
    amount_text="Sovg'a: 🧸 Ayiqcha — 15 ⭐", price=3_000,
)
plain2 = txt2.replace("<b>", "").replace("</b>", "").replace("&#x27;", "'")
check("Keshbek" not in plain2, "Keshbek yo'q bo'lsa qator qo'shilmaydi")
check("Sovg'a: 🧸 Ayiqcha" in plain2, "esc() apostrofni buzmaydi")

print()
print("=" * 68)
print("5) server.ts bilan format BIR XILMI?")
print("=" * 68)
fn = re.search(r"function channelOrderText\(.*?\n}\n", SRV, re.S)
check(fn is not None, "server.ts da channelOrderText() bor")
if fn:
    js = fn.group(0)
    for frag in ("Summasi", "Keshbek", "amountText"):
        check(frag in js, f"server.ts: {frag!r} mavjud")
check("api.telegram.org/bot${token}/sendMessage" in SRV,
      "to'g'ridan-to'g'ri Bot API chaqiriladi (AUTO_START_TG_BOT=false)")

print()
print("=" * 68)
print("6) Gift tanlash va anonim semantikasi saqlangan")
print("=" * 68)
check(B.order_is_anonymous({"anon": True}) is True, "anon=True -> anonim")
check(B.order_is_anonymous({"anon": False}) is False, "anon=False -> profil ko'rinadi")
check(B.order_is_anonymous({"hide_my_name": True}) is True,
      "eski yozuv (hide_my_name) ham to'g'ri o'qiladi")
check(len(B.GIFT_EMOJI) == len(B.GIFTS), "GIFT_EMOJI to'liq")

print()
print("NATIJA:", "✅ BARCHASI TO'G'RI" if ok else "❌ MUAMMO BOR")
sys.exit(0 if ok else 1)