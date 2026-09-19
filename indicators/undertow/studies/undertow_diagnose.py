"""Where does the shipped strategy actually leak? Every cached symbol.

    PYTHONPATH=. python3 indicators/undertow/studies/undertow_diagnose.py

**DESCRIPTIVE, AND NOT A HOLDOUT.** It runs ONE configuration -- the one that
ships -- across every symbol in the local cache, which is essentially the whole
venue. Nothing is compared, nothing is selected, nothing is promoted. It exists
to answer "what is wrong with this thing" with numbers instead of impressions,
so that a fix can be pre-registered before any evaluation data is touched.

WHY DESCRIBING A SPENT UNIVERSE IS LEGITIMATE and selecting on it is not. Every
one of these symbols has been read before; twelve disjoint holdouts have been
spent on twelve component questions. What that forbids is CHOOSING between
options on this data, because best-of-N selection on a read universe is worth
-0.31 R per trade of pure illusion (../measurements/UNDERTOW_PARAMS.md). It does
not forbid measuring where the funnel loses setups or how the exit sits against
the move -- those are properties of the mechanism, not a choice between arms.

AND THE HOLDOUT METHOD IS OVER, which is the constraint every plan after this
has to start from. research/symbols_fresh.py, re-counted against the live
exchange: 585 eligible contracts, 563 spoken for, 21 usable and all at the
liquidity floor. A thirteenth set of 45 does not exist, and 21 contracts field
about 20 / 19 / 14 symbols on 15m / 30m / 1h -- it could not report 30m, and the
symbols it could report 15m on are the thinnest tail on the venue rather than
the population every earlier page measured.

So the two honest designs left are WALK-FORWARD ON THE SPENT SETS and the
PROSPECTIVE FORWARD RECORD the watch was built for. This page is neither. It is
the diagnosis that says what either of them should be pointed at.

WHAT IT REPORTS, and the order is deliberate -- the funnel first, because a
strategy that loses 9 setups in 10 before the entry has its biggest lever there
and not in the exit:

  1. the funnel, pins -> armed -> filled -> resolved
  2. R per trade and per ARMED setup, against the break-even line WITH fees
  3. the same split by the bias state at the pin, which `biasGate = direction
     only` made tradeable and which nothing has scored apart yet
  4. the MFE distribution against the fixed 3.5R target -- the exit question,
     re-measured here because UNDERTOW_EXITS.md is SUPERSEDED
  5. per-symbol dispersion, because a mean over 500 symbols still hides whether
     it is carried by ten of them
"""
from __future__ import annotations

import pathlib
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

from indicators.undertow.port import undertow as U               # noqa: E402
from indicators.undertow.studies.undertow_sweep import (         # noqa: E402
    CACHE, FEE, TFS, load)

MIN_BARS = 6000


def universe() -> list:
    """Every symbol with a cached file, not a curated list.

    The point of this page is to stop reading six symbols and calling it the
    population, so the universe is whatever is on disk.
    """
    return sorted({p.name.rsplit("-", 1)[0] for p in CACHE.glob("*.json")})


def mfe_mae(cs, t) -> tuple:
    """Best and worst excursion of one trade, in R, from the fill to the exit.

    Computed here because `Trade` does not carry it: the engine scores a fixed
    target and has no reason to remember how far the move went. The exit
    question cannot be asked without it.
    """
    risk = abs(t.entry - t.stop)
    if risk <= 0 or t.exitBar <= t.fillBar:
        return 0.0, 0.0
    seg = cs[t.fillBar:t.exitBar + 1]
    if t.short:
        best = (t.entry - min(c.l for c in seg)) / risk
        worst = (max(c.h for c in seg) - t.entry) / risk
    else:
        best = (max(c.h for c in seg) - t.entry) / risk
        worst = (t.entry - min(c.l for c in seg)) / risk
    return best, worst


def run_tf(tf, syms):
    d = load(tf, syms)
    fun = dict(pins=0, armed=0, filled=0, resolved=0, cap=0, sup=0,
               noW=0, noF=0, biasDrop=0, missBack=0, missGone=0, missStop=0)
    trades, perSym, held = [], {}, []
    used = 0
    for s in syms:
        cs = d.get(s)
        if not cs or len(cs) < MIN_BARS:
            continue
        used += 1
        # Every other study pins BECAUSE it must keep reproducing a
        # published table. This one must do the opposite: it asks what the
        # chart anybody actually loads is doing, so a pinned baseline would
        # make it describe a configuration nobody runs. It is re-run when a
        # default moves rather than kept reproducible across one.
        #
        # TRACKS THE CURRENT DEFAULT — `feeFrac` is named only because P
        # defaults it to 0, and a page reporting gross R would be wrong.
        r = U.run(cs, U.P(feeFrac=FEE), s)
        fun["pins"] += len(r.pins);      fun["armed"] += len(r.armed)
        fun["filled"] += r.nFilled;      fun["cap"] += r.nCap
        fun["sup"] += r.nSuper;          fun["noW"] += r.nNoWork
        fun["noF"] += r.nNoFail;         fun["biasDrop"] += r.nBiasDrop
        fun["missBack"] += r.nMissBack;  fun["missGone"] += r.nMissGone
        fun["missStop"] += r.nMissStop
        rs = []
        for t in r.real:
            best, worst = mfe_mae(cs, t)
            trades.append((t, best, worst))
            rs.append(t.r)
            held.append(t.exitBar - t.fillBar)
        fun["resolved"] += len(rs)
        if rs:
            perSym[s] = statistics.mean(rs)
    return tf, used, fun, trades, perSym, held


