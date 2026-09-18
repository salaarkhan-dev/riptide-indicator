"""The priority shape as a GATE, not a ranking.

    PYTHONPATH=. python3 indicators/undertow/studies/undertow_strict.py

Runs exactly what prereg/PREREG_undertow_strict.md pre-registered.

WHAT IS BEING ASKED. `famPriority` shipped as a RANKING -- the priority shape
wins when both are live, the second choice trades when it is absent.
`famStrict` makes it a GATE: only the shooting star in a bull trend, only the
hammer in a bear trend, and the hanging man and the inverted hammer stop being
setups at all. With the colour rule already fixing the colour, what survives is
exactly one code per direction.

THE CONTROL IS A RANDOM GATE, not a random entry, and the design input says so
rather than the other way round. Measured on the spent 23 at maxLive 64, every
trade the gate takes the shipped rule also takes and it invents none -- 929 of
929 on Min15. A rule that throws away 45% of a population moves the mean
whatever it is, and half of all such rules move it up, so the thing to beat is
a coin refusing as often. That is the opposite of undertow_anchor.py and
undertow_scale.py, where the rule RELOCATED the population and a seeded random
entry was the honest control.

AND THE COMPLEMENT IS FREE. Because S1 is precisely the priority-coded half of
S0, `S0 - S1` is precisely the non-priority half: the two halves partition the
baseline exactly, with no second run and no rivalry caveat. S2 is that slice,
and it is the sharpest thing this study reports -- if the shape carries
information the priority half has to beat the other one.
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

# AS SHIPPED, PINNED -- see test_studies_pin_their_settings.py. This study is
# the one case where "as shipped" and "as pinned" are the same list, because
# the question is whether to change the chart and the thing to beat is
# therefore the chart. Every field the pinning test names is written out, at
# the value the chart carries today, so a later default drift fails the test
# rather than silently re-baselining this page.
BASE = U.P(stopSrc=U.S_PULL, biasTier=U.TIER_SWING, useBackup=False, biasSrc=U.BS_SMC, smcSwingLen=14, smcInternalLen=5,
           confirmOrder=U.C_WF, failTest=U.T_TOUCH,
           pinNewest=True, famPriority=True, famStrict=False,
           pinAt=U.PIN_PULL, locTol=0, armWins=False,
           swingSrc=U.SW_RANGE, msLen=6, msShortLen=2,
           endMinor=U.E_FLIP, endSweep=False, endStale=False, retraceMax=70,
           maxLive=64, feeFrac=FEE, rr=3.5)

ARMS = [
    ("S0", "what ships — the shape is a RANKING", {}),
    ("S1", "famStrict ON — the shape is a GATE", dict(famStrict=True)),
]
PRIMARY = "S1"
MIN_BARS = 11000
MIN_SYMS = 20


def prio_code(t):
    """The code the gate admits, for this trade's direction."""
    return "HAM" if t.short else "SS"


def off_shape(trades):
    """Trades carrying something OTHER than the priority code.

    THE IMPOSSIBILITY, and it is not a threshold. undertow_anchor.py asked for
    >= 70% because an ANCHOR points at a bar and can point slightly wrong. A
    GATE admits one code by construction, so the honest assertion is zero --
    and a single hanging man or inverted hammer in S1 means `famStrict` is not
    being read at all.
    """
    return [t for t in trades if t.code != prio_code(t)]


