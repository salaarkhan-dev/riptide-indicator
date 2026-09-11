# Pre-registration — does the point of interest still work?

**Written and committed 11 Sep 2026, before any live row was queried.** Nothing
below was chosen after seeing a forward number. If a later analysis disagrees
with anything here, this file is the record and the analysis is the outcome.

> **AMENDED the same day, before any live row was queried, and the amendment
> narrows the test rather than widening it.** The first version was written
> believing the POI had failed everywhere on the deep window. It has not.
> `research/studies/poi_recheck.py` rebuilt the original 2×2 and found the POI
> alive in exactly one cell — **Min30, confirmed, trend agreeing, DAILY zone**
> — at +0.174 ± 0.084 against +0.014 for trend alone, with the original's cell
> ordering preserved exactly and 6 of 8 non-overlapping 42-day windows
> positive. The earlier summary ("2/6 positive, median −0.036") took a median
> across six rows of which five were early or 15m, and buried the one cell that
> works. That was my error and it is corrected in `matrix.py` too.
>
> The hypothesis, the margin and the primary below have been rewritten to test
> **the surviving cell**, which is the honest target. The original framing is
> left in the body rather than deleted, so the amendment is auditable against
> `git log` on this file.

---

## Why this test exists

The POI is the most consequential setting in the bot and its two measurements
disagree completely.

**For it.** `MEASUREMENTS.md`, 42 days, 14 symbols with 9 held out: a raid
landing inside a daily order block or fair value gap was *"the single largest
separation measured here and the only filter to pass a pre-registered held-out
test on symbols it was not found on."* Min15 went from −0.095 to **+0.417**
inside one. `hybrid.py` Policy G took return per unit of drawdown from 6.94 to
21.53. It is the reason `POI_REQUIRED` defaults to 1, and — more importantly —
it is one of the three axes of the grade table itself.

**Against it — but only outside one cell.** `research/studies/matrix.py`,
333 days, 59 symbols, 31,025 filled trades. Eighteen in-zone-against-
out-of-zone contrasts across three timeframes, two streams and both POI
definitions:

| contrast | positive | median diff | clears 2 SE |
|---|---|---|---|
| live 8h POI | 2 / 6 | −0.036 | 1, **against** |
| daily POI (the original configuration) | 2 / 6 | −0.040 | 0 |
| both contexts vs neither | 2 / 6 | −0.076 | 1, **against** |

Twelve of eighteen negative, and the only two rows clearing 2 SE both point
against the filter.

**And that summary is misleading, which `poi_recheck.py` established before
this test starts.** Five of those six rows are early signals or Min15. The
sixth — Min30 confirmed on the DAILY zone — is **+0.160 ± 0.099**, positive in
six of eight independent 42-day windows with a median of +0.331. Rebuilt as the
original's 2×2:

| POI | trend | bets | 333 days | original (41 days) |
|---|---|---|---|---|
| no | no | 1,247 | −0.050 ± 0.037 | +0.082 |
| no | yes | 696 | +0.014 ± 0.051 | +0.206 |
| yes | no | 556 | −0.094 ± 0.057 | +0.105 |
| **yes** | **yes** | **282** | **+0.174 ± 0.084** | **+0.822** |

Every cell shrank; **the ordering is preserved exactly**. The interaction is
still there at +0.160 where the original measured +0.616. So the deep window
does not refute the claim — **it refutes the size**, by about 4×, which is what
the original's power predicts: those cells held 28–43 signals with an MDE of
0.79–0.98, so they could not have distinguished +0.16 from +0.82.

Where it genuinely fails is **early signals and Min15**: −0.028, −0.058, −0.065,
which is roughly 80% of the alert stream.

**Neither reading settles it and a third backtest cannot.** Both windows end
today and overlap; the 333-day one contains the 42-day one. The deep window
also carries a survivorship premium that the 42-day window largely does not.
Re-slicing the same candles again is how this project has already wasted
measurements — `entry_deep.py` is the standing example: two entry variants that
led on 42 days came back as the two **worst** on 333 days at −5.0 and −4.7 SE,
and nothing was wrong with the first study except its sample.

So the only instrument that can resolve this is data neither measurement has
seen. That means forward.

---

## A correction, recorded before it can be quietly forgotten

Earlier in this project's notes — including in a conversation on 11 Sep — the
POI's cost was stated as *"it halves the stream"*. **That is wrong**, and the
error matters enough to fix here rather than bury.

`engine.GRADES` is **asymmetric in the POI axis**:

| | trend agrees | trend against |
|---|---|---|
| confirmed, in a zone | **A** | C |
| confirmed, no zone | **B** | C |
| early, in a zone | **B** | C |
| early, no zone | C | D |

