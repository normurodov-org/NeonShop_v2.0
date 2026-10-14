import express, { Request, Response } from 'express';
import cors from 'cors';
import path from 'path';
import fs from 'fs';
import { execSync } from 'child_process';
import { fileURLToPath } from 'url';
import { startTelegramBot, stopTelegramBot, getBotStatus, sendTelegramMessage } from './src/botService';
import { loadDatabase, saveDatabase, DB_FILE } from './src/db';
import { getUsdtUzsRate, usdtToUzs, starsToUsdt } from './src/rateService';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = Number(process.env.PORT) || 3000;

app.use(cors());
app.use(express.json());

// 🔬 FAQAT MAHSULLIQ: rasmlarni 7 soniya kechiktirib beradi —
// sekin internetni simulyatsiya qilish uchun (test_server_boot da
// ishlatiladi). Production'da bu yo'l ISHLAMAYDI (tezorat yo'q).
if (process.env.NFT_SLOW_IMAGES_MS) {
  const delay = Number(process.env.NFT_SLOW_IMAGES_MS) || 7000;
  app.get(/^\/_t\/slow(\d)\.png$/, (req: Request, res: Response) => {
    const m = /^\/_t\/slow(\d)\.png$/.exec(req.path);
    if (!m) return;
    try {
      const buf = fs.readFileSync(`${__dirname}/public/_t/g${m[1]}.png`);
      setTimeout(() => {
        res.setHeader('Content-Type', 'image/png');
        res.end(buf);
      }, delay);
    } catch {
      res.status(404).end();
    }
  });
  console.log(`🔬 NFT rasmlari ${delay}ms kechiktiriladi (test rejimi)`);
}

// Load persistent database from /data/users_db.json
const dbSnapshot = loadDatabase();

export const store = {
  settings: dbSnapshot.settings,
  users: new Map<number, any>(
    Object.values(dbSnapshot.users).map((u) => [u.id, u])
  ),
  orders: new Map<string, any>(
    Object.entries(dbSnapshot.orders)
  ),
  topups: new Map<string, any>(
    Object.entries(dbSnapshot.topups)
  ),
  /** NFT sovg'alar (ijara) — admin panel orqali qo'shiladi */
  nfts: new Map<string, any>(
    Object.entries(dbSnapshot.nfts || {})
  ),
  contest: dbSnapshot.contest,
};

// Atomically save data to /data/users_db.json
//
// DIQQAT: bot.py va server.ts bitta faylda ishlaydi. Agar oddiycha "xotiramni yoz"
// desak, botning o'zgarishlari (masalan to'lovni completed qilishi) yo'qolib ketadi.
// Shuning uchun 3 tomonlama merge qilamiz:
//   • diskdagi yangi ma'lumot (bot yozganlar) — asos
//   • lokal o'zgarishlar (biz yozganlar) — ustiga qo'yiladi
//   • lokal o'zgarishni `lastSynced` bilan solishtirib aniqlaymiz
let lastSynced: any = null;

const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v ?? null));

function currentSnapshot() {
  const usersObj: Record<string, any> = {};
  for (const [id, u] of store.users.entries()) usersObj[String(id)] = u;
  const ordersObj: Record<string, any> = {};
  for (const [id, o] of store.orders.entries()) ordersObj[id] = o;
  const topupsObj: Record<string, any> = {};
  for (const [id, t] of store.topups.entries()) topupsObj[id] = t;
  const nftsObj: Record<string, any> = {};
  for (const [id, n] of store.nfts.entries()) nftsObj[id] = n;
  return {
    settings: store.settings,
    users: usersObj,
    orders: ordersObj,
    topups: topupsObj,
    nfts: nftsObj,
    contest: store.contest,
  };
}

/**
 * Eski versiyalarda settings ga SOXTA statistika yozilgan edi
 * (14 280 foydalanuvchi / 8 740 buyurtma / 485 000 000 UZS).
 * Ular bazaga allaqachon saqlangan bo'lgani uchun kodni o'zgartirish
 * o'zi yetarli emas — ularni tozalashimiz kerak.
 *
 * Shu bilan birga bot.py ham `total_users + store.users.size` qilib
 * hisoblagan — ya'ni raqam ikki marta qo'shilardi.
 */
const LEGACY_FAKE_STATS: Record<string, number> = {
  total_users: 14280,
  total_orders: 8740,
  total_volume_uzs: 485000000,
};

function migrateLegacyFakeStats() {
  let changed = false;
  for (const [key, fake] of Object.entries(LEGACY_FAKE_STATS)) {
    if (Number(store.settings?.[key]) === fake) {
      console.warn(`[migrate] soxta statistika tozalandi: ${key} = ${fake} -> 0`);
      (store.settings as any)[key] = 0;
      changed = true;
    }
  }
  if (changed) {
    try {
      syncAndSaveDb();
    } catch (e) {
      console.error('[migrate] saqlashda xato:', e);
    }
  }
}

/**
 * ORDERS_CHANNEL kanaliga xabar yuboradi (Telegram Bot API orqali).
 *
 * MUHIM: avval `sendTelegramMessage` (grammy) ishlatilardi, lekin u
 * faqat AUTO_START_TG_BOT=true bo'lganda ishlaydi. Bizda esa Python
 * bot.py ishlaydi va AUTO_START_TG_BOT=false — shuning uchun barcha
 * kanal xabarlari jimgina YO'QOLIB borardi.
 * Shuning uchun to'g'ridan-to'g'ri Bot API chaqiramiz.
 */
async function postToOrdersChannel(text: string, buttonLabel = '📊 NeonShop') {
  const token = (process.env.BOT_TOKEN || '').trim();
  const chat = (process.env.ORDERS_CHANNEL || '@Shop_NeonOrders').trim();
  if (!token || !chat) {
    console.warn('[channel] BOT_TOKEN yoki ORDERS_CHANNEL yo‘q — xabar yuborilmadi');
    return false;
  }
  try {
    const res = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        chat_id: chat,
        text,
        parse_mode: 'HTML',
        disable_web_page_preview: true,
        reply_markup: {
          inline_keyboard: [[{ text: buttonLabel, url: process.env.WEBAPP_URL || 'https://t.me/' }]],
        },
      }),
      signal: AbortSignal.timeout(15000),
    });
    const data: any = await res.json();
    if (!data?.ok) {
      console.warn('[channel] yuborilmadi:', data?.description || res.status);
      return false;
    }
    return true;
  } catch (e) {
    console.error('[channel] xato:', e);
    return false;
  }
}

/** Rasmdagi kanal formati (3-rasm). */
/** Usernamni kanalda yashiradi: @odilbek -> @ode**** */
function maskUsername(name: string | number | null | undefined): string {
  const t = String(name ?? '').trim().replace(/^@+/, '');
  if (!t) return '@user';
  if (t.length <= 4) return `@${t.slice(0, 1)}***`;
  return `@${t.slice(0, 3)}****`;
}

function channelOrderText(o: {
  title: string;
  username: string;
  amountText: string;
  price: number;
  cashback?: number;
  bonus?: number;
}): string {
  const lines = [
    `⭐ <b>${o.title}</b> `,
    `👤 <b>${maskUsername(o.username)} </b>`,
    '',
    `📦 <b>${o.amountText}</b>`,
    `💵 <b>Summasi:</b> ${o.price.toLocaleString()} so'm`,
  ];
  if (o.cashback) lines.push(`  <b>Keshbek:</b> +${o.cashback.toLocaleString()} so'm`);
  return lines.join('\n');
}

/**
 * Bot.py diskga yozgan yangi ma'lumotni (masalan admin panel orqali
 * qo'shilgan NFT) server xotirasiga olib keladi.
 *
 * MUHIM: `store` faqat ishga tushganda o'qiladi. Agar admin keyin
 * NFT qo'shsa, server eski ro'yxatni qaytarib berardi va WebApp'da
 * hech narsa ko'rinmasdi. Bu funksiya har so'rovda nechta daqiqada
 * bir diskni tekshiradi (mtime orqali) — har so'rovda o'qimaydi,
 * chunki bu og'ir.
 */
let lastNftScan = 0;
const NFT_SCAN_MS = 3000;
let lastDbMtime = 0;
try {
  lastDbMtime = fs.statSync(DB_FILE).mtimeMs;
} catch {
  lastDbMtime = 0;
}

/** Diskdagi `nfts` bo'limini `store.nfts` ga singdirib qo'yadi. */
export function refreshNftsFromDisk() {
  const now = Date.now();
  if (now - lastNftScan < NFT_SCAN_MS) return;
  lastNftScan = now;
  let mtime = 0;
  try {
    mtime = fs.statSync(DB_FILE).mtimeMs;
  } catch {
    return;
  }
  if (mtime === lastDbMtime) return;
  lastDbMtime = mtime;
  try {
    const fresh = loadDatabase();
    store.nfts = new Map<string, any>(Object.entries(fresh.nfts || {}));
    lastSynced = { ...(lastSynced ?? {}), nfts: clone(store.nfts ? Object.fromEntries(store.nfts) : {}) };
  } catch (e) {
    console.error('refreshNftsFromDisk: bazani o‘qib bo‘lmadi:', e);
  }
}

export function syncAndSaveDb() {
  let fresh: any;
  try {
    fresh = loadDatabase();
  } catch (e) {
    console.error('syncAndSaveDb: bazani o‘qib bo‘lmadi:', e);
    fresh = lastSynced ?? currentSnapshot();
  }

  const merged: any = {
    settings: { ...(fresh.settings || {}) },
    users: { ...(fresh.users || {}) },
    orders: { ...(fresh.orders || {}) },
    topups: { ...(fresh.topups || {}) },
    nfts: { ...(fresh.nfts || {}) },
    contest: { ...(fresh.contest || {}) },
  };

  // settings: faqat lokalda o'zgargan kalitlarni ustiga qo'yamiz
  for (const [k, v] of Object.entries(store.settings)) {
    const prev = lastSynced?.settings?.[k];
    if (!lastSynced || JSON.stringify(prev) !== JSON.stringify(v)) {
      merged.settings[k] = v;
    }
  }

  // users / orders / topups
  const sections: [string, Map<any, any>][] = [
    ['users', store.users],
    ['orders', store.orders],
    ['topups', store.topups],
    ['nfts', store.nfts],
  ];
  for (const [key, map] of sections) {
    for (const [k, v] of map.entries()) {
      const sk = String(k);
      const prev = lastSynced?.[key]?.[sk];
      const localChanged = !lastSynced || JSON.stringify(prev) !== JSON.stringify(v);
      if (localChanged) {
        merged[key][sk] = v;
      }
    }
  }

  // contest
  if (!lastSynced || JSON.stringify(lastSynced.contest) !== JSON.stringify(store.contest)) {
    merged.contest = store.contest;
  }

  saveDatabase(merged);
  lastSynced = clone(merged);

  // Xotiramizni ham yangilangan holatga moslashtiramiz
  store.settings = merged.settings;
  store.contest = merged.contest;
  for (const [k, u] of Object.entries(merged.users)) store.users.set(Number(k), u);
  for (const [k, o] of Object.entries(merged.orders)) store.orders.set(k, o);
  for (const [k, t] of Object.entries(merged.topups)) store.topups.set(k, t);
  for (const [k, n] of Object.entries(merged.nfts || {})) store.nfts.set(k, n);
}

// Boshlang'ich holatni "o'zgartirilmagan" deb belgilaymiz
lastSynced = clone(currentSnapshot());
migrateLegacyFakeStats();

// =============================================================================
// TELEGRAM IDENTIFIKATSIYASI — HMAC tekshiruvi
// =============================================================================
// 🔴 BU NIMA UCHUN KERAK?
// Ilgari foydalanuvchi id'si `x-telegram-user-id` HEADERidan olinardi
// va TELEGRAM TOMONidan HECH QANDAY TEKSHIRILMAGAN edi. Shu sabab:
//   • header kelmasa  -> targetId = DEFAULT_USER_ID (admin!) bo'lib qolardi
//   • `?uid=` URL orqali -> istalgan id yuborish mumkin edi
// Ya'ni:
//   1) Telegram DAN tashqarida ochilgan WebApp -> ADMIN sifatida kiradi
//      (profil "odilbek" ko'rinadi, balans 357 813 UZS, AdminPanel ochiq)
//   2) H anyone `?uid=8307046273` deb yozib, ADMINNING BALANSINI
//      ishlatib yubora olardi
//   3) `POST /api/admin/adjust-balance` authsiz -> cheksiz UZS yaratish
//
// YECHIM: Telegram WebApp `initData` SIGNED satrini yuboradi. Uning
// HMAC-SHA256 imzosi BOT_TOKEN kaliti bilan tekshiriladi (Telegramning
// o'z rasmiy usuli). Imzo mos kelmasa — so'rov RAD qilinadi.
//
//  data_check_string = "auth_date=<t>\nquery_id=<q>\nuser=<json>"
//  secret_key         = HMAC_SHA256(bot_token, "WebAppData")
//  hash               = HMAC_SHA256(data_check_string, secret_key)  <- initData'dagi hash

import crypto from 'crypto';

/** `initData` satridan maydonlarni ajratadi (URL-decode qilib). */
function parseInitData(initData: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const pair of initData.split('&')) {
    const i = pair.indexOf('=');
    if (i < 0) continue;
    try {
      out[pair.slice(0, i)] = decodeURIComponent(pair.slice(i + 1).replace(/\+/g, ' '));
    } catch {
      out[pair.slice(0, i)] = pair.slice(i + 1);
    }
  }
  return out;
}

/**
 * `initData` imzosini BOT_TOKEN bilan tekshiradi.
 *
 * Qaytaradi: `{ ok: true, user: {...} }` yoki `{ ok: false, why: string }`
 */
export function verifyTelegramInitData(
  initData: string
): { ok: boolean; user?: any; why?: string } {
  if (!initData || !initData.trim()) return { ok: false, why: 'initData yoq' };
  const token = (process.env.BOT_TOKEN || '').trim();
  // Bot token ENV yo'q bo'lsa tekshiruvni O'CHIRMAYMIZMIZ — aks holda
  // hamma narsa yotib qoladi. Balki "ruxsat yoq" deb rad qilamiz
  // (fail-closed), chunki ochiq qoldirish xavfsiz emas.
  if (!token) return { ok: false, why: 'BOT_TOKEN ENV yoq' };

  const params = parseInitData(initData);
  const hash = params.hash;
  if (!hash) return { ok: false, why: 'hash yoq' };

  // hash ni chiqarib, qolganini "key=value" tartibida (bo'sh joy
  // bo'yicha saralangan) data_check_string ga yig'amiz
  const pairs: string[] = [];
  for (const k of Object.keys(params).sort()) {
    if (k === 'hash') continue;
    pairs.push(`${k}=${params[k]}`);
  }
  const dataCheckString = pairs.join('\n');

  const secretKey = crypto
    .createHmac('sha256', 'WebAppData')
    .update(token)
    .digest();
  const expected = crypto
    .createHmac('sha256', secretKey)
    .update(dataCheckString)
    .digest('hex');

  // Uzunlik bo'yicha taqqoslash (timing-safe)
  const a = Buffer.from(expected, 'utf8');
  const b = Buffer.from(hash, 'utf8');
  if (a.length !== b.length || !crypto.timingSafeEqual(a, b)) {
    return { ok: false, why: 'imzo mos emas' };
  }

  // auth_date juda eshimi bo'lsa — rad qilamiz (eskirgan link)
  const authDate = Number(params.auth_date || 0);
  const maxAge = Number(process.env.WEBAPP_AUTH_MAX_AGE || 86400); // 1 kun
  if (authDate && Date.now() / 1000 - authDate > maxAge) {
    return { ok: false, why: 'initData eskirgan' };
  }

  try {
    const user = JSON.parse(params.user || '{}');
    if (!user.id) return { ok: false, why: 'user.id yoq' };
    return { ok: true, user };
  } catch {
    return { ok: false, why: 'user JSON buzilgan' };
  }
}

const DEFAULT_USER_ID = 8307046273;

/**
 * Konkurs faqat admin yaratgan va hali muddati tugamagan bo'lsa faol.
 *
 * Himoya: eski/demo konkurs (active=true, lekin end_at o'tgan) hech qachon
 * ko'rinmasligi kerak — aks holda "Hali konkurs yo'q" o'rniga o'lik
 * konkurs ko'rinib turadi va "3 kun qoldi" yozib turadi.
 */
/** Qiymat berilgan bo'lsa uni ishlatadi (0 ham to'g'ri qiymat), aks holda zaxira. */
function numOr(v: any, fallback: number): number {
  const n = Number(v);
  return Number.isFinite(n) && v !== undefined && v !== null && v !== '' ? n : fallback;
}

/**
 * Konkursni FAOL qiladi (WebApp'da ko'rinishi uchun).
 *
 * Oldin default `active: false` + "Hali konkurs yaratilmagan" edi —
 * shuning uchun WebApp hech qachon raqamni ko'rsatmasdi. Endi:
 *   • bo'sh/placeholder konkurs bo'lsa — real, faol konkurs bilan
 *     almashtiriladi (admin keyin o'zgartirishi mumkin)
 *   • admin tomonidan yaratilgan konkurs tegilmaydi
 */
const DEFAULT_CONTEST_DAYS = 30;

function defaultContest() {
  const end = new Date(Date.now() + DEFAULT_CONTEST_DAYS * 86400_000);
  return {
    id: 'contest_1',
    text: '🎉 <b>Yulduzlar g\'alchasi!</b>\nXaridingiz orqali ball to\'pling va sovg\'a yutish shansini qo\'shing.',
    winners: 3,
    prize_stars: 100,
    ends_in: DEFAULT_CONTEST_DAYS,
    end_at: end.toISOString(),
    participants: [],
    min: 10_000,
    active: true,
  };
}

