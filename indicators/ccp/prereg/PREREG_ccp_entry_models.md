# PRE-REGISTRATION — is there a tradeable entry in the CCP-at-grab mark?

Committed before the first number. Run by
`indicators/ccp/studies/ccp_entry_models.py`.

## The decision this is for

`riptide-ccp.pine` marks a grab when a pin shape appears at the swing that
built the level and at the candles that ran it. Nothing is known about whether
that mark predicts anything — `research/CCP_SEARCH_INFLATION.md` says so
explicitly and measures only how often the classifier fires.

This asks the next question and only that one: **does the CCP mark select
grabs that pay better than the grabs it rejects, and does either make money at
all?**

The prior from this repo is not encouraging and is recorded here so the result
cannot be read as a surprise either way:

* `research/MS_ENTRY_MODELS.md` — five entry models on the structure engine,
  **nothing passed**, and every model including the control was negative in
  standalone R.
* `research/POOL_PIVOT_LENGTH.md` — six pivot widths on this exact grab
  detector, came back **UNDERPOWERED**.
* `indicators/ccp/tools/liquidity_grab_rate.py` — the grab fires at least 1.8x as often as
  Riptide's own raid, and two thirds of its marks are places Riptide says
  nothing.

## Population

Every grab from the **3/3 (narrow) instance**, the same detector
`deploy/ccp-grab-check.py` proves is byte-identical between
`riptide-indicator-v2.pine` and `riptide-ccp.pine`, transcribed in
`indicators/ccp/tools/ccp_at_grabs_check.py`.

* 23 symbols, `research.data.SYMBOLS`
* **three timeframes: Min15, Min30, Min60** — the 15m / 30m / 1h asked for
* 333-day deep window via `research.deep.load_universe`
* split older / newer half by bar index → **six panels**

## The entry, held constant across every arm

This is the point of the design. Entry timing, stop and target are **identical
for every grab**, so the only thing that varies between arms is whether the CCP
filter accepted it. Anything the arms differ by is selection, not execution.

| | |
|---|---|
| **direction** | grab of a HIGH (buy-side) → SHORT; grab of a LOW → LONG. Fixed by the grab, never chosen. |
| **signal bar** | `grabBar + ccpFwd` — the bar on which the CCP verdict is knowable. Every arm enters on the same bar, including the ones CCP rejected. |
| **entry** | the close of that bar. Market, so there is no fill assumption to argue about. |
| **stop** | the extreme of the widest window the right-end search can see: lowest low (long) / highest high (short) over `[grabBar − ccpBack, grabBar + ccpFwd]`. Defined identically whether or not CCP fired, which is why it is this and not the merged window's extreme. |
| **stop floor** | widened to **0.25 x ATR(14)** if the structural stop is tighter. Declared in advance: `MS_ENTRY_MODELS` had two of five models rendered *unmeasurable* by stops at 0.16–0.20% of price, and this is the guard against repeating that. |
| **skip** | a stop on the wrong side of entry is SKIPPED, never substituted, and the count is reported. |
| **target** | 2R |
| **horizon** | 48 hours — 192 / 96 / 48 bars |
| **fees** | `research.harness` defaults, maker+taker, charged in R |
| **scorer** | `research.harness.simulate_market` |

## Arms, fixed in advance

**B — BASE.** Every grab. The reference, not an arm under test.

| id | filter |
|---|---|
| **A1** | CCP fires at BOTH ends, direction-gated — the shipped default |
| **A2** | CCP fires at the RIGHT end only (the candles that ran the level) |
| **A3** | A1 plus `ccpAnchorExtreme` — the long wick must be the anchor's own |
| **C0** | control: same grabs as B, same direction, same stop, but the signal bar drawn uniformly from `[grabBar+ccpFwd, grabBar+ccpFwd+20]` |

C0 is the timing control. If B and C0 score the same, the specific bar carries
nothing and any arm's edge is selection alone; if B beats C0, entering promptly
after a grab is worth something before CCP is even consulted.

