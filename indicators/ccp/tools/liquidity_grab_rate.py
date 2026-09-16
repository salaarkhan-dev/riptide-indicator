"""How often does the mickes GRAB fire, and does it say anything Riptide's
raid does not already say?

The question is not "is the grab a good pattern". It is: if I add a second
mark to a chart that already marks raids, how many NEW marks appear, and do
they land in the same places?

Both conditions are transcribed from the sources, not paraphrased:

  mickes grab (pivot low, Type -1), audit finding 4 collapsed out:
      low[1] <= p and close >= p          on a CONFIRMED bar
      invalidated earlier if close < p    on the piercing bar itself
  mickes sweep (pivot low):
      low[1] <= p and close <= p

  riptide raid (sell-side pool at level L):
      low < L - atr*grabBufferATR         (default 0.05)
      then, within grabBars, an MSS: close > structLevel

Pools on both sides come from the SAME pivots so the comparison is about the
trigger, not about level selection.

WHAT THIS IS NOT. The riptide side here is a reduction of the real engine to
its trigger: pool -> wick beyond the level + ATR buffer -> MSS within a bar
budget. It does not run the obstacle check, the zone classification, the
session gates, the HTF trend filter or the FVG requirement, all of which
REMOVE raids. So the raid count below is an upper bound on what the indicator
actually marks, and the ratio "grabs per raid" is therefore a LOWER bound.
That direction is the safe one for the conclusion being drawn — adding grabs
to the chart adds at least this many marks — but the absolute counts are not
the indicator's.
"""
from __future__ import annotations

import asyncio
import statistics
import sys

import aiohttp

sys.path.insert(0, ".")
from riptide.exchange import fetch_candles  # noqa: E402

SYMS = "BTC_USDT ETH_USDT SOL_USDT XRP_USDT DOGE_USDT LINK_USDT".split()
TFS = ("Min15", "Min30", "Min60")
LEFT = RIGHT = 3
LOOKBACK = 5
GRAB_BUF = 0.05          # riptide.conf default grabBufferATR
GRAB_BARS = 12           # riptide.conf default grabBars


def atr(o, h, l, c, n=14):
    tr, out, prev = [], [], None
    for i in range(len(c)):
        t = h[i] - l[i] if i == 0 else max(h[i] - l[i], abs(h[i] - c[i - 1]),
                                           abs(l[i] - c[i - 1]))
        tr.append(t)
        if i + 1 < n:
            out.append(None)
            continue
        prev = sum(tr[:n]) / n if prev is None else (prev * (n - 1) + t) / n
        out.append(prev)
    return out


def pivots(h, l, left, right):
    """(bar, price, kind) confirmed `right` bars later, exactly like
    ta.pivothigh/ta.pivotlow."""
    out = []
    for i in range(left, len(h) - right):
        if all(h[i] > h[j] for j in range(i - left, i)) and \
           all(h[i] >= h[j] for j in range(i + 1, i + right + 1)):
            out.append((i, h[i], 1))
        if all(l[i] < l[j] for j in range(i - left, i)) and \
           all(l[i] <= l[j] for j in range(i + 1, i + right + 1)):
            out.append((i, l[i], -1))
    return out


