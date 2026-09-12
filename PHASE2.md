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
| Risk per trade | **0.5%** | Chosen. Return per unit of drawdown barely moves across 0.5/1/2% (2.39 / 2.11 / 2.00) — this is a pain choice, not an edge choice. 0.5% measured +12% return on 6% drawdown. |
| Concurrent positions | **max 8** | Drawdown falls monotonically as the cap tightens, but below 8 return falls faster. ret/DD: no cap 1.30, max 12 1.84, max 8 2.21, max 5 0.89, max 3 0.05. |
| Reserve for confirmed | **3 slots** | Best single rule measured, and the only one with a mechanism: confirmed are worth 3.4× an early signal (+0.227 vs +0.021) and early outnumber them 5.6:1, so without a rule the worse signal crowds out the better one purely by arriving first. |
| Same-direction cap | **none** | Sounds like correlation control, measured badly: 0.47 against 2.21. It blocks winners during exactly the trending moves that pay. |
| Daily loss limit | **none** | Unproven. −4% scored 2.67, −6% scored 1.54, −10% never fired. A threshold that flips the result like that is noise. |
| Break-even | **off** | Loses at every arm level on both signal types. Arming at 1R costs −2.5 SE and drops total R from +53.1 to +34.8. It converts trades that would have reached target into +0.1R scratches. |
| Entry | **limit at the stated entry** | This is literally what was backtested: "bars after the gap forms in which a limit at the entry may fill." |
| Fill window | **10 bars, then cancel** | Past this the backtest records "never filled", which is a result, not a discard. ~19% of grade B never fill and the +0.173 R/signal is the average *after* those misses. |
| Target | **2R** | Measured monotone 1R +20.4, 1.5R +39.5, 2R +52.8, 3R +61.9 total R, though each step is ~1.5 SE. |
| Daily quota | **none** | No measured limit on how many alerts to take per day ever came out of this project. Slots are the scarce resource, not signals. |

**Do not stack every rule.** All of them together scored 2.11, worse than
reserving slots alone at 3.67. Each rule blocks trades and stacking them blocks
the winners too.

---

## What is still OPEN

### 1. Which selection rule the bot trades — the central question

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

**Until that resolves, no order code should be written against either rule.**

### 2. The old portfolio number is not stable

Rerunning `portfolio.py` unchanged today:

| rule | TRADING.md | today |
|---|---|---|
| max 8, 3 slots for confirmed | 3.67 | **5.47** |
| everything, no rules | 1.30 | **0.54** |

Same code, same rules, a window that slid forward ~42 days. **The ordering
survived; the levels did not.** Treat every ret/DD level in `TRADING.md` as
ordinal, not cardinal — and do not size an account off one.

### 3. 15m may have to be excluded entirely

On the sent stream, net of fees (`fee_key.out`, n=4625):

| tf | gross R | net R | fee as % of gross |
|---|---|---|---|
| **15m** | +0.0064 | **−0.0268** | **521%** |
| 30m | +0.0486 | +0.0255 | 47% |
| 1h | +0.0594 | +0.0435 | 27% |

15m loses money after fees. The mechanism is not subtle — fee in R is
`fee_pct / risk_pct`, and 15m's median stop is 1.01% against 1h's 2.04%, so
every 15m trade pays roughly twice the fee per unit of risk.

A human skips a bad-looking 15m alert without noticing they did. **A bot takes
every one.** `phase2_rule.py` asks whether this carries to the picked stream.

### 4. Minimum order size at minimum capital

Funding starts at the exchange minimum. At 0.5% risk that is a very small
notional, and MEXC has per-symbol minimum order sizes. **Expect most signals to
be unplaceable at stage 1.** That is fine — stage 1 is about proving the
plumbing, not about return — but the bot must skip them cleanly and count them,
not error.

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
