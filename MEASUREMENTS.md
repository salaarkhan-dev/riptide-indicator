# Measurements

Every strategy question tested on this project, what came back, and what was
done about it. Written down because most of these came back negative, and a
negative result nobody recorded gets re-tested in a month.

## Method

Unless stated otherwise: 50 MEXC USDT perpetuals ranked by 24h turnover,
2000 `Min30` bars (41.6 days), the engine's shipped `Cfg`.

Each signal is scored as a trade: a limit at the entry, fillable for 10 bars
from the bar the setup became **detectable**; the alerted stop; a fixed target;
stop taken first when one bar contains both; marked to market at the close
after 60 bars. A setup that never fills scores **0R**, so fill rate cannot be
gamed by moving the entry somewhere price never returns.

Comparisons between entry variants are **paired** on the same setups, which is
why their standard errors are far smaller than the levels they compare.

Two things are never modelled, and both flatter every number below: **fees and
slippage**. A ~0.06% round trip is ~0.04R at 1.5% risk and ~0.10R at 0.6%, so
the tighter-stop variants are hurt most.

## The one thing that worked

**Daily SuperTrend(14, 5) filter.** 2026 setups, 1R target:

| | setups | R per setup |
|---|---|---|
| with the daily trend | 1011 | **+0.103 ± 0.021** |
| against the daily trend | 1015 | −0.008 ± 0.020 |
| difference | | **+0.110 ± 0.029 (+3.8 SE)** |

It is the only result that has replicated: the gap came back at **+0.135,
+0.095 and +0.110** across two windows, two symbol sets and two scoring
methods. The level it sits on has ranged from −0.05 to +0.32 over the same
comparisons.

Re-measured after the audit below, on the fixed engine with the trend
lookahead removed, it reads **+0.119 against −0.016, a +0.135 ± 0.047 gap
(+2.8 SE) over 1188 setups**. Smaller sample because `fvg_scan_from="mss"`
roughly halves the setup count; the separation is what survived, which is
the claim.

**Trust the separation, not the level.** Shipped as a label on every alert
rather than a filter, so counter-trend signals are judged rather than hidden.
`/trend on` suppresses them.

## Two bugs that invalidated earlier numbers

**Lookahead in every backtest.** `scan_leg` searches for the entry gap
backwards from the raid, so the gap often forms *before* the shift that makes
the setup detectable — 56% of the time, median 4 bars earlier, up to 41.
Scoring from the gap bar counted fills from bars that had already closed
before the setup existed. Correcting it cost **0.229 R per setup (−22 SE)**,
larger than any effect these tests were built to detect. Every figure on this
page is post-correction.

**The freshness gate measured from the wrong bar.** It aged a setup from the
shift, not from when it became knowable, so any setup whose gap took more than
a bar to arrive was found, recorded, deduped and never sent — 76 of 2035 (4%),
permanently. Both bugs were the same mistake about when a setup starts
existing.

## Full audit, 6 Sep

Every module read line by line, plus invariant checks over 1219 confirmed,
2966 early and 7943 sweep signals on 50 symbols. Three real defects.

**The stop froze at the shift while the gap search kept going.** Trailing the
raid extreme lives inside `if was_swept and not was_mss`, so it stops the
instant the shift confirms — but the setup block keeps hunting for a gap for
`max_bars_after_mss` bars after that. When price traded back through the raid
extreme in that window, the setup carried a stop price had already taken, and
when the gap formed beyond it the stop landed on the **wrong side of the
entry**: a long stopped above its own entry.

| | n | share | R per setup |
|---|---|---|---|
| inverted stop | 7 | 0.6% | **−0.857** |
| stop already traded through | 37 | 3.0% | +0.150 |
| clean | 1175 | 96.4% | +0.047 |

Six of the seven inverted setups lost by construction. The Pine had the same
defect in the same shape. Both now expire the cluster instead: for a long,
price back below the swept low means that low was taken a second time and the
reversal the shift claimed did not hold — there is no setup left to re-price.
After the fix all three classes are zero and 100% of setups carry an intact
stop. Aggregate cost was small (+0.045 → +0.050); the point is that seven
alerts were unwinnable trades.

The giveaway that it was an oversight rather than a decision: `Early` has
exactly this guard, and so does `mtf.refine`. Only `scan_leg` lacked it.

**15% of early alerts were a confirmed alert sent twice.** The early block
runs before the setup block on the same bar, and with `fvg_scan_from="mss"`
`scan_leg` examines the very gap the early block just used, with the same
entry formula and the same stop. Whenever the shift landed within
`early_max_bars` of the raid, both fired: **457 of 2966 early signals** had
byte-identical entry and stop, the same detected bar, and therefore the same
freshness — two messages, one trade. Worse, both were armed for tracking, so
`/stats` counted one trade twice and correlated its own sample.

Now paired: the confirmed alert carries the trade and gains a line saying it
also qualified early, the duplicate is recorded so it can never be sent later,
and only one outcome row is armed. Early signals that share a gap but differ
in price are untouched — 6 of them in the test set.

**The trend read a daily bar that had not closed.** `bisect_right(times, when)
- 1` finds the last bar that had *opened* at `when`, not the last that had
*closed*. Live this never bit, because `fetch_candles` drops the forming bar
so today's daily candle is not in the series at all. In a backtest every bar
is closed and present, so a signal at 12:00 read the trend computed from that
day's close. It moved 1.2% of signals and the headline gap from +0.147 to
+0.135 — **the conclusion survived**, and it is fixed so measurements and live
now agree.

Two smaller things: the trend was evaluated at `mss_time` for setups but at
the detection bar for early signals (both now use `detected_time`), and the
`/trend` help quoted superseded figures.

