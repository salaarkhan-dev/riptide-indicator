"""Two swing detectors, and the reason there are two.

THE PROBLEM, in the user's words: "the problem is each work different on
different TF". `msLen = 15` is fifteen BARS. On 3m that is 45 minutes; on 1h it
is fifteen hours. The same number describes two completely different things, so
a setting tuned on one timeframe is meaningless on another — and a "best
parameter per timeframe" table found by search is three separate overfits
wearing one hat.

The fix is to stop measuring a swing in bars and measure it in PRICE — a swing
is a reversal of `k x <something>`, with no bar window at all. Then the only
question is what that something is, and the first answer tried here was wrong
in a way worth keeping written down.

WRONG ANSWER: k x ATR(14). The reasoning was "ATR already carries the
timeframe". It does — in the wrong direction. Aggregating four bars into one
multiplies the per-bar ATR by roughly sqrt(4), so `k x ATR` asks for a move
TWICE as large on the higher timeframe and finds a quarter as many swings per
unit of time. Measured, on a 4000-bar random walk aggregated 4:1:

    bar pivot 15    138 -> 42 swings   (x0.30)
    k x ATR(14)     407 -> 89 swings   (x0.22)     WORSE than the thing it fixes

A per-bar quantity cannot be the unit, because the bar is what changes.

RIGHT ANSWER: k x the RANGE OF A FIXED SPAN OF TIME. `range_basis` below is the
average high-to-low of the last `hours` of trading, computed over however many
bars that takes — 96 bars on 15m, 24 on 1h. A day's range is a day's range
whichever chart you open it on, so `k = 0.4` asks the same question of both.
Same measurement:

    k x day range   119 -> 106 swings  (x0.89)

WHAT IT STILL COSTS:

  * confirmation lags by MOVEMENT rather than by bars. A bar pivot is known
    msLen bars later, always. A price swing is known when price has retraced
    the threshold, which can be two bars or forty. Neither repaints; they lag
    differently.
  * one parameter replaces two, and it is not the same parameter, so nothing
    measured on `msLen` transfers.
  * x0.89 is not x1.00. A 1h chart cannot resolve a swing that lives inside one
    of its bars, so some structure is genuinely unavailable there. That part is
    not a defect in the detector.
  * it is NOT the v2 engine's detector. Everything downstream is unchanged --
    the same crossing state machine, the same CHoCH, BOS, IDM and sweep tests
    read these swings -- but the swings themselves are Undertow's own, and
    deploy/undertow-ms-check.py does not cover this file.

WHICH ONE MAKES MORE MONEY IS NOT KNOWN AND IS NOT ASSERTED HERE. Scale
invariance is a property of the DETECTOR, proved above; it says nothing about
whether the setups it finds are better. `bar` stays the default. This module
exists so the question can be an arm in a study instead of an opinion.

Both functions return the same four per-bar lists as the Pine's `msSwings()`:

    tops[i]   the swing HIGH price, on the bar it is CONFIRMED, else None
    topxs[i]  forward-filled bar index of the bar that swing high SITS on
    btms[i]   the swing LOW price, on the bar it is confirmed, else None
    btmxs[i]  forward-filled bar index of the bar it sits on

That shape is load-bearing: `tops[i] is not None` is the event, and `topxs[i]`
is where to draw it. Keeping it identical is what lets one engine read either
detector.
"""
from __future__ import annotations

from collections import deque


def _roll(vals, L, cmp):
    """Rolling extreme over the trailing L bars INCLUDING the current one, the
    way ta.highest / ta.lowest do it. Monotonic deque, so O(n) not O(n*L)."""
    out = [None] * len(vals)
    dq: deque = deque()
    for i, v in enumerate(vals):
        while dq and cmp(vals[dq[-1]], v):
            dq.pop()
        dq.append(i)
        while dq[0] <= i - L:
            dq.popleft()
        out[i] = vals[dq[0]]
    return out


def bar_swings(cs, msL: int):
    """`msSwings()` from riptide-indicator-v2.pine section 12, verbatim logic.

    This is the same transcription as indicators/riptide_ms/port/ms_struct.py
    and is kept identical to it on purpose -- tests/test_undertow_port.py
    asserts the two agree bar for bar, so a fix to one that misses the other
    fails rather than hides.
    """
    n = len(cs)
    highs = [c.h for c in cs]
    lows = [c.l for c in cs]
    hh = _roll(highs, msL, lambda a, b: a <= b)
    ll = _roll(lows, msL, lambda a, b: a >= b)

    sOs = 0
    sTopX = None
    sBtmX = None
    tops, topxs, btms, btmxs = [], [], [], []
    for i in range(n):
        was = sOs
        if i >= msL:
            if highs[i - msL] > hh[i]:
                sOs = 0
            elif lows[i - msL] < ll[i]:
                sOs = 1
            else:
                sOs = was
        sTop = highs[i - msL] if (i >= msL and sOs == 0 and was != 0) else None
        if i >= msL and sOs == 0 and was != 0:
            sTopX = i - msL
        sBtm = lows[i - msL] if (i >= msL and sOs == 1 and was != 1) else None
        if i >= msL and sOs == 1 and was != 1:
            sBtmX = i - msL
        tops.append(sTop)
        topxs.append(sTopX)
        btms.append(sBtm)
        btmxs.append(sBtmX)
    return tops, topxs, btms, btmxs


