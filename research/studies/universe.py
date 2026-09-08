"""Does a smaller, more liquid universe pay better per signal?

One variable: how many symbols are scanned. Min30 only, POI required, same
window, same scorer, same everything else. Raised by `scalp.py`, where Min30
confirmed-in-a-POI on 30 symbols scored +0.431 at a 61% win rate against a
comparable 52% on 60 — but that run changed the symbol count AND dropped the
trend condition at once, so it settled nothing.

THE TRAP THIS IS DESIGNED AROUND

Ranking symbols by TODAY'S turnover and then scoring the last 42 days is
look-ahead. A coin that pumped last week is in today's top 20 because of the
very move being scored, so "the top 20 did better" would be guaranteed before
any data was fetched. `filter_by_turnover` ranks on live `amount24`, which is
exactly this, and `market.py` has only 1.6 days of turnover history — not
enough to rank on the past.

So the ranking comes from the CANDLES, and it is split in time:

  rank on    median bar turnover (volume x close) over the FIRST half
  score on   signals in the SECOND half only

The ranking variable is then strictly prior to every outcome it sorts. The
naive version — rank and score on the whole window — is reported beside it so
the SIZE of the bias is visible rather than assumed.

WHAT WOULD COUNT. Not a winning cutoff: testing five cutoffs and keeping the
best is how the last twenty-one filters were nearly born. What counts is a
MONOTONE gradient across the marginal tiers — each successive tier of less
liquid symbols worth less than the one above it — holding in the honest split.
A single peak in the middle is noise wearing a number.

    PYTHONPATH=. python3 research/studies/universe.py
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
TF = "Min30"
BANDS = (10, 20, 30, 40, 60)


async def collect():
    """Per symbol: its first-half and full-window turnover, and every signal
    it produced with the half of the window it landed in."""
    out, days = [], []
    async with aiohttp.ClientSession() as sess:
        for sym in await list_symbols(sess):
            try:
                hcs = await fetch_paged(sess, sym, HTF, 1)
                cs = await fetch_paged(sess, sym, TF, 1)
            except Exception:
                continue
            if len(hcs) < 60 or len(cs) < 300:
                continue
            days.append((cs[-1].t - cs[0].t) / 86400)
            mid_t = cs[len(cs) // 2].t
            first = [c.v * c.c for c in cs if c.t < mid_t]
            allb = [c.v * c.c for c in cs]
            if not first:
                continue
            zones = zones_of(hcs, atr_series(hcs, CFG.atr_len))
            hst, hdi = supertrend(hcs), di_direction(hcs)
            step = BAR_SECONDS[TF]
            idx = {c.t: i for i, c in enumerate(cs)}
            early: list = []
            setups = run_engine(sym, cs, CFG, early_out=early)
            sigs = []
            for kind, group in (("confirmed", setups), ("early", early)):
                for x in group:
                    i = idx.get(x.detected_time)
                    if i is None:
                        continue
                    poi = in_poi(zones, cs[i].t, x.stop, x.is_long,
                                 BAR_SECONDS[HTF])
                    if not poi:                       # POI_REQUIRED, fixed
                        continue
                    o = simulate(cs, i, x.entry, x.stop, x.is_long,
                                 fill_bars=FILL_HOURS * 3600 // step,
                                 horizon_bars=HORIZON_HOURS * 3600 // step,
                                 **FEE)
                    if o.filled and o.exit_bar is None:
                        continue
                    d = htf_dir_at(hcs, hst, hdi, cs[i].t)
                    sigs.append(dict(
                        kind=kind, r=o.r, filled=o.filled,
                        second_half=cs[i].t >= mid_t,
                        grade=grade_of(kind == "early", poi, d, x.is_long, d)[0]))
            out.append(dict(sym=sym, turn_first=statistics.median(first),
                            turn_all=statistics.median(allb), sigs=sigs))
    return out, (statistics.median(days) if days else 42.0)


def stat(sigs):
    if len(sigs) < 25:
        return None
    rs = [s["r"] for s in sigs]
    f = [s for s in sigs if s["filled"]]
    w = [s for s in f if s["r"] > 0]
    m, se = mean_se(rs)
    return len(sigs), (len(w) / len(f) if f else 0.0), m, se, sum(rs)


def show(lab, v):
    if not v:
        print(f"  {lab:<28}{'too few':>10}")
        return
    n, win, m, se, tot = v
    print(f"  {lab:<28}{n:>6}{win:>7.0%}{m:>+11.3f} ± {se:.3f}{tot:>+9.1f}")


HEAD = f"  {'':<28}{'n':>6}{'win':>7}{'R/signal':>17}{'total':>9}"


def report(title, syms, key, pick):
    """`key` ranks the symbols; `pick` selects which signals of each count."""
    ranked = sorted(syms, key=lambda s: -s[key])
    print(f"\n{title}")
    print(HEAD)
    print("  -- cumulative: the top N symbols --")
    for n in BANDS:
        sigs = [g for s in ranked[:n] for g in s["sigs"] if pick(g)]
        show(f"top {n}", stat(sigs))
    print("  -- marginal: what each tier adds --")
    lo = 0
    for n in BANDS:
        sigs = [g for s in ranked[lo:n] for g in s["sigs"] if pick(g)]
        show(f"symbols {lo + 1}-{n}", stat(sigs))
        lo = n


def main():
    syms, span = asyncio.run(collect())
    tot = sum(len(s["sigs"]) for s in syms)
    print(f"\n{len(syms)} symbols · {tot} POI signals on {TF} over "
          f"{span:.0f} days · fees in")
    print("Pre-registered: more liquid pays MORE per signal, and the marginal")
    print("tiers must be MONOTONE for it to count.")

    print("\n" + "=" * 72)
    print("HONEST SPLIT — ranked on the first half, scored on the second")
    print("=" * 72)
    report("all POI signals", syms, "turn_first", lambda g: g["second_half"])
    report("confirmed only", syms, "turn_first",
           lambda g: g["second_half"] and g["kind"] == "confirmed")

    print("\n" + "=" * 72)
    print("NAIVE — ranked and scored on the same window (shows the bias)")
    print("=" * 72)
    report("all POI signals", syms, "turn_all", lambda g: True)

    print("\n" + "=" * 72)
    print("READ THE MARGINAL ROWS, NOT THE CUMULATIVE ONES")
    print("=" * 72)
    print("  Cumulative rows share most of their signals with each other, so")
    print("  they cannot disagree much and a gradient there is nearly")
    print("  automatic. The marginal tiers are disjoint. If those are not")
    print("  monotone in the honest split, there is nothing here.")


if __name__ == "__main__":
    main()
