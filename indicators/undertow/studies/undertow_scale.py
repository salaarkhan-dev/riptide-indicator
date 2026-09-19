"""The swing scale — 50/5 against 6/2.

    PYTHONPATH=. python3 indicators/undertow/studies/undertow_scale.py

Runs exactly what prereg/PREREG_undertow_scale.md pre-registered.

THE ONE GAP LEFT BY THE ENGINE SWAP. SPEC.md 1 records three changes and two
were already measured: the DETECTOR is the same expression either way
(port/smc.py, pivot for pivot) and the ENGINE swap scored +0.002 / +0.065 /
+0.006 R (UNDERTOW_V2.md). The SCALE was never scored, and it is the largest of
the three -- a 50-bar pivot on 15m is twelve and a half hours.

THE CONTROL IS A RANDOM ENTRY, NOT A RANDOM GATE, and that is a measured
decision rather than a default. On FRESH6 the two scales share only 564 trades:
2,733 belong to 6/2 alone and 692 to 50/5 alone. The scale RELOCATES the
population, so there is no discard rate to match a coin against. The pin study
is the opposite case and uses a gate; the difference is in both preregs.

S2 RUNS THE OLD ENGINE at the same 6/2 so the page can separate engine from
scale in one panel. It is descriptive and may not be promoted.
"""
from __future__ import annotations

import dataclasses
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

from indicators.undertow.port import smc                          # noqa: E402
from indicators.undertow.port import undertow as U               # noqa: E402
from indicators.undertow.studies.undertow_sweep import (         # noqa: E402
    FEE, LOADED, TFS, clustered, load)
from indicators.undertow.studies.undertow_v2 import (            # noqa: E402
    control_full)
from research.symbols_fresh import (SYMBOLS_FRESH9,              # noqa: E402
                                    assert_disjoint)
from riptide.config import BAR_SECONDS                           # noqa: E402

# AS SHIPPED, PINNED — see test_studies_pin_their_settings.py. `biasSrc` is
# BS_SMC here because that IS the shipped engine now; every page-reproducing
# study pins BS_STRUCT instead, and that difference is the reason the field is
# in the PINNED list at all.
BASE = U.P(locTol=0, pinPick=U.PICK_READY, pinAt=U.PIN_PULL, pinLag=0, biasGate=U.BG_TRADEABLE, famStrict=False, armWins=False, stopSrc=U.S_PULL, useBackup=False, pinNewest=False, famPriority=False, failTest=U.T_CLOSE, biasSrc=U.BS_SMC, confirmOrder=U.C_WF, maxLive=64, feeFrac=FEE,
           rr=3.5, swingSrc=U.SW_BAR, msLen=6, msShortLen=2,
           endSweep=False, endStale=False, endMinor=U.E_FLIP, retraceMax=70)

SMALL = dict(smcSwingLen=6, smcInternalLen=2)
SHIPPED = dict(smcSwingLen=50, smcInternalLen=5)
OLD_ENGINE = dict(biasSrc=U.BS_STRUCT, swingSrc=U.SW_BAR, msLen=6,
                  msShortLen=2)

ARMS = [
    ("S0", "SMC at 6/2 — the old scale — BASELINE", SMALL),
    ("S1", "SMC at 50/5 — what ships — PRIMARY", SHIPPED),
    ("S2", "riptide structure at 6/2 — the old engine", OLD_ENGINE),
]
PRIMARY = "S1"
DESCRIPTIVE = {"S2"}
MIN_BARS = 11000
MIN_SYMS = 20


