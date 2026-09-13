"""MEXC futures REST access.

Only reads: contract listings, 24h turnover and candles. There is no API key
and no signed request anywhere in this module.
"""

from __future__ import annotations

import asyncio
import time

import aiohttp

from .config import (BASE, BAR_SECONDS, EXCLUDE_TRADFI, INTERVAL, LOOKBACK,
                     MIN_REQUEST_GAP, MIN_VOL_USDT, QUOTE, SCAN_INTERVAL,
                     SYMBOLS_ENV, TOP_N, log)
from .engine import Candle

# One pacer for the whole process. The lock is held across the sleep on
# purpose: that is what turns a burst into a queue.
_pace_lock = asyncio.Lock()
_last_request = 0.0

# THE GAP ADAPTS, BECAUSE THE RIGHT VALUE IS NOT KNOWABLE FROM HERE. MEXC does
# not publish a rate for this endpoint, it varies with what else shares the IP,
# and 0.07s was measured as safe on a 60-symbol universe that has since grown
# to 115 across three timeframes plus context fetches. On 12 Sep it was no
# longer safe: 20-26 symbols per timeframe came back throttled every cycle.
#
# Rather than replace one guess with another, the pacer widens itself when the
# exchange refuses and narrows again when it stops. A fixed number would be
# wrong again the next time the universe changes.
_gap_mult = 1.0

# THE CEILING IS DERIVED, NOT PICKED, because a picked one goes stale silently.
# A first version hardcoded x12, which was safe at a 0.07s floor and became
# 16.8 minutes per cycle the moment the floor moved to 0.12 — longer than the
# 15-minute scan it has to fit inside. Its own test caught that, which is the
# argument for computing it here instead.
#
# The budget is HALF the scan interval: a scan that eats its whole window
# leaves nothing for the tracker, the watches and the command poller, and a
# cycle that overruns delays every cycle after it. Slowing down past this point
# would cost more than the symbols it saves, so the pacer stops widening and
# the refusals become visible as dropped symbols instead — which /status and
# the scan summary both report.
EXPECTED_REQUESTS = 700          # ~115 symbols x 3 timeframes + context
GAP_BUDGET = 0.5                 # fraction of one scan interval


def _gap_ceiling() -> float:
    if MIN_REQUEST_GAP <= 0:
        return 1.0
    budget = BAR_SECONDS.get(SCAN_INTERVAL, 900) * GAP_BUDGET
    return max(1.0, budget / EXPECTED_REQUESTS / MIN_REQUEST_GAP)


GAP_MULT_MAX = _gap_ceiling()
GAP_ON_THROTTLE = 1.6    # widen hard: being refused costs a whole symbol
# Narrow slowly: ~230 clean requests to halve the penalty, so one bad patch
# does not immediately undo itself.
GAP_DECAY = 0.997


def note_throttled() -> None:
    """Widen the gap after a refusal. Called from get_json, not from callers."""
    global _gap_mult
    was = _gap_mult
    _gap_mult = min(GAP_MULT_MAX, _gap_mult * GAP_ON_THROTTLE)
    # Logged at each doubling rather than each refusal: during a bad patch this
    # fires on most requests, and a line per request would bury the scan log.
    if _gap_mult >= was * 2 or (was < GAP_MULT_MAX <= _gap_mult):
        log.warning("rate limited — request gap widened to %.0fms (x%.1f). "
                    "Raise RIPTIDE_MIN_REQUEST_GAP if this persists.",
                    MIN_REQUEST_GAP * _gap_mult * 1000, _gap_mult)


def gap_mult() -> float:
    """The current widening factor, for /status."""
    return _gap_mult


async def _pace() -> None:
    global _last_request, _gap_mult
    if MIN_REQUEST_GAP <= 0:
        return
    async with _pace_lock:
        gap = MIN_REQUEST_GAP * _gap_mult
        wait = _last_request + gap - time.monotonic()
        if wait > 0:
            await asyncio.sleep(wait)
        _last_request = time.monotonic()
        if _gap_mult > 1.0:
            _gap_mult = max(1.0, _gap_mult * GAP_DECAY)


