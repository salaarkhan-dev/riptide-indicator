# Riptide — research state as of 11 Sep 2026

A self-contained briefing. Everything below was measured on this repository's own
data and code; nothing is quoted from memory or from a vendor. If you are being
asked to propose improvements, read section 9 first — it lists what is already
dead, and re-proposing it wastes a cycle.

---

## 1. What the system is

A Telegram alert bot for crypto perpetual futures. **Phase 1: alerts only.**
There is no exchange API key and no order-placement code anywhere in the
repository, and there must not be. It scans, it messages, a human decides.

The signal model is ICT/SMC liquidity reversal:

```
liquidity pool  →  sweep/raid  →  market structure shift (MSS)
                →  fair value gap (FVG)  →  limit entry at the gap's near edge
                →  stop beyond the raid extreme  →  2R target
```

Deployed configuration (`riptide.conf`): Min30 structure (Min15 also scanned),
daily point-of-interest required, grade A–B only, the 120 crypto USDT perps
above 1M/day turnover, refreshed 6-hourly, 2R target, 10-bar fill window,
60-bar horizon.

Two tradeable alert streams:
- **CONFIRMED** — the full chain above. Grade A.
- **EARLY** — the gap fires before the structure shift confirms. Grade B.

Plus watch-only sweep and trendline alerts, not counted as trades.

Runtime: one Python process under systemd on an Oracle free tier box. No Docker,
no web server, no inbound ports. Only dependency beyond stdlib is `aiohttp`.

---

## 2. How things are measured here — read this before trusting any number

**Unit of evidence is a BET, not a trade.** Sixty perpetuals raiding together on
one bar is one draw, not sixty. A "bet" is the mean R of every symbol firing on
the same bar. All standard errors and significance claims use bets. Trade counts
are reported as volume only. This matters enormously: 4,316 trades are 2,398
bets.

**Outcome is scored from the FILL bar, never the signal bar.** An earlier
generation of scripts got this wrong and inflated confirmed signals by +0.135 R
(4.2 SE) — entries are retracements, so pre-fill bars sit on the profitable side
and manufacture wins. One shared scorer now (`research/harness.py`); no study
has a private copy.

**Unfilled scores 0.0, not a loss.** Dropping unfilled rows would flatter every
result that fills less often.

**When one bar spans both stop and target, the STOP wins.** Bar data cannot
resolve intrabar order; this is the only honest read and it is the single
assumption biasing results downward.

**Fees are modelled from a real settlement**, not a rate card: 0.010% maker in,
0.022% taker out. **Funding and slippage are NOT modelled.** The same settlement
showed funding running a further ~25% on top of the trading fee.

**Survivorship bias is real and is not fixable.** The universe is the most
liquid perps *today*, walked back 333 days. Every coin that died, delisted or
dropped out is missing. **Absolute levels are biased optimistic, more so for
longs.** Comparisons between two arms measured on the same rows are largely
immune (common-mode) — trust differences, distrust levels.

**Four instruments are used to kill bad findings:**

1. **Circular-shift null** — rotate a symbol's feature series in time against its
   outcomes. Preserves persistence and distribution, destroys only the pairing.
2. **Symbol bootstrap** — resample the universe's symbols with replacement
   4,000×. A number carried by five coins collapses; one spread over forty
   survives. Stricter than the per-bet SE, which assumes symbols are
   interchangeable.
3. **Split-half** — an effect that is a property holds its sign in both halves of
   the window. One that flips is a period.
4. **Minimum detectable effect (MDE)** — printed next to every bucket comparison.
   Below it, a result is not weak, it is unreadable.

---

## 3. Baseline performance (333 days, Min30)

Measured on the 60-symbol universe that was deployed when this was written. The
floor was later lowered to 1M/day (120 symbols); see section 11 for what that
changed, which on performance is nothing measurable.

| | Confirmed (A) | Early (B) | Both |
|---|---|---|---|
| Signals / filled | 841 / 610 | 4,658 / 3,706 | 5,499 / 4,316 |
| Independent bets | 503 | 2,251 | 2,398 |
| Win rate | 37.0% | 36.6% | 36.7% |
| Net | +32.1 R | +119.5 R | +151.6 R |
| Profit factor | 1.08 | 1.05 | 1.06 |
| R per bet ± SE | +0.070 ± 0.062 | +0.034 ± 0.028 | **+0.034 ± 0.027** |

**The whole strategy is 1.2 SE from zero.** That is the single most important
fact in this document.

