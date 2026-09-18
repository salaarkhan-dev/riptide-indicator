# PRE-REGISTRATION — the swing scale, 50/5 against 6/2

Committed before the first number. Run by
`indicators/undertow/studies/undertow_scale.py`.

## The question, and why it is owed

The structure engine is now LuxAlgo's Smart Money Concepts, at **LuxAlgo's own
lengths — 50 and 5**. It shipped that way by decision, not by measurement.
[`SPEC.md` §1](../SPEC.md) states the accounting plainly and this study closes
the one gap in it:

| | measured? |
|---|---|
| the DETECTOR — `leg()` against `bar_swings()` | **yes**, and they are the same expression, pivot for pivot |
| the ENGINE — SMC against riptide's | **yes**: [+0.002 / +0.065 / +0.006 R](../measurements/UNDERTOW_V2.md) |
| **the SCALE — 50/5 against 6/2** | **no. This.** |

A 50-bar pivot on 15m is twelve and a half hours. It is much the largest of
the three changes and it is the only one nothing has scored.

## THE SCALE RELOCATES THE POPULATION, IT DOES NOT FILTER IT

Measured on `SYMBOLS_FRESH6`, a spent universe, as a design input before
anything here was registered:

| | trades |
|---|---|
| SMC 6/2 | 3,297 |
| SMC 50/5 | 1,256 |
| shared | 564 |
| **only 6/2** | **2,733** |
| **only 50/5** | **692** |

**55% of what 50/5 takes, 6/2 never takes at all.** So this is not a gate and a
matched random gate is not the control — that argument belongs to
[`PREREG_undertow_pin.md`](PREREG_undertow_pin.md), where the rule really is a
subset. Here the control is a **seeded random entry matched to the primary over
the whole series**, as in v2 and v3.

The three pools are reported separately anyway, because on
[`UNDERTOW_V3.md`](../measurements/UNDERTOW_V3.md) that decomposition was more
informative than the headline.

## The arms

| id | | |
|---|---|---|
| **S0** | SMC at **6/2** — the old scale on the new engine | **THE BASELINE** |
| **S1** | SMC at **50/5** — what ships | **THE PRIMARY** |
| S2 | riptide structure at 6/2, bar pivots | descriptive — what shipped before the engine swap |
| **C** | seeded random entry matched to S1, whole series | **THE CONTROL** |

S2 may not be promoted. It is here so the page can separate *engine* from
*scale* in one panel instead of across two studies on two universes.

**Everything else is the shipped configuration** and identical across arms:
W→F confirmation, `endMinor` on the flip, retrace 70, the pullback anchor,
`locTol 0`, `rr` 3.5, 7bp.

## Population

**`SYMBOLS_FRESH8`** — 45 contracts, disjoint from the 23 and from all seven
earlier fresh sets. Nothing has been seen. `SYMBOLS_FRESH7` is NOT used: it is
pre-registered to the pin study and spending it here would void that.

**And it corrects the projection in FRESH7's note.** That note read a ~25%
decline across three sets and extrapolated. Re-ranked a day later, 24h
turnover in thousands:

| | min | median | max |
|---|---|---|---|
| FRESH6 | 124 | 197 | 263 |
| FRESH7 | 111 | 159 | 1095 |
| **FRESH8** | **124** | **135** | **1222** |

FRESH8 is **not** thinner than FRESH7. The tail is noisy rather than monotone,
and three points were the wrong basis for a trend. What holds is the structural
part: the top of the book is spent and 210 unused contracts remain.

* 12,000 bars, Min15 / Min30 / Min60, ≥ 11,000 bars or the symbol is dropped
* a timeframe with fewer than 20 surviving symbols is **not reported**
* `maxLive = 64`, pullback stop with tracking, 0.25 ATR buffer

## What must be IMPOSSIBLE

* **S0 and S2 fire CHoCH on the SAME BARS.** `smc.py` and
  `test_undertow_port.py` both assert the two engines' CHoCH lists are
  identical at a given pivot length; S0 and S2 run both engines at 6/2, so on
  fresh data the count must match. **This is the strongest wiring check
  available here** — it says the engine swap did what it claims, on data
  neither engine has seen, and it would catch a length that never reached the
  detector.
* **S1 ≠ S0.** Identical means `smcSwingLen` is not being read.
* **`nCap` is 0 in every arm.**

Any of these firing makes the run **VOID** and the numbers are not published.

## Pre-registered bars, on S1

1. **COVERAGE.** ≥ 200 closed trades.
2. **NOT CONFOUNDED.** All three impossibilities hold.
3. **BEATS THE OLD SCALE.** S1 − S0 ≥ **+0.10 R per trade**, clustered |z| ≥ 2.
4. **BEATS ITS CONTROL.** ≥ 1 SE above the seeded random entry.
5. **POSITIVE.** Mean R per trade > 0 after fees.
6. **NOT ONE TIMEFRAME.** Positive on ≥ 2 of 3.

## THE DECISION RULE, and it is not symmetric

**50/5 already ships, by your decision, because it reads better on a chart.**
This study cannot un-make that decision and is not trying to. So:

* **S1 clears 3, 4, 5 and 6** → the scale is earning its place as well as
  reading well. Nothing changes except the page.
* **NULL — S1 − S0 inside ±0.10** → the scale costs nothing measurable.
  **It stays.** A preference that costs nothing is a fine reason to keep a
  setting, and this project has never had grounds to overrule one.
* **S1 is WORSE than S0 by more than 0.10 R with |z| ≥ 2 on ≥ 2 timeframes**
  → that is a real cost and it goes to you as a decision, with the number, not
  as a silent revert. The chart is yours; the measurement's job is to make the
  price of it visible.

## My prediction, recorded before the run

* **S1 fails bar 4**, making this the fifteenth null. Fourteen for fourteen so
  far.
* **S1 − S0 lands between −0.08 and +0.08.** Every bias study in this project
  has landed there, and `UNDERTOW_BIAS_SOURCE.md` moved the *source* across
  five alternatives without moving R per trade.
* **But this is the first study to change the TIME SCALE of the bias rather
  than its source**, and the earlier ones roughly held flip rate constant.
  2.3 flips a day against something near 0.5 is a different kind of change,
  and it is the reason I hold the prediction above more loosely than the
  fourteen before it.
* **S1 trades about 38% of S0's rate**, from the design table.
* **S2 ≈ S0 on CHoCH count and differs on trade count**, because the engines
  share a detector and differ on the BOS rule.
* **Win rates sit on the fee-inclusive line**, 22.9–23.5% by timeframe, not on
  22.2%. [`UNDERTOW_V3.md`](../measurements/UNDERTOW_V3.md) corrected that.

**Power, stated in advance.** The design table suggests ~1,250 trades for S1 at
Min15, well above v2's and v3's 500–700, so the minimum detectable effect is
roughly **±0.15 R per trade** rather than ±0.20. Better than the last two
studies and still not enough to exclude +0.05 R.

## What cannot happen

* **No third length.** Two scales, fixed above. A ladder of pivot lengths is a
  sweep, and this project priced a sweep at **−0.31 R per trade** of illusion
  in [`UNDERTOW_PARAMS.md`](../measurements/UNDERTOW_PARAMS.md).
* **No promotion of S2.**
* **No falling back to an earlier universe**, and FRESH7 in particular is
  claimed.
* **No change to the anchor, the taxonomy, the levels or the exit.**
* **No exchange API key and no order placement.**
* **One study, one run.**
