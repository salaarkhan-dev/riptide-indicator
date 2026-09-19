# PRE-REGISTRATION — the zone entry, the break-even stop, the wide stop

Committed before the first number of the evaluation run. Run by
`indicators/undertow/studies/undertow_zone.py` (to be written against this
file, not before it).

## The three findings this comes from, and where they came from

All three are DESCRIPTIVE, from the whole cached venue — 561 symbols, ~566,000
trades, the shipped configuration. Nothing was selected on them; they are the
diagnosis that decides what to pre-register.

| page | finding |
|---|---|
| [`UNDERTOW_LOSSES.md`](../measurements/UNDERTOW_LOSSES.md) | only **10%** of losers never moved; **39%** gave back a full R or more |
| same | the **FVG** fill scores +0.120 / +0.208 / +0.127 against the Focus line's −0.063 / −0.006 / −0.038 |
| same | a break-even stop after +1R is worth +0.021 / +0.014 / +0.021, **after** charging it the 36% of winners it scratches |
| [`undertow_edges.py`](../studies/undertow_edges.py) | R declines monotonically with stop width; the >8% bucket is −0.283 / −0.157 / −0.013 |

## THE POPULATION PROBLEM, stated first because it shapes everything else

**There is no clean disjoint holdout left.** `research/symbols_fresh.py`,
re-counted against the live exchange: 585 eligible contracts, 563 spoken for,
**21 usable** and every one at the 80–85k turnover floor. Twenty-one contracts
field about 20 / 19 / 14 symbols on 15m / 30m / 1h — it cannot report 30m, and
the 15m symbols are the venue's thinnest tail rather than the population every
earlier page measured.

So this prereg uses **three instruments of decreasing contamination and
increasing power**, and says plainly what each is worth:

**A. WALK-FORWARD ON THE SPENT SETS — the primary.** Fit nothing; apply the
rules below to the **newer half** of all 561 symbols, scored once.
**It is contaminated and here is exactly how much:** the diagnosis above read
aggregate statistics over the WHOLE series, including this half. It did not
read this half separately, and it did not choose a threshold per window — H1
is a mechanism with no free parameter, H2's +1R was chosen because it is the
first round number and the MFE band boundary that already existed in the
loss page, and H3's 3% is named below on a stated reason. That is weaker
contamination than a fitted threshold, and it is not zero.

**B. THE 21 REMAINING CONTRACTS — genuinely unseen, and underpowered.**
Reported on Min15 only. It cannot carry the decision; it can embarrass it.

**C. THE FORWARD RECORD — the real arbiter, and it starts now.** The watch is
already firing. Nothing below overrules a forward record that disagrees.

## The arms

| id | | |
|---|---|---|
| **E0** | the shipped configuration | **THE BASELINE** |
| **E1** | **zone-first entry** — the limit is placed at the nearest FVG between the Focus line and the stop, at ARM time, instead of only after price runs away | **THE PRIMARY** |
| **E2** | **break-even stop** — once the trade is +1R up, the stop moves to the entry | secondary |
| **E3** | **3% max stop width** — a setup whose stop is more than 3% from its entry is not taken | tertiary |
| **C** | seeded random entry matched to E0's count and direction | **THE CONTROL** |

**The arms are scored SEPARATELY against E0, never stacked.** A combined arm
is a fourth hypothesis wearing three hats, and the point of numbering them is
that each can fail alone.

Everything else is the shipped configuration and identical across arms:
`PIN_LOCAL`, `pbLook 10`, `locTol 3`, `pinLag 0`, `pinPick` best-entry, W→F,
`rr 3.5`, 7bp, `maxLive 16`.

## Why these thresholds and not others

* **E1 has no free parameter.** "The nearest FVG between the Focus line and
  the stop" is `bk_zone()`, which already exists and already ships as the
  backup. The change is WHEN it is consulted, not what it finds.
* **E2's +1R** is the first round number and is the band boundary the loss
  page already used. No ladder of 0.5R / 1R / 1.5R will be run.
* **E3's 3%** is the tightest cap that keeps **≥ 75% of trades on every
  timeframe** (89% / 77% / 55%). It was NOT chosen as the best-scoring cap:
  the best-scoring cap on the descriptive pass is 2% on Min60 at +0.051, and
  it keeps 29% of trades, which is a different strategy rather than a filter.

## What must be IMPOSSIBLE

