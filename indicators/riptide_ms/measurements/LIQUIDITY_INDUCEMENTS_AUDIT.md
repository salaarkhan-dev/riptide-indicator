# Audit — "Liquidity & inducements" (imports `mickes/PriceAction/4`)

Same convention as the Inducement Engine audit: **[PROVEN]** means established
by a trace that you can re-run, **[READ]** means established from the code's
semantics.

    python3 indicators/riptide_ms/tools/liquidity_inducements_trace.py

---

## 0. WHAT THIS AUDIT CANNOT COVER — read this first

```pine
import mickes/PriceAction/4
```

The trend, the pivots that decide it, BOS, CHoCH and the whole turtle-soup
implementation live inside that library:

    PriceAction.Pivot()            PriceAction.BreakOfStructure()
    PriceAction.ChangeOfCharacter()PriceAction.Confirm()
    PriceAction.GetPivots()        PriceAction.VisualizeTurtleSoups()
    PriceAction.SetBarIndices()    PriceAction.SetPivots()
    priceAction.Swing.Trend

Library source is not fetchable from here. So **most of the decision logic in
this indicator is unaudited and I cannot tell you whether it repaints.**
Everything below is about the ~600 lines you pasted, which are the drawing and
bookkeeping layer on top.

That is not a small caveat. `priceAction.Swing.Trend` is the input to almost
every branch in this file — it decides whether a level is labelled `$$$` or
`IDM`, and it gates the turtle-soup confirmation. If the trend repaints, so
does everything that reads it.

---

## 1. [PROVEN] `SetBarIndex` has no termination condition

```pine
method SetBarIndex(PriceAction.Pivot pivot, int barTime) =>
    barIndex = 0
    i = 0
    while true
        if time[i] < barTime
            barIndex := bar_index - (i - 1)
            break
        i += 1
```

`while true` with the only exit inside the `if`. Walk it off the end of the
loaded history and `time[i]` is `na`; in Pine any comparison with `na` yields
`na`, `if na` does not branch, and `i` increments without bound.

The script declares `max_labels_count` and `max_lines_count` but **no
`max_bars_back`**, while indexing history by a value computed at runtime. So
which limit kills it is not the script's choice:

```
pivot 5 bars back, plenty of history   ('ok', 394)
pivot on the OLDEST loaded bar         ('RUNTIME ERROR: beyond max_bars_back', 301)
pivot older than ALL loaded history    ('RUNTIME ERROR: beyond max_bars_back', 301)
...same, with max_bars_back raised     ('INFINITE LOOP: na never satisfies the break', 1001)
```

Last two rows: same input, different failure, decided entirely by a limit the
script never sets.

**When you actually hit it.** The `Timeframe` inputs. A pivot fetched from a
higher timeframe carries that timeframe's open time, and `SetBarIndex` then
walks back one *chart* bar at a time until it reaches it — 48 iterations for a
1D pivot on a 30m chart, 1,440 for a 1D pivot on a 1m chart. Past ~300 that is
a history-buffer error; past the end of the loaded window it is a hang.

*Fix:* declare `max_bars_back`, bound the loop (`while i < 5000`), and break on
`na(time[i])` as well as on the comparison.

---

## 2. [PROVEN] Equal highs/lows silently stop working if you change the pivot length

```pine
if latestPivot.BarIndex == bar_index - 1          // EqualPivotsInducementAndLiquidity
```

`GetEqualPivotsPivots` stamps the pivot with `Time = time[PivotRightLength]`,
and `SetBarIndex` turns that back into `bar_index - PivotRightLength`. The gate
compares it against `bar_index - 1`:

```
 right len    Time = time[R]    BarIndex  gate wants   fires?
         1           time[1]         398         398     True
         2           time[2]         397         398    False
         3           time[3]         396         398    False
         5           time[5]         394         398    False
        10          time[10]         389         398    False
```

The default right length is 1, so it works out of the box. **Set the
Equal highs/lows "Pivot" right field to anything other than 1 and the feature
produces nothing at all** — no error, no message, just an empty chart section.

This is a transcription slip rather than a design choice, and the file proves
it itself: the equivalent gate in `CreateRetracementInducement` is written
correctly as

