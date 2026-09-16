# PRE-REGISTRATION — which inducement definition, if any, sorts Riptide's setups

Written and committed **before the first number**. Run by
`research/studies/inducement_on_riptide.py`.

## The decision this is for

Whether to render market structure, BOS, CHoCH and IDM on the Riptide
indicator as a v2 layer — and if so, **which** definition of inducement, since
four different ones are now on the table from three different indicators.

Rendering a level that does not sort Riptide's own setups is decoration. This
measures whether any of them does, before any Pine is written.

## The question

> For a Riptide setup, does it matter whether an inducement was taken before
> the raid?

Not "is this IDM definition prettier". Riptide already has an entry, a stop and
a target that ship. The only thing an inducement can add is **sorting**: it
either separates Riptide's bets into better and worse, or it does not.

## Population

Every confirmed setup from `run_engine(sym, cs, CFG)` — Riptide's real engine,
its real limit entry at the fair value gap, its real stop beyond the raid
extreme — scored by `research.harness.simulate` at `target_r = 2.0` with
Riptide's fee model, a 5-hour fill window and a 48-hour horizon.

* 333-day deep window, Min30 and Min15
* 40 symbols
* **Unit of evidence is the BET**, one per `sweep_time`. Several setups off one
  raid are one observation, averaged.
* An unfilled limit scores **0.0 R, not a loss**, and stays in the sample. The
  inducement is known before the fill, so if it changes the fill rate that is
  part of its effect and must not be hidden by conditioning on fills.

## The covariate

For each bet and each definition X:

> Was an inducement of type X, **on the side the raid swept**, taken within
> `W` bars ending at the raid bar?

* Long setup (Riptide swept a low pool) → the inducement is a **LOW**.
* Short setup → a **HIGH**.
* `W = 50 = CFG.max_bars_after_grab`, Riptide's own grab-to-shift window.
  **Fixed a priori from shipped config. It is not swept and will not be.**

Every definition that needs a pivot uses Riptide's own `pivot_left = 1,
pivot_right = 2`, so the comparison is between *definitions* and not between
pivot sensitivities. The one exception is A, which owns its pivot semantics by
construction.

## The candidates

| id | name | rule |
|---|---|---|
| **F** | **PIVOT — the control** | the most recent confirmed swing on the matching side, taken inside the window. No structure, no cleverness. |
| A1 | LIT-IDM (Main) | an `idm_break` event from `lit_v3.engine`, Main depth, matching direction |
| A2 | LIT-IDM (Internal) | the same, Internal depth |
| B | RETRACE-IDM | first pivot after a structure break whose predecessor predates that break; taken when price trades through |
| C | EQUAL-IDM | two same-side pivots within `0.5 × ATR(14)` with no wick through the line joining them; taken when price trades through |
| D | RANGE-IDM | a pivot strictly inside the running structure range; pending until price trades through |
| E | GRAB | a pivot wicked through and closed back inside |

B and D need a structure-break source. They use LIT **Internal**, not Main,
because Main latches on 14% of Min30 symbols including BTC
(`research/studies/lit_main_latch.py`) and Internal is what is actually being
traded. Stated here so it cannot be presented later as a choice made after
seeing results.

**F is the point of the exercise.** Every one of A–E will correlate with "there
was a pullback before the raid", and so will F. If none of them beats F, then
*inducement* is vocabulary on top of *a pivot got taken*, and the honest v2
layer draws pivots.

## Primary metric

For each definition X, across the same bets:

    Δ_X = mean R | X fired  −  mean R | X did not

reported with n on each side, both means, SE of the difference and z.

## Pre-registered bars — all four, or it fails

1. **COVERAGE.** X fires on between **15% and 85%** of bets. Outside that band
   it is relabelling the sample, not sorting it.
2. **SIGN STABILITY.** Δ keeps one sign in **all four panels** — older half and
   newer half, Min30 and Min15.
3. **BEATS THE NULL.** Δ_X > Δ_F in **both halves**.
4. **SIGNIFICANCE.** z ≥ 2.0 on the pooled newer half.

### Why four bars and not just the fourth

Seven candidates are being tested. At z ≥ 2.0 alone the family-wise chance of
at least one false positive is about **28%** — so passing condition 4 on its
own is close to meaningless, and the three structural conditions are what carry
the result. This is stated now, at the front, because a z-score quoted later
without it would be misleading.

### Power

~100 bets per symbol on Min30 and ~180 on Min15 over 333 days; 40 symbols gives
roughly 4,000 and 7,200 bets. With R's spread around 1.3 and a near-even split,
SE of the difference is about 0.041 R on Min30, so z ≥ 2.0 needs Δ ≥ ~0.08 R.

That is a real and reachable effect size. Recorded here because a previous
pre-registration in this project set a bar (`t ≥ 3.0`) that the sample could
not have cleared, and that must not happen twice.

## What cannot happen

* **No production change.** Nothing in `riptide/` is modified. The frozen
  control test must still pass.
* **No exchange API key, no order placement, no execution code.** Unchanged
  standing constraint.
* **No parameter tuning.** `W`, the pivot lengths, the ATR factor and the
  target are all fixed above from shipped config. If a definition fails, it
  fails — it does not get a second window or a nicer ATR multiple.
* **No retrospective symbol or timeframe filtering.** The 40 symbols and the
  two timeframes are fixed before the run.
* **Latched symbol-timeframes are not dropped.** Where LIT Main is dead, A1
  simply does not fire, and that counts against A1's coverage. That is the
  honest accounting: a definition that cannot be computed is a definition that
  cannot be used.

## If nothing passes

Then the answer is *no inducement definition sorts Riptide's setups*, and it
gets reported that way. The v2 structure layer may still be built — reading
structure by eye is a legitimate reason to draw it — but it ships as **context
with no claim attached**, and nothing in the panel may imply it improves
anything.

A definition that passes earns exactly one thing: the right to be the one
rendered. It does not become a filter on Riptide's alerts without its own
forward test.
