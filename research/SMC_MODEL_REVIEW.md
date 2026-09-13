# SMC model review — 15 models, what each scored, and what went wrong

Self-contained export for outside analysis. Everything needed to reason about
these results is in this file; no repository access required.

---

## 1. What the system is

A liquidity-sweep bot on MEXC crypto perpetual futures. It sends Telegram
alerts; a human takes the trades. **No orders are placed programmatically.**

The deployed model, in one line:

```
liquidity pool  →  sweep (raid)  →  market-structure shift  →  price returns to
the fair-value gap  →  limit entry at the gap's near edge  →  stop at the raid
extreme  →  target 2R
```

Two signal types are sent:

- **CONFIRMED** (`🎯`) — the full sequence above, including the structure shift.
- **EARLY** (`⚡`) — sweep + gap, *without* waiting for the shift. ~5× the traffic.

Deployed gates: daily point-of-interest required on the raid; grade B+ (which
requires the Hour8 SuperTrend and Hour8 DI to agree with the trade); a sweep
relative-volume gate; timeframes Min30 + Min15.

---

## 2. Measurement method — read this before the table

Getting these details wrong is how earlier versions of this work produced
confident nonsense, so they are stated explicitly.

| item | value | why it matters |
|---|---|---|
| **Universe** | 60 most-liquid USDT perps | refreshed every 6h |
| **Sample** | **42 days** (2000 bars of Min30) | the binding constraint on everything |
| **Fees** | **0.010% maker / 0.022% taker** | derived from a real settlement, NOT the published 0.02/0.06 — an earlier project-wide error charged double and reversed at least one conclusion |
| **Fee cost in R** | `fee_pct / risk_pct` | **convex in 1/risk** — a tight stop pays enormously more. This drives several results below |
| **Unit of account** | **one bet per candle close** | dozens of symbols fire the same direction on one close; counting them separately inflates n, the streak length and the significance |
| **Drawdown** | uncapped R equity curve, 1 unit per trade, exit-time order | deterministic. An earlier portfolio simulator had an 8-slot cap and gave +20% and +11% for the *same* rule on two runs |
| **Splits** | time (discovery/held-out) and symbol (odd/even) | choices made on discovery, read once on held out |
| **Nulls** | **circular shift** (rotate each symbol's feature series in time) | preserves autocorrelation and keep-rate exactly. A coin-flip null was too lenient — it cleared 2 SE only 2% of the time against a textbook 4.6% |

**Base rate to keep in mind: roughly 45 hypotheses have been tested in this
project and one survived.** Any table of 15 models will contain cells that look
good by chance.

---

## 3. THE TABLE

Status key — **DEPLOYED**: running live. **DEAD**: tested, failed. **COVERED**:
equivalent to something already tested. **UNTESTED**.

| # | Model | Status | Score | The issue |
|---|---|---|---|---|
| 1 | Sweep → MSS → FVG *(the core)* | **DEPLOYED** | Min30 confirmed **52% win, +0.509 R/bet** (73 bets); held out 61%, +0.801 (23 bets) | **Held-out sample is 23 bets.** The live recommendation rests on this |
| 1b | Entry variations (12 locations) | **DEAD** | Deployed near-edge is **best of 12** on both panels. Fib 0.786 worst at **−0.152 R/signal (−3.5 SE)** | A better price = a tighter stop = a bigger fee. For Fib 0.786 the extra fee is **+0.131 R** and the extra loss is **0.123 R** — the same number |
| 2 | Sweep → MSS → **Order Block** retest | **DEAD** | OB +0.079 ± 0.014 vs shipped +0.059 ± 0.018 @1R. Paired **+1.6, +1.6, +1.1 SE** | (a) An OB exists for **1899 of 1899** setups, so it cannot act as a filter. (b) OB-stop risk is 0.6% vs the baseline's 1.5% — most of the apparent gain is **an unpaid fee**. (c) Trend-aligned, the shipped entry is best |
| 3 | FVG + OB **confluence** | **SHIPPED as a score** | +1.4 SE. Best bucket (gap + OB + breaker agree, with trend) = 9% of signals at **+0.170 ± 0.057** | Not strong enough to gate on, so it is displayed rather than enforced |
| 4 | **Breaker block** | **DEAD** | +0.058 to +0.079 ± 0.017 vs shipped +0.059. Paired **−0.1, +0.9, +0.5 SE**. Breaker alone as confluence: **+0.6 SE** | Same tight-stop fee artefact. Also: the first implementation wasn't a breaker at all (wrong polarity) — found and fixed, then re-measured |
| 5 | Aggressive: sweep → displacement → FVG, **no MSS** | **DEPLOYED — this is the ⚡ EARLY signal** | Held out, per bet: **−0.009 R, 37% win, 302 bets**. Min30 early alone **−0.072** | It is **88% of all traffic and worth approximately zero.** Kept as a heads-up, not a trade |
| 6 | Judas swing / session | **DEAD** | 6 GMT buckets; best−worst **+2.7 SE** | Max-minus-min of **six** buckets produces 2–2.5 SE from noise alone, and the winner was a single hour with the smallest sample (n=113) |
| 7 | PDH / PDL sweep | **DEPLOYED** (`use_daily`) | Day pool **+0.094 ± 0.035** (311 setups) vs Pivot **+0.048 ± 0.017** (1686) | +1.2 SE — nothing. Weekly pool: **295 sweeps produced 0 setups**, so it is switched off |
| 8 | Equal high / equal low | **COVERED — it *is* the pivot pool** | `tol_atr` swept 0.15 / 0.25 / 0.35 / 0.50; **the shipped 0.25 is best** | Clustering pivots within a tolerance *is* equal-high detection. Nothing new to add |
| 9+10 | Internal→external liquidity / **opposing liquidity as TP** | **DEAD** | Nearest pool held out **+0.111 vs 2R's +0.775 = −1.9 SE.** On Hour4 (333 days) every liquidity policy is negative on both held-out panels | **The nearest unswept pool sits at a median of 1.1–1.2R, and 77–81% are closer than 2R.** "Target the liquidity" is just a *closer target* — the exit dial again. Win rate 53%→57%, money down |
| 10b | Liquidity **distance as a filter** | **DEAD, and informative** | Holding the exit at 2R and taking only trades whose nearest pool is 2R+ away: win rate **53% → 29%** (−1.8 SE) | Far-away liquidity marks **worse** trades. **Confound:** "pool far in R" ≈ "stop is tight", so this may be re-measuring tight stops |
| 11 | **FVG continuation** (trend, no sweep) | **DEAD** | Best arm **+0.038 R/bet held out, +2.0 SE vs control** (+1.7 at zero fees). Hour4: **+0.4 SE** | Fails the 333-day check. **57% overlap** with existing signals on Hour4 — not an independent stream. **37 bets/day** vs 1.8 for the deployed cell |
| 11b | *(control inside model 11)* | — | Counter-trend gaps **−0.588** vs with-trend **+0.038** — a 0.63 R gap, the biggest number in the study | That separation is **the Hour8 trend filter, already deployed**. The control existed precisely to catch this |
| 12 | MSS retracement | **COVERED** | Fib 0.5 of leg **−0.030** vs deployed **−0.029** R/signal | Same entry axis as 1b; flat |
| 13 | Displacement candle 50% | **COVERED** | = Fib 0.5 of the leg, above | as above |
| 14 | **Premium / discount filter** | **UNTESTED** | — | The one adjacent test was **degenerate and that is a flaw in the test**: 97% of entries already sit past 50% of the raid leg, so the split had nothing to compare. **The filter itself has never been tested** |
| 15 | Multi-timeframe liquidity | **DEPLOYED** | The **daily POI gate** is the strongest single filter in the system, and the **only** filter to pass a pre-registered held-out test on symbols it was not found on | MTF *agreement* (two timeframes confirming) was tested separately and died |

### Additional models tested outside the 15

| model | result |
|---|---|
| Trendline break as entry quality / as a trailing stop | dead (deployed only as an unproven display mark) |
| Support/resistance break indicator | dead |
| RSI divergence | dead |
| 31-feature batch (ADX, MACD, VWAP, EMAs ×4 HTFs, SuperTrend, exhaustion, Fib) | **all dead** under the circular-shift null |
| BTC regime filter | dead |
| Pool memory | dead |
| 25 exit policies (targets 1–3R × plain/BE/partial) | **plain 2R wins** |
| Pivot pool grid (7 parameters, 19 configs) | **shipped defaults are the top of the grid** |
| "3+ touch" pool filter | dead — real 1.69 SE against a circular-shift null p95 of **2.56 SE** |
| **Sweep relative-volume gate** | **THE ONE SURVIVOR.** +13.5 SE, reproduced live (44.2 → 15.7 alerts/day) |

---

## 4. Four findings that recur across every study

**1. The win rate is a dial the exit sets, and turning it costs money.**
Same trades: **65% wins for −3% return, or 39% wins for +20%.** Every attempt to
raise the win rate through the exit (partials, break-even, closer targets,
liquidity targets) has lost money. Four independent confirmations.

**2. Risk *distance* dominates entry *logic*.** Appears four separate times.
The clearest instance — same signals, same entries, only the stop moves:

| gap ≥ 0.25 ATR (model 11) | risk | win | R/bet |
|---|---|---|---|
| stop at the gap's far edge | 0.49% | 39% | −0.141 |
| stop under the whole leg | 1.19% | 44% | **+0.038** |

**+0.18 R from the stop alone** (+0.108 at zero fees, so ~60% real / ~40% fee).
The mechanism is arithmetic: fee-in-R = `fee_pct / risk_pct`, convex in 1/risk.

**3. Signals are not independent draws.** The deployed stream's worst losing run
is **40 trades inside 12 hours** (24 inside 3.8 hours held out). One market move
takes out everything open at once. Counting those as separate trades makes the
streak, the sample size and every standard error a fiction.

**4. The only legitimate win-rate improvement was cell selection, not tuning.**
Pooled stream 42% → Min30 confirmed **52%** per bet. Nothing about the exit or
the entry changed; fewer trades were taken from a better population.

---

## 5. Known limitations — please attack these

**SAMPLE SIZE is the binding constraint.** 42 days, 60 symbols. SE on the key
cell's R/bet is **0.17**. A genuine +0.15 R filter would register at 0.9 SE and
read as "inside noise." **Most of the ~45 dead tests could not have detected a
real effect even if one existed.** "Inside noise" mostly meant *underpowered*,
not *nothing there*.

**Newly discovered:** the exchange caps one response at 2000 bars, but serves
any window. Paging back yields **333 days with zero discontinuities in ~3
seconds per symbol** — 8× the history, available the whole time and never used.
SE would fall ~2.8× to about 0.06.

**Survivorship bias in that deep window.** The universe is the top 60 by volume
*today*. Going back 333 days over-samples coins that went up and excludes ones
that died. Absolute expectancy from the deep window will be biased optimistic
(longs more than shorts). Filter-A-vs-filter-B comparisons are much less
affected, since both arms draw from the same biased pool.

**Multiple comparisons.** ~45 tested, 1 survivor ≈ a 2% base rate. Any new sweep
will hand back a best-on-discovery cell regardless of whether anything is there.

**A proposed "Strategy Matrix"** (Liquidity × MSS × Entry × SL × TP × Timeframe)
was rejected for this reason: thousands of cells on 42 days would produce ~50
cells at 2 SE from pure noise with no way to tell which.

---

## 6. Current state

| | value |
|---|---|
| Recommended policy | take **Min30 CONFIRMED** only |
| Traffic | **1.8 separate bets/day**; 29 of 42 days had one; longest silence 4.5 days |
| Win rate | 52% per bet (61% held out, 23 bets) |
| R per bet | +0.509 (SE 0.172) |
| Worst losing run | 10 bets over 3.4 days |
| Break-even win rate at 2R | **~35% with fees** |
| Sizing rule | same-close alerts = **one bet**, sized once |

---

## 7. Questions worth an outside view

1. Given a ~2% historical hit rate across 45 tests, **how should 8× more data be
   spent** without simply repeating the same multiple-comparisons error at
   higher resolution? Re-test the survivors, re-test the near-misses, or test
   new hypotheses?

2. Is there a **model class structurally absent** from this list? Everything
   tested varies the entry, the exit or the filter of one trade. Position
   sizing, correlation-aware portfolio construction and regime conditioning are
   comparatively untouched.

3. Finding #2 says risk distance dominates. **Is a floor on risk-in-percent the
   right formalisation, or is this really a position-sizing problem?** Note a
   floor on risk-in-*ATR* was tested at three thresholds and found nothing — but
   fees are a fixed % of notional, so ATR is arguably the wrong normaliser and
   that test may be mis-specified.

4. At a 2R target with break-even ~35%, **is 52% near the ceiling** for this
   trade family? If so the effort should move from win rate to traffic,
   sizing, or a genuinely uncorrelated second stream.

5. Model 14 (premium/discount) is the only one of the 15 never properly tested.
   **Is it worth testing, given that the adjacent Fibonacci test was degenerate
   at 97% one-sided?**
