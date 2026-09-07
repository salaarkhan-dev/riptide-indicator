"""How many alerts of each type actually arrive, per day, under the live policy.

Not "how many signals exist" — how many MESSAGES a phone gets. That means
applying the shipped configuration exactly: the live universe, both scanned
timeframes, POI_REQUIRED, and the real grade function rather than a
reconstruction of it.

One consequence worth seeing rather than being told: with the POI required,
grade D can never be sent. D is early + no POI + against the trend, and the
no-POI half is the thing being filtered, so the band that used to be 38% of
all traffic is now structurally unreachable. B splits the same way — the
"confirmed with the trend, no POI" half of it cannot arrive either, so every
B you see is an early signal.
"""
from __future__ import annotations

import research.env  # noqa: F401  (must precede riptide.config)

import asyncio
import statistics
from collections import defaultdict

import aiohttp

from riptide.config import CFG, BAR_SECONDS, SWEEP_INTERVALS
from riptide.engine import atr_series, grade_of, run_engine
from riptide.exchange import list_symbols
from riptide.trend import supertrend, di_direction
from research.harness import mean_se, simulate
from research.studies.mtf_grid import (FEE, FILL_HOURS, HORIZON_HOURS,
                                       fetch_paged, zones_of, in_poi,
                                       htf_dir_at)

HTF = "Day1"
TFS = ("Min30", "Min15")


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = await list_symbols(sess)
        rows, sweeps, days = [], [], []
        for sym in syms:
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
                early, sw = [], []
                setups = run_engine(sym, cs, CFG, early_out=early, sweeps_out=sw)
                for w in sw:
                    if tf in SWEEP_INTERVALS and in_poi(
                            zones, w.sweep_time, w.sweep_extreme,
                            not w.is_high, BAR_SECONDS[HTF]):
                        sweeps.append(tf)
                for kind, sigs in (("confirmed", setups), ("early", early)):
                    for x in sigs:
                        i = idx.get(x.detected_time)
                        if i is None:
                            continue
                        poi = in_poi(zones, cs[i].t, x.stop, x.is_long,
                                     BAR_SECONDS[HTF])
                        if not poi:                     # POI_REQUIRED
                            continue
                        d = htf_dir_at(hcs, hst, hdi, cs[i].t)
                        o = simulate(cs, i, x.entry, x.stop, x.is_long,
                                     fill_bars=FILL_HOURS * 3600 // step,
                                     horizon_bars=HORIZON_HOURS * 3600 // step,
                                     **FEE)
                        if o.filled and o.exit_bar is None:
                            continue
                        g = grade_of(kind == "early", poi, d, x.is_long, d)[0]
                        rows.append((tf, kind, g, o.r, o.filled,
                                     100 * abs(x.entry - x.stop) / x.entry))
    span = statistics.median(days) if days else 42.0
    print(f"\n{len(syms)} symbols · {span:.0f} days · POI required · "
          f"grade from riptide.engine.grade_of\n")
    print(f"  {'timeframe':<10}{'type':<11}{'grade':<7}{'per day':>9}{'n':>7}"
          f"{'fill':>7}{'win':>7}{'stop%':>7}{'R/signal':>18}")
    tot = defaultdict(int)
    for tf in TFS:
        for kind in ("confirmed", "early"):
            for g in ("A", "B", "C", "D"):
                sub = [r for r in rows if r[0] == tf and r[1] == kind
                       and r[2] == g]
                if not sub:
                    continue
                rs = [r[3] for r in sub]
                fills = [r for r in sub if r[4]]
                m, se = mean_se(rs)
                tot[tf] += len(sub)
                print(f"  {tf:<10}{kind:<11}{g:<7}{len(sub) / span:>9.1f}"
                      f"{len(sub):>7}{len(fills) / len(sub):>7.0%}"
                      f"{sum(r[3] > 0 for r in fills) / max(len(fills), 1):>7.0%}"
                      f"{statistics.median([r[5] for r in sub]):>7.2f}"
                      f"{m:>+11.3f} ± {se:.3f}")
        print()
    for tf in TFS:
        print(f"  {tf}: {tot[tf] / span:.1f} trade alerts/day")
    print(f"  sweeps ({'+'.join(SWEEP_INTERVALS)}): {len(sweeps) / span:.1f}/day")
    print(f"\n  TOTAL {(sum(tot.values()) + len(sweeps)) / span:.1f} messages/day")


if __name__ == "__main__":
    asyncio.run(main())
