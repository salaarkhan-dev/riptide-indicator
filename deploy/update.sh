#!/usr/bin/env bash
#
# Pull the branch, validate, install, restart, verify — roll back if the
# service does not come up. Run by riptide-update.timer every few minutes;
# also safe to run by hand.
#
# Exits silently when there is nothing new, so the timer stays quiet.
#
# Everything lives inside main(), called on the last line. bash reads a script
# incrementally by byte offset, and this script git-pulls a newer copy of
# itself partway through — without the wrapper, execution would continue at an
# offset into a file that has changed underneath it.

set -euo pipefail

main() {
    local APP=/home/ubuntu/riptide
    local SRC=/home/ubuntu/riptide-src
    local BRANCH="${RIPTIDE_BRANCH:-claude/oracle-free-tier-alerts-3vzflp}"

    log() { echo "$(date -u '+%Y-%m-%d %H:%M:%S') $*"; }

    # Best effort, and never allowed to fail the update. Reads the token
    # straight from .env rather than sourcing it, so nothing lands in the
    # environment.
    notify() {
        local text="$1" tok chat
        [[ -r $APP/.env ]] || return 0
        tok=$(sed -n 's/^TELEGRAM_TOKEN=//p'    "$APP/.env" | head -1) || true
        chat=$(sed -n 's/^TELEGRAM_CHAT_ID=//p' "$APP/.env" | head -1) || true
        [[ -n ${tok:-} && -n ${chat:-} ]] || return 0
        curl -sS -m 15 -X POST "https://api.telegram.org/bot${tok}/sendMessage" \
             -d "chat_id=${chat}" --data-urlencode "text=${text}" \
             -o /dev/null 2>/dev/null || true
    }

    [[ -d $SRC/.git ]] || { log "no clone at $SRC — run install-autoupdate.sh"; return 1; }

    cd "$SRC"
    git fetch --quiet origin "$BRANCH" || { log "fetch failed (network?), will retry"; return 0; }

    local have want short
    have=$(git rev-parse HEAD)
    want=$(git rev-parse "origin/$BRANCH")
    [[ $have == "$want" ]] && return 0          # nothing new — stay silent

    short=$(git rev-parse --short "origin/$BRANCH")
    log "new commit $short, updating"

    # Fast-forward only. A diverged local clone means someone edited on the
    # box; stop rather than clobber it.
    if ! git merge --ff-only "origin/$BRANCH" --quiet; then
        log "cannot fast-forward — local clone has diverged"
        notify "Riptide update skipped: $SRC has local changes that would be overwritten. Needs a look."
        return 1
    fi

    # Byte-compile the whole package with the venv's own interpreter before
    # anything is installed.
    if ! "$APP/.venv/bin/python" -m compileall -q \
            "$SRC/riptide" "$SRC/riptide_bot.py" 2>/tmp/riptide-compile.err; then
        log "compile failed, not installing"
        notify "Riptide update $short FAILED to compile. Nothing installed, still running the previous build."$'\n\n'"$(head -c 400 /tmp/riptide-compile.err)"
        return 1
    fi

    local prev_build
    prev_build=$(cat "$APP/BUILD" 2>/dev/null || echo unknown)

    # Stage the package beside the live one and swap, so the window where the
    # tree is half-written is not one the service can start in.
    rm -rf "$APP/riptide.new" "$APP/riptide.old"
    cp -r "$SRC/riptide" "$APP/riptide.new"
    cp -f "$APP/riptide_bot.py" "$APP/riptide_bot.py.prev" 2>/dev/null || true
    [[ -d $APP/riptide ]] && mv "$APP/riptide" "$APP/riptide.old"
    mv "$APP/riptide.new" "$APP/riptide"

    install -m 644 "$SRC/riptide_bot.py" "$APP/riptide_bot.py"
    [[ -f $SRC/riptide.conf ]] && install -m 644 "$SRC/riptide.conf" "$APP/riptide.conf"
    printf '%s\n' "$short" > "$APP/BUILD"

    log "restarting service"
    sudo -n systemctl restart riptide

    # Give it time to bind, fetch symbols and run the startup scan.
    sleep 10

    if systemctl is-active --quiet riptide; then
        log "update to $short ok"
        notify "Riptide updated: ${prev_build} → ${short}"
        rm -rf "$APP/riptide.old" "$APP/riptide_bot.py.prev"
    else
        log "service did not come up — rolling back to $prev_build"
        rm -rf "$APP/riptide"
        [[ -d $APP/riptide.old ]] && mv "$APP/riptide.old" "$APP/riptide"
        [[ -f $APP/riptide_bot.py.prev ]] && mv -f "$APP/riptide_bot.py.prev" "$APP/riptide_bot.py"
        printf '%s\n' "$prev_build" > "$APP/BUILD"
        sudo -n systemctl restart riptide
        sleep 5
        local state
        state=$(systemctl is-active riptide || true)
        notify "Riptide update $short FAILED — service would not start. Rolled back to ${prev_build}, now: ${state}."$'\n\n'"$(journalctl -u riptide -n 12 --no-pager | tail -c 600)"
        return 1
    fi
}

main "$@"
