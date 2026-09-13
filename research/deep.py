"""Deep history. The exchange serves 2000 bars per request — but ANY window.

THE SINGLE BIGGEST CONSTRAINT ON THIS PROJECT WAS NEVER A HYPOTHESIS. It was
that every study ran on 42 days, because a kline request returns at most 2000
bars and 2000 Min30 bars is six weeks. Forty-five hypotheses were tested at a
standard error of about 0.17 R on the key cell, where a genuine +0.15 R filter
registers at 0.9 SE and gets filed as "inside noise". Most of those negatives
could not have found an effect that was really there.

The cap is on the RESPONSE, not on the history. Asking for a window that ended
20000 bars ago returns 2000 bars from 458 days ago. Paging backwards therefore
yields as much history as the symbol has, and on Min30 that is 333 days with no
discontinuities, in about three seconds a symbol.

SURVIVORSHIP IS THE PRICE AND IT MUST BE PAID KNOWINGLY. The universe is the
sixty most liquid perpetuals TODAY. Walking those same sixty back a year
over-samples coins that went up and excludes every one that died or delisted,
so absolute expectancy from the deep window is biased OPTIMISTIC — and more so
for longs than shorts. A replication that comes back BETTER than the 42-day
result is evidence of that bias, not of a stronger edge.

  What survivorship does NOT corrupt much is a comparison between two arms
  measured on the same rows: filter against no filter, policy against policy.
  Both draw from the same biased pool, so the bias is largely common-mode. Read
  differences here; distrust levels.

    from research.deep import load_deep
    cs = await load_deep(sess, "BTC_USDT", "Min30", days=333)
"""
from __future__ import annotations

import gzip
import json
import os
import time

from riptide.config import BAR_SECONDS, log
from riptide.engine import Candle
from riptide.exchange import BASE, get_json

PAGE = 2000                                   # the exchange's hard response cap
CACHE = os.environ.get("RIPTIDE_DEEP_CACHE", "")


def _path(symbol, interval, days):
    return os.path.join(CACHE, f"{symbol}.{interval}.{days}.json.gz")


def _read(symbol, interval, days):
    if not CACHE:
        return None
    p = _path(symbol, interval, days)
    if not os.path.exists(p):
        return None
    try:
        with gzip.open(p, "rt") as f:
            return [Candle(*row) for row in json.load(f)]
    except Exception:
        return None


def _write(symbol, interval, days, cs):
    if not CACHE or not cs:
        return
    os.makedirs(CACHE, exist_ok=True)
    tmp = _path(symbol, interval, days) + ".tmp"
    with gzip.open(tmp, "wt") as f:
        json.dump([[c.t, c.o, c.h, c.l, c.c, c.v] for c in cs], f)
    os.replace(tmp, _path(symbol, interval, days))


async def load_deep(sess, symbol: str, interval: str, days: int = 333,
                    max_pages: int = 40) -> list[Candle]:
    """Closed candles going back `days`, newest last, paged and de-duplicated.

    Keyed by bar OPEN time in a dict, so overlapping pages cannot double-count
    a bar and a page boundary cannot drop one. The forming bar is excluded on
    the same rule the live fetch uses — the engine only ever sees finished
    candles, so research and production see the same chart.
    """
    step = BAR_SECONDS[interval]
    hit = _read(symbol, interval, days)
    if hit is not None:
        return hit

    now = int(time.time())
    floor = now - days * 86400
    end, seen = now, {}
    for _ in range(max_pages):
        d = await get_json(sess, f"{BASE}/api/v1/contract/kline/{symbol}",
                           {"interval": interval, "start": end - PAGE * step,
                            "end": end})
        k = d and d.get("data")
        if not k or not k.get("time"):
            break
        vol = k.get("vol") or [0] * len(k["time"])
        for t, o, h, l, c, v in zip(k["time"], k["open"], k["high"],
                                    k["low"], k["close"], vol):
            t = int(t)
            if t + step <= now:
                seen[t] = Candle(t, float(o), float(h), float(l), float(c),
                                 float(v))
        oldest = min(k["time"])
        if oldest <= floor or len(k["time"]) < PAGE:
            break                              # covered, or the symbol ends here
        end = oldest - step

    cs = [seen[t] for t in sorted(seen) if t >= floor]
    if cs:
        gaps = sum(1 for a, b in zip(cs, cs[1:]) if b.t - a.t != step)
        if gaps:
            # Worth saying rather than silently analysing a broken series: a
            # hole means a page was refused, not that the market stopped.
            log.warning("%s %s: %d discontinuities in %d bars",
                        symbol, interval, gaps, len(cs))
        _write(symbol, interval, days, cs)
    return cs


async def load_universe(sess, symbols, interval: str, days: int = 333,
                        min_bars: int = 2000):
    """{symbol: candles} for everything with enough history to be worth scoring.

    Symbols listed more recently than `days` come back short. They are KEPT if
    they clear `min_bars`, because dropping them would narrow the universe to
    the oldest listings and add a second survivorship filter on top of the one
    already baked in.
    """
    out = {}
    for s in symbols:
        try:
            cs = await load_deep(sess, s, interval, days)
        except Exception as e:
            log.warning("%s: deep fetch failed: %s", s, e)
            continue
        if len(cs) >= min_bars:
            out[s] = cs
    return out