function openContestIfEmpty() {
  const c = store.contest as any;
  const isEmpty =
    !c ||
    c.id === 'contest_none' ||
    !c.text ||
    String(c.text).includes('yaratilmagan');
  if (!isEmpty) return false;
  store.contest = { ...defaultContest(), participants: [] } as any;
  syncAndSaveDb();
  console.log('[contest] WebApp uchun faol konkurs yo\'qilindi');
  return true;
}

/**
 * Konkursni ochish — BARCHA const/function deklaratsiyalaridan KEYIN
 * chaqirilishi shart. Aks holda TDZ (Temporal Dead Zone) xatosi:
 * "Cannot access 'DEFAULT_CONTEST_DAYS' before initialization" —
 * bu serverni butunlay ishga tushirmaydi (production'da "Server crashed").
 */
openContestIfEmpty();

/** WebApp uchun konkursni tayyorlaydi (konkurs yo'q bo'lsa — ochadi). */
function contestPayload(userId: number): any {
  if (!store.contest || !store.contest.text) openContestIfEmpty();
  const c: any = store.contest as any;
  return {
    ...c,
    active: contestIsActive(c),
    joined: Array.isArray(c.participants) ? c.participants.includes(userId) : false,
    spent: Number(store.users.get(userId)?.total_spent) || 0,
  };
}

function contestIsActive(c: any): boolean {
  if (!c || !c.active) return false;
  if ((c.prize_stars ?? 0) <= 0) return false;
  const end = c.end_at ? Date.parse(c.end_at) : NaN;
  if (!Number.isNaN(end) && end < Date.now()) return false;
  return true;
}

/**
 * 🔴 SO'ROVNING TEGISHLILIGINI ANIQLAYDI.
 *
 * Tartib:
 *   1) `X-Telegram-Init-Data` header — IMZOLI, `verifyTelegramInitData()`
 *      bilan tekshiriladi. Bu — YAGONA ishonchli manba.
 *   2) `x-telegram-user-id` — FAQAT `ALLOW_UNSIGNED_USER=1` bo'lsa
 *      (mahalliy ishlab chiqish uchun). Production'da YO'Q.
 *
 * 🔴 ESKI XULOSASIZ: `if (header yo'q) -> DEFAULT_USER_ID`. Bu
 * Telegram dan tashqarida ochilgan har bir WebApp'ni ADMIN qilib
 * qo'yardi (profil, 357 813 UZS balans, AdminPanel). Endi — 401.
 */
// =============================================================================
// TELEGRAM LOGIN WIDGET — brauzerda (sayt orqali) kirish
// =============================================================================
// 📐 NIMA UCHUN?
// WebApp ichida (`t.me/bot/app`) Telegram `initData` imzosini beradi —
// server uni BOT_TOKEN bilan tekshiradi. Lekin mijoz saytni
// BRAUZERDA (kompyuter/planshet) ochsa `initData` BO'LMAYDI:
// ilova «Telegram orqali kiring» ekranida qolardi va hech qanday
// xizmat ishlamasdi.
//
// Yechim — Telegram'ning rasmiy **Login Widget**'i:
//   `https://telegram.org/js/telegram-widget.js`
// Bu brauzerda `my.telegram.org` orqali Telegram'ning O'Z OAuth
// oynasini ochadi va imzolangan ma'lumotni qaytaradi. Imzo
// WebApp'dan FARQ qilib SHA256 kalit bilan tekshiriladi:
//
//   secret = SHA256(bot_token)          <- WebApp'da HMAC("WebAppData")
//   hash   = HMAC_SHA256(data_check_string, secret)
//
// Ikki xil kalit — ikkalasi ham Telegram rasmiy hujjatida shunday.
//
// 📔 SESSIYA: tekshirilgan foydalanuvchiga token beriladi va
// frontend uni `localStorage` da saqlab, har bir so'rovda
// `X-Session-Token` header orqali yuboradi.
// =============================================================================

/** Login Widget ma'lumotini BOT_TOKEN bilan tekshiradi. */
export function verifyTelegramLoginWidget(data: string): { ok: boolean; user?: any; why?: string } {
  if (!data || !data.trim()) return { ok: false, why: "bo'sh" };
  const token = (process.env.BOT_TOKEN || "").trim();
  if (!token) return { ok: false, why: "BOT_TOKEN ENV yo'q" };

  const fields = parseInitData(data);
  const hash = fields.hash;
  if (!hash) return { ok: false, why: "hash yo'q" };

  const pairs: string[] = [];
  for (const k of Object.keys(fields).sort()) {
    if (k === "hash") continue;
    pairs.push(`${k}=${fields[k]}`);
  }
  const dataCheckString = pairs.join("\n");

  // 🔴 Login Widget kaliti: SHA256(bot_token) — WebApp'dagi
  //    HMAC(bot_token, "WebAppData") dan FARQ qiladi.
  const secret = crypto.createHash("sha256").update(token, "utf8").digest();
  const expected = crypto.createHmac("sha256", secret)
    .update(dataCheckString, "utf8").digest("hex");

  const a = Buffer.from(expected, "utf8");
  const b = Buffer.from(hash, "utf8");
  if (a.length !== b.length || !crypto.timingSafeEqual(a, b)) {
    return { ok: false, why: "imzo mos emas" };
  }

  const authDate = Number(fields.auth_date || 0);
  const maxAge = Number(process.env.WEBAPP_AUTH_MAX_AGE || 86400);
  if (authDate && Date.now() / 1000 - authDate > maxAge) {
    return { ok: false, why: "kirish eskirgan (1 kundan ko'p)" };
  }

  const id = Number(fields.id || 0);
  if (!id || id <= 0) return { ok: false, why: "id yo'q" };

  return {
    ok: true,
    user: {
      id,
      username: String(fields.username || "").replace(/^@/, ""),
      first_name: fields.first_name || "",
      last_name: fields.last_name || "",
      photo_url: fields.photo_url || undefined,
    },
  };
}

// =============================================================================
// \U0001F510\u2006BRAUZER SESSIYALARI \u2014 ALOHIDA FAYLDA
// =============================================================================
// \U0001F534\u2006NIMA UCHUN BUNDAY?
// \U0001F534\u2006Sessiya avval `users_db.json` ning `settings.__sessions` da
// saqlanardi. LEKIN bot.py har 20 soniyada `db.save()` qiladi
// (`update_heartbeat` \u2192 `set_runtime_status`) va u O\u0026Z XOTIRASIDAN
// yozadi \u2014 `reload_if_changed()` chaqirmasdan. Bot qo\u0027lda ishga
// tushganda olgan nusxa eskirgan, unda `__sessions` YO\u0027Q.
//
// Natija: brauzerda mijoz kirdi \u2192 server sessiyani yozdi \u2192 20
// soniyadan keyin bot.py o\u0027z eski nusxasini yozdi va sessiyani
// O\u0027CHIRDI \u2192 mijoz qayta kirish ekraniga qaytdi. Xuddi shunday
// holat: \u00abTelegram bilan uladim, lekin asosiy sahifa ochilmayapti\u00bb.
//
// \U0001F4D4\u2006YECHIM: sessiyalar alohida faylda (`web_sessions.json`).
// Uni FAQAT server.ts ochadi \u2014 bot.py umuman tegmaydi, shuning uchun
// hech qanday eskirgan nusxa uni o\u0027chira olmaydi.
// Railway\u0027da `/data` bir xil volume\u2014 saqlanib qoladi.
// =============================================================================


// 🔐 `DB_FILE` allaqachon `./src/db` dan IMPORT qilingan — qayta
// e'lon qilish TypeScript xatosi beradi.
const SESSIONS_FILE = DB_FILE.replace(/\.json$/, '') + '.sessions.json';

/** token \u2192 { user_id, created_at, expires_at, via } */
let sessionStore: Record<string, any> = {};

function loadSessions(): void {
  try {
    if (!fs.existsSync(SESSIONS_FILE)) return;
    const raw = fs.readFileSync(SESSIONS_FILE, "utf8");
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === "object") sessionStore = parsed;
  } catch (e) {
    console.warn("Sessiya fayli o\\u0027qilamadi:", (e as Error)?.message);
  }
}

function saveSessions(): void {
  try {
    fs.mkdirSync(path.dirname(SESSIONS_FILE), { recursive: true });
    const tmp = SESSIONS_FILE + ".tmp";
    // \U0001F510 MUDDATI \U0007/O\\u0027GAN sessiyalarni tozalash \u2014 fayl
    //   cheksiz o\\u0027sib ketmasin.
    const nowMs = Date.now();
    for (const [t, r] of Object.entries(sessionStore)) {
      if (r?.expires_at && Date.parse(r.expires_at) < nowMs) {
        delete sessionStore[t];
      }
    }
    fs.writeFileSync(tmp, JSON.stringify(sessionStore, null, 2), "utf8");
    fs.renameSync(tmp, SESSIONS_FILE);
  } catch (e) {
    console.error("Sessiya fayliga yozib bo\\u0027lmadi:", (e as Error)?.message);
  }
}

loadSessions();

/** `X-Session-Token` \u2192 foydalanuvchi (brauzer uchun). */
function sessionUser(req: Request): any | null {
  const token =
    (req.headers["x-session-token"] as string) ||
    (req.headers["authorization"] as string)?.replace(/^Bearer\s+/i, "") ||
    "";
  if (!token) return null;
  const rec = sessionStore[token];
  if (!rec) return null;
  // 🔴 Muddati o'tgan sessiya — tozalanadi
  if (rec.expires_at && Date.parse(rec.expires_at) < Date.now()) {
    delete sessionStore[token];
    saveSessions();
    return null;
  }
  const user = store.users.get(Number(rec.user_id));
  if (!user) return null;
  return user;
}

/**
 * 🔐 `POST /api/auth/telegram` — brauzerda Telegram orqali kirish.
 *
 * Telegram Login Widget imzosini tekshiradi, foydalanuvchini bazaga
 * yozadi (yoki yangilaydi) va uzoq muddatli token qaytaradi.
 */
app.post("/api/auth/telegram", (req: Request, res: Response) => {
  const v = verifyTelegramLoginWidget(String(req.body?.data || ""));
  if (!v.ok || !v.user) {
    return res.status(401).json({ ok: false, error: `Tasdiqlash muvaffaqiyatsiz: ${v.why}` });
  }

  // 🔄 Profilni yangilaymiz (username/rasm o'zgargan bo'lishi mumkin)
  try {
    loadDatabase();
  } catch { /* bo'sh */ }
  const uid = Number(v.user.id);
  const existing = store.users.get(uid);
  if (existing) {
    if (v.user.username) existing.username = v.user.username;
    if (v.user.first_name) existing.first_name = v.user.first_name;
    if (v.user.photo_url) existing.photo_url = v.user.photo_url;
  } else {
    store.users.set(uid, {
      id: uid,
      username: v.user.username || "",
      first_name: v.user.first_name || undefined,
      photo_url: v.user.photo_url,
      balance: 0,
      total_spent: 0,
      referrals_count: 0,
      ref_stars: 0,
      banned: false,
      created_at: new Date().toISOString(),
    });
  }

  const token = crypto.randomBytes(24).toString("hex");
  const days = Number(process.env.SESSION_DAYS || 30);
  sessionStore[token] = {
    user_id: uid,
    created_at: new Date().toISOString(),
    expires_at: new Date(Date.now() + days * 86400000).toISOString(),
    via: "login_widget",
  };
  // 🔐 «BOTGA» ALMAYDI — sessiya alohida faylda
  saveSessions();

  res.json({ ok: true, token, days, user: store.users.get(uid) });
});

// =============================================================================
// 🌐 WEB LOGIN — DEEP LINK (Telegram orqali kirish)
// =============================================================================
// 🔴 NIMA UCHUN BU QO'SHILDI?
//    Telegram'ning eski **Login Widget** popup oqimi ishonchsiz:
//      1. tugma bosiladi → `window.open` popup ochiladi
//      2. Telegram `/auth` → natija `postMessage` YOKI `/auth/get` XHR orqali
//      3. natija kelmasa → `{event:'unauthorized'}` → ota tomonda
//         `onUnauth && onUnauth()` — bizda `data-onunauth` YO'Q edi
//         → 🔴 HECH NARSA bo'lmaydi, sahifa o'zgarmaydi qoladi
//    Mijoz xabari: «ekran ochilib 1 soniyada yopiladi, sahifa o'zgarmadi».
//    `/auth/get` ning javobi (`{"error":"NOT_AUTHORIZED"}`) shuni tasdiqladi.
//
// ✅ YECHIM — popup umuman yo'q:
//    1. server `web_<48hex>` kod beradi
//    2. brauzer `https://t.me/<bot>?start=<kod>` ni ochadi
//    3. mijoz Telegram'da **Start** ni bosadi
//    4. bot.py `/start <kod>` ni oladi va `*_login_codes.json` ga yozadi
//    5. brauzer `GET /api/auth/telegram/status` bilan kutadi
//    6. server sessiya yaratadi
//
//    Bu yo'l ishonchli: popup yo'q, CORS yo'q, third-party cookie yo'q.
//    Kompyuterdagi Telegram ham, telefon ham bir xil ishlaydi.
//
// 📁 FAYLLAR (har birining YAGINA yozuvchisi bor — chunki avval
//    `settings.__sessions` da bo'lganda bot.py 20 soniyada o'chirdi):
//    * `*_login_codes.json`  → YAZADI: bot.py, O'QIYDI: server.ts
//    * `*_sessions.json`     → YAZADI: server.ts, O'QIYDI: server.ts
// =============================================================================

const LOGIN_CODES_FILE = DB_FILE.replace(/\.json$/, '') + '.login_codes.json';

