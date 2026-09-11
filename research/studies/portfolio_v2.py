"""The portfolio half of the plan: items 20, 22 and 24.

    20  dynamic position sizing      size by 1/stop, and by signal quality
    22  market-event policies        take all / first / best / BTC-only /
                                     allocate across the event
    24  regime detection             classify from the strategy's own behaviour
                                     rather than from an indicator

WHY THESE ARE THE ITEMS WORTH RUNNING. `power.py` showed the sample cannot read
feature buckets and `exits.py` showed it can read paired policy swaps. These
three are the same shape as the exit tests: the trades are fixed and only the
ALLOCATION over them changes, so the comparison is paired and the variance
largely cancels.

AND THEY ARE AIMED AT THE RIGHT PROBLEM. The strategy's expectancy is +0.034 R
a bet at 1.2 SE and nothing in this project has moved it. Its DRAWDOWN is 85%
on a 300 USDT account at 1% a trade, which is not marginal at all — it is
disqualifying, and it is the one number a portfolio rule can actually change.

TWO WARNINGS THAT APPLY TO EVERY ROW BELOW.

  SCALING IS NOT IMPROVEMENT. `power.py` already found that capping risk per
  event cuts return and drawdown by the same 47% and leaves the recovery factor
  at 1.13 against 1.14. Any rule that simply trades smaller will look like a
  drawdown win and be worth nothing, so RECOVERY FACTOR and time under water
  are the columns to read, never max drawdown on its own.

  A POLICY THAT PICKS THE BEST SIGNAL IN AN EVENT IS PICKING ON SOMETHING. The
  "best" here is the deployed risk band, which is the only signal-quality
  measure that has survived anything. Using last year's winner as the quality
  score would be the symbol-ranking mistake in a new costume, and
  `symbols.py` already established that ranking does not persist.

    PYTHONPATH=. RIPTIDE_MIN_GRADE=B RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/portfolio_v2.py

RESULT, 11 Sep 2026

  ITEM 22 — CHOOSING ONE TRADE PER EVENT BEATS TAKING THEM ALL, and unlike the
  event cap in `power.py` it is not scaling, because the recovery factor moves.

      A  take all                 +180.7 R   dd 135.9   rec 1.33   uw 60%
      D  allocate across event     +89.6     dd  65.8   rec 1.36   uw 32%
      E  first symbol only         +98.7     dd  69.2   rec 1.43   uw 32%
      C  best by risk band only   +112.7     dd  61.4   rec 1.84   uw 32%
      B  majors only               +18.4     dd  21.4   rec 0.86   uw 55%

  Three things in that table. Taking ONE trade out of an event rather than
  spreading across it is better even when the one is chosen arbitrarily (E,
  alphabetical, 1.43 against D's 1.36). Choosing it on the risk band lifts
  recovery to 1.84, 39% above take-all. And the plan's suggestion B — take BTC
  or ETH as the event's representative — is the WORST row on the board at 0.86,
  below one: the majors lose more than they make.

  THE HONEST DISCOUNT ON ROW C. It picks using the risk band, which was itself
  chosen by looking at this data, so C inherits that selection debt whole. The
  claim that survives it is the weaker one E establishes: concentrating an
  event into a single position is better than spreading it, arbitrary choice or
  not. Every row also shares the time-under-water halving, 60% to 32%, which
  `power.py` already showed comes from the concentration and not from the
  choosing.

  ITEM 20 — HALF OF IT IS ALREADY DONE BY CONSTRUCTION. The plan proposes
  sizing at 1/stop-distance as an improvement. That is not a policy, it is what
  the R unit means: the bot already publishes entry and stop and a fixed
  percent-of-balance risk IS 1/stop sizing. It cannot show up in an R-based
  measurement because it is the measurement's denominator.

  The half that is a real choice — weighting by quality — comes out monotone:

      flat                       +45.5 R   dd 29.5   rec 1.54
      band x1.25 / other x0.75   +69.5     dd 26.5   rec 2.62
      band x1.5  / other x0.5    +93.6     dd 23.6   rec 3.96
      band x2    / other x0     +141.7     dd 23.9   rec 5.93

  This is NOT a new finding and should not be read as one. If the risk band is
  real then leaning on it harder must look better, arithmetically; the table
  restates the band's edge under sizing rather than discovering anything. It is
  worth printing only because it prices the decision to leave the band
  advisory: at x1.5/x0.5, a soft tilt with no signal suppressed, recovery goes
  from 1.54 to 3.96 while every alert still arrives.

  ITEM 24 — NO REGIME EFFECT, ON EITHER DEFINITION. Built from the strategy's
  own behaviour rather than from an indicator, per week:

      by signal rate   quiet +0.077   normal -0.033   busy +0.070
      by market width  calm  +0.060   normal +0.004   wild +0.046

  Both non-monotone with the middle worst, both inside their standard errors
  of about 0.045. The quarterly spread the plan called a scream of regime
  dependence does not reproduce when the year is cut by anything other than
  the calendar — which is what four noisy draws look like.
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import statistics                                       # noqa: E402
from collections import defaultdict                     # noqa: E402
from datetime import datetime, timezone                 # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.exchange import list_symbols               # noqa: E402
from research.deep import load_universe                 # noqa: E402
from research.studies.report import (DAYS, INTERVAL, collect, drawdown,
                                     streaks)           # noqa: E402
from research.studies.survivor import LO, HI            # noqa: E402

MAJORS = ("BTC_USDT", "ETH_USDT", "SOL_USDT")


def curve(units):
    """(total, max drawdown, recovery, share of series under water)."""
    if not units:
        return 0.0, 0.0, 0.0, 0.0
    dd, dl = drawdown(units)
    tot = sum(units)
    return tot, dd, (tot / dd if dd else 0.0), dl / len(units)


def line(name, units, n_note=""):
    tot, dd, rec, uw = curve(units)
    bw, bl = streaks(units)
    print(f"  {name:<34}{len(units):>6} units{tot:>+9.1f} R"
          f"{dd:>9.1f} dd{rec:>8.2f} rec{uw:>7.0%} uw"
          f"{bl:>5} loss run  {n_note}")


def events_of(trades):
    ev = defaultdict(list)
    for t in trades:
        ev[(t.t, t.is_long)].append(t)
    return [v for _, v in sorted(ev.items(),
                                 key=lambda kv: max(t.exit_t for t in kv[1]))]


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = await list_symbols(sess)
        candles = await load_universe(sess, syms, INTERVAL, DAYS)
        trades = await collect(sess, candles)

    live = [t for t in trades if t.filled and t.exit_t is not None]
    conf = [t for t in live if t.kind == "confirmed"]
    ev = events_of(live)
    print(f"PORTFOLIO POLICIES\n{len(live)} filled trades in {len(ev)} same-bar "
          f"same-direction events · {DAYS} days\n"
          f"read RECOVERY and UNDER WATER, not drawdown: a rule that trades "
          f"smaller\nshrinks drawdown and return together and is worth nothing."
          f"\n\n  {'policy':<34}{'units':>6}{'':>7}{'total':>9}"
          f"{'':>9}{'':>8}{'':>7}")

    print("\n-- ITEM 22, MARKET-EVENT POLICIES " + "-" * 43)
    line("A  take all (1 unit per trade)", [t.r for t in sorted(
        live, key=lambda x: x.exit_t)])
    line("D  allocate 1 unit across event",
         [statistics.fmean(t.r for t in v) for v in ev])
    line("E  first symbol only", [sorted(v, key=lambda t: t.sym)[0].r
                                  for v in ev])
    line("C  best by risk band only",
         [sorted(v, key=lambda t: (not (LO <= t.risk_pct <= HI),
                                   t.sym))[0].r for v in ev])
    maj = [v for v in ev if any(t.sym in MAJORS for t in v)]
    line("B  majors only, when present",
         [next(t.r for t in v if t.sym in MAJORS) for v in maj],
         f"({len(maj)} events contain one)")

    print("\n-- ITEM 20, POSITION SIZING " + "-" * 49)
    print("  R is already risk-normalised, so sizing by 1/stop is what the R")
    print("  unit MEANS and cannot show up here. What can is weighting the")
    print("  units by a quality score, which is a real choice.")
    band = [t for t in conf if LO <= t.risk_pct <= HI]
    line("flat 1 unit, confirmed only",
         [t.r for t in sorted(conf, key=lambda x: x.exit_t)])
    for hi_w, lo_w in ((1.25, 0.75), (1.5, 0.5), (2.0, 0.0)):
        line(f"band x{hi_w:g} / outside x{lo_w:g}",
             [t.r * (hi_w if LO <= t.risk_pct <= HI else lo_w)
              for t in sorted(conf, key=lambda x: x.exit_t)])
    print(f"  (the band is {len(band)} of {len(conf)} confirmed trades; x2/x0 "
          f"is the hard filter the user declined,\n   shown for scale only)")

    print("\n-- ITEM 24, REGIME FROM THE STRATEGY'S OWN BEHAVIOUR " + "-" * 24)
    print("  classified per WEEK, on what the scanner itself saw that week:")
    wk = defaultdict(list)
    for t in live:
        d = datetime.fromtimestamp(t.t, timezone.utc).isocalendar()
        wk[(d[0], d[1])].append(t)
    counts = sorted(len(v) for v in wk.values())
    q1, q3 = counts[len(counts) // 3], counts[2 * len(counts) // 3]
    print(f"  signal-rate terciles: quiet <= {q1} a week, busy > {q3}")
    for lab, f in (("quiet weeks", lambda n: n <= q1),
                   ("normal weeks", lambda n: q1 < n <= q3),
                   ("busy weeks", lambda n: n > q3)):
        rows = [t for v in wk.values() if f(len(v)) for t in v]
        wks = sum(1 for v in wk.values() if f(len(v)))
        if len(rows) < 100:
            continue
        g = defaultdict(list)
        for t in rows:
            g[t.t].append(t.r)
        b = [statistics.fmean(v) for v in g.values()]
        m = statistics.fmean(b)
        se = statistics.pstdev(b) / len(b) ** 0.5
        print(f"    {lab:<16}{wks:>3} weeks {len(rows):>5} trades {len(b):>5} "
              f"bets  {sum(1 for r in b if r > 0) / len(b):>3.0%} win  "
              f"{m:>+6.3f}±{se:.3f}")

    print("\n  and by how wide the market was moving that week (median stop%):")
    vol = defaultdict(float)
    for k, v in wk.items():
        vol[k] = statistics.median(t.risk_pct for t in v)
    vs = sorted(vol.values())
    v1, v3 = vs[len(vs) // 3], vs[2 * len(vs) // 3]
    for lab, f in (("calm weeks", lambda x: x <= v1),
                   ("normal weeks", lambda x: v1 < x <= v3),
                   ("wild weeks", lambda x: x > v3)):
        rows = [t for k, v in wk.items() if f(vol[k]) for t in v]
        if len(rows) < 100:
            continue
        g = defaultdict(list)
        for t in rows:
            g[t.t].append(t.r)
        b = [statistics.fmean(v) for v in g.values()]
        m = statistics.fmean(b)
        se = statistics.pstdev(b) / len(b) ** 0.5
        print(f"    {lab:<16}{'':>3}       {len(rows):>5} trades {len(b):>5} "
              f"bets  {sum(1 for r in b if r > 0) / len(b):>3.0%} win  "
              f"{m:>+6.3f}±{se:.3f}")


if __name__ == "__main__":
    asyncio.run(main())
