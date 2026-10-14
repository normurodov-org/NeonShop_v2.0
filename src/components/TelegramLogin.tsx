/**
 * 🔐 Telegram orqali kirish (BRAZER uchun) — Telegram Login Widget.
 *
 * NIMA UCHUN?
 * Telegram ichida (`t.me/bot/app`) `initData` imzosi avtomatik keladi
 * va server uni BOT_TOKEN bilan tekshiradi — mijoz hech narsa bosmaydi.
 * Lekin saytni BRAUZERDA ochsa `initData` YO'Q: ilova
 * «Telegram orqali kiring» ekranida qolar edi.
 *
 * Yechim — Telegram'ning rasmiy **Login Widget**'i:
 *   • «Connect Telegram» tugmasi
 *   • bosilganda Telegram oynasi (qurilma / IP / Log in)
 *   • IMZOLANGAN ma'lumot qaytariladi
 * Server uni SHA256(bot_token) kaliti bilan tekshiradi va sessiya
 * beradi (WebApp'dan FARQ qilib HMAC("WebAppData") emas).
 *
 * 🔴 IKKI MUHIM NUQTA (bitta-birta tuzatilgan xato):
 *
 * 1) SKript NERAGA QO'SHILADI?
 *    Telegram'ning skripti iframe'ni o'zi yaratadi va o'sha yerda
 *    joylashtiradi — skript qaysi konteynerda bo'lsa, tugma ham
 *    shu yerda chiqadi. Skriptni `document.body` ga qo'shganimda
 *    tugma KARTA TASHQARISIDA (va ko'rinmay) chiqardi — mijoz
 *    bo'sh joy ko'rardi. Endi skript `boxRef` ICHIGA qo'shiladi.
 *
 * 2) QAYTA YUKLASH
 *    Skript `async` — `onload` voqeasi `body` yuklanganda bo'lishi
 *    mumkin emas. Shu sababli faqat `load` hodisasiga ishonib
 *    bo'lmaydi: `readyState` tekshiriladi va yuklanmagan bo'lsa
 *    tugma QAYTA qo'shiladi.
 */
import React, { useCallback, useEffect, useRef } from 'react';
import { setSessionToken } from '../lib/tgAuth';

interface Props {
  botUsername: string;
  isDark: boolean;
  onSuccess: () => void;
  onError?: (msg: string) => void;
}

declare global {
  interface Window {
    onTelegramAuth?: (user: any) => void;
    /** Telegram widget ichidagi xato (masalan «Bot domain invalid») */
    onTelegramLoginError?: (message: string) => void;
  }
}

const WIDGET_SRC = 'https://telegram.org/js/telegram-widget.js?23';

export const TelegramLogin: React.FC<Props> = ({
  botUsername, isDark, onSuccess, onError,
}) => {
  const boxRef = useRef<HTMLDivElement>(null);
  const cbRef = useRef({ onSuccess, onError });
  cbRef.current = { onSuccess, onError };

  /** Skriptni konteyner ichiga qo'shadi (iframe shu yerda chiqadi). */
  const inject = useCallback(() => {
    const box = boxRef.current;
    if (!box || !botUsername) return;

    // Allaqachon shu konteynerda skript/iframe bormi?
    if (box.querySelector('script[data-telegram-login]') || box.querySelector('iframe')) {
      return;
    }

    const s = document.createElement('script');
    s.src = WIDGET_SRC;
    s.async = true;
    s.setAttribute('data-telegram-login', botUsername);
    s.setAttribute('data-size', 'large');
    s.setAttribute('data-radius', '18');
    s.setAttribute('data-userpic', 'true');
    // 🔐 `write` — bot foydalanuvchiga xabar yubora oladi
    // (Stars yetkazildi, to'lov tasdiqlandi, va h.k.)
    s.setAttribute('data-request-access', 'write');
    // 🔴 Iframe QAYERDA chiqishini hal qilish uchun marker
    s.setAttribute('data-neon-login-widget', '1');
    // 🔴 `data-onerror` — Telegram widget ichidagi xatoni
    // «Bot domain invalid» / «Bot not found» kabi ko'rsatadi.
    // Bu hodisasiz mijoz XUDDI SHU YERDAGI xabarini ko'radi
    // (rasmdagi holat) va nima qilishini bilmaydi.
    s.setAttribute('data-onerror', 'onTelegramLoginError');
    box.appendChild(s);
  }, [botUsername]);

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;
    let retry: number | undefined;

    // ---------------------------------------------------------- 1) callback
    window.onTelegramAuth = async (user: any) => {
      try {
        const res = await fetch('/api/auth/telegram', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ data: user }),
        });
        const j = await res.json();
        if (j?.ok && j.token) {
          setSessionToken(j.token);
          cbRef.current.onSuccess();
        } else {
          cbRef.current.onError?.(j?.error || 'Tasdiqlash muvaffaqiyatsiz');
        }
      } catch (e: any) {
        cbRef.current.onError?.(e?.message || 'Tarmoq xatosi');
      }
    };

    // 🔶 WIDGET XATOSI. Telegram ichida «Bot domain invalid»
    //    chiqsa — sabab: @BotFather da bu domen ro'yxatga
    //    olINGAN EMAS (`/setdomain`). Bu holatda foydalanuvchi
    //    hech nima qilolmaydi, shuning uchun biz aniq xabar
    //    ko'rsatamiz.
    window.onTelegramLoginError = (message: string) => {
      const m = String(message || '').toLowerCase();
      let hint = 'Telegram bilan bog‘lanishda xatolik yuz berdi.';
      if (m.includes('domain')) {
        hint =
          '«Bot domain invalid» — Telegram shu saytga ruxsat berilmagan.\n'
          + 'BotFather → /setdomain → domenni kiritish kerak.';
      } else if (m.includes('not found') || m.includes('unavailable')) {
        hint = 'Bot topilmadi — bot nomi noto‘g‘ri.';
      }
      cbRef.current.onError?.(hint);
    };

    // ---------------------------------------------------------- 2) yuklash
    const tryInject = () => {
      if (cancelled) return;
      inject();
      // 🔴 Skript yuklanib bo'lib, lekin iframe Hali chiqmagan bo'lishi
      // mumkin (Telegram o'z serveridan yuklaydi). 2.5 sekundan keyin
      // tekshirib, yo'q bo'lsa QAYTA qo'shamiz — aks holda tugma
      // bo'sh joy qolib, mijoz "ishlamadi" deb o'ylaydi.
      retry = window.setTimeout(() => {
        const box = boxRef.current;
        if (!cancelled && box && !box.querySelector('iframe')) {
          const old = box.querySelector('script[data-telegram-login]');
          if (old) old.remove();
          inject();
        }
      }, 2500);
    };

    if (document.readyState === 'complete') {
      timer = window.setTimeout(tryInject, 0);
    } else {
      window.addEventListener('load', tryInject, { once: true });
    }

    return () => {
      cancelled = true;
      window.removeEventListener('load', tryInject);
      if (timer) window.clearTimeout(timer);
      if (retry) window.clearTimeout(retry);
    };
  }, [botUsername, inject]);

  return (
    <div
      ref={boxRef}
      className="flex justify-center items-center min-h-[54px] w-full"
      aria-live="polite"
    />
  );
};

export default TelegramLogin;