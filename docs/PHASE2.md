# Phase 2 — automated execution

Phase 1 sends messages. Phase 2 places orders. Everything in `MEASUREMENTS.md`
and `TRADING.md` still applies; this file is only about what changes when a
machine acts on it instead of a person.

**Nothing here is advice about whether to automate.** It is what has to be true
for the automation to be worth trusting, and what is still unknown.

---

## The one thing automation actually buys

Not speed, and not more trades. **Discipline.**

Every rule this project measured assumes a limit order at the stated entry,
filled or expired within 10 bars, with the stated stop and a 2R target, and no
break-even. A person deviates from that constantly and invisibly. A single
afternoon of live alerts produced all of these:

- price ran 0.25% past the entry and chasing it would have turned a 2.0R trade
  into 1.0R — the same stop, the same target, half the trade
- a signal whose count conflicted with the trade tempted a skip
- an unfilled limit tempted a move to a "better" price

A bot does none of that. It places the limit, waits 10 bars, cancels. **That
fidelity is the product.** If the automation is not more faithful to the
measured rules than the human is, it has no reason to exist.

## The one thing it costs

New failure modes that a person does not have, all of them fast:

| failure | consequence |
|---|---|
| retry loop places the same order twice | double size, silently |
| fill arrives, stop placement fails | an unprotected position |
| restart loses local state | a position nobody is managing |
| config typo in size | one trade at 50x intended risk |
| runaway loop | rate-limited out of the market mid-trade |

Phase 1 already proved the last one can happen: on 12 Sep a quarter of the
universe went unscanned for hours and every log line looked normal. Assume the
same class of bug will happen in phase 2, and design so that when it does,
nothing catastrophic follows from it.

---

## Non-negotiables

These are not tunables. Each one exists because its absence has a specific,
plausible, expensive failure.

**1. Sub-account, funded with what you can lose.** A bug cannot reach what is
not in the account.

**2. API key: trade permission only. NO withdrawal. IP-whitelisted to the box.**
A leaked trade-only key costs you a bad position. A leaked withdrawal key costs
you the balance. Stored in `/home/ubuntu/riptide/.env`, `chmod 600`, owned by
`ubuntu`, never printed, never in a systemd unit, never committed — the same
rules the Telegram token already follows.

**3. Idempotent orders.** Client order ID is a deterministic function of the
signal's dedupe key. The same signal can never place two orders, no matter how
many times a retry, a restart or a duplicated scan replays it. **This is the
single most important safety property in the system** — it is what makes every
other retry safe.

**4. The exchange is the source of truth.** On every cycle and on every start,
read positions and open orders from the exchange and reconcile against what the
database expects. Local state is a cache and is assumed stale.

**5. Protective orders live on the exchange, not in the bot.** Stop and target
are placed as exchange-resident orders immediately on fill. If the process dies,
the position is still protected. A bot that "watches for the stop level" is a
bot that stops watching when it crashes.

**6. Two separate kill switches.**
- `/halt` — cancel all working orders, place no new ones. Positions stay open.
- `/flatten` — close every open position at market.

They are different decisions and must be different commands. `/halt` is the one
you reach for when something looks wrong; `/flatten` is the one you reach for
when you know it is.

**7. Hard caps in code, not config.** Maximum orders per minute, maximum
notional per position, maximum concurrent positions. A config file typo must not
be able to place a hundred orders. The cap is a constant with a test.

**8. Circuit breaker on surprise.** If reconciliation finds anything unexpected
— a position nobody opened, a size mismatch, a missing stop — **halt and alert.
Do not self-heal.** An automated fix applied to a state you do not understand is
how a small bug becomes a large one.

---

## What the measurements say to do

From `TRADING.md`, which is derived from `MEASUREMENTS.md`. Where a number is
unstable or unmeasured, it says so.

