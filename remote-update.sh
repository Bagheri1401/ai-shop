#!/usr/bin/env bash
set -Eeuo pipefail
VERSION="4.1.0"



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


validate_nginx_candidate() {
  local candidate="$1"
  local duplicate
  duplicate="$(awk '
    /^[[:space:]]*(proxy_http_version|proxy_connect_timeout|proxy_send_timeout|proxy_read_timeout|proxy_next_upstream_tries)[[:space:]]/ {
      key=$1
      count[key]++
    }
    END {
      for (key in count) {
        if (count[key] > 1) print key
      }
    }
  ' "$candidate")"

  if [ -n "$duplicate" ]; then
    fail "دستور تکراری در Nginx پیدا شد: $duplicate"
    return 1
  fi
}

[ "$(id -u)" -eq 0 ] || {
  fail "اجرا کنید: sudo bash remote-update.sh"
  exit 1
}

banner

REPO_URL="${AI_SHOP_REPO_URL:-https://github.com/Bagheri1401/AI-SHOP.git}"
BRANCH="${AI_SHOP_BRANCH:-main}"
TMP_DIR="$(mktemp -d /tmp/ai-shop-update.XXXXXX)"
BACKUP_DIR=""
UPDATE_STARTED=0

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

step 1 5 "دریافت آخرین نسخه از GitHub"
info "$REPO_URL — branch: $BRANCH"
git clone --quiet --depth 1 --branch "$BRANCH" "$REPO_URL" "$TMP_DIR/source"
TARGET_VERSION="$(tr -d '[:space:]' < "$TMP_DIR/source/VERSION")"
ok "نسخه $TARGET_VERSION دریافت شد."

step 2 5 "اعتبارسنجی فایل‌های نسخه جدید"
python3 -m py_compile "$TMP_DIR/source/app/main.py"
for file in install.sh update.sh remote-update.sh easy-update.sh repair.sh backup.sh restore.sh uninstall.sh health-check.sh; do
  if [ -f "$TMP_DIR/source/$file" ]; then
    bash -n "$TMP_DIR/source/$file"
  fi
done
ok "Python و تمام اسکریپت‌های Shell معتبر هستند."

step 3 5 "ساخت نسخه بازگشت"
[ -f /opt/ai-shop/.env ] || {
  fail "نصب قبلی در /opt/ai-shop پیدا نشد؛ برای نصب اولیه از install.sh استفاده کنید."
  exit 1
}
[ -d /opt/ai-shop/app ] || {
  fail "پوشه برنامه نصب‌شده پیدا نشد."
  exit 1
}

BACKUP_DIR="/opt/ai-shop-rollback-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp -a /opt/ai-shop/app "$BACKUP_DIR/app"
[ -d /opt/ai-shop/docs ] && cp -a /opt/ai-shop/docs "$BACKUP_DIR/docs"
cp -a /opt/ai-shop/.env "$BACKUP_DIR/.env"
[ -f /etc/systemd/system/ai-shop.service ] && cp -a /etc/systemd/system/ai-shop.service "$BACKUP_DIR/ai-shop.service"
[ -f /etc/nginx/sites-available/ai-shop ] && cp -a /etc/nginx/sites-available/ai-shop "$BACKUP_DIR/nginx.conf"
ok "بکاپ بازگشت: $BACKUP_DIR"

rollback() {
  local exit_code=$?
  trap - ERR
  set +e
  if [ "$UPDATE_STARTED" -eq 1 ]; then
    fail "آپدیت کامل نشد؛ نسخه قبلی بازیابی می‌شود."
    systemctl stop ai-shop >/dev/null 2>&1
    rm -rf /opt/ai-shop/app /opt/ai-shop/docs
    cp -a "$BACKUP_DIR/app" /opt/ai-shop/app
    [ -d "$BACKUP_DIR/docs" ] && cp -a "$BACKUP_DIR/docs" /opt/ai-shop/docs
    cp -a "$BACKUP_DIR/.env" /opt/ai-shop/.env
    [ -f "$BACKUP_DIR/ai-shop.service" ] && cp -a "$BACKUP_DIR/ai-shop.service" /etc/systemd/system/ai-shop.service
    [ -f "$BACKUP_DIR/nginx.conf" ] && cp -a "$BACKUP_DIR/nginx.conf" /etc/nginx/sites-available/ai-shop
    chown -R ai-shop:ai-shop /opt/ai-shop
    chmod 600 /opt/ai-shop/.env
    systemctl daemon-reload
    nginx -t >/dev/null 2>&1 && systemctl reload nginx
    systemctl restart ai-shop
    journalctl -u ai-shop -n 60 --no-pager
  fi
  exit "$exit_code"
}
trap rollback ERR

