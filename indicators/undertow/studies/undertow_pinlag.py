"""Which candle of the pullback: the newest, or the one before it?

    PYTHONPATH=. python3 indicators/undertow/studies/undertow_pinlag.py

DESCRIPTIVE. No prereg, no holdout, nothing is promoted. It runs on the SPENT
23-symbol set, which has been read many times, and it exists to answer one
question before a universe is spent on it: **is there an effect here big enough
to be worth pre-registering?** If the paired difference is a tenth of its own
error bar, the answer is no and nothing has been wasted finding out.

THE RULE, in the chart owner's words. In a bearish trend the pullback offers
1..n counter-trend candles; a hammer at the top of it is the setup. Two ways to
choose which:

    A  "n candle if it qualifies, otherwise the last qualified candle"
    B  "let's say three qualified (n, n-1, n-2) -- in this case choose n-1"

**A IS ALREADY WHAT SHIPS.** It is `pinNewest=True`, the default: each new
qualifying candle supersedes the earlier unarmed ones, so what arms is the
newest. Only B needed coding, as `pinLag=1`.

THE COMPARISON IS PAIRED AND THAT IS THE WHOLE DESIGN. 82% of pullbacks offer
exactly ONE qualifying candle, so the two rules agree on them by construction.
Comparing two whole populations that share 82% of their trades is how a study
produces a null that means nothing -- roughly 80 differing trades inside a
sample whose noise is ten times the effect anyone expects. So this pairs them:
only pullbacks where A and B pick DIFFERENT candles, A's outcome against B's
outcome on the same pullback, clustered by symbol. The shared 82% cancels
instead of drowning it.

SHORTS ONLY, as asked -- "first legs just measure the shorts and bearish
whether this work or not" -- and filtered at the pin rather than on the trade
list, so the longs never took a `maxLive` slot either.

WHAT B COSTS, reported and not buried: a pullback with only one qualifying
candle gives B nothing to pick, so B simply does not trade it. That is most of
them. B is a much rarer rule, and rarity is not a defect, but a page that
compared R without saying so would be describing a strategy nobody could run.
"""
from __future__ import annotations

import math
import pathlib
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

from indicators.undertow.port import undertow as U               # noqa: E402
from indicators.undertow.studies.undertow_sweep import (         # noqa: E402
    FEE, TFS, clustered, load)
from research.data import SYMBOLS                                # noqa: E402

# AS SHIPPED, PINNED. Same discipline as every other study here: every setting
# named, so a default moving later cannot silently re-point this page.
BASE = dict(
    biasSrc=U.BS_STRUCT, msLen=50, msShortLen=3, swingSrc=U.SW_BAR,
    msBosNeedsIdm=True, smcInternalLen=5, famStrict=True, armWins=True,
    stopSrc=U.S_SWING, pinNewest=True, famPriority=True, failTest=U.T_TOUCH,
    confirmOrder=U.C_WF, pinAt=U.PIN_PULL, locTol=0, endMinor=U.E_FLIP,
    endSweep=False, endStale=False, retraceMax=70, useBackup=True,
    maxLive=64, feeFrac=FEE, rr=3.5, shortsOnly=True)


def arms(tf, syms):
    """Both rules on the same data, keyed by (symbol, pullback)."""
    d = load(tf, syms)
    out = {0: {}, 1: {}}
    counts = {0: [0, 0, 0], 1: [0, 0, 0]}
    short = 0
    for s in syms:
        cs = d.get(s)
        if not cs or len(cs) < 11000:
            continue
        for lag in (0, 1):
            r = U.run(cs, U.P(pinLag=lag, **BASE), s)
            by = {(t.symbol, t.armBar): t for t in r.real}
            counts[lag][0] += len(r.armed)
            counts[lag][1] += len(r.real)
            if lag == 1:
                short += r.nLagShort
            for a in r.armed:
                t = by.get((s, a["bar"]))
                # An armed setup that never filled is a real outcome and is a
                # 0, not a missing row -- dropping them would score each rule
                # only on the pullbacks where its own choice happened to fill.
                # ONE ROW PER PULLBACK PER RULE, which is the unit being
                # paired. A pullback that arms twice keeps the later arm; with
                # `armWins` and the shape gate on that is rare, and `multi`
                # below reports how rare so the choice is not taken on trust.
                k = (s, a["short"], a["pbStart"])
                if k in out[lag]:
                    counts[lag][2] += 1
                out[lag][k] = (a["pin"], 0.0 if t is None else t.r)
    return out, counts, short


