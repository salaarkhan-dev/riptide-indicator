# indicators/ — one folder per indicator

Everything about one indicator lives in its own folder: the Pine source, the
Python port, the studies that measured it, the results those studies produced,
the pre-registrations written before they ran, its own tests, and its own
tools. Nothing about an indicator belongs in the repository root.

| folder | what it is | status |
|---|---|---|
| [`riptide/`](riptide/) | the production sweep-and-reversal engine the bot runs | **LIVE — do not edit without a parity check** |
| [`riptide_ms/`](riptide_ms/) | the market-structure engine (v2), the one usually charted | research |
| [`ccp/`](ccp/) | combined candle patterns and the grab line — the research bench | research, **verdict: nothing tradeable** |
| [`exhaustion/`](exhaustion/) | the 9-count and 13-count | ships as a watch, **off by default, measured at no edge** |
| [`undertow/`](undertow/) | structure bias + a pin at the pullback extreme | **spec only**, nothing built, nothing claimed |

## The layout, and what each part is for

```
indicators/<name>/
  INDICATOR.md      what it is, what was MEASURED, and where everything is
  pine/             the Pine sources — what you paste into TradingView
  port/             the Python transcription of the Pine, if one exists
  detector.py       or a detector, when there is no Pine to port from
  studies/          the measurements, and the .out file each one produced
  measurements/     what those studies concluded, in prose
  prereg/           what was promised BEFORE each study ran
  tools/            checkers and audits specific to this indicator
  tests/            its own tests, run by deploy/preflight.py
```

Not every indicator has every folder, and an empty one is not created to look
symmetrical. `riptide/` is a Pine file and nothing else, because its Python
side IS the bot.

**`measurements/` and `prereg/` are load-bearing, not paperwork.** Every
result in this repository was pre-registered before it was run, and the reason
is in [`ccp/measurements/CCP_FILTER_OVERFIT.md`](ccp/measurements/CCP_FILTER_OVERFIT.md):
a filter chosen by looking at the losers scored +0.089 in sample and −0.082
out. A study without a prereg beside it is a story about data, and the folders
are arranged so the absence is visible.

## Two trees, and why

An indicator that sends alerts has code in **two** places, deliberately:

| | where | why |
|---|---|---|
| research | `indicators/<name>/` | studies, Pine, ports, results — the whole record |
| runtime | `riptide/watchers/<name>.py` | the live adapter the bot imports |

The bot package must stay self-contained, because it is what systemd runs and
what `deploy/update.sh` pulls. `research/` and `indicators/` pull in the study
stack, fetch a thousand days of candles on import, and change weekly; a
refactor there must never be able to break a running scanner. So the live
adapter is a small file inside `riptide/`, and it says in its docstring which
`indicators/<name>/` folder holds the evidence for what it claims.

Where the same arithmetic exists in both trees — the exhaustion counts do —
a test runs BOTH and asserts they agree bar for bar, so a drift fails rather
than hides. See `exhaustion/tests/test_exhaust.py`.

## Adding an indicator

**1. Make it a folder.** `indicators/<name>/` with the layout above and an
`INDICATOR.md`. Copy an existing one; `exhaustion/` is the smallest complete
example.

**2. Measure it before you wire it up.** Write the pre-registration first —
the arms, the population, the bars it has to clear, and what you expect —
commit that, then run the study. `ccp/prereg/` has ten worked examples. An
indicator that has never been measured can still ship as a watch; it just has
to say so in its caveat, in the message, in the words the reader sees.

**3. If it should send alerts, register it.** A watch indicator is one module
in `riptide/watchers/` declaring four things — how to find its hits, how to
draw one digest row, how to group them, and what the message must admit about
the evidence. Then one import line in `riptide/watchers/__init__.py`, which is
the whole deployment switch: `app.py` starts a loop for everything registered,
`storage.py` creates one table for all of them, and `/<name>` routes to any of
them. There is no fourth place to remember.

The contract is `riptide/watchers/registry.py`. The shortest worked example is
`tests/test_watch.py`, which defines a complete fake indicator in about thirty
lines and runs the whole framework against it.

**4. Add its tests under `indicators/<name>/tests/`.** They are discovered by
glob, so `python3 deploy/preflight.py` picks them up with no edit anywhere.

**5. If it needs a Pine check, add it to `PINE_CHECKS`** in
`deploy/preflight.py`. That list is the one place in this repository where a
Pine checker's correct invocation is written down.

## Two indicators working together

Two watches never share a message, a dedupe namespace, a settings namespace or
a timer, and that is on purpose: a failure in one must not be able to silence
the other, and a digest that mixed two indicators would be a digest nobody
reads. Confluence between them is a **measurement question**, not a plumbing
one — every hit either watch records lands in `seen_watch` with its indicator,
its symbol, its timeframe and its bar close, which is exactly what a study
needs to ask whether two firing together is worth more than either alone.

That question has been asked here before and the answer was no. The trendline
confluence tag scored +0.206 R offline over 3773 signals and stalled at +0.7
SE on the held-out half; the whole line was removed. So the join belongs in a
study under `indicators/<name>/studies/`, with a prereg beside it, before any
of it reaches a message.

## Before you deploy

```
python3 deploy/preflight.py            # syntax, imports, every test, every pine check
python3 deploy/preflight.py ccp        # one indicator's checks, plus the shared tests
python3 deploy/preflight.py --quick    # syntax and imports only, about a second
```
