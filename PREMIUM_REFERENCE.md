# ICT SM Trades PREMIUM — captured settings

**Why this file exists.** The premium subscription expires in a few days. Once
it lapses the inputs panel, its tooltips and its defaults are gone. Every
number below is transcribed from the live panel while access lasted, with the
tooltips quoted verbatim, so that a future question about the reference
indicator can be answered from here instead of from memory.

Riptide's engine was originally written against this indicator —
`riptide/config.py`'s `Cfg` docstring still says *"Defaults mirror the Pine
inputs"* — so the right-hand column of each table is the Riptide parameter it
corresponds to, its current value, and whether that value has been measured.

Captured 13 Sep 2026, chart BTCUSDT.P.

---

## Chart-level

| Setting | Premium | Riptide equivalent |
|---|---|---|
| Panel header warning | *"IF YOU GET ERROR 'THE SCRIPT TAKES TOO LONG TO EXECUTE' TRY HIGHER TIMEFRAME OR CHECK LESS TYPES"* | n/a — Riptide is a Python scanner, not a Pine script, so it has no execution budget |

---

## TYPE — which pool sources are scanned

| Source | Premium | Riptide equivalent | Riptide value |
|---|---|---|---|
| Pivot Liquidity Grab + MSS | ON | `use_pivot` | `True` |
| LIVE Pivot Liquidity | ON | — (a drawing layer, not a signal) | — |
| ⤷ Extended Lines | OFF | — | — |
| LIVE Pivot Liquidity Grab | ON | — (a drawing layer) | — |
| Daily H/L Liquidity Grab + MSS | ON | `use_daily` | `True` |
| Weekly H/L Liquidity Grab + MSS | ON | `use_weekly` | **`False`** |
| Session H/L Liquidity Grab + MSS | ON | **no counterpart** | — |

**Two real divergences here.**

`use_weekly` is OFF in Riptide and ON in the premium. That is a measured
decision, not an oversight: 295 weekly raids produced **zero** setups in 41.6
days (MEASUREMENTS.md, "Pool source"). It is a switch, not a deletion.

**Session H/L as a pool source has no Riptide counterpart at all.** Riptide
takes liquidity from pivots and from daily highs/lows; it has never taken it
from session highs/lows. This is the single largest structural difference in
the whole panel. Note that a *session filter* is on the research ban list —
but a session H/L **pool source** is not the same thing as a session filter. It
is a different place to find liquidity, not a rule about when to trade.

---

## CORE

| Setting | Premium | Tooltip | Riptide | Riptide value |
|---|---|---|---|---|
| Look Back Maximum X Bars for Liquidity Grab and Market Structure Shift | **12** | *"How many candles at maximum should be between liquidity grab candle and MSS candle. In other words: How fast should reversal move be from liquidity grab to opposite side of local structure."* | `max_bars_after_grab` | **50** |
| ATR Length (number of bars back) | **28** | — | `atr_len` | **28** ✓ match |
| Market Structure Shift by Close or High/Low | **close** | — | `mss_close` | **`True`** ✓ match |

**The one number that is wildly different is the grab→MSS window: 12 against
Riptide's 50.** The tooltip says exactly what the parameter means and it is a
speed requirement — *how fast the reversal must be*. Riptide allows the shift to
arrive up to fifty bars after the raid; the reference allows twelve. That is not
a cosmetic gap, it is a four-fold difference in how patient the pattern is
allowed to be, and it has never been swept. See "What to test first" below.

---

## TYPE: PIVOT

| Setting | Premium | Tooltip | Riptide | Riptide value |
|---|---|---|---|---|
| Pivot H/Ls Look Back/Forward Period | **1** | *"For PIVOT HIGH there has to be X (by default 1) candles lower to the left and X (by default 1) candles lower to the right and vice versa for PIVOT LOW."* | `pivot_left` / `pivot_right` | **1 / 2** |
| Pivot H/Ls Maximum Range by X ATR | **0.2** | *"Minimum of 2 pivot H/Ls in close range to form a liquidity (tested and untested pivot H/Ls together)."* | `max_cluster_span_atr` | **0.80** |
| Pivot H/Ls Maximum Tested Range by X ATR | **0.1** | *"Maximal accepted deviation for tested H/Ls."* | `tol_atr` | **0.25** |

