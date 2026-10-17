# -*- coding: utf-8 -*-
"""
\U0001F41B\U0001F534 PYTHON 3.11 MOSLIGI \u2014 Railway build'ni \U0001F6AB1 QILADI

Mijoz Railway logi (2026-10-17):
    SyntaxError: f-string expression part cannot include a backslash
    File \"<unknown>\", line 5918

🔴🔴🔴 NIMA UCHUN?
   Railway'da Python **3.11** ishlaydi (PEP 701 esa faqat 3.12+ da).
   3.11 da f-string ICHIDA backslash bo'lmaydi:

       f\"{esc(account or 'noma\\u2018lum')}\"   ❌ SYNTAX ERROR

   Lokal Python 3.14 buni qabul qiladi — shuning uchun xato
   `py_compile` va 52 ta testda KO'RINMADI, faqat Railway'da
   build ko'tarildi.

✅ SHU TEST: `tools/check_py311.py` ni chaqiradi va qaytarilishni
   tekshiradi — kelajakda shu xato chiqsa, test OLDINDAN qizil bo'ladi.
"""
import io
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILS = []


def check(cond, msg):
    print(("  \u2705 " if cond else "  \u274c ") + msg)
    if not cond:
        FAILS.append(msg)


def section(t):
    print("\n" + "=" * 74)
    print(t)
    print("=" * 74)


# \U0001F50E Tekshiruvchini yuklaymiz
spec = importlib.util.spec_from_file_location(
    "check_py311", os.path.join(ROOT, "tools", "check_py311.py"))
chk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chk)

BOT = io.open(os.path.join(ROOT, "bot.py"), encoding="utf-8").read()
BOT_LINES = BOT.split("\n")

# ═════════════════════════════════════════════════════════════════════════════
section("1) \U0001F41B\U0001F534 BACKSLASH f-string ICHIDA (Railway build FAIL sababi)")
issues = chk.find_issues(os.path.join(ROOT, "bot.py"))
check(not issues,
      "bot.py da f-string ifodasi ichida backslash YO'Q (%d ta)" % len(issues))
for ln, _c, why in issues[:10]:
    check(False, "  %d: %s" % (ln, why))

# ═════════════════════════════════════════════════════════════════════════════
section("2) \U0001F41B Ichki bir xil qo'shtirnoq (f\"{{d[\"k\"]}}\" \u2014 3.11 da XATO)")
bad = []
spans = chk._fstring_spans(BOT)
check(spans is not None, "tokenize ishladi (f-stringlar topildi)")
if spans:
    for (s_pos, e_pos) in spans:
        chunk = BOT[chk._offset(BOT, s_pos):chk._offset(BOT, e_pos)]
        body = chk._body_of(chunk)
        quote = chunk[1] if len(chunk) > 1 else '"'
        depth = 0
        for c in body:
            if c == "{":
                depth += 1
            elif c == "}":
                depth = max(0, depth - 1)
            elif depth > 0 and c == quote:
                bad.append(s_pos[0])
                break
    check(not bad, "ichki bir xil qo'shtirnoq yo'q (%d ta)" % len(bad))
    for ln in sorted(set(bad))[:8]:
        check(False, "  %d: %s" % (ln, BOT_LINES[ln - 1].strip()[:90]))

# ═════════════════════════════════════════════════════════════════════════════
section("3) \U0001F9EA XIYOSAT XIZMATI O'Z-O'ZINI SINOV QILADI")
check("def _body_of(" in io.open(os.path.join(ROOT, "tools", "check_py311.py"),
                               encoding="utf-8").read(),
      "tekshiruvchi `\\_body_of` ni o'z ichida saqlaydi")

BAD_SAMPLES = [
    'x = f"{esc(a or \'noma\\u2018lum\')}"',   # 3.11 da XATO
]
GOOD_SAMPLES = [
    'x = f"{esc(t)}"',
    'x = f"line1\\nline2 {esc(v)}\\n"',       # matn qismida backslash OK
    'x = f"{\'a\\u2018b\'}"',                 # ifodada backslash — XATO
]
scratch = []
for i, code in enumerate(BAD_SAMPLES):
    p = os.path.join(ROOT, "tools", "_py311_probe.py")
    io.open(p, "w", encoding="utf-8").write(code + "\n")
    found = bool(chk.find_issues(p))
    os.remove(p)
    check(found, "XATO bo\u02b8lgan namuna yakunlanadi: %s" % code[:46])

for code in GOOD_SAMPLES[:2]:
    p = os.path.join(ROOT, "tools", "_py311_probe.py")
    io.open(p, "w", encoding="utf-8").write(code + "\n")
    found = bool(chk.find_issues(p))
    os.remove(p)
    check(not found, "TO\u02b8G\u02b8RI namuna o\u02b8tadi: %s" % code[:46])

# ═════════════════════════════════════════════════════════════════════════════
section("4) \U0001F4A1 LOYIHADAGI QO\u02b8LDA ESLATMA")
check("f-string ichida apostrof yoki backslash ishlatmang" in BOT,
      "qoida o'z ichida bot.py da yozilgan")

print()
if FAILS:
    print("NATIJA: \u274c MUAMMO BOR (%d ta)" % len(FAILS))
    for f in FAILS:
        print("   - " + f)
    raise SystemExit(1)
print("NATIJA: \u2705 BARCHASI TO'G'RI")