**Verified clean:** no API key, signing, order or position code anywhere —
`exchange.py` is GETs only. Every Early invariant passed on all 2966 signals
(stop exactly at the raid extreme, entry inside the gap, window 0–10 bars,
confluence 0–1, sweep before gap), as did every sweep invariant. Non-repainting
confirmed, tracker idempotent through `last_bar`, dedupe tables cannot collide,
commands gated on chat *and* sender with literal `systemctl` arguments.

Early scores **+0.053 ± 0.016** per signal against +0.045 ± 0.024 for
confirmed, over 2944 scored — not the weaker strategy, and it fires a median
4 bars after the raid.

## Tested and rejected

Everything here is a paired comparison against the shipped entry unless noted.

### Entry placement

| variant | 1R | 3R | fill | median risk |
|---|---|---|---|---|
| **FVG entry, raid stop (shipped)** | +0.056 ± 0.016 | +0.041 ± 0.025 | 50% | 1.61% |
| Order Block (full candle), raid stop | +0.079 ± 0.014 | +0.047 ± 0.023 | 37% | 1.17% |
| Order Block (full candle), OB stop | +0.085 ± 0.014 | +0.045 ± 0.025 | 37% | 0.62% |
| Order Block (body), raid stop | +0.073 ± 0.013 | +0.052 ± 0.022 | 32% | 1.03% |

Paired: **+1.6, +1.6, +1.1 SE at 1R; +0.3, +0.1, +0.5 SE at 3R.** Across six
comparisons, one at 1.6 SE is what noise produces. Trend-aligned — the only
bucket that has ever separated — the shipped entry is **best** (+0.103 against
+0.096, +0.069, +0.068), so the nominal advantage lives entirely in the half
worth least. An OB exists for essentially every setup (0 of 1899 lacked one),
so it cannot act as a filter.

| variant | 1R | 3R | fill | median risk |
|---|---|---|---|---|
| **FVG entry, raid stop (shipped)** | +0.059 ± 0.018 | +0.040 ± 0.029 | 55% | 1.50% |
| Breaker (candle), raid stop | +0.058 ± 0.017 | +0.034 ± 0.028 | 47% | 1.26% |
| Breaker (candle), breaker stop | +0.079 ± 0.017 | +0.031 ± 0.030 | 47% | 0.64% |
| Breaker (body), raid stop | +0.068 ± 0.016 | +0.048 ± 0.026 | 40% | 1.08% |

Paired: **−0.1, +0.9, +0.5 SE at 1R; −0.2, −0.2, +0.3 SE at 3R.** Trend-aligned,
the shipped entry is best again (+0.110 against +0.081, +0.064, +0.085).

The breaker here is the opposing candle whose extreme the shift broke, which
is distinct from the Order Block above (anchored to the impulse that made the
gap). Both land in the same place.

**Lower-timeframe entry** (`Min15` gap on a `Min30` structure), 816 paired
setups: filled 85% against 45% and scored the same, **−0.020 R (−0.4 SE)**.
Filling twice as often produced proportionally more wins *and* more losses.

All three move the entry along one axis — deeper fills less often at better
prices, shallower fills more often at worse ones — and all three net out. That
axis appears to be genuinely flat on this data.

**Watch the tight-stop variants.** The best-looking rows (OB/breaker with the
zone stop) have ~0.6% risk against the baseline's ~1.5%. Fees cost ~0.10R there
versus ~0.04R, so most of the apparent gain is a bill not yet paid.

### Exits

1006 trend-aligned setups:

| exit | R per setup | paired vs 1R |
|---|---|---|
| 1.0R, no break-even | +0.103 ± 0.022 | — |
| 1.5R, arm 1.0R, lock 0.1R | +0.103 ± 0.025 | +0.000 (+0.0 SE) |
| 2.0R, arm 1.0R, lock 0.1R | +0.102 ± 0.027 | −0.001 (−0.1 SE) |
| 3.0R, arm 1.5R, lock 0.1R | +0.116 ± 0.034 | +0.013 (+0.5 SE) |

Nothing separates. An earlier run of this same comparison found the far target
clearly worst and the ordering perfectly monotonic; on a later window with the
lookahead corrected, 3R is nominally **best**. That ranking was one window's
noise read as a result — it is the clearest illustration on this page of why a
confident-looking backtest number is not a finding.

**Trailing stops**, 1374 trend-aligned setups, five families: ATR(14)×2 from
entry −1.3 SE, ATR×2 armed at 1R +1.1 SE, 2-bar structure trail at 1R +0.6 SE.
All inside noise. Trailing from entry is nominally worst — a 2×ATR band sits
inside the normal retracement of a post-sweep move.

### Filters and sources

**Session timing**, using the reference indicator's own GMT+0 windows
(London 08–17, NY 13–22, Asia 00–09), 2000 setups in six exclusive buckets:

| window | all setups |
|---|---|
| Asia only 00-08 | +0.071 ± 0.026 (689) |
| Asia + London 08-09 | +0.179 ± 0.062 (113) |
| London only 09-13 | +0.030 ± 0.040 (297) |
| London + NY 13-17 | +0.075 ± 0.031 (451) |
| NY only 17-22 | −0.020 ± 0.039 (320) |
| outside all 22-00 | +0.018 ± 0.061 (130) |

Best minus worst is +2.7 SE, but that is the max-minus-min of **six** buckets,
which produces ~2–2.5 SE from noise alone — and the winner is a single hour
with the smallest sample. Rejected.

**Pool source:**

| pool | sweeps | setups | converts | R per setup |
|---|---|---|---|---|
| Pivot | 6114 | 1686 | 28% | +0.048 ± 0.017 |
| Day | 3286 | 311 | 9% | +0.094 ± 0.035 |
| Week | 295 | **0** | **0%** | — |

