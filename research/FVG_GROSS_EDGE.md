# Is the FVG edge constant gross, with fees explaining the rest? No.

Pre-registered in `PREREG_fvg_gross_edge.md`. Study:
`research/studies/fvg_gross_edge.py`.

## Verdict: NOT SUPPORTED

```
87 / 86 / 84 symbols, 330-332 days, the same window at every timeframe

Min15  n 30,067   GROSS +0.006 ± 0.009   Δ -0.015 ± 0.010  z -1.59   ctl Δ -0.017
Min30  n 14,842   GROSS -0.000 ± 0.012   Δ +0.012 ± 0.013  z +0.91   ctl Δ -0.008
Min60  n  6,895   GROSS +0.045 ± 0.016   Δ +0.052 ± 0.018  z +2.82   ctl Δ +0.002

spread 0.045 R against the pre-registered 0.04 band
```

| bar | | |
|---|---|---|
| 1 | 300+ bets **and** 300+ days everywhere | PASS |
| 2 | gross R positive on all three | **FAIL** |
| 3 | gross R flat within 0.04 R | **FAIL** |
| 4 | gross Δ beats the random-bar control | PASS |
| 5 | \|z\| ≥ 2.0 on gross Δ everywhere | **FAIL** |

**The hypothesis was mine and it is wrong.** The gross edge is not flat. It is
about zero on Min15 and Min30 and +0.045 on Min60.

## Why the post-hoc arithmetic misled me

In `FVG_TIMEFRAME_COHERENCE.md` I added fee drags of **0.136 / 0.088 / 0.058 R**
to each timeframe's net and got implied gross edges of +0.092 / +0.093 / +0.103
— flat, and convincing enough to be worth a prereg.

Those drags came from `ccp_entry_models`, which used a **different stop rule**:
0.25 ATR as a *floor* rather than a buffer beyond the wick. Tighter stops, and
fees in R go as 1/risk. The drags actually measured here, on this study's own
stops, are **0.034 / 0.022 / 0.015 R** — a quarter the size.

I flagged the borrowing in the prereg as "indicative and not exact". It was not
indicative. It was the whole result.

**The lesson is narrow and worth keeping: a quantity that goes as 1/risk cannot
be carried between studies with different stop rules.**

## What the run found instead, and it matters more

**The timeframe-specificity is real, not a cost illusion.** Min60 has a gross
edge and the faster timeframes do not. Whatever makes the 1h case different, it
is not that 1h is simply the first timeframe where the same edge clears its
fees — that idea is now dead.

**And on the fast timeframes the FVG filter is mostly selecting cheaper trades,
not better ones:**

| | gross Δ | net Δ | how much of net Δ is cost |
|---|---|---|---|
| Min15 | **−0.015** | +0.038 | all of it, and then some |
| Min30 | +0.012 | +0.046 | about three quarters |
| Min60 | +0.052 | +0.074 | about a third |

On Min15 the filter's gross Δ is **negative**: the grabs it picks are slightly
*worse*, and the net advantage comes entirely from their being wider-stopped
and therefore paying proportionally less fee. Median risk among FVG grabs runs
higher at every timeframe, which is the mechanism.

That partly reaches back into the earlier confirmations. `FVG_H1_HOLDOUT` and
`FVG_H1_TEMPORAL` measured **net** R, so a share of those passes was a cost
effect rather than a selection effect. On Min60 a real gross Δ of +0.052 at
z +2.82 survives that deduction — but it is smaller than the net numbers
implied, and the fast-timeframe versions of the same filter do not survive it
at all.

## Break-even fees, reported not tested

| | median risk | fee drag | break-even round trip |
|---|---|---|---|
| Min15 | 0.78% | 0.034 R | **0.007%** |
| Min30 | 1.16% | 0.022 R | ~0.000% |
| Min60 | 1.73% | 0.015 R | **0.131%** |

Min60 has roughly three times the headroom of the harness's ~0.044% assumption.
Min15 and Min30 need a fee tier at or below free.

## Status

Outcome C stands. This was an explanation, it failed, and nothing is
reinstated. The FVG line now has three pre-registered passes on **net** R at
Min60, one pre-registered failure on coherence, and one pre-registered failure
of the explanation offered for that failure.

What is left standing is narrower than it was a day ago: **a gross edge at
Min60 of +0.045 ± 0.016, unexplained, that does not appear at Min15 or Min30.**
Any further work starts by explaining why 1h, and the cost story — the obvious
candidate — has now been tested and ruled out.

No forward run, no signal, no alert, no production code.
