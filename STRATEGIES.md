# Strategies — the registry, and how a new one gets in

Riptide today is one strategy wearing three hats: `sweep`, `early`, `setup`.
They share an engine, and `scanner.cycle()` handles each with its own copy of
the same loop. A fourth strategy — **Liquidity Entry Zones** (`liquidity-entry-zones.pine`) —
is a fourth copy of that loop unless the loop is factored out first.

This document is the review of that indicator, the architecture that lets it
run beside Riptide without touching it, and the release phases. Nothing here
is shipped yet. Phase 0 is this document.

---

## Part 1 — Review of `liquidity-entry-zones.pine`

The file is in the repo **verbatim**, byte for byte as written. Nothing below
has been changed in it. Findings are separated into what is wrong, what is
undecided, and what is right, because most of it is right.

### 1.1 What the model actually is

Stripped of the drawing code, it is a **single-timeframe, single-candle
rejection model**:

1. Store the last 20 confirmed `ta.pivothigh`/`ta.pivotlow` levels (length 5).
2. Find the newest stored level the current bar exceeded by at least
   `0.10 × ATR(14)`.
3. Require the bar to close back inside that level (the *reclaim*), with a
   lower wick ≥ 35% of range, a body ≤ 65% of range, and a range ≥ 0.20 ATR.
4. Within `confirmationWindow` bars, require a bar that closes with a bullish
   body, above EMA-50, and above the sweep candle's midpoint.
5. Enter at that bar's **close**. Stop at `1.50 × ATR(14)`. Target at 3R.

### 1.2 Non-repainting — it passes

This matters more than anything else and it is clean:

- No `request.security` anywhere, so there is no higher-timeframe leak of the
  kind that cost this project a re-measurement of the whole grade table.
- `ta.pivothigh(high, 5, 5)` is only pushed when it confirms, and is dated
  `bar_index - pivotLength`. A pivot that has just confirmed cannot be swept
  on the bar it confirms — its right-strength guarantees the last 5 highs are
  below it — so the newest usable level is always at least 6 bars old. No
  look-ahead.
- Every signal condition is evaluated on `close`.
- The exit block is guarded by `bar_index > simulatedEntryBar`, so a target
  cannot resolve on the entry bar, and a bar spanning both stop and target
  resolves as a **loss**. That is exactly `research/harness.py`'s convention.

The downward loops (`for i = highLevelCount - 1 to 0`) are guarded by a
non-empty check, so they avoid the `i = -1` trap that bit the previous
indicator work.

**Consequence: a faithful Python port is straightforward and there is no leak
to hunt.** That is the main reason this is worth measuring rather than
arguing about.

### 1.3 The quality score is nearly a constant — this is a real bug

`f_quality_score` divides each component by the same threshold that gates the
signal:

| component | points | gate that must already have passed | result on a printed signal |
|---|---|---|---|
| wick | 32 | `wickPct >= minWickPercent` | ratio ≥ 1 → **clamped at 32** |
| range | 18 | `candleRange >= minCandleRangeAtr × ATR` | ratio ≥ 1 → **clamped at 18** |
| reclaim | 10 | `bullishReclaim` is required by `validBuySweep` | **always 10** |
| body | 24 | `bodyPct <= maxBodyPercent` | genuinely varies, 0–24 |
| ema | 10 | not required at sweep time | varies |
| midline | 6 | not required at sweep time | varies |

So **60 of the 100 points are pinned at maximum by construction**. Every
signal scores between 60 and 100; the real range is 40 points shown on a
0–100 dial. And `f_score_color` paints red below 55, which a printed signal
can never reach — the score has a colour it can never display.

A "Q:78" is really 18 out of 40. Not useless as an ordering, but it is not
the number it looks like, and no filter should ever be built on the absolute
value.

Second, smaller point: the score is computed on the **sweep** bar
(`bullSweepScoreNow`, stored into `pendingBullScore`). When confirmation lands
on a later bar, the Q shown at entry describes a different candle.

