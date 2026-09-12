"""WHAT DOES MEXC GIVE AWAY FOR FREE, AND WHICH OF IT IS BACKTESTABLE?

WHY THIS EXISTS. riptide/market.py asserted for months that funding rate has no
history endpoint and "cannot be backtested at all — not with more effort, not
with a better script". That was false: /api/v1/contract/funding_rate/history is
public, unauthenticated, and carries 539 days on BTC_USDT. A remembered claim
closed a door that was open, and nothing in the repo could catch it because
nothing in the repo had ever asked the exchange.

So this asks the exchange. It is a PROBE, not a study — no hypothesis, nothing
pre-registered, no conclusions. It prints what is reachable today and what
shape it comes in, so a claim about the data surface can be checked in ninety
seconds instead of believed.

THE ONE DISTINCTION THAT MATTERS, and the reason the output is grouped by it:

    HAS HISTORY   -> can be backtested against the 333-day window today
    LIVE ONLY     -> can only be logged forward, like riptide/market.py does
                     for open interest. Six weeks before it says anything.

Anything in the second group is a decision to spend six weeks, not a decision
to write a filter. Treat the two very differently.

    PYTHONPATH=. python3 research/studies/exchange_surface.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import json                                             # noqa: E402
import time                                             # noqa: E402
from collections import Counter                         # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import BASE, MIN_VOL_USDT, TOP_N    # noqa: E402

PACE = 0.7          # be a good citizen; the 12 Sep throttle is fresh
TIMEOUT = aiohttp.ClientTimeout(total=20)


async def get(sess, path):
    async with sess.get(BASE + path, timeout=TIMEOUT) as r:
        return r.status, await r.text()


async def probe(sess, name, path):
    """Returns (ok, one-line shape description)."""
    try:
        status, body = await get(sess, path)
    except Exception as e:
        return False, f"{type(e).__name__}"
    try:
        d = json.loads(body)
    except Exception:
        return False, f"HTTP {status}, non-JSON"
    if not (isinstance(d, dict) and d.get("success") is True):
        msg = d.get("message") if isinstance(d, dict) else body[:50]
        return False, f"HTTP {status} · {str(msg)[:44]}"
    data = d.get("data")
    if isinstance(data, list):
        head = sorted(data[0].keys()) if data and isinstance(data[0], dict) else data[:1]
        return True, f"list[{len(data)}] {str(head)[:86]}"
    if isinstance(data, dict):
        return True, f"dict {str(sorted(data.keys()))[:92]}"
    return True, str(data)[:92]


HISTORY = [
    ("funding rate history", "/api/v1/contract/funding_rate/history"
                             "?symbol=BTC_USDT&page_num=1&page_size=5"),
    ("index price kline", "/api/v1/contract/kline/index_price/BTC_USDT?interval=Min60"),
    ("fair price kline", "/api/v1/contract/kline/fair_price/BTC_USDT?interval=Min60"),
    ("price kline (in use)", "/api/v1/contract/kline/BTC_USDT?interval=Min60"),
]

LIVE_ONLY = [
    ("ticker (in use)", "/api/v1/contract/ticker"),
    ("contract detail (in use)", "/api/v1/contract/detail"),
    ("order book depth", "/api/v1/contract/depth/BTC_USDT"),
    ("depth commits", "/api/v1/contract/depth_commits/BTC_USDT/5"),
    ("recent trades", "/api/v1/contract/deals/BTC_USDT"),
    ("funding rate now", "/api/v1/contract/funding_rate/BTC_USDT"),
    ("index price", "/api/v1/contract/index_price/BTC_USDT"),
    ("fair price", "/api/v1/contract/fair_price/BTC_USDT"),
    ("insurance fund", "/api/v1/contract/risk_reverse"),
    ("support currencies", "/api/v1/contract/support_currencies"),
]

ABSENT = [
    ("open interest history", "/api/v1/contract/open_interest/BTC_USDT"),
    ("open interest history 2", "/api/v1/contract/openInterest?symbol=BTC_USDT"),
    ("hold_vol history", "/api/v1/contract/hold_vol/BTC_USDT"),
    ("hold_vol kline", "/api/v1/contract/kline/hold_vol/BTC_USDT?interval=Min60"),
    ("tiered fee rate", "/api/v1/contract/tiered_fee_rate?symbol=BTC_USDT"),
]


async def funding_depth(sess):
    """How far back funding actually goes — the number that made it usable."""
    _, body = await get(sess, "/api/v1/contract/funding_rate/history"
                              "?symbol=BTC_USDT&page_num=1&page_size=100")
    d = json.loads(body)["data"]
    await asyncio.sleep(PACE)
    _, body = await get(sess, f"/api/v1/contract/funding_rate/history"
                              f"?symbol=BTC_USDT&page_num={d['totalPage']}&page_size=100")
    old = json.loads(body)["data"]["resultList"][-1]
    new = d["resultList"][0]
    span = (new["settleTime"] - old["settleTime"]) / 86400000
    return d["totalCount"], span, old["settleTime"] / 1000, new["settleTime"] / 1000


async def fees_and_minimums(sess):
    """Fee rates and minimum order size across the universe the bot scans."""
    _, body = await get(sess, "/api/v1/contract/detail")
    spec = json.loads(body)["data"]
    await asyncio.sleep(PACE)
    _, body = await get(sess, "/api/v1/contract/ticker")
    tick = {t["symbol"]: t for t in json.loads(body)["data"]}

    live = [x for x in spec
            if x["symbol"].endswith("_USDT") and x.get("state") == 0
            and (tick.get(x["symbol"], {}).get("amount24") or 0) >= MIN_VOL_USDT]
    live.sort(key=lambda x: -(tick[x["symbol"]].get("amount24") or 0))
    live = live[:TOP_N or len(live)]

    mins = sorted(((x.get("minVol") or 1) * (x.get("contractSize") or 1)
                   * (tick[x["symbol"]].get("lastPrice") or 0), x["symbol"])
                  for x in live)
    return live, mins


async def main():
    async with aiohttp.ClientSession() as sess:
        print("MEXC PUBLIC SURFACE — no API key, no signature, probed "
              f"{time.strftime('%Y-%m-%d')}\n")

        for title, group in (("HAS HISTORY — backtestable today", HISTORY),
                             ("LIVE ONLY — log forward or nothing", LIVE_ONLY),
                             ("ABSENT — confirmed 404/error", ABSENT)):
            print(f"{'=' * 92}\n{title}\n{'=' * 92}")
            for name, path in group:
                ok, shape = await probe(sess, name, path)
                print(f"  {'OK ' if ok else 'no '} {name:<26}{shape}")
                await asyncio.sleep(PACE)
            print()

        n, span, t0, t1 = await funding_depth(sess)
        print(f"{'=' * 92}\nFUNDING HISTORY DEPTH\n{'=' * 92}")
        print(f"  {n} settlements on BTC_USDT · {span:.0f} days "
              f"({time.strftime('%Y-%m-%d', time.gmtime(t0))} -> "
              f"{time.strftime('%Y-%m-%d', time.gmtime(t1))})")
        print("  Longer than the 333-day window every study here runs on, so it")
        print("  joins to existing rows directly. riptide/market.py said this")
        print("  was impossible until 12 Sep; it never was.\n")
        await asyncio.sleep(PACE)

        live, mins = await fees_and_minimums(sess)
        mk = Counter(x.get("makerFeeRate") for x in live)
        tk = Counter(x.get("takerFeeRate") for x in live)
        zero_t = sum(v for k, v in tk.items() if k == 0)
        print(f"{'=' * 92}\nFEES AND MINIMUMS ACROSS THE SCANNED UNIVERSE "
              f"({len(live)} symbols)\n{'=' * 92}")
        print(f"  maker rates: {sorted(mk.items())}")
        print(f"  taker rates: {sorted(tk.items())}")
        print(f"  ZERO taker fee: {zero_t}/{len(live)} = "
              f"{100 * zero_t / max(len(live), 1):.0f}%")
        print("  Every study here charges 0.02/0.06 maker/taker, so the measured")
        print("  numbers are a FLOOR. They cannot simply be rerun at zero: today's")
        print("  schedule says nothing about the 333-day window, and promotional")
        print("  zero-fee zones end.\n")
        print(f"  minimum order notional: cheapest {mins[0][1]} ${mins[0][0]:.4f}"
              f" · median ${mins[len(mins) // 2][0]:.2f}"
              f" · dearest {mins[-1][1]} ${mins[-1][0]:.2f}")
        print(f"  needing over $10: {sum(1 for m, _ in mins if m > 10)}"
              f" · over $50: {sum(1 for m, _ in mins if m > 50)}")
        print("  So a small account can place nearly the whole universe.")


if __name__ == "__main__":
    asyncio.run(main())
