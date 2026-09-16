"""Why does section 12 draw so few BOS and CHoCH?

A DIAGNOSTIC, not a study. It counts events; it scores nothing, so there is no
outcome, no control and no prereg — and no claim that more marks are better
marks is made or implied anywhere in it.

Two questions, one table each:

  1. How much does `msLen` change the yield? It is the CHoCH detection period
     and the ported script shipped it at 50, which on a 15m chart is 12.5
     hours of structure.

  2. How many BOS does the INDUCEMENT PREREQUISITE suppress? Section 12 fires
     a BOS only when msSBtmCrossed / msSTopCrossed is true, and those are set
     only by the IDM block, which itself requires `msSBtmY != msBtmY`. So the
     real chain is CHoCH -> IDM -> BOS, and a break of the running extreme
     with no inducement before it is never labelled.

The engine loop below is a PATCHED COPY of the port's
(indicators/riptide_ms/port/ms_struct.py), carrying the extra counters. The
original is left alone because deploy/ms-py-parity.py compares it, statement
by statement, to the Pine.
"""
import asyncio, collections, os, sys
os.environ.setdefault("RIPTIDE_LOOKBACK", "2000")
sys.path.insert(0, ".")
import aiohttp
from riptide.exchange import fetch_candles
from indicators.riptide_ms.port.ms_struct import ms_swings


def gt(a, b):
    return a is not None and b is not None and a > b


def lt(a, b):
    return a is not None and b is not None and a < b


def count(cs, msLen, msShortLen=3):
    n = len(cs)
    msTop, msTopX, msBtm, msBtmX = ms_swings(cs, msLen)
    msSTop, msSTopX, msSBtm, msSBtmX = ms_swings(cs, msShortLen)
    msOs = 0; msOsPrev = 0
    msTopCrossed = msBtmCrossed = False
    msSTopCrossed = msSBtmCrossed = False
    msMax = msMin = None; msMaxX = msMinX = None
    msTopY = msBtmY = None; msSTopY = msSBtmY = None
    c = collections.Counter()
    for i in range(n):
        h, l, cl = cs[i].h, cs[i].l, cs[i].c
        if msTop[i] is not None:
            msTopY = msTop[i]; msTopCrossed = False
        if msBtm[i] is not None:
            msBtmY = msBtm[i]; msBtmCrossed = False
        if gt(cl, msTopY) and not msTopCrossed:
            msOs = 1; msTopCrossed = True
        if lt(cl, msBtmY) and not msBtmCrossed:
            msOs = 0; msBtmCrossed = True
        if msOs != msOsPrev:
            msMax = h; msMin = l; msMaxX = msMinX = i
            msSTopCrossed = msSBtmCrossed = False
            c["choch"] += 1
        if msSTop[i] is not None:
            msSTopY = msSTop[i]
        if msSBtm[i] is not None:
            msSBtmY = msSBtm[i]

        # bullish
        if lt(l, msSBtmY) and not msSBtmCrossed and msOs == 1 and msSBtmY != msBtmY:
            c["idm"] += 1; msSBtmCrossed = True
        elif lt(l, msSBtmY) and not msSBtmCrossed and msOs == 1:
            c["idm_blocked_same_swing"] += 1
        if gt(cl, msMax) and msOs == 1:
            if msSBtmCrossed:
                c["bos"] += 1; msSBtmCrossed = False
            else:
                c["bos_suppressed"] += 1
        # bearish
        if gt(h, msSTopY) and not msSTopCrossed and msOs == 0 and msSTopY != msTopY:
            c["idm"] += 1; msSTopCrossed = True
        elif gt(h, msSTopY) and not msSTopCrossed and msOs == 0:
            c["idm_blocked_same_swing"] += 1
        if lt(cl, msMin) and msOs == 0:
            if msSTopCrossed:
                c["bos"] += 1; msSTopCrossed = False
            else:
                c["bos_suppressed"] += 1

        msMax = h if msMax is None else max(h, msMax)
        msMin = l if msMin is None else min(l, msMin)
        if msMaxX is None or msMax == h:
            msMaxX = i
        if msMinX is None or msMin == l:
            msMinX = i
        msOsPrev = msOs
    return c


async def main():
    async with aiohttp.ClientSession() as s:
        data = {sym: await fetch_candles(s, sym, "Min15")
                for sym in ("BTC_USDT", "ETH_USDT", "SOL_USDT")}
    print(f"{'msLen':>6}{'CHoCH':>8}{'IDM':>7}{'BOS':>7}"
          f"{'BOS suppressed':>16}{'IDM blocked':>13}   (3 symbols, 15m, 20.8d)")
    print("-" * 78)
    for L in (50, 30, 20, 15, 10, 8, 6, 5, 4, 3):
        t = collections.Counter()
        for cs in data.values():
            t += count(cs, L)
        print(f"{L:>6}{t['choch']:>8}{t['idm']:>7}{t['bos']:>7}"
              f"{t['bos_suppressed']:>16}{t['idm_blocked_same_swing']:>13}")

asyncio.run(main())
