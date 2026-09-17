# PRE-REGISTRATION — does the backup work if it cannot pre-empt?

Committed before the first number. Run by
`indicators/undertow/studies/undertow_late_backup.py`.

## The decision this is for

[`UNDERTOW_BACKUP_FILL.md`](../measurements/UNDERTOW_BACKUP_FILL.md) found the
largest effect anywhere in this indicator, and found it twice, pointing in
opposite directions:

| | trades per tf | R each | clustered z |
|---|---|---|---|
| **ADDED** — filled only because of the backup | 388 / 411 / 436 | **+0.56 / +0.67 / +0.57** | +4.3 / +6.5 / +5.4 |
| **PRE-EMPTED** — a worse price on a trade that was coming anyway | 541 / 599 / 597 | **−0.23 / −0.28 / −0.29** | −5.6 / −7.1 / −7.2 |

Net: **+0.02 R per armed setup, z ≈ 0.6.** Nothing.

Pre-emption exists for exactly one mechanical reason: the zone sits between the
market and the Focus line **while the Focus limit is still live**, so price
touches the zone first and takes the worse of two prices that were both going
to fill. Remove that and the −0.27 R tax cannot be paid.

**This study tests the one design where pre-emption is impossible by
construction.** The backup is not placed until the Focus fill window has
expired without a fill. At that point there is no order left to pre-empt, so
every backup is an ADDED trade by definition.

## The cost, stated before the run

This is not free and the direction of the cost is known in advance: **many of
the +0.6 R ADDED trades filled INSIDE the Focus window** and a late backup
cannot have them. What survives is the subset whose zone touch happens after
`fillBars`, entered at a price that has had longer to drift and against a stop
that has not moved.

So the question is not "is late better than live in principle" — it obviously
is, per trade. It is **whether enough trades survive the wait to beat +0.02 R
per armed setup.**

## A STRUCTURAL CHECK WAS RUN FIRST, AND IT CHANGED THIS DOCUMENT

Disclosed because it has to be. After implementing the rule I ran it on **one
symbol** (BTC 30m) to confirm the mechanism worked at all, and saw the trade
COUNTS — not the outcomes of any panel this study reports:

    off     207 armed, 111 filled,  0 backups
    live    207 armed, 138 filled, 54 backups
    LATE    207 armed, 112 filled,  1 backup

**One.** That is a structural fact about the population, not a result, and it
changes what this study can possibly show — so it is recorded here rather than
discovered afterwards and explained.

The reason is mechanical. A candidate only reaches the Focus window's expiry if
it has not already been killed by the target printing (`gone`), the stop being
taken (`stop`), or the bias turning. On that symbol only 21 of 207 armed setups
reached expiry at all, and a zone then had to exist *and* be touched inside 20
more bars. **The late design can address roughly a tenth of the population, and
converts a fraction of that.**

Which means the previous study's +0.6 R ADDED trades **overwhelmingly filled
INSIDE the Focus window** — they are structurally entangled with the pre-empted
ones, not separable from them by waiting. That is the most likely answer to
this study's question and the study is being run to confirm it properly rather
than to infer it from one symbol.

**A REQUIRED DIAGNOSTIC is therefore added to the report:** of the live
backup's ADDED trades, the distribution of `fillBar − armBar` against
`fillBars`. That single histogram is what says whether any late design could
ever have worked, and it is descriptive — it tests no hypothesis.

## The prior, and my prediction, recorded before the run

**My prediction, revised after the structural check above:**

* L1 produces **10 to 60 backups per timeframe against B3's ~1100**. My
  pre-check estimate of 100–180 was written before I saw the counts and was
  wrong by an order of magnitude; the revision is disclosed rather than
  quietly applied.
* Those that survive are worth **+0.3 to +0.6 R each** — about what ADDED was.
* **Zero pre-emption**, by construction. If the study reports any, the
  implementation does not match this document and the run is VOID.
* **Net between 0.00 and +0.02 R per armed setup — bar 3 FAILS, and this panel
  is likely to be UNDERPOWERED and reported as a bound.** Too few trades to
  move a denominator of 3,700.
* **L1 beats L3 on per-trade value and NOT on total — bar 5 is genuinely
  uncertain.** Removing the tax helps each trade and removing the opportunity
  hurts the sum, and I do not know which wins. This is the one number in the
  study I cannot call.
* **The control matches again.** A midpoint entry will do what the zones do, as
  it has every other time.
* **The diagnostic shows most ADDED fills landing well inside the window** —
  I expect the median `fillBar − armBar` under 10 against a window of 20.

If L1 clears **+0.10 R per armed setup with z ≥ 2 and beats its control**, I am
wrong on every count above, and this is the first thing in Undertow to earn a
default-on.

## Population and what is held constant

Identical to
[`PREREG_undertow_backup_fill.md`](PREREG_undertow_backup_fill.md), so the two
studies are directly comparable:

* 23 MEXC perpetuals, 12,000 bars each, Min15 / Min30 / Min60, run separately
* `maxLive = 64`; the shipped config (swing 6/2, `endMinor` on the flip,
  extreme-swept off, no-new-extreme off, `retraceMax` 70, `locTol` 0, stop at
  the pullback extreme with tracking and a 0.25 ATR buffer, **`rr` 3.5**)
