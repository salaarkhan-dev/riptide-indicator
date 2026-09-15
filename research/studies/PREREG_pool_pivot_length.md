# Prereg — does a LONGER pivot build better pools?

Written and committed **before** the run. Nothing below is adjusted after
seeing a number.

## Where this comes from

The "Big grab" in mickes' *Liquidity & inducements* is not a different
detector from its ordinary grab: it is the same function with the pivot
length raised from 3/3 to 10/10 and its own colour
(`audit/LIQUIDITY_BORROW_ASSESSMENT.md` §1). Its `Timeframe` input defaults
to `""`, the chart timeframe, so unless it was changed, a big grab that looked
useful on a 15m chart was computed **on 15m with a 10/10 pivot** — not on a
higher timeframe.

That makes "would a higher timeframe help?" the wrong first question. The
cheaper and more likely explanation for a big grab being informative is the
**pivot length**, which Riptide already has as `pivot_left` / `pivot_right`
and currently sets to **1 / 2**.

So: measure the pivot length before building anything that fetches another
timeframe.

## Arms — fixed now

`(pivot_left, pivot_right)` ∈

    (1, 2)    CONTROL — the production value in riptide.conf, frozen
    (3, 3)    mickes' ordinary grab
    (5, 5)
    (8, 8)
    (10, 10)  mickes' big grab
    (16, 16)  ~4h of structure on a 15m chart

Six arms. Everything else in `Cfg` is left at production values; only these two
fields move.

## Data — fixed now

* the 23 symbols in `research.data.SYMBOLS`, in that order, no substitutions
* `Min15`
* `RIPTIDE_LOOKBACK = 2000` bars
* candles fetched **once per symbol** and reused across all six arms, so the
  arms see identical price data and differ only in the engine config

## Unit of evidence — the BET, not the trade

A bet is `(symbol, sweep_time)`. Setups that share a sweep are one bet and
their R is averaged within it. Counting them separately is how this project
has manufactured t-statistics out of autocorrelation before
(`research/MS_ENTRY_MODELS.md`).

Confirmed setups only. `kind == "early"` rows are excluded from the primary
outcome.

## Primary outcome

Mean R per bet, with SE, per arm. Scored by `research.harness.simulate` at its
defaults — the same resolver every other study on this repo uses: the entry
bar resolves nothing, the stop is tested before the target, a gapped stop
fills at the open.

## Decision rule — stated before the run

Five comparisons against the control. At a nominal 2 SE that family hands out
roughly one false positive by construction, so:

> An arm **passes** only if it beats the control by **≥ 3.0 SE** on mean R per
> bet **and** keeps the sign of that difference on both the symbol split
> (odd/even index) and the window split (first/second half of the data).

## Power — and the escape hatch that was missing last time

An earlier study on this repo set a 3.0 SE bar that the sample could never
have reached, and it had to be retracted. So, stated now:

> After the run, report the achieved SE of the control-minus-arm difference.
> If 3.0 SE corresponds to an effect **larger than +0.50 R per bet**, the
> study is declared **UNDERPOWERED** and reports a bound — "an effect smaller
> than X R per bet could not have been seen here" — instead of a verdict.
> An underpowered null is not evidence of no effect and will not be written
> up as one.

## Secondary, descriptive, NOT part of the decision

* bets per arm, and setups per arm
* median risk as a % of entry price, per arm

The second is a guard, not a result. Stage A of the LIT work died at a 0.42%
median risk: below roughly half a percent the stop sits inside the noise and
gap losses dominate, which says nothing about the pool that produced it. Any
arm whose median risk falls under **0.50%** is flagged as degenerate and its
mean R is not interpreted, whichever way it points.

A longer pivot is expected to WIDEN stops, so the degenerate case is more
likely at the short end — including, possibly, at the control.

## What a pass would and would not license

A pass licenses **one** thing: adding a second, longer-pivot pool set to
`riptide-indicator-v2.pine` behind its own toggle, drawn in its own colour,
as context.

It does **not** license changing `pivot_left` / `pivot_right`. Those are
parity-locked: `deploy/check-parity.py` matches them to `riptide.conf` by
name, and moving them moves every alert the bot sends.

## Expected result

Negative. Seven inducement definitions, five entry models and the
cycle-position effect have all come back at or below their controls. The prior
here is that pivot length is another knob that reshapes the setup count
without moving R per bet. Recording that expectation now so that a negative
result cannot be presented later as though it were a surprise, and so a
positive one has to survive the bar above.
