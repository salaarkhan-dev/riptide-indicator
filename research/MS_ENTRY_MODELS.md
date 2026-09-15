# Entry models on the market-structure engine

Pre-registered in `PREREG_ms_entry_models.md`, committed before the run.
Studies: `research/studies/ms_entry_models.py` and `ms_entry_diag.py`, outputs
alongside them.

## Verdict

**Nothing passes. The one model the study's own verdict column marks PASSES is
an artefact of my grouping, and I am not accepting it.**

Two of the five models were not measurable at all. Two were measured cleanly
and came back flat or negative. The fifth "won" by definition.

## The engine measured

`research/ms_struct.py` — a transcription of section 12 of
`riptide-indicator-v2.pine`, checked statement-by-statement against the Pine by
`deploy/ms-py-parity.py` (**every logic statement pairs**, and the checker
catches a planted dropped-guard). 28 symbols, Min30 and Min15, 333 days, four
panels.

## Results

Paired difference against a random entry in the same cycle, same direction,
same stop rule — so the only difference is *when* it entered.

| model | Δ Min30 old | Δ Min30 new | Δ Min15 old | Δ Min15 new | pooled z | verdict |
|---|---|---|---|---|---|---|
| E1 IDM | −1.111 | −1.287 | −1.931 | −1.756 | −11.35 | unmeasurable — see below |
| E2 BOS | +0.151 | −0.080 | +0.054 | +0.042 | −0.17 | **INCONCLUSIVE** |
| E3 CHoCH | +0.561 | +0.317 | +0.569 | +0.492 | +9.90 | **artefact — see below** |
| E4 SWEEP | — | −0.743 | — | — | −4.39 | unmeasurable — see below |
| E5 IDM→BOS | identical to E2 | | | | | see below |

**Every model, and the control, is negative in standalone R.** The random
control scores −0.25 to −0.59 R per bet; the best model reaches about −0.09.
On this engine, with this stop and a 2R target, nothing makes money. That is
the first thing to say and it does not depend on any of the subtleties below.

## Why E1 and E4 are not measurable

The prereg held one stop rule constant: the live short-period opposing swing.
Constant in *definition*. Not constant in *effect*:

| model | median risk, % of price | p25 | p75 |
|---|---|---|---|
| **E1 IDM** | **0.16** | 0.07 | 0.32 |
| **E4 SWEEP** | **0.20** | 0.09 | 0.44 |
| E2 BOS | 2.37 | 1.51 | 3.80 |
| E3 CHoCH | 2.21 | 1.38 | 3.48 |
| E5 IDM→BOS | 2.37 | 1.51 | 3.80 |

Stage A of the LIT work died at a **0.42%** median stop. E1 and E4 are at 0.16%
and 0.20% — *tighter than the failure that ended that stage*. Their triggers
fire when price is touching the level the stop sits on, so risk is adjacent to
entry by construction, and their −1.6 to −2.5 R per bet is gap losses past a
stop too tight to survive. It says nothing about whether the trigger has
information in it.

That is a defect in my pre-registration, not a finding about IDM entries.

## Why E3's pass is circular

The bet is grouped **by CHoCH cycle**, and E3 enters at bar 0 of its own cycle
**by definition**. The control enters at a random later bar. So the comparison
is only meaningful if position within a cycle is neutral. It is not:

| position in cycle | 0.0 | 0.2 | 0.4 | 0.6 | 0.8 | 0.9 |
|---|---|---|---|---|---|---|
| control's mean R | −0.250 | −0.503 | −0.543 | −0.467 | −0.893 | −1.204 |

    first 30% of a cycle   −0.340 R
    last  30% of a cycle   −0.975 R
    gap                    +0.636 R

E3's measured advantage is +0.32 to +0.57 R. **The positional gap is +0.64 R.**
It accounts for the entire effect, and E3 sits at position 0.0 by construction
because the cycle is defined by the CHoCH that triggers it.

The thing being tested defines the window it is tested in. z = 9.90 is what a
definitional advantage looks like, not an edge. Bars 1–4 all pass and the
result is still worthless — which is why a verdict column is not a substitute
for reading the design.

## E2 and E5 are the same model, and the engine says so

They are identical in every panel — same bet count, same R, same delta. The
engine's BOS condition is:

```python
if gt(cl, msMax) and msSBtmCrossed and msOs == 1:
```

`msSBtmCrossed` is set only by an IDM. **A BOS cannot fire unless an inducement
was taken first**, so the "IDM then BOS" two-step is already built into the
engine and E5 was never a separate model. My mistake in specifying it;
a genuine and useful fact about the engine.

That leaves **E2/E5 as the only cleanly measured model**, and it is flat:
+0.151, −0.080, +0.054, +0.042, pooled z = −0.17. It fails sign stability and
it fails significance.

## Corrections made during the run, disclosed

The first run reported E4 as `unpaired` on every panel, because the control
only ever existed in the cycle's own direction and E4 fires *against* the
trend. That was a defect in the specification — it made a listed model
unmeasurable for a reason unrelated to the model — so the control now draws one
random bar per direction. Corrected rather than reported, and E4 still fails.

## What this changes for the Pine

`riptide-indicator-v2.pine` already ships the structure layer as **context with
no claim attached**, and that was the right call before this study and remains
the right call after it. Nothing here earns a signal layer.

Per the prereg: *"If nothing passes, the structure layer stays what it already
is."* It does.

## What would be worth testing next, and what would not

**Not worth testing:** another stop rule for E1 and E4 to rescue them. The
prereg forbids it, and more importantly a trigger that only works with a stop
chosen after seeing it fail is a fitted result.

**Worth testing, as its own pre-registration:** the positional finding is the
most interesting number here and it was not what was being looked for. Entering
early in a structure cycle beats entering late by 0.64 R, monotonically across
deciles, on 3,000+ observations. That is a property of the cycle definition
rather than of any trigger — but it is large, it replicates across both
timeframes, and nothing in this project has measured it directly. It would need
its own control, because "early in a window defined by a breakout" is exactly
the kind of thing that can be circular twice over.
