"""Volume, BTC regime, RSI, ADX and volatility regime, on the fixed scorer.

All five were tested earlier on the broken one. Volume was untestable at all
until Candle gained a volume field.

    PYTHONPATH=. python3 research/studies/context.py
"""
import research.env                                     # noqa: F401  MUST be first
import asyncio, statistics                              # noqa: E402
from bisect import bisect_right                         # noqa: E402

import aiohttp                                          # noqa: E402
from riptide.config import BAR_SECONDS, CFG             # noqa: E402
from riptide.engine import rsi_series                   # noqa: E402
from riptide.exchange import fetch_candles              # noqa: E402
from riptide.trend import di_direction, supertrend      # noqa: E402
from research.data import load, atr_at                  # noqa: E402
from research.harness import report, risk_terciles      # noqa: E402

BTC = {}
_C = {}


def L(r):
    return 1 if r.signal.is_long else -1


def grab(r):
    idx = {c.t: i for i, c in enumerate(r.candles)}
    return idx.get(getattr(r.signal, "grab_time", 0) or r.signal.sweep_time, r.bar)


def cached(r):
    k = id(r.candles)
    if k not in _C:
        cs = r.candles
        _C[k] = (rsi_series(cs), [c.v for c in cs])
    return _C[k]


def relvol(r, bar, n=20):
    vols = cached(r)[1]
    if bar < n or not any(vols):
        return None
    med = statistics.median(vols[bar - n:bar]) or 1e-12
    return vols[bar] / med


# ---- volume -------------------------------------------------------------
def f_sweep_vol(r):
    return relvol(r, grab(r))


def f_gap_vol(r):
    return relvol(r, r.bar)


# ---- RSI ----------------------------------------------------------------
def f_rsi(r):
    return (50 - cached(r)[0][grab(r)]) * L(r)


# ---- ADX / DI on the chart timeframe ------------------------------------
def f_adx_dir(r):
    k = ("di", id(r.candles))
    if k not in _C:
        _C[k] = di_direction(r.candles)
    d = _C[k][r.bar]
    return None if not d else (d > 0) == r.signal.is_long


# ---- volatility regime --------------------------------------------------
def f_atr_pct(r):
    a = atr_at(r)
    k = ("atrs", id(r.candles))
    if k not in _C:
        from riptide.engine import atr_series
        _C[k] = sorted(x for x in atr_series(r.candles, CFG.atr_len) if x > 0)
    arr = _C[k]
    return 100 * bisect_right(arr, a) / max(len(arr), 1)


# ---- BTC regime ---------------------------------------------------------
def f_btc(r):
    if not BTC or r.symbol == "BTC_USDT":
        return None
    times, st = BTC["Day1"]
    j = bisect_right(times, r.candles[r.bar].t - BAR_SECONDS["Day1"]) - 1
    if not 0 <= j < len(st) or not st[j]:
        return None
    return (st[j] > 0) == r.signal.is_long        # +1 is up in supertrend()


def f_btc_30m(r):
    if "Min30" not in BTC or r.symbol == "BTC_USDT":
        return None
    times, st = BTC["Min30"]
    j = bisect_right(times, r.candles[r.bar].t - BAR_SECONDS["Min30"]) - 1
    if not 0 <= j < len(st) or not st[j]:
        return None
    return (st[j] > 0) == r.signal.is_long


FEATURES = [
    ("sweep-bar relative volume", f_sweep_vol),
    ("gap-bar relative volume", f_gap_vol),
    ("RSI extension at the raid", f_rsi),
    ("chart DI agrees", f_adx_dir),
    ("ATR percentile (volatility regime)", f_atr_pct),
    ("BTC daily trend agrees", f_btc),
    ("BTC 30m trend agrees", f_btc_30m),
]


async def main():
    rows = await load()
    async with aiohttp.ClientSession() as s:
        for iv in ("Day1", "Min30"):
            cs = await fetch_candles(s, "BTC_USDT", iv)
            if len(cs) > 40:
                BTC[iv] = ([c.t for c in cs], supertrend(cs))
    vols = [c.v for r in rows[:1] for c in r.candles[:5]]
    print(f"{len(rows)} signals · volume present: {any(vols)} {vols}")
    for kind in ("confirmed", "early"):
        sub = [r for r in rows if r.kind == kind]
        print(f"\n{'='*66}\n{kind.upper()}  n={len(sub)}\n{'='*66}")
        for name, fn in FEATURES:
            try:
                report(name, sub, fn, control=risk_terciles)
            except Exception as e:
                print(f"\n{name}\n  skipped: {type(e).__name__} {e}")

asyncio.run(main())
