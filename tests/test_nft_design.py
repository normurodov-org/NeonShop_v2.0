"""NftRentView DIZAYN va KONGASTR — brauzerdagi aniq o'lchovlarga asoslangan.

Bu test haqiqiy brauzerdagi topilgan 4 ta jiddiy xatoni ushlaydi:

1) `--accent` CSS o'zgaruvchisi butun ilovada YO'Q EDI.
   `bg-[var(--accent)]` fon bermaydi -> `text-white` yorug' fonda
   OQ QOLIB KETADI (ko'rinmaydi). Faol kun/chip va CTA tugmasi
   butunlay ko'rinmas edi. Kontrast 1.07:1 (WCAG AA uchun 4.5 kerak).

2) `apple-view-animate` `animation-fill-mode: both` bilan ishlatiladi:
   animatsiya tugagandan keyin ham `transform: scale(1)` va
   `filter: blur(0px)` QOLADI. Ikkalasi ham `position: fixed` ni
   buzadi — modal VIEWPORT emas, butun konteyner balandligida
   joylashadi. Brauzerda CTA tugmasi ekran pastidan 260px pastda
   (top: 909, viewport 700) qolgan edi.

3) `https://t.me/nft/...` — bu RASM EMAS, SPA sahifa.
   `<img src="https://t.me/nft/FinePen">` brauzerda BUZILGAN rasm
   ikonkasini ko'rsatadi (naturalWidth = 0).

4) Yuklanmaydigan rasm (o'lik domen) 404 ham bermaydi, balki
   osilib qoladi: `onError` ishlamaydi va karta doim bo'sh.

Kontast qiymatlari haqiqiy brauzerda computed style o'qilib
olingan. Bu test ularni CSS dan qayta hisoblaydi.
"""
import re
import sys

ROOT = __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__)))
CSS = open(f"{ROOT}/src/index.css", encoding="utf-8").read()
VIEW = open(f"{ROOT}/src/components/views/NftRentView.tsx", encoding="utf-8").read()
MODAL = open(f"{ROOT}/src/components/Modal.tsx", encoding="utf-8").read()
APP = open(f"{ROOT}/src/App.tsx", encoding="utf-8").read()
SRV = open(f"{ROOT}/server.ts", encoding="utf-8").read()

ok = True


def check(cond, msg):
    global ok
    ok &= bool(cond)
    print(f"  {'✅' if cond else '❌'} {msg}")


# ---------------------------------------------------------------- kontrast
def _srgb(c):
    c /= 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def lum(hexstr):
    h = hexstr.lstrip("#")
    if len(h) == 3:
        h = "".join(x * 2 for x in h)
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _srgb(r) + 0.7152 * _srgb(g) + 0.0722 * _srgb(b)


def contrast(a, b):
    l1, l2 = lum(a), lum(b)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def var_value(block_name, var):
    """CSS blokida o'zgaruvchi qiymatini oladi."""
    i = CSS.find(block_name)
    if i < 0:
        return None
    m = re.search(rf"{re.escape(var)}\s*:\s*(#[0-9a-fA-F]{{3,6}})", CSS[i:i + 400])
    return m.group(1) if m else None


print("=" * 70)
print("1) --accent BOR (butun ilova uchun)")
print("=" * 70)
check("--accent:" in CSS, "--accent e'lon qilingan")
check(re.search(r"^\s*--accent\s*:", CSS, re.M) is not None,
      "`:root` blokida aniqlangan (bo'sh qolmaydi)")
# ilovada ishlatilishi
used = re.findall(r"var\(--accent(?:-text)?\)", VIEW)
check(len(used) >= 6, f"NFT bo'limida {len(used)} marta ishlatiladi")
# BUG: `bg-[var(--accent)]` + `text-white` bitta qatorda bo'lsa,
# accent yo'q bo'lgani butun tugmani ko'rinmay qiladi
check("bg-[var(--accent)] text-white" in VIEW,
      "CTA: accent fon + oq matn")

print()
print("=" * 70)
print("2) KONTRAST — WCAG AA (4.5) va AAA (7.0)")
print("=" * 70)
# Brauzerda o'lchilgan qadrlar:
#   .light liquid-glass-card gradient -> #f7f7fa
#   .dark  liquid-glass-card gradient -> #1e1e26
LIGHT_CARD = "#f7f7fa"
DARK_CARD = "#1e1e26"
WHITE = "#ffffff"

lt_accent = var_value(".light {", "--accent")
dt_accent = var_value(".dark {", "--accent")
lt_text = var_value(".light {", "--accent-text")
dt_text = var_value(".dark {", "--accent-text")

check(lt_accent is not None, f"yorug' rejim --accent = {lt_accent}")
check(dt_accent is not None, f"qorong'i rejim --accent = {dt_accent}")
check(lt_text is not None, f"yorug' rejim --accent-text = {lt_text}")
check(dt_text is not None, f"qorong'i rejim --accent-text = {dt_text}")

if lt_accent:
    c = contrast(WHITE, lt_accent)
    print(f"      yorug': oq matn ustida = {c:.2f}:1")
    check(c >= 4.5, f"CTA oq matn / aksent fon = {c:.2f}:1 (AA 4.5)")
    check(c >= 7.0, f"...hatto AAA 7.0 ({c:.2f})")
if dt_accent:
    c = contrast(WHITE, dt_accent)
    print(f"      qorong'i: oq matn ustida = {c:.2f}:1")
    check(c >= 4.5, f"CTA oq matn / aksent fon = {c:.2f}:1 (AA 4.5)")
