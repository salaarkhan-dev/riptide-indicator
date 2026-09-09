"""An EXACT port of `liquidity-trendline.pine`, and nothing else.

This file only produces breakouts. It does not score them, does not filter them
and has no opinion about them. `research/studies/trendline_measure.py` scored
them and `riptide/watch.py` alerts on them; keeping the port in one module
means the thing verified against the chart, the thing that was measured and the
thing that sends a message are the same object, and a change to one cannot
silently fail to reach the others.

IT LIVES IN `riptide/` RATHER THAN `research/` FOR EXACTLY THAT REASON. A copy
under research and a copy in the bot would be two indicators with one name, and
the day they drifted apart nothing would say so.

NOTHING HERE IS A TRADE. `trendline_measure.py` put these breakouts through the
same scorer as everything else: net R per signal is NEGATIVE on both halves of
the window and indistinguishable from a random entry of the same shape. The
break is used as a HEADS-UP — "this chart is doing something, go look" — and
that is the only claim the alert makes.

WHAT THE INDICATOR ACTUALLY DOES

    1  Confirmed pivot highs go into `upbin`, newest first. Pivot lows go into
       `dnbin`.
    2  When the newest two pivot highs are DESCENDING, a channel may be drawn:
       a line through those two pivots, plus a parallel `space * vol()` below.
       Validity needs either the global `broken` flag, or four stored pivots
       whose newest two are both under the two before them.
    3  A backward walk then asks whether the line was ever violated. If so the
       channel is discarded and `broken` is set; if not it is kept.
    4  On every bar a live channel is extended, and price closing clear of it
       fires the breakout.

    The low side mirrors this, with two asymmetries that are in the source and
    are reproduced rather than corrected. See ASYMMETRIES below.

THREE THINGS THAT LOOK LIKE MISTAKES AND ARE FAITHFULLY COPIED

  THE BACKWARD WALK IS NOT A GEOMETRIC EXTENSION. Reading it as "extend the
  line and see if price crossed it" is wrong. Each iteration recomputes the
  slope from the line's CURRENT endpoints, jumps `x2` to `bar_index[i]` — which
  moves BACKWARD as i grows — and then moves `y2` by exactly one slope step.
  Because x2 leaps while y2 creeps, and the slope is recomputed from the
  mutated endpoints, the path traced is not the straight line through the two
  pivots. It is reproduced statement for statement; guessing at the intent
  would produce a different indicator.

  THE LIVE EXTENSION IS LINEAR, BUT STARTS FROM THE WRONG POINT. Reading
  `set_x2(b.n); set_y2(y2 + slope)` as a progressive drift is wrong, and this
  file said so until the tests were written: once x2 advances one bar at a
  time, `y2 - y1` and `x2 - x1` grow together and the point stays exactly on
  the line. The distortion is a single step, at creation. A channel is built on
  the confirming bar with `x2 = i - period`, so the first extension jumps x2
  forward by `period` bars while y2 moves ONE slope unit. From then on the line
  is straight — but permanently `(period - 1)` slope units away from the true
  pivot-to-pivot projection, and for a descending resistance that means HIGHER,
  which makes the upside break harder rather than easier. See
  `research/test_trendline.py`, which computes both by hand.

  `broken` IS SHARED BETWEEN THE TWO SIDES. A low-side channel breaking sets
  the same flag the high side reads, so a downside break lets the very next
  descending pivot pair form a channel without the four-pivot test. The sides
  are coupled through one boolean.

ASYMMETRIES, also copied

  The up channel tests the breakout against `upln[1]` — the raw pivot-to-pivot
  line. The down channel tests against `dnln[0]` — the PADDED line, which on
  that side sits ABOVE the raw one. So the two sides do not use the same
  threshold: the upside break is measured at the trendline and the downside
  break `space * vol()` away from it.

  Both backward walks subtract the slope (`y2 - slope`), including the low side
  where the mirrored operation would be to add it.

`vol()` is `min(0.1 * ATR(200), 0.001 * close)` evaluated on the bar the
channel is created, and Pine's `ta.atr(200)` is `na` for the first 199 bars, so
no channel can be built before bar 200. That warm-up is reproduced: this
project's `rma` returns a partial average where Pine returns `na`, and using it
would create channels the chart never draws.

NON-REPAINTING. A pivot is confirmed `pivot_len` bars after it prints and is
used no earlier; a channel is built on the bar that confirms it; a break is
tested on a bar's own high/low against a line extended from prior bars only.
Nothing reads forward. The bot feeds it closed candles only, so what it sends
is what the chart shows once the bar is done.

    PYTHONPATH=. python3 research/studies/trendline.py ETH_USDT Min30
"""
from __future__ import annotations

