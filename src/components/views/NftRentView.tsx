import React, { useEffect, useState } from 'react';
import { Boxes, Heart, ChevronDown, SlidersHorizontal, X, Minus, Plus } from 'lucide-react';

interface NftItem {
  id: string;
  title: string;
  number: number | null;
  image: string;
  link: string;
  daily: number;
}

interface Quote {
  days: number;
  per_day: number;
  rent: number;
  network_fee: number;
  total: number;
}

interface NftProps {
  isDark: boolean;
  /** Telegram foydalanuvchi ID — balans uchun */
  userId?: number;
  balance?: number;
  onGoToTopup: () => void;
  /** Buyurtma yuborilganda chaqiriladi (toast + tab yopish) */
  onRented?: (msg: string, newBalance?: number) => void;
}

const TABS = [
  { id: 'gifts', label: 'Gifts' },
  { id: 'usernames', label: 'Usernames' },
  { id: 'mine', label: 'My rentals' },
] as const;

type TabId = (typeof TABS)[number]['id'];

const BACKDROPS = ['All backdrops', 'Battleship Grey', 'Black', 'Onyx Black', 'Gold'];
const COLLECTIONS = ['All collections', 'Regular gifts', 'Upgrades', 'Unique'];

const fmt = (n: number) => Number(n || 0).toLocaleString('uz-UZ').replace(/,/g, ' ');

/**
 * Rasm manzilini tekshiradi.
 *
 * DIQQAT: server endi rasmlarni ikki xil ko'rinishda beradi:
 *   • to'g'ridan-to'g'ri havolа (https://...) — admin link yuborgan
 *   • nisbiy proxy yo'l (/api/nft-image/<id>) — admin RASM yuborgan
 *     (Telegram file_id brauzerda ochilmaydi, shuning uchun proxy orqali)
 * Eski kod faqat `^https?://` ni qabul qilardi va proxy rasmni
 * YASHIRIB qo'yardi — shuning uchun NFT rasm chiqmay qolgan.
 */
const isImageUrl = (v?: string): boolean => {
  if (!v) return false;
  return /^https?:\/\//i.test(v) || v.startsWith('/');
};

