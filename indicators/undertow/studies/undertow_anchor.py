"""The leg-extreme anchor — the author's stated rule, at the right object.

    PYTHONPATH=. python3 indicators/undertow/studies/undertow_anchor.py

Runs exactly what prereg/PREREG_undertow_anchor.md pre-registered.

WHY THIS IS MEASURED AND W->F WAS NOT. The confirmation order, the priority
pairing and the inclusive failure test all shipped as CORRECTIONS without a
measurement, because each changes WHICH EVENT ARMS and costs nothing. This one
removes three quarters of the setups -- 1,831 trades against 888 on a spent
universe -- and a rule that expensive is not a free correction whoever stated
it.

THIRD ATTEMPT AT THE IDEA, FIRST AT THE RIGHT OBJECT. UNDERTOW_V3.md measured
`trend extreme`, which anchors on the running extreme since the MAJOR CHoCH --
one stale point per trend, with the priority-shape pin a median of 47 bars past
it. `leg extreme` resets on every internal turn: median 8.

THE PRIORITY-SHAPE SHARE IS AN IMPOSSIBILITY, not a column. It is the mechanism
the anchor exists to deliver; if the pins are not overwhelmingly the priority
shape then the object is still wrong and the expectancy is beside the point.
"""
from __future__ import annotations

import dataclasses
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

from indicators.undertow.port import undertow as U               # noqa: E402
from indicators.undertow.studies.undertow_sweep import (         # noqa: E402
    FEE, LOADED, TFS, clustered, load)
from indicators.undertow.studies.undertow_v2 import (            # noqa: E402
    control_full)
from research.symbols_fresh import (SYMBOLS_FRESH10,             # noqa: E402
                                    assert_disjoint)
from riptide.config import BAR_SECONDS                           # noqa: E402

# AS SHIPPED, PINNED — see test_studies_pin_their_settings.py. This BASE is
# the live configuration: SMC 14/5, W→F, the priority pairing on, the
# inclusive failure test. The only thing the arms vary is the anchor.
BASE = U.P(locTol=0, pinPick=U.PICK_READY, pinAt=U.PIN_PULL, pinLag=0, biasGate=U.BG_TRADEABLE, famStrict=False, armWins=False, stopSrc=U.S_PULL, useBackup=False, biasSrc=U.BS_SMC, smcSwingLen=14, smcInternalLen=5,
           confirmOrder=U.C_WF, pinNewest=True, famPriority=True,
           failTest=U.T_TOUCH, workTest=U.T_CLOSE,
           maxLive=64, feeFrac=FEE, rr=3.5,
           swingSrc=U.SW_BAR, msLen=6, msShortLen=2,
           endMinor=U.E_FLIP, endSweep=False, endStale=False, retraceMax=70)

ARMS = [
    ("L0", "pullback extreme, tol 0 — what ships", dict(pinAt=U.PIN_PULL)),
    ("L1", "LEG extreme, tol 0 — the stated rule", dict(pinAt=U.PIN_LEG)),
    ("L2", "leg extreme, tol 2", dict(pinAt=U.PIN_LEG, locTol=2)),
    ("L3", "trend extreme, tol 0 — v3's anchor", dict(pinAt=U.PIN_TREND)),
]
PRIMARY = "L1"
DESCRIPTIVE = {"L2", "L3"}
MIN_BARS = 11000
MIN_SYMS = 20
PRIORITY_FLOOR = 70.0


def priority_pc(armed):
    """Share of ARMED pins on the stated priority shape. Armed rather than
    filled, because this is a property of the DETECTOR and a fill is a later
    accident."""
    if not armed:
        return 0.0
    n = sum(1 for a in armed if a["code"] == ("HAM" if a["short"] else "SS"))
    return 100.0 * n / len(armed)


