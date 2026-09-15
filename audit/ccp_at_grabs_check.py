"""How often do BOTH ends of a grab carry the shape the grab implies?

A transcription of section 5 of riptide-ccp.pine after it was narrowed from
"every bar" to "the two ends of a grab, in the grab's own direction". The
ungated version marked 88.4% of all bars (research/CCP_SEARCH_INFLATION.md);
this measures what the prior bought.

Two anchors per grab:
    LEFT   the swing candle that built the level
    RIGHT  the candle that ran it
and only the direction the setup predicts — a grab of a HIGH wants a bearish
shape, a grab of a LOW a bullish one.

    python3 audit/ccp_at_grabs_check.py
"""
from __future__ import annotations

import asyncio
import collections
import os
import sys

import aiohttp

sys.path.insert(0, ".")
os.environ.setdefault("RIPTIDE_LOOKBACK", "2000")

from riptide.exchange import fetch_candles        # noqa: E402
from research.data import SYMBOLS                 # noqa: E402
from audit.ccp_merge_check import atr14, name_of  # noqa: E402

LOOKBACK = 5


def pivots(cs, L, R):
    out = []
    for i in range(L, len(cs) - R):
        if all(cs[i].h > cs[j].h for j in range(i - L, i)) and \
           all(cs[i].h >= cs[j].h for j in range(i + 1, i + R + 1)):
            out.append((i, cs[i].h, True))
        if all(cs[i].l < cs[j].l for j in range(i - L, i)) and \
           all(cs[i].l <= cs[j].l for j in range(i + 1, i + R + 1)):
            out.append((i, cs[i].l, False))
    return out


def grabs(cs, L, R):
    """(pivotBar, grabBar, isHigh) — the exact condition section 4 uses."""
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
                out.append((bar, i, hi))
                e[3] = "done"
            elif (cs[i].c > px if hi else cs[i].c < px):
                e[3] = "done"
        for bar, px, hi in by.get(i, []):
            live.append([bar, px, hi, "open"])
            for e in [x for x in live if x[2] == hi][:-LOOKBACK]:
                e[3] = "done"
    return out


def scan_at(cs, anchor, back, fwd, body_max, wick_min, min_rng, want_bull):
    """ccpScanAt(): best window containing `anchor`, direction gated."""
    if anchor - back < 0 or anchor + fwd >= len(cs):
        return None
    best, bs = None, -1e18
    for f in range(fwd + 1):
        hi = max(cs[k].h for k in range(anchor, anchor + f + 1))
        lo = min(cs[k].l for k in range(anchor, anchor + f + 1))
        cc = cs[anchor + f].c
        for b in range(back + 1):
            if b > 0:
                hi = max(hi, cs[anchor - b].h)
                lo = min(lo, cs[anchor - b].l)
            oo = cs[anchor - b].o
            rng = hi - lo
            if rng <= 0 or rng < min_rng:
                continue
            body = abs(cc - oo) / rng
            up = (hi - max(oo, cc)) / rng
            dn = (min(oo, cc) - lo) / rng
            big = max(up, dn)
            if body > body_max or big < wick_min or (dn > up) != want_bull:
                continue
            sc = big - (b + f) * 100
            if sc > bs:
                bs, best = sc, (b, f, name_of(dn > up, cc >= oo))
    return best


async def main():
    async with aiohttp.ClientSession() as s:
        data = []
        for sym in SYMBOLS:
            try:
                cs = await fetch_candles(s, sym, "Min15")
            except Exception:                                  # noqa: BLE001
                continue
            if len(cs) >= 300:
                data.append((cs, atr14(cs)))

    print(f"{len(data)} symbols, Min15. Grabs from the 3/3 instance.\n")
    print(f"  {'back/fwd':>9}{'grabs':>8}{'left':>8}{'right':>8}{'BOTH':>8}"
          f"{'both %':>9}   alone+alone / a+m / m+a / m+m")
    print("  " + "-" * 88)

    for w in (0, 1, 2, 3):
        n = L = R = B = 0
        combo = collections.Counter()
        names = collections.Counter()
        for cs, a in data:
            for pv, gb, hi in grabs(cs, 3, 3):
                if a[gb] is None or gb + w >= len(cs) or pv - w < 0:
                    continue
                n += 1
                want = not hi
                mn = a[gb] * 0.50
                lr = scan_at(cs, pv, w, w, 0.15, 0.70, mn, want)
                rr = scan_at(cs, gb, w, w, 0.15, 0.70, mn, want)
                if lr:
                    L += 1
                if rr:
                    R += 1
                if lr and rr:
                    B += 1
                    lm = "merged" if lr[0] + lr[1] else "alone"
                    rm = "merged" if rr[0] + rr[1] else "alone"
                    combo[f"{lm}+{rm}"] += 1
                    names[rr[2]] += 1
        if not n:
            continue
        c = combo
        print(f"  {str(w)+'/'+str(w):>9}{n:>8}{L:>8}{R:>8}{B:>8}"
              f"{100*B/n:>8.1f}%   "
              f"{c['alone+alone']} / {c['alone+merged']} / "
              f"{c['merged+alone']} / {c['merged+merged']}")
        if w == 2:
            print(f"            names at the right end: "
                  f"{dict(names.most_common())}")

asyncio.run(main())