/** `code` → `{ user_id, username, first_name, photo_url, at }` (bot.py yozadi) */
function readLoginCodes(): Record<string, any> {
  try {
    if (!fs.existsSync(LOGIN_CODES_FILE)) return {};
    const parsed = JSON.parse(fs.readFileSync(LOGIN_CODES_FILE, 'utf8'));
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch (e) {
    console.warn("Login kodlar fayli o'qilamadi:", (e as Error)?.message);
    return {};
  }
}

/** Kod shakli: `web_` + 48 hex. Telegram start param faqat A-Za-z0-9_- qabul qiladi. */
const LOGIN_CODE_RE = /^web_[0-9a-f]{48}$/;

/**
 * 🌐 `POST /api/auth/telegram/start` — bitta martalik kod beradi.
 *
 * Javobda `telegram_url` qaytadi — brauzer shuni ochadi, mijoz
 * Telegram'da Start bosadi.
 */
app.post('/api/auth/telegram/start', async (_req: Request, res: Response) => {
  // 🔴 `resolveBotUsername` ASYNC — `await` siz `Promise` qaytarardi
  //    va havola `t.me/[object Promise]` bo'lib ketardi.
  const bot = await resolveBotUsername();
  if (!bot) {
    return res.status(503).json({ ok: false, error: 'Bot nomi hali aniqlanmadi' });
  }
  // 48 hex = 192 bit — taxmin qilish mumkin emas
  const code = 'web_' + crypto.randomBytes(24).toString('hex');
  return res.json({
    ok: true,
    code,
    telegram_url: 'https://t.me/' + bot + '?start=' + code,
  });
});

/**
 * 🔍 `GET /api/auth/telegram/status?code=...` — mijoz tasdiqladimi?
 *
 * `pending` → Telegram'da Start hali bosilmagan
 * `ok`      → tasdiqlandi, `token` qaytariladi
 */
app.get('/api/auth/telegram/status', (req: Request, res: Response) => {
  const code = String(req.query.code || '');
  if (!LOGIN_CODE_RE.test(code)) {
    return res.status(400).json({ ok: false, status: 'error', error: "Kod noto'g'ri" });
  }

  // 🔴 BIR MARTA ishlatiladi — aks holda kimdir boshqaning kodini
  //    qayta ishlatib sessiya olishi mumkin.
  if (sessionStore.__used_login_codes?.[code]) {
    return res.json({ ok: true, status: 'error', error: 'Kod allaqachon ishlatilgan' });
  }

  const rec = readLoginCodes()[code];
  if (!rec) return res.json({ ok: true, status: 'pending' });

  // 🔐 KOD ESKIRISHI — 10 daqiqadan keyin ishlamaydi
  const age = Date.now() - Date.parse(rec.at || 0);
  if (!rec.at || age > 10 * 60 * 1000) {
    return res.json({ ok: true, status: 'error', error: 'Kod muddati tugagan' });
  }

  const uid = Number(rec.user_id);
  // 🔄️ `loadDatabase()` faqat MA’LUMOT QAYTARADI — `store.users` ni
  //    yangilamaydi. Bot.py foydalanuvchini bir necha soniya oldin
  //    yozgan bo'lishi mumkin, shuning uchun haqiqiy o'qish kerak.
  //    Aks holda endi token BERILMASDI (404) — ya’ni mijoz Telegram’da
  //    Start bosgan bo'lsa ham, saytda «xato» chiqardi.
  try {
    const fresh = loadDatabase();
    store.users = new Map<number, any>(
      Object.values(fresh.users).map((u: any) => [Number(u.id), u])
    );
  } catch { /* bo'sh */ }
  const user = store.users.get(uid);
  if (!user) {
    // Bot foydalanuvchini bazaga yozmagan bo'lishi mumkin
    return res.status(404).json({ ok: false, status: 'error', error: 'Foydalanuvchi topilmadi' });
  }

  // Mijozni Telegram ma'lumotlari bilan yangilaymiz
  if (rec.username) user.username = rec.username;
  if (rec.first_name) user.first_name = rec.first_name;
  if (rec.photo_url) user.photo_url = rec.photo_url;

  const token = crypto.randomBytes(24).toString('hex');
  const days = Number(process.env.SESSION_DAYS || 30);
  sessionStore[token] = {
    user_id: uid,
    created_at: new Date().toISOString(),
    expires_at: new Date(Date.now() + days * 86400000).toISOString(),
    via: 'deep_link',
  };
  // 🔴 Ishlatilgan kodlarni eslatib qolamiz (restart'dan keyin ham)
  sessionStore.__used_login_codes = sessionStore.__used_login_codes || {};
  sessionStore.__used_login_codes[code] = new Date().toISOString();
  saveSessions();

  return res.json({ ok: true, status: 'ok', token });
});

/** `POST /api/auth/logout` — sessiyani o'chirish. */
app.post("/api/auth/logout", (req: Request, res: Response) => {
  const token = (req.headers["x-session-token"] as string) || "";
  if (token && sessionStore[token]) {
    delete sessionStore[token];
    saveSessions();
  }
  res.json({ ok: true });
});

function requireIdentity(req: Request): { user: any } | null {
  const initData = (req.headers['x-telegram-init-data'] as string) || '';
  if (initData) {
    const v = verifyTelegramInitData(initData);
    if (v.ok && v.user) return { user: v.user };
    return null;   // imzo mos emas -> rad
  }

  // 🔶 BRAUZER UCHUN: Telegram Login Widget orqali olingan sessiya.
  //    Telegram ichida `initData` bo'ladi — bu yo'l faqat saytni
  //    brauzerda ochganda ishlaydi.
  const sess = sessionUser(req);
  if (sess) return { user: sess };
  if (String(process.env.ALLOW_UNSIGNED_USER || '') === '1') {
    const raw = (req.headers['x-telegram-user-id'] as string) || '';
    const id = parseInt(raw, 10);
    if (!isNaN(id) && id > 0) {
      return {
        user: {
          id,
          username: (req.headers['x-telegram-username'] as string || '').replace('@', ''),
          first_name: (req.headers['x-telegram-first-name'] as string) || '',
          photo_url: (req.headers['x-telegram-photo-url'] as string) || undefined,
        },
      };
    }
  }
  return null;
}

function requireAdmin(req: Request): boolean {
  const id = requireIdentity(req)?.user?.id;
  return !!id && id === Number(store.settings.admin_id || DEFAULT_USER_ID);
}

/** 401 javobini beradi (frontend "Telegram orqali kiring" ko'rsatadi). */
function unauthorized(res: Response, why = 'Telegram orqali kiring') {
  return res.status(401).json({ ok: false, need_telegram: true, error: why });
}

function getUser(req?: Request, defaultId = DEFAULT_USER_ID) {
  // Always refresh latest state from /data/users_db.json so data matches bot 1:1
  try {
    const freshDb = loadDatabase();
    if (freshDb && freshDb.users) {
      for (const [k, u] of Object.entries(freshDb.users)) {
        store.users.set(Number(k), u);
      }
      for (const [k, o] of Object.entries(freshDb.orders || {})) {
        store.orders.set(k, o);
      }
      // Topups ham har safar yangilanadi: bot.py (userbot) to'lovni tasdiqlaganda
      // "completed" qiladi — server eski "pending" holatini ustiga yozib yubormasin.
      for (const [k, t] of Object.entries(freshDb.topups || {})) {
        store.topups.set(k, t);
      }
      store.settings = { ...store.settings, ...(freshDb.settings || {}) };
      store.contest = { ...store.contest, ...(freshDb.contest || {}) };
    }
  } catch (e) {
    console.error('Error refreshing db in getUser:', e);
  }

  // 🔴 IDENTITET — faqat tekshirilgan manbadan
  let targetId = defaultId;
  let username = '';
  let firstName = '';
  let photoUrl: string | undefined;

  if (req) {
    const ident = requireIdentity(req);
    if (ident?.user) {
      const u = ident.user;
      targetId = Number(u.id);
      username = String(u.username || '').replace('@', '');
      firstName = String(u.first_name || '');
      photoUrl = u.photo_url ? String(u.photo_url) : undefined;
    } else if (String(process.env.ALLOW_UNSIGNED_USER || '') !== '1') {
      // 🔴 IMZO YO'Q — endi ADMIN emas, balki null. Endpoint'lar
      // `getUser(req)` natijasini tekshirib 401 qaytaradi.
      return null as any;
    }
  }
  let user = store.users.get(targetId);
  if (!user) {
    user = {
      id: targetId,
      // 🔴 ESKI: `'user_' + id.slice(-4)` — bu SUN'IY username edi.
      // "O'zimga" bosilganda shu yuborilardi, server har qanday
      // bo'sh bo'lmagan string'ni qabul qilib UZS ni yechardi, so'ng
      // Fragment ishlamay qolardi: pul ketgan, hech narsa kelmagan.
      // Endi username yo'q bo'lsa BO'SH qoladi — frontend bu holatda
      // "O'zimga" tugmasini o'chiradi va xabar ko'rsatadi.
      username: username || '',
      first_name: firstName || undefined,
      photo_url: photoUrl || (targetId === DEFAULT_USER_ID ? '/logo.svg' : undefined),
      // 🔴 ESKI: `targetId === DEFAULT_USER_ID ? 357813 : 0` — ya'ni
      // admin ro'yxatga YO'YOTSA uni soxta qilib 357 813 UZS BERARDI.
      // Endi har qanday yangi hisob 0 dan boshlanadi.
      balance: 0,
      total_spent: 0,
      referrals_count: 0,
      ref_stars: 0,
      banned: false,
      created_at: new Date().toISOString(),
    };
    store.users.set(targetId, user);
    syncAndSaveDb();
  } else {
    let changed = false;
    if (username && user.username !== username) {
      user.username = username;
      changed = true;
    }
    if (firstName && user.first_name !== firstName) {
      user.first_name = firstName;
      changed = true;
    }
    if (photoUrl && user.photo_url !== photoUrl) {
      user.photo_url = photoUrl;
      changed = true;
    } else if (!user.photo_url && targetId === DEFAULT_USER_ID) {
      user.photo_url = '/logo.svg';
      changed = true;
    }
    if (changed) {
      syncAndSaveDb();
    }
  }
  return user;
}

// REST API Endpoints
app.get('/api/me', async (req: Request, res: Response) => {
  const user = getUser(req);
  if (!user) return unauthorized(res);
  const pendingTopup = Array.from(store.topups.values()).find(
    (t) => t.user_id === user.id && t.status === 'pending' && !isExpired(t)
  );

  const userOrders = Array.from(store.orders.values())
    .filter((o) => o.user_id === user.id)
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

  // Try live on-chain USDT balance check for admin wallet
  if (store.settings.wallet_address && store.settings.wallet_address.length > 20) {
    try {
      const tonRes = await fetch(
        `https://tonapi.io/v2/accounts/${store.settings.wallet_address}/jettons`,
        { headers: { Accept: 'application/json' }, signal: AbortSignal.timeout(2000) }
      );
      if (tonRes.ok) {
        const tonData = await tonRes.json();
        const usdt = tonData.balances?.find(
          (b: any) =>
            b.jetton?.symbol === 'USDT' ||
            b.jetton?.address?.includes('EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs')
        );
        if (usdt && usdt.balance) {
          const liveUsdt = Number(usdt.balance) / 10 ** 6;
          if (liveUsdt >= 0) {
            store.settings.wallet_usdt_balance = +liveUsdt.toFixed(2);
          }
        }
      }
    } catch (e) {
      // Ignore network timeout
    }
  }

  res.json({
    ok: true,
    user: {
      ...user,
      pending_topup: pendingTopup || null,
    },
    history: userOrders,
    contest: contestPayload(user.id),
    settings: store.settings,
  });
});

/**
 * To'lovga UNIQUE qo'shimcha qo'shadi (mijoz shu summani yuboradi).
 *
 * Nima uchun: bir nechta mijoz bir vaqtda bir xil summani yuborsa,
 * avtomatik moslashtirish chalkashadi — kimning to'lovi ekanini
 * aniqlab bo'lmaydi. Shu sababli har bir so'rovga ketma-ket raqam
 * qo'shiladi:
 *
 *     mijoz 1 000 so'm so'raydi  ->  1 000 + 1  =  1 001 so'm yuboradi
 *     mijoz 1 000 so'm so'raydi  ->  1 000 + 2  =  1 002 so'm yuboradi
 *
 * Mijoz balansiga FAQAT so'ralgan summa qo'shiladi (qo'shimcha
 * faqat moslashtirish uchun tegish hisoblanadi).
 */
let TOPUP_SEQ = 0;

/**
 * Chaqiruv BARCHA deklaratsiyalardan KEYIN bo'lishi shart —
 * aks holda TDZ: "Cannot access 'TOPUP_SEQ' before initialization"
 * (bu serverni butunlay o'ldiradi).
 */
loadTopupSequence();

function nextTopupSequence(): number {
  // Noldan boshlanmaslik uchun birga qo'shiladi
  return ++TOPUP_SEQ;
}

function loadTopupSequence(): number {
  // DB'da eng katta ketma-ket raqamni topamiz (restart'dan keyin
  // raqam qayta ishlatilmasligi kerak)
  let max = 0;
  for (const t of store.topups.values()) {
    const n = Number((t as any)?.seq) || 0;
    if (n > max) max = n;
  }
  TOPUP_SEQ = max;
  return max;
}

/**
 * expires_at ni millisekundga keltiradi.
 *
 * Nima uchun kerak: eski versiyalarda bot.py `time.time()` (SEKUND)
 * yozgan, server.ts esa `Date.now()` (MS) ishlatadi. Agar sekund qiymatni
 * to'g'ridan-to'g'ri solishtirsak — so'rov DARHOL "expired" bo'lib
 * qoladi (1.79e9 < 1.79e12), mijoz esa "eskirgan" xatosini oladi.
 * 10^11 dan kichik qiymat = sekund deb hisoblanadi.
 */
function expiresMs(t: any): number {
  const v = Number(t?.expires_at) || 0;
  if (v <= 0) return 0;
  return v < 1e11 ? v * 1000 : v;
}

/** So'rov muddati o'tganmi? */
function isExpired(t: any): boolean {
  const e = expiresMs(t);
  return e > 0 && Date.now() > e;
}

/**
 * NFT RENT — narx hisobi (bot.py bilan BIR XIL).
 * Mijozga: per day / rent / network fee / total.
 */
const NFT_MIN_DAYS = 3;
const NFT_MAX_DAYS = 50;
const NFT_NETWORK_FEE = 1700;
const NFT_QUICK_DAYS = [3, 7, 14, 30];

function nftQuote(daily: number, days: number) {
  const d = Math.max(NFT_MIN_DAYS, Math.min(NFT_MAX_DAYS, Number(days) || NFT_MIN_DAYS));
  const perDay = Math.max(0, Number(daily) || 0);
  const rent = perDay * d;
  return {
    days: d,
    per_day: perDay,
    rent,
    network_fee: NFT_NETWORK_FEE,
    total: rent + NFT_NETWORK_FEE,
    min_days: NFT_MIN_DAYS,
    max_days: NFT_MAX_DAYS,
  };
}

/**
 * Telegram `file_id` ni brauzerda ochiladigan URL ga aylantiradi.
 *
 * MUHIM: admin rasm YUBORSA (t.me/nft/... emas), `image` maydoniga
 * Telegram `file_id` saqlanadi. `<img src="AgACAgIAA...">` esa
 * hech qachon rasm ko'rsatmaydi — brauzer undan URL ni tushunmaydi.
 * Shu sabab `/api/nft-image/:id` orqali o'tkazamiz: u Bot API
 * `getFile` orqali haqiqiy CDN havolasini topadi va 302 qiladi.
 */
function isTelegramFileId(v: string): boolean {
  if (!v || /^https?:\/\//i.test(v)) return false;
  // Havola yoki boshqa matn (masalan "t.me/nft/xxx") — file_id emas
  if (/[\/\s]/.test(v)) return false;
  // file_id — base64url belgilaridan iborat, odatda 40+ belgi
  return /^[A-Za-z0-9_-]{20,}$/.test(v);
}

/** WebApp uchun rasm manzilini tayyorlaydi (to'g'ridan-to'g'ri yoki proxy). */
/**
 * Telegram sahifa havolalari — bular RASM EMAS, balki SPA sahifa.
 * `<img src="https://t.me/nft/FinePen">` brauzerda BUZILGAN rasm
 * ikonkasini ko'rsatadi (naturalWidth = 0). Shuning uchun ularni
 * rasm sifatida qabul qilmaymiz.
 *
 * Eslatma: server tomondan bu sahifalardan rasmni yuklab bo'lmaydi —
 * `t.me/nft/...` 302 bilan `telegram.org` ga qaytaradi, rasm esa
 * faqat klientda (Mini App) chiziladi. Shuning uchun rasmni admin
 * yuborishi kerak: `/admin → 🖼 Rasm qo'shish`.
 */
function isTelegramPageUrl(v: string): boolean {
  return /^https?:\/\/(?:[a-z0-9-]+\.)*(?:t\.me|telegram\.me|telegram\.dog|nft\.telegram\.org|fragment\.com)(?:[/?#]|$)/i.test(
    v,
  );
}

function nftImageUrl(n: any): string {
  const raw = String(n?.image || '').trim();
  if (!raw) return '';
  if (/^https?:\/\//i.test(raw)) {
    // t.me/nft/... — sahifa, rasm emas
    return isTelegramPageUrl(raw) ? '' : raw;
  }
  if (isTelegramFileId(raw)) return `/api/nft-image/${encodeURIComponent(n.id)}`;
  return '';
}

/**
 * Telegram `og:description` matnidan "Backdrop" ni ajratadi.
 *
 * Matn shakli: "Model: Solar Atlas / Backdrop: Chestnut /
 * Symbol: Carrot / Gifted to berkut"
 * 1-rasmdagi filtr shpitskalari ("Battleship Grey", "Black" ...)
 * aynan shu maydonni ifodalaydi.
 */
function nftBackdrop(desc: string): string {
  // 🔴 DIQQAT: ikkala tuzilish ham uchraydi:
  //   "Backdrop: Chestnut\nSymbol: Carrot"        (Telegram HAQIQIY format)
  //   "Model: X / Backdrop: Chestnut / Symbol: C"   (qisqa variant)
  // `\s` yang qatorni ham yutadi, `[^/]` esa newline ni YUTMAYDI —
  // ikkalasi birgalikda butun qoldiqni olib kelardi va WebApp'dagi
  // Backdrop filtrlari bitta gigant qiymatga yig'ilib, hech narsa
  // filtrlamay qolardi.
  // To'g'ri: bo'shliq faqat `[ \t]` bilan, qiymat `[^\n/]+`.
  const m = String(desc || '').match(/Backdrop:[ \t]*([^\n/]+)/i);
  return m ? m[1].trim() : '';
}

function nftPublicList(): any[] {
  const items = [...store.nfts.values()]
    .filter((n: any) => n?.active !== false)
    .map((n: any) => ({
      id: n.id,
      title: String(n.title || 'NFT sovg\'a'),
      number: n.number ?? null,
      image: nftImageUrl(n),
      link: n.link || '',
      backdrop: nftBackdrop(n.description),
      collection: n.collection || '',
      created_at: n.created_at || '',
      // Rasmdagi GIF/WebP animatsiyasi mavjudmi? (admin yuborgan bo'lsa)
      animated: !!n.image_animated,
      daily: Number(n.daily) || 0,
    }))
    .sort((a, b) => a.daily - b.daily);
  return items;
}

/**
 * Telegram fayl havolasini topish va keshlash.
 * Bot API `file_path` havolasi ~1 soatda muddati tugadi, shuning uchun
 * 30 daqiqa bilan qayta so'raymiz (har karta uchun emas — bitta misol uchun).
 */
const fileUrlCache = new Map<string, { url: string; at: number }>();
const FILE_URL_TTL = 30 * 60 * 1000;

async function telegramFileUrl(fileId: string): Promise<string | null> {
  const hit = fileUrlCache.get(fileId);
  if (hit && Date.now() - hit.at < FILE_URL_TTL) return hit.url;
  const token = (process.env.BOT_TOKEN || '').trim();
  if (!token) return null;
  try {
    const r = await fetch(`https://api.telegram.org/bot${token}/getFile?file_id=${encodeURIComponent(fileId)}`, {
      signal: AbortSignal.timeout(12000),
    });
    const j: any = await r.json();
    const path = j?.result?.file_path;
    if (!j?.ok || !path) return null;
    const url = `https://api.telegram.org/file/bot${token}/${path}`;
    fileUrlCache.set(fileId, { url, at: Date.now() });
    return url;
  } catch {
    return null;
  }
}

/** NFT rasmini beradi (Telegram faylidan yoki havoladan). */
app.get('/api/nft-image/:id', async (req: Request, res: Response) => {
  refreshNftsFromDisk();
  const item: any = store.nfts.get(String(req.params.id || ''));
  const raw = String(item?.image || '').trim();
  if (!raw) return res.status(404).json({ ok: false, error: 'Rasm yo\'q' });
  if (/^https?:\/\//i.test(raw)) return res.redirect(302, raw);
  if (!isTelegramFileId(raw)) return res.status(404).json({ ok: false, error: 'Rasm yo\'q' });
  const url = await telegramFileUrl(raw);
  if (!url) {
    return res.status(404).json({
      ok: false,
      error: 'Rasmni Telegram dan olib bo\'lmadi. Bot token tekshirilsin.',
    });
  }
  // Brauzer rasmni to'g'ridan-to'g'ri yuklaydi (server orasidan o\'tmaydi)
  res.redirect(302, url);
});

app.post('/api/topup', (req: Request, res: Response) => {
  const user = getUser(req);
  if (!user) return unauthorized(res);
  const amount = Number(req.body.amount);

  if (!amount || amount < 1000 || amount > 10000000) {
    return res.status(400).json({ ok: false, error: "1 000 dan 10 000 000 so'mgacha summa kiriting." });
  }

  // Cancel any existing pending topups
  for (const t of store.topups.values()) {
    if (t.user_id === user.id && t.status === 'pending') {
      t.status = 'cancelled';
    }
  }

  const id = 'top_' + Math.random().toString(36).slice(2, 9);
  // 60 daqiqa (eski 5 min edi — mijoz kartadan to'lab, keyin
  // "tekshirish" bosishi uchun vaqt yetmasdi)
  const expires_at = Date.now() + 60 * 60 * 1000;

  // Ketma-ket raqam: har bir so'rovga unikal qo'shimcha qo'shiladi
  // (masalan 1000 + 39 = 1039) — avtomatik moslashtirish chalkashmasligi uchun
  const seq = nextTopupSequence();
  const amountToSend = amount + seq;

  const newTopup = {
    id,
    user_id: user.id,
    amount,            // mijoz so'ragan (balansga SHU qo'shiladi)
    seq,               // ketma-ket raqam
    amount_to_send: amountToSend,  // mijoz kartaga yuborishi KERAK
    status: 'pending',
    card: store.settings.card_number,
    holder: store.settings.card_holder,
    expires_at,
    expires_in: 3600,
    created_at: new Date().toISOString(),
  };

  store.topups.set(id, newTopup);
  // MUHIM: so'rov darhol faylga yoziladi — bot.py dagi userbot shu topupni
  // ko'rib, bank xabarini kelganda avtomatik balansga qo'shadi.
  syncAndSaveDb();
  res.json({ ok: true, topup: newTopup });
});

app.get('/api/topup/status', (req: Request, res: Response) => {
  const id = req.query.id as string;
  const user = getUser(req);
  if (!user) return unauthorized(res);
  const topup = store.topups.get(id);

  if (!topup) {
    return res.status(404).json({ ok: false, error: 'Top-up topilmadi.' });
  }
  // 🔴 EGALIK: boshqa mijozning to'lovini ko'rish/o'chirish mumkin
  // emas edi (kartasi va summasi ochiq chiqardi).
  if (Number(topup.user_id) !== Number(user.id)) {
    return res.status(403).json({ ok: false, error: "Bu to'lov sizniki emas." });
  }

  if (topup.status === 'pending' && isExpired(topup)) {
    topup.status = 'expired';
    syncAndSaveDb();
  }

  res.json({
    ok: true,
    topup: {
      ...topup,
      expires_in: Math.max(0, Math.floor((expiresMs(topup) - Date.now()) / 1000)),
    },
    balance: user.balance,
  });
});

app.post('/api/topup/cancel', (req: Request, res: Response) => {
  // 🔐 Bu MIJOZ tugmasi ("Bekor qilish"), admin emas. Egalik tekshiriladi.
  const user = getUser(req);
  if (!user) return unauthorized(res);
  const id = req.body.id;
  const topup = store.topups.get(id);
  // 🔴 EGALIK: boshqaning to'lovini bekor qilish mumkin emas edi
  if (!topup) return res.status(404).json({ ok: false, error: 'Top-up topilmadi.' });
  if (Number(topup.user_id) !== Number(user.id)) {
    return res.status(403).json({ ok: false, error: 'Bu to\'lov sizniki emas.' });
  }
  if (topup.status === 'pending') {
    topup.status = 'cancelled';
    topup.cancelled_at = new Date().toISOString();
    syncAndSaveDb();
  }
  res.json({ ok: true, topup, balance: Number(user.balance) || 0 });
});

// Bank xabarlari (humocardbot userbot orqali) avtomatik tasdiqlaydi.
// Bu endpoint endi to'lovni darhol qo'shmaydi — faqat statusni tekshiradi
// va admini xabardor qiladi.
app.post('/api/topup/simulate-pay', async (req: Request, res: Response) => {
  const id = req.body.id;
  const user = getUser(req);
  if (!user) return unauthorized(res);
  const topup = store.topups.get(id);

  if (!topup) {
    return res.status(404).json({ ok: false, error: "To'lov so'rovi topilmadi" });
  }
  // 🔴 EGALIK
  if (Number(topup.user_id) !== Number(user.id)) {
    return res.status(403).json({ ok: false, error: "Bu to'lov sizniki emas." });
  }

  if (topup.status === 'completed') {
    return res.json({
      ok: true,
      message: `✅ ${topup.amount.toLocaleString()} UZS balansga muvaffaqiyatli qo'shildi!`,
      topup,
      balance: user.balance,
    });
  }

  if (topup.status === 'pending' && isExpired(topup)) {
    topup.status = 'expired';
    syncAndSaveDb();
    return res.status(400).json({
      ok: false,
      error: "So'rov muddati tugagan. Qayta urinib ko'ring — yangi so'rov yarating.",
      expired: true,
    });
  }

  if (topup.status !== 'pending') {
    return res.status(400).json({ ok: false, error: "Bu to'lov allaqachon yakunlangan yoki bekor qilingan." });
  }

  // Avto-to'lov hali qayd etilmagan — admini so'rov bilan xabardor qilamiz
  const adminId = store.settings.admin_id || 8307046273;
  const token = process.env.BOT_TOKEN;
  if (token) {
    try {
      const tgRes = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          chat_id: adminId,
          text: `🧾 <b>To'lovni tasdiqlash so'rovi</b>\n\n👤 User ID: <code>${topup.user_id}</code>\n💰 Summa: <b>${topup.amount.toLocaleString()} UZS</b>\n🆔 <code>${topup.id}</code>\n\n@humocardbot da mos xabar topilmadi. Tasdiqlaysizmi?`,
          parse_mode: 'HTML',
          reply_markup: {
            inline_keyboard: [
              [
                { text: '✅ Tasdiqlash', callback_data: `adm_topup_ok:${topup.id}` },
                { text: '❌ Rad etish', callback_data: `adm_topup_no:${topup.id}` },
              ],
            ],
          },
        }),
      });
      if (!tgRes.ok) console.error('Admin xabarini yuborishda xato:', await tgRes.text());
    } catch (e) {
      console.error('Admin xabarini yuborishda xato:', e);
    }
  }

  res.json({
    ok: true,
    pending: true,
    message: "⏳ To'lov tekshirilmoqda. Admin tasdiqlashi kerak, iltimos kuting...",
    topup,
  });
});

