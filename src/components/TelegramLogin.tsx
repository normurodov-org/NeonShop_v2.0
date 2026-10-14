/**
 * 🔐 Telegram orqali kirish (BRAZER uchun) — Telegram Login Widget.
 *
 * NIMA UCHUN?
 * Telegram ichida (`t.me/bot/app`) `initData` imzosi avtomatik keladi
 * va server uni BOT_TOKEN bilan tekshiradi — mijoz hech narsa bosmaydi.
 * Lekin saytni BRAUZERDA (kompyuter / planshet) ochsa `initData` YO'Q:
 * ilova «Telegram orqali kiring» ekranida qolardi va hech qanday
 * xizmat ishlamasdi.
 *
 * Yechim — Telegram'ning rasmiy **Login Widget**'i:
 *   • brauzerda `my.telegram.org` orqali Telegram'ning o'z oynasini ochadi
 *   • foydalanuvchi «Telegram bilan davom etish» bosadi
 *   • IMZOLANGAN ma'lumot qaytariladi
 * Server uni SHA256(bot_token) kaliti bilan tekshiradi va sessiya
 * beradi (WebApp'dan FARQ qilib HMAC("WebAppData") emas).
 */
import React, { useEffect, useRef } from 'react';
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
  }
}

export const TelegramLogin: React.FC<Props> = ({ botUsername, isDark, onSuccess, onError }) => {
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;

    // 1) Telegram'ning rasmiy skriptini yuklaymiz
    const existing = document.querySelector('script[data-neon-login-widget]');
    const inject = () => {
      if (cancelled || !boxRef.current) return;
      if (existing) return;
      const s = document.createElement('script');
      s.src = 'https://telegram.org/js/telegram-widget.js?23';
      s.async = true;
      s.setAttribute('data-telegram-login', botUsername);
      s.setAttribute('data-size', 'large');
      s.setAttribute('data-radius', '18');
      s.setAttribute('data-userpic', 'true');
      s.setAttribute('data-request-access', 'write');
      s.setAttribute('data-neon-login-widget', '1');
      document.body.appendChild(s);
    };

    // 2) Telegram autentifikatsiya qilinganda chaqiriladi
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
          onSuccess();
        } else {
          onError?.(j?.error || 'Tasdiqlash muvaffaqiyatsiz');
        }
      } catch (e: any) {
        onError?.(e?.message || 'Tarmoq xatosi');
      }
    };

    // Skript allaqachon yuklangan bo'lsa bo'sh joyga to'g'ridan-to'g'ri qo'yamiz
    if (typeof (window as any).TelegramLoginWidget !== 'undefined'
      && !existing && document.querySelector('iframe[src*="telegram.org"]')) {
      inject();
      return () => { cancelled = true; };
    }

    if (document.readyState === 'complete') setTimeout(inject, 0);
    else window.addEventListener('load', inject, { once: true });

    return () => {
      cancelled = true;
      window.removeEventListener('load', inject);
      window.onTelegramAuth = undefined;
    };
  }, [botUsername, onSuccess, onError]);

  return (
    <div
      ref={boxRef}
      className="flex justify-center items-center min-h-[54px] w-full"
      aria-live="polite"
    >
      {!botUsername && (
        <p className={`text-xs ${isDark ? 'text-neutral-400' : 'text-neutral-600'}`}>
          Bot nomi sozlanmagan
        </p>
      )}
    </div>
  );
};

export default TelegramLogin;