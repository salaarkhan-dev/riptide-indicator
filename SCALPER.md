# Scalper Lab — a separate model family

Riptide's Min30 liquidity-reversal model is **frozen** and is the control.
Nothing in this file touches it, shares its tables, or appears in its `/stats`.
Each experiment here gets its own id, its own rows, and its own verdict.

The reason for the wall is not tidiness. Every number in `MEASUREMENTS.md` is
worth what it is because the thing it measured did not change underneath it. A
scalping idea that quietly borrows Riptide's counters would cost more than it
could ever earn.

---

## The gate came first, and it changed the design

`research/studies/scalp_viability.py` asked whether **any** 1m entry can pay for
itself before a single entry rule was written. The arithmetic that decides it:

```
cost in R  =  cost as % of price  /  stop distance as %
```

The numerator barely moves between timeframes. The denominator collapses. This
project already learned that one timeframe up and did not generalise it —
`fee_key.out` has 15m at a 1.01% median stop going **net negative** on 4625
trades while 1h at 2.04% keeps 73% of its gross.

**I expected this to kill the branch. It did not.** Measured on 30 days of real
1m candles and a live book:

| symbol | rank | 1m ATR | spread | cost in R @2×ATR |
|---|---|---|---|---|
| **BTC_USDT** | 0 | 0.044% | 0.000% | **0.23** |
| ZEC_USDT | 3 | 0.176% | 0.001% | **0.00** |
| LSK_USDT | 10 | 0.098% | 0.012% | 0.16 |
| BEAT_USDT | 25 | 0.363% | 0.110% | 0.15 |
| PONS_USDT | 50 | 0.559% | 0.033% | 0.03 |
| BTW_USDT | 80 | 0.279% | 0.032% | 0.06 |
| VIRTUAL_USDT | 110 | 0.124% | 0.016% | 0.06 |

At the median that is **0.05R** — perfectly survivable, and far better than I
predicted.

### But read the BTC row, because it inverts the usual intuition

BTC has the *tightest spread on the exchange* and the **worst cost ratio here**.
Its 1m ATR is 0.044%, so a 1×ATR stop is 44 basis points of a percent — and its
0.02% taker fee alone is **46% of that risk**. The majors are the *worst* 1m
candidates, not the best, and for exactly the reason 15m loses: a stop too small
to carry its own costs.

### So the universe filter is part of the strategy, not an afterthought

Two hard admission criteria, before any entry logic:

1. **`takerFeeRate == 0`.** 82 of 120 symbols qualify today (68%). On a
   fee-paying symbol a 1m stop pays roughly ten times the cost ratio of a 30m
   one.
2. **1m ATR ≥ ~0.15%**, so a 2×ATR stop is ≥ 0.30% and costs stay under a tenth
   of risk.

### And the numbers above are a FLOOR, which is the important caveat

The spread was sampled **once, in calm conditions**. A stop-out happens in the
opposite conditions — the market is moving fast and the book is thin exactly
when the market order goes in. Slippage beyond the spread is not modelled here
and cannot be.

**Spread has no history on this exchange** (`exchange_surface.out`: the book is
live-only). So a 1m strategy's true cost is *unbacktestable*. That forces the
sequence below and is the single most important structural fact in this file.

---

## The sequence, and why it is this order

**1. Backtest GROSS only.** Never quote a net number from a 1m backtest — the
cost input does not exist historically. Gross R is what the pattern is worth
before execution.

**2. Log spread forward, from day one.** A per-symbol spread sample on every
signal, stored with the hypothetical trade. Six weeks of that is the only way a
net number ever becomes honest, and it can run while the backtests do.

**3. Judge net only when 2 has enough rows.** A gross +0.15R with an unmeasured
cost is not a result, it is a hypothesis with a decimal point.

Every hypothetical scalp records: spread at signal, spread ÷ stop distance,
estimated entry slippage, estimated exit slippage, fee, gross R, net R.

---

