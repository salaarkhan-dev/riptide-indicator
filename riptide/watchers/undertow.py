"""Riptide Undertow — a limit-order heads-up across the whole MEXC universe.

WHAT THIS SOLVES. Undertow is a chart indicator, and reading it means watching
one symbol wait for a pin, then wait for a close beyond the pin's high, then
wait for a close beyond its low, then place a limit and wait again. That is
hours of screen time per symbol, and nobody can do it for twenty-three of them.
This fires one message the moment a setup ARMS — both confirmations landed, the
limit would go on now — with the three levels and a link to the chart.

WHAT AN ALERT MEANS, EXACTLY, and it is worth being precise because this is the
one watch in the repository that prints prices:

    a counter-trend pin was found at the pullback extreme, price has since
    CLOSED beyond both of its extremes in some order inside the confirm
    window, and a sane stop exists.

That is the arming bar. Nothing has filled, nothing is a position, and the
setup can still die four ways before it does — the bias can turn, price can
reach the target without you, price can take the stop first, or it can simply
never come back. Historically about HALF of armed setups never fill at all.

──────────────────────────────────────────────────────────────────────────────
WHY IT PRINTS ENTRY, STOP AND TARGET, when registry.py says a watch may not
carry them.

That rule exists so a watch cannot arm an outcome row, reach /stats, or wear
the authority of a measured alert. None of that changes here: this indicator
creates no outcome row, its hits never touch `tracker`, and `/stats` cannot see
it — `riptide/watch.py` enforces that for every indicator and this one could
not opt out if it tried.

What the rule cannot do is make the message useful without the focus line. The
whole point of the alert is "your limit goes at this price, now"; a heads-up
that says "go look at ETH" when the actionable moment has already arrived is a
worse product than no alert. So the three numbers are in the ROW TEXT, as
information about the chart being pointed at, and the caveat under every digest
says what they are not. That is a deliberate widening of the rule, in a diff,
with the reason written here rather than discovered later.

──────────────────────────────────────────────────────────────────────────────
THE EVIDENCE, AND IT IS NEGATIVE. THREE PRE-REGISTERED STUDIES.

    indicators/undertow/measurements/UNDERTOW_PARAMS.md
        48 configs, 23 symbols, 15m/30m/1h, chosen on one half and scored on a
        holdout sharing neither symbols nor calendar: -0.093, +0.071, -0.063 R
        per trade. It lost to a seeded random entry of the same shape on two of
        three, and on 1h the two were -0.063 against -0.064.

    indicators/undertow/measurements/UNDERTOW_PIN_VALUE.md
        the candle taxonomy adds nothing. Full rule minus location-only is
        -0.073 / -0.049 / +0.092 R, inside the noise everywhere, and on two of
        three the arm with NO candle test scored higher.

    indicators/undertow/measurements/UNDERTOW_EXITS.md
        the one that matters most here. 8-12% of these setups DO reach 7R and
        the average trade's best price is +2.5 R -- the big winners are real.
        But a fixed-R exit breaks even at a hit rate of 1/(1+R), which is also
        what a coin gives, and the measured hit rates sit within a point or two
        of it at every target and get WORSE as R grows:

            target   coin    Undertow
               2R   33.3%       34.1%
               3R   25.0%       25.1%
               7R   12.5%        9.8%

SO WHY SHIP IT AT ALL. Because one explanation survives all three and no
backtest can reach it: SELECTION. Roughly ten discretionary trades a week
against twelve thousand mechanical ones. The tail is real and the mechanical
base rate is chance, which is exactly the shape of a market where choosing
which one in ten to take is the whole skill — and also exactly the shape of a
market where nobody can.

Historical bars cannot tell those apart. A PROSPECTIVE RECORD can: alerts fired
forward in real time, taken or skipped by a human, outcomes written down. This
watch is that instrument. It ships OFF, it says all of the above in its caveat
and in /undertow, and it makes no claim it has not earned.

──────────────────────────────────────────────────────────────────────────────
A PORT OF A PORT, AND DELIBERATELY SO. indicators/undertow/port/undertow.py
already holds this machine and the studies ran on it, but the research tree
must never be importable from a live scanner -- it pulls in the whole study
stack, and a refactor there must not be able to break a running bot. So the
machine is here too, and indicators/undertow/tests/test_watch_undertow.py runs
BOTH over the same candles and asserts they produce THE SAME ARMED SETUPS, bar
for bar and price for price. A drift fails rather than hides.

This copy stops at the arming bar. It has no fill, no outcome, no ghost column
and no scoring, because a watch has none of those and carrying them would be
carrying a trading path into the bot package.

IT ALSO HAS NO BACKUP FILL, and that is not an omission. The OB/FVG backup only
comes into existence once the move has run without you, which is minutes to
hours AFTER the alert this watch sends. Alerting on it would be a second,
later message about the same setup; the machinery for that is the port's and it
is not measured yet. For now the alert is the limit at the Focus line, and the
backup is something you place yourself if you miss it.

NO EXCHANGE API KEY AND NO ORDER PLACEMENT. This sends a Telegram message.
"""

