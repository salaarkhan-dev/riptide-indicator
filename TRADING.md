# Trading rules

Everything here is derived from `MEASUREMENTS.md`. Where a rule has no number
behind it, it says so. Nothing in this file is advice about whether to trade —
it is what the measurements say IF you do.

**The single most important caveat:** every number below comes from one
41.6-day backtest window, and the parameters were chosen on that same window.
The one time an effect was held out it came back at 70% of its discovered
size. Assume the same shrinkage applies to all of it.

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
times; portfolio rules have not been tried until now.

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

## What none of this fixes

27% of losing confirmed trades fall on five days out of forty-two. That is
five bad days, not twenty-four bad signals. No entry filter sees it coming and
no stop placement survives it. The concurrency cap is the only thing that
limits the damage, and it limits it rather than avoiding it.

## The honest bar

`/stats` scores forward at 2R, out of sample, fee-inclusive. It has about 71
settled rows and needs 200 or more. Where it disagrees with anything above,
believe it.
