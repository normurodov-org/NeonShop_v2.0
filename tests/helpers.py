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

import ast
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
    """Python kodidan `#` izoh va haqiqiy DOCSTRING'larni olib tashlaydi.

    `tokenize` orqali izohlarni ANIQ ajratamiz (`#` satr ichida ham
    bo'ladi: `"#0f172a"`, `"#fff"`).

    🔴 Nima uchun docstring uchun `tokenize` EMAS, `ast` ishlatiladi:
       `tokenize` da "birinchi STRING tokeni = docstring" degan qoida
       YOLG'ON. Masalan ko'p qatorli tuple:

           _STAR_MONEY_KEYS = (
               "usdt yetarli emas",      <-- birinchi STRING
               "yetarli usdt",
           )

       Bu DOCSTRING EMAS — oddiy tuple. Eski yondashuv uni `""` bilan
       almashtirib, testga yolg'on natija berardi (test "kalit yo'q"
       deb qizil bo'lardi, kod esa to'g'ri edi).

       `ast` esa aniq: docstring faqat Module/FunctionDef/AsyncFunctionDef/
       ClassDef ning `body[0]` da bo'lgan STRING.
    """
    # --- 1) haqiqiy docstring qatorlarini topamiz ---
    doc_lines = set()
    try:
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Module, ast.FunctionDef,
                                     ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            body = getattr(node, "body", None)
            if not body:
                continue
            first = body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                    and isinstance(first.value.value, str):
                ln = first.value.lineno
                doc_lines.add((ln, first.value.end_lineno or ln))
    except SyntaxError:
        # Sintaksis xatosi bo'lsa — izohlarni regex bilan olib tashlaymiz,
        # matnni KAMAYTIRMAYMIZMIZ (test ma'lumotni yo'qotmasin)
        return re.sub(r"(?<!['\"])#[^\n]*", "", text)

    # --- 2) tokenlarni qayta yig'amiz ---
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, IndentationError):
        return re.sub(r"(?<!['\"])#[^\n]*", "", text)

    out = []
    # 🔴 JAHAN SOLISH: tokenning O'Z matnidan chiqamiz, `token.end` dan
    #    emas. Sababi: `NEWLINE` tokeni matni `"\n"` (qator raqamini
    #    OSHIRMAYDI: end=(1,9) -> keyingi token (2,0)), lekin bir qatorni
    #    YO'Q qiladi. `end` dan hisoblasak, har bir qator IKKI marta
    #    yozilardi va butun fayl buzilib ketardi.
    cur_row, cur_col = 1, 0
    for tok in toks:
        ttype, tstr, start, end, _line = tok
        if ttype == tokenize.COMMENT:
            continue
        tr, tc = start
        if ttype == tokenize.STRING and any(
                a <= tr <= b for a, b in doc_lines):
            tstr = '""'
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