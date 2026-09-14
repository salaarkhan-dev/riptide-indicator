# PRE-REGISTRATION — LIT Stage A (naked IDM continuation)

Frozen before the experiment is run. Committed before any Stage A result is
inspected.

## 0. HONESTY ABOUT WHAT THIS PRE-REGISTRATION IS AND IS NOT

A pre-registration is only worth the blindness behind it, so the limits are
stated first rather than buried.

**I am not blind to this project.** Earlier sessions measured a *zone-entry*
LIT strategy extensively — retrace-to-zone, pullback-gap filtering, SCOB
confirmation, obstacle checking, zone classification, and a ten-arm exit
sweep — and the results are in `LIT_CHANGELOG.md`. I have seen those numbers
and they inform the thresholds below. This document cannot undo that.

**What is genuinely unmeasured is the thing being registered here.** The naked
continuation control — enter at the IDM-break close, stop at the raid extreme,
nothing else — was last measured in `research/lit_entry.py` under a fee model
now known to be wrong (see §5). It has never been scored at the repository's
fee, never through the shared scorer, and never in bets rather than trades.

So the claim is narrow and it is the only one made: **the thresholds in §10
are fixed before the numbers exist, and they will not move afterwards.**

## 1. HYPOTHESIS

H0: the naked LIT continuation event has no economic edge net of costs.

H1: it has positive expectancy per bet, sufficient to justify a further
engineering cycle on POI / pullback-gap / SCOB / mitigation / obstacle
filtering.

This experiment is allowed to kill the strategy family. A negative result is
reported as a result, not rescued.

## 2. POPULATION — frozen

- **Symbols (60):** the 30 discovery symbols in `research/lit_exit.py::SYMS`,
  plus 30 held-out symbols at turnover ranks 31+ built by
  `research/lit_repl.py::heldout`, which is the construction
  `research/studies/trend_holdout.py` already uses.
- **Timeframes:** Min15, Min30, Min60.
- **History:** 333 days per symbol via `research/deep.py::load_deep`.
- **Warm-up:** the first 500 bars of each series are ineligible.
- **Minimum history:** 2000 bars, else the symbol is dropped.
- **Window split:** at 120 days. `recent` = last 120 days, `older` =
  everything before. Both are reported; see §9 for which is primary.

Survivorship is acknowledged and not corrected: per `research/deep.py`, the
universe is today's most liquid perpetuals walked backwards, which
over-samples coins that went up. Absolute levels are biased optimistic.
Differences between arms on the same rows are not.

## 3. STRUCTURE CONFIGURATION — frozen

`research/lit_v3.py` exactly as committed. No edits during this experiment.

- Policies P1 (close decides), P3, P4 as implemented.
- `M_PB = BRK_BODY` — pullback confirmation on the body, per
  `LIT_STRATEGY_DESIGN.md` for the Stage A build and `LIT_SOURCE.md` Ch.24.
- Depth: **MAIN only**. Internal and Deep are not traded in Stage A.
- No parameter is tuned, swept, or changed because a result looks better.

## 4. ENTRY, STOP, ACTIVE PRICE — frozen

- **Signal:** the `idm_break` event emitted by `lit_v3`.
- **Direction:** with-trend only. Long on a bullish IDM break with BOS locked
  above; short mirrored. Countertrend is Stage A′ and is scored separately.
- **Entry:** the close of the IDM-break bar (`idm_break.entry`). A MARKET
  entry — no limit-fill assumption, no unfilled state.
- **Stop:** the IDM raid extreme (`idm_break.stop`) — the break bar's low for
  a long, its high for a short. **No buffer.**
- **Active Price:** `entry ± (0.5R + round-trip fee expressed in price)`.
  It is **not a target.** It is the level at which a trailing policy arms.
  Below it the initial stop is the only exit.

## 5. FEES — frozen, and a correction to earlier work

The repository's model, from `research/harness.py`:

    FEE_MAKER = 0.010%      FEE_TAKER = 0.022%
    "Fees are charged once per filled trade, in R: FEE_PCT / risk_pct."

`simulate_market` charges taker on entry (a market order), taker on a stop,
maker on a limit target. That split is used unchanged.

**Every earlier LIT measurement used 0.05% per side — 0.10% round trip —
taken from the reference document's Ch.24 default, roughly 3x the repo's
assumption.** That penalised every LIT result. Quantified in
`research/lit_recheck.py`. This experiment uses the repository's model, as
`research/harness.py` requires and as the task specification demands.

Per `harness.py`, the fee is a distribution rather than a constant (VIP tier,
MX deduction, zero-fee promotions), so any conclusion that turns on it is to
be read as a range. Both fee models are therefore reported; the repo model is
primary.

## 6. EXIT POLICIES — frozen, all scored on the SAME setups

Fully specified controls:

| policy | definition |
|---|---|
| `FIXED_1R` | target at +1.0R |
| `FIXED_2R` | target at +2.0R |
| `BOS_TARGET` | target at the locked BOS price |

Experimental source-inspired trails, each armed only at Active Price:

| policy | definition |
|---|---|
| `T6_PIVOT` | stop trails behind each newly confirmed pullback pivot in the trade direction |
| `T6_STRUCTURE` | stop trails behind the most recent structural level (the IDM raid extreme) |

**MFE-fraction trailing is NOT RUN.** It is arbitrary-parameter optimisation
and is excluded by the specification.