def range_basis(cs, n: int):
    """The average high-to-low range of the last `n` bars, as a price.

    THE TIMEFRAME-INVARIANT UNIT. Pass `n` = the number of bars in a fixed span
    of time and this returns the same price on every timeframe, because the
    range of a day does not depend on how the day is sliced. Contrast ATR(14),
    which is the range of a BAR and therefore scales with the bar.

    Smoothed with the same rolling window rather than an rma, so it has no
    memory beyond the span it names -- `hours=24` means the last 24 hours, not
    an exponential tail reaching back a week.
    """
    n = max(2, int(n))
    highs = [c.h for c in cs]
    lows = [c.l for c in cs]
    hh = _roll(highs, n, lambda a, b: a <= b)
    ll = _roll(lows, n, lambda a, b: a >= b)
    return [h - l for h, l in zip(hh, ll)]


def bars_per(cs, hours: float) -> int:
    """How many bars cover `hours`, from the candles' own timestamps.

    The SMALLEST gap between consecutive bars is the step: a session break or a
    missing candle only ever makes a gap larger. Getting this from the data
    rather than from a config string is what lets one setting run unchanged
    across 15m, 30m and 1h.
    """
    gaps = [b.t - a.t for a, b in zip(cs, cs[1:]) if b.t > a.t]
    step = min(gaps) if gaps else 0
    return max(2, round(hours * 3600 / step)) if step > 0 else 2


def price_swings(cs, k: float, scale: list, warmup: int = 20):
    """A swing is a reversal of `k * scale[i]`. No bar window.

    `scale` is the price unit the threshold is quoted in — `range_basis` for a
    timeframe-invariant one, an ATR series for the per-bar one. The state
    machine does not care which; see the module docstring for why the choice
    is the whole point.

    The state machine is the smallest one that cannot look ahead:

        tracking a HIGH   every new high moves the running extreme. The moment
                          price trades `k * scale` BELOW it, that extreme is a
                          confirmed swing high, emitted on the confirming bar
                          and dated to the bar it sits on. Now track a low.
        tracking a LOW    mirror image.

    THE THRESHOLD IS READ ON THE CONFIRMING BAR, not on the extreme's bar. Both
    are defensible; this one is what a live scanner can do, because the scale at
    the extreme is not the scale now and only "now" is available to act on.

    `low` is tested before `high` inside one bar, which matters only when a
    single bar both extends the extreme and retraces past the threshold. That
    bar's order is unknowable intrabar, so the conservative reading is taken:
    while tracking a high, a bar that makes a new high does NOT also confirm
    on its own low. It gets one more bar.

    `warmup` drops the opening bars where the scale series is still filling and
    the threshold is meaningless.
    """
    n = len(cs)
    tops = [None] * n
    btms = [None] * n
    topxs = [None] * n
    btmxs = [None] * n
    if n == 0:
        return tops, topxs, btms, btmxs

    up = True                      # True = tracking a potential swing HIGH
    ext = cs[0].h
    extX = 0
    sTopX = None
    sBtmX = None
    for i in range(n):
        c = cs[i]
        thr = k * (scale[i] or 0.0)
        if i >= warmup and thr > 0:
            if up:
                if c.h > ext:
                    ext, extX = c.h, i
                elif ext - c.l >= thr:
                    tops[i] = ext
                    sTopX = extX
                    up = False
                    ext, extX = c.l, i
            else:
                if c.l < ext:
                    ext, extX = c.l, i
                elif c.h - ext >= thr:
                    btms[i] = ext
                    sBtmX = extX
                    up = True
                    ext, extX = c.h, i
        else:
            # Warmup: track the extreme so the first real swing is not dated to
            # bar `warmup`, but confirm nothing.
            if up and c.h > ext:
                ext, extX = c.h, i
            elif not up and c.l < ext:
                ext, extX = c.l, i
        topxs[i] = sTopX
        btmxs[i] = sBtmX
    return tops, topxs, btms, btmxs
