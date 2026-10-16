#!/usr/bin/env bash
# Avto to'ldirish va gift yuborish oqimlarining testlari.
# Ishga tushirish:  bash tests/run.sh
set -e
cd "$(dirname "$0")/.."

echo "=== 1/45 Avto to'ldirish (bank xabari parsing + balansga qo'shish) ==="

echo

rm -f /tmp/_t_topup.json /tmp/_t_topup.json.bak /tmp/_t_topup.json.tmp
DB_PATH=/tmp/_t_topup.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  CARD_NUMBER="${CARD_NUMBER:-9860 1701 1569 3682}" \
  python3 tests/test_topup.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo "=== 2/45 Qisman to‘ldirish (boshqa summa) ==="
rm -f /tmp/_t_partial.json /tmp/_t_partial.json.bak /tmp/_t_partial.json.tmp
DB_PATH=/tmp/_t_partial.json BOT_TOKEN=123:F API_ID=0 API_HASH= \
  python3 tests/test_partial_topup.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo "=== 3/45 HAQIQIY HUMO format (sizning bank xabaringiz) ==="
rm -f /tmp/_t_real.json /tmp/_t_real.json.bak /tmp/_t_real.json.tmp
DB_PATH=/tmp/_t_real.json API_ID=1 API_HASH=x \
  python3 tests/test_real_humo.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo
echo "=== 4/45 Userbot ulash (telefon / 2FA / QR) ==="
# DIQQAT: bu qatorda avval qoldiq `/tmp/_t_partial.json` bor edi va bash uni
# BUYRUQ deb bajarishga urinib, butun testni o'tkazib yuborardi (test 4
# sokin o'tkazib yuborilardi!). Faqat DB_PATH kerak.
rm -f /tmp/_t_login.json /tmp/_t_login.json.bak /tmp/_t_login.json.tmp
DB_PATH=/tmp/_t_login.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_login.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo "=== 5/45 Gift worker (userbot orqali yuborish) ==="
rm -f /tmp/_t_gift.json /tmp/_t_gift.json.bak /tmp/_t_gift.json.tmp
DB_PATH=/tmp/_t_gift.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_gift.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo "=== 6/45 Gift tanlash (emos bo‘yicha), xabar matni, anonim ==="
rm -f /tmp/_t_giftmatch.json /tmp/_t_giftmatch.json.bak /tmp/_t_giftmatch.json.tmp
DB_PATH=/tmp/_t_giftmatch.json API_ID=0 API_HASH= BOT_TOKEN=123:F \
  python3 tests/test_gift_matching.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING|ERROR"

echo
echo "=== 7/45 BITTA userbot + kanal xabari formati ==="
rm -f /tmp/_t_giftacct.json /tmp/_t_giftacct.json.bak /tmp/_t_giftacct.json.tmp
DB_PATH=/tmp/_t_giftacct.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_gift_account.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo "=== 8/45 Gift xatolari: doimiy vs ichki (buyurtma yopilmasin) ==="
rm -f /tmp/_t_ge.json /tmp/_t_ge.json.bak /tmp/_t_ge.json.tmp
DB_PATH=/tmp/_t_ge.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_gift_errors.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING|ERROR"

echo
echo "=== 9/45 SESSION_STRING validatsiyasi (362 belgi) ==="
rm -f /tmp/_t_sess.json /tmp/_t_sess.json.bak /tmp/_t_sess.json.tmp
DB_PATH=/tmp/_t_sess.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_session.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo "=== 10/45 MENYULAR — /start va Giftlar chiziladimi? ==="
rm -f /tmp/_t_menu.json /tmp/_t_menu.json.bak /tmp/_t_menu.json.tmp
DB_PATH=/tmp/_t_menu.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_menus.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo "=== 11/45 Gift avtomatik yuborilishi (matn, anonim, t.me, tiklash) ==="
rm -f /tmp/_t_as.json /tmp/_t_as.json.bak /tmp/_t_as.json.tmp
DB_PATH=/tmp/_t_as.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_gift_autosend.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING|ERROR"