def run_tf(tf, syms):
    out, counts, short = arms(tf, syms)
    a, b = out[0], out[1]
    both = sorted(set(a) & set(b))
    diff = [k for k in both if a[k][0] != b[k][0]]
    print(f"\n{'-' * 78}\n{tf}\n{'-' * 78}")
    for lag, tag in ((0, "A  newest  (SHIPS)"), (1, "B  second newest")):
        n, f, multi = counts[lag]
        print(f"  {tag:22} armed {n:5}  filled {f:5}  "
              f"pullbacks arming twice {multi:4}")
    print(f"  pullbacks B gave up for want of a second candle: {short}")
    print(f"  pullbacks BOTH traded: {len(both)}   "
          f"of which they chose a DIFFERENT candle: {len(diff)}")
    if len(diff) < 30:
        print("\n  FEWER THAN 30 PAIRS. Nothing is reported from this "
              "timeframe: at this n the error bar is wider than any effect\n"
              "  this project has ever measured, and a number here would be "
              "read as a finding.")
        return None
    da = [a[k][1] for k in diff]
    db = [b[k][1] for k in diff]
    print(f"\n  ON THE {len(diff)} PULLBACKS WHERE THEY DISAGREE")
    print(f"    A  newest          {statistics.mean(da):+.3f} R")
    print(f"    B  second newest   {statistics.mean(db):+.3f} R")
    # Paired, clustered by symbol: one symbol's pullbacks are not independent.
    per = {}
    for k, x, y in zip(diff, da, db):
        per.setdefault(k[0], []).append(y - x)
    means = [statistics.mean(v) for v in per.values()]
    d = statistics.mean(means)
    se = statistics.stdev(means) / len(means) ** 0.5 if len(means) > 1 else 0
    z = d / se if se else 0
    print(f"    B - A              {d:+.3f} +/- {se:.3f}  z {z:+.2f}  "
          f"({len(means)} symbols)")
    return d, se, z, len(diff)


if __name__ == "__main__":
    print(__doc__.split("\n\n")[0])
    print("DESCRIPTIVE — spent 23-symbol set, no holdout, nothing promoted.")
    rows = {}
    for tf in TFS:
        rows[tf] = run_tf(tf, SYMBOLS)
    print(f"\n{'=' * 78}\nSUMMARY\n{'=' * 78}")
    print(f"  {'tf':8} {'B - A':>8} {'+/-':>7} {'z':>6} {'pairs':>7}")
    for tf, r in rows.items():
        if r is None:
            print(f"  {tf:8} {'not reported — too few pairs':>30}")
            continue
        print(f"  {tf:8} {r[0]:+8.3f} {r[1]:7.3f} {r[2]:+6.2f} {r[3]:7}")
    live = [r for r in rows.values() if r]
    # THE BAR IS A CONSISTENT SIGN, not a big number somewhere. The first
    # version of this asked for |z| >= 1 on any timeframe, which would have
    # called almost every table in ../measurements worth a universe --
    # UNDERTOW_PARAMS.md priced best-of selection at -0.31 R per trade of pure
    # illusion, and picking the loudest of three timeframes is that selection.
    signs = {r[0] > 0 for r in live}
    loud = live and max(abs(r[2]) for r in live) >= 2.0
    if len(live) < 2:
        print("\n  ONE TIMEFRAME IS NOT A RESULT. Nothing here is worth a "
              "universe until at\n  least two report enough pairs to speak.")
    elif len(signs) > 1:
        print("\n  THE TIMEFRAMES DISAGREE ON THE SIGN, which is what noise "
              "looks like at\n  these sample sizes and not a reason to spend "
              "anything. The mechanism is\n  real and the effect is not "
              "resolved; the honest next instrument is the\n  forward record, "
              "not another backtest.")
    elif loud:
        print("\n  WORTH A PREREG. Same sign on every reported timeframe and "
              "|z| >= 2 on one.\n  Write it before looking again — these "
              "numbers are from the spent set and\n  decide nothing.")
    else:
        print("\n  CONSISTENT BUT QUIET. Same sign throughout, no timeframe "
              "past |z| 2. Worth\n  keeping in view; not worth the last "
              "universe.")
