import React, { useState, useEffect } from 'react';
import { User, Contest } from '../../types';
import { Lang, translations } from '../../i18n';
import { Trophy, Crown, Sparkles, Clock, ShoppingBag } from 'lucide-react';

interface RankingViewProps {
  user: User | null;
  contest: Contest | null;
  lang: Lang;
  isDark: boolean;
  onGoToBuy?: () => void;
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

export const RankingView: React.FC<RankingViewProps> = ({ user, contest, lang, isDark, onGoToBuy }) => {
  const t = translations[lang];
  const [viewMode, setViewMode] = useState<'ranking' | 'contest'>('ranking');
  const [timeFilter, setTimeFilter] = useState<'all' | 'today' | '3days' | '7days'>('all');

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
            'x-telegram-user-id': user?.id ? user.id.toString() : '',
          },
        });
        const data = await res.json();
        if (isMounted && data.ok) {
          setLeaders(data.leaders || []);
          if (data.myRanking) {
            setMyRanking(data.myRanking);
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
  }, [user, timeFilter]);

  return (
    <div className="space-y-4 max-w-md mx-auto pb-28 apple-view-animate">
      {/* Header */}
      <div>
        <h2 className={`text-xl font-bold tracking-tight ${isDark ? 'text-white' : 'text-neutral-900'}`}>{t.ranking}</h2>
        <p className={`text-xs mt-0.5 ${isDark ? 'text-neutral-400' : 'text-neutral-500'}`}>{t.topBuyers}</p>
      </div>

      {/* Contest vs Ranking switch (Apple Segmented Style) */}
      <div className="flex items-center gap-1 p-1 rounded-full liquid-glass">
        <button
          onClick={() => setViewMode('contest')}
          className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-full text-xs font-semibold transition-all cursor-pointer apple-spring ${
            viewMode === 'contest'
              ? isDark ? 'bg-white text-black shadow-md' : 'bg-black text-white shadow-md'
              : isDark ? 'text-neutral-400 hover:text-white' : 'text-neutral-600 hover:text-black'
          }`}
        >
          <Trophy className="w-3.5 h-3.5" />
          <span>{t.contest}</span>
        </button>

        <button
          onClick={() => setViewMode('ranking')}
          className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-full text-xs font-semibold transition-all cursor-pointer apple-spring ${
            viewMode === 'ranking'
              ? isDark ? 'bg-white text-black shadow-md' : 'bg-black text-white shadow-md'
              : isDark ? 'text-neutral-400 hover:text-white' : 'text-neutral-600 hover:text-black'
          }`}
        >
          <Sparkles className="w-3.5 h-3.5" />
          <span>{t.ranking}</span>
        </button>
      </div>

      {viewMode === 'contest' && contest && (
        <div className="rounded-[28px] liquid-glass-card p-5 space-y-4">
          <div className="flex items-center justify-between">
            <span className="px-3 py-1 rounded-full text-[11px] font-bold liquid-glass-pill">
              {contest.prize_stars} ⭐ SOVRIN
            </span>
            <span className="text-xs font-mono text-neutral-400 flex items-center gap-1">
              <Clock className="w-3.5 h-3.5" />
              <span>3 kun qoldi</span>
            </span>
          </div>

          <h3 className={`text-sm font-semibold leading-relaxed ${isDark ? 'text-white' : 'text-neutral-900'}`}>
            {contest.text.replace(/<[^>]*>?/gm, '')}
          </h3>

          <div className={`p-4 rounded-[18px] space-y-2 text-xs ${isDark ? 'bg-black/30' : 'bg-white/60'} border border-white/10`}>
            <div className="flex justify-between text-neutral-400">
              <span>G'oliblar soni:</span>
              <b className={isDark ? 'text-white' : 'text-neutral-900'}>{contest.winners} ta</b>
            </div>
            <div className="flex justify-between text-neutral-400">
              <span>Qatnashuvchilar:</span>
              <b className={isDark ? 'text-white' : 'text-neutral-900'}>{contest.participants} kishi</b>
            </div>
            <div className="flex justify-between text-neutral-400">
              <span>Holat:</span>
              <b className="text-emerald-500 font-bold">Faol qatnashyapsiz</b>
            </div>
          </div>
        </div>
      )}

      {viewMode === 'ranking' && (
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
                onClick={() => setTimeFilter(f.id as any)}
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
              <p className="text-xs text-neutral-400 max-w-xs mx-auto leading-relaxed">
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
                  <span className="text-[10px] text-neutral-400">{leaders[1].orders} {t.orders}</span>
                  <div className="w-full h-18 mt-2 rounded-t-[18px] liquid-glass flex items-center justify-center font-mono font-bold text-xs">
                    {(leaders[1].amount / 1000).toFixed(0)}K
                  </div>
                </div>
              ) : (
                <div className="flex-1" />
              )}

              {/* 1st Place (Tallest, Center) */}
              {leaders[0] && (
                <div className="flex-1 flex flex-col items-center relative -top-3">
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
                  <span className="text-[10px] text-neutral-400">{leaders[0].orders} {t.orders}</span>
                  <div className="w-full h-26 mt-2 rounded-t-[20px] liquid-glass-card flex items-center justify-center font-mono font-bold text-sm">
                    {(leaders[0].amount / 1000).toFixed(0)}K
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
                  <span className="text-[10px] text-neutral-400">{leaders[2].orders} {t.orders}</span>
                  <div className="w-full h-14 mt-2 rounded-t-[18px] liquid-glass flex items-center justify-center font-mono font-bold text-xs">
                    {(leaders[2].amount / 1000).toFixed(0)}K
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
                  <div className="flex items-center gap-3">
                    <span className="w-5 text-center text-xs font-mono font-bold text-neutral-400">
                      #{item.rank}
                    </span>
                    <div className="w-7 h-7 rounded-full overflow-hidden liquid-glass-pill shrink-0">
                      {item.photo_url ? (
                        <img src={item.photo_url} alt="" className="w-full h-full object-cover" />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center font-bold text-[10px]">
                          {item.name.charAt(0).toUpperCase()}
                        </div>
                      )}
                    </div>
                    <div>
                      <h4 className={`text-xs font-semibold ${isDark ? 'text-white' : 'text-neutral-900'}`}>{item.name}</h4>
                      <span className="text-[10px] text-neutral-400">{item.orders} {t.orders}</span>
                    </div>
                  </div>
                  <div className={`text-xs font-mono font-bold ${isDark ? 'text-white' : 'text-neutral-900'}`}>
                    {item.amount.toLocaleString()} <span className="text-[9px] font-normal opacity-70">UZS</span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* User's Place Pinned Real Card */}
          <div className="rounded-[22px] liquid-glass-card p-3.5 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-full p-[1.5px] overflow-hidden liquid-glass-pill shrink-0">
                {user?.photo_url ? (
                  <img
                    src={user.photo_url}
                    alt={user.username || 'User'}
                    className="w-full h-full rounded-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full rounded-full flex items-center justify-center font-bold text-xs">
                    {user?.username ? user.username.charAt(0).toUpperCase() : 'U'}
                  </div>
                )}
              </div>
              <div>
                <div className="text-[10px] text-neutral-400 font-medium">
                  {t.yourPlace}: <b className={isDark ? 'text-white' : 'text-neutral-900'}>
                    {myRanking.rank ? `#${myRanking.rank}` : "Hali xarid yo'q"}
                  </b>
                </div>
                <div className="text-xs font-semibold text-amber-500">
                  {myRanking.inTop10 ? t.top10 : `${myRanking.orders} ta xarid`}
                </div>
              </div>
            </div>
            <div className="text-right">
              <div className={`text-xs font-mono font-bold ${isDark ? 'text-white' : 'text-neutral-900'}`}>
                {myRanking.amount.toLocaleString()} <span className="text-[9px] font-normal opacity-70">UZS</span>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
