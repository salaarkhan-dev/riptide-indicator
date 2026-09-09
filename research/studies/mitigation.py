"""Is a FRESH daily zone better than one price has already been back into?

The one concept in the LuxAlgo SMC script that Riptide has never measured.
Everything else it adds beyond pool → sweep → shift → gap was pre-registered
and tested in the "doctrine" batch and nothing passed: premium/discount
(−0.176 / −0.242), pool tightness a.k.a. equal highs/lows (+0.082 / −0.041),
displacement (backwards), inducement (null), stacked imbalances (negative),
daily levels as a pool source (+0.024, +0.4 SE).

Order block mitigation was the row that read "not measured", and the reason is
recorded: the test asked whether price traded back into the block between the
block bar and the SIGNAL, and the block sits immediately before the gap, so
the answer was yes for 1888 of 1888 signals. A degenerate feature returns no
buckets and silently drops out of a table. The note says what a correct
definition needs — **look at the bars before the raid, not after** — and this
is that definition.

WHAT IS BEING TESTED. A daily zone forms at bar t. The raid happens later, at
`when`, inside that zone — that is what `in_poi` already requires. The
question is whether price visited the zone at any point BETWEEN those two
moments. If it did, the zone has been "mitigated": the orders that made it are
presumed already filled, and doctrine says it is spent. If it did not, the
raid is the first return and doctrine says that is the good one.

PRE-REGISTERED: unmitigated scores higher. Both of LuxAlgo's mitigation modes
are measured because they are genuinely different questions and the script
offers both as a setting:

  wick   any trade into the zone counts as a visit   (HIGHLOW)
  close  only a daily CLOSE inside the zone counts   (CLOSE)

The wick definition will mark far more zones as mitigated. If the effect is
real it should survive both; if it appears in only one, that is a fitted
threshold rather than a mechanism.

    PYTHONPATH=. python3 research/studies/mitigation.py
"""
from __future__ import annotations

import research.env  # noqa: F401  (must precede riptide.config)

import asyncio
import statistics

import aiohttp

from riptide.config import CFG, BAR_SECONDS
from riptide.engine import atr_series, grade_of, run_engine
from riptide.exchange import list_symbols
from riptide.trend import supertrend, di_direction
from research.harness import mean_se, simulate
from research.studies.mtf_grid import (FEE, FILL_HOURS, HORIZON_HOURS,
                                       ZONE_MAX_AGE_BARS, fetch_paged,
                                       zones_of, htf_dir_at)

HTF = "Day1"
TFS = ("Min30", "Min15")


def poi_state(cs_htf, zones, when, price, is_long, step):
    """The zone the raid landed in, and whether price had been back into it.

    Returns (in_poi, visits_wick, visits_close) — None when no zone matches, so
    the caller can keep the POI test identical to the shipped one.

    Visits are counted on daily bars STRICTLY BETWEEN the zone's formation bar
    and the raid. The formation bar itself is excluded (a zone is drawn from
    the bar that made it, so it always touches itself) and so is the raid bar
    (the raid is the return being scored, not a prior visit). Excluding both is
    the whole fix: including the raid bar is what made the earlier attempt
    return "mitigated" for 1888 of 1888 signals.
    """
    best = None
    for t, bull, lo, hi in zones:
        if (t <= when and bull == is_long and lo <= price <= hi
                and when - t <= ZONE_MAX_AGE_BARS * step):
            if best is None or t > best[0]:
                best = (t, lo, hi)          # most recent matching zone
    if best is None:
        return None
    t0, lo, hi = best
    wick = close_ = 0
    for c in cs_htf:
        if c.t <= t0 or c.t >= when:
            continue
        if c.l <= hi and c.h >= lo:
            wick += 1
        if lo <= c.c <= hi:
            close_ += 1
    return True, wick, close_


