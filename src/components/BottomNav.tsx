import React from 'react';
import { Home, Plus, ShoppingBag, Trophy, User } from 'lucide-react';
import { Lang, translations } from '../i18n';

export type TabType = 'home' | 'topup' | 'buy' | 'ranking' | 'profile' | 'admin';

interface BottomNavProps {
  currentTab: TabType;
  onChangeTab: (tab: TabType) => void;
  lang: Lang;
  isDark: boolean;
}

export const BottomNav: React.FC<BottomNavProps> = ({ currentTab, onChangeTab, lang, isDark }) => {
  const t = translations[lang];

  return (
    <div className="fixed bottom-4 left-4 right-4 max-w-md mx-auto z-40 pointer-events-none">
      <nav className="pointer-events-auto relative liquid-glass rounded-full px-2.5 py-1.5 flex items-center justify-between shadow-[0_20px_50px_rgba(0,0,0,0.45)]">
        {/* 1. Home */}
        <button
          onClick={() => onChangeTab('home')}
          className={`flex-1 flex flex-col items-center justify-center py-2 rounded-full apple-spring cursor-pointer ${
            currentTab === 'home'
              ? isDark
                ? 'bg-white/[0.15] text-white shadow-[inset_0_1px_1px_rgba(255,255,255,0.4)]'
                : 'bg-black/[0.08] text-black shadow-[inset_0_1px_1px_rgba(0,0,0,0.1)]'
              : isDark
              ? 'text-neutral-400 hover:text-white'
              : 'text-neutral-500 hover:text-black'
          }`}
        >
          <Home className={`w-5 h-5 transition-transform duration-300 ${currentTab === 'home' ? 'scale-110 stroke-[2.2]' : 'stroke-[1.7]'}`} />
          <span className="text-[10px] mt-0.5 font-medium tracking-tight">{t.home}</span>
        </button>

        {/* 2. Top up */}
        <button
          onClick={() => onChangeTab('topup')}
          className={`flex-1 flex flex-col items-center justify-center py-2 rounded-full apple-spring cursor-pointer ${
            currentTab === 'topup'
              ? isDark
                ? 'bg-white/[0.15] text-white shadow-[inset_0_1px_1px_rgba(255,255,255,0.4)]'
                : 'bg-black/[0.08] text-black shadow-[inset_0_1px_1px_rgba(0,0,0,0.1)]'
              : isDark
              ? 'text-neutral-400 hover:text-white'
              : 'text-neutral-500 hover:text-black'
          }`}
        >
          <Plus className={`w-5 h-5 transition-transform duration-300 ${currentTab === 'topup' ? 'scale-110 stroke-[2.2]' : 'stroke-[1.7]'}`} />
          <span className="text-[10px] mt-0.5 font-medium tracking-tight">{t.topup}</span>
        </button>

        {/* 3. Center Minimalist Apple Liquid Lens Orb */}
        <div className="flex-1 flex flex-col items-center justify-center relative -top-4">
          <button
            onClick={() => onChangeTab('buy')}
            className={`w-13 h-13 rounded-full flex items-center justify-center apple-spring cursor-pointer liquid-lens-button ${
              currentTab === 'buy' ? 'scale-110 ring-4 ring-white/10' : 'hover:scale-105 opacity-95'
            }`}
          >
            <ShoppingBag className={`w-5 h-5 ${isDark ? 'text-white' : 'text-neutral-900'} stroke-[2.4]`} />
          </button>
          <span
            className={`text-[10px] mt-0.5 font-semibold tracking-tight transition-colors ${
              currentTab === 'buy'
                ? isDark ? 'text-white font-bold' : 'text-black font-bold'
                : isDark ? 'text-neutral-400' : 'text-neutral-500'
            }`}
          >
            {t.buy}
          </span>
        </div>

        {/* 4. Ranking */}
        <button
          onClick={() => onChangeTab('ranking')}
          className={`flex-1 flex flex-col items-center justify-center py-2 rounded-full apple-spring cursor-pointer ${
            currentTab === 'ranking'
              ? isDark
                ? 'bg-white/[0.15] text-white shadow-[inset_0_1px_1px_rgba(255,255,255,0.4)]'
                : 'bg-black/[0.08] text-black shadow-[inset_0_1px_1px_rgba(0,0,0,0.1)]'
              : isDark
              ? 'text-neutral-400 hover:text-white'
              : 'text-neutral-500 hover:text-black'
          }`}
        >
          <Trophy className={`w-5 h-5 transition-transform duration-300 ${currentTab === 'ranking' ? 'scale-110 stroke-[2.2]' : 'stroke-[1.7]'}`} />
          <span className="text-[10px] mt-0.5 font-medium tracking-tight">{t.ranking}</span>
        </button>

        {/* 5. Profile */}
        <button
          onClick={() => onChangeTab('profile')}
          className={`flex-1 flex flex-col items-center justify-center py-2 rounded-full apple-spring cursor-pointer ${
            currentTab === 'profile'
              ? isDark
                ? 'bg-white/[0.15] text-white shadow-[inset_0_1px_1px_rgba(255,255,255,0.4)]'
                : 'bg-black/[0.08] text-black shadow-[inset_0_1px_1px_rgba(0,0,0,0.1)]'
              : isDark
              ? 'text-neutral-400 hover:text-white'
              : 'text-neutral-500 hover:text-black'
          }`}
        >
          <User className={`w-5 h-5 transition-transform duration-300 ${currentTab === 'profile' ? 'scale-110 stroke-[2.2]' : 'stroke-[1.7]'}`} />
          <span className="text-[10px] mt-0.5 font-medium tracking-tight">{t.profile}</span>
        </button>
      </nav>
    </div>
  );
};
