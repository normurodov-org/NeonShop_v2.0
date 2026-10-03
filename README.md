<div align="center">

<img src="assets/banner.svg" alt="NEON STORE — Telegram Stars, Premium va Gifts savdo boti" width="100%"/>

<br/>

<a href="https://t.me/shop_neonbot"><img src="https://img.shields.io/badge/Telegram-@shop__neonbot-26A5E4?style=for-the-badge&logo=telegram&logoColor=white" alt="Telegram bot"/></a>
<a href="https://t.me/Shop_NeonChannel"><img src="https://img.shields.io/badge/Kanal-@Shop__NeonChannel-8B5CF6?style=for-the-badge&logo=telegram&logoColor=white" alt="Kanal"/></a>
<a href="https://prem-bot-mini-app.vercel.app"><img src="https://img.shields.io/badge/Web%20App-Vercel-000000?style=for-the-badge&logo=vercel&logoColor=white" alt="Web App"/></a>

<img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.10+"/>
<img src="https://img.shields.io/badge/aiogram-3.x-2CA5E0?style=flat-square&logo=telegram&logoColor=white" alt="aiogram 3"/>
<img src="https://img.shields.io/badge/pyrofork-userbot-FF4FD8?style=flat-square" alt="pyrofork"/>
<img src="https://img.shields.io/badge/TON-Fragment-0098EA?style=flat-square" alt="TON + Fragment"/>
<img src="https://img.shields.io/badge/deploy-Railway-0B0D0E?style=flat-square&logo=railway&logoColor=white" alt="Railway"/>

<h3>⭐ Telegram Stars, 💎 Premium va 🎁 Gifts — so'mda, bir necha daqiqada, avtomatik</h3>

<p>
  <a href="#-imkoniyatlar">Imkoniyatlar</a> •
  <a href="#-qanday-ishlaydi">Qanday ishlaydi</a> •
  <a href="#-ornatish">O'rnatish</a> •
  <a href="#%EF%B8%8F-sozlamalar">Sozlamalar</a> •
  <a href="#%EF%B8%8F-admin-panel">Admin panel</a> •
  <a href="#-muammolar-va-yechimlar">Muammolar</a>
</p>

</div>

---

## 💫 Loyiha haqida

**NEON STORE** — O'zbekiston foydalanuvchilari uchun Telegram raqamli mahsulotlari do'koni. Mijoz balansini
karta orqali to'ldiradi, bot to'lovni **o'zi aniqlaydi**, buyurtmalarni esa **Fragment + TON** yoki
**userbot** orqali avtomatik yetkazadi. Hammasi bitta chatda — yoki chiroyli **Web App** ichida.

<div align="center">
  <img src="assets/flow.svg" alt="Buyurtma jarayoni" width="100%"/>
</div>

## ✨ Imkoniyatlar

<table>
<tr>
<td width="50%" valign="top">

### 🛍 Mijozlar uchun
- ⭐ **Stars sotib olish** — Fragment orqali, TON bilan avtomatik (min. 50 ⭐)
- 💰 **Stars sotish** — Stars'ni botga sotib, kartaga pul olish
- 💎 **Telegram Premium** — sovg'a sifatida yoki akkauntga kirib (1–12 oy)
- 🎁 **Telegram Gifts** — userbot akkauntidan avtomatik yuboriladi
- 💳 **Avto-to'ldirish** — karta orqali, HUMOcard xabaridan avtomatik tasdiq
- 🌐 **Web App** — barcha xizmatlar zamonaviy mini-ilovada
- 👥 **Referal dastur** — har bir do'st uchun ⭐, 50 ⭐ dan yechish
- 🎉 **Keshbek** — kanaldagi har bir buyurtma ostida bonus tugmasi

</td>
<td width="50%" valign="top">

