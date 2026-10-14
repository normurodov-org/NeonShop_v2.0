/**
 * ⏳ Bot nomi kelmaganda ko'rsatiladigan vaqtdan o'tgan holat.
 *
 * 🔴 NIMA UCHUN?
 * Telegram Login Widget bot NOMINI talab qiladi
 * (`data-telegram-login="..."`). Server nomni `getMe` orqali oladi —
 * lekin tarmoq uzilsa yoki bot hali ishga tushmagan bo'lsa, bo'sh
 * qoladi. Foydalanuvchi shunda faqat «Bot nomi yuklanmoqda…» deb
 * ko'radi va hech narsa qilmaydi — "ishlamadi" taassuroti.
 *
 * Yechim:
 *   1) 4 soniya kutamiz (server javob bermasligi mumkin)
 *   2) keyin aniq tushuntirish + «Qayta urinish»
 *   3) pastda har doim «Botga o'tish» havolasi (yuqorida bor)
 */
import React, { useEffect, useState } from 'react';

interface Props {
  isDark: boolean;
  onRetry: () => void;
}

export const BotNameWait: React.FC<Props> = ({ isDark, onRetry }) => {
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setSlow(true), 4000);
    return () => clearTimeout(t);
  }, []);

  return (
    <div className="py-2 text-center">
      <p
        className={`text-[12px] ${
          slow ? 'text-amber-500' : isDark ? 'text-neutral-500' : 'text-neutral-500'
        }`}
      >
        {slow ? (
          <>
            <b>Tugmani yuklab bo&apos;lmadi.</b>
            <br />
            <span className="text-[11px] opacity-80">
              Bot hali ishga tushmagan bo‗lishi mumkin — bir daqiqa
              kutub, qayta urinib ko‗ring.
            </span>
          </>
        ) : (
          'Bot nomi yuklanmoqda\u2026'
        )}
      </p>
      {slow && (
        <button
          onClick={onRetry}
          className={`mt-3 px-4 py-2 rounded-full text-[12px] font-semibold apple-spring cursor-pointer ${
            isDark
              ? 'liquid-glass-pill text-neutral-300'
              : 'liquid-glass-pill text-neutral-700'
          }`}
        >
          \U0001F504 Qayta urinish
        </button>
      )}
    </div>
  );
};

export default BotNameWait;