"""Is the FVG edge constant GROSS, with fees explaining the timeframe spread?

Pre-registered in PREREG_fvg_gross_edge.md, committed before this ran.

    python3 indicators/ccp/studies/fvg_gross_edge.py

FVG_TIMEFRAME_COHERENCE returned OUTCOME C and the line stopped. Writing it up
I noticed — AFTER seeing the numbers — that adding the measured fee drag back
gave implied gross edges of +0.092, +0.093 and +0.103. That was post-hoc and
worth nothing. This turns it into a test.

A PASS DOES NOT REINSTATE THE Min60 RESULT. Outcome C stands whatever this
returns.

The flaw that produced outcome C was a Min15 panel covering 25 days against 862
for the others. Here every panel is the same 333-day window on the same 90
non-discovery symbols, and bar 1 carries a TIME-SPAN floor as well as a bet
floor.

Each timeframe is scored twice on the IDENTICAL setups — once with the
harness's fees, once with fee_pct=0.0 — so gross and net differ by the fee and
nothing else, and the drag is measured here rather than borrowed.
"""
from __future__ import annotations

import asyncio
import math
import os
import random
import sys

import aiohttp

sys.path.insert(0, ".")
os.environ.setdefault("RIPTIDE_DEEP_CACHE", ".cache/deep")
os.makedirs(os.environ["RIPTIDE_DEEP_CACHE"], exist_ok=True)

from research.data import SYMBOLS as DISCOVERY            # noqa: E402
from research.deep import load_universe                   # noqa: E402
from research.harness import simulate_market              # noqa: E402
from riptide.exchange import list_symbols                 # noqa: E402
from indicators.ccp.tools.ccp_merge_check import atr14  # noqa: E402
from indicators.ccp.tools.ccp_at_grabs_check import grabs  # noqa: E402
from indicators.ccp.studies.ccp_context_filters import clustered  # noqa: E402
from indicators.ccp.studies.fvg_h1_holdout import DAYS          # noqa: E402
from indicators.ccp.detector import ratios                  # noqa: E402
from indicators.ccp.studies.ccp_context_filters import (        # noqa: E402
    fvg, PIVOT, CCP_FWD, CCP_BACK, ATR_BUF)

TFS = (("Min15", 192), ("Min30", 96), ("Min60", 48))
MIN_BETS = 300
MIN_DAYS = 300
MDE_CEILING = 0.10
FLAT_BAND = 0.04        # bar 3: max - min of the three gross values


def build(cs, a, sym: str, horizon: int):
    """One row per grab, scored TWICE on the same setup: net and gross."""
    out = []
    for pv, gb, is_high in grabs(cs, PIVOT, PIVOT):
        sig = gb + CCP_FWD
        lo_i, hi_i = gb - CCP_BACK, gb + CCP_FWD
        if lo_i < 0 or sig >= len(cs) - 1 or sig < 60:
            continue
        if a[sig] is None or a[gb] is None:
            continue
        is_long = not is_high
        entry = cs[sig].c
        buf = a[sig] * ATR_BUF
        stop = (min(cs[k].l for k in range(lo_i, hi_i + 1)) - buf if is_long
                else max(cs[k].h for k in range(lo_i, hi_i + 1)) + buf)
        if (stop >= entry) if is_long else (stop <= entry):
            continue
        net = simulate_market(cs, sig, entry, stop, is_long,
                              target_r=2.0, horizon_bars=horizon)
        gro = simulate_market(cs, sig, entry, stop, is_long, target_r=2.0,
                              horizon_bars=horizon, fee_pct=0.0)
        if net is None or gro is None:
            continue
        row = {"sym": sym, "t": cs[sig].t, "net": net.r, "gross": gro.r,
               "f": fvg(cs, gb, sig, is_long),
               "risk_pct": 100.0 * abs(entry - stop) / entry,
               "cnet": None, "cgross": None, "cf": None}
        rnd = random.Random(f"g|{sym}|{gb}")
        frac = abs(entry - stop) / entry
        for _ in range(4):
            j = rnd.randrange(70, len(cs) - horizon - 1)
            if a[j] is None:
                continue
            e2 = cs[j].c
            s2 = e2 - e2 * frac if is_long else e2 + e2 * frac
            cg = simulate_market(cs, j, e2, s2, is_long, target_r=2.0,
                                 horizon_bars=horizon, fee_pct=0.0)
            if cg is None:
                continue
            row["cgross"] = cg.r
            row["cf"] = fvg(cs, j, j, is_long)
            break
        out.append(row)
    return out