## 7. SCORING — frozen

`research/harness.py::simulate_market`, the shared scorer. No private scorer,
no duplicate fee logic.

- **The entry bar resolves nothing** — neither stop nor target. The entry is
  that bar's close, so every tick of it printed before the position existed.
- **Stop is tested before target on every subsequent bar.** Where OHLC cannot
  order the two, the loss is taken. This is the repository's existing
  conservative assumption and it is not relaxed.
- **Trailing levels are read from `trail[k-1]`**, never `trail[k]`: a level is
  only usable once the bar that produced it has closed.
- **A trailing stop never moves against the trade.**
- **Horizon:** 500 bars, then exit at the close as a timeout.

## 8. UNIT OF EVIDENCE — frozen

**The BET, not the trade.** Per `research/studies/fvg_continuation.py::bets`
and six other studies: trades sharing a bar open time are averaged into one
observation. Thirty perpetuals firing long in the same hour are one bet on one
move.

All headline means, standard errors and z-scores are computed over bets.
Trade-level counts are reported alongside but are not the unit of inference.

**This is a correction to earlier LIT work**, which treated every trade as
independent and therefore understated standard error.

## 9. PRIMARY AND SECONDARY ANALYSES — frozen

- **Primary population:** all 60 symbols, all three timeframes, both windows
  pooled, in bets, at the repo fee.
- **Pre-specified secondary breakdowns**, reported whatever they show:
  discovery vs held-out symbols; recent vs older window; per timeframe.
- Secondary cells are descriptive. A positive secondary cell **does not**
  overturn a negative primary result, and will not be presented as one.
- With 5 policies × several breakdowns, some cells will clear 2 SE by chance.
  Only the primary endpoint decides pass/fail.

## 10. PASS / FAIL — frozen BEFORE the numbers exist

**PASS** requires both, on the primary population:

1. At least one fully-specified control (`FIXED_1R`, `FIXED_2R`,
   `BOS_TARGET`) has R/bet > 0 with t ≥ 2.0; and
2. P(realized loss > 1.5R) ≤ 10%.

**FAIL:** all three controls have R/bet ≤ 0 on the primary population.

**INCONCLUSIVE:** anything else — including a positive point estimate that
does not reach t ≥ 2.0.

A trail (`T6_PIVOT`, `T6_STRUCTURE`) counts as an improvement only if its mean
**paired** delta against `BOS_TARGET`, over the same setups, is > 0 with
|z| ≥ 2. A trail cannot convert a FAIL into a PASS: the base event must stand
on a fully-specified control.

**On FAIL or INCONCLUSIVE, work stops.** No progression to pullback-gap, POI,
Decisional/Extreme/Breaker/Flip, mitigation, SCOB, obstacle checking or
position sizing. Those are not rescue tools for a weak base distribution — and
per `LIT_CHANGELOG.md` several have already been measured on the zone-entry
variant and did not rescue it.

## 11. THE DECISIVE DIAGNOSTIC (reported, not a pass criterion)

Among trades that reach Active Price, the distribution of maximum favourable
excursion: median, mean, p25/p50/p75/p90, and the proportion exceeding 1R,
1.5R, 2R, 3R.

The reference strategy is trail-based, so if price reaches +0.5R often but
rarely continues far enough to pay for the losers and the stop overruns, a
trailing strategy has no economic basis regardless of any single arm's mean.

**No threshold is selected from this distribution.** It is diagnostic.

## 12. REALIZED-LOSS REPORTING (reported, one input to pass criterion 2)

P(realized loss > 1.0R / 1.25R / 1.5R / 2.0R), median, p90, p95, worst.

Planned loss is 1R by construction. Realized loss exceeds it through gaps
through the stop. `LIT_SOURCE.md` Ch.24 records the author's own worked
example of a realised loss at 2.5x the planned risk under body-mode stops.

## 13. WHAT REMAINS INFERRED

Named, not silently resolved:

- **T6** — what the trailing stop trails is never stated in the source. Both
  candidates are research policies, not findings.
- **T8** — the with-trend rule conflicts with a source example showing a
  countertrend reaction off a BOS grab. Stage A is with-trend only; Stage A′
  measures the conflict separately and its P&L is never combined.
- **Body&Sweep after a Hidden Shadow rejection** — the active sweep level is
  preserved. Inferred policy.
- **Pine↔Python parity is NOT established.** See §14.

## 14. A HARD BLOCKER, STATED PLAINLY

The specification requires a Pine→Python parity gate before Stage A. **It
cannot be executed in this environment: there is no Pine compiler or
TradingView runtime available here, and `riptide-lit-v2.pine` has never been
compiled.**

What exists instead, and its limits:

- The Python engine reproduces the **reference indicator's own published
  statistics** (ZEC 30m IDM→BOS 65.6% against the reference's 65.0%), which is
  external validation against the thing being modelled rather than against our
  own second implementation.
- Python-side fixture tests can be written and are.
- Agreement between `riptide-lit-v2.pine` and `research/lit_v3.py` is
  **unverified**, and no claim of parity is made anywhere in this work.

Stage A therefore proceeds on the Python engine alone, and its results stand
or fall on that engine. This limitation is not worked around.

---

Date: 2026-09-14
Commit: recorded in `lit_stage_a_out.txt` at run time
Status at the time of writing: **NOT YET RUN**