def pct(a, b):
    return f"{100.0 * a / b:5.1f}%" if b else "    — "


def report(tf, used, fun, trades, perSym, held):
    print(f"\n{'=' * 78}\n{tf}  ·  {used} symbols  ·  {len(trades)} trades"
          f"\n{'=' * 78}")

    print("\n1. THE FUNNEL — where setups are lost")
    p, a, f = fun["pins"], fun["armed"], fun["resolved"]
    print(f"   pins found            {p:8}")
    print(f"   armed                 {a:8}   {pct(a, p)} of pins")
    print(f"     lost: superseded    {fun['sup']:8}   turned away at cap "
          f"{fun['cap']}")
    print(f"     lost: no W / W no F {fun['noW']:8} / {fun['noF']}")
    print(f"     lost: bias turned   {fun['biasDrop']:8}")
    print(f"   filled and resolved   {f:8}   {pct(f, a)} of armed")
    print(f"     no entry: back/gone/stop  {fun['missBack']} / "
          f"{fun['missGone']} / {fun['missStop']}")

    if not trades:
        print("\n   NO TRADES. Nothing below can be reported.")
        return None
    rs = [t.r for t, _, _ in trades]
    won = sum(1 for t, _, _ in trades if t.won)
    fee = statistics.mean([abs(t.r) for t, _, _ in trades]) * 0 + FEE
    rr = U.P().rr
    # Break-even INCLUDING the cost, which is where UNDERTOW_V3.md found a
    # panel calling a losing rule a winner: (1 + drag) / (1 + rr), not 1/(1+rr).
    risks = [abs(t.entry - t.stop) / t.entry for t, _, _ in trades]
    drag = FEE / statistics.median(risks) if risks else 0.0
    be = 100.0 * (1.0 + drag) / (1.0 + rr)
    print("\n2. THE MONEY")
    print(f"   R per trade           {statistics.mean(rs):+8.3f}")
    print(f"   R per ARMED setup     {sum(rs) / a if a else 0:+8.3f}")
    print(f"   win rate              {100.0 * won / len(rs):7.1f}%   "
          f"break-even {be:.1f}%  (drag {drag:.3f} R)")
    print(f"   median risk           {100 * statistics.median(risks):7.2f}% "
          f"of entry")
    print(f"   median bars held      {statistics.median(held):7.0f}")

    print("\n3. BY BIAS STATE AT THE PIN  (all four trade since "
          "`direction only`)")
    for st in ("running", "immature", "ending", "none"):
        g = [t.r for t, _, _ in trades if t.state == st]
        w = sum(1 for t, _, _ in trades if t.state == st and t.won)
        if not g:
            continue
        print(f"   {st:10} {len(g):7} trades  R {statistics.mean(g):+7.3f}  "
              f"win {100.0 * w / len(g):5.1f}%  "
              f"{'ABOVE' if 100.0 * w / len(g) > be else 'below'} break-even")

    print("\n4. THE EXIT — how far the move actually went, in R")
    mfes = sorted(b for _, b, _ in trades)
    q = statistics.quantiles(mfes, n=100)
    print(f"   median MFE {statistics.median(mfes):6.2f}   "
          f"p75 {q[74]:6.2f}   p90 {q[89]:6.2f}   p99 {q[98]:6.2f}")
    for lvl in (1.0, 2.0, rr, 5.0, 7.0, 10.0):
        n = sum(1 for m in mfes if m >= lvl)
        tag = "  <- the shipped target" if abs(lvl - rr) < 1e-9 else ""
        print(f"   reach {lvl:5.1f} R   {pct(n, len(mfes))}{tag}")

    print("\n5. DISPERSION — is the mean carried by a few symbols?")
    ms = sorted(perSym.values())
    pos = sum(1 for v in ms if v > 0)
    loo = min(statistics.mean([x for j, x in enumerate(ms) if j != i])
              for i in range(len(ms))) if len(ms) > 1 else 0.0
    print(f"   symbols {len(ms)}   positive {pos} ({pct(pos, len(ms))})   "
          f"median symbol {statistics.median(ms):+.3f}")
    print(f"   worst leave-one-out {loo:+.3f}   "
          f"best symbol {ms[-1]:+.3f}   worst {ms[0]:+.3f}")
    return statistics.mean(rs)


if __name__ == "__main__":
    print(__doc__.split("\n\n")[0])
    syms = universe()
    print(f"DESCRIPTIVE — {len(syms)} cached symbols, the shipped "
          f"configuration, nothing promoted.")
    out = {}
    for tf in TFS:
        out[tf] = report(*run_tf(tf, syms))
    print(f"\n{'=' * 78}\nSUMMARY — R per trade, shipped configuration")
    for tf, v in out.items():
        print(f"   {tf:8} {v:+.3f}" if v is not None else f"   {tf:8}  —")
    print("\nREAD SECTION 1 FIRST. A lever on a stage that discards nine in ten\n"
          "is worth more than one on a stage that discards one in ten, whatever\n"
          "the R column says — and no number here chooses anything, because\n"
          "every symbol on it has been read before.")