from dataclasses import dataclass

from .engine import atr_series

PIVOT_LEN = 5          # `len`
SPACE = 2.0            # `space`
ATR_LEN = 200          # ta.atr(200)


@dataclass
class Line:
    """A Pine `line`, with only the four coordinates that matter here."""
    x1: int
    y1: float
    x2: int
    y2: float

    def slope(self) -> float:
        # `method slope(line ln) => (y2 - y1) / (x2 - x1)`. Pine returns na on
        # a zero run and na propagates harmlessly; here it cannot happen,
        # because x2 only reaches x1 on the final iteration of a walk that
        # computes the slope before moving x2.
        dx = self.x2 - self.x1
        return (self.y2 - self.y1) / dx if dx else 0.0


@dataclass
class Signal:
    """One arrow on the chart.

    THE BREAK CONDITION IS STRICTER THAN "CLOSES BEYOND THE LINE", and this is
    worth being explicit about because it is the natural thing to assume. The
    Pine tests `b.l > top.get_y2()` on the up side and `b.h < btm.get_y2()` on
    the down side: the bar's LOW must be above the line, or its HIGH below it.
    The entire candle, wick included, has to be clear. A candle that closes
    beyond the line but whose wick is still touching it prints no arrow.

    The `plotshape(..., offset = -1)` in the source only moves the triangle one
    bar to the left so it does not sit on top of the candle. The condition
    itself is evaluated on the breaking bar, which is `bar` here.
    """
    bar: int           # the bar the breakout fires on; entry is its close
    is_long: bool      # plup -> long, pldn -> short
    price: float       # that bar's close
    line_y: float      # the line level the break was measured against
    x1: int            # the channel's anchor pivot, for inspection
    y1: float
    pivots: int        # how many pivots were stored when it was built
    # The slope of the line that was broken, in price per bar, and how many
    # bars it spanned at the break. Recorded rather than computed later
    # because the line object is discarded on the break — by the time anything
    # downstream looks, it is gone. Sign is guaranteed by construction: an up
    # channel is only built from DESCENDING pivot highs and a down channel from
    # ASCENDING pivot lows, so what varies is steepness alone.
    slope: float = 0.0
    run: int = 0


def pivot_highs(cs, n: int):
    """(confirm_bar, pivot_bar, price) for `ta.pivothigh(high, n, n)`.

    Strictly greater on both sides, and only known at `pivot_bar + n`, which is
    the bar Pine returns it on.
    """
    out = []
    for j in range(n, len(cs) - n):
        h = cs[j].h
        if all(cs[k].h < h for k in range(j - n, j)) and \
           all(cs[k].h < h for k in range(j + 1, j + n + 1)):
            out.append((j + n, j, h))
    return out


def pivot_lows(cs, n: int):
    out = []
    for j in range(n, len(cs) - n):
        lo = cs[j].l
        if all(cs[k].l > lo for k in range(j - n, j)) and \
           all(cs[k].l > lo for k in range(j + 1, j + n + 1)):
            out.append((j + n, j, lo))
    return out


