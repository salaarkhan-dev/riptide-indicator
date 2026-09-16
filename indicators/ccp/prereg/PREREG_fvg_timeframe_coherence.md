# PRE-REGISTRATION — is the FVG result coherent across timeframes?

Committed before the first number. Run by
`indicators/ccp/studies/fvg_timeframe_coherence.py`.

## Why this runs before a forward test

`research/FVG_H1_TEMPORAL.md` has three pre-registered passes for FVG on
**Min60** grabs. One thing about it does not make sense: the discovery found
the same filter **negative** on Min15 (−0.094) and Min30 (−0.056) and positive
only on Min60. A real mechanism usually degrades smoothly across timeframes
rather than switching sign.

So this runs Min15 and Min30 **on the temporal window** — the 862 days that
end before the discovery window opens. It is deliberately designed to be able
to damage the result, and it costs hours rather than the weeks a forward run
needs.

**This is a coherence test, not a strict falsification, and calling it one
would be dishonest.** What it can do is tell the difference between a stable
odd result and an unstable one. The interpretations are fixed below, before
any number exists, because deciding afterwards what a mixed result "really
means" is how every one of these goes wrong.

## The three outcomes, and what each one means — decided now

| outcome | reading |
|---|---|
| **A** — Min15 and Min30 both **negative**, as in the discovery | The effect is genuinely timeframe-specific. Odd, unexplained, but **stable across regime and universe**, and the Min60 result stands. |
| **B** — Min15 and Min30 both **clearly positive** | FVG is a broad effect, not a 1h one. The discovery's negatives were noise, which means **the discovery was noisier than assumed** — but the Min60 result is not undermined, it is generalised. The story changes; the finding survives. |
| **C** — **mixed, or a sign flip against the discovery on the same timeframe** | The FVG result is timeframe- and regime-**unstable**. Treated as **not established**, no forward run, and `FVG_H1_TEMPORAL.md` gets a retraction paragraph. |

**C is the damaging outcome and it is the one I am looking for.** A result that
cannot hold its sign on adjacent timeframes across two windows is a result
about windows, not about markets.

## Population and method

* the **same 862-day temporal window** — fetch 1,200 days, keep only bars
  before the 333-day cutoff, drop any signal whose 48-hour horizon would cross
  it
* every listed symbol with 2,000+ bars before the cutoff, at each timeframe
* **Min15** (horizon 192 bars) and **Min30** (horizon 96 bars)
* the FVG rule, pivot width, stop buffer, target and scoring are **imported**
  from `indicators/ccp/studies/fvg_h1_holdout.py`, unchanged

**Min60 is re-run in the same pass as a pipeline anchor.** It is **not a test**
and gets no bar. If it does not reproduce approximately +0.046, the harness or
the refactor is broken and every number here is void — that is the only thing
the anchor is for.

## Bars

Two tests, one per timeframe. Family size **two**, stated: at z ≥ 2.0 each the
chance of at least one false positive is about 9%.

1. **COVERAGE.** ≥ 300 FVG grabs per timeframe, else that timeframe is not
   measurable.
2. **SIGN.** Reported against the discovery's sign on the same timeframe.
   Agreement supports outcome A; a clear reversal supports B or C per the table
   above.
3. **CONTROL.** Δ against the same filter on seeded random bars, reported for
   each timeframe, so a broad-market effect is distinguishable from a
   grab-specific one.

There is no "pass". This run does not decide whether anything is tradeable —
it decides whether the Min60 result is coherent enough to be worth a forward
test.

## My prediction

**Outcome A, roughly 3 chances in 5.** The discovery's Min15 and Min30
negatives were measured on only 23 symbols over 333 days, so they are not
strong evidence — but the Min60 effect has now survived two independent
holdouts, and an unstable artefact usually fails one of those first.

**Outcome C, about 1 in 5.** That is the one that would end this.

I was wrong about the cross-sectional holdout and wrong about the temporal one,
in the same direction both times. That is recorded here so a third wrong guess
is visible as a pattern rather than an isolated miss.

## What cannot happen

* **No tuning.** Same filter, same stop, same target, same pivot width.
* **No re-cut** of the window, no extra timeframe beyond these two.
* **No production change**, no API key, no order placement.
* **One run.** There is no v2 of this prereg.
