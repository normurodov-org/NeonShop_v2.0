/**
 * 🔐 Telegram orqali kirish — Telegram'ning RASMIY OAuth sahifasi.
 *
 * 🔴🔴 NIMA UCHUN BIR TABDA (popup/tab emas)
 *
 * «Tugmani bosganimda yangi tab ochilib birdaniga yopilib qolyapti» —
 * bu `window.open` ning natijasi: brauzer Telegram sahifasini **tab**
 * sifatida ochadi, Telegram esa uni (popup deb hisoblab) yopadi. Natijada
 * mijoz hech narsa ko'rmaydi, sayt esa «kutilayotgan» holatda qoladi.
 *
 * ✅ YECHIM: ikkinchi tab umuman yo'q. Asl tab o'zi Telegram'ga boradi:
 *
 *     1. https://oauth.telegram.org/auth?bot_id=…&origin=…&return_to=…
 *     2. Mijoz Telegram'da tasdiqlaydi
 *     3. Telegram `return_to#tgAuthResult=<base64url>` ga QAYTADI —
 *        ya'ni yana shu saytga, `#tgAuthResult` bilan
 *     4. 🔴 Bu sahifada `readTelegramAuthResult()` natijani oladi,
 *        `/api/auth/telegram` ga yuboradi va sessiya saqlaydi
 *     5. Sahifa yangilanadi — mijoz ASOSIY SAHIFADA
 *
 * 💡 Agar Telegram tasdiqlamasdan qaytarsa (`#tgAuthResult` yo'q),
 *    bu sahifa «Telegram ruxsat bermadi» deb aniq xabar beradi —
 *    jimgina qolmaydi.
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
 * 📌 FORMAT: base64url(JSON) → `{ id, first_name, username, photo_url,
 *    auth_date, hash }`.
 *
 * 📌 Natija serverga `k=v&k=v` ko'rinishida YUBORILADI — chunki server
 *    `parseInitData` ishlatadi (buzilgan query string). `k=v\n` formatida
 *    yuborsak server «hash yo'q» deydi.
 */