Risk/reward: planned 2R, realised **1.82 : 1** (avg win +1.836 R, avg loss
−1.008 R). Break-even win rate needed **35.4%**; actual **36.7%**. Margin: 1.2
percentage points.

- Largest win +1.999 R · largest loss −1.301 R (gapped through stop)
- Avg MFE +1.361 R · avg MAE −1.054 R · median stop 1.42% of price
- Exits: 33% target, 61% stop, 6% timeout; 22% of signals never fill
- Hold: median 9 bars, mean 15.1 (7.5 h). Fill: median 1 bar
- Max drawdown **132.4 R against +151.6 R net** (recovery 1.15)
- Under water 2,702 of 4,316 trades (63% of the year)
- Max consecutive: 20 wins, 28 losses

On a 300 USDT account at 1% risk per trade: **+12% with an 84.9% max drawdown**
unlimited; **−39% at max 10 concurrent**. Untradeable as configured.

**Long vs short:** long +0.020 R/bet, short +0.045, difference −0.025 at |z|
0.46. No directional edge.

**Concentration:** 32 of 60 symbols positive. **The best 5 supply 107% of net R —
remove them and the year is −10.6 R.**

Quarterly (confirmed): +0.129, −0.063, −0.037, +0.276 — but SEs are ±0.117 to
±0.133, so this spread is entirely consistent with a constant +0.07 plus noise.
It is **not** evidence of regime dependence (see item 24).

---

## 4. The one survivor: stop distance

Confirmed Min30, by distance from entry to stop as % of price:

| Zone | R/bet | Win | Symbol bootstrap (5th–95th) | Quarters |
|---|---|---|---|---|
| under 1.2% | −0.051 | 33% | [−0.193, +0.075] straddles zero | Q3 flips + |
| **1.2–2.6%** | **+0.214** | **42%** | **[+0.082, +0.329] all above zero** | **4/4 positive** |
| over 2.6% | −0.192 | 30% | **[−0.338, −0.032] all below zero** | 4/4 negative |

Replicated independently on **Min15** (791 confirmed setups): band +0.129, 41%
win, bootstrap [+0.028, +0.238], positive in 3 quarters of 4. The tight tail is
flat there too. The wide tail on Min15 is underpowered (63 bets, SE 0.162 — the
Min30 effect would score |z| 1.2 and still fail), not contradictory.

**The band cell in isolation:** 312 trades, 42% win, +55.6 R, max drawdown 14.0
R, **recovery factor 3.97**, under water only 74 of 312 trades, **0.94 fills per
day**. On 300 USDT at 1% risk: **+66% at a 13.4% drawdown.**

Only 0.5% of bootstrap universe draws come back non-positive, against 97.5%
non-positive for the excluded arm — the two halves fail in opposite directions,
which is hard to explain as a concentration artefact.

**Honest discounts:** (a) 5 of 57 symbols still supply 79% of the cell's R, and
a resample misses all five only 0.65% of the time, so the bootstrap's verdict is
partly a restatement of that — though deleting those five still leaves +11.5 R,
which no other cell manages; (b) the 1.2 and 2.6 boundaries were **chosen by
looking at data** (the test was pre-registered, the boundaries were not), so some
separation is selection.

**Deployed as an advisory label, not a filter** — the alert prints `2.34% risk ·
take`, `0.9% risk · flat`, `3.12% risk · skip`. Nothing is suppressed. The label
is gated to Min30 and Min15, the only timeframes it has been measured on.

---

## 5. Statistical power — why most hypotheses cannot be answered here

Minimum detectable effect, two arms, 5% significance / 80% power. Per-bet
standard deviation is ~1.4 R.

| Population | Bets | MDE |
|---|---|---|
| all tradeable | 2,395 | **0.152** |
| ↳ split discovery / OOS | 1,198 | 0.214 |
| ↳ a tercile inside each half | 399 | 0.371 |
| confirmed only | 489 | **0.351** |
| ↳ split discovery / OOS | 244 | 0.496 |
| ↳ a tercile inside each half | 82 | **0.860** |

**The largest effect ever measured on this project is +0.292 R/bet.**

So a tercile inside a discovery half of the confirmed stream needs an effect
three times larger than anything real that has ever been found here. The only
cell with power to see +0.292 is the full, undivided sample — which out-of-sample
discipline forbids using.

