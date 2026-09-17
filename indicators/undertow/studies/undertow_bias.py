"""Where should the bias come from? Runs exactly what
prereg/PREREG_undertow_bias_source.md pre-registered.

    PYTHONPATH=. python3 indicators/undertow/studies/undertow_bias.py

THE BIAS IS THE ONE LAYER NEVER VARIED. Five studies changed the candle, the
location, the exit and the fill; all five kept the same CHoCH engine
underneath. And the complaint against it is concrete: a 6-bar pivot flips the
direction 2.3 times a day on 15m and 1.1 on 30m -- the SAME setting behaving
differently per timeframe, because six bars is ninety minutes on one chart and
three hours on the other.

SEVEN ARMS. Structure as shipped (reference only), structure with matched
Ending rules (the baseline), EMA cross, Supertrend, Slope, Range position, and
structure on scale-invariant swings.

THE ENDING RULES ARE MATCHED, and that is the one judgement in the file. Three
of structure's four read minor structure and sweeps, which do not exist for a
moving average, so every arm runs retrace-only. Faking a minor CHoCH for an EMA
would make the comparison look fair while not being.

THE METRIC IS NOT THE LAST STUDY'S. The backup studies used R per ARMED SETUP
because arming was invariant across their arms. It is not invariant here -- the
direction decides which setups exist at all -- so the primary is mean R per
TRADE, with R per 1,000 bars beside it because a source with half the
expectancy and four times the trades is a different proposition.

IT SELECTS, so it has a holdout: one arm chosen on the even symbols' older
half, scored once on the odd symbols' newer half.
"""
from __future__ import annotations

import dataclasses
import math
import pathlib
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

from indicators.undertow.port import undertow as U               # noqa: E402
from indicators.undertow.studies.undertow_sweep import (         # noqa: E402
    FEE, LOADED, SEED, TFS, clustered, control, load, quadrant)
from research.data import SYMBOLS                                # noqa: E402
from riptide.config import BAR_SECONDS                           # noqa: E402

BASE = U.P(maxLive=64, feeFrac=FEE)
# Retrace-only Ending: the only rule that exists for every source.
MATCH = dict(endMinor=U.E_OFF, endSweep=False, endStale=False)

ARMS = [
    ("S0", "structure, as shipped", {}),
    ("S1", "structure — THE BASELINE", MATCH),
    ("S2", "EMA cross 50/200", {**MATCH, "biasSrc": U.BS_EMA}),
    ("S3", "Supertrend 10/3.0", {**MATCH, "biasSrc": U.BS_ST}),
    ("S4", "Slope 50 @ 0.05", {**MATCH, "biasSrc": U.BS_SLOPE}),
    ("S5", "Range position 50", {**MATCH, "biasSrc": U.BS_DON}),
    ("S6", "structure, range swings", {**MATCH, "swingSrc": U.SW_RANGE,
                                       "swingK": 0.40, "swingKMinor": 0.12}),
]
REFERENCE = {"S0"}          # reported, never a baseline and never chosen


def run_arm(tf, p, syms, older):
    data = LOADED[tf]
    agg = U.Result()
    ctl, bars = [], 0
    flips, holds = 0, []
    for sym in syms:
        cs = data.get(sym)
        if not cs or len(cs) < 1200:
            continue
        seg, skip = quadrant(cs, older)
        r = U.run(seg, p, sym)
        r.trades = [t for t in r.trades if t.fillBar >= skip]
        agg.add(r)
        bars += len(seg) - skip
        if r.real:
            ctl += control(r.real, tf, [sym], older, p, seed=SEED)
        st, _ = U.structure(seg, p)
        run = 1
        for i in range(skip + 1, len(seg)):
            if st["os"][i] != st["os"][i - 1]:
                flips += 1
                holds.append(run)
                run = 1
            else:
                run += 1
    step = BAR_SECONDS[tf]
    return dict(res=agg, ctl=ctl, bars=bars,
                flips=flips / max(1e-9, bars * step / 86400.0),
                hold=statistics.median(holds) * step / 3600 if holds else 0.0)


def panel(tf, syms, older, title):
    print(f"\n{'-' * 78}\n{tf} · {title}\n{'-' * 78}")
    print(f"  {'':3} {'bias source':26} {'R/trade':>8} {'+/-':>6} {'n':>6} "
          f"{'R/1k bars':>10} {'flips/d':>8} {'hold h':>7} {'ctl':>7}")
    out = {}
    for aid, name, over in ARMS:
        p = dataclasses.replace(BASE, **over)
        g = run_arm(tf, p, syms, older)
        m, se, n = clustered(g["res"].real)
        cm = clustered(g["ctl"])[0] if g["ctl"] else float("nan")
        thru = 1000.0 * g["res"].netR / max(1, g["bars"])
        print(f"  {aid:3} {name:26} {m:+8.3f} {se:6.3f} {n:6} "
              f"{thru:+10.3f} {g['flips']:8.1f} {g['hold']:7.1f} {cm:+7.3f}"
              + ("   ·reference" if aid in REFERENCE else "")
              + ("   CAP!" if g["res"].nCap else ""))
        out[aid] = dict(m=m, se=se, n=n, thru=thru, ctl=cm, res=g["res"],
                        ctls=g["ctl"], flips=g["flips"], hold=g["hold"])
    return out