| rule | setting | why |
|---|---|---|
| Risk per trade | **0.5%** | Chosen. A pain choice, not an edge choice — ret/DD barely moves across 0.5/1/2%. At 0.5% on the picked stream the study below shows +175% on 15% max drawdown over 333 days. |
| Concurrent positions | **max 8** | Kept as a safety bound, not for return: on the picked stream it blocks 9 trades in 333 days. The old justification ("drawdown falls monotonically as the cap tightens") was an artifact of the simulator leak — corrected, it is not even ordered. |
| Reserve for confirmed | **none** | Best rule for the SENT stream, a drag on the PICKED one: 8.77 against 11.74, and 2.81 against 5.54 on the first half. The pick rule already ranks confirmed ahead of early inside its window. |
| Same-direction cap | **none** | Sounds like correlation control, measured badly on the sent stream (0.47 against 2.21) and never re-asked on the picked one. Left out, and flagged as unmeasured rather than settled. |
| Daily loss limit | **none** | Unproven, and its numbers came from the leaking simulator. Post-fix the −4% and −6% stops rank 2nd and 3rd on the sent stream, which is a reason to re-ask the question, not to ship one. |
| Break-even | **off** | Loses at every arm level on both signal types. Arming at 1R costs −2.5 SE and drops total R from +53.1 to +34.8. It converts trades that would have reached target into +0.1R scratches. |
| Entry | **limit at the stated entry** | This is literally what was backtested: "bars after the gap forms in which a limit at the entry may fill." |
| Fill window | **10 bars, then cancel** | Past this the backtest records "never filled", which is a result, not a discard. ~19% of grade B never fill and the +0.173 R/signal is the average *after* those misses. |
| Target | **2R** | Measured monotone 1R +20.4, 1.5R +39.5, 2R +52.8, 3R +61.9 total R, though each step is ~1.5 SE. |
| Daily quota | **none** | No measured limit on how many alerts to take per day ever came out of this project. Slots are the scarce resource, not signals. |

**Do not stack every rule.** Each rule blocks trades, and stacking them blocks
the winners too. The study below is the clearest case: adding confirmed-slot
reservation on top of the pick rule costs half its first-half score.

---

## ANSWERED — which rule the bot trades

`research/studies/phase2_rule.out`. 59 symbols, 333 days, 15m+30m+1h, 300 USDT
at 10x, maker/taker fees, risk 0.5%. Of 9071 signals sent, 2905 (32%) carry a 🎯.

| arm | fed | taken | win | ret | maxDD | **ret/DD** | 1st half | 2nd half |
|---|---|---|---|---|---|---|---|---|
| everything, no rules | 9071 | 8832 | 36% | −29% | 89% | −0.33 | −0.80 | +2.49 |
| slots: max 8 | 9071 | 5734 | 36% | −12% | 74% | −0.16 | −0.69 | +1.50 |
| slots: max 8 + 3 confd | 9071 | 4281 | 35% | −51% | 70% | −0.72 | −0.83 | +0.31 |
| PICK only, no cap | 2905 | 2905 | 38% | +164% | 15% | 10.99 | 4.70 | 4.04 |
| **PICK + max 8** | 2905 | 2896 | 38% | **+175%** | **15%** | **11.74** | **5.54** | **4.22** |
| PICK + max 8 + 3 confd | 2905 | 2749 | 38% | +143% | 16% | 8.77 | 2.81 | 4.16 |
| PICK + max 8, no 15m | 1051 | 1051 | 39% | +53% | 13% | 4.14 | −0.13 | 6.63 |
| slots 8 + 3 confd, no 15m | 4449 | 2494 | 36% | −1% | 50% | −0.03 | −0.71 | +1.75 |

**The pick rule wins and it is not close.** Every take-everything-then-cap arm
is NEGATIVE over the full window and negative in the first half. Every pick arm
is strongly positive in **both** halves — the only arms in the table that are.

**The slot rules never had an edge to allocate.** They were rationing a stream
measured at recovery 0.05. Capping how much of nothing you take does not make it
something; it just loses more slowly (−0.33 → −0.16).

### So: `SELECT = the 🎯 pick, hard cap 8 concurrent.`

Three consequences, each of which contradicts something written above it:

**1. Do NOT reserve slots for confirmed.** 8.77 against 11.74, and 2.81 against
5.54 on the first half. It is the best rule for the *sent* stream and a drag on
the *picked* one — the pick rule already ranks confirmed ahead of early inside
its own window, so reserving slots just blocks picks that had already won the
comparison. `TRADING.md`'s recommendation does not transfer.

