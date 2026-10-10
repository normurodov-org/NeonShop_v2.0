import React, { useState, useEffect } from 'react';
import { User, StoreSettings, Order, UsdtRate } from '../../types';
import { Lang, translations } from '../../i18n';
import { Star, Sparkles, Gift, UserCheck, AlertCircle, RefreshCw, Edit3, Check, Wallet } from 'lucide-react';

interface BuyViewProps {
  user: User | null;
  settings: StoreSettings | null;
  lang: Lang;
  isDark: boolean;
  initialTab?: 'stars' | 'premium' | 'gifts';
  onOrderSuccess: (order: Order, newBalance: number, msg: string) => void;
  onGoToTopup: () => void;
}

export const BuyView: React.FC<BuyViewProps> = ({
  user,
  settings,
  lang,
  isDark,
  initialTab = 'stars',
  onOrderSuccess,
  onGoToTopup,
}) => {
  const t = translations[lang];
  const [subTab, setSubTab] = useState<'stars' | 'premium' | 'gifts'>(initialTab);

  // Chuqur menyu (masalan Premium/Gifts) tanlangan katoriya bilan sinxron bolsin
  React.useEffect(() => {
    setSubTab(initialTab);
  }, [initialTab]);

  // Form states
  const [recipient, setRecipient] = useState<string>(user?.username || '');
  const [resolvedProfile, setResolvedProfile] = useState<{
    username: string;
    display_name: string;
    photo_url?: string;
  } | null>(() => {
    if (user?.username) {
      return {
        username: user.username,
        display_name: user.first_name || `@${user.username}`,
        photo_url: user.photo_url,
      };
    }
    return null;
  });
  const [isEditingRecipient, setIsEditingRecipient] = useState<boolean>(!user?.username);
  const [resolving, setResolving] = useState<boolean>(false);

  const [amount, setAmount] = useState<number>(100);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Premium state
  const [premMode, setPremMode] = useState<'nologin' | 'login'>('nologin');
  const [premMonths, setPremMonths] = useState<number>(3);

  // Gifts state
  const [selectedGift, setSelectedGift] = useState<string>('bear');

  // USDT (TON) kursi — live API dan, settings orqali zaxira
  const [rate, setRate] = useState<UsdtRate | null>(null);

  const starPrice = settings?.star_buy_price || 200;
  const starsPresets = [50, 100, 250, 500, 1000];

  const usdtRate = rate?.usdt_uzs || settings?.usdt_rate_uzs || 0;
  const usdtForStars = +(amount * (settings?.star_usdt_rate || 0.015)).toFixed(3);
  // Kurs hali kelmagan bo'lsa — ko'rsatmaymiz (null bo'lib qolmasin)
  const showRate = usdtRate > 0;

  // USDT kursini yangilab turamiz (har daqiqada)
  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const res = await fetch('/api/rate');
        const data = await res.json();
        if (alive && data.ok) setRate(data);
      } catch (e) {
        /* offline — settings'dagi zaxira ishlatiladi */
      }
    };
    load();
    const timer = setInterval(load, 60000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, []);

  // Resolve recipient profile when username is changed
  useEffect(() => {
    const clean = recipient.replace('@', '').trim();
    if (!clean || clean.length < 3) {
      setResolvedProfile(null);
      return;
    }

    if (user?.username && clean.toLowerCase() === user.username.toLowerCase()) {
      setResolvedProfile({
        username: user.username,
        display_name: user.first_name || `@${user.username}`,
        photo_url: user.photo_url,
      });
      return;
    }

    const timer = setTimeout(async () => {
      setResolving(true);
      try {
        const res = await fetch(`/api/resolve-user?username=${encodeURIComponent(clean)}`);
        const data = await res.json();
        if (data.ok && data.user) {
          setResolvedProfile(data.user);
        }
      } catch (e) {
        console.error('Resolve user error:', e);
      } finally {
        setResolving(false);
      }
    }, 450);

    return () => clearTimeout(timer);
  }, [recipient, user]);

  const premPlans = {
    nologin: [
      { months: 3, price: 155000, label: '3 oy' },
      { months: 6, price: 205000, label: '6 oy' },
      { months: 12, price: 375000, label: '12 oy' },
    ],
    login: [
      { months: 1, price: 40000, label: '1 oy' },
      { months: 12, price: 285000, label: '12 oy' },
    ],
  };

  const giftsList = [
    { key: 'bear', name: '🧸 Ayiqcha', stars: 15, price: 3000 },
    { key: 'heart', name: '💝 Yurakcha', stars: 15, price: 3000 },
    { key: 'rose', name: '🌹 Atirgul', stars: 25, price: 6000 },
    { key: 'cake', name: '🎂 Tort', stars: 50, price: 10000 },
    { key: 'rocket', name: '🚀 Raketa', stars: 50, price: 10000 },
    { key: 'cup', name: '🏆 Kubok', stars: 100, price: 20000 },
    { key: 'diamond', name: '💎 Olmos', stars: 100, price: 20000 },
  ];

  // Calculate current price
  let currentPrice = 0;
  if (subTab === 'stars') {
    currentPrice = amount * starPrice;
  } else if (subTab === 'premium') {
    const p = premPlans[premMode].find((x) => x.months === premMonths);
    currentPrice = p?.price || 155000;
  } else if (subTab === 'gifts') {
    const g = giftsList.find((x) => x.key === selectedGift);
    currentPrice = g?.price || 3000;
  }

  const userBal = user?.balance || 0;
  const isEnough = userBal >= currentPrice;
  const needMore = Math.max(0, currentPrice - userBal);

  const handleBuy = async () => {
    setError(null);
    const cleanUser = recipient.replace('@', '').trim();
    if (!cleanUser) {
      setError("Iltimos, Telegram username kiriting (masalan: @durov)");
      return;
    }

    if (!isEnough) {
      setError(`${t.needMore} ${needMore.toLocaleString()} UZS.`);
      return;
    }

    setLoading(true);
    try {
      let body: any = { username: cleanUser };
      if (subTab === 'stars') {
        body = { ...body, kind: 'stars', amount };
      } else if (subTab === 'premium') {
        body = { ...body, kind: 'premium', mode: premMode, months: premMonths };
      } else if (subTab === 'gifts') {
        body = { ...body, kind: 'gift', gift: selectedGift };
      }

      const res = await fetch('/api/order', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-telegram-user-id': user?.id?.toString() || '',
        },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!data.ok) {
        throw new Error(data.error || "Buyurtma berishda xatolik");
      }
      onOrderSuccess(data.order, data.balance, data.message);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4 max-w-md mx-auto pb-28 apple-view-animate">
      {/* Title & Exchange rate header */}
      <div className="flex items-center justify-between">
        <h2 className={`text-xl font-bold tracking-tight ${isDark ? 'text-white' : 'text-neutral-900'}`}>{t.buy}</h2>
        <span className="text-[11px] font-bold px-3 py-1 rounded-full liquid-glass-pill opacity-90">
          1 ★ = {starPrice} UZS
        </span>
      </div>

      {/* USDT (TON) to'lov nishoni — Stars FAQAT USDT bilan Fragment'dan xarid qilinadi */}
      {subTab === 'stars' && (
        <div className="flex items-center justify-between gap-2 px-4 py-3 rounded-[22px] liquid-glass apple-view-animate">
          <div className="flex items-center gap-2.5 min-w-0">
            <div
              className={`w-8 h-8 rounded-[12px] flex items-center justify-center shrink-0 ${
                isDark ? 'bg-emerald-400/15 text-emerald-300' : 'bg-emerald-500/10 text-emerald-600'
              }`}
            >
              <Wallet className="w-4 h-4" />
            </div>
            <div className="min-w-0">
              <div className={`text-[11px] font-bold ${isDark ? 'text-white' : 'text-neutral-900'}`}>
                {t.paidWithUsdtTon}
              </div>
              <div className={`text-[10px] ${isDark ? 'text-neutral-400' : 'text-neutral-500'}`}>
                {t.fragmentDelivery}
              </div>
            </div>
          </div>
          <div className="text-right shrink-0">
            <div className={`text-[11px] font-bold font-mono ${isDark ? 'text-emerald-300' : 'text-emerald-600'}`}>
              ≈ {usdtForStars.toFixed(3)} USDT
            </div>
            {showRate && (
              <div className="text-[9px] text-neutral-400 font-mono">
                1 USDT ≈ {usdtRate.toLocaleString()} UZS
              </div>
            )}
          </div>
        </div>
      )}

      {/* Apple Segmented Control Bar */}
      <div className="flex items-center gap-1 p-1 rounded-full liquid-glass">
        <button
          onClick={() => {
            setSubTab('stars');
            setError(null);
          }}
          className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-full text-xs font-semibold transition-all cursor-pointer apple-spring ${
            subTab === 'stars'
              ? isDark
                ? 'bg-white text-black shadow-md'
                : 'bg-black text-white shadow-md'
              : isDark ? 'text-neutral-400 hover:text-white' : 'text-neutral-600 hover:text-black'
          }`}
        >
          <Star className="w-3.5 h-3.5" />
          <span>{t.stars}</span>
        </button>

        <button
          onClick={() => {
            setSubTab('premium');
            setError(null);
          }}
          className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-full text-xs font-semibold transition-all cursor-pointer apple-spring ${
            subTab === 'premium'
              ? isDark
                ? 'bg-white text-black shadow-md'
                : 'bg-black text-white shadow-md'
              : isDark ? 'text-neutral-400 hover:text-white' : 'text-neutral-600 hover:text-black'
          }`}
        >
          <Sparkles className="w-3.5 h-3.5" />
          <span>{t.premium}</span>
        </button>

        <button
          onClick={() => {
            setSubTab('gifts');
            setError(null);
          }}
          className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-full text-xs font-semibold transition-all cursor-pointer apple-spring ${
            subTab === 'gifts'
              ? isDark
                ? 'bg-white text-black shadow-md'
                : 'bg-black text-white shadow-md'
              : isDark ? 'text-neutral-400 hover:text-white' : 'text-neutral-600 hover:text-black'
          }`}
        >
          <Gift className="w-3.5 h-3.5" />
          <span>{t.gifts}</span>
        </button>
      </div>

      {/* Recipient box / Resolved Profile Card */}
      <div className="rounded-[26px] liquid-glass-card p-4 space-y-2">
        <div className="flex items-center justify-between">
          <label className={`text-xs font-semibold ${isDark ? 'text-neutral-300' : 'text-neutral-700'}`}>{t.recipient}</label>
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => {
                setRecipient(user?.username || '');
                setIsEditingRecipient(false);
              }}
              className="flex items-center gap-1 px-3 py-1 rounded-full liquid-glass-pill text-[11px] font-semibold apple-spring cursor-pointer"
            >
              <UserCheck className="w-3 h-3" />
              <span>{t.myself}</span>
            </button>
          </div>
        </div>

        {resolvedProfile && !isEditingRecipient ? (
          <div
            onClick={() => setIsEditingRecipient(true)}
            className="flex items-center justify-between p-3 rounded-[20px] bg-white/[0.05] dark:bg-white/[0.08] border border-white/15 hover:border-white/30 apple-spring cursor-pointer shadow-sm group"
            title="O'zgartirish uchun bosing"
          >
            <div className="flex items-center gap-3">
              <div className="w-11 h-11 rounded-full p-[1.5px] bg-gradient-to-tr from-amber-400 to-yellow-500 overflow-hidden shadow-sm shrink-0">
                {resolvedProfile.photo_url ? (
                  <img
                    src={resolvedProfile.photo_url}
                    alt={resolvedProfile.display_name}
                    className="w-full h-full rounded-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full rounded-full bg-neutral-900 text-amber-300 flex items-center justify-center font-bold text-sm">
                    {resolvedProfile.display_name.charAt(0).toUpperCase()}
                  </div>
                )}
              </div>
              <div className="min-w-0">
                <div className={`text-xs font-bold truncate ${isDark ? 'text-white' : 'text-neutral-900'}`}>
                  {resolvedProfile.display_name}
                </div>
                <div className="text-[11px] text-cyan-400 font-mono font-medium">
                  @{resolvedProfile.username}
                </div>
              </div>
            </div>

            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setIsEditingRecipient(true);
              }}
              className="px-2.5 py-1.5 rounded-full liquid-glass-pill text-[11px] font-semibold flex items-center gap-1 text-neutral-400 group-hover:text-white apple-spring"
            >
              <Edit3 className="w-3 h-3" />
              <span>Tahrirlash</span>
            </button>
          </div>
        ) : (
          <div className="space-y-2">
            <div className="relative">
              <input
                type="text"
                value={recipient}
                autoFocus={isEditingRecipient}
                onChange={(e) => {
                  setRecipient(e.target.value);
                  setError(null);
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && recipient) {
                    setIsEditingRecipient(false);
                  }
                }}
                placeholder="@username"
                className={`w-full pl-4 pr-12 py-3 rounded-[16px] text-sm font-medium focus:outline-none apple-spring liquid-glass-input ${
                  isDark ? 'text-white placeholder:text-neutral-600' : 'text-neutral-900 placeholder:text-neutral-400'
                }`}
              />
              {recipient && (
                <button
                  type="button"
                  onClick={() => setIsEditingRecipient(false)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1.5 rounded-full liquid-glass-pill text-emerald-400 apple-spring cursor-pointer"
                  title="Tayyor"
                >
                  <Check className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
            <p className="text-[10px] text-neutral-400">{t.recipientUsername}</p>
          </div>
        )}
      </div>

      {/* Stars Amount Selection */}
      {subTab === 'stars' && (
        <div className="rounded-[26px] liquid-glass-card p-4 space-y-3">
          <div className="flex items-center justify-between text-xs">
            <span className={`font-semibold ${isDark ? 'text-neutral-300' : 'text-neutral-700'}`}>{t.starsAmount}</span>
            <span className="text-[10px] text-neutral-400 font-mono">50 - 1 000 000</span>
          </div>

          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-neutral-400">
              <Star className="w-4 h-4" />
            </div>
            <input
              type="number"
              value={amount}
              onChange={(e) => {
                setAmount(Math.max(1, parseInt(e.target.value || '0', 10)));
                setError(null);
              }}
              className={`w-full pl-11 pr-4 py-3 rounded-[16px] font-mono text-base font-bold focus:outline-none apple-spring liquid-glass-input ${
                isDark ? 'text-white' : 'text-neutral-900'
              }`}
            />
          </div>

          <div className="grid grid-cols-5 gap-1.5">
            {starsPresets.map((val) => (
              <button
                key={val}
                onClick={() => {
                  setAmount(val);
                  setError(null);
                }}
                className={`py-2 rounded-[12px] text-xs font-semibold font-mono apple-spring cursor-pointer border ${
                  amount === val
                    ? isDark
                      ? 'bg-white text-black border-white shadow-sm'
                      : 'bg-black text-white border-black shadow-sm'
                    : 'liquid-glass-pill opacity-80 hover:opacity-100'
                }`}
              >
                {val}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Premium Selection */}
      {subTab === 'premium' && (
        <div className="rounded-[26px] liquid-glass-card p-4 space-y-3">
          <div className={`flex items-center gap-1 p-1 rounded-full ${isDark ? 'bg-black/30' : 'bg-black/5'}`}>
            <button
              onClick={() => setPremMode('nologin')}
              className={`flex-1 py-1.5 text-xs font-semibold rounded-full apple-spring ${
                premMode === 'nologin'
                  ? isDark ? 'bg-white text-black' : 'bg-black text-white'
                  : 'text-neutral-400'
              }`}
            >
              Akkauntga kirmasdan
            </button>
            <button
              onClick={() => setPremMode('login')}
              className={`flex-1 py-1.5 text-xs font-semibold rounded-full apple-spring ${
                premMode === 'login'
                  ? isDark ? 'bg-white text-black' : 'bg-black text-white'
                  : 'text-neutral-400'
              }`}
            >
              Akkauntga kirib
            </button>
          </div>

          <div className="grid grid-cols-3 gap-2">
            {premPlans[premMode].map((p) => (
              <button
                key={p.months}
                onClick={() => setPremMonths(p.months)}
                className={`p-3 rounded-[18px] border text-center apple-spring cursor-pointer ${
                  premMonths === p.months
                    ? isDark ? 'bg-white text-black border-white shadow-sm' : 'bg-black text-white border-black shadow-sm'
                    : 'liquid-glass-pill opacity-80 hover:opacity-100'
                }`}
              >
                <div className="text-xs font-bold">{p.label}</div>
                <div className="text-[10px] opacity-80 mt-1 font-mono">
                  {p.price.toLocaleString()} UZS
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Gifts Selection */}
      {subTab === 'gifts' && (
        <div className="rounded-[26px] liquid-glass-card p-4 space-y-3">
          <div className="grid grid-cols-2 gap-2 max-h-52 overflow-y-auto pr-1">
            {giftsList.map((g) => (
              <button
                key={g.key}
                onClick={() => setSelectedGift(g.key)}
                className={`p-3 rounded-[18px] border text-left flex items-center justify-between apple-spring cursor-pointer ${
                  selectedGift === g.key
                    ? isDark ? 'bg-white text-black border-white shadow-sm' : 'bg-black text-white border-black shadow-sm'
                    : 'liquid-glass-pill opacity-80 hover:opacity-100'
                }`}
              >
                <div>
                  <div className="text-xs font-bold">{g.name}</div>
                  <div className="text-[10px] opacity-70 font-mono mt-0.5">
                    {g.stars} ⭐
                  </div>
                </div>
                <div className="text-xs font-mono font-bold">
                  {g.price.toLocaleString()} UZS
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Price & Balance Need Box */}
      <div className="rounded-[26px] liquid-glass-card p-4 space-y-2">
        <div className="flex items-center justify-between">
          <span className={`text-xs font-semibold ${isDark ? 'text-neutral-400' : 'text-neutral-600'}`}>{t.price}</span>
          <span className={`text-lg font-bold font-mono ${isDark ? 'text-white' : 'text-neutral-900'}`}>
            {currentPrice.toLocaleString()} <span className="text-xs font-normal opacity-70">UZS</span>
          </span>
        </div>

        {!isEnough && (
          <div className="pt-2 border-t border-white/10 flex items-center justify-between">
            <span className="text-xs font-semibold text-rose-400">
              {t.needMore}: <b>{needMore.toLocaleString()} UZS</b>
            </span>
            <button
              onClick={onGoToTopup}
              className={`px-3 py-1 rounded-full text-xs font-semibold apple-spring cursor-pointer ${
                isDark ? 'bg-white text-black hover:bg-neutral-200' : 'bg-black text-white hover:bg-neutral-800'
              }`}
            >
              {t.topup}
            </button>
          </div>
        )}
      </div>

      {/* Error display */}
      {error && (
        <div className="p-3 rounded-[16px] bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Main Buy Button */}
      <button
        onClick={handleBuy}
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
          <Star className="w-4 h-4 fill-current" />
        )}
        <span>{subTab === 'stars' ? t.buyStars : subTab === 'premium' ? (t.premium + ' sotib olish') : ('Gift yuborish')}</span>
      </button>
    </div>
  );
};
