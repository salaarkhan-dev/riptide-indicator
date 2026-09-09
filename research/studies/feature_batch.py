"""Thirty-one features at once — with an empirical null, because thirty-one.

WHAT IS BEING TESTED: ADX with its smoothing, EMA 21/51/100/200, SuperTrend
(10, 1.8), MACD, VWAP, Fibonacci position in the raid leg, and momentum
exhaustion — each on the signal's own timeframe and, where it makes sense, on
4h, 8h and daily as well.

THE PROBLEM IS THE COUNT, NOT ANY ONE FEATURE. Thirty-one tests at a 2 SE bar
produce about one and a half false positives from pure noise, by construction.
This session has already watched that happen three times at much smaller
counts: the trendline slope gave +4.4 SE and reversed, BTC regime gave +5.1 SE
and reversed, the pool swing count gave +2.4 SE and died on the next check. A
table of thirty-one results with the biggest one circled would be worthless.

SO THE NULL IS MEASURED RATHER THAN ASSUMED. Alongside the real features, 300
RANDOM ones are generated with the same shape — a coin flip per signal, at the
same keep-rate as the real feature it shadows — and put through the identical
pipeline. That gives the distribution of |SE| this machinery produces when
there is provably nothing there, on this exact data, with this exact sample
size. A real feature has to beat that distribution, not a textbook z-table.

Bonferroni would say 0.05/31, about 3.2 SE. The empirical null is better,
because it also absorbs whatever autocorrelation and cross-symbol clustering
this population has — 33% of signals arrive with 8+ others on the same close,
so these are nowhere near 3771 independent draws and a nominal SE overstates
what is known. The null feels that; a z-table does not.

PRE-REGISTERED, BEFORE THE FIRST NUMBER

  PRIMARY   A feature survives only if it clears the 95th percentile of the
            300-strong random null on the FULL panel AND holds its sign on the
            HELD-OUT half. Both, not either.

  REPORTED  Everything, sorted, with the null's own percentiles printed beside
            it. No feature is described as promising for beating 2 SE; at this
            count, 2 SE is the noise.

  DIRECTION is fixed per feature in advance and stated in its name: "with the
  trend" means the indicator agrees with the trade's direction. A feature that
  works backwards is a failed test, not a discovery, because there is no
  mechanism that predicts backwards for all of ADX, EMA, SuperTrend and MACD
  at once.

  EXPECTATION: nothing survives. ADX and volatility regime are already dead in
  context.py, EMA length was already swept in ema_len.py, and the daily
  SuperTrend and DI are already IN the grade. What is genuinely new here is
  the HTF versions of the rest, VWAP, Fibonacci and exhaustion.

    PYTHONPATH=. python3 research/studies/feature_batch.py
"""
import research.env                                     # noqa: F401  MUST be first

import asyncio                                          # noqa: E402
import random                                           # noqa: E402
import statistics                                       # noqa: E402
from bisect import bisect_right                         # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import BAR_SECONDS, INTERVAL        # noqa: E402
from riptide.engine import atr_series, rma as atr_rma   # noqa: E402
from riptide.exchange import fetch_candles, list_symbols  # noqa: E402
from riptide.trend import supertrend                    # noqa: E402
from research.data import load_sync                     # noqa: E402
from research.harness import mean_se                    # noqa: E402

HTFS = ("Hour4", "Hour8", "Day1")
NULLS = 300
ADX_LEN = ADX_SMOOTH = 14
ADX_THRESH = 20.0
ST_LEN, ST_FACTOR = 10, 1.8
EMAS = (21, 51, 100, 200)


# ------------------------------------------------------------------ indicators
def ema(vals, n):
    out, a = [None] * len(vals), 2.0 / (n + 1)
    if len(vals) < n:
        return out
    out[n - 1] = sum(vals[:n]) / n
    for i in range(n, len(vals)):
        out[i] = a * vals[i] + (1 - a) * out[i - 1]
    return out


