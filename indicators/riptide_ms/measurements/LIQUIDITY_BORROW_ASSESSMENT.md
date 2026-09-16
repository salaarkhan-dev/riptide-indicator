# What is worth borrowing from "Liquidity & inducements" (© mickes)

Companion to `audit/LIQUIDITY_INDUCEMENTS_AUDIT.md`, which is about whether
that script is *correct*. This one is about whether any of it is worth having
in `riptide-indicator-v2.pine`.

    python3 indicators/ccp/tools/liquidity_grab_rate.py          # the measurement in §2

Same convention: **[PROVEN]** means a trace or a run you can repeat,
**[READ]** means established from the code.

The short version, up front, because most of the answer is "you already have
it":

| thing you named | what it actually is | verdict |
|---|---|---|
| **Grab** (`$$$`) | wick through a pivot, close back on the original side | **already have it, weaker** — Riptide's raid + MSS |
| **Big grab** | *the same function*, called a second time with pivot 10/10 instead of 3/3 | **no new mechanism at all** |
| **Sweep** (`$`) | wick through a pivot and close *through* it — and NOT the bar that broke structure | **borrow the discrimination, not the mark** |
| **BSL / SSL** | unmitigated swing highs/lows, drawn until price trades through | **already have it** (`msLiq*`, from TFlab) — but see §5 |
| **Turtle soup** | a failed breakout, confirmed by a CHoCH against it | **that is Riptide's whole thesis.** Nothing to port |
| Equal highs/lows | — | excluded by you, and broken anyway (audit findings 2–3) |
| **`active =` on inputs** | Pine v6 native input-greying | **borrow this one.** It is the best thing in the file |

---

## 1. [READ] Grab and Big grab are one mechanism, not two

```pine
if _grabs
    var settings = LiquidityGrabsSettings.new(_grabsLookback, ..., _grabsPivotLeftLength, _grabsPivotRightLength, _grabsColor, ...)
    ...
if _bigGrabs
    var settings = LiquidityGrabsSettings.new(_bigGrabsLookback, ..., _bigGrabsPivotLeftLength, _bigGrabsPivotRightLength, _bigGrabsColor, ...)
```

Identical type, identical `LiquidityGrabs()` call, identical
`VisualizeLiquidityGrabs()`. The only differences are the defaults: pivot
**10/10** instead of **3/3**, aqua instead of orange, and its own `Timeframe`.

So "big grab" is not a bigger grab. It is *the same detector pointed at a
more significant level*. Worth saying plainly because it changes what
borrowing it would cost: zero extra logic, five extra inputs.

Riptide already has the general form of this idea and calls it something
else — pools are ranked and the chart distinguishes them. What Riptide does
*not* have is two independent pivot lengths running side by side. That is a
real (small) capability, and it is also five more inputs on a panel you told
me last turn is already too big.

**The grab condition itself**, with audit finding 4's tautology collapsed
out, is a three-bar sequence:

```
pivot low at price P
bar N-1:  low <= P          and   close >= P     (else invalidated forever)
bar N:    close >= P                             -> "$$$"
```

Wick through, close back above, *still* above one bar later. That is a clean,
honest pattern and it is not repainting — `LiquidityGrabs()` is gated on
`barstate.isconfirmed`.

Compare Riptide, `riptide-indicator-v2.pine:1938`:

```pine
bool grabbed = c.isHigh ? high > c.level + buf : low < c.level - buf
```

then an MSS (`close` beyond `structLevel`) within `grabBars`.

Two real differences:

* Riptide requires the wick to clear the level **by an ATR buffer**; mickes
  accepts a one-tick tag. So mickes fires on touches Riptide deliberately
  ignores.
* mickes confirms with **a close back on the original side**; Riptide
  confirms with **a break of the internal structure the raid created**.
  Riptide's is a strictly stronger and strictly later condition.

Neither is "right". But they are not complementary — they are the same idea
at two confidence levels, which is exactly the situation where putting both
on one chart produces two marks that mean nearly the same thing.

---

## 2. [PROVEN] What a second mark would actually cost you

6 symbols × {15m, 30m, 1h}, 10,782 confirmed bars, same 3/3 pivots feeding
both detectors:

```
  TOTAL              10782    655    213    370    201
                             grab  sweep   raid   both

  201/370 riptide raids (54%) have a mickes grab on the same level
  454/655 grabs (69%) are marks riptide does not already make
  median bars the grab leads the raid by: +3.0  (n=201)
```

Read that carefully, and read the caveat in the script's docstring: the
Riptide side is reduced to its *trigger* — no obstacle check, no zone
classification, no session gate, no HTF filter, no FVG. The real indicator
marks **fewer** raids than 370. So 655:370 is a **lower** bound on the ratio.

What it says:

* The grab fires **at least 1.8× as often** as the raid.
* **Two thirds of grabs are new marks** — places Riptide currently says
  nothing.
* Where they agree, the grab is **3 bars earlier**.

That 3-bar lead is the whole appeal, and it is also the whole problem. It is
earlier because it asks for less. The 454 extra marks are not a bonus feature;
they are the price of the lead, and nothing in that table says whether they
are worth anything — a fire rate is not an edge.

