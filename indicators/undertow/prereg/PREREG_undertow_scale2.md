# PRE-REGISTRATION — the swing scale, second attempt

Committed before the first number. Run by
`indicators/undertow/studies/undertow_scale.py` against `SYMBOLS_FRESH9`.

## Why there is a second one

[`PREREG_undertow_scale.md`](PREREG_undertow_scale.md) ran and is **VOID**
([`UNDERTOW_SCALE.md`](../measurements/UNDERTOW_SCALE.md)). The question is
unchanged and still open: **the 50/5 swing scale ships and has never been
measured against 6/2.**

**Three things about the first attempt belong here, not buried in a page.**

**1. The impossibility that fired was badly specified, and it was mine.** It
said the two engines' CHoCH counts "must match". It was *meant* to say a pivot
length had reached the detector. The engines turn out to differ by 0.1% — 17
events in 10,930, every one of them the series' *first* structure break,
because LuxAlgo's bias starts at "neither" and riptide's starts at "bearish".
Corrected below.

**2. FRESH8 is spent and this is what that cost.** A universe can be burned by
a study that publishes nothing. 45 contracts, gone, for a check I wrote wrong.

**3. I HAVE SEEN THE VOID NUMBERS AND A READER SHOULD WEIGH THAT.** They are
not published and they will not be quoted, but I read them, so I am not a
neutral party to this run. The protections are that FRESH9 is untouched, that
the arms and bars below are unchanged from the first attempt, and that this
paragraph exists. If the second answer flatters the first, that is worth less
than it would have been.

**Nothing else is changed from the first prereg** — same arms, same baseline,
same control, same bars, same decision rule. Only the impossibilities and the
population move. Changing anything else after a void run would be choosing a
design with a result already in view.

## The arms

| id | | |
|---|---|---|
| **S0** | SMC at **6/2** — the old scale on the new engine | **THE BASELINE** |
| **S1** | SMC at **50/5** — what ships | **THE PRIMARY** |
| S2 | riptide structure at 6/2, bar pivots | descriptive — the old engine |
| **C** | seeded random entry matched to S1, whole series | **THE CONTROL** |

The control is a random ENTRY and not a random gate, because the scale
**relocates** the population rather than filtering it: measured on FRESH6, the
two scales share 564 trades while 2,733 belong to 6/2 alone and 692 to 50/5
alone. There is no discard rate for a coin to match.

Everything else is the shipped configuration and identical across arms: W→F,
`endMinor` on the flip, retrace 70, the pullback anchor, `locTol 0`, `rr` 3.5,
7bp, `maxLive 64`.

## Population

**`SYMBOLS_FRESH9`** — 45 contracts, disjoint from the 23 and from all eight
earlier sets. 24h turnover 109–164k, median 115k. 165 unused contracts remain
after it.

* 12,000 bars, Min15 / Min30 / Min60, ≥ 11,000 bars or the symbol is dropped
* a timeframe with fewer than 20 surviving symbols is **not reported**

## What must be IMPOSSIBLE — rewritten

Each one now asserts the thing it is actually checking for.

* **THE LENGTH REACHES THE DETECTOR.** S1's CHoCH count is **below half** of
  S0's. A 50-bar pivot cannot flip as often as a 6-bar one; if it does,
  `smcSwingLen` is not being read. *This is what the old check was trying to
  say and failed to.*
* **S1 ≠ S0** on trades.
* **THE TWO ENGINES AGREE AFTER THE FIRST BREAK.** S0 and S2 fire CHoCH on
  identical bars once the series' first structure break is excluded. This is
  the corrected, tested form of the claim in
  [`smc.py`](../port/smc.py) — exact agreement, not a tolerance, everywhere
  except the one event whose cause is now understood.
* **`nCap` is 0 in every arm.**

Any of these firing makes the run **VOID**, and there will be no third attempt
on a third universe — a question that burns two holdouts on wiring is a
question to stop asking until the wiring is trusted.

## Pre-registered bars, on S1

Unchanged from the first attempt.

1. **COVERAGE.** ≥ 200 closed trades.
2. **NOT CONFOUNDED.** All four impossibilities hold.
3. **BEATS THE OLD SCALE.** S1 − S0 ≥ **+0.10 R per trade**, clustered |z| ≥ 2.
4. **BEATS ITS CONTROL.** ≥ 1 SE above the seeded random entry.
5. **POSITIVE.** Mean R per trade > 0 after fees.
6. **NOT ONE TIMEFRAME.** Positive on ≥ 2 of 3.

## THE DECISION RULE, unchanged and still asymmetric

**50/5 ships because it reads better on a chart, and that is a legitimate
reason.** This study prices that preference; it does not overrule it.

* **S1 clears 3, 4, 5 and 6** → it earns its place as well as reading well.
* **NULL, S1 − S0 inside ±0.10** → it costs nothing measurable. **It stays.**
* **S1 worse than S0 by more than 0.10 R at |z| ≥ 2 on ≥ 2 timeframes** →
  that is a real cost, and it goes to the chart's owner as a decision with the
  number attached, never as a silent revert.

## My prediction, recorded before the run

Unchanged from the first attempt, and deliberately not updated in light of
numbers I am not allowed to use:

* **S1 fails bar 4**, the fifteenth null.
* **S1 − S0 lands between −0.08 and +0.08.**
* **S1 trades about 38% of S0's rate.**
* **Win rates sit on the fee-inclusive line**, 22.9–23.5%, not 22.2%.
* **Held more loosely than the fourteen before it**, because this is the first
  study to change the bias's TIME SCALE rather than its source — 2.3 flips a
  day against something near 0.3 — and the earlier bias studies roughly held
  flip rate constant.

## What cannot happen

* **No third length**, no ladder. A sweep is the −0.31 R per trade
  [`UNDERTOW_PARAMS.md`](../measurements/UNDERTOW_PARAMS.md) measured.
* **No quoting the void run**, for support or contrast.
* **No promotion of S2.**
* **No third universe for this question.**
* **No change to the anchor, the taxonomy, the levels or the exit.**
* **No exchange API key and no order placement.**
* **One study, one run.**
