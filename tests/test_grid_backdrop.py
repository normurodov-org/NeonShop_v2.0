# -*- coding: utf-8 -*-
"""Grid backdrop mantig'i — rASM ASOSIDA RAQAMLAR BILAN SINOV.

🔴 NIMA UCHUN PYTHON?
   `GridBackdrop.tsx` ichida bo'lsa, sinab bo'lmasdi: headless
   brauzerda `requestAnimationFrame` ISHLAMAYDI (o'lchangan:
   `rAFIshlayapti: false`) va canvas yo'q. Shuning uchun mantiq
   `src/lib/gridBackdrop.ts` da ajratilgan — u DOM'siz, oddiy
   TypeScript/JS, va shu yerda to'g'ridan-to'g'ri sinanadi.

🔴 SINOV QANDAY ISHLAYDI?
   `src/lib/gridBackdrop.ts` dagi funksiyalar TypeScript bo'lgani
   uchun ularni shu yerda qayta yozamiz (bir xil formula), real
   kadrni esa `CanvasRenderingContext2D` o'rniga TEKISH obyektiga
   chizib, chizilgan narsalarni tekshiramiz.
"""
import io
import math
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FAILS = []


def check(cond, msg):
    print(("  \u2705 " if cond else "  \u274c ") + msg)
    if not cond:
        FAILS.append(msg)


def section(t):
    print("\n" + "=" * 77)
    print(t)
    print("=" * 77)


# =============================================================================
section("1) \U0001F5FA\U0001F534\U0001F534FE0F SOURCE KONSISTENTLIGI")
# =============================================================================
SRC = io.open(os.path.join(ROOT, "src/lib/gridBackdrop.ts"),
              encoding="utf-8").read()
COMP = io.open(os.path.join(ROOT, "src/components/GridBackdrop.tsx"),
               encoding="utf-8").read()
APP = io.open(os.path.join(ROOT, "src/App.tsx"), encoding="utf-8").read()

for fn in ("buildGrid", "stepNodes", "drawFrame"):
    check("export function %s" % fn in SRC, "\U0001F5FA\U0001F534\U0001F534FE0F `%s` eksport qilingan" % fn)
    check(fn in COMP, "\U0001F5FA\U0001F534\U0001F534FE0F komponent `%s` dan foydalanadi" % fn)
# heatOf chizish ichida (drawFrame) ishlatiladi — komponentdan
# bevosita chaqirilmaydi, shuning uchun alohida tekshiriladi.
check("export function heatOf" in SRC, "heatOf eksport qilingan")
check("heatOf(" in SRC.split("export function drawFrame")[1],
      "drawFrame ichida nuqta qizarganligi hisoblanadi")

# 🔴 Mantiq ikki yerda KO'CHA yozilmasin — komponent moduldan oladi
check("function buildGrid(" not in COMP, "\U0001F534\U0001F534\U0001F534 mantiq komponentda TAKROR yozilmagan")
check("buildGrid(W, H, cell)" in COMP, "\U0001F534\U0001F534\U0001F534 to'r moduldan quriladi")

# 🔴 Bot brendiga mos ranglar (qora + yashil)
check("#000000" in SRC, "\U0001F534 qora fon (#000000)")
check("PALETTE_DARK" in SRC and "PALETTE_LIGHT" in SRC, "\U0001F5FA\U0001F534\U0001F534FE0F ikkala palitra")
# 🌈 OQ-QORA (bot dizayni) — YASHIL QOLMADI
dots = re.findall(r"rgba\((\d+),\s*(\d+),\s*(\d+)", SRC)
green = [d for d in dots if int(d[1]) > int(d[0]) and int(d[1]) > int(d[2])]
check(len(green) == 0, "🔴🔴🔴 YASHIL rang QOLMADI (%d ta)" % len(green))
grey = [d for d in dots if d[0] == d[1] == d[2]]
check(len(grey) >= 4, "🔴🔴 oq-qora (kulrang) ranglar: %d ta" % len(grey))
check("dot: 'rgba(255, 255, 255, 0.34)'" in SRC, "🔴🔴🔴 nuqta oq")
check("dotHot: 'rgba(255, 255, 255, 1)'" in SRC, "🔴🔴🔴 kursor ostidagi nuqta to'liq oq")
check("dot: 'rgba(0, 0, 0, 0.30)'" in SRC, "🔴🔴🔴 yorug' rejimda nuqta qora")

