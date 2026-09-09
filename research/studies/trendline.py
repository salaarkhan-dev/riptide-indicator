"""The chart-diff tool for the Liquidity Trendline port.

THE PORT ITSELF MOVED TO `riptide/trendline.py`. It had to: the bot now sends
heads-up alerts on these breakouts (`riptide/watch.py`), and a copy here plus a
copy there would be two indicators under one name, drifting apart silently. So
this file imports the one implementation and does the only thing research
needs that the bot does not — print a signal list a human can hold up against
the TradingView chart.

Everything about what the indicator does, and the three faithfully-copied
oddities in it, is documented in `riptide/trendline.py`.

    PYTHONPATH=. python3 research/studies/trendline.py ETH_USDT Min30
"""
from __future__ import annotations

import research.env  # noqa: F401  (must precede riptide.config)

from riptide.trendline import (ATR_LEN, PIVOT_LEN, SPACE, Line,  # noqa: F401
                               Signal, pivot_highs, pivot_lows,
                               trendline_signals)

if __name__ == "__main__":
    import asyncio
    import sys
    from datetime import datetime, timezone

    import aiohttp

    from research.studies.mtf_grid import fetch_paged

    sym = sys.argv[1] if len(sys.argv) > 1 else "ETH_USDT"
    tf = sys.argv[2] if len(sys.argv) > 2 else "Min30"

    async def main():
        async with aiohttp.ClientSession() as sess:
            cs = await fetch_paged(sess, sym, tf, 1)
        sigs = trendline_signals(cs)
        ts = lambda t: datetime.fromtimestamp(t, timezone.utc).strftime(
            "%Y-%m-%d %H:%M")
        print(f"PORT — Liquidity Trendline With Signals — {sym} {tf}")
        print(f"window  {ts(cs[0].t)} -> {ts(cs[-1].t)} UTC  ({len(cs)} bars)")
        print(f"period {PIVOT_LEN} · padding {SPACE:g} · ATR {ATR_LEN}")
        print(f"pivot highs {len(pivot_highs(cs, PIVOT_LEN))}   "
              f"pivot lows {len(pivot_lows(cs, PIVOT_LEN))}")
        up = sum(1 for s in sigs if s.is_long)
        print(f"\nBREAKOUTS  {len(sigs)}   up {up}   down {len(sigs) - up}"
              f"   ({len(sigs) / ((cs[-1].t - cs[0].t) / 86400):.2f} per day)")
        print(f"\n  {'bar time (UTC)':<18}{'signal':<8}{'close':>12}"
              f"{'line level':>12}{'anchor bar':>12}")
        for s in sigs[-40:]:
            print(f"  {ts(cs[s.bar].t):<18}"
                  f"{'BREAK UP' if s.is_long else 'BREAK DN':<8}"
                  f"{s.price:>12.6g}{s.line_y:>12.6g}"
                  f"{ts(cs[s.x1].t):>18}")

    asyncio.run(main())
