# -*- coding: utf-8 -*-
"""CSS darajasidagi regressiya testi — chap menyu kontent ustiga chiqmasin.

Muammo FAQAT build'dagi CSS tartibida ko'rinadi:
  .md\\:pl-[124px] { padding-left: 124px }   <- 2
  .xl\\:px-10      { padding-inline: 40px }  <- 3  KEYIN chiqadi
`padding-inline` chap tomonni ham qayta yozadi, shuning uchun
>=1280px da chap bo'shliq 124px emas, 40px bo'lib qoladi.

Bu test `dist/` build qilingan bo'lsa uni tekshiradi. Build yo'q bo'lsa
o'tkazib yuboradi (CI da `npm run build` oldindan bajariladi).
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist", "assets")

FAILS = []


def check(cond, msg):
    print(("  ✅ " if cond else "  ❌ ") + msg)
    if not cond:
        FAILS.append(msg)


def section(t):
    print("\n" + "=" * 77)
    print(t)
    print("=" * 77)


def specificity(selector):
    """(klass+id+pseudo, element) — CSS specificity."""
    sel = re.sub(r"\[[^\]]*\]", " ", selector)          # attributelarni tashlaymiz
    sel = re.sub(r"::[a-z-]+", " ", sel)                  # pseudo-element
    sel = re.sub(r":(?!:)[a-z-]+(\([^)]*\))?", " ", sel)  # pseudo-class
    ids = len(re.findall(r"#[A-Za-z0-9_-]+", sel))
    cls = len(re.findall(r"\.[A-Za-z0-9_-]+", sel))
    els = len(re.findall(r"(?:^|[\s>+~])([a-zA-Z][A-Za-z0-9]*)", " " + sel))
    return (ids, cls, els)


css_files = sorted(
    (os.path.join(DIST, f) for f in os.listdir(DIST) if f.endswith(".css")),
    key=os.path.getmtime,
) if os.path.isdir(DIST) else []

if not css_files:
    print("dist/assets topilmadi — build qilinmagan. O'tkazib yuboriladi.")
    sys.exit(0)

CSS = io.open(css_files[-1], encoding="utf-8").read()
print("CSS: " + os.path.relpath(css_files[-1], ROOT))

section("1) 🔴 rail-clear qoidasi build'da mavjudmi?")

def parse_rules(css):
    """CSS ni (position, selector, declarations) ro'yxatga aylantiradi.

    📌 `rfind` ishonchsiz: `@media(...){html body .x{...}}` da selektor
       `}` dan emas, `{` dan keyin keladi va chuqurlik (nesting) bor.
       Shu sabab selektor boshlanishini `buf_start` da saqlaymiz —
       u har doim oldingi `}` dan keyingi joyga tenglanadi.

    📌🔴 `@layer components;` — `;` bilan TUGAGAN at-rule tanasiz.
       Uni `{` deb o'ylab, keyingi haqiqiy `}` gacha yutib yuborardi.

    📌🔴🔴 `@layer utilities { .a{} .b{} }` — at-rule ICHIDA qoidalar.
       Uni butun bitta qoida deb olsak, ichidagi yuzlab utility'lar
       ko'rinmay qolardi. Shuning uchun at-rule tanasiga REKURSIYA
       bilan kirib qolamiz.
    """
    rules = []
    i, n = 0, len(css)
    buf_start = 0
    while i < n:
        if css[i] != "{":
            i += 1
            continue
        sel = css[buf_start:i].strip()
        if ";" in sel:
            sel = sel.rsplit(";", 1)[-1].strip()
        # muvozanatli `}` ni topamiz
        depth, j = 1, i + 1
        while j < n and depth:
            if css[j] == "{":
                depth += 1
            elif css[j] == "}":
                depth -= 1
            j += 1
        body = css[i + 1:j - 1]
        if sel.startswith("@"):
            rules.extend(parse_rules(body))      # 🔴 ichiga kiramiz
        elif sel:
            rules.append((i, sel, body))
        buf_start = j
        i = j
    return rules


RULES = parse_rules(CSS)


def rules_for(cls):
    """`.md\\:px-6` kabi klassga tegishli qoidalar."""
    out = []
    for pos, sel, body in RULES:
        # selektor ro'yxatida shu klass bormi (vergul bilan ajratilgan)
        for part in sel.split(","):
            part = part.strip()
            if part == cls or part.endswith(" " + cls):
                out.append((pos, part, body))
                break
    return out


CSS = CSS
rules = rules_for("html body .rail-clear")
check(len(rules) >= 1, "🔴 `html body .rail-clear` qoidasi build'da bor")
rail_spec = rules[-1][0] if False else None
if rules:
    pos, sel, decl = rules[-1]
    check("padding-left:var(--rail-clear)" in decl.replace(" ", ""),
          "🔴 `padding-left: var(--rail-clear)`")
    print("     selektor = %r" % sel)
    print("     specificity = (id,klass,element) = %s" % (specificity(sel),))

section("2) 🔴🔴 specificity rail-clear ga USTUNMI? (asosiy tekshiruv)")

rail_spec = specificity(rules[-1][1]) if rules else (0, 0, 0)
check(rail_spec >= (0, 1, 2),
      "🔴 rail-clear specificity %s >= (0,1,2)" % (rail_spec,))

# main/header da ishlatiladigan barcha padding utility'lari
CONFLICTS = ["md:px-6", "xl:px-10", "px-4", "md:px-4"]
found_any = False
for name in CONFLICTS:
    cls = "." + name.replace(":", "\\:")
    for pos, sel, body in rules_for(cls):
        found_any = True
        sets_pad = "padding-inline" in body or "padding-left" in body
        if not sets_pad:
            continue
        spec = specificity(sel)
        check(rail_spec > spec,
              "🔴🔴 `.%s` (spec %s) < rail-clear (spec %s)"
              % (name, spec, rail_spec))

check(found_any, "📐 padding utility'lari build'da topildi (tartib tekshirildi)")

section("3) 🔴 chap bo'shliq tokenlari to'liqmi?")

check("--rail-w:" in CSS, "📐 `--rail-w`")
check("--rail-inset:" in CSS, "📐 `--rail-inset`")
check("--rail-gap:" in CSS, "📐 `--rail-gap`")
check("--rail-clear:calc(var(--rail-w)" in CSS.replace(" ", ""),
      "📐 `--rail-clear` hisoblanadi (16+92+16 = 124px)")

# haqiqiy qiymatni olamiz
m = re.search(r"--rail-w:\s*([0-9]+)px", CSS)
i = re.search(r"--rail-inset:\s*([0-9]+)px", CSS)
g = re.search(r"--rail-gap:\s*([0-9]+)px", CSS)
if m and i and g:
    total = int(m.group(1)) + int(i.group(1)) + int(g.group(1))
    check(total == 124,
          "📐 arifmetika: %d + %d + %d = %dpx (kutilgan 124px)"
          % (int(m.group(1)), int(i.group(1)), int(g.group(1)), total))

section("4) 🔴🔴 eskirgan yo'l build'da qolib ketmaganmi?")

check("html body .rail-clear" in CSS,
      "🔴 eskirgan `md:pl-[124px]` emas, yangi qoida ishlatilmoqda")

print()
if FAILS:
    print("NATIJA: ❌ MUAMMO BOR  (%d ta)" % len(FAILS))
    for f in FAILS:
        print("   • " + f)
    sys.exit(1)
print("NATIJA: ✅ BARCHASI TO'G'RI")
