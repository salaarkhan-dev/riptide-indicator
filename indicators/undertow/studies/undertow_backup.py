"""Is the OB/FVG backup fill worth taking? Runs exactly what
prereg/PREREG_undertow_backup_fill.md pre-registered.

    PYTHONPATH=. python3 indicators/undertow/studies/undertow_backup.py
    PYTHONPATH=. python3 indicators/undertow/studies/undertow_backup.py Min30

THE DENOMINATOR IS THE WHOLE DESIGN. The backup changes the NUMBER of trades,
so mean R per trade cannot compare two arms -- more trades at a lower mean can
still be more money. The metric is **mean R per ARMED SETUP**: `nArmed` is
identical in every arm by construction, an unfilled setup contributes 0, and
that makes the arms directly subtractable.

AND THE BACKUP IS NOT ONE THING. The zone sits between the market and the Focus
line, so price touches it FIRST, and every backup is one of two opposite
things:

    ADDED        filled only with the backup on -- a trade that would not have
                 happened. Scored against the 0 it would have earned.
    PRE-EMPTED   filled in BOTH arms -- a worse price on a trade that was
                 going to happen anyway. Scored as backup R minus Focus R.

A single net number hides both, so every armed setup is matched across the two
arms by (symbol, arming bar) and the two halves are reported separately.

THE CONTROL IS THE BAR THAT MATTERS. Arm C keeps the trigger, the cap and the
direction and throws the zone detection away, entering at the MIDPOINT between
the trigger bar's extreme and the Focus. If that scores the same, the OB/FVG
machinery is decoration and what is being measured is "enter later into a
running move".

Reads the .cache/ candles undertow_sweep.py fetched. Never run by preflight.
"""
from __future__ import annotations

import dataclasses
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

from indicators.undertow.port import undertow as U               # noqa: E402
from indicators.undertow.studies.undertow_sweep import (         # noqa: E402
    FEE, LOADED, TFS, clustered, load, quadrant)
from research.data import SYMBOLS                                # noqa: E402

# AS PUBLISHED, PINNED. Every setting this study's page was run under is
# named here even where it matched P's default at the time, because a default
# that later moves silently re-points a published study: `swingSrc` went from
# the bar pivot to "price move" after this ran, so without these lines the
# script would print different numbers under the same page's name. A study that
# cannot reproduce its own measurement is not a record of anything.
BASE = U.P(famStrict=False, armWins=False, stopSrc=U.S_PULL, useBackup=False, pinNewest=False, famPriority=False, failTest=U.T_CLOSE, biasSrc=U.BS_STRUCT, confirmOrder=U.C_EITHER, maxLive=64, feeFrac=FEE, rr=3.5,
           swingSrc=U.SW_BAR, msLen=6, msShortLen=2,
           endSweep=False, endStale=False)

ARMS = [
    # B0 IS EMPTY AND BASE NOW PINS `useBackup=False`, which is the whole
    # repair. It used to be empty while BASE said nothing, so when the default
    # went False -> True the BASELINE THIS PAGE IS A DIFFERENCE AGAINST became
    # a second copy of B3. It printed a full table -- B3 - B0 = +0.000 on all
    # three timeframes, 0 trades added, every pre-empted fill worth +0.000 --
    # and a VERDICT saying the backup does nothing. Every one of those numbers
    # was the arm subtracted from itself.
    #
    # BASE carried a docstring explaining exactly this hazard and the ARMS list
    # underneath it walked into it anyway, because the pinning test was
    # satisfied by `useBackup` appearing on the five lines below. It now checks
    # the baseline.
    ("B0", "backup off", {}),
    ("B1", "order blocks only", dict(useBackup=True, useFVG=False)),
    ("B2", "fair value gaps only", dict(useBackup=True, useOB=False)),
    ("B3", "BOTH — the primary", dict(useBackup=True)),
    ("B4", "both, trigger 0.5", dict(useBackup=True, bkTrigger=0.5)),
    ("B5", "both, trigger 2.0", dict(useBackup=True, bkTrigger=2.0)),
    ("C", "CONTROL — midpoint", dict(useBackup=True, bkMode="mid")),
]
DESCRIPTIVE = {"B1", "B2", "B4", "B5"}

