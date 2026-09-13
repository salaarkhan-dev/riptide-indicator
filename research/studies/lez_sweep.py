"""Parameter sweep for Liquidity Entry Zones — stop, target, quality, trend, POI.

Phase 1 (`lez.py`) failed its gate and the plan said no sweep. This runs one
anyway, at the user's explicit direction, so it is built to survive the two
things that make sweeps worthless.

WHY A SWEEP LIES, AND WHAT IS DONE ABOUT IT

(1) BEST-OF-N. Try 360 cells on noise and the best one clears +2.9 SE by
    construction. Quoting it is not a finding, it is arithmetic.

    The fix is not a p-value correction, it is a CONTROL SWEEP. The identical
    360-cell grid is run over RANDOM entries — same symbols, same bars
    available, same stops, same targets, same trend and POI filters, direction
    by coin toss. Whatever the best random cell scores is the noise floor for
    this grid, measured rather than assumed. A LEZ cell only means something if
    it beats that.

(2) A BETTER SHAPE IS NOT A BETTER SIGNAL. Widening the stop raises risk_pct,
    and fee in R is fee/risk_pct, so EVERY strategy improves — including
    coin-flip entries. Phase 1's whole result was that the trade shape costs
    what the fee costs and the signal adds nothing. A sweep that reports
    R/signal will "discover" a wide stop and call it an edge.

    So the headline number here is **EDGE = LEZ − random at the SAME cell**,
    with the same stop, target, trend filter and POI requirement applied to
    both. R/signal is still printed, but it is not what anything is judged on.

(3) THE WINDOW IS SPLIT. Twice the candles are fetched and cut in half. The
    NEWER half is the discovery window — the same ~42 days Phase 1 already
    used, so nothing new is being spent. The OLDER half has never been looked
    at by anything in this project and is where the winner is tested ONCE.

THE SELECTION RULE AND THE BAR, BOTH FIXED BEFORE THE FIRST RUN

    Winner  = the cell with the highest EDGE on discovery, among cells with
              n >= 150. One cell. Not "the best few", not "the best per
              timeframe after looking".
    Passes  = on the HELD-OUT window, that cell has EDGE > 0 AND R/signal > 0.

    Anything else is a fail, including a cell that looks wonderful on discovery
    and merely flat out of sample. Shrinkage is expected; a sign flip is not.

THE GRID
    stop      0.75 / 1.0 / 1.5 / 2.0 / 3.0  x ATR(14)
    target    1.5R / 2R / 3R / 4R
    quality   any / >=75 / >=85      (the score's floor is 60, see STRATEGIES.md)
    trend     any / daily agrees / daily agrees or flat
    POI       off / the raid must land in a daily order block or gap

    360 cells per timeframe. Min5 is not swept: Phase 1 measured its fee at
    0.26 R per losing trade against 0.10 R at Min30, and no cell in this grid
    changes the fee.

    PYTHONPATH=. python3 research/studies/lez_sweep.py
"""
from __future__ import annotations

import research.env  # noqa: F401  (must precede riptide.config)

import asyncio
import random
import statistics
from dataclasses import dataclass

import aiohttp

from riptide.config import CFG, BAR_SECONDS
from riptide.engine import atr_series
from riptide.exchange import list_symbols
from riptide.trend import di_direction, supertrend
from research.harness import mean_se, simulate_market
from research.studies.lez import FEE, P, lez_signals
from research.studies.mtf_grid import (fetch_paged, htf_dir_at, in_poi,
                                       zones_of)

HTF = "Day1"
# Double the Phase 1 window, then split. Min30 2 pages is ~83 days -> two
# halves of ~42; Min15 needs 4 pages for the same calendar span.
TFS = (("Min30", 2), ("Min15", 4))
SYMBOLS = 30
HORIZON_HOURS = 48
RANDOM_MULT = 3           # random entries per LEZ signal, for a tighter floor

STOPS = (0.75, 1.0, 1.5, 2.0, 3.0)
TARGETS = (1.5, 2.0, 3.0, 4.0)
QUALITY = ((0.0, "any"), (75.0, "Q>=75"), (85.0, "Q>=85"))
TRENDS = (("any", None), ("agrees", "with"), ("agrees/flat", "notagainst"))
POIS = ((False, "POI off"), (True, "POI required"))
MIN_N = 150               # a cell below this cannot be the winner


