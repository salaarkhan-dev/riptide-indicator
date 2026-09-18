# Riptide Undertow — market-structure bias + a single-candle pin

**Status: MEASURED FIFTEEN TIMES, nothing promoted. The last two measured the
CORRECTED rule — see SPEC.md 8 — and both are null. The fourteenth also found
that the break-even line these pages quote, 22.2%, is the figure BEFORE costs:
the real line is 22.9–23.5% and the shipped rule sits exactly on it. Ships as a
watch, OFF by default, saying so in every message.**

| study | result |
|---|---|
| [`UNDERTOW_PARAMS.md`](measurements/UNDERTOW_PARAMS.md) | −0.093 / +0.071 / −0.063 R per trade on a holdout sharing neither symbols nor calendar with the search; **lost to a random entry on two of three** |
| [`UNDERTOW_PIN_VALUE.md`](measurements/UNDERTOW_PIN_VALUE.md) | the candle taxonomy adds nothing; removing it scored **higher** on two of three |
| [`UNDERTOW_EXITS.md`](measurements/UNDERTOW_EXITS.md) | 8–12% of setups really do reach 7R — and a **coin reaches 7R 12.5% of the time** |
| [`UNDERTOW_BACKUP_FILL.md`](measurements/UNDERTOW_BACKUP_FILL.md) | the OB/FVG backup nets **+0.03 R per armed setup**, positive on 3 of 3 and significant on none — because two large, individually significant halves nearly cancel |
| [`UNDERTOW_LATE_BACKUP.md`](measurements/UNDERTOW_LATE_BACKUP.md) | waiting for the Focus limit to expire removes the tax **and all the opportunity**: 100% of the +0.6 R trades fill inside the window, median 1–2 bars |
| [`UNDERTOW_BIAS_SOURCE.md`](measurements/UNDERTOW_BIAS_SOURCE.md) | five direction sources — structure, EMA, Supertrend, Slope, range midpoint — and **none beat the baseline**. EMA swung 0.54 R per trade between two halves of the same universe, which is the clearest "this is noise" in the project |
| [`UNDERTOW_OVERLAP.md`](measurements/UNDERTOW_OVERLAP.md) | **74% of 15m trades run alongside another in the same direction**, up to 13 at once, and those groups win or lose together **78%** of the time. Four longs within $10 is one idea at 4x size. Descriptive; the chart now collapses them and the strategy is unchanged |
| [`UNDERTOW_SLOPE_DEFAULT.md`](measurements/UNDERTOW_SLOPE_DEFAULT.md) | the bias study's best number, Slope at **+0.198** on Min30, came back **−0.228** on a different stretch of the same symbols. A time-normalised Slope then cleared *every* bar on Min60 at z +3.61 — and lost to a coin at z −2.46 on Min30. **Nothing promoted** |
| [`UNDERTOW_HTF.md`](measurements/UNDERTOW_HTF.md) | the HTF agreement gate, on **45 symbols nothing here had ever seen**, against a **random gate discarding the same count**: worth **+0.032 / +0.010 / −0.029 R** over that control on 22,875 trades. Best-powered null in the project, and the one that cannot be blamed on a spent holdout |
| [`UNDERTOW_MTF_EMA.md`](measurements/UNDERTOW_MTF_EMA.md) | two timeframes, EMA 20/50, trade only when aligned. **The second timeframe is worth −0.005 to +0.020 R across six panels** — the abstain state fires on 19% of bars and removes 7–9% of trades, because disagreement clusters where nothing was arming anyway |
| [`UNDERTOW_MTF_DEFAULT.md`](measurements/UNDERTOW_MTF_DEFAULT.md) | MTF as the default against the **shipped** configuration: worse, on 2 of 3. The surprise is the BASELINE — structure as shipped is **+0.063 / +0.016 / −0.067** on an unseen universe, and `endMinor` discards **64%** of trades to get there, uncontrolled. The first number here worth a prereg rather than a shrug |
| [`UNDERTOW_PULLBACK.md`](measurements/UNDERTOW_PULLBACK.md) | the three pullback defects in SPEC 2.3b, fixed and measured. **The 2nd and 3rd candle after the pullback extreme are within ±0.025 R of the 1st**, and `locTol=2` nearly doubles the setups for it — a throughput finding, not an edge. A minimum pullback depth removes trades that are not worse |
| [`UNDERTOW_V2.md`](measurements/UNDERTOW_V2.md) | **the corrected strategy — W→F confirmation, SMC 50/5 structure, CHoCH+BOS only, pullback after the BOS, newest pin wins.** Negative on 3 of 3, loses to its control on 2 of 3, worse than v1 on two. **Every win rate in the study lands between 20.3% and 23.5% against a 22.2% break-even** |
| [`UNDERTOW_V3.md`](measurements/UNDERTOW_V3.md) | **the corrected ANCHOR — the counter-trend candle is the bounce attempt at the leg low, not the top of the pullback.** Positive on 3 of 3 and above its control on 3 of 3, the first arm here to do either, and **it clears neither bar** because every margin is a third of an SE. Two things it settled against me: **22.2% is the break-even BEFORE fees** — the real line is 22.9–23.5% and v1's win rate matches it to a tenth of a point on all three timeframes — and **the 76.7% family mix in my own prereg is an artifact of `locTol 0`**, where the pinned bar *is* the bar that made the low, so a green bar there is a hammer by construction. The trades the anchor ADDS are +0.054 / +0.107 / +0.089 R, none significant: the first thing here worth measuring twice |

