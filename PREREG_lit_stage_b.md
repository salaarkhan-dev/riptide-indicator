# PRE-REGISTRATION — LIT Stage B (the stop definition)

Frozen before the experiment is run. Committed before any Stage B P&L exists.

Shared machinery — population, structure config, entry, scoring, fees, unit of
evidence — is inherited unchanged from `PREREG_lit_stage_a.md`. Only what
differs is restated here.

## 0. HONESTY ABOUT CONTAMINATION

**This document is written after seeing Stage A's results, and that is a real
weakness, not a formality.** Stage A returned INCONCLUSIVE because its stop —
the IDM raid extreme with no buffer — produced a risk unit that 99% of losses
exceeded. Stage B exists because of that finding. It is a follow-up
hypothesis, not an independent one, and it should be read as one.

What is genuinely frozen: **the thresholds in §5, and the choice of primary
stop policy in §3, both fixed before any Stage B return is computed.**

**The primary stop policy was selected on GEOMETRY, not on returns.** The
selection input was stop width and the resulting fee-in-R — properties of the
setup that contain no P&L information. The measurement that drove it is
reproduced in §2 so it is auditable. No Stage B expectancy, win rate or R was
computed before this document was committed.

## 1. WHAT STAGE A ESTABLISHED, AND WHAT IT DID NOT

Established: the raid-extreme stop is not viable. Median width 0.42% of price,
0.18% at the first quartile, 99% of losses exceeding the planned 1R, median
hold one bar, worst loss 22.45R.

Not established: that the entry event is worthless. Among the 60% of setups
reaching Active Price, median MFE was 1.91R and 48.3% exceeded 2R. Favourable
excursion exists. The risk unit underneath it was broken.

H0: with a structurally-defined stop, the naked LIT continuation event still
has no economic edge net of costs.

H1: it does, and Stage A's failure was located entirely in the stop.

## 2. THE GEOMETRY MEASUREMENT THAT SELECTED THE PRIMARY — no P&L

Discovery symbols, first 12, Min30, 333 days, 237 IDM breaks. Repo round-trip
fee 0.032%. "usable" = the level lies on the correct side of the entry.

    stop policy    usable   median width      p25    fee/R
    RAID              97%         0.516%   0.221%   0.062R
    IDM_PIVOT         52%         0.472%   0.224%   0.068R
    PRIOR_PB          77%         3.203%   1.551%   0.010R
    LEG               92%         8.359%   3.392%   0.004R
    CHOCH             95%        13.934%   8.582%   0.002R

**The IDM pivot stop — the one this experiment was requested to test — does
not fix the problem and cannot be the primary.** For a long the IDM pivot sits
ABOVE the raid low, because the raid is the sweep through that pivot. So it is
*narrower* than the stop it was meant to replace (0.472% against 0.516%), and
it is usable on only 52% of setups. It is registered and run anyway, as a
named secondary, because it was asked for and because recording that it fails
is worth more than quietly dropping it.