Day beats Pivot by +1.2 SE, which is nothing. Note that **conversion rate and
profitability are different questions** — Pivot converts three times as often
and scores no better per setup. Conflating the two once led to a wrong ranking
of what to build next.

**Week pools are the one actionable result on this page.** 295 sweeps produced
zero setups in 41.6 days. By the rule of three that bounds their conversion
below ~1%, against Pivot's 28%. They cost sweep alerts and return nothing —
see `RIPTIDE_USE_WEEKLY` in `riptide.conf`.

**A minimum risk floor.** `Cfg` has `max_risk_atr = 4.0` and no minimum, so
nothing stops a setup whose stop sits inside a single ordinary candle. A live
BTC_USDT alert on 5 Sep was stopped out with its stop about 1.0 ATR away,
which raised the obvious hypothesis: R normalises by risk, so a 1-ATR stop and
a 3-ATR stop both pay +1R when they work, but only the 1-ATR stop can be taken
out by noise.

Three thresholds were fixed before looking — reject below 0.50, 0.75, 1.00 ATR
— along with the rule that it ships only if the effect is **monotonic across
all three** and the best gap is ≥ 2 SE. 1210 setups, shipped config:

| floor | rejected (below) | kept | kept − rej |
|---|---|---|---|
| 0.50 ATR | −0.667 ± 0.333 (3) | +0.047 ± 0.024 (1207) | +2.1 SE |
| 0.75 ATR | +0.267 ± 0.228 (15) | +0.042 ± 0.024 (1195) | −1.0 SE |
| 1.00 ATR | +0.122 ± 0.136 (41) | +0.042 ± 0.024 (1169) | −0.6 SE |

**The hypothesis is wrong, and the monotonicity rule is what caught it.** The
0.50 row is +2.1 SE on *three setups*, and its sign flips under the old
`fvg_scan_from="grab"` config (+0.500 on two setups there). Taken alone it
would have read as a shippable result. The two thresholds with enough samples
to mean anything both run the *other* way: tight stops score slightly better,
not worse.

Across quintiles there is no gradient in either direction — the widest-stop
quintile is nominally the worst (+0.005 against +0.050 for the tightest), but
that is 0.6 SE, and 1.3 SE on the larger `grab` sample. Rejected; no floor added.

Two by-products worth keeping. Only 3% of setups have a stop under 1 ATR, and
the median is 2.58 ATR — so the BTC alert sat below the 10th percentile and was
not representative of a class. And fill rates confirm the stale-entry fix:
64–75% per quintile under `fvg_scan_from="mss"` against 40–60% under `"grab"`,
where entries routinely sat too far below market to ever fill.

### Structure timeframe: Min5 vs Min15 vs Min30

**The first measurement on this page that includes fees**, and it changes what
the numbers mean. Every other figure here is gross.

Two design points decide whether this comparison says anything. All three
timeframes see the **same 20.8 days** — 2000 bars is 6.9 days of Min5 but 41.6
of Min30, so equal bar counts would compare three market periods and call the
difference a timeframe effect. And the primary metric is **net of fees**,
because fees are a fixed fraction of notional while R is measured against the
stop: halve the timeframe, halve the stop, double the cost in R.

23 symbols, 20.8 days, 0.08% round trip (0.02% maker in, 0.06% taker out):

| tf | setups | per day | median risk | fill | gross R | cost | **net R** |
|---|---|---|---|---|---|---|---|
| Min5 | 1347 | 2.82 | 0.92% | 71% | +0.033 | 0.082 | **−0.049** |
| Min15 | 516 | 1.08 | 1.59% | 72% | +0.058 | 0.047 | **+0.011** |
| **Min30** | 277 | 0.58 | 2.37% | 69% | +0.090 | 0.032 | **+0.058** |

Both effects push the same way. Gross expectancy *rises* with timeframe
(+0.033 → +0.090) and cost *falls* (0.082 → 0.032), so the net gap is wider
than either alone. Min5 pays 8.2% of its risk in fees before it has done
anything.

**Min5 is measurably worse: −0.107 against Min30, −2.0 SE, and both halves of
the symbol set agree.** Min15 is −0.047 at −0.8 SE with the halves
disagreeing (−0.163 / +0.091) — indistinguishable, nominally behind. No change:
Min30 stays.

Band A confirmed, the part actually worth trading:

| tf | setups | gross | net |
|---|---|---|---|
| Min5 | 655 | +0.104 | +0.026 ± 0.032 |
| Min15 | 283 | +0.079 | +0.034 ± 0.048 |
| Min30 | 138 | +0.213 | **+0.178 ± 0.065** |

Min30 band A is the only cell that clearly survives its own costs, though 138
setups is thin and Min30-over-Min15 there is only 1.8 SE.

Alert volume, which is a cost of its own: at 23 symbols Min5 would produce
about **250 alerts a day** against Min30's 45.

**Fees make early signals unprofitable on every timeframe** — −0.103, −0.044,
−0.021 — where gross they are +0.042, +0.035, +0.039. Early runs a tighter
stop and fills more often, so it pays the round trip more times on a smaller R
denominator. One caveat before writing it off: this scores at a 1R target, and
early was separately measured to need a far target (its trend-aligned edge
only appeared at 3R). The 1R rule is the wrong one for it. What is not in
doubt is that its 1R edge does not survive costs.

Standing caveats: 20.8 days, one regime, and slippage is still not modelled —
only spread-free fees, so these are an upper bound.

### Early at a far target — the rescue that did not happen

The timeframe run left early unprofitable after fees at 1R, with one open
defence: 1R might simply be the wrong exit. `riptide.conf` recorded that
early's trend-aligned edge "only appears at 3R", and early runs a tighter stop
so it has more room in R terms. A far target also *dilutes* the fee — the cost
in R is FEE/risk whatever the target, but at 3R it is subtracted from a 4R
win-loss spread instead of a 2R one.

