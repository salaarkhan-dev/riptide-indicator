"""The last four items: pool compression, daily POI granularity, FVG size and
FVG ordinal.

    7   pool compression     span between the cluster's outermost pivots / ATR
    9   daily POI depth/age  how far into the zone the raid landed, and how old
    10  daily FVG vs OB      which KIND of zone it was, and whether both
    11  FVG size             the entry gap's own size / ATR
    12  first FVG vs later   which gap in the displacement produced this setup

ONE ENGINE CHANGE WAS NEEDED AND IT IS INERT. `Setup` now carries `span`, the
price distance between a cluster's highest and lowest pivot, because nothing
downstream could otherwise reconstruct it — the cluster is gone by the time a
setup exists. It is a defaulted field assigned at construction and read by
nothing in production. Verified by replaying BTC, SOL and ONDO through the
pre-change engine: 104, 115 and 100 setups with identical entry/stop/direction
hashes. If that ever stops being true, this file is why to look.

THE OTHER THREE NEEDED NO CHANGE AT ALL. POI type, depth and age come from
re-deriving `daily_zones` with a label attached, which is a reimplementation of
a pure function rather than a modification of one. FVG size is the gap on the
signal bar, straight off the candles. And the FVG ORDINAL falls out of the data
already there: the engine emits one Setup per gap in a leg, so setups sharing a
symbol, MSS bar and direction ARE gap 1, 2, 3 of that displacement once sorted
by time.

READ EVERY ROW AGAINST THE MDE PRINTED IN THE HEADER. `power.py` and
`tier1.py` between them established that these bucket comparisons need about
0.15 R on the full stream and 0.35 on confirmed alone, and that eight of nine
such hypotheses came in under it.

    PYTHONPATH=. RIPTIDE_MIN_GRADE=B RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/zones.py

RESULT, 11 Sep 2026 — 594 confirmed trades, 492 bets, MDE 0.350

    item 7   pool span / ATR          spread +0.175   unreadable
    item 11  entry FVG size / ATR     spread +0.112   unreadable
    item 9   depth into daily POI     spread +0.146   unreadable
    item 9b  daily POI age            spread +0.101   unreadable

  Four more under the noise floor, which makes twelve of thirteen bucket
  hypotheses across this file and `tier1.py`. Several again show the tempting
  shape — the deepest POI bucket is the best at +0.185 with a bootstrap clear
  of zero, and it means nothing at half the MDE.

  ITEM 12 CANNOT BE TESTED ON THE BOT, AND THE REASON IS THE PLAN'S OWN
  WARNING TURNED BACK ON IT. All 594 trades are gap number ONE; there is no
  second gap to compare against, in any leg, in a year. The plan reads
  `maxFvgPerSetup` out of the PINE source and infers that the engine scans a
  leg for several gaps — and the Pine does. `riptide/engine.py` does not: it
  sets `c.done = True` on the same line it appends the Setup, so a cluster
  emits exactly one, the first that qualifies. The bot already takes the first
  gap always. "First FVG vs best FVG" is a question about the indicator, not
  about the thing the 333-day report measures, which is exactly the Pine-is-
  not-the-bot distinction the plan itself raises at the end.

  ITEM 10 POINTS THE OPPOSITE WAY TO ITS PREDICTION.

      daily FVG    410 tr  39% win  +0.095   bootstrap 5th +0.002
      daily OB     131 tr  37% win  +0.047   bootstrap 5th -0.118
      BOTH          53 tr  32% win  -0.012   bootstrap 5th -0.294

  The plan expects BOTH to be "much smaller but potentially much higher
  quality". It is much smaller and it is the WORST of the three, at a 32% win
  rate against 39% for a plain daily gap. At 53 trades against an MDE of 0.350
  this settles nothing on its own — but a specific prediction was made and the
  data leans against it rather than for it, and that is worth more than another
  cell that merely failed to separate.
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import statistics                                       # noqa: E402
from collections import defaultdict                     # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import BAR_SECONDS, CFG, TREND_INTERVAL, TRACK_TARGET_R  # noqa: E402
from riptide.engine import (POI_MAX_AGE_BARS, atr_series, grade_of,  # noqa: E402
                            run_engine)
from riptide.exchange import fetch_candles, list_symbols  # noqa: E402
from riptide.trend import di_at, direction_at, poi_at  # noqa: E402
from research.deep import load_universe                 # noqa: E402
from research.harness import mean_se, simulate          # noqa: E402
from research.studies.power import mde                  # noqa: E402
from research.studies.report import bets_of             # noqa: E402
from research.studies.survivor import symbol_bootstrap  # noqa: E402
from research.studies.tier1 import cellstat, hypothesis  # noqa: E402

DAYS = 333
INTERVAL = "Min30"


def labelled_zones(cs, atr):
    """daily_zones, but each zone says whether it is a GAP or an ORDER BLOCK.

    A reimplementation rather than an edit: `riptide.engine.daily_zones` is on
    the production path and returns a 4-tuple that several callers unpack
    positionally. Widening it to carry a label would be a change to production
    for a research convenience, which is exactly what this whole exercise is
    meant not to do.
    """
    out = []
    for j in range(2, len(cs)):
        a = atr[j] if j < len(atr) else 0.0
        if a <= 0:
            continue
        if cs[j].l > cs[j - 2].h:
            out.append((cs[j].t, True, cs[j - 2].h, cs[j].l, "FVG"))
        elif cs[j].h < cs[j - 2].l:
            out.append((cs[j].t, False, cs[j].h, cs[j - 2].l, "FVG"))
        if cs[j].c - cs[j].o > a and cs[j - 1].c < cs[j - 1].o:
            out.append((cs[j].t, True, cs[j - 1].l, cs[j - 1].h, "OB"))
        elif cs[j].o - cs[j].c > a and cs[j - 1].c > cs[j - 1].o:
            out.append((cs[j].t, False, cs[j - 1].l, cs[j - 1].h, "OB"))
    return out


def poi_detail(zones, when, price, is_long, step):
    """(kinds hit, youngest age in days, depth into the zone) or None.

    Depth is 0 at the edge the raid came from and 1 at the far side, measured
    in the trade's own direction, so a long and a short are comparable.
    """
    hits = []
    for t, bull, lo, hi, kind in zones:
        if (t + step <= when and bull == is_long and lo <= price <= hi
                and when - t <= POI_MAX_AGE_BARS * step):
            hits.append((kind, (when - t) // step, lo, hi))
    if not hits:
        return None
    kinds = {k for k, _, _, _ in hits}
    kind = "BOTH" if len(kinds) > 1 else next(iter(kinds))
    age = min(a for _, a, _, _ in hits)
    _, _, lo, hi = min(hits, key=lambda h: h[1])
    rng = hi - lo
    if rng <= 0:
        depth = 0.5
    else:
        depth = (hi - price) / rng if is_long else (price - lo) / rng
    return kind, age, max(0.0, min(1.0, depth))


class Z:
    __slots__ = ("sym", "t", "r", "kind", "span_atr", "fvg_atr", "ordinal",
                 "poi_kind", "poi_age", "poi_depth")


async def collect(sess, candles):
    step = BAR_SECONDS[TREND_INTERVAL]
    out = []
    for sym, cs in candles.items():
        try:
            setups = run_engine(sym, cs, CFG)
        except Exception:
            continue
        idx = {c.t: i for i, c in enumerate(cs)}
        atr = atr_series(cs, CFG.atr_len)
        # The daily bars are fetched directly rather than pulled out of
        # trend._series, whose cache tuple holds the already-built zones and
        # not the candles they came from.
        dcs = await fetch_candles(sess, sym, TREND_INTERVAL)
        dz = labelled_zones(dcs, atr_series(dcs, CFG.atr_len)) if dcs else None

        # FVG ordinal: setups sharing a displacement, in gap order.
        order = defaultdict(list)
        for x in setups:
            order[(x.mss_time, x.is_long)].append(x)
        rank = {}
        for k, g in order.items():
            for n, x in enumerate(sorted(g, key=lambda s: s.fvg_time), 1):
                rank[id(x)] = n

        for x in setups:
            i = idx.get(x.detected_time)
            if i is None or x.entry <= 0 or abs(x.entry - x.stop) <= 0:
                continue
            w = x.detected_time
            poi = await poi_at(sess, sym, w, x.stop, x.is_long, fetch_candles)
            if not (True if poi is None else bool(poi)):
                continue
            d = await direction_at(sess, sym, w, fetch_candles)
            di = await di_at(sess, sym, w, fetch_candles)
            if grade_of(False, True, d or 0, x.is_long, di or 0)[0] not in "AB":
                continue
            o = simulate(cs, i, x.entry, x.stop, x.is_long,
                         target_r=TRACK_TARGET_R)
            if not o.filled or o.exit_bar is None:
                continue
            fi = idx.get(x.fvg_time)
            a = atr[fi] if fi is not None and fi < len(atr) else 0.0
            if fi is None or fi < 2 or not a:
                continue

            z = Z()
            z.sym, z.t, z.r, z.kind = sym, w, o.r, "confirmed"
            z.span_atr = x.span / a if a else None
            gap = (cs[fi].l - cs[fi - 2].h) if x.is_long \
                else (cs[fi - 2].l - cs[fi].h)
            z.fvg_atr = gap / a if gap > 0 else None
            z.ordinal = rank.get(id(x))
            z.poi_kind = z.poi_age = z.poi_depth = None
            if dz:
                got = poi_detail(dz, w, x.stop, x.is_long, step)
                if got:
                    z.poi_kind, z.poi_age, z.poi_depth = got
            out.append(z)
    return out


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = await list_symbols(sess)
        candles = await load_universe(sess, syms, INTERVAL, DAYS)
        rows = await collect(sess, candles)

    b = bets_of(rows)
    m = mde(statistics.pstdev(b), len(b) / 2)
    print(f"ZONES AND GAPS\n{len(rows)} confirmed A/B trades, {len(b)} bets, "
          f"{DAYS} days.\nMDE on this population: {m:.3f} R/bet. "
          f"largest effect ever measured here: +0.292.")

    T = [0.25, 0.5, 0.75]
    hypothesis("item 7   pool span / ATR", rows, lambda r: r.span_atr, T, m)
    hypothesis("item 11  entry FVG size / ATR", rows, lambda r: r.fvg_atr, T, m)
    hypothesis("item 12  FVG ordinal in the leg", rows,
               lambda r: float(r.ordinal) if r.ordinal else None,
               [0.6], m, labels=["first gap", "later gap"])
    hypothesis("item 9   depth into the daily POI", rows,
               lambda r: r.poi_depth, T, m)
    hypothesis("item 9b  daily POI age, days", rows,
               lambda r: float(r.poi_age) if r.poi_age is not None else None,
               T, m)

    print(f"\nitem 10  daily POI kind   ({len(rows)} trades, MDE {m:.3f})")
    byk = defaultdict(list)
    for r in rows:
        byk[r.poi_kind or "none/unknown"].append(r)
    for k in sorted(byk, key=lambda x: -len(byk[x])):
        g = byk[k]
        if len(g) < 25:
            print(f"    {k:<16} {len(g):>4} tr — thin")
            continue
        n, nb, mm, se, p5 = cellstat(g)
        print(f"    {k:<16} {n:>4} tr {nb:>4} bets  "
              f"{sum(1 for r in g if r.r > 0) / n:>3.0%} win  "
              f"{mm:>+6.3f}±{se:.3f}  boot5th {p5:>+6.3f}"
              f"{'  OK' if p5 > 0 else ''}")


if __name__ == "__main__":
    asyncio.run(main())