# MEXC SIGNALS THROTTLING IN THE BODY, NOT IN THE STATUS LINE. It answers
# HTTP 200 with {"success": false, "code": 510, "message": "Requests are too
# frequent, please try again later"}. So raise_for_status() passes, the 429
# branch below never runs, and the throttle is handed downstream as an ordinary
# empty response.
#
# That is exactly the silence this function was written to remove, arriving
# through a different door: on 12 Sep a live scan logged "no candles returned"
# for 20-26 symbols PER TIMEFRAME every cycle and reported "scanned 115
# symbols" immediately after. A quarter of the universe was unscanned and the
# only trace was a WARNING that reads like a quiet market.
#
# 510 is the documented "too frequent" code; 506 and 507 are its siblings. Any
# of them means back off and retry, never "no data".
THROTTLE_CODES = {506, 507, 510}


def _throttled_body(d) -> bool:
    """True when a 200 response is actually a rate-limit refusal."""
    return (isinstance(d, dict) and d.get("success") is False
            and d.get("code") in THROTTLE_CODES)


async def get_json(sess, url, params=None, tries=3):
    """One GET with retries. Returns None when it gives up.

    A 429 that survives every retry used to fall out of this loop and return
    None with NOTHING logged — only exceptions were. Being rate limited was
    therefore indistinguishable from a quiet market anywhere downstream:
    fetch_candles turns None into an empty list, scan_symbol returns no
    signals at all for a symbol under 100 bars, and the scan reports success.
    A throttled scanner looked exactly like a calm one.

    The same is now true of an in-body 510, which is how MEXC actually says it
    — see THROTTLE_CODES above.
    """
    throttled = False
    for k in range(tries):
        try:
            await _pace()
            async with sess.get(url, params=params, timeout=aiohttp.ClientTimeout(total=20)) as r:
                if r.status == 429:
                    throttled = True
                    note_throttled()
                    await asyncio.sleep(2 * (k + 1))
                    continue
                r.raise_for_status()
                d = await r.json()
                if _throttled_body(d):
                    throttled = True
                    note_throttled()
                    # Longer than the 429 backoff on purpose: a 200-with-510
                    # means the pacer is already over the line, so retrying
                    # promptly just spends another slot to be refused again.
                    await asyncio.sleep(2 * (k + 1))
                    continue
                return d
        except Exception as e:
            if k == tries - 1:
                log.warning("GET %s failed: %s", url, e)
                return None
            await asyncio.sleep(1.5 * (k + 1))
    if throttled:
        log.warning("RATE LIMITED after %d tries: %s — this symbol contributes "
                    "no signals this cycle", tries, url.rsplit("/", 1)[-1])
    return None


async def list_symbols(sess) -> list[str]:
    # An explicit list is a deliberate choice; never second-guess it.
    if SYMBOLS_ENV:
        return [s.strip() for s in SYMBOLS_ENV.split(",") if s.strip()]
    d = await get_json(sess, f"{BASE}/api/v1/contract/detail")
    if not d or not d.get("data"):
        return []
    out, skipped = [], 0
    for c in d["data"]:
        if c.get("quoteCoin") != QUOTE:
            continue
        if c.get("state") != 0:            # 0 = enabled
            continue
        if c.get("apiAllowed") is False:
            continue
        if EXCLUDE_TRADFI and any("tradfi" in p for p in
                                  (c.get("conceptPlate") or [])):
            skipped += 1
            continue
        out.append(c["symbol"])
    if skipped:
        log.info("skipped %d tokenised stock/commodity contracts; every "
                 "measurement here assumes 24/7 crypto perpetuals", skipped)
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
    if kept and TOP_N > 0 and len(kept) > TOP_N:
        kept.sort(key=lambda s: turnover.get(s, 0.0), reverse=True)
        log.info("universe capped at the top %d by turnover; the cut is at "
                 "%.1fM 24h", TOP_N, turnover.get(kept[TOP_N - 1], 0.0) / 1e6)
        kept = kept[:TOP_N]
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
        # Empty here used to be silent, and it is the single most consequential
        # silence in the bot: no candles means no signals for this symbol this
        # cycle, which is indistinguishable from a symbol that simply had none.
        # Whatever the exchange said instead of candles is worth seeing.
        log.warning("%s %s: no candles returned — %s", symbol, interval,
                    "empty response" if not d else str(d)[:160])
        return []
    k = d["data"]
    try:
        vol = k.get("vol") or [0] * len(k["time"])
        rows = list(zip(k["time"], k["open"], k["high"], k["low"], k["close"],
                        vol))
    except (KeyError, TypeError):
        return []
    # Drop the forming bar. This is the confirmOnBarClose rule: the engine only
    # ever sees finished candles, so its output matches the chart.
    return [Candle(int(t), float(o), float(h), float(l), float(c), float(v))
            for t, o, h, l, c, v in rows if int(t) + step <= now]