app.post('/api/order', async (req: Request, res: Response) => {
  const user = getUser(req);
  if (!user) return unauthorized(res);
  const { kind, amount, months, gift, username, hide_my_name } = req.body;

  let price = 0;
  let title = '';
  // Qabul qiluvchini tozalaydi — mijoz shunday shakllarda kiritishi mumkin:
  //   @bobur | bobur | https://t.me/bobur | t.me/bobur/ | "bobur "
  // Avval faqat bitta "@" olib tashlanardi va t.me havolalari to'liq
  // saqlanardi -> Telegram'da qabul qiluvchi topilmasdi va gift yuborilmasdi.
  let recipient = (username || '')
    .trim()
    .replace(/^(?:https?:\/\/)?(?:t|telegram)\.(?:me|dog)\//i, '')
    .replace(/^@+/, '')
    .replace(/\/+$/, '')
    .replace(/[^A-Za-z0-9_]/g, '')
    .slice(0, 32);

  if (!recipient) {
    return res.status(400).json({ ok: false, error: "Qabul qiluvchi Telegram username'ni kiriting." });
  }

  // 🔴 SUN'IY USERNAME RAD QILINADI.
  // Eski kod yangi (serverda yo'q) foydalanuvchiga `user_XXXX`
  // username yozardi. "O'zimga" bosilganda shu yuborilardi, server
  // har qanday bo'sh bo'lmagan string'ni qabul qilib UZS ni yechardi,
  // so'ng Fragment ishlamay qolardi -> pul ketgan, hech narsa kelmagan.
  if (/^user_\d+$/i.test(recipient)) {
    return res.status(400).json({
      ok: false,
      error: 'Telegram akkauntingizda username yo\'q. Botga /start yozib, '
        + 'username o\'rnatasiz — keyin "O\'zimga" ishlaydi.',
    });
  }
  // 🔴 Faqat raqam (Telegram ID) qabul qilinmaydi — bu Stars yuborish
  // uchun noto'g'ri ma'lumot va Fragment ishlamaydi.
  if (/^\d+$/.test(recipient)) {
    return res.status(400).json({
      ok: false,
      error: 'Qabul qiluvchi Telegram username (masalan @bobur) bo\'lishi kerak, '
        + 'ID emas.',
    });
  }

  if (kind === 'stars') {
    const starCount = Number(amount);
    if (!starCount || starCount < 50 || starCount > 1000000) {
      return res.status(400).json({ ok: false, error: "Minimal 50 ta, maksimal 1 000 000 ta Stars sotib olish mumkin." });
    }
    price = starCount * store.settings.star_buy_price;
    title = `⭐ ${starCount.toLocaleString()} Telegram Stars`;
  } else if (kind === 'premium') {
    const m = Number(months);
    const mode = req.body.mode || 'nologin';
    const plans: Record<string, Record<number, number>> = {
      nologin: { 3: 155000, 6: 205000, 12: 375000 },
      login: { 1: 40000, 12: 285000 },
    };
    price = plans[mode]?.[m] || 0;
    if (!price) {
      return res.status(400).json({ ok: false, error: "Noto'g'ri tarif tanlandi." });
    }
    title = `💎 Telegram Premium (${m} oy - ${mode === 'nologin' ? "Sovg'a" : 'Kirib'})`;
  } else if (kind === 'gift') {
    const giftsCatalog: Record<string, { name: string; price: number; stars: number }> = {
      bear: { name: '🧸 Ayiqcha', price: 3000, stars: 15 },
      heart: { name: '💝 Yurakcha', price: 3000, stars: 15 },
      box: { name: "🎁 Sovg'a qutisi", price: 6000, stars: 25 },
      rose: { name: '🌹 Atirgul', price: 6000, stars: 25 },
      cake: { name: '🎂 Tort', price: 10000, stars: 50 },
      bouquet: { name: '💐 Gul dastasi', price: 10000, stars: 50 },
      rocket: { name: '🚀 Raketa', price: 10000, stars: 50 },
      cup: { name: '🏆 Kubok', price: 20000, stars: 100 },
      ring: { name: '💍 Uzuk', price: 20000, stars: 100 },
      diamond: { name: '💎 Olmos', price: 20000, stars: 100 },
      champagne: { name: '🍾 Shampan', price: 10000, stars: 50 },
    };
    const item = giftsCatalog[gift];
    if (!item) {
      return res.status(400).json({ ok: false, error: "Sovg'a turi topilmadi." });
    }
    price = item.price;
    title = `${item.name} (${item.stars} ⭐)`;
  } else {
    return res.status(400).json({ ok: false, error: "Noma'lum xizmat turi." });
  }

  if (user.balance < price) {
    return res.status(402).json({
      ok: false,
      error: `Balans yetarli emas. Narx: ${price.toLocaleString()} UZS, Balansingiz: ${user.balance.toLocaleString()} UZS. Avval balansni to'ldiring.`,
    });
  }

  user.balance -= price;
  user.total_spent += price;
  store.settings.total_orders += 1;

  // 0.1% cashback
  const cashback = Math.floor(price * 0.001);
  if (cashback > 0) {
    user.balance += cashback;
  }

  const orderId = 'ord_' + Math.random().toString(36).slice(2, 9);
  let orderStatus: 'completed' | 'processing' | 'pending_admin' = 'completed';
  let orderMessage = `✅ Buyurtma qabul qilindi va muvaffaqiyatli yetkazildi! ${cashback > 0 ? `+${cashback} so'm keshbek berildi!` : ''}`;
  let failureReason: string | undefined = undefined;

  // Stars FAQAT USDT (TON) orqali Fragment'dan xarid qilinadi.
  // WebApp stub emas — buyurtma bazaga yoziladi, bot.py dagi star_order_worker()
  // uni olib, haqiqiy Fragment USDT to'lovini amalga oshiradi.
  if (kind === 'stars') {
    const starCount = Number(amount);
    orderStatus = 'processing';
    const usdtNeeded = await starsToUsdt(starCount, store.settings.star_usdt_rate || 0.015);
    orderMessage =
      `⏳ <b>Buyurtmangiz qabul qilindi!</b>\n\n` +
      `⭐ Miqdor: <b>${starCount.toLocaleString()} Stars</b>\n` +
      `👤 Qabul qiluvchi: <b>@${recipient}</b>\n` +
      `💳 Yechildi: <b>${price.toLocaleString()} UZS</b>\n` +
      `🆔 <code>${orderId}</code>\n\n` +
      `📦 Stars <b>avtomatik tarzda yuborilmoqda</b> — 1–5 daqiqa ichida ` +
      `hisobingizga tushadi.\n⏳ Sabr qiling, xabarni kuting.`;

    sendTelegramMessage(
      store.settings.admin_id || 8307046273,
      `⭐ <b>Yangi Stars buyurtmasi (WebApp)</b>\n\n` +
        `📦 Buyurtma: <code>#${orderId}</code>\n` +
        `👤 Mijoz: @${user.username} (ID: <code>${user.id}</code>)\n` +
        `🎯 Qabul qiluvchi: <b>@${recipient}</b>\n` +
        `⭐ Miqdor: <b>${starCount.toLocaleString()} Stars</b>\n` +
        `💳 Yechilgan: <b>${price.toLocaleString()} UZS</b>\n` +
        `💎 Taxminiy sarf: <b>${usdtNeeded} USDT (TON)</b>\n\n` +
        `🤖 <i>bot.py worker orqali USDT bilan Fragment'da avtomatik xarid qilinadi.</i>`
    );


    // Rasmdagi formatda ORDERS_CHANNEL kanaliga
    postToOrdersChannel(
      channelOrderText({
        title: 'Stars olindi',
        username: `@${user.username || user.id}`,
        amountText: `Miqdor: ${starCount} ⭐`,
        price,
        cashback,
      }),
    ).catch(() => undefined);

    postToOrdersChannel(
      channelOrderText({
        title: 'Stars olindi',
        username: `@${user.username || user.id}`,
        amountText: `Miqdor: ${starCount} \u2B50`,
        price,
        cashback,
      }),
    ).catch(() => undefined);
  } else if (kind === 'premium') {
    // 🔴 ILGARI: `orderStatus` 'completed' bo'lib qolardi va mijozga
    // "yetkazildi" degan xabar yuborilardi — lekin Telegram Premium
    // berish AVTOMATIK emas, admin qo'lda beradi. Natijada mijoz
    // pulini to'lab, HECH NARSA olmay qolardi va xato xabar olardi.
    // Endi: 'processing' + admin darhol xabar beriladi.
    orderStatus = 'processing';
    const pm = Number(months);
    const pmMode = req.body.mode === 'login' ? 'login' : 'nologin';
    orderMessage =
      `\u23f3 <b>Buyurtmangiz qabul qilindi!</b>\n\n` +
      `\ud83d\udc8e Premium: <b>${title}</b>\n` +
      `\ud83d\udc64 Kimga: <b>@${recipient}</b>\n` +
      `\ud83d\udcb3 Yechildi: <b>${price.toLocaleString()} UZS</b>\n` +
      `\ud83c\udd94 <code>${orderId}</code>\n\n` +
      `\ud83d\udce6 Premium <b>bir necha soat</b> ichida beriladi.\n` +
      `\u23f3 Telegram hisobingizga xabar keladi. Sabr qiling.`;

    sendTelegramMessage(
      store.settings.admin_id || 8307046273,
      `\ud83d\udc8e <b>Yangi PREMIUM buyurtmasi!</b>\n\n` +
        `\ud83d\udcc4 Buyurtma: <code>#${orderId}</code>\n` +
        `\ud83d\udc64 Mijoz: @${user.username} (ID: <code>${user.id}</code>)\n` +
        `\ud83c\udfaf Qabul qiluvchi: <b>@${recipient}</b>\n` +
        `\ud83c\udf20 Rejim: <b>${pmMode === 'login' ? "Kirib (login)" : 'Sovg\'a (nologin)'}</b>, ` +
        `<b>${pm} oy</b>\n` +
        `\ud83d\udcb3 Yechilgan: <b>${price.toLocaleString()} UZS</b>\n\n` +
        `\ud83e\uddea <i>Berib bo\'lgach: /admin \u2192 \ud83d\udc8e Premium buyurtmalari \u2192 ` +
        `\u2705 Berildi</i>`
    );
  } else if (kind === 'gift') {
    // Gift userbot orqali ASINCHRON yuboriladi — darhol "yetkazildi" degani
    // NOTO'G'RI bo'lardi (mijoz pulini to'lab, hech narsa olmay qolardi).
    orderStatus = 'processing';
    orderMessage =
      `\u23f3 <b>Buyurtmangiz qabul qilindi!</b>\n\n` +
      `\ud83c\udf81 Sovg'a: <b>${title}</b>\n` +
      `\ud83d\udc64 Qabul qiluvchi: <b>@${recipient}</b>\n` +
      `\ud83d\udcb3 Yechildi: <b>${price.toLocaleString()} UZS</b>\n` +
      `\ud83c\udd94 <code>${orderId}</code>\n\n` +
      `\ud83d\udce6 Sovg'a <b>avtomatik yuborilmoqda</b> — 1\u20135 daqiqa ichida ` +
      `Telegram hisobingizga tushadi.\n\u23f3 Sabr qiling, xabarni kuting.`;
    // Notify admin / userbot for automated gift dispatch
    sendTelegramMessage(
      store.settings.admin_id || 8307046273,
      `🎁 <b>Yangi Gift buyurtmasi!</b>\n\n` +
      `📦 Buyurtma: <code>#${orderId}</code>\n` +
      `👤 Mijoz: @${user.username} (ID: <code>${user.id}</code>)\n` +
      `🎯 Qabul qiluvchi: <b>@${recipient}</b>\n` +
      `🎁 Sovg'a: <b>${title}</b>\n` +
      `💳 Summa: <b>${price.toLocaleString()} UZS</b>\n\n` +
      `🤖 <i>Userbot orqali yetkazilmoqda...</i>`
    );
  }

  const newOrder = {
    id: orderId,
    user_id: user.id,
    kind,
    title,
    recipient,
    price,
    price_uzs: price,
    amount: amount || months || 1,
    stars: kind === 'stars' ? Number(amount) : undefined,
    gift: kind === 'gift' ? gift : undefined,
    // 🔴 Premium: bot qancha oy va qanday rejim (Sovg'a / Kirib) berishini
    // bilishi SHART. Ilgari saqlanmagandi — buyurtma yaratilgan va
    // "yetkazildi" deb yozilgan, lekin hech kim qilmaydigan ish qolardi.
    months: kind === 'premium' ? Number(months) : undefined,
    mode: kind === 'premium' ? (req.body.mode || 'nologin') : undefined,
    // Sovg'a maxfiyligi.
    // UI "🕶️ Anonim" tanlangan bo'lsa true. Semantika:
    //   true  -> Telegram hide_my_name=True  -> profil YASHIRILADI (anonim)
    //   false -> Telegram hide_my_name=False -> do'kon profili KO'RINADI
    // (Telegram MTProto: InputInvoiceStarGift.hide_name = flags.0?true)
    anon: kind === 'gift' ? Boolean(hide_my_name) : undefined,
    hide_my_name: kind === 'gift' ? Boolean(hide_my_name) : undefined,
    status: orderStatus,
    source: 'webapp',
    payment_method: 'usdt_ton',
    failure_reason: failureReason,
    created_at: new Date().toISOString(),
  };

  store.orders.set(orderId, newOrder);

  // 🔴 TARIX: Stars / Premium / Gift xaridlari WebApp'da KO'RINMASDI.
  // Faqat `nft_rent` qo'lda yozilgan edi. Natijada mijoz
  // "xarid qildim, lekin tarixda yo'q" deb ko'rardi.
  // Botdagi `add_history` bilan BIR XIL formatda yozamiz
  // (bot.py: `HISTORY_LIMIT = 100`).
  try {
    const hist: any[] = Array.isArray(user.history) ? user.history : [];
    hist.push({
      type: kind,                       // "stars" | "premium" | "gift"
      amount: -price,                   // yechilgan summa (manfiy)
      cashback: cashback > 0 ? cashback : undefined,
      details: title,
      date: new Date().toISOString(),
    });
    user.history = hist.slice(-100);    // bot.py dagi HISTORY_LIMIT
  } catch {
    /* tarix — qo'shimcha, xatoga olib kelmasligi kerak */
  }

  syncAndSaveDb();

  res.json({
    ok: true,
    message: orderMessage,
    order: newOrder,
    balance: user.balance,
  });
});

// USDT (TON) kursi — live API + ENV zaxira
/**
 * 🔴 Fragment CDN — 1500x1500 rasmlar.
 *
 * `og:image` har doim 160x160 THUMBNAIL beradi — telefon ekranida
 * (devicePixelRatio 3) juda xira ko'rinadi. Fragment'ning o'z CDN'i
 * esa to'liq o'lchamni beradi:
 *     https://nft.fragment.com/gift/finepen-18272.webp  ->  1500x1500
 *
 * ⚠️ Slug qoidasi: KICHIK harf, so'zlar BIRGA (chiziqcha yo'q).
 *     FinePen-18272 -> finepen-18272       ✅
 *     homemade-cake-2976 -> 404             ❌
 *
 * Production'dagi 38 ta NFT tekshirildi: 38/8 -> 1500x1500.
 */
const NFT_HD_BASE = 'https://nft.fragment.com/gift/';

function nftHdUrl(link: string): string {
  const m = /\/nft\/([^/?#]+)/i.exec((link || '').split('?')[0]);
  if (!m) return '';
  // 🔴 TO'LIQ slug (nom + raqam). Faqat nom -> 404.
  return `${NFT_HD_BASE}${m[1].toLowerCase()}.webp`;
}

/** HEAD bilan tekshiradi (arzon, rasm yuklamaydi). */
async function nftHdExists(url: string): Promise<boolean> {
  if (!url) return false;
  try {
    const r = await fetch(url, {
      method: 'HEAD',
      headers: { 'User-Agent': NFT_UA },
      signal: AbortSignal.timeout(10000),
    });
    if (!r.ok) return false;
    return (r.headers.get('content-type') || '').toLowerCase().startsWith('image/');
  } catch {
    return false;
  }
}

/**
 * 🔗 Telegram NFT sahifasidan rasmni olish.
 *
 * `https://t.me/nft/FinePen-18272` server tomonda `og:image` beradi
 * (`cdn*.telesco.pe`). `<img src="t.me/...">` esa hech qachon rasm
 * ko'rsatmaydi — bu SPA sahifa.
 *
 * DIQQAT: raqamsiz havola (`/nft/FinePen`) 302 qaytaradi va rasm
 * yo'q. Faqat haqiqiy NFT (raqam bilan) rasm beradi.
 */
const NFT_UA =
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 ' +
  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';

/** Kesh: link -> { image, title, number } (telesco.pe URLlari barqaror) */
const nftPageCache = new Map<string, { data: any; at: number }>();
const NFT_PAGE_TTL = 6 * 60 * 60 * 1000; // 6 soat

async function resolveNftPage(link: string): Promise<any | null> {
  if (!isTelegramPageUrl(link)) return null;
  const url = link.trim();
  const hit = nftPageCache.get(url);
  if (hit && Date.now() - hit.at < NFT_PAGE_TTL) return hit.data;
  try {
    const r = await fetch(url, {
      // DIQQAT: redirect qilmaymiz — 302 Telegram sahifa emas,
      // demak rasm ham yo'q. Aks holda telegram.org sahifasini
      // tekshirib vaqt yo'qotamiz.
      redirect: 'manual',
      headers: { 'User-Agent': NFT_UA, Accept: 'text/html' },
      signal: AbortSignal.timeout(12000),
    });
    if (r.status !== 200) {
      nftPageCache.set(url, { data: null, at: Date.now() });
      return null;
    }
    const html = (await r.text()).slice(0, 200000);
    const meta = (p: string): string => {
      const re1 = new RegExp(
        `<meta[^>]+property=["']${p}["'][^>]+content=["']([^"']+)`,
        'i',
      );
      const re2 = new RegExp(
        `<meta[^>]+content=["']([^"']+)["'][^>]+property=["']${p}["']`,
        'i',
      );
      const m = html.match(re1) || html.match(re2);
      return m ? m[1].trim() : '';
    };
    // 🔴 AVVAL 1500x1500 Fragment CDN, keyin 160px og:image.
    let hd = '';
    const hdCandidate = nftHdUrl(url);
    if (hdCandidate && (await nftHdExists(hdCandidate))) hd = hdCandidate;
    let image = hd || meta('og:image');
    if (!image.startsWith('http')) {
      nftPageCache.set(url, { data: null, at: Date.now() });
      return null;
    }
    const rawTitle = meta('og:title');
    const numMatch = rawTitle.match(/#(\d+)\s*$/);
    const data = {
      image,
      imageHd: !!hd,
      title: rawTitle.replace(/\s*#\d+\s*$/, '').trim(),
      number: numMatch ? Number(numMatch[1]) : null,
      description: meta('og:description'),
    };
    nftPageCache.set(url, { data, at: Date.now() });
    return data;
  } catch {
    return null;
  }
}

/**
 * NFT ro'yxatini chiqarishdan OLDIN rasmni to'ldiradi.
 *
 * Eski NFT'lar (bot.py resolveri qo'shilgidan OLDIN qo'shilgan)
 * `image` maydonida t.me linki saqlagan bo'ladi. Ular uchun
 * shu yerda, so'rov paytida rasm topiladi va NATIJAGA yoziladi
 * (keyingi so'rovlarda tez bo'ladi).
 */
async function nftPublicListResolved(): Promise<any[]> {
  const list = nftPublicList();
  await Promise.all(
    list.map(async (item: any) => {
      const raw = String(item.link || '').trim();
      if (!isTelegramPageUrl(raw)) return;
      // 🔴 ESKI (160px telesco.pe) rasmni HD ga ALMASHTIRAMIZ.
      // Sabab: eski resolver og.image (160x160) saqlagan edi va
      // telefon ekranida juda XIRA ko'rinardi. Endi 1500x1500.
      if (item.image && !/telesco\.pe/i.test(item.image)) return;
      if (item.image && /fragment\.com/i.test(item.image)) return; // allaqachon HD
      const got = await resolveNftPage(raw);
      if (!got?.image) return;
      // Bazaga yozamiz — keyingi so'rovlarda qayta yuklamaydi
      const stored: any = store.nfts.get(item.id);
      if (stored) {
        stored.image = got.image;
        if (!stored.title && got.title) stored.title = got.title;
        if (stored.number == null && got.number != null) stored.number = got.number;
        if (!stored.description && got.description) stored.description = got.description;
        try {
          syncAndSaveDb();
        } catch {
          /* yozilmasa ham joriy so'rovda ko'rinadi */
        }
      }
      item.image = got.image;
      if (!item.title || item.title === "NFT sovg'a") item.title = got.title || item.title;
      if (item.number == null) item.number = got.number;
    }),
  );
  return list;
}

/**
 * 🔄 Rasmni qayta olish (self-healing).
 *
 * `cdn*.telesco.pe` havolalari muddati tugishi mumkin. Rasm
 * yuklanmasa brauzer shu endpoint ga murojaat qiladi va biz
 * Telegram sahifasidan yangisini olib, bazaga yozamiz.
 */
app.post('/api/nfts/refresh-image/:id', async (req: Request, res: Response) => {
  refreshNftsFromDisk();
  const id = String(req.params.id || '');
  const item: any = store.nfts.get(id);
  if (!item) return res.status(404).json({ ok: false, error: 'NFT topilmadi.' });
  const link = String(item.link || '').trim();
  if (!isTelegramPageUrl(link)) {
    return res.json({ ok: true, image: item.image ? nftImageUrl(item) : '' });
  }
  // keshni tashlaymiz — majburlangan yangilash
  nftPageCache.delete(link);
  const got = await resolveNftPage(link);
  if (!got?.image) return res.json({ ok: true, image: '' });
  item.image = got.image;
  if (!item.title && got.title) item.title = got.title;
  if (item.number == null && got.number != null) item.number = got.number;
  if (!item.description && got.description) item.description = got.description;
  try {
    syncAndSaveDb();
  } catch {
    /* yozilmasa ham joriy javobda qaytariladi */
  }
  res.json({ ok: true, image: got.image, title: item.title, number: item.number ?? null });
});

/** NFT ro'yxati (WebApp NFT Rent bo'limi uchun) */
app.get('/api/nfts', async (_req: Request, res: Response) => {
  getUser(_req);
  refreshNftsFromDisk();
  res.json({
    ok: true,
    items: await nftPublicListResolved(),
    min_days: NFT_MIN_DAYS,
    max_days: NFT_MAX_DAYS,
    network_fee: NFT_NETWORK_FEE,
    quick_days: NFT_QUICK_DAYS,
  });
});

/** NFT ijaraga olish hisobi (muddat -> to'liq summa) */
app.get('/api/nfts/quote', (req: Request, res: Response) => {
  getUser(req);
  refreshNftsFromDisk();
  const id = String(req.query.id || '');
  const days = Number(req.query.days) || NFT_MIN_DAYS;
  const item: any = store.nfts.get(id);
  if (!item || item.active === false) {
    return res.status(404).json({ ok: false, error: 'NFT topilmadi.' });
  }
  const q = nftQuote(Number(item.daily) || 0, days);
  const u = getUser(req);
  if (!u) return unauthorized(res);
  res.json({ ok: true, quote: q, balance: Number(u.balance) || 0, item: {
    id: item.id, title: item.title, number: item.number ?? null,
    image: nftImageUrl(item), link: item.link || '',
  } });
});


/**
 * NFT ijarani rasmiy yopish — BITTA odam.
 *
 * 🔴 DIQQAT: avval menedjer username'i `NFT_MANAGER_USERNAME` ENV dan
 * olinardi va bu `bot.py` dagi `NFT_MANAGER` bilan MOS EMAS EDI
 * (`@saidovmanajer` vs `@saidovManajer`). Telegram username'lar
 * registrga sezgir — bitta harf farq bo'lsa, xabar butunlay boshqa
 * odamga boradi. Endi IKKALASI ham `NFT_MANAGER` ENV dan olinadi va
 * bir xil nomlanadi.
 */
const NFT_MANAGER = (process.env.NFT_MANAGER || '@saidovManajer').trim();

/**
 * Sizning Telegram nomingiz — xabarda «Kim yubordi» sifatida
 * ko'rinadi.
 *
 * 🔴 MANBA ZARBIRASI (avval shunday edi):
 *   `process.env.ADMIN_USERNAME || 'admin'` — Railway'da bu ENV yo'q
 *   bo'lsa NFT xabarida `«Kim yubordi: @admin»` chiqardi (soxta).
 *
 * Endi zaxira manbalar ketma-ket sinanadi:
 *   1) `ADMIN_USERNAME` / `ADMIN_HANDLE` ENV
 *   2) `settings.admin_username` (bot.py yoki admin panel yozgan bo'lsa)
 *   3) `users[settings.admin_id].username` — haqiqiy adminning bazadagi nomi
 *   4) `normuzb` — oxirgi zaxira
 *
 * DIQQAT: `store` `loadDatabase()` dan keyin to'lgani uchun bu
 * qiymat `nftPublicListResolved()` ishga tushgandan KEYIN
 * `adminHandle()` orqali olinadi (modul darajasida emas).
 */
function adminHandle(): string {
  const fromEnv = (process.env.ADMIN_USERNAME || process.env.ADMIN_HANDLE || '')
    .trim().replace(/^@/, '');
  if (fromEnv) return fromEnv;
  const st: any = store.settings || {};
  const fromSettings = String(st.admin_username || '').replace(/^@/, '').trim();
  if (fromSettings) return fromSettings;
  const adminId = Number(st.admin_id || DEFAULT_USER_ID);
  const rec: any = (store.users || new Map()).get(adminId);
  const fromUser = String((rec && rec.username) || '').replace(/^@/, '').trim();
  if (fromUser) return fromUser;
  return 'normuzb';
}

// =============================================================================
// 🔗 BOT NOMI — runtime'da aniqlanadi
// =============================================================================
// 📐 NIMA UCHUN?
// Telegram Login Widget bot NOMINI talab qiladi
// (`data-telegram-login="..."`). Vite build vaqtidagi
// `VITE_BOT_USERNAME` ga bog'liq qilsak, Railway ENV build paytida
// berilmasa ilova noto'g'ri nom bilan chiqadi — va hech kim
// ro'yxatdan o'ta olmaydi.
//
// Yechim: server `BOT_TOKEN` orqali Telegram API ga `getMe` so'rovi
// yuborib nomni o'zi aniqlaydi (javob 1 soatga keshlanadi).
// =============================================================================

let botUsernameCache: { value: string; at: number } | null = null;

async function resolveBotUsername(): Promise<string> {
  // 1) kesh (1 soat)
  if (botUsernameCache && Date.now() - botUsernameCache.at < 3_600_000
      && botUsernameCache.value) {
    return botUsernameCache.value;
  }
  // 2) aniq ENV (qo'lda berilgan bo'lsa)
  const fromEnv = (process.env.BOT_USERNAME || '').trim().replace(/^@/, '');
  if (fromEnv) {
    botUsernameCache = { value: fromEnv, at: Date.now() };
    return fromEnv;
  }
  // 3) 🔗 BAZADAN — bot.py o'z nomini `getMe` orqali olib
  //    yozadi (`settings.bot_username`). Bu eng ishonchli manba:
  //    nom allaqachon tekshirilgan va bot ishga tushganda mavjud bo'ladi.
  //    Aks holda mijoz Login Widget tugmasini umuman KO'RMASDI.
  const fromDb = String(
    (store.settings as any)?.bot_username || ""
  ).trim().replace(/^@/, "");
  if (fromDb) {
    botUsernameCache = { value: fromDb, at: Date.now() };
    return fromDb;
  }
  // 4) Telegram API — `getMe`
  const token = (process.env.BOT_TOKEN || '').trim();
  if (token) {
    try {
      const r = await fetch(`https://api.telegram.org/bot${token}/getMe`, {
        signal: AbortSignal.timeout(10_000),
      });
      const j: any = await r.json();
      const uname = String(j?.result?.username || '').replace(/^@/, '');
      if (j?.ok && uname) {
        botUsernameCache = { value: uname, at: Date.now() };
        return uname;
      }
    } catch {
      /* tarmoq yo'q — quyidagiga qaytamiz */
    }
  }
  return "";
}

/**
 * 🔗 Ommaviy sozlama — Telegram ichida ham, brauzerda ham
 * kerak (Login Widget bot nomini oladi).
 */
app.get("/api/config", async (_req: Request, res: Response) => {
  try {
    const username = await resolveBotUsername();
    res.json({
      ok: true,
      bot_username: username,
      support_username: (process.env.SUPPORT_USERNAME || "").replace(/^@/, ""),
    });
  } catch (e) {
    res.status(500).json({ ok: false, error: String((e as Error)?.message || e) });
  }
});

/**
 * NFT ijaraga olish buyurtmasi.
 *
 * Mijoz "Sotib olish" bosganida:
 *   • balansdan summa yechiladi
 *   • buyurtma yaratiladi (status: pending)
 *   • ADMIN va @saidovManajer ga xabar boradi:
 *       NFT linki, muddat, narx, mijoz username
 * Menejer mijoz bilan tez orada bog'lanadi va Fragment orqali
 * ulaydi.
 */
app.post('/api/nfts/rent', async (req: Request, res: Response) => {
  const user = getUser(req);
  if (!user) return unauthorized(res);
  refreshNftsFromDisk();
  const id = String(req.body?.id || '');
  const days = Number(req.body?.days) || NFT_MIN_DAYS;

  const item: any = store.nfts.get(id);
  if (!item || item.active === false) {
    return res.status(404).json({ ok: false, error: 'NFT topilmadi.' });
  }

  const q = nftQuote(Number(item.daily) || 0, days);
  if (q.days < NFT_MIN_DAYS || q.days > NFT_MAX_DAYS) {
    return res.status(400).json({
      ok: false,
      error: `Muddat ${NFT_MIN_DAYS}–${NFT_MAX_DAYS} kun oralig'ida bo'lishi kerak.`,
    });
  }

  if (Number(user.balance) < q.total) {
    return res.status(402).json({
      ok: false,
      error: `Balans yetarli emas. Kerak: ${q.total.toLocaleString()} UZS, `
           + `balansingiz: ${Number(user.balance).toLocaleString()} UZS.`,
      need_topup: true,
      required: q.total,
      balance: Number(user.balance),
    });
  }

  // Balansdan yechamiz
  user.balance = Number(user.balance) - q.total;
  user.total_spent = Number(user.total_spent || 0) + q.total;

  // Botdagi "📜 Tarix" ro'yxatiga ham yozamiz — mijoz WebApp'da
  // ko'rmagan amalini bot orqali ko'ra olsin.
  // Formati bot.py dagi JsonDB.add_history bilan BIR XIL.
  try {
    const hist: any[] = Array.isArray(user.history) ? user.history : [];
    hist.push({
      type: 'nft_rent',
      amount: -q.total,
      details: `NFT ijarasi: ${item.title}${item.number != null ? ` #${item.number}` : ''} · ${q.days} kun`,
      date: new Date().toISOString(),
    });
    user.history = hist.slice(-100); // bot.py dagi HISTORY_LIMIT bilan bir xil
  } catch {
    /* tarix — qo'shimcha, xatoga olib kelmasligi kerak */
  }

  const orderId = 'nft_' + Math.random().toString(36).slice(2, 9);
  const who = `@${user.username || user.id}`;
  const newOrder = {
    id: orderId,
    user_id: user.id,
    kind: 'nft_rent',
    title: `${item.title}${item.number != null ? ` #${item.number}` : ''}`,
    nft_id: item.id,
    nft_link: item.link || '',
    nft_title: item.title,
    nft_number: item.number ?? null,
    days: q.days,
    per_day: q.per_day,
    rent: q.rent,
    network_fee: q.network_fee,
    price: q.total,
    price_uzs: q.total,
    amount: q.days,
    status: 'pending',
    source: 'webapp',
    // bot.py xabar matnida shularni ko'rsatadi
    customer_username: String(user.username || user.id),
    admin_username: adminHandle(),
    // Yuborilgan xabarlar — natijani ikkalasida ham yangilash uchun
    notices: [],
    // bot.py: menedjerga userbot orqali yuborildimi? (false = yuborilmagan)
    nft_notified: false,
    nft_notify_tries: 0,
    created_at: new Date().toISOString(),
  };
  store.orders.set(orderId, newOrder);

  // --- ADMINGA xabar (bot orqali, tugmalar bilan) ---
  //
  // 🔴 NIMA UCHUN FAQAT ADMIN?
  // Sizning talabingiz: "xabarni bitta menga emas @saidovManajer ga ham
  // USERBOT orqali ... barcha malumotlar bilan". Ya'ni menedjerga xabar
  // USERBOT akkauntidan chiqishi kerak (sizning nomingizdan).
  // Shuning uchun:
  //   • bu yerda — faqat ADMIN (bot orqali, tez va darhol)
  //   • menedjerga — `nft_notifications` navbati orqali `bot.py` yuboradi
  //     (`nft_notify_worker()`), chunki userbot faqat Python'da ishlaydi.
  // Ikkalasida ham bir xil tugmalar: nftok:<order_id>:done / :cancel
  //
  // `claim_nft_order()` (bot.py) lock + diskdan qayta o'qish bilan
  // bitta jarayonda BIRINCHI bosishni belgilaydi — ikkinchisi rad
  // qilinadi. Ya'ni hech qachon "ikkisi ham bajarildi" bo'lmaydi.
  const text =
    `🎁 <b>NFT ijaraga olish so'rovi</b>\n\n`
    + `🖼 <b>${item.title}</b>${item.number != null ? ` <code>#${item.number}</code>` : ''}\n`
    + (item.link
        ? `🔗 <a href="${item.link}">${item.link}</a>\n`
        : '🔗 Link: <i>yuborilmagan</i>\n')
    + `👤 Mijoz: <b>${who}</b> (ID: <code>${user.id}</code>)\n`
    + `👑 Meneger: <b>@${NFT_MANAGER}</b>\n`
    + `📅 Muddat: <b>${q.days} kun</b>\n\n`
    + `💰 Hisob:\n`
    + `├ 1 kunlik: ${q.per_day.toLocaleString()} UZS\n`
    + `├ Ijara (${q.days} kun): ${q.rent.toLocaleString()} UZS\n`
    + `├ Network fee: ${q.network_fee.toLocaleString()} UZS\n`
    + `└ <b>Jami: ${q.total.toLocaleString()} UZS</b>\n\n`
    + `🆔 <code>${orderId}</code>\n\n`
    + `⚡ <i>@${NFT_MANAGER} ga ham userbot orqali yuborildi. `
    + `Kim birinchi tugmani bossa — o'sha amal bajariladi.</i>`;

  // ✅ Bajarildi / ❌ Bekor qilish
  const kb = {
    inline_keyboard: [[
      { text: '✅ Bajarildi', callback_data: `nftok:${orderId}:done` },
      { text: '❌ Bekor qilish', callback_data: `nftok:${orderId}:cancel` },
    ]],
  };

  const token = (process.env.BOT_TOKEN || '').trim();
  const adminChat = Number(store.settings.admin_id || DEFAULT_USER_ID);
  if (token && adminChat) {
    try {
      const r = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          chat_id: adminChat,
          text,
          reply_markup: kb,
          parse_mode: 'HTML',
          disable_web_page_preview: true,
        }),
        signal: AbortSignal.timeout(15000),
      });
      const j: any = await r.json();
      if (j.ok) {
        // Xabar joyini saqlaymiz — natijada ikkala xabar ham yangilanadi
        newOrder.notices.push({
          via: 'bot',
          chat: Number(j.result?.chat?.id || adminChat),
          msg: Number(j.result?.message_id || 0),
        });
      } else {
        console.warn('[nft-rent] adminga xabar yuborilmadi:', j?.description);
      }
    } catch (e) {
      console.error('[nft-rent] adminga xabar yuborishda xato:', e);
    }
  }

  syncAndSaveDb();

  // 📨 Menedjerga USERBOT orqali yuborish uchun belgi.
  //
  // 🔴 NIMA UCHUN alohida "navbat" bo'limi emas?
  // `syncAndSaveDb()` faqat settings/users/orders/topups/nfts/contest
  // ni birlashtiradi — boshqa har qanday top-level kalit FAYLDAN
  // YO'QOLARDI. Shuning uchun navbatni ORDER'NING ICHIDA saqlaymiz:
  // bot.py dagi `nft_notify_worker()` `kind == "nft_rent"` va
  // `nft_notified` yo'q bo'lgan buyurtmalarni topadi va userbot
  // orqali yuboradi (xabar sizning akkauntingizdan chiqadi).

  res.json({
    ok: true,
    order: newOrder,
    balance: user.balance,
    message: `✅ NFT ijaraga olish so'rovi yuborildi!\n\n`
      + `🖼 ${item.title}\n`
      + `📅 ${q.days} kun · ${q.total.toLocaleString()} UZS\n\n`
      + `📞 Menejer siz bilan tez orada bog'lanadi.`,
  });
});

app.get('/api/rate', async (_req: Request, res: Response) => {
  try {
    const snapshot = await getUsdtUzsRate();
    const walletUsdt = Number(store.settings.wallet_usdt_balance || 0);
    const walletUzs = await usdtToUzs(walletUsdt);
    res.json({
      ok: true,
      usdt_uzs: snapshot.rate,
      source: snapshot.source,
      updated_at: snapshot.updatedAt,
      wallet_usdt: walletUsdt,
      wallet_uzs: walletUzs,
    });
  } catch (e) {
    res.status(500).json({ ok: false, error: (e as Error)?.message || 'Kursni olib bo‘lmadi' });
  }
});

// Dynamic Real Ranking from actual database users & completed orders
app.get('/api/ranking', (req: Request, res: Response) => {
  // 🔴 `getUser()` imzo yo'q bo'lganda `null` qaytaradi.
  // Reyting ommaviy ma'lumot, shuning uchun 401 emas — anonim
  // foydalanuvchi ham ko'ra oladi, faqat "o'zing" belgisi yo'q.
  const currentUser = getUser(req);
  const period = (req.query.period as string) || 'all';
  const now = Date.now();
  const cutoffMs =
    period === 'today' ? 86400000 :
    period === '3days' ? 3 * 86400000 :
    period === '7days' ? 7 * 86400000 : 0;

  const allUsers = Array.from(store.users.values());
  const allOrders = Array.from(store.orders.values()).filter((ord) => {
    if (!cutoffMs) return true;
    const t = ord.created_at ? new Date(ord.created_at).getTime() : 0;
    return now - t <= cutoffMs;
  });

  const userStats = new Map<number, { user: any; ordersCount: number; totalSpent: number }>();

  for (const u of allUsers) {
    userStats.set(u.id, {
      user: u,
      ordersCount: 0,
      totalSpent: cutoffMs ? 0 : (Number(u.total_spent) || 0),
    });
  }

  for (const ord of allOrders) {
    const allowedStatuses = ['completed', 'done', 'sent_unconfirmed', 'pending_admin'];
    if (allowedStatuses.includes(ord.status)) {
      const existing = userStats.get(ord.user_id);
      if (existing) {
        existing.ordersCount += 1;
        const ordPrice = orderPrice(ord);
        if (cutoffMs || !existing.totalSpent) {
          existing.totalSpent += ordPrice;
        }
      }
    }
  }

  // Filter only real users who have spent > 0 or placed >= 1 order
  const realBuyers = Array.from(userStats.values())
    .filter((s) => s.totalSpent > 0 || s.ordersCount > 0)
    .sort((a, b) => b.totalSpent - a.totalSpent);

  const leaders = realBuyers.map((item, index) => ({
    rank: index + 1,
    id: item.user.id,
    name: item.user.username ? `@${item.user.username}` : (item.user.first_name || `Mijoz #${item.user.id.toString().slice(-4)}`),
    username: item.user.username || '',
    photo_url: item.user.photo_url || '',
    orders: item.ordersCount || 1,
    amount: item.totalSpent,
    isMe: !!currentUser && item.user.id === currentUser.id,
  }));

  const myIndex = leaders.findIndex((l) => l.isMe);
  const allTimeSpent = Number(currentUser?.total_spent) || 0;
  const mySpent = cutoffMs
    ? allOrders
        .filter((o) => currentUser && o.user_id === currentUser.id)
        .reduce((sum, o) => sum + orderPrice(o), 0)
    : allTimeSpent;
  const myRank = myIndex !== -1 ? myIndex + 1 : (mySpent > 0 ? leaders.length + 1 : null);
  const myOrders = currentUser ? allOrders.filter((o) => o.user_id === currentUser.id).length : 0;

  res.json({
    ok: true,
    leaders,
    myRanking: {
      rank: myRank,
      orders: myOrders,
      amount: mySpent,
      inTop10: myRank !== null && myRank <= 10,
    },
  });
});

// Buyurtma narxini xavfsiz olish: price/price_uzs yo'q bo'lsa yoki
// noto'g'ri turdagi bo'lsa 0 qaytaradi. Aks holda `s + undefined` -> NaN ->
// JSON'da null -> frontend `null.toLocaleString()` bilan BUTUN EKRANNI
// oq qilib qoldiradi (Reyting bo'limi "Bugun/3 kunlik"da shunday bo'lardi).
function orderPrice(ord: any): number {
  const raw = Number(ord?.price ?? ord?.price_uzs ?? 0);
  return Number.isFinite(raw) && raw > 0 ? raw : 0;
}

// Resolve Telegram username into live display name and photo
app.get('/api/resolve-user', async (req: Request, res: Response) => {
  const rawUsername = (req.query.username as string || '').replace('@', '').trim();
  if (!rawUsername) {
    return res.status(400).json({ ok: false, error: "Username kiritilmadi" });
  }

  // 1. Check in local store.users
  const local = Array.from(store.users.values()).find(
    (u) => u.username && u.username.toLowerCase() === rawUsername.toLowerCase()
  );
  // DIQQAT: baza yozuvi bor, lekin profil rasmi yo'q bo'lsa darhol
  // qaytarib yubonmasak — foydalanuvchi bo'sh (sariq) doirani ko'radi.
  // Bunday holatda quyidagi t.me dan haqiqiy ism/rasm olinadi.
  if (local && local.photo_url) {
    return res.json({
      ok: true,
      user: {
        id: local.id,
        username: local.username,
        display_name: local.first_name || `@${local.username}`,
        first_name: local.first_name,
        photo_url: local.photo_url,
        from_bot: true,
      },
    });
  }

  // 2. Fetch public profile preview from https://t.me/{username}
  try {
    const resp = await fetch(`https://t.me/${rawUsername}`, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      },
      signal: AbortSignal.timeout(3000),
    });
    if (resp.ok) {
      const html = await resp.text();
      const ogTitleMatch = html.match(/<meta property="og:title" content="([^"]+)">/);
      const ogImageMatch = html.match(/<meta property="og:image" content="([^"]+)">/);
      const extraMatch = html.match(/<div class="tgme_page_extra">([^<]+)<\/div>/);

      const title = ogTitleMatch ? ogTitleMatch[1].replace('Telegram: Contact ', '').trim() : rawUsername;
      const photo = ogImageMatch && !ogImageMatch[1].includes('telegram-logo') ? ogImageMatch[1] : undefined;

      // Botda ro'yxatdan o'tmagan foydalanuvchi ham shu yerda
      // ism/rasm oladi — botga kirish shart emas.
      return res.json({
        ok: true,
        user: {
          id: local?.id,
          username: rawUsername,
          display_name: local?.first_name || title || `@${rawUsername}`,
          first_name: local?.first_name || title,
          // rasm topilmasa — Telegram'ning standart avatarini qo'yamiz
          // (bo'sh rasm emas, har doim ko'rinadigan doira)
          photo_url: photo || (local ? '' : ''),
          avatar_fallback: true,
          from_bot: Boolean(local),
          extra: extraMatch ? extraMatch[1].trim() : undefined,
        },
      });
    }
  } catch (e) {
    // Ignore fetch error
  }

  // Butunlay topilmasa — username'ni ko'rsatamiz, rasm o'rniga
  // initial harfli avatar (frontend chizadi). Bo'sh/buzilgan rasm YO'Q.
  return res.json({
    ok: true,
    user: {
      id: local?.id,
      username: rawUsername,
      display_name: local?.first_name || `@${rawUsername}`,
      first_name: local?.first_name,
      photo_url: '',
      avatar_fallback: true,
      from_bot: Boolean(local),
    },
  });
});

