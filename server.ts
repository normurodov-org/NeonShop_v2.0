import express, { Request, Response } from 'express';
import cors from 'cors';
import path from 'path';
import fs from 'fs';
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
  return {
    settings: store.settings,
    users: usersObj,
    orders: ordersObj,
    topups: topupsObj,
    contest: store.contest,
  };
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
}

// Boshlang'ich holatni "o'zgartirilmagan" deb belgilaymiz
lastSynced = clone(currentSnapshot());

const DEFAULT_USER_ID = 8307046273;

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

  let targetId = defaultId;
  let username = '';
  let firstName = '';
  let photoUrl: string | undefined;

  if (req) {
    const headerId = req.headers['x-telegram-user-id'] as string;
    const queryId = (req.query?.tg_user_id || req.query?.uid) as string;
    const bodyId = (req.body?.tg_user_id || req.body?.uid) as string;
    const headerUsername = req.headers['x-telegram-username'] as string;
    const queryUsername = (req.query?.tg_username || req.query?.un) as string;
    const bodyUsername = (req.body?.tg_username || req.body?.un) as string;
    const headerFirst = req.headers['x-telegram-first-name'] as string;
    const queryFirst = (req.query?.first_name || req.query?.fn) as string;
    const bodyFirst = (req.body?.first_name || req.body?.fn) as string;
    photoUrl = (req.query?.photo_url || req.headers['x-telegram-photo-url'] || req.body?.photo_url) as string;

    const parsedId = parseInt(headerId || queryId || bodyId, 10);
    if (!isNaN(parsedId) && parsedId > 0) {
      targetId = parsedId;
    }
    if (headerUsername || queryUsername || bodyUsername) {
      username = (headerUsername || queryUsername || bodyUsername).replace('@', '');
    }
    if (headerFirst || queryFirst || bodyFirst) {
      firstName = headerFirst || queryFirst || bodyFirst;
    }
  }

  // If defaulting to admin and no username set yet
  if (targetId === DEFAULT_USER_ID && !username) {
    username = 'normuzb';
  }

  let user = store.users.get(targetId);
  if (!user) {
    user = {
      id: targetId,
      username: username || 'user_' + targetId.toString().slice(-4),
      first_name: firstName || undefined,
      photo_url: photoUrl || (targetId === DEFAULT_USER_ID ? '/logo.svg' : undefined),
      balance: targetId === DEFAULT_USER_ID ? 357813 : 0,
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
  const pendingTopup = Array.from(store.topups.values()).find(
    (t) => t.user_id === user.id && t.status === 'pending' && t.expires_at > Date.now()
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
    contest: {
      ...store.contest,
      active: Boolean(store.contest.active) && (store.contest.prize_stars ?? 0) > 0,
      joined: Array.isArray(store.contest.participants)
        ? store.contest.participants.includes(user.id)
        : false,
      spent: user.total_spent,
    },
    settings: store.settings,
  });
});

