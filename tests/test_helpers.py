"""tests/helpers.py uchun o'z-o'zini tekshiruvchi test."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import strip_code, strip_py_comments  # noqa: E402

ok = True


def check(cond, msg):
    global ok
    ok &= bool(cond)
    print(f"  {'✅' if cond else '❌'} {msg}")


print("=" * 70)
print("A) strip_py_comments() — Python")
print("=" * 70)

check("izoh" not in strip_py_comments("abc = 1  # izoh"),
      "oddiy `#` izoh olib tashlandi")
check("abc = 1" in strip_py_comments("abc = 1  # izoh"),
      "izohdagi kod saqlanadi")

# 🔴 ASOSIY XATO: `#` satr ICHIDA bo'ladi
hexcode = 'color = "#0f172a"  # izoh'
r = strip_py_comments(hexcode)
check("#0f172a" in r, "🔴 satr ichidagi `#0f172a` saqlandi")

# 🔴 o'zbekcha apostrof + `//` — regex bu yerda butunlay buzilardi
uz = "# ILGARI: msg.answer(\"Premium bo'limi\") - bu STUB edi.\ndef real():\n    pass"
r = strip_py_comments(uz)
check("STUB edi" not in r, "🔴 apostrofli `#` izoh to'liq olib tashlandi")
check("def real():" in r, "🔴 izohdagi apostrof keyingi kodni YEMADI")
check("    pass" in r, "keyingi qator saqlandi")

# docstring
r = strip_py_comments('def f():\n    """doc"""\n    return 1')
check("doc" not in r, "docstring olib tashlandi")
check("return 1" in r, "funksiya saqlanadi")
# Qator soni: DEDENT/ENDMARKER oxirida bitta qator qo'shadi, shuning
# uchun aniq son emas, STRUKTURA tekshiriladi (ch indentation saqlanadi).
check("\n    return 1" in r,
      "🔴 qatorlar buzilmadi (ch indentation saqlandi)")

r = strip_py_comments("def f():\n    '''doc bo'limi'''\n    return 1")
check("doc" not in r, "apostrofli docstring olib tashlandi")

# f-string va dict kalitlari
r = strip_py_comments('d = {"a": 1}  # izoh\ny = f"x {d[\'a\']} # bezdana"')
check('f"x {d[' in r, "f-string ichidagi `#` saqlandi")

# butun fayl
r = strip_py_comments("import os\n\n\ndef g():\n    return os  # comment\n")
check("import os" in r and "def g():" in r and "return os" in r, "butun fayl o'qildi")

print()
print("=" * 70)
print("B) strip_code() — JS/TS")
print("=" * 70)
url = 'x = "https://nft.fragment.com/gift/finepen.webp"'
check(strip_code(url).strip() == url.strip(),
      "🔴 URL ichidagi `//` IZOH deb hisoblanmadi")
check("izoh" not in strip_code("abc; // izoh"), "`//` izoh olib tashlandi")
# DIQQAT: JS tilida `a // b` — bu IZOH (JS da `//` har doim izoh
# boshlaydi, butunlik operatori `Math.floor(a/b)` bilan yoziladi).
# Python'da esa `//` butunlik. Shuning uchun bu test Python uchun
# `strip_py_comments` da, JS uchun `strip_code` da emas.
check(strip_code("x = a // b").strip() == "x = a",
      "JS da `a // b` — izoh (JS qoidasi)")

# Python da `//` butunlik operatori — uni tegilmasligi kerak
check("//" in strip_py_comments("x = a // b"),
      "🔴 Python da `a // b` butunlik operatori (izoh EMAS)")
check("y" not in strip_code("a = 1 /* y o'q */ b = 2"), "block izoh olib tashlandi")
check("doc" not in strip_code('const a = 1; /** doc */'), "JSDoc olib tashlandi")
check("const a = 1;" in strip_code('const a = 1; /** doc */'), "kod saqlandi")

print()
print("=" * 70)
print("NATIJA: ✅ BARCHASI TO'G'RI" if ok else "NATIJA: ❌ MUAMMO BOR")
print("=" * 70)
sys.exit(0 if ok else 1)