```pine
if latestPivot.BarIndex == bar_index - settings.PivotRightLength
```

*Fix:* use `settings.PivotRightLength` in the equal-pivot gate too.

---

## 3. [PROVEN] Two of the six `Timeframe` inputs only ever disable their feature

Both gates in finding 2 compare a *time-derived* bar index against a *chart*
offset. On the chart timeframe those coincide. On a higher timeframe they do
not:

```
1D pivot on a 30m chart: BarIndex=351, gate wants 398 -> False
```

So setting a Timeframe for **Equal highs/lows** or for **Retracement
inducements** switches the feature off rather than lifting it to the higher
timeframe. The control looks like it works and does the opposite of what it
says.

Grabs, big grabs, sweeps and turtle soups do not use that gate — they poll the
stored level on every bar — so their Timeframe inputs do function, subject to
finding 1.

---

## 4. [READ] The grab "confirmation" is a tautology

```pine
if low[1] <= pivot.Price and close >= pivot.Price
    if 1 > 0
        confirmed = true
        for i = 1 - 1 to 0
            if close[i] < pivot.Price
                confirmed := false
                break
        confirmed
    else
        true
```

* `1 > 0` — constant true, `else true` unreachable.
* `for i = 1 - 1 to 0` — `for i = 0 to 0`, one iteration, `i = 0`.
* that iteration tests `close[0] < pivot.Price`, which the enclosing `if`
  already excluded (`close >= pivot.Price`).

So `confirmed` is true on every path that reaches it. The whole inner block
computes nothing.

The shape is unmistakable: this was once parameterised on a confirmation-bar
count and the parameter was hard-coded to `1`, which collapses it. The result
is not a *wrong* number — the outer condition still encodes the intended
one-bar test — but **the knob is gone**, and anyone reading the code will
believe there is a multi-bar confirmation when there is not.

---

## 5. [READ] Half the script respects bar close and half does not

Explicitly gated on a closed bar:

```pine
LiquidityGrabs(...)   => if barstate.isconfirmed
LiquiditySweeps(...)  => if barstate.isconfirmed
TurtleSoup(...)       => if barstate.isconfirmed
```

Not gated, running on the forming bar:

```pine
EqualPivotsInducementTrigger   high >= inducement.StopLosses / low <= ...
StopRetracementInducement      high >= inducementHigh.Pivot.Price / low <= ...
ClearMitigatedExternalLiquidity  low <= price / high >= price
EqualPivotsInducementAndLiquidity  uses _atr = ta.atr(14) on the live bar
```

**This is the repaint you asked about, and it is the honest kind to name:**
`$$$` sweep labels, the removal of buyside/sellside pools, and the "IDM taken"
mark all appear the moment the wick touches, and un-appear if the bar pulls
back before close. Grabs and sweeps do not behave that way. So two marks on the
same chart follow two different rules and nothing on the chart says which is
which.

`_atr` compounds it: `ta.atr(14)` includes the forming bar, and it sets both
the equal-pivot tolerance band

```pine
equalPivotMaximumPrice = equalPivot.Price + (_atr * settings.AverageTrueRangeFactor)
```

and the inducement stop level (`equalPivot.Price ± _atr * 0.1`). So whether two
pivots count as "equal" can flip during a bar, and the level you would place a
stop behind moves while the bar is open.

*Fix:* `ta.atr(14)[1]`, and gate the three unconfirmed blocks on
`barstate.isconfirmed` like the other three.

---

## 6. [READ] `request.security` — the tooltip already admits this one

Six calls, none of which pass `lookahead` and none of which offset by `[1]`:

```pine
[grabHigh, grabLow] = request.security(syminfo.tickerid, _grabsTimeframe, GetLiquidityGrabs(settings))
```

Default is `lookahead_off`, so **on historical bars there is no future leak** —
this is not the lookahead bug. What it does mean is that on the currently
forming higher-timeframe bar the returned pivot updates tick by tick, so an
HTF pivot can be reported, then withdrawn when that HTF bar closes differently.

The author knows. From the turtle-soup tooltip, verbatim:

> *"this is due to how higher timeframe values (pivots in this case) are fethed
> in Pine Script and that the trend can change during that fetching"*

