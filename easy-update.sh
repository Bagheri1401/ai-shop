#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
if [ -d .git ]; then
  git fetch origin
  git reset --hard origin/main
fi
sudo bash remote-update.sh
