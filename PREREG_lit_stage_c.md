# PRE-REGISTRATION — LIT Stage C (the trailing exit, on untouched symbols)

Frozen before the experiment is run. Committed before any Stage C return
exists.

Shared machinery — structure config, entry, Active Price, scorer, fees, unit
of evidence — is inherited unchanged from `PREREG_lit_stage_a.md`. The stop is
inherited from `PREREG_lit_stage_b.md`. Only what differs is restated.

## 0. THIS IS THE THIRD PRE-REGISTRATION AND THAT IS A PROBLEM

`PREREG_lit_stage_b.md` §5 closed the family on an INCONCLUSIVE verdict and
said explicitly that a further pre-registration would be "fitting by
iteration, which is the thing this process exists to prevent."

**Stage C is that further pre-registration.** It exists because the trailing
arms were the best cells in Stage B (T6_PIVOT +0.145, t=2.5) and a human
decided the lead was worth one clean test. That is a legitimate call for a
person to make; it is not a loophole, and it is not this process deciding on
its own momentum. But the honest accounting is:

- This is the **weakest-blinded** of the three pre-registrations. The
  hypothesis exists *because* of a number I have already seen.
- It gets **one** test. Whatever the outcome, there is no Stage D. A fourth
  pre-registration on the same family would be indefensible and this document
  commits against it.

What is genuinely frozen: the population (§2), the primary arm (§3), the
thresholds (§6), and the two disqualifiers (§5), all fixed before any Stage C
return is computed.

## 1. HYPOTHESIS

H0: the trailing exit has no edge over a fully-specified control on symbols
that took no part in Stages A or B.

H1: the Stage B trail result replicates on untouched symbols.

This is a **replication**, not a discovery. The effect size to replicate is
+0.145 R/bet against a BOS_TARGET control, from Stage B's primary stop.

## 2. POPULATION — frozen, and a correction to what "held-out" means here

**The previous "held-out" set is NOT out of sample and will not be used as
one.** Turnover ranks 31-60 were inside Stages A and B; the +0.145 was
computed partly from them. Calling them held-out now would be false.

Stage C uses the **untouched tier**: every symbol in the ranked turnover
universe that appears in neither `lit_exit.SYMS` (discovery, 30) nor the
rank-31+ set used by Stages A and B. At the time of writing that is **55
symbols**, none of which has contributed a single number to this project.

Everything else follows Stage A: Min15/Min30/Min60, 333 days of deep history,
500-bar warm-up, ≥2000 bars, MAIN depth, with-trend only.

Stage A/B symbols are re-run alongside purely as a **reproduction check** —
to confirm the pipeline still returns Stage B's numbers — and play no part in
the verdict.

## 3. ARMS — frozen

Stop is fixed at **`PRIOR_PB`**, Stage B's primary. It is not varied. Stage B
established it gives a real risk unit (median realized loss 1.02R,
P(>1.5R) = 1.9%) and there is no third stop search.

| arm | role |
|---|---|
| `T6_PIVOT` | **PRIMARY.** Stop trails behind each newly confirmed pullback pivot in the trade direction, armed at Active Price. |
| `BOS_TARGET` | **CONTROL.** The paired comparison base, as in Stages A and B. |
| `T6_STRUCTURE` | secondary. Trails the most recent structural level. |
| `FIXED_1R`, `FIXED_2R` | secondary, reported for continuity. |

**Why `T6_PIVOT` is the primary, stated so it can be audited.**
`LIT_STRATEGY_DESIGN.md` designates T6 `pivot` as the **DEFAULT** trail, and
has since before any trail was measured. That is a pre-existing, non-outcome
basis for the choice.