### 1.4 The chart cannot tell you it is working

Two defaults conspire:

- `showStoppedTrades = false` — on a stop-out, the TP box, SL box, entry zone,
  entry lines, invalidation line and all four tags are **deleted** (lines
  880–905). Winners keep a green `TP 3R HIT` label. Losers leave a BUY/SELL
  arrow and nothing else.
- `showStatusPanel` explicitly documents that "performance rows such as
  trades, win rate, net result, and drawdown are not displayed."

So the chart draws every win in full and erases every loss's projection, and
reports no win rate. **"It's doing great on the chart" is not evidence yet.**
It may well be doing great — that is what Phase 1 exists to find out — but the
display is not capable of showing otherwise. Set `showStoppedTrades = true`
before forming any further impression from a chart.

Third bias in the same place: `blockSignalsInTrade = true` means whether a
setup prints depends on whether the *previous* setup is still open. The
visible sample is path-dependent, not a sample of setups.

### 1.5 The confirmation window does not require a confirming bar

`pendingBullSweepBar := bar_index` is assigned on the sweep bar, and
`bullWindowOpen` then tests `bar_index - pendingBullSweepBar <= confirmationWindow`
— which is `0 <= 2` on that same bar. **The sweep bar can be its own
confirmation bar.**

For a bull setup that means the whole model collapses to one candle: a hammer
with a ≥35% lower wick that reclaimed a prior pivot low, closed above its own
midpoint, closed above its open, and closed above EMA-50.

That may be the intent. It is not what "Max Bars After Sweep For Confirmation"
describes, and it changes what the model *is*. Phase 1 measures both arms
separately (`bars_to_confirm == 0` vs `> 0`) rather than assuming.

### 1.6 The stop is a volatility constant, not a structural level

Entry is the confirmation close; the stop is `entry ∓ 1.5 × ATR`, with no
reference to the raid extreme. Usually that lands below the sweep low, but
nothing enforces it: once the sweep candle's range exceeds roughly 2 ATR, the
stop sits **inside the candle that triggered the trade**, and the line drawn
on the chart labelled `INVALIDATION` is then a claim the model cannot support.

This is the single largest departure from everything Riptide has measured.
Riptide's stop is placed just beyond the raid extreme, and `stop_buffer.py`
found the peak at a buffer of 0. An ATR stop is a genuinely untested rule
here — not wrong, untested. Phase 1 reports the share of signals whose stop
falls inside the sweep candle, and scores an ATR stop against a raid-extreme
stop on the identical signal set.

### 1.7 Fees are absent, and at this stop width they matter

The indicator's simulation charges nothing. Real cost on MEXC: the entry is a
market order at the close (**taker, 0.06%**), a target is a limit (**maker,
0.02%**), a stop is a market order (**taker, 0.06%**). Round trip: 0.08% on a
win, 0.12% on a loss.

Cost in R is `fee_pct / risk_pct`, and risk here is `1.5 × ATR`:

| 1.5 ATR as % of price | fee on a loss | break-even win rate at 3R |
|---|---|---|
| 0.60% (liquid alt, 15m) | 0.20 R | 25% → **~29.5%** |
| 0.35% (quiet symbol) | 0.34 R | 25% → **~33%** |

Not fatal — the ATR stop is wide enough to absorb it, which is the one place
this model is *cheaper* than a tight scalp — but four to eight points of
required win rate is not a rounding error, and it is the difference between
the on-chart picture and a tradeable one.

### 1.8 The only directional filter is the one measured as a null

`useLocalEmaFilter` uses EMA-50 **on the signal's own timeframe**.
`research/studies/which_trend.py`, on 6,970 signals:

| filter | agreeing | against | separation |
|---|---|---|---|
| daily trend | +0.056 | −0.083 | **+4.5 SE** |
| the chart's own trend | — | — | +0.002, **−0.0 SE** |

The higher timeframe supplies direction; the chart's own trend supplies
nothing. This indicator uses only the second one. That is the cheapest
available improvement and Phase 1 tests it as a bucket variable before anyone
proposes it as a gate.

