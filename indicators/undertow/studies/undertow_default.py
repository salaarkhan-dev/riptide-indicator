"""The shipped configuration, all of it, against the one it replaced.

    PYTHONPATH=. python3 indicators/undertow/studies/undertow_default.py

Runs exactly what prereg/PREREG_undertow_default.md pre-registered.

TWELVE STUDIES HAVE MEASURED COMPONENTS AND NONE HAS MEASURED THE CHART. Every
page in ../measurements takes one anchor, one gate, one scale, one bias source.
In a single day the shipped defaults changed in four independent ways, and a
chart nobody has measured is not made trustworthy by twelve pages about its
parts.

THE CONTROL IS THE SEEDED RANDOM ENTRY AND THE MEASUREMENT INVERTED THE OBVIOUS
CHOICE. 81% of the new default's trades are also the old one's, which on the
reasoning of undertow_pin.py and undertow_strict.py argues for a matched random
GATE. It is descriptive here instead: a gate draws only from the old population
and can never produce the 19% the new default takes and the old one does not,
so if those trades are good the gate flatters the arm by construction. The
random entry is matched to the arm rather than drawn from the baseline and has
no such bias. Both are reported and the page names the gate's.

THE LEAVE-ONE-OUT LADDER IS NOT A SEARCH. Four things changed at once and a
bare null would say nothing about which to reconsider -- and there is no
universe left to ask again. Each L arm answers one question fixed in advance
and none may be promoted.
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
# THE SHARED RANDOM-ENTRY CONTROL, not a third copy of one. It carries two
# fixes this project has already paid for -- the entry is drawn over the WHOLE
# series rather than near the real one, and an unresolved entry is marked to
# market rather than dropped. See UNDERTOW_PULLBACK.md.
from indicators.undertow.studies.undertow_v2 import (            # noqa: E402
    control_full)
from research.symbols_fresh import (SYMBOLS_FRESH12,             # noqa: E402
                                    assert_disjoint)
from riptide.config import BAR_SECONDS                           # noqa: E402

# WHAT THE CHART SHIPS TODAY. Written out in full rather than read from P's
# defaults, because this page has to keep meaning the same thing after the next
# default moves -- which is the whole subject of
# test_studies_pin_their_settings.py.
NEW = dict(biasSrc=U.BS_STRUCT, msLen=50, msShortLen=3, swingSrc=U.SW_BAR,
           msBosNeedsIdm=True, smcInternalLen=5,
           famStrict=True, armWins=True, stopSrc=U.S_SWING,
           pinNewest=True, famPriority=True, failTest=U.T_TOUCH,
           confirmOrder=U.C_WF, pinAt=U.PIN_PULL, locTol=0,
           endMinor=U.E_FLIP, endSweep=False, endStale=False, retraceMax=70,
           maxLive=64, feeFrac=FEE, rr=3.5)
# AND WHAT IT SHIPPED YESTERDAY. The four changes, reverted together.
OLD = dict(NEW, biasSrc=U.BS_SMC, smcSwingLen=14, msLen=6, msShortLen=2,
           swingSrc=U.SW_RANGE, famStrict=False, armWins=False,
           stopSrc=U.S_PULL)

BASE = U.P(biasGate=U.BG_TRADEABLE, useBackup=False, **NEW)
ARMS = [
    ("D0", "what the chart shipped YESTERDAY", OLD),
    ("D1", "what the chart ships TODAY", {}),
    ("L1", "  … minus the shape gate", dict(famStrict=False)),
    ("L2", "  … minus first-to-confirm-wins", dict(armWins=False)),
    ("L3", "  … minus the minor-swing stop", dict(stopSrc=U.S_PULL)),
    ("L4", "  … minus the inducement engine", dict(biasSrc=U.BS_SMC,
                                                   smcSwingLen=14)),
]
PRIMARY = "D1"
DESCRIPTIVE = {"L1", "L2", "L3", "L4"}
MIN_BARS = 11000
MIN_SYMS = 20


def prio_code(t):
    return "HAM" if t.short else "SS"


def off_shape(trades):
    """Trades carrying anything but the priority code. The shape gate admits
    one code per direction by construction, so the honest assertion is zero."""
    return [t for t in trades if t.code != prio_code(t)]


def random_gate(trades, frac, seed=SEED):
    """D0's own trades with `frac` discarded at random, per symbol.

    DESCRIPTIVE HERE, not the control, and the prereg says why: it can only
    draw from D0, so the 19% of D1 that D0 never takes is out of its reach and
    the comparison tilts toward D1 by construction.
    """
    rnd = random.Random(seed)
    bysym: dict = {}
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
    print("UNDERTOW — THE SHIPPED CONFIGURATION, ALL OF IT")
    print("prereg: indicators/undertow/prereg/PREREG_undertow_default.md")
    print("population: SYMBOLS_FRESH12, never looked at, and THE LAST SET OF")
    print("THIS SIZE — 29 contracts remain and they cannot field Min60.")
    print("THE CONTROL IS A SEEDED RANDOM ENTRY. 81% of D1 is inside D0, which")
    print("argues for a gate; a gate cannot reach the other 19% and would")
    print("flatter D1. The gate is reported as G, with its bias named.")

    rows, void = [], False
    for tf in tfs:
        LOADED[tf] = load(tf, SYMBOLS_FRESH12)
        syms = [s for s in SYMBOLS_FRESH12
                if len(LOADED[tf].get(s) or []) >= MIN_BARS]
        if len(syms) < MIN_SYMS:
            print(f"\n{tf}: only {len(syms)} FRESH12 symbols carry "
                  f"{MIN_BARS} bars — the prereg says NOT REPORTED.")
            continue
        days = sum(len(LOADED[tf][s]) for s in syms) * BAR_SECONDS[tf] / 86400

        print(f"\n{'-' * 78}\n{tf} · {len(syms)} symbols, scored once"
              f"\n{'-' * 78}")
        print(f"  {'':3} {'configuration':36} {'R/trade':>8} {'+/-':>6} "
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
                    keys[(sym, t.bar, t.short)] = t.stop
            m, se, n = clustered(agg.real)
            wr = 100.0 * sum(1 for t in agg.real if t.won) / max(1, n)
            pc = 100.0 * (1 - len(off_shape(agg.real)) / max(1, n))
            print(f"  {aid:3} {name:36} {m:+8.3f} {se:6.3f} {n:6} "
                  f"{wr:5.1f}% {pc:5.1f}% {len(agg.real) / days:9.2f}"
                  + ("   ·descriptive" if aid in DESCRIPTIVE else ""))
            out[aid] = dict(m=m, se=se, n=n, res=agg, wr=wr, keys=keys)

        a, b = out[PRIMARY], out["D0"]
        # The inducement, run only to prove the rule is live.
        idm_off = U.Result()
        for sym in syms:
            idm_off.add(U.run(LOADED[tf][sym],
                              dataclasses.replace(BASE, msBosNeedsIdm=False),
                              sym))

        offs = off_shape(a["res"].real)
        live = [("the configuration is read", a["n"] != b["n"]),
                ("the shape gate is live", not offs),
                ("the inducement is live",
                 len(idm_off.real) != len(a["res"].real)),
                # THE REGISTERED CONDITION IS "D1 != L3" AND THIS IS WHAT
                # THAT MEANS. The first version of this line tested TRADE
                # COUNT, which is a proxy and a bad one: a stop source moves
                # the stop LEVEL, and only changes how many setups arm in the
                # corner cases where there is no swing to hang one on or the
                # stop lands the wrong side of the entry. On Min30 both arms
                # came to 588 trades and scored -0.037 against -0.105 -- the
                # setting plainly read, the proxy plainly fired, and the run
                # declared VOID on a check that was not asking the registered
                # question. Third proxy-check incident in this project, and
                # the prereg for this very study contains a line warning
                # against it.
                #
                # The stops themselves, on the trades the two arms share, is
                # the unambiguous reading and cannot fire for the wrong reason.
                ("the stop is the minor swing",
                 any(out["L3"]["keys"].get(k) != v
                     for k, v in a["keys"].items()
                     if k in out["L3"]["keys"])),
                ("nCap is 0 everywhere",
                 all(out[x]["res"].nCap == 0 for x in out))]
        for label, held in live:
            print(f"  IMPOSSIBILITY  {label:28} "
                  + ("holds" if held else "VIOLATED — RUN IS VOID"))
        if offs:
            print(f"      {len(offs)} D1 trades are NOT the priority code; "
                  f"first {offs[0].code} short={offs[0].short}")
        void = void or not all(h for _, h in live)

        # THE CONTROL, and it is matched to the arm rather than drawn from D0.
        cm, cse, cn = clustered(control_full(a["res"].real, tf))
        print(f"\n  C   seeded random entry, matched to D1{'':10} "
              f"{cm:+8.3f} {cse:6.3f} {cn:6}      ·THE CONTROL")
        frac = 1.0 - (a["n"] / b["n"] if b["n"] else 1.0)
        gm, gse, gn = clustered(random_gate(b["res"].real, max(0.0, frac)))
        print(f"  G   random gate on D0, {100 * max(0.0, frac):.0f}% discarded"
              f"{'':7} {gm:+8.3f} {gse:6.3f} {gn:6}      ·descriptive, "
              f"tilted toward D1")

        d = a["m"] - b["m"]
        dse = math.sqrt(a["se"] ** 2 + b["se"] ** 2)
        z = d / dse if dse else 0.0
        dc, dcse = a["m"] - cm, math.sqrt(a["se"] ** 2 + cse ** 2)
        bars = [a["n"] >= 200,
                all(h for _, h in live),
                d >= 0.10 and abs(z) >= 2.0,
                dcse > 0 and dc >= dcse,
                a["m"] > 0]
        print(f"\n  BARS for D1")
        print(f"    1 coverage        {a['n']} trades   "
              f"{'PASS' if bars[0] else 'FAIL — a bound'}")
        print(f"    2 not confounded  all five hold   "
              f"{'PASS' if bars[1] else 'FAIL — VOID'}")
        print(f"    3 beats what it replaced  D1 - D0 = {d:+.3f} +/- {dse:.3f} "
              f"(z {z:+.2f})   {'PASS' if bars[2] else 'FAIL'}")
        print(f"    4 beats its control  {a['m']:+.3f} vs {cm:+.3f}, "
              f"diff {dc:+.3f} +/- {dcse:.3f}   "
              f"{'PASS' if bars[3] else 'FAIL'}")
        print(f"    5 positive        {a['m']:+.3f} R   "
              f"{'PASS' if bars[4] else 'FAIL'}")
        print(f"\n    WHAT EACH CHANGE CONTRIBUTES — D1 minus the arm without"
              f" it.\n    Positive means the change HELPS the package.")
        for lid, lname in (("L1", "the shape gate"),
                           ("L2", "first-to-confirm-wins"),
                           ("L3", "the minor-swing stop"),
                           ("L4", "the inducement engine")):
            lm = out[lid]["m"]
            lse = math.sqrt(a["se"] ** 2 + out[lid]["se"] ** 2)
            print(f"      {lname:24} {a['m'] - lm:+7.3f} +/- {lse:.3f}   "
                  f"({lid} {lm:+.3f}, n {out[lid]['n']})")
        rows.append(dict(tf=tf, m=a["m"], d0=b["m"], d=d, z=z, c=cm, g=gm,
                         n=a["n"], wr=a["wr"], bars=bars,
                         L={k: out[k]["m"] for k in DESCRIPTIVE}))

    if not rows:
        print("\nNO TIMEFRAME HAD ENOUGH SYMBOLS. Nothing is reported.")
        return 2

    print(f"\n{'=' * 78}\nVERDICT\n{'=' * 78}\n")
    print(f"  {'tf':8} {'D1 today':>9} {'D0 was':>8} {'delta':>7} {'z':>6} "
          f"{'rnd entry':>10} {'rnd gate':>9} {'n':>6} {'win%':>6}  bars")
    for v in rows:
        print(f"  {v['tf']:8} {v['m']:+9.3f} {v['d0']:+8.3f} {v['d']:+7.3f} "
              f"{v['z']:+6.2f} {v['c']:+10.3f} {v['g']:+9.3f} {v['n']:6} "
              f"{v['wr']:5.1f}%  "
              + "".join("P" if x else "." for x in v["bars"]))
    print(f"\n  WHAT EACH CHANGE CONTRIBUTES, D1 minus the arm without it.")
    print(f"  {'tf':8} {'gate':>8} {'armWins':>8} {'swing stop':>11} "
          f"{'engine':>8}")
    for v in rows:
        print(f"  {v['tf']:8} {v['m'] - v['L']['L1']:+8.3f} "
              f"{v['m'] - v['L']['L2']:+8.3f} {v['m'] - v['L']['L3']:+11.3f} "
              f"{v['m'] - v['L']['L4']:+8.3f}")

    pos = [v for v in rows if v["m"] > 0]
    print(f"\n  6 NOT ONE TIMEFRAME  {len(pos)} of {len(rows)} positive   "
          f"{'PASS' if len(pos) >= 2 else 'FAIL'}")
    won = sum(1 for v in rows if all(v["bars"][2:5]))
    bad = sum(1 for v in rows if v["d"] <= -0.10 and abs(v["z"]) >= 2.0)
    print()
    if void:
        print("  RUN IS VOID — a pre-registered impossibility fired, and")
        print("  there is no universe left to re-run it on.")
    elif len(pos) >= 2 and won >= 2:
        print("  THE SHIPPED CONFIGURATION CLEARS ITS BARS. The first one in")
        print("  this project to do so, on a universe frozen for it. It stays")
        print("  the default and this page is why.")
    elif bad >= 2:
        print("  IT IS WORSE THAN WHAT IT REPLACED, and the page says so in")
        print("  its title. The ladder above names which change carries the")
        print("  damage; reverting that one is the recommendation.")
    else:
        print("  NULL. The defaults were set from a chart owner's preference")
        print("  against a spent-universe table, and nothing measured supports")
        print("  them. They stay, because they are the owner's to set, and the")
        print("  page says in its title that they are unsupported.")
        print("  The ladder says which one to reconsider first.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
