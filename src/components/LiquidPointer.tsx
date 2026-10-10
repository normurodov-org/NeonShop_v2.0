import { useEffect } from 'react';

/**
 * LiquidPointer — WWDC25 Liquid Glass uslubida kursor yorug'ini kuzatadi.
 * --mx / --my: barcha glass sirtlaridagi specular yorug'i uchun viewport koordinatalari
 * --ax / --ay: aurora fon parallaksi
 * rAF + lerp bilan "suvsimon" silliq harakat.
 */
export const LiquidPointer: React.FC = () => {
  useEffect(() => {
    const root = document.documentElement;
    let tx = window.innerWidth / 2;
    let ty = window.innerHeight * 0.3;
    let cx = tx;
    let cy = ty;
    let raf = 0;
    let running = false;

    const apply = () => {
      root.style.setProperty('--mx', `${cx}px`);
      root.style.setProperty('--my', `${cy}px`);
      const nx = ((cx / window.innerWidth) - 0.5) * 2;
      const ny = ((cy / window.innerHeight) - 0.5) * 2;
      root.style.setProperty('--ax', `${(nx * 14).toFixed(2)}px`);
      root.style.setProperty('--ay', `${(ny * 14).toFixed(2)}px`);
    };

    const loop = () => {
      const dx = tx - cx;
      const dy = ty - cy;
      cx += dx * 0.16;
      cy += dy * 0.16;
      apply();
      if (Math.abs(dx) > 0.05 || Math.abs(dy) > 0.05) {
        raf = requestAnimationFrame(loop);
      } else {
        running = false;
      }
    };

    const start = () => {
      if (!running) {
        running = true;
        raf = requestAnimationFrame(loop);
      }
    };

    const onMove = (e: PointerEvent) => {
      tx = e.clientX;
      ty = e.clientY;
      start();
    };

    window.addEventListener('pointermove', onMove, { passive: true });
    window.addEventListener('pointerdown', onMove, { passive: true });
    apply();

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerdown', onMove);
    };
  }, []);

  return null;
};