At `MIN_GRADE=B` a confirmed signal with no zone falls A → B and **still
sends**; an early one falls B → C and is **muted by the grade, not by
`POI_REQUIRED`**. So turning `POI_REQUIRED` off releases the confirmed
signals with no zone and *nothing else*. Measured:

| | alerts/day (120 symbols) | total R, 333 days |
|---|---|---|
| POI on — what is deployed | 85.1 | +298.0 |
| POI off, regraded — what `POI_REQUIRED=0` actually gives | 99.6 | +439.9 |
| no POI at all — **not a configuration that exists** | 189.5 | +1116.8 |

The real cost of the `POI_REQUIRED` gate is **14.5 alerts a day, about 17%**,
not half the stream. The half-the-stream figure describes the gap to the third
row, which no setting can reach.

**This changes what is being tested.** `POI_REQUIRED` turns out to be a small
lever. The large one is that the **grade table itself encodes the POI**, so
even with the gate off, `MIN_GRADE=B` keeps muting every early signal that has
no zone. A verdict against the POI therefore implies rebuilding `GRADES`
without that axis — a bigger change than flipping one boolean, and one that
needs its own study. That is stated now so the eventual result is not quietly
narrowed to the easy half.

---

## The data already exists, and that is not luck

`riptide/scanner.py` arms the tracker **before** the send gate, not after:

```python
if fresh:
    _arm(db, sid, s, tracker.CONFIRMED)          # every fresh signal
if fresh and not mute and poi_ok(s) and grade_ok(s, False):
    ...send                                       # only the ones that pass
```

with the comment *"Track what was actionable, sent or not: a pause or a
delivery failure must not put a hole in the sample."* The consequence, probably
unintended, is that **out-of-zone signals have been scored forward all along**
even though they were never messaged. `outcomes.poi` records which arm each row
is in.

So this test needs **no instrumentation change, no extra alerts, and no extra
API requests** — the scanner already fetches the candles it scores against.
The clock can start on the day this file is committed.

---

## The hypothesis, stated so the data can refuse it

> **In the surviving cell — Min30, confirmed, trend agreeing, daily zone —
> being inside a POI is worth about +0.16 R per bet. Everywhere else it is
> worth nothing.**

Both halves are under test and they are tested separately, because the
deployment consequences are opposite: the first says keep the filter where it
works, the second says the grade table should stop applying it to early signals
and to Min15.

Direction is **not** left open. A result in the other direction is *not* a
finding in this design; it is a failure of the filter and is scored as zero.

---

## Design: non-inferiority, not significance

A plain two-sided test here would almost certainly return "no separation" and
leave the decision exactly where it is now. That is not a useful outcome, and
designing a test whose likely result is "we still don't know" is how research
budgets are wasted.

The right shape is **non-inferiority**, because the two sides of this decision
are not symmetric. The POI's **cost is certain and already measured** (14.5
alerts a day, and one of three axes of the grade table). Its **benefit is what
is in doubt**. So the filter must *earn* its cost, and the question is not "is
it better than nothing" but "can we rule out its being worth enough to keep".

**Pre-committed margin: δ = +0.10 R per bet, on the BROAD arm only.**

Chosen for two reasons, both stated before any data:

1. It is the smallest margin this sample can bound inside one season (see
   power below). A tighter δ would need most of a year.
2. It is **below the deep window's own estimate for the surviving cell**
   (+0.16). So a filter performing as `poi_recheck.py` says it performs would
   *not* be ruled out — which is the property a non-inferiority margin must
   have if the test is to be fair to the filter rather than designed to kill
   it.

**The narrow arm is a plain two-sided test, not non-inferiority.** In the
surviving cell the question is simply whether +0.16 is still there, and the
deep window's own estimate is the prior. It is underpowered on purpose-built
honesty grounds (see power), and that is stated now rather than discovered
later.

---

## The primary analysis, fixed now

**Population.** Rows in `outcomes` with `armed_time` **strictly after this
file's commit timestamp**, which is fixed and recorded here rather than left
to be decided later:

```
commit  0e1f833beba7512df3e869a8655835b7b2dec37f
epoch   1789139933          # 2026-09-11T15:18:53Z
```

(That commit adds this file without the two lines above; the amend that records
its own hash changes nothing else, and `git log --follow` shows both.)
 Rows armed before it are out-of-sample with respect
to the deep window but *not* with respect to the author, who has read `/stats`;
they may be reported as a supporting look and may **never** be decisive.

**Inclusions.**
- `status IN ('won', 'lost', 'timeout')` — filled and resolved. `expired`
  (never filled) is excluded because an unfilled signal has no R to compare;
  `pending`, `open` and `stale` are excluded as unresolved.
