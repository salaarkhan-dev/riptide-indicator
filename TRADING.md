# Trading rules

Everything here is derived from `MEASUREMENTS.md`. Where a rule has no number
behind it, it says so. Nothing in this file is advice about whether to trade —
it is what the measurements say IF you do.

**The single most important caveat:** almost every number below comes from one
~42-day backtest window, and the parameters were chosen on that same window.
One effect has been held out on data it was not found on: the daily POI kept
its sign on all three measurable arms. The BTC regime was held out too and
replicated, but with its labels inverted by a sign bug — see below. Assume
shrinkage on everything else.

## Read the grade first

Every alert opens with a letter. It is the whole triage, and it is the only
thing in the message that has been measured end to end.

Measured on the live universe — 60 symbols, 30m and 15m, POI required, 42
days, fees in, an unfilled signal counted as a zero:

| grade | what it is | /day | fill | **win** | RR | R/signal |
|---|---|---|---|---|---|---|
| **A** | confirmed, in a POI, trend agrees | 4.4 | 72% | **48%** | 1.81 | **+0.271** |
| **B** | early, in a POI, trend agrees | 24.4 | 82% | 45% | 1.71 | +0.180 |
| C | everything else *(muted)* | 37.5 | 79% | 38% | 1.70 | +0.016 |
| D | cannot occur while the POI is required | — | — | — | — | — |

**A wins 48% of the trades it fills. More than half of them lose.** It is
profitable because it pays 1.81:1, not because it is often right. Four A's a
day means a run of three losers happens most weeks and means nothing; you need
about 30 before the sample says anything at all. If you are reading each A as
a high-probability trade you will stop taking them at the worst moment.

*(An earlier version of this file put A at +0.822 and a 76% win rate. That was
43 signals, 30m only, on 23 hand-picked symbols. On the 60 symbols the bot now
scans the same cell is +0.271 at 48%. The ORDER of the letters survived the
change; the levels did not, which is what this file has always said about
levels. Corrected 8 Sep.)*

Two axes make the letter, and they multiply rather than add: neither is
+0.082, the trend alone +0.206, the POI alone +0.105. That is why there is a
table rather than a points system.

A 30m A is worth more than a 15m A — +0.317 against +0.216, 52% win against
45% — but the gap is well inside one standard error, so it is a tiebreaker,
not a rule.

**Priority when several alerts land at once and you have one slot free:**

  1. A, always. 4.4 a day across 60 symbols, and it is the only band paying
     more than +0.2 R per signal.
  2. Between two A's, prefer the 30m one and the one with the wider stop. Both
     are sub-1 SE tiebreakers, so use them only to break an actual tie.
  3. The BTC line is not a tiebreaker in either direction. See below — the
     numbers this file used to quote had their labels inverted by a bug, and
     the corrected reading is not stable enough to act on.
  4. Never fill the last slot with a C when the day is young. Slots are the
     scarce resource, not signals — the account simulation had to skip
     hundreds of signals for want of one.

**What to avoid, in order of how much it costs:**

  - **Do not take D.** It is the only band measuring negative and it used to be
    38% of everything sent. With POI_REQUIRED on you will rarely see one.
  - **Do not chase an A that has run.** An A whose entry is already far behind
    price is a missed trade, not a better one. See the fill-rate rules below.
  - **Do not size up on an A.** The letter changes which trades you take, never
    how much you risk. 1% stays 1%.
  - **Do not read the band percentage as a forecast.** It is a base rate from
    one window. The ORDERING of the bands is what replicated; the levels are
    the least stable thing measured, and they have already moved once.
  - **Do not draw a conclusion from one trade, in either direction.** At a 48%
    win rate a losing A is the more likely outcome, and a winning one is not
    evidence either. Every rule in this file was changed only by a measurement
    across hundreds of signals, and the two that survived a held-out test are
    named as such. One chart cannot move any of them.
  - **Do not act on a sweep heads-up.** It has no entry and no stop because
    neither exists yet. It means go and look, nothing more.

## The BTC line — read it as a fact, not as a verdict

**A sign bug inverted the label on every BTC measurement this project ever
made.** Six research scripts compared `supertrend() < 0` against the trade
direction, under a comment reading "-1 is up". It returns **+1** for up — the
alert code always had it right, the studies did not. So every number this file
and the code comments quoted for "BTC agrees" was in fact measured on BTC
going the *other* way.

Re-measured on the correct sign, 6970 early signals, 42 days, live universe:

| | n | fill | win | R/signal |
|---|---|---|---|---|
| BTC 30m trending WITH you | 3253 | 84% | 31% | **-0.150** |
| BTC 30m trending AGAINST you | 3717 | 81% | 41% | **+0.081** |

