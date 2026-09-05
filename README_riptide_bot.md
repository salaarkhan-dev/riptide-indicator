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

## Layout

`riptide_bot.py` is a launcher; the implementation is a package beside it, so
the systemd unit's `ExecStart` never changes.

| | |
|---|---|
| `riptide/config.py` | settings from the environment, and `Cfg` — the engine's calibrated defaults, mirroring the Pine inputs |
| `riptide/engine.py` | the state machine. Pure and synchronous: no I/O, no clock, so it can be run against recorded candles |
| `riptide/exchange.py` | MEXC reads: contracts, turnover, candles |
| `riptide/storage.py` | SQLite dedupe and key/value bookkeeping |
| `riptide/telegram.py` | delivery and message formatting |
| `riptide/tracker.py` | scores alerts forward against candles already fetched. Observes only — the engine cannot see it |
| `riptide/scanner.py` | the scan cycle and the loop that drives it |
| `riptide/commands.py` | Telegram command handling |
| `riptide/app.py` | startup and task supervision |

`scanner` and `commands` import `telegram` as a module rather than pulling
`tg_send` into their own namespace, so a harness can substitute the sender in
one place — that is how `deploy/flood_test.py` throttles it.

## Multi-timeframe entries

`RIPTIDE_ENTRY_INTERVAL` splits where structure is found from where the entry
is placed. The pool, the sweep and the shift still come from
`RIPTIDE_INTERVAL`; once the shift confirms, the entry moves to the first gap
on the lower timeframe, with the stop on that timeframe's own structure — the
extreme reached between the shift and the gap.

The problem it solves: a Min30 gap sits where price has already been, and
often does not return. Over 12.5 days on 20 symbols:

| Entry | Filled within 5h | Of fills, reached 1R |
|---|---|---|
| Min30 gap + Min30 stop | 45% | 48% |
| Min15 gap + Min15 stop | **85%** | 51% |

So roughly twice as many setups turn into a 1R win, and the tighter stop
(median 0.68× the distance) does not cost hit rate.

**It does not make alerts faster — it makes them later.** A lower-timeframe
gap cannot exist until three of its candles have closed measured from the
shift bar's open, so a setup alert arrives a median 60 minutes after the same
setup would have alerted on the higher timeframe (quartiles +15 and +120). The
trade is a later alert for one that can be filled: 84% against 48%.

A setup with no usable gap on the lower timeframe keeps its higher-timeframe
entry rather than being dropped — 14 of 239 in the sample. Alerts show which,
as `Min30 → Min15` in the header.

**Read those numbers carefully.** One market regime, under a hundred filled
samples per variant, no fees, no slippage, and no break-even rule. Enough to
justify running it, not enough to size a position on. `riptide/mtf.py` carries
the same caveat at the top.

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

## Telegram commands

| | |
|---|---|
| `/status` | build, symbols, alert state, uptime, last and next scan |
| `/stats` | how the alerts have actually scored — see *Outcome tracking* |
| `/scan` | run a scan now instead of waiting for the close |
| `/pause` / `/resume` | stop sending while still recording, so resuming does not replay the backlog |
| `/update` | check GitHub for a new build now |
| `/restart` | restart the service |
| `/help` | the list |

Only `TELEGRAM_CHAT_ID` is obeyed. Both the chat and the sender must match it;
anything else is logged and ignored without a reply, so the bot never confirms
it exists to a stranger.

The update offset is persisted and advanced **before** a command runs.
Otherwise `/restart` would be redelivered to the process it just started, and
restart forever.

Symbols and settings are not editable from Telegram on purpose — they live in
`riptide.conf` on GitHub, which stays the single source of truth. A second
place to change them would drift out of sync.

This adds no trading capability. There is still no exchange key and no code
path that can place an order.

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

### Three timing limits, often confused

The chain is pool → **sweep** → **MSS** (structure shift) → **FVG** (the gap
the entry sits in). Three separate settings bound it, and they answer three
different questions:

| | | |
|---|---|---|
| `Cfg.max_bars_after_grab` | 50 | how long after the **sweep** the shift may come |
| `Cfg.max_bars_after_mss` | 10 | how long after the **shift** the gap may form |
| `RIPTIDE_FRESH_BARS` | 3 | how old the **setup** may be when the alert fires |

A long wait between the sweep and the entry is normal and fully alerted —
median 14 bars, quartiles 7 and 25, up to the 50-bar limit. Only the third
setting suppresses anything.

It measures from `Setup.detected_time`, the later of the shift bar and the gap
bar, because a setup needs both to exist. Measuring from the shift instead —
which the bot did until this was caught — silently binned every setup whose
gap took more than a bar to arrive: **76 of 2035 setups (4%) over 41.6 days**,
recorded and deduped, so the loss was permanent and invisible. Nominally they
scored better than the ones that were sent, though on 76 samples that is not
worth reading; the reason to fix it is that the gate was measuring the wrong
thing, not that the dropped ones looked good.

`detected_time` is the same bar outcome tracking starts scoring from. Both bugs
were the same mistake about when a setup starts existing.

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

## Outcome tracking

Every strategy figure quoted in this repo — the trend filter, the exit
comparison, the entry-timeframe test — comes from one 41-day backtest over
symbols chosen by their turnover *today*. That is survivorship bias, one
ranging regime, and no out-of-sample data. Testing more variants against that
same window cannot fix it.

Two things found while building the tracker show why that matters more than it
sounds.

