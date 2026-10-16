/**
 * 🟩 GRID BACKDROP — chizish va harakat MANTIG'I (sof, DOM'siz).
 *
 * 🔴 NIMA UCHUN AJRATILGAN?
 *   `GridBackdrop.tsx` ichida hammasi bo'lsa, chizish/harakat mantiqini
 *   sinab bo'lmaydi — `requestAnimationFrame` headless muhitda ishlamaydi
 *   (o'lchangan: `rAFIshlayapti: false`) va `canvas` yo'q. Bu modul esa
 *   DOM va rAF talab qilmaydi, shuning uchun Node'da to'g'ridan-to'g'ri
 *   sinanadi (tests/test_grid_backdrop.py).
 *
 * 📌 MIJOZ SO'RAYOTGAN QARORLAR (2026-10-16):
 *   1. 🎨 Rang — OQ-QORA (bot dizayida aksent rangi yo'q)
 *   2. 🚫 Kursor ostidagi YORUG'LIK — butunlay olib tashlandi
 *   3. 🚫 Kursor qisilganda chiqadigan DOIRA (tolqin) — olib tashlandi
 *   4. 🚫 Nuqtalar orasidagi CHIZIQLAR — olib tashlandi (faqat nuqta)
 *      ⚠️ Gorizontal va vertikal chiziq kodi saqlanib qoldi
 *         (`showLines = true` bersangiz qayta paydo bo'ladi) — kelajakda
 *         kerak bo'lsa, bitta o'zgaruvchaning qiymatini o'zgartirish kifoya.
 */

export interface GridNode {
  /** Joriy (siljigan) pozitsiya — chiziladigan. */
  x: number;
  y: number;
  /** Dastlabki (tinch) pozitsiya — qaytish nishoni. */
  ox: number;
  oy: number;
}

/** Ranglar — oq-qora (bot brendidan). */
export interface GridPalette {
  bg: string;
  line: string;
  dot: string;
  dotHot: string;
}

export const PALETTE_DARK: GridPalette = {
  bg: '#000000',
  line: 'rgba(255, 255, 255, 0.10)', // 🔴 saqlangan, lekin HOZIR chizilmaydi
  dot: 'rgba(255, 255, 255, 0.34)',
  dotHot: 'rgba(255, 255, 255, 1)',
};

export const PALETTE_LIGHT: GridPalette = {
  bg: '#ffffff',
  line: 'rgba(0, 0, 0, 0.10)',
  dot: 'rgba(0, 0, 0, 0.30)',
  dotHot: 'rgba(0, 0, 0, 0.85)',
};

/** Nuqtalar to'rini quradi (chiziq kesishgan joylar). */
export function buildGrid(W: number, H: number, cell: number): GridNode[] {
  const out: GridNode[] = [];
  const cols = Math.ceil(W / cell) + 1;
  const rows = Math.ceil(H / cell) + 1;
  // 🔴 Tor o'rtada joylashadi (chapdan kosmos qolmasin)
  const offX = (W - (cols - 1) * cell) / 2;
  const offY = (H - (rows - 1) * cell) / 2;
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const x = offX + c * cell;
      const y = offY + r * cell;
      out.push({ x, y, ox: x, oy: y });
    }
  }
  return out;
}

/**
 * 🔴 KADR: nuqtalarni kursor tomon SURISH va keyin tinch holatga QAYTARISH.
 *
 * 🔬 QO'LLANMA (rasmdagi effekt):
 *   • Kursordan yaqin nuqta radial yo'nalishda SURILADI
 *   • Surish kuchaytiruvchisi `(1 - d/R)²` — chetda deyarli
 *     harakatsiz, markizda eng kuchli
 *   • 🔴 SURISH va QAYTISH turlicha: qaytish `lerp` bilan YUMSHOQ,
 *     aks holda nuqta «spring» bo'lib sakrab ketadi (rasmda yo'q)
 *
 * @param push surish kuchaytiruvchisi (`0` = tugma ustidagi tinch holat)
 * @param pull qaytish tezligi (0..1)
 */