export function readTelegramAuthResult(): string | null {
  const m = location.hash.match(/[#?&]tgAuthResult=([A-Za-z0-9\-_=]*)$/);
  if (!m || !m[1]) return null;
  // 🔴 Hash darhol tozalanadi — aks holda sahifa yangilanganda bir xil
  //    (eskirgan) natija yana keladi
  location.hash = location.hash.replace(/[#?&]tgAuthResult=[A-Za-z0-9\-_=]*$/, '');
  try {
    let b64 = m[1].replace(/-/g, '+').replace(/_/g, '/');
    const pad = b64.length % 4;
    if (pad > 1) b64 += new Array(5 - pad).join('=');
    const obj = JSON.parse(window.atob(b64));
    if (!obj || !obj.id || !obj.hash) return null;
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

/**
 * Rasmiy OAuth havolasi. `return_to` — shu sahifaning o'zi.
 *
 * 🔴📌 `?tg=1` MARKERI NIMA UCHUN:
 *   Telegram foydalanuvchiga ruxsat BERMASA, `return_to` ga `hash` OLMAS
 *   qaytadi. Agar biz «Telegram'dan qaytib keldikmi?» degan belgini
 *   bilmasak, mijoz yana bir xil kirish ekranini ko'radi va
 *   nima qilishini bilmaydi.
 *
 *   🔴 `useRef` bu uchun ISHLAMAYDI: qaytish — bu TO'LIQ sahifa
 *   qayta yuklanishi, ref esa nolga qaytadi. `sessionStorage` ham
 *   ishlaydi, lekin URL markeri eng oddiy va hamma holatda ko'rinadi.
 */
export function telegramAuthUrl(botId: number): string {
  const origin = location.origin;
  const params = new URLSearchParams({
    bot_id: String(botId),
    origin,
    return_to: `${origin}${location.pathname}?tg=1`,
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

    // 🔴 Telegram'dan QAYTIB KELMIQMI? (`?tg=1` marker orqali)
    const cameBack = new URLSearchParams(location.search).get('tg') === '1';
    if (cameBack) {
      // Marker ni darhol tozalaymiz — keyin yangilansa ham takrorlanmasin
      const u = new URL(location.href);
      u.searchParams.delete('tg');
      window.history.replaceState({}, '', u.pathname + u.search + u.hash);
    }

    if (data) { submit(data); return; }
    if (cameBack) {
      // Telegram ruxsat bermadi yoki mijoz bekor qilgan — jimgina
      // qolmaymiz, aniq xabar beramiz
      setErr('Telegram tasdiqlamadi. Qayta urinib ko‘ring.');
    }
  }, [submit]);

  const go = () => {
    if (!botId) { setErr('Bot aniqlanmadi'); return; }
    window.location.href = telegramAuthUrl(botId);
  };

  /** ⏪ Telegram sahifasidan bekor qilib qaytish. */
  const goBack = () => {
    setErr(null);
    setBusy(false);
    if (window.history.length > 1) window.history.back();
    else window.location.href = window.location.origin + window.location.pathname;
  };

  const card = (children: React.ReactNode) => (
    <div className={`rounded-2xl p-4 text-center ${
      isDark ? 'bg-white/[0.06] border border-white/10' : 'bg-neutral-100 border border-neutral-200'
    }`}>{children}</div>
  );

  return (
    <div className="mt-7 w-full">
      {busy ? (
        card(
          <>
            <div className={`mx-auto mb-3 h-7 w-7 rounded-full border-[3px] border-t-transparent animate-spin ${
              isDark ? 'border-[#2AABEE]' : 'border-[#229ED9]'
            }`} />
            <p className={`text-[13px] font-semibold ${isDark ? 'text-white' : 'text-neutral-900'}`}>
              Telegram tasdiqlamoqda…
            </p>
            <p className={`mt-1.5 text-[12px] leading-relaxed ${
              isDark ? 'text-neutral-400' : 'text-neutral-600'
            }`}>
              Bu oynada <b>Continue</b> ni bosing. Sayt avtomatik qaytadi.
            </p>
          </>
        )
      ) : err ? (
        card(
          <>
            <p className="text-[12.5px] text-rose-500">{err}</p>
            <button
              type="button"
              onClick={go}
              data-testid="tg-login-retry"
              className={`mt-2.5 h-9 w-full rounded-xl text-[12.5px] font-semibold text-white
                          transition active:scale-[.98] ${
                isDark ? 'bg-[#2AABEE] hover:bg-[#3cb3f2]' : 'bg-[#229ED9] hover:bg-[#1b8cc2]'
              }`}
            >
              Qayta urinish
            </button>
          </>
        )
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
          {/* 📖 RASMIY Telegram logotipi (qog'oz-nokurasi) */}
          <svg width="19" height="19" viewBox="0 0 24 24" fill="currentColor"
               aria-hidden="true" focusable="false">
            <path d="M9.78 18.65l.28-4.23 7.68-6.92c.34-.31-.07-.46-.52-.19L7.74 13.3 3.64 12c-.88-.25-.89-.86.2-1.3l15.97-6.16c.73-.33 1.43.18 1.15 1.3l-2.72 12.81c-.19.91-.74 1.13-1.5.71L12.6 16.3l-1.99 1.93c-.23.23-.42.42-.83.42z" />
          </svg>
          Telegram orqali kiring
        </button>
      )}

      {busy && (
        <button
          type="button"
          onClick={goBack}
          className={`mt-3 w-full text-[12px] underline underline-offset-2 ${
            isDark ? 'text-neutral-400' : 'text-neutral-600'
          }`}
        >
          Bekor qilish — saytga qaytish
        </button>
      )}

      <p className="mt-3 text-[11.5px] text-center leading-relaxed text-neutral-500">
        Telegram ochiladi, tasdiqlang — sayt avtomatik qaytib keladi.
        {botId ? '' : ' (bot aniqlanmoqda…)'}
      </p>
    </div>
  );
};

export default TelegramLogin;