@dataclass
class Row:
    """One candidate trade, with everything a filter might ask of it, and its
    outcomes precomputed for every (stop, target) in the grid.

    Precomputed because a cell is then a filtered mean rather than a
    re-simulation: 360 cells over the same rows is 20 distinct simulations per
    row, not 360.
    """
    is_long: bool
    entry: float
    score: float
    htf_dir: int
    poi: bool
    outs: dict          # (stop_atr, target_r) -> Outcome
    risk: dict          # (stop_atr,) -> risk as a % of entry


def keep(r: Row, qmin, trend, need_poi) -> bool:
    if r.score < qmin:
        return False
    if need_poi and not r.poi:
        return False
    want = 1 if r.is_long else -1
    if trend == "with" and r.htf_dir != want:
        return False
    if trend == "notagainst" and r.htf_dir == -want:
        return False
    return True


def cell(rows, stop_atr, target_r, qmin, trend, need_poi):
    """(n, mean, se, win, risk%) for one grid cell."""
    sel = [r for r in rows if keep(r, qmin, trend, need_poi)]
    rs = [r.outs[(stop_atr, target_r)].r for r in sel
          if (stop_atr, target_r) in r.outs]
    if not rs:
        return 0, 0.0, 0.0, 0.0, 0.0
    m, se = mean_se(rs)
    risk = statistics.fmean(r.risk[stop_atr] for r in sel
                            if stop_atr in r.risk) if sel else 0.0
    return len(rs), m, se, sum(x > 0 for x in rs) / len(rs), risk


def build(cs, bar, is_long, entry, atr_v, score, hcs, hst, hdi, zones, hstep,
          horizon):
    """One Row, or None when the horizon runs off the end of the data.

    The drop is decided by POSITION only — never by how the trade turned out —
    so it cannot bias the sample.
    """
    if atr_v <= 0 or bar + 1 + horizon > len(cs) or entry <= 0:
        return None
    when = cs[bar].t
    outs, risk = {}, {}
    for sa in STOPS:
        dist = atr_v * sa
        stop = entry - dist if is_long else entry + dist
        if stop <= 0:
            continue
        risk[sa] = 100 * dist / entry
        for tr in TARGETS:
            o = simulate_market(cs, bar, entry, stop, is_long, target_r=tr,
                                horizon_bars=horizon, **FEE)
            if o is not None:
                outs[(sa, tr)] = o
    if not outs:
        return None
    # The POI test uses the RAID extreme, not the entry: it is the sweep that
    # has to land in the daily zone, the same convention riptide/scanner.py
    # uses. `in_poi` is the fixed version — a zone is not knowable until the
    # bar that formed it has CLOSED.
    raid = cs[bar].l if is_long else cs[bar].h
    return Row(is_long=is_long, entry=entry, score=score,
               htf_dir=htf_dir_at(hcs, hst, hdi, when),
               poi=in_poi(zones, when, raid, is_long, hstep),
               outs=outs, risk=risk)


