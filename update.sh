#!/usr/bin/env bash
set -Eeuo pipefail
VERSION="4.2.0"



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
  fail "اجرا کنید: sudo bash update.sh"
  exit 1
}

banner
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_VERSION="$(tr -d '[:space:]' < "$PROJECT_DIR/VERSION")"

step 1 4 "اعتبارسنجی نسخه محلی"
python3 -m py_compile "$PROJECT_DIR/app/main.py"
for file in install.sh update.sh remote-update.sh easy-update.sh repair.sh backup.sh restore.sh uninstall.sh health-check.sh; do
  [ -f "$PROJECT_DIR/$file" ] && bash -n "$PROJECT_DIR/$file"
done
ok "نسخه محلی $TARGET_VERSION معتبر است."

step 2 4 "بررسی نصب فعلی"
[ -f /opt/ai-shop/.env ] || {
  fail "نصب قبلی پیدا نشد؛ از sudo bash install.sh استفاده کنید."
  exit 1
}
BACKUP_DIR="/opt/ai-shop-rollback-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp -a /opt/ai-shop/app "$BACKUP_DIR/app"
[ -d /opt/ai-shop/docs ] && cp -a /opt/ai-shop/docs "$BACKUP_DIR/docs"
cp -a /opt/ai-shop/.env "$BACKUP_DIR/.env"
ok "نسخه بازگشت ساخته شد."

rollback() {
  local exit_code=$?
  trap - ERR
  set +e
  fail "آپدیت محلی ناموفق بود؛ نسخه قبلی بازیابی می‌شود."
  systemctl stop ai-shop >/dev/null 2>&1
  rm -rf /opt/ai-shop/app /opt/ai-shop/docs
  cp -a "$BACKUP_DIR/app" /opt/ai-shop/app
  [ -d "$BACKUP_DIR/docs" ] && cp -a "$BACKUP_DIR/docs" /opt/ai-shop/docs
  cp -a "$BACKUP_DIR/.env" /opt/ai-shop/.env
  chown -R ai-shop:ai-shop /opt/ai-shop
  chmod 600 /opt/ai-shop/.env
  systemctl restart ai-shop
  exit "$exit_code"
}
trap rollback ERR

step 3 4 "جایگزینی برنامه"
systemctl stop ai-shop || true
rm -rf /opt/ai-shop/app.new /opt/ai-shop/docs.new
cp -a "$PROJECT_DIR/app" /opt/ai-shop/app.new
[ -d "$PROJECT_DIR/docs" ] && cp -a "$PROJECT_DIR/docs" /opt/ai-shop/docs.new
chown -R ai-shop:ai-shop /opt/ai-shop/app.new
[ -d /opt/ai-shop/docs.new ] && chown -R ai-shop:ai-shop /opt/ai-shop/docs.new
rm -rf /opt/ai-shop/app
mv /opt/ai-shop/app.new /opt/ai-shop/app
rm -rf /opt/ai-shop/docs
[ -d /opt/ai-shop/docs.new ] && mv /opt/ai-shop/docs.new /opt/ai-shop/docs

cp "$PROJECT_DIR/systemd/ai-shop.service" /etc/systemd/system/ai-shop.service
DOMAIN="$(grep '^DOMAIN=' /opt/ai-shop/.env | cut -d= -f2-)"
[ -n "$DOMAIN" ] || {
  fail "مقدار DOMAIN در /opt/ai-shop/.env خالی است."
  false
}
NGINX_CANDIDATE="$(mktemp /tmp/ai-shop-nginx.XXXXXX)"
sed "s/__DOMAIN__/${DOMAIN}/g" "$PROJECT_DIR/nginx/ai-shop.conf" > "$NGINX_CANDIDATE"
validate_nginx_candidate "$NGINX_CANDIDATE"
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

nginx -t
systemctl reload nginx
ok "برنامه جدید اجرا شد."

step 4 4 "بررسی نسخه"
for _ in $(seq 1 45); do
  curl -fsS http://127.0.0.1:3000/health >/dev/null 2>&1 && break
  sleep 1
done
ACTIVE_VERSION="$(curl -fsS http://127.0.0.1:3000/version)"
echo "$ACTIVE_VERSION" | grep -Eq '"version"[[:space:]]*:[[:space:]]*"'"$TARGET_VERSION"'"'
cp "$NGINX_CANDIDATE" /etc/nginx/sites-available/ai-shop
ln -sf /etc/nginx/sites-available/ai-shop /etc/nginx/sites-enabled/ai-shop
nginx -t
systemctl reload nginx
rm -f "$NGINX_CANDIDATE"
trap - ERR
ok "نسخه فعال: $TARGET_VERSION"
summary_box
