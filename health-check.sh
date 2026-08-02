#!/usr/bin/env bash
set -u
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
