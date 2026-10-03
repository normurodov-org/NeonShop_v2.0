import React, { useState } from 'react';
import { User, StoreSettings, Topup } from '../../types';
import { Lang, translations } from '../../i18n';
import { CreditCard, Copy, Check, Clock, Plus, History, AlertCircle, RefreshCw } from 'lucide-react';

interface TopupViewProps {
  user: User | null;
  settings: StoreSettings | null;
  lang: Lang;
  isDark: boolean;
  activeTopup: Topup | null;
  onTopupCreated: (t: Topup) => void;
  onTopupSuccess: (newBalance: number, msg: string) => void;
  onOpenHistory: () => void;
}

export const TopupView: React.FC<TopupViewProps> = ({
  user,
  settings,
  lang,
  isDark,
  activeTopup,
  onTopupCreated,
  onTopupSuccess,
  onOpenHistory,
}) => {
  const t = translations[lang];
  const [selectedAmount, setSelectedAmount] = useState<number>(50000);
  const [customAmount, setCustomAmount] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<boolean>(false);
  const [simulating, setSimulating] = useState<boolean>(false);

  const presets = [10000, 25000, 50000, 100000, 250000, 500000];

  const handleCopyCard = () => {
    const card = activeTopup?.card || settings?.card_number || '9860 1701 1569 3682';
    navigator.clipboard.writeText(card.replace(/\s+/g, ''));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleCreateTopup = async () => {
    setError(null);
    const amount = customAmount ? parseInt(customAmount, 10) : selectedAmount;
    if (!amount || amount < 1000 || amount > 10000000) {
      setError("1 000 dan 10 000 000 so'mgacha summa kiriting.");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch('/api/topup', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-telegram-user-id': user?.id?.toString() || '',
        },
        body: JSON.stringify({ amount }),
      });
      const data = await res.json();
      if (!data.ok) {
        throw new Error(data.error || "To'lov so'rovini yaratishda xatolik");
      }
      onTopupCreated(data.topup);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSimulatePayment = async () => {
    if (!activeTopup) return;
    setSimulating(true);
    setError(null);
    try {
      const res = await fetch('/api/topup/simulate-pay', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-telegram-user-id': user?.id?.toString() || '',
        },
        body: JSON.stringify({ id: activeTopup.id }),
      });
      const data = await res.json();
      if (!data.ok) {
        throw new Error(data.error || "Tasdiqlashda xatolik");
      }
      onTopupSuccess(data.balance, data.message);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSimulating(false);
    }
  };

  return (
    <div className="space-y-4 max-w-md mx-auto pb-28 apple-view-animate">
      {/* Header bar */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className={`text-xl font-bold tracking-tight ${isDark ? 'text-white' : 'text-neutral-900'}`}>{t.topup}</h2>
          <p className={`text-xs mt-0.5 ${isDark ? 'text-neutral-400' : 'text-neutral-500'}`}>
            {t.balance}: <b className={`font-mono font-bold ${isDark ? 'text-white' : 'text-black'}`}>{user?.balance.toLocaleString() || '0'} UZS</b>
          </p>
        </div>
        <button
          onClick={onOpenHistory}
          className="p-2.5 rounded-full liquid-glass-pill apple-spring cursor-pointer"
          title={t.orderHistory}
        >
          <History className="w-4 h-4 opacity-70" />
        </button>
      </div>

      {/* Active Topup Card (If pending payment exists) */}
      {activeTopup && (
        <div className="rounded-[28px] liquid-glass-card p-5 space-y-4">
          <div className="flex items-center justify-between text-xs">
            <span className={`px-3 py-1 rounded-full text-[11px] font-semibold flex items-center gap-1.5 ${
              isDark ? 'bg-amber-400/10 text-amber-300 border border-amber-400/20' : 'bg-amber-500/10 text-amber-700 border border-amber-500/20'
            }`}>
              <Clock className="w-3.5 h-3.5 animate-spin" />
              <span>To'lov kutilmoqda</span>
            </span>
            <span className="text-neutral-400 font-mono text-[11px]">
              ID: <b>{activeTopup.id}</b>
            </span>
          </div>

          <div className={`p-4 rounded-[20px] space-y-2 ${isDark ? 'bg-black/30' : 'bg-white/60'} border border-white/10`}>
            <div className="text-[11px] text-neutral-400 font-medium">To'lov summasi:</div>
            <div className={`text-2xl font-bold font-mono tracking-tight ${isDark ? 'text-white' : 'text-neutral-900'}`}>
              {activeTopup.amount.toLocaleString()} <span className="text-xs font-normal opacity-70">UZS</span>
            </div>

            <div className="pt-2 border-t border-white/10 flex items-center justify-between">
              <div>
                <div className="text-[10px] text-neutral-400">Karta raqami:</div>
                <div className={`text-sm font-mono font-bold tracking-wider ${isDark ? 'text-white' : 'text-neutral-900'}`}>
                  {activeTopup.card}
                </div>
                <div className="text-[10px] text-neutral-400 mt-0.5">
                  {activeTopup.holder}
                </div>
              </div>
              <button
                onClick={handleCopyCard}
                className="px-3 py-1.5 rounded-full liquid-glass-pill text-xs font-semibold flex items-center gap-1.5 apple-spring cursor-pointer"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copied ? t.copied : t.copyCard}</span>
              </button>
            </div>
          </div>

          <p className="text-[11px] text-neutral-400 leading-relaxed">
            {t.transferNotice}
          </p>

          <button
            onClick={handleSimulatePayment}
            disabled={simulating}
            className={`w-full py-3.5 rounded-[18px] font-semibold text-xs flex items-center justify-center gap-2 apple-spring cursor-pointer ${
              isDark ? 'bg-white text-black hover:bg-neutral-100' : 'bg-black text-white hover:bg-neutral-800'
            }`}
          >
            {simulating ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
            <span>To'lovni tekshirish / Tasdiqlash</span>
          </button>
        </div>
      )}

      {/* Main Top-up Creation Card */}
      <div className="rounded-[28px] liquid-glass-card p-5 space-y-4">
        <label className={`block text-xs font-semibold ${isDark ? 'text-neutral-300' : 'text-neutral-700'}`}>
          Top-up amount (UZS)
        </label>

        {/* Minimalist Input box */}
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-neutral-400">
            <CreditCard className="w-4 h-4" />
          </div>
          <input
            type="number"
            value={customAmount}
            onChange={(e) => {
              setCustomAmount(e.target.value);
              setError(null);
            }}
            placeholder={selectedAmount.toString()}
            className={`w-full pl-11 pr-14 py-3.5 rounded-[18px] font-mono text-base font-bold focus:outline-none apple-spring liquid-glass-input ${
              isDark ? 'text-white placeholder:text-neutral-600' : 'text-neutral-900 placeholder:text-neutral-400'
            }`}
          />
          <div className="absolute inset-y-0 right-0 pr-4 flex items-center pointer-events-none text-xs font-mono text-neutral-400">
            UZS
          </div>
        </div>

        {/* Segmented Quick select pills */}
        <div className="grid grid-cols-3 gap-2">
          {presets.map((amt) => {
            const isSel = !customAmount && selectedAmount === amt;
            return (
              <button
                key={amt}
                onClick={() => {
                  setCustomAmount('');
                  setSelectedAmount(amt);
                  setError(null);
                }}
                className={`py-2.5 px-2 rounded-[14px] text-xs font-semibold font-mono apple-spring cursor-pointer border ${
                  isSel
                    ? isDark
                      ? 'bg-white text-black border-white shadow-md'
                      : 'bg-black text-white border-black shadow-md'
                    : 'liquid-glass-pill opacity-80 hover:opacity-100'
                }`}
              >
                {amt.toLocaleString()}
              </button>
            );
          })}
        </div>

        {/* Helper text */}
        <p className="text-[11px] text-neutral-400 leading-relaxed">
          {t.transferNotice}
        </p>

        {/* Error message */}
        {error && (
          <div className="p-3 rounded-[16px] bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Apple Minimalist CTA Button */}
        <button
          onClick={handleCreateTopup}
          disabled={loading}
          className={`w-full py-3.5 rounded-[18px] font-semibold text-xs flex items-center justify-center gap-2 apple-spring cursor-pointer disabled:opacity-50 ${
            isDark
              ? 'bg-white text-black hover:bg-neutral-100 shadow-md'
              : 'bg-black text-white hover:bg-neutral-800 shadow-md'
          }`}
        >
          {loading ? (
            <RefreshCw className="w-4 h-4 animate-spin" />
          ) : (
            <Plus className="w-4 h-4 stroke-[2.4]" />
          )}
          <span>{t.createPayment}</span>
        </button>
      </div>
    </div>
  );
};
