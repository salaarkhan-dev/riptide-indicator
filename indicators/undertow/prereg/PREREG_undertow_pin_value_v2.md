# PRE-REGISTRATION v2 — the same question, with the cap taken out

Committed before the first number of run 2. Run by
`indicators/undertow/studies/undertow_ablation.py --uncapped`.

Read [`PREREG_undertow_pin_value.md`](PREREG_undertow_pin_value.md) first: the
question, the six arms, the population, the metric, the control and the
prohibitions are all inherited unchanged. **Only what is listed below differs.**

## Why there is a v2

Run 1 is VOID by its own bar 2. `maxLive = 4` turned away seven to nine setups
for every one it traded on the looser arms, so `A0 − A3` was measuring the cap
as much as the gate. The prereg named that confound in advance, set the
threshold, and required a new pre-registration rather than a rerun. This is it.
Run 1's numbers are published in
[`UNDERTOW_PIN_VALUE.md`](../measurements/UNDERTOW_PIN_VALUE.md) and are not
withdrawn.

**The void was mechanical and not convenient.** Every arm in run 1 was negative
or within noise of zero, so there is no unfavourable result being re-rolled. A
reader should check that claim against the published table rather than take it.

## The one change

`maxLive = 64` on every arm, in place of 4.

Verified before writing this: on the loosest possible combination (no wick, no
colour, no Ending rules) 64 brings `nCap` to **exactly 0** on a full symbol-half,
and 1000 gives the identical trade count. So 64 is not a tuned number — it is
"enough", and anything larger changes nothing.

**`maxLive` is a charting artifact, not a strategy rule.** `SPEC.md` is explicit
that the cap exists for TradingView's 500-drawing budget and to keep the chart
readable. The port draws nothing, so in a measurement the cap should not exist
at all; carrying it over was the error in run 1. The port's *default* stays 4 so
that `deploy/undertow-port-check.py` keeps holding the port to the Pine's
inputs — the study overrides it explicitly, which is visible in the code.

**A consequence to state plainly:** uncapped, the arms run many overlapping
positions at once. **Mean R per setup remains well defined and is the metric.
Total R is not a portfolio return and will not be quoted as one.** Position
sizing and concurrency are a separate problem and this study does not address
them.

## Bar 2, restated

> **NOT CONFOUNDED.** `nCap` must be **0** for every arm on every panel.

Not "below the fill count" — zero. If it is not zero the cap is still choosing
setups and the run is void again, and the fix is a larger `maxLive` in a v3, not
a judgement call here.

## Everything else carries over unchanged

The six arms, the frozen configuration, the population, the primary contrast
`A0 − A3`, the ±0.15 R and |z| ≥ 2.0 thresholds, the UNDERPOWERED and
INCONCLUSIVE labels, the control definition, the multiplicity statement, and
every item under *What cannot happen* — including no new arm, no re-running with
a different frozen configuration, no promotion, no production change, and no
order placement.

## The prediction, re-recorded

Run 1's tables are now visible, so an honest prediction has to say what it takes
from them. What I have seen is: every arm negative or near zero, A3 slightly
*above* A0 on two of three timeframes, and A5 above A0 on two of three.

**Prediction: `A0 − A3` lands between −0.10 and +0.05 R on all three
timeframes, which is bar 4 — the candle is dead.** Run 1 already pointed there
and removing the cap should sharpen it rather than reverse it, because the cap
was suppressing A3 more than A0 and A3 was still ahead.

**Second prediction, and this is the one I am least sure of: A5 stays at or
above A0.** If it does, the ghost column and the ablation genuinely disagree
about the bias gate and neither can be quoted without the other. If A5 drops
below A0 once uncapped, the ghost column wins and run 1's A5 was a cap artifact.
Either way the answer goes in the measurement file, because an unresolved
contradiction between two of this project's own measurements is worth more than
another parameter.
