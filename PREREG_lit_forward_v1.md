# PRE-REGISTRATION — LIT_FORWARD_V1 (prospective collection)

Committed before the first V1 setup is collected. Collection ships DISABLED.

## 0. AN OPEN PRECONDITION THAT MUST BE READ FIRST

**Pine↔Python parity is NOT established, and it cannot be established in this
environment.** There is no Pine compiler here and `riptide-lit-v2.pine` has
never been compiled. The task specification is explicit that forward evidence
is meaningless if the Python structure definition differs from the validated
Pine reference, and that parity must be completed before collection begins.

It has not been. Therefore:

- This experiment is **built and pre-registered but NOT activated.**
- Activation requires a human to (a) compile the Pine on TradingView, (b)
  compare its setup markers against the Python record on the same symbol and
  timeframe, and (c) record the comparison here before setting the flag.
- One divergence was already found and fixed while writing this document (§9).
  That it existed at all is the argument for doing the check properly.

What external validation DOES exist: the Python engine reproduces the reference
indicator's own published statistics (ZEC 30m IDM→BOS 65.6% against 65.0%).
That is validation against the thing being modelled, not against our Pine.

## 1. HISTORICAL BACKGROUND, AND WHY THE FAMILY IS CLOSED

| stage | what it tested | verdict |
|---|---|---|
| A | naked LIT continuation, raid-extreme stop | INCONCLUSIVE — risk unit broken: 99% of losses exceeded 1R, median hold 1 bar |
| B | five stop definitions | INCONCLUSIVE — stop fixed (median loss 1.02R), and the apparent edge disappeared with it |
| C | T6_PIVOT on untouched symbols, pre-registered | INCONCLUSIVE — standalone +0.114 (t=2.4) passed; paired +0.068 (z=1.5) failed |

`PREREG_lit_stage_c.md` §6 closed the family permanently. **That verdict is
frozen and this document does not reopen it.** Nothing here re-slices history,
pools samples, re-tunes T6_PIVOT, alters Active Price, tries another trail,
changes entry or stop, filters symbols, or adds FVG/POI/SCOB.

The only honest remaining source of evidence is time that has not happened yet.

## 2. HYPOTHESIS AND PRIMARY OUTCOME

H0: T6_PIVOT adds no incremental value over the frozen control on genuinely
unseen setups.

**Primary variable, one number:**

    paired_delta_R = t6_pivot_R − control_R

measured on the SAME setup — one entry, one initial stop, two hypothetical
exits. Standalone T6 is SECONDARY.

**Why paired is primary.** Stage C found T6 standalone positive (+0.114) while
the control was also positive (+0.047). A standalone number cannot separate
"the trail works" from "the setup drifted up". Only the same-setup difference
isolates the trail.

## 3. THE FROZEN SETUP — copied literally from Stage C, not recalled

Source of truth: `research/studies/lit_stage_c.py::run_symbol` and
`PREREG_lit_stage_c.md` §3. **They were compared before implementation and they
AGREE**; had they disagreed the instruction was to stop and report.

- **Structure:** `research/lit_v3.py`, imported not copied. MAIN depth only.
- **Signal:** an `idm_break` event.
- **Direction:** with-trend only — the locked BOS must lie beyond the entry.
- **Entry:** the CLOSE of the IDM-break bar, as a MARKET order. No limit-fill
  assumption and no unfilled state.
- **Stop:** the PRIOR confirmed pullback pivot — the most recent pivot IS the
  IDM being broken, so the stop is the one behind it, scoped to the current
  cycle. **No buffer.** Where none exists the setup is SKIPPED, never given a
  substitute.
- **Active Price:** `entry ± (0.5R + round-trip fee in price)`. It ARMS the
  trail. It is **not** a target.

## 4. THE FROZEN CONTROL

`BOS_TARGET` — exit at the locked BOS price. Same entry, same initial stop,
same scorer. It is the comparator and it is not adjusted for any reason.

## 5. THE FROZEN PRIMARY ARM

`T6_PIVOT` — no fixed target; once Active Price is reached the stop follows
each newly confirmed pullback pivot in the trade direction and never moves
against the position.

**A parity detail that matters**: the TRAIL pivot forward-fills ACROSS
structural cycles (`research/studies/lit_stage_a.py::trails`), while the STOP
pivot is scoped to the current cycle. They are different accumulators. §9
records that conflating them was a real defect.

## 6. SCORING, FEES, HORIZON, SAME-BAR

- **Scorer:** `research/harness.py::simulate_market`. Shared, not duplicated.
- **Fees:** the repo's frozen model — `FEE_MAKER` 0.010%, `FEE_TAKER` 0.022%,
  maker/taker split. Unchanged mid-experiment. No funding or slippage estimate
  is added; if that ever changes it is V2.
- **Same-bar:** the entry bar resolves nothing; thereafter the stop is tested
  before the target. Where OHLC cannot order two events the loss is taken.
- **Horizon:** 500 bars, exactly Stage C.
- **Timeout:** a `timeout` from the scorer at the live edge means "ran out of
  candles", NOT "reached the horizon". It is only accepted as an exit once 500
  bars have genuinely elapsed. **Open positions are never marked to market.**
  This project produced one such false positive (+0.360 R/bet that was 58
  capped positions); `forward.score_pair` makes it structurally impossible.

## 7. UNIT OF EVIDENCE

The **bet**, via `riptide/decide.py::event_span` — the project's existing
event definition, reused rather than reimplemented. Correlated same-window
same-direction signals across symbols and timeframes are ONE observation.
Raw setups, resolved setups and independent bets are all reported; inference
uses bets.

