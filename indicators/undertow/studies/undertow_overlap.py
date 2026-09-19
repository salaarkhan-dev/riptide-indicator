"""How much of Undertow's trade count is the same idea, counted several times?

    PYTHONPATH=. python3 indicators/undertow/studies/undertow_overlap.py

THE QUESTION CAME OFF A CHART. ETH on 15m, four LONGs inside ten dollars of
each other, boxes and labels piled on top of one another, and the complaint was
"there are so many trades overlapping". The first thing worth knowing is
whether that is a drawing problem or a strategy property, and it is the second.

DESCRIPTIVE. No arms, no selection, no holdout -- it reports a property of the
SHIPPED configuration and chooses nothing, which is why it carries no prereg.
The numbers it prints are quoted in two tooltips on the chart, which is the
reason it lives in the repository instead of a scratch file: a number shown to
a user has to be reproducible.

A CLUSTER is a maximal set of trades on one symbol, in one direction, whose
[fillBar, exitBar] intervals transitively overlap. That is the operational
meaning of "I am in four of these at once".

WHAT IT DOES NOT SAY. It does not say the measurements are wrong. Every study
here clusters its SE by SYMBOL, which is a coarser grouping than this one and
therefore already absorbs it -- a symbol's trades include all of its
time-overlapping groups. What has no clustering at all is the PANEL on the
chart, which reads "26 / 58" as if those were 84 independent draws.
"""
from __future__ import annotations

import pathlib
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

from indicators.undertow.port import undertow as U               # noqa: E402
from indicators.undertow.studies.undertow_sweep import (         # noqa: E402
    FEE, LOADED, TFS, clustered, load)
from research.data import SYMBOLS                                # noqa: E402

# AS PUBLISHED, PINNED — see test_studies_pin_their_settings.py. maxLive is 64
# rather than the chart's 4 for the usual reason: the cap turns setups away and
# would itself suppress the overlap this is trying to size.
SHIPPED = U.P(locTol=0, pinPick=U.PICK_READY, pinAt=U.PIN_PULL, pinLag=0, biasGate=U.BG_TRADEABLE, famStrict=False, armWins=False, stopSrc=U.S_PULL, useBackup=False, pinNewest=False, famPriority=False, failTest=U.T_CLOSE, biasSrc=U.BS_STRUCT, confirmOrder=U.C_EITHER, maxLive=64, feeFrac=FEE, rr=3.5,
              swingSrc=U.SW_RANGE, msLen=6, msShortLen=2,
              endSweep=False, endStale=False)
HOURS = {"Min15": 0.25, "Min30": 0.5, "Min60": 1.0}


def clusters(trades):
    """Transitively overlapping, same direction, one symbol at a time."""
    out = []
    for t in sorted(trades, key=lambda x: x.fillBar):
        for c in out:
            if (c[-1].short == t.short
                    and max(x.exitBar for x in c) >= t.fillBar):
                c.append(t)
                break
        else:
            out.append([t])
    return out


def main():
    print("UNDERTOW OVERLAP — how many of the trades are one idea?")
    print(f"shipped settings, maxLive 64, fees {FEE * 1e4:.0f}bp · "
          f"DESCRIPTIVE, no prereg, nothing is chosen\n")
    print(f"  {'tf':7} {'trades':>7} {'groups':>7} {'per':>6} {'max':>5} "
          f"{'in a group':>11} {'unanimous':>10} {'span h':>7}")
    got = {}
    for tf in TFS:
        LOADED[tf] = load(tf)
        if not LOADED[tf]:
            print(f"  {tf}: no cached candles. Run undertow_sweep.py --fetch.")
            return 2
        allc, real = [], []
        for sym in SYMBOLS:
            cs = LOADED[tf].get(sym)
            if not cs or len(cs) < 1200:
                continue
            r = U.run(cs, SHIPPED, sym)
            real += r.real
            allc += clusters(r.real)
        multi = [c for c in allc if len(c) > 1]
        inmulti = sum(len(c) for c in multi)
        unan = [c for c in multi if len({t.won for t in c}) == 1]
        span = [max(t.exitBar for t in c) - min(t.fillBar for t in c)
                for c in multi]
        n = len(real)
        print(f"  {tf:7} {n:7} {len(allc):7} {n / max(1, len(allc)):6.2f} "
              f"{max(len(c) for c in allc):5} "
              f"{100 * inmulti / max(1, n):10.1f}% "
              f"{100 * len(unan) / max(1, len(multi)):9.1f}% "
              f"{statistics.median(span) * HOURS[tf] if span else 0:7.1f}")
        got[tf] = (real, allc)

    print("\n  'unanimous' = groups of 2+ where EVERY trade won or EVERY one")
    print("  lost. High means the group is ONE bet and the trade count")
    print("  overstates the sample by roughly the 'per' column.\n")

    print("  WHAT IT COSTS THE PANEL'S ERROR BAR — the chart treats every fill")
    print("  as a draw. The studies do not: they cluster by SYMBOL, which is")
    print("  coarser than this and already covers it.\n")
    for tf, (real, allc) in got.items():
        rs = [t.r for t in real]
        naive = statistics.pstdev(rs) / len(rs) ** 0.5
        cm = [statistics.mean([t.r for t in c]) for c in allc]
        byc = statistics.pstdev(cm) / len(cm) ** 0.5
        print(f"  {tf}  mean {statistics.mean(rs):+.3f} R   "
              f"SE per trade {naive:.3f} (n {len(rs)})   "
              f"SE per group {byc:.3f} (n {len(cm)})   "
              f"x{byc / max(naive, 1e-9):.2f}")

    print("\n  AND THE ONE NUMBER THAT IS NOT A CONCLUSION. Keeping only the")
    print("  FIRST trade of each group is a different strategy, and this is")
    print("  what it scores IN SAMPLE on the whole dataset, with no holdout,")
    print("  looked at after the fact. It decides nothing. Adopting it on")
    print("  these numbers is the exact error CCP_FILTER_OVERFIT.md records.\n")
    print(f"  {'tf':7} {'all trades':>26} {'first of each group':>28} "
          f"{'delta':>7}")
    for tf, (real, allc) in got.items():
        first = [min(c, key=lambda t: t.fillBar) for c in allc]
        a, ase, an = clustered(real)
        f, fse, fn = clustered(first)
        print(f"  {tf:7} {a:+13.3f} +/- {ase:.3f} (n {an:5})  "
              f"{f:+9.3f} +/- {fse:.3f} (n {fn:5})  {f - a:+7.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
