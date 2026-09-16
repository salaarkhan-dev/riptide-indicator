# FVG on 1h grabs — confirmatory holdout, 90 unseen symbols

Pre-registered in `PREREG_fvg_h1_holdout.md`, committed before the run.
Study: `indicators/ccp/studies/fvg_h1_holdout.py`, output alongside it.

## Verdict: CONFIRMED, on all five pre-registered bars

**I predicted this would fail bar 2. It did not, and the prediction is in the
prereg where it cannot be quietly dropped.**

```
84 symbols with 2000+ bars at Min60, none of them used by the discovery
38,138 grabs, unfiltered R -0.031 ± 0.007

  FVG grabs      n  6,911   R +0.031 ± 0.016
  no-FVG grabs   n 31,227   R -0.045
  Δ +0.076 ± 0.018   z +4.12
  control Δ, same filter on random bars   +0.017
```

| bar | | |
|---|---|---|
| 1 | 300+ FVG grabs | PASS (6,911) |
| 2 | positive standalone R after fees | PASS (+0.031) |
| 3 | beats grabs without an FVG | PASS (+0.076) |
| 4 | beats the same filter on random bars | PASS (+0.076 vs +0.017) |
| 5 | clustered \|z\| ≥ 2.0 | PASS (+4.12) |
| power | MDE 0.037 R | adequate |

**Family size was one.** One hypothesis, one timeframe, one arm, one
population, fixed before the data was fetched. There is no
multiple-comparison correction to argue about, which is the only reason this
result reads differently from the three cells in `CCP_CONTEXT_FILTERS.md` that
looked just as good and then died.

The robustness split came out the right way round, which it did not have to:

```
  more history   n 6,355   R +0.034 ± 0.017
  less history   n   556   R +0.002 ± 0.057
```

The effect lives in the **established** symbols. Had it been the other way, the
prereg's own rule was that the verdict becomes *not confirmed* — an edge that
exists only in the thinnest names is an artefact of a fixed fee assumption.

## What this is not

**The sorting is strong. The profitability is marginal.** Δ is +0.076 at
z +4.12 — the filter clearly separates grabs that pay from grabs that do not.
But the number that would be traded is **+0.031 ± 0.016**, which is t ≈ 1.9.
Bar 2 asked for "positive", and it is positive; it did not ask for
"significantly positive", and at 1.9 SE it would not have cleared that.

**Part of the effect is not about grabs.** The same filter applied to random
bars gives Δ +0.017. So of the +0.076, roughly **+0.059 is grab-specific** and
the rest is a fact about what follows an FVG anywhere.

**+0.031 R per bet is thin.** Fees are already netted, but the harness assumes
a fill at the level and a fixed fee. On 84 mostly-smaller perpetuals, slippage
is not a rounding error against an edge this size.

**The window is the same 333 days.** This is a *cross-sectional* holdout. Every
symbol in it traded the same period as the discovery, so a regime effect would
show up in both and look exactly like this. **That is the single biggest hole
left**, and it is the one thing this design cannot address.

**Timeframe-specificity is unexplained.** The discovery found FVG negative on
Min15 (−0.094) and Min30 (−0.056) and positive only on Min60. A real mechanism
usually degrades smoothly across timeframes rather than switching sign. No
explanation is offered here because none has been tested.

## What it earns

**A temporal holdout, next, and it is available without waiting.**
`research.deep` pages back much further than the 333 days used. Re-running this
exact test on days 334 and older, for the same symbols, tests the one thing the
cross-sectional holdout cannot: whether this survives a different regime.

If that passes too, then a forward-tracking run, and only after that does
anything get built. Still no signal, no alert, no line of production code —
`riptide/watch.py` set those terms and four studies' worth of nulls is not
undone by one confirmation, however clean.

## For the record

Four studies in this sequence found nothing:
`CCP_ENTRY_MODELS`, `CCP_EXIT_MODELS`, `CCP_FILTER_OVERFIT`,
`CCP_CONTEXT_FILTERS`. This is the fifth, it was pre-registered as a single
falsifiable test with a stated prediction against it, and it passed.

That is what the discipline is *for*. The same rules that killed the partial
exit at z −4.2, the mined filters at +0.089 → −0.082, and five of six context
filters, are the rules that make this one worth a second look.
