# PRE-REGISTRATION — is the OB/FVG backup fill worth taking?

Committed before the first number. Run by
`indicators/undertow/studies/undertow_backup.py`.

## The decision this is for

The backup fill was in the original design and was the last thing built. It is
now implemented in the Pine and the port, **off by default**, and nothing about
it has been measured.

It is the one remaining component with a plausible mechanism.
[`UNDERTOW_EXITS.md`](../measurements/UNDERTOW_EXITS.md) showed the average
setup's best price is **+2.5 R** while the realised result is zero — a real
excursion nobody captures. A large part of that is setups where the move
happened and the limit at the Focus line was never touched. The backup exists
to convert those.

## THE DENOMINATOR IS THE WHOLE DESIGN, so it is fixed first

The backup **changes the number of trades**. Comparing mean R *per trade*
between an arm with 73 trades and an arm with 91 would be meaningless: more
trades at a lower mean can still be more money, and fewer trades at a higher
mean can still be less.

**The primary metric is mean R per ARMED SETUP.** `nArmed` is identical in both
arms by construction — the backup lives entirely downstream of arming, and
`indicators/undertow/tests/test_undertow_port.py` already asserts that the
setups found, the setups armed and the bias cancellations are untouched. An
unfilled setup contributes 0. That makes the two arms directly subtractable.

Mean R per trade is reported as a secondary, labelled as such.

## AND THE BACKUP IS NOT ONE THING, so it is decomposed

The zone sits **between the market and the Focus line**, so price touches it
**first**. On a fixture, 36 backups were:

* **18 trades that would not have happened at all** — the limit was never
  reached and the setup would have expired unfilled
* **18 that PRE-EMPTED a Focus fill**, taking a worse price on a trade that
  was going to happen anyway

Those are opposite in sign and a single net number hides both. The study
matches every armed setup across the two arms by `(symbol, arming bar)` and
reports:

| | what it measures |
|---|---|
| **ADDED** | filled only with the backup on. Its R against the 0 it would have scored. |
| **PRE-EMPTED** | filled in both arms. Backup R **minus** Focus R — the price of chasing. |
| **UNCHANGED** | filled at the Focus in both, or filled in neither. |

A backup that is net positive because ADDED outweighs PRE-EMPTED is a different
finding from one that is positive because pre-emption happens to be harmless,
and both will be stated.

## The prior, and my prediction, recorded before the run

One smoke test exists and I have seen it: BTC 30m, 111 fills to 137, net −5.4 R
to +8.3 R. That is one symbol, in sample, unsplit, and it is the reason this
prereg exists rather than a reason to believe anything.

**My prediction:**

* **ADDED is positive**, around **+0.2 to +0.5 R per added trade**. These are
  entries into a move that has already run 1R in the trade's direction, which
  is a momentum continuation, and the exits study showed the excursion is
  genuinely there.
* **PRE-EMPTED is negative**, around **−0.1 to −0.3 R per pre-empted trade** —
  a strictly worse entry on a trade that was going to happen, with the stop
  unchanged, so the risk is larger and the same move is worth less R.
* **The net lands within ±0.05 R per armed setup, and bar 3 FAILS.** The two
  halves roughly cancel.
* **The control matches the zones.** I expect entering at an arbitrary level
  between the market and the Focus to do about as well as entering at an order
  block or a fair-value gap — because every other component of this strategy
  that has been ablated turned out to be doing nothing, and the mechanism here
  is "enter later at a worse price into a move that is running", which does not
  need a zone.

If ADDED clears **+0.3 R** and the net clears **+0.10 R per armed setup with
z ≥ 2 against the control**, I am wrong, the backup is the missing piece, and
it earns a default-on and a forward run.

## Population and what is held constant

Identical to the ablation, so the two are directly comparable:

* 23 MEXC perpetuals, `research/data.SYMBOLS`, 12,000 bars per symbol
* Min15, Min30, Min60 — run separately, never pooled for a significance claim.
  15m and 30m are what the watch ships; 1h is measured anyway so the pattern
  can be seen.
* **`maxLive = 64`** — the charting cap removed. Leaving it at 4 is what voided
  the first ablation run and it would bite harder here.
* the **current shipped configuration**: swing 6/2, `endMinor = on the flip`,
  extreme-swept off, no-new-extreme off, `retraceMax` 70, `locTol` 0, stop at
  the pullback extreme with tracking and a 0.25 ATR buffer, **`rr` 3.5**
