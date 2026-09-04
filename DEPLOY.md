# Riptide scanner — Oracle Cloud deployment (phase 1, alerts only)

Ampere A1 (aarch64), Ubuntu 24.04, user `ubuntu`. Outbound connections only —
nothing here opens a port or touches the security list.

## Pre-flight results

The MEXC fetch layer was tested against the live API before writing any of
this, since that was the one untested part. **No code changes were needed.**

| Check | Result |
|---|---|
| `https://api.mexc.com/api/v1/contract/detail` | 200, 1174 contracts |
| `https://contract.mexc.com` (the old host) | connection times out — the `MEXC_BASE` default is correct |
| `quoteCoin` / `state` / `apiAllowed` field names | all present and the expected types (`str` / `int` / `bool`) |
| `state` semantics | every listed contract is `0`, so `state != 0` filters nothing today but is harmless |
| Symbols passing `list_symbols` | 1019 USDT perps; all six of the starting symbols present |
| `contract/kline/{symbol}` | dict-of-lists, `time` in **seconds**, 600 bars returned |
| Forming-bar drop | confirmed — 600 rows in, 599 closed candles out |
| `run_engine` on live BTC_USDT | 11 setups over the 599-bar window |
| Full `cycle()` over 6 symbols | 0.6 s |
| Dedupe | second cycle immediately after sends 0 |
| Message formatting | valid HTML, TradingView link resolves |

## One thing to know before step 4

`RIPTIDE_ALERT_FIRST_RUN=1` **does not flood.** Measured on live data: 81
setups across the six symbols, **0** of them sent.

`cycle()` gates every send on two independent conditions:

```python
bootstrap = first_run(db) and not ALERT_ON_FIRST_RUN
fresh     = (now - s.mss_time) <= FRESH_BARS * step
...
if fresh and not bootstrap:
```

`RIPTIDE_ALERT_FIRST_RUN` only clears `bootstrap`. The `fresh` gate still
drops anything whose shift is older than 3 bars — and every *historic* setup
is older than that by definition. The newest one in the window was 5.8 bars
old, so the flag alone sends nothing.

If you had run step 4 as written you would have seen zero messages and had no
way to tell "Telegram is broken" from "no setups qualified".

`deploy/flood-test.sh` handles it by also overriding `RIPTIDE_FRESH_BARS` for
that one run. Both are exported into that process only — no code edit, no
`.env` change, so normal alerting behaviour is untouched. Verified: 81
messages sent, correctly formatted.

The code itself is unchanged. Making the flag flood on its own would mean
editing `cycle()`, which your constraints put off-limits — say the word if
you'd rather have that than the env override.

## Deploy

From your machine:

```bash
git clone https://github.com/salaarkhan-dev/riptide-indicator.git
cd riptide-indicator
git checkout claude/oracle-free-tier-alerts-3vzflp
scp -i <key> -r riptide_bot.py deploy ubuntu@<ip>:~/
ssh -i <key> ubuntu@<ip>
```

### 1 & 2 — prepare and install

```bash
bash deploy/install.sh
```

apt update/upgrade, installs `python3-venv` + `chrony`, asserts `aarch64`,
Python ≥ 3.10 and a synchronized clock, creates the venv, installs `aiohttp`,
and prompts for the Telegram credentials. **Input is hidden and never echoed
or logged.** `.env` is written `600`, owned by `ubuntu`, and is the only copy
of the secrets on the box — `.gitignore` already excludes `.env` and `*.db`.

Any failed check stops the script.

### 3 — foreground test

```bash
cd ~/riptide && set -a && . ./.env && set +a && .venv/bin/python riptide_bot.py
```

Expect `riptide up: 6 symbols, Min30 bars` and a "Riptide scanner started"
Telegram message. **Confirm that arrived before continuing.** Then wait for the
bar close (≤30 min) for `scanned 6 symbols, sent 0 alerts` and `first run:
history recorded, nothing sent`. Zero alerts on the first cycle is correct.

`no symbols; check MEXC_BASE or RIPTIDE_SYMBOLS` should not appear — that path
was tested live and passes.

### 4 — prove alerts deliver

Ctrl-C the foreground process, then:

```bash
bash deploy/flood-test.sh
```

Defaults to `BTC_USDT` alone (~11 messages). All six symbols is 81 messages,
which will trip Telegram's per-chat rate limit and show up as `telegram 429`
in the log — one symbol is enough to prove delivery and formatting. Pass a
list if you want more: `bash deploy/flood-test.sh BTC_USDT,ETH_USDT`.

Ctrl-C once messages arrive. The script deletes `riptide.db` on exit, so
normal behaviour resumes.

### 5 — install the service

```bash
bash deploy/install-service.sh
sudo reboot
# reconnect
systemctl is-enabled riptide && systemctl is-active riptide
journalctl -u riptide --since "5 minutes ago"
```

The unit is `deploy/riptide.service`: `EnvironmentFile=/home/ubuntu/riptide/.env`,
`Restart=always`, `RestartSec=10`. No secrets in the unit file. It adds
`Wants=network-online.target` alongside the README's `After=` — without the
`Wants`, `After=network-online.target` is inert on a default Ubuntu install and
the service can start before the network is up, costing a restart cycle on
every boot.

## Done when

- [ ] `systemctl is-enabled riptide` → `enabled`
- [ ] survives a reboot with no intervention
- [ ] "Riptide scanner started" arrived in Telegram
- [ ] a completed cycle in `journalctl -u riptide`
- [ ] `.env` is `600` and holds the only copy of the secrets

## Afterwards

Follow the logs:

```bash
journalctl -u riptide -f
```

Widen to every USDT perpetual (~1019 symbols) — remove the symbol line from
`.env` and restart:

```bash
sudo sed -i '/^RIPTIDE_SYMBOLS=/d' /home/ubuntu/riptide/.env
sudo systemctl restart riptide
journalctl -u riptide -f
```

The first cycle after that is silent for the newly added symbols: they have no
history in `riptide.db`, and the `fresh` gate means only shifts from the last
3 bars alert. Expect alert volume to rise sharply — a full-market cycle is
~1019 symbols at concurrency 8. Raise `RIPTIDE_CONCURRENCY` if a cycle starts
running long against the 30-minute bar.

Restore the short list by putting the line back:

```bash
echo 'RIPTIDE_SYMBOLS=BTC_USDT,ETH_USDT,SOL_USDT,HYPE_USDT,TIA_USDT,INJ_USDT' \
  | sudo tee -a /home/ubuntu/riptide/.env
sudo systemctl restart riptide
```

## Not included, deliberately

No API key, no order placement, no code path that could place one. No Docker,
no reverse proxy, no inbound port. One Python process under systemd, one
dependency (`aiohttp`). Engine logic and `Cfg` defaults are untouched.
