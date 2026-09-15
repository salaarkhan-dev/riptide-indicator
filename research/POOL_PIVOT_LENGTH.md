# Does a longer pivot build better pools?

Prereg: `research/studies/PREREG_pool_pivot_length.md`, committed before the
run (`10c5db7`).

    python3 research/studies/pool_pivot_length.py

## Verdict: UNDERPOWERED. No claim either way.

The prereg's power escape hatch fired. That clause exists because an earlier
study on this repo set a 3.0 SE bar the sample could never have reached and
had to be retracted; this time the check ran before any interpretation.

```
     pivot  setups   bets   meanR/bet      SE   win%  med risk%
  -------------------------------------------------------------
    (1, 2)     256    256      -0.057   0.073   23.8       1.11
    (3, 3)     109    109      -0.027   0.109   22.0       1.02
    (5, 5)      44     44      +0.028   0.175   22.7       1.03
    (8, 8)      28     28      +0.125   0.240   28.6       1.18
  (10, 10)      28     28      +0.125   0.240   28.6       1.18
  (16, 16)      26     26      +0.134   0.259   30.8       1.07

  each arm MINUS the control (1, 2), on mean R per bet
     pivot      diff      SE  SE units  sym split  win split       verdict
  ------------------------------------------------------------------------
    (3, 3)    +0.030   0.131      +0.2    flipped    flipped         fails
    (5, 5)    +0.085   0.190      +0.4       held    flipped         fails
    (8, 8)    +0.182   0.251      +0.7    flipped       held         fails
  (10, 10)    +0.182   0.251      +0.7    flipped       held         fails
  (16, 16)    +0.191   0.269      +0.7    flipped    flipped         fails
```

**The bound is the result: this run could not have seen an effect smaller than
+0.81 R per bet.** That is an enormous effect. So the five "fails" above are
*not* evidence that pivot length does nothing — they are evidence that 46,000
bars cannot answer the question.

## What is nonetheless true in the table

**The direction is consistent and monotone.** Mean R per bet rises with pivot
length at every step, −0.057 → +0.134, and win rate rises with it, 23.8% →
30.8%. Five out of five arms point the same way.

That is worth exactly as much as its statistics, which is not much: the
largest difference is **+0.7 SE**, and the sign flips across the symbol split
on four of the five arms and across the window split on three. A monotone
trend built from five overlapping subsets of the same 256 control bets is what
a null looks like when the arms are nested — every wide-pivot bet is also, by
construction, a candidate at every narrower setting.

**Nothing is degenerate.** Median risk is 1.02%–1.18% in every arm, comfortably
above the 0.50% floor the prereg set from the Stage A failure. The wide arms
are not winning by hiding inside a stop the noise cannot reach.

**(8,8) and (10,10) are nearly the same experiment.** 27 of their 28 setups
are identical; the one that differs happens to score the same R, which is why
their rows match to three decimals. That is not a bug — the raw pivot counts do
separate (BTC 15m: 164 pivots at 8/8, 135 at 10/10, 89 at 16/16) — it is the
sample being too thin for the arms to come apart. It is the clearest single
sign that this run is underpowered.

## The cost, which is not in doubt

Setups collapse **256 → 26**, a 90% reduction, for a difference that cannot be
measured. One setup per ~1,640 bars, or roughly one per symbol per three weeks
at 15m.

That trade is the honest headline. Whatever a wide pivot does to quality, it
unambiguously does *this* to quantity, and the quantity number needs no
statistics.

## What would settle it

SE has to fall by 0.81/0.50 = 1.61×, so the sample has to grow by **2.6×** —
about 5,200 bars per symbol at 15m, roughly 54 days against the 20.8 days used
here. That is reachable by raising `RIPTIDE_LOOKBACK`, and it is deliberately
**not** done in this file: 2,000 bars was preregistered, and re-running with
more data and reporting that as the preregistered study is the exact move the
prereg discipline exists to prevent. It needs its own prereg.

## What this does and does not license

It does not license adding anything. There is no measured benefit here, only
an unmeasurable one.

If a second wide-pivot pool set goes into `riptide-indicator-v2.pine`, it goes
in the way everything else from that audit goes in: **behind its own toggle,
off by default, in its own colour, as context, with no performance claim** —
and this file is the reason there is no performance claim to make.

It does **not** license moving `pivot_left` / `pivot_right`. Those are
parity-locked by `deploy/check-parity.py`; moving them moves every alert the
bot sends, on the strength of +0.7 SE.

## Relationship to the higher-timeframe question

This study was run because "the big grab is useful" is most simply explained
by pivot length, not by timeframe: mickes' `_bigGrabsTimeframe` defaults to
`""`, the chart timeframe, so a big grab on a 15m chart is a 15m pivot of
10/10 unless that input was changed.

The separate, genuinely-higher-timeframe question already has one measured
answer on this repo, recorded in `riptide-indicator-v2.pine` itself: **weekly
liquidity produced 295 raids and zero setups in 41.6 days**, which is why
`useWeeklyLiq` ships off. Daily is on; session is chart-only because
`riptide/engine.py` has no session source.

So of the higher-timeframe sources Riptide already has, the one that was
measured produced nothing, and the one thing that is cheap to try instead —
a wider pivot on the chart timeframe — comes back at +0.7 SE on a sample that
cannot resolve it.
