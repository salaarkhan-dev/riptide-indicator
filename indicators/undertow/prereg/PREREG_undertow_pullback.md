# PRE-REGISTRATION — the three pullback defects

Committed before the first number. Run by
`indicators/undertow/studies/undertow_pullback.py`.

## What is being tested

[`SPEC.md` §2.3b](../SPEC.md) records three defects found by reading the
pullback rule against the code, and measures how often each bites:

| | Min15 | Min30 | Min60 |
|---|---|---|---|
| pin has a **zero-bar pullback** | 25.3% | 30.8% | 33.6% |
| pullback ≤ 3 bars | 70.9% | 80.5% | 85.2% |
| median pullback age | 2 bars | 1 bar | 1 bar |

1. the bar that makes a new trend extreme is immediately its own "pullback
   extreme" (`pbReset` sets `pbExtX = i` on the same line)
2. there is **no minimum pullback**, in bars or in price
3. **only one bar can ever be the pin** — `locTol` ships at 0, so a doji or a
   wrong-coloured bar at the extreme discards the whole pullback

## THE DESIGN PROBLEM, and how it is handled

These pull in **opposite directions**. `locTol` LOOSENS — more setups. The two
minimums TIGHTEN — fewer. Three knobs at four levels each is 64 configurations
and a maximum, which is precisely the **−0.31 R per trade** that
[`UNDERTOW_PARAMS.md`](../measurements/UNDERTOW_PARAMS.md) measured as the cost
of selecting from a chart.

So: **one primary, fixed here, and no maximum is taken anywhere.**

### Why the primary is `locTol 2` + `pbMinDepth 0.20`, and not `pbMinAge`

`pbMinAge` is a number of **BARS**. Three bars is 45 minutes on 15m and three
hours on 1h — the same timeframe dependence this project has now rewritten the
swing detector, the Slope source and the HTF gate to remove. `pbMinDepth` is a
fraction of the impulse leg the engine already tracks, so it means one thing on
every chart.

`locTol` is also in bars and is kept anyway, because "how many candles will you
look at" is genuinely a candle count and not a span of market time.

`pbMinAge` runs as a **descriptive** arm so its timeframe dependence is visible
rather than assumed.

## The arms

| id | locTol | pbMinAge | pbMinDepth | |
|---|---|---|---|---|
| **A0** | 0 | 0 | 0.0 | **THE BASELINE — what ships** |
| **A1** | **2** | 0 | **0.20** | **THE PRIMARY** |
| A2 | 2 | 0 | 0.0 | descriptive — defect 3 alone |
| A3 | 0 | 0 | 0.20 | descriptive — defect 2 alone |
| A4 | 0 | 3 | 0.0 | descriptive — the bar-unit version |
| **C** | seeded random entry matched to A1 | | | **THE CONTROL** |

`locTol = 2` means the pin may be the extreme bar or one of the next two —
"if the first candle does not qualify, look at the second and third", which is
the request this came from, taken literally and not widened.

`pbMinDepth = 0.20` is one fifth of the impulse. Chosen because 38.8% of 15m
setups fall below it (SPEC §2.3b), so it bites on a substantial minority
without gutting the population. **It is not tuned and no second value is
scored.**

## THE DECOMPOSITION, which is the useful part

A1 both adds and removes setups, so the mean alone cannot say which change did
what. Every A1 trade is labelled against A0:

* **SHARED** — A0 takes it too
* **ADDED** — only A1 takes it (the `locTol` loosening)
* **DROPPED** — A0 takes it, A1 refuses it (the `pbMinDepth` tightening)

**ADDED and DROPPED are each scored separately**, the way
[`UNDERTOW_BACKUP_FILL.md`](../measurements/UNDERTOW_BACKUP_FILL.md) split its
population — the split is where that study's only real signal came from, and it
is the thing a single mean hides.

If ADDED is strongly negative, defect 3 is not a defect and the extreme bar is
the extreme bar for a reason. If DROPPED is strongly negative, the no-pullback
setups were losing money and defect 2 is real. **Both are diagnosis, not a
result** — which subset a trade lands in depends on the rule being tested.

## Population

**`SYMBOLS_FRESH4`** — ranks 136–180 under the frozen rule, disjoint from the
23 and from all three earlier fresh sets. No number from it has been seen.

* 45 symbols, 12,000 bars, Min15 / Min30 / Min60, ≥ 11,000 bars or dropped
* `maxLive = 64`, `rr` 3.5, shipped Ending rules, pullback stop, 7bp fees
* bias `structure` on `price move` swings — **the bias is not varied here**
* candle, confirmations, levels and exit unchanged in every arm

## The metric

* **PRIMARY: mean R per trade**, clustered by symbol.
* Reported: trades per day, setups per day, and the ADDED / SHARED / DROPPED
  split with a mean and an SE each.
* **Throughput is reported and is NOT a bar.** In the HTF prereg I made it one
  and it passed 3 of 3 for a worthless reason — the baseline was negative, so
  doing less of a losing thing raises R per bar.

## Pre-registered bars, on A1

1. **COVERAGE.** ≥ 200 closed trades.
2. **NOT CONFOUNDED.** `nCap` 0 in every arm.
3. **BEATS THE BASELINE.** A1 − A0 ≥ **+0.10 R per trade**, clustered |z| ≥ 2.
4. **BEATS ITS CONTROL.** ≥ 1 SE above the seeded random entry matched on
   symbol, direction, risk, `rr` and holding window.
5. **POSITIVE.** Mean R per trade > 0 after fees.
6. **NOT ONE TIMEFRAME.** Positive on ≥ 2 of 3.

**PROMOTION RULE: `locTol` and `pbMinDepth` change their shipped defaults only
if A1 clears 3, 4, 5 and 6.** A2, A3 and A4 change nothing whatever they print.

## My prediction, recorded before the run

* **A1 fails bar 4.** Eleven components measured, none has beaten a control.
* **A2 roughly doubles the trade count.** On the one symbol looked at while
  building this (ETH 15m, not in any of these universes) `locTol = 2` took 33
  trades to 75.
* **ADDED scores WORSE than SHARED**, by 0.05 to 0.20 R. The extreme bar is the
  extreme for a reason: a pin one or two bars later sits at a worse price for
  the same stop, so the R is mechanically smaller before any question of edge.
  **This is the prediction I am least sure of** — if ADDED comes back at or
  above SHARED, defect 3 was costing real money and that is the most useful
  thing this study could produce.
* **DROPPED scores below zero**, because the no-pullback setups are the ones
  taken at the impulse bar with no retracement to lean on.
* **A3 raises mean R per trade and fails bar 3 anyway**, on the same pattern
  every filter here has followed.
* **A4 removes a visibly different fraction of setups on each timeframe** — it
  is three bars everywhere and three bars is not the same thing anywhere.

## What cannot happen

* **No second value** of `locTol`, `pbMinAge` or `pbMinDepth`.
* **No promotion of A2, A3 or A4.**
* **No promotion on the ADDED/DROPPED split**, which is diagnosis: membership
  is defined by the arm being tested.
* **No change to the bias, the candle, the confirmations, the levels or the
  exit.**
* **No falling back to an earlier universe for the primary.**
* **No production change unless the promotion rule is met.**
  `tests/test_control_frozen.py` must still pass.
* **No exchange API key and no order placement.**
* **One study, one run.**

## If A1 fails

Then the pullback rule is measured too, the three defects are real as
*descriptions* and worthless as *fixes*, and SPEC §2.3b keeps the numbers with
a note that correcting them changed nothing. The decomposition is still worth
having: it says which half of the rule was wrong, which is more than "it does
not work".
