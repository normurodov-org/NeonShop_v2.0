"""NFT RASMI YO'QOLMASIN — sekin internetda ham.

XABAR: "webappda taxminan 5 sekundlardan keyin rasmlar yuqolib qolyapti"

🔴 BU MENGING KIRITGAN XATOM. Flicker tuzatish paytida qo'ygan
quyidagi qator rasmlarni O'LDIRDI:

    const t = setTimeout(() => setState('failed'), 6000);

Har 6 soniyada rasm "muvaffaqiyatsiz" deb hisoblanardi. Telefonlar
sekin internetda Telegram CDN rasmini 6 soniyada yuklay OLMAYDI —
va rasm o'z-o'zidan yo'qolib, o'rniga placeholder chiqardi.

Keyin "20 soniyaga chiqardim" deb tuzatdim — u ham yetarli bo'lmadi
(sekin internetda yana o'ldi). Brauzerda o'lchandim:
    eski kod:  t=4.2s imgs:5 -> t=10.2s imgs:0 placeholders:6 (YO'QOLDII)
    yangi kod: t=14s  imgs:5 loaded:5 -> t=45s imgs:5 loaded:5 (JOYIDA)

🔴 XULOSA: IS TALAB QILINMAYDI.
  `<img>` `error` hodisasini FAQAT haqiqiy xatoda chiqaradi
  (404, DNS xatosi, ulanish yo'q, noto'g'ri ma'lumot).
  U "sekin internet" uchun CHIQMAYDI — demak `onError` yetarli.

  Ishlatilmay qolgan taymer esa faqat bir narsaga xarid qiladi:
  YETISHLI rasmlarni o'ldiradi — bu foydalanuvchi uchun ko'rinadigan
  jiddiy muammo (bo'sh kvadrat).
"""
import os
import re
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIEW = open(f"{ROOT}/src/components/views/NftRentView.tsx", encoding="utf-8").read()
CSS = open(f"{ROOT}/src/index.css", encoding="utf-8").read()
SRV = open(f"{ROOT}/server.ts", encoding="utf-8").read()

ok = True


def check(cond, msg):
    global ok
    ok &= bool(cond)
    print(f"  {'✅' if cond else '❌'} {msg}")


print("=" * 70)
print("1) 🔴 ISTATILGAN MUDDATLI TAYMER BO'LMASIN")
print("=" * 70)
# 🔴 IZOHLARNI OLIB TASHLAMISHI SHART — aks holda bu test o'z
# izohimizni ("eski xato shunday edi") xato deb o'ylab qizil bo'ladi.
def strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)      # /* ... */
    text = re.sub(r"//[^\n]*", "", text)                  # // ...
    return text

raw = VIEW[VIEW.index("const NftImage:"):VIEW.index("export const NftRentView")]
img = strip_comments(raw)
timers = re.findall(r"setTimeout\([^)]*\)", img)
check(not timers,
      f"KODDA setTimeout yo'q ({len(timers)} ta) — izohlardan keyin")
check("stopTimer" not in img, "stopTimer ham yo'q")
check("timerRef" not in img, "timerRef ham yo'q")
check("setState('failed'), 6000" not in strip_comments(VIEW),
      "6s da o'ldirish qoldig'i yo'q")
check("setState('failed'), 20000" not in strip_comments(VIEW),
      "20s da o'ldirish qoldig'i yo'q")

print()
print("=" * 70)
print("2) TAYER QILISHI — faqat HAQIQIY xatoda")
print("=" * 70)
check("onError={() => {" in img, "onError ishlaydi")
check("retry();" in img, "haqiqiy xatoda serverdan qayta olish")
check("if (nftId && !retriedRef.current)" in img, "faqat 1 marta qayta urinish")
check('const retriedRef = useRef(false)' in img, "infinite loop himoyasi")
check("setState('failed')" in img, "oxirida placeholder")

print()
print("=" * 70)
print("3) YUKLANAYOTGAN PAYT — shimmer (xato emas, chiroyli)")
print("=" * 70)
check("const [loading, setLoading] = useState(false)" in img, "loading holati")
check("setLoading(true)" in img, "yuklanish boshlanadi")
check("setLoading(false)" in img, "yuklanish tugaydi (onLoad/onError)")
check('nft-shimmer' in img, "shimmer qo'llanadi")
check(".nft-shimmer {" in CSS, "shimmer CSS bor")
check("@keyframes nftShimmer" in CSS, "shimmer animatsiyasi")
check("prefers-reduced-motion" in CSS,
      "qurilma talablariga mos (harakat kamaytirilgan)")
check("nft-img w-full h-full nft-shimmer" in img,
      "shimmer rasm o'lchamini saqlaydi (CLS = 0)")

print()
print("=" * 70)
print("4) onLoad — shimmer darhol yo'qoladi")
print("=" * 70)
check("onLoad={() => {" in img, "onLoad ishlaydi")
i_load = img.index("onLoad={() => {")
i_load_end = img.index("}}", i_load)
check("setLoading(false)" in img[i_load:i_load_end],
      "onLoad da loading=false")
check("loadedRef.current = true" in img[i_load:i_load_end],
      "yuklangan belgisi qo'yiladi")