Tested paired, so every target is scored on the same 1374 early signals rather
than on two independent samples. 23 symbols, 41.6 days, fees included.

| target | hit target | stopped | timeout | gross | **net** |
|---|---|---|---|---|---|
| 1R | 42% | 36% | 2% | +0.057 | **−0.016** |
| 2R | 26% | 47% | 7% | +0.078 | **+0.006** |
| 3R | 17% | 52% | 11% | +0.067 | **−0.006** |

Paired against the shipped 1R: **3R is +0.010, +0.3 SE**, and the window halves
disagree (−0.040 first half, +0.057 second). 2R is +0.022 at +0.9 SE. Nothing.

**The defence fails, and the earlier claim does not survive being measured
properly.** It was computed gross, unpaired, on a different window. With fees,
pairing and splits, early sits within noise of zero at every exit tested —
three targets, two horizons, and a break-even variant. Its median fee cost is
0.066 R against 0.044 R for confirmed, because it runs a tighter stop and
fills more often, and that is structural rather than a quirk of one window.

Two by-products, both declared descriptive before the run and therefore **not
shippable on this evidence**:

**Confirmed setups nominally prefer a far target** — net +0.020 at 1R, +0.065
at 2R, +0.078 at 3R, paired +0.058 (+1.4 SE) for 3R over 1R. Suggestive, under
2 SE, and the obvious next pre-registered primary. `TRACK_TARGET_R` is 1.0.

**The break-even rule still does nothing, even at 3R** — +0.077 against +0.078
without it. That was the one place it might have mattered, since there is 3R of
open profit to protect rather than 1R. There is not. A longer horizon does not
help either: 120 bars gives confirmed +0.062 at 3R against +0.078 at 60.

Early band A at 3R is +0.093 ± 0.059, the only early cell that looks alive —
but that is a band × target slice of a descriptive branch, which is exactly
the shape of the false positives already buried on this page.

### Volume, and the context filters

The first tests using information the engine does not already have. Everything
above rearranges the same OHLC geometry.

**Sweep volume** (relative turnover on the raid bar, against the median of the
50 bars before it). Quintiles on R: +0.011, +0.095, +0.080, +0.052, +0.007 —
an inverted U, Q5 minus Q1 is −0.1 SE. Three pre-registered thresholds all
lean negative but none past −1.3 SE. **No effect on trade quality.**

But conversion is a different story, and a large one:

| sweep RVOL | → confirmed setup |
|---|---|
| Q1 0.01–0.98 | 26.4% ± 1.1 |
| Q2 0.98–1.55 | 20.3% ± 1.0 |
| Q3 1.55–2.35 | 14.6% ± 0.9 |
| Q4 2.35–4.08 | 10.6% ± 0.8 |
| Q5 4.08–387 | **6.5% ± 0.6** |

Monotonic over 7869 sweeps, **+15.6 SE**. A quiet raid is four times likelier
to reverse than a loud one — which inverts the folk premise. Volume surging
through a level is a *breakout*, not a stop run; the classic grab that snaps
back drifts through on thin participation. Note what this is not: the setups
that *do* come from loud sweeps score the same (−0.1 SE). Conversion and
expectancy are different questions. Actionable for sweep heads-ups, not for
setup quality.

**Volume profile.** Density in the path from entry to the 1R target, over a
500-bar / 100-bin profile built strictly before the signal. Confirmed Q5−Q1
was +2.1 SE — *backwards* from the premise (heavy volume in the path scored
better, not worse), not monotonic, and +0.7 SE on early. Density at the gap
(+1.4 SE) and density at the swept pool (−1.5 SE) point opposite ways. Noise.
Likely partly a proxy for risk size, which is itself null.

**BTC regime**, conditional on the symbol's own daily trend. One cell cleared
the pre-registered bar, and it should still not ship, because the 2×2 pattern
contradicts itself:

| | confirmed worst cell | early worst cell |
|---|---|---|
| | own against + BTC against, −0.063 | own **with** + BTC against, −0.062 |

The two strategies disagree about *which* combination is bad. And the design
was flawed: allowing "any of two rows" to pass doubles the false-positive rate
against what was intended. Rejected.

**Daily ADX level.** Not monotonic, confirmed +1.1 SE, early −0.4 SE with the
opposite sign. Null.

### RSI and RSI divergence

Divergence fits this strategy better than any indicator tested before it: the
raid is *by construction* a new price extreme, and the liquidity pool the
engine already tracks is the prior swing to compare against. So RSI at the
sweep bar against RSI at the pool's anchor bar is an exact comparison, not an
approximation. Signed so positive always means divergent in the trade's favour.

**Divergence: null.** +0.028, +0.6 SE, and the time split flips sign — −1.0 SE
in the first half of the window, +2.5 SE in the second. That flip is the whole
story: an effect that reverses between halves of one 41-day window is regime
noise, and it is exactly what the split rule exists to catch.

Worth keeping descriptively: only **30% of setups diverge in the trade's
favour**, median −3.4. RSI usually *confirms* the raid's extreme rather than
refusing it. The textbook setup is the minority case here.

**RSI level** (oriented to the trade: oversold for a long, overbought for a
short) passed the pre-registered rule at +0.106, +2.2 SE, with all four splits
the same sign. But it is **not an independent effect** — conditioned on DI it
only exists in one half:

| | RSI high | RSI low | gap |
|---|---|---|---|
| DI with | +0.175 (281) | +0.143 (306) | −0.009 (−0.1 SE) |
| DI against | +0.035 (311) | **−0.169 (287)** | +0.187 (+2.8 SE) |

