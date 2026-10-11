#!/usr/bin/env python3
"""
Telegram WebApp splash icon generator — NEON STORE (ikki uslub).

Telegram talabi:
    "Use an SVG file with a canvas size of 512x512 and a single <path>
     element inside"

Chiqaradiganlar:
    public/splash.svg          — TO'LDIRILGAN (solid) uslub
    public/splash-outline.svg  — CHIZIQLI (kontur) uslub
    public/splash-preview*.png — tekshirish uchun (Telegram yuklamaydi)

Ikkala uslubda ham: 512x512, FAQAT bitta <path>, orqa fon YO'Q,
rang qora, logo kadr markazida.

Ishga tushirish:  python3 tools/make_splash_svg.py
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

CANVAS = 512
OUT_DIR = Path(__file__).resolve().parent.parent / "public"
LOGO_COLOR = "#000000"
# Telegram belgini o'z o'lchamida chizadi — logo maydonni to'ldirishi kerak.
ART_SCALE = 1.38
# Kontur uslubidagi chiziq qalinligi
STROKE = 13

# --- Geometriya (logik koordinatalar, 512 maydonga keyin joylashtiriladi) ----
LEFT = (165, 150, 225, 370)    # N — chap ustun   x0,y0,x1,y1
RIGHT = (287, 205, 347, 360)   # N — o'ng ustun
BAR_R = 30                     # ustun burchagi
DIAG = (230, 195, 282, 345)    # N — diagonal
DIAG_W = 60                    # diagonal balandligi
STAR_CX, STAR_CY = 322, 155    # yulduz markazi
STAR_OUT, STAR_IN = 55, 23     # yulduz radiusi


# ---------------------------------------------------------------- geometriya
def rounded_rect(x0: float, y0: float, x1: float, y1: float, r: float) -> str:
    r = min(r, abs(x1 - x0) / 2, abs(y1 - y0) / 2)
    return (
        f"M {x0 + r:.1f} {y0:.1f} "
        f"L {x1 - r:.1f} {y0:.1f} "
        f"A {r:.1f} {r:.1f} 0 0 1 {x1:.1f} {y0 + r:.1f} "
        f"L {x1:.1f} {y1 - r:.1f} "
        f"A {r:.1f} {r:.1f} 0 0 1 {x1 - r:.1f} {y1:.1f} "
        f"L {x0 + r:.1f} {y1:.1f} "
        f"A {r:.1f} {r:.1f} 0 0 1 {x0:.1f} {y1 - r:.1f} "
        f"L {x0:.1f} {y0 + r:.1f} "
        f"A {r:.1f} {r:.1f} 0 0 1 {x0 + r:.1f} {y0:.1f} Z"
    )


def star_points(cx: float, cy: float, r_out: float, r_in: float,
                rot_deg: float = -90.0) -> list[tuple[float, float]]:
    pts = []
    for i in range(10):
        ang = math.radians(rot_deg + i * 36)
        r = r_out if i % 2 == 0 else r_in
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    return pts


def _content_center() -> tuple[float, float]:
    xs = [LEFT[0], LEFT[2], RIGHT[0], RIGHT[2], DIAG[0], DIAG[1]]
    ys = [LEFT[1], LEFT[3], RIGHT[1], RIGHT[3], DIAG[2], DIAG[3]]
    for x, y in star_points(STAR_CX, STAR_CY, STAR_OUT, STAR_IN):
        xs.append(x)
        ys.append(y)
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2


_CX, _CY = _content_center()
_OX = CANVAS / 2 - _CX * ART_SCALE
_OY = CANVAS / 2 - _CY * ART_SCALE
_K = ART_SCALE


def place(x: float, y: float) -> tuple[float, float]:
    """Logik koordinata -> 512x512 kadr koordinatasi (markazda, kattalashtirilgan)."""
    return (x * _K + _OX, y * _K + _OY)


def _inset_polygon(pts: list[tuple[float, float]], t: float) -> list[tuple[float, float]]:
    """Ko'pburchakni t izchalaslik ichkariga suradi (konveks shakllar uchun).

    Har bir yon chiziq ichki normal bo'yicha `t` ga suriladi, keyin
    qo'shni chiziqlar kesishgan nuqtasi yangi burchak bo'ladi — shuning
    uchun chiziq qalinligi hamma joyda BIREXIM chiqadi (markazga qarab
    qisqartirish esa diagonalda notekislik qoldirardi).
    """
    n = len(pts)
    gx = sum(p[0] for p in pts) / n
    gy = sum(p[1] for p in pts) / n

    lines = []
    for i in range(n):
        ax, ay = pts[i]
        bx, by = pts[(i + 1) % n]
        ex, ey = bx - ax, by - ay
        ln = math.hypot(ex, ey) or 1.0
        # ichkariga qaragan normal
        nx, ny = ey / ln, -ex / ln
        if nx * (gx - ax) + ny * (gy - ay) < 0:
            nx, ny = -nx, -ny
        lines.append(((ax + nx * t, ay + ny * t), (bx + nx * t, by + ny * t)))

    def inter(l1, l2):
        (x1, y1), (x2, y2) = l1
        (x3, y3), (x4, y4) = l2
        d = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(d) < 1e-9:
            return ((x1 + x2) / 2, (y1 + y2) / 2)
        a = x1 * y2 - y1 * x2
        b = x3 * y4 - y3 * x4
        return ((a * (x3 - x4) - (x1 - x2) * b) / d,
                (a * (y3 - y4) - (y1 - y2) * b) / d)

    return [inter(lines[i - 1], lines[i]) for i in range(n)]


def _shrink(pts: list[tuple[float, float]], inset: float) -> list[tuple[float, float]]:
    """Nuqtalarni o'z markaziga qarab surib, ichkariga qisqartiradi."""
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    out = []
    for x, y in pts:
        dx, dy = x - cx, y - cy
        d = math.hypot(dx, dy) or 1.0
        # radial qisqartirish chiziq qalinligiga yaqin bo'lishi uchun
        f = max(0.0, (d - inset) / d)
        out.append((cx + dx * f, cy + dy * f))
    return out