### 1.9 Smaller findings

- **Levels are never consumed.** A swept level stays in the array and can be
  swept again; only the 20-slot FIFO evicts it. `signalCooldownBars = 10`
  masks some of this. Measurable: the repeat-sweep rate per level.
- **Cooldown is off by one.** `bar_index - lastSignalBar > signalCooldownBars`
  requires an 11-bar gap for a setting of 10.
- **Long/short ties are broken arbitrarily.** `sellSignal = ... and not buySignal`.
  Both pendings can be live at once.
- **Session labels are decorative.** `hour(time, "GMT+3")` buckets are close
  enough to London/NY but nothing filters on them.
- `alertcondition` messages carry no symbol, price or direction placeholders.
  Irrelevant here — the bot will run its own port, not TradingView webhooks.

### 1.10 Verdict

Mechanically sound, non-repainting, portable, and honest in its exit
convention. Its **display** is not honest about losses, and three of its
choices (ATR stop, market entry at the close, chart-EMA direction) run against
what this project has already measured. That is a reason to measure it, not to
reject it — the ATR stop in particular has never been tested here and could go
either way.

Nothing goes to Telegram until Phase 2 clears.

---

### 1.11 Crypto correctness — audited, and four things fixed

Asked directly: is anything in here assuming pips or an FX-shaped instrument?

**The trigger is already scale-free and needed nothing.** Every threshold —
`minSweepDistanceAtr`, `minWickPercent`, `maxBodyPercent`, `minCandleRangeAtr`,
`stopLossAtrMultiplier` — is an ATR multiple or a ratio of the candle to
itself. There is no pip, no point value, no fixed price constant anywhere in
the signal path. It behaves identically on BTC at $100,000 and on a coin at
$0.0000012. That is good design and it is why the Python port and every
measurement in `MEASUREMENTS.md` still describe this file exactly: the
signal-path blocks are **byte-identical** to the original after these changes.

What was not crypto-proper was everything around it.

| | before | now |
|---|---|---|
| **No fee model at all** | a 2R win drawn as 2R | taker/maker inputs, net R on every label, and a **"Win Rate Needed"** row |
| **No funding** | absent, and it exists only on perps | `fundingPct8h` input, cost per 8h in R |
| **Volatility bands** | hardcoded 0.80% / 0.35% of price — a *timeframe*, not a market state: nearly every 30m crypto bar reads LOW, every daily bar reads HIGH, an FX pair never leaves LOW | ratio to this symbol's own 200-bar average |
| **Session clock** | `hour(time, "GMT+3")` with ASIA 00:00–08:00, which is wrong for that offset | timezone input, UTC default, correct windows, labelled as reference — crypto is 24/7 |
| **Levels shown as words** | `ENTRY`, `ATR STOP`, `TARGET 2R` — you cannot read your own prices off the chart | actual prices via `format.mintick`, so precision comes from the instrument and is right from BTC to PEPE |
| **`showStoppedTrades`** | `false` — every winner drawn in full, every loser's projection deleted | `true` |

**The most useful of these is the break-even row.** On ETH 30m with the shipped
`SL 1.5 ATR / TP 2R`, 1.5 ATR is roughly 0.5% of price, so a losing round trip
costs about 0.23 R and the panel will read **≈40% to break even**. The measured
win rate of this configuration is 33%. The chart now states its own problem.

**None of this changes the strategy's expectancy.** Rounding is display-only —
the simulation keeps unrounded levels, so no trade resolves differently. What
changed is that the panel stops flattering the model.

## Part 2 — Multi-strategy architecture

### 2.1 The rule this is built on, which already exists

`scanner.poi_ok` and `scanner.grade_ok` both carry the same comment:

> Gates SENDING only. The signal is still recorded and still armed, because
> muting a strategy must not also stop measuring it — /stats is the only
> forward, out-of-sample evidence this project has.

Beta gating is not a new idea. It is that rule with a third value. Every
signal, from every strategy, always passes through three independent stages:

