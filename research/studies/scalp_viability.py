"""CAN A 1-MINUTE STRATEGY PAY FOR ITSELF? ASK BEFORE BUILDING ONE.

THIS IS A GATE, NOT A STRATEGY. Nothing here tests an entry. It asks the one
question that decides whether ANY 1m entry is worth looking for, and it is
cheap enough to answer in an hour instead of a month.

THE ARITHMETIC THAT DECIDES IT. Cost in R is not a fee schedule, it is a ratio:

    cost in R  =  cost as % of price  /  stop distance as %

The numerator barely changes between timeframes — the spread is the spread. The
DENOMINATOR collapses. Riptide's median 30m stop is 1.45%; a 1m stop is a
fraction of that. Every cost therefore multiplies by the ratio of the two, and
a cost that is a rounding error at 30m can be a third of the risk at 1m.

This project already learned the same lesson one timeframe up and did not
generalise it. fee_key.out:

    tf     med stop   gross R      net R    fee as % of gross
    15m       1.01%   +0.0064    -0.0268                 521%
    30m       1.45%   +0.0486    +0.0255                  47%
    1h        2.04%   +0.0594    +0.0435                  27%

15m is NEGATIVE after costs, on 4625 trades, for exactly this reason — its
stops are half of 1h's, so it pays about twice the cost per unit of risk. 1m
stops are smaller again. That table is the prior for this one.

WHAT THIS MEASURES, on real 1m candles and a real order book:

  1. The natural stop scale at 1m — ATR(14) in percent, per symbol.
  2. The live spread, from the book, in percent.
  3. Their ratio, at several plausible stop multiples, plus the taker fee the
     symbol actually charges today.
  4. The GROSS R a strategy would need just to break even, and the minimum
     stop distance at which costs fall under a tenth of risk.

SPREAD IS CHARGED ONCE, ON THE EXIT, and that is the optimistic reading. The
entry is a limit — maker, no spread, and 98% of this universe pays zero maker
fee. The stop is a market order: it crosses. A strategy that ever chases an
entry pays it twice and every number here doubles.

WHAT WOULD KILL THE BRANCH: if a realistic 1m stop puts costs above roughly a
third of risk, then a hypothetical +0.15R edge is gone before slippage is even
modelled, and no amount of pattern work recovers it. The honest response to
that is a larger stop — which is a slower timeframe wearing a 1m label.

    PYTHONPATH=. python3 research/studies/scalp_viability.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import json                                             # noqa: E402
import time                                             # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import BASE, MIN_VOL_USDT           # noqa: E402

PACE = 0.7
DAYS = 30                  # enough to characterise volatility, cheap to fetch
MAX_BARS = 2000            # MEXC's ceiling for one kline request
STOP_MULTIPLES = (1.0, 1.5, 2.0, 3.0)
TIMEOUT = aiohttp.ClientTimeout(total=25)


async def get(sess, path):
    async with sess.get(BASE + path, timeout=TIMEOUT) as r:
        return json.loads(await r.text())


async def minute_bars(sess, symbol, days=DAYS):
    """1m candles, paged backwards at MEXC's 2000-bar ceiling."""
    end = int(time.time())
    start = end - days * 86400
    out = {}
    cur = start
    while cur < end:
        stop = min(cur + MAX_BARS * 60, end)
        d = await get(sess, f"/api/v1/contract/kline/{symbol}"
                            f"?interval=Min1&start={cur}&end={stop}")
        k = (d.get("data") or {})
        ts = k.get("time") or []
        if not ts:
            break
        for t, h, lo, c in zip(ts, k["high"], k["low"], k["close"]):
            out[t] = (float(h), float(lo), float(c))
        cur = max(ts) + 60
        await asyncio.sleep(PACE)
    return [out[t] for t in sorted(out)]