from __future__ import annotations

import math

from collections import deque

from ..config import (BAR_SECONDS, UNDERTOW_ALERTS, UNDERTOW_CONFIRM_BARS,
                      UNDERTOW_FRESH_BARS, UNDERTOW_INTERVALS,
                      UNDERTOW_MAX_LINES, UNDERTOW_MS_LEN, UNDERTOW_STATES)
from .registry import Hit, Indicator, Option, register

RECENT_BARS = 6

# Frozen from the Pine's defaults and NOT exposed as chat settings. Every one
# of these was measured at no edge, so offering them as knobs would invite
# tuning against a live stream, which is the worst possible place to tune.
# indicators/undertow/port/undertow.py::P is the authority; the two are held
# together by test_watch_undertow.py.
MS_SHORT_LEN = 2
BOS_NEEDS_IDM = True
END_MINOR = "on the flip"
END_SWEEP = False
END_STALE = False
STALE_BARS = 30
RETRACE_MAX = 70
WICK_EDGE = 0.05
LOC_TOL = 0
STOP_BUF = 0.25
RR = 3.5


def _dp(ref: float) -> int:
    """Decimal places of a price that was actually TRADED.

    The entry is a candle's open, so it sits on the exchange's tick grid and
    its own precision is the best available read of that grid — no symbol
    metadata, no extra request. The stop and the target are COMPUTED (an ATR
    fraction past an extreme), so they carry float noise well past any real
    tick: an entry of 0.1985 printed beside a stop of 0.19694503 is eight
    figures of a number whose last four cannot be placed.
    """
    t = f"{ref:.8g}"
    return len(t.split(".")[1]) if "." in t and "e" not in t else 0


def _snap(v: float, entry: float, away: bool) -> float:
    """Round a level onto the entry's grid, AWAY from the entry.

    Away, not nearest, and in both directions: a stop rounded toward the entry
    is a tighter stop than the one that was measured, and a target rounded
    toward it is an easier one. Both would make the row flatter than the trade.
    Rounding outward costs a fraction of a tick and cannot overstate anything.
    """
    n = _dp(entry)
    q = 10.0 ** n
    return (math.floor(v * q) / q if v < entry else math.ceil(v * q) / q) \
        if away else round(v, n)


def sig_of(symbol: str, tf: str, bar_time: int, is_long: bool) -> str:
    """The dedupe signature. One armed setup per symbol / tf / arming bar /
    side — stable across restarts, or every restart replays the chat."""
    return f"UT|{symbol}|{tf}|{bar_time}|{'U' if is_long else 'D'}"


# ─────────────────────────────────────────────────── the machine, copied ──


def _roll(vals, L, cmp):
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


def _swings(cs, msL):
    """msSwings() from riptide-indicator-v2.pine section 12."""
    n = len(cs)
    highs, lows = [c.h for c in cs], [c.l for c in cs]
    hh = _roll(highs, msL, lambda a, b: a <= b)
    ll = _roll(lows, msL, lambda a, b: a >= b)
    sOs = 0
    tops, btms = [], []
    for i in range(n):
        was = sOs
        if i >= msL:
            if highs[i - msL] > hh[i]:
                sOs = 0
            elif lows[i - msL] < ll[i]:
                sOs = 1
            else:
                sOs = was
        tops.append(highs[i - msL] if (i >= msL and sOs == 0 and was != 0)
                    else None)
        btms.append(lows[i - msL] if (i >= msL and sOs == 1 and was != 1)
                    else None)
    return tops, btms