ALL = [(s, True) for s in SYMBOLS] + [(s, False) for s in SYMBOLS]
FRESH = [(s, False) for i, s in enumerate(SYMBOLS) if i % 2 == 0] \
      + [(s, True) for i, s in enumerate(SYMBOLS) if i % 2 == 1]


def run_arm(tf, p, pairs):
    """Every armed setup in the panel, keyed so arms can be matched.

    The key is (symbol, arming bar). It is stable across arms because the
    backup lives entirely downstream of arming -- the port's tests assert that
    `nArmed` and the arming bars are untouched by it, which is what makes this
    subtraction legal at all.
    """
    data = LOADED[tf]
    armed: dict = {}
    # THE KEY IS (symbol, quadrant, PIN bar, arming bar) AND EVERY PART OF IT
    # IS LOAD-BEARING. Both weaknesses were found by the same pre-registered
    # impossibility -- the late arm reporting a pre-emption in a design where
    # pre-emption cannot happen -- and the only way to get one is a mis-keyed
    # match:
    #
    #   the QUADRANT, because a panel spans both halves of every symbol and
    #   each half is indexed from 0, so a setup in the newer half matches one
    #   at the same index in the older half;
    #
    #   the PIN BAR, because two candidates can ARM ON THE SAME BAR -- a
    #   pullback holds several pins and their confirmations can land together.
    #   Keyed on the arming bar alone they share a slot, and one filling at the
    #   Focus while the other fills at a backup reads as a single setup that
    #   did both.
    bk: set = set()
    res = U.Result()
    for sym, older in pairs:
        cs = data.get(sym)
        if not cs or len(cs) < 1200:
            continue
        seg, skip = quadrant(cs, older)
        r = U.run(seg, p, sym)
        r.trades = [t for t in r.trades if t.fillBar >= skip]
        r.armed = [a for a in r.armed if a["bar"] >= skip]
        res.add(r)
        for a in r.armed:
            armed[(sym, older, a["pin"], a["bar"])] = 0.0
        for t in r.real:
            k = (sym, older, t.bar, t.armBar)
            if k in armed:
                armed[k] = t.r
            if t.backup:
                bk.add(k)
    return res, armed, bk


def per_armed(armed):
    """Mean R per armed setup, clustered by symbol. An unfilled setup is a 0,
    which is the point: it is the denominator that does not move."""
    ts = [U.Trade(symbol=k[0], r=v) for k, v in armed.items()]
    return clustered(ts)


def decompose(off, on, bk):
    """ADDED against PRE-EMPTED, matched setup by setup.

    `bk` is the set of FULL keys (symbol, quadrant, arming bar) that filled via
    a backup -- see run_arm for why the quadrant has to be in there.
    """
    added, preempt = [], []
    for k, r_on in on.items():
        r_off = off.get(k, 0.0)
        if k not in bk:
            continue                      # not a backup fill; nothing to say
        # Clustered by symbol, like everything else here -- one symbol's
        # backups are not independent of each other.
        (added if r_off == 0.0 else preempt).append(
            U.Trade(symbol=k[0], r=r_on if r_off == 0.0 else r_on - r_off))
    return added, preempt, len(added), len(preempt)