def atr_pct(bars, n=14):
    """ATR(14) as a percentage of price — the natural stop scale at 1m."""
    if len(bars) < n + 2:
        return None
    trs = []
    for i in range(1, len(bars)):
        h, lo, _ = bars[i]
        pc = bars[i - 1][2]
        trs.append(max(h - lo, abs(h - pc), abs(lo - pc)))
    # median of rolling ATR, so one violent hour cannot set the scale
    vals = []
    for i in range(n, len(trs)):
        a = sum(trs[i - n:i]) / n
        px = bars[i][2]
        if px:
            vals.append(100 * a / px)
    vals.sort()
    return vals[len(vals) // 2] if vals else None


async def spread_pct(sess, symbol):
    d = await get(sess, f"/api/v1/contract/depth/{symbol}")
    dd = d.get("data") or {}
    bids, asks = dd.get("bids") or [], dd.get("asks") or []
    if not bids or not asks:
        return None
    bb, ba = bids[0][0], asks[0][0]
    return 100 * (ba - bb) / ((bb + ba) / 2)


async def main():
    async with aiohttp.ClientSession() as sess:
        det = await get(sess, "/api/v1/contract/detail")
        spec = {d["symbol"]: d for d in det["data"]}
        await asyncio.sleep(PACE)
        tk = await get(sess, "/api/v1/contract/ticker")
        vol = {t["symbol"]: (t.get("amount24") or 0) for t in tk["data"]}

        live = sorted((s for s in spec
                       if s.endswith("_USDT") and spec[s].get("state") == 0
                       and vol.get(s, 0) >= MIN_VOL_USDT),
                      key=lambda s: -vol[s])
        picks = [live[i] for i in (0, 3, 10, 25, 50, 80, 110) if i < len(live)]

        print("CAN A 1-MINUTE STRATEGY PAY FOR ITSELF?")
        print(f"{DAYS} days of 1m candles · live order book · "
              f"{time.strftime('%Y-%m-%d')}\n")
        print("Riptide's 30m median stop is 1.45% and it pays 47% of gross to")
        print("fees. 15m at 1.01% is NET NEGATIVE. This asks what 1m stops")
        print("look like and what that ratio becomes.\n")

        rows = []
        for sym in picks:
            bars = await minute_bars(sess, sym)
            a = atr_pct(bars)
            sp = await spread_pct(sess, sym)
            await asyncio.sleep(PACE)
            if a is None or sp is None:
                print(f"  {sym}: no data ({len(bars)} bars)")
                continue
            taker = 100 * float(spec[sym].get("takerFeeRate") or 0)
            rows.append((sym, live.index(sym), vol[sym], len(bars), a, sp, taker))
            print(f"  fetched {sym:<16}{len(bars):>7} bars  "
                  f"1m ATR {a:.3f}%  spread {sp:.3f}%  taker {taker:.3f}%")

        print(f"\n{'=' * 96}\nTHE COST RATIO AT EACH STOP SIZE\n{'=' * 96}")
        print("  cost in R = (spread + taker fee) / stop%.  Spread charged ONCE,")
        print("  on the market-order exit; the limit entry is maker and free.\n")
        head = "".join(f"{m:g}xATR".rjust(11) for m in STOP_MULTIPLES)
        print(f"  {'symbol':<16}{'rank':>5}{'ATR%':>8}{'spr%':>7}{head}")
        for sym, rank, _v, _n, a, sp, tk_ in rows:
            cells = ""
            for m in STOP_MULTIPLES:
                stop = a * m
                cost_r = (sp + tk_) / stop if stop else 9.99
                cells += f"{cost_r:>11.2f}"
            print(f"  {sym:<16}{rank:>5}{a:>8.3f}{sp:>7.3f}{cells}")

        print(f"\n{'=' * 96}\nWHAT IT TAKES TO BREAK EVEN\n{'=' * 96}")
        print(f"  {'symbol':<16}{'stop @2xATR':>13}{'cost R':>9}"
              f"{'gross R to net 0':>19}{'min stop% for':>16}")
        print(f"  {'':<16}{'':>13}{'':>9}{'at 1R target':>19}{'cost<0.10R':>16}")
        for sym, _r, _v, _n, a, sp, tk_ in rows:
            stop = a * 2
            cost_r = (sp + tk_) / stop if stop else 9.99
            need = 1 + cost_r
            min_stop = (sp + tk_) / 0.10
            print(f"  {sym:<16}{stop:>12.3f}%{cost_r:>9.2f}{need:>19.2f}"
                  f"{min_stop:>15.3f}%")

        if rows:
            med_a = sorted(r[4] for r in rows)[len(rows) // 2]
            med_s = sorted(r[5] for r in rows)[len(rows) // 2]
            med_t = sorted(r[6] for r in rows)[len(rows) // 2]
            print(f"\n{'=' * 96}\nTHE COMPARISON THAT MATTERS\n{'=' * 96}")
            print(f"  {'strategy':<28}{'stop %':>10}{'cost %':>10}"
                  f"{'cost in R':>12}{'':>6}")
            for lab, stop in (("Riptide 30m (measured)", 1.45),
                              ("Riptide 15m (NET NEGATIVE)", 1.01),
                              (f"1m @ 2x ATR", med_a * 2),
                              (f"1m @ 3x ATR", med_a * 3)):
                c = med_s + med_t
                print(f"  {lab:<28}{stop:>9.3f}%{c:>9.3f}%{c / stop:>12.2f}")
            print("\n  Median across the sampled symbols. If the 1m rows sit far")
            print("  above the 15m row — the one already measured as losing —")
            print("  then the branch needs a bigger stop, which is a slower")
            print("  timeframe wearing a 1m label.")


if __name__ == "__main__":
    asyncio.run(main())