- **Trend agrees**: the SuperTrend and DI both with the trade, i.e.
  `grade_of(early, poi=True, trend_dir, side, di_dir)[0] in "AB"`.
  Grading with `poi=True` for every row is deliberate and is the only
  non-circular choice available — the real grade *contains* the POI, so
  filtering on it would select on the variable under test. This reduces
  exactly to "trend agrees", which is what the backtest arms also held fixed.

**Arms.** `outcomes.poi` — 1 versus 0.

**Two populations, tested separately and pre-specified:**

- **NARROW (the surviving cell):** `kind = 'setup'` (confirmed) **and**
  `tf = 'Min30'`. This is where `poi_recheck.py` says the filter lives.
- **BROAD (everything else):** early signals of any timeframe, plus confirmed
  on Min15 and Min60. This is where it does not.

Pooling the two would be the same mistake `matrix.py` made — averaging one
working cell with five flat ones and reporting the average.

**Unit.** A **bet**, not a trade: the mean R of every row sharing a bet key.
Bet key is `armed_time` floored to **3600 seconds**, the slowest scanned bar.
Flooring is required rather than optional: with Min15, Min30 and Min60 all
scanned, a 15m signal at 10:15 and the 1h signal at 10:00 containing it are one
raid with two timestamps, and keying on the raw time would borrow independence
that is not there and shrink the standard error dishonestly.

**Statistic.** `mean(bets_in_zone) − mean(bets_out_of_zone)`, with the standard
error as the root sum of squares of the two arm standard errors, and a 95%
confidence interval as ±1.96 SE.

**Decision rule — committed, and it produces an action in every branch:**

**NARROW arm** (Min30 confirmed), two-sided:

| result | verdict | action |
|---|---|---|
| CI lower bound **> 0** | the surviving cell is real | Keep the POI here. Consider *raising* its weight in `GRADES` rather than lowering it. |
| CI upper bound **< 0** | even the surviving cell is gone | The filter is finished; rebuild `GRADES` without the POI axis entirely. |
| CI spans zero | underpowered, as expected | **No change.** Report the interval and extend once. |

**BROAD arm** (early, and confirmed on Min15/Min60), non-inferiority at δ:

| result | verdict | action |
|---|---|---|
| CI upper bound **< +0.10** | the POI does not earn its cost here | Rebuild `GRADES` so the POI axis applies to **confirmed Min30 only**, and stop muting early signals for lack of a zone. `POI_REQUIRED` becomes a Min30-confirmed gate. |
| CI lower bound **> 0** | it works here too | Nothing changes; `poi_recheck.py` gets a correction. |
| CI spans both | undecided | **No change.** Extend once. |

Every "undecided" branch changes nothing. An undecided test must not become a
licence to act on a point estimate — which is precisely the failure that
produced the +0.822 figure this whole test exists to re-measure.

---

## Power, computed before the data

Per-bet standard deviation on this strategy is **1.31** across every timeframe
measured (15m 1.30, 30m 1.31, 1h 1.31 — remarkably stable). Minimum detectable
effect for two arms at 5% significance and 80% power:

```
MDE = 2.80 × 1.31 × sqrt(2 / n_per_arm)
```

Forward bet rate, from `matrix.py` scaled to the live 120-symbol universe
(bets scale as symbols^0.905):

| population | filled trades/day | bets/day | smaller arm |
|---|---|---|---|
| **NARROW** — Min30 confirmed | ~7.7 | ~6 | ~2.6 |
| **BROAD** — everything else | ~182 | ~46 | ~21 |

| n per arm | MDE | days, pooled | days, confirmed only |
|---|---|---|---|
| 670 | 0.200 | 30 | 74 |
| 1,400 | 0.139 | 64 | 156 |
| 2,000 | 0.116 | 91 | 222 |

**The BROAD arm is decidable inside a season; the NARROW one is not, and that
has to be said now rather than discovered in December.** At ~2.6 bets a day in
its smaller arm, Min30 confirmed needs **~540 days** to reach n=1,400 and an
MDE of 0.139. Forward data alone will not settle the surviving cell this year.

That is not a reason to skip it. It is a reason to state the honest schedule:

- **BROAD arm reads out at 1,400 bets in the smaller arm or 31 Dec 2026**,
  whichever is *later*. This is the decidable test and it is the one that can
  change the grade table.
- **NARROW arm reads out at 31 Dec 2027**, or earlier only if its CI has
  already excluded zero. Until then it is reported with its interval and
  **nothing is done to the POI on Min30 confirmed in either direction** — which
  is the status quo, so the default costs nothing.

No other looks at either primary.

**One permitted interim look, at 14 days**, reporting *only*: total rows armed,
the in-zone/out-of-zone split, the resolved fraction, and any nulls. It must not
compute R. Its sole purpose is to catch a plumbing failure early — a test that
silently records nothing for three months is the failure mode this guards.

