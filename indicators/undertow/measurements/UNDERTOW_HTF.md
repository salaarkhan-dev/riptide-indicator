# The higher-timeframe gate does nothing, and it does nothing more than a coin

Against [`PREREG_undertow_htf.md`](../prereg/PREREG_undertow_htf.md).
**45 fresh symbols, disjoint from the 23 every other study here has used**,
12,000 bars each, 15m / 30m / 1h, 7bp fees. One arm fixed in advance, scored
once per timeframe. Nothing selected, no maximum taken.

## The verdict

| tf | H2 (HTF 4h) | H0 (off) | Δ | z | **random gate** | **H2 − random** | n | bars 1-5,7 |
|---|---|---|---|---|---|---|---|---|
| Min15 | +0.012 | −0.022 | +0.034 | +0.63 | −0.021 | **+0.032 ± 0.056** | 6771 | PP..PP |
| Min30 | −0.037 | −0.046 | +0.009 | +0.18 | −0.047 | **+0.010 ± 0.052** | 8044 | PP...P |
| Min60 | −0.121 | −0.098 | −0.023 | −0.56 | −0.092 | **−0.029 ± 0.041** | 8060 | PP...P |

**Bar 3 failed 3 of 3. Bar 4 — beat a random gate discarding the same number of
trades — failed 3 of 3. The gate is not promoted.**

## The one number that matters

A gate only removes trades, and **any rule that discards 30% of them moves the
mean — about half of all such rules move it up.** So the control here is not a
random entry, it is a **random gate**: same symbols, same count refused, chosen
by a seed instead of by the higher timeframe.

Against that control the HTF gate is worth **+0.032, +0.010 and −0.029 R per
trade**, on a combined 22,875 trades, with diff SEs of 0.04–0.06.

Refusing 23–30% of setups because a 4-hour structure disagrees is, to the
resolution of this measurement, **the same thing as refusing 23–30% of them at
random.** The higher timeframe is not carrying information.

## Why this is the strongest negative in the project

| | previous eight studies | this one |
|---|---|---|
| population | the same 23 symbols throughout | **45 symbols never looked at** |
| holdout | a quadrant, increasingly spent | the entire universe, unseen |
| selection | a maximum of 6–48 configs, usually | **none — one arm fixed in the prereg** |
| control | random *entry* | random *gate*, matched on rejection rate |
| trades per arm | 500–2,600 (12,000 on the widest) | **6,771–8,060** |
| diff SE | 0.05–0.19 | **0.04–0.06** |

Two measurement pages here say "every quadrant is spent" as a limit on what
could be asked next. **That was wrong, and finding out is worth more than the
result.** The venue lists 594 crypto USDT perpetuals that pass a mechanical
filter; the 23 were never the available data, they were the data somebody once
picked. [`research/symbols_fresh.py`](../../../research/symbols_fresh.py)
freezes 45 more.

## What the descriptive arms show

| arm | Min15 | Min30 | Min60 | refused (15m) |
|---|---|---|---|---|
| H0 off *(baseline)* | −0.022 | −0.046 | −0.098 | 0 |
| **H2 HTF 4h** *(primary)* | **+0.012** | **−0.037** | **−0.121** | 11,882 |
| H1 HTF 1h | −0.018 | −0.044 | −0.108 | 5,564 |
| H3 HTF 12h | +0.016 | −0.000 | −0.081 | 20,850 |
| H4 HTF ×4 bars | −0.018 | −0.046 | −0.121 | 5,564 |

Coarser is very slightly less bad and it costs trades to get there — H3 refuses
20,850 setups on 15m to move the mean by 0.038 R. Nothing here is a finding and
none of these arms was eligible to be one.

**The unit conversion is verified three ways.** On 15m, `htfHours 1.0` and
`htfMult 4` both resolve to mult 4 and produce **bit-identical** runs
(−0.018, n 8327). On 1h, `htfHours 4.0` and `htfMult 4` are likewise identical
(−0.121, n 8060). On 30m they correctly differ, because 1h there is mult 2 and
`×4` is 2h. That was a pre-registered prediction and it held exactly.

## A BAR I GOT WRONG, and it passed 3 of 3

**Bar 7 — "R per 1,000 bars ≥ the baseline's" — is meaningless here and I
should have seen it when writing the prereg.** It passed everywhere:

| tf | H2 R/1k | H0 R/1k |
|---|---|---|
| Min15 | +0.153 | −0.415 |
| Min30 | −0.578 | −0.983 |
| Min60 | −2.262 | −2.381 |

The baseline is **negative on all three**. Doing less of a losing thing raises R
per bar mechanically, so bar 7 as written rewards any gate at all, including the
random one. It was designed for a positive baseline and there isn't one. It
should have read "if the baseline is positive, the gate must not cut throughput";
as written it carries no information and the three PASSes above should be read
as blank.

## Against the prediction

| predicted | actual | |
|---|---|---|
| H2 fails bar 4 | failed 3 of 3, and by margins inside 1 SE | right |
| H2 raises R per trade but **fails bar 7** on throughput | raised R per trade on 1 of 3; bar 7 passed 3 of 3 **because the bar is broken** | wrong, and wrong about my own bar |
| H4 ≈ H1 on 15m exactly | bit-identical | right |
| the fresh universe is not kinder | baselines −0.022 / −0.046 / −0.098, worse than the 23 | right |
| bar 4 is the one that could surprise me | it did not | right |

## What this does and does not rule out

**Ruled out:** *this* HTF gate — the same structure engine, run one timeframe
up, as an AND gate on direction and tradeability — on liquid crypto perps at
15m / 30m / 1h, to a resolution of about ±0.10 R per trade.

**Not ruled out, and worth being clear:** the gate runs the *structure engine*
on coarser bars, and eight studies already say that engine carries no edge on
the base timeframe. Running an uninformative rule on coarser data is not a
strong test of "higher-timeframe context" in general. An HTF direction from
something else entirely, or a gate that reads HTF *level* rather than HTF
*direction*, is a different question. It would need its own prereg — and now it
can have a clean population to run on.

The gate also requires the higher timeframe to be **tradeable** as well as
agreeing, which is two conditions where the hypothesis was one. That is
conservative and it is a design choice this page did not vary.

## What changes

**Nothing ships.** `htfUnit` defaults to `"bars"` and `htfMult` to 0, so the
gate is off, exactly as it was before this study. It stays available in the
port because a measured null is worth keeping runnable.

**It does not go on the chart.** An honest HTF bias in Pine needs the whole
structure slab inside a function so `request.security` can evaluate it on
higher-timeframe bars, which would break `undertow-ms-check.py`'s anchor
against v2. That refactor was the price of putting it on the chart and the gate
did not earn it.

**The 45 symbols stay, and they are the real output of this study.** Nine
components have now been ablated with no effect, and this is the first one that
cannot be blamed on a spent holdout or a lucky quadrant. Every future question
gets a population nobody has looked at — including, still, the only question no
backtest reaches, which is whether a human picking one setup in ten beats the
machine taking all of them.
