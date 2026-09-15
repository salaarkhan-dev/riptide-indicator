"""How many grab alerts would the real universe actually produce?

Sizes the feature before it is designed. The trendline watch exists because
"20 symbols broke on one 4h close" was measured first; this is the same
question for grabs.
"""
import asyncio, os, sys, collections, datetime as dt
os.environ.setdefault("RIPTIDE_LOOKBACK", "2000")
sys.path.insert(0, ".")
import aiohttp
from riptide.exchange import fetch_candles
from riptide.config import BAR_SECONDS
from research.data import SYMBOLS

LOOKBACK = 5


def pivots(cs, L, R):
    out = []
    for i in range(L, len(cs) - R):
        if all(cs[i].h > cs[j].h for j in range(i-L, i)) and \
           all(cs[i].h >= cs[j].h for j in range(i+1, i+R+1)):
            out.append((i, cs[i].h, True))
        if all(cs[i].l < cs[j].l for j in range(i-L, i)) and \
           all(cs[i].l <= cs[j].l for j in range(i+1, i+R+1)):
            out.append((i, cs[i].l, False))
    return out


def grabs(cs, L, R):
    by = {}
    for bar, px, hi in pivots(cs, L, R):
        by.setdefault(bar + R, []).append((bar, px, hi))
    live, out = [], []
    for i in range(len(cs)):
        for e in live:
            if e[3] != "open" or i - 1 <= e[0]:
                continue
            bar, px, hi = e[0], e[1], e[2]
            w = cs[i-1].h if hi else cs[i-1].l
            if (w >= px if hi else w <= px) and \
               (cs[i].c <= px if hi else cs[i].c >= px):
                out.append(i); e[3] = "done"
            elif (cs[i].c > px if hi else cs[i].c < px):
                e[3] = "done"
        for bar, px, hi in by.get(i, []):
            live.append([bar, px, hi, "open"])
            for e in [x for x in live if x[2] == hi][:-LOOKBACK]:
                e[3] = "done"
    return out


async def main():
    print(f"{'tf':>7}{'syms':>6}{'days':>7}{'grabs':>8}{'per day':>9}"
          f"{'busiest close':>15}{'closes w/ >=1':>15}")
    print("-" * 67)
    async with aiohttp.ClientSession() as s:
        for tf, L, R in (("Min15", 3, 3), ("Min30", 3, 3), ("Min60", 3, 3),
                         ("Min15", 10, 10), ("Min60", 10, 10)):
            per_close = collections.Counter()
            tot = n = bars = 0
            for sym in SYMBOLS:
                try:
                    cs = await fetch_candles(s, sym, tf)
                except Exception:                              # noqa: BLE001
                    continue
                if len(cs) < 300:
                    continue
                n += 1; bars = max(bars, len(cs))
                g = grabs(cs, L, R)
                tot += len(g)
                for i in g:
                    per_close[cs[i].t] += 1
            if not n:
                continue
            days = bars * BAR_SECONDS[tf] / 86400
            closes = bars
            print(f"{tf + ' ' + str(L) + '/' + str(R):>7}"[:7].rjust(7), end="")
            print(f"{n:>6}{days:>7.1f}{tot:>8}{tot/days:>9.1f}"
                  f"{max(per_close.values()):>15}"
                  f"{100*len(per_close)/closes:>14.0f}%"
                  f"   {tf} {L}/{R}")

asyncio.run(main())
