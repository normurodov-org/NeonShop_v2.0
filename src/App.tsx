import React, { useState, useEffect } from 'react';
import { User, StoreSettings, Topup, Order, Contest } from './types';
import { Lang } from './i18n';
import { Header } from './components/Header';
import { BottomNav, TabType } from './components/BottomNav';
import { HomeView } from './components/views/HomeView';
import { TopupView } from './components/views/TopupView';
import { BuyView } from './components/views/BuyView';
import { RankingView } from './components/views/RankingView';
import { ProfileView } from './components/views/ProfileView';
import { AdminPanel } from './components/AdminPanel';
import { LiquidPointer } from './components/LiquidPointer';
import { CheckCircle2, ArrowLeft, PauseCircle } from 'lucide-react';

export default function App() {
  const [currentTab, setCurrentTab] = useState<TabType>('home');
  const [initialBuyCategory, setInitialBuyCategory] = useState<'stars' | 'premium' | 'gifts'>('stars');
  const [lang, setLang] = useState<Lang>(() => {
    return (localStorage.getItem('neon_lang') as Lang) || 'uz';
  });

  // Day / Night mode: 'dark' by default, persisted in localStorage
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    return (localStorage.getItem('apple_theme') as 'dark' | 'light') || 'dark';
  });
  const isDark = theme === 'dark';

  const [user, setUser] = useState<User | null>(null);
  const [settings, setSettings] = useState<StoreSettings | null>(null);
  const [contest, setContest] = useState<Contest | null>(null);
  const [history, setHistory] = useState<Order[]>([]);
  const [activeTopup, setActiveTopup] = useState<Topup | null>(null);
  const [toastMsg, setToastMsg] = useState<string | null>(null);

  // Admin condition: ONLY user ID 8307046273 (or settings.admin_id)
  const isAdmin = user?.id === 8307046273 || (Boolean(settings?.admin_id) && user?.id === settings?.admin_id);

  const handleLangChange = (newLang: Lang) => {
    setLang(newLang);
    localStorage.setItem('neon_lang', newLang);
  };

  const handleToggleTheme = () => {
    const next = theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    localStorage.setItem('apple_theme', next);
    triggerHaptic('light');
  };

  const fetchUserData = async (
    tgId?: number,
    tgUsername?: string,
    photoUrl?: string,
    firstName?: string
  ) => {
    try {
      let url = '/api/me';
      const params = new URLSearchParams();
      if (tgId) params.append('uid', tgId.toString());
      if (tgUsername) params.append('un', tgUsername);
      if (photoUrl) params.append('photo_url', photoUrl);
      if (firstName) params.append('first_name', firstName);
      if (params.toString()) {
        url += `?${params.toString()}`;
      }

      const res = await fetch(url, {
        headers: {
          'x-telegram-user-id': tgId ? tgId.toString() : '',
          'x-telegram-username': tgUsername || '',
          'x-telegram-photo-url': photoUrl || '',
          'x-telegram-first-name': firstName || '',
        },
      });
      const data = await res.json();
      if (data.ok) {
        setUser(data.user);
        setHistory(data.history || []);
        setContest(data.contest || null);
        setSettings(data.settings || null);
        if (data.user?.pending_topup) {
          setActiveTopup(data.user.pending_topup);
        }
      }
    } catch (err) {
      console.error('Failed to fetch user data:', err);
    }
  };

  useEffect(() => {
    const tg = (window as any).Telegram?.WebApp;
    if (tg) {
      try {
        tg.ready();
        tg.expand();
      } catch (e) {
        console.error('Telegram WebApp ready error:', e);
      }
    }

    let parsedId: number | undefined;
    let parsedUn: string | undefined;
    let parsedFirst: string | undefined;
    let parsedPhoto: string | undefined;

    // 1. Direct WebApp object
    if (tg?.initDataUnsafe?.user?.id) {
      parsedId = Number(tg.initDataUnsafe.user.id);
      parsedUn = tg.initDataUnsafe.user.username;
      parsedFirst = tg.initDataUnsafe.user.first_name;
      parsedPhoto = tg.initDataUnsafe.user.photo_url;
    }

    // 2. tg.initData query string
    if (!parsedId && tg?.initData) {
      try {
        const q = new URLSearchParams(tg.initData);
        const userStr = q.get('user');
        if (userStr) {
          const u = JSON.parse(userStr);
          if (u.id) {
            parsedId = Number(u.id);
            parsedUn = u.username || parsedUn;
            parsedFirst = u.first_name || parsedFirst;
            parsedPhoto = u.photo_url || parsedPhoto;
          }
        }
      } catch (e) {
        console.error('Error parsing tg.initData:', e);
      }
    }

    // 3. URL Hash fragment (#tgWebAppData=...)
    if (!parsedId && window.location.hash) {
      try {
        const hashStr = window.location.hash.replace(/^#/, '');
        const hashParams = new URLSearchParams(hashStr);
        const tgWebAppData = hashParams.get('tgWebAppData');
        if (tgWebAppData) {
          const dataParams = new URLSearchParams(tgWebAppData);
          const userStr = dataParams.get('user');
          if (userStr) {
            const u = JSON.parse(userStr);
            if (u.id) {
              parsedId = Number(u.id);
              parsedUn = u.username || parsedUn;
              parsedFirst = u.first_name || parsedFirst;
              parsedPhoto = u.photo_url || parsedPhoto;
            }
          }
        }
      } catch (e) {
        console.error('Error parsing window.location.hash:', e);
      }
    }

    // 4. URL query parameters (?uid=... or ?tg_user_id=...)
    const urlParams = new URLSearchParams(window.location.search);
    const queryUid = urlParams.get('uid') || urlParams.get('tg_user_id');
    const queryUn = urlParams.get('un') || urlParams.get('tg_username');
    const queryFirst = urlParams.get('first_name') || urlParams.get('fn');
    const queryPhoto = urlParams.get('photo_url');

    if (!parsedId && queryUid && !isNaN(Number(queryUid))) {
      parsedId = Number(queryUid);
    }
    if (queryUn) parsedUn = queryUn;
    if (queryFirst) parsedFirst = queryFirst;
    if (queryPhoto) parsedPhoto = queryPhoto;

    fetchUserData(parsedId, parsedUn, parsedPhoto, parsedFirst);
  }, []);

  const triggerHaptic = (type: 'light' | 'medium' | 'heavy' | 'success' = 'medium') => {
    try {
      const tg = (window as any).Telegram?.WebApp;
      if (tg?.HapticFeedback) {
        if (type === 'success') {
          tg.HapticFeedback.notificationOccurred('success');
        } else {
          tg.HapticFeedback.impactOccurred(type);
        }
      }
    } catch (e) {
      // ignore
    }
  };

  const showToast = (msg: string) => {
    triggerHaptic('success');
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 4000);
  };

  const handleOrderSuccess = (order: Order, newBalance: number, msg: string) => {
    if (user) {
      setUser({
        ...user,
        balance: newBalance,
        total_spent: user.total_spent + order.price,
      });
    }
    setHistory((prev) => [order, ...prev]);
    showToast(msg);
  };

  /**
   * Buyurtma holatini kuzatish
   * -----------------------
   * Stars yuborilayotgan paytda webapp "yuborilmoqda" deb turmasligi uchun
   * holatni avtomatik yangilaymiz. Bot yetkazganda "✅ Stars yuborildi!"
   * xabari chiqadi va balantari ham yangilanadi.
   */
  const processingCount = history.filter(
    (o) => o.status === 'processing' || o.status === 'queued' || o.status === 'pending'
  ).length;

  useEffect(() => {
    if (processingCount === 0) return;
    let alive = true;
    let ticks = 0;

    const poll = async () => {
      try {
        const res = await fetch('/api/me', {
          headers: { 'x-telegram-user-id': user?.id?.toString() || '' },
        });
        const data = await res.json();
        if (!alive || !data.ok) return;

        const fresh: Order[] = data.history || [];
        if (!fresh.length) return;

        // Eski holat bilan solishtirib, tugaganlarini topamiz
        setHistory((prev) => {
          const prevMap = new Map(prev.map((o) => [o.id, o]));
          let changed = false;
          const merged = fresh.map((o) => {
            const before = prevMap.get(o.id);
            const wasPending =
              before && (before.status === 'processing' || before.status === 'queued' || before.status === 'pending');
            const nowDone = o.status === 'done' || o.status === 'completed' || o.status === 'sent_unconfirmed';
            if (wasPending && nowDone) changed = true;
            return o;
          });
          return changed ? merged : prev;
        });

        if (data.user?.balance !== undefined && user && data.user.balance !== user.balance) {
          setUser(data.user);
        }
      } catch (e) {
        /* tarmoq uzilishi — keyingi urinishda */
      }
    };

    poll();
    const timer = setInterval(() => {
      ticks += 1;
      if (ticks > 75) return;      // ~10 daqiqadan keyin to'xtaydi
      poll();
    }, 8000);

    return () => {
      alive = false;
      clearInterval(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [processingCount, user?.id]);

  const handleTopupSuccess = (newBalance: number, msg: string) => {
    if (user) {
      setUser({ ...user, balance: newBalance });
    }
    setActiveTopup(null);
    showToast(msg);
  };

  // Admin botni to'xtatgan bo'lsa — WebApp ham javov bermaydi (Liquid Glass ekran)
  if (settings && settings.bot_active === false) {
    return (
      <div className={`${theme} min-h-screen flex flex-col items-center justify-center text-center p-8 relative overflow-hidden ${isDark ? 'bg-[#000000] text-white' : 'bg-[#f2f2f7] text-neutral-900'}`}>
        <div className="aurora-blob aurora-1 -top-24 -left-20 w-96 h-96" />
        <div className="aurora-blob aurora-2 -bottom-24 -right-20 w-96 h-96" />
        <div className="noise-overlay" />
        <div className="relative z-10 liquid-glass-card rounded-[36px] p-8 max-w-xs w-full sheet-in">
          <div className={`w-16 h-16 mx-auto rounded-[22px] liquid-glass-pill flex items-center justify-center mb-5 ${isDark ? 'text-amber-300' : 'text-amber-600'}`}>
            <PauseCircle className="w-8 h-8" />
          </div>
          <h1 className={`text-xl font-bold mb-2 ${isDark ? 'text-white' : 'text-neutral-900'}`}>
            Bot vaqtincha to'xtatilgan
          </h1>
          <p className={`text-sm leading-relaxed ${isDark ? 'text-neutral-400' : 'text-neutral-600'}`}>
            Iltimos, birozdan so'ng qayta urinib ko'ring.
          </p>
          <div className={`mt-5 inline-flex items-center gap-2 px-4 py-2 rounded-full liquid-glass-pill text-xs font-semibold ${isDark ? 'text-neutral-300' : 'text-neutral-700'}`}>
            <span className="w-2 h-2 rounded-full bg-amber-400 live-dot" />
            Tez orada qayta ishlaydi
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`${theme} min-h-screen ${isDark ? 'bg-[#000000] text-neutral-100' : 'bg-[#f2f2f7] text-neutral-900'} relative overflow-x-hidden transition-colors duration-300 font-sans`}>
      {/* LiquidPointer — glass specular yorug'i + aurora parallaks */}
      <LiquidPointer />

      {/* Neon Aurora backdrop — glass uchun rangli refraksiya */}
      <div className="fixed inset-0 pointer-events-none z-0" aria-hidden style={{ transform: 'translate(var(--ax), var(--ay))' }}>
        <div className="aurora-blob aurora-1 -top-32 -left-24 w-[420px] h-[420px]" />
        <div className="aurora-blob aurora-2 top-1/4 -right-28 w-[380px] h-[380px]" />
        <div className="aurora-blob aurora-3 -bottom-28 left-1/3 w-[360px] h-[360px]" />
        <div className="aurora-blob aurora-4 top-2/3 -left-1/4 w-[300px] h-[300px]" />
      </div>
      <div className="noise-overlay" />

      {/* Apple Minimalist Toast */}
      {toastMsg && (
        <div className="fixed top-14 left-1/2 -translate-x-1/2 z-50 max-w-xs w-full px-4 pointer-events-none">
          <div className="toast-in liquid-glass rounded-full px-4 py-2.5 shadow-2xl flex items-center justify-center gap-2 border">
            <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
            <span className="text-xs font-semibold text-center">{toastMsg}</span>
          </div>
        </div>
      )}

      {/* Modern Apple Minimalist Header */}
      <Header
        user={user}
        settings={settings}
        lang={lang}
        onChangeLang={handleLangChange}
        isDark={isDark}
        onToggleTheme={handleToggleTheme}
        onOpenTopup={() => setCurrentTab('topup')}
        onOpenAdmin={isAdmin ? () => setCurrentTab('admin') : undefined}
        isAdmin={isAdmin}
      />

      {/* Main View Area */}
      <main className="flex-1 max-w-md w-full mx-auto px-4 pt-3.5 relative z-10">
        {/* 1. HOME VIEW */}
        {currentTab === 'home' && (
          <HomeView
            user={user}
            settings={settings}
            lang={lang}
            isDark={isDark}
            onGoToBuy={(cat) => {
              if (cat) setInitialBuyCategory(cat);
              setCurrentTab('buy');
            }}
            onGoToTopup={() => setCurrentTab('topup')}
          />
        )}

        {/* 2. TOP UP VIEW */}
        {currentTab === 'topup' && (
          <TopupView
            user={user}
            settings={settings}
            lang={lang}
            isDark={isDark}
            activeTopup={activeTopup}
            onTopupCreated={(t) => {
              setActiveTopup(t);
              showToast("To'lov so'rovi yaratildi.");
            }}
            onTopupSuccess={handleTopupSuccess}
            onOpenHistory={() => setCurrentTab('profile')}
          />
        )}

        {/* 3. BUY VIEW (Stars, Premium, Gifts) */}
        {currentTab === 'buy' && (
          <BuyView
            user={user}
            settings={settings}
            lang={lang}
            isDark={isDark}
            initialTab={initialBuyCategory}
            onOrderSuccess={handleOrderSuccess}
            onGoToTopup={() => setCurrentTab('topup')}
          />
        )}

        {/* 4. RANKING VIEW */}
        {currentTab === 'ranking' && (
          <RankingView
            user={user}
            contest={contest}
            lang={lang}
            isDark={isDark}
            onGoToBuy={() => setCurrentTab('buy')}
          />
        )}

        {/* 5. PROFILE VIEW */}
        {currentTab === 'profile' && (
          <ProfileView
            user={user}
            settings={settings}
            orders={history}
            lang={lang}
            onChangeLang={handleLangChange}
            isDark={isDark}
            onToggleTheme={handleToggleTheme}
            onGoToTopup={() => setCurrentTab('topup')}
            onOpenAdmin={() => setCurrentTab('admin')}
            isAdmin={isAdmin}
          />
        )}

        {/* 6. SECRET ADMIN VIEW (ONLY FOR USER 8307046273) */}
        {currentTab === 'admin' && isAdmin && (
          <div className="space-y-4 pb-28 apple-view-animate">
            <button
              onClick={() => setCurrentTab('profile')}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full liquid-glass-pill text-xs font-semibold apple-spring cursor-pointer"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Do'konga qaytish</span>
            </button>
            <AdminPanel
              onSettingsUpdated={(newSettings) => setSettings(newSettings)}
            />
          </div>
        )}
      </main>

      {/* Floating Apple Liquid Glass Bottom Navigation Dock */}
      <BottomNav
        currentTab={currentTab}
        onChangeTab={(tab) => {
          triggerHaptic('light');
          setCurrentTab(tab);
        }}
        lang={lang}
        isDark={isDark}
      />
    </div>
  );
}
