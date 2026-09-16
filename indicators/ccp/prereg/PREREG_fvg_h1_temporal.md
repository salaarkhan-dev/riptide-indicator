# PRE-REGISTRATION — does the FVG/1h result survive a different regime?

Committed before the first number. Run by
`indicators/ccp/studies/fvg_h1_temporal.py`.

## The single hypothesis, unchanged

`research/FVG_H1_HOLDOUT.md` confirmed, on 84 symbols the discovery never
touched, that **Min60 grabs with an unfilled directional FVG pay and grabs
without one do not**:

```
38,138 grabs   FVG n 6,911  R +0.031 ± 0.016
               Δ +0.076 ± 0.018   z +4.12   control Δ +0.017
```

That test had one hole its design could not close, and this file exists only to
close it. **Every symbol in it traded the same 333 days as the discovery.** A
regime effect — one market condition that persisted across that window and
happened to reward this shape — would appear in both and look exactly like a
confirmation.

    H: on Min60, grabs with an unfilled directional FVG have positive
       net R after fees, and beat grabs without one,
       IN A WINDOW THAT ENDS BEFORE THE DISCOVERY WINDOW BEGINS.

## Population — strictly older data

Every listed symbol with enough history. `research.deep` pages back far beyond
the 333 days used so far, so this fetches **1,200 days** and then keeps only
bars **older than the 333-day cutoff**.

**Zero overlap, enforced twice.** Candles at or after the cutoff are discarded
before anything is scored, and a signal is additionally dropped unless its
whole 48-hour horizon also falls before the cutoff. A trade that opens before
the cutoff and resolves after it would be scored partly on discovery data.

A symbol is kept if it has at least 2,000 bars before the cutoff. The count is
reported; nothing is dropped for any other reason and nothing is dropped after
its result is seen.

**Survivorship is real here and is not fixable.** The symbol list is what the
exchange lists *today*, so anything delisted in the interim is invisible. That
biases the older window toward assets that survived. It is stated here rather
than discovered later, and it is a reason a pass is not proof.

## Held constant — everything

The FVG rule, the pivot width, the stop buffer, the target, the horizon and the
scoring all come from `indicators/ccp/studies/fvg_h1_holdout.py` **by import**, so
this cannot test a subtly different filter than the one that was confirmed.

**No parameter is tuned. Not one.**

## Bars — the same five

1. **COVERAGE.** ≥ 300 FVG grabs, else not measurable.
2. **MAKES MONEY.** Standalone net R > 0 after fees.
3. **BEATS UNFILTERED.** Δ > 0.
4. **IT IS ABOUT GRABS.** Δ exceeds the same filter's Δ on seeded random-bar
   entries with matched direction and risk fraction.
5. **SIGNIFICANCE.** Clustered |z| ≥ 2.0 on Δ.

**Family size is ONE.** Same hypothesis, same filter, same timeframe, one new
population. No correction to argue about.

If the realised MDE exceeds **0.15 R** the run is **UNDERPOWERED** and reported
as a bound.

## My prediction, calibrated rather than contrarian

I predicted the cross-sectional holdout would fail and it did not. Repeating a
pessimistic guess to look rigorous would be its own kind of dishonesty, so:

* **Bar 3 (Δ > 0): I expect it to pass, roughly 2 chances in 3.** A z of +4.12
  on 38,138 independent-ish grabs is not the sort of number that usually comes
  from nothing, and the effect survived a change of universe.
* **Bar 2 (standalone R > 0): genuinely a coin flip.** The confirmed number was
  +0.031 ± 0.016, t ≈ 1.9. An effect that marginal does not need much regime
  drift to land the other side of zero.

**The outcome I consider most likely overall is bars 3, 4 and 5 passing while
bar 2 fails.** If that happens the honest reading is narrow and worth saying
now, before it can be spun: *the filter sorts grabs reliably, and the subset it
selects still does not pay after costs.* That is a real finding and it is not
tradeable.

## What cannot happen

* **No tuning, no second arm, no second timeframe, no re-cut of the window.**
  If 1,200 days fails, 900 days does not get a turn.
* **No production change.** Nothing under `riptide/`;
  `tests/test_control_frozen.py` must still pass.
* **No exchange API key, no order placement.**
* **One run.** There is no v2 of this prereg.

## If it passes

Then the result has survived a change of universe and a change of regime, and
it earns a **forward-tracking run** — logging signals as they occur, scored by
the same rules, judged later on data that does not exist yet. That is the last
test available and the only one nothing can leak into.

Still no signal, no alert and no production code until that returns.

## If it fails

Then `FVG_H1_HOLDOUT.md` gets a paragraph saying the confirmation did not
survive a regime change, the cross-sectional pass is recorded as most likely a
property of the 2024–25 window, and the grab layer stays context.
