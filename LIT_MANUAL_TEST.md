# LIT_FORWARD_V2 — how to read a setup by hand

For testing on a live chart and on existing bars. Rules copied from the frozen
definition (`riptide/strategies/lit/types.py`, rules hash `4b105c593bc48469`),
not from memory.

## READ THIS BEFORE THE STEPS

**This is not a validated strategy and following it is not expected to make
money.** Three pre-registered experiments each returned INCONCLUSIVE:

| stage | result |
|---|---|
| A | risk unit broken — 99% of losses exceeded 1R, median hold 1 bar |
| B | stop fixed, and the apparent edge disappeared with it |
| C | on untouched symbols, +0.114 R/bet standalone but the paired difference vs the control was +0.068 at z=1.5 — it missed its own bar |

A 162-combination settings grid then showed per-pair tuning decays ~0.95 R/bet
out of sample, and flips sign between 15m and 30m.

All three stages were measured under the V1 engine, which latched on 7.3% of
symbol-timeframes — those charts contributed nothing. That makes their samples
smaller than recorded, and selected toward symbols whose first BOS happened to
break. It does not overturn the verdicts: less power means less evidence, not
contrary evidence. Re-running them under V2 would be a new experiment needing
its own pre-registration, and nobody has done it.

So the honest description of what you are about to do: **collect observations
on a candidate that has not been shown to work.** That is a real and useful
thing to do. It is not the same as trading a tested edge, and if you find
yourself feeling confident after ten good ones, re-read this box.

## 0. CHART SETUP

Load **`riptide-lit-v3.pine`**, not v2. v2 carries a trap state that stops
Main structure emitting altogether on about 7% of charts — BTC 30m is one of
them — and v3 repairs it with the P9 bootstrap CHoCH. `riptide-lit-v2.pine` is
left in the repo untouched so anything recorded under V1 can be reproduced.

Leave every default as shipped — the defaults were matched to the Python
record deliberately:

    Pullback confirmation    Body
    IDM break                Shadow
    BOS break                Body & Sweep
    CHoCH break              Body & Sweep
    Hidden Shadow            pullback off, IDM off, BOS on, CHoCH on
    Outside group [P1]       Close decides
    Tracker re-seed [P3]     Resolver group
    Exact equality [P4]      off
    Track both directions    off
    Bootstrap CHoCH [P9]     Leg extreme (V2)
    Signals follow           Main

Then turn ON, in group 9: **Show entry signals**.

Changing any structure setting means you are no longer testing V2, and your
results cannot be compared with anything already measured.

## 1. THE TREND

Read `Main` structure only. Internal and Deep publish no V2 setups.

* Bullish while the most recent **BOS** is above and unbroken.
* Bearish while it is below.
* Direction changes **only** when CHoCH breaks — never on an IDM break.

**Trade with the trend only.** Long in bullish structure, short in bearish.

## 2. THE IDM

An IDM is the pivot of the most recently confirmed pullback — the liquidity
resting under a bullish leg, or above a bearish one.

It **migrates**: if a newer pullback confirms before the old IDM is taken, the
old one is retired and the newest pivot becomes the IDM. Only the live one
counts. The indicator draws it labelled `IDM`.

## 3. THE SIGNAL — the IDM breaks

Price trades through the IDM level. Break mode is **Shadow**, so the wick
breaking it is enough; the candle does not have to close beyond it.

That candle is the **signal bar**.

## 4. ENTRY

    Entry = the CLOSE of the signal bar. Market order.

Not the wick, not the next open, not a limit back at the level. The close of
the bar that broke the IDM.

## 5. STOP — the part everyone gets wrong

    Stop = the PRIOR confirmed pullback pivot, in the trade direction.
           No buffer. Not the signal bar's low.

The most recent pivot **is** the IDM you just broke. The stop is the pivot
**behind** it — one more step back in the same structural cycle.

**If there is no prior pivot in this cycle, SKIP the setup.** Do not substitute
the signal bar's extreme, the IDM, or anything else. About 16–17% of breaks are
skipped for this reason and that is correct.

This one rule is why Stage A failed and Stage B did not: the signal bar's own
wick gives a median stop of 0.42% of price, which noise takes out immediately
and which 99% of losses exceed. The prior pivot gives ~2.9%, and then losses
land at about 1.00R as they should.

