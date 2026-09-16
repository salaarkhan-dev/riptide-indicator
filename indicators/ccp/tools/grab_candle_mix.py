"""What do the four candle-pair combinations actually look like on a grab?

The tooltip shipped with section 13 says "$$$ — both candles the same colour:
the piercing bar itself closed back over the level". That gloss is true when
both bars run WITH the reclaim, and false when both run AGAINST it — a
sell-side grab whose two bars are both bearish is "same colour" and nothing
rejected inside one bar. This counts how often that happens.
"""
import asyncio, collections, os, sys
os.environ.setdefault("RIPTIDE_LOOKBACK", "2000")
sys.path.insert(0, ".")
import aiohttp
from riptide.exchange import fetch_candles
from research.data import SYMBOLS

LEFT = RIGHT = 3
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


def grabs(cs):
    by = {}
    for bar, px, hi in pivots(cs, LEFT, RIGHT):
        by.setdefault(bar + RIGHT, []).append((bar, px, hi))
    live, out = [], []
    for i in range(len(cs)):
        for e in live:
            if e[3] != "open" or i - 1 <= e[0]:
                continue
            bar, px, hi = e[0], e[1], e[2]
            w = cs[i - 1].h if hi else cs[i - 1].l
            pierced = w >= px if hi else w <= px
            back = cs[i].c <= px if hi else cs[i].c >= px
            through = cs[i].c > px if hi else cs[i].c < px
            if pierced and back:
                out.append((i, hi))
                e[3] = "done"
            elif through:
                e[3] = "done"
        for bar, px, hi in by.get(i, []):
            live.append([bar, px, hi, "open"])
            same = [e for e in live if e[2] == hi]
            for e in same[:-LOOKBACK]:
                e[3] = "done"
    return out


async def main():
    c = collections.Counter()
    async with aiohttp.ClientSession() as s:
        for sym in SYMBOLS:
            try:
                cs = await fetch_candles(s, sym, "Min15")
            except Exception:                                  # noqa: BLE001
                continue
            if len(cs) < 300:
                continue
            for i, hi in grabs(cs):
                # reclaim direction: a sell-side grab (pivot low) reclaims UP
                up = not hi
                prevBull = cs[i - 1].c > cs[i - 1].o
                thisBull = cs[i].c > cs[i].o
                withPrev = prevBull == up          # N-1 ran WITH the reclaim
                withThis = thisBull == up
                same = prevBull == thisBull
                if withPrev and withThis:
                    k = "both WITH the reclaim"
                elif not withPrev and not withThis:
                    k = "both AGAINST the reclaim"
                else:
                    k = "one each way"
                c[k] += 1
                c["same" if same else "diff"] += 1
                if same:
                    c["same/" + ("with" if withPrev else "against")] += 1
    tot = c["same"] + c["diff"]
    print(f"{tot} grabs, 23 symbols, Min15, 2000-bar lookback, pivot 3/3\n")
    print("  CURRENT RULE — same colour vs different")
    for k in ("same", "diff"):
        lab = "$$$  same colour" if k == "same" else "$$   different"
        print(f"    {lab:<22}{c[k]:>6}  {100*c[k]/tot:>5.1f}%")
    print("\n  WHAT 'same colour' ACTUALLY CONTAINS")
    for k in ("same/with", "same/against"):
        lab = ("both ran WITH the reclaim  (gloss is true)" if k.endswith("with")
               else "both ran AGAINST it        (gloss is FALSE)")
        print(f"    {lab:<44}{c[k]:>6}  {100*c[k]/c['same']:>5.1f}% of $$$")
    print("\n  DIRECTION-AWARE ALTERNATIVE — did bar N-1 close in the reclaim direction?")
    wp = c["both WITH the reclaim"] + (c["one each way"] and 0)
    print(f"    N-1 with the reclaim   {c['both WITH the reclaim']:>6}"
          f"  (+ part of 'one each way')")
    for k in ("both WITH the reclaim", "one each way", "both AGAINST the reclaim"):
        print(f"    {k:<28}{c[k]:>6}  {100*c[k]/tot:>5.1f}%")

asyncio.run(main())
