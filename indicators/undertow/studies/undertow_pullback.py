"""The three pullback defects in SPEC.md 2.3b — do fixing them help?

    PYTHONPATH=. python3 indicators/undertow/studies/undertow_pullback.py

Runs exactly what prereg/PREREG_undertow_pullback.md pre-registered.

THE DEFECTS, measured in SPEC 2.3b: the bar that makes a new trend extreme is
immediately its own "pullback extreme"; there is no minimum pullback in bars or
in price; and only ONE bar can ever be the pin, so a doji at the extreme
discards the whole pullback.

THEY PULL IN OPPOSITE DIRECTIONS, which is the design problem. locTol loosens,
the two minimums tighten, and three knobs at four levels is 64 configurations
and a maximum -- the -0.31 R per trade UNDERTOW_PARAMS.md measured as the cost
of selecting from a chart. So ONE primary is fixed in the prereg and no maximum
is taken.

THE DECOMPOSITION IS THE USEFUL PART. A1 both adds and removes setups, so every
A1 trade is labelled against A0 -- SHARED, ADDED (the locTol loosening) or
DROPPED (the pbMinDepth tightening) -- and each is scored on its own, the way
UNDERTOW_BACKUP_FILL.md split its population. That split is where that study's
only real signal came from.

THE CONTROL IS SAMPLED FROM THE WHOLE SERIES, and this file does NOT reuse
undertow_sweep.control(). That helper draws its random entries from a QUADRANT
(`older=True` is bars 0..mid), which is right for the studies that score a
quadrant and wrong here, where the real trades span all 12,000 bars. In
undertow_htf and undertow_mtf the mismatch is harmless because their bar 4 is a
random GATE and the random-entry number is reported only; here bar 4 IS this
control, so it is built to match.
"""
from __future__ import annotations

import dataclasses
import math
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

from indicators.undertow.port import undertow as U               # noqa: E402
from indicators.undertow.studies.undertow_sweep import (         # noqa: E402
    FEE, LOADED, SEED, TFS, clustered, load)
from research.symbols_fresh import (SYMBOLS_FRESH4,              # noqa: E402
                                    assert_disjoint)
from riptide.config import BAR_SECONDS                           # noqa: E402

# AS PUBLISHED, PINNED — see test_studies_pin_their_settings.py. The SHIPPED
# Ending rules, because this study is about the pullback and everything else
# has to be what the chart runs.
BASE = U.P(pinPick=U.PICK_READY, pinAt=U.PIN_PULL, pinLag=0, biasGate=U.BG_TRADEABLE, famStrict=False, armWins=False, stopSrc=U.S_PULL, useBackup=False, pinNewest=False, famPriority=False, failTest=U.T_CLOSE, biasSrc=U.BS_STRUCT, confirmOrder=U.C_EITHER, maxLive=64, feeFrac=FEE, rr=3.5,
           swingSrc=U.SW_RANGE, msLen=6, msShortLen=2,
           endMinor=U.E_FLIP, endSweep=False, endStale=False, retraceMax=70)

ARMS = [
    ("A0", "shipped — 0 / 0 / 0.00", {}),
    ("A1", "locTol 2 + depth 0.20 — PRIMARY", dict(locTol=2, pbMinDepth=0.20)),
    ("A2", "locTol 2 alone (defect 3)", dict(locTol=2)),
    ("A3", "depth 0.20 alone (defect 2)", dict(pbMinDepth=0.20)),
    ("A4", "pbMinAge 3 alone — the BAR unit", dict(pbMinAge=3)),
]
PRIMARY, DESCRIPTIVE = "A1", {"A2", "A3", "A4"}
MIN_BARS = 11000


def key(t):
    """One trade's identity. The pin bar and the arming bar together, because
    two candidates can arm on the same bar from different pins -- that exact
    collision cost two bugs in the backup study before its matcher was keyed
    this way. Asserted collision-free below rather than assumed."""
    return (t.symbol, t.bar, t.armBar, t.short)


