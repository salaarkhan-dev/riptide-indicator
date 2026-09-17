# PRE-REGISTRATION — is the exit the bug?

Committed before the first number. Run by
`indicators/undertow/studies/undertow_exits.py`.

## The decision this is for

Two measurements say Undertow has no edge
([`UNDERTOW_PARAMS.md`](../measurements/UNDERTOW_PARAMS.md),
[`UNDERTOW_PIN_VALUE.md`](../measurements/UNDERTOW_PIN_VALUE.md)). The person who
trades it says it works manually, at **1:2 at worst and usually 1:3 to 1:7**,
and that the winners are taken to **opposite-side liquidity** rather than to a
fixed multiple.

**Those two statements are not in conflict, and this study is the reason why.**
Every number measured so far exits at a fixed 2R or 3R and nothing else. A rule
that wins 30% of the time scores:

| exit | expectancy per trade |
|---|---|
| fixed 3R | 0.30 × 3 − 0.70 = **+0.20 R** |
| half the winners run to 6R | 0.15 × 6 + 0.15 × 3 − 0.70 = **+0.65 R** |

Same entries, same stops, same win rate, a **3× difference in expectancy**
decided entirely by where the trade is closed. If the manual version lets
winners run and the port does not, the port is measuring a different strategy
and its verdict does not transfer.

This is the most credible remaining explanation for the gap, it is cheap to
test, and it has not been tested.

## The prior, and my prediction, recorded before the run

I have argued against this strategy three times and been right twice and wrong
once, so the prior I actually hold is worth stating plainly rather than
flattering either side.

**My prediction: the exit matters, and not enough.** Specifically:

* I expect **median MFE below 2R** and **mean MFE between 2R and 4R** — a long
  right tail, which is what makes 1:7 outcomes both real and unrepresentative.
* I expect **every runner exit to beat fixed 3R** by 0.1 to 0.4 R per trade,
  because a right-tailed excursion distribution always rewards letting winners
  run when the stop is unchanged.
* I expect **the best runner exit still to land between −0.1 and +0.3 R**, i.e.
  better than what was measured, possibly positive, and short of the +1.0 R the
  manual account implies.
* I expect **E5 (liquidity) to beat the fixed exits and lose to E6 (trail)**,
  because a fixed structural target is still a cap and a trail is not.

If a runner exit clears **+0.5 R per trade on the holdout with z ≥ 2 against its
control**, I am substantially wrong about this strategy and it earns a forward
run. That is the outcome this study exists to be able to detect.

**What would make me wrong in the other direction:** if MFE has no right tail —
if the 90th percentile is under 3R — then the 1:7 trades in the manual record
are not in this data at all, and the disagreement is about *which setups get
taken*, not about where they are closed. That is a different investigation and I
will say so rather than reaching for another exit model.

## Population and what is held constant

**The entries are frozen and are not under test.** Every exit model is scored on
**the identical set of filled trades**, produced by the same configuration the
ablation used:

* Pine defaults, `bar 15/3` swings, `endMinor = on the flip`, `locTol` 0, stop
  at the pullback extreme with tracking on and a 0.25 ATR buffer
* `maxLive = 64` — the charting cap removed, as
  [`PREREG_undertow_pin_value_v2.md`](PREREG_undertow_pin_value_v2.md) requires
* 23 MEXC perpetuals, 12,000 bars per symbol, Min15 / Min30 / Min60
* `feeFrac = 0.0007`, slippage still not modelled and still optimistic
* a trade whose exit has not resolved when the data ends is **discarded**

**The stop is identical across every arm.** It is the R denominator, so a study
that varied it would not be comparing exits. Two arms move the stop *after*
entry (E4, E6) and that is the arm's definition, not a change to the risk.

**Horizon: 200 bars from the fill.** A trade that has neither stopped nor met
its exit rule by then is **marked to market at bar 200** — not discarded, which
would quietly delete the arms that hold longest and flatter exactly the models
under test.

## The arms — eight exits, fixed now