## 6. ACTIVE PRICE — not a target

    1R = |entry − stop|
    Active Price = entry ± (0.5R + round-trip fee)

Fee is 0.032% of price (maker 0.010% + taker 0.022%).

Active Price is **where the trailing stop arms**. You do not take profit there.
Before price reaches it, the original stop is your only exit.

## 7. MANAGEMENT

**Before Active Price** — original stop. Nothing else moves.

**After Active Price is touched** — the trail arms. From then on:

> each time a new pullback pivot confirms **in your trade direction**, move the
> stop to that pivot.

Two rules that are not optional:

* The stop **only ever moves in your favour**. If a later pivot sits worse than
  your current stop, it is ignored.
* A pivot confirmed **on the current bar cannot stop you on that same bar**. Use
  it from the next bar onward.

## 8. EXIT

There is **no fixed target**. You exit when the stop takes you out — the
original one, or the trailed one.

The one exception is the horizon: if 500 bars pass with no stop hit, close at
the market. That is ~10 days on 30m, ~5 days on 15m.

## 9. THE CONTROL — run it on paper alongside

For every setup, also record what a **BOS target** exit would have produced:
same entry, same stop, exit at the locked BOS price.

This is the whole experiment. The trail's standalone P&L cannot tell you
whether trailing helped, because the control is usually positive too. Only

    paired difference = trailed R − BOS-target R

on the **same** setup isolates it. Stage C got +0.068 on that and it was not
enough.

## 10. WHAT TO RECORD, PER SETUP

    symbol · timeframe · direction · signal bar time
    entry · stop · risk as % of price · Active Price
    BOS price · distance to BOS in R
    did it reach Active Price?
    trailed exit: price, reason (stop / trailed / horizon), R
    BOS-target exit: price, R
    paired difference = trailed R − control R

The last line is the one that matters. Everything else is context.

## HOW OFTEN TO EXPECT ONE

Measured over 333 days:

| | one symbol | across 120 symbols |
|---|---|---|
| 15m | one every **7.7 days** | ~15.6/day |
| 30m | one every **18.4 days** | ~6.5/day |

Watching one pair on 30m and seeing a setup a fortnight is correct behaviour,
not a broken indicator. If you want volume you need many symbols, not looser
settings.

## ON RUNNING RIPTIDE ALONGSIDE — read this carefully

You have both enabled. They are **not** the same kind of thing:

* **Riptide** is the production strategy. It is measured, it has a frozen
  control test, and its alerts are graded.
* **LIT** is an open research candidate with three INCONCLUSIVE verdicts.

Using Riptide as confirmation for a LIT setup — "I'll take the LIT entry when
Riptide agrees" — feels prudent and creates a **third strategy that nobody has
ever measured**. It is not Riptide, whose entry, stop and target are different.
It is not LIT_FORWARD_V2, whose whole sample is every setup rather than the
agreeing subset. Filtering by another signal is exactly the kind of choice that
looked good in the settings grid and then decayed by 0.95 R out of sample.

If you want to know whether confluence helps, it is answerable: record the LIT
setups **unfiltered**, note separately whether Riptide also fired within some
window, and compare afterwards. That keeps V2's sample intact and still gets
you the answer. Deciding at the chart, one setup at a time, gets you neither.

**Do not size positions off either of them on the strength of this document.**

## WORKED EXAMPLE — bullish

    1. Main structure bullish, BOS locked above.
    2. A pullback confirms; its low becomes the IDM at 4,300.
    3. An earlier pullback low in the same cycle sits at 4,250.
       ← that is your stop
    4. Price wicks to 4,296, below the IDM. It closes at 4,312.
       ← entry 4,312, signal bar
    5. 1R = 4,312 − 4,250 = 62.   Risk = 1.44% of price.
    6. Active Price = 4,312 + 31 + 1.4 ≈ 4,344.
    7. Price reaches 4,344 → the trail arms.
    8. A new bullish pullback confirms with its low at 4,330 →
       stop moves 4,250 → 4,330, from the next bar.
    9. Price later trades down through 4,330 → exit.
       R = (4,330 − 4,312) / 62 = +0.29R
   10. Control, for the same setup: BOS sat at 4,480 →
       had it been reached, +2.71R; if price stopped at 4,250 first, −1.00R.
   11. Record the paired difference.

Note step 3. If no earlier pullback low exists in that cycle, the setup is
skipped — no trade, and that is the rule doing its job.
