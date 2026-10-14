/**
 * 🔐 Telegram API so'rovlari uchun yagona yordamchi.
 *
 * NIMA UCHUN?
 * Server foydalanuvchi id'sini faqat ISHONCHLI manbadan oladi:
 *   1) `X-Telegram-Init-Data` — Telegram WebApp imzosi
 *      (bot ichida ochilganda: `t.me/bot/app`)
 *   2) `X-Session-Token` — Telegram Login Widget orqali berilgan
 *      sessiya (BRAUZERDA ochilganda)
 * Boshqa manbalar (`x-telegram-user-id`, `?uid=`) ishonchsiz.
 *
 * 🔴 Ilgari har bir komponent `x-telegram-user-id` yuborardi yoki
 * umuman yubormardi. Natijada:
 *   • yubormagan so'rovlar -> server ADMIN sifatida ishlardi
 *   • "O'zimga", "To'ldirish", "Reyting" va h.k. noto'g'ri ishlar edi
 *
 * Endi barcha so'rovlar shu yordamchidan o'tadi — imzo/sessiya har
 * doim birga yuboriladi va hech qayerda yo'qolmaydi.
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

// ---------------------------------------------------------------------------
// 🖥 BRAZER UCHUN SESSIYA (Telegram Login Widget)
// ---------------------------------------------------------------------------
const SESSION_KEY = 'neon_session_token';

/** Ilova Telegram ichida ochilganmi? (brauzerda emas) */
export function isInsideTelegram(): boolean {
  try {
    const w = window as any;
    return Boolean(w?.Telegram?.WebApp?.initData || w?.Telegram?.WebApp?.initDataUnsafe?.user);
  } catch {
    return false;
  }
}

export function sessionToken(): string {
  try {
    return window.localStorage.getItem(SESSION_KEY) || '';
  } catch {
    return '';
  }
}

export function setSessionToken(token: string): void {
  try {
    if (token) window.localStorage.setItem(SESSION_KEY, token);
    else window.localStorage.removeItem(SESSION_KEY);
  } catch {
    /* private mode — sessiya saqlanmaydi */
  }
}

/**
 * 🛑️ Chiqish (Log out).
 *
 * 🔴 NIMA UCHUN `setSessionToken('')` EMAS? Chunki u shunchaki
 *    `localStorage` dan o'chiredi. Sessiya serverda (`*_sessions.json`)
 *    ham qoladi — token o'g'irlangan bo'lsa, odam boshqa qurilmadan
 *    foydalanib tura olardi. Shuning uchun avval serverga xabar
 *    beramiz, keyin o'chiramiz.
 */
export async function logout(): Promise<void> {
  const token = sessionToken();
  try {
    if (token) {
      await fetch('/api/auth/logout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Session-Token': token },
      });
    }
  } catch {
    /* tarmoq yo'q — mahalliy tozalash baribir ishlaydi */
  }
  setSessionToken('');
}

/** Faqat `initData` + sessiya header'lar (GET uchun). */
export function tgHeadersGet(extra?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = {
    'X-Telegram-Init-Data': telegramInitData(),
  };
  const t = sessionToken();
  if (t) headers['X-Session-Token'] = t;
  return { ...headers, ...(extra || {}) };
}

/** `tgHeadersGet` + JSON `Content-Type` (POST/PUT uchun). */
export function tgHeaders(extra?: Record<string, string>): Record<string, string> {
  return { 'Content-Type': 'application/json', ...tgHeadersGet(extra) };
}