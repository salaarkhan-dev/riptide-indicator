# Measurements

Every strategy question tested on this project, what came back, and what was
done about it. Written down because most of these came back negative, and a
negative result nobody recorded gets re-tested in a month.

## CORRECTION — the backtest scorer was wrong, and most numbers below are inflated

Found on 7 Sep while measuring exits. **Every ad-hoc backtest script in this
session scored outcomes from the SIGNAL bar instead of the FILL bar.**

    if not any(entry touched in the next 12 bars): return 0.0
    for c in cs[i+1 : i+1+48]:          # <- i is the SIGNAL bar, not the fill
        if stop hit: return -1.0
        if target hit: return +1.0

The fill check and the outcome loop were separate. If the entry filled on bar
i+5, bars i+1 to i+4 were scored as though a position already existed. Entries
are RETRACEMENTS, so before the fill price sits on the profitable side of the
entry — the error therefore manufactured wins and almost never manufactured
losses.

| | signals with the target reached before the fill | old | fill-anchored | inflation |
|---|---|---|---|---|
| early | 12.8% | +0.191 | +0.076 | **+0.115 (9.1 SE)** |
| confirmed | 18.9% | +0.328 | +0.193 | **+0.135 (4.2 SE)** |

Roughly 60% of the early "edge" and 40% of the confirmed "edge" was the bug.

**`riptide/tracker.py` does NOT have this bug** — it holds a row PENDING until
the entry is touched and only then evaluates. `/stats` was never affected, and
forward numbers remain the ones to trust. This was throwaway research code.

### What survives re-running

| claim | status |
|---|---|
| risk cap 2.5 ATR on confirmed **(shipped)** | **stronger.** +0.135 vs +0.031 for 4.0, total R 32.0 vs 16.5 — it doubles total R rather than matching it |
| daily DI over 4h DI **(shipped)** | **holds.** +2.2 SE against +0.9 SE |
| 4h SuperTrend over daily **(shipped)** | **much weaker.** +2.1 SE against daily's +1.8 SE, where it read +3.7 against +2.2. Both are marginal now; 4h is no longer clearly better |
| the impulse-gap effect (never shipped) | **largely gone.** Still monotone on early but tiny (-0.021 to +0.130), and it now runs the OPPOSITE way on confirmed (+0.215 down to +0.115). It was headlined at +7.5 SE. It was the bug |
| early signals generally | **thinner than reported.** +0.076 at 1R, not the +0.114 quoted |

Everything below this section that quotes an R value was produced with the
broken scorer unless it says otherwise. **Treat the levels as inflated and the
comparisons as suspect** — especially any comparison where one group takes
longer to fill than the other, because that group collected more free bars.
The impulse-gap result is exactly that failure mode: a large gap means a
slower fill means more pre-fill bars.

## Re-measured on the corrected scorer — entry-side features

18 features, both signal types, 36 comparisons, run through
`research/studies/features.py` on `research/harness.py`. Live windows (10 fill
bars, 60 horizon), fill-anchored outcomes, fees included, and the harness's own
bar: monotone AND >= 3 SE AND one sign on all four splits AND surviving the
stop-size control.

**Nothing passed. Not one of the 36.**

| feature | confirmed | early |
|---|---|---|
| MACD histogram sign agrees | -0.081 (-0.5) | -0.057 (-1.2) |
| Stochastic extension our way | -0.051 (-0.3) | +0.069 (+1.0) |
| CCI extension our way | +0.268 (+1.9) | +0.032 (+0.5) |
| raid extreme outside Bollinger | +0.040 (+0.4) | +0.043 (+0.8) |
| rejection wick / range | -0.026 (-0.2) | -0.017 (-0.2) |
| raid body / range | +0.276 (+1.9) | +0.184 (+2.7) |
| range width before the raid | +0.036 (+0.2) | +0.022 (+0.3) |
| pool age | +0.264 (+1.7) | +0.089 (+1.3) |
| hour of day | +0.078 (+0.5) | -0.066 (-1.0) |
| **price past entry at signal** | **-0.233 (-1.5)** | **-0.008 (-0.1)** |
| displacement | +0.109 (+0.7) | +0.056 (+0.8) |
| gap share of the leg | -0.151 (-1.0) | -0.005 (-0.1) |
| imbalances in the leg | +0.224 (+2.0) | -0.032 (-0.3) |
| swings in the pool | +0.051 (+0.5) | -0.056 (-0.9) |
| Day pool vs Pivot | too few | +0.024 (+0.4) |
| confluence score | -0.005 (-0.0) | -0.016 (-0.3) |
| stop size (% risk) | +0.352 (+2.4) | +0.191 (+2.9) |

Two entries deserve naming.

**The impulse-gap effect is dead.** It was headlined in this file at +7.5 SE
and is now -1.5 SE on confirmed and -0.1 on early — it has changed SIGN. It
was the scorer bug in its purest form: a large gap means a slow fill means
more free pre-fill bars, so the feature was partly measuring the bug itself.

**Stop size now runs the OTHER way.** Wider stops score better (+0.352 /
+0.191), where the broken scorer said tighter. Both readings are partly
mechanical rather than an edge: fees cost `0.08 / risk_pct` R, so a wide stop
is cheaper per unit of risk. And risk_pct is not the same axis as the ATR cap
— it mixes stop width with symbol volatility, which ATR normalises away. It
does not by itself contradict the 2.5 ATR cap; that is re-measured separately.

**Confluence is flat at -0.005 and -0.016.** The order block and breaker
agreement, the thing this indicator draws in yellow and orange, sorts nothing.

## Re-measured on the corrected scorer — decisions and exits

`research/studies/decisions.py`. Min30, live windows, net of fees.

### The 2.5 ATR risk cap survives, and it is the peak

| cap | n | R/signal | total R |
|---|---|---|---|
| 1.5 ATR | 72 | -0.081 | -5.8 |
| 2 ATR | 146 | -0.005 | -0.8 |
| **2.5 ATR (shipped)** | 246 | **+0.083** | **+20.4** |
| 3 ATR | 358 | +0.045 | +16.3 |
| 4 ATR | 558 | +0.005 | +2.9 |

Unchanged decision, and on better evidence than it was made with: at 4 ATR
confirmed setups are worth essentially nothing.

### Exits — confirmed

| policy | R/signal | total R | vs 1.5R |
|---|---|---|---|
| target 1R | +0.083 | +20.4 | |
| target 1.5R (baseline) | +0.160 | +39.5 | |
| target 2R | +0.215 | +52.8 | +1.6 SE |
| target 2.5R | +0.242 | +59.6 | +1.6 SE |
| target 3R | +0.252 | +61.9 | +1.5 SE |
| BE arm 1R lock 0.1R | +0.129 | +31.7 | **-1.8 SE** |
| BE arm 1.5R / 2R lock 0.1R | +0.160 | +39.5 | 0.000 |
| half 1.5R, half 3R | +0.192 | +47.2 | +1.2 SE |
| horizon 20 bars | +0.063 | +15.6 | **-3.3 SE** |
| horizon 40 bars | +0.106 | +26.2 | **-3.2 SE** |

**Only one result clears 3 SE, and it is a negative: cutting the horizon
short costs real money.** 20 bars loses 60% of the total R against 60 bars.
Let trades run.

Targets are monotone and total R triples from 1R to 3R, but every step is
about 1.5 SE, so the ladder is direction without proof.

**The break-even rule is worthless or harmful.** Arming at 1R costs -1.8 SE.
Arming at 1.5R or 2R with a 1.5R target cannot trigger at all, which is the
setting the alert has been advising — a no-op dressed as advice. The
pre-registered prediction (BE lowers expectancy) was right.

### Exits — early, and this is the finding that matters

| target | R/signal | total R |
|---|---|---|
| 1R | -0.033 | **-45.5** |
| 1.5R | -0.016 | -22.7 |
| 2R | +0.008 | +10.5 |
| 3R | +0.013 | +17.8 |

**Early signals are net negative after fees at the target the bot actually
tracks.** Not weak — negative, across 1384 signals, and no exit policy rescues
them: every break-even, partial and horizon variant sits between -0.019 and
+0.013. On the broken scorer they read +0.114.

This is 33 alerts a day, the majority of what the bot sends, and the strategy
the user said mattered most. It needs a decision, not a tweak.

### Structure timeframe

| | R/signal | total R |
|---|---|---|
| Min30 confirmed | **+0.083** | +20.4 |
| Min15 confirmed | -0.067 | -15.1 |
| Min30 early | -0.033 | -45.5 |
| Min15 early | -0.065 | -88.1 |

30m confirmed. 15m is worse on both, so that question stays closed.

### Trend timeframe — the 4h switch was wrong and is reverted

| reading | with | against | separation | |
|---|---|---|---|---|
| **daily SuperTrend** | +0.201 | -0.049 | **+0.250** | +2.4 SE |
| 4h SuperTrend | +0.183 | -0.031 | +0.214 | +2.0 SE |
| **daily DI** | +0.204 | -0.062 | **+0.266** | +2.5 SE |
| 4h DI | +0.088 | +0.077 | +0.011 | +0.1 SE |

Daily is ahead on both axes. `TREND_INTERVAL` is back to `Day1`, where it was
before the broken numbers moved it. Daily DI is the one reading the correction
barely touched — +0.250 before, +0.266 after — which is some comfort about the
axis the grade is built on, though at 2.5 SE it still does not clear the bar.

## Re-measured — volume, RSI, ADX, BTC regime, volatility

`research/studies/context.py`. Volume was untestable until now: `Candle` had
no volume field, so every earlier "volume" test was measuring something else.

| feature | confirmed | early |
|---|---|---|
| sweep-bar relative volume | +0.100 (+0.7) | +0.049 (+0.7) |
| gap-bar relative volume | -0.169 (-1.1) | +0.014 (+0.2) |
| RSI extension at the raid | +0.296 (+1.9) | +0.025 (+0.4) |
| chart DI agrees | -0.241 (-1.5) | -0.078 (-1.6) |
| ATR percentile (volatility regime) | +0.017 (+0.1) | -0.001 (-0.0) |
| BTC DAILY trend agrees | -0.094 (-0.9) | **-0.122 (-2.6)** |
| **BTC 30m trend agrees** | +0.192 (+1.8) | **+0.174 (+3.6) — RETIRED, see `three_ideas.py`: −0.6 SE held out** |

> **LABELS SWAPPED — see the BTC sign correction at the end of this file.**
> Both BTC rows read backwards: they measure BTC going the OTHER way.
> Every other row in this table is unaffected — the bug was only in the
> two BTC helpers in `context.py`.

**The canonical volume premise is false here.** A liquidity grab is supposed
to print a volume spike; relative volume on the raid bar sorts nothing
(+0.7 SE on both). Nor does volume on the gap bar. That closes the whole
volume family, now that it can actually be measured.

**RSI, chart DI and volatility regime: nothing.**

### BTC 30m regime — the only thing that has cleared the bar since the fix

> **LABELS SWAPPED — see the BTC sign correction at the end of this file.**
> DISAGREES and AGREES are the wrong way round throughout this section.
> The +0.174 at 3.6 SE is real and belongs to BTC going AGAINST the trade.

    early, n=1384
      BTC 30m trend DISAGREES   -0.129  (n=626)
      BTC 30m trend AGREES      +0.045  (n=758)
      top-bottom +0.174 ± 0.048   +3.6 SE   monotone
      splits  +0.264 / +0.081 / +0.154 / +0.189
      risk terciles  +0.112 / +0.188 / +0.203      => CANDIDATE

It clears every gate: 3.6 SE, same sign on all four splits, and it survives
the stop-size control with the sign intact in all three terciles. Confirmed
setups point the same way at +1.8 SE.

**And it takes early signals from negative to positive.** Early is -0.033 R
overall; the with-BTC half is +0.045 and the against half is -0.129. That is
the first thing measured on the corrected scorer that would change what the
bot sends rather than how it is described.

**One thing about it is wrong, though, and it should be said before anyone
acts.** The DAILY BTC trend points the OTHER WAY, at -2.6 SE on the same
signals. Both readings are internally consistent across splits, and they
contradict each other. Either the 30m version is picking up something real
about intraday alt-follows-BTC while the daily is mean-reversion, or one of
them is a coincidence dressed in four agreeing splits. 14 comparisons were
run in this batch, so a single 3.6 SE result is not the same evidence as a
3.6 SE result that was predicted in advance — and this one was not.

Not shipped. It needs its own pre-registration on fresh data, and the daily
contradiction resolved.

## Break-even, measured properly at last

It shipped at `be_arm_r = 1.5` for months, printed on every alert as advice,
and had never been tested. The first test used a 1.5R target, where a 1.5R arm
can never trigger — so it registered as a harmless no-op. At the 2R target now
in use it CAN trigger, which made the question real.

| policy | confirmed R | vs none | early R | vs none |
|---|---|---|---|---|
| no break-even | **+0.216** | | **+0.008** | |
| arm 1.0R lock 0.1R | +0.142 | **-2.5 SE** | -0.000 | -0.7 SE |
| arm 1.5R lock 0.1R | +0.197 | -1.3 SE | +0.001 | -1.3 SE |
| arm 1.75R lock 0.1R | +0.208 | -1.0 SE | +0.007 | -0.5 SE |

**It loses at every arm level, on both signal types, and the earlier the arm
the more it loses.** Total R on confirmed drops from +53.1 to +34.8 at a 1R
arm. The mechanism is not subtle: it converts trades that would have reached
target into +0.1R scratches, and 26% of confirmed setups reach 3R.

Switched off, and the alert no longer prints the line. Advice on an alert
should have cleared a bar before it was given; this one was never asked.

## BTC regime — pre-registered, held out, and the honest verdict

The one candidate to survive the scorer correction, tested the way it should
have been from the start. Pre-registration in
`research/studies/PREREG_btc.md`, written before the held-out data was
fetched: direction stated in advance (BTC 30m AGREEING predicts higher R), the
daily contradiction named as the thing that had to resolve, and the bar set at
3 SE on held-out data alone.

**Held-out window: 16 Jun – 27 Jul 2026, 1390 early signals.** It ends where
the discovery window begins. Nothing in this project had ever looked at it.

| BTC timeframe | disagrees | agrees | difference | |
|---|---|---|---|---|
| **30m** | -0.113 | +0.010 | **+0.123** | +1.8 SE |
| **1h** | -0.140 | +0.041 | **+0.182** | +2.7 SE |
| 4h | -0.013 | -0.065 | -0.051 | -0.8 SE |
| daily | -0.065 | -0.014 | +0.051 | +0.8 SE |

**The direction replicated. The magnitude did not.** 30m came back at +0.123
against the +0.174 it was found at — about 70%, with the same sign on all four
splits. That is the classic shape of a real effect overestimated in the window
that discovered it. It did not clear 3 SE, so by the pre-registered rule it is
**not shipped as a filter**.

**The contradiction resolved, and in the effect's favour.** The daily BTC
trend read -0.122 at -2.6 SE on the discovery window and +0.051 at +0.8 SE
here — it was noise, not a competing mechanism. What is left is coherent:
short BTC timeframes carry the signal (30m +1.8 SE, 1h +2.7 SE) and it decays
to nothing by 4h. Alts follow BTC intraday and stop following it by the day.

**1h is stronger than 30m on held-out data**, which was not predicted and is
therefore exploratory. Not acted on.

What shipped: the alert now says whether BTC agrees, appended to the existing
trend line rather than given one of its own, on confirmed and early alerts
alike. `btc_dir` is recorded on every signal, so `/stats` accumulates forward
evidence on it out of sample. Nothing is suppressed.

That is the whole point of the distinction: a filter would have been a claim,
and the evidence does not support a claim. A line on the alert is context, and
the evidence supports that.

## Where it stands — the shipped configuration, 41.6 days, 23 symbols

`research/studies/standing.py`. Min30, target 2R, cap 2.5 ATR confirmed and
4.0 early, break-even off. "win" is the share of FILLED trades ending
positive; R per signal counts an unfilled setup as zero.

| | n | fill | win | median risk | GROSS R | total | net R | total |
|---|---|---|---|---|---|---|---|---|
| CONFIRMED | 246 | 71% | 49% | 1.26% | **+0.270** | +66.5 | +0.227 | +55.8 |
| EARLY | 1384 | 80% | 39% | 1.24% | **+0.080** | +110.9 | +0.021 | +28.9 |
| BOTH | 1630 | 79% | 41% | 1.24% | +0.109 | +177.5 | +0.052 | +84.7 |

Gross is with no fees and no slippage. Net models the fees a limit-entry
strategy actually pays.

### Fees were being overstated, and it mattered most where the edge was thinnest

Every earlier number charged 0.08% — taker on both sides — to every trade.
That is wrong for this strategy. **The entry is always a LIMIT order at the
gap, so it pays maker (0.02%), and a target exit is also a limit.** Only the
stop is a market order. So a winner costs 0.04% round trip and a loser 0.08%.

| | flat 0.08% | maker/taker modelled |
|---|---|---|
| confirmed | +0.216 (+53.1) | **+0.227 (+55.8)** |
| early | +0.008 (+11.5) | **+0.021 (+28.9)** |

Early's net total goes from +11.5 to +28.9 — it was being charged taker fees
on trades it exits with a limit. `simulate` now takes `fee_maker`/`fee_taker`;
the flat `fee_pct` remains so older numbers stay reproducible.

**Fees still take 74% of the early edge and 16% of the confirmed edge**, and
that ratio is the whole story of the difference between them. Cost in R is
`fee / risk_pct`, and the median stop here is 1.24%, so every round trip is
3-6% of the risk taken. Early signals earn +0.080 R gross; there is not much
room in that for anything.

### Early signals, split by BTC

> **LABELS SWAPPED — see the BTC sign correction at the end of this file.**
> The two rows below are labelled backwards. `standing.py` carried the
> same bug: +0.179 belongs to BTC AGAINST, -0.055 to BTC agreeing.

| | n | fill | win | GROSS R | total | net R | total |
|---|---|---|---|---|---|---|---|
| BTC 30m agrees | 800 | 77% | 44% | **+0.179** | +143.1 | +0.125 | +99.8 |
| BTC 30m against | 584 | 84% | 33% | **-0.055** | -32.2 | -0.121 | -70.9 |

At the 2R target the split is much starker than it was at 1R: the agreeing
half is the better of the two signal types on a per-signal basis, and the
disagreeing half is a straight bleed. Note the fill rates run the wrong way —
the losing half fills MORE often (84% against 77%), which is what a losing
trade looks like from the entry side: price comes back to you because it is
going through you.

Still not a filter. It is 1.8 SE on held-out data and the bar is 3.

### Per symbol

Best five by total gross R: PUMPFUN +30, ZEC +24, BTC +19, SOL +19, HYPE +18.
Worst five: ADA +2, LINK -2, DASH -7, LTC -12, AKE -13.

**Do not act on this.** 23 symbols scored twice is 46 comparisons on 41.6 days
with 5-17 confirmed signals per symbol; a spread from +30 to -13 is what
random numbers look like at that sample size. Dropping the bottom five would
be fitting the window, and the two that look worst — AKE and LTC — are also
among the thinnest. It is recorded because per-symbol edge is a real question,
and it needs per-symbol sample sizes this window cannot supply.

## A 300 USDT account, simulated

`research/studies/equity.py`. Chronological replay: risk 1% of the balance AT
ENTRY so it compounds, 10x, target 2R, maker 0.02% / taker 0.06%. No slippage,
no funding, no liquidation, no downtime.

| strategy | trades | win | end USDT | return | max DD | skipped |
|---|---|---|---|---|---|---|
| confirmed only | 170 | 49% | 504.70 | +68% | 10% | 4 |
| early only | 199 | 41% | 375.96 | +25% | 14% | 908 |
| early, BTC agrees only | 152 | 40% | 347.81 | +16% | 18% | 467 |
| **confirmed + early(BTC agrees)** | 343 | 44% | **546.18** | **+82%** | 23% | 450 |

> **LABELS SWAPPED — see the BTC sign correction at the end of this file.**
> The two `BTC agrees` rows are really `BTC against`, so the +82%
> headline selected the half the corrected measurement calls better — the
> number stands, the name on it does not. Rows without BTC in the label
> are unaffected.
| everything | 329 | 39% | 349.38 | +16% | 21% | 952 |
| — max 5 open | 126 | 51% | 488.08 | +63% | **7%** | 667 |
| — max 10 open | 317 | 46% | 623.41 | +108% | 16% | 476 |
| — risk 0.5% | 394 | 43% | 428.69 | +43% | 9% | 399 |
| — risk 2% | 286 | 44% | 750.28 | +150% | **34%** | 507 |
| — risk 3% | 151 | 44% | 569.71 | +90% | 27% | 642 |

### The finding is the "skipped" column, not the returns

**450 to 950 signals could not be taken because the margin was already
committed.** At 1% risk on a 1.24% stop the position is 242 USDT of notional —
24 USDT of margin at 10x — so a 300 USDT account holds about twelve at once,
and the engine produces 1630 signals in 41.6 days. **At this size the binding
constraint is capacity, not signal quality.**

That is why raising the risk lowers the trade count (394 trades at 0.5%, 151
at 3%): a bigger position fills the margin faster and blocks the next signal.
And it is why "everything" underperforms the filtered set — the losing early
signals do not merely lose, they occupy margin a better signal needed.

A real system would prioritise by grade when margin is short. This one takes
whatever arrives first, which is the honest baseline and beatable.

### What these numbers are not

**They are not a forecast, and the differences between the variants are
mostly noise.** Every parameter in the shipped configuration was chosen on
this exact 41.6-day window — the 2.5 ATR cap, the 2R target, the BTC split.
Replaying it here measures how well the choices fit the data they were chosen
from. That is an upper bound.

+82% in 41.6 days is roughly +1.5% a day compounding, which nothing sustains.
The max drawdown numbers are the more useful half: 23% on the headline
variant, 34% at 2% risk. And drawdown is the one figure a backtest
systematically understates, because it never models the day the API is down
with positions open.

`/stats`, scoring forward at 2R, is the number that decides this.

## How losing trades actually fail

`research/studies/losers.py`. Not a filter hunt — twenty-one attempts to
separate winners from losers before the fact have failed. This asks what
happened AFTER the entry.

| | confirmed (88 losers) | early (675 losers) |
|---|---|---|
| never got into profit | 0% | 0% |
| got under 0.5R | 36% | 38% |
| got 0.5 – 1R | 35% | 35% |
| got 1 – 1.5R | 17% | 17% |
| got past 1.5R and still lost | **11%** | **9%** |
| **price reached 2R AFTER the stop** | **25%** | **36%** |
| stopped within 3 bars of filling | 24% | 31% |
| median bars held — losers / winners | 8 / 22 | 7 / 14 |
| worst 5 days hold | 27% of losers | 19% |

Two things look immediately actionable and only one of them is.

### The stop is NOT too tight — measured, and it is the opposite

A quarter to a third of losers saw price reach the target after being stopped
out, and on confirmed setups winners carry WIDER stops than losers (1.44%
against 1.13%). The obvious read is that the stop needs room. `sl_buffer_atr`
had been 0.0 since the beginning and had never been swept, so it was swept.

| sl_buffer_atr | confirmed R | total | early R | total |
|---|---|---|---|---|
| **0 (shipped)** | **+0.227** | **+55.8** | **+0.020** | **+28.0** |
| 0.1 | +0.149 | +32.8 | +0.011 | +15.4 |
| 0.25 | +0.151 | +28.6 | +0.013 | +17.9 |
| 0.5 | +0.033 | +4.9 | -0.007 | -9.1 |
| 0.75 | -0.014 | -1.5 | -0.030 | -40.6 |
| 1.0 | +0.052 | +3.7 | -0.028 | -36.4 |

**Worse at every level, on both signal types.** Zero is the peak. R is measured
in units of risk, so a wider stop shrinks every win in R terms; the trades it
saves are not worth what it gives up on the ones that were already working. It
also pushes setups over `max_risk_atr` — confirmed drops from 246 signals to
72 at 1.0 ATR — so part of the decline is the cap eating the sample.

The distinction worth keeping: a NATURALLY wide stop is good (winners have
them) and an ARTIFICIALLY widened one is bad. A deep raid that leaves the stop
far away is information; adding a buffer to a shallow one is just paying more
for the same trade.

### The clustering is the real finding

27% of confirmed losers fall on five days out of forty-two. That is not
twenty-four bad signals, it is five bad days — one market move taking out
everything at once, which is correlation risk and not signal quality. Nothing
about a single alert can see it coming.

It is also the one thing already shown to be fixable. In the equity
simulation, capping concurrent positions at five cut maximum drawdown from
23% to 7% while keeping most of the return. That is a portfolio rule, not a
strategy rule, and it is where the remaining improvement on this project
plausibly lives.

## Portfolio rules — where the remaining improvement is

`research/studies/portfolio.py`. 300 USDT, 10x, target 2R, maker/taker fees.
Judged on return per unit of maximum drawdown, because a strategy that doubles
through a 50% drawdown is not tradeable by a person.

| rules | trades | win | return | max DD | ret/DD |
|---|---|---|---|---|---|
| everything, no rules | 313 | 41% | +28% | 21% | 1.30 |
| max 12 open | 281 | 41% | +30% | 16% | 1.84 |
| **max 8 open** | 154 | 44% | +34% | 15% | 2.21 |
| max 5 open | 96 | 40% | +11% | 12% | 0.89 |
| max 3 open | 61 | 38% | +1% | 9% | 0.05 |
| max 8, cap 5 same direction | 147 | 39% | +16% | 16% | 0.99 |
| max 8, cap 3 same direction | 136 | 38% | +9% | 19% | 0.47 |
| **max 8, 3 slots for confirmed** | 182 | **46%** | **+46%** | **13%** | **3.67** |
| max 8, early needs BTC | 233 | 44% | +49% | 18% | 2.67 |

> **LABELS SWAPPED — see the BTC sign correction at the end of this file.**
> This row and every `ALL RULES` row below filter on `early_needs_btc`,
> which selected BTC AGAINST. `max 8, 3 slots for confirmed` — the rule
> `TRADING.md` actually recommends — uses no BTC condition and is clean,
> as are the plain caps, the direction caps and the daily loss stops.
| max 8, stop day at -4% | 148 | 43% | +34% | 13% | 2.67 |
| max 8, stop day at -6% | 195 | 41% | +24% | 15% | 1.54 |
| ALL RULES together | 116 | 46% | +31% | 15% | 2.11 |
| ALL RULES, flat sizing | 119 | 45% | +26% | 15% | 1.68 |
| ALL RULES, risk 2% | 114 | 45% | +59% | 24% | 2.39 |
| ALL RULES, risk 0.5% | 123 | 44% | +12% | 6% | 2.00 |

**Drawdown falls monotonically as the cap tightens** — 21 / 16 / 15 / 12 / 9%
— and that part is structural rather than fitted. Return does not: below eight
positions it falls faster than the drawdown does, and a cap of three earns
+1%.

**Reserving slots for confirmed setups is the best rule measured, and it is
the one with a mechanism rather than just a number.** Confirmed setups are
worth 3.4x an early one per signal (+0.227 against +0.021) and early signals
outnumber them 5.6 to 1 — so without a rule the worse signal crowds out the
better one purely by arriving first. Win rate rises to 46% and drawdown falls
to 13%.

**Capping same-direction positions is worse than no rule at all** (0.47
against 2.21). It reads like correlation control and behaves like blocking the
winners during the trending moves that pay for everything else.

**Stacking every rule is worse than the best single rule** — 2.11 against
3.67. Each rule blocks trades, and blocked trades include the good ones.

**A daily loss limit is noise.** -4% scored 2.67, -6% scored 1.54, -10% never
triggered. A threshold that flips the answer between adjacent values is not a
rule.

### The caveat that applies to this whole table

Sixteen configurations on one 41.6-day window, with the best selected after
the fact. That is the multiple-comparison hazard in its plainest form, and the
spread from 0.05 to 3.67 is mostly what noise looks like at this sample size.
Two things survive that objection because they have mechanisms independent of
the numbers: drawdown falling with the concurrency cap, and the better signal
being crowded out by the more frequent one. The rest is a table to re-run, not
a set of parameters to adopt.

Written up as rules in `TRADING.md`.

## Candlestick reversal patterns at the raid

Five patterns, in the direction the trade needs, tested on the raid bar and
anywhere from the raid to the signal. `research/patterns.py`,
`research/studies/candles.py`.

### Piercing Line and Dark Cloud Cover cannot happen here

The textbook definition requires the bar to OPEN BEYOND the previous close —
a gap. A 24/7 perpetual has no gaps: bar i opens where bar i-1 closed, to the
tick. Measured: **0 of 1638 signals, and 0 of 1999 bars scanned in either
direction.**

Any indicator labelling these on a crypto chart has dropped the gap condition.
That is a different pattern wearing the same name, and it is what
`piercing_gapless` implements — close back past the midpoint of the previous
opposing body, no gap required.

### Everything else: flat

24 comparisons across engulfing, engulfing of a small body, hammer / shooting
star, morning / evening star, and any-of-them, on the raid bar and across the
raid-to-signal window. Nothing exceeded ±1.3 SE on either signal type. The
largest was morning/evening star anywhere, confirmed, at +0.143 (+0.9 SE).

### The one candidate, and its refutation

Gapless piercing / dark cloud, anywhere raid-to-signal, on early signals:

    discovery window   without -0.043 (n=1054)   with +0.217 (n=338)
                       +0.260, 3.2 SE, monotone, control held   => CANDIDATE

Found among 26 comparisons and not predicted in advance, so it went to a
held-out window ending 28 Jul that had never been looked at, with the
direction stated in writing first.

    held out           without -0.035 (n=1168)   with -0.112 (n=292)
                       -0.078, -1.0 SE, and NEGATIVE on all four splits

**It reversed sign.** The 3.2 SE was one of twenty-six comparisons landing
where chance puts one. Rejected.

Worth setting beside the BTC regime result, which went through the identical
process and came back at +0.123 with the same sign on all four splits — 70% of
its discovered size. That is the difference between a real effect overestimated
where it was found and a number that was never anything. Both looked the same
on the discovery window; only the held-out test told them apart.

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

**BTC regime**, conditional on the symbol's own daily trend.

> **LABELS SWAPPED — see the BTC sign correction at the end of this file.**
> Every "BTC against" below is really "BTC agrees" and vice versa. The
> self-contradiction it reports is unaffected by relabelling — swapping both
> columns leaves the two strategies still disagreeing about which cell is bad
> — so the REJECTION stands and only the cell names are wrong. This is also
> the section I cited on 8 Sep to dismiss the grade-A BTC result as a known
> unstable interaction. That reasoning was built on inverted labels.

One cell cleared the pre-registered bar, and it should still not ship, because
the 2×2 pattern contradicts itself:

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

What changed: the sweep alert appends the distance to the line that already
names the shift level — "Shift confirms below 83.51 · 5.9% away" — and the two
input labels no longer claim the levels are yesterday's.

The first version put the conversion rate on the alert too, as its own line.
That was reverted on the day it shipped: a sweep alert is read in two seconds
to decide whether to open the chart, and a sentence of statistics is not what
that decision needs. The distance stays because it costs no line and answers
the one question the level alone left open — whether the shift is a candle
away or a day away. The base rates live here.

## The raid dot never moved

Reported as "this live sweep is invalidated, there is a new high — shouldn't
it be here". It should have been. The dot was in the wrong place.

`drawRaidDot` puts the provisional dot on the chart in EITHER draw mode — the
comment beside it says so, deliberately, because most raids never produce a
shift and the dot is what stands in for the X until one does. But the call
that moves a raid's marks to each new extreme was guarded:

    if trailed and not deferred
        moveGrab(c)

`deferred` is the DEFAULT draw mode ("On MSS confirmation"). So on default
settings every raid dot was pinned to the first bar of the raid and never
moved again, while the engine underneath went on trailing the extreme.

The guard was right for the X and its tag, which genuinely do not exist yet in
deferred mode, and wrong for the dot, which does. `moveGrab` is na-safe per
handle, so dropping the guard moves only what is on screen.

How wrong it was, over 3703 raids on 23 symbols:

| | extension past the pinned bar |
|---|---|
| moved at all | 88% |
| moved more than 0.5% | 75% |
| median | 1.71% |
| 75th percentile | 4.22% |
| 90th percentile | 9.24% |

