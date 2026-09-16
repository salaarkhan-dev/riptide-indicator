# PRE-REGISTRATION — does the FVG gradient continue above 1h?

Committed before the first number. Run by
`indicators/ccp/studies/fvg_higher_tf.py`.

## The question, and why it is sharp

`research/FVG_WHY_1H.md` measured five arms with **physical structure size and
forward horizon both held constant**, varying only the bar interval:

```
A  Min60      pivot 3,  horizon 48 bars   gross +0.044   z +2.83
E  Min30 x2   pivot 6,  horizon 96 bars   gross +0.023   z +1.00
B  Min15 x4   pivot 12, horizon 192 bars  gross +0.008   z -0.75
```

Same 3 hours of structure, same 48-hour horizon, and the edge still falls as
the bars get finer. Two readings survive that, and they make **opposite
predictions above 1h**:

| | prediction for Hour4 and Hour8 |
|---|---|
| **The gradient is real** — something about slower bars carries the effect | gross R keeps rising past +0.044 |
| **A is the lucky cell** — one significant arm out of five, re-measured on overlapping data | no reason to continue; Hour4 and Hour8 scatter around zero |

That is a genuine fork, and no run so far has touched Hour4 or Hour8 at all.

    H: gross R for FVG grabs continues to rise with the bar interval above
       Min60.

## Design — identical in BAR terms, slower in wall-clock

Every arm uses **pivot 3, window 2, horizon 48 bars**, which is arm A's
configuration exactly. Only the bar interval changes.

That choice matters and is deliberate. Holding the horizon at 48 *hours* would
give Hour8 six bars to resolve in, and `FVG_WHY_1H` already showed a starved
bar-horizon is harmful — arm D was the worst on the table. Holding **48 bars**
keeps the horizon in the same proportion to the structure at every arm, which
is what the A/E/B comparison did and is the only way this extends that line
rather than starting a different one.

| arm | timeframe | structure | horizon |
|---|---|---|---|
| **anchor** | Min60 | 3h | 48h |
| **H4** | Hour4 | 12h | 8 days |
| **H8** | Hour8 | 24h | 16 days |

## Population

The **90 non-discovery symbols**, fetched at **1,200 days** so Hour8 has enough
bars to qualify at all — 333 days gives it under 1,000.

**Stated plainly: this window contains the discovery window.** For the anchor
that is contamination and the anchor is not a test, it is a pipeline check.
For H4 and H8 it does not matter, because **no Hour4 or Hour8 test has ever
been run on any window** — every bar of it is new to this question.

Everything else is imported unchanged: the FVG rule, the 0.25 ATR stop buffer,
the 2R target, `simulate_market`. Scored **gross** (`fee_pct=0.0`), because
`FVG_GROSS_EDGE` showed net R is partly a stop-width artefact and the question
here is about edge.

## Bars

1. **COVERAGE.** ≥ 300 FVG grabs and ≥ 300 days of window at both H4 and H8.
2. **BOTH POSITIVE.** Gross R > 0 at H4 and H8.
3. **THE GRADIENT CONTINUES.** The mean of H4 and H8 gross R ≥ the anchor's
   gross R **measured in this same run**, not the +0.044 quoted above. This is
   the hypothesis.
4. **GRAB-SPECIFIC.** Gross Δ beats the same filter on seeded random-bar
   entries, at both.
5. **SIGNIFICANCE.** Clustered |z| ≥ 2.0 on gross Δ at both.

Family size: **one hypothesis**, two timeframes that must both agree. Requiring
agreement is stricter than a single test, so there is nothing to correct for.

If a panel's MDE exceeds **0.15 R** it is **UNDERPOWERED** and reported as a
bound. H8 is the arm at risk — 1,200 days is only about 3,600 bars per symbol.

## My prediction

**Genuinely 50/50, and I am not going to manufacture a lean.**

For the gradient: it was measured with physical size and horizon controlled,
which is a real control, and three points in order is not nothing.

Against it: A is the only arm of five that ever cleared |z| = 2, it has been
re-measured four times on overlapping data, and the sequence has already
produced a result that looked this good — `CCP_CONTEXT_FILTERS` had three cells
at z above 2 that all died on the next half.

**What would move me most is H8.** It is the furthest extrapolation and the one
with least to do with anything already measured. If H8 is flat, the gradient
story is finished whatever H4 does.

## What cannot happen

* **No tuning**, no third timeframe, no re-cut of the window, no switch to a
  48-hour horizon if 48 bars disappoints.
* **No production change**, no API key, no order placement.
* **One run.** There is no v2, and a pass does not reopen outcome C — it would
  only mean the 1h cell has a mechanism worth a forward test.

## If it fails

Then the leading explanation for the whole FVG line is that the Min60 cell was
noise, re-measured on overlapping data until it looked solid. The three
pre-registered passes stand as recorded and the conclusion drawn from them does
not.
