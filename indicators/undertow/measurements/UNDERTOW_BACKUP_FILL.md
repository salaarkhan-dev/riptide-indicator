# The backup fill: the first real signal in Undertow, and it is given straight back

Against [`PREREG_undertow_backup_fill.md`](../prereg/PREREG_undertow_backup_fill.md).
23 symbols, 12,000 bars each, 15m / 30m / 1h, `maxLive 64`, 7bp fees, the
shipped config (swing 6/2, rr 3.5). Metric: **mean R per ARMED SETUP** — the one
denominator the backup cannot move.

> **CORRECTED.** The first publication of this page keyed each setup by
> `(symbol, arming bar)`. Two candidates can arm on the same bar — a pullback
> holds several pins and their confirmations can land together — and a panel
> spans both halves of every symbol, each indexed from 0. So the key collided
> twice over, collapsing ~19% of the denominator and mismatching a handful of
> trades. The key is now `(symbol, quadrant, pin bar, arming bar)`, verified
> collision-free. **Every number below is the corrected one and no conclusion
> changed.** How the bug was found is at the bottom of this page; it is the
> most useful thing on it.

## The headline

| tf | B3 − B0 | ± | z | B3 − C (control) | armed |
|---|---|---|---|---|---|
| Min15 | +0.026 | 0.047 | +0.55 | +0.030 | 4442 |
| Min30 | +0.033 | 0.035 | +0.94 | +0.017 | 4474 |
| Min60 | +0.027 | 0.040 | +0.68 | +0.023 | 4538 |

**Positive on all three. Significant on none.** Bar 3 (≥ +0.05 at |z| ≥ 2)
failed everywhere, and bar 4 failed too: the OB/FVG zones did not beat a
midpoint control that keeps the trigger and the cap and throws the zone
detection away.

Bars 1, 2, 5 and 6 passed — coverage, not confounded, positive on 3 of 3, and
survives dropping the biggest symbol.

## The decomposition, which is the actual finding

Every armed setup matched across the two arms by `(symbol, quadrant, pin bar, arming bar)`:

| tf | ADDED — trades that would not have happened | PRE-EMPTED — a worse price on a trade that was going to happen |
|---|---|---|
| Min15 | **470 @ +0.555 ± 0.153** (z +3.6) · +261 R | **573 @ −0.245 ± 0.047** (z −5.2) · −141 R |
| Min30 | **516 @ +0.663 ± 0.108** (z +6.2) · +342 R | **605 @ −0.314 ± 0.044** (z −7.1) · −190 R |
| Min60 | **550 @ +0.564 ± 0.110** (z +5.1) · +310 R | **649 @ −0.284 ± 0.043** (z −6.6) · −185 R |

Clustered by symbol, and **both halves are individually significant on all
three timeframes at |z| of 4 to 7.** That is the first strongly significant
result anywhere in this indicator, and there are two of them, pointing in
opposite directions.

**A setup that arms, runs 1R away without filling, and then retraces into a
zone is worth about +0.6 R.** Consistently, on 470–550 trades per timeframe,
at z ≥ 3.6. That is not noise and it is not small.

**Taking the same zone when price was going to come back to the Focus anyway
costs about −0.27 R.** Also consistent, also significant, and it happens ~1.4
times as often.

+0.6 × 510 against −0.28 × 610 is roughly +300 against −170. The net is real
and it is +0.03 R per armed setup, which is nothing.

## WHY YOU CANNOT JUST TAKE THE GOOD HALF

This is the part that matters and it is easy to get wrong.

At the moment the backup fills, **you do not know which half you are in.**
Whether a setup is ADDED or PRE-EMPTED depends on whether price would later
have returned to the Focus line — which is in the future at the moment of
entry. The split is a *post-hoc decomposition that explains the net*, not a
rule anyone can trade.

The tradeable quantity is the net: **+0.026 to +0.033 R per armed setup,
z 0.55 to 0.94.** Everything else on this page is diagnosis.