**With 503 confirmed bets you can have OOS validation or you can have power, not
both.** More features do not help: every feature is a deterministic function of
bars already on disk. **Features are free; bets are scarce; the only source of
more bets is forward time.**

**Exception — paired tests.** Comparing two exit policies on the *same* trades
cancels most of the variance. Paired SEs land at 0.011–0.046 instead of 0.351.
This is why exit and portfolio questions are answerable on this sample and
feature-bucket questions are not.

---

## 6. A 24-item review was tested in full. Results.

| # | Item | Result |
|---|---|---|
| 1 | Sweep penetration / ATR | spread +0.099 vs MDE 0.152 — unreadable |
| 2 | Sweep→MSS speed | cleared Min30 (+0.323), **failed Min15 transfer, wrong sign** |
| 3 | Raid rejection (close location) | +0.150 vs 0.152 — unreadable |
| 4 | Displacement quality | +0.162 vs 0.351 — unreadable, split-half flips |
| 5 | Liquidity pool age | +0.096 vs 0.152 — unreadable |
| 6 | Liquidity touch count | +0.106 vs 0.152 — unreadable |
| 7 | Pool compression (span/ATR) | +0.175 vs 0.350 — unreadable |
| 8 | Liquidity source as feature | Pivot +0.031, Daily +0.045 — no separation |
| 9 | Daily POI depth / age | +0.146, +0.101 vs 0.350 — unreadable |
| 10 | Daily FVG vs OB vs BOTH | **leans against prediction** — see below |
| 11 | Entry FVG size / ATR | +0.112 vs 0.350 — unreadable |
| 12 | First FVG vs best FVG | **untestable** — see below |
| 13 | FVG timing after MSS | +0.112 vs 0.351 — unreadable |
| 14 | Don't optimise win rate | agreed; enforced throughout |
| 15 | Conditional MFE ladder | measured, see below |
| 16 | 2R vs alternatives | **2R survives everything** |
| 17 | Structure-failure exit | **worst policy tested**: −0.074, \|z\| 1.92 |
| 18 | Time stop | ≈free (−0.007 R) and ≈worthless |
| 19 | Risk distance | the one survivor (section 4) |
| 20 | Dynamic position sizing | half already true by construction |
| 21 | Correlation-aware risk | recovery 1.14 → 1.13 — **just trading smaller** |
| 22 | Market-event policies | **best new result found** |
| 23 | Symbol characteristics | ranking does not persist |
| 24 | Regime detection | no effect on any definition tried |

### Item 2 — the near-miss, and how it died

Min30 sweep-to-MSS speed: 1–3 bars +0.015, **4–6 bars +0.323** (46% win,
bootstrap 5th +0.163), 7–11 −0.044, >11 +0.016. Spread +0.367 against MDE 0.351.
Cleared the bootstrap. Held sign across both halves. **Not** the risk band in
disguise — conditioning both ways gives a clean additive 2×2 (in-band + MSS 4-6:
51% win, +0.476, 78 trades).

One pre-registered test on Min15: **−0.087 against +0.032 — wrong sign.** The
Min15 gradient is slow-is-better (+0.248 at 12–20 bars), neither the hypothesis
nor the Min30 result. Matching wall-clock instead of bar count gives +0.038 at
|z| 0.30.

Found among ~34 cells, passed three filters, died on generalisation. The
predicted direction ("fast rejection = better") was backwards on both timeframes.

### Item 16/17/18 — exits (paired, so these ARE well-powered)

594 filled confirmed trades, 492 bets. Paired SEs 0.011–0.046. **Nothing clears
2 SE; eleven of thirteen alternatives are negative.**

| Policy | vs 2R | paired SE | \|z\| |
|---|---|---|---|
| target 2.5R | +0.0305 | 0.0269 | 1.14 |
| target 3R | +0.0099 | 0.0392 | 0.25 |
| out at 5 bars < 0.5R | −0.0021 | 0.0263 | 0.08 |
| out at 20 bars < 0.5R | −0.0074 | 0.0111 | 0.66 |
| 2R + BE at 1R → 0 | −0.0326 | 0.0219 | 1.49 |
| target 1.5R | −0.0383 | 0.0275 | 1.40 |
| half at 1R, rest to 3R | −0.0502 | 0.0344 | 1.46 |
| **2R + swing trail (structure exit)** | **−0.0743** | 0.0388 | **1.92** |

