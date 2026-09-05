"""MEXC futures REST access.

Only reads: contract listings, 24h turnover and candles. There is no API key
and no signed request anywhere in this module.
"""

from __future__ import annotations

import asyncio
import time

import aiohttp

from .config import (BASE, INTERVAL, LOOKBACK, MIN_VOL_USDT,
                     QUOTE, SYMBOLS_ENV, BAR_SECONDS, log)
from .engine import Candle

async def get_json(sess, url, params=None, tries=3):
    for k in range(tries):
        try:
            async with sess.get(url, params=params, timeout=aiohttp.ClientTimeout(total=20)) as r:
                if r.status == 429:
                    await asyncio.sleep(2 * (k + 1))
                    continue
                r.raise_for_status()
                return await r.json()
        except Exception as e:
            if k == tries - 1:
                log.warning("GET %s failed: %s", url, e)
                return None
            await asyncio.sleep(1.5 * (k + 1))
    return None


async def list_symbols(sess) -> list[str]:
    # An explicit list is a deliberate choice; never second-guess it.
    if SYMBOLS_ENV:
        return [s.strip() for s in SYMBOLS_ENV.split(",") if s.strip()]
    d = await get_json(sess, f"{BASE}/api/v1/contract/detail")
    if not d or not d.get("data"):
        return []
    out = []
    for c in d["data"]:
        if c.get("quoteCoin") != QUOTE:
            continue
        if c.get("state") != 0:            # 0 = enabled
            continue
        if c.get("apiAllowed") is False:
            continue
        out.append(c["symbol"])
    return await filter_by_turnover(sess, out)


async def filter_by_turnover(sess, symbols: list[str]) -> list[str]:
    """
    Drop symbols below MIN_VOL_USDT of 24h turnover.

    contract/detail carries no volume, so this needs contract/ticker, where
    amount24 is turnover in the quote currency (volume24 is contract count,
    which is not comparable across symbols).

    Falls back to the unfiltered list on any failure. This runs at startup
    and on the 6-hourly refresh, and an alerting service that stays up on a
    stale symbol list is better than one that exits because a secondary
    endpoint blipped.
    """
    if MIN_VOL_USDT <= 0 or not symbols:
        return symbols

    t = await get_json(sess, f"{BASE}/api/v1/contract/ticker")
    rows = (t or {}).get("data") or []
    if not rows:
        log.warning("ticker unavailable; volume filter skipped, keeping %d symbols",
                    len(symbols))
        return symbols

    turnover = {}
    for r in rows:
        try:
            turnover[r["symbol"]] = float(r.get("amount24") or 0.0)
        except (KeyError, TypeError, ValueError):
            continue

    kept = [s for s in symbols if turnover.get(s, 0.0) >= MIN_VOL_USDT]
    if not kept:
        log.warning("volume filter (%.0f USDT) matched no symbols; "
                    "threshold looks too high, keeping %d unfiltered",
                    MIN_VOL_USDT, len(symbols))
        return symbols

    log.info("volume filter: %d/%d symbols at or above %.0f USDT 24h turnover",
             len(kept), len(symbols), MIN_VOL_USDT)
    return kept


async def fetch_candles(sess, symbol: str, interval: str = "") -> list[Candle]:
    """Closed candles, newest last. Defaults to the structure timeframe."""
    interval = interval or INTERVAL
    if interval not in BAR_SECONDS:
        log.warning("unknown interval %r, falling back to %s", interval, INTERVAL)
        interval = INTERVAL
    step = BAR_SECONDS[interval]
    now = int(time.time())
    params = {"interval": interval, "start": now - LOOKBACK * step, "end": now}
    d = await get_json(sess, f"{BASE}/api/v1/contract/kline/{symbol}", params)
    if not d or not d.get("data"):
        return []
    k = d["data"]
    try:
        rows = list(zip(k["time"], k["open"], k["high"], k["low"], k["close"]))
    except (KeyError, TypeError):
        return []
    # Drop the forming bar. This is the confirmOnBarClose rule: the engine only
    # ever sees finished candles, so its output matches the chart.
    return [Candle(int(t), float(o), float(h), float(l), float(c))
            for t, o, h, l, c in rows if int(t) + step <= now]
