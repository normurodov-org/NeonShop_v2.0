"""Test uchun NFT rasmlari (public/_t/g1..g5.png).

`tests/test_nft_image_persist.py` sekin internetni simulyatsiya
qilish uchun shu rasmlardan foydalanadi (server 7 soniya kechiktirib
beradi). Rasm tarkibi muhim emas — faqat haqiqiy PNG kerak.

Qayta yaratish:  python3 tools/make_test_fixtures.py
"""
import os
import struct
import zlib

COLORS = [(120, 80, 200), (200, 90, 140), (90, 150, 210),
          (220, 150, 70), (110, 190, 130)]


def write_png(path: str, rgb, w=160, h=160) -> None:
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return (struct.pack(">I", len(data)) + body
                + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF))

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw))
           + chunk(b"IEND", b""))
    with open(path, "wb") as fh:
        fh.write(png)


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "public", "_t")
    os.makedirs(out, exist_ok=True)
    for i, c in enumerate(COLORS, 1):
        write_png(os.path.join(out, f"g{i}.png"), c)
    print(f"✅ {len(COLORS)} ta test rasm yaratildi: {out}")
