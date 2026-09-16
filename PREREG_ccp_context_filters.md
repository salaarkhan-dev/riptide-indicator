# PRE-REGISTRATION — do order blocks, FVGs or trend filters sort grabs?

Committed before the first number. Run by
`research/studies/ccp_context_filters.py`.

## The decision this is for

Three runs have now found nothing in a grab entry:

* `research/CCP_ENTRY_MODELS.md` — gross expectancy at a grab is about **zero**;
  the CCP shape filter does not sort winners from losers.
* `research/CCP_EXIT_MODELS.md` — a 1.5R partial with the stop to breakeven is
  **significantly worse** than a plain 2R exit, z −4.2 to −8.3 over six panels.
* `research/CCP_FILTER_OVERFIT.md` — filters mined from the failures give back
  more than they appear to make: +0.089 → −0.082 and +0.078 → −0.032.

That last file names the one legitimate route left: **a filter with a mechanism,
fixed before anyone looks at which trades it excludes.** This is that study.
Six conditions, named here, defined here, not swept.

## The prior, and my prediction, recorded before the run

`research/studies/ccp_excursion.py` bounds what is available: after a grab,
price beats a risk-matched random entry by about **1.5 points** on the
+1R-first race — roughly **+0.03 R** — against a measured fee drag of **0.05 to
0.14 R**. For any filter to make this tradeable it must find a subset with a
gross edge far above the population's zero, which means some complementary
subset must be strongly negative.

**My prediction: all six fail bar 4.** I expect the trend filters (F3, F5) to
reduce the loss slightly without turning it positive, because a grab is a
mean-reversion event and "with trend" mostly re-labels it as momentum
continuation, which is a different bet and also averages zero. I further expect
that whatever they do at grabs, they do at random bars too — which is bar 6, and
is the bar I expect to kill them.

If a filter passes all six, I am wrong and it earns a forward-tracking run.

## Population and what is held constant

Identical to `PREREG_ccp_exit_models.md`, so **X1 there is this study's
unfiltered baseline** and the two are directly comparable.

* every grab from the **3/3 narrow instance**, 23 symbols
* **Min15 / Min30 / Min60**, 333 days, older/newer halves → six panels
* entry: close of `grabBar + ccpFwd`, market
* stop: extreme of the grab window **minus 0.25 × ATR**
* target 2R, horizon 48 hours, `research.harness` fees, `simulate_market`

**The CCP shape filter is NOT applied.** It was measured and adds nothing, so
stacking it here would only shrink the sample and confound the question.

## The six arms, defined exactly

Each is a binary condition evaluated **at the signal bar**, using only closed
bars. No parameter is swept; every number below is fixed now.

| id | condition |
|---|---|
| **F1** | **ORDER BLOCK.** Scanning back at most 20 bars from the grab bar, take the most recent opposite-colour candle (`close < open` for a long, `close > open` for a short) that was *displaced* — some later bar up to the signal bar exceeded its high (long) or broke its low (short). F1 holds when the **signal bar's range overlaps that candle's range**. |
| **F2** | **FAIR VALUE GAP.** A three-bar imbalance formed at bar *i* with *i* in `[grabBar − 1, signalBar − 1]`: for a long `low[i+1] > high[i−1]`, for a short `high[i+1] < low[i−1]`. F2 holds when such a gap exists **in the trade's direction** and is still **unfilled** at the signal bar. |
| **F3** | **EMA TREND.** `EMA(50) > EMA(200)` for a long, `<` for a short, at the signal bar. |
| **F4** | **ADX REGIME.** Wilder `ADX(14) ≥ 20` at the signal bar. Direction-agnostic on purpose — this arm tests *trending vs ranging*, not direction. |
| **F5** | **SUPERTREND.** `Supertrend(10, 3.0)` direction agrees with the trade at the signal bar. |
| **F6** | **CONFLUENCE.** F1 **and** F2 — the one combination anyone actually asks for. |

**No other combination is tested.** Pairs are where the last study found its
+0.089 that became −0.082, and 105 candidates is how that happened.

**Each filter is tested as AGREEMENT only.** A filter and its complement
partition the population, so the complement's number is reported as
information — but a complement that looks good is a **hypothesis for a future
prereg, not a pass here.** Running both directions and keeping the better one
is a two-sided test dressed as a one-sided one.

## Unit of evidence and metric

**The bet = one grab.** SEs clustered by **(symbol, calendar day)**.

For each arm, the difference between the grabs it keeps and the grabs it drops,
within a panel:

    Δ_F = mean R( F holds ) − mean R( F does not hold )

Standalone net R is reported for every arm. **The standalone number decides
whether anything is tradeable; Δ only decides whether the filter is doing work.**

## Pre-registered bars — all six

1. **COVERAGE.** ≥ 200 kept bets in every panel, else that panel is not
   measurable.
2. **SIGN STABILITY.** Δ keeps one sign across all six panels.
3. **BEATS UNFILTERED.** Δ > 0 on the newer half of all three timeframes.
4. **MAKES MONEY.** Standalone net R > 0 after fees on the newer half of all
   three timeframes.
5. **SIGNIFICANCE.** Clustered |z| ≥ 2.0 on the pooled newer half.
6. **IT IS ABOUT GRABS.** Δ at grabs must exceed Δ from the *same filter*
   applied to seeded random-bar entries with the same direction and the same
   risk fraction. A trend filter that improves any entry equally has told us
   about the market, not about grabs.

### Family-wise inflation, stated before the run

Six arms, with the primary test pooled across timeframes on the newer half →
**six primary tests**. At z ≥ 2.0 each, the chance of at least one false
positive is roughly **26%**. The six panels feed bar 2, not six separate
significance claims. **Bar 5 alone carries nothing and no result from this study
will be quoted with its z-score and without this sentence.**

### Power, and the escape hatch

Tens of thousands of grabs give SE(Δ) near 0.02 R unfiltered, rising as a
filter cuts the sample. If a panel's minimum detectable effect exceeds
**0.10 R**, that panel is declared **UNDERPOWERED** and reported as a bound
rather than a verdict. F6 is the arm most at risk, since two conditions
together may not leave 200 bets.

## What cannot happen

* **No parameter sweeps.** 20-bar OB lookback, EMA 50/200, ADX 14 at 20,
  Supertrend 10/3.0, FVG within the grab window. If a filter fails, a
  differently-tuned version of it does **not** get a turn in this study.
* **No extra combinations** beyond F6.
* **No counter-trend rescue.** See the agreement-only rule above.
* **No production change.** Nothing under `riptide/`;
  `tests/test_control_frozen.py` must still pass.
* **No exchange API key, no order placement.** Measurement only.
* **One study.** There is no v2 of this prereg.

## If nothing passes

Then the grab layer stays what it has been all along: context, drawn because
reading levels by eye is a legitimate reason to draw them, with no entry, no
alert and no claim. Four studies will have said the same thing four ways, and
the honest conclusion is that this particular event does not carry a tradeable
edge at these costs — not that a fifth filter family is needed.