Once relabelled, the earlier work replicates rather than contradicting this:
discovery, held-out window, and now the current window all point the same way.
Three windows, same direction. And it is mechanically coherent — these are
reversal setups off a liquidity sweep, and a reversal needs something to
reverse against.

**It is still not a rule, and you should not trade it yet.** Inside grade B —
the band you actually receive most of — the split reverses between the two
halves of the window: +0.289 in the first half, -0.641 in the second. An
effect that changes sign inside 42 days is a regime relationship, not an edge,
whatever the pooled standard error says.

So: **the BTC line tells you which way BTC is pointing. Nothing more.** Do not
skip a B because BTC disagrees, and do not take one because it does. `/stats`
records `btc_dir` on every signal and is the only place this gets settled.

The alert wording changed with this correction — 🟢/🔻 implied a verdict the
evidence does not support, so both cases now read "⛓️ BTC trending with/against
you" and neither is coloured as good or bad.

## Per trade

**Size by risk, never by margin.** Position notional = `account × risk% ÷
stop%`. The alert gives you the stop%. Sizing by a percentage of balance is
what makes stop distance drive loss size, and it is why wide-stop trades felt
punishing — they were not worse trades, they were bigger ones.

**Enter with a LIMIT at the alert's entry.** Never market. The entry is a
retracement into the gap and price is usually already past it; a market fill
takes a worse price against the same stop, which quietly inflates the risk you
just sized. About 20-30% never fill. That is a zero, not a loss, and it is
already priced into every number here.

Market-entering every signal instead was measured directly: -0.064 R on
confirmed and -0.048 on early. The limit order is not a formality, it is doing
the selecting.

**Leave the limit working the full 10 bars, and do not chase it.** Five hours
on 30m. Cancelling at 5 bars costs 0.069 R per confirmed setup (2.0 SE).
Moving the order toward price to force a fill is worse still, and the more you
move it the worse it gets — 0.5 ATR costs 0.066, a full ATR costs 0.230
(3.6 SE), because the stop does not move with the entry, so buying fill rate
buys risk on every trade rather than just the ones you were missing. This
holds even though 80% of the setups that never fill go on to reach 2R without
you. Those are not the ones that got away; they are the price of the ones that
did fill working at all.

**Do not chase a higher win rate.** It is a dial, not an achievement: the win
rate is set by the target, and every turn toward a higher one costs money.
Measured across ten targets on 2748 alerts, perfectly monotone — 0.5R wins
69% and LOSES 54 R; 2R wins 41% and makes 255 R; 4R wins 32% and makes 413 R.
Reaching 60% overall means a 0.75R target and keeping +7 R instead of +255.
Break-even at 2R is about 36% after fees, so 41-49% is the edge, not a
shortfall. The number to improve is **R per signal**.

**Exit at 2R.** The ladder is monotone — 1R +20.4 total R, 1.5R +39.5, 2R
+52.8, 3R +61.9 — though each step is only about 1.5 SE, so 2R is a floor
rather than a proven optimum. Longer is not worse.

**Do not move the stop to break-even.** Measured at every arm level on both
signal types and it loses at all of them: arming at 1R costs 0.074 R per
confirmed setup (2.5 SE) and drops total R from +53.1 to +34.8. It converts
trades that would have reached target into scratches, and 26% of confirmed
setups reach 3R.

**Do not widen the stop.** `sl_buffer_atr` was swept 0 to 1.0 ATR and 0 is the
peak on both signal types. A naturally wide stop is fine — winners have wider
stops than losers. Adding a buffer to a narrow one is not.

**Do not cut a trade short.** Shortening the horizon from 60 bars to 20 costs
3.3 SE, the only exit result in the whole batch that clears the bar, and it is
a warning rather than an edge.

## Per portfolio

This is where the remaining improvement is. Entry filters have failed 21
times, and a 22nd idea — scanning fewer, more liquid symbols — failed its own
pre-registered test in `universe.py`. Portfolio rules are the one family that
has not been exhausted.

**There is no measured limit on how many alerts to take per day.** Nothing in
this project ever produced one, and a daily quota is not a smaller version of
the rule below — it is a different rule with no evidence behind it. What is
measured is a cap on how many positions are OPEN AT ONCE, which is the thing
that actually competes for capital. Take as many as the slots allow.

**Cap concurrent positions at about 8.** Drawdown falls monotonically as the
cap tightens — no cap 21%, 12 open 16%, 8 open 15%, 5 open 12%, 3 open 9% —
but return falls too, and below 8 it falls faster. Return per unit of drawdown:
no rules 1.30, max 12 1.84, **max 8 2.21**, max 5 0.89, max 3 0.05.

