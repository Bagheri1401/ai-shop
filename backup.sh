#!/usr/bin/env bash
set -euo pipefail

[ "$(id -u)" -eq 0 ] || {
  echo "این اسکریپت را با root یا sudo اجرا کنید."
  exit 1
}

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKUP_DIR="${PROJECT_DIR}/backups"
INSTALL_DIR="/opt/ai-shop"
STAMP="$(date +%Y%m%d-%H%M%S)"
ARCHIVE="${BACKUP_DIR}/ai-shop-${STAMP}.tar.gz"

mkdir -p "${BACKUP_DIR}"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

cd /tmp
runuser -u postgres -- pg_dump ai_shop | gzip > "${TMP_DIR}/database.sql.gz"

if [ -f "${INSTALL_DIR}/.env" ]; then
  cp "${INSTALL_DIR}/.env" "${TMP_DIR}/env.backup"
  chmod 600 "${TMP_DIR}/env.backup"
fi

tar -czf "${ARCHIVE}" -C "${TMP_DIR}" .
chmod 600 "${ARCHIVE}"

echo "بکاپ ساخته شد:"
echo "${ARCHIVE}"
