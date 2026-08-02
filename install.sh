#!/usr/bin/env bash
set -Eeuo pipefail
VERSION="3.4.1"


C_RESET="\033[0m"
C_BOLD="\033[1m"
C_BLUE="\033[38;5;39m"
C_CYAN="\033[38;5;45m"
C_GREEN="\033[38;5;42m"
C_YELLOW="\033[38;5;220m"
C_RED="\033[38;5;203m"
C_GRAY="\033[38;5;245m"
C_WHITE="\033[38;5;255m"

banner() {
  clear 2>/dev/null || true
  printf "%b" "${C_CYAN}${C_BOLD}"
  cat <<'BANNER'
╔════════════════════════════════════════════════════════════╗
║                                                            ║
║                         ai-shop                            ║
║                                                            ║
║              Professional Commerce Platform               ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
BANNER
  printf "%b" "${C_RESET}"
  printf "\n%bنسخه حرفه‌ای%b   %b%s%b\n\n" \
    "${C_WHITE}${C_BOLD}" "${C_RESET}" "${C_GRAY}" "$VERSION" "${C_RESET}"
}

line() {
  printf "%b\n" "${C_BLUE}────────────────────────────────────────────────────────────${C_RESET}"
}

step() {
  printf "\n%b[%s/%s]%b %s\n" "${C_CYAN}${C_BOLD}" "$1" "$2" "${C_RESET}" "$3"
}

ok() {
  printf "%b✔%b %s\n" "${C_GREEN}" "${C_RESET}" "$1"
}

warn() {
  printf "%b⚠%b %s\n" "${C_YELLOW}" "${C_RESET}" "$1"
}

fail() {
  printf "%b✖%b %s\n" "${C_RED}" "${C_RESET}" "$1" >&2
}

info() {
  printf "%b●%b %s\n" "${C_CYAN}" "${C_RESET}" "$1"
}

key_value() {
  printf "%-26s : %s\n" "$1" "$2"
}

progress() {
  local current="$1"
  local total="$2"
  local title="$3"
  local width=30
  local filled=$(( current * width / total ))
  local empty=$(( width - filled ))
  local percent=$(( current * 100 / total ))
  printf "%b%3d%%%b [" "${C_CYAN}${C_BOLD}" "$percent" "${C_RESET}"
  printf "%${filled}s" "" | tr ' ' '█'
  printf "%${empty}s" "" | tr ' ' '░'
  printf "] %s\n" "$title"
}

summary_box() {
  printf "\n%b" "${C_GREEN}${C_BOLD}"
  cat <<'SUMMARY'
╔════════════════════════════════════════════════════════════╗
║                  عملیات با موفقیت انجام شد                ║
╚════════════════════════════════════════════════════════════╝
SUMMARY
  printf "%b" "${C_RESET}"
}

trim_value() {
  local value="$1"
  value="${value//$'\r'/}"
  value="${value//$'\n'/}"
  value="${value#\"}"
  value="${value%\"}"
  value="${value#\'}"
  value="${value%\'}"
  printf "%s" "$value" | xargs
}

mask_secret() {
  local value="$1"
  local len="${#value}"
  if [ "$len" -le 10 ]; then
    printf "********"
  else
    printf "%s********%s" "${value:0:5}" "${value: -4}"
  fi
}


[ "$(id -u)" -eq 0 ] || {
  fail "این فایل باید با sudo اجرا شود."
  echo "sudo bash install.sh"
  exit 1
}

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
trap 'fail "نصب در خط $LINENO متوقف شد."; journalctl -u ai-shop -n 40 --no-pager 2>/dev/null || true' ERR

banner
line
info "نصب بومی و پایدار روی Ubuntu 22.04 و Ubuntu 24.04"
info "اطلاعات اصلی فروشگاه در PostgreSQL سرور ذخیره می‌شوند."
line

progress 1 8 "بررسی سیستم و پیش‌نیازها"
step 1 8 "بررسی سیستم و نصب پیش‌نیازها"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-psycopg2 postgresql nginx   certbot python3-certbot-nginx curl openssl git ca-certificates jq
python3 -m py_compile "$PROJECT_DIR/app/main.py"
ok "سیستم و کد برنامه آماده هستند."

progress 2 8 "دریافت تنظیمات فروشگاه"
step 2 8 "اطلاعات فروشگاه"

read -rp "دامنه فروشگاه: " DOMAIN_RAW
DOMAIN="$(trim_value "$DOMAIN_RAW")"
[[ "$DOMAIN" =~ ^[A-Za-z0-9.-]+$ ]] || {
  fail "دامنه معتبر نیست."
  exit 1
}

