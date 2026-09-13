"""Does the daily POI rescue a scalping timeframe the way it rescued 15m?

Asked after three trades in a row stopped out: tune it down to a scalping
timeframe. Dropping to Min5 was measured once and lost — fill rate rose 69% to
85%, the stop tightened 1.43% to 0.66%, and the win rate fell 54% to 33%
underneath it. But that measurement PREDATES the daily POI filter, and the POI
is the one thing that changed a timeframe's verdict: Min15 measured NEGATIVE
on its own (-0.095 confirmed, -0.039 early) and turned positive only inside a
POI (+0.417, +0.159).

So the question is open and worth the compute: if the POI rescued 15m, does it
rescue 5m? Refusing to re-test because an older, differently-configured run
said no is how a project stops learning.

FAIR COMPARISON, WHICH IS MOST OF THE WORK

  same calendar window   2000 bars is 41.6 days of Min30 but 6.9 days of Min5.
                         Pages are fetched per timeframe so all three see the
                         same number of DAYS, not the same number of bars.
  same symbols           a timeframe that silently drops thin symbols would
                         look better for it.
  fees in R              the whole point. Cost in R is FEE/risk_pct, so a
                         0.66% stop pays 12% of its risk in a round trip
                         against 5% at 1.6%. On a scalping timeframe the fee
                         is not a rounding error, it is the position.
  same daily POI         one HTF zone set, applied identically at every
                         timeframe.

WHAT WOULD CHANGE MY MIND. Min5 inside a POI scoring positive, with fees, on
a window this size. Nothing less.

    PYTHONPATH=. python3 research/studies/scalp.py
"""
from __future__ import annotations

import research.env  # noqa: F401  (must precede riptide.config)

import asyncio
import statistics

import aiohttp

from riptide.config import CFG, BAR_SECONDS
from riptide.engine import atr_series, run_engine
from riptide.exchange import list_symbols
from riptide.trend import supertrend, di_direction
from research.harness import mean_se, simulate
from research.studies.mtf_grid import (FEE, FILL_HOURS, HORIZON_HOURS,
                                       fetch_paged, zones_of, in_poi,
                                       htf_dir_at)

HTF = "Day1"
# Pages chosen so every timeframe covers roughly the same 40+ days.
# 2000 bars is 41.6d of Min30, 20.8d of Min15, 6.9d of Min5, 1.4d of Min1.
TFS = (("Min30", 1), ("Min15", 2), ("Min5", 6), ("Min1", 30))
SYMBOLS = 30          # fewer symbols, because Min1 costs 30 requests each


async def collect():
    out, span = [], {}
    async with aiohttp.ClientSession() as sess:
        syms = (await list_symbols(sess))[:SYMBOLS]
        for sym in syms:
            try:
                hcs = await fetch_paged(sess, sym, HTF, 1)
            except Exception:
                continue
            if len(hcs) < 60:
                continue
            zones = zones_of(hcs, atr_series(hcs, CFG.atr_len))
            hst, hdi = supertrend(hcs), di_direction(hcs)
            for tf, pages in TFS:
                try:
                    cs = await fetch_paged(sess, sym, tf, pages)
                except Exception:
                    continue
                if len(cs) < 300:
                    continue
                step = BAR_SECONDS[tf]
                span.setdefault(tf, []).append((cs[-1].t - cs[0].t) / 86400)
                idx = {c.t: i for i, c in enumerate(cs)}
                early: list = []
                setups = run_engine(sym, cs, CFG, early_out=early)
                for kind, sigs in (("confirmed", setups), ("early", early)):
                    for x in sigs:
                        i = idx.get(x.detected_time)
                        if i is None:
                            continue
                        o = simulate(cs, i, x.entry, x.stop, x.is_long,
                                     fill_bars=FILL_HOURS * 3600 // step,
                                     horizon_bars=HORIZON_HOURS * 3600 // step,
                                     **FEE)
                        if o.filled and o.exit_bar is None:
                            continue
                        risk = 100 * abs(x.entry - x.stop) / x.entry
                        out.append(dict(
                            tf=tf, kind=kind,
                            poi=bool(in_poi(zones, cs[i].t, x.stop, x.is_long,
                                            BAR_SECONDS[HTF])),
                            trend=htf_dir_at(hcs, hst, hdi, cs[i].t)
                                  == (1 if x.is_long else -1),
                            r=o.r, filled=o.filled, risk=risk,
                            fee_share=0.08 / risk if risk else 0.0))
    return out, {k: statistics.median(v) for k, v in span.items()}


def row(lab, rows, days):
    if len(rows) < 25:
        print(f"  {lab:<28}{len(rows):>6}   too few")
        return
    rs = [r["r"] for r in rows]
    f = [r for r in rows if r["filled"]]
    w = [r for r in f if r["r"] > 0]
    m, se = mean_se(rs)
    risk = statistics.median([r["risk"] for r in rows])
    fee = statistics.median([r["fee_share"] for r in rows])
    print(f"  {lab:<28}{len(rows):>6}{len(rows) / max(days, 1):>7.1f}"
          f"{risk:>8.2f}{fee:>8.1%}{len(f) / len(rows):>7.0%}"
          f"{(len(w) / len(f) if f else 0):>6.0%}"
          f"{m:>+11.3f} ± {se:.3f}{sum(rs):>+9.1f}")


HEAD = (f"  {'':<28}{'n':>6}{'/day':>7}{'stop%':>8}{'fee/R':>8}"
        f"{'fill':>7}{'win':>6}{'R/signal':>17}{'total':>9}")


def main():
    rows, spans = asyncio.run(collect())
    print(f"\n{len(rows)} signals · {SYMBOLS} symbols · fees in · "
          f"unfilled counted as zero")
    print("window per timeframe: "
          + ", ".join(f"{tf} {spans.get(tf, 0):.0f}d" for tf, _ in TFS) + "\n")

    for title, pred in (
            ("EVERY SIGNAL — no POI filter", lambda r: True),
            ("INSIDE A DAILY POI — the question", lambda r: r["poi"]),
            ("INSIDE A POI, WITH THE DAILY TREND", lambda r: r["poi"] and r["trend"]),
    ):
        print("=" * 96)
        print(title)
        print("=" * 96)
        print(HEAD)
        for tf, _ in TFS:
            row(tf, [r for r in rows if r["tf"] == tf and pred(r)],
                spans.get(tf, 1))
        print()

    print("=" * 96)
    print("CONFIRMED ONLY, INSIDE A POI — the highest-quality cell per timeframe")
    print("=" * 96)
    print(HEAD)
    for tf, _ in TFS:
        row(tf, [r for r in rows if r["tf"] == tf and r["poi"]
                 and r["kind"] == "confirmed"], spans.get(tf, 1))

    print("\n" + "=" * 96)
    print("WHAT THE FEE COLUMN MEANS")
    print("=" * 96)
    for tf, _ in TFS:
        sub = [r for r in rows if r["tf"] == tf and r["poi"]]
        if len(sub) < 25:
            continue
        risk = statistics.median([r["risk"] for r in sub])
        print(f"  {tf:<8} median stop {risk:>5.2f}% -> a round trip costs "
              f"{0.08 / risk:.3f} R, "
              f"{0.08 / risk * 100:.0f}% of a 1R loss")


if __name__ == "__main__":
    main()
