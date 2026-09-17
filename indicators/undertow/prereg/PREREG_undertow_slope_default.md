# PRE-REGISTRATION — should Slope be the default bias?

Committed before the first number. Run by
`indicators/undertow/studies/undertow_slope.py`.

## The decision this is for

[`UNDERTOW_BIAS_SOURCE.md`](../measurements/UNDERTOW_BIAS_SOURCE.md) scored six
bias sources and promoted none. Slope came closest — **+0.198 R per trade on
the Min30 holdout**, the largest single number in the study — and failed only
the z bar (+0.228 against the baseline at z 1.72, needing 2.0). The request is
to run it as the default and compare.

## FIRST, AN OBJECTION TO THE QUESTION AS ASKED

**Slope as shipped carries the exact defect that chose the current default.**
`slopeLen` is a number of BARS and `slopeMin` is quoted in ATR per BAR. Both
halves of the rule are per-bar, so the same setting is a different rule on
every chart — and the bias study measured it:

| source | 15m flips/day | 30m flips/day | ratio |
|---|---|---|---|
| bar pivot 6/2 — the setting the complaint was about | 2.3 | 1.1 | **2.1×** |
| **Slope 50 / 0.05 — as shipped** | **1.2** | **0.5** | **2.4×** |
| price move 0.40 — the current default | 0.6 | 0.6 | **1.0×** |

`price move` is the default *only* because of that last column. Promoting
Slope-in-bars over it would give back the thing that was bought, and would do
it on the strength of one cell out of twenty-one.

So Slope gets a second arm that does not have the defect. **`slopeUnit =
"hours"`** restates the identical rule in time: the window is `slopeHours` of
trading and the threshold is in **day-ranges per hour** — the fit's rise per
hour over the last 24 hours' high-to-low, the same unit the `price move`
swings already use. Nothing per-bar survives.

**12.5 hours is 50 bars on 15m.** The window is the shipped setting converted,
not retuned, and that conversion is arithmetic, not a choice.

## THE ONE NUMBER THAT IS NOT ARITHMETIC, and how it is fixed

`slopeMinPerHr` is in a different unit from `slopeMin`, so 0.05 does not carry
over and there is no conversion that does not assume a price process. It is
therefore **calibrated, before any expectancy is read, by this rule**:

> Take the ladder **{0.002, 0.005, 0.01, 0.02, 0.03, 0.05, 0.08}**, fixed here.
> On the **calibration quadrant** (even symbols, newer half), Min15 only, pick
> the rung whose **flips per day** is closest in log ratio to Slope-in-bars'
> flips per day on the same quadrant. Ties to the smaller rung.

Flip rate is a descriptive statistic of the direction series. It is not an
outcome, it does not read a trade, and it is what makes the two Slope arms
*the same rule in two units* rather than two different rules. **The chosen
rung is printed and frozen before the holdout runs, and no other value of
`slopeMinPerHr` is scored.**

## The arms — three, and no more

| id | bias | |
|---|---|---|
| **A0** | `structure` on `price move` 0.40 / 0.12 | **THE BASELINE — what ships today** |
| **A1** | `Slope`, `bars`, 50 / 0.05 | exactly what the bias study measured |
| **A2** | `Slope`, `hours`, 12.5 / calibrated | the same rule, in time |

Retrace-only Ending on every arm, as before — the other three Ending rules read
minor structure and sweeps, which do not exist for a slope.

**`swingSrc` is unread in A1 and A2.** When `biasSrc` is not `structure` the
engine never calls the swing detector at all. Nobody should read a swing
setting into those rows.

## Population, held constant

* 23 MEXC perpetuals, 12,000 bars each, Min15 / Min30 / Min60, run separately
* `maxLive = 64`, `rr` 3.5, `locTol` 0, stop at the pullback extreme with
  tracking and a 0.25 ATR buffer, `feeFrac = 0.0007`
* candle, location, confirmations, levels and exit **unchanged in every arm**
* a trade unresolved when the data ends is discarded

## THE HOLDOUT, AND WHAT IS HONESTLY LEFT OF IT

The bias study spent even/older (train) and odd/newer (holdout). **Slope's
+0.198 was read on odd/newer, so that quadrant can no longer test Slope.** Two
quadrants were never scored:

