# PRE-REGISTRATION — is there a setting of Undertow that works, and does the swing unit matter?

Committed before the first number. Run by
`indicators/undertow/studies/undertow_sweep.py`.

## The decision this is for

Undertow has been judged entirely by its own status panel on single charts, and
those charts disagree with each other:

| chart | won / lost | mean R | net R |
|---|---|---|---|
| BTCUSDT.P 30m | 14 / 19 | +0.27 | +9 |
| XAUUSD 30m (Vantage) | 16 / 17 | +0.45 | +15 |
| XAUUSDT.P 30m (MEXC) | 5 / 22 | −0.44 | −12 |
| ETHUSDT.P 30m | 38 / 45 | +0.37 | +31 |

Rows 2 and 3 are **the same metal on two venues** and they disagree by 0.89 R
per trade. Pooling all four gives **+0.22 R ± 0.11** over 176 trades — nominally
positive, but every one of those four panels was produced on settings arrived at
by looking at the panel, which is the exact procedure that scored +0.089 in
sample and **−0.082** out of sample in
[`CCP_FILTER_OVERFIT.md`](../../ccp/measurements/CCP_FILTER_OVERFIT.md).

So this study is not "find the best settings". Searching a grid and reporting
the winner IS the overfit. This study picks a configuration on data that is then
never scored, and reports one number from data that was never searched.

**A second question rides along, and it is the one with a mechanism behind it.**
`msLen` is a pivot of *n bars*, which is a different span of time on every
chart, so the same setting is a different rule on 15m and on 1h. A swing
measured in *price over a fixed span of time* is not. That property is already
proved in `indicators/undertow/tests/test_undertow_port.py` — across a 4:1 bar
aggregation, swings per unit time survive at ×0.89 for a fixed-time range
against ×0.30 for a bar pivot. **Being scale-invariant is not the same as being
profitable**, and this study is where that distinction gets tested.

## The prior, and my prediction, recorded before the run

Two ideas in this repository have measured positive offline and then lost to a
seeded random-entry control: the trendline confluence tag (+0.206 R over 3773
signals, dead on the holdout, line removed) and the exhaustion count (ships off
by default). Undertow is a third idea of the same shape — a chart pattern plus a
trend filter — so the base rate here is poor and I am not going to pretend
otherwise.

**My prediction: nothing clears bar 4 (the control).** Specifically:

* I expect the grid's in-sample winner to score roughly **+0.3 to +0.5 R** per
  trade, because with 48 configurations the best one is about 2.4 SE above the
  mean by construction.
* I expect that to fall to **between −0.1 and +0.15 R** on the holdout.
* I expect the random control to be **close to zero but not zero**, and I expect
  the gap between Undertow and its control to be smaller than the gap between
  Undertow and break-even — which is the failure mode that killed the trendline.
* On the swing unit I expect `range` to produce **more consistent counts across
  the three timeframes** and **no better expectancy**. Consistency is a real
  result and is worth having; it is not an edge.
* On the HTF gate I expect a **large cut in trade count for a small and
  unstable change in mean R**, i.e. underpowered rather than useful.

If the chosen configuration clears all six bars I am wrong, and it earns a
forward-tracking run — not a deployment.

## Population, and what is held constant

* **23 MEXC perpetuals**, the list in `research/data.SYMBOLS`, unchanged.
* **Min15, Min30, Min60**, each run separately and never pooled across
  timeframes for a significance claim.
* **12,000 bars per symbol per timeframe**, fetched by paging the kline
  endpoint backwards. That is ~125 days on 15m, ~250 on 30m, ~500 on 1h.
* Entry, stop, target and the fill rules are **exactly the port's**, which is
  exactly the Pine's — including the three orderings that a chart found the
  hard way: the target printing before the fill drops the setup, one bar
  spanning entry and stop counts as the loss, and no fill on the arming bar.
* **Costs are on.** `feeFrac = 0.0007` of notional, a maker-in / taker-out round
  trip on a major perp, converted to R per trade against that trade's own risk.
  Slippage is **not** modelled and is additional; every result here is therefore
  still optimistic.
* A trade still open when the data ends is **discarded, not counted** — the same
  rule `research/data.py` applies, because scoring an unfinished trade at
  whatever price the fetch stopped on is noise dressed as an outcome.

## The split, decided now

Two dimensions at once, so the holdout shares neither symbols nor calendar with
the search:

| | symbols | bars |
|---|---|---|
| **TRAIN** | the 12 even-indexed symbols | the older half |
| **HOLDOUT** | the 11 odd-indexed symbols | the newer half |

The two quadrants that are neither (even/newer, odd/older) are **not scored and
not looked at**. They exist to keep the split clean, not as a third chance.