The tooltip on "Maximum Range" also documents the **minimum of 2 pivots to form
a liquidity pool**, which Riptide matches exactly (`min_pivots = 2`).

**Riptide's cluster is four times looser and its tolerance 2.5x looser.** The
premium wants pivots within 0.2 ATR of each other to count as one pool and
accepts 0.1 ATR of deviation on a tested level; Riptide uses 0.80 and 0.25.

Both parameters **have** been swept, by `pivot_tune.py`, and the pool was left
exactly as shipped — but the premium's values sit **below the bottom of that
grid**: it tried `tol_atr` at 0.15/0.25/0.35/0.50 against the reference's 0.1,
and `max_cluster_span_atr` at 0.50/0.80/1.20 against the reference's 0.2. So
the tighter end is untested rather than rejected.

That sweep is also the one whose headline finding died properly: three-touch
pools looked like +0.206 R per bet held out, then failed a circular-shift null
(1.69 SE real against a 2.56 SE p95) and failed to reproduce on three fresh
timeframes. `min_pivots` stays at 2. Read the premium's tighter geometry as a
question the grid did not reach, not as a hint the grid missed.

Riptide's pivot is also **asymmetric** (1 left, 2 right) where the premium is
symmetric (1/1). Requiring two bars to the right makes a pivot confirm one bar
later, which is a freshness cost in exchange for fewer false pivots.

---

## TYPE: DAILY H/L, WEEKLY H/L, SESSION H/L

| Setting | Premium | Tooltip | Riptide |
|---|---|---|---|
| Look Back X Bars for H/L of Local Structure in Opposite Side | **12** | *"Found H/L of local structure in opposite side is used for market structure shift purposes when broken."* | no separate parameter — Riptide uses `run_min`/`run_max` tracked from the sweep, i.e. the whole run rather than a fixed 12-bar window |

---

## FILTER (applies to alerts)

| Setting | Premium | Tooltip | Riptide |
|---|---|---|---|
| Longs | ON | — | both directions always sent |
| Shorts | ON | — | both directions always sent |
| By Daily Bias | **OFF** | — | — |
| By Trend | **OFF** | — | `grade_of` uses SuperTrend + DI, but as a **grade**, never a hard filter |
| By Session | **OFF** | *"For example if filtering by session is applied then we can choose if trade should be found either if liquidity grab happens in particular session time or MSS happens in particular session time."* | none — and session filters are on the research ban list |
| Event for Filtering Rules | **MSS** (options: `Liquidity Grab`, `MSS`) | — | n/a |

**All three optional filters ship OFF in the reference indicator.** Worth
recording plainly: the author of the indicator Riptide was modelled on does not
turn on daily bias, trend or session filtering by default. That is independent
support for what twenty-one failed filter tests already concluded here.

---

## SHOW/HIDE

| Setting | Premium | Riptide |
|---|---|---|
| Daily Bias | **none** | — |
| Trend | **none** | — |
| Fair Value Gaps *(must be CHECKED for FVG alerts)* | ON | the entry gap — core |
| Middle Line in Fair Value Gaps | ON | `entry_mode = "mid"` exists; **measured and rejected**, −0.012 ±0.007 (−1.8 SE) in `entry_deep.py`. This is the "consequent encroachment" line. |
| Order Block *(must be CHECKED for OB alerts)* | ON | `confluence_of` counts order blocks; **measured and rejected** as an entry, −0.027 to −0.048 |
| Breaker Block *(must be CHECKED for BB alerts)* | ON | `confluence_of` counts breakers |

Note the dependency the tooltips spell out: a drawing being hidden **disables
its alerts**. The show/hide toggles are not cosmetic in this indicator.

---

## TREND

| Setting | Premium | Riptide | Riptide value |
|---|---|---|---|
| Timeframe | **1D** | `TREND_INTERVAL` | **`Hour8`** |
| Supertrend Factor | **5** | `TREND_FACTOR` | **5.0** ✓ match |
| Supertrend ATR Length | **14** | `TREND_LEN` | **14** ✓ match |

**The SuperTrend itself is an exact match — factor 5, length 14. Only the
timeframe differs, and that difference was introduced here by accident.**

`TREND_INTERVAL` moved Day1 → Hour8 on 9 Sep and silently took the point of
interest with it, because `trend.poi_at` reads `TREND_INTERVAL` rather than a
key of its own. `poi_tf.py` then measured Day1 against Hour8 **for the POI
label** and found a dead heat (|z| 0.1 across three framings).

