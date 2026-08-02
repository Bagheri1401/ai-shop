#!/usr/bin/env bash
set -Eeuo pipefail
[ "$(id -u)" -eq 0 ] || { echo "sudo bash repair.sh"; exit 1; }

echo "بررسی نصب ai-shop..."
systemctl daemon-reload
systemctl enable --now postgresql nginx >/dev/null 2>&1 || true

[ -f /opt/ai-shop/.env ] || {
  echo "فایل /opt/ai-shop/.env پیدا نشد؛ نصب اولیه لازم است."
  exit 1
}

chown -R ai-shop:ai-shop /opt/ai-shop
chmod 750 /opt/ai-shop
chmod 600 /opt/ai-shop/.env

systemctl restart ai-shop
sleep 3
systemctl status ai-shop --no-pager || true
curl -s http://127.0.0.1:3000/health; echo


echo "بررسی خطای 502..."
systemctl daemon-reload
systemctl restart ai-shop

READY=0
for _ in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:3000/health >/dev/null 2>&1; then
    READY=1
    break
  fi
  sleep 1
done

if [ "$READY" -ne 1 ]; then
  echo "سرویس داخلی آماده نشد."
  systemctl status ai-shop --no-pager || true
  journalctl -u ai-shop -n 120 --no-pager || true
  exit 1
fi

nginx -t
systemctl reload nginx
echo "اتصال داخلی و Nginx سالم هستند."