| [`UNDERTOW_SCALE.md`](measurements/UNDERTOW_SCALE.md) | **the 50/5 swing scale against 6/2 — NULL, and the price is not in R.** Δ of −0.061 / +0.019 / −0.006, every one inside one SE in both directions. What it buys: the bias flips **a sixth as often** (2.18 → 0.35 a day on 15m) and the strategy takes **39% of the trades**, for no change in expectancy. A quieter chart for the same money. It STAYS, by the prereg's asymmetric rule — a preference that costs nothing needs no overruling. Third universe to score the engine swap at nothing (+0.060 / −0.038 / +0.007). **Voided twice first, both times by my own checks**, once genuinely and once while the registered condition held exactly |

**It ships anyway, off by default, for one reason.** One explanation survives
all three and no backtest can reach it: whether a human choosing which one in
ten setups to take beats the machine taking all of them. That needs a
*prospective* record — alerts fired forward, taken or skipped, outcomes written
down — and `riptide/watchers/undertow.py` is the instrument for building one.
**19 alerts a day** across 23 symbols on all three timeframes.

[`SPEC.md`](SPEC.md) is the design. **[`SETTINGS.md`](SETTINGS.md) is where
every one of the 65 settings got its value** — 17 from a study, 15 from a
chart, 28 inert, 4 definitions, and the one that was wrong.

## In one paragraph

Find the trend from major/minor market structure and refuse to trade a trend
that is ending. Inside it, wait for the counter-trend-coloured pin at the top
of a pullback — green in a downtrend, red in an uptrend — and take its high,
low and open as three levels. When price has closed beyond **both** the high
and the low, in either order, place a limit at the open. Stop above the
pullback, target 3R.

## What is claimed, and what is not

**Not an edge.** See the table above and the measurement file behind it.

**The candle adds nothing.** A six-arm ablation
([`UNDERTOW_PIN_VALUE.md`](measurements/UNDERTOW_PIN_VALUE.md)) removed one gate
at a time over 12,000 bars x 23 symbols. Full rule minus location-only is
**−0.073, −0.049, +0.092 R** on 15m / 30m / 1h — inside ±0.15 everywhere, not
close to significance, and not even a consistent sign. On two of three, *no
candle test at all* scored higher with twice the trades. The 16-variant
taxonomy, the wick-edge doji margin and the whole of input group 2 are
describing a filter that does not filter.

The honest version of this strategy is one sentence: **take the pullback
extreme while the structure bias is running.**

