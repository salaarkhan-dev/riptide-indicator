# PRE-REGISTRATION — does the candle carry anything, or is it just the location?

Committed before the first number. Run by
`indicators/undertow/studies/undertow_ablation.py`.

## The decision this is for

[`UNDERTOW_PARAMS.md`](../measurements/UNDERTOW_PARAMS.md) found that Undertow
does not beat a random entry of the same shape, and could not say **which part**
is dead. That matters, because the strategy is three separate claims stacked:

1. a **bias** — trade with the structure, refuse a trend that is Ending
2. a **location** — only at the extreme of the pullback
3. a **candle** — and only if that bar is a hammer / hanging man / inverted
   hammer / shooting star of the counter-trend colour

The parameter study already settled (1): the bias gate's ghost column shows the
setups it cancels are worth −0.40 to −0.61 R each, so that layer sorts good from
bad. It said nothing about (2) or (3).

**(3) is the layer with the weakest prior anywhere in this repository.**
`CCP_PATTERN_EXPLORE.md` scored the same four single-candle patterns at
liquidity grabs and found no edge — and specifically that *the pin added nothing
over the location alone*. Undertow is the same four patterns at a different
location. If the candle is again adding nothing, then most of the design, most
of the inputs and all of the taxonomy argument is decoration on a rule that
reads "buy the pullback extreme in an uptrend".

That is worth knowing whether the answer is yes or no. It is the cheapest
remaining question and it has never been asked.

## This is an ABLATION, not a search, and that changes the statistics

The parameter study had 48 configurations and its danger was selection: the best
of 48 is 2.4 SE above zero by construction. **This study selects nothing.** Six
arms are named below, all six are run, all six are reported, and the primary
contrast is fixed in advance. There is no maximum being taken, so there is no
maximum to shrink.

Because of that, the primary panel is the **whole population** — all 23 symbols,
all 12,000 bars — rather than a holdout. A holdout protects against selection
and there is none here; splitting would only halve the power of a study that is
already power-limited. The two quadrants the parameter study never scored
(even-indexed symbols' newer half, odd-indexed symbols' older half) are reported
as a **second panel**, so a reader can see whether the contrast is stable on
bars that have never been used for anything.

## The prior, and my prediction, recorded before the run

**My prediction: A0 and A3 will be within 0.1 R of each other, and A3 will have
several times as many trades.** In other words, the candle taxonomy adds
nothing, and the honest version of this strategy is the location alone.

I also predict:

* **A5 (no Ending rules) is clearly worse than A0.** This one I expect to be
  right because the ghost column already measured it from the other direction,
  and predicting it is a check that the two agree. If A5 is *not* worse, one of
  the two measurements is wrong and that is more interesting than the ablation.
* **A4 (no location) is worse than A0** and has far more trades. The location
  is the only gate with an obvious mechanism — it is where the stop can be
  placed tightly — so removing it should hurt.
* **A2 (no colour) ≈ A0.** The colour rule is the one I understand least: the
  bias already decides direction, so the candle's own colour is being asked to
  add information on top of a trend filter that has already fired.
* **No arm beats its own random control.** Nothing in the parameter study
  suggests any of this has an edge; this study is about *attribution*, not about
  finding one. If an arm does beat its control, that is a new hypothesis for a
  new prereg, not a result from this one.

## Population and what is held constant

Identical to `PREREG_undertow_params.md`, so the two are directly comparable:

* 23 MEXC perpetuals, `research/data.SYMBOLS`
* Min15, Min30, Min60, run separately, never pooled for a significance claim
* 12,000 bars per symbol per timeframe, the same cached fetch
* `feeFrac = 0.0007`, slippage not modelled and therefore still optimistic
* trades open when the data ends are discarded, not counted

**One configuration, frozen now, for every arm.** The Pine defaults: `bar 15/3`
swings, `msBosNeedsIdm` on, `endMinor = on the flip`, `endSweep` on, `endStale`
on at 30, `retraceMax` 70, `adxMin` 0, `wickEdge` 0.05, both families on, both
comparison tests `close beyond`, `confirmBars` 20, `fillBars` 20, `maxLive` 4,
`locTol` 0, stop at the pullback extreme, tracking on, `stopBuf` 0.25 ATR,
`rr` 3.0, `htfMult` 0.

