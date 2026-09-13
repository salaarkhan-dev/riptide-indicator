"""How many trendline-break alerts would actually arrive, per timeframe?

A HEADS-UP alert is a different product from a trade signal and it fails for a
different reason. A trade signal fails by losing money. A heads-up fails by
arriving too often to read — an alert you scroll past is worse than no alert,
because it also buries the ones you would have opened.

`trendline_measure.py` already settled the trading question: the break is
indistinguishable from a random entry, so nothing here should be traded on. It
did not answer the question that matters for a watch list, which is simply how
many arrive and how far apart.

So this counts, and nothing else. No outcomes, no R, no win rate — those exist
already and they say do not trade it. The only outputs are:

    per symbol per day       how often one symbol speaks
    across the universe      how many land in the chat in a day
    median gap               how long between two alerts, in minutes, which is
                             the number that decides whether a human reads them

Min60 and Hour4 are included because they have never been measured here and are
the obvious place a heads-up wants to live: a break of a 4h trendline is a rarer
and larger event than a break of a 15m one, and rarity is the whole feature.

    PYTHONPATH=. python3 research/studies/trendline_rate.py
"""
from __future__ import annotations

import research.env  # noqa: F401  (must precede riptide.config)

import asyncio
import statistics

import aiohttp

from riptide.config import BAR_SECONDS
from riptide.exchange import list_symbols
from research.studies.mtf_grid import fetch_paged
from research.studies.trendline import trendline_signals

SYMBOLS = 60
# Pages sized so each timeframe covers roughly the same 80+ days.
TFS = (("Min15", 4), ("Min30", 2), ("Min60", 1), ("Hour4", 1))


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = (await list_symbols(sess))[:SYMBOLS]
        print(f"Trendline break ALERT RATE — {len(syms)} symbols\n"
              f"counting only; the trading question is already answered in "
              f"MEASUREMENTS.md and the answer is no\n")
        print(f"  {'timeframe':<12}{'days':>6}{'signals':>9}{'/sym/day':>10}"
              f"{'per day, all':>14}{'burst':>9}{'worst':>9}")
        for tf, pages in TFS:
            total, days, times = 0, [], []
            for sym in syms:
                try:
                    cs = await fetch_paged(sess, sym, tf, pages)
                except Exception:
                    continue
                if len(cs) < 400:
                    continue
                days.append((cs[-1].t - cs[0].t) / 86400)
                sigs = trendline_signals(cs)
                total += len(sigs)
                times += [cs[s.bar].t for s in sigs]
            if not days:
                continue
            span = statistics.median(days)
            per_sym = total / (span * len(days))
            universe = per_sym * len(syms)
            # NOT the median gap, which came out at 0 minutes and said only
            # that alerts share timestamps. Of course they do: bar closes are
            # synchronised across symbols, so breaks cluster on the same close
            # rather than arriving spread out. The number a reader feels is the
            # BURST — how many land at once — so that is what is reported.
            from collections import Counter
            per_close = Counter(times)
            burst = statistics.median(per_close.values()) if per_close else 0
            worst = max(per_close.values()) if per_close else 0
            print(f"  {tf:<12}{span:>6.0f}{total:>9}{per_sym:>10.2f}"
                  f"{universe:>14.0f}{burst:>9.0f}{worst:>9}")
        print(f"\n  'per day, all' is what lands in the chat. 'burst' is how "
              f"many symbols break\n  on the SAME bar close, median and worst "
              f"— alerts arrive together, not spread\n  out, because bar "
              f"closes are synchronised across the universe.")


if __name__ == "__main__":
    asyncio.run(main())
