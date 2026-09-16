# Order blocks, FVGs and trend filters on grabs

Pre-registered in `PREREG_ccp_context_filters.md`, committed before the run.
Study: `research/studies/ccp_context_filters.py`, output alongside it.

## Verdict

**All six arms fail.** Not one produces a positive standalone R on the newer
half of all three timeframes, which is bar 4 and the bar that decides whether
anything is tradeable.

The prediction recorded in the prereg was "all six fail bar 4", including the
specific claim that the trend filters would die on bar 6 — helping a random
entry as much as a grab. Both held.

## The trend arms did what trend filters do, to everything

`F3` is EMA 50/200 agreement. On the newer half, compare what it does to grabs
against what the same filter does to seeded random entries:

| newer half | Δ at grabs | Δ at random bars |
|---|---|---|
| Min15 | +0.007 | **+0.031** |
| Min30 | −0.019 | **+0.060** |
| Min60 | −0.023 | **+0.014** |

**The EMA filter helps a random entry more than it helps a grab, in all three
panels.** That is bar 6 failing in the cleanest possible way: the filter knows
something about the market and nothing about this setup. `F4` (ADX) and `F5`
(Supertrend) behave the same way.

This is also why bar 6 exists. Without it, F3's older-half Min15 number —
**Δ +0.069 at z +2.97** — reads like a discovery. Its newer half is **+0.007**,
and its control does better than it does.

## Non-replication, again

| arm | older half | newer half |
|---|---|---|
| F3 Min15 | Δ +0.069, z +2.97 | Δ +0.007, z +0.30 |
| F2 Min15 | Δ +0.059, z +2.23 | Δ −0.005, z −0.20 |
| F6 Min15 | R +0.013, Δ +0.095 | R −0.083, Δ +0.007 |

Three cells that would have been quoted as findings, none of which survives the
next half. With 36 panel-level cells, this is what the family-wise warning in
the prereg was describing in advance.

## The one result that is not noise-shaped

**F2, the FVG arm, on Min60 alone, is positive in BOTH halves:**

```
Min60 OLD   n 891   R +0.090   Δ +0.108  z +2.07   control Δ +0.020
Min60 NEW   n 926   R +0.034   Δ +0.127  z +2.53   control Δ -0.045
```

Positive standalone R after fees in both halves. Δ positive in both, with the
larger z in the *newer* one. On the newer half it beats its own random-bar
control, which is the bar designed to catch a filter that is really about the
market. In four studies this is the only cell that has done all of that.

**It still fails, and the reasons are not formalities.**

* Bars 3 and 4 require all three timeframes. On Min15 and Min30 the same
  filter gives −0.094 and −0.056 standalone. "It works on 1h" is a claim about
  one timeframe made after looking at three.
* The run flags it **UNDERPOWERED** at Min60: MDE 0.10 R against an effect of
  0.11–0.13 R, so the panel can barely resolve what it is reporting.
* It is one arm of six across three timeframes. The prereg put the chance of at
  least one false positive at z ≥ 2 at roughly 26% for the six primary tests,
  and this cell is not even one of those six — it is a sub-panel.

## What this earns, and what it does not

It does not earn a signal, an alert, or a line of production code. It earns
**one thing**: a forward-tracking run on Min60 FVG grabs, because the only
honest test left is data this study has not seen. All 333 days are spent. A
second pass over the same window would be confirming a hypothesis with the
observations that generated it, which is the mistake
`research/CCP_FILTER_OVERFIT.md` measured at +0.089 → −0.082.

The remaining five arms are finished. Order blocks, EMA trend, ADX regime and
Supertrend do not sort grabs, and the trend family does not because it is not
about grabs at all.

## Where this leaves the grab layer

Four studies now, all saying the same thing four ways:

| | finding |
|---|---|
| `CCP_ENTRY_MODELS` | gross expectancy at a grab ≈ zero; CCP shape adds nothing |
| `CCP_EXIT_MODELS` | partial + breakeven is significantly **worse**, z −4.2 to −8.3 |
| `CCP_FILTER_OVERFIT` | mined filters give back more than they appear to make |
| this file | five named context filters fail; one earns a forward run |

The grab layer stays what it has been throughout: context, drawn because
reading levels by eye is a legitimate reason to draw them, with no entry, no
alert and no claim attached.