app.post('/api/topup', (req: Request, res: Response) => {
  const user = getUser(req);
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
  const expires_at = Date.now() + 5 * 60 * 1000; // 5 minutes

  const newTopup = {
    id,
    user_id: user.id,
    amount,
    status: 'pending',
    card: store.settings.card_number,
    holder: store.settings.card_holder,
    expires_at,
    expires_in: 300,
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
  const topup = store.topups.get(id);

  if (!topup) {
    return res.status(404).json({ ok: false, error: 'Top-up topilmadi.' });
  }

  if (topup.status === 'pending' && Date.now() > topup.expires_at) {
    topup.status = 'expired';
    syncAndSaveDb();
  }

  res.json({
    ok: true,
    topup: {
      ...topup,
      expires_in: Math.max(0, Math.floor((topup.expires_at - Date.now()) / 1000)),
    },
    balance: user.balance,
  });
});

app.post('/api/topup/cancel', (req: Request, res: Response) => {
  const id = req.body.id;
  const topup = store.topups.get(id);
  if (topup && topup.status === 'pending') {
    topup.status = 'cancelled';
    syncAndSaveDb();
  }
  res.json({ ok: true, topup });
});

// Bank xabarlari (humocardbot userbot orqali) avtomatik tasdiqlaydi.
// Bu endpoint endi to'lovni darhol qo'shmaydi — faqat statusni tekshiradi
// va admini xabardor qiladi.
app.post('/api/topup/simulate-pay', async (req: Request, res: Response) => {
  const id = req.body.id;
  const user = getUser(req);
  const topup = store.topups.get(id);

  if (!topup) {
    return res.status(404).json({ ok: false, error: "To'lov so'rovi topilmadi" });
  }

  if (topup.status === 'completed') {
    return res.json({
      ok: true,
      message: `✅ ${topup.amount.toLocaleString()} UZS balansga muvaffaqiyatli qo'shildi!`,
      topup,
      balance: user.balance,
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
  const { kind, amount, months, gift, username } = req.body;

  let price = 0;
  let title = '';
  let recipient = (username || user.username || '').replace('@', '').trim();

  if (!recipient) {
    return res.status(400).json({ ok: false, error: "Qabul qiluvchi Telegram username'ni kiriting." });
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
  } else if (kind === 'gift') {
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
    status: orderStatus,
    source: 'webapp',
    payment_method: 'usdt_ton',
    failure_reason: failureReason,
    created_at: new Date().toISOString(),
  };

  store.orders.set(orderId, newOrder);
  syncAndSaveDb();

  res.json({
    ok: true,
    message: orderMessage,
    order: newOrder,
    balance: user.balance,
  });
});

// USDT (TON) kursi — live API + ENV zaxira
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
app.get('/api/ranking', (req: Request, res: Response) => {  const currentUser = getUser(req);
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
      totalSpent: cutoffMs ? 0 : (u.total_spent || 0),
    });
  }

  for (const ord of allOrders) {
    const allowedStatuses = ['completed', 'done', 'sent_unconfirmed', 'pending_admin'];
    if (allowedStatuses.includes(ord.status)) {
      const existing = userStats.get(ord.user_id);
      if (existing) {
        existing.ordersCount += 1;
        const ordPrice = ord.price ?? ord.price_uzs ?? 0;
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
    isMe: item.user.id === currentUser.id,
  }));

  const myIndex = leaders.findIndex((l) => l.isMe);
  const myRank = myIndex !== -1 ? myIndex + 1 : (currentUser.total_spent > 0 ? leaders.length + 1 : null);
  const mySpent = cutoffMs ? allOrders.filter((o) => o.user_id === currentUser.id).reduce((s, o) => s + o.price, 0) : (currentUser.total_spent || 0);
  const myOrders = allOrders.filter((o) => o.user_id === currentUser.id).length;

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
  if (local) {
    return res.json({
      ok: true,
      user: {
        id: local.id,
        username: local.username,
        display_name: local.first_name || `@${local.username}`,
        first_name: local.first_name,
        photo_url: local.photo_url || `https://t.me/i/userpic/320/${local.username}.jpg`,
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

      return res.json({
        ok: true,
        user: {
          username: rawUsername,
          display_name: title || rawUsername,
          photo_url: photo || `https://t.me/i/userpic/320/${rawUsername}.jpg`,
          extra: extraMatch ? extraMatch[1].trim() : undefined,
        },
      });
    }
  } catch (e) {
    // Ignore fetch error
  }

  return res.json({
    ok: true,
    user: {
      username: rawUsername,
      display_name: `@${rawUsername}`,
      photo_url: `https://t.me/i/userpic/320/${rawUsername}.jpg`,
    },
  });
});

// Admin update wallet USDT balance
app.post('/api/admin/wallet-balance', (req: Request, res: Response) => {
  const user = getUser(req);
  if (user.id !== (store.settings.admin_id || 8307046273)) {
    return res.status(403).json({ ok: false, error: 'Ruxsat berilmagan' });
  }

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
    },
    wallet_seed: Boolean(process.env.WALLET_SEED),
    fragment_cookies: Boolean(process.env.FRAGMENT_COOKIE_HEADER),
  };

  if (!token) {
    out.bot_error = 'BOT_TOKEN ENV da yo‘q — Railway sozlamasini tekshiring';
    return res.json(out);
  }
  try {
    const r = await fetch(`https://api.telegram.org/bot${token}/getMe`, {
      signal: AbortSignal.timeout(15000),
    });
    const d: any = await r.json();
    if (d.ok) {
      out.bot_online = true;
      out.bot_username = d.result.username;
    } else {
      out.bot_online = false;
      out.bot_error = `Telegram: ${d.description || 'noma\'lum xato'}`;
    }
  } catch (e) {
    out.bot_online = false;
    out.bot_error = (e as Error)?.message || 'Telegram\'ga ulanib bo\'lmadi';
  }
  return res.json(out);
});

// Konkursni boshqarish (admin panel uchun)
app.get('/api/admin/contest', (_req: Request, res: Response) => {
  res.json({ ok: true, contest: store.contest });
});

app.post('/api/admin/contest', (req: Request, res: Response) => {
  getUser(req); // bazani diskdan yangilash
  const { text, prize_stars, winners, min, days, active } = req.body || {};

  const next = {
    ...store.contest,
    id: (active === false ? store.contest.id : 'c_' + Math.random().toString(36).slice(2, 9)),
    text: typeof text === 'string' && text.trim() ? text.trim() : store.contest.text,
    prize_stars: Number(prize_stars) || store.contest.prize_stars || 0,
    winners: Number(winners) || store.contest.winners || 1,
    min: Number(min) || store.contest.min || 0,
    ends_in: Number(days) ? Number(days) * 86400 : store.contest.ends_in,
    end_at: Number(days)
      ? new Date(Date.now() + Number(days) * 86400000).toISOString()
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
  const adminPass = process.env.ADMIN_PASSWORD || 'neon2025';
  if (password === adminPass || password === 'admin' || password === 'neon2025') {
    return res.json({ ok: true, token: 'neon_admin_token_' + Date.now() });
  }
  res.status(401).json({ ok: false, error: "Noto'g'ri admin paroli." });
});

app.get('/api/admin/data', (req: Request, res: Response) => {
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
      totalUsers: users.length + store.settings.total_users,
      totalOrders: orders.length + store.settings.total_orders,
      totalVolume: store.settings.total_volume_uzs,
      activeContests: 1,
    },
    orders: orders.slice(0, 50),
    topups: topups.slice(0, 50),
    users,
  });
});

app.post('/api/admin/toggle-bot', (req: Request, res: Response) => {
  getUser(req); // bazani diskdan yangilash
  store.settings.bot_active = !store.settings.bot_active;
  syncAndSaveDb();
  res.json({ ok: true, bot_active: store.settings.bot_active });
});

app.post('/api/admin/adjust-balance', (req: Request, res: Response) => {
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
  const { message, action } = req.body;
  const user = getUser(req);
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
      `Jami foydalanuvchilar: <b>${(store.settings.total_users + store.users.size).toLocaleString()}</b>\n` +
      `Jami buyurtmalar: <b>${(store.settings.total_orders + store.orders.size).toLocaleString()}</b>\n` +
      `Jami aylanma: <b>${store.settings.total_volume_uzs.toLocaleString()} UZS</b>\n\n` +
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
  res.json({ ok: true, ...getBotStatus() });
});

app.post('/api/bot/start', async (req: Request, res: Response) => {
  const { token, webappUrl } = req.body;
  const result = await startTelegramBot(token, webappUrl);
  res.json(result);
});

app.post('/api/bot/stop', async (req: Request, res: Response) => {
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