def main():
    assert_disjoint()
    argv = [a for a in sys.argv[1:] if a in TFS]
    tfs = argv or list(TFS)
    print("UNDERTOW — THE SWING SCALE, 50/5 against 6/2")
    print("prereg: indicators/undertow/prereg/PREREG_undertow_scale2.md")
    print("population: SYMBOLS_FRESH9, never looked at")
    print("The engine and the detector were already measured; the SCALE was")
    print("not, and it is the largest of the three changes. The control is a")
    print("random ENTRY: the two scales share 17% of their trades, so the")
    print("scale relocates the population rather than filtering it.")

    rows, void = [], False
    for tf in tfs:
        LOADED[tf] = load(tf, SYMBOLS_FRESH9)
        syms = [s for s in SYMBOLS_FRESH9
                if len(LOADED[tf].get(s) or []) >= MIN_BARS]
        if len(syms) < MIN_SYMS:
            print(f"\n{tf}: only {len(syms)} FRESH9 symbols carry {MIN_BARS} "
                  f"bars — the prereg says this timeframe is NOT REPORTED.")
            continue
        days = sum(len(LOADED[tf][s]) for s in syms) * BAR_SECONDS[tf] / 86400

        print(f"\n{'-' * 78}\n{tf} · {len(syms)} symbols, scored once"
              f"\n{'-' * 78}")
        print(f"  {'':3} {'configuration':40} {'R/trade':>8} {'+/-':>6} "
              f"{'n':>6} {'win%':>6} {'choch/d':>8} {'trades/d':>9}")
        # The series' first structure break, per symbol, from the engine that
        # defines it. Computed once: both arms must exclude the SAME bar.
        firstBreak = {}
        for sym in syms:
            m = smc.structure(LOADED[tf][sym], 6)
            firstBreak[sym] = next((i for i in range(len(LOADED[tf][sym]))
                                    if m["up"][i] or m["dn"][i]), -1)

        out = {}
        for aid, name, over in ARMS:
            p = dataclasses.replace(BASE, **over)
            agg, keys, choch, after = U.Result(), set(), 0, 0
            for sym in syms:
                r = U.run(LOADED[tf][sym], p, sym)
                agg.add(r)
                keys |= {(sym, t.bar, t.short) for t in r.real}
                st, _ = U.structure(LOADED[tf][sym], p)
                cb = [i for i, v in enumerate(st["choch"]) if v]
                choch += len(cb)
                # AFTER THE FIRST BREAK, and this has to EXCLUDE A SPECIFIC BAR
                # rather than drop each list's first element. The first version
                # did `len(cb) - 1`, which is not the same thing: if one engine
                # has an extra CHoCH at the first break its list is
                # [b0, b1, b2...] against [b1, b2...], and dropping the head of
                # each leaves [b1, b2...] against [b2...] — still off by one,
                # for every symbol, forever. It fired on a run where the
                # REGISTERED condition held exactly.
                after += len(set(cb) - {firstBreak[sym]})
            m, se, n = clustered(agg.real)
            wr = 100.0 * sum(1 for t in agg.real if t.won) / max(1, n)
            print(f"  {aid:3} {name:40} {m:+8.3f} {se:6.3f} {n:6} "
                  f"{wr:5.1f}% {choch / days:8.2f} "
                  f"{len(agg.real) / days:9.2f}"
                  + ("   ·descriptive" if aid in DESCRIPTIVE else "")
                  + ("   CAP!" if agg.nCap else ""))
            out[aid] = dict(m=m, se=se, n=n, res=agg, wr=wr, keys=keys,
                            choch=choch, after=after)

        # THE IMPOSSIBILITIES, REWRITTEN, before anything is read as a
        # result. The first attempt registered "the two engines' CHoCH counts
        # must match" and that fired on a 0.1% difference whose whole cause is
        # the SERIES' FIRST BREAK -- LuxAlgo's bias starts at neither,
        # riptide's starts at bearish. It was meant to say "the length reached
        # the detector" and said something far stronger instead. Each one below
        # asserts the thing it is actually checking for.
        a, b = out[PRIMARY], out["S0"]
        live = [("the length reaches the detector",
                 a["choch"] * 2 < b["choch"]),
                ("S1 != S0", a["n"] != b["n"] or abs(a["m"] - b["m"]) > 1e-12),
                ("the engines agree after the first break",
                 out["S0"]["after"] == out["S2"]["after"]),
                ("nCap is 0 everywhere",
                 all(out[x]["res"].nCap == 0 for x in out))]
        for label, held in live:
            print(f"  IMPOSSIBILITY  {label:38} "
                  + ("holds" if held else "VIOLATED — RUN IS VOID"))
        if a["choch"] * 2 >= b["choch"]:
            print(f"      50/5 fired {a['choch']} CHoCH against 6/2's "
                  f"{b['choch']}. A 50-bar pivot cannot flip as often as a "
                  f"6-bar one; smcSwingLen is not being read.")
        if out["S0"]["after"] != out["S2"]["after"]:
            print(f"      {out['S0']['after']} CHoCH from SMC at 6/2 after the "
                  f"first break against {out['S2']['after']} from riptide's. "
                  f"smc.py's corrected claim is that these agree EXACTLY once "
                  f"the first break is excluded, and here they do not.")
        void = void or not all(h for _, h in live)

        cm, cse, cn = clustered(control_full(a["res"].real, tf))
        print(f"\n  C   seeded random entry, whole series"
              f"{'':11} {cm:+8.3f} {cse:6.3f} {cn:6}      ·THE CONTROL")

        # THE THREE POOLS. On UNDERTOW_V3.md this said more than the headline.
        sh = a["keys"] & b["keys"]
        rmap = {}
        for aid in ("S0", "S1"):
            for t in out[aid]["res"].real:
                rmap.setdefault(aid, {})[(t.symbol, t.bar, t.short)] = t.r
        pools = (("shared", [rmap["S1"][k] for k in sh]),
                 ("6/2 only", [rmap["S0"][k] for k in b["keys"] - sh]),
                 ("50/5 only", [rmap["S1"][k] for k in a["keys"] - sh]))
        print(f"\n  THE THREE POOLS — the scale relocates, it does not filter")
        for nm, v in pools:
            mu = sum(v) / len(v) if v else 0.0
            print(f"    {nm:10} {mu:+.3f} R   n {len(v)}")

        d = a["m"] - b["m"]
        dse = math.sqrt(a["se"] ** 2 + b["se"] ** 2)
        z = d / dse if dse else 0.0
        dc, dcse = a["m"] - cm, math.sqrt(a["se"] ** 2 + cse ** 2)
        bars = [a["n"] >= 200,
                all(h for _, h in live),
                d >= 0.10 and abs(z) >= 2.0,
                dcse > 0 and dc >= dcse,
                a["m"] > 0]
        print(f"\n  BARS for S1")
        print(f"    1 coverage        {a['n']} trades   "
              f"{'PASS' if bars[0] else 'FAIL — a bound'}")
        print(f"    2 not confounded  CHoCH agree, S1 live, no cap   "
              f"{'PASS' if bars[1] else 'FAIL — VOID'}")
        print(f"    3 beats 6/2       S1 - S0 = {d:+.3f} +/- {dse:.3f} "
              f"(z {z:+.2f})   {'PASS' if bars[2] else 'FAIL'}")
        print(f"    4 beats control   {a['m']:+.3f} vs {cm:+.3f}, "
              f"diff {dc:+.3f} +/- {dcse:.3f}   "
              f"{'PASS' if bars[3] else 'FAIL'}")
        print(f"    5 positive        {a['m']:+.3f} R   "
              f"{'PASS' if bars[4] else 'FAIL'}")
        print(f"    · THE ENGINE, held at one scale: S0 - S2 = "
              f"{b['m'] - out['S2']['m']:+.3f} R — descriptive")
        rows.append(dict(tf=tf, m=a["m"], s0=b["m"], s2=out["S2"]["m"], d=d,
                         z=z, c=cm, n=a["n"], wr=a["wr"], bars=bars,
                         dse=dse,
                         fl1=a["choch"] / days, fl0=b["choch"] / days,
                         tpd1=len(a["res"].real) / days,
                         tpd0=len(b["res"].real) / days))

    if not rows:
        print("\nNO TIMEFRAME HAD ENOUGH SYMBOLS. Nothing is reported.")
        return 2

    print(f"\n{'=' * 78}\nVERDICT\n{'=' * 78}\n")
    print(f"  {'tf':8} {'S1 50/5':>8} {'S0 6/2':>8} {'delta':>7} {'z':>6} "
          f"{'control':>8} {'n':>6} {'win%':>6} {'flips/d':>8}  bars")
    for v in rows:
        print(f"  {v['tf']:8} {v['m']:+8.3f} {v['s0']:+8.3f} {v['d']:+7.3f} "
              f"{v['z']:+6.2f} {v['c']:+8.3f} {v['n']:6} {v['wr']:5.1f}% "
              f"{v['fl1']:8.2f}  "
              + "".join("P" if x else "." for x in v["bars"]))
    print(f"\n  WHAT THE SCALE COSTS IN ACTIVITY")
    print(f"  {'tf':8} {'flips/d 6/2':>12} {'flips/d 50/5':>13} "
          f"{'trades/d 6/2':>13} {'trades/d 50/5':>14}")
    for v in rows:
        print(f"  {v['tf']:8} {v['fl0']:12.2f} {v['fl1']:13.2f} "
              f"{v['tpd0']:13.2f} {v['tpd1']:14.2f}")

    pos = [v for v in rows if v["m"] > 0]
    print(f"\n  6 NOT ONE TIMEFRAME  {len(pos)} of {len(rows)} positive   "
          f"{'PASS' if len(pos) >= 2 else 'FAIL'}")
    won = sum(1 for v in rows if v["bars"][2] and v["bars"][3] and v["bars"][4])
    # THE ASYMMETRIC DECISION RULE, exactly as the prereg fixed it.
    worse = sum(1 for v in rows
                if v["d"] <= -0.10 and abs(v["z"]) >= 2.0)
    print()
    if void:
        print("  RUN IS VOID — a pre-registered impossibility fired.")
    elif len(pos) >= 2 and won >= 2:
        print("  THE SHIPPED SCALE CLEARS ITS BARS. It reads better on a")
        print("  chart AND it earns its place. Nothing changes but the page.")
    elif worse >= 2:
        print("  THE SHIPPED SCALE IS MEASURABLY WORSE THAN 6/2.")
        print("  Not a silent revert: the prereg says this goes to the chart's")
        print("  owner as a decision, with the number. 50/5 was chosen because")
        print("  it reads better, and this is what that preference costs.")
    else:
        print("  NULL — the scale costs nothing measurable, so it STAYS.")
        print("  A preference that costs nothing is a fine reason to keep a")
        print("  setting, and nothing here has grounds to overrule one. What")
        print("  the page owes the reader is the activity table: the scale")
        print("  bought a quieter chart, and quieter is what it bought.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
