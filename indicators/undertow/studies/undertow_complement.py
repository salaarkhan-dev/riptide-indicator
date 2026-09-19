"""Does the 1h complement cell replicate on a universe nobody has seen?

    PYTHONPATH=. python3 indicators/undertow/studies/undertow_complement.py

Runs exactly what prereg/PREREG_undertow_complement.md pre-registered.

WHAT THIS IS REPLICATING. ../measurements/UNDERTOW_STRICT.md split the shipped
population into its two shape halves -- an exact partition, because the strict
gate is an exact subset -- and on Min60 the NON-priority half (hanging man
long, inverted hammer short) scored +0.197 R per trade at a 27.3% win rate
against the priority half's -0.062. Diff +0.258, z +2.46: the only |z| >= 2 in
eighteen studies, and it points AGAINST the strategy's stated priority.

THE HYPOTHESIS WAS SELECTED BECAUSE IT WAS THE BIGGEST OF THREE NUMBERS, and
every design choice here follows from that:

  * Min60 is the PRE-REGISTERED PRIMARY. Min15 and Min30 are reported and
    cannot rescue it. Testing "whichever timeframe works" on a fresh set
    would repeat the original sin at a larger scale.
  * the effect size to beat is stated in advance, not "positive".
  * a null is the predicted outcome and a useful one: it closes the only open
    question in the programme for the price of one universe.

WHY THE PRIMARY IS A SLICE AND NOT `famInvert`. The finding was a slice, so the
replication is of a slice. They are different objects: with the inverse gate
RUNNING, priority-shaped pins never enter the candidate pool, so famPriority's
rivalry has nothing to act on and the surviving set differs -- on one spent
symbol the two halves run separately come to 37 + 30 against the baseline's 64.
I3 is the tradeable version and is reported as descriptive; I1 is the measured
one and is the primary.
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
from research.symbols_fresh import (SYMBOLS_FRESH11,             # noqa: E402
                                    assert_disjoint)
from riptide.config import BAR_SECONDS                           # noqa: E402

# AS SHIPPED, PINNED -- see test_studies_pin_their_settings.py. Identical to
# undertow_strict.py's BASE, deliberately: this study has to reproduce that
# one's I2 arm exactly or its own impossibility fires.
BASE = U.P(pinLag=0, biasGate=U.BG_TRADEABLE, stopSrc=U.S_PULL, useBackup=False, biasSrc=U.BS_SMC, smcSwingLen=14, smcInternalLen=5,
           confirmOrder=U.C_WF, failTest=U.T_TOUCH,
           pinNewest=True, famPriority=True, famStrict=False, famInvert=False,
           pinAt=U.PIN_PULL, locTol=0, armWins=False,
           swingSrc=U.SW_RANGE, msLen=6, msShortLen=2,
           endMinor=U.E_FLIP, endSweep=False, endStale=False, retraceMax=70,
           maxLive=64, feeFrac=FEE, rr=3.5)

PRIMARY_TF = "Min60"
MIN_BARS = 11000
MIN_SYMS = 20


def is_prio(t):
    """The shape the strategy calls first choice, for this trade's direction:
    the hammer in a bearish trend, the shooting star in a bullish one."""
    return t.code == ("HAM" if t.short else "SS")


def random_gate(trades, frac, seed=SEED):
    """I0's own trades with `frac` of them discarded at random, per symbol.

    THE POINT OF MATCHING PER SYMBOL rather than globally: the discard rate
    varies by symbol, and a global shuffle would quietly re-weight the universe
    toward whichever symbols the coin happened to keep.
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


def row(aid, name, trades, days, note=""):
    m, se, n = clustered(trades)
    wr = 100.0 * sum(1 for t in trades if t.won) / max(1, n)
    pc = 100.0 * sum(1 for t in trades if is_prio(t)) / max(1, n)
    print(f"  {aid:3} {name:38} {m:+8.3f} {se:6.3f} {n:6} "
          f"{wr:5.1f}% {pc:5.1f}% {len(trades) / days:9.2f}{note}")
    return dict(m=m, se=se, n=n, wr=wr, pc=pc)