def panel(tf, pairs, title):
    print(f"\n{'-' * 78}\n{tf} · {title}\n{'-' * 78}")
    out = {}
    base_armed = None
    for aid, name, over in ARMS:
        p = dataclasses.replace(BASE, **over)
        res, armed, bk = run_arm(tf, p, pairs)
        m, se, n = per_armed(armed)
        if aid == "B0":
            base_armed = armed
            print(f"  {'':3} {'arm':22} {'R/armed':>9} {'+/-':>6} "
                  f"{'armed':>6} {'fills':>6} {'bk':>5}   vs B0")
        d = ""
        if base_armed is not None and aid != "B0":
            dm = m - out["B0"]["m"]
            dse = math.sqrt(se ** 2 + out["B0"]["se"] ** 2)
            z = dm / dse if dse else 0.0
            d = f"{dm:+.3f} +/- {dse:.3f} (z {z:+.2f})"
        flag = " ·descriptive" if aid in DESCRIPTIVE else ""
        print(f"  {aid:3} {name:22} {m:+9.3f} {se:6.3f} {n:6} "
              f"{len(res.real):6} {res.nBackup:5}   {d}{flag}")
        out[aid] = dict(m=m, se=se, n=n, res=res, armed=armed, bk=bk,
                        cap=res.nCap, fills=len(res.real))
    return out


def verdict(tf, o):
    b0, b3, c = o["B0"], o["B3"], o["C"]
    d = b3["m"] - b0["m"]
    dse = math.sqrt(b3["se"] ** 2 + b0["se"] ** 2)
    z = d / dse if dse else 0.0
    dc = b3["m"] - c["m"]
    dcse = math.sqrt(b3["se"] ** 2 + c["se"] ** 2)

    cover = b0["n"] >= 300
    clean = b0["n"] == b3["n"] and b0["cap"] == 0 and b3["cap"] == 0
    improves = d >= 0.05 and abs(z) >= 2.0
    beats_ctl = dcse > 0 and dc >= dcse

    print(f"\n  PRIMARY  B3 - B0 = {d:+.3f} R per armed setup "
          f"+/- {dse:.3f}  (z {z:+.2f})")
    print(f"    1 coverage        {b0['n']} armed setups   "
          f"{'PASS' if cover else 'FAIL — a bound, not a verdict'}")
    print(f"    2 not confounded  armed {b0['n']}=={b3['n']}, cap "
          f"{b0['cap']}/{b3['cap']}   "
          f"{'PASS' if clean else 'FAIL — the contrast is void'}")
    print(f"    3 improves        >= +0.05 at |z| >= 2   "
          f"{'PASS' if improves else 'FAIL'}")
    print(f"    4 beats control   B3 - C = {dc:+.3f} +/- {dcse:.3f}   "
          f"{'PASS' if beats_ctl else 'FAIL'}"
          + ("" if beats_ctl else
             "  → the zones are not doing the work"))

    added, preempt, na, npre = decompose(b0["armed"], b3["armed"], b3["bk"])
    am, ase, _ = clustered(added)
    pm, pse, _ = clustered(preempt)
    sa = sum(t.r for t in added)
    sp = sum(t.r for t in preempt)
    print(f"\n  DECOMPOSITION of {b3['res'].nBackup} backup fills")
    print(f"    ADDED       {na:4} trades that would not have happened   "
          f"{am:+.3f} +/- {ase:.3f} R each  (z {am / ase if ase else 0:+.1f})"
          f"   {sa:+.1f} R")
    print(f"    PRE-EMPTED  {npre:4} that took a worse price anyway       "
          f"{pm:+.3f} +/- {pse:.3f} R each  (z {pm / pse if pse else 0:+.1f})"
          f"   {sp:+.1f} R")
    net = sa + sp
    print(f"    NET         {net:+.1f} R over {b0['n']} armed setups = "
          f"{net / max(1, b0['n']):+.3f} R each")

    # bar 6: drop the biggest contributor
    per: dict = {}
    for k, v in b3["armed"].items():
        per[k[0]] = per.get(k[0], 0.0) + (v - b0["armed"].get(k, 0.0))
    worst = max(per, key=per.get, default=None)
    rest = {k: v for k, v in b3["armed"].items() if k[0] != worst}
    rest0 = {k: v for k, v in b0["armed"].items() if k[0] != worst}
    d6 = (sum(rest.values()) - sum(rest0.values())) / max(1, len(rest))
    print(f"    6 not one symbol  without {worst}: {d6:+.3f} R   "
          f"{'PASS' if d6 > 0 else 'FAIL'}")
    return dict(tf=tf, d=d, dse=dse, z=z, dc=dc, n=b0["n"],
                bars=[cover, clean, improves, beats_ctl, d6 > 0],
                added=(na, am), pre=(npre, pm))