async def collect(sess, syms, tf, pages, hcache):
    """Rows for both halves of the window, for LEZ signals and for the random
    control, in one pass over the candles."""
    horizon = max(1, HORIZON_HOURS * 3600 // BAR_SECONDS[tf])
    hstep = BAR_SECONDS[HTF]
    out = {("disc", "lez"): [], ("disc", "rnd"): [],
           ("held", "lez"): [], ("held", "rnd"): []}
    days = []

    for n, sym in enumerate(syms):
        try:
            cs = await fetch_paged(sess, sym, tf, pages)
            if sym not in hcache:
                hcache[sym] = await fetch_paged(sess, sym, HTF, 1)
            hcs = hcache[sym]
        except Exception:
            continue
        if len(cs) < 800 or len(hcs) < 60:
            continue
        days.append((cs[-1].t - cs[0].t) / 86400)
        hst, hdi = supertrend(hcs), di_direction(hcs)
        zones = zones_of(hcs, atr_series(hcs, CFG.atr_len))
        atr = atr_series(cs, P.atr_len)
        cut = len(cs) // 2                       # older half is held out
        rnd = random.Random(1000 + n)

        sigs = lez_signals(cs)
        n_by_half = {"held": 0, "disc": 0}
        for s in sigs:
            half = "held" if s.bar < cut else "disc"
            r = build(cs, s.bar, s.is_long, s.entry, s.atr, s.score,
                      hcs, hst, hdi, zones, hstep, horizon)
            if r is not None:
                out[(half, "lez")].append(r)
                n_by_half[half] += 1

        # The control, matched per symbol AND per half so the floor is built
        # on the same market, not on a different slice of it.
        for half, lo, hi in (("held", 60, cut), ("disc", cut, len(cs))):
            want = n_by_half[half] * RANDOM_MULT
            hi = min(hi, len(cs) - horizon - 2)
            if hi <= lo or want <= 0:
                continue
            for _ in range(want):
                i = rnd.randrange(lo, hi)
                r = build(cs, i, rnd.random() < 0.5, cs[i].c, atr[i], 0.0,
                          hcs, hst, hdi, zones, hstep, horizon)
                if r is not None:
                    out[(half, "rnd")].append(r)
    return out, days


def grid(lez_rows, rnd_rows):
    """Every cell, scored for both LEZ and the control, sorted by EDGE."""
    res = []
    for sa in STOPS:
        for tr in TARGETS:
            for qmin, qlab in QUALITY:
                for tlab, tkey in TRENDS:
                    for need, plab in POIS:
                        n, m, se, win, risk = cell(lez_rows, sa, tr, qmin,
                                                   tkey, need)
                        # The control gets the same stop, target, trend and
                        # POI. Quality has no analogue for a coin toss, which
                        # is the point: the question is whether trading only
                        # high-quality signals beats trading at random under
                        # otherwise identical conditions.
                        rn, rm, rse, _, _ = cell(rnd_rows, sa, tr, 0.0,
                                                 tkey, need)
                        if not n or not rn:
                            continue
                        res.append(dict(
                            key=(sa, tr, qmin, tkey, need),
                            lab=f"{sa:g}ATR {tr:g}R {qlab:<6} "
                                f"{tlab:<11} {plab}",
                            n=n, m=m, se=se, win=win, risk=risk,
                            rn=rn, rm=rm, rse=rse,
                            edge=m - rm, edge_se=(se ** 2 + rse ** 2) ** 0.5))
    return sorted(res, key=lambda c: -c["edge"])


HEAD = (f"  {'cell':<44}{'n':>6}{'win':>6}{'risk':>7}{'R/sig':>9}"
        f"{'random':>9}{'EDGE':>9}{'SE':>7}")


def show(c):
    print(f"  {c['lab']:<44}{c['n']:>6}{c['win']:>6.0%}{c['risk']:>6.2f}%"
          f"{c['m']:>+9.3f}{c['rm']:>+9.3f}{c['edge']:>+9.3f}"
          f"{c['edge'] / c['edge_se'] if c['edge_se'] else 0:>+6.1f}")


def one_at_a_time(rows, rnd):
    """Descriptive, and the only honest place to look at single knobs: five
    families of a handful of cells each, rather than one family of 360."""
    base = dict(stop_atr=1.5, target_r=3.0, qmin=0.0, trend=None, poi=False)

    def row(lab, **kw):
        a = {**base, **kw}
        n, m, se, win, risk = cell(rows, a["stop_atr"], a["target_r"],
                                   a["qmin"], a["trend"], a["poi"])
        rn, rm, _, _, _ = cell(rnd, a["stop_atr"], a["target_r"], 0.0,
                               a["trend"], a["poi"])
        if n < 25 or rn < 25:
            print(f"    {lab:<24} n={n} too few")
            return
        print(f"    {lab:<24}{n:>6}{win:>6.0%}{risk:>6.2f}%{m:>+9.3f}"
              f"{rm:>+9.3f}{m - rm:>+9.3f}")

    print(f"\n  ONE KNOB AT A TIME, from the shipped defaults")
    print(f"    {'':<24}{'n':>6}{'win':>6}{'risk':>7}{'R/sig':>9}"
          f"{'random':>9}{'EDGE':>9}")
    print("   -- stop, ATR multiple --")
    for sa in STOPS:
        row(f"stop {sa:g} ATR", stop_atr=sa)
    print("   -- target --")
    for tr in TARGETS:
        row(f"target {tr:g}R", target_r=tr)
    print("   -- quality score (floor 60) --")
    for q, lab in QUALITY:
        row(lab, qmin=q)
    print("   -- daily trend --")
    for lab, t in TRENDS:
        row(lab, trend=t)
    print("   -- daily POI --")
    for need, lab in POIS:
        row(lab, poi=need)


def report(tf, data, days):
    print(f"\n{'=' * 104}\n{tf}   "
          f"{statistics.median(days):.0f} days total across {len(days)} "
          f"symbols, split in half\n{'=' * 104}")
    d_lez, d_rnd = data[("disc", "lez")], data[("disc", "rnd")]
    h_lez, h_rnd = data[("held", "lez")], data[("held", "rnd")]
    print(f"  discovery (newer half): {len(d_lez)} signals, "
          f"{len(d_rnd)} control    held out (older half): "
          f"{len(h_lez)} signals, {len(h_rnd)} control")
    if len(d_lez) < MIN_N:
        print("  too few discovery signals to sweep")
        return

    one_at_a_time(d_lez, d_rnd)

    g = grid(d_lez, d_rnd)
    # THE FLOOR MUST BE TWO INDEPENDENT SAMPLES OF NOISE, NOT ONE COMPARED TO
    # ITSELF. grid(rnd, rnd) returns an edge of exactly zero in every cell —
    # a floor of +0.000 that any result clears, which would have made this
    # whole control decorative. Split the control pool in half instead and let
    # one half play the strategy against the other; the best of 360 such cells
    # is what "best of 360" is worth when there is provably nothing there.
    rnd_a = d_rnd[0::2]
    rnd_b = d_rnd[1::2]
    rg = grid(rnd_a, rnd_b)
    print(f"\n  THE GRID on the discovery half — {len(g)} cells, best 12 by EDGE")
    print(HEAD)
    for c in g[:12]:
        show(c)

    # The noise floor, measured. The control sweep asks the same 360 questions
    # of coin flips; whatever its best cell scores is what "best of 360" is
    # worth before any skill is involved.
    # Halving the pool halves the counts, so the eligibility bar halves too.
    floor = [c for c in rg if c["n"] >= MIN_N // 2]
    if floor:
        b = max(floor, key=lambda c: c["edge"])
        top = sorted((c["edge"] for c in floor), reverse=True)
        print(f"\n  NOISE FLOOR — the same 360 questions asked of coin flips,"
              f" one half against the other:")
        print(f"    best of {len(floor)} cells       EDGE {b['edge']:+.3f}"
              f"   ({b['lab'].strip()}, n={b['n']})")
        print(f"    5th best                  EDGE {top[4]:+.3f}"
              if len(top) > 4 else "")
        print(f"    a LEZ cell at or below {b['edge']:+.3f} is this sweep "
              f"finding nothing.")

    elig = [c for c in g if c["n"] >= MIN_N]
    if not elig:
        print(f"\n  no cell reaches n >= {MIN_N}; nothing to hold out")
        return
    w = elig[0]
    print(f"\n  WINNER by the pre-declared rule (highest EDGE, n >= {MIN_N}):")
    print(HEAD)
    show(w)
    if floor and w["edge"] <= b["edge"]:
        print(f"    ^ this does NOT clear the noise floor of "
              f"{b['edge']:+.3f}. The held-out test below is run anyway, "
              f"but a cell that a coin flip matches is not a candidate.")

    sa, tr, q, t, poi = w["key"]
    n, m, se, win, risk = cell(h_lez, sa, tr, q, t, poi)
    rn, rm, _, _, _ = cell(h_rnd, sa, tr, 0.0, t, poi)
    print(f"\n  HELD OUT — the older half, never looked at before now. "
          f"ONE cell, one shot.")
    if n < 25 or rn < 25:
        print(f"    n={n} control={rn}: too few to read")
        return
    _, _, rsehold, _, _ = cell(h_rnd, sa, tr, 0.0, t, poi)
    edge = m - rm
    edge_se = (se ** 2 + rsehold ** 2) ** 0.5
    print(f"    {'n':<12}{n}")
    print(f"    {'win':<12}{win:.0%}")
    print(f"    {'R/signal':<12}{m:+.3f} ± {se:.3f}")
    print(f"    {'random':<12}{rm:+.3f}")
    print(f"    {'EDGE':<12}{edge:+.3f} ± {edge_se:.3f}"
          + (f"   {edge / edge_se:+.1f} SE" if edge_se else ""))
    ok = edge > 0 and m > 0
    print(f"    => {'PASSES' if ok else 'FAILS'} — the bar was EDGE > 0 AND "
          f"R/signal > 0, fixed before the run")
    print(f"    discovery said {w['edge']:+.3f} edge / {w['m']:+.3f} R; "
          f"held out says {edge:+.3f} / {m:+.3f}")


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = (await list_symbols(sess))[:SYMBOLS]
        print(f"Liquidity Entry Zones — parameter sweep\n"
              f"{len(syms)} symbols · grid of "
              f"{len(STOPS) * len(TARGETS) * len(QUALITY) * len(TRENDS) * len(POIS)}"
              f" cells · every cell measured against the SAME cell run on "
              f"random entries")
        hcache: dict = {}
        for tf, pages in TFS:
            data, days = await collect(sess, syms, tf, pages, hcache)
            if days:
                report(tf, data, days)


if __name__ == "__main__":
    asyncio.run(main())