**Chart only. The bot was never affected** — `riptide/engine.py` trails
`grab_high`/`grab_low` in the same block it always did, so stops on ⚡ EARLY
alerts were always measured from the real extreme.

### And no, a new extreme does not invalidate the raid

The obvious follow-on question, and the first cut of it looked emphatic:
grouping raids by how far the extreme ran, conversion to a confirmed setup
fell 35.4% → 7.2% and early R fell +0.532 → -0.085.

**That table is worthless and I nearly reported it.** The extension was
measured over the whole grab window, which includes bars after the signal. "A
raid that kept running against you did badly" is the outcome restated, not a
predictor.

Measured causally — extension known AT the signal bar, and split by stop size,
since a longer raid mechanically means a wider stop:

| extension at signal | early, tight stops | mid | wide |
|---|---|---|---|
| under 0.25% | +0.224 | +0.209 | +0.055 |
| 0.25 – 0.75% | +0.391 | +0.183 | +0.090 |
| 0.75 – 1.5% | — | +0.142 | +0.146 |
| over 1.5% | — | +0.300 | +0.156 |

No gradient, no consistent sign, and the wide-stop column runs the *opposite*
way to the contaminated version. Confirmed setups behave the same. Nothing
changed on the strategy: the raid keeps trailing to the new extreme, and the
only thing that expires it is the grab window.

## Batch 3 — MACD, oscillators, candle shape, pattern context

Fourteen features, pre-registered with their predicted direction before
anything was computed, scored on 1839 signals across 23 symbols. Bar for
calling something real: monotone, top minus bottom at least 3 SE, same sign on
all four splits, and surviving a stop-size control.

**Twenty-six comparisons. Nothing passed.** Top-minus-bottom R per signal:

| feature | early | confirmed |
|---|---|---|
| MACD histogram sign agrees | -0.081 | -0.288 |
| MACD histogram slope agrees | -0.085 | -0.151 |
| Stochastic extension our way | +0.068 | -0.099 |
| CCI extension our way | -0.003 | +0.089 |
| raid extreme outside Bollinger | -0.068 | -0.076 |
| rejection wick / range | -0.082 | -0.094 |
| raid-bar body / range | **+0.188** | +0.105 |
| daily MACD sign agrees | -0.012 | +0.163 |
| daily MACD slope agrees | -0.085 | -0.151 |
| daily RSI extension our way | -0.180 | **-0.251** |
| ATR compression before the raid | -0.039 | -0.112 |
| range width before the raid | +0.002 | +0.159 |
| pool age | -0.073 | -0.175 |
| hour of day | -0.124 | -0.133 |

Worth naming what died. **MACD adds nothing** on either timeframe, in sign or
slope, and the chart-timeframe version is mildly negative — the same result the
chart SuperTrend gave, and for the same reason: an oscillator that turns with
the move turns at the reversal being traded. **Bollinger** does not separate,
so "the sweep pierced the band" is not information the pool level did not
already carry. **ATR compression and range width** both fail, which is the
coiled-spring/consolidation-breakout idea and it is not there. **Pool age**
fails as a signal ranking even though it strongly predicts whether a raid
CONFIRMS — those are different questions and it only answers the first.

Two pre-registered directions came back inverted, which is worth more than a
result that merely fails:

- **The rejection wick is not the tell.** ICT reading says a long wick beyond
  the pool is the confirmation. Wick fraction scored -0.082 / -0.094, and body
  fraction — its opposite — was the largest number in the table. A decisive
  raid candle beats a hesitant one.
- **Daily RSI extension the trade's way is BAD**, -0.251 on confirmed and
  monotone. The grade already uses CHART RSI extension the other way round.
  Below the bar and not acted on, but it says the two timeframes are not the
  same variable and the grade should not assume they are.

### The one thing worth another look

Raid-bar body ratio, restricted to early signals whose price gap at the signal
is under 0.25R:

| split | n low body | n high body | high - low R | |
|---|---|---|---|---|
| all | 228 | 228 | +0.349 | +4.0 SE |
| symbols A | 120 | 120 | +0.294 | +2.5 SE |
| symbols B | 108 | 108 | +0.308 | +2.4 SE |
| window 1st half | 108 | 109 | +0.339 | +2.7 SE |
| window 2nd half | 119 | 120 | +0.341 | +2.8 SE |
| tight stops | 95 | 95 | +0.404 | +2.9 SE |
| wide stops | 133 | 133 | +0.294 | +2.6 SE |

Same sign and nearly the same size in all six sub-splits. **It is still not a
finding**: the low-gap restriction was chosen after seeing that body did
nothing in the other buckets, so the 3 SE bar was never really in force. It is
a hypothesis with a good-looking first look, and it needs its own
pre-registration on fresh data.

What makes it interesting rather than noise is where it sits. Body and the
impulse-gap effect are **substitutes, not additions** — the same "decisive
beats hesitant" story measured two ways:

| | body effect inside it | | | gap effect inside it | |
|---|---|---|---|---|---|
| gap under 0.25R | +0.349 | +4.0 SE | small body | +0.613 | +6.2 SE |
| gap 0.25 - 0.75R | -0.021 | -0.2 SE | mid body | +0.480 | +5.3 SE |
| gap over 0.75R | -0.073 | -0.6 SE | big body | +0.151 | +1.6 SE |

Each one stops mattering once the other is already large. So body is not a new
axis to stack on the grade — it is a way to reach the 93%-fill low-gap bucket,
which is the biggest and worst-scoring group and the one the gap measure calls
uniformly mediocre.

## Batch 4 — the rest of the SMC doctrine

Riptide already implements the core of it: pool, sweep, structure shift, gap.
These are the parts of the doctrine it does NOT implement, each pre-registered
with the direction the doctrine claims, on 1888 signals across 23 symbols.

| concept | doctrine says | early | confirmed |
|---|---|---|---|
| premium / discount at entry | buy in discount | **-0.176** | **-0.242** |
| displacement (leg range in ATR) | bigger is better | -0.171 | -0.322 |
| pool tightness (equal highs/lows) | tighter is better | +0.082 | -0.041 |
| inducement before the raid | present is better | -0.003 | -0.030 |
| gap share of the leg | bigger is better | -0.038 | +0.049 |
| imbalances stacked in the leg | more is better | -0.147 | -0.110 |
| order block unmitigated | fresh is better | not measured | not measured |

**Nothing passed.** Two of these need their failures described precisely
rather than filed under "flat".

**Displacement runs backwards.** The doctrine is that a real reversal moves
with energy. The smallest-displacement quartile scored best on both signal
types (+0.33 early, +0.35 confirmed, against +0.16 and +0.03 for the largest).
Non-monotone, so not a finding in reverse either — but it is not support.

**Premium / discount points the right way and still fails.** It is the only
concept whose sign matched the doctrine: entries deep in discount scored
+0.27 against +0.09 in premium on early, -2.6 SE overall. It is non-monotone,
and the pre-registered control kills it — entry deep in discount means entry
near the raid extreme, which means a TIGHT STOP, and tight stops already score
better. Inside risk terciles it is -1.8 / -0.4 / -2.3 on early and -0.8 /
-1.9 / -0.0 on confirmed. No consistent effect once stop size is held.

### Two errors in this batch, both mine

**The gap-share feature was miscoded.** It computed entry-to-stop distance
divided by the leg, not gap size divided by the leg. As coded it was close to
a restatement of premium/discount — risk is measured from the raid extreme —
and it produced the largest number in the batch at 4.7 SE. Recomputed with the
actual gap size it is -0.7 SE and +0.6 SE. The 4.7 SE was an artefact of
measuring the same thing twice, and it was one rounding step away from being
reported as a finding: the monotonicity check rejected it on values that print
as +0.18 and +0.18 and are actually 0.1750 and 0.1826.

**Order block mitigation was not measured at all.** The test asked whether
price traded back into the block between the block bar and the signal, and the
block sits immediately before the gap, so the answer was yes for 1888 of 1888
signals. A degenerate feature returns no buckets and silently drops out of the
table. It needs a definition that looks at the bars before the raid, not after.

## Structure timeframe x trend timeframe

Asked directly: 15m for entries, 4h for the trend. Both halves measured, 23
symbols, net of fees at 0.08% round trip.

### 15m for entries: worse

| structure TF | early | confirmed |
|---|---|---|
| Min15 | +0.073 | +0.075 |
| Min30 | **+0.114** | **+0.110** |

Min30 wins on both signal types. The gap is about +1.2 SE on early — not
decisive on its own, but it is the same direction the earlier Min5/Min15/Min30
comparison found, and 15m's tighter stops make fees bite harder: median risk
1.14% against 1.21%, so the same 0.08% round trip costs 0.070R instead of
0.066R while the gross edge is smaller too.

### 4h for the trend: yes for the filter, no for DI

This is the useful half, and it forced a config change. Separation between
with-trend and against-trend, Min30 confirmed, net of fees:

| reading | separation | | splits |
|---|---|---|---|
| **4h SuperTrend** | **+0.255** | +3.7 SE | +3.0 / +2.2 / +2.7 / +2.6 |
| daily SuperTrend | +0.150 | +2.2 SE | |
| **daily DI** | **+0.250** | +3.7 SE | +2.3 / +2.9 / +3.0 / +2.2 |
| 4h DI | +0.001 | +0.0 SE | -0.6 / +0.7 / +0.2 / -0.2 |

The 4h SuperTrend replicates on all four splits and beats the daily one it
replaces. **4h DI is a flat null on every split** where daily DI is the
strongest thing this project has measured.

Those were ONE setting. `TREND_INTERVAL` drove the SuperTrend filter and DI
alike, so moving the filter to 4h — the change that looks like an
improvement — would silently have moved the grade letter onto an axis that
sorts nothing. They are now `TREND_INTERVAL` (Hour4) and `DI_INTERVAL` (Day1),
and the grade's reason string interpolates the interval instead of hardcoding
"daily", so it cannot go on claiming daily if that ever moves.

On EARLY signals the 4h SuperTrend does not replicate: +1.9 SE overall with
one split at +0.1 SE. A confirmed-setup effect, recorded as such.

## 15m alerts with the 4h trend filter on

Asked directly. Reported with VOLUME as well as rate, because a filter that
lifts R per signal while halving the signals can still leave less on the
table, and R per signal alone hides that. 41.6 days, 23 symbols, net of fees.

| setup | n | per day | R/signal | total R |
|---|---|---|---|---|
| Min15 early — everything | 1314 | 31.6 | +0.073 | +95.8 |
| Min15 early — with 4h trend | 665 | 16.0 | +0.121 | +80.2 |
| Min15 confirmed — everything | 512 | 12.3 | +0.075 | +38.4 |
| Min15 confirmed — with 4h trend | 265 | 6.4 | +0.123 | +32.6 |
| Min30 early — everything | 1347 | 32.4 | +0.114 | **+153.4** |
| Min30 early — with 4h trend | 634 | 15.2 | +0.161 | +101.8 |
| Min30 confirmed — everything | 544 | 13.1 | +0.110 | +59.7 |
| **Min30 confirmed — with 4h trend** | 273 | 6.6 | **+0.237** | **+64.7** |

**30m beats 15m in every cell, per signal and in total.** On confirmed setups
with the filter it is nearly double: +0.237 against +0.123, +64.7 total R
against +32.6. Nothing about the 4h filter rescues the faster timeframe.

**The filter is worth turning on for exactly one of the four cells.** Min30
confirmed is the only one where filtering RAISES total R — +64.7 from +59.7 —
while halving the trades, which is a real improvement in return per unit of
risk taken. In the other three it costs total R: Min30 early drops 153.4 to
101.8, and both Min15 cells fall too. The per-signal number rises everywhere,
which is exactly the trap volume is reported to avoid.

`RIPTIDE_TREND_FILTER` is one switch across both signal types, so turning it
on today buys +5 R on confirmed and gives up 51.6 R on early — 166.5 against
213.1 overall. It stays OFF. Making it per-signal-type is the change that
would let the useful half be taken.

Out of sample on the 15m with-trend cells: early +0.101 / +0.144 / +0.164 /
+0.078, confirmed +0.063 / +0.189 / +0.141 / +0.106. Positive in all eight,
but two splits sit under 1 SE and the level is roughly half the Min30
equivalent throughout.

## The risk cap, swept properly

Raised from a BTC 30m example: a raid candle with a 75% lower wick (range
525, low 78,959.9 against a body at 79,390) puts the early stop a very long
way from the entry.

Swept by running the ENGINE at each cap, not by filtering signals afterwards.
That distinction matters: a rejected gap does not end the search, so a tighter
cap produces DIFFERENT signals — a later, tighter gap off the same raid — not
merely fewer. Filtering post-hoc answers a question nobody asked.

| max risk | early n | R/signal | total R | confirmed n | R/signal | total R |
|---|---|---|---|---|---|---|
| 1 ATR | 180 | +0.235 | +42.4 | 14 | +0.398 | +5.6 |
| 1.5 ATR | 586 | +0.179 | +105.0 | 71 | +0.323 | +22.9 |
| 2 ATR | 961 | +0.141 | +135.5 | 143 | +0.239 | +34.2 |
| **2.5 ATR** | 1186 | +0.121 | +143.2 | **242** | **+0.260** | **+63.0** |
| 3 ATR | 1281 | +0.118 | +151.3 | 348 | +0.181 | +63.1 |
| 4 ATR (current) | 1347 | +0.114 | **+153.4** | 544 | +0.110 | +59.7 |
| none | 1373 | +0.111 | +152.5 | 787 | +0.075 | +59.4 |

**The two signal types want different caps, and they used to share one.**
Split as of this measurement: `max_risk_atr` 2.5 for confirmed setups,
`early_max_risk_atr` 4.0 for early. Confirmed alerts fall from 13.4 to 6.0 a
day; early is unchanged at 33.4.

For EARLY, 4 ATR is already about right. R per signal rises all the way down
to +0.235 at 1 ATR, and total R falls the whole way — the tighter caps are
deleting winners. Against 4.0 the difference is +0.007 at 0.035 SE, and total
R drops 153.4 to 143.2.

For CONFIRMED, 2.5 ATR beats it:

| split | n 2.5 | R 2.5 | n 4.0 | R 4.0 | diff | total 2.5 | total 4.0 |
|---|---|---|---|---|---|---|---|
| all | 242 | +0.260 | 544 | +0.110 | +0.151 (2.5 SE) | +63.0 | +59.7 |
| symbols A | 119 | +0.329 | 273 | +0.145 | +0.184 | +39.1 | +39.6 |
| symbols B | 123 | +0.194 | 271 | +0.074 | +0.120 | +23.9 | +20.2 |
| window 1st | 114 | +0.278 | 266 | +0.118 | +0.161 | +31.7 | +31.3 |
| window 2nd | 128 | +0.244 | 278 | +0.102 | +0.142 | +31.3 | +28.4 |

Same sign on all four splits. **Read what it is, though: the same total return
from 44% of the trades**, not more money. Total R is 63.0 against 59.7, which
is inside noise. What actually improves is efficiency — 2.4x the R per trade,
less than half the exposure, less time in market, and the widest-stop setups
gone. That is worth taking, and it is not an edge increase.

### Does the cap cost reward? It buys reward.

The obvious objection is that cutting the wide-stop setups cuts the big moves
with them. Measured on ONE uncapped run, so both groups come from the same
gaps and are directly comparable:

| confirmed setups | n | fill | median risk | avg MFE | reach 1R | 2R | 3R |
|---|---|---|---|---|---|---|---|
| kept (<= 2.5 ATR) | 234 | 74% | 1.25% | **2.47 R** | 61% | 40% | **26%** |
| dropped (> 2.5 ATR) | 549 | 79% | 3.02% | 1.06 R | 31% | 12% | **5%** |

The dropped group reaches 3R five percent of the time. The kept group reaches
it twenty-six. Reward per unit of risk more than doubles, which is arithmetic
as much as edge: a tight stop makes each R a small price move, so the same
move is worth more R. The only thing that gets worse is the fill rate, 74%
against 79%.

### The part the cap does not fix

A far stop is not a bigger loss. A -1R loss is -1R whether the stop sits 0.2%
or 5% away, provided the position is sized by RISK rather than by notional: a
wide stop means a smaller position, not a larger loss. In the BTC case a
78,959.9 stop against a ~79,500 entry is 0.68% risk, so risking 1% of an
account is 1.5x notional — less leverage than a tight-stop setup would need,
not more. Sizing by a fixed contract count is what turns stop distance into
loss size, and no cap in the engine can repair that.

Fees also run the other way from intuition: cost in R is 0.08 / risk_pct, so a
wide stop is CHEAPER per unit of risk, not dearer.

## The Pine stats table ignored the trend filter

Reported as "these are not updating the results": ticking *Only take setups
with the higher-timeframe trend* changed nothing in the panel's numbers.

It was true. Three paths existed and only two were gated:

| path | gated by |
|---|---|
| alerts | `trendOk` |
| drawing | `showLongs`/`showShorts` and `trendOk`, inside `drawSetup` |
| **stats table** | **nothing** |

`openTrade` sat beside `drawSetup` in the same `if` and took no filter at all,
so `stx.setups` counted every setup whatever the panel said. Flipping the
filter moved the alerts and the drawings and left the table identical.

That is the worst place for it to have been missing. The table is what the
filter is *judged by* — the whole reason to switch it on is to see whether
those setups score better — and it was quietly answering a different question.
Anyone reading it would have concluded the filter does nothing, which is the
opposite of what the bot measured (+3.7 SE on 4h confirmed setups).

Fixed by gating `openTrade` on `trendOk`. Deliberately NOT on
`showLongs`/`showShorts`: those are viewing preferences and must not move a
measurement. That also matches what the alert path gates on, so the table now
counts exactly the population the alerts would have sent.

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

## Entry fill rate — the misses are the winners, and chasing them still loses

`research/studies/fills.py`. 30m, 23 symbols, 2000 bars, 2R target, maker
0.02% / taker 0.06%, engine defaults otherwise. Every variant re-scores the
SAME signal set through `research.harness.simulate`, so the differences are
PAIRED and the SEs below are paired SEs, not the difference of two
independent means.

**The ceiling is real.** Of the 74 confirmed setups whose limit never filled,
**59 (80%) went on to reach 2R without us** — measured from the entry price
they never traded at. Early: 206 of 281 (73%). Market-entering just those
would have returned +0.361 R each, better than the book that did fill.

That number is a look-ahead and cannot be traded. Which setups go unfilled is
knowable only afterwards. The decision actually available is to enter more
aggressively on *every* signal, and each version of that was measured:

    CONFIRMED  n=246                fill      R/sig    paired vs shipped
      limit at gap edge  <- shipped 69.9%    +0.250
      market at signal close       100.0%    +0.186    -0.064  -1.1 SE   risk x1.55
      limit +0.10 ATR toward price  72.0%    +0.223    -0.027  -1.0 SE   risk x1.06
      limit +0.30 ATR               81.3%    +0.198    -0.052  -1.1 SE   risk x1.18
      limit +0.50 ATR               87.4%    +0.183    -0.066  -1.2 SE   risk x1.30
      limit +1.00 ATR               95.1%    +0.020    -0.230  -3.6 SE   risk x1.61

    EARLY      n=1388
      limit at gap edge  <- shipped 79.8%    +0.020
      market at signal close       100.0%    -0.028    -0.048  -1.9 SE   risk x1.34
      limit +0.50 ATR               94.3%    -0.077    -0.097  -3.8 SE   risk x1.34
      limit +1.00 ATR               98.7%    -0.232    -0.252  -8.9 SE   risk x1.68

Monotone in both signal types, over the full range, and the mechanism is not
mysterious: the stop stays pinned to the raid extreme, so buying the fill rate
costs risk on **every** trade, including the 70% that would have filled
anyway. The 80% ceiling is paid for out of the other 70% of the book, and the
bill is larger than the prize.

**The opposite lever also loses**, which is what makes this a peak rather than
a slope. Entering DEEPER into the gap concedes fill rate to buy a better
price, and it is worse in the other direction:

    CONFIRMED             fill      R/sig    paired
      0.00 proximal  <-   69.9%    +0.250              the shipped entry_mode
      0.50 mid            60.2%    +0.125    -0.125  -3.3 SE
      1.00 distal         52.4%    +0.098    -0.152  -2.8 SE

So `entry_mode = "proximal"` is not a default nobody checked; it is the top of
a curve that falls away on both sides.

**Split entries lose.** Half at the proximal edge, half at the midpoint:
-0.062 (-3.3 SE). Half and half at the distal edge: -0.076 (-2.8 SE). The
second leg fills mostly on the trades that were going to lose anyway.

**Fill window: 10 bars is right, and cancelling early is expensive.** The
first sweep looked like 15 bars beat 10 by +0.086 at 2.0 SE, but that
comparison was against the 5-bar baseline, not against 10. Measured directly,
10 -> 15 is +0.017 at +0.6 SE and the four splits disagree in sign
(+0.013 / +0.021 / +0.050 / -0.009). Nothing there. What IS there is the
other end: **5 bars costs -0.069 (-2.0 SE) against 10.** Late fills in
isolation are too few to read (n=19 in bars 11-15).

    => nothing adopted. Four levers, eight variants, all at or below the
       shipped configuration. The one behavioural rule this does support:
       leave the limit working the full 10 bars (5 hours on 30m) and do not
       cancel it early because it "looks stale".

The general lesson, which is worth more than the sweep: **the unfilled setups
are profitable because they are unfilled.** The limit order is not failing to
catch them, it is doing the selecting — the same discipline that refuses the
runaway winner is what refuses the entries that were never going to offer a
good price. Removing the refusal removes both.

## How long to leave the order working — 2 to 20 bars, paired

`research/studies/wait.py`. Every value from 2 to 20 bars, each paired against
the shipped 10 on the same signal set.

    CONFIRMED n=246       fill     win    R/signal   total   vs 10
       2 bars            43.9%   50.0%     +0.159    +39.2   -0.090  -1.8 SE
       5 bars            58.5%   48.6%     +0.181    +44.4   -0.069  -2.0 SE
       8 bars            64.2%   50.0%     +0.230    +56.6   -0.020  -0.8 SE
      10 bars  <-        69.9%   50.0%     +0.250    +61.4
      12 bars            74.0%   50.5%     +0.280    +68.8   +0.030  +1.4 SE
      15 bars            77.6%   49.2%     +0.267    +65.6   +0.017  +0.6 SE
      20 bars            80.9%   48.2%     +0.256    +63.1   +0.007  +0.2 SE

    EARLY n=1388 is flat everywhere: every value from 2 to 20 sits between
    +0.012 and +0.030 R/signal, and the largest paired difference against 10
    is +0.010 (1.1 SE) at 18 bars.

**Win rate does not move.** Fill rate nearly doubles from 2 bars to 20 —
43.9% to 80.9% — and the win rate stays pinned at 48-50% the whole way. The
setups that take twelve bars to retrace win as often as the ones that fill in
two. That is the single most useful number here: waiting longer is not
"accepting worse trades", it is the same trades arriving later.

**The curve has a floor, not a peak.** Below 8 bars it costs real money (2
bars is -0.090, 5 bars -0.069, both about 2 SE) because the setup is being
abandoned before it has retraced. From 9 to 20 it is a plateau: 12 is the
nominal argmax at +0.030, which is 1.4 SE and nowhere near the 3 SE bar.

**Per-symbol tuning is noise, and this is how we know.** Each symbol's own
best wait, confirmed signals: 2, 2, 3, 3, 7, 7, 9, 10, 10, 11, 12, 13, 14, 17
— spread across almost the whole tested range, stdev 4.6, median 6. Early is
the same, min 2 max 18 stdev 5.4. If 10 were wrong for a symbol there would be
a cluster somewhere else; instead every symbol picks a different value, which
is what fitting ~10 observations looks like.

    => 10 stays. 12 is not distinguishable from it and per-symbol values are
       noise. The rule that IS supported: never cancel before 8 bars.

## Why chasing the entry fails — it is not the risk, it is the stop

`research/studies/decouple.py`. The buffer result in the previous section held
the stop at the raid extreme, so it proved something narrower than it looked:
chasing loses WHEN THE STOP STAYS PUT. That is a coupling — entry and stop are
welded, so every tick of chase is a tick of extra risk on all 246 trades. Break
the weld and the arithmetic should change. Four stop rules x four chase
distances:

    CONFIRMED n=246      chase   fill     win   risk%    R/signal   total
      raid extreme <-     0.00  69.9%   50.0%   1.83      +0.250    +61.4
      raid extreme        1.00  95.1%   40.2%   2.86      +0.020     +4.9
      constant risk       0.25  80.9%   42.2%   1.82      +0.126    +30.9
      constant risk       0.50  87.4%   42.8%   1.82      +0.165    +40.5
      constant risk       1.00  95.1%   35.9%   1.82      -0.047    -11.5
      gap far edge        0.00  69.9%   40.1%   0.54      -0.057    -14.1
      5-bar swing         0.00  69.9%   45.9%   1.68      +0.190    +46.7

`constant risk` holds |entry - stop| at exactly what it was — risk% stays 1.82
across the whole chase, so risk inflation is eliminated by construction. **It
still loses**, and the win rate column says why: 50.0% at the gap edge, 42.2%
after a quarter-ATR chase, 35.9% after a full one, at identical risk. Fourteen
points of win rate bought with nothing but a worse entry price.

So the coupling was never the problem. **The raid extreme is not merely where
a stop fits; it is the price beyond which the setup is wrong.** Any stop nearer
than that sits inside normal retracement noise and gets taken by the pullback
the setup was always going to have. `gap far edge` is the clean proof: it
places a very tight stop (0.54% vs 1.83%), and the win rate falls to 40% on
confirmed and 28% on early, for -0.057 and -0.398 R per signal. Cheap risk,
bought at a price that more than consumes it. Even the 5-bar swing low — a
real structural level, only slightly nearer than the raid — is worse than the
raid extreme with no chase at all (+0.190 vs +0.250).

    => sixteen cells, nothing beats the shipped entry-at-gap-edge with the
       stop beyond the raid. The fill-rate ceiling from the previous section
       is not reachable by any repositioning of entry or stop. It is not a
       parameter problem.

## The "sniper entry" SMC blueprint, claim by claim

`research/studies/sniper.py`. The blueprint circulating as HTF bias -> sweep at
an HTF zone -> LTF confirmation -> refined LTF entry -> tight stop -> 1:3 RR.
Three of its five steps were already settled here and were not re-run: HTF bias
(measured, daily DI, +0.204 with / -0.062 against), LTF confirmation (measured
— it IS the confirmed signal, +0.250 against +0.020 for the no-shift early),
and the tight stop at the invalidation wick (refuted in the section above,
0.54% risk and 40.1% win against 1.83% and 50.0%). The 1:3 target is also
already known: 3R is +0.252 against 2R's +0.215, about 1.5 SE, not separable.

Three claims were genuinely untested.

### A. The raid must land in a 4h order block or fair value gap — no effect

    rule                              flagged        confirmed      early
    any 4h zone, ever              1479 (90%)      unbucketable   -0.231 -2.1 SE
    formed within last 30 4h bars   614 (38%)      -0.027 -0.2 SE  -0.005 -0.1 SE
    last 30 bars AND unmitigated     14 (1%)       too few         too few

The first row is the trap, and worth writing down because it is how this kind
of test usually goes wrong. 333 days of 4h bars accumulate thousands of gaps
and blocks; between them they cover most of the price range, so "the raid was
in an HTF zone" is true 90% of the time and tests nothing. (Its one nominal
result points the WRONG way — the 136 raids outside any zone scored +0.231
against -0.000 — and fails the splits anyway.)

Constrained to zones formed in the last five days, the flag splits the book
38/62 and is dead flat on both signal types.

Constrained further to zones that are also unmitigated — the actual ICT
premise, price arriving at a fresh higher-timeframe zone — it fires **14 times
in 1637 signals, 1%.** That is the useful finding: the blueprint's setup is not
a filter that improves these signals, it is a much rarer event that our pools
almost never coincide with. It cannot be measured here and it cannot be traded
at any useful frequency.

### B. Refining the entry onto a faster chart — loses 0.525 R per setup

`riptide/mtf.py` has implemented this since early on, gated behind
`RIPTIDE_ENTRY_INTERVAL`, and it is OFF. Its docstring justified it with "85%
of setups filled, 51% of fills reached 1R" against 45%/48% for Min30 — numbers
from the buggy scorer. Re-run through the harness on matched wall-clock
windows (10 bars and 60 bars on 30m are 5 and 30 hours, so 20 and 120 bars on
Min15), 80 comparable confirmed setups:

    Min30 gap + Min30 stop  <-  fill 57.5%   win 56.5%   +0.304 ± 0.127
    Min15 gap + Min15 stop      fill 82.5%   win 27.3%   -0.221 ± 0.137
                                        paired difference -0.525, 3.2 SE

**The fill-rate claim reproduces almost exactly** — 82.5% against the old
85%. What the old scorer hid is the price of it: the win rate more than halves.
This is the decouple result again from a fifth direction. A Min15 stop is
structural on the Min15 chart and pure noise on the Min30 one.

Min5 was inconclusive (-0.067, 0.2 SE) but only 30 setups fall within reach of
2000 Min5 bars, so that is absence of evidence, not evidence of absence.

The mtf.py docstring has been corrected in place; the old numbers were live
documentation arguing for a feature that costs half an R per setup.

### C. Targeting the opposing liquidity pool — the blueprint contradicts itself

    CONFIRMED n=245        R/signal          EARLY n=1390
      fixed 2R  <-          +0.246             +0.023
      at the pool           -0.021             -0.032
      floored at 1.5R       +0.188             -0.003
      1.5R-3R band          +0.183             -0.001

The distribution explains it. **The nearest opposing pool sits at a median of
0.16R for confirmed setups, and 95% of them are below 1R.** Early is barely
better: median 0.45R, 74% below 1R.

That is not a flaw in the measurement, it is a consequence of where the entry
is. We enter at the proximal edge of a gap after a retracement, which is by
construction close to the swing that price just came from — so the nearest
opposing liquidity is right there. "Target the opposing pool" and "take a
minimum 1:3" are not two rules that combine; on this system they are
contradictory, and the ladder that already ships resolves it in the right
direction.

    => nothing adopted from the blueprint. Its confirmation step was already
       our largest measured effect, its stop rule is the one thing we have
       refuted from five separate directions, its HTF-zone step describes an
       event that occurs in 1% of our signals, and its target rule would exit
       at 0.16R.

## The multi-timeframe model, swept properly — and one filter that survived

`research/studies/mtf_grid.py`, held out in `research/studies/mtf_holdout.py`.

This is Model 1 built as an actual multi-timeframe model, which is NOT what
sniper.py rejected. There, riptide/mtf.py took the first gap on a faster chart
after the 30m shift and put the stop on that gap. Here the lower timeframe
forms its OWN complete setup — its own sweep, its own change of character, its
own gap — and the stop sits beyond the LOWER timeframe's raid extreme. Every
stop refuted so far shared one property: none sat beyond a liquidity raid.
This one does, so it earned its own measurement.

Run as an ablation, so each of the five strict steps is priced separately:
LTF alone, + HTF point of interest, + HTF narrative, + both. 7 HTF/LTF pairs,
4 arms, 2 signal types = 56 cells on 14 symbols.

### The faster timeframes are worse, monotonically

    LTF alone, confirmed        n     fill     win    risk    R/signal
      Min30                    145   69.0%   54.0%   1.43%    +0.317
      Min15                    140   82.1%   32.2%   1.36%    -0.095
      Min5                     603   84.9%   32.6%   0.66%    -0.182

The blueprint's central promise — drop to 5m or 1m, use a tiny stop, ride a 4h
trend for a huge RR — is the opposite of what happens. Fill rate does rise
exactly as promised (69% to 85%), and the stop does get much tighter (1.43% to
0.66%). Both of those are real. What comes with them is the win rate falling
from 54% to 33%, and at 0.66% risk the round-trip fee is 0.06-0.12 R before
anything else happens. Min1 was excluded outright: 2000 bars is 33 hours.

This is now the sixth independent route to the same conclusion. A stop is only
worth what the level under it is worth, and speed does not create levels.

