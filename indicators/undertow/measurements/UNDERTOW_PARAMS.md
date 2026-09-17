# Undertow parameters, 15m / 30m / 1h — the holdout says no

Run by `indicators/undertow/studies/undertow_sweep.py` against
[`PREREG_undertow_params.md`](../prereg/PREREG_undertow_params.md), committed
before the first number. 23 MEXC perpetuals, 12,000 bars per symbol per
timeframe, 7bp round-trip fees, seed 20260917.

## The result

| tf | chosen on train | train | **holdout** | **control** | n | bars passed |
|---|---|---|---|---|---|---|
| Min15 | `bar 15/3 · flip · rr3 · htf4` | +0.284 | **−0.093** | **+0.184** | 45 | 0 of 6 |
| Min30 | `range 0.40/0.12 · flip · rr3` | +0.348 | **+0.071** | **+0.108** | 153 | 3 of 6 |
| Min60 | `bar 15/3 · flip · rr3` | +0.223 | **−0.063** | **−0.064** | 136 | 0 of 6 |

All figures are mean R per trade, net of fees, SEs clustered by symbol.

**Nothing cleared all six bars, and bar 4 — beat a seeded random entry — was
not cleared on any timeframe.** On 15m the random control *beat* Undertow by
0.28 R per trade. On 30m it beat it by 0.04. On 1h the two were identical to
three decimal places: **−0.063 against −0.064**.

The control is the same symbol, the same quadrant, the same direction, the same
risk, the same `rr` and the same holding window — the only thing that differs is
*when* it entered. Undertow's answer to "when" is worth nothing.

## What selection bought, measured three times

| tf | train | holdout | shrinkage |
|---|---|---|---|
| Min15 | +0.284 | −0.093 | **−0.377** |
| Min30 | +0.348 | +0.071 | **−0.277** |
| Min60 | +0.223 | −0.063 | **−0.286** |

Picking the best of 48 configurations bought about **+0.31 R per trade of pure
illusion**, consistently, on all three timeframes. That is the number to hold on
to the next time a panel on a single chart reads +0.37.

It is also almost exactly what the prereg predicted it would be, for the reason
the prereg gave: the expected maximum of 48 draws under the null is about 2.4 SE
above zero, and 2.4 × ~0.17 ≈ 0.4.

## THE POWER LIMIT, stated before anything else is read into this

45, 153 and 136 closed trades. At `rr = 3` the per-trade SD is about 1.8, so the
clustered SE is ~0.17 R and the **minimum detectable effect at 80% power is
roughly ±0.5 R per trade**.

**This study can rule out a large edge. It cannot rule out a small one.** What
it refutes is the +0.27 to +0.45 R the four single charts appeared to show; an
edge of +0.1 R would be invisible here and is not excluded. Anyone quoting
"Undertow does not work" from this file has to quote this paragraph with it.

## Three things that ARE settled

### 1. The bias gate is earning its place, and I was wrong about it

Before this ran I argued the gate was probably harmful: arming requires a close
beyond *both* pin extremes, so a setup always arms while the pullback is
deepening, which is exactly when the minor structure turns against the trend.
Anti-correlated with the setup by construction. That structural argument is
correct and its conclusion was wrong.

The ghost column — cancelled setups walked forward anyway — says:

| tf | armed setups cancelled | of those, would have filled | worth each | verdict |
|---|---|---|---|---|
| Min15 | 16 | 9 | **−0.607 R** | gate **saved 5.5 R** |
| Min30 | 85 | 50 | **−0.396 R** | gate **saved 19.8 R** |
| Min60 | 84 | 44 | **−0.485 R** | gate **saved 21.3 R** |

Every timeframe, same sign, and the cancelled setups are much worse than the
population. **Letting a triggered setup survive a bias flip would have cost
money on all three.** Do not remove that gate.

Which of the five rules does the work, on the holdouts:

| | minor | sweep | stale | retrace | adx |
|---|---|---|---|---|---|
| Min15 | 6 | 9 | 0 | 1 | off |
| Min30 | 41 | 31 | 3 | 10 | off |
| Min60 | 43 | 29 | 3 | 9 | off |

`End: minor structure` and `End: extreme swept` carry it. `End: no new extreme`
fires almost never at 30 bars and `End: retraced %` at 70 fires rarely — both
are close to free, and close to useless, as configured.

### 2. The swing unit is a real fix for a real problem, and it is not an edge

`range 0.40/0.12` won the Min30 train; `bar 15/3` won Min15 and Min60. No
consistent winner, and the one timeframe where the scale-invariant unit won is
also the only one whose holdout was positive — on 153 trades at z = +0.73, which
is nothing.

The scale invariance itself is not in doubt; it is measured in
`tests/test_undertow_port.py`, across a 4:1 aggregation:

| | swings per unit time survive at |
|---|---|
| bar pivot 15 | ×0.30 |
| k × ATR(14) | ×0.22 |
| k × 24h range | ×0.89 |

So the answer to *"each works different on different TF"* is: **yes, and
`swingSrc="range"` fixes it — it just does not pay you for fixing it.** Use it
because one setting then means one thing on every chart, not because it makes
money.

Worth recording that the obvious version of this idea was wrong. `k × ATR` was
implemented first and is **worse than the bar pivot it replaces**, because
aggregating four bars multiplies per-bar ATR by ~√4 and so doubles the
threshold. A per-bar quantity cannot be the unit, because the bar is what
changes. The test caught it before the study ran.

### 3. The HTF gate is underpowered, not useful

Selected only on Min15, where it cut the holdout to **45 trades**. Every other
panel chose `htfMult = 0`. It removes most of the sample for a change in mean R
that cannot be measured at this size. It stays available and stays off.

## What happens now, per the prereg

**Undertow stays a research bench.** No alert, no `riptide/watchers/undertow.py`,
no digest line. The holdout is spent — these 11 symbols' newer half cannot score
a second configuration, and a follow-up question needs its own pre-registration
and its own data.

The honest summary is short: the four charts that started this were 176 trades
at +0.22 ± 0.11 R, chosen by looking, and two of them were the same metal on two
venues disagreeing by 0.89 R. Against 334 holdout trades that were not looked
at, the same rules score **−0.093, +0.071 and −0.063**, and lose to a coin flip
of the same shape on two of three.

## What would actually move this

Not another parameter. The three levers this study says are worth a *new*
prereg, in order:

1. **The fill.** `back` and `gone` are the two largest no-entry buckets on every
   panel, and `gone` — the target printing before the limit filled — means the
   whole move was available at a worse price. A backup fill at an OB or FVG was
   in the original spec and is still unbuilt. That changes the trade count, not
   the entry rule, which is the only kind of change that can help at this
   sample size.
2. **More data.** 12,000 bars is 125 days on 15m. The MEXC endpoint pages back
   further and the study already knows how; the binding constraint on every
   verdict above is n, not the strategy.
3. **A reason to expect an edge.** Every finding here is consistent with "the
   pin adds nothing to the structure bias". The bias gate demonstrably sorts
   good from bad; the pin has never been shown to. A study that scored the bias
   alone — enter on any counter-trend-coloured bar at the pullback extreme, no
   wick test — would say whether the candle taxonomy is carrying anything at
   all. It is the cheapest remaining question and nobody has asked it.
