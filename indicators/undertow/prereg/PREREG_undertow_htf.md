# PRE-REGISTRATION — does a higher-timeframe agreement gate help?

Committed before the first number. Run by
`indicators/undertow/studies/undertow_htf.py`.

## The decision this is for

Eight studies have found nothing, and the request is: *use the HTF bias.*

**Unlike the last four ideas, this one has genuinely never been tested.** The
HTF gate already exists in the port (`htfMult`), is no-look-ahead, and is
covered by two tests — but it has only ever appeared as **one binary dimension
of a 48-cell grid** in the parameter study, where only the single cell selected
on train was ever scored. `htf4` was in the 15m train winner, whose holdout came
back −0.093. That is not "HTF was tested and failed". Nothing isolated it, and
nothing controlled it.

## TWO THINGS ARE DIFFERENT ABOUT THIS STUDY

### 1. A genuinely unseen universe

Every previous Undertow study ran on the same 23 symbols, and all four
quadrants of that set have now been scored for something. Two measurement pages
say "every quadrant is spent" as a limit on what could be asked next.

**That limit was wrong.** The venue lists **594 crypto USDT perpetuals** that
pass a mechanical filter. `research/symbols_fresh.py` freezes **45 of them,
disjoint from the 23**, chosen by a rule fixed before any of them was loaded:
liquid crypto perps by 24h volume, with tokenised stocks, metals, oil and index
products excluded because they have session breaks and `bars_per()` mis-reads a
session break.

**This is the first Undertow study whose population no measurement here has
ever looked at.** The 23 are not used at all — not for training, not for
tuning, not for a sanity check.

### 2. The right control for a GATE

A gate only ever removes setups. Every previous study used a seeded
random-*entry* control, which asks "is the entry timing worth anything". That
is the wrong question here, because **any gate that removes 40% of trades will
move the mean, and roughly half of all such gates will move it up.**

So the primary control is a **seeded RANDOM GATE matched on rejection rate**:
same symbol, same timeframe, refusing the same *number* of setups, chosen at
random instead of by the higher timeframe. If the HTF gate cannot beat a coin
that throws away the same count, the higher timeframe is not informative and
the effect is just "trade less".

The random-entry control is reported alongside, for continuity with the other
eight pages.

## THE UNIT PROBLEM, again, and it is the same one

`htfMult` is a multiple of the BASE bar: `htfMult = 4` is 1h on a 15m chart and
**4h on a 1h chart**. One setting, two rules — the exact defect that the swing
detector and then Slope were both rewritten to remove.

So the port gains `htfUnit = "hours"` and `htfHours`: the HTF bar is a span of
TIME, however many base bars that takes. On 15m, `htfHours = 1.0` resolves to
exactly `htfMult = 4` — verified, and the equivalence is a test.

`htfUnit` defaults to `"bars"` with `htfMult = 0`, so the gate stays **off** and
every existing study is untouched. That is asserted, not assumed.

## The arms

| id | gate | |
|---|---|---|
| **H0** | off | **THE BASELINE** |
| **H2** | `htfHours = 4.0` | **THE PRIMARY, and the only arm eligible for anything** |
| H1 | `htfHours = 1.0` | descriptive |
| H3 | `htfHours = 12.0` | descriptive |
| H4 | `htfMult = 4` (bar multiple) | descriptive — the unit contrast |
| **R** | random gate, matched rejection rate | **THE CONTROL for H2** |

**ONE PRIMARY ARM, FIXED NOW, AND NO SELECTION.** 4 hours is pre-specified as
the higher timeframe because it is the conventional 4×–16× step above the three
base timeframes and because it is the same span of time on all three. H1, H3 and
H4 are printed so the shape is visible and **cannot be promoted** — if 12h
scores best, that is a finding for a future prereg, not this one.

Three primary tests, one per timeframe. No maximum is taken anywhere.

## Population and what is held constant

* **45 FRESH symbols** (`research.symbols_fresh.SYMBOLS_FRESH`), 12,000 bars
  each, Min15 / Min30 / Min60, run separately. Any symbol returning fewer than
  11,000 bars is dropped before anything is scored.
