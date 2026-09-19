"""Which pin wins, when a pullback offers several.

    PYTHONPATH=. python3 indicators/undertow/studies/undertow_pin.py

Runs exactly what prereg/PREREG_undertow_pin.md pre-registered.

WHY THIS RE-OPENS SOMETHING v2 CLOSED. `famPriority` has effect only INSIDE the
`pinNewest` branch, so the two switches are one rule with three settings, and
undertow_v2.py's L5 scored the middle one -- pure recency, which selects
AGAINST the stated shape 70% of the time in a bearish trend. The pairing is the
rule as its author states it and has never been tested.

THE CONTROL IS A RANDOM GATE, not a random entry, and that is the whole design.
The pair is a SELECTOR: measured on FRESH6, every trade it takes is one the
shipped rule also takes, and it discards 55% of them. A rule that throws away
half a population moves the mean whatever it is, and half of all such rules
move it up -- so the thing to beat is a coin discarding as often.
UNDERTOW_MTF_DEFAULT.md records that argument and this study inherits it.

P0 IS THE SHIPPED CONFIGURATION, not v1-as-published. The question is whether
to change the chart, so the thing to beat is the chart.
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
from research.symbols_fresh import (SYMBOLS_FRESH7,              # noqa: E402
                                    assert_disjoint)
from riptide.config import BAR_SECONDS                           # noqa: E402

# AS SHIPPED, PINNED — see test_studies_pin_their_settings.py. `confirmOrder`
# is W→F here because that IS what ships now; every other study pins C_EITHER
# because that is what its page was produced under. The difference is
# deliberate and it is the reason the field is in the PINNED list.
BASE = U.P(locTol=0, pinPick=U.PICK_READY, pinAt=U.PIN_PULL, pinLag=0, biasGate=U.BG_TRADEABLE, famStrict=False, armWins=False, stopSrc=U.S_PULL, useBackup=False, failTest=U.T_CLOSE, pinNewest=False,
           famPriority=False, biasSrc=U.BS_STRUCT, confirmOrder=U.C_WF, maxLive=64, feeFrac=FEE, rr=3.5,
           swingSrc=U.SW_RANGE, msLen=6, msShortLen=2,
           endMinor=U.E_FLIP, endSweep=False, endStale=False, retraceMax=70)

PAIR = dict(pinNewest=True, famPriority=True)
RECENCY = dict(pinNewest=True, famPriority=False)

ARMS = [
    ("P0", "what ships today — BASELINE", {}),
    ("P1", "priority shape, newest of it — PRIMARY", PAIR),
    ("P2", "newest wins, any shape — what v2 scored", RECENCY),
]
PRIMARY = "P1"
DESCRIPTIVE = {"P2"}
MIN_BARS = 11000
MIN_SYMS = 20


def priority_pc(trades):
    """Share pinned on the STATED priority shape — hammer in a bearish trend,
    shooting star in a bullish one. Descriptive; it says whether the mechanism
    reproduces, not whether the rule pays."""
    if not trades:
        return 0.0
    n = sum(1 for t in trades if t.code == ("HAM" if t.short else "SS"))
    return 100.0 * n / len(trades)


def random_gate(trades, frac, seed=SEED):
    """P0's own trades with `frac` of them discarded at random, per symbol.

    THE POINT OF MATCHING PER SYMBOL rather than globally: the pair's discard
    rate varies by symbol, and a global shuffle would quietly re-weight the
    universe toward whichever symbols the coin happened to keep.
    """
    rnd = random.Random(seed)
    bysym = {}
    for t in trades:
        bysym.setdefault(t.symbol, []).append(t)
    keep = []
    for ts in bysym.values():
        ts = list(ts)
        rnd.shuffle(ts)
        keep += ts[:max(0, round(len(ts) * (1.0 - frac)))]
    return keep


def main():
    assert_disjoint()
    argv = [a for a in sys.argv[1:] if a in TFS]
    tfs = argv or list(TFS)
    print("UNDERTOW — WHICH PIN WINS when a pullback offers several")
    print("prereg: indicators/undertow/prereg/PREREG_undertow_pin.md")
    print("population: SYMBOLS_FRESH7, never looked at, and thinner than")
    print("FRESH6 — 145-190k 24h turnover against 181-242k")
    print("THE CONTROL IS A RANDOM GATE. The pair discards ~55% of what ships")
    print("and invents nothing, so a coin refusing as often is what it must")
    print("beat. A random entry would be the easy control, not the honest one.")

    rows, void = [], False
    for tf in tfs:
        LOADED[tf] = load(tf, SYMBOLS_FRESH7)
        syms = [s for s in SYMBOLS_FRESH7
                if len(LOADED[tf].get(s) or []) >= MIN_BARS]
        if len(syms) < MIN_SYMS:
            print(f"\n{tf}: only {len(syms)} FRESH7 symbols carry "
                  f"{MIN_BARS} bars — the prereg says this timeframe is NOT "
                  f"REPORTED. Run undertow_sweep.py --fetch-fresh7 if that "
                  f"is a cache problem rather than a listing-age one.")
            continue
        days = sum(len(LOADED[tf][s]) for s in syms) * BAR_SECONDS[tf] / 86400

        print(f"\n{'-' * 78}\n{tf} · {len(syms)} symbols, scored once"
              f"\n{'-' * 78}")
        print(f"  {'':3} {'configuration':38} {'R/trade':>8} {'+/-':>6} "
              f"{'n':>6} {'win%':>6} {'prio%':>6} {'trades/d':>9}")
        out = {}
        for aid, name, over in ARMS:
            p = dataclasses.replace(BASE, **over)
            agg = U.Result()
            keys = set()
            for sym in syms:
                r = U.run(LOADED[tf][sym], p, sym)
                agg.add(r)
                keys |= {(sym, t.bar, t.short) for t in r.real}
            m, se, n = clustered(agg.real)
            wr = 100.0 * sum(1 for t in agg.real if t.won) / max(1, n)
            print(f"  {aid:3} {name:38} {m:+8.3f} {se:6.3f} {n:6} "
                  f"{wr:5.1f}% {priority_pc(agg.real):5.1f}% "
                  f"{len(agg.real) / days:9.2f}"
                  + ("   ·descriptive" if aid in DESCRIPTIVE else "")
                  + ("   CAP!" if agg.nCap else ""))
            out[aid] = dict(m=m, se=se, n=n, res=agg, wr=wr, keys=keys)

        # THE IMPOSSIBILITIES, checked before anything is read as a result.
        a, b = out[PRIMARY], out["P0"]
        outside = a["keys"] - b["keys"]
        live = [("P1 is a SUBSET of P0", not outside),
                ("P1 != P0", a["n"] != b["n"] or abs(a["m"] - b["m"]) > 1e-12),
                ("P2 != P0", out["P2"]["n"] != b["n"]
                 or abs(out["P2"]["m"] - b["m"]) > 1e-12),
                ("nCap is 0 everywhere",
                 all(out[x]["res"].nCap == 0 for x in out))]
        for label, held in live:
            print(f"  IMPOSSIBILITY  {label:24} "
                  + ("holds" if held else "VIOLATED — RUN IS VOID"))
        if outside:
            print(f"      {len(outside)} trades the pair takes and the "
                  f"baseline does not. It is not selecting.")
        void = void or not all(h for _, h in live)

        frac = 1.0 - (a["n"] / b["n"] if b["n"] else 1.0)
        gm, gse, gn = clustered(random_gate(b["res"].real, max(0.0, frac)))
        print(f"\n  G   random gate, {100 * max(0.0, frac):.1f}% discarded"
              f"{'':14} {gm:+8.3f} {gse:6.3f} {gn:6}      ·THE CONTROL")

        d = a["m"] - b["m"]
        dse = math.sqrt(a["se"] ** 2 + b["se"] ** 2)
        z = d / dse if dse else 0.0
        dg, dgse = a["m"] - gm, math.sqrt(a["se"] ** 2 + gse ** 2)
        bars = [a["n"] >= 200,
                all(h for _, h in live),
                d >= 0.10 and abs(z) >= 2.0,
                dgse > 0 and dg >= dgse,
                a["m"] > 0]
        print(f"\n  BARS for P1")
        print(f"    1 coverage        {a['n']} trades   "
              f"{'PASS' if bars[0] else 'FAIL — a bound'}")
        print(f"    2 not confounded  subset, both live, no cap   "
              f"{'PASS' if bars[1] else 'FAIL — VOID'}")
        print(f"    3 beats what ships  P1 - P0 = {d:+.3f} +/- {dse:.3f} "
              f"(z {z:+.2f})   {'PASS' if bars[2] else 'FAIL'}")
        print(f"    4 BEATS THE RANDOM GATE  {a['m']:+.3f} vs {gm:+.3f}, "
              f"diff {dg:+.3f} +/- {dgse:.3f}   "
              f"{'PASS' if bars[3] else 'FAIL'}")
        print(f"    5 positive        {a['m']:+.3f} R   "
              f"{'PASS' if bars[4] else 'FAIL'}")
        print(f"    · P1 - P2 = {a['m'] - out['P2']['m']:+.3f} R — how much "
              f"the SHAPE is worth, given both discard most of the population")
        rows.append(dict(tf=tf, m=a["m"], p0=b["m"], p2=out["P2"]["m"], d=d,
                         z=z, g=gm, n=a["n"], wr=a["wr"], bars=bars,
                         prio=priority_pc(a["res"].real),
                         prio0=priority_pc(b["res"].real),
                         prio2=priority_pc(out["P2"]["res"].real)))

    if not rows:
        print("\nNO TIMEFRAME HAD ENOUGH SYMBOLS. Nothing is reported.")
        return 2

    print(f"\n{'=' * 78}\nVERDICT\n{'=' * 78}\n")
    print(f"  {'tf':8} {'P1 pair':>8} {'P0 ships':>9} {'delta':>7} {'z':>6} "
          f"{'rnd gate':>9} {'n':>6} {'win%':>6}  bars")
    for v in rows:
        print(f"  {v['tf']:8} {v['m']:+8.3f} {v['p0']:+9.3f} {v['d']:+7.3f} "
              f"{v['z']:+6.2f} {v['g']:+9.3f} {v['n']:6} {v['wr']:5.1f}%  "
              + "".join("P" if x else "." for x in v["bars"]))
    print(f"\n  THE MECHANISM — share pinned on the stated priority shape.")
    print(f"  Predicted P0 near 60%, P1 above it, P2 near 30%.")
    print(f"  {'tf':8} {'P0':>8} {'P1':>8} {'P2':>8}")
    for v in rows:
        print(f"  {v['tf']:8} {v['prio0']:7.1f}% {v['prio']:7.1f}% "
              f"{v['prio2']:7.1f}%")

    pos = [v for v in rows if v["m"] > 0]
    print(f"\n  6 NOT ONE TIMEFRAME  {len(pos)} of {len(rows)} positive   "
          f"{'PASS' if len(pos) >= 2 else 'FAIL'}")
    won = sum(1 for v in rows if v["bars"][2] and v["bars"][3] and v["bars"][4])
    gate = sum(1 for v in rows if v["bars"][3])
    print()
    if void:
        print("  RUN IS VOID — a pre-registered impossibility fired.")
    elif len(pos) >= 2 and won >= 2:
        print("  THE STATED RULE CLEARS ITS BARS. First thing in this project")
        print("  to beat a matched random gate. Both switches become defaults")
        print("  in the port, the chart and the watch.")
    elif gate >= 2 and len(pos) >= 2:
        print("  P1 BEATS THE GATE BUT NOT WHAT SHIPS — the weaker outcome")
        print("  the prereg named in advance. The pair goes on the chart as")
        print("  an input defaulting to OFF, the way pinAt did. That is not a")
        print("  promotion and the page does not get to call it one.")
    else:
        print("  THE STATED RULE DOES NOT CLEAR ITS BARS.")
        print("  v2 scored the wrong form of it and this scores the right")
        print("  one. Both switches stay off. What the page owes the reader")
        print("  is the P1 - P2 column: whether the SHAPE mattered, given")
        print("  that both arms discard most of the population.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