// Admin update wallet USDT balance
app.post('/api/admin/wallet-balance', (req: Request, res: Response) => {
  // 🔐 Unified `requireAdmin()` ga o'tkazildi. Avval `user.id !== admin_id`
  // deb qo'lda tekshirilardi — natija to'g'ri edi, lekin boshqa
  // endpoint'lardan farqli ko'rinishi keyinchalik auditda
  // "guard'siz" deb o'ngayotgan (va shunday).
  if (!requireAdmin(req)) return unauthorized(res, 'Faqat admin');

  const { balance, star_usdt_rate, wallet_address } = req.body;
  if (balance !== undefined && !isNaN(Number(balance))) {
    store.settings.wallet_usdt_balance = Number(balance);
  }
  if (star_usdt_rate !== undefined && !isNaN(Number(star_usdt_rate))) {
    store.settings.star_usdt_rate = Number(star_usdt_rate);
  }
  if (wallet_address !== undefined) {
    store.settings.wallet_address = wallet_address.trim();
  }
  syncAndSaveDb();

  res.json({
    ok: true,
    message: 'Hamyon sozlamalari yangilandi',
    settings: store.settings,
  });
});

// Bot holati tekshiruvi — Python bot o'lsa ham server ishlashda davom etadi,
// shuning uchun muammoni shu yerdan ko'rish mumkin.
app.get('/api/health', async (_req: Request, res: Response) => {
  const token = (process.env.BOT_TOKEN || '').trim();
  const out: Record<string, any> = {
    ok: true,
    server: 'running',
    bot_token_set: Boolean(token),
    bot_online: null,
    bot_username: null,
    bot_error: null,
    userbot_env: {
      api_id: Boolean(process.env.API_ID),
      api_hash: Boolean(process.env.API_HASH),
      session_string: Boolean(process.env.SESSION_STRING),
      // Sovg'a yuborish ham, bank xabarlarini tekshirish ham BITTA
      // userbot (SESSION_STRING) orqali amalga oshiriladi.
    },
    wallet_seed: Boolean(process.env.WALLET_SEED),
    fragment_cookies: Boolean(process.env.FRAGMENT_COOKIE_HEADER),
  };

  if (!token) {
    out.bot_error = 'BOT_TOKEN ENV da yo‘q — Railway sozlamasini tekshiring';
  } else {
    try {
      const r = await fetch(`https://api.telegram.org/bot${token}/getMe`, {
        signal: AbortSignal.timeout(15000),
      });
      const d: any = await r.json();
      if (d.ok) {
        out.bot_online = true;
        out.bot_username = d.result.username;

        // Webhook o'rnatilganmi? (bo'lsa polling umuman ishlamaydi!)
        try {
          const wr = await fetch(`https://api.telegram.org/bot${token}/getWebhookInfo`, {
            signal: AbortSignal.timeout(15000),
          });
          const wd: any = await wr.json();
          if (wd.ok) {
            out.webhook_url = wd.result.url || null;
            out.pending_updates = wd.result.pending_update_count;
            if (wd.result.url) {
              // O'zimiz to'g'ramiz — Python bot polling bilan ishlashi uchun
              await fetch(
                `https://api.telegram.org/bot${token}/deleteWebhook?drop_pending_updates=false`,
                { signal: AbortSignal.timeout(15000) }
              );
              out.webhook_auto_cleared = true;
            }
          }
        } catch (e) {
          /* webhook tekshiruvi ixtiyoriy */
        }
      } else {
        out.bot_online = false;
        out.bot_error = `Telegram: ${d.description || 'noma\'lum xato'}`;
      }
    } catch (e) {
      out.bot_online = false;
      out.bot_error = (e as Error)?.message || 'Telegram\'ga ulanib bo\'lmadi';
    }
  }

  // Python botning o'z holati (bazaga yozilgan)
  try {
    const fresh = loadDatabase();
    const rt = (fresh.settings as any)?.runtime;
    if (rt) out.python_bot = rt;
  } catch (e) {
    /* db o'qilmasa */
  }

  // Python jarayoni yashirmi? (bir xil konteynerda bo'lgani uchun ko'rish mumkin)
  try {
    const run = (cmd: string): string => execSync(cmd, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] });
    let ps = '';
    try {
      ps = run('ps -eo pid,etimes,args');
    } catch {
      try {
        ps = run('ps -eo pid,args');            // macOS da etimes yo'q
      } catch {
        ps = run('ps aux');                      // eng oxirgi zaxira
      }
    }
    const procs = ps
      .split('\n')
      // Faqat haqiqiy "python ... bot.py" jarayonlari (py_compile/grep kabi chalg'ituvchilar chiqarib tashlanadi)
      .filter((l) => {
        if (!/python/.test(l) || !/\bbot\.py\b/.test(l)) return false;
        if (/py_compile|grep|ps -eo|execSync/.test(l)) return false;
        return true;
      })
      .map((l) => {
        const parts = l.trim().split(/\s+/);
        if (parts.length < 3) return null;
        const pid = Number(parts[0]);
        if (!pid || isNaN(pid)) return null;
        return {
          pid,
          uptime_sec: /^\d+$/.test(parts[1]) ? Number(parts[1]) : null,
          cmd: parts.slice(2).join(' ').slice(0, 60),
        };
      })
      .filter(Boolean);
    out.python_process = procs;
    out.python_running = procs.length > 0;
  } catch (e) {
    out.python_process = null;
    out.python_running = null;
  }

  // Bo'ldimagi tekshiruvlar ro'yxati
  out.checks = [];
  if (!out.bot_token_set) out.checks.push('❌ BOT_TOKEN yo‘q');
  if (out.bot_online === false) out.checks.push(`❌ Bot online emas: ${out.bot_error}`);
  if (out.bot_online === true) out.checks.push('✅ Bot online');
  if (out.webhook_url) {
    out.checks.push(`❌ WEBHOOK o‘rnatilgan edi: ${out.webhook_url} — o‘chirildi (polling uchun zarur emas)`);
  } else if (out.webhook_auto_cleared) {
    out.checks.push('✅ Webhook avtomatik o‘chirildi');
  }
  if (process.env.AUTO_START_TG_BOT === 'true') {
    out.checks.push('❌ AUTO_START_TG_BOT=true — Node bot ham polling qilmoqda, '
      + 'Python bilan conflict bo‘ladi. Railway da false qiling.');
  } else {
    out.checks.push('✅ AUTO_START_TG_BOT sozlamasi to‘g‘ri');
  }
  if (!out.fragment_cookies) out.checks.push('❌ FRAGMENT_COOKIE_HEADER yo‘q — Stars xaridi ishlamaydi');
  else out.checks.push('✅ Fragment cookie‘lar bor');
  if (!out.wallet_seed) out.checks.push('❌ WALLET_SEED yo‘q — USDT yuborilmaydi');
  else out.checks.push('✅ WALLET_SEED bor');
  const ub = out.userbot_env;
  if (!ub.api_id || !ub.api_hash || !ub.session_string) {
    out.checks.push('⚠️ Userbot kalitlari to‘liq emas');
  } else {
    out.checks.push('✅ Userbot kalitlari bor');
  }
  if (out.python_running === true) {
    out.checks.push(`✅ Python bot jarayoni ishlayapti (PID ${out.python_process?.[0]?.pid})`);
  } else if (out.python_running === false) {
    out.checks.push('❌ Python bot jarayoni YO‘Q — Railway loglariga qarang');
  }
  const rt: any = out.python_bot;
  if (rt) {
    if (rt.userbot === 'connected') {
      out.checks.push(`✅ Userbot ulangan${rt.account ? ' (' + rt.account + ')' : ''}`);
    } else if (rt.userbot === 'missing_env') {
      out.checks.push('❌ Userbot kalitlari yetishmaydi: ' + [].concat(rt.missing || []).join(', '));
      out.checks.push('   → Avto to‘ldirish va gift yuborish ishlamaydi');
    } else if (rt.userbot === 'error') {
      out.checks.push('❌ Userbot ULANMADI: ' + String(rt.error || 'noma‘lum sabab').slice(0, 160));
      out.checks.push('   → /admin → 📱 Raqam bilan ulash orqali yangi SESSION_STRING oling');
    } else if (rt.userbot) {
      out.checks.push(`⚠️ Userbot: ${rt.userbot}${rt.error ? ' — ' + String(rt.error).slice(0, 80) : ''}`);
    } else {
      out.checks.push('⚠️ Userbot holati hali yozilmagan');
    }

    // Gift worker holati
    if (rt.gift_worker === 'blocked_userbot_offline') {
      out.checks.push(`❌ Gift worker to‘xtagan — userbot yo‘q (kutayotgan: ${rt.gift_pending ?? '?'})`);
    } else if (rt.gift_worker === 'running') {
      out.checks.push(`✅ Gift worker ishlayapti (yuborilgan: ${rt.gift_sent ?? 0}, kutilmoqda: ${rt.gift_pending ?? 0})`);
    }

    // Avto to'ldirish: qancha topup kutilmoqda
    try {
      const pend = Object.values(store.topups).filter(
        (t: any) => t && t.status === 'pending'
      ).length;
      out.pending_topups = pend;
      if (pend > 0) {
        out.checks.push(`⏳ Balans to‘ldirish kutilmoqda: ${pend} ta so‘rov`);
      }
    } catch { /* topups o'qilmasa */ }

    if (rt.bot === 'conflict') {
      out.checks.push('❌ CONFLICT: boshqa jarayon shu token bilan polling qilmoqda!');
      out.checks.push('   → AUTO_START_TG_BOT=false bo‘lishi kerak');
      out.checks.push('   → Boshqa joyda (kompyuter/Cloud Run) bot ishlamayotganini tekshiring');
    }
    if (typeof rt.updates === 'number') {
      out.checks.push(`📨 Polling olgan update'lar: ${rt.updates}`);
      if (rt.last_update_ago_sec !== null && rt.last_update_ago_sec !== undefined) {
        out.checks.push(`   oxirgisi: ${rt.last_update_ago_sec} soniya oldin`);
      }
      if (rt.updates === 0) {
        out.checks.push('   ⚠️ Hali birorta update kelmagan — polling ishlayaptimi?');
      }
    }
  }

  return res.json(out);
});

