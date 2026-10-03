import React, { useState, useEffect, useRef } from 'react';
import { User, StoreSettings, BotChatMessage } from '../types';
import { Send, Bot, Sparkles, RefreshCw, ExternalLink, ShieldCheck, Play, Square, AlertCircle, CheckCircle2 } from 'lucide-react';

interface BotSimulatorProps {
  user: User | null;
  settings: StoreSettings | null;
  onOpenStoreTab: (tab: string) => void;
  onOpenTopup: () => void;
  onBalanceUpdated: (newBalance: number) => void;
}

export const BotSimulator: React.FC<BotSimulatorProps> = ({
  user,
  settings,
  onOpenStoreTab,
  onOpenTopup,
  onBalanceUpdated,
}) => {
  // Real Telegram bot connection state
  const [botStatus, setBotStatus] = useState<any>({ running: false, botInfo: null });
  const [botTokenInput, setBotTokenInput] = useState<string>('');
  const [botWebappUrlInput, setBotWebappUrlInput] = useState<string>(
    typeof window !== 'undefined' ? window.location.origin : 'https://ais-dev-ffdnmkh7ixsl5w6yf5m34t-532430849464.asia-southeast1.run.app'
  );
  const [connecting, setConnecting] = useState<boolean>(false);
  const [botActionMsg, setBotActionMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Chat simulator state matching Image 1
  const [messages, setMessages] = useState<BotChatMessage[]>([
    {
      id: 'init_1',
      sender: 'bot',
      text: `👋 <b>Assalomu alaykum, @${user?.username || 'normuzb'}</b>\n\n🆔 User ID: <code>${user?.id || 8307046273}</code>\n💳 Balans: <b>${user?.balance.toLocaleString() || '357 813'} so'm</b>\n\n🔗 Referral link: <code>t.me/shop_neonbot?start=u${user?.id || 8307046273}</code>`,
      time: '9:47 AM',
      inlineKeyboard: [
        [{ text: '🟢 Stars sotib olish', action: 'buy_stars' }],
        [{ text: '🔵 Stars sotish', action: 'sell_stars' }, { text: '🔵 Premium', action: 'buy_prem' }],
        [{ text: '🔴 Giftlar', action: 'buy_gifts' }],
        [{ text: "🟢 Balans to'ldirish", action: 'topup' }, { text: '🔵 Referal', action: 'referral' }],
        [{ text: '🔵 Web App ❐', action: 'open_webapp' }],
        [{ text: '⚫ Profil', action: 'profile' }, { text: '⚫ Tarix', action: 'history' }],
        [{ text: '🔴 Support', action: 'support' }],
      ],
      replyKeyboard: [
        ['Stars sotib olish', 'Premium'],
        ['Giftlar', "Balans to'ldirish"],
        ['Profil', 'Tarix'],
        ['Web App ❐', 'Support'],
      ],
    },
  ]);

  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Exact button colors matching Image 1
  const getButtonColorClass = (btnText: string) => {
    const t = btnText.toLowerCase().trim();
    if (t.includes('stars sotib olish') || t.includes("balans to'ldirish") || t.includes("balans toldirish")) {
      return 'bg-[#2e7d32] hover:bg-[#388e3c] text-white shadow-sm border-0';
    }
    if (t.includes('stars sotish') || t.includes('premium') || t.includes('referal') || t.includes('web app')) {
      return 'bg-[#1976d2] hover:bg-[#2196f3] text-white shadow-sm border-0';
    }
    if (t.includes('giftlar') || t.includes('gift') || t.includes('support')) {
      return 'bg-[#c62828] hover:bg-[#d32f2f] text-white shadow-sm border-0';
    }
    if (t.includes('profil') || t.includes('tarix')) {
      return 'bg-[#1e293b] hover:bg-[#334155] text-slate-100 shadow-sm border-0';
    }
    return 'bg-[#1976d2] hover:bg-[#2196f3] text-white border-0';
  };

  const fetchBotStatus = async () => {
    try {
      const res = await fetch('/api/bot/status');
      const data = await res.json();
      if (data.ok) {
        setBotStatus(data);
        if (data.webappUrl) {
          setBotWebappUrlInput(data.webappUrl);
        }
      }
    } catch (e) {
      console.error('Failed to fetch bot status:', e);
    }
  };

  useEffect(() => {
    fetchBotStatus();
    const interval = setInterval(fetchBotStatus, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleStartRealBot = async () => {
    if (!botTokenInput.trim()) {
      setBotActionMsg({ type: 'error', text: 'Iltimos, @BotFather bergan BOT_TOKEN kiriting.' });
      return;
    }

    setConnecting(true);
    setBotActionMsg(null);
    try {
      const res = await fetch('/api/bot/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          token: botTokenInput.trim(),
          webappUrl: botWebappUrlInput.trim() || window.location.origin,
        }),
      });
      const data = await res.json();
      if (data.ok) {
        setBotActionMsg({
          type: 'success',
          text: `✅ Telegram Bot @${data.botInfo?.username} muvaffaqiyatli ishga tushdi va ulandi!`,
        });
        fetchBotStatus();
      } else {
        setBotActionMsg({ type: 'error', text: `❌ Xatolik: ${data.error}` });
      }
    } catch (e: any) {
      setBotActionMsg({ type: 'error', text: `❌ Ulanishda xatolik: ${e.message}` });
    } finally {
      setConnecting(false);
    }
  };

  const handleStopRealBot = async () => {
    setConnecting(true);
    try {
      await fetch('/api/bot/stop', { method: 'POST' });
      setBotActionMsg({ type: 'success', text: "Telegram bot to'xtatildi." });
      fetchBotStatus();
    } catch (e: any) {
      setBotActionMsg({ type: 'error', text: e.message });
    } finally {
      setConnecting(false);
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const sendQuery = async (queryText: string, actionName?: string) => {
    if (!queryText && !actionName) return;

    const displayMsg = queryText || actionName || '';
    const userMsg: BotChatMessage = {
      id: 'usr_' + Date.now(),
      sender: 'user',
      text: displayMsg,
      time: new Date().toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const res = await fetch('/api/bot/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: queryText, action: actionName }),
      });
      const data = await res.json();
      if (data.ok && data.message) {
        setMessages((prev) => [...prev, data.message]);
        if (data.user?.balance !== undefined) {
          onBalanceUpdated(data.user.balance);
        }
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleButtonClick = (action: string) => {
    if (action === 'open_webapp') {
      onOpenStoreTab('stars');
      return;
    }
    if (action === 'topup') {
      onOpenTopup();
      return;
    }
    if (action === 'buy_stars') {
      onOpenStoreTab('stars');
      return;
    }
    if (action === 'buy_prem') {
      onOpenStoreTab('premium');
      return;
    }
    if (action === 'buy_gifts') {
      onOpenStoreTab('gifts');
      return;
    }
    if (action === 'history') {
      onOpenStoreTab('history');
      return;
    }
    sendQuery('', action);
  };

  const handleReplyKeyboardClick = (btnText: string) => {
    if (btnText === '🌐 Web App') {
      onOpenStoreTab('stars');
      return;
    }
    if (btnText === '💳 Balans to\'ldirish') {
      onOpenTopup();
      return;
    }
    sendQuery(btnText);
  };

  return (
    <div className="space-y-6">
      {/* Real Telegram Bot Manager Panel */}
      <div className="rounded-3xl bg-gradient-to-br from-slate-900 via-indigo-950/40 to-slate-900 border border-white/10 p-5 md:p-6 space-y-4 shadow-xl">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className={`w-12 h-12 rounded-2xl flex items-center justify-center text-white shrink-0 ${
              botStatus.running
                ? 'bg-emerald-500/20 border border-emerald-500/40 shadow-lg shadow-emerald-500/20'
                : 'bg-cyan-500/20 border border-cyan-500/30'
            }`}>
              <Bot className="w-6 h-6 text-cyan-300" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-bold text-white">Haqiqiy Telegram Bot Boshqaruvi</h3>
                <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                  botStatus.running
                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                    : 'bg-slate-800 text-slate-400'
                }`}>
                  {botStatus.running ? '🟢 Online / Ishlayapti' : '⚪ O\'chiq'}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Bot @BotFather tokeni orqali to'g'ridan-to'g'ri Telegramga ulanadi va mini-ilova bilan 1:1 sinxron ishlaydi.
              </p>
            </div>
          </div>

          {botStatus.running && botStatus.botInfo && (
            <a
              href={`https://t.me/${botStatus.botInfo.username}`}
              target="_blank"
              rel="noreferrer"
              className="px-4 py-2 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs flex items-center gap-1.5 transition-all shadow-md self-start sm:self-auto"
            >
              <span>@{botStatus.botInfo.username} ni ochish</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          )}
        </div>

        {/* Bot Token Form */}
        <div className="pt-2 border-t border-white/5 space-y-3">
          {botStatus.running && botStatus.botInfo ? (
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-2xl bg-emerald-950/30 border border-emerald-500/20">
              <div className="space-y-1">
                <div className="text-xs text-emerald-300 font-bold">
                  Ulangan Bot: @{botStatus.botInfo.username} ({botStatus.botInfo.first_name})
                </div>
                <div className="text-[11px] text-slate-400">
                  Web App manzili: <span className="font-mono text-cyan-400">{botStatus.webappUrl}</span>
                </div>
              </div>
              <button
                onClick={handleStopRealBot}
                disabled={connecting}
                className="px-4 py-2 rounded-xl bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 font-bold text-xs border border-rose-500/30 flex items-center justify-center gap-1.5 transition-colors cursor-pointer"
              >
                <Square className="w-3.5 h-3.5" />
                <span>To'xtatish</span>
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-12 gap-3">
              <div className="sm:col-span-5 space-y-1">
                <label className="text-xs text-slate-300 font-medium">BOT_TOKEN (@BotFather'dan)</label>
                <input
                  type="password"
                  placeholder="1234567890:ABCdefGHIjklMNOpqr..."
                  value={botTokenInput}
                  onChange={(e) => setBotTokenInput(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-white/10 text-xs font-mono text-white placeholder-slate-600 outline-none focus:border-cyan-500"
                />
              </div>

              <div className="sm:col-span-4 space-y-1">
                <label className="text-xs text-slate-300 font-medium">Web App Havolasi</label>
                <input
                  type="text"
                  placeholder="https://..."
                  value={botWebappUrlInput}
                  onChange={(e) => setBotWebappUrlInput(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-white/10 text-xs font-mono text-white placeholder-slate-600 outline-none focus:border-cyan-500"
                />
              </div>

              <div className="sm:col-span-3 flex items-end">
                <button
                  onClick={handleStartRealBot}
                  disabled={connecting}
                  className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-bold text-xs tracking-wide shadow-lg shadow-cyan-950/40 active:scale-95 transition-all flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50"
                >
                  <Play className="w-3.5 h-3.5" />
                  <span>{connecting ? 'Ulanmoqda...' : 'Botni Ishga Tushirish'}</span>
                </button>
              </div>
            </div>
          )}

          {botActionMsg && (
            <div className={`p-3 rounded-xl text-xs flex items-center gap-2 ${
              botActionMsg.type === 'success'
                ? 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/20'
                : 'bg-rose-500/10 text-rose-300 border border-rose-500/20'
            }`}>
              {botActionMsg.type === 'success' ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              ) : (
                <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
              )}
              <span>{botActionMsg.text}</span>
            </div>
          )}
        </div>
      </div>

      {/* Interactive Telegram Chat Simulator Header */}
      <div className="max-w-3xl mx-auto rounded-3xl bg-[#0f1422] border border-white/10 shadow-2xl overflow-hidden flex flex-col h-[700px]">
        <div className="bg-[#171e31] p-4 border-b border-white/10 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="relative">
              <img
                src="/logo.svg"
                alt="NeonShop"
                className="w-10 h-10 rounded-xl object-cover shadow-md"
              />
              <span className="absolute bottom-0 right-0 w-3 h-3 rounded-full bg-emerald-400 border-2 border-[#171e31]" />
            </div>
            <div>
              <div className="flex items-center gap-1.5 font-bold text-white text-sm">
                <span>NEON STORE BOT (Simulyator)</span>
                <ShieldCheck className="w-4 h-4 text-cyan-400" />
              </div>
              <div className="text-[11px] text-cyan-400 font-mono">@shop_neonbot • online</div>
            </div>
          </div>

          <button
            onClick={() => {
              setMessages([]);
              sendQuery('/start');
            }}
            className="p-2 rounded-xl bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white transition-colors"
            title="Qayta ishga tushirish (/start)"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>

        {/* Chat Messages Body */}
        <div className="flex-1 p-4 overflow-y-auto space-y-4 bg-radial from-[#131929] to-[#0b0e18]">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex flex-col ${msg.sender === 'user' ? 'items-end' : 'items-start'}`}
            >
              <div
                className={`max-w-[85%] rounded-2xl p-4 space-y-3 text-xs leading-relaxed shadow-lg ${
                  msg.sender === 'user'
                    ? 'bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-tr-none'
                    : 'bg-[#1b233a] border border-white/10 text-slate-200 rounded-tl-none'
                }`}
              >
                <div
                  dangerouslySetInnerHTML={{
                    __html: msg.text.replace(/\n/g, '<br/>'),
                  }}
                />

                {/* Inline Keyboard buttons */}
                {msg.inlineKeyboard && msg.inlineKeyboard.length > 0 && (
                  <div className="space-y-1.5 pt-2 border-t border-white/10">
                    {msg.inlineKeyboard.map((row, rIdx) => (
                      <div key={rIdx} className="flex gap-1.5 flex-wrap">
                        {row.map((btn, bIdx) => (
                          <button
                            key={bIdx}
                            onClick={() => handleButtonClick(btn.action)}
                            className={`flex-1 min-w-[120px] py-2.5 px-3 rounded-xl text-xs font-bold text-white transition-all flex items-center justify-center gap-1 active:scale-95 cursor-pointer ${getButtonColorClass(btn.text)}`}
                          >
                            <span>{btn.text}</span>
                          </button>
                        ))}
                      </div>
                    ))}
                  </div>
                )}

                <div
                  className={`text-[9px] text-right font-mono ${
                    msg.sender === 'user' ? 'text-purple-200' : 'text-slate-400'
                  }`}
                >
                  {msg.time}
                </div>
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex items-center gap-2 p-3 rounded-xl bg-[#1b233a] text-slate-400 text-xs w-28">
              <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-bounce" />
              <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-bounce delay-100" />
              <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-bounce delay-200" />
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Reply Keyboard */}
        <div className="bg-[#141b2e] p-2.5 border-t border-white/10">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5">
            {[
              '⭐ Stars sotib olish',
              '💎 Telegram Premium',
              '🎁 Telegram Gifts',
              "💳 Balans to'ldirish",
              '👤 Profilim',
              '🏆 Konkurs & Bonus',
              '🌐 Web App',
              '🆘 Yordam',
            ].map((btn) => (
              <button
                key={btn}
                onClick={() => handleReplyKeyboardClick(btn)}
                className="py-2 px-2.5 rounded-xl bg-slate-900/90 hover:bg-slate-800 border border-white/10 text-white text-[11px] font-semibold active:scale-95 transition-all text-center cursor-pointer truncate"
              >
                {btn}
              </button>
            ))}
          </div>
        </div>

        {/* Input bar */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (input.trim()) sendQuery(input);
          }}
          className="p-3 bg-[#0d121f] border-t border-white/10 flex items-center gap-2"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Xabar yozing (masalan: /start, /buy, /premium, /admin)..."
            className="flex-1 px-4 py-2.5 rounded-xl bg-slate-950 border border-white/10 text-xs text-white placeholder-slate-500 outline-none focus:border-cyan-500"
          />
          <button
            type="submit"
            disabled={!input.trim() || loading}
            className="p-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white disabled:opacity-40 transition-all cursor-pointer shadow-md"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  );
};