export const NftRentView: React.FC<NftProps> = ({
  isDark,
  userId,
  balance = 0,
  onGoToTopup,
  onRented,
}) => {
  const [items, setItems] = useState<NftItem[]>([]);
  const [minDays, setMinDays] = useState(3);
  const [maxDays, setMaxDays] = useState(50);
  const [quick, setQuick] = useState<number[]>([3, 7, 14, 30]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<TabId>('gifts');
  const [sort, setSort] = useState<'cheap' | 'big'>('cheap');
  const [backdrop, setBackdrop] = useState('All backdrops');
  const [collection, setCollection] = useState('All collections');
  const [fav, setFav] = useState<Record<string, boolean>>({});

  // Modal
  const [sel, setSel] = useState<NftItem | null>(null);
  const [days, setDays] = useState(3);
  const [quote, setQuote] = useState<Quote | null>(null);
  const [qLoading, setQLoading] = useState(false);
  const [renting, setRenting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = async () => {
    try {
      const r = await fetch('/api/nfts', {
        headers: { 'x-telegram-user-id': userId?.toString() || '' },
      });
      const d = await r.json();
      if (d.ok) {
        setItems(d.items || []);
        setMinDays(d.min_days ?? 3);
        setMaxDays(d.max_days ?? 50);
        setNetworkFee(d.network_fee ?? 1700);
        if (Array.isArray(d.quick_days) && d.quick_days.length) {
          setQuick(d.quick_days);
        }
      }
    } catch {
      /* xato bo'lsa bo'sh ro'yxat */
    } finally {
      setLoading(false);
    }
  };

  const [networkFee, setNetworkFee] = useState(1700);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId]);

  // Tanlangan NFT uchun hisobni serverdan olamiz (bitta manba)
  const loadQuote = async (item: NftItem, d: number) => {
    setQLoading(true);
    try {
      const r = await fetch(`/api/nfts/quote?id=${encodeURIComponent(item.id)}&days=${d}`, {
        headers: { 'x-telegram-user-id': userId?.toString() || '' },
      });
      const j = await r.json();
      if (j.ok) {
        setQuote(j.quote);
        if (typeof j.balance === 'number') onBalance?.(j.balance);
      } else {
        // serverga ulanmagan bo'lsa — hisobni mijoz tomonda qilamiz
        const dd = Math.max(minDays, Math.min(maxDays, d));
        setQuote({
          days: dd,
          per_day: item.daily,
          rent: item.daily * dd,
          network_fee: networkFee,
          total: item.daily * dd + networkFee,
        });
      }
    } catch {
      const dd = Math.max(minDays, Math.min(maxDays, d));
      setQuote({
        days: dd,
        per_day: item.daily,
        rent: item.daily * dd,
        network_fee: networkFee,
        total: item.daily * dd + networkFee,
      });
    } finally {
      setQLoading(false);
    }
  };

  const [, setLiveBalance] = useState(balance);
  const onBalance = (b: number) => setLiveBalance(b);

  /** "Sotib olish" — buyurtma yaratadi va menejer/adminga xabar boradi. */
  const rent = async () => {
    if (!sel || !quote || renting) return;
    setRenting(true);
    setErr(null);
    try {
      const r = await fetch('/api/nfts/rent', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-telegram-user-id': userId?.toString() || '',
        },
        body: JSON.stringify({ id: sel.id, days: quote.days }),
      });
      const j = await r.json();
      if (!j.ok) {
        // Balans yetarli emas -> to'ldirishga yo'naltiramiz
        if (j.need_topup || r.status === 402) {
          setErr(j.error || 'Balans yetarli emas');
          onGoToTopup();
        } else {
          setErr(j.error || 'Xatolik yuz berdi');
        }
        return;
      }
      onBalance(Number(j.balance) || 0);
      onRented?.(j.message || 'NFT ijaraga olish so&apos;rovi yuborildi', Number(j.balance) || 0);
      setSel(null);
      load();
    } catch {
      setErr('Server bilan bog‘lanib bo‘lmadi');
    } finally {
      setRenting(false);
    }
  };

  const open = (item: NftItem) => {
    setSel(item);
    setErr(null);
    setDays(minDays);
    loadQuote(item, minDays);
  };

  const setD = (d: number) => {
    const v = Math.max(minDays, Math.min(maxDays, d));
    setDays(v);
    if (sel) loadQuote(sel, v);
  };

  const shown = [...items].sort((a, b) =>
    sort === 'cheap' ? a.daily - b.daily : b.daily - a.daily
  );

  const insufficient = quote ? quote.total > balance : false;

  const chip = (active: boolean) =>
    `shrink-0 px-4 py-2.5 rounded-full text-[13px] font-semibold whitespace-nowrap
     apple-spring cursor-pointer transition-colors
     ${active
       ? 'bg-[var(--accent)] text-white font-bold'
       : isDark
         ? 'bg-white/[0.06] text-neutral-300 border border-white/10'
         : 'bg-black/[0.04] text-neutral-700 border border-black/[0.06]'}`;

  return (
    <div className="space-y-4">
      {/* Tabs */}
      <div
        className={`flex items-center gap-1.5 p-1.5 rounded-[22px] liquid-glass overflow-x-auto ${
          isDark ? '' : ''
        }`}
      >
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex-1 min-w-fit px-4 py-2.5 rounded-[18px] text-[13px] font-bold
                        apple-spring cursor-pointer transition-all whitespace-nowrap ${
              tab === t.id
                ? isDark
                  ? 'bg-white text-black'
                  : 'bg-[var(--accent)] text-white'
                : isDark
                  ? 'text-neutral-400'
                  : 'text-neutral-600'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab !== 'gifts' ? (
        <div
          className={`rounded-[24px] liquid-glass-card p-10 text-center space-y-2 ${
            isDark ? 'text-neutral-400' : 'text-neutral-500'
          }`}
        >
          <Boxes className="w-9 h-9 mx-auto opacity-40" />
          <div className="text-sm font-bold">
            {tab === 'usernames' ? 'Usernames' : 'My rentals'}
          </div>
          <div className="text-xs">Hozircha bo&apos;sh</div>
        </div>
      ) : (
        <>
          {/* Filtrlar */}
          <div className="flex items-center gap-2 overflow-x-auto pb-1 -mx-4 px-4">
            <button onClick={() => setCollection(collection)} className={chip(false)}>
              <span className="flex items-center gap-2">
                {collection} <ChevronDown className="w-3.5 h-3.5" />
              </span>
            </button>
            <button
              onClick={() => setSort(sort === 'cheap' ? 'big' : 'cheap')}
              className={chip(false)}
            >
              <span className="flex items-center gap-2">
                {sort === 'cheap' ? 'Cheapest first' : 'Most expensive'}{' '}
                <ChevronDown className="w-3.5 h-3.5" />
              </span>
            </button>
            <button className={chip(false)} aria-label="Tanlanganlar">
              <Heart className={`w-4 h-4 ${Object.values(fav).some(Boolean) ? 'fill-current' : ''}`} />
            </button>
            <SlidersHorizontal className="w-4 h-4 opacity-40 shrink-0 self-center" />
          </div>

          {/* Backdrop filtrlari */}
          <div className="flex items-center gap-2 overflow-x-auto pb-1 -mx-4 px-4">
            {BACKDROPS.map((b) => (
              <button
                key={b}
                onClick={() => setBackdrop(b)}
                className={chip(backdrop === b)}
              >
                {b}
              </button>
            ))}
          </div>

          {/* Kartalar */}
          {loading ? (
            <div className="text-center py-10 text-xs opacity-50">Yuklanmoqda…</div>
          ) : shown.length === 0 ? (
            <div
              className={`rounded-[24px] liquid-glass-card p-10 text-center space-y-2 ${
                isDark ? 'text-neutral-400' : 'text-neutral-500'
              }`}
            >
              <Boxes className="w-9 h-9 mx-auto opacity-40" />
              <div className="text-sm font-bold">Hozircha NFT yo&apos;q</div>
              <div className="text-xs">
                Admin panel orqali qo&apos;shiladi: /admin → ➕ NFT qo&apos;shish
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-3">
              {shown.map((n) => (
                <button
                  key={n.id}
                  onClick={() => open(n)}
                  className={`text-left rounded-[24px] overflow-hidden liquid-glass apple-spring
                              apple-view-animate cursor-pointer group`}
                >
                  <div className="relative aspect-square overflow-hidden">
                    {isImageUrl(n.image) ? (
                      <img
                        src={n.image}
                        alt={n.title}
                        loading="lazy"
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                      />
                    ) : (
                      <div
                        className={`w-full h-full flex items-center justify-center ${
                          isDark ? 'bg-white/[0.04]' : 'bg-black/[0.03]'
                        }`}
                      >
                        <Boxes className="w-9 h-9 opacity-30" />
                      </div>
                    )}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setFav((f) => ({ ...f, [n.id]: !f[n.id] }));
                      }}
                      className={`absolute top-2 right-2 w-8 h-8 rounded-full flex items-center
                                  justify-center backdrop-blur-md apple-spring cursor-pointer
                                  ${fav[n.id] ? 'bg-[var(--accent)]' : 'bg-black/45 text-white'}`}
                      aria-label="Tanlangan"
                    >
                      <Heart className={`w-4 h-4 ${fav[n.id] ? 'fill-white' : ''}`} />
                    </button>
                  </div>
                  <div className={`p-3 ${isDark ? 'bg-black/40' : 'bg-white/60'}`}>
                    <div
                      className={`text-[13px] font-bold truncate ${
                        isDark ? 'text-white' : 'text-neutral-900'
                      }`}
                    >
                      {n.title}
                    </div>
                    {n.number != null && (
                      <div
                        className={`text-[11px] opacity-60 mt-0.5 ${
                          isDark ? 'text-neutral-300' : 'text-neutral-600'
                        }`}
                      >
                        #{n.number}
                      </div>
                    )}
                    <div className="mt-1.5 flex items-baseline gap-1">
                      <span
                        className={`text-[15px] font-black ${
                          isDark ? 'text-white' : 'text-neutral-900'
                        }`}
                      >
                        {fmt(n.daily)} UZS
                      </span>
                      <span className="text-[10px] opacity-60">per day</span>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </>
      )}

      {/* MODAL — muddat va hisob */}
      {sel && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setSel(null)}
          />
          <div
            className={`relative w-full sm:max-w-md rounded-t-[32px] sm:rounded-[32px]
                        liquid-glass-card p-5 space-y-4 max-h-[92vh] overflow-y-auto
                        apple-view-animate`}
          >
            {/* Sarlavha */}
            <div className="flex items-center gap-3">
              <div
                className={`w-16 h-16 rounded-[18px] overflow-hidden shrink-0 ${
                  isDark ? 'bg-white/[0.06]' : 'bg-black/[0.04]'
                }`}
              >
                {isImageUrl(sel.image) ? (
                  <img src={sel.image} alt="" className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center">
                    <Boxes className="w-6 h-6 opacity-30" />
                  </div>
                )}
              </div>
              <div className="flex-1 min-w-0">
                <div
                  className={`text-[15px] font-black truncate ${
                    isDark ? 'text-white' : 'text-neutral-900'
                  }`}
                >
                  {sel.title}
                  {sel.number != null ? ` #${sel.number}` : ''}
                </div>
                <div className={`text-[11px] opacity-60 ${isDark ? 'text-neutral-400' : 'text-neutral-500'}`}>
                  Ijara muddati: {minDays}–{maxDays} kun
                </div>
              </div>
              <button
                onClick={() => setSel(null)}
                className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0
                            ${isDark ? 'bg-white/10 text-white' : 'bg-black/5 text-neutral-700'}`}
                aria-label="Yopish"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Muddat */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className={`text-[13px] font-bold ${isDark ? 'text-white' : 'text-neutral-900'}`}>
                  Term
                </span>
                <span className={`text-[12px] ${isDark ? 'text-neutral-400' : 'text-neutral-500'}`}>
                  {minDays}–{maxDays} days
                </span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setD(days - 1)}
                  disabled={days <= minDays}
                  className={`w-14 h-14 rounded-[20px] flex items-center justify-center
                              disabled:opacity-30 apple-spring cursor-pointer
                              ${isDark ? 'bg-white/[0.06] text-white' : 'bg-black/[0.04] text-neutral-900'}`}
                  aria-label="Kamaytirish"
                >
                  <Minus className="w-5 h-5" />
                </button>
                <input
                  type="number"
                  value={days}
                  min={minDays}
                  max={maxDays}
                  onChange={(e) => setD(Number(e.target.value))}
                  className={`flex-1 h-14 rounded-[20px] text-center text-[20px] font-black
                              apple-spring focus:outline-none
                              ${isDark ? 'bg-white/[0.06] text-white' : 'bg-black/[0.04] text-neutral-900'}`}
                />
                <button
                  onClick={() => setD(days + 1)}
                  disabled={days >= maxDays}
                  className={`w-14 h-14 rounded-[20px] flex items-center justify-center
                              disabled:opacity-30 apple-spring cursor-pointer
                              ${isDark ? 'bg-white/[0.06] text-white' : 'bg-black/[0.04] text-neutral-900'}`}
                  aria-label="Ko'paytirish"
                >
                  <Plus className="w-5 h-5" />
                </button>
              </div>
              <div className="flex items-center gap-2">
                {quick.map((d) => (
                  <button
                    key={d}
                    onClick={() => setD(d)}
                    className={`flex-1 py-2.5 rounded-full text-[12px] font-bold apple-spring cursor-pointer
                                ${days === d
                                  ? 'bg-[var(--accent)] text-white'
                                  : isDark
                                    ? 'bg-white/[0.06] text-neutral-300'
                                    : 'bg-black/[0.04] text-neutral-600'}`}
                  >
                    {d} days
                  </button>
                ))}
              </div>
            </div>

            {/* Hisob */}
            <div
              className={`rounded-[24px] p-4 space-y-2 ${
                isDark ? 'bg-white/[0.05]' : 'bg-black/[0.03]'
              }`}
            >
              <Row label="Per day" value={`${fmt(quote?.per_day ?? sel.daily)} UZS`} dark={isDark} />
              <Row
                label={`Rent (${quote?.days ?? days} days)`}
                value={`${fmt(quote?.rent ?? 0)} UZS`}
                dark={isDark}
              />
              <Row
                label="Network fee"
                value={`${fmt(quote?.network_fee ?? networkFee)} UZS`}
                dark={isDark}
              />
              <div className={`h-px ${isDark ? 'bg-white/10' : 'bg-black/10'}`} />
              <div className="flex items-center justify-between pt-1">
                <span className={`text-[14px] font-black ${isDark ? 'text-white' : 'text-neutral-900'}`}>
                  Total
                </span>
                <span className="text-[16px] font-black text-[var(--accent)]">
                  {fmt(quote?.total ?? 0)} UZS
                </span>
              </div>
              <div className="flex items-center justify-between pt-1">
                <span className={`text-[12px] ${isDark ? 'text-neutral-400' : 'text-neutral-500'}`}>
                  Balance
                </span>
                <span
                  className={`text-[12px] font-bold ${
                    insufficient ? 'text-red-500' : isDark ? 'text-neutral-300' : 'text-neutral-600'
                  }`}
                >
                  {fmt(balance)} UZS{insufficient ? ' · not enough' : ''}
                </span>
              </div>
            </div>

            {err && (
              <div className="rounded-[18px] bg-red-500/10 border border-red-500/25 px-3 py-2.5">
                <div className="text-[11px] font-bold text-red-400">{err}</div>
              </div>
            )}
            <button
              disabled={renting || qLoading}
              onClick={insufficient ? onGoToTopup : rent}
              className={`w-full py-4 rounded-[22px] text-[15px] font-black apple-spring
                          disabled:opacity-50 cursor-pointer
                          bg-[var(--accent)] text-white shadow-lg`}
            >
              {insufficient
                ? `Top up · ${fmt(quote?.total ?? 0)} UZS`
                : renting
                  ? 'Yuborilmoqda…'
                  : `Sotib olish · ${fmt(quote?.total ?? 0)} UZS`}
            </button>
            <p className={`text-[10px] text-center leading-relaxed ${isDark ? 'text-neutral-500' : 'text-neutral-400'}`}>
              To&apos;lovdan keyin NFTni Fragment hisobingizga ulaysiz. Muddat tugach
              egasi qaytaradi.
            </p>
          </div>
        </div>
      )}
    </div>
  );
};

const Row: React.FC<{ label: string; value: string; dark: boolean }> = ({ label, value, dark }) => (
  <div className="flex items-center justify-between">
    <span className={`text-[13px] ${dark ? 'text-neutral-400' : 'text-neutral-600'}`}>{label}</span>
    <span className={`text-[13px] font-bold ${dark ? 'text-white' : 'text-neutral-900'}`}>{value}</span>
  </div>
);

export default NftRentView;