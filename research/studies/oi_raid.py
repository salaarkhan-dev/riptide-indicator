"""Does OPEN INTEREST across the raid say whether the sweep was real?

WRITTEN BEFORE THE DATA EXISTED, DELIBERATELY. At the time this was committed
the market table held 6328 rows over 2.8 days, which is nowhere near enough to
answer anything. Writing the analysis plan now, while nobody can have seen an
OI result, is the strongest form of pre-registration available — the thresholds,
the direction, the bar and the refusal-to-report rule are all fixed before the
first number. Everything this project has been burned by came from choosing a
cut after seeing what it did.

THE HYPOTHESIS, and its direction is fixed in advance:

    OI FALLING across the raid   positions being CLOSED — forced exits, a stop
                                 run. The raid is what the strategy assumes and
                                 the reversal is the reasonable read.  BETTER.
    OI RISING across the raid    new money positioning INTO the move. That is a
                                 breakout with participation and the reversal is
                                 wrong.  WORSE.

A result in the opposite direction is a FAILED test, not a discovery. Saying so
here, before the data, is the entire point of writing this early.

WHY THIS IS WORTH THE WAIT. Every input tested in this project so far is a
rearrangement of the same OHLC — and thirteen families of them have come back
inside noise. Open interest is different information: two identical candles can
mean opposite things and nothing in the price series can separate them. The
volume work already pointed here from outside: sweep-to-setup conversion falls
monotonically from 26.4% to 6.5% as raid volume rises (+15.6 SE), which says
loud raids are breakouts. OI would say it directly rather than by inference.

THE DATA IS VERIFIED FIT FOR PURPOSE. From the first 2.8-day export:

    134 distinct bars, every step exactly 1800s — no missed snapshots
    0 of 23 long series with a frozen or stale OI value
    72% of bars move OI by more than 0.5%, 31% by more than 2%
    correlation of OI change with PRICE change: median +0.038

That last line is the one that mattered. If OI merely tracked price it would be
another OHLC rearrangement wearing a disguise. It does not.

    PYTHONPATH=. python3 research/studies/oi_raid.py riptideoi.csv
"""
import research.env                                     # noqa: F401  MUST be first

import csv                                              # noqa: E402
import sys                                              # noqa: E402
from collections import defaultdict                     # noqa: E402

from riptide.config import BAR_SECONDS, INTERVAL        # noqa: E402
from research.data import load_sync                     # noqa: E402
from research.harness import mean_se, report            # noqa: E402

STEP = BAR_SECONDS[INTERVAL]

# PRE-REGISTERED, all of it, before any OI number has been looked at.
#
# Buckets in percent change of open interest across the raid bar. Cut at zero
# because zero is where the hypothesis changes sign, not because any value was
# tried; the outer edges are round numbers either side of it.
EDGES = (-2.0, 0.0, 2.0)
LABELS = ("OI dumped", "OI fell", "OI rose", "OI surged")
# The bar is research.harness.report's, unchanged: 3 SE on top-minus-bottom,
# monotone across buckets, same sign on every split. And the sign must be the
# one predicted above — falling OI better than rising.
SE_BAR = 3.0
# Below this the script REFUSES to print a verdict and prints a countdown
# instead. This exists so that nobody — including whoever wrote it — can peek
# at an underpowered result and be steered by it. 610 signals is what a 0.30 R
# difference needs at 3 SE given the measured per-signal spread of 1.234 R;
# anything smaller than 0.30 R needs more, and the countdown says how much.
MIN_N = 610
SD_PER_SIGNAL = 1.234       # measured: 0.033 SE on 1399 early signals


def load_oi(path):
    """(symbol, bar_open_time) -> hold_vol, from a /oi CSV export.

    Rows are stamped with last_closed_bar(), which is the OPEN time of the bar
    that had just closed — the same key a Candle carries — so the join needs no
    adjustment.
    """
    out = {}
    with open(path) as f:
        for d in csv.DictReader(f):
            try:
                out[(d["symbol"], int(d["t"]))] = float(d["hold_vol"])
            except (KeyError, TypeError, ValueError):
                continue
    return out


