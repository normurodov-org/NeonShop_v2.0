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
import { CheckCircle2, ArrowLeft } from 'lucide-react';

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

  const handleTopupSuccess = (newBalance: number, msg: string) => {
    if (user) {
      setUser({ ...user, balance: newBalance });
    }
    setActiveTopup(null);
    showToast(msg);
  };

  return (
    <div className={`${theme} min-h-screen ${isDark ? 'bg-[#000000] text-neutral-100' : 'bg-[#f2f2f7] text-neutral-900'} relative overflow-x-hidden transition-colors duration-300 font-sans`}>
      {/* Ambient Fluid Background Elements */}
      <div className={`fixed -top-28 -left-20 w-88 h-88 rounded-full blur-[110px] pointer-events-none ambient-fluid-1 ${
        isDark ? 'bg-white/[0.04]' : 'bg-black/[0.03]'
      }`} />
      <div className={`fixed top-1/3 -right-24 w-96 h-96 rounded-full blur-[130px] pointer-events-none ambient-fluid-2 ${
        isDark ? 'bg-white/[0.03]' : 'bg-black/[0.02]'
      }`} />
      <div className={`fixed -bottom-24 left-1/4 w-80 h-80 rounded-full blur-[100px] pointer-events-none ${
        isDark ? 'bg-white/[0.02]' : 'bg-black/[0.02]'
      }`} />

      {/* Apple Minimalist Toast */}
      {toastMsg && (
        <div className="fixed top-14 left-1/2 -translate-x-1/2 z-50 max-w-xs w-full px-4 animate-in fade-in slide-in-from-top-3 duration-300 pointer-events-none">
          <div className="liquid-glass rounded-full px-4 py-2.5 shadow-2xl flex items-center justify-center gap-2 border">
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
      <main className="flex-1 max-w-md w-full mx-auto px-4 pt-3.5">
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
