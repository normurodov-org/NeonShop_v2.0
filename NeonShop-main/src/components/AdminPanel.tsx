import React, { useState, useEffect } from 'react';
import { StoreSettings } from '../types';
import { Shield, Lock, Power, Users, ShoppingBag, DollarSign, CheckCircle2, AlertCircle, ArrowRight, RefreshCw } from 'lucide-react';

interface AdminPanelProps {
  onSettingsUpdated: (newSettings: StoreSettings) => void;
}

export const AdminPanel: React.FC<AdminPanelProps> = ({ onSettingsUpdated }) => {
  const [authenticated, setAuthenticated] = useState<boolean>(false);
  const [password, setPassword] = useState<string>('');
  const [adminData, setAdminData] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

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
        setAdjMsg(`✅ Balans muvaffaqiyatli o'zgartirildi! Yangi balans: ${data.user.balance.toLocaleString()} UZS`);
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
      <div className="max-w-md mx-auto my-12 rounded-3xl bg-slate-900 border border-white/10 p-8 shadow-2xl space-y-6">
        <div className="text-center space-y-2">
          <div className="w-14 h-14 mx-auto rounded-2xl bg-purple-500/20 border border-purple-500/30 flex items-center justify-center text-purple-400">
            <Lock className="w-6 h-6" />
          </div>
          <h2 className="text-lg font-bold text-white">Admin Paneliga Kirish</h2>
          <p className="text-xs text-slate-400">
            Standart parol: <code className="text-purple-300 font-mono">neon2025</code> yoki <code className="text-purple-300 font-mono">admin</code>
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
      {/* Admin stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="p-4 rounded-2xl bg-slate-900 border border-white/10">
          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
            <Users className="w-3.5 h-3.5 text-cyan-400" /> Jami foydalanuvchilar
          </div>
          <div className="text-2xl font-black text-white mt-1">
            {stats?.totalUsers?.toLocaleString() || '14,281'}
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-slate-900 border border-white/10">
          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
            <ShoppingBag className="w-3.5 h-3.5 text-purple-400" /> Jami buyurtmalar
          </div>
          <div className="text-2xl font-black text-purple-300 mt-1">
            {stats?.totalOrders?.toLocaleString() || '8,743'}
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-slate-900 border border-white/10">
          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
            <DollarSign className="w-3.5 h-3.5 text-emerald-400" /> Jami aylanma
          </div>
          <div className="text-xl font-black text-emerald-400 mt-1">
            {stats?.totalVolume?.toLocaleString() || '485 000 000'} <span className="text-xs">UZS</span>
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

      {/* Balance Adjuster Section */}
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

      {/* TON Wallet & Fragment USDT Configuration */}
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

      {/* Orders List */}
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
          {adminData?.orders?.map((ord: any) => (
            <div
              key={ord.id}
              className="p-3 rounded-xl bg-slate-950/80 border border-white/5 flex items-center justify-between text-xs"
            >
              <div>
                <span className="font-bold text-white">{ord.title}</span>
                <span className="text-slate-400 ml-2">(@{ord.recipient})</span>
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
      </div>
    </div>
  );
};