def control_full(trades, tf, seed=SEED):
    """One seeded random entry per real trade, drawn from the WHOLE series.

    Same symbol, same direction, same risk in price, same rr, same maximum
    holding window, resolved with the same rules -- stop first when one bar
    spans both. The only difference is WHEN it entered.
    """
    rnd = random.Random(seed)
    out = []
    for t in trades:
        cs = LOADED[tf].get(t.symbol)
        if not cs:
            continue
        hold = max(1, t.exitBar - t.fillBar)
        lo, hi = 0, len(cs) - hold - 2
        if hi <= lo:
            continue
        risk = abs(t.stop - t.entry)
        if risk <= 0:
            continue
        i = rnd.randint(lo, hi)
        entry = cs[i].c
        stop = entry + risk if t.short else entry - risk
        tgt = entry - BASE.rr * risk if t.short else entry + BASE.rr * risk
        r = None
        for j in range(i + 1, min(i + 1 + hold, len(cs))):
            b = cs[j]
            lost = b.h >= stop if t.short else b.l <= stop
            won = b.l <= tgt if t.short else b.h >= tgt
            if lost:
                r = -1.0
                break
            if won:
                r = BASE.rr
                break
        if r is None:
            # MARKED TO MARKET, and getting this wrong is why the first run of
            # this study was thrown away. Discarding the unresolved ones looks
            # harmless and is not: at rr 3.5 the stop sits 1R away and the
            # target 3.5R, so whatever DOES resolve inside a short window is
            # mostly stop-outs. Dropping the rest kept the control's losers and
            # threw away its survivors, and it printed -0.51 R against every
            # previous control in this project at -0.02 to -0.15. undertow_
            # sweep.control() already did this correctly and said so in a
            # comment; this file did not copy it.
            b = cs[min(i + hold, len(cs) - 1)]
            r = ((entry - b.c) if t.short else (b.c - entry)) / risk
        out.append(dataclasses.replace(t, r=r - FEE * entry / risk,
                                       won=r > 0))
    return out


def run_arm(tf, p, syms):
    agg = U.Result()
    bars = 0
    for sym in syms:
        agg.add(U.run(LOADED[tf][sym], p, sym))
        bars += len(LOADED[tf][sym])
    return agg, bars


