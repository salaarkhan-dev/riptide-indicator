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

    # Sign-convention audit, on the NEW tree, before anything is installed.
    #
    # This exists because a comment reading "-1 is up" sat above six copies of
    # `supertrend() < 0` for weeks and nothing caught it: every verification
    # was a person reading that comment. The audit reads nothing — it buckets
    # each direction series by its own output and scores it against realised
    # price. See research/studies/signs.py.
    #
    # THE EXIT CODES MATTER MORE THAN THE CHECK. 1 means a check failed and
    # the tree is wrong. 2 means the exchange was unreachable, which is not a
    # failure of the commit, and blocking on it would turn an exchange outage
    # into a fake bug report. `timeout` returns 124 and is treated the same.
    # The static half of the audit needs no network and always runs, so a
    # re-introduction of the literal bug is caught even during an outage.
    local audit_out audit_rc warn=""
    audit_out=$(cd "$SRC" && PYTHONPATH="$SRC" timeout 180 \
                "$APP/.venv/bin/python" research/studies/signs.py 2>&1) \
        && audit_rc=0 || audit_rc=$?
    case "$audit_rc" in
        0)  log "sign audit passed" ;;
        2|124)
            log "sign audit skipped (no market data or timed out), continuing"
            warn=$'\n\n'"note: the sign audit could not reach the exchange, so only its static check ran." ;;
        *)  log "sign audit FAILED, not installing"
            notify "Riptide update $short BLOCKED by the sign audit. Nothing installed, still running the previous build."$'\n\n'"$(printf '%s' "$audit_out" | tail -c 700)"
            return 1 ;;
    esac

    # Pine/Python parity is ADVISORY, never blocking. A drift here means the
    # chart and the bot disagree; it is not a reason to refuse a Python fix,
    # and making it blocking would let an indicator edit wedge the service.
    local parity_out
    if ! parity_out=$(cd "$SRC" && PYTHONPATH="$SRC" timeout 60 \
                      "$APP/.venv/bin/python" deploy/check-parity.py 2>&1); then
        log "parity check reported drift (advisory)"
        warn+=$'\n\n'"parity drift: $(printf '%s' "$parity_out" | tail -c 300)"
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
        notify "Riptide updated: ${prev_build} → ${short}${warn}"
        rm -rf "$APP/riptide.old" "$APP/riptide_bot.py.prev"
    else
        log "service did not come up — rolling back to $prev_build"
        # Capture the FAILING journal before the rollback restart overwrites
        # the tail with the old build's healthy startup. Reading it after the
        # restart is how a failure once reported itself as a working service:
        # every line in the notification came from the build that was fine.
        local fail_log
        fail_log=$(journalctl -u riptide -n 40 --no-pager \
                   | grep -iE "error|traceback|exception|[A-Za-z]+Error" \
                   | tail -c 600 || true)
        [[ -n ${fail_log:-} ]] || fail_log=$(journalctl -u riptide -n 12 \
                                             --no-pager | tail -c 600 || true)
        rm -rf "$APP/riptide"
        [[ -d $APP/riptide.old ]] && mv "$APP/riptide.old" "$APP/riptide"
        [[ -f $APP/riptide_bot.py.prev ]] && mv -f "$APP/riptide_bot.py.prev" "$APP/riptide_bot.py"
        printf '%s\n' "$prev_build" > "$APP/BUILD"
        sudo -n systemctl restart riptide
        sleep 5
        local state
        state=$(systemctl is-active riptide || true)
        notify "Riptide update $short FAILED — service would not start. Rolled back to ${prev_build}, now: ${state}."$'\n\n'"${fail_log}"
        return 1
    fi
}

main "$@"