**`maxLive` is the one number I am flagging as a confound in advance.** Removing
a gate admits far more candidates, and at a cap of 4 the extra ones get turned
away rather than traded — so a looser arm is throttled in a way the baseline is
not. The study therefore reports `nCap` for every arm, and **any arm whose
`nCap` exceeds its filled count is reported as CONFOUNDED** and its comparison
against A0 is void. This is stated now so it cannot be discovered later and
explained away.

## The six arms

Everything above stays fixed. Each arm changes exactly what its row says.

| id | arm | change |
|---|---|---|
| **A0** | **FULL** — the strategy as specified | none; the baseline |
| **A1** | no wick test | `useFamily = False` |
| **A2** | no colour test | `useColour = False` |
| **A3** | **location only** | `useFamily = False`, `useColour = False` |
| **A4** | no location test | `locTol = 50` |
| **A5** | no Ending rules | `endMinor = off`, `endSweep = False`, `endStale = False`, `retraceMax = 0` |

When the family test is off, the machine still needs to know which of the pin's
two extremes is *Working*; it falls back to whichever wick is longer, ties going
to the hammer reading. That is a mechanical fallback, not a finding, and it is
written into the port beside the code.

**No other arm.** No combinations beyond A3, which is the one the question is
about. No `wickEdge` sweep — "the taxonomy tuned differently" is a different
question and does not get a turn here.

## Unit of evidence and metric

**The bet = one filled trade.** Ghost trades are reported separately and never
mixed in.

Primary metric: **mean R per trade, net of fees**, SEs **clustered by symbol**.

**PRIMARY CONTRAST: A0 − A3**, per timeframe. Everything else is secondary and
will be labelled as such.

## Pre-registered bars

For the primary contrast, on each timeframe:

1. **COVERAGE.** Both arms ≥ 150 closed trades, else that panel is a bound.
2. **NOT CONFOUNDED.** Neither arm's `nCap` exceeds its filled count.
3. **THE CANDLE EARNS ITS PLACE** if and only if `A0 − A3 ≥ +0.15 R` with
   clustered |z| ≥ 2.0 on the difference, on at least 2 of the 3 timeframes.
4. **THE CANDLE IS DEAD** if `|A0 − A3| < 0.15 R` on at least 2 of 3, or if A3
   is the higher of the two anywhere it is significant.
5. **ANY ARM CLAIMING AN EDGE** must also beat its own seeded random-entry
   control, defined exactly as in `PREREG_undertow_params.md` — same symbol,
   quadrant, direction, risk, `rr` and holding window, one draw per real trade.

Bars 3 and 4 do not exhaust the space: a difference between 0.15 R and
significance is **INCONCLUSIVE** and will be reported with that word.

### Multiplicity, stated before the run

Six arms × three timeframes = 18 numbers, but **one** pre-declared primary
contrast per timeframe, so three primary tests. At z ≥ 2 each the chance of at
least one false positive is about 14%. The other fifteen numbers are
descriptive and no significance claim will be made from them.

### Power

The parameter study gave SE ≈ 0.17 R at ~140 trades. A3 should produce several
times as many, so SE on the difference should land near 0.15 R. **The 0.15 R
threshold in bar 3 is therefore roughly a 1 SE effect and this study can only
just see it.** If either arm's SE exceeds 0.25 R that panel is declared
UNDERPOWERED and reported as a bound.

## What cannot happen

* **No new arm** after seeing any number.
* **No re-running with a different frozen configuration.** The baseline is the
  Pine's defaults and stays there even if another setting would flatter an arm.
* **No `maxLive` increase mid-study.** If arms are confounded by the cap, that
  is the reported outcome and the fix is a new prereg, not a rerun.
* **No promotion.** Nothing here can make Undertow shippable; bar 5 exists to
  stop an arm that happens to look good from being read as an edge.
* **No production change.** Nothing under `riptide/`;
  `tests/test_control_frozen.py` must still pass.
* **No exchange API key, no order placement.**
* **One study.** A follow-up needs its own file, written before its own run.

## If the candle is dead

Then that is the most useful thing this project has learned about Undertow, and
it is not a failure. It would mean the strategy is one sentence — *take the
pullback extreme while the structure bias is running* — and every input in
group 2, the whole 16-variant taxonomy, the wick-edge doji margin and most of
`SPEC.md` section 2 are describing a filter that does not filter.

A one-sentence rule is easier to test, easier to trust, and has one parameter
instead of four. The next study would be about the location and the fill, which
is where both remaining no-entry buckets already point.