def main():
    assert_disjoint()
    argv = [a for a in sys.argv[1:] if a in TFS]
    tfs = argv or list(TFS)
    print("UNDERTOW PULLBACK — the three defects in SPEC.md 2.3b")
    print("prereg: indicators/undertow/prereg/PREREG_undertow_pullback.md")
    print("population: SYMBOLS_FRESH4, ranks 136-180, never looked at")
    print("ONE primary fixed in advance; A2/A3/A4 are descriptive and cannot")
    print("be promoted whatever they print")

    rows = []
    for tf in tfs:
        LOADED[tf] = load(tf, SYMBOLS_FRESH4)
        syms = [s for s in SYMBOLS_FRESH4
                if len(LOADED[tf].get(s) or []) >= MIN_BARS]
        if len(syms) < 20:
            print(f"\n{tf}: only {len(syms)} FRESH4 symbols cached. Run "
                  f"undertow_sweep.py --fetch-fresh4")
            return 2
        days = sum(len(LOADED[tf][s]) for s in syms) * BAR_SECONDS[tf] / 86400

        print(f"\n{'-' * 78}\n{tf} · {len(syms)} symbols, scored once"
              f"\n{'-' * 78}")
        print(f"  {'':3} {'configuration':36} {'R/trade':>8} {'+/-':>6} "
              f"{'n':>6} {'setups/d':>9} {'trades/d':>9}")
        out = {}
        for aid, name, over in ARMS:
            p = dataclasses.replace(BASE, **over)
            res, _ = run_arm(tf, p, syms)
            m, se, n = clustered(res.real)
            print(f"  {aid:3} {name:36} {m:+8.3f} {se:6.3f} {n:6} "
                  f"{res.nLoc / days:9.2f} {len(res.real) / days:9.2f}"
                  + ("   ·descriptive" if aid in DESCRIPTIVE else "")
                  + ("   CAP!" if res.nCap else ""))
            out[aid] = dict(m=m, se=se, n=n, res=res)

        a, b = out[PRIMARY], out["A0"]

        # THE DECOMPOSITION. Keys must be unique or the labels are noise.
        ka = {key(t): t for t in a["res"].real}
        kb = {key(t): t for t in b["res"].real}
        assert len(ka) == a["n"] and len(kb) == b["n"], (
            f"KEY COLLISION — {len(ka)} keys for {a['n']} A1 trades, "
            f"{len(kb)} for {b['n']} A0. The decomposition below would be "
            f"mislabelled and the run is void.")
        shared = [t for k, t in ka.items() if k in kb]
        added = [t for k, t in ka.items() if k not in kb]
        dropped = [t for k, t in kb.items() if k not in ka]
        print(f"\n  A1 AGAINST A0, trade by trade")
        for lab, ts in (("SHARED  both take it", shared),
                        ("ADDED   only A1 (locTol loosening)", added),
                        ("DROPPED only A0 (depth tightening)", dropped)):
            if ts:
                mm, ss, nn = clustered(ts)
                print(f"    {lab:36} {mm:+8.3f} {ss:6.3f} {nn:6}")
            else:
                print(f"    {lab:36} {'—':>8}")

        cm, cse, cn = clustered(control_full(a["res"].real, tf))
        print(f"\n  C   seeded random entry, whole series  "
              f"{cm:+8.3f} {cse:6.3f} {cn:6}      ·THE CONTROL")

        d = a["m"] - b["m"]
        dse = math.sqrt(a["se"] ** 2 + b["se"] ** 2)
        z = d / dse if dse else 0.0
        dc, dcse = a["m"] - cm, math.sqrt(a["se"] ** 2 + cse ** 2)
        bars = [a["n"] >= 200,
                all(out[x]["res"].nCap == 0 for x in out),
                d >= 0.10 and abs(z) >= 2.0,
                dcse > 0 and dc >= dcse,
                a["m"] > 0]
        print(f"\n  BARS for A1")
        print(f"    1 coverage        {a['n']} trades   "
              f"{'PASS' if bars[0] else 'FAIL — a bound'}")
        print(f"    2 not confounded  nCap 0 everywhere   "
              f"{'PASS' if bars[1] else 'FAIL — VOID'}")
        print(f"    3 beats baseline  A1 - A0 = {d:+.3f} +/- {dse:.3f} "
              f"(z {z:+.2f})   {'PASS' if bars[2] else 'FAIL'}")
        print(f"    4 beats control   {a['m']:+.3f} vs {cm:+.3f}, "
              f"diff {dc:+.3f} +/- {dcse:.3f}   "
              f"{'PASS' if bars[3] else 'FAIL'}")
        print(f"    5 positive        {a['m']:+.3f} R   "
              f"{'PASS' if bars[4] else 'FAIL'}")
        rows.append(dict(tf=tf, m=a["m"], a0=b["m"], d=d, z=z, c=cm,
                         n=a["n"], bars=bars,
                         add=clustered(added)[0] if added else float("nan"),
                         drop=clustered(dropped)[0] if dropped else float("nan"),
                         shr=clustered(shared)[0] if shared else float("nan"),
                         a4=out["A4"]["res"].nLoc / days,
                         a0loc=out["A0"]["res"].nLoc / days))

    print(f"\n{'=' * 78}\nVERDICT\n{'=' * 78}\n")
    print(f"  {'tf':8} {'A1':>8} {'A0':>8} {'delta':>7} {'z':>6} "
          f"{'control':>8} {'n':>6} {'SHARED':>8} {'ADDED':>8} "
          f"{'DROPPED':>8}  bars")
    for v in rows:
        print(f"  {v['tf']:8} {v['m']:+8.3f} {v['a0']:+8.3f} {v['d']:+7.3f} "
              f"{v['z']:+6.2f} {v['c']:+8.3f} {v['n']:6} {v['shr']:+8.3f} "
              f"{v['add']:+8.3f} {v['drop']:+8.3f}  "
              + "".join("P" if x else "." for x in v["bars"]))
    print(f"\n  A4, the BAR-unit arm — setups/day kept, against A0's")
    for v in rows:
        print(f"    {v['tf']:8} {v['a4']:6.2f} of {v['a0loc']:6.2f}   "
              f"{100 * v['a4'] / max(1e-9, v['a0loc']):5.1f}% kept")
    pos = [v for v in rows if v["m"] > 0]
    print(f"\n  6 NOT ONE TIMEFRAME  {len(pos)} of {len(rows)} positive   "
          f"{'PASS' if len(pos) >= 2 else 'FAIL'}")
    won = sum(1 for v in rows if v["bars"][2] and v["bars"][3] and v["bars"][4])

    print()
    if len(pos) >= 2 and won >= 2:
        print("  THE PULLBACK FIXES CLEAR THEIR BARS.")
        print("  First thing in Undertow to beat its control. locTol and")
        print("  pbMinDepth earn their defaults, and SPEC 2.3b's defects were")
        print("  defects rather than descriptions.")
    else:
        print("  THE PULLBACK FIXES DO NOT CLEAR THEIR BARS.")
        print("  The defects are real as descriptions and did not pay as")
        print("  fixes. The ADDED / DROPPED split still says WHICH half of")
        print("  the rule was wrong, which is more than 'it does not work'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
