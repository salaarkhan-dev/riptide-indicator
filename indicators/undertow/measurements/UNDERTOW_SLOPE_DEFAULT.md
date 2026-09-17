# Slope as the default: the shipped version died, and the fixed version is the
# strongest thing this project has produced and still does not ship

Against [`PREREG_undertow_slope_default.md`](../prereg/PREREG_undertow_slope_default.md).
23 symbols, 12,000 bars each, 15m / 30m / 1h. Everything but the direction held
constant, retrace-only Ending on every arm, 7bp fees. Calibrated on the even
symbols' newer half by flip rate only; scored **once** on the odd symbols'
older half.

## The verdict

| tf | arm | holdout | A0 baseline | Δ | z | control | n | bars 1-5,7 |
|---|---|---|---|---|---|---|---|---|
| Min15 | A1 Slope, bars | +0.095 | −0.018 | +0.114 | +0.60 | −0.016 | 887 | PP..P. |
| Min15 | **A2 Slope, hours** | **+0.147** | −0.018 | +0.166 | +0.88 | −0.049 | 904 | PP.PPP |
| Min30 | A1 Slope, bars | −0.228 | −0.185 | −0.043 | −0.28 | −0.061 | 812 | PP.... |
| Min30 | A2 Slope, hours | −0.124 | −0.185 | +0.061 | +0.67 | +0.036 | 1270 | PP...P |
| Min60 | A1 Slope, bars | −0.151 | −0.131 | −0.020 | −0.12 | −0.050 | 1022 | PP.... |
| Min60 | **A2 Slope, hours** | **+0.179** | −0.131 | **+0.310** | **+3.61** | +0.025 | 821 | **PPPPPP** |

| | A1 bars | A2 hours |
|---|---|---|
| 6 · positive on ≥ 2 of 3 | 1 of 3 — **FAIL** | 2 of 3 — PASS |
| 7 · flip rate 15m vs 30m within 1.35× | 1.92× — **FAIL** | 1.05× — PASS |
| **promotion rule (3,4,5 on ≥2 tf, and 6, and 7)** | **no** | **no** |

**Neither arm is promoted. The default does not change.**

## 1. The number that prompted this study did not replicate, and it inverted

`UNDERTOW_BIAS_SOURCE.md` reported **Slope at +0.198 R per trade on the Min30
holdout** — the largest single number in that study, failing only the z bar. It
was the reason for the request.

| Slope 50 / 0.05, Min30 | |
|---|---|
| previous holdout — odd symbols, **newer** half | **+0.198** |
| this holdout — odd symbols, **older** half | **−0.228** |
| swing | **0.426 R per trade** |

Same symbols, same settings, same code, a different stretch of time, and the
sign reversed. That is the second time this project has watched a single-cell
maximum do this — `EMA cross` swung 0.54 R between two halves of the *same*
universe in the bias study.

**This is the most useful result on the page and it is a negative one.** The
answer to "measure Slope as the default" is no, and the reason is not that it
scored badly; it is that its good score was not there the second time anyone
looked.

## 2. The objection in the prereg was correct, and it was measurable

Slope as shipped measures its window in **bars** and its threshold in **ATR per
bar**. Both halves are per-bar, so the rule changes with the chart:

| source | 15m flips/day | 30m flips/day | 1h flips/day | 15/30 ratio |
|---|---|---|---|---|
| A0 structure + price move — ships today | 0.63 | 0.59 | 0.56 | **1.07** |
| A1 Slope, bars 50 / 0.05 | 1.21 | 0.63 | 0.28 | **1.92** |
| A2 Slope, hours 12.5 / 0.02 | 1.21 | 1.16 | 1.55 | **1.05** |

A1 halves its activity at every step up the timeframe ladder — 1.21, 0.63,
0.28. That is the exact defect `price move` swings were adopted to fix, and
Slope-in-bars has it worse than the bar pivot did (1.92× against 2.1×, and
4.3× across all three).

`slopeUnit = "hours"` removes it. The unit test sweeps the whole threshold
ladder across a 4:1 aggregation: **bars keeps ×0.21 of its flip rate, hours
keeps ×1.03 to ×1.24.**

The calibration was clean and is worth showing, because it is the only free
number in the study:

| rung (day-ranges/hour) | flips/day on calibration | \|log ratio\| to A1's 1.066 |
|---|---|---|
| 0.002 | 1.887 | 0.571 |
| 0.010 | 1.466 | 0.318 |
| **0.020** | **1.120** | **0.049** ← chosen |
| 0.030 | 0.830 | 0.250 |
| 0.050 | 0.412 | 0.951 |

