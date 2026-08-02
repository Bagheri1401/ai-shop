#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${PROJECT_DIR}"

if [ "$(id -u)" -eq 0 ]; then
  bash remote-update.sh
else
  sudo bash remote-update.sh
fi