def _diag_points() -> list[tuple[float, float]]:
    dx0, dy0, dx1, dy1 = DIAG
    dsk = dy1 - dy0 - DIAG_W
    return [(dx0, dy0), (dx1, dy0 + dsk), (dx1, dy1), (dx0, dy1 - dsk)]


def _d(pts: list[tuple[float, float]]) -> str:
    return "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in
                             [place(*p) for p in pts]) + " Z"


# ------------------------------------------------------------------- uslublar
def _bar(b, shrink: float = 0.0) -> str:
    """Ustunni kadr koordinatlarida yumaloq to'rtburchak qilib qaytaradi."""
    x0, y0 = place(b[0] + shrink, b[1] + shrink)
    x1, y1 = place(b[2] - shrink, b[3] - shrink)
    return rounded_rect(x0, y0, x1, y1, r=max(1.0, (BAR_R - shrink) * _K))


def build_solid() -> str:
    subs: list[str] = [
        _bar(LEFT),
        _bar(RIGHT),
        _d(_diag_points()),
        _d(star_points(STAR_CX, STAR_CY, STAR_OUT, STAR_IN)),
    ]
    return _wrap(" ".join(subs))


def build_outline() -> str:
    """Kontur usluli: har element 'halqa' — tashqi + ichki (teshik)."""
    s = STROKE / _K            # chiziq qalinligi logik koordinatada
    subs: list[str] = []

    # N ustunlari (tashqi + ichki -> kontur)
    for b in (LEFT, RIGHT):
        subs.append(_bar(b, 0))
        subs.append(_bar(b, s))

    # N diagonali — to'g'ri geometrik inset
    diag = _diag_points()
    subs.append(_d(diag))
    subs.append(_d(_inset_polygon(diag, s)))

    # Yulduz — markazga qarab masshtab (uchli yulduzda bu tabiiyroq)
    star = star_points(STAR_CX, STAR_CY, STAR_OUT, STAR_IN)
    subs.append(_d(star))
    k_in = 1 - STROKE / (STAR_OUT * _K)
    subs.append(_d([(STAR_CX + (x - STAR_CX) * k_in,
                      STAR_CY + (y - STAR_CY) * k_in) for x, y in star]))

    return _wrap(" ".join(subs), evenodd=True)