That is a disclosed limitation, not a hidden one, and `_turtleSoupsConfirmation`
exists to suppress the worst of it. Worth knowing that the suppression is a
filter on the output, not a fix to the fetch.

Note also that the first CHoCH on any chart never confirms a turtle soup:
`Confirm` requires `not na(previousStructureBreakBarIndex)`, and that variable
is only assigned at the very bottom of the script, after `Confirm` has already
run.

---

## 7. [READ] What is NOT wrong — so it does not get flagged twice

* **Index-removal order.** `StopRetracementInducement` collects indices with
  `unshift`, which yields descending order, then removes in that order. That is
  the correct way to do it and a very common thing to get wrong.
* **The equal-pivot sweep scan.** `barPrice = latestPivot.Price + step*(j-1)`
  against `high[j]`, with the pivot pinned at `bar_index - 1`, lines the
  interpolated line up with the right bar. The arithmetic is right.
* **`EqualPivotSettings` field order** is `..., PivotRightLength,
  PivotLeftLength, ...` — reversed relative to the other three settings types —
  but the constructor call passes them in that same reversed order, so it is
  correct. A trap for the next edit, not a present bug.
* **Pivot lag** of `PivotRightLength` bars is honest latency. Nothing is
  redrawn later because of it.

It is also worth saying plainly: outside findings 1–3, this is noticeably
better-built code than the Inducement Engine. Typed, decomposed, no global
mutation-through-function tricks, and the confirmed-bar gating is present in
the places the author thought about.

---

## 8. [READ] There is nothing here to measure

This is the part that matters for what you actually asked for.

The indicator has **no entry, no stop, no target, no direction, and no
`alert()` or `alertcondition()` anywhere in the file.** It draws lines and
labels — `$$$`, `$`, `IDM`, buyside/sellside pools — and that is the whole
output.

So a win rate, an R, a drawdown, a streak count: none of them can be added to
this file, because none of them are defined. "How is it performing" has no
answer until somebody decides what a trade *is*. Concretely, at minimum:

1. **Which mark is the trigger** — a grab? a sweep? a turtle soup? an IDM being
   taken? They fire at different rates and mean different things.
2. **Direction** — with the trend from the library, or countertrend into the
   grab?
3. **Entry price** — the close of the marking bar, or a limit back at the level?
4. **Stop** — the wick that did the grabbing, the pivot behind it, or an ATR
   multiple? This is the one that decided Stage A vs Stage B for LIT, and it is
   the difference between a 0.4%-of-price stop that noise takes out and a real
   one.
5. **Exit** — a fixed R, the next opposing pool, or a trail?

Pick those five and a ledger is a day's work, and it can reuse the one already
written in `inducement-engine.pine` — the bar-by-bar resolver with the entry
bar resolving nothing, the stop tested before the target, R per trade with a
standard error, max drawdown, longest loss run, and total-R-without-the-best-
trade. That machinery is strategy-agnostic; only the five decisions above are
missing.

**What I am not going to do is pick them for you and then report a win rate.**
Choosing an entry and a stop until the statistics look good is the exact
procedure the 162-combination grid showed decaying ~0.95 R/bet out of sample.
If the trade definition comes from the way you already read these charts, the
number means something. If it comes from me tuning against the backtest, it
does not.

---

## Summary

| # | finding | severity | affects |
|---|---|---|---|
| 1 | `SetBarIndex` can hang or error; no `max_bars_back` | **high** | any Timeframe input |
| 2 | equal-pivot gate hard-codes `- 1` | **high** | Equal highs/lows, silently |
| 3 | two Timeframe inputs only disable their feature | **high** | Equal h/l, Retracement IDM |
| 4 | grab confirmation is a tautology | medium | readability, not numbers |
| 5 | three blocks run on the forming bar; live ATR | medium | intrabar flicker, stop level |
| 6 | HTF fetch updates on the forming HTF bar | low | disclosed in the tooltip |
| 8 | no entry/stop/target, no alerts | — | nothing can be scored |

Findings 1–3 are worth fixing before you rely on any Timeframe setting.
Findings 5 is worth fixing if you read levels intrabar. Finding 8 is the one
standing between you and the numbers you asked for, and it needs a decision
from you, not a patch from me.
