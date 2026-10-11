#!/usr/bin/env python3
"""
Splash icon generator — NeonShop (Telegram WebApp).

Nima qiladi: brend logosi (public/logo.svg) asosida 640x640 PNG yaratadi —
Telegram WebApp "Set Splash Icon" uchun to'liq kvadrat (burchaklar yumaloq
EMAS, Telegram o'zi maskalaydi).

Ishga tushirish:  python3 tools/make_splash.py
Natija:          public/splash.png   (640x640)
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

SIZE = 640
# Logoning kattaligi (1.0 = logo.svg asl o'lchami). Telegram splash'da
# belgi kadrni to'ldirishi uchun biroz kattaroq bo'lishi tabiiy.
LOGO_SCALE = 1.16
CENTER = 256.0  # logo.svg markazi
OUT = Path(__file__).resolve().parent.parent / "public" / "splash.png"

# --- Brend ranglari (logo.svg bilan bir xil) ---------------------------------
BG_STOPS = [
    (0.00, (0x7C, 0x3A, 0xED)),   # #7c3aed
    (0.45, (0x93, 0x33, 0xEA)),   # #9333ea
    (0.85, (0xC0, 0x26, 0xD3)),   # #c026d3
    (1.00, (0xDB, 0x27, 0x77)),   # #db2777
]
STAR_TOP = (0xFD, 0xE0, 0x47)     # #fde047
STAR_BOTTOM = (0xF5, 0x9E, 0x0B)  # #f59e0b
WHITE = (0xFF, 0xFF, 0xFF)
N_SHADE = (0xED, 0xE9, 0xFE)     # #ede9fe (diagonal bog'lovchi)
SHADOW = (0x4C, 0x1D, 0x95)      # #4c1d95


def make_mapper(size: int):
    """logo.svg koordinatalarini splash maydoniga o'tkazadi (markazga bog'liq)."""
    unit = size / 512
    scale = unit * LOGO_SCALE
    off = size / 2 - CENTER * scale

    def L(x: float, y: float) -> tuple[float, float]:
        return (x * scale + off, y * scale + off)

    return L, scale


def lerp(a: int, b: int, t: float) -> int:
    return int(round(a + (b - a) * t))


def gradient_background(size: int) -> Image.Image:
    """Vertikal brend gradienti + chapdan yuqoriga yumshoq yorug'lik."""
    img = Image.new("RGB", (1, size))
    px = img.load()
    for y in range(size):
        t = y / (size - 1)
        # qo'shimcha segment topish
        for i in range(len(BG_STOPS) - 1):
            p0, c0 = BG_STOPS[i]
            p1, c1 = BG_STOPS[i + 1]
            if p0 <= t <= p1:
                k = (t - p0) / (p1 - p0) if p1 > p0 else 0.0
                px[0, y] = (
                    lerp(c0[0], c1[0], k),
                    lerp(c0[1], c1[1], k),
                    lerp(c0[2], c1[2], k),
                )
                break
        else:
            px[0, y] = BG_STOPS[-1][1]

    bg = img.resize((size, size), Image.BILINEAR)

    # Yuqori chapdagi yumshoq yorug'lik chizig'i (rasmdagi kabi)
    glow = Image.new("L", (size, size), 0)
    g = ImageDraw.Draw(glow)
    g.polygon(
        [(0, 0), (int(size * 0.72), 0), (0, int(size * 0.72))],
        fill=70,
    )
    glow = glow.filter(ImageFilter.GaussianBlur(size * 0.18))
    white = Image.new("RGB", (size, size), (255, 255, 255))
    return Image.composite(white, bg, glow)


def star_points(cx: float, cy: float, r_out: float, r_in: float,
                rot_deg: float = -90.0) -> list[tuple[float, float]]:
    """5 burchakli yulduz nuqtalari."""
    pts = []
    for i in range(10):
        ang = math.radians(rot_deg + i * 36)
        r = r_out if i % 2 == 0 else r_in
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    return pts