def _wrap(d: str, evenodd: bool = False) -> str:
    rule = ' fill-rule="evenodd" clip-rule="evenodd"' if evenodd else ""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" '
        'width="512" height="512">'
        f'<path fill="{LOGO_COLOR}"{rule} d="{d}"/>'
        "</svg>"
    )


# ------------------------------------------------------------------- preview
def _draw(d: ImageDraw.ImageDraw, ink, hole, outline: bool) -> None:
    """Logo chizadi.

    DIQQAT: kontur uslubida har bir element "tashqi + ichki" juftligi.
    Preview SVG ning evenodd natijasini TO'G'RI ko'rsatishi uchun:
      1) avval tashqi shakllar siyoh bilan chiziladi
      2) keyin ichki shakllar FON rangiga qayta chiziladi (teshik)
    Aks holda preview kontur chiziqlarini alohida chizib, haqiqiy
    natijani ko'rsatmay qolardi.
    """
    if not outline:
        for b in (LEFT, RIGHT):
            (ax, ay), (bx, by) = place(b[0], b[1]), place(b[2], b[3])
            d.rounded_rectangle([ax, ay, bx, by], radius=BAR_R * _K, fill=ink)
        d.polygon([place(*p) for p in _diag_points()], fill=ink)
        d.polygon([place(x, y) for x, y in
                   star_points(STAR_CX, STAR_CY, STAR_OUT, STAR_IN)], fill=ink)
        return

    st = STROKE / _K
    star = star_points(STAR_CX, STAR_CY, STAR_OUT, STAR_IN)
    k_in = 1 - STROKE / (STAR_OUT * _K)
    star_in = [(STAR_CX + (x - STAR_CX) * k_in, STAR_CY + (y - STAR_CY) * k_in)
               for x, y in star]
    diag = _diag_points()
    diag_in = _inset_polygon(diag, st)

    # 1) tashqi (siyoh)
    for b in (LEFT, RIGHT):
        (ax, ay), (bx, by) = place(b[0], b[1]), place(b[2], b[3])
        d.rounded_rectangle([ax, ay, bx, by], radius=BAR_R * _K, fill=ink)
    for pts in (diag, star):
        d.polygon([place(x, y) for x, y in pts], fill=ink)

    # 2) ichki (teshik)
    for b in (LEFT, RIGHT):
        (ax, ay) = place(b[0] + st, b[1] + st)
        (bx, by) = place(b[2] - st, b[3] - st)
        d.rounded_rectangle([ax, ay, bx, by],
                            radius=max(1.0, (BAR_R - st) * _K), fill=hole)
    for pts in (diag_in, star_in):
        d.polygon([place(x, y) for x, y in pts], fill=hole)


def build_preview(outline: bool = False, bg=None) -> Image.Image:
    mode = "RGBA" if bg is None else "RGB"
    im = Image.new(mode, (CANVAS, CANVAS), (0, 0, 0, 0) if bg is None else bg)
    ink = (0, 0, 0, 255) if bg is None else (0, 0, 0)
    hole = (0, 0, 0, 0) if bg is None else bg
    _draw(ImageDraw.Draw(im), ink, hole, outline)
    return im


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    (OUT_DIR / "splash.svg").write_text(build_solid(), encoding="utf-8")
    (OUT_DIR / "splash-outline.svg").write_text(build_outline(), encoding="utf-8")

    build_preview(False).save(OUT_DIR / "splash-preview.png", "PNG")
    build_preview(False, (11, 14, 20)).save(OUT_DIR / "splash-preview-dark.png", "PNG")
    build_preview(True).save(OUT_DIR / "splash-outline-preview.png", "PNG")
    build_preview(True, (11, 14, 20)).save(OUT_DIR / "splash-outline-preview-dark.png", "PNG")

    for name in ("splash.svg", "splash-outline.svg"):
        svg = (OUT_DIR / name).read_text(encoding="utf-8")
        n = svg.count("<path")
        assert n == 1, f"{name}: {n} ta <path> (1 bo'lishi kerak)"
        assert "viewBox=\"0 0 512 512\"" in svg
        print(f"✅ public/{name:22} (1 ta <path>, {(OUT_DIR / name).stat().st_size/1024:.1f} KB)")
    print("✅ 4 ta preview PNG (shaffof + tun rejimi, ikkala uslub uchun)")