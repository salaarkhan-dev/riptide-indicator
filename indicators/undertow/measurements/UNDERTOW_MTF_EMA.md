# The second timeframe buys nothing: −0.005 to +0.020 R across six panels

Against [`PREREG_undertow_mtf_ema.md`](../prereg/PREREG_undertow_mtf_ema.md).
From a supplied Pine script, *MTF Market Structure Bias* — EMA 20/50 on two
timeframes, FULL BULLISH / FULL BEARISH / MIXED, stand aside on MIXED.

**Primary population: `SYMBOLS_FRESH2`**, ranks 46–90, disjoint from the
original 23 *and* from `SYMBOLS_FRESH`. One arm fixed in advance, scored once.

## The verdict

| tf | M1 (MTF ×2) | M0 (ships) | M2 (one TF) | Δ vs M0 | z | **random gate** | n | bars |
|---|---|---|---|---|---|---|---|---|
| Min15 | −0.012 | −0.021 | −0.032 | +0.009 | +0.18 | −0.033 | 8335 | PP... |
| Min30 | +0.032 | −0.018 | +0.029 | +0.050 | +1.01 | +0.035 | 8291 | PP..P |
| Min60 | −0.142 | −0.069 | −0.143 | −0.073 | −1.29 | −0.152 | 6967 | PP... |

**Bar 3 failed 3 of 3. Bar 4 failed 3 of 3. Bar 6 failed (1 of 3 positive).
Not promoted.**

## The number the study was built to produce

M1 is M2 plus the alignment gate, so **M1 − M2 is exactly what the second
timeframe buys.** Across all six panels:

| | Min15 | Min30 | Min60 |
|---|---|---|---|
| **FRESH2** (primary) | **+0.020** | **+0.003** | **+0.001** |
| **FRESH** (secondary) | **+0.003** | **+0.004** | **−0.005** |

**Between −0.005 and +0.020 R per trade, on 47,000 trades.** Requiring a second
timeframe to agree — the entire idea of the script — adds nothing to a
single-timeframe EMA 20/50 cross. Against a random gate discarding the same
count, M1 is worth +0.021, −0.003 and +0.010.

Whether the EMA cross is a good direction is a separate question with its own
answer above (M2 is −0.032 / +0.029 / −0.143, and M0 the structure engine is
−0.021 / −0.018 / −0.069). Neither is an edge. But the *MTF* part specifically
contributes nothing measurable in either direction.

## Why the abstain state does less than 19% suggests

MIXED fires on **18–19% of bars** and removes only **7–9% of trades**.

The gap is the mechanism. A setup has to be armed *while* the timeframes
disagree for the abstain to cancel it, and disagreement clusters in chop —
where the structure is flat and fewer setups arm in the first place. The 19% of
bars that look gated are largely bars that were not going to produce a trade.

This is the most useful diagnostic here: "stand aside when timeframes disagree"
was the one piece of folklore in this sequence with a plausible mechanism (chop
kills pullback-continuation, and disagreement detects chop), and the reason it
does nothing is that **it mostly stands aside from nothing.**

## THE PREREG EARNED ITS KEEP, visibly, in this run

M3 — MTF EMA **50/200** — was descriptive and could not be promoted. Look at
what it printed:

| M3 | Min15 | Min30 | Min60 |
|---|---|---|---|
| **FRESH2** | **+0.053** | **+0.074** | −0.011 |
| **FRESH** | **−0.066** | **−0.020** | **+0.015** |

**The sign flips on all three timeframes between two universes drawn by the
same rule on the same day.** Had the prereg not fixed M1 as the primary in
advance, +0.053 and +0.074 on the primary population would have read as the
first positive finding in this project — and the panel directly beneath it
contradicts them.

That is the third time this has happened here (EMA cross swung 0.54 R between
halves; Slope inverted by 0.426 R between periods) and the first time it was
caught by a rule written before the run rather than by a re-measurement
afterwards.

## The cross-study machine check passed exactly

`SYMBOLS_FRESH` ran as a secondary panel with one job: M0 here must equal H0 in
[`UNDERTOW_HTF.md`](UNDERTOW_HTF.md), because the two studies pin identical
settings.

| | Min15 | Min30 | Min60 |
|---|---|---|---|
| M0 here | −0.022 (n 9608) | −0.046 (n 11011) | −0.098 (n 10451) |
| H0 there | −0.022 (n 9608) | −0.046 (n 11011) | −0.098 (n 10451) |

Identical to the digit and to the trade. Two independently written studies are
running the same machine.

## A CORRECTION TO THE SCRIPT, worth more than the measurement

```pine
biasEMA20 = request.security(syminfo.tickerid, biasTF, ta.ema(close, fastLen))
```

On the live bar this returns the **forming** higher-timeframe EMA, so the table
flips intrabar and the historical chart is cleaner than live trading was. The
fix is to read the completed bar:

```pine
biasEMA20 = request.security(syminfo.tickerid, biasTF, ta.ema(close, fastLen)[1])
```

**The port does not reproduce the repaint** — the slower EMA comes from
aggregated bars whose verdict lands on a base bar only from the bar *after* the
one that closed it, the same rule `htf_dir` follows. So the numbers above are
what the rule would have done honestly, and they are the pessimistic version
only in the sense that the repainting version would have looked better without
being tradeable.

Two smaller things: `structureTF = "15"` on a chart above 15m is a request for
a *lower* timeframe, which `request.security` will answer but not meaningfully;
and with `structureTF` equal to the chart timeframe the "structure" row is just
the chart's own EMA cross.

## Against the prediction

| predicted | actual | |
|---|---|---|
| M1 fails bar 3 | failed 3 of 3 | right |
| M1 − M2 small and positive, +0.00 to +0.05 | +0.020 / +0.003 / +0.001 | right |
| M1 fails bar 4 | failed 3 of 3 | right |
| M2 has more trades than M0 and a worse mean | more trades on 15m/30m, fewer on 1h; mean worse on 15m/60m, better on 30m | half right |
| M3 ≈ M1 within 0.05 | M3 is 0.06–0.16 away and unstable in sign | wrong |
| "what would surprise me: M1 clearing bar 4" | it did not | right |

## What changes

**Nothing ships.** `biasSrc` stays `structure`. `BS_MTF` stays in the port as a
dropdown value, off, with the page that says what it scored — the same place
EMA, Slope and Range midpoint sit.

**It does not go on the chart.** The promotion rule required bars 3, 4, 5 and
6; it cleared none of 3, 4 or 6.

**Three universes now exist**, disjoint, frozen, 45 symbols each beyond the
original 23. The tenth component has been measured without an effect, and the
thing that keeps improving is not the strategy — it is the ability to find that
out quickly and on data nobody has looked at.
