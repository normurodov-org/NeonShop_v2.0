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
import { setSessionToken, sessionToken } from '../lib/tgAuth';

interface Props {
  botUsername: string;
  botId: number;
  isDark: boolean;
  onSuccess: () => void;
  onError?: (msg: string) => void;
}

const TG_AUTH_ORIGIN = 'https://oauth.telegram.org';

/** Telegram oynasini kutish vaqti (ms) */
const OPEN_TIMEOUT_MS = 3 * 60 * 1000;

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
        // 🛑️ Bu OYNA Telegram'dan qaytgan — endi o'zini yopamiz.
        //    Asl tab oyna boshqaruvini oldida turadi.
        try { if (window.opener) window.close(); } catch { /* ignore */ }
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

  /** 📱 Telegram oynasini ochib, undan natijani KUTAMIZ.

   *  🔴️ NIMA UCHUN YANGI OYNA (eski yo'l esa bu edi):
   *    `window.location.href = oauth...` bilan ASL TAB Telegram'ga ketar
   *    edi — mijoz u yerga kirib, telefon raqamini kiritib, SMS kodini
   *    yozib, keyin saytga QAYTIB kelishi kerak edi. Ko'pchilik bu
   *    oynani yopib tashlab, «kirish ishlamadi» deb o'ylardi.
   *
   *  ✅ YANGI: asl tab HECH QACHON ko'chmaydi. Telegram yangi oynada
   *    ochiladi, tasdiqlangach o'sha oyna `return_to` ga qaytadi — ya'ni
   *    yana ham ilova — `#tgAuthResult` ni o'qiydi, sessiyani yozadi va
   *    o'zini yopadi. Asl tab esa `localStorage` ni kuzatib, kirish
   *  tugallanishini darhol ko'radi.
   *
   *  🔒 `localStorage` origin bo'yicha UMUMIY bo'lgani uchun popup
   *  qanday ochilishidan qat'i nazar bu usul ishlaydi (COOP ham ahamiyat
   *  yo'q — biz `postMessage` ga bog'liq emasmiz). */
  const popupRef = useRef<Window | null>(null);
  const pollRef = useRef<number | undefined>(undefined);

  const cleanupPoll = () => {
    if (pollRef.current) window.clearInterval(pollRef.current);
    pollRef.current = undefined;
  };

  useEffect(() => () => cleanupPoll(), []);

  const go = () => {
    if (!botId) { setErr('Bot aniqlanmadi'); return; }
    const before = sessionToken();
    const url = telegramAuthUrl(botId);

    // 📴 YANGI OYNA — asl tab joyida qoladi
    const w = window.open(
      url, 'tg_login',
      'width=560,height=640,left=' + Math.max(0, (screen.width - 560) / 2)
      + ',top=' + Math.max(0, (screen.height - 640) / 2) + ',menubar=0,toolbar=0'
    );
    popupRef.current = w;

    if (!w) {
      // 🔴 Popup bloklangan (brauzer so'rogan bo'lishi mumkin).
      //    Bunday holatda ASL TABni ko'chirish yaxshiroq — biror narsa
      //    qilish kerak.
      setErr('Oyna bloklandi — asl tabda ochilmoqda…');
      window.location.href = url;
      return;
    }

    setBusy(true);
    setErr(null);
    cleanupPoll();
    const startedAt = Date.now();
    // 🔍 `localStorage` ni kuzatamiz — sessiya yozilishi bilan
    pollRef.current = window.setInterval(() => {
      const now = sessionToken();
      if (now && now !== before) {
        cleanupPoll();
        setBusy(false);
        cbRef.current.onSuccess();
      }
      // 🔴 `popup.closed` ISHLATILMAYDI — u ISHONCHSIZ.
      //
      //    Popup boshqa ORIGIN dan ochilganda brauzerlar `WindowProxy`
      //    ni kesib qoʼydi (`Cross-Origin-Opener-Policy` yoki uning
      //    tabiiy ta'siri natijasida) va `.closed` DARHOL `true` qaytaradi —
      //    foydalanuvchi hech narsa qilmagan holda. Natija: mijoz tugmani
      //    bosadi, oyna ochiladi, va biz «bekor qilindi» deb xabar
      //    beramiz — bu 💨 RASMDAGI xatolik.
      //
      //    🟢 Endi FAQAT `localStorage` ga ishonamiz (origin boʼyicha
      //    umumiy, 100% ishonchli) va VAQT bilan chegaralaymiz.
      const waited = Date.now() - startedAt;
      if (waited > OPEN_TIMEOUT_MS) {
        cleanupPoll();
        setBusy(false);
        setErr('Vaqt tugadi. Telegram oynasida tasdiqlanmadingiz.');
      }
    }, 900);
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
            Telegram oynasida tasdiqlang
          </p>
          {/* 📖 Nima qilish kerakligini ANIQ aytamiz — mijoz
              nima qilishini bilmasligi kerak emas. */}
          <p className={`mt-1.5 text-[12px] leading-relaxed ${isDark ? 'text-neutral-400' : 'text-neutral-600'}`}>
            Ochilgan kichik oynada Telegram <b>Continue</b> tugmasini bosing.
            Tugilgach sayt avtomatik ochiladi.
          </p>
          {/* 🛑️ Ixtiyoriy: mijoz Telegram oynasini yopib
              qoʼysa, u hech qachon «kutilayotgan» holatda qolmasin. */}
          <button
            type="button"
            onClick={() => {
              cleanupPoll();
              try { popupRef.current?.close(); } catch { /* ignore */ }
              setBusy(false);
            }}
            className={`mt-2.5 text-[12px] underline underline-offset-2 ${
              isDark ? 'text-neutral-400' : 'text-neutral-600'
            }`}
          >
            Bekor qilish
          </button>
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
          {/* 🔴 RASMIY Telegram logotipi (qog'oz-nokurasi).
              Avvalgi path «video/play» belgisiga oʼhardi — mijoz
              rasmda shuni koʼrdi. */}
          <svg width="19" height="19" viewBox="0 0 24 24" fill="currentColor"
               aria-hidden="true" focusable="false">
            <path d="M9.78 18.65l.28-4.23 7.68-6.92c.34-.31-.07-.46-.52-.19L7.74 13.3 3.64 12c-.88-.25-.89-.86.2-1.3l15.97-6.16c.73-.33 1.43.18 1.15 1.3l-2.72 12.81c-.19.91-.74 1.13-1.5.71L12.6 16.3l-1.99 1.93c-.23.23-.42.42-.83.42z" />
          </svg>
          Telegram orqali kiring
        </button>
      )}

      {err && (
        <div className="mt-3 text-center">
          <p className="text-[12px] text-rose-500">{err}</p>
          <button
            type="button"
            onClick={go}
            data-testid="tg-login-retry"
            className={`mt-2 h-9 w-full rounded-xl text-[12.5px] font-semibold text-white
                        transition active:scale-[.98] ${
              isDark ? 'bg-[#2AABEE] hover:bg-[#3cb3f2]' : 'bg-[#229ED9] hover:bg-[#1b8cc2]'
            }`}
          >
            Qayta urinish
          </button>
        </div>
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