def trendline_signals(cs, pivot_len: int = PIVOT_LEN, space: float = SPACE,
                      atr_len: int = ATR_LEN) -> list[Signal]:
    """Every breakout the indicator prints, in bar order.

    One pass, mirroring the Pine's per-bar execution order exactly: the pivot
    high block, then the up-channel extension, then the pivot low block, then
    the down-channel extension. That order matters — `broken` is written by the
    first two and read by the third.
    """
    atr = atr_series(cs, atr_len)
    ph_at = {c: (j, px) for c, j, px in pivot_highs(cs, pivot_len)}
    pl_at = {c: (j, px) for c, j, px in pivot_lows(cs, pivot_len)}

    upbin: list[tuple[float, int]] = []      # (src, n), index 0 is newest
    dnbin: list[tuple[float, int]] = []
    upln: list[Line] = []                    # [padded, raw]
    dnln: list[Line] = []
    broken = False
    out: list[Signal] = []

    for i, c in enumerate(cs):
        # `vol()` uses ta.atr(200), which is na until bar 200. A channel built
        # on a na offset is a channel the chart never draws.
        a = atr[i] if i >= atr_len - 1 else None
        vol = min(a * 0.1, c.c * 0.001) if a is not None and a > 0 else None
        plup = pldn = False

        # ------------------------------------------------ if ph
        if i in ph_at and vol is not None:
            pj, ppx = ph_at[i]
            upbin.insert(0, (ppx, pj))       # unshift
            if len(upbin) > 1:
                cur, bef = upbin[0], upbin[1]
                if cur[0] < bef[0]:
                    if broken:
                        valid = True
                    elif len(upbin) > 3:
                        late, now = upbin[0], upbin[1]
                        pastcur, pastold = upbin[2], upbin[3]
                        valid = (now[0] < pastcur[0] and now[0] < pastold[0]
                                 and late[0] < pastcur[0]
                                 and late[0] < pastold[0])
                    else:
                        valid = False

                    if valid:
                        # upln = [padded, raw]; the walk mutates the RAW line.
                        ln = Line(bef[1], bef[0], cur[1], cur[0])
                        remove = False
                        for k in range(0, (i - bef[1]) + 1):
                            s = ln.slope()
                            ln.x2 = i - k
                            ln.y2 = ln.y2 - s
                            if cs[i - k].l > ln.y2:
                                remove = True
                                break
                        upbin.clear()
                        if remove:
                            upln.clear()
                            broken = True
                        else:
                            # Rebuilt from the ORIGINAL pivot coordinates: the
                            # walk's mutations are discarded, as in the Pine.
                            upln = [Line(bef[1], bef[0] - vol * space,
                                         cur[1], cur[0] - vol * space),
                                    Line(bef[1], bef[0], cur[1], cur[0])]
                            broken = False

        # ------------------------------------------------ up channel, live
        if len(upln) > 1:
            btm, top = upln[0], upln[1]
            if c.l > top.y2:
                sig_y = top.y2
                x1, y1 = top.x1, top.y1
                slope, run = top.slope(), top.x2 - top.x1
                upln = []
                broken = True
                upbin.clear()
                plup = True
                out.append(Signal(i, True, c.c, sig_y, x1, y1, len(upbin),
                                  slope, run))
            if len(upln) > 1:
                slup, sldn = top.slope(), btm.slope()
                top.x2, top.y2 = i, top.y2 + slup
                btm.x2, btm.y2 = i, btm.y2 + sldn

        # ------------------------------------------------ if pl
        if i in pl_at and vol is not None:
            pj, ppx = pl_at[i]
            dnbin.insert(0, (ppx, pj))
            if len(dnbin) > 1:
                cur, bef = dnbin[0], dnbin[1]
                if cur[0] > bef[0]:
                    if broken:
                        valid = True
                    elif len(dnbin) > 3:
                        late, now = dnbin[0], dnbin[1]
                        pastcur, pastold = dnbin[2], dnbin[3]
                        valid = (now[0] > pastcur[0] and now[0] > pastold[0]
                                 and late[0] > pastcur[0]
                                 and late[0] > pastold[0])
                    else:
                        valid = False

                    if valid:
                        ln = Line(bef[1], bef[0], cur[1], cur[0])
                        remove = False
                        for k in range(0, (i - bef[1]) + 1):
                            s = ln.slope()
                            ln.x2 = i - k
                            # MINUS, exactly as in the source. The mirrored
                            # operation would be plus; it is not what runs.
                            ln.y2 = ln.y2 - s
                            if cs[i - k].h < ln.y2:
                                remove = True
                                break
                        dnbin.clear()
                        if remove:
                            dnln.clear()
                            broken = True
                        else:
                            dnln = [Line(bef[1], bef[0] + vol * space,
                                         cur[1], cur[0] + vol * space),
                                    Line(bef[1], bef[0], cur[1], cur[0])]
                            broken = False

        # ------------------------------------------------ down channel, live
        if len(dnln) > 1:
            btm, top = dnln[0], dnln[1]
            # `btm` is dnln[0], the PADDED line, which on this side sits ABOVE
            # the raw one. The up side tests against the raw line instead.
            if c.h < btm.y2:
                sig_y = btm.y2
                x1, y1 = btm.x1, btm.y1
                slope, run = btm.slope(), btm.x2 - btm.x1
                dnln = []
                broken = True
                dnbin.clear()
                pldn = True
                out.append(Signal(i, False, c.c, sig_y, x1, y1, len(dnbin),
                                  slope, run))
            if len(dnln) > 1:
                slup, sldn = top.slope(), btm.slope()
                top.x2, top.y2 = i, top.y2 + slup
                btm.x2, btm.y2 = i, btm.y2 + sldn
    return out
