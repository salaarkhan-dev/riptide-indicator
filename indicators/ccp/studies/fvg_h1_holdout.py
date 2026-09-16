"""Confirmatory: does the FVG/1h result hold on 90 symbols it has never seen?

Pre-registered in PREREG_fvg_h1_holdout.md, committed before this ran.

    python3 indicators/ccp/studies/fvg_h1_holdout.py

ONE hypothesis, one timeframe, one arm, one population. The discovery ran 36
panel-level cells and this runs one, so there is no multiple-comparison
correction to argue about — which is the entire advantage of a confirmatory
run and the reason nothing else is bolted on here.

Everything that defines the test — the FVG rule, the stop, the target, the
horizon, the pivot width — is IMPORTED from
indicators/ccp/studies/ccp_context_filters.py rather than restated. A copy
would be free to drift, and a holdout testing a subtly different filter tests
nothing.
"""
from __future__ import annotations

import asyncio
import math
import os
import random
import statistics
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
from indicators.ccp.studies.ccp_context_filters import (        # noqa: E402
    fvg, clustered, PIVOT, CCP_FWD, CCP_BACK, ATR_BUF, DAYS)

TF, HORIZON = "Min60", 48
MIN_BETS = 300          # bar 1
MDE_CEILING = 0.15      # bar: above this the run is a bound, not a verdict


def build(cs, a, sym: str, horizon: int = HORIZON):
    """Every grab, the plain 2R exit, and whether F2 held. Nothing else.

    `horizon` is a parameter only so fvg_timeframe_coherence.py can reuse
    this exact function at Min15 and Min30. The default is Min60's, so
    every existing caller is unchanged.
    """
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
        o = simulate_market(cs, sig, entry, stop, is_long,
                            target_r=2.0, horizon_bars=horizon)
        if o is None:
            continue
        row = {"sym": sym, "t": cs[sig].t, "r": o.r,
               "f": fvg(cs, gb, sig, is_long), "cr": None, "cf": None,
               "bars": len(cs)}
        # Bar 4's control: same filter, random bar, matched direction and risk.
        rnd = random.Random(f"h|{sym}|{gb}")
        frac = abs(entry - stop) / entry
        for _ in range(4):
            j = rnd.randrange(70, len(cs) - horizon - 1)
            if a[j] is None:
                continue
            e2 = cs[j].c
            s2 = e2 - e2 * frac if is_long else e2 + e2 * frac
            co = simulate_market(cs, j, e2, s2, is_long,
                                 target_r=2.0, horizon_bars=horizon)
            if co is None:
                continue
            row["cr"] = co.r
            row["cf"] = fvg(cs, j, j, is_long)
            break
        out.append(row)
    return out


def split(rows, key, rkey="r"):
    k = [(r["sym"], r["t"] // 86400) for r in rows if r[key] is not None]
    keep = [r[rkey] for r in rows if r[key] is True and r[rkey] is not None]
    kk = [(r["sym"], r["t"] // 86400) for r in rows
          if r[key] is True and r[rkey] is not None]
    drop = [r[rkey] for r in rows if r[key] is False and r[rkey] is not None]
    dk = [(r["sym"], r["t"] // 86400) for r in rows
          if r[key] is False and r[rkey] is not None]
    if not keep or not drop:
        return None
    mk, sk, nk = clustered(keep, kk)
    md, sd, nd = clustered(drop, dk)
    se = math.sqrt(sk * sk + sd * sd)
    return mk, sk, nk, md, nd, mk - md, se, (mk - md) / se if se > 0 else float("nan")


async def main() -> None:
    print(__doc__.split("\n\n")[0])
    async with aiohttp.ClientSession() as sess:
        allsym = await list_symbols(sess)
        holdout = [s for s in allsym if s not in set(DISCOVERY)]
        print(f"\n{len(allsym)} listed, {len(DISCOVERY)} used by the discovery, "
              f"{len(holdout)} in the holdout")
        uni = await load_universe(sess, holdout, TF, DAYS)
        print(f"{len(uni)} of them have 2000+ bars at {TF}\n")

        rows = []
        for sym, cs in uni.items():
            rows += build(cs, atr14(cs), sym)

    if not rows:
        print("nothing scored")
        return

    base, bk = [r["r"] for r in rows], [(r["sym"], r["t"] // 86400) for r in rows]
    bm, bse, _ = clustered(base, bk)
    print(f"{len(rows)} grabs, unfiltered R {bm:+.3f} ± {bse:.3f}")

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

    # Descriptive only, per the prereg: an effect living in the thinnest
    # symbols is an artefact of a fixed fee assumption, not an edge.
    med = statistics.median(r["bars"] for r in rows)
    print("\n  robustness, DESCRIPTIVE — cannot rescue a failure:")
    for name, sel in (("more history", lambda r: r["bars"] >= med),
                      ("less history", lambda r: r["bars"] < med)):
        sub = [r for r in rows if sel(r) and r["f"]]
        if len(sub) > 20:
            m, s_, n = clustered([r["r"] for r in sub],
                                 [(r["sym"], r["t"] // 86400) for r in sub])
            print(f"    {name:<14} n {n:>6}   R {m:+.3f} ± {s_:.3f}")

    mde = 2 * se
    b1, b2, b3 = nk >= MIN_BETS, mk > 0, d > 0
    b4 = c is not None and d > c[5]
    b5 = abs(z) >= 2.0 and not math.isnan(z)
    print("\n═══ VERDICT — family size ONE, no correction to argue about ═══")
    for n_, ok, what in ((1, b1, f"{MIN_BETS}+ FVG grabs (got {nk})"),
                         (2, b2, "positive standalone R after fees"),
                         (3, b3, "beats grabs without an FVG"),
                         (4, b4, "beats the same filter on random bars"),
                         (5, b5, f"clustered |z| >= 2.0 (got {z:+.2f})")):
        print(f"  bar {n_}  {'PASS' if ok else 'FAIL'}  {what}")
    print(f"  power   MDE {mde:.3f} R"
          + ("  UNDERPOWERED — read as a bound, not a verdict"
             if mde > MDE_CEILING else "  (adequate)"))
    print(f"\n  → {'CONFIRMED' if all((b1, b2, b3, b4, b5)) else 'NOT CONFIRMED'}")


if __name__ == "__main__":
    # Guarded because fvg_h1_temporal.py imports build() from here. The temporal holdout must score with the EXACT same rules as the
    # confirmation it is checking; importing makes drift impossible.
    asyncio.run(main())