**This is the same offer `research/INDUCEMENT_ON_RIPTIDE.md` and
`research/MS_ENTRY_MODELS.md` already tested and rejected**, in a different
costume: a cheaper trigger that fires more often. Seven inducement definitions
and five entry models later, none of them beat the plain control. I am not
going to tell you this one is different because the code is tidier.

If you want it, take it as **context, off by default, no alert** — a faint
mark that says "this level got tagged and reclaimed". Not as a signal, and
not wired into `alert()`.

> **Built, on those terms.** Section 13 of `riptide-indicator-v2.pine`, panel
> groups 18 (Grabs, 3/3, orange) and 19 (Big grabs, 10/10, aqua). Both off by
> default, no `alert()` anywhere in the section, nothing in Riptide reads
> them.
>
> It is written as **one detector with two instances**, which is what §1 above
> established the original to be — `drawGrabBand` / `scanGrabs` /
> `addGrabPivot` take a `GrabSet` holding that instance's settings and its own
> state, so not one line of the logic is written twice. Four defects of the
> original are not reproduced: no Timeframe input at all (finding 1's
> unbounded `while true`), the tautological confirmation written out as the
> one-bar test it actually encodes (finding 4), per-instance drawing budgets
> where the original deletes nothing, and the `$` sweep mark left out as a
> separate decision.
>
> `deploy/pine-static-check.py` earned its keep here: the first draft named
> its drawing function `drawGrab`, which is already Riptide's own raid-X
> function at line 1141. A silent redefinition of the raid marker, caught
> before it reached a chart.

---

## 3. [READ] The one genuinely new idea: sweep-vs-BOS discrimination

This is the bit I would actually steal.

```pine
if sweep.Pivot.LiquidationSwept()
    if not na(previousStructureBreakPivot) and sweep.Pivot.BarIndex == previousStructureBreakPivot.BarIndex
        sweep.Invalidated := true // invalidated by a structure pivot that caused a BOS
```

A level that price traded *through* gets a `$` — **unless that level was the
pivot whose break produced the last BOS**, in which case it is a structure
break and gets no liquidity mark at all.

That is a real distinction and Riptide v2 does not draw it. Section 12
(market structure) and the pool/raid layer run independently, so the same
price can receive a BOS label from one and a raid mark from the other, and
the chart offers no hint that they are the same event. It is the kind of
double-counting that makes a chart look busier than the market is.

It costs one comparison. The implementation cannot be lifted verbatim —
`previousStructureBreakPivot` comes from the unavailable library — but v2
already tracks its own break bar in section 12, so the equivalent is
available locally.

Also worth noting, and cheap: `Clear(liquiditySweeps)` on every CHoCH. The
sweep memory resets each structure cycle, so a level from two cycles ago
cannot suddenly get marked. Riptide expires pools on a bar budget
(`pendingExpiryBars`) rather than on a structure event. Neither is obviously
better; the structural one is more principled.

---

## 4. [READ] Turtle soup — what it is, and why there is nothing to port

The name is from **Linda Raschke and Larry Connors, *Street Smarts* (1995)**.
It fades the Turtle traders' famous 20-day-breakout system — hence "turtle
soup", you make soup out of the Turtles. The original rule, long side:

1. today makes a new **20-day low**;
2. the previous 20-day low was made **at least 4 sessions earlier** (so the
   level is old enough that orders have piled up behind it);
3. buy back **above** the prior low;
4. stop under today's low.

The thesis is one sentence: *a published breakout level collects breakout
orders and protective stops, and a breakout that fails traps every one of
them.* It is the oldest written form of what SMC now calls a liquidity sweep.

In this script the implementation is entirely inside the library:

```pine
PriceAction.VisualizeTurtleSoups(...)   PriceAction.Confirm(...)
PriceAction.GetPivots(...)              PriceAction.SetPivots(...)
```

`mickes/PriceAction/4` is not fetchable from here, so **it cannot be ported,
only re-implemented from the call sites.** What the visible code tells us is
only the shape: pivots of configurable length, optionally from a higher
timeframe, are the targets; `_turtleSoupsConfirmation` requires *a CHoCH in
the opposite direction* afterwards; the whole thing runs on confirmed bars.

Which is the point. Strip the names off:

```
turtle soup   :  old level taken  ->  rejected  ->  CHoCH against the break
riptide       :  pool taken       ->  raid      ->  MSS against the break  ->  FVG
```

**Riptide is a turtle soup with a displacement filter.** That is what
`pool → sweep → MSS → FVG` *is*. There is no feature here to add; there is a
vocabulary you may want on the chart, and there is one parameter of the
original that Riptide does not enforce — **rule 2, the age of the level**.
Riptide pools have `createdBar` and an expiry, but no *minimum* age. Whether
a floor on pool age does anything is measurable and, on the record of the
last seven attempts, probably nothing. I am not going to add it on the
strength of a 1995 rule of thumb.

