#!/usr/bin/env bash
set -Eeuo pipefail
[ "$(id -u)" -eq 0 ] || { echo "sudo bash check-admin.sh"; exit 1; }
source /opt/ai-shop/.env
export PGPASSWORD="$DB_PASSWORD"
psql -h "${DB_HOST:-127.0.0.1}" -p "${DB_PORT:-5432}" -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 <<'SQL'
SELECT COUNT(*) FROM users;
SELECT COUNT(*) FROM products;
SELECT COUNT(*) FROM orders;
SELECT COUNT(*) FROM tickets;
SELECT COUNT(*) FROM discount_codes;
SELECT COUNT(*) FROM service_inventory;
SELECT COUNT(*) FROM app_settings;
SQL
curl -fsS http://127.0.0.1:3000/health
echo
echo "دیتابیس و سرویس پنل سالم هستند."
