"""What each grade actually delivers: fill rate, win rate, RR, expectancy.

The one table to read before deciding which alerts to act on. It scores the
signals the bot would ACTUALLY SEND — live universe, both scanned timeframes,
POI required, grade from riptide.engine.grade_of — so every row is a category
of message that arrives on the phone rather than an abstract bucket.

FOUR NUMBERS, AND THEY ARE NOT INTERCHANGEABLE
----------------------------------------------
  fill %      how often the limit order is touched at all. An unfilled setup
              is a zero, not a loss, and pays no fee.
  win %       of the fills that happened, how many reached target. This is the
              number people mean by "win rate" and it flatters every strategy
              with a low fill rate, so it is never shown alone here.
  RR          realised, not planned. The plan is 2R against 1R; what comes
              back is average win divided by average loss, and it is always
              below 2 because a stop costs slightly more than 1R after fees
              and a timeout exits somewhere in between.
  R / signal  the only one that compounds. Fill rate, win rate and RR all
              collapse into it, unfilled signals included as zeros, fees
              charged maker-in/maker-out on a win and maker-in/taker-out on a
              loss. If two rows disagree, this is the one to believe.

WHAT THIS IS NOT. A 42-day backtest window, and the grade boundaries were
drawn on data that overlaps it. /stats is the forward record and is worth
strictly more the moment it has the rows.
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
                                       fetch_paged, zones_of, in_poi,
                                       htf_dir_at)

HTF = "Day1"
TFS = ("Min30", "Min15")


async def collect():
    out, days = [], []
    async with aiohttp.ClientSession() as sess:
        syms = await list_symbols(sess)
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
                early: list = []
                setups = run_engine(sym, cs, CFG, early_out=early)
                for kind, sigs in (("confirmed", setups), ("early", early)):
                    for x in sigs:
                        i = idx.get(x.detected_time)
                        if i is None:
                            continue
                        poi = in_poi(zones, cs[i].t, x.stop, x.is_long,
                                     BAR_SECONDS[HTF])
                        if not poi:                 # POI_REQUIRED: never sent
                            continue
                        d = htf_dir_at(hcs, hst, hdi, cs[i].t)
                        o = simulate(cs, i, x.entry, x.stop, x.is_long,
                                     fill_bars=FILL_HOURS * 3600 // step,
                                     horizon_bars=HORIZON_HOURS * 3600 // step,
                                     **FEE)
                        if o.filled and o.exit_bar is None:
                            continue
                        out.append(dict(
                            tf=tf, kind=kind,
                            grade=grade_of(kind == "early", poi, d,
                                           x.is_long, d)[0],
                            r=o.r, filled=o.filled,
                            risk=100 * abs(x.entry - x.stop) / x.entry))
    return out, (statistics.median(days) if days else 42.0)


HEAD = (f"  {'category':<26}{'n':>6}{'/day':>7}{'fill':>7}{'win':>7}"
        f"{'avg win':>9}{'avg loss':>9}{'RR':>6}{'R/trade':>9}"
        f"{'R/signal':>17}")


def row(lab, rows, span):
    if len(rows) < 20:
        print(f"  {lab:<26}{len(rows):>6}   too few to report")
        return
    rs = [r["r"] for r in rows]
    fills = [r for r in rows if r["filled"]]
    wins = [r["r"] for r in fills if r["r"] > 0]
    losses = [r["r"] for r in fills if r["r"] <= 0]
    aw = statistics.fmean(wins) if wins else 0.0
    al = statistics.fmean(losses) if losses else 0.0
    rr = (aw / abs(al)) if al else 0.0
    m, se = mean_se(rs)
    per_trade = statistics.fmean([r["r"] for r in fills]) if fills else 0.0
    print(f"  {lab:<26}{len(rows):>6}{len(rows) / span:>7.1f}"
          f"{len(fills) / len(rows):>7.0%}"
          f"{(len(wins) / len(fills) if fills else 0):>7.0%}"
          f"{aw:>+9.2f}{al:>+9.2f}{rr:>6.2f}{per_trade:>+9.3f}"
          f"{m:>+11.3f} ± {se:.3f}")


def main():
    rows, span = asyncio.run(collect())
    print(f"\n{len(rows)} alerts over {span:.0f} days · POI required · "
          f"2R target · maker/taker fees · scored from the FILL bar\n")

    print("=" * 104)
    print("BY GRADE — every alert the bot sends")
    print("=" * 104)
    print(HEAD)
    for g in ("A", "B", "C", "D"):
        row(f"grade {g}", [r for r in rows if r["grade"] == g], span)
    print()
    row("ALL", rows, span)

    print("\n" + "=" * 104)
    print("BY GRADE AND TYPE — what the letter means on each kind of alert")
    print("=" * 104)
    print(HEAD)
    for kind in ("confirmed", "early"):
        for g in ("A", "B", "C", "D"):
            sub = [r for r in rows if r["grade"] == g and r["kind"] == kind]
            if sub:
                row(f"{kind} {g}", sub, span)
        print()

    print("=" * 104)
    print("BY GRADE AND TIMEFRAME — is a 15m alert worth the same as a 30m one?")
    print("=" * 104)
    print(HEAD)
    for tf in TFS:
        for g in ("A", "B", "C", "D"):
            sub = [r for r in rows if r["grade"] == g and r["tf"] == tf]
            if sub:
                row(f"{tf} {g}", sub, span)
        print()

    print("=" * 104)
    print("EVERY CELL — timeframe, type, grade")
    print("=" * 104)
    print(HEAD)
    for tf in TFS:
        for kind in ("confirmed", "early"):
            for g in ("A", "B", "C", "D"):
                sub = [r for r in rows if r["grade"] == g
                       and r["tf"] == tf and r["kind"] == kind]
                if sub:
                    row(f"{tf} {kind} {g}", sub, span)


if __name__ == "__main__":
    main()
