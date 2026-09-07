"""
Higher-timeframe trend filter.

The reference indicator exposes a "By Trend" filter driven by a daily
Supertrend, and ships it switched off. It is the only thing tested in this
project that separates winning signals from losing ones. Measured across 50
symbols over 41.6 days, 1R target, fills counted only from the bar the setup
became detectable:

    with the daily trend       582 setups   +0.119 R/setup  ± 0.034
    against the daily trend    606 setups   -0.016 R/setup  ± 0.033
    difference                +0.135 R  ± 0.047  (+2.8 SE)

An earlier run of the same comparison read +0.103 / -0.008 (+0.110, +3.8 SE)
over 2026 setups. Two things moved it: fvg_scan_from="mss" roughly halves the
setup count, and direction_at used to read the daily bar that had OPENED at
the signal rather than the one that had CLOSED, which was worth about 1.2% of
signals. The corrected figure is smaller and less certain; the separation is
what survived both, which is the point.

Six engine-parameter variants, two entry timeframes, five exit families and
four targets all came back inside noise. The edge was never in the parameters
or the exit; it was in which half of the signals get taken.

Trust the separation, not the level it sits on. The gap has come back at
+0.135, +0.095 and +0.110 across two windows, two symbol sets and two
scoring methods. The absolute expectancy under it has ranged from -0.05 to
+0.32 over the same comparisons — it moves with the window, and a figure
that unstable cannot size a position.

Caveats: still one regime at a time, and no fees or slippage — about 0.03R
per round trip, which the aligned half survives and the other half does not.

Supertrend here mirrors the reference's defaults: daily bars, ATR 14,
factor 5.
"""

from __future__ import annotations

import time
from bisect import bisect_right

from .config import (BAR_SECONDS, BTC_REGIME_INTERVAL, CFG, DI_INTERVAL,
                     TREND_FACTOR, TREND_INTERVAL, TREND_LEN, log)
from .engine import (Candle, atr_series, daily_zones, in_zone,
                     rma as atr_rma)

# Daily bars change once a day; refetching them every scan is pure waste.
# (fetched_at, bar times, supertrend dirs, DI dirs)
_CACHE: dict[tuple[str, str],
             tuple[float, list[int], list[int], list[int]]] = {}
_TTL = 3600.0
# A FAILED fetch is cached far more briefly than a good one. It used to share
# the hour-long TTL, which meant one rate-limited request muted a symbol's
# trend and POI readings until the next hour — and under POI_REQUIRED a
# missing POI reading is the difference between an alert and silence. Retrying
# in two minutes costs one request and removes an hour-long blind spot.
_FAIL_TTL = 120.0


def di_direction(cs: list[Candle], length: int = 14) -> list[int]:
    """
    Wilder's +DI / -DI as a direction: +1 where +DI leads, -1 where -DI does.

    Measured stronger than the SuperTrend above and replicated on every split
    — see GRADES in engine.py. It sets the letter on confirmed alerts; the
    SuperTrend line is kept beside it so both can be watched live before
    anything is filtered on either.
    """
    tr, pdm, ndm = [], [], []
    for i, c in enumerate(cs):
        if i == 0:
            tr.append(c.h - c.l)
            pdm.append(0.0)
            ndm.append(0.0)
            continue
        p = cs[i - 1]
        tr.append(max(c.h - c.l, abs(c.h - p.c), abs(c.l - p.c)))
        up, dn = c.h - p.h, p.l - c.l
        pdm.append(up if (up > dn and up > 0) else 0.0)
        ndm.append(dn if (dn > up and dn > 0) else 0.0)
    atr = atr_rma(tr, length)
    pd, nd = atr_rma(pdm, length), atr_rma(ndm, length)
    out = []
    for a, p_, n_ in zip(atr, pd, nd):
        if a <= 0:
            out.append(0)
            continue
        out.append(1 if p_ > n_ else -1 if n_ > p_ else 0)
    return out


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


async def _series(sess, symbol: str, fetch, interval: str):
    """Cached (fetched_at, times, supertrend, DI) for one symbol on `interval`.

    Keyed on the interval as well as the symbol, because the SuperTrend filter
    and DI no longer read the same timeframe — see TREND_INTERVAL and
    DI_INTERVAL in config.py for the measurement that separated them. When
    both are set to the same value this is one fetch and one cache entry, as
    it was before.

    Both readings still come off one fetch, so whichever timeframe is asked
    for costs a single request per TTL.
    """
    now = time.monotonic()
    key = (symbol, interval)
    hit = _CACHE.get(key)
    ttl = _TTL if (hit and hit[1]) else _FAIL_TTL
    if hit is None or now - hit[0] > ttl:
        cs = await fetch(sess, symbol, interval)
        if not cs:
            # NOTHING came back. That is a failed request, not a fact about
            # the symbol, and the caller must be able to tell the difference —
            # see poi_at.
            log.warning("%s: no %s bars returned, retrying in %.0fs",
                        symbol, interval, _FAIL_TTL)
            _CACHE[key] = (now, [], [], [], [])
            return None
        # Some bars came back, just not many. That IS a fact about the symbol:
        # a coin listed six days ago genuinely has six daily candles. The
        # SuperTrend and DI need a full window and are left empty, but the
        # zones are computed from whatever exists and are correct for it —
        # six bars simply produce few or no zones, which is the true answer
        # rather than a missing one.
        short = len(cs) < TREND_LEN + 5
        if short:
            log.info("%s: only %d %s bars — too new for a trend reading; "
                     "POI still computed from what exists", symbol, len(cs),
                     interval)
        _CACHE[key] = (now, [c.t for c in cs],
                       [] if short else supertrend(cs),
                       [] if short else di_direction(cs),
                       daily_zones(cs, atr_series(cs, CFG.atr_len)))
        hit = _CACHE[key]
    return hit if hit[1] else None


