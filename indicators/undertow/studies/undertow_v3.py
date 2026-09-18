"""v3 — the corrected ANCHOR, against v1 and against v2.

    PYTHONPATH=. python3 indicators/undertow/studies/undertow_v3.py

Runs exactly what prereg/PREREG_undertow_v3.md pre-registered.

WHAT MAKES THIS DIFFERENT FROM THE THIRTEEN BEFORE IT. Every earlier study
changed how MANY setups are taken -- a bias source, a gate, an Ending rule, a
supersede rule. This one changes WHICH CANDLE is anchored. SPEC.md 2.3d records
the correction: the counter-trend candle is the bounce attempt at the leg LOW,
not the last bar of the rally away from it. The family mix moves from 51.1% to
76.7% priority shapes with no priority rule applied, which is the strongest
sign so far that the two anchors are looking at different objects rather than
different amounts of the same one.

W2 IS THE ARM THAT ANSWERS IT. v1 differs from W2 by the anchor alone, so
W2 - W0 is what moving the pin to the leg low is worth with everything else
held at what ships. THE ANCHOR AND ITS TOLERANCE MOVE TOGETHER and cannot be
separated here: at locTol 0 the anchor admits 689 bearish pins against v1's
2,675, which is not the stated rule ("if the first candle does not qualify,
move to the second and third"). W2 - W0 is therefore the anchor AS STATED.

THE CONTROL IS undertow_v2's control_full, IMPORTED RATHER THAN COPIED. It
marks unresolved entries to market and samples the whole series -- both bugs
UNDERTOW_PULLBACK.md records this project paying for. A second copy is a second
chance to reintroduce them.
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
    NEED_BOS, NEWEST, NO_ENDING, SMC, WF, control_full)
from research.symbols_fresh import (SYMBOLS_FRESH6,              # noqa: E402
                                    assert_disjoint)
from riptide.config import BAR_SECONDS                           # noqa: E402

# AS PUBLISHED, PINNED — see test_studies_pin_their_settings.py. W0 IS v1
# EXACTLY AS SHIPPED, the same BASE undertow_v2.py uses, which is what makes
# the two studies' baselines comparable.
BASE = U.P(biasSrc=U.BS_STRUCT, confirmOrder=U.C_EITHER, maxLive=64, feeFrac=FEE,
           rr=3.5,
           swingSrc=U.SW_RANGE, msLen=6, msShortLen=2,
           endMinor=U.E_FLIP, endSweep=False, endStale=False, retraceMax=70)

# The two things v3 adds to v2. `locTol` is not a tuned parameter: it is the
# stated rule, and it is fixed at 2 for every arm that uses the new anchor.
ANCHOR = dict(pinAt=U.PIN_TREND, locTol=2)
FAM = dict(famPriority=True)
V2 = {**SMC, **NO_ENDING, **NEED_BOS, **WF, **NEWEST}
V3 = {**V2, **ANCHOR, **FAM}

ARMS = [
    ("W0", "v1 exactly as shipped — BASELINE", {}),
    ("W1", "the full v3 stack — PRIMARY", V3),
    ("W2", "v1 + the corrected anchor ONLY", {**ANCHOR}),
    ("W3", "v3 without famPriority", {**V3, "famPriority": False}),
    ("W4", "the v2 stack — v2 on this universe", V2),
]
PRIMARY = "W1"
DESCRIPTIVE = {"W2", "W3", "W4"}
MIN_BARS = 11000
BREAK_EVEN = 100.0 / (1.0 + 3.5)


def priority_pc(trades):
    """Share of trades whose pinned candle is the STATED priority shape —
    hammer in a bearish trend, shooting star in a bullish one.

    Descriptive, and it is the column that says whether the anchor did what
    SPEC.md 2.3d claims. It decides nothing: a rule can pick the right shape
    and still lose money, which is most of what this project has measured.
    """
    if not trades:
        return 0.0
    n = sum(1 for t in trades if t.code == ("HAM" if t.short else "SS"))
    return 100.0 * n / len(trades)


def main():
    assert_disjoint()
    argv = [a for a in sys.argv[1:] if a in TFS]
    tfs = argv or list(TFS)
    print("UNDERTOW v3 — the corrected ANCHOR, against v1 and against v2")
    print("prereg: indicators/undertow/prereg/PREREG_undertow_v3.md")
    print("population: SYMBOLS_FRESH6, ranks 226-270, never looked at")
    print("ONE primary — the WHOLE v3 stack. W2, W3 and W4 are descriptive")
    print("and none may be promoted; best-of-five is selection.")
    print(f"break-even at rr {BASE.rr} is {BREAK_EVEN:.1f}%")

    rows, void = [], False
    for tf in tfs:
        LOADED[tf] = load(tf, SYMBOLS_FRESH6)
        syms = [s for s in SYMBOLS_FRESH6
                if len(LOADED[tf].get(s) or []) >= MIN_BARS]
        if len(syms) < 20:
            print(f"\n{tf}: only {len(syms)} FRESH6 symbols cached. Run "
                  f"undertow_sweep.py --fetch-fresh6")
            return 2
        days = sum(len(LOADED[tf][s]) for s in syms) * BAR_SECONDS[tf] / 86400

        print(f"\n{'-' * 78}\n{tf} · {len(syms)} symbols, scored once"
              f"\n{'-' * 78}")
        print(f"  {'':3} {'configuration':34} {'R/trade':>8} {'+/-':>6} "
              f"{'n':>6} {'win%':>6} {'prio%':>6} {'trades/d':>9}")
        out = {}
        for aid, name, over in ARMS:
            p = dataclasses.replace(BASE, **over)
            agg = U.Result()
            for sym in syms:
                agg.add(U.run(LOADED[tf][sym], p, sym))
            m, se, n = clustered(agg.real)
            wr = 100.0 * sum(1 for t in agg.real if t.won) / max(1, n)
            print(f"  {aid:3} {name:34} {m:+8.3f} {se:6.3f} {n:6} "
                  f"{wr:5.1f}% {priority_pc(agg.real):5.1f}% "
                  f"{len(agg.real) / days:9.2f}"
                  + ("   ·descriptive" if aid in DESCRIPTIVE else "")
                  + ("   CAP!" if agg.nCap else ""))
            out[aid] = dict(m=m, se=se, n=n, res=agg, wr=wr)

        # THE IMPOSSIBILITIES, checked before a single number is read as a
        # result. Both say the same thing in two places: `pinAt` must actually
        # REACH the pin. A renamed constant that no longer matches would fall
        # through to the old branch and every arm here would silently measure
        # v1 or v2 again -- which is not hypothetical, it is what the swingSrc
        # dropdown rename did to five published studies.
        live = [("W2 != W0", out["W2"]["n"] != out["W0"]["n"]
                 or abs(out["W2"]["m"] - out["W0"]["m"]) > 1e-12),
                ("W1 != W4", out["W1"]["n"] != out["W4"]["n"]
                 or abs(out["W1"]["m"] - out["W4"]["m"]) > 1e-12)]
        for label, held in live:
            print(f"\n  IMPOSSIBILITY  {label}   "
                  + ("holds" if held else
                     "VIOLATED — the anchor is INERT. pinAt is not reaching "
                     "the pin, so every arm measured the old rule under a new "
                     "name. RUN IS VOID."))
        void = void or not all(h for _, h in live)

        a, b = out[PRIMARY], out["W0"]
        cm, cse, cn = clustered(control_full(a["res"].real, tf))
        print(f"  C   seeded random entry, whole series"
              f"{'':9} {cm:+8.3f} {cse:6.3f} {cn:6}      ·THE CONTROL")

        d = a["m"] - b["m"]
        dse = math.sqrt(a["se"] ** 2 + b["se"] ** 2)
        z = d / dse if dse else 0.0
        dc, dcse = a["m"] - cm, math.sqrt(a["se"] ** 2 + cse ** 2)
        bars = [a["n"] >= 200,
                all(out[x]["res"].nCap == 0 for x in out)
                and all(h for _, h in live),
                d >= 0.10 and abs(z) >= 2.0,
                dcse > 0 and dc >= dcse,
                a["m"] > 0]
        print(f"\n  BARS for W1")
        print(f"    1 coverage        {a['n']} trades   "
              f"{'PASS' if bars[0] else 'FAIL — a bound'}")
        print(f"    2 not confounded  nCap 0, the anchor is live   "
              f"{'PASS' if bars[1] else 'FAIL — VOID'}")
        print(f"    3 beats v1        W1 - W0 = {d:+.3f} +/- {dse:.3f} "
              f"(z {z:+.2f})   {'PASS' if bars[2] else 'FAIL'}")
        print(f"    4 beats control   {a['m']:+.3f} vs {cm:+.3f}, "
              f"diff {dc:+.3f} +/- {dcse:.3f}   "
              f"{'PASS' if bars[3] else 'FAIL'}")
        print(f"    5 positive        {a['m']:+.3f} R   "
              f"{'PASS' if bars[4] else 'FAIL'}")
        print(f"    · THE ANCHOR ALONE  W2 - W0 = "
              f"{out['W2']['m'] - b['m']:+.3f} R — descriptive, decides "
              f"nothing")
        rows.append(dict(tf=tf, m=a["m"], w0=b["m"], d=d, z=z, c=cm,
                         n=a["n"], wr=a["wr"], bars=bars,
                         prio=priority_pc(a["res"].real),
                         desc={k: out[k]["m"] - b["m"] for k in DESCRIPTIVE}))

    print(f"\n{'=' * 78}\nVERDICT\n{'=' * 78}\n")
    print(f"  {'tf':8} {'W1':>8} {'W0 v1':>8} {'delta':>7} {'z':>6} "
          f"{'control':>8} {'n':>6} {'win%':>6} {'prio%':>6}  bars")
    for v in rows:
        print(f"  {v['tf']:8} {v['m']:+8.3f} {v['w0']:+8.3f} {v['d']:+7.3f} "
              f"{v['z']:+6.2f} {v['c']:+8.3f} {v['n']:6} {v['wr']:5.1f}% "
              f"{v['prio']:5.1f}%  "
              + "".join("P" if x else "." for x in v["bars"]))
    print(f"\n  DESCRIPTIVE — distance from W0, the shipped rule. "
          f"None may be promoted.")
    print(f"  {'tf':8} " + " ".join(f"{k:>8}" for k in sorted(DESCRIPTIVE)))
    for v in rows:
        print(f"  {v['tf']:8} "
              + " ".join(f"{v['desc'][k]:+8.3f}" for k in sorted(DESCRIPTIVE)))
    print("    W2 anchor only · W3 v3 without famPriority · W4 the v2 stack")

    pos = [v for v in rows if v["m"] > 0]
    print(f"\n  6 NOT ONE TIMEFRAME  {len(pos)} of {len(rows)} positive   "
          f"{'PASS' if len(pos) >= 2 else 'FAIL'}")
    won = sum(1 for v in rows if v["bars"][2] and v["bars"][3] and v["bars"][4])
    print()
    if void:
        print("  RUN IS VOID — a pre-registered impossibility fired.")
    elif len(pos) >= 2 and won >= 2:
        print("  v3 CLEARS ITS BARS. The first thing in this project to beat")
        print("  a control. It becomes the shipped rule in the port, the")
        print("  chart and the watch, and every page in measurements/ is")
        print("  SUPERSEDED, because all thirteen measured the wrong anchor.")
    else:
        print("  v3 DOES NOT CLEAR ITS BARS.")
        print("  The anchor correction is measured. Whether it goes on the")
        print("  chart as a DRAWING is the W2 question and the prereg answers")
        print("  it there: a correction that loses money is still a")
        print("  correction, but it does not get to be the default.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
