# Where should the bias come from? Nothing wins, and one thing nearly did

Against [`PREREG_undertow_bias_source.md`](../prereg/PREREG_undertow_bias_source.md).
23 symbols, 12,000 bars each, 15m / 30m / 1h. Everything but the direction held
constant, retrace-only Ending on every arm, 7bp fees. Chosen on the even
symbols' older half, scored **once** on the odd symbols' newer half.

## The verdict

| tf | chosen | holdout | S1 baseline | Δ | z | control | n | bars |
|---|---|---|---|---|---|---|---|---|
| Min15 | S6 range swings | +0.039 | +0.030 | +0.009 | +0.13 | −0.062 | 1281 | PP·PP |
| Min30 | **S4 Slope** | **+0.198** | −0.030 | **+0.228** | **+1.72** | +0.049 | 997 | PP·PP |
| Min60 | S5 Range position | −0.035 | −0.108 | +0.073 | +0.64 | −0.022 | 2625 | PP··· |

**Bar 3 — beat the baseline by ≥ 0.10 R at |z| ≥ 2 — failed on all three.**
Min30's Slope arm came closest and failed on the z only: +0.228 R per trade at
z 1.72.

**Bar 4 — beat its own control — passed on two of three, which has not happened
before in this project.** It needs the qualification, though: bar 4's threshold
is *1 SE*, which is a one-sided 16% chance under the null, not significance.
The two passes were z 1.68 (Min15) and z 1.32 (Min30). Read as "not obviously
worse than a coin", not as "beats a coin".

## Why I do not believe any of it, and the evidence is inside the study

**EMA cross swung by 0.54 R per trade between two halves of the same
universe:**

| | Min15 train | Min15 holdout | Min30 train | Min30 holdout |
|---|---|---|---|---|
| **S2 EMA cross** | **−0.281** | **+0.261** | +0.055 | −0.137 |

On 15m it was the *worst* arm on train and would have been the *best* on the
holdout (+0.261 ± 0.068, z 3.8 against zero). On 30m it did the same thing in
reverse. A real effect does not do that. Had the selection rule happened to
pick it, this page would be reporting a z-3.8 "discovery" that the very next
panel contradicts.

That is the single most useful number in the study, and it is only visible
because every arm is printed on both halves.

## The full holdout tables

| arm | Min15 | Min30 | Min60 | flips/day (15m) | median hold |
|---|---|---|---|---|---|
| S0 structure, as shipped *(reference)* | −0.112 | +0.119 | −0.136 | 2.2 | 8.2 h |
| **S1 structure, matched — baseline** | +0.030 | −0.030 | −0.108 | 2.2 | 8.2 h |
| S2 EMA cross 50/200 | +0.261 | −0.137 | −0.184 | 0.6 | 23 h |
| S3 Supertrend 10/3.0 | +0.030 | +0.014 | −0.080 | 2.4 | 7.2 h |
| S4 Slope 50 @ 0.05 | −0.093 | **+0.198** | −0.230 | 1.2 | 15.5 h |
| S5 Range position 50 | −0.042 | +0.058 | −0.035 | 7.5 | 1.0 h |
| S6 structure, range swings | +0.039 | +0.047 | −0.034 | 0.7 | 25.5 h |

Twenty-one holdout cells, nine positive, twelve negative, none significant
against the baseline. The column that varies most is not the source — it is the
timeframe.

## What the study does establish

**1. The consistency finding holds, and it is the answer to the original
complaint.** A pivot measured in BARS is a different rule on every chart:

| source | 15m flips/day | 30m flips/day |
|---|---|---|
| bar 6/2 — shipped | 2.3 | 1.1 |
| **range 0.40** | **0.6** | **0.6** |
| Slope 50 | 1.2 | 0.5 |
| Supertrend 10/3 | 2.4 | 1.2 |
| Range position 50 | 7.3 | 3.4 |

`range 0.40` is the only source that gives the same flip rate on both
timeframes. Supertrend and Range position are *as twitchy or worse* than the
pivot they were meant to replace — Range position flips **7.3 times a day** on
15m, a median hold of one hour, which is not a bias, it is a coin.

**2. The shipped Ending rules are not the problem either.** S0 (as shipped)
against S1 (retrace only) differs by −0.14, +0.15 and −0.03 across the three
holdouts — no sign, no size, no pattern.

**3. Slope is the only source with a mechanism that matches the complaint**, and
it is the only one whose train and holdout agreed on the timeframe where it was
chosen (+0.097 → +0.198 on 30m). It holds its direction below the threshold
instead of flipping on noise. It is also −0.093 and −0.230 on the other two, so
this is a hypothesis and not a finding.

## Against the prediction

| predicted | actual | |
|---|---|---|
| all arms within ±0.10 R of each other and zero | range is −0.23 to +0.26 — wider than that | **wrong** |
| trade counts differ enormously by source | 498 to 2,779 on one panel | right |
| no arm beats its control | two of three passed a 1-SE bar | **half wrong** |
| range swings match on expectancy, win on consistency | exactly that | right |
| "the one I cannot call is Slope — if anything wins, it" | Slope is the closest thing to a win | right |

The first one is the one that matters: I expected the arms to be
indistinguishable and they are not — they are *unstable*, which looks similar
in a summary table and is a different thing.

## What changes

**Nothing ships differently.** The watch stays on `structure` with the shipped
settings, because nothing cleared bar 3 and the one arm that came close is
contradicted by its own other two panels.

**All five sources are on the chart** and in the port, selectable from one
dropdown, so they can be looked at. That is what they earned.

**If you want one recommendation on grounds other than edge:** `range 0.40`
swings, because it is the only setting in the study that means the same thing
on 15m as it does on 30m. That makes every future measurement comparable across
timeframes and stops the "it works differently on each chart" problem at its
source. It does not make money and this page does not claim it does.

## The open question, unchanged

Six components have now been ablated — candle, location, exit, bias gate, fill,
and now the direction source — and none has beaten its control at any threshold
worth the name. The remaining explanation is the one no backtest reaches, the
watch exists for it, and it is still the only thing left to try.
