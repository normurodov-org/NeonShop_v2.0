/**
 * 🗺 YO'LLAR (routing) — NeonShop'dagi HAR BIR xizmat o'z manziliga ega.
 *
 * ============================================================================
 * 🔴🔴🔴 MIJOZ SO'RAYOTGAN ASOSIY QAROR (2026-10-16)
 * ============================================================================
 *   «Har bir xizmat uchun alohida URL bo'lsin. /premium, /nft va h.k.
 *    Kichkina xizmatlar bo'lsa ham — har biriga yarat.
 *    Agar xizmat boshqa xizmat ICHIDA bo'lsa — /bo'lim/xizmat.»
 *
 * ✅ SHUNDAY QILINDI. To'liq ro'yxat:
 *
 *   /                      Bosh sahifa (Asosy)
 *   /topup                 Balansni to'ldirish
 *
 *   /stars                 ✦ Telegram Stars xaridi
 *   /premium               ✧ Telegram Premium
 *   /gifts                 🎁 Giftlar
 *   /nft                   NFT ijarasi (bosh sahifa)
 *   /nft/gifts             NFT → Sovg'alar      (NFT ichida)
 *   /nft/usernames         NFT → Username'lar    (NFT ichida)
 *   /nft/mine              NFT → Mening ijaram   (NFT ichida)
 *
 *   /ranking               Reyting (umumiy)
 *   /ranking/today         Reyting → Bugun       (Reyting ichida)
 *   /ranking/3days         Reyting → 3 kun
 *   /ranking/7days         Reyting → 7 kun
 *
 *   /profile               Profil
 *   /profile/history       Profil → Buyurtmalar tarixi
 *   /profile/referral      Profil → Referral (taklif)
 *   /profile/settings      Profil → Sozlamalar
 *
 *   /admin                 Admin panel (faqat admin)
 *   /admin/stats           Admin → Statistika
 *   /admin/balance         Admin → Balans boshqaruvi
 *   /admin/wallet          Admin → TON / USDT
 *   /admin/contest         Admin → Konkurs
 *   /admin/orders          Admin → Buyurtmalar (live)
 *
 * 📌 NIMA UCHUN SHOKLAR (ichki bo'limlar ham alohida yo'l oldi):
 *   Mijoz `https://neonshop.uz/nft` ni Telegram'da saqlab qo'yib,
 *   ertaga bosgani — doim BIR XIL oynaga ochilishi kerak. Ichki
 *   tab (`/nft/usernames`) ham xuddi shunday saqlanishi mumkin.
 *   Shu sababli `Route` — `{ tab, sections[] }` ko'rinishida: `sections`
 *   ichki -> tashqi tartibda bo'lgan yo'l BO'LAKLARI.
 */

/** Navigatsiya darajasi (BottomNav). */
export type TabType = 'home' | 'topup' | 'buy' | 'ranking' | 'profile' | 'admin';

/** `/stars`, `/premium`, `/gifts`, `/nft` — birinchi bo'lim. */
export type BuySub = 'stars' | 'premium' | 'gifts' | 'nft';
/** `/nft/gifts`, `/nft/usernames`, `/nft/mine` — NFT ichidagi tablar. */
export type NftSub = 'gifts' | 'usernames' | 'mine';
/** `/ranking/today`, … — reyting davri. `all` = yo'l bo'sh qoladi. */
export type RankingSub = 'all' | 'today' | '3days' | '7days';
/** `/profile/…` — profil ichidagi bo'limlar. `overview` = yo'l bo'sh. */
export type ProfileSub = 'overview' | 'history' | 'referral' | 'settings';
/** `/admin/…` — admin panel ichidagi bo'limlar. `stats` = yo'l bo'sh. */
export type AdminSub = 'stats' | 'balance' | 'wallet' | 'contest' | 'orders';

