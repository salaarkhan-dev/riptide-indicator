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
| **BTC 30m trend agrees** | +0.192 (+1.8) | **+0.174 (+3.6) CANDIDATE** |

**The canonical volume premise is false here.** A liquidity grab is supposed
to print a volume spike; relative volume on the raid bar sorts nothing
(+0.7 SE on both). Nor does volume on the gap bar. That closes the whole
volume family, now that it can actually be measured.

**RSI, chart DI and volatility regime: nothing.**

### BTC 30m regime — the only thing that has cleared the bar since the fix

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
