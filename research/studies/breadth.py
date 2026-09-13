"""BREADTH — how many symbols fired the same way at the same moment.

THE ONE SIGNAL A PER-SYMBOL STUDY STRUCTURALLY CANNOT SEE, and this project has
already pointed straight at it without being able to use it:

    "27% of confirmed losers fall on five days out of forty-two. That is not
     twenty-four bad signals, it is five bad days — one market move taking out
     everything at once, which is correlation risk and not signal quality.
     NOTHING ABOUT A SINGLE ALERT CAN SEE IT COMING."

That last sentence is true of a single alert and false of the scanner. When the
bot sends the seventh long of a cycle it already knows about the other six —
they are sitting in the same `results` list. The information is free, in memory,
and thrown away.

Every feature ever tested here describes one chart: POI, trend, volume, RSI,
reclaim, raid depth, slope, divergence. Breadth describes the MARKET at the
moment the signal fired, and it is the only axis left that a backtest of one
symbol at a time could never have contained.

TWO OUTCOMES, BOTH USEFUL, AND THE DIRECTION IS NOT PRE-JUDGED

  HIGH BREADTH IS BETTER    a genuine market-wide move, and a reversal setup
                            riding it has the whole market behind it.
  HIGH BREADTH IS WORSE     a correlated bundle — sixty charts printing one
                            bet, which is the "five bad days" shape, and the
                            reason capping concurrent positions cut drawdown
                            from 23% to 7%.

Both are plausible and they are opposite, so unlike every other study in this
file the direction is NOT fixed in advance — there is no prior to fix it with.
What IS fixed is the bar. Saying afterwards "of course it went that way" is the
thing pre-registration exists to prevent, so the interpretation of each
direction is written above, before the number.

WHY IT IS WORTH SOMETHING EVEN IF R DOES NOT MOVE. Breadth is a SIZING input,
not only a filter. "7th long this cycle" on an alert tells a reader that these
are one bet rather than seven, which is exactly the fact the portfolio study
found was costing 27% of the losses. That is useful whether or not the mean R
of a wide cycle differs from a narrow one.

PRE-REGISTERED

  PRIMARY   R per signal must differ between the top and bottom breadth
            buckets on the HELD-OUT half at 2 SE, monotone across buckets, in
            either direction, and clear a 25-seed placebo floor.

  SECONDARY The same on confirmed setups separately, and the raw shape of the
            distribution — how often a cycle is wide at all — because if
            breadth is almost always 1 the idea is dead on arrival regardless.

    PYTHONPATH=. python3 research/studies/breadth.py
"""
import research.env                                     # noqa: F401  MUST be first

import random                                           # noqa: E402
import statistics                                       # noqa: E402
from collections import Counter                         # noqa: E402

from riptide.config import BAR_SECONDS, INTERVAL        # noqa: E402
from research.data import load_sync                     # noqa: E402
from research.harness import mean_se                    # noqa: E402

SEEDS = 25
STEP = BAR_SECONDS[INTERVAL]


def signal_time(r):
    """The bar close at which this signal became actionable, on the grid.

    Snapped to the bar so signals from different symbols that fired on the
    same close land in the same bucket — which is the whole measurement. A
    raw timestamp would put every symbol in its own group and report a breadth
    of one for everything.
    """
    t = getattr(r.signal, "fvg_time", 0) or getattr(r.signal, "mss_time", 0) \
        or r.signal.sweep_time
    return t - (t % STEP)


def tag_breadth(rows):
    """Stamp each row with how many SAME-DIRECTION signals shared its close.

    Counted across the whole universe, including the row itself, so a lone
    signal has breadth 1. Deliberately not de-duplicated by symbol: a symbol
    printing two signals on one close really is two alerts arriving.
    """
    c = Counter((signal_time(r), r.signal.is_long) for r in rows)
    for r in rows:
        r.breadth = c[(signal_time(r), r.signal.is_long)]
    return rows


def line(lab, vals):
    if len(vals) < 25:
        print(f"    {lab:<26}{len(vals):>6}   too few")
        return None
    m, se = mean_se(vals)
    w = sum(1 for v in vals if v > 0) / len(vals)
    print(f"    {lab:<26}{len(vals):>6}{w:>7.0%}{m:>+10.3f}{se:>7.3f}")
    return m, se


def placebo(vals, n):
    if n < 25 or n >= len(vals):
        return None
    return statistics.median(
        statistics.fmean(random.Random(1300 + s).sample(vals, n))
        for s in range(SEEDS))


EDGES = (2, 4, 8)
LABELS = ("alone", "2-3 together", "4-7 together", "8+ together")


def panel(title, rows):
    print(f"\n{title}   n={len(rows)}")
    print(f"    {'':<26}{'n':>6}{'win':>7}{'R/signal':>10}{'SE':>7}")
    allv = [r.r for r in rows]
    line("all signals", allv)
    cuts = [0] + list(EDGES) + [10 ** 9]
    stats = []
    for lab, lo, hi in zip(LABELS, cuts, cuts[1:]):
        sub = [r.r for r in rows if lo <= r.breadth < hi]
        stats.append((lab, line(lab, sub), len(sub)))
    ok = [(l, s) for l, s, _ in stats if s]
    if len(ok) >= 2:
        (la, a), (lb, b) = ok[0], ok[-1]
        d, dse = b[0] - a[0], (a[1] ** 2 + b[1] ** 2) ** 0.5
        mids = [s[0] for _, s in ok]
        mono = (all(x <= y for x, y in zip(mids, mids[1:]))
                or all(x >= y for x, y in zip(mids, mids[1:])))
        n_top = [n for l, s, n in stats if s and l == lb][0]
        f = placebo(allv, n_top)
        print(f"    {'widest minus alone':<26}{'':>13}{d:>+10.3f}{dse:>7.3f}"
              f"   {d / dse if dse else 0:+.1f} SE"
              f"   {'monotone' if mono else 'NOT monotone'}"
              + (f"   placebo {f:+.3f}" if f is not None else ""))


def main():
    import asyncio
    import aiohttp
    from riptide.exchange import list_symbols

    async def _s():
        async with aiohttp.ClientSession() as sess:
            return await list_symbols(sess)
    syms = asyncio.run(_s()) or None
    every = tag_breadth(load_sync(symbols=syms))
    early = [r for r in every if r.kind == "early"]
    conf = [r for r in every if r.kind == "confirmed"]
    print(f"BREADTH — how many symbols fired the same way on the same close\n"
          f"{len(every)} signals over {len(set(r.symbol for r in every))} "
          f"symbols · bars of {INTERVAL}")

    b = Counter(r.breadth for r in every)
    tot = sum(b.values())
    print(f"\nHOW WIDE DOES IT ACTUALLY GET — if this is almost always 1, "
          f"the idea is\ndead on arrival whatever the R says.")
    print(f"  {'same-direction signals on one close':<40}{'share':>8}")
    for lab, lo, hi in zip(LABELS, [0] + list(EDGES), list(EDGES) + [10 ** 9]):
        n = sum(v for k, v in b.items() if lo <= k < hi)
        print(f"  {lab:<40}{n / tot:>8.0%}")
    print(f"  widest single close: {max(b) if b else 0} signals")

    panel("EARLY — all", early)
    panel("EARLY — HELD OUT (older half), the pre-registered one",
          [r for r in early if r.split_window])
    panel("CONFIRMED — all", conf)
    panel("CONFIRMED — HELD OUT", [r for r in conf if r.split_window])


if __name__ == "__main__":
    main()
