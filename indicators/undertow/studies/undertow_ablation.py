"""Which of Undertow's three gates is doing anything? Runs exactly what
prereg/PREREG_undertow_pin_value.md pre-registered.

    PYTHONPATH=. python3 indicators/undertow/studies/undertow_ablation.py
    PYTHONPATH=. python3 indicators/undertow/studies/undertow_ablation.py --uncapped
    PYTHONPATH=. python3 indicators/undertow/studies/undertow_ablation.py Min30

RUN 1 (no flag) IS THE v1 PREREG AND IT IS VOID -- see the measurement file. It
is kept runnable rather than deleted so the void can be reproduced. `--uncapped`
is the v2 prereg: the same six arms with maxLive 64 instead of 4.

Six arms, one frozen configuration, every arm reported. NOTHING IS SELECTED, so
unlike undertow_sweep.py there is no maximum being taken and no holdout needed
to protect against taking one — see the prereg for why that is the right call
here and the wrong one there.

    A0  FULL             the strategy as specified
    A1  no wick test     is the candle taxonomy doing anything?
    A2  no colour test
    A3  LOCATION ONLY    the primary contrast is A0 - A3
    A4  no location test
    A5  no Ending rules  cross-checks the ghost column from the other side

THE CAP IS A CONFOUND AND THE PREREG SAYS SO IN ADVANCE. Removing a gate admits
far more candidates, and `maxLive = 4` turns the surplus away rather than
trading them, so a looser arm is throttled in a way the baseline is not. nCap is
printed for every arm and an arm whose nCap exceeds its fills is marked
CONFOUNDED and its contrast is void. That rule was written down before the run,
which is the only time such a rule means anything.

Reads the same .cache/ candles undertow_sweep.py fetched. Run that with --fetch
first if the cache is empty. Never run by preflight: a study is not a check.
"""
from __future__ import annotations

import dataclasses
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

from indicators.undertow.port import undertow as U               # noqa: E402
from indicators.undertow.studies.undertow_sweep import (         # noqa: E402
    FEE, LOADED, SEED, TFS, clustered, control, load, quadrant)
from research.data import SYMBOLS                                # noqa: E402

# The frozen baseline. Every Pine default, rr 3.0, costs on.
#
# maxLive: 4 is the Pine's, and the Pine has it for TradingView's 500-drawing
# budget -- SPEC.md says so. It is a CHARTING ARTIFACT and in a measurement it
# should not exist, which is what run 1 got wrong. `--uncapped` raises it to 64,
# verified to bring nCap to exactly 0 on the loosest arm (1000 gives the
# identical trade count, so 64 is "enough", not a tuned number).
#
# The port's DEFAULT stays 4 so deploy/undertow-port-check.py keeps holding the
# port to the Pine's inputs. The override is here, in the open.
BASE = U.P(rr=3.0, feeFrac=FEE)
UNCAPPED = 64

ARMS = [
    ("A0", "FULL", {}),
    ("A1", "no wick test", dict(useFamily=False)),
    ("A2", "no colour test", dict(useColour=False)),
    ("A3", "LOCATION ONLY", dict(useFamily=False, useColour=False)),
    ("A4", "no location test", dict(locTol=50)),
    ("A5", "no Ending rules", dict(endMinor=U.E_OFF, endSweep=False,
                                   endStale=False, retraceMax=0)),
]

# The two quadrants undertow_sweep.py never scored. Reported as a second panel
# so the contrast can be seen on bars that have never been used for anything.
FRESH = [(s, False) for i, s in enumerate(SYMBOLS) if i % 2 == 0] \
      + [(s, True) for i, s in enumerate(SYMBOLS) if i % 2 == 1]


def run_arm(tf, p, pairs, seed):
    """`pairs` is (symbol, older), so one panel can mix quadrants.

    The control is drawn HERE, per (symbol, quadrant) group, rather than by the
    caller -- a random entry has to come from the same slice of bars as the
    real trade it replaces, and a panel that spans both halves cannot name one
    quadrant for the whole thing.
    """
    data = LOADED[tf]
    agg = U.Result()
    ctl = []
    for sym, older in pairs:
        cs = data.get(sym)
        if not cs or len(cs) < 1200:
            continue
        seg, skip = quadrant(cs, older)
        r = U.run(seg, p, sym)
        r.trades = [t for t in r.trades if t.fillBar >= skip]
        agg.add(r)
        if r.real:
            ctl += control(r.real, tf, [sym], older, p, seed=seed)
    return agg, ctl


def diff_se(a, b):
    """SE of the difference of two means, clustered by symbol.

    The two arms share symbols and largely share bars, so their errors are
    POSITIVELY CORRELATED and treating them as independent OVERSTATES the SE.
    That is the conservative direction for a study trying to detect a
    difference, so it is what is used -- and it is said out loud rather than
    left for someone to notice.
    """
    _, sa, _ = clustered(a)
    _, sb, _ = clustered(b)
    if not (sa and sb) or math.isinf(sa) or math.isinf(sb):
        return float("inf")
    return math.sqrt(sa ** 2 + sb ** 2)


