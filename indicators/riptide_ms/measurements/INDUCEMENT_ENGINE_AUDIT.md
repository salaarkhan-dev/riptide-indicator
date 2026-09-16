# Audit — "Inducement Engine Liquidity Targets"

Findings ordered by how much they change the numbers you would read off the
chart. Each one says how it was established: **[PROVEN]** means measured on
real data, **[READ]** means established from the code's semantics.

---

## 1. [PROVEN] The pivot function never checks the current bar

```pine
f_pivotHigh(series float src, simple int len) =>
    float candidate = src[len]
    for i = 1 to len * 2
        if i != len and src[i] >= candidate
            isValid := false
```

The loop starts at `i = 1`. With `len = 5` it tests `src[1..4]` on the right
and `src[6..10]` on the left — **four bars right, five bars left**, and
`src[0]`, the bar the function is running on, is never tested.

So a "pivot high" can be confirmed on a bar whose own high is above it.

Measured on BTC 30m, 15,973 bars, `swing_len = 5`:

```
pivots the code accepts                    1103
pivots under a symmetric 5-left/5-right     1010
accepted by this code ONLY                   93   = 8.4% of its pivots
  ...of which the CURRENT bar already
     equals or exceeds the "pivot"           93   = all of them
```

**Every one** of the 93 extra pivots is a bar that had already been taken out.
Those feed `ind_list`, become IDMs, and produce signals.

*Fix:* start the loop at `i = 0`.

---

## 2. [READ] ATR repaints the SL, the TPs and the signal itself

```pine
float atr_val = ta.atr(atr_len)                       // CURRENT, forming bar
float raw_sl_short = ind_bull_sl + (atr_val * atr_sl_mult)
bool  f_vol = use_vol_filter ? atr_val > atr_sma : true
```

`ta.atr(atr_len)` includes the bar that is still forming. Its high and low move
on every tick, so:

* the **SL line and all three TP lines move while the bar is open**, and only
  settle at the close;
* `f_vol` can flip true→false→true intrabar, so with the volatility filter on
  the **whole signal appears and disappears** during the bar.

This is the repaint you were asking about, and it is the one that actually
affects the levels you would trade.

*Fix:* `ta.atr(atr_len)[1]`. Everything else in the signal path already uses
`[1]`, so this is the single inconsistency.

---

## 3. [READ] The alert fires one full bar after the entry it reports

```pine
float entry_price = close[1]
...
if sig.trigger and barstate.isconfirmed
    alert(sig.gen_payload(), alert.freq_once_per_bar_close)
```

Detection uses `low[1] < ip.price` — the previous bar. The entry is recorded as
`close[1]`. But the alert is gated on `barstate.isconfirmed`, so it is sent at
the close of the **current** bar.

The webhook therefore says `"entry": close[1]` while the earliest you can act
is `close[0]` — a full bar later. On 30m that is thirty minutes of drift
between the reported fill and the achievable one, and it is unmeasured because
nothing scores the result.

*Fix:* either send at the open of the detection bar, or report the entry you
can actually get. The enhanced build reports `close[0]` and says so.

---

## 4. [READ] The structure range only ever widens

```pine
if ph > ms.last_high
    ms.last_high := ph
if pl < ms.last_low or ms.last_low == 0.0
    ms.last_low := pl
```

`last_high` only rises, `last_low` only falls. They are reset **one side at a
time**, and only when a signal fires.

The IDM registration test is `ph < ms.last_high and ph > ms.last_low`. As the
range widens toward the full history's extremes, that test stops
discriminating: eventually almost every pivot qualifies as an inducement.

This is why `Pending IDM` climbs and why the array keeps hitting `ind_max`.
The cap hides the symptom rather than fixing it.

---

## 5. [READ] Initial bias is hard-coded bullish

```pine
if ms.trend == 0 and ms.last_high != 0.0 and ms.last_low != 0.0
    ms.trend := 1
```

The first trend is always bullish regardless of what price did. Every IDM
registered before the first real signal inherits that assumption.

---

## 6. [READ] Same-bar collisions have no defined resolution

The sweep loop runs over the whole array and does not stop at the first break:

* several IDMs can break on one bar; `ind_broken_idx` and `ind_bull_sl` keep
  being overwritten, so **the last one in array order wins** — which is the
  oldest surviving IDM, not the nearest;
* a bull IDM and a bear IDM can both break on the same bar, making
  `short_signal` and `long_signal` both true. Both drawing blocks then run and
  the second overwrites the first, while `sig` ends up holding the long.

---

## 7. [READ] What is NOT wrong — checked so it is not flagged twice

```pine
request.security(syminfo.tickerid, htf_res, ta.ema(close, htf_ema_len)[1],
     lookahead=barmerge.lookahead_on)
```

`lookahead_on` looks alarming, and with a `[1]` offset it is the **correct**
non-repainting idiom: it returns the previous completed HTF bar. This one is
fine as written.

The FVG and rejection filters also read `[1]`/`[3]` only — closed bars, no
repaint. The sweep test reads `low[1]`/`high[1]` — closed. The pivot lag of
`swing_len` bars is honest latency, not repainting: nothing is redrawn later.

---

## 8. [READ] There are no performance statistics at all

The dashboard reports current state — bias, last IDM, entry/TP/SL, bars since,
pending count. Nothing tracks what happened to any signal.

So there is no win rate, no R, no drawdown, and no way to know whether the
levels drawn were ever reached. That is the gap the enhanced build fills.

---

## What the enhanced build changes

`inducement-engine.pine` in the repo root:

**Correctness**
* pivot loop starts at `i = 0` — with a `Legacy pivot` switch to reproduce the
  old behaviour for comparison
* `ta.atr()[1]` everywhere in the signal path — no intrabar movement
* signal evaluation and stats update only on confirmed bars
* the reported entry is the price you can actually get, and the payload says so

**Statistics — the point of the exercise**

A virtual-trade ledger, resolved bar by bar on closed bars only, with the entry
bar resolving nothing and the stop tested before the target:

    trades · win rate · TOTAL R · R per trade ± SE · t
    profit factor · expectancy · avg win / avg loss
    max drawdown in R, and the longest run below the prior equity peak
    longest win run · longest LOSS run
    best trade as a share of gross profit  ← the concentration check
    TOTAL R without the best trade
    TP1 / TP2 / TP3 reach rates separately
    open trades still running

**Why those specific columns.** R per trade without a standard error is the
number that misleads; a total that collapses when one trade is removed was one
trade. Both are shown next to the headline so it cannot be read the flattering
way.
