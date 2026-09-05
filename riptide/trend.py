"""
Higher-timeframe trend filter.

The reference indicator exposes a "By Trend" filter driven by a daily
Supertrend, and ships it switched off. Measured across 50 symbols over 41.6
days, with the best exit found (1R target), it is the only thing tested in
this project that separates winning signals from losing ones:

    with the daily trend      990 setups   +0.083 R/setup  ± 0.023
    against the daily trend   971 setups   -0.053 R/setup  ± 0.023
    difference                +0.135 R  (+4.2 SE)

Six engine-parameter variants and two entry timeframes all came back inside
noise. The edge was never in the parameters; it was in which half of the
signals get taken.

Caveats: one 41.6-day window, and no fees or slippage in those figures —
about 0.03R per round trip would still leave the aligned half positive.

Supertrend here mirrors the reference's defaults: daily bars, ATR 14,
factor 5.
"""

from __future__ import annotations

import time
from bisect import bisect_right

from .config import (TREND_FACTOR, TREND_INTERVAL, TREND_LEN, log)
from .engine import Candle, atr_series

# Daily bars change once a day; refetching them every scan is pure waste.
_CACHE: dict[str, tuple[float, list[int], list[int]]] = {}
_TTL = 3600.0


def supertrend(cs: list[Candle], length: int = TREND_LEN,
               factor: float = TREND_FACTOR) -> list[int]:
    """+1 uptrend, -1 downtrend, one value per bar. Never looks ahead."""
    atr = atr_series(cs, length)
    out: list[int] = []
    upper = lower = None
    direction = 1
    for i, c in enumerate(cs):
        hl2 = (c.h + c.l) / 2.0
        up = hl2 + factor * atr[i]
        lo = hl2 - factor * atr[i]
        if i == 0:
            upper, lower = up, lo
            out.append(direction)
            continue
        # Bands only tighten while price stays on their side, which is what
        # makes the line ratchet rather than whipsaw with every ATR tick.
        up = min(up, upper) if cs[i - 1].c <= upper else up
        lo = max(lo, lower) if cs[i - 1].c >= lower else lo
        if c.c > upper:
            direction = 1
        elif c.c < lower:
            direction = -1
        upper, lower = up, lo
        out.append(direction)
    return out


async def direction_at(sess, symbol: str, when: int, fetch) -> int | None:
    """
    Trend on the bar that had already closed at `when`. Returns +1, -1, or
    None when there is not enough history to judge — the caller keeps the
    setup in that case rather than dropping it on missing data.
    """
    now = time.monotonic()
    hit = _CACHE.get(symbol)
    if hit is None or now - hit[0] > _TTL:
        cs = await fetch(sess, symbol, TREND_INTERVAL)
        if len(cs) < TREND_LEN + 5:
            log.warning("%s: only %d %s bars, trend filter skipped",
                        symbol, len(cs), TREND_INTERVAL)
            _CACHE[symbol] = (now, [], [])
            return None
        _CACHE[symbol] = (now, [c.t for c in cs], supertrend(cs))
        hit = _CACHE[symbol]

    _, times, dirs = hit
    if not times:
        return None
    # bisect_right - 1 is the last bar at or before `when`: strictly the past.
    i = bisect_right(times, when) - 1
    return dirs[i] if 0 <= i < len(dirs) else None
