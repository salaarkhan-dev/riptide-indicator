"""Should the target be the next pool of liquidity instead of a fixed 2R?

THE ONE DIMENSION NOBODY HAS TESTED. This project has swept six engine
parameters, twelve entry locations, twenty-five exit policies, four targets,
order blocks, breakers, sessions, pool sources, and a pivot-pool grid. Every
exit test used a FIXED multiple of risk. Not one asked whether the target
should depend on the chart.

AND THE EXIT IS DEMONSTRABLY THE BIGGEST LEVER IN THE SYSTEM. `exit_grid.py`
showed the same trades paying 65% wins for -3% return or 39% wins for +20%,
purely by moving the target. So the exit is where the money is decided; it has
simply only ever been moved by a constant.

2R IS ARBITRARY AND THE CHART SAYS SO. A long taken with the nearest unswept
high sitting 0.7R away is a different trade from one with clear air to 6R, and
a fixed target prices them identically — booking the first at a level price
must fight through, and abandoning the second well short of where it was going.
"Take profit into the liquidity above" is the oldest idea in this vocabulary
and it is the one the engine already has the machinery for: the pools are built
from pivots, and the same pivot primitive the pool builder uses is public.

WHAT AN OPPOSING POOL IS, HERE. For a long, the nearest confirmed pivot HIGH
above the entry that price has not since traded through — buy-side liquidity,
in the vocabulary. Nearest is the INTERNAL target, the one after it the
EXTERNAL target. Confirmed strictly: a pivot needs `pivot_right` bars after it
to exist, so only pivots whose right side closed at or before the signal bar
are eligible. A study that used the next pivot as a target when that pivot had
not formed yet would be reading the future, and would look wonderful.

PRE-REGISTERED, BEFORE THE FIRST NUMBER

  PRIMARY   A liquidity target must beat the deployed plain 2R on the HELD-OUT
            half, on R per bet, by 2 SE. Same entries, same stops, same signals
            — only the exit differs, so this is a clean paired comparison and
            nothing else can explain a difference.

  SECOND    It must reproduce on Hour4, which carries 333 days against the 42
            every other study here runs on. `pivot_filter.py` was killed by
            exactly this check, and it is the strongest one available.

  REPORTED REGARDLESS: win rate, R per bet, and how far away the pool actually
  sits, because a target that lands at 0.8R will raise the win rate and lose
  money and that must be visible rather than inferred.

  UNIT: one bet per candle close.

  EXPECTATION: the nearest pool beats 2R on WIN RATE and loses on R, because it
  is mostly a closer target — the same trade `exit_grid.py` already priced. The
  interesting cell is the FLOOR, which only takes the trade when the pool is far
  enough away to be worth it, and that is a filter as much as an exit. Recorded
  so it cannot be revised.

    PYTHONPATH=. RIPTIDE_MIN_GRADE=B python3 research/studies/liquidity_target.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import statistics                                       # noqa: E402
from collections import defaultdict                     # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import CFG, MIN_GRADE, TRACK_TARGET_R  # noqa: E402
from riptide.engine import (grade_of, is_pivot_high,    # noqa: E402
                            is_pivot_low, run_engine)
from riptide.exchange import fetch_candles, list_symbols  # noqa: E402
from riptide.trend import di_at, direction_at, poi_at   # noqa: E402
from research.harness import mean_se, simulate          # noqa: E402

BANDS = "ABCD"
CUT = BANDS.index(MIN_GRADE)
TFS = ("Min30", "Hour4")
LOOK = 300          # bars back to search for an unswept pool
MAX_R = 10.0        # a target further than this is not a target, it is a hope


def pools_at(cs, bar, is_long, left, right):
    """Unswept opposing pools above (long) or below (short) `bar`, nearest first.

    ONLY PIVOTS THAT HAD ALREADY FORMED. A pivot at index i is not confirmed
    until bar i + right has closed, so the search stops at bar - right. Using a
    pivot whose right shoulder is still forming would target a level the chart
    could not yet show, and every such study looks brilliant.

    UNSWEPT means price has not traded through it since. A high that has already
    been taken is not liquidity any more, it is history — and it is exactly the
    level this engine would have raided rather than aimed at.
    """
    out = []
    px = cs[bar].c
    lo = max(left, bar - LOOK)
    for i in range(bar - right, lo, -1):
        if is_long:
            if not is_pivot_high(cs, i, left, right):
                continue
            lvl = cs[i].h
            if lvl <= px:
                continue
            if max(cs[k].h for k in range(i + 1, bar + 1)) >= lvl:
                continue                       # already swept, not liquidity
        else:
            if not is_pivot_low(cs, i, left, right):
                continue
            lvl = cs[i].l
            if lvl >= px:
                continue
            if min(cs[k].l for k in range(i + 1, bar + 1)) <= lvl:
                continue
        out.append(lvl)
    out.sort(reverse=not is_long)
    return out


# Each policy maps (entry, stop, is_long, pools) -> target in R, or None to skip.
def _r_of(entry, stop, is_long, lvl):
    risk = abs(entry - stop)
    return ((lvl - entry) if is_long else (entry - lvl)) / risk if risk else 0.0


def plain(_e, _s, _l, _p, r=TRACK_TARGET_R):
    return r


def internal(e, s, l, p):
    """Nearest opposing pool. The classic 'take profit into liquidity'."""
    if not p:
        return None
    r = _r_of(e, s, l, p[0])
    return r if 0 < r <= MAX_R else None


def external(e, s, l, p):
    """The pool BEYOND the nearest — internal liquidity taken, then external."""
    if len(p) < 2:
        return None
    r = _r_of(e, s, l, p[1])
    return r if 0 < r <= MAX_R else None


def floored(e, s, l, p, floor=2.0):
    """Nearest pool, but only when it is at least `floor` away.

    THE INTERESTING ONE, and it is a filter as much as an exit: it declines the
    trade whose nearest liquidity is too close to pay for the risk, and takes
    the full distance when there is room. That is the ICT reading of the idea —
    "is there liquidity worth reaching for" — rather than merely a nearer target.
    """
    if not p:
        return None
    r = _r_of(e, s, l, p[0])
    return r if floor <= r <= MAX_R else None


POLICIES = (
    ("plain 2R (deployed)", plain),
    ("nearest pool", internal),
    ("pool beyond it", external),
    ("nearest pool, floor 1.5R", lambda e, s, l, p: floored(e, s, l, p, 1.5)),
    ("nearest pool, floor 2R", lambda e, s, l, p: floored(e, s, l, p, 2.0)),
    ("nearest pool, floor 3R", lambda e, s, l, p: floored(e, s, l, p, 3.0)),
    ("2R, but only if a pool is 2R+ away",
     lambda e, s, l, p: (TRACK_TARGET_R
                         if floored(e, s, l, p, 2.0) is not None else None)),
)


class Row:
    __slots__ = ("t", "r", "held", "tgt")


async def collect(sess, candles, kind):
    """Every SENT signal with its opposing pools, scored under every policy."""
    out = defaultdict(list)
    dists = []
    for sym, cs in candles.items():
        early = []
        try:
            setups = run_engine(sym, cs, CFG, early_out=early)
        except Exception:
            continue
        sigs, key = ((setups, "detected_time") if kind == "confirmed"
                     else (early, "fvg_time"))
        idx = {c.t: i for i, c in enumerate(cs)}
        mid = cs[len(cs) // 2].t
        for x in sigs:
            i = idx.get(getattr(x, key))
            if i is None or x.entry <= 0 or abs(x.entry - x.stop) <= 0:
                continue
            when = getattr(x, key)
            poi = await poi_at(sess, sym, when, x.stop, x.is_long,
                               fetch_candles)
            poi = True if poi is None else bool(poi)
            if not poi:
                continue
            d = await direction_at(sess, sym, when, fetch_candles)
            di = await di_at(sess, sym, when, fetch_candles)
            if BANDS.index(grade_of(kind == "early", poi, d or 0, x.is_long,
                                    di or 0)[0]) > CUT:
                continue
            pl = pools_at(cs, i, x.is_long, CFG.pivot_left, CFG.pivot_right)
            if pl:
                dists.append(_r_of(x.entry, x.stop, x.is_long, pl[0]))
            for lab, fn in POLICIES:
                tgt = fn(x.entry, x.stop, x.is_long, pl)
                if tgt is None:
                    continue
                o = simulate(cs, i, x.entry, x.stop, x.is_long, target_r=tgt)
                if not o.filled or o.exit_bar is None:
                    continue
                r = Row()
                r.t, r.r, r.held, r.tgt = when, o.r, when < mid, tgt
                out[lab].append(r)
    return out, dists


def bets(rows):
    bybar = defaultdict(list)
    for r in rows:
        bybar[r.t].append(r.r)
    return [statistics.fmean(v) for v in bybar.values()]


def stat(rows):
    b = bets(rows)
    if len(b) < 15:
        return None
    m, se = mean_se(b)
    return dict(n=len(b), win=sum(1 for r in b if r > 0) / len(b), m=m, se=se,
                tot=sum(b), tgt=statistics.fmean(r.tgt for r in rows))


def panel(title, byp, days):
    print(f"\n{title}")
    print(f"  {'policy':<36}{'/day':>6}{'bets':>6}{'tgtR':>6}{'win':>6}"
          f"{'R/bet':>9}{'SE':>7}{'total':>8}   vs deployed")
    base = stat(byp.get("plain 2R (deployed)", []))
    for lab, _ in POLICIES:
        s = stat(byp.get(lab, []))
        if not s:
            print(f"  {lab:<36}   too few")
            continue
        cmp = ""
        if base and lab != "plain 2R (deployed)":
            d = s["m"] - base["m"]
            se = (s["se"] ** 2 + base["se"] ** 2) ** 0.5
            cmp = f"{d:>+8.3f}  {d / se if se else 0:>+5.1f} SE"
        print(f"  {lab:<36}{s['n'] / days:>6.1f}{s['n']:>6}{s['tgt']:>6.1f}"
              f"{s['win']:>6.0%}{s['m']:>+9.3f}{s['se']:>7.3f}{s['tot']:>+8.1f}"
              f"{cmp}")


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = await list_symbols(sess)
        for tf in TFS:
            cands = {}
            for sym in syms:
                try:
                    cs = await fetch_candles(sess, sym, tf)
                except Exception:
                    continue
                if len(cs) >= 300:
                    cands[sym] = cs
            if not cands:
                continue
            days = statistics.median((cs[-1].t - cs[0].t) / 86400
                                     for cs in cands.values())
            fresh = "  (FRESH — 333 days, the out-of-sample check)" \
                if tf == "Hour4" else ""
            print(f"\n{'=' * 104}\n{tf} · {len(cands)} symbols · {days:.0f} "
                  f"days · POI required · grade {MIN_GRADE}+{fresh}\n{'=' * 104}")
            for kind in ("confirmed", "early"):
                byp, dists = await collect(sess, cands, kind)
                if dists:
                    q = sorted(dists)
                    print(f"\n  {tf} {kind} — where the nearest unswept pool "
                          f"actually sits: median {q[len(q) // 2]:.1f}R · "
                          f"{sum(1 for d in q if d < 2) / len(q):.0%} of them "
                          f"closer than 2R")
                panel(f"{tf} {kind} — FULL WINDOW", byp, days)
                panel(f"{tf} {kind} — HELD OUT (older half)",
                      {k: [r for r in v if r.held] for k, v in byp.items()},
                      days / 2)

    print(f"\nPRE-REGISTERED: a liquidity target must beat plain 2R on the "
          f"HELD-OUT half by\n2 SE, AND reproduce on Hour4. Same entries, same "
          f"stops, same signals — only the\nexit differs, so nothing but the "
          f"exit can explain a difference.")


if __name__ == "__main__":
    asyncio.run(main())
