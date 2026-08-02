#!/usr/bin/env bash
set -Eeuo pipefail
VERSION="2.2.1"


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
║            Telegram AI Commerce Platform                  ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
BANNER
  printf "%b" "${C_RESET}"
  printf "\n%bProfessional Edition%b   %bVersion %s%b\n\n" \
    "${C_WHITE}${C_BOLD}" "${C_RESET}" "${C_GRAY}" "$VERSION" "${C_RESET}"
}

line() {
  printf "%b\n" "${C_BLUE}────────────────────────────────────────────────────────────${C_RESET}"
}

section() {
  printf "\n%b┌─ %s%b\n" "${C_BLUE}${C_BOLD}" "$1" "${C_RESET}"
}

step() {
  printf "%b│  [%s/%s]%b %s\n" "${C_CYAN}${C_BOLD}" "$1" "$2" "${C_RESET}" "$3"
}

ok() {
  printf "%b│  ✔%b %s\n" "${C_GREEN}" "${C_RESET}" "$1"
}

warn() {
  printf "%b│  ⚠%b %s\n" "${C_YELLOW}" "${C_RESET}" "$1"
}

fail() {
  printf "%b│  ✖%b %s\n" "${C_RED}" "${C_RESET}" "$1" >&2
}

info() {
  printf "%b│  ●%b %s\n" "${C_CYAN}" "${C_RESET}" "$1"
}

end_section() {
  printf "%b\n" "${C_BLUE}└──────────────────────────────────────────────────────────${C_RESET}"
}

summary_box() {
  printf "\n%b" "${C_GREEN}${C_BOLD}"
  cat <<'SUMMARY'
╔════════════════════════════════════════════════════════════╗
║                    عملیات موفق بود                        ║
╚════════════════════════════════════════════════════════════╝
SUMMARY
  printf "%b" "${C_RESET}"
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
sed "s/__DOMAIN__/${DOMAIN}/g" "$PROJECT_DIR/nginx/ai-shop.conf" > /etc/nginx/sites-available/ai-shop
ln -sf /etc/nginx/sites-available/ai-shop /etc/nginx/sites-enabled/ai-shop
nginx -t
systemctl daemon-reload
systemctl reload nginx
systemctl restart ai-shop
ok "برنامه جدید اجرا شد."

step 4 4 "بررسی نسخه"
for _ in $(seq 1 45); do
  curl -fsS http://127.0.0.1:3000/health >/dev/null 2>&1 && break
  sleep 1
done
ACTIVE_VERSION="$(curl -fsS http://127.0.0.1:3000/version)"
echo "$ACTIVE_VERSION" | grep -Eq '"version"[[:space:]]*:[[:space:]]*"'"$TARGET_VERSION"'"'
trap - ERR
ok "نسخه فعال: $TARGET_VERSION"
summary_box
