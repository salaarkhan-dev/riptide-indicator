"""Is the FVG result coherent across timeframes, or only a 1h accident?

Pre-registered in PREREG_fvg_timeframe_coherence.md, committed before this ran.

    python3 research/studies/fvg_timeframe_coherence.py

The discovery found FVG negative on Min15 and Min30 and positive only on Min60.
A real mechanism usually degrades smoothly rather than switching sign. This
runs Min15 and Min30 on the SAME 862-day temporal window that Min60 survived.

THE THREE OUTCOMES ARE FIXED IN THE PREREG, before any number existed:

    A  both negative           timeframe-specific but STABLE; Min60 stands
    B  both clearly positive   FVG is broad; discovery was noisier than
                               assumed; Min60 generalised rather than undermined
    C  mixed, or a sign flip   UNSTABLE; not established; no forward run

C is the damaging one and it is what this run is looking for.

Min60 is re-run as a PIPELINE ANCHOR, not a test. If it does not reproduce
about +0.046 the refactor is broken and every number here is void.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time

import aiohttp

sys.path.insert(0, ".")
os.environ.setdefault("RIPTIDE_DEEP_CACHE", ".cache/deep")
os.makedirs(os.environ["RIPTIDE_DEEP_CACHE"], exist_ok=True)

from research.deep import load_universe                   # noqa: E402
from riptide.exchange import list_symbols                 # noqa: E402
from audit.ccp_merge_check import atr14                   # noqa: E402
from research.studies.fvg_h1_holdout import (             # noqa: E402
    build, split, clustered, MIN_BETS)

OLD_DAYS = 1200
CUT_DAYS = 333
MIN_BARS_BEFORE = 2000
BAR_SEC = {"Min15": 900, "Min30": 1800, "Min60": 3600}

# (timeframe, horizon bars = 48h, the discovery's sign on this timeframe)
RUNS = (
    ("Min15", 192, "NEGATIVE (-0.094)"),
    ("Min30", 96, "NEGATIVE (-0.056)"),
    ("Min60", 48, "ANCHOR, not a test — expect about +0.046"),
)


async def one(sess, tf: str, horizon: int, cutoff: int):
    sig_cut = cutoff - horizon * BAR_SEC[tf]
    uni = await load_universe(sess, await list_symbols(sess), tf, OLD_DAYS,
                              min_bars=MIN_BARS_BEFORE)
    rows, kept = [], 0
    for sym, cs in uni.items():
        old = [c for c in cs if c.t < cutoff]
        if len(old) < MIN_BARS_BEFORE:
            continue
        kept += 1
        rows += [r for r in build(old, atr14(old), sym, horizon)
                 if r["t"] < sig_cut]
    return rows, kept


async def main() -> None:
    print(__doc__.split("\n\n")[0])
    cutoff = int(time.time()) - CUT_DAYS * 86400
    print(f"\ntemporal window ends {time.strftime('%Y-%m-%d', time.gmtime(cutoff))}"
          f" — the discovery window starts there\n")

    results = {}
    async with aiohttp.ClientSession() as sess:
        for tf, horizon, note in RUNS:
            rows, kept = await one(sess, tf, horizon, cutoff)
            if not rows:
                print(f"{tf}: nothing scored\n")
                continue
            lo, hi = min(r["t"] for r in rows), max(r["t"] for r in rows)
            bk = [(r["sym"], r["t"] // 86400) for r in rows]
            bm, bse, _ = clustered([r["r"] for r in rows], bk)
            g = split(rows, "f")
            c = split(rows, "cf", "cr")
            print(f"═══ {tf} — discovery said {note} ═══")
            print(f"  {kept} symbols, {len(rows)} grabs, "
                  f"{time.strftime('%Y-%m-%d', time.gmtime(lo))} to "
                  f"{time.strftime('%Y-%m-%d', time.gmtime(hi))}")
            print(f"  unfiltered R {bm:+.3f} ± {bse:.3f}")
            if g is None:
                print("  no split possible\n")
                continue
            mk, sk, nk, md, nd, d, se, z = g
            print(f"  FVG grabs      n {nk:>6}   R {mk:+.3f} ± {sk:.3f}")
            print(f"  no-FVG grabs   n {nd:>6}   R {md:+.3f}")
            print(f"  Δ {d:+.3f} ± {se:.3f}   z {z:+.2f}"
                  + (f"   control Δ {c[5]:+.3f}" if c else ""))
            if nk < MIN_BETS:
                print(f"  NOT MEASURABLE — {nk} < {MIN_BETS} FVG grabs")
            print()
            results[tf] = (mk, sk, nk, d, z)

    print("═══ WHICH OUTCOME ═══")
    a60 = results.get("Min60")
    if a60:
        ok = 0.02 <= a60[0] <= 0.08
        print(f"  anchor Min60 R {a60[0]:+.3f}  "
              f"{'reproduces — pipeline sound' if ok else 'DOES NOT REPRODUCE — every number here is void'}")
    tested = [results.get(t) for t in ("Min15", "Min30")]
    tested = [x for x in tested if x and x[2] >= MIN_BETS]
    if len(tested) < 2:
        print("  not both timeframes measurable; no outcome assigned")
        return
    signs = {x[0] > 0 for x in tested}
    strong = all(abs(x[0]) > 2 * x[1] for x in tested)
    if len(signs) == 2:
        out = ("C", "mixed signs across adjacent timeframes — UNSTABLE, "
                    "not established, no forward run")
    elif signs == {False}:
        out = ("A", "both negative as the discovery found — timeframe-specific "
                    "but STABLE across regime and universe; Min60 stands")
    elif strong:
        out = ("B", "both clearly positive — FVG is broad, the discovery's "
                    "negatives were noise; Min60 generalised, not undermined")
    else:
        out = ("C", "positive but not clearly so, against the discovery's "
                    "negatives — a sign flip that does not replace it. "
                    "UNSTABLE, not established")
    print(f"\n  → OUTCOME {out[0]}: {out[1]}")


asyncio.run(main())
