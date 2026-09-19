"""Why do the losers lose? Anatomy of every losing trade, whole venue.

    PYTHONPATH=. python3 indicators/undertow/studies/undertow_losses.py

**DESCRIPTIVE.** Every cached symbol, the shipped configuration, nothing
compared and nothing promoted -- see undertow_diagnose.py for why describing a
spent universe is legitimate and choosing on one is not.

THE QUESTION. "R per trade is -0.02" says how much is lost and nothing about
where. A loss has at least two completely different shapes and they call for
opposite fixes:

    NEVER WORKED   the trade went to the stop without ever showing a profit.
                   The ENTRY was wrong -- the pin, the direction, the moment.
    GAVE IT BACK   the trade ran 1R, 2R, sometimes 3R in profit and then
                   reversed into the stop. The entry was RIGHT and the EXIT
                   gave the money back.

A strategy that is 90% "never worked" needs a better filter. One that is 40%
"gave it back" needs a better exit, and no amount of pin selection will touch
it. The headline R is identical either way, which is why it has not been able
to tell anyone which week of work to do.

WHAT IS MEASURED

  1. the MFE of every LOSER -- how far in profit it got before it died
  2. the MAE of every WINNER -- how much heat a winning trade takes, which is
     the other side of the same question and bounds how tight a stop could be
  3. the loss anatomy split by bias state, confirmation route, candle code,
     backup fill and risk size, to find a bucket that is worse than the rest
  4. a descriptive costing of two exits the anatomy suggests -- break-even
     after +1R, and a partial at +1R -- computed on the SAME trades

THE COSTING IS NOT A RECOMMENDATION. Both exits are scored on the data that
suggested them, which is the definition of the -0.31 R illusion in
../measurements/UNDERTOW_PARAMS.md. They are here so the size of the prize is
known before a prereg is written, not so one can be chosen.

THE TWO EXITS ARE WALKED BAR BY BAR, NOT INFERRED FROM MFE. The first version
of this page scored them off the excursion -- a loser that reached +1R became a
0, a winner was left alone -- and that is an UPPER BOUND, because a winner that
went +1R, came back through its entry and then ran on to the target would
really have been SCRATCHED and MFE cannot see that it happened. The walk counts
those as scratches and reports how many there were, which is the difference
between knowing the prize and hoping for it.

AND IT STILL CANNOT SEE INSIDE A BAR. Highs and lows are all there is, so a bar
spanning both +1R and the stop counts as having reached +1R, and a bar spanning
both the break-even stop and the target resolves AGAINST the trade -- the same
rule the engine uses for a bar spanning entry and stop. Correcting that needs
tick data.
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
    MIN_BARS, mfe_mae, pct, universe)


def collect(tf, syms):
    """Every resolved trade with its excursions, plus the bars it took."""
    d = load(tf, syms)
    rows = []
    for s in syms:
        cs = d.get(s)
        if not cs or len(cs) < MIN_BARS:
            continue
        # TRACKS THE CURRENT DEFAULT — the same exemption and the same reason
        # as undertow_diagnose.py: this describes the chart people load.
        r = U.run(cs, U.P(feeFrac=FEE), s)
        for t in r.real:
            best, worst = mfe_mae(cs, t)
            rows.append((t, best, worst, cs))
    return rows


def walk_be(t, cs):
    """R if the stop moved to break-even once the trade was +1R up.

    WALKED BAR BY BAR rather than inferred from MFE, because the inferred
    version is an UPPER BOUND and the difference is the whole question: a
    winner that reached +1R, came back through its entry and then ran on to
    the target is a SCRATCH under this rule, and MFE cannot see that it
    happened. The first version of this page counted those as wins and so
    could only overstate the prize.

    Intrabar order is unknowable, so a bar that spans both levels resolves
    AGAINST the trade -- the same rule the engine uses for a bar spanning
    entry and stop.
    """
    risk = abs(t.entry - t.stop)
    if risk <= 0 or t.exitBar <= t.fillBar:
        return t.r
    up = False
    for c in cs[t.fillBar:t.exitBar + 1]:
        hit1 = ((t.entry - c.l) / risk >= 1.0 if t.short
                else (c.h - t.entry) / risk >= 1.0)
        if up:
            back = c.h >= t.entry if t.short else c.l <= t.entry
            if back:
                return 0.0
        elif hit1:
            up = True
    return t.r


def walk_half(t, cs):
    """R if half the position came off at +1R and the rest ran on."""
    risk = abs(t.entry - t.stop)
    if risk <= 0 or t.exitBar <= t.fillBar:
        return t.r
    for c in cs[t.fillBar:t.exitBar + 1]:
        hit1 = ((t.entry - c.l) / risk >= 1.0 if t.short
                else (c.h - t.entry) / risk >= 1.0)
        if hit1:
            return 0.5 * 1.0 + 0.5 * t.r
    return t.r


def anatomy(rows):
    lose = [(t, b, w, n) for t, b, w, n in rows if not t.won]
    win = [(t, b, w, n) for t, b, w, n in rows if t.won]
    if not lose:
        return None
    print(f"\n   losers {len(lose)}   winners {len(win)}   "
          f"({pct(len(lose), len(rows))} of trades lose)")

    print("\n   HOW FAR THE LOSERS GOT BEFORE THEY DIED")
    bands = [(0.0, 0.25, "never moved      "), (0.25, 0.5, "under +0.5R      "),
             (0.5, 1.0, "+0.5R to +1R     "), (1.0, 2.0, "+1R to +2R       "),
             (2.0, 3.0, "+2R to +3R       "), (3.0, 99.0, "+3R or better    ")]
    for lo, hi, lab in bands:
        n = sum(1 for _, b, _, _ in lose if lo <= b < hi)
        print(f"     {lab} {n:8}  {pct(n, len(lose))}")
    up1 = sum(1 for _, b, _, _ in lose if b >= 1.0)
    up2 = sum(1 for _, b, _, _ in lose if b >= 2.0)
    print(f"\n     GAVE IT BACK from +1R or more: {up1} "
          f"({pct(up1, len(lose))} of losers)")
    print(f"     GAVE IT BACK from +2R or more: {up2} "
          f"({pct(up2, len(lose))} of losers)")

    print("\n   HOW MUCH HEAT THE WINNERS TOOK  (max adverse, in R)")
    if win:
        maes = sorted(w for _, _, w, _ in win)
        q = statistics.quantiles(maes, n=100)
        print(f"     median {statistics.median(maes):5.2f}   p75 {q[74]:5.2f}"
              f"   p90 {q[89]:5.2f}   p95 {q[94]:5.2f}")
        for lvl in (0.25, 0.5, 0.75):
            n = sum(1 for m in maes if m <= lvl)
            print(f"     never went past -{lvl:.2f}R: {pct(n, len(maes))}"
                  f"  <- a stop there keeps {pct(n, len(maes))} of winners")

    print("\n   WHICH BUCKET LOSES WORST")
    def split(name, keyfn):
        seen = {}
        for t, b, w, n in rows:
            seen.setdefault(keyfn(t), []).append(t.r)
        print(f"     {name}")
        for k in sorted(seen, key=lambda x: str(x)):
            v = seen[k]
            if len(v) < 500:
                continue
            print(f"       {str(k):22} {len(v):7} trades  "
                  f"R {statistics.mean(v):+.3f}")
    split("by bias state at the pin", lambda t: t.state)
    # NO CONFIRMATION-ROUTE SPLIT. `order` is on the ARMED dict, not on
    # `Trade`, and asking for it here crashed the first run of this page --
    # written from memory of the wrong record. Carrying it onto Trade is a
    # port change for a question nobody has asked yet, so the split is dropped
    # rather than the field added on a guess.
    split("by candle code", lambda t: t.code)
    split("by fill", lambda t: t.backup or "at the focus line")
    split("by risk size", lambda t: (
        "tight  <1%" if abs(t.entry - t.stop) / t.entry < 0.01 else
        "normal 1-3%" if abs(t.entry - t.stop) / t.entry < 0.03 else
        "wide   >3%"))

    print("\n   WHAT TWO EXITS WOULD HAVE DONE — descriptive, not a choice")
    rr = U.P().rr
    base = statistics.mean([t.r for t, _, _, _ in rows])
    be = [walk_be(t, c) for t, _, _, c in rows]
    half = [walk_half(t, c) for t, _, _, c in rows]
    print(f"     as it ships (target {rr}R)      {base:+.4f} R per trade")
    print(f"     + break-even stop after +1R    {statistics.mean(be):+.4f}"
          f"   ({statistics.mean(be) - base:+.4f})")
    print(f"     + half off at +1R              {statistics.mean(half):+.4f}"
          f"   ({statistics.mean(half) - base:+.4f})")
    scr = sum(1 for t, x in zip([r[0] for r in rows], be) if t.won and x == 0.0)
    print(f"     winners the break-even stop would have SCRATCHED: {scr}"
          f"  ({pct(scr, len(win))} of winners)")
    print("     WALKED BAR BY BAR, not inferred from MFE: a winner that went\n"
          "     +1R, came back through its entry and then ran to target is\n"
          "     counted as a SCRATCH here, which is what would really happen.")
    return statistics.mean(be) - base


if __name__ == "__main__":
    print(__doc__.split("\n\n")[0])
    syms = universe()
    print(f"DESCRIPTIVE — {len(syms)} cached symbols, shipped configuration.")
    for tf in TFS:
        rows = collect(tf, syms)
        print(f"\n{'=' * 78}\n{tf}  ·  {len(rows)} resolved trades\n{'=' * 78}")
        anatomy(rows)
    print(f"\n{'=' * 78}")
    print("READ THE FIRST BLOCK. If most losers never moved, the ENTRY is the\n"
          "problem and no exit will fix it. If a large share gave back a gain,\n"
          "the entry is finding something the exit is handing back — and those\n"
          "are different weeks of work.")
