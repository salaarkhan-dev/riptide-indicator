"""Three edge cases the chart owner named: the route, the wide stop, the age.

    PYTHONPATH=. python3 indicators/undertow/studies/undertow_edges.py

**DESCRIPTIVE.** Every cached symbol, the shipped configuration, nothing
compared and nothing promoted -- see undertow_diagnose.py for why describing a
spent universe is legitimate and choosing on one is not. This exists so a
prereg can name a THRESHOLD instead of searching over one, which is the whole
difference between a hypothesis and a fishing trip.

THE THREE QUESTIONS, in his words:

  1. "we wanna see the W>F and F>W>F"
     Two routes to the same arm. W->F is the clean one: the counter-trend
     candle works, then fails. F->W->F failed first, worked, then failed again
     -- a rounder, messier shape. Nothing has ever scored them apart.

  2. "to wide stoplosses we wanna avoid that ... sometimes due to volatility
     too much big candles appears"
     The stop rides the pullback extreme, so one outsized bar inside the
     pullback widens it for every candidate behind it. A wide stop is not
     wrong in R -- R normalises it -- but it is wrong in POSITION SIZE and in
     the time it takes to resolve, and if those trades also score worse then
     the cap earns its place twice.

  3. "we wanna test minimum candles in the pullback for realistic pullback"
     A pullback one bar old is not a pullback. `pbMinAge` and `pbMinDepth`
     already exist in P for exactly this.

AND THE THIRD CONTROL IS CURRENTLY INERT, which is the first thing this page
found and the reason it is worth running before writing anything. In
port/undertow.py the two minimums are applied inside

    if p.pinAt == PIN_PULL:
        locOk = locOk and pbAge >= p.pbMinAge and ...

and the shipped anchor is PIN_LOCAL. So the setting exists, reads sensibly in
the Pine, and DOES NOTHING on the chart anybody loads. Any prereg that proposes
a minimum pullback has to widen that condition first or it will measure a
field that never fires.

HOW THE JOIN WORKS. `Trade` carries neither the confirmation route nor the
pullback it came from; the ARMED record carries both. They share `armBar`, so
every trade is matched back to its arm rather than adding fields to the port
for a question that might not survive this page.
"""
from __future__ import annotations

import pathlib
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

from indicators.undertow.port import undertow as U               # noqa: E402
from indicators.undertow.studies.undertow_sweep import (         # noqa: E402
    FEE, TFS, load)
from indicators.undertow.studies.undertow_diagnose import (      # noqa: E402
    MIN_BARS, universe)


def collect(tf, syms):
    """Every resolved trade, joined back to the arm that produced it."""
    d = load(tf, syms)
    rows = []
    for s in syms:
        cs = d.get(s)
        if not cs or len(cs) < MIN_BARS:
            continue
        # TRACKS THE CURRENT DEFAULT — same exemption, same reason as
        # undertow_diagnose.py: this describes the chart people load.
        r = U.run(cs, U.P(feeFrac=FEE), s)
        by = {a["bar"]: a for a in r.armed}
        for t in r.real:
            a = by.get(t.armBar)
            if a is None:
                continue
            risk = abs(t.entry - t.stop) / t.entry if t.entry else 0.0
            rows.append(dict(r=t.r, won=t.won, risk=risk,
                             route="F-W-F" if a["order"] == 2 else "W-F",
                             age=t.bar - a["pbStart"], cand=a["pinIdx"] + 1,
                             held=t.exitBar - t.fillBar, sym=s))
    return rows


def band(rows, name, keyfn, order=None):
    """R by bucket, with a per-symbol clustered error on each.

    THE ERROR BAR IS THE POINT. A bucket mean over 20,000 overlapping trades
    looks precise and is not; clustering by symbol is what makes "worse" mean
    something. Buckets under 30 symbols are printed and marked rather than
    hidden, because a thin bucket is usually where the interesting claim is.
    """
    seen: dict = {}
    for x in rows:
        seen.setdefault(keyfn(x), []).append(x)
    keys = order or sorted(seen, key=lambda k: str(k))
    print(f"\n   {name}")
    print(f"     {'bucket':22} {'trades':>8} {'R':>8} {'+/-':>7} "
          f"{'z':>6} {'win%':>6} {'bars':>6}")
    for k in keys:
        v = seen.get(k)
        if not v:
            continue
        per: dict = {}
        for x in v:
            per.setdefault(x["sym"], []).append(x["r"])
        ms = [statistics.mean(q) for q in per.values()]
        mu = statistics.mean(ms)
        se = statistics.stdev(ms) / len(ms) ** 0.5 if len(ms) > 1 else 0.0
        w = 100.0 * sum(1 for x in v if x["won"]) / len(v)
        held = statistics.median([x["held"] for x in v])
        thin = "  <- thin" if len(per) < 30 else ""
        print(f"     {str(k):22} {len(v):8} {mu:+8.3f} {se:7.3f} "
              f"{mu / se if se else 0:+6.2f} {w:6.1f} {held:6.0f}{thin}")