export interface Route {
  tab: TabType;
  /**
   * Tab ichidagi xizmatlar — ICHKI -> TASHQI tartibda.
   *   `/nft/gifts`  -> `['nft', 'gifts']`
   *   `/ranking`    -> `[]`
   * Har doim `SECTIONS[tab]` dan biror qatorga teng bo'lishi SHART
   * (bo'sh massiv ham bo'lishi mumkin).
   */
  sections: string[];
}

/**
 * Tab nomi -> yo'lning birinchi bo'lagi.
 * 📌 `home` va `buy` da bo'sh: `home` — `/`, `buy` — bo'limlari o'zi
 * yo'l (`/stars`, `/premium` …), ya'ni `/buy/stars` emas.
 */
const TAB_PREFIX: Record<TabType, string> = {
  home: '',
  topup: 'topup',
  buy: '',
  ranking: 'ranking',
  profile: 'profile',
  admin: 'admin',
};

/**
 * 🔴 RUXSAT ETILGAN bo'lim zanjirlari — bitta manba.
 * Yo'l bo'lmagan kombinatsiya (`/nft/bla`) avtomatik bosh sahifaga
 * qaytadi — xato manzil mijozni chalkashtirmasin.
 */
const SECTIONS: Record<TabType, string[][]> = {
  home: [[]],
  topup: [[]],
  buy: [
    ['stars'],
    ['premium'],
    ['gifts'],
    ['nft'],
    ['nft', 'gifts'],
    ['nft', 'usernames'],
    ['nft', 'mine'],
  ],
  ranking: [[], ['today'], ['3days'], ['7days']],
  profile: [[], ['history'], ['referral'], ['settings']],
  admin: [[], ['stats'], ['balance'], ['wallet'], ['contest'], ['orders']],
};

/** Asosiy (birinchi bo'limsiz) yo'llar — hujjat va testlar uchun. */
export const TAB_PATHS: Record<TabType, string> = {
  home: '/',
  topup: '/topup',
  buy: '/stars',
  ranking: '/ranking',
  profile: '/profile',
  admin: '/admin',
};

/** Xarid bo'limlarining o'z yo'llari (eski `SUB_PATHS` o'rniga). */
export const SUB_PATHS: Record<BuySub, string> = {
  stars: '/stars',
  premium: '/premium',
  gifts: '/gifts',
  nft: '/nft',
};

/** Barcha kanonik yo'llar — `/nft/gifts` kabi chuqur yo'llar ham. */
export const ALL_PATHS: string[] = (Object.keys(TAB_PREFIX) as TabType[]).flatMap((tab) =>
  SECTIONS[tab].map((chain) => sectionsToPath(tab, chain))
);

/**
 * 🔴 ALIAS'LAR — qisqa va eski nomlar.
 * Chapga: foydalanuvchi/bot shu yo'lni yozsa, o'ng tomondagi
 * kanonik yo'lga yo'naltiriladi.
 */
const ALIASES: Record<string, Route> = {
  // bosh sahifa
  '/home': { tab: 'home', sections: [] },
  '/index': { tab: 'home', sections: [] },
  '/bosh': { tab: 'home', sections: [] },

  // to'ldirish
  '/balance': { tab: 'topup', sections: [] },
  '/replenish': { tab: 'topup', sections: [] },
  '/tolish': { tab: 'topup', sections: [] },

  // xarid
  '/buy': { tab: 'buy', sections: ['stars'] },
  '/shop': { tab: 'buy', sections: ['stars'] },
  '/star': { tab: 'buy', sections: ['stars'] },
  '/gift': { tab: 'buy', sections: ['gifts'] },
  '/nftrent': { tab: 'buy', sections: ['nft'] },
  '/nft-rent': { tab: 'buy', sections: ['nft'] },
  '/rent': { tab: 'buy', sections: ['nft'] },
  '/nft/usernames-list': { tab: 'buy', sections: ['nft', 'usernames'] },
  '/nft/my': { tab: 'buy', sections: ['nft', 'mine'] },

  // reyting
  '/rating': { tab: 'ranking', sections: [] },
  '/top': { tab: 'ranking', sections: [] },
  '/reyting': { tab: 'ranking', sections: [] },

  // profil
  '/account': { tab: 'profile', sections: [] },
  '/me': { tab: 'profile', sections: [] },
  '/history': { tab: 'profile', sections: ['history'] },
  '/orders': { tab: 'profile', sections: ['history'] },
  '/referral': { tab: 'profile', sections: ['referral'] },
  '/taklif': { tab: 'profile', sections: ['referral'] },
  '/settings': { tab: 'profile', sections: ['settings'] },
  '/sozlamalar': { tab: 'profile', sections: ['settings'] },

  // admin
  '/admin-panel': { tab: 'admin', sections: [] },
};

