"""O'lik tugmalar / uzun callback / takroriy filtr auditi."""
import io
import re
from collections import defaultdict

s = io.open('/Users/odilbek/Downloads/NeonShop-main/bot.py', encoding='utf-8').read()

produced = set(re.findall(r'callback_data\s*=\s*f?"([^"{]+)"', s))

handlers = defaultdict(list)
for m in re.finditer(
    r'^@(router|common_router|admin_router)\.callback_query\(([^\n]*)\)\s*\n'
    r'async def (\w+)', s, flags=re.M,
):
    router, filt, name = m.group(1), m.group(2), m.group(3)
    line = s[:m.start()].count('\n') + 1
    eq = re.search(r'F\.data\s*==\s*"([^"]+)"', filt)
    if eq:
        handlers[eq.group(1)].append((router, name, line))
    for sw in re.findall(r'F\.data\.startswith\("([^"]+)"\)', filt):
        handlers[sw].append((router, name, line))
    if 'F.data.startswith(' in filt and not re.findall(
            r'F\.data\.startswith\("([^"]+)"\)', filt):
        handlers['*'].append((router, name, line))

EXACT = {k: v for k, v in handlers.items() if k != '*'}


def handled(data: str) -> bool:
    if data in EXACT or '*' in handlers:
        return True
    return any(data.startswith(p) for p in EXACT)


print("=== 1) O'LIK TUGMALAR (bosiladi, hech narsa bo'lmaydi) ===")
dead = [d for d in sorted(produced) if ':' in d and not handled(d)]
for d in dead:
    lines = [i + 1 for i, ln in enumerate(s.split('\n')) if f'"{d}"' in ln]
    print(f"  {d:<32} qatorlar: {lines[:4]}")
if not dead:
    print("  (yo'q)")

print()
print("=== 2) callback_data > 64 bayt (Telegram butun tugmani RAD qiladi) ===")
longs = [d for d in produced if len(d.encode()) > 64]
print("  " + (str(longs) if longs else "(yo'q)"))

print()
print("=== 3) TAKRORIY FILTR (aiogram birinchisini oladi, ikkinchisi O'LIK) ===")
dups = {p: hs for p, hs in EXACT.items() if len(hs) > 1}
for p, hs in dups.items():
    print(f"  {p}: {[f'{r}.{n}(L{l})' for r, n, l in hs]}")
if not dups:
    print("  (yo'q)")

print()
print("=== 4) TUGMA YO'Q, FAQAT URL (callback emas) ===")
urls = re.findall(r'callback_data\s*=\s*f?"([^"]*)"\s*,\s*\n\s*(?:style|url)=',
                   s)
print("  " + (str([u for u in urls if not u]) if urls else "(yo'q)"))

print()
print("=== 5) m:* menyu tugmalari -> actions dict da bor-mi? ===")
# Tugmalar ikki xil yo'l bilan yaratiladi:
#   a) `b("Matn", "action")`            -> `callback_data=f"m:{action}"`
#   b) `callback_data="m:nft"` (to'g'ridan-to'g'ri)
m_btns = {m.group(1) for m in re.finditer(r'\bb\("[^"]*",\s*"([a-z_]+)"', s)}
m_btns |= {m.group(1) for m in re.finditer(r'callback_data=f?"m:([a-z_]+)"', s)}
blk = s[s.index("actions = {"):]
blk = blk[:blk.index("\n    }")]
missing = sorted(a for a in m_btns if f'"{a}"' not in blk)
print("  tugmalar:", ", ".join(sorted(m_btns)))
print("  🔴 handler yo'q:", missing if missing else "(yo'q)")

print()
print("=== 6) MENU_STYLES da m:* bor, lekin tugma ishlatilmaydimi? ===")
sty = s[s.index("MENU_STYLES = {"):]
sty = sty[:sty.index("\n}")]
sty_keys = set(re.findall(r'"(m:[a-z_]+)"', sty))
unused = sorted(k for k in sty_keys if f'"{k}"' not in blk and f'"{k[2:]}"' not in blk)
print("  foydalanilmagan:", unused if unused else "(yo'q)")

ok = not dead and not longs and not dups and not missing
print()
print("NATIJA: ✅ BARCHASI TO'G'RI" if ok else "NATIJA: ❌ MUAMMO BOR")
raise SystemExit(0 if ok else 1)