**THE LARGEST EFFECT FOUND ANYWHERE IN THIS INDICATOR**, and it is given
straight back. Decomposing the backup fill setup by setup:

* a setup that arms, runs 1R away without filling, then retraces into a zone is
  worth **+0.56 to +0.67 R**, on ~400 trades per timeframe, clustered z of
  **4 to 7**. Not noise, not small.
* taking that same zone when price was going to return to the Focus anyway
  costs **−0.23 to −0.29 R**, also z 5 to 7, and it happens ~1.4× as often.

**You cannot take only the good half**: which one you are in depends on whether
price later returns to the Focus, which is in the future at the moment of
entry. The tradeable number is the net, +0.02 R, z 0.6. The split is diagnosis.

That pointed at one clean hypothesis — place the backup only *after* the Focus
limit expires, so pre-emption is impossible by construction — and it has now
been run and **failed structurally**: 100% of the +0.6 R trades fill INSIDE the
20-bar window, median 1–2 bars. There is nothing left for a late design to
take. The two halves are the same population, separated only by what price did
afterwards.

**Three further things are established**, and they are worth more than the
verdict:

1. **The bias gate does two jobs and probably only one works — and this is now
   the top of the queue.** `UNDERTOW_MTF_DEFAULT.md` found the shipped
   `endMinor` rule discarding **64% of trades** on 15m while the configuration
   that keeps it scores **+0.063** against **−0.041** for the one that does
   not. That is uncontrolled: any rule discarding 64% moves the mean. The
   contrast deserves the random-gate control that every recent study built and
   this one pointed at the wrong arm. Note it CONTRADICTS the ablation's A5,
   which removed all the Ending rules and scored better over 11,000 trades. The ghost
   column — setups the gate cancelled, walked forward anyway — says cancelling
   an *already-armed* setup saves 0.40 to 0.61 R each, on all three
   timeframes. But removing the Ending rules entirely (ablation arm A5) is
   *better* than keeping them on 15m, identical on 30m and worse on 1h. Both
   can be true if the cancellation earns its place and the admission block does
   not. That is a hypothesis, nothing here varied the two independently, and it
   is Undertow's most concrete open question.
2. **Selecting on a chart is worth about −0.31 R per trade.** Best-of-48 on
   train, then holdout: −0.377, −0.277, −0.286. Three timeframes, same answer.
3. **A pivot measured in bars really is a different rule on every timeframe,
   and `swingSrc="price move"` fixes it** — a swing as k × the last 24h range
   survives a 4:1 aggregation at ×0.89 against ×0.30 for the bar pivot. It buys
   consistency, not expectancy.
4. **The noise floor of this measurement is about ±0.3 R per trade per cell,
   and it has now been demonstrated twice.** EMA cross swung 0.54 R between two
   halves of the same universe; Slope swung 0.426 R and inverted its sign
   between two time periods of the same symbols. Every positive result this
   project has produced is smaller than that. Any single cell — including
   Slope-in-hours' +0.310 at z +3.61 on Min60 — has to be read against it.
5. **`maxLive = 4` is not a neutral setting.** It exists for TradingView's
   drawing budget, and on these populations it refuses more setups than it
   trades — 683 against 811 fills on 15m at the baseline, and seven to nine per
   fill once a gate is removed. It voided the first ablation run. The chart's
   "at cap" row is the same effect, and any number read off the panel is biased
   by it.

**What the studies cannot say.** The parameter study had 45–153 trades per
panel, an MDE of about ±0.5 R. The ablation is far better powered — 700 to
2,400 trades per arm, and 11,000–12,000 on the widest — and there the best
estimate of the underlying bet lands at **−0.04 to −0.07 R ± 0.03** after 7bp
of fees. That is what a zero-edge entry with costs on looks like. Neither study
finds a rate anyone could trade against in either direction; what they exclude
is the +0.27 to +0.45 R the single charts appeared to show.

The two nearest priors in this repository both came back negative and both
pointed here:

* `indicators/ccp/measurements/CCP_PATTERN_EXPLORE.md` — the same single-candle
  pins, scored at liquidity grabs: no edge, and **the pin added nothing** over
  the location alone.
* `indicators/ccp/measurements/CCP_CONTEXT_FILTERS.md` — EMA / ADX / Supertrend
  trend filters as gates: all failed, and they improved *seeded random entries*
  more than real ones.

Neither refutes this. The bias here is market structure rather than a moving
average, the pin sits at a pullback extreme rather than at a grab, and the pin
is not being asked to predict anything — it supplies the levels. But they are
the closest priors, they point the same way, and the reason v1 is built to be
measurable from the first line is that this design has to clear a bar those two
did not.

The strategy's own evidence before the port was manual bar-replay: ~65% win at
roughly 1:3, which would be about **+1.6 R per trade**. The measured figure on
data nobody looked at first is between **−0.09 and +0.07**. Manual replay has a
known failure mode — a setup is judged valid after its outcome is visible — and
this is what that failure mode is worth.

## "Every quadrant is spent" was wrong

Two measurement pages say it, as a limit on what could be asked next. The venue
lists **594 crypto USDT perpetuals** that pass a mechanical filter; the 23 used
by the first eight studies were never the available data, they were the data
somebody once picked. [`research/symbols_fresh.py`](../../research/symbols_fresh.py)
freezes **two further sets of 45, disjoint from the 23 and from each other**.
`UNDERTOW_HTF.md` is the first study to run on a population nothing here had
looked at; `UNDERTOW_MTF_EMA.md` got its own, because reading a set's baseline
spends it. Fetch with `undertow_sweep.py --fetch-fresh` and `--fetch-fresh2`.
A question now costs ten minutes of fetching to get a universe nobody has
seen, and 594 symbols qualify.

Where the older pages say a holdout is spent, they are right about *those 23*
and wrong about the conclusion drawn from it.

## Every study reproduces its page — audited 2026-09-17

A study that leans on `P`'s defaults stops measuring what its page describes the
moment a default moves, and moves nothing else: it still runs, still prints a
table, and the table is wrong under a name that says otherwise. Two defaults
moved (`swingSrc`, then `slopeUnit`), and three more had moved earlier
(`msLen`/`msShortLen`, `endSweep`/`endStale`, `rr`). Every study now pins what
its measurement was run under, reconstructed from git at each page's own commit,
and every one was **re-run and compared cell by cell**:

| study | checked against | result |
|---|---|---|
| `undertow_sweep` | `UNDERTOW_PARAMS.md` | all 3 tf: train/holdout/control/n exact |
| `undertow_ablation --uncapped` | `UNDERTOW_PIN_VALUE.md` run 2 | 6 arms × 3 tf exact; `A0 − A3` −0.073 / −0.049 / +0.092 exact |
| `undertow_exits` | `UNDERTOW_EXITS.md` | all 3 tf exact **after** a second fix — see below |
| `undertow_backup` | `UNDERTOW_BACKUP_FILL.md` | 4442 armed, `B3 − B0` +0.026 ± 0.047 exact |
| `undertow_late_backup` | `UNDERTOW_LATE_BACKUP.md` | 3 tf exact, incl. the 100%-inside-window diagnostic |
| `undertow_bias` | `UNDERTOW_BIAS_SOURCE.md` | 7 arms exact |
| `undertow_slope` | `UNDERTOW_SLOPE_DEFAULT.md` | +0.310 at z +3.61 exact |
| `undertow_rate` | — | exempt: it is *supposed* to track what ships |
| `undertow_overlap` | `UNDERTOW_OVERLAP.md` | written after the audit; pinned from the start |
| `undertow_htf` | `UNDERTOW_HTF.md` | written after the audit; pinned from the start |
| `undertow_mtf` | `UNDERTOW_MTF_EMA.md` | its M0 reproduces `undertow_htf`'s H0 to the trade, on both shared panels |
| `undertow_mtf_default` | `UNDERTOW_MTF_DEFAULT.md` | carries a pre-registered impossibility (D1 == D1b) that held on 3 of 3 |

