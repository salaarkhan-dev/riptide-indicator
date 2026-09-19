"""Two timeframes, EMA 20/50 on each, trade only when they agree.

    PYTHONPATH=. python3 indicators/undertow/studies/undertow_mtf.py

Runs exactly what prereg/PREREG_undertow_mtf_ema.md pre-registered.

FROM A SUPPLIED PINE SCRIPT, "MTF Market Structure Bias": EMA 20/50 on a slower
timeframe and on a faster one, FULL BULLISH / FULL BEARISH / MIXED, and stand
aside on MIXED.

NOT ALREADY MEASURED, and both near misses were checked. S2 in
UNDERTOW_BIAS_SOURCE.md was EMA 50/200 on ONE timeframe, and that prereg says
"'EMA 20/50 might do better' is a different prereg" -- this is it.
UNDERTOW_HTF.md gated on the STRUCTURE engine one timeframe up, and its closing
line asks for exactly this study.

THE THIRD STATE IS THE POINT. Every other direction source here is always long
or short; this one ABSTAINS. That is a gate and a direction at once, so:

    M2      the direction alone, no abstaining
    M1      M2 plus the alignment gate      <- THE PRIMARY
    G       M2 with the same NUMBER of trades discarded at random

M1 - M2 is what the second timeframe buys. M1 - G is whether it bought anything
a coin could not.

POPULATION: SYMBOLS_FRESH2, ranks 46-90, disjoint from the 23 and from
SYMBOLS_FRESH. UNDERTOW_HTF.md has been read on FRESH, so FRESH is no longer
untouched; it runs here as a SECONDARY panel where M0 must reproduce that
page's H0 exactly.
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
from research.symbols_fresh import (SYMBOLS_FRESH,               # noqa: E402
                                    SYMBOLS_FRESH2, assert_disjoint)

# AS PUBLISHED, PINNED — see test_studies_pin_their_settings.py. Identical to
# undertow_htf.py's BASE on purpose: M0 here and H0 there must agree on the
# FRESH panel, which is the check that both studies run the same machine.
BASE = U.P(pinAt=U.PIN_PULL, pinLag=0, biasGate=U.BG_TRADEABLE, famStrict=False, armWins=False, stopSrc=U.S_PULL, useBackup=False, biasSrc=U.BS_STRUCT, pinNewest=False, famPriority=False, failTest=U.T_CLOSE, confirmOrder=U.C_EITHER, maxLive=64, feeFrac=FEE, rr=3.5,
           swingSrc=U.SW_RANGE, msLen=6, msShortLen=2,
           endMinor=U.E_OFF, endSweep=False, endStale=False)

MTF = dict(biasSrc=U.BS_MTF, mtfFast=20, mtfSlow=50, mtfMult=2)
ARMS = [
    ("M0", "structure — BASELINE (what ships)", {}),
    ("M1", "MTF EMA 20/50 x2 — THE PRIMARY", MTF),
    ("M2", "EMA 20/50, one timeframe", dict(biasSrc=U.BS_EMA, emaFast=20,
                                            emaSlow=50)),
    ("M3", "MTF EMA 50/200 x2", {**MTF, "mtfFast": 50, "mtfSlow": 200}),
]
PRIMARY, DESCRIPTIVE = "M1", {"M2", "M3"}
MIN_BARS = 11000


def usable(tf, syms):
    return [s for s in syms if len(LOADED[tf].get(s) or []) >= MIN_BARS]


def run_arm(tf, p, syms):
    agg = U.Result()
    bars = 0
    for sym in syms:
        cs = LOADED[tf][sym]
        agg.add(U.run(cs, p, sym))
        bars += len(cs)
    return agg, bars


def random_gate(tf, syms, frac, seed=SEED):
    """M2's trades with a matched FRACTION discarded at random, per symbol.

    The control the prereg names. It isolates the alignment gate from the fact
    that ANY rule refusing a fifth of the trades moves the mean, and roughly
    half of them move it up.
    """
    rnd = random.Random(seed)
    p = dataclasses.replace(BASE, biasSrc=U.BS_EMA, emaFast=20, emaSlow=50)
    keep = []
    for sym in syms:
        ts = list(U.run(LOADED[tf][sym], p, sym).real)
        rnd.shuffle(ts)
        keep += ts[:max(0, round(len(ts) * (1.0 - frac)))]
    return keep


def panel(tf, syms, title):
    print(f"\n{'-' * 78}\n{tf} · {title} · {len(syms)} symbols\n{'-' * 78}")
    print(f"  {'':3} {'direction':36} {'R/trade':>8} {'+/-':>6} {'n':>6} "
          f"{'R/1k':>7} {'mixed%':>7}")
    out = {}
    for aid, name, over in ARMS:
        p = dataclasses.replace(BASE, **over)
        res, bars = run_arm(tf, p, syms)
        m, se, n = clustered(res.real)
        thru = 1000.0 * res.netR / max(1, bars)
        mixpc = 0.0
        if over.get("biasSrc") == U.BS_MTF:
            st, _ = U.structure(LOADED[tf][syms[0]], p)
            mx = st["mixed"]
            mixpc = 100.0 * sum(mx) / max(1, len(mx))
        print(f"  {aid:3} {name:36} {m:+8.3f} {se:6.3f} {n:6} {thru:+7.3f} "
              f"{mixpc:6.1f}%"
              + ("   ·descriptive" if aid in DESCRIPTIVE else "")
              + ("   CAP!" if res.nCap else ""))
        out[aid] = dict(m=m, se=se, n=n, thru=thru, res=res)
    return out


def score(tf, syms, o, primary=True):
    a, b, m2 = o[PRIMARY], o["M0"], o["M2"]
    frac = 1.0 - (a["n"] / m2["n"] if m2["n"] else 1.0)
    gm, gse, gn = clustered(random_gate(tf, syms, frac))
    print(f"\n  G   random gate on M2, {100 * frac:.1f}% discarded   "
          f"{gm:+8.3f} {gse:6.3f} {gn:6}      ·THE CONTROL")
    print(f"      M1 - M2 = {a['m'] - m2['m']:+.3f}   "
          f"(what the second timeframe buys)")

    d = a["m"] - b["m"]
    dse = math.sqrt(a["se"] ** 2 + b["se"] ** 2)
    z = d / dse if dse else 0.0
    dg = a["m"] - gm
    dgse = math.sqrt(a["se"] ** 2 + gse ** 2)
    bars = [a["n"] >= 200,
            all(o[x]["res"].nCap == 0 for x in o),
            d >= 0.10 and abs(z) >= 2.0,
            dgse > 0 and dg >= dgse,
            a["m"] > 0]
    if primary:
        print(f"\n  BARS for {PRIMARY}")
        print(f"    1 coverage        {a['n']} trades   "
              f"{'PASS' if bars[0] else 'FAIL — a bound'}")
        print(f"    2 not confounded  nCap 0 everywhere   "
              f"{'PASS' if bars[1] else 'FAIL — VOID'}")
        print(f"    3 beats baseline  M1 - M0 = {d:+.3f} +/- {dse:.3f} "
              f"(z {z:+.2f})   {'PASS' if bars[2] else 'FAIL'}")
        print(f"    4 BEATS THE RANDOM GATE  {a['m']:+.3f} vs {gm:+.3f}, "
              f"diff {dg:+.3f} +/- {dgse:.3f}   "
              f"{'PASS' if bars[3] else 'FAIL'}")
        print(f"    5 positive        {a['m']:+.3f} R   "
              f"{'PASS' if bars[4] else 'FAIL'}")
        print(f"      (R per 1k bars {a['thru']:+.3f} vs {b['thru']:+.3f} — "
              f"REPORTED, NOT A BAR: see the prereg on why it was one last "
              f"time and should not have been)")
    return dict(tf=tf, m=a["m"], m0=b["m"], m2=m2["m"], d=d, z=z, g=gm,
                n=a["n"], bars=bars)


def main():
    assert_disjoint()
    argv = [a for a in sys.argv[1:] if a in TFS]
    tfs = argv or list(TFS)
    print("UNDERTOW MTF EMA — two timeframes, 20/50, trade only when aligned")
    print("prereg: indicators/undertow/prereg/PREREG_undertow_mtf_ema.md")
    print("PRIMARY population: SYMBOLS_FRESH2, ranks 46-90, disjoint from the")
    print("23 and from SYMBOLS_FRESH — no number from it has been looked at")
    print("the control is a RANDOM GATE on M2 matched to M1's rejection rate")

    rows = []
    for tf in tfs:
        LOADED[tf] = load(tf, SYMBOLS_FRESH2)
        syms = usable(tf, SYMBOLS_FRESH2)
        if len(syms) < 20:
            print(f"\n{tf}: only {len(syms)} FRESH2 symbols cached. Run "
                  f"undertow_sweep.py --fetch-fresh2")
            return 2
        rows.append(score(tf, syms,
                          panel(tf, syms, "PRIMARY — FRESH2, scored once")))

    print(f"\n{'=' * 78}\nVERDICT — SYMBOLS_FRESH2\n{'=' * 78}\n")
    print(f"  {'tf':8} {'M1':>8} {'M0':>8} {'M2':>8} {'delta':>7} {'z':>6} "
          f"{'rnd gate':>9} {'n':>6}  bars")
    for v in rows:
        print(f"  {v['tf']:8} {v['m']:+8.3f} {v['m0']:+8.3f} {v['m2']:+8.3f} "
              f"{v['d']:+7.3f} {v['z']:+6.2f} {v['g']:+9.3f} {v['n']:6}  "
              + "".join("P" if x else "." for x in v["bars"]))
    pos = [v for v in rows if v["m"] > 0]
    print(f"\n  6 NOT ONE TIMEFRAME  {len(pos)} of {len(rows)} positive   "
          f"{'PASS' if len(pos) >= 2 else 'FAIL'}")
    won = sum(1 for v in rows if v["bars"][2] and v["bars"][3] and v["bars"][4])

    print(f"\n{'=' * 78}\nSECONDARY — SYMBOLS_FRESH. NOT the primary: this set "
          f"was read\nin UNDERTOW_HTF.md. M0 here must equal H0 there.\n"
          f"{'=' * 78}")
    for tf in tfs:
        LOADED[tf] = load(tf, SYMBOLS_FRESH)
        syms = usable(tf, SYMBOLS_FRESH)
        if len(syms) >= 20:
            score(tf, syms, panel(tf, syms, "SECONDARY — FRESH"),
                  primary=False)

    print()
    if len(pos) >= 2 and won >= 2:
        print("  MTF ALIGNMENT CLEARS ITS BARS on the primary population.")
        print("  First thing in Undertow to beat a matched random gate. It")
        print("  earns a place on the chart and a forward run — and the")
        print("  DEFAULT only if the FRESH panel above agrees.")
    else:
        print("  MTF ALIGNMENT DOES NOT CLEAR ITS BARS.")
        print("  Tenth component measured without an effect, on a third")
        print("  population nothing here had seen, with the right control.")
        print("  It stays in the port as a dropdown value, off.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
