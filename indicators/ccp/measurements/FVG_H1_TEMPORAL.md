# FVG on 1h grabs — temporal holdout, 862 days before the discovery window

Pre-registered in `PREREG_fvg_h1_temporal.md`, committed before the run.
Study: `indicators/ccp/studies/fvg_h1_temporal.py`, output alongside it.

> **SUPERSEDED IN PART.** The timeframe coherence test that this file asked
> for came back **OUTCOME C — not established**; see
> `research/FVG_TIMEFRAME_COHERENCE.md`. The three passes below stand as
> recorded, and the line does **not** proceed to a forward run on them.

## Verdict: SURVIVES THE REGIME CHANGE

```
88 symbols with 2000+ Min60 bars before the cutoff
window 2023-06-06 to 2025-10-16   (862 days)
newest signal is 2.0 days before the discovery window opens — zero overlap

80,873 grabs, unfiltered R -0.048 ± 0.005

  FVG grabs      n 15,201   R +0.046 ± 0.011
  no-FVG grabs   n 65,672   R -0.070
  Δ +0.117 ± 0.013   z +9.19
  control Δ, same filter on random bars   +0.045
```

| bar | | |
|---|---|---|
| 1 | 300+ FVG grabs | PASS (15,201) |
| 2 | positive standalone R after fees | PASS (+0.046) |
| 3 | beats grabs without an FVG | PASS (+0.117) |
| 4 | beats the same filter on random bars | PASS (+0.117 vs +0.045) |
| 5 | clustered \|z\| ≥ 2.0 | PASS (+9.19) |
| power | MDE 0.025 R | adequate |

**The marginal number is no longer marginal.** The cross-sectional run gave
+0.031 ± 0.016, t ≈ 1.9 — positive but not significantly so, which this file's
prereg called a coin flip. Here it is **+0.046 ± 0.011, t ≈ 4.2**, on a window
that ends before the discovery window opens.

The prereg's most-likely outcome — bars 3, 4 and 5 passing while bar 2 failed —
did not happen. Bar 2 passed with room.

## Where the evidence now stands

| | population | period | result |
|---|---|---|---|
| discovery | 23 symbols | last 333d | +0.090 / +0.034 both halves |
| cross-sectional holdout | 84 **unseen** symbols | same 333d | +0.031, z +4.12 |
| temporal holdout | 88 symbols | **862d before** | +0.046, z +9.19 |

Three passes, each pre-registered with family size one, across a change of
universe and a change of regime. The two holdouts are not fully independent —
they share symbols — but their **periods are disjoint**, so the regime question
the second was built to answer is answered.

## What is still not established

**Roughly 38% of the effect is not about grabs.** The same filter on random
bars gives Δ +0.045 of the +0.117. That share grew from the cross-sectional run
(+0.017 of +0.076). So a meaningful part of this is *what follows an FVG
anywhere*, and only **+0.072** is grab-specific here.

**Slippage is not modelled.** Median risk at Min60 runs near 1.2% of price, so
an extra 0.02% of round-trip slippage costs about **0.017 R**. Against +0.046
that is a third of the edge, and on the thinner symbols it would be worse. The
harness assumes a fill at the level.

**Survivorship, stated in the prereg and not fixable.** The symbol list is what
the exchange lists today; anything delisted since 2023 is invisible. The older
window is biased toward assets that survived.

**Timeframe-specificity is still unexplained.** The discovery found FVG
negative on Min15 (−0.094) and Min30 (−0.056), positive only on Min60. A real
mechanism usually degrades smoothly rather than switching sign. **This is now
the most informative remaining test**, and it can only weaken the case: if
Min15 and Min30 are also negative on the older window, the odd picture is at
least consistent; if they turn positive there, the timeframe story was noise
and so, probably, is this.

## What it earns

Two things, in this order:

1. **A timeframe falsification run** — Min15 and Min30 on the temporal window,
   pre-registered with the prediction that both stay negative. Available now,
   no waiting, and designed to break the result rather than support it.
2. **A forward-tracking run.** Logging signals as they occur and judging them
   on data that does not exist yet is the only test nothing can leak into.

Still **no signal, no alert and no production code.** Three passes is the point
at which this becomes worth real work, not the point at which it becomes a
trade.