Break-even has now lost three times and stays off. The structure-failure exit —
proposed as "the most interesting exit I see" — is the worst row and the closest
of anything to being significantly *worse*: a stop under the last confirmed swing
gets hit on exactly the retracements a 2R trade must survive.

**MFE ladder (observational, target moved to 99R):**

- reached 0.5R (455 trades) → 1R 71%, 1.5R 55%, 2R 45%, 2.5R 38%, 3R 29%
- reached 1R (322) → 1.5R 78%, 2R 64%, 2.5R 54%, 3R 41%
- reached 2R (207) → 2.5R 84%, **3R 64%**
- 23% of fills never reach 0.5R at all

Once at 2R, 64% go on to 3R — which looks like an argument for a runner until you
see the 3R target itself is worth +0.0099 at |z| 0.25. The conditional
probability is real; the money is not, because the 36% that turn back give up two
full R.

### Item 22 — the one genuinely new positive result

Same-bar same-direction signals grouped into "market events". 4,263 trades → 2,445
events (median size 1, mean 1.8, max 20).

| Policy | Total | Max DD | **Recovery** | Under water |
|---|---|---|---|---|
| A take all (1 unit/trade) | +180.7 R | 135.9 | 1.33 | 60% |
| D allocate 1 unit across event | +89.6 R | 65.8 | 1.36 | 32% |
| E one arbitrary symbol only | +98.7 R | 69.2 | 1.43 | 32% |
| **C best by risk band only** | **+112.7 R** | 61.4 | **1.84** | 32% |
| B majors (BTC/ETH/SOL) only | +18.4 R | 21.4 | **0.86** | 55% |

**Concentrating an event into one position beats spreading it**, even chosen
arbitrarily. Read recovery factor, not drawdown — a rule that simply trades
smaller shrinks both together (that is exactly what item 21 does: 1.14 → 1.13).

Row C inherits the risk band's selection debt, so the defensible claim is row E's:
one position per event beats many. Row B — take a major as the event's
representative — is the **worst** row, below 1.0.

Event size does **not** predict outcome: +0.040, +0.067, −0.082, −0.059, +0.452
by size 1, 2, 3–4, 5–9, 10+. Non-monotone, largest events best. That is a noise
shape.

### Item 12 — untestable, and the reason matters

All 594 confirmed trades are gap **number one**. `riptide/engine.py` sets
`c.done = True` on the same line it appends the Setup, so a cluster emits exactly
one gap, ever. `maxFvgPerSetup` is a **Pine indicator input with no Python
equivalent**. The bot already always takes the first gap. This is a concrete case
of the Pine-is-not-the-bot distinction: the indicator and the bot are different
programs and only the bot's numbers are authoritative.

### Item 10 — prediction was backwards

Daily FVG 410 trades, 39% win, +0.095 (bootstrap 5th +0.002) · Daily OB 131
trades, 37%, +0.047 · **BOTH 53 trades, 32%, −0.012** (bootstrap 5th −0.294).
The prediction was that BOTH would be smaller but higher quality. It is smaller
and worse. At 53 trades this settles nothing on its own, but the data leans
against a specific prediction rather than merely failing to separate.

### Item 20 — half of it is a category error

"Position size ∝ 1/stop distance" is not a policy — it is what the R unit *means*.
The bot publishes entry and stop; risking a fixed % of balance **is** 1/stop
sizing. It cannot appear in an R-based measurement because it is the denominator.

Quality weighting is a real choice and is monotone (recovery 1.54 flat → 2.62 at
×1.25/×0.75 → 3.96 at ×1.5/×0.5 → 5.93 at ×2/×0), but this **restates the risk
band's edge under sizing rather than discovering anything.** Its only value is
pricing the decision to keep the band advisory.

---

## 7. Also tested and dead (earlier work, same standards)

- **Macro news windows (CPI/PPI/NFP/FOMC).** Real BLS + Federal Reserve calendar,
  DST-correct. Signals within ±120 min: 13 bets, −0.092 vs +0.065, |z| 0.44.
  **16 of 20 placebo calendars produced a LARGER effect than the real one.** The
  window is 2.2% of bars, so even a real effect would be worth ~2 R/year against
  ~32 R. Dead, and unfixable by more data — the shortage is releases per year.
- **Harmonic patterns** (Gartley/Bat/Butterfly/Crab/Shark/Cypher at ±5%).
  Conforming patterns −0.152 R/bet (862 bets, 11% win) vs near-misses −0.085
  (5,686 bets, 18% win). Clears its null, **in the negative direction.** All six
  patterns negative. Tighter ratio conformance is *worse*.
