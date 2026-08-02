#!/usr/bin/env bash
set -Eeuo pipefail
VERSION="2.2.0"


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
  printf "${C_CYAN}${C_BOLD}"
  cat <<'BANNER'
╔════════════════════════════════════════════════════════════╗
║                                                            ║
║                         ai-shop                            ║
║                                                            ║
║            Telegram AI Commerce Platform                  ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
BANNER
  printf "${C_RESET}"
  printf "\n${C_WHITE}${C_BOLD}  Professional Edition${C_RESET}"
  printf "   ${C_GRAY}Version %s${C_RESET}\n\n" "$VERSION"
}

section() {
  printf "\n${C_BLUE}${C_BOLD}┌─ %s${C_RESET}\n" "$1"
}

step() {
  printf "${C_CYAN}${C_BOLD}│  [%s/%s]${C_RESET} %s\n" "$1" "$2" "$3"
}

ok() {
  printf "${C_GREEN}│  ✔${C_RESET} %s\n" "$1"
}

warn() {
  printf "${C_YELLOW}│  ⚠${C_RESET} %s\n" "$1"
}

fail() {
  printf "${C_RED}│  ✖${C_RESET} %s\n" "$1"
}

info() {
  printf "${C_CYAN}│  ●${C_RESET} %s\n" "$1"
}

end_section() {
  printf "${C_BLUE}${C_BOLD}└──────────────────────────────────────────────────────────${C_RESET}\n"
}

summary_box() {
  printf "\n${C_GREEN}${C_BOLD}"
  printf "╔════════════════════════════════════════════════════════════╗\n"
  printf "║                    عملیات موفق بود                        ║\n"
  printf "╚════════════════════════════════════════════════════════════╝\n"
  printf "${C_RESET}"
}

[ "$(id -u)" -eq 0 ] || {
  fail "این فایل باید با sudo اجرا شود."
  echo "sudo bash install.sh"
  exit 1
}

trap 'fail "نصب در خط $LINENO متوقف شد."; journalctl -u ai-shop -n 30 --no-pager 2>/dev/null || true' ERR
banner
line
info "نصب بومی بدون Docker؛ مناسب Ubuntu 22.04 و 24.04"
line

step 1 8 "بررسی سیستم و نصب پیش‌نیازها"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-psycopg2 postgresql nginx   certbot python3-certbot-nginx curl openssl git ca-certificates
ok "پیش‌نیازها آماده شدند."

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 -m py_compile "$PROJECT_DIR/app/main.py"
ok "کد Python از نظر نحوی معتبر است."

step 2 8 "دریافت تنظیمات فروشگاه"
printf "${C_GRAY}اطلاعات حساس روی صفحه نمایش داده نمی‌شوند.${C_RESET}
"
read -rp "دامنه فروشگاه (مثال shop.example.com): " DOMAIN
read -rp "ایمیل SSL: " SSL_EMAIL
read -rsp "توکن ربات تلگرام: " BOT_TOKEN; echo
read -rp "شناسه عددی مدیر تلگرام: " ADMIN_ID
read -rp "Merchant ID زرین‌پال (اختیاری): " MERCHANT
read -rp "شماره کارت: " CARD
read -rp "نام صاحب کارت: " HOLDER

[[ "$DOMAIN" =~ ^[A-Za-z0-9.-]+$ ]] || { fail "دامنه معتبر نیست."; exit 1; }
[[ "$ADMIN_ID" =~ ^[0-9]+$ ]] || { fail "شناسه مدیر باید عددی باشد."; exit 1; }
[[ -n "$BOT_TOKEN" ]] || { fail "توکن ربات خالی است."; exit 1; }

DB_PASS="$(openssl rand -hex 24)"
WEBHOOK_SECRET="$(openssl rand -hex 24)"
ADMIN_PASS="$(openssl rand -base64 30 | tr -d '/+=' | head -c 24)"

step 3 8 "ساخت تنظیمات امن"
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
ok "فایل تنظیمات امن ساخته شد."

step 4 8 "آماده‌سازی PostgreSQL"
systemctl enable --now postgresql nginx >/dev/null
cd /tmp
if runuser -u postgres -- psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='ai_shop'" | grep -q '^1$'; then
  runuser -u postgres -- psql -v ON_ERROR_STOP=1 -c "ALTER USER ai_shop WITH LOGIN PASSWORD '${DB_PASS}';" >/dev/null