RSI level does nothing when DI agrees with the trade, and rescues the trade
when DI does not. Its +2.2 SE main effect is entirely those counter-DI cells.
Ships as a modifier on that band if at all, never as its own axis — the two
measures agree on only 48% of setups, so this is a genuine interaction rather
than the same reading twice.

### DI direction — the strongest open hypothesis since the trend filter

Declared descriptive-only before the run, so **it is not shipped on this
evidence**. Recorded because it is the best candidate the project has found
since the SuperTrend, and because promoting a secondary to a finding is
exactly the flexibility pre-registration exists to stop.

Confirmed setups, 1185 scored:

| | with | against | gap |
|---|---|---|---|
| daily SuperTrend | +0.122 (582) | −0.026 (603) | +0.148 (+3.1 SE) |
| daily DI+/DI− | +0.158 (587) | −0.063 (598) | **+0.222 (+4.7 SE)** |

It is **not** the SuperTrend restated. The two agree on only 78% of signals,
and DI still separates after conditioning on it — +2.1 SE within the
trend-aligned half, +2.7 SE within the counter-trend half, same sign in both.

**It got that test, and it passed.** Re-run as a pre-registered primary under
a split rule that does not depend on early signals (which the section below
shows cannot discriminate a trend-derived effect):

| split | gap | |
|---|---|---|
| overall | +0.222 | **+4.7 SE** |
| symbols A (alternating by turnover rank) | +0.193 | +2.9 SE |
| symbols B | +0.253 | +3.8 SE |
| first half of the window | +0.279 | +4.0 SE |
| second half | +0.170 | +2.6 SE |

Every split the same sign, every split individually significant. That is a
stronger replication than the SuperTrend itself has, and DI's effect is
larger. **This is the second thing in the project that has ever separated,**
and the practical reading is that the daily trend axis should probably *be*
DI rather than the SuperTrend.

The standing caveat still applies and is not small: the symbol split is
genuinely out of sample across instruments and the time split across time, but
both halves are the same 41.6 days of the same market. A different regime can
still kill it. What it has earned is a place in the grade ladder and a live
`/stats` split, not a position size.

### The trend filter does not work on early signals

The most useful thing to come out of this round, and it affects what already
ships:

| | with the daily trend | against | gap |
|---|---|---|---|
| confirmed (1185) | +0.122 | −0.026 | +0.148 (+3.1 SE) |
| early (2945) | +0.035 | +0.065 | **−0.030 (−0.9 SE)** |

On early signals the daily trend shows no effect at all, and nominally the
wrong sign, over 2945 samples. The difference between the two strategies is
itself **+3.0 SE**, so this is not merely a weaker version of the same thing —
the axis that sorts confirmed setups does not sort early ones.

Two consequences. First, `GRADES` was measured on confirmed setups and is
applied to early alerts too, where the trend axis carrying almost all of the
separation appears not to hold — the letter on an early alert is less
meaningful than the letter on a confirmed one. Second, **early is not a valid
replication set for a trend-derived filter**, which retrospectively weakens
the replication requirement used above: the known-good control fails that same
test.

### Engine parameters

Six variants covering the reference indicator's own settings — `pivot_right`,
`tol_atr`, `max_overshoot_atr`, `max_bars_after_grab` — all inside noise. The
last of those was later swept on its own across six values; see below.

`max_bars_after_mss = 5` (against 10) drops 55 of 2034 setups and alters none.
Those 55 nominally scored better (+0.319 against +0.044), but on 55 samples
that is not readable. Reverted: the count reduction is certain, the quality
claim is not, and suppressing them would foreclose the live measurement that
could settle it.

**`max_bars_after_grab`** — how long a raid stays live waiting for a structure
break — swept properly across six pre-registered values:

| cancel at | setups | R per setup |
|---|---|---|
| 10 bars | 759 | +0.038 ± 0.030 |
| 20 bars | 1081 | +0.044 ± 0.025 |
| 30 bars | 1178 | +0.039 ± 0.024 |
| **50 bars** (shipped) | **1210** | **+0.045 ± 0.024** |
| 75 bars | 1196 | +0.046 ± 0.024 |
| 100 bars | 1183 | +0.047 ± 0.024 |

Flat. The whole range spans 0.009 R against standard errors of 0.025 — 0.3 SE
end to end. Kept at 50, which already admits 97% of setups: raid age at the
break has median 9 bars, p90 28, p99 67. Lowering to 10 costs 37% of alerts
and buys nothing measurable; raising past 50 reaches 2.8% more.

Fill rate is flat across age too (71–74% in every band), which is a coherence
check on `fvg_scan_from="mss"`: the entry gap comes from after the break, so an
old raid does not imply a stale entry.

**A late shift does widen the stop, and it does not matter.** The stop sits at
the raid extreme, so the longer a raid waits the further price has travelled
from it — median risk climbs 1.36% → 1.61% → 2.10% → 2.06% → 2.12% across
0-2, 3-6, 7-12, 13-25 and 26-50 bar bands. That is a real gradient and it is
why a 50-bar window occasionally produces a setup risking 16%.

But it costs nothing: within 12 bars nets +0.017, later nets +0.040, a −0.3 SE
difference. R already normalises by risk, and a wider stop is *cheaper* in fee
terms because the fixed round trip is a smaller fraction of it. So the case for
shortening the window is legibility, not money.

One cell stands out and is **not** being acted on: shifts arriving within 2
bars of the raid net **+0.169 ± 0.100 on 70 setups**, far above every other
band. It is 1.5 SE, on the smallest bucket, and it is the third different
slice of the same parameter — which is precisely the shape of the false
positives already buried on this page. Recorded as a lead.