// Konkursni boshqarish (admin panel uchun)
app.get('/api/admin/contest', (req: Request, res: Response) => {
  // 🔐 AUTENTIFIKATSIYA — faqat ADMIN. (Guard avval `res.json` dan KEYIN
  // turgan edi — o'lik kod, hech qachon ishlamagan.)
  if (!requireAdmin(req)) return unauthorized(res, 'Faqat admin');
  res.json({ ok: true, contest: store.contest });
});

app.post('/api/admin/contest', (req: Request, res: Response) => {
  // 🔐 AUTENTIFIKATSIYA — bu endpoint faqat ADMINga ochiq.
  if (!requireAdmin(req)) return unauthorized(res, 'Faqat admin');
  getUser(req); // bazani diskdan yangilash
  const { text, prize_stars, winners, min, days, active } = req.body || {};

  const next = {
    ...store.contest,
    id: (active === false ? store.contest.id : 'c_' + Math.random().toString(36).slice(2, 9)),
    text: typeof text === 'string' && text.trim() ? text.trim() : store.contest.text,
    // DIQQAT: `Number(x) || eski` ishlatib bo'lmaydi — 0 falsy bo'lgani uchun
    // admin narxni/yutuvchilar sonini 0 ga tushira olmasdi.
    // Number.isFinite orqali "qiymat berilganmi?" aniq aniqlanadi.
    prize_stars: numOr(prize_stars, store.contest.prize_stars ?? 0),
    winners: numOr(winners, store.contest.winners ?? 1),
    min: numOr(min, store.contest.min ?? 0),
    ends_in: numOr(days, 0) ? numOr(days, 0) * 86400 : store.contest.ends_in,
    end_at: numOr(days, 0)
      ? new Date(Date.now() + numOr(days, 0) * 86400000).toISOString()
      : store.contest.end_at,
    active: active === false ? false : active === true ? true : store.contest.active,
  };
  // Yangi konkurs yaratilganda ishtirokchilar tozalanadi
  if (active === true || active === undefined) {
    next.participants = [];
  }
  if (!Array.isArray(next.participants)) next.participants = [];

  store.contest = next;
  syncAndSaveDb();
  res.json({ ok: true, contest: store.contest });
});