echo
echo "=== 12/45 SESSION bazada saqlanadi + gift diagnostikasi ==="
rm -f /tmp/_t_sd.json /tmp/_t_sd.json.bak /tmp/_t_sd.json.tmp
DB_PATH=/tmp/_t_sd.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_session_db.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo "=== 13/45 Gift bekor qilish (pul qaytariladi) ==="
rm -f /tmp/_t_gc.json /tmp/_t_gc.json.bak /tmp/_t_gc.json.tmp
DB_PATH=/tmp/_t_gc.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_gift_cancel.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING|ERROR"

echo
echo "=== 14/45 Sessiya kaliti bekor qilingan (AUTH_KEY_UNREGISTERED) ==="
rm -f /tmp/_t_sr.json /tmp/_t_sr.json.bak /tmp/_t_sr.json.tmp
DB_PATH=/tmp/_t_sr.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_session_revoked.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING|ERROR"

echo
echo "=== 15/45 SERVER ISHGA TUSHADI + NFT yangilanishi (TDZ crash ga qarshi) ==="
# Bu test server.ts ni REAL ishga tushiradi. td/tsx build runtime
# xatolarini (masalan "Cannot access X before initialization") ushlab
# olmaydi — production'da esa butun serverni o'ldiradi.
python3 tests/test_server_boot.py 2>&1 | grep -vE "TgCrypto"

echo
echo "=== 16/45 BEKOR QILISH TUGMASI — bosilishidan natijagacha ==="
rm -f /tmp/_t_cu.json /tmp/_t_cu.json.bak /tmp/_t_cu.json.tmp
DB_PATH=/tmp/_t_cu.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_gift_cancel_ui.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING|ERROR"

echo
echo "=== 17/45 TO'LOV BEKOR QILISH + MUDDAT (0:00 muammosi) ==="
rm -f /tmp/_t_tc.json /tmp/_t_tc.json.bak /tmp/_t_tc.json.tmp
DB_PATH=/tmp/_t_tc.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_topup_cancel.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING|ERROR"

echo
echo "=== 18/45 NFT RENT — hisob, admin oqimi, WebApp bo'limi ==="
rm -f /tmp/_t_nft.json /tmp/_t_nft.json.bak
DB_PATH=/tmp/_t_nft.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_nft_rent.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo "=== 19/45 NFT DIZAYN va KONGASTR (portal, --accent, WCAG AA) ==="
python3 tests/test_nft_design.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo "=== 20/45 NFT ADMIN OQIMI — 2 bosqich + ochish/yopish ==="
rm -f /tmp/_af.json /tmp/_af.json.bak
DB_PATH=/tmp/_af.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_nft_admin_flow.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo "=== 21/45 NFT BUYURTMA HAYOTI — tugmalar, race, ikki tomon, filtrlar ==="
rm -f /tmp/_lc.json /tmp/_lc.json.bak
DB_PATH=/tmp/_lc.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_nft_order_lifecycle.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo "=== 22/45 NFT XABARI @saidovManajer ga (userbot, 3 ta sabab tuzatildi) ==="
rm -f /tmp/_nm.json /tmp/_nm.json.bak
DB_PATH=/tmp/_nm.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_nft_notify_manager.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo "=== 23/45 PARSE_MODE (userbot enum rad) + HOME NFT KARTA ==="
# `bot` ni import qiladi (xabar matnini tekshirish uchun) — env kerak
rm -f /tmp/_pmt.json /tmp/_pmt.json.bak
DB_PATH=/tmp/_pmt.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_parse_mode_and_home_nft.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo "=== 24/45 NFT RASMI TINIQ (1500x1500 Fragment CDN) ==="
rm -f /tmp/_t_hdquality.json /tmp/_t_hdquality.json.bak
DB_PATH=/tmp/_t_hdquality.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_nft_image_quality.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo "=== 25/45 NFT RASMI YO'QOLMASIN (sekin internet, 7s kechikish) ==="
python3 tests/test_nft_image_persist.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo "=== 26/45 NFT KARTALARI — rasm uchib ketmasin (flicker/jitter) ==="
python3 tests/test_nft_flicker.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo "=== 27/45 NFT RASM — Telegram sahifasidan AVTOMATIK (og:image) ==="
rm -f /tmp/_pv.json /tmp/_pv.json.bak
DB_PATH=/tmp/_pv.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_nft_preview.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo "=== 28/45 NFT RASMI — admin qo'shgan NFT WebApp'da ko'rinadi ==="
rm -f /tmp/_t_ni.json /tmp/_t_ni.json.bak
DB_PATH=/tmp/_t_ni.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_nft_image.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo "=== 29/45 NFT IJARAGA OLISH — buyurtma + admin/menejerga xabar ==="
rm -f /tmp/_t_nr.json /tmp/_t_nr.json.bak
DB_PATH=/tmp/_t_nr.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_nft_rent_order.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo "=== 30/45 O'LIK TUGMALAR — bosiladi, hech narsa bo'lmaydimi? ==="
python3 tests/test_dead_buttons.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo "=== 31/45 TEST YORDAMCHILARI — izohlarni to'g'ri ajratish ==="
python3 tests/test_helpers.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo "=== 32/45 STARS SOTUV + PREMIUM — to'liq pul oqimi ==="
rm -f /tmp/_t_sp.json /tmp/_t_sp.json.bak /tmp/_t_sp.json.tmp
DB_PATH=/tmp/_t_sp.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_sell_and_premium.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo "=== 33/45 E2E — mijoz oqimi haqiqiy server orqali ==="
python3 tests/test_e2e_customer.py 2>&1 | grep -vE "TgCrypto"