| id | exit | definition |
|---|---|---|
| **E0** | fixed 2R | the baseline the chart panel shows |
| **E1** | fixed 3R | the Pine default, and the sweep's choice |
| **E2** | fixed 5R | |
| **E3** | fixed 7R | the top of the manual range |
| **E4** | 1R then break-even, run to horizon | stop to entry once +1R trades, then no target |
| **E5** | **liquidity** | the opposing structural extreme at the moment of entry — for a long, the engine's running `msMax`; for a short, `msMin`. If it is not beyond the entry, the trade uses the horizon. This is the manual rule as described. |
| **E6** | ATR trail | once +1R trades, stop trails 2.0 × ATR(14) behind the running favourable extreme |
| **E7** | MFE oracle | the best price the trade ever reached. **NOT TRADEABLE** — it is the ceiling, reported so every other arm can be read as a fraction of what was available |

**No other arm, and no parameter sweep inside an arm.** The 2.0 in E6 and the
1R trigger in E4 and E6 are fixed now and do not get a second value. If a trail
wins, "a better-tuned trail" is a different prereg.

E7 is reported in every table and is excluded from every verdict.

## Unit of evidence and metric

**The bet = one filled trade.** Mean R per trade net of fees, SEs clustered by
symbol. Ghost trades excluded entirely.

Reported alongside, as description rather than test: the **MFE distribution** in
R — median, 75th, 90th, 95th percentile, and the share of trades reaching 2R,
3R, 5R and 7R. That distribution is a fact about the data and carries no
hypothesis; it is what says whether the manual account's tail exists at all.

## The split

The ablation established that this population is well powered, so this study
uses the **same train / holdout split as the parameter study** —
even-indexed symbols' older half to look, odd-indexed symbols' newer half to
report — because unlike the ablation, **this study does select**: eight arms and
the best one is a maximum.

Expected maximum of 8 draws under the null is about **1.4 SE**. Less than the
sweep's 48, and still enough to require a holdout.

## Pre-registered bars, on the HOLDOUT

1. **COVERAGE.** ≥ 300 closed trades. The ablation produced 700–2,400 per arm at
   `maxLive 64`, so this should be comfortable; below 300 the panel is a bound.
2. **BEATS THE FIXED EXIT.** The chosen runner arm must beat E1 (fixed 3R) by
   ≥ 0.15 R with clustered |z| ≥ 2.0 on the difference.
3. **POSITIVE.** Mean R > 0 after fees.
4. **BEATS ITS CONTROL.** ≥ 1 SE of the difference above a seeded random-entry
   control **scored under the same exit model** — an exit that improves any
   entry equally has told us about the market, not about Undertow. This bar has
   killed two ideas in this repository and is the one most likely to kill this.
5. **NOT ONE TIMEFRAME.** Positive on ≥ 2 of 3 holdouts.
6. **NOT ONE SYMBOL.** Dropping the largest contributor leaves it positive.

A result that clears 2 but not 4 means **the exit rule is real and the entry
still is not** — which would be a genuine finding and would point at the
entry, not at another exit.

## What cannot happen

* **No change to the entry, the stop or the population.** If an exit needs a
  different stop to work, that is a different study.
* **No new arm** after any number is seen, and no second value for the trail
  multiple or the break-even trigger.
* **E7 never appears in a verdict.** It is a ceiling, not a strategy.
* **No claim from the MFE distribution.** It is descriptive.
* **No production change**, nothing under `riptide/`,
  `tests/test_control_frozen.py` must still pass.
* **No exchange API key and no order placement.**
* **One study.**

## What this does NOT test, and why that matters

Three other differences between the port and the manual account are real and are
**not** in this study:

1. **The backup fill** at an order block or FVG when the limit is missed. `gone`
   and `back` are the two largest no-entry buckets and the spec has always said
   this belongs. It changes which trades exist, so it cannot share a population
   with an exit study.
2. **Lower-timeframe stop refinement**, which would shrink the R denominator and
   inflate every number here. It is a separate prereg and it has to be, because
   a tighter stop that gets hit more often is not free.
3. **Selection.** Roughly ten discretionary trades a week against twelve
   thousand mechanical ones. Nothing here can measure a human's choice of which
   setup to take.

If this study comes back negative, (1) is the next one to run and (3) is the one
that can never be settled from historical bars.
