# PRE-REGISTRATION — two timeframes, EMA 20/50 on each, trade only when aligned

Committed before the first number. Run by
`indicators/undertow/studies/undertow_mtf.py`.

## Where this came from

A Pine script, *MTF Market Structure Bias*: EMA 20 and EMA 50 on a slower
timeframe (30m) and on a faster one (15m), a table reading **FULL BULLISH /
FULL BEARISH / MIXED**, and the implied rule — take the direction only when
both timeframes agree.

## WHY THIS IS NOT ALREADY MEASURED, and I checked before saying so

Two earlier pages come close and neither covers it:

* **`UNDERTOW_BIAS_SOURCE.md` S2** was **EMA 50/200 on ONE timeframe** as the
  direction source. That prereg says, in as many words: *"No arm gets a second
  setting; 'EMA 20/50 might do better' is a different prereg."* **This is that
  prereg.**
* **`UNDERTOW_HTF.md`** ran the **structure engine** one timeframe up as an AND
  gate. Its closing section says an HTF direction "from something else
  entirely" is a different question that "would need its own prereg — and now
  it can have a clean population to run on". **This is that question.**

There is also a third thing here that no source in this project has had: **a
stand-aside state.** Every previous direction source is always long or short.
This one abstains on MIXED, which is a gate and a direction at the same time,
and the study has to separate the two or it measures a blur.

## The prior, stated plainly, and it is not good

EMA 50/200 on one timeframe swung **0.54 R per trade between two halves of the
same universe** in the bias study — the clearest "this is noise" result in the
project. 20/50 is faster and will flip more. Nine components have been ablated
without an effect.

**That is a prior, not a verdict.** The rule being tested is a two-timeframe
alignment with an abstain state, which is a different rule from a single-
timeframe cross, and dismissing it on the 50/200 result would repeat exactly
the error this project already made once and had to withdraw.

## ONE CORRECTION TO THE SOURCE SCRIPT, and it matters

`request.security(syminfo.tickerid, "30", ta.ema(close, 20))` returns the value
of the **forming** 30m bar on the live bar. The table therefore flips intrabar,
and the historical chart is cleaner than live trading would have been.

**The port does not reproduce that.** The slower EMA is read from aggregated
bars whose verdict is written onto a base bar only from the bar AFTER the one
that closed it — the same no-look-ahead rule `htf_dir` already follows.
Measuring the repainting version would measure the repaint.

If the rule is worth using on a chart, the script needs `[1]` on those
`request.security` calls. That is a separate matter from whether it pays.

## How the two timeframes are expressed

The script names fixed timeframes, 30m and 15m. Fixed strings cannot be run
across 15m / 30m / 1h: a 15m series cannot be built from 1h bars, and on a 30m
chart "15m structure" is below the base bar.

So the pairing is expressed as a **ratio**: structure on the BASE bars, bias on
bars aggregated `mtfMult = 2`. **On a 15m chart that is exactly the 15m / 30m
pairing the script was written with**, which is the chart it came from, and it
lets the same rule be run on 30m (30m/1h) and 1h (1h/2h).

`mtfMult = 2` is fixed here and is not an arm.

## THE POPULATION — a second untouched universe

`UNDERTOW_HTF.md` has now been read on `SYMBOLS_FRESH`, so those 45 are no
longer untouched: their baseline is known to be −0.022 / −0.046 / −0.098.

So this runs on **`SYMBOLS_FRESH2`** — ranks 46–90 under the identical frozen
rule, disjoint from both the original 23 and from `SYMBOLS_FRESH`, and **no
number from it has been looked at**. 594 symbols qualify; a fresh universe per
question costs ten minutes and is cheaper than arguing about contamination.

`SYMBOLS_FRESH` is reported as a **secondary panel**, where the M0 baseline
must reproduce `UNDERTOW_HTF.md`'s H0 exactly — a built-in check that the two
studies are running the same machine.

* 45 symbols, 12,000 bars, Min15 / Min30 / Min60, run separately
* any symbol with fewer than 11,000 bars is dropped before anything is scored
* `maxLive = 64`, `rr` 3.5, `locTol` 0, pullback stop with tracking, 0.25 ATR
  buffer, `feeFrac = 0.0007`, retrace-only Ending
* candle, location, confirmations, levels and exit **unchanged in every arm**

**No train/holdout split, because nothing is selected.** One arm is fixed
below; the rest are descriptive and may not be promoted.