| stage | when | who can turn it off |
|---|---|---|
| **RECORD** | always | nobody |
| **TRACK** | always, if fresh | nobody |
| **NOTIFY** | strategy enabled **and** not in beta | config, `/strategies`, beta flag |

A beta strategy is `RECORD + TRACK, never NOTIFY`. It builds its live sample
from day one and cannot reach the chat.

### 2.2 The package

```
riptide/strategies/
    __init__.py      REGISTRY, resolve(), enabled_for()
    base.py          Signal, Strategy protocol, Sink
    riptide_smc.py   wraps the existing engine — three kinds, byte-identical
    lez.py           Liquidity Entry Zones
```

```python
class Strategy(Protocol):
    name: str                        # registry key, db key, /strategies key
    label: str                       # what the user reads
    beta: bool                       # True -> NOTIFY is unreachable
    intervals: tuple[str, ...]

    def scan(self, symbol, candles, tf) -> list[Signal]: ...
    def sig_id(self, sig) -> str: ...
    def message(self, sig) -> str: ...
```

`cycle()` becomes one loop over the registry instead of three hand-written
blocks. The per-kind gate counters generalise to per-strategy counters, so the
existing "why was it silent" log line keeps working and gains a column.

### 2.3 Enable, disable, subscribe

Precedence, highest first:

1. **`beta = True` in code.** NOTIFY is unreachable. `/strategies on lez`
   answers *"lez is in beta — recorded and tracked, not sent"* and changes
   nothing. Promotion is a code change plus a deploy, not a chat command,
   because a chat command is exactly how a half-measured strategy ends up in
   the chat at 3am.
2. **`meta` table override**, set by `/strategies on|off <name>`. Same
   mechanism as `/trend` and `/pause` already use — read once per cycle, so a
   toggle takes effect on the next scan with no restart.
3. **Config default**, `RIPTIDE_STRATEGIES=riptide` in `.env`.

### 2.4 Not disturbing what works

The user's constraint — *"other strategies don't get disturbed"* — is a
testable property, not a coding style:

- `riptide_smc.py` **wraps** the existing engine. No engine file is touched.
- A parity test runs the pre-refactor `cycle()` and the post-refactor one over
  the same recorded candles and asserts **identical signal sets and identical
  message bodies**. The refactor does not merge until that passes. This is the
  same discipline `deploy/check-parity.py` applies to the Pine/Cfg pair.
- Dedupe: the three existing tables (`seen`, `seen_sweeps`, `seen_early`) are
  left alone — no migration of something that works. New strategies get one
  `seen_signals` table keyed `(strategy, sig)`.
- `outcomes` gains a `strategy` column defaulting to `'riptide'`, added through
  the existing one-entry-per-column migration in `tracker.init` — the pattern
  that exists precisely because two columns once shared a guard and one of
  them never landed.
- `/stats` gains a per-strategy breakdown. Existing output for `riptide` is
  unchanged.

### 2.5 Still phase 1, still alerts only

No exchange key, no order placement, no inbound port. A strategy produces
messages and outcome rows. Nothing in this design touches an exchange beyond
the public REST endpoints already in use.

---

## Part 3 — Release phases

Each phase has an entry gate, a deliverable, and an exit gate. A phase that
fails its exit gate does not advance; it goes back or it stops. The point of
writing the gates down now is that they cannot be moved later to whichever bar
the result happens to clear — that is the discipline in `PREREG_btc.md` and
`PREREG_mitigation.md`, and both of them caught something.

### Phase 0 — in the repo *(this commit)*

- `liquidity-entry-zones.pine`, verbatim.
- This document: review, architecture, gates.
- **Exit gate:** none. It is a record.

### Phase 1 — measure it, no bot code at all

`research/studies/lez.py`: a faithful Python port of §1.1, scored by
`research/harness.py` over the standard 60-symbol universe, on 15m and 30m.

