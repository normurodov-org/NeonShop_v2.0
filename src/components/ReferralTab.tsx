import React, { useState } from 'react';
import { User, StoreSettings } from '../types';
import { Users, Star, Copy, Check, ArrowRight, Gift, AlertCircle } from 'lucide-react';

interface ReferralTabProps {
  user: User | null;
  settings: StoreSettings | null;
  onWithdrawSuccess: (newBalance: number, msg: string) => void;
}

export const ReferralTab: React.FC<ReferralTabProps> = ({
  user,
  settings,
  onWithdrawSuccess,
}) => {
  const [copied, setCopied] = useState<boolean>(false);
  const [withdrawing, setWithdrawing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const refLink = `https://t.me/shop_neonbot?start=ref_${user?.id || '8307046273'}`;
  const refStars = user?.ref_stars || 0;
  const canWithdraw = refStars >= 50;
  const withdrawUzs = refStars * (settings?.star_buy_price || 200);

  const handleCopy = () => {
    navigator.clipboard.writeText(refLink);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleWithdraw = async () => {
    setError(null);
    if (!canWithdraw) {
      setError("Yechib olish uchun kamida 50 ⭐ Stars to'plashingiz kerak.");
      return;
    }

    setWithdrawing(true);
    try {
      const res = await fetch('/api/referral/withdraw', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      const data = await res.json();
      if (!data.ok) {
        throw new Error(data.error || "Yechib olishda xatolik");
      }
      onWithdrawSuccess(data.balance, data.message);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setWithdrawing(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Banner */}
      <div className="rounded-2xl bg-gradient-to-r from-amber-500/15 via-purple-500/15 to-blue-500/15 border border-amber-500/20 p-5">
        <div className="flex items-center gap-3.5">
          <div className="w-12 h-12 rounded-2xl bg-amber-500/20 border border-amber-500/30 flex items-center justify-center text-amber-300 text-2xl shrink-0">
            👥
          </div>
          <div>
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              Referal Dasturi
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 font-semibold border border-amber-500/30">
                1 do'st = 1 ⭐
              </span>
            </h2>
            <p className="text-xs text-slate-300 mt-0.5">
              Do'stlaringizni taklif qiling, har bir do'st uchun Telegram Stars oling va balansingizga bepul yechib oling.
            </p>
          </div>
        </div>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <div className="rounded-2xl bg-slate-900/80 border border-white/10 p-4">
          <div className="text-[11px] text-slate-400">Taklif qilingan do'stlar</div>
          <div className="text-2xl font-black text-white mt-1">
            {user?.referrals_count || 0}{' '}
            <span className="text-xs font-normal text-slate-400">odam</span>
          </div>
        </div>

        <div className="rounded-2xl bg-slate-900/80 border border-white/10 p-4">
          <div className="text-[11px] text-slate-400">To'plangan Stars</div>
          <div className="text-2xl font-black text-amber-400 mt-1 flex items-center gap-1">
            <Star className="w-5 h-5 fill-amber-400 text-amber-400" />
            <span>{refStars} ⭐</span>
          </div>
        </div>

        <div className="col-span-2 sm:col-span-1 rounded-2xl bg-slate-900/80 border border-white/10 p-4">
          <div className="text-[11px] text-slate-400">Yechish mumkin (so'mda)</div>
          <div className="text-2xl font-black text-cyan-400 mt-1">
            {withdrawUzs.toLocaleString()}{' '}
            <span className="text-xs font-normal text-slate-400">UZS</span>
          </div>
        </div>
      </div>

      {/* Referral Link Copy */}
      <div className="bg-slate-900/80 rounded-2xl border border-white/10 p-5 space-y-3">
        <label className="text-xs font-bold text-slate-300">
          Sizning shaxsiy referal havolangiz:
        </label>
        <div className="flex items-center gap-2 bg-slate-950 p-2 rounded-xl border border-white/10">
          <input
            type="text"
            readOnly
            value={refLink}
            className="w-full bg-transparent px-2 text-xs font-mono text-cyan-300 outline-none truncate"
          />
          <button
            onClick={handleCopy}
            className="shrink-0 px-3.5 py-2 rounded-lg bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 font-semibold text-xs flex items-center gap-1.5 transition-colors cursor-pointer"
          >
            {copied ? (
              <>
                <Check className="w-3.5 h-3.5 text-emerald-400" />
                <span className="text-emerald-400">Nusxalandi</span>
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5" />
                <span>Nusxa olish</span>
              </>
            )}
          </button>
        </div>
        <p className="text-[11px] text-slate-400">
          Ushbu havolani do'stlaringizga, kanallarga va guruhlarga ulashing.
        </p>
      </div>

      {/* Error message */}
      {error && (
        <div className="flex items-center gap-2 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">
          <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
          <span>{error}</span>
        </div>
      )}

      {/* Withdraw section */}
      <div className="rounded-2xl bg-slate-950 border border-white/10 p-5 space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="text-xs font-bold text-white flex items-center gap-1.5">
              <Gift className="w-4 h-4 text-amber-400" />
              <span>Stars'ni asosiy balansga o'tkazish</span>
            </div>
            <p className="text-[11px] text-slate-400 mt-0.5">
              Minimal yechib olish miqdori: <b>50 ⭐ Stars</b>
            </p>
          </div>
          <button
            onClick={handleWithdraw}
            disabled={!canWithdraw || withdrawing}
            className={`py-3 px-5 rounded-xl text-xs font-black transition-all flex items-center justify-center gap-2 cursor-pointer ${
              canWithdraw
                ? 'bg-amber-500 hover:bg-amber-400 text-slate-950 shadow-lg shadow-amber-500/20 active:scale-95'
                : 'bg-slate-800 text-slate-500 cursor-not-allowed'
            }`}
          >
            <span>{refStars} ⭐ Balansga yechish ({withdrawUzs.toLocaleString()} UZS)</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};
