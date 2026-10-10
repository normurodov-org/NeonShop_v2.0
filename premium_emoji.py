# -*- coding: utf-8 -*-
"""
PREMIUM EMOJI MODULI
===================
Telegram'da maxsus (premium) emojilarni yuborish uchun `custom_emoji` entitysi
kerak. Lekin `parse_mode` va `entities` birga ishlatib bo'lmaydi — shuning uchun
bu modul:

  1. HTML matnni (<b>, <i>, <code>, <a>, ...) yalang'och matn + entities ga aylantiradi
  2. Matndagi har bir emojini `custom_emoji` entitysi bilan almashtiradi

Xavfsizlik: konvertatsiya xatosida `render_text` None qaytaradi va xabar
oddiy `parse_mode="HTML"` bilan yuboriladi — bot hech qachon buzilmaydi.
"""

import html
import re
from typing import Any, Optional

from aiogram.types import MessageEntity
from aiogram.enums import ParseMode

# =============================================================================
# PREMIUM EMOJI XARITASI (Telegram custom emoji ID'lari)
# =============================================================================
PREMIUM_EMOJI: dict[str, str] = {
    # asosiy menyu
    "⭐": "5229227046290343318", "💰": "5409029353851872920", "💎": "5841235769728962577",
    "🎁": "5330312778093704176", "💳": "5215420556089776398", "👥": "5453957997418004470",
    "🌐": "5463386283856373524", "👤": "5974048815789903111", "📜": "5388922215347534633",
    "🆘": "5841605514873540460",
    # xabarlar va tugmalar
    "👋": "5312345830382910731", "🆔": "5841191265277841038", "🔗": "5271604874419647061",
    "🚀": "5443064517246360671", "🔙": "5253997076169115797", "⬅️": "5472321989085505243",
    "✅": "5462919317832082236", "❌": "5210952531676504517", "⚠️": "5462935376714802451",
    "⏳": "5404727802370999261", "⌛": "5215394081911351762", "⏱": "5382194935057372936",
    "🧾": "5444856076954520455", "📦": "5463172695132745432", "💵": "5460978422111021593",
    "🙋": "5974416568069655298", "🔐": "5197288647275071607", "ℹ️": "5974193375799152241",
    "❗": "4927486932113425461", "❓": "5436113877181941026", "📢": "5440804200512525401",
    "🎉": "5461151367559141950", "➕": "5397916757333654639", "➖": "5382261056078881010",
    "↩️": "5854967531793550989", "🚫": "5240241223632954241", "⛔": "5436303886535111778",
    "✍️": "5238156910363950406", "🤖": "5355051922862653659", "📅": "5413879192267805083",
    "📌": "5462912132351797094",
    # giftlar
    "🧸": "5440563403171077596", "💝": "5440817124069122820", "🌹": "5440465310413003014",
    "🎂": "5442726060938533686", "💐": "5443151748032141644", "🏆": "5443143823817479892",
    "💍": "5442988419015811615", "🍾": "5440548327835869020",
    # admin
    "🛠": "5980828026529649035", "📊": "5231200819986047254", "📣": "5462950031143216831",
    "🔎": "5264892613630111886", "🍪": "5364028559130119804", "🗓": "5274055917766202507",
    "🔄": "5453969572354878595", "🟢": "5215685881989442149", "🔴": "5409143075995945165",
    "⏸": "5359543311897998264", "▶️": "5440353022788018906", "🚪": "5974506040828366250",
    "🛒": "5226656353744862682", "👉": "5415758949129404605",
    # qo'shimcha (xabarlarda ishlatiladigan)
    "💸": "5409029353851872920", "👥": "5453957997418004470", "🎯": "5463172695132745432",
    "🏦": "5274055917766202507", "👛": "5364028559130119804", "🔬": "5264892613630111886",
    "🩺": "5404727802370999261", "🏷": "5462950031143216831", "🎁": "5330312778093704176",
}

# Teglar -> (entity turi, atribut kaliti)
_TAGS: dict[str, tuple[str, Optional[str]]] = {
    "b": ("bold", None), "strong": ("bold", None),
    "i": ("italic", None), "em": ("italic", None),
    "u": ("underline", None), "ins": ("underline", None),
    "s": ("strikethrough", None), "strike": ("strikethrough", None), "del": ("strikethrough", None),
    "code": ("code", None), "pre": ("pre", None),
    "a": ("text_link", "href"),
    "tg-spoiler": ("spoiler", None), "tg-spoiler=": ("spoiler", None),
    "blockquote": ("blockquote", None),
}

