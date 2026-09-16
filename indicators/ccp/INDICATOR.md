# CCP — combined candle patterns, and the grab line

**Status: research bench. Verdict: nothing tradeable.** Nothing here sends an
alert, arms an outcome, or reaches the bot. It is kept because the work is
worth being able to re-run, not because it produced a signal.

```
pine/riptide-ccp.pine      the bench — grabs, big grabs, the twelve patterns,
                           an entry-model drawing layer, context-filter gates.
                           Everything off by default, no alerts anywhere.
detector.py                the twelve patterns as code: 4 x 1CP + 8 x 2CP
sheet.py                   the pattern sheet the twelve came from
studies/                   every measurement, with the .out it produced
tools/                     the audits: merge, anchor, grabs, reject reasons
measurements/              what each study concluded
prereg/                    what was promised before each one ran
```

**Read [`measurements/GRAB_LINE_VERDICT.md`](measurements/GRAB_LINE_VERDICT.md)
first.** It is the index to everything below and it states the conclusion in
one line.

## What was tested, and what happened

| question | answer | where |
|---|---|---|
| does a grab entry pay? | **no** — gross ≈ 0.00 R over 76,297 grabs | `CCP_ENTRY_MODELS.md` |
| does the CCP shape sort them? | **no** | `CCP_ENTRY_MODELS.md` |
| does a 1.5R partial + breakeven help? | **no — significantly worse**, z −4.2 to −8.3 | `studies/ccp_exit_models.out` |
| can filters be found by looking at the losers? | **no** — +0.089 in sample, −0.082 out | `CCP_FILTER_OVERFIT.md` |
| order blocks, EMA trend, ADX, Supertrend? | **all fail**; the trend filters help *random* entries more | `CCP_CONTEXT_FILTERS.md` |
| do the sheet's twelve patterns pay? | **no** — eight of twelve collapse into two | `CCP_PATTERN_EXPLORE.md` |
| **does an FVG sort grabs at 1h?** | **yes, repeatedly, on unseen data** | `FVG_H1_HOLDOUT.md`, `FVG_H1_TEMPORAL.md` |
| is that coherent across timeframes? | **no** | `FVG_TIMEFRAME_COHERENCE.md` |
| is it flat gross, with fees explaining it? | **no** | `FVG_GROSS_EDGE.md` |
| is it the forward horizon? | **no** | `FVG_WHY_1H.md` |
| does it continue above 1h? | **no** | `FVG_HIGHER_TF.md` |
| is it net-positive at 4h/8h? | **not established** | `FVG_NET_HIGHER_TF.md` |

Three pre-registered passes, six pre-registered failures. **Every failure was
an attempt to explain or extend the passes**, which is the shape this folder is
actually for.

## The one thing that survives, and why it is still not a trade

At Min60 an unfilled directional FVG in the grab window separates grabs that
pay from grabs that do not, on four populations including two clean holdouts,
at z +4.12 to +9.19. The sorting is not in doubt. It is not tradeable: standalone
net R is +0.038 to +0.039 with a 0.015 R fee drag and slippage unmodelled,
nothing explains why 1h, and it does not extend above it.

The only clean test left is forward, on data that does not exist yet.

## Re-running any of it

Every study is `PYTHONPATH=. python3 indicators/ccp/studies/<name>.py` and
prints to stdout; the `.out` beside each one is what it printed when the
measurement in `measurements/` was written. **The prereg was committed before
the run every time** — that is the discipline `CCP_FILTER_OVERFIT.md` exists to
justify, and `CCP_SEARCH_INFLATION.md` puts a number on what happens without
it.

Cross-imports are real: `fvg_h1_temporal.py` imports `build()` from
`fvg_h1_holdout.py` so the holdout scores with the exact same rules, and the
FVG rule, stop buffer and target come from `ccp_context_filters.py` rather than
being restated. A copy would be free to drift, and a holdout testing a subtly
different filter tests nothing.

The bench Pine is checked by `deploy/ccp-grab-check.py`, which asserts its grab
engine is still the same code as section 13 of `riptide-indicator-v2.pine` — so
a fix to one was applied to the other. It runs under
`python3 deploy/preflight.py ccp`.
