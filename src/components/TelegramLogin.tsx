/**
 * 🔐 Telegram orqali kirish.
 *
 * 🍎 ASOSIY YO'L — Telegram ILOVASI orqali (deep link).
 *
 * 🔴🔴 NIMA UCHUN BU BIRINCHI O'RINDA?
 *    `oauth.telegram.org/auth` (Login Widget va OAuth) — brauzerda TAB
 *    ichida ochilganda Telegram uni O'ZI YOPADI (ichida «Bot domain
 *    invalid» yoki oddiy «Continue» ekranni ko'rsatib, `window.close()`
 *    chaqiradi). Natijada mijoz «tab ochilib yopildi» deb ko'radi,
 *    sayt esa «kutilayotgan» holatda qoladi. Bu Telegram'ning ichki
 *    mexanizmi — biz skriptni o'zgartira olmaymiz.
 *
 *    Deep link esa TO'G'RI ilovani ochadi:
 *      `t.me/<bot>?start=<kod>` → Telegram ilovasi → «Start» →
 *      bot.py kodni yozadi → sessiya.
 *    Bu domen ro'yxatidan ham qat'i nazar, popup ham yo'q.
 *
 * 📌 Ikkala yo'l ham Telegram'ning RASMIY mexanizmlari. Ikkalasi ham
 *    ishlaydi, lekin birinchisi ishonchli — shuning uchun u asosiy.
 *
 * 🟡 IKKINCHI YO'L — `oauth.telegram.org` (web orqali). Sarlavha ostida.
 *
 * 🔒🔒 ASOSIY QO'LDA: **jamiy hech qachon ko'chmaydi va yopilmaydi.**
 *    Telegram har doim YANGI oynada ochiladi. Natija `localStorage`
 *    orqali uzatiladi (origin bo'yicha umumiy) — shuning uchun biz
 *    `postMessage` ga bog'liq emasmiz va COOP ham muammo qilmaydi.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { setSessionToken, sessionToken } from '../lib/tgAuth';

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

  const [wait, setWait] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  /** Popup bloklanganda ko'rsatiladigan havola (jamiy tab qoladi). */
  const [fallbackUrl, setFallbackUrl] = useState<string | null>(null);

  const pollRef = useRef<number | undefined>(undefined);
  const beforeRef = useRef<string>('');

  /* ──────────────────────────────────────────────────────────────────────
   * 🔒 Jamiy tab QOLADI. Natija kelishi uchun IKKITA yo'l birga tekshiriladi.
   * 🔴🔴 IKKITA YO'L BIRDA KUTILADI (chunki ular turli oynadan keladi):
   *
   *   1) `/api/auth/telegram/status?code=…` — DEEP LINK uchun.
   *      `t.me` oynasi saytimizga QAYTMAYDI, shuning uchun tokeni
   *      faqat server orqali olish mumkin: bot.py kodni yozadi →
   *      shu so'rov `token` beradi → biz `localStorage` ga yozamiz.
   *      🔴 BU YO'L BO'LMASA deep link umuman ISHLAMAYDI.
   *
   *   2) `localStorage` — `oauth.telegram.org` uchun.
   *      U sahifa `return_to` orqali saytimizga QAYTADI, u yerda
   *      boshqa oyna `setSessionToken()` qiladi — biz shuni sezamiz.
   *
   * @param code deep link kodi (yo'q bo'lsa faqat `localStorage` tekshiriladi)
   */
  const waitForResult = useCallback((code?: string) => {
    if (pollRef.current) window.clearInterval(pollRef.current);
    beforeRef.current = sessionToken();
    let checking = false;

    pollRef.current = window.setInterval(() => {
      // 1) 🔴 Boshqa oyna sessiyani yozganmi? (OAuth qaytishi)
      const now = sessionToken();
      if (now && now !== beforeRef.current) {
        if (pollRef.current) window.clearInterval(pollRef.current);
        setWait(false);
        setFallbackUrl(null);
        cbRef.current.onSuccess();
        return;
      }

      // 2) 🔴 Bot kodni tasdiqlaganmi? (deep link)
      if (!code || checking) return;
      checking = true;
      fetch(`/api/auth/telegram/status?code=${encodeURIComponent(code)}`)
        .then((r) => r.json())
        .then((j: any) => {
          checking = false;
          if (!j?.ok || j.status !== 'ok' || !j.token) return;
          if (pollRef.current) window.clearInterval(pollRef.current);
          setSessionToken(j.token);   // 🔴 localStorage ga yozamiz
          setWait(false);
          setFallbackUrl(null);
          cbRef.current.onSuccess();
        })
        .catch(() => { checking = false; });
    }, 1200);
  }, []);

  const stopWaiting = useCallback(() => {
    if (pollRef.current) window.clearInterval(pollRef.current);
    setWait(false);
    setFallbackUrl(null);
  }, []);

  /* ──────────────────────────────────────────────────────────────────────
   * 🛡️ Oynani SINXRON ochish.
   *
   * 🔴🔴 NIMA UCHUN?
   *   `window.open` faqat foydalanuvchi hodisasi sifatida, ya'ni
   *   `await` YO'Q holda ishlaydi. Aks holda brauzer uni «popup»
   *   deb hisoblab bloklaydi. Shuning uchun:
   *      1) bo'sh oyna HEMMASOH AVDAN ochiladi (sinxron),
   *      2) keyin server javobiga qarab `location` ga Telegram
   *         havolasi yoziladi.
   *   Natijada kodingiz async bo'lsa ham popup bloklanmaydi.
   * ──────────────────────────────────────────────────────────────────── */
  const openBlank = (): Window | null => {
    try {
      return window.open('', '_blank');
    } catch {
      return null;
    }
  };

  const pointWindow = (w: Window | null, url: string): boolean => {
    if (w) {
      try { w.location.href = url; return true; } catch { /* ignore */ }
    }
    // 🔴 Popup bloklandi — jamiy tab QOLADI, havola ko'rsatiladi
    setFallbackUrl(url);
    return false;
  };

  /** 🔴 IZOHLANGAN NATIJANI serverga yuboradi. */
  const submit = useCallback(async (data: string) => {
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
        setErr(j?.error || 'Telegram tasdiqlamadi');
        cbRef.current.onError?.(j?.error || 'Telegram tasdiqlamadi');
      }
    } catch (e: any) {
      setErr(e?.message || 'Tarmoq xatosi');
      cbRef.current.onError?.(e?.message || 'Tarmoq xatosi');
    }
  }, []);

  /* 🔴 Telegram'dan QAYTIB KELGAN bo'lsak — natijani darhol olamiz.
   *    (Yangi oynada Telegram shu sahifani `?tg=1` bilan ochadi.) */
  useEffect(() => {
    const data = readTelegramAuthResult();
    const cameBack = new URLSearchParams(location.search).get('tg') === '1';
    if (cameBack) {
      const u = new URL(location.href);
      u.searchParams.delete('tg');
      window.history.replaceState({}, '', u.pathname + u.search + u.hash);
    }
    if (data) { submit(data); return; }
    if (cameBack) setErr('Telegram tasdiqlamadi. Qayta urinib ko‘ring.');
  }, [submit]);

  useEffect(() => () => {
    if (pollRef.current) window.clearInterval(pollRef.current);
  }, []);

  /** 🌐 YO'L 1 — Telegram ILOVASI (deep link). ASOSIY.
   *
   *  📌 Oqim:
   *      1. server bir martalik kod beradi (`web_<48hex>`)
   *      2. `t.me/<bot>?start=<kod>` → Telegram ILOVASI (yangi oynada)
   *      3. mijoz «Start» ni bosadi
   *      4. bot.py kodni `*_login_codes.json` ga yozadi
   *      5. biz sessiya tokenining paydo bo'lishini kutamiz
   *
   *  🔴 Bu yo'l domen ro'yxatidan ham, popup'dan ham qat'i nazar. */
  const deepStart = useCallback(async () => {
    setErr(null);
    setFallbackUrl(null);
    // 🛡️ Bo'sh oynani AVVAL ochamiz (sinxron → bloklanmaydi)
    const w = openBlank();
    setWait(true);
    try {
      const res = await fetch('/api/auth/telegram/start', { method: 'POST' });
      const j = await res.json().catch(() => ({}));
      if (!res.ok || !j?.telegram_url) {
        try { w?.close(); } catch { /* ignore */ }
        setWait(false);
        setErr(j?.error || 'Serverga ulanib bo‘lmadi');
        return;
      }
      pointWindow(w, j.telegram_url);
      waitForResult(j.code);   // 🔴 kodni server orqali tekshiramiz
    } catch (e: any) {
      try { w?.close(); } catch { /* ignore */ }
      setWait(false);
      setErr(e?.message || 'Tarmoq xatosi');
    }
  }, [waitForResult]);

  /** 📕 YO'L 2 — Telegram web (`oauth.telegram.org`). Zaxira.
   *
   *  🔴 Bu sahifa brauzerda TAB ichida ochilganda Telegram uni o'zini
   *     YOPADI. Shuning uchun biz uni ham YANGI OYNADA ochamiz —
   *     jamiy tab hech qachon yopilmaydi. Telegram `return_to` orqali
   *     saytga `tgAuthResult` bilan qaytadi, ilova sessiyani yoza oladi
   *     va biz `localStorage` orqali sezamiz. */
  const oauthStart = useCallback(() => {
    if (!botId) { setErr('Bot aniqlanmadi'); return; }
    setErr(null);
    setFallbackUrl(null);
    const url = telegramAuthUrl(botId);
    const w = openBlank();
    if (!pointWindow(w, url)) { setWait(false); return; }
    setWait(true);
    waitForResult();
  }, [botId, waitForResult]);

  const card = (children: React.ReactNode) => (
    <div className={`rounded-2xl p-4 text-center ${
      isDark ? 'bg-white/[0.06] border border-white/10' : 'bg-neutral-100 border border-neutral-200'
    }`}>{children}</div>
  );

  return (
    <div className="mt-7 w-full">
      {wait ? (
        /* 🔍 Kutish — jamiy tab joyida, hech narsa yopilmaydi */
        card(
          <>
            <div className={`mx-auto mb-3 h-7 w-7 rounded-full border-[3px] border-t-transparent animate-spin ${
              isDark ? 'border-[#2AABEE]' : 'border-[#229ED9]'
            }`} />
            <p className={`text-[13px] font-semibold ${isDark ? 'text-white' : 'text-neutral-900'}`}>
              Telegram ilovasida «Start» ni bosing
            </p>
            <p className={`mt-1.5 text-[12px] leading-relaxed ${
              isDark ? 'text-neutral-400' : 'text-neutral-600'
            }`}>
              Telegram <b>yangi oynada</b> ochildi. Unda <b>Start</b> ni bosing —
              bu sayt avtomatik kiradi. Oynani yopishingiz mumkin.
            </p>
            <button
              type="button"
              onClick={stopWaiting}
              className={`mt-2.5 text-[12px] underline underline-offset-2 ${
                isDark ? 'text-neutral-400' : 'text-neutral-600'
              }`}
            >
              Bekor qilish
            </button>
          </>
        )
      ) : err ? (
        card(
          <>
            <p className="text-[12.5px] text-rose-500">{err}</p>
            <button
              type="button"
              onClick={deepStart}
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
          onClick={deepStart}
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

      {/* 🔴 Popup bloklanganda — jamiy tab QOLADI, havola ko'rsatiladi */}
      {fallbackUrl && (
        <p className="mt-2 text-[12px] text-center leading-relaxed">
          <span className={isDark ? 'text-neutral-400' : 'text-neutral-600'}>
            Oyna bloklandi. Qo‘lda oching:{' '}
          </span>
          <a
            href={fallbackUrl}
            target="_blank"
            rel="noopener noreferrer"
            data-testid="tg-login-fallback"
            className="underline underline-offset-2 break-all"
          >
            {fallbackUrl}
          </a>
        </p>
      )}

      {!wait && !err && (
        <>
          <p className="mt-3 text-[11.5px] text-center leading-relaxed text-neutral-500">
            Telegram <b>yangi oynada</b> ochiladi — bu sayt yopilmaydi.
          </p>

          {/* 📕 ZAXIRA: Telegram web orqali (`oauth.telegram.org`).

              📐 Bu sahifa brauzerda TAB ichida ochilganda Telegram uni
              o'zini YOPADI — shuning uchun biz uni ham yangi oynada
              ochamiz. Bot egasi `/setdomain` orqali domenni ro'yxatga
              olgandan keyin to'g'ri ishlaydi. */}
          <button
            type="button"
            onClick={oauthStart}
            data-testid="tg-login-oauth"
            className={`mt-2 w-full text-[12px] underline underline-offset-2 ${
              isDark ? 'text-neutral-400 hover:text-neutral-300' : 'text-neutral-600 hover:text-neutral-500'
            }`}
          >
            Telegram web orqali kirish
          </button>
        </>
      )}
    </div>
  );
};

export default TelegramLogin;
