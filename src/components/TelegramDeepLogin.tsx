/**
 * 🌐 Telegram orqali kirish — DEEP LINK usuli.
 *
 * 🔴 NIMA UCHUN BU KOMPONENT QO'SHILDI?
 *    Telegram'ning eski **Login Widget** popup oqimi ishonchsiz bo'lib
 *    chiqdi. Mijoz xabari: «tugmani bosdim, ekran ochilib 1 soniyada
 *    yopildi, sahifa o'zgarmadi». Telegram'ning `/auth/get` javobini
 *    tekshirish natijani ko'rsatdi:
 *
 *      {"error":"NOT_AUTHORIZED", "origin":"https://..."}
 *
 *    Bu `TWidgetLogin.onAuth(origin, false)` → `{event:'unauthorized'}`
 *    → ota tomonda `onUnauth && onUnauth()`. Bizda `data-onunauth`
 *    YO'Q EDI, shuning uchun hech narsa bo'lmasdi — sahifa jimgina
 *    o'z-o'zidan qolardi.
 *
 * ✅ BU YO'L — popup umuman yo'q:
 *      1. server bitta martalik kod beradi (`web_<48hex>`)
 *      2. biz `https://t.me/<bot>?start=<kod>` ni ochamiz
 *      3. mijoz Telegram'da **Start** bosadi
 *      4. bot.py kodni `*_login_codes.json` ga yozadi
 *      5. biz `GET /api/auth/telegram/status` bilan kutamiz
 *      6. server sessiya beradi
 *
 *    Popup yo'q, CORS yo'q, third-party cookie yo'q. Kompyuterdagi
 *    Telegram ham, telefon ham bir xil ishlaydi.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { setSessionToken } from '../lib/tgAuth';

interface Props {
  isDark: boolean;
  onSuccess: () => void;
  onError?: (msg: string) => void;
}

type Phase = 'idle' | 'opening' | 'waiting' | 'failed';

const POLL_MS = 1500;
const MAX_WAIT_MS = 5 * 60 * 1000;

export const TelegramDeepLogin: React.FC<Props> = ({ isDark, onSuccess, onError }) => {
  const [phase, setPhase] = useState<Phase>('idle');
  const [secLeft, setSecLeft] = useState(MAX_WAIT_MS / 1000);
  const codeRef = useRef<string | null>(null);
  const popupRef = useRef<Window | null>(null);
  const timerRef = useRef<number | undefined>(undefined);
  const startRef = useRef<number | undefined>(undefined);
  const doneRef = useRef(false);

  const stop = useCallback(() => {
    if (timerRef.current) window.clearTimeout(timerRef.current);
    if (startRef.current) window.clearInterval(startRef.current);
    timerRef.current = undefined;
    startRef.current = undefined;
  }, []);

  // 🔴 Komponent unmount bo'lsa kutish to'xtaydi (memory leak bo'lmasin)
  useEffect(() => () => stop(), [stop]);

  /** 🔍 Kodni tekshiradi — Telegram'da Start bosilganmi? */
  const poll = useCallback(async () => {
    const code = codeRef.current;
    if (!code || doneRef.current) return;

    try {
      const res = await fetch(`/api/auth/telegram/status?code=${encodeURIComponent(code)}`);
      const j = await res.json().catch(() => ({}));

      if (j?.status === 'ok' && j?.token) {
        doneRef.current = true;
        stop();
        setSessionToken(j.token);
        onSuccess();
        return;
      }
      if (j?.status === 'error') {
        doneRef.current = true;
        stop();
        setPhase('failed');
        onError?.(j?.error || 'Tasdiqlash muvaffaqiyatsiz');
        return;
      }
      // 'pending' — Telegram'da Start hali bosilmagan
    } catch {
      // Tarmoq uzildi — keyingi urinishga qoldiramiz
    }

    timerRef.current = window.setTimeout(poll, POLL_MS);
  }, [stop, onError, onSuccess]);

  /** ▶️ Kirishni boshlash */
  const start = useCallback(async () => {
    setPhase('opening');
    setSecLeft(MAX_WAIT_MS / 1000);
    doneRef.current = false;

    try {
      const res = await fetch('/api/auth/telegram/start', { method: 'POST' });
      const j = await res.json().catch(() => ({}));
      if (!res.ok || !j?.telegram_url) {
        setPhase('failed');
        onError?.(j?.error || 'Serverga ulanib bo\'lmadi');
        return;
      }

      codeRef.current = j.code;
      setPhase('waiting');

      // 🪟 Telegram oynasi — yangi tabda. Popup bloklanmasligi uchun
      //    `window.open` foydalanuvchi BOSGAN paytda chaqirilishi shart
      //    (async await dan keyin ba'zi brauzerlarda bloklanadi).
      const w = window.open(j.telegram_url, '_blank');
      popupRef.current = w;

      const startedAt = Date.now();
      startRef.current = window.setInterval(() => {
        const left = MAX_WAIT_MS - (Date.now() - startedAt);
        setSecLeft(Math.max(0, Math.round(left / 1000)));
        if (left <= 0) {
          stop();
          if (!doneRef.current) {
            setPhase('failed');
            onError?.('Vaqt tugadi. Telegram\'da «Start»ni bosmadingiz.');
          }
        }
      }, 1000);

      timerRef.current = window.setTimeout(poll, POLL_MS);
    } catch (e: any) {
      setPhase('failed');
      onError?.(e?.message || 'Tarmoq xatosi');
    }
  }, [poll, stop, onError]);

  const busy = phase === 'waiting';
  const mm = Math.floor(secLeft / 60);
  const ss = secLeft % 60;

  return (
    <div className="mt-7 w-full">
      {!busy ? (
        <button
          type="button"
          onClick={start}
          disabled={phase === 'opening'}
          className={`w-full h-[54px] rounded-2xl font-semibold text-[15px] flex items-center justify-center gap-2.5 transition active:scale-[.98] disabled:opacity-60 ${
            isDark
              ? 'bg-[#2AABEE] text-white hover:bg-[#3cb3f2]'
              : 'bg-[#229ED9] text-white hover:bg-[#1b8cc2]'
          }`}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M21.9 4.3c-.2-.9-1-1.6-1.9-1.8C18.2 2.2 12 2.2 12 2.2s-6.2 0-8 .3c-.9.2-1.7.9-1.9 1.8C1.8 6.1 1.8 12 1.8 12s0 5.9.3 7.7c.2.9 1 1.6 1.9 1.8 1.8.3 8 .3 8 .3s6.2 0 8-.3c.9-.2 1.7-.9 1.9-1.8.3-1.8.3-7.7.3-7.7s0-5.9-.3-7.7zM9.9 15.6V8.4l6.3 3.6-6.3 3.6z" />
          </svg>
          {phase === 'failed' ? 'Qayta urinish' : 'Telegram orqali kiring'}
        </button>
      ) : (
        /* ⏳ Kutish holati — foydalanuvchi nima qilishini ANIQ ko'rsatadi */
        <div
          className={`rounded-2xl p-4 text-center ${
            isDark ? 'bg-white/[0.06] border border-white/10' : 'bg-neutral-100 border border-neutral-200'
          }`}
        >
          <div
            className={`mx-auto mb-3 h-8 w-8 rounded-full border-[3px] border-t-transparent animate-spin ${
              isDark ? 'border-[#2AABEE]' : 'border-[#229ED9]'
            }`}
          />
          <p className={`text-[13.5px] font-semibold ${isDark ? 'text-white' : 'text-neutral-900'}`}>
            Telegram oynasida <span className="text-[#2AABEE]">Start</span> ni bosing
          </p>
          <p className={`text-[12px] mt-1 ${isDark ? 'text-neutral-400' : 'text-neutral-600'}`}>
            Bu oyna ochilmaganda{' '}
            <button
              type="button"
              onClick={start}
              className="underline underline-offset-2 font-medium"
            >
              bu yerga bosing
            </button>
          </p>
          {mm > 0 && (
            <p className={`text-[11.5px] mt-2 tabular-nums ${isDark ? 'text-neutral-500' : 'text-neutral-500'}`}>
              {mm}:{String(ss).padStart(2, '0')} dan keyin to'xtaydi
            </p>
          )}
          <button
            type="button"
            onClick={() => {
              doneRef.current = true;
              stop();
              popupRef.current?.close();
              setPhase('idle');
            }}
            className={`mt-3 text-[12px] underline underline-offset-2 ${
              isDark ? 'text-neutral-400' : 'text-neutral-600'
            }`}
          >
            Bekor qilish
          </button>
        </div>
      )}
    </div>
  );
};

export default TelegramDeepLogin;