### Only the DAILY point of interest does anything

4h and 1h POIs did nothing or hurt in every cell. The daily POI — the LTF raid
landing inside a daily order block or fair value gap formed in the last 30 days
— improved every cell it could be measured in:

    discovery, 14 symbols            without POI    with POI
      Day1 -> Min30  confirmed          +0.317       +0.520
      Day1 -> Min30  early              +0.061       +0.125
      Day1 -> Min15  confirmed          -0.095       +0.417
      Day1 -> Min15  early              -0.039       +0.159

Four cells, one direction. That is a better shape than the gapless-piercing
candidate ever had, which is why it was worth holding out rather than adopting.

### Held out, pre-registered, on nine symbols the grid never saw

The prediction was written into `mtf_holdout.py` before the run: same sign in
all four arms, sign flip in any one is a failure.

    Day1 -> Min30  confirmed   +0.036 (n=71)  -> +0.429 (n=30)   +1.4 SE
    Day1 -> Min30  early       -0.083 (n=376) -> +0.066 (n=170)  +1.3 SE
    Day1 -> Min15  confirmed   too few (24 inside the POI)
    Day1 -> Min15  early       -0.043 (n=387) -> +0.201 (n=122)  +1.8 SE

    => SURVIVES. All three measurable arms kept the predicted sign.

Read this honestly. No single arm clears 2 SE, let alone the 3 SE bar a
single-comparison filter has to clear here. What carries it is that four
discovery cells and three held-out cells all point one way, on disjoint
symbols, which is not what the September candlestick candidate did — that one
reversed sign the moment it left the window it was found in. One wobble worth
naming: the Day1->Min30 early arm is -0.054 in the first half of the held-out
window and positive overall.

### What it would actually mean

The Day1->Min30 arm needs no new timeframe and no new engine. It is one filter
on the signals that already ship: **require the raid to land inside a daily
order block or fair value gap.** It drops about 65% of signals and roughly
doubles R on what is left, so TOTAL R falls (145 x 0.317 = +45.9 against
51 x 0.520 = +26.5) while R PER SIGNAL rises sharply.

That trade is only worth making because capacity, not signal quality, is the
binding constraint at 300 USDT — the portfolio study had to skip 450-950
signals for want of a slot. Fewer, better signals is exactly the direction that
constraint asks for. On a large account the same filter would be a downgrade.

## Models 2 and 3 — the two SMC models without a liquidity sweep

`research/studies/models23.py`. Min30 structure, daily context, all 23
symbols, same harness and same wall-clock windows as everything else, so these
sit directly beside Model 1.

Both models were chosen because they share one property Riptide's signals never
have: **neither requires a liquidity sweep.** If the raid is what carries the
edge — which five separate stop studies imply, since the raid extreme is the
only stop level that has survived anything — both should be materially worse.
That was the prediction, and it is what happened.

                                        n    fill    win   risk    R/signal
    M1 sweep -> CHOCH  <- shipped     247   69.6%  50.0%  1.83%    +0.248
      + daily POI                      81   64.2%  61.5%  1.78%    +0.486
      + daily trend                   109   70.6%  57.1%  1.97%    +0.449
      + both                           43   67.4%  75.9%  1.90%    +0.822

    M2 order block continuation       946   63.8%  34.4%  1.01%    -0.056
      + daily POI                     240   61.3%  40.1%  0.78%    +0.041
      + both                           84   56.0%  40.4%  0.81%    +0.053

    M3 FVG sniper, gap edge          3183   79.3%  35.3%  1.24%    -0.036
      + daily POI                     872   74.2%  38.5%  1.06%    +0.028
      + both                          363   74.4%  42.2%  1.30%    +0.129
    M3 FVG, displacement > 1.5 ATR   1109   77.2%  36.3%  1.67%    -0.003
      + both                          115   72.2%  44.6%  1.82%    +0.190

**Model 1 unfiltered beats every cell of Models 2 and 3, including their best
filtered arms.** Both alternatives are negative raw and only reach break-even
once the daily filters carry them. Win rate is the tell: 50% for Model 1
against 34-36% for both others, at the same 2R target.

Three specific things fall out of this:

**The sweep is the edge, not the structure around it.** Model 2 has a trend, a
break of structure, an order block and a pullback — every SMC ingredient except
the raid — and returns -0.056. Model 3 has a displacement and a gap and returns
-0.036. Add a raid and the same 30m chart returns +0.248.

**"The order block should have an FVG next to it" is worth nothing.** The
condition is standard doctrine and it is tested here as its own arm: -0.029
with the FVG against -0.056 without, and with both daily filters on it is
WORSE than plain Model 2 (-0.029 against +0.053). It also discards 39% of the
signals to achieve that.

**Entering at the gap edge beats the 50% mark again**, on a completely
different model: -0.036 against -0.065 raw, +0.129 against +0.021 filtered.
That is now the third independent confirmation of `entry_mode = "proximal"`.

### The daily POI keeps working, on models it was not found on

Worth separating from the rest, because it is the strongest evidence yet that
the POI result is real rather than a Model-1 quirk. It was discovered on Model
1, held out on nine unseen symbols, and here it improves **every arm of every
model**, including two models built on a different premise entirely:

    M1  +0.248 -> +0.486     M2  -0.056 -> +0.041     M3  -0.036 -> +0.028

An effect that only existed in the window it was found in would not do that.

### Model 1 replicates on the full symbol set

The grid ran on 14 symbols; this run is all 23, and the ablation lands in the
same place: +0.248 raw, +0.486 with the POI, +0.449 with the trend, +0.822
with both, against +0.317 / +0.520 / +0.522 / +0.889 on the 14. The 43-signal
"both" arm wins 75.9% of its fills.

## The cell table, and hybrid alert policies on 300 USDT

`research/studies/hybrid.py`. 3215 signals, 23 symbols, 41 days, both
timeframes, daily context. Every signal falls into (timeframe, kind, daily
POI, daily trend) — four axes, all known at signal time, all separately
measured. This is the table a grade should be built from.

    tf     kind       POI  trend     n   fill   win     R/signal
    Min30  confirmed  no   no      100   72%   44%   +0.082 ± 0.119
    Min30  confirmed  no   yes      66   73%   46%   +0.206 ± 0.157
    Min30  confirmed  yes  no       38   61%   43%   +0.105 ± 0.189
    Min30  confirmed  yes  yes      43   67%   76%   +0.822 ± 0.187
    Min30  early      no   no      624   80%   36%   -0.050 ± 0.049
    Min30  early      no   yes     331   80%   40%   +0.048 ± 0.070
    Min30  early      yes  no      228   78%   38%   +0.018 ± 0.084
    Min30  early      yes  yes     214   78%   46%   +0.188 ± 0.087
    Min15  confirmed  yes  no       28   93%   58%   +0.605 ± 0.287
    Min15  confirmed  yes  yes      31   61%   58%   +0.417 ± 0.222
    Min15  early      yes  yes     197   81%   49%   +0.281 ± 0.096
    Min15  early      no   no      541   86%   31%   -0.131 ± 0.056
    (Min15 confirmed without a POI is -0.177 and -0.241; Min15 is only
     tradeable inside a POI, which is the opposite of "add a 15m feed".)

The two filters are not additive, they are multiplicative. Confirmed with
neither is +0.082; with the trend alone +0.206; with the POI alone +0.105;
with both +0.822 and a 76% win rate. **The single largest cell in the project
is the one where both agree**, and 624 of 1644 Min30 signals — 38% of
everything the bot currently sends — sit in the one cell that is negative.

### Policies on a 300 USDT account

Judged on return per unit of drawdown. 10x, 1% risk, max 8 open, 2 reserved
for confirmed, compounding.

    policy                                    alerts taken  ret  maxDD  ret/DD
    A  everything, 30m only (shipped)           1644   177  +94%   14%    6.94
    B  30m confirmed only                        247   157  +78%    8%    9.78
    C  30m, POI required on both                 523   214 +101%    6%   16.22
    D  30m confirmed all + 30m early in POI      689   221  +88%   12%    7.20
    E  D + 15m early in POI                     1045   235 +127%   12%   10.38
    G  both tf, POI required on everything       938   237 +141%    7%   21.53
    H  POI and trend on everything               485   144  +24%   10%    2.24

**Policy H is the important one.** Its cells are the best in the table — every
signal it takes comes from a POI+trend cell scoring +0.188 to +0.822 — and it
finishes second to last. Requiring the daily trend concentrates every position
on the same side of the same market at the same time, so the individually best
signals arrive as one correlated bundle. Highest R per signal is not the same
objective as best account outcome, and this is the cleanest demonstration of it
the project has produced.

### A flaw in the first version of this simulation, and what it was worth

The first run let a 30m early and a 15m early on the same symbol hold two
positions at once. They are the same idea twice. With one position per symbol
enforced:

    policy   with the rule        without it
    E          10.38                25.29
    G          21.53                13.79
    A           6.94                 3.24

E's apparent lead was mostly a free doubling of size on exactly the moves both
charts agreed about — which is where a multi-timeframe policy must not be given
a discount, since agreement is the thing being tested. The ranking inverts
once it is removed. Recorded rather than quietly fixed, because the first
number is the one that would have been believed.

    => the POI requirement is the whole win: 6.94 -> 16.22 on 30m alone, and
       21.53 using both timeframes. The second timeframe adds real value ONLY
       inside a POI and ONLY without doubling up per symbol. Requiring the
       daily trend as well is actively harmful at the portfolio level despite
       being the best filter per signal.

Caveat: nine policies were compared on one dataset and C, E and G are within a
plausible noise band of each other. What is NOT within noise is that every
POI-requiring policy beats the shipped one by 2-3x on return per drawdown, and
the POI component is the one thing here that has passed a pre-registered
held-out test.

## What policy G actually gives up — and a correction

`research/studies/missed.py`, run on the LIVE universe (60 symbols, both
timeframes, 42 days) rather than the 23 the cell table was built on.

    suppressed by G          n   per day    R/signal      total R
      Min30 confirmed, trend      149   3.6    +0.030        +4.5
      Min30 confirmed, against    270   6.5    -0.175       -47.2
      Min30 early, trend          811  19.5    +0.010        +8.4
      Min30 early, against       1569  37.7    -0.099      -155.5
      Min15 confirmed, trend      199   4.8    -0.011        -2.2
      Min15 confirmed, against    186   4.5    -0.165       -30.7
      Min15 early, trend         1038  24.9    -0.029       -29.8
      Min15 early, against       1177  28.3    -0.144      -169.9

      suppressed  5399 signals (129.7/day)   -422.5 R
      kept        2630 signals ( 63.2/day)   +273.0 R

**CORRECTION.** Earlier sections of this file, and the advice that went with
them, say that requiring a POI lowers TOTAL R and is therefore only worth it
while a position slot is the scarce resource. On the live 60-symbol universe
that is wrong. **The suppressed book is worth -422.5 R.** Not one suppressed
cell measures above +0.030. G is not trading volume for quality; it is cutting
a losing book, and total R rises.

The earlier claim came from the 23-symbol measurement, where Min30 confirmed
outside a POI but with the trend scored +0.206 on 66 signals. On 60 symbols
the same cell is +0.030 on 149. The extra 37 symbols are materially worse than
the hand-picked 23 — which is the second finding here, and it cuts both ways:

**Widening the universe dilutes signal quality, and that is exactly why the
POI filter matters more at 60 symbols than it did at 23.** The kept book
averages +0.104 R per signal across 60 symbols. Expanding the universe without
the filter would have made the bot worse, not better; the two changes are only
sound together.

### Sweep heads-ups, which no measurement covers

Sweeps are not trades — no entry, no stop, nothing to score — so no cell in the
table applies to them, and gating them on the POI was a decision made by the
code rather than by a finding. It now has its own switch. Measured rates:

    every sweep, both timeframes      393/day
    every sweep, 30m only             216/day
    in a daily POI, both timeframes   123/day
    in a daily POI, 30m only           65/day   <- the default

The default sends FEWER sweeps than the old 23-symbol single-timeframe setup
(~83/day) despite scanning nearly three times the market. The POI default is
also coherent rather than merely quiet: a sweep's POI is evaluated at the same
raid a setup's would be, so a sweep outside a zone can only lead to signals
POI_REQUIRED then suppresses — sending it would advertise a setup the bot has
already decided not to alert on.

## Sweeps in a POI: same chance, different payoff

`research/studies/sweeps.py`. 16347 raids, live 60-symbol universe, both
timeframes, 42 days. A sweep has no entry so it cannot be scored as a trade,
but "does a POI raid have more chances" is still a measurable claim — and it
turns out to mean two things that answer differently.

    sweeps       -> setup   -> early    R of the setups that followed
      outside a POI      11249    7.5%    41.4%    -0.055 ± 0.041
      inside a POI        5098    7.0%    41.2%    +0.141 ± 0.067

**The conversion rate is the same.** 7.0% against 7.5% — if anything a POI raid
is marginally LESS likely to produce a confirmed setup. Early conversion is
identical too, 41.2% against 41.4%. Being in a daily zone does not make a raid
more likely to turn into anything.

**What follows is worth +0.196 R more.** The setups born from POI raids score
+0.141; those born outside score -0.055. Same split on both timeframes:
Min30 +0.143 against -0.071, Min15 +0.140 against -0.037.

So the POI does not change the ODDS of a setup appearing. It changes whether
the setup, once it appears, is worth taking.

### It is a genuinely separate axis from the shift distance

The engine already predicts conversion from how far price must travel back for
the shift to confirm, and that gradient is steep. If POI raids were simply
raids sitting closer to their shift level, the label would add nothing. Crossed:

    band            no POI                    in POI
    under 1%   24.8% conv   -0.137       22.5% conv   +0.191
    1-2%       13.5% conv   -0.051       14.8% conv   +0.100
    2-4%        5.6% conv   +0.013        5.2% conv   +0.139

Conversion tracks the distance and ignores the POI. R tracks the POI and
ignores the distance. Median shift distance is 3.10% inside a POI and 2.96%
outside — the same. Two independent axes, which is why the sweep alert
usefully carries both:

    "3.9% away"        how likely a setup is to appear at all
    "in a daily POI"   whether it will be worth taking when it does

### The conversion table was stale, and is now updated

`SHIFT_ODDS` in engine.py was measured on 23 hand-picked symbols. Re-measured
on the live universe, Min30, 8984 raids:

    distance     old        new
    under 1%     37%        24%
    1-2%         25%        13%
    2-4%         17%         6%
    4-8%          7%         2%
    over 8%       3%         1%

Every band converts less often than the old table claimed. The shape is
identical and the gradient is steeper; only the level moved, because the wider
universe is thinner — the same finding the POI work produced from the other
direction. The table is not shown on any alert (only the distance is), so
nothing user-facing was ever wrong; the comment beside it was.

## Inside grade A — anatomy of the alerts that pay and the ones that do not

`research/studies/grade_a.py`, prompted by a live grade-A alert on XRP_USDT
15m that lost. One loss carries no information — the live-universe table below
puts A at a **48% win rate**, so a losing A is the modal outcome — but it is a
fair prompt for asking whether anything already measured sorts A's.

**The live grade table, 60 symbols, both scanned timeframes, POI required,
42 days.** This supersedes the 23-symbol Min30-only cell table earlier in this
file, which is what `TRADING.md` had been quoting.

| grade | n | /day | fill | win | RR | R/signal |
|---|---|---|---|---|---|---|
| **A** confirmed + POI + trend | 184 | 4.4 | 72% | **48%** | 1.81 | **+0.271 ± 0.094** |
| **B** early + POI + trend | 1017 | 24.4 | 82% | 45% | 1.71 | +0.180 ± 0.041 |
| C everything else *(muted)* | 1561 | 37.5 | 79% | 38% | 1.70 | +0.016 ± 0.032 |
| D | 0 | — | — | — | — | unreachable with POI_REQUIRED |

| cell | n | fill | win | R/signal |
|---|---|---|---|---|
| Min30 confirmed A | 100 | 67% | 52% | +0.317 ± 0.121 |
| Min15 confirmed A | 84 | 77% | 45% | +0.216 ± 0.147 |
| Min15 confirmed C | 114 | 79% | 42% | +0.147 ± 0.125 |
| Min30 confirmed C | 121 | 60% | 36% | −0.013 ± 0.098 |

The old table's +0.822 at a 76% win rate came from 43 Min30 signals on 23
hand-picked symbols. On the 60 the bot now scans, the same cell is +0.271 at
48%. The ordering survived the universe change; **the level did not**, exactly
as this file has said about every level it reports. A 15m A is a coin flip
with a 1.8:1 payoff, and it should be read that way.

### Three axes inside A, and none of them earns a rule

| gap at alert | n | fill | win | R/signal |
|---|---|---|---|---|
| 0 – 0.25R past entry | 54 | 96% | 50% | +0.371 ± 0.197 |
| 0.25 – 0.5R | 48 | 77% | 49% | +0.326 ± 0.191 |
| 0.5 – 1R | 54 | 59% | 47% | +0.200 ± 0.162 |
| over 1R past | 28 | 39% | 45% | +0.118 ± 0.186 |

**The gap gradient reverses inside A.** On the whole book it is this project's
most replicated effect and it runs the counter-intuitive way — stranded alerts
pay more, same sign on all ten splits. Inside A it runs the ordinary way, and
the spread is 0.9 SE, which is nothing. The honest reading is that the axis is
dead once the POI and the daily trend are already conditioned on, not that it
inverted. Recorded because it was the first hypothesis and it was wrong.

| stop width | n | fill | win | R/signal |
|---|---|---|---|---|
| under 1.00% risk | 61 | 66% | 45% | +0.167 ± 0.159 |
| 1.00% or wider | 123 | 75% | 50% | +0.322 ± 0.116 |

**Tight stops on an A are mildly worse, at 0.8 SE.** Weak on its own, but it
is the third independent reading pointing the same way: the feature regression
on the corrected scorer put stop size at +0.352 (2.4 SE) on confirmed, and
`losers.py` puts the median stop of a confirmed winner at 1.44% against 1.17%
for a loser. Mechanism is at least partly arithmetic — the round trip costs
`0.08 / risk_pct` R, so 0.107 R at a 0.75% stop against 0.055 R at 1.45%, and
a tight stop sits nearer the noise it is meant to be outside of. Not a filter:
0.8 SE inside A, and cutting sub-1% A's would drop a third of them to save
0.155 R apiece on a number that could be zero.

| BTC 30m | n | fill | win | R/signal |
|---|---|---|---|---|
| agrees | 58 | 71% | **29%** | −0.113 ± 0.152 |
| against | 126 | 72% | **57%** | +0.447 ± 0.115 |

**This one is 2.9 SE and points the WRONG WAY, and it is still noise.** The
pre-registered, held-out BTC result is +0.123 for *agreeing* — measured on
early signals, which is where all the power was. This is a post-hoc subgroup
of 184 confirmed signals that already condition on the symbol's own daily
trend and DI, which is precisely the interaction tested at line "BTC regime,
conditional on the symbol's own daily trend" and **rejected there for
contradicting itself across the 2×2**. Finding the same interaction flipping
sign again in a corner of that 2×2 is confirmation that it is unstable, not a
discovery. Nothing changes on the alert, and nothing is filtered. If it is
real, `/stats` will show it forward, out of sample, which is the only place
this could now be settled.

### The XRP trade itself

Entry 1.393, stop 1.383 (0.75%), 2R at 1.413. Filled on the alert bar,
08 Sep 04:00 UTC. Best price reached in the next nine bars: 1.3967, a maximum
favourable excursion of **+0.37R** — it never got half way to 1R. Stopped
06:15 UTC on a single 15m bar that took the low out by 0.23R and kept going.
Price did not subsequently reach the target either, so this is not the
"stopped out then it went" case.

`losers.py` on confirmed setups: 34% of losers peak under 0.5R, the median
loser is held 8 bars against 23 for a winner, and 27% of losers see the target
after the stop. This trade is the median loser almost exactly. There is no
diagnosis to make beyond that — it is what a 52%-probability outcome looks
like from the inside.

## CORRECTION — the BTC regime sign was inverted in every study that measured it

Found on 8 Sep while measuring grade B split by BTC, which was run only to
check whether the daily POI absorbed a split established elsewhere.

`riptide/trend.py:supertrend` returns **+1 for an uptrend**, as its docstring
says and as an empirical check confirms (BTC 30m, `+1` bars carry a median
trailing 20-bar move of +0.298% against −0.062% for `−1`). Six research
scripts tested the BTC regime as:

    return (st[j] < 0) == r.signal.is_long     # -1 is up

`btc_regime.py`, `context.py` (twice), `equity.py`, `portfolio.py`,
`standing.py`. All six fixed. `riptide/trend.py:btc_at` and
`riptide/telegram.py:trend_note` used `> 0` and were always correct — the
shipped alert has never told anyone the wrong direction, only the wrong thing
about what that direction is worth.

**What this invalidates.** Every "BTC agrees" figure in this file, in
`TRADING.md`, and in the `btc_at` and `trend_note` docstrings had its two
columns swapped. The discovery result (+0.174, 3.6 SE) and the pre-registered
held-out replication (+0.123, 1.8 SE) were both measuring BTC going the OTHER
way. `PREREG_btc.md` stated its direction in advance under the wrong label, so
the pre-registration is intact as a procedure and wrong as a claim.

**What survives.** The effect. All three windows point the same way once the
label is corrected, so this is a naming failure rather than a measurement
failure, and it is coherent: a liquidity-sweep reversal wants something to
reverse against.

### Re-measured, correct sign — `research/studies/btc_by_grade.py`

Live universe, both timeframes, 2R, fees in. Direction pre-registered by the
held-out study (which, corrected, predicts AGAINST scores higher).

| slice | agrees n | R | against n | R | diff | SE |
|---|---|---|---|---|---|---|
| **grade B** (early+POI+trend) | 471 | −0.023 | 889 | **+0.198** | −0.221 | −3.0 |
| grade A (conf+POI+trend) | 57 | −0.100 | 128 | +0.458 | −0.557 | −2.9 |
| grade C, in a POI | 853 | −0.083 | 686 | +0.122 | −0.205 | −3.2 |
| everything sent (A+B) | 528 | −0.031 | 1017 | +0.231 | −0.262 | −3.8 |
| **all early, POI or not** | 3253 | −0.150 | 3717 | +0.081 | −0.231 | **−7.6** |
| all early, outside a POI | 2198 | −0.184 | 2446 | +0.013 | −0.197 | −5.3 |

The POI does not absorb the split; the two stack. Win rates move with it —
grade B is 36% with BTC and 46% against.

**And it is still not shipped, because grade B fails its robustness arms:**

| grade B split | diff | SE |
|---|---|---|
| symbols A (even index) | −0.126 | −1.2 |
| symbols B (odd index) | −0.321 | −3.1 |
| first half of window | **+0.289** | **+2.7** |
| second half of window | **−0.641** | **−6.2** |

The window halves have opposite signs, each at more than 2 SE. That is a
regime relationship that changed inside 42 days, and it is exactly why the
overall −3.0 must not be traded. The symbol halves agree in sign but differ
2.5x in size.

**This also settles the grade-A "inversion" recorded in the section above.**
It was not an inversion and it was not noise — it pointed the same way as
everything else, and it was dismissed because it was checked against a prior
that was itself backwards. The entry above stands as written for the two axes
it tested; its BTC paragraph is wrong and is superseded here.

**What changed.** The six studies. The `btc_at` and `trend_note` docstrings.
`TRADING.md`, which had been telling the reader to prefer the agreeing signal
— the worse half. And the alert text: 🟢/🔻 asserted a verdict the evidence
never supported in that direction and does not support strongly in the other,
so both now read "⛓️ BTC trending with/against you", uncoloured. No filter,
no grade change, no suppression.

### Blast radius of the sign bug, and what is NOT affected

Six results are relabelled, marked in place above with **LABELS SWAPPED**:

| result | script | status |
|---|---|---|
| feature table, the two BTC rows | `context.py` | columns swapped |
| "BTC 30m regime — the only thing that cleared the bar" | `context.py` | columns swapped |
| held-out BTC replication + `PREREG_btc.md` | `btc_regime.py` | columns swapped |
| early signals split by BTC | `standing.py` | columns swapped |
| equity variants naming BTC (incl. the +82%) | `equity.py` | selection was the other half |
| `max 8, early needs BTC` and every `ALL RULES` row | `portfolio.py` | filtered the other half |

**Unaffected, and worth stating explicitly because the temptation after a bug
like this is to distrust everything:** the daily POI and its held-out test,
the grade system, the 2R target, the stop-placement work, the fill-rate and
wait-bar studies, the sweep conversion table, the entry-gap gradient, the risk
cap, DI, the symbol's own daily trend, the concurrency caps, and
`max 8, 3 slots for confirmed` — the one portfolio rule `TRADING.md` actually
recommends. None of them read BTC. The bug lived in two helper functions that
only the BTC studies called.

### The check that should have existed — `research/studies/signs.py`

The bug survived a discovery run, a pre-registered held-out replication that
appeared to confirm it, and weeks in `TRADING.md`, because every verification
was a person reading a comment that was wrong. So the audit does not read
anything:

  1. `supertrend()` and `di_direction()` are bucketed by their own output and
     scored against realised trailing price. `+1` must land on bars that had
     been rising. Currently +0.574% vs −0.291% and +0.996% vs −0.860%, 12/12
     symbols agreeing on both.
  2. `htf_dir_at()` — the function the GRADE is built on, and the one whose
     inversion would silently flip every letter — is checked twice: that it
     passes its series' sign through unchanged (10587 bars, 0 disagreements),
     and against daily price directly (+18.3% vs −10.5%).
  3. Engine geometry: every long has stop < entry, every short the reverse.
     420 signals, 0 inverted. This pins what `is_long` means.
  4. The literal bug as a grep: no direction may be compared to `is_long`
     with `< 0`.

**It gates every deploy.** `deploy/update.sh` runs it on the new tree before
anything is installed, beside the byte-compile step. Exit 1 blocks the update
and notifies; exit 2 — the exchange unreachable — lets it proceed with a note,
because refusing to ship on a network blip would make an exchange outage look
like a bug in the commit, and the static half of the audit runs regardless. A
`timeout 180` is treated the same as exit 2; the audit takes about 5 seconds.
Pine/Python parity now runs there too but is ADVISORY only: chart drift is not
a reason to refuse a Python fix.

It exits non-zero on failure. **Negative-tested three ways** — inverting
`supertrend`'s return fails check 1 (0/12 symbols agree), inverting
`htf_dir_at` fails both arms of check 2, and reintroducing `< 0` in
`scanner.py` fails check 4 naming the file and line. Two checks shipped
earlier in this project could not fail; these can.

The lesson is not that pre-registration failed. It worked exactly as designed
and still certified a backwards claim, because a pre-registered direction is
only as good as the code computing the variable, and nothing in that procedure
ever looked at the variable.

## What a 60% win rate costs — `research/studies/winrate.py`

Asked for directly: raise the win rate to at least 60%. It is reachable, it is
easy, and it is the most expensive thing this project has priced.

The win rate is not a property of the signals. It is a property of the TARGET:
move the target down and more trades reach it. So the only honest way to
answer is to price the dial. 2748 alerts, 42 days, live universe, POI
required, unfilled counted as zero, fees in.

| target | fill | **win** | R/signal | total R |
|---|---|---|---|---|
| 0.50R | 79% | **69%** | −0.020 ± 0.012 | **−54.3** |
| 0.75R | 79% | **60%** | +0.003 ± 0.015 | +7.1 |
| 1.00R | 79% | 55% | +0.027 ± 0.017 | +74.2 |
| 1.50R | 79% | 46% | +0.057 ± 0.021 | +157.3 |
| **2.00R (shipped)** | 79% | **41%** | **+0.093 ± 0.025** | **+254.6** |
| 3.00R | 79% | 35% | +0.124 ± 0.030 | +339.9 |
| 4.00R | 79% | 32% | +0.150 ± 0.034 | +413.3 |

**Perfectly monotone in both directions across ten targets.** Every step that
raises the win rate lowers the money, and the two columns never cross.

To reach 60% overall you take a 0.75R target and keep **+7.1 R instead of
+254.6** — 97% of the profit, paid for a number that is not the profit. At
0.5R the win rate is 69% and the strategy LOSES.

Per grade, where the signal is better and the trade less brutal:

| | 60% reached at | R/signal there | R/signal at 2R | cost |
|---|---|---|---|---|
| grade A | 1.25R | +0.214 | +0.286 | −25% |
| grade B | 0.75R | +0.051 | +0.186 | −73% |

So 60% on grade A alone is the only version of this that is merely expensive
rather than ruinous, and it still throws away a quarter of the edge.

**The break-even win rate at 2R is 1/(1+2) ≈ 33%, and 36% after fees.** Grade
A wins 49% and grade B 45%. The distance from break-even is the edge; the
distance from 60% is not a deficit, it is what a 1.8:1 payoff looks like.

### The 4R result is NOT a recommendation

The ladder never turns over — R/signal is still climbing at 4R, which is the
largest target tested. Four reasons not to act on it:

  1. The standard error widens with the target (±0.034 at 4R against ±0.025 at
     2R), because the same signals produce fewer, larger outcomes.
  2. The horizon is fixed. A longer target inside an unchanged 60-bar window
     converts wins into timeouts, and the timeout is scored where it exits,
     which flatters nothing but hides the cost in trade DURATION.
  3. Slots. `portfolio.py` measures the concurrency cap as the binding
     constraint; a 4R target holds each slot far longer, and none of that is
     in this table. Total R per signal is not total R per slot-day.
  4. `decisions.py` put 2R→3R at about 1.5 SE on an earlier window. Monotone
     on one window is suggestive; it is not the held-out test that the daily
     POI passed and that this has not been given.

2R stays shipped. What this table settles is the direction of the question,
not a new target.

## Entering at the MSS close instead of the gap — `research/studies/mss_entry.py`

Asked after an XPL long missed its limit by 0.12R and then ran 3%. Not covered
by `fills.py`, which tested a market entry at the SIGNAL bar (the gap). This is
earlier: the moment structure shifts, before the retracement that may never
come. 1244 confirmed setups, 42 days, live universe, fees in, unfilled shipped
entries counted as zero.

Two ways to score it, because they answer different questions. **2R of the new
risk** keeps the trade's shape. **Same target price** keeps the destination —
this is the version that asks "would I have caught the move", which is what
the missed chart shows.

| inside a daily POI | fill | win | RR | R/signal | total |
|---|---|---|---|---|---|
| **shipped: limit at the gap** | 70% | 44% | 1.79 | **+0.162 ± 0.061** | **+68.2** |
| MSS close, 2R of new risk | 100% | 43% | 1.59 | +0.102 ± 0.066 | +43.0 |
| MSS close, same target px | 100% | **55%** | 0.93 | +0.057 ± 0.051 | +24.0 |

| grade A | fill | win | RR | R/signal | total |
|---|---|---|---|---|---|
| **shipped** | 71% | 50% | 1.81 | **+0.294 ± 0.094** | **+54.0** |
| MSS close, 2R of new risk | 100% | 47% | 1.66 | +0.245 ± 0.103 | +45.0 |
| MSS close, same target px | 100% | **59%** | 0.96 | +0.157 ± 0.077 | +28.9 |

**It loses on every arm — all setups, inside a POI, outside one, grade A and
grade C.** Six comparisons, six the same direction. The fill rate does go to
100% exactly as advertised; it is simply not worth what it costs.

**The mechanism is arithmetic, not luck.** The stop does not move — it is the
raid extreme, the price at which the setup is wrong — so a worse entry inflates
the risk rather than tightening the stop. Measured inflation: **1.46x**. The
same market move is therefore worth 1/1.46 = 0.68 as many R, and the 2R target
sits 46% further away in price. The win rate barely moves (35% → 37%) because
the target retreated in step with the entry. And the entry pays TAKER instead
of maker.

This is the sixth independent confirmation of the same thing: the limit order
is not a formality, it is doing the selecting. Market at the gap (−0.064 /
−0.048), chasing by ATR (−0.066 / −0.230), constant-risk chasing, dropping to
5m for a tighter stop, cancelling early — and now this.

### It also prices the 60% win rate exactly