def main():
    assert_disjoint()
    argv = [a for a in sys.argv[1:] if a in TFS]
    tfs = argv or list(TFS)
    print("UNDERTOW — THE LEG-EXTREME ANCHOR")
    print("prereg: indicators/undertow/prereg/PREREG_undertow_anchor.md")
    print("population: SYMBOLS_FRESH10, never looked at")
    print("Measured rather than shipped as a correction because it costs 75%")
    print("of the setups. The priority-shape share is an IMPOSSIBILITY here,")
    print("not a column: it is the mechanism the anchor exists to deliver.")

    rows, void = [], False
    for tf in tfs:
        LOADED[tf] = load(tf, SYMBOLS_FRESH10)
        syms = [s for s in SYMBOLS_FRESH10
                if len(LOADED[tf].get(s) or []) >= MIN_BARS]
        if len(syms) < MIN_SYMS:
            print(f"\n{tf}: only {len(syms)} FRESH10 symbols carry "
                  f"{MIN_BARS} bars — NOT REPORTED, per the prereg.")
            continue
        days = sum(len(LOADED[tf][s]) for s in syms) * BAR_SECONDS[tf] / 86400

        print(f"\n{'-' * 78}\n{tf} · {len(syms)} symbols, scored once"
              f"\n{'-' * 78}")
        print(f"  {'':3} {'configuration':38} {'R/trade':>8} {'+/-':>6} "
              f"{'n':>6} {'win%':>6} {'prio%':>7} {'trades/d':>9}")
        out = {}
        for aid, name, over in ARMS:
            p = dataclasses.replace(BASE, **over)
            agg, keys = U.Result(), set()
            for sym in syms:
                r = U.run(LOADED[tf][sym], p, sym)
                agg.add(r)
                keys |= {(sym, t.bar, t.short) for t in r.real}
            m, se, n = clustered(agg.real)
            wr = 100.0 * sum(1 for t in agg.real if t.won) / max(1, n)
            pr = priority_pc(agg.armed)
            print(f"  {aid:3} {name:38} {m:+8.3f} {se:6.3f} {n:6} "
                  f"{wr:5.1f}% {pr:6.1f}% {len(agg.real) / days:9.2f}"
                  + ("   ·descriptive" if aid in DESCRIPTIVE else "")
                  + ("   CAP!" if agg.nCap else ""))
            out[aid] = dict(m=m, se=se, n=n, res=agg, wr=wr, keys=keys, pr=pr)

        a, b = out[PRIMARY], out["L0"]
        live = [("the anchor reaches the pin", a["n"] != b["n"]),
                ("L1 is NOT a subset of L0", bool(a["keys"] - b["keys"])),
                (f"priority shape >= {PRIORITY_FLOOR:.0f}%",
                 a["pr"] >= PRIORITY_FLOOR),
                ("nCap is 0 everywhere",
                 all(out[x]["res"].nCap == 0 for x in out))]
        for label, held in live:
            print(f"  IMPOSSIBILITY  {label:30} "
                  + ("holds" if held else "VIOLATED — RUN IS VOID"))
        if a["pr"] < PRIORITY_FLOOR:
            print(f"      {a['pr']:.1f}% of L1's armed pins are the priority "
                  f"shape, against a floor of {PRIORITY_FLOOR:.0f}%. The "
                  f"anchor is not finding the candle the diagram shows, so "
                  f"the object is still wrong and its expectancy is beside "
                  f"the point.")
        void = void or not all(h for _, h in live)

        cm, cse, cn = clustered(control_full(a["res"].real, tf))
        print(f"\n  C   seeded random entry, whole series"
              f"{'':13} {cm:+8.3f} {cse:6.3f} {cn:6}      ·THE CONTROL")

        sh = a["keys"] & b["keys"]
        rmap = {}
        for aid in ("L0", "L1"):
            for t in out[aid]["res"].real:
                rmap.setdefault(aid, {})[(t.symbol, t.bar, t.short)] = t.r
        print(f"\n  THE THREE POOLS")
        for nm, src, ks in (("shared", "L1", sh),
                            ("ships only", "L0", b["keys"] - sh),
                            ("leg only", "L1", a["keys"] - sh)):
            v = [rmap[src][k] for k in ks]
            print(f"    {nm:11} {sum(v) / len(v) if v else 0.0:+.3f} R   "
                  f"n {len(v)}")

        d = a["m"] - b["m"]
        dse = math.sqrt(a["se"] ** 2 + b["se"] ** 2)
        z = d / dse if dse else 0.0
        dc, dcse = a["m"] - cm, math.sqrt(a["se"] ** 2 + cse ** 2)
        bars = [a["n"] >= 200,
                all(h for _, h in live),
                d >= 0.10 and abs(z) >= 2.0,
                dcse > 0 and dc >= dcse,
                a["m"] > 0]
        print(f"\n  BARS for L1")
        print(f"    1 coverage        {a['n']} trades   "
              f"{'PASS' if bars[0] else 'FAIL — a bound'}")
        print(f"    2 not confounded  all four hold   "
              f"{'PASS' if bars[1] else 'FAIL — VOID'}")
        print(f"    3 beats what ships  L1 - L0 = {d:+.3f} +/- {dse:.3f} "
              f"(z {z:+.2f})   {'PASS' if bars[2] else 'FAIL'}")
        print(f"    4 beats control   {a['m']:+.3f} vs {cm:+.3f}, "
              f"diff {dc:+.3f} +/- {dcse:.3f}   "
              f"{'PASS' if bars[3] else 'FAIL'}")
        print(f"    5 positive        {a['m']:+.3f} R   "
              f"{'PASS' if bars[4] else 'FAIL'}")
        print(f"    · what it COSTS   {len(a['res'].real) / days:.2f} "
              f"trades a day against {len(b['res'].real) / days:.2f} — "
              f"{100 * len(a['res'].real) / max(1, len(b['res'].real)):.0f}% "
              f"of what ships")
        rows.append(dict(tf=tf, m=a["m"], l0=b["m"], d=d, z=z, c=cm,
                         n=a["n"], wr=a["wr"], pr=a["pr"], bars=bars,
                         keep=100 * len(a["res"].real)
                         / max(1, len(b["res"].real)),
                         desc={k: out[k]["m"] - b["m"] for k in DESCRIPTIVE},
                         dpr={k: out[k]["pr"] for k in DESCRIPTIVE}))

    if not rows:
        print("\nNO TIMEFRAME HAD ENOUGH SYMBOLS. Nothing is reported.")
        return 2

    print(f"\n{'=' * 78}\nVERDICT\n{'=' * 78}\n")
    print(f"  {'tf':8} {'L1 leg':>8} {'L0 ships':>9} {'delta':>7} {'z':>6} "
          f"{'control':>8} {'n':>6} {'win%':>6} {'prio%':>7} {'kept':>6}  bars")
    for v in rows:
        print(f"  {v['tf']:8} {v['m']:+8.3f} {v['l0']:+9.3f} {v['d']:+7.3f} "
              f"{v['z']:+6.2f} {v['c']:+8.3f} {v['n']:6} {v['wr']:5.1f}% "
              f"{v['pr']:6.1f}% {v['keep']:5.0f}%  "
              + "".join("P" if x else "." for x in v["bars"]))
    print(f"\n  DESCRIPTIVE — distance from what ships, and the shape share")
    print(f"  {'tf':8} " + " ".join(f"{k:>18}" for k in sorted(DESCRIPTIVE)))
    for v in rows:
        print(f"  {v['tf']:8} " + " ".join(
            f"{v['desc'][k]:+8.3f} {v['dpr'][k]:6.1f}%"
            for k in sorted(DESCRIPTIVE)))
    print("    L2 leg extreme at tol 2 · L3 trend extreme at tol 0")

    pos = [v for v in rows if v["m"] > 0]
    print(f"\n  6 NOT ONE TIMEFRAME  {len(pos)} of {len(rows)} positive   "
          f"{'PASS' if len(pos) >= 2 else 'FAIL'}")
    won = sum(1 for v in rows if v["bars"][2] and v["bars"][3] and v["bars"][4])
    worse = sum(1 for v in rows if v["d"] <= -0.10 and abs(v["z"]) >= 2.0)
    print()
    if void:
        print("  RUN IS VOID — a pre-registered impossibility fired.")
    elif len(pos) >= 2 and won >= 2:
        print("  THE LEG EXTREME EARNS THE DEFAULT. It becomes the anchor in")
        print("  the port, the chart and the watch — the first thing in this")
        print("  project to clear its bars.")
    elif worse >= 2:
        print("  THE LEG EXTREME IS MEASURABLY WORSE. It stays off.")
    else:
        print("  NULL — AND A NULL IS NOT A SHIP HERE, which is the one way")
        print("  this differs from the scale study. There the null meant a")
        print("  preference was free. Here it means the stated anchor costs")
        print("  three quarters of the setups for no measurable gain. It")
        print("  stays selectable, the page says what it costs, and the")
        print("  decision is the chart owner's with the number in front of")
        print("  them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
