# PRE-REGISTRATION — the leg-extreme anchor

Committed before the first number. Run by
`indicators/undertow/studies/undertow_anchor.py`.

## The question

The strategy's author has now stated the anchor three times, and drawn it:
**in a bearish trend the counter-trend candle is at the bottom of each down-leg
and in a bullish trend at the top of each up-leg** — one per minor leg, four
circles inside one trend.

`pinAt = "leg extreme"` is that object: the running extreme since the last
INTERNAL structure break. It is selectable, **off by default**, and unmeasured.

**This is the third attempt at the same idea and the first at the right
object.** [`UNDERTOW_V3.md`](../measurements/UNDERTOW_V3.md) measured
`trend extreme`, which anchors on the running extreme since the MAJOR CHoCH —
one point per trend. At the shipped 6/2 of the time it updated often enough to
look right; it is a stale point, and the priority-shape pin sits a median of 47
bars past it. `leg extreme` resets on every internal turn: median 8 bars.

## Why this is NOT shipped as a correction like W→F

W→F, the priority pairing and the inclusive failure test all went out as
corrections without a measurement, because each cost nothing: they change
*which event arms*, not how much the strategy sees.

**This one costs three quarters of the setups.** Measured on a spent universe:
1,831 trades at the shipped anchor against 888 at the leg extreme. A rule that
removes 75% of the population is not a free correction, whoever stated it, and
it gets measured before it becomes a default.

## THE ANCHOR RELOCATES THE POPULATION, IT DOES NOT FILTER IT

`SYMBOLS_FRESH6`, spent, as a design input:

| | trades |
|---|---|
| shipped (pullback extreme) | 1,831 |
| leg extreme | 888 |
| shared | 408 |
| **only the leg extreme** | **480** |

**54% of what the leg anchor takes, the shipped anchor never takes.** So the
control is a **seeded random entry matched to the primary**, not a matched
random gate — the same reasoning as the scale study, and the opposite of the
pin study where the rule really is a subset.

## The arms

| id | | |
|---|---|---|
| **L0** | what ships — pullback extreme, `locTol 0` | **THE BASELINE** |
| **L1** | **leg extreme, `locTol 0`** | **THE PRIMARY** |
| L2 | leg extreme, `locTol 2` | descriptive — the coverage/shape trade |
| L3 | trend extreme, `locTol 0` | descriptive — v3's anchor on today's engine |
| **C** | seeded random entry matched to L1, whole series | **THE CONTROL** |

Everything else is the shipped configuration and identical across arms: SMC
14/5, W→F, `pinNewest` and `famPriority` on, `endMinor` on the flip, retrace
70, `rr` 3.5, 7bp, `maxLive 64`.

L2 and L3 may not be promoted. Best-of-four is selection, and it is the
−0.31 R per trade [`UNDERTOW_PARAMS.md`](../measurements/UNDERTOW_PARAMS.md)
priced.

## Population

**`SYMBOLS_FRESH10`** — 45 contracts, disjoint from the 23 and from all nine
earlier sets. 24h turnover 100–112k. 122 unused contracts remain, which is two
more sets of this size at most.

* 12,000 bars, Min15 / Min30 / Min60, ≥ 11,000 bars or dropped
* a timeframe with fewer than 20 surviving symbols is **not reported**

## What must be IMPOSSIBLE

Written to assert the thing being checked, which two preregs ago it did not.

* **THE ANCHOR REACHES THE PIN.** L1 ≠ L0 on trade count. Identical means
  `pinAt` is not read.
* **L1 IS NOT A SUBSET OF L0.** The design table says it relocates; if it comes
  back a strict subset, the anchor is behaving as a filter and the random-entry
  control is the wrong one.
* **THE PRIORITY SHAPE DOMINATES L1.** ≥ 70% of L1's armed pins are the
  priority shape — hammer in a bearish trend, shooting star in a bullish one.
  This is the *mechanism* the anchor is supposed to deliver and the reason it
  was asked for; if it does not, the object is still wrong and the expectancy
  is beside the point.
* **`nCap` is 0 in every arm.**

Any of these firing makes the run **VOID** and the numbers are not published.

## Pre-registered bars, on L1

1. **COVERAGE.** ≥ 200 closed trades.
2. **NOT CONFOUNDED.** All four impossibilities hold.
3. **BEATS WHAT SHIPS.** L1 − L0 ≥ **+0.10 R per trade**, clustered |z| ≥ 2.
4. **BEATS ITS CONTROL.** ≥ 1 SE above the seeded random entry.
5. **POSITIVE.** Mean R per trade > 0 after fees.
6. **NOT ONE TIMEFRAME.** Positive on ≥ 2 of 3.

## THE DECISION RULE, and a null does NOT mean "ship it anyway"

The scale study's null meant *keep the preference, it is free*. **This null
would mean something different, and the difference is the point:**

* **L1 clears 3, 4, 5 and 6** → the leg extreme becomes the default anchor in
  the port, the chart and the watch.
* **NULL** → the author's stated anchor costs **75% of the setups for no
  measurable gain**. That is not free and it does not ship on a diagram. It
  stays selectable, the page says plainly what it costs, and the decision is
  the chart owner's with the number in front of them.
* **WORSE by more than 0.10 R at |z| ≥ 2 on ≥ 2 timeframes** → it stays off and
  the page says so.

## My prediction, recorded before the run

* **L1 fails bar 4.** Sixteen components measured, none has beaten a control.
* **L1 − L0 lands between −0.10 and +0.10**, and I hold this one a little
  loosely: unlike the scale, this changes WHICH candle is pinned, and
  UNDERTOW_V3.md's one suggestive number — the trades the anchor ADDED scored
  +0.054 / +0.107 / +0.089 — came from the same family of change.
* **The priority-shape impossibility HOLDS at 80-85%.** Measured at 84% on a
  spent set; if it comes back near 50% the anchor is not doing what the diagram
  says and that is the most useful thing this study could find.
* **L2 (tol 2) has roughly 3x L1's trades and ~56% priority shapes**, repeating
  v3's finding that the shape selection lives entirely at zero tolerance.
* **Win rates near the fee-inclusive line**, 22.9–23.5%.

## What cannot happen

* **No fourth anchor and no second `locTol`** beyond the fixed arms above.
* **No promotion of L2 or L3.**
* **No falling back to an earlier universe.** FRESH7 is claimed by the pin
  study; FRESH8 and FRESH9 are spent.
* **No change to the taxonomy, the levels, the exit or the bias.**
* **No exchange API key and no order placement.**
* **One study, one run.**
