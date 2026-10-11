#!/usr/bin/env python3
"""
Telegram WebApp splash icon generator — NEON STORE.

Telegram talabi (rasmdagi matn):
    "Use an SVG file with a canvas size of 512x512 and a single <path>
     element inside"

Shuning uchun bu skript:
  • 512x512 SVG yaratadi
  • ichida FAQAT bitta <path> (defs/gradient bilan)
  • fill-rule="evenodd" orqali N harfi va yulduz "teshik" qilinadi —
    ya'ni tasvir bitta yopiq shakl + ichidagi bo'shliqlar

Ishga tushirish:  python3 tools/make_splash_svg.py
Natija:
    public/splash.svg         — asosiy (gradient bilan)
    public/splash-solid.svg   — zaxira (faqat bir rang)
    public/splash-preview.png — tekshirish uchun (Telegram yuklamaydi)
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

CANVAS = 512
OUT_DIR = Path(__file__).resolve().parent.parent / "public"

# --- Geometriya (512x512 maydon) ---------------------------------------------
BG_R = 118                     # (fon olib tashlandi — saqlanib qoldi)
LEFT = (165, 150, 225, 370)    # chap ustun  x0,y0,x1,y1
RIGHT = (287, 205, 347, 360)   # o'ng ustun
BAR_R = 30                     # ustun burchagi
DIAG = (230, 195, 282, 345)    # diagonal: x0,y0(x1 y0),x1,y1(x2)
DIAG_W = 60                    # diagonal kengligi
# Yulduz o'ng ustunning USTIDA turadi (brend logosi kabi).
#
# MUHIM: 5 burchakli yulduzning pastki uchi (90°) r_in radiusda bo'ladi,
# lekin uning OYOG'LARI (54° va 126°) r_out radiusga cho'zilib ketadi.
# Ya'ni haqiqiy pastki chegar: CY + STAR_OUT * sin(54°) ≈ 0.809 * STAR_OUT.
# fill-rule="evenodd" da chiziqlar kesib ketSA, u yerda tasvir QAYTADI
# (dog'a qoladi) — shuning uchun ustunga tegmasligi kerak.
STAR_CX, STAR_CY = 322, 155    # yulduz markazi
STAR_OUT, STAR_IN = 55, 23     # yulduz radiusi

# Telegram splash: fon yo‘q, faqat qora logo (rasmdagi namunaga o‘xshash)
LOGO_COLOR = "#000000"
# Telegram splash belgisini o'z o'lchamida chizadi — shuning uchun logo
# 512x512 maydonni imkon bo'lganicha to'ldirishi kerak.
ART_SCALE = 1.38


# ---------------------------------------------------------------- yordamchilar
def rounded_rect(x0: float, y0: float, x1: float, y1: float, r: float) -> str:
    """Yumaloq to'rtburchak -> SVG path."""
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


def content_bounds() -> tuple[float, float, float, float]:
    """Logo chegaralari (markazga tekislash uchun)."""
    xs: list[float] = []
    ys: list[float] = []
    for x0, y0, x1, y1 in (LEFT, RIGHT):
        xs += [x0, x1]
        ys += [y0, y1]
    dx0, dy0, dx1, dy1 = DIAG
    xs += [dx0, dx1]
    ys += [dy0, dy1]
    for x, y in star_points(STAR_CX, STAR_CY, STAR_OUT, STAR_IN):
        xs.append(x)
        ys.append(y)
    return min(xs), min(ys), max(xs), max(ys)


def content_center() -> tuple[float, float]:
    """Logo geometriyasining markazi (chizilgan koordinatalarda)."""
    x0, y0, x1, y1 = content_bounds()
    return (x0 + x1) / 2, (y0 + y1) / 2


def _tf() -> tuple[float, float, float]:
    """(siljitma x, siljitma y, masshtab) — markazga tekislash uchun."""
    cx, cy = content_center()
    return (CANVAS / 2 - cx * ART_SCALE, CANVAS / 2 - cy * ART_SCALE, ART_SCALE)


def place(x: float, y: float) -> tuple[float, float]:
    """Logo koordinatasini kadr markaziga keltiradi va kattalashtiradi."""
    ox, oy, s = _tf()
    return (x * s + ox, y * s + oy)


