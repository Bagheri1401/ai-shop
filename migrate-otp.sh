#!/usr/bin/env bash
set -Eeuo pipefail

[ "$(id -u)" -eq 0 ] || {
  echo "اجرا کنید: sudo bash migrate-otp.sh"
  exit 1
}

ENV_FILE="/opt/ai-shop/.env"
[ -f "$ENV_FILE" ] || {
  echo "فایل تنظیمات نصب‌شده پیدا نشد."
  exit 1
}

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

export PGPASSWORD="$DB_PASSWORD"

psql \
  -h "${DB_HOST:-127.0.0.1}" \
  -p "${DB_PORT:-5432}" \
  -U "$DB_USER" \
  -d "$DB_NAME" \
  -v ON_ERROR_STOP=1 <<'SQL'
CREATE TABLE IF NOT EXISTS admin_login_otps(
  id BIGSERIAL PRIMARY KEY,
  telegram_id BIGINT NOT NULL,
  otp_hash TEXT NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  used_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_admin_login_otps_lookup
  ON admin_login_otps(otp_hash,expires_at)
  WHERE used_at IS NULL;
SQL

systemctl restart ai-shop
echo "جدول رمز یک‌بارمصرف ساخته و سرویس ریستارت شد."