/** Zanjir `SECTIONS` da ruxsat etilganmi? */
function chainAllowed(tab: TabType, chain: string[]): boolean {
  return SECTIONS[tab].some((s) => s.length === chain.length && s.every((v, i) => v === chain[i]));
}

/**
 * 🔴 `Route` ni KANONIK ko'rinishga keltiradi.
 * Masalan `{tab:'buy', sections: []}` -> `{tab:'buy', sections:['stars']}`.
 * `applyRoute` shuni ishlatadi — shunda holat ham, URL ham bir xil.
 */
export function normalizeRoute(route: Route): Route {
  if (!route) return { tab: 'home', sections: [] };
  const tab = route.tab in TAB_PREFIX ? route.tab : 'home';
  const chain = Array.isArray(route.sections) ? route.sections : [];
  return { tab, sections: chainAllowed(tab, chain) ? [...chain] : [...SECTIONS[tab][0]] };
}

/** `['nft','gifts']` -> `/nft/gifts` */
export function sectionsToPath(tab: TabType, sections: string[] = []): string {
  const parts = [TAB_PREFIX[tab], ...sections].filter(Boolean);
  return parts.length ? '/' + parts.join('/') : '/';
}

/** 🔴 ASOSIY: `Route` -> kanonik yo'l. */
export function routeToPath(route: Route): string {
  if (!route) return '/';
  const tab = route.tab in TAB_PREFIX ? route.tab : 'home';
  const chain = Array.isArray(route.sections) ? route.sections : [];
  // 🔴🔴🔴 `buy` da bo'lim BO'LMAYDI — masalan BottomNav'dagi «Xarid»
  //     tugmasi `applyRoute({tab:'buy', sections: []})` chaqiradi.
  //     `TAB_PREFIX.buy` bo'sh bo'lgani uchun bo'sh zanjir `/` ga
  //     aylanib KETARDI (bosh sahifa!). Endi ruxsat etilmagan zanjir
  //     bo'lsa, tabning BIRINCHI ruxsat etilgan zanjiriga qaytamiz
  //     (`['stars']`) — ya'ni `/stars`.
  return sectionsToPath(tab, chainAllowed(tab, chain) ? chain : SECTIONS[tab][0]);
}

/**
 * Yo'lni `Route` ga aylantiradi.
 * Noma'lum yo'l → bosh sahifa (404 ko'rsatmaymiz — Telegram WebApp da
 * noto'g'ri havola mijozni chalkashtiradi).
 */