`grade A, MSS close, same target price` **wins 59%** — within a point of the
60% that was asked for. It also earns **+0.157 against +0.294**, so reaching
that win rate costs **47% of the edge on the best signal the bot produces**.

The reason is visible in the RR column: 1.81 → 0.96. A 59% win rate at 0.96:1
is worth about half of a 50% win rate at 1.81:1. This is the `winrate.py`
result arriving from a completely different direction, and it is the clearest
statement of it in the file — **the win rate went up, the money went down, in
the same table, on the same signals.**

### Note on the chart's own statistics panel

The Pine panel shows Net @1R +52.0R, @1.5R +54.5R, @2R +54.3R, @3R +54.5R on
XPL — a target ladder that is completely flat, which contradicts the
strongly monotone ladder in `winrate.py` (+254 at 2R, +340 at 3R, +413 at 4R).

The panel had **BE arms 1.5R, locks 0.1R** switched on. `beArmR` ships at 0.0
and its tooltip records why: break-even lost at every arm level on both signal
types. With it armed, most trades that would have run are scratched near
entry, so the target stops mattering — the flat ladder is an artifact of that
setting, not a fact about the market. The panel also states
`excl. fees/funding/slippage`, so its +0.33/trade is GROSS and not comparable
with the net figures in this file.

## "Trade with the trend" — which trend? — `research/studies/which_trend.py`

The phrase names two different things and this strategy does not treat them
alike. 8218 signals, 4813 with both trends readable, 42 days, fees in.

  **Daily** = `TREND_INTERVAL` / `DI_INTERVAL`, both Day1. What the grade reads.
  **Chart** = the same SuperTrend and DI on the timeframe being traded.

| | n | win | R/signal |
|---|---|---|---|
| **daily agrees** | 3408 | 39% | **+0.056 ± 0.022** |
| **daily against** | 3468 | 34% | **−0.083 ± 0.021** |
| | | | **+0.139, +4.5 SE** |
| chart agrees | 1895 | 35% | −0.046 ± 0.029 |
| chart against | 3897 | 36% | −0.044 ± 0.020 |
| | | | **−0.002, −0.0 SE** |

**The daily trend is the strongest single axis measured after the POI. The
chart's own trend sorts nothing at all** — not weakly, not negatively: a
difference of 0.002 R on 5792 signals, which is as close to a pure null as
this project has produced.

The direction was stated before measuring, in the script's docstring: this is
a reversal strategy, price raids a pool and turns, so the move immediately
before the setup is by construction going the wrong way on the chart being
traded. "With the chart trend" asks a reversal pattern for continuation. The
prediction was that it would not help. It measured exactly zero.

So the answer to the question is unambiguous: **the higher timeframe supplies
the direction, the chart supplies the entry.** They are different jobs and the
advice is only correct about the first.

### The 2x2 is NOT to be traded, and it is worth saying why

| R/signal | chart agrees | chart against |
|---|---|---|
| all signals · daily agrees | −0.010 (711) | **+0.033** (1651) |
| in a POI · daily agrees | **+0.359** (207) | +0.139 (654) |
| confirmed · daily agrees | **+0.037** (186) | −0.168 (134) |

Three panels, and they disagree about the sign of the chart's contribution
inside the same daily-agrees row: it hurts on all signals, helps inside a POI,
helps on confirmed. That is the self-contradicting 2x2 that got the
BTC × own-trend interaction rejected, in the same shape.

An earlier version of this script printed "best cell inside a POI: daily
agrees, chart agrees +0.359". That line was removed. It is the maximum of four
post-hoc subgroups with no correction — precisely the move this file has
rejected twice before — and quoting it would have manufactured a filter out of
n=207. The script now prints whether the panels agree instead of which cell
won.

## Does the daily POI rescue a scalping timeframe? — `research/studies/scalp.py`

Asked after three trades in a row stopped out: tune it down to a scalping
timeframe. Worth re-testing rather than quoting the old Min5 result, because
that run predates the POI — and the POI is the one thing that ever changed a
timeframe's verdict, turning Min15 from −0.078 on its own to positive inside a
zone. If it rescued 15m it might rescue 5m.

44845 signals, 30 symbols, **every timeframe given the same ~42 calendar days**
by paging (2000 bars is 41.6d of Min30 but 6.9d of Min5), fees in, unfilled
counted as zero.

**Inside a daily POI:**

| tf | n | /day | stop% | fee/R | fill | win | R/signal |
|---|---|---|---|---|---|---|---|
| **Min30** | 666 | 16.0 | 1.09 | 7.3% | 77% | 45% | **+0.146 ± 0.049** |
| **Min15** | 1198 | 28.8 | 0.77 | 10.4% | 81% | 39% | **+0.033 ± 0.039** |
| Min5 | 2967 | 71.2 | 0.41 | 19.7% | 90% | 35% | **−0.150 ± 0.026** |
| Min1 | 7080 | 230.1 | 0.18 | 44.4% | 95% | 32% | **−0.525 ± 0.020** |

**Inside a POI, with the daily trend** — the best condition available:

| tf | fill | win | R/signal |
|---|---|---|---|
| Min30 | 79% | 50% | **+0.281 ± 0.072** |
| Min15 | 80% | 43% | +0.142 ± 0.056 |
| Min5 | 89% | 37% | **−0.083 ± 0.041** |
| Min1 | 95% | 34% | **−0.401 ± 0.030** |

**The POI does not rescue Min5 or Min1. Every arm is monotone in timeframe and
the sign flips below 15m.** The filter that saved 15m cannot save 5m, and the
reason is not subtle.

### The fee column is the whole story

| tf | median stop | round trip costs | as a share of a 1R loss |
|---|---|---|---|
| Min30 | 1.09% | 0.073 R | **7%** |
| Min15 | 0.77% | 0.104 R | **10%** |
| Min5 | 0.41% | 0.197 R | **20%** |
| Min1 | 0.18% | 0.444 R | **44%** |

Cost in R is `FEE / risk_pct`, so halving the stop doubles the fee in R terms.
At Min1 the exchange takes 44% of the risk on every round trip before the trade
has done anything. No edge in this family survives that.

### And it makes the complaint worse, not better

The win rate FALLS monotonically as the timeframe drops — 45% → 39% → 35% → 32%
inside a POI. Tighter stops sit closer to the noise they are meant to be
outside of, so a scalping timeframe produces MORE stop-outs, not fewer. The
symptom that prompted the request is the thing the change would amplify.

Three stop-outs in a row on grade A/B is a 13–16% event. It arrives about one
week in seven and carries no information.

### One thing here IS worth a proper test, and it is not scalping

`Min30 confirmed inside a POI` on these 30 symbols: 101 signals, 63% fill,
**61% win**, +0.431 ± 0.121. That is the 60% win rate asked for two sessions
ago, on the HIGHER timeframe, at 3.6 SE.

It must not be read as a finding yet. `grades.py` put the comparable cell at
52% on 60 symbols, and this run differs in TWO ways at once — 30 symbols
instead of 60, and no daily-trend condition — so the causes are confounded.
What it suggests is that the improvement lies in **fewer, more liquid symbols
on a higher timeframe**, which is the opposite direction from scalping and is
consistent with the already-recorded finding that the wider universe is
materially worse per signal. Needs a clean one-variable test before anything
moves.

## Does a smaller, more liquid universe pay better? — `research/studies/universe.py`

The clean one-variable test promised after `scalp.py` showed Min30
confirmed-in-a-POI at 61% / +0.431 on 30 symbols against a comparable 52% on
60. That comparison changed the symbol count and dropped the trend condition
at once, so it settled nothing. Here only the symbol count moves: Min30, POI
required, same window, same scorer.

**Pre-registered before looking:** more liquid pays more per signal, and the
MARGINAL tiers must be monotone for it to count. Cumulative bands share most
of their signals, so a gradient there is nearly automatic and proves little.

**Designed around the look-ahead that would have guaranteed a positive.**
Ranking by today's turnover and scoring the last 42 days puts every coin that
just pumped in the top band because of the very move being scored.
`filter_by_turnover` ranks on live `amount24`, and `market.py` has 1.6 days of
history — not enough to rank on the past. So symbols are ranked by median bar
turnover (volume × close) over the FIRST half of the window and scored only on
signals in the SECOND half. The ranking variable is strictly prior to every
outcome it sorts.

**Honest split, marginal tiers — the pre-registered test:**

| tier | n | win | R/signal |
|---|---|---|---|
| symbols 1–10 | 120 | 45% | +0.145 ± 0.120 |
| symbols 11–20 | 164 | 42% | +0.020 ± 0.092 |
| symbols 21–30 | 129 | 34% | −0.031 ± 0.108 |
| **symbols 31–40** | 149 | 50% | **+0.296 ± 0.104** |
| symbols 41–60 | 264 | 37% | +0.036 ± 0.074 |

**Not monotone, and the best tier is the fourth** — precisely the band that
"fewer, more liquid symbols" would cut. The cumulative row behaves the same
way: +0.145, +0.073, +0.041, +0.108, +0.085, dipping and recovering rather
than falling. **Rejected.**

The naive same-window version is no better behaved (+0.015, +0.154, +0.101,
+0.261, +0.029), which incidentally says the look-ahead bias here is not a
simple one — the naive top-10 is WORSE than the honest top-10. Either way
there is no gradient to trade.

**What this settles.** The 61% in `scalp.py` was the confounded comparison it
was flagged as, not a finding. TOP_N stays at 60. And it is worth naming the
temptation that was refused: symbols 31–40 at +0.296 on n=149 is a middle tier
with no mechanism behind it, reachable only by reading a table five ways —
exactly the shape of the twenty-one entry filters that came before it.

The pre-registration did its job. Reading cumulative rows alone, "top 10 is
best at +0.145" was available and would have been wrong.

## CORRECTION — the daily POI test looked ahead, and most of its edge was that

Found on 9 Sep while controlling a mitigation result. It is the largest
correction in this file.

### How it surfaced

`mitigation.py` returned an enormous effect: unmitigated daily zones +0.743 at
a 74% win rate against −0.030, **+11.9 SE**. The pre-registered control asked
whether "unmitigated" was really "young", since a zone formed one bar before
the raid has no intervening bars and cannot be mitigated by construction. It
was worse than that. Splitting on age alone:

| zone age at the raid | n | win | R/signal |
|---|---|---|---|
| **0 daily bars** | 406 | **74%** | **+0.730 ± 0.059** |
| 1–2 | 460 | 34% | −0.051 |
| 3–5 | 480 | 38% | +0.044 |
| 6–10 | 626 | 37% | −0.029 |
| 11+ | 728 | 35% | −0.063 |

A cliff at zero and noise everywhere else is not an edge, it is a leak.

### The bug

`in_poi` tested `t <= when`. A zone is dated by the bar that COMPLETED it, and
that bar is not knowable until it CLOSES one step later. So a signal at 10:00
could match a zone built from the daily candle it was sitting inside — a
candle whose high, low and close encode where price went for the rest of that
day, **including after the raid being validated**.

`htf_dir_at`, twelve lines below in the same file, guards this exact hazard
and documents it: *"a bar whose open is at or before `when` may still be
forming, and using it would look ahead."* `in_poi` did not.

Fixed to `t + step <= when` in `research/studies/mtf_grid.py` and, for the same
rule in the live engine, `riptide/engine.py:in_zone`.

**The live bot was never affected.** `fetch_candles` drops the forming bar, so
the newest daily zone it can see has always been a closed one. The filter has
been doing the right thing; the MEASUREMENT that justified it was wrong.

### What the grade table actually is

Re-run of `grades.py`, everything else identical:

| grade | before (leaked) | **after (correct)** | win before → after |
|---|---|---|---|
| **A** | +0.271 ± 0.094 | **+0.128 ± 0.104** | 48% → **41%** |
| **B** | +0.180 ± 0.041 | **+0.080 ± 0.042** | 45% → **41%** |
| C *(muted)* | +0.016 | **−0.083** | 38% → 34% |
| **ALL** | +0.093 | **−0.007** | 41% → 37% |

**More than half the measured edge was the leak, and grade A is no longer
significantly positive at 1.2 SE.** B is 1.9 SE. The whole book, C included,
is flat.

The ORDERING survives — A > B > C, and C is now clearly negative, which is at
least an argument for having muted it. Min30 still beats Min15 (A +0.215 vs
+0.028; B +0.097 vs +0.062).

### What this invalidates

Every study that called `in_poi`, which is nearly all of them:
`mtf_grid`, `mtf_holdout` **(including the held-out POI test)**, `grades`,
`rates`, `missed`, `hybrid`, `sweeps`, `models23`, `grade_a`, `btc_by_grade`,
`winrate`, `which_trend`, `mss_entry`, `scalp`, `universe`, `mitigation`.

Their INTERNAL comparisons are mostly safe — the leak applies equally to both
arms of most splits, so a difference between arms is less affected than a
level. What is not safe is any absolute figure and, critically, the claim that
**the daily POI is a filter worth having at all**. That has to be re-measured
from scratch, and so does the held-out test it passed.

### The lesson, which is not a new one

This is the third time a measurement in this project was wrong in a way that
looked fine: the scorer bug (scoring from the signal bar, not the fill bar),
the BTC sign inversion, and now this. All three inflated a result. All three
survived review because the output was plausible.

The thing that caught this one was a **pre-registered control that I expected
to fail** — "is unmitigated just young?" — asked of a result I wanted to be
true. The control is what found the leak. Nothing else in the process would
have.

## Order block mitigation, measured properly — and a second copy of the same bug

`dailypriceaction.com/blog/order-blocks/` makes unmitigated status its central
rule: *"An order block is only valid the first time price reaches it... If
price has already wicked into the order block, even slightly, I consider it
mitigated, that level is done."* This is the claim `mitigation.py` was written
to test.

### The bug, again, in a copy

After `in_poi` was fixed, `mitigation.py` was re-run and **the numbers did not
move at all** — 2706 signals against 2700, the same +11.9 SE. That is what
exposed it: `poi_state` carried its own copy of `t <= when`, so fixing
`in_poi` had done nothing to this study. Fixed to `t + step <= when`.

MEASUREMENTS.md already records this exact lesson from the duplicate-signal
bug: *"A rule enforced in one place needs verifying in one place."* It was
written about a different bug and applied to none. A grep for the pattern
found the copy in seconds and should have been the first move after the fix.

### What survives once the look-ahead is gone

**The wick definition — the article's actual rule — becomes untestable.**

| | before (leaked) | after |
|---|---|---|
| unmitigated zones | 408 of 2706 (15%) | **3 of 2371 (0%)** |
| R/signal | +0.730 (74% win, +11.9 SE) | too few to report |

A daily zone that is at least one day old has essentially always been wicked
into. The entire +11.9 SE was age-0 zones — blocks read from the daily candle
the raid was sitting inside. **100% of that result was the leak.** By this
file's own pre-registered degeneracy rule (5–60%), the wick definition fails
and cannot be measured on daily zones at all.

**The close definition does survive, at a quarter of the size.**

| population | unmitigated | mitigated | difference |
|---|---|---|---|
| **all POI (primary)** | +0.209 ± 0.059 (47% win) | −0.061 ± 0.029 (34%) | **+0.269, +4.1 SE** |
| confirmed only | +0.161 ± 0.175 | +0.008 ± 0.073 | +0.153, +0.8 SE |
| grade A only | +0.283 ± 0.206 | +0.080 ± 0.120 | +0.203, +0.9 SE |

The pre-registered primary was 3 SE on the close definition, all POI signals.
**It clears at 4.1 SE, and no secondary panel flips sign.**

### It is a CANDIDATE and it is not shipped. Four reasons

1. **The "both definitions" clause failed.** `PREREG_mitigation.md` required
   the effect on wick and close alike, and the wick arm is now degenerate. That
   is not a contradiction — it is an arm that cannot be read — but it is not
   the support that was asked for in advance either.
2. **The fixed-age control is inconsistent.** Holding age at one value:
   age 1 +0.533 (3.6 SE), age 2 +0.700 (3.3), age 3 −0.106, age 4 +0.540 (2.0),
   age 5 +0.414 (1.6), age 6 −0.013, age 8 −0.142. Four positive, three flat or
   negative, no pattern in which is which.
3. **The non-monotone visit gradient predicted in advance is still there.**
   0 visits +0.209, 1 visit **−0.183**, 2–3 +0.004, 4+ −0.036. One visit is the
   worst cell and four or more recovers. Doctrine predicts decay; this is a
   cliff plus noise, and the pre-registration said in advance that this shape
   would mean the variable is not measuring what the story claims.
4. **It has not been held out.** Everything found in this window today was
   found in this window.

**What it is NOT is zone age.** That control came back clean: age 1–2 −0.049,
3–5 +0.058, 6–10 −0.002, 11+ −0.024. Flat. So a tighter `ZONE_MAX_AGE_BARS` is
not the hidden finding.

**Practical consequence for any indicator.** The article's rule as written —
any wick kills the block — cannot be implemented usefully on daily zones: it
would reject 2368 of 2371. A close-based mitigation test is implementable and
is the only version with evidence behind it.

---

## Liquidity Entry Zones, Phase 1 — `research/studies/lez.py`

A new indicator (`liquidity-entry-zones.pine`), ported to Python and scored on
Min5 / Min15 / Min30, 30 symbols, ~42 days each, entry at the confirmation
close as a taker, stop `1.5 × ATR(14)`, target 3R, fees 0.02/0.06%. Full
review of the Pine source in `STRATEGIES.md`.

The gate was written in `STRATEGIES.md` before the first run: **positive R per
signal after fees, with the same sign on both window halves and both symbol
halves.**

| timeframe | n | win | stops | risk | R/signal | gate |
|---|---|---|---|---|---|---|
| Min30 | 1383 | 26% | 1024 | 1.20% | **−0.122 ± 0.047** | FAIL |
| Min15 | 2906 | 24% | 2196 | 0.84% | **−0.226 ± 0.032** | FAIL |
| Min5 | 8299 | 23% | 6382 | 0.46% | **−0.435 ± 0.019** | FAIL |

The chart's own default view — `blockSignalsInTrade`, one position at a time —
is negative too: −0.145, −0.248, −0.293. There is no arm of this that is
positive.

### THE CONTROL IS THE RESULT

Random entries, same symbols, same timeframe, same market-at-the-close, same
1.5 ATR stop, same 3R target, same fees, entry bar and direction chosen by a
coin toss:

| timeframe | LEZ | random entries | what the signal adds |
|---|---|---|---|
| Min30 | −0.122 | **−0.094** | −0.027 ± 0.066 (−0.4 SE) |
| Min15 | −0.226 | **−0.149** | −0.077 ± 0.046 (−1.7 SE) |
| Min5 | −0.435 | **−0.340** | −0.095 ± 0.028 (−3.4 SE) |

**Almost the entire loss is the trade shape, and the trade shape's entire loss
is fees.** The control's gross is zero to three decimal places — at Min30 it
takes 340 targets at 3R against 1007 stops, which is 1020 − 1007 = +13 R over
1383 trades, or +0.009 before costs. A market entry with a symmetric volatility
stop and a distant target is a fair coin, exactly as it should be, and every
cent of its loss is the fee.

That is worth stating on its own, because it also validates the scorer: an
unbiased simulator is supposed to return zero on random entries, and it does.

What the signal itself contributes is between nothing and mildly negative, and
it gets worse as the timeframe falls. It never once helps.

### The fee law again, from a third direction

`scalp.py` found it by timeframe, `winrate.py` by target, and this by control.
Cost in R is `fee / risk_pct`, so as the stop tightens the fee grows:

| timeframe | mean risk | fee on a losing round trip |
|---|---|---|
| Min30 | 1.20% | 0.10 R |
| Min15 | 0.84% | 0.14 R |
| Min5 | 0.46% | 0.26 R |

And it is **convex** — the mean of `1/risk` is far above `1/mean(risk)` — so
the average is set by the quietest symbols, not the typical one. At Min5 the
random control loses 0.340 R per trade to fees alone, which is a third of a
stop, per trade, before anything is decided.

### The one arm where the indicator's own choice wins

The ATR stop beats a stop just beyond the raid extreme on every timeframe:
−0.122 vs −0.229 (Min30), −0.226 vs −0.367 (Min15), −0.435 vs −0.603 (Min5).
Both lose, so this is not a recommendation — but the structural stop is
*tighter* here (0.98% vs 1.20% at Min30) and pays more fee per unit of risk for
it, which is the same law a third time. `stop_buffer.py`'s buffer-of-0 finding
was measured on limit entries at a retracement; it does not transfer to a
market entry at a candle close.

### Evidence the port is sound, which a negative result needs as much as a positive one

- The random control returns zero gross. A scorer with a sign or fill error
  would not.
- The daily trend separates at Min30 exactly as `which_trend.py` says it
  should: agreeing +0.007, against −0.290, a 3.0 SE gap. A broken port does not
  reproduce a known effect in the right direction.
- Signal frequency is plausible: 1.1 per symbol per day at Min30 unblocked,
  0.15 serialised — about one a week per symbol, which is what a chart looks
  like.

### Other pre-registered arms, none of which rescue it

- **Target ladder** is flat: 1.5R −0.139, 2R −0.128, 3R −0.122, 4R −0.119,
  5R −0.134 at Min30. No target saves a signal with no edge, which is the
  correct behaviour and the mirror image of `winrate.py`.
- **The sweep bar is its own confirmation bar** for 52% of Min30 signals, 53%
  of Min15 and 54% of Min5 — so this is mostly a single-candle model, not a
  sweep-then-confirm one. At Min30 that arm is the worst: −0.225 same-bar
  against +0.121 at two bars (n=222, 1.0 SE — not evidence, just not a rescue).
- **25% of signals have their stop inside the sweep candle** that triggered
  them, across all three timeframes. §1.6 of `STRATEGIES.md` predicted this.
- **Quality score terciles do not order.** Min30: low −0.047, mid −0.170,
  high −0.148. As expected once 60 of its 100 points are pinned.
- **Overlap with Riptide is 7–9%.** It genuinely is a different strategy. It
  is simply not a profitable one.

### Verdict

**Phase 1 fails on all three timeframes. Phases 2–5 do not start.** No
parameter sweep, because sweeping a model that cannot clear zero once is how a
curve gets fitted — that condition was written into the plan before the run.

The finding that survives is not about this indicator at all: **a market entry
with a volatility stop is a fair coin, and on a 15m or 5m chart the fee alone
is a quarter to a third of a stop per trade.** Any future strategy taking
market entries starts from that hole.

---

## The Liquidity Entry Zones sweep — `research/studies/lez_sweep.py`

Run at the user's explicit direction after Phase 1 failed, and after the plan
had said no sweep. 360 cells per timeframe: stop 0.75/1/1.5/2/3 ATR, target
1.5/2/3/4 R, quality any/≥75/≥85, daily trend any/agrees/agrees-or-flat, daily
POI off/required. Min30 and Min15, ~83 days fetched and cut in half — the newer
half to sweep on, the older half never looked at before, for one shot at the
winner.

### THE INSTRUMENT THAT DECIDES IT: a control sweep

Best-of-360 on pure noise clears +2.9 SE by construction. So the identical grid
is asked of **random entries** — same symbols, same bars, same stops, same
targets, same trend and POI filters, direction by coin toss — and the headline
number is not R per signal but **EDGE = LEZ − random in the SAME cell**. That
matters because widening a stop raises `risk_pct` and fee-in-R is
`fee / risk_pct`, so a wider stop improves *every* strategy including a coin
flip. A sweep reporting R per signal will "discover" a wide stop and call it an
edge.

**The noise floor, measured rather than assumed** — the same 360 questions
asked of coin flips, one half of the control pool playing against the other:

| timeframe | best of 360 noise cells | 5th best | best LEZ cell |
|---|---|---|---|
| Min30 | **+0.289** | +0.173 | +0.196 |
| Min15 | **+0.191** | +0.151 | +0.117 |

**Neither timeframe's best cell reaches its own noise floor.** A grid this size
manufactures a better-looking result out of coin flips than the strategy
produced. That is the sweep's answer and everything below is detail.

> The first version of this floor was broken and would have made the control
> decorative: it compared the random pool **to itself**, which returns an edge
> of exactly zero in every cell. A floor of +0.000 that any result clears. It
> was caught because +0.000 across 120 cells is not a number noise produces.

### The held-out shot, reported exactly as the rule was written

| | Min30 winner | Min15 winner |
|---|---|---|
| cell | 1 ATR, 4R, Q≥85, POI | 3 ATR, 4R, Q≥75, trend-not-against, POI |
| discovery | +0.196 edge / −0.050 R | +0.117 edge / +0.106 R |
| **held out** | +0.127 ± 0.158 edge / **−0.106** R | +0.052 ± 0.110 edge / **+0.121 ± 0.098** R |
| pre-declared bar | **FAILS** | **PASSES** |

**And the bar it passed was too weak — that is my error, and it was in the
pre-registration.** "EDGE > 0 and R/signal > 0" has no significance
requirement, so a coin flip clears it about half the time. The Min15 held-out
edge is **0.5 SE** and its R per signal **1.2 SE**. Pooling both halves of that
one cell gives roughly +0.085 ± 0.076 edge, about 1.1 SE. Nothing here is
distinguishable from zero, and the instrument that was built to say so — the
floor — says the cell never cleared it on discovery either.

### One knob at a time, which is the readable part

Min30, from the shipped defaults, EDGE in the last column:

| knob | R/signal | random | EDGE |
|---|---|---|---|
| stop 0.75 ATR | −0.228 | −0.307 | **+0.079** |
| stop 1.5 ATR (shipped) | −0.126 | −0.152 | +0.026 |
| **stop 3 ATR** | **−0.077** | **−0.077** | **+0.000** |
| target 2R | −0.131 | −0.165 | +0.034 |
| target 4R | −0.118 | −0.130 | +0.012 |
| Q ≥ 85 | −0.147 | −0.152 | +0.005 |
| daily trend agrees | +0.006 | +0.026 | **−0.020** |
| **POI required** | −0.078 | −0.148 | **+0.070** |

The 3 ATR row is the cleanest statement of the whole exercise: the strategy and
a coin flip score **identically to three decimal places**, and the only reason
R per signal improved from −0.228 to −0.077 is that a 2.38% stop pays a third
of the fee a 0.59% stop pays.

At **Min15 every single knob has a negative edge** except Q≥85 at +0.007 —
including the two that raise R per signal most. Yet the Min15 grid still
produced a +0.117 best cell. That gap between "every ingredient hurts" and "the
best of 360 combinations looks fine" is best-of-N, visible in one table.

### The trend filter helps random entries MORE than it helps this strategy

Min15: the daily-trend filter takes random entries from −0.179 to **−0.040**
and LEZ from −0.227 to only −0.139. Min30: random −0.152 → **+0.026**, LEZ
−0.126 → +0.006.

Two things follow. First, `which_trend.py`'s +4.5 SE daily-trend effect
reproduces cleanly **inside the control**, which is independent evidence that
the scorer and the context plumbing here are sound. Second, this strategy is
anti-correlated with it: LEZ buys after a low is swept — a mean-reversion
trigger — while the trend filter is a momentum filter. A random long in an
uptrend rides it; a LEZ long in an uptrend has specifically bought a flush.

### Answers to the specific questions asked

- **2R**: no. Min30 edge +0.034 (R −0.131), Min15 edge −0.043 (R −0.226). The
  target ladder is flat in edge terms at both timeframes; 2R is not special.
- **ATR multiple**: wider is better for R and worse for edge, monotonically,
  and both are the fee moving. There is no stop width at which the signal pays.
- **Quality score**: dead, as predicted from its construction — 60 of its 100
  points are pinned by the gates it divides by. Min30 +0.005, Min15 +0.007.
- **Trend**: negative edge on both timeframes. It is a good filter that this
  signal is the wrong shape for.
- **POI**: the only knob with any life — Min30 +0.070 on 372 signals — and it
  flips sign at Min15 (−0.036). One timeframe positive, one negative, is how
  the BTC × own-trend interaction was rejected, and it was right to be.

### Verdict

**The sweep found nothing that clears its own noise floor.** The components
that carry the one positive-looking cell — the daily trend and the daily POI —
are variables Riptide already uses and already gates on. The Liquidity Entry
Zones trigger itself contributes about +0.05 R with a standard error of 0.11.

If a strategy is to be built out of this, the honest reading is that the
filters are doing the work and the trigger is decoration.

---

## The momentum mirror: break and retest — `research/studies/momentum.py`

Built because the LEZ sweep left exactly one thing pointing somewhere: the
daily-trend filter helped RANDOM entries more than it helped LEZ. That is
`which_trend.py`'s +4.5 SE effect reproducing inside the control while the
strategy fails to collect it, and the reason is shape — LEZ buys after a low is
swept, which is mean reversion, while the daily trend is a momentum filter.

So: the same machinery, inverted. Same stored pivots, same ATR margin, same
cooldown, same scorer. Instead of *takes a level and closes back inside it*
(rejection), it is *takes a level and closes beyond it* (acceptance), and the
broken level becomes the retest.

Fixed by evidence rather than swept: direction is a **requirement** from the
daily trend, not a filter (longs only in a daily uptrend, flat days sit out);
no chart EMA, because it is the measured null; body ≥ 50% of range for a
decisive close; and the level must be freshly broken — the previous bar closed
on the other side — which fixes the stale-level flaw found in the Pine.

**Pre-registered primary, named before the run:** market entry at the breakout
close, 1.5 × ATR(14) stop, 3R target, no POI. The exact mirror of LEZ's shipped
settings, so LEZ vs this differs in one variable. The other 23 cells are
descriptive; naming the cell in advance is what stops best-of-N, and the
previous study's bar failed precisely because it was applied to the best of 360.

### The held-out result, on the pre-declared cell

| | Min30 | Min15 |
|---|---|---|
| n | 1773 | 3508 |
| win | 23% | 24% |
| R/signal | **−0.201 ± 0.040** | **−0.212 ± 0.029** |
| matched control | −0.140 | −0.199 |
| EDGE | **−0.062 ± 0.047** | **−0.013 ± 0.034** |
| | **FAILS** | **FAILS** |

Discovery said +0.005 (Min30) and −0.083 (Min15). It was never positive.

### Every matched-risk cell, and the noise floor

| | best matched cell | worst | noise floor |
|---|---|---|---|
| Min30 | +0.079 (0.8 SE) | −0.107 | **+0.250** |
| Min15 | −0.036 | −0.117 | **+0.183** |

At Min15 **every** matched cell is negative. At Min30 the best is a third of
the floor. Nothing here is a candidate.

### THE TRAP THIS RUN WALKED INTO, TWICE

**First: a stop that is not a trade.** The structural stop sits at the breakout
bar's extreme and the retest limit sits at the broken level; nothing keeps them
apart. When they land a hair apart, `risk_pct` goes to nearly zero while fee in
R is `fee / risk_pct` — so one row books a loss of tens of R. The first run had
all eight `struct` cells at the TOP of the table with control means near
**−4.7 R**, entirely from a handful of those. A floor of `risk ≥ 0.25 × ATR`
fixes it: below a quarter of a bar's typical range the stop is inside the noise
of the candle that triggered the trade.

**Second, and this one is subtler: EDGE only cancels the fee when the two sides
take the SAME RISK.** With the floor in place the `struct` cells still topped
the table — Min30 `market struct 3R POI` at **+0.304, 2.9 SE**; Min15
`market struct 2R ---` at **+0.142, 4.8 SE**. Four to five sigma, consistent
across timeframes and POI settings. It looks like a finding.

It is not. A breakout bar has a big body by definition, so its close-to-extreme
distance is wider than a random bar's, and a wider stop pays less fee per unit
of risk *and* aims at a target that is further away in price. It is a different
trade, not a better-timed one. Printing the control's risk beside the signal's
settles it in one line:

| cell | signal risk | control risk | EDGE | SE |
|---|---|---|---|---|
| Min15 market struct 2R POI | 0.58% | **0.36%** | +0.211 | +3.2 |
| Min15 market struct 2R --- | 0.67% | **0.45%** | +0.142 | +4.8 |
| Min15 **retest struct 2R ---** | 0.47% | **0.43%** | **+0.046** | +1.3 |
| Min15 **retest struct 3R ---** | 0.47% | **0.43%** | **+0.002** | +0.1 |

