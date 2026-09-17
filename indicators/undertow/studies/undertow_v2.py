"""v2 — the corrected strategy, against v1.

    PYTHONPATH=. python3 indicators/undertow/studies/undertow_v2.py

Runs exactly what prereg/PREREG_undertow_v2.md pre-registered.

THE PRIMARY IS THE WHOLE STACK. Five changes at once is normally the worst
design available; it is right here because v2 is not a parameter search, it is
the strategy as its author states it, and the question is "does the intended
rule work" rather than "which of these five helps". A factorial would be 32
configurations and a maximum -- the -0.31 R per trade UNDERTOW_PARAMS.md
measured as the cost of selecting from a chart.

The five components are reported LEAVE-ONE-OUT so the change can be attributed.
They are descriptive and none may be promoted: picking the best four of five is
selection, and the prereg forbids it in as many words.

THE CONTROL IS BUILT HERE, not taken from undertow_sweep, for both reasons
UNDERTOW_PULLBACK.md records: that helper samples from a QUADRANT while these
trades span the whole series, and unresolved entries must be MARKED TO MARKET
rather than discarded -- discarding them is what made a control read -0.51 R.
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
from research.symbols_fresh import (SYMBOLS_FRESH5,              # noqa: E402
                                    assert_disjoint)
from riptide.config import BAR_SECONDS                           # noqa: E402

# AS PUBLISHED, PINNED — see test_studies_pin_their_settings.py. V0 IS v1
# EXACTLY AS SHIPPED, which is what makes it the baseline worth beating.
BASE = U.P(maxLive=64, feeFrac=FEE, rr=3.5,
           swingSrc=U.SW_RANGE, msLen=6, msShortLen=2,
           endMinor=U.E_FLIP, endSweep=False, endStale=False, retraceMax=70)

# The five components of v2, named so leave-one-out can drop exactly one.
SMC = dict(biasSrc=U.BS_SMC, smcSwingLen=50, smcInternalLen=5)
NO_ENDING = dict(endMinor=U.E_OFF, endSweep=False, endStale=False,
                 retraceMax=0, adxMin=0)
NEED_BOS = dict(needBos=True)
WF = dict(confirmOrder=U.C_WF)
NEWEST = dict(pinNewest=True)
V2 = {**SMC, **NO_ENDING, **NEED_BOS, **WF, **NEWEST}

# v1's own settings, for putting one component back.
V1_BIAS = dict(biasSrc=U.BS_STRUCT, swingSrc=U.SW_RANGE, msLen=6,
               msShortLen=2)
V1_ENDING = dict(endMinor=U.E_FLIP, endSweep=False, endStale=False,
                 retraceMax=70, adxMin=0)

ARMS = [
    ("V0", "v1 exactly as shipped — BASELINE", {}),
    ("V2", "the full v2 stack — PRIMARY", V2),
    ("L1", "v2, but v1's bias source", {**V2, **V1_BIAS}),
    ("L2", "v2, but v1's Ending rules", {**V2, **V1_ENDING}),
    ("L3", "v2 without needBos", {**V2, "needBos": False}),
    ("L4", "v2 with either-order confirm", {**V2, "confirmOrder": U.C_EITHER}),
    ("L5", "v2 without pinNewest", {**V2, "pinNewest": False}),
]
PRIMARY = "V2"
LEAVE_ONE_OUT = {"L1", "L2", "L3", "L4", "L5"}
MIN_BARS = 11000
BREAK_EVEN = 100.0 / (1.0 + 3.5)


def control_full(trades, tf, seed=SEED):
    """One seeded random entry per real trade, over the WHOLE series, with
    unresolved entries MARKED TO MARKET. Both points are bugs this project has
    already paid for; see UNDERTOW_PULLBACK.md."""
    rnd = random.Random(seed)
    out = []
    for t in trades:
        cs = LOADED[tf].get(t.symbol)
        if not cs:
            continue
        hold = max(1, t.exitBar - t.fillBar)
        hi = len(cs) - hold - 2
        risk = abs(t.stop - t.entry)
        if hi <= 0 or risk <= 0:
            continue
        i = rnd.randint(0, hi)
        entry = cs[i].c
        stop = entry + risk if t.short else entry - risk
        tgt = entry - BASE.rr * risk if t.short else entry + BASE.rr * risk
        r = None
        for j in range(i + 1, min(i + 1 + hold, len(cs))):
            b = cs[j]
            if (b.h >= stop if t.short else b.l <= stop):
                r = -1.0
                break
            if (b.l <= tgt if t.short else b.h >= tgt):
                r = BASE.rr
                break
        if r is None:
            b = cs[min(i + hold, len(cs) - 1)]
            r = ((entry - b.c) if t.short else (b.c - entry)) / risk
        out.append(dataclasses.replace(t, r=r - FEE * entry / risk, won=r > 0))
    return out


def main():
    assert_disjoint()
    argv = [a for a in sys.argv[1:] if a in TFS]
    tfs = argv or list(TFS)
    print("UNDERTOW v2 — the corrected strategy, against v1")
    print("prereg: indicators/undertow/prereg/PREREG_undertow_v2.md")
    print("population: SYMBOLS_FRESH5, ranks 181-225, never looked at")
    print("ONE primary — the WHOLE v2 stack. The five leave-one-out arms are")
    print("descriptive and none may be promoted; best-four-of-five is")
    print(f"selection. break-even at rr {BASE.rr} is {BREAK_EVEN:.1f}%")

    rows = []
    for tf in tfs:
        LOADED[tf] = load(tf, SYMBOLS_FRESH5)
        syms = [s for s in SYMBOLS_FRESH5
                if len(LOADED[tf].get(s) or []) >= MIN_BARS]
        if len(syms) < 20:
            print(f"\n{tf}: only {len(syms)} FRESH5 symbols cached. Run "
                  f"undertow_sweep.py --fetch-fresh5")
            return 2
        days = sum(len(LOADED[tf][s]) for s in syms) * BAR_SECONDS[tf] / 86400

        print(f"\n{'-' * 78}\n{tf} · {len(syms)} symbols, scored once"
              f"\n{'-' * 78}")
        print(f"  {'':3} {'configuration':34} {'R/trade':>8} {'+/-':>6} "
              f"{'n':>6} {'win%':>6} {'trades/d':>9} {'vs V2':>7}")
        out = {}
        for aid, name, over in ARMS:
            p = dataclasses.replace(BASE, **over)
            agg = U.Result()
            for sym in syms:
                agg.add(U.run(LOADED[tf][sym], p, sym))
            m, se, n = clustered(agg.real)
            wr = 100.0 * sum(1 for t in agg.real if t.won) / max(1, n)
            d = f"{m - out['V2']['m']:+7.3f}" if aid in LEAVE_ONE_OUT else ""
            print(f"  {aid:3} {name:34} {m:+8.3f} {se:6.3f} {n:6} "
                  f"{wr:5.1f}% {len(agg.real) / days:9.2f} {d:>7}"
                  + ("   ·descriptive" if aid in LEAVE_ONE_OUT else "")
                  + ("   CAP!" if agg.nCap else ""))
            out[aid] = dict(m=m, se=se, n=n, res=agg, wr=wr)

        a, b = out[PRIMARY], out["V0"]
        cm, cse, cn = clustered(control_full(a["res"].real, tf))
        print(f"\n  C   seeded random entry, whole series"
              f"{'':9} {cm:+8.3f} {cse:6.3f} {cn:6}      ·THE CONTROL")

        d = a["m"] - b["m"]
        dse = math.sqrt(a["se"] ** 2 + b["se"] ** 2)
        z = d / dse if dse else 0.0
        dc, dcse = a["m"] - cm, math.sqrt(a["se"] ** 2 + cse ** 2)
        bars = [a["n"] >= 200,
                all(out[x]["res"].nCap == 0 for x in out),
                d >= 0.10 and abs(z) >= 2.0,
                dcse > 0 and dc >= dcse,
                a["m"] > 0]
        print(f"\n  BARS for V2")
        print(f"    1 coverage        {a['n']} trades   "
              f"{'PASS' if bars[0] else 'FAIL — a bound'}")
        print(f"    2 not confounded  nCap 0 everywhere   "
              f"{'PASS' if bars[1] else 'FAIL — VOID'}")
        print(f"    3 beats v1        V2 - V0 = {d:+.3f} +/- {dse:.3f} "
              f"(z {z:+.2f})   {'PASS' if bars[2] else 'FAIL'}")
        print(f"    4 beats control   {a['m']:+.3f} vs {cm:+.3f}, "
              f"diff {dc:+.3f} +/- {dcse:.3f}   "
              f"{'PASS' if bars[3] else 'FAIL'}")
        print(f"    5 positive        {a['m']:+.3f} R   "
              f"{'PASS' if bars[4] else 'FAIL'}")
        rows.append(dict(tf=tf, m=a["m"], v0=b["m"], d=d, z=z, c=cm,
                         n=a["n"], wr=a["wr"], bars=bars,
                         loo={k: out[k]["m"] - a["m"] for k in LEAVE_ONE_OUT}))

    print(f"\n{'=' * 78}\nVERDICT\n{'=' * 78}\n")
    print(f"  {'tf':8} {'V2':>8} {'V0 v1':>8} {'delta':>7} {'z':>6} "
          f"{'control':>8} {'n':>6} {'win%':>6}  bars")
    for v in rows:
        print(f"  {v['tf']:8} {v['m']:+8.3f} {v['v0']:+8.3f} {v['d']:+7.3f} "
              f"{v['z']:+6.2f} {v['c']:+8.3f} {v['n']:6} {v['wr']:5.1f}%  "
              + "".join("P" if x else "." for x in v["bars"]))
    print(f"\n  LEAVE-ONE-OUT — how far each arm sits from V2. Descriptive.")
    print(f"  {'tf':8} " + " ".join(f"{k:>8}" for k in sorted(LEAVE_ONE_OUT)))
    for v in rows:
        print(f"  {v['tf']:8} "
              + " ".join(f"{v['loo'][k]:+8.3f}" for k in sorted(LEAVE_ONE_OUT)))
    print("    L1 v1 bias · L2 v1 Ending · L3 no needBos · "
          "L4 either-order · L5 no pinNewest")

    pos = [v for v in rows if v["m"] > 0]
    print(f"\n  6 NOT ONE TIMEFRAME  {len(pos)} of {len(rows)} positive   "
          f"{'PASS' if len(pos) >= 2 else 'FAIL'}")
    won = sum(1 for v in rows if v["bars"][2] and v["bars"][3] and v["bars"][4])
    print()
    if len(pos) >= 2 and won >= 2:
        print("  v2 CLEARS ITS BARS. First thing in this project to beat a")
        print("  control. It becomes the shipped rule in the port, the chart")
        print("  and the watch — and every page in measurements/ is")
        print("  SUPERSEDED, because all twelve measured v1.")
    else:
        print("  v2 DOES NOT CLEAR ITS BARS.")
        print("  The corrected rule is measured too. The twelve v1 nulls are")
        print("  now thirteen, and the one that matters is this one, because")
        print("  it is the only one that measured the strategy as stated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