| | symbols | bars | |
|---|---|---|---|
| **CALIBRATION** | even-indexed | newer half | the ladder rung is chosen here, on flip rate only |
| **HOLDOUT** | odd-indexed | **older half** | every expectancy number, scored **once** |

**This is a weaker holdout than the last one and the page will say so.** It
shares *symbols* with the previous holdout; what it does not share is the *time
period*, and for "does this replicate" the time separation is the one that
matters. It is what is left. A clean holdout would need data this repository
does not have.

## The metric

Unchanged from the bias study, and for the same reason: the direction decides
which setups exist, so arming is not invariant.

* **PRIMARY: mean R per trade**, net of fees, clustered by symbol.
* **SECONDARY: R per 1,000 bars.**
* Descriptive: flips per day, median hold, armed and fill counts.

## Pre-registered bars, on the HOLDOUT

1. **COVERAGE.** ≥ 200 closed trades per arm, else that arm is a bound.
2. **NOT CONFOUNDED.** `nCap` 0 in every arm.
3. **BEATS THE BASELINE.** Arm − A0 ≥ **+0.10 R per trade**, clustered
   |z| ≥ 2.0.
4. **BEATS ITS CONTROL.** ≥ 1 SE above the seeded random-entry control matched
   on symbol, quadrant, direction, risk, `rr` and holding window.
5. **POSITIVE.** Mean R per trade > 0 after fees.
6. **NOT ONE TIMEFRAME.** Positive on ≥ 2 of 3 holdout timeframes.
7. **CONSISTENT.** `max(flips/day) / min(flips/day)` across 15m and 30m
   ≤ **1.35**. A0 scores 1.0 and Slope-in-bars scored 2.4 in the bias study.
   This bar exists because consistency is the *only* reason the current default
   holds its place, so an arm that replaces it has to at least match it.

### THE PROMOTION RULE, fixed now

**Slope becomes the default only if an arm clears 3, 4, 5, 6 AND 7.** Clearing
7 alone changes nothing — A0 already has it. Clearing 3–6 without 7 is a reason
to keep measuring, not to ship, and the page will say that instead of shipping.

## My prediction, recorded before the run

* **A1 will not replicate +0.198 on Min30.** It was one cell of twenty-one at
  z 1.72, and in the same study EMA cross swung **0.54 R between two halves of
  the same universe** — that is the noise floor for a single cell here. I
  expect Min30 A1 between −0.15 and +0.10.
* **A2 ≈ A1 on expectancy**, within ±0.10 R. They are the same rule; if
  restating a rule in a different unit changed its expectancy materially, that
  would say the effect was the unit.
* **A2 passes bar 7, A1 fails it.** This is the one thing I expect to be clean.
* **Nothing clears bar 3 or bar 4**, and the default does not change. Six
  components have been ablated without an effect and I do not expect the
  seventh look at the sixth to produce one.
* **If I am wrong anywhere it is bar 7 on A2** — converting the window to hours
  fixes the window, and I am less sure the day-range threshold fixes the
  threshold as cleanly as it does for the swings.

## What cannot happen

* **No second rung** for `slopeMinPerHr` after the ladder rule has run.
* **No re-tuning** of `slopeHours`, `slopeLen` or `slopeMin`. 12.5 is the
  arithmetic conversion of 50 bars on 15m and that is the only reason it is
  there.
* **No fourth arm**, and no arm added after a number is seen.
* **No mixing** — Slope filtering structure, or structure filtering Slope, is a
  different study and the one that would need the most protection from itself.
* **No scoring on the calibration quadrant.** It sees flip rate and nothing
  else.
* **No re-use of odd/newer.** It is spent for Slope.
* **No change to the candle, location, confirmations, levels or exit.**
* **No production change unless the promotion rule above is met.**
  `tests/test_control_frozen.py` must still pass.
* **No exchange API key and no order placement.**
* **One study, one run.**

## If nothing clears the promotion rule

Then the answer to "measure Slope as the default" is **no**, the `+0.198` was a
maximum and not a finding, and the useful residue is the `hours` unit: Slope
becomes the second setting in this indicator that means one thing on every
chart, available behind a dropdown, promoted to nothing.
