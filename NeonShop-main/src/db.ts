import fs from 'fs';
import path from 'path';

export interface UserRecord {
  id: number;
  username: string;
  first_name?: string;
  balance: number;
  total_spent: number;
  referrals_count: number;
  ref_stars: number;
  banned: boolean;
  referred_by?: number;
  created_at: string;
}

export interface OrderRecord {
  id: string;
  user_id: number;
  kind: 'stars' | 'premium' | 'gift';
  title: string;
  recipient: string;
  price: number;
  amount: number;
  status: 'completed' | 'pending' | 'pending_admin' | 'failed';
  payment_method?: 'usdt' | 'balance';
  failure_reason?: string;
  created_at: string;
}

export interface TopupRecord {
  id: string;
  user_id: number;
  amount: number;
  status: 'pending' | 'completed' | 'cancelled';
  card: string;
  holder: string;
  expires_at: number;
  created_at: string;
}

export interface DatabaseSchema {
  settings: {
    bot_active: boolean;
    card_number: string;
    card_holder: string;
    star_buy_price: number;
    star_sell_price: number;
    support_username: string;
    admin_id: number;
    total_users: number;
    total_orders: number;
    total_volume_uzs: number;
    wallet_usdt_balance: number;
    wallet_address?: string;
    star_usdt_rate?: number;
  };
  users: Record<string, UserRecord>;
  orders: Record<string, OrderRecord>;
  topups: Record<string, TopupRecord>;
  contest: {
    id: string;
    text: string;
    color: string;
    winners: number;
    prize_stars: number;
    ends_in: number;
    end_at: string;
    participants: number[];
    min: number;
  };
}

// Check where we can store the database:
// 1) Environment DB_PATH (e.g. /data/users_db.json)
// 2) /data/users_db.json if writable
// 3) Local ./data/users_db.json
function resolveDbPath(): string {
  if (process.env.DB_PATH) {
    return process.env.DB_PATH;
  }
  try {
    if (!fs.existsSync('/data')) {
      fs.mkdirSync('/data', { recursive: true });
    }
    fs.accessSync('/data', fs.constants.W_OK);
    return '/data/users_db.json';
  } catch (e) {
    const localDir = path.resolve(process.cwd(), 'data');
    if (!fs.existsSync(localDir)) {
      fs.mkdirSync(localDir, { recursive: true });
    }
    return path.join(localDir, 'users_db.json');
  }
}

export const DB_FILE = resolveDbPath();

console.log(`💾 Persistent database file resolved at: ${DB_FILE}`);

const defaultData: DatabaseSchema = {
  settings: {
    bot_active: true,
    card_number: '9860 1701 1569 3682',
    card_holder: 'O. N (HUMO)',
    star_buy_price: 200,
    star_sell_price: 125,
    support_username: 'normuzb',
    admin_id: 8307046273,
    total_users: 14280,
    total_orders: 8740,
    total_volume_uzs: 485000000,
    wallet_usdt_balance: 50.0,
    star_usdt_rate: 0.015,
    wallet_address: 'UQCFJEP4WZ_mpdo0_kMEmsTgvrMHG7K_tWY16pQhKHwoOtFz',
  },
  users: {
    '8307046273': {
      id: 8307046273,
      username: 'normuzb',
      first_name: 'Odilbek',
      balance: 357813,
      total_spent: 850000,
      referrals_count: 14,
      ref_stars: 48,
      banned: false,
      created_at: new Date(Date.now() - 30 * 86400000).toISOString(),
    },
  },
  orders: {
    ord_demo1: {
      id: 'ord_demo1',
      user_id: 8307046273,
      kind: 'stars',
      title: '⭐ 100 Telegram Stars',
      recipient: 'normuzb',
      price: 20000,
      amount: 100,
      status: 'completed',
      payment_method: 'usdt',
      created_at: new Date(Date.now() - 3600000 * 2).toISOString(),
    },
    ord_demo2: {
      id: 'ord_demo2',
      user_id: 8307046273,
      kind: 'premium',
      title: "💎 Telegram Premium (3 oy - Sovg'a)",
      recipient: 'normuzb',
      price: 155000,
      amount: 3,
      status: 'completed',
      created_at: new Date(Date.now() - 3600000 * 24).toISOString(),
    },
    ord_demo3: {
      id: 'ord_demo3',
      user_id: 8307046273,
      kind: 'gift',
      title: '🚀 Raketa (Gifts)',
      recipient: 'durov',
      price: 10000,
      amount: 50,
      status: 'completed',
      created_at: new Date(Date.now() - 3600000 * 48).toISOString(),
    },
  },
  topups: {},
  contest: {
    id: 'contest_march',
    text: "🎉 <b>NEON STORE Bahorgi Katta Konkursi!</b>\n\nSovrin jamg'armasi: <b>1 000 ⭐ Stars</b>\n5 nafar g'olib random orqali aniqlanadi.\nQatnashish uchun minimal xarid: 20 000 so'm.",
    color: 'purple',
    winners: 5,
    prize_stars: 1000,
    ends_in: 86400 * 3,
    end_at: new Date(Date.now() + 86400000 * 3).toISOString(),
    participants: [8307046273, 541098231, 672901239, 908123491],
    min: 20000,
  },
};

