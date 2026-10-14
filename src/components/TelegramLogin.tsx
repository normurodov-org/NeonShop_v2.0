/**
 * 🔐 Telegram orqali kirish — Telegram'ning rasmiy **Login Widget**'i.
 *
 * 🔴 BU YO'L 3 MARTA ISHLAMADI — shuning uchun har bir nuqta qayta
 *    ko'rib chiqildi va xatolar kiritildi. Quyidagi hamma Telegram'ning
 *    o'z skriptidan (`telegram-widget.js`, `widget-frame.js`) o'qib olingan.
 *
 * 1) `data-onauth` — ENG MUHIM. Yo'q bo'lsa:
 *        if (el.hasAttribute('data-onauth')) {
 *          onAuthUser = __parseFunction(el.getAttribute('data-onauth'), ['user']);
 *        } // aks holda `onAuthUser` = undefined
 *    → popup ochiladi, yopiladi, HECH NARSA chaqirilmaydi.
 *
 * 2) `data-onunauth` — ikkinchi yo'l:
 *        onAuth(origin, authData) {
 *          if (authData) data = {event:'auth_user', ...};
 *          else          data = {event:'unauthorized'};   // ← shu yerga tushadi
 *        }
 *        // ota tomonda: onUnauth && onUnauth();
 *    Oldin `data-onunauth` YO'Q EDI → natija kelmasa sahifa JIMGINA
 *    o'z-o'zidan qolardi («ekran ochildi-yopildi, lekin kirmadi»).
 *
 * 3) `window.open` kuzatuvchisi — 🔴 ASOSIY MITIGATSIYA.
 *    Tugma IFRAME ichida (oauth.telegram.org), shuning uchun biz
 *    bosilishni bevosita bilmaymiz. Lekin iframe `window.parent` dagi
 *    `window.open` ni chaqiradi — ya'ni BIZNING oynamiz orqali.
 *    Shu sababli `window.open` ni o'rab, bosilganini aniqlaymiz va
 *    **watchdog** yoqamiz: natija kelmasa, foydalanuvchiga aniq
 *    xabar beramiz (jimgina qolmasin).
 *
 * 4) Tiklash — `TWidgetLogin.authFinished` IFRAME ichida yashaydi.
 *    Bir marta `true` bo'lsa, o iframe boshqa hech qachon natija bermaydi
 *    (`onAuth` darhol qaytadi). Shuning uchun «Qayta urinish» iframe'ni
 *    butunlay YO'Q QILADI va yangisini qo'yadi — `authFinished` sifirlanadi.
 *
 * 5) Skript KARTA ICHIGA qo'yiladi (`box.appendChild`), `document.body`
 *    ga emas — aks holda iframe kartadan tashqarida, ko'rinmaydi.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
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
    onTelegramLoginError?: (message: string) => void;
    onTelegramLoginUnauth?: () => void;
  }
}

const WIDGET_SRC = 'https://telegram.org/js/telegram-widget.js?23';

/** Bosilgandan keyin natija kelmaydigan maksimal kutish (ms) */
const WATCHDOG_MS = 12_000;

