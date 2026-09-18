# The 50/5 swing scale costs 60% of the trades and changes nothing else

Against [`PREREG_undertow_scale2.md`](../prereg/PREREG_undertow_scale2.md).
`SYMBOLS_FRESH9`, 45 / 42 / 33 symbols, scored once. All four pre-registered
impossibilities hold.

## The verdict

| tf | S1 50/5 | S0 6/2 | Δ | z | control | n | win% | bars |
|---|---|---|---|---|---|---|---|---|
| Min15 | −0.012 | +0.049 | −0.061 | −0.67 | −0.056 | 1462 | 23.3% | PP... |
| Min30 | +0.001 | −0.018 | +0.019 | +0.25 | −0.001 | 1322 | 23.2% | PP..P |
| Min60 | −0.114 | −0.108 | −0.006 | −0.07 | +0.010 | 1146 | 20.3% | PP... |

**NULL.** Every delta is inside ±0.10 and inside one standard error, in both
directions. Bars 3, 4 and 6 fail; the scale neither beats 6/2 nor loses to it.

**Under the prereg's asymmetric decision rule, 50/5 STAYS.** It ships because
it reads better on a chart, it costs nothing measurable, and nothing here has
grounds to overrule a preference that is free.

## WHAT IT ACTUALLY BUYS, AND THE PRICE IS NOT IN R

| tf | flips/day 6/2 | flips/day 50/5 | trades/day 6/2 | trades/day 50/5 |
|---|---|---|---|---|
| Min15 | 2.18 | **0.35** | 0.66 | **0.26** |
| Min30 | 1.10 | **0.17** | 0.33 | **0.13** |
| Min60 | 0.54 | **0.09** | 0.17 | **0.07** |

**The bias flips a sixth as often and the strategy takes 39% of the trades,
for no change in expectancy.** That is the trade the scale makes: a far
quieter chart, the same money. Whether quieter is worth 60% of the
opportunities is a judgement about how the chart is used, not a measurement —
but it should be made knowing that is the trade.

The prediction that S1 would trade "about 38% of S0's rate" came in at 39%.

## The three pools

The scale relocates rather than filters — only 17% of trades are shared:

| tf | shared | 6/2 only | 50/5 only |
|---|---|---|---|
| Min15 | −0.041 (665) | +0.069 (3036) | +0.012 (797) |
| Min30 | −0.001 (603) | −0.022 (2866) | +0.002 (719) |
| Min60 | −0.200 (487) | −0.089 (2383) | −0.051 (659) |

No pool is meaningfully better than any other. The trades 50/5 uniquely finds
are not a better class of trade; they are a different, smaller sample of the
same thing.

## The engine, held at one scale — third universe to say the same

`S0 − S2` runs SMC and riptide's engine at the same 6/2: **+0.060 / −0.038 /
+0.007 R**. [`UNDERTOW_V2.md`](UNDERTOW_V2.md) measured the same swap at
+0.002 / +0.065 / +0.006 on a different universe. The two engines score the
same because, as [`smc.py`](../port/smc.py) shows, they are the same detector.

## Against the prediction

| predicted | actual | |
|---|---|---|
| S1 fails bar 4 | failed 3 of 3 | right |
| S1 − S0 between −0.08 and +0.08 | −0.061 / +0.019 / −0.006 | right |
| S1 trades ~38% of S0's rate | 39% | right |
| win rates on the fee-inclusive line | 23.3 / 23.2 / 20.3 against 23.5 / 23.2 / 22.9 | right on two, below on Min60 |
| held loosely because it changes the bias's TIME SCALE | it changed activity 6× and R not at all | the loosening was unnecessary |

## THIS STUDY WAS VOIDED ONCE AND THEN VOIDED ITSELF WRONGLY

Both failures were in my checks, not the data, and the sequence is worth
keeping because the second one nearly cost a third universe.

**The first attempt** ([`PREREG_undertow_scale.md`](../prereg/PREREG_undertow_scale.md),
on `SYMBOLS_FRESH8`) registered *"the two engines' CHoCH counts must match"*.
They differ by 0.1%, all of it the series' **first structure break** — LuxAlgo
starts its bias at "neither", riptide's starts at "bearish". Genuinely void:
the rule said match, they did not match. FRESH8 spent.

**The second attempt registered the corrected condition** — *"identical bars
once the series' first structure break is excluded"* — and then **implemented
it wrongly**. The code did `len(choch) - 1`, dropping each list's first
element rather than excluding one specific bar. Those are not the same: if one
engine has an extra event at bar `b0`, the lists are `[b0,b1,b2…]` against
`[b1,b2…]`, and dropping each head leaves `[b1,b2…]` against `[b2…]` — still
off by one, for every symbol, forever.

So the study declared itself void while **the registered condition held
exactly: 0 differing bars on all three timeframes.** The check was corrected
and the study re-run; the arm numbers are bit-identical, because they are
deterministic and nothing about the arms changed.

**What made that safe to publish rather than a third attempt:** the prereg's
wording is fixed, public and unambiguous, and the corrected code implements it
literally. What would NOT have been safe is deciding after the fact that a
fired impossibility was "close enough". The distinction is the whole game, and
a reader who wants to check it can diff the two lines of code against the one
sentence in the prereg.

**A caveat the prereg required me to keep:** I had seen FRESH8's void numbers
before this ran. They are not quoted here and the design was unchanged, but
FRESH9's answer agreeing with them is worth less than it would be otherwise.

## What changes

**No default changes.** 50/5 stays, as the decision rule said it would on a
null. `retraceMax`, `endMinor` and every other setting are untouched.

**The open question this leaves is not about the scale.** It is that the same
50/5 configuration leaves the bias reading `ending` or `none`
[83.5% of the time on Min30](../SETTINGS.md), in stretches with a median of
112 bars, because `retraceMax` latches and only clears on a structural event
that a 50-bar pivot delivers rarely. That is a far larger effect than anything
on this page and it has never been measured.
