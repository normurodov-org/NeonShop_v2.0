import React, { useState, useEffect } from 'react';
import { User, StoreSettings, Topup } from '../../types';
import { Lang, translations } from '../../i18n';
import { CreditCard, Copy, Check, Clock, Plus, History, AlertCircle, RefreshCw, X } from 'lucide-react';
import { tgHeaders, tgHeadersGet } from '../../lib/tgAuth';

interface TopupViewProps {
  user: User | null;
  settings: StoreSettings | null;
  lang: Lang;
  isDark: boolean;
  activeTopup: Topup | null;
  onTopupCreated: (t: Topup) => void;
  onTopupSuccess: (newBalance: number, msg: string) => void;
  /** 🔴 To'lov muddati tugadi yoki bekor qilindi — ilova karta va
   *  poller ni TO'XTATISHI kerak (o'siz o'lik to'lov kartasi ekranda
   *  qoladi va har 4 soniyada so'rov yuborishda davom etadi). */
  onTopupCancelled: (status?: 'expired' | 'cancelled') => void;
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
  onTopupCancelled,
  onOpenHistory,
}) => {
  const t = translations[lang];
  const [selectedAmount, setSelectedAmount] = useState<number>(50000);
  const [customAmount, setCustomAmount] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<boolean>(false);
  const [simulating, setSimulating] = useState<boolean>(false);

  /** 🔴 Oxirgi ko'rilgan `rescan_done_at` — takror xabarni chiqarmaslik uchun. */
  const lastRescanSeen = React.useRef<number>(0);

  const presets = [10000, 25000, 50000, 100000, 250000, 500000];

  /**
   * AVTO TO'LDIRISH (WebApp tomoni)
   * ---------------------------------
   * Foydalanuvchi so'mni kartaga o'tkazadi, userbot bank xabarini aniqlab bazada
   * `completed` qiladi. Bu yerda har 4 soniyada holat tekshiriladi va balans
   * darhol yangilanadi — mijozning "Tasdiqlash" tugmasini bosishi shart emas.
   */
  useEffect(() => {
    if (!activeTopup || activeTopup.status !== 'pending') return;
    let alive = true;
    const poll = async () => {
      try {
        // 🔴 IMZO MUHIM. Server endi `x-telegram-user-id` ni
        // ISHONCHLI DEB QABUL QILMAYDI (faqat `X-Telegram-Init-Data`).
        // Bu header bo'lmasa 401 kelardi va AVTO-YUKLASH butunlay
        // ISHLAMASDI — ya'ni mijoz kartaga pul yuborsa, hech qachon
        // avtomatik to'ldirilmay qolardi ("xisob toldirish ishlamayapti").
        const res = await fetch(`/api/topup/status?id=${encodeURIComponent(activeTopup.id)}`, {
          headers: tgHeadersGet(),
        });
        const data = await res.json();
        if (!alive || !data.ok) return;

        const st = data.topup?.status;
        if (st === 'completed') {
          onTopupSuccess(
            Number(data.balance ?? user?.balance ?? 0),
            `✅ ${activeTopup.amount.toLocaleString()} UZS avtomatik to'ldirildi!`
          );
          return;
        }
        if (st === 'expired' || st === 'cancelled') {
          // 🔴 ESKI KOD FAQAT `setError` qilardi:
          //   * `activeTopup` holati HECH QACHON yangilanmasdi — `App`dagi
          //     `activeTopup` `pending` da qolardi
          //   * shuning uchun poller OCHILMAY qolardi va 4 soniyada bir
          //     so'rov KECHIB KETARDI
          //   * o'lik to'lov kartasi (karta raqami + nusxa ko'chirish)
          //     ekranda qolardi
          // Endi holat `App`ga yoziladi — poller o'z-o'zidan to'xtaydi
          // va karta yo'qoladi.
          setError(
            st === 'expired'
              ? "To'lov so'rovi muddati tugadi. Qayta urinib ko'ring."
              : "To'lov bekor qilindi."
          );
          onTopupCancelled?.(st);
          return;
        }

        // 🔴🔴🔴 «Tekshirish» natijasi — server `rescan_*` maydonlarini
        //   yozadi, bot.py dagi worker esa @humocardbot tarixini QAYTA
        //   o'qib, topilsa balansni avtomatik to'ldiradi. Bu yerda
        //   mijozga NIMA bo'ganini aniq ko'rsatamiz.
        const done = Number(data.topup?.rescan_done_at) || 0;
        if (done && done !== lastRescanSeen.current) {
          lastRescanSeen.current = done;
          const r = String(data.topup?.rescan_result || '');
          if (r === 'found') {
            setError('');   // poller `completed` holatini ham kutadi
          } else if (r === 'not_found') {
            setError(String(data.topup?.rescan_message || ''));
          } else if (r === 'userbot_offline') {
            setError(
              'Bank xabari avtomatik tekshirilmaydi — userbot ulanmagan. '
              + 'Iltimos yordamchiga murojaat qiling: to\'lov qo\'lda tasdiqlanadi.'
            );
          } else if (r === 'chat_empty') {
            // 🔴🔴🔴 Eng ko'p uchraydigan sabab: userbot kartani
            //   EGASINING akkaunti emas. Bank xabari faqat karta
            //   egasiga yuboriladi — kod bilan tuzatib bo'lmaydi.
            setError(
              'Bank xabarida hech narsa topilmadi: bot karta egasi akkaunti '
              + 'bilan ulangan emas. Iltimos yordamchiga murojaat qiling.'
            );
          } else if (r && r !== 'found' && r !== 'already') {
            // 🔴 Texnik xato — mijozga «nima qilish kerak» aytilmasin,
            //    ammo sabab ko'rinishi uchun maydon chiqariladi.
            setError(String(data.topup?.rescan_message || ''));
          }
        }
      } catch (e) {
        /* tarmoq uzilishi — keyingi urinishda tekshiramiz */
      }
    };

    poll();
    const timer = setInterval(poll, 4000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [activeTopup?.id, activeTopup?.status, user?.id]);

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
        headers: tgHeaders(),
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

  // To'lov so'rovini bekor qilish (mijoz xato summani tanlagan bo'lsa)
  const handleCancel = async () => {
    if (!activeTopup) return;
    setSimulating(true);
    setError(null);
    try {
      const res = await fetch('/api/topup/cancel', {
        method: 'POST',
        headers: tgHeaders(),
        body: JSON.stringify({ id: activeTopup.id }),
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || 'Bekor qilindi');
      onTopupCancelled();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSimulating(false);
    }
  };

  const handleSimulatePayment = async () => {
    // 🔴 «To'lovni tekshirish» ni ikki marta bosish mumkin —
    // har safar `POST /api/topup/simulate-pay` ketar edi.
    if (simulating) return;
    if (!activeTopup) return;
    setSimulating(true);
    setError(null);
    try {
      const res = await fetch('/api/topup/simulate-pay', {
        method: 'POST',
        headers: tgHeaders(),
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
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSimulating(false);
    }
  };

  return (
    <div className="space-y-4 max-w-md md:max-w-3xl md:px-6 mx-auto pb-28 md:pb-10 apple-view-animate">
      {/* Header bar */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className={`text-xl font-bold tracking-tight ${isDark ? 'text-white' : 'text-neutral-900'}`}>{t.topup}</h2>
          <p className={`text-xs mt-0.5 ${isDark ? 'text-neutral-400' : 'text-neutral-500'}`}>
            {t.balance}: <b className={`font-mono font-bold ${isDark ? 'text-white' : 'text-black'}`}>{Number(user?.balance ?? 0).toLocaleString()} UZS</b>
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
            <span className={`${isDark ? 'text-neutral-400' : 'text-neutral-600'} font-mono text-[11px]`}>
              ID: <b>{activeTopup.id}</b>
            </span>
          </div>

          <div className={`p-4 rounded-[20px] space-y-2 ${isDark ? 'bg-black/30' : 'bg-white/60'} border border-white/10`}>
            {/* 🔴 BU YERDA `amount_to_send` KO'RSATILADI, `amount` EMAS.
                Har bir to'lovga ketma-ket raqam qo'shiladi (1000 -> 1001
                -> 1002 ...) va bot aynan `amount_to_send` ni bank
                xabaridan qidiradi. `amount` ko'rsatilsa, mijoz to'g'ri
                summani yubormaydi va uning puli QOLIB KETADI.

                Bot yaratgan to'lovlarda `amount_to_send` yo'q — u holda
                `amount` ishlatiladi (bot o'z xabarida to'g'ri summani
                ko'rsatadi). */}
            <div className={`text-[11px] ${isDark ? 'text-neutral-400' : 'text-neutral-600'} font-medium`}>
              Kartaga yuborish uchun ANIQ summa:
            </div>
            <div className={`text-2xl font-bold font-mono tracking-tight ${isDark ? 'text-white' : 'text-neutral-900'}`}>
              {(activeTopup.amount_to_send ?? activeTopup.amount).toLocaleString()}{' '}
              <span className="text-xs font-normal opacity-70">UZS</span>
            </div>
            {activeTopup.amount_to_send != null
              && activeTopup.amount_to_send !== activeTopup.amount ? (
              <div className="text-[10px] text-amber-400/90">
                ⚠️ Aynan shu {activeTopup.amount_to_send.toLocaleString()} so'mni
                yuboring — boshqa summa avtomatik topilmaydi.
              </div>
            ) : null}

            {/* 📌 Buyurtma raqami (№) — mijoz uchun qulay va
                «qayerdan keldi?» savoliga aniq javob.
                🔴 Bu raqam BALANSGA QO'SHILMAYDI — faqat to'lovni
                chalkashtirmaslik uchun. Balansga `amount` (so'rangan
                summa) qo'shiladi. */}
            {activeTopup.amount_to_send != null
              && activeTopup.amount_to_send !== activeTopup.amount ? (
              <div className={`text-[10px] ${isDark ? 'text-neutral-400' : 'text-neutral-600'} mt-1`}>
                So&apos;ragan: <b>{activeTopup.amount.toLocaleString()}</b> so&apos;m
                {' · '}№<b>{(activeTopup as any).seq ?? activeTopup.amount_to_send - activeTopup.amount}</b>
                {' · '}farqlash uchun +<b>{(activeTopup.amount_to_send - activeTopup.amount).toLocaleString()}</b>
              </div>
            ) : null}

            <div className="pt-2 border-t border-white/10 flex items-center justify-between">
              <div>
                <div className={`text-[10px] ${isDark ? 'text-neutral-400' : 'text-neutral-600'}`}>Karta raqami:</div>
                <div className={`text-sm font-mono font-bold tracking-wider ${isDark ? 'text-white' : 'text-neutral-900'}`}>
                  {activeTopup.card || (isDark ? 'bot orqali' : '—')}
                </div>
                <div className={`text-[10px] ${isDark ? 'text-neutral-400' : 'text-neutral-600'} mt-0.5`}>
                  {activeTopup.holder || ' '}
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

          <p className={`text-[11px] ${isDark ? 'text-neutral-400' : 'text-neutral-600'} leading-relaxed`}>
            {t.transferNotice}
          </p>

          {/* 📖 BITTAGINA: ilgari ikkita bir xil tugma bor edi
              («To'lovni tekshirish / Tasdiqlash» va «To'lovni tekshirish»)
              — ikkalasi ham `handleSimulatePayment` ni chaqirardi va
              «Tasdiqlash» birinchisida spinner yo'q edi (bosilganini
              bilib bo'lmasdi). Endi bitta tugma + loader. */}
          <div className="flex items-center gap-2">
            <button
              onClick={handleSimulatePayment}
              disabled={simulating}
              className={`flex-1 py-3.5 rounded-[18px] font-semibold text-xs flex items-center justify-center gap-2 apple-spring cursor-pointer disabled:opacity-60 ${
                isDark ? 'bg-white text-black hover:bg-neutral-100' : 'bg-black text-white hover:bg-neutral-800'
              }`}
            >
              {simulating ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
              <span>
                {simulating
                  ? 'Tekshirilmoqda…'
                  : 'To’lovni tekshirish / Tasdiqlash'}
              </span>
            </button>
            <button
              onClick={handleCancel}
              disabled={simulating}
              className={`py-3.5 px-5 rounded-[18px] font-semibold text-xs flex items-center justify-center gap-1.5 apple-spring cursor-pointer ${
                isDark
                  ? 'bg-white/10 text-white/80 hover:bg-white/15 border border-white/10'
                  : 'bg-black/5 text-neutral-700 hover:bg-black/10 border border-black/5'
              }`}
            >
              <X className="w-4 h-4" />
              <span>Bekor qilish</span>
            </button>
          </div>
        </div>
      )}

      {/* Main Top-up Creation Card */}
      <div className="rounded-[28px] liquid-glass-card p-5 space-y-4">
        <label className={`block text-xs font-semibold ${isDark ? 'text-neutral-300' : 'text-neutral-700'}`}>
          Top-up amount (UZS)
        </label>

        {/* Minimalist Input box */}
        <div className="relative">
          <div className={`absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none ${isDark ? 'text-neutral-400' : 'text-neutral-600'}`}>
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
          <div className={`absolute inset-y-0 right-0 pr-4 flex items-center pointer-events-none text-xs font-mono ${isDark ? 'text-neutral-400' : 'text-neutral-600'}`}>
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
        <p className={`text-[11px] ${isDark ? 'text-neutral-400' : 'text-neutral-600'} leading-relaxed`}>
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
