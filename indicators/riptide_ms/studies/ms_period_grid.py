"""Two-dimensional sweep: can CHoCH be made sensitive WITHOUT killing IDM/BOS?

The 1-D sweep in ms_bos_gate.py beside this showed the two wants pull
opposite ways through a single parameter. This asks whether separating msLen
from msShortLen buys back the IDM/BOS chain at a short msLen.
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


def count(cs, msLen, msShortLen):
    n = len(cs)
    msTop, msTopX, msBtm, msBtmX = ms_swings(cs, msLen)
    msSTop, msSTopX, msSBtm, msSBtmX = ms_swings(cs, msShortLen)
    msOs = msOsPrev = 0
    msTopCrossed = msBtmCrossed = False
    msSTopCrossed = msSBtmCrossed = False
    msMax = msMin = msMaxX = msMinX = None
    msTopY = msBtmY = msSTopY = msSBtmY = None
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
        if lt(l, msSBtmY) and not msSBtmCrossed and msOs == 1:
            if msSBtmY != msBtmY:
                c["idm"] += 1; msSBtmCrossed = True
            else:
                c["blocked"] += 1
        if gt(cl, msMax) and msOs == 1:
            if msSBtmCrossed:
                c["bos"] += 1; msSBtmCrossed = False
        if gt(h, msSTopY) and not msSTopCrossed and msOs == 0:
            if msSTopY != msTopY:
                c["idm"] += 1; msSTopCrossed = True
            else:
                c["blocked"] += 1
        if lt(cl, msMin) and msOs == 0:
            if msSTopCrossed:
                c["bos"] += 1; msSTopCrossed = False
        msMax = h if msMax is None else max(h, msMax)
        msMin = l if msMin is None else min(l, msMin)
        msOsPrev = msOs
    return c


async def main():
    async with aiohttp.ClientSession() as s:
        data = [await fetch_candles(s, sym, "Min15")
                for sym in ("BTC_USDT", "ETH_USDT", "SOL_USDT")]
    shorts = (1, 2, 3, 5)
    print("     each cell: CHoCH / IDM / BOS / IDM-blocked      "
          "(3 symbols, 15m, 20.8d)")
    print(f"{'msLen':>6}" + "".join(f"{'short=' + str(s):>22}" for s in shorts))
    print("-" * (6 + 22 * len(shorts)))
    for L in (20, 15, 12, 10, 8, 6, 5):
        cells = []
        for S in shorts:
            if S >= L:
                cells.append(f"{'-':>22}")
                continue
            t = collections.Counter()
            for cs in data:
                t += count(cs, L, S)
            cells.append(f"{t['choch']:>5}/{t['idm']:>4}/{t['bos']:>4}"
                         f"/{t['blocked']:>4}   ")
        print(f"{L:>6}" + "".join(cells))

asyncio.run(main())
