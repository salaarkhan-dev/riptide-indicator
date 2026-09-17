# Is the exit the bug? No — but the 1:7 trades are real

Against [`PREREG_undertow_exits.md`](../prereg/PREREG_undertow_exits.md). Eight
exits scored on identical frozen fills, same stop in every arm, 200-bar horizon
with unresolved trades marked to market (it truncated 0–2% of trades, so the
runner arms were measured rather than cut off).

## First, the part that vindicates the manual account

**The tail is there.** Across six panels:

| | median MFE | p75 | p90 | p95 | max |
|---|---|---|---|---|---|
| Min15 | 1.05 / 0.99 | 2.84 / 2.41 | 6.12 / 6.10 | 7.52 / 8.86 | 15.1 / 31.5 |
| Min30 | 1.14 / 1.05 | 3.61 / 2.80 | 7.23 / 6.35 | 8.04 / 9.33 | 41.5 / 44.7 |
| Min60 | 1.11 / 0.99 | 3.63 / 3.26 | 7.02 / 7.17 | 7.60 / 8.61 | 62.1 / 17.9 |

*(train / holdout)*

**8 to 12% of these trades reach 7R.** The 90th percentile is 6–7R. The average
trade's best price is **+2.1 to +2.6 R** — the MFE oracle, z ≈ 6–7. Someone
watching these setups and remembering 1:3 to 1:7 outcomes is **remembering
correctly**. Those trades exist, at roughly one in ten.

That was worth establishing. It means the disagreement was never about whether
the moves happen.

## And here is why it does not add up to an edge

A fixed-R exit breaks even at a hit rate of **1/(1+R)** — which is also exactly
what a driftless random walk delivers. So "how often did it reach kR" against
1/(1+k) is the strategy against a coin, and it needs no control run. It is
arithmetic.

| target | break-even | Min15 | Min30 | Min60 | average edge |
|---|---|---|---|---|---|
| 1R | 50.0% | 51.6 / 49.5 | 52.5 / 52.0 | 53.9 / 49.7 | **+1.5 pp** |
| 2R | 33.3% | 33.3 / 29.8 | 35.8 / 33.9 | 37.3 / 34.6 | **+0.8 pp** |
| 3R | 25.0% | 24.0 / 18.2 | 28.4 / 23.2 | 30.4 / 26.4 | **+0.1 pp** |
| 5R | 16.7% | 13.2 / 12.6 | 18.5 / 10.7 | 17.5 / 18.2 | **−1.5 pp** |
| 7R | 12.5% | 7.4 / 8.6 | 11.7 / 8.5 | 10.1 / 12.6 | **−2.7 pp** |

At every target the hit rate sits within a couple of points of a coin, and it
gets **worse** as the payoff grows. That is the signature of no edge, and the
7R row is the one that matters most to the manual account: **a coin flip with a
1:7 payoff produces a 7R winner 12.5% of the time. Undertow produces one 10% of
the time.**

The 1:7 trades are real. They are also exactly as common as chance, and slightly
less.

## The arms

| tf | chosen on train | holdout | vs fixed 3R | ceiling (E7) |
|---|---|---|---|---|
| Min15 | E5 liquidity | −0.168 | +0.189 (z +1.24) | +2.153 |
| Min30 | E3 fixed 7R | −0.108 | −0.015 (z −0.08) | +2.614 |
| Min60 | E0 fixed 2R | +0.005 | −0.041 (z −0.21) | +2.529 |

No arm cleared bar 2. No arm cleared coverage (159–198 against the
pre-registered 300, so these are bounds). One of three was positive.

**The gap between +2.5 R available and ~0 R captured is not an exit problem.**
Every arm was offered the same excursion and none could convert it, because the
excursion is a right tail that arrives one trade in ten while the other nine hit
the stop. No exit rule fixes a hit rate that equals chance — running winners
further only helps when the tail is *fatter* than chance, and here it is
thinner.

My prediction was that every runner would beat fixed 3R by 0.1–0.4 R. On the
holdout, **two of three did not.** The right-tail reasoning was correct in
principle and the tail was not fat enough for it to pay.

## What this does not close

Three differences between this and the manual account remain untested, and two
of them are testable:

1. **The backup fill at an OB or FVG.** `gone` — the target printing before the
   limit filled — is a large bucket, and those are trades where the move
   happened and the order was not on. This changes *which trades exist* and is
   the next study.
2. **Lower-timeframe stop refinement.** A tighter stop raises every R in the
   table above. It also gets hit more often, and the table shows the hit rate is
   already at chance, so it is not obviously a rescue — but it has not been
   measured and it should not be dismissed from the armchair.
3. **Selection.** ~10 discretionary trades a week against 12,000 mechanical
   ones. **Nothing in historical bars can measure this**, and it is the only
   remaining explanation that fits all the evidence: the tail is real, the
   mechanical base rate is chance, and a trader who can pick which one in ten is
   about to run is profitable on exactly this data.

That third one is not a dismissal. It is a statement that the question has moved
somewhere a backtest cannot follow, and the only instrument that can settle it
is a **prospective record**: alerts fired forward in real time, taken or skipped
by a human, with the outcome tracked. That is what `riptide/watchers/` is for
and it is the next thing to build.
