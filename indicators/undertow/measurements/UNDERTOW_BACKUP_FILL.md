# The backup fill: the first real signal in Undertow, and it is given straight back

Against [`PREREG_undertow_backup_fill.md`](../prereg/PREREG_undertow_backup_fill.md).
23 symbols, 12,000 bars each, 15m / 30m / 1h, `maxLive 64`, 7bp fees, the
shipped config (swing 6/2, rr 3.5). Metric: **mean R per ARMED SETUP** — the one
denominator the backup cannot move.

## The headline

| tf | B3 − B0 | ± | z | B3 − C (control) | armed |
|---|---|---|---|---|---|
| Min15 | +0.023 | 0.041 | +0.56 | +0.034 | 3737 |
| Min30 | +0.028 | 0.036 | +0.78 | +0.023 | 3701 |
| Min60 | +0.019 | 0.035 | +0.54 | +0.012 | 3783 |

**Positive on all three. Significant on none.** Bar 3 (≥ +0.05 at |z| ≥ 2)
failed everywhere, and bar 4 failed too: the OB/FVG zones did not beat a
midpoint control that keeps the trigger and the cap and throws the zone
detection away.

Bars 1, 2, 5 and 6 passed — coverage, not confounded, positive on 3 of 3, and
survives dropping the biggest symbol.

## The decomposition, which is the actual finding

Every armed setup matched across the two arms by `(symbol, arming bar)`:

| tf | ADDED — trades that would not have happened | PRE-EMPTED — a worse price on a trade that was going to happen |
|---|---|---|
| Min15 | **388 @ +0.558 ± 0.129** (z +4.3) · +216 R | **541 @ −0.230 ± 0.041** (z −5.6) · −125 R |
| Min30 | **411 @ +0.668 ± 0.103** (z +6.5) · +274 R | **599 @ −0.283 ± 0.040** (z −7.1) · −169 R |
| Min60 | **436 @ +0.570 ± 0.105** (z +5.4) · +248 R | **597 @ −0.288 ± 0.040** (z −7.2) · −172 R |

Clustered by symbol, and **both halves are individually significant on all
three timeframes at |z| of 4 to 7.** That is the first strongly significant
result anywhere in this indicator, and there are two of them, pointing in
opposite directions.

**A setup that arms, runs 1R away without filling, and then retraces into a
zone is worth about +0.6 R.** Consistently, on ~400 trades per timeframe, at
z ≥ 4. That is not noise and it is not small.

**Taking the same zone when price was going to come back to the Focus anyway
costs about −0.27 R.** Also consistent, also significant, and it happens ~1.4
times as often.

+0.6 × 400 against −0.27 × 580 is roughly +240 against −155. The net is real
and it is +0.02 R per armed setup, which is nothing.

## WHY YOU CANNOT JUST TAKE THE GOOD HALF

This is the part that matters and it is easy to get wrong.

At the moment the backup fills, **you do not know which half you are in.**
Whether a setup is ADDED or PRE-EMPTED depends on whether price would later
have returned to the Focus line — which is in the future at the moment of
entry. The split is a *post-hoc decomposition that explains the net*, not a
rule anyone can trade.

The tradeable quantity is the net: **+0.02 to +0.03 R per armed setup, z ≈ 0.6.**
Everything else on this page is diagnosis.

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

`B3 − C` was +0.034, +0.023, +0.012 — all inside 1 SE. Entering at the
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
| net within ±0.05, bar 3 fails | +0.019 to +0.028, failed | right |
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
survives is worth more than the +0.02 R the current design nets is exactly the
kind of thing that can be measured, and it is the first hypothesis in this
project that came out of a significant result rather than out of a chart.

It needs its own pre-registration. It has not been run and nothing here should
be read as predicting it.
