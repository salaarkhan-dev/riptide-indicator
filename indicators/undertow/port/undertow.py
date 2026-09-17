"""Riptide Undertow in Python — the transcription of riptide-undertow.pine.

WHY A PORT EXISTS. The Pine answers one chart at a time and scores it in
sample, which is how every bad result in this repository was produced. The port
answers the questions the chart cannot: the same rules over many symbols, three
timeframes, a held-out half and a random control, in seconds instead of an
afternoon of clicking.

TRANSCRIBED, NOT REIMPLEMENTED. Every identifier carries the Pine's name and
every condition is written in the Pine's order, so the two can be compared
mechanically rather than by eye:

    python3 deploy/undertow-port-check.py     the inputs: same names, same
                                              defaults, same dropdown strings
    indicators/undertow/tests/test_undertow_port.py    the logic

That is why this file reads oddly for Python. `msSBtmCrossed`, `pbExtX` and
`workHi` are not names anyone would choose here; they are the names in the
Pine, so they are the names here. The first of those two checks found a real
drift on its first run -- `rr` had defaulted to 2.0 here and 3.0 in the Pine --
which is exactly the silent kind: a study reporting a number for settings the
chart is not running.

THREE THINGS THE PORT HAS THAT THE PINE DOES NOT, each because Pine cannot:

  1. PRICE SWINGS (swings.py). A swing as a k x price move instead of n bars,
     so one setting can mean the same thing on 15m and on 1h. Off by default,
     and swings.py records the measurement that says WHICH price unit works --
     the obvious one, ATR, is worse than the bar pivot it replaces.
  2. HTF BIAS. Doing this correctly in Pine needs the whole structure engine
     inside a function so request.security can evaluate it on higher-timeframe
     bars, which would break the parity check against v2. In Python it is
     resampling and a forward-fill, with the HTF state made visible only on the
     base bar where the HTF bar CLOSES — no look-ahead.
  3. COSTS. A round-trip fee in R, subtracted per trade. The Pine's net R is
     gross and says so; at 1m gross is a fantasy and even at 30m it is not
     exactly right.

WHAT IT DELIBERATELY KEEPS. The ghost column: a setup the bias gate cancels is
walked forward anyway, into separate counters, so the gate can be measured
instead of trusted. See SPEC.md.

NOTHING HERE PLACES AN ORDER, and nothing here reads an API key.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from indicators.undertow.port.swings import (bar_swings, bars_per,
                                             price_swings, range_basis)

# The Pine's three comparison modes, by their exact input strings.
T_CLOSE = "close beyond"
T_TOUCH = "close at or beyond"
T_BODY = "whole body beyond"
# `stopSrc`
S_PIN = "Pin high / low"
S_PULL = "Pullback extreme"
S_SWING = "Minor swing extreme"
# `endMinor`
E_OFF = "off"
E_FLIP = "on the flip"
E_OPPOSED = "while opposed"


@dataclass(frozen=True)
class P:
    """Every input in the Pine, same names, same defaults, plus the three the
    Pine cannot have. Frozen so a sweep cannot mutate a shared config."""
    # 1 · Bias
    msLen: int = 6
    msShortLen: int = 2
    msBosNeedsIdm: bool = True
    endMinor: str = E_FLIP
    endSweep: bool = False
    endStale: bool = False
    staleBars: int = 30
    retraceMax: int = 70
    adxMin: int = 0
    # 2 · Candle
    wickEdge: float = 0.05
    useHammer: bool = True
    useStar: bool = True
    # 3 · Setup
    workTest: str = T_CLOSE
    failTest: str = T_CLOSE
    confirmBars: int = 20
    fillBars: int = 20
    maxLive: int = 4
    locTol: int = 0
    # 4 · Levels
    stopSrc: str = S_PULL
    stopTrack: bool = True
    stopBuf: float = 0.25
    rr: float = 3.5
    # 5 · Backup fill. "if we miss we can fill the order as a backup on any OB
    # or FVG." OFF by default and unmeasured. It is NOT a better price: for a
    # short the zone sits BELOW the Focus, so it is further from the stop --
    # bigger risk, further target, worse R on the same move. What it buys is a
    # trade instead of no trade.
    useBackup: bool = False
    bkTrigger: float = 1.0
    bkMaxRisk: float = 2.0
    useOB: bool = True
    useFVG: bool = True
    bkLook: int = 30
    # ── port only ───────────────────────────────────────────────────────────
    # WHERE THE SWINGS COME FROM. See swings.py -- the choice is the answer to
    # "each works different on different TF", and the three options are not
    # equally good at it. Measured on a 4:1 aggregation, swings per unit time:
    #     "bar"    the v2 pivot, msLen / msShortLen in BARS       x0.30
    #     "atr"    k x ATR(14). A per-bar unit, so it is WORSE    x0.22
    #     "range"  k x the range of `swingHours` of trading       x0.89
    # "range" is the only one that means the same thing on 15m and on 1h.
    # "bar" stays the default because being scale-invariant is not the same as
    # being profitable, and only a study can say which.
    swingSrc: str = "bar"
    swingK: float = 0.40
    swingKMinor: float = 0.12
    swingHours: float = 24.0
    # HTF bias. 0 = off. Otherwise the number of BASE bars per HTF bar, so 4 on
    # a 15m chart is 1h. The bias is computed on the aggregate and a setup may
    # only be taken when the HTF direction agrees with the base direction.
    htfMult: int = 0
    # ABLATION SWITCHES. Not inputs on the chart, because they are not settings
    # anyone should trade -- they exist so a study can remove one gate at a
    # time and attribute the difference. The Pine has no equivalent and must
    # not grow one; deploy/undertow-port-check.py lists them as port-only.
    #   useFamily  False -> every bar passes the wick taxonomy. The 1CP layer
    #                       is gone and only location and colour remain.
    #   useColour  False -> the counter-trend colour test is gone.
    # With both off and locTol at 0, the "pin" is just "the pullback extreme".
    useFamily: bool = True
    useColour: bool = True
    # Round-trip cost as a fraction of NOTIONAL, subtracted per trade after
    # conversion to R. 0.0007 is a maker-in / taker-out round trip on a major
    # perp. Not a guess at slippage, which is separate and worse.
    feeFrac: float = 0.0

    def tag(self) -> str:
        """The settings that a sweep varies, in one short line."""
        sw = (f"bar {self.msLen}/{self.msShortLen}" if self.swingSrc == "bar"
              else f"{self.swingSrc} {self.swingK}/{self.swingKMinor}")
        return (f"{sw} idm{int(self.msBosNeedsIdm)} "
                f"end[{self.endMinor[:4]}|{int(self.endSweep)}"
                f"{int(self.endStale)}|rt{self.retraceMax}|adx{self.adxMin}] "
                f"w{self.wickEdge} loc{self.locTol} rr{self.rr} "
                f"htf{self.htfMult}")


@dataclass(eq=False)
class Trade:
    """One filled setup, walked to its target or its stop."""
    symbol: str = ""
    bar: int = 0                 # the pin
    armBar: int = 0
    fillBar: int = 0
    exitBar: int = 0
    short: bool = False
    entry: float = 0.0
    stop: float = 0.0
    target: float = 0.0
    won: bool = False
    r: float = 0.0               # net of feeFrac
    ghost: bool = False          # the bias gate cancelled it; scored apart
    state: str = ""              # the bias AT THE PIN
    code: str = ""               # HAM / HGM / IH / SS
    backup: str = ""             # "OB" / "FVG" if this was a backup fill


@dataclass
class Result:
    symbol: str = ""
    bars: int = 0
    # the funnel, exactly the Pine's panel
    nRaw: int = 0
    nPins: int = 0
    nColour: int = 0
    nLoc: int = 0
    nCap: int = 0
    nArmed: int = 0
    nFilled: int = 0
    nMissBack: int = 0
    nMissStop: int = 0
    nMissGone: int = 0
    nMissBias: int = 0
    # Fills that came from a backup zone rather than the Focus line. Counted
    # apart so no number can imply the limit worked when it did not.
    nBackup: int = 0
    # which Ending rule cancelled an armed setup
    nEndMinor: int = 0
    nEndSweep: int = 0
    nEndStale: int = 0
    nEndRetr: int = 0
    nEndAdx: int = 0
    # HTF disagreement, when htfMult is on
    nHtf: int = 0
    trades: list = field(default_factory=list)
    # THE MOMENT A LIMIT ORDER WOULD GO ON. One entry per setup that armed:
    # (bar, symbol, short, entry, stop, target, code, state). This is the only
    # thing the live watcher alerts on, and indicators/undertow/tests/
    # test_watch_undertow.py asserts the bot's own copy of the machine
    # reproduces this list exactly.
    armed: list = field(default_factory=list)

    @property
    def real(self):
        return [t for t in self.trades if not t.ghost]

    @property
    def ghosts(self):
        return [t for t in self.trades if t.ghost]

    @property
    def netR(self) -> float:
        return sum(t.r for t in self.real)

    @property
    def gateCost(self) -> float:
        """What the cancelled setups would have made. Positive = the gate is
        throwing trades away; negative = it cancelled losers."""
        return sum(t.r for t in self.ghosts)

    def add(self, o: "Result") -> "Result":
        for k, v in vars(o).items():
            if isinstance(v, int) and k != "bars":
                setattr(self, k, getattr(self, k) + v)
        self.bars += o.bars
        self.trades += o.trades
        self.armed += o.armed
        return self


# ───────────────────────────────────────────────────────────── indicators ──


def _rma(values, length):
    """Wilder's smoothing, as ta.rma does it. Same code as riptide.engine.rma;
    duplicated rather than imported so the research tree cannot break the bot
    tree, which is the rule in indicators/README.md."""
    out = []
    acc = 0.0
    for i, v in enumerate(values):
        if i < length:
            acc += v
            out.append(acc / (i + 1))
        else:
            out.append((out[-1] * (length - 1) + v) / length)
    return out


def _tr(cs):
    out = []
    for i, c in enumerate(cs):
        if i == 0:
            out.append(c.h - c.l)
        else:
            pc = cs[i - 1].c
            out.append(max(c.h - c.l, abs(c.h - pc), abs(c.l - pc)))
    return out


def atr_series(cs, length=14):
    return _rma(_tr(cs), length)


def adx_series(cs, diLen=14, adxLen=14):
    """ta.dmi(14, 14)[2]. Transcribed from the Pine reference implementation,
    including the `sum == 0 ? 1 : sum` guard, because that guard is the
    difference between ADX and a divide by zero on a flat bar."""
    n = len(cs)
    plusDM, minusDM = [0.0] * n, [0.0] * n
    for i in range(1, n):
        up = cs[i].h - cs[i - 1].h
        dn = cs[i - 1].l - cs[i].l
        plusDM[i] = up if (up > dn and up > 0) else 0.0
        minusDM[i] = dn if (dn > up and dn > 0) else 0.0
    trur = _rma(_tr(cs), diLen)
    rp, rm = _rma(plusDM, diLen), _rma(minusDM, diLen)
    dx = []
    for i in range(n):
        t = trur[i] or 1e-12
        plus = 100.0 * rp[i] / t
        minus = 100.0 * rm[i] / t
        s = plus + minus
        dx.append(abs(plus - minus) / (s if s != 0 else 1))
    return [100.0 * v for v in _rma(dx, adxLen)]


# ──────────────────────────────────────────────────── the structure engine ──


def _swings(cs, p: P, major: bool, atr):
    if p.swingSrc == "bar":
        return bar_swings(cs, p.msLen if major else p.msShortLen)
    k = p.swingK if major else p.swingKMinor
    scale = (atr if p.swingSrc == "atr"
             else range_basis(cs, bars_per(cs, p.swingHours)))
    return price_swings(cs, k, scale)


def structure(cs, p: P):
    """Sections 3 and 4 of the Pine, one pass, per-bar state out.

    Section 3 is the copied v2 engine and the statements are unchanged from
    riptide_ms/port/ms_struct.py. Section 4 is the same crossing machine run on
    the SHORT swings and is Undertow's own.
    """
    n = len(cs)
    atr = atr_series(cs, 14)
    msTop, msTopX, msBtm, msBtmX = _swings(cs, p, True, atr)
    msSTop, msSTopX, msSBtm, msSBtmX = _swings(cs, p, False, atr)

    msOs = 0
    msTopCrossed = False
    msBtmCrossed = False
    msMax = msMin = msMaxX = msMinX = None
    msTopY = msBtmY = None
    msSTopCrossed = False
    msSBtmCrossed = False
    msSTopY = msSBtmY = None
    # section 4
    msSOs = 0
    msSTopXd = False
    msSBtmXd = False
    msSTopLvl = msSBtmLvl = None

    out = dict(os=[], choch=[], bosUp=[], bosDn=[], sweepUp=[], sweepDn=[],
               msMax=[], msMin=[], msMaxX=[], msMinX=[], sOs=[],
               minorChoch=[], sTopY=[], sBtmY=[])

    def gt(a, b):
        return a is not None and b is not None and a > b

    def lt(a, b):
        return a is not None and b is not None and a < b

    for i in range(n):
        c = cs[i]
        msOsPrev = msOs
        msMaxPrev, msMinPrev = msMax, msMin

        if msTop[i] is not None:
            msTopY = msTop[i]
            msTopCrossed = False
        if msBtm[i] is not None:
            msBtmY = msBtm[i]
            msBtmCrossed = False

        if gt(c.c, msTopY) and not msTopCrossed:
            msOs = 1
            msTopCrossed = True
        if lt(c.c, msBtmY) and not msBtmCrossed:
            msOs = 0
            msBtmCrossed = True

        msChoch = msOs != msOsPrev
        if msChoch:
            msMax, msMin = c.h, c.l
            msMaxX = msMinX = i
            msSTopCrossed = False
            msSBtmCrossed = False

        if msSTop[i] is not None:
            msSTopY = msSTop[i]
        if msSBtm[i] is not None:
            msSBtmY = msSBtm[i]

        msIdmUp = (lt(c.l, msSBtmY) and not msSBtmCrossed and msOs == 1
                   and msSBtmY != msBtmY)
        if msIdmUp:
            msSBtmCrossed = True
        msBosUp = (gt(c.c, msMax) and (not p.msBosNeedsIdm or msSBtmCrossed)
                   and msOs == 1)
        if msBosUp:
            msSBtmCrossed = False

        msIdmDn = (gt(c.h, msSTopY) and not msSTopCrossed and msOs == 0
                   and msSTopY != msTopY)
        if msIdmDn:
            msSTopCrossed = True
        msBosDn = (lt(c.c, msMin) and (not p.msBosNeedsIdm or msSTopCrossed)
                   and msOs == 0)
        if msBosDn:
            msSTopCrossed = False

        msSweepUp = (gt(c.h, msMax) and lt(c.c, msMax) and msOs == 1
                     and msMaxX is not None and i - msMaxX > 1)
        msSweepDn = (lt(c.l, msMin) and gt(c.c, msMin) and msOs == 0
                     and msMinX is not None and i - msMinX > 1)

        # ── section 4, the minor crossing machine ───────────────────────────
        msSOsPrev = msSOs
        if msSTop[i] is not None:
            msSTopLvl = msSTop[i]
            msSTopXd = False
        if msSBtm[i] is not None:
            msSBtmLvl = msSBtm[i]
            msSBtmXd = False
        if gt(c.c, msSTopLvl) and not msSTopXd:
            msSOs = 1
            msSTopXd = True
        if lt(c.c, msSBtmLvl) and not msSBtmXd:
            msSOs = 0
            msSBtmXd = True
        msMinorChoch = msSOs != msSOsPrev

        out["os"].append(msOs)
        out["choch"].append(msChoch)
        out["bosUp"].append(msBosUp)
        out["bosDn"].append(msBosDn)
        out["sweepUp"].append(msSweepUp)
        out["sweepDn"].append(msSweepDn)
        out["sOs"].append(msSOs)
        out["minorChoch"].append(msMinorChoch)
        out["sTopY"].append(msSTopY)
        out["sBtmY"].append(msSBtmY)

        # Trailing extremes, AFTER the tests above read them.
        msMax = c.h if msMax is None else max(c.h, msMax)
        msMin = c.l if msMin is None else min(c.l, msMin)
        if msMaxPrev is None or msMax > msMaxPrev:
            msMaxX = i
        if msMinPrev is None or msMin < msMinPrev:
            msMinX = i
        out["msMax"].append(msMax)
        out["msMin"].append(msMin)
        out["msMaxX"].append(msMaxX)
        out["msMinX"].append(msMinX)

    return out, atr


# ────────────────────────────────────────────────────────────── HTF bias ──


@dataclass
class _Bar:
    t: int
    o: float
    h: float
    l: float
    c: float
    v: float = 0.0


def aggregate(cs, mult: int):
    """`mult` base bars into one, and the BASE index at which each HTF bar is
    finished. Returns (htf_bars, close_index) with close_index[j] the base bar
    whose close completes htf bar j.

    ALIGNED ON THE TIMESTAMP, not on a running count, so the buckets do not
    shift when the feed has a gap — which every broker feed with a session
    break has, and which is a large part of why XAUUSD and XAUUSDT.P disagreed.
    """
    if mult <= 1 or not cs:
        return [], []
    gaps = [b.t - a.t for a, b in zip(cs, cs[1:]) if b.t > a.t]
    step = min(gaps) if gaps else 0
    if step <= 0:
        return [], []
    span = step * mult
    out, closeX = [], []
    cur = None
    for i, c in enumerate(cs):
        b = (c.t // span) * span
        if cur is None or b != cur.t:
            if cur is not None:
                out.append(cur)
                closeX.append(i - 1)
            cur = _Bar(b, c.o, c.h, c.l, c.c, c.v)
        else:
            cur.h = max(cur.h, c.h)
            cur.l = min(cur.l, c.l)
            cur.c = c.c
            cur.v += c.v
    if cur is not None:
        out.append(cur)
        closeX.append(len(cs) - 1)
    return out, closeX


def htf_dir(cs, p: P):
    """Per BASE bar, the HTF bias direction (+1/-1) and whether it is tradeable.

    NO LOOK-AHEAD, and this is the only thing that makes the feature honest: an
    HTF bar's verdict is written onto base bars only from the bar AFTER the one
    that closed it. On the base bars inside a forming HTF bar, the answer is the
    previous HTF bar's -- exactly what a live scanner would have.
    """
    n = len(cs)
    hb, closeX = aggregate(cs, p.htfMult)
    if not hb:
        return [0] * n, [False] * n
    # Same rules, one timeframe up. msLen stays in BARS on the aggregate, which
    # is the point of running it there at all.
    st, _ = structure(hb, p)
    dirs, ok = bias(hb, st, p)
    outD, outK = [0] * n, [False] * n
    for j, ci in enumerate(closeX):
        lo = ci + 1
        hi = closeX[j + 1] if j + 1 < len(closeX) else n - 1
        for i in range(lo, min(hi, n - 1) + 1):
            outD[i] = dirs[j]
            outK[i] = ok[j]
    return outD, outK


# ───────────────────────────────────────────────────────────────── bias ──


def bias(cs, st, p: P):
    """Section 5. Returns (biasDir, tradeable) per bar, plus latches the reason
    in `st["endWhy"]` so a study can attribute a cancellation."""
    n = len(cs)
    adx = adx_series(cs) if p.adxMin > 0 else [0.0] * n
    biasSeen = False
    bosN = 0
    ending = False
    endWhy = "-"
    dirs, ok, whys, states = [], [], [], []
    for i in range(n):
        if st["choch"][i]:
            biasSeen = True
            bosN = 0
            ending = False
        biasDir = 1 if st["os"][i] == 1 else -1
        bosNow = st["bosUp"][i] if biasDir > 0 else st["bosDn"][i]
        if bosNow:
            bosN += 1
            ending = False

        minorAgainst = (st["sOs"][i] == 0) if biasDir > 0 else (st["sOs"][i] == 1)
        endA = (False if p.endMinor == E_OFF else
                minorAgainst if p.endMinor == E_OPPOSED else
                (st["minorChoch"][i] and minorAgainst))
        endB = p.endSweep and (st["sweepUp"][i] if biasDir > 0
                               else st["sweepDn"][i])
        lastExtX = st["msMaxX"][i] if biasDir > 0 else st["msMinX"][i]
        endC = (p.endStale and lastExtX is not None
                and i - lastExtX >= p.staleBars)
        msMax, msMin = st["msMax"][i], st["msMin"][i]
        msLeg = (msMax - msMin) if (msMax is not None and msMin is not None) else 0.0
        retraced = 0.0
        if msLeg > 0:
            retraced = ((msMax - cs[i].c) / msLeg if biasDir > 0
                        else (cs[i].c - msMin) / msLeg)
        endD = p.retraceMax > 0 and retraced >= p.retraceMax / 100.0
        endE = p.adxMin > 0 and adx[i] < p.adxMin

        if biasSeen and (endA or endB or endC or endD or endE):
            if not ending:
                endWhy = ("minor" if endA else "sweep" if endB else
                          "stale" if endC else "retrace" if endD else "adx")
            ending = True

        dirs.append(biasDir)
        ok.append(biasSeen and not ending)
        whys.append(endWhy)
        states.append("none" if not biasSeen else "ending" if ending
                      else "immature" if bosN == 0 else "running")
    st["endWhy"] = whys
    st["biasState"] = states
    return dirs, ok


# ───────────────────────────────────────────────────── the setup machine ──


def _beyond_up(c, lvl, mode):
    if mode == T_TOUCH:
        return c.c >= lvl
    if mode == T_BODY:
        return min(c.o, c.c) > lvl
    return c.c > lvl


def _beyond_dn(c, lvl, mode):
    if mode == T_TOUCH:
        return c.c <= lvl
    if mode == T_BODY:
        return max(c.o, c.c) < lvl
    return c.c < lvl


def bk_zone(cs, i, short, focus, lo, look, want_ob, want_fvg):
    """The Pine's `bkZone()`. The nearest order block or fair-value gap edge
    between `lo` and `focus`, or None.

    THE NEAR EDGE, ON FIRST TOUCH. A short retracing upward touches the bottom
    of a zone above it, so that is the fill -- and it is the worse of the two
    edges for a short, which makes it the conservative reading. The better
    price needs a deeper retrace that may never come, and assuming it would be
    assuming a fill that did not happen.

    AN ORDER BLOCK NEEDS A CLOSE BEYOND IT, not a wick through. That is the fix
    for the loose OB detection this project already has: a wick through an
    up-candle is noise, a close beyond it is a decision.
    """
    best, why = None, ""
    first = max(1, i - look)

    def better(e):
        return best is None or (e < best if short else e > best)

    def in_range(e):
        return (lo < e < focus) if short else (focus < e < lo)

    for b in range(i - 1, first - 1, -1):
        c = cs[b]
        if want_ob:
            is_opp = c.c > c.o if short else c.c < c.o
            if is_opp:
                disp = any((cs[j].c < c.l) if short else (cs[j].c > c.h)
                           for j in range(b + 1, i + 1))
                if disp:
                    edge = c.l if short else c.h
                    if in_range(edge) and better(edge):
                        best, why = edge, "OB"
        if want_fvg and 1 <= b < i:
            # PINE INDICES RUN BACKWARDS AND THIS IS WHERE THAT BITES. In the
            # Pine `high[b - 1]` is the bar AFTER b; here `cs[b - 1]` is the
            # bar BEFORE it. Getting that the wrong way round produced a
            # detector that found zero fair-value gaps while reporting the
            # feature as on, which is the quietest possible failure -- the
            # backup still worked, on order blocks alone, and nothing said so.
            #   bearish gap (a short):  high[newer] < low[older]
            #   bullish gap (a long):   low[newer]  > high[older]
            newer, older = cs[b + 1], cs[b - 1]
            edge = newer.h if short else newer.l
            far = older.l if short else older.h
            if (edge < far) if short else (edge > far):
                if in_range(edge) and better(edge):
                    best, why = edge, "FVG"
    return best, why


@dataclass(eq=False)
class _Cand:
    bar: int
    hi: float
    lo: float
    focus: float
    workHi: bool
    short: bool
    pbExt: float
    state: str
    code: str
    workOk: bool = False
    failOk: bool = False
    armed: bool = False
    armBar: int = -1
    stop: float = 0.0
    target: float = 0.0
    ghost: bool = False
    bkPx: float = 0.0
    bkWhy: str = ""
    ran: bool = False


def run(cs, p: P = P(), symbol: str = "") -> Result:
    """Sections 6 and 7, and the scoring the Pine's panel does.

    One pass over the bars. The loop below is the Pine's loop in the Pine's
    order, including the two orderings that were found the hard way on real
    charts and are load-bearing:

      * `target reached before the fill` is tested BEFORE the fill, because the
        bar that comes back to the entry is often the same bar returning FROM
        the target, and scoring that as a win is how the chart printed a clean
        2R over a trade that collapsed.
      * the stop is tested BEFORE the touch, so a bar spanning both counts as
        the loss.
    """
    res = Result(symbol=symbol, bars=len(cs))
    if len(cs) < 60:
        return res
    st, atr = structure(cs, p)
    dirs, tradeable = bias(cs, st, p)
    hD, hK = htf_dir(cs, p) if p.htfMult > 1 else ([0] * len(cs), [True] * len(cs))

    cands: list[_Cand] = []
    live: list[Trade] = []
    pbExt = None
    pbExtX = None

    for i, c in enumerate(cs):
        biasDir = dirs[i]
        atrBuf = p.stopBuf * atr[i]

        # ── the pullback, section 6 ─────────────────────────────────────────
        prevDir = dirs[i - 1] if i else biasDir
        prevMaxX = st["msMaxX"][i - 1] if i else st["msMaxX"][i]
        prevMinX = st["msMinX"][i - 1] if i else st["msMinX"][i]
        pbReset = (biasDir != prevDir
                   or (biasDir < 0 and st["msMinX"][i] != prevMinX)
                   or (biasDir > 0 and st["msMaxX"][i] != prevMaxX))
        if pbReset or pbExt is None:
            pbExt = c.h if biasDir < 0 else c.l
            pbExtX = i
        elif biasDir < 0 and c.h >= pbExt:
            pbExt, pbExtX = c.h, i
        elif biasDir > 0 and c.l <= pbExt:
            pbExt, pbExtX = c.l, i

        # ── every candidate, oldest last so removal is safe ─────────────────
        for cd in list(cands):
            gone = False
            filled = False
            if not tradeable[i] and not cd.ghost:
                if cd.armed:
                    res.nMissBias += 1
                    w = st["endWhy"][i]
                    if w == "minor":
                        res.nEndMinor += 1
                    elif w == "sweep":
                        res.nEndSweep += 1
                    elif w == "stale":
                        res.nEndStale += 1
                    elif w == "retrace":
                        res.nEndRetr += 1
                    elif w == "adx":
                        res.nEndAdx += 1
                    cd.ghost = True
                else:
                    gone = True

            if not gone and not cd.armed:
                if cd.short and c.h > cd.pbExt:
                    cd.pbExt = c.h
                if not cd.short and c.l < cd.pbExt:
                    cd.pbExt = c.l
                wHit = (_beyond_up(c, cd.hi, p.workTest) if cd.workHi
                        else _beyond_dn(c, cd.lo, p.workTest))
                fHit = (_beyond_dn(c, cd.lo, p.failTest) if cd.workHi
                        else _beyond_up(c, cd.hi, p.failTest))
                if wHit:
                    cd.workOk = True
                if fHit:
                    cd.failOk = True
                if cd.workOk and cd.failOk:
                    sw = st["sTopY"][i] if cd.short else st["sBtmY"][i]
                    base = ((cd.hi if cd.short else cd.lo) if p.stopSrc == S_PIN
                            else cd.pbExt if p.stopSrc == S_PULL
                            else sw)
                    if base is None:
                        gone = True
                    else:
                        stp = base + atrBuf if cd.short else base - atrBuf
                        risk = abs(stp - cd.focus)
                        sane = risk > 0 and (stp > cd.focus if cd.short
                                             else stp < cd.focus)
                        if sane:
                            cd.armed = True
                            cd.armBar = i
                            cd.stop = stp
                            cd.target = (cd.focus - p.rr * risk if cd.short
                                         else cd.focus + p.rr * risk)
                            res.nArmed += 1
                            res.armed.append(dict(
                                bar=i, symbol=symbol, short=cd.short,
                                entry=cd.focus, stop=cd.stop,
                                target=cd.target, code=cd.code,
                                state=cd.state, pin=cd.bar))
                        else:
                            gone = True
                elif i - cd.bar >= p.confirmBars:
                    gone = True

            if not gone and cd.armed and p.stopTrack and p.stopSrc == S_PULL:
                deeper = c.h > cd.pbExt if cd.short else c.l < cd.pbExt
                if deeper:
                    cd.pbExt = c.h if cd.short else c.l
                    cd.stop = (cd.pbExt + atrBuf if cd.short
                               else cd.pbExt - atrBuf)
                    rk2 = abs(cd.stop - cd.focus)
                    cd.target = (cd.focus - p.rr * rk2 if cd.short
                                 else cd.focus + p.rr * rk2)

            # ── the backup arms, ONCE ───────────────────────────────────
            # Re-scanning every bar would keep finding a nearer zone and would
            # converge on "enter at the current price", which is not a backup.
            if p.useBackup and not gone and cd.armed and not cd.ran:
                risk0 = abs(cd.stop - cd.focus)
                ranR = 0.0
                if risk0 > 0:
                    ranR = ((cd.focus - c.l) / risk0 if cd.short
                            else (c.h - cd.focus) / risk0)
                if ranR >= p.bkTrigger:
                    cd.ran = True
                    px, why = bk_zone(cs, i, cd.short, cd.focus,
                                      c.l if cd.short else c.h,
                                      p.bkLook, p.useOB, p.useFVG)
                    if px is not None:
                        rk = abs(cd.stop - px)
                        if 0 < rk <= p.bkMaxRisk * risk0:
                            cd.bkPx, cd.bkWhy = px, why

            if not gone and cd.armed and i > cd.armBar:
                tgtGone = c.l <= cd.target if cd.short else c.h >= cd.target
                stopHit = c.h >= cd.stop if cd.short else c.l <= cd.stop
                # The nearer level, so price reaches it first, and for a short
                # the worse price. Checked before the Focus for both reasons.
                bkHit = bool(cd.bkWhy) and c.h >= cd.bkPx >= c.l
                touched = c.h >= cd.focus >= c.l
                if tgtGone:
                    if not cd.ghost:
                        res.nMissGone += 1
                    gone = True
                elif stopHit:
                    if not cd.ghost:
                        res.nMissStop += 1
                    gone = True
                elif bkHit or touched:
                    if bkHit:
                        # Re-based onto the zone: same stop, bigger risk, and a
                        # target recomputed from it -- or `rr` would quietly
                        # stop meaning rr.
                        cd.focus = cd.bkPx
                        rk3 = abs(cd.stop - cd.focus)
                        cd.target = (cd.focus - p.rr * rk3 if cd.short
                                     else cd.focus + p.rr * rk3)
                        if not cd.ghost:
                            res.nBackup += 1
                    if not cd.ghost:
                        res.nFilled += 1
                    filled = True
                    live.append(Trade(
                        symbol=symbol, bar=cd.bar, armBar=cd.armBar, fillBar=i,
                        short=cd.short, entry=cd.focus, stop=cd.stop,
                        target=cd.target, ghost=cd.ghost, state=cd.state,
                        code=cd.code, backup=cd.bkWhy))
                    gone = True
                elif i - cd.armBar >= p.fillBars:
                    if not cd.ghost:
                        res.nMissBack += 1
                    gone = True
            if gone or filled:
                cands.remove(cd)

        # ── filled trades, walked to their target or their stop ─────────────
        # AFTER the candidate loop, as in the Pine, so a setup filled on this
        # bar is checked for its outcome on this bar too. A limit filled
        # intrabar really was exposed to the rest of that bar. Stop first: when
        # one bar spans both levels the order is unknowable, so it is the loss.
        for t in list(live):
            lost = c.h >= t.stop if t.short else c.l <= t.stop
            won = c.l <= t.target if t.short else c.h >= t.target
            if lost or won:
                t.won = bool(won and not lost)
                t.exitBar = i
                risk = abs(t.stop - t.entry)
                gross = p.rr if t.won else -1.0
                # The round trip in R. A wider stop is a smaller cost in R,
                # which is the whole reason this is not a flat number.
                cost = (p.feeFrac * t.entry / risk) if risk > 0 else 0.0
                t.r = gross - cost
                res.trades.append(t)
                live.remove(t)

        # ── a new pin, section 6 tests ──────────────────────────────────────
        rng = c.h - c.l
        upW = (c.h - max(c.o, c.c)) / rng if rng > 0 else 0.0
        dnW = (min(c.o, c.c) - c.l) / rng if rng > 0 else 0.0
        isGreen = c.c >= c.o
        famHam = dnW - upW >= p.wickEdge
        famStar = upW - dnW >= p.wickEdge
        # THE THREE GATES, each independently removable. See `useFamily` and
        # `useColour` in P: turning one off does not change what the machine
        # then does with the bar, only whether the bar is admitted -- which is
        # what makes the difference between two arms attributable to the gate.
        #
        # `famHam` still decides which line is Working even when the family
        # test is OFF, because the machine needs the answer either way. With
        # the test off it degenerates to "whichever wick is longer", ties going
        # to the hammer reading. That is a fallback, not a finding.
        famOk = True if not p.useFamily else (
            (famHam and p.useHammer) or (famStar and p.useStar))
        colourOk = True if not p.useColour else (
            isGreen if biasDir < 0 else not isGreen)
        locOk = (i - pbExtX) <= p.locTol
        # The HTF gate. A base-timeframe setup may only be taken when the
        # higher timeframe agrees on direction AND is itself tradeable. Off
        # when htfMult is 0, and then it is not counted either.
        htfOk = True
        if p.htfMult > 1:
            htfOk = hK[i] and hD[i] == biasDir

        if famOk:
            res.nRaw += 1
        if famOk and tradeable[i]:
            res.nPins += 1
            if colourOk:
                res.nColour += 1
                if locOk:
                    res.nLoc += 1
                    if not htfOk:
                        res.nHtf += 1
        if famOk and tradeable[i] and colourOk and locOk and htfOk:
            if len([x for x in cands if not x.ghost]) >= p.maxLive:
                res.nCap += 1
            else:
                cands.append(_Cand(
                    bar=i, hi=c.h, lo=c.l, focus=c.o, workHi=famHam,
                    short=biasDir < 0, pbExt=pbExt,
                    state=st["biasState"][i],
                    code=("HAM" if isGreen else "HGM") if famHam
                    else ("IH" if isGreen else "SS")))

    # Trades still open at the end of the data have not had their window.
    # Counting them as anything would score an unfinished trade at whatever
    # price the fetch happened to stop on, which is noise dressed as an
    # outcome -- the same rule research/data.py applies.
    return res
