# PRE-REGISTRATION — is the FVG edge NET-positive at 4h and 8h?

Committed before the first number. Run by
`indicators/ccp/studies/fvg_net_higher_tf.py`.

## Why this is half a test and half arithmetic, said up front

`research/FVG_HIGHER_TF.md` measured **gross** R at Hour4 and Hour8 on the 90
non-discovery symbols: **+0.037 and +0.067**, with median risk **3.78% and
5.45%** of price against Min60's 1.78%.

Net R is gross R minus a fee that depends only on risk size. **On those same
symbols the net answer is already determined** by numbers I have seen. Running
it there produces exact figures, not evidence, and this file will not present
it as evidence.

So the run is split, and only one half is a test:

| | population | status |
|---|---|---|
| **THE TEST** | the **23 discovery symbols** | never measured at Hour4 or Hour8, at any window, gross or net |
| **the arithmetic** | the 90 non-discovery symbols | already used for gross; net there is subtraction and is reported as such |

The 23 symbols are the FVG line's *original* universe — contaminated for Min60,
where they found the effect, and **completely fresh above it**, because no run
in this sequence has touched Hour4 or Hour8 on them.

    H: FVG grabs at Hour4 and Hour8 have positive NET R after fees on the
       23 discovery symbols, and beat Min60's net on the same symbols.

## Design

Every arm: **pivot 3, window 2, horizon 48 bars** — unchanged from
`FVG_HIGHER_TF`, so the two are directly comparable. 1,200 days. Min60 is
carried as an anchor on each population and is **not a test**.

Scored **net**, with `research.harness` fees. Gross is reported beside it so
the drag is visible and measured here rather than inferred.

The FVG rule, stop buffer, target and scoring are **imported** from
`indicators/ccp/studies/fvg_higher_tf.py`. Nothing is tuned.

## Bars — on the 23-symbol test population only

1. **COVERAGE.** ≥ 300 FVG grabs and ≥ 300 days at both Hour4 and Hour8.
   Hour8 on 23 symbols is the arm at risk; a thin panel is reported as not
   measurable rather than read.
2. **NET POSITIVE.** Net R > 0 at both.
3. **BEATS 1h NET.** Net R at both ≥ Min60's net on the same 23 symbols.
4. **GRAB-SPECIFIC.** Net Δ beats the same filter on seeded random-bar entries,
   at both.
5. **SIGNIFICANCE.** Clustered |z| ≥ 2.0 on net Δ at both.

Family: one hypothesis, two timeframes that must agree. If a panel's MDE
exceeds **0.15 R** it is **UNDERPOWERED** and reported as a bound.

## My prediction

**Bar 2 passes, ~7 in 10.** This is the one place a confident lean is earned
rather than manufactured: gross was positive at both on the other population,
the drag falls as 1/risk, and risk is two to three times larger than Min60's.
The arithmetic has to go badly wrong for net to be negative.

**Bar 3 is the interesting one and I put it at ~50/50.** It needs Hour4 and
Hour8 net to each beat Min60 net *on the same symbols* — and Min60 on these
23 is the contaminated cell where the effect was originally found, so it is
likely to look strong. The test is partly "does 4h/8h beat the number that
started all this, measured on its home turf".

**Bar 5 is where I expect a failure, on Hour8**, purely on sample size: 23
symbols at 8-hour bars over 1,200 days is roughly 700 FVG grabs, and a z of 2
on that is a real requirement.

## What cannot happen

* **No tuning**, no third timeframe, no re-cut of the window, and no switching
  the test population to the 90 if the 23 disappoint.
* **No production change**, no API key, no order placement.
* **One run.** There is no v2, and a pass does not reopen outcome C. The
  question of *why 1h is a floor* remains unanswered by anything here.

## If it passes

The FVG line would have a net-positive result on a population fresh for these
timeframes — which is the strongest thing it has had — and the next step is a
**forward-tracking run at Hour4 or Hour8**, not a trade. Slower bars also mean
far fewer signals, so a forward run there needs months, and that is the cost of
the only clean test left.
