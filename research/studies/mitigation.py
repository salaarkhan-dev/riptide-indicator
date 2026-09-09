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
    age = (when - t0) // step          # in HTF bars
    wick = close_ = 0
    for c in cs_htf:
        if c.t <= t0 or c.t >= when:
            continue
        if c.l <= hi and c.h >= lo:
            wick += 1
        if lo <= c.c <= hi:
            close_ += 1
    return age, wick, close_


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
                        age, wick, close_ = st
                        d = htf_dir_at(hcs, hst, hdi, cs[i].t)
                        o = simulate(cs, i, x.entry, x.stop, x.is_long,
                                     fill_bars=FILL_HOURS * 3600 // step,
                                     horizon_bars=HORIZON_HOURS * 3600 // step,
                                     **FEE)
                        if o.filled and o.exit_bar is None:
                            continue
                        out.append(dict(
                            tf=tf, kind=kind, r=o.r, filled=o.filled,
                            wick=wick, close=close_, age=age,
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


CACHE = "/tmp/riptide-mitigation-rows.json"


def main():
    import json
    import os
    if os.path.exists(CACHE):
        with open(CACHE) as fh:
            blob = json.load(fh)
        rows, span = blob["rows"], blob["span"]
        print(f"(reusing {CACHE} — delete it to refetch)")
    else:
        rows, span = asyncio.run(collect())
        with open(CACHE, "w") as fh:
            json.dump({"rows": rows, "span": span}, fh)
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
    print("THE CONTROL — is 'unmitigated' just 'young'?")
    print("=" * 74)
    print("A zone formed one bar before the raid has NO intervening bars and")
    print("is unmitigated by construction. If the effect is about unfilled")
    print("orders it must survive inside age buckets. If it does not, the")
    print("finding is zone AGE and the fix is a tighter age cap.\n")
    ages = sorted(r["age"] for r in rows)
    a1, a2 = ages[len(ages) // 3], ages[2 * len(ages) // 3]
    print(f"  age terciles: young <{a1}, mid {a1}-{a2}, old >{a2} daily bars")
    for key in ("wick", "close"):
        print(f"\n  -- {key} definition --")
        print(f"  {'':<32}{'n':>6}{'win':>7}{'R/signal':>17}")
        for lo, hi, lab in ((0, a1, "young"), (a1, a2, "mid"),
                            (a2, 10 ** 9, "old")):
            band = [r for r in rows if lo <= r["age"] < hi]
            f = cell([r for r in band if r[key] == 0])
            m = cell([r for r in band if r[key] > 0])
            show(f"{lab}: unmitigated", f)
            show(f"{lab}: mitigated", m)
            if f and m:
                d = f[2] - m[2]
                se = (f[3] ** 2 + m[3] ** 2) ** 0.5
                print(f"  {'  -> difference':<32}{'':>13}{d:>+11.3f}"
                      f"   {d / se if se else 0:+.1f} SE")
    print()
    print("  Also: how young ARE the unmitigated ones?")
    for key in ("wick", "close"):
        f = [r["age"] for r in rows if r[key] == 0]
        m = [r["age"] for r in rows if r[key] > 0]
        if f and m:
            print(f"    {key:<6} median age — unmitigated "
                  f"{statistics.median(f):.0f} bars, mitigated "
                  f"{statistics.median(m):.0f} bars")

    print("\n" + "=" * 74)
    print("THE DECISIVE PANEL — age held at ONE value")
    print("=" * 74)
    print("The tercile control cannot settle it: 'young' spans 0-2 bars and at")
    print("age 0 there are no intervening bars, so mitigation is impossible by")
    print("construction. Fixing age at a single value removes the confound")
    print("completely — at age 3 there are exactly three bars that could have")
    print("been a visit, and unmitigated vs mitigated is then a clean contrast.\n")
    for key in ("wick", "close"):
        print(f"  -- {key} definition --")
        print(f"  {'age':<6}{'unmit n':>9}{'unmit R':>10}"
              f"{'mit n':>8}{'mit R':>10}{'diff':>9}{'SE':>7}")
        for a in range(1, 13):
            band = [r for r in rows if r["age"] == a]
            f = cell([r for r in band if r[key] == 0])
            m = cell([r for r in band if r[key] > 0])
            if not f or not m:
                continue
            d = f[2] - m[2]
            se = (f[3] ** 2 + m[3] ** 2) ** 0.5
            print(f"  {a:<6}{f[0]:>9}{f[2]:>+10.3f}{m[0]:>8}{m[2]:>+10.3f}"
                  f"{d:>+9.3f}{d / se if se else 0:>7.1f}")
        print()
    print("  If the difference survives at fixed age, mitigation is real.")
    print("  If it collapses, the whole finding is 'the zone is young'.\n")

    print("=" * 74)
    print("AGE ALONE — ignoring mitigation entirely")
    print("=" * 74)
    print(f"  {'':<32}{'n':>6}{'win':>7}{'R/signal':>17}")
    for lo, hi, lab in ((0, 1, "age 0"), (1, 3, "age 1-2"), (3, 6, "age 3-5"),
                        (6, 11, "age 6-10"), (11, 10 ** 9, "age 11+")):
        show(lab, cell([r for r in rows if lo <= r["age"] < hi]))
    print("\n  If this gradient alone is as strong as the mitigation split,")
    print("  the shippable change is a tighter ZONE_MAX_AGE_BARS and nothing")
    print("  about order blocks at all.\n")

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
