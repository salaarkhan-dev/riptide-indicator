# Does any inducement definition sort Riptide's setups?

**No.** Seven definitions, two pre-registered designs, 6,663 bets across 28
symbols and 333 days. Not one of them clears the bars, and not one of them even
keeps its sign across the four panels.

Pre-registrations: `PREREG_inducement_on_riptide.md` (v1) and
`PREREG_inducement_on_riptide_v2.md` (v2), both committed before their runs.
Studies: `research/studies/inducement_on_riptide.py` and `..._v2.py`, outputs
alongside them.

---

## What was measured

Riptide's own confirmed setups, with Riptide's real limit entry at the fair
value gap, its real stop beyond the raid extreme, a 2R target, its fee model, a
5-hour fill window and a 48-hour horizon. Unit of evidence is the **bet** — one
per `sweep_time` — and an unfilled limit scores 0.0 R and stays in the sample,
because the inducement is known before the fill.

Against that, seven candidate answers to *"was there an inducement before the
raid?"*:

| id | definition | source |
|---|---|---|
| **F** | **the control** — the most recent plain swing pivot, taken | none; this is the null |
| A1 | LIT-IDM on Main structure | `lit_v3` |
| A2 | LIT-IDM on Internal structure | `lit_v3` |
| B | first pullback after a structure break | "Liquidity & inducements" |
| C | equal highs/lows within 0.5 ATR | "Liquidity & inducements" |
| D | a pivot inside the running structure range | "Inducement Engine" |
| E | a grab — wicked through, closed back inside | "Liquidity & inducements" |

---

## v1 failed on its own design, and the control is why

v1 asked a boolean: *was an inducement taken in the 50 bars before the raid?*

| definition | fires on |
|---|---|
| F_PIVOT (control) | **>99%** |
| D_RANGE | **>99%** |
| C_EQUAL | ~98% |
| E_GRAB | ~98% |

The control has no variance. **Riptide's raid *is* a pivot being taken** — it
sweeps a pool built out of pivots — so "a pivot was taken recently" nearly
restates "a Riptide setup exists". That is my design error, not a property of
the definitions.

Every v1 candidate came back INCONCLUSIVE. One correction to that run's own
output: it printed **yes** under "beats the control" for six definitions, which
was vacuous — the control could not be computed at all, and the check silently
skipped. Bar 3 was not evaluated in v1. It is in v2.

---

## v2: count, not presence

The covariate became **k = how many distinct takes happened in the 50 bars
strictly before the bar that took the pool**, and the metric the OLS slope of a
bet's R on `min(k, 3)`.

### The four panels

β per panel, with z underneath:

| definition | Min30 older | Min30 newer | Min15 older | Min15 newer | pooled newer z |
|---|---|---|---|---|---|
| **F_PIVOT** | −0.119 (−2.26) | +0.006 (0.10) | +0.010 (0.26) | −0.063 (−1.50) | −1.16 |
| A1_LIT_MAIN | +0.010 (0.07) | +0.130 (0.60) | −0.174 (−1.32) | +0.124 (0.97) | 1.09 |
| A2_LIT_INT | −0.031 (−0.39) | +0.080 (0.73) | −0.053 (−0.70) | +0.114 (1.43) | 1.58 |
| B_RETRACE | −0.075 (−0.89) | −0.070 (−0.77) | +0.059 (0.79) | +0.153 (1.91) | 1.04 |
| C_EQUAL | −0.055 (−1.86) | −0.028 (−0.90) | +0.011 (0.44) | −0.009 (−0.36) | −0.73 |
| D_RANGE | −0.144 (−2.03) | +0.018 (0.24) | +0.015 (0.30) | −0.077 (−1.56) | −1.16 |
| E_GRAB | −0.005 (−0.13) | −0.010 (−0.27) | +0.008 (0.26) | +0.002 (0.07) | −0.05 |

**Every row changes sign.** Not one definition is even consistently pointing in
one direction, let alone significantly.

### Why it fails, definition by definition

