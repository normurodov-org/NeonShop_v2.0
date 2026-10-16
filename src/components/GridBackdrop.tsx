import React, { useEffect, useRef } from 'react';
import {
  buildGrid, stepNodes, stepWaves, drawFrame,
  PALETTE_DARK, PALETTE_LIGHT,
  type GridNode, type Wave,
} from '../lib/gridBackdrop';

/**
 * 🟩 GRID BACKDROP — bot dizayiga mos qora + yashil to'r.
 *
 * 🔴 NIMA UCHUN?
 *   Avval fon — turli rangli (havorang, siyohrang, pushti, sariq)
 *   `aurora-blob` + `noise` edi. Bot esa qora-yashil «terminal» uslubida
 *   ishlaydi. Bu fon bot brendiga moslang.
 *
 * 🔴🔴 KURSOR OSTIDA NIMA BO'LADI (rasmdagi effekt):
 *   1) **TO'R (tor)** — kursor atrofidagi nuqtalar kursor tomon
 *      DEB SURILADI (radial repulsion). Rasmdagi markazdagi
 *      «cho'zilish» shuning natijasi.
 *   2) **To'lqin (ripple)** — kursor tezligiga bog'liq doira tarqaladi
 *      va so'ng yo'qoladi. Rasmda katta nuqtalarning yorishligi
 *      shu tolqindan.
 *   3) **Nuqta kattalashuvi** — yaqin nuqtalar kattalashadi va
 *      yorishadi (odatdagidan yorqoqroq bo'ladi).
 *   4) **Chiziq egilishi** — grid chiziqlari ham nuqta kabi siljiydi,
 *      ya'ni to'r birday buzilmaydi.
 *
 * 📌 SILLIQ HARAKAT: barcha nuqtalar kursor tomon `lerp` bilan
 *    yaqinlashadi — shuning uchun «suvsimon» oqim chiqadi, sakrab
 *    ketmaydi. Qaytish surishdan SEKIN (spring emas).
 *
 * 🔋 BATERIYA / SIFAT:
 *   • `prefers-reduced-motion: reduce` → tolqin tug'maydi
 *   • tab yashirin bo'lsa → rAF to'xtaydi
 *   • DPR 2 bilan cheklangan (Retina'da ham tekis, 4x emas)
 *   • kursor qo'ymasa → rAF o'zi to'xtaydi (bo'sh sikl yo'q)
 *
 * 📌 Mantiq `src/lib/gridBackdrop.ts` da — u DOM'siz, shuning uchun
 *    `tests/test_grid_backdrop.py` da to'g'ridan-to'g'ri sinanadi
 *    (headless brauzerda `requestAnimationFrame` ishlamaydi).
 */

interface Props {
  /** Yorug' rejim uchun yumshoqroq palitra. */
  isDark: boolean;
}

export const GridBackdrop: React.FC<Props> = ({ isDark }) => {
  const ref = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const cv = ref.current;
    if (!cv) return;
    const ctx = cv.getContext('2d', { alpha: false });
    if (!ctx) return;

    const P = isDark ? PALETTE_DARK : PALETTE_LIGHT;

    /* ── O'lchamlar ─────────────────────────────────────────────── */
    // 🔴 Telefonda 24px juda zich — chiziqlar «kofani» beradi.
    const resize = () => {
      const W = window.innerWidth;
      const H = window.innerHeight;
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      cv.width = Math.floor(W * dpr);
      cv.height = Math.floor(H * dpr);
      cv.style.width = `${W}px`;
      cv.style.height = `${H}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      // 🔴 Kichik ekranda katak kichraytiriladi (ko'proq nuqta),
      //    lekin juda zich bo'lmasin — chiziqlar qo'shilib ketadi.
      const cell = W < 640 ? 34 : 46;
      return {
        W, H, cell,
        nodes: buildGrid(W, H, cell),
        radius: cell * 3.0,
      };
    };

    let geo = resize();

    /* ── Kursor va tolqinlar ─────────────────────────────────────── */
    let px = geo.W / 2;
    let py = geo.H / 2;
    let cx = px;
    let cy = py;
    let active = false;
    let waves: Wave[] = [];

    const reduced = () =>
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    /* ── Kadr ────────────────────────────────────────────────────── */
    let raf = 0;

    const draw = () => {
      drawFrame(
        ctx as any, geo.W, geo.H, P, geo.nodes,
        cx, cy, active, waves, geo.radius, 1.1, 3.7,
      );
    };

    const step = () => {
      // 🔴 Kursor k target ga lerp bilan yaqinlashadi (suvsimon oqim)
      cx += (px - cx) * 0.12;
      cy += (py - cy) * 0.12;

      stepNodes(
        geo.nodes, cx, cy, geo.radius,
        geo.cell * 0.42,   // surish
        0.16,             // qaytish (yumshoqroq = spring yo'q)
      );
      waves = stepWaves(waves, geo.cell * 0.42);

      draw();

      // 🔴 Qachon to'xtash? Faqat kerak bo'lganda rAF davom etadi.
      const moving =
        active ||
        waves.length > 0 ||
        Math.abs(px - cx) > 0.05 ||
        Math.abs(py - cy) > 0.05 ||
        geo.nodes.some((n) => Math.abs(n.ox - n.x) > 0.05 || Math.abs(n.oy - n.y) > 0.05);

      raf = moving ? requestAnimationFrame(step) : 0;
    };

    const kick = () => {
      if (!raf) raf = requestAnimationFrame(step);
    };

    /* ── Hodisalar ────────────────────────────────────────────────── */
    let lastX = px;
    let lastY = py;

    const onMove = (e: PointerEvent) => {
      const wasActive = active;
      active = true;
      px = e.clientX;
      py = e.clientY;
      if (!wasActive) {
        cx = px;
        cy = py;
      }
      // 🔴 Tez silinsa — tolqin tug'iladi (rasmdagi yorishli halqalar)
      const speed = Math.hypot(px - lastX, py - lastY);
      if (speed > 34 && !reduced()) {
        waves.push({ x: px, y: py, r: 4, max: geo.cell * 3.4 });
        if (waves.length > 4) waves.shift();
      }
      lastX = px;
      lastY = py;
      kick();
    };

    const onLeave = () => {
      active = false;
      kick();
    };

    const onResize = () => {
      geo = resize();
      // 🔴 Ekran o'zgarganda kursor ochiq qolsa, uning o'rnini
      //    yangi o'lchamga ko'chiramiz (tor markazda qolmasin).
      if (active) {
        px = Math.min(px, geo.W);
        py = Math.min(py, geo.H);
      }
      kick();
    };

    const onVisibility = () => {
      if (document.hidden) {
        if (raf) cancelAnimationFrame(raf);
        raf = 0;
      } else {
        kick();
      }
    };

    draw();

    window.addEventListener('pointermove', onMove, { passive: true });
    window.addEventListener('pointerleave', onLeave, { passive: true });
    window.addEventListener('resize', onResize);
    document.addEventListener('visibilitychange', onVisibility);

    return () => {
      if (raf) cancelAnimationFrame(raf);
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerleave', onLeave);
      window.removeEventListener('resize', onResize);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [isDark]);

  return (
    <canvas
      ref={ref}
      aria-hidden="true"
      className="fixed inset-0 pointer-events-none z-0"
    />
  );
};

export default GridBackdrop;