# 🔴🔴🔴 Glow (kursor ostidagi yorug'lik) va TOLQIN doirasi OLIB TASHLANGAN
body = SRC.split("export function drawFrame", 1)[1]
check("createRadialGradient" not in body,
      "🔴🔴🔴 kursor ostidagi YORUG'LIK (glow) chizilmaydi")
check("P.wave" not in body, "🔴🔴🔴 tolqin DOIRASI chizilmaydi")
check("glow" not in SRC, "🔴🔴🔴 palitradagi glow maydoni ham olib tashlandi")

# 🌐 VERTIKAL chiziq ham bor
check("showLines" in SRC, "📄 `showLines` — chiziqlarni o'chirish mumkin")
check("prevX = Math.round(n.ox)" in body, "📄📄 VERTIKAL chiziq chiziladi")
check("prevY = Math.round(n.oy)" in body, "📄📄 HORIZONTAL chiziq chiziladi")

# 🔴🔴🔴 Tugma ustida fon TO'XTAYDI
check("overUI" in COMP, "🔴🔴🔴 tugma ustida to'xtatish bor")
check("onOverUI" in COMP, "🔴🔴🔴 `pointerover` ishlovchi")
check("button, a, input, select, textarea" in COMP,
      "🔴🔴🔴 tugma/link/ input aniqlanadi")
check("stepNodes(\n          geo.nodes, cx, cy, geo.radius,\n          geo.cell * 0.42" in COMP
      or "geo.cell * 0.42,   // surish" in COMP,
      "🔴🔴🔴 fonda surish (push = 0.42) ishlaydi")
check("stepNodes(geo.nodes, cx, cy, geo.radius, 0, 0.16)" in COMP,
      "🔴🔴🔴🔴 tugma ustida surish NOL (faqat qaytish)")
check("(active && !overUI && !reducedMotion())" in COMP,
      "🔴🔴🔴 tugma ustida animatsiya to'xtaydi")

# 🔴 TDZ: `overUI` `onOverUI` dan OLDIN e'lon bo'lishi kerak
check(COMP.index("let overUI = false;") < COMP.index("const onOverUI"),
      "🔴🔴🔴 `overUI` `onOverUI` dan OLDIN e'lon qilingan (TDZ xatosi yo'q)")

# 🔴 Aurora olib tashlangan
check("aurora-blob" not in APP, "\U0001F534 asosiy ekranda `aurora-blob` YO'Q")
check(APP.count("<GridBackdrop") == 3,
      "\U0001F5FA\U0001F534\U0001F534FE0F GridBackdrop 3 ekranda (kirish / bot-to\u02bcxtatilgan / asosiy)")

# =============================================================================
section("2) \U0001F9EA TO'R QURILISHI (buildGrid)")
# =============================================================================


def build_grid(W, H, cell):
    out = []
    cols = math.ceil(W / cell) + 1
    rows = math.ceil(H / cell) + 1
    off_x = (W - (cols - 1) * cell) / 2
    off_y = (H - (rows - 1) * cell) / 2
    for r in range(rows):
        for c in range(cols):
            x = off_x + c * cell
            y = off_y + r * cell
            out.append({"x": x, "y": y, "ox": x, "oy": y})
    return out


W, H, CELL = 1000.0, 800.0, 46.0
nodes = build_grid(W, H, CELL)
check(len(nodes) > 100, "\U0001F5FA\U0001F534\U0001F534FE0F nuqtalar soni: %d" % len(nodes))
check(all(n["x"] == n["ox"] and n["y"] == n["oy"] for n in nodes),
      "\U0001F534\U0001F534\U0001F534 barcha nuqta TINCH holatda boshlanadi")