Faithful means: entry at the confirmation close, stop at `1.5 × ATR(14)`,
target 3R, stop wins a bar spanning both, no resolution on the entry bar. A
port test asserts the Python signal set matches the Pine on at least one
symbol-window exported from TradingView, so "faithful" is checked, not
asserted — the sign-bug lesson is that a comment is not evidence.

Measured, all pre-registered here:

1. **R per signal and win rate**, net of fees, with standard errors, on the
   four standard splits (symbols A/B, window halves).
2. `bars_to_confirm == 0` vs `> 0` — §1.5.
3. Share of signals whose stop lands inside the sweep candle — §1.6.
4. **ATR stop vs raid-extreme stop** on the identical signal set — the one
   genuinely new idea this indicator brings.
5. Daily trend agreeing vs against, as a **bucket** — §1.8.
6. Quality score in quartiles, acknowledging the 60-point floor — §1.3.
7. Target ladder 1.5R / 2R / 3R / 4R, as `winrate.py` did.
8. Overlap with Riptide's own signals: same symbol, same direction, within
   one bar. A strategy that is 70% the same trades is not a second strategy.

Run on **Min5, Min15 and Min30**, each given the same ~42 calendar days by
paging, so a timeframe cannot flatter itself with a different window.

**Exit gate, stated in advance:** net R per signal **> 0 after fees on the
full sample, and the same sign in both window halves and both symbol halves.**
Riptide's confirmed band is +0.128 ± 0.104 (grade A) and +0.080 ± 0.042
(grade B) post-look-ahead-fix; a second strategy that cannot clear zero is not
worth a slot. Below that: back to Phase 1 with one variable changed, or stop.

> ### OUTCOME — 9 Sep 2026: **FAILED, on all three timeframes**
>
> | timeframe | n | win | R/signal | random-entry control | what the signal adds |
> |---|---|---|---|---|---|
> | Min30 | 1383 | 26% | **−0.122 ± 0.047** | −0.094 | −0.027 ± 0.066 (−0.4 SE) |
> | Min15 | 2906 | 24% | **−0.226 ± 0.032** | −0.149 | −0.077 ± 0.046 (−1.7 SE) |
> | Min5 | 8299 | 23% | **−0.435 ± 0.019** | −0.340 | −0.095 ± 0.028 (−3.4 SE) |
>
> The chart's own default view (`blockSignalsInTrade`) is negative too:
> −0.145, −0.248, −0.293.
>
> The control was added after the first run and it is the actual result. Random
> entries — same symbols, same timeframe, same market-at-the-close, same 1.5
> ATR stop, same 3R target, coin-toss direction — score **zero gross** and lose
> only the fee. So **the trade shape is a fair coin and the fee is the whole
> cost**, and what the signal contributes on top is between nothing and mildly
> negative, worsening as the timeframe falls.
>
> Neither the target ladder, nor the daily trend, nor the quality score, nor
> the confirmation-window split rescues it. The one arm the indicator wins is
> its own ATR stop against a raid-extreme stop — because the structural stop is
> tighter and pays more fee per unit of risk. Full numbers and the
> port-fidelity evidence in `MEASUREMENTS.md`.
>
> **Phases 2–5 do not start.**
>
> ### The sweep, run afterwards at the user's direction — `lez_sweep.py`
>
> 360 cells (stop, target, quality, trend, POI) on Min30 and Min15, window
> doubled and split so the winner got one shot at unseen data. Scored on
> **EDGE = LEZ − random entries in the same cell**, because a wider stop
> lowers fee-in-R and so improves a coin flip too.
>
> The same grid asked of coin flips — one half of the control pool against the
> other — has a best cell at **+0.289** (Min30) and **+0.191** (Min15). The
> best LEZ cells are **+0.196** and **+0.117**. **Neither reaches its own noise
> floor.** At a 3 ATR stop on Min30 the strategy and a coin flip score
> identically to three decimals.
>
> The Min30 held-out shot fails. The Min15 one passes a bar that was written
> too weak — "edge > 0 and R > 0" with no significance requirement, which a
> coin flip clears about half the time; its held-out edge is 0.5 SE. Full
> numbers in `MEASUREMENTS.md`.
>
> The components carrying the one positive-looking cell are the daily trend and
> the daily POI, both of which Riptide already gates on. The trigger itself
> adds +0.05 ± 0.11.

