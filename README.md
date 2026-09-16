# riptide-indicator

A liquidity-sweep alert bot, the Pine indicators it came from, and the
measurements that decide what any of it is allowed to claim.

**It sends alerts. It does not trade.** There is no exchange API key and no
order placement anywhere in this repository, and there must not be.

## The map

| | what |
|---|---|
| `riptide_bot.py`, `riptide.conf` | the entry point and the only file you edit to configure it |
| [`riptide/`](riptide/) | the live bot: engine, scanner, alerts, outcome tracking, Telegram commands |
| [`riptide/watchers/`](riptide/watchers/) | the live adapter for each heads-up indicator, plus the registry that describes one |
| [`indicators/`](indicators/README.md) | **one folder per indicator** — Pine, ports, studies, results, preregs, tests |
| [`research/`](research/README.md) | the shared harness: one scorer, one data loader, one reporting format |
| [`tests/`](tests/) | the bot's own tests |
| [`deploy/`](deploy/) | install, systemd units, the update path, and every check |
| [`docs/`](docs/) | the measurement log, the strategy notes, the setup guides |

## Before you deploy

```
python3 deploy/preflight.py
```

Syntax, every first-party import, every test in `tests/` and
`indicators/*/tests/`, and every Pine check — one command, one exit code,
about seven seconds. `--quick` is the first two stages only; a bare indicator
name (`python3 deploy/preflight.py ccp`) narrows it to that indicator plus the
shared suite.

It runs nothing that touches the network, an order, or a secret.

## Adding an indicator

A folder under `indicators/`, and — if it should send alerts — one module in
`riptide/watchers/` plus one import line. [`indicators/README.md`](indicators/README.md)
is the whole procedure, including why the research code and the live adapter
live in two different trees.

## What this project actually believes

Two things, and they are the reason most of the folders above exist.

**A result is only a result if it was pre-registered.** Every study here has a
prereg committed before it ran, naming the arms, the population and the bars it
has to clear. The demonstration is in
[`indicators/ccp/measurements/CCP_FILTER_OVERFIT.md`](indicators/ccp/measurements/CCP_FILTER_OVERFIT.md):
a filter chosen by looking at the losers scored +0.089 in sample and **−0.082**
out of sample.

**A signal has to beat its own control.** Twice now an idea looked obviously
useful, measured positive, and lost to a seeded random-bar entry of the same
shape — so the trendline line was removed after that, and the exhaustion watch
ships off and says so in every message it sends. The digests carry their own
caveat in the words the reader sees, not in a footnote.

`docs/MEASUREMENTS.md` is an append-only log and includes work that has since
been removed from the repository; where it disagrees with an indicator's own
`INDICATOR.md`, the `INDICATOR.md` is the current one.