def adx(cs, length=ADX_LEN, smooth=ADX_SMOOTH):
    """Wilder's ADX. `length` smooths DM/TR, `smooth` smooths DX into ADX —
    the two inputs the indicator panel exposes separately."""
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
    a, pd, nd = atr_rma(tr, length), atr_rma(pdm, length), atr_rma(ndm, length)
    dx = []
    for x, p_, n_ in zip(a, pd, nd):
        if x <= 0:
            dx.append(0.0)
            continue
        pi, ni = 100 * p_ / x, 100 * n_ / x
        dx.append(100 * abs(pi - ni) / (pi + ni) if (pi + ni) else 0.0)
    return atr_rma(dx, smooth)


def macd_hist(cs, fast=12, slow=26, sig=9):
    c = [x.c for x in cs]
    f, s = ema(c, fast), ema(c, slow)
    line = [(a - b) if (a is not None and b is not None) else None
            for a, b in zip(f, s)]
    solid = [x for x in line if x is not None]
    sg = ema(solid, sig)
    out, k = [None] * len(cs), 0
    for i, v in enumerate(line):
        if v is None:
            continue
        out[i] = (v - sg[k]) if sg[k] is not None else None
        k += 1
    return out


def vwap_session(cs):
    """Daily-anchored VWAP, reset at UTC midnight — the session a crypto
    chart's VWAP actually uses."""
    out, day, pv, vv = [], None, 0.0, 0.0
    for c in cs:
        d = c.t // 86400
        if d != day:
            day, pv, vv = d, 0.0, 0.0
        tp = (c.h + c.l + c.c) / 3.0
        pv += tp * c.v
        vv += c.v
        out.append(pv / vv if vv > 0 else None)
    return out


# ------------------------------------------------------------------ HTF lookup
_HTF: dict = {}


async def load_htf(sess, syms):
    for tf in HTFS:
        for sym in syms:
            try:
                cs = await fetch_candles(sess, sym, tf)
            except Exception:
                continue
            if len(cs) < 60:
                continue
            _HTF[(sym, tf)] = {
                "t": [c.t for c in cs],
                "st": supertrend(cs, ST_LEN, ST_FACTOR),
                "adx": adx(cs),
                "macd": macd_hist(cs),
                "close": [c.c for c in cs],
                **{f"ema{n}": ema([c.c for c in cs], n) for n in EMAS},
            }


def htf_at(sym, tf, key, when):
    """Value on the last HTF bar whose CLOSE is at or before `when`.

    Bar times are OPEN times, so the forming bar is excluded by arithmetic
    rather than by hoping the fetch dropped it — the same rule trend._at uses,
    and the only place lookahead could enter this study.
    """
    d = _HTF.get((sym, tf))
    if not d:
        return None
    i = bisect_right(d["t"], when - BAR_SECONDS[tf]) - 1
    if not (0 <= i < len(d[key])):
        return None
    return d[key][i]


# ------------------------------------------------------------------ features
_LOCAL: dict = {}


def local(r):
    k = id(r.candles)
    if k not in _LOCAL:
        cs = r.candles
        c = [x.c for x in cs]
        _LOCAL[k] = {
            "st": supertrend(cs, ST_LEN, ST_FACTOR),
            "adx": adx(cs),
            "macd": macd_hist(cs),
            "vwap": vwap_session(cs),
            "atr": atr_series(cs, 14),
            **{f"ema{n}": ema(c, n) for n in EMAS},
        }
    return _LOCAL[k]


def sig_time(r):
    return (getattr(r.signal, "fvg_time", 0)
            or getattr(r.signal, "mss_time", 0) or r.signal.sweep_time)