_TAG_RE = re.compile(
    r"<(/?)([a-zA-Z][a-zA-Z0-9-]*)([^>]*)>",
)


def _u16_len(text: str) -> int:
    """UTF-16 kod birliklaridagi uzunlik (Telegram offset/length shuni ishlatadi)."""
    return len(text.encode("utf-16-le")) // 2


def _emoji_pattern() -> re.Pattern:
    """Premium emojilarni topish uchun regex (uzunroq emojilarni oldindan)."""
    chars = sorted(PREMIUM_EMOJI.keys(), key=len, reverse=True)
    escaped = [re.escape(c) for c in chars]
    return re.compile("(" + "|".join(escaped) + ")")


_EMOJI_RE = _emoji_pattern()


def html_to_text_entities(source: str) -> tuple[str, list[MessageEntity]]:
    """HTML matnni (yalang'och matn, entities) ga aylantiradi."""
    entities: list[MessageEntity] = []
    out: list[str] = []
    offset = 0                       # UTF-16 birliklarida
    open_stack: list[tuple[str, int, Optional[str]]] = []

    pos = 0
    for match in _TAG_RE.finditer(source):
        chunk = source[pos:match.start()]
        if chunk:
            decoded = html.unescape(chunk)
            out.append(decoded)
            offset += _u16_len(decoded)
        pos = match.end()

        closing = match.group(1) == "/"
        tag = match.group(2).lower()
        attrs_raw = match.group(3) or ""

        info = _TAGS.get(tag)
        if info is None:
            continue
        kind, attr = info

        if closing:
            # Eng so'nggi tegni yopamiz
            for idx in range(len(open_stack) - 1, -1, -1):
                if open_stack[idx][0] == kind:
                    name, start, extra = open_stack.pop(idx)
                    entities.append(_build_entity(name, start, offset - start, extra))
                    break
        else:
            extra: Optional[str] = None
            if attr == "href":
                m = re.search(r'href\s*=\s*["\']([^"\']+)["\']', attrs_raw)
                extra = m.group(1) if m else None
                if not extra:
                    continue
            open_stack.append((kind, offset, extra))

    tail = source[pos:]
    if tail:
        decoded = html.unescape(tail)
        out.append(decoded)
        offset += _u16_len(decoded)

    for name, start, extra in reversed(open_stack):
        entities.append(_build_entity(name, start, offset - start, extra))

    return "".join(out), entities


def _build_entity(kind: str, start: int, length: int, extra: Optional[str]) -> MessageEntity:
    if length <= 0:
        length = 1
    if kind == "text_link":
        return MessageEntity(type=kind, offset=start, length=length, url=extra or "https://t.me")
    return MessageEntity(type=kind, offset=start, length=length)


def add_premium_emoji(text: str, entities: list[MessageEntity]) -> tuple[str, list[MessageEntity]]:
    """Matndagi emojilarga custom_emoji entitylarini qo'shadi.

    Matnning o'zi O'ZGARMAS (emoji belgilari joyida qoladi), shuning uchun
    mavjud entity offset'lari kuzatilmaydi — biz faqat yangilarini qo'shamiz.
    """
    if not any(ch in text for ch in PREMIUM_EMOJI):
        return text, entities

    found = list(_EMOJI_RE.finditer(text))
    if not found:
        return text, entities

    new_entities = list(entities)
    for match in found:
        piece = match.group(0)
        emoji_id = PREMIUM_EMOJI.get(piece)
        if not emoji_id:
            continue
        new_entities.append(
            MessageEntity(
                type="custom_emoji",
                offset=_u16_len(text[:match.start()]),
                length=_u16_len(piece),
                custom_emoji_id=emoji_id,
            )
        )

    return text, new_entities


def render_text(source: str) -> Optional[tuple[str, list[MessageEntity]]]:
    """(matn, entities) qaytaradi. Xato bo'lsa None — oddiy HTML bilan yuboriladi."""
    if not source:
        return source, []
    try:
        text, entities = html_to_text_entities(source)
        text, entities = add_premium_emoji(text, entities)
        return text, entities
    except Exception:  # noqa: BLE001
        return None