else
  runuser -u postgres -- psql -v ON_ERROR_STOP=1 -c "CREATE USER ai_shop WITH LOGIN PASSWORD '${DB_PASS}';" >/dev/null
fi
if ! runuser -u postgres -- psql -tAc "SELECT 1 FROM pg_database WHERE datname='ai_shop'" | grep -q '^1$'; then
  runuser -u postgres -- createdb -O ai_shop ai_shop
fi
runuser -u postgres -- psql -v ON_ERROR_STOP=1 -c "ALTER DATABASE ai_shop OWNER TO ai_shop;" >/dev/null
PGPASSWORD="$DB_PASS" psql -h 127.0.0.1 -U ai_shop -d ai_shop -c "SELECT 1;" >/dev/null
ok "دیتابیس متصل و آماده است."

step 5 8 "نصب برنامه و سرویس"
id ai-shop >/dev/null 2>&1 || useradd --system --home-dir /opt/ai-shop --create-home --shell /usr/sbin/nologin ai-shop
rm -rf /opt/ai-shop/app /opt/ai-shop/docs
mkdir -p /opt/ai-shop
cp -a "$PROJECT_DIR/app" /opt/ai-shop/
cp -a "$PROJECT_DIR/docs" /opt/ai-shop/
cp "$PROJECT_DIR/.env" /opt/ai-shop/.env
chown -R ai-shop:ai-shop /opt/ai-shop
chmod 750 /opt/ai-shop
chmod 600 /opt/ai-shop/.env
cp "$PROJECT_DIR/systemd/ai-shop.service" /etc/systemd/system/ai-shop.service
systemctl daemon-reload
systemctl enable ai-shop >/dev/null
ok "سرویس systemd نصب شد."

step 6 8 "تنظیم Nginx و دامنه"
sed "s/__DOMAIN__/${DOMAIN}/g" "$PROJECT_DIR/nginx/ai-shop.conf" > /etc/nginx/sites-available/ai-shop
ln -sf /etc/nginx/sites-available/ai-shop /etc/nginx/sites-enabled/ai-shop
rm -f /etc/nginx/sites-enabled/default
nginx -t >/dev/null
systemctl reload nginx
systemctl restart ai-shop
ok "وب‌سرور و برنامه اجرا شدند."

step 7 8 "بررسی سلامت و دریافت SSL"
READY=0
for _ in $(seq 1 45); do
  if curl -fsS http://127.0.0.1:3000/health >/dev/null 2>&1; then READY=1; break; fi
  sleep 1
done
if [ "$READY" -ne 1 ]; then
  fail "برنامه روی پورت 3000 آماده نشد."
  journalctl -u ai-shop -n 100 --no-pager
  exit 1
fi
ok "برنامه سالم است."

if getent hosts "$DOMAIN" >/dev/null 2>&1; then
  certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "$SSL_EMAIL" --redirect >/dev/null 2>&1     && ok "SSL نصب شد." || warn "SSL نصب نشد؛ بعداً certbot --nginx -d $DOMAIN را اجرا کنید."
else
  warn "دامنه هنوز Resolve نمی‌شود؛ SSL فعلاً رد شد."
fi

step 8 8 "ثبت Webhook و پایان نصب"
WEBHOOK_RESPONSE="$(curl -sS -X POST "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook"   -H "Content-Type: application/json"   -d "{\"url\":\"https://${DOMAIN}/telegram/webhook\",\"secret_token\":\"${WEBHOOK_SECRET}\",\"allowed_updates\":[\"message\",\"callback_query\"]}" || true)"
echo "$WEBHOOK_RESPONSE" | grep -q '"ok":true' && ok "Webhook تلگرام ثبت شد." || warn "پاسخ Webhook: $WEBHOOK_RESPONSE"

echo
line
printf "${C_GREEN}${C_BOLD}نصب ai-shop با موفقیت تمام شد.${C_RESET}
"
line
printf "پنل مدیریت:  ${C_CYAN}https://${DOMAIN}/admin${C_RESET}
"
printf "راهنمای گرافیکی: ${C_CYAN}https://${DOMAIN}/admin/help${C_RESET}
"
printf "مدیریت دیتابیس: ${C_CYAN}https://${DOMAIN}/admin/database${C_RESET}
"
printf "نام کاربری:   ${C_BOLD}admin${C_RESET}
"
printf "رمز پنل:      ${C_YELLOW}${ADMIN_PASS}${C_RESET}
"
printf "
${C_RED}رمز پنل را همین حالا در محل امن ذخیره کنید.${C_RESET}
"
