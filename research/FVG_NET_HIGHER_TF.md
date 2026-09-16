# Net FVG edge at 4h and 8h — not established

Pre-registered in `PREREG_fvg_net_higher_tf.md`. Study:
`research/studies/fvg_net_higher_tf.py`.

## The test — 23 discovery symbols, fresh above 1h

```
tf     syms  days     n    NET R     SE   net Δ      z   gross   drag  risk%   ctlΔ
Min60    23  1197  5977   +0.039  0.018  +0.110  +5.43  +0.055  0.016   1.63  +0.016
Hour4    23  1190  1460   +0.043  0.037  +0.103  +2.50  +0.051  0.008   3.46  +0.089
Hour8    20  1179   706   +0.032  0.052  +0.103  +1.75  +0.038  0.005   4.99  +0.030
```

| bar | | |
|---|---|---|
| 1 | 300+ bets and 300+ days, both | PASS |
| 2 | net R positive at both | **PASS** |
| 3 | net beats Min60 net on the same symbols | **FAIL** |
| 4 | net Δ beats the random-bar control, both | PASS |
| 5 | \|z\| ≥ 2.0 on net Δ, both | **FAIL** |

**Verdict: NOT ESTABLISHED.**

## The predictions, which were on the record

The prereg said bar 2 would pass at ~7 in 10, bar 3 was 50/50, and **bar 5
would fail on Hour8 purely on sample size**. All three were right: bar 2
passed, bar 3 failed, and Hour8 came in at z +1.75 on 706 grabs.

Recording that because the two predictions before this one were wrong, both in
the same direction. Three in a row would be a pattern; one in three is not a
calibration.

## Why it failed, which is the useful part

**The fee arithmetic worked exactly as expected and did not help.** Drag falls
from 0.016 R at Min60 to 0.008 and 0.005 — a third, as the 1/risk relation
predicts. But **gross fell at the same time** on this population: +0.055 →
+0.051 → +0.038. The cost saving was real and was cancelled by the edge
shrinking, so net went +0.039 → +0.043 → +0.032 and never pulled clear.

**At Hour4 the effect is barely grab-specific.** The control — the same FVG
filter on seeded random-bar entries — gives **Δ +0.089** against the filter's
**+0.103**. Bar 4 passes on that margin, and the margin is meaningless next to
the standard errors. On Hour4, for these symbols, an FVG predicts nearly as
much anywhere as it does at a grab.

That flatly contradicts the 90-symbol arithmetic panel, where Hour4's control
is **−0.007**. Two populations, opposite answers on the same question, and no
reason to prefer either.

## Where the whole FVG line now stands

| run | result |
|---|---|
| discovery, Min60 | positive both halves |
| 84 unseen symbols, net | CONFIRMED z +4.12 |
| 862 prior days, net | CONFIRMED z +9.19 |
| timeframe coherence | **OUTCOME C** |
| gross flat across timeframes | **refuted** |
| horizon explains it | **refuted** |
| gradient continues above 1h | **refuted** |
| net-positive above 1h | **not established** |

Three pre-registered passes, then four pre-registered failures — every one of
them an attempt to explain or extend the passes, and none of them succeeding.

**What survives:** at Min60 the FVG filter sorts grabs, repeatedly, on data it
has not seen — net Δ +0.110 at z +5.43 on the discovery symbols and +0.098 at
z +8.65 on the others, in this run alone. The sorting is not in doubt.

**What does not survive:** any account of *why*, any extension beyond 1h, and
any claim that the sorted subset is worth trading. Standalone net R at Min60 is
+0.038 to +0.039 across both populations — positive, small, and sitting on top
of a fee drag of 0.015 R with slippage unmodelled.

## The honest next step

Not another explanation. Four have been tested and four have failed, and the
fifth would be chosen after seeing which residuals are left — which
`CCP_FILTER_OVERFIT.md` already measured the value of.

**The only clean test left is forward.** Log Min60 FVG grabs as they occur,
score them by these rules, and look in three months at data that does not
exist yet. Everything else in this repository has now been spent on the
question.

No signal, no alert, no production code.