**The backtests had lookahead.** `scan_leg` searches for the gap backwards from
the grab bar, so the gap often forms *before* the shift that makes the setup
detectable — 56% of the time, median 4 bars earlier, up to 41. Scoring from
the gap bar therefore counted fills from bars that had already closed before
the setup existed. Correcting it cost **0.229 R per setup (−22 SE)**, larger
than any effect the backtests were built to detect. The tracker starts scoring
from the later of the gap bar and the bar that had just closed when the alert
fired, which is exactly the bar a person could first have acted on.

**A published ranking evaporated.** The exit comparison once found the far
target clearly worst and the ordering perfectly monotonic. Re-run on a later
window with the scoring corrected, 3R is nominally *best* and all four targets
sit within half a standard error of each other. The ranking was one window's
noise read as a result — which is what a backtest with no out-of-sample check
will hand you, indefinitely, without ever looking wrong.

What survived both corrections is the trend separation: +0.135, +0.095, +0.110
across two windows, two symbol sets and two scoring methods. The absolute level
it sits on ranged from −0.05 to +0.32 over the same comparisons. Trust the
gap; do not size anything off the level.

`tracker.py` scores live alerts forward instead. Each fresh setup is armed with
the entry, stop and trend alignment that were alerted, and advanced every cycle
against candles the scan already fetched — no extra requests, no effect on what
is sent, and nothing the engine can read.

The simulated rule is the plain one the alert leads with:

- a limit at the entry, fillable for `RIPTIDE_TRACK_FILL_BARS` bars after the
  gap forms; a setup that never fills scores **0R**, so fill rate cannot be
  gamed by widening the entry
- the stop where the alert put it, the target at `RIPTIDE_TRACK_TARGET_R`
- **stop first** when one bar contains both — the reading that cannot flatter
  the result
- marked to market at the close after `RIPTIDE_TRACK_HORIZON_BARS`

MFE and MAE are stored in R per setup, so a different fixed target can be
scored from the same rows later without re-running anything.

Only setups that passed the freshness gate are tracked, **whether or not the
alert was sent** — a `/pause` or a delivery failure must not put a hole in the
sample. That gate is also what keeps this forward-only: on a first run the 600
bars of recorded history are all stale, so none of them arm.

A row whose symbol later leaves the scan list stops receiving candles and is
retired as `stale` past the point where it could resolve. Those are excluded
from the figures and counted separately in `/stats`, because a sample with an
invisible hole is worse than a smaller honest one.

Two things it does not model, both of which flatter the numbers: fees, and
slippage on the stop. Read `/stats` as an upper bound.

```
/stats
```

`update()` resumes from the last bar it processed, so a re-scan, a restart or a
manual `/scan` cannot double-count an excursion. Verified against an
independent one-shot scorer on 130 real setups across 10 symbols: bar-by-bar
replay and whole-history scoring agree exactly, and a repeat scan is a no-op.

## Settings

Engine defaults live in the `Cfg` dataclass and match the Pine inputs. Change
them there, not in the engine body.

| Variable | Default | Notes |
|---|---|---|
| `RIPTIDE_INTERVAL` | `Min30` | `Min15`, `Min30`, `Min60`, `Hour4` |
| `RIPTIDE_SYMBOLS` | all USDT perps | comma separated |
| `RIPTIDE_ENTRY_INTERVAL` | unset | lower timeframe for entries. Structure stays on `RIPTIDE_INTERVAL` |
| `RIPTIDE_FRESH_BARS` | `3` | only alert if the setup became **detectable** this recently — see *Three timing limits* |
| `RIPTIDE_SCAN_ON_START` | `1` | scan immediately on startup instead of waiting for the next close |
| `RIPTIDE_TG_RETRIES` | `4` | Telegram send attempts. Only provably-undelivered failures are retried |
| `RIPTIDE_TZ` | unset | IANA zone for the heartbeat's clock. Display only |
| `RIPTIDE_TG_COMMANDS` | `1` | accept commands from `TELEGRAM_CHAT_ID`. `0` disables |
| `RIPTIDE_SWEEP_ALERTS` | `1` | heads-up when a pool is swept, ahead of the shift. `0` disables |
| `RIPTIDE_SWEEP_SRC` | unset | which pools raise a heads-up. Unset = all. e.g. `Pivot` |
| `RIPTIDE_SWEEP_FRESH_BARS` | `2` | sweep freshness window. **Minimum 2** — see below |
| `RIPTIDE_LOOKBACK` | `600` | bars fetched per symbol |
| `RIPTIDE_CONCURRENCY` | `8` | parallel requests |
| `RIPTIDE_MIN_VOL` | `3000000` | min 24h turnover (USDT). Only applies when `RIPTIDE_SYMBOLS` is unset; an explicit list is never filtered. `0` disables. At the default this cuts ~1019 perps to ~96 |
| `RIPTIDE_TRACK` | `1` | score alerts forward and report with `/stats`. `0` disables |
| `RIPTIDE_TRACK_FILL_BARS` | `10` | bars the entry limit stays live. Past this the setup counts as 0R |
| `RIPTIDE_TRACK_HORIZON_BARS` | `60` | bars a filled setup is followed before being marked to market |
| `RIPTIDE_TRACK_TARGET_R` | `1.0` | target for the simulated rule |
| `RIPTIDE_DB` | `riptide.db` | dedupe, signal history and outcomes |
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
