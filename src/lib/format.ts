/**
 * 💰 SUMMA FORMATLASH — O'ZBEK FORMATIDA
 *
 * 🔴🔴🔴 BU NIMA UCHUN MUHIM (2026-10-17, «saytda avto to'ldirish
 *    ishlamayapti, WebApp'da ishlaydi»):
 *
 *    `Number.prototype.toLocaleString()` BRAUZER TILIGA QARAB
 *    formatlaydi. Ingliz tilida (en-US) 1102 → «1,102».
 *
 *    O'zbekistonda esa VERGUL KASR BELGISI:
 *        1,102  =  1 so'm 102 tiyin   (bitta so'm!)
 *        1 102  =  1 102 so'm
 *
 *    Ya'ni saytda mijoz «1,102 UZS» deb ko'radi va bank ilovasiga
 *    aynan shu sonni kiritadi → bank 1.102 YOKI 1 102 ni tushunadi.
 *    Telegram WebApp'da esa `bot.py` dagi `fmt()` chiqadi:
 *        «1 102»  — bo'sh bilan, TO'G'RI.
 *
 *    Bu YAGONA sabab mijozni chalkashtiradi va to'lov topilmaydi.
 *
 * ✅ YECHIM: hech qaerda `toLocaleString()` ishlatilmaydi. Bu yordamchi
 *    har doim O'zbek formatida chiqadi (1 102 500) — brauzer tilidan
 *    qat'i nazar.
 */

/** 1102 → «1 102»  ·  1000000 → «1 000 000» */
export function fmtUzs(n: number | string | null | undefined): string {
  const v = Number(n);
  if (!Number.isFinite(v)) return '0';
  const neg = v < 0;
  const s = Math.abs(Math.trunc(v)).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  return neg ? `-${s}` : s;
}

/**
 * 🏦 BANK KO'RINISHIDAGI SUMMA — «1 102,00 UZS»
 *
 * Bank xabari aynan shu ko'rinishda keladi (`1.025,00 UZS`), shuning
 * uchun mijozga ko'rsatiladigan summa ham xuddi shu bo'lishi kerak —
 * mijoz solishtirib tekshirsin.
 */
export function fmtBank(n: number | string | null | undefined): string {
  return fmtUzs(n) + ',00';
}