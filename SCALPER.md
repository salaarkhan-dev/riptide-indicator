# Scalper Lab — a separate model family

> ## RESULTS ARE IN — and the answer is "real edge, eaten by spread"
>
> `research/studies/scalp_lab.out`. 14 symbols, 30 days of 1m, gross R.
>
> **One model works before costs.** LSR-4 — price dips below the *previous 5m
> bar's low*, closes back above it, first 1m FVG is the limit entry:
>
> | target | n | gross R | win |
> |---|---|---|---|
> | 1.0R | 13,887 | +0.094 | 55% |
> | 1.5R | 13,887 | +0.152 | 47% |
> | **2.0R** | 13,887 | **+0.202** | 42% |
>
> It clears everything: control −0.36, placebo band −0.084..+0.051, both halves
> +0.212 / +0.197, day-block bootstrap 95% CI **+0.190 .. +0.220**, and it is
> positive on **14 of 14 symbols**.
>
> **Then spread eats it.** Measured live on those same 14 symbols against the
> median 0.259% stop:
>
> | | |
> |---|---|
> | mean net after spread | **+0.027R** |
> | symbols still above +0.15 net | **1 of 14** |
> | symbols net NEGATIVE | **6 of 14** |
>
> And that is the *optimistic* reading: spread sampled once in calm conditions,
> charged once, slippage not modelled at all.
>
> **THE FILTER CAUSED THE PROBLEM IT WAS MEANT TO SOLVE.** The 1m ATR ≥ 0.15%
> floor exists so the stop is wide enough to carry its costs. But at 1m, high
> ATR means *illiquid*: it admitted UAI, RAVE, PONS, AKE, CYS, SKYAI and
> rejected SOL, XRP and DOGE (1m ATR ~0.04%). Volatile and tight-spread are
> nearly mutually exclusive at this timeframe, and the gate that protects the
> denominator wrecks the numerator.
>
> **Verdict: do not deploy.** A +0.027R mean with six symbols negative is not a
> strategy, and the single survivor (PONS, +0.206 net) is one symbol out of
> fourteen — which is what a fluke looks like.
>
> The one route left open was the same model on tight-spread symbols with a
> WIDER stop. **It was run. It works, and it is not a scalper.** See below.

---

> ## THE WIDE-STOP TEST — it passes, and it is a one-hour trade
>
> `scalp_wide.out`, `scalp_wide_timing.out`. Liquid symbols (median spread
> **0.0108%**, three times tighter than the illiquid set), stop taken from a
> deliberate floor instead of the raid.
>
> | target | best floor | discovery net | **HELD-OUT net** | control |
> |---|---|---|---|---|
> | 1.5R | 0.6% | +0.134 | **+0.176** | −0.291 |
> | **2R** | **0.6%** | +0.175 | **+0.199** | −0.284 |
>
> The floor was chosen on the first half and read once on the second. It clears
> the +0.15 bar, the control is strongly negative, and excluding the two
> tokenised stocks in the universe *improves* it to **+0.200R** — so that
> contamination was not carrying the result.
>
> ### But it is not a scalp, and the timing says so plainly
>
> | | |
> |---|---|
> | median time to resolve | **58 minutes** |
> | 90th percentile | 119 minutes (the horizon cap) |
> | never resolved in 2h | **32%** |
>
> A 0.6% stop on a symbol whose 1-minute bar moves 0.04% is **fifteen times its
> 1m ATR**. Of course it takes an hour. This is a one-hour mean-reversion trade
> that happens to be *triggered* by a 1-minute pattern, and it should be named
> and tested as one — exactly what this file predicted before the data arrived.
>
> ### Two reasons not to get excited yet
>
> **The held-out half is 15 days.** Riptide's numbers come from 333 days split
> in two. Here the whole window is 30 days because *MEXC serves no more 1m
> history than that*. A crypto regime lasts longer than 15 days, so this split
> can be passed by a strategy that merely suits the month. It is the weakest
> validation in this project, and it is weak for a structural reason that no
> amount of care can fix.
>
> **The trade count is not reachable.** 13,862 trades over 30 days and 14
> symbols is ~460 signals a day, each held about an hour. You cannot hold 460
> hour-long positions. The +0.199R is per *signal*, and phase2_rule.py already
> showed what happens when slots bind: the per-trade number and the account
> number are different animals. **Nothing here has been through an account
> simulator yet**, and until it has, this is a pattern rather than a strategy.


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

| id | model | TF | new parameters | RESULT |
|---|---|---|---|---|
| **LSR-2** | 5m liquidity → 1m MSS → 1m FVG | 5m+1m | **none** | reject (+0.002) |
| LSR-1 | 5m liquidity → 1m raid → displacement → FVG | 5m+1m | displacement threshold | reject (+0.111) |
| **LSR-4** | previous 5m H/L raid → 1m reversal | 5m+1m | none | **gross +0.202, net +0.027** |
| LSR-3 | 3m liquidity → 1m displacement → FVG | 3m+1m | displacement threshold | no trades |
| LSR-5 | micro MSS → FVG | 1m | none | reject (−0.033) |
| LSR-6 | prev 5m H/L → displacement | 5m+1m | displacement threshold | +0.196 — same as LSR-4, so the parameter adds nothing |
| LSR-7 | opening-range raid | 1m/3m | session + range length | reject, inside placebo |

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
