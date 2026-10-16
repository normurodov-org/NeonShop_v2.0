/**
 * 🗺 YO'LLAR (routing) — saytning har bir xizmati o'z manziliga ega.
 *
 * 🔴 NIMA UCHUN?
 *     Avval barcha xizmatlar bitta sahifada `currentTab` state orqali
 *     ochilardi. Mijoz `https://…/nft` ni Telegram'da saqlab qo'yib,
 *     ertaga ochsa — doim **bosh sahifa** chiqardi (yo'l butunlay
 *     ko'rinmasdi). Bot esa WebApp'ga `?tab=buy&sub=nft` havolasi bilan
 *     kirishi mumkin edi.
 *
 * ✅ ENDI HAQIQIY YO'LLAR:
 *     /              Bosh sahifa
 *     /topup         To'ldirish
 *     /buy           Xarid → Stars
 *     /stars         Xarid → Telegram Stars
 *     /premium       Xarid → Telegram Premium
 *     /gifts         Xarid → Giftlar
 *     /nft           Xarid → NFT ijarasi
 *     /nftrent       /nft ning qisqa alias'i
 *     /ranking       Reyting
 *     /profile       Profil (Mening hisobim)
 *     /admin         Admin panel
 *
 * 📌 ALIAS'LAR (`/nftrent`, `/stars` …)
 *     Bot xabarlari va eski havolalar uchun. Ular `ALIASES` orqali
 *     `CANONICAL` ga qaytariladi — ya'ni `/nftrent` ochilsa, manzil
 *     darhol `/nft` bo'lib qoladi. Bu:
 *       • `location.pathname` har doim bir xil bo'ladi (testlash),
 *       • mijoz brauzer tarixida bir xil sahifani ko'rmaydi,
 *       • "qaysi yo'l?" savoliga bitta javob bor.
 */

/** Navigatsiya darajasi (BottomNav). */
export type TabType = 'home' | 'topup' | 'buy' | 'ranking' | 'profile' | 'admin';

/** `BuyView` ichidagi kichik tab. */
export type BuySub = 'stars' | 'premium' | 'gifts' | 'nft';

export interface Route {
  tab: TabType;
  sub: BuySub | null;
}

/** Har bir tab uchun yo'l. `null` sub = kichik tab yo'q. */
export const TAB_PATHS: Record<TabType, string> = {
  home: '/',
  topup: '/topup',
  buy: '/buy',
  ranking: '/ranking',
  profile: '/profile',
  admin: '/admin',
};

/** Kichik tab uchun yo'llar. */
export const SUB_PATHS: Record<BuySub, string> = {
  stars: '/stars',
  premium: '/premium',
  gifts: '/gifts',
  nft: '/nft',
};

/**
 * 🔴 ALIAS'LAR — qisqa/eskari nomlar.
 * Chapga: foydalanuvchi shu yo'lni yozsa, o'ng tomondagi
 * `CANONICAL` yo'lga yo'naltiriladi.
 */
const ALIASES: Record<string, Route> = {
  '': { tab: 'home', sub: null },
  '/': { tab: 'home', sub: null },
  '/home': { tab: 'home', sub: null },
  '/index': { tab: 'home', sub: null },

  '/topup': { tab: 'topup', sub: null },
  '/balance': { tab: 'topup', sub: null },
  '/replenish': { tab: 'topup', sub: null },

  '/buy': { tab: 'buy', sub: 'stars' },
  '/shop': { tab: 'buy', sub: 'stars' },

  '/stars': { tab: 'buy', sub: 'stars' },
  '/star': { tab: 'buy', sub: 'stars' },

  '/premium': { tab: 'buy', sub: 'premium' },

  '/gifts': { tab: 'buy', sub: 'gifts' },
  '/gift': { tab: 'buy', sub: 'gifts' },

  '/nft': { tab: 'buy', sub: 'nft' },
  '/nftrent': { tab: 'buy', sub: 'nft' },
  '/nft-rent': { tab: 'buy', sub: 'nft' },
  '/rent': { tab: 'buy', sub: 'nft' },

  '/ranking': { tab: 'ranking', sub: null },
  '/rating': { tab: 'ranking', sub: null },
  '/top': { tab: 'ranking', sub: null },

  '/profile': { tab: 'profile', sub: null },
  '/account': { tab: 'profile', sub: null },
  '/me': { tab: 'profile', sub: null },

  '/admin': { tab: 'admin', sub: null },
};

/**
 * Yo'lni `{ tab, sub }` ga aylantiradi.
 * Noma'lum yo'l → bosh sahifa (404 ko'rsatmaymiz — Telegram WebApp
 * da noto'g'ri havola mijozni chalkashtiradi).
 */
export function pathToRoute(pathname: string): Route {
  const raw = String(pathname || '/').trim();
  // Soz oxiridagi `/` va `index.html` ni tashlaymiz
  let p = raw.replace(/\/+$/, '') || '/';
  p = p.replace(/\/index\.html$/i, '') || '/';
  // Katta-kichik harfni tekislaymiz (URL kichik bo'lishi shart emas)
  p = p.toLowerCase();

  return ALIASES[p] ? { ...ALIASES[p] } : { tab: 'home', sub: null };
}

/**
 * `{ tab, sub }` ni YO'LGA aylantiradi.
 *
 * 📌 `buy` tabi uchun kichik tab yo'li beriladi (`/nft`), aks holda
 * `/buy` (Stars). Sabab: `buy` o'zida `stars` sub-tabini o'z ichida
 * oladi, lekin uning o'z yo'li ham kerak.
 */
export function routeToPath(tab: TabType, sub?: BuySub | null): string {
  if (tab === 'buy') {
    const s = (sub || 'stars') as BuySub;
    return SUB_PATHS[s] || SUB_PATHS.stars;
  }
  return TAB_PATHS[tab] || '/';
}

/**
 * 🔴 ESKI HAVOLALAR UCHUN: `?tab=…&sub=…` ni o'qib, yo'lga o'giradi.
 *
 * 📌 Bot (va eski versiyalar) `?tab=buy&sub=nft` ishlatadi. Bu
 * funksiya shuni kiritishda ham, qaytadan URL'ga yozganda ham
 * ishlatiladi — shu bilan **bir manba** qoladi va ikkala usul ham
 * ishlaydi (eski havolalar buzilmaydi).
 */
export function queryToRoute(search: string): Route | null {
  try {
    const p = new URLSearchParams(String(search || '').replace(/^\?/, ''));
    const tab = (p.get('tab') || '').trim().toLowerCase();
    const sub = (p.get('sub') || '').trim().toLowerCase();
    if (!tab && !sub) return null;

    if (sub && (!tab || tab === 'buy')) {
      if (sub in SUB_PATHS) return { tab: 'buy', sub: sub as BuySub };
    }
    if (tab in TAB_PATHS) {
      return {
        tab: tab as TabType,
        sub: tab === 'buy' ? 'stars' : null,
      };
    }
    return null;
  } catch {
    return null;
  }
}

/** `?tab=` va `?sub=` ni URL dan olib tashlaydi (marker tozalash). */
export function stripQuery(url: string): string {
  try {
    const u = new URL(url, 'http://localhost');
    u.searchParams.delete('tab');
    u.searchParams.delete('sub');
    const qs = u.searchParams.toString();
    return u.pathname + (qs ? `?${qs}` : '') + u.hash;
  } catch {
    return url;
  }
}