## The models, and one change to the ordering

The proposed ranking put displacement first. **I would flip the top two**, on a
principle this project has paid for repeatedly.

| id | model | TF | new parameters |
|---|---|---|---|
| **LSR-2** | 5m liquidity → 1m MSS → 1m FVG | 5m+1m | **none** |
| LSR-1 | 5m liquidity → 1m raid → displacement → FVG | 5m+1m | displacement threshold |
| LSR-4 | previous 5m H/L raid → 1m reversal | 5m+1m | none |
| LSR-3 | 3m liquidity → 1m displacement → FVG | 3m+1m | displacement threshold |
| LSR-5 | micro MSS → FVG | 1m | none |
| LSR-6 | failed breakout → displacement | 1m/3m | breakout definition |
| LSR-7 | opening-range raid | 1m/3m | session + range length |

**Why LSR-2 before LSR-1.** "Displacement" is not a primitive this engine has.
Defining it mechanically needs a threshold — *how large is a strong candle?* —
and that threshold will be chosen by looking at results. MSS and FVG already
exist, are already calibrated against the Pine indicator, and add **zero new
tunables**.

Twenty-one entry filters have failed here, and the pattern in the failures is
consistent: the ones with a free parameter fit the discovery half and died on
the held-out half. The trendline slope gate is the cleanest example — +9.0pp at
4.4 SE on discovery, −3.1pp held out.

LSR-1 is still worth running. It should just not be the one that sets the
branch's priors, and when it runs, its displacement threshold must be **chosen
on one half and read on the other**, like `funding_holdout.py` does.

LSR-7 is ranked last deliberately: a session-based idea adds a time-of-day
parameter to a market that trades 24/7, and this project has no measured
session effect to anchor it.

---

## The first hypothesis, stated tightly enough to reject

> A 5-minute liquidity level is raided on 1m. Price then produces a 1m MSS
> against the raid. The first 1m FVG after that MSS is the limit entry. The stop
> goes beyond the raid extreme. Evaluate 0.75R / 1R / 1.25R / 1.5R / 2R on
> **gross** R, over zero-fee symbols with 1m ATR ≥ 0.15%, with both halves
> reported and an opposite-direction control.

Pre-registered before the first number, in the file that runs it.

---

## Sizing: the dollar figure is an output

A $4–5 target is not a strategy parameter. Derive it:

```
account          300 USDT
risk             0.5%        -> 1.50 USDT at risk
stop distance    0.35%       (2x ATR on a qualifying symbol)
position notional  1.50 / 0.0035  = 428 USDT
margin at 20x    21 USDT
target 1.5R      2.25 USDT gross
cost 0.05R       0.08 USDT
net              ~2.17 USDT
```

To reach $4.50 net at 1.5R you need roughly **$600 of account at 0.5% risk**, or
the same account at 1% — not a different strategy. The bot should print this
whole chain per signal so the number is visible rather than assumed.

**Leverage is not in the edge.** It sets margin, not risk: position notional and
stop distance fix the dollar loss, and 5× versus 50× changes neither. What high
leverage *does* change is liquidation distance — at 50× that is roughly 2% away,
which is fine against a 0.35% stop, and at 100× it is ~1%, which starts to
matter on a symbol whose 1m ATR is 0.5%. Cap leverage so liquidation sits at
least 5× the stop distance away, and let margin fall where it falls.

---

## What would make me stop

- Gross edge under ~0.15R. Below that the unmeasured costs decide the outcome
  and no amount of forward logging rescues it.
- An effect that needs the fee-paying symbols to reach significance — that is
  the 15m result being rediscovered.
- A displacement or breakout threshold that only works inside a narrow band.
- Any result that reverses between halves.

## What stays true regardless

Riptide Min30 stays frozen, keeps its own tables, and remains the control. If
the scalper branch produces nothing, that is a result too — it is the fourth
independent time this project will have found that adding timeframe resolution
does not add edge.