# 🔴 Tor o'rtada (chapdan kosmos qolmasin)
xs = sorted({round(n["x"], 3) for n in nodes})
left_gap = xs[0]
right_gap = W - xs[-1]
check(abs(left_gap - right_gap) < 1.5,
      "\U0001F5FA\U0001F534\U0001F534FE0F tor markazda (chap %.1f / o\u02b8ng %.1f)" % (left_gap, right_gap))

# 🔴 Telefonda katak kichrayadi (ko'\u02b8proq nuqta)
small = build_grid(390.0, 780.0, 34.0)
big = build_grid(390.0, 780.0, 46.0)
check(len(small) > len(big),
      "\U0001F5FA\U0001F534\U0001F534FE0F telefon ekranida ko'\u02b8proq nuqta (%d > %d)" % (len(small), len(big)))

# =============================================================================
section("3) \U0001F9EA KURSOR TA'SIRI (rasmdagi effekt)")
# =============================================================================


def heat(x, y, cx, cy, radius):
    dx, dy = x - cx, y - cy
    d2 = dx * dx + dy * dy
    if d2 >= radius * radius:
        return 0.0
    return (1.0 - math.sqrt(d2) / radius) ** 2


def step_nodes(nodes, cx, cy, radius, push, pull):
    R2 = radius * radius
    for n in nodes:
        dx, dy = n["x"] - cx, n["y"] - cy
        d2 = dx * dx + dy * dy
        if d2 < R2 and d2 > 1e-6:
            d = math.sqrt(d2)
            f = (1.0 - d / radius) ** 2 * push
            n["x"] = n["ox"] + (dx / d) * f
            n["y"] = n["oy"] + (dy / d) * f
        else:
            n["x"] += (n["ox"] - n["x"]) * pull
            n["y"] += (n["oy"] - n["y"]) * pull


RADIUS = CELL * 3.0
PUSH = CELL * 0.42
CX, CY = 500.0, 400.0

# 🔴 1) KURSORGA YAQIN nuqta SURILADI
near = [n for n in nodes
        if 10 < math.hypot(n["ox"] - CX, n["oy"] - CY) < 70]
check(len(near) > 0, "\U0001F9EA kursor yaqinida nuqta bor: %d" % len(near))
before_d = [math.hypot(n["ox"] - CX, n["oy"] - CY) for n in near]
step_nodes(nodes, CX, CY, RADIUS, PUSH, 0.16)
after_d = [math.hypot(n["x"] - CX, n["y"] - CY) for n in near]
moved_out = sum(1 for a, b in zip(before_d, after_d) if b > a + 0.01)
check(moved_out == len(near),
      "\U0001F534\U0001F534\U0001F534 yaqin nuqtalar SURILDI: %d/%d" % (moved_out, len(near)))

# 🔴 2) UZOQ nuqta QIMOD qoladi
far = [n for n in nodes if math.hypot(n["ox"] - CX, n["oy"] - CY) > RADIUS * 1.5]
step_nodes(nodes, CX, CY, RADIUS, PUSH, 0.16)
moved_far = [n for n in far
             if abs(n["x"] - n["ox"]) > 0.5 or abs(n["y"] - n["oy"]) > 0.5]
check(len(moved_far) == 0,
      "\U0001F534\U0001F534\U0001F534 uzoq nuqtalar qimod (%d/%d o\u02b8zgargan)"
      % (len(moved_far), len(far)))

# 🔴 3) RADIAL YO'NALISH — nuqta kursor tomon EMAS, UZQOQ qaraydi
sample = next(n for n in nodes
              if 15 < math.hypot(n["ox"] - CX, n["oy"] - CY) < 70)
ox0, oy0 = sample["ox"], sample["oy"]
step_nodes([sample], CX, CY, RADIUS, PUSH, 0.16)
v_from = (ox0 - CX, oy0 - CY)
v_to = (sample["x"] - ox0, sample["y"] - oy0)
dot = v_from[0] * v_to[0] + v_from[1] * v_to[1]
check(dot > 0, "\U0001F534\U0001F534\U0001F534 surish RADIAL (kursordan uzoq tomon)")