def build_features():
    """(name, fn) where fn returns True / False / None for one signal."""
    F = []

    def add(name, fn):
        F.append((name, fn))

    # --- signal timeframe
    add(f"ADX({ADX_LEN},{ADX_SMOOTH}) > {ADX_THRESH:g}  [{INTERVAL}]",
        lambda r: (lambda v: None if v is None else v > ADX_THRESH)(
            local(r)["adx"][r.bar] if r.bar < len(local(r)["adx"]) else None))
    add(f"SuperTrend({ST_LEN},{ST_FACTOR}) with  [{INTERVAL}]",
        lambda r: (lambda v: None if not v else (v > 0) == r.signal.is_long)(
            local(r)["st"][r.bar] if r.bar < len(local(r)["st"]) else None))
    add(f"MACD hist with  [{INTERVAL}]",
        lambda r: (lambda v: None if v is None else (v > 0) == r.signal.is_long)(
            local(r)["macd"][r.bar] if r.bar < len(local(r)["macd"]) else None))
    add(f"close vs VWAP with  [{INTERVAL}]",
        lambda r: (lambda v: None if v is None
                   else (r.candles[r.bar].c > v) == r.signal.is_long)(
            local(r)["vwap"][r.bar] if r.bar < len(local(r)["vwap"]) else None))
    for n in EMAS:
        add(f"close vs EMA{n} with  [{INTERVAL}]",
            lambda r, n=n: (lambda v: None if v is None
                            else (r.candles[r.bar].c > v) == r.signal.is_long)(
                local(r)[f"ema{n}"][r.bar]
                if r.bar < len(local(r)[f"ema{n}"]) else None))

    # --- higher timeframes
    for tf in HTFS:
        add(f"ADX({ADX_LEN},{ADX_SMOOTH}) > {ADX_THRESH:g}  [{tf}]",
            lambda r, tf=tf: (lambda v: None if v is None
                              else v > ADX_THRESH)(
                htf_at(r.symbol, tf, "adx", sig_time(r))))
        add(f"SuperTrend({ST_LEN},{ST_FACTOR}) with  [{tf}]",
            lambda r, tf=tf: (lambda v: None if not v
                              else (v > 0) == r.signal.is_long)(
                htf_at(r.symbol, tf, "st", sig_time(r))))
        add(f"MACD hist with  [{tf}]",
            lambda r, tf=tf: (lambda v: None if v is None
                              else (v > 0) == r.signal.is_long)(
                htf_at(r.symbol, tf, "macd", sig_time(r))))
        for n in EMAS:
            def f(r, tf=tf, n=n):
                e = htf_at(r.symbol, tf, f"ema{n}", sig_time(r))
                c = htf_at(r.symbol, tf, "close", sig_time(r))
                if e is None or c is None:
                    return None
                return (c > e) == r.signal.is_long
            add(f"close vs EMA{n} with  [{tf}]", f)

    # --- geometry, signal timeframe only
    def fib(r):
        """Where the entry sits between the raid extreme and the swept level.

        0 = at the raid extreme, 1 = back at the pool that was taken. The
        classic retracement question, using only fields the engine records.
        Split at 0.5 — deeper than half the leg, or shallower.
        """
        lv, e, st = getattr(r.signal, "level", 0.0), r.signal.entry, r.signal.stop
        span = lv - st
        if not span:
            return None
        return abs((e - st) / span) > 0.5

    add(f"entry past 50% of the raid leg  [{INTERVAL}]", fib)

    def exhaust(r):
        """Momentum exhaustion: three or more consecutive bars pushing INTO
        the raid immediately before it. A long comes off a swept low, so the
        exhausted case is a run of down bars."""
        cs = r.candles
        idx = {c.t: i for i, c in enumerate(cs)}
        g = idx.get(getattr(r.signal, "grab_time", 0) or r.signal.sweep_time)
        if g is None or g < 4:
            return None
        n = 0
        for k in range(g, max(g - 6, 0), -1):
            down = cs[k].c < cs[k].o
            if down == r.signal.is_long:      # into the raid
                n += 1
            else:
                break
        return n >= 3

    add(f"3+ bars into the raid  [{INTERVAL}]", exhaust)
    return F


