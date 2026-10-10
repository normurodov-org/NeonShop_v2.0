import React, { useState } from 'react';
import { User, Contest } from '../types';
import { Trophy, Users, Clock, CheckCircle2, AlertCircle, Sparkles } from 'lucide-react';

interface ContestTabProps {
  user: User | null;
  contest: Contest | null;
  onJoinSuccess: (msg: string) => void;
  onOpenTopup: () => void;
}

export const ContestTab: React.FC<ContestTabProps> = ({
  user,
  contest,
  onJoinSuccess,
  onOpenTopup,
}) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!contest) return null;

  const userSpent = user?.total_spent || 0;
  const isEligible = userSpent >= (contest.min || 0);
  const isJoined = contest.joined;
  const isActive = Boolean(contest.active) && (contest.prize_stars || 0) > 0;

  const handleJoin = async () => {
    setError(null);
    setLoading(true);
    try {
      const res = await fetch('/api/contest/join', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-telegram-user-id': user?.id?.toString() || '',
        },
      });
      const data = await res.json();
      if (!data.ok) {
        throw new Error(data.error || 'Xatolik yuz berdi');
      }
      onJoinSuccess(data.message);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Hali konkurs yaratilmagan — chiroyli "yo'q" holati
  if (!isActive) {
    return (
      <div className="space-y-4">
        <div className="relative overflow-hidden rounded-3xl liquid-glass-card p-8 text-center space-y-4">
          <div className="w-16 h-16 mx-auto rounded-2xl liquid-glass-pill flex items-center justify-center text-3xl">
            🎁
          </div>
          <h2 className="text-lg font-black">Hali konkurs yo'q</h2>
          <p className="text-xs text-neutral-400 leading-relaxed max-w-xs mx-auto">
            Keyingi konkurs tez orada e'lon qilinadi. Bu yerga kirib turishni davom ettiring —
            birinchi bo'lib qo'shilsangiz, sovg'a yutish shansingiz katta!
          </p>
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full liquid-glass-pill text-[11px] font-semibold text-neutral-300">
            <Sparkles className="w-3.5 h-3.5 text-amber-400" />
            E'lon qilinsa xabar beramiz
          </div>
          <button
            onClick={onOpenTopup}
            className="w-full py-3.5 rounded-2xl apple-spring cursor-pointer font-bold text-xs flex items-center justify-center gap-2 liquid-glass-pill"
          >
            <span>Xarid qilib ball to'plash</span>
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Contest Hero Banner */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-purple-900/40 via-indigo-900/30 to-slate-900 border border-purple-500/30 p-6 md:p-8 space-y-6 shadow-2xl">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="w-14 h-14 rounded-2xl bg-purple-500/20 border border-purple-500/40 flex items-center justify-center text-purple-300 text-3xl shrink-0 shadow-lg shadow-purple-500/20">
              🏆
            </div>
            <div>
              <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/30">
                Faol Konkurs
              </span>
              <h2 className="text-xl font-black text-white mt-1 leading-tight">
                {contest.text?.replace(/<[^>]+>/g, '') || 'Konkurs'}
              </h2>
            </div>
          </div>

          <div className="flex items-center gap-2 self-start sm:self-center">
            <div className="px-3.5 py-1.5 rounded-xl bg-purple-950/80 border border-purple-500/30 text-purple-200 text-xs font-bold flex items-center gap-1.5">
              <Sparkles className="w-4 h-4 text-purple-400" />
              <span>{contest.prize_stars} ⭐ Sovrin</span>
            </div>
          </div>
        </div>

        {/* Contest Details */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
          <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-white/10">
            <div className="text-[10px] uppercase font-bold text-slate-400">G'oliblar</div>
            <div className="text-xl font-black text-amber-400 mt-1">{contest.winners} nafar</div>
          </div>
          <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-white/10">
            <div className="text-[10px] uppercase font-bold text-slate-400">Ishtirokchilar</div>
            <div className="text-xl font-black text-cyan-400 mt-1">{contest.participants} ta</div>
          </div>
          <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-white/10">
            <div className="text-[10px] uppercase font-bold text-slate-400">Min. Xarid</div>
            <div className="text-xl font-black text-purple-400 mt-1">{(contest.min || 0).toLocaleString()} UZS</div>
          </div>
          <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-white/10">
            <div className="text-[10px] uppercase font-bold text-slate-400">Sizning xaridingiz</div>
            <div className="text-xl font-black text-white mt-1">{userSpent.toLocaleString()} UZS</div>
          </div>
        </div>

        {/* Status & CTA */}
        {error && (
          <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div className="pt-2">
          {isJoined ? (
            <div className="w-full py-4 rounded-2xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 font-bold text-sm flex items-center justify-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-emerald-400" />
              <span>Siz konkurs ishtirokchisisiz! Omadingizni tilaymiz 🍀</span>
            </div>
          ) : isEligible ? (
            <button
              onClick={handleJoin}
              disabled={loading}
              className="w-full py-4 rounded-2xl bg-gradient-to-r from-purple-600 via-indigo-600 to-cyan-500 hover:from-purple-500 hover:to-cyan-400 text-white font-black text-sm shadow-xl shadow-purple-900/40 active:scale-[0.99] transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
            >
              <Trophy className="w-5 h-5 text-amber-300" />
              <span>{loading ? "Qo'shilmoqda..." : "Konkursda qatnashish (Bepul)"}</span>
            </button>
          ) : (
            <div className="space-y-3">
              <div className="text-xs text-slate-400 text-center">
                Konkursda qatnashish uchun kamida <b>{(contest.min || 0).toLocaleString()} UZS</b> xarid qilishingiz kerak.
                Hozirgi xaridingiz: <b>{userSpent.toLocaleString()} UZS</b>.
              </div>
              <button
                onClick={onOpenTopup}
                className="w-full py-3.5 rounded-2xl bg-slate-800 hover:bg-slate-700 text-white font-bold text-sm flex items-center justify-center gap-2 transition-all cursor-pointer"
              >
                <span>Xarid qilish uchun balansni to'ldirish</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
