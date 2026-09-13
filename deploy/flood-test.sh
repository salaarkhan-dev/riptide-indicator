#!/usr/bin/env bash
#
# Riptide scanner — step 4, prove alerts actually deliver.
#
#     bash deploy/flood-test.sh                 # BTC_USDT only (~11 messages)
#     bash deploy/flood-test.sh BTC_USDT,ETH_USDT
#
# Sends every historic setup in the lookback window to Telegram, then resets
# state so normal behaviour resumes.
#
# NOTE: RIPTIDE_ALERT_FIRST_RUN=1 on its own sends NOTHING. It only lifts the
# first-run suppression; the separate "fresh" gate still drops any setup whose
# shift is older than RIPTIDE_FRESH_BARS bars, and historic setups are all
# older than that by definition. Overriding RIPTIDE_FRESH_BARS for this one
# run is what produces the flood. Both are env-only, set for this process
# alone — no code and no .env change, so normal behaviour is untouched.

set -euo pipefail

APP_DIR=/home/ubuntu/riptide
SYMBOLS="${1:-BTC_USDT}"

cd "$APP_DIR"

if systemctl is-active --quiet riptide 2>/dev/null; then
  echo "riptide.service is running; stop it first:  sudo systemctl stop riptide"
  exit 1
fi

echo "Flood test on: $SYMBOLS"
echo "Every historic setup will be sent. Ctrl-C once messages start arriving."
echo

rm -f riptide.db

set -a; . ./.env; set +a
export RIPTIDE_SYMBOLS="$SYMBOLS"
export RIPTIDE_ALERT_FIRST_RUN=1
export RIPTIDE_FRESH_BARS=100000

trap 'echo; echo "resetting state..."; rm -f "$APP_DIR/riptide.db"; \
      echo "riptide.db deleted. Overrides were process-local; .env is unchanged."; \
      echo "Normal behaviour resumes when you start the service."' EXIT

# flood_test.py runs one cycle immediately and exits. Running riptide_bot.py
# directly would sleep until the next bar close first — up to 30 minutes of
# apparent silence before the test does anything.
cp "$SRC_DIR/deploy/flood_test.py" "$APP_DIR/flood_test.py"
.venv/bin/python flood_test.py
