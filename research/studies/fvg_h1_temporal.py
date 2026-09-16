"""Temporal holdout: does the FVG/1h result survive a different regime?

Pre-registered in PREREG_fvg_h1_temporal.md, committed before this ran.

    python3 research/studies/fvg_h1_temporal.py

The cross-sectional confirmation had one hole its design could not close: every
symbol in it traded the same 333 days as the discovery, so a regime effect
would appear in both and look exactly like a confirmation.

This fetches 1,200 days and scores ONLY what happened before that window. Zero
overlap is enforced twice — candles at or after the cutoff are discarded before
anything is scored, and a signal is dropped unless its whole 48-hour horizon
also lands before the cutoff, because a trade opening before the cutoff and
resolving after it would be scored partly on discovery data.

build(), split(), the FVG rule and every constant are IMPORTED from
fvg_h1_holdout, so this cannot score by different rules than the run it checks.
"""
from __future__ import annotations

import asyncio
import math
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
    build, split, clustered, TF, HORIZON, MIN_BETS, MDE_CEILING)

OLD_DAYS = 1200         # how far back to fetch
CUT_DAYS = 333          # everything newer than this is the discovery window
MIN_BARS_BEFORE = 2000  # a symbol must have this much history before the cut


async def main() -> None:
    print(__doc__.split("\n\n")[0])
    cutoff = int(time.time()) - CUT_DAYS * 86400
    # A signal must also have its whole horizon before the cutoff.
    sig_cut = cutoff - HORIZON * 3600

    async with aiohttp.ClientSession() as sess:
        syms = await list_symbols(sess)
        print(f"\n{len(syms)} symbols listed, fetching {OLD_DAYS} days at {TF}")
        uni = await load_universe(sess, syms, TF, OLD_DAYS,
                                  min_bars=MIN_BARS_BEFORE)
        print(f"{len(uni)} returned enough history overall")

        rows, kept_syms = [], 0
        for sym, cs in uni.items():
            old = [c for c in cs if c.t < cutoff]
            if len(old) < MIN_BARS_BEFORE:
                continue
            kept_syms += 1
            rows += [r for r in build(old, atr14(old), sym)
                     if r["t"] < sig_cut]

    print(f"{kept_syms} symbols have {MIN_BARS_BEFORE}+ bars BEFORE the cutoff")
    if not rows:
        print("nothing scored")
        return

    lo, hi = min(r["t"] for r in rows), max(r["t"] for r in rows)
    span = (hi - lo) / 86400.0
    print(f"window: {time.strftime('%Y-%m-%d', time.gmtime(lo))} to "
          f"{time.strftime('%Y-%m-%d', time.gmtime(hi))}  ({span:.0f} days)")
    print(f"discovery window began {time.strftime('%Y-%m-%d', time.gmtime(cutoff))}"
          f" — newest signal here is {(cutoff - hi) / 86400.0:.1f} days before it")

    bk = [(r["sym"], r["t"] // 86400) for r in rows]
    bm, bse, _ = clustered([r["r"] for r in rows], bk)
    print(f"\n{len(rows)} grabs, unfiltered R {bm:+.3f} ± {bse:.3f}")

    g = split(rows, "f")
    c = split(rows, "cf", "cr")
    if g is None:
        print("no split possible")
        return
    mk, sk, nk, md, nd, d, se, z = g
    print(f"\n  FVG grabs      n {nk:>6}   R {mk:+.3f} ± {sk:.3f}")
    print(f"  no-FVG grabs   n {nd:>6}   R {md:+.3f}")
    print(f"  Δ {d:+.3f} ± {se:.3f}   z {z:+.2f}")
    if c:
        print(f"  control Δ (same filter, random bars) {c[5]:+.3f}")

    print("\n  the confirmed cross-sectional numbers, for comparison:")
    print("    FVG R +0.031 ± 0.016   Δ +0.076 ± 0.018  z +4.12  control +0.017")

    mde = 2 * se
    b1, b2, b3 = nk >= MIN_BETS, mk > 0, d > 0
    b4 = c is not None and d > c[5]
    b5 = abs(z) >= 2.0 and not math.isnan(z)
    print("\n═══ VERDICT — family size ONE, older data only ═══")
    for n_, ok, what in ((1, b1, f"{MIN_BETS}+ FVG grabs (got {nk})"),
                         (2, b2, "positive standalone R after fees"),
                         (3, b3, "beats grabs without an FVG"),
                         (4, b4, "beats the same filter on random bars"),
                         (5, b5, f"clustered |z| >= 2.0 (got {z:+.2f})")):
        print(f"  bar {n_}  {'PASS' if ok else 'FAIL'}  {what}")
    print(f"  power   MDE {mde:.3f} R"
          + ("  UNDERPOWERED — read as a bound, not a verdict"
             if mde > MDE_CEILING else "  (adequate)"))
    ok = all((b1, b2, b3, b4, b5))
    print(f"\n  → {'SURVIVES THE REGIME CHANGE' if ok else 'DOES NOT SURVIVE'}")
    if not ok and b3 and b4 and b5 and not b2:
        print("\n  This is the outcome the prereg named as most likely: the")
        print("  filter sorts grabs reliably and the subset it selects still")
        print("  does not pay after costs. Real finding, not tradeable.")


asyncio.run(main())