step 4 5 "جایگزینی امن برنامه"
UPDATE_STARTED=1
systemctl stop ai-shop || true

rm -rf /opt/ai-shop/app.new /opt/ai-shop/docs.new
cp -a "$TMP_DIR/source/app" /opt/ai-shop/app.new
if [ -d "$TMP_DIR/source/docs" ]; then
  cp -a "$TMP_DIR/source/docs" /opt/ai-shop/docs.new
fi
chown -R ai-shop:ai-shop /opt/ai-shop/app.new
[ -d /opt/ai-shop/docs.new ] && chown -R ai-shop:ai-shop /opt/ai-shop/docs.new

rm -rf /opt/ai-shop/app.old /opt/ai-shop/docs.old
mv /opt/ai-shop/app /opt/ai-shop/app.old
[ -d /opt/ai-shop/docs ] && mv /opt/ai-shop/docs /opt/ai-shop/docs.old
mv /opt/ai-shop/app.new /opt/ai-shop/app
[ -d /opt/ai-shop/docs.new ] && mv /opt/ai-shop/docs.new /opt/ai-shop/docs

cp "$TMP_DIR/source/systemd/ai-shop.service" /etc/systemd/system/ai-shop.service
DOMAIN="$(grep '^DOMAIN=' /opt/ai-shop/.env | cut -d= -f2-)"
[ -n "$DOMAIN" ] || {
  fail "مقدار DOMAIN در /opt/ai-shop/.env خالی است."
  false
}

NGINX_CANDIDATE="$TMP_DIR/ai-shop.nginx.candidate"
sed "s/__DOMAIN__/${DOMAIN}/g" "$TMP_DIR/source/nginx/ai-shop.conf" > "$NGINX_CANDIDATE"
validate_nginx_candidate "$NGINX_CANDIDATE"
ok "قالب Nginx بدون دستور تکراری است."

systemctl daemon-reload
systemctl restart ai-shop

# main.py creates the OTP table on startup. A second restart is not needed.
APP_READY=0
for _ in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:3000/health >/dev/null 2>&1; then
    APP_READY=1
    break
  fi
  sleep 1
done
if [ "$APP_READY" -ne 1 ]; then
  fail "برنامه بعد از ۶۰ ثانیه آماده نشد."
  systemctl status ai-shop --no-pager || true
  journalctl -u ai-shop -n 120 --no-pager || true
  false
fi

cp "$NGINX_CANDIDATE" /etc/nginx/sites-available/ai-shop
ln -sf /etc/nginx/sites-available/ai-shop /etc/nginx/sites-enabled/ai-shop
nginx -t
systemctl reload nginx
ok "نسخه جدید اجرا شد."

step 5 5 "بررسی سلامت و نسخه فعال"
READY=0
for _ in $(seq 1 45); do
  if curl -fsS http://127.0.0.1:3000/health >/dev/null 2>&1; then
    READY=1
    break
  fi
  sleep 1
done
[ "$READY" -eq 1 ] || {
  fail "سرویس تا ۴۵ ثانیه آماده نشد."
  false
}

ACTIVE_VERSION="$(curl -fsS http://127.0.0.1:3000/version)"
echo "$ACTIVE_VERSION" | grep -Eq '"version"[[:space:]]*:[[:space:]]*"'"$TARGET_VERSION"'"' || {
  fail "نسخه فعال با نسخه مقصد برابر نیست: $ACTIVE_VERSION"
  false
}

rm -rf /opt/ai-shop/app.old /opt/ai-shop/docs.old
UPDATE_STARTED=0
trap - ERR

ok "نسخه فعال: $TARGET_VERSION"
line
summary_box
printf "پنل مدیریت: %bhttps://%s/admin%b\n" "$C_CYAN" "$DOMAIN" "$C_RESET"
printf "راهنما:      %bhttps://%s/admin/help%b\n" "$C_CYAN" "$DOMAIN" "$C_RESET"
