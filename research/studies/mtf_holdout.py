"""Held-out test of the daily-POI filter found in mtf_grid.py.

PRE-REGISTERED, WRITTEN BEFORE THE RUN
--------------------------------------
mtf_grid.py swept 7 HTF/LTF pairs x 4 filter arms x 2 signal types = 56 cells
on SYMBOLS[:14]. One pattern stood out, and unlike the candlestick candidate
that died here in September it is not a single cell:

    requiring the LTF raid to land inside a recent DAILY order block or fair
    value gap improved R/signal in all four cells where it could be measured

      Day1 -> Min30  confirmed   +0.317 -> +0.520
      Day1 -> Min30  early       +0.061 -> +0.125
      Day1 -> Min15  confirmed   -0.095 -> +0.417
      Day1 -> Min15  early       -0.039 -> +0.159

    while the same filter built on a 4h or 1h POI did nothing or hurt, and
    faster lower timeframes were monotonically worse (Min30 > Min15 > Min5).

PREDICTION, in advance: on the nine symbols mtf_grid never saw, the daily-POI
arm beats the unfiltered arm, with the SAME SIGN, in Day1->Min30 and
Day1->Min15, on both signal types. A sign flip in any of the four is a
failure, the same standard applied to the gapless-piercing candidate.

Also stated in advance so it cannot be rationalised afterwards: n will be
small. Nine symbols give roughly 90 confirmed setups before filtering and
perhaps 30 after, so the confirmed arms are indicative only. The EARLY arms
carry the weight — several hundred rows each — and they are the ones the
prediction really rests on.
"""
from __future__ import annotations

import research.env  # noqa: F401  (must precede riptide.config)

import asyncio
import statistics

import aiohttp

from riptide.config import CFG, BAR_SECONDS
from riptide.engine import atr_series, run_engine
from research.data import SYMBOLS
from research.harness import mean_se, simulate
from research.studies.mtf_grid import (FEE, FILL_HOURS, HORIZON_HOURS,
                                       fetch_paged, zones_of, in_poi)

HELD_OUT = SYMBOLS[14:]
PAIRS = (("Day1", "Min30"), ("Day1", "Min15"))


async def one(sess, htf_name, ltf_name):
    step_l, step_h = BAR_SECONDS[ltf_name], BAR_SECONDS[htf_name]
    fill = max(1, FILL_HOURS * 3600 // step_l)
    hor = max(1, HORIZON_HOURS * 3600 // step_l)
    pages = max(1, min(6, (41 * 86400) // (2000 * step_l)))
    acc = {("confirmed", k): [] for k in ("no", "yes")}
    acc.update({("early", k): [] for k in ("no", "yes")})
    halves = {("confirmed", k): [] for k in ("no", "yes")}
    halves.update({("early", k): [] for k in ("no", "yes")})

    for sym in HELD_OUT:
        try:
            ltf = await fetch_paged(sess, sym, ltf_name, pages)
            hcs = await fetch_paged(sess, sym, htf_name, 1)
        except Exception:
            continue
        if len(ltf) < 300 or len(hcs) < 60:
            continue
        zones = zones_of(hcs, atr_series(hcs, CFG.atr_len))
        mid = ltf[len(ltf) // 2].t
        early: list = []
        setups = run_engine(sym, ltf, CFG, early_out=early)
        idx = {c.t: i for i, c in enumerate(ltf)}
        for kind, sigs in (("confirmed", setups), ("early", early)):
            for x in sigs:
                i = idx.get(x.detected_time)
                if i is None:
                    continue
                o = simulate(ltf, i, x.entry, x.stop, x.is_long,
                             fill_bars=fill, horizon_bars=hor, **FEE)
                key = "yes" if in_poi(zones, ltf[i].t, x.stop, x.is_long,
                                      step_h) else "no"
                acc[(kind, key)].append(o.r)
                if ltf[i].t < mid:
                    halves[(kind, key)].append(o.r)

    print(f"\n{htf_name} -> {ltf_name}   held out: {len(HELD_OUT)} symbols "
          f"mtf_grid never saw")
    ok = {}
    for kind in ("confirmed", "early"):
        no, yes = acc[(kind, "no")], acc[(kind, "yes")]
        if len(no) < 25 or len(yes) < 25:
            print(f"  {kind:<10} too few  (no={len(no)} yes={len(yes)})")
            ok[kind] = None
            continue
        mn, sn = mean_se(no)
        my, sy = mean_se(yes)
        d = my - mn
        se = (sn ** 2 + sy ** 2) ** 0.5
        h1n, h1y = halves[(kind, "no")], halves[(kind, "yes")]
        hd = (mean_se(h1y)[0] - mean_se(h1n)[0]
              if len(h1n) >= 12 and len(h1y) >= 12 else None)
        print(f"  {kind:<10} outside POI {mn:+.3f} (n={len(no)})   "
              f"inside POI {my:+.3f} (n={len(yes)})")
        print(f"  {'':<10} difference {d:+.3f} ± {se:.3f}"
              + (f"  {d / se:+.1f} SE" if se else "")
              + (f"   1st half {hd:+.3f}" if hd is not None else ""))
        ok[kind] = d
    return ok


async def main():
    print(__doc__)
    verdicts = []
    async with aiohttp.ClientSession() as sess:
        for htf, ltf in PAIRS:
            r = await one(sess, htf, ltf)
            verdicts += [v for v in r.values() if v is not None]
    print("\n" + "=" * 70)
    if not verdicts:
        print("VERDICT: nothing measurable on the held-out symbols.")
    elif all(v > 0 for v in verdicts):
        print(f"VERDICT: all {len(verdicts)} held-out arms kept the predicted "
              f"sign (median {statistics.median(verdicts):+.3f}). SURVIVES.")
    else:
        n_bad = sum(v <= 0 for v in verdicts)
        print(f"VERDICT: {n_bad} of {len(verdicts)} arms flipped sign. "
              f"REJECTED, on the standard applied to every other candidate.")


if __name__ == "__main__":
    asyncio.run(main())
