"""Can we fill more of the setups we already find — and is it worth it?

29% of confirmed setups never touch their entry. The instinct is that those
are wasted signals. They are not wasted, they are DECLINED: an unfilled setup
costs nothing, pays no fee, and scores 0.0. So "improve the fill rate" is only
an improvement if the newly-filled trades carry positive expectancy, and that
is not obvious in either direction:

  the case FOR   a long entry sits BELOW price, so unfilled means price went
                 straight up. The setups that get away are the ones that were
                 right. Chasing them should pay.

  the case AGAINST  the stop stays pinned to the raid extreme. Moving the
                 entry closer to price does not move the stop, so every unit
                 of extra fill costs risk, and R shrinks for every trade —
                 including the 71% that would have filled anyway. You pay the
                 whole book to catch the tail.

Which one wins is an empirical question with a peak somewhere in between, so
this is a sweep, not a filter test. Judge it on the SHAPE of the curve, not on
a single comparison clearing 3 SE.

WHAT IS HELD FIXED
------------------
The signal set. The engine's 2.5-ATR risk cap is applied at the ORIGINAL entry
and then left alone, so every variant scores the same signals and the paired
differences are honest. Widening the entry does breach that cap slightly; the
mean risk change is printed so the size of the cheat is visible.

Everything else — fill window, horizon, target, fee model — comes from the
shared harness.
"""
from __future__ import annotations

import research.env  # noqa: F401  (must precede riptide.config)

import statistics

from research.data import load_sync, atr_at
from research.harness import simulate, mean_se

FEE = dict(fee_maker=0.02, fee_taker=0.06)


def gap_of(row):
    """(top, bot) of the entry gap, or None. Setup carries fvg_time, not a bar."""
    x = row.signal
    j = getattr(x, "fvg_bar", None)
    if j is None:
        idx = {c.t: i for i, c in enumerate(row.candles)}
        j = idx.get(getattr(x, "fvg_time", 0))
    if j is None or j < 2 or j >= len(row.candles):
        return None
    cs = row.candles
    return ((cs[j].l, cs[j - 2].h) if x.is_long else (cs[j - 2].l, cs[j].h))


def resim(row, entry, **kw):
    """Re-score one signal at a different entry. Stop never moves."""
    o = dict(FEE)
    o.update(kw)
    return simulate(row.candles, row.bar, entry, row.signal.stop,
                    row.signal.is_long, **o)


def paired(base, alt):
    """mean difference and its SE over the SAME signals — far tighter than
    comparing two independent means, and the only fair read of a sweep."""
    d = [b - a for a, b in zip(base, alt)]
    if len(d) < 2:
        return 0.0, 0.0
    return statistics.fmean(d), statistics.stdev(d) / len(d) ** 0.5


def line(lab, outs, base_r=None, extra=""):
    rs = [o.r for o in outs]
    fill = sum(o.filled for o in outs) / len(outs) if outs else 0.0
    m, se = mean_se(rs)
    s = f"  {lab:<26} fill {fill:5.1%}   {m:+.3f} ± {se:.3f}   tot {sum(rs):+7.1f}"
    if base_r is not None:
        d, dse = paired(base_r, rs)
        s += f"   {d:+.3f}" + (f" {d / dse:+.1f}SE" if dse else "")
    print(s + extra)
    return rs


# ---------------------------------------------------------------- the ceiling

def ceiling(rows, kind):
    """What the unfilled signals actually did. This bounds every idea below:
    if the ones that get away are losers, no entry tweak can help."""
    sub = [r for r in rows if r.kind == kind]
    miss = [r for r in sub if not r.filled]
    print(f"\n{kind.upper()}: the {len(miss)} of {len(sub)} that never filled")
    if not miss:
        return

    # Did price reach the 2R level (measured from the entry that never
    # filled), without ever coming back to touch the entry? That is a winner
    # the setup identified and the limit order declined to take.
    ran, faded = 0, 0
    for r in miss:
        x, cs = r.signal, r.candles
        risk = abs(x.entry - x.stop)
        tgt = x.entry + (2.0 * risk if x.is_long else -2.0 * risk)
        hit = any((cs[k].h >= tgt) if x.is_long else (cs[k].l <= tgt)
                  for k in range(r.bar + 1, min(r.bar + 61, len(cs))))
        ran += hit
        faded += not hit
    print(f"  reached 2R without us: {ran} ({ran / len(miss):.0%})   "
          f"never got there: {faded}")

    # And if we had simply bought the close of the signal bar instead?
    outs = [resim(r, r.candles[r.bar].c) for r in miss]
    line("market at signal close", outs)


# ------------------------------------------------------------------ the sweeps

def buffer_sweep(rows, kind):
    """Move the limit TOWARD price by k x ATR. Stop unchanged, so risk grows."""
    sub = [r for r in rows if r.kind == kind]
    print(f"\n{kind.upper()}: entry buffer (limit moved toward price)  n={len(sub)}")
    base = None
    for k in (0.0, 0.1, 0.2, 0.3, 0.5, 0.75, 1.0):
        outs, dr = [], []
        for r in sub:
            a = atr_at(r)
            e = r.signal.entry + (a * k if r.signal.is_long else -a * k)
            outs.append(resim(r, e))
            dr.append(abs(e - r.signal.stop) / abs(r.signal.entry - r.signal.stop))
        extra = f"   risk x{statistics.fmean(dr):.2f}"
        rs = line(f"+{k:.2f} ATR" + ("  <- shipped" if k == 0 else ""),
                  outs, base, extra)
        if base is None:
            base = rs


