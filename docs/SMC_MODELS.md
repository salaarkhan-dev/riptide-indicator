# Smart Money Concepts — the models, and what Riptide measured about each

Two things are in this file and they should not be confused.

**The sequences** are the canon as taught. They are written here precisely,
long and short, because a half-remembered sequence is how people end up taking
a trade that has three of the five conditions.

**The verdicts** are this project's own measurements — 9,000 to 10,000 signals
per test on 333 days across ~110 MEXC perpetuals, paired on identical setups
wherever the comparison allows it. They are not opinions about ICT and they are
not from a book. Where a verdict contradicts the canon, the canon is what is
taught and the verdict is what happened.

The short version: **the base model works and almost every refinement of it
does not.**

---

## Model 1 — Liquidity Sweep → MSS → FVG

The core reversal model (ICT's "2022 model" is this plus an HTF bias step).
This is what Riptide trades and what every other model here is measured
against.

### LONG sequence

```
1.  LIQUIDITY EXISTS BELOW
    Equal lows, a prior swing low, PDL, or a session low.
    Two or more touches at the same price. One low is not liquidity.

2.  PRICE RAIDS IT
    Price trades BELOW that level and does not hold. The wick beyond it
    is the point — that is the stops being taken.

3.  DISPLACEMENT UP
    An aggressive up-move that closes above the most recent swing HIGH of
    the local structure. This is the MSS (market structure shift).
    Closing through it matters; a wick through it does not.

4.  IT LEAVES AN FVG
    Three candles where candle 3's LOW is above candle 1's HIGH.
    The untraded gap between them is the entry zone.

5.  ENTRY
    Limit order at the NEAR edge of that gap (the top, for a long).

6.  STOP
    Below the raid extreme — the lowest price of the sweep.

7.  TARGET
    Opposing liquidity: prior highs, equal highs, PDH.
```

### SHORT sequence

```
1.  LIQUIDITY EXISTS ABOVE — equal highs, prior swing high, PDH, session high
2.  PRICE RAIDS IT — trades above and fails to hold
3.  DISPLACEMENT DOWN — closes below the most recent swing LOW → MSS
4.  IT LEAVES AN FVG — candle 3's HIGH below candle 1's LOW
5.  ENTRY — limit at the near edge of the gap (the bottom, for a short)
6.  STOP — above the raid extreme
7.  TARGET — sell-side liquidity: prior lows, equal lows, PDL
```

### Measured

The base model, gates as shipped, 333 days: **+0.045 R per setup**, ~1,200
setups. Modest and positive. Everything below is measured against it.

---

## Model 2 — Order Block

**LONG:** the last DOWN-close candle before an up-displacement that breaks
structure. Enter on the retrace into that candle's range.
**SHORT:** the last UP-close candle before a down-displacement.

A *volumetric* order block adds the requirement that the candle traded above
its own recent median volume. The reference indicator adds a further one: the
displacement off it must be at least **2 ATR**.

### Measured — REJECTED as an entry

Paired against the FVG near edge on 9,863 signals, R per signal:

| entry | vs near edge |
|---|---|
| order block extreme | **−0.027** (−2.3 SE) |
| order block mid | **−0.048** (−3.5 SE) |
| volumetric OB extreme | −0.023 (−1.4 SE) |
| volumetric OB mid | −0.037 (−2.2 SE) |

Worse, and the volumetric filter does not rescue it. **Caveat:** the 2-ATR
displacement qualifier was *not* tested — that version of the order block is
still open.

---

## Model 3 — Breaker Block

An order block that **failed and flipped**.

**Bullish breaker:** price makes a low, rallies to a high, then breaks *below*
that low (taking sell-side). The bearish order block up at the high is now
violated. When price rallies back through it, that zone becomes **support**.

**Bearish breaker:** the mirror — a bullish OB that price broke down through
becomes **resistance**.

The logic is that trapped traders defend it: everyone short from the broken
zone is now offside and covers there.

### Measured — counted, never isolated

Riptide's `confluence_of` counts a breaker sharing the gap's price area as one
of two confluence votes. Breaker confluence was measured at **+0.079 ± 0.017**
on confirmed setups in an early pass — but that is a 42-day number, and every
42-day result in this project that was later re-run on 333 days either shrank
or reversed. It has not been re-run. Treat as **unproven**.

---

## Model 4 — Unicorn

A **breaker and an FVG that overlap**. Enter in the overlap only.

The claim is that two independent reasons for a zone are stronger than one.
Sequence is Model 1's, with step 4 replaced by "the FVG must sit inside a
breaker".

### Measured — not tested as a model

Riptide counts breaker + order block as confluence 0–2 but never required the
*overlap* as an entry condition. Genuinely open.

---

## Model 5 — Turtle Soup (sweep-and-reverse, no MSS)

```
LONG:   equal lows swept → price immediately reclaims → enter
SHORT:  equal highs swept → price immediately rejects → enter
```

No structure shift required. Faster, earlier, and by construction less
confirmed. **Riptide's "Early" signal is this model** — the first imbalance
after the raid, within 10 bars, with no shift.

### Measured — works, barely, and it is the fragile half

Early signals are net positive but thin. The engine's own docstring names the
failure mode exactly:

> *"There is no confirmation that the sweep reversed anything, so a pool taken
> in a trend keeps going and the signal is simply wrong."*

What buys that back is geometry: the stop sits at the raid extreme, a few
candles away, so risk per signal is small.

Tested this session — **pool width does not predict which ones fail.** Wide,
sloppy pools scored +0.028 against +0.000 for tight ones (|z| 0.9, wrong sign
for the hypothesis), consistent across both window halves and all three
stop-size terciles.

---

## Model 6 — AMD / Power of 3

```
ACCUMULATION   price ranges, building orders
MANIPULATION   a sweep out of one side of the range — the trap
DISTRIBUTION   expansion the other way
```

On a daily candle: open → wick against the day's direction (manipulation) →
body expansion → close near the extreme.

**LONG:** range, sweep BELOW it, expansion up.
**SHORT:** range, sweep ABOVE it, expansion down.

This is the framing behind Model 1 rather than a separate entry — the raid is
the manipulation, the displacement is the distribution.

### Measured — not testable as stated

There is no operational definition of "accumulation range" in the engine.
The manipulation-and-expansion half *is* Model 1 and is measured there.

---

## Model 7 — Silver Bullet

A **time-gated** version of Model 1. Look for an FVG formed inside a fixed
window, enter the retrace, target the nearest liquidity.

Windows (New York time): **03:00–04:00**, **10:00–11:00**, **14:00–15:00**.

### Measured — session filters are OFF in the reference too

The reference indicator ships `By Session` **unchecked**, along with `By Daily
Bias` and `By Trend`. Its own author does not gate on time by default.

This project measured session buckets — Asia-only came in at +0.071 ± 0.026 —
and session filtering is on the research ban list precisely because it is a
large family of cuts with an obvious multiple-comparison problem: three
windows × two directions × several timeframes will hand you a winner by
construction.

**Not recommended without a pre-registered held-out test.**

---

## Model 8 — OTE (Optimal Trade Entry)

After a displacement leg, retrace into the **0.62–0.79** Fibonacci zone of that
leg. The "sweet spot" is **0.705**.

**LONG:** anchor 0 at the leg low, 1 at the leg high; buy the 0.62–0.79 pullback.
**SHORT:** mirror.

### Measured — REJECTED, and it is the worst family on the board

Paired against the near edge on 9,863 signals, anchored on the reclaim leg
(raid extreme → leg peak, which is the anchor a trader actually draws):

| entry | vs near edge |
|---|---|
| Fib 0.5 | **−0.020** (−2.3 SE) |
| Fib 0.618 | **−0.041** (−3.9 SE) |
| **Fib 0.786** | **−0.066** (−5.0 SE) |

Monotone: the deeper the retracement you wait for, the worse you do. Fib 0.786
is the single worst entry of twelve tested.

**And the mechanism is worth understanding, because it generalises.** A deeper
entry only fills when price came back further — and price coming back further
means the reclaim was weaker. It is not the same trade at a better price; the
depth is itself a signal, and it is a bad one. On a 42-day sample Fib 0.786
looked like the *best* entry. The deep re-run reversed it at −5.0 SE.

---

## Model 9 — SMT Divergence

Two correlated assets, one sweeps its level and the other does not.

**LONG:** BTC makes a lower low, ETH does not → the low is false → long.
**SHORT:** BTC makes a higher high, ETH does not → short.

### Measured — not tested

Riptide is single-symbol per signal. `decouple.py` touched correlation but SMT
as an entry condition has never been measured here. **Open.**

---

## Model 10 — FVG Continuation

Not a reversal. In an established trend, buy bullish FVGs on the way up.

**LONG:** HTF trend up → price pulls back into a bullish FVG → continue long.
**SHORT:** mirror.

### Measured — FVG retest is one of the few positives

`fvg_continuation.py` exists, and the FVG-retest feature scored positive on all
four splits (+0.063 / +0.071 / +0.158 / +0.098). That is a 42-day result and
has not been re-run deep. **Promising, unproven.**

---

## The scoreboard

Everything this project has actually measured, on the deep window unless noted.

### Entry — twelve alternatives, all worse

| | vs the shipped FVG near edge |
|---|---|
| FVG mid / consequent encroachment | −0.012 (−1.8 SE) |
| Fib 0.5 | −0.020 (−2.3) |
| FVG far edge | −0.022 (−2.4) |
| volumetric OB extreme | −0.023 (−1.4) |
| order block extreme | −0.027 (−2.3) |
| MSS bar extreme (displacement origin) | −0.030 (−1.6) |
| volumetric OB mid | −0.037 (−2.2) |
| Fib 0.618 | −0.041 (−3.9) |
| order block mid | −0.048 (−3.5) |
| market entry at the MSS close | −0.058 (−2.3) |
| the swept level (retest) | −0.062 (−4.7) |
| Fib 0.786 | −0.066 (−5.0) |

**The near edge of the FVG wins, and nothing is close.**

### Stop — eight anchors, the structural ones are worst

| | vs the shipped raid-extreme stop |
|---|---|
| raid + 0.25 ATR | +0.007 (+1.1 SE) — the only positive, not established |
| raid + 1 ATR | +0.004 (+0.4) |
| raid − 0.25 ATR | −0.010 (−1.3) |
| the swept level | −0.020 (−1.8) |
| MSS invalidation | −0.023 (−0.4) |
| sweep bar extreme | −0.026 (−3.6) |
| **FVG invalidation** | **−0.119 (−6.1)** |

**Stop at the raid extreme.** "Stop at FVG invalidation" is the single worst
idea measured in this project.

### Exit

| | |
|---|---|
| target 2R | the control |
| target 3R | +1.8 SE over the window — **but first half −0.8, second half +3.6.** A window effect. |
| break-even at 1R | −0.074 (−2.5 SE) |
| every path-conditional rule | beaten by flat 3R |
| partial at 0.5R | win rate 38%→64%, R −0.104. Buys comfort, costs money. |

**2R fixed. No break-even. No trailing.**

### Filters — 21 tested, 1 survived

The survivor is the **HTF point of interest**: the raid landing inside an
aligned order block or FVG on a higher timeframe. It passed a pre-registered
held-out test on symbols it was not found on, **on Min30**. On Min60 it points
the other way and is not worth having.

Everything else — RSI divergence, EMA, ADX, SuperTrend as a hard gate, BTC
trend, volume, volatility, Bollinger bands, symbol scoring, trendline
confluence, pool touch count — failed.

---

## What this adds up to

1. **Take the base model.** Liquidity → sweep → MSS → FVG. It is the only one
   here with a measured positive edge that survived a deep re-run.
2. **Enter at the near edge.** Not the midpoint, not consequent encroachment,
   not an OTE retracement, not the order block. Every one of those is measurably
   worse, and the deeper ones are worse in proportion to their depth.
3. **Stop at the raid extreme.** Not at FVG invalidation — that is −6.1 SE.
4. **Target 2R.** Fixed, no management.
5. **On Min30, require the HTF point of interest.** It is the one filter that
   earned its place.
6. **Stop adding conditions.** Twenty-one filters, twelve entries, eight stops,
   eleven exit rules. The base model beat all of them. Every refinement tested
   here has cost money, and the ones that looked best on a small sample were
   the ones that reversed hardest on a large one.

The uncomfortable finding underneath all of it: **being able to predict
something is not the same as being able to trade it.** The path to 1R predicts
the path to 2R enormously — fast, clean trades reach 2R 57% of the time against
29% for slow ones — and no rule built on that made a single R. Filtering on a
predictor only pays when the group you exclude is *negative*, not merely *less
positive*.
