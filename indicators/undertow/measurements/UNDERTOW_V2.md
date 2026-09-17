# v2, the corrected strategy, is null too — and every arm sits on break-even

Against [`PREREG_undertow_v2.md`](../prereg/PREREG_undertow_v2.md).
`SYMBOLS_FRESH5`, ranks 181–225, disjoint from the 23 and from all four earlier
fresh sets. One primary — the whole v2 stack — fixed in advance, scored once.

## The verdict

| tf | V2 | V0 (v1) | Δ | z | control | n | win% | bars |
|---|---|---|---|---|---|---|---|---|
| Min15 | −0.097 | −0.012 | −0.086 | −0.87 | **+0.046** | 666 | 21.3% | PP... |
| Min30 | −0.056 | −0.001 | −0.054 | −0.53 | **+0.043** | 637 | 21.8% | PP... |
| Min60 | −0.027 | −0.124 | +0.096 | +0.92 | −0.030 | 455 | 22.2% | PP... |

**Bars 3, 4, 5 and 6 all failed.** v2 is negative on 3 of 3, loses to its own
random-entry control on 2 of 3, and is *worse than v1* on 15m and 30m.

**This is the thirteenth null, and it is the one that counts** — the twelve
before it measured v1, which [`SPEC.md` §8](../SPEC.md) records as a misreading
of the strategy. This one measured the strategy as its author states it.

## THE NUMBER THAT SAYS THE MOST

Break-even at `rr` 3.5 is **22.2%**, which is also what a driftless random walk
returns. Every win rate in the study:

| | V0 | V2 | L1 | L2 | L3 | L4 | L5 |
|---|---|---|---|---|---|---|---|
| Min15 | 23.4% | 21.3% | 21.4% | 26.1% | 21.5% | 22.6% | 22.0% |
| Min30 | 23.3% | 21.8% | 23.3% | 22.0% | 22.6% | 22.4% | 23.5% |
| Min60 | 20.3% | 22.2% | 22.4% | 13.8% | 23.2% | 22.3% | 22.4% |

**Twenty-one cells, and every one with a usable sample lands between 20.3% and
23.5% against a 22.2% line.** Two universes, thirteen studies, five symbol
sets, both rule versions. The exceptions are the two L2 cells, on 142 and 87
trades, which is noise.

That is what a zero-edge entry with costs looks like, and it is now shown for
the corrected rule as well as the original.

## Leave-one-out: every component is a small drag

Distance from V2 — positive means *removing* that component scored better:

| tf | L1 v1 bias | L2 v1 Ending | L3 no needBos | L4 either-order | L5 no pinNewest |
|---|---|---|---|---|---|
| Min15 | +0.002 | +0.205 | +0.005 | +0.057 | +0.032 |
| Min30 | +0.065 | +0.002 | +0.032 | +0.026 | +0.074 |
| Min60 | +0.006 | **−0.381** | +0.043 | +0.002 | +0.010 |

**Fourteen of fifteen cells are positive** — removing almost any piece improves
it. The prereg forbids acting on that, and the reason is visible in the table:
the gaps are 0.002 to 0.074 R, well inside the SEs, and L2's ±0.2–0.4 swings
come from 87–142 trades.

**Picking the best four of five here would be selection on noise.** That is the
−0.31 R per trade `UNDERTOW_PARAMS.md` measured, and the prereg named it in
advance for exactly this table.

## What each piece actually did

**`pinNewest` cost the most trades and the least expectancy**, as predicted:
L5 moves R per trade by +0.032 / +0.074 / +0.010 and the trade count by **4.4×**
on 15m (0.62 against 0.14 a day).

**The v2 stack cuts trading to a quarter of v1's** — 0.14 / 0.07 / 0.04 trades
a day per symbol against 0.59 / 0.29 / 0.15. `needBos`, `pinNewest` and the
W→F rule each tighten, and they compound.

**The SMC bias source changed almost nothing on its own** (L1: +0.002 / +0.065
/ +0.006). The engine whose swing detector and CHoCH are
[already identical to riptide's](../port/smc.py) also turns out to score the
same once the rest of the stack is held constant.

## THE HONEST LIMIT OF THIS STUDY

**v2 takes so few trades that this is the least powerful test in the project.**
n of 455–666 with SEs of 0.086–0.093 gives a difference SE near 0.10, so the
minimum detectable effect is about **±0.20 R per trade**, not the ±0.10 bar 3
asks for.

**A small real edge in v2 would not be visible here.** What the study excludes
is an edge of the size the strategy is supposed to have — the 1:2 to 1:7
outcomes that prompted the whole project — and that it excludes comfortably.
It does not exclude +0.05 R.

That is a direct consequence of v2 being a much stricter rule, and it is worth
knowing rather than papering over: the tighter the rule, the more data it needs
to prove itself, and v2 needs roughly four times the history v1 did to reach
the same resolution.

## Against the prediction

| predicted | actual | |
|---|---|---|
| V2 fails bar 4 | failed 3 of 3 | right |
| **V2 − V0 positive and large** | **−0.086 / −0.054 / +0.096** | **wrong** |
| L4 (either-order) is the biggest leave-one-out gap | +0.057 / +0.026 / +0.002 — not the biggest | **wrong** |
| L2 second biggest, showing v1's Ending rules did the filtering | L2's n is 87–142; unreadable | can't say |
| `pinNewest` barely moves R, moves trade count a lot | +0.01 to +0.07 R, 4.4× the trades | right |
| would surprise me: V2 clearing bar 4 | it did not | right |

I expected the corrected rule to be *better* than v1 and it is worse on two of
three timeframes. The mechanism argument for W→F still reads correctly to me —
the setup is a counter-trend attempt failing, so the attempt has to happen
first — and the data does not support it paying.

## What changes

**No default changes on this result.** The promotion rule required bars 3, 4,
5 and 6 and v2 cleared none of them.

**But the chart, the port and the watch already run W→F**, and that stays.
It is not a promotion and never was: v1's either-order rule was a misreading of
the strategy, so drawing and alerting the intended rule is a correction. The
prereg said this in advance — *"the measurement decides what the DEFAULTS are,
not what the chart is capable of showing."*

The remaining defaults are unchanged: `biasSrc` is still `structure`, the
Ending rules are still on, `needBos` and `pinNewest` are still off. Those are
defaults v2 did not earn.

**The twelve v1 pages are not superseded**, because v2 did not replace v1. They
stand as what they always were: thirteen measurements of a strategy that does
not have an edge either way round.

## Where this leaves it

Thirteen studies. Six symbol universes. Both versions of the rule. Every win
rate on the break-even line.

The one explanation no backtest reaches is unchanged and is now the only one
left: **whether a human choosing which setups to take beats the machine taking
all of them.** That needs a prospective record — alerts fired forward, taken or
skipped, outcomes written down — which is what `riptide/watchers/undertow.py`
exists to build, and it now alerts on the corrected rule.
