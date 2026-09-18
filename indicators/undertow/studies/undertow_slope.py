"""Should Slope be the default bias? Runs exactly what
prereg/PREREG_undertow_slope_default.md pre-registered.

    PYTHONPATH=. python3 indicators/undertow/studies/undertow_slope.py

THE REQUEST WAS "measure slope as the default and compare". Slope came closest
in UNDERTOW_BIAS_SOURCE.md -- +0.198 R per trade on the Min30 holdout, the
largest number in that study, failing only the z bar.

THE OBJECTION IS IN THE PREREG AND IT IS THE REASON FOR THE THIRD ARM. Slope as
shipped measures its window in BARS and its threshold in ATR per BAR, so it
flips 1.2 times a day on 15m and 0.5 on 30m -- a 2.4x ratio, worse than the bar
pivot's 2.1x, and that ratio is the whole reason `price move` is the default.
So Slope also runs with `slopeUnit="hours"`: the same rule, window in hours and
threshold in day-ranges per hour, nothing per-bar left.

THE ONE FREE NUMBER IS CALIBRATED, NOT CHOSEN. `slopeMinPerHr` is in a
different unit from `slopeMin`, so a fixed ladder is walked on the CALIBRATION
quadrant and the rung whose FLIP RATE matches Slope-in-bars is taken. Flip rate
is descriptive -- it does not read a trade -- and it is what makes the two
Slope arms the same rule in two units instead of two rules.

QUADRANTS. The bias study spent even/older and odd/newer, and Slope's +0.198
was read on odd/newer, so that one cannot test Slope again. Calibration is
even/newer; the holdout is odd/older. It shares SYMBOLS with the old holdout
and not the time period. That is weaker and the measurement page says so.
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

# AS PUBLISHED, PINNED — see test_studies_pin_their_settings.py. `rr` is the
# one that would bite here: every R on the page is quoted at 3.5, and A1 and A2
# read no swing setting at all (Slope is not the structure engine), so the swing
# pins matter only to A0, which names its own.
BASE = U.P(famStrict=False, armWins=False, stopSrc=U.S_PULL, useBackup=False, pinNewest=False, famPriority=False, failTest=U.T_CLOSE, biasSrc=U.BS_STRUCT, confirmOrder=U.C_EITHER, maxLive=64, feeFrac=FEE, rr=3.5,
           swingSrc=U.SW_RANGE, msLen=6, msShortLen=2,
           endSweep=False, endStale=False)
# Retrace-only Ending: the only rule that exists for a slope.
MATCH = dict(endMinor=U.E_OFF, endSweep=False, endStale=False)

A0 = {**MATCH, "biasSrc": U.BS_STRUCT, "swingSrc": U.SW_RANGE,
      "swingK": 0.40, "swingKMinor": 0.12}
A1 = {**MATCH, "biasSrc": U.BS_SLOPE, "slopeUnit": U.SL_BARS,
      "slopeLen": 50, "slopeMin": 0.05}
# slopeMinPerHr is filled in by calibrate(), never by hand.
A2 = {**MATCH, "biasSrc": U.BS_SLOPE, "slopeUnit": U.SL_HOURS,
      "slopeHours": 12.5}

# Fixed in the prereg. No rung outside this list is ever scored.
LADDER = (0.002, 0.005, 0.01, 0.02, 0.03, 0.05, 0.08)
CONSISTENCY_MAX = 1.35          # bar 7


def flips_per_day(tf, p, syms, older):
    """Direction changes per day. Descriptive -- reads no trade."""
    data = LOADED[tf]
    flips, bars, holds, run = 0, 0, [], 1
    for sym in syms:
        cs = data.get(sym)
        if not cs or len(cs) < 1200:
            continue
        seg, skip = quadrant(cs, older)
        st, _ = U.structure(seg, p)
        bars += len(seg) - skip
        run = 1
        for i in range(skip + 1, len(seg)):
            if st["os"][i] != st["os"][i - 1]:
                flips += 1
                holds.append(run)
                run = 1
            else:
                run += 1
    step = BAR_SECONDS[tf]
    return (flips / max(1e-9, bars * step / 86400.0),
            statistics.median(holds) * step / 3600 if holds else 0.0)


def calibrate(syms):
    """The ladder rule, verbatim from the prereg. Min15, calibration quadrant,
    flip rate only. Returns the rung and prints the whole ladder so the choice
    is auditable rather than asserted."""
    tf = "Min15"
    target, _ = flips_per_day(tf, dataclasses.replace(BASE, **A1), syms, False)
    print(f"\n{'=' * 78}\nCALIBRATION — even symbols, newer half, {tf}, "
          f"FLIP RATE ONLY\n{'=' * 78}")
    print(f"  A1 Slope(bars 50/0.05) flips/day = {target:.3f}   <- the target")
    print(f"\n  {'rung':>8} {'flips/day':>10} {'hold h':>8} "
          f"{'|log ratio|':>12}")
    best, bestd = None, float("inf")
    for rung in LADDER:
        p = dataclasses.replace(BASE, **A2, slopeMinPerHr=rung)
        f, h = flips_per_day(tf, p, syms, False)
        d = abs(math.log(max(f, 1e-9) / max(target, 1e-9)))
        print(f"  {rung:8.3f} {f:10.3f} {h:8.1f} {d:12.3f}"
              + ("   <-" if d < bestd else ""))
        if d < bestd:                       # strict, so ties take the smaller
            best, bestd = rung, d
    print(f"\n  CHOSEN slopeMinPerHr = {best}   (log ratio {bestd:.3f})")
    print("  FROZEN. No other rung is scored anywhere below.")
    return best


def run_arm(tf, p, syms, older):
    data = LOADED[tf]
    agg = U.Result()
    ctl, bars = [], 0
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
    f, h = flips_per_day(tf, p, syms, older)
    return dict(res=agg, ctl=ctl, bars=bars, flips=f, hold=h)


def panel(tf, arms, syms, older, title):
    print(f"\n{'-' * 78}\n{tf} · {title}\n{'-' * 78}")
    print(f"  {'':3} {'bias':30} {'R/trade':>8} {'+/-':>6} {'n':>6} "
          f"{'R/1k':>7} {'flips/d':>8} {'hold h':>7} {'ctl':>7}")
    out = {}
    for aid, name, over in arms:
        p = dataclasses.replace(BASE, **over)
        g = run_arm(tf, p, syms, older)
        m, se, n = clustered(g["res"].real)
        cm = clustered(g["ctl"])[0] if g["ctl"] else float("nan")
        thru = 1000.0 * g["res"].netR / max(1, g["bars"])
        print(f"  {aid:3} {name:30} {m:+8.3f} {se:6.3f} {n:6} "
              f"{thru:+7.3f} {g['flips']:8.2f} {g['hold']:7.1f} {cm:+7.3f}"
              + ("   CAP!" if g["res"].nCap else ""))
        out[aid] = dict(m=m, se=se, n=n, thru=thru, ctl=cm, res=g["res"],
                        ctls=g["ctl"], flips=g["flips"], hold=g["hold"])
    return out


def verdict(aid, a, base, ratio):
    """The seven bars, in the prereg's order. Returns the pass list."""
    d = a["m"] - base["m"]
    dse = math.sqrt(a["se"] ** 2 + base["se"] ** 2)
    z = d / dse if dse else 0.0
    cse = clustered(a["ctls"])[1] if a["ctls"] else float("inf")
    dc = a["m"] - a["ctl"]
    dcse = math.sqrt(a["se"] ** 2 + cse ** 2) if cse != float("inf") else 0.0
    bars = [a["n"] >= 200,
            a["res"].nCap == 0,
            d >= 0.10 and abs(z) >= 2.0,
            dcse > 0 and dc >= dcse,
            a["m"] > 0,
            None,                       # bar 6 is cross-timeframe
            ratio is not None and ratio <= CONSISTENCY_MAX]
    print(f"\n  BARS for {aid}")
    print(f"    1 coverage        {a['n']} trades   "
          f"{'PASS' if bars[0] else 'FAIL — a bound'}")
    print(f"    2 not confounded  nCap {a['res'].nCap}   "
          f"{'PASS' if bars[1] else 'FAIL — VOID'}")
    print(f"    3 beats baseline  {aid} - A0 = {d:+.3f} +/- {dse:.3f} "
          f"(z {z:+.2f})   {'PASS' if bars[2] else 'FAIL'}")
    print(f"    4 beats control   {a['m']:+.3f} vs {a['ctl']:+.3f}, "
          f"diff {dc:+.3f} +/- {dcse:.3f}   {'PASS' if bars[3] else 'FAIL'}")
    print(f"    5 positive        {a['m']:+.3f} R   "
          f"{'PASS' if bars[4] else 'FAIL'}")
    return bars, d, z


