import React, { useState, useEffect } from 'react';
import { StoreSettings, Contest } from '../types';
import { Shield, Lock, Power, Users, ShoppingBag, DollarSign, CheckCircle2, AlertCircle, ArrowRight, RefreshCw, Trophy, TrendingUp, Wallet, Clock, Ban, ChevronUp, ChevronDown } from 'lucide-react';
import type { AdminSub } from '../lib/routes';

interface AdminPanelProps {
  onSettingsUpdated: (newSettings: StoreSettings) => void;
  /**
   * 🔴 `isDark` MAJBURIY.
   *
   * Sabab: panel kirish maydonlarini `text-white` bilan yozgan edi, lekin
   * `.light .liquid-glass-input` foni `rgba(255,255,255,.75)` — ya'ni
   * yorug' rejimda OQ USTIGA OQ (≈1.1:1) va maydonlar butunlay
   * KO'RINMAYDI. Panel `isDark` olmagani uchun qaror qabul qila
   * olmasdi.
   */
  isDark: boolean;
  /**
   * 🔴🔴🔴 `/admin/stats` `/admin/balance` `/admin/wallet`
   *    `/admin/contest` `/admin/orders`
   *    Har bir boshqaruv bo'limi — alohida xizmat, alohida manzil.
   *    Avval hammasi bitta uzun sahifada ketma-ket edi.
   */
  initialSection?: AdminSub;
  onSectionChange?: (s: AdminSub) => void;
}

/** Bo'lim sarlavhalari (boshqaruv paneli navigatsiyasi). */
const ADMIN_SECTIONS: { id: AdminSub; label: string }[] = [
  { id: 'stats', label: 'Statistika' },
  { id: 'balance', label: 'Balans' },
  { id: 'wallet', label: 'TON / USDT' },
  { id: 'contest', label: 'Konkurs' },
  { id: 'orders', label: 'Buyurtmalar' },
];

