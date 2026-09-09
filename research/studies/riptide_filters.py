"""The two things that survived, tested on Riptide's OWN pipeline.

Eleven studies have now ended at the same place, and only two variables came
out of them still standing:

  A  THE TREND INTERVAL.  `which_trend.py` found the higher timeframe sorts at
     +4.5 SE and the chart's own trend at -0.0. `lez_entry.py` then found the
     4h bias held its sign in all four panels where DAILY flipped, and
     `location.py` found the daily trend's absolute lift did not survive its
     older half at all. Riptide ships `TREND_INTERVAL = Day1`. Nothing has ever
     compared the intervals against each other on Riptide's own signals.

  B  `sweep_worth`'s DISTANCE UNIT.  `shift_distance.py` found the 3% cut's
     conversion table replicates exactly, that tightening the percent cut is
     WORSE in all four panels, and that the same distance measured in ATR
     orders consistently (+0.065, +0.226, +0.180, +0.205) where percent flips
     sign. It was recorded as a candidate needing a test against the real
     pipeline rather than the synthetic market-entry shape. This is that test.

Everything here runs on **Riptide's actual signals with Riptide's actual entry
and stop** — a limit at the fair value gap, the stop beyond the raid extreme,
scored by `simulate`. Every earlier measurement of these two variables used a
market entry with an ATR stop, which is not what ships.

60 symbols, Min30 and Min15, ~83 days split in half.

PRE-REGISTERED, BEFORE THE FIRST NUMBER

  A-PRIMARY  Among Day1 / Hour8 / Hour4 / Min60, an interval may replace the
             shipped Day1 only if its agree-minus-against gap keeps ONE SIGN in
             all four panels AND is larger than Day1's in at least three. Both
             the SuperTrend-alone convention (what `TREND_INTERVAL` actually
             controls today) and the SuperTrend-and-DI convention are reported,
             because they are different filters and the choice between them is
             part of the question.

  B-PRIMARY  Expected R per RAID — conversion rate times what the setup earns,
             with a raid that never converts scoring 0.0 — must decline
             monotonically across the distance bands in BOTH halves, for the
             unit being proposed. Percent is the incumbent and keeps the seat
             unless ATR orders consistently and percent does not.

             Expected R per raid, not R per setup, because that is what the
             filter decides: it gates whether the chart is worth opening, and a
             raid that produces nothing is the cost of opening it.

  NEITHER CHANGES ANYTHING unless it passes. A shipped constant with a
  replicated conversion table is a high bar to displace, and it should be.

    PYTHONPATH=. python3 research/studies/riptide_filters.py
"""
from __future__ import annotations

import research.env  # noqa: F401  (must precede riptide.config)

import asyncio
import statistics

import aiohttp

from riptide.config import CFG, BAR_SECONDS, TREND_INTERVAL, WATCH_MAX_DIST
from riptide.engine import atr_series, run_engine
from riptide.exchange import list_symbols
from riptide.trend import di_direction, supertrend
from research.harness import mean_se, simulate
from research.studies.mtf_grid import (fetch_paged, htf_dir_at, in_poi,
                                       zones_of)

TFS = (("Min30", 2), ("Min15", 4))
SYMBOLS = 60
HORIZON_HOURS, FILL_HOURS = 48, 5
FEE = dict(fee_maker=0.02, fee_taker=0.06)
TARGET_R, ATR_LEN = 2.0, 14

# The candidates. Day1 is the incumbent.
TREND_TFS = ("Day1", "Hour8", "Hour4", "Min60")
PCT_BANDS = ((0.0, 1.0), (1.0, 2.0), (2.0, 3.0), (3.0, 1e9))
ATR_BANDS = ((0.0, 2.0), (2.0, 3.5), (3.5, 6.0), (6.0, 1e9))


def st_only(cs, st, di, when):
    """SuperTrend alone on the last CLOSED higher-timeframe bar — what
    `TREND_INTERVAL` controls today, via `trend.direction_at`."""
    lo, hi = 0, len(cs) - 1
    if not cs or when < cs[0].t:
        return 0
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if cs[mid].t <= when:
            lo = mid
        else:
            hi = mid - 1
    i = lo - 1
    return st[i] if i >= 0 else 0


class Setup:
    __slots__ = ("half", "r", "dirs")        # dirs: (tf, conv) -> agrees


class Raid:
    __slots__ = ("half", "pct", "atr_d", "poi", "conv", "r")


