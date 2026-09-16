"""Why only 1h? A scaling diagnostic.

    python3 research/studies/fvg_why_1h.py

EXPLORATORY. No prereg, no verdict. It is a mechanism hunt, and anything it
suggests needs its own pre-registered test before it counts.

research/FVG_GROSS_EDGE.md left one fact standing: gross R for FVG grabs is
+0.045 at Min60 and about zero at Min15 and Min30. The cost explanation was
tested and failed. So what IS different about 1h?

THE CONFOUND NOBODY NAMED. "Min60, pivot 3, horizon 48 hours" is not the same
EXPERIMENT at each timeframe, it is the same numbers:

    pivot 3 bars    =  45 minutes on Min15,  3 hours on Min60
    48-hour horizon = 192 bars on Min15,    48 bars on Min60

So a Min60 grab is a structurally larger and slower event than a Min15 grab,
and it gets a quarter of the forward bars to resolve in. Two different things
change at once with the timeframe, and neither has been separated from "the
timeframe" itself.

FIVE ARMS, chosen so the answer is readable off which ones match:

    A  Min60 native      pivot 3,  window 2,  horizon  48 bars  (the baseline)
    B  Min15 scaled x4   pivot 12, window 8,  horizon 192 bars  (same PHYSICAL
                                                                 size as A)
    C  Min15 native      pivot 3,  window 2,  horizon 192 bars  (the original)
    D  Min15 native      pivot 3,  window 2,  horizon  48 bars  (isolates the
                                                                 horizon alone)
    E  Min30 scaled x2   pivot 6,  window 4,  horizon  96 bars  (same physical
                                                                 size as A)

    B ~ A and E ~ A  ->  physical size explains it. 1h is not special; the
                         structure's duration is, and Min15 can be scaled to it.
    D ~ A only       ->  the forward horizon in BARS explains it.
    neither          ->  something about the 1-hour bar itself — session
                         boundaries, funding, algo cadence — and that is a
                         different and much harder question.

Scored GROSS (fee_pct=0.0) throughout, because FVG_GROSS_EDGE showed the net
numbers are partly a stop-width artefact and the question here is about edge,
not cost. The 90 non-discovery symbols, 333 days.
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
from research.harness import simulate_market              # noqa: E402
from riptide.exchange import list_symbols                 # noqa: E402
from audit.ccp_merge_check import atr14                   # noqa: E402
from audit.ccp_at_grabs_check import grabs                # noqa: E402
from research.studies.ccp_context_filters import clustered, fvg, ATR_BUF  # noqa: E402
from research.studies.fvg_h1_holdout import DAYS          # noqa: E402

# (id, timeframe, pivot, window, horizon bars, what it isolates)
ARMS = (
    ("A", "Min60", 3, 2, 48, "baseline — the cell with the edge"),
    ("B", "Min15", 12, 8, 192, "same physical size as A"),
    ("C", "Min15", 3, 2, 192, "the original Min15 run"),
    ("D", "Min15", 3, 2, 48, "native structure, A's horizon in bars"),
    ("E", "Min30", 6, 4, 96, "same physical size as A"),
)


def build(cs, a, sym: str, pivot: int, win: int, horizon: int):
    out = []
    for pv, gb, is_high in grabs(cs, pivot, pivot):
        sig = gb + win
        lo_i, hi_i = gb - win, gb + win
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
        o = simulate_market(cs, sig, entry, stop, is_long, target_r=2.0,
                            horizon_bars=horizon, fee_pct=0.0)
        if o is None:
            continue
        out.append({"sym": sym, "t": cs[sig].t, "r": o.r,
                    "f": fvg(cs, gb, sig, is_long),
                    "risk_pct": 100.0 * abs(entry - stop) / entry})
    return out


def split(rows):
    k = [(r["sym"], r["t"] // 86400) for r in rows]
    keep = [r["r"] for r in rows if r["f"]]
    kk = [(r["sym"], r["t"] // 86400) for r in rows if r["f"]]
    drop = [r["r"] for r in rows if not r["f"]]
    dk = [(r["sym"], r["t"] // 86400) for r in rows if not r["f"]]
    if not keep or not drop:
        return None
    mk, sk, nk = clustered(keep, kk)
    md, sd, _ = clustered(drop, dk)
    se = math.sqrt(sk * sk + sd * sd)
    return mk, sk, nk, md, mk - md, se, (mk - md) / se if se > 0 else float("nan")


async def main() -> None:
    print(__doc__.split("\n\n")[0])
    print("\nEXPLORATORY mechanism hunt. Gross R throughout. No verdict.\n")
    cache: dict[str, dict] = {}
    res = {}
    async with aiohttp.ClientSession() as sess:
        syms = [s for s in await list_symbols(sess) if s not in set(DISCOVERY)]
        print(f"{'arm':<4}{'tf':<7}{'pivot':>6}{'win':>5}{'horiz':>7}"
              f"{'n FVG':>8}{'gross R':>10}{'SE':>7}{'Δ':>9}{'z':>7}"
              f"{'risk%':>7}   isolates")
        print("-" * 104)
        for aid, tf, pivot, win, horizon, note in ARMS:
            if tf not in cache:
                cache[tf] = await load_universe(sess, syms, tf, DAYS)
            rows = []
            for sym, cs in cache[tf].items():
                rows += build(cs, atr14(cs), sym, pivot, win, horizon)
            g = split(rows) if rows else None
            if g is None:
                print(f"{aid:<4}{tf:<7}{pivot:>6}{win:>5}{horizon:>7}"
                      f"      nothing scored")
                continue
            mk, sk, nk, md, d, se, z = g
            risk = sorted(r["risk_pct"] for r in rows)
            print(f"{aid:<4}{tf:<7}{pivot:>6}{win:>5}{horizon:>7}{nk:>8}"
                  f"{mk:>10.3f}{sk:>7.3f}{d:>9.3f}{z:>7.2f}"
                  f"{risk[len(risk)//2]:>7.2f}   {note}")
            res[aid] = (mk, sk, nk, d, z)

    print("\n═══ WHICH MECHANISM ═══")
    if "A" not in res:
        print("  baseline missing; nothing to compare")
        return
    a_m, a_se = res["A"][0], res["A"][1]
    print(f"  A (Min60 native) gross R {a_m:+.3f} ± {a_se:.3f}\n")
    for aid in ("B", "E", "C", "D"):
        if aid not in res:
            continue
        m, se, n, d, z = res[aid]
        gap = m - a_m
        gse = math.sqrt(se * se + a_se * a_se)
        near = abs(gap) <= 2 * gse
        print(f"  {aid}: gross R {m:+.3f} ± {se:.3f}   vs A {gap:+.3f} ± {gse:.3f}"
              f"   {'matches A' if near else 'DIFFERS from A'}")
    print("\n  B and E matching A  → physical size, not the timeframe.")
    print("  D matching A alone  → the forward horizon in bars.")
    print("  neither             → something about the 1-hour bar itself.")
    print("\n  Whatever this suggests needs its own prereg. A mechanism found")
    print("  by comparing five arms is a hypothesis, not a finding.")


asyncio.run(main())