Within one family, the six cells whose risk is mismatched score +0.09 to +0.30,
and the two whose risk nearly matches score **+0.046 and +0.002**. The edge is
the risk gap. Every ATR-stop cell matches to within 5% by construction and is
readable; every `struct` cell is now printed with a RISK MISMATCH marker rather
than deleted, so the artefact stays visible instead of being quietly dropped.

### What both studies agree on, which is the useful part

The two triggers are opposites — rejection and acceptance of the same pivot
levels — and they land in the same place:

| | best R/signal seen | its matched control | trigger's contribution |
|---|---|---|---|
| LEZ (rejection), Min15 held-out | +0.121 | +0.069 | +0.052 ± 0.110 |
| Momentum (acceptance), Min30 disc | +0.176 | +0.113 | +0.063 ± 0.090 |

**Roughly +0.05 R, with a standard error twice that, from either polarity.**
Meanwhile the conditions those cells share — daily trend agreeing, raid inside
a daily POI — take the CONTROL from about −0.15 to about +0.11. The location
filters are worth two to three times what the trigger is worth, and they are
worth it to a coin flip.

**The practical reading: the entry trigger is not where the money is on this
data.** Riptide already gates on both filters. A third pivot-level trigger,
in either direction, is not the missing piece.

Stated as an open question rather than a finding, because it has not been held
out here: a control that is positive at trend + POI (+0.113 on the Min30
discovery half) is consistent with `which_trend.py` and `hybrid.py`, and would
be worth a study of its own with a pre-registered bar.

---

## Location or trigger? A nested ladder — `research/studies/location.py`

`lez.py` and `momentum.py` are opposite triggers on the same pivot levels and
both landed in the same place: the trigger worth about +0.05 R with twice that
in standard error, while the control went from about −0.15 to about +0.11 once
the daily trend agreed and the raid sat in a daily POI. That was an accident of
two studies, seen after the fact, on discovery halves. So it got its own
pre-registration and its own held-out shot.

**One trade shape on every rung** — market entry at the close, 1.5 × ATR(14)
stop, 3R target — so `risk_pct` cannot drift between rungs and the fee cannot
masquerade as an edge, which is exactly how `momentum.py` produced a 4.8 SE
mirage.

| rung | Min30 disc | Min30 **held** | Min15 disc | Min15 **held** |
|---|---|---|---|---|
| L0 random, nothing | −0.147 | −0.130 | −0.175 | −0.170 |
| L1 + daily trend agrees | +0.042 | **−0.131** | −0.063 | **−0.153** |
| L2 + raid in a daily POI | −0.121 | −0.074 | −0.202 | −0.089 |
| **L3 + BOTH (location alone)** | **+0.107** | **−0.001** | −0.002 | **−0.082** |
| L4 L3 + LEZ trigger | +0.112 | +0.025 | −0.013 | −0.052 |
| L5 L3 + Riptide cluster sweep | +0.033 | −0.079 | +0.005 | −0.053 |
| L6 L5 + valid, shift < 3% | +0.149 | +0.091 | +0.051 | −0.062 |

### The primary FAILS, and it was told in advance what that would mean

L3 on the held-out half is **−0.001 ± 0.054** (Min30) and **−0.082 ± 0.040,
−2.0 SE** (Min15). The bar was positive at 2 SE. This document said before the
run: *"if L3 is flat, then the +0.11 seen in two control groups was the
discovery halves talking."* It was. **Location alone is not tradeable.**

### THE BIGGEST RESULT HERE IS ABOUT THE DAILY TREND, AND IT IS A WARNING

L1 is "trade in the daily trend's direction, at a random bar". Against L0:

| | discovery | held out |
|---|---|---|
| Min30 | −0.147 → **+0.042** (+0.189) | −0.130 → **−0.131** (−0.001) |
| Min15 | −0.175 → **−0.063** (+0.112) | −0.170 → **−0.153** (+0.017) |

**On the older half the daily trend adds nothing at all.** It is worth +0.19 R
in one 42-day window and 0.00 in the one before it.

This does not refute `which_trend.py`, and the difference matters: that study
measured *agreeing versus against* on Riptide's own limit-entry signals, a
relative split. This measures the *absolute lift* of trading with the trend at
a random bar. But it does say the absolute lift is regime-dependent, and every
control group in the last three studies was standing on it. Any future result
resting on "the daily trend adds R" needs both halves, not one.

### The user's question: is Riptide's sweep logic a better filter than a pivot?

Two separate things were tested, and they answer differently.

**The cluster definition alone does nothing.** L5 is a Riptide `Cluster` being
taken — several pivots within `tol_atr` of each other, a genuine pool of equal
highs or lows, rather than LEZ's single 5-bar `ta.pivothigh`. Against L3 it
scores −0.073, −0.078, +0.007, +0.029 across the four panels. Two negative, two
positive, none above 0.8 SE. **A better definition of "a level" is not worth
anything on its own.**

**The validity test is the only thing in this session positive in all four
panels.** L6 adds `sweep_worth`'s rule — the structure level the shift must
break is within 3% — and against L3 it scores **+0.042, +0.092, +0.053,
+0.020**. Four for four.

And it earns them **against a fee handicap**, which is the opposite of the trap
that has caught two studies here. L6 selects lower-volatility bars (a 3%
distance is easier to satisfy on a quiet symbol), so its `risk_pct` is 0.64–0.92%
against L3's 0.78–1.26%, and fee in R is `fee / risk_pct` — it pays **0.032 to
0.038 R more per losing trade than L3 does**. The script prints that line on
every panel rather than leaving it to be assumed.

**It is still not a finding.** Each increment is under 1 SE; pooled across the
four panels it is roughly +0.05 with a standard error near 0.05. It is the
first thing in six studies that has not been killed, which is not the same as
being alive.

### On filtering, which was the practical question

Signals per symbol per day, on the same universe:

| | Min30 | Min15 |
|---|---|---|
| L4 LEZ trigger | 0.10–0.11 | 0.19–0.20 |
| L5 Riptide cluster sweep | 0.42–0.48 | 0.65–0.71 |
| L6 + the 3% validity rule | 0.18–0.22 | 0.37–0.41 |

The validity rule cuts the sweep count by **roughly half** — and it is the half
that carries whatever is there. That is the same shape `sweep_worth`'s own
docstring reports from a different measurement: under 3% is 48% of raids and
87% of the R.

### What this run says overall

The trigger is not where the money is, and neither is the location. What
survives is narrower than either: **not "was a level taken" but "was the level
taken close enough to structure that a shift can follow"** — a property of the
raid's geometry, not of the candle that made it. Riptide already gates its
sweep alerts on exactly that rule. This is weak, out-of-sample support for a
filter that is already shipped, and it is the correct place to look next.

---

## Where is the knee in the shift distance? — `research/studies/shift_distance.py`

`location.py` left one thing alive: `sweep_worth`'s rule that the level a shift
must break sits within `WATCH_MAX_DIST` = 3% of the raid extreme. So: is the
knee tighter than 3%, and is percent even the right unit?

**Scope first, because it decides how to read the R column.** This study trades
the RAID BAR directly — market entry at its close, 1.5 × ATR stop, 3R. Riptide
does not do that; it rests a limit at the FVG with the stop at the raid extreme.
So the R column here describes *trading the raid*, not Riptide's alerts. The
**conversion** column is Riptide's own pipeline and does describe it.

### The conversion rate replicates, exactly

`riptide/engine.py`'s docstring justifies the 3% cut with a table measured on a
window this project no longer has. Re-measured on the current one, `<1%` /
`1-2%` / `2-3%` / `>3%`:

| | Min30 disc | Min30 held | Min15 disc | Min15 held | shipped docstring |
|---|---|---|---|---|---|
| <1% | 17% | 30% | 19% | 23% | 22.7% |
| 1–2% | 13% | 19% | 8% | 7% | 14.8% |
| 2–3% | 3% | 9% | 3% | 4% | 6.6% |
| >3% | 1% | 1% | 1% | 1% | 0.7–3.1% |

**Monotone in all four panels, magnitudes matching.** A shipped constant whose
evidence could not be re-run is now a shipped constant whose evidence re-runs.

### But R is NOT monotone in distance, and tightening makes it WORSE

The pre-registered primary was a monotone decline across those four bands in
both halves. **It fails in every panel.** And the secondary is unambiguous:

| | <1.5% | 1.5–3% | difference |
|---|---|---|---|
| Min30 discovery | −0.299 | −0.056 | **−0.243 ± 0.130** |
| Min30 held out | −0.161 | −0.023 | **−0.139 ± 0.149** |
| Min15 discovery | −0.280 | −0.200 | **−0.080 ± 0.094** |
| Min15 held out | −0.166 | −0.118 | **−0.048 ± 0.097** |

**Four panels, all negative. Tightening `WATCH_MAX_DIST` below 3% would make it
worse, not better.** That is the answer to the question asked.

### The two columns disagree, and the fee is why

The `<1%` band converts most often and scores worst. Min15 discovery: 19%
conversion, `risk_pct` **0.42%**, so the fee is **0.347 R** — gross −0.085
against net −0.432. Min15 held out: 23% conversion, risk 0.50%, fee 0.254 R,
gross **+0.120** against net −0.134.

A raid that sits close to structure sits on a quiet symbol with tight
structure, where 1.5 ATR is a fraction of a percent of price — and fee in R is
`fee / risk_pct`. **The nearest raids are the best signals and the worst trades,
and it is entirely the fee.** Gross R shows no gradient either way; this is not
a claim that near raids are secretly profitable.

### Percent is the wrong unit — ATR is the only ordering that holds

Top band minus bottom band, across the two halves:

| unit | Min30 disc/held | Min15 disc/held | |
|---|---|---|---|
| percent | −0.559 / **+0.183** | −0.273 / −0.010 | **sign flips at Min30** |
| **ATR** | **+0.065 / +0.226** | **+0.180 / +0.205** | **four for four** |

Measuring the distance in ATR removes the volatility confound by construction,
and the `1–2 ATR` band also carries the highest conversion anywhere in either
unit — **31%, 37%, 36%, 33%** across the four panels.

This is a **candidate, not a change.** It is a top-versus-bottom consistency,
not the monotone decline the primary demanded, and it was measured against a
market entry with an ATR stop rather than Riptide's actual entry model. It
needs its own pre-registered test against the real pipeline before
`sweep_worth` is touched.

### The concrete gap this exposes in the shipped code

`Cfg.max_risk_atr = 2.5` caps risk **in ATR units**. There is no floor on risk
as a **percent of price** anywhere in the codebase — and fee in R lives
entirely on that axis. An ATR-unit cap cannot see the difference between a
1.5 ATR stop worth 0.42% and one worth 1.6%, and those two trades pay 0.35 R
and 0.08 R respectively before anything happens.

Every study in this sequence has ended at the same place from a different
direction: `scalp.py` by timeframe, `winrate.py` by target, `lez.py` by
control, `momentum.py` twice by accident, and now this one by distance band.
**A minimum `risk_pct` is the best-evidenced untested lever in the project**,
and it applies to Riptide itself, not only to the strategies that failed.

### Verdict

- **Do not tighten `WATCH_MAX_DIST`.** Four panels say tighter is worse.
- The 3% rule is a **conversion** filter and a good one; it was never an R
  filter and this confirms it is not one.
- Distance in **ATR** is a candidate worth a proper test.
- The next study is a **minimum risk floor in percent**, on Riptide's own
  signals, with a pre-registered monotonicity bar.

---

## The stop: where to put it, and what to do with it — `research/studies/stops.py`

Two pre-registered questions, one collection pass, on Riptide's real signals
(limit at the gap, stop at the raid extreme) and on LEZ (market at the close,
1.5 ATR stop), Min30 and Min15, window split in half. Target 2R — what the
chart is actually running.

**Both primaries fail.** Neither a minimum risk floor nor any stop-management
rule clears its bar. But the tables answer the question that was asked.

### A. The risk floor — NOT SUPPORTED, and the reason is instructive

Net R is not monotone in `risk_pct` in any of the eight panels. The gradient is
an **inverted U**: both extremes are bad and the middle is least bad, so a
floor is the wrong instrument even where the bottom bucket is genuinely awful.

What the gross column does show, and it is the fee in the clear:

| panel | bottom bucket | fee | gross | net |
|---|---|---|---|---|
| LEZ Min15 discovery | risk < 0.45% | **0.368 R** | −0.123 | **−0.490** |
| LEZ Min15 held out | risk < 0.50% | **0.281 R** | **+0.123** | **−0.158** |
| LEZ Min30 discovery | risk < 0.65% | 0.255 R | −0.077 | −0.332 |
| Riptide Min15 held | risk < 0.54% | 0.134 R | −0.101 | −0.235 |

The LEZ Min15 held-out row is the whole argument in one line: those trades are
**profitable gross at +0.123** and the fee alone turns them into −0.158. Three
quarters of a stop, paid to the exchange, on the tightest fifth of trades.

And the study's own design question is answered cleanly. The bottom bucket is
the worst bucket in **3 of 4 LEZ panels** but only **1 of 4 Riptide panels** —
exactly as the pre-registration predicted it might split. LEZ's risk is
EXOGENOUS (a fixed ATR multiple, so a small `risk_pct` just means a quiet
symbol and a big fee); Riptide's is ENDOGENOUS (the raid extreme, so a small
`risk_pct` means a tight raid, and setup quality competes with the fee).

**No floor is recommended.** Monotonicity was the bar and it was not met. Even
in the best case the arithmetic does not rescue anything: dropping LEZ's worst
Min15 bucket moves the strategy from −0.212 to about −0.14, which is a smaller
loss, not a profit.

### B. Stop management — nothing beats a plain fixed stop, but look at the cost

No rule beats the plain stop on net R in both halves, on either strategy. The
Riptide prior replicates: break-even loses at every arm level, and the earlier
the arm the worse it is.

**But the question asked was about the win rate and the stop-outs, and the
partial delivers both, nearly free — on LEZ:**

| LEZ Min30, held out | win | full losses | R net | vs plain |
|---|---|---|---|---|
| plain fixed stop | 33% | **1131 (66%)** | −0.114 | — |
| BE at 1R, lock 0 | 29% | 988 (58%) | −0.126 | −0.012 |
| **half at 1R, rest to target** | **50%** | **843 (50%)** | −0.121 | **−0.007** |

**33% → 50% win rate, 66% → 50% full stop-outs, for 0.007 R per trade.** The
Min15 held-out panel is the same shape at a higher price: 34% → 49% win, 66% →
51% full losses, −0.031 R.

Note the break-even rule does the opposite of what it is reached for: it cuts
full losses but LOWERS the win rate (33% → 29%), because a break-even exit
scores 0.0 and `r > 0` does not count it. A partial banks +0.5R, which does.
**If the goal is the win rate, the partial is the instrument and break-even is
not.**

### THE PRICE OF A HIGHER WIN RATE IS PROPORTIONAL TO THE EDGE YOU HAVE

The same partial, on the one panel in this study where the strategy is actually
making money:

| Riptide Min30, discovery | win | full losses | R net | vs plain |
|---|---|---|---|---|
| plain fixed stop | 31% | 119 (39%) | **+0.174** | — |
| half at 1R, rest to target | 40% | 94 (31%) | **+0.071** | **−0.103** |

It costs **59% of the edge**. On LEZ, where there is no edge, the identical
rule costs 6%.

That is `winrate.py`'s finding arriving from a new direction and it is the
practical rule to take away: **a partial exit is close to free when the
strategy has no edge and expensive exactly when it has one.** Buying comfort is
cheapest where comfort is all you are buying.

### What ships from this

Nothing. Both primaries failed and neither is a change to the bot. What is now
quantified, and was not before:

- A 0.4% stop pays **0.37 R** per trade in fees. A 1.4% stop pays 0.07 R. That
  is the single largest cost in every strategy measured in this sequence.
- `Cfg.max_risk_atr` caps risk in ATR units and still cannot see that axis. A
  percent-based cap or floor remains untested as a *shipped* change, but the
  gradient does not support one.
- `research/harness.py`'s `simulate_market` now supports break-even and
  partial exits, mirroring `simulate` exactly, with tests — so the market-entry
  side of every future study can ask this question without a local copy.

---

## EMA trend-filter length — `research/studies/ema_len.py`

Asked directly: try 21 instead of 50. Run as a **ladder** rather than a
two-arm comparison, because a two-arm test of a null variable favours whichever
arm was asked about half the time and gives no way to tell that from an effect.

Everything held at what the chart runs — market entry at the close, 1.5 × ATR
stop, 2R target, MEXC fees. Only `ema_len` moves.

| arm | Min30 disc | Min30 **held** | Min15 disc | Min15 **held** | signals/day (Min30) |
|---|---|---|---|---|---|
| off | −0.171 | −0.122 | −0.227 | −0.182 | 1.79 |
| EMA 9 | −0.165 | −0.106 | −0.231 | −0.190 | 1.45 |
| **EMA 21** | −0.167 | **−0.073** | −0.222 | −0.181 | 1.29 |
| EMA 34 | −0.119 | −0.119 | −0.222 | −0.159 | 1.23 |
| **EMA 50 (shipped)** | −0.119 | −0.114 | −0.212 | −0.148 | 1.20 |
| EMA 100 | −0.141 | −0.137 | −0.232 | −0.123 | 1.15 |
| EMA 200 | −0.105 | −0.142 | −0.242 | −0.136 | 1.11 |

**The pre-registered bar was EMA 21 beating EMA 50 in all four panels. It wins
1 of 4.** Min30 held-out +0.040, and the other three go the other way.

### The ladder's shape is the actual evidence

The best arm is a **different length in every panel**: EMA 200, EMA 21, EMA 50,
EMA 100. That is the signature of a null variable — a real one produces the
same ordering twice.

The whole ladder spans 0.030–0.069 R against standard errors of 0.026–0.039, so
**no arm is more than about 1.5 SE from any other**, and EMA 21's best panel
(−0.073 vs off at −0.122) is +0.049 ± 0.044, or 1.1 SE.

**Turning the filter off entirely sits inside the spread in every panel.** It
is not measurably worse than any length, and it produces the most signals. The
filter costs 33% of them at EMA 50 and 38% at EMA 200 to buy nothing that can
be distinguished from zero.

This replicates `which_trend.py` exactly: the daily trend sorts at +4.5 SE, the
chart's own trend at −0.0 SE. `useLocalEmaFilter` is the chart's own trend, and
its length is a knob on a filter that does nothing.

### And no length is positive

Every one of the 28 cells is negative. The question "which EMA length" was
never going to be the one that changed the sign.

**No change recommended.** If the goal is fewer signals, EMA 50 already does
that and is as good as anything. If the goal is more signals, off is as good as
EMA 50. Neither choice is worth the time it takes to make.

---

## After the signal: an HTF bias, and waiting for an FVG — `research/studies/lez_entry.py`

Seven arms on the identical signal set (every signal kept only if the full
worst-case window exists, so no arm is scored on a population another had to
drop). Stop 1.5 × ATR from whatever the entry turns out to be, on every arm, so
`risk_pct` stays matched and the fee cannot pose as an edge.

### FIRST: MY BAR WAS WRONG AGAIN, AND FIVE ARMS "PASSED" IT

The pre-registered bar was *"beats `base` on R per signal in all four panels"*.
**`base` is negative, so beating it means losing less.** Five of six arms
cleared that, and not one of them is positive. This is the third time in this
sequence a bar has been set too weak, and it is recorded rather than quietly
restated: the bar should have been "positive in all four panels".

| arm | Min30 disc | Min30 held | Min15 disc | Min15 held | |
|---|---|---|---|---|---|
| + 4h bias | +0.134 | +0.019 | +0.059 | +0.037 | 4/4 |
| + daily bias | +0.084 | +0.049 | +0.079 | **−0.027** | 3/4 |
| FVG market | +0.036 | +0.026 | +0.093 | +0.030 | 4/4 |
| FVG retest | +0.063 | +0.071 | +0.158 | +0.098 | 4/4 |
| FVG retest + 4h | +0.114 | +0.017 | +0.149 | +0.084 | 4/4 |
| FVG retest + daily | +0.137 | +0.029 | +0.186 | +0.072 | 4/4 |

### THE FVG ARMS' GAIN IS ENTIRELY "NOT TRADING", AND THE ENTRY IS WORSE

The retest fills 54–58% of the time. Multiplying a negative mean by 0.56 makes
it less negative without anything having improved, so the gain was split into
**selection** (does waiting pick better signals?) and **entry** (is the limit at
the gap a better price than the close?), the second measured **paired on the
same signals**:

| panel | base, all | base, only the ones the retest filled | retest, those same signals | ENTRY, paired |
|---|---|---|---|---|
| Min30 disc | −0.122 | −0.084 | −0.108 | **−0.023 ± 0.045** |
| Min30 held | −0.114 | −0.042 | −0.078 | **−0.037 ± 0.044** |
| Min15 disc | −0.210 | −0.077 | −0.091 | **−0.014 ± 0.033** |
| Min15 held | −0.149 | −0.024 | −0.087 | **−0.063 ± 0.032 (−2.0 SE)** |

**The limit at the gap is a WORSE price than the close, in all four panels.**
The whole improvement is selection: +0.037, +0.072, +0.134, +0.125 — signals
that displace into a gap and then retrace it are better signals, and the arm
captures that by declining the other 45%.

That decides the operational question. LEZ produces 1.2–2.6 signals per symbol
per day across 60 symbols, so **signals are not scarce and R per trade TAKEN is
the metric that matters.** By that measure the FVG arms are worse: R per filled
trade is −0.108 vs base's −0.122 at Min30 discovery, and −0.087 vs −0.149 at
Min15 held-out only because of the same selection. Declining trades is not an
edge; it is doing less of a losing thing.

`mss_entry.py` found the market entry beat the gap limit on Riptide's signals.
This finds the same on LEZ's, from the opposite starting point.

### THE 4h BIAS IS THE ONE THING THAT SURVIVES A PROPER TEST

The table above compares each bias's own subset against everything, which
flatters any filter that removes anything worse than average. The test that
does not is **agree against AGAINST**, holding the entry constant — the shape
`which_trend.py` used:

| | Min30 disc | Min30 held | Min15 disc | Min15 held |
|---|---|---|---|---|
| **4h agree − against** | **+0.203 (2.5 SE)** | +0.029 (0.4) | +0.091 (1.6) | +0.055 (1.0) |
| daily agree − against | +0.138 (1.8) | +0.071 (0.9) | +0.129 (2.4) | **−0.039 (−0.7)** |

**4h holds its sign in all four panels. Daily flips at Min15 held-out.**

That daily fails here is not a surprise — `location.py` found the daily trend's
absolute lift did not survive its older half either, and this reproduces it
independently. That **4h passes where daily fails is new**: `which_trend.py`
tested the daily trend, and 4h has never been measured in this project. A
plausible mechanism, offered as a hypothesis rather than a finding: LEZ is a
15m/30m trigger, and a 4h bias is two timeframes away where a daily bias is
five — the daily narrative may simply be too coarse to say anything about the
next 48 hours on a 30m chart.

### But nothing is positive

The best cell in the entire study is `+ 4h bias` at Min30 discovery: **+0.012**.
Every other cell of every arm is negative. The 4h bias moves the strategy from
about −0.12 to about −0.10 and costs **66% of its signals** to do it.

### Verdict

- **The FVG retest is measured and it is worse.** The gap is a decent signal
  filter; the retest limit is a worse entry than the close. If you want the
  filter, keep the market entry.
- **The 4h bias is a candidate** — the only variable in nine studies to hold
  its sign on a proper agree-vs-against test across four panels. It is 1.0–2.5
  SE, not 3, and it does not make anything profitable.
- If it is ever added to the Pine it needs `request.security(..., lookahead_off)`
  with `[1]`, or it will repaint and every number here becomes meaningless.

---

## The author's own three filters — `research/studies/lez_strict.py`

The indicator's author, replying to a user asking how to raise the win rate:
*"increasing the Minimum Sweep Distance, increasing the Minimum Candle Range,
keeping the EMA Trend Filter enabled, using Strong Reclaim instead of Close
Back Inside, and requiring bullish/bearish confirmation bodies."*

The EMA is already measured and is a null (`ema_len.py`) and the confirmation
bodies are on by default, so this tests the other three. Forty cells, both
timeframes, window split.

**The bar is different this time and deliberately so.** Three studies in this
sequence used "beats the baseline", and all three were too weak: the baseline is
negative, so beating it only means losing less. Here the winning cell had to be
**POSITIVE on the held-out half**.

### Held out: both fail, and both are worse than shipping the defaults

| | winner | held-out R | shipped defaults, same half |
|---|---|---|---|
| Min30 | sweep 0.10 · range 0.50 · close-inside | **−0.140 ± 0.035** | −0.136 |
| Min15 | sweep 1.00 · range 1.20 · close-inside | **−0.177 ± 0.083** | −0.160 |

### One knob at a time — and the sweep distance is the lesson

Min30, R per signal:

| sweep distance | DISCOVERY (newer) | HELD OUT (older) | kept |
|---|---|---|---|
| 0.10 (ships) | −0.129 | −0.136 | 100% |
| 0.25 | −0.124 | −0.129 | 81% |
| 0.50 | −0.203 | −0.138 | 46% |
| 0.75 | −0.338 | −0.055 | 23% |
| **1.00** | **−0.392** | **+0.160** (42% win) | 11% |

**The ladder points in opposite directions on two adjacent 42-day windows.**
That `+0.160` at a 42% win rate is the only positive cell in the study, and the
discovery half scores the identical setting as **the worst of all forty**. On
the older data alone it looks like the discovery of the project; on the newer
data it is the single worst configuration available. It is noise with a 42% win
rate attached, and n = 195.

**Candle range** is flat — 0.50 marginally best on one panel, 1.20 best on
another, nothing outside the standard errors. **Strong Reclaim** is −0.016 on
Min30 and +0.006 on Min15: null, and it costs 7% of signals to be one.

### THE PLACEBO FLOOR, AND A CORRECTION TO IT

These filters do not change the entry, only which signals survive — so the
control is a filter keeping the same FRACTION of signals **at random**, and the
best of forty placebos is what best-of-forty is worth when the filtering is
known to carry no information.

| | median best-of-40 placebo | worst case over 25 seeds | best REAL cell |
|---|---|---|---|
| Min30 | **+0.050** | +0.123 | −0.109 |
| Min15 | **−0.094** | +0.012 | −0.142 |

**Neither timeframe's best real cell reaches its own placebo floor.** A filter
that throws away the same share of signals by coin toss does as well as the
best of the author's forty combinations.

> **The first version of this floor was one seed and returned +0.112.** That is
> about 3 SE above the population mean and roughly a 1-in-25 draw — the max
> across 25 seeds is +0.123, so the single seed had landed near the top of its
> own distribution. Reporting it as "the floor" would have been quoting one
> lucky sample as a constant, which is precisely the error the control exists
> to prevent. It is now the median of 25, with the max printed beside it.

### Verdict

**None of the three ships.** The author is right that they raise the win rate
(33% → 42% at the extreme) and right that they cut the signal count (1.21/day →
0.13/day), and right again in his own caveat that *"a higher win rate does not
always mean a better system"* — `winrate.py` measured exactly that. On this
data they raise the win rate and lose more money.

### An open question this cannot close

The author's reply also says to *"make sure the Pip Mode matches the market you
are testing."* **The source in this repo contains no occurrence of the string
`pip`.** Either the chart runs a different build or that advice concerns a
different script. Every LEZ measurement in this document describes
`liquidity-entry-zones.pine` as committed here, and until the version question
is settled the possibility that they describe the wrong source stays open.

---

## Liquidity Trendline With Signals, full universe — `research/studies/trendline_measure.py`

An exact port (`trendline.py`, tested by `research/test_trendline.py`) scored on
the universe Riptide actually scans: **60 symbols**, Min30 / Min15 / Min5, ~83
days each split in half. Market entry at the breakout close, 1.5 × ATR(14)
stop, MEXC fees. Answering the four questions an alerting service has to ask.

### The verdict, on the held-out half

| | signals | /symbol/day | win | **need** | R/signal | vs random |
|---|---|---|---|---|---|---|
| Min30 | 2012 | 0.81 | 33% | **36%** | **−0.120 ± 0.032** (−3.8 SE) | −0.001 (0.0 SE) |
| Min15 | 4331 | 1.73 | 31% | **37%** | **−0.216 ± 0.022** (−10.0 SE) | −0.047 (−1.9 SE) |
| Min5 | 12698 | 5.08 | 34% | **40%** | **−0.271 ± 0.013** (−20.5 SE) | +0.006 (+0.4 SE) |

**Fails the pre-registered bar at all three timeframes.** The bar was positive
at 2 SE; the result is negative at 4, 10 and 20 SE.

### WIN RATE — it is the coin flip's win rate, and it is below break-even

The `need` column is the win rate this configuration must beat to break even
after fees at that bucket's own risk. **The strategy sits 3 to 6 points under
it at every timeframe**, which is the whole loss.

And the random control's win rate is **33–34%** against the strategy's
**31–34%**. A trendline break produces the same win rate as entering at a
random bar in a random direction. That is what `EDGE ≈ 0` means in the last
column, and it is the single most compact statement of the result.

### RR — the ladder is flat, so the win rate is purely the target

Min15 held-out:

| target | win | R/signal |
|---|---|---|
| 1.5R | 40% | −0.210 |
| 2R | 31% | −0.216 |
| 3R | 24% | −0.216 |
| 4R | 19% | −0.225 |

The win rate moves 40% → 19% and R moves 0.015. Same shape at Min30 and Min5.
`winrate.py` again: the win rate is a dial the target sets, not a property of
the model, and no target rescues a signal with no edge.

### SIGNALS — far too many, before anything else is wrong

Per symbol per day, across 60 symbols:

| | /symbol/day | alerts per day, whole universe |
|---|---|---|
| Min30 | 0.81–0.88 | **~50** |
| Min15 | 1.73–1.80 | **~105** |
| Min5 | 4.95–5.08 | **~300** |

### QUALITY — nothing sorts, so no grade is possible

Five variables, all fixed before the run. High-minus-low, or agrees-minus-
against, across all six panels:

| variable | M30 disc | M30 held | M15 disc | M15 held | M5 disc | M5 held | |
|---|---|---|---|---|---|---|---|
| break distance | +0.060 | +0.104 | −0.012 | −0.055 | — | — | flips |
| channel age | +0.034 | +0.050 | −0.116 | +0.014 | — | — | flips, non-monotone |
| slope | +0.030 | −0.118 | +0.095 | −0.060 | — | — | flips |
| 4h agrees | +0.117 | **−0.066** | +0.092 | **−0.050** | +0.038 | +0.072 | flips on both held halves |
| daily agrees | **+0.276** | **−0.032** | +0.159 | +0.045 | +0.015 | −0.004 | collapses out of sample |

**Every one flips sign on at least one panel.** The daily-trend split is the
sharpest warning: **+0.276 on the Min30 discovery half and −0.032 on the
held-out half** — a variable that looks like the answer on the newer 42 days
and is nothing on the older ones.

This is the decision-relevant finding. **With no variable that sorts, there is
no grade**, and without a grade every alert must be sent or none of them can
be. Fifty to three hundred ungraded alerts a day is not an alerting service.

### Verdict

**Not a candidate.** It is not merely unprofitable — it is statistically
indistinguishable from random entry at two timeframes and significantly worse
at the third, while producing 50–300 alerts a day with nothing to rank them by.
The port is exact, tested, and the signal list is diffable against the chart,
so this is a measurement of the indicator rather than of a translation of it.

---

## The two survivors, on Riptide's own pipeline — `research/studies/riptide_filters.py`

Eleven studies left exactly two variables standing. Both are tested here on
**Riptide's actual signals with its actual entry and stop** — a limit at the
fair value gap, the stop beyond the raid extreme — because every earlier
measurement of them used a market entry with an ATR stop, which is not what
ships. 60 symbols, Min30 and Min15, ~83 days split in half.

### A. THE TREND INTERVAL — Hour8 passes, and it is NOT the 4h

Agree minus against, holding the entry constant. Four panels: Min30 discovery
and held-out, Min15 discovery and held-out.

