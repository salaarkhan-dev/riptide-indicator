"""Does a higher-timeframe agreement gate help? Runs exactly what
prereg/PREREG_undertow_htf.md pre-registered.

    PYTHONPATH=. python3 indicators/undertow/studies/undertow_htf.py

THIS ONE HAS GENUINELY NEVER BEEN TESTED. The HTF gate exists in the port, is
no-look-ahead and has two tests, but it has only ever been ONE BINARY DIMENSION
of a 48-cell grid in the parameter study, where only the selected cell was
scored. `htf4` was in the 15m train winner, whose holdout came back -0.093.
That is not a measurement of the gate.

TWO THINGS ARE DIFFERENT HERE.

1. A POPULATION NOTHING HAS LOOKED AT. Every previous study used the same 23
   symbols and two pages say "every quadrant is spent". The venue lists 594
   crypto USDT perps; research/symbols_fresh.py freezes 45 of them, disjoint
   from the 23. The 23 are not consulted here for anything, including a sanity
   check. So there is no train/holdout split: nothing is selected, one
   pre-specified arm is scored once per timeframe, and the whole universe is
   the holdout.

2. THE RIGHT CONTROL FOR A GATE. Every previous study used a random-ENTRY
   control, which asks whether the entry timing is worth anything. Wrong
   question for a gate: ANY rule that throws away 40% of the trades moves the
   mean, and about half of them move it up. So the primary control is a seeded
   RANDOM GATE refusing the same NUMBER of setups on the same symbol. If the
   higher timeframe cannot beat a coin that discards the same count, the higher
   timeframe is not informative and the effect is "trade less".

ONE PRIMARY ARM, FIXED IN THE PREREG: htfHours = 4.0. H1, H3 and H4 are printed
so the shape is visible and may not be promoted whatever they say.
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
    FEE, LOADED, SEED, TFS, clustered, control, load)
from research.symbols_fresh import SYMBOLS_FRESH, assert_disjoint  # noqa: E402

# AS PUBLISHED, PINNED — see test_studies_pin_their_settings.py.
BASE = U.P(pinAt=U.PIN_PULL, pinLag=0, biasGate=U.BG_TRADEABLE, famStrict=False, armWins=False, stopSrc=U.S_PULL, useBackup=False, pinNewest=False, famPriority=False, failTest=U.T_CLOSE, biasSrc=U.BS_STRUCT, confirmOrder=U.C_EITHER, maxLive=64, feeFrac=FEE, rr=3.5,
           swingSrc=U.SW_RANGE, msLen=6, msShortLen=2,
           endMinor=U.E_OFF, endSweep=False, endStale=False)

ARMS = [
    ("H0", "gate off — BASELINE", {}),
    ("H2", "HTF 4h — THE PRIMARY", dict(htfUnit=U.HTF_HOURS, htfHours=4.0)),
    ("H1", "HTF 1h", dict(htfUnit=U.HTF_HOURS, htfHours=1.0)),
    ("H3", "HTF 12h", dict(htfUnit=U.HTF_HOURS, htfHours=12.0)),
    ("H4", "HTF x4 bars — the unit contrast", dict(htfMult=4)),
]
PRIMARY = "H2"
DESCRIPTIVE = {"H1", "H3", "H4"}
MIN_BARS = 11000          # the prereg's coverage floor, per symbol


def run_arm(tf, p, syms):
    agg = U.Result()
    ctl, bars = [], 0
    for sym in syms:
        cs = LOADED[tf].get(sym)
        if not cs or len(cs) < MIN_BARS:
            continue
        r = U.run(cs, p, sym)
        agg.add(r)
        bars += len(cs)
        if r.real:
            ctl += control(r.real, tf, [sym], True, p, seed=SEED)
    return dict(res=agg, ctl=ctl, bars=bars)


def random_gate(tf, syms, reject_frac, seed=SEED):
    """THE CONTROL THE PREREG NAMES. Runs the ungated strategy and then throws
    away a matched FRACTION of its trades at random, per symbol.

    Matched on count, not on which ones — that is the whole point. It answers
    "is the higher timeframe informative", where the ungated baseline only
    answers "does gating do anything".
    """
    rnd = random.Random(seed)
    keep = []
    for sym in syms:
        cs = LOADED[tf].get(sym)
        if not cs or len(cs) < MIN_BARS:
            continue
        r = U.run(cs, dataclasses.replace(BASE), sym)
        ts = list(r.real)
        rnd.shuffle(ts)
        keep += ts[:max(0, round(len(ts) * (1.0 - reject_frac)))]
    return keep


def panel(tf, syms):
    print(f"\n{'-' * 78}\n{tf} · {len(syms)} FRESH symbols, all bars — "
          f"scored once\n{'-' * 78}")
    print(f"  {'':3} {'gate':34} {'R/trade':>8} {'+/-':>6} {'n':>6} "
          f"{'R/1k':>7} {'refused':>8} {'mult':>5}")
    out = {}
    for aid, name, over in ARMS:
        p = dataclasses.replace(BASE, **over)
        g = run_arm(tf, p, syms)
        m, se, n = clustered(g["res"].real)
        thru = 1000.0 * g["res"].netR / max(1, g["bars"])
        cs0 = next((LOADED[tf][s] for s in syms if LOADED[tf].get(s)), [])
        mult = U.htf_mult(cs0, p) if cs0 else 0
        print(f"  {aid:3} {name:34} {m:+8.3f} {se:6.3f} {n:6} "
              f"{thru:+7.3f} {g['res'].nHtf:8} {mult:5}"
              + ("   ·descriptive" if aid in DESCRIPTIVE else "")
              + ("   CAP!" if g["res"].nCap else ""))
        out[aid] = dict(m=m, se=se, n=n, thru=thru, res=g["res"],
                        ctls=g["ctl"], mult=mult)
    return out


def main():
    assert_disjoint()
    argv = [a for a in sys.argv[1:] if a in TFS]
    tfs = argv or list(TFS)
    for tf in tfs:
        LOADED[tf] = load(tf, SYMBOLS_FRESH)
        have = [s for s in SYMBOLS_FRESH
                if len(LOADED[tf].get(s) or []) >= MIN_BARS]
        if len(have) < 20:
            print(f"{tf}: only {len(have)} fresh symbols cached. Run "
                  f"undertow_sweep.py --fetch-fresh")
            return 2

    print("UNDERTOW HTF GATE — does agreement with a higher timeframe help?")
    print("prereg: indicators/undertow/prereg/PREREG_undertow_htf.md")
    print(f"45 FRESH symbols, DISJOINT from the 23 every other study used · "
          f"fees {FEE * 1e4:.0f}bp")
    print("no train/holdout split: nothing is selected, H2 is fixed in advance")
    print("the control is a RANDOM GATE matched on rejection rate, not a "
          "random entry")

    rows = []
    for tf in tfs:
        syms = [s for s in SYMBOLS_FRESH
                if len(LOADED[tf].get(s) or []) >= MIN_BARS]
        ho = panel(tf, syms)
        a, b = ho[PRIMARY], ho["H0"]

        # The matched random gate, at H2's own rejection rate.
        frac = 1.0 - (a["n"] / b["n"] if b["n"] else 1.0)
        rg = random_gate(tf, syms, frac)
        rm, rse, rn = clustered(rg)
        print(f"\n  R   random gate, {100 * frac:.1f}% refused      "
              f"{rm:+8.3f} {rse:6.3f} {rn:6}      ·THE CONTROL")

        d = a["m"] - b["m"]
        dse = math.sqrt(a["se"] ** 2 + b["se"] ** 2)
        z = d / dse if dse else 0.0
        dg = a["m"] - rm
        dgse = math.sqrt(a["se"] ** 2 + rse ** 2)
        # Reported for continuity with the other eight pages, not a bar.
        ce = clustered(a["ctls"])[0] if a["ctls"] else float("nan")

        bars = [a["n"] >= 200,
                all(ho[x]["res"].nCap == 0 for x in ho),
                d >= 0.10 and abs(z) >= 2.0,
                dgse > 0 and dg >= dgse,
                a["m"] > 0,
                None,                       # bar 6 is cross-timeframe
                a["thru"] >= b["thru"]]
        print(f"\n  BARS for {PRIMARY} (HTF 4h)")
        print(f"    1 coverage        {a['n']} trades   "
              f"{'PASS' if bars[0] else 'FAIL — a bound'}")
        print(f"    2 not confounded  nCap 0 everywhere   "
              f"{'PASS' if bars[1] else 'FAIL — VOID'}")
        print(f"    3 beats baseline  H2 - H0 = {d:+.3f} +/- {dse:.3f} "
              f"(z {z:+.2f})   {'PASS' if bars[2] else 'FAIL'}")
        print(f"    4 BEATS THE RANDOM GATE  {a['m']:+.3f} vs {rm:+.3f}, "
              f"diff {dg:+.3f} +/- {dgse:.3f}   "
              f"{'PASS' if bars[3] else 'FAIL'}")
        print(f"    5 positive        {a['m']:+.3f} R   "
              f"{'PASS' if bars[4] else 'FAIL'}")
        print(f"    7 throughput      {a['thru']:+.3f} vs {b['thru']:+.3f} "
              f"R per 1k bars   {'PASS' if bars[6] else 'FAIL'}")
        print(f"        (random-entry control, reported only: {ce:+.3f})")
        rows.append(dict(tf=tf, m=a["m"], h0=b["m"], d=d, z=z, rg=rm,
                         n=a["n"], thru=a["thru"], t0=b["thru"], bars=bars))

    print(f"\n{'=' * 78}\nVERDICT\n{'=' * 78}\n")
    print(f"  {'tf':8} {'H2 4h':>8} {'H0 off':>8} {'delta':>7} {'z':>6} "
          f"{'rnd gate':>9} {'n':>6} {'R/1k':>7} {'vs':>7}  bars 1-5,7")
    for v in rows:
        flag = "".join("P" if x else "." for x in v["bars"] if x is not None)
        print(f"  {v['tf']:8} {v['m']:+8.3f} {v['h0']:+8.3f} {v['d']:+7.3f} "
              f"{v['z']:+6.2f} {v['rg']:+9.3f} {v['n']:6} {v['thru']:+7.3f} "
              f"{v['t0']:+7.3f}  {flag}")
    pos = [v for v in rows if v["m"] > 0]
    print(f"\n  6 NOT ONE TIMEFRAME  {len(pos)} of {len(rows)} positive   "
          f"{'PASS' if len(pos) >= 2 else 'FAIL'}")
    won = sum(1 for v in rows
              if v["bars"][2] and v["bars"][3] and v["bars"][4]
              and v["bars"][6])
    print()
    if len(pos) >= 2 and won >= 2:
        print("  THE HTF GATE CLEARS THE PROMOTION RULE.")
        print("  First thing in Undertow to beat a matched random gate, on a")
        print("  population nothing here has seen. It earns the default, the")
        print("  Pine work, and a forward run — not a conclusion.")
    else:
        print("  THE HTF GATE DOES NOT CLEAR THE PROMOTION RULE.")
        print("  Ninth component measured without an effect, and this one")
        print("  cannot be blamed on a spent holdout: the population had")
        print("  never been looked at. That makes it the strongest negative")
        print("  in the project, and the 45 fresh symbols are what it leaves")
        print("  behind — every future question now gets a clean population.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