def run(o, h, l, c):
    a = atr(o, h, l, c)
    piv = pivots(h, l, LEFT, RIGHT)
    by_conf = {}
    for bar, px, kind in piv:
        by_conf.setdefault(bar + RIGHT, []).append((bar, px, kind))

    live = []          # [bar, px, kind, state] state: 'open'|'done'
    grabs, sweeps, raids = [], [], []
    pend = []          # riptide: [bar, px, kind, structLevel, sweepBar]

    for i in range(len(c)):
        # --- mickes: evaluate on the confirmed bar, before new pivots land ---
        for e in live:
            if e[3] != "open":
                continue
            bar, px, kind = e[0], e[1], e[2]
            if i - 1 < 0 or i - 1 <= bar:
                continue
            if kind == -1:
                if l[i - 1] <= px and c[i] >= px:
                    grabs.append((i, px, kind))
                    e[3] = "done"
                elif l[i - 1] <= px and c[i] <= px:
                    sweeps.append((i, px, kind))
                    e[3] = "done"
                elif c[i] < px:
                    e[3] = "done"          # invalidated
            else:
                if h[i - 1] >= px and c[i] <= px:
                    grabs.append((i, px, kind))
                    e[3] = "done"
                elif h[i - 1] >= px and c[i] >= px:
                    sweeps.append((i, px, kind))
                    e[3] = "done"
                elif c[i] > px:
                    e[3] = "done"

        # --- riptide: wick beyond the level + buffer, then an MSS ---
        if a[i] is not None:
            for p in pend:
                if p[4] is not None or p[5]:
                    continue
                bar, px, kind = p[0], p[1], p[2]
                if i <= bar:
                    continue
                buf = a[i] * GRAB_BUF
                hit = (l[i] < px - buf) if kind == -1 else (h[i] > px + buf)
                if hit:
                    p[4] = i
                    # structLevel = the running extreme on the other side
                    seg = range(bar, i + 1)
                    p[3] = max(h[j] for j in seg) if kind == -1 else \
                        min(l[j] for j in seg)
            for p in pend:
                if p[4] is None or p[5]:
                    continue
                if i - p[4] > GRAB_BARS:
                    p[5] = True
                    continue
                mss = (c[i] > p[3]) if p[2] == -1 else (c[i] < p[3])
                if mss and i > p[4]:
                    raids.append((i, p[1], p[2], p[4]))
                    p[5] = True

        # --- new pivots confirm on this bar ---
        for bar, px, kind in by_conf.get(i, []):
            live.append([bar, px, kind, "open"])
            pend.append([bar, px, kind, None, None, False])
            same = [e for e in live if e[2] == kind]
            for e in same[:-LOOKBACK]:
                e[3] = "done"
    return grabs, sweeps, raids


async def main():
    tot = {"g": 0, "s": 0, "r": 0, "shared": 0, "bars": 0}
    leads = []
    print(f"{'sym':<10}{'tf':>7}{'bars':>7}{'grab':>7}{'sweep':>7}"
          f"{'raid':>7}{'both':>7}{'grab lead':>11}")
    sess = aiohttp.ClientSession()
    for sym in SYMS:
        for tf in TFS:
            try:
                k = await fetch_candles(sess, sym, tf)
            except Exception as e:                      # noqa: BLE001
                print(f"  {sym} {tf}: {type(e).__name__} {e}")
                continue
            if not k or len(k) < 300:
                continue
            o = [x.o for x in k]
            h = [x.h for x in k]
            l = [x.l for x in k]
            c = [x.c for x in k]
            g, s, r = run(o, h, l, c)
            # a raid and a grab "agree" when they name the same level and the
            # grab lands within GRAB_BARS of the raid's sweep bar
            both, lead = 0, []
            for rb, rpx, rk, sb in r:
                for gb, gpx, gk in g:
                    if gk == rk and abs(gpx - rpx) < 1e-12 and \
                            abs(gb - sb) <= GRAB_BARS:
                        both += 1
                        lead.append(rb - gb)
                        break
            leads += lead
            tot["g"] += len(g)
            tot["s"] += len(s)
            tot["r"] += len(r)
            tot["shared"] += both
            tot["bars"] += len(c)
            ml = f"{statistics.median(lead):+.1f}" if lead else "-"
            print(f"{sym:<10}{tf:>7}{len(c):>7}{len(g):>7}{len(s):>7}"
                  f"{len(r):>7}{both:>7}{ml:>11}")
    await sess.close()
    print("-" * 63)
    print(f"{'TOTAL':<10}{'':>7}{tot['bars']:>7}{tot['g']:>7}{tot['s']:>7}"
          f"{tot['r']:>7}{tot['shared']:>7}")
    if tot["r"]:
        print(f"\n  {tot['shared']}/{tot['r']} riptide raids "
              f"({100*tot['shared']/tot['r']:.0f}%) have a mickes grab on the "
              f"same level")
    if tot["g"]:
        print(f"  {tot['g'] - tot['shared']}/{tot['g']} grabs "
              f"({100*(tot['g']-tot['shared'])/tot['g']:.0f}%) are marks "
              f"riptide does not already make")
    if leads:
        print(f"  median bars the grab leads the raid by: "
              f"{statistics.median(leads):+.1f}  (n={len(leads)})")


asyncio.run(main())