def diff(rows, key, col):
    keep = [(r[col], (r["sym"], r["t"] // 86400)) for r in rows
            if r[key] is True and r[col] is not None]
    drop = [(r[col], (r["sym"], r["t"] // 86400)) for r in rows
            if r[key] is False and r[col] is not None]
    if not keep or not drop:
        return None
    mk, sk, nk = clustered([v for v, _ in keep], [k for _, k in keep])
    md, sd, _ = clustered([v for v, _ in drop], [k for _, k in drop])
    se = math.sqrt(sk * sk + sd * sd)
    return mk, sk, nk, md, mk - md, se, (mk - md) / se if se > 0 else float("nan")


async def main() -> None:
    print(__doc__.split("\n\n")[0])
    async with aiohttp.ClientSession() as sess:
        syms = [s for s in await list_symbols(sess) if s not in set(DISCOVERY)]
        print(f"\n{len(syms)} non-discovery symbols, {DAYS} days, "
              f"the same window at every timeframe\n")
        res = {}
        for tf, horizon in TFS:
            uni = await load_universe(sess, syms, tf, DAYS)
            rows = []
            for sym, cs in uni.items():
                rows += build(cs, atr14(cs), sym, horizon)
            if not rows:
                continue
            span = (max(r["t"] for r in rows) - min(r["t"] for r in rows)) / 86400
            g = diff(rows, "f", "gross")
            n = diff(rows, "f", "net")
            c = diff(rows, "cf", "cgross")
            if g is None or n is None:
                continue
            risk = sorted(r["risk_pct"] for r in rows)
            med = risk[len(risk) // 2]
            drag = g[0] - n[0]
            # the fee rate at which net crosses zero, arithmetic not a test
            be = n[0] and (g[0] / (drag / 0.044)) if drag > 0 else float("nan")
            print(f"═══ {tf} — {len(uni)} symbols, {len(rows)} grabs, "
                  f"{span:.0f} days ═══")
            print(f"  FVG grabs   n {g[2]:>6}")
            print(f"    GROSS  R {g[0]:+.3f} ± {g[1]:.3f}   "
                  f"Δ {g[4]:+.3f} ± {g[5]:.3f}  z {g[6]:+.2f}"
                  + (f"   control Δ {c[4]:+.3f}" if c else ""))
            print(f"    net    R {n[0]:+.3f} ± {n[1]:.3f}   "
                  f"Δ {n[4]:+.3f}")
            print(f"    fee drag {drag:.3f} R at {med:.2f}% median risk"
                  f"   break-even fee ≈ {be:.3f}% round trip")
            print()
            res[tf] = dict(gross=g, net=n, ctl=c, span=span, drag=drag)

    print("═══ VERDICT ═══")
    if len(res) < 3:
        print("  fewer than three timeframes measurable; no verdict")
        return
    gs = [res[t]["gross"][0] for t, _ in TFS]
    spread = max(gs) - min(gs)
    b1 = all(res[t]["gross"][2] >= MIN_BETS and res[t]["span"] >= MIN_DAYS
             for t, _ in TFS)
    b2 = all(v > 0 for v in gs)
    b3 = spread <= FLAT_BAND
    b4 = all(res[t]["ctl"] is not None and
             res[t]["gross"][4] > res[t]["ctl"][4] for t, _ in TFS)
    b5 = all(abs(res[t]["gross"][6]) >= 2.0 for t, _ in TFS)
    worst = max(2 * res[t]["gross"][5] for t, _ in TFS)
    print(f"  gross R by timeframe: "
          + "  ".join(f"{t} {res[t]['gross'][0]:+.3f}" for t, _ in TFS))
    print(f"  spread {spread:.3f} R against a {FLAT_BAND} band\n")
    for n_, ok, what in ((1, b1, f"{MIN_BETS}+ bets AND {MIN_DAYS}+ days, every timeframe"),
                         (2, b2, "gross R positive on all three"),
                         (3, b3, f"gross R flat within {FLAT_BAND} R"),
                         (4, b4, "gross Δ beats the random-bar control, all three"),
                         (5, b5, "clustered |z| >= 2.0 on gross Δ, all three")):
        print(f"  bar {n_}  {'PASS' if ok else 'FAIL'}  {what}")
    print(f"  power   worst MDE {worst:.3f} R"
          + ("  UNDERPOWERED" if worst > MDE_CEILING else "  (adequate)"))
    ok = all((b1, b2, b3, b4, b5))
    print(f"\n  → {'THE EDGE IS FLAT GROSS; FEES EXPLAIN THE SPREAD' if ok else 'NOT SUPPORTED'}")
    print("  Outcome C stands either way — this explains, it does not reinstate.")


asyncio.run(main())
