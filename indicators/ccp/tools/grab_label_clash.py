"""How often does a section-12 label land on top of a section-13 grab label?

Both layers centre their label on their own span, and neither knows the other
exists. This counts the overlaps so the fix is sized to the problem rather
than guessed at.

A clash = same bar +/- BAR_TOL and within PX_TOL x ATR in price.
"""
import asyncio, os, statistics, sys
os.environ.setdefault("RIPTIDE_LOOKBACK", "2000")
sys.path.insert(0, ".")
import aiohttp
from riptide.exchange import fetch_candles
from research.data import SYMBOLS
from indicators.riptide_ms.port.ms_struct import engine, ms_swings

BAR_TOL = 2
PX_TOL = 0.35          # x ATR
LOOKBACK = 5


def atr14(cs, n=14):
    tr, out, prev = [], [], None
    for i, c in enumerate(cs):
        t = c.h - c.l if i == 0 else max(c.h - c.l, abs(c.h - cs[i-1].c),
                                         abs(c.l - cs[i-1].c))
        tr.append(t)
        if i + 1 < n:
            out.append(None); continue
        prev = sum(tr[:n]) / n if prev is None else (prev*(n-1)+t)/n
        out.append(prev)
    return out


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


def grab_labels(cs, L, R):
    """(labelBar, price) with the label CENTRED on the band, as requested."""
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
                x2 = i - 1
                out.append((bar + (x2 - bar)//2, px))
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
    tot = {"grab": 0, "clash": 0}
    per = {}
    async with aiohttp.ClientSession() as s:
        for sym in SYMBOLS:
            try:
                cs = await fetch_candles(s, sym, "Min15")
            except Exception:                                  # noqa: BLE001
                continue
            if len(cs) < 300:
                continue
            a = atr14(cs)
            ev, _ = engine(cs, msLen=15, msShortLen=3)
            # section 12 centres its label between x1 and the current bar
            ms = [(e["bar"], e["px"]) for e in ev]
            for name, (L, R) in (("3/3", (3, 3)), ("10/10", (10, 10))):
                g = grab_labels(cs, L, R)
                c = 0
                for gb, gp in g:
                    for mb, mp in ms:
                        if abs(mb - gb) <= BAR_TOL and a[gb] and \
                           abs(mp - gp) <= PX_TOL * a[gb]:
                            c += 1
                            break
                d = per.setdefault(name, [0, 0])
                d[0] += len(g); d[1] += c
    print(f"clash = a section-12 label within {BAR_TOL} bars and "
          f"{PX_TOL} ATR of a grab label\n")
    print(f"  {'instance':<12}{'grab labels':>13}{'clashing':>11}{'rate':>8}")
    print("  " + "-" * 44)
    for k, (n, c) in per.items():
        print(f"  {k:<12}{n:>13}{c:>11}{100*c/n:>7.1f}%")

asyncio.run(main())
