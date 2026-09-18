"""Does the backup work if it CANNOT pre-empt? Runs exactly what
prereg/PREREG_undertow_late_backup.md pre-registered.

    PYTHONPATH=. python3 indicators/undertow/studies/undertow_late_backup.py

THE QUESTION. The live backup's two halves are both large and both significant
and they cancel: +0.6 R on trades it adds, -0.27 R on trades it pre-empts at a
worse price. Pre-emption exists for one mechanical reason -- the zone is nearer
than the Focus while the Focus limit is still live. Wait for that limit to
EXPIRE and pre-emption is impossible by construction.

THE COST IS KNOWN IN ADVANCE and the prereg discloses the one-symbol structural
check that found it: a candidate only reaches the Focus window's expiry if it
was not already killed by the target printing, the stop, or the bias. On BTC
30m that was 21 of 207 armed setups, and the late backup converted ONE.

SO THE DIAGNOSTIC IS THE POINT. `fillBar - armBar` for the LIVE backup's ADDED
trades, against the 20-bar window, is what says whether any late design could
ever have worked. If those fills cluster well inside the window then the +0.6 R
trades are structurally entangled with the pre-empted ones and no amount of
waiting separates them.

Metric, population and split are identical to undertow_backup.py so the two are
directly comparable. Never run by preflight.
"""
from __future__ import annotations

import dataclasses
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

from indicators.undertow.port import undertow as U               # noqa: E402
from indicators.undertow.studies.undertow_backup import (        # noqa: E402
    ALL, FRESH, decompose, per_armed, run_arm)
from indicators.undertow.studies.undertow_sweep import (         # noqa: E402
    FEE, LOADED, TFS, clustered, load)

# AS PUBLISHED, PINNED. Every setting this study's page was run under is
# named here even where it matched P's default at the time, because a default
# that later moves silently re-points a published study: `swingSrc` went from
# the bar pivot to "price move" after this ran, so without these lines the
# script would print different numbers under the same page's name. A study that
# cannot reproduce its own measurement is not a record of anything.
BASE = U.P(biasGate=U.BG_TRADEABLE, famStrict=False, armWins=False, stopSrc=U.S_PULL, useBackup=False, pinNewest=False, famPriority=False, failTest=U.T_CLOSE, biasSrc=U.BS_STRUCT, confirmOrder=U.C_EITHER, maxLive=64, feeFrac=FEE, rr=3.5,
           swingSrc=U.SW_BAR, msLen=6, msShortLen=2,
           endSweep=False, endStale=False)
LATE = dict(useBackup=True, bkWhen=U.B_LATE)

ARMS = [
    ("L0", "backup off", {}),
    ("L1", "LATE, zones — primary", LATE),
    ("L2", "CONTROL — late, midpoint", {**LATE, "bkMode": "mid"}),
    ("L3", "the LIVE backup (B3)", dict(useBackup=True)),
    ("L4", "late, wait 40", {**LATE, "bkLateBars": 40}),
    ("L5", "late, wait 10", {**LATE, "bkLateBars": 10}),
]
DESCRIPTIVE = {"L4", "L5"}


def fill_timing(tf, pairs):
    """THE REQUIRED DIAGNOSTIC. For the LIVE backup, how long after arming did
    each ADDED trade fill, against the 20-bar Focus window?

    Descriptive. It tests nothing; it says whether a late design had any
    population to work with in the first place.
    """
    from indicators.undertow.studies.undertow_sweep import quadrant
    data = LOADED[tf]
    on_p = dataclasses.replace(BASE, useBackup=True)
    lags = []
    # PER QUADRANT, not per symbol. Both halves of a symbol are indexed from 0,
    # so a bar number alone matches across them -- the same collision that made
    # the late arm report an impossible pre-emption.
    for sym, older in pairs:
        cs = data.get(sym)
        if not cs or len(cs) < 1200:
            continue
        seg, skip = quadrant(cs, older)
        off_bars = {t.armBar for t in U.run(seg, BASE, sym).real
                    if t.fillBar >= skip}
        for t in U.run(seg, on_p, sym).real:
            if t.fillBar < skip or not t.backup:
                continue
            if t.armBar in off_bars:
                continue                      # pre-empted, not added
            lags.append(t.fillBar - t.armBar)
    return sorted(lags)


def panel(tf, pairs, title):
    print(f"\n{'-' * 78}\n{tf} · {title}\n{'-' * 78}")
    print(f"  {'':3} {'arm':26} {'R/armed':>9} {'+/-':>6} {'armed':>6} "
          f"{'fills':>6} {'bk':>5}   vs L0")
    out = {}
    for aid, name, over in ARMS:
        p = dataclasses.replace(BASE, **over)
        res, armed, bk = run_arm(tf, p, pairs)
        m, se, n = per_armed(armed)
        d = ""
        if aid != "L0":
            dm = m - out["L0"]["m"]
            dse = math.sqrt(se ** 2 + out["L0"]["se"] ** 2)
            d = f"{dm:+.3f} +/- {dse:.3f} (z {dm / dse if dse else 0:+.2f})"
        print(f"  {aid:3} {name:26} {m:+9.3f} {se:6.3f} {n:6} "
              f"{len(res.real):6} {res.nBackup:5}   {d}"
              + (" ·descriptive" if aid in DESCRIPTIVE else ""))
        out[aid] = dict(m=m, se=se, n=n, res=res, armed=armed, bk=bk,
                        cap=res.nCap)
    return out