export const TelegramLogin: React.FC<Props> = ({
  botUsername, isDark, onSuccess, onError,
}) => {
  const boxRef = useRef<HTMLDivElement>(null);
  const cbRef = useRef({ onSuccess, onError });
  cbRef.current = { onSuccess, onError };
  const [stuck, setStuck] = useState(false);

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

    // 🔴🔴 ENG MUHIM — callback bu atribut orqali topiladi.
    s.setAttribute('data-onauth', 'onTelegramAuth');
    // 🔴🔴 IKKINCHI YO'L — ruxsat berilmasa. Bu YO'Q EDI, ya'ni
    //    natija kelmasa hech narsa bo'lmasdi.
    s.setAttribute('data-onunauth', 'onTelegramLoginUnauth');
    s.setAttribute('data-onerror', 'onTelegramLoginError');

    s.setAttribute('data-size', 'large');
    s.setAttribute('data-radius', '18');
    s.setAttribute('data-userpic', 'true');
    // 🔐 `write` — bot foydalanuvchiga xabar yubora oladi
    //    (Stars yetkazildi, to'lov tasdiqlandi, va h.k.)
    s.setAttribute('data-request-access', 'write');
    // 🔴 Iframe QAYERDA chiqishini hal qilish uchun marker
    s.setAttribute('data-neon-login-widget', '1');

    box.appendChild(s);
  }, [botUsername]);

  /** Iframe'ni butunlay olib tashlab, yangisini qo'yadi.
   *  🔴 `TWidgetLogin.authFinished` iframe ichida — buni FAQAT
   *     yangi iframe reset qiladi. */
  const resetWidget = useCallback(() => {
    const box = boxRef.current;
    if (!box) return;
    box.querySelectorAll('script[data-telegram-login], iframe').forEach((n) => n.remove());
    inject();
  }, [inject]);

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;
    let retry: number | undefined;
    let watchdog: number | undefined;

    // ---------------------------------------------------------- 1) callback
    window.onTelegramAuth = async (data: string) => {
      try {
        // 📌 Telegram callbackga IZOHLAYDIGAN MATN yuboradi (obyekt emas):
        //    `id=...&first_name=...&hash=...`. `server.ts` ham shuni kutadi.
        const res = await fetch('/api/auth/telegram', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ data }),
        });
        const j = await res.json().catch(() => ({}));
        if (j?.ok && j.token) {
          if (watchdog) window.clearTimeout(watchdog);
          setSessionToken(j.token);
          cbRef.current.onSuccess();
        } else {
          cbRef.current.onError?.(j?.error || 'Tasdiqlash muvaffaqiyatsiz');
        }
      } catch (e: any) {
        cbRef.current.onError?.(e?.message || 'Tarmoq xatosi');
      }
    };

    /** 🔶 RUXSAT BERILMADI (`{event:'unauthorized'}`).
     *  Eski yo'lda bu HANDSHI kelardi va hech narsa bo'lmasdi. */
    window.onTelegramLoginUnauth = () => {
      if (watchdog) window.clearTimeout(watchdog);
      setStuck(true);
      cbRef.current.onError?.(
        "Telegram ruxsat bermadi. Agar birinchi marta bo'lsangiz, "
        + "Telegram da botga «Start» bering va qayta urinib ko'ring."
      );
    };

    /** 🔶 WIDGET ichidagi xato («Bot domain invalid» va h.k.) */
    window.onTelegramLoginError = (message: string) => {
      const m = String(message || '').toLowerCase();
      let hint = 'Telegram bilan bog‘lanishda xatolik yuz berdi.';
      if (m.includes('domain')) {
        hint = 'Telegram shu saytga ruxsat bermagan. Sayt administratoriga xabar bering.';
      } else if (m.includes('not found') || m.includes('unavailable')) {
        hint = 'Bot topilmadi — bot nomi noto‘g‘ri.';
      }
      cbRef.current.onError?.(hint);
    };

    // ------------------------------------------- 2) `window.open` kuzatuvchisi
    // 🔴 Tugma IFRAME ichida, shuning uchun bosilishni bevosita
    //    ko'ra olmaymiz. Lekin iframe `window.parent` dagi `window.open`
    //    ni chaqiradi — demak bu oyna orqali o'tadi. Shu yerda
    //    bosilganini aniqlab, watchdog yoqamiz.
    const origOpen = window.open;
    window.open = function (u?: any, n?: any, f?: any) {
      const p = origOpen.call(window, u as any, n as any, f as any);
      try {
        if (String(u).indexOf('/auth') >= 0) {
          setStuck(false);
          cbRef.current.onError?.('');           // eski xatoni tozalash
          if (watchdog) window.clearTimeout(watchdog);
          // 🔴 12 soniyada natija kelmasa — jimgina qolmaymiz
          watchdog = window.setTimeout(() => {
            if (!cancelled) setStuck(true);
          }, WATCHDOG_MS);
        }
      } catch { /* noqa: BLE001 */ }
      return p;
    };

    // ---------------------------------------------------------- 3) yuklash
    const tryInject = () => {
      if (cancelled) return;
      inject();
      // 🔴 Skript yuklangan, lekin iframe Hali chiqmagan bo'lishi mumkin.
      //    2.5 sekunddan keyin tekshirib, yo'q bo'lsa QAYTA qo'shamiz.
      retry = window.setTimeout(() => {
        const box = boxRef.current;
        if (!cancelled && box && !box.querySelector('iframe')) {
          box.querySelectorAll('script[data-telegram-login]').forEach((n) => n.remove());
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
      window.open = origOpen;                    // 🔴 o'ramani qaytarish
      window.removeEventListener('load', tryInject);
      if (timer) window.clearTimeout(timer);
      if (retry) window.clearTimeout(retry);
      if (watchdog) window.clearTimeout(watchdog);
    };
  }, [botUsername, inject]);

  return (
    <div className="mt-7 w-full">
      <div
        ref={boxRef}
        className="flex justify-center items-center min-h-[54px] w-full"
        aria-live="polite"
      />

      {/* 🔴 Natija kelmasa — JIM qolmaydi, aniq yo'l ko'rsatiladi */}
      {stuck && (
        <div
          className={`mt-3 rounded-2xl p-3.5 text-center ${
            isDark ? 'bg-white/[0.06] border border-white/10' : 'bg-neutral-100 border border-neutral-200'
          }`}
        >
          <p className={`text-[12.5px] leading-relaxed ${isDark ? 'text-neutral-300' : 'text-neutral-700'}`}>
            Telegram tasdiqlamadi. Ochilgan oynada <b>Start</b> tugmasini bosdingizmi?
          </p>
          <button
            type="button"
            onClick={() => { setStuck(false); resetWidget(); }}
            className="mt-2.5 h-9 w-full rounded-xl text-[12.5px] font-semibold text-white transition active:scale-[.98] bg-[#229ED9] hover:bg-[#1b8cc2]"
          >
            Qayta urinish
          </button>
        </div>
      )}
    </div>
  );
};

export default TelegramLogin;