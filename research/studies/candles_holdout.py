"""Held-out test: gapless piercing / dark cloud anywhere raid->signal, early.

Discovery window: -0.043 without against +0.217 with, +0.260 at 3.2 SE, n=338.
Found among 26 comparisons and not predicted in advance, so it is a hypothesis
until it survives data that was never looked at.

Stated in advance: the pattern PRESENT predicts a HIGHER R per signal.
Bar: >= 3 SE on the held-out window alone, same sign on all four splits.
"""
import research.env                                     # noqa: F401  MUST be first
import asyncio, time                                    # noqa: E402

import aiohttp                                          # noqa: E402
from riptide.config import BAR_SECONDS, CFG, TRACK_TARGET_R  # noqa: E402
from riptide.engine import Candle, run_engine           # noqa: E402
from riptide.exchange import BASE, get_json             # noqa: E402
from research.data import SYMBOLS, Row                  # noqa: E402
from research.harness import report, risk_terciles, simulate  # noqa: E402
from research.patterns import piercing_gapless          # noqa: E402


async def window(sess, symbol, interval, end, bars=2000):
    step = BAR_SECONDS[interval]
    d = await get_json(sess, f"{BASE}/api/v1/contract/kline/{symbol}",
                       {"interval": interval, "start": end - bars * step,
                        "end": end})
    if not d or not d.get("data"):
        return []
    k = d["data"]
    vol = k.get("vol") or [0] * len(k["time"])
    return [Candle(int(t), float(o), float(h), float(l), float(c), float(v))
            for t, o, h, l, c, v in
            zip(k["time"], k["open"], k["high"], k["low"], k["close"], vol)]


async def main():
    end = int(time.time()) - 2000 * BAR_SECONDS["Min30"]
    print(f"held-out window ends {time.strftime('%d %b %Y', time.gmtime(end))}\n")
    rows = []
    async with aiohttp.ClientSession() as sess:
        for n, sym in enumerate(SYMBOLS):
            cs = await window(sess, sym, "Min30", end)
            if len(cs) < 400:
                continue
            early = []
            run_engine(sym, cs, CFG, early_out=early)
            idx = {c.t: i for i, c in enumerate(cs)}
            mid = cs[len(cs) // 2].t
            for x in early:
                i = idx.get(x.fvg_time)
                if i is None or abs(x.entry - x.stop) <= 0:
                    continue
                o = simulate(cs, i, x.entry, x.stop, x.is_long,
                             target_r=TRACK_TARGET_R, fee_maker=0.02,
                             fee_taker=0.06)
                if o.filled and o.exit_bar is None:
                    continue
                rows.append(Row(symbol=sym, kind="early", r=o.r, filled=o.filled,
                                fill_time=cs[o.fill_bar].t if o.fill_bar else 0,
                                exit_time=cs[o.exit_bar].t if o.exit_bar else 0,
                                mfe=o.mfe, mae=o.mae,
                                risk_pct=100 * abs(x.entry - x.stop) / x.entry,
                                split_symbol=n % 2, split_window=cs[i].t < mid,
                                bar=i, signal=x, candles=cs))
    print(f"{len(rows)} early signals on held-out data")

    def feat(r):
        idx = {c.t: i for i, c in enumerate(r.candles)}
        g = idx.get(getattr(r.signal, "grab_time", 0) or r.signal.sweep_time, r.bar)
        return any(piercing_gapless(r.candles, i, r.signal.is_long)
                   for i in range(max(g, 2), r.bar + 1))

    report("gapless piercing/dark cloud raid->signal  [predicted POSITIVE]",
           rows, feat, control=risk_terciles)

asyncio.run(main())
