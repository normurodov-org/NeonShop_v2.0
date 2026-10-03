import React, { useState } from 'react';
import { User, GiftItem } from '../types';
import { Gift, Star, Send, AlertCircle, ArrowRight, UserCheck } from 'lucide-react';

interface GiftsTabProps {
  user: User | null;
  onOrderSuccess: (order: any, newBalance: number, msg: string) => void;
  onOpenTopup: () => void;
}

export const GiftsTab: React.FC<GiftsTabProps> = ({
  user,
  onOrderSuccess,
  onOpenTopup,
}) => {
  const gifts: GiftItem[] = [
    { key: 'bear', name: 'Ayiqcha', stars: 15, priceUzs: 3000, emoji: '🧸', tag: 'Trend' },
    { key: 'heart', name: 'Yurakcha', stars: 15, priceUzs: 3000, emoji: '💝', tag: 'Mashhur' },
    { key: 'box', name: "Sovg'a qutisi", stars: 25, priceUzs: 6000, emoji: '🎁' },
    { key: 'rose', name: 'Atirgul', stars: 25, priceUzs: 6000, emoji: '🌹' },
    { key: 'cake', name: 'Tort', stars: 50, priceUzs: 10000, emoji: '🎂' },
    { key: 'bouquet', name: 'Gul dastasi', stars: 50, priceUzs: 10000, emoji: '💐' },
    { key: 'rocket', name: 'Raketa', stars: 50, priceUzs: 10000, emoji: '🚀', tag: 'Top' },
    { key: 'cup', name: 'Kubok', stars: 100, priceUzs: 20000, emoji: '🏆' },
    { key: 'ring', name: 'Uzuk', stars: 100, priceUzs: 20000, emoji: '💍' },
    { key: 'diamond', name: 'Olmos', stars: 100, priceUzs: 20000, emoji: '💎', tag: 'VIP' },
    { key: 'champagne', name: 'Shampan', stars: 50, priceUzs: 10000, emoji: '🍾' },
  ];

  const [selectedGift, setSelectedGift] = useState<GiftItem>(gifts[0]);
  const [recipient, setRecipient] = useState<string>(user?.username || '');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const userBalance = user?.balance || 0;
  const isEnough = userBalance >= selectedGift.priceUzs;

  const handleBuy = async () => {
    setError(null);
    const cleanUser = recipient.replace('@', '').trim();
    if (!cleanUser) {
      setError("Iltimos, Telegram username kiriting (masalan: @durov)");
      return;
    }

    if (!isEnough) {
      setError(`Balans yetarli emas. Narx: ${selectedGift.priceUzs.toLocaleString()} UZS, balansingiz: ${userBalance.toLocaleString()} UZS.`);
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
          kind: 'gift',
          gift: selectedGift.key,
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
    <div className="space-y-6">
      {/* Banner */}
      <div className="rounded-2xl bg-gradient-to-r from-pink-500/15 via-purple-500/15 to-indigo-500/15 border border-pink-500/20 p-5">
        <div className="flex items-center gap-3.5">
          <div className="w-12 h-12 rounded-2xl bg-pink-500/20 border border-pink-500/30 flex items-center justify-center text-pink-300 text-2xl shrink-0">
            🎁
          </div>
          <div>
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              Telegram Gifts (Sovg'alar)
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-pink-500/20 text-pink-300 font-semibold border border-pink-500/30">
                Avto-userbot
              </span>
            </h2>
            <p className="text-xs text-slate-300 mt-0.5">
              Istalgan profilga Telegram orqali sovg'a yuboriladi va uning profilida paydo bo'ladi.
            </p>
          </div>
        </div>
      </div>

      {/* Recipient username input */}
      <div className="bg-slate-900/80 rounded-2xl border border-white/10 p-4 space-y-2">
        <label className="text-xs font-semibold text-slate-300 flex items-center justify-between">
          <span>Sovg'a kimga yuborilsin? (Telegram @username)</span>
          {user?.username && (
            <button
              type="button"
              onClick={() => setRecipient(user.username)}
              className="text-[11px] text-pink-400 hover:text-pink-300 font-medium flex items-center gap-1"
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
            placeholder="masalan: durov"
            className="w-full pl-8 pr-4 py-2.5 rounded-xl bg-slate-950/80 border border-white/10 focus:border-pink-500/80 text-sm text-white placeholder-slate-500 outline-none font-mono"
          />
        </div>
      </div>

      {/* Gifts Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
        {gifts.map((item) => {
          const isSelected = selectedGift.key === item.key;
          return (
            <div
              key={item.key}
              onClick={() => setSelectedGift(item)}
              className={`relative cursor-pointer rounded-2xl p-4 border transition-all duration-200 flex flex-col items-center text-center ${
                isSelected
                  ? 'bg-gradient-to-b from-pink-950/50 to-slate-900 border-pink-500/80 ring-2 ring-pink-500/30 shadow-lg shadow-pink-950/40'
                  : 'bg-slate-900/70 border-white/10 hover:border-white/20 hover:bg-slate-900'
              }`}
            >
              {item.tag && (
                <span className="absolute top-2 right-2 px-1.5 py-0.5 rounded text-[9px] font-extrabold uppercase bg-pink-500/20 text-pink-300 border border-pink-500/30">
                  {item.tag}
                </span>
              )}
              <div className="text-4xl my-2 transform transition-transform hover:scale-110">
                {item.emoji}
              </div>
              <div className="font-bold text-white text-xs mt-1">{item.name}</div>
              <div className="flex items-center gap-1 text-[11px] text-amber-400 font-semibold mt-1">
                <Star className="w-3 h-3 fill-amber-400" />
                <span>{item.stars} ⭐</span>
              </div>
              <div className="text-xs font-black text-cyan-400 mt-1">
                {item.priceUzs.toLocaleString()} <span className="text-[10px] text-slate-400">UZS</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Selected summary */}
      <div className="rounded-2xl bg-slate-950/90 border border-white/10 p-5 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="text-3xl">{selectedGift.emoji}</span>
          <div>
            <div className="text-xs text-slate-400">Tanlangan sovg'a:</div>
            <div className="text-base font-extrabold text-white">
              {selectedGift.name} ({selectedGift.stars} ⭐)
            </div>
          </div>
        </div>
        <div className="text-right">
          <div className="text-xs text-slate-400">Narxi:</div>
          <div className="text-xl font-black text-cyan-400">
            {selectedGift.priceUzs.toLocaleString()} <span className="text-xs text-slate-400">UZS</span>
          </div>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">
          <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
          <span>{error}</span>
        </div>
      )}

      {/* CTA Button */}
      <div>
        {isEnough ? (
          <button
            onClick={handleBuy}
            disabled={loading}
            className="w-full py-4 px-6 rounded-2xl bg-gradient-to-r from-red-600 via-rose-600 to-pink-600 hover:from-red-500 hover:via-rose-500 hover:to-pink-500 text-white font-black text-sm shadow-xl shadow-red-950/60 ring-2 ring-red-400/50 active:scale-[0.99] transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
          >
            {loading ? (
              <span>Sovg'a yuborilmoqda...</span>
            ) : (
              <>
                <Send className="w-4 h-4" />
                <span>
                  🔴 {selectedGift.emoji} {selectedGift.name} yuborish ({selectedGift.priceUzs.toLocaleString()} UZS)
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
              Yetishmayotgan summa: {(selectedGift.priceUzs - userBalance).toLocaleString()} UZS
            </p>
          </div>
        )}
      </div>
    </div>
  );
};