1.120 against a target of 1.066 is a near-exact flip-rate match, so A1 and A2
really are the same rule in two units — **on 15m**. See §4, where they stop
being.

## 3. A2 is the strongest result in this project, and I do not believe it

On Min60, A2 clears every expectancy bar: **+0.179 R per trade, +0.310 over the
baseline at z +3.61, and +0.155 ± 0.072 above its own random-entry control.**
Nothing in seven Undertow studies has done that. It also clears bar 4 on Min15
(+0.196 ± 0.130) and bars 6 and 7 outright.

Here is why it still does not ship, and every number is from this same run.

**It is significantly WORSE than random on Min30.**

| A2 vs its own seeded control | diff | z |
|---|---|---|
| Min15 | +0.196 ± 0.130 | **+1.51** |
| Min30 | **−0.160 ± 0.065** | **−2.46** |
| Min60 | +0.155 ± 0.072 | **+2.15** |

One arm, one setting, one run: significantly better than a coin on 1h and
significantly worse than a coin on 30m. A real effect does not do that. An
unstable one does, and this study opened by documenting an arm that inverted by
0.426 R between two time periods.

**And it is one cell of three.** So was +0.198. The pre-registered promotion
rule demanded bars 3–5 on **two** timeframes precisely so that one cell could
not carry a decision, and it did its job.

## 4. A2 and A1 are NOT the same rule on 1h, which weakens the Min60 result

The calibration matched their flip rates on 15m: 1.21 against 1.21. By 1h they
have separated completely — **A2 flips 1.55 times a day and A1 flips 0.28**, a
factor of 5.5.

That is scale invariance behaving exactly as advertised: A1 degenerates on the
higher timeframe and A2 does not. But it means the Min60 comparison is no
longer "the same rule in two units". A2 on 1h is a **far more active** rule
than A1 on 1h, and "trade five times as often on 1h" is a plausible alternative
explanation for its +0.310 that this study cannot separate from "the unit is
right".

A2's own flip rate also drifts across the three timeframes — 1.21, 1.16, 1.55,
a **1.34× spread**. Bar 7 was defined on 15m vs 30m and it passes there at
1.05×; across all three it sits just inside the same threshold, not
comfortably. The `hours` unit fixes most of the timeframe dependence and not
all of it.

## Against the prediction

| predicted | actual | |
|---|---|---|
| A1 will not replicate +0.198 on Min30; expect −0.15 to +0.10 | **−0.228** — did not replicate, and landed below the range | **right, and worse than predicted** |
| A2 ≈ A1 on expectancy, within ±0.10 R | +0.05, +0.10, **+0.33** — the Min60 gap is triple the band | **wrong** |
| A2 passes bar 7, A1 fails it | exactly that, 1.05× against 1.92× | right |
| nothing clears bar 3 or bar 4 | A2 cleared **both** on Min60, and bar 4 on Min15 | **wrong** |
| the default does not change | it does not | right |
| "if I am wrong anywhere it is bar 7 on A2" | bar 7 was the thing I got right; I was wrong on bars 3 and 4 | **wrong about where I was wrong** |

Two of six wrong, and they are the two that matter. I predicted the seventh
ablation would find nothing, as the previous six did, and on one timeframe it
found the largest effect in the project.

## What changes

**Nothing ships.** The bias stays `structure` on `price move` swings. The
promotion rule was fixed before the run and A2 missed it on bar 3 at two of
three timeframes.

**`slopeUnit` stays defaulted to `bars`** even though `hours` is the version
that clears bar 7. This is deliberate and it is worth being explicit, because
the argument for switching is real: consistency is the *declared* basis for the
current swing default, bar 7 was pre-registered, and A2 passes it while A1
fails. The reason I am not switching is that the prereg says the residue is
"available behind a dropdown, **promoted to nothing**", and quietly moving a
sub-default *after* seeing that the same arm scored better is the move the
prereg exists to stop. **If you want `hours` to be the default whenever Slope
is selected, that is a defensible call on the consistency ground alone and it
is a one-line change — but it should be your call, not one I make on the back
of a score.**

**Every quadrant of this dataset is now spent for this question.** Even/older
and odd/newer went to the bias study; even/newer and odd/older went to this
one. There is no clean in-sample test of A2 left. The only honest next test of
+0.310 on 1h is forward, on data that does not exist yet, which is what the
watch is for.

## The open question, narrowed

Seven studies, seven ablations, and the tally now reads: six components with no
effect, and one arm that beat its control on two timeframes out of three while
losing to it significantly on the third. That is not an edge. It is the
clearest picture yet of **what the noise floor of this measurement actually
is** — about ±0.3 R per trade per cell — and every "finding" this project has
produced, including this one, has been smaller than a number that has twice
inverted on re-measurement.