- **Symbol ranking.** Rank on H1, score on H2: leaderboard worth **−0.004 R/trade**
  on 4,230 trades. Spearman +0.13 / +0.15 / +0.18 across three streams; all
  inside a shuffled-ranking null. **Do not blacklist or whitelist symbols.**
- **Meme label** (BONK/DOGE/PEPE/SHIB/FARTCOIN/PENGU/USELESS/PUMPFUN/TRUMP).
  Whole-window it looked positive; split in half it flips (−0.208 in H1, +0.080
  in H2). No meme effect in either direction.
- **Turnover tier.** Flips sign between halves on both tradeable streams.
- **BTC trend filter, RSI/MACD/ADX/EMA batches, equal-high/low, OB and breaker
  variants, FVG continuation, opposing-liquidity exits** — all previously tested,
  all failed. Roughly 45 hypotheses total; the risk band is the only survivor.

**One live lead, recorded but NOT shipped:** inside the risk-band cell, high
realised volatility beat low by +0.300 in H1 and +0.298 in H2 — the same number
twice, out of sample, and not a meme confound (strip the 9 meme symbols and the
wild tercile is still +0.291 over 83 trades). The natural variable is the **ratio
stop-distance ÷ ATR** — a stop that is tight relative to the coin's own noise
implies an unusually well-defined raid. Never measured as a ratio. Needs its own
pre-registration.

---

## 8. Hard constraints on any proposal

1. **No order placement, no exchange API keys, no trading execution.** Alerts only.
2. No new dependencies beyond `aiohttp`. No Docker, no Kubernetes, no reverse
   proxy, no web server, no inbound ports.
3. Secrets live in a `chmod 600` `.env`, never in git, never in a systemd unit.
4. The Pine indicator is a visualisation layer. **`riptide/tracker.py` is the
   authoritative record** — it has no fill bug and no survivorship. Optimising
   the Pine's stats table does not improve the bot.
5. Production signal logic is the control and does not change during research.

---

## 9. What a useful proposal looks like

**Do not propose:** another ICT concept (order blocks, breakers, premium/discount,
Fibonacci, session bias, equal highs/lows); conventional indicators; symbol
selection by past performance; a regime classifier built on the quarterly spread;
break-even or trailing stops; win-rate optimisation; instrumenting more features
for retrospective mining.

**The binding constraint is statistical power, not information.** Any proposal
whose payoff is "measure X on the existing 333 days" must first clear the MDE
table in section 5. Most cannot.

**Three directions that survive the above:**

1. **Forward instrumentation.** Record features at signal time into the live
   tracker. The only action that creates new *bets* rather than new *columns*.
2. **Event concentration (item 22).** The only new positive result.
   **SHIPPED 11 Sep** — see section 11.
3. ~~**Stop-distance ÷ ATR ratio.**~~ **TESTED 11 Sep — DOES NOT SURVIVE.**
   Pre-registered at `e2f16b0` (low beats high), run on a 60-symbol discovery
   set and 60 held-out symbols never fitted on. Discovery LOW-HIGH +0.044
   against an MDE of 0.350, and the shape came back HUMPED rather than
   monotone — the middle tercile won, which contradicts the hypothesis rather
   than weakly confirming it. The one criterion that passed was the held-out
   sign, on a set whose median turnover is 1.7M against discovery's 10.6M,
   which is the liquidity confound the pre-registration named in advance. The
   variable was worth testing — it correlates only +0.231 with plain
   stop-percent — and it is now answered. See `research/studies/stop_atr.py`
   and `PREREG_stop_atr.md`.

   **This was the last lead on the list.**

### How fast more statistical power is actually obtainable

Measured by subsampling the existing universe, 30 draws per point. Bets scale
as **symbols^0.905** — near-linear, only mildly sublinear (more symbols means
more same-bar clustering, so trades per bet rises from 1.05 at 10 symbols to
1.21 at 59).

| Universe | Confirmed bets / 333 days | MDE |
|---|---|---|
| 60 (today) | 504 | 0.346 |
| 90 | 727 | 0.288 |
| 120 | 944 | 0.253 |
| 200 | 1,498 | 0.201 |
| 400 | 2,806 | 0.147 |

Available supply: 1,069 live USDT perps — 104 above the current 3M/day
turnover floor, 171 above 1M, 309 above 0.3M.