export function pathToRoute(pathname: string): Route {
  const raw = String(pathname || '/').trim().toLowerCase();
  let p = raw.replace(/\/+$/, '') || '/';
  p = p.replace(/\/index\.html$/i, '') || '/';

  const segs = p.split('/').filter(Boolean);
  if (!segs.length) return { tab: 'home', sections: [] };

  // 1) To'g'ri-to'g'ri kanonik yo'l (alias'dan oldin — `/nft/gifts`
  //    alias'da ham bor, lekin kanonik shakl ustun bo'lishi kerak).
  //    `buy` ning prefiksi yo'q — bo'limlar o'zi yo'l.
  for (const tab of Object.keys(TAB_PREFIX) as TabType[]) {
    const prefix = TAB_PREFIX[tab];
    if (prefix && segs[0] === prefix) {
      const chain = segs.slice(1);
      if (chainAllowed(tab, chain)) return { tab, sections: chain };
      // 🔴 Prefiks to'g'ri, lekin bo'lim noto'g'ri (`/admin/bla`).
      //    Yo'li butunlay tashlab yubormaymiz — o'z tabiga qaytamiz.
      return { tab, sections: [] };
    }
  }
  if (chainAllowed('buy', segs)) return { tab: 'buy', sections: segs };

  // 2) Alias'lar
  const alias = ALIASES['/' + segs.join('/')];
  if (alias) return { tab: alias.tab, sections: [...alias.sections] };

  return { tab: 'home', sections: [] };
}

/**
 * 🔴 ESKI HAVOLALAR UCHUN: `?tab=…&sub=…` ni o'qib, yo'lga o'giradi.
 *
 * 📌 Bot (va eski versiyalar) `?tab=buy&sub=nft` ishlatadi. Bu
 * funksiya shuni kiritganda ham, qaytadan URL'ga yozganda ham
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
      const base: string[] = sub === 'nft' ? ['nft'] : [sub];
      if (chainAllowed('buy', base)) {
        const deep = p.get('s');
        const chain = deep && chainAllowed('buy', [...base, deep]) ? [...base, deep] : base;
        return { tab: 'buy', sections: chain };
      }
    }
    if (tab in TAB_PREFIX) {
      const t = tab as TabType;
      // 📌 `?tab=buy` (sub'siz) -> `/stars`. Aks holda `chainAllowed`
      //    `[]` ni rad etar, funksiya `null` qaytarar va eski havola
      //    butunlay ishlamay qolardi.
      return { tab: t, sections: SECTIONS[t][0] };
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
    u.searchParams.delete('s');
    const qs = u.searchParams.toString();
    return u.pathname + (qs ? `?${qs}` : '') + u.hash;
  } catch {
    return url;
  }
}

/* ============================================================================
 * 📌 YORDAMCHILAR — komponentlar shular orqali o'z bo'limini o'qiydi.
 * ========================================================================== */

/** `/nft/gifts` -> `'gifts'`  |  `/stars` -> `null` */
export function nftSectionOf(route: Route): NftSub | null {
  if (!route || route.tab !== 'buy') return null;
  const s = route.sections[0];
  if (s !== 'nft') return null;
  return (route.sections[1] || 'gifts') as NftSub;
}

/** `/ranking/today` -> `'today'`  |  `/ranking` -> `'all'` */
export function rankingPeriodOf(route: Route): RankingSub {
  if (!route || route.tab !== 'ranking') return 'all';
  return (route.sections[0] || 'all') as RankingSub;
}

/** `/profile/history` -> `'history'`  |  `/profile` -> `'overview'` */
export function profileSectionOf(route: Route): ProfileSub {
  if (!route || route.tab !== 'profile') return 'overview';
  return (route.sections[0] || 'overview') as ProfileSub;
}

/** `/admin/orders` -> `'orders'`  |  `/admin` -> `'stats'` */
export function adminSectionOf(route: Route): AdminSub {
  if (!route || route.tab !== 'admin') return 'stats';
  return (route.sections[0] || 'stats') as AdminSub;
}

/** `/stars` -> `'stars'`  |  `/nft/gifts` -> `'nft'` */
export function buySectionOf(route: Route): BuySub {
  if (!route || route.tab !== 'buy') return 'stars';
  return (route.sections[0] || 'stars') as BuySub;
}

/** `/profile/referral` — referral ochiq bo'lishi kerakmi? */
export function isReferralOpen(route: Route): boolean {
  return profileSectionOf(route) === 'referral';
}