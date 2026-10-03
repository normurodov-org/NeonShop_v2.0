import React, { useState } from 'react';
import { User, StoreSettings } from '../types';
import { Star, Send, ShieldCheck, Zap, UserCheck, AlertCircle, CheckCircle2, ArrowRight } from 'lucide-react';

interface StarsTabProps {
  user: User | null;
  settings: StoreSettings | null;
  onOrderSuccess: (order: any, newBalance: number, msg: string) => void;
  onOpenTopup: () => void;
}

export const StarsTab: React.FC<StarsTabProps> = ({
  user,
  settings,
  onOrderSuccess,
  onOpenTopup,
}) => {
  const [amount, setAmount] = useState<number>(100);
  const [recipient, setRecipient] = useState<string>(user?.username || '');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const starPrice = settings?.star_buy_price || 200;
  const totalPrice = amount * starPrice;
  const userBalance = user?.balance || 0;
  const isEnough = userBalance >= totalPrice;
  const cashback = Math.floor(totalPrice * 0.001);

  const presets = [50, 100, 250, 500, 1000, 2500, 5000, 10000];

  const handleBuy = async () => {
    setError(null);
    const cleanUser = recipient.replace('@', '').trim();
    if (!cleanUser) {
      setError("Iltimos, Telegram username kiriting (masalan: @durov)");
      return;
    }

    if (amount < 50 || amount > 1000000) {
      setError("Minimal 50 ta, maksimal 1 000 000 ta Stars kiritish mumkin.");
      return;
    }

    if (!isEnough) {
      setError(`Balans yetarli emas. Narx: ${totalPrice.toLocaleString()} UZS, balansingiz: ${userBalance.toLocaleString()} UZS.`);
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
          kind: 'stars',
          amount,
          username: cleanUser,
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
    <div className="space-y-5">
      {/* Promo banner */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-amber-500/15 via-purple-500/15 to-cyan-500/15 border border-amber-500/20 p-5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="w-12 h-12 rounded-2xl bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-300 shrink-0 shadow-lg shadow-amber-500/10">
              <Star className="w-7 h-7 fill-amber-400 text-amber-400 animate-pulse" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                Telegram Stars — Fragment orqali tezkor
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 font-semibold border border-amber-500/30">
                  1 ⭐ = {starPrice} UZS
                </span>
              </h2>
              <p className="text-xs text-slate-300 mt-0.5">
                Fragment.com va TON orqali rasmiy va xavfsiz. 1-2 daqiqada hisobingizga tushadi.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 self-start md:self-center">
            <span className="flex items-center gap-1 text-[11px] text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded-lg border border-emerald-500/20 font-medium">
              <Zap className="w-3.5 h-3.5" /> Avtomatik yetkazish
            </span>
          </div>
        </div>
      </div>

      {/* Main card */}
      <div className="bg-slate-900/80 rounded-2xl border border-white/10 p-5 md:p-6 space-y-6">
        {/* Recipient Input */}
        <div className="space-y-2">
          <label className="text-xs font-semibold text-slate-300 flex items-center justify-between">
            <span>Telegram @username (Qabul qiluvchi)</span>
            {user?.username && (
              <button
                type="button"
                onClick={() => setRecipient(user.username)}
                className="text-[11px] text-cyan-400 hover:text-cyan-300 flex items-center gap-1 font-medium transition-colors"
              >
                <UserCheck className="w-3 h-3" />
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
              placeholder="username (masalan: durov)"
              className="w-full pl-8 pr-4 py-2.5 rounded-xl bg-slate-950/80 border border-white/10 focus:border-cyan-500/80 focus:ring-1 focus:ring-cyan-500 text-sm text-white placeholder-slate-500 outline-none transition-all font-mono"
            />
          </div>
          <p className="text-[11px] text-slate-400">
            Stars to'g'ridan-to'g'ri shu akkauntga Fragment orqali yuboriladi.
          </p>
        </div>

        {/* Amount Selector */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <label className="text-xs font-semibold text-slate-300">
              Stars miqdori (Minimal: 50 ⭐)
            </label>
            <div className="flex items-center gap-1 font-bold text-amber-300 text-sm">
              <Star className="w-4 h-4 fill-amber-400 text-amber-400" />
              <span>{amount.toLocaleString()} ⭐</span>
            </div>
          </div>

          {/* Quick presets */}
          <div className="grid grid-cols-4 sm:grid-cols-8 gap-2">
            {presets.map((preset) => (
              <button
                key={preset}
                type="button"
                onClick={() => setAmount(preset)}
                className={`py-2 px-1 rounded-xl text-xs font-bold transition-all border ${
                  amount === preset
                    ? 'bg-amber-500/20 border-amber-500 text-amber-300 shadow-md shadow-amber-500/10'
                    : 'bg-slate-950/60 border-white/10 text-slate-300 hover:border-white/20 hover:bg-slate-800'
                }`}
              >
                {preset.toLocaleString()}
              </button>
            ))}
          </div>

          {/* Slider */}
          <div className="pt-2">
            <input
              type="range"
              min={50}
              max={10000}
              step={25}
              value={amount}
              onChange={(e) => setAmount(Number(e.target.value))}
              className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-amber-400"
            />
          </div>

          {/* Manual input */}
          <div className="flex items-center justify-between pt-1">
            <span className="text-[11px] text-slate-400">Yoki o'zingiz kiriting:</span>
            <div className="relative w-36">
              <input
                type="number"
                min={50}
                max={1000000}
                value={amount}
                onChange={(e) => setAmount(Math.max(0, Number(e.target.value)))}
                className="w-full px-3 py-1.5 rounded-lg bg-slate-950 border border-white/10 text-right text-xs font-bold text-amber-300 pr-7 outline-none focus:border-amber-400"
              />
              <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-amber-400 font-bold">⭐</span>
            </div>
          </div>
        </div>

        {/* Order Price calculation breakdown */}
        <div className="rounded-xl bg-slate-950/90 border border-white/10 p-4 space-y-2.5">
          <div className="flex justify-between items-center text-xs text-slate-400">
            <span>1 ⭐ narxi</span>
            <span className="font-medium text-slate-200">{starPrice} UZS</span>
          </div>
          <div className="flex justify-between items-center text-xs text-slate-400">
            <span>Stars miqdori</span>
            <span className="font-semibold text-amber-300">{amount.toLocaleString()} ⭐</span>
          </div>
          <div className="flex justify-between items-center text-xs text-slate-400">
            <span>0.1% Keshbek</span>
            <span className="font-medium text-emerald-400">+{cashback} UZS</span>
          </div>
          <div className="border-t border-white/10 pt-2.5 flex justify-between items-center">
            <span className="text-sm font-bold text-white">Jami to'lov:</span>
            <div className="text-right">
              <span className="text-lg font-black text-cyan-400 tracking-tight">
                {totalPrice.toLocaleString()}
              </span>
              <span className="text-xs text-slate-400 ml-1 font-bold">UZS</span>
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

        {/* Action Button */}
        <div>
          {isEnough ? (
            <button
              onClick={handleBuy}
              disabled={loading}
              className="w-full py-4 px-4 rounded-2xl bg-gradient-to-r from-emerald-500 via-green-500 to-teal-500 hover:from-emerald-400 hover:via-green-400 hover:to-teal-400 text-white font-black text-sm tracking-wide shadow-xl shadow-emerald-950/60 ring-2 ring-emerald-400/50 active:scale-[0.99] transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
            >
              {loading ? (
                <span>Fragment orqali yuborilmoqda...</span>
              ) : (
                <>
                  <Send className="w-4 h-4" />
                  <span>🟢 Xaridni tasdiqlash ({totalPrice.toLocaleString()} UZS)</span>
                </>
              )}
            </button>
          ) : (
            <div className="space-y-2">
              <button
                onClick={onOpenTopup}
                className="w-full py-4 px-4 rounded-2xl bg-gradient-to-r from-blue-600 via-indigo-600 to-cyan-500 hover:from-blue-500 hover:to-cyan-400 text-white font-black text-sm shadow-xl shadow-blue-950/60 active:scale-[0.99] transition-all flex items-center justify-center gap-2 cursor-pointer"
              >
                <span>🔵 Balans yetarli emas — Balansni to'ldirish (Ko'k)</span>
                <ArrowRight className="w-4 h-4" />
              </button>
              <p className="text-[11px] text-center text-slate-400">
                Yetishmayotgan summa: {(totalPrice - userBalance).toLocaleString()} UZS
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
