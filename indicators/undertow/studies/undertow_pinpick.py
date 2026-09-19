"""Pick the pullback's candle by PRICE, not by position.

    PYTHONPATH=. python3 indicators/undertow/studies/undertow_pinpick.py

DESCRIPTIVE. No prereg, no holdout, nothing is promoted. It runs on the SPENT
23-symbol set, which has been read many times. It exists to answer one question
before a universe is spent on it: does the rule the chart owner actually
DESCRIBED behave differently from the rule he stated?

THE TWO ARE NOT THE SAME, and that is the whole subject. He stated "take the
second-last qualified candle", which ships as `pinLag = 1`. Asked WHY, he gave
a different rule:

    "sometimes after the last candle market never closes above its working
     line and goes straight down, that's why we choose 2nd last so the next
     candle will go above its working line"

    "the main goal is for short trend how much up possible we can enter, not
     that much up so we miss the entry W->F"

That is not a rule about POSITION. It is: enter as high as possible in a
downtrend (as low as possible in an uptrend) among the candles that actually
CONFIRM. `pinLag` is a proxy for it -- a good one when the pullback offers
exactly two qualifying candles and the newest one usually fails to Work, and a
bad one otherwise. He said as much himself: "in this case we can choose the
last candle as the next candle closes beyond the working line of it".

`pinPick = PICK_BEST` answers it directly. See the constant in ../port for why
no lookahead is needed: W spreads downward through the candidates and F spreads
upward, so on any bar the confirming set is known exactly and its highest
member is the best short entry available at the moment an entry exists.

THREE ARMS, and the third is the one under test:

    A  pinLag 0   the newest qualifying candle, `pinNewest` deleting the rest
    B  pinLag 1   the second-newest -- WHAT SHIPS
    C  PICK_BEST  the best-priced candle of those confirming on the bar

WHAT IS REPORTED, and the order matters because the headline everyone reaches
for is the wrong one here. B trades a fraction of what A and C do: a pullback
offering one qualifying candle gives B nothing to pick and it does not trade at
all. So R PER ARMED SETUP flatters B by construction -- it is the average of a
hand-picked minority. The unit that decides anything is R PER PULLBACK OFFERED,
over the union of pullbacks any rule could have traded, with a rule that passes
scoring 0 rather than being dropped from its own denominator.

SHORTS ONLY, as the pin-selection pages have been throughout -- "first legs
just measure the shorts and bearish whether this work or not" -- and filtered
at the pin, so the longs never took a `maxLive` slot either.
"""
from __future__ import annotations

import pathlib
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

from indicators.undertow.port import undertow as U               # noqa: E402
from indicators.undertow.studies.undertow_sweep import (         # noqa: E402
    FEE, TFS, load)
from research.data import SYMBOLS                                # noqa: E402

# AS SHIPPED, PINNED -- and unlike undertow_pinlag.py's, this BASE is pinned to
# what ships TODAY: msLen 14, the pullback-extreme stop, the direction-only
# bias gate and the local anchor. Every setting named, so a default moving
# later cannot silently re-point this page.
BASE = dict(
    biasSrc=U.BS_STRUCT, msLen=14, msShortLen=3, swingSrc=U.SW_BAR,
    msBosNeedsIdm=True, smcInternalLen=5, famStrict=True, armWins=True,
    stopSrc=U.S_PULL, pinNewest=True, famPriority=True, failTest=U.T_TOUCH,
    confirmOrder=U.C_WF, pinAt=U.PIN_LOCAL, pbLook=10, locTol=0,
    endMinor=U.E_FLIP, endSweep=False, endStale=False, retraceMax=70,
    useBackup=True, biasGate=U.BG_DIRECTION, maxLive=64, feeFrac=FEE, rr=3.5,
    side=U.SIDE_SHORT,
    # Named here as well as in every arm. The arms below override it, but the
    # baseline has to state it or a default moving would re-point this page --
    # and `pinLag`'s default moved THIS MORNING, which is exactly why the pin
    # check refuses a baseline that leaves it out.
    pinLag=0,
    # Named here as well as in every arm, same reason as `pinLag` above:
    # the baseline has to state it or a default moving re-points this
    # page -- and this is the page that argues for moving it.
    pinPick=U.PICK_READY)

