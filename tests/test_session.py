"""SESSION_STRING validatsiyasi.

Muammo: noto'g'ri session Railway da bo'lganda Pyrofork ichida
"unpack requires a buffer of 271 bytes" degan MA'NOSIZ xato chiqardi —
qaysi qiymat noto'g'ri ekanini aytmaydi, admin esa qayta-qayta urinib
hayotdan bezor bo'lardi.

To'g'ri pyrofork session = 362 belgi (271 bayt).
"""
import sys

sys.path.insert(0, '.')
import bot as B  # noqa: E402

ok = True


def check(cond, msg):
    global ok
    ok &= bool(cond)
    print(f"  {'✅' if cond else '❌'} {msg}")


print("=" * 66)
print("1) TO'G'RI uzunliklar")
print("=" * 66)
check(B.SESSION_STRING_EXPECTED == 362, "Yangi format: 362 belgi")
check(set(B.SESSION_STRING_LEGACY) == {351, 356},
      f"Eski formatlar: {B.SESSION_STRING_LEGACY}")

for n, valid, label in (
    (362, True, "yangi format"),
    (351, True, "eski format (263 bayt)"),
    (356, True, "eski format (267 bayt)"),
    (0, False, "bo'sh"),
    (21, False, "telethon session qisqasi"),
    (100, False, "qirqilgan"),
    (300, False, "to'liq emas"),
    (400, False, "ortiqcha"),
):
    got, why = B.diagnose_session_string("A" * n)
    mark = "✅" if got == valid else "❌"
    print(f"  {mark} {n:4} belgi ({label:24}) -> {'to' + chr(39) + 'g' + chr(39) + 'ri' if got else 'noto' + chr(39) + 'g' + chr(39) + 'ri'}")
    ok &= (got == valid)

print()
print("=" * 66)
print("2) NOTO'G'RI xabar — TUZATILADIGAN bo'lishi kerak")
print("=" * 66)
_, why = B.diagnose_session_string("A" * 21)
check("362 belgi" in why, "kutilgan uzunlik ko'rsatilgan")
check("SESSION_STRING" in why, "ENV kaliti nomi ko'rsatilgan")
check("Session zaxirasi" in why, "qayerdan olish kerakligi ko'rsatilgan")
check("GIFT_SESSION_STRING" not in why, "eskirgan GIFT_SESSION_STRING yo'qqon qilinmadi")
check("Invalid base64-encoded string" not in why,
      "Python ichki base64 xatosi yashirilgan (ma'nosizroq)")
check("unpack requires" not in why, "pyrofork ichki xatosi takrorlanmadi")

_, why = B.diagnose_session_string("A" * 300)
check("225 bayt" in why, "nechta bayt ekani ko'rsatilgan")
check("kutilgan" in why.lower() or "kerak" in why.lower(), "tuzatiladigan matn bor")

_, why = B.diagnose_session_string("")
check(why == "bo'sh", "bo'sh qiymat -> oddiy xabar")

print()
print("=" * 66)
print("3) normalize_session_string — bo'sh joy / qator uzilishi")
print("=" * 66)
cases = [
    ("  abc  ", "abc", "oldidan-o'zidan bo'sh joy"),
    ("abc\n", "abc", "oxirida qator uzilishi"),
    ("\r\nabc\r\n", "abc", "Windows qatori"),
    ('"abc"', "abc", "qoshtirnoq"),
    ("'abc'", "abc", "bir qoshtirnoq"),
    ("abc\r\ndef", "abcdef", "ichidagi qator uzilishi"),
    ("abc def", "abcdef", "ichidagi bo'sh joy"),
    ("", "", "bo'sh"),
    (None, "", "None"),
    (12345, "", "son emas"),
]
for raw, expect, label in cases:
    got = B.normalize_session_string(raw)
    mark = "✅" if got == expect else "❌"
    print(f"  {mark} {label:32} {raw!r:20} -> {got!r}")
    ok &= (got == expect)

print()
print("=" * 66)
print("4) Diagnostikani TEKSHIRMAY qoldirilmaydi (tuzatish mumkin)")
print("=" * 66)
_, why = B.diagnose_session_string("A" * 100)
steps = why.count("1)") + why.count("2)") + why.count("3)")
check(steps >= 3, f"3 ta aniq qadam bor (topildi: {steps})")

print()
print("=" * 66)
print("5) Railway ENV o'qilishi tozalangan holda")
print("=" * 66)
import os  # noqa: E402

os.environ["SESSION_STRING"] = "  " + "A" * 362 + "\n"
check(B.normalize_env_session("SESSION_STRING") == "A" * 362,
      "ENV dagi bo'sh joy/qator uzilishi tozalanadi")
del os.environ["SESSION_STRING"]
check(B.normalize_env_session("SESSION_STRING") == "",
      "yo'q ENV -> bo'sh string (xato bermaydi)")

print()
print("NATIJA:", "✅ BARCHASI TO'G'RI" if ok else "❌ MUAMMO BOR")
sys.exit(0 if ok else 1)