**Reserve capacity for confirmed setups.** The best single rule measured:
+46% return on 13% drawdown, 3.67 return per unit of drawdown, against 2.21
for a plain cap of 8. The mechanism is structural rather than fitted —
confirmed setups are worth 3.4x an early one per signal (+0.227 against
+0.021) and early signals outnumber them 5.6 to 1, so without a rule the worse
signal crowds out the better one purely by arriving first.

**Do NOT cap same-direction positions.** It sounds like correlation control
and it measured badly: 8 open with a 3-direction cap scores 0.47 against 2.21
without. It blocks the winners during exactly the trending moves that pay.

**A daily loss limit is unproven.** -4% scored 2.67, -6% scored 1.54, -10%
never triggered. A single threshold flipping the result like that is noise,
not a rule. Left out.

**Compounding beats flat sizing** — 2.11 against 1.68 — but that is one window
and a rising equity curve; it is what compounding always looks like in a
window that went up.

**Risk 1% per trade.** At 2% the return goes to +59% and the drawdown to 24%;
at 0.5%, +12% and 6%. Return per unit of drawdown barely moves (2.39 / 2.11 /
2.00), so this is a choice about how much pain to accept, not about edge.

**Do not stack every rule.** All of them together scored 2.11, worse than
reserving slots alone at 3.67. Each rule blocks trades and stacking them
blocks the winners too.

## Why the alert volume dropped

The bot sends only signals whose raid landed inside a daily order block or
fair value gap, on both the 30m and 15m charts. That suppresses about two
thirds of what it used to send.

**You are not missing winners.** Measured on the live 60-symbol universe: the
suppressed book is 5399 signals worth **-422.5 R**, and not one suppressed
cell scores above +0.030. The kept book is 2630 signals worth +273.0 R.

This also corrects an earlier version of this file, which said the filter
traded total R for quality. On 23 hand-picked symbols that was true. On the
60 the bot now scans it is not: the wider universe is materially worse per
signal, so the filter cuts more and costs less. The two changes — more
symbols, POI required — are only sound together.

**15m alerts are not a faster version of 30m.** 15m signals measured NEGATIVE
on their own (-0.095 confirmed, -0.039 early) and only turn positive inside a
POI (+0.417 and +0.159). A 15m alert exists only because it passed the filter.
Treat it as equal to a 30m alert of the same letter, not as a lesser one, and
never turn the second timeframe on without the filter.

## Things that sound right and are not

Each of these was tested properly and lost. They are listed because they are
the ideas most likely to come back.

  - **A tighter stop.** Nearest-structure, gap-edge, 5-bar swing, constant-risk
    at a chased entry, and a full 15m setup with a 15m stop: all worse, five
    separate ways. The raid extreme is not a convenient level, it is the price
    beyond which the setup is wrong. Anything nearer sits inside the pullback
    the setup was always going to have. The 15m-stop version halved the win
    rate, 56.5% to 27.3%.
  - **Dropping to 5m or 1m for a sniper entry.** Fill rate rises exactly as
    promised, 69% to 85%, and the stop does get tighter, 1.43% to 0.66%. The
    win rate falls 54% to 33% underneath it, and at 0.66% risk the round-trip
    fee alone is 0.06-0.12 R.
  - **Targeting the opposing liquidity pool.** The nearest one sits at a median
    0.16R, and 95% are below 1R, because the entry is already next to the swing
    price came from. "Target the pool" and "take a 1:3" cannot both be followed.
  - **Candlestick reversal patterns at the zone.** 26 comparisons, nothing
    survived. The one candidate reversed sign on held-out data. Textbook
    Piercing Line and Dark Cloud Cover are structurally IMPOSSIBLE on a 24/7
    perpetual — they need an opening gap, and there are none.
  - **Order-block continuation and FVG-displacement entries.** Both lose
    without a liquidity sweep (-0.056 and -0.036) where the same chart with a
    sweep returns +0.248. The sweep is the edge, not the structure around it.
  - **"The order block should have an FVG next to it."** Worth nothing, and it
    discards 39% of the signals to achieve that.

## What none of this fixes

27% of losing confirmed trades fall on five days out of forty-two. That is
five bad days, not twenty-four bad signals. No entry filter sees it coming and
no stop placement survives it. The concurrency cap is the only thing that
limits the damage, and it limits it rather than avoiding it.

## The honest bar

`/stats` scores forward at 2R, out of sample, fee-inclusive. It has about 71
settled rows and needs 200 or more. Where it disagrees with anything above,
believe it.
