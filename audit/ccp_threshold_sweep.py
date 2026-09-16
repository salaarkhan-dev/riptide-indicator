"""What do the body cap and wick floor cost, gated to grabs?

    python3 audit/ccp_threshold_sweep.py

research/CCP_SEARCH_INFLATION.md tightened the pin definition from the CCP
sheet's own 0.35 body / 0.50 wick to 0.15 / 0.70, to fight a classifier that
was marking 88% of all bars. That was measured UNGATED — before the search was
restricted to the two ends of a grab in the grab's own direction, which is what
actually fixed the rate.

So the tightening was never re-examined once the prior did the work, and it is
the reason a candle that plainly reads as a hammer by eye comes back "no
shape": 0.15 is a much smaller body than most real pins have. This sweeps both
thresholds WITH the grab gate in place, so the cost of the sheet's own
definition can be read off rather than guessed at.

The column that matters is BOTH — the share of grabs where the swing that built
the level and the candles that ran it both carry the shape.
"""
from __future__ import annotations

import asyncio
import os
import sys

import aiohttp

sys.path.insert(0, ".")
os.environ.setdefault("RIPTIDE_DEEP_CACHE", ".cache/deep")

from research.data import SYMBOLS                        # noqa: E402
from research.deep import load_universe                  # noqa: E402
from audit.ccp_merge_check import atr14                  # noqa: E402
from audit.ccp_at_grabs_check import grabs, scan_at      # noqa: E402

PIVOT = 3
BACK = FWD = 2
MIN_RANGE_ATR = 0.50
DAYS = 333

# The sheet's definition, the shipped one, and the ground between them.
GRID = [
    (0.35, 0.50, "the CCP sheet's own shape"),
    (0.35, 0.60, ""),
    (0.25, 0.60, ""),
    (0.25, 0.70, ""),
    (0.20, 0.65, ""),
    (0.15, 0.70, "SHIPPED"),
    (0.10, 0.75, ""),
]


async def main():
    async with aiohttp.ClientSession() as sess:
        for tf in ("Min15", "Min30", "Min60"):
            uni = await load_universe(sess, SYMBOLS, tf, DAYS)
            ev = []
            for sym, cs in uni.items():
                a = atr14(cs)
                for pv, gb, is_high in grabs(cs, PIVOT, PIVOT):
                    if a[gb] is None or gb + FWD >= len(cs) or pv - BACK < 0:
                        continue
                    ev.append((cs, a[gb] * MIN_RANGE_ATR, pv, gb, not is_high))

            print(f"═══ {tf} — {len(ev)} grabs ═══")
            print(f"  {'body<=':>7}{'wick>=':>8}{'left':>9}{'right':>9}"
                  f"{'BOTH':>9}{'both %':>9}   ")
            print("  " + "-" * 62)
            for body, wick, note in GRID:
                L = R = B = 0
                for cs, mn, pv, gb, want in ev:
                    lr = scan_at(cs, pv, BACK, FWD, body, wick, mn, want)
                    rr = scan_at(cs, gb, BACK, FWD, body, wick, mn, want)
                    if lr:
                        L += 1
                    if rr:
                        R += 1
                    if lr and rr:
                        B += 1
                n = len(ev) or 1
                print(f"  {body:>7.2f}{wick:>8.2f}{L:>9}{R:>9}{B:>9}"
                      f"{100*B/n:>8.1f}%   {note}")
            print()

    print("READ IT AS A TRADE, NOT AN IMPROVEMENT. A looser shape marks more")
    print("grabs; it does not make the marks mean more. research/")
    print("CCP_ENTRY_MODELS.md measured the shipped setting and found gross")
    print("expectancy at a grab is about zero, so nothing on this table is")
    print("known to be better than anything else on it — only busier or")
    print("quieter. Pick the one that matches what your eye calls a pin.")


if __name__ == "__main__":
    asyncio.run(main())