**So raising `RIPTIDE_TOP_N` from 60 to 104 costs one config line, needs no new
floor, improves the historical MDE from 0.346 to ~0.27, and raises the forward
observation rate by ~73%.** Going past that means lowering the liquidity floor,
which degrades fill realism and worsens survivorship — a judgement call, not a
free win.

Halving the MDE requires 4× the bets. Universe expansion is the clean lever
(different symbols are more independent than different timeframes on the same
symbol). Stacking Min15 onto Min30 adds ~672 confirmed bets but they are *not*
independent of the Min30 set — a Min30 bar contains two Min15 bars — so that
sample cannot simply be added.

---

## 10. Where the evidence lives

All studies in `research/studies/`, each with a `*_out.txt` of its last run and a
docstring carrying the pre-registration and the result:

`report.py` (full strategy report) · `survivor.py` (symbol bootstrap of the risk
band) · `power.py` (MDE table + market events) · `tier1.py` (items 1–9 + the
Min15 transfer test) · `exits.py` (items 14–18 + MFE ladder) ·
`portfolio_v2.py` (items 20, 22, 24) · `zones.py` (items 7, 9–12) ·
`symbols.py` (item 23) · `news.py` (macro releases) · `risk_band.py` (the
original pre-registration) · `stop_atr.py` + `PREREG_stop_atr.md` (the
pre-registered stop÷ATR test and its failure) · `universe_size.py` (3M against
1M floor).

Shared scorer: `research/harness.py`. Deep history loader:
`research/deep.py`. Prior negative results: `MEASUREMENTS.md`.

Tests: `tests/test_control_frozen.py` pins the production signal;
`test_event_pick.py`, `test_risk_verdict.py` and `test_tracker_event.py` cover
what shipped on 11 Sep.

---

## 11. Shipped on 11 Sep — read this before proposing anything

This section exists because an outside review, working from an earlier version
of this document, recommended three projects that were all already finished. If
you are being asked for advice, the list below is what has changed.

**Risk band label.** The alert prints `2.34% risk · take`, `0.9% · flat`,
`3.12% · skip`. Gated to Min30 and Min15, the only timeframes the band has
been measured on. Suppresses nothing. `tests/test_risk_verdict.py`.

**Event concentration rule.** `riptide/scanner.py::tag_event_pick` groups
signals by (timeframe, bar, direction) and names one: `🎯 the pick` or
`pick is ARB`. Ranked **take → flat → skip**, then confirmed before early, then
alphabetically for determinism. When every member is a `skip` it declines to
pick at all, because the evidence there points at the whole cluster rather than
one of them. Per-symbol history is deliberately excluded — ranking symbols does
not persist. Suppresses nothing; `RIPTIDE_EVENT_PICK=0` turns it off.

**Forward instrumentation of that rule.** `outcomes.event_pick` records five
states: -1 unrecorded, 0 solo, 1 the pick, 2 a sibling, 3 a cluster with no
pick. `/stats` compares 1 against 2 only — solo signals were never a choice, so
including them would measure "was there a cluster" rather than "was the ranking
right". **This is the first line on /stats never fitted on past data**, and it
needs roughly ten resolved clusters a side before it says anything.

**Stop÷ATR — tested and dead.** See section 9, item 3.

**Universe floor 3M → 1M, 69 → 120 symbols.** Done for data rate, not
opportunity: bets scale as symbols^0.905, so this takes the MDE from about 0.32
to 0.25 and nearly doubles the forward observation rate, at roughly 31 alerts a
day instead of 19. `universe_size.py` then asked whether the combination is
actually better and found it depends on the reader — the wider universe dilutes
somebody who takes everything (+0.032 → +0.016 R/bet) and helps somebody who
filters to the band (recovery 1.75 → 2.94). **Every one of those differences is
inside its own noise**, and the proof is that moving the cutoff by nine symbols
reversed one of the rows.

**The control is now enforced, not just asserted.**
`tests/test_control_frozen.py` hashes the five fields a reader acts on across
213 signals from a committed candle fixture. Deliberately NOT two separate
engine objects: two code paths drift, and every measurement afterwards
describes a strategy nobody runs. One engine plus a frozen hash makes drift
impossible and any real change loud. Research instrumentation stays welcome —
`Setup.span` and `harness.stale_bars` were both added today without moving it.

**Still deliberately not done**, on the same reasoning as section 9: daily
bias, new entry models, new exit models. 2R survived thirteen alternatives and
nothing beat it at 2 SE.