### The query, fixed now so it is not re-invented later

The analysis script does not exist yet and must not be written against live
data. What it does is fixed here:

```sql
SELECT poi, armed_time, r, kind, entry, stop, risk,
       trend_dir, di_dir, side, tf, status
  FROM outcomes
 WHERE status IN ('won','lost','timeout')
   AND armed_time > 1789139933;      -- this file's commit, see above
```

then, in Python, and in this order:

```python
keep   = grade_of(k == "early", True, trend_dir, side == "long", di_dir)[0] in "AB"
key    = armed_time - (armed_time % 3600)          # the slowest scanned bar
bet    = mean(r for rows sharing key)              # within each arm separately
gap    = mean(bets[poi == 1]) - mean(bets[poi == 0])
se     = (se_in**2 + se_out**2) ** 0.5
ci     = (gap - 1.96 * se, gap + 1.96 * se)
```

`risk_pct = 100 * risk / entry` for secondary 2, with the band boundaries taken
unchanged from `survivor.py` (1.2 and 2.6) and **not** refitted on live data.

No other transformation. No winsorising, no outlier removal, no symbol
exclusions — if a single symbol dominates a result that is reported, not
removed.

---

## Secondaries — reported, never decisive

Because rule 5 of `matrix.py` applies here too: about a dozen contrasts will be
printed, and one or two will clear 2 SE by chance.

1. The same contrast per timeframe (15m / 30m / 1h) and per stream
   (confirmed / early) — the full 2×2 with the trend axis, so the interaction
   claim is tested in the same shape the original made it.
2. The same contrast **inside the risk band only** — the band is the one filter
   this project trusts, so whether the POI adds anything on top of it is the
   question that would change the alert, not just the config.
3. Win rate and realised RR for each arm. R per trade is
   `(win − breakeven) × average round trip`, so a real difference must appear
   in one of those blades; a difference in R with neither moving is a sign of
   an outlier, not an edge.
4. Drawdown and recovery factor per arm on the R curve in exit order.

---

## What is frozen for the duration

Changing any of these mid-test invalidates it, and the analysis must check them
rather than assume them:

- `POI_INTERVAL` is **`Day1`**, set in `riptide.conf` on 11 Sep before the clock
  started, and stays there for the duration,
  and `POI_MAX_AGE_BARS` stays **30**. This is no longer a formality:
  `poi_recheck.py` finds the surviving cell at **+0.160 on Day1** and **+0.006
  on Hour8**, and the bot has read Hour8 since 9 Sep only because `poi_at` read
  `TREND_INTERVAL` and the SuperTrend moved. It has now been set back to `Day1`
  while `TREND_INTERVAL` stays `Hour8` — the separation the new key exists for —
  so **`Day1` is the configuration under test**. Changing it *during* the test
  invalidates the test.
- `RIPTIDE_INTERVALS` stays **Min30,Min15,Min60**, `MIN_GRADE` stays **B**
  (set in `riptide.conf`; the module default in `config.py` is still `C`, and
  that mismatch is deliberate noise to be aware of, not a second setting),
  `MIN_VOL_USDT` stays **1,000,000**, `TOP_N` stays **120**.
- The engine's signal output stays pinned by `tests/test_control_frozen.py`.
  That test exists precisely so a change to what the bot emits is loud, and it
  is the reason this test can trust rows armed three months apart.
- The tracker schema and the meaning of `outcomes.poi`.

`RIPTIDE_INTERVALS` gained Min60 on the same day this file was written, so the
forward stream's composition changed today and the test starts from today's
configuration rather than yesterday's. Labels (`risk_verdict`, the cross-
timeframe chip) may change freely — they alter no signal and no arm.

---

## What would make me distrust my own result

Written now, while it is still cheap to be honest:

- **A regime that favours one arm.** Out-of-zone raids may be more common in
  trending markets and in-zone ones in ranges. A single season can be one
  regime. The analysis will report the split by month; a result driven by one
  month is not a result.
- **The arms are not randomised.** This is an observational comparison of two
  naturally occurring populations, not an experiment. In-zone and out-of-zone
  signals differ in more than the label — median stop distance among them, which
  is the one variable known to matter. Secondary 2 partly controls for it; it
  does not eliminate it.
- **Survivorship runs the other way here, and that is a point in the test's
  favour.** Forward data has no survivorship bias at all, which is exactly why
  it can settle what two backtests could not.
- **I already believe the answer.** Having written `matrix.py`, I expect the
  POI to fail. That is the strongest argument for every number in this file
  being fixed before the query is run, and for the decision table having a
  branch that keeps the POI on.
