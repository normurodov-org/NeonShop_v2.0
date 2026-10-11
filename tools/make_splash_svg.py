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
BG_R = 118                     # fon burchagi
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

PURPLE_A, PURPLE_B = "#7C3AED", "#DB2777"


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


def build_subpaths() -> list[str]:
    """Fon + N + yulduz: bitta <path> ichidagi subpath'lar."""
    subs: list[str] = [rounded_rect(0, 0, CANVAS, CANVAS, BG_R)]

    # N — chap ustun
    subs.append(rounded_rect(*LEFT, r=BAR_R))
    # N — o'ng ustun
    subs.append(rounded_rect(*RIGHT, r=BAR_R))

    # N — diagonal (parallelogram)
    dx0, dy0, dx1, dy1 = DIAG
    subs.append(
        f"M {dx0} {dy0} L {dx1} {dy0 + (dy1 - dy0 - DIAG_W)} "
        f"L {dx1} {dy1} L {dx0} {dy1 - (dy1 - dy0 - DIAG_W)} Z"
    )

    # Yulduz
    pts = star_points(STAR_CX, STAR_CY, STAR_OUT, STAR_IN)
    star_d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in pts) + " Z"
    subs.append(star_d)

    return subs


def build_svg(gradient: bool = True) -> str:
    d = " ".join(build_subpaths())
    if gradient:
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" '
            'width="512" height="512">'
            "<defs>"
            f'<linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
            f'<stop offset="0" stop-color="{PURPLE_A}"/>'
            f'<stop offset="0.55" stop-color="#9333EA"/>'
            f'<stop offset="1" stop-color="{PURPLE_B}"/>'
            "</linearGradient>"
            "</defs>"
            f'<path fill-rule="evenodd" clip-rule="evenodd" fill="url(#g)" d="{d}"/>'
            "</svg>"
        )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" '
        'width="512" height="512">'
        f'<path fill-rule="evenodd" clip-rule="evenodd" fill="#9333EA" d="{d}"/>'
        "</svg>"
    )


def build_preview(bg: tuple[int, int, int] = (255, 255, 255)) -> Image.Image:
    """Tasvirni tekshirish uchun PNG ko'rinishi (teshiklar fon rangida)."""
    im = Image.new("RGB", (CANVAS, CANVAS), bg)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, CANVAS - 1, CANVAS - 1], radius=BG_R, fill=(0x93, 0x33, 0xEA))
    d.rounded_rectangle(LEFT, radius=BAR_R, fill=bg)
    d.rounded_rectangle(RIGHT, radius=BAR_R, fill=bg)

    dx0, dy0, dx1, dy1 = DIAG
    d.polygon([(dx0, dy0), (dx1, dy0 + (dy1 - dy0 - DIAG_W)),
               (dx1, dy1), (dx0, dy1 - (dy1 - dy0 - DIAG_W))], fill=bg)
    d.polygon(star_points(STAR_CX, STAR_CY, STAR_OUT, STAR_IN), fill=bg)
    return im


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    svg = build_svg(gradient=True)
    (OUT_DIR / "splash.svg").write_text(svg, encoding="utf-8")

    (OUT_DIR / "splash-solid.svg").write_text(build_svg(gradient=False), encoding="utf-8")

    build_preview().save(OUT_DIR / "splash-preview.png", "PNG")

    n_paths = svg.count("<path")
    print(f"✅ public/splash.svg        ({n_paths} ta <path>, {len(svg)} belgi)")
    print("✅ public/splash-solid.svg  (faqat bitta rang — zaxira variant)")
    print("✅ public/splash-preview.png (tekshirish uchun)")

    assert n_paths == 1, f"FAQAT BITTA <path> bo'lishi kerak, topildi: {n_paths}"
    print("   Telegram talabi: bitta <path> ✅")