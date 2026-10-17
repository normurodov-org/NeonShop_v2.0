# -*- coding: utf-8 -*-
"""💰 SUMMA FORMATLASH — O'ZBEK FORMATIDA (1 102, noldagi 1,102)

🔴 NIMA UCHUN: brauzer tilidan qarab formatlash «saytda avto to'ldirish
   ishlamaydi» ning ASAOSIY sababi edi. Ingliz brauzerida
   `(1102).toLocaleString()` → «1,102» chiqadi, lekin O'zbekistonda
   vergul KASR belgisi (1,102 = 1 so'm 102 tiyin!).

   Telegram WebApp'da `bot.py` `fmt()` dan foynalanardi → «1 102»
   (to'g'ri) — shuning uchun WebApp'da ishlagan.
"""
import subprocess
import sys
import os

sys.path.insert(0, '.')
FAILS = []


def check(name, cond, extra=""):
    print(("  \u2705 " if cond else "  \u274c ") + name + (("  | " + str(extra)) if extra else ""))
    if not cond:
        FAILS.append(name)


# tsx orqali TS faylni to'g'ridan-to'g'ri ishga tushiramiz
CMD = ["npx", "tsx", "-e"]
PROBE = """
const { fmtUzs, fmtBank } = require('./src/lib/format');
const out = [];
out.push(fmtUzs(0));
out.push(fmtUzs(1));
out.push(fmtUzs(999));
out.push(fmtUzs(1000));
out.push(fmtUzs(1102));
out.push(fmtUzs(1024));
out.push(fmtUzs(1000000));
out.push(fmtUzs(12345678));
out.push(fmtBank(1024));
out.push(fmtUzs('1102'));
out.push(fmtUzs(undefined));
out.push(fmtUzs(null));
out.push(fmtUzs(NaN));
console.log(JSON.stringify(out));
"""


def main():
    print("\n\U0001F4B0 fmtUzs — O'zbek formati")
    p = subprocess.run(CMD, input=PROBE, capture_output=True, text=True,
                       timeout=90)
    if p.returncode != 0:
        print("  \U0001F534 tsx ishlamadi:", (p.stderr or "")[-300:])
        return 1
    import json
    v = json.loads(p.stdout.strip().split("\n")[-1])
    names = ["0", "1", "999", "1000", "1102", "1024", "1000000",
             "12345678", "fmtBank(1024)", "'1102'", "undefined", "null", "NaN"]
    for n, got in zip(names, v):
        print("     %-14s -> %r" % (n, got))

    check("0 -> '0'", v[0] == '0', v[0])
    check("1 -> '1'", v[1] == '1', v[1])
    check("999 -> '999'", v[2] == '999', v[2])
    check("1000 -> '1 000'", v[3] == '1 000', v[3])
    check("1102 -> '1 102'", v[4] == '1 102', v[4])
    check("1024 -> '1 024'", v[5] == '1 024', v[5])
    check("1000000 -> '1 000 000'", v[6] == '1 000 000', v[6])
    check("12345678 -> '12 345 678'", v[7] == '12 345 678', v[7])
    check("fmtBank -> '1 024,00'", v[8] == '1 024,00', v[8])
    check("matn '1102' -> '1 102'", v[9] == '1 102', v[9])
    check("undefined -> '0'", v[10] == '0', v[10])
    check("null -> '0'", v[11] == '0', v[11])
    check("NaN -> '0'", v[12] == '0', v[12])

    # 🔴 ASOSIY KONTROVER: vergul BO'Lmasligi shart
    #    (`fmtBank` dan tashqari — u bank formati uchun AYNAN vergul bilan
    #    yozadi: «1 024,00». Bu TO'G'RI — bank xabari shunday keladi.)
    for n, got in zip(names[:8], v[:8]):
        check("«%s» da VERGUL YO'Q" % n, "," not in got, got)

    # 🔴 KODDA toLocaleString() QOLMAGAN KERAK
    print("\n\U0001F6E1\uFE0F kodda toLocaleString() qolmagan")
    import io
    bad = []
    for root, dirs, files in os.walk('src'):
        for fn in files:
            if not fn.endswith(('.ts', '.tsx')):
                continue
            fp = os.path.join(root, fn)
            if fp.endswith('lib/format.ts'):
                continue
            txt = io.open(fp, encoding='utf-8').read()
            for i, line in enumerate(txt.split('\n'), 1):
                if '.toLocaleString()' in line:
                    bad.append("%s:%d" % (fp, i))
    check("`.toLocaleString()` qolmagan", not bad, bad[:5] or 'toza')

    print()
    print("=" * 74)
    if FAILS:
        print("\U0001F534 MUAMMO: %d ta" % len(FAILS))
        return 1
    print("\u2705\u2705\u2705 FORMAT TO'G'RI — 1,102 O'RNIGA 1 102")
    return 0


sys.exit(main())