""""Trade with the trend" — which trend? The chart's, or the daily?

The phrase is used as though it names one thing. It names two, and on this
strategy they do not agree, so the advice is not merely ambiguous — followed
one way it helps and the other way it hurts.

  DAILY TREND    the bias the setup is taken INTO. This is what the grade
                 already reads: TREND_INTERVAL and DI_INTERVAL both ship as
                 Day1. "With the trend +0.119 R per setup, against it -0.016."
  CHART TREND    the same SuperTrend and DI computed on the timeframe being
                 traded — 30m or 15m. Nothing reads this. The feature table
                 has it at -0.241 (-1.5 SE) on confirmed, which is negative
                 but too weak to answer anything.

So both are measured on the same signals, in one 2x2, with the same scorer.
That is the only form of the answer that cannot be argued with: four cells,
one number each.

WHAT TO EXPECT, STATED FIRST. This is a REVERSAL strategy. Price raids a
liquidity pool and turns. On the chart being traded, the move immediately
before the setup is by construction going the WRONG way — that move is what
built the pool and then swept it. So "with the chart trend" asks for
continuation from a pattern whose whole premise is reversal. If the 2x2 shows
chart-agreement helping, the strategy is not what this project thinks it is.

    PYTHONPATH=. python3 research/studies/which_trend.py
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


def dir_at(st, di, bar: int) -> int:
    """Direction on the last CLOSED bar before `bar`, combining SuperTrend and
    DI the same way htf_dir_at does: they must agree or it is 0. Using bar-1
    is what keeps this non-repainting — the signal bar itself is still forming
    when the decision would be made."""
    j = bar - 1
    if j < 0 or j >= len(st) or j >= len(di):
        return 0
    return st[j] if st[j] == di[j] else 0


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
                # The CHART's own trend, on the timeframe being traded.
                cst, cdi = supertrend(cs), di_direction(cs)
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
                        d = htf_dir_at(hcs, hst, hdi, cs[i].t)
                        c = dir_at(cst, cdi, i)
                        o = simulate(cs, i, x.entry, x.stop, x.is_long,
                                     fill_bars=FILL_HOURS * 3600 // step,
                                     horizon_bars=HORIZON_HOURS * 3600 // step,
                                     **FEE)
                        if o.filled and o.exit_bar is None:
                            continue
                        want = 1 if x.is_long else -1
                        out.append(dict(
                            tf=tf, kind=kind, poi=bool(poi), r=o.r,
                            filled=o.filled,
                            grade=grade_of(kind == "early", poi, d,
                                           x.is_long, d)[0],
                            daily=(None if not d else d == want),
                            chart=(None if not c else c == want)))
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
        print(f"  {lab:<34}   too few")
        return
    n, win, m, se = v
    print(f"  {lab:<34}{n:>6}{win:>7.0%}{m:>+11.3f} ± {se:.3f}")


HEAD = f"  {'':<34}{'n':>6}{'win':>7}{'R/signal':>17}"


def axis(title, rows, key):
    print(f"\n{title}")
    print(HEAD)
    show("agrees with the trade", cell([r for r in rows if r[key] is True]))
    show("against the trade", cell([r for r in rows if r[key] is False]))
    a = cell([r for r in rows if r[key] is True])
    b = cell([r for r in rows if r[key] is False])
    if a and b:
        d = a[2] - b[2]
        se = (a[3] ** 2 + b[3] ** 2) ** 0.5
        print(f"  {'difference (agrees - against)':<34}"
              f"{'':>13}{d:>+11.3f}   {d / se if se else 0:+.1f} SE")


def grid(title, rows):
    print(f"\n{title}")
    print(f"  {'':<20}{'chart AGREES':>22}{'chart AGAINST':>22}")
    for dv, dlab in ((True, "daily agrees"), (False, "daily against")):
        line = f"  {dlab:<20}"
        for cv in (True, False):
            v = cell([r for r in rows if r["daily"] is dv and r["chart"] is cv])
            line += (f"{v[2]:>+13.3f} (n={v[0]})" if v else f"{'too few':>22}")
        print(line)


def main():
    rows, span = asyncio.run(collect())
    known = [r for r in rows if r["daily"] is not None and r["chart"] is not None]
    print(f"\n{len(rows)} signals over {span:.0f} days · "
          f"{len(known)} with both trends readable · fees in\n")
    print("Daily = TREND_INTERVAL/DI_INTERVAL, what the GRADE reads.")
    print("Chart = the same SuperTrend and DI on the traded timeframe.")

    print("\n" + "=" * 74)
    print("ONE AXIS AT A TIME")
    print("=" * 74)
    axis("THE DAILY TREND — the one the grade uses", rows, "daily")
    axis("THE CHART'S OWN TREND — nothing reads this", rows, "chart")

    print("\n" + "=" * 74)
    print("BOTH AT ONCE — R per signal in each cell")
    print("=" * 74)
    grid("all signals", known)
    grid("inside a daily POI (what the bot sends)",
         [r for r in known if r["poi"]])
    grid("confirmed only", [r for r in known if r["kind"] == "confirmed"])

    print("\n" + "=" * 74)
    print("SO WHICH TREND")
    print("=" * 74)
    print("  Read the two SINGLE-AXIS results above, not the grids.\n")

    # An earlier version of this printed the best of the four cells. That is
    # the max of four post-hoc subgroups with no correction — the same move
    # that produced the BTC x own-trend "finding" this project already
    # rejected for contradicting itself. What matters about the grids is
    # whether they AGREE with each other, so that is what gets printed.
    for lab, cv in (("chart AGREES", True), ("chart AGAINST", False)):
        vals = []
        for pname, sub in (("all", known),
                           ("in a POI", [r for r in known if r["poi"]]),
                           ("confirmed", [r for r in known
                                          if r["kind"] == "confirmed"])):
            v = cell([r for r in sub if r["daily"] is True and r["chart"] is cv])
            vals.append(f"{pname} {v[2]:+.3f}" if v else f"{pname} —")
        print(f"  daily agrees + {lab:<14} {' · '.join(vals)}")
    print("\n  If those three disagree in sign or ordering, the chart-trend\n"
          "  interaction is a regime, not an edge, and the single-axis result\n"
          "  (chart trend sorts nothing) is the one to believe.")


if __name__ == "__main__":
    main()