No event-pick ranking filters the sample: Stage C did not use one, so V1 must
not. Event-pick metadata may be recorded for later analysis and must not alter
inclusion.

## 8. POWER — computed before activation, and it is the uncomfortable part

Stage C's paired delta: +0.068 R/bet, SE 0.047 on 3027 bets, so the per-bet
standard deviation is **2.586 R**.

**Rate, corrected after measurement.** An earlier draft used Stage C's own
9.1 bets/day, which came from its 55-symbol research universe. Production
scans `TOP_N=120` across three timeframes. Measured directly — 880 setups over
39 symbol-timeframes x 333 days — the rate is **0.068 setups per
symbol-timeframe-day**, independently matching the 0.074 implied by Stage C's
4090 setups. Live that is **~24 setups/day, ~18 bets/day**.

Only the calendar estimates below change. **The checkpoints are defined in
BETS and they do not move.**

    bets      SE    MDE@z=2   z at +0.068   z at +0.120
     250   0.164     0.327        0.42          0.73
     500   0.116     0.231        0.59          1.04
    1000   0.082     0.164        0.83          1.47
    2000   0.058     0.116        1.18          2.08

    to reach z=2 at +0.068 (the Stage C estimate):  5,784 bets ≈ 320 days
    to reach z=2 at +0.120 (the Stage B estimate):  1,857 bets ≈ 103 days
    to reach z=2 at +0.200:                           669 bets ≈  37 days

**STATE THIS PLAINLY: if the true effect is the size Stage C measured, this
experiment cannot resolve it in under about 320 days.** Setting a bar that
requires it would repeat the Stage C mistake of a threshold the sample cannot
reach. The checkpoints below are therefore chosen to be powered for the
**Stage B** effect size, and the final read is explicitly a statement about
effects of that size or larger — not about zero.

## 9. FIXED REVIEW CHECKPOINTS — set now, not later

| # | resolved bets | ≈ elapsed | what happens |
|---|---|---|---|
| 1 | 250 | ~2 weeks | **Health check only.** Guards, data integrity, bet rate. NO efficacy read, and the paired delta is not even looked at for a decision. |
| 2 | 1000 | ~8 weeks | **Futility check only.** If the paired delta is ≤ −0.10, stop early: that is a wrong-direction result large enough to matter. Otherwise continue. No success claim is available here. |
| 3 | 1857 | ~15 weeks | **THE READ.** The only checkpoint at which V1 can be closed as supported or not. |

**No other evaluation is permitted.** Recomputing a decision daily and stopping
when significance appears is optional-stopping bias; `/stats` therefore reports
`COLLECTING` and never a verdict.

## 10. THE DECISION RULE — fixed before any data exists

At checkpoint 3, **both** required:

1. **Standalone not pathological:** T6 R/bet > 0, AND P(realized loss > 1.5R)
   ≤ 10%, AND timeout exits ≤ 20% of resolved setups.
2. **Paired incremental:** mean `paired_delta_R` > 0 with **z ≥ 2.0**.

**SUPPORTED:** both met. The claim is then narrow — *on forward data, the
pivot trail added measurable incremental value over the frozen control* — and
it still does not authorise trading, sizing, or a production release.

**NOT SUPPORTED:** either unmet. V1 closes and the LIT trading family stays
closed.

A null at checkpoint 3 means **"no effect of magnitude ≳0.12 R/bet was
detected"**, not "the effect is zero". §8 is why.

## 11. GUARDS, REPORTED THROUGHOUT AND NEVER OPTIMISED TOWARD

Realized loss: P(>1.0R), P(>1.25R), P(>1.5R), P(>2.0R), median, p90, p95,
worst. Timeout contribution tracked separately. These are tripwires, not
targets.

## 12. IMMUTABILITY

`LIT_FORWARD_V1` is frozen from activation. Every stored setup carries
`strategy_version` and `rules_hash` (a hash over the frozen rules dict, so
reformatting a comment cannot invalidate a live experiment but changing a rule
must).

Once recorded, identity, entry, stop, version and rules_hash NEVER change.
Outcome fields move only `pending → resolved` or `pending → timed_out`.

**Any material rule change is `LIT_FORWARD_V2`. V1 and V2 results are never
pooled.** No rule changes because ten setups went badly, twenty went well, the
regime shifted, one symbol looks strong, or a parameter looks attractive.

## 13. NO RETROACTIVE SURVIVORSHIP

Universe membership is stored as it was at signal time. Delisted, thinned or
poorly-performing symbols are never dropped afterwards. No symbol
leaderboards — symbol-ranking persistence has already failed elsewhere in this
repository and V1 is not permission to reopen it. No regime filters of any
kind.

## 14. NO BACKFILL

`forward_start_timestamp` is stamped once at activation and is idempotent
across restarts. Any setup with `signal_time ≤ start` is REJECTED, not
recorded. Old candles may not manufacture forward evidence.

## 15. WHAT IS EXPLICITLY NOT BUILT

PullbackGap/FVG, Decisional/Extreme/Breaker/Flip POI, mitigation, SCOB,
obstacle filtering, position sizing. The historical family is closed and none
of these is justified as an improvement by the current evidence.

No exchange API, no order placement, no execution, no automated trading.

## 16. ACTIVATION

Two flags, both shipping `0`:

    RIPTIDE_LIT_FORWARD=1          # collection
    RIPTIDE_LIT_FORWARD_ALERTS=1   # optional research alerts

Neither is enabled by this work. §0's parity check should be completed first.

---

Date: 2026-09-14
Rules hash at registration: `4b105c593bc48469`
Status: **PRE-REGISTERED — NOT ACTIVATED**
