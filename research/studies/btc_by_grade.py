"""Does the BTC 30m regime still sort signals AFTER the POI filter?

The held-out BTC result was measured on ALL early signals, before the daily
POI filter existed: agreeing +0.179, against -0.055 on the discovery window,
+0.123 (1.8 SE) held out. Grade B is early + POI + trend and scores +0.180
overall, so the open question is whether the POI absorbs the BTC split or the
two stack.

DIRECTION IS PRE-REGISTERED, and by something other than this file: the
held-out study said BTC 30m AGREEING predicts higher R on early signals. That
is the direction expected here. A result the other way is evidence the effect
does not survive the filter, NOT a new effect to trade backwards -- which is
the mistake grade A invited when it came back inverted at 2.9 SE.

Grade A is included so the two sit in one table, but A is the subgroup that
already misbehaved and nothing here changes that reading.

ROBUSTNESS. The headline split is repeated on disjoint symbol halves and on
the first and second half of the window. An effect that holds in one arm and
reverses in another is noise however large its overall SE.

    PYTHONPATH=. python3 research/studies/btc_by_grade.py
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


def btc_agrees(bcs, bst, when, is_long):
    """BTC 30m supertrend as of the last CLOSED 30m bar at `when`."""
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


async def collect():
    out = []
    async with aiohttp.ClientSession() as sess:
        syms = await list_symbols(sess)
        bcs = await fetch_paged(sess, "BTC_USDT", "Min30", 1)
        bst = supertrend(bcs) if len(bcs) > 60 else []
        for si, sym in enumerate(syms):
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
                        g = grade_of(kind == "early", poi, d, x.is_long, d)[0]
                        o = simulate(cs, i, x.entry, x.stop, x.is_long,
                                     fill_bars=FILL_HOURS * 3600 // step,
                                     horizon_bars=HORIZON_HOURS * 3600 // step,
                                     **FEE)
                        if o.filled and o.exit_bar is None:
                            continue
                        out.append(dict(
                            sym=sym, half=si % 2, tf=tf, grade=g, kind=kind,
                            poi=bool(poi), t=cs[i].t, r=o.r, filled=o.filled,
                            btc=btc_agrees(bcs, bst, cs[i].t, x.is_long)))
    return out


def cell(rows):
    if len(rows) < 15:
        return None
    rs = [r["r"] for r in rows]
    fills = [r for r in rows if r["filled"]]
    wins = [r for r in fills if r["r"] > 0]
    m, se = mean_se(rs)
    return (len(rows), len(fills) / len(rows),
            (len(wins) / len(fills) if fills else 0.0), m, se)


def split(lab, rows):
    """Print agrees / against / difference for one slice."""
    a = cell([r for r in rows if r["btc"] is True])
    b = cell([r for r in rows if r["btc"] is False])
    if not a or not b:
        print(f"  {lab:<28}  too few")
        return
    diff = a[3] - b[3]
    se = (a[4] ** 2 + b[4] ** 2) ** 0.5
    print(f"  {lab:<28}{a[0]:>6}{a[1]:>6.0%}{a[2]:>6.0%}{a[3]:>+8.3f}"
          f"{b[0]:>7}{b[1]:>6.0%}{b[2]:>6.0%}{b[3]:>+8.3f}"
          f"{diff:>+9.3f}{diff / se if se else 0:>7.1f}")


HEAD = (f"  {'':<28}{'n':>6}{'fill':>6}{'win':>6}{'R':>8}"
        f"{'n':>7}{'fill':>6}{'win':>6}{'R':>8}{'diff':>9}{'SE':>7}")


def main():
    rows = asyncio.run(collect())
    known = [r for r in rows if r["btc"] is not None]
    mid = statistics.median([r["t"] for r in known])
    print(f"\n{len(known)} alerts with a BTC reading · POI required · "
          f"2R · fees in")
    print("Pre-registered direction: AGREEING scores higher (held out at "
          "+0.123 on early).\n")
    print(f"  {'':<28}{'--------- BTC AGREES --------':^26}"
          f"{'-------- BTC AGAINST --------':^27}")
    print(HEAD)

    print("\n  -- the headline --")
    split("grade B (early+POI+trend)", [r for r in rows if r["grade"] == "B"])
    split("grade A (conf+POI+trend)", [r for r in rows if r["grade"] == "A"])
    split("grade C (in a POI)",
          [r for r in rows if r["grade"] == "C" and r["poi"]])
    split("everything sent (A+B)",
          [r for r in rows if r["grade"] in ("A", "B")])

    print("\n  -- grade B by timeframe --")
    for tf in TFS:
        split(f"B {tf}", [r for r in rows if r["grade"] == "B"
                          and r["tf"] == tf])

    print("\n  -- grade B, robustness: does it hold in every arm? --")
    b = [r for r in rows if r["grade"] == "B"]
    split("symbols A (even index)", [r for r in b if r["half"] == 0])
    split("symbols B (odd index)", [r for r in b if r["half"] == 1])
    split("first half of window", [r for r in b if r["t"] < mid])
    split("second half of window", [r for r in b if r["t"] >= mid])

    print("\n  -- reference: the population the held-out study measured --")
    split("all early, POI or not", [r for r in rows if r["kind"] == "early"])
    split("all early, outside a POI",
          [r for r in rows if r["kind"] == "early" and not r["poi"]])


if __name__ == "__main__":
    main()