def _rma(values, length):
    out, acc = [], 0.0
    for i, v in enumerate(values):
        if i < length:
            acc += v
            out.append(acc / (i + 1))
        else:
            out.append((out[-1] * (length - 1) + v) / length)
    return out


def _atr(cs, length=14):
    tr = []
    for i, c in enumerate(cs):
        tr.append(c.h - c.l if i == 0 else
                  max(c.h - c.l, abs(c.h - cs[i - 1].c), abs(c.l - cs[i - 1].c)))
    return _rma(tr, length)


class _Cand:
    __slots__ = ("bar", "hi", "lo", "focus", "workHi", "short", "pbExt",
                 "state", "code", "workOk", "failOk")

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k, False))


def armed_setups(cs, ms_len: int = 6, max_live: int = 64) -> list:
    """Every bar at which a limit order would have gone on.

    Sections 3-7 of riptide-undertow.pine, stopping at the arming bar. The
    structure engine, the minor structure, the bias state machine, the
    pullback, the pin and the two confirmations, in the Pine's order — which is
    load-bearing, because the trailing extremes are updated AFTER the BOS and
    sweep tests read them.
    """
    n = len(cs)
    if n < 60:
        return []
    atr = _atr(cs, 14)
    msTop, msBtm = _swings(cs, ms_len)
    msSTop, msSBtm = _swings(cs, MS_SHORT_LEN)

    msOs = 0
    msTopCrossed = msBtmCrossed = False
    msMax = msMin = msMaxX = msMinX = None
    msTopY = msBtmY = None
    msSTopCrossed = msSBtmCrossed = False
    msSTopY = msSBtmY = None
    msSOs = 0
    msSTopXd = msSBtmXd = False
    msSTopLvl = msSBtmLvl = None

    biasSeen = False
    ending = False
    bosN = 0
    pbExt = pbExtX = None
    cands: list = []
    out: list = []

    def gt(a, b):
        return a is not None and b is not None and a > b

    def lt(a, b):
        return a is not None and b is not None and a < b

    for i in range(n):
        c = cs[i]
        msOsPrev = msOs
        msMaxPrev, msMinPrev = msMax, msMin
        prevMaxX, prevMinX = msMaxX, msMinX

        if msTop[i] is not None:
            msTopY, msTopCrossed = msTop[i], False
        if msBtm[i] is not None:
            msBtmY, msBtmCrossed = msBtm[i], False
        if gt(c.c, msTopY) and not msTopCrossed:
            msOs, msTopCrossed = 1, True
        if lt(c.c, msBtmY) and not msBtmCrossed:
            msOs, msBtmCrossed = 0, True

        msChoch = msOs != msOsPrev
        if msChoch:
            msMax, msMin = c.h, c.l
            msMaxX = msMinX = i
            msSTopCrossed = msSBtmCrossed = False

        if msSTop[i] is not None:
            msSTopY = msSTop[i]
        if msSBtm[i] is not None:
            msSBtmY = msSBtm[i]

        if (lt(c.l, msSBtmY) and not msSBtmCrossed and msOs == 1
                and msSBtmY != msBtmY):
            msSBtmCrossed = True
        msBosUp = (gt(c.c, msMax) and (not BOS_NEEDS_IDM or msSBtmCrossed)
                   and msOs == 1)
        if msBosUp:
            msSBtmCrossed = False
        if (gt(c.h, msSTopY) and not msSTopCrossed and msOs == 0
                and msSTopY != msTopY):
            msSTopCrossed = True
        msBosDn = (lt(c.c, msMin) and (not BOS_NEEDS_IDM or msSTopCrossed)
                   and msOs == 0)
        if msBosDn:
            msSTopCrossed = False

        msSweepUp = (gt(c.h, msMax) and lt(c.c, msMax) and msOs == 1
                     and msMaxX is not None and i - msMaxX > 1)
        msSweepDn = (lt(c.l, msMin) and gt(c.c, msMin) and msOs == 0
                     and msMinX is not None and i - msMinX > 1)

        msSOsPrev = msSOs
        if msSTop[i] is not None:
            msSTopLvl, msSTopXd = msSTop[i], False
        if msSBtm[i] is not None:
            msSBtmLvl, msSBtmXd = msSBtm[i], False
        if gt(c.c, msSTopLvl) and not msSTopXd:
            msSOs, msSTopXd = 1, True
        if lt(c.c, msSBtmLvl) and not msSBtmXd:
            msSOs, msSBtmXd = 0, True
        msMinorChoch = msSOs != msSOsPrev

        # Trailing extremes, AFTER the tests above read them.
        msMax = c.h if msMax is None else max(c.h, msMax)
        msMin = c.l if msMin is None else min(c.l, msMin)
        if msMaxPrev is None or msMax > msMaxPrev:
            msMaxX = i
        if msMinPrev is None or msMin < msMinPrev:
            msMinX = i

        # ── bias ────────────────────────────────────────────────────────────
        if msChoch:
            biasSeen, bosN, ending = True, 0, False
        biasDir = 1 if msOs == 1 else -1
        if (msBosUp if biasDir > 0 else msBosDn):
            bosN += 1
            ending = False
        minorAgainst = (msSOs == 0) if biasDir > 0 else (msSOs == 1)
        endA = (msMinorChoch and minorAgainst) if END_MINOR == "on the flip" \
            else (minorAgainst if END_MINOR == "while opposed" else False)
        endB = END_SWEEP and (msSweepUp if biasDir > 0 else msSweepDn)
        lastExtX = msMaxX if biasDir > 0 else msMinX
        endC = (END_STALE and lastExtX is not None
                and i - lastExtX >= STALE_BARS)
        leg = (msMax - msMin) if (msMax is not None and msMin is not None) else 0.0
        retraced = 0.0
        if leg > 0:
            retraced = ((msMax - c.c) / leg if biasDir > 0
                        else (c.c - msMin) / leg)
        endD = RETRACE_MAX > 0 and retraced >= RETRACE_MAX / 100.0
        if biasSeen and (endA or endB or endC or endD):
            ending = True
        tradeable = biasSeen and not ending
        state = ("none" if not biasSeen else "ending" if ending
                 else "immature" if bosN == 0 else "running")

        # ── the pullback ────────────────────────────────────────────────────
        pbReset = (biasDir != (1 if msOsPrev == 1 else -1)
                   or (biasDir < 0 and msMinX != prevMinX)
                   or (biasDir > 0 and msMaxX != prevMaxX))
        if pbReset or pbExt is None:
            pbExt, pbExtX = (c.h if biasDir < 0 else c.l), i
        elif biasDir < 0 and c.h >= pbExt:
            pbExt, pbExtX = c.h, i
        elif biasDir > 0 and c.l <= pbExt:
            pbExt, pbExtX = c.l, i

        atrBuf = STOP_BUF * atr[i]

        # ── candidates ──────────────────────────────────────────────────────
        for cd in list(cands):
            if not tradeable:
                cands.remove(cd)
                continue
            if cd.short and c.h > cd.pbExt:
                cd.pbExt = c.h
            if not cd.short and c.l < cd.pbExt:
                cd.pbExt = c.l
            wHit = (c.c > cd.hi) if cd.workHi else (c.c < cd.lo)
            fHit = (c.c < cd.lo) if cd.workHi else (c.c > cd.hi)
            if wHit:
                cd.workOk = True
            if fHit:
                cd.failOk = True
            if cd.workOk and cd.failOk:
                base = cd.pbExt
                stop = base + atrBuf if cd.short else base - atrBuf
                risk = abs(stop - cd.focus)
                if risk > 0 and ((stop > cd.focus) if cd.short
                                 else (stop < cd.focus)):
                    out.append(dict(
                        bar=i, short=cd.short, entry=cd.focus, stop=stop,
                        target=(cd.focus - RR * risk if cd.short
                                else cd.focus + RR * risk),
                        code=cd.code, state=cd.state, pin=cd.bar))
                cands.remove(cd)
            elif i - cd.bar >= UNDERTOW_CONFIRM_BARS:
                cands.remove(cd)

        # ── a new pin ───────────────────────────────────────────────────────
        rng = c.h - c.l
        upW = (c.h - max(c.o, c.c)) / rng if rng > 0 else 0.0
        dnW = (min(c.o, c.c) - c.l) / rng if rng > 0 else 0.0
        isGreen = c.c >= c.o
        famHam = dnW - upW >= WICK_EDGE
        famStar = upW - dnW >= WICK_EDGE
        colourOk = isGreen if biasDir < 0 else not isGreen
        if ((famHam or famStar) and tradeable and colourOk
                and (i - pbExtX) <= LOC_TOL and len(cands) < max_live):
            cands.append(_Cand(
                bar=i, hi=c.h, lo=c.l, focus=c.o, workHi=famHam,
                short=biasDir < 0, pbExt=pbExt, state=state,
                code=("HAM" if isGreen else "HGM") if famHam
                else ("IH" if isGreen else "SS")))
    return out