app.post('/api/contest/join', (req: Request, res: Response) => {
  const user = getUser(req);
  if (!user) return unauthorized(res);

  // Konkurs faol emas — hech kim qatnasha olmaydi
  const isActive = Boolean(store.contest.active) && (store.contest.prize_stars || 0) > 0;
  if (!isActive) {
    return res.status(400).json({ ok: false, error: 'Hozircha faol konkurs yo‘q.' });
  }
  if (!Array.isArray(store.contest.participants)) {
    store.contest.participants = [];
  }
  if (store.contest.participants.includes(user.id)) {
    return res.json({ ok: true, message: "Siz allaqachon konkursda qatnashyapsiz!", joined: true });
  }
  if (user.total_spent < store.contest.min) {
    return res.status(400).json({
      ok: false,
      error: `Konkursda qatnashish uchun kamida ${store.contest.min.toLocaleString()} so'mlik xarid qilishingiz kerak. Sizning xaridingiz: ${user.total_spent.toLocaleString()} so'm.`,
    });
  }
  store.contest.participants.push(user.id);
  syncAndSaveDb();
  res.json({
    ok: true,
    message: "🎉 Tabriklaymiz! Siz konkurs ishtirokchisiga aylandingiz.",
    joined: true,
    participants: store.contest.participants.length,
  });
});

app.post('/api/referral/withdraw', (req: Request, res: Response) => {
  const user = getUser(req);
  if (!user) return unauthorized(res);
  if (user.ref_stars < 50) {
    return res.status(400).json({
      ok: false,
      error: `Yechib olish uchun kamida 50 ⭐ Stars to'plashingiz kerak. Sizda: ${user.ref_stars} ⭐`,
    });
  }
  const starsToWithdraw = user.ref_stars;
  const uzsAmount = starsToWithdraw * store.settings.star_buy_price;
  user.ref_stars = 0;
  user.balance += uzsAmount;
  syncAndSaveDb();
  res.json({
    ok: true,
    message: `✅ ${starsToWithdraw} ⭐ Stars (${uzsAmount.toLocaleString()} UZS) asosiy balansingizga o'tkazildi!`,
    balance: user.balance,
    ref_stars: 0,
  });
});

// Admin endpoints
app.post('/api/admin/login', (req: Request, res: Response) => {
  const { password } = req.body;
  const adminPass = (process.env.ADMIN_PASSWORD || '').trim();

  // Xavfsizlik: avvalgi versiyalarda "neon2025" va "admin" kodlari kod ichida
  // yozilgan edi — endi FAQAT Railway Variables dagi ADMIN_PASSWORD ishlaydi.
  // ENV yo'q bo'lsa kirish umuman yopiladi (tuzatilmaydigan zaiflik emas).
  if (!adminPass) {
    console.error('ADMIN_PASSWORD o‘zgaruvchisi yo‘q — admin panel kirishi yopilgan');
    return res.status(503).json({
      ok: false,
      error: 'Admin paroli sozlanmagan. Railway Variables ga ADMIN_PASSWORD qo‘shing.',
    });
  }

  if (password === adminPass) {
    return res.json({ ok: true, token: 'neon_admin_token_' + Date.now() });
  }
  res.status(401).json({ ok: false, error: 'Noto‘g‘ri admin paroli.' });
});

app.get('/api/admin/data', (req: Request, res: Response) => {
  // 🔐 AUTENTIFIKATSIYA — bu endpoint faqat ADMINga ochiq.
  if (!requireAdmin(req)) return unauthorized(res, 'Faqat admin');
  const orders = Array.from(store.orders.values()).sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );
  const topups = Array.from(store.topups.values()).sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );
  const users = Array.from(store.users.values());

  res.json({
    ok: true,
    settings: store.settings,
    stats: {
      // DIQQAT: eski kod `users.length + settings.total_users` qilardi —
      // settings'dagi SOXTA qiymat ham qo'shilardi (va haqiqiy hisob
      // ikki marta hisoblanardi). Endi FAQAT haqiqiy ma'lumot.
      ...realStats(),
    },
    orders: orders.slice(0, 50),
    topups: topups.slice(0, 50),
    users,
  });
});

/**
 * HAQIQIY statistika — faqat haqiqiy ma'lumotlardan.
 *
 * AVVAL: "Jami aylanma" — `settings.total_volume_uzs` dan olinardi. Bu
 * bitta jamlangan akkumulator bo'lib, seed qiymati (485 000 000) bilan
 * boshlanardi va orderlarning haqiqiy holati bilan MOS KELMASDI.
 *
 * ENDI: har bir ko'rsatkich aniq HAQIQIY ro'yxatdan hisoblanadi.
 */
function realStats() {
  const users = [...store.users.values()];
  const orders = [...store.orders.values()];
  const topups = [...store.topups.values()];

  const orderPrice = (o: any): number => {
    const p = Number(o?.price_uzs ?? o?.price ?? 0);
    return Number.isFinite(p) && p > 0 ? p : 0;
  };
  const done = (o: any): boolean =>
    o?.status === 'completed' && !o?.gift_cancelled;
  const t0 = new Date();
  t0.setHours(0, 0, 0, 0);
  const todayMs = t0.getTime();

  const completed = orders.filter(done);
  const revenue = completed.reduce((s, o) => s + orderPrice(o), 0);
  const doneTopups = topups.filter((t: any) => t?.status === 'completed');
  const topupSum = doneTopups.reduce(
    (s: number, t: any) => s + (Number(t?.amount) || 0), 0
  );
  const todayOrders = completed.filter(
    (o: any) => Date.parse(o?.created_at || '') >= todayMs
  );

  return {
    totalUsers: users.length,
    activeUsers: users.filter((u: any) => Number(u?.total_spent) > 0).length,
    bannedUsers: users.filter((u: any) => u?.banned).length,
    newUsersToday: users.filter(
      (u: any) => Date.parse(u?.joined_at || '') >= todayMs
    ).length,

    totalOrders: orders.length,
    completedOrders: completed.length,
    pendingOrders: orders.filter(
      (o: any) => o?.status === 'processing' || o?.status === 'pending_admin'
    ).length,
    cancelledOrders: orders.filter(
      (o: any) => o?.status === 'cancelled' || o?.gift_cancelled
    ).length,
    todayOrders: todayOrders.length,

    totalTopups: topupSum,
    topupsCompleted: doneTopups.length,
    topupsPending: topups.filter((t: any) => t?.status === 'pending').length,

    totalRevenue: revenue,
    totalVolume: topupSum,
    todayVolume: doneTopups
      .filter((t: any) => Date.parse(t?.created_at || '') >= todayMs)
      .reduce((s: number, t: any) => s + (Number(t?.amount) || 0), 0),
    todayRevenue: todayOrders.reduce((s: number, o: any) => s + orderPrice(o), 0),

    userBalance: users.reduce(
      (s: number, u: any) => s + (Number(u?.balance) || 0), 0
    ),
    starsSold: completed
      .filter((o: any) => o?.kind === 'sell')
      .reduce((s: number, o: any) => s + (Number(o?.stars) || 0), 0),

    activeContests: contestIsActive(store.contest) ? 1 : 0,
  };
}

