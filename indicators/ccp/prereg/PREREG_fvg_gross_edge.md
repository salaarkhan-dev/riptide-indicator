# PRE-REGISTRATION — is the FVG edge constant gross, with fees explaining the rest?

Committed before the first number. Run by
`indicators/ccp/studies/fvg_gross_edge.py`.

## Where this comes from, and its status

`research/FVG_TIMEFRAME_COHERENCE.md` returned **OUTCOME C** and the FVG line
stopped. In writing that up I noticed, *after* seeing the numbers, that adding
the measured fee drag back to each timeframe's net R gives implied gross edges
of **+0.092, +0.093 and +0.103** — flat, with only the cost changing.

**That observation was post-hoc and is worth nothing as evidence.** This prereg
exists to turn it into something falsifiable, tested properly, instead of
letting it quietly rehabilitate a failed result.

    H: the FVG filter's GROSS edge at grabs is positive and roughly constant
       across Min15, Min30 and Min60, and the differences in NET R between
       timeframes are fee drag alone.

**A pass does not reinstate the Min60 result.** Outcome C stands whatever this
returns. What a pass would buy is a coherent explanation and a reason to test
the thing at a fee tier where it could survive; what a failure buys is the end
of the line.

## Fixing the flaw that produced outcome C

The Min15 panel in that run covered **25 days** against 862 for the others,
because the exchange will not page Min15 back further. The prereg set a floor
on the number of grabs and none on the span of time, and 12,933 grabs inside
one month looked like coverage.

**Population here is the 90 non-discovery symbols over the same 333 days at all
three timeframes**, so every panel spans the same window by construction. Bar 1
adds an explicit **time-span floor** as well as a bet floor.

**What is and is not fresh, stated plainly.** Min15 and Min30 on this
population are entirely new. Min60 *net* on this population is already known
(`FVG_H1_HOLDOUT.md`, +0.031); Min60 **gross** is a new measurement. This is
not a clean holdout for the Min60 cell and is not claimed as one — the
hypothesis under test is about the *relationship across three timeframes*, and
two of the three are fresh.

## Held constant

The FVG rule, pivot width, stop buffer, target, horizon and scoring are
**imported** from `indicators/ccp/studies/fvg_h1_holdout.py`, unchanged. Horizon is
48 hours at each timeframe: 192 / 96 / 48 bars.

Each timeframe is scored **twice on the identical setups** — once with the
harness's fees and once with `fee_pct=0.0`. Gross and net therefore differ by
the fee and nothing else, and the drag is **measured in this run** rather than
borrowed from another study with a different stop rule, which is how the
post-hoc table was built and one reason it proves nothing.

## Bars

1. **COVERAGE.** ≥ 300 FVG grabs **and** ≥ 300 days of window in every
   timeframe. The second half is the fix for what broke the last run.
2. **GROSS POSITIVE.** Gross R for FVG grabs > 0 on all three timeframes.
3. **FLAT.** max − min of the three gross R values ≤ **0.04 R**. This is the
   hypothesis. A gross edge that varies more than that across timeframes is not
   "constant with fees explaining the rest", and the explanation is wrong.
4. **GRAB-SPECIFIC.** Gross Δ at grabs exceeds gross Δ from the same filter on
   seeded random-bar entries, on all three timeframes.
5. **SIGNIFICANCE.** Clustered |z| ≥ 2.0 on gross Δ in every timeframe.

Family size: **one hypothesis**, five bars, three timeframes that must agree.
Requiring agreement across three panels is stricter than any single test, not
looser, so there is no correction to make.

If a panel's MDE exceeds **0.10 R** it is **UNDERPOWERED** and reported as a
bound.

## Reported but not tested

* net R beside gross R, and the measured drag between them
* the implied break-even fee for each timeframe — the rate at which net crosses
  zero. This is arithmetic, not a test, and it is the number that would matter
  if anything were ever built.

## My prediction

I have been wrong twice in this sequence, both times predicting failure and
getting a pass, so a third pessimistic guess would be a reflex rather than a
judgement.

* **Bars 2 and 3 (gross positive and flat): I expect these to pass, ~3 in 5.**
  The post-hoc arithmetic was tight — +0.092, +0.093, +0.103 — and that band is
  narrow enough that it is unlikely to be coincidence across three timeframes.
* **Bar 4 is the one I expect to fail, on Min15.** In the coherence run the
  Min15 control Δ was **+0.096** against the filter's **+0.108** — the FVG
  barely beat a random entry there. If that holds with a proper window, the
  effect is not grab-specific at the fast end and the whole thing is weaker
  than it looks.

## What cannot happen

* **No tuning**, no fourth timeframe, no re-cut of the window.
* **No production change**, no API key, no order placement.
* **One run.** There is no v2 of this prereg, and a pass does not reopen the
  coherence verdict.