def depth_sweep(rows, kind):
    """The opposite lever: enter DEEPER into the gap. Worse fill, better price.
    f=0 proximal (shipped), 0.5 mid, 1.0 distal — the entry_mode options."""
    sub = [r for r in rows if r.kind == kind and gap_of(r)]
    print(f"\n{kind.upper()}: entry depth into the gap  n={len(sub)}")
    base = None
    for f in (0.0, 0.25, 0.5, 0.75, 1.0):
        outs = []
        for r in sub:
            top, bot = gap_of(r)
            w = top - bot
            e = (top - f * w) if r.signal.is_long else (bot + f * w)
            outs.append(resim(r, e))
        lab = {0.0: "0.00 proximal  <- shipped", 0.5: "0.50 mid",
               1.0: "1.00 distal"}.get(f, f"{f:.2f}")
        rs = line(lab, outs, base)
        if base is None:
            base = rs


def window_sweep(rows, kind):
    """How long to leave the order working. Late fills are stale setups."""
    sub = [r for r in rows if r.kind == kind]
    print(f"\n{kind.upper()}: fill window (bars the limit stays live)  n={len(sub)}")
    base = None
    for n in (5, 10, 15, 20, 30, 40):
        outs = [resim(r, r.signal.entry, fill_bars=n) for r in sub]
        rs = line(f"{n} bars" + ("  <- shipped" if n == 10 else ""), outs, base)
        if base is None:
            base = rs


def split_entry(rows, kind):
    """Two limits, half size each: one at the gap edge, one deeper. The classic
    scale-in. Scored as two independent half positions sharing one stop, which
    is exactly how it would be placed."""
    sub = [r for r in rows if r.kind == kind and gap_of(r)]
    print(f"\n{kind.upper()}: split entry, half and half  n={len(sub)}")
    base = [resim(r, r.signal.entry).r for r in sub]
    m, se = mean_se(base)
    print(f"  {'single at proximal':<26} {m:+.3f} ± {se:.3f}   tot {sum(base):+7.1f}")
    for f in (0.5, 1.0):
        rs = []
        for r in sub:
            top, bot = gap_of(r)
            w = top - bot
            e2 = (top - f * w) if r.signal.is_long else (bot + f * w)
            rs.append(0.5 * resim(r, r.signal.entry).r + 0.5 * resim(r, e2).r)
        m, se = mean_se(rs)
        d, dse = paired(base, rs)
        print(f"  {'half prox + half @' + f'{f:.2f}':<26} {m:+.3f} ± {se:.3f}"
              f"   tot {sum(rs):+7.1f}   {d:+.3f}"
              + (f" {d / dse:+.1f}SE" if dse else ""))


def market_all(rows, kind):
    """The honest version of the ceiling.

    "Market-enter the ones that never filled" scores +0.361 on confirmed —
    better than the filled book. That number is a LOOK-AHEAD: which setups go
    unfilled is knowable only afterwards. The decision actually on offer is
    market-enter EVERY signal, which also takes the 70% that would have filled
    at a worse price and a wider stop. That is the comparison below."""
    sub = [r for r in rows if r.kind == kind]
    print(f"\n{kind.upper()}: market vs limit, on ALL signals  n={len(sub)}")
    base = line("limit at gap  <- shipped", [resim(r, r.signal.entry) for r in sub])
    outs, dr = [], []
    for r in sub:
        e = r.candles[r.bar].c
        outs.append(resim(r, e))
        dr.append(abs(e - r.signal.stop) / abs(r.signal.entry - r.signal.stop))
    # Market on both legs: taker in, taker out.
    line("market at signal close", outs, base,
         f"   risk x{statistics.fmean(dr):.2f}")


def window_splits(rows, kind):
    """Extending the fill window is the one lever that concedes NO price and
    NO risk — the same order, left working longer. So it gets the full
    treatment: what the late fills alone are worth, then the four splits."""
    sub = [r for r in rows if r.kind == kind]
    print(f"\n{kind.upper()}: late fills in isolation  n={len(sub)}")
    for lo, hi in ((10, 15), (15, 20), (20, 30), (30, 40)):
        late = []
        for r in sub:
            o = resim(r, r.signal.entry, fill_bars=hi)
            p = resim(r, r.signal.entry, fill_bars=lo)
            if o.filled and not p.filled:
                late.append(o.r)
        m, se = mean_se(late)
        print(f"  filled in bars {lo + 1}-{hi:<3}  n={len(late):<5} {m:+.3f} ± {se:.3f}"
              f"   tot {sum(late):+6.1f}")

    print(f"\n{kind.upper()}: 10 -> 15 bars, across the splits")
    for lab, pred in (("all", lambda r: True),
                      ("symbols A", lambda r: r.split_symbol == 0),
                      ("symbols B", lambda r: r.split_symbol == 1),
                      ("window 1st half", lambda r: r.split_window),
                      ("window 2nd half", lambda r: not r.split_window)):
        s = [r for r in sub if pred(r)]
        if len(s) < 25:
            print(f"  {lab:<18} too few")
            continue
        a = [resim(r, r.signal.entry, fill_bars=10).r for r in s]
        b = [resim(r, r.signal.entry, fill_bars=15).r for r in s]
        d, dse = paired(a, b)
        print(f"  {lab:<18} n={len(s):<5} {d:+.3f}"
              + (f" {d / dse:+.1f}SE" if dse else ""))


def main():
    rows = load_sync(**FEE)
    print(f"loaded {len(rows)} signals")
    for kind in ("confirmed", "early"):
        ceiling(rows, kind)
        market_all(rows, kind)
        buffer_sweep(rows, kind)
        depth_sweep(rows, kind)
        window_sweep(rows, kind)
        window_splits(rows, kind)
        split_entry(rows, kind)


if __name__ == "__main__":
    main()
