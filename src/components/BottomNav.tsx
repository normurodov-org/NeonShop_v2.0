/**
 * 📐 BottomNav — telefon uchun pastki panel, DESKTOP uchun chap menyu.
 *
 * 🔴 NIMA UCHUN IKKI KO'RINISH?
 * Pastki panel telefon uchun to'g'ri. Lekin kompyuterda (≥1024px)
 * ekranning pastki qismi juda uzoqda bo'ladi — sichqoncha uzoq
 * yurish kerak, panel esa butun ekran kengligida "telefon
 * kattalashtirilgan" ko'rinishda qolardi.
 *
 * Desktopda biz:
 *   • chap tomonga VERTIKAL menyu qo'yamiz (110px keng)
 *   • kontentni o'ngga siljitamiz (App.tsx `md:pl-[124px]`)
 *   • markaziy "lens" tugmasi oddiy qator tugmasiga aylanadi
 */
import React from 'react';
import { Home, Plus, ShoppingBag, Trophy, User } from 'lucide-react';
import { Lang, translations } from '../i18n';

export type TabType = 'home' | 'topup' | 'buy' | 'ranking' | 'profile' | 'admin';

interface BottomNavProps {
  currentTab: TabType;
  onChangeTab: (tab: TabType) => void;
  lang: Lang;
  isDark: boolean;
  /** `window.innerWidth >= 768` — bitta manba (useLayout) */
  isDesktop: boolean;
}

const TABS: { id: TabType; icon: React.ElementType }[] = [
  { id: 'home', icon: Home },
  { id: 'topup', icon: Plus },
  { id: 'buy', icon: ShoppingBag },
  { id: 'ranking', icon: Trophy },
  { id: 'profile', icon: User },
];

export const BottomNav: React.FC<BottomNavProps> = ({
  currentTab, onChangeTab, lang, isDark, isDesktop,
}) => {
  const t = translations[lang];
  const labels: Record<TabType, string> = {
    home: t.home,
    topup: t.topup,
    buy: t.buy,
    ranking: t.ranking,
    profile: t.profile,
    admin: t.admin,
  };

  // =======================================================================
  // 🖥 DESKTOP — chapdagi vertikal menyu
  // =======================================================================
  if (isDesktop) {
    return (
      <nav
        aria-label="Asosiy menyu"
        className="fixed left-4 top-1/2 -translate-y-1/2 z-40 w-[92px] rounded-[28px] liquid-glass p-2 flex flex-col gap-1.5 shadow-[0_20px_50px_rgba(0,0,0,0.35)]"
      >
        {TABS.map(({ id, icon: Icon }) => {
          const active = currentTab === id;
          return (
            <button
              key={id}
              onClick={() => onChangeTab(id)}
              aria-current={active ? 'page' : undefined}
              title={labels[id]}
              className={`flex flex-col items-center justify-center gap-1.5 rounded-[20px] py-3 apple-spring cursor-pointer transition-colors duration-300 ${
                active
                  ? isDark
                    ? 'bg-white/[0.16] shadow-[inset_0_1px_1px_rgba(255,255,255,0.4)]'
                    : 'bg-black/[0.09] shadow-[inset_0_1px_1px_rgba(0,0,0,0.12)]'
                  : isDark
                    ? 'hover:bg-white/[0.07]'
                    : 'hover:bg-black/[0.05]'
              }`}
            >
              <Icon
                className={`w-[22px] h-[22px] transition-all duration-300 ${
                  active ? 'scale-110 stroke-[2.3]' : 'stroke-[1.8]'
                } ${active ? (isDark ? 'text-white' : 'text-black')
                         : (isDark ? 'text-neutral-400' : 'text-neutral-600')}`}
              />
              <span
                className={`text-[10px] font-semibold tracking-tight transition-colors duration-300 ${
                  active
                    ? isDark ? 'text-white' : 'text-black'
                    : isDark ? 'text-neutral-400' : 'text-neutral-600'
                }`}
              >
                {labels[id]}
              </span>
            </button>
          );
        })}
      </nav>
    );
  }

  // =======================================================================
  // 📱 TELEFON — pastki panel (dizayn o'zgarmadi)
  // =======================================================================
  return (
    <div className="fixed bottom-4 left-4 right-4 max-w-md mx-auto z-40 pointer-events-none">
      <nav className="pointer-events-auto relative liquid-glass rounded-full px-2.5 py-1.5 flex items-center justify-between shadow-[0_20px_50px_rgba(0,0,0,0.45)]">
        {TABS.map(({ id, icon: Icon }) => {
          const active = currentTab === id;
          const isCenter = id === 'buy';

          // Markaziy Liquid Lens Orb — ko'tarilgan va premium halqa bilan
          if (isCenter) {
            return (
              <button
                key={id}
                onClick={() => onChangeTab(id)}
                className="flex-1 flex flex-col items-center justify-center relative -top-4 cursor-pointer"
              >
                <span
                  className={`w-13 h-13 rounded-full flex items-center justify-center liquid-lens-button apple-spring cursor-pointer transition-transform duration-300 ${
                    active ? 'scale-110' : 'hover:scale-105'
                  }`}
                >
                  <Icon
                    className={`w-5 h-5 ${isDark ? 'text-white' : 'text-neutral-900'} stroke-[2.4]`}
                  />
                </span>
                <span
                  className={`text-[10px] mt-0.5 font-medium tracking-tight transition-all duration-300 ${
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
          }

          // Oddiy tugmalar — faol holatda o'z pill'i bilan
          return (
            <button
              key={id}
              onClick={() => onChangeTab(id)}
              className={`flex-1 flex flex-col items-center justify-center py-2 rounded-full apple-spring cursor-pointer transition-colors duration-300 ${
                active
                  ? isDark
                    ? 'bg-white/[0.15] shadow-[inset_0_1px_1px_rgba(255,255,255,0.4)]'
                    : 'bg-black/[0.08] shadow-[inset_0_1px_1px_rgba(0,0,0,0.1)]'
                  : isDark
                  ? 'text-neutral-400 hover:text-white'
                  : 'text-neutral-500 hover:text-black'
              }`}
            >
              <Icon
                className={`w-5 h-5 transition-all duration-300 ${
                  active ? 'scale-110 stroke-[2.2]' : 'stroke-[1.7]'
                }`}
              />
              <span
                className={`text-[10px] mt-0.5 font-medium tracking-tight transition-colors duration-300 ${
                  active ? (isDark ? 'text-white' : 'text-black') : ''
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
