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

Leave `RIPTIDE_SYMBOLS` unset to scan every USDT perpetual.

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
| `RIPTIDE_LOOKBACK` | `600` | bars fetched per symbol |
| `RIPTIDE_CONCURRENCY` | `8` | parallel requests |
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
