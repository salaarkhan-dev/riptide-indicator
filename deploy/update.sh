#!/usr/bin/env bash
#
# Pull the branch, validate, install, restart, verify — roll back if the
# service does not come up. Run by riptide-update.timer every few minutes;
# also safe to run by hand.
#
# Exits silently when there is nothing new, so the timer stays quiet.

set -euo pipefail

APP=/home/ubuntu/riptide
SRC=/home/ubuntu/riptide-src
BRANCH="${RIPTIDE_BRANCH:-claude/oracle-free-tier-alerts-3vzflp}"

log() { echo "$(date -u '+%Y-%m-%d %H:%M:%S') $*"; }

# Best effort, and never allowed to fail the update. Reads the token straight
# from .env rather than sourcing it, so nothing lands in the environment.
notify() {
    local text="$1" tok chat
    [[ -r $APP/.env ]] || return 0
    tok=$(sed -n 's/^TELEGRAM_TOKEN=//p'   "$APP/.env" | head -1) || true
    chat=$(sed -n 's/^TELEGRAM_CHAT_ID=//p' "$APP/.env" | head -1) || true
    [[ -n ${tok:-} && -n ${chat:-} ]] || return 0
    curl -sS -m 15 -X POST "https://api.telegram.org/bot${tok}/sendMessage" \
         -d "chat_id=${chat}" --data-urlencode "text=${text}" \
         -o /dev/null 2>/dev/null || true
}

[[ -d $SRC/.git ]] || { log "no clone at $SRC — run install-autoupdate.sh"; exit 1; }

cd "$SRC"
git fetch --quiet origin "$BRANCH" || { log "fetch failed (network?), will retry"; exit 0; }

have=$(git rev-parse HEAD)
want=$(git rev-parse "origin/$BRANCH")
[[ $have == "$want" ]] && exit 0          # nothing new — stay silent

short=$(git rev-parse --short "origin/$BRANCH")
log "new commit $short, updating"

# Fast-forward only. A diverged local clone means someone edited on the box;
# stop rather than clobber it.
if ! git merge --ff-only "origin/$BRANCH" --quiet; then
    log "cannot fast-forward — local clone has diverged"
    notify "Riptide update skipped: $SRC has local changes that would be overwritten. Needs a look."
    exit 1
fi

# Syntax-check with the venv's own interpreter before anything is installed.
if ! "$APP/.venv/bin/python" -m py_compile "$SRC/riptide_bot.py" 2>/tmp/riptide-compile.err; then
    log "py_compile failed, not installing"
    notify "Riptide update $short FAILED to compile. Nothing installed, still running the previous build."$'\n\n'"$(head -c 400 /tmp/riptide-compile.err)"
    exit 1
fi

prev_build=$(cat "$APP/BUILD" 2>/dev/null || echo unknown)
cp -f "$APP/riptide_bot.py" "$APP/riptide_bot.py.prev"

install -m 644 "$SRC/riptide_bot.py" "$APP/riptide_bot.py"
[[ -f $SRC/riptide.conf ]] && install -m 644 "$SRC/riptide.conf" "$APP/riptide.conf"
printf '%s\n' "$short" > "$APP/BUILD"

log "restarting service"
sudo systemctl restart riptide

# Give it time to bind, fetch symbols and run the startup scan.
sleep 10

if systemctl is-active --quiet riptide; then
    log "update to $short ok"
    notify "Riptide updated: ${prev_build} → ${short}"
    rm -f "$APP/riptide_bot.py.prev"
else
    log "service did not come up — rolling back to $prev_build"
    mv -f "$APP/riptide_bot.py.prev" "$APP/riptide_bot.py"
    printf '%s\n' "$prev_build" > "$APP/BUILD"
    sudo systemctl restart riptide
    sleep 5
    state=$(systemctl is-active riptide || true)
    notify "Riptide update $short FAILED — service would not start. Rolled back to ${prev_build}, now: ${state}."$'\n\n'"$(journalctl -u riptide -n 12 --no-pager | tail -c 600)"
    exit 1
fi
