"""What effect size can this sample actually resolve, and what does an event
cap do to drawdown?

TWO QUESTIONS, ASKED BECAUSE A RESEARCH PLAN LANDED THAT ASSUMES BOTH ANSWERS.

THE FIRST IS ARITHMETIC AND IT DECIDES HOW MUCH RESEARCH IS WORTH DOING. A
proposal to instrument every setup with eighty features and test twelve
hypotheses, discovery-then-out-of-sample, is only as good as the smallest
effect the sample can see. Per-bet standard deviation here is about 1.4 R, so
the minimum detectable effect at conventional power is 2.8 x sd / sqrt(n)
for a two-arm comparison — and n is not the trade count, it is the BET count,
because sixty perpetuals raiding together on one bar is one draw. Splitting
503 confirmed bets into a discovery half and an out-of-sample half, then into
terciles inside each half, leaves cells of forty. This file prints what those
cells can and cannot resolve, so the plan can be sized against the data rather
than against the ambition.

THE SECOND IS THE PLAN'S BEST IDEA AND IT IS NOT ABOUT EXPECTANCY AT ALL.
Grouping simultaneous signals into one MARKET EVENT and capping risk per event
rather than per trade cannot change the edge — the same trades happen — but it
changes the drawdown, and drawdown is where this system actually fails: 85% on
a 300 USDT account at 1% a trade. The good news is that this needs no new
instrumentation to test, because the per-event portfolio already exists in this
codebase under another name. `bets_of()` averages every symbol firing on the
same bar, which IS an equal-risk split across one event. The bet series that
every standard error in this project is computed on is the equity curve of the
event-capped portfolio. So the comparison is free.

    PYTHONPATH=. RIPTIDE_MIN_GRADE=B RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/power.py

RESULT, 11 Sep 2026

  POWER. The minimum detectable effect, against the largest effect this project
  has ever found (+0.292 R/bet, the stop band in against out):

      population                        bets      MDE
      all tradeable                     2395     0.152
        discovery / OOS halves          1198     0.214
        a tercile inside each half       399     0.371
      confirmed only                     489     0.351
        discovery / OOS halves           244     0.496
        a tercile inside each half        82     0.860

  A tercile inside a half of the confirmed stream needs an effect THREE TIMES
  larger than anything ever measured here before it can tell that effect from
  noise. The only cell in the table with the power to see +0.292 is the full
  undivided sample of everything tradeable — which is precisely the cell that
  out-of-sample discipline forbids using.

  THAT IS THE BIND, AND IT IS NOT A DESIGN FLAW THAT BETTER DESIGN FIXES. With
  503 confirmed bets you may have out-of-sample validation or you may have
  power. Not both. More features do not help: features are free, bets are not,
  and every feature is a deterministic function of bars already on disk. The
  scarce resource is FORWARD TIME.

  MARKET EVENTS. 4239 trades collapse into 2416 same-bar same-direction
  events; median size 1, mean 1.8, max 20.

  The plan's H12 — bigger event trades worse — is NOT supported. By size:
  +0.040, +0.067, -0.082, -0.059, then +0.452 for the 21 events of ten or
  more. Non-monotone, and the largest events are the best cell. That shape is
  noise, not a gradient.

  AND CAPPING RISK PER EVENT IS NOT THE FREE DRAWDOWN WIN IT LOOKS LIKE:

      1 unit per TRADE   +150.5 R   max drawdown 131.8 R   recovery 1.14
      1 unit per EVENT    +80.4 R   max drawdown  70.9 R   recovery 1.13

  Return and drawdown both fall by 47%, so the recovery factor does not move.
  In risk-adjusted terms, capping per event is arithmetically the same as
  trading half size — it buys nothing a smaller position would not.

  The one thing it does buy is PATH: time under water falls from 60% of the
  series to 32%. That is real and it is not scaling. Whether halving the
  stretch spent below a previous peak is worth halving the return is a
  preference, not a measurement, and it belongs to whoever holds the account.
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import statistics                                       # noqa: E402
from collections import defaultdict                     # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.exchange import list_symbols               # noqa: E402
from research.deep import load_universe                 # noqa: E402
from research.studies.report import (DAYS, INTERVAL, bets_of, collect,
                                     drawdown)          # noqa: E402
from research.studies.survivor import LO, HI            # noqa: E402

# 2.80 = z(0.975) + z(0.80), the usual 5%-significance / 80%-power constant,
# doubled under the root for a two-arm difference of means.
MDE_K = 2.80


def mde(sd, n_per_arm):
    """Smallest difference between two arms this many bets can resolve."""
    return MDE_K * sd * (2 / n_per_arm) ** 0.5


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = await list_symbols(sess)
        candles = await load_universe(sess, syms, INTERVAL, DAYS)
        trades = await collect(sess, candles)

    live = [t for t in trades if t.filled and t.exit_t is not None]
    conf = [t for t in live if t.kind == "confirmed"]
    cell = [t for t in conf if LO <= t.risk_pct <= HI]

    print("PART 1 — WHAT THIS SAMPLE CAN RESOLVE")
    print("minimum detectable effect, two arms, 5% significance and 80% power.")
    print("anything smaller than the MDE is a coin toss no matter how carefully")
    print("the study is designed.\n")
    print(f"  {'population':<34}{'bets':>7}{'sd R':>8}{'MDE R/bet':>12}")
    for name, rows in (("all tradeable", live),
                       ("confirmed only", conf),
                       (f"confirmed, stop {LO}-{HI}%", cell)):
        b = bets_of(rows)
        sd = statistics.pstdev(b)
        print(f"  {name:<34}{len(b):>7}{sd:>8.2f}{mde(sd, len(b) / 2):>12.3f}")
        for split, frac in (("  ... split discovery / OOS", 2),
                            ("  ... then a tercile inside each", 6)):
            n = len(b) / frac
            print(f"  {split:<34}{n:>7.0f}{'':>8}{mde(sd, n / 2):>12.3f}")

    print("\n  for scale, the largest effects this project has ever measured:")
    b_cell = bets_of(cell)
    b_out = bets_of([t for t in conf if not (LO <= t.risk_pct <= HI)])
    print(f"    the surviving stop band, in-vs-out      "
          f"{statistics.fmean(b_cell) - statistics.fmean(b_out):>+7.3f} R/bet")
    print(f"    the whole strategy against zero         "
          f"{statistics.fmean(bets_of(live)):>+7.3f} R/bet")

    # ------------------------------------------------------------------ events
    print("\n\nPART 2 — MARKET EVENTS, AND WHAT CAPPING THEM COSTS")
    ev = defaultdict(list)
    for t in live:
        ev[(t.t, t.is_long)].append(t)
    sizes = sorted(len(v) for v in ev.values())
    print(f"  {len(live)} trades collapse into {len(ev)} same-bar same-direction "
          f"events")
    print(f"  event size: median {statistics.median(sizes)}, "
          f"mean {statistics.fmean(sizes):.1f}, max {sizes[-1]}, "
          f"{sum(1 for s in sizes if s >= 5)} events of 5 or more")

    print("\n  does a bigger event trade worse? (the plan's hypothesis H12)")
    buckets = ((1, 1), (2, 2), (3, 4), (5, 9), (10, 99))
    for lo_, hi_ in buckets:
        rows = [v for v in ev.values() if lo_ <= len(v) <= hi_]
        if len(rows) < 15:
            continue
        rs = [statistics.fmean(t.r for t in v) for v in rows]
        m = statistics.fmean(rs)
        se = statistics.pstdev(rs) / len(rs) ** 0.5
        lab = f"{lo_}" if lo_ == hi_ else f"{lo_}-{hi_ if hi_ < 99 else '+'}"
        print(f"    size {lab:<6} {len(rows):>5} events  "
              f"{sum(1 for r in rs if r > 0) / len(rs):>3.0%} win  "
              f"{m:>+7.3f} +/- {se:.3f} R")

    print("\n  THE PORTFOLIO COMPARISON. Same trades, same order, same exits —")
    print("  only how risk is allocated changes.")
    for name, series in (
            ("1 unit per TRADE", [t.r for t in sorted(
                live, key=lambda x: x.exit_t)]),
            ("1 unit per EVENT, split across it", [
                statistics.fmean(t.r for t in v)
                for _, v in sorted(ev.items(),
                                   key=lambda kv: max(t.exit_t for t in kv[1]))])):
        dd, dl = drawdown(series)
        tot = sum(series)
        print(f"    {name:<36} {len(series):>5} units  {tot:>+7.1f} R  "
              f"max drawdown {dd:>6.1f} R  recovery {tot / dd if dd else 0:>5.2f}"
              f"  under water {dl / len(series):>4.0%}")
    print("  The per-event row is what /stats already computes as a 'bet'. The")
    print("  edge is identical by construction; only the risk profile differs.")


if __name__ == "__main__":
    asyncio.run(main())