export const AdminPanel: React.FC<AdminPanelProps> = ({ onSettingsUpdated, isDark, initialSection = 'stats', onSectionChange }) => {
  /** 🔴 Bo'lim manzildan keladi — ichki state yo'q. */
  const section = initialSection || 'stats';
  const switchSection = (s: AdminSub) => { if (onSectionChange) onSectionChange(s); };
  /** Kirish maydonlari matni: yorug' rejimda oq emas, QORA bo'lishi SHART. */
  const fieldText = isDark ? 'text-white' : 'text-neutral-900';
  // 🔴 `.light .liquid-glass-pill` foni `rgba(255,255,255,.6)` —
  // deyarli oq. Ustidagi `text-purple-300` (≈1.4:1) va
  // `text-neutral-200` (≈1.2:1) oq ustida KO'RINMAYDI.
  const accentText = isDark ? 'text-purple-300' : 'text-purple-700';
  // 🔴 yorug' rejimda `neutral-400` = 2.4:1 (o'tmaydi)
  const dimText = isDark ? 'text-neutral-400' : 'text-neutral-600';
  const msgText = isDark ? 'text-neutral-200' : 'text-neutral-700';
  const [authenticated, setAuthenticated] = useState<boolean>(false);
  const [password, setPassword] = useState<string>('');
  const [adminData, setAdminData] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Konkurs boshqaruvi
  const [contest, setContest] = useState<Contest | null>(null);
  const [ctForm, setCtForm] = useState({
    text: '',
    prize_stars: '1000',
    winners: '5',
    min: '20000',
    days: '7',
  });
  const [ctLoading, setCtLoading] = useState(false);
  const [ctMsg, setCtMsg] = useState<string | null>(null);
  // Ro'yxatni yopiq saqlash (12-rasm: uzoq ro'yxat asosiy ekranni bosib qo'yardi)
  const [showAllOrders, setShowAllOrders] = useState<boolean>(false);

  const loadContest = async () => {
    try {
      const res = await fetch('/api/admin/contest');
      const data = await res.json();
      if (data.ok && data.contest) {
        setContest(data.contest);
        setCtForm({
          text: (data.contest.text || '').replace(/<[^>]+>/g, ''),
          prize_stars: String(data.contest.prize_stars || 1000),
          winners: String(data.contest.winners || 5),
          min: String(data.contest.min || 20000),
          days: String(Math.max(1, Math.round((data.contest.ends_in || 604800) / 86400))),
        });
      }
    } catch (e) {
      /* offline */
    }
  };

  const saveContest = async (active: boolean) => {
    setCtLoading(true);
    setCtMsg(null);
    try {
      const res = await fetch('/api/admin/contest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: ctForm.text,
          prize_stars: Number(ctForm.prize_stars),
          winners: Number(ctForm.winners),
          min: Number(ctForm.min),
          days: Number(ctForm.days),
          active,
        }),
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || 'Xatolik');
      setContest(data.contest);
      setCtMsg(active ? '✅ Konkurs yaratildi va e\'lon qilindi!' : '🛑 Konkurs tugatildi.');
      loadContest();
    } catch (err: any) {
      setCtMsg('❌ ' + err.message);
    } finally {
      setCtLoading(false);
    }
  };

  // Balance adjustment state
  const [adjUserId, setAdjUserId] = useState<string>('8307046273');
  const [adjAmount, setAdjAmount] = useState<string>('50000');
  const [adjMsg, setAdjMsg] = useState<string | null>(null);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await fetch('/api/admin/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
      });
      const data = await res.json();
      if (!data.ok) {
        throw new Error(data.error || "Parol noto'g'ri");
      }
      setAuthenticated(true);
      fetchAdminData();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchAdminData = async () => {
    try {
      const res = await fetch('/api/admin/data');
      const data = await res.json();
      if (data.ok) {
        setAdminData(data);
        onSettingsUpdated(data.settings);
      }
    } catch (err) {
      console.error(err);
    }
    loadContest();
  };

  const toggleBot = async () => {
    try {
      const res = await fetch('/api/admin/toggle-bot', { method: 'POST' });
      const data = await res.json();
      if (data.ok) {
        fetchAdminData();
      }
    } catch (err) {
      console.error(err);
    }
  };

  const adjustBalance = async () => {
    setAdjMsg(null);
    if (!adjUserId || !adjAmount) return;
    try {
      const res = await fetch('/api/admin/adjust-balance', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ userId: adjUserId, amount: adjAmount }),
      });
      const data = await res.json();
      if (data.ok) {
        setAdjMsg(`✅ Balans muvaffaqiyatli o'zgartirildi! Yangi balans: ${Number(data.user.balance ?? 0).toLocaleString()} UZS`);
        fetchAdminData();
      } else {
        setAdjMsg(`❌ Xatolik: ${data.error}`);
      }
    } catch (err: any) {
      setAdjMsg(`❌ Xatolik: ${err.message}`);
    }
  };

  if (!authenticated) {
    return (
      <div className="max-w-md md:max-w-none md:px-6 xl:px-10 mx-auto my-12 rounded-3xl bg-slate-900 border border-white/10 p-8 shadow-2xl space-y-6">
        <div className="text-center space-y-2">
          <div className="w-14 h-14 mx-auto rounded-2xl bg-purple-500/20 border border-purple-500/30 flex items-center justify-center text-purple-400">
            <Lock className="w-6 h-6" />
          </div>
          <h2 className="text-lg font-bold text-white">Admin Paneliga Kirish</h2>
          <p className="text-xs text-slate-400">
            Parol: Railway Variables dagi <code className={`font-mono ${accentText}`}>ADMIN_PASSWORD</code>
          </p>
        </div>

        <form onSubmit={handleLogin} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-300">Admin paroli</label>
            <input
              type="password"
              placeholder="Parolni kiriting..."
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-2.5 rounded-xl bg-slate-950 border border-white/10 text-sm text-white placeholder-slate-500 outline-none focus:border-purple-500"
            />
          </div>

          {error && (
            <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3.5 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-bold text-sm tracking-wide shadow-lg shadow-purple-900/30 cursor-pointer disabled:opacity-50"
          >
            {loading ? 'Kirilmoqda...' : 'Kirish'}
          </button>
        </form>
      </div>
    );
  }

  const settings = adminData?.settings;
  const stats = adminData?.stats;

  return (
    <div className="space-y-6">
      {/* 🔴🔴🔴 BO'LIM NAVIGATSIYASI — har bir boshqaruv xizmati
          o'z manzili bilan: /admin/stats, /admin/balance,
          /admin/wallet, /admin/contest, /admin/orders */}
      {authenticated && (
        <div className="flex items-center gap-1.5 overflow-x-auto scrollbar-none">
          {ADMIN_SECTIONS.map((s) => (
            <button
              key={s.id}
              onClick={() => switchSection(s.id)}
              className={`py-1.5 px-3.5 rounded-full text-xs font-semibold whitespace-nowrap border apple-spring cursor-pointer ${
                section === s.id
                  ? isDark ? 'bg-white text-black border-white' : 'bg-black text-white border-black'
                  : 'liquid-glass-pill opacity-75 hover:opacity-100'
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>
      )}

      {/* Admin stats */}
      {section === 'stats' && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="p-4 rounded-2xl bg-slate-900 border border-white/10">
            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <Users className="w-3.5 h-3.5 text-cyan-400" /> Jami foydalanuvchilar
            </div>
            <div className="text-2xl font-black text-white mt-1">
              {Number(stats?.totalUsers || 0).toLocaleString()}
            </div>
          </div>

          <div className="p-4 rounded-2xl bg-slate-900 border border-white/10">
            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <ShoppingBag className="w-3.5 h-3.5 text-purple-400" /> Jami buyurtmalar
            </div>
            <div className={`text-2xl font-black mt-1 ${accentText}`}>
              {Number(stats?.totalOrders || 0).toLocaleString()}
            </div>
          </div>

          <div className="p-4 rounded-2xl bg-slate-900 border border-white/10">
            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <DollarSign className="w-3.5 h-3.5 text-emerald-400" /> Jami aylanma
            </div>
            <div className="text-xl font-black text-emerald-400 mt-1">
              {Number(stats?.totalVolume || 0).toLocaleString()} <span className="text-xs">UZS</span>
            </div>
            <div className="text-[9px] text-slate-500 mt-0.5">
              Bugungi: {Number(stats?.todayVolume || 0).toLocaleString()} UZS
            </div>
          </div>

          <div className="p-4 rounded-2xl bg-slate-900 border border-white/10">
            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <Wallet className="w-3.5 h-3.5 text-teal-400" /> Tushum (sotilgan)
            </div>
            <div className="text-xl font-black text-teal-300 mt-1">
              {Number(stats?.totalRevenue || 0).toLocaleString()}{' '}
              <span className="text-xs">UZS</span>
            </div>
            <div className="text-[9px] text-slate-500 mt-0.5">
              Kutilmoqda: {Number(stats?.topupsPending || 0).toLocaleString()}
            </div>
          </div>

          <div className="p-4 rounded-2xl bg-slate-900 border border-white/10">
            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-amber-400" /> Kutayotgan buyurtma
            </div>
            <div className="text-xl font-black text-amber-300 mt-1">
              {Number(stats?.pendingOrders || 0).toLocaleString()}
            </div>
            <div className="text-[9px] text-slate-500 mt-0.5">
              Bekor: {Number(stats?.cancelledOrders || 0).toLocaleString()}
            </div>
          </div>

          <div className="p-4 rounded-2xl bg-slate-900 border border-white/10">
            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <TrendingUp className="w-3.5 h-3.5 text-sky-400" /> Bajarilgan xaridlar
            </div>
            <div className="text-xl font-black text-sky-300 mt-1">
              {Number(stats?.completedOrders || 0).toLocaleString()}{' '}
              <span className="text-xs text-slate-500">
                / {Number(stats?.totalOrders || 0).toLocaleString()}
              </span>
            </div>
          </div>

          <div className="p-4 rounded-2xl bg-slate-900 border border-white/10 flex flex-col justify-between">
            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <Power className="w-3.5 h-3.5 text-amber-400" /> Bot holati
            </div>
            <div className="flex items-center justify-between mt-1">
              <span
                className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                  settings?.bot_active
                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                    : 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                }`}
              >
                {settings?.bot_active ? '🟢 Faol' : '🔴 To\'xtatilgan'}
              </span>
              <button
                onClick={toggleBot}
                className="text-xs text-cyan-400 hover:text-cyan-300 font-bold underline"
              >
                {settings?.bot_active ? 'To\'xtatish' : 'Ishga tushirish'}
              </button>
            </div>
          </div>
        </div>

      )}

      {/* Balance Adjuster Section */}
      {section === 'balance' && (
        <div className="rounded-3xl bg-slate-900 border border-white/10 p-6 space-y-4">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <span>Foydalanuvchi balansini boshqarish</span>
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="space-y-1">
              <label className="text-xs text-slate-400">Telegram User ID</label>
              <input
                type="text"
                value={adjUserId}
                onChange={(e) => setAdjUserId(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-white/10 text-xs font-mono text-white outline-none focus:border-cyan-500"
              />
            </div>

            <div className="space-y-1">
              <label className="text-xs text-slate-400">Summa (+ yoki - so'mda)</label>
              <input
                type="number"
                value={adjAmount}
                onChange={(e) => setAdjAmount(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-white/10 text-xs font-mono text-white outline-none focus:border-cyan-500"
              />
            </div>

            <div className="flex items-end">
              <button
                onClick={adjustBalance}
                className="w-full py-2.5 px-4 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white font-bold text-xs transition-colors cursor-pointer"
              >
                Balansni o'zgartirish
              </button>
            </div>
          </div>

          {adjMsg && (
            <div className="p-3 rounded-xl bg-slate-950 border border-white/10 text-xs text-slate-200">
              {adjMsg}
            </div>
          )}
        </div>

      )}

      {/* TON Wallet & Fragment USDT Configuration */}
      {section === 'wallet' && (
        <div className="rounded-3xl bg-slate-900 border border-white/10 p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <DollarSign className="w-4 h-4 text-emerald-400" />
              <span>TON Hamyon va Fragment USDT Sozlamalari</span>
            </h3>
            <span className="text-xs font-mono text-emerald-400 font-bold">
              Mavjud: {settings?.wallet_usdt_balance ?? 50} USDT
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="space-y-1">
              <label className="text-xs text-slate-400">Hamyondagi USDT balansi</label>
              <input
                type="number"
                step="0.01"
                defaultValue={settings?.wallet_usdt_balance ?? 50}
                id="admin_usdt_bal"
                className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-white/10 text-white text-xs font-mono"
              />
            </div>

            <div className="space-y-1">
              <label className="text-xs text-slate-400">1 ⭐ Stars kursi (USDT)</label>
              <input
                type="number"
                step="0.001"
                defaultValue={settings?.star_usdt_rate ?? 0.015}
                id="admin_star_rate"
                placeholder="0.015 (100 stars = 1.5 USDT)"
                className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-white/10 text-white text-xs font-mono"
              />
            </div>

            <div className="flex items-end">
              <button
                onClick={async () => {
                  const balInput = document.getElementById('admin_usdt_bal') as HTMLInputElement;
                  const rateInput = document.getElementById('admin_star_rate') as HTMLInputElement;
                  try {
                    const res = await fetch('/api/admin/wallet-balance', {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({
                        balance: parseFloat(balInput?.value || '50'),
                        star_usdt_rate: parseFloat(rateInput?.value || '0.015'),
                      }),
                    });
                    const d = await res.json();
                    if (d.ok) {
                      alert("✅ Hamyon sozlamalari saqlandi!");
                      fetchAdminData();
                    }
                  } catch (e: any) {
                    alert("Xatolik: " + e.message);
                  }
                }}
                className="w-full py-2.5 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs transition-colors cursor-pointer"
              >
                Hamyonni Saqlash
              </button>
            </div>
          </div>

          <p className="text-[11px] text-slate-400 leading-relaxed">
            100 ⭐ Stars narxi = <b>{((settings?.star_usdt_rate || 0.015) * 100).toFixed(2)} USDT</b>.
            Kurs o'zgarganda ushbu maydonda yangilab borishingiz mumkin.
          </p>
        </div>

      )}

      {/* Konkurs boshqaruvi */}
      {section === 'contest' && (
        <div className="rounded-3xl liquid-glass-card p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold flex items-center gap-2">
              <Trophy className="w-4 h-4 text-purple-400" />
              <span>Konkurs boshqaruvi</span>
            </h3>
            <span
              className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                contest?.active ? 'bg-emerald-500/20 text-emerald-300' : 'bg-slate-500/20 text-slate-400'
              }`}
            >
              {contest?.active ? '🟢 Faol' : '⚪ Faol emas'}
            </span>
          </div>

          {contest?.active && (
            <div className="p-3 rounded-2xl liquid-glass-pill text-[11px] space-y-1">
              <div className={`font-bold ${accentText}`}>
                {contest.text?.replace(/<[^>]+>/g, '')}
              </div>
              <div className={dimText}>
                🏆 {contest.prize_stars} ⭐ · 🥇 {contest.winners} ta g'olib · 💰 min{' '}
                {(contest.min || 0).toLocaleString()} UZS
              </div>
              <div className={dimText}>
                👥 {Array.isArray(contest.participants) ? contest.participants.length : 0} ishtirokchi
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1 sm:col-span-2">
              <label className="text-xs text-slate-400">Konkurs matni</label>
              <input
                type="text"
                value={ctForm.text}
                onChange={(e) => setCtForm({ ...ctForm, text: e.target.value })}
                placeholder="Misol: 🎉 Yangi yil sovg'asi — 1000 Stars!"
                className={`w-full px-3 py-2.5 rounded-xl liquid-glass-input text-xs ${fieldText}`}
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-slate-400">Sovrin (Stars)</label>
              <input
                type="number"
                value={ctForm.prize_stars}
                onChange={(e) => setCtForm({ ...ctForm, prize_stars: e.target.value })}
                className={`w-full px-3 py-2.5 rounded-xl liquid-glass-input text-xs font-mono ${fieldText}`}
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-slate-400">G'oliblar soni</label>
              <input
                type="number"
                value={ctForm.winners}
                onChange={(e) => setCtForm({ ...ctForm, winners: e.target.value })}
                className={`w-full px-3 py-2.5 rounded-xl liquid-glass-input text-xs font-mono ${fieldText}`}
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-slate-400">Minimal xarid (UZS)</label>
              <input
                type="number"
                value={ctForm.min}
                onChange={(e) => setCtForm({ ...ctForm, min: e.target.value })}
                className={`w-full px-3 py-2.5 rounded-xl liquid-glass-input text-xs font-mono ${fieldText}`}
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-slate-400">Davomiylik (kun)</label>
              <input
                type="number"
                value={ctForm.days}
                onChange={(e) => setCtForm({ ...ctForm, days: e.target.value })}
                className={`w-full px-3 py-2.5 rounded-xl liquid-glass-input text-xs font-mono ${fieldText}`}
              />
            </div>
          </div>

          <div className="flex gap-2">
            <button
              onClick={() => saveContest(true)}
              disabled={ctLoading}
              className="flex-1 py-2.5 px-4 rounded-xl apple-spring cursor-pointer font-bold text-xs bg-purple-600 hover:bg-purple-500 text-white disabled:opacity-50"
            >
              {ctLoading ? 'Saqlanmoqda...' : '🎉 Yaratish / Yangilash'}
            </button>
            {contest?.active && (
              <button
                onClick={() => saveContest(false)}
                disabled={ctLoading}
                className="py-2.5 px-4 rounded-xl apple-spring cursor-pointer font-bold text-xs bg-rose-600 hover:bg-rose-500 text-white disabled:opacity-50"
              >
                🛑 Tugatish
              </button>
            )}
          </div>

          {ctMsg && (
            <div className={`p-3 rounded-xl liquid-glass-pill text-[11px] ${msgText}`}>{ctMsg}</div>
          )}
        </div>

      )}

      {/* Orders List */}
      {section === 'orders' && (
        <div className="rounded-3xl bg-slate-900 border border-white/10 p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-white">So'nggi buyurtmalar (Live)</h3>
            <button
              onClick={fetchAdminData}
              className="p-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
        </div>

        <div className="space-y-2">
          {/* DIQQAT: ternary `adminData` hali yo'q bo'lsa `undefined` qaytaradi —
              uning ustida to'g'ridan-to'g'ri .map() chaqirilsa, render
              crash qilib butun ekran oq bo'lib qolardi (kirishdan keyin). */}
          {((showAllOrders ? adminData?.orders : adminData?.orders?.slice(0, 5)) || []).map((ord: any) => (
            <div
              key={ord.id}
              className="p-3 rounded-xl bg-slate-950/80 border border-white/5 flex items-center justify-between text-xs"
            >
              <div>
                <span className="font-bold text-white">{ord.title}</span>
                <span className="text-slate-400 ml-2">({ord.recipient ? `@${ord.recipient}` : 'NFT ijara'})</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="font-bold text-cyan-400">{ord.price?.toLocaleString()} UZS</span>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-300">
                  {ord.status}
                </span>
              </div>
            </div>
          ))}
        </div>

      {/* Ro'yxat uzun bo'lmasligi uchun: bitta tugma bosilganda
            to'liq ro'yxat ochiladi (5 ta birinchi ko'rsatiladi). */}
        {(adminData?.orders?.length || 0) > 5 && (
          <button
            onClick={() => setShowAllOrders((v) => !v)}
            className="w-full py-2.5 rounded-xl liquid-glass-pill text-xs font-semibold
                       text-neutral-200 hover:text-white transition-colors cursor-pointer
                       flex items-center justify-center gap-1.5"
          >
            {showAllOrders ? (
              <>
                <ChevronUp className="w-3.5 h-3.5" />
                <span>Yopish</span>
              </>
            ) : (
              <>
                <ChevronDown className="w-3.5 h-3.5" />
                <span>
                  So&apos;nggi buyurtmalar ({adminData?.orders?.length} ta)
                </span>
              </>
            )}
          </button>
        )}
      </div>
      )}
    </div>
  );
};
