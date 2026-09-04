#!/usr/bin/env bash
#
# Riptide scanner — steps 1 & 2 (prepare the box, install).
# Run on the Oracle instance as the `ubuntu` user:
#
#     bash deploy/install.sh
#
# Halts on any failed check rather than working around it.
# Does NOT install the systemd service — see deploy/install-service.sh.
# Does NOT open any inbound port and never touches the security list.

set -euo pipefail

APP_DIR=/home/ubuntu/riptide
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

die() { echo "FAIL: $*" >&2; exit 1; }
ok()  { echo "  ok: $*"; }

[[ $EUID -ne 0 ]] || die "run as the ubuntu user, not root"
[[ $(id -un) == ubuntu ]] || echo "  warn: expected user 'ubuntu', got '$(id -un)'"

echo "== 1. prepare the box =="

sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get upgrade -y
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y python3-venv chrony

# architecture
arch=$(uname -m)
[[ $arch == aarch64 ]] || die "expected aarch64, got $arch"
ok "arch $arch"

# python >= 3.10
pyv=$(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])')
python3 -c 'import sys;sys.exit(0 if sys.version_info>=(3,10) else 1)' \
  || die "python $pyv is older than 3.10"
ok "python $pyv"

# clock — bar-close alignment depends on this, do not skip
sudo systemctl enable --now chrony >/dev/null 2>&1 || true
for i in $(seq 1 30); do
  timedatectl show -p NTPSynchronized --value | grep -q '^yes$' && break
  [[ $i -eq 30 ]] && { timedatectl; die "system clock not synchronized"; }
  sleep 2
done
ok "clock synchronized"
timedatectl | sed 's/^/     /'

echo
echo "== 2. install =="

mkdir -p "$APP_DIR"
cp "$SRC_DIR/riptide_bot.py" "$APP_DIR/riptide_bot.py"
ok "riptide_bot.py -> $APP_DIR"

python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/.venv/bin/pip" install --quiet aiohttp
ok "venv + aiohttp ($("$APP_DIR/.venv/bin/python" -c 'import aiohttp;print(aiohttp.__version__)'))"

# .env — secrets are typed here, on the box, and never echoed
if [[ -f $APP_DIR/.env ]]; then
  ok ".env already exists, leaving it alone"
else
  echo
  echo "  Telegram credentials (input is hidden, nothing is printed or logged):"
  read -rsp "    TELEGRAM_TOKEN: " TG_TOKEN; echo
  read -rsp "    TELEGRAM_CHAT_ID: " TG_CHAT; echo
  [[ -n $TG_TOKEN && -n $TG_CHAT ]] || die "both values are required"

  umask 077
  cat > "$APP_DIR/.env" <<EOF
TELEGRAM_TOKEN=$TG_TOKEN
TELEGRAM_CHAT_ID=$TG_CHAT
RIPTIDE_INTERVAL=Min30
RIPTIDE_SYMBOLS=BTC_USDT,ETH_USDT,SOL_USDT,HYPE_USDT,TIA_USDT,INJ_USDT
EOF
  unset TG_TOKEN TG_CHAT
  ok ".env written"
fi

chmod 600 "$APP_DIR/.env"
chown ubuntu:ubuntu "$APP_DIR/.env" 2>/dev/null || sudo chown ubuntu:ubuntu "$APP_DIR/.env"
ok ".env is $(stat -c '%a %U:%G' "$APP_DIR/.env")"

echo
echo "Done. Next: the foreground test (step 3)."
echo
echo "    cd $APP_DIR && set -a && . ./.env && set +a && .venv/bin/python riptide_bot.py"
echo
echo "Expect 'riptide up: 6 symbols, Min30 bars' and a Telegram message."
echo "Confirm the message arrived, then wait one bar close for"
echo "'scanned 6 symbols, sent 0 alerts' + 'first run: history recorded, nothing sent'."
