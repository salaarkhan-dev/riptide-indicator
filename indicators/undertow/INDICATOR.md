# Riptide Undertow — market-structure bias + a single-candle pin

**Status: MEASURED THREE TIMES, all negative. Ships as a watch, OFF by
default, saying so in every message.**

| study | result |
|---|---|
| [`UNDERTOW_PARAMS.md`](measurements/UNDERTOW_PARAMS.md) | −0.093 / +0.071 / −0.063 R per trade on a holdout sharing neither symbols nor calendar with the search; **lost to a random entry on two of three** |
| [`UNDERTOW_PIN_VALUE.md`](measurements/UNDERTOW_PIN_VALUE.md) | the candle taxonomy adds nothing; removing it scored **higher** on two of three |
| [`UNDERTOW_EXITS.md`](measurements/UNDERTOW_EXITS.md) | 8–12% of setups really do reach 7R — and a **coin reaches 7R 12.5% of the time** |
| [`UNDERTOW_BACKUP_FILL.md`](measurements/UNDERTOW_BACKUP_FILL.md) | the OB/FVG backup nets **+0.03 R per armed setup**, positive on 3 of 3 and significant on none — because two large, individually significant halves nearly cancel |
| [`UNDERTOW_LATE_BACKUP.md`](measurements/UNDERTOW_LATE_BACKUP.md) | waiting for the Focus limit to expire removes the tax **and all the opportunity**: 100% of the +0.6 R trades fill inside the window, median 1–2 bars |
| [`UNDERTOW_BIAS_SOURCE.md`](measurements/UNDERTOW_BIAS_SOURCE.md) | five direction sources — structure, EMA, Supertrend, Slope, range position — and **none beat the baseline**. EMA swung 0.54 R per trade between two halves of the same universe, which is the clearest "this is noise" in the project |

**It ships anyway, off by default, for one reason.** One explanation survives
all three and no backtest can reach it: whether a human choosing which one in
ten setups to take beats the machine taking all of them. That needs a
*prospective* record — alerts fired forward, taken or skipped, outcomes written
down — and `riptide/watchers/undertow.py` is the instrument for building one.
**19 alerts a day** across 23 symbols on all three timeframes.

[`SPEC.md`](SPEC.md) is the design.

## In one paragraph

Find the trend from major/minor market structure and refuse to trade a trend
that is ending. Inside it, wait for the counter-trend-coloured pin at the top
of a pullback — green in a downtrend, red in an uptrend — and take its high,
low and open as three levels. When price has closed beyond **both** the high
and the low, in either order, place a limit at the open. Stop above the
pullback, target 3R.

## What is claimed, and what is not

**Not an edge.** See the table above and the measurement file behind it.

**The candle adds nothing.** A six-arm ablation
([`UNDERTOW_PIN_VALUE.md`](measurements/UNDERTOW_PIN_VALUE.md)) removed one gate
at a time over 12,000 bars x 23 symbols. Full rule minus location-only is
**−0.073, −0.049, +0.092 R** on 15m / 30m / 1h — inside ±0.15 everywhere, not
close to significance, and not even a consistent sign. On two of three, *no
candle test at all* scored higher with twice the trades. The 16-variant
taxonomy, the wick-edge doji margin and the whole of input group 2 are
describing a filter that does not filter.

The honest version of this strategy is one sentence: **take the pullback
extreme while the structure bias is running.**

**THE LARGEST EFFECT FOUND ANYWHERE IN THIS INDICATOR**, and it is given
straight back. Decomposing the backup fill setup by setup:

* a setup that arms, runs 1R away without filling, then retraces into a zone is
  worth **+0.56 to +0.67 R**, on ~400 trades per timeframe, clustered z of
  **4 to 7**. Not noise, not small.
* taking that same zone when price was going to return to the Focus anyway
  costs **−0.23 to −0.29 R**, also z 5 to 7, and it happens ~1.4× as often.

**You cannot take only the good half**: which one you are in depends on whether
price later returns to the Focus, which is in the future at the moment of
entry. The tradeable number is the net, +0.02 R, z 0.6. The split is diagnosis.

That pointed at one clean hypothesis — place the backup only *after* the Focus
limit expires, so pre-emption is impossible by construction — and it has now
been run and **failed structurally**: 100% of the +0.6 R trades fill INSIDE the
20-bar window, median 1–2 bars. There is nothing left for a late design to
take. The two halves are the same population, separated only by what price did
afterwards.

**Three further things are established**, and they are worth more than the
verdict:

1. **The bias gate does two jobs and probably only one works.** The ghost
   column — setups the gate cancelled, walked forward anyway — says cancelling
   an *already-armed* setup saves 0.40 to 0.61 R each, on all three
   timeframes. But removing the Ending rules entirely (ablation arm A5) is
   *better* than keeping them on 15m, identical on 30m and worse on 1h. Both
   can be true if the cancellation earns its place and the admission block does
   not. That is a hypothesis, nothing here varied the two independently, and it
   is Undertow's most concrete open question.
2. **Selecting on a chart is worth about −0.31 R per trade.** Best-of-48 on
   train, then holdout: −0.377, −0.277, −0.286. Three timeframes, same answer.