# ───────────────────────────────────────────────────────── the indicator ──


def detect(cs, symbol: str, tf: str, opts: dict) -> tuple:
    """Setups that armed in the last RECENT_BARS bars, and how many this
    indicator's own gates threw away.

    The drop count is what lets /status tell "6 setups, all immature" from "the
    loop never woke". Both look like silence from the chat.
    """
    want = opts.get("states", UNDERTOW_STATES)
    ms_len = int(opts.get("swing", UNDERTOW_MS_LEN))
    step = BAR_SECONDS[tf]
    cut = len(cs) - RECENT_BARS
    out, dropped = [], 0
    for a in armed_setups(cs, ms_len=ms_len):
        if a["bar"] < cut:
            continue
        if want != "both" and a["state"] != want:
            dropped += 1
            continue
        # Snapped BEFORE the risk is computed, so every number on the row
        # agrees with every other one. riptide/telegram.py::fmt carries the
        # lesson: a displayed percentage that disagrees with the displayed
        # prices puts the order in the wrong place.
        stop = _snap(a["stop"], a["entry"], True)
        target = _snap(a["target"], a["entry"], True)
        risk = abs(stop - a["entry"])
        if risk <= 0:
            dropped += 1
            continue
        out.append(Hit(
            key=sig_of(symbol, tf, cs[a["bar"]].t, not a["short"]),
            symbol=symbol, tf=tf, is_long=not a["short"],
            # Candle.t is the bar's OPEN and a setup only arms once the bar has
            # CLOSED, so the moment it became real is t + step. That is what
            # the freshness gate and the "Nm ago" both measure from.
            bar_time=cs[a["bar"]].t + step, price=a["entry"],
            detail=(f"{a['code']} {a['state']} entry {a['entry']:g} "
                    f"stop {stop:g} tgt {target:g}"),
            entry=a["entry"], stop=stop, target=target,
            code=a["code"], state=a["state"],
            riskPct=100.0 * risk / a["entry"] if a["entry"] else 0.0))
    return out, dropped