read -rp "ایمیل دریافت SSL: " SSL_EMAIL_RAW
SSL_EMAIL="$(trim_value "$SSL_EMAIL_RAW")"
[[ "$SSL_EMAIL" == *"@"* ]] || {
  fail "ایمیل SSL معتبر نیست."
  exit 1
}

read -rp "شناسه عددی مدیر تلگرام: " ADMIN_ID_RAW
ADMIN_ID="$(trim_value "$ADMIN_ID_RAW")"
[[ "$ADMIN_ID" =~ ^[0-9]+$ ]] || {
  fail "شناسه مدیر باید عددی باشد."
  exit 1
}

progress 3 8 "اعتبارسنجی توکن ربات"
step 3 8 "دریافت و تأیید توکن Telegram"

while true; do
  read -rsp "توکن ربات را Paste کنید: " BOT_TOKEN_RAW
  echo
  BOT_TOKEN="$(trim_value "$BOT_TOKEN_RAW")"

  if [[ ! "$BOT_TOKEN" =~ ^[0-9]{6,15}:[A-Za-z0-9_-]{30,}$ ]]; then
    fail "فرمت توکن صحیح نیست؛ توکن باید مانند 123456789:ABC... باشد."
    continue
  fi

  info "در حال بررسی توکن با Telegram API..."
  BOT_INFO="$(curl -fsS --connect-timeout 10 --max-time 20     "https://api.telegram.org/bot${BOT_TOKEN}/getMe" 2>/dev/null || true)"

  if echo "$BOT_INFO" | jq -e '.ok == true' >/dev/null 2>&1; then
    BOT_USERNAME="$(echo "$BOT_INFO" | jq -r '.result.username // "unknown"')"
    BOT_NAME="$(echo "$BOT_INFO" | jq -r '.result.first_name // "Telegram Bot"')"
    ok "توکن تأیید شد."
    key_value "نام ربات" "$BOT_NAME"
    key_value "نام کاربری" "@$BOT_USERNAME"
    key_value "توکن ذخیره‌شونده" "$(mask_secret "$BOT_TOKEN")"
    break
  fi

  fail "Telegram API توکن را تأیید نکرد."
  warn "توکن را از BotFather دوباره کپی کنید و بدون فاصله وارد کنید."
done

read -rp "Merchant ID زرین‌پال (اختیاری): " MERCHANT_RAW
MERCHANT="$(trim_value "$MERCHANT_RAW")"
read -rp "شماره کارت: " CARD_RAW
CARD="$(trim_value "$CARD_RAW")"
read -rp "نام صاحب کارت: " HOLDER_RAW
HOLDER="$(trim_value "$HOLDER_RAW")"

DB_PASS="$(openssl rand -hex 24)"
WEBHOOK_SECRET="$(openssl rand -hex 24)"
ADMIN_PASS="$(openssl rand -base64 30 | tr -d '/+=' | head -c 24)"

progress 4 8 "ساخت تنظیمات امن"
step 4 8 "ساخت فایل تنظیمات"

cat > "$PROJECT_DIR/.env" <<EOF
APP_HOST=127.0.0.1
APP_PORT=3000
DOMAIN=${DOMAIN}
PUBLIC_URL=https://${DOMAIN}
DB_NAME=ai_shop
DB_USER=ai_shop
DB_PASSWORD=${DB_PASS}
DB_HOST=127.0.0.1
DB_PORT=5432
TELEGRAM_BOT_TOKEN=${BOT_TOKEN}
TELEGRAM_WEBHOOK_SECRET=${WEBHOOK_SECRET}
ADMIN_TELEGRAM_ID=${ADMIN_ID}
ADMIN_USERNAME=admin
ADMIN_PASSWORD=${ADMIN_PASS}
ZARINPAL_MERCHANT_ID=${MERCHANT}
ZARINPAL_SANDBOX=true
CURRENCY=IRR
CARD_NUMBER=${CARD}
CARD_HOLDER=${HOLDER}
SHOP_TIMEZONE=Asia/Tehran
EOF
chmod 600 "$PROJECT_DIR/.env"
ok "تنظیمات با دسترسی 600 ذخیره شدند."

progress 5 8 "آماده‌سازی PostgreSQL"
step 5 8 "دیتابیس PostgreSQL"

systemctl enable --now postgresql nginx >/dev/null
cd /tmp

if runuser -u postgres -- psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='ai_shop'" | grep -q '^1$'; then
  runuser -u postgres -- psql -v ON_ERROR_STOP=1     -c "ALTER USER ai_shop WITH LOGIN PASSWORD '${DB_PASS}';" >/dev/null
else
  runuser -u postgres -- psql -v ON_ERROR_STOP=1     -c "CREATE USER ai_shop WITH LOGIN PASSWORD '${DB_PASS}';" >/dev/null
