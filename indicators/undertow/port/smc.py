"""LuxAlgo's Smart Money Concepts structure, transcribed.

Asked for because "the swing, and the detection of market structure is better
here". Before transcribing anything, the two engines were compared on real
candles, and the answer is narrower and more useful than it looked.

TWO THINGS ARE ALREADY IDENTICAL, MEASURED ON ETH 15m:

  1. THE SWING DETECTOR. LuxAlgo's

         newLegHigh = high[size] > ta.highest(size)

     expands to `high[i-size] > max(high[i-size+1 .. i])`, and riptide's
     `bar_swings()` computes `highs[i-msL] > max(highs[i-msL+1 .. i])`. They
     are the same expression. Pivot-for-pivot identical at sizes 5, 6, 15 and
     50 -- 300/300, 260/260, 118/119, 36/37.

  2. THE CHoCH. Identical bars at every size tested: 172 of 172, 68 of 68,
     30 of 30. Not "similar" -- the same list.

SO WHAT IS ACTUALLY DIFFERENT IS TWO THINGS:

  1. THE PIVOT LENGTH, and this is the one that shows on a chart. LuxAlgo runs
     the major structure at **50** and the internal at **5**. Undertow runs 6
     and 2. A 50-bar pivot is a different animal from a 6-bar pivot, and that
     -- not the algorithm -- is why one chart looks clean and the other looks
     busy.

  2. THE BOS RULE. LuxAlgo tags any same-direction pivot break as a BOS.
     Undertow's needs an inducement first (`msBosNeedsIdm`) and a break of the
     running extreme. Counts on the same candles: 112 / 65 / 17 against
     53 / 53 / 40 -- and note the ordering inverts with size, so neither is
     uniformly looser.

WHAT THIS MODULE IS. A faithful transcription of the LuxAlgo state machine, so
the second difference can be measured rather than argued about. It reuses
`bar_swings` for the pivots, because that has been proven to be the same
function and a second copy would only be a second thing to drift.

NOTHING HERE IS ENDORSED. It is a bias source to be measured like the six
before it.
"""
from __future__ import annotations

from indicators.undertow.port.swings import bar_swings

BULLISH = 1
BEARISH = -1


def structure(cs, size: int, ref=None):
    """One LuxAlgo structure pass. Returns per-bar lists.

    `ref` is the SWING structure's levels when running the INTERNAL pass, to
    reproduce LuxAlgo's `internalHigh.currentLevel != swingHigh.currentLevel`
    guard -- an internal break that sits exactly on a swing level is the swing
    break, not a second event.

    THE CROSS IS `ta.crossover(close, level)`, which is
    `close > level and close[1] <= level[1]` -- and `level[1]` is the PREVIOUS
    BAR'S level, not the current one. That matters whenever a new pivot lands:
    the comparison is against the level that was in force last bar. Getting it
    wrong would fire a break on the bar a pivot is confirmed, which is a bar
    early and would not repaint only because it is wrong in a consistent
    direction.

    THE `crossed` FLAG IS ONE-SHOT PER PIVOT. A level that has been broken does
    not break again; it takes a new pivot to arm a new break. Without it a
    close oscillating around an old swing high prints a BOS on every bar.
    """
    n = len(cs)
    tops, topxs, btms, btmxs = bar_swings(cs, size)

    hiLvl = loLvl = None
    hiPrev = loPrev = None
    hiCrossed = loCrossed = True
    bias = 0

    out = dict(dir=[0] * n, choch=[False] * n, bos=[False] * n,
               up=[False] * n, dn=[False] * n,
               hiLvl=[None] * n, loLvl=[None] * n,
               hiX=[None] * n, loX=[None] * n)

    for i in range(n):
        if tops[i] is not None:
            hiLvl, hiCrossed = tops[i], False
        if btms[i] is not None:
            loLvl, loCrossed = btms[i], False

        c = cs[i]
        if i > 0:
            # The internal pass ignores a level that IS the swing level.
            okHi = ref is None or ref["hiLvl"][i] != hiLvl
            okLo = ref is None or ref["loLvl"][i] != loLvl
            if (hiLvl is not None and hiPrev is not None and not hiCrossed
                    and okHi and c.c > hiLvl and cs[i - 1].c <= hiPrev):
                out["choch"][i] = bias == BEARISH
                out["bos"][i] = bias != BEARISH
                out["up"][i] = True
                hiCrossed, bias = True, BULLISH
            if (loLvl is not None and loPrev is not None and not loCrossed
                    and okLo and c.c < loLvl and cs[i - 1].c >= loPrev):
                out["choch"][i] = bias == BULLISH
                out["bos"][i] = bias != BULLISH
                out["dn"][i] = True
                loCrossed, bias = True, BEARISH

        hiPrev, loPrev = hiLvl, loLvl
        out["dir"][i] = bias
        out["hiLvl"][i] = hiLvl
        out["loLvl"][i] = loLvl
        out["hiX"][i] = topxs[i]
        out["loX"][i] = btmxs[i]
    return out


def state(cs, p):
    """The LuxAlgo structure dressed as Undertow's per-bar state dict.

    UNLIKE `alt_structure`, THIS HAS REAL BOS EVENTS. The other alternative
    sources have no break of structure to count, so `alt_structure` fakes one
    `matureBars` after a direction flip. This engine emits them, so
    Immature-vs-Running means here what it means for the original structure
    engine: Immature is a CHoCH with no BOS behind it yet.

    `msMax`/`msMin` are the running extremes SINCE THE LAST DIRECTION CHANGE,
    the same as everywhere else, because the pullback and the retrace rule both
    read them and they have to mean one thing.

    Minor structure comes from the INTERNAL pass, which is what the 1CP layer
    is meant to read: the major character says which way, the minor character
    says where the pullback is turning.
    """
    n = len(cs)
    maj = structure(cs, p.smcSwingLen)
    mnr = structure(cs, p.smcInternalLen, ref=maj)

    out = dict(os=[], choch=[], bosUp=[], bosDn=[], sweepUp=[], sweepDn=[],
               msMax=[], msMin=[], msMaxX=[], msMinX=[], sOs=[],
               minorChoch=[], sTopY=[], sBtmY=[], mixed=[False] * n)
    mx = mn = None
    mxX = mnX = 0
    for i in range(n):
        c = cs[i]
        d = maj["dir"][i] or BULLISH
        flip = i > 0 and maj["dir"][i] != maj["dir"][i - 1]
        if flip or mx is None:
            mx, mn, mxX, mnX = c.h, c.l, i, i
        else:
            if c.h > mx:
                mx, mxX = c.h, i
            if c.l < mn:
                mn, mnX = c.l, i
        out["os"].append(1 if d > 0 else 0)
        out["choch"].append(maj["choch"][i])
        out["bosUp"].append(maj["bos"][i] and maj["up"][i])
        out["bosDn"].append(maj["bos"][i] and maj["dn"][i])
        # No sweep concept in this engine. Stated, not faked -- a fabricated
        # sweep would make the Ending rules look comparable while not being.
        out["sweepUp"].append(False)
        out["sweepDn"].append(False)
        out["sOs"].append(1 if (mnr["dir"][i] or BULLISH) > 0 else 0)
        out["minorChoch"].append(mnr["choch"][i])
        out["sTopY"].append(mnr["hiLvl"][i])
        out["sBtmY"].append(mnr["loLvl"][i])
        out["msMax"].append(mx)
        out["msMin"].append(mn)
        out["msMaxX"].append(mxX)
        out["msMinX"].append(mnX)
    return out
