#!/usr/bin/env bash
#
# One-time setup for hands-off updates.
#
#     bash deploy/install-autoupdate.sh
#
# Afterwards: edit riptide.conf or riptide_bot.py on GitHub, commit, and the
# server picks it up within ~5 minutes, validates it, restarts, and messages
# you the result. No SSH.
#
# Outbound only — the box polls GitHub. Nothing new listens.

set -euo pipefail

APP=/home/ubuntu/riptide
SRC=/home/ubuntu/riptide-src
REPO="${RIPTIDE_REPO:-https://github.com/salaarkhan-dev/riptide-indicator.git}"
BRANCH="${RIPTIDE_BRANCH:-claude/oracle-free-tier-alerts-3vzflp}"

die() { echo "FAIL: $*" >&2; exit 1; }
ok()  { echo "  ok: $*"; }

[[ -f $APP/.env ]]                 || die "$APP/.env missing — run install.sh first"
[[ -x $APP/.venv/bin/python ]]     || die "venv missing — run install.sh first"
command -v git >/dev/null 2>&1     || sudo apt-get install -y git

echo "== 1. clone =="
if [[ -d $SRC/.git ]]; then
    git -C "$SRC" fetch --quiet origin "$BRANCH"
    git -C "$SRC" checkout --quiet -B "$BRANCH" "origin/$BRANCH"
    ok "updated existing clone at $SRC"
else
    git clone --quiet --branch "$BRANCH" "$REPO" "$SRC"
    ok "cloned to $SRC"
fi
chmod +x "$SRC"/deploy/*.sh
printf '%s\n' "$(git -C "$SRC" rev-parse --short HEAD)" > "$APP/BUILD"
ok "build $(cat "$APP/BUILD")"

echo
echo "== 2. settings move out of .env and into the repo =="
install -m 644 "$SRC/riptide.conf" "$APP/riptide.conf"
ok "riptide.conf installed"

# The bot is a package now; make sure the app dir has it before restarting.
install -m 644 "$SRC/riptide_bot.py" "$APP/riptide_bot.py"
rm -rf "$APP/riptide.new"
cp -r "$SRC/riptide" "$APP/riptide.new"
rm -rf "$APP/riptide"
mv "$APP/riptide.new" "$APP/riptide"
ok "riptide/ package installed"

# .env keeps only the secrets. Anything RIPTIDE_* left there would be shadowed
# by riptide.conf anyway (systemd applies the later EnvironmentFile last), and
# a stale duplicate is exactly the kind of thing that wastes an hour later.
if grep -q '^RIPTIDE_' "$APP/.env"; then
    cp -a "$APP/.env" "$APP/.env.bak.$(date +%Y%m%d%H%M%S)"
    echo "  current RIPTIDE_* lines in .env (now superseded by riptide.conf):"
    grep '^RIPTIDE_' "$APP/.env" | sed 's/^/      /'
    grep -v '^RIPTIDE_' "$APP/.env" > "$APP/.env.tmp"
    mv "$APP/.env.tmp" "$APP/.env"
    chmod 600 "$APP/.env"
    ok "removed from .env (backup kept, mode $(stat -c '%a' "$APP/.env"))"
    echo "  NOTE: if your symbol list differed from riptide.conf, edit the file"
    echo "        on GitHub — the box no longer reads it from .env."
else
    ok ".env already holds secrets only"
fi

echo
echo "== 3. permission to restart the service =="
sudo tee /etc/sudoers.d/riptide-update >/dev/null <<'EOF'
ubuntu ALL=(root) NOPASSWD: /usr/bin/systemctl restart riptide, /bin/systemctl restart riptide, /usr/bin/systemctl start riptide-update.service, /bin/systemctl start riptide-update.service
EOF
sudo chmod 440 /etc/sudoers.d/riptide-update
sudo visudo -c -f /etc/sudoers.d/riptide-update >/dev/null || die "bad sudoers file"
ok "scoped to 'restart riptide' and 'start riptide-update.service' only"

echo
echo "== 4. units =="
sudo cp "$SRC/deploy/riptide.service"        /etc/systemd/system/riptide.service
sudo cp "$SRC/deploy/riptide-update.service" /etc/systemd/system/riptide-update.service
sudo cp "$SRC/deploy/riptide-update.timer"   /etc/systemd/system/riptide-update.timer
sudo chmod 644 /etc/systemd/system/riptide*.service /etc/systemd/system/riptide-update.timer
sudo systemctl daemon-reload
sudo systemctl enable --now riptide-update.timer
ok "timer enabled"

echo
echo "== 5. apply the current commit now =="
sudo systemctl restart riptide
sleep 8
systemctl is-active --quiet riptide || die "riptide did not restart — check journalctl -u riptide"
ok "riptide active on build $(cat "$APP/BUILD")"

echo
systemctl list-timers riptide-update.timer --no-pager || true
echo
echo "Done. From now on:"
echo "  - edit riptide.conf or riptide_bot.py on github.com (phone is fine)"
echo "  - commit to $BRANCH"
echo "  - within ~5 min the box updates itself and messages you the result"
echo
echo "  check timer:   systemctl list-timers riptide-update.timer"
echo "  check updates: journalctl -u riptide-update -n 30"
echo "  force now:     sudo systemctl start riptide-update.service"
