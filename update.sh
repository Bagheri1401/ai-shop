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

[ "$(id -u)" -eq 0 ] || { fail "اجرا کنید: sudo bash update.sh"; exit 1; }
banner
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 -m py_compile "$PROJECT_DIR/app/main.py"
info "آپدیت از فایل‌های محلی نسخه $(cat "$PROJECT_DIR/VERSION")"
TMP_REPO="$(mktemp -d /tmp/ai-shop-local.XXXXXX)"
trap 'rm -rf "$TMP_REPO"' EXIT
cp -a "$PROJECT_DIR"/. "$TMP_REPO/"
AI_SHOP_REPO_URL="file://$TMP_REPO" AI_SHOP_BRANCH="$(git -C "$PROJECT_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)" bash "$PROJECT_DIR/remote-update.sh"
