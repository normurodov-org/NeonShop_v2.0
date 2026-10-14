/**
 * 🔐 Telegram orqali kirish.
 *
 * 🔴🔴 BU — ISHONCHLI YECHIM. Oldingi yechim ishlamasligining SABABI
 *
 * Telegram'ning eski Login Widget skripti (`telegram-widget.js?23`)
 * natijani ICHKI funksiya orqali qaytaradi:
 *
 *     onInitAuthUser = onAuthUser = __parseFunction('onTelegramAuth', ['user']);
 *     // = eval("(function(user){onTelegramAuth})")  → funksiya QAYTARILADI,
 *     //   lekin HECH QACHON chaqirilmaydi
 *     ...
 *     var auth_result = haveTgAuthResult();
 *     if (auth_result && onAuthUser) { onAuthUser(auth_result); }
 *
 * Bu skript o'z ichida `window.open` bilan popup ochadi, `postMessage` bilan
 * natija kutadi va `checkClose()` bilan har 100 ms da `popup.closed` ni
 * tekshiradi. Agar popup bir zumda yopilgan deb hisoblansa — `getAuth()`
 * chaqiriladi, u hali tasdiqlanmagan natija qaytaradi, `authFinished = true`
 * bo'ladi va butun oqim **o'limga** tortiladi. Natijada:
 *
 *     tugma bosiladi → popup ochiladi → yopiladi → HECH NARSA
 *
 * Bu Telegram'ning ichki ishi — biz uni tuzatamiz emas, balki
 * 🟢 RASMIY VA ISHONCHLI YO'LGA O'TAMIZ:
 *
 *     1. `https://oauth.telegram.org/auth?bot_id=…&origin=…&return_to=…`
 *        (Telegram'ning RASMIY OAuth sahifasi — popup emas, oddiy
 *         sahifa navigatsiyasi)
 *     2. Mijoz Telegram'da tasdiqlaydi
 *     3. Telegram `return_to#tgAuthResult=<base64url>` ga qaytaradi
 *     4. 🔴 Qaytishni TUGINKI O'ZIMIZ qaytaramiz — Telegram skriptiga
 *        bog'liq bo'lmaymiz
 *
 * Bu ham Telegram'ning rasmiy mexanizmi (bir xil imzo, bir xil
 * `SHA256(bot_token)` kaliti, bir xil `/api/auth/telegram` endpoint),
 * faqat popup va uning zaif tomonlari yo'q.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { setSessionToken } from '../lib/tgAuth';

interface Props {
  botUsername: string;
  botId: number;
  isDark: boolean;
  onSuccess: () => void;
  onError?: (msg: string) => void;
}

const TG_AUTH_ORIGIN = 'https://oauth.telegram.org';

/**
 * 🔴 `location.hash` dagi `#tgAuthResult=…` ni o'qiydi.
 *
 * 📌 FORMAT: base64url(JSON). Ichida:
 *      { id, first_name, username, photo_url, auth_date, hash }
 *
 * 📌 Telegram'ning skripti bu ma'lumotni `onAuthUser` ga **obyekt**
 *    sifatida beradi, popup oqimida esa **MATN** beradi. Serverimiz
 *    matn formatini kutadi, shuning uchun obyektni kanonik matnga
 *    qaytarib beramiz.
 */