**Not varied.** `ccpBack`/`ccpFwd` = 2/2, `ccpBodyMax` = 0.15, `ccpWickMin` =
0.70, `ccpMinRangeATR` = 0.50 — the shipped defaults, not swept. The 10/10
wide instance is not an arm. Target, horizon, fees and the stop rule are fixed
above. **A losing arm does not get a second stop rule.**

## Unit of evidence

**The bet = one grab.** Grabs on the same symbol on the same day share a level,
a session and a move, so significance is computed with **standard errors
clustered by (symbol, calendar day)**. That is the primary SE and it is chosen
now, not after seeing which one is kinder.

## Primary metric

For each arm A, the difference between the grabs it accepted and the grabs it
rejected, within the same panel:

    Δ_A = mean R( grabs where A fires ) − mean R( grabs where A does not )

Standalone net R is reported for every arm and for B and C0. **The standalone
number is the one that decides whether anything is tradeable**; Δ only decides
whether the filter is doing work.

## Pre-registered bars — all five

1. **COVERAGE.** At least **200 accepted bets in every panel**. Below that the
   panel is reported as not measurable rather than read.
2. **SIGN STABILITY.** Δ keeps one sign across all six panels.
3. **BEATS WHAT IT REJECTED.** Δ > 0 on the newer half of all three
   timeframes.
4. **MAKES MONEY.** The arm's standalone net R > 0 after fees on the newer half
   of all three timeframes. A filter that loses less than the grabs it threw
   away is not an entry model.
5. **SIGNIFICANCE.** Clustered |z| ≥ 2.0 on the pooled newer half.

### Family-wise inflation, stated before the run

Three arms x three timeframes x two halves = **18 tests**. At z ≥ 2.0 each, the
expected number of false positives is about 0.9 and the chance of at least one
is roughly **60%**. Bars 1–4 carry any pass. **Bar 5 alone carries nothing, and
no result from this study will be quoted with its z-score and without this
sentence.**

### Power, and the escape hatch

At 2/2 the CCP filter accepts about 16.4% of grabs. From
`indicators/ccp/tools/ccp_at_grabs_check.py`, Min15 gives roughly 2,700 grabs per 20-day
window, so a 333-day window should give far more than the 200-bet floor on
Min15, and Min60 is the one at risk.

R's spread on this repo's studies runs near 1.3. If a panel's SE(Δ) implies a
**minimum detectable effect above 0.25 R**, that panel is declared
**UNDERPOWERED** and reported as a bound — "this run could not have resolved an
effect smaller than X" — rather than as a verdict. That is what
`POOL_PIVOT_LENGTH` did and it is the honest outcome when the sample is thin,
not a failure to report.

### Degenerate-stop guard

Median risk as a percent of price is reported per timeframe. **Below 0.42%**
— the level at which Stage A of the LIT work died, and at which two of the five
structure models became unmeasurable — the panel is declared unmeasurable on
its stop rather than read as a result about the trigger. The 0.25 ATR floor
above exists to prevent this; the guard exists in case it does not.

## Seeding

C0 draws its bar from `random.Random(hash((symbol, tf, grabBar)))`, so the
control is identical on every re-run and cannot be re-rolled into a better
comparison.

## What cannot happen

* **No production change.** Nothing under `riptide/`; `tests/test_control_frozen.py`
  must still pass. No change to `riptide-indicator.pine`.
* **No exchange API key, no order placement, no execution code.** This is phase
  1 and it is measurement only.
* **No parameter tuning.** The CCP settings above are the shipped defaults and
  are not swept in this study.
* **No retrospective filtering** of symbols, timeframes, halves or grabs.
* **One study, one set of arms.** There is no v2 of this prereg. If every arm
  fails, that is the finding.

## If nothing passes

Then `riptide-ccp.pine` stays what it is — a bench that draws a classification,
with no entry layer, no stop, no target, no grade and no outcome tracking, on
exactly the terms `riptide/watch.py` already set for the trendline. The order
blocks and FVGs mentioned as the next thing to try are a **separate prereg and
a separate run**; they do not get folded into this one to rescue it, because a
filter chosen after seeing this study's residuals is not a filter, it is a fit.

An arm that passes all five bars earns an entry layer in the bench — **off by
default** — and a forward-tracking run before it is allowed near the bot.