Two distinct failure modes, and they split the candidates cleanly:

**The structural ones almost never fire.** `k = 0` on

* A1 (LIT Main): **95%** of Min30 bets, **96%** of Min15
* A2 (LIT Internal): **87%** / **90%**
* B (retracement): **87%** / **88%**

LIT's IDM is a rare event — tens per symbol-year — and Riptide produces roughly
100 setups per symbol-year. They simply do not coincide often enough for one to
say anything about the other. These three fail bar 1 on covariate spread, which
is the bar existing to catch exactly this.

**The loose ones saturate.** `k ≥ 3` on 78% (F) and 92% (D) of Min30 bets. At
that point the covariate is close to constant again.

Only C and E have real spread across all four buckets, and both are flat: E's
largest |β| anywhere is 0.010, with z never exceeding 0.27.

### The two "significant" cells, and why the four-panel bar exists

`F_PIVOT` on Min30-older reaches **z = −2.26** and `D_RANGE` **z = −2.03**.
Taken alone, either is a publishable-looking result: *the more minor levels
price clears on the way in, the worse the setup.*

In the newer half of the same timeframe, F is **+0.006 at z = 0.10** and D is
**+0.018 at z = 0.24**. The effect is gone, and its sign with it. With seven
candidates across four panels there are 28 cells, so two at |z| ≈ 2 is roughly
what noise delivers.

### The one real pattern in the table is not about inducement

A1, A2 and B all have β **negative in both older halves and positive in both
newer halves**. Three different definitions, the same flip, at the same time.
That is a property of the second half of the window — a regime — not of
inducement. It is also exactly what would be mistaken for a working filter by
anyone who tested on recent data only.

---

## Deviations from the pre-registrations, disclosed

1. **28 symbols, not 40.** `RP.DISCOVERY` holds 30 symbols, so `[:40]` yielded
   30, and 28 had ≥3,000 bars on both timeframes. The prereg said 40. The
   universe was not changed after the fact — it was smaller than I recorded.
2. **6,663 bets, not ~11,200**, following from (1). Pooled newer half is 3,187,
   so SE(β) came in near 0.03 rather than the predicted 0.017, and bar 4 needed
   |β| ≈ 0.06 rather than 0.035. The largest |β| observed in any pooled test
   was well short of that, and no candidate keeps a sign, so the shortfall in
   power does not change any verdict — but the bar was harder than advertised
   and that is worth stating.
3. **A smoke run was seen before v2 was designed.** Recorded in the v2 prereg.
   Only the coverage column drove the redesign.

---

## What this does and does not say

**It says:** knowing whether, or how many, minor levels were taken before a
Riptide raid tells you nothing useful about what that setup will pay. Under any
of the four published definitions of inducement now on the table, and under the
plain-pivot null as well.

**It does not say** inducement is meaningless as a concept, or that these
indicators are wrong about their own charts. It says the concept does not sort
*this* strategy's setups — which is the only question that bears on whether to
draw it on *this* indicator.

**It does not test** inducement as a standalone entry. That would be a
different study with a different population, and given that three
pre-registered LIT stages already returned INCONCLUSIVE on the closest version
of that question, it is not an obvious next move.

Per the v2 prereg there is no v3 of this covariate. A third redesign after two
failures would be fitting the measurement to the answer.

---

## Consequence for the Riptide v2 structure layer

The pre-registration committed to this in advance, so:

> Structure, BOS, CHoCH and IDM may still be drawn on the Riptide indicator,
> because reading structure by eye is a legitimate reason to draw something.
> It ships as **context with no claim attached**, the panel says so, and it
> does not become a filter on Riptide's alerts.

Two things follow for the build itself:

* **Draw Internal, not Main.** Main latches on 14% of Min30 symbols including
  BTC (`research/studies/lit_main_latch.py`), and A1's 95% zero-rate above is
  partly that defect showing through.
* **No performance claim anywhere in the layer** — no win rate attached to
  IDM, no "high-probability" labelling, no implication that a setup with an
  inducement behind it is better. This document is why.
