#!/usr/bin/env bash
# Avto to'ldirish va gift yuborish oqimlarining testlari.
# Ishga tushirish:  bash tests/run.sh
set -e
cd "$(dirname "$0")/.."

echo "=== 1/13 Avto to'ldirish (bank xabari parsing + balansga qo'shish) ==="
rm -f /tmp/_t_topup.json /tmp/_t_topup.json.bak /tmp/_t_topup.json.tmp
DB_PATH=/tmp/_t_topup.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  CARD_NUMBER="${CARD_NUMBER:-9860 1701 1569 3682}" \
  python3 tests/test_topup.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo "=== 2/13 Qisman to‘ldirish (boshqa summa) ==="
rm -f /tmp/_t_partial.json /tmp/_t_partial.json.bak /tmp/_t_partial.json.tmp
DB_PATH=/tmp/_t_partial.json BOT_TOKEN=123:F API_ID=0 API_HASH= \
  python3 tests/test_partial_topup.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo "=== 3/13 HAQIQIY HUMO format (sizning bank xabaringiz) ==="
rm -f /tmp/_t_real.json /tmp/_t_real.json.bak /tmp/_t_real.json.tmp
DB_PATH=/tmp/_t_real.json API_ID=1 API_HASH=x \
  python3 tests/test_real_humo.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo
echo "=== 4/13 Userbot ulash (telefon / 2FA / QR) ==="
rm -f /tmp/_t_login.json /tmp/_t_partial.json
DB_PATH=/tmp/_t_login.json /tmp/_t_partial.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_login.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo "=== 5/13 Gift worker (userbot orqali yuborish) ==="
rm -f /tmp/_t_gift.json /tmp/_t_gift.json.bak /tmp/_t_gift.json.tmp
DB_PATH=/tmp/_t_gift.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_gift.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo "=== 6/13 Gift tanlash (emos bo‘yicha), xabar matni, anonim ==="
rm -f /tmp/_t_giftmatch.json /tmp/_t_giftmatch.json.bak /tmp/_t_giftmatch.json.tmp
DB_PATH=/tmp/_t_giftmatch.json API_ID=0 API_HASH= BOT_TOKEN=123:F \
  python3 tests/test_gift_matching.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING|ERROR"

echo
echo "=== 7/13 BITTA userbot + kanal xabari formati ==="
rm -f /tmp/_t_giftacct.json /tmp/_t_giftacct.json.bak /tmp/_t_giftacct.json.tmp
DB_PATH=/tmp/_t_giftacct.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_gift_account.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo "=== 8/13 Gift xatolari: doimiy vs ichki (buyurtma yopilmasin) ==="
rm -f /tmp/_t_ge.json /tmp/_t_ge.json.bak /tmp/_t_ge.json.tmp
DB_PATH=/tmp/_t_ge.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_gift_errors.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING|ERROR"

echo
echo "=== 9/13 SESSION_STRING validatsiyasi (362 belgi) ==="
rm -f /tmp/_t_sess.json /tmp/_t_sess.json.bak /tmp/_t_sess.json.tmp
DB_PATH=/tmp/_t_sess.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_session.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo "=== 10/13 MENYULAR — /start va Giftlar chiziladimi? ==="
rm -f /tmp/_t_menu.json /tmp/_t_menu.json.bak /tmp/_t_menu.json.tmp
DB_PATH=/tmp/_t_menu.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_menus.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo "=== 11/13 Gift avtomatik yuborilishi (matn, anonim, t.me, tiklash) ==="
rm -f /tmp/_t_as.json /tmp/_t_as.json.bak /tmp/_t_as.json.tmp
DB_PATH=/tmp/_t_as.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_gift_autosend.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING|ERROR"

echo
echo "=== 12/13 SESSION bazada saqlanadi + gift diagnostikasi ==="
rm -f /tmp/_t_sd.json /tmp/_t_sd.json.bak /tmp/_t_sd.json.tmp
DB_PATH=/tmp/_t_sd.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_session_db.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING"

echo
echo "=== 13/13 Gift bekor qilish (pul qaytariladi) ==="
rm -f /tmp/_t_gc.json /tmp/_t_gc.json.bak /tmp/_t_gc.json.tmp
DB_PATH=/tmp/_t_gc.json API_ID=1 API_HASH=x BOT_TOKEN=123:F \
  python3 tests/test_gift_cancel.py 2>&1 | grep -vE "TgCrypto|INFO|WARNING|ERROR"

rm -f /tmp/_t_*.json /tmp/_t_*.json.bak /tmp/_t_*.json.tmp