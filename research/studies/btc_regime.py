"""BTC regime on EARLY signals — held-out test. See PREREG_btc.md."""
import research.env                                     # noqa: F401  MUST be first
import asyncio, time                                    # noqa: E402
from bisect import bisect_right                         # noqa: E402

import aiohttp                                          # noqa: E402
from riptide.config import BAR_SECONDS, CFG             # noqa: E402
from riptide.engine import Candle, run_engine           # noqa: E402
from riptide.exchange import BASE, get_json             # noqa: E402
from riptide.trend import supertrend                    # noqa: E402
from research.data import SYMBOLS, Row                  # noqa: E402
from research.harness import report, risk_terciles, simulate  # noqa: E402

TFS = ("Min30", "Min60", "Hour4", "Day1")


async def window(sess, symbol, interval, end, bars=2000):
    """Explicit start/end, so an OLDER window can be requested. fetch_candles
    only ever reads backwards from now, which cannot produce held-out data."""
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
    now = int(time.time())
    step = BAR_SECONDS["Min30"]
    # The discovery window is the most recent 2000 bars. Held-out ends there.
    held_end = now - 2000 * step
    print(f"held-out window ends {time.strftime('%d %b %Y', time.gmtime(held_end))}"
          f" — {time.strftime('%d %b', time.gmtime(held_end - 2000 * step))} onward\n")

    async with aiohttp.ClientSession() as sess:
        btc = {}
        for tf in TFS:
            cs = await window(sess, "BTC_USDT", tf,
                              held_end + 5 * BAR_SECONDS[tf],
                              2000 if tf != "Day1" else 400)
            if len(cs) > 40:
                btc[tf] = ([c.t for c in cs], supertrend(cs))
        print("BTC series:", {k: len(v[0]) for k, v in btc.items()})

        rows = []
        for n, sym in enumerate(SYMBOLS):
            if sym == "BTC_USDT":
                continue
            cs = await window(sess, sym, "Min30", held_end)
            if len(cs) < 400:
                continue
            early = []
            run_engine(sym, cs, CFG, early_out=early)
            idx = {c.t: i for i, c in enumerate(cs)}
            mid = cs[len(cs) // 2].t
            for x in early:
                i = idx.get(x.fvg_time)
                if i is None:
                    continue
                risk = abs(x.entry - x.stop)
                if risk <= 0:
                    continue
                o = simulate(cs, i, x.entry, x.stop, x.is_long, target_r=2.0)
                if o.filled and o.exit_bar is None:
                    continue
                rows.append(Row(symbol=sym, kind="early", r=o.r, filled=o.filled,
                                mfe=o.mfe, mae=o.mae, risk_pct=100 * risk / x.entry,
                                split_symbol=n % 2, split_window=cs[i].t < mid,
                                bar=i, signal=x, candles=cs))

    print(f"{len(rows)} early signals on held-out data\n")

    def agree(tf):
        def f(r):
            got = btc.get(tf)
            if not got:
                return None
            times, st = got
            j = bisect_right(times, r.candles[r.bar].t - BAR_SECONDS[tf]) - 1
            if not 0 <= j < len(st) or not st[j]:
                return None
            return (st[j] < 0) == r.signal.is_long     # -1 is up
        f.__name__ = f"btc_{tf}"
        return f

    for tf in TFS:
        report(f"BTC {tf} trend agrees  [predicted POSITIVE for 30m]",
               rows, agree(tf), control=risk_terciles)

asyncio.run(main())