**2. Do NOT exclude 15m.** This is the reverse of what the fee arithmetic
predicted, and the reason is that the pick rule *selects within* the timeframe:

| stream | n | net R/trade |
|---|---|---|
| 15m **sent** | 4622 | **−0.024** |
| 15m **PICKED** | 1854 | **+0.064** |
| 30m sent / picked | 2798 / 634 | +0.030 / +0.070 |
| 1h sent / picked | 1651 / 417 | +0.048 / +0.112 |

15m is a losing timeframe to take wholesale and a winning one to take
selectively. Dropping it removes 64% of all picks and takes ret/DD from 11.74 to
4.14 — and makes it *unstable*, −0.13 in the first half against +5.54 with 15m
kept. **Keep it.**

**3. The cap barely binds, and that is fine.** 2905 fed, 2896 taken — it blocks
9 trades in 333 days. It is worth keeping anyway: it costs nothing measurable
and it is the only thing standing between a bug and an unbounded position count.

### Still to check before stage 1

The 🎯 stream is ~2905 trades over 333 days — about **8.7 a day**, well above the
8-slot cap in bursts. The cap's near-zero bite above says the two rarely collide,
but that is a backtest with instant fills. Shadow mode should count how often a
pick is refused for want of a slot in live conditions.

---

## What is still OPEN

### 1. ~~Which selection rule the bot trades~~ — ANSWERED ABOVE

Kept for the record, because the *reason* it went unasked for so long matters.

The project has **two** selection rules and they have never been compared,
because they live in incompatible harnesses:

|  | data | judged on |
|---|---|---|
| **Slot rule** (`portfolio.py`, `TRADING.md`) | ~42 days, **one** timeframe | 300 USDT account, ret/DD |
| **Pick rule** (`decide.py`, `band_key.py`) | 333 days, **three** timeframes | R per trade, recovery factor |

`research.data.load()` fetches one interval per symbol, so it is
single-timeframe by construction — and the pick rule's *first* ranking key is
"slowest timeframe first". The pick rule cannot be expressed in the slot rule's
harness at all.

A human holds both comfortably: read the 🎯, respect the slots. **A bot cannot.**
It needs one rule that answers, per signal, "do I place this order?"

`research/studies/phase2_rule.py` rebuilds the comparison on the 333-day
three-timeframe pipeline and runs `portfolio.simulate()` over it, so the judge
is the same code and only the rows change.

**This is now resolved — see the answer above.**

### 2. ~~The old portfolio number is not stable~~ — it was a BUG, not drift

My first reading of this was wrong, and the wrong reading was the comfortable
one. Rerunning `portfolio.py` unchanged gave 5.47 where `TRADING.md` records
3.67, and I wrote that off as a window sliding forward — "the ordering survived,
the levels did not."

It was a leaking simulator. `portfolio.py` sorted a trade's close ahead of its
own open at equal timestamps, so a trade that filled and stopped inside ONE bar
had its close silently dropped and its open parked in a dict nothing would ever
clear. The first `max_open` of those pinned every slot **permanently**: the
account traded month one and then sat frozen for eleven months, reporting a
plausible return on a flattering drawdown.

353 of 9071 rows are same-bar stop-outs. Fixed in `portfolio.py`, with the
correction table in `TRADING.md`.

**What it cost:** on the 41.6-day window the recommended rule went from 138
trades to 489, and its drawdown from a reported **13% to an actual 34%** — the
one number anyone sizing an account would have used, wrong by nearly 3×. The
claim that *"drawdown falls monotonically as the cap tightens"* was pure
artifact: tighter caps leak slots faster.

**The lesson worth keeping:** the tell was visible in the output all along —
`max 12 open` and `everything, no rules` returned byte-identical rows, which no
real cap does. Two separate reruns printed it and I read past it both times. A
simulator that silently drops events produces numbers that look exactly like
numbers.

### 3. ~~15m may have to be excluded entirely~~ — ANSWERED, and reversed

I predicted from the fee arithmetic that a bot must not be given 15m. The
measurement says the opposite: picked 15m is **+0.064** net R/trade against
**−0.024** sent, and excluding it takes ret/DD from 11.74 to 4.14. See above.

