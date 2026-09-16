# The grab line — final verdict

Everything measured in this sequence, and what it adds up to. Each row links a
pre-registered study; none of the numbers below were chosen after the fact.

## The verdict in one line

**Nothing here is tradeable. One thing is real, unexplained, and too small to
act on.**

## What was tested and what happened

| question | answer | where |
|---|---|---|
| does a grab entry pay? | **no** — gross ≈ 0.00 R over 76,297 grabs, net −0.07 to −0.14 | `CCP_ENTRY_MODELS` |
| does the CCP shape sort them? | **no** | `CCP_ENTRY_MODELS` |
| does a 1.5R partial + breakeven help? | **no — significantly worse**, z −4.2 to −8.3 | `CCP_EXIT_MODELS` |
| can filters be found by looking at the losers? | **no** — +0.089 in-sample became −0.082 out | `CCP_FILTER_OVERFIT` |
| order blocks, EMA trend, ADX, Supertrend? | **all fail**; the trend filters help *random* entries more than grabs | `CCP_CONTEXT_FILTERS` |
| do the sheet's twelve patterns pay? | **no**, and the pin adds nothing — eight of twelve collapse into two | `CCP_PATTERN_EXPLORE` |
| **does an FVG sort grabs at 1h?** | **yes, repeatedly, on unseen data** | `FVG_H1_HOLDOUT`, `FVG_H1_TEMPORAL` |
| is that coherent across timeframes? | **no** — outcome C | `FVG_TIMEFRAME_COHERENCE` |
| is the edge flat gross, with fees explaining it? | **no** | `FVG_GROSS_EDGE` |
| is it the forward horizon? | **no** — the worst arm on the table | `FVG_WHY_1H` |
| does it continue above 1h? | **no** — flat, then fails | `FVG_HIGHER_TF` |
| is it net-positive at 4h/8h? | **not established** | `FVG_NET_HIGHER_TF` |

**Three pre-registered passes. Six pre-registered failures.** Every failure was
an attempt to explain or extend the passes.

## The one thing that survives

At **Min60**, an unfilled directional FVG in the grab window **separates grabs
that pay from grabs that do not**, on populations the hypothesis had never
seen:

```
84 unseen symbols       net Δ +0.076   z +4.12
862 days before         net Δ +0.117   z +9.19
23 discovery symbols    net Δ +0.110   z +5.43
90 non-discovery        net Δ +0.098   z +8.65
```

**The sorting is not in doubt.** Four populations, two of them clean holdouts,
z from +4 to +9, and it beats a random-bar control each time.

## Why that is still not a trade

* **Standalone net R is +0.038 to +0.039.** Positive, and small enough that a
  0.015 R fee drag is already 40% of it.
* **Slippage is not modelled.** The harness assumes a fill at the level. On an
  edge this size that is not a rounding error.
* **Nothing explains why 1h.** Four explanations tested, four refuted. Min15
  and Min30 give zero and negative readings on large samples, and a step change
  between 30m and 1h is not what a mechanism looks like.
* **It does not extend.** Above 1h the edge goes flat and the grab-specificity
  becomes unstable — at Hour4 on one population the control scores +0.089
  against the filter's +0.103, and on another the same control is −0.007.

## What is shipped

Nothing that carries a claim. `riptide-ccp.pine` is a bench: grabs, big grabs,
the twelve CCP patterns, an entry-model drawing layer with a results table, and
context-filter gates — **all off by default, no alerts anywhere, no orders, no
exchange connection.** `riptide-indicator.pine` and `riptide-indicator-v2.pine`
are untouched by this work, and `tests/test_control_frozen.py` passes.

## The only clean test left

A **forward run**: log Min60 FVG grabs as they occur, score them by these
rules, and read the result in three months on data that does not exist yet.

Not a fifth explanation. Four have failed, and a fifth would be picked from the
residuals the first four left behind — `CCP_FILTER_OVERFIT` measured what that
is worth.

## Still open, unrelated to the research

* the leaked Telegram bot token needs rotating via @BotFather — user-side
* `riptide-indicator.pine` lines 721 and 744 still hold unsafe
  `size() == 0 or get(...)` array guards, the RE10045 pattern. Offered, never
  authorised, and a production risk independent of everything above.
