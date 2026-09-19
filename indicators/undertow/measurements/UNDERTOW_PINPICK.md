# Picking the pullback's candle by price: the stated goal, and another null

From [`undertow_pinpick.py`](../studies/undertow_pinpick.py). **DESCRIPTIVE** —
the spent 23-symbol set, no prereg, no holdout, nothing promoted. Shorts only.

Unlike [`UNDERTOW_PINLAG.md`](UNDERTOW_PINLAG.md), this page's `BASE` is pinned
to what ships **today**: `msLen 14`, the pullback-extreme stop, the
direction-only bias gate, the local pullback anchor.

## The question

`pinLag = 1` — "take the second-last qualified candle" — is a rule about
**position**. Asked why he uses it, the strategy's author described a rule
about **price**:

> "sometimes after the last candle market never closes above its working line
> and goes straight down, that's why we choose 2nd last so the next candle will
> go above its working line"
>
> "the main goal is for short trend how much up possible we can enter, not that
> much up so we miss the entry W→F"

`pinPick = PICK_BEST` answers that directly. For a short the pin is a hammer,
so Working is a close **above** its high and Failure a close **below** its low;
W therefore spreads **downward** through the pullback's candles and F spreads
**upward**. The confirming set is known exactly on every bar with no lookahead,
and its highest member is the best short entry available at the moment an entry
exists — higher pin, same stop, tighter risk.

## The verdict — R per pullback OFFERED

`R/armed` flatters lag 1, because it is the average of a minority the rule
selected itself. The deciding unit charges each rule for the pullbacks it
passed on.

| arm | Min15 | Min30 | Min60 |
|---|---|---|---|
| **A** `pinLag 0` newest | −0.044 | +0.019 | −0.005 |
| **B** `pinLag 1` — ships | −0.013 | +0.013 | +0.007 |
| **C** `PICK_BEST` | −0.036 | +0.047 | −0.014 |
| **C − B**, clustered by symbol | −0.027 ±0.033 | +0.041 ±0.040 | −0.022 ±0.028 |
| z | −0.83 | +1.04 | −0.80 |
| symbols agreeing | 9/23 | 13/23 | 9/21 |

**NULL.** The signs disagree across all three timeframes, no z reaches 1.1, and
no more than 13 of 23 symbols agree on any of them.

## What is not null: frequency

| arm | Min15 armed | Min30 | Min60 |
|---|---|---|---|
| A `pinLag 0` | 2230 | 2126 | 1974 |
| **B `pinLag 1` — ships** | **447** | **456** | **430** |
| C `PICK_BEST` | 3236 | 3102 | 2990 |

**Seven times as many armed setups as what ships**, because `pinLag` refuses
every pullback offering a single qualifying candle and this does not. It also
arms more than plain newest-wins, because the supersede deletes rivals that
would have confirmed when the survivor did not.

## What the pick actually does — 72 real disagreements, Min30, 8 symbols

| | |
|---|---|
| same candle, armed **earlier** | **63 of 72** |
| a genuinely **different** candle | **9 of 72** — and all nine later AND higher |
| mean risk per trade | **1.249% → 1.168%** (6.5% tighter stop) |
| bars where more than one candidate confirmed | 406 / 372 / 471 of ~3000 arms (~13%) |

So most of what it does is **arm sooner** — `PICK_BEST` fires at the first
confirmation while `pinLag` waits for its count to come true. The candle choice
itself changes about one arm in eight, and when it does it goes the way the
stated goal says it should, every time.

## The honest reading

The mechanism matches the stated goal, the frequency cost of the proxy
disappears, the risk per trade is measurably tighter on the trades where the
two disagree — and **the expectancy is not measured as better**. Three
timeframes, three signs, nothing resolved.

That is the same shape as every other finding in this project, and the same
conclusion follows: prefer it because it is the rule, not because it pays. The
instrument that can settle whether it pays is the forward record.

## SHIPPED, against this page

`pinPick = PICK_BEST` is the default in all three copies as of 2026-09-19, on
the strategy author's instruction and with the null above unchanged. Two other
defaults moved with it because neither makes sense alone:

* **`pinLag` 1 → 0.** They are different answers to the same question and the
  lag runs **first**, so at 1 it refuses candles the pick would have chosen —
  the pick would be selecting from what the proxy left, which is the proxy
  still deciding.
* **`maxLive` 4 → 8.** See the regression below. Both rules skip the
  newest-wins supersede, and a cap of 4 then discards pins for no reason but
  pool size.

**The reason is the mechanism, not this page.** It is the rule he described
when asked why he uses the proxy, it arms the setups he takes, and the backtest
has never seen which setups he takes or how long he holds them. The instrument
that can settle whether it pays is the forward record.

**The operational consequence is the alert rate.** Seven times the armed setups
of `pinLag 1` reaches Telegram, not just the chart.

## A regression this study found

`pinLag > 0` skips the newest-wins supersede, so the candidate pool no longer
collapses to one per pullback — and the chart's `Live setups at once` default
is **4**. Min15, 6 symbols:

| rule | pins refused at maxLive 4 | at maxLive 8 |
|---|---|---|
| `pinLag 0` | 0 | 0 |
| **`pinLag 1` — ships** | **412 — 6.6% of pins** | 3 |
| `PICK_BEST` | 261 — 4.2% | 0 |

It costs about 4% of armed setups and was not flagged when `pinLag` shipped.
**Fixed with this ship: `maxLive` 4 → 8 in all three copies.**

`maxLive` was not in `PINNED` either. Twenty-one of twenty-two studies passed
`maxLive=64` so nobody had noticed, but `undertow_sweep.py` ran at the
**default** and its page would have been silently re-pointed by a cap change
that has nothing to do with what it measures. Pinned there at 4 — its published
value — and in `undertow_ablation.py`, which overrides the cap per run but
never named it in its baseline. That is the fifth field caught unpinned on the
day its default moved.