def _at(times, series, when, interval: str) -> int | None:
    """Value on the last bar whose CLOSE is at or before `when`. See the note
    in direction_at: bar times are OPEN times, so the forming bar must be
    excluded by arithmetic, not by hoping it was dropped upstream. The step
    subtracted must be the step of the series being read, which is why the
    interval is passed rather than assumed."""
    i = bisect_right(times, when - BAR_SECONDS[interval]) - 1
    return series[i] if 0 <= i < len(series) else None


async def btc_at(sess, when: int, fetch) -> int | None:
    """BTC's SuperTrend direction on BTC_REGIME_INTERVAL, at `when`.

    Market context rather than symbol context: most alts follow BTC intraday,
    so the same setup is a different bet depending on which way BTC is going.
    Uses the same cache and the same last-closed-bar arithmetic as the rest of
    this module, so it costs one extra fetch per TTL for the whole scan, not
    one per symbol.

    Shown on the alert, never used to suppress one. Measured on early signals:
    on the discovery window, agreeing +0.045 against disagreeing -0.129
    (+0.174, 3.6 SE); on a held-out window that had never been looked at,
    +0.010 against -0.113 (+0.123, 1.8 SE), same sign on all four splits. The
    direction replicated at about 70% of the discovered size — the shape of a
    real effect that was overestimated where it was found — but it did not
    clear the pre-registered 3 SE bar, so it informs and does not decide.
    """
    hit = await _series(sess, "BTC_USDT", fetch, BTC_REGIME_INTERVAL)
    if hit is None:
        return None
    return _at(hit[1], hit[2], when, BTC_REGIME_INTERVAL) or None


async def poi_at(sess, symbol: str, when: int, price: float, is_long: bool,
                 fetch) -> bool | None:
    """Did the raid land inside an aligned daily order block or fair value gap?

    Reads the same cached daily bars as the SuperTrend and DI, so it costs no
    extra request.

    Returns None — not False — when the daily fetch came back EMPTY. The
    distinction is the whole point: "the raid was not in a zone" and "we could
    not find out" look identical to a boolean, and under POI_REQUIRED the
    first means suppress while the second must mean send. Daily fetches do
    fail transiently, and collapsing the two would silently mute a symbol for
    as long as the failure lasted.

    A symbol with real but SHORT history is not unknown. A coin listed six
    days ago has six daily candles and therefore genuinely has no daily point
    of interest, so it answers False and is suppressed by the filter — which
    is correct: a policy built on daily context cannot be run on a symbol that
    has none.
    """
    hit = await _series(sess, symbol, fetch, TREND_INTERVAL)
    if hit is None:
        return None
    return in_zone(hit[4], when, price, is_long, BAR_SECONDS[TREND_INTERVAL])


async def di_at(sess, symbol: str, when: int, fetch) -> int | None:
    """DI direction on DI_INTERVAL's last closed bar at `when`. +1, -1, None."""
    hit = await _series(sess, symbol, fetch, DI_INTERVAL)
    if hit is None:
        return None
    return _at(hit[1], hit[3], when, DI_INTERVAL) or None


async def direction_at(sess, symbol: str, when: int, fetch) -> int | None:
    """
    Trend on the bar that had already closed at `when`. Returns +1, -1, or
    None when there is not enough history to judge — the caller keeps the
    setup in that case rather than dropping it on missing data.
    """
    hit = await _series(sess, symbol, fetch, TREND_INTERVAL)
    if hit is None:
        return None
    _, times, dirs, _, _ = hit
    if not times:
        return None
    # Candle.t is a bar OPEN time, so the last bar that had already CLOSED at
    # `when` is the last one with open + step <= when — not the last one with
    # open <= when, which is the bar still forming.
    #
    # Live the distinction never bites: fetch_candles drops the forming bar, so
    # today's daily candle is not in the series at all. In a BACKTEST every bar
    # is closed and present, so the looser reading handed a signal at 12:00 the
    # trend computed from that day's close — hours of lookahead. It moved 1.2%
    # of signals and the headline gap from +0.149 to +0.138 (still +2.9 SE), so
    # nothing built on it changed; it is fixed so measurements and live agree.
    i = bisect_right(times, when - BAR_SECONDS[TREND_INTERVAL]) - 1
    return dirs[i] if 0 <= i < len(dirs) else None