**It is also the arm that scored highest in Stage B (t=2.5 against
T6_STRUCTURE's 2.2), and I am disclosing that rather than resting on the
design-doc rationale alone.** The two coincide. A reader should treat the
designation as partly contaminated and weight the result accordingly.

## 4. POWER — computed before the run, and it changes the threshold I proposed

I told the user the threshold would be set "higher than 2.5". **The power
calculation refutes that and I am not using it.**

Stage B's T6_PIVOT: +0.145 R/bet, SE 0.059, 3195 bets. SE scales as 1/√n:

    bets    SE      t at the observed effect    MDE at t=2.0
    2000  0.0746            1.9                     0.149R
    2500  0.0667            2.2                     0.133R
    3000  0.0609            2.4                     0.122R
    4770  0.0483            3.0                     0.097R

Reaching t ≥ 3.0 needs about **4770 bets** — more than Stages A and B produced
on the full 60-symbol population. A 55-symbol tier will not reach it. **A
t ≥ 3.0 bar would therefore return FAIL even if the effect is exactly as large
as observed**, which is a badly designed experiment, not a strict one.

The bar is kept high a different way: **two conditions, both required** (§6),
which jointly is stricter than a single t ≥ 2.5 while staying inside the
power the data can supply.

**UNDERPOWER DECLARATION.** If the run yields **fewer than 2000 bets** on the
primary arm, the experiment is declared **UNDERPOWERED** and a null result is
reported as uninformative — not as evidence of absence. The achieved bet
count, SE and MDE are reported either way.

## 5. TWO DISQUALIFIERS — frozen, and they override any R

Checked before the verdict. If either trips, the result is **CONFOUNDED**
regardless of how good the returns look.

1. **Mark-to-market.** If more than **20%** of primary-arm trades exit at the
   horizon timeout rather than at a stop, the arm is valuing open positions at
   an arbitrary cutoff. This project has already produced one such false
   positive — "hold with no target" at +0.360 R/bet, of which the entire
   result was 58 positions marked at the 500-bar cap. In Stage B's trail this
   ran at 5.2% with a +0.001R contribution, so the guard is expected to pass;
   it is registered because it is the specific way this measurement could lie.

2. **Broken risk unit.** P(realized loss > 1.5R) must be ≤ 10%, the criterion
   that caught Stage A. Expected to pass at the `PRIOR_PB` stop.

## 6. PASS / FAIL — frozen BEFORE any Stage C return exists

Judged on `T6_PIVOT`, untouched tier, in bets. **Both required:**

1. R/bet > 0 with **t ≥ 2.0**; and
2. Mean **paired** delta against `BOS_TARGET`, over the same setups, > 0 with
   **z ≥ 2.0**.

**PASS:** both met, and neither disqualifier in §5 tripped.

**FAIL:** R/bet ≤ 0, or the paired delta ≤ 0.

**INCONCLUSIVE:** positive on both but short of the thresholds — or
underpowered per §4.

Secondary arms are descriptive. `T6_STRUCTURE` outperforming `T6_PIVOT` does
**not** convert a FAIL into a PASS; the primary was designated in §3 and does
not move.

**WHAT FOLLOWS EITHER WAY.**

- On **PASS**, the claim is narrow and must stay narrow: *a pivot-trailing
  exit on the naked LIT continuation replicated on untouched symbols at a
  magnitude consistent with Stage B.* It is not "LIT is profitable". It would
  justify one engineering cycle — a Pine implementation and forward-recorded
  alerts — and nothing is traded on it.
- On **FAIL or INCONCLUSIVE**, the LIT trading family is closed permanently.
  No Stage D, no further variants, no re-registration.

## 7. LIMITS CARRIED OVER UNCHANGED

- **Pine↔Python parity is NOT established** and cannot be here: no Pine
  compiler exists in this environment and `riptide-lit-v2.pine` has never been
  compiled. No parity claim is made.
- **T6 itself remains an open [GAP]** in the source — what the trailing stop
  trails is never stated. Both trail definitions are research policies. A PASS
  would not resolve the [GAP]; it would only say one guess pays.
- **T8 remains unresolved** — the countertrend target does not exist in the
  Python event stream at grab time.
- **A known engine defect:** a minority of symbols emit almost no structure
  (1 IDM break over 333 days against a median of 28.5). They contribute
  ~nothing rather than distorting. The untouched tier is lower-liquidity than
  the discovery set, so this may be **more** common there; the per-symbol
  event counts are reported.
- Survivorship in the deep window is uncorrected and biases absolute levels
  optimistic. The untouched tier is lower-liquidity and therefore **more**
  exposed to it, which is a reason to distrust a strongly positive level here
  while still trusting the paired difference.

---

Date: 2026-09-14
Commit: recorded in `lit_stage_c_out.txt` at run time
Status at the time of writing: **NOT YET RUN**