_GROUPS = {(True, "running"): (0, "LONG · running"),
           (False, "running"): (1, "SHORT · running"),
           (True, "immature"): (2, "long · immature"),
           (False, "immature"): (3, "short · immature")}


def classify(h) -> tuple:
    rank, name = _GROUPS.get((h.is_long, h.extra["state"]),
                             (4, "other"))
    return (rank, -BAR_SECONDS[h.tf], h.symbol), name


GROUP_W = 16


def row(h, group: str) -> str:
    """One armed setup. The levels are the product — see the module docstring
    for why a watch prints them and what that still does not make them.

    `watch.chart` already renders the price, and `Hit.price` IS the limit, so
    the entry is NOT repeated here. The first version printed it twice, which
    is worse than either choice: two numbers that are always equal read as two
    different levels until you check.

    tg.fmt, not `:g`. A raw float prints 0.0246017 next to 0.027424 and the
    columns stop lining up at exactly the moment a reader is comparing a stop
    to an entry — which is the only thing this row is for.
    """
    from .. import telegram as tg
    from .. import watch
    e = h.extra
    return (watch.label(SPEC, group) + watch.chart(h)
            + f"  <i>sl {tg.fmt(e['stop'])} · tp {tg.fmt(e['target'])}"
            f" · {e['riskPct']:.2f}% · {e['code']}</i>")


def rate(db, tfs=None, **over):
    """Armed setups a day across the universe.

    NOT A GUESS. Measured over the same 23 symbols x 12,000 bars the studies
    used, in indicators/undertow/studies/undertow_rate.py. Rerun it rather than
    trusting this table -- the exhaustion watch's equivalent was written from
    memory once, was wrong in every file that quoted it, and needed a study to
    find out.
    """
    want = over.get("states", UNDERTOW_STATES)
    per = RATE_BOTH if want == "both" else RATE_ONE.get(want, RATE_BOTH)
    return sum(per.get(t, 0) for t in (tfs or UNDERTOW_INTERVALS))


