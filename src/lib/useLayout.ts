/**
 * 📐 Ekran o'lchamini kuzatish.
 *
 * NIMA UCHUN?
 * Ilova telefon uchun `max-w-md` (448px) bilan qurilgan edi: pastki
 * navigatsiya, 4 ustunli kartalar, barcha `max-w-md` konteynerlar.
 * Kompyuter va planshetda bu "telefonni kattalashtirilgan ko'rinish"
 * bo'lib qolardi — chapdan va o'ngdan bo'sh joy, matn kichik, tugmalar
 * noqulay.
 *
 * Yechim: bitta joyda aniqlanadi va butun ilova bo'ylab ishlatiladi:
 *   • `>= 768px` — desktop: chap menyu paneli + keng kontent
 *   • `< 1024px`  — telefon: hozirgi ko'rinish saqlanadi
 */
import { useEffect, useState } from 'react';

export const DESKTOP_BREAKPOINT = 768;

export function useIsDesktop(): boolean {
  const [isDesktop, setIsDesktop] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false;
    return window.innerWidth >= DESKTOP_BREAKPOINT;
  });

  useEffect(() => {
    const mq = window.matchMedia(`(min-width: ${DESKTOP_BREAKPOINT}px)`);
    const on = () => setIsDesktop(mq.matches);
    on();
    mq.addEventListener('change', on);
    return () => mq.removeEventListener('change', on);
  }, []);

  return isDesktop;
}

/** Telefon uchun quyi breypoint (kichik ekranlar uchun). */
export function useIsSmallPhone(): boolean {
  const [small, setSmall] = useState<boolean>(() => {
    if (typeof window === 'undefined') return true;
    return window.innerWidth < 380;
  });
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 379px)');
    const on = () => setSmall(mq.matches);
    on();
    mq.addEventListener('change', on);
    return () => mq.removeEventListener('change', on);
  }, []);
  return small;
}