def vertical_gradient_mask(size: int, top: tuple[int, int, int],
                           bottom: tuple[int, int, int],
                           bbox: tuple[int, int, int, int]) -> Image.Image:
    """Yulduz uchun vertikal gradient (faqat bbox ichida)."""
    x0, y0, x1, y1 = bbox
    w, h = x1 - x0, max(1, y1 - y0)
    strip = Image.new("RGB", (1, h))
    p = strip.load()
    for y in range(h):
        t = y / (h - 1)
        p[0, y] = (lerp(top[0], bottom[0], t),
                   lerp(top[1], bottom[1], t),
                   lerp(top[2], bottom[2], t))
    return strip.resize((w, h), Image.BILINEAR)


def build() -> Image.Image:
    size = SIZE
    base = gradient_background(size).convert("RGBA")
    L, k = make_mapper(size)

    def rect(x0, y0, x1, y1):
        a, b = L(x0, y0)
        c, d = L(x1, y1)
        return [a, b, c, d]

    def poly(pts):
        return [L(x, y) for x, y in pts]

    def rrect(draw, box, r, **kw):
        draw.rounded_rectangle(box, radius=r, **kw)

    # --- "N" harfi: soya ---------------------------------------------------
    shadow_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow_layer)
    rrect(sd, rect(170, 155, 230, 365), 30 * k, fill=(*SHADOW, 115))
    rrect(sd, rect(282, 210, 342, 360), 30 * k, fill=(*SHADOW, 115))
    sd.polygon(poly([(205, 175), (320, 335), (290, 350), (175, 190)]),
               fill=(*SHADOW, 95))
    base.alpha_composite(shadow_layer.filter(ImageFilter.GaussianBlur(size * 0.015)))

    # --- Diagonal bog'lovchi ------------------------------------------------
    conn = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(conn).polygon(
        poly([(205, 175), (320, 335), (290, 350), (175, 190)]),
        fill=(*N_SHADE, 230),
    )
    base.alpha_composite(conn)

    # --- Oq vertikal ustunlar ---------------------------------------------
    bars = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bars)
    rrect(bd, rect(170, 155, 230, 365), 30 * k, fill=(*WHITE, 255))
    rrect(bd, rect(282, 210, 342, 360), 30 * k, fill=(*WHITE, 255))
    base.alpha_composite(bars)

    # --- Oltin yulduz (o'ng ustun ustida, biroz ustga) ---------------------
    # Logo.svg dagi yulduz markaziga (312, 163) + ustun ustiga yaqinlashtiramiz
    scx, scy = L(310, 158)
    r_out, r_in = 50 * k, 21 * k
    pts = star_points(scx, scy, r_out, r_in, rot_deg=-90)

    star_shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(star_shadow).polygon(
        [(x, y + 7 * k) for x, y in pts], fill=(*SHADOW, 125)
    )
    base.alpha_composite(star_shadow.filter(ImageFilter.GaussianBlur(size * 0.011)))

    pad = int(size * 0.02)
    bbox = (int(min(p[0] for p in pts)) - pad, int(min(p[1] for p in pts)) - pad,
            int(max(p[0] for p in pts)) + pad, int(max(p[1] for p in pts)) + pad)
    bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]

    # yumshoq sariq shovqin
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(glow).polygon(pts, fill=(*STAR_BOTTOM, 95))
    base.alpha_composite(glow.filter(ImageFilter.GaussianBlur(size * 0.024)))

    grad = vertical_gradient_mask(size, STAR_TOP, STAR_BOTTOM, bbox)
    mask = Image.new("L", (bw, bh), 0)
    ImageDraw.Draw(mask).polygon([(x - bbox[0], y - bbox[1]) for x, y in pts], fill=255)
    grad.putalpha(mask)
    base.alpha_composite(grad, (bbox[0], bbox[1]))

    stroke = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(stroke).polygon(pts, outline=(*STAR_BOTTOM, 215),
                                   width=max(1, int(1.5 * k)))
    base.alpha_composite(stroke)

    return base.convert("RGB")


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    img = build()
    img.save(OUT, "PNG", optimize=True)
    print(f"✅ {OUT}  ({img.width}x{img.height}, {OUT.stat().st_size / 1024:.1f} KB)")