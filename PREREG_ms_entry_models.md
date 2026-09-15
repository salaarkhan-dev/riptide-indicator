# PRE-REGISTRATION — which entry model on the market-structure engine, if any

Committed before the first number. Run by
`research/studies/ms_entry_models.py`.

## The decision this is for

`riptide-indicator-v2.pine` draws structure. The next question is whether any
entry rule built on it is worth shipping as a signal layer, and if so which.

This project has already answered the adjacent question in the negative:
**no definition of inducement sorts Riptide's setups**
(`research/INDUCEMENT_ON_RIPTIDE.md`). That is not this question. That asked
whether structure improves *Riptide*. This asks whether structure, standing on
its own, produces an entry that beats arbitrary timing.

## Population

Every event from `research.ms_struct.engine` — the transcription of section 12,
whose logic is checked statement-by-statement against the Pine by
`deploy/ms-py-parity.py` (currently: every logic statement pairs).

* 30 discovery symbols, Min30 and Min15, 333-day deep window
* split older / newer half by bar index → **four panels**

## What varies, and what does not

**Varying: the entry trigger only.**

| id | model | fires on |
|---|---|---|
| E1 | IDM | the bar an inducement is taken, with trend |
| E2 | BOS | the bar the running extreme breaks, with trend |
| E3 | CHOCH | the bar the trend flips, in the NEW direction |
| E4 | SWEEP | the bar a wick clears the running extreme and closes back inside, AGAINST the trend |
| E5 | IDM→BOS | the first BOS after an IDM in the same cycle — the two-step |
| **E0** | **RANDOM — the control** | a uniformly random bar inside the same cycle, in the cycle's direction |

**Held constant, so the comparison is between triggers and nothing else:**

* **Entry** — the close of the trigger bar. Market, so there is no unfilled
  state and no fill assumption to argue about.
* **Stop** — the live short-period opposing swing (`sBtmY` for longs, `sTopY`
  for shorts). It must lie on the correct side of the entry or **the setup is
  SKIPPED**, never substituted. This is the one stop rule this project has
  established is not degenerate: the signal bar's own extreme gave a median
  stop of 0.42% of price and 99% of losses exceeded 1R (Stage A), and the
  prior structural pivot fixed it (Stage B).
* **Exit** — 2R target or stop, 48-hour horizon, Riptide's maker/taker fees,
  scored by `research.harness.simulate_market`.

## Unit of evidence

**The bet = (symbol, timeframe, CHoCH cycle, direction).** Several signals of
one model inside one cycle are one observation, averaged. Signals inside a
cycle are not independent — they share a trend, a leg and often a level — and
counting them separately is how a t-statistic gets manufactured out of
autocorrelation.

## Primary metric

For each model X, the **paired difference against the random control on the
same cycle**:

    Δ_X = mean( R(X, cycle) − R(E0, cycle) )

Standalone R is reported too, but the paired difference is the primary. A model
that makes money only because its cycles happened to trend is not an entry
model, it is a long position with extra steps — and E0 catches exactly that,
because E0 is in the same cycles, in the same direction, with the same stop
rule, and differs only in *when* it enters.

## Pre-registered bars — all four

1. **COVERAGE.** At least **200 bets in every panel**. Below that the panel is
   reported as not measurable rather than read.
2. **SIGN STABILITY.** Δ keeps one sign across all four panels.
3. **BEATS THE CONTROL.** Δ > 0 in both halves — i.e. the trigger beats random
   timing inside the same structure.
4. **SIGNIFICANCE.** z ≥ 2.0 on the pooled newer half.

### Family-wise inflation, stated before the run

Five models. At z ≥ 2.0 alone, the chance of at least one false positive is
about **20%**. Bars 1–3 carry any pass; bar 4 alone does not, and no result
will be quoted with its z-score and without this sentence.

### Power

Roughly 3,000–6,000 cycles per timeframe are expected. With R's spread near 1.3
and a paired difference cancelling most of the common variance, SE(Δ) should
land near 0.03 R, so bar 4 needs **|Δ| ≈ 0.06 R**. Reachable. Recorded because
stage A once set a bar the sample could not clear.

## Seeding

E0 draws one bar per cycle from `random.Random(hash(symbol, tf, cycle))`, so the
control is identical on every re-run and cannot be re-rolled into a better
comparison.

## What cannot happen

* **No production change.** Nothing under `riptide/`; the frozen control test
  must still pass.
* **No exchange API key, no order placement, no execution code.**
* **No parameter tuning.** `msLen = 50` and `msShortLen = 3` are the pasted
  script's own defaults and are not swept. The target, horizon, fees and stop
  rule are fixed above. A losing model does not get a second stop rule.
* **No retrospective filtering** of symbols, timeframes or cycles.
* **One study, one set of models.** There is no v2 of this covariate. If every
  model fails, that is the finding.

## If nothing passes

Then the structure layer stays what it already is: context, drawn because
reading structure by eye is a legitimate reason to draw it, with no signal
layer and no stats table claiming a record. `riptide-indicator-v2.pine` already
ships exactly that, and it would not change.

A model that passes earns an entry layer in the Pine — **shipped off by
default**, labelled with what it is, and carrying a stats table that reports
its standard error, its worst drawdown and its total R without its best trade
alongside any headline number.
