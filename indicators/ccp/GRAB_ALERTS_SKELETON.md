# Skeleton — grab alerts on Telegram, and the combined-candle indicator

A design, not an implementation. Nothing here is built yet.

Two separate pieces that arrived in one request, and they should stay separate
because one is a bot module and the other is a chart experiment:

1. **`riptide/grabwatch.py`** — a Telegram digest when a grab happens.
2. **`riptide-ccp.pine`** — a standalone indicator for merging adjacent
   candles and naming the shape they make.

---

## 0. The thing to know before anything else

**Telegram alerts do not come from the Pine indicator.** The chart's `alert()`
fires into TradingView. The Telegram messages come from the bot, which runs
its own engine over its own candle fetch and reads `riptide.conf`. Nothing on
the chart can reach Telegram.

So "grab alerts on Telegram" means **a new Python module**, not a new
`alert()` call in `riptide-indicator-v2.pine`. Section 13 stays exactly as it
is: drawing only, no alerts, as its tooltips promise.

That also means grab detection would exist twice — once in Pine, once in
Python — and the two must agree. `deploy/check-parity.py` is what enforces
that today for the 24 shared settings, and any grab knob that ships to the bot
joins it.

---

## 1. The template already exists, and it is `riptide/watch.py`

The trendline watch solved this exact problem and its own docstring reads like
a spec for this one. Five rules, all of them earned:

* **Its own everything.** Own loop, own timeframe, own dedupe table, own
  message, own on/off switch. It shares the candle fetcher and the Telegram
  sender and nothing else. *"A failure in a watch list must never be able to
  cost a trade alert."*
* **One digest per bar close, not one message per event.** Bar closes are
  synchronised, so events do not trickle in — they arrive together.
* **`collapse()`** — one line per symbol per direction, keeping the slowest
  timeframe, because a chart that fired on 15m and 30m is one event to a
  reader.
* **A volume-control gate, labelled as one.** For trendlines that is the
  minimum slope. Grabs need the equivalent; §2 says what it should be.
* **No outcome tracking, on purpose.** §3.

`grabwatch.py` should be `watch.py` with the detector swapped. Same shape,
same table pattern, same digest, same `/grabs on|off` command.

---

## 2. Volume — measured first, because it decides the design

Over the real 23-symbol universe:

```
   tf  pivot   days   grabs  per day  busiest close  closes with >=1
  15m    3/3   20.8    2721    130.7             20              56%
  30m    3/3   41.6    2736     65.7             53              58%
   1h    3/3   83.3    2757     33.1             27              56%
  15m  10/10   20.8     917     44.0             14              26%
   1h  10/10   83.3     925     11.1             12              26%
```

Three things fall out, and one of them contradicts the instinct in the
request.

**The digest is mandatory.** At 15m narrow, 56% of closes have at least one
grab somewhere and the worst single close had 20 at once. One message per grab
is 131 messages a day and past Telegram's per-chat rate limit. This is the
same finding that produced the trendline digest.

**A slower interval is NOT the volume control.** "Maybe every 30 min, or if
that's too much, 1h" treats the interval as a throttle, and it barely is:
grabs scale with bars, so 15m → 1h cuts per-day volume 131 → 33 but leaves
**56% of closes carrying something either way**. Worse, 30m had the *busiest*
single close of all — 53 symbols — because a 30m close is also a 15m close and
everything lands at once.

**The pivot width is the volume control.** 15m at 10/10 instead of 3/3 is
44/day against 131, and the share of closes carrying anything drops 56% → 26%.
That is a real filter: it is selecting bigger swings, not just looking less
often.

> **Recommended default: 1h, big grabs only (10/10).** 11 alerts a day, 26% of
> closes, worst case 12 symbols in one message. That is roughly one digest
> every four hours with a line or two in it — readable, and it survives a busy
> session. `15m, 10/10` is the faster option at 44/day if that proves too
> quiet.

Narrow grabs (3/3) should not alert at all at first. They can be switched on
later if the wide ones prove worth reading.

---

## 3. The honesty constraint, which the repo already set for this exact case

`watch.py` says it plainly:

> *The identical breakout was scored through the same harness as everything
> else here: net R per signal is NEGATIVE on both halves of the window and
> statistically indistinguishable from a random entry of the same shape. So
> there is no entry, no stop, no target, no grade, and — this is deliberate
> and not an oversight — NO OUTCOME TRACKING.*

**The grab is in the same position, and in one respect a weaker one.**

* `research/POOL_PIVOT_LENGTH.md` — six pivot widths, preregistered, came back
  **UNDERPOWERED**. The direction was consistent but the largest difference was
  +0.7 SE and the run could not have resolved an effect smaller than +0.81 R
  per bet.
* `indicators/ccp/tools/liquidity_grab_rate.py` — the grab fires at least **1.8× as often** as
  Riptide's own raid on the same pivots, and **two thirds of its marks are
  places Riptide says nothing**.

