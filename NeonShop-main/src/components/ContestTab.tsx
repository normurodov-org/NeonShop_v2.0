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
  const isEligible = userSpent >= contest.min;
  const isJoined = contest.joined;

  const handleJoin = async () => {
    setError(null);
    setLoading(true);
    try {
      const res = await fetch('/api/contest/join', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      const data = await res.json();
      if (!data.ok) {
        throw new Error(data.error || "Xatolik yuz berdi");
      }
      onJoinSuccess(data.message);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

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
              <h2 className="text-xl font-black text-white mt-1">
                Bahorgi Katta Stars Konkursi
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
            <div className="text-xl font-black text-purple-400 mt-1">{contest.min.toLocaleString()} UZS</div>
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
                Konkursda qatnashish uchun kamida <b>{contest.min.toLocaleString()} UZS</b> xarid qilishingiz kerak.
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
