#!/usr/bin/env bash
set -euo pipefail

[ "$(id -u)" -eq 0 ] || {
  echo "این اسکریپت را با root یا sudo اجرا کنید."
  exit 1
}

[ $# -eq 1 ] || {
  echo "استفاده:"
  echo "sudo ./restore.sh backups/ai-shop-YYYYMMDD-HHMMSS.tar.gz"
  exit 1
}

ARCHIVE="$(readlink -f "$1")"
[ -f "${ARCHIVE}" ] || {
  echo "فایل بکاپ پیدا نشد: ${ARCHIVE}"
  exit 1
}

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

tar -xzf "${ARCHIVE}" -C "${TMP_DIR}"
[ -f "${TMP_DIR}/database.sql.gz" ] || {
  echo "ساختار بکاپ معتبر نیست."
  exit 1
}

read -rp "اطلاعات فعلی دیتابیس جایگزین شود؟ RESTORE را بنویسید: " CONFIRM
[ "${CONFIRM}" = "RESTORE" ] || {
  echo "عملیات لغو شد."
  exit 0
}

systemctl stop ai-shop || true

cd /tmp
runuser -u postgres -- dropdb --if-exists ai_shop
runuser -u postgres -- createdb -O ai_shop ai_shop
gzip -dc "${TMP_DIR}/database.sql.gz" | runuser -u postgres -- psql ai_shop

if [ -f "${TMP_DIR}/env.backup" ]; then
  cp "${TMP_DIR}/env.backup" /opt/ai-shop/.env
  chown ai-shop:ai-shop /opt/ai-shop/.env
  chmod 600 /opt/ai-shop/.env
fi

systemctl restart ai-shop
echo "بازیابی با موفقیت انجام شد."
