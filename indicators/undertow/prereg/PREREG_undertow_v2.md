# PRE-REGISTRATION — v2, the corrected strategy

Committed before the first number. Run by
`indicators/undertow/studies/undertow_v2.py`.

## What v2 is

[`SPEC.md` §8](../SPEC.md) records that **§4 described a different event from
the one the strategy is about**, corrected by the strategy's author after
twelve studies. Everything in `measurements/` is correctly measured and
measured **v1**. v2 is:

| | v1 | **v2** |
|---|---|---|
| bias source | riptide structure, 6 / 2 pivots | **SMC structure, 50 / 5** |
| Ending rules | minor, sweep, stale, retrace 70, ADX | **none — CHoCH and BOS only** |
| trend required | Immature or Running | **Running — the pullback comes AFTER a BOS** |
| confirmation | both lines, **either order** | **WORKING first, then FAILURE** |
| pins per pullback | every one runs independently | **the newest supersedes the un-armed** |

## THE PRIMARY IS THE WHOLE STACK, and that is deliberate

Five changes at once is normally the worst possible design. It is the right one
here, and the reason is that **v2 is not a parameter search — it is the
strategy as its author states it.** The question is not "which of these five
helps", it is "does the intended rule work". Splitting it into a factorial
would be 32 configurations and a maximum, which is the **−0.31 R per trade**
[`UNDERTOW_PARAMS.md`](../measurements/UNDERTOW_PARAMS.md) measured as the cost
of selecting from a chart.

So: **one primary, the full v2 stack, fixed here.** The five components are
each reported as a leave-one-out arm — **descriptive, and none may be
promoted.** Leave-one-out says which part carries the change; it does not
license picking the best four.

## The arms

| id | | |
|---|---|---|
| **V0** | v1 exactly as shipped | **THE BASELINE** |
| **V2** | the full v2 stack | **THE PRIMARY** |
| L1 | v2 but v1's bias source (riptide 6/2) | descriptive |
| L2 | v2 but v1's Ending rules | descriptive |
| L3 | v2 without `needBos` | descriptive |
| L4 | v2 with either-order confirmation | descriptive |
| L5 | v2 without `pinNewest` | descriptive |
| **C** | seeded random entry matched to V2, **whole series** | **THE CONTROL** |

The control is built in-study and **not** `undertow_sweep.control()`, which
samples from a quadrant — the flaw recorded in
[`UNDERTOW_PULLBACK.md`](../measurements/UNDERTOW_PULLBACK.md). It marks
unresolved entries to market; discarding them is the bug that page also
records, and it made a control read −0.51 R.

## Population

**`SYMBOLS_FRESH5`** — ranks 181–225 under the frozen rule, disjoint from the
23 and from all four earlier fresh sets. Nothing from it has been seen.

* 45 symbols, 12,000 bars, Min15 / Min30 / Min60, ≥ 11,000 bars or dropped
* `maxLive = 64`, `rr` 3.5, `locTol` 0, pullback stop, 0.25 ATR buffer, 7bp
* the candle, the location, the levels and the exit are **unchanged**
* `pbMinAge` / `pbMinDepth` stay at 0 — `UNDERTOW_PULLBACK.md` measured them
  and they are not part of v2

## The metric

* **PRIMARY: mean R per trade**, clustered by symbol.
* Reported: trades and setups per day, win rate against the 22.2% break-even,
  and each leave-one-out arm's distance from V2.
* Throughput reported, **not a bar** — the HTF prereg made it one and it passed
  for a worthless reason, because a negative baseline rewards doing less.

## Pre-registered bars, on V2

1. **COVERAGE.** ≥ 200 closed trades.
2. **NOT CONFOUNDED.** `nCap` 0 in every arm.
3. **BEATS v1.** V2 − V0 ≥ **+0.10 R per trade**, clustered |z| ≥ 2.
4. **BEATS ITS CONTROL.** ≥ 1 SE above the seeded random entry.
5. **POSITIVE.** Mean R per trade > 0 after fees.
6. **NOT ONE TIMEFRAME.** Positive on ≥ 2 of 3.

**PROMOTION RULE: v2 becomes the shipped rule — port, chart and watch — only if
it clears 3, 4, 5 and 6.** If it does, every page in `measurements/` is
superseded and says so, because they all measured v1.

**The chart changes regardless of this result**, and that is not a promotion.
v1's confirmation rule is a misreading of the strategy; drawing the intended
rule is a correction, not a claim that it pays. The measurement decides what
the DEFAULTS are, not what the chart is capable of showing.

## My prediction, recorded before the run

* **V2 fails bar 4.** Twelve components measured, none has beaten a control.
  I have been wrong about a prediction twice in this project and both times it
  was about a *component*, never about a control.
* **V2 − V0 is positive and large, and bar 3 is the one that could go either
  way.** v2's bias source alone changes the trade population enormously: on one
  symbol, SMC 50/5 gave 236 trades against v1's 33. A number that different is
  a different strategy, not a tweak.
* **L4 is the biggest leave-one-out gap**, because the W→F rule is the
  correction with a mechanism behind it — the setup is a counter-trend attempt
  FAILING, so the attempt has to happen first, and either-order admits bars
  where it never happened.
* **L2 is the second biggest**, and in the direction that says v1's Ending
  rules were doing most of the filtering: removing them took one symbol from
  33 trades to 259.
* **`pinNewest` (L5) will barely matter** on R per trade and will matter a lot
  on trade count.
* **What would surprise me** is V2 clearing bar 4 on two timeframes. That would
  be the first thing in this project to beat a control, and it would mean the
  twelve nulls were nulls about the wrong rule.

## What cannot happen

* **No leave-one-out arm is promoted**, whatever it prints. Picking the best
  four of five is selection and this prereg exists to stop it.
* **No second value** of `smcSwingLen`, `smcInternalLen` or anything else.
* **No falling back to an earlier universe for the primary.**
* **No change to the candle, the location, the levels or the exit.**
* **No production DEFAULT change unless the promotion rule is met.**
  `tests/test_control_frozen.py` must still pass.
* **No exchange API key and no order placement.**
* **One study, one run.**