3. **A pivot measured in bars really is a different rule on every timeframe,
   and `swingSrc="price move"` fixes it** — a swing as k × the last 24h range
   survives a 4:1 aggregation at ×0.89 against ×0.30 for the bar pivot. It buys
   consistency, not expectancy.
4. **`maxLive = 4` is not a neutral setting.** It exists for TradingView's
   drawing budget, and on these populations it refuses more setups than it
   trades — 683 against 811 fills on 15m at the baseline, and seven to nine per
   fill once a gate is removed. It voided the first ablation run. The chart's
   "at cap" row is the same effect, and any number read off the panel is biased
   by it.

**What the studies cannot say.** The parameter study had 45–153 trades per
panel, an MDE of about ±0.5 R. The ablation is far better powered — 700 to
2,400 trades per arm, and 11,000–12,000 on the widest — and there the best
estimate of the underlying bet lands at **−0.04 to −0.07 R ± 0.03** after 7bp
of fees. That is what a zero-edge entry with costs on looks like. Neither study
finds a rate anyone could trade against in either direction; what they exclude
is the +0.27 to +0.45 R the single charts appeared to show.

The two nearest priors in this repository both came back negative and both
pointed here:

* `indicators/ccp/measurements/CCP_PATTERN_EXPLORE.md` — the same single-candle
  pins, scored at liquidity grabs: no edge, and **the pin added nothing** over
  the location alone.
* `indicators/ccp/measurements/CCP_CONTEXT_FILTERS.md` — EMA / ADX / Supertrend
  trend filters as gates: all failed, and they improved *seeded random entries*
  more than real ones.

Neither refutes this. The bias here is market structure rather than a moving
average, the pin sits at a pullback extreme rather than at a grab, and the pin
is not being asked to predict anything — it supplies the levels. But they are
the closest priors, they point the same way, and the reason v1 is built to be
measurable from the first line is that this design has to clear a bar those two
did not.

The strategy's own evidence before the port was manual bar-replay: ~65% win at
roughly 1:3, which would be about **+1.6 R per trade**. The measured figure on
data nobody looked at first is between **−0.09 and +0.07**. Manual replay has a
known failure mode — a setup is judged valid after its outcome is visible — and
this is what that failure mode is worth.

## Layout

```
SPEC.md                        the design; the Pine is built against it
pine/riptide-undertow.pine     v1 — draws setups and scores them on screen
port/undertow.py               the Python transcription; three swing sources
port/swings.py                 bar pivot · k x ATR · k x a fixed span of time
prereg/                        written before each run — seven of them
studies/undertow_sweep.py      the parameter study
studies/undertow_ablation.py   the six-arm ablation
studies/undertow_exits.py      eight exits on identical fills
studies/undertow_backup.py     the OB/FVG backup, decomposed
studies/undertow_late_backup.py  the same backup, placed after the limit dies
studies/undertow_bias.py       five direction sources, head to head
studies/undertow_rate.py       how many alerts a day — the product decision
measurements/                  what they concluded

riptide/watchers/undertow.py   THE LIVE ADAPTER, in the bot tree, off by
                               default. A second copy of the machine, held to
                               this one by tests/test_watch_undertow.py
tests/test_undertow_port.py    57 assertions; the parity chain and the orderings
```

## v1 is on the chart

Paste `pine/riptide-undertow.pine` into TradingView. Six input groups, a status
panel top-right, and a debug mode that is off by default.

**What it draws:** the live candidate's three lines as they develop, with a
label saying which confirmations have landed and how many bars in; then, on a
fill, the entry triangle, the stop and target, and the risk / reward zones.
A setup that never fills leaves nothing behind.

**What the panel says:** bias and state, how long the pullback has run, the
counts, what the live candidate is waiting for, and — the row that matters —
*why the last candidate was rejected*. A count alone cannot tell "nothing
qualified" from "the detector is broken".

**What it does not do:** score outcomes, send alerts, or claim anything. There
is no win rate and no R total in it.

## The parity checks — three of them, and each guards a different drift

Pine cannot import and Pine cannot run here, so "the chart and the study are
the same thing" is a chain, not an assertion. All three run inside
`deploy/preflight.py`.

| check | what it holds |
|---|---|
| `deploy/undertow-ms-check.py` | the copied engine in the Pine == the engine in `riptide-indicator-v2.pine`, every condition and assignment, both directions |
| `deploy/ms-py-parity.py` | that v2 engine == `riptide_ms/port/ms_struct.py` |
| `tests/test_undertow_port.py` | `ms_struct.py` == the port's `structure()`, CHoCH / BOS / sweep on identical bars |

Chain those and the port's market structure is the chart's market structure.
Sections 5–7 have no second copy anywhere, so they are held by behaviour
instead — including the three orderings found the hard way on real charts: the
target printing before the fill, one bar spanning entry and stop, and no fill
on the arming bar.

A fourth, `deploy/undertow-port-check.py`, compares every Pine `input.*` to the
port's `P` — same name, same default, same dropdown strings. It is narrower
than a logic check and it caught a real drift on its first run (`rr` defaulted
to 2.0 in the port and 3.0 in the Pine), which is the silent kind: a study
reporting a number for settings the chart is not running.