export function readTelegramAuthResult(): string | null {
  const m = location.hash.match(/[#?&]tgAuthResult=([A-Za-z0-9\-_=]*)$/);
  if (!m || !m[1]) return null;
  // 🔴 HASH NI DARHOL TOZALAYMIZ — aks holda sahifa yangilanganda
  //    bir xil natija yana keladi (eskirgan sessiya bilan aralashadi)
  location.hash = location.hash.replace(/[#?&]tgAuthResult=[A-Za-z0-9\-_=]*$/, '');
  try {
    let b64 = m[1].replace(/-/g, '+').replace(/_/g, '/');
    const pad = b64.length % 4;
    if (pad > 1) b64 += new Array(5 - pad).join('=');
    const obj = JSON.parse(window.atob(b64));
    if (!obj || !obj.id || !obj.hash) return null;
    // 🔴📌 FORMAT: server `parseInitData` ishlatadi — ya'ni BUZILGAN
    //    QUERY STRING (`id=…&first_name=…&hash=…`) kutadi. Agar
    //    `k=v\n` ko'rinishida yuborsak, server «hash yo'q» deydi
    //    (2024-yilda shu sababdan kulrang xatolik chiqadi).
    //
    //    ✅ Telegram'ning o'z widget skripti ham `onAuthUser` ga shu
    //       formatda MATN yuboradi (popup oqimida). Biz shu formatni
    //       qo'lda tiklaymiz — imzo serverda `SHA256(bot_token)` bilan
    //       tekshiriladi, ya'ni bu Telegram'ning rasmiy imzosi.
    const keys = ['id', 'first_name', 'last_name', 'username', 'photo_url', 'auth_date'];
    const parts: string[] = [];
    for (const k of keys) {
      if (obj[k] !== undefined && obj[k] !== null) {
        parts.push(`${k}=${encodeURIComponent(String(obj[k]))}`);
      }
    }
    parts.push(`hash=${encodeURIComponent(String(obj.hash))}`);
    return parts.join('&');
  } catch {
    return null;
  }
}

/** Rasmiy OAuth havolasi (popup yo'q). */
export function telegramAuthUrl(botId: number): string {
  const origin = `${location.origin}`;
  const params = new URLSearchParams({
    bot_id: String(botId),
    origin,
    return_to: `${location.origin}${location.pathname}`,
  });
  return `${TG_AUTH_ORIGIN}/auth?${params.toString()}`;
}

export const TelegramLogin: React.FC<Props> = ({
  botUsername, botId, isDark, onSuccess, onError,
}) => {
  const cbRef = useRef({ onSuccess, onError });
  cbRef.current = { onSuccess, onError };
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  /** 🔴 IZOHLANGAN NATIJANI serverga yuboradi. */
  const submit = useCallback(async (data: string) => {
    setBusy(true);
    setErr(null);
    try {
      const res = await fetch('/api/auth/telegram', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ data }),
      });
      const j = await res.json().catch(() => ({}));
      if (j?.ok && j.token) {
        setSessionToken(j.token);
        cbRef.current.onSuccess();
      } else {
        setBusy(false);
        setErr(j?.error || 'Telegram tasdiqlamadi');
        cbRef.current.onError?.(j?.error || 'Telegram tasdiqlamadi');
      }
    } catch (e: any) {
      setBusy(false);
      setErr(e?.message || 'Tarmoq xatosi');
      cbRef.current.onError?.(e?.message || 'Tarmoq xatosi');
    }
  }, []);

  // 🔴 Sahifa ochilganda Telegram qaytarib qoldirgan natijani olamiz
  useEffect(() => {
    const data = readTelegramAuthResult();
    if (data) submit(data);
  }, [submit]);

  // 🔴 Popup oqimidan qolgan natija (agar Telegram skripti ishlasa)
  useEffect(() => {
    const onMsg = (e: MessageEvent) => {
      if (e.origin !== TG_AUTH_ORIGIN) return;
      let d: any = {};
      try { d = JSON.parse(e.data); } catch { return; }
      if (d?.event === 'auth_user' && d.auth_data && !busy) {
        submit(String(d.auth_data));
      } else if (d?.event === 'unauthorized' && !busy) {
        setErr('Telegram ruxsat bermadi');
      }
    };
    window.addEventListener('message', onMsg);
    return () => window.removeEventListener('message', onMsg);
  }, [submit, busy]);

  const go = () => {
    if (!botId) { setErr('Bot aniqlanmadi'); return; }
    // 🔴 Odiiy sahifa navigatsiyasi — popup yo'q, `popup.closed` yopiqligi yo'q
    window.location.href = telegramAuthUrl(botId);
  };

  return (
    <div className="mt-7 w-full">
      {busy ? (
        <div className={`rounded-2xl p-4 text-center ${
          isDark ? 'bg-white/[0.06] border border-white/10' : 'bg-neutral-100 border border-neutral-200'
        }`}>
          <div className={`mx-auto mb-3 h-7 w-7 rounded-full border-[3px] border-t-transparent animate-spin ${
            isDark ? 'border-[#2AABEE]' : 'border-[#229ED9]'
          }`} />
          <p className={`text-[13px] font-semibold ${isDark ? 'text-white' : 'text-neutral-900'}`}>
            Telegram tasdiqlamoqda…
          </p>
        </div>
      ) : (
        <button
          type="button"
          onClick={go}
          data-testid="tg-login"
          className={`w-full h-[54px] rounded-2xl font-semibold text-[15px] flex items-center
                      justify-center gap-2.5 transition active:scale-[.98] ${
            isDark
              ? 'bg-[#2AABEE] text-white hover:bg-[#3cb3f2]'
              : 'bg-[#229ED9] text-white hover:bg-[#1b8cc2]'
          }`}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M21.9 4.3c-.2-.9-1-1.6-1.9-1.8C18.2 2.2 12 2.2 12 2.2s-6.2 0-8 .3c-.9.2-1.7.9-1.9 1.8C1.8 6.1 1.8 12 1.8 12s0 5.9.3 7.7c.2.9 1 1.6 1.9 1.8 1.8.3 8 .3 8 .3s6.2 0 8-.3c.9-.2 1.7-.9 1.9-1.8.3-1.8.3-7.7.3-7.7s0-5.9-.3-7.7zM9.9 15.6V8.4l6.3 3.6-6.3 3.6z" />
          </svg>
          Telegram orqali kiring
        </button>
      )}

      {err && (
        <p className="mt-3 text-[12px] text-center text-rose-500">{err}</p>
      )}

      <p className={`mt-3 text-[11.5px] text-center leading-relaxed ${
        isDark ? 'text-neutral-500' : 'text-neutral-500'
      }`}>
        Telegram ochiladi, tasdiqlang — bu saytga qaytib keladi.
        {botId ? '' : ' (bot aniqlanmoqda…)'}
      </p>
    </div>
  );
};

export default TelegramLogin;