| interval | conv | M30 disc | M30 held | M15 disc | M15 held | one sign | pooled |
|---|---|---|---|---|---|---|---|
| **Day1 (shipped)** | st | +0.107 | +0.035 | +0.060 | +0.070 | yes | +0.068 ± 0.042 (1.6 SE) |
| Day1 | st+di | +0.239 | +0.005 | +0.104 | +0.001 | yes | +0.083 ± 0.044 (1.9 SE) |
| **Hour8** | **st** | **+0.163** | **+0.168** | **+0.128** | **+0.074** | **yes** | **+0.127 ± 0.042 (3.0 SE)** |
| **Hour8** | **st+di** | **+0.182** | **+0.176** | **+0.127** | **+0.108** | **yes** | **+0.142 ± 0.045 (3.2 SE)** |
| Hour4 | st | +0.137 | +0.037 | −0.037 | −0.053 | **no** | +0.009 (0.2 SE) |
| Hour4 | st+di | +0.079 | −0.065 | +0.040 | −0.045 | **no** | +0.002 (0.0 SE) |
| Min60 | st | +0.078 | −0.009 | +0.128 | −0.031 | **no** | +0.043 (1.0 SE) |
| Min60 | st+di | −0.087 | −0.164 | +0.023 | +0.020 | **no** | −0.043 (−0.9 SE) |

**Hour8 is the only interval that holds one sign across all four panels, and it
does so under BOTH conventions.** That is the part that makes it hard to
dismiss as best-of-eight: a noise winner scatters across arms, and this one
does not. It beats Day1 in 4/4 panels on SuperTrend alone and 3/4 with DI, and
roughly doubles the shipped filter's sorting power.

**AND 4h FAILS — which corrects something this document said two studies ago.**
`lez_entry.py` found the 4h bias held its sign in all four panels and reported
it as the one variable still standing. That was measured on **LEZ's** signals
with a market entry and an ATR stop. On **Riptide's** signals with Riptide's
entry and stop, 4h flips on both Min15 panels and pools to +0.009, which is
nothing. The earlier result was not wrong about what it measured; it was wrong
as a guide to what would ship, and only testing the real pipeline showed it.

**Honest limits on the pooled figure.** The four panels are treated as
independent for inverse-variance pooling. The two window halves genuinely are
disjoint, but the same 60 symbols appear in Min30 and Min15, so a cleanly
trending symbol contributes twice and the 3.0–3.2 SE is optimistic. The claim
worth standing behind is the **sign consistency across four panels**, which is
what Hour4 and Min60 fail and which needs no independence assumption. The
individual panels are 1.7–1.8 SE each.

### B. `sweep_worth`'s DISTANCE UNIT — neither orders, percent keeps its seat

Expected R per RAID: conversion rate times what the setup earns, with a raid
that converts to nothing scoring 0.0 rather than being dropped — because the
filter gates whether to OPEN the chart, and a raid that produces nothing is the
cost of having opened it.

| distance % | conv | E[R]/raid, M30 | | distance ATR | conv | E[R]/raid, M30 |
|---|---|---|---|---|---|---|
| 0–1% | 20–32% | −0.019 / −0.037 | | 0–2 ATR | 34–36% | −0.078 / +0.000 |
| 1–2% | 14–16% | +0.011 / +0.004 | | 2–3.5 | 10–13% | +0.028 / +0.012 |
| 2–3% | 7–9% | +0.009 / +0.009 | | 3.5–6 | 1–2% | +0.003 / −0.004 |
| >3% | 1% | +0.003 / +0.003 | | >6 | 0–1% | +0.006 / +0.001 |

**Neither unit declines monotonically, in any half, on either timeframe. No
change to `sweep_worth`.**

The reason is the one `shift_distance.py` found and this confirms on the real
pipeline: **the nearest raids convert most often and are worth least.** A near
raid means the structure level is close, which means the setup that follows has
a tight stop, which means a large `fee / risk_pct`. That mechanism was first
seen with a synthetic 1.5 ATR stop and might have been an artefact of it. It is
not — Riptide's stop sits at the raid extreme and the same thing happens.

**What this does confirm is that the filter is doing its stated job.**
Conversion orders beautifully in both units, and ATR orders it more sharply
(34% → 0%) than percent (20% → 1%). `sweep_worth`'s docstring says it answers
"is this chart worth looking at", and conversion is the right metric for that.
It was never an expected-R filter and this settles that it should not be made
into one.

### The only shippable change to come out of eleven studies

`RIPTIDE_TREND_INTERVAL` from `Day1` to `Hour8`. It is a one-line environment
change, it is reversible, and `/stats` will score it forward. It has not been
shipped here: it should go through a held-out test on a window this study has
not touched, and the decision is the user's.

---

## HELD-OUT: does Hour8 replicate? — `research/studies/trend_holdout.py`

`riptide_filters.py` found Hour8 beat the shipped Day1 across eight arms. Eight
arms earns a confirmation, not a deployment. This file can only agree or
disagree with a prediction fixed before it was written: **Hour8's
agree-minus-against gap positive on both timeframes under both conventions,
and larger than Day1's in at least three of four.**

### FRESH WINDOW — days 83–166 back. PASSES, 4/4.

Nothing in this project had looked further back than 83 days. The engine runs
over the whole series so its warm-up and cluster state match live; only signals
landing in the older half are scored.

| | conv | agree | against | **gap** | SE | |
|---|---|---|---|---|---|---|
| Min30 Day1 | st | −0.143 | −0.026 | **−0.117** | 0.065 | −1.8 |
| Min30 Day1 | st+di | −0.092 | −0.080 | −0.012 | 0.072 | −0.2 |
| **Min30 Hour8** | st | −0.036 | −0.127 | **+0.091** | 0.065 | +1.4 |
| **Min30 Hour8** | st+di | +0.018 | −0.134 | **+0.152** | 0.072 | +2.1 |
| Min15 Day1 | st | −0.043 | −0.087 | +0.045 | 0.052 | +0.9 |
| Min15 Day1 | st+di | −0.058 | −0.067 | +0.009 | 0.056 | +0.2 |
| **Min15 Hour8** | st | −0.005 | −0.124 | **+0.119** | 0.052 | +2.3 |
| **Min15 Hour8** | st+di | +0.049 | −0.129 | **+0.178** | 0.056 | +3.2 |

**All four Hour8 cells positive. Beats Day1 4/4.** 3,442 setups.

Shrinkage is there and is expected: pooled +0.127/+0.142 on discovery against
+0.091 to +0.178 here. The sign held, which was the test.

**The sharper finding is what Day1 did.** On this window the shipped filter
went **negative on Min30 SuperTrend (−0.117, −1.8 SE)** — setups agreeing with
the daily trend scored *worse* than those against it. Hour8 stayed positive on
the same setups in the same window. `location.py` had already found the daily
trend's absolute lift did not survive its older half; this is the same thing
appearing in the relative split, on Riptide's own signals.

### SYMBOL HOLD-OUT — NOT AVAILABLE, and the first run mis-reported it

The plan was ranks 61–120 by turnover. **`list_symbols` applies Riptide's
`TOP_N = 60`, so `allsyms[60:120]` was an empty list and the set never ran** —
and the script printed **"symbols FAIL"** for a test that had not happened. A
missing test reported as a failed one, which is worse than either.

Rebuilt with the cap lifted, the answer is that the test cannot be run at all:
`MIN_VOL_USDT = 3,000,000` leaves roughly **65** tradeable perpetuals in total,
so past rank 60 there are **5** names. There is no second universe to hold out.
The script now reports this as an ABSENT test and refuses to fold it into the
verdict.

So the window hold-out carries this alone, and the generality-across-instruments
question stays open rather than answered.

### Where this leaves the change

**CORRECTION — it is TWO settings, not one.** `grade_of` requires the
SuperTrend *and* the DI to agree, and they read different config keys:
`TREND_INTERVAL` (the SuperTrend) and `DI_INTERVAL` (the DI), both defaulting
to `Day1`. Setting only `RIPTIDE_TREND_INTERVAL=Hour8` therefore produces
SuperTrend on 8h ANDed with DI on the daily — **a mixed combination that was
never measured.** The tested `Hour8 st+di` arm needs BOTH
`RIPTIDE_TREND_INTERVAL=Hour8` and `RIPTIDE_DI_INTERVAL=Hour8`. Reversible
either way, and `/stats` scores it forward.

For it: discovered on eight arms and confirmed on a window it was not found on,
positive in 8 of 8 cells across discovery and hold-out, under both conventions,
beating the incumbent in 4/4 on the held-out set — while the incumbent itself
turned negative there.

Against it: individual cells are 1.4–3.2 SE, not overwhelming; the pooled
figures lean on treating two timeframes over the same symbols as independent,
which they are not; and no symbol hold-out was possible, so this is one
regime-generality test rather than two.

Still not shipped. The evidence supports it and the decision is the user's.

---

## HalfTrend Long/Short Signal Engine — `research/studies/halftrend_measure.py`

A separate strategy, kept separate: it shares the candle fetcher and
`research.harness` and nothing else. No cluster, no POI, no grade, no
`sweep_worth`. 60 symbols, Min30 / Min15 / Min5, ~83 days split in half.

Brought in on a chart reading **">60% win rate with 1:3 RR"**.

### FIRST: repaint and lookahead — the engine is CLEAN

`buySignal` carries `barstate.isconfirmed`, so a signal exists only on a closed
bar. `ta.highestbars`, `ta.lowestbars`, `ta.sma` and `ta.atr` all read backwards
only. The single `request.security` feeds the multi-asset dashboard, not the
signal, on `timeframe.period` with v6's default `lookahead_off`. The trend state
machine is path-dependent but never forward-looking.

**The 60% is not a repaint. It is the scoreboard's arithmetic.**

### THE SCOREBOARD, reproduced and then decomposed

The port reproduces the chart exactly — 64.00% on ETH 30m — which is how the
counter port was verified. Over the whole universe:

| | dashboard says | never hit TP1, stopped | **hit TP1 then stopped** | hit TP3 |
|---|---|---|---|---|
| Min30 | 1803W / 1182L = **60.4%** | 1173 (52%) | **514 (23%)** | 513 (23%) |
| Min15 | 3467W / 2533L = **57.8%** | 2503 (53%) | **1160 (25%)** | 1028 (22%) |
| Min5 | 12087W / 7932L = **60.4%** | 7748 (52%) | **3631 (24%)** | 3543 (24%) |

Read the Min30 row as arithmetic: 513 runners counted three times each is 1539
of the 1803 "wins". The 1182 "losses" is almost exactly the 1173 that never
touched TP1. **The 514 trades that reached TP1 and then stopped out appear in
neither column** — `longTPHit1` makes the stop subtract one from *both*
counters. That is 23% of all trades, and it is the worst-behaved 23%, removed.

The third effect is quieter and equally real: the panel prints
`Target R:R  1 : 3` while crediting the win at **TP1, one risk unit away**.

*(Caveat on the bucket counts: the dashboard tracks a trade until it stops,
reaches TP3, or a new signal overwrites it, while the decomposition uses a 48h
horizon. The counts are approximate at the margins — but 1173 against 1182 on
the loss column shows the erasure is not.)*

### THE HONEST SCORE — each trade counted once

Held-out halves, market entry at the flip close, stop `3 × ATR(100)/2`, fees:

| | 1R win | 2R win | **3R win** | R/signal at 3R | control | EDGE |
|---|---|---|---|---|---|---|
| Min30 | 49% | 32% | **24%** | **−0.127 ± 0.052** (−2.5 SE) | −0.116 | −0.011 (−0.2 SE) |
| Min15 | 46% | 29% | **22%** | **−0.277 ± 0.035** (−7.9 SE) | −0.210 | −0.067 (−1.7 SE) |
| Min5 | 48% | 32% | **24%** | **−0.321 ± 0.020** (−16.0 SE) | −0.275 | −0.046 (−2.0 SE) |

**Fails the pre-registered bar at all three timeframes.**

**The win rate at the 3R it advertises is 22–24%, not 60%.** At 1R — where the
dashboard actually credits its wins — it is 46–49%, and even that is below the
break-even a 1R target needs after fees.

The EDGE row is the other half: **−0.011, −0.067, −0.046 against random entries
of the identical shape.** Indistinguishable from a coin toss at Min30, worse at
the other two.

### Verdict

Not a candidate. The signal engine is honest — no repaint, no lookahead, and
the flips are real trend flips. What is not honest is the number on the panel,
and it is wrong in three compounding ways that together turn a 22% win rate at
3R into a printed 60%.

**The general lesson, which is the one worth keeping:** an indicator that
computes its own performance is reporting the author's accounting, not the
strategy's. This is the second indicator in this sequence whose on-chart
scoreboard could not show a loss — Liquidity Entry Zones deleted stopped
trades' drawings, this one deletes them from the arithmetic. Neither was
dishonest by intent and both were wrong by the same margin.

---

## The same trendline break as a HEADS-UP — `research/studies/trendline_rate.py`

The measurement above killed the trendline break as a *trade*. It says nothing
about the break as a *watch list*, which is a different product that fails for
a different reason: **a heads-up fails by arriving too often to read**, not by
losing money. An alert you scroll past is worse than no alert, because it also
buries the ones you would have opened.

So this counts, and nothing else — no outcomes, no R, no win rate. Those exist
already and they say do not trade it.

60 symbols, the same universe Riptide scans.

| timeframe | days | breaks | per symbol/day | **across the universe** | worst single close |
|---|---|---|---|---|---|
| Min15 | 83 | 9101 | 1.82 | **109 a day** | 29 at once |
| Min30 | 83 | 4333 | 0.87 | **52** | 21 |
| Min60 | 83 | 2087 | 0.42 | **25** | 16 |
| Hour4 | 333 | 2194 | 0.11 | **7** | 20 |

**Hour4 is the only readable rate**, and 15m — the timeframe the indicator
looks best on, and the one it is most tempting to set this to — is a feed at
109 a day rather than an alert.

### Alerts arrive in BURSTS, and that changed the design

The first version of this script reported a *median gap between alerts* and got
**0 minutes**, which is not a measurement of anything. Of course it is zero:
bar closes are synchronised across the universe, so breaks do not arrive spread
out, they arrive **together**. The number a reader actually feels is how many
land at once, so that is what the table reports — and the worst single 4h close
in the window had **20 symbols break simultaneously**.

Twenty separate Telegram messages in one second is unreadable and is past
Telegram's per-chat rate limit, and it would happen precisely during a
market-wide move, which is the one time the alert was worth having. So
`riptide/watch.py` sends **one digest per bar close** rather than one message
per break, and a quiet close sends nothing at all.

---

## Does the SLOPE of the broken line separate anything? — `research/studies/trendline_slope.py`

Asked because the natural reading of the chart says it should: a steeply
descending resistance broken upward is a trend changing, while a nearly **flat**
line is just a horizontal level, and price crossing a horizontal level is the
most ordinary thing a chart does.

Not the trading question — that is settled and the answer is no. This asks the
weaker thing a heads-up actually promises: after the alert, did the chart **do**
anything? Continuation over the next 8 bars, against a known null of 50%.
No fees, no stop, no R.

Steepness is `|slope| / ATR(200)` at the break, so a 100000-dollar chart and a
0.008-dollar one are on the same scale. 9082 breaks at Min15, 4327 at Min30.

### The pre-registered test failed, and it failed in the most instructive way

Quartiles cut on the **discovery** half, read on the **held-out** half:

| | flat quartile | steep quartile | difference | |
|---|---|---|---|---|
| Min15 discovery | 43.4% | 52.4% | **+9.0pp** | **+4.4 SE** |
| Min15 **held out** | 46.0% | 43.0% | **−3.1pp** | −1.4 SE |
| Min30 discovery | 43.3% | 45.2% | +1.8pp | +0.6 SE |
| Min30 **held out** | 43.8% | 44.0% | +0.2pp | +0.1 SE |

The discovery half says steep breaks continue nine points more often at 4.4 SE.
That is a publishable-looking number. **The held-out half reverses the sign.**

This is the cleanest example in the whole file of why the discovery/held-out
split is not a formality. Nothing about the +4.4 SE looked like noise from
inside the discovery half — the n was 2367, the effect was large, and the story
was one a trader would nod along to. It was noise.

If anything the lean is the *other* way. MFE − MAE on the held-out half:

| | Min15 | Min30 |
|---|---|---|
| flat | +0.132 ± 0.072 ATR | +0.345 ± 0.249 |
| steep | **−0.288 ± 0.080** | **−0.205 ± 0.107** |

Steep breaks' adverse excursion grows faster than their favourable one, on both
timeframes, held out (−3.9 SE and −2.0 SE). A steeply falling resistance broken
upward looks like a violent counter-trend pop that gets sold. Reported as a
lean rather than a finding: it was not the pre-registered primary, and MFE−MAE
is a statistic that inflates with volatility on both sides.

### Continuation is BELOW the coin flip at every threshold

44–48% on both halves at every cut from 0.00 to 0.30, at both timeframes. These
breaks very slightly **mean revert**. That is the fourth independent
measurement in this project pointing the same way, and it is why the digest says
"not a trade" in the message itself.

### What the slope gate is actually for

Volume, and it is labelled as volume:

| `\|slope\|/ATR ≥` | kept | alerts/day at 15m+30m |
|---|---|---|
| 0.00 | 100% | 161 |
| 0.05 | 68% | 110 |
| 0.10 | 39% | 63 |
| **0.15** | **20%** | **32** ← default |
| 0.20 | 10% | 16 |

That is what makes 15m+30m readable at all, and it is the only claim made for
it.

---

### What shipped

`RIPTIDE_TRENDLINE_ALERTS=1`, `RIPTIDE_TRENDLINE_INTERVALS=Min15,Min30`,
`RIPTIDE_TRENDLINE_MIN_SLOPE=0.15` — about 32 a day. Live-settable with
`/trendline 15m,30m` and `/trendline slope 0.2`. A 30m close is also a 15m
close, so both land in one digest and a chart that broke on both is listed
once, on the slower one — with its timeframe on the line, always, since that is
the tag that answers "which chart am I opening". No entry, no stop, no grade, and deliberately **not armed
for outcome tracking** — /stats exists to judge trades, and a heads-up has no
outcome to judge. The measurement above is why the message says, in the
message, that it is not a trade.


---

## Was the raid FINISHED when the early fired? — `research/studies/early_raid.py`

Prompted by a live observation: the early sometimes fires and *then* the sweep
runs further, taking out a stop frozen at `grab_low - sl_buffer`. The mechanism
is real and visible in the code — the early takes the FIRST imbalance within
`early_max_bars` and nothing asks whether the raid has stopped extending.

Four ways of asking, all of them geometry the engine already computes and
throws away. 1399 early signals, baseline **+0.007 ± 0.033 R**. Bar is
`harness.report`'s: 3 SE, monotone, same sign on every split.

| | top−bottom | | verdict |
|---|---|---|---|
| 1. reclaim of the swept level, in ATR | −0.023 ± 0.089 | −0.3 SE | rejected, not monotone |
| 3. where the raid bar CLOSED vs the level | −0.001 ± 0.086 | −0.0 SE | rejected, not monotone |
| 4. bars from sweep to gap | −0.280 ± 0.239 | −1.2 SE | rejected, not monotone |
| 2. next bar made a new raid extreme | — | — | only 20 rows in one bucket |

Every one of them flips sign between window halves — reclaim runs −0.229 then
+0.155, grab-close −0.225 then +0.189, bars-from-sweep +0.232 then −0.646. That
is the signature of noise, and it is the same shape that produced +4.4 SE on
one half of the trendline slope study and the opposite sign on the other.

### The finding is in what did NOT need a filter

**The described failure happens 26% of the time and does not cost anything.**
365 of 1399 early signals formed their gap while price was still beyond the
swept level — a bounce inside an unfinished raid, exactly as described. Those
score **+0.056 ± 0.065**, slightly BETTER than the +0.007 baseline. The thing
that looks broken on a chart is not the thing losing money.

**What does kill a trade is rare and cannot be filtered.** When the very next
bar makes a new raid extreme, the trade returns **−1.112 ± 0.019** — a full
stop plus fees, essentially deterministic. But it is only **20 of 1399 (1.4%)**,
worth +0.016 R per signal if every one could be avoided.

And it cannot be, for two independent reasons:

**It is circular.** The stop sits just beyond the raid extreme, so "the next bar
makes a new raid extreme" is very nearly a restatement of "the stop was hit".
The −1.112 is not a prediction, it is the loss being observed.

**Acting on it means waiting a bar, and waiting costs more than it saves.**
Re-simulated with the limit at the same gap price and the fill window starting
one bar later:

| | R/signal | n |
|---|---|---|
| unfiltered, every early | +0.007 ± 0.033 | 1399 |
| filtered, entry unchanged (not actionable — uses the next bar) | +0.023 ± 0.033 | 1379 |
| **filtered, entry DELAYED one bar** | **−0.041 ± 0.032** | 1379 |

Net **−0.048 ± 0.046, −1.0 SE: worse than doing nothing.** The 22 R saved by
skipping 20 dead trades is more than given back in fills lost on the other
1379 — the limit at the gap edge often fills on the very next bar, and a delay
forfeits those.

Nor can the order simply be cancelled on a new extreme instead of delayed: for
a long, the gap edge sits ABOVE the raid low, so price making a new low has
already traded through the entry. The fill always happens first.

### Verdict

No change. The early trigger stays as it is. The mechanism is real, common, and
harmless; the version that hurts is rare, near-tautological, and costs more to
avoid than it takes.


---

## Open interest — the data is verified, the sample is not there yet

First export of the `market` table: **6328 rows, 94 symbols, 2.8 days**. Far
too little to test anything, but exactly enough to check the logger is
recording something worth accumulating — which is the higher-value question at
this stage, because a subtly broken logger would waste the next six weeks.

### The logger is sound

| check | result |
|---|---|
| distinct bars in the span | 134, every step exactly 1800s — **no missed snapshots** |
| aligned to the Min30 grid | yes |
| OI series frozen or stale | **0 of 23** long series |
| bars moving OI by >0.5% / >2% | 72% / 31% |
| `hold_vol <= 0` | 0 rows |
| funding | 336 distinct values, 0.5% exactly zero |

**The number that mattered most: correlation of OI change with PRICE change is
+0.038** (median over 23 symbols, p10 −0.270, p90 +0.231). If OI merely tracked
price it would be another OHLC rearrangement wearing a disguise, and thirteen
families of those have already died here. It does not track price. It is
genuinely separate information.

### One real defect found, and fixed

`market.snapshot` filtered the ticker response down to the currently-scanned
symbols. The response carries **1196 contracts** and 1136 were being discarded —
from a request that was already being made.

Worse than waste: the scanned set is the top `TOP_N` by turnover refreshed every
six hours, so symbols near that line rotate constantly. The export showed 94
distinct symbols but **only 20 with more than 95% bar coverage**. Short broken
series are close to worthless here, because the tested quantity is the *change*
in OI across the raid, which needs the previous bar too.

Now logs every contract above `RIPTIDE_MARKET_MIN_VOL` (1M, a third of the scan
threshold), plus the scanned set unconditionally. **180 symbols instead of 60**,
same single request, no rotation holes, and history already in place for a
symbol on the day it rotates into the scanned set.

### When it becomes testable

128 of 1399 backtest early signals joined to an OI reading on both the raid bar
and the one before — **97% of those whose raid fell inside the window**, so the
join itself is clean. 46 usable signals a day.

Per-signal spread is 1.234 R, so at the 3 SE bar:

| detectable difference | signals needed | days from the 2.8-day export |
|---|---|---|
| 0.30 R | 305 | 4 |
| 0.20 R | 685 | 12 |
| 0.15 R | 1218 | 24 |

Discovery numbers; a held-out half doubles every row. So a properly held-out
test of a plausible effect is **4 to 8 weeks out**, matching what `market.py`
predicted when it was written.

### The analysis was pre-registered before the data existed

`research/studies/oi_raid.py` was written and committed while the table held
2.8 days — direction, buckets, bar and all. Falling OI across the raid must
score **better** than rising; a result the other way is a failed test, not a
discovery.

It also **refuses to print a verdict below 610 joined signals** and prints the
countdown above instead. That refusal is the point: the trendline slope study
produced +4.4 SE on one half of its data and the opposite sign on the other, and
the only reason it was caught is that nobody was permitted to act on the first
half. This removes the temptation mechanically rather than relying on
discipline.


---

## A trendline as the stop — `research/studies/trendline_stop.py`

From a live TAO trade: early alert filled on the retest, an ascending Liquidity
Trendline support underneath, stop parked under the line and dragged up with it.
It worked. One winning trade is the weakest evidence for a rule and the best
reason to test one, because the rule is specific enough to be wrong measurably.

**Three claims were bundled together and only two are testable.**

### A — "I entered on the FVG retest" is already what the bot does

Early signals enter with a LIMIT at the gap edge; the scorer fills only when
price returns to touch it. The retest *is* the fill. Nothing to change.

### Coverage settles a lot of it: 18%

Only 699 of 3,900 early signals across the full 60-symbol universe had a live
trendline on the correct side of the trade at entry. **The rule applies to
roughly one trade in five**, so whatever it does, it cannot move the aggregate
much. The TAO trade was one of that fifth, and it won.

### B — "stop under the line" is not a trendline effect, it is a wider stop

| | risk | win | full SL | R/signal | vs plain |
|---|---|---|---|---|---|
| plain fixed stop | 1.78% | 41% | 58% | +0.067 | — |
| **B  stop at the line** | **3.10%** | 44% | 48% | +0.020 | −0.6 SE |

The line sits **74% further from entry** than the raid extreme. A stop is
one-dimensional — same risk means same price — so there is no separate control
to run: arm B *is* "use a much wider stop", and the drop in stop-outs is
mechanical rather than structural. A wider stop was already tested in
`stops.py` (the risk floor: inverted U, not supported), and here it costs net R
in all three panels.

### C — the actual idea, trailing up the line, is a wash

Initial risk unchanged, so this is a clean exit-management comparison.

| | win | full SL | R/signal | vs plain |
|---|---|---|---|---|
| all, plain | 41% | 58% | +0.067 | — |
| all, trailed | 36% | 51% | +0.065 | **−0.0 SE** |
| discovery, trailed | 35% | 54% | +0.005 | −0.1 SE |
| **held out, trailed** | 37% | 47% | +0.155 | **+0.1 SE** |

**No arm beats the plain stop anywhere.** On a first pass with the 23-symbol
corpus the held-out half showed +0.092 for the trail; widening to 60 symbols
shrank it to +0.014, which is what noise does when it gets more data.

### What DOES replicate, in all three panels

**Full stop-outs fall — 58% → 51%** (55% → 47% held out). That is real and it
is what the idea was reached for.

**But the win rate falls with it — 41% → 36%.** A trailed-out trade exits at a
scratch or small loss instead of running to target, and a scratch is not a win.
This is precisely the mechanism `stops.py` documented for break-even: it "cuts
full losses but LOWERS the win rate". Net R is unchanged because the two cancel.

### My own pre-registered expectation was half wrong

Recorded before the run: *"the trail raises the win rate, cuts full stop-outs,
and loses net R."* Actual: it **lowers** the win rate, cuts full stop-outs, and
costs **nothing**. Two of three wrong, in the direction of my own prior being
too pessimistic about R and too optimistic about the win rate.

### Verdict

Not adopted, and not because it is harmful — because it is free and does
nothing. If fewer full stop-outs is worth a lower win rate to trade
comfortably, the trail costs no measurable R and that is a legitimate
discretionary reason to use it on the ~18% of setups where a line exists. It is
not an edge, it should not be automated, and it should not be expected to
improve returns.

For the win rate specifically, `stops.py` already found the better instrument:
a partial at 1R took LEZ from 33% to 50% win and 66% to 50% full stop-outs for
0.007 R.


---

## Sweep + FVG + a trendline BREAKOUT agreeing — `research/studies/early_breakout.py`

The one confluence question nobody had asked. Every filter tried on this
population — POI, trend, volume, RSI, ADX, reclaim, raid depth, grab close —
describes the **setup**. This describes something else that happened on the same
chart at roughly the same time and points the same way: **two independent
constructions agreeing**.

No lookahead: a break counts only if it fired at or before the early signal's own
bar. Both series come from closed bars on the same candles.

### It FAILS the pre-registered bar

| panel | n with | WITH | without | difference | |
|---|---|---|---|---|---|
| all early | 128 (3%) | +0.183 | −0.022 | **+0.206** | +1.9 SE |
| discovery | 68 | +0.246 | −0.032 | +0.279 | +1.9 SE |
| **held out** | **60** | +0.112 | −0.011 | **+0.123** | **+0.7 SE** |

The bar was 2 SE on the held-out half. It got +0.7 SE on 60 trades. **Not
adopted.**

### But it is the most consistent shape found on this population

- **Positive in every panel it could be computed in** — five of five.
- **Clears the placebo floor everywhere.** 25 random subsets of the same size
  give +0.018 (all), +0.003 (discovery), +0.005 (held out); the real filter beats
  those by +0.165, +0.243 and +0.107. So it is not merely "a small slice of a
  noisy population".
- **Replicates on an independent signal type.** Confirmed setups — a different
  signal, needing the structure shift the early does not — give **+0.154 at
  +1.0 SE**, same sign, also above its placebo floor. Its held-out half has only
  18 qualifying trades, too few to score.
- **The window curve decays the way a real recency effect would:**

| window | kept | difference |
|---|---|---|
| 3 | 1% | +0.126 |
| 5 | 2% | +0.178 |
| **10** | **3%** | **+0.206** |
| 20 | 10% | +0.052 |
| 40 | 26% | −0.002 |

10 was fixed in advance as `CFG.early_max_bars`, not chosen from this table.

### The evidence against it, stated plainly

**The opposite-direction break does nothing.** −0.021 (all), −0.050 (discovery),
+0.016 (held out). If agreement helps, disagreement should hurt. It does not,
and that is a real argument that the positive side is noise.

**Coverage is 3%.** Even if entirely real, this fires on about one early signal
in thirty-three — roughly one a day at current alert volume.

### Verdict: do not filter, start measuring

At +0.7 SE held-out on n=60 this is an encouraging shape, not evidence, and
acting on it would be exactly the mistake the trendline slope study demonstrated
(+4.4 SE on one half, opposite sign on the other).

But the forward sample is the only thing that can settle it and it accrues at
about one signal a day, so the clock is worth starting — the same reasoning that
justifies the open-interest logger. Tagging alerts that have the confluence, and
letting `/stats` score the tag forward, changes nothing that is sent and costs
one extra computation per symbol per scan on candles already fetched.


---

## "Support and Resistance Levels with Breaks" — `research/studies/srbreak_measure.py`

Ported exactly (`srbreak.py`). The reason to measure it is a genuine collision:
**Riptide and this indicator are opposite bets on the same candle.** Riptide
sees price take out a pivot low and reads a raid — reversal, long. This reads
close crossing under a pivot low on expanding volume and calls it a breakdown —
continuation, short.

And the collision is not open in the abstract. `context.py` already measured
sweep-to-setup conversion against raid volume over 7869 sweeps: **26.4% for the
quietest quintile down to 6.5% for the loudest, monotone, +15.6 SE.** Loud raids
are breakouts. That is this indicator's premise, arrived at independently, and
it is the strongest single result in this file. So the promising use was never a
new strategy — it was a **negative filter** on Riptide.

### Three things about the indicator itself, before any numbers

**The lines are drawn 16 bars to the left of where they became knowable.**
`plot(..., offset = -(rightBars+1))`. `pivothigh(15,15)` is `na` until 15 bars
after the pivot, plus one for the `[1]`. The *signal* is honest and
non-repainting; the *picture* makes every break look like a break of a level
that was already sitting there. It was not.

**A quiet, clean break prints nothing at all.** The clean label needs `osc > 20`;
the wick labels do not test volume. A break that is neither wicky nor loud falls
through every branch and leaves no mark — easy to read as "that never happened".

**The alerts and the arrows are different conditions.** `alertcondition` tests
only the cross plus `osc > threshold` — no wick test. Wiring those alerts up
subscribes you to something other than what you see.

### Nothing passes

**As a trade of its own** — market at the close, 1.5 ATR stop, 2R, MEXC fees:

| | n | win | R/signal |
|---|---|---|---|
| clean break | 897 | 34% | **−0.097 ± 0.048** |
| wick break | 310 | 35% | −0.057 ± 0.082 |

The fifth indicator in this file to fail as a standalone. Note it is *not* a
free +0.097 to fade: the stop and target are asymmetric and both sides pay fees.

**As a negative filter** — the pre-registered primary. Early signals with a
contradicting clean break in the preceding 10 bars:

| panel | n | R | vs the rest | |
|---|---|---|---|---|
| all early | 394 (10%) | −0.026 | −0.011 ± 0.062 | −0.2 SE |
| **held out** | 197 | −0.086 | **−0.087 ± 0.084** | **−1.0 SE** |

The held-out half leans the predicted way — contradicted signals do worse, win
rate 25% against a 30% baseline — but at −1.0 SE, and the all-panel is flat.
**Fails.**

**As confluence, the sign flips between populations.** An agreeing clean break
scores **−0.058 on early** and **+0.177 on confirmed** (+1.3 SE, n=73). A
mechanism does not help one signal type and hurt the other; noise does exactly
that. The wick arms are all under 50 rows and say nothing.

### Verdict

Not adopted in any of the three roles. Coverage was reasonable (10% for the
contradicting arm, unlike the trendline confluence's 3%) and the direction on
the held-out half was the predicted one, which is more than most — but −1.0 SE
with a flat aggregate is not a finding.

**The premise it shares with the +15.6 SE conversion result still stands. This
particular formalisation of it does not sort R.** Which `context.py` had already
warned about from the other side: it found a huge effect on conversion and none
on expectancy, and those are different questions.


---

## RSI divergence — `research/studies/divergence.py`

### The strategy that prompted it is not measurable from its own tester

Reported: **+213.92%, 64.04% wins, profit factor 1.561**, 89 trades, BTC 15m.
The settings say otherwise, and this is arithmetic rather than opinion:

**Leverage.** `default_qty_value=2, strategy.fixed` on BTC near 78,000 is a
**$157,000 position on $10,000** — 15.7x, up to 31.4x with `pyramiding=2`. The
62.54% max drawdown is the leverage, not the edge.

**No fees, no slippage.** The `strategy()` call sets neither. Average profit is
$240 a trade = **0.153% of notional**, against a MEXC round trip of 0.08–0.12%:

| | net PnL | profit factor |
|---|---|---|
| as shown | +214% | 1.561 |
| at 0.08% | +102% | 1.207 |
| at 0.12% | **+46%** | **1.084** |

Two thirds to four fifths of the result is the fee it was never charged.

**Long only, and `Buy and hold` is toggled off** in the screenshot — the one
comparison that would separate the strategy from the rally it ran through.

**No stop.** `sl_type` defaults to `"NONE"`, so a losing long is held until RSI
crosses 80 or a bear divergence prints. That is what makes the win rate 64%, and
the tester says so itself: **average win $1,044 against average loss $1,192**, a
ratio of 0.88. Wins smaller than losses is the signature of a no-stop system.

**The author publishes different tuned parameters per symbol** in the header
comments — GOOGL 5/3/1, SPY 5/3/3. Curve fitting, stated openly.

### The concept was still worth one measurement

`context.py` had tested RSI *extension* at the raid (+0.025, +0.4 SE, dead).
Extension is "RSI is far from 50"; **divergence is a relationship between two
series** and had never been tested here. Author's parameters kept exactly: RSI 9,
pivots 1/3, previous pivot 5–60 bars back.

**As a trade of its own** — market at the confirming close, 1.5 ATR stop, 2R,
MEXC fees:

| | n | win | R/signal |
|---|---|---|---|
| regular divergence | 1394 | 32% | **−0.144 ± 0.038** (−3.8 SE) |
| hidden divergence | 2944 | 34% | **−0.097 ± 0.026** (−3.7 SE) |

The sixth indicator here to fail standalone, and the most decisively negative of
them.

**As a filter** — the pre-registered primary was an agreeing regular divergence
on early signals, held out, at 2 SE:

| panel | n | vs the rest | |
|---|---|---|---|
| early, all | 354 (9%) | −0.055 | −0.8 SE |
| **early, held out** | 150 | **+0.028** | **+0.3 SE** |
| confirmed, all | 74 | **−0.235** | **−1.7 SE** |

**Fails.** The sign flips between the halves on early, and the largest number in
the table — agreement making confirmed setups *worse* at −1.7 SE — points the
opposite way to the concept. A contradicting divergence came out mildly positive
(+1.2 SE all, +0.5 SE held out), which is backwards and is how noise looks.

### Verdict

Not adopted in any role. RSI is the most-tested oscillator in existence and this
population has now rejected both its level form and its divergence form.


---

## Sweep volume as the heads-up gate — `research/studies/sweep_vol_gate.py`

**The largest result in this file went unused for months.** `context.py` found
sweep→setup conversion falling 26.4% → 6.5% with raid volume, +15.6 SE. It
survived only as a paragraph in `market.py`.

Reproduced independently on 9,419 sweeps, 60 symbols, 42 days:

| quintile | rvol | converts |
|---|---|---|
| Q1 | < 0.98 | **14.3%** |
| Q2 | 0.98–1.55 | 9.7% |
| Q3 | 1.55–2.37 | 6.1% |
| Q4 | 2.37–4.12 | 4.6% |
| Q5 | > 4.12 | **2.4%** |

**Q1 − Q5 = +11.9pp, +13.5 SE, monotone.** It inverts the folk premise: the
raids that reverse are the **quiet** ones. A volume spike through a level is a
breakout with participation; the grab that snaps back drifts through on thin
trade.

### Head to head against the gate it replaces

| gate | converts | per symbol-day | share kept |
|---|---|---|---|
| every sweep | 7.4% | 3.8 | 100% |
| distance <3% (the old live rule) | 13.3% | 1.7 | 46% |
| **volume only** | **14.3%** | **0.8** | 20% |
| **both** | **18.0%** | **0.5** | 13% |

**Volume alone beats distance on both axes — higher conversion at half the
messages.** Together they more than double the ungated conversion rate at an
eighth of the traffic. Shipped: `sweep_worth` is now an AND of three, and live
it takes sweeps through the gate from 48% to 18%.

Not an edge claim. `context.py` measured raid volume against R on the setups
that follow and found nothing (+0.7 SE). Conversion and expectancy are
different questions; a heads-up is asked only the first.

---

## Breadth — `research/studies/breadth.py`

The one axis a per-symbol study structurally cannot contain. This project had
already pointed at it: *"27% of confirmed losers fall on five days out of
forty-two ... nothing about a single alert can see it coming."* A single alert
cannot. **A cycle can** — when the scanner sends the seventh long it already
holds the other six.

It gets wide often: **33% of signals arrive with 8+ same-direction signals on
the same close**, widest 32.

### Early signals, held out — the pre-registered panel

| | n | win | R/signal |
|---|---|---|---|
| alone | 343 | 28% | −0.065 |
| 2–3 together | 568 | 29% | −0.033 |
| 4–7 together | 426 | 28% | −0.102 |
| **8+ together** | 429 | **34%** | **+0.122** |

**+0.187 over "alone", +2.1 SE**, above a 25-seed placebo floor, and +2.1 SE
again on the full panel in the same direction. The win-rate step 28% → 34%
repeats in both halves.

**It still FAILS**, and on the term that was fixed in advance: the
pre-registration required the gradient to be **monotone** and it is not — 4–7
is the *worst* bucket and 8+ the best. This is a threshold at 8, not a slope,
and a threshold that appears at one of four pre-chosen edges is exactly what a
single lucky bucket looks like. Confirmed setups show nothing (+0.2 SE held
out).

**Shipped as a printed fact, not a filter.** The alert now says "9 longs on this
close — size them as one bet", because that is true regardless of the R, and it
is the fact behind 27% of the losses. `/stats` scores it forward.

**Direction, for the record:** of the two outcomes written down in advance,
high breadth came out **better**, not worse — a genuine market-wide move rather
than a correlated bundle about to snap. That is the opposite of what the
drawdown work would have suggested, and it is why the position cap stays exactly
as it is: fewer, larger losses on wide days is a drawdown problem, and this says
nothing about drawdown.


---

## Ideas 3, 4 and 5 — `research/studies/three_ideas.py`

### 3. BTC 30m regime — the standing CANDIDATE is RETIRED

`context.py` flagged BTC's 30m trend *against* the trade as a CANDIDATE at
**+0.174, 3.6 SE**, monotone, surviving all four splits and the risk-tercile
control. It has sat in this file as promising ever since, and `btc_dir` is
recorded on every signal and printed on every alert.

| panel | BTC against | BTC with | difference | |
|---|---|---|---|---|
| all early | +0.073 | −0.129 | **+0.202 ± 0.040** | **+5.1 SE** |
| **held out** | −0.035 | +0.002 | **−0.036 ± 0.058** | **−0.6 SE** |

**+5.1 SE on the full panel and the held-out half reverses the sign.** The full
panel is carried entirely by the discovery half. This is the same shape as the
trendline slope study, at a larger magnitude, and it is the most emphatic
demonstration in this file that a large SE on pooled data is worth nothing on
its own.

**The candidate is retired, and the alert line that carried it is removed.**
Every alert used to read "BTC trending with/against you"; a warning whose basis
has been withdrawn is worse than no line, because it costs a second of reading
on every message and points the eye at a factor now measured at nothing.
`btc_dir` is still computed and still stored on every outcome row — retiring a
display is not the same as stopping the measurement. It should not be
re-proposed without a fresh window, and the earlier +3.6 SE is best read as having been measured on what is
now the discovery half.

### 4. Internal MTF agreement — fails, and the first run was an impossible test

Min30 signals with a same-direction Min15 signal within 10 bars:

| panel | with | without | difference | |
|---|---|---|---|---|
| all Min30 | +0.026 | −0.038 | +0.063 ± 0.043 | +1.5 SE |
| overlapping window | +0.026 | −0.061 | +0.086 ± 0.058 | +1.5 SE |
| **older half of the overlap** | +0.013 | −0.068 | **+0.081 ± 0.080** | **+1.0 SE** |

**Fails.** Consistently positive across three panels and above the placebo floor
every time, which is more than most — but +1.0 SE is not evidence.

**The first run reported "0 rows" for the held-out panel and that was a real
methodological bug, not a null.** Both corpora fetch 2000 bars, so Min30 spans
~42 days and Min15 only ~21 — and the held-out half of Min30 is the *older*
half, which the Min15 data does not reach at all. Restricting Min30 to the
window Min15 actually covers is what the table above does.

### 5. Pool memory — fails, and its secondary died on the next check

Raid count on the same level: **not monotone**, −0.4 SE all, +0.5 SE held out.
The 3rd-raid bucket looks good in both panels (+0.084, +0.272) on 116 and 72
rows. Nothing there.

**The `pivots` reading nearly became a finding, and is worth recording as a
near miss.** Pool swing count on early held-out: 2 swings −0.041, 4+ swings
**+0.208 ± 0.098** — a difference of **+0.249, +2.4 SE**, above its placebo
floor, and positive on the full panel too (+1.6 SE). It was not pre-registered,
so the immediate next step was to check it elsewhere rather than report it:

| | 4+ minus 2 swings | |
|---|---|---|
| early, held out (where it was found) | +0.249 | **+2.4 SE** |
| **early, discovery — the other half** | **−0.017** | **−0.2 SE** |
| confirmed, all — independent population | +0.095 | +0.8 SE |
| confirmed, held out | +0.087 | +0.5 SE |

**Gone.** One half of one population. The cost of checking was two minutes; the
cost of not checking would have been a filter on the alert path.


---

## What a higher win rate costs — `research/studies/win_rate_price.py`

The goal was more wins and fewer stop-outs. There are two ways to chase it and
only one has ever worked here, so both were priced.

### Filters are exhausted, and the losers say why

`losers.py` on the current corpus: **not one loser failed to go green first.**
62% of early losers reached 0.5R, 26% reached a full 1R, median peak 0.63R.
Those are not bad entries a filter could have caught — they are trades that
worked and then stopped working. **A filter cannot reach them. An exit can.**

(Twenty-one filter attempts are recorded in this file, plus six more in one
session — trendline slope, SR break, RSI divergence, BTC regime, MTF agreement,
pool memory. One survivor in twenty-seven: the daily POI.)

### The win rate is buyable, and the price is now exact

Early, held out, same trades, exit varied:

| exit | win | full SL | R/signal | vs plain | R per win point |
|---|---|---|---|---|---|
| **plain, 2R** | **38%** | **59%** | −0.031 | — | — |
| half at 0.5R | **64%** | **34%** | −0.104 | −0.073 | 0.0028 |
| half at 1R, rest 2R | 52% | 46% | −0.069 | −0.038 | 0.0027 |
| half at 1R, rest 3R | 52% | 46% | −0.059 | −0.028 | 0.0020 |
| break-even at 1R | **30%** | 52% | −0.065 | −0.035 | — |

**Break-even is strictly bad and this was predicted in advance:** it *lowers*
the win rate, because a break-even exit scores 0.0 and `r > 0` does not count
it. It costs R as well.

The partial does exactly what it is reached for — **38% → 64% win, 59% → 34%
full stop-outs** — at a cost inside 1 SE of plain for the 1R/3R variant. On the
pre-registered bar it passes.

### And then it fails the metric that decides

Return per unit of maximum drawdown, 300 USDT, 1% risk, under the deployed
portfolio rules — exit is the ONLY thing varied:

| exit | win | return | max DD | **ret/DD** |
|---|---|---|---|---|
| **plain, 2R** | 42% | **+20%** | **8%** | **2.45** |
| half at 1R, rest 3R | 52% | −1% | 15% | −0.07 |
| half at 1R, rest 2R | 51% | −3% | 10% | −0.28 |
| half at 0.5R, rest 2R | **65%** | −3% | 11% | −0.31 |

**The partial destroys the equity curve, and drawdown gets WORSE, not better.**
The return lives in a small number of large winners; halving them at 1R while
the losers still lose in full removes exactly the trades that pay for
everything. A partial does not prevent a loss — it only shrinks a win.

The target ladder says the same thing from an independent direction:

| target | win | return | max DD | ret/DD |
|---|---|---|---|---|
| 1.0R | **54%** | +12% | 13% | 0.98 |
| 1.5R | 44% | +10% | 10% | 0.92 |
| **2.0R** | 42% | **+20%** | **8%** | **2.45** |
| 3.0R | 34% | +3% | 18% | 0.19 |
| 4.0R | 34% | +15% | 16% | 0.92 |

**2R is the peak on both return and drawdown.** 1R buys 12 points of win rate
and costs 60% of the return.

### Verdict

**Nothing changes. The deployed exit is already the best one measured**, and
that is the finding: the win rate is a purchasable property and every way of
purchasing it measured here costs more than it is worth. 65% wins for −3%
return, or 42% wins for +20%.

If a smoother curve is wanted for reasons other than money, the price is now
known to three decimal places and can be paid deliberately.


---

## Thirty-one features at once — `research/studies/feature_batch.py`, `feature_batch2.py`

ADX (14/14, threshold 20), EMA 21/51/100/200, SuperTrend (10, 1.8), MACD, VWAP,
Fibonacci position in the raid leg and momentum exhaustion — each on the signal
timeframe and, where meaningful, on 4h, 8h and daily. 3766 early signals.

**Thirty-one tests at a 2 SE bar manufacture about one and a half false
positives from nothing.** So the null was measured rather than assumed.

### The null went through two versions and the first one was mine to fix

**Version 1 — a coin flip per signal.** 300 of them. Result: median |SE| 0.63,
p95 1.79, and only **2% cleared 2 SE against a textbook 4.6%**. A null tighter
than theory is not strict, it is broken: a coin flip has no autocorrelation,
while a real EMA state persists for hundreds of bars so consecutive signals on
one symbol share a value. That inflates a real feature's spread and not the
control's.

**Version 2 — a circular shift.** Each symbol's real feature series rotated in
time by a random offset, scored against unrotated R. Same values, same order,
same keep-rate, same autocorrelation; only the alignment with the outcome is
destroyed. p95 rises to **1.8–2.1 and the null's MAX reaches 2.6–3.6**.

**That last number is the whole result: noise on this data routinely produces
+3.5 SE. The best real feature managed +2.7.**

### Decisively dead

| feature | Min30 | 4h | 8h | 1d |
|---|---|---|---|---|
| **ADX(14,14) > 20** | +0.1 | −0.1 | +1.0 | +0.9 |
| **MACD histogram** | +0.2 | +0.4 | +0.2 | +0.1 |

**The ADX filter does nothing at any timeframe.** Neither does MACD. VWAP on the
signal timeframe is +1.1. Momentum exhaustion (3+ bars into the raid) is −1.5
and flips to +0.5 held out.

The Fibonacci test was **degenerate and that is a flaw in the test, not evidence
about Fibonacci**: 97% of entries sit past 50% of the raid leg, because the FVG
forms on the reclaim by construction, so the split had nothing to divide.

### The one coherent lean, and why it still fails

Every EMA-on-a-higher-timeframe variant leans the same way — price above its
HTF EMA, agreeing with the trade, scores better. Five clear the strict null's
p95: EMA200[4h] +2.4, EMA51[8h] +2.0, EMA100[8h] +2.7, EMA21[1d] +2.2,
EMA51[1d] +2.3.

A family rather than one lucky cell is worth more than a single number. But:

- **Held out they are +0.3 to +1.6.** None approaches 2.
- **The null's max is 3.5.** The best of them is inside what noise makes.
- They are five correlated readings of one idea, not five findings.

Conditioned on the deployed Hour8 trend filter, EMA100[8h] gives +2.0 SE where
the trend agrees and +1.4 where it does not — so it is *not* purely the existing
filter in disguise, but neither half is strong.

### Verdict

**Nothing adopted.** The honest summary is that HTF trend alignment leans
slightly positive, which the grade already encodes through the Hour8 SuperTrend
and DI, and that every oscillator asked — ADX, MACD, RSI, VWAP — says nothing
at any timeframe.


---

## WHERE to enter — twelve entries on the same raids — `research/studies/entry_zones.py`

Every earlier test was a **filter** — 21 in this file, 31 more in
`feature_batch.py`, one survivor. This asks something structurally different:
given the raid, where should the entry sit? The loser anatomy is why it is worth
asking — not one loser failed to go green first, so a better price is a lever a
filter does not have.

Same signals, same stop at the raid extreme, target 2R. **Scored on R PER
SIGNAL**, counting an unfilled signal as zero, because a deeper entry fills only
on the trades that came back to it and per-fill scoring hides everything that
ran away.

### Early, held out — the pre-registered panel

| entry | fill | risk | **fee R** | win | R/fill | **R/SIGNAL** |
|---|---|---|---|---|---|---|
| market at the FVG close | 100% | 1.71% | 0.047 | 38% | −0.092 | −0.092 |
| retest + rejection | 39% | 1.54% | 0.052 | 37% | −0.110 | −0.042 |
| **FVG near edge (deployed)** | **78%** | 1.28% | 0.063 | **38%** | **−0.037** | **−0.029** |
| FVG mid | 70% | 1.12% | 0.071 | 36% | −0.057 | −0.040 |
| FVG far edge | 64% | 0.96% | 0.083 | 37% | −0.054 | −0.034 |
| Fib 0.5 of the leg | 63% | 1.02% | 0.079 | 37% | −0.047 | −0.030 |
| Fib 0.618 | 52% | 0.77% | 0.104 | 35% | −0.123 | −0.063 |
| **Fib 0.786** | 38% | **0.41%** | **0.194** | 30% | −0.403 | **−0.152** |
| order block extreme | 75% | 1.52% | 0.053 | 34% | −0.151 | −0.113 |
| order block mid | 62% | 1.22% | 0.065 | 34% | −0.174 | −0.108 |
| volumetric OB extreme | 74% | 1.55% | 0.052 | 36% | −0.094 | −0.069 |
| volumetric OB mid | 55% | 1.14% | 0.070 | 32% | −0.223 | −0.123 |
| the swept level | 55% | 1.15% | 0.070 | 34% | −0.161 | −0.089 |

**Nothing beats the deployed entry.** Best of twelve, on both populations.

### For the deeper entries, the loss IS the fee — almost exactly

Fib 0.786 pays **0.194 R** in fees against the deployed entry's **0.063 R**, a
difference of **+0.131 R**. Its R per signal is **−0.123 R** worse. The two
numbers are the same number.

That is the whole mechanism, and it generalises: a better price means a tighter
stop, a tighter stop means a bigger fee as a fraction of risk, and on this
strategy the fee is what the better price buys. **The golden pocket is the
worst entry tested (−3.5 SE)** for precisely this reason.

### But order blocks fail for a DIFFERENT reason, and that is the real finding

Order block mid pays **0.065 R** in fees — the deployed entry pays **0.063 R**.
Essentially identical, at essentially identical risk. Yet it loses **−0.080 R
per signal (−2.0 SE)** and its win rate is **34% against 38%**.

**The fee explains nothing here. The order block is simply a worse place to
enter than the fair value gap**, at the same price distance and the same cost.
Volumetric OB does not rescue it (−0.094, −2.3 SE); requiring the block to have
traded above its median makes it worse, not better.

### Retest + rejection: fewer trades, no better

Operationalised as drawn — price returns into the gap, closes back out of it,
and the testing wick is longer than the body. It fires on **39%** of signals and
scores **−0.042 per signal against −0.029**. The confirmation costs 61% of the
trades and buys nothing; per fill it is worse than not waiting.

### Market versus limit

Market at the FVG close is **−0.092** against the limit's **−0.029**. Waiting
for the limit is worth 0.06 R a signal, which is the taker fee and the better
price together. The current design is right.

### Verdict

**No change.** The deployed FVG-edge entry is the best of twelve, and the two
mechanisms behind that are now explicit: deeper entries lose exactly their extra
fee, and order blocks lose on location at equal fee.


---

## CORRECTION — the fee rate was wrong for the whole project, and it reverses a finding

Every study before 10 Sep charged **0.02% maker / 0.06% taker**, or a flat 0.08%
round trip. Those are MEXC's list rates. They are not what this account pays,
and nobody had checked them against a settlement.

### Derived from a real fill, not a fee table

An ARBUSDT long: 323.9062 USDT notional, entry 0.17237, close 0.16923, realised
**−6.0747**. Gross on the price move is **−5.9005**, so fees and funding
together cost **0.1742 over 641.9 USDT of two-sided volume = 0.0271% per side.**
A second settlement (XMR) splits them — trading 0.0864, funding 0.0216 — so
stripping funding at that 25% ratio leaves **~0.0217% per side of trading fee.**

MEXC's schedule shows **0.000–0.040% maker and 0.000–0.100% taker** with a 20%
MX deduction active, which brackets it. The model was **twice** the true cost
overall and **three times** on the taker side.

### What it changes

| fee model | early R/trade | early total | confirmed R/trade |
|---|---|---|---|
| **old assumption** mk .020 / tk .060 | **−0.008** | −23.5 R | +0.040 |
| measured taker, mk .020 / tk .022 | **+0.017** | +51.9 R | +0.063 |
| **likely real** mk .010 / tk .022 | **+0.031** | +91.9 R | +0.074 |
| zero-fee pairs, mk .000 / tk .022 | **+0.043** | +127.9 R | +0.084 |
| no fees at all | +0.059 | +175.5 R | +0.098 |

**"Early signals are net negative after fees" is WITHDRAWN.** It was one of this
project's load-bearing findings and it was an artefact of a fee rate that was
never checked against a settlement. At the rate actually paid, early signals are
**positive**.

The deployed FVG entry moves the same way: **−0.029 → +0.029 R per signal** on
the held-out half. The entry study's *ordering* is unchanged — it is still best
of twelve — but its level was negative only because of the fee.

### And it softens a second conclusion

`win_rate_price.py` concluded that a partial "destroys the equity curve". At the
corrected fee, on return per unit of drawdown:

| exit | win | return | max DD | ret/DD |
|---|---|---|---|---|
| plain 2R | 39% | +11% | 9% | **1.21** |
| half at 0.5R | **65%** | +8% | 8% | **1.00** |
| half at 1R, rest 3R | 48% | −4% | 10% | −0.34 |
| break-even at 1R | 31% | +11% | 11% | 0.96 |

**The partial is no longer disastrous — 65% win rate for 17% of the ret/DD.**
The earlier "it destroys the return" was substantially the overstated fee, since
a partial books half the position at 1R and therefore pays the fee twice.
Plain still leads, but the gap is now inside what the account simulation's own
path-dependence can produce.

### A caveat on the account simulation itself

The concurrency cap makes it chaotic: which trades get one of the eight slots
depends on which earlier trades filled, so a small change cascades. Two runs of
the *same* rule across this correction gave +20% and +11%. **The per-trade R
numbers are stable and should carry any argument; the account percentages are
directional only.**

### What is still not modelled

**Funding** — the XMR settlement puts it at a further 25% on top of the trading
fee, and nothing here charges it. **Slippage** on the stop. And the maker rate
assumes the entry limit actually rests; a marketable limit pays taker.

`RIPTIDE_FEE_MAKER` and `RIPTIDE_FEE_TAKER` now override the defaults, because
MEXC's rate is a distribution across pairs and time — zero-fee promotions run on
many pairs at once — rather than a constant.


---

## Exit policy, done properly — `research/studies/exit_grid.py`

Twenty-five policies (targets 1–3R × plain / break-even at 1R and 1.5R /
partial at 0.5R and 1R), on Min30 and Min15, early and confirmed. Fees at the
corrected 0.010/0.022, plus a zero-fee bound.

**Two instruments were replaced.** The fee (twice the true rate) and the
drawdown — `portfolio.simulate`'s eight-slot cap makes it path-dependent, and
two runs of the same rule gave +20% and +11%. Drawdown here is the **uncapped
R equity curve**: one unit per trade, in exit-time order, no slots, no
compounding. Deterministic, so a difference between rules is a difference
between rules.

Twenty-five cells is an optimisation, so the best cell is chosen on the
**discovery** half and reported on the **held-out** half — that estimates the
decision procedure, not the winning cell.

### Plain wins every panel

| panel | chosen on discovery | held out vs deployed 2R |
|---|---|---|
| Min30 early | plain @ 2.5R | −0.016 ± 0.043 (−0.4 SE) |
| Min30 confirmed | plain @ 3R | +0.012 ± 0.100 (+0.1 SE) |
| Min15 early | plain @ 2.5R | +0.007 ± 0.044 (+0.2 SE) |
| Min15 confirmed | plain @ 3R | +0.003 ± 0.105 (+0.0 SE) |

**Not one of the twenty-five is a partial or a break-even.** The deployed
plain @ 2R is not beaten on any panel.

### The partial buys the win rate and destroys the return

Min30 early, discovery:

| policy | win | full SL | R/signal | total R | maxDD | R/DD |
|---|---|---|---|---|---|---|
| **plain @ 2R (deployed)** | 38% | 60% | **+0.027** | **+52.3** | 58.6 | **0.89** |
| plain @ 2.5R | 34% | 64% | +0.035 | +68.3 | 73.0 | 0.94 |
| **half at 0.5R @ 2R** | **67%** | **33%** | **−0.007** | **−13.0** | 53.9 | **−0.24** |
| BE at 1R @ 2R | **32%** | 54% | +0.018 | +36.2 | 61.7 | 0.59 |

The partial nearly doubles the win rate and halves full stop-outs — and takes
total R from **+52 to −13**. The drawdown it buys is **8% smaller** (53.9 vs
58.6). That is the trade in full.

**Break-even lowers the win rate**, 38% → 32%, and costs R. Third confirmation.

### And the fee is NOT why the partial fails

At **zero fees**, Min30 early held out:

| policy | win | R/signal | total R | R/DD |
|---|---|---|---|---|
| **plain @ 2R** | 38% | **+0.048** | **+86.5** | **2.58** |
| half at 1R @ 3R | 52% | +0.032 | +56.7 | 1.65 |
| half at 0.5R @ 2R | **66%** | +0.002 | +3.4 | 0.11 |

Even with **no fee at all**, the partial is +0.002 against plain's +0.048. It
cuts the winners, and the winners are the entire return. The fee makes it worse;
it is not the cause.

### CORRECTION to the interim reading

An intermediate run off the path-dependent account simulation suggested the
partial was "no longer disastrous" at the corrected fee (65% win, ret/DD 1.00 vs
1.21) and that 1.5R "edges 2R". **Both are withdrawn.** On the deterministic
instrument the partial is −0.24 R/DD against plain's 0.89, and 1.5R is +0.019
against 2R's +0.027. The chaotic simulation was reading its own noise.

### Min15 is worse on both axes

Held out, early: Min30 **+0.020 R** with a 34.7 R drawdown; Min15 **−0.012 R**
with a **75.8 R** drawdown. Twice the drawdown for negative return.


---

## Is Min15 worth scanning — `research/studies/min15_worth.py`

`exit_grid.py` put held-out Min15 early at −0.012 R with a 75.8 R drawdown
against Min30's +0.020 at 34.7 and that looked damning — but it was **every**
signal the engine finds, and the bot sends only what survives POI_REQUIRED and
`MIN_GRADE=B`. So this replicates the deployed gates and asks whether Min15
earns its place among what actually reaches the phone.

### Among SENT signals, at grade B

| | n | win | R/signal | total R | maxDD | R/DD |
|---|---|---|---|---|---|---|
| Min30 early | 498 | 38% | +0.070 | +34.8 | 32.3 | 1.08 |
| **Min30 confirmed** | 82 | **50%** | **+0.458** | +37.5 | 14.3 | **2.63** |
| Min15 early | 623 | 37% | +0.046 | +28.6 | 57.9 | 0.49 |
| Min15 confirmed | 86 | 37% | +0.070 | +6.0 | 9.8 | 0.62 |
| **Min30 ALONE** | 580 | 40% | **+0.125** | +72.4 | **35.0** | **2.06** |
| Min30 + Min15 | 1289 | 38% | +0.083 | +107.0 | 84.6 | 1.27 |

Held out: Min30 alone **+10.5 R at 17.8 drawdown (R/DD 0.59)**; combined
**+11.9 R at 59.8 drawdown (R/DD 0.20)**.

### The pre-registered test PASSES, and it was the wrong test

The primary was: combined must beat Min30 alone on **total R**, held out. It
does — **+1.4 R**. So by the letter of the pre-registration, Min15 stays.

**That criterion was badly chosen and saying so afterwards is the only honest
option.** Min15 adds **65% more signals** (204 → 583) for **13% more R** and
**3.4× the drawdown**. Total R alone cannot see that, and the drawdown was
listed as a secondary when it should have been half the primary.

What separates the two readings is which one replicates:

| | full window | held out |
|---|---|---|
| R/DD, Min30 alone | **2.06** | **0.59** |
| R/DD, combined | 1.27 | 0.20 |

**The R/DD degradation appears on both halves. The +1.4 R gain is noise-sized.**
On the evidence that replicates, Min15 makes the equity curve substantially
worse for a return improvement that cannot be distinguished from zero.

### Not a data question any more

Dropping Min15 is a judgement call the measurement has now framed rather than
settled: fewer, better signals at a third of the drawdown, against 65% fewer
alerts. `RIPTIDE_INTERVALS=Min30` is the whole change.

The untested middle is **Min15 at grade A only** — the traffic is mostly grade
B early, and the A band is where Min30's own strength sits.

### A label bug, found in the first run

The panel titles hardcoded "grade B+" while the gate read `MIN_GRADE`, which
resolves to **C** unless `riptide.conf` is loaded — so the first run reported
grade C results under a grade B heading. Both now interpolate the same
constant. It is the same class of defect this project keeps finding in other
people's indicators: a label that can disagree with the filter it describes.

---

## Which alerts to actually take — and why five losses in a row is not a broken system

`research/studies/priority.py` · 60 symbols · 42 days · POI required · grade B+

Two things prompted this: a real run of five or six trades taken and all lost,
and the reader's own proposal to **give priority to 30m confirmed because it
wins more often**.

The proposal is right, and it is right for a reason worth stating. Every
earlier attempt in this project to raise the win rate moved the **exit** —
partials, break-even, nearer targets — and `exit_grid.py` showed what that buys:
65% wins for −3% return, or 39% wins for +20%. The win rate is a dial the exit
sets, and turning it does not make money. **Selecting a better cell is a
different mechanism**: it takes fewer trades from a population that genuinely
wins more often, and nothing about the exit changes.

### The alerts are not independent bets, and that is the real finding

The first pass reported a worst losing run of **13 straight losses** for a cell
winning 50% of the time. A binomial says that should essentially never happen
over 82 trades, so the streak column got a second column — how long the run
took:

| stream | worst losing run | spanning |
|---|---|---|
| everything sent (deployed) | **40 losses** | **12.0 hours** |
| everything sent, held out | 24 losses | **3.8 hours** |
| Min30 confirmed only | 13 losses | 88.5 hours |

**Twenty-four consecutive losers inside 3.8 hours is not twenty-four bets that
went wrong. It is one market event that fired two dozen alerts at once.** When
the whole book turns over together, every open position loses together — so
counting them as separate trades makes the streak, the sample size and the
standard error all fiction.

So every policy is also reported with **same-close alerts averaged into one
bet**, which is what the breadth line on the alert has been asking the reader
to do since it shipped. That is a re-framing rather than an independent
confirmation — it was introduced after seeing the per-signal table — but it is
applied uniformly and both views agree on the split that matters.

### Held out, as one bet per close

| policy | bets | /day | win | R/bet | SE | total R | maxDD | R/DD | worst run |
|---|---|---|---|---|---|---|---|---|---|
| everything (deployed) | 316 | 15.2 | 38% | +0.024 | 0.075 | +7.5 | 21.5 | 0.35 | 11 |
| **confirmed only, both TFs** | 59 | 2.8 | **49%** | **+0.411** | 0.193 | **+24.2** | **4.2** | **5.71** | **4** |
| Min30 confirmed only | 23 | 1.1 | 61% | +0.801 | 0.315 | +18.4 | 3.1 | 5.99 | 3 |
| Min15 confirmed only | 36 | 1.7 | 42% | +0.162 | 0.239 | +5.8 | 4.2 | 1.37 | 4 |
| Min30 **early** only | 152 | 7.3 | 34% | **−0.072** | 0.107 | **−11.0** | 17.5 | −0.63 | 10 |
| Min15 early only | 150 | 7.2 | 39% | +0.055 | 0.108 | +8.3 | 23.9 | 0.35 | 11 |

**The confirmed stream made +24.2 R held out. The early stream, five times the
traffic, made −2.7 R.** Early signals are 88% of everything that reaches the
phone and they are worth approximately nothing out of sample — Min30 early is
outright negative on both the per-signal and the per-bet view.

A first draft of this section said the early stream "lost 16.7 R of it back",
by subtracting the confirmed total from the all-in total. **That subtraction is
invalid** and the correction is worth keeping visible: clustering by close
merges an early and a confirmed alert that share a candle into one averaged
bet, so the three rows are not disjoint and do not add. Per signal — where the
rows *are* disjoint — the held-out early stream is **−6.6 R over 515 signals**
against confirmed's **+17.4 R over 69**. Same conclusion, reached without
subtracting incomparable things.

The gap between +24.2 (confirmed alone) and +7.5 (everything) is then mostly
**dilution**: on the closes where both kinds fire, averaging the early alerts
in drags the confirmed bet's R down.

Taking confirmed only also cuts the worst losing run from **11 to 4**.

### Grade A is the same filter, arrived at from the other side

`GRADES` gives A to `(confirmed, POI, trend agrees)`. Since POI is already
required and a trend disagreement drops a confirmed setup to C, **every
confirmed alert that clears the deployed grade B floor is already a grade A**.
The two rows are identical in every panel, which also answers the open question
left by `min15_worth.py`: "Min15 at grade A only" *is* Min15 confirmed, and it
is the weaker half of the pair.

### What this does and does not license

**Does:** take confirmed setups, both timeframes, and treat every alert sharing
one candle close as a single bet sized once.

**Does not:** the held-out confirmed sample is **59 bets**, +0.411 ± 0.193 —
about 2 SE from zero. Suggestive, not settled. The R/DD of 5.71 rests on a 4.2 R
drawdown observed over 21 days, and a small drawdown over a short window is
mostly luck; it will get worse. Narrowing further to **Min30 confirmed alone**
is where the numbers point, but 23 held-out bets cannot carry that decision,
and Min15 confirmed is positive there too.

### On the losing run itself

| win rate | P(6 losses in a row) | expected worst run in 50 trades |
|---|---|---|
| 35% | 7.5% | 9.1 |
| 38% | 5.7% | 8.2 |
| 50% | 1.6% | 5.6 |

Six straight losses is not evidence of a broken system at any of these rates —
it is what the deployed win rate looks like from the inside, several times a
year. The clustering makes it likelier still: five or six trades taken from one
session are close to **one bet placed five or six times**, and the arithmetic
above understates how ordinary that run was.

### A caching change, so the window stops moving

`gather()` writes the collected rows to `RIPTIDE_ROW_CACHE` and reloads them.
Each collection costs minutes of API traffic for a table that prints instantly,
and — more to the point — every policy is now read off **exactly the same
sample** rather than a fresh one that quietly moved between questions.

### How many separate bets, and what the losing runs really look like

"Separate" means a distinct candle close. Two confirmed alerts on the same 30m
close are **one** bet however many symbols printed it; two on consecutive
closes are **two**, however close together they feel.

| | Min30 confirmed | Min30+Min15 confirmed | everything (deployed) |
|---|---|---|---|
| alerts / day | 2.0 | 4.0 | 31.0 |
| **separate bets / day** | **1.8** | **3.5** | 16.0 |
| days with at least one bet | 29 of 42 | 30 of 42 | 42 of 42 |
| bets on an active day | median 3, busiest 6 | median 4, busiest 13 | median 11, busiest 37 |
| symbols per bet | median 1, biggest 3 | median 1, biggest 5 | median 1, biggest 18 |
| **win rate per bet** | **52%** | 47% | 42% |
| R per bet | +0.509 (SE 0.172) | +0.346 (SE 0.121) | +0.087 (SE 0.051) |
| **worst losing run** | **10 bets over 3.4 days** | 5 bets over 14.5h | 19 bets over 13.2h |
| chance alone would give | 5.8 | 7.9 | 12.1 |
| wait between bets | median 6.5h, longest quiet 4.5 days | median 2.8h | median 0.8h |

**Min30 confirmed is roughly two separate bets a day, and a third of days have
none at all.** The longest quiet stretch in 42 days was 4.5 days with nothing.
That is the real cost of the win rate, and it is not small: a policy that is
silent for most of a week is a different thing to sit with than one firing
every 45 minutes.

**The best cell still produced a ten-bet losing run.** Ten in a row at a 52%
win rate over 73 bets is well past the 5.8 that chance alone would give — a
small-sample tail rather than a broken cell, but the honest reading is that
**confirmed-only reduces how often a bad run happens; it does not remove it.**
Unlike the deployed stream's runs, this one was spread over **3.4 days**, so
those were ten genuinely separate decisions rather than one market move.

Worth noting against the earlier ranking: adding Min15 confirmed *shortens* the
worst run (10 bets to 5) and doubles the traffic, at the cost of five points of
win rate. Neither difference clears its own error bar, which is the point —
these two cells are not distinguishable on 42 days of data, and the choice
between them is about how many trades a week you want, not about edge.

---

## The 3+ touch filter — pre-registered, and it fails

`research/studies/pivot_filter.py` · 60 symbols · POI required · grade B+ · one bet per close

`pivot_tune.py` found that on Min30 early, signals whose pool had three or more
touches ran +0.206 R per bet held out at a 46% win rate, against −0.141 and 34%
for two-touch pools. That was the strongest separation anywhere in the early
stream. Three conditions were registered before this study ran; **all three had
to pass.**

### Condition 1 — the strict null: FAILS

| | |
|---|---|
| real separation | **1.69 SE** |
| circular-shift null p95 | **2.56 SE** |
| null max over 300 rotations | 3.86 SE |

Rotating each symbol's touch-count series in time — same values, same order,
same keep rate, same autocorrelation, no link to the outcome — manufactures a
*larger* separation than the real one more than 5% of the time. **The finding is
smaller than what its own shape produces against a random outcome.**

This is exactly why the instrument matters. Against the coin-flip null that
`feature_batch.py` originally used, 1.69 SE would have read as nearly
significant. A pool's touch count persists for the pool's whole life, so
consecutive signals on a symbol share it, and only a rotation preserves that
while breaking the link to R.

### Condition 2 — holds sign on both splits: PASSES, weakly

On Min30 early all four sub-panels are positive (+0.7, +1.5, +2.3, +0.5 SE). But
the magnitude swings 5× between odd symbols (+0.483) and even (+0.094), which is
a sign the size of the effect is not a stable quantity.

### Condition 3 — reproduces on a fresh timeframe: FAILS

Min60 and Hour4 had never been examined in this project, so nothing could leak
into them.

| difference, kept − dropped | full window | held out |
|---|---|---|
| **Min30 early** *(found here)* | **+0.248 (+1.7 SE)** | +0.345 |
| Min15 early | +0.036 (+0.3 SE) | −0.047 |
| Min60 early | +0.074 (+0.5 SE) | −0.000 |
| Hour4 early | +0.029 (+0.2 SE) | −0.059 |

**Three independent timeframes say zero.** Min30 early is the outlier, not the
rule.

### The whole scatter

Across eight panels — four timeframes × two signal types — the difference reads
+1.7, −1.4, +0.3, −0.4, +0.5, +0.6, +0.2, +1.5 SE. **Not one clears 2 SE, the
largest is the panel it was discovered on, and the set is centred near zero.**
That is what no effect looks like.

Confirmed is incoherent in the other direction too: Min30 confirmed says
two-touch pools are far better (−0.470, −1.4 SE), while Min60 and Hour4
confirmed lean the opposite way. A real property of a level would not change
sign with the chart timeframe.

**Verdict: nothing changes. The pool stays as shipped, and `min_pivots` stays
at 2.**

### One thing worth keeping

Hour4 carries **333 days** of history against the 42 days every other study in
this project runs on. It is far too slow to trade — 0.2 bets a day — but as an
*out-of-sample window for testing a mechanism* it is eight times anything used
here so far. Any future claim about market structure should be checked against
it before being believed.

---

## The liquidity target — the one untested exit dimension, and it fails

`research/studies/liquidity_target.py` · POI required · grade B+ · one bet per close

Every exit ever tested here used a **fixed** multiple of risk — 25 policies, four
targets, five families. None asked whether the target should depend on the
chart. "Take profit into the opposing liquidity" is the standard SMC answer and
the engine already has the machinery, so this was the last genuinely untested
dimension in the exit.

### Where the pool actually sits — the finding that explains everything else

| | median distance to nearest unswept pool | share closer than 2R |
|---|---|---|
| Min30 confirmed | 1.2 R | **77%** |
| Hour4 confirmed | 1.1 R | **81%** |
| Hour4 early | 1.2 R | 79% |

**"Target the liquidity" is, on this data, almost always a *closer* target.** So
it is not a new mechanism at all — it is the exit dial that `exit_grid.py`
already priced, reached by a different route.

And it behaves exactly as that predicts. Win rate up, money down:

| Min30 confirmed, full window | win | R/bet | vs deployed |
|---|---|---|---|
| plain 2R *(deployed)* | 53% | **+0.529** | — |
| nearest pool | **57%** | +0.194 | −1.5 SE |
| pool beyond it | 57% | +0.558 | +0.1 SE |

The pre-registered expectation said "the nearest pool beats 2R on win rate and
loses on R." It does, on all four full-window panels.

### Both pre-registered conditions FAIL

**Primary — Min30 confirmed, held out:** the nearest pool is **−1.9 SE worse**
than plain 2R (+0.111 against +0.775).

**Second — Hour4, 333 days, the fresh check:** every liquidity policy is
negative against the deployed exit on both held-out panels — nearest pool −0.5
SE on confirmed and −0.9 SE on early.

**Across eight panels, not one liquidity target beats plain 2R held out, and
the sign is negative in every one.** That is not a close call.

### The floor was the interesting cell, and it is the worst one

The expectation was that a floor would help — take the trade only when the pool
is far enough away to pay for the risk. The opposite happens, and the cleanest
row is the diagnostic one:

| Min30 confirmed, full window | bets | win | R/bet |
|---|---|---|---|
| plain 2R, all trades | 74 | 53% | +0.529 |
| **2R, only when a pool sits 2R+ away** | 17 | **29%** | −0.142 (−1.8 SE) |

That row holds the exit fixed at 2R and changes only *which trades are taken*.
**Trades whose nearest liquidity is far away are worse trades, not better
ones** — the reverse of the intuition that clear air ahead is good.

**One confound, and it is not small.** "Pool is far in R" and "the stop is
tight" are close to the same statement, since R is the denominator. So this row
may be re-measuring the tight-stop population rather than anything about
liquidity, and tight stops pay proportionally more in fees and stop out on
noise. The honest reading is that the filter fails; *why* it fails is not
settled by this study.

### What this closes

The exit has now been moved by a fixed multiple (25 policies), by a break-even
rule, by a partial, by a structural trail, and by the chart's own liquidity. All
five families lose to plain 2R. **The exit is not where the remaining headroom
is, and this was the last untested way in.**

---

## FVG continuation — a second strategy, tested against its own control

`research/studies/fvg_continuation.py` · 60 symbols · Hour8 trend must agree · target 2R

Everything tested in this project until now is the same trade: liquidity raided,
structure shifts, price returns to a gap. This is a different model — no sweep,
no pool, no shift. A displacement with the higher-timeframe trend leaves a gap,
price retraces into it, you go with the trend.

**The trap was designed for in advance.** "Enter with the Hour8 trend" is already
the strongest filter in this system, so a continuation model will look
profitable for reasons that are already deployed. Every arm therefore sits
against a **control**: a limit half an ATR below the close with the stop an ATR
under it, on bars sampled from the same trending population, no gap required. If
the gap cannot beat that, the gap is decoration.

### Min30, held out (42 days)

| arm | bets/day | risk | win | R/bet | vs CONTROL |
|---|---|---|---|---|---|
| gap ≥ 0.05 ATR *(engine default)* | 44.5 | 0.33% | 21% | −0.569 | −12.2 SE |
| gap ≥ 0.25 ATR | 37.3 | 0.49% | 39% | −0.141 | −1.7 SE |
| gap ≥ 0.50 ATR | 27.4 | 0.66% | 38% | −0.110 | −0.9 SE |
| **gap ≥ 0.25 ATR, stop under leg** | 37.3 | 1.19% | 44% | +0.038 | **+2.0 SE** |
| counter-trend gaps *(the mirror)* | 44.9 | 0.34% | 21% | −0.588 | −12.8 SE |
| CONTROL: any dip in the trend | 4.7 | 0.81% | 46% | −0.059 | — |

### Verdict: 1 of 3 conditions, marginally, and it fails the strongest one

**PRIMARY — beat the control held out by 2 SE:** passes at *exactly* +2.0 SE with
fees, **+1.7 SE without them**. Sitting on the threshold, and flattered by the
fee.

**SECOND — reproduce on Hour4 (333 days):** **FAILS.** The same arm is +0.035 at
**+0.4 SE**, with or without fees. This check has now killed three candidates in
a row.

**THIRD — overlap with the deployed model:** 32% on Min30 and **57% on Hour4**.
On the longer sample more than half of these "new" signals land within three
bars of one the engine already sends. It is not an independent second stream.

**And it is untradeable as specified: 37 bets a day**, against 1.8 for Min30
confirmed. Twenty times the traffic for +0.038 R.

### What actually moved the numbers, and it was not the gap

The same signals, the same entries, differing only in where the stop goes:

| gap ≥ 0.25 ATR, Min30 held out | risk | win | R/bet |
|---|---|---|---|
| stop at the gap's far edge | 0.49% | 39% | −0.141 |
| stop under the whole leg | 1.19% | 44% | **+0.038** |

**+0.18 R from the stop alone**, and at zero fees still +0.108 — so roughly 40%
of it is fees and 60% is real. The gap filter moves R by a fraction of that.

This is the **fourth** time the risk distance has turned out to dominate the
entry logic in this project, and it is the clearest statement of it: across
every study here, *how far the stop sits* has mattered more than *where the
entry is chosen*. The near-zero-risk arms are the proof — a 0.05 ATR gap puts
the stop 0.33% away, where a 0.032% round trip is a large fraction of R, and the
convexity of fee-in-R does the rest.

### The counter-trend mirror is the deployed filter, restated

Counter-trend gaps run −0.588 against +0.038 for the same construction with the
trend. A 0.63 R separation — the largest number in this study by far, and it is
**the Hour8 trend filter that is already deployed and already required by the
grade.** Exactly the trap the control was built to catch.

**Verdict: not adopted.** No second strategy here.

---

# PHASE A — the deployed model on 333 days. The edge does not survive.

`research/studies/replicate.py` · 60 symbols · nothing tuned, nothing chosen

The exchange caps a *response* at 2000 bars but serves any *window*. Paging back
yields **333 days with no discontinuities**, ~3 seconds a symbol. It was
available all along. Every study in this project ran on 42 days.

### First, the validation — the deep pipeline reproduces the known number

| Min30 confirmed, trailing window | bets | win | R/bet | SE | total R | R/DD |
|---|---|---|---|---|---|---|
| **last 42d** | 77 | **51%** | **+0.477** | 0.167 | +36.8 | 3.14 |
| last 90d | 156 | 42% | +0.199 | 0.114 | +31.0 | 2.28 |
| last 180d | 280 | 39% | +0.106 | 0.083 | +29.8 | 1.07 |
| last 270d | 402 | 38% | +0.060 | 0.069 | +24.1 | 0.87 |
| **last 333d** | 500 | **38%** | **+0.063** | 0.062 | +31.4 | 1.13 |

The 42-day row matches the known figure (74 bets, 52%, +0.509) to within the
window boundary. **The loader is sound, so the decay is real.**

### The finding

**+0.063 ± 0.062 R per bet over a year is one standard error from zero.**

And total R barely moves down the ladder — +36.8 at 42 days against +31.4 at 333.
**Essentially all of the past year's profit was made in the last six weeks; the
preceding 291 days netted about −5 R.**

| Min30 confirmed by quarter | bets | win | R/bet | total R |
|---|---|---|---|---|
| 2025Q4 | 123 | 37% | +0.058 | +7.1 |
| 2026Q1 | 120 | 34% | −0.074 | −8.9 |
| 2026Q2 | 139 | 35% | −0.008 | −1.1 |
| **2026Q3** | 118 | **46%** | **+0.289** | **+34.1** |

**Every study in this project was measured on the one quarter that worked.** The
"held-out half" was held out *within* that quarter, so it was never out of
sample in the way that matters.

### Survivorship is NOT the explanation, which makes this worse

| | bets | win | R/bet |
|---|---|---|---|
| Min30 confirmed · LONG | 267 | 38% | +0.081 |
| Min30 confirmed · SHORT | 233 | 38% | +0.042 |

Long minus short: **+0.039 R, +0.3 SE.** Symmetric. Walking today's most liquid
coins back a year should have *flattered* the deep window, and it came back at
zero anyway. The pre-registered warning was "a gain over 42 days is the bias
talking" — there was no gain to explain away.

### Three prior conclusions this overturns

**1. "52% win rate, well above the ~35% break-even."** The real figure is **38%
over a year, against a ~35% break-even.** Barely above water, not comfortably
above it. That reassurance was drawn from the best quarter and was wrong.

**2. "Take Min30 confirmed, not early."** Over 333 days: confirmed +0.063 ±
0.062, early +0.028 ± 0.028. The difference is **+0.5 SE**. Confirmed still wins
on R/DD (1.13 vs 0.88) and on traffic (1.5 vs 6.9 bets/day), which is a real
reason to prefer it — but not the edge difference that was claimed.

**3. "45 tests, one survivor, so the structural variations don't matter."** They
were all measured inside one favourable quarter. That does not make them alive —
it means the negatives were measured on the wrong window as well as an
underpowered one.

### What is actually true now

The system is **marginal, not broken**: +31.4 R over 500 bets at R/DD 1.13,
positive in three of the last four quarters by total R but negative in two of
four by R per bet. At ~1.5 bets a day that is roughly +0.1 R a day, with a
27.8 R drawdown to sit through.

Whether Q3 is a better *regime* or the other three quarters are the truth is not
answerable from one year of data. What is answerable: **the 52% / +0.5 R version
of this system does not exist over a year.**

## Regime conditioning — nothing separates the quarter that paid

`research/studies/regime.py` · 624 Min30 confirmed signals · 333 days

If a variable observable **at signal time** separated Q3 from Q1 and Q2, the
strategy becomes conditional and useful. Five candidates, each chosen for a
written-down mechanism, each expressed as a **trailing 30-day percentile** rather
than a level — a level is a disguised date and would separate quarters by
construction.

### Whole window — top tercile against bottom

| variable | top R/bet | bottom R/bet | difference | |
|---|---|---|---|---|
| market volatility | +0.053 | +0.006 | +0.047 | +0.3 SE |
| one-way market | +0.095 | −0.011 | +0.106 | +0.7 SE |
| dispersion | +0.074 | +0.050 | +0.024 | +0.2 SE |
| volatility rising | +0.001 | +0.116 | −0.115 | −0.7 SE |
| symbol vol vs market | +0.120 | +0.103 | +0.017 | +0.1 SE |

**Nothing reaches 1 SE.** Five values scattered between −0.7 and +0.7 — what no
effect looks like.

### The within-quarter test earned its place immediately

`dispersion`, read one quarter at a time:

| quarter | top | bottom | difference |
|---|---|---|---|
| 2025Q4 | −0.033 | −0.043 | +0.010 |
| 2026Q1 | −0.216 | +0.145 | −0.361 |
| 2026Q2 | −0.172 | +0.344 | −0.516 |
| **2026Q3** | **+0.461** | −0.284 | **+0.745 (+2.4 SE)** |

**Looking only at Q3, dispersion "explains" the good quarter at +2.4 SE.** It
reverses in Q1 and Q2 and comes to +0.2 SE over the window. This is the single
clearest demonstration in the project of why a variable must separate *within*
the buckets it appears to explain — I already knew Q3 was the good quarter, so
any variable elevated there would have fit it perfectly and predicted nothing.

`symbol vol vs market` does the same thing more neatly: **+1.6 SE in Q1, −1.5 SE
in Q2.** Cancelling noise.

### The strict null

| variable | real \|SE\| | circular-shift null p95 | null max |
|---|---|---|---|
| market volatility | 0.31 | 2.17 | 2.71 |
| one-way market | 0.70 | 1.94 | 3.15 |
| dispersion | 0.16 | 2.23 | 3.10 |
| volatility rising | 0.73 | 2.01 | 3.41 |
| symbol vol vs market | 0.11 | 1.83 | 2.92 |

Not one is within a factor of two of its own null.

### 0 of 5, and the power is adequate for the question asked

The quarterly spread being explained is about **0.36 R** (−0.074 to +0.289).
Terciles of ~170 bets give an SE on the difference of ~0.15–0.20, so a variable
that *fully* explained the quarterly variation would register near 2 SE. Nothing
reached 0.7.

**This rules out a large, price-observable regime effect. It does not rule out a
small one**, and it says nothing about variables not tested here — funding rates,
open interest, or time-of-day. Open interest is the interesting gap: the bot
already logs it, and it is the only non-price data source available.

### What this leaves

No regime filter. The honest description of the system is unchanged and now
better supported: **a marginal edge whose returns arrive in bursts that cannot be
timed from price.** The practical consequence is about sizing rather than
filtering — constant small size and patience, not a switch that turns the
strategy on and off.

## Funding rate — the first non-price test, and the mechanism fails its own prediction

`research/studies/funding.py` · 60 symbols · 540 days of funding history · 624 signals

Every variable tested in this project until now was a transform of price. That
is a closed loop: a strategy built from price, conditioned on price. Funding —
what longs pay shorts to hold the perpetual — is the first thing available that
measures **positioning** rather than price, and MEXC serves 540 days of it.

**The mechanism was written down first and it is directional.** This strategy
fades a raid, on the claim that a sweep of the lows is forced selling that
exhausts itself. Funding says whether there was anything to force:

> `crowd_against` = +funding for a long, −funding for a short. A raid into a
> crowded *opposite* book is a liquidation; a raid into a flat book is just a
> move. **Higher should pay.**

### Whole window

| variable | top R/bet | bottom R/bet | difference | |
|---|---|---|---|---|
| **crowd positioned against us** *(the mechanism)* | +0.062 | +0.047 | +0.015 | **+0.1 SE** |
| funding extreme, either way | +0.128 | +0.036 | +0.092 | +0.6 SE |
| raw funding percentile *(unsigned control)* | +0.128 | +0.055 | +0.073 | +0.5 SE |

### The mechanism variable is the WEAKEST of the three, and that is the finding

If the liquidation story were right, the **signed** variable should beat the
unsigned control — knowing *which* side is crowded should matter more than
knowing *that* positioning is extreme. It comes in at +0.1 SE against the
control's +0.5 SE. Whatever trace exists in funding is about how stretched
positioning is, **not about which side is trapped** — the opposite of the
prediction.

The long/short split says the same thing:

| crowd positioned against us | difference | |
|---|---|---|
| LONG signals only | +0.131 | +0.6 SE |
| SHORT signals only | −0.029 | **−0.1 SE** |

The mechanism claims both sides. It appears on neither, and the short side is
nominally reversed.

### All four conditions fail

| condition | crowd_against |
|---|---|
| 1. 2 SE on the whole window | **no** (+0.1) |
| 2. sign in 3 of 4 quarters | **no** (2 of 4: −1.2, +1.2, −0.1, +1.6) |
| 3. clears circular-shift null | **no** (0.10 against p95 1.69) |
| 4. present on both sides as predicted | **no** (shorts reversed) |

`funding extreme` passes condition 2 alone (3 of 4 quarters) while failing 1 and
3 by wide margins — 0.64 against a null p95 of 1.74. One condition out of three
is what noise produces.

### What this costs the ICT premise

This is the most direct test the project can run of the story the whole strategy
rests on: **that a liquidity raid is a liquidation of a crowded book.** The best
available positioning data, over 540 days, with the direction stated in advance,
found nothing — and found the signed version weaker than the unsigned one.

That is not proof the mechanism is absent. Funding is a coarse 4-to-8-hour
proxy, and terciles of ~180 bets resolve to about 0.3 R, so a small effect would
be invisible. But it is the strongest disconfirmation available, and it bears
directly on whether more ICT-flavoured hypotheses are worth the compute.

### Where the day's work leaves the system

Eight tests, all negative: the pool grid, the touch-count mechanism, the 3+
touch filter, the liquidity target, FVG continuation, the deep replication, five
regime variables, and three funding variables.

The description that survives all of it: **a marginal, unconditional edge —
+0.063 ± 0.062 R per bet over a year at R/DD 1.13 — whose returns arrive in
bursts that nothing tested can time.** Not a losing system on the measured
window. A small one, and an untimeable one.

## Correlation-aware sizing — the edge story is false, the variance story is not

`research/studies/sizing.py` · 333 days · same-close same-direction alerts already collapsed to one bet

### The mechanism, measured directly instead of inferred from a policy

R per bet against how many same-direction bets were **already open**:

| already open | Min30 confirmed | | everything sent | |
|---|---|---|---|---|
| | bets | R/bet | bets | R/bet |
| 0 | 329 | +0.094 | 606 | −0.011 |
| 1 | 131 | +0.084 | 700 | +0.015 |
| 2 | 34 | **−0.394** | 515 | +0.080 |
| 3 | — | — | 329 | +0.040 |
| 4 | — | — | 185 | +0.031 |
| 5+ | — | — | 138 | +0.051 |

**On the pooled stream it is flat, if anything rising.** A later position in a
cluster is not a worse bet. The confirmed cell shows −0.394 at two already open,
but that is **34 bets** and 7% of the stream.

### So where did the policy sweep's "+100% R/DD" come from?

| everything sent | total R | maxDD | R/DD | by quarter |
|---|---|---|---|---|
| flat (deployed) | +71.6 | 76.5 | 0.94 | — |
| cap: skip if 3 already open | +93.0 | 49.8 | **1.87** | beats flat 3 of 4 |
| budget 1/(1+open) | +18.2 | 46.5 | 0.39 | 1 of 4 |

The cap looks excellent and **the bucket table says it should not.** The
resolution is that a cap is **path-dependent**: skipping a bet changes what is
open later, so "3 already open under the cap" is a different set from "3 already
open under flat". That is the same class of artefact as the old eight-slot
portfolio simulator which gave +20% and +11% for the same rule on two runs. Its
Q4 cell (4.46 against flat's 1.47) carries most of the result.

On **Min30 confirmed** — the cell actually traded — every policy beats flat in
**2 of 4 quarters**, and the headline +33% R/DD for `budget 1/(1+open)` comes
from one quarter (1.90 against 0.59) while losing in another (2.17 against 2.91).
A coin toss.

### What survives is arithmetic, not a finding

The book is rarely crowded where it matters: on Min30 confirmed, **66% of bets
arrive with nothing else open**, the median is 0 and the maximum is 4. There is
very little for a correlation rule to act on.

And since R per bet does **not** degrade with concurrency, sizing down when
crowded buys no expected return — it buys **lower variance**, which is a
statement about arithmetic rather than about the market. Six correlated longs
are decided by one market move, so the size of a bad session scales with how
many are open instead of averaging out. That is true whether or not any study
confirms it.

**Therefore: no sizing rule is deployed, and no alert is ever skipped.** What
ships is the count — `⚖ 3 longs already open` — drawn from the reader's own
journal, so they can hold a risk budget across the book rather than per alert.
Information, with the measurement behind it in `/legend`, and explicitly not a
filter, because the data says a later position is not a worse bet.

## What actually discriminates between the alerts you receive

Three things printed on every alert, measured over 333 days on the deep window.

### Risk % — the best candidate found in this project since the volume gate

| Min30 confirmed, by risk % | bets | win | R/bet | SE |
|---|---|---|---|---|
| tightest quarter, <1.21% | 145 | 35% | −0.024 | 0.117 |
| **1.21 – 1.72%** | 139 | **43%** | **+0.188** | 0.120 |
| **1.72 – 2.59%** | 127 | **43%** | **+0.185** | 0.124 |
| widest quarter, >2.59% | 137 | **26%** | **−0.210** | 0.107 |

An inverted U: **the middle half beats the two extremes by +0.318 R at +2.7 SE.**
Both tails have a mechanism — a tight stop pays a large fee as a fraction of R
(the convexity that has now appeared five times), and a very wide stop means the
raid itself was violent, which is a move continuing rather than exhausting.

**By quarter: +0.7, +3.3, +1.8, −0.4 SE — the sign holds in 3 of 4.** It is
*absent in 2026Q3*, the one quarter that paid, and present in the three that did
not. That is the opposite of every variable killed earlier today, all of which
lived in Q3 alone.

**What holds it back, stated plainly:**
- **It does not appear in the early stream at all** — −0.0 SE overall, quarters
  −0.4, −0.2, +1.5, −1.0. A fee-and-continuation mechanism should show in both.
- Six comparisons were made (three variables × two signal types) and this is the
  best. Corrected for that, 2.7 SE is around p ≈ 0.04.
- The circular-shift null has not been run on it.

**Status: the most promising thing on the alert, not a rule.** It is reported so
a reader can weight by it, not gated.

### The other two are nothing

| Min30 confirmed | R/bet | |
|---|---|---|
| Day pool | +0.111 (61) | vs Pivot +0.043 (456) — +0.4 SE |
| swings in the pool | 1: +0.111 · 2: +0.071 · 3: +0.046 · 4+: +0.075 | flat |

Swings are flat on confirmed and non-monotone on early (2 swings −0.031, 3
swings +0.118), which is the same verdict `pivot_filter.py` reached by a much
longer route. Pool source repeats the 42-day finding at the same non-significance.

### The grade letter carries no information right now

`GRADES` gives A to (confirmed, POI, trend agrees) and B to (early, POI, trend
agrees). With POI required and the floor at B, a trend disagreement drops either
kind to C and it is never sent. **So every alert sent is A if confirmed and B if
early** — the letter and the ★ are the same fact twice.
