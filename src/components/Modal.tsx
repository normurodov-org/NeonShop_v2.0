import React, { useEffect } from 'react';
import { createPortal } from 'react-dom';

/**
 * Modal oynasi — VIEWPORT ga biriktirilgan.
 *
 * 🔴 NIMA UCHUN BU KERAK:
 * `position: fixed` element `transform`, `filter`, `perspective`,
 * `backdrop-filter` yoki `contain` ko'rsatgan ajodaga nisbatan
 * joylashadi — VIEWPORT ga emas.
 *
 * Ilovamizda `apple-view-animate` `animation-fill-mode: both` bilan
 * ishlatiladi, ya'ni animatsiya tugagandan keyin ham
 * `transform: scale(1)` va `filter: blur(0px)` QOLADI. Ikkalasi ham
 * containing block yaratadi. Shu sabab har bir view ichidagi modal
 * ekranning emas, balki butun konteyner balandligida joylashgan
 * bo'ladi — CTA tugmasi ekrandan tashqariga chiqib ketadi.
 *
 * Yechim: `createPortal(..., document.body)` — modal DOM da
 * `body` ning to'g'ridan-to'g'ri farzadi bo'ladi, hech qanday
 * transform/filter unga tegmaydi va `fixed` ishlaydi.
 */
interface ModalProps {
  open: boolean;
  onClose: () => void;
  children: React.ReactNode;
  /** `sm:items-center` — katt ekranda markazda, telefonda pastda */
  align?: 'bottom' | 'center';
  /** Zarur bo'lsa ekranni to'ldiruvchi fon */
  dim?: boolean;
  label?: string;
}

export const Modal: React.FC<ModalProps> = ({
  open,
  onClose,
  children,
  align = 'bottom',
  dim = true,
  label,
}) => {
  // Escape bilan yopish
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  // Modal ochiqligida orqa fonni skrol qilmaslik.
  // DIQQAT: body.style ni to'g'ridan-to'g'ri o'zgartirmaslik kerak —
  // Telegram WebApp o'z skrolini boshqaradi, biz uni buzib qo'yamiz.
  // Faqat `overflow: hidden` qo'yamiz va o'z holatini tiklaymiz.
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  if (!open) return null;

  return createPortal(
    <div
      className={`fixed inset-0 z-[100] flex justify-center ${
        align === 'bottom' ? 'items-end sm:items-center' : 'items-center'
      }`}
      role="dialog"
      aria-modal="true"
      aria-label={label}
    >
      {dim && (
        <div
          className="absolute inset-0 bg-black/60 backdrop-blur-sm"
          onClick={onClose}
          aria-hidden
        />
      )}
      {children}
    </div>,
    document.body,
  );
};

export default Modal;