# 🔴 4) MAXIMAL SURISH markazda — chetda deyarli nol
center_max = (1.0 - 1.0 / RADIUS) ** 2 * PUSH
edge_max = (1.0 - 0.90) ** 2 * PUSH
check(center_max > edge_max * 10,
      "\U0001F534\U0001F534\U0001F534 markizda eng kuchli (%.2f px) va chetda deyarli yo'q (%.3f px)"
      % (center_max, edge_max))

# 🔴 5) QAYTISH — kursor UZOQLASHGACHON nuqtalar tinch holatga QAYTADI
settled = build_grid(W, H, CELL)
# Avval kursor ostidagi nuqtalarni SURDIRIChI
for _ in range(3):
    step_nodes(settled, CX, CY, RADIUS, PUSH, 0.16)
displaced = max(math.hypot(n["x"] - n["ox"], n["y"] - n["oy"]) for n in settled)
check(displaced > 1.0,
      "📌 kursor ostida nuqtalar siljigan (%.2f px)" % displaced)

# 🔴🔴🔴 Kursorni UZOQGA olib ketamiz (radius = 0) — surish
#    toʼxtaydi, faqat `pull` ishlaydi. SHU YERDA qaytish tekshiriladi:
#    (kursor oʼz joyida tursa, surish har doim ustun kelar — bu normal,
#     aynan shuning uchun test u ham oʼzgartamiz)
for _ in range(400):
    step_nodes(settled, -9999.0, -9999.0, 0.0, PUSH, 0.16)
resid = max(math.hypot(n["x"] - n["ox"], n["y"] - n["oy"]) for n in settled)
check(resid < 0.01,
      "🔴🔴🔴 kursor qoʼʸygachon nuqtalar QAYTADI (qoldiq %.5f px)" % resid)

# 🔴 6) QAYTISH sekinroq (spring emas)
one = build_grid(W, H, CELL)
step_nodes(one, CX, CY, RADIUS, PUSH, 0.16)
d1 = max(math.hypot(n["x"] - n["ox"], n["y"] - n["oy"]) for n in one)
check(0 < d1 < PUSH, "\U0001F5FA\U0001F534\U0001F534FE0F bitta qadamda siljish %.2f px (birdan qaytmaydi)" % d1)

# =============================================================================
section("4) \U0001F9EA QIZGARNISH (nuqta kattalashuvi)")
# =============================================================================
h_center = heat(CX, CY, CX, CY, RADIUS)
h_mid = heat(CX + RADIUS / 2, CY, CX, CY, RADIUS)
h_edge = heat(CX + RADIUS * 0.95, CY, CX, CY, RADIUS)
h_far = heat(CX + RADIUS * 2, CY, CX, CY, RADIUS)
check(h_center == 1.0, "\U0001F534 markiz to'liq qiziladi (%.2f)" % h_center)
check(h_mid < h_center, "\U0001F534\U0001F534\U0001F534 o'rta nuqta o'rtacha (%.2f)" % h_mid)
check(h_edge < h_mid, "\U0001F534\U0001F534\U0001F534 chekka nuqta deyarli so'ng (%.3f)" % h_edge)
check(h_far == 0.0, "\U0001F534\U0001F534\U0001F534 radiusdan tashqarida so'ng qoladi")

# 🔴 Nuqta radiusi 1.1 -> 3.7 (daraja 1..3)
BASE, MAXR = 1.1, 3.7
r_c = BASE + h_center * (MAXR - BASE)
r_f = BASE + h_far * (MAXR - BASE)
check(r_c > r_f * 2, "\U0001F534\U0001F534\U0001F534 yaqin nuqta kattaroq (%.2f vs %.2f px)" % (r_c, r_f))

# =============================================================================
section("5) \U0001F9EA TOLQIN (kursor tezligi)")
# =============================================================================


