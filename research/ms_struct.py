"""The market-structure engine of riptide-indicator-v2.pine section 12, in
Python.

TRANSCRIBED, NOT REIMPLEMENTED. Every identifier carries the same name as the
Pine, and every condition is written in the same order, so the two can be
compared mechanically rather than by eye:

    python3 deploy/ms-port-check.py riptide-indicator-v2.pine research/ms_struct.py

That is the parity check LIT never had, and the reason this file reads oddly
for Python — `msSBtmCrossed` is not a name anyone would choose here. It is the
name in the Pine, so it is the name here.

What the engine is: CHoCH from long-period swings, BOS from the running
extreme, IDM from short-period swings, sweeps from a wick through the running
extreme that closes back inside. Boundaries MIGRATE — every new swing re-seeds
them — which is why it has no equivalent of the LIT PH_SEEK latch.
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


def ms_swings(cs, msL):
    """`msSwings()` from the Pine, evaluated for every bar at once.

    Returns four per-bar lists: the swing price on the bar it is confirmed
    (None otherwise), and the forward-filled bar index of the latest one.
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


def engine(cs, msLen=15, msShortLen=3, msBosNeedsIdm=True):
    """One pass. Returns a list of events, each a dict:

    Returns (events, state). `state` holds per-bar os / cycle / stop levels.

        kind   "choch" | "bos" | "idm" | "sweep"
        bar    the bar it fired on
        dir    the structure direction at the time, +1 bull / -1 bear
        px     the level involved
        close  that bar's close — what a market entry would get
        cycle  how many CHoCH flips have happened, so events can be grouped
        sBtmY  the live short-period low   } the stop candidates, captured at
        sTopY  the live short-period high  } the moment the event fired
    """
    msTop, msTopX, msBtm, msBtmX = ms_swings(cs, msLen)
    msSTop, msSTopX, msSBtm, msSBtmX = ms_swings(cs, msShortLen)

    msOs = 0
    msTopCrossed = False
    msBtmCrossed = False
    msMax = None
    msMin = None
    msMaxX = None
    msMinX = None
    msTopY = None
    msBtmY = None
    msSTopCrossed = False
    msSBtmCrossed = False
    msSTopY = None
    msSBtmY = None

    cycle = 0
    ev = []
    # Per-bar state, for the RANDOM control in the entry-model study: it
    # needs to enter at an arbitrary bar with the stop rule as it stood
    # there. Collected by .append(), which the parity checker does not read
    # as logic, so it adds nothing to compare against the Pine.
    st = dict(os=[], cyc=[], sBtmY=[], sTopY=[])

    def gt(a, b):
        return a is not None and b is not None and a > b

    def lt(a, b):
        return a is not None and b is not None and a < b

    for i, c in enumerate(cs):
        o, h, l, cl = c.o, c.h, c.l, c.c
        msOsPrev = msOs
        msMaxPrev = msMax
        msMinPrev = msMin

        if msTop[i] is not None:
            msTopY = msTop[i]
            msTopCrossed = False
        if msBtm[i] is not None:
            msBtmY = msBtm[i]
            msBtmCrossed = False

        if gt(cl, msTopY) and not msTopCrossed:
            msOs = 1
            msTopCrossed = True
        if lt(cl, msBtmY) and not msBtmCrossed:
            msOs = 0
            msBtmCrossed = True

        if msOs != msOsPrev:
            cycle += 1
            msMax = h
            msMin = l
            msMaxX = i
            msMinX = i
            msSTopCrossed = False
            msSBtmCrossed = False
            ev.append(dict(kind="choch", bar=i, dir=1 if msOs == 1 else -1,
                           px=msTopY if msOs == 1 else msBtmY, close=cl,
                           cycle=cycle, sBtmY=msSBtmY, sTopY=msSTopY))

        if msSTop[i] is not None:
            msSTopY = msSTop[i]
        if msSBtm[i] is not None:
            msSBtmY = msSBtm[i]

        # ── bullish ────────────────────────────────────────────────────────
        if lt(l, msSBtmY) and not msSBtmCrossed and msOs == 1 \
                and msSBtmY != msBtmY:
            ev.append(dict(kind="idm", bar=i, dir=1, px=msSBtmY, close=cl,
                           cycle=cycle, sBtmY=msSBtmY, sTopY=msSTopY))
            msSBtmCrossed = True

        if gt(cl, msMax) and (not msBosNeedsIdm or msSBtmCrossed) and msOs == 1:
            ev.append(dict(kind="bos", bar=i, dir=1, px=msMax, close=cl,
                           cycle=cycle, sBtmY=msSBtmY, sTopY=msSTopY))
            msSBtmCrossed = False

        # ── bearish ────────────────────────────────────────────────────────
        if gt(h, msSTopY) and not msSTopCrossed and msOs == 0 \
                and msSTopY != msTopY:
            ev.append(dict(kind="idm", bar=i, dir=-1, px=msSTopY, close=cl,
                           cycle=cycle, sBtmY=msSBtmY, sTopY=msSTopY))
            msSTopCrossed = True

        if lt(cl, msMin) and (not msBosNeedsIdm or msSTopCrossed) and msOs == 0:
            ev.append(dict(kind="bos", bar=i, dir=-1, px=msMin, close=cl,
                           cycle=cycle, sBtmY=msSBtmY, sTopY=msSTopY))
            msSTopCrossed = False

        # ── sweeps ─────────────────────────────────────────────────────────
        # A sweep is a FAILED continuation, so its direction is against the
        # trend: a bull-trend sweep pokes above the running high and closes
        # back under it.
        if gt(h, msMax) and lt(cl, msMax) and msOs == 1 \
                and msMaxX is not None and i - msMaxX > 1:
            ev.append(dict(kind="sweep", bar=i, dir=-1, px=msMax, close=cl,
                           cycle=cycle, sBtmY=msSBtmY, sTopY=msSTopY))
        if lt(l, msMin) and gt(cl, msMin) and msOs == 0 \
                and msMinX is not None and i - msMinX > 1:
            ev.append(dict(kind="sweep", bar=i, dir=1, px=msMin, close=cl,
                           cycle=cycle, sBtmY=msSBtmY, sTopY=msSTopY))

        st["os"].append(1 if msOs == 1 else -1)
        st["cyc"].append(cycle)
        st["sBtmY"].append(msSBtmY)
        st["sTopY"].append(msSTopY)

        # Trailing extremes, AFTER the tests above read them.
        msMax = h if msMax is None else max(h, msMax)
        msMin = l if msMin is None else min(l, msMin)
        if msMaxPrev is None or msMax > msMaxPrev:
            msMaxX = i
        if msMinPrev is None or msMin < msMinPrev:
            msMinX = i

    return ev, st
