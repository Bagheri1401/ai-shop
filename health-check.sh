#!/usr/bin/env bash
set -u
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

banner
CHECKS=0
PASSED=0
check() {
  CHECKS=$((CHECKS+1))
  if eval "$2" >/dev/null 2>&1; then
    ok "$1"
    PASSED=$((PASSED+1))
  else
    fail "$1"
  fi
}
check "سرویس ai-shop فعال است" "systemctl is-active ai-shop"
check "PostgreSQL فعال است" "systemctl is-active postgresql"
check "Nginx فعال است" "systemctl is-active nginx"
check "پورت داخلی پاسخ می‌دهد" "curl -fsS http://127.0.0.1:3000/health"
check "مسیر نسخه پاسخ می‌دهد" "curl -fsS http://127.0.0.1:3000/version"
check "تنظیمات امن وجود دارد" "test -s /opt/ai-shop/.env"
echo
line
printf "نتیجه: ${C_BOLD}%s از %s بررسی موفق${C_RESET}\n" "$PASSED" "$CHECKS"
[ "$PASSED" -eq "$CHECKS" ]
