/**
 * 🔐 Telegram API so'rovlari uchun yagona yordamchi.
 *
 * NIMA UCHUN?
 * Server foydalanuvchi id'sini FAQAT `X-Telegram-Init-Data`
 * (Telegram tomonidan imzolangan satr) dan oladi va uni BOT_TOKEN
 * bilan tekshiradi. Boshqa manbalar (`x-telegram-user-id`, `?uid=`)
 * ishonchsiz.
 *
 * 🔴 Ilgari har bir komponent `x-telegram-user-id` yuborardi yoki
 * umuman yubormardi. Natijada:
 *   • yubormagan so'rovlar -> server ADMIN sifatida ishlardi
 *   • "O'zimga", "To'ldirish", "Reyting" va h.k. noto'g'ri ishlar edi
 *
 * Endi barcha so'rovlar shu yordamchidan o'tadi — imzo har doim
 * birga yuboriladi va hech qayerda yo'qolmaydi.
 */

let cachedInitData: string = '';

/** Telegram `initData` ni bir marta o'qiab, keshlaydi. */
export function telegramInitData(): string {
  if (cachedInitData) return cachedInitData;
  try {
    const w = window as any;
    cachedInitData =
      w?.Telegram?.WebApp?.initData ||
      (document.querySelector('script[data-webapp-initdata]') as any)?.textContent ||
      '';
  } catch {
    cachedInitData = '';
  }
  return cachedInitData;
}

/** Faqat `initData` header'li to'liq header'lar. */
export function tgHeaders(extra?: Record<string, string>): Record<string, string> {
  return {
    'Content-Type': 'application/json',
    'X-Telegram-Init-Data': telegramInitData(),
    ...(extra || {}),
  };
}

/** GET uchun (Content-Type kerak emas). */
export function tgHeadersGet(extra?: Record<string, string>): Record<string, string> {
  return {
    'X-Telegram-Init-Data': telegramInitData(),
    ...(extra || {}),
  };
}