def step_waves(waves, speed):
    out = []
    for w in waves:
        w["r"] += speed
        if w["r"] < w["max"]:
            out.append(w)
    return out


ws = [{"x": 10, "y": 10, "r": 4, "max": 150.0}]
after1 = step_waves(ws, 20.0)
check(len(after1) == 1 and after1[0]["r"] == 24.0, "\U0001F5FA\U0001F534\U0001F534FE0F tolqin kengayadi (4 -> 24 px)")
after2 = step_waves(after1, 20.0)
after3 = step_waves(after2, 20.0)
after4 = step_waves(after3, 20.0)
after5 = step_waves(after4, 20.0)
after6 = step_waves(after5, 20.0)
after7 = step_waves(after6, 20.0)
after8 = step_waves(after7, 20.0)
check(len(after8) == 0, "\U0001F534\U0001F534\U0001F534 tolqin oxirida YO'QOLADI")

# =============================================================================
section("6) \U0001F9EA CHIZISH (soxta canvas bilan)")
# =============================================================================


class FakeCtx:
    def __init__(self):
        self.fills = 0
        self.strokes = 0
        self.arcs = []
        self.rect = None
        self.max_dx = 0.0

    def fillRect(self, x, y, w, h):
        self.fills += 1
        self.rect = (x, y, w, h)

    def beginPath(self):
        pass

    def moveTo(self, x, y):
        pass

    def lineTo(self, x, y):
        pass

    def stroke(self):
        self.strokes += 1

    def fill(self):
        self.fills += 1

    def arc(self, x, y, r, s, e):
        self.arcs.append((round(x, 2), round(y, 2), round(r, 2)))
        self.max_dx = max(self.max_dx, r)

    def createRadialGradient(self, x, y, r0, x1, y1, r1):
        return self

    def addColorStop(self, o, c):
        pass


# Minimal canvas konteksti
ctx = FakeCtx()
ctx.fillStyle = ctx.strokeStyle = "#000"
ctx.lineWidth = 1
ctx.globalAlpha = 1

paint_nodes = build_grid(W, H, CELL)
step_nodes(paint_nodes, CX, CY, RADIUS, PUSH, 0.16)
check(len(paint_nodes) == len(nodes),
      "\U0001F5FA\U0001F534\U0001F534FE0F chiziladigan nuqtalar soni bir xil")

check(len(ctx.arcs) == 0, "\U0001F9EA boshlang\u02b4ch chizilgan yo'q")

# Endi \u00abchiz\u00bb
for n in paint_nodes:
    ctx.arc(n["x"], n["y"], 1.1, 0, 6.28)
check(len(ctx.arcs) == len(paint_nodes),
      "\U0001F5FA\U0001F534\U0001F534FE0F har bir nuqta chizildi: %d" % len(ctx.arcs))
check(ctx.max_dx <= BASE + 1e-6, "\U0001F534\u0001F535 barcha nuqta bazis radiusda (%.2f)" % ctx.max_dx)

# Kursor yonida — kattaroq
ctx2 = FakeCtx()
ctx2.fillStyle = ctx2.strokeStyle = "#000"
ctx2.lineWidth = 1
ctx2.globalAlpha = 1
hot_nodes = build_grid(W, H, CELL)
step_nodes(hot_nodes, CX, CY, RADIUS, PUSH, 0.16)
for n in hot_nodes:
    h = heat(n["x"], n["y"], CX, CY, RADIUS)
    ctx2.arc(n["x"], n["y"], 1.1 + h * (3.7 - 1.1), 0, 6.28)
check(ctx2.max_dx > BASE * 2,
      "\U0001F534\U0001F534\U0001F534 kursor yonida nuqta KATTALASHDI (%.2f px)" % ctx2.max_dx)

print()
if FAILS:
    print("NATIJA: \u274c MUAMMO BOR  (%d ta)" % len(FAILS))
    for f in FAILS:
        print("   - " + f)
    raise SystemExit(1)
print("NATIJA: \u2705 BARCHASI TO'G'RI")