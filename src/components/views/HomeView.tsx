import React, { useRef } from 'react';
import { User, StoreSettings } from '../../types';
import { Lang, translations } from '../../i18n';
import { ShoppingBag, Star, Sparkles, Gift, ChevronRight, Zap } from 'lucide-react';

interface HomeViewProps {
  user: User | null;
  settings: StoreSettings | null;
  lang: Lang;
  isDark: boolean;
  onGoToBuy: (initialCategory?: 'stars' | 'premium' | 'gifts') => void;
  onGoToTopup: () => void;
}

export const HomeView: React.FC<HomeViewProps> = ({
  user,
  settings,
  lang,
  isDark,
  onGoToBuy,
}) => {
  const t = translations[lang];
  const starPrice = settings?.star_buy_price || 200;
  const heroRef = useRef<HTMLDivElement>(null);

  /* Apple VisionOS uslubida 3D tilt — pointerga qarab egiladi */
  const onHeroMove = (e: React.PointerEvent) => {
    const el = heroRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const px = (e.clientX - r.left) / r.width - 0.5;
    const py = (e.clientY - r.top) / r.height - 0.5;
    el.style.setProperty('--ry', `${(px * 7).toFixed(2)}deg`);
    el.style.setProperty('--rx', `${(-py * 7).toFixed(2)}deg`);
  };
  const onHeroLeave = () => {
    const el = heroRef.current;
    if (!el) return;
    el.style.setProperty('--rx', '0deg');
    el.style.setProperty('--ry', '0deg');
  };

  return (
    <div className="space-y-4 max-w-md mx-auto pb-28">
      {/* 1. Ultra-Minimalist Apple VisionOS Liquid Glass Hero Banner */}
      <div
        ref={heroRef}
        onPointerMove={onHeroMove}
        onPointerLeave={onHeroLeave}
        className="relative overflow-hidden rounded-[32px] liquid-glass-card p-6 text-center apple-view-animate stagger-1 tilt-card"
      >
        {/* Specular Liquid Sheen Animation */}
        <div className="sheen-overlay" />

        {/* Center Floating VisionOS Glass Icon */}
        <div className={`relative mx-auto w-15 h-15 rounded-[22px] p-[2px] mb-4 flex items-center justify-center shadow-lg ${
          isDark
            ? 'bg-gradient-to-b from-white/30 via-white/10 to-transparent shadow-[0_0_25px_rgba(255,255,255,0.08)]'
            : 'bg-gradient-to-b from-black/10 via-black/5 to-transparent shadow-[0_4px_16px_rgba(0,0,0,0.06)]'
        }`}>
          <img
            src="/logo.svg"
            alt="NeonStore"
            className="w-full h-full rounded-[20px] object-cover"
          />
        </div>

        {/* Subtitle Minimalist Badge */}
        <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-semibold uppercase tracking-wider mb-2.5 ${
          isDark ? 'bg-white/[0.08] text-neutral-300' : 'bg-black/[0.05] text-neutral-600'
        }`}>
          <Zap className="w-3 h-3 text-cyan-400 opacity-80" />
          <span>{t.telegramServices}</span>
        </div>

        {/* Hero Title & Description */}
        <h2 className={`text-xl font-bold tracking-tight leading-snug ${isDark ? 'text-white' : 'text-neutral-900'}`}>
          {t.heroTitle}
        </h2>
        <p className={`text-xs mt-2 max-w-xs mx-auto leading-relaxed ${isDark ? 'text-neutral-400' : 'text-neutral-600'}`}>
          {t.heroSubtitle}
        </p>

        {/* Apple Tactile CTA Button (Minimalist Monochrome Glass) */}
        <button
          onClick={() => onGoToBuy('stars')}
          className={`mt-5 w-full py-3.5 px-6 rounded-[20px] font-semibold text-xs flex items-center justify-center gap-2 apple-spring cursor-pointer ${
            isDark
              ? 'bg-white text-black hover:bg-neutral-100 shadow-[0_10px_25px_rgba(255,255,255,0.15)]'
              : 'bg-black text-white hover:bg-neutral-800 shadow-[0_10px_25px_rgba(0,0,0,0.15)]'
          }`}
        >
          <ShoppingBag className="w-4 h-4 stroke-[2.2]" />
          <span>{t.startShopping}</span>
        </button>
      </div>

      {/* 2. Apple Minimalist Liquid Glass Service Cards */}
      <div className="space-y-2.5">
        {/* Telegram Stars Card */}
        <div
          onClick={() => onGoToBuy('stars')}
          className="group relative overflow-hidden rounded-[24px] liquid-glass p-4 flex items-center justify-between apple-spring apple-view-animate stagger-2 cursor-pointer"
        >
          <div className="flex items-center gap-3.5">
            <div className={`w-11 h-11 rounded-[18px] flex items-center justify-center ${
              isDark ? 'bg-white/[0.08] text-amber-300' : 'bg-black/[0.04] text-amber-600'
            }`}>
              <Star className="w-5 h-5 fill-current drop-shadow-sm" />
            </div>
            <div>
              <h3 className={`text-xs font-bold ${isDark ? 'text-white' : 'text-neutral-900'}`}>
                Telegram Stars
              </h3>
              <p className={`text-[11px] mt-0.5 ${isDark ? 'text-neutral-400' : 'text-neutral-500'}`}>
                {t.starsDesc}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className={`text-[11px] font-bold px-2.5 py-1 rounded-full liquid-glass-pill ${
              isDark ? 'text-neutral-200' : 'text-neutral-800'
            }`}>
              1 ★ = {starPrice} UZS
            </span>
            <ChevronRight className="w-4 h-4 opacity-40 group-hover:opacity-100 transition-opacity" />
          </div>
        </div>

        {/* Telegram Premium Card */}
        <div
          onClick={() => onGoToBuy('premium')}
          className="group relative overflow-hidden rounded-[24px] liquid-glass p-4 flex items-center justify-between apple-spring apple-view-animate stagger-3 cursor-pointer"
        >
          <div className="flex items-center gap-3.5">
            <div className={`w-11 h-11 rounded-[18px] flex items-center justify-center ${
              isDark ? 'bg-white/[0.08] text-blue-300' : 'bg-black/[0.04] text-blue-600'
            }`}>
              <Sparkles className="w-5 h-5 drop-shadow-sm" />
            </div>
            <div>
              <h3 className={`text-xs font-bold ${isDark ? 'text-white' : 'text-neutral-900'}`}>
                Telegram Premium
              </h3>
              <p className={`text-[11px] mt-0.5 ${isDark ? 'text-neutral-400' : 'text-neutral-500'}`}>
                {t.premiumDesc}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className={`text-[11px] font-bold px-2.5 py-1 rounded-full liquid-glass-pill ${
              isDark ? 'text-neutral-200' : 'text-neutral-800'
            }`}>
              {t.fromWord} 40 000 UZS
            </span>
            <ChevronRight className="w-4 h-4 opacity-40 group-hover:opacity-100 transition-opacity" />
          </div>
        </div>

        {/* Gifts Card */}
        <div
          onClick={() => onGoToBuy('gifts')}
          className="group relative overflow-hidden rounded-[24px] liquid-glass p-4 flex items-center justify-between apple-spring apple-view-animate stagger-4 cursor-pointer"
        >
          <div className="flex items-center gap-3.5">
            <div className={`w-11 h-11 rounded-[18px] flex items-center justify-center ${
              isDark ? 'bg-white/[0.08] text-neutral-300' : 'bg-black/[0.04] text-neutral-700'
            }`}>
              <Gift className="w-5 h-5 drop-shadow-sm" />
            </div>
            <div>
              <h3 className={`text-xs font-bold ${isDark ? 'text-white' : 'text-neutral-900'}`}>
                Telegram Gifts
              </h3>
              <p className={`text-[11px] mt-0.5 ${isDark ? 'text-neutral-400' : 'text-neutral-500'}`}>
                {t.giftsDesc}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className={`text-[11px] font-bold px-2.5 py-1 rounded-full liquid-glass-pill ${
              isDark ? 'text-neutral-200' : 'text-neutral-800'
            }`}>
              {t.fromWord} 3 000 UZS
            </span>
            <ChevronRight className="w-4 h-4 opacity-40 group-hover:opacity-100 transition-opacity" />
          </div>
        </div>
      </div>
    </div>
  );
};
