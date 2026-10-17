# -*- coding: utf-8 -*-
"""
\U0001F41B\u1F534 PYTHON 3.11 MOSLIGI TEKSHIRUVI (ANIQ, 2-VERSIYA)

Railway'da Python **3.11** ishlaydi. Unda f-string ICHIDA backslash
bo\u02b8lmaydi (PEP 701 faqat 3.12+ da):

    SyntaxError: f-string expression part cannot include a backslash

\u26A0\uFE0F FAQAT `{...}` ICHIDAGI backslash xato \u2014 matn qismidagi
   `\\n`, `\\t`, `\\u2018` NORMAL va to\u02b8g\u02b8ri.

\u274C 1-VERSIYA NIMA UCHUN XATO QILDI?
   `tokenize` (3.12+) ichki string'ni BITTA STRING token sifatida
   beradi \u2014 ya'ni ichidagi `\\u2018` ko\u02b8rinmaydi. Natijada xato
   \u00abko\u02b8rinmadi\u00bb. Haqiqiy sabab:

       f"<code>{esc(account or 'noma\\u2018lum')}</code>"
                          ^^^^^^^^^^^^^^^^^ ichki string ichida

   Python 3.11 \u00ab\`{}\` ifodasi ichida BACKSLASH BO\u02b8LMAYDI\u00bb
   deydi \u2014 ichki string ichida ham.

\u2705 2-VERSIYA: f-stringning XOM (raw) matnini olib, `{...}` ichida
   backslash bormi tekshiramiz \u2014 token turidan qat'i nazar.

Ishlatish:  python3 tools/check_py311.py [fayl.py ...]
"""
import io
import sys
import tokenize


def _fstring_spans(src):
    """(boshlanish, tugash) indekslari \u2014 har bir f-string uchun."""
    spans = []
    stack = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type == tokenize.FSTRING_START:
                stack.append(tok.start)
            elif tok.type == tokenize.FSTRING_END:
                if stack:
                    spans.append((stack.pop(), tok.end))
    except (tokenize.TokenError, SyntaxError):
        return None
    return spans


def _offset(src, pos):
    """(satr, ustun) -> belgi indeksiga."""
    lines = src.split("\n")
    off = 0
    for i in range(min(pos[0] - 1, len(lines))):
        off += len(lines[i]) + 1
    return off + pos[1]


def _body_of(chunk):
    """`f"..."` -> faqat ichki matn (prefiks va yopuvchi `"` olib tashlanadi).

    🐛 NIMAGA KERAK: f-stringning TASHQI qoʸsh tirnoqʸni oddiy
    string boshlovchi deb olsak, butun `{...}` bir "string" ichida
    qoladi va hech qachon topilmaydi (shu xato birinchi versiya qildi).
    """
    i = 1  # `f` belgisidan keyin
    if i < len(chunk) and chunk[i] in "\"'":
        quote = chunk[i]
        i += 1
        out = []
        while i < len(chunk):
            if chunk[i] == "\\" and i + 1 < len(chunk):
                out.append(chunk[i:i + 2])
                i += 2
                continue
            if chunk[i] == quote:
                if i + 1 >= len(chunk) or chunk[i + 1] != quote:
                    break
                out.append(chunk[i:i + 2])
                i += 2
                continue
            out.append(chunk[i])
            i += 1
        return "".join(out)
    return chunk[1:]


def _expr_has_backslash(body):
    """f-string TANASIDA `{...}` ichida backslash bormi?

    Chuqurlikni kuzatamiz: `{` da +1, `}` da -1. Chuqurlik > 0
    paytida `\\` topilsa — bu f-string IFODASI ichida — XATO.

    🐛 Ichki string ichidagi backslash ham xato (Python 3.11
    qoidasi), lekin `"` kabi KETMA-KET juftlar normal.
    """
    depth = 0
    i = 0
    n = len(body)
    while i < n:
        ch = body[i]
        if ch == "\\":
            if depth > 0:
                return True
            i += 2
            continue
        if ch in "\"'":
            q = ch
            j = i + 1
            while j < n:
                if body[j] == "\\":
                    if depth > 0:
                        return True
                    j += 2
                    continue
                if body[j] == q:
                    break
                j += 1
            i = j + 1
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth = max(0, depth - 1)
        i += 1
    return False


def find_issues(path):
    src = io.open(path, encoding="utf-8").read()
    spans = _fstring_spans(src)
    if spans is None:
        return [("\U0001F41B", 0, "faylni tokenize qilib bo\u02b8lmadi "
                                 "(boshqa sintaktik xato)")]

    out = []
    for (s_pos, e_pos) in spans:
        a, b = _offset(src, s_pos), _offset(src, e_pos)
        if b <= a:
            continue
        chunk = src[a:b]
        if _expr_has_backslash(_body_of(chunk)):
            ln = s_pos[0]
            # xato qatorini aniqroq ko\u02b8rsatish uchun qatorni tekshiramiz
            best = ln
            lines = src.split("\n")
            for off in range(ln - 1, min(ln + 6, len(lines))):
                if "{" in lines[off] and "}" in lines[off]:
                    best = off + 1
                    break
            out.append((best, 0, "f-string ifodasi ichida backslash"))
    return out


def main(paths):
    total = 0
    for p in paths:
        issues = find_issues(p)
        if not issues:
            print("  \u2705 %s" % p)
            continue
        uniq = sorted({ln for ln, _, _ in issues})
        print("  \u274c %s \u2014 %d ta xato" % (p, len(issues)))
        lines = io.open(p, encoding="utf-8").read().split("\n")
        for ln in uniq[:20]:
            print("       %d: %s" % (ln, lines[ln - 1].strip()[:104]))
        total += len(issues)
    print()
    if total:
        print("NATIJA: \u274c %d ta xato (Python 3.11 da build FAILED bo\u02b8ladi)" % total)
        return 1
    print("NATIJA: \u2705 Python 3.11 mosligi toza")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["bot.py"]))
