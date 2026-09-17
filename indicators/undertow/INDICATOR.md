# Riptide Undertow — market-structure bias + a single-candle pin

**Status: MEASURED, and it did not clear its own bar. Research bench only —
no alerts, and no watcher module.**

[`measurements/UNDERTOW_PARAMS.md`](measurements/UNDERTOW_PARAMS.md) is the
result, against a pre-registration committed before the first number. On 334
held-out trades across 15m, 30m and 1h it scores **−0.093, +0.071 and −0.063**
R per trade, and it loses to a seeded random entry of the same shape on two of
the three. [`SPEC.md`](SPEC.md) is the design.

## In one paragraph

Find the trend from major/minor market structure and refuse to trade a trend
that is ending. Inside it, wait for the counter-trend-coloured pin at the top
of a pullback — green in a downtrend, red in an uptrend — and take its high,
low and open as three levels. When price has closed beyond **both** the high
and the low, in either order, place a limit at the open. Stop above the
pullback, target 3R.

## What is claimed, and what is not

**Not an edge.** See the table above and the measurement file behind it.

**Three things ARE established**, and they are worth more than the verdict:

1. **The bias gate earns its place.** The ghost column walks every setup the
   gate cancelled forward anyway. Those setups are worth −0.61, −0.40 and
   −0.49 R each on the three timeframes — far worse than the population — so
   the gate saved 5.5, 19.8 and 21.3 R. Letting a triggered setup survive a
   bias flip would have lost money everywhere. I argued before the run that the
   gate was probably harmful; it is not.
2. **Selecting on a chart is worth about −0.31 R per trade.** Best-of-48 on
   train, then holdout: −0.377, −0.277, −0.286. Three timeframes, same answer.
3. **A pivot measured in bars really is a different rule on every timeframe,
   and `swingSrc="range"` fixes it** — a swing as k × the last 24 hours' range
   survives a 4:1 aggregation at ×0.89 against ×0.30 for the bar pivot. It buys
   consistency, not expectancy.

**What the study cannot say.** With 45–153 trades per panel the minimum
detectable effect is about ±0.5 R. It refutes the +0.27 to +0.45 R the single
charts showed. It does not exclude a small edge.

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
prereg/                        written before each run
studies/undertow_sweep.py      the parameter study
measurements/                  what it concluded
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