def panel(tf, pairs, title, cap):
    print(f"\n{'-' * 78}\n{tf} · {title}\n{'-' * 78}")
    print(f"  {'':3} {'arm':18} {'mean R':>8} {'+/-':>6} {'n':>5} "
          f"{'cap':>5} {'ctl':>7}  note")
    out = {}
    for k, (aid, name, over) in enumerate(ARMS):
        p = dataclasses.replace(BASE, maxLive=cap, **over)
        # A fixed per-arm offset, not hash(aid): str hashing is salted per
        # process, so a hashed seed would make the run irreproducible.
        r, ctl = run_arm(tf, p, pairs, seed=SEED + 101 * k)
        m, se, n = clustered(r.real)
        cm = clustered(ctl)[0] if ctl else float("nan")
        # v2 bar 2 is ZERO turned away, not "fewer than were traded": below
        # zero-ish the cap is still choosing setups. v1's looser rule is kept
        # for reproducing the void.
        confounded = (r.nCap > 0) if cap == UNCAPPED else (r.nCap > max(1, n))
        note = []
        if n < 150:
            note.append("UNDERPOWERED")
        if se > 0.25:
            note.append("SE>0.25")
        if confounded:
            note.append("CONFOUNDED by maxLive")
        print(f"  {aid:3} {name:18} {m:+8.3f} {se:6.3f} {n:5} "
              f"{r.nCap:5} {cm:+7.3f}  {' · '.join(note)}")
        out[aid] = dict(m=m, se=se, n=n, cap=r.nCap, ctl=cm, res=r,
                        confounded=confounded)
    return out


def verdict(tf, o, cap):
    """The primary contrast, against the bars written down beforehand."""
    a0, a3 = o["A0"], o["A3"]
    d = a0["m"] - a3["m"]
    dse = diff_se(a0["res"].real, a3["res"].real)
    z = d / dse if dse and not math.isinf(dse) else 0.0
    cover = a0["n"] >= 150 and a3["n"] >= 150
    clean = not (a0["confounded"] or a3["confounded"])
    earns = d >= 0.15 and abs(z) >= 2.0
    dead = abs(d) < 0.15
    print(f"\n  PRIMARY  A0 - A3 = {d:+.3f} R  +/- {dse:.3f}  (z {z:+.2f})")
    print(f"    1 coverage      A0 {a0['n']}, A3 {a3['n']}"
          f"          {'PASS' if cover else 'FAIL — read as a bound'}")
    want = "must be 0" if cap == UNCAPPED else "must not exceed fills"
    print(f"    2 not confounded A0 cap {a0['cap']}, A3 cap {a3['cap']} "
          f"({want})   {'PASS' if clean else 'FAIL — contrast is void'}")
    if not (cover and clean):
        state = "VOID"
    elif earns:
        state = "THE CANDLE EARNS ITS PLACE"
    elif dead:
        state = "THE CANDLE IS DEAD"
    else:
        state = "INCONCLUSIVE"
    print(f"    3/4 verdict     {state}")
    return dict(tf=tf, d=d, dse=dse, z=z, state=state,
                n0=a0["n"], n3=a3["n"])


def main():
    uncapped = "--uncapped" in sys.argv[1:]
    cap = UNCAPPED if uncapped else BASE.maxLive
    argv = [a for a in sys.argv[1:] if a in TFS]
    tfs = argv or list(TFS)
    for tf in tfs:
        LOADED[tf] = load(tf)
        if not LOADED[tf]:
            print(f"{tf}: no cached candles. Run undertow_sweep.py --fetch.")
            return 2

    print("UNDERTOW ABLATION — which gate is doing anything?")
    print("prereg: indicators/undertow/prereg/PREREG_undertow_pin_value"
          + ("_v2.md" if uncapped else ".md  (RUN 1 — VOID, see the "
             "measurement file)"))
    print(f"maxLive {cap}"
          + ("  — the charting cap removed; bar 2 requires nCap == 0"
             if uncapped else "  — the Pine's charting cap, kept"))
    print(f"frozen config: {BASE.tag()}")
    print(f"fees {FEE * 1e4:.0f}bp round trip, seed {SEED}")
    print("\nNOTHING IS SELECTED HERE. Six arms, all reported, one primary")
    print("contrast per timeframe declared in advance: A0 - A3.")

    allp = [(s, True) for s in SYMBOLS] + [(s, False) for s in SYMBOLS]
    vs = []
    for tf in tfs:
        o = panel(tf, allp, "PRIMARY — all 23 symbols, both halves", cap)
        vs.append(verdict(tf, o, cap))
        panel(tf, FRESH, "SECOND PANEL — the two quadrants the sweep never "
                         "scored", cap)

    print(f"\n{'=' * 78}\nVERDICT\n{'=' * 78}\n")
    print(f"  {'tf':8} {'A0-A3':>8} {'+/-':>6} {'z':>6} {'nA0':>6} {'nA3':>6}"
          f"  state")
    for v in vs:
        print(f"  {v['tf']:8} {v['d']:+8.3f} {v['dse']:6.3f} {v['z']:+6.2f} "
              f"{v['n0']:6} {v['n3']:6}  {v['state']}")
    dead = [v for v in vs if v["state"] == "THE CANDLE IS DEAD"]
    earn = [v for v in vs if v["state"] == "THE CANDLE EARNS ITS PLACE"]
    print()
    if len(earn) >= 2:
        print("  THE CANDLE EARNS ITS PLACE on 2 of 3 timeframes.")
        print("  It still has to beat its own control before it is an edge.")
    elif len(dead) >= 2:
        print("  THE CANDLE IS DEAD on 2 of 3 timeframes.")
        print("  The honest strategy is the location alone: take the pullback")
        print("  extreme while the structure bias is running. Group 2 of the")
        print("  inputs, the 16-variant taxonomy and the wick-edge margin are")
        print("  describing a filter that does not filter.")
    else:
        print("  INCONCLUSIVE. Neither bar 3 nor bar 4 is met on 2 of 3")
        print("  timeframes; per the prereg this is reported with that word")
        print("  and no stronger claim is made from it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
