# Why only 1h? Not the horizon. Possibly not anything.

`research/studies/fvg_why_1h.py`. **Exploratory — no prereg, no verdict.**
90 non-discovery symbols, 333 days, gross R throughout.

## The five arms

```
arm tf     pivot win horiz  n FVG  gross R     SE       Δ      z  risk%
A   Min60      3   2    48   6835   +0.044  0.016  +0.052  +2.83   1.72
E   Min30      6   4    96  10099   +0.023  0.014  +0.017  +1.00   1.40
B   Min15     12   8   192  14246   +0.008  0.012  -0.011  -0.75   1.21
C   Min15      3   2   192  29713   +0.003  0.009  -0.018  -1.80   0.77
D   Min15      3   2    48  29713   -0.007  0.008  -0.026  -2.97   0.77
```

A reproduces `FVG_GROSS_EDGE`'s +0.045 on an independently re-fetched
universe, so the baseline is sound.

## What is ruled out

**The forward horizon is not the mechanism.** Arm D gave Min15 the same 48-bar
horizon as A and it is the **worst** arm on the table, with a significantly
negative Δ of −0.026 at z −2.97. Shortening the horizon made the FVG filter
actively harmful. That hypothesis is dead.

## What is suggested, weakly

**There is a monotone gradient, and scaling moves arms the right way.**
Ordering by gross R: A +0.044 > E +0.023 > B +0.008 > C +0.003 > D −0.007.
Both scaled arms improved on their native versions — Min30 went from −0.000
(gross-edge study) to **+0.023** when its structure was doubled, and Min15 from
+0.003 to **+0.008** when quadrupled. The direction the physical-size
hypothesis predicts.

**But scaling does not close the gap.** B, given exactly A's physical structure
size, returns +0.008 against A's +0.044 — a fifth of it. If physical size were
the whole story, B should equal A. It does not.

## A correction to this study's own output

The first printout labelled B and E as **"matches A"** because the gap fell
inside two standard errors. **That was the wrong word and I have changed it.**
SE on the gap is about 0.020, so a point estimate five times smaller than A's
still fails to reach significance. That is the comparison being **underpowered**,
not the arms agreeing. It now prints "cannot distinguish" with the MDE beside
it.

This matters because "B matches A" would have read as support for the physical
size story, and the data does not support it — it is merely unable to refute it.

## The hypothesis I cannot rule out, and should not dodge

**A may be the lucky cell.** It is the only arm of five with |z| > 2. It is the
same cell that has now been measured four times, and — this is the part worth
being blunt about — **arms A here and the Min60 cell in `FVG_GROSS_EDGE` are
the same symbols over the same 333 days.** This run is not independent evidence
for A. It re-measures it.

Against that: A did pass two genuinely independent pre-registered holdouts
(84 unseen symbols, 862 prior days), both on net R. For it, the gradient across
E → B → C is at least ordered the way a real slow-structure effect would be.

## The test that would separate them

**Extend the gradient upward: Hour4 and Hour8, native settings.**

* If the mechanism is real and about slow structure, gross R should keep rising
  past A's +0.044.
* If A is a lucky cell, the higher timeframes have no reason to continue the
  pattern and will scatter around zero.

That is a sharp, cheap, falsifiable prediction on data never used for this
question, and it needs its own prereg with the direction stated in advance.
It is the obvious next step and it is the one I would run.

## Status

Unchanged: outcome C stands, no forward run, no signal, no alert, no production
code. What this adds is that the **horizon explanation is dead**, the physical
size explanation is **unsupported but not refuted**, and the honest leading
alternative is that the 1h cell is noise that has been re-measured on
overlapping data.