fi

if ! runuser -u postgres -- psql -tAc "SELECT 1 FROM pg_database WHERE datname='ai_shop'" | grep -q '^1$'; then
  runuser -u postgres -- createdb -O ai_shop ai_shop
fi

runuser -u postgres -- psql -v ON_ERROR_STOP=1   -c "ALTER DATABASE ai_shop OWNER TO ai_shop;" >/dev/null

PGPASSWORD="$DB_PASS" psql -h 127.0.0.1 -U ai_shop -d ai_shop   -c "SELECT 1;" >/dev/null
ok "اتصال PostgreSQL با موفقیت آزمایش شد."

progress 6 8 "نصب سرویس و پنل"
step 6 8 "نصب برنامه"

id ai-shop >/dev/null 2>&1 || useradd --system   --home-dir /opt/ai-shop --create-home   --shell /usr/sbin/nologin ai-shop

rm -rf /opt/ai-shop/app /opt/ai-shop/docs
mkdir -p /opt/ai-shop
cp -a "$PROJECT_DIR/app" /opt/ai-shop/
[ -d "$PROJECT_DIR/docs" ] && cp -a "$PROJECT_DIR/docs" /opt/ai-shop/
cp "$PROJECT_DIR/.env" /opt/ai-shop/.env

chown -R ai-shop:ai-shop /opt/ai-shop
chmod 750 /opt/ai-shop
chmod 600 /opt/ai-shop/.env

cp "$PROJECT_DIR/systemd/ai-shop.service" /etc/systemd/system/ai-shop.service
systemctl daemon-reload
systemctl enable ai-shop >/dev/null
ok "سرویس ai-shop نصب شد."

progress 7 8 "تنظیم دامنه، Nginx و SSL"
step 7 8 "وب‌سرور و دامنه"

sed "s/__DOMAIN__/${DOMAIN}/g"   "$PROJECT_DIR/nginx/ai-shop.conf"   > /etc/nginx/sites-available/ai-shop

ln -sf /etc/nginx/sites-available/ai-shop /etc/nginx/sites-enabled/ai-shop
rm -f /etc/nginx/sites-enabled/default

nginx -t
systemctl reload nginx
systemctl restart ai-shop

READY=0
for _ in $(seq 1 45); do
  if curl -fsS http://127.0.0.1:3000/health >/dev/null 2>&1; then
    READY=1
    break
  fi
  sleep 1
done

[ "$READY" -eq 1 ] || {
  fail "سرویس روی پورت 3000 آماده نشد."
  journalctl -u ai-shop -n 100 --no-pager
  exit 1
}
ok "برنامه سالم و فعال است."

if getent hosts "$DOMAIN" >/dev/null 2>&1; then
  if certbot --nginx -d "$DOMAIN" --non-interactive     --agree-tos -m "$SSL_EMAIL" --redirect >/dev/null 2>&1; then
    ok "گواهی SSL نصب شد."
  else
    warn "SSL نصب نشد؛ اتصال DNS یا محدودیت Certbot را بررسی کنید."
  fi
else
  warn "دامنه هنوز Resolve نمی‌شود؛ SSL فعلاً نصب نشد."
fi

progress 8 8 "ثبت Webhook و پایان نصب"
step 8 8 "اتصال ربات تلگرام"

WEBHOOK_RESPONSE="$(curl -sS -X POST   "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook"   -H "Content-Type: application/json"   -d "{\"url\":\"https://${DOMAIN}/telegram/webhook\",\"secret_token\":\"${WEBHOOK_SECRET}\",\"allowed_updates\":[\"message\",\"callback_query\"]}"   || true)"

if echo "$WEBHOOK_RESPONSE" | jq -e '.ok == true' >/dev/null 2>&1; then
  ok "Webhook تلگرام ثبت شد."
else
  fail "ثبت Webhook ناموفق بود."
  echo "$WEBHOOK_RESPONSE"
  warn "بعد از فعال‌شدن SSL، دوباره install.sh یا repair.sh را اجرا کنید."
fi

line
summary_box
key_value "نسخه فعال" "3.0.0"
key_value "ربات" "@$BOT_USERNAME"
key_value "پنل مدیریت" "https://${DOMAIN}/admin"
key_value "راهنما" "https://${DOMAIN}/admin/help"
key_value "مدیریت دیتابیس" "https://${DOMAIN}/admin/database"
key_value "نام کاربری پنل" "admin"
key_value "رمز پنل" "$ADMIN_PASS"
echo
warn "رمز پنل را در محل امن نگهداری کنید."
warn "توکن ربات هرگز روی صفحه یا داخل GitHub نمایش داده نمی‌شود."
