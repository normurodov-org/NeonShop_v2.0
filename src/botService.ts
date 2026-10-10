import { Bot, InlineKeyboard, Keyboard } from 'grammy';
import { store, syncAndSaveDb } from '../server';

let currentBot: Bot | null = null;
let isBotRunning = false;
let botInfo: any = null;
let lastError: string | null = null;
let currentWebappUrl =
  process.env.WEBAPP_URL ||
  (process.env.RAILWAY_PUBLIC_DOMAIN ? `https://${process.env.RAILWAY_PUBLIC_DOMAIN}` : '');

export function getBotStatus() {
  return {
    running: isBotRunning,
    botInfo,
    webappUrl: currentWebappUrl,
    error: lastError,
  };
}

export async function stopTelegramBot() {
  if (currentBot && isBotRunning) {
    try {
      await currentBot.stop();
    } catch (e) {
      console.error('Error stopping bot:', e);
    }
    isBotRunning = false;
    currentBot = null;
    botInfo = null;
    console.log('🛑 Telegram bot stopped');
  }
}

export async function sendTelegramMessage(chatId: number, text: string): Promise<boolean> {
  if (currentBot && isBotRunning) {
    try {
      await currentBot.api.sendMessage(chatId, text, { parse_mode: 'HTML' });
      return true;
    } catch (e: any) {
      console.error('Failed to send telegram message:', e.message);
    }
  }
  return false;
}

