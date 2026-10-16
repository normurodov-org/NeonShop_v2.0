import React from 'react';
import { User, StoreSettings } from '../types';
import { Lang } from '../i18n';
import { ShieldCheck, Plus, Settings, Globe, Sun, Moon } from 'lucide-react';

interface HeaderProps {
  /** `window.innerWidth >= 768` — sarlavhani chap menyudan o'ngga surish */
  isDesktop?: boolean;
  user: User | null;
  settings: StoreSettings | null;
  lang: Lang;
  onChangeLang: (lang: Lang) => void;
  isDark: boolean;
  onToggleTheme: () => void;
  onOpenTopup: () => void;
  onOpenAdmin?: () => void;
  isAdmin: boolean;
  /** Bot nomi (`shop_neonbot`) — «Telegram Bot» tugmasi uchun */
  botUsername?: string;
}

export const Header: React.FC<HeaderProps> = ({
  user,
  settings,
  lang,
  onChangeLang,
  isDark,
  onToggleTheme,
  onOpenTopup,
  onOpenAdmin,
  isAdmin,
  isDesktop = false,
  botUsername = '',
}) => {
  // 🔴 Bot havolasi — `@` va bo'sh joylarni tozalaymiz
  const botHandle = (botUsername || '').trim().replace(/^@/, '');
  const [avatarError, setAvatarError] = React.useState(false);

  // 🔴 `avatarError` bir marta `true` bo'lsa butunlay
  // QOLIB KETARDI (rasm yangilansa ham). Telegram rasm havolasi
  // vaqt o'tib o'zgaradi (mijoz rasmni yangilasa) — eski 404 bo'lsa
  // har doim birinchi harf ko'rsatilardi.
  React.useEffect(() => {
    setAvatarError(false);
  }, [user?.photo_url]);

  const initial = user?.username ? user.username.charAt(0).toUpperCase() : 'N';
  const displayName = user?.username ? `@${user.username}` : (user?.first_name || 'Mijoz');

  const cycleLang = () => {
    if (lang === 'uz') onChangeLang('ru');
    else if (lang === 'ru') onChangeLang('en');
    else onChangeLang('uz');
  };

  return (
    /* 🍎 APPLE: «Scroll views offer a scroll edge effect that helps
       maintain sufficient legibility and contrast for controls by
       obscuring content that scrolls beneath them.»
       `glass-scroll-edge` — kontent sarlavha ostida eriydi, matn
       o'qilmay qolmaydi. Avval oddiy `backdrop-blur-2xl` edi.

       🔴 `rail-clear` — chap menyu bilan qoplanmasligi uchun.
       Avval `md:pl-[124px]` edi, lekin `xl:px-10` undan KEYIN
       chiqib, `padding-inline` bilan chapni qayta yozardi
       (≥1280px da 124px → 40px) va sarlavha menyu ustiga
       chiqib qolardi. Endi `html body .rail-clear` (0,1,2). */
    <header className="glass-scroll-edge glass-bottom-edge liquid-glass-nav sticky top-0 z-30 px-4 pt-3 pb-2.5 border-b transition-colors duration-300 border-white/[0.08]">
      <div
        className="max-w-md md:max-w-none md:px-6 xl:px-10 rail-clear mx-auto flex items-center justify-between gap-2.5"
      >
        {/* User Avatar + Greeting */}
        <div className="flex items-center gap-2.5">
          <div className="relative">
            <div className={`w-9 h-9 rounded-full p-[1.5px] overflow-hidden ${
              isDark
                ? 'bg-gradient-to-tr from-neutral-400 via-neutral-200 to-neutral-500 shadow-[0_0_12px_rgba(255,255,255,0.15)]'
                : 'bg-gradient-to-tr from-neutral-300 via-neutral-100 to-neutral-400 shadow-sm'
            }`}>
              {user?.photo_url && !avatarError ? (
                <img
                  src={user.photo_url}
                  alt={displayName}
                  onError={() => setAvatarError(true)}
                  className="w-full h-full rounded-full object-cover"
                />
              ) : (
                <div className={`w-full h-full rounded-full flex items-center justify-center font-bold text-xs ${
                  isDark ? 'bg-[#18181b] text-neutral-200' : 'bg-neutral-100 text-neutral-800'
                }`}>
                  {initial}
                </div>
              )}
            </div>
            {/* Status dot */}
            <span
              className={`absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full border-2 ${
                isDark ? 'border-[#000000]' : 'border-white'
              } ${settings?.bot_active ? 'bg-emerald-400' : 'bg-rose-500'}`}
            />
          </div>

          <div>
            <div className="flex items-center gap-1">
              <span className={`text-[10px] font-semibold tracking-wider uppercase ${isDark ? 'text-neutral-400' : 'text-neutral-500'}`}>
                NeonShop
              </span>
              <ShieldCheck className="w-3 h-3 text-neutral-400" />
            </div>
            <h2 className={`text-xs font-bold leading-none mt-0.5 truncate max-w-[110px] ${isDark ? 'text-white' : 'text-neutral-900'}`}>
              {displayName}
            </h2>
          </div>
        </div>

        {/* Right Actions: Telegram Bot + Theme + Lang + Admin Gear + Balance */}
        <div className="flex items-center gap-1.5">
          {/* 📲 Telegram Bot — rasmiy kanalga boradi.
              📌 Mijoz so'ragan: sarlavhada «Telegram Bot» tugmasi.
              🔴 `botUsername` kelmasa (server javob bermasa) tugma
                 umuman chiqmaydi — bo'sh joy qolmasin. */}
          {botHandle && (
            <a
              href={`https://t.me/${botHandle}`}
              target="_blank"
              rel="noopener noreferrer"
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-full liquid-glass-pill
                          text-[11px] font-semibold apple-spring cursor-pointer ${
                isDark
                  ? 'text-neutral-200 hover:text-white'
                  : 'text-neutral-700 hover:text-black'
              }`}
              title={`@${botHandle}`}
            >
              {/* 📖 Rasmiy Telegram qog'oz-nokurasi */}
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"
                   aria-hidden="true" focusable="false" className="opacity-90">
                <path d="M9.78 18.65l.28-4.23 7.68-6.92c.34-.31-.07-.46-.52-.19L7.74 13.3 3.64 12c-.88-.25-.89-.86.2-1.3l15.97-6.16c.73-.33 1.43.18 1.15 1.3l-2.72 12.81c-.19.91-.74 1.13-1.5.71L12.6 16.3l-1.99 1.93c-.23.23-.42.42-.83.42z" />
              </svg>
              <span className="uppercase tracking-wide">Bot</span>
            </a>
          )}

          {/* Day / Night Theme Toggle */}
          <button
            onClick={onToggleTheme}
            className={`p-2 rounded-full liquid-glass-pill apple-spring cursor-pointer ${
              isDark ? 'text-amber-300 hover:text-amber-200' : 'text-neutral-700 hover:text-black'
            }`}
            title={isDark ? "Kun rejimiga o'tish" : "Tun rejimiga o'tish"}
          >
            {isDark ? <Sun className="w-3.5 h-3.5" /> : <Moon className="w-3.5 h-3.5" />}
          </button>

          {/* Language Toggle with Apple Glass Pill */}
          <button
            onClick={cycleLang}
            className={`flex items-center gap-1 px-2.5 py-1.5 rounded-full liquid-glass-pill text-xs font-semibold apple-spring cursor-pointer ${
              isDark ? 'text-neutral-300 hover:text-white' : 'text-neutral-700 hover:text-black'
            }`}
            title="Til / Язык / Language"
          >
            <Globe className="w-3 h-3 opacity-70" />
            <span className="uppercase text-[10px] font-bold">{lang}</span>
          </button>

          {/* Admin Button — STRICTLY FOR ADMIN ONLY */}
          {isAdmin && onOpenAdmin && (
            <button
              onClick={onOpenAdmin}
              className="p-2 rounded-full liquid-glass-pill text-amber-400 hover:text-amber-300 apple-spring cursor-pointer"
              title="Admin Panel"
            >
              <Settings className="w-3.5 h-3.5" />
            </button>
          )}

          {/* Minimalist Apple Liquid Balance Pill */}
          <button
            onClick={onOpenTopup}
            className={`flex items-center gap-1 px-3 py-1.5 rounded-full apple-spring cursor-pointer ${
              isDark
                ? 'bg-white/[0.1] hover:bg-white/[0.15] text-white border border-white/15 shadow-[inset_0_1px_1px_rgba(255,255,255,0.25)]'
                : 'bg-black/[0.06] hover:bg-black/[0.1] text-black border border-black/10 shadow-sm'
            }`}
          >
            {/* 🔴 `user.balance` serverda DOIM ham kelmaydi
                (`balance` ixtiyoriy maydon). `user?` faqat `user` null
                bo'lsa himoya qiladi — `user` bor, `balance` yo'q bo'lsa
                TypeError va ilova OQ EKRANGA tushardi (Header
                ErrorBoundary dan tashqarida). */}
            <span className="font-mono text-[11px] font-bold">
              {Number(user?.balance ?? 0).toLocaleString()}
            </span>
            <span className="text-[9px] font-medium opacity-70">UZS</span>
            <Plus className="w-3 h-3 ml-0.5 opacity-80" />
          </button>
        </div>
      </div>
    </header>
  );
};