* **E1 CHANGES THE FILL RATE.** A limit placed further from price must fill
  LESS often. If E1's fill rate is ≥ E0's, the zone is not being used.
* **E1 ≠ E0** on entry price for at least 20% of arms.
* **E2 never improves a loser that did not reach +1R**, and scratches
  **between 25% and 50%** of E0's winners. Outside that band the walk is wrong.
* **E3 removes between 10% and 25% of trades** on each timeframe.
* **`nCap` is 0 in every arm.**

Any of these firing makes that arm **VOID**. E1 voiding does not void E2.

## Pre-registered bars

**Three hypotheses is three chances to be lucky.** The clustered |z| bar is
**2.4**, not 2, which is Bonferroni at three tests and α 0.05.

1. **COVERAGE.** ≥ 500 closed trades per arm per timeframe.
2. **NOT CONFOUNDED.** The impossibilities for that arm hold.
3. **BEATS THE BASELINE.** Arm − E0 ≥ **+0.05 R per trade**, clustered
   |z| ≥ **2.4**.
4. **BEATS ITS CONTROL.** ≥ 1 SE above the seeded random entry.
5. **POSITIVE.** Mean R per trade > 0 after fees.
6. **NOT ONE TIMEFRAME.** Positive on ≥ 2 of 3.

## THE DECISION RULE

* **An arm clearing 3, 4, 5 and 6 on instrument A, and not contradicted by
  B** → it goes to the chart's owner as a recommendation with the numbers
  attached. It does not ship silently.
* **NULL, inside ±0.05** → it does not ship. The shipped configuration stays.
  A mechanism that matches how somebody trades is a legitimate reason to ship
  anyway — that is how `pinPick` shipped — but it is HIS reason to give, not a
  result, and the page must say so.
* **An arm WORSE than E0 by more than 0.05 R at |z| ≥ 2.4 on ≥ 2 timeframes**
  → recorded as a closed question so nobody re-opens it in three months.

## My prediction, recorded before the run

* **E1 clears bar 3 on Min30 and fails bar 6**, because the descriptive
  +0.208 is a self-selected population — those trades exist only because
  price ran 1R away first — and placing at the zone from the start recruits a
  different, worse set. I expect roughly **half** the descriptive effect to
  survive, so +0.08 to +0.12 on Min30 and near zero elsewhere.
* **E1's fill rate falls from 91% to 60–75%.**
* **E2 clears bar 5 and fails bar 3**, landing +0.01 to +0.03 — real,
  consistent, and under the +0.05 bar. This is the one I expect to be right
  and unusable.
* **E3 lands inside ±0.02 on every timeframe** and fails bar 3. The wide-stop
  bucket is genuinely awful and genuinely rare, and I have already made the
  mistake once of reading the bucket as the prize.
* **The sixteenth null is the most likely single outcome.**

## What cannot happen

* **No stacking.** No arm is combined with another after seeing the numbers.
* **No second threshold** for any arm. No 0.5R, no 2R, no 2% cap, no ladder.
* **No re-running instrument A after reading instrument B.**
* **No promotion on instrument B alone** — 21 thin contracts on one timeframe
  cannot carry a decision.
* **No quoting the descriptive pages as confirmation.** They are where the
  hypotheses came from; they cannot also be evidence for them.
* **No change to the anchor, the pin rule, the taxonomy or `rr`.**
* **No exchange API key and no order placement.** Phase 1 is alerts.
* **One run per instrument.**

## What this does NOT test, and why

Two questions were asked and answered descriptively as **nulls**. They are
recorded here so they are not re-opened:

* **W→F vs F→W→F.** −0.026 against −0.020 on Min15, +0.036 against +0.035 on
  Min30. The messier route is not worse. **Closed.**
* **A minimum pullback age.** On Min30 the YOUNGEST pullbacks score best
  (+0.050 and +0.052 for 0–1 and 2–3 bars against +0.014 for 7–10). A minimum
  would cut the strongest bucket. **Closed, and inverted from the
  expectation.**

And one prerequisite, if the pullback minimum is ever revisited: **`pbMinAge`
and `pbMinDepth` are inert.** They are applied inside
`if p.pinAt == PIN_PULL` and the shipped anchor is `PIN_LOCAL`, so both read
sensibly in the Pine and do nothing on the chart anybody loads. Testing them
without widening that condition would measure a field that never fires.
