"""MTF as the DEFAULT, against what actually ships.

    PYTHONPATH=. python3 indicators/undertow/studies/undertow_mtf_default.py

Runs exactly what prereg/PREREG_undertow_mtf_default.md pre-registered.

WHAT THIS ADDS TO A STUDY THAT ALREADY RAN. UNDERTOW_MTF_EMA.md compared MTF
against structure with RETRACE-ONLY Ending on both arms, because three of
structure's four Ending rules read minor structure and sweeps and an EMA has
neither. That was right for comparing directions. But "as the default" means
the SHIPPED configuration -- endMinor "on the flip", retrace 70 -- so the
published baseline is not the chart's baseline. This closes that gap and
nothing else.

THE IMPOSSIBILITY IS THE POINT OF THE ARM LIST. For a non-structure source the
structure-reading Ending rules are inert, so MTF-with-shipped-Ending must be
BIT-IDENTICAL to MTF-with-retrace-only. D1 and D1b are both run and compared;
if they differ by one trade the run is VOID and the published page measured
something other than what it claims.

POPULATION: SYMBOLS_FRESH3, ranks 91-135, disjoint from the 23 and from both
earlier fresh sets, which now have published baselines.
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
from research.symbols_fresh import (SYMBOLS_FRESH3,              # noqa: E402
                                    assert_disjoint)
from riptide.config import BAR_SECONDS                           # noqa: E402

# AS PUBLISHED, PINNED — see test_studies_pin_their_settings.py. This BASE is
# the SHIPPED configuration, which is the whole point: endMinor on the flip,
# endSweep and endStale off, retrace 70. undertow_mtf.py's BASE differs by
# endMinor alone, deliberately, and that difference is what this study is for.
BASE = U.P(confirmOrder=U.C_EITHER, maxLive=64, feeFrac=FEE, rr=3.5,
           swingSrc=U.SW_RANGE, msLen=6, msShortLen=2,
           endMinor=U.E_FLIP, endSweep=False, endStale=False, retraceMax=70)
RETRACE_ONLY = dict(endMinor=U.E_OFF, endSweep=False, endStale=False)
MTF = dict(biasSrc=U.BS_MTF, mtfFast=20, mtfSlow=50, mtfMult=2)

ARMS = [
    ("D0", "structure, SHIPPED Ending — BASELINE", {}),
    ("D1", "MTF EMA 20/50 x2, shipped — PRIMARY", MTF),
    ("D1b", "MTF, retrace-only — MUST EQUAL D1", {**MTF, **RETRACE_ONLY}),
    ("D2", "structure, retrace-only (the published M0)", RETRACE_ONLY),
]
PRIMARY = "D1"
MIN_BARS = 11000


def run_arm(tf, p, syms):
    agg = U.Result()
    bars = 0
    for sym in syms:
        cs = LOADED[tf][sym]
        agg.add(U.run(cs, p, sym))
        bars += len(cs)
    return agg, bars


def random_gate(tf, syms, frac, seed=SEED):
    """D1's own direction with a matched fraction of trades discarded at
    random, so the abstain state is measured against a coin refusing as often.

    Built from the UNGATED MTF direction -- the same EMA pair, never standing
    aside -- which is what makes the contrast "is disagreement informative"
    rather than "is refusing trades good".
    """
    rnd = random.Random(seed)
    p = dataclasses.replace(BASE, biasSrc=U.BS_EMA, emaFast=20, emaSlow=50)
    keep = []
    for sym in syms:
        ts = list(U.run(LOADED[tf][sym], p, sym).real)
        rnd.shuffle(ts)
        keep += ts[:max(0, round(len(ts) * (1.0 - frac)))]
    return keep


def panel(tf, syms):
    days = sum(len(LOADED[tf][s]) for s in syms) * BAR_SECONDS[tf] / 86400.0
    print(f"\n{'-' * 78}\n{tf} · SYMBOLS_FRESH3, {len(syms)} symbols, "
          f"scored once\n{'-' * 78}")
    print(f"  {'':4} {'configuration':40} {'R/trade':>8} {'+/-':>6} {'n':>6} "
          f"{'setups/d':>9} {'trades/d':>9} {'mixed%':>7}")
    out = {}
    for aid, name, over in ARMS:
        p = dataclasses.replace(BASE, **over)
        res, _ = run_arm(tf, p, syms)
        m, se, n = clustered(res.real)
        mixpc = 0.0
        if over.get("biasSrc") == U.BS_MTF:
            st, _ = U.structure(LOADED[tf][syms[0]], p)
            mixpc = 100.0 * sum(st["mixed"]) / max(1, len(st["mixed"]))
        print(f"  {aid:4} {name:40} {m:+8.3f} {se:6.3f} {n:6} "
              f"{res.nLoc / days:9.2f} {len(res.real) / days:9.2f} "
              f"{mixpc:6.1f}%" + ("   CAP!" if res.nCap else ""))
        out[aid] = dict(m=m, se=se, n=n, res=res, days=days)
    return out


def main():
    assert_disjoint()
    argv = [a for a in sys.argv[1:] if a in TFS]
    tfs = argv or list(TFS)
    print("UNDERTOW — MTF AS THE DEFAULT, against the SHIPPED configuration")
    print("prereg: indicators/undertow/prereg/PREREG_undertow_mtf_default.md")
    print("closes ONE gap in UNDERTOW_MTF_EMA.md: that study matched Ending")
    print("rules across arms, and 'as the default' means the shipped ones")
    print("population: SYMBOLS_FRESH3, ranks 91-135, never looked at")

    rows, void = [], False
    for tf in tfs:
        LOADED[tf] = load(tf, SYMBOLS_FRESH3)
        syms = [s for s in SYMBOLS_FRESH3
                if len(LOADED[tf].get(s) or []) >= MIN_BARS]
        if len(syms) < 20:
            print(f"\n{tf}: only {len(syms)} FRESH3 symbols cached. Run "
                  f"undertow_sweep.py --fetch-fresh3")
            return 2
        o = panel(tf, syms)
        a, b = o[PRIMARY], o["D0"]

        # THE IMPOSSIBILITY, checked before anything is read as a result.
        same = (a["n"] == o["D1b"]["n"]
                and abs(a["m"] - o["D1b"]["m"]) < 1e-12
                and a["res"].nLoc == o["D1b"]["res"].nLoc)
        print(f"\n  IMPOSSIBILITY  D1 == D1b   "
              + ("holds" if same else
                 f"VIOLATED — {a['n']} vs {o['D1b']['n']} trades. The Ending "
                 f"rules are reaching an alt source and UNDERTOW_MTF_EMA.md "
                 f"measured something other than what it says. RUN IS VOID."))
        void = void or not same

        frac = 1.0 - (a["n"] / o["D2"]["n"] if o["D2"]["n"] else 1.0)
        gm, gse, gn = clustered(random_gate(tf, syms, max(0.0, frac)))
        print(f"  G    random gate, {100 * max(0.0, frac):.1f}% discarded"
              f"{'':13} {gm:+8.3f} {gse:6.3f} {gn:6}      ·THE CONTROL")

        d = a["m"] - b["m"]
        dse = math.sqrt(a["se"] ** 2 + b["se"] ** 2)
        z = d / dse if dse else 0.0
        dg, dgse = a["m"] - gm, math.sqrt(a["se"] ** 2 + gse ** 2)
        bars = [a["n"] >= 200,
                all(o[x]["res"].nCap == 0 for x in o) and same,
                d >= 0.10 and abs(z) >= 2.0,
                dgse > 0 and dg >= dgse,
                a["m"] > 0]
        print(f"\n  BARS for D1")
        print(f"    1 coverage        {a['n']} trades   "
              f"{'PASS' if bars[0] else 'FAIL — a bound'}")
        print(f"    2 not confounded  nCap 0, D1 == D1b   "
              f"{'PASS' if bars[1] else 'FAIL — VOID'}")
        print(f"    3 beats baseline  D1 - D0 = {d:+.3f} +/- {dse:.3f} "
              f"(z {z:+.2f})   {'PASS' if bars[2] else 'FAIL'}")
        print(f"    4 BEATS THE RANDOM GATE  {a['m']:+.3f} vs {gm:+.3f}, "
              f"diff {dg:+.3f} +/- {dgse:.3f}   "
              f"{'PASS' if bars[3] else 'FAIL'}")
        print(f"    5 positive        {a['m']:+.3f} R   "
              f"{'PASS' if bars[4] else 'FAIL'}")
        print(f"    · the shipped Ending rules cost structure "
              f"{o['D0']['m'] - o['D2']['m']:+.3f} R here "
              f"(D0 - D2) — reported, decides nothing")
        rows.append(dict(tf=tf, m=a["m"], d0=b["m"], d2=o["D2"]["m"], d=d,
                         z=z, g=gm, n=a["n"], bars=bars,
                         tpd=len(a["res"].real) / a["days"],
                         tpd0=len(b["res"].real) / b["days"]))

    print(f"\n{'=' * 78}\nVERDICT\n{'=' * 78}\n")
    print(f"  {'tf':8} {'D1 MTF':>8} {'D0 ships':>9} {'delta':>7} {'z':>6} "
          f"{'rnd gate':>9} {'n':>6} {'D1 t/d':>7} {'D0 t/d':>7}  bars")
    for v in rows:
        print(f"  {v['tf']:8} {v['m']:+8.3f} {v['d0']:+9.3f} {v['d']:+7.3f} "
              f"{v['z']:+6.2f} {v['g']:+9.3f} {v['n']:6} {v['tpd']:7.2f} "
              f"{v['tpd0']:7.2f}  "
              + "".join("P" if x else "." for x in v["bars"]))
    pos = [v for v in rows if v["m"] > 0]
    print(f"\n  6 NOT ONE TIMEFRAME  {len(pos)} of {len(rows)} positive   "
          f"{'PASS' if len(pos) >= 2 else 'FAIL'}")
    won = sum(1 for v in rows if v["bars"][2] and v["bars"][3] and v["bars"][4])

    print()
    if void:
        print("  RUN IS VOID — the pre-registered impossibility fired.")
    elif len(pos) >= 2 and won >= 2:
        print("  MTF CLEARS ITS BARS AGAINST THE SHIPPED CONFIGURATION.")
        print("  It earns the default. Change biasSrc in the Pine, the port")
        print("  and the watch, and say so on every page that names a default.")
    else:
        print("  MTF DOES NOT EARN THE DEFAULT.")
        print("  biasSrc stays 'structure'. It is already selectable on the")
        print("  chart, and this was only ever about what an unconfigured")
        print("  user gets. The trades/day columns are the honest reason")
        print("  somebody might still choose it by hand.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
