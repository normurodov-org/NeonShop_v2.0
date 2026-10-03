import React, { useState } from 'react';
import { User } from '../types';
import { Sparkles, Check, Gift, Key, ShieldCheck, ArrowRight, AlertCircle, Zap } from 'lucide-react';

interface PremiumTabProps {
  user: User | null;
  onOrderSuccess: (order: any, newBalance: number, msg: string) => void;
  onOpenTopup: () => void;
}

export const PremiumTab: React.FC<PremiumTabProps> = ({
  user,
  onOrderSuccess,
  onOpenTopup,
}) => {
  const [mode, setMode] = useState<'nologin' | 'login'>('nologin');
  const [selectedMonths, setSelectedMonths] = useState<number>(12);
  const [recipient, setRecipient] = useState<string>(user?.username || '');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const plans = {
    nologin: [
      { months: 3, price: 155000, label: '3 oy', badge: null, monthly: '51 600 UZS / oy' },
      { months: 6, price: 205000, label: '6 oy', badge: 'Tavsiya etiladi', monthly: '34 100 UZS / oy' },
      { months: 12, price: 375000, label: '12 oy (1 yil)', badge: 'Eng tejamkor 🔥', monthly: '31 250 UZS / oy' },
    ],
    login: [
      { months: 1, price: 40000, label: '1 oy', badge: null, monthly: '40 000 UZS / oy' },
      { months: 12, price: 285000, label: '12 oy (1 yil)', badge: 'Super narx 💎', monthly: '23 750 UZS / oy' },
    ],
  };

  const currentPlans = plans[mode];
  const activePlan = currentPlans.find((p) => p.months === selectedMonths) || currentPlans[0];
  const userBalance = user?.balance || 0;
  const isEnough = userBalance >= activePlan.price;

  const handleBuy = async () => {
    setError(null);
    const cleanUser = recipient.replace('@', '').trim();
    if (mode === 'nologin' && !cleanUser) {
      setError("Sovg'a qabul qiluvchi Telegram @username'ni kiriting.");
      return;
    }

    if (!isEnough) {
      setError(`Balans yetarli emas. Narx: ${activePlan.price.toLocaleString()} UZS, balansingiz: ${userBalance.toLocaleString()} UZS.`);
      return;
    }

    setLoading(true);
    try {
      const res = await fetch('/api/order', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-telegram-user-id': user?.id?.toString() || '',
        },
        body: JSON.stringify({
          kind: 'premium',
          mode,
          months: activePlan.months,
          username: cleanUser || user?.username,
        }),
      });
      const data = await res.json();
      if (!data.ok) {
        throw new Error(data.error || "Xatolik yuz berdi");
      }
      onOrderSuccess(data.order, data.balance, data.message);
    } catch (err: any) {
      setError(err.message || "Buyurtma berishda xatolik");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Mode selection tabs */}
      <div className="flex p-1.5 rounded-2xl bg-slate-900 border border-white/10 gap-1.5">
        <button
          type="button"
          onClick={() => {
            setMode('nologin');
            setSelectedMonths(12);
          }}
          className={`flex-1 py-3 px-4 rounded-xl text-xs sm:text-sm font-bold flex items-center justify-center gap-2 transition-all ${
            mode === 'nologin'
              ? 'bg-gradient-to-r from-purple-600 to-indigo-600 text-white shadow-lg shadow-purple-900/40 border border-purple-400/30'
              : 'text-slate-400 hover:text-white'
          }`}
        >
          <Gift className="w-4 h-4 text-purple-300" />
          <span>Sovg'a sifatida (Parolsiz)</span>
        </button>
        <button
          type="button"
          onClick={() => {
            setMode('login');
            setSelectedMonths(12);
          }}
          className={`flex-1 py-3 px-4 rounded-xl text-xs sm:text-sm font-bold flex items-center justify-center gap-2 transition-all ${
            mode === 'login'
              ? 'bg-gradient-to-r from-cyan-600 to-blue-600 text-white shadow-lg shadow-cyan-900/40 border border-cyan-400/30'
              : 'text-slate-400 hover:text-white'
          }`}
        >
          <Key className="w-4 h-4 text-cyan-300" />
          <span>Akkauntga kirib (Arzonroq)</span>
        </button>
      </div>

      {/* Recipient username for Gift mode */}
      {mode === 'nologin' && (
        <div className="bg-slate-900/80 rounded-2xl border border-white/10 p-4 space-y-2">
          <label className="text-xs font-semibold text-slate-300 flex items-center justify-between">
            <span>Kimga yuborilsin? (@username)</span>
            {user?.username && (
              <button
                type="button"
                onClick={() => setRecipient(user.username)}
                className="text-[11px] text-purple-400 hover:text-purple-300 font-medium"
              >
                O'zimga (@{user.username})
              </button>
            )}
          </label>
          <div className="relative">
            <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 font-bold text-sm">@</span>
            <input
              type="text"
              value={recipient}
              onChange={(e) => setRecipient(e.target.value.replace('@', ''))}
              placeholder="qabul_qiluvchi_username"
              className="w-full pl-8 pr-4 py-2.5 rounded-xl bg-slate-950/80 border border-white/10 focus:border-purple-500/80 text-sm text-white placeholder-slate-500 outline-none font-mono"
            />
          </div>
        </div>
      )}

      {/* Plans Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {currentPlans.map((plan) => {
          const isSelected = selectedMonths === plan.months;
          return (
            <div
              key={plan.months}
              onClick={() => setSelectedMonths(plan.months)}
              className={`relative cursor-pointer rounded-2xl p-5 border transition-all duration-200 flex flex-col justify-between ${
                isSelected
                  ? 'bg-gradient-to-b from-purple-950/40 to-slate-900 border-purple-500/80 ring-2 ring-purple-500/30 shadow-xl shadow-purple-950/50'
                  : 'bg-slate-900/70 border-white/10 hover:border-white/20 hover:bg-slate-900'
              }`}
            >
              {plan.badge && (
                <div className="absolute -top-3 right-4">
                  <span className="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wider bg-gradient-to-r from-amber-500 to-rose-500 text-slate-950 shadow-md">
                    {plan.badge}
                  </span>
                </div>
              )}

              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-base font-extrabold text-white">{plan.label}</span>
                  <div
                    className={`w-5 h-5 rounded-full border flex items-center justify-center ${
                      isSelected
                        ? 'bg-purple-500 border-purple-400 text-white'
                        : 'border-white/20'
                    }`}
                  >
                    {isSelected && <Check className="w-3.5 h-3.5 stroke-[3]" />}
                  </div>
                </div>

                <div className="mt-3">
                  <div className="text-2xl font-black text-cyan-400 tracking-tight">
                    {plan.price.toLocaleString()}
                    <span className="text-xs text-slate-400 font-normal ml-1">UZS</span>
                  </div>
                  <div className="text-[11px] text-slate-400 mt-0.5">{plan.monthly}</div>
                </div>
              </div>

              <div className="mt-5 pt-4 border-t border-white/10 space-y-1.5 text-xs text-slate-300">
                <div className="flex items-center gap-1.5 text-[11px]">
                  <Check className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                  <span>Telegram rasmiy obuna</span>
                </div>
                <div className="flex items-center gap-1.5 text-[11px]">
                  <Zap className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                  <span>Avtomatik faollashtirish</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Telegram Premium features list */}
      <div className="rounded-2xl bg-slate-900/60 border border-white/10 p-5 space-y-3">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-purple-400" />
          Telegram Premium imkoniyatlari
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-2.5 text-xs text-slate-300">
          <div className="flex items-center gap-2">
            <span className="text-purple-400 font-bold">✓</span>
            <span>4 GB gacha fayllar</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-purple-400 font-bold">✓</span>
            <span>Reklamalarsiz tezlik</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-purple-400 font-bold">✓</span>
            <span>Ovozli xabar matni</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-purple-400 font-bold">✓</span>
            <span>Premium nishoncha ⭐️</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-purple-400 font-bold">✓</span>
            <span>Cheksiz stikerlar & emoji</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-purple-400 font-bold">✓</span>
            <span>Tez yuklab olish tezligi</span>
          </div>
        </div>
      </div>

      {/* Error message */}
      {error && (
        <div className="flex items-center gap-2 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">
          <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
          <span>{error}</span>
        </div>
      )}

      {/* Action CTA */}
      <div>
        {isEnough ? (
          <button
            onClick={handleBuy}
            disabled={loading}
            className="w-full py-4 px-6 rounded-2xl bg-gradient-to-r from-blue-600 via-indigo-600 to-cyan-500 hover:from-blue-500 hover:via-indigo-500 hover:to-cyan-400 text-white font-black text-sm shadow-xl shadow-blue-950/60 ring-2 ring-blue-400/50 active:scale-[0.99] transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
          >
            {loading ? (
              <span>Buyurtma berilmoqda...</span>
            ) : (
              <>
                <Gift className="w-4 h-4" />
                <span>
                  🔵 Telegram Premium ({activePlan.label}) — {activePlan.price.toLocaleString()} UZS sotib olish
                </span>
              </>
            )}
          </button>
        ) : (
          <div className="space-y-2">
            <button
              onClick={onOpenTopup}
              className="w-full py-4 px-6 rounded-2xl bg-gradient-to-r from-emerald-600 to-green-600 hover:from-emerald-500 hover:to-green-500 text-white font-bold text-sm shadow-xl shadow-emerald-950/40 active:scale-[0.99] transition-all flex items-center justify-center gap-2 cursor-pointer"
            >
              <span>🟢 Balans yetarli emas — Balansni to'ldirish (Yashil)</span>
              <ArrowRight className="w-4 h-4" />
            </button>
            <p className="text-[11px] text-center text-slate-400">
              Yetishmayotgan summa: {(activePlan.price - userBalance).toLocaleString()} UZS
            </p>
          </div>
        )}
      </div>
    </div>
  );
};
