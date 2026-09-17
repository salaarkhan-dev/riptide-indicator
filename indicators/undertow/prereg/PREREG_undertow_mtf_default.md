# PRE-REGISTRATION — MTF as the default, against what actually ships

Committed before the first number. Run by
`indicators/undertow/studies/undertow_mtf_default.py`.

## What this adds to a study that already ran

[`UNDERTOW_MTF_EMA.md`](../measurements/UNDERTOW_MTF_EMA.md) already compared
MTF EMA align against the structure engine, on a fresh universe, with a matched
random-gate control. That study's M1 − M0 **is** "MTF as the direction versus
what ships", and it failed bars 3, 4 and 6.

**One thing it deliberately did not do.** Both arms ran **retrace-only
Ending**, because three of structure's four Ending rules read minor structure
and sweeps, which do not exist for an EMA. Matching them was correct for
comparing *directions*.

But "as the default" means the **shipped configuration**, and what ships is
`endMinor = "on the flip"` with `retraceMax = 70`. So the published baseline is
not the chart's baseline, and this closes exactly that gap and nothing else.

## AN IMPOSSIBILITY, PRE-REGISTERED

For a non-structure source the Ending rules that read structure are inert:
`alt_structure` sets `minorChoch = False` and `sOs == os`, so `minorAgainst` is
always False and `endA` can never fire under either `endMinor` setting; sweeps
are all False so `endB` cannot fire; and `endStale` is off in the shipped
defaults so `endC` cannot either.

**Therefore MTF-with-shipped-Ending must be BIT-IDENTICAL to
MTF-with-retrace-only.** Both are run as separate arms and compared.

> **If D1 and D1b differ by so much as one trade, this run is VOID** and the
> cause is a plumbing error in how the Ending rules reach an alternative
> source — which would also mean the published `UNDERTOW_MTF_EMA.md` measured
> something other than what it says.

Only the BASELINE changes between that study and this one. Saying so in advance
is what makes that checkable.

## The arms

| id | direction | Ending | |
|---|---|---|---|
| **D0** | `structure`, `price move` swings | **shipped** (`on the flip`, retrace 70) | **THE BASELINE — what ships today** |
| **D1** | MTF EMA 20/50 ×2 | shipped | **THE PRIMARY** |
| D1b | MTF EMA 20/50 ×2 | retrace-only | must equal D1 exactly |
| D2 | `structure`, `price move` swings | retrace-only | the published M0 config, for continuity |
| **G** | random gate on D1's direction | — | **THE CONTROL**, matched to D1's abstain rate |

Nothing is selected. D1 is fixed as the primary before the run; D1b and D2 are
checks, not candidates.

## Population

**`SYMBOLS_FRESH3`** — ranks 91–135 under the frozen rule, disjoint from the
23, from `SYMBOLS_FRESH` and from `SYMBOLS_FRESH2`. Both earlier fresh sets now
have published baselines, so neither is untouched for a new contrast.

**Rule 3b is added and is a judgement:** pegged bases are excluded.
`USDC_USDT` ranked inside the top 45 and a stablecoin pair has no trend to be
right or wrong about. It is a fixed list rather than a volatility threshold so
it can be checked, and **it was verified to exclude nothing from the 23,
`SYMBOLS_FRESH` or `SYMBOLS_FRESH2`** — it changes no published number.

* 45 symbols, 12,000 bars, Min15 / Min30 / Min60, ≥ 11,000 bars or dropped
* `maxLive = 64`, `rr` 3.5, `locTol` 0, pullback stop, 0.25 ATR buffer, 7bp
* candle, location, confirmations, levels and exit unchanged in every arm

## The metric, and one addition

* **PRIMARY: mean R per trade**, clustered by symbol.
* **REPORTED, because it is what changing a default actually does to you:**
  **setups and trades per day per symbol** under each arm. Switching the
  default changes the alert stream, and a rule with the same expectancy and
  half the alerts is a different product. It is **not** a pass/fail bar — the
  HTF prereg made throughput a bar and it passed for a worthless reason,
  because a negative baseline rewards doing less.
* Reported: % of bars mixed, setups refused while mixed.

## Pre-registered bars, on D1

1. **COVERAGE.** ≥ 200 closed trades.
2. **NOT CONFOUNDED.** `nCap` 0 in every arm, **and D1 == D1b exactly**.
3. **BEATS THE BASELINE.** D1 − D0 ≥ **+0.10 R per trade**, clustered |z| ≥ 2.
4. **BEATS THE RANDOM GATE.** D1 − G ≥ 1 SE.
5. **POSITIVE.** Mean R per trade > 0 after fees.
6. **NOT ONE TIMEFRAME.** Positive on ≥ 2 of 3.

**PROMOTION RULE: `biasSrc` changes default to `MTF EMA align` only if D1
clears 3, 4, 5 and 6.** Nothing less. It is already selectable on the chart;
this is only about what an unconfigured user gets.

## My prediction, recorded before the run

* **D1 − D0 lands within ±0.05 of the published M1 − M0** (+0.009 / +0.050 /
  −0.073), because only the baseline moved and the baseline's Ending rules were
  measured as unstable-but-small: `UNDERTOW_BIAS_SOURCE.md` put shipped-vs-
  retrace-only at −0.14 / +0.15 / −0.03, no sign and no pattern.
* **D1 == D1b.** If not, something is wrong and the run is void.
* **Nothing clears bar 3 or bar 4.** Eleven for eleven.
* **D1 produces FEWER trades per day than D0**, because of the abstain state,
  and that is the honest reason someone might still prefer it — fewer alerts
  for the same expectancy is a real preference, and it is not an edge.
* **The one thing I cannot call** is whether the shipped Ending rules help or
  hurt structure on this third universe. They were −0.14 / +0.15 / −0.03 on the
  first. D0 − D2 measures it again on unseen data, for free, and I expect it to
  be a fourth uninformative answer.

## What cannot happen

* **No new parameter.** 20 / 50 / ×2, as measured.
* **No promotion of D1b or D2.**
* **No falling back to the earlier universes for the primary.**
* **No change to the candle, location, confirmations, levels or exit.**
* **No production change unless the promotion rule is met.**
  `tests/test_control_frozen.py` must still pass.
* **No exchange API key and no order placement.**
* **One study, one run.**
