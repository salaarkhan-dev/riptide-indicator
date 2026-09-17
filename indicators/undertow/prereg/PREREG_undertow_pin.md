# PRE-REGISTRATION — which pin, when a pullback offers several

Committed before the first number. Run by
`indicators/undertow/studies/undertow_pin.py`.

## The question, and why it is not the one v2 answered

A pullback contains several counter-trend candles. What ships runs **all of
them** as independent candidates. The strategy as its author states it does
not: *"priority shape wins, newest of that shape."*

`UNDERTOW_V2.md` scored `pinNewest` and concluded against it. **That was the
wrong form of the rule.** `famPriority` has effect only *inside* the
`pinNewest` branch, by construction, so the two switches are one rule with
three settings, and v2 tested the middle one:

| | bearish armed | hammer | R per trade |
|---|---|---|---|
| neither — what ships | 1,953 | 60.1% | +0.046 ±0.069 |
| `pinNewest` alone — pure recency | 279 | **30.1%** | **−0.115 ±0.137** |
| `famPriority` alone | 1,953 | 60.1% | inert, bit-identical |
| **both — the stated rule** | 812 | **62.2%** | **+0.061 ±0.089** |

FRESH6, Min15, from [`UNDERTOW_V3.md`](../measurements/UNDERTOW_V3.md). **Those
numbers are why this study exists and they may not be counted as its result** —
FRESH6 is spent, one timeframe, 0.7 SE.

## THE PAIR IS A SELECTOR, SO THE CONTROL IS A RANDOM GATE

Measured on FRESH6: of the 807 trades the pair takes on Min15, **zero are
trades the shipped rule does not also take.** It discards 55.3% of them and
invents nothing. Min30: 53.2%, zero outside.

**So the right control is a coin discarding the same fraction**, not a random
entry. `UNDERTOW_MTF_DEFAULT.md` records why: any rule that throws away half a
population moves the mean, and half of all such rules move it up. A random
entry would be the easy control and it would not be the honest one.

## The arms

| id | | |
|---|---|---|
| **P0** | **what ships today** | **THE BASELINE** |
| **P1** | `pinNewest` + `famPriority` — the stated rule | **THE PRIMARY** |
| P2 | `pinNewest` alone — pure recency | descriptive: the form v2 scored |
| **G** | P0's trades, the same fraction discarded at random, seeded | **THE CONTROL** |

P0 is the SHIPPED configuration and not v1-as-published: structure bias,
`endMinor` on the flip, retrace 70, **W→F confirmation**, the pullback anchor,
`locTol 0`. The question is whether to change the chart, so the thing to beat
is the chart.

P2 may not be promoted whatever it prints. It is here so the page can say what
v2 actually measured, in the same panel, on a fresh universe.

## Population

**`SYMBOLS_FRESH7`** — 45 contracts, disjoint from the 23 and from all six
earlier fresh sets. Nothing has been seen.

It adds **rule 3c** to the frozen selection rule: drop a base coin on a written
stablecoin list. `USDC_USDT` came top of the unused list and is a pair pinned
near 1.0000 — 12,000 bars of flat entering a trend study. The rule is widened
in `research/symbols_fresh.py` with the list spelled out, not by deleting a
name.

**The venue's liquid end is spent and this set is thinner than the last.** 24h
turnover in thousands: FRESH5 227–376, FRESH6 181–242, **FRESH7 145–190**. The
step is the same size as the one before it, so this is the same kind of
population — but it is a step down and the page must say so.

* 12,000 bars, Min15 / Min30 / Min60, ≥ 11,000 bars or the symbol is dropped
* a timeframe with fewer than 20 surviving symbols is **not reported at all**
* `maxLive = 64`, `rr` 3.5, pullback stop with tracking, 0.25 ATR buffer, 7bp
* the candle taxonomy, the levels and the exit are **unchanged**

## What must be IMPOSSIBLE

* **P1 ⊆ P0.** Every trade the pair takes is one the shipped rule also takes.
  It selects; it cannot invent. A trade outside P0 means superseding is doing
  something other than choosing between candidates.
* **P2 ≠ P0** and **P1 ≠ P0.** Identical means a switch never reached the
  supersede block — the `swingSrc` rename failure, again.
* **`nCap` is 0 in every arm.** At the cap the arms stop being comparable,
  because the pair frees slots the baseline is using.

Any of these firing makes the run **VOID**, not "inconclusive", and the numbers
are not published.

## Pre-registered bars, on P1

1. **COVERAGE.** ≥ 200 closed trades.
2. **NOT CONFOUNDED.** All three impossibilities hold.
3. **BEATS WHAT SHIPS.** P1 − P0 ≥ **+0.10 R per trade**, clustered |z| ≥ 2.
4. **BEATS THE RANDOM GATE.** ≥ 1 SE above a coin discarding the same fraction.
5. **POSITIVE.** Mean R per trade > 0 after fees.
6. **NOT ONE TIMEFRAME.** Positive on ≥ 2 of 3.

**PROMOTION RULE: both switches become defaults — port, chart and watch — only
if P1 clears 3, 4, 5 and 6.** Bar 4 is the one that matters here and it is the
one a selector usually fails.

**A separate, weaker outcome is available to this study and is named in
advance**: if P1 clears 4 but not 3, the pair goes on the chart as an input
defaulting to off, the way `pinAt` did. That is not a promotion and the page
must not describe it as one.

## My prediction, recorded before the run

* **P1 fails bar 4.** Fourteen components measured, none has beaten a control,
  and this is the first one measured against the harder control rather than a
  random entry. The FRESH6 number that prompted the study is 0.7 SE, which is
  what noise looks like.
* **P1 − P0 lands between −0.05 and +0.08 R.** Halving a population moves the
  mean by about this much whatever the rule is.
* **P2 is the worst arm**, and by more than its error bar on at least one
  timeframe. Pure recency selects against the stated shape 70% of the time; if
  shape matters at all, this is where it shows.
* **P1 − P2 is the most informative number on the page**, because both discard
  most of the population and they differ only in how they choose.
* **The hammer share confirms the mechanism**: P0 near 60%, P1 above it, P2
  near 30%. If it does not reproduce on a fresh universe, the FRESH6 table was
  noise and the study's premise is wrong — which the page must then say.
* **Win rates sit on the fee-inclusive line**, 22.9–23.5% by timeframe, not on
  22.2%. [`UNDERTOW_V3.md`](../measurements/UNDERTOW_V3.md) corrected that.

## What cannot happen

* **No second value** of anything. Both switches are booleans and the arms are
  fixed above.
* **No promotion of P2**, whatever it prints.
* **No falling back to an earlier universe for the primary**, and FRESH6 in
  particular is spent.
* **No change to the candle taxonomy, the levels, the anchor or the exit.**
  `pinAt` stays at the pullback extreme in every arm — this study is about
  WHICH candidate wins, not where they are looked for.
* **No production DEFAULT change unless the promotion rule is met.**
  `tests/test_control_frozen.py` must still pass.
* **No exchange API key and no order placement.**
* **One study, one run.**