That does **not** close the question for the SuperTrend. `poi_tf.py` held every
grade at `poi=True` so the A/B floor stayed constant and only the POI label
varied — the trend gate's own timeframe was never the thing being tested. So
"should the SuperTrend read Day1 like the reference, or Hour8 like today?" is
still open, and it is a one-line config change to test.

---

## ORDER BLOCK

| Setting | Premium | Riptide |
|---|---|---|
| Order Block Move by X ATR | **2** | no direct counterpart; `confluence_of` detects order blocks without a displacement-size requirement |

The reference requires a **2 ATR move** off the order block for it to count.
Riptide's order-block detection has no such requirement. When `entry_deep.py`
measured "order block extreme" and "order block mid" as entries (−0.027 and
−0.048), it used the unqualified definition — so the 2-ATR-displacement variant
was **not** what was rejected.

---

## SESSION

| Setting | Premium |
|---|---|
| Session Timezone | **GMT+0** |
| Session Time 1 | **08:00 – 17:00**, Active |
| Session Time 2 | **13:00 – 22:00**, Active |
| Session Time 3 | **00:00 – 09:00**, Active |

London, New York and Asia respectively, in UTC. Recorded for completeness —
these only matter if Session H/L is used as a pool source, since the session
*filter* is off.

---

## What is NOT yet captured — grab these before access lapses

The panel was captured from the **Inputs** tab only, and not all of it. Missing:

1. **Tooltips not yet opened**: ATR Length; Market Structure Shift by Close or
   High/Low (and its full option list); By Daily Bias; By Trend; the Daily Bias
   and Trend dropdowns under SHOW/HIDE (and their option lists); Timeframe;
   Supertrend Factor; Supertrend ATR Length; Order Block Move by X ATR; Session
   Timezone; the Session Time rows; Fair Value Gaps; Middle Line in Fair Value
   Gaps; Order Block; Breaker Block.
2. **Anything below SESSION** in the Inputs tab — the panel was still scrolling.
3. **Anything in SHOW/HIDE below "Breaker Block"**.
4. **The entire Style tab** and **the entire Visibility tab**.
5. **The alert dialog** — the alert message templates and the available alert
   conditions (FVG / OB / BB alerts are referenced but their setup is unseen).
6. **The `Defaults` button state** — several values above may already be
   non-default; pressing Defaults and re-screenshotting the panel would show
   which numbers are the author's shipped values and which are a prior
   adjustment. Do this **last**, and screenshot the current state first.

---

## What to test first, once this is only a document

Ranked by how large the divergence is and how cheap the test is. All three are
config sweeps on the existing deep pipeline, not new indicators, and none is on
the ban list.

1. **`max_bars_after_grab`: 50 → 12.** The largest single divergence in the
   panel, and the tooltip makes clear it is deliberate — the reference is
   enforcing that the reversal be *fast*. A four-fold difference in patience,
   and the one parameter here that `pivot_tune.py` did **not** sweep.
2. **Cluster geometry: `max_cluster_span_atr` 0.80 → 0.2, `tol_atr` 0.25 →
   0.1.** These two move together; sweep them as a pair, not separately. Both
   were swept before but only down to 0.50 and 0.15 — extending the existing
   grid downward is a smaller job than a new study, and `pivot_tune.py`'s
   pre-registration and circular-shift null can be reused as they stand.
3. **`TREND_INTERVAL` Hour8 → Day1 for the SuperTrend gate**, which `poi_tf.py`
   did not test. One config line.

Two further items that are structural rather than a sweep:

4. **Session H/L as a fourth pool source.** No counterpart in Riptide at all.
   This is a new place to look for liquidity, not a filter on when to trade.
5. **The 2-ATR displacement requirement on order blocks.** The order-block
   entries that `entry_deep.py` rejected used the unqualified definition, so
   the reference's stricter version is untested.

Finally, the honest caveat on the whole list: these are the reference
indicator's defaults, not evidence. Riptide's values were mostly arrived at by
measurement and several of them (`use_weekly`, `max_risk_atr`, `be_arm_r`,
`fvg_scan_from`, `entry_mode`) beat the reference's choice when tested. A
divergence is a question, not a correction.