export function stepNodes(
  nodes: GridNode[],
  cx: number,
  cy: number,
  radius: number,
  push = 0.42,
  pull = 0.16,
): void {
  const R2 = radius * radius;
  for (const n of nodes) {
    const dx = n.x - cx;
    const dy = n.y - cy;
    const d2 = dx * dx + dy * dy;
    if (push > 0 && d2 < R2 && d2 > 1e-6) {
      const d = Math.sqrt(d2);
      const f = (1 - d / radius) ** 2 * push;
      n.x = n.ox + (dx / d) * f;
      n.y = n.oy + (dy / d) * f;
    } else {
      n.x += (n.ox - n.x) * pull;
      n.y += (n.oy - n.y) * pull;
    }
  }
}

/**
 * 🔴 Nuqtaning «qizarganligi» 0..1 — kursor yaqinligi.
 * Kvadrat bilan ko'tariladi: chetlar yumshoq, markiz to'liq.
 */
export function heatOf(
  x: number, y: number, cx: number, cy: number, radius: number,
): number {
  const dx = x - cx;
  const dy = y - cy;
  const d2 = dx * dx + dy * dy;
  if (d2 >= radius * radius) return 0;
  return (1 - Math.sqrt(d2) / radius) ** 2;
}

/** Canvas kontekstining qisqa turi (test uchun). */
export interface Ctx2D {
  fillStyle: string | CanvasGradient;
  strokeStyle: string | CanvasGradient;
  lineWidth: number;
  globalAlpha: number;
  fillRect(x: number, y: number, w: number, h: number): void;
  beginPath(): void;
  moveTo(x: number, y: number): void;
  lineTo(x: number, y: number): void;
  stroke(): void;
  fill(): void;
  arc(x: number, y: number, r: number, s: number, e: number): void;
}

/**
 * 🖼 Butun kadrni chizadi (fon + nuqtalar [+ ixtiyoriy chiziqlar]).
 *
 * @param showLines `false` (sukut bo'yicha) — faqat nuqtalar.
 *   `true` bo'lsa gorizontal VA vertikal chiziqlar ham chiziladi.
 */
export function drawFrame(
  ctx: Ctx2D,
  W: number,
  H: number,
  P: GridPalette,
  nodes: GridNode[],
  cx: number,
  cy: number,
  radius: number,
  dotBase: number,
  dotMax: number,
  showLines = false,
): void {
  ctx.fillStyle = P.bg;
  ctx.fillRect(0, 0, W, H);

  // 🔴🔴🔴 BU YERDA AVVAL IKKI NARSA BOR EDI, MIJOZ OLIB TASHLASHNI SO'RADI:
  //   1) Kursor ostidagi YUMASHOQ YORUG'LIK (radial gradient)
  //   2) Kursor tezligiga bog'liq TOLQIN DOIRALARI
  //   Endi fon faqat nuqtalardan iborat — toza va tinch.

  // 📐 Ixtiyoriy chiziqlar (hozir o'chirilgan)
  if (showLines) {
    ctx.strokeStyle = P.line;
    ctx.lineWidth = 1;
    // Gorizontal
    ctx.beginPath();
    let prevY = Number.NaN;
    for (const n of nodes) {
      if (!Number.isFinite(prevY) || Math.round(n.oy) !== prevY) {
        ctx.moveTo(n.x, n.y);
      } else {
        ctx.lineTo(n.x, n.y);
      }
      prevY = Math.round(n.oy);
    }
    ctx.stroke();
    // Vertikal
    ctx.beginPath();
    let prevX = Number.NaN;
    for (const n of nodes) {
      if (!Number.isFinite(prevX) || Math.round(n.ox) !== prevX) {
        ctx.moveTo(n.x, n.y);
      } else {
        ctx.lineTo(n.x, n.y);
      }
      prevX = Math.round(n.ox);
    }
    ctx.stroke();
  }

  // 🟢 Nuqtalar — qizarganlik bo'yicha kattalashadi va yorishadi
  for (const n of nodes) {
    const hot = heatOf(n.x, n.y, cx, cy, radius);
    ctx.beginPath();
    ctx.arc(n.x, n.y, dotBase + hot * (dotMax - dotBase), 0, Math.PI * 2);
    if (hot > 0.05) {
      ctx.fillStyle = P.dotHot;
      ctx.globalAlpha = 0.35 + hot * 0.65;
    } else {
      ctx.fillStyle = P.dot;
      ctx.globalAlpha = 0.55;
    }
    ctx.fill();
  }
  ctx.globalAlpha = 1;
}