def random_gate(trades, frac, seed=SEED):
    """S0's own trades with `frac` of them discarded at random, per symbol.

    THE POINT OF MATCHING PER SYMBOL rather than globally: the gate's discard
    rate varies by symbol, and a global shuffle would quietly re-weight the
    universe toward whichever symbols the coin happened to keep. Inherited from
    undertow_pin.py, whose prereg is retired and whose universe this study uses.
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
    print("UNDERTOW — THE PRIORITY SHAPE AS A GATE")
    print("prereg: indicators/undertow/prereg/PREREG_undertow_strict.md")
    print("population: SYMBOLS_FRESH7, never looked at — released from the")
    print("retired pin study, which computed no number on it")
    print("THE CONTROL IS A RANDOM GATE. The rule discards ~45% of what ships")
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
            keys = {}
            for sym in syms:
                r = U.run(LOADED[tf][sym], p, sym)
                agg.add(r)
                for t in r.real:
                    keys[(sym, t.bar, t.short)] = t
            m, se, n = clustered(agg.real)
            wr = 100.0 * sum(1 for t in agg.real if t.won) / max(1, n)
            pc = 100.0 * (1 - len(off_shape(agg.real)) / max(1, n))
            print(f"  {aid:3} {name:38} {m:+8.3f} {se:6.3f} {n:6} "
                  f"{wr:5.1f}% {pc:5.1f}% {len(agg.real) / days:9.2f}")
            out[aid] = dict(m=m, se=se, n=n, res=agg, wr=wr, keys=keys, pc=pc)

        a, b = out[PRIMARY], out["S0"]

        # S2 — THE COMPLEMENT, and it is a slice rather than a run. S1 is an
        # exact subset of S0 (asserted below), so S0's trades that S1 does not
        # take ARE the non-priority half. Computed here so the impossibility
        # above has already been printed if it failed.
        comp = [t for k, t in b["keys"].items() if k not in a["keys"]]
        cm, cse, cn = clustered(comp)
        print(f"  S2  the COMPLEMENT — S0 minus S1{'':6} {cm:+8.3f} {cse:6.3f} "
              f"{cn:6} "
              f"{100.0 * sum(1 for t in comp if t.won) / max(1, cn):5.1f}% "
              f"{100.0 * (1 - len(off_shape(comp)) / max(1, cn)):5.1f}% "
              f"{len(comp) / days:9.2f}   ·descriptive")

        # THE IMPOSSIBILITIES, checked before anything is read as a result.
        outside = set(a["keys"]) - set(b["keys"])
        offs = off_shape(a["res"].real)
        live = [("the gate reaches the pin", not offs),
                ("S1 is a SUBSET of S0", not outside),
                ("S1 is SMALLER than S0", a["n"] < b["n"]),
                ("nCap is 0 everywhere",
                 all(out[x]["res"].nCap == 0 for x in out))]
        for label, held in live:
            print(f"  IMPOSSIBILITY  {label:26} "
                  + ("holds" if held else "VIOLATED — RUN IS VOID"))
        if offs:
            print(f"      {len(offs)} trades in S1 are NOT the priority "
                  f"code — famStrict is not being read. "
                  f"first: {offs[0].code} short={offs[0].short}")
        if outside:
            print(f"      {len(outside)} trades the gate takes and the "
                  f"baseline does not. It is not selecting.")
        void = void or not all(h for _, h in live)

        frac = 1.0 - (a["n"] / b["n"] if b["n"] else 1.0)
        gm, gse, gn = clustered(random_gate(b["res"].real, max(0.0, frac)))
        print(f"\n  C   random gate, {100 * max(0.0, frac):.1f}% discarded"
              f"{'':14} {gm:+8.3f} {gse:6.3f} {gn:6}      ·THE CONTROL")

        d = a["m"] - b["m"]
        dse = math.sqrt(a["se"] ** 2 + b["se"] ** 2)
        z = d / dse if dse else 0.0
        dg, dgse = a["m"] - gm, math.sqrt(a["se"] ** 2 + gse ** 2)
        dc, dcse = a["m"] - cm, math.sqrt(a["se"] ** 2 + cse ** 2)
        bars = [a["n"] >= 200,
                all(h for _, h in live),
                d >= 0.10 and abs(z) >= 2.0,
                dgse > 0 and dg >= dgse,
                a["m"] > 0]
        print(f"\n  BARS for S1")
        print(f"    1 coverage        {a['n']} trades   "
              f"{'PASS' if bars[0] else 'FAIL — a bound'}")
        print(f"    2 not confounded  all four hold   "
              f"{'PASS' if bars[1] else 'FAIL — VOID'}")
        print(f"    3 beats what ships  S1 - S0 = {d:+.3f} +/- {dse:.3f} "
              f"(z {z:+.2f})   {'PASS' if bars[2] else 'FAIL'}")
        print(f"    4 BEATS THE RANDOM GATE  {a['m']:+.3f} vs {gm:+.3f}, "
              f"diff {dg:+.3f} +/- {dgse:.3f}   "
              f"{'PASS' if bars[3] else 'FAIL'}")
        print(f"    5 positive        {a['m']:+.3f} R   "
              f"{'PASS' if bars[4] else 'FAIL'}")
        print(f"    · DOES THE SHAPE MATTER AT ALL  S1 - S2 = {dc:+.3f} "
              f"+/- {dcse:.3f} — the priority half against the other half of")
        print(f"      the same population. This is the question the taxonomy "
              f"has never been asked directly.")
        print(f"    · what it COSTS   {a['n'] / days:.2f} trades a day against "
              f"{b['n'] / days:.2f} — {100.0 * a['n'] / b['n']:.0f}% of "
              f"what ships")
        rows.append(dict(tf=tf, m=a["m"], s0=b["m"], s2=cm, d=d, z=z, g=gm,
                         n=a["n"], wr=a["wr"], bars=bars, dc=dc, dcse=dcse,
                         keep=100.0 * a["n"] / b["n"], pc=a["pc"]))

    if not rows:
        print("\nNO TIMEFRAME HAD ENOUGH SYMBOLS. Nothing is reported.")
        return 2

    print(f"\n{'=' * 78}\nVERDICT\n{'=' * 78}\n")
    print(f"  {'tf':8} {'S1 gate':>8} {'S0 ships':>9} {'delta':>7} {'z':>6} "
          f"{'rnd gate':>9} {'n':>6} {'win%':>6} {'prio%':>6} {'kept':>5}  "
          f"bars")
    for v in rows:
        print(f"  {v['tf']:8} {v['m']:+8.3f} {v['s0']:+9.3f} {v['d']:+7.3f} "
              f"{v['z']:+6.2f} {v['g']:+9.3f} {v['n']:6} {v['wr']:5.1f}% "
              f"{v['pc']:5.1f}% {v['keep']:4.0f}%  "
              + "".join("P" if x else "." for x in v["bars"]))
    print(f"\n  DOES THE SHAPE MATTER — the priority half against the other")
    print(f"  half of the same trades. Predicted within +/-0.05 of zero.")
    print(f"  {'tf':8} {'S1':>8} {'S2':>8} {'S1 - S2':>9} {'+/-':>6}")
    for v in rows:
        print(f"  {v['tf']:8} {v['m']:+8.3f} {v['s2']:+8.3f} {v['dc']:+9.3f} "
              f"{v['dcse']:6.3f}")

    pos = [v for v in rows if v["m"] > 0]
    print(f"\n  6 NOT ONE TIMEFRAME  {len(pos)} of {len(rows)} positive   "
          f"{'PASS' if len(pos) >= 2 else 'FAIL'}")
    won = sum(1 for v in rows if v["bars"][2] and v["bars"][3] and v["bars"][4])
    gate = sum(1 for v in rows if v["bars"][3])
    print()
    if void:
        print("  RUN IS VOID — a pre-registered impossibility fired.")
        print("  The numbers above are not published and FRESH7 is spent.")
    elif len(pos) >= 2 and won >= 2:
        print("  THE STATED GATE CLEARS ITS BARS. First component in this")
        print("  project to beat its control. famStrict becomes the default")
        print("  in the port, the chart and the watch.")
    elif gate >= 2 and len(pos) >= 2:
        print("  S1 BEATS THE GATE BUT NOT WHAT SHIPS — the weaker outcome")
        print("  the prereg named in advance. famStrict stays an input")
        print("  defaulting to OFF, the way pinAt did. That is not a")
        print("  promotion and the page does not get to call it one.")
    else:
        print("  NULL — and a null is not a ship here, which is the one way")
        print("  this differs from the scale study. There the null meant a")
        print("  preference was free. Here it means the stated gate costs")
        print("  45% of the setups for no measurable gain. It stays")
        print("  selectable, the page says what it costs, and the decision")
        print("  is the chart owner's with the number in front of them.")
        print()
        print("  The S1 - S2 column is what the page owes the reader: the")
        print("  priority half against the other half of the same trades is")
        print("  the most direct test the taxonomy has ever had.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