async def collect(sess, syms, tf, pages, cache):
    horizon = max(1, HORIZON_HOURS * 3600 // BAR_SECONDS[tf])
    fill_bars = max(1, FILL_HOURS * 3600 // BAR_SECONDS[tf])
    setups_out: list[Setup] = []
    raids_out: list[Raid] = []
    days = []

    for sym in syms:
        try:
            cs = await fetch_paged(sess, sym, tf, pages)
            for h in TREND_TFS + ("Day1",):
                if (sym, h) not in cache:
                    cache[(sym, h)] = await fetch_paged(sess, sym, h, 1)
        except Exception:
            continue
        if len(cs) < 600:
            continue
        htfs = {h: cache[(sym, h)] for h in TREND_TFS}
        if any(len(v) < 40 for v in htfs.values()):
            continue
        days.append((cs[-1].t - cs[0].t) / 86400)
        atr = atr_series(cs, ATR_LEN)
        cut = len(cs) // 2
        idx = {c.t: i for i, c in enumerate(cs)}
        trends = {h: (supertrend(v), di_direction(v)) for h, v in htfs.items()}
        hd = cache[(sym, "Day1")]
        zones = zones_of(hd, atr_series(hd, CFG.atr_len))
        hstep = BAR_SECONDS["Day1"]

        sweeps: list = []
        try:
            setups = run_engine(sym, cs, CFG, sweeps_out=sweeps)
        except Exception:
            continue

        # ---- A: every confirmed setup, with Riptide's REAL entry and stop
        by_sweep: dict = {}
        for s in setups:
            i = idx.get(s.detected_time)
            if i is None or i + 1 + horizon > len(cs):
                continue
            if abs(s.entry - s.stop) <= 0 or s.entry <= 0:
                continue
            o = simulate(cs, i, s.entry, s.stop, s.is_long, target_r=TARGET_R,
                         fill_bars=fill_bars, horizon_bars=horizon,
                         fee_pct=0.0, **FEE)
            rec = Setup()
            rec.half = "held" if i < cut else "disc"
            rec.r = o.r
            want = 1 if s.is_long else -1
            rec.dirs = {}
            for h in TREND_TFS:
                st, di = trends[h]
                rec.dirs[(h, "st")] = st_only(htfs[h], st, di, cs[i].t) == want
                rec.dirs[(h, "st+di")] = htf_dir_at(htfs[h], st, di,
                                                    cs[i].t) == want
            setups_out.append(rec)
            if s.sweep_time:
                by_sweep.setdefault(s.sweep_time, []).append(o.r)

        # ---- B: every raid, and what it was worth in expectation
        for w in sweeps:
            i = idx.get(w.sweep_time)
            if i is None or atr[i] <= 0 or i + 1 + horizon > len(cs):
                continue
            ext = w.sweep_extreme
            if not ext:
                continue
            gap = abs(ext - w.struct_level)
            r = Raid()
            r.half = "held" if i < cut else "disc"
            r.pct = gap / ext * 100
            r.atr_d = gap / atr[i]
            r.poi = in_poi(zones, cs[i].t, ext, not w.is_high, hstep)
            follow = by_sweep.get(w.sweep_time)
            r.conv = follow is not None
            # A raid that converted to nothing is worth 0.0, not "excluded".
            # The filter gates whether to OPEN the chart, so a raid that
            # produces no setup is the cost of having opened it.
            r.r = statistics.fmean(follow) if follow else 0.0
            raids_out.append(r)
    return setups_out, raids_out, days


def study_a(setups, tf):
    print(f"\n  A. THE TREND INTERVAL — Riptide's own setups, its own entry "
          f"and stop\n     (shipped: {TREND_INTERVAL})")
    print(f"  {'interval':<10}{'conv':<8}" + "".join(
        f"{h:>29}" for h in ("DISCOVERY", "HELD OUT")))
    print(f"  {'':<10}{'':<8}" + "".join(
        f"{'agree':>8}{'against':>8}{'gap':>6}" for _ in range(2)))
    res = {}
    for h in TREND_TFS:
        for conv in ("st", "st+di"):
            cells, line = [], f"  {h:<10}{conv:<8}"
            for half in ("disc", "held"):
                sub = [x for x in setups if x.half == half]
                a = [x.r for x in sub if x.dirs[(h, conv)]]
                b = [x.r for x in sub if not x.dirs[(h, conv)]]
                if len(a) < 25 or len(b) < 25:
                    line += f"{'too few':>29}"
                    cells.append(None)
                    continue
                (ma, sa), (mb, sb) = mean_se(a), mean_se(b)
                se = (sa ** 2 + sb ** 2) ** 0.5
                cells.append((ma - mb, se))
                line += (f"{ma:>+8.3f}{mb:>+8.3f}{ma - mb:>+7.3f}"
                         f"{(ma - mb) / se if se else 0:>+6.1f}")
            res[(h, conv)] = cells
            print(line)
    return res


def study_b(raids, tf):
    print(f"\n  B. sweep_worth's DISTANCE UNIT — expected R per RAID"
          f"\n     (shipped: percent, cut at {WATCH_MAX_DIST:g}%; a raid that "
          f"never converts scores 0.0)")
    out = {}
    for unit, key, bands in (("percent", lambda r: r.pct, PCT_BANDS),
                             ("ATR", lambda r: r.atr_d, ATR_BANDS)):
        print(f"   -- distance in {unit} --")
        print(f"  {'band':<12}" + "".join(
            f"{t:>34}" for t in ("DISCOVERY", "HELD OUT")))
        print(f"  {'':<12}" + "".join(
            f"{'n':>7}{'conv':>7}{'E[R]/raid':>12}{'SE':>8}" for _ in range(2)))
        seq = {"disc": [], "held": []}
        for lo, hi in bands:
            lab = f"{lo:g}-{hi:g}" if hi < 1e8 else f">{lo:g}"
            line = f"  {lab:<12}"
            for half in ("disc", "held"):
                sub = [r for r in raids
                       if r.half == half and r.poi and lo <= key(r) < hi]
                if len(sub) < 25:
                    line += f"{len(sub):>7}{'too few':>27}"
                    seq[half].append(None)
                    continue
                m, se = mean_se([r.r for r in sub])
                seq[half].append(m)
                line += (f"{len(sub):>7}"
                         f"{sum(r.conv for r in sub) / len(sub):>7.0%}"
                         f"{m:>+12.3f}{se:>8.3f}")
            print(line)
        mono = {}
        for half in ("disc", "held"):
            v = [x for x in seq[half] if x is not None]
            mono[half] = len(v) >= 3 and all(a >= b for a, b in zip(v, v[1:]))
        out[unit] = mono
        print(f"      monotone decline:  discovery {mono['disc']}   "
              f"held out {mono['held']}")
    return out


def verdict(all_a, all_b):
    print(f"\n{'=' * 100}\n  VERDICTS, against the bars fixed before the run"
          f"\n{'=' * 100}")
    print(f"  A — an interval replaces Day1 only if its gap keeps ONE SIGN in "
          f"all four panels\n      and beats Day1's gap in at least three")
    base = {}
    for conv in ("st", "st+di"):
        base[conv] = [c for tf in all_a for c in all_a[tf][("Day1", conv)]]
    for h in TREND_TFS:
        for conv in ("st", "st+di"):
            cells = [c for tf in all_a for c in all_a[tf][(h, conv)]]
            good = [c for c in cells if c is not None]
            if len(good) < 4:
                print(f"    {h:<8}{conv:<8} incomparable")
                continue
            gaps = [g for g, _ in good]
            one_sign = all(g > 0 for g in gaps) or all(g < 0 for g in gaps)
            beats = sum(1 for (g, _), b in zip(good, base[conv])
                        if b is not None and g > b[0])
            # Inverse-variance pooling of the four panels. They are separate
            # timeframes and separate window halves, so treating them as
            # independent is defensible; it is stated rather than assumed.
            w = [1 / (se ** 2) for _, se in good if se > 0]
            gw = [g / (se ** 2) for g, se in good if se > 0]
            pooled = sum(gw) / sum(w) if w else 0.0
            pse = (1 / sum(w)) ** 0.5 if w else 0.0
            mark = ("PASSES" if h != "Day1" and one_sign
                    and all(g > 0 for g in gaps) and beats >= 3 else "")
            print(f"    {h:<8}{conv:<8}"
                  + "  ".join(f"{g:+.3f}" for g in gaps)
                  + f"   one sign {str(one_sign):<5} beats Day1 {beats}/4"
                  + f"   pooled {pooled:+.3f} ± {pse:.3f}"
                  + f" ({pooled / pse if pse else 0:+.1f} SE)   {mark}")

    print(f"\n  B — the unit must decline monotonically in BOTH halves; "
          f"percent keeps the seat unless\n      ATR orders and percent does not")
    for tf, b in all_b.items():
        for unit, m in b.items():
            print(f"    {tf:<8}{unit:<9} discovery {m['disc']}   "
                  f"held out {m['held']}")


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = (await list_symbols(sess))[:SYMBOLS]
        print(f"Riptide's two survivors, on Riptide's own pipeline\n"
              f"{len(syms)} symbols · limit at the gap, stop beyond the raid, "
              f"{TARGET_R:g}R target, fees 0.02/0.06%")
        cache: dict = {}
        all_a, all_b = {}, {}
        for tf, pages in TFS:
            setups, raids, days = await collect(sess, syms, tf, pages, cache)
            if not days:
                continue
            print(f"\n{'=' * 100}\n{tf}   {statistics.median(days):.0f} days x "
                  f"{len(days)} symbols   ({len(setups)} setups, "
                  f"{len(raids)} raids)\n{'=' * 100}")
            all_a[tf] = study_a(setups, tf)
            all_b[tf] = study_b(raids, tf)
        if all_a:
            verdict(all_a, all_b)


if __name__ == "__main__":
    asyncio.run(main())