export async function startTelegramBot(token?: string, webappUrl?: string) {
  const botToken = token || process.env.BOT_TOKEN;
  if (!botToken || botToken.trim() === '') {
    lastError = 'BOT_TOKEN kiritilmagan';
    return { ok: false, error: lastError };
  }

  if (webappUrl) {
    currentWebappUrl = webappUrl.replace(/\/$/, '');
  }

  // If already running, stop first
  if (isBotRunning) {
    await stopTelegramBot();
  }

  try {
    const bot = new Bot(botToken.trim());
    currentBot = bot;
    lastError = null;

    // Get bot identity
    botInfo = await bot.api.getMe();
    console.log(`🤖 Telegram bot initialized: @${botInfo.username} (${botInfo.first_name})`);

    // Helper: Find or create user
    const getOrCreateUser = (ctx: any) => {
      const from = ctx.from;
      if (!from) return null;
      let user = store.users.get(from.id);
      if (!user) {
        user = {
          id: from.id,
          username: from.username || `user_${from.id.toString().slice(-4)}`,
          first_name: from.first_name,
          balance: 357813,
          total_spent: 0,
          referrals_count: 0,
          ref_stars: 0,
          banned: false,
          created_at: new Date().toISOString(),
        };
        store.users.set(from.id, user);
        store.settings.total_users += 1;
        syncAndSaveDb();
      } else if (from.username && user.username !== from.username) {
        user.username = from.username;
        syncAndSaveDb();
      }
      return user;
    };

    // 1. /start command — exactly matching Image 1
    bot.command('start', async (ctx) => {
      const user = getOrCreateUser(ctx);
      if (!user) return;

      // Check referral payload: /start ref_12345 or /start u12345
      const text = ctx.message?.text || '';
      const match = text.match(/(?:ref_|u)(\d+)/);
      if (match) {
        const referrerId = parseInt(match[1], 10);
        if (referrerId !== user.id && store.users.has(referrerId)) {
          const referrer = store.users.get(referrerId);
          if (referrer && !user.referred_by) {
            user.referred_by = referrerId;
            referrer.referrals_count = (referrer.referrals_count || 0) + 1;
            referrer.ref_stars = (referrer.ref_stars || 0) + 1;
            syncAndSaveDb();
          }
        }
      }

      // Welcome text matching Image 1
      const welcomeText =
        `👋 <b>Assalomu alaykum, @${user.username}</b>\n\n` +
        `🆔 User ID: <code>${user.id}</code>\n` +
        `💳 Balans: <b>${user.balance.toLocaleString()} so'm</b>\n\n` +
        `🔗 Referral link: <code>t.me/${botInfo?.username || 'shop_neonbot'}?start=u${user.id}</code>`;

      // 7-row inline keyboard matching Image 1 with vibrant colors
      const inlineKb = new InlineKeyboard()
        .text('⭐ Stars sotib olish', 'buy_stars').row()
        .text('💸 Stars sotish', 'sell_stars')
        .text('💎 Premium', 'buy_prem').row()
        .text('🎁 Giftlar', 'buy_gifts').row()
        .text("💳 Balans to'ldirish", 'topup')
        .text('👥 Referal', 'referral').row()
        .webApp('📱 Web App ❐', currentWebappUrl).row()
        .text('👤 Profil', 'profile')
        .text('📜 Tarix', 'history').row()
        .url('💬 Support', `https://t.me/${store.settings.support_username}`);

      await ctx.reply(welcomeText, {
        parse_mode: 'HTML',
        reply_markup: inlineKb,
      });
    });

    // 2. Stars
    const handleStars = async (ctx: any) => {
      const inlineKb = new InlineKeyboard()
        .text('⭐ 50 Stars (10 000 UZS)', 'buy_stars_50')
        .text('⭐ 100 Stars (20 000 UZS)', 'buy_stars_100').row()
        .text('⭐ 250 Stars (50 000 UZS)', 'buy_stars_250')
        .text('⭐ 500 Stars (100 000 UZS)', 'buy_stars_500').row()
        .text('⭐ 1 000 Stars (200 000 UZS)', 'buy_stars_1000').row()
        .webApp('Web App orqali istalgan miqdor ❐', currentWebappUrl);

      const msg =
        `⭐ <b>Telegram Stars sotib olish</b>\n\n` +
        `• Kurs: 1 ⭐ = <b>${store.settings.star_buy_price} UZS</b>\n` +
        `• Minimal miqdor: <b>50 ⭐</b>\n` +
        `• To'lov tizimi: <b>Fragment (USDT on TON)</b> orqali avtomatik!\n\n` +
        `Kerakli paketni tanlang:`;

      await ctx.reply(msg, {
        parse_mode: 'HTML',
        reply_markup: inlineKb,
      });
    };

    bot.command('buy', handleStars);
    bot.hears(['Stars sotib olish', '⭐ Stars sotib olish', '🟢 ⭐ Stars sotib olish'], handleStars);

    // Stars sotish
    const handleSellStars = async (ctx: any) => {
      const user = getOrCreateUser(ctx);
      if (!user) return;

      const inlineKb = new InlineKeyboard()
        .url("👨‍💻 Admin bilan bog'lanish", `https://t.me/${store.settings.support_username}`)
        .webApp('Web App ❐', currentWebappUrl);

      const msg =
        `💰 <b>Stars sotish (Kartaga pul olish)</b>\n\n` +
        `• 1 ⭐ qabul qilish narxi: <b>${store.settings.star_sell_price} UZS</b>\n` +
        `• Minimal sotish miqdori: <b>100 ⭐</b>\n` +
        `• To'lov kartalari: <b>Humo / Uzcard</b> (bir necha daqiqada)\n\n` +
        `Stars'ni sotish uchun admin bilan bog'laning: @${store.settings.support_username}`;

      await ctx.reply(msg, {
        parse_mode: 'HTML',
        reply_markup: inlineKb,
      });
    };

    bot.hears(['Stars sotish', '💰 Stars sotish'], handleSellStars);

    // 3. Premium
    const handlePremium = async (ctx: any) => {
      const inlineKb = new InlineKeyboard()
        .text("💎 3 oy (Sovg'a) — 155 000 UZS", 'buy_prem_3').row()
        .text("💎 6 oy (Sovg'a) — 205 000 UZS", 'buy_prem_6').row()
        .text("💎 12 oy (Sovg'a) — 375 000 UZS", 'buy_prem_12').row()
        .webApp('Web App orqali xarid qilish ❐', currentWebappUrl);

      const msg =
        `💎 <b>Telegram Premium obunasi</b>\n\n` +
        `Telegram imkoniyatlarini maksimal darajaga ko'taring:\n` +
        `• 4 GB fayl yuklash hajmi\n` +
        `• Reklamalarsiz tezlik\n` +
        `• Ovozli xabarlarni avtomatik matnga aylantirish\n` +
        `• Eksklyuziv profil nishonchasi va stikerlar\n\n` +
        `Kerakli muddatni tanlang:`;

      await ctx.reply(msg, {
        parse_mode: 'HTML',
        reply_markup: inlineKb,
      });
    };

    bot.command('premium', handlePremium);
    bot.hears(['Premium', '💎 Premium', '💎 Telegram Premium'], handlePremium);

    // 4. Gifts
    const handleGifts = async (ctx: any) => {
      const inlineKb = new InlineKeyboard()
        .text('🧸 Ayiqcha (3 000 UZS)', 'buy_gift_bear')
        .text('💝 Yurakcha (3 000 UZS)', 'buy_gift_heart').row()
        .text("🎁 Sovg'a qutisi (6 000 UZS)", 'buy_gift_box')
        .text('🚀 Raketa (10 000 UZS)', 'buy_gift_rocket').row()
        .text('🏆 Kubok (20 000 UZS)', 'buy_gift_cup')
        .text('💎 Olmos (20 000 UZS)', 'buy_gift_diamond').row()
        .webApp("Barcha 11 ta sovg'ani ko'rish (Web App) ❐", currentWebappUrl);

      const msg =
        `🎁 <b>Telegram Gifts (Sovg'alar)</b>\n\n` +
        `Do'stlaringizga va yaqinlaringizga profilingizdan Telegram sovg'alarini yuboring.\n` +
        `Yetkazish avtomatlashtirilgan userbot orqali amalga oshiriladi.\n\n` +
        `Sovg'ani tanlang:`;

      await ctx.reply(msg, {
        parse_mode: 'HTML',
        reply_markup: inlineKb,
      });
    };

    bot.command('gifts', handleGifts);
    bot.hears(['Giftlar', '🎁 Giftlar', '🎁 Telegram Gifts'], handleGifts);

    // 5. Balance & Top-up
    const handleBalance = async (ctx: any) => {
      const user = getOrCreateUser(ctx);
      if (!user) return;

      const inlineKb = new InlineKeyboard()
        .text('➕ 25 000 UZS', 'topup_25000')
        .text('➕ 50 000 UZS', 'topup_50000').row()
        .text('➕ 100 000 UZS', 'topup_100000')
        .text('➕ 250 000 UZS', 'topup_250000').row()
        .webApp("Web App orqali to'lov ❐", currentWebappUrl);

      const msg =
        `💳 <b>Balans va To'lov</b>\n\n` +
        `Sizning balansingiz: <b>${user.balance.toLocaleString()} so'm</b>\n\n` +
        `Qabul qiluvchi karta (HUMO):\n<code>${store.settings.card_number}</code>\n` +
        `Karta egasi: <b>${store.settings.card_holder}</b>\n\n` +
        `Tezkor to'ldirish summasini tanlang yoki Web App orqali to'lang:`;

      await ctx.reply(msg, {
        parse_mode: 'HTML',
        reply_markup: inlineKb,
      });
    };

    bot.command('balance', handleBalance);
    bot.hears(["Balans to'ldirish", "💳 Balans to'ldirish"], handleBalance);

    // 6. Profile
    const handleProfile = async (ctx: any) => {
      const user = getOrCreateUser(ctx);
      if (!user) return;

      const inlineKb = new InlineKeyboard()
        .text("Balans to'ldirish", 'topup')
        .text('Referal', 'referral').row()
        .webApp('Web App ❐', currentWebappUrl);

      const msg =
        `👤 <b>Foydalanuvchi profili</b>\n\n` +
        `🆔 ID: <code>${user.id}</code>\n` +
        `👤 Username: @${user.username}\n` +
        `💳 Balans: <b>${user.balance.toLocaleString()} so'm</b>\n` +
        `🛍 Jami xaridlar: <b>${user.total_spent.toLocaleString()} so'm</b>\n` +
        `👥 Taklif qilingan do'stlar: <b>${user.referrals_count} ta</b>\n` +
        `⭐ Referal Stars: <b>${user.ref_stars} ⭐</b>`;

      await ctx.reply(msg, {
        parse_mode: 'HTML',
        reply_markup: inlineKb,
      });
    };

    bot.command('profile', handleProfile);
    bot.hears(['Profil', '👤 Profil', '👤 Profilim'], handleProfile);

    // Tarix
    const handleHistory = async (ctx: any) => {
      const user = getOrCreateUser(ctx);
      if (!user) return;

      const userOrders = Array.from(store.orders.values())
        .filter((o: any) => o.user_id === user.id)
        .slice(0, 5);

      let text = `📜 <b>Oxirgi buyurtmalar tarixi (@${user.username}):</b>\n\n`;
      if (userOrders.length === 0) {
        text += "Sizda hali xaridlar mavjud emas.";
      } else {
        userOrders.forEach((o: any, idx: number) => {
          const statusIcon = o.status === 'completed' ? '✅' : o.status === 'pending_admin' ? '⏳' : '❌';
          text += `${idx + 1}. ${statusIcon} <b>${o.title}</b> — ${o.price.toLocaleString()} UZS\n`;
          text += `   Holat: ${o.status === 'completed' ? 'Yetkazildi' : 'Adminga yuborilgan'}\n`;
        });
      }

      const inlineKb = new InlineKeyboard().webApp('Barcha tarixni Web App da ko\'rish ❐', currentWebappUrl);

      await ctx.reply(text, { parse_mode: 'HTML', reply_markup: inlineKb });
    };

    bot.hears(['Tarix', '📜 Tarix'], handleHistory);

    // Support
    const handleSupport = async (ctx: any) => {
      await ctx.reply(
        `🆘 <b>Qo'llab-quvvatlash xizmati</b>\n\nSavollar yoki yordam uchun adminga murojaat qiling: @${store.settings.support_username}`,
        {
          parse_mode: 'HTML',
          reply_markup: new InlineKeyboard().url('Admin bilan yozishish', `https://t.me/${store.settings.support_username}`),
        }
      );
    };

    bot.hears(['Support', '🆘 Yordam'], handleSupport);

    // 7. Contest
    const handleContest = async (ctx: any) => {
      const user = getOrCreateUser(ctx);
      if (!user) return;

      const isJoined = store.contest.participants.includes(user.id);
      const inlineKb = new InlineKeyboard();
      if (!isJoined) {
        inlineKb.text("🎉 Konkursda qatnashish", 'join_contest').row();
      }
      inlineKb.webApp("Web App'da ko'rish ❐", currentWebappUrl);

      const msg =
        `🏆 <b>Faol Konkurs: Bahorgi Stars Sovrini</b>\n\n` +
        `${store.contest.text}\n\n` +
        `👥 Jami ishtirokchilar: <b>${store.contest.participants.length} ta</b>\n` +
        `💰 Sizning xaridingiz: <b>${user.total_spent.toLocaleString()} UZS</b>\n` +
        `📌 Holatingiz: <b>${isJoined ? "✅ Siz ishtirokchisiz!" : "❌ Hali qo'shilmagansiz"}</b>`;

      await ctx.reply(msg, {
        parse_mode: 'HTML',
        reply_markup: inlineKb,
      });
    };

    bot.command('contest', handleContest);

    // 8. Referral
    const handleReferral = async (ctx: any) => {
      const user = getOrCreateUser(ctx);
      if (!user) return;

      const refLink = `https://t.me/${botInfo.username}?start=u${user.id}`;
      const inlineKb = new InlineKeyboard()
        .url('Do\'stlarga ulashish', `https://t.me/share/url?url=${encodeURIComponent(refLink)}&text=${encodeURIComponent("NEON STORE — Telegram Stars va Premium arzon narxda!")}`)
        .row()
        .webApp('Web App ❐', currentWebappUrl);

      const msg =
        `👥 <b>Referal tizimi</b>\n\n` +
        `Har bir taklif qilingan faol do'stingiz uchun <b>1 ⭐ Stars</b> oling!\n\n` +
        `• Taklif qilinganlar: <b>${user.referrals_count} ta</b>\n` +
        `• To'plangan Stars: <b>${user.ref_stars} ⭐</b>\n` +
        `• Minimal yechib olish: <b>50 ⭐</b>\n\n` +
        `Sizning referal havolangiz:\n<code>${refLink}</code>`;

      await ctx.reply(msg, {
        parse_mode: 'HTML',
        reply_markup: inlineKb,
      });
    };

    bot.command('referral', handleReferral);

    // Callback queries
    bot.on('callback_query:data', async (ctx) => {
      const data = ctx.callbackQuery.data;
      const user = getOrCreateUser(ctx);
      if (!user) return;

      // Handle Buy Stars via Fragment (USDT on TON)
      if (data.startsWith('buy_stars_')) {
        const starCount = parseInt(data.replace('buy_stars_', ''), 10);
        const price = starCount * store.settings.star_buy_price;

        if (user.balance < price) {
          const inlineKb = new InlineKeyboard()
            .text("Balans to'ldirish", 'topup')
            .webApp('Web App ❐', currentWebappUrl);

          await ctx.answerCallbackQuery({ text: '⚠️ Balans yetarli emas!', show_alert: true });
          await ctx.reply(
            `⚠️ <b>Balans yetarli emas!</b>\n\n` +
            `Narx: <b>${price.toLocaleString()} UZS</b>\n` +
            `Balansingiz: <b>${user.balance.toLocaleString()} so'm</b>\n\n` +
            `Iltimos, avval balansni to'ldiring:`,
            { parse_mode: 'HTML', reply_markup: inlineKb }
          );
          return;
        }

        user.balance -= price;
        user.total_spent += price;
        store.settings.total_orders += 1;

        const orderId = 'ord_' + Math.random().toString(36).slice(2, 9);
        const usdtNeeded = +(starCount * (store.settings.star_usdt_rate || 0.015)).toFixed(3);

        // Stars FAQAT USDT (TON) orqali Fragment'dan xarid qilinadi.
        // Bu Node-stub emas — buyurtma bazaga yoziladi va bot.py dagi
        // star_order_worker() uni haqiqiy Fragment USDT to'lovini yuborish uchun oladi.
        store.orders.set(orderId, {
          id: orderId,
          user_id: user.id,
          kind: 'stars',
          title: `⭐ ${starCount} Telegram Stars`,
          recipient: user.username,
          price,
          price_uzs: price,
          amount: starCount,
          stars: starCount,
          status: 'processing',
          source: 'grammy',
          payment_method: 'usdt_ton',
          created_at: new Date().toISOString(),
        });

        syncAndSaveDb();

        // Adminga xabar
        sendTelegramMessage(
          store.settings.admin_id || 8307046273,
          `⭐ <b>Yangi Stars buyurtmasi (grammy)</b>\n\n` +
            `📦 <code>#${orderId}</code>\n` +
            `👤 @${user.username} (<code>${user.id}</code>) → @${user.username}: <b>${starCount} ⭐</b>\n` +
            `💳 Yechilgan: <b>${price.toLocaleString()} UZS</b>\n` +
            `💎 Taxminiy sarf: <b>${usdtNeeded} USDT (TON)</b>\n\n` +
            `🤖 <i>bot.py worker orqali USDT bilan Fragment'da avtomatik xarid qilinadi.</i>`
        );

        await ctx.answerCallbackQuery({ text: '⏳ Buyurtma yuborilmoqda...' });
        await ctx.reply(
          `⏳ <b>Buyurtmangiz qabul qilindi!</b>\n\n` +
            `⭐ Miqdor: <b>${starCount.toLocaleString()} Stars</b>\n` +
            `💳 Yechildi: <b>${price.toLocaleString()} UZS</b>\n` +
            `💎 To'lov: <b>USDT (TON)</b> — Fragment orqali avtomatik\n` +
            `📌 Holat: <b>yuborilmoqda (10–60 soniya)</b>`,
          { parse_mode: 'HTML' }
        );
        return;
      }

      // Handle Topup
      if (data.startsWith('topup_')) {
        const amount = parseInt(data.replace('topup_', ''), 10);
        const topupId = 'top_' + Math.random().toString(36).slice(2, 9);
        const newTopup = {
          id: topupId,
          user_id: user.id,
          amount,
          status: 'pending',
          card: store.settings.card_number,
          holder: store.settings.card_holder,
          expires_at: Date.now() + 5 * 60 * 1000,
          created_at: new Date().toISOString(),
        };
        store.topups.set(topupId, newTopup);
        syncAndSaveDb();

        await ctx.answerCallbackQuery();
        await ctx.reply(
          `💳 <b>To'lov so'rovi yaratildi</b>\n\n` +
          `Summa: <b>${amount.toLocaleString()} UZS</b>\n` +
          `Karta (HUMO): <code>${store.settings.card_number}</code>\n` +
          `Egasi: <b>${store.settings.card_holder}</b>\n\n` +
          `<i>Kartaga to'lov qilishingiz bilan bank orqali balans avtomatik to'ldiriladi (5 daqiqa ichida).</i>`,
          { parse_mode: 'HTML' }
        );
        return;
      }

      // Shortcuts
      if (data === 'buy_stars') return handleStars(ctx);
      if (data === 'sell_stars') return handleSellStars(ctx);
      if (data === 'buy_prem') return handlePremium(ctx);
      if (data === 'buy_gifts') return handleGifts(ctx);
      if (data === 'topup') return handleBalance(ctx);
      if (data === 'referral') return handleReferral(ctx);
      if (data === 'profile') return handleProfile(ctx);
      if (data === 'history') return handleHistory(ctx);

      await ctx.answerCallbackQuery();
    });

    // Set Telegram chat menu button to open Web App
    try {
      await bot.api.setChatMenuButton({
        menu_button: {
          type: 'web_app',
          text: 'Web App',
          web_app: { url: currentWebappUrl },
        },
      });
      console.log('✅ Telegram chat menu button configured with Web App:', currentWebappUrl);
    } catch (e: any) {
      console.warn('Chat menu button setup notice:', e.message);
    }

    bot.catch((err) => {
      console.warn('Telegram bot error caught:', err.message);
      lastError = err.message;
    });

    // Start long polling with automatic retry and never drop updates
    const startPollingWithRetry = () => {
      bot.start({
        drop_pending_updates: false,
        allowed_updates: ['message', 'callback_query'],
        onStart: () => {
          isBotRunning = true;
          console.log(`✅ Telegram bot @${botInfo.username} long-polling is ACTIVE and listening!`);
        },
      }).catch(async (err) => {
        console.warn('Telegram bot polling notice:', err.message);
        lastError = err.message;
        isBotRunning = false;
        if (currentBot === bot) {
          console.log('🔄 Telegram bot will reconnect in 2.5s...');
          await new Promise((r) => setTimeout(r, 2500));
          if (currentBot === bot) {
            startPollingWithRetry();
          }
        }
      });
    };

    startPollingWithRetry();

    return {
      ok: true,
      botInfo,
      message: `Telegram bot @${botInfo.username} muvaffaqiyatli ishga tushdi!`,
    };
  } catch (err: any) {
    console.error('Failed to start Telegram bot:', err);
    lastError = err.message || 'Botni ishga tushirib bo\'lmadi';
    isBotRunning = false;
    return { ok: false, error: lastError };
  }
}
