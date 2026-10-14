import React, { useState, useEffect, useRef } from 'react';
import { User, StoreSettings, Topup, Order, Contest } from './types';
import { Lang } from './i18n';
import { Header } from './components/Header';
import { BottomNav, TabType } from './components/BottomNav';
import { HomeView } from './components/views/HomeView';
import { TopupView } from './components/views/TopupView';
import { BuyView } from './components/views/BuyView';
import { RankingView } from './components/views/RankingView';
import { ProfileView } from './components/views/ProfileView';
import { AdminPanel } from './components/AdminPanel';
import { LiquidPointer } from './components/LiquidPointer';
import { toastText } from './lib/telegramText';
import { ErrorBoundary } from './components/ErrorBoundary';
import { CheckCircle2, ArrowLeft, PauseCircle, ShieldAlert } from 'lucide-react';
import { useIsDesktop } from './lib/useLayout';
import { isInsideTelegram, tgHeadersGet } from './lib/tgAuth';
import TelegramDeepLogin from './components/TelegramDeepLogin';

export default function App() {
  const [currentTab, setCurrentTab] = useState<TabType>('home');
  const [initialBuyCategory, setInitialBuyCategory] = useState<'stars' | 'premium' | 'gifts' | 'nft'>('stars');
  const [lang, setLang] = useState<Lang>(() => {
    return (localStorage.getItem('neon_lang') as Lang) || 'uz';
  });

  // Day / Night mode: 'dark' by default, persisted in localStorage
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    return (localStorage.getItem('apple_theme') as 'dark' | 'light') || 'dark';
  });
  const isDark = theme === 'dark';

  // Botga o'tish havolasi (401 ekrani uchun)
  // 🔶 Bot nomi state'i (serverdan, `/api/config`) — `isDesktop`
  //    deklaratsiyasi YONIDA, chunki undan foydalanadi (TDZ xatosi).
  const [botUsername, setBotUsername] = useState<string>('');

  // 🔴 ZAXIRA ZAXIRALAR (birinchi topilgani ishlatiladi):
  //    1) `botUsername` — serverdan (`/api/config` → bazadagi bot nomi)
  //    2) build vaqtidagi `VITE_BOT_USERNAME`
  //    3) `FALLBACK_BOT_USERNAME` — qat'iy qiymat
  //    3-bosqich YO&Q bo!lishi SHART: `/api/config` javob bermasa
  //    yoki server hali ishga tushmagan bo!lsa, Login Widget bot
  //    NOMISIZ yuklanmaydi → mijoz saytga umuman kira olmaydi.
  const BUILD_BOT_USERNAME =
    (import.meta.env.VITE_BOT_USERNAME || '').replace(/^@/, '');
  const FALLBACK_BOT_USERNAME = 'shop_neonbot';
  const BOT_USERNAME =
    botUsername || BUILD_BOT_USERNAME || FALLBACK_BOT_USERNAME;


  // Tema klassi faqat asosiy `<div>` da bo'lsa, `document.body` ga
  // PORTAL qilingan modal (NftRentView) tema ranglarini OLMAYDI:
  // u `.light`/`.dark` dan tashqarida qoladi va har doim qorong'i
  // kabi chiziladi. Shu sabab biz ham body ga sinxronlaymiz.
  useEffect(() => {
    // 🏠 IKKALA TA YERGA ham sinxronlanadi:
    //   1) `document.body`  — `.light .liquid-glass-*` CSS qoidalari shu
    //      yerda ishlaydi (bu ilova temani faqat shu orqali boshqaradi)
    //   2) `document.documentElement` — `<html>` da `class="dark"`
    //      QATTIQCHA yozilgan bo'lsa, TAILWIND `dark:` VARIANTLARI
    //      DOIM yoniq bo'lib qoladi va yorug' rejimda ham oq yuvish
    //      qo'yiladi (`hover:bg-white/5` kabi). Buni tozalash SHART.
    const b = document.body;
    b.classList.remove('light', 'dark');
    b.classList.add(theme);
    const h = document.documentElement;
    h.classList.remove('light', 'dark');
    h.classList.add(theme);
  }, [theme]);

  // 🌐 EKRAN O'LSAMI: desktopda (>=768px) ilova telefon
  // ko'rinishida qolmasin — chap menyu + keng kontent.
  const isDesktop = useIsDesktop();

  // 🔗 Bot nomini serverdan oliramiz (Login Widget uchun zarur)
  useEffect(() => {
    let alive = true;
    fetch('/api/config')
      .then((r) => r.json())
      .then((j) => {
        if (alive && j?.ok && j.bot_username) setBotUsername(j.bot_username);
      })
      .catch(() => { /* server yo'q — build fallback */ });
    return () => { alive = false; };
  }, []);

  const [user, setUser] = useState<User | null>(null);
  const [settings, setSettings] = useState<StoreSettings | null>(null);
  const [contest, setContest] = useState<Contest | null>(null);
  const [history, setHistory] = useState<Order[]>([]);
  const [activeTopup, setActiveTopup] = useState<Topup | null>(null);
  const [toastMsg, setToastMsg] = useState<string | null>(null);
  // 🔴 Server "Telegram orqali kiring" dedi (401) — bu holatda
  // ilovani bo'sh qoldirmaslik kerak, chunki aks holda mijoz
  // NIMAGANI bilmay qoladi.
  const [needTelegram, setNeedTelegram] = useState<string | null>(null);
  // 📖 Login Widget xatosi alohida — `needTelegram` esa
  // «kirish kerak» holatini bildiradi (401 dan keladi)
  const [loginError, setLoginError] = useState<string | null>(null);

  // 🔶 Telegram ICHIDA yoki BRAUZERDAmi? Brauzerda Login
  //  Widget kerak; Telegram ichida — hech narsa ko'rsatilmaydi
  //  (`initData` bor va server uni avtomatik tekshiradi).
  const inBrowser = !isInsideTelegram();
  // 🔴 Poller ham o'ziga IMZO yuborishi SHART — aks holda server
  // identifikatsiyani topa olmay, 401 qaytaradi (yoki eski kodda —
  // ADMIN bo'lib qolardi va mijozning ekrani "dilbek"ga aylanardi).
  const [initData, setInitData] = useState<string>('');

  // Admin condition: ONLY user ID 8307046273 (or settings.admin_id)
  const isAdmin = user?.id === 8307046273 || (Boolean(settings?.admin_id) && user?.id === settings?.admin_id);

  const handleLangChange = (newLang: Lang) => {
    setLang(newLang);
    localStorage.setItem('neon_lang', newLang);
  };

  const handleToggleTheme = () => {
    const next = theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    localStorage.setItem('apple_theme', next);
    triggerHaptic('light');
  };

  const fetchUserData = async (
    tgId?: number,
    tgUsername?: string,
    photoUrl?: string,
    firstName?: string,
    initData?: string
  ) => {
    try {
      let url = '/api/me';
      const params = new URLSearchParams();
      if (tgId) params.append('uid', tgId.toString());
      if (tgUsername) params.append('un', tgUsername);
      if (photoUrl) params.append('photo_url', photoUrl);
      if (firstName) params.append('first_name', firstName);
      if (params.toString()) {
        url += `?${params.toString()}`;
      }

      const res = await fetch(url, {
        // 🔴 `tgHeadersGet()` — avval qo'lda header bloki
        // yozilgan edi va u **sessiya tokenini YUBORMASDI**. Ya'ni
        // brauzerda Telegram Login Widget orqali kirgandan keyin ham
        // ilova «Telegram orqali kiring» ekranida QOLARDI —
        // `fetch('/api/me')` ‘X-Session-Token’siz 401 beradi.
        // 📖 Barcha so'rovlar `tgAuth` yordamchisidan o'tadi:
        //    Telegram ichida → `X-Telegram-Init-Data` (imzo)
        //    brauzerda         → `X-Session-Token` (sessiya)
        headers: tgHeadersGet({
          'x-telegram-user-id': tgId ? tgId.toString() : '',
          'x-telegram-username': tgUsername || '',
          'x-telegram-photo-url': photoUrl || '',
          'x-telegram-first-name': firstName || '',
        }),
      });
      const data = await res.json();
      if (res.status === 401 || data.need_telegram) {
        setNeedTelegram(data.error || 'Telegram orqali kiring');
        return;
      }
      if (data.ok) {
        setUser(data.user);
        setHistory(data.history || []);
        setContest(data.contest || null);
        setSettings(data.settings || null);
        if (data.user?.pending_topup) {
          setActiveTopup(data.user.pending_topup);
        } else {
          // 🔴 `activeTopup` faqat SET qilinardi, hech qachon
          // tozalanmasdi. Bekor qilingan yoki vaqti o'tgan to'lov o'lik
          // kartasi bo'lib qolardi (va `TopupView` har 4 soniyada
          // so'rov yuborishda davom etardi).
          setActiveTopup(null);
        }
      }
    } catch (err) {
      console.error('Failed to fetch user data:', err);
    }
  };

  useEffect(() => {
    const tg = (window as any).Telegram?.WebApp;
    if (tg) {
      try {
        tg.ready();
        tg.expand();
      } catch (e) {
        console.error('Telegram WebApp ready error:', e);
      }
    }

    let parsedId: number | undefined;
    let parsedUn: string | undefined;
    let parsedFirst: string | undefined;
    let parsedPhoto: string | undefined;
    // 🔴 IMZOLI identifikatsiya. Server shuni BOT_TOKEN bilan
    // tekshiradi va FAQAT undan foydalanuvchi id'sini oladi.
    // Boshqa manbalar (?uid=, header) ishonchsiz — ularni
    // hujjatlashtirish uchun ham yuboramiz (server ALLOW_UNSIGNED_USER
    // yoqiqda e'tiborsiz qoldiradi).
    let initDataRaw = '';

    // 0. 🔴 IMRZO SATRI — server shuni tekshiradi
    try {
      initDataRaw =
        (window as any).Telegram?.WebApp?.initData ||
        (document.querySelector('script[data-webapp-initdata]') as any)?.textContent ||
        '';
    } catch {
      initDataRaw = '';
    }

    // 1. Direct WebApp object
    if (tg?.initDataUnsafe?.user?.id) {
      parsedId = Number(tg.initDataUnsafe.user.id);
      parsedUn = tg.initDataUnsafe.user.username;
      parsedFirst = tg.initDataUnsafe.user.first_name;
      parsedPhoto = tg.initDataUnsafe.user.photo_url;
    }

    // 2. tg.initData query string
    if (!parsedId && tg?.initData) {
      try {
        const q = new URLSearchParams(tg.initData);
        const userStr = q.get('user');
        if (userStr) {
          const u = JSON.parse(userStr);
          if (u.id) {
            parsedId = Number(u.id);
            parsedUn = u.username || parsedUn;
            parsedFirst = u.first_name || parsedFirst;
            parsedPhoto = u.photo_url || parsedPhoto;
          }
        }
      } catch (e) {
        console.error('Error parsing tg.initData:', e);
      }
    }

    // 3. URL Hash fragment (#tgWebAppData=...)
    if (!parsedId && window.location.hash) {
      try {
        const hashStr = window.location.hash.replace(/^#/, '');
        const hashParams = new URLSearchParams(hashStr);
        const tgWebAppData = hashParams.get('tgWebAppData');
        if (tgWebAppData) {
          const dataParams = new URLSearchParams(tgWebAppData);
          const userStr = dataParams.get('user');
          if (userStr) {
            const u = JSON.parse(userStr);
            if (u.id) {
              parsedId = Number(u.id);
              parsedUn = u.username || parsedUn;
              parsedFirst = u.first_name || parsedFirst;
              parsedPhoto = u.photo_url || parsedPhoto;
            }
          }
        }
      } catch (e) {
        console.error('Error parsing window.location.hash:', e);
      }
    }

    // 4. URL query parameters (?uid=... or ?tg_user_id=...)
    const urlParams = new URLSearchParams(window.location.search);
    const queryUid = urlParams.get('uid') || urlParams.get('tg_user_id');
    const queryUn = urlParams.get('un') || urlParams.get('tg_username');
    const queryFirst = urlParams.get('first_name') || urlParams.get('fn');
    const queryPhoto = urlParams.get('photo_url');

    if (!parsedId && queryUid && !isNaN(Number(queryUid))) {
      // 🔴 Bu ISHONCHSIZ (server tasdiqlamaydi). Faqat Telegram
      // initData bo'lmaganda ko'rsatish uchun.
      parsedId = Number(queryUid);
    }
    if (queryUn) parsedUn = queryUn;
    if (queryFirst) parsedFirst = queryFirst;
    if (queryPhoto) parsedPhoto = queryPhoto;

    setInitData(initDataRaw);
    fetchUserData(parsedId, parsedUn, parsedPhoto, parsedFirst, initDataRaw);
  }, []);

  const triggerHaptic = (type: 'light' | 'medium' | 'heavy' | 'success' = 'medium') => {
    try {
      const tg = (window as any).Telegram?.WebApp;
      if (tg?.HapticFeedback) {
        if (type === 'success') {
          tg.HapticFeedback.notificationOccurred('success');
        } else {
          tg.HapticFeedback.impactOccurred(type);
        }
      }
    } catch (e) {
      // ignore
    }
  };

  // DIQQAT: server.ts xabarlarni Telegram HTML formatida yuboradi
  // (<b>, <code> ...). Toast oddiy matn sifatida ko'rsatadi, shuning
  // uchun teglarni TOZA MATNGA aylantiramiz — aks holda foydalanuvchi
  // "<b>Buyurtmangiz qabul qilindi!</b>" deb XOM teglarni ko'radi.
  // NFT ijaraga olish yuborilganda — balans darhol yangilanadi
  // (server allaqon yechgan) va toast chiqadi.
  const handleNftRented = (msg: string, newBalance?: number, order?: any) => {
    if (user && typeof newBalance === 'number') {
      setUser({ ...user, balance: newBalance });
    }
    // 🔴 TARIXGA QO'SHISH. Bu holda `processingCount` oshadi va
    // poller (`useEffect`) ISHLAB KETADI — aks holda to'lanagan buyurtma
    // to'liq qayta yuklashgacha ko'rinmay qolardi: poller `data.history`
    // dan foydalanadi, `processingCount` nol bo'lgani uchun umuman
    // ishlamaydi va mijoz «to'lov o'tmadi» deb o'ylaydi.
    if (order) {
      setHistory((prev) => [{ ...order, kind: 'nft_rent' }, ...prev]);
    }
    showToast(msg);
  };

  // 📖 Toast timer'i bOSHqARILADI: har yangi xabarda eskisi
  // tozalanadi. Aks holda ikki xabar tez oraliqda kelsa, birinchi timer
  // ikkinchisini ham o'chiradi — xabar 1 soniya ko'rinib, "ishlamadi"
  // taassuroti qoldiradi.
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showToast = (msg: string) => {
    triggerHaptic('success');
    setToastMsg(toastText(msg));
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToastMsg(null), 4000);
  };

  const handleOrderSuccess = (order: Order, newBalance: number, msg: string) => {
    if (user) {
      // 🔴 `total_spent` NaN bo'lsa butun mijoz hisobiga
      // «NaN» yopishadi — haftalik bonus ustasi ham, reyting ham
      // buziladi. `order.price` serverda ixtiyoriy (eski buyurtmalarda
      // yo'q bo'lishi mumkin).
      const spent = Number(order?.price) || 0;
      const nextSpent = (Number(user.total_spent) || 0) + spent;
      setUser({
        ...user,
        balance: Number(newBalance) || 0,
        total_spent: nextSpent,
      });
    }
    setHistory((prev) => [order, ...prev]);
    showToast(msg);
  };

  /**
   * Buyurtma holatini kuzatish
   * -----------------------
   * Stars yuborilayotgan paytda webapp "yuborilmoqda" deb turmasligi uchun
   * holatni avtomatik yangilaymiz. Bot yetkazganda "✅ Stars yuborildi!"
   * xabari chiqadi va balantari ham yangilanadi.
   */
  const processingCount = history.filter(
    (o) => o.status === 'processing' || o.status === 'queued' || o.status === 'pending'
  ).length;

  useEffect(() => {
    if (processingCount === 0) return;
    let alive = true;
    let ticks = 0;

    const poll = async () => {
      try {
        const res = await fetch('/api/me', {
          // 🔴 `sessiya` ham yuborilishi SHART — brauzerda
          // poller har 8 sekundda 401 olardi va to'lov hech qachon
          // avtomatik yangishmasdi.
          headers: tgHeadersGet({
            'x-telegram-user-id': user?.id?.toString() || '',
          }),
        });
        const data = await res.json();
        if (!alive || !data.ok) return;

        const fresh: Order[] = data.history || [];
        if (!fresh.length) return;

        // Eski holat bilan solishtirib, tugaganlarini topamiz
        setHistory((prev) => {
          const prevMap = new Map(prev.map((o) => [o.id, o]));
          let changed = false;
          const merged = fresh.map((o) => {
            const before = prevMap.get(o.id);
            const wasPending =
              before && (before.status === 'processing' || before.status === 'queued' || before.status === 'pending');
            const nowDone = o.status === 'done' || o.status === 'completed' || o.status === 'sent_unconfirmed';
            if (wasPending && nowDone) changed = true;
            return o;
          });
          return changed ? merged : prev;
        });

        if (data.user?.balance !== undefined && user && data.user.balance !== user.balance) {
          setUser(data.user);
        }
      } catch (e) {
        /* tarmoq uzilishi — keyingi urinishda */
      }
    };

    poll();
    const timer = setInterval(() => {
      ticks += 1;
      if (ticks > 75) return;      // ~10 daqiqadan keyin to'xtaydi
      poll();
    }, 8000);

    return () => {
      alive = false;
      clearInterval(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [processingCount, user?.id, initData]);

  const handleTopupSuccess = (newBalance: number, msg: string) => {
    if (user) {
      setUser({ ...user, balance: newBalance });
    }
    setActiveTopup(null);
    showToast(msg);
  };

  // 🔐 KIRISH EKRANI
  // 🔴 Telegram ICHIDA ochilganda — `initData` avtomatik keladi,
  //     server imzosini tekshiradi va bu ekran umuman chiqMAYDI
  //     («Telegram orqali kiring» deb so'ramaymiz).
  // 📖 BRAUZERDA ochilganda — `initData` yo'q. Endi mijoz
  //     «Login via Telegram» tugmasini bosadi (Telegram'ning rasmiy
  //     Login Widget) va o'z Telegram profil bilan ro'yxatdan
  //     o'tadi. Keyinchalik sessiya `localStorage` da saqlanadi.
  if (needTelegram) {
    return (
      <div
        className={`${theme} min-h-screen flex flex-col items-center justify-center text-center p-6 sm:p-8 relative overflow-hidden ${
          isDark ? 'bg-[#000000] text-white' : 'bg-[#f2f2f7] text-neutral-900'
        }`}
      >
        <div className="aurora-blob aurora-1 -top-24 -left-20 w-96 h-96" />
        <div className="aurora-blob aurora-2 -bottom-24 -right-20 w-96 h-96" />
        <div className="noise-overlay" />

        <div className="relative z-10 liquid-glass-card rounded-[36px] p-7 sm:p-9 w-full max-w-sm sm:max-w-md sheet-in">
          <div
            className={`w-16 h-16 mx-auto rounded-[22px] liquid-glass-pill flex items-center justify-center mb-5 ${
              isDark ? 'text-blue-300' : 'text-blue-600'
            }`}
          >
            <ShieldAlert className="w-8 h-8" />
          </div>

          <h2 className={`text-lg font-bold ${isDark ? 'text-white' : 'text-neutral-900'}`}>
            Telegram orqali kiring
          </h2>

          {inBrowser ? (
            /* 🌐 YANGI KO'RINISH — FAQAT «Connect Telegram».
               🔴 Mijozning so'rovi: «Botga o'tish» tugmasi
               umuman kerak emas. Sayt — sayt; mijoz shu yerda
               Telegram orqali kiradi va shu yerdan foydalanadi.
               Ilgari ikkita yo'l bor edi (Widget + Botga o'tish) —
               bu chalkashlik keltirardi va Widget yuklanmagan paytda
               «Botga o'tish» bilan bo'sh joy qolardi. */
            <>
              <p
                className={`text-[12.5px] mt-2.5 leading-relaxed ${
                  isDark ? 'text-neutral-400' : 'text-neutral-600'
                }`}
              >
                Xizmatlardan foydalanish uchun Telegram orqali kiring.
                Sizning nomingiz, usernamingiz va profil rasmingiz
                Telegram tomonidan tasdiqlanadi.
              </p>

              {/* 🌐 TELEGRAM ORQALI KIRISH — deep link (popup umuman yo'q)

                  🔴🔴 NIMA UCHUN ESKI LOGIN WIDGET OLIB TASHLANDI?
                  Mijoz xabari: «tugmani bosdim, ekran ochilib 1 soniyada
                  yopildi, sahifa o'zgarmadi». Telegram'ning `/auth/get`
                  javobini tekshirish natijani ko'rsatdi:

                      {"error":"NOT_AUTHORIZED", "origin":"https://..."}

                  Bu `onAuth(origin, false)` → `{event:'unauthorized'}` → ota
                  tomonda `onUnauth && onUnauth()`. Bizda `data-onunauth`
                  YO'Q EDI — ya'ni hech narsa bo'lmasdi, sahifa jimgina
                  o'z-o'zidan qolardi. Shu sababli eski yo'l butunlay
                  olib tashlandi.

                  ✅ YANGI YO'L: server kod beradi → biz
                  `t.me/<bot>?start=<kod>` ni ochamiz → mijoz Telegram'da
                  Start bosadi → bot.py kodni yozadi → biz sessiya
                  olamiz. Popup, CORS va third-party cookie umuman yo'q. */}
              <TelegramDeepLogin
                isDark={isDark}
                onSuccess={() => {
                  setLoginError(null);
                  setNeedTelegram(null);
                  window.location.reload();
                }}
                onError={(msg) => setLoginError(msg)}
              />

              {loginError && (
                <p className="mt-3 text-[12px] text-rose-400">{loginError}</p>
              )}
            </>
          ) : (
            <>
              {/* 📐 Bu holat NORMAL DEGIL — Telegram ichida
                  `initData` bo'ladi va server uni avtomatik tekshiradi.
                  Bu ekran faqat sessiya muddati tuggan yoki `initData`
                  kelmagan holatda chiqadi.
                  🔴 Mijozning so'rovi bo!yicha «Botga o'tish»
                  tugmasi QO'SHILMADI — faqat qayta urinish. */}
              <p
                className={`text-[12.5px] mt-2.5 leading-relaxed ${
                  isDark ? 'text-neutral-400' : 'text-neutral-600'
                }`}
              >
                Telegram akkauntingizga ulanish muvaffaqiyatsiz bo'ldi.
                Qayta urinib ko'ring — bot orqali qayta ochsangiz,
                🔄 tugmasini bosing.
              </p>
              <button
                onClick={() => {
                  setNeedTelegram(null);
                  window.location.reload();
                }}
                className={`mt-5 w-full py-3 rounded-[18px] text-[13px] font-bold apple-spring cursor-pointer ${
                  isDark
                    ? 'liquid-glass-pill text-white'
                    : 'liquid-glass-pill text-neutral-900'
                }`}
              >
                🔄 Qayta urinish
              </button>
            </>
          )}
        </div>
      </div>
    );
  }

  // Admin botni to'xtatgan bo'lsa — WebApp ham javov bermaydi (Liquid Glass ekran)
  if (settings && settings.bot_active === false) {
    return (
      <div className={`${theme} min-h-screen flex flex-col items-center justify-center text-center p-8 relative overflow-hidden ${isDark ? 'bg-[#000000] text-white' : 'bg-[#f2f2f7] text-neutral-900'}`}>
        <div className="aurora-blob aurora-1 -top-24 -left-20 w-96 h-96" />
        <div className="aurora-blob aurora-2 -bottom-24 -right-20 w-96 h-96" />
        <div className="noise-overlay" />
        <div className="relative z-10 liquid-glass-card rounded-[36px] p-8 max-w-xs w-full sheet-in">
          <div className={`w-16 h-16 mx-auto rounded-[22px] liquid-glass-pill flex items-center justify-center mb-5 ${isDark ? 'text-amber-300' : 'text-amber-600'}`}>
            <PauseCircle className="w-8 h-8" />
          </div>
          <h1 className={`text-xl font-bold mb-2 ${isDark ? 'text-white' : 'text-neutral-900'}`}>
            Bot vaqtincha to'xtatilgan
          </h1>
          <p className={`text-sm leading-relaxed ${isDark ? 'text-neutral-400' : 'text-neutral-600'}`}>
            Iltimos, birozdan so'ng qayta urinib ko'ring.
          </p>
          <div className={`mt-5 inline-flex items-center gap-2 px-4 py-2 rounded-full liquid-glass-pill text-xs font-semibold ${isDark ? 'text-neutral-300' : 'text-neutral-700'}`}>
            <span className="w-2 h-2 rounded-full bg-amber-400 live-dot" />
            Tez orada qayta ishlaydi
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`${theme} min-h-screen ${isDark ? 'bg-[#000000] text-neutral-100' : 'bg-[#f2f2f7] text-neutral-900'} relative overflow-x-hidden transition-colors duration-300 font-sans`}>
      {/* LiquidPointer — glass specular yorug'i + aurora parallaks */}
      <LiquidPointer />

      {/* Neon Aurora backdrop — glass uchun rangli refraksiya */}
      <div className="fixed inset-0 pointer-events-none z-0" aria-hidden style={{ transform: 'translate(var(--ax), var(--ay))' }}>
        <div className="aurora-blob aurora-1 -top-32 -left-24 w-[420px] h-[420px]" />
        <div className="aurora-blob aurora-2 top-1/4 -right-28 w-[380px] h-[380px]" />
        <div className="aurora-blob aurora-3 -bottom-28 left-1/3 w-[360px] h-[360px]" />
        <div className="aurora-blob aurora-4 top-2/3 -left-1/4 w-[300px] h-[300px]" />
      </div>
      <div className="noise-overlay" />

      {/* Apple Minimalist Toast */}
      {toastMsg && (
        <div
          className="fixed top-[3.6rem] inset-x-0 z-50 flex justify-center px-4 pointer-events-none"
          role="status"
          aria-live="polite"
        >
          <div
            className="toast-in liquid-glass rounded-full px-4 py-2.5 shadow-2xl
                       flex items-center justify-center gap-2 border
                       w-fit max-w-full break-words"
          >
            <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
            <span className="text-xs font-semibold text-center leading-snug">{toastMsg}</span>
          </div>
        </div>
      )}

      {/* 🔴 HEADER ErrorBoundary ICHIDA.
          Sabab: `Header` butun ilova bo'ylab chiziladi va `user.balance`
          kabi maydonlarni to'g'ridan-to'g'ri o'qiydi. U TASHQARIDA
          bo'lsa, bitta xato butun ilovani oq ekranga tushiradi
          (oddiy `user?` himoyasi `user` bor, `balance` yo'q bo'lganda
          ishlamaydi). Endi xato faqat sarlavhani olib tashlaydi —
          kontent ishlayveradi. */}
      <ErrorBoundary label="Sarlavha">
        <Header
          user={user}
          settings={settings}
          lang={lang}
          onChangeLang={handleLangChange}
          isDark={isDark}
          onToggleTheme={handleToggleTheme}
          onOpenTopup={() => setCurrentTab('topup')}
          onOpenAdmin={isAdmin ? () => setCurrentTab('admin') : undefined}
          isAdmin={isAdmin}
          isDesktop={isDesktop}
        />
      </ErrorBoundary>

      {/* Main View Area */}
      <main className={
        `flex-1 max-w-md md:max-w-none w-full mx-auto px-4 md:px-6 xl:px-10 pt-3.5 relative z-10 `
        + `${isDesktop ? 'md:pl-[124px]' : ''}`
      }>
        <ErrorBoundary label="Bosh sahifa">
        {currentTab === 'home' && (
          <HomeView
            user={user}
            settings={settings}
            lang={lang}
            isDark={isDark}
            onGoToBuy={(cat) => {
              if (cat) setInitialBuyCategory(cat);
              setCurrentTab('buy');
            }}
            onGoToTopup={() => setCurrentTab('topup')}
          />
        )}
        </ErrorBoundary>

        {/* 2. TOP UP VIEW */}
        <ErrorBoundary label="To'ldirish">
        {currentTab === 'topup' && (
          <TopupView
            user={user}
            settings={settings}
            lang={lang}
            isDark={isDark}
            activeTopup={activeTopup}
            onTopupCreated={(t) => {
              setActiveTopup(t);
              showToast("To'lov so'rovi yaratildi.");
            }}
            onTopupSuccess={handleTopupSuccess}
            onTopupCancelled={() => {
              // 🔤 O'LIK TO'LOV KARTASINI OLIB TASHLAMIZ: serverda
              // muddati tugagan/bekor qilingan to'lov endi ko'rinmasin,
              // poller ham o'z-o'zidan to'xtasin.
              setActiveTopup(null);
            }}
            onOpenHistory={() => setCurrentTab('profile')}
          />
        )}
        </ErrorBoundary>

        {/* 3. BUY VIEW */}
        <ErrorBoundary label="Xarid">
        {currentTab === 'buy' && (
          <BuyView
            user={user}
            settings={settings}
            lang={lang}
            isDark={isDark}
            initialTab={initialBuyCategory}
            onOrderSuccess={handleOrderSuccess}
            onGoToTopup={() => setCurrentTab('topup')}
            onRented={handleNftRented}
          />
        )}
        </ErrorBoundary>

        {/* 4. RANKING VIEW */}
        <ErrorBoundary label="Reyting">
        {currentTab === 'ranking' && (
          <RankingView
            user={user}
            contest={contest}
            lang={lang}
            isDark={isDark}
            onGoToBuy={() => setCurrentTab('buy')}
          />
        )}
        </ErrorBoundary>

        {/* 5. PROFILE VIEW */}
        <ErrorBoundary label="Profil">
        {currentTab === 'profile' && (
          <ProfileView
            user={user}
            settings={settings}
            orders={history}
            lang={lang}
            onChangeLang={handleLangChange}
            isDark={isDark}
            onToggleTheme={handleToggleTheme}
            onGoToTopup={() => setCurrentTab('topup')}
            onOpenAdmin={() => setCurrentTab('admin')}
            isAdmin={isAdmin}
          />
        )}
        </ErrorBoundary>

        {/* 6. SECRET ADMIN VIEW (ONLY FOR USER 8307046273) */}
        {currentTab === 'admin' && isAdmin && (
          <div className="space-y-4 pb-28 md:pb-10 apple-view-animate">
            <button
              onClick={() => setCurrentTab('profile')}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full liquid-glass-pill text-xs font-semibold apple-spring cursor-pointer"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Do'konga qaytish</span>
            </button>
            {/* 🔴 Admin panel ham ErrorBoundary ichida: biror render
                xatosi butun ilovani oq qilmasin — aks holda admin
                o'z panelini tuzatish imkoniyatidan ham mahrum bo'lardi. */}
            <ErrorBoundary label="Admin">
              <AdminPanel
                isDark={isDark}
                onSettingsUpdated={(newSettings) => setSettings(newSettings)}
              />
            </ErrorBoundary>
          </div>
        )}
      </main>

      {/* Floating Apple Liquid Glass Bottom Navigation Dock */}
      <BottomNav
        currentTab={currentTab}
        onChangeTab={(tab) => {
          triggerHaptic('light');
          setCurrentTab(tab);
        }}
        lang={lang}
        isDark={isDark}
        isDesktop={isDesktop}
      />
    </div>
  );
}