def main():
    argv = [a for a in sys.argv[1:] if a in TFS]
    tfs = argv or list(TFS)
    # THE CALIBRATION IS ALWAYS ON Min15, whatever is being scored, because the
    # prereg fixed it there. So Min15 is loaded even when it is not scored --
    # otherwise `undertow_slope.py Min60` dies in calibrate() on a KeyError.
    for tf in sorted(set(tfs) | {"Min15"}):
        LOADED[tf] = load(tf)
        if not LOADED[tf]:
            print(f"{tf}: no cached candles. Run undertow_sweep.py --fetch.")
            return 2
    evens = [s for i, s in enumerate(SYMBOLS) if i % 2 == 0]
    odds = [s for i, s in enumerate(SYMBOLS) if i % 2 == 1]

    print("UNDERTOW SLOPE AS THE DEFAULT — does +0.198 replicate, and does")
    print("Slope survive the consistency bar that chose the current default?")
    print("prereg: indicators/undertow/prereg/PREREG_undertow_slope_default.md")
    print(f"fees {FEE * 1e4:.0f}bp · retrace-only Ending on every arm · "
          f"maxLive 64 · rr {BASE.rr}")

    rung = calibrate(evens)
    arms = [("A0", "structure, price move — BASELINE", A0),
            ("A1", "Slope, bars 50 / 0.05", A1),
            ("A2", f"Slope, hours 12.5 / {rung}",
             {**A2, "slopeMinPerHr": rung})]

    # Bar 7 is a property of the DIRECTION SERIES, not of the holdout's
    # trades, so it is read across 15m and 30m on the holdout quadrant.
    print(f"\n{'=' * 78}\nBAR 7 — CONSISTENCY across timeframes "
          f"(holdout quadrant)\n{'=' * 78}")
    print(f"  {'':3} {'bias':30} {'15m f/d':>9} {'30m f/d':>9} {'ratio':>7}")
    ratios = {}
    if "Min15" in tfs and "Min30" in tfs:
        for aid, name, over in arms:
            p = dataclasses.replace(BASE, **over)
            f15 = flips_per_day("Min15", p, odds, True)[0]
            f30 = flips_per_day("Min30", p, odds, True)[0]
            r = max(f15, f30) / max(1e-9, min(f15, f30))
            ratios[aid] = r
            print(f"  {aid:3} {name:30} {f15:9.2f} {f30:9.2f} {r:7.2f}"
                  f"   {'PASS' if r <= CONSISTENCY_MAX else 'FAIL'}")
    else:
        print("  needs both Min15 and Min30; skipped.")

    rows = []
    for tf in tfs:
        ho = panel(tf, arms, odds, True,
                   "HOLDOUT — odd symbols, OLDER half — scored once")
        for aid in ("A1", "A2"):
            bars, d, z = verdict(aid, ho[aid], ho["A0"], ratios.get(aid))
            rows.append(dict(tf=tf, aid=aid, m=ho[aid]["m"], a0=ho["A0"]["m"],
                             d=d, z=z, ctl=ho[aid]["ctl"], n=ho[aid]["n"],
                             bars=bars))

    print(f"\n{'=' * 78}\nVERDICT\n{'=' * 78}\n")
    print(f"  {'tf':8} {'arm':4} {'holdout':>8} {'A0':>8} {'delta':>7} "
          f"{'z':>6} {'control':>8} {'n':>6}  bars 1-5,7")
    for v in rows:
        flag = "".join("P" if x else "." for x in v["bars"] if x is not None)
        print(f"  {v['tf']:8} {v['aid']:4} {v['m']:+8.3f} {v['a0']:+8.3f} "
              f"{v['d']:+7.3f} {v['z']:+6.2f} {v['ctl']:+8.3f} {v['n']:6}  "
              f"{flag}")

    print()
    promoted = []
    for aid in ("A1", "A2"):
        mine = [v for v in rows if v["aid"] == aid]
        pos = [v for v in mine if v["m"] > 0]
        six = len(pos) >= 2
        print(f"  6 NOT ONE TIMEFRAME  {aid}: {len(pos)} of {len(mine)} "
              f"positive   {'PASS' if six else 'FAIL'}")
        r = ratios.get(aid)
        seven = r is not None and r <= CONSISTENCY_MAX
        print(f"  7 CONSISTENT         {aid}: ratio "
              + (f"{r:.2f}" if r is not None else "n/a")
              + f"   {'PASS' if seven else 'FAIL'}")
        # The promotion rule: bars 3, 4, 5, 6 and 7, and 3-5 on >= 2 tfs.
        ok345 = sum(1 for v in mine if v["bars"][2] and v["bars"][3]
                    and v["bars"][4])
        if ok345 >= 2 and six and seven:
            promoted.append(aid)

    print()
    if promoted:
        print("  " + ", ".join(promoted) + " CLEARS THE PROMOTION RULE.")
        print("  First thing in Undertow to beat its own control on a holdout.")
        print("  It earns the default and a forward run — not a conclusion.")
    else:
        print("  NO SLOPE ARM CLEARS THE PROMOTION RULE.")
        print("  The answer to 'measure slope as the default' is no. Whatever")
        print("  bar 7 says, an arm that does not clear 3-6 is a dropdown and")
        print("  not a default, and the prereg fixed that before the run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