## The mechanism is confirmed three separate ways

If pre-emption is the tax, then anything that reduces the number of backups
without losing the ADDED ones should score better. Three descriptive arms say
the same thing:

| arm | backups (15m/30m/1h) | vs B0 |
|---|---|---|
| **B4** trigger 0.5 — arms earlier, far more backups | 1910 / 2036 / 2040 | −0.001 / +0.021 / **−0.033** |
| **B3** trigger 1.0 | 1070 / 1148 / 1229 | +0.023 / +0.028 / +0.019 |
| **B5** trigger 2.0 — arms later, almost none | 134 / 182 / 184 | +0.009 / +0.007 / +0.006 |
| **B2** FVG only — fewer zones than B3 | 664 / 691 / 762 | +0.023 / **+0.032** / **+0.044** |

Arming earlier makes it worse. Arming later makes it vanish. The arm with the
*fewest* zones (FVG only) beat the arm with the most on two of three. Every one
of those is what "pre-emption is the cost" predicts.

## And the zones themselves are doing nothing

`B3 − C` was +0.030, +0.017, +0.023 — all inside 1 SE. Entering at the
**midpoint** between the trigger bar's extreme and the Focus, with no order
block and no fair-value gap anywhere in it, scores the same as entering at a
detected zone.

So the order-block and FVG machinery — the thing the original spec asked for,
including the better OB detection — is **decoration on top of "enter later into
a running move."** That is now the fourth component of Undertow to be ablated
and found inert, after the candle taxonomy, the location and the exit rule.

## Against the prediction

Recorded before the run, in the prereg:

| predicted | actual | |
|---|---|---|
| ADDED +0.2 to +0.5 R | **+0.56 to +0.67** | **wrong — I underestimated it** |
| PRE-EMPTED −0.1 to −0.3 R | −0.23 to −0.29 | right |
| net within ±0.05, bar 3 fails | +0.026 to +0.033, failed | right |
| the control matches the zones | it does | right |

The one I got wrong is the one worth having got wrong.

## What this changes

**Nothing ships differently yet.** The backup stays off by default in the Pine
and absent from the watch. A component that is positive on three panels and
significant on none, and that loses to its own control, has not earned a
default.

## The one question this opens, and it is a good one

Pre-emption exists **only because the zone sits between the market and the
Focus while the Focus limit is still live.** There is a mechanical way to
remove it entirely:

> **Place the backup only after the Focus limit has expired.** Then every
> backup is an ADDED trade by construction, and the −0.27 R tax cannot be paid,
> because there is no trade left to pre-empt.

The cost is that the zone touch has to happen *after* `fillBars`, which
discards some of the +0.6 R trades that fill inside the window. Whether what
survives is worth more than the +0.03 R the current design nets is exactly the
kind of thing that can be measured, and it is the first hypothesis in this
project that came out of a significant result rather than out of a chart.

It has now been run:
[`UNDERTOW_LATE_BACKUP.md`](UNDERTOW_LATE_BACKUP.md). The answer is no, and the
reason is structural rather than statistical.

---

## How the keying bug was found, because it is the reusable part

Not by review. The late-backup prereg contained a bar that was **not a test of
the hypothesis at all**:

> **NOT CONFOUNDED.** … and **L1's PRE-EMPTED count must be exactly 0**. A
> non-zero pre-emption in a design where it is impossible means the
> implementation does not match this document and the run is VOID.

Pre-emption cannot happen in the late design — the Focus limit is cancelled
before the backup is placed. The study reported **1**. That single impossible
count was the only visible symptom of a keying bug that was silently present in
this study too, and it took two rounds to clear: first the quadrant, then the
pin bar.

**Write down what must be impossible, not only what you expect.** An
expectation that fails tells you the world is surprising; an impossibility that
fails tells you the code is wrong, and nothing else in either study would have
said so.