**The method was wrong, and the verification step is what caught it.** The
plan was to run once at a ceiling of 200, record each setup's age, and read
every threshold off that one population — the parameter only ever *removes*
setups, so the books should nest. They do not. Re-running each candidate gives
1210 setups at 50 against 1128 predicted, and 759 at 10 against 656. Expiring
a cluster early frees later clusters that the long-lived one would have
suppressed through `mss_cooldown_bars`, so the threshold *creates* setups as
well as removing them — the count is not even monotonic (100 bars yields fewer
setups than 50). The re-run figures above are the authoritative ones.

Worth carrying forward: **no parameter sweep on this engine may assume
nesting.** Clusters interact, so a threshold must be measured by re-running it.

## Confluence — and the broken breaker underneath it

**The breaker was not a breaker.** `confluence_of` looked for the last candle
of the SAME polarity as the order block, anchored near the break extreme. Over
244 setups that returned the order block *itself* **60% of the time** — so
"2 of 2 zones agree" usually meant one candle agreeing with itself, and the
Pine drew two lines on top of each other, which is how it was spotted: the
reference showed two levels where ours showed one.

A breaker is an order block on the OPPOSITE side that failed. For a long, the
decline into the raid was loaded by the last UP-close candle before it; when
the shift breaks back above that candle it flips from resistance to support.
Different polarity, therefore a different candle by construction. `breaker_of`
now implements that, and additionally requires the shift to have actually
traded through the block — an unbroken block is not a breaker, just an order
block facing the other way. Coincidence with the order block is now **0%**.

Re-measured on 558 setups with a real breaker, net of fees:

| zones agreeing | n | gross | net |
|---|---|---|---|
| 0 of 2 | 285 | +0.018 | −0.020 |
| 1 of 2 | 223 | +0.131 | **+0.086** |
| 2 of 2 | 50 | +0.063 | +0.013 |

**2 minus 0 is +0.3 SE**, down from the +1.4 SE recorded under the old rule,
and it is not monotonic — one zone beats two. So part of that earlier +1.4 SE
was the double-count, and confluence is weaker than it already looked.

Nothing shipped has to be unwound: the grade ladder moved to DI × RSI before
this was found, and confluence stopped setting the letter then. It is still
recorded on every alert and in `outcomes`, so if it ever separates live, the
rows are there. On this window it does not.

The section below is the original write-up, kept because it is what the old
rule measured and because the entry-price tests in it are unaffected.

## Confluence — the original write-up

The tests above asked whether an Order Block or Breaker is a *better entry
price* than the gap. Flat, three times over. They never asked whether the zones
**agreeing** grades a setup, which is a different question and the more natural
use for them: keep the shipped entry, and score the alert by how many other
zones sit in the same price area.

1982 setups that had both an order block and a breaker:

| zones agreeing with the gap | all setups | trend-aligned | 3R |
|---|---|---|---|
| 0 of 2 | +0.043 ± 0.019 (1232) | +0.082 ± 0.028 | +0.032 ± 0.030 |
| 1 of 2 | +0.035 ± 0.032 (388) | +0.104 ± 0.045 | +0.042 ± 0.051 |
| 2 of 2 | **+0.106 ± 0.039** (362) | **+0.170 ± 0.057** | +0.064 ± 0.063 |

2 minus 0 is **+1.4 SE**. Taken alone:

| | agrees | does not | |
|---|---|---|---|
| Order block overlaps the gap | +0.096 ± 0.030 (542) | +0.037 ± 0.018 (1440) | +1.7 SE |
| Breaker overlaps the gap | +0.067 ± 0.030 (570) | +0.047 ± 0.018 (1412) | +0.6 SE |

And by how far the order block sits from the gap entry, in ATR: Q1 (0.00–0.24)
+0.090, Q2 +0.045, Q3 (0.51–0.99) +0.017, Q4 +0.059.

**Not a finding.** +1.4 to +1.7 SE across four framings is roughly what the
maximum of four tests produces from noise, and the primary is **not monotonic**
— 1 of 2 came in *below* 0 of 2, which a real effect should not do. The
trend-aligned column is monotonic and the OB-distance quartiles agree with the
OB-overlap result, so two roughly independent framings point the same way. That
is more than any rejected variant above managed, and still not enough.

So it ships the only way an uncertain signal should: **as a label, never as a
filter.** Every alert carries `●●` / `●○` / `○○`, no setup is suppressed, and
`outcomes.confluence` lets `/stats` split live results by it. If the effect is
real it will show up out of sample; if it is the fourth false positive on this
page, nothing was lost but a line of text.

Note also that the breaker contributes almost nothing on its own (+0.6 SE) —
if this survives, the order block is doing the work.

## The grade on each alert

Two lines on the alert — a trend note and a zone count — asked the reader to
combine them. They are now one graded line, with the bands read off the joint
cells rather than invented:

| | 0 zones | 1 zone | 2 zones |
|---|---|---|---|
| **with the trend** | +0.083 (620) | +0.109 (188) | **+0.170 (173)** |
| **against** | +0.001 (625) | −0.025 (204) | +0.047 (189) |

Every with-trend cell beats every against-trend cell, and within with-trend the
confluence ordering is monotonic — which is what makes a ladder defensible:

| grade | | share of alerts | measured |
|---|---|---|---|
| 🟢 **A+** | with the trend · gap, order block and breaker agree | 9% | +0.170 ± 0.057 |
| 🟢 **A** | with the trend · gap and order block agree | 9% | +0.109 ± 0.045 |
| 🟡 **B** | with the trend | 31% | +0.083 ± 0.028 |
| 🟠 **C** | against the trend | 50% | +0.008 |
| ⚪ **?** | trend unknown | rare | — |

**Read the steps honestly.** Only the **B/C step is established** — that is the
trend filter, +0.110 ± 0.029, +3.8 SE, replicated three times. **A+ over B is
+0.087 ± 0.064, which is +1.4 SE and not significant**, and against the trend
the confluence ordering breaks down entirely (1 zone scores *below* 0 zones).