app.post('/api/admin/toggle-bot', (req: Request, res: Response) => {
  // 🔐 AUTENTIFIKATSIYA — bu endpoint faqat ADMINga ochiq.
  if (!requireAdmin(req)) return unauthorized(res, 'Faqat admin');
  getUser(req); // bazani diskdan yangilash
  store.settings.bot_active = !store.settings.bot_active;
  syncAndSaveDb();
  res.json({ ok: true, bot_active: store.settings.bot_active });
});

app.post('/api/admin/adjust-balance', (req: Request, res: Response) => {
  // 🔐 AUTENTIFIKATSIYA — bu endpoint faqat ADMINga ochiq.
  if (!requireAdmin(req)) return unauthorized(res, 'Faqat admin');
  getUser(req); // MUHIM: foydalanuvchini diskdan yangilaymiz, eskirgan ma'lumot bilan
  const { userId, amount } = req.body;
  const user = store.users.get(Number(userId));
  if (!user) {
    return res.status(404).json({ ok: false, error: 'Foydalanuvchi topilmadi.' });
  }
  user.balance = Math.max(0, user.balance + Number(amount));
  syncAndSaveDb();
  res.json({ ok: true, user });
});

// Interactive Telegram Bot chat simulator handler
app.post('/api/bot/chat', (req: Request, res: Response) => {
  // 🔐 AUTENTIFIKATSIYA — bu endpoint faqat ADMINga ochiq.
  if (!requireAdmin(req)) return unauthorized(res, 'Faqat admin');
  const { message, action } = req.body;
  const user = getUser(req);
  if (!user) return unauthorized(res);
  const text = (message || action || '').trim();

  let botReply = '';
  let inlineKeyboard: Array<Array<{ text: string; action: string; url?: string }>> = [];
  let replyKeyboard: Array<Array<string>> = [
    ['⭐ Stars sotib olish', '💎 Telegram Premium'],
    ['🎁 Telegram Gifts', '💳 Balans to\'ldirish'],
    ['👤 Profilim', '🏆 Konkurs & Bonus'],
    ['🌐 Web App', '🆘 Yordam'],
  ];

  if (text === '/start' || text === 'start') {
    botReply = `Assalomu alaykum, <b>@${user.username}</b>! 👋\n\n` +
      `<b>NEON STORE</b> — Telegram Stars, Premium va Gifts avtomatlashtirilgan do'koniga xush kelibsiz!\n\n` +
      `💳 Balansingiz: <b>${user.balance.toLocaleString()} UZS</b>\n` +
      `⭐ 1 Stars narxi: <b>${store.settings.star_buy_price} UZS</b>\n\n` +
      `Quyidagi bo'limlardan birini tanlang yoki Web App mini-ilovasini oching:`;
    inlineKeyboard = [
      [{ text: '🌐 Web App mini-ilovasi', action: 'open_webapp' }],
      [{ text: '⭐ Stars sotib olish', action: 'buy_stars' }, { text: '💎 Telegram Premium', action: 'buy_prem' }],
      [{ text: '💳 Balans to\'ldirish', action: 'topup' }, { text: '👥 Referal tizimi', action: 'referral' }],
    ];
  } else if (text === '⭐ Stars sotib olish' || text === 'buy_stars' || text === '/buy') {
    botReply = `⭐ <b>Telegram Stars sotib olish</b>\n\n` +
      `• Narx: 1 ⭐ = <b>${store.settings.star_buy_price} UZS</b>\n` +
      `• Minimal miqdor: <b>50 ⭐</b>\n` +
      `• Tez yetkazib berish: 1-2 daqiqa (Fragment + TON orqali)\n\n` +
      `Qancha Stars sotib olmoqchisiz?`;
    inlineKeyboard = [
      [{ text: '⭐ 50 Stars (10 000 UZS)', action: 'order_stars_50' }, { text: '⭐ 100 Stars (20 000 UZS)', action: 'order_stars_100' }],
      [{ text: '⭐ 250 Stars (50 000 UZS)', action: 'order_stars_250' }, { text: '⭐ 500 Stars (100 000 UZS)', action: 'order_stars_500' }],
      [{ text: '⭐ 1 000 Stars (200 000 UZS)', action: 'order_stars_1000' }],
      [{ text: '🌐 Web App orqali buyurtma berish', action: 'open_webapp' }],
    ];
  } else if (text.startsWith('order_stars_')) {
    const starCount = parseInt(text.replace('order_stars_', ''), 10) || 50;
    const cost = starCount * store.settings.star_buy_price;
    if (user.balance < cost) {
      botReply = `⚠️ <b>Balans yetarli emas!</b>\n\nKerakli summa: <b>${cost.toLocaleString()} UZS</b>\nBalansingiz: <b>${user.balance.toLocaleString()} UZS</b>\n\nIltimos, avval balansni to'ldiring:`;
      inlineKeyboard = [[{ text: '💳 Balans to\'ldirish', action: 'topup' }]];
    } else {
      user.balance -= cost;
      user.total_spent += cost;
      store.orders.set('ord_' + Math.random().toString(36).slice(2, 8), {
        id: 'ord_' + Math.random().toString(36).slice(2, 8),
        user_id: user.id,
        kind: 'stars',
        title: `⭐ ${starCount} Telegram Stars`,
        recipient: user.username,
        price: cost,
        status: 'completed',
        created_at: new Date().toISOString(),
      });
      botReply = `✅ <b>Buyurtma muvaffaqiyatli bajarildi!</b>\n\n` +
        `⭐ <b>${starCount} ta Stars</b> @${user.username} akkauntingizga yetkazildi!\n` +
        `Yechildi: <b>${cost.toLocaleString()} UZS</b>\n` +
        `Qolgan balans: <b>${user.balance.toLocaleString()} UZS</b>`;
      inlineKeyboard = [
        [{ text: '⭐ Yana sotib olish', action: 'buy_stars' }, { text: '💳 Balans', action: 'balance' }],
      ];
    }
  } else if (text === '💎 Telegram Premium' || text === 'buy_prem' || text === '/premium') {
    botReply = `💎 <b>Telegram Premium obunasi</b>\n\n` +
      `Telegram imkoniyatlarini maksimal darajaga ko'taring:\n` +
      `• Reklamalarsiz foydalanish\n` +
      `• 4 GB fayl yuklash\n` +
      `• Ovozli xabarlarni matnga aylantirish\n` +
      `• Eksklyuziv reaksiyalar va stikerlar\n\n` +
      `Kerakli muddatni tanlang:`;
    inlineKeyboard = [
      [{ text: '💎 3 oy (Sovg\'a) — 155 000 UZS', action: 'prem_3' }],
      [{ text: '💎 6 oy (Sovg\'a) — 205 000 UZS', action: 'prem_6' }],
      [{ text: '💎 12 oy (Sovg\'a) — 375 000 UZS', action: 'prem_12' }],
      [{ text: '🔑 1 oy (Kirib) — 40 000 UZS', action: 'prem_1_login' }],
    ];
  } else if (text === '🎁 Telegram Gifts' || text === 'gifts' || text === '/gifts') {
    botReply = `🎁 <b>Telegram Gifts do'koni</b>\n\n` +
      `Do'stlaringizga va yaqinlaringizga ajoyib Telegram sovg'alarini yuboring:\n\n` +
      `• 🧸 Ayiqcha — 3 000 UZS\n` +
      `• 💝 Yurakcha — 3 000 UZS\n` +
      `• 🎁 Sovg'a qutisi — 6 000 UZS\n` +
      `• 🎂 Tort — 10 000 UZS\n` +
      `• 🚀 Raketa — 10 000 UZS\n` +
      `• 🏆 Kubok — 20 000 UZS`;
    inlineKeyboard = [
      [{ text: '🧸 Ayiqcha (3 000 UZS)', action: 'buy_gift_bear' }, { text: '💝 Yurakcha (3 000 UZS)', action: 'buy_gift_heart' }],
      [{ text: '🎁 Sovg\'a qutisi (6 000 UZS)', action: 'buy_gift_box' }, { text: '🚀 Raketa (10 000 UZS)', action: 'buy_gift_rocket' }],
      [{ text: '🌐 Barcha sovg\'alar (Web App)', action: 'open_webapp' }],
    ];
  } else if (text === '💳 Balans to\'ldirish' || text === 'topup' || text === '/balance') {
    botReply = `💳 <b>Balans to'ldirish</b>\n\n` +
      `Hozirgi balansingiz: <b>${user.balance.toLocaleString()} UZS</b>\n\n` +
      `To'lov kartasi: <code>${store.settings.card_number}</code>\n` +
      `Karta egasi: <b>${store.settings.card_holder}</b>\n\n` +
      `Web App yoki quyidagi tezkor to'ldirish tugmasini bosing:`;
    inlineKeyboard = [
      [{ text: '➕ 25 000 UZS', action: 'quick_topup_25' }, { text: '➕ 50 000 UZS', action: 'quick_topup_50' }],
      [{ text: '➕ 100 000 UZS', action: 'quick_topup_100' }, { text: '➕ 250 000 UZS', action: 'quick_topup_250' }],
      [{ text: '🌐 Web App orqali to\'ldirish', action: 'open_webapp' }],
    ];
  } else if (text.startsWith('quick_topup_')) {
    const amt = parseInt(text.replace('quick_topup_', ''), 10) * 1000;
    user.balance += amt;
    botReply = `✅ <b>Balans muvaffaqiyatli to'ldirildi!</b>\n\n` +
      `Qo'shildi: <b>+${amt.toLocaleString()} UZS</b>\n` +
      `Yangi balans: <b>${user.balance.toLocaleString()} UZS</b>`;
    inlineKeyboard = [
      [{ text: '⭐ Stars sotib olish', action: 'buy_stars' }, { text: '💎 Premium', action: 'buy_prem' }],
    ];
  } else if (text === '👤 Profilim' || text === '/profile') {
    botReply = `👤 <b>Foydalanuvchi profili</b>\n\n` +
      `🆔 Telegram ID: <code>${user.id}</code>\n` +
      `👤 Username: @${user.username}\n` +
      `💳 Balans: <b>${user.balance.toLocaleString()} UZS</b>\n` +
      `🛍 Jami xaridlar: <b>${user.total_spent.toLocaleString()} UZS</b>\n` +
      `👥 Referallar: <b>${user.referrals_count} ta</b>\n` +
      `⭐ Referal Stars: <b>${user.ref_stars} ⭐</b>`;
    inlineKeyboard = [
      [{ text: '💳 Balans to\'ldirish', action: 'topup' }, { text: '👥 Referal havola', action: 'referral' }],
    ];
  } else if (text === '🏆 Konkurs & Bonus' || text === '/contest') {
    botReply = `🏆 <b>Faol Konkurs</b>\n\n` +
      `${store.contest.text}\n\n` +
      `👥 Ishtirokchilar: <b>${store.contest.participants.length} ta</b>\n` +
      `Sizning holatingiz: <b>${store.contest.participants.includes(user.id) ? '✅ Ishtirok etyapsiz' : '❌ Hali qo\'shilmagansiz'}</b>`;
    inlineKeyboard = [
      [{ text: '🎉 Konkursga qo\'shilish', action: 'join_contest' }],
    ];
  } else if (text === 'join_contest') {
    if (store.contest.participants.includes(user.id)) {
      botReply = `Siz allaqachon konkurs ishtirokchisisiz! G'oliblar tasodifiy tanlanadi.`;
    } else {
      store.contest.participants.push(user.id);
      botReply = `🎉 Tabriklaymiz! Siz konkursga muvaffaqiyatli qo'shildingiz!`;
    }
  } else if (text === '👥 Referal tizimi' || text === 'referral') {
    botReply = `👥 <b>Referal dasturi</b>\n\n` +
      `Do'stlaringizni taklif qiling va har bir do'stingiz uchun <b>1 ⭐ Stars</b> oling!\n\n` +
      `Sizning referal havolangiz:\n` +
      `<code>https://t.me/shop_neonbot?start=ref_${user.id}</code>\n\n` +
      `Taklif qilingan do'stlar: <b>${user.referrals_count}</b>\n` +
      `To'plangan Stars: <b>${user.ref_stars} ⭐</b>`;
    inlineKeyboard = [
      [{ text: '⭐ Balansga yechish (min 50 ⭐)', action: 'withdraw_ref' }],
    ];
  } else if (text === 'admin' || text === '/admin') {
    botReply = `🔐 <b>Admin paneliga xush kelibsiz!</b>\n\n` +
      `Bot holati: <b>${store.settings.bot_active ? '🟢 Faol' : '🔴 To\'xtatilgan'}</b>\n` +
      `Jami foydalanuvchilar: <b>${store.users.size.toLocaleString()}</b>\n` +
      `Jami buyurtmalar: <b>${store.orders.size.toLocaleString()}</b>\n` +
      `Jami aylanma: <b>${realStats().totalVolume.toLocaleString()} UZS</b>\n\n` +
      `Admin buyruqlari quyida:`;
    inlineKeyboard = [
      [{ text: store.settings.bot_active ? '⏸ Botni to\'xtatish' : '▶️ Botni yoqish', action: 'admin_toggle_bot' }],
      [{ text: '📊 Batafsil statistika', action: 'admin_stats' }, { text: '🌐 Admin boshqaruv paneli', action: 'open_admin' }],
    ];
  } else if (text === 'admin_toggle_bot') {
    store.settings.bot_active = !store.settings.bot_active;
    botReply = `Bot holati o'zgartirildi: <b>${store.settings.bot_active ? '🟢 Faol' : '🔴 To\'xtatilgan'}</b>`;
    inlineKeyboard = [[{ text: '◀️ Admin menyusi', action: 'admin' }]];
  } else {
    botReply = `Tushundim. Marhamat, quyidagi amallardan birini tanlang:`;
    inlineKeyboard = [
      [{ text: '⭐ Stars sotib olish', action: 'buy_stars' }, { text: '💎 Telegram Premium', action: 'buy_prem' }],
      [{ text: '🌐 Web App ochish', action: 'open_webapp' }],
    ];
  }

  res.json({
    ok: true,
    message: {
      id: 'msg_' + Date.now(),
      sender: 'bot',
      text: botReply,
      time: new Date().toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' }),
      inlineKeyboard,
      replyKeyboard,
    },
    user: {
      balance: user.balance,
      total_spent: user.total_spent,
    },
  });
});

// Live Telegram Bot Connection Endpoints
app.get('/api/bot/status', (req: Request, res: Response) => {
  // 🔐 AUTENTIFIKATSIYA — bu endpoint faqat ADMINga ochiq.
  if (!requireAdmin(req)) return unauthorized(res, 'Faqat admin');
  res.json({ ok: true, ...getBotStatus() });
});

app.post('/api/bot/start', async (req: Request, res: Response) => {
  // 🔐 AUTENTIFIKATSIYA — bu endpoint faqat ADMINga ochiq.
  if (!requireAdmin(req)) return unauthorized(res, 'Faqat admin');
  const { token, webappUrl } = req.body;
  const result = await startTelegramBot(token, webappUrl);
  res.json(result);
});

app.post('/api/bot/stop', async (req: Request, res: Response) => {
  // 🔐 AUTENTIFIKATSIYA — bu endpoint faqat ADMINga ochiq.
  if (!requireAdmin(req)) return unauthorized(res, 'Faqat admin');
  await stopTelegramBot();
  res.json({ ok: true, message: "Telegram bot to'xtatildi" });
});

// Vite Dev Server middleware or Static Build Serving
async function startServer() {
  const isProd = process.env.NODE_ENV === 'production';
  const distDir = path.resolve(__dirname, 'dist');

  if (isProd && fs.existsSync(distDir)) {
    app.use(express.static(distDir));
    app.get('*', (req: Request, res: Response) => {
      res.sendFile(path.resolve(distDir, 'index.html'));
    });
  } else {
    const { createServer: createViteServer } = await import('vite');
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);

    // Guaranteed SPA fallback for any route
    app.use('*', async (req: Request, res: Response, next) => {
      if (req.originalUrl.startsWith('/api')) {
        return next();
      }
      try {
        const url = req.originalUrl;
        const indexPath = path.resolve(__dirname, 'index.html');
        if (fs.existsSync(indexPath)) {
          let template = fs.readFileSync(indexPath, 'utf-8');
          template = await vite.transformIndexHtml(url, template);
          res.status(200).set({ 'Content-Type': 'text/html' }).end(template);
        } else {
          next();
        }
      } catch (e: any) {
        next(e);
      }
    });
  }

  // Auto-start Telegram Bot faqat AUTO_START_TG_BOT=true bo'lganda
  // (aks holda Python bot.py bilan token ziddiyeti/conflict bo'ladi)
  if (process.env.BOT_TOKEN && process.env.AUTO_START_TG_BOT === 'true') {
    const webapp =
      process.env.WEBAPP_URL ||
      (process.env.RAILWAY_PUBLIC_DOMAIN ? `https://${process.env.RAILWAY_PUBLIC_DOMAIN}` : '');
    startTelegramBot(process.env.BOT_TOKEN, webapp).then((res) => {
      if (res.ok) {
        console.log('🤖 Real Telegram bot started automatically from BOT_TOKEN env var');
      } else {
        console.log('⚠️ Telegram bot auto-start failed:', res.error);
      }
    });
  }

  app.listen(PORT, '0.0.0.0', () => {
    console.log(`🚀 NEON STORE Server running at http://0.0.0.0:${PORT}`);
  });
}

startServer().catch((err) => {
  console.error('Server failed to start:', err);
});
