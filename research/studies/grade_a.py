"""Inside grade A: what separates the A's that pay from the A's that don't.

Prompted by a live losing A. One loss is not evidence — A wins under half its
fills, so a loser is the modal outcome, not an anomaly. The useful question is
whether anything ALREADY MEASURED sorts A's, so the answer is a rule rather
than a story about one chart.

Three axes, all of them known at the moment the alert lands and none of them
new here:

  gap at alert   how far price already sits past the alert's own entry, in
                 units of that alert's risk. The project's most replicated
                 effect (10 splits, same sign in all 10) and it runs the
                 counter-intuitive way: alerts that look stranded pay more.
                 Grade does not contain this axis, so it can sort inside A.
  stop width     % risk. On the corrected scorer wider scores better, and the
                 loser diagnosis says confirmed winners carry a 1.44% median
                 stop against 1.17% for losers.
  BTC 30m        held out at +0.123 (1.8 SE) on early signals. Shown on the
                 alert, deliberately not used as a filter.

Every panel here is a SUBGROUP of a subgroup, so read the n before the number.
This is a check on whether known effects survive inside A, not a search for a
new one.

    PYTHONPATH=. python3 research/studies/grade_a.py
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
        try:
            bcs = await fetch_paged(sess, "BTC_USDT", "Min30", 1)
        except Exception:
            bcs = []
        bst = supertrend(bcs) if len(bcs) > 60 else []
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
                for x in run_engine(sym, cs, CFG):
                    i = idx.get(x.detected_time)
                    if i is None:
                        continue
                    poi = in_poi(zones, cs[i].t, x.stop, x.is_long,
                                 BAR_SECONDS[HTF])
                    if not poi:
                        continue
                    d = htf_dir_at(hcs, hst, hdi, cs[i].t)
                    if grade_of(False, poi, d, x.is_long, d)[0] != "A":
                        continue
                    o = simulate(cs, i, x.entry, x.stop, x.is_long,
                                 fill_bars=FILL_HOURS * 3600 // step,
                                 horizon_bars=HORIZON_HOURS * 3600 // step,
                                 **FEE)
                    if o.filled and o.exit_bar is None:
                        continue
                    risk = abs(x.entry - x.stop)
                    px = cs[i].c
                    gap = (px - x.entry) / risk * (1 if x.is_long else -1)
                    out.append(dict(
                        tf=tf, r=o.r, filled=o.filled, gap=gap,
                        risk_pct=100 * risk / x.entry,
                        btc=btc_agrees(bcs, bst, cs[i].t, x.is_long)))
    return out, (statistics.median(days) if days else 42.0)


def btc_agrees(bcs, bst, when, is_long):
    """BTC 30m supertrend direction as of the last CLOSED 30m bar at `when`."""
    if not bst:
        return None
    j = None
    for k, c in enumerate(bcs):
        if c.t + BAR_SECONDS["Min30"] <= when:
            j = k
        else:
            break
    if j is None or j >= len(bst) or not bst[j]:
        return None
    return (bst[j] > 0) == is_long


def row(lab, rows):
    if len(rows) < 15:
        print(f"  {lab:<26}{len(rows):>6}   too few to report")
        return
    rs = [r["r"] for r in rows]
    fills = [r for r in rows if r["filled"]]
    wins = [r for r in fills if r["r"] > 0]
    m, se = mean_se(rs)
    print(f"  {lab:<26}{len(rows):>6}{len(fills) / len(rows):>7.0%}"
          f"{(len(wins) / len(fills) if fills else 0):>7.0%}"
          f"{statistics.median([r['risk_pct'] for r in rows]):>8.2f}"
          f"{m:>+11.3f} ± {se:.3f}")


HEAD = f"  {'':<26}{'n':>6}{'fill':>7}{'win':>7}{'stop%':>8}{'R/signal':>17}"


def main():
    rows, span = asyncio.run(collect())
    print(f"\n{len(rows)} grade-A alerts over {span:.0f} days "
          f"({len(rows) / span:.1f}/day), confirmed + POI + daily trend\n")

    print("=" * 72)
    print("1. HOW FAR PRICE HAD ALREADY RUN WHEN THE A LANDED")
    print("=" * 72)
    print(HEAD)
    for lo, hi, lab in ((-1e9, 0.25, "0 - 0.25R past entry"),
                        (0.25, 0.5, "0.25 - 0.5R past"),
                        (0.5, 1.0, "0.5 - 1R past"),
                        (1.0, 1e9, "over 1R past")):
        row(lab, [r for r in rows if lo <= r["gap"] < hi])

    print("\n" + "=" * 72)
    print("2. STOP WIDTH — terciles of % risk")
    print("=" * 72)
    print(HEAD)
    rs = sorted(r["risk_pct"] for r in rows)
    if len(rs) >= 45:
        a, b = rs[len(rs) // 3], rs[2 * len(rs) // 3]
        row(f"tight  (under {a:.2f}%)", [r for r in rows if r["risk_pct"] < a])
        row(f"mid    ({a:.2f} - {b:.2f}%)",
            [r for r in rows if a <= r["risk_pct"] < b])
        row(f"wide   (over {b:.2f}%)", [r for r in rows if r["risk_pct"] >= b])
        print()
        row("under 1.00% risk", [r for r in rows if r["risk_pct"] < 1.0])
        row("1.00% risk or more", [r for r in rows if r["risk_pct"] >= 1.0])

    print("\n" + "=" * 72)
    print("3. THE BTC LINE ON THE ALERT")
    print("=" * 72)
    print(HEAD)
    row("BTC 30m agrees", [r for r in rows if r["btc"] is True])
    row("BTC 30m against", [r for r in rows if r["btc"] is False])

    print("\n" + "=" * 72)
    print("4. BY TIMEFRAME — is a 15m A the same animal as a 30m A?")
    print("=" * 72)
    print(HEAD)
    for tf in TFS:
        row(tf, [r for r in rows if r["tf"] == tf])
    print()
    row("ALL grade A", rows)


if __name__ == "__main__":
    main()