The fee argument was not wrong, it was incomplete: `fee_pct / risk_pct` still
makes 15m roughly twice as expensive per unit of risk as 1h, which is exactly
why picked 15m (+0.064) trails picked 1h (+0.112). It just does not make it
negative once the pick rule has chosen which ones to take.

### 4. ~~Minimum order size at minimum capital~~ — checked, not a problem

I assumed minimum order sizes would block most signals at minimum funding.
Probed `contract/detail` across the 120-symbol universe on 12 Sep:

| minimum order notional | symbols |
|---|---|
| median | **$1.03** |
| cheapest (SHIB) | $0.005 |
| over $10 | 13 of 120 |
| over $50 | 2 of 120 |

At 0.5% risk on a small account a position is on the order of $100 notional, so
**107 of 120 symbols are placeable at stage 1**. The bot must still skip the
handful it cannot afford, and count them — but "most signals unplaceable" was
wrong.

### 5. The fee assumption is CONSERVATIVE, and by a lot

Every number in this project — `fee_key.out`, `phase2_rule.out`, the claim that
15m is net −0.0268 — is computed at **0.02% maker / 0.06% taker**. The live
schedule is not that:

| | zero rate | of the 120-symbol universe |
|---|---|---|
| maker | **118 / 120** | 98% |
| taker | **81 / 120** | 68% |

Many symbols sit in a `mc-trade-zone-0fees` concept plate. The backtest is
therefore charging fees that most of the universe does not currently pay, which
means every result here is a **floor, not a forecast** — the safe direction to
be wrong in.

**It cannot simply be rerun at zero.** Today's schedule says nothing about what
the rates were across the 333-day window, and promotional zones end. The honest
statement is that the measured numbers understate, by an amount nobody has
bounded. Worth a sensitivity arm (fees off vs fees in) before stage 2 sizing,
and worth re-checking the plate membership periodically, since a symbol leaving
it silently raises the cost of every trade on it.

---

## Staging

Each stage has an exit condition. Do not advance on feeling.

### Stage 0 — SHADOW. No API key exists yet.

The bot computes exactly what it *would* place — symbol, side, entry, stop,
target, size, and the reason it was selected — and writes it to a table. It
sends nothing and trades nothing.

Run 2–4 weeks. Compare against the tracker.

**Exit when:** every shadow order matches what `/stats` assumed for the same
signal, minimum-size rejections are counted rather than crashing, and a restart
mid-window produces no duplicate or missing shadow orders.

This stage has zero financial risk and catches sizing bugs, rule mismatches and
state bugs — which are most of them.

### Stage 1 — LIVE, minimum size.

Sub-account, minimum funding, real orders at the smallest size the exchange
accepts.

The goal is **not** profit. It is: do fills arrive where the model says, do
stops land, does reconciliation stay clean across restarts and disconnects.
Expect to lose a little to fees. That is tuition, and it is cheap.

**Exit when:** 30+ completed round trips with zero reconciliation errors, zero
duplicate orders, zero unprotected positions, and at least one clean recovery
from a deliberate mid-trade restart.

### Stage 2 — FUND.

Only after stage 1 is clean. Scale to intended capital, keep everything else
identical, and compare live R per trade against the backtest.

**The honest bar**, from `TRADING.md`: `/stats` has ~71 settled rows and needs
200 or more. *Where it disagrees with anything above, believe it.*

---

## What would make me say stop

- Shadow orders disagree with the tracker's assumptions → the backtest is not
  describing what the bot would do, and no live result would mean anything.
- Live fills differ materially from the limit-fill model → the fill assumption
  is the foundation of every number here.
- Any reconciliation error at all → not a tuning problem. Stop and find it.
- `phase2_rule.py` shows the pick rule reversing across halves → the rule that
  looks best is fitted, and shipping it to an account is shipping a fit.

---

## What none of this fixes

27% of losing confirmed trades fall on five days out of forty-two. That is five
bad days, not twenty-four bad signals. No entry filter sees it coming and no
stop placement survives it. The concurrency cap limits the damage; it does not
avoid it.

Automation does not change this and cannot. It will simply take those five days
faster and without hesitating.
