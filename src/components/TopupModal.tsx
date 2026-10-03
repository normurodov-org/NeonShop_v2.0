import React, { useState, useEffect } from 'react';
import { User, Topup, StoreSettings } from '../types';
import { X, Copy, Check, Clock, CreditCard, ShieldCheck, Zap, AlertCircle, RefreshCw } from 'lucide-react';

interface TopupModalProps {
  isOpen: boolean;
  onClose: () => void;
  user: User | null;
  settings: StoreSettings | null;
  activeTopup: Topup | null;
  onTopupSuccess: (newBalance: number, msg: string) => void;
  onTopupCreated: (topup: Topup) => void;
  onTopupCancelled: () => void;
}

export const TopupModal: React.FC<TopupModalProps> = ({
  isOpen,
  onClose,
  user,
  settings,
  activeTopup,
  onTopupSuccess,
  onTopupCreated,
  onTopupCancelled,
}) => {
  const [selectedAmount, setSelectedAmount] = useState<number>(50000);
  const [customAmount, setCustomAmount] = useState<string>('');
  const [copied, setCopied] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);
  const [simulating, setSimulating] = useState<boolean>(false);
  const [timeLeft, setTimeLeft] = useState<number>(300);
  const [error, setError] = useState<string | null>(null);

  const presets = [10000, 25000, 50000, 100000, 250000, 500000, 1000000];

  useEffect(() => {
    if (activeTopup) {
      setTimeLeft(activeTopup.expires_in || 300);
      const timer = setInterval(() => {
        setTimeLeft((prev) => {
          if (prev <= 1) {
            clearInterval(timer);
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
      return () => clearInterval(timer);
    }
  }, [activeTopup]);

  if (!isOpen) return null;

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
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: activeTopup.id }),
      });
      const data = await res.json();
      if (!data.ok) {
        throw new Error(data.error || "Tasdiqlashda xatolik");
      }
      if (data.pending) {
        setError(data.message || "⏳ To'lov tekshirilmoqda, iltimos kuting...");
        return;
      }
      onTopupSuccess(data.balance, data.message);
      onClose();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSimulating(false);
    }
  };

  const handleCancelTopup = async () => {
    if (!activeTopup) return;
    try {
      await fetch('/api/topup/cancel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: activeTopup.id }),
      });
      onTopupCancelled();
    } catch (err) {
      console.error(err);
    }
  };

  const minutes = Math.floor(timeLeft / 60);
  const seconds = timeLeft % 60;
  const timeFormatted = `${minutes}:${seconds < 10 ? '0' : ''}${seconds}`;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-lg rounded-3xl bg-slate-900 border border-white/15 p-6 shadow-2xl space-y-5 max-h-[90vh] overflow-y-auto">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-5 right-5 p-2 rounded-full bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Modal Title */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-cyan-500/20 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
            <CreditCard className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white">Balansni to'ldirish</h2>
            <p className="text-xs text-slate-400">Humo / Uzcard orqali avtomatik to'ldirish</p>
          </div>
        </div>

        {error && (
          <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {!activeTopup ? (
          /* Step 1: Select Amount */
          <div className="space-y-5">
            <div className="space-y-2">
              <label className="text-xs font-semibold text-slate-300">
                To'ldirish summasini tanlang
              </label>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {presets.map((preset) => (
                  <button
                    key={preset}
                    type="button"
                    onClick={() => {
                      setSelectedAmount(preset);
                      setCustomAmount('');
                    }}
                    className={`py-2.5 px-3 rounded-xl text-xs font-bold transition-all border ${
                      selectedAmount === preset && !customAmount
                        ? 'bg-cyan-500/20 border-cyan-500 text-cyan-300 shadow-md shadow-cyan-500/10'
                        : 'bg-slate-950/60 border-white/10 text-slate-300 hover:border-white/20'
                    }`}
                  >
                    +{preset.toLocaleString()} UZS
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-400">
                Yoki boshqa summa kiriting (so'mda):
              </label>
              <div className="relative">
                <input
                  type="number"
                  placeholder="Summa, masalan: 75 000"
                  value={customAmount}
                  onChange={(e) => {
                    setCustomAmount(e.target.value);
                    setSelectedAmount(0);
                  }}
                  className="w-full px-4 py-2.5 rounded-xl bg-slate-950 border border-white/10 text-sm text-white placeholder-slate-500 outline-none focus:border-cyan-500"
                />
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-slate-400 font-semibold">
                  UZS
                </span>
              </div>
            </div>

            <div className="rounded-2xl bg-cyan-950/20 border border-cyan-500/20 p-4 space-y-2 text-xs text-slate-300">
              <div className="flex items-center gap-2 text-cyan-300 font-semibold">
                <Zap className="w-4 h-4 text-cyan-400" />
                <span>Avtomat Humo/Uzcard to'lov tizimi</span>
              </div>
              <p className="text-[11px] text-slate-400 leading-relaxed">
                Kartaga pul o'tkazishingiz bilan bot bank xabarnomasini o'zi ushlaydi va balansingizni 10–20 soniya ichida to'ldiradi.
              </p>
            </div>

            <button
              onClick={handleCreateTopup}
              disabled={loading}
              className="w-full py-4 px-4 rounded-2xl bg-gradient-to-r from-emerald-500 via-green-500 to-teal-500 hover:from-emerald-400 hover:to-green-400 text-white font-black text-sm tracking-wide shadow-xl shadow-emerald-950/60 ring-2 ring-emerald-400/50 active:scale-[0.99] transition-all cursor-pointer disabled:opacity-50"
            >
              {loading ? "So'rov yaratilmoqda..." : "🟢 To'lovga o'tish (Yashil)"}
            </button>
          </div>
        ) : (
          /* Step 2: Payment details with Timer and Humo simulation */
          <div className="space-y-5">
            {/* Timer banner */}
            <div className="flex items-center justify-between p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs">
              <div className="flex items-center gap-2 font-semibold">
                <Clock className="w-4 h-4 text-amber-400 animate-spin" />
                <span>To'lov uchun qolgan vaqt:</span>
              </div>
              <span className="font-mono font-black text-sm text-amber-200">
                {timeFormatted}
              </span>
            </div>

            {/* Card Information */}
            <div className="rounded-2xl bg-slate-950 border border-white/10 p-5 space-y-4">
              <div className="space-y-1">
                <div className="text-[11px] text-slate-400">O'tkazilishi kerak bo'lgan summa:</div>
                <div className="text-2xl font-black text-emerald-400">
                  {activeTopup.amount.toLocaleString()}{' '}
                  <span className="text-sm font-semibold text-slate-400">UZS</span>
                </div>
              </div>

              <div className="space-y-1">
                <div className="text-[11px] text-slate-400">Qabul qiluvchi karta (HUMO):</div>
                <div className="flex items-center justify-between bg-slate-900 px-3.5 py-2.5 rounded-xl border border-white/10">
                  <span className="font-mono font-bold text-white text-sm tracking-wider">
                    {activeTopup.card}
                  </span>
                  <button
                    onClick={handleCopyCard}
                    className="flex items-center gap-1 text-xs text-cyan-400 hover:text-cyan-300 font-semibold"
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
              </div>

              <div className="flex justify-between items-center text-xs text-slate-400">
                <span>Karta egasi:</span>
                <span className="font-semibold text-white">{activeTopup.holder}</span>
              </div>
            </div>

            {/* Instruction */}
            <div className="text-[11px] text-slate-400 space-y-1 bg-slate-950/50 p-3 rounded-xl border border-white/5">
              <p className="text-slate-300 font-medium">📌 To'lov yo'riqnomasi:</p>
              <p>1. Kartaga aniq <b>{activeTopup.amount.toLocaleString()} UZS</b> o'tkazing (Payme, Click, Apelsin, bank ilovasi).</p>
              <p>2. To'lov amalga oshishi bilan bot to'lovni avtomatik aniqlaydi.</p>
            </div>

            {/* Simulation button for reviewer/testing (Blue) */}
            <div className="p-3.5 rounded-2xl bg-blue-950/30 border border-blue-500/30 space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold text-blue-300 flex items-center gap-1.5">
                  <ShieldCheck className="w-4 h-4 text-blue-400" />
                  Bank bildirishnomasini simulyatsiya qilish
                </span>
                <span className="text-[10px] bg-blue-500/20 text-blue-300 px-1.5 py-0.5 rounded font-bold">
                  Test / Demo
                </span>
              </div>
              <p className="text-[10px] text-slate-400">
                Haqiqiy kartaga pul o'tkazmasdan to'lovni tasdiqlash jarayonini sinab ko'ring:
              </p>
              <button
                onClick={handleSimulatePayment}
                disabled={simulating}
                className="w-full py-3 px-3 rounded-xl bg-gradient-to-r from-blue-600 via-indigo-600 to-cyan-500 hover:from-blue-500 hover:to-cyan-400 text-white font-black text-xs flex items-center justify-center gap-2 transition-all shadow-lg shadow-blue-950/50 cursor-pointer disabled:opacity-50"
              >
                {simulating ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  <>
                    <Zap className="w-4 h-4" />
                    <span>🔵 To'lovni tasdiqlash ({activeTopup.amount.toLocaleString()} UZS qo'shish)</span>
                  </>
                )}
              </button>
            </div>

            {/* Cancel Button (Red) */}
            <div className="flex gap-2">
              <button
                onClick={handleCancelTopup}
                className="w-full py-3 px-3 rounded-xl bg-gradient-to-r from-rose-900 to-red-800 hover:from-rose-800 hover:to-red-700 text-white font-bold text-xs transition-colors cursor-pointer border border-rose-500/30 shadow-md"
              >
                🔴 So'rovni bekor qilish (Qizil)
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