export function loadDatabase(): DatabaseSchema {
  try {
    if (fs.existsSync(DB_FILE)) {
      const content = fs.readFileSync(DB_FILE, 'utf-8');
      // Eski bazalarda BOM (utf-8-sig) bo'lishi mumkin — olib tashlaymiz
      const parsed = JSON.parse(content.replace(/^﻿/, '').trim());
      console.log(`✅ Baza yuklandi: ${DB_FILE} (users: ${Object.keys(parsed.users || {}).length})`);
      // Merge with defaults to ensure all keys exist
      return {
        settings: { ...defaultData.settings, ...(parsed.settings || {}) },
        users: { ...(parsed.users || {}) },
        orders: { ...(parsed.orders || {}), ...(parsed.sales || {}) },
        topups: { ...(parsed.topups || {}) },
        contest: { ...defaultData.contest, ...(parsed.contest || {}) },
      };
    }
  } catch (err) {
    console.error(`⚠️ Error reading ${DB_FILE}:`, err);
    // Zaxiradan tiklashga urinish
    try {
      const bak = `${DB_FILE}.bak`;
      if (fs.existsSync(bak)) {
        const parsed = JSON.parse(fs.readFileSync(bak, 'utf-8').replace(/^﻿/, '').trim());
        console.log(`♻️ Zaxiradan tiklandi: ${bak}`);
        return {
          settings: { ...defaultData.settings, ...(parsed.settings || {}) },
          users: { ...(parsed.users || {}) },
          orders: { ...(parsed.orders || {}) },
          topups: { ...(parsed.topups || {}) },
          contest: { ...defaultData.contest, ...(parsed.contest || {}) },
        };
      }
    } catch (e2) {
      console.error(`⚠️ Zaxira ham o'qilmadi:`, e2);
    }
    // Muhim: haqiqiy faylni ustiga default yozib yubormaymiz
    console.error(`🛑 Asosiy baza o'qilmadi. Fayl saqlab qolindi, default qaytarildi.`);
    return structuredClone(defaultData);
  }

  // If file doesn't exist, write defaults atomically
  saveDatabase(defaultData);
  return defaultData;
}

export function saveDatabase(data: DatabaseSchema): void {
  try {
    const dir = path.dirname(DB_FILE);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }

    const tmpFile = `${DB_FILE}.tmp`;
    const bakFile = `${DB_FILE}.bak`;
    const jsonStr = JSON.stringify(data, null, 2);

    fs.writeFileSync(tmpFile, jsonStr, 'utf-8');
    if (fs.existsSync(DB_FILE)) {
      fs.copyFileSync(DB_FILE, bakFile);
    }
    fs.renameSync(tmpFile, DB_FILE);
  } catch (err) {
    console.error(`❌ Failed to save database to ${DB_FILE}:`, err);
  }
}