So B versus C is a real distinction; A+ versus A versus B is a hypothesis being
tracked live. Four bands rather than ten because the data cannot resolve ten,
and no band is a prediction about any single trade — C averages roughly zero,
not a loss.

Nothing is suppressed by grade. `/stats` reports by grade so live data settles
the top of the ladder, and grades are computed from the stored `trend_dir` and
`confluence` columns rather than stored themselves — so revising the ladder
re-grades history instead of stranding it.

## What this adds up to

Tested: six engine parameters, two entry timeframes, five exit families, four
targets, Order Block entries (four variants), Breaker Block entries (four
variants), session timing (six buckets), pool source, a minimum risk floor
(three thresholds). **Every one came back inside noise.** One thing has ever
separated, and it keeps replicating.

The reasonable conclusion is not that these need testing more carefully. It is
that the structural variations genuinely do not matter much on this data, and
the remaining headroom is not in another entry *price* — nor, now, in another
entry *filter*.

Zone confluence is the one live candidate, at +1.4 SE — shipped as a score
rather than a filter, precisely because that is not enough to act on.

## Duplicate alerts, and what the collapse is allowed to merge

Three signal types each sent the same event more than once, because several
liquidity pools sit in the same price area: one bar runs through all of them,
or several clusters reach the same gap. Measured over 20 symbols:

| | raw | sent | merged |
|---|---|---|---|
| 👀 sweep | 1085 | 917 | 168 |
| ⚡ early | 501 | 347 | 154 |
| 🎯 confirmed | 228 | 224 | 4 |

`collapse()` merges on (event, direction) and keeps the tightest stop; the
group size survives as `pools` and is printed on the alert, so four pools taken
in one candle reads as a stronger signal in one message rather than four
messages.

**The sweep key includes the shift level, and that is not incidental.** Two
pools taken by the same bar can need *different* levels broken for the shift to
confirm — they are two setups in waiting, not one. 37 same-bar groups disagreed
on it, and merging those would have dropped a real alert. Adding it to the key
put 39 sweeps back.

`run_engine(collapse_dupes=False)` returns the raw stream so this is a test
rather than a claim in a comment. The test asserts two things on every merged
group: that `raw − sent == merged` (nothing vanishes uncounted), and that the
members agreed on direction, entry/extreme and shift level — meaning only the
named pool and the stop distance differed. Both hold across 20 symbols.

Worth recording how this was found: the duplicate was reported on early
signals, fixed there, and I then said twice that the confirmed path was clean,
citing a measurement that returned zero on 30 symbols which happened to contain
no case. Writing one test across all three types failed immediately on the
third. A rule enforced in one place needs verifying in one place.

## How far price has already run when the alert lands

Found while answering "why didn't we catch this move" on AKE, not
pre-registered — so it was replicated before being written down.

Measure, at the close of the bar that produces the alert, how far price sits
past the alert's own entry, in units of that alert's risk. Zero means the
entry is still live at current price; +1R means price has already travelled a
full stop-distance beyond the entry you are being told to buy. Then score the
setup the way the tracker does: 12 bars to fill, 1R target, 48-bar horizon,
**an unfilled setup counts as 0.0** rather than being dropped.

23 symbols, 41.6 days.

| gap at alert | confirmed n | fill % | R/setup | early n | fill % | R/setup |
|---|---|---|---|---|---|---|
| 0 – 0.25R past | 262 | 93% | +0.057 | 686 | 92% | +0.063 |
| 0.25 – 0.5R | 146 | 71% | +0.187 | 380 | 78% | +0.207 |
| 0.5 – 1R | 109 | 55% | +0.241 | 233 | 64% | +0.388 |
| over 1R past | 32 | 50% | +0.500 | 56 | 59% | +0.589 |

Monotone in both columns and it goes the *opposite* way to the intuition. The
alerts that look worst on arrival — price already gone, entry stranded behind
it — are the ones that pay. Half of them never fill and are scored zero
anyway, and they still beat the tidy ones almost 5:1.

The obvious objection is that this is the risk gradient wearing a disguise: a
gap measured in R is large when the stop is small, and small stops already
score better. It is not. Splitting into risk terciles, the gradient holds
inside every one of the six panels, monotone in all six — including the wide-stop
confirmed tercile where the *level* is around zero but the ordering survives
(-0.064 → -0.014 → +0.000).

Out of sample, taking the top band minus the bottom as the primary:

| split | confirmed | early |
|---|---|---|
| all | +0.253 (3.1 SE) | +0.413 (7.5 SE) |
| symbols A | +0.305 (2.8 SE) | +0.375 (4.9 SE) |
| symbols B | +0.196 (1.6 SE) | +0.455 (5.8 SE) |
| first half of window | +0.245 (1.9 SE) | +0.325 (4.0 SE) |
| second half | +0.267 (2.5 SE) | +0.494 (6.6 SE) |

Same sign in all ten, and on early it is the largest and most consistently
replicated effect this project has measured — larger than DI (+0.222) and
larger than the daily trend filter. On confirmed it is real but weaker, and
two of the four splits are under 2 SE.

Caveats before anything is built on it. Nothing here is fee-adjusted, and the
high-gap band skews toward tighter stops within a tercile, where 0.08% round
trip costs more R. The 1R scoring is generous to a band whose whole character
is a violent impulse followed by a pullback — the fill often happens on a bar
that also reaches target, and bar-order assumptions decide that case. And it
is one window.

What it is not is a filter. Suppressing the low-gap alerts throws away 93% of
the fills to keep a band that trades half the time; the honest use is
**ranking** — the number belongs on the alert, so a stranded entry reads as
what the data says it is rather than as a miss.