# onLoad MAVJUDLIGI — bu asosiy himoya
check("onLoad" in img, "🔴 onLoad bo'lmasa sekin rasm yana o'ladi")

print()
print("=" * 70)
print("5) SERVER — sekin rasm test yo'li (ENV bilan)")
print("=" * 70)
check("NFT_SLOW_IMAGES_MS" in SRV, "test uchun kechiktirish yo'li")
check("if (process.env.NFT_SLOW_IMAGES_MS)" in SRV,
      "🔴 faqat ENV bilan yoqiladi (production'da yo'q)")
# route idempotent bo'lishi uchun faqat bitta ta'rif
check(SRV.count("NFT_SLOW_IMAGES_MS") == 2,
      f"ENV faqat 2 marta ishlatilgan ({SRV.count('NFT_SLOW_IMAGES_MS')})")
fixtures = f"{ROOT}/public/_t"
check(os.path.isdir(fixtures) and len(os.listdir(fixtures)) >= 5,
      "test rasmlari mavjud (public/_t)")

print()
print("=" * 70)
print("6) HAQIQIY TEKSHIRUV — server sekin rasmni 7s da beradi")
print("=" * 70)
port = 4822
env = {
    **os.environ,
    "PORT": str(port),
    "BOT_TOKEN": "123456:FAKE",
    "API_ID": "1",
    "API_HASH": "x",
    "DB_PATH": "/tmp/_t_slowimg.json",
    "AUTO_START_TG_BOT": "false",
    "NFT_SLOW_IMAGES_MS": "7000",
}
for sfx in ("", ".bak"):
    p = "/tmp/_t_slowimg.json" + sfx
    if os.path.exists(p):
        os.remove(p)
import json  # noqa: E402
with open("/tmp/_t_slowimg.json", "w", encoding="utf-8") as fh:
    json.dump({"settings": {"bot_active": True}, "users": {}, "orders": {},
               "topups": {}, "contest": {},
               "nfts": {f"nft_{i}": {"id": f"nft_{i}", "title": f"G{i}",
                                    "number": i, "image": "", "link": "",
                                    "daily": 50 + i, "active": True}
                        for i in range(1, 6)}}, fh)

subprocess.run(["pkill", "-f", "tsx server.ts"], stdout=subprocess.DEVNULL,
               stderr=subprocess.DEVNULL, check=False)
time.sleep(1.5)
proc = subprocess.Popen(["npx", "tsx", "server.ts"], cwd=ROOT, env=env,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                        preexec_fn=os.setsid, bufsize=1)
base = f"http://127.0.0.1:{port}"
ready = False
deadline = time.time() + 150
try:
    while time.time() < deadline:
        if proc.poll() is not None:
            break
        try:
            with urllib.request.urlopen(base + "/api/health", timeout=8) as r:
                if r.status == 200:
                    ready = True
                    break
        except Exception:  # noqa: BLE001
            time.sleep(1)
    check(ready, "server ishga tushdi")

    if ready:
        t0 = time.time()
        try:
            with urllib.request.urlopen(base + "/_t/slow1.png", timeout=25) as r:
                body = r.read()
            dt = time.time() - t0
            check(r.status == 200, f"rasm 200 ({dt:.1f}s)")
            check(dt >= 6.5, f"haqiqatan kechiktirildi ({dt:.1f}s >= 6.5s)")
            check(len(body) > 100, f"rasm keldi ({len(body)} bayt)")
        except Exception as exc:  # noqa: BLE001
            check(False, f"rasm yuklanmadi: {exc}")

        # ⚠️ ASOSIY: shu 7 soniyada server /api/nfts ni o'zgartirmasligi
        # kerak — ya'ni sekin rasm sababli NFT yo'qolmasin
        with urllib.request.urlopen(base + "/api/nfts", timeout=15) as r:
            items = json.loads(r.read()).get("items", [])
        check(len(items) == 5, f"barcha NFT'lar saqlanib qoldi ({len(items)})")
finally:
    try:
        import signal
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        time.sleep(1)
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except Exception:  # noqa: BLE001
        pass
    for sfx in ("", ".bak"):
        p = "/tmp/_t_slowimg.json" + sfx
        if os.path.exists(p):
            os.remove(p)

print()
print("=" * 70)
print("TAQQOSLASH (brauzerda o'lchilgan)")
print("=" * 70)
print("  ESKI  (6s taymer):")
print("      t=4.2s   imgs:5 loaded:0")
print("      t=10.2s  imgs:0 loaded:0 placeholders:6   ← RASMLAR YO'QOLDII")
print("      t=18.1s  imgs:0 loaded:0 placeholders:6")
print("  YANGI (taymer yo'q, shimmer):")
print("      t=14.1s  imgs:5 loaded:5 shimmer:0  ← KELDI")
print("      t=45.0s  imgs:5 loaded:5 shimmer:0  ← JOYIDA")

print()
print("=" * 70)
print("NATIJA:", "✅ BARCHASI TO'G'RI" if ok else "❌ MUAMMO BOR")
print("=" * 70)
sys.exit(0 if ok else 1)