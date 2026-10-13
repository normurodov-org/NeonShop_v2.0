import React, { useEffect, useRef, useState } from 'react';
import Modal from '../Modal';
import { Boxes, Gift, Heart, ChevronDown, SlidersHorizontal, X, Minus, Plus } from 'lucide-react';

interface NftItem {
  id: string;
  title: string;
  number: number | null;
  image: string;
  link: string;
  /** Telegram sahifasidan olingan "Backdrop: ..." (masalan "Chestnut") */
  backdrop?: string;
  /** To'plam (server.tomlardan keladi, bo'lmasa hech qanday) */
  collection?: string;
  /** "Newest first" saralash uchun */
  created_at?: string;
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

/**
 * Backdrop filtrlari.
 *
 * DIQQAT: avval ro'yxat QAT'IY yozilgan edi va hech qanday
 * filtrlashni bajarmaydi (o'lik UI). Endi ro'yxat Telegram
 * sahifasidan olingan `backdrop` maydonidan YIG'ILADI — ya'ni
 * filtr haqiqiy ma'lumotga ishlaydi.
 */
const ALL_BACKDROPS = 'All backdrops';
const ALL_COLLECTIONS = 'All collections';

const SORT_OPTIONS = [
  { id: 'cheap', label: 'Cheapest first' },
  { id: 'big', label: 'Most expensive' },
  { id: 'new', label: 'Newest first' },
] as const;
const SORT_LABEL: Record<string, string> = Object.fromEntries(
  SORT_OPTIONS.map((o) => [o.id, o.label]),
);
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

/**
 * NFT rasmi — rasm, "yuklanmoqda" va chiroli placeholder.
 *
 * 🔴 NIMA UCHUN alohida komponent:
 * `<img>` buzilsa (404, noto'g'ri havola) brauzer o'z "broken image"
 * ikonkasini ko'rsatadi — bu chiroli emas va mijozni chalg'itadi.
 * Shu sabab `onError` da biz o'zimizning placeholderimizga almashamiz.
 */
const NftImage: React.FC<{
  src?: string;
  alt: string;
  isDark: boolean;
  className?: string;
  /** NFT id — rasmni qayta olish uchun (self-healing) */
  nftId?: string;
  /** Telegram foydalanuvchi id */
  userId?: number;
}> = ({ src, alt, isDark, className = '', nftId, userId }) => {
  const [state, setState] = useState<'idle' | 'failed'>('idle');
  const [retrying, setRetrying] = useState(false);
  // Faqat BIR marta qayta urinish — aks holda cheksiz sikl bo'ladi
  const retriedRef = useRef(false);

  // 🔴 Yuklanmaydigan rasm — bo'sh kvadrat UCHUN QOLMASIN.
  // Ba'zi havolalar (o'lik domen, Telegram CDN muammosi) 404 ham
  // bermaydi, balki osilib qoladi: `onError` ishlamaydi va karta
  // doim bo'sh ko'rinadi. Shuning uchun qisqa muddatli TAYMER
  // ham qo'yamiz — yuklanmasa placeholder ga o'tamiz.
  const [fresh, setFresh] = useState<string | undefined>(undefined);
  const shown = fresh ?? src;

  // 🔴 🔴 🔴 BU YERDA IKKALTA XATO BO'LDI — ikkalasi ham TUZATILDI
  //
  // 1-XATO: `setTimeout(() => setState('failed'), 6000)`
  //   Rasmlar har 6 soniyada "muvaffaqiyatsiz" deb hisoblanardi.
  //   Natija: telefonlar sekin internetda rasm 6 soniyada
  //   YUKLANMAYDI -> rasm o'z-o'zidan YO'QOLDI.
  //   ("rasmlar 5 sekunddan keyin yuqolib qolyapti")
  //
  // 2-XATO: shuni `onLoad` bilan "tuzatdim", lekin 20 soniya ham
  //   yetarli bo'lmadi — sekin internetda yana o'ldi.
  //
  // 🔴 XULOSA: IS TALAB QILINMAYDI. `<img>` `error` hodisasini
  //   FAQAT haqiqiy xatoda chiqaradi (404, DNS xatosi, ulanish
  //   yo'q, noto'g'ri ma'lumot). U "sekin internet" uchun
  //   CHIQMAYDI — demak `onError` yetarli.
  //
  //   Ishlatilmay qolgan taymer esa BITTA muammo keltiradi:
  //   YETISHLI rasmlarni o'ldiradi — bu foydalanuvchi uchun
  //   ko'rinadigan va jiddiy muammo (bo'sh kvadrat).
  //
  //   Endi: yuklanayotgan paytda shimmer ko'rsatiladi (chiroyli),
  //   rasm kelganda `onLoad` -> shimmer yo'qoladi,
  //   haqiqiy xatoda `onError` -> serverdan qayta olish -> placeholder.
  const [loading, setLoading] = useState(false);
  const loadedRef = useRef(false);

  useEffect(() => {
    if (!isImageUrl(src)) {
      setLoading(false);
      return;
    }
    setState('idle');
    setFresh(undefined);
    setLoading(true);
    loadedRef.current = false;
    retriedRef.current = false;
    // DIQQAT: `timer` yo'q. Agar rasm juda uzoq yuklanmasa,
    // shimmer qoladi — bu placeholder'dan YAXSHI (kamroq xato).
  }, [src]);

  /**
   * 🔄 SELF-HEALING: Telegram CDN havolasi muddati tugagan bo'lishi
   * mumkin. Serverdan yangisini so'raymiz va ko'rsatamiz.
   */
  const retry = async () => {
    if (!nftId || retrying) return;
    setRetrying(true);
    try {
      const r = await fetch(`/api/nfts/refresh-image/${encodeURIComponent(nftId)}`, {
        method: 'POST',
        headers: { 'x-telegram-user-id': userId?.toString() || '' },
      });
      const j = await r.json();
      if (j?.ok && j.image && j.image !== src) {
        loadedRef.current = false;
        setFresh(j.image);
        setLoading(true);
        setState('idle');
        return;
      }
    } catch {
      /* server yo'q — placeholder qoladi */
    }
    setState('failed');
    setLoading(false);
    setRetrying(false);
  };

  const ok = isImageUrl(shown) && state !== 'failed';

  // Yuklanayotgan payt — shimmer (rasm kelganda yo'qoladi).
  // Bu yerda rasm O'LMAYDI: faqat chiroyli "yuklanmoqda" holati.
  if (ok && loading) {
    return (
      <div
        className={`nft-img w-full h-full nft-shimmer ${
          isDark ? 'bg-white/[0.04]' : 'bg-black/[0.03]'
        } ${className}`}
        aria-label="Yuklanmoqda"
      />
    );
  }

  if (!ok) {
    return (
      <div
        className={`nft-img w-full h-full flex flex-col items-center justify-center gap-1 ${
          isDark
            ? 'bg-gradient-to-br from-violet-500/20 to-fuchsia-500/10'
            : 'bg-gradient-to-br from-violet-100 to-fuchsia-50'
        } ${className}`}
      >
        <Gift
          className={`w-7 h-7 ${isDark ? 'text-violet-300/70' : 'text-violet-400/80'}`}
        />
        <span
          className={`text-[8px] font-bold uppercase tracking-wide ${
            isDark ? 'text-violet-200/60' : 'text-violet-400/70'
          }`}
        >
          NFT
        </span>
      </div>
    );
  }
  return (
    <img
      src={shown}
      alt={alt}
      loading="lazy"
      decoding="async"
      // 🔴 Rasmga o'lcham beriladi: `aspect-square` konteyner barqaror,
      // lekin rasmning o'z `width`/`height` siz yo'q bo'lsa, rasm
      // yuklanganda konteyner BIR PIKSEL siljishi mumkin (CLS).
      width={512}
      height={512}
      onLoad={() => {
        // Rasm keldi — shimmer yo'qoladi
        loadedRef.current = true;
        setLoading(false);
        setState('idle');
      }}
      onError={() => {
        // Avval serverdan yangisini so'raymiz
        if (nftId && !retriedRef.current) {
          retriedRef.current = true;
          retry();
        } else {
          setState('failed');
          setLoading(false);
        }
      }}
      className={`nft-img w-full h-full object-cover ${className}`}
    />
  );
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
  const [sort, setSort] = useState<'cheap' | 'big' | 'new'>('cheap');
  const [backdrop, setBackdrop] = useState(ALL_BACKDROPS);
  const [collection, setCollection] = useState(ALL_COLLECTIONS);
  const [fav, setFav] = useState<Record<string, boolean>>({});
  // Faqat tanlanganlar filtrini ON/OFF qiladi
  const [favOnly, setFavOnly] = useState(false);
  // Ochiq dropdown (bir vaqtda faqat bittasi)
  const [openMenu, setOpenMenu] = useState<'collection' | 'sort' | null>(null);

  // 🔴 Tanlanganlar localStorage'da saqlanadi. Aks holda sahifa
  // yangilanganda yurakcha holati yo'qolib ketardi va filtr
  // "ishlamaydi" degan taassurot tug'ilardi.
  useEffect(() => {
    try {
      const raw = localStorage.getItem('neon_nft_fav');
      if (raw) setFav(JSON.parse(raw));
    } catch {
      /* localStorage yo'q (incognito) — xatosiz davom etamiz */
    }
  }, []);
  const toggleFav = (id: string) => {
    setFav((f) => {
      const next = { ...f, [id]: !f[id] };
      try {
        localStorage.setItem('neon_nft_fav', JSON.stringify(next));
      } catch {
        /* saqlanmasa ham ishlaydi */
      }
      return next;
    });
  };

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

  //Dropdown yopilgandan keyin kartani ochamiz
  const open = (item: NftItem) => {
    setOpenMenu(null);
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

  // Backdrop ro'yxati — NFT'lar ichidagi haqiqiy qiymatlardan
  const backdrops = [ALL_BACKDROPS, ...new Set(
    items.map((n) => n.backdrop).filter(Boolean) as string[]
  )];

  // 🔴 Har bir filtr HAQIQATAN qo'llanadi (avval collection va ♥
  // hech narsani filtrlamagan — faqat o'lik UI edi).
  const shown = items
    .filter((n) => backdrop === ALL_BACKDROPS || n.backdrop === backdrop)
    .filter((n) => collection === ALL_COLLECTIONS || n.collection === collection)
    .filter((n) => !favOnly || fav[n.id])
    .sort((a, b) => {
      if (sort === 'big') return b.daily - a.daily;
      if (sort === 'new') return (b.created_at || '').localeCompare(a.created_at || '');
      return a.daily - b.daily;
    });

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
          {/* Filtrlar — 4 ta element, hammasi ISHLAYDI */}
          <div className="relative flex items-center gap-2 overflow-x-auto pb-1 -mx-4 px-4">
            {/* 1) All collections ▾ */}
            <div className="relative shrink-0">
              <button
                onClick={() => setOpenMenu(openMenu === 'collection' ? null : 'collection')}
                className={chip(false)}
                aria-expanded={openMenu === 'collection'}
                aria-haspopup="listbox"
              >
                <span className="flex items-center gap-2">
                  {collection}
                  <ChevronDown
                    className={`w-3.5 h-3.5 transition-transform ${
                      openMenu === 'collection' ? 'rotate-180' : ''
                    }`}
                  />
                </span>
              </button>
              {openMenu === 'collection' && (
                <div className="absolute left-0 top-full mt-2 z-30 min-w-[190px] rounded-[20px] p-1.5 liquid-glass-card nft-menu-in">
                  {[ALL_COLLECTIONS, ...new Set(
                    items.map((n) => n.collection).filter(Boolean) as string[]
                  )].map((c) => (
                    <button
                      key={c}
                      onClick={() => { setCollection(c); setOpenMenu(null); }}
                      className={`w-full text-left px-3 py-2.5 rounded-[14px] text-[13px] font-semibold apple-spring cursor-pointer ${
                        collection === c
                          ? 'bg-[var(--accent)] text-white'
                          : isDark
                            ? 'text-neutral-200 hover:bg-white/10'
                            : 'text-neutral-700 hover:bg-black/5'
                      }`}
                    >
                      {c}
                    </button>
                  ))}
                  {/* To'plamlar yo'q bo'lsa — tushunarli tushuntirish */}
                  {!items.some((n) => n.collection) && (
                    <div className={`px-3 py-2 text-[11px] leading-relaxed ${
                      isDark ? 'text-neutral-400' : 'text-neutral-500'
                    }`}>
                      Hozircha to'plamlar yo'q.
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* 2) Cheapest first ▾ */}
            <div className="relative shrink-0">
              <button
                onClick={() => setOpenMenu(openMenu === 'sort' ? null : 'sort')}
                className={chip(false)}
                aria-expanded={openMenu === 'sort'}
                aria-haspopup="listbox"
              >
                <span className="flex items-center gap-2">
                  {SORT_LABEL[sort] || 'Cheapest first'}
                  <ChevronDown
                    className={`w-3.5 h-3.5 transition-transform ${
                      openMenu === 'sort' ? 'rotate-180' : ''
                    }`}
                  />
                </span>
              </button>
              {openMenu === 'sort' && (
                <div className="absolute left-0 top-full mt-2 z-30 min-w-[190px] rounded-[20px] p-1.5 liquid-glass-card nft-menu-in">
                  {SORT_OPTIONS.map((o) => (
                    <button
                      key={o.id}
                      onClick={() => { setSort(o.id); setOpenMenu(null); }}
                      className={`w-full text-left px-3 py-2.5 rounded-[14px] text-[13px] font-semibold apple-spring cursor-pointer ${
                        sort === o.id
                          ? 'bg-[var(--accent)] text-white'
                          : isDark
                            ? 'text-neutral-200 hover:bg-white/10'
                            : 'text-neutral-700 hover:bg-black/5'
                      }`}
                    >
                      {o.label}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* 3) ♥ — tanlanganlar filtri (localStorage'da saqlanadi) */}
            <button
              onClick={() => setFavOnly(!favOnly)}
              aria-pressed={favOnly}
              aria-label="Faqat tanlanganlar"
              className={`shrink-0 w-11 h-11 rounded-full flex items-center justify-center apple-spring cursor-pointer border ${
                favOnly
                  ? 'bg-[var(--accent)] text-white border-transparent'
                  : isDark
                    ? 'bg-white/[0.06] text-neutral-300 border-white/10'
                    : 'bg-black/[0.04] text-neutral-600 border-black/[0.06]'
              }`}
            >
              <Heart className={`w-4.5 h-4.5 ${favOnly ? 'fill-white' : ''}`} />
            </button>

            {/* 4) ⚙ — qolgan filtrlarni tozalash */}
            <button
              onClick={() => {
                setCollection(ALL_COLLECTIONS);
                setBackdrop(ALL_BACKDROPS);
                setSort('cheap');
                setFavOnly(false);
                setOpenMenu(null);
              }}
              aria-label="Filtrlarni tozalash"
              className={`shrink-0 w-11 h-11 rounded-full flex items-center justify-center apple-spring cursor-pointer border ${
                shown.length === items.length
                  ? 'opacity-30 pointer-events-none'
                  : isDark
                    ? 'bg-white/[0.06] text-neutral-300 border-white/10'
                    : 'bg-black/[0.04] text-neutral-600 border-black/[0.06]'
              }`}
            >
              <SlidersHorizontal className="w-4.5 h-4.5" />
            </button>
          </div>

          {/* Backdrop filtrlari */}
          <div className="flex items-center gap-2 overflow-x-auto pb-1 -mx-4 px-4">
            {backdrops.map((b) => (
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
              {shown.map((n, idx) => (
                <button
                  key={n.id}
                  onClick={() => open(n)}
                  style={{ ['--i' as string]: Math.min(idx, 8) }}
                  className={`text-left rounded-[24px] overflow-hidden liquid-glass apple-spring
                              nft-card-in cursor-pointer group`}
                >
                  <div className="relative aspect-square overflow-hidden">
                    <NftImage
                      src={n.image}
                      alt={n.title}
                      isDark={isDark}
                      nftId={n.id}
                      userId={userId}
                      className="transition-transform duration-300 group-hover:scale-105"
                    />
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleFav(n.id);
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

      {/* MODAL — muddat va hisob.
          `Modal` PORTAL orqali `document.body` ga chiqaradi. Bu SHART:
          `apple-view-animate` da `transform: scale(1)` va `filter: blur(0px)`
          ANIMATSIYA TUGAGANDAN KEYIN HAM qoladi (fill-mode: both) —
          ikkalasi ham `position: fixed` ni buzadi va modal ekran emas,
          butun konteyner balandligida joylashadi (CTA tugmasi
          ekrandan tashqariga chiqib ketadi). */}
      <Modal open={!!sel} onClose={() => setSel(null)} align="bottom" label="NFT ijarasi">
        {sel && (
          <div
            className={`relative w-full sm:max-w-md rounded-t-[32px] sm:rounded-[32px]
                        liquid-glass-card p-5 space-y-4 overflow-y-auto sheet-in
                        max-h-[calc(100dvh-1.5rem)] sm:max-h-[88vh]
                        pb-[max(1.25rem,env(safe-area-inset-bottom))]`}
          >
            {/* Sarlavha */}
            <div className="flex items-center gap-3">
              <div
                className={`w-16 h-16 rounded-[18px] overflow-hidden shrink-0 ${
                  isDark ? 'bg-white/[0.06]' : 'bg-black/[0.04]'
                }`}
              >
                <NftImage src={sel.image} alt={sel.title} isDark={isDark} nftId={sel.id} userId={userId} />
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
                <span className="text-[16px] font-black text-[var(--accent-text)]">
                  {fmt(quote?.total ?? 0)} UZS
                </span>
              </div>
              <div className="flex items-center justify-between pt-1">
                {/* DIQQAT: neutral-500 yorug' rejimda 4.43:1 edi
                    (WCAG AA 4.5 dan past). neutral-600 -> 7.31:1 */}
                <span className={`text-[12px] ${isDark ? 'text-neutral-400' : 'text-neutral-600'}`}>
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
                          bg-[var(--accent)] text-white shadow-lg active:scale-[0.98] transition-transform`}
            >
              {insufficient
                ? `Top up · ${fmt(quote?.total ?? 0)} UZS`
                : renting
                  ? 'Yuborilmoqda…'
                  : `Sotib olish · ${fmt(quote?.total ?? 0)} UZS`}
            </button>
            <p className={`text-[10px] text-center leading-relaxed ${isDark ? 'text-neutral-400' : 'text-neutral-500'}`}>
              To&apos;lovdan keyin NFTni Fragment hisobingizga ulaysiz. Muddat tugach
              egasi qaytaradi.
            </p>
          </div>
        )}
      </Modal>
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