So nothing is known about whether a grab is worth acting on. It ships on
exactly the trendline's terms or it does not ship:

| | |
|---|---|
| entry / stop / target | **none** |
| grade (A/B/C/D) | **none** |
| outcome tracking, `/stats` rows | **none** — arming these would put invented entries into the table that judges real strategies |
| what the message says it is | a heads-up: *which chart to open*, nothing more |
| own on/off switch | yes, default **off** |

If it later earns a claim, it earns it through a prereg and a study like
everything else.

---

## 4. "Properly from both ends" — what a digest line carries

From the screenshot: the two circled groups are the **swing end** (the candles
that built the level) and the **grab end** (the candles that took it). Both
belong in the message, because the shape at each end is the thing being
watched.

Proposed line, one per symbol per direction:

```
BTC  1h  sell-side @ 76,914   swing 3 Sep 14:00  ·  held 22 bars
     end shapes: inverted hammer  →  shooting star        [chart]
```

* **level and side** — what was taken, buy-side or sell-side
* **age** — how long the level stood before it was run; a level that has been
  there 40 bars is a different object from one four bars old
* **both end shapes** — from §5's classifier, once that exists. Until it does,
  the line ships without them rather than with a guess.
* **chart link** at the right symbol and timeframe, the way the trendline
  digest already does it

Open: whether the two-instance split (narrow/wide) appears in the message or
only wide ones alert at all. Recommendation is the latter, per §2.

---

## 5. `riptide-ccp.pine` — merging candles and naming the shape

A **separate file**, as asked, so nothing here can disturb
`riptide-indicator-v2.pine` or the production file. It is a test bench.

### The merge rule

Merging *n* adjacent candles into one synthetic candle is unambiguous:

```
open  = open  of the FIRST
close = close of the LAST
high  = max of the highs
low   = min of the lows
```

That is the whole operation. Everything else is classification.

### Classification comes from the CCP sheet, and its rule is not the obvious one

`MMC_CP_Confirmations.pdf` (source: `indicators/ccp/sheet.py`) already settles
the taxonomy, and its footnote is the part that matters here:

> *A hammer and a hanging man are the identical candle in two colours, and
> both are bullish. So are the inverted hammer and the shooting star, and both
> are bearish.*

**Shape decides; colour only names.** A long LOWER wick with a small body is
bullish whichever colour the body is. A long UPPER wick is bearish. There are
four names and two shapes.

The sheet also records a mistake worth not repeating: an earlier version drew
the bearish column by *flipping* the bullish pins, and flipping a hammer
produces an inverted hammer — the flip is precisely the operation that turns
one shape into the other. The bearish pins are the same four **shifted up**,
not flipped.

So the classifier is:

```
bodyFrac  = |close - open| / (high - low)
upWick    = (high - max(open, close)) / (high - low)
dnWick    = (min(open, close) - low)  / (high - low)

pin       = bodyFrac <= bodyMax   and  max(upWick, dnWick) >= wickMin
direction = dnWick > upWick ? bullish : bearish
name      = direction + (close >= open ? green-name : red-name)
```

Three inputs — `bodyMax`, `wickMin`, and the merge width — and every name
falls out. No thresholds hidden in the code.

### What it draws

For each group of *n* adjacent candles:

* a faint box over the group, so it is obvious which candles were merged
* the merged candle itself, drawn beside the group as a body rectangle and a
  wick line, so you can see the thing being classified
* the name, once, under the group

Merge width should be an input, and sweeping it (2, 3, 4) is the first
experiment: a group that reads as a pin at width 3 and as nothing at width 2
is exactly what "after effect" means, and the chart is where that gets decided.

### One thing to expect

Some groups will come out with a different name than the eye gives them,
because the merge arithmetic is strict and the sheet's rule ignores colour.
In the left-hand circle of the screenshot — green candle, small red with a long
upper wick, red candle — the merge gives a small body with a long upper wick,
which is the **inverted hammer / shooting star shape, bearish**, and the move
after it was down. That one agrees. Others will not, and the point of building
the tool rather than reasoning about it is to find out which.

---

## 6. Order of work, and what it depends on

1. **`riptide-ccp.pine`** first. It is standalone, touches nothing, and until
   the classifier exists the digest in §4 has no end-shapes to print.
2. Sweep the merge width on real charts. Decide whether "both ends the same
   shape" is a thing worth filtering on.
3. **`grabwatch.py`** second, modelled on `watch.py`, wide grabs only, 1h,
   default off, no outcome tracking.
4. Only after it has run for a while, and only through a prereg, does anything
   here get to claim it predicts something.

## 7. Decisions still open

* interval and instance — **1h + wide only** is the recommendation; 15m + wide
  if that is too quiet
* whether narrow grabs ever alert
* merge width default, and whether the merged candle is drawn on the chart or
  in a separate pane
* whether a "both ends are the same shape" condition gates the alert, which
  cannot be answered before step 2
