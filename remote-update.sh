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

[ "$(id -u)" -eq 0 ] || { fail "اجرا کنید: sudo bash remote-update.sh"; exit 1; }
banner
REPO_URL="${AI_SHOP_REPO_URL:-https://github.com/Bagheri1401/AI-SHOP.git}"
BRANCH="${AI_SHOP_BRANCH:-main}"
TMP_DIR="$(mktemp -d /tmp/ai-shop-update.XXXXXX)"
trap 'rm -rf "$TMP_DIR"' EXIT

step 1 5 "دریافت آخرین نسخه از GitHub"
info "$REPO_URL — branch: $BRANCH"
git clone --quiet --depth 1 --branch "$BRANCH" "$REPO_URL" "$TMP_DIR/source"
TARGET_VERSION="$(tr -d '[:space:]' < "$TMP_DIR/source/VERSION")"
ok "نسخه $TARGET_VERSION دریافت شد."

step 2 5 "اعتبارسنجی فایل‌ها"
python3 -m py_compile "$TMP_DIR/source/app/main.py"
for f in install.sh update.sh remote-update.sh backup.sh restore.sh uninstall.sh health-check.sh; do
  [ -f "$TMP_DIR/source/$f" ] && bash -n "$TMP_DIR/source/$f"
done
ok "فایل‌ها معتبر هستند."

step 3 5 "آماده‌سازی آپدیت امن"
[ -f /opt/ai-shop/.env ] || { fail "نصب قبلی پیدا نشد؛ از install.sh استفاده کنید."; exit 1; }
BACKUP="/opt/ai-shop-rollback-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP"
cp -a /opt/ai-shop/app "$BACKUP/app"
[ -d /opt/ai-shop/docs ] && cp -a /opt/ai-shop/docs "$BACKUP/docs"
cp -a /opt/ai-shop/.env "$BACKUP/.env"
ok "نسخه بازگشت در $BACKUP ذخیره شد."

rollback() {
  fail "آپدیت ناموفق بود؛ نسخه قبلی بازیابی می‌شود."
  systemctl stop ai-shop >/dev/null 2>&1 || true
  rm -rf /opt/ai-shop/app /opt/ai-shop/docs
  cp -a "$BACKUP/app" /opt/ai-shop/app
  [ -d "$BACKUP/docs" ] && cp -a "$BACKUP/docs" /opt/ai-shop/docs
  cp -a "$BACKUP/.env" /opt/ai-shop/.env
  chown -R ai-shop:ai-shop /opt/ai-shop
  systemctl restart ai-shop || true
  journalctl -u ai-shop -n 80 --no-pager || true
}
trap rollback ERR

step 4 5 "جایگزینی نسخه و اجرای Migration"
systemctl stop ai-shop || true
rm -rf /opt/ai-shop/app.new /opt/ai-shop/docs.new
cp -a "$TMP_DIR/source/app" /opt/ai-shop/app.new
cp -a "$TMP_DIR/source/docs" /opt/ai-shop/docs.new
chown -R ai-shop:ai-shop /opt/ai-shop/app.new /opt/ai-shop/docs.new
rm -rf /opt/ai-shop/app.old /opt/ai-shop/docs.old
mv /opt/ai-shop/app /opt/ai-shop/app.old
[ -d /opt/ai-shop/docs ] && mv /opt/ai-shop/docs /opt/ai-shop/docs.old
mv /opt/ai-shop/app.new /opt/ai-shop/app
mv /opt/ai-shop/docs.new /opt/ai-shop/docs
cp "$TMP_DIR/source/systemd/ai-shop.service" /etc/systemd/system/ai-shop.service
DOMAIN="$(grep '^DOMAIN=' /opt/ai-shop/.env | cut -d= -f2-)"
sed "s/__DOMAIN__/${DOMAIN}/g" "$TMP_DIR/source/nginx/ai-shop.conf" > /etc/nginx/sites-available/ai-shop
nginx -t >/dev/null
systemctl daemon-reload
systemctl reload nginx
systemctl restart ai-shop
ok "نسخه جدید اجرا شد."

step 5 5 "بررسی سلامت و شماره نسخه"
READY=0
for _ in $(seq 1 45); do
  if curl -fsS http://127.0.0.1:3000/health >/dev/null 2>&1; then READY=1; break; fi
  sleep 1
done
[ "$READY" -eq 1 ] || { fail "سرویس آماده نشد."; false; }
ACTIVE="$(curl -fsS http://127.0.0.1:3000/version)"
echo "$ACTIVE" | grep -q "\"version\": *\"$TARGET_VERSION\"" || { fail "نسخه فعال صحیح نیست: $ACTIVE"; false; }
rm -rf /opt/ai-shop/app.old /opt/ai-shop/docs.old
trap - ERR
ok "نسخه فعال: $TARGET_VERSION"
line
printf "${C_GREEN}${C_BOLD}آپدیت با موفقیت تمام شد.${C_RESET}
"
printf "پنل: ${C_CYAN}https://${DOMAIN}/admin${C_RESET}
"
printf "راهنما: ${C_CYAN}https://${DOMAIN}/admin/help${C_RESET}
"
