"""Does a LONGER pivot build better pools?

Runs research/studies/PREREG_pool_pivot_length.md exactly as written. The
arms, the data, the unit of evidence, the 3.0 SE bar, the +0.50 R power
escape hatch and the 0.50% degenerate-stop flag are all fixed there.

    python3 research/studies/pool_pivot_length.py
"""
from __future__ import annotations

import asyncio
import dataclasses
import os
import statistics
import sys

import aiohttp

sys.path.insert(0, ".")
os.environ.setdefault("RIPTIDE_LOOKBACK", "2000")

from riptide.config import CFG                    # noqa: E402
from riptide.engine import run_engine             # noqa: E402
from riptide.exchange import fetch_candles        # noqa: E402
from research.data import SYMBOLS                 # noqa: E402
from research.harness import simulate             # noqa: E402

ARMS = [(1, 2), (3, 3), (5, 5), (8, 8), (10, 10), (16, 16)]
INTERVAL = "Min15"
SE_BAR = 3.0
POWER_LIMIT = 0.50        # R per bet
RISK_FLOOR = 0.50         # % of entry


def mean_se(v):
    if len(v) < 2:
        return (statistics.fmean(v) if v else 0.0), 0.0
    return statistics.fmean(v), statistics.stdev(v) / len(v) ** 0.5


def bets(rows):
    """One bet per (symbol, sweep_time); R averaged inside the bet."""
    g: dict[tuple, list[float]] = {}
    for r in rows:
        g.setdefault((r["symbol"], r["sweep"]), []).append(r["r"])
    return g


def arm_rows(sym, cs, idx, n, left, right):
    cfg = dataclasses.replace(CFG, pivot_left=left, pivot_right=right)
    out = []
    for x in run_engine(sym, cs, cfg):
        i = idx.get(x.detected_time)
        if i is None:
            continue
        risk = abs(x.entry - x.stop)
        if risk <= 0 or x.entry <= 0:
            continue
        o = simulate(cs, i, x.entry, x.stop, x.is_long)
        # An unfinished trade at the end of the data is not a timeout, it is
        # a trade that has not happened yet.
        if o.exit_bar is None and o.filled:
            continue
        out.append(dict(symbol=sym, r=o.r, sweep=x.sweep_time,
                        risk_pct=100 * risk / x.entry,
                        split_sym=n % 2,
                        split_win=cs[i].t < cs[len(cs) // 2].t))
    return out


async def main():
    per_arm: dict[tuple, list] = {a: [] for a in ARMS}
    got = 0
    async with aiohttp.ClientSession() as sess:
        for n, sym in enumerate(SYMBOLS):
            try:
                cs = await fetch_candles(sess, sym, INTERVAL)
            except Exception:                                  # noqa: BLE001
                continue
            if len(cs) < 300:
                continue
            got += 1
            idx = {c.t: i for i, c in enumerate(cs)}
            for a in ARMS:
                per_arm[a] += arm_rows(sym, cs, idx, n, *a)
    print(f"symbols with data: {got}/{len(SYMBOLS)}   {INTERVAL}   "
          f"lookback {os.environ['RIPTIDE_LOOKBACK']}\n")

    # ── per-arm summary ────────────────────────────────────────────────────
    summary = {}
    print(f"  {'pivot':>8}{'setups':>8}{'bets':>7}{'meanR/bet':>12}"
          f"{'SE':>8}{'win%':>7}{'med risk%':>11}")
    print("  " + "-" * 61)
    for a in ARMS:
        rows = per_arm[a]
        b = bets(rows)
        v = [statistics.fmean(x) for x in b.values()]
        m, se = mean_se(v)
        risk = statistics.median([r["risk_pct"] for r in rows]) if rows else 0
        win = 100 * sum(1 for x in v if x > 0) / len(v) if v else 0
        summary[a] = dict(vals=v, m=m, se=se, rows=rows, risk=risk)
        flag = "  DEGENERATE" if risk < RISK_FLOOR else ""
        print(f"  {str(a):>8}{len(rows):>8}{len(v):>7}{m:>+12.3f}"
              f"{se:>8.3f}{win:>7.1f}{risk:>11.2f}{flag}")

    ctrl = summary[ARMS[0]]
    if not ctrl["vals"]:
        print("\nno control bets — nothing to compare")
        return

    # ── the preregistered comparison ───────────────────────────────────────
    print(f"\n  each arm MINUS the control {ARMS[0]}, on mean R per bet")
    print(f"  {'pivot':>8}{'diff':>10}{'SE':>8}{'SE units':>10}"
          f"{'sym split':>11}{'win split':>11}{'verdict':>14}")
    print("  " + "-" * 72)
    detectable = []
    for a in ARMS[1:]:
        s = summary[a]
        if not s["vals"]:
            print(f"  {str(a):>8}   no bets")
            continue
        d = s["m"] - ctrl["m"]
        se = (s["se"] ** 2 + ctrl["se"] ** 2) ** 0.5
        units = d / se if se else 0.0
        detectable.append(SE_BAR * se)

        holds = {}
        for key in ("split_sym", "split_win"):
            ok = True
            for val in sorted({r[key] for r in ctrl["rows"]}):
                cb = [statistics.fmean(x) for x in
                      bets([r for r in ctrl["rows"] if r[key] == val]).values()]
                ab = [statistics.fmean(x) for x in
                      bets([r for r in s["rows"] if r[key] == val]).values()]
                if len(cb) < 10 or len(ab) < 10:
                    ok = False
                    break
                sub = statistics.fmean(ab) - statistics.fmean(cb)
                if (sub > 0) != (d > 0) or sub == 0:
                    ok = False
                    break
            holds[key] = ok

        passed = (units >= SE_BAR and holds["split_sym"] and holds["split_win"])
        print(f"  {str(a):>8}{d:>+10.3f}{se:>8.3f}{units:>+10.1f}"
              f"{('held' if holds['split_sym'] else 'flipped'):>11}"
              f"{('held' if holds['split_win'] else 'flipped'):>11}"
              f"{('PASSES' if passed else 'fails'):>14}")

    # ── power, as the prereg demands, whichever way the result went ────────
    worst = max(detectable) if detectable else 0.0
    print(f"\n  POWER. The 3.0 SE bar corresponds to an effect of at most "
          f"{worst:+.3f} R per bet")
    print(f"  across the five comparisons. The prereg calls the study "
          f"UNDERPOWERED above {POWER_LIMIT:+.2f}.")
    if worst > POWER_LIMIT:
        print(f"  -> UNDERPOWERED. This run cannot distinguish 'no effect' "
              f"from an effect")
        print(f"     smaller than {worst:+.3f} R per bet. No verdict is "
              f"claimed; the bound is the result.")
    else:
        print("  -> powered as preregistered; the verdicts above stand.")


asyncio.run(main())
