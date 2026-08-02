#!/usr/bin/env bash
set -Eeuo pipefail

[ "$(id -u)" -eq 0 ] || {
  echo "اجرا کنید: sudo bash reset-panel-password.sh"
  exit 1
}

ENV_FILE="/opt/ai-shop/.env"
[ -f "$ENV_FILE" ] || {
  echo "فایل $ENV_FILE پیدا نشد."
  exit 1
}

NEW_PASSWORD="$(openssl rand -base64 30 | tr -d '/+=' | head -c 24)"

if grep -q '^ADMIN_PASSWORD=' "$ENV_FILE"; then
  sed -i "s|^ADMIN_PASSWORD=.*|ADMIN_PASSWORD=${NEW_PASSWORD}|" "$ENV_FILE"
else
  echo "ADMIN_PASSWORD=${NEW_PASSWORD}" >> "$ENV_FILE"
fi

chown ai-shop:ai-shop "$ENV_FILE"
chmod 600 "$ENV_FILE"
systemctl restart ai-shop

echo
echo "رمز جدید پنل مدیریت:"
echo "$NEW_PASSWORD"
echo
echo "نام کاربری: admin"
