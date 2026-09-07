"""Worked example: the daily DI direction, re-run on the shared harness.

This is the one entry-side finding that survived, so it is the right thing to
pin as a regression: if a future change to the engine breaks it, this study
turns from CANDIDATE to rejected and says so.

    python3 research/studies/di_direction.py
"""
import research.env                                         # noqa: F401  MUST be first
from bisect import bisect_right                             # noqa: E402

import asyncio                                              # noqa: E402
import aiohttp                                              # noqa: E402

from riptide.config import BAR_SECONDS, DI_INTERVAL         # noqa: E402
from riptide.exchange import fetch_candles                  # noqa: E402
from riptide.trend import di_direction                      # noqa: E402
from research.data import load, SYMBOLS                     # noqa: E402
from research.harness import report, risk_terciles          # noqa: E402


async def main():
    rows = await load()
    # DI on its own timeframe, read on the last bar CLOSED at the signal.
    di = {}
    async with aiohttp.ClientSession() as s:
        for sym in SYMBOLS:
            try:
                cs = await fetch_candles(s, sym, DI_INTERVAL)
            except Exception:
                continue
            if len(cs) > 30:
                di[sym] = ([c.t for c in cs], di_direction(cs))
    step = BAR_SECONDS[DI_INTERVAL]

    def agrees(row):
        got = di.get(row.symbol)
        if not got:
            return None
        times, dirs = got
        j = bisect_right(times, row.candles[row.bar].t - step) - 1
        if not 0 <= j < len(dirs) or not dirs[j]:
            return None
        return (dirs[j] > 0) == row.signal.is_long

    for kind in ("confirmed", "early"):
        sub = [r for r in rows if r.kind == kind]
        report(f"{DI_INTERVAL} DI agrees with the trade — {kind} (n={len(sub)})",
               sub, agrees, control=risk_terciles)

asyncio.run(main())
