"""Does the FVG gradient continue above 1h?

Pre-registered in PREREG_fvg_higher_tf.md, committed before this ran.

    python3 indicators/ccp/studies/fvg_higher_tf.py

FVG_WHY_1H held physical structure size and forward horizon CONSTANT and varied
only the bar interval, and the edge still fell as the bars got finer:
Min60 +0.044, Min30 +0.023, Min15 +0.008. Two readings survive that and they
predict opposite things above 1h.

    the gradient is real  ->  Hour4 and Hour8 keep rising past +0.044
    A is the lucky cell   ->  they scatter around zero

Every arm uses pivot 3, window 2, horizon 48 BARS — arm A's configuration
exactly, with only the bar interval changing. Holding 48 hours instead would
give Hour8 six bars to resolve in, and FVG_WHY_1H's arm D already showed a
starved bar-horizon is actively harmful.

The anchor is a pipeline check, not a test. Its window contains the discovery
period and it has been measured four times; H4 and H8 are what is new here, and
no Hour4 or Hour8 test has ever been run on any window.
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
from indicators.ccp.studies.ccp_context_filters import (  # noqa: E402
    ATR_BUF, clustered, fvg)

PIVOT, WIN, HORIZON = 3, 2, 48
DAYS = 1200
MIN_BARS = 1500
MIN_BETS = 300
MIN_DAYS = 300
MDE_CEILING = 0.15

# (id, timeframe, seconds per bar, is it a test?)
ARMS = (("anchor", "Min60", 3600, False),
        ("H4", "Hour4", 14400, True),
        ("H8", "Hour8", 28800, True))


def build(cs, a, sym: str):
    out = []
    for pv, gb, is_high in grabs(cs, PIVOT, PIVOT):
        sig = gb + WIN
        lo_i, hi_i = gb - WIN, gb + WIN
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
                            horizon_bars=HORIZON, fee_pct=0.0)
        net = simulate_market(cs, sig, entry, stop, is_long, target_r=2.0,
                              horizon_bars=HORIZON)
        if o is None or net is None:
            continue
        row = {"sym": sym, "t": cs[sig].t, "r": o.r, "net": net.r,
               "f": fvg(cs, gb, sig, is_long), "cr": None, "cnet": None, "cf": None,
               "risk_pct": 100.0 * abs(entry - stop) / entry}
        rnd = random.Random(f"h|{sym}|{gb}")
        frac = abs(entry - stop) / entry
        for _ in range(4):
            j = rnd.randrange(70, len(cs) - HORIZON - 1)
            if a[j] is None:
                continue
            e2 = cs[j].c
            s2 = e2 - e2 * frac if is_long else e2 + e2 * frac
            co = simulate_market(cs, j, e2, s2, is_long, target_r=2.0,
                                 horizon_bars=HORIZON, fee_pct=0.0)
            cn = simulate_market(cs, j, e2, s2, is_long, target_r=2.0,
                                 horizon_bars=HORIZON)
            if co is None or cn is None:
                continue
            row["cr"] = co.r
            row["cnet"] = cn.r
            row["cf"] = fvg(cs, j, j, is_long)
            break
        out.append(row)
    return out


def split(rows, key, col):
    keep = [(r[col], (r["sym"], r["t"] // 86400)) for r in rows
            if r[key] is True and r[col] is not None]
    drop = [(r[col], (r["sym"], r["t"] // 86400)) for r in rows
            if r[key] is False and r[col] is not None]
    if not keep or not drop:
        return None
    mk, sk, nk = clustered([v for v, _ in keep], [k for _, k in keep])
    md, sd, _ = clustered([v for v, _ in drop], [k for _, k in drop])
    se = math.sqrt(sk * sk + sd * sd)
    return mk, sk, nk, mk - md, se, (mk - md) / se if se > 0 else float("nan")


async def main() -> None:
    print(__doc__.split("\n\n")[0])
    print("\nGross R. pivot 3 / window 2 / horizon 48 BARS at every arm.\n")
    res = {}
    async with aiohttp.ClientSession() as sess:
        syms = [s for s in await list_symbols(sess) if s not in set(DISCOVERY)]
        print(f"{'arm':<8}{'tf':<7}{'syms':>6}{'days':>7}{'n FVG':>8}"
              f"{'gross R':>10}{'SE':>7}{'Δ':>9}{'z':>7}{'ctlΔ':>9}{'risk%':>7}")
        print("-" * 88)
        for aid, tf, sec, is_test in ARMS:
            uni = await load_universe(sess, syms, tf, DAYS, min_bars=MIN_BARS)
            rows = []
            for sym, cs in uni.items():
                rows += build(cs, atr14(cs), sym)
            if not rows:
                print(f"{aid:<8}{tf:<7}  nothing scored")
                continue
            span = (max(r["t"] for r in rows) - min(r["t"] for r in rows)) / 86400
            g = split(rows, "f", "r")
            c = split(rows, "cf", "cr")
            if g is None:
                print(f"{aid:<8}{tf:<7}  no split")
                continue
            mk, sk, nk, d, se, z = g
            risk = sorted(r["risk_pct"] for r in rows)
            print(f"{aid:<8}{tf:<7}{len(uni):>6}{span:>7.0f}{nk:>8}"
                  f"{mk:>10.3f}{sk:>7.3f}{d:>9.3f}{z:>7.2f}"
                  f"{(c[3] if c else float('nan')):>9.3f}"
                  f"{risk[len(risk)//2]:>7.2f}")
            res[aid] = dict(m=mk, se=sk, n=nk, d=d, dse=se, z=z,
                            ctl=(c[3] if c else None), span=span)

    print("\n═══ VERDICT ═══")
    if not all(k in res for k in ("anchor", "H4", "H8")):
        print("  an arm is missing; no verdict")
        return
    a = res["anchor"]["m"]
    hi = [res["H4"], res["H8"]]
    mean_hi = sum(h["m"] for h in hi) / 2
    print(f"  anchor Min60 gross {a:+.3f}   H4 {res['H4']['m']:+.3f}   "
          f"H8 {res['H8']['m']:+.3f}   mean of the two {mean_hi:+.3f}\n")
    b1 = all(h["n"] >= MIN_BETS and h["span"] >= MIN_DAYS for h in hi)
    b2 = all(h["m"] > 0 for h in hi)
    b3 = mean_hi >= a
    b4 = all(h["ctl"] is not None and h["d"] > h["ctl"] for h in hi)
    b5 = all(abs(h["z"]) >= 2.0 for h in hi)
    worst = max(2 * h["dse"] for h in hi)
    for n_, ok, what in ((1, b1, f"{MIN_BETS}+ bets and {MIN_DAYS}+ days, both"),
                         (2, b2, "gross R positive at both"),
                         (3, b3, "mean of H4 and H8 >= the anchor"),
                         (4, b4, "gross Δ beats the random-bar control, both"),
                         (5, b5, "clustered |z| >= 2.0 on gross Δ, both")):
        print(f"  bar {n_}  {'PASS' if ok else 'FAIL'}  {what}")
    print(f"  power   worst MDE {worst:.3f} R"
          + ("  UNDERPOWERED" if worst > MDE_CEILING else "  (adequate)"))
    ok = all((b1, b2, b3, b4, b5))
    print(f"\n  → {'THE GRADIENT CONTINUES' if ok else 'THE GRADIENT DOES NOT CONTINUE'}")
    if not ok:
        # The prereg's "if it fails" paragraph assumed ONE failure mode: the
        # higher timeframes scattering around zero. That reading only applies
        # if they actually did. Printing it unconditionally would assert
        # something the data may flatly contradict, which is how a
        # pre-written conclusion becomes a false one.
        scattered = all(abs(h["m"]) < 2 * h["se"] for h in hi)
        if scattered:
            print("  Both higher timeframes are indistinguishable from zero,")
            print("  which is what the noise explanation predicted. The three")
            print("  pre-registered passes stand as recorded; the conclusion")
            print("  drawn from them does not.")
        else:
            print("  BUT NOT BY SCATTERING AROUND ZERO, which is the only")
            print("  failure mode the prereg wrote a conclusion for. The")
            print("  higher timeframes are positive, so the noise explanation")
            print("  is NOT supported either. Neither pre-registered story")
            print("  fits; see the writeup before reading anything into this.")


if __name__ == "__main__":
    # Guarded because fvg_net_higher_tf.py imports build() and the constants
    # from here. Without it the import re-ran this entire
    # study first — 1,200 days across three timeframes — and wrote its output
    # into the other study's file.
    asyncio.run(main())