### Phase 2 — the refactor, with Riptide's behaviour frozen

Build §2. Ship `riptide_smc.py` only. `lez` is registered but returns nothing.

**Exit gate:** the parity test in §2.4 passes — identical signals, identical
messages — and `python -m pytest` is green. No behaviour change reaches the
chat in this phase. Deploy is gated on `signs.py` as every deploy already is.

**Also in this phase, and independent of any strategy: the `/stats` table.**
Today it reports a win rate, and a win rate on its own cannot answer the
question that actually gets asked. The shape it grows into is already built and
proven in `research/studies/lez.py`:

```
                        n   win   wins  stops  t/out   risk   R/sig    ±SE    total
  target 2R          1383   33%    460    919      4  1.20%  -0.128  0.039   -177.1
  target 3R          1383   26%    342   1024     17  1.20%  -0.122  0.047   -168.1
  target 4R          1383   22%    258   1079     46  1.20%  -0.119  0.053   -165.3
```

Three things it adds. **The ladder** — the same signals scored at 2R, 3R and
4R, because the win rate is not a property of the strategy, it is a dial the
target sets (`winrate.py`: 0.5R wins 69% and loses money, 4R wins 32% and makes
the most). **The exit breakdown** — wins, stops and timeouts as counts, because
a timeout closing a hair above entry scores as a win under `r > 0` and is
nothing of the sort. **Standard errors**, so a run of luck stops reading as a
result.

`research/harness.py` already carries the piece this needs: `Outcome.exit` now
records *why* a trade ended (`"stop"`, `"target"`, `"timeout"`, `""` for
unfilled). `riptide/tracker.py` stores a status per row and can be read the
same way, so `/stats` needs no new data — only the query and the format.

### Phase 3 — beta, recording only, no Telegram

`lez.beta = True`. It scans, records, and arms outcome tracking every cycle.
It cannot send. `/stats lez` shows its live sample.

**Exit gate:** **at least 100 tracked live signals**, and live R per signal
within 1.5 SE of the Phase 1 backtest estimate. A live sample that disagrees
with the backtest means the port is wrong or the backtest is contaminated, and
in this project that has happened twice. Minimum dwell: 3 weeks, because 100
signals arriving in four days is one regime.

### Phase 4 — promotion, one alert kind, muted by default

Beta flag off. `RIPTIDE_STRATEGIES` still excludes `lez`, so it stays silent
until `/strategies on lez`. One kind only — the confirmed signal. No sweep
heads-up, no early variant.

**Exit gate:** 4 weeks live with alerts on, `/stats lez` still clearing zero
net of fees, and no operational surprise (no duplicate storms, no cycle
aborted by a `lez` exception — `_arm`-style wrapping applies to every new call
site).

### Phase 5 — the other alert kinds, one at a time

Only after Phase 4 holds. Candidates, in the order their evidence would be
cheapest to get:

- **`lez.sweep`** — the raid detected, before any confirmation. Riptide's
  equivalent is a heads-up, not a trade, and no measurement covers it. Same
  status here.
- **`lez.early`** — the reclaim bar without the midline/body confirmation.
  Fires earlier, fills worse. Measured before it is built, not after.
- **HTF-filtered variant** — §1.8, if Phase 1's bucket 5 separates.

Each is its own registry entry with its own beta flag and its own Phase 1→4
walk. None of them rides in on the parent's evidence.

### What is deliberately not in the plan

- No promotion by chat command. Beta comes off in code.
- No parameter sweep before Phase 1's exit gate. Tuning a model that has not
  cleared zero once is how a curve gets fitted.
- No shared state between strategies. If `lez` and Riptide both fire, both
  alert; slot management is the trade desk's job and it already exists.
