"""Which cells to actually TAKE — and how long the losing runs get.

TWO QUESTIONS, ONE PASS.

THE FIRST CAME FROM A REAL LOSING RUN: five or six trades taken, all losers.
That needs an answer that is arithmetic rather than reassurance, so every
policy below reports its WORST OBSERVED LOSING STREAK alongside its return. A
38% win rate means 62% of trades lose, and six in a row has a 0.62^6 = 5.7%
chance of starting at any given trade — over a few dozen trades it is not
unlucky, it is scheduled. The streak column says what each policy actually
produced rather than what the binomial predicts, which is the honest version.

THE SECOND IS THE USER'S OWN IDEA AND IT IS THE RIGHT ONE. "Give priority to
30m confirmed, it has the better win rate." Every earlier attempt in this
project to raise the win rate did it by changing the EXIT — partials,
break-even, closer targets — and every one of them bought win rate with return,
because the win rate is a dial the exit sets. `exit_grid.py` priced that: 65%
wins for -3% return, or 39% wins for +20%.

SELECTING A BETTER CELL IS A DIFFERENT MECHANISM ENTIRELY. It does not move the
dial; it takes fewer trades from a population that genuinely wins more often.
`min15_worth.py` found Min30 confirmed at grade B running 50% wins and +0.458 R
per signal — the strongest cell measured anywhere in this project, and four
times the R of the pooled stream. That is the one honest route to a higher win
rate, and it has never been priced as a policy.

WHAT IT COSTS IS TRAFFIC, and that is the whole trade-off. Confirmed setups are
outnumbered by early ones roughly 5.6 to 1, so a confirmed-only rule is a
different product: far fewer alerts, and a real chance of quiet days.

PRE-REGISTERED, BEFORE THE FIRST NUMBER

  Every policy is reported on the same axes and NO policy is declared the
  winner by R alone. The columns that decide are R per drawdown and signals
  per day, because a rule that returns more while trading four times less is
  not strictly better — it is a different thing to live with.

  The held-out half is reported for every policy. A cell chosen because it
  looked strong on the full window is exactly the mistake three studies in
  this project have already made.

  EXPECTATION: confirmed-only wins on R per signal and on win rate, loses badly
  on signals per day, and its held-out sample is too thin to be conclusive.

    PYTHONPATH=. RIPTIDE_MIN_GRADE=B python3 research/studies/priority.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import math                                             # noqa: E402
import json                                             # noqa: E402
import os                                               # noqa: E402
import statistics                                       # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import MIN_GRADE                    # noqa: E402
from riptide.exchange import list_symbols               # noqa: E402
from research.harness import mean_se                    # noqa: E402
from research.studies.min15_worth import Row, collect, dd_r  # noqa: E402

BANDS = "ABCD"


def worst_streak(rows):
    """Longest run of consecutive losers, in time order, and how long it took.

    THE SPAN IS THE POINT. A binomial says a 50%-win policy should almost never
    produce thirteen losses in a row over eighty trades. It does anyway, because
    these signals are not independent draws: when the whole market turns against
    the book, every open trade loses at once. So the streak length alone would
    overstate how unlucky the run was. Reported with the hours it spanned, a
    long streak inside a few hours reads as ONE market event rather than
    thirteen, which is both the truth and the more useful thing to know.
    """
    run = worst = 0
    t0 = start = 0
    span = 0.0
    for x in sorted(rows, key=lambda z: z.t):
        if x.r > 0:
            run = 0
        else:
            if run == 0:
                start = x.t
            run += 1
            t0 = x.t
            if run > worst:
                worst, span = run, (t0 - start) / 3600.0
    return worst, span


def keep(rows, tfs, kinds, grade):
    cut = BANDS.index(grade)
    return [x for x in rows if x.filled and x.poi and x.tf in tfs
            and x.kind in kinds and BANDS.index(x.grade) <= cut]


POLICIES = (
    ("Min30+Min15, both kinds", ("Min30", "Min15"), ("early", "confirmed"), "B"),
    ("Min30 only, both kinds", ("Min30",), ("early", "confirmed"), "B"),
    ("Min15 only, both kinds", ("Min15",), ("early", "confirmed"), "B"),
    ("Min30 + Min15 CONFIRMED", ("Min30", "Min15"), ("confirmed",), "B"),
    ("Min30 CONFIRMED only", ("Min30",), ("confirmed",), "B"),
    ("Min15 CONFIRMED only", ("Min15",), ("confirmed",), "B"),
    ("Min30 EARLY only", ("Min30",), ("early",), "B"),
    ("Min15 EARLY only", ("Min15",), ("early",), "B"),
    ("everything at grade A", ("Min30", "Min15"), ("early", "confirmed"), "A"),
)


def panel(title, rows, days):
    print(f"\n{title}")
    print(f"  {'policy':<28}{'n':>6}{'/day':>7}{'win':>6}{'R/sig':>9}{'SE':>7}"
          f"{'total':>8}{'maxDD':>7}{'R/DD':>7}{'worst losing run':>19}")
    for lab, tfs, kinds, g in POLICIES:
        sub = keep(rows, tfs, kinds, g)
        if len(sub) < 15:
            print(f"  {lab:<28}{len(sub):>6}   too few")
            continue
        m, se = mean_se([x.r for x in sub])
        win = sum(1 for x in sub if x.r > 0) / len(sub)
        d = dd_r(sub)
        tot = sum(x.r for x in sub)
        # Under 40 rows an R per signal is barely an estimate; say so on the
        # line rather than in a footnote nobody reads.
        thin = " THIN" if len(sub) < 40 else ""
        w, span = worst_streak(sub)
        print(f"  {lab:<28}{len(sub):>6}{len(sub) / days:>7.1f}{win:>6.0%}"
              f"{m:>+9.3f}{se:>7.3f}{tot:>+8.1f}{d:>7.1f}"
              f"{(tot / d) if d else 0:>7.2f}{w:>6}L in {span:>5.1f}h{thin}")


def clusters(rows):
    """One bet per (timeframe, bar close), averaged. The honest unit count.

    THE SPAN COLUMN FORCES THIS. Forty consecutive losers inside twelve hours
    is not forty bets that went wrong, it is a handful of market moments that
    each fired a dozen alerts at once — so counting them as forty trades makes
    both the streak and the sample size a fiction, and flatters the standard
    error most of all. Averaging every alert that shares a close reduces the
    book to what it really is: a smaller number of genuinely separate bets,
    each one taken at full size across however many symbols agreed. It is also
    exactly what the breadth line on the alert has been telling the reader to
    do.
    """
    bybar = {}
    for x in rows:
        bybar.setdefault((x.tf, x.t), []).append(x.r)
    out = []
    for (tf, t), rs in bybar.items():
        c = Row()
        c.tf, c.t = tf, t
        c.r = statistics.fmean(rs)
        c.kind, c.filled, c.poi, c.grade = "cluster", True, True, "A"
        c.risk, c.half = 0.0, "all"
        out.append(c)
    return out


def cluster_panel(title, rows, days):
    print(f"\n{title}")
    print(f"  {'policy':<28}{'bets':>6}{'/day':>7}{'win':>6}{'R/bet':>9}"
          f"{'SE':>7}{'total':>8}{'maxDD':>7}{'R/DD':>7}"
          f"{'worst losing run':>19}")
    for lab, tfs, kinds, g in POLICIES:
        sub = clusters(keep(rows, tfs, kinds, g))
        if len(sub) < 15:
            print(f"  {lab:<28}{len(sub):>6}   too few")
            continue
        m, se = mean_se([x.r for x in sub])
        win = sum(1 for x in sub if x.r > 0) / len(sub)
        d = dd_r(sub)
        tot = sum(x.r for x in sub)
        w, span = worst_streak(sub)
        print(f"  {lab:<28}{len(sub):>6}{len(sub) / days:>7.1f}{win:>6.0%}"
              f"{m:>+9.3f}{se:>7.3f}{tot:>+8.1f}{d:>7.1f}"
              f"{(tot / d) if d else 0:>7.2f}{w:>6}L in {span:>5.1f}h"
              f"{' THIN' if len(sub) < 40 else ''}")


def traffic(title, rows, days, tfs, kinds, grade="B"):
    """How many SEPARATE bets a policy actually offers, and how they arrive.

    "Separate" means a distinct candle close. Two confirmed alerts on the same
    30m close are one bet however many symbols printed it; two on consecutive
    closes are two, however close together they feel. That is the unit a person
    can act on, and it is the number that decides whether a policy is a product
    or a curiosity.

    THE DAILY DISTRIBUTION MATTERS AS MUCH AS THE MEAN. A policy averaging two
    bets a day made of quiet weeks and busy Tuesdays is a different thing to
    live with than one that reliably offers two, and only the histogram
    separates them.
    """
    sub = keep(rows, tfs, kinds, grade)
    if not sub:
        print(f"\n{title}: nothing")
        return
    bets = clusters(sub)
    byday = {}
    for b in bets:
        byday[int(b.t // 86400)] = byday.get(int(b.t // 86400), 0) + 1
    counts = sorted(byday.values())
    sizes = {}
    for x in sub:
        sizes[(x.tf, x.t)] = sizes.get((x.tf, x.t), 0) + 1
    bundles = sorted(sizes.values())

    wsig, spansig = worst_streak(sub)
    wbet, spanbet = worst_streak(bets)
    msig, sesig = mean_se([x.r for x in sub])
    mbet, sebet = mean_se([x.r for x in bets])

    print(f"\n{title}")
    print(f"  alerts                {len(sub):>6}   "
          f"{len(sub) / days:>5.1f} / day")
    print(f"  SEPARATE BETS         {len(bets):>6}   "
          f"{len(bets) / days:>5.1f} / day   "
          f"(one per candle close, however many symbols)")
    print(f"  active days           {len(byday):>6}   "
          f"of {days:.0f} days in the window had at least one bet")
    print(f"  bets on an active day        median {statistics.median(counts):>3.0f}"
          f" · busiest {counts[-1]}")
    print(f"  symbols per bet              median "
          f"{statistics.median(bundles):>3.0f} · biggest bundle {bundles[-1]}")
    print(f"  win rate              per alert {sum(1 for x in sub if x.r > 0) / len(sub):>4.0%}"
          f"   ·  per bet {sum(1 for x in bets if x.r > 0) / len(bets):>4.0%}")
    print(f"  R                     per alert {msig:>+6.3f} (SE {sesig:.3f})"
          f"  ·  per bet {mbet:>+6.3f} (SE {sebet:.3f})")
    # A streak is only readable next to what chance alone produces at this
    # win rate and this many bets: log(n) / -log(loss rate).
    wr = sum(1 for x in bets if x.r > 0) / len(bets)
    exp = (math.log(len(bets)) / -math.log(1 - wr)) if 0 < wr < 1 else 0
    print(f"  worst losing run      {wsig:>3} alerts in {spansig:>5.1f}h"
          f"   ·  {wbet:>3} bets in {spanbet:>5.1f}h "
          f"({spanbet / 24:.1f} days)")
    print(f"  chance alone would give        {exp:>4.1f} bets in a row at this "
          f"win rate over {len(bets)} bets")
    gaps = sorted((b.t - a.t) / 86400
                  for a, b in zip(sorted(bets, key=lambda z: z.t),
                                  sorted(bets, key=lambda z: z.t)[1:]))
    if gaps:
        print(f"  wait between bets     median "
              f"{gaps[len(gaps) // 2] * 24:>4.1f}h · longest quiet stretch "
              f"{gaps[-1]:.1f} days")


FIELDS = ("tf", "kind", "r", "filled", "poi", "grade", "t", "risk", "half")


async def gather(cache):
    """Collect, or reload a previous collection. One window, many slices.

    `collect` fetches two timeframes plus a daily and an Hour8 series per
    signal, which is minutes of API traffic for a table that takes a
    millisecond to print. Caching the ROWS rather than the conclusions means a
    follow-up question about the same window is free, and — more to the point —
    every policy below is then read off exactly the same data instead of a
    fresh sample that quietly moved.
    """
    if cache and os.path.exists(cache):
        with open(cache) as f:
            blob = json.load(f)
        rows = []
        for d in blob["rows"]:
            r = Row()
            for k in FIELDS:
                setattr(r, k, d[k])
            rows.append(r)
        return rows, [tuple(s) for s in blob["spans"]], blob["nsym"]
    async with aiohttp.ClientSession() as sess:
        syms = await list_symbols(sess)
        rows, spans = await collect(sess, syms)
    if cache:
        with open(cache, "w") as f:
            json.dump({"nsym": len(syms), "spans": spans,
                       "rows": [{k: getattr(r, k) for k in FIELDS}
                                for r in rows]}, f)
    return rows, spans, len(syms)


async def main():
    rows, spans, nsym = await gather(os.environ.get("RIPTIDE_ROW_CACHE"))
    days = statistics.median((b - a) / 86400 for a, b in spans)
    print(f"WHICH CELLS TO TAKE — and how long the losing runs get\n"
          f"{nsym} symbols · {days:.0f} days · POI required · "
          f"MIN_GRADE floor from the environment is {MIN_GRADE}\n"
          f"'/day' counts the whole universe. 'worst run' is the longest "
          f"streak of consecutive\nlosers that policy actually produced — the "
          f"thing a person feels, not a binomial.")
    panel("FULL WINDOW", rows, days)
    panel("HELD OUT (older half)", [x for x in rows if x.half == "held"],
          days / 2)
    cluster_panel("SAME-CLOSE ALERTS COUNTED AS ONE BET — full window",
                  rows, days)
    cluster_panel("SAME-CLOSE ALERTS AS ONE BET — HELD OUT (older half)",
                  [x for x in rows if x.half == "held"], days / 2)
    traffic("HOW MANY SEPARATE BETS — Min30 CONFIRMED", rows, days,
            ("Min30",), ("confirmed",))
    traffic("HOW MANY SEPARATE BETS — Min30 + Min15 CONFIRMED", rows, days,
            ("Min30", "Min15"), ("confirmed",))
    traffic("for comparison — EVERYTHING now sent", rows, days,
            ("Min30", "Min15"), ("early", "confirmed"))
    print(f"\nHOW ORDINARY A LOSING RUN IS, at each win rate:")
    print(f"  {'win rate':<12}{'P(6 losses in a row)':>24}"
          f"{'expected worst run in 50 trades':>34}")
    for w in (0.30, 0.35, 0.38, 0.42, 0.50):
        p6 = (1 - w) ** 6
        exp = math.log(50) / -math.log(1 - w)
        print(f"  {w:<12.0%}{p6:>23.1%}{exp:>30.1f} losses")
    print(f"\n  Six straight losses is not a broken system at any of these "
          f"rates.\n  It is what a 38% win rate looks like from the inside, "
          f"several times a year.")


if __name__ == "__main__":
    asyncio.run(main())
