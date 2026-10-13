#!/usr/bin/env bash
# Avto to'ldirish va gift yuborish oqimlarining testlari.
# Ishga tushirish:  bash tests/run.sh
set -e
cd "$(dirname "$0")/.."

echo "=== 1/19 Avto to'ldirish (bank xabari parsing + balansga qo'shish) ==="
rm -f /tmp/_t_topup.json /tmp/_t_topup.json.bak /tmp/_t_topup.json.tmp
DB_PATH=/tmp/_t_topup.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  CARD_NUMBER="${CARD_NUMBER:-9860 1701 1569 3682}" \
  python3 tests/test_topup.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo "=== 2/19 Qisman to‘ldirish (boshqa summa) ==="
rm -f /tmp/_t_partial.json /tmp/_t_partial.json.bak /tmp/_t_partial.json.tmp
DB_PATH=/tmp/_t_partial.json BOT_TOKEN=123:F API_ID=0 API_HASH= \
  python3 tests/test_partial_topup.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo "=== 3/19 HAQIQIY HUMO format (sizning bank xabaringiz) ==="
rm -f /tmp/_t_real.json /tmp/_t_real.json.bak /tmp/_t_real.json.tmp
DB_PATH=/tmp/_t_real.json API_ID=1 API_HASH=x \
  python3 tests/test_real_humo.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo
echo "=== 4/19 Userbot ulash (telefon / 2FA / QR) ==="
# DIQQAT: bu qatorda avval qoldiq `/tmp/_t_partial.json` bor edi va bash uni
# BUYRUQ deb bajarishga urinib, butun testni o'tkazib yuborardi (test 4
# sokin o'tkazib yuborilardi!). Faqat DB_PATH kerak.
rm -f /tmp/_t_login.json /tmp/_t_login.json.bak /tmp/_t_login.json.tmp
DB_PATH=/tmp/_t_login.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_login.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo "=== 5/19 Gift worker (userbot orqali yuborish) ==="
rm -f /tmp/_t_gift.json /tmp/_t_gift.json.bak /tmp/_t_gift.json.tmp
DB_PATH=/tmp/_t_gift.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_gift.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo "=== 6/19 Gift tanlash (emos bo‘yicha), xabar matni, anonim ==="
rm -f /tmp/_t_giftmatch.json /tmp/_t_giftmatch.json.bak /tmp/_t_giftmatch.json.tmp
DB_PATH=/tmp/_t_giftmatch.json API_ID=0 API_HASH= BOT_TOKEN=123:F \
  python3 tests/test_gift_matching.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING|ERROR"

echo
echo "=== 7/19 BITTA userbot + kanal xabari formati ==="
rm -f /tmp/_t_giftacct.json /tmp/_t_giftacct.json.bak /tmp/_t_giftacct.json.tmp
DB_PATH=/tmp/_t_giftacct.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_gift_account.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo "=== 8/19 Gift xatolari: doimiy vs ichki (buyurtma yopilmasin) ==="
rm -f /tmp/_t_ge.json /tmp/_t_ge.json.bak /tmp/_t_ge.json.tmp
DB_PATH=/tmp/_t_ge.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_gift_errors.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING|ERROR"

echo
echo "=== 9/19 SESSION_STRING validatsiyasi (362 belgi) ==="
rm -f /tmp/_t_sess.json /tmp/_t_sess.json.bak /tmp/_t_sess.json.tmp
DB_PATH=/tmp/_t_sess.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_session.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo "=== 10/19 MENYULAR — /start va Giftlar chiziladimi? ==="
rm -f /tmp/_t_menu.json /tmp/_t_menu.json.bak /tmp/_t_menu.json.tmp
DB_PATH=/tmp/_t_menu.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_menus.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo "=== 11/19 Gift avtomatik yuborilishi (matn, anonim, t.me, tiklash) ==="
rm -f /tmp/_t_as.json /tmp/_t_as.json.bak /tmp/_t_as.json.tmp
DB_PATH=/tmp/_t_as.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_gift_autosend.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING|ERROR"

echo
echo "=== 12/19 SESSION bazada saqlanadi + gift diagnostikasi ==="
rm -f /tmp/_t_sd.json /tmp/_t_sd.json.bak /tmp/_t_sd.json.tmp
DB_PATH=/tmp/_t_sd.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_session_db.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo "=== 13/19 Gift bekor qilish (pul qaytariladi) ==="
rm -f /tmp/_t_gc.json /tmp/_t_gc.json.bak /tmp/_t_gc.json.tmp
DB_PATH=/tmp/_t_gc.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_gift_cancel.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING|ERROR"

echo
echo "=== 14/19 Sessiya kaliti bekor qilingan (AUTH_KEY_UNREGISTERED) ==="
rm -f /tmp/_t_sr.json /tmp/_t_sr.json.bak /tmp/_t_sr.json.tmp
DB_PATH=/tmp/_t_sr.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_session_revoked.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING|ERROR"

echo
echo "=== 15/19 SERVER HAQIQATAN ISHGA TUSHADI? (TDZ crash ga qarshi) ==="
# Bu test server.ts ni REAL ishga tushiradi. td/tsx build runtime
# xatolarini (masalan "Cannot access X before initialization") ushlab
# olmaydi — production'da esa butun serverni o'ldiradi.
python3 tests/test_server_boot.py 2>&1 | grep -vE "TgCrypto"

echo
echo "=== 16/19 BEKOR QILISH TUGMASI — bosilishidan natijagacha ==="
rm -f /tmp/_t_cu.json /tmp/_t_cu.json.bak /tmp/_t_cu.json.tmp
DB_PATH=/tmp/_t_cu.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_gift_cancel_ui.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING|ERROR"

echo
echo "=== 17/19 TO'LOV BEKOR QILISH + MUDDAT (0:00 muammosi) ==="
rm -f /tmp/_t_tc.json /tmp/_t_tc.json.bak /tmp/_t_tc.json.tmp
DB_PATH=/tmp/_t_tc.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_topup_cancel.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING|ERROR"

echo
echo "=== 18/19 NFT RENT — hisob, admin oqimi, WebApp bo'limi ==="
rm -f /tmp/_t_nft.json /tmp/_t_nft.json.bak
DB_PATH=/tmp/_t_nft.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_nft_rent.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo "=== 19/19 NFT IJARAGA OLISH — buyurtma + admin/menejerga xabar ==="
rm -f /tmp/_t_nr.json /tmp/_t_nr.json.bak
DB_PATH=/tmp/_t_nr.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_nft_rent_order.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

rm -f /tmp/_t_*.json /tmp/_t_*.json.bak /tmp/_t_*.json.tmp