ARMS = [("A", "lag 0 · newest", dict(pinLag=0, pinPick=U.PICK_READY)),
        ("B", "lag 1 · SHIPS", dict(pinLag=1, pinPick=U.PICK_READY)),
        ("C", "PICK_BEST", dict(pinLag=0, pinPick=U.PICK_BEST))]
MIN_BARS = 11000


def run_tf(tf, syms):
    d = load(tf, syms)
    # per arm: {(symbol, pbStart): R}, and the raw counters
    got: dict = {k: {} for k, _, _ in ARMS}
    cnt: dict = {k: [0, 0, 0] for k, _, _ in ARMS}     # armed, filled, among
    offered: set = set()
    used = 0
    for s in syms:
        cs = d.get(s)
        if not cs or len(cs) < MIN_BARS:
            continue
        used += 1
        for k, _, kw in ARMS:
            r = U.run(cs, U.P(**{**BASE, **kw}), s)
            by = {(t.symbol, t.armBar): t for t in r.real}
            cnt[k][0] += len(r.armed)
            cnt[k][1] += len(r.real)
            cnt[k][2] += r.nPickAmong
            for a in r.armed:
                t = by.get((s, a["bar"]))
                # An armed setup that never filled is a real outcome and a 0,
                # not a missing row. A pullback arming twice keeps the later
                # arm, which `armWins` makes rare.
                key = (s, a["pbStart"])
                got[k][key] = 0.0 if t is None else t.r
                offered.add(key)

    print(f"\n{'-' * 78}\n{tf}  ·  {used} symbols  ·  "
          f"{len(offered)} pullbacks traded by at least one rule\n{'-' * 78}")
    print(f"  {'arm':22} {'armed':>6} {'filled':>7} {'chose':>6} "
          f"{'R/armed':>9} {'R/pullback':>11} {'total R':>9}")
    out = {}
    for k, label, _ in ARMS:
        vals = got[k]
        tot = sum(vals.values())
        per_armed = tot / len(vals) if vals else 0.0
        # THE UNIT THAT DECIDES. Every pullback any rule could have traded is
        # in the denominator for all three, so a rule that sits one out is
        # charged for sitting it out instead of being flattered by it.
        per_offered = tot / len(offered) if offered else 0.0
        print(f"  {k} {label:20} {cnt[k][0]:6} {cnt[k][1]:7} {cnt[k][2]:6} "
              f"{per_armed:+9.3f} {per_offered:+11.3f} {tot:+9.1f}")
        out[k] = (vals, per_offered)
    # Clustered by symbol, because one symbol's pullbacks are not independent.
    print("\n  C - B, PAIRED ON THE PULLBACK, clustered by symbol")
    for other in ("A", "B"):
        per: dict = {}
        for key in offered:
            d1 = out["C"][0].get(key, 0.0) - out[other][0].get(key, 0.0)
            per.setdefault(key[0], []).append(d1)
        means = [statistics.mean(v) for v in per.values()]
        m = statistics.mean(means)
        se = (statistics.stdev(means) / len(means) ** 0.5
              if len(means) > 1 else 0.0)
        pos = sum(1 for x in means if x > 0)
        print(f"    C - {other}   {m:+.3f} +/- {se:.3f}  "
              f"z {m / se if se else 0:+.2f}   "
              f"symbols agreeing {pos}/{len(means)}")
    return out


if __name__ == "__main__":
    print(__doc__.split("\n\n")[0])
    print("DESCRIPTIVE — spent 23-symbol set, no holdout, nothing promoted.")
    for tf in TFS:
        run_tf(tf, SYMBOLS)
    print(f"\n{'=' * 78}")
    print("READ `R/pullback`, NOT `R/armed`. B trades a fraction of the\n"
          "pullbacks the other two do, so its R/armed is the average of a\n"
          "minority it selected itself. R/pullback charges every rule for the\n"
          "opportunities it passed on, which is the comparison being made.")
    print("\nAND NOTHING HERE PROMOTES ANYTHING. Spent set, in sample, no\n"
          "control. A mechanism that matches the stated goal is a reason to\n"
          "prefer it on its own terms; this page only says whether the\n"
          "preference costs anything measurable.")