## The arms

| id | direction | |
|---|---|---|
| **M0** | `structure` on `price move` swings | **THE BASELINE — what ships** |
| **M1** | **MTF EMA 20/50, base + ×2, abstain on MIXED** | **THE PRIMARY** |
| M2 | EMA 20/50 on the base timeframe only, never abstains | descriptive — isolates the direction from the gate |
| M3 | MTF EMA 50/200, base + ×2 | descriptive — the link to S2 |
| **G** | random gate on M2, matched to M1's rejection rate | **THE CONTROL for the alignment** |

**M1 = M2 + the alignment gate.** So `M1 − M2` is what the second timeframe
buys, and `G` is what discarding the same number of M2's trades at random buys.
`M1 − G` is the question the study exists for.

## The metric

* **PRIMARY: mean R per trade**, net of fees, clustered by symbol.
* **SECONDARY: R per 1,000 bars.** Reported, and **NOT a pass/fail bar this
  time.** In `UNDERTOW_HTF.md` I made throughput a bar and it passed 3 of 3 for
  a worthless reason: the baseline was negative, so doing less of a losing
  thing raises R per bar mechanically and the bar rewarded any gate at all,
  including the random one. It is reported here and it decides nothing.
* Reported: % of bars MIXED, setups refused while mixed, armed and fill counts.

## Pre-registered bars, on M1, on SYMBOLS_FRESH2

1. **COVERAGE.** ≥ 200 closed trades, else a bound.
2. **NOT CONFOUNDED.** `nCap` 0 in every arm.
3. **BEATS THE BASELINE.** M1 − M0 ≥ **+0.10 R per trade**, clustered
   |z| ≥ 2.0.
4. **BEATS THE RANDOM GATE.** M1 − G ≥ 1 SE. Does the *second timeframe*
   carry information, or does refusing 20% of the trades?
5. **POSITIVE.** Mean R per trade > 0 after fees.
6. **NOT ONE TIMEFRAME.** Positive on ≥ 2 of 3.

**PROMOTION RULE, fixed now: M1 becomes a selectable bias source on the chart
only if it clears 3, 4, 5 and 6.** It becomes the DEFAULT only if it also
reproduces on the `SYMBOLS_FRESH` secondary panel. Clearing 3 and 5 while
failing 4 means "trading less helps", which is a fact about position count and
not about the second timeframe, and it will be written that way.

## My prediction, recorded before the run

* **I expect M1 to fail bar 3.** Nine for nine so far.
* **I expect M1 − M2 to be small and positive**, +0.00 to +0.05 R, and **to
  fail bar 4** — an abstain state removes trades in choppy stretches, which
  looks like skill and is mostly the random gate's effect.
* **I expect M2 to have more trades than M0 and a worse mean.** A 20/50 cross
  is a looser gate than the structure engine's Ending rules.
* **I expect M3 ≈ M1 within 0.05**, because the 50/200 pair flips less and the
  alignment does most of the work either way.
* **On the smoke test I already ran** (ETH 15m, one symbol, NOT in any of these
  universes and NOT scored here): mixed on 19.2% of bars, and `mtfMult = 1`
  reproduced single-timeframe EMA exactly, which is the arithmetic check.
* **What would surprise me:** M1 clearing bar 4 on two timeframes. The abstain
  state is the only genuinely new mechanism any source here has had, and
  "stand aside when timeframes disagree" is the one piece of trading folklore
  in this whole sequence that has a plausible mechanism — chop is where
  pullback-continuation dies, and disagreement is a chop detector.

## What cannot happen

* **No second value of `mtfFast`, `mtfSlow` or `mtfMult`.** 20 / 50 / 2, fixed.
* **No promotion of M2 or M3**, whatever they print.
* **No selection of a timeframe.**
* **No falling back to `SYMBOLS_FRESH` or the 23 for the primary.** FRESH is
  the secondary panel and cannot rescue a failed primary.
* **No change to the candle, location, confirmations, levels or exit.**
* **No production change unless the promotion rule is met**; `biasSrc` stays
  `structure` and `tests/test_control_frozen.py` must still pass.
* **No exchange API key and no order placement.**
* **One study, one run.**

## If M1 fails

Then the tenth component is measured without an effect, on a third population
that nothing here has seen, with the correct control for a gate. The rule stays
in the port behind a dropdown value, off, and the page says what it scored.