## The grid — 48 configurations, fixed now

Exactly these. Everything not listed stays at the Pine default.

| factor | values |
|---|---|
| swing source | `bar 15/3` · `bar 30/5` · `range 0.25/0.08` · `range 0.40/0.12` |
| `endMinor` | `off` · `on the flip` · `while opposed` |
| `htfMult` | `0` · `4` |
| `rr` | `2.0` · `3.0` |

4 × 3 × 2 × 2 = **48**, run on each of three timeframes independently.

**Frozen, and not swept:** `msBosNeedsIdm` true, `endSweep` true, `endStale`
true at 30 bars, `retraceMax` 70, `adxMin` 0 (off — ADX failed as a filter in
this project and its regime use is a separate prereg, not a free parameter
here), `wickEdge` 0.05, both families on, both comparison tests `close beyond`,
`confirmBars` 20, `fillBars` 20, `maxLive` 4, `locTol` 0, stop at the pullback
extreme, stop tracking on, `stopBuf` 0.25 ATR, `swingHours` 24.

### Family-wise inflation, stated before the run

48 configurations per timeframe. Under the null, the **expected maximum** of 48
independent draws is about **2.4 SE** above zero, and the chance that at least
one clears z ≥ 2 is effectively **1**. The in-sample winner is therefore
*guaranteed* to look good and its in-sample number carries **no evidence
whatsoever**. It will be reported only as the thing that selected the
configuration. Every claim in this study rests on the holdout.

## Unit of evidence and metric

**The bet = one filled trade.** Ghost trades — setups the bias gate cancelled,
walked forward anyway — are scored in a **separate column** and are never mixed
into the primary number.

Primary metric: **mean R per trade, net of fees**, with standard errors
**clustered by symbol**, because one symbol's trades are not independent of each
other.

## Pre-registered bars — all six, on the HOLDOUT

1. **COVERAGE.** ≥ 150 closed trades on the holdout at that timeframe. Below
   that the panel is declared UNDERPOWERED and reported as a bound, not a
   verdict.
2. **POSITIVE.** Mean R > 0 after fees.
3. **SIGNIFICANCE.** Clustered z ≥ 2.0.
4. **BEATS ITS CONTROL.** Mean R must exceed the seeded random-entry control by
   at least 1 SE of the *difference*. The control is defined below and is the
   bar this is most likely to fail.
5. **NOT ONE TIMEFRAME.** Mean R > 0 on the holdout of at least 2 of the 3
   timeframes, each using its own separately chosen configuration.
6. **NOT ONE SYMBOL.** Dropping the single largest-contributing symbol leaves
   the holdout mean R positive.

### The control, defined exactly

For every real trade the control draws **one** substitute, seeded so the run is
reproducible:

* same symbol, same timeframe, same split quadrant
* a **uniformly random entry bar** from that symbol's eligible bars
* the **same direction** as the real trade — so the control inherits the
  strategy's directional bias and the comparison isolates the *timing*, not the
  side
* the **same risk in price** and the **same `rr`**
* the **same maximum holding window**, and the same stop-before-target
  resolution when one bar spans both
* the same fee

Equal counts, so the two SEs are comparable. **If Undertow does not beat this,
what has been measured is the market, not the pattern.**

## What cannot happen

* **The holdout is scored once.** One configuration per timeframe, chosen on
  TRAIN, carried across, reported. There is no second look and no
  "well, the runner-up did better".
* **No widening the grid** after seeing it. A factor that fails does not get a
  differently-tuned turn in this study.
* **No new factor introduced mid-run** — in particular `retraceMax`, `adxMin`,
  `locTol`, `wickEdge` and the two comparison tests are frozen above and stay
  frozen even if the funnel suggests otherwise.
* **No pooling the three timeframes** into one significance claim.
* **No production change.** Nothing under `riptide/`;
  `tests/test_control_frozen.py` must still pass.
* **No changes to `indicators/riptide/pine/riptide-indicator.pine`.**
* **No exchange API key and no order placement.** This is a measurement and the
  repository has no trading path, by design.
* **One study.** There is no v2 of this prereg. A follow-up question needs its
  own file, written before its own run.

## If nothing passes

Then Undertow is what the evidence says it is: a detector that draws a coherent
story on a chart and does not beat a random entry of the same shape. It stays a
research bench — no alert, no watcher module, no `riptide/watchers/undertow.py`
— and `INDICATOR.md` records the negative result beside the other two.

That is a real outcome and it is cheaper than finding out later. The three
charts that started this were four samples of about thirty trades each,
disagreeing with each other by 0.9 R on the same asset; the whole reason this
file exists is that thirty trades cannot tell you anything and a grid search
over them will happily tell you something anyway.