**The exits study is why enumerating fields does not work.** The first pass
pinned `swingSrc`, `msLen`, `msShortLen` and `rr` — and missed `endSweep` and
`endStale`, which had also flipped. Exits then chose a *different exit arm* on
two of three timeframes and only the full re-run found it. So
`test_studies_pin_their_settings.py` also fingerprints `P`'s defaults and fails
on **any** of them moving, which is the cause rather than a consequence. When it
fails, re-run the studies before touching the fingerprint.

## Layout

```
SPEC.md                        the design; the Pine is built against it
pine/riptide-undertow.pine     v1 — draws setups and scores them on screen
port/undertow.py               the Python transcription; three swing sources
port/swings.py                 bar pivot · k x ATR · k x a fixed span of time
prereg/                        written before each run — seven of them
studies/undertow_sweep.py      the parameter study
studies/undertow_ablation.py   the six-arm ablation
studies/undertow_exits.py      eight exits on identical fills
studies/undertow_backup.py     the OB/FVG backup, decomposed
studies/undertow_late_backup.py  the same backup, placed after the limit dies
studies/undertow_bias.py       five direction sources, head to head
studies/undertow_rate.py       how many alerts a day — the product decision
studies/undertow_overlap.py    how many of the trades are one idea
studies/undertow_htf.py        the higher-timeframe gate, on fresh symbols
studies/undertow_mtf.py        two timeframes of EMA, aligned or stand aside
studies/undertow_mtf_default.py  the same, against the SHIPPED config
studies/undertow_pullback.py   the three pullback defects in SPEC 2.3b
studies/undertow_v2.py         the corrected rule, whole stack, vs v1
port/smc.py                    LuxAlgo's structure — same swings, same CHoCH
measurements/                  what they concluded

riptide/watchers/undertow.py   THE LIVE ADAPTER, in the bot tree, off by
                               default. A second copy of the machine, held to
                               this one by tests/test_watch_undertow.py
tests/test_undertow_port.py    57 assertions; the parity chain and the orderings
```

## v1 is on the chart

Paste `pine/riptide-undertow.pine` into TradingView. Six input groups, a status
panel top-right, and a debug mode that is off by default.

**What it draws:** the live candidate's three lines as they develop, with a
label saying which confirmations have landed and how many bars in; then, on a
fill, the entry triangle, the stop and target, and the risk / reward zones.
A setup that never fills leaves nothing behind.

**What the panel says:** bias and state, how long the pullback has run, the
counts, what the live candidate is waiting for, and — the row that matters —
*why the last candidate was rejected*. A count alone cannot tell "nothing
qualified" from "the detector is broken".

**What it does not do:** score outcomes, send alerts, or claim anything. There
is no win rate and no R total in it.

## The parity checks — three of them, and each guards a different drift

Pine cannot import and Pine cannot run here, so "the chart and the study are
the same thing" is a chain, not an assertion. All three run inside
`deploy/preflight.py`.

| check | what it holds |
|---|---|
| `deploy/undertow-ms-check.py` | the copied engine in the Pine == the engine in `riptide-indicator-v2.pine`, every condition and assignment, both directions |
| `deploy/ms-py-parity.py` | that v2 engine == `riptide_ms/port/ms_struct.py` |
| `tests/test_undertow_port.py` | `ms_struct.py` == the port's `structure()`, CHoCH / BOS / sweep on identical bars |

Chain those and the port's market structure is the chart's market structure.
Sections 5–7 have no second copy anywhere, so they are held by behaviour
instead — including the three orderings found the hard way on real charts: the
target printing before the fill, one bar spanning entry and stop, and no fill
on the arming bar.

A fourth, `deploy/undertow-port-check.py`, compares every Pine `input.*` to the
port's `P` — same name, same default, same dropdown strings. It is narrower
than a logic check and it caught a real drift on its first run (`rr` defaulted
to 2.0 in the port and 3.0 in the Pine), which is the silent kind: a study
reporting a number for settings the chart is not running.
