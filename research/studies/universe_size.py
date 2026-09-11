"""Did widening the universe from 60 symbols to 120 help or dilute?

ASKED BECAUSE THE ANSWER WAS ASSUMED RATHER THAN MEASURED. The floor was
lowered from 3M to 1M of 24h turnover on 11 Sep on a power argument: bets scale
as symbols^0.905, so 69 to 120 takes the minimum detectable effect from about
0.32 to 0.25 and nearly doubles the forward observation rate. The liquidity
bands had been checked for a PENALTY and none was detectable — +0.036, -0.026
and -0.002 R per bet across ranks 1-60, 61-90 and 91-120, every one inside its
own standard error of zero and of the others.

"No detectable penalty" is not the same claim as "the combination is better",
and this file asks the second question, which is the one that matters to
somebody actually reading the alerts.

IT HAS THREE ANSWERS, BECAUSE IT DEPENDS ENTIRELY ON WHAT THE READER DOES.
That is the finding, and collapsing it to one number would be the mistake:

    take every alert            60: +0.036 R/bet     120: +0.016 R/bet
    one per cluster, any band   60: recovery 3.01    120: recovery 2.09
    one per cluster, in band    60: recovery 1.85    120: recovery 2.94

The wider universe DILUTES a reader who takes everything and HELPS one who
filters to the risk band, because the extra symbols add far more mediocre
signals than good ones — and the band is what separates them. The mechanism
that was hoped for is NOT the one that operated: bigger clusters were supposed
to be likelier to contain an in-band member, and that barely moved (63% to
66%, median cluster size 1 either way). What actually happened is simpler —
twice the symbols produce roughly twice the in-band opportunities, 3.5 a day
against 6.0, and the band's quality holds up across them.

EVERY DIFFERENCE HERE IS INSIDE ITS OWN NOISE. On 254 picks the standard error
of R per pick is about 0.088, so +0.197 against +0.149 is a difference of
0.048 with an error bar twice its size. Recovery factors are worse still: a
maximum drawdown is an extreme-value statistic read off ONE path, and it has no
usable error bar at all. Read the direction of these rows, never the magnitude,
and do not let the fact that they point different ways in different slices
become a story about which slice is right.

    PYTHONPATH=. RIPTIDE_MIN_GRADE=B RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/universe_size.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import json                                             # noqa: E402
import os                                               # noqa: E402
import statistics                                       # noqa: E402
from collections import defaultdict                     # noqa: E402

import aiohttp                                          # noqa: E402

from research.deep import load_universe                 # noqa: E402
from research.harness import mean_se                    # noqa: E402
from research.studies.report import (DAYS, INTERVAL, bets_of, collect,
                                     drawdown)          # noqa: E402
from research.studies.survivor import LO, HI            # noqa: E402

RANKED = "/tmp/holdout.json"    # symbols by turnover, written by the loader


def rank(t):
    """The deployed event_rank, reproduced on a Trade row rather than a Setup.

    Kept in step with riptide/scanner.py by hand rather than imported, because
    that function reads a live Setup and these are backtest rows. If the three
    tiers there ever change, they change here too.
    """
    r = t.risk_pct
    return (0 if LO <= r <= HI else (1 if r < LO else 2),
            0 if t.kind == "confirmed" else 1, t.sym)


def picks(trades, band_only=False):
    ev = defaultdict(list)
    for t in trades:
        ev[(t.t, t.is_long)].append(t)
    out = []
    for v in sorted(ev.values(), key=lambda g: max(t.exit_t for t in g)):
        b = min(v, key=rank)
        tier = rank(b)[0]
        if tier == 0 or (not band_only and tier != 2):
            out.append(b)
    return out


def line(lab, rs):
    m, se = mean_se(rs)
    dd, _ = drawdown(rs)
    tot = sum(rs)
    print(f"  {lab:<26}{len(rs):>7}{len(rs) / DAYS:>7.1f}"
          f"{sum(1 for r in rs if r > 0) / len(rs):>6.0%}{m:>+9.3f}±{se:.3f}"
          f"{tot:>+9.1f}{dd:>8.1f}{tot / dd if dd else 0:>10.2f}")


async def main():
    ranked = json.load(open(RANKED))["ranked"]
    have = {f.split(".")[0] for f in
            os.listdir(os.environ["RIPTIDE_DEEP_CACHE"]) if ".Min30." in f}
    syms = [x for x in ranked[:120] if x in have]
    async with aiohttp.ClientSession() as sess:
        cs = await load_universe(sess, syms, INTERVAL, DAYS)
        allt = [t for t in await collect(sess, cs)
                if t.filled and t.exit_t is not None]
    top60 = set(ranked[:60])
    sets = (("60 symbols", lambda t: t.sym in top60),
            ("120 symbols", lambda t: True))

    print(f"UNIVERSE SIZE\n{len(syms)} symbols cached, {len(allt)} filled "
          f"trades, {DAYS} days.\nevery difference below is inside its own "
          f"noise. read direction, not magnitude.\n")
    print(f"  {'':<26}{'n':>7}{'/day':>7}{'win':>6}{'R each':>16}"
          f"{'total':>9}{'maxDD':>8}{'recovery':>10}")

    print("\n-- take every alert " + "-" * 57)
    for lab, sel in sets:
        b = bets_of([t for t in allt if sel(t)])
        line(lab + " (per bet)", b)

    print("\n-- one per cluster, any band " + "-" * 48)
    for lab, sel in sets:
        line(lab, [t.r for t in picks([t for t in allt if sel(t)])])

    print("\n-- one per cluster, IN THE RISK BAND " + "-" * 40)
    for lab, sel in sets:
        line(lab, [t.r for t in
                   picks([t for t in allt if sel(t)], band_only=True)])

    print("\n-- the same, confirmed setups only " + "-" * 42)
    for lab, sel in sets:
        line(lab, [t.r for t in
                   picks([t for t in allt if sel(t)], band_only=True)
                   if t.kind == "confirmed"])

    print("\n-- the mechanism that was hoped for, and did not happen " + "-" * 21)
    for lab, sel in sets:
        ev = defaultdict(list)
        for t in [t for t in allt if sel(t)]:
            ev[(t.t, t.is_long)].append(t)
        multi = [v for v in ev.values() if len(v) > 1]
        inband = sum(1 for v in multi
                     if any(LO <= t.risk_pct <= HI for t in v))
        print(f"  {lab:<14} clusters of 2+ {len(multi):>5}   with an in-band "
              f"member {inband / len(multi):>4.0%}   median cluster size "
              f"{statistics.median(len(v) for v in ev.values()):.0f}")
    print("  bigger clusters were supposed to be likelier to hold an in-band")
    print("  signal. They are barely likelier. The gain is simply MORE of them.")


if __name__ == "__main__":
    asyncio.run(main())
