#!/usr/bin/env bash
set -u
VERSION="3.1.0"




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
