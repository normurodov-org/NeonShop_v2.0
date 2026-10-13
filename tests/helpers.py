"""Testlar uchun yordamchi funksiyalar.

Nima uchun kerak: kod ichida o'z xatamizni izohlab yozamiz
("avval shunday edi — tuzatildi"). Test xom kodni tekshirsa,
o'z izohimizni "xato" deb o'ylab qizil bo'ladi.

IKKI XIL KOD TILI bor \u2014 va ularda IZOH QOIDASI boshqacha:

  * `strip_code()`      \u2014 JS/TS uchun (`//`, `/* */`, `/** */`)
  * `strip_py_comments()` \u2014 Python uchun (`#`, docstring)

🔴 Nima uchun Python uchun alohida funksiya:
   `tokenize` moduli izohlarni ANIQ olib tashlaydi. Regex bilan
   urinish ishlamaydi:
     - `#` satr ichida ham bo'ladi: `"#0f172a"`, `"#fff"`
     - o'zbekcha apostrof: `# msg.answer("Premium bo'limi")` \u2014
       `'` birinchi qatorchani ochib, izohni "oxirigacha yopiq"
       deb o'ylaydi va butun fayl izohlarga aylanib qoladi
   Bu real xato bo'ldi: `strip_code()` Python faylida ishlatilganda
   izohlarni olib tashlamaydi va test o'z izohimizni "xato kod"
   deb qizil bo'ladi.
"""

import io
import re
import tokenize

_TRIPLE_D = '"' * 3
_TRIPLE_S = "'" * 3


def strip_code(text: str) -> str:
    """JS/TS kodidan `//`, `/* */` va uch qatorli docstring olib tashlaydi.

    DIQQAT: satr ichidagi `//` saqlanadi \u2014 `https://...`, `a // b`.
    """
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    # `(?<![:'"])(?<!\w)` \u2014 URL, string va `a // b` dan himoya:
    #   `:`  -> `https://`
    #   `'`  -> `'... // ...'`
    #   `"`  -> `"... // ..."`
    #   `\w` -> `a//b` (JS butunlik operatori)
    text = re.sub(r"(?<![:'\"])(?<!\w)//[^\n]*", "", text)
    text = re.sub(_TRIPLE_D + ".." + _TRIPLE_D, '""', text, flags=re.S)
    text = re.sub(_TRIPLE_S + ".." + _TRIPLE_S, "''", text, flags=re.S)
    return text


def strip_py_comments(text: str) -> str:
    """Python kodidan `#` izoh va docstring'larni olib tashlaydi.

    `tokenize` orqali \u2014 shuning uchun `#` satr ICHIDAN
    (`"#0f172a"`, `"#fff"`) va apostrofli o'zbekcha so'zlardan
    (`bo'limi`) to'g'ri ajratiladi.
    """
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        # Syntax xatosi bo'lsa \u2014 regex bilan eng yaxshi holatni
        # berishga urinamiz (test ma'lumotni kamaytirmasligi uchun)
        return re.sub(r"(?<!['\"])#[^\n]*", "", text)

    out = []
    # 🔴 JAHAN SOLISH: tokenning O'Z matnidan chiqamiz, `token.end` dan
    #    emas. Sababi: `NEWLINE` tokeni matni `"\n"` (qator raqamini
    #    OSHIRMAYDI: end=(1,9) -> keyingi token (2,0)), lekin bir qatorni
    #    YO'Q qiladi. `end` dan hisoblasak, har bir qator IKKI marta
    #    yozilardi va butun fayl buzilib ketardi.
    cur_row, cur_col = 1, 0
    prev_tok = tokenize.INDENT
    for tok in toks:
        ttype, tstr, start, end, _line = tok
        if ttype == tokenize.COMMENT:
            continue
        if ttype == tokenize.STRING and prev_tok in (
                tokenize.INDENT, tokenize.NEWLINE, tokenize.NL,
                tokenize.DEDENT, tokenize.ENCODING):
            # docstring — uni `""` bilan almashtiramiz (qatorlar saqlanadi)
            tstr = '""'
        tr, tc = start
        if tr > cur_row:
            out.append("\n" * (tr - cur_row))
            cur_col = 0
        if tc > cur_col:
            out.append(" " * (tc - cur_col))
        out.append(tstr)
        nl = tstr.count("\n")
        if nl:
            cur_row = tr + nl
            cur_col = len(tstr) - tstr.rindex("\n") - 1
        else:
            cur_row = tr
            cur_col = tc + len(tstr)
        prev_tok = ttype
    return "".join(out)


def section(text: str, start_marker: str, end_marker: str, clean: bool = True) -> str:
    """Ikki marker orasidagi kodni qaytaradi (izohsiz)."""
    i = text.index(start_marker)
    j = text.index(end_marker, i + 1)
    seg = text[i:j]
    if not clean:
        return seg
    return strip_py_comments(seg) if _looks_python(seg) else strip_code(seg)


def _looks_python(text: str) -> bool:
    """Qisqa belgi: `import`/`def`/`#` belgilari mavjudmi."""
    return bool(re.search(r"^\s*(import |from |def |async def |class )", text, flags=re.M))