#!/usr/bin/env bash
#
# Riptide scanner — step 5, install as a systemd service.
#
#     bash deploy/install-service.sh
#
# The unit carries no secrets; it reads them via EnvironmentFile.

set -euo pipefail

APP_DIR=/home/ubuntu/riptide
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

die() { echo "FAIL: $*" >&2; exit 1; }

[[ -f $APP_DIR/.env ]]                || die "$APP_DIR/.env missing — run install.sh first"
[[ -x $APP_DIR/.venv/bin/python ]]    || die "venv missing — run install.sh first"
[[ -f $APP_DIR/riptide_bot.py ]]      || die "riptide_bot.py missing — run install.sh first"
[[ $(stat -c '%a' "$APP_DIR/.env") == 600 ]] || die ".env is not mode 600"

# a stale first-run db from the flood test would suppress real alerts silently
if [[ -f $APP_DIR/riptide.db ]]; then
  echo "note: $APP_DIR/riptide.db exists — first service cycle will be silent"
  echo "      (that is correct behaviour; delete it only if you want a fresh bootstrap)"
fi

sudo cp "$SRC_DIR/deploy/riptide.service" /etc/systemd/system/riptide.service
sudo chmod 644 /etc/systemd/system/riptide.service
sudo systemctl daemon-reload
sudo systemctl enable --now riptide

sleep 3
echo
systemctl status riptide --no-pager || true
echo
echo "enabled: $(systemctl is-enabled riptide)"
echo "active:  $(systemctl is-active riptide)"
echo
echo "Follow the logs:   journalctl -u riptide -f"
echo "Then reboot and confirm it comes back:   sudo reboot"
