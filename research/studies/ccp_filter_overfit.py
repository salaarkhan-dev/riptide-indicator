"""If we "just add filters until the losers go away", what do we get?

    python3 research/studies/ccp_filter_overfit.py

A METHOD DIAGNOSTIC, not a study of the market. It has no prereg and no
verdict because it is not asking whether anything works — it is asking what
happens when you pick a filter by looking at which trades failed.

THE PROCEDURE, which is the one the phrase describes:

  1. score every grab with the plain 2R exit
  2. compute a bank of ordinary, plausible binary conditions at signal time
  3. on the OLDER half, try every single condition and every pair, and keep
     whichever looks best
  4. then look at what that winner does on the NEWER half, which it has never
     seen

THE NUMBER THAT MATTERS is the rank correlation between in-sample and
out-of-sample performance across all candidates. If picking the best filter on
past data tells you nothing about future data, that correlation is near zero,
and every filter chosen by looking at failures is a coin flip wearing a
rationale.

Nothing here says filters cannot work. It says a filter chosen THIS WAY cannot
be trusted, and it puts a number on how untrustworthy. A filter with a
mechanism behind it, named before the data is seen, is a different object and
gets a prereg.
"""
from __future__ import annotations

import asyncio
import itertools
import math
import os
import statistics
import sys

import aiohttp

sys.path.insert(0, ".")
os.environ.setdefault("RIPTIDE_DEEP_CACHE", ".cache/deep")
os.makedirs(os.environ["RIPTIDE_DEEP_CACHE"], exist_ok=True)

from research.data import SYMBOLS                        # noqa: E402
from research.deep import load_universe                  # noqa: E402
from research.harness import simulate_market             # noqa: E402
from audit.ccp_merge_check import atr14                  # noqa: E402
from audit.ccp_at_grabs_check import grabs               # noqa: E402

PIVOT = 3
CCP_BACK = CCP_FWD = 2
ATR_BUF = 0.25
DAYS = 333
TFS = (("Min15", 192), ("Min30", 96), ("Min60", 48))
MIN_SIDE = 150          # a candidate must keep at least this many bets


def ema(vals, n):
    k, out, e = 2.0 / (n + 1), [], None
    for v in vals:
        e = v if e is None else v * k + e * (1 - k)
        out.append(e)
    return out