* `feeFrac = 0.0007`; slippage still not modelled, so still optimistic
* a trade unresolved when the data ends is discarded

## The arms

**Primary contrast: B3 − B0**, declared now, one per timeframe.

| id | arm |
|---|---|
| **B0** | backup **off** — the baseline |
| **B1** | order blocks only |
| **B2** | fair-value gaps only |
| **B3** | **both** — `bkTrigger` 1.0, `bkMaxRisk` 2.0, `bkLook` 30 |
| **B4** | both, `bkTrigger` 0.5 — arms earlier, more backups, better prices |
| **B5** | both, `bkTrigger` 2.0 — arms later, fewer backups, worse prices |
| **C** | **the control.** Same trigger, same cap, same everything — but the backup price is the **midpoint between the trigger bar's extreme and the Focus line**, with no zone detection at all. |

B1, B2, B4 and B5 are **descriptive**. No verdict is taken from them and no
significance claim is made about them; they exist so the shape of the effect is
visible rather than a single number.

**C is the bar that matters.** If entering at an arbitrary level between the
market and the Focus does as well as entering at an order block or a gap, then
the zones are decoration and what is being measured is "enter later into a
running move", which is a different and much simpler claim.

Because the primary contrast is declared and nothing is selected, the primary
panel is the **whole population** — the same reasoning as
[`PREREG_undertow_pin_value.md`](PREREG_undertow_pin_value.md), and the opposite
of [`PREREG_undertow_params.md`](PREREG_undertow_params.md), which searched 48
configurations and therefore needed a holdout. The two quadrants the parameter
study never scored are reported as a second panel.

## Unit of evidence and metric

**The bet = one ARMED SETUP.** Mean R per armed setup, net of fees, SEs
clustered by symbol. Ghost trades excluded entirely.

## Pre-registered bars

1. **COVERAGE.** ≥ 300 armed setups on the timeframe, else it is a bound.
2. **NOT CONFOUNDED.** `nArmed` identical in B0 and B3, and `nCap` 0 in both.
   If either fails the contrast is void, exactly as in the ablation.
3. **IMPROVES.** `B3 − B0` ≥ **+0.05 R per armed setup** with clustered
   |z| ≥ 2.0 on the difference, on at least 2 of 3 timeframes.
4. **BEATS THE CONTROL.** `B3 − C` ≥ 1 SE of the difference. Failing this while
   passing 3 means *the backup works and the zones do not* — which is a real
   result and would be reported in those words.
5. **NOT ONE TIMEFRAME.** Positive on ≥ 2 of 3.
6. **NOT ONE SYMBOL.** Dropping the largest contributor leaves `B3 − B0`
   positive.

### Multiplicity

One pre-declared primary contrast per timeframe → three primary tests. At
z ≥ 2 each that is roughly a 14% chance of at least one false positive. The
other twenty-odd numbers are descriptive and carry no claim.

### Power

The ablation gave SEs of 0.05–0.11 R per *trade* at 700–2,400 trades. Per armed
setup the denominator is larger and the variance lower, so SE should land near
0.04 R — meaning the +0.05 threshold in bar 3 is about a 1.2 SE effect and this
study can just about see it. If any arm's SE exceeds 0.08 R that panel is
UNDERPOWERED and reported as a bound.

## What cannot happen

* **No new arm** after any number is seen. `bkLook` 30, `bkMaxRisk` 2.0 and the
  two extra triggers are fixed now; a differently-tuned backup does not get a
  turn in this study.
* **No change to the entry, the arming rule, the stop or the exit.** The
  backup is the only thing that varies.
* **No promotion on a descriptive arm.** If B4 looks best, that is a hypothesis
  for a new prereg, not a default.
* **No `maxLive` at 4.** Void, per the ablation.
* **No production change**, nothing under `riptide/` except the watch's own
  documented caveat if the result changes what it should say;
  `tests/test_control_frozen.py` must still pass.
* **No exchange API key and no order placement.**
* **One study.**

## If it passes

Then it is the first thing in this indicator that has ever cleared its own
bars, and it still does not become a trade. It becomes: default-on in the Pine,
a second alert in the watch when a missed setup's backup zone arms, and a
forward record. Three studies said no; one saying yes earns a fourth look, not
a conclusion.

## If it fails

Then every component of Undertow has now been ablated and none of them carries
an effect — bias gate, candle, location, exit and fill. The remaining
explanation is the one no backtest can reach, the watch already exists to test
it prospectively, and the right move is to stop measuring history and start
recording the future.
