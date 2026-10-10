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

const TABS: { id: TabType; icon: React.ElementType }[] = [
  { id: 'home', icon: Home },
  { id: 'topup', icon: Plus },
  { id: 'buy', icon: ShoppingBag },
  { id: 'ranking', icon: Trophy },
  { id: 'profile', icon: User },
];

export const BottomNav: React.FC<BottomNavProps> = ({ currentTab, onChangeTab, lang, isDark }) => {
  const t = translations[lang];
  const labels: Record<TabType, string> = {
    home: t.home,
    topup: t.topup,
    buy: t.buy,
    ranking: t.ranking,
    profile: t.profile,
    admin: t.admin,
  };
  const idx = TABS.findIndex((tab) => tab.id === currentTab);

  return (
    <div className="fixed bottom-4 left-4 right-4 max-w-md mx-auto z-40 pointer-events-none">
      <nav className="pointer-events-auto relative liquid-glass rounded-full px-2.5 py-1.5 flex items-center justify-between shadow-[0_20px_50px_rgba(0,0,0,0.45)]">
        {/* Suzuvchi Liquid indikator — faol tab orqasida silliq siljinadi */}
        {idx >= 0 && (
          <div
            className="dock-indicator"
            style={{ transform: `translateX(calc(100% * ${idx} + ${idx * 12}px))` }}
          />
        )}

        {TABS.map(({ id, icon: Icon }) => {
          const active = currentTab === id;
          const isCenter = id === 'buy';
          return (
            <button
              key={id}
              onClick={() => onChangeTab(id)}
              className={`flex-1 flex flex-col items-center justify-center ${
                isCenter ? 'relative -top-4' : 'py-2'
              } apple-spring cursor-pointer`}
            >
              {isCenter ? (
                /* Markaziy Liquid Lens Orb — yuqori ko'tarilgan */
                <span
                  className={`w-13 h-13 rounded-full flex items-center justify-center liquid-lens-button apple-spring cursor-pointer transition-transform duration-300 ${
                    active ? 'scale-110' : 'hover:scale-105'
                  }`}
                >
                  <Icon className={`w-5 h-5 ${isDark ? 'text-white' : 'text-neutral-900'} stroke-[2.4]`} />
                </span>
              ) : (
                <Icon
                  className={`w-5 h-5 transition-all duration-300 ${
                    active ? 'scale-110 stroke-[2.2]' : 'stroke-[1.7]'
                  }`}
                />
              )}
              <span
                className={`text-[10px] mt-0.5 font-medium tracking-tight transition-colors duration-300 ${
                  active
                    ? isDark
                      ? 'text-white font-bold'
                      : 'text-black font-bold'
                    : isDark
                    ? 'text-neutral-400'
                    : 'text-neutral-500'
                }`}
              >
                {labels[id]}
              </span>
            </button>
          );
        })}
      </nav>
    </div>
  );
};