def build(cs, a, horizon: int, sym: str):
    """Every grab, the plain 2R exit, plus a bank of ordinary conditions."""
    closes = [c.c for c in cs]
    e50 = ema(closes, 50)
    vols = [c.v for c in cs]
    vmed = statistics.median(v for v in vols if v > 0) or 1.0
    rows = []
    for pv, gb, is_high in grabs(cs, PIVOT, PIVOT):
        sig = gb + CCP_FWD
        lo_i, hi_i = gb - CCP_BACK, gb + CCP_FWD
        if lo_i < 0 or sig >= len(cs) - 1 or a[sig] is None or a[gb] is None:
            continue
        is_long = not is_high
        entry = cs[sig].c
        buf = a[sig] * ATR_BUF
        stop = (min(cs[k].l for k in range(lo_i, hi_i + 1)) - buf if is_long
                else max(cs[k].h for k in range(lo_i, hi_i + 1)) + buf)
        if (stop >= entry) if is_long else (stop <= entry):
            continue
        o = simulate_market(cs, sig, entry, stop, is_long,
                            target_r=2.0, horizon_bars=horizon)
        if o is None:
            continue

        g = cs[gb]
        rng = max(g.h - g.l, 1e-12)
        hour = (cs[sig].t // 3600) % 24
        # Every condition is knowable at the signal bar. Ordinary things a
        # person would reach for after looking at a losing trade.
        f = {
            "long": is_long,
            "with EMA50": (entry > e50[sig]) == is_long,
            "EMA50 rising": e50[sig] > e50[sig - 10],
            "wide stop": abs(entry - stop) / entry > 0.008,
            "high ATR": a[sig] > a[sig - 50] if sig >= 50 else False,
            "level held long": (gb - pv) > 12,
            "grab wick big": (g.h - max(g.o, g.c) if is_high
                             else min(g.o, g.c) - g.l) / rng > 0.4,
            "grab body small": abs(g.c - g.o) / rng < 0.35,
            "grab closed back hard": (abs(cs[sig].c - g.c) / a[gb]) > 0.5,
            "volume high": g.v > vmed,
            "London/NY": 7 <= hour < 21,
            "signal bar with": (cs[sig].c > cs[sig].o) == is_long,
            "no gap to level": abs(entry - (g.h if is_high else g.l)) < a[sig],
            "not overextended": abs(entry - e50[sig]) < 3 * a[sig],
        }
        rows.append({"t": cs[sig].t, "r": o.r, "f": f, "sym": sym})
    return rows


def mean(v):
    return sum(v) / len(v) if v else float("nan")


def spearman(xs, ys) -> float:
    n = len(xs)
    if n < 3:
        return float("nan")
    rx = {v: i for i, v in enumerate(sorted(range(n), key=lambda k: xs[k]))}
    ry = {v: i for i, v in enumerate(sorted(range(n), key=lambda k: ys[k]))}
    d2 = sum((rx[i] - ry[i]) ** 2 for i in range(n))
    return 1 - 6 * d2 / (n * (n * n - 1))


async def main():
    print(__doc__.split("\n\n")[0])
    print("\nA METHOD DIAGNOSTIC. No prereg, no verdict, no claim about the "
          "market.\n")

    async with aiohttp.ClientSession() as sess:
        for tf, horizon in TFS:
            uni = await load_universe(sess, SYMBOLS, tf, DAYS)
            rows = []
            for sym, cs in uni.items():
                rows += build(cs, atr14(cs), horizon, sym)
            if len(rows) < 2 * MIN_SIDE:
                continue
            rows.sort(key=lambda r: r["t"])
            cut = len(rows) // 2
            old, new = rows[:cut], rows[cut:]
            names = list(rows[0]["f"])

            cands = [(n,) for n in names] + list(itertools.combinations(names, 2))
            ins, oos, kept = [], [], []
            for c in cands:
                io = [r["r"] for r in old if all(r["f"][k] for k in c)]
                oo = [r["r"] for r in new if all(r["f"][k] for k in c)]
                if len(io) < MIN_SIDE or len(oo) < MIN_SIDE:
                    continue
                ins.append(mean(io))
                oos.append(mean(oo))
                kept.append((c, len(io), len(oo)))

            base_o, base_n = mean([r["r"] for r in old]), mean([r["r"] for r in new])
            print(f"═══ {tf} — {len(rows)} grabs, {len(kept)} candidate "
                  f"filters that keep {MIN_SIDE}+ bets a side ═══")
            print(f"  no filter at all:   older {base_o:+.3f}   "
                  f"newer {base_n:+.3f}")

            best = max(range(len(kept)), key=lambda i: ins[i])
            c, ni, no = kept[best]
            print(f"  BEST ON THE OLDER HALF: {' + '.join(c)}")
            print(f"     older (chosen here) {ins[best]:+.3f}  n {ni}")
            print(f"     newer (never seen)  {oos[best]:+.3f}  n {no}"
                  f"    kept {oos[best] - ins[best]:+.3f} of it")

            pos = sum(1 for v in ins if v > 0)
            pos_n = sum(1 for v in oos if v > 0)
            print(f"  {pos}/{len(ins)} candidates beat zero on the older half; "
                  f"{pos_n}/{len(oos)} do on the newer half")
            rho = spearman(ins, oos)
            print(f"  RANK CORRELATION in-sample vs out-of-sample: {rho:+.3f}")
            print("     near zero means picking the best filter on past data")
            print("     tells you nothing about the next half.\n")


if __name__ == "__main__":
    asyncio.run(main())