* `maxLive = 64`, `rr` 3.5, `locTol` 0, stop at the pullback extreme with
  tracking and a 0.25 ATR buffer, `feeFrac = 0.0007`
* bias `structure` on `price move` swings 0.40 / 0.12, retrace-only Ending
* the candle, the location, the confirmations, the levels and the exit are
  **unchanged in every arm**. Only the gate varies.
* a trade unresolved when the data ends is discarded

**No train/holdout split, because there is nothing to select.** The whole
universe is the holdout; one pre-specified arm is scored once per timeframe.

## The metric

* **PRIMARY: mean R per trade**, net of fees, clustered by symbol.
* **SECONDARY AND IT MATTERS MORE THAN USUAL: R per 1,000 bars.** A gate that
  removes half the trades for the same per-trade R is a *worse* product, not a
  neutral one. On ETH 15m, `htfHours 4.0` cut 33 trades to 16.
* Reported: setups refused by the gate, armed and fill counts, % of bars where
  the HTF agrees.

## Pre-registered bars, on H2

1. **COVERAGE.** ≥ 200 closed trades, else a bound.
2. **NOT CONFOUNDED.** `nCap` 0 in every arm.
3. **BEATS THE BASELINE.** H2 − H0 ≥ **+0.10 R per trade**, clustered
   |z| ≥ 2.0.
4. **BEATS THE RANDOM GATE.** H2 − R ≥ 1 SE. **This is the bar that matters and
   it is new.** It asks whether the higher timeframe is informative, or whether
   refusing setups is.
5. **POSITIVE.** Mean R per trade > 0 after fees.
6. **NOT ONE TIMEFRAME.** Positive on ≥ 2 of 3.
7. **DOES NOT COST MORE THAN IT EARNS.** R per 1,000 bars ≥ H0's. A gate can
   pass 3–6 and still make the strategy smaller and no richer; this is the bar
   that catches it.

**PROMOTION RULE, fixed now: H2 ships as a default only if it clears 3, 4, 5, 6
AND 7.** Clearing 3 and 5 while failing 4 means "trading less helps", which is
a fact about position count and not about the higher timeframe, and it will be
written that way.

## My prediction, recorded before the run

* **I expect H2 to fail bar 4.** Eight studies, nothing has beaten a control
  yet, and a gate has the easiest possible way to look good by accident.
* **I expect H2 to raise mean R per trade and fail bar 7** — fewer, better-
  aligned trades at a materially lower throughput. On the one symbol looked at
  while building the machinery (ETH 15m, not scored here), the gate cut 33
  trades to 16.
* **I expect H4 ≈ H1 on 15m exactly** — they resolve to the same multiple
  there, and if they do not, the unit conversion is broken.
* **The one that could surprise me is bar 4.** The ghost column in the
  parameter study said cancelling an already-armed setup saves 0.40–0.61 R, and
  this gate is a cancellation rule. That is the strongest mechanical prior any
  idea in this project has had. Against it: the ablation found that removing
  *all* the Ending rules beat keeping them on two of three timeframes, so this
  strategy's existing gates are not obviously earning their place either.
* **I do not expect the fresh universe to be kinder.** If anything the 23 were
  hand-picked and these 45 are not, so the baseline should look slightly worse.

## What cannot happen

* **No second value of `htfHours`.** H2 is 4.0 and that is fixed.
* **No promotion of H1, H3 or H4**, whatever they print.
* **No selection of a timeframe.** All three are reported.
* **No falling back to the 23 symbols** for anything, including a "sanity
  check" — the moment they are consulted this stops being a clean population.
* **No change to the candle, location, confirmations, levels, exit or bias
  source.**
* **No production change unless the promotion rule is met.** `htfUnit` defaults
  to `"bars"` and `htfMult` to 0, so the gate ships OFF either way until then,
  and `tests/test_control_frozen.py` must still pass.
* **No exchange API key and no order placement.**
* **One study, one run.**

## If H2 fails

Then the higher-timeframe gate is the ninth thing measured without an effect,
on a population that has never been touched — which is a stronger negative than
any of the eight before it, because it cannot be blamed on a spent holdout. The
45 fresh symbols remain, and they are then the most valuable thing this study
produced: every future question gets a clean population instead of a quadrant
somebody has already looked at.