# Armed setups a day across 23 symbols, from undertow_rate.py over 125 / 250
# symbol-days, AT THE SHIPPED CONFIG -- swing 6/2 with the sweep and stale
# Ending rules off.
#
# THAT CONFIG TRIPLES THE RATE. The same measurement at swing 15 with those two
# rules on was 11 and 5; a shorter swing means a twitchier structure and more
# CHoCHs, and turning off two of the five Ending rules leaves far more bars
# tradeable. 15m + 30m together is 54 rows a day, which is the point at which a
# digest starts not getting read.
#
#     swing   15m both   15m running   30m both   30m running
#       6         36          18           18          9
#      15         22          16           10          7
#      30         16          13            8          6
#
# `/undertow running` halves it to 27 and is the first thing to reach for.
# 1h is not shipped: it is not in the default intervals.
RATE_BOTH = {"Min15": 36, "Min30": 18, "Min60": 9}
RATE_ONE = {
    "running": {"Min15": 18, "Min30": 9, "Min60": 5},
    "immature": {"Min15": 17, "Min30": 9, "Min60": 4},
}


SPEC = register(Indicator(
    name="undertow",
    title="UNDERTOW",
    glyph="🌊",
    unit="setup",
    caveat=("a limit level to go look at, not a trade — three pre-registered "
            "studies measured no edge, and it lost to a random entry. About "
            "half of these never fill."),
    detect=detect,
    row=row,
    classify=classify,
    min_bars=200,
    recent_bars=RECENT_BARS,
    fresh_bars=UNDERTOW_FRESH_BARS,
    max_lines=UNDERTOW_MAX_LINES,
    label_w=GROUP_W,
    default_enabled=UNDERTOW_ALERTS,
    default_intervals=tuple(UNDERTOW_INTERVALS),
    fallback_interval="Min60",
    options=(
        Option("states", "choice", UNDERTOW_STATES,
               "which bias states count. 'running' is the trend that has "
               "already broken structure at least once and is the quieter "
               "half; 'immature' is the fresh CHoCH",
               choices=("both", "running", "immature")),
        Option("swing", "number", UNDERTOW_MS_LEN,
               "the major swing length in BARS. Higher = fewer, larger "
               "trends and far fewer setups. Note this means a different "
               "span of TIME on every timeframe — that is a known flaw, "
               "measured in indicators/undertow/port/swings.py",
               lo=2, hi=100),
    ),
    tf_counted=("Min15", "Min30", "Min60"),
    rate=rate,
    blurb=("<i>Fires the moment a setup ARMS: a counter-trend pin was found "
           "at the pullback extreme, price has since closed beyond BOTH of "
           "its extremes in either order, and a sane stop exists. That is "
           "when the limit order would go on.</i>\n\n"
           "<i>The three numbers are the pin's open (the limit), the stop "
           "past the pullback extreme plus a quarter ATR, and 3R. Nothing "
           "has filled — roughly half of armed setups never do.</i>"),
    evidence=("<b>Three pre-registered studies, all negative.</b> On a holdout "
              "sharing neither symbols nor calendar with the search it scored "
              "−0.093 / +0.071 / −0.063 R per trade on 15m / 30m / 1h, and "
              "LOST to a seeded random entry of the same shape on two of "
              "three. The candle taxonomy adds nothing — removing it scored "
              "higher on two of three. And while 8–12% of these setups really "
              "do reach 7R, a coin flip reaches 7R 12.5% of the time; the "
              "measured hit rate matches chance at every target and gets "
              "worse as the payoff grows.\n\n"
              "<i>It ships anyway, off by default, for one reason: the only "
              "explanation left is whether a human choosing which one in ten "
              "to take beats the machine taking all of them. No backtest can "
              "answer that. A forward record can, and this is the instrument "
              "for building one.</i>"),
    examples=("<code>/undertow on</code> — start them\n"
              "<code>/undertow 30m,1h</code> — which timeframes\n"
              "<code>/undertow running</code> — skip the fresh-CHoCH ones\n"
              "<code>/undertow swing 30</code> — far fewer, larger trends\n"
              "<code>/undertow off</code> — stop them"),
))
