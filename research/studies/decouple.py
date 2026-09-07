"""The fill-rate problem, attacked at its actual cause.

fills.py established that moving the entry toward price raises the fill rate
and loses money, monotonically, out to a full ATR. But that test held the STOP
fixed at the raid extreme, which is the shipped rule. So what it really proved
is narrower than it looked:

    chasing loses WHEN THE STOP STAYS PUT.

That is a coupling problem, not a law. Entry and stop are welded together: the
stop sits beyond the raid extreme regardless of where we get in, so every tick
of chase is a tick of extra risk on every trade. Unweld them and the arithmetic
changes — a higher entry with a correspondingly nearer stop can hold risk
constant, or even shrink it.

So: four stop rules, each swept across the same entry buffers.

  raid extreme     shipped. Risk grows with the chase.        (the control)
  constant risk    stop placed to keep |entry-stop| exactly
                   what it was. Not at structure — a money
                   stop. Tests whether the buffer result was
                   about risk inflation or about entry quality.
  gap far edge     stop just beyond the FVG's distal edge.
                   Structural, and much nearer than the raid.
  swing            stop beyond the lowest low / highest high
                   of the last 5 bars before the signal.

If the buffer loss is risk inflation, `constant risk` should flatten the
curve. If it survives even at constant risk, then a chased entry is simply a
worse entry and the coupling was never the problem.

Reported for every cell: fill rate, WIN RATE, R/signal, and total R. Win rate
matters here in a way it usually does not — a tighter stop mechanically loses
more often while risking less per loss, so the two must be read together.
"""
from __future__ import annotations

import research.env  # noqa: F401  (must precede riptide.config)

import statistics

from research.data import load_sync, atr_at
from research.harness import simulate, mean_se

FEE = dict(fee_maker=0.02, fee_taker=0.06)
BUFFERS = (0.0, 0.25, 0.5, 1.0)
SWING = 5


def gap_bar(row):
    x = row.signal
    j = getattr(x, "fvg_bar", None)
    if j is None:
        idx = {c.t: i for i, c in enumerate(row.candles)}
        j = idx.get(getattr(x, "fvg_time", 0))
    return j if (j is not None and 2 <= j < len(row.candles)) else None


def stop_for(row, rule, entry):
    """Where the stop goes under each rule. None = this rule cannot place one."""
    x, cs = row.signal, row.candles
    if rule == "raid":
        return x.stop
    if rule == "constant":
        risk = abs(x.entry - x.stop)
        return entry - risk if x.is_long else entry + risk
    if rule == "gapfar":
        j = gap_bar(row)
        if j is None:
            return None
        a = atr_at(row) * 0.1
        # The distal edge — the side of the gap price would have to pass
        # through completely for the imbalance to be voided.
        return (cs[j - 2].h - a) if x.is_long else (cs[j - 2].l + a)
    if rule == "swing":
        lo = max(0, row.bar - SWING)
        a = atr_at(row) * 0.1
        seg = cs[lo:row.bar + 1]
        if not seg:
            return None
        return (min(c.l for c in seg) - a) if x.is_long else \
               (max(c.h for c in seg) + a)
    raise ValueError(rule)


def cell(rows, rule, k):
    outs, risks = [], []
    for r in rows:
        a = atr_at(r)
        entry = r.signal.entry + (a * k if r.signal.is_long else -a * k)
        stop = stop_for(r, rule, entry)
        if stop is None:
            continue
        # A stop on the wrong side of the entry is not a trade. The gap-far
        # and swing rules can produce one when the chase carries the entry
        # past its own structure; those signals are dropped, and the count
        # is printed so a rule that survives by discarding half the book is
        # visible rather than flattering.
        if (stop >= entry) if r.signal.is_long else (stop <= entry):
            continue
        outs.append(simulate(r.candles, r.bar, entry, stop, r.signal.is_long,
                             **FEE))
        risks.append(100 * abs(entry - stop) / entry)
    return outs, risks


def table(rows, kind):
    sub = [r for r in rows if r.kind == kind]
    print(f"\n{'=' * 78}\n{kind.upper()}  n={len(sub)}\n{'=' * 78}")
    print(f"  {'stop rule':<10} {'chase':>6}  {'kept':>5}  {'fill':>6}"
          f"  {'win':>6}  {'risk%':>6}  {'R/signal':>16}  {'total':>7}")
    for rule in ("raid", "constant", "gapfar", "swing"):
        for k in BUFFERS:
            outs, risks = cell(sub, rule, k)
            if len(outs) < 30:
                print(f"  {rule:<10} {k:>6.2f}  too few")
                continue
            rs = [o.r for o in outs]
            fill = sum(o.filled for o in outs) / len(outs)
            won = [o for o in outs if o.filled]
            win = sum(o.r > 0 for o in won) / len(won) if won else 0.0
            m, se = mean_se(rs)
            mark = "  <- shipped" if (rule == "raid" and k == 0.0) else ""
            print(f"  {rule:<10} {k:>6.2f}  {len(outs):>5}  {fill:>6.1%}"
                  f"  {win:>6.1%}  {statistics.fmean(risks):>6.2f}"
                  f"  {m:>+9.3f} ± {se:.3f}  {sum(rs):>+7.1f}{mark}")
        print()


def main():
    rows = load_sync(**FEE)
    print(f"loaded {len(rows)} signals")
    for kind in ("confirmed", "early"):
        table(rows, kind)


if __name__ == "__main__":
    main()