echo
echo "=== 34/45 STARS BAJARILMADI — avtomatik qayta urish + qaytarish ==="
DB_PATH=/tmp/_t_sf.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_star_failure.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo "=== 35/45 BROWSER KIRISH — Telegram Login Widget + sessiya ==="
python3 tests/test_login_widget.py 2>&1 | grep -vE "TgCrypto"

echo
echo "=== 36/45 RESPONSIVE — desktopda telefon ko'rinishi bo'lmasin ==="
python3 tests/test_responsive_layout.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo "=== 37/45 SESSIYA SAQLANISHI — bot.py o'chirmasin ==="
python3 tests/test_session_persistence.py 2>&1 | grep -vE "TgCrypto"

echo
echo "=== 38/45 TELEGRAM WIDGET KONTRAKTI — data-onauth SHART ==="
python3 tests/test_login_widget_contract.py 2>&1 | grep -vE "TgCrypto"

echo
echo "=== 39/45 WEB LOGIN — deep link end-to-end (popup'siz) ==="
python3 tests/test_deeplink_login.py 2>&1 | grep -vE "TgCrypto"

echo
echo "=== 40/45 APPLE LIQUID GLASS + SCROLL ==="
python3 tests/test_liquid_glass.py 2>&1 | grep -vE "TgCrypto"

echo
echo "=== 41/45 TELEGRAM LOGIN — rasmiy OAuth end-to-end (popup'siz) ==="
python3 tests/test_login_e2e.py 2>&1 | grep -vE "TgCrypto"

echo
echo "=== 42/45 NAVIGATSIYA KONTENT USTIGA CHIQMAYDI (build CSS darajasida) ==="
python3 tests/test_rail_clearance.py 2>&1 | grep -vE "TgCrypto"

echo
echo "=== 43/45 NFT: admin narxi + bot -> WebApp NFT boʸlimi ==="
python3 tests/test_nft_admin_price.py 2>&1 | grep -vE "TgCrypto"

echo
echo "=== 44/45 NFT NETWORK FEE — uchta manba bir xil ==="
python3 tests/test_nft_fee.py 2>&1 | grep -vE "TgCrypto"

echo
echo "=== 45/45 BOT TOʼXTATISH QALQONI + SAYT YOʼLLARI ==="
python3 tests/test_bot_pause_and_routes.py 2>&1 | grep -vE "TgCrypto"

rm -f /tmp/_t_*.json /tmp/_t_*.json.bak /tmp/_t_*.json.tmp