* `feeFrac = 0.0007`, slippage not modelled and therefore still optimistic
* a trade unresolved when the data ends is discarded
* **metric: mean R per ARMED SETUP** — the denominator no backup can move.
  `nArmed` is identical in every arm and an unfilled setup contributes 0.

## The rule being tested, defined exactly

> **LATE BACKUP.** A setup arms and its limit rests at the Focus line for
> `fillBars` bars. If it has not filled by then, the Focus order is **cancelled**
> and — on that same bar — the nearest order block or fair-value gap **between
> the current price and the Focus line** becomes the new limit, provided its
> stop distance is within `bkMaxRisk` × the original. It rests for a further
> `bkLateBars` bars. The stop price is unchanged; the target is `rr` from the
> new entry. The original stop and target still apply throughout, stop first.

The zone is scanned **at the moment of expiry**, not at the earlier trigger — a
zone identified twenty bars ago may be behind price by the time the window
closes, and "the level I would take now" is the rule being described.

## The arms

**Primary contrast: L1 − L0.** Secondary and equally pre-declared: L1 − L3.

| id | arm |
|---|---|
| **L0** | backup off — the baseline |
| **L1** | **LATE backup, zones.** `bkLateBars` 20, `bkMaxRisk` 2.0, `bkLook` 30 |
| **L2** | **control.** Late, same windows and cap, but the entry is the **midpoint** between the expiry bar's extreme and the Focus — no zone detection at all |
| **L3** | the LIVE backup exactly as measured before (B3), for the direct comparison |
| **L4** | late, `bkLateBars` 40 — descriptive |
| **L5** | late, `bkLateBars` 10 — descriptive |

L4 and L5 are descriptive. No verdict and no significance claim comes from
them.

Nothing is selected, so the primary panel is the whole population, and the two
quadrants the parameter study never scored are a second panel — the same
reasoning as the two previous ablations.

## Pre-registered bars

1. **COVERAGE.** ≥ 300 armed setups per timeframe. Separately, **if L1
   produces fewer than 100 backups on a timeframe that panel is declared
   UNDERPOWERED** and reported as a bound rather than a verdict — the
   structural check above says this is the likely outcome and saying so now is
   the only way it means anything later.
2. **NOT CONFOUNDED.** `nArmed` identical across L0, L1, L3; `nCap` 0 in all;
   and **L1's PRE-EMPTED count must be exactly 0**. A non-zero pre-emption in a
   design where it is impossible means the implementation does not match this
   document and the run is VOID.
3. **IMPROVES.** `L1 − L0` ≥ **+0.05 R per armed setup** at clustered
   |z| ≥ 2.0, on ≥ 2 of 3 timeframes.
4. **BEATS ITS CONTROL.** `L1 − L2` ≥ 1 SE of the difference. Failing this
   while passing 3 means *waiting works and the zones do not*, and will be
   reported in those words.
5. **BEATS THE LIVE BACKUP.** `L1 − L3` > 0 on ≥ 2 of 3. **This is the
   hypothesis.** Failing it means removing pre-emption costs more than it
   saves, and the whole line of reasoning is wrong.
6. **NOT ONE SYMBOL.** Dropping the largest contributor leaves `L1 − L0`
   positive.

### Multiplicity

Two pre-declared contrasts per timeframe (L1−L0 and L1−L3) → six primary tests.
At z ≥ 2 each that is roughly a 26% chance of at least one false positive, and
no result from this study will be quoted with a z-score and without this
sentence. The descriptive arms carry no claim.

### Power

The previous study gave SE ≈ 0.036–0.041 R per armed setup. L1 will have far
fewer backups, so its SE should be *smaller* than B3's, not larger — the extra
trades are what added variance. If any arm's SE exceeds 0.08 R the panel is
UNDERPOWERED and reported as a bound.

## What cannot happen

* **No new arm** after any number is seen. `bkLateBars` 20 with 10 and 40 as
  descriptive neighbours, `bkMaxRisk` 2.0, `bkLook` 30 — all fixed now.
* **No change to the entry, arming, stop or exit rules.** Only when the backup
  is placed varies.
* **No promotion from a descriptive arm.**
* **No re-running with a different `fillBars`.** The Focus window is 20 bars
  and stays there; "a shorter window would let the backup in sooner" is a
  different study.
* **No production change.** Nothing under `riptide/` except the watch's caveat
  if the result changes what it must say; `tests/test_control_frozen.py` must
  still pass.
* **No exchange API key and no order placement.**
* **One study.**

## If it passes

Then Undertow has one component that beats its own control, and the right next
step is still not a trade: it is default-on in the Pine, a second alert in the
watch when a missed setup's late zone arms, and a forward record. Four studies
said no; one saying yes earns a fifth look.

## If it fails

Then the +0.6 R in ADDED is real and structurally uncapturable — it exists only
in trades that are indistinguishable, at the moment of entry, from the ones
that cost −0.27 R. Five components will have been ablated and none will have
survived its control, and the only remaining question is the one no backtest
can answer. The watch is already built for that and the answer is to start
recording rather than to keep measuring.
