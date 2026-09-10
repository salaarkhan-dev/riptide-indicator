"""Correlation-aware sizing — the one improvement that needs no new edge.

WHAT THIS IS FOR. Eight hypotheses were tested and every one came back empty,
so the edge is what it is: +0.063 R per bet over 333 days at R/DD 1.13. Sizing
does not need a discovery. It cannot make the edge bigger — but it can change
how much drawdown that edge is bought with, and drawdown is the term that
actually hurt: the worst run in the deployed stream is twenty-four losers inside
3.8 hours, which is one market move taking out an entire book at once.

R PER UNIT OF DRAWDOWN IS THE METRIC AND THE REASON IS ARITHMETIC. Doubling
every position doubles both total R and the drawdown, so total R alone cannot
tell a better rule from more leverage. R/DD is scale-invariant: it only moves if
the rule sizes DIFFERENTLY across trades. That makes it the only honest way to
compare a sizing policy, and it is why "total R fell" is not by itself an
argument against one.

THE DEPLOYED RULE ALREADY DOES HALF OF THIS. Alerts sharing one candle close in
one direction are collapsed into a single bet, sized once. Every policy below
starts from that collapse, so what is being tested is the part that is NOT yet
handled: positions from DIFFERENT closes that are open at the same time. The
3.8-hour run spans several closes, so the same-close rule cannot see it.

THE POLICIES

  flat                    one unit per bet. The deployed behaviour.
  cap at N                take the bet only if fewer than N same-direction bets
                          are already open. A hard ceiling on correlated risk.
  budget 1/(1+open)       each new correlated bet takes a diminishing share, so
                          total exposure to one market move is bounded.
  budget 1/sqrt(1+open)   the same idea, much gentler — full size when alone,
                          70% with one other open, 50% with three.

PRE-REGISTERED, BEFORE THE FIRST NUMBER

  PRIMARY   A policy wins only by improving R PER DRAWDOWN against flat. Total R
            is reported but decides nothing, since any policy can raise it by
            sizing up.

  SECOND    The worst 48-hour loss, because that is the number a person feels
            and the one that produced "I took five or six and they all lost".

  REPORTED REGARDLESS: average size and the share of bets skipped. A cap that
  declines a third of the stream is a different product, not a free improvement.

  EXPECTATION: the budget rules improve R/DD modestly and cut the worst 48-hour
  loss substantially, because they act exactly when many positions are open —
  which is exactly when a single move can take them all. The hard cap does
  better on drawdown and worse on R/DD, because it declines bets rather than
  shrinking them. Recorded so it cannot be revised.

    PYTHONPATH=. RIPTIDE_MIN_GRADE=B RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/sizing.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import statistics                                       # noqa: E402
from collections import defaultdict                     # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.exchange import list_symbols               # noqa: E402
from research.deep import load_universe                 # noqa: E402
from research.harness import mean_se                    # noqa: E402
from research.studies.replicate import DAYS, TF, collect  # noqa: E402


class Bet:
    __slots__ = ("t", "t_in", "t_out", "r", "is_long", "n")


def to_bets(sigs):
    """Collapse same-close, same-direction alerts into one bet — as deployed.

    KEYED ON DIRECTION AS WELL AS TIME, which is how the shipped breadth tag
    keys it. A long and a short printing on the same close are two different
    bets about two different things; merging them would net a real long against
    a real short and invent a position nobody held.

    The bet is open from the first leg's fill to the LAST leg's exit, because
    that is the span over which it is exposed to a market move.
    """
    grp = defaultdict(list)
    for s in sigs:
        grp[(s.t, s.is_long)].append(s)
    out = []
    for (t, is_long), v in grp.items():
        b = Bet()
        b.t, b.is_long, b.n = t, is_long, len(v)
        b.t_in = min(s.t_in for s in v)
        b.t_out = max(s.t_out for s in v)
        b.r = statistics.fmean(s.r for s in v)
        out.append(b)
    out.sort(key=lambda b: b.t)
    return out


def run(bets, size_of):
    """Walk the book in time order, sizing each bet by what is already open.

    Concurrency is counted on the SAME DIRECTION only. Two longs open at once
    are one market move away from losing together; a long and a short are not,
    and treating them as correlated would penalise the one combination that is
    actually hedged.

    The equity curve realises each trade at its EXIT, which is when the money
    actually moves, so the drawdown is the one a person would have lived
    through rather than a signal-time fiction.
    """
    live, realised, sizes, skipped = [], [], [], 0
    for b in bets:
        live = [x for x in live if x[0] > b.t_in]          # still open
        openn = sum(1 for t_out, d in live if d == b.is_long)
        sz = size_of(openn)
        sizes.append(sz)
        if sz <= 0:
            skipped += 1
            continue
        live.append((b.t_out, b.is_long))
        realised.append((b.t_out, sz * b.r))

    realised.sort()
    bal = peak = dd = 0.0
    curve = []
    for t, r in realised:
        bal += r
        peak = max(peak, bal)
        dd = max(dd, peak - bal)
        curve.append((t, bal))

    # The worst 48 hours: the largest peak-to-trough inside any two-day span.
    # A max drawdown can accumulate over months; this is the single bad session.
    worst48 = 0.0
    for i, (t, v) in enumerate(curve):
        hi = v
        for t2, v2 in curve[i:]:
            if t2 - t > 48 * 3600:
                break
            hi = max(hi, v2)
            worst48 = max(worst48, hi - v2)

    tot = bal
    return dict(taken=len(realised), skipped=skipped,
                avg=statistics.fmean(sizes) if sizes else 0.0,
                tot=tot, dd=dd, rdd=(tot / dd) if dd else 0.0, w48=worst48)


POLICIES = (
    ("flat — one unit per bet (deployed)", lambda n: 1.0),
    ("cap: skip if 3 already open", lambda n: 1.0 if n < 3 else 0.0),
    ("cap: skip if 5 already open", lambda n: 1.0 if n < 5 else 0.0),
    ("cap: skip if 8 already open", lambda n: 1.0 if n < 8 else 0.0),
    ("budget 1/(1+open)", lambda n: 1.0 / (1 + n)),
    ("budget 1/sqrt(1+open)", lambda n: (1 + n) ** -0.5),
    ("budget 1/(1+open/2)", lambda n: 1.0 / (1 + n / 2)),
    ("half size when any are open", lambda n: 1.0 if n == 0 else 0.5),
)


def panel(title, bets, days):
    print(f"\n{title}   {len(bets)} bets · {len(bets) / days:.1f}/day")
    print(f"  {'policy':<36}{'taken':>7}{'skip':>6}{'avg sz':>8}{'total R':>9}"
          f"{'maxDD':>8}{'R/DD':>7}{'worst 48h':>11}   vs flat")
    base = None
    for lab, fn in POLICIES:
        g = run(bets, fn)
        if base is None:
            base = g
        cmp = ""
        if g is not base and base["rdd"]:
            cmp = f"{(g['rdd'] / base['rdd'] - 1) * 100:>+6.0f}% R/DD"
        print(f"  {lab:<36}{g['taken']:>7}{g['skipped']:>6}{g['avg']:>8.2f}"
              f"{g['tot']:>+9.1f}{g['dd']:>8.1f}{g['rdd']:>7.2f}"
              f"{g['w48']:>11.1f}   {cmp}")


def by_concurrency(bets):
    """R per bet, bucketed by how many same-direction bets were ALREADY open.

    THE MECHANISM, MEASURED DIRECTLY RATHER THAN INFERRED FROM A CAP. A cap
    that improves the curve is consistent with "later positions in a cluster
    are worse" but does not establish it — the improvement could come from the
    smaller book alone. This table asks the question outright, on every bet,
    with no policy in between.
    """
    grp = defaultdict(list)
    live = []
    for b in bets:
        live = [x for x in live if x[0] > b.t_in]
        n = sum(1 for t_out, d in live if d == b.is_long)
        grp[min(n, 5)].append(b.r)
        live.append((b.t_out, b.is_long))
    print(f"\n  {'already open':<16}{'bets':>7}{'share':>8}{'win':>7}"
          f"{'R/bet':>10}{'SE':>8}")
    for n in sorted(grp):
        v = grp[n]
        if len(v) < 15:
            continue
        m, se = mean_se(v)
        lab = f"{n}" if n < 5 else "5 or more"
        print(f"  {lab:<16}{len(v):>7}{len(v) / len(bets):>8.0%}"
              f"{sum(1 for r in v if r > 0) / len(v):>7.0%}{m:>+10.3f}"
              f"{se:>8.3f}")


def stability(bets, days):
    """Does a policy's ranking hold in every quarter, or only overall?

    R/DD IS A RATIO WITH A VERY NOISY DENOMINATOR. A max drawdown is a single
    extreme observation from a single path, so a 30% improvement in R/DD can be
    one avoided cluster rather than a better rule. And this study swept eight
    policies over two panels, which is exactly the shape that handed back
    min_pivots = 3 on one timeframe and 4 on another earlier today.

    So each policy is re-read one quarter at a time. A rule that beats flat in
    every quarter is sizing better; one that wins overall and loses in half the
    quarters won a coin toss on one crowded week.
    """
    from datetime import datetime, timezone
    byq = defaultdict(list)
    for b in bets:
        dt = datetime.fromtimestamp(b.t, timezone.utc)
        byq[f"{dt.year}Q{(dt.month - 1) // 3 + 1}"].append(b)
    qs = sorted(byq)
    print(f"\n  {'policy':<36}" + "".join(f"{q:>10}" for q in qs)
          + f"{'beats flat':>12}")
    flat = {q: run(byq[q], lambda n: 1.0)["rdd"] for q in qs}
    for lab, fn in POLICIES:
        cells, wins = [], 0
        for q in qs:
            g = run(byq[q], fn)["rdd"]
            cells.append(f"{g:>10.2f}")
            if g > flat[q] + 1e-9:
                wins += 1
        note = f"{wins} of {len(qs)}"
        print(f"  {lab:<36}" + "".join(cells) + f"{note:>12}"
              + ("  <-- every quarter" if wins == len(qs) else ""))


def concurrency(bets):
    """How often the book is actually crowded — the size of the problem."""
    live = []
    counts = []
    for b in bets:
        live = [x for x in live if x[0] > b.t_in]
        counts.append(sum(1 for t_out, d in live if d == b.is_long))
        live.append((b.t_out, b.is_long))
    q = sorted(counts)
    return (statistics.fmean(counts), q[len(q) // 2], q[int(0.9 * len(q))],
            q[-1], sum(1 for c in counts if c == 0) / len(counts))


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = await list_symbols(sess)
        candles = await load_universe(sess, syms, TF, DAYS)
        sigs = await collect(sess, candles)
    days = statistics.median((cs[-1].t - cs[0].t) / 86400
                             for cs in candles.values())

    print(f"CORRELATION-AWARE SIZING — no new edge required\n"
          f"{len(candles)} symbols · {days:.0f} days · same-close same-"
          f"direction alerts already collapsed to one bet\n"
          f"R/DD is the metric: it is scale-invariant, so it moves only if a "
          f"rule sizes\nDIFFERENTLY across trades rather than simply smaller")

    for name, sub in (("Min30 CONFIRMED", [s for s in sigs
                                           if s.kind == "confirmed"]),
                      ("EVERYTHING SENT", sigs)):
        bets = to_bets(sub)
        mean, med, p90, mx, alone = concurrency(bets)
        print(f"\n{'=' * 104}\n{name} — how crowded the book gets\n"
              f"  same-direction bets already open when a new one arrives: "
              f"mean {mean:.1f} · median {med} · p90 {p90} · max {mx}\n"
              f"  {alone:.0%} of bets arrive with nothing else open"
              f"\n{'=' * 104}")
        by_concurrency(bets)
        panel(name, bets, days)
        stability(bets, days)

    print(f"\nPRE-REGISTERED: R per drawdown decides. Total R decides nothing — "
          f"any policy can\nraise it by sizing up, and every rule here that "
          f"lowers it also lowers exposure.")


if __name__ == "__main__":
    asyncio.run(main())