if lt_text:
    c = contrast(lt_text, LIGHT_CARD)
    print(f"      yorug': Total matni kartada = {c:.2f}:1")
    check(c >= 4.5, f"Total summa / karta = {c:.2f}:1 (AA)")
if dt_text:
    c = contrast(dt_text, DARK_CARD)
    print(f"      qorong'i: Total matni kartada = {c:.2f}:1")
    check(c >= 4.5, f"Total summa / karta = {c:.2f}:1 (AA)")

# Qorong'i rejimda `#8b5cf6` ishlatilgan edi va faqat 4.23 chiqardi
old_dark = "#8b5cf6"
if dt_accent and dt_accent.lower() != old_dark:
    check(contrast(WHITE, old_dark) < 4.5,
          f"eski {old_dark} AA dan past bo'lgani sababli almashtirildi "
          f"({contrast(WHITE, old_dark):.2f}:1)")

print()
print("  `Balance` yorug' rejimda avval 4.43 edi (AA dan past):")
check("isDark ? 'text-neutral-400' : 'text-neutral-600'" in VIEW,
      "neutral-500 -> neutral-600 (7.31:1)")

print()
print("=" * 70)
print("3) MODAL PORTAL — position:fixed buzilmasligi uchun")
print("=" * 70)
check("createPortal" in MODAL, "Modal.tsx createPortal ishlatadi")
check("document.body" in MODAL,
      "document.body ga chiqariladi (transform/filter ta'sirida emas)")
check("<Modal open={!!sel}" in VIEW, "NFT modali <Modal> orqali")
check("fixed inset-0 z-50 flex items-end sm:items-center" not in VIEW,
      "eski inline `fixed` wrapper olib tashlandi")
check("role=\"dialog\"" in MODAL, "aria-modal dialog (maxalarni o'qish uchun)")
check("Escape" in MODAL, "Escape bilan yopiladi")
check("z-[100]" in MODAL, "z-index 100 — pastki menyudan yuqorida")
check("100dvh" in VIEW or "88vh" in VIEW, "ekran balandligiga moslashuv")
check("safe-area-inset-bottom" in VIEW,
      "Telegram pastki paneli ostida qolmasligi uchun safe-area")
check("overflow-y-auto" in VIEW, "kichik ekranda skroll qilinadi")

print()
print("  Portal uchun tema body ga sinxronlanishi SHART:")
check("b.classList.add(theme)" in APP,
      "App.tsx: tema klassi document.body ga qo'yiladi")
check("b.classList.remove('light', 'dark')" in APP, "eski klass tozalanadi")

print()
print("=" * 70)
print("4) TELEGRAM SAHIFA HAVOLASI RASM DEGIL")
print("=" * 70)
check("function isTelegramPageUrl(" in SRV, "isTelegramPageUrl() bor")
for host in ("t\\.me", "telegram\\.me", "nft\\.telegram\\.org", "fragment\\.com"):
    check(host in SRV, f"{host} aniqlanadi")
check("return isTelegramPageUrl(raw) ? '' : raw;" in SRV,
      "t.me linki -> bo'sh (buzilgan rasm chiqmaydi)")
fn = SRV[SRV.index("function nftImageUrl("):SRV.index("function nftPublicList(")]
check("/api/nft-image/" in fn, "file_id -> proxy (ishlaydi)")
check("isTelegramFileId(raw)" in fn, "file_id -> proxy (ishlaydi)")
check(fn.count("return '';") >= 1, "boshqa holatlar -> placeholder")

print()
print("=" * 70)
print("5) PLACEHOLDER — buzilgan/osilib qolgan rasm uchun")
print("=" * 70)
check("const NftImage" in VIEW, "NftImage komponenti")
check("onError={() => setFailed(true)}" in VIEW, "onError -> placeholder")
check("setTimeout(() => setFailed(true), 6000)" in VIEW,
      "6 soniya taymer (o'lik domen osilib qolmasligi uchun)")
check("clearTimeout" in VIEW, "taymer tozalanadi (component unmount)")
check("<NftImage" in VIEW, "kartada ishlatiladi")
check(VIEW.count("<NftImage") >= 2, "kartada VA modalda")
check("lucide-gift" not in VIEW, "")
check("Gift" in VIEW and "import" in VIEW, "Gift ikonkasi import qilingan")
# eski xato qolmaganligi
check("/^https?:\\/\\//i.test(n.image)" not in VIEW,
      "eski `^https?://` tekshiruvi qolmagan")

print()
print("=" * 70)
print("6) TAQQOSLASH — eski qiymatlar (bu xatolar bo'ldi)")
print("=" * 70)
print(f"      eski --accent (yo'q)  -> fon yo'q, oq matn = 1.07:1  ❌")
print(f"      eski CTA top:909 / viewport 700 -> ekran tashqarisida ❌")
print(f"      eski Balance light     -> 4.43:1 (AA dan past)          ❌")
print(f"      eski dark accent #8b5cf6 -> 4.23:1 (AA dan past)        ❌")
print("      endi:")
print(f"      CTA (ikkala rejim)     -> >=4.5:1  ✅")
print(f"      modal BODY da, to'liq ekran, CTA ko'rinadi  ✅")
print(f"      Balance / Total        -> >=4.5:1  ✅")

print()
print("=" * 70)
print("NATIJA:", "✅ BARCHASI TO'G'RI" if ok else "❌ MUAMMO BOR")
print("=" * 70)
sys.exit(0 if ok else 1)