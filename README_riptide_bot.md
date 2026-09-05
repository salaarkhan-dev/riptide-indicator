# Riptide scanner - phase 1

Alerts only. No exchange API key, no orders. Polls MEXC futures candles after
each bar close, runs the Riptide engine, sends new setups to Telegram.

## 1. Telegram

1. Message `@BotFather`, send `/newbot`, copy the token.
2. Send any message to your new bot.
3. Open `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy
   `result[0].message.chat.id`.

## 2. Server

Any small box. Hetzner CX22 (~EUR 4/mo) or Oracle always-free ARM.

```bash
sudo apt update && sudo apt install -y python3-venv
mkdir -p ~/riptide && cd ~/riptide
python3 -m venv .venv && . .venv/bin/activate
pip install aiohttp
# copy riptide_bot.py here
```

Test in the foreground first:

```bash
export TELEGRAM_TOKEN=123:ABC
export TELEGRAM_CHAT_ID=456789
export RIPTIDE_INTERVAL=Min30
export RIPTIDE_SYMBOLS=BTC_USDT,ETH_USDT,HYPE_USDT,TIA_USDT,INJ_USDT
python riptide_bot.py
```

The first run records history silently and sends nothing - that is deliberate,
otherwise you would get a flood of stale setups. From the second bar close it
alerts on new ones only. To see the flood once for testing, set
`RIPTIDE_ALERT_FIRST_RUN=1` and delete `riptide.db` first.

Leave `RIPTIDE_SYMBOLS` unset to scan every USDT perpetual above
`RIPTIDE_MIN_VOL` of 24h turnover.

## Two kinds of alert

**Sweep** — the liquidity grab on its own, the X on the chart, sent on the
close of the bar that took the pool. No entry or stop, because there is no
setup yet: it is a heads-up to open the chart and watch for the shift and
then the FVG. Most sweeps never become setups.

**Setup** — the finished pattern: sweep, structure shift, fair value gap.
Carries entry, stop and targets.

Measured over 12.5 days on 20 symbols, sweeps outnumber setups roughly 5:1,
and the share that goes on to produce a setup varies sharply by pool type:

| Pool | Sweeps | Setups | Converts | Sweeps/day |
|---|---|---|---|---|
| Pivot | 767 | 213 | **28%** | 61.6 |
| Day | 353 | 32 | 9% | 28.3 |
| Week | 50 | 1 | 2% | 4.0 |

The intuition that daily and weekly levels are the significant ones is not
what the numbers show. Keep that in mind if you ever narrow
`RIPTIDE_SWEEP_SRC`; it is unset by default, which alerts on all of them.

Expect roughly 95 sweep messages a day on 20 symbols, against 20 setups. Cut
the symbol list, not the source filter, if that is too many.

### Restarts

The scan loop sleeps before it scans, so without `RIPTIDE_SCAN_ON_START` a
restart is blind until the next bar close — up to a full bar. That also
loses signal rather than merely delaying it: a sweep on the bar that closed
just before the restart is `2 * step + 10s` old by the first scheduled
cycle, past its 2-bar window, so it is never sent.

Scanning on startup fixes both. Repeating work is safe — dedupe skips
anything the previous process recorded, the freshness gate still applies,
and an empty database still bootstraps silently.

The daily heartbeat is separate and still fires once per restart:
`last_heartbeat` lives in memory and resets to `0.0` on every start, so
"Riptide alive" is a restart marker as much as a daily one.

### Why `RIPTIDE_SWEEP_FRESH_BARS` cannot be 1

`Candle.t` is the bar's **open** time, so a bar that has just closed is
already one full step old, and the scan wakes a further 10s after the close.
At `Min30` a sweep that just confirmed is 1810s old, against a window of
1×1800s. Setting this to 1 therefore suppresses every sweep alert silently —
no error, just nothing arriving. 2 is the minimum, and means "the bar that
just closed": the previous bar lands at 3610s and is correctly excluded, so
each sweep alerts exactly once.

## 3. Run it as a service

`/etc/systemd/system/riptide.service`:

```ini
[Unit]
Description=Riptide scanner
After=network-online.target

[Service]
User=YOUR_USER
WorkingDirectory=/home/YOUR_USER/riptide
EnvironmentFile=/home/YOUR_USER/riptide/.env
ExecStart=/home/YOUR_USER/riptide/.venv/bin/python riptide_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

`.env` (chmod 600) holds the same variables without `export`.

```bash
sudo systemctl enable --now riptide
journalctl -u riptide -f
```

Make sure the clock is synced (`timedatectl`) - bar alignment depends on it.

## Settings

Engine defaults live in the `Cfg` dataclass and match the Pine inputs. Change
them there, not in the engine body.

| Variable | Default | Notes |
|---|---|---|
| `RIPTIDE_INTERVAL` | `Min30` | `Min15`, `Min30`, `Min60`, `Hour4` |
| `RIPTIDE_SYMBOLS` | all USDT perps | comma separated |
| `RIPTIDE_FRESH_BARS` | `3` | only alert if the shift is this recent |
| `RIPTIDE_SCAN_ON_START` | `1` | scan immediately on startup instead of waiting for the next close |
| `RIPTIDE_TG_RETRIES` | `4` | Telegram send attempts. Only provably-undelivered failures are retried |
| `RIPTIDE_TZ` | unset | IANA zone for the heartbeat's clock. Display only |
| `RIPTIDE_SWEEP_ALERTS` | `1` | heads-up when a pool is swept, ahead of the shift. `0` disables |
| `RIPTIDE_SWEEP_SRC` | unset | which pools raise a heads-up. Unset = all. e.g. `Pivot` |
| `RIPTIDE_SWEEP_FRESH_BARS` | `2` | sweep freshness window. **Minimum 2** — see below |
| `RIPTIDE_LOOKBACK` | `600` | bars fetched per symbol |
| `RIPTIDE_CONCURRENCY` | `8` | parallel requests |
| `RIPTIDE_MIN_VOL` | `3000000` | min 24h turnover (USDT). Only applies when `RIPTIDE_SYMBOLS` is unset; an explicit list is never filtered. `0` disables. At the default this cuts ~1019 perps to ~96 |
| `RIPTIDE_DB` | `riptide.db` | dedupe and signal history |
| `MEXC_BASE` | `https://api.mexc.com` | futures moved here in Jan 2026 |

## Verifying against the chart

Run it alongside the indicator for a week on a handful of pairs. For each
alert, open that symbol and check the X, the shift label and the zone sit on
the bars the message describes. Differences will come from:

- sessions - not implemented here, off by default in the indicator too
- `Cfg` drifting from the Pine inputs after you tune one and not the other
- the indicator's deferred drawing, which puts the pattern on the chart at the
  shift bar even though the sweep happened earlier

## What this deliberately does not do

No API key is read and no order can be placed. Execution is phase 3, after the
alerts have matched the chart and after you have re-run the stats with the
realistic fill model.