def main():
    assert_disjoint()
    argv = [a for a in sys.argv[1:] if a in TFS]
    tfs = argv or list(TFS)
    print("UNDERTOW — DOES THE 1h COMPLEMENT CELL REPLICATE")
    print("prereg: indicators/undertow/prereg/PREREG_undertow_complement.md")
    print("population: SYMBOLS_FRESH11, never looked at, frozen for this")
    print(f"THE PRIMARY TIMEFRAME IS {PRIMARY_TF}, named in the prereg before")
    print("the run. The hypothesis was selected because it was the biggest of")
    print("three numbers, so the other two are reported and cannot rescue it.")

    rows, void = [], False
    for tf in tfs:
        LOADED[tf] = load(tf, SYMBOLS_FRESH11)
        syms = [s for s in SYMBOLS_FRESH11
                if len(LOADED[tf].get(s) or []) >= MIN_BARS]
        if len(syms) < MIN_SYMS:
            print(f"\n{tf}: only {len(syms)} FRESH11 symbols carry "
                  f"{MIN_BARS} bars — the prereg says this timeframe is NOT "
                  f"REPORTED." + (f"\n  AND {tf} IS THE PRIMARY. The prereg "
                                  f"names this outcome: the question is "
                                  f"unanswered and one\n  more set of 45 "
                                  f"remains in the venue to answer it."
                                  if tf == PRIMARY_TF else ""))
            continue
        days = sum(len(LOADED[tf][s]) for s in syms) * BAR_SECONDS[tf] / 86400

        print(f"\n{'-' * 78}\n{tf} · {len(syms)} symbols, scored once"
              + ("   ·THE PRIMARY" if tf == PRIMARY_TF else "")
              + f"\n{'-' * 78}")
        print(f"  {'':3} {'configuration':38} {'R/trade':>8} {'+/-':>6} "
              f"{'n':>6} {'win%':>6} {'prio%':>6} {'trades/d':>9}")

        base, strict, inv = U.Result(), U.Result(), U.Result()
        bkeys = {}
        for sym in syms:
            r = U.run(LOADED[tf][sym], BASE, sym)
            base.add(r)
            for t in r.real:
                bkeys[(sym, t.bar, t.short)] = t
            strict.add(U.run(LOADED[tf][sym],
                             dataclasses.replace(BASE, famStrict=True), sym))
            inv.add(U.run(LOADED[tf][sym],
                          dataclasses.replace(BASE, famStrict=True,
                                              famInvert=True), sym))
        # THE TWO SLICES. Cut from ONE run of the baseline, which is what makes
        # them a partition -- see the impossibility below and the prereg's note
        # on why the primary is not `famInvert`.
        i1 = [t for t in bkeys.values() if not is_prio(t)]
        i2 = [t for t in bkeys.values() if is_prio(t)]

        o0 = row("I0", "what ships — both shapes", base.real, days)
        a = row("I1", "the NON-priority half, as a slice", i1, days,
                "   ·THE PRIMARY")
        o2 = row("I2", "the priority half, as a slice", i2, days)
        o3 = row("I3", "the inverse gate as a RUN", inv.real, days,
                 "   ·descriptive")

        # THE IMPOSSIBILITIES, checked before anything is read as a result.
        sm, _, sn = clustered(strict.real)
        live = [
            ("the slices PARTITION I0", len(i1) + len(i2) == len(base.real)),
            ("I1 is ONLY non-priority", not any(is_prio(t) for t in i1)),
            ("I2 is ONLY priority", all(is_prio(t) for t in i2)),
            ("I2 reproduces famStrict",
             sn == len(i2) and abs(sm - o2["m"]) < 1e-12),
            ("nCap is 0 everywhere",
             base.nCap == 0 and strict.nCap == 0 and inv.nCap == 0)]
        for label, held in live:
            print(f"  IMPOSSIBILITY  {label:26} "
                  + ("holds" if held else "VIOLATED — RUN IS VOID"))
        if not live[3][1]:
            print(f"      famStrict's own arm is {sn} trades at {sm:+.3f}; "
                  f"the slice is {len(i2)} at {o2['m']:+.3f}. One of them is "
                  f"not what UNDERTOW_STRICT.md measured.")
        void = void or not all(h for _, h in live)

        frac = 1.0 - (a["n"] / o0["n"] if o0["n"] else 1.0)
        gm, gse, gn = clustered(random_gate(base.real, max(0.0, frac)))
        print(f"\n  C   random gate, {100 * max(0.0, frac):.1f}% discarded"
              f"{'':14} {gm:+8.3f} {gse:6.3f} {gn:6}      ·THE CONTROL")

        d = a["m"] - o2["m"]
        dse = math.sqrt(a["se"] ** 2 + o2["se"] ** 2)
        z = d / dse if dse else 0.0
        dg, dgse = a["m"] - gm, math.sqrt(a["se"] ** 2 + gse ** 2)
        bars = [a["n"] >= 200 and len(syms) >= MIN_SYMS,
                all(h for _, h in live),
                d >= 0.10 and abs(z) >= 2.0,
                dgse > 0 and dg >= dgse,
                a["m"] > 0]
        print(f"\n  BARS for I1"
              + ("" if tf == PRIMARY_TF else "   (NOT the primary timeframe — "
                                             "reported, cannot rescue it)"))
        print(f"    1 coverage        {a['n']} trades, {len(syms)} symbols   "
              f"{'PASS' if bars[0] else 'FAIL — a bound'}")
        print(f"    2 not confounded  all five hold   "
              f"{'PASS' if bars[1] else 'FAIL — VOID'}")
        print(f"    3 THE CONTRAST REPLICATES  I1 - I2 = {d:+.3f} +/- "
              f"{dse:.3f} (z {z:+.2f})   {'PASS' if bars[2] else 'FAIL'}")
        print(f"        FRESH7 had +0.258 +/- 0.105 here. The bar is +0.10 at "
              f"|z| >= 2, which at this SE needs about +{2 * dse:.2f}.")
        print(f"    4 beats its control  {a['m']:+.3f} vs {gm:+.3f}, "
              f"diff {dg:+.3f} +/- {dgse:.3f}   "
              f"{'PASS' if bars[3] else 'FAIL'}")
        print(f"    5 positive        {a['m']:+.3f} R   "
              f"{'PASS' if bars[4] else 'FAIL'}")
        print(f"    · the tradeable version  I3 - I1 = "
              f"{o3['m'] - a['m']:+.3f} — how much the rivalry effect moves it")
        rows.append(dict(tf=tf, m=a["m"], i0=o0["m"], i2=o2["m"], i3=o3["m"],
                         d=d, z=z, g=gm, n=a["n"], wr=a["wr"], bars=bars,
                         syms=len(syms)))

    prim = next((v for v in rows if v["tf"] == PRIMARY_TF), None)
    if not rows:
        print("\nNO TIMEFRAME HAD ENOUGH SYMBOLS. Nothing is reported.")
        return 2

    print(f"\n{'=' * 78}\nVERDICT\n{'=' * 78}\n")
    print(f"  {'tf':8} {'I1 other':>9} {'I2 prio':>8} {'I1 - I2':>8} {'z':>6} "
          f"{'I0':>8} {'rnd gate':>9} {'n':>6} {'win%':>6}  bars")
    for v in rows:
        print(f"  {v['tf']:8} {v['m']:+9.3f} {v['i2']:+8.3f} {v['d']:+8.3f} "
              f"{v['z']:+6.2f} {v['i0']:+8.3f} {v['g']:+9.3f} {v['n']:6} "
              f"{v['wr']:5.1f}%  " + "".join("P" if x else "." for x in v["bars"])
              + ("   ·PRIMARY" if v["tf"] == PRIMARY_TF else ""))

    print(f"\n  AGAINST FRESH7, where the finding came from")
    print(f"  {'tf':8} {'FRESH7 I1-I2':>13} {'FRESH11 I1-I2':>14}")
    for tf, was in (("Min15", -0.062), ("Min30", +0.037), ("Min60", +0.258)):
        v = next((x for x in rows if x["tf"] == tf), None)
        print(f"  {tf:8} {was:+13.3f} "
              + (f"{v['d']:+14.3f}" if v else f"{'not reported':>14}"))

    print()
    if void:
        print("  RUN IS VOID — a pre-registered impossibility fired.")
        print("  The numbers above are not published and FRESH11 is spent.")
        return 0
    if prim is None:
        print(f"  {PRIMARY_TF} WAS NOT REPORTED, and it is the primary. The")
        print("  prereg names this outcome: the question is unanswered. One")
        print("  more set of 45 remains in the venue to answer it, and the")
        print("  rows above are not a substitute for the one that is missing.")
        return 0
    sign = sum(1 for v in rows if v["tf"] != PRIMARY_TF and v["d"] > 0)
    b6 = sign >= 1
    print(f"  6 THE SIGN HOLDS SOMEWHERE ELSE  {sign} of "
          f"{len(rows) - 1} other timeframes positive   "
          f"{'PASS' if b6 else 'FAIL'}")
    print()
    if all(prim["bars"][2:5]) and b6:
        print("  IT REPLICATED. The first replicated positive finding in this")
        print("  project, and it arrived by measurement rather than from a")
        print("  diagram. famInvert goes on the chart as an input, OFF, with")
        print("  the page beside it. IT DOES NOT BECOME A DEFAULT ON TWO")
        print("  STUDIES — the prereg says a third confirmation on the last")
        print("  fresh set is what that would take.")
    elif all(prim["bars"][2:5]):
        print("  IT REPLICATED ON 1h AND NOWHERE ELSE. Same outcome as above")
        print("  and the page says '1h only' in its title.")
    elif prim["d"] <= -0.10 and abs(prim["z"]) >= 2.0:
        print("  IT REVERSED. The original sign did not survive fresh data,")
        print("  at |z| >= 2 the other way, which is stronger evidence against")
        print("  the shapes carrying information than either page alone.")
    else:
        print("  NULL — the FRESH7 cell was the ~14% coincidence its own page")
        print("  predicted. That is worth having: it closes the only open")
        print("  question in the programme, and one universe is the cheapest")
        print("  possible price for not trading on it.")
        print("  famInvert stays port-only. The taxonomy stays a naming")
        print("  scheme, which is what UNDERTOW_PIN_VALUE.md said first.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
