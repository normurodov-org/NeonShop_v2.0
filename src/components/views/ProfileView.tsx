import React, { useState } from 'react';
import { User, StoreSettings, Order } from '../../types';
import { Lang, translations } from '../../i18n';
import { Shield, Plus, Users, Globe, Headphones, Settings, Copy, Check, ChevronRight, Sparkles, Star, Sun, Moon } from 'lucide-react';

interface ProfileViewProps {
  user: User | null;
  settings: StoreSettings | null;
  orders: Order[];
  lang: Lang;
  onChangeLang: (lang: Lang) => void;
  isDark: boolean;
  onToggleTheme: () => void;
  onGoToTopup: () => void;
  onOpenAdmin: () => void;
  isAdmin: boolean;
}

export const ProfileView: React.FC<ProfileViewProps> = ({
  user,
  settings,
  orders,
  lang,
  onChangeLang,
  isDark,
  onToggleTheme,
  onGoToTopup,
  onOpenAdmin,
  isAdmin,
}) => {
  const t = translations[lang];
  const [copiedRef, setCopiedRef] = useState<boolean>(false);
  const [showReferralModal, setShowReferralModal] = useState<boolean>(false);

  const initial = user?.username ? user.username.charAt(0).toUpperCase() : 'O';
  const displayName = user?.username ? `@${user.username}` : (user?.first_name || 'odilbek');
  const userBalance = user?.balance || 0;
  const userSpent = user?.total_spent || 0;

  const refLink = `https://t.me/shop_neonbot?start=u${user?.id || '8307046273'}`;

  const copyRefLink = () => {
    navigator.clipboard.writeText(refLink);
    setCopiedRef(true);
    setTimeout(() => setCopiedRef(false), 2000);
  };

  return (
    <div className="space-y-4 max-w-md mx-auto pb-28 apple-view-animate">
      {/* 1. Header Profile Banner */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-full p-[1.5px] overflow-hidden liquid-glass-pill shadow-sm">
            {user?.photo_url ? (
              <img
                src={user.photo_url}
                alt={displayName}
                className="w-full h-full rounded-full object-cover"
              />
            ) : (
              <div className="w-full h-full rounded-full flex items-center justify-center font-bold text-sm">
                {initial}
              </div>
            )}
          </div>
          <div>
            <h2 className={`text-sm font-bold tracking-tight ${isDark ? 'text-white' : 'text-neutral-900'}`}>{displayName}</h2>
            <p className="text-[11px] text-neutral-400 font-mono mt-0.5">
              User ID: <b>{user?.id || '8307046273'}</b>
            </p>
          </div>
        </div>

        {/* Secret Admin button if Admin */}
        {isAdmin && (
          <button
            onClick={onOpenAdmin}
            className="p-2.5 rounded-full liquid-glass-pill text-amber-400 apple-spring cursor-pointer"
            title="Admin Panel"
          >
            <Settings className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* 2. Apple Liquid Glass Minimalist Balance Card */}
      <div className="relative overflow-hidden rounded-[28px] p-5 text-white liquid-glass-card shadow-lg">
        {/* Specular sheen */}
        <div className="sheen-overlay" />

        <div className="flex items-center justify-between">
          <span className={`text-xs font-semibold ${isDark ? 'text-neutral-300' : 'text-neutral-600'}`}>{t.balance}</span>
          <span className={`text-[10px] px-2.5 py-0.5 rounded-full font-mono font-bold uppercase ${
            isDark ? 'bg-white/10 text-neutral-200' : 'bg-black/5 text-neutral-700'
          }`}>
            UZS
          </span>
        </div>

        <div className={`text-2xl font-bold font-mono tracking-tight mt-2 mb-4 ${isDark ? 'text-white' : 'text-neutral-900'}`}>
          {userBalance.toLocaleString()}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={onGoToTopup}
            className={`flex-1 py-3 rounded-[16px] font-semibold text-xs flex items-center justify-center gap-1.5 apple-spring cursor-pointer ${
              isDark
                ? 'bg-white text-black hover:bg-neutral-100 shadow-sm'
                : 'bg-black text-white hover:bg-neutral-800 shadow-sm'
            }`}
          >
            <Plus className="w-3.5 h-3.5 stroke-[2.4]" />
            <span>{t.topup}</span>
          </button>

          <button
            onClick={() => setShowReferralModal(true)}
            className={`flex-1 py-3 rounded-[16px] font-semibold text-xs flex items-center justify-center gap-1.5 apple-spring cursor-pointer liquid-glass-pill ${
              isDark ? 'text-white' : 'text-neutral-900'
            }`}
          >
            <Users className="w-3.5 h-3.5 stroke-[2.4]" />
            <span>Referral</span>
          </button>
        </div>
      </div>

      {/* 3. Weekly Bonus Card */}
      <div className="rounded-[26px] liquid-glass-card p-4 space-y-2.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5 text-amber-400" />
            <span className={`text-xs font-semibold ${isDark ? 'text-white' : 'text-neutral-900'}`}>{t.weeklyBonus}</span>
          </div>
          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold liquid-glass-pill">
            +25 000 UZS
          </span>
        </div>

        <div className={`w-full rounded-full h-2 overflow-hidden ${isDark ? 'bg-white/10' : 'bg-black/10'}`}>
          <div
            className={`h-full rounded-full transition-all duration-700 ${isDark ? 'bg-white' : 'bg-black'}`}
            style={{ width: `${Math.min(100, (userSpent / 500000) * 100)}%` }}
          />
        </div>

        <div className="flex justify-between text-[10px] text-neutral-400">
          <span>Haftalik: <b>{userSpent.toLocaleString()} / 500 000</b></span>
          <span>Qoldi: {Math.max(0, 500000 - userSpent).toLocaleString()} UZS</span>
        </div>
      </div>

      {/* 4. Purchase Stats Box */}
      <div className="rounded-[26px] liquid-glass-card p-4 space-y-2.5">
        <h3 className={`text-xs font-semibold ${isDark ? 'text-white' : 'text-neutral-900'}`}>{t.purchaseStats}</h3>

        <div className="grid grid-cols-2 gap-2">
          <div className={`p-3 rounded-[16px] ${isDark ? 'bg-black/20' : 'bg-white/50'}`}>
            <span className="text-[10px] text-neutral-400">{t.spent}</span>
            <div className={`text-sm font-bold font-mono mt-0.5 ${isDark ? 'text-white' : 'text-neutral-900'}`}>
              {userSpent.toLocaleString()} <span className="text-[10px] font-normal opacity-70">UZS</span>
            </div>
          </div>
          <div className={`p-3 rounded-[16px] ${isDark ? 'bg-black/20' : 'bg-white/50'}`}>
            <span className="text-[10px] text-neutral-400">{t.orders}</span>
            <div className={`text-sm font-bold font-mono mt-0.5 ${isDark ? 'text-white' : 'text-neutral-900'}`}>
              {orders.length} <span className="text-[10px] font-normal opacity-70">{t.orders}</span>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2 text-center">
          <div className={`p-2 rounded-[14px] ${isDark ? 'bg-black/20' : 'bg-white/50'}`}>
            <div className={`text-xs font-bold font-mono ${isDark ? 'text-white' : 'text-neutral-900'}`}>550</div>
            <div className="text-[9px] text-neutral-400">Stars</div>
          </div>
          <div className={`p-2 rounded-[14px] ${isDark ? 'bg-black/20' : 'bg-white/50'}`}>
            <div className={`text-xs font-bold font-mono ${isDark ? 'text-white' : 'text-neutral-900'}`}>1</div>
            <div className="text-[9px] text-neutral-400">Premium</div>
          </div>
          <div className={`p-2 rounded-[14px] ${isDark ? 'bg-black/20' : 'bg-white/50'}`}>
            <div className={`text-xs font-bold font-mono ${isDark ? 'text-white' : 'text-neutral-900'}`}>1</div>
            <div className="text-[9px] text-neutral-400">Gift</div>
          </div>
        </div>
      </div>

      {/* 5. Order History List */}
      <div className="rounded-[26px] liquid-glass-card p-4 space-y-2.5">
        <div className="flex items-center justify-between">
          <h3 className={`text-xs font-semibold ${isDark ? 'text-white' : 'text-neutral-900'}`}>{t.orderHistory}</h3>
          <span className="text-[10px] font-mono opacity-70">
            {orders.length} ta
          </span>
        </div>

        {orders.length === 0 ? (
          <p className="text-xs text-neutral-400 text-center py-3">{t.noOrders}</p>
        ) : (
          <div className="space-y-1.5">
            {orders.map((ord) => (
              <div
                key={ord.id}
                className="flex items-center justify-between p-2.5 rounded-[14px] hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
              >
                <div className="flex items-center gap-2.5">
                  <div className={`w-7 h-7 rounded-[10px] flex items-center justify-center ${
                    isDark ? 'bg-white/5 text-amber-300' : 'bg-black/5 text-amber-600'
                  }`}>
                    <Star className="w-3.5 h-3.5 fill-current" />
                  </div>
                  <div>
                    <h4 className={`text-xs font-semibold ${isDark ? 'text-white' : 'text-neutral-900'}`}>{ord.title || `⭐ ${ord.stars || 0} Stars`}</h4>
                    <span className="text-[10px] text-neutral-400">
                      @{ord.recipient} • {ord.created_at?.slice(0, 10)}
                    </span>
                  </div>
                </div>

                <div className="text-right">
                  <div className={`text-xs font-mono font-bold ${isDark ? 'text-white' : 'text-neutral-900'}`}>
                    {(ord.price ?? ord.price_uzs ?? 0).toLocaleString()} UZS
                  </div>
                  <span className={`text-[9px] font-semibold px-2 py-0.5 rounded-full ${
                    ord.status === 'completed'
                      ? 'bg-emerald-500/10 text-emerald-500'
                      : 'bg-amber-500/10 text-amber-500'
                  }`}>
                    {ord.status === 'completed' ? t.done : t.pending}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 6. Settings & Support Options */}
      <div className="rounded-[26px] liquid-glass-card p-1.5 space-y-0.5">
        {/* Day / Night Theme switcher */}
        <div
          onClick={onToggleTheme}
          className="flex items-center justify-between p-3 hover:bg-black/5 dark:hover:bg-white/5 rounded-[16px] transition-colors cursor-pointer"
        >
          <div className="flex items-center gap-2.5 text-xs font-semibold">
            {isDark ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-neutral-700" />}
            <span className={isDark ? 'text-white' : 'text-neutral-900'}>{t.theme}</span>
          </div>
          <div className="flex items-center gap-1.5 text-xs font-bold text-neutral-400">
            <span>{isDark ? t.darkMode : t.lightMode}</span>
            <ChevronRight className="w-3.5 h-3.5 opacity-50" />
          </div>
        </div>

        {/* Language option */}
        <div className="flex items-center justify-between p-3 hover:bg-black/5 dark:hover:bg-white/5 rounded-[16px] transition-colors">
          <div className="flex items-center gap-2.5 text-xs font-semibold">
            <Globe className="w-4 h-4 opacity-70" />
            <span className={isDark ? 'text-white' : 'text-neutral-900'}>{t.language}</span>
          </div>
          <div className="flex items-center gap-1">
            {(['uz', 'ru', 'en'] as Lang[]).map((l) => (
              <button
                key={l}
                onClick={() => onChangeLang(l)}
                className={`px-2.5 py-1 rounded-full text-[10px] font-bold uppercase apple-spring cursor-pointer ${
                  lang === l
                    ? isDark ? 'bg-white text-black' : 'bg-black text-white'
                    : 'liquid-glass-pill opacity-70 hover:opacity-100'
                }`}
              >
                {l}
              </button>
            ))}
          </div>
        </div>

        {/* Support option */}
        <a
          href={`https://t.me/${settings?.support_username || 'normuzb'}`}
          target="_blank"
          rel="noreferrer"
          className="flex items-center justify-between p-3 hover:bg-black/5 dark:hover:bg-white/5 rounded-[16px] transition-colors cursor-pointer"
        >
          <div className="flex items-center gap-2.5 text-xs font-semibold">
            <Headphones className="w-4 h-4 opacity-70" />
            <span className={isDark ? 'text-white' : 'text-neutral-900'}>{t.support}</span>
          </div>
          <ChevronRight className="w-3.5 h-3.5 opacity-50" />
        </a>

        {/* Secret Admin panel entrance (ONLY FOR ADMIN) */}
        {isAdmin && (
          <button
            onClick={onOpenAdmin}
            className="w-full flex items-center justify-between p-3 rounded-[16px] transition-colors cursor-pointer mt-0.5 apple-spring text-amber-500 hover:bg-amber-500/10"
          >
            <div className="flex items-center gap-2 text-xs font-bold">
              <Shield className="w-3.5 h-3.5" />
              <span>⚡ Admin Boshqaruv Paneli</span>
            </div>
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {/* Referral Modal */}
      {showReferralModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xl animate-in fade-in duration-200">
          <div className="w-full max-w-sm rounded-[30px] liquid-glass-card p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between">
              <h3 className={`text-sm font-bold flex items-center gap-2 ${isDark ? 'text-white' : 'text-neutral-900'}`}>
                <Users className="w-4 h-4" />
                <span>Referral Dasturi</span>
              </h3>
              <button
                onClick={() => setShowReferralModal(false)}
                className="w-7 h-7 rounded-full liquid-glass-pill flex items-center justify-center cursor-pointer apple-spring text-xs"
              >
                ✕
              </button>
            </div>

            <p className={`text-xs leading-relaxed ${isDark ? 'text-neutral-300' : 'text-neutral-600'}`}>
              Do'stlaringizni taklif qiling va har bir do'stingiz uchun <b>1 ⭐ Stars</b> oling!
            </p>

            <div className={`p-3 rounded-[16px] space-y-1 ${isDark ? 'bg-black/30' : 'bg-black/5'}`}>
              <span className="text-[10px] text-neutral-400">Sizning taklif havolangiz:</span>
              <div className="text-[11px] font-mono font-semibold break-all opacity-90">
                {refLink}
              </div>
            </div>

            <button
              onClick={copyRefLink}
              className={`w-full py-3.5 rounded-[18px] font-semibold text-xs flex items-center justify-center gap-2 apple-spring cursor-pointer ${
                isDark ? 'bg-white text-black hover:bg-neutral-100' : 'bg-black text-white hover:bg-neutral-800'
              }`}
            >
              {copiedRef ? <Check className="w-4 h-4 text-emerald-500" /> : <Copy className="w-4 h-4" />}
              <span>{copiedRef ? t.copied : 'Havolani nusxalash'}</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