def report(tf, rows):
    print(f"\n{'=' * 78}\n{tf}  ·  {len(rows)} trades joined to their arm"
          f"\n{'=' * 78}")
    if not rows:
        print("   no trades")
        return
    band(rows, "1. BY CONFIRMATION ROUTE", lambda x: x["route"],
         order=["W-F", "F-W-F"])

    risks = sorted(x["risk"] for x in rows)
    med = statistics.median(risks)
    print(f"\n   median risk {100 * med:.2f}% of entry   "
          f"p90 {100 * risks[int(.9 * len(risks))]:.2f}%   "
          f"p99 {100 * risks[int(.99 * len(risks))]:.2f}%")
    band(rows, "2. BY STOP WIDTH  (risk as % of entry)",
         lambda x: ("a <1%" if x["risk"] < .01 else "b 1-2%" if x["risk"] < .02
                    else "c 2-3%" if x["risk"] < .03 else
                    "d 3-5%" if x["risk"] < .05 else
                    "e 5-8%" if x["risk"] < .08 else "f >8%"))

    band(rows, "3. BY PULLBACK AGE AT THE PIN  (bars since it began)",
         lambda x: ("a 0-1 bars" if x["age"] <= 1 else
                    "b 2-3 bars" if x["age"] <= 3 else
                    "c 4-6 bars" if x["age"] <= 6 else
                    "d 7-10 bars" if x["age"] <= 10 else "e 11+ bars"))

    band(rows, "4. BY QUALIFYING CANDLES BEFORE THE PIN",
         lambda x: ("a 1st candle" if x["cand"] == 1 else
                    "b 2nd" if x["cand"] == 2 else
                    "c 3rd" if x["cand"] == 3 else "d 4th or later"))

    # WHAT A CAP WOULD ACTUALLY COST, in trades as well as in R. A filter that
    # improves R by removing nine tenths of the trades is not an improvement,
    # it is a different strategy with a smaller sample.
    print("\n   5. WHAT A MAX-RISK CAP WOULD KEEP  (descriptive, not a choice)")
    # CLUSTERED, LIKE THE BUCKETS ABOVE. The first version of this table used a
    # plain trade-weighted mean while every bucket row above it was clustered
    # by symbol, so a wide-stop bucket reading -0.219 sat directly above a cap
    # table claiming the cap changed nothing. Two different statistics printed
    # as though they were one, which is a reader's trap and was nearly the
    # basis of a prereg hypothesis.
    def clustered(sel):
        per: dict = {}
        for x in sel:
            per.setdefault(x["sym"], []).append(x["r"])
        ms = [statistics.mean(q) for q in per.values()]
        return statistics.mean(ms) if ms else 0.0
    base = clustered(rows)
    print(f"     {'cap':>8} {'kept':>8} {'share':>7} {'R':>8}  {'vs all':>8}")
    for cap in (0.02, 0.03, 0.04, 0.05, 0.08):
        k = [x for x in rows if x["risk"] <= cap]
        if not k:
            continue
        m = clustered(k)
        print(f"     {100 * cap:7.0f}% {len(k):8} "
              f"{100.0 * len(k) / len(rows):6.1f}% {m:+8.3f} {m - base:+8.3f}")
    print("     FIVE CAPS ARE A SEARCH. None of these is a result; the prereg\n"
          "     names ONE on a stated reason and scores that one.")


if __name__ == "__main__":
    print(__doc__.split("\n\n")[0])
    syms = universe()
    print(f"DESCRIPTIVE — {len(syms)} cached symbols, shipped configuration.")
    print("`pbMinAge` and `pbMinDepth` are INERT under PIN_LOCAL — see the "
          "module docstring.")
    for tf in TFS:
        report(tf, collect(tf, syms))
