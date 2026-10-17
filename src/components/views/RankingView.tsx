import React, { useState, useEffect } from 'react';
import { User, Contest } from '../../types';
import { Lang, translations } from '../../i18n';
import { Trophy, Crown, Sparkles, Clock, ShoppingBag } from 'lucide-react';
import { telegramInitData } from '../../lib/tgAuth';
import type { RankingSub } from '../../lib/routes';
import { fmtUzs } from '../../lib/format';

interface RankingViewProps {
  user: User | null;
  contest: Contest | null;
  lang: Lang;
  isDark: boolean;
  onGoToBuy?: () => void;
  /**
   * 🔴🔴🔴 `/ranking` `/ranking/today` `/ranking/3days` `/ranking/7days`
   *   Har bir davr — alohida xizmat, alohida manzil. Avval `timeFilter`
   *   faqat ichki state edi: manzil doim `/ranking` bo'lib qolardi.
   */
  initialPeriod?: RankingSub;
  onPeriodChange?: (p: RankingSub) => void;
}

interface LeaderItem {
  rank: number;
  id: number;
  name: string;
  username: string;
  photo_url?: string;
  orders: number;
  amount: number;
  isMe: boolean;
}

export const RankingView: React.FC<RankingViewProps> = ({ user, contest, lang, isDark, onGoToBuy, initialPeriod = 'all', onPeriodChange }) => {
  const t = translations[lang];
  const [timeFilter, setTimeFilter] = useState<RankingSub>(initialPeriod);

  // 🔴 Manzil -> davr (orqaga tugmasi, havolada ochish)
  useEffect(() => { setTimeFilter(initialPeriod || 'all'); }, [initialPeriod]);

  // 🔴 Davr -> manzil (`/ranking/3days`)
  const switchPeriod = (p: RankingSub) => {
    if (onPeriodChange) onPeriodChange(p);
    else setTimeFilter(p);
  };

  const [leaders, setLeaders] = useState<LeaderItem[]>([]);
  const [myRanking, setMyRanking] = useState<{
    rank: number | null;
    orders: number;
    amount: number;
    inTop10: boolean;
  }>({
    rank: null,
    orders: 0,
    amount: 0,
    inTop10: false,
  });
  const [loading, setLoading] = useState<boolean>(true);

  // Fetch real ranking from database
  useEffect(() => {
    let isMounted = true;
    async function loadRanking() {
      try {
        const res = await fetch(`/api/ranking?period=${timeFilter}`, {
          headers: {
            // 🔴 IMZO: server `x-telegram-user-id` ni ishonchsiz deb
            // qabul qilmaydi. Bu header bo'lmasa `isMe` DOIM false bo'lardi
            // va «Sizning o'rningiz» hech qachon ko'rinmasdi.
            'X-Telegram-Init-Data': telegramInitData(),
            'x-telegram-user-id': user?.id ? user.id.toString() : '',
          },
        });
        const data = await res.json();
        if (isMounted && data.ok) {
          setLeaders(data.leaders || []);
          if (data.myRanking) {
            // DIQQAT: server eski versiyalarda `amount: null` qaytarardi
            // (price yo'q bo'lgan buyurtmalar) — bu yerda crash qilib
            // butun ekranni oq qilib qoldirardi. Endi himoyalangan.
            const mr = data.myRanking;
            const amt = Number(mr.amount);
            setMyRanking({
              rank: typeof mr.rank === 'number' ? mr.rank : null,
              orders: Number(mr.orders) || 0,
              amount: Number.isFinite(amt) ? amt : 0,
              inTop10: Boolean(mr.inTop10),
            });
          }
        }
      } catch (e) {
        console.error('Failed to load ranking:', e);
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    loadRanking();
    return () => {
      isMounted = false;
    };
  // 🔴 DEP `[user]` butun obyektni oladi. `App` dagi poller har
  // 8 soniyada `setUser(data.user)` qilib obyektni QAYTA YARATADI,
  // shuning uchun reyting har 8 soniyada qayta so'ralar edi
  // (ortiqcha trafik + keraksiz qayta chizish). Faqat `id` yetarli.
  }, [user?.id, timeFilter]);

  return (
    <div className="space-y-4 max-w-md md:max-w-none md:px-6 xl:px-10 mx-auto pb-28 md:pb-10 apple-view-animate">
      {/* Header */}
      <div>
        <h2 className={`text-xl font-bold tracking-tight ${isDark ? 'text-white' : 'text-neutral-900'}`}>{t.ranking}</h2>
        <p className={`text-xs mt-0.5 ${isDark ? 'text-neutral-400' : 'text-neutral-500'}`}>{t.topBuyers}</p>
      </div>

      {(
        <>
          {/* Time filter pills */}
          <div className="flex items-center gap-1.5 overflow-x-auto scrollbar-none pb-1">
            {[
              { id: 'all', label: t.allTime },
              { id: 'today', label: t.today },
              { id: '3days', label: t.days3 },
              { id: '7days', label: t.days7 },
            ].map((f) => (
              <button
                key={f.id}
                onClick={() => switchPeriod(f.id as RankingSub)}
                className={`py-1 px-3.5 rounded-full text-xs font-semibold transition-all border apple-spring cursor-pointer ${
                  timeFilter === f.id
                    ? isDark ? 'bg-white text-black border-white' : 'bg-black text-white border-black'
                    : 'liquid-glass-pill opacity-75 hover:opacity-100'
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>

          {/* Empty State when no real purchases have been made yet */}
          {!loading && leaders.length === 0 && (
            <div className="rounded-[28px] liquid-glass-card p-6 text-center space-y-3 my-4">
              <div className="w-12 h-12 rounded-full liquid-glass mx-auto flex items-center justify-center text-amber-400 shadow-md">
                <Trophy className="w-6 h-6" />
              </div>
              <h3 className={`text-sm font-bold ${isDark ? 'text-white' : 'text-neutral-900'}`}>
                Hozircha xaridlar mavjud emas
              </h3>
              <p className={`text-xs ${isDark ? 'text-neutral-400' : 'text-neutral-600'} max-w-xs mx-auto leading-relaxed`}>
                Birinchi bo'lib xarid qiling va haftalik reytingning 1-o'rnini egallang!
              </p>
              {onGoToBuy && (
                <button
                  onClick={onGoToBuy}
                  className={`mt-2 py-3 px-5 rounded-[16px] text-xs font-bold inline-flex items-center gap-2 apple-spring cursor-pointer ${
                    isDark ? 'bg-white text-black shadow-md' : 'bg-black text-white shadow-md'
                  }`}
                >
                  <ShoppingBag className="w-4 h-4" />
                  <span>Xarid qilish</span>
                </button>
              )}
            </div>
          )}

          {/* Real Podium if at least 1 buyer exists */}
          {leaders.length > 0 && (
            <div className="pt-6 pb-2 px-2 flex items-end justify-center gap-2">
              {/* 2nd Place */}
              {leaders[1] ? (
                <div className="flex-1 flex flex-col items-center">
                  <div className="w-9 h-9 rounded-full liquid-glass-pill flex items-center justify-center font-bold text-xs shadow-md overflow-hidden">
                    {leaders[1].photo_url ? (
                      <img src={leaders[1].photo_url} alt="" className="w-full h-full object-cover" />
                    ) : (
                      '2'
                    )}
                  </div>
                  <span className={`text-[11px] font-semibold mt-1 truncate max-w-[75px] ${isDark ? 'text-white' : 'text-neutral-900'}`}>
                    {leaders[1].name}
                  </span>
                  <span className={`text-[10px] ${isDark ? 'text-neutral-400' : 'text-neutral-600'}`}>{Number(leaders[1].orders) || 0} {t.orders}</span>
                  <div className="w-full h-[88px] mt-2 rounded-t-[18px] liquid-glass flex items-center justify-center font-mono font-bold text-xs">
                    {((Number(leaders[1].amount) || 0) / 1000).toFixed(0)}K
                  </div>
                </div>
              ) : (
                <div className="flex-1" />
              )}

              {/* 1st Place (Tallest, Center) */}
              {leaders[0] && (
                /* 🔴🔴🔴 BU YERDA `-top-3` BORIDI VA U CHIQARDI!
                   `relative -top-3` butun USTUNNI (avatar + ism +
                   summa bloki) 12px KOTARARDI. Saqlanish esa
                   `items-end` — ya'ni pastki chekkalari tekislanadi.
                   Natija: 1-o'rin pastda, 2 va 3-o'rin 12px pastda
                   qolgan. O'lchildi: PASTKI_FARQ = 12px.

                   ✅ Endi hech qanday `top`/`translate` yo'q —
                   ustunlar `items-end` bilan HAQIQATAN pastki
                   chiziqdan tekislanadi. «Birinchi balandroq»
                  effekti faqat balandlik bilan beriladi. */
                <div className="flex-1 flex flex-col items-center">
                  <Crown className="w-5 h-5 text-amber-400 mb-1 drop-shadow-sm" />
                  <div className="w-11 h-11 rounded-full liquid-glass flex items-center justify-center font-bold text-sm shadow-lg ring-1 ring-amber-400/40 overflow-hidden">
                    {leaders[0].photo_url ? (
                      <img src={leaders[0].photo_url} alt="" className="w-full h-full object-cover" />
                    ) : (
                      '1'
                    )}
                  </div>
                  <span className={`text-xs font-bold mt-1 truncate max-w-[85px] ${isDark ? 'text-white' : 'text-neutral-900'}`}>
                    {leaders[0].name}
                  </span>
                  <span className={`text-[10px] ${isDark ? 'text-neutral-400' : 'text-neutral-600'}`}>{Number(leaders[0].orders) || 0} {t.orders}</span>
                  {/* 📏 Balandliklar IZCHIL qadam bilan: 72 / 88 / 104px.
                      Aks holda (70 / 101 / 55) tepa chiziqlar «arra» bo'lib
                      ko'rinar edi. Endi har bir qadam aynan 16px. */}
                  <div className="w-full h-[104px] mt-2 rounded-t-[20px] liquid-glass-card ring-1 ring-amber-400/30 flex items-center justify-center font-mono font-bold text-sm">
                    {((Number(leaders[0].amount) || 0) / 1000).toFixed(0)}K
                  </div>
                </div>
              )}

              {/* 3rd Place */}
              {leaders[2] ? (
                <div className="flex-1 flex flex-col items-center">
                  <div className="w-9 h-9 rounded-full liquid-glass-pill flex items-center justify-center font-bold text-xs shadow-md overflow-hidden">
                    {leaders[2].photo_url ? (
                      <img src={leaders[2].photo_url} alt="" className="w-full h-full object-cover" />
                    ) : (
                      '3'
                    )}
                  </div>
                  <span className={`text-[11px] font-semibold mt-1 truncate max-w-[75px] ${isDark ? 'text-white' : 'text-neutral-900'}`}>
                    {leaders[2].name}
                  </span>
                  <span className={`text-[10px] ${isDark ? 'text-neutral-400' : 'text-neutral-600'}`}>{Number(leaders[2].orders) || 0} {t.orders}</span>
                  <div className="w-full h-[72px] mt-2 rounded-t-[18px] liquid-glass flex items-center justify-center font-mono font-bold text-xs">
                    {(Number(leaders[2].amount) / 1000).toFixed(0)}K
                  </div>
                </div>
              ) : (
                <div className="flex-1" />
              )}
            </div>
          )}

          {/* Leaderboard rows 4 and above */}
          {leaders.length > 3 && (
            <div className="space-y-1.5 rounded-[26px] liquid-glass-card p-2.5">
              {leaders.slice(3).map((item) => (
                <div
                  key={item.id}
                  className={`flex items-center justify-between p-2.5 rounded-[14px] transition-colors ${
                    item.isMe ? 'bg-amber-400/10 border border-amber-400/20' : 'hover:bg-black/5 dark:hover:bg-white/5'
                  }`}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <span className={`w-5 shrink-0 text-center text-xs font-mono font-bold ${isDark ? 'text-neutral-400' : 'text-neutral-600'}`}>
                      #{item.rank}
                    </span>
                    <div className="w-7 h-7 shrink-0 rounded-full overflow-hidden liquid-glass-pill">
                      {item.photo_url ? (
                        <img src={item.photo_url} alt="" className="w-full h-full object-cover" />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center font-bold text-[10px]">
                          {item.name.charAt(0).toUpperCase()}
                        </div>
                      )}
                    </div>
                    {/* 📌 `min-w-0` + `truncate` — uzun ism summani surib
                        yubormasdi. Pinned karta ham shu qoidada. */}
                    <div className="min-w-0">
                      <h4 className={`text-xs font-semibold truncate ${isDark ? 'text-white' : 'text-neutral-900'}`}>{item.name}</h4>
                      <span className={`text-[10px] ${isDark ? 'text-neutral-400' : 'text-neutral-600'}`}>{item.orders} {t.orders}</span>
                    </div>
                  </div>
                  <div className={`shrink-0 text-xs font-mono font-bold ${isDark ? 'text-white' : 'text-neutral-900'}`}>
                    {(fmtUzs(Number(item.amount) || 0))}{' '}
                    <span className="text-[9px] font-normal opacity-70">UZS</span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* User's Place Pinned Real Card
              🔴🔴🔴 MIJOZ: «ikkalasi bir biriga to'g'ri kelmayapti».

              📐 SABAB: bu karta ro'yxat qatorlaridan BUTUNLAY boshqa
              tuzilishda edi:
                • tashqi kartada `p-2.5`, ichida `p-2.5`  → avatar 20px
                • bu kartada `p-3.5`                        → avatar 14px
                • ro'yxat avatari `w-7 h-7`, bu yerda `w-9 h-9`
                • ro'yxatda `gap-3`, bu yerda `gap-2.5`
              Natija: karta pastda turgan edi, lekin avatar va summa
              qatorlarning ustki qatorlari bilan BIR CHIZIQDA turmardi.

              ✅ Endi qator STRUKTURASI bit-tik nusxalangan:
                kartaning ichi aynan `leaders.slice(3)` qatori kabi
                quriladi (p-2.5 + p-2.5 + w-5 + w-7 + gap-3).
                Shuning uchun avatar, ism va summa ustma-ust tushadi. */}
          <div className="rounded-[26px] liquid-glass-card p-2.5">
            <div className="flex items-center justify-between gap-3 p-2.5 rounded-[14px] bg-amber-400/10 border border-amber-400/20">
              <div className="flex items-center gap-3 min-w-0">
                {/* O'rin raqami — ro'yxatdagi `#` kabi kenglikda */}
                <span className="w-5 shrink-0 text-center text-xs font-mono font-bold text-amber-500">
                  {myRanking.rank ? `#${myRanking.rank}` : '—'}
                </span>
                <div className="w-7 h-7 shrink-0 rounded-full overflow-hidden liquid-glass-pill">
                  {user?.photo_url ? (
                    <img
                      src={user.photo_url}
                      alt={user.username || 'User'}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full rounded-full flex items-center justify-center font-bold text-[10px]">
                      {user?.username ? user.username.charAt(0).toUpperCase() : 'U'}
                    </div>
                  )}
                </div>
                {/* 📌 `min-w-0` + `truncate` — uzun ism BALANSSNI
                    chapga surib yubormasdi (karta torayardi). */}
                <div className="min-w-0">
                  <h4 className={`text-xs font-semibold truncate ${isDark ? 'text-white' : 'text-neutral-900'}`}>
                    {t.yourPlace}
                  </h4>
                  <span className="text-[10px] text-amber-500">
                    {myRanking.inTop10 ? t.top10 : `${myRanking.orders} ${t.orders}`}
                  </span>
                </div>
              </div>
              {/* 📌 `shrink-0` — summa hech qachon siqilmasdi */}
              <div className={`shrink-0 text-xs font-mono font-bold ${isDark ? 'text-white' : 'text-neutral-900'}`}>
                {fmtUzs(myRanking.amount)}{' '}
                <span className="text-[9px] font-normal opacity-70">UZS</span>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