# ------------------------------------------------------------------ scoring
def split_se(rows, fn):
    hit = [r.r for r in rows if fn(r) is True]
    miss = [r.r for r in rows if fn(r) is False]
    if len(hit) < 40 or len(miss) < 40:
        return None
    a, sa = mean_se(hit)
    b, sb = mean_se(miss)
    d, dse = a - b, (sa ** 2 + sb ** 2) ** 0.5
    return d, dse, (d / dse if dse else 0.0), len(hit), len(hit) / len(rows)


def null_distribution(rows, keep_rates, seeds=NULLS):
    """|SE| of random features with the same keep-rates, on this exact data.

    The instrument the whole study rests on. A z-table assumes independent
    draws; 33% of these signals arrive with eight or more others on the same
    bar close, so they are not independent and the nominal SE overstates what
    is known. This measures what the machinery produces from nothing.
    """
    out = []
    for s in range(seeds):
        rnd = random.Random(6000 + s)
        p = keep_rates[s % len(keep_rates)]
        f = {id(r): (rnd.random() < p) for r in rows}
        got = split_se(rows, lambda r: f[id(r)])
        if got:
            out.append(abs(got[2]))
    return sorted(out)


def main():
    async def go():
        async with aiohttp.ClientSession() as sess:
            syms = await list_symbols(sess)
            await load_htf(sess, syms)
            return syms
    syms = asyncio.run(go())
    every = load_sync(symbols=syms)
    rows = [r for r in every if r.kind == "early"]
    held = [r for r in rows if r.split_window]
    F = build_features()
    print(f"THIRTY-ONE FEATURES, WITH AN EMPIRICAL NULL\n"
          f"{len(rows)} early signals · {len(F)} features · {NULLS} random "
          f"controls\nsignal timeframe {INTERVAL} · higher timeframes "
          f"{', '.join(HTFS)}")

    res = []
    for name, fn in F:
        got = split_se(rows, fn)
        if not got:
            print(f"  SKIP (too few either side): {name}")
            continue
        h = split_se(held, fn)
        res.append((name, got, h))

    rates = [g[4] for _, g, _ in res] or [0.5]
    null = null_distribution(rows, rates)
    p95 = null[int(0.95 * (len(null) - 1))] if null else float("inf")
    p99 = null[int(0.99 * (len(null) - 1))] if null else float("inf")

    print(f"\nTHE NULL — |SE| from {len(null)} random features on this same "
          f"data:")
    print(f"  median {null[len(null) // 2]:.2f}   p90 "
          f"{null[int(.9 * (len(null) - 1))]:.2f}   p95 {p95:.2f}   "
          f"p99 {p99:.2f}   max {null[-1]:.2f}")
    print(f"  {sum(1 for x in null if x >= 2.0) / len(null):.0%} of PURE NOISE "
          f"features clear 2 SE. That is why 2 SE is not the bar here.")

    print(f"\n  {'feature':<40}{'kept':>7}{'diff':>9}{'SE':>7}{'held out':>11}"
          f"{'':>4}")
    for name, g, h in sorted(res, key=lambda x: -abs(x[1][2])):
        mark = ("  <-- beats null p95" if abs(g[2]) >= p95 else "")
        hs = f"{h[2]:+.1f} SE" if h else "too few"
        # A survivor must also keep its sign on the held-out half.
        if mark and h and (h[0] > 0) != (g[0] > 0):
            mark = "  (p95 but SIGN FLIPS held out)"
        print(f"  {name:<40}{g[4]:>6.0%}{g[0]:>+9.3f}{g[2]:>+7.1f}{hs:>11}"
              f"{mark}")

    print(f"\nPRE-REGISTERED: clear the null's p95 ({p95:.2f} SE) on the full "
          f"panel AND\nhold the sign on the held-out half. Both.")


if __name__ == "__main__":
    main()
