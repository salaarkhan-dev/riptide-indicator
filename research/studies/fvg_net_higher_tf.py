"""Is the FVG edge NET-positive at 4h and 8h?

Pre-registered in PREREG_fvg_net_higher_tf.md, committed before this ran.

    python3 research/studies/fvg_net_higher_tf.py

HALF OF THIS IS NOT A TEST, and the prereg says so. On the 90 non-discovery
symbols the gross numbers are already known (+0.037 and +0.067) and net is
gross minus a fee that depends only on risk size — so that half is subtraction
on data already seen. It is printed because exact figures are useful, and
labelled ARITHMETIC because it is not evidence.

THE TEST is the 23 discovery symbols. They are the FVG line's original
universe, contaminated at Min60 where the effect was found, and completely
fresh above it: no run in this sequence has touched Hour4 or Hour8 on them.

build(), the FVG rule, the stop buffer, the target and the horizon are imported
from fvg_higher_tf unchanged, so the two runs are directly comparable.
"""
from __future__ import annotations

import asyncio
import math
import os
import sys

import aiohttp

sys.path.insert(0, ".")
os.environ.setdefault("RIPTIDE_DEEP_CACHE", ".cache/deep")
os.makedirs(os.environ["RIPTIDE_DEEP_CACHE"], exist_ok=True)

from research.data import SYMBOLS as DISCOVERY            # noqa: E402
from research.deep import load_universe                   # noqa: E402
from riptide.exchange import list_symbols                 # noqa: E402
from audit.ccp_merge_check import atr14                   # noqa: E402
from research.studies.ccp_context_filters import clustered  # noqa: E402
from research.studies.fvg_higher_tf import (              # noqa: E402
    build, DAYS, MIN_BARS, MIN_BETS, MIN_DAYS, MDE_CEILING)

TFS = (("Min60", "anchor"), ("Hour4", "TEST"), ("Hour8", "TEST"))


def split(rows, key, col):
    keep = [(r[col], (r["sym"], r["t"] // 86400)) for r in rows
            if r[key] is True and r.get(col) is not None]
    drop = [(r[col], (r["sym"], r["t"] // 86400)) for r in rows
            if r[key] is False and r.get(col) is not None]
    if not keep or not drop:
        return None
    mk, sk, nk = clustered([v for v, _ in keep], [k for _, k in keep])
    md, sd, _ = clustered([v for v, _ in drop], [k for _, k in drop])
    se = math.sqrt(sk * sk + sd * sd)
    return mk, sk, nk, mk - md, se, (mk - md) / se if se > 0 else float("nan")


async def panel(sess, syms, tf, label):
    uni = await load_universe(sess, syms, tf, DAYS, min_bars=MIN_BARS)
    rows = []
    for sym, cs in uni.items():
        rows += build(cs, atr14(cs), sym)
    if not rows:
        return None
    span = (max(r["t"] for r in rows) - min(r["t"] for r in rows)) / 86400
    n = split(rows, "f", "net")
    g = split(rows, "f", "r")
    c = split(rows, "cf", "cnet")
    if n is None or g is None:
        return None
    risk = sorted(r["risk_pct"] for r in rows)
    return dict(tf=tf, label=label, syms=len(uni), span=span,
                net=n, gross=g, ctl=c, risk=risk[len(risk) // 2],
                drag=g[0] - n[0])


def show(p):
    n, g = p["net"], p["gross"]
    print(f"  {p['tf']:<7}{p['label']:<8}{p['syms']:>5}{p['span']:>7.0f}"
          f"{n[2]:>8}{n[0]:>9.3f}{n[1]:>7.3f}{n[3]:>9.3f}{n[5]:>7.2f}"
          f"{g[0]:>9.3f}{p['drag']:>8.3f}{p['risk']:>7.2f}"
          f"{(p['ctl'][3] if p['ctl'] else float('nan')):>9.3f}")


async def main() -> None:
    print(__doc__.split("\n\n")[0])
    async with aiohttp.ClientSession() as sess:
        allsym = await list_symbols(sess)
        others = [s for s in allsym if s not in set(DISCOVERY)]
        hdr = (f"  {'tf':<7}{'role':<8}{'syms':>5}{'days':>7}{'n':>8}"
               f"{'NET R':>9}{'SE':>7}{'net Δ':>9}{'z':>7}"
               f"{'gross':>9}{'drag':>8}{'risk%':>7}{'ctlΔ':>9}")
        test = {}

        print(f"\n═══ THE TEST — {len(DISCOVERY)} discovery symbols, fresh "
              f"above 1h ═══")
        print(hdr)
        print("  " + "-" * 98)
        for tf, label in TFS:
            p = await panel(sess, list(DISCOVERY), tf, label)
            if p is None:
                print(f"  {tf:<7}{label:<8}  nothing scored")
                continue
            show(p)
            test[tf] = p

        print(f"\n═══ ARITHMETIC, NOT EVIDENCE — {len(others)} non-discovery "
              f"symbols, already used for gross ═══")
        print(hdr)
        print("  " + "-" * 98)
        for tf, label in TFS:
            p = await panel(sess, others, tf, "—")
            if p is not None:
                show(p)

    print("\n═══ VERDICT — the 23-symbol test population only ═══")
    if not all(t in test for t in ("Min60", "Hour4", "Hour8")):
        print("  an arm is missing; no verdict")
        return
    a = test["Min60"]["net"][0]
    hi = [test["Hour4"], test["Hour8"]]
    print(f"  Min60 anchor net {a:+.3f}   "
          + "   ".join(f"{h['tf']} {h['net'][0]:+.3f}" for h in hi) + "\n")
    b1 = all(h["net"][2] >= MIN_BETS and h["span"] >= MIN_DAYS for h in hi)
    b2 = all(h["net"][0] > 0 for h in hi)
    b3 = all(h["net"][0] >= a for h in hi)
    b4 = all(h["ctl"] is not None and h["net"][3] > h["ctl"][3] for h in hi)
    b5 = all(abs(h["net"][5]) >= 2.0 for h in hi)
    worst = max(2 * h["net"][4] for h in hi)
    for i, ok, what in ((1, b1, f"{MIN_BETS}+ bets and {MIN_DAYS}+ days, both"),
                        (2, b2, "net R positive at both"),
                        (3, b3, "net R beats Min60 net on the same symbols"),
                        (4, b4, "net Δ beats the random-bar control, both"),
                        (5, b5, "clustered |z| >= 2.0 on net Δ, both")):
        print(f"  bar {i}  {'PASS' if ok else 'FAIL'}  {what}")
    print(f"  power   worst MDE {worst:.3f} R"
          + ("  UNDERPOWERED" if worst > MDE_CEILING else "  (adequate)"))
    ok = all((b1, b2, b3, b4, b5))
    print(f"\n  → {'NET-POSITIVE ABOVE 1h ON A FRESH POPULATION' if ok else 'NOT ESTABLISHED'}")
    print("  Outcome C stands either way, and why 1h is a floor is still")
    print("  unexplained by anything in this sequence.")


asyncio.run(main())
