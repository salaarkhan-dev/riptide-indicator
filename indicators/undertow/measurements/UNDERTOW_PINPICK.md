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

## Not shipped

`pinPick` defaults to `PICK_READY`, which is what has always happened;
`undertow_anchor` re-ran bit-identical when the field was added. It is not a
Pine input and not in the watcher, so
[`../../../deploy/undertow-port-check.py`](../../../deploy/undertow-port-check.py)
and the three-way check both hold it at its off value until that changes.

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
Moving the `maxLive` default needs it pinned into `undertow_sweep.py` first —
the one study of twenty-two that does not name it.
