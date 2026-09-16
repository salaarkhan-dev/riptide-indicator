# PRE-REGISTRATION v2 — inducement COUNT, not presence

Supersedes the covariate in `PREREG_inducement_on_riptide.md`. That file's
population, scoring, control and constraints are carried over unchanged; only
the covariate and the bars are redefined.

Written **after seeing v1's coverage and before computing any v2 number.**

## Why v1 needed replacing, and what was seen first

v1 asked a boolean: *was an inducement of type X taken in the 50 bars before
the raid?* A three-symbol smoke run answered it:

| definition | fires on |
|---|---|
| F_PIVOT (control) | >99% |
| D_RANGE | >99% |
| C_EQUAL | ~98% |
| E_GRAB | ~97% |

Four of the seven candidates have essentially no variance in the covariate, so
there is nothing to sort by. **This is my design error, not a property of the
definitions.** Riptide's raid *is* a pivot being taken — it sweeps a pool built
out of pivots — so "a pivot was taken recently" is very nearly a restatement of
"a Riptide setup exists."

**Disclosure.** That smoke run also printed deltas and z-scores on 255 bets
across 3 symbols. I saw them. They are not used to design anything here, and
the change below is driven only by the coverage column, which is a property of
the window and the definition and not of any outcome. Recording it because a
pre-registration that hides what the author had already seen is worth nothing.

## The corrected covariate

> **k** = the number of distinct take events of type X, on the side the raid
> swept, in the window `[anchor − W, anchor)` — **strictly before** the bar
> that took the pool.

Two changes, both corrections rather than choices:

1. **Count, not presence.** The SMC claim is a two-step — inducement first,
   then the pool. How many minor levels were cleared on the way in is the
   variable with information in it; whether at least one was is not.
2. **The window ends before the raid.** `anchor` is the bar of `sweep_time`,
   the bar that took the pool, and it is now excluded. The raid's own take is
   the thing Riptide trades, not an inducement to it. v1 counted it and that
   is most of why the control saturated.

`W = 50 = CFG.max_bars_after_grab` is unchanged and still not swept. Pivot
lengths, ATR factor, target, fees, horizon, symbols and timeframes are all
unchanged from v1.

## Primary metric

The OLS slope of a bet's R on `k` (capped at 3), per panel:

    R  =  a  +  β·min(k, 3)  +  ε

reported with β, its standard error and z, for each of the four panels — older
and newer half, Min30 and Min15. The bucket means for k = 0, 1, 2, 3+ are
printed alongside so non-linearity is visible rather than hidden inside a
slope.

A slope is used rather than strict monotonicity across buckets. With roughly
600 bets per bucket and R's spread near 1.3, a bucket mean carries an SE of
about 0.053 R, so requiring four buckets to order correctly in all four panels
would need a true step of ~0.15 R each — a spread of 0.45 R end to end. That
bar would be unreachable, and this project has already set one unreachable bar
(`t ≥ 3.0` in stage A) and had to retract it. Not twice.

## Pre-registered bars — all four

1. **COVARIATE SPREAD.** `k` takes at least three distinct values, each holding
   ≥ 5% of bets, in every panel. A definition whose k is almost always 0 or
   almost always saturated has nothing to regress on and fails here.
2. **SIGN STABILITY.** β keeps one sign in all four panels.
3. **BEATS THE CONTROL.** β_X exceeds β_F in the same direction in both halves.
4. **SIGNIFICANCE.** |z| = |β / SE| ≥ 2.0 on the pooled newer half.

### Power

Pooled newer half is roughly 5,600 bets. With `k` spread around SD ≈ 1 and R
around SD ≈ 1.3, SE(β) ≈ 1.3 / (1.0 · √5600) ≈ **0.017 R**, so bar 4 needs
|β| ≥ about **0.035 R per additional inducement cleared**.

That is a modest and reachable effect size. Stated before the run, as v1 did.

### Family-wise inflation

Still seven candidates. At |z| ≥ 2.0 alone the chance of at least one false
positive is about 28%. Bars 1–3 carry any pass; bar 4 alone does not.

## What cannot happen

Unchanged from v1, and repeated because it is the point:

* No production change; the frozen control test must still pass.
* No exchange API key, no order placement, no execution code.
* No parameter tuning. If a definition fails, it fails — it does not get a
  third window, a different cap on `k`, or a nicer ATR multiple. **There is no
  v3 of this covariate.** A further redesign after seeing v2's outcomes would
  be fitting the measurement to the answer, and the correct response to a
  second failure is to report that inducement does not sort Riptide's setups.
* No retrospective symbol or timeframe filtering.

## If nothing passes

Reported as: *no inducement definition sorts Riptide's setups.* The v2 Pine
structure layer may still be built, because reading structure by eye is a
legitimate reason to draw it — but it ships as context with no claim attached,
the panel says so, and it never becomes a filter on Riptide's alerts.