def main():
    argv = [a for a in sys.argv[1:] if a in TFS]
    tfs = argv or list(TFS)
    for tf in tfs:
        LOADED[tf] = load(tf)
        if not LOADED[tf]:
            print(f"{tf}: no cached candles. Run undertow_sweep.py --fetch.")
            return 2
    evens = [s for i, s in enumerate(SYMBOLS) if i % 2 == 0]
    odds = [s for i, s in enumerate(SYMBOLS) if i % 2 == 1]

    print("UNDERTOW BIAS SOURCE — where should the direction come from?")
    print("prereg: indicators/undertow/prereg/PREREG_undertow_bias_source.md")
    print(f"everything but the direction is held constant · fees "
          f"{FEE * 1e4:.0f}bp · retrace-only Ending on every arm")
    print("primary: mean R per TRADE (arming is NOT invariant here)")

    vs = []
    for tf in tfs:
        tr = panel(tf, evens, True, "TRAIN — even symbols, older half. "
                                    "NOT EVIDENCE: 6 arms, a maximum is taken.")
        pick = max((a for a in tr if a not in REFERENCE and tr[a]["n"] >= 60),
                   key=lambda a: tr[a]["m"], default=None)
        if pick is None:
            print("\n  no arm reached 60 train trades; nothing to carry.")
            continue
        print(f"\n  CARRIED OVER: {pick} {dict((a, n) for a, n, _ in ARMS)[pick]}"
              f"   (train {tr[pick]['m']:+.3f})")

        ho = panel(tf, odds, False, "HOLDOUT — odd symbols, newer half — "
                                    "scored once")
        a, b = ho[pick], ho["S1"]
        d = a["m"] - b["m"]
        dse = math.sqrt(a["se"] ** 2 + b["se"] ** 2)
        z = d / dse if dse else 0.0
        cse = clustered(a["ctls"])[1] if a["ctls"] else float("inf")
        dc = a["m"] - a["ctl"]
        dcse = math.sqrt(a["se"] ** 2 + cse ** 2) if cse != float("inf") else 0
        bars = [a["n"] >= 200,
                all(ho[x]["res"].nCap == 0 for x in ho),
                d >= 0.10 and abs(z) >= 2.0,
                dcse > 0 and dc >= dcse,
                a["m"] > 0]
        print(f"\n  HOLDOUT VERDICT for {pick}")
        print(f"    1 coverage        {a['n']} trades   "
              f"{'PASS' if bars[0] else 'FAIL — a bound'}")
        print(f"    2 not confounded  nCap 0 everywhere   "
              f"{'PASS' if bars[1] else 'FAIL — VOID'}")
        print(f"    3 beats baseline  {pick} - S1 = {d:+.3f} +/- {dse:.3f} "
              f"(z {z:+.2f})   {'PASS' if bars[2] else 'FAIL'}")
        print(f"    4 beats control   {a['m']:+.3f} vs {a['ctl']:+.3f}, "
              f"diff {dc:+.3f} +/- {dcse:.3f}   "
              f"{'PASS' if bars[3] else 'FAIL'}")
        print(f"    5 positive        {a['m']:+.3f} R   "
              f"{'PASS' if bars[4] else 'FAIL'}")
        vs.append(dict(tf=tf, pick=pick, m=a["m"], se=a["se"], n=a["n"],
                       s1=b["m"], d=d, z=z, ctl=a["ctl"], bars=bars,
                       thru=a["thru"]))

    print(f"\n{'=' * 78}\nVERDICT\n{'=' * 78}\n")
    print(f"  {'tf':8} {'chosen':4} {'holdout':>8} {'S1':>8} {'delta':>7} "
          f"{'z':>6} {'control':>8} {'n':>6}  bars")
    for v in vs:
        print(f"  {v['tf']:8} {v['pick']:4} {v['m']:+8.3f} {v['s1']:+8.3f} "
              f"{v['d']:+7.3f} {v['z']:+6.2f} {v['ctl']:+8.3f} {v['n']:6}  "
              + "".join("P" if x else "." for x in v["bars"]))
    pos = [v for v in vs if v["m"] > 0]
    print(f"\n  6 NOT ONE TIMEFRAME  {len(pos)} of {len(vs)} positive   "
          f"{'PASS' if len(pos) >= 2 else 'FAIL'}")
    win = [v for v in vs if all(v["bars"])]
    print()
    if len(pos) >= 2 and len(win) >= 2:
        print("  A BIAS SOURCE CLEARS EVERY BAR on "
              + ", ".join(v["tf"] for v in win) + ".")
        print("  First thing in Undertow to beat its own control. It earns the")
        print("  watch's default and a forward run — not a conclusion.")
    else:
        print("  NO BIAS SOURCE CLEARS ITS BARS.")
        print("  The direction layer is the sixth component ablated without an")
        print("  effect. What stays true regardless is the CONSISTENCY finding:")
        print("  a pivot measured in bars means something different on every")
        print("  chart, and `range` or `Slope` fix that whether or not they pay.")
        print("  That is worth having on its own terms and on no other.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
