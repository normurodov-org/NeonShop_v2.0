import React from 'react';
import { Order } from '../types';
import { Clock, CheckCircle2, AlertCircle, ShoppingBag, Star, Gift, Sparkles } from 'lucide-react';

interface HistoryTabProps {
  orders: Order[];
}

export const HistoryTab: React.FC<HistoryTabProps> = ({ orders }) => {
  if (orders.length === 0) {
    return (
      <div className="rounded-3xl bg-slate-900/60 border border-white/10 p-12 text-center space-y-3">
        <div className="w-14 h-14 mx-auto rounded-2xl bg-slate-800/80 flex items-center justify-center text-slate-400">
          <ShoppingBag className="w-6 h-6" />
        </div>
        <h3 className="text-base font-bold text-white">Hozircha buyurtmalar yo'q</h3>
        <p className="text-xs text-slate-400 max-w-sm mx-auto">
          Stars, Premium yoki Sovg'alarga buyurtma bersangiz, barcha buyurtmalar va yetkazib berish holati shu yerda ko'rinadi.
        </p>
      </div>
    );
  }

  const getIcon = (kind: string) => {
    switch (kind) {
      case 'stars':
        return <Star className="w-5 h-5 text-amber-400 fill-amber-400" />;
      case 'premium':
        return <Sparkles className="w-5 h-5 text-purple-400" />;
      case 'gift':
        return <Gift className="w-5 h-5 text-pink-400" />;
      default:
        return <ShoppingBag className="w-5 h-5 text-cyan-400" />;
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between px-1">
        <h3 className="text-sm font-bold text-white flex items-center gap-2">
          <span>Xaridlar tarixi</span>
          <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 font-normal">
            {orders.length} ta buyurtma
          </span>
        </h3>
      </div>

      <div className="space-y-2.5">
        {orders.map((order) => {
          const dateStr = new Date(order.created_at).toLocaleString('uz-UZ', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
          });

          return (
            <div
              key={order.id}
              className="rounded-2xl bg-slate-900/80 border border-white/10 p-4 hover:border-white/20 transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-3"
            >
              <div className="flex items-center gap-3.5">
                <div className="w-11 h-11 rounded-xl bg-slate-950 flex items-center justify-center shrink-0 border border-white/5">
                  {getIcon(order.kind)}
                </div>
                <div>
                  <div className="text-sm font-bold text-white">{order.title}</div>
                  <div className="flex items-center gap-2 text-xs text-slate-400 mt-0.5">
                    <span>Qabul qiluvchi: <b className="text-slate-300">@{order.recipient}</b></span>
                    <span>•</span>
                    <span>{dateStr}</span>
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between sm:justify-end gap-4 border-t sm:border-t-0 pt-2 sm:pt-0 border-white/5">
                <div className="text-left sm:text-right">
                  <div className="text-sm font-extrabold text-cyan-400">
                    {order.price.toLocaleString()} <span className="text-[10px] text-slate-400">UZS</span>
                  </div>
                  <div className="text-[10px] font-mono text-slate-500">ID: {order.id}</div>
                </div>

                <div className="flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Bajarildi</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
