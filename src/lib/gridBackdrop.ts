/**
 * 🟩 GRID BACKDROP — chizish va harakat MANTIG'I (sof, DOM'siz).
 *
 * 🔴 NIMA UCHUN AJRATILGAN?
 *   `GridBackdrop.tsx` ichida hammasi bo'lsa, chizish/harakat mantiqini
 *   sinab bo'lmaydi — `requestAnimationFrame` headless muhitda ishlamaydi
 *   va `canvas` yo'q. Bu modul esa DOM va rAF talab qilmaydi, shuning
 *   uchun Node'da to'g'ridan-to'g'ri sinovlanadi (test_grid_backdrop.py).
 *
 * 📌 XALQARO PARAMETRL:
 *   • ta'sir radiusi — kursor atrofidagi hudud
 *   • surish kuchaytiruvchisi (quyidagi kvadrat tengligi)
 *   • qaytish tezligi (`lerp`) — spring emas, suvsimon oqim
 */

export interface GridNode {
  /** Joriy (siljigan) pozitsiya — chiziladigan. */
  x: number;
  y: number;
  /** Dastlabki (tinch) pozitsiya — qaytish nishoni. */
  ox: number;
  oy: number;
}

/** Ranglar (bot brendidan: qora + yashil). */
export interface GridPalette {
  bg: string;
  line: string;
  dot: string;
  dotHot: string;
  glow: string;
  wave: string;
}

export const PALETTE_DARK: GridPalette = {
  bg: '#000000',
  line: 'rgba(23, 64, 30, 0.55)',
  dot: 'rgba(45, 139, 58, 0.85)',
  dotHot: 'rgba(120, 220, 130, 1)',
  glow: 'rgba(60, 200, 80, 0.10)',
  wave: 'rgba(90, 210, 110,',
};

export const PALETTE_LIGHT: GridPalette = {
  bg: '#f7faf7',
  line: 'rgba(28, 110, 44, 0.16)',
  dot: 'rgba(34, 139, 56, 0.45)',
  dotHot: 'rgba(22, 120, 40, 0.85)',
  glow: 'rgba(60, 200, 80, 0.08)',
  wave: 'rgba(40, 150, 60,',
};

/** Tolqin halqasi. */
export interface Wave {
  x: number;
  y: number;
  /** Joriy radius. */
  r: number;
  /** Oxirgi radius — shundan keyin yo'qoladi. */
  max: number;
}

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
 *     harakatsiz, markizda eng kuchli (chiziqlar «cho'ziladi»)
 *   • 🔴 SURISH va QAYTISH turlicha: qaytish `lerp` bilan YUMSHAQ,
 *     aks holda to'r «spring» bo'lib sakrab ketadi (rasmda yo'q)
 *
 * @param push surish kuchaytiruvchisi (ko'pincha `cell * 0.42`)
 * @param pull qaytish tezligi (0..1) — kichikroq = sekinroq
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
    if (d2 < R2 && d2 > 1e-6) {
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

/** Tolqinlarni kengaytiradi va o'lgilarini olib tashlaydi. */
export function stepWaves(waves: Wave[], speed: number): Wave[] {
  const out: Wave[] = [];
  for (const w of waves) {
    w.r += speed;
    if (w.r < w.max) out.push(w);
  }
  return out;
}

/**
 * 🔴 Nuqtaning «qizarganligi» 0..1 — kursor yaqinligi.
 * Kvadrat bilan ko'tariladi: chetlar yumshoq, markiz to'liq.
 */
export function heatOf(x: number, y: number, cx: number, cy: number, radius: number): number {
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
  createRadialGradient(x: number, y: number, r0: number, x1: number, y1: number, r1: number): {
    addColorStop(o: number, c: string): void;
  };
}

/** Butun kadrni chizadi (fon + yorug'lik + tolqin + tor + nuqtalar). */
export function drawFrame(
  ctx: Ctx2D,
  W: number,
  H: number,
  P: GridPalette,
  nodes: GridNode[],
  cx: number,
  cy: number,
  active: boolean,
  waves: Wave[],
  radius: number,
  dotBase: number,
  dotMax: number,
): void {
  ctx.fillStyle = P.bg;
  ctx.fillRect(0, 0, W, H);

  // 1) Kursor atrofidagi yumshoq yorug'lik
  if (active) {
    const r3 = radius * 1.2;
    const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, r3);
    g.addColorStop(0, P.glow);
    g.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = g;
    ctx.fillRect(cx - r3, cy - r3, r3 * 2, r3 * 2);
  }

  // 2) Tolqin halqalari
  ctx.lineWidth = 1;
  for (const w of waves) {
    const t = w.r / w.max;
    ctx.beginPath();
    ctx.arc(w.x, w.y, w.r, 0, Math.PI * 2);
    ctx.strokeStyle = `${P.wave}${(0.18 * (1 - t)).toFixed(3)})`;
    ctx.stroke();
  }

  // 3) Grid chiziqlari — nuqtalarning SILJIGAN joyidan
  ctx.strokeStyle = P.line;
  ctx.lineWidth = 1;
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

  // 4) Nuqtalar — qizarganlik bo'yicha kattalashadi va yorishadi
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