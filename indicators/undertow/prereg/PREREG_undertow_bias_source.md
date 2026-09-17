# PRE-REGISTRATION — where should the bias come from?

Committed before the first number. Run by
`indicators/undertow/studies/undertow_bias.py`.

## The decision this is for

The bias is the one layer of Undertow never varied. Five studies changed the
candle, the location, the exit and the fill; all five kept the same CHoCH
engine underneath. The complaint that prompted this is concrete and it has a
number behind it:

| bias source | 15m flips/day | 15m median hold | 30m flips/day | 30m hold |
|---|---|---|---|---|
| **bar 6/2 — the shipped setting** | **2.3** | 7.8 h | **1.1** | 16.5 h |
| bar 15/3 | 1.1 | 17 h | 0.5 | 34.5 h |
| bar 30/5 | 0.6 | 33 h | 0.3 | 68 h |
| range 0.40 | 0.6 | 26.8 h | 0.6 | 30.5 h |

Two things fall out and both are reasons to test this properly. The shipped
setting **flips the bias more than twice a day** on 15m. And the bar pivot is
**not timeframe-invariant** — the same `6/2` gives 2.3 flips on 15m and 1.1 on
30m, because six bars is ninety minutes on one chart and three hours on the
other.

## A CORRECTION THAT MADE THIS STUDY NECESSARY

An earlier note in this conversation dismissed EMA, ADX and Supertrend as bias
candidates on the strength of
[`CCP_CONTEXT_FILTERS.md`](../../ccp/measurements/CCP_CONTEXT_FILTERS.md).
**That was wrong and the dismissal is withdrawn.** That study measured them as
**entry filters at liquidity grabs** — a mean-reversion event, a different
population, a different job. Whether the same indicator makes a good
**direction source for a pullback-continuation strategy** is a different
question and this repository has never asked it.

Carrying a verdict across strategies is exactly the error the prereg
discipline exists to prevent, and it nearly cost this study.

## The prior, and my prediction, recorded before the run

I have been wrong about this family once already, so the prior is held loosely.

* **I expect all six arms within ±0.10 R per trade of each other and of zero.**
  Five components have now been ablated and none carried an effect; a sixth
  changing the answer would be the first.
* **I expect the trade COUNTS to differ enormously** — Supertrend and Range
  position flip far more often and should produce two to four times the
  setups; EMA and Slope far fewer. That is the axis these actually differ on.
* **I expect no arm to beat its control.** If one does, it is the first thing
  in Undertow to do so and it earns a forward run.
* **I expect the scale-invariant structure arm (S6) to match S1 on expectancy
  and beat it on consistency across timeframes.** Consistency is a real
  property and it is not an edge.
* **The one I genuinely cannot call is Slope.** It is the only source here that
  holds its direction through a flat patch instead of flipping on noise, which
  is the specific failure the complaint describes. If anything wins, I expect
  it to be that.

## Population and what is held constant

Identical to every previous Undertow study:

* 23 MEXC perpetuals, 12,000 bars each, Min15 / Min30 / Min60, run separately
* `maxLive = 64`, `rr` 3.5, `locTol` 0, stop at the pullback extreme with
  tracking and a 0.25 ATR buffer, `feeFrac = 0.0007`
* the candle, the location, the confirmations, the levels and the exit are
  **unchanged in every arm**. Only the direction varies.
* a trade unresolved when the data ends is discarded

## THE ENDING RULES HAVE TO BE MATCHED, and this is the one judgement

The structure engine has four Ending rules; three of them (`endMinor`,
`endSweep`, `endStale`) read minor structure and sweeps, which **do not exist**
for an EMA or a Supertrend. Only the retrace rule is source-independent.

So the comparison is run with **retrace-only Ending on every arm**, including
structure. Faking a minor CHoCH for a moving average would make the comparison
look fair while not being.

The shipped structure configuration is reported **alongside** as S0, so the
cost of stripping it back is visible — but it is not the baseline, because it
is not comparable.

## The metric, and why it is not the last study's

The backup-fill studies used **R per armed setup** because arming was invariant
across their arms. **It is not invariant here** — the direction decides which
setups exist at all — so that denominator would be measuring two different
things.

* **PRIMARY: mean R per trade**, net of fees, clustered by symbol. This asks
  the question the study is for: is a trade taken under this bias better?
* **SECONDARY: R per 1,000 bars.** Throughput. A source with half the
  expectancy and four times the trades is a different proposition and one
  number cannot hold both.
* Reported descriptively: flips per day, median hold, % of bars tradeable,
  armed count, fill count.

## The arms

| id | bias source | |
|---|---|---|
| **S0** | structure, **shipped** Ending rules | reference only, not a baseline |
| **S1** | structure, retrace-only Ending | **THE BASELINE** |
| **S2** | EMA cross 50 / 200 | |
| **S3** | Supertrend 10 / 3.0 | |
| **S4** | Slope 50 bars, 0.05 ATR/bar | |
| **S5** | Range position, 50 bars | |
| **S6** | structure on `range` swings 0.40 / 0.12 | the scale-invariant pivot |

Every parameter above is fixed now. **No arm gets a second setting**; "EMA
20/50 might do better" is a different prereg.

## THIS STUDY SELECTS, SO IT NEEDS A HOLDOUT

Unlike the two ablations, the point here is to pick a winner from six — that is
a maximum, and the expected maximum of six draws under the null is about
**1.3 SE** above zero. So the split is the parameter study's:

| | symbols | bars |
|---|---|---|
| **TRAIN** | the 12 even-indexed symbols | older half |
| **HOLDOUT** | the 11 odd-indexed symbols | newer half |

One arm is chosen on TRAIN per timeframe and scored **once** on the holdout.
The other two quadrants are not scored.

## Pre-registered bars, on the HOLDOUT

1. **COVERAGE.** ≥ 200 closed trades for the chosen arm, else a bound.
2. **NOT CONFOUNDED.** `nCap` 0 in every arm.
3. **BEATS THE BASELINE.** Chosen arm − S1 ≥ **+0.10 R per trade** with
   clustered |z| ≥ 2.0.
4. **BEATS ITS CONTROL.** ≥ 1 SE above a seeded random-entry control matched on
   symbol, direction, risk, `rr` and holding window. **This is the bar that has
   killed every idea in this project so far.**
5. **POSITIVE.** Mean R per trade > 0 after fees.
6. **NOT ONE TIMEFRAME.** Positive on ≥ 2 of 3 holdouts.

### Multiplicity

Six arms selected on train, one primary contrast per timeframe on the holdout
→ three primary tests. The train table carries **no evidence** and will be
labelled that way, exactly as the parameter study's was.

## What cannot happen

* **No second parameter for any source.** The seven settings above are fixed.
* **No new source** after any number is seen.
* **No mixing sources** (an EMA filter on top of structure is a different
  study, and it is the one that would need the most protection from itself).
* **No change to the candle, location, confirmations, levels or exit.**
* **No promotion on the train table.**
* **No production change.** The watch stays frozen on `structure` until and
  unless something here clears bar 4; `tests/test_control_frozen.py` must still
  pass.
* **No exchange API key and no order placement.**
* **One study.**

## If nothing clears bar 4

Then the bias source is the sixth component ablated without an effect, and the
honest reading is that the direction layer is not where the problem is either.
What remains true regardless is the consistency finding: a pivot measured in
bars means something different on every chart, and `range` or `Slope` fix that
whether or not they pay. Consistency is worth having on its own terms — it
makes every future measurement mean one thing — and it will be recommended on
that basis and no other.
