/**
 * NEON STORE — USDT (TON) kurs xizmati
 * =====================================
 * USDT -> UZS kursini LIVE API dan oladi:
 *   1) CoinGecko: tether -> USD
 *   2) Frankfurter: USD -> UZS
 *
 * Kesh: 5 daqiqa. Internet/xato bo'lsa — USDT_RATE_UZS (ENV) zaxirasi ishlatiladi.
 * Bu kurs:
 *   • WebApp'da "Stars narxi ≈ X USDT" ko'rsatish uchun
 *   • Admin panelda USDT balansini so'mga solishtirish uchun ishlatiladi.
 *
 * Eslatma: Fragment'da Stars xaridi uchun to'lanadigan USDT miqdori
 * Fragment API'sining O'Z javobidan olinadi (process_star_order) — bu kurs
 * faqat ko'rsatish/ hisoblash uchun, to'lov Fragment tomonidan aniqlanadi.
 */

const RATE_TTL_MS = Number(process.env.USDT_RATE_TTL || 300) * 1000;
const FALLBACK_RATE = Number(process.env.USDT_RATE_UZS || 13000);

const TETHER_PRICE_URL = 'https://api.coingecko.com/api/v3/simple/price?ids=tether&vs_currencies=usd';
const FX_URL = 'https://api.frankfurter.app/latest?from=USD&to=UZS';

interface RateSnapshot {
  rate: number;
  source: 'live' | 'env';
  updatedAt: number;
}

let cache: RateSnapshot | null = null;

function num(value: unknown): number | null {
  const n = Number(value);
  return Number.isFinite(n) && n > 0 ? n : null;
}

/** 1 USDT = ? UZS */
export async function getUsdtUzsRate(force = false): Promise<RateSnapshot> {
  const now = Date.now();
  if (!force && cache && now - cache.updatedAt < RATE_TTL_MS) {
    return cache;
  }

  try {
    const [tetherRes, fxRes] = await Promise.all([
      fetch(TETHER_PRICE_URL, { headers: { 'User-Agent': 'NeonStore/1.0' } }),
      fetch(FX_URL, { headers: { 'User-Agent': 'NeonStore/1.0' } }),
    ]);

    if (!tetherRes.ok || !fxRes.ok) throw new Error(`HTTP ${tetherRes.status}/${fxRes.status}`);

    const tetherJson: any = await tetherRes.json();
    const fxJson: any = await fxRes.json();

    const usdPerUsdt = num(tetherJson?.tether?.usd);
    const uzsPerUsd = num(fxJson?.rates?.UZS);
    if (!usdPerUsdt || !uzsPerUsd) throw new Error("Kurs JSON formati o'zgargan");

    const rate = Math.round(usdPerUsdt * uzsPerUsd);
    cache = { rate, source: 'live', updatedAt: now };
    console.log(`💱 USDT/UZS live kursi: ${rate} so'm`);
    return cache;
  } catch (e) {
    console.warn('⚠️ Live kursni olib bo‘lmadi, ENV zaxirasi ishlatilmoqda:', (e as Error)?.message);
    cache = { rate: FALLBACK_RATE, source: 'env', updatedAt: now };
    return cache;
  }
}

/** USDT -> UZS (butun son, yaxlitlash bilan) */
export async function usdtToUzs(usdt: number): Promise<number> {
  const { rate } = await getUsdtUzsRate();
  return Math.round(usdt * rate);
}

/** 1 ta Stars taxminan qancha USDT turadi (Fragment bozoriga yaqin) */
export async function starsToUsdt(stars: number, usdtPerStar = 0.015): Promise<number> {
  return +(stars * usdtPerStar).toFixed(3);
}