def build_subpaths() -> list[str]:
    """Fon + N + yulduz: bitta <path> ichidagi subpath'lar."""
    # DIQQAT: fon (yumaloq kvadrat) QO'SHILMAYDI — Telegram splash'da
    # faqat logo ko'rsatiladi, orqa foni shaffof qoladi.
    _, _, k = _tf()
    subs: list[str] = []

    def box(b):
        x0, y0 = place(b[0], b[1])
        x1, y1 = place(b[2], b[3])
        return [x0, y0, x1, y1]

    # N — chap ustun
    subs.append(rounded_rect(*box(LEFT), r=BAR_R * k))
    # N — o'ng ustun
    subs.append(rounded_rect(*box(RIGHT), r=BAR_R * k))

    # N — diagonal (parallelogram)
    dx0, dy0, dx1, dy1 = DIAG
    dsk = dy1 - dy0 - DIAG_W
    pts = [place(dx0, dy0), place(dx1, dy0 + dsk), place(dx1, dy1), place(dx0, dy1 - dsk)]
    subs.append("M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in pts) + " Z")

    # Yulduz
    star_pts = [place(x, y) for x, y in star_points(STAR_CX, STAR_CY, STAR_OUT, STAR_IN)]
    subs.append("M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in star_pts) + " Z")

    return subs


def build_svg(gradient: bool = True) -> str:
    d = " ".join(build_subpaths())
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" '
        'width="512" height="512">'
        f'<path fill="{LOGO_COLOR}" d="{d}"/>'
        "</svg>"
    )


def _draw_logo(d: ImageDraw.ImageDraw, ink) -> None:
    """Logoni chizadi (qora rang, foni yo'q)."""
    ox, oy, k = _tf()
    for b in (LEFT, RIGHT):
        (ax, ay), (bx, by) = place(b[0], b[1]), place(b[2], b[3])
        d.rounded_rectangle([ax, ay, bx, by], radius=BAR_R * k, fill=ink)
    dx0, dy0, dx1, dy1 = DIAG
    dsk = dy1 - dy0 - DIAG_W
    d.polygon([place(dx0, dy0), place(dx1, dy0 + dsk),
               place(dx1, dy1), place(dx0, dy1 - dsk)], fill=ink)
    d.polygon([place(x, y) for x, y in
               star_points(STAR_CX, STAR_CY, STAR_OUT, STAR_IN)], fill=ink)


def build_preview(bg=None) -> Image.Image:
    """Tekshirish rasmi.

    DIQQAT: avvalgi versiya RGB (oq fonli) edi — shuning uchun "fon bor"
    deb ko'rinyapti, garchi splash.svg da fon YO'Q edi.
    Endi default: RGBA + shaffof fon (alpha=0) — ya'ni orqa fonsiz.
    """
    mode = "RGBA" if bg is None else "RGB"
    im = Image.new(mode, (CANVAS, CANVAS), (0, 0, 0, 0) if bg is None else bg)
    _draw_logo(ImageDraw.Draw(im), (0, 0, 0, 255) if bg is None else (0, 0, 0))
    return im


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    svg = build_svg()
    (OUT_DIR / "splash.svg").write_text(svg, encoding="utf-8")

    # 1) shaffof fonli (asl ko'rinish — orqa fon YO'Q)
    build_preview().save(OUT_DIR / "splash-preview.png", "PNG")
    # 2) Telegram TUNG rejimida qanday ko'rinishini ko'rsatish uchun
    build_preview(bg=(11, 14, 20)).save(OUT_DIR / "splash-preview-dark.png", "PNG")

    n_paths = svg.count("<path")
    print(f"✅ public/splash.svg        ({n_paths} ta <path>, {len(svg)} belgi)")
    print("✅ public/splash-preview.png       (shaffof fon — orqa fon YO'Q)")
    print("✅ public/splash-preview-dark.png  (Telegram tun rejimi)")

    assert n_paths == 1, f"FAQAT BITTA <path> bo'lishi kerak, topildi: {n_paths}"
    print("   Telegram talabi: bitta <path> ✅")