def main():
    argv = [a for a in sys.argv[1:] if a in TFS]
    tfs = argv or list(TFS)
    for tf in tfs:
        LOADED[tf] = load(tf)
        if not LOADED[tf]:
            print(f"{tf}: no cached candles. Run undertow_sweep.py --fetch.")
            return 2

    print("UNDERTOW BACKUP FILL — is it worth taking?")
    print("prereg: indicators/undertow/prereg/PREREG_undertow_backup_fill.md")
    print(f"config: {BASE.tag()} maxLive {BASE.maxLive}, fees "
          f"{FEE * 1e4:.0f}bp")
    print("metric: mean R per ARMED SETUP — the one denominator the backup")
    print("        cannot move. An unfilled setup is a 0.")

    vs = []
    for tf in tfs:
        o = panel(tf, ALL, "PRIMARY — all 23 symbols, both halves")
        vs.append(verdict(tf, o))
        panel(tf, FRESH, "SECOND PANEL — the two quadrants the sweep never "
                         "scored")

    print(f"\n{'=' * 78}\nVERDICT\n{'=' * 78}\n")
    print(f"  {'tf':8} {'B3-B0':>8} {'+/-':>6} {'z':>6} {'B3-C':>7} "
          f"{'armed':>6}  added        pre-empted")
    for v in vs:
        print(f"  {v['tf']:8} {v['d']:+8.3f} {v['dse']:6.3f} {v['z']:+6.2f} "
              f"{v['dc']:+7.3f} {v['n']:6}  "
              f"{v['added'][0]:4} @ {v['added'][1]:+.2f}  "
              f"{v['pre'][0]:4} @ {v['pre'][1]:+.2f}")
    pos = [v for v in vs if v["d"] > 0]
    b5 = len(pos) >= 2
    print(f"\n  5 NOT ONE TIMEFRAME  {len(pos)} of {len(vs)} positive   "
          f"{'PASS' if b5 else 'FAIL'}")
    win = [v for v in vs if all(v["bars"])]
    zones = [v for v in vs if v["bars"][3]]
    improves = [v for v in vs if v["bars"][2]]
    print()
    if b5 and len(win) >= 2:
        print("  THE BACKUP FILL CLEARS ITS BARS on "
              f"{', '.join(v['tf'] for v in win)}.")
        print("  First component of Undertow ever to do so. It earns default-on")
        print("  in the Pine, a second alert in the watch, and a forward run —")
        print("  not a conclusion.")
    elif b5 and len(improves) >= 2 and not zones:
        print("  THE BACKUP HELPS AND THE ZONES DO NOT.")
        print("  It cleared bar 3 but not the midpoint control, so what is")
        print("  working is 'enter later into a running move' — the OB and FVG")
        print("  detection is decoration on top of it. A different claim.")
    elif b5 and not improves:
        print("  POSITIVE ON EVERY TIMEFRAME, AND NOT ESTABLISHED.")
        print("  Bar 3 failed everywhere: the net is real in sign and too")
        print("  small to call, because the two halves of it very nearly")
        print("  cancel. Read the decomposition, not the net — that is what")
        print("  it is there for, and it is where the next question is.")
    else:
        print("  THE BACKUP FILL DOES NOT CLEAR ITS BARS.")
        print("  Every component of Undertow has now been ablated — bias gate,")
        print("  candle, location, exit, fill — and none carries an effect. The")
        print("  remaining explanation is the one no backtest can reach, the")
        print("  watch already exists to test it prospectively, and the right")
        print("  move is to stop measuring history and start recording.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
