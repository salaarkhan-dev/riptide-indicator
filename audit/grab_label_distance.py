"""How far is the $$$ label from the two candles that chose it?

drawGrabBand places the label at the MIDPOINT of the band,
    fromBar + (bar_index - 1 - fromBar) / 2
inherited from mickes, where "$$$" describes the LEVEL and the midpoint is a
fine place for it. Once the glyph encodes a property of two specific candles
(N-1 and N), the midpoint stops pointing at what it describes.
"""
import asyncio, os, statistics, sys, collections
os.environ.setdefault("RIPTIDE_LOOKBACK", "2000")
sys.path.insert(0, ".")
import aiohttp
from riptide.exchange import fetch_candles
from research.data import SYMBOLS

LOOKBACK = 5


def pivots(cs, left, right):
    out = []
    for i in range(left, len(cs) - right):
        if all(cs[i].h > cs[j].h for j in range(i - left, i)) and \
           all(cs[i].h >= cs[j].h for j in range(i + 1, i + right + 1)):
            out.append((i, cs[i].h, True))
        if all(cs[i].l < cs[j].l for j in range(i - left, i)) and \
           all(cs[i].l <= cs[j].l for j in range(i + 1, i + right + 1)):
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
            w = cs[i - 1].h if hi else cs[i - 1].l
            if (w >= px if hi else w <= px) and \
               (cs[i].c <= px if hi else cs[i].c >= px):
                out.append((i, bar))          # (grab bar N, pivot bar)
                e[3] = "done"
            elif (cs[i].c > px if hi else cs[i].c < px):
                e[3] = "done"
        for bar, px, hi in by.get(i, []):
            live.append([bar, px, hi, "open"])
            same = [e for e in live if e[2] == hi]
            for e in same[:-LOOKBACK]:
                e[3] = "done"
    return out


async def main():
    async with aiohttp.ClientSession() as s:
        data = {}
        for sym in SYMBOLS:
            try:
                cs = await fetch_candles(s, sym, "Min15")
            except Exception:                                  # noqa: BLE001
                continue
            if len(cs) >= 300:
                data[sym] = cs

    print(f"{len(data)} symbols, Min15, 2000-bar lookback\n")
    print(f"  {'instance':<22}{'grabs':>7}{'median':>9}{'mean':>8}"
          f"{'p90':>7}{'max':>7}{'>=3 bars away':>16}")
    print("  " + "-" * 76)
    for name, (L, R) in (("Grabs  3/3", (3, 3)), ("Big grabs  10/10", (10, 10))):
        d = []
        for cs in data.values():
            for n, pivot in grabs(cs, L, R):
                x2 = n - 1
                lab = pivot + (x2 - pivot) // 2      # Pine int division
                d.append(n - lab)                    # bars from label to bar N
        if not d:
            continue
        far = 100 * sum(1 for x in d if x >= 3) / len(d)
        print(f"  {name:<22}{len(d):>7}{statistics.median(d):>9.0f}"
              f"{statistics.fmean(d):>8.1f}"
              f"{sorted(d)[int(.9*len(d))]:>7}{max(d):>7}{far:>15.0f}%")
    print("\n  The glyph is decided by the candles at N-1 and N.")
    print("  The label sits this many bars to the LEFT of N.")

asyncio.run(main())
