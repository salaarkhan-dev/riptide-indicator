"""How long should the limit order stay live before we call the setup stale?

Shipped is 10 bars (5 hours on 30m). The coarse sweep in fills.py compared
5/10/15/20/30/40 against the 5-bar baseline, which made 15 look like a +2.0 SE
improvement when measured against 10 it is +0.6. This is the fine version,
every value from 2 to 20, each one PAIRED against the shipped 10.

Two things are reported that the coarse sweep did not:

  WIN RATE   asked for directly. Note that win rate and R/signal can move in
             opposite directions here: a longer window adds trades that fill
             late, and those can win often while returning little, or the
             reverse. Only R/signal pays.

  PER SYMBOL because "what suits best across multiple symbols" is the actual
             question, and the honest answer usually is not "symbol X wants
             14". With ~10 confirmed signals per symbol, a per-symbol argmax
             is fitting noise, and the way to show that is to print the
             argmaxes and let them disagree.
"""
from __future__ import annotations

import research.env  # noqa: F401  (must precede riptide.config)

import statistics
from collections import defaultdict

from research.data import load_sync
from research.harness import simulate, mean_se

FEE = dict(fee_maker=0.02, fee_taker=0.06)
WAITS = list(range(2, 21))
SHIPPED = 10


def score(rows, n):
    return [simulate(r.candles, r.bar, r.signal.entry, r.signal.stop,
                     r.signal.is_long, fill_bars=n, **FEE) for r in rows]


def paired(a, b):
    d = [y - x for x, y in zip(a, b)]
    if len(d) < 2:
        return 0.0, 0.0
    return statistics.fmean(d), statistics.stdev(d) / len(d) ** 0.5


def sweep(rows, kind):
    sub = [r for r in rows if r.kind == kind]
    print(f"\n{'=' * 74}\n{kind.upper()}  n={len(sub)}   every value paired "
          f"against the shipped {SHIPPED}\n{'=' * 74}")
    print(f"  {'wait':>4}  {'fill':>6}  {'win':>6}  {'R/signal':>16}"
          f"  {'total R':>8}   vs {SHIPPED}")
    base = None
    curve = {}
    for n in WAITS:
        outs = score(sub, n)
        rs = [o.r for o in outs]
        curve[n] = sum(rs)
        fill = sum(o.filled for o in outs) / len(outs)
        won = [o for o in outs if o.filled]
        win = sum(o.r > 0 for o in won) / len(won) if won else 0.0
        m, se = mean_se(rs)
        tail = ""
        if base is not None:
            d, dse = paired(base, rs)
            tail = f"   {d:+.3f}" + (f" {d / dse:+.1f}SE" if dse else "")
        if n == SHIPPED:
            base = rs
            tail = "   <- shipped"
        print(f"  {n:>4}  {fill:>6.1%}  {win:>6.1%}  {m:>+9.3f} ± {se:.3f}"
              f"  {sum(rs):>+8.1f}{tail}")
    # base was set mid-loop, so the rows before it printed no comparison.
    # Re-print those now that it exists.
    print(f"\n  the values below {SHIPPED}, paired properly:")
    for n in [w for w in WAITS if w < SHIPPED]:
        rs = [o.r for o in score(sub, n)]
        d, dse = paired(base, rs)
        print(f"  {n:>4}  {d:+.3f}" + (f" {d / dse:+.1f}SE" if dse else ""))
    return curve


def per_symbol(rows, kind):
    """Each symbol's own best wait, and what that argmax is worth out of
    sample. If the argmaxes scatter, the per-symbol tuning is noise."""
    sub = [r for r in rows if r.kind == kind]
    by = defaultdict(list)
    for r in sub:
        by[r.symbol].append(r)
    print(f"\n{kind.upper()}: each symbol's own best wait")
    print(f"  {'symbol':<14} {'n':>4}  {'best':>4}  {'R at best':>10}"
          f"  {'R at ' + str(SHIPPED):>10}")
    best_list = []
    for sym, rs in sorted(by.items()):
        if len(rs) < 10:
            continue
        tot = {n: sum(o.r for o in score(rs, n)) for n in WAITS}
        b = max(tot, key=tot.get)
        best_list.append(b)
        print(f"  {sym:<14} {len(rs):>4}  {b:>4}  {tot[b]:>+10.1f}"
              f"  {tot[SHIPPED]:>+10.1f}")
    if best_list:
        print(f"\n  argmax spread: min {min(best_list)}  max {max(best_list)}"
              f"  median {statistics.median(best_list)}"
              f"  stdev {statistics.pstdev(best_list):.1f}")
        print("  A tight cluster would mean the optimum is real. A spread "
              "across\n  most of the tested range means each symbol is "
              "fitting its own noise.")


def main():
    rows = load_sync(**FEE)
    print(f"loaded {len(rows)} signals")
    for kind in ("confirmed", "early"):
        sweep(rows, kind)
        per_symbol(rows, kind)


if __name__ == "__main__":
    main()