**PRIOR_PB is the primary:** the tightest structural level whose risk unit is
not dominated by costs (fee 0.010R against RAID's 0.062R), at 77% coverage.
LEG and CHOCH are wider and also registered; a wider stop buys a sane risk
unit at the price of fewer R per win, and which side of that trade-off pays is
the thing being measured.

## 3. STOP POLICIES — frozen

All are evaluated on the SAME setups, so differences are attributable to the
stop alone. A setup whose level is missing or on the wrong side of the entry
is SKIPPED for that policy and the skip is reported.

| policy | definition |
|---|---|
| `RAID` | **control.** The IDM raid extreme — Stage A's stop, reproduced for direct comparison. |
| `IDM_PIVOT` | *secondary, requested.* The IDM level itself: the confirmed pullback pivot whose break is the signal. |
| `PRIOR_PB` | **PRIMARY.** The second-most-recent confirmed pullback pivot in the trade direction within the current structural cycle. The most recent one is the IDM, so this is the structural level behind it. |
| `LEG` | *secondary.* The deepest confirmed pullback pivot of the current leg — the low of a bullish leg, mirrored for bearish. |
| `CHOCH` | *secondary.* The CHoCH level: the price at which the trend thesis is structurally invalidated. |

No buffer is added to any of them. No policy is tuned.

## 4. EVERYTHING ELSE — inherited unchanged from PREREG_lit_stage_a.md

Population (60 symbols, Min15/Min30/Min60, 333 days, 500-bar warm-up), MAIN
depth, with-trend only, entry at the IDM-break bar close as a MARKET order,
Active Price at `entry ± (0.5R + fee)` arming a trail and never a target, the
five exit policies (`FIXED_1R`, `FIXED_2R`, `BOS_TARGET` as fully-specified
controls; `T6_PIVOT`, `T6_STRUCTURE` armed at Active Price; **MFE-fraction not
run**), scoring through `research/harness.py::simulate_market` with the repo's
maker/taker fees, entry bar resolves nothing, stop tested before target,
horizon 500 bars, and **the BET as the unit of evidence**.

## 5. PASS / FAIL — frozen BEFORE any Stage B return exists

Judged on the **PRIMARY stop policy (`PRIOR_PB`)**, primary population.

**PASS** requires both:

1. At least one fully-specified control exit (`FIXED_1R`, `FIXED_2R`,
   `BOS_TARGET`) has R/bet > 0 with **t ≥ 2.5**. The threshold is raised from
   Stage A's 2.0 because three exits are tested on the primary stop, and a
   2.0 bar across three tests is not a 2.0 bar.
2. P(realized loss > 1.5R) ≤ 10% — the criterion Stage A failed, unchanged.

**FAIL:** all three control exits have R/bet ≤ 0 on the primary stop policy.

**INCONCLUSIVE:** anything else, including a positive estimate short of
t ≥ 2.5.

A criterion-3 style fee gate is **not** imposed, because it would not be a
test: `PRIOR_PB` already clears any sane version of it by construction
(0.010R), as §2 shows. It is stated only so the comparison against `RAID` and
`IDM_PIVOT` is legible.

The four secondary stop policies are **descriptive**. A secondary policy
outperforming the primary does NOT convert a FAIL or INCONCLUSIVE into a PASS,
and will not be presented as a result. With 5 stops × 3 control exits, some
cells will clear 2 SE by chance; only the primary cell decides.

**On FAIL or INCONCLUSIVE, the LIT trading family is closed.** No progression
to pullback-gap, POI, Decisional/Extreme/Breaker/Flip, mitigation, SCOB,
obstacle checking or position sizing, and no further stop variants: a third
pre-registration after a second failure would be fitting by iteration, which
is the thing this process exists to prevent.

## 6. WHAT IS REPORTED REGARDLESS

Per stop policy and exit policy: setups, skips, trades, bets, R/bet, SE, t,
win rate, profit factor, total R, max drawdown, recovery factor.

Realized-loss distribution: P(loss > 1.0R / 1.25R / 1.5R / 2.0R), median, p90,
p95, worst — the diagnostic that caught Stage A.

Stop width in % of price and fee-in-R per policy, so the geometry in §2 is
confirmed on the full population rather than the 12-symbol subsample.

MFE beyond Active Price among setups that reach it, and Active Price reach
rate — the decisive diagnostic from `PREREG_lit_stage_a.md` §11.

Paired deltas of every exit against `BOS_TARGET` on the primary stop.

## 7. LIMITS THAT CARRY OVER UNCHANGED

- **Pine↔Python parity is NOT established** and cannot be in this environment:
  there is no Pine compiler here and `riptide-lit-v2.pine` has never been
  compiled. No parity claim is made.
- **A known engine defect:** 4 of 28 discovery symbols emit almost no
  structure on Min30 (1 IDM break over 333 days against a median of 28.5).
  They contribute ~nothing rather than distorting, but the defect is real,
  unexplained, and recorded here rather than discovered later.
- **T6 remains unresolved** — what the trailing stop trails is never stated in
  the source, and both trail policies are research policies, not findings.
- **T8 remains unresolved** — the countertrend target does not exist in the
  Python event stream at grab time; see `lit_stage_a_prime_out.txt`.
- Survivorship in the deep window is acknowledged and uncorrected; absolute
  levels are biased optimistic, differences between arms on the same rows are
  not.

---

Date: 2026-09-14
Commit: recorded in `lit_stage_b_out.txt` at run time
Status at the time of writing: **NOT YET RUN**