async def collect():
    out, days = [], []
    async with aiohttp.ClientSession() as sess:
        for sym in await list_symbols(sess):
            try:
                hcs = await fetch_paged(sess, sym, HTF, 1)
            except Exception:
                continue
            if len(hcs) < 60:
                continue
            zones = zones_of(hcs, atr_series(hcs, CFG.atr_len))
            hst, hdi = supertrend(hcs), di_direction(hcs)
            for tf in TFS:
                try:
                    cs = await fetch_paged(sess, sym, tf, 1)
                except Exception:
                    continue
                if len(cs) < 300:
                    continue
                step = BAR_SECONDS[tf]
                if tf == TFS[0]:
                    days.append((cs[-1].t - cs[0].t) / 86400)
                idx = {c.t: i for i, c in enumerate(cs)}
                early: list = []
                setups = run_engine(sym, cs, CFG, early_out=early)
                for kind, sigs in (("confirmed", setups), ("early", early)):
                    for x in sigs:
                        i = idx.get(x.detected_time)
                        if i is None:
                            continue
                        st = poi_state(hcs, zones, cs[i].t, x.stop, x.is_long,
                                       BAR_SECONDS[HTF])
                        if st is None:            # POI_REQUIRED, as shipped
                            continue
                        _, wick, close_ = st
                        d = htf_dir_at(hcs, hst, hdi, cs[i].t)
                        o = simulate(cs, i, x.entry, x.stop, x.is_long,
                                     fill_bars=FILL_HOURS * 3600 // step,
                                     horizon_bars=HORIZON_HOURS * 3600 // step,
                                     **FEE)
                        if o.filled and o.exit_bar is None:
                            continue
                        out.append(dict(
                            tf=tf, kind=kind, r=o.r, filled=o.filled,
                            wick=wick, close=close_,
                            grade=grade_of(kind == "early", True, d,
                                           x.is_long, d)[0]))
    return out, (statistics.median(days) if days else 42.0)


def cell(rows):
    if len(rows) < 25:
        return None
    rs = [r["r"] for r in rows]
    f = [r for r in rows if r["filled"]]
    w = [r for r in f if r["r"] > 0]
    m, se = mean_se(rs)
    return len(rows), (len(w) / len(f) if f else 0.0), m, se


def show(lab, v):
    if not v:
        print(f"  {lab:<32}{'too few':>10}")
        return
    n, win, m, se = v
    print(f"  {lab:<32}{n:>6}{win:>7.0%}{m:>+11.3f} ± {se:.3f}")


HEAD = f"  {'':<32}{'n':>6}{'win':>7}{'R/signal':>17}"


def axis(title, rows, key):
    print(f"\n{title}")
    print(HEAD)
    fresh = cell([r for r in rows if r[key] == 0])
    used = cell([r for r in rows if r[key] > 0])
    show("UNMITIGATED (never revisited)", fresh)
    show("mitigated (been back in)", used)
    if fresh and used:
        d = fresh[2] - used[2]
        se = (fresh[3] ** 2 + used[3] ** 2) ** 0.5
        print(f"  {'difference (pre-registered +)':<32}{'':>13}"
              f"{d:>+11.3f}   {d / se if se else 0:+.1f} SE")
    print("  -- by how many times it was revisited --")
    for lo, hi, lab in ((0, 1, "0 visits"), (1, 2, "1 visit"),
                        (2, 4, "2-3 visits"), (4, 10 ** 9, "4+ visits")):
        show(lab, cell([r for r in rows if lo <= r[key] < hi]))


def main():
    rows, span = asyncio.run(collect())
    print(f"\n{len(rows)} POI signals over {span:.0f} days · fees in · "
          f"unfilled counted as zero")
    print("Pre-registered: an UNMITIGATED zone scores higher. Must hold on")
    print("both definitions to count as a mechanism rather than a threshold.\n")

    for key, name in (("wick", "WICK definition — any trade into the zone counts"),
                      ("close", "CLOSE definition — only a daily close inside counts")):
        print("=" * 74)
        print(name)
        print("=" * 74)
        axis("all POI signals", rows, key)
        axis("confirmed only", [r for r in rows if r["kind"] == "confirmed"],
             key)
        axis("grade A only", [r for r in rows if r["grade"] == "A"], key)
        print()

    print("=" * 74)
    print("SANITY — the earlier attempt was degenerate; is this one?")
    print("=" * 74)
    for key in ("wick", "close"):
        n0 = sum(1 for r in rows if r[key] == 0)
        print(f"  {key:<6} unmitigated {n0:>5} of {len(rows)} "
              f"({n0 / max(len(rows), 1):.0%})")
    print("  A split near 0% or 100% means the definition is degenerate again\n"
          "  and the numbers above mean nothing.")


if __name__ == "__main__":
    main()
