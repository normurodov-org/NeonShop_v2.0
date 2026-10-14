import React, { useState, useEffect, useRef } from 'react';
import { User, StoreSettings, Order, UsdtRate } from '../../types';
import { Lang, translations } from '../../i18n';
import { Star, Sparkles, Gift, UserCheck, AlertCircle, RefreshCw, Edit3, Check, Wallet, Layers, ChevronRight } from 'lucide-react';
import AEmoji from '../AEmoji';
import NftRentView from './NftRentView';
import { tgHeaders } from '../../lib/tgAuth';

interface BuyViewProps {
  user: User | null;
  settings: StoreSettings | null;
  lang: Lang;
  isDark: boolean;
  initialTab?: 'stars' | 'premium' | 'gifts' | 'nft';
  onOrderSuccess: (order: Order, newBalance: number, msg: string) => void;
  onGoToTopup: () => void;
  /** NFT ijaraga olish yuborilganda — toast ko'rsatish uchun */
  /** 📖 `order` ham uzatiladi — ilova uni tarixga qo'shishi
   *  kerak (aks holda poller ishlamaydi). */
  onRented?: (msg: string, newBalance?: number, order?: any) => void;
}

export const BuyView: React.FC<BuyViewProps> = ({
  user,
  settings,
  lang,
  isDark,
  initialTab = 'stars',
  onOrderSuccess,
  onGoToTopup,
  onRented,
}) => {
  const t = translations[lang];
  const [subTab, setSubTab] = useState<'stars' | 'premium' | 'gifts' | 'nft'>(initialTab);

  // 🔴 Telegram username'i bo'lmagan akkauntlar uchun "O'zimga" ishlashmaydi.
  // `user_XXXX` kabi sun'iy qiymatni HECH QACHON ishlatmaymiz — u
  // server tomonida qabul qilinib, UZS yechilib, Fragment ishlamaydi.
  const myUsername = (user?.username || '').trim().replace(/^@/, '');

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
  // Profil rasmi 404 bo'ldimi? (Telegram'da rasm yo'q bo'lishi mumkin)
  const [photoFailed, setPhotoFailed] = useState<boolean>(false);
  // Sovg'a: anonim yuborish (true) yoki do'kon profili ko'rinadi (false)
  const [hideMyName, setHideMyName] = useState<boolean>(true);

  const [amount, setAmount] = useState<number>(100);
  // Kirish maydoni uchun alohida holat: foydalanuvchi raqamni to'liq
  // o'chira olishi kerak (eski kod Math.max(1, NaN) sababli "1" qolib ketardi).
  const [amountInput, setAmountInput] = useState<string>('100');
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
  // Chegara: interfeysda ham "50 - 1 000 000" deb yozilgan
  const MIN_STARS = 50;
  const MAX_STARS = 1_000_000;

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

  // 🔴 so'rov ketma-ketligi uchun ref (yuqoridagi guard uchun)
  const resolveSeq = useRef(0);

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

    // 🔴 SO'ROV KETMA-KETLIGI (sequence guard).
    // Muammo: 450ms debounce'dan keyin so'rov ketadi. Mijoz tez-tez
    // username o'zgartirsa, birinchi (sekin) javob ikkinchisidan KEYIN
    // kelishi mumkin — va eski profil ustiga yopiladi: rasmda A,
    // haqiqiy xaridda B. Mijoz NOTO'G'RI odamga Stars yuboradi.
    // Yechim: har so'rov o'z raqamini oladi; javob kelganda o'z
    // raqami bilan solishtiriladi — eskisi tashlab yuboriladi.
    const seq = ++resolveSeq.current;

    const timer = setTimeout(async () => {
      setResolving(true);
      try {
        const res = await fetch(`/api/resolve-user?username=${encodeURIComponent(clean)}`);
        const data = await res.json();
        // 🔴 Boshqa so'rov javobi keldi — bu ESKISI, unutamiz
        if (seq !== resolveSeq.current) return;
        if (data.ok && data.user) {
          // 🔴 javob shakli tekshiriladi — avval `any` to'g'ridan
          // to'g'ri `display_name` o'qilardi va yo'q bo'lsa TypeError
          // chiqib, butun "Xarid" tabini xato ekranga aylantirardi.
          setResolvedProfile({
            username: String(data.user.username || clean),
            display_name: String(data.user.display_name || data.user.username || clean),
            photo_url: data.user.photo_url ? String(data.user.photo_url) : undefined,
          });
          setPhotoFailed(false);
        } else {
          // 🔴 MUVAFFAQIYATSIZ bo'lsa ham eski profilni TOZALAMIZ
          // — aks holda A ning rasmi B ning nomi bilan ko'rinib turadi
          // va mijoz qayerda yuborayotganini ANIQLAY OLMAYDI.
          setResolvedProfile(null);
          setPhotoFailed(false);
        }
      } catch (e) {
        console.error('Resolve user error:', e);
        if (seq === resolveSeq.current) setResolvedProfile(null);
      } finally {
        if (seq === resolveSeq.current) setResolving(false);
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

  // emoji alohida saqlanadi — animatsiyalangan ko'rinish uchun
  const giftsList = [
    { key: 'bear', name: 'Ayiqcha', emoji: '🧸', stars: 15, price: 3000 },
    { key: 'heart', name: 'Yurakcha', emoji: '💝', stars: 15, price: 3000 },
    { key: 'rose', name: 'Atirgul', emoji: '🌹', stars: 25, price: 6000 },
    { key: 'cake', name: 'Tort', emoji: '🎂', stars: 50, price: 10000 },
    { key: 'rocket', name: 'Raketa', emoji: '🚀', stars: 50, price: 10000 },
    { key: 'cup', name: 'Kubok', emoji: '🏆', stars: 100, price: 20000 },
    { key: 'diamond', name: 'Olmos', emoji: '💎', stars: 100, price: 20000 },
  ];

  // 🔴 PREMIUM REJIM/MUDDAT MUVOFIQLIGI.
  // Muammo: `login` rejimida faqat 1 va 12 oy bor. Mijoz avval "3 oy"
  // ni tanlab, keyin "Akkauntga kirib" ni bossa, `premMonths` ESKI
  // qiymatida qoladi — `find()` topmaydi va `|| 155000` YASHIR
  // zaxira narxni ko'rsatadi. Natijada mijoz 155 000 ko'rib "Sotib
  // olish" bosadi, server esa `400 "Noto'g'ri tarif tanlandi."`
  // qaytaradi: hech narsa bo'lmaydi, mijoz chalkashadi.
  // Yechim: rejim almashganda muddat ham shu rejimga moslanadi.
  const switchPremMode = (mode: 'nologin' | 'login') => {
    setPremMode(mode);
    if (!premPlans[mode].some((x) => x.months === premMonths)) {
      setPremMonths(premPlans[mode][0].months);
    }
  };

  // 📖 Tanlanmagan tarifni YASHIRMAYDIGAN qimma — keyin
  // `buy_disabled` orqali tugma o'chiriladi va mijoz xatoni oldini oladi.
  const premPlan = premPlans[premMode].find((x) => x.months === premMonths) || null;

  // Calculate current price
  let currentPrice = 0;
  if (subTab === 'stars') {
    currentPrice = amount * starPrice;
  } else if (subTab === 'premium') {
    currentPrice = premPlan ? premPlan.price : 0;
  } else if (subTab === 'gifts') {
    const g = giftsList.find((x) => x.key === selectedGift);
    currentPrice = g?.price || 3000;
  }

  const userBal = user?.balance || 0;
  const isEnough = userBal >= currentPrice;
  const needMore = Math.max(0, currentPrice - userBal);

  const handleBuy = async () => {
    // 🔴 🔄 IKKI MARTA TO'LOVNI TO'XTATISH.
    // `disabled={loading}` yetarli EMAS: React holatni qayta render
    // qilishdan OLDIN ikkinchi bosilish yuborilishi mumkin.
    if (loading) return;
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
        // 🐄 Tanlanmagan tariffni serverga yubormaymiz — 400 olib
        // mijozni chalkashga qoldirmaslik uchun (hozir CTA ham o'chiriladi)
        if (!premPlan) {
          setError('Premium tarifni tanlang.');
          return;
        }
        body = { ...body, kind: 'premium', mode: premMode, months: premMonths };
      } else if (subTab === 'gifts') {
        body = { ...body, kind: 'gift', gift: selectedGift, hide_my_name: hideMyName };
      }

      const res = await fetch('/api/order', {
        method: 'POST',
        headers: tgHeaders(),
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
    <div className="space-y-4 max-w-md md:max-w-none lg:px-6 xl:px-10 mx-auto pb-28 md:pb-10 apple-view-animate">
      {/* Title & Exchange rate header */}
      <div className="flex items-center justify-between">
        <h2 className={`text-xl font-bold tracking-tight ${isDark ? 'text-white' : 'text-neutral-900'}`}>{t.buy}</h2>
        <span className="text-[11px] font-bold px-3 py-1 rounded-full liquid-glass-pill opacity-90">
          1 ★ = {starPrice} UZS
        </span>
      </div>


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

        <button
          onClick={() => {
            setSubTab('nft');
            setError(null);
          }}
          className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-full text-xs font-semibold transition-all cursor-pointer apple-spring ${
            subTab === 'nft'
              ? isDark
                ? 'bg-white text-black shadow-md'
                : 'bg-black text-white shadow-md'
              : isDark ? 'text-neutral-400 hover:text-white' : 'text-neutral-600 hover:text-black'
          }`}
        >
          <Layers className="w-3.5 h-3.5" />
          <span>NFT</span>
        </button>
      </div>

      {/* Recipient box / Resolved Profile Card */}
      <div className="rounded-[26px] liquid-glass-card p-4 space-y-2">
        <div className="flex items-center justify-between">
          <label className={`text-xs font-semibold ${isDark ? 'text-neutral-300' : 'text-neutral-700'}`}>{t.recipient}</label>
          <div className="flex items-center gap-1.5">
            {/* 🔴 ILGAR BU TUGMA HECH NARSA QILMASDI.
                Sabab: `user.username` Telegram akkauntlarida ko'p
                hollarda `null` bo'ladi (username yo'q). U holda
                `setRecipient('')` — holat o'zgarmasdi, `resolvedProfile`
                null bo'lib qolardi va ternary yana XUDDI SHU inputni
                chizardi. Ko'rinishda "hech narsa bo'lmadi".
                Endi:
                  • username yo'q bo'lsa tugma O'CHIRILADI + sabab
                  • username bo'lsa: `resolvedProfile` va `photoFailed`
                    ham tozalanadi (avvalgi xato chizilgan bo'lsa,
                    "o'zgarmadi" degan taassurot qolardi)} */}
            <button
              onClick={() => {
                if (!myUsername) return;
                setRecipient(myUsername);
                // 🔴 Eski xato holati tozalanadi — aks holda eski
                // avatar ko'rinib turadi va tugma "ishlamadi" degan
                // taassurot qoldiradi.
                setResolvedProfile(null);
                setPhotoFailed(false);
                setIsEditingRecipient(true);
              }}
              disabled={!myUsername}
              title={
                myUsername
                  ? t.myself
                  : 'Telegram akkauntingizda username yo\'q. Botga /start yozing.'
              }
              className={`flex items-center gap-1 px-3 py-1 rounded-full text-[11px] font-semibold apple-spring ${
                myUsername ? 'liquid-glass-pill cursor-pointer' : 'opacity-40 cursor-not-allowed'
              }`}
            >
              <UserCheck className="w-3 h-3" />
              <span>{t.myself}</span>
            </button>
          </div>
        </div>

        {resolvedProfile && !isEditingRecipient ? (
          <div
            onClick={() => setIsEditingRecipient(true)}
            className="flex items-center justify-between p-3 rounded-[20px] bg-white/[0.05] border border-white/15 hover:border-white/30 apple-spring cursor-pointer shadow-sm group"
            title="O'zgartirish uchun bosing"
          >
            <div className="flex items-center gap-3">
              <div className="w-11 h-11 rounded-full p-[1.5px] bg-gradient-to-tr from-amber-400 to-yellow-500 overflow-hidden shadow-sm shrink-0">
                {resolvedProfile.photo_url && !photoFailed ? (
                  <img
                    src={resolvedProfile.photo_url}
                    alt={resolvedProfile.display_name}
                    className="w-full h-full rounded-full object-cover"
                    // Rasm 404 bo'lsa (profil rasmi yo'q foydalanuvchilar)
                    // bo'sh sariq doira emas — initial harf chiqadi.
                    onError={() => setPhotoFailed(true)}
                  />
                ) : (
                  <div className="w-full h-full rounded-full bg-neutral-900 text-amber-300 flex items-center justify-center font-bold text-sm">
                    {String(resolvedProfile.display_name || resolvedProfile.username || '?')
                      .charAt(0)
                      .toUpperCase()}
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
              className={`px-2.5 py-1.5 rounded-full liquid-glass-pill text-[11px] font-semibold flex items-center gap-1 ${isDark ? 'text-neutral-400' : 'text-neutral-600'} group-hover:text-white apple-spring`}
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
            <p className={`text-[10px] ${isDark ? 'text-neutral-400' : 'text-neutral-600'}`}>{t.recipientUsername}</p>
          </div>
        )}
      </div>

      {/* Stars Amount Selection */}
      {/* 📐 FORM bo'limlari (Stars / Premium / Gift) o'qish uchun TOR
          qoladi — butun ekran keng bo'lishi mumkin emas. Faqat NFT
          (katalog — rasm va filtrlar) to'liq kenglikda yoyiladi.
          Mijozning so'rovi: «desktopda qizil bilan belgilangan bo'limni
          yanada kengaytir». */}
      <div className={`md:max-w-3xl mx-auto w-full ${subTab === 'nft' ? 'hidden' : ''}`}>
      {subTab === 'stars' && (
        <div className="rounded-[26px] liquid-glass-card p-4 space-y-3">
          <div className="flex items-center justify-between text-xs">
            <span className={`font-semibold ${isDark ? 'text-neutral-300' : 'text-neutral-700'}`}>{t.starsAmount}</span>
            <span className={`text-[10px] ${isDark ? 'text-neutral-400' : 'text-neutral-600'} font-mono`}>
              {MIN_STARS.toLocaleString()} - {MAX_STARS.toLocaleString()}
            </span>
          </div>

          <div className="relative">
            <div className={`absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none ${isDark ? 'text-neutral-400' : 'text-neutral-600'}`}>
              <Star className="w-4 h-4" />
            </div>
            <input
              type="number"
              inputMode="numeric"
              value={amountInput}
              onChange={(e) => {
                    const raw = e.target.value;
                    setAmountInput(raw);
                    // Faqat raqam kiritilgan bo'lsa darhol narxni hisoblaymiz;
                    // bo'sh yoki noto'g'ri qiymatda eski narx saqlanadi.
                    const n = parseInt(raw, 10);
                    if (Number.isFinite(n) && n > 0) setAmount(n);
                    setError(null);
                  }}
                  onBlur={() => {
                    // maydon bo'sh qoldirilgan bo'lsa — minimal qiymatga qaytaramiz
                    const n = parseInt(amountInput, 10);
                    const safe = Number.isFinite(n)
                      ? Math.min(MAX_STARS, Math.max(MIN_STARS, n))
                      : MIN_STARS;
                    setAmount(safe);
                    setAmountInput(String(safe));
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
                  setAmountInput(String(val));
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
              onClick={() => switchPremMode('nologin')}
              className={`flex-1 py-1.5 text-xs font-semibold rounded-full apple-spring ${
                premMode === 'nologin'
                  ? isDark ? 'bg-white text-black' : 'bg-black text-white'
                  : isDark ? 'text-neutral-400' : 'text-neutral-600'
              }`}
            >
              Akkauntga kirmasdan
            </button>
            <button
              onClick={() => switchPremMode('login')}
              className={`flex-1 py-1.5 text-xs font-semibold rounded-full apple-spring ${
                premMode === 'login'
                  ? isDark ? 'bg-white text-black' : 'bg-black text-white'
                  : isDark ? 'text-neutral-400' : 'text-neutral-600'
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
                  <div className="text-xs font-bold flex items-center gap-1.5">
                    <AEmoji char={g.emoji} size={16} anim="float" label={g.name} />
                    {g.name}
                  </div>
                  <div className="text-[10px] opacity-70 font-mono mt-0.5 flex items-center gap-1">
                    {g.stars}
                    <AEmoji char="⭐" size={12} anim="shine" label="Stars" />
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

      {/* Sovg'a uchun yuborish turi: anonim yoki profil ko'rinadi */}
      {subTab === 'gifts' && (
        <div className="rounded-[22px] liquid-glass-card p-3.5 space-y-2.5">
          <div className={`text-[11px] font-semibold ${
            isDark ? 'text-neutral-300' : 'text-neutral-600'
          }`}>
            🕶️ Sovg'ani qanday yuboramiz?
          </div>
          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={() => setHideMyName(true)}
              className={`py-2.5 rounded-[16px] text-[11px] font-semibold apple-spring cursor-pointer border ${
                hideMyName
                  ? 'bg-white text-black border-white'
                  : `liquid-glass-pill border-white/20 ${
                      isDark ? 'text-neutral-300' : 'text-neutral-600'
                    }`
              }`}
            >
              🕶️ Anonim
              <span className="block text-[9px] font-normal opacity-70 mt-0.5">
                Profilingiz ko'rinmaydi
              </span>
            </button>
            <button
              onClick={() => setHideMyName(false)}
              className={`py-2.5 rounded-[16px] text-[11px] font-semibold apple-spring cursor-pointer border ${
                !hideMyName
                  ? 'bg-white text-black border-white'
                  : `liquid-glass-pill border-white/20 ${
                      isDark ? 'text-neutral-300' : 'text-neutral-600'
                    }`
              }`}
            >
              👤 Do'kon profili
              <span className="block text-[9px] font-normal opacity-70 mt-0.5">
                Do'kon akkaunti ko'rinadi
              </span>
            </button>
          </div>

        </div>
      )}


      {/* Error display */}
      {error && (
        <div className="p-3 rounded-[16px] bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* 🔴 NFT TABDA BU TUGMA KO'RSATILMAYDI.
          Sabab: `handleBuy` `kind` yubormaydi (faqat `{ username }`),
          shuning uchun server `400 "Noma'lum xizmat turi."` qaytarardi.
          NFT ijaraga olish — alohida oqim (`NftRentView` ichida
          `POST /api/nfts/rent`), o'z CTA'si bilan. */}
      {subTab !== 'nft' && (
      <button
        onClick={handleBuy}
        /* 🐄 Premium rejimda tarif tanlanmagan bo'lsa tugma o'chiriladi:
           server `400 "Noto'g'ri tarif tanlandi."` qaytarib, mijozni
           chalkash qoldirmasligimiz kerak. */
        disabled={loading || (subTab === 'premium' && !premPlan)}
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
        <span>
          {subTab === 'stars'
            ? t.buyStars
            : subTab === 'premium'
              ? t.premium + ' sotib olish'
              : 'Gift yuborish'}
        </span>
      </button>
      )}
      </div>

      {subTab === 'nft' && (
        <NftRentView
          isDark={isDark}
          userId={user?.id}
          balance={user?.balance || 0}
          onGoToTopup={onGoToTopup}
          onRented={onRented}
        />
      )}
    </div>
  );
};