One implementation detail worth carrying over as a warning rather than a
feature: `Confirm` requires `not na(previousStructureBreakBarIndex)`, and
that variable is assigned at the very bottom of the script — *after* `Confirm`
has run. So the first CHoCH on any chart never confirms a turtle soup. If you
ever re-implement this, the ordering is the bug to avoid.

---

## 5. [READ] BSL / SSL — you have it, and theirs is worse, and theirs is better

Mechanically it is 40 lines: every market-structure pivot becomes a line
extending right with a "Buyside liquidity" / "Sellside liquidity" label;
`ClearMitigatedExternalLiquidity` deletes it the moment `high >= price` (or
`low <= price`); a `Show` input decides how many of the newest are visible.

v2 already has this as `msLiq*`, imported from `TFlab/LiquidityFinderLibrary/1`.
So this is a **swap**, not an addition. Three things decide it:

**Against mickes.** Two defects, one of them mine to point out and not in the
existing audit:

* `ClearMitigatedExternalLiquidity` runs on the **forming bar** (audit
  finding 5). A pool vanishes the instant a wick touches and reappears if the
  bar pulls back.
* `AddExternalLiquidity` hides pools past `Show` by setting `color = na` — it
  never deletes them, and `externalLiquidityPools` is only ever `unshift`ed
  and removed on mitigation. **Every unmitigated pivot in history holds a live
  `line` and a live `label` forever.** With `max_lines_count = 500` Pine
  silently evicts the oldest, so it does not crash, it just eats the budget.
  v2 shares one 500-line budget across nine drawing sections; this is
  precisely the wrong neighbour to have.

**For mickes.** It is **~40 lines you can read**. The TFlab import is a black
box with the same standing problem as `mickes/PriceAction/4` — unauditable,
shares the drawing budget, and I cannot tell you whether it repaints.

**My call:** not now. Replacing a working black box with a readable
re-implementation is a genuine improvement in auditability and *zero*
improvement on the chart, and it is a day of work plus a parity checker. Put
it behind the TFlab library actually misbehaving.

---

## 6. [READ] The thing actually worth taking today

```pine
_grabsLookback = input.int(5, "Lookback", group = "Grabs", active = _grabs)
```

`active =` is a Pine v6 input parameter that **greys an input out when its
master toggle is off**. mickes uses it on essentially every dependent input.

`riptide-indicator-v2.pine` contains the token twice and neither is an input
parameter — `riptide-indicator-v2.pine:517` declares a struct field called
`active`, `:1586` sets it in the constructor. So: **zero of the 149 inputs
use it.**

Last turn you said the panel was too complex, and we fixed the *taxonomy* —
152 inputs down to 149, largest group 51 down to 18. What we did not fix is
that all 149 are always live. Twelve of the thirteen inputs under **Market
structure** do nothing when `msShow` is off, and the panel does not say so.
Same for the nine under **Market structure — liquidity lines**, the sessions
block, the stats block.

This is free: `active =` changes no default, no name, no type, and no
behaviour — `deploy/pine-input-audit.py --diff` will prove that — and it
removes more apparent complexity than any amount of regrouping, because an
input that is greyed out is one you do not have to read.

**That is the borrow I recommend, and it is the only one I would do
unprompted.**

> **Done.** 67 of the 149 inputs are now gated — `msShow` alone carries 13,
> `trackOutcomes` 6, `showFVGs` 5. `deploy/pine-input-audit.py --diff` reports
> *"EVERY INPUT KEEPS ITS NAME, TYPE AND DEFAULT"*, and all five checkers pass.
> Four dependencies were deliberately **not** gated because the input is
> parity-locked (`beLockR`, `earlyMaxBars`, `earlyMaxRiskATR`,
> `poiMaxAgeDays`): those must track `riptide.conf` whether or not the chart
> draws the thing they govern, and greying them would say otherwise. Five more
> were dropped on inspection — `liqCol` looks like it depends on `liqDirCol`
> and does not, `setupExtendBars`/`setupLevelKeep` are shared with the early
> zones and the target lines, `showTrendTag` is documented as working with the
> trend line off, and `sessTz` feeds a master declared later in the file.

---

## Summary — what I would and would not do

| | |
|---|---|
| **do** | `active =` on every dependent input (§6). Free, presentation-only, directly answers last turn's complaint. |
| **consider** | sweep-vs-BOS discrimination (§3) — one comparison, stops the chart double-marking one event. |
| **only if you want it as context** | the grab, off by default, no alert, no `Timeframe` input (§1–2). It is 1.8× the marks for a 3-bar lead, and the extra marks are unmeasured. |
| **no** | big grabs (same detector, 5 more inputs), turtle soup (you already have it), BSL/SSL swap (no chart gain), equal highs/lows (excluded, and broken), anything using `Timeframe` (audit finding 1: `SetBarIndex` can hang). |

Nothing above changes `riptide-indicator.pine`. Any port lands in
`riptide-indicator-v2.pine` behind a toggle, as context, with no performance
claim attached — consistent with `research/INDUCEMENT_ON_RIPTIDE.md` and
`research/MS_ENTRY_MODELS.md`, which is where every previous "this fires more
often" idea went to die.
