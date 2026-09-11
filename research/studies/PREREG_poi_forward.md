# Pre-registration — does the point of interest still work?

**Written and committed 11 Sep 2026, before any live row was queried.** Nothing
below was chosen after seeing a forward number. If a later analysis disagrees
with anything here, this file is the record and the analysis is the outcome.

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

**Against it.** `research/studies/matrix.py`, 333 days, 59 symbols, 31,025
filled trades. Eighteen in-zone-against-out-of-zone contrasts across three
timeframes, two streams and both POI definitions:

| contrast | positive | median diff | clears 2 SE |
|---|---|---|---|
| live 8h POI | 2 / 6 | −0.036 | 1, **against** |
| daily POI (the original configuration) | 2 / 6 | −0.040 | 0 |
| both contexts vs neither | 2 / 6 | −0.076 | 1, **against** |

Twelve of eighteen negative, and the only two rows clearing 2 SE both point
against the filter. The daily arm there is the *original* configuration — Day1,
30-bar life — so this is not an artefact of the 9 Sep move to Hour8.

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

> **H₀ (what the deep window says): being inside a POI is worth nothing.
> H₁ (what the original study says): it is worth a large positive amount.**

Direction is **not** left open. The original claim is that in-zone beats
out-of-zone by a wide margin — around +0.4 R on Min15. A result in the other
direction is *not* a finding in this design; it is a failure of the filter, and
it is scored the same way as zero.

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

**Pre-committed margin: δ = +0.10 R per bet.**

Chosen for two reasons, both stated before any data:

1. It is the smallest margin this sample can bound inside one season (see
   power below). A tighter δ would need most of a year.
2. It is **a quarter of the effect originally claimed** (+0.417 on Min15). If
   the POI is worth even a quarter of what it was reported to be worth, this
   test will not rule it out. Ruling out +0.10 is therefore a strong statement
   about the original claim specifically, not a generic null.

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

**Arms.** `outcomes.poi` — 1 versus 0. No other split.

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

| result | verdict | action |
|---|---|---|
| CI lower bound **> 0** | POI vindicated | Nothing changes. The 333-day result becomes the anomaly and `matrix.py` gets a correction. |
| CI upper bound **< +0.10** | POI does not earn its cost | `POI_REQUIRED` → 0, **and** open the study to rebuild `GRADES` without the POI axis. The POI becomes a printed label. |
| CI spans both | undecided | The test is extended once, to double the bets, at a date fixed in advance (below). If it is still undecided, the POI **stays on** and this file records that the question was not answerable in a year. |

The third row is the honest default and it is deliberately the one that changes
nothing: an undecided test must not become a licence to act on the point
estimate.

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

| stream | filled trades/day | bets/day | smaller arm |
|---|---|---|---|
| confirmed only | ~26 | ~20 | ~9 |
| both streams pooled | ~190 | ~49 | ~22 |

| n per arm | MDE | days, pooled | days, confirmed only |
|---|---|---|---|
| 670 | 0.200 | 30 | 74 |
| 1,400 | 0.139 | 64 | 156 |
| 2,000 | 0.116 | 91 | 222 |

**The primary is the pooled stream**, because it is the only one that reaches a
useful δ inside a season. Confirmed-only is a secondary and will be
underpowered; that is stated now so its wide interval is not later read as
disagreement.

**Stopping rule.** The analysis is run once, at **1,400 bets in the smaller
arm** or **31 December 2026**, whichever comes *later*. The extension in the
"undecided" branch runs to 2,800 or 30 June 2027, again whichever is later.
No other looks at the primary.

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
   (confirmed / early).
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

- `POI_INTERVAL` stays **Hour8** and `POI_MAX_AGE_BARS` stays **30**.
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