## Why AKE's +69% was not caught, and what it actually shows

The complaint was that a large AKE rally on 5 Sep ran out of a consolidation
Riptide had not marked. It had. The sequence, on 30m:

    04 Sep 11:00  pool swept
    04 Sep 21:00  raid extreme 0.012785
    05 Sep 00:30  structure shift
    05 Sep 01:00  gap → CONFIRMED LONG, entry 0.014121, stop 0.012785
    05 Sep 01:30  alert goes out — price 0.016588

The pattern completed and the alert fired. It was unusable, because by the
time the gap bar closed price stood **17.5% above the entry it named**, and the
limit was never touched again inside the fill window — it filled a day later,
on 6 Sep 06:30, in a different context. Had it filled it was worth +5.6R with
a worst case of +1.1R.

So the failure is not detection and not the shift being slow. It is that the
entry is a retracement into a gap, and a vertical move does not retrace. That
is the same phenomenon the table above measures, at its extreme: gap 1.85R
past entry, fill 0, scored 0.0.

The three other largest AKE advances in the window read the same way — raids
detected beforehand in every case, the shift level sitting above where price
was when the move began.

## The two pivot rules are nested, so one comparison colour is empty

The "Riptide + ICT" preset was asked for with three colours: ICT-only,
Riptide-only, and both. Only two of those can ever appear.

Both rules use the same look-back (1) and differ only in bars-after — the
reference uses 1, Riptide 2. A bar that is the strict extreme of a 4-bar
window is necessarily the strict extreme of the 3-bar window inside it, so
every Riptide swing is also an ICT swing. The reference does not see
*different* swings, it sees *more* of them.

Checked rather than argued, on 6 symbols over 41.6 days:

| | ICT (right 1) | Riptide (right 2) | Riptide-only |
|---|---|---|---|
| swing highs | 2821 | 2194 | **0** |
| swing lows | 2816 | 2212 | **0** |

Zero out of roughly 12,000. 22% of the reference's marks are ones Riptide
declines to take.

So a Riptide-coloured diamond already means both rules agree, and the pale
colour means the reference alone. A third colour would have been a legend
entry for a case that cannot occur.

This is also the whole of why their chart looks busier at the swing level, and
it is a rule difference and not a bug in either.

## Stale day levels, and the raid that cannot confirm

Raised as "why this live sweep, it doesn't make sense" — a raid dot on HYPE
30m, 6 Sep 16:00 chart time. The mark was correct and the instinct behind the
complaint was also correct, for a reason neither the chart nor the alert said
out loud.

What it took: **3 Sep's high at 88.142**, still unswept three days later. Its
shift level was **83.510**, which is 4 Sep's low — 5.9% below the raid extreme
of 88.780. Confirming meant price travelling 5.9% the other way inside the
grab window.

The engine keeps EVERY unswept previous-day high and low, not just
yesterday's, and the structure level is the opposing extreme measured back
from the bar that set the level. So the longer a level survives, the further
its shift level drifts, and a raid on a week-old level asks for a move nothing
is going to deliver. Both the Pine input and its tooltip said "Yesterday's
high / low", which is simply wrong and hid this.

23 symbols, 41.6 days, 3702 raids:

| source | n | median shift distance | over 4% away | reached a confirmed setup |
|---|---|---|---|---|
| Pivot | 2747 | 2.59% | 32% | 19.5% |
| Day | 955 | 4.56% | 57% | 6.4% |

And the gradient itself, all sources pooled:

| shift level sits | n | → confirmed | → early |
|---|---|---|---|
| under 1% away | 322 | 37.0% | 45.0% |
| 1 – 2% | 830 | 25.5% | 41.2% |
| 2 – 4% | 1128 | 16.8% | 40.2% |
| 4 – 8% | 865 | **7.2%** | 40.1% |
| over 8% | 557 | **2.7%** | 39.5% |

The HYPE dot sat in the 4-8% band: about a 7% chance of ever becoming the X
it was provisionally standing in for.

**It is not a filter, and the early column is why.** Conversion to a confirmed
setup collapses 37% → 3%, but conversion to an early signal is flat at ~40%
across every bucket, and so is what those early signals are worth:

| shift level sits | early n | R/signal | SE |
|---|---|---|---|
| under 1% | 142 | +0.211 | 0.076 |
| 1 – 2% | 329 | +0.206 | 0.048 |
| 2 – 4% | 407 | +0.194 | 0.042 |
| 4 – 8% | 298 | +0.104 | 0.052 |
| over 8% | 178 | +0.222 | 0.063 |

No gradient, not even a monotone one. Day-source early signals score +0.175
against Pivot's +0.185. So a far shift level says the *confirmed* path is
unlikely and says nothing at all against the *early* one — suppressing these
raids would delete real early signals to remove a mark that is merely
uninformative.

Confirmed setups that do occur off a far level are worse (+0.318 / +0.219 /
+0.027 / -0.001 across the first four buckets, top minus bottom +2.5 SE), but
that is 54 setups in the far bucket, one window, and was not pre-registered.
Not acted on.

What changed: the sweep alert now prints the distance and the base rate for
it, and the two input labels no longer claim the levels are yesterday's.

## The standing caveat

Everything above shares one 41.6-day window, on symbols chosen by their
turnover *today* — survivorship bias, one regime, no out-of-sample data. The
trend-filter estimate moved 35% in a few hours of fresh candles. A confident
monotonic exit ranking evaporated on the next window.

That is what `riptide/tracker.py` exists for. `/stats` scores live alerts
forward from the moment they fire, out of sample, in whatever regime actually
occurs. At ~39 entry signals a day across two strategies, a thin read takes
about 10 days and one that could see a 0.1R difference about 52.

**Where live data disagrees with this page, believe the live data.**