### 🛡 Tizim va xavfsizlik
- 🤖 **Captcha** — yangi foydalanuvchilar uchun "robot emasman" tekshiruvi
- 📢 **Majburiy obuna** — bir nechta kanal, `EXTRA_CHANNELS` orqali
- 📣 **Buyurtmalar kanali** — har bir bajarilgan buyurtma e'lon qilinadi
- ♻️ **Userbot watchdog** — uzilib qolsa o'zi qayta ulanadi
- 🔁 **Zaxira rejim** — avto-xarid ishlamasa buyurtma adminga o'tadi
- 💾 **JSON baza** — atomik yozish va `.bak` zaxira nusxa
- ✨ **Premium emoji** va rangli tugmalar
- 🔐 Maxfiy ma'lumotlar faqat `.env` / hosting o'zgaruvchilarida

</td>
</tr>
</table>

## 🔄 Qanday ishlaydi

<details open>
<summary><b>⭐ Stars xaridi</b></summary>

```mermaid
sequenceDiagram
    autonumber
    actor M as 👤 Mijoz
    participant B as 🤖 NEON bot
    participant F as 🌐 Fragment
    participant T as 💎 TON hamyon
    participant K as 📣 Buyurtmalar kanali
    M->>B: @username + miqdor
    B->>M: 🧾 Buyurtma: narx va balans
    M->>B: ✅ Tasdiqlash
    B->>B: Balansdan yechish
    B->>F: Stars so'rovi (initBuyStarsRequest)
    F-->>B: To'lov manzili va summa
    B->>T: TON tranzaksiya
    T-->>F: To'lov
    F-->>M: ⭐ Stars tushdi
    B->>M: ✅ Muvaffaqiyatli!
    B->>K: E'lon + 🎁 keshbek tugmasi
```

</details>

<details>
<summary><b>💳 Balansni avtomatik to'ldirish</b></summary>

```mermaid
sequenceDiagram
    autonumber
    actor M as 👤 Mijoz
    participant B as 🤖 NEON bot
    participant U as 👁 Userbot
    participant H as 🏦 @humocardbot
    M->>B: 💳 Balans to'ldirish → 50 000
    B->>M: Karta raqami + aniq summa (5 daqiqa)
    M->>H: Kartaga o'tkazma
    H-->>U: "To'ldirish ➕ 50 000 UZS"
    U->>B: Summa mos keldi
    B->>M: ✅ Balans to'ldirildi!
    Note over B,U: Yangilanish kelmasa ham userbot<br/>bank chatini har 20 s tekshiradi
```

</details>

<details>
<summary><b>🚪 Yangi foydalanuvchi: /start</b></summary>

```mermaid
flowchart LR
    A(["/start"]) --> B{"🤖 Captcha"}
    B -->|"noto'g'ri ×3"| X["⏳ 5 daqiqa blok"]
    B -->|"to'g'ri"| C{"📢 Barcha kanallarga<br/>obuna bo'lganmi?"}
    C -->|"yo'q"| D["Obuna tugmalari + ✅ Tekshirish"]
    D --> C
    C -->|"ha"| E["👥 Referal bonusi"] --> F(["🏠 Asosiy menyu"])
```

</details>

## 🧱 Texnologiyalar