def verdict(tf, o, pairs):
    l0, l1, l2, l3 = o["L0"], o["L1"], o["L2"], o["L3"]
    d = l1["m"] - l0["m"]
    dse = math.sqrt(l1["se"] ** 2 + l0["se"] ** 2)
    z = d / dse if dse else 0.0
    dc, dcse = l1["m"] - l2["m"], math.sqrt(l1["se"] ** 2 + l2["se"] ** 2)
    dl = l1["m"] - l3["m"]

    added, preempt, na, npre = decompose(l0["armed"], l1["armed"], l1["bk"])
    nbk = l1["res"].nBackup
    cover = l0["n"] >= 300
    powered = nbk >= 100
    clean = (l0["n"] == l1["n"] == l3["n"] and l0["cap"] == 0 == l1["cap"]
             and npre == 0)

    print(f"\n  PRIMARY  L1 - L0 = {d:+.3f} R per armed setup "
          f"+/- {dse:.3f}  (z {z:+.2f})")
    print(f"    1 coverage        {l0['n']} armed, {nbk} late backups   "
          f"{'PASS' if cover and powered else 'FAIL — UNDERPOWERED, a bound'}")
    print(f"    2 not confounded  armed equal, cap 0, PRE-EMPTED = {npre}   "
          f"{'PASS' if clean else 'FAIL — VOID'}"
          + ("" if npre == 0 else
             "  ← pre-emption is impossible in this design; the code does "
             "not match the prereg"))
    print(f"    3 improves        >= +0.05 at |z| >= 2   "
          f"{'PASS' if d >= 0.05 and abs(z) >= 2 else 'FAIL'}")
    print(f"    4 beats control   L1 - L2 = {dc:+.3f} +/- {dcse:.3f}   "
          f"{'PASS' if dcse > 0 and dc >= dcse else 'FAIL'}")
    print(f"    5 beats LIVE      L1 - L3 = {dl:+.3f}   "
          f"{'PASS' if dl > 0 else 'FAIL'}   ← the hypothesis")

    if na:
        am, ase, _ = clustered(added)
        print(f"\n    the {na} late backups are worth {am:+.3f} +/- {ase:.3f} "
              f"R each  (z {am / ase if ase else 0:+.1f})")
    lags = fill_timing(tf, pairs)
    if lags:
        q = lambda f: lags[min(len(lags) - 1, int(f * len(lags)))]  # noqa: E731
        inside = sum(1 for v in lags if v < BASE.fillBars) / len(lags)
        print(f"\n  DIAGNOSTIC — the LIVE backup's {len(lags)} ADDED fills, "
              f"bars after arming (window {BASE.fillBars})")
        print(f"    median {q(.5)}   p75 {q(.75)}   p90 {q(.90)}   "
              f"max {lags[-1]}   ·   {inside * 100:.0f}% landed INSIDE the "
              f"window")
    return dict(tf=tf, d=d, dse=dse, z=z, dc=dc, dl=dl, nbk=nbk, na=na,
                bars=[cover and powered, clean, d >= 0.05 and abs(z) >= 2,
                      dcse > 0 and dc >= dcse, dl > 0])


def main():
    argv = [a for a in sys.argv[1:] if a in TFS]
    tfs = argv or list(TFS)
    for tf in tfs:
        LOADED[tf] = load(tf)
        if not LOADED[tf]:
            print(f"{tf}: no cached candles. Run undertow_sweep.py --fetch.")
            return 2

    print("UNDERTOW LATE BACKUP — does it work if it cannot pre-empt?")
    print("prereg: indicators/undertow/prereg/PREREG_undertow_late_backup.md")
    print(f"config: {BASE.tag()} maxLive {BASE.maxLive}, fees {FEE * 1e4:.0f}bp")
    print("metric: mean R per ARMED SETUP")

    vs = []
    for tf in tfs:
        o = panel(tf, ALL, "PRIMARY — all 23 symbols, both halves")
        vs.append(verdict(tf, o, ALL))
        panel(tf, FRESH, "SECOND PANEL — the quadrants the sweep never scored")

    print(f"\n{'=' * 78}\nVERDICT\n{'=' * 78}\n")
    print(f"  {'tf':8} {'L1-L0':>8} {'+/-':>6} {'z':>6} {'L1-L2':>7} "
          f"{'L1-L3':>7} {'backups':>8}")
    for v in vs:
        print(f"  {v['tf']:8} {v['d']:+8.3f} {v['dse']:6.3f} {v['z']:+6.2f} "
              f"{v['dc']:+7.3f} {v['dl']:+7.3f} {v['nbk']:8}")
    beats_live = [v for v in vs if v["bars"][4]]
    improves = [v for v in vs if v["bars"][2]]
    powered = [v for v in vs if v["bars"][0]]
    print(f"\n  5 BEATS THE LIVE BACKUP  {len(beats_live)} of {len(vs)}   "
          f"{'PASS' if len(beats_live) >= 2 else 'FAIL'}")
    print()
    if len(improves) >= 2 and len(beats_live) >= 2:
        print("  REMOVING PRE-EMPTION WORKS.")
        print("  First component of Undertow to clear its bars. It earns")
        print("  default-on, a second alert, and a forward run — not a trade.")
    elif not powered:
        print("  UNDERPOWERED, AND THAT IS THE ANSWER.")
        print("  Waiting for the Focus limit to expire removes the pre-emption")
        print("  tax and almost all the opportunity with it: the +0.6R trades")
        print("  fill INSIDE the window, so they are structurally entangled")
        print("  with the ones that cost -0.27R. No design separates them by")
        print("  waiting, because the thing that makes a trade ADDED is not")
        print("  knowable until after it has filled.")
    else:
        print("  THE LATE BACKUP DOES NOT CLEAR ITS BARS.")
        print("  Five components of Undertow have now been ablated and none")
        print("  has survived its own control. The remaining question is the")
        print("  one no backtest can answer, and the watch is already built")
        print("  for it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
