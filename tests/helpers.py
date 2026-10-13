"""Testlar uchun yordamchi funksiyalar.

`strip_code()` — koddan IZOH va DOCSTRING olib tashlaydi.

Nima uchun kerak: ko'p testda kod ichida o'z xatamizni izohlab
yozamiz ("avval shunday edi — tuzatildi"). Agar test xom kodni
tekshirsa, o'z izohimizni "xato" deb o'ylab qizil bo'ladi.
"""

import re

_TRIPLE_D = '"' * 3
_TRIPLE_S = "'" * 3


def strip_code(text: str) -> str:
    """/* ... */, // ..., \"\"\"docstring\"\"\" olib tashlaydi."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    # `(?<!:)` — `https://` ichidagi `//` IZOH EMAS. Aks holda
    # "https://nft.fragment.com/..." kabi satrlar butunlay
    # kesilib ketardi va test yolg'on xato berardi.
    text = re.sub(r"(?<![:'\"])//[^\n]*", "", text)
    # Docstring'lar (uch qatorli)
    text = re.sub(_TRIPLE_D + ".." + _TRIPLE_D, '""', text, flags=re.S)
    text = re.sub(_TRIPLE_S + ".." + _TRIPLE_S, "''", text, flags=re.S)
    return text


def section(text: str, start_marker: str, end_marker: str, clean: bool = True) -> str:
    """Ikki marker orasidagi kodni qaytaradi (izohsiz)."""
    i = text.index(start_marker)
    j = text.index(end_marker, i + 1)
    seg = text[i:j]
    return strip_code(seg) if clean else seg