| Qism | Texnologiya | Vazifasi |
|---|---|---|
| 🤖 Bot | [aiogram 3](https://docs.aiogram.dev) | Menyu, FSM, to'lovlar, admin panel |
| 👁 Userbot | [pyrofork](https://github.com/Mayuri-Chan/pyrofork) | Bank xabarlarini kuzatish, Gift yuborish |
| 💎 Blokcheyn | [pytoniq](https://github.com/yungwine/pytoniq) | TON hamyon (WalletV4R2), tranzaksiyalar |
| 🌐 Fragment | cloudscraper | Fragment.com orqali Stars xaridi |
| 🖥 Web App | HTML + Telegram WebApp API | [prem-bot-mini-app](https://github.com/normurodov-org/prem-bot-mini-app) |
| 💾 Baza | JSON | Atomik yozish, `.bak` zaxira |

## 🚀 O'rnatish

### 1. Lokal kompyuterda

```bash
git clone https://github.com/normurodov-org/neon-store-bot.git
cd neon-store-bot
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # qiymatlarni to'ldiring
python bot.py
```

### 2. Railway'da (tavsiya etiladi)

1. **New Project → Deploy from GitHub repo** → shu repozitoriyani tanlang.
2. **Variables** bo'limiga `.env.example` dagi qiymatlarni kiriting.
3. **Volume** qo'shing va `/data` ga ulang — baza (`DB_PATH=/data/users_db.json`) deploy'lar orasida saqlanadi.
4. **Settings → Networking → Generate Domain** — Web App API uchun ochiq domen (PORT va `RAILWAY_PUBLIC_DOMAIN` avtomatik beriladi). Shunda Web App to'ldirish va buyurtmalarni botga o'tmasdan o'zi bajaradi.
5. Deploy tugagach botga `/admin` yozing va **🔑 Userbot ulash (QR)** yoki **📱 Raqam bilan ulash** orqali userbot'ni ulang.

> [!IMPORTANT]
> Botni kanallarga (**@Shop_NeonChannel**, **@Channel_Neon**, **@Shop_NeonOrders**) **admin** qilib qo'shing — aks holda obunani tekshirib bo'lmaydi va buyurtmalar kanalga chiqmaydi.

## ⚙️ Sozlamalar

<details open>
<summary><b>🔑 Majburiy</b></summary>

| O'zgaruvchi | Tavsif |
|---|---|
| `BOT_TOKEN` | @BotFather bergan token |
| `ADMIN_PASSWORD` | `/admin` paroli |
| `API_ID`, `API_HASH` | [my.telegram.org](https://my.telegram.org) → API development tools (userbot uchun) |
| `WALLET_SEED` | TON hamyon (WalletV4R2) 24 so'zi — Stars xaridi uchun (USDT on TON + gaz uchun ozgina TON) |
| `FRAGMENT_STEL_SSID`, `FRAGMENT_STEL_TOKEN`, `FRAGMENT_STEL_TON_TOKEN`, `FRAGMENT_STEL_DT` | fragment.com cookie'lari |
| `FRAGMENT_USER_AGENT` | cookie olingan brauzerning `navigator.userAgent` qiymati |

</details>

<details>
<summary><b>🎛 Ixtiyoriy</b></summary>

| O'zgaruvchi | Standart | Tavsif |
|---|---|---|
| `ADMIN_ID` | — | Asosiy admin Telegram ID |
| `SESSION_STRING` | — | Userbot sessiyasi (admin panel orqali ulasangiz shart emas) |
| `CHANNEL_ID` / `CHANNEL_URL` | `@Shop_NeonChannel` | Asosiy majburiy kanal |
| `EXTRA_CHANNELS` | `@Channel_Neon,@Shop_NeonOrders` | Qo'shimcha majburiy kanallar (vergul bilan) |
| `ORDERS_CHANNEL` | `@Shop_NeonOrders` | Bajarilgan buyurtmalar kanali (bo'sh — o'chiq) |
| `WEBAPP_URL` | `https://prem-bot-mini-app.vercel.app` | Web App manzili |
| `WEBAPP_API_URL` | `https://$RAILWAY_PUBLIC_DOMAIN` | Web App API manzili (bo'lmasa Web App bot orqali ishlaydi) |
| `CARD_NUMBER` / `CARD_HOLDER` | — | To'ldirish uchun karta |
| `TOPUP_SOURCE_CHAT` | `@humocardbot` | Bank bildirishnomalari keladigan bot |
| `DB_PATH` | `/data/users_db.json` | Baza fayli |
| `FRAGMENT_PAYMENT_METHOD` | `usdt` | Stars uchun to'lov: `usdt` yoki `ton` |
| `USDT_MAX_PER_STAR` | `0.03` | 1 ⭐ uchun maksimal USDT (xavfsizlik chegarasi) |
| `MANUAL_FALLBACK` | `1` | Avto-xarid ishlamasa buyurtma adminga (`0` — pul qaytariladi) |
| `USERBOT_START_DELAY` | `30` | Deploy paytida userbot'ni kechiktirish (soniya) |
| `SUPPORT_USERNAME` | `normuzb` | 🆘 Support tugmasi profili |
| `FRAGMENT_COOKIE_HEADER` | — | Brauzerdagi to'liq `cookie` sarlavhasi (eng ishonchli) |
| `FRAGMENT_API_HASH`, `FRAGMENT_PROXY`, `FRAGMENT_ADDRESS` | — | Fragment qo'shimcha sozlamalari |

</details>

> [!CAUTION]
> `.env`, sessiya va hamyon so'zlarini **hech qachon** GitHub'ga yuklamang. `.env` allaqachon `.gitignore` da.

## 🛠️ Admin panel

`/admin` → parol. Panel imkoniyatlari:

| Tugma | Vazifasi |
|---|---|
| ⏸ / ▶️ | Botni vaqtincha to'xtatish / ishga tushirish |
| 📊 **Statistika** | Foydalanuvchilar, to'ldirishlar, savdo, Premium, Gift, referallar |
| 📣 **Xabar yuborish** | Barcha foydalanuvchilarga (matn, rasm, video) |
| 🏆 **Top 20** | Balans yoki referallar soni bo'yicha reyting |
| 🎉 **Konkurs** | Matn, tugma rangi, g'oliblar soni, boshlanish/tugash vaqti; kanallar va botga avtomatik post, tasodifiy g'oliblar |
| ➕ / ➖ **Balans** | Foydalanuvchi balansini o'zgartirish |
| 🚫 / ✅ **Ban** | Bloklash / blokdan chiqarish |
| 💎 **TON balans** | Hamyondagi TON qoldig'i |
| 🔎 **Fragment test** | Fragment ulanishini tekshirish (pul yechilmaydi) |
| 🔑 **Userbot ulash (QR)** · 📱 **Raqam bilan ulash** | Userbot sessiyasini server ichida yaratish |
| 🩺 **Userbot holati** | Userbot ishlayaptimi, oxirgi bank xabari, kutilayotgan to'ldirishlar |

## 📁 Tuzilma

```text
neon-store-bot/
├── bot.py             # butun bot: sozlamalar, baza, handlerlar, userbot, admin panel
├── make_session.py    # userbot sessiyasini kompyuterda yaratish (QR yoki raqam)
├── requirements.txt   # kutubxonalar
├── .env.example       # sozlamalar namunasi
└── assets/            # README uchun animatsiyali SVG'lar
```

## ❓ Muammolar va yechimlar

<details>
<summary><b>💳 Balans avtomatik to'ldirilmayapti</b></summary>

1. `/admin` → **🩺 Userbot holati** ni oching.
2. 🔴 bo'lsa — **🔑 Userbot ulash (QR)** yoki **📱 Raqam bilan ulash**.
3. «Bank xabari tanilmadi» ogohlantirishi kelsa — bank xabar formatini o'zgartirgan; xabar matnini dasturchiga yuboring.

</details>

<details>
<summary><b>🔑 <code>AUTH_KEY_DUPLICATED</code> / sessiya bekor qilindi</b></summary>

Bitta sessiya bir vaqtda ikki joyda (masalan, kompyuter va serverda) ishlatilgan. Sessiyani **faqat serverda**
ishlating va admin panel orqali qayta ulang. Deploy paytida eski va yangi konteyner to'qnashmasligi uchun
`USERBOT_START_DELAY` ni oshiring.

</details>

<details>
<summary><b>⭐ Stars xaridida "Access denied"</b></summary>

Fragment cookie'lari eskirgan. fragment.com'ga qayta kiring, cookie'larni (yoki `FRAGMENT_COOKIE_HEADER` ni)
yangilang va **🔎 Fragment test** bilan tekshiring. `MANUAL_FALLBACK=1` bo'lsa, shu vaqt ichida buyurtmalar
adminga qo'lda bajarish uchun keladi.

</details>

<details>
<summary><b>📢 Hech kim menyuga o'ta olmayapti</b></summary>

Bot majburiy kanallardan birida admin emas. Adminga «Kanal obunasini tekshirib bo'lmayapti» xabari keladi —
unda qaysi kanal ekani yozilgan.

</details>

---

<div align="center">

**NEON STORE** · <a href="https://t.me/shop_neonbot">@shop_neonbot</a> · <a href="https://t.me/Shop_NeonChannel">@Shop_NeonChannel</a> · <a href="https://t.me/normuzb">Support</a>

<sub>Made with 💜 in Uzbekistan</sub>

</div>
# NeonShop_v2.0
