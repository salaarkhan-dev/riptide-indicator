"""What a 60% win rate would actually cost.

Asked directly: "I want to improve the win rate to at least 60%." The win rate
is the one number in this system that can be set to almost any value on
demand, because it is not a property of the signals — it is a property of the
TARGET. Move the target down and more trades reach it. That is arithmetic, not
edge, and it is why the win rate is never quoted alone anywhere in this
project.

So this does not hunt for a filter. Twenty-one filters have been tried and one
survived. This prices the dial instead: for each target, the win rate you get
and the R per signal you pay for it. The honest question is not "can the win
rate reach 60%" — it can — but "is the version of this strategy that wins 60%
of the time worth more than the version that wins 45%".

Both columns are needed to answer that and the answer is not obvious in
advance, which is the only reason this is worth measuring rather than
asserting.

Scored exactly as the live policy scores: live universe, both timeframes, POI
required, grade from riptide.engine.grade_of, unfilled counted as a zero,
maker in and maker-or-taker out.

    PYTHONPATH=. python3 research/studies/winrate.py
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
TARGETS = (0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0, 4.0)


async def collect():
    """Every signal the bot would send, kept as (candles, bar, signal) so each
    can be re-scored at every target without re-fetching."""
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
                        if not poi:                 # POI_REQUIRED
                            continue
                        d = htf_dir_at(hcs, hst, hdi, cs[i].t)
                        out.append((cs, i, x, tf,
                                    grade_of(kind == "early", poi, d,
                                             x.is_long, d)[0]))
    return out, (statistics.median(days) if days else 42.0)


def score(rows, target: float):
    """Re-score every signal at one target. An unfilled signal is a zero and
    pays no fee; a timeout that never resolved is dropped, as everywhere."""
    rs, fills, wins = [], 0, 0
    for cs, i, x, tf, g in rows:
        step = BAR_SECONDS[tf]
        o = simulate(cs, i, x.entry, x.stop, x.is_long,
                     target_r=target,
                     fill_bars=FILL_HOURS * 3600 // step,
                     horizon_bars=HORIZON_HOURS * 3600 // step, **FEE)
        if o.filled and o.exit_bar is None:
            continue
        rs.append(o.r)
        if o.filled:
            fills += 1
            if o.r > 0:
                wins += 1
    if not rs:
        return None
    m, se = mean_se(rs)
    return dict(n=len(rs), fill=fills / len(rs),
                win=(wins / fills if fills else 0.0), m=m, se=se,
                total=sum(rs))


HEAD = (f"  {'target':>7}{'n':>7}{'fill':>7}{'WIN':>7}{'R/signal':>17}"
        f"{'total R':>10}")


def table(label, rows):
    print(f"\n{label}  ({len(rows)} signals)")
    print(HEAD)
    hit60 = None
    for t in TARGETS:
        v = score(rows, t)
        if not v:
            continue
        star = ""
        if v["win"] >= 0.60 and hit60 is None:
            hit60 = (t, v)
            star = "  <- 60% reached here"
        print(f"  {t:>7.2f}{v['n']:>7}{v['fill']:>7.0%}{v['win']:>7.0%}"
              f"{v['m']:>+11.3f} ± {v['se']:.3f}{v['total']:>+10.1f}{star}")
    return hit60


def main():
    rows, span = asyncio.run(collect())
    print(f"\n{len(rows)} alerts over {span:.0f} days · POI required · "
          f"fees in · unfilled counted as zero")
    print("The win rate is a function of the TARGET. Both columns, always.")

    print("\n" + "=" * 78)
    print("EVERY ALERT THE BOT SENDS")
    print("=" * 78)
    hit = table("all grades", rows)
    best = max(((t, score(rows, t)) for t in TARGETS),
               key=lambda kv: kv[1]["m"] if kv[1] else -9)

    print("\n" + "=" * 78)
    print("BY GRADE — does a better signal reach 60% at a target worth taking?")
    print("=" * 78)
    for g in ("A", "B"):
        table(f"grade {g}", [r for r in rows if r[4] == g])

    print("\n" + "=" * 78)
    print("THE ANSWER")
    print("=" * 78)
    cur = score(rows, 2.0)
    print(f"  shipped, 2R      win {cur['win']:.0%}   "
          f"{cur['m']:+.3f} R/signal   {cur['total']:+.1f} R total")
    if hit:
        t, v = hit
        loss = (v["total"] - cur["total"])
        print(f"  first 60% win    at a {t:g}R target: win {v['win']:.0%}   "
              f"{v['m']:+.3f} R/signal   {v['total']:+.1f} R total")
        print(f"  price of 60%     {loss:+.1f} R over {span:.0f} days, "
              f"{v['m'] - cur['m']:+.3f} per signal")
    else:
        print("  60% is not reached at ANY target down to "
              f"{min(TARGETS):g}R — the win rate cannot be bought at all here.")
    print(f"  best R/signal    at {best[0]:g}R: {best[1]['m']:+.3f} "
          f"(win {best[1]['win']:.0%})")


if __name__ == "__main__":
    main()
