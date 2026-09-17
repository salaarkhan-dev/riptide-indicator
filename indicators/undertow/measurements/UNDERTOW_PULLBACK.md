# The 2nd and 3rd candle are as good as the 1st — and it still is not an edge

Against [`PREREG_undertow_pullback.md`](../prereg/PREREG_undertow_pullback.md).
`SYMBOLS_FRESH4`, ranks 136–180, disjoint from the 23 and from all three
earlier fresh sets. One primary fixed in advance, scored once.

## The verdict

| tf | A1 | A0 (ships) | Δ | z | control | n | SHARED | ADDED | DROPPED | bars |
|---|---|---|---|---|---|---|---|---|---|---|
| Min15 | −0.043 | +0.007 | −0.050 | −0.58 | −0.074 | 2596 | −0.055 | −0.030 | +0.055 | PP... |
| Min30 | +0.122 | +0.059 | +0.062 | +0.80 | −0.057 | 2586 | +0.133 | +0.109 | −0.015 | PP.PP |
| Min60 | −0.040 | −0.042 | +0.002 | +0.03 | −0.037 | 2427 | −0.029 | −0.053 | −0.065 | PP... |

**Bar 3 failed 3 of 3. Bar 4 passed once. Bar 6 failed. Nothing is promoted.**

## THE ANSWER TO THE QUESTION THAT PROMPTED THIS

*"We detect the first candle; if that does not qualify, move to the second and
third."* That is `locTol = 2`, and the decomposition answers it directly:

| | Min15 | Min30 | Min60 |
|---|---|---|---|
| **SHARED** — the pin at the extreme bar | −0.055 | +0.133 | −0.029 |
| **ADDED** — pins 1–2 bars later, which A0 refuses | **−0.030** | **+0.109** | **−0.053** |
| difference | **+0.025** | **−0.024** | **−0.024** |

**The 2nd and 3rd candle are worth within ±0.025 R of the 1st**, and better on
one of three. And `locTol = 2` alone (arm A2) **nearly doubles the setups**:

| trades per day per symbol | Min15 | Min30 | Min60 |
|---|---|---|---|
| A0 — extreme bar only | 0.63 | 0.30 | 0.14 |
| A2 — extreme bar + next two | **1.06** | **0.50** | **0.24** |

So the answer is **yes, and it costs about 0.024 R per trade.** Defect 3 was
real: requiring the pin to BE the extreme bar was throwing away roughly as many
setups again, of essentially the same quality.

**That is a throughput finding, not an edge.** A2 scores −0.004 / +0.074 /
−0.032 against A0's +0.007 / +0.059 / −0.042 — the same nothing, at 1.7× the
rate. If you want more alerts for the same expectancy, this is where they are.
**I predicted ADDED would be 0.05–0.20 R worse**, on the reasoning that a pin
one or two bars late sits at a worse price for the same stop. That was the
prediction I flagged as least certain and it was wrong.

## The other half went the other way

**DROPPED — the shallow-pullback setups that `pbMinDepth` removes — score
+0.055 / −0.015 / −0.065.** No consistent sign, and on 15m the rule removes
*better*-than-average trades.

Defect 2 is a correct description of the rule and a useless filter. A quarter to
a third of setups genuinely have no pullback behind them; those setups are not
systematically worse. Requiring 20% of the impulse back (A3) cuts trades per day
from 0.63 to 0.28 on 15m and buys −0.062 R for it.

## The bar unit is timeframe-dependent, as predicted

`pbMinAge = 3` is three bars everywhere and three bars is not the same thing
anywhere:

| A4 keeps | Min15 | Min30 | Min60 |
|---|---|---|---|
| of A0's setups | **39.9%** | **29.8%** | **23.6%** |

It also printed the largest number in the study — **+0.268 R on Min30**, z 2.65
against zero on 734 trades. It is descriptive and could not be promoted, which
is the point: it is a bar-unit rule on one cell of fifteen, and four numbers in
this project have already inverted between populations.

## A BUG I WROTE, CAUGHT BY A NUMBER THAT LOOKED WRONG

The first run of this study printed a control of **−0.511 / −0.402 / −0.395**
and bar 4 PASSED on all three. Every previous control here has run −0.02 to
−0.15, and at `rr` 3.5 a random entry should sit near zero — −0.5 implies an
11% win rate against a 22.2% break-even. It was not a discovery, it was a bug.

`control_full()` **discarded** random entries that resolved neither way inside
the window, with a bare `continue`. At `rr` 3.5 the stop sits 1R away and the
target 3.5R, so whatever resolves inside a short window is mostly stop-outs:
discarding the rest keeps the control's losers and throws away its survivors.

`undertow_sweep.control()` already handled this correctly, and its comment says
exactly why — *"marked to market, which is the only reading that does not
quietly discard the control's losers."* **I wrote a fresh control specifically
to fix a different flaw in that helper, and introduced a worse one by not
copying the part that was right.**

Fixed, re-run, and the corrected control is −0.074 / −0.057 / −0.037. **Bar 4
then fails on two of three instead of passing on all three.** Bars 3, 5 and 6
never touched the control and are unchanged.

## Against the prediction

| predicted | actual | |
|---|---|---|
| A1 fails bar 4 | fails on 2 of 3 | right |
| A2 roughly doubles the trade count | 0.63 → 1.06 trades/day on 15m | right |
| **ADDED scores 0.05–0.20 R worse than SHARED** | **within ±0.025, better on one** | **wrong — and it was the one I flagged** |
| DROPPED below zero | −0.015, −0.065, but **+0.055** on 15m | half right |
| A3 raises mean R and fails bar 3 anyway | lowered it on 15m and 60m | wrong |
| A4 removes a different fraction per timeframe | 39.9% / 29.8% / 23.6% | right |

## What changes

**Nothing ships.** `locTol`, `pbMinAge` and `pbMinDepth` stay at 0 / 0 / 0.0.
The promotion rule required bars 3, 4, 5 and 6 and A1 cleared bar 3 nowhere.

**One thing is now known that was not.** The location rule's strictness is
costing roughly half the setups at no measurable gain in quality. That does not
make the strategy profitable — A2 is −0.004 / +0.074 / −0.032, which is the
same zero — but if the watch is ever run for the reason it exists (a forward
record of human selection), **`locTol = 2` gives it 1.7× the sample for the
same expectancy**, and sample size is the binding constraint on that question.

That is a reason to consider it for the WATCH and not for the backtest, and it
is the first setting in this project with an argument that does not depend on
an edge existing.