def oi_delta(oi, symbol, bar_time):
    """Percent change in open interest ACROSS the raid bar.

    Needs the bar before as well as the bar itself, which is why a broken
    series is worth so much less than a continuous one, and why the logger
    stopped filtering to the currently-scanned symbols.
    """
    now = oi.get((symbol, bar_time))
    prev = oi.get((symbol, bar_time - STEP))
    if now is None or prev is None or prev <= 0:
        return None
    return 100.0 * (now - prev) / prev


def days_needed(have, want, per_day):
    return max(0.0, (want - have) / per_day) if per_day > 0 else float("inf")


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 1
    oi = load_oi(sys.argv[1])
    if not oi:
        print("no OI rows read")
        return 1
    times = sorted({t for _, t in oi})
    span_days = (times[-1] - times[0]) / 86400 or 1e-9
    print(f"OI ACROSS THE RAID — pre-registered, direction fixed in advance\n"
          f"{len(oi)} snapshots · {len({s for s, _ in oi})} symbols · "
          f"{span_days:.1f} days")

    rows = [r for r in load_sync(lookback=2000) if r.kind == "early"]
    joined = []
    for r in rows:
        # The raid bar, not the gap bar. The hypothesis is about what happened
        # to open positions AS the pool was taken.
        t = getattr(r.signal, "grab_time", 0) or r.signal.sweep_time
        d = oi_delta(oi, r.symbol, t - (t % STEP))
        if d is not None:
            r.oi = d
            joined.append(r)

    inwin = [r for r in rows
             if times[0] <= (getattr(r.signal, "grab_time", 0)
                             or r.signal.sweep_time) <= times[-1]]
    per_day = len(joined) / span_days
    print(f"\nJOIN")
    print(f"  early signals in the backtest        {len(rows)}")
    print(f"  ...whose raid falls in the OI window {len(inwin)}")
    print(f"  ...with OI on the raid bar AND the   {len(joined)}"
          f"   ({len(joined) / len(inwin) if inwin else 0:.0%} of them)")
    print(f"     bar before it")
    print(f"  usable signals per day               {per_day:.0f}")

    if len(joined) < MIN_N:
        print(f"\nUNDERPOWERED — NO VERDICT PRINTED, DELIBERATELY.")
        print(f"  This is not a failure to compute. Printing a number here is "
              f"how a\n  study gets fitted: the trendline slope work produced "
              f"+4.4 SE on one\n  half of its data and the opposite sign on "
              f"the other, and the only\n  reason that was caught is that "
              f"nobody was allowed to act on the first\n  half alone.\n")
        print(f"  {'detectable difference':<24}{'signals needed':>16}"
              f"{'days from now':>15}")
        for delta in (0.30, 0.20, 0.15):
            n = 2 * (SE_BAR * SD_PER_SIGNAL / delta) ** 2
            print(f"  {delta:<24.2f}{n:>16.0f}"
                  f"{days_needed(len(joined), n, per_day):>15.0f}")
        print(f"\n  Those are DISCOVERY numbers. A held-out half doubles every "
              f"row, and\n  this project does not act on anything that has not "
              f"survived one.")
        print(f"  Nothing to do but wait — the logger is already running and "
              f"verified.")
        return 0

    m, se = mean_se([r.r for r in joined])
    print(f"\n  baseline on the joined set  {m:+.3f} ± {se:.3f} R")
    disc = [r for r in joined if not r.split_window]
    held = [r for r in joined if r.split_window]
    for name, sub in (("DISCOVERY (newer half)", disc),
                      ("HELD OUT (older half)", held)):
        report(f"{name} — OI change across the raid, %",
               sub, lambda r: r.oi, edges=EDGES, labels=LABELS,
               se_bar=SE_BAR)
    print("\nPRE-REGISTERED DIRECTION: falling OI must score BETTER than "
          "rising.\nA result the other way is a FAILED test, not a discovery.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
