export interface User {
  id: number;
  username: string;
  first_name?: string;
  photo_url?: string;
  balance: number;
  total_spent: number;
  referrals_count: number;
  ref_stars: number;
  banned: boolean;
  created_at: string;
}

export interface Topup {
  id: string;
  user_id: number;
  amount: number;
  status: 'pending' | 'completed' | 'cancelled' | 'expired';
  card: string;
  holder: string;
  expires_in: number;
  created_at: string;
}

export interface Order {
  id: string;
  user_id: number;
  kind: 'stars' | 'premium' | 'gift';
  title: string;
  recipient: string;
  price: number;
  price_uzs?: number;
  stars?: number;
  amount?: number;
  status:
    | 'completed'
    | 'processing'
    | 'queued'
    | 'pending'
    | 'manual'
    | 'failed'
    | 'done'
    | 'sent_unconfirmed'
    | 'manual_pending'
    | 'unknown';
  source?: 'webapp' | 'grammy' | 'bot';
  payment_method?: 'usdt' | 'usdt_ton' | 'balance' | 'humocard';
  usdt_spent?: number | null;
  created_at: string;
}

export interface UsdtRate {
  usdt_uzs: number;
  source: 'live' | 'env';
  updated_at: number;
  wallet_usdt: number;
  wallet_uzs: number;
}

export interface Contest {
  id: string;
  text: string;
  color?: string;
  winners: number;
  ends_in: number;
  end_at: string;
  participants: number[] | number;
  joined?: boolean;
  spent?: number;
  min: number;
  prize_stars: number;
  /** Faol konkurs bormi (admin panel orqali yaratiladi) */
  active?: boolean;
}

export interface GiftItem {
  key: string;
  name: string;
  stars: number;
  priceUzs: number;
  emoji: string;
  tag?: string;
}

export interface PremiumPlan {
  months: number;
  priceUzs: number;
  mode: 'nologin' | 'login';
  popular?: boolean;
  savings?: string;
}

export interface StoreSettings {
  admin_id?: number;
  bot_active: boolean;
  card_number: string;
  card_holder: string;
  star_buy_price: number;
  star_sell_price: number;
  star_usdt_rate?: number;
  support_username: string;
  total_users: number;
  total_orders: number;
  total_volume_uzs: number;
  wallet_usdt_balance?: number;
  wallet_address?: string;
  /** USDT alohida jetton manzilida saqlanadi (TON hamyondan boshqa) */
  wallet_usdt_address?: string;
  wallet_ton_balance?: number;
  wallet_usdt_updated_at?: string;
  usdt_rate_uzs?: number;
  usdt_rate_updated_at?: string;
}

export interface BotChatMessage {
  id: string;
  sender: 'user' | 'bot';
  text: string;
  time: string;
  photoUrl?: string;
  inlineKeyboard?: Array<Array<{ text: string; action: string; url?: string }>>;
  replyKeyboard?: Array<Array<string>>;
}
