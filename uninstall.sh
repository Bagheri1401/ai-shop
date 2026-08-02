#!/usr/bin/env bash
set -euo pipefail

[ "$(id -u)" -eq 0 ] || {
  echo "این اسکریپت را با root یا sudo اجرا کنید."
  exit 1
}

SERVICE_NAME="ai-shop"
INSTALL_DIR="/opt/ai-shop"
DB_NAME="ai_shop"
DB_USER="ai_shop"

echo "== حذف ai-shop =="

read -rp "آیا از اطلاعات خود بکاپ گرفته‌اید؟ برای ادامه DELETE را بنویسید: " CONFIRM
if [ "${CONFIRM}" != "DELETE" ]; then
  echo "عملیات لغو شد."
  exit 0
fi

REMOVE_DB="no"
REMOVE_SSL="no"
REMOVE_PACKAGES="no"

read -rp "دیتابیس و تمام سفارش‌ها حذف شوند؟ [yes/no]: " REMOVE_DB
read -rp "گواهی SSL دامنه نیز حذف شود؟ [yes/no]: " REMOVE_SSL
read -rp "بسته‌های Nginx/PostgreSQL/Certbot هم حذف شوند؟ [yes/no]: " REMOVE_PACKAGES

DOMAIN=""
if [ -f "${INSTALL_DIR}/.env" ]; then
  DOMAIN="$(grep '^DOMAIN=' "${INSTALL_DIR}/.env" | cut -d= -f2- || true)"
fi

systemctl disable --now "${SERVICE_NAME}" 2>/dev/null || true
rm -f "/etc/systemd/system/${SERVICE_NAME}.service"
systemctl daemon-reload
systemctl reset-failed || true

rm -f /etc/nginx/sites-enabled/ai-shop
rm -f /etc/nginx/sites-available/ai-shop
nginx -t >/dev/null 2>&1 && systemctl reload nginx || true

rm -rf "${INSTALL_DIR}"
id ai-shop >/dev/null 2>&1 && userdel ai-shop || true

if [ "${REMOVE_DB}" = "yes" ]; then
  cd /tmp
  runuser -u postgres -- dropdb --if-exists "${DB_NAME}" || true
  runuser -u postgres -- psql -c "DROP ROLE IF EXISTS ${DB_USER};" || true
  echo "دیتابیس و کاربر PostgreSQL حذف شدند."
else
  echo "دیتابیس حفظ شد."
fi

if [ "${REMOVE_SSL}" = "yes" ] && [ -n "${DOMAIN}" ]; then
  certbot delete --cert-name "${DOMAIN}" --non-interactive || true
fi

if [ "${REMOVE_PACKAGES}" = "yes" ]; then
  apt-get remove --purge -y nginx certbot python3-certbot-nginx postgresql || true
  apt-get autoremove -y || true
fi

echo
echo "ai-shop از سیستم حذف شد."
echo "پوشه پروژه Git در مسیر فعلی حذف نشده است."
