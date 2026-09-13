"""Re-measure every entry-side idea from batches 1-4 on the corrected scorer.

    PYTHONPATH=. python3 research/studies/features.py
"""
import research.env                                     # noqa: F401  MUST be first
import asyncio, statistics                              # noqa: E402

from riptide.config import CFG                          # noqa: E402
from riptide.engine import last_opposing                # noqa: E402
from research.data import load, atr_at                  # noqa: E402
from research.harness import report, risk_terciles      # noqa: E402


def ema(v, n):
    k, out, e = 2 / (n + 1), [], None
    for x in v:
        e = x if e is None else x * k + e * (1 - k)
        out.append(e)
    return out


_CACHE = {}


def series(row):
    key = id(row.candles)
    if key not in _CACHE:
        cs = row.candles
        cl = [c.c for c in cs]
        f, s = ema(cl, 12), ema(cl, 26)
        line = [a - b for a, b in zip(f, s)]
        sig = ema(line, 9)
        hist = [a - b for a, b in zip(line, sig)]
        st, cc, bb = [], [], []
        tp = [(c.h + c.l + c.c) / 3 for c in cs]
        for i in range(len(cs)):
            w = cs[max(0, i - 13):i + 1]
            hi, lo = max(c.h for c in w), min(c.l for c in w)
            st.append(50.0 if hi == lo else 100 * (cs[i].c - lo) / (hi - lo))
            wt = tp[max(0, i - 19):i + 1]
            m = statistics.fmean(wt)
            d = statistics.fmean([abs(x - m) for x in wt]) or 1e-12
            cc.append((tp[i] - m) / (0.015 * d))
            wc = cl[max(0, i - 19):i + 1]
            mu = statistics.fmean(wc)
            sd = statistics.pstdev(wc) if len(wc) > 1 else 0.0
            bb.append((mu - 2 * sd, mu + 2 * sd))
        _CACHE[key] = (hist, st, cc, bb)
    return _CACHE[key]


def L(row):
    return 1 if row.signal.is_long else -1


def grab_bar(row):
    idx = {c.t: i for i, c in enumerate(row.candles)}
    t = getattr(row.signal, "grab_time", 0) or row.signal.sweep_time
    return idx.get(t, row.bar)


# ---- features -------------------------------------------------------------
def f_macd_sign(r):  return (series(r)[0][r.bar] > 0) == (L(r) > 0)
def f_macd_slope(r): return (series(r)[0][r.bar] - series(r)[0][r.bar - 1] > 0) == (L(r) > 0)
def f_stoch(r):      return (50 - series(r)[1][r.bar]) * L(r)
def f_cci(r):        return -series(r)[2][r.bar] * L(r)
def f_boll(r):
    g = grab_bar(r); lo, hi = series(r)[3][g]
    return (r.candles[g].l < lo) if r.signal.is_long else (r.candles[g].h > hi)
def f_wick(r):
    c = r.candles[grab_bar(r)]; rng = max(c.h - c.l, 1e-12)
    return ((min(c.o, c.c) - c.l) if r.signal.is_long else (c.h - max(c.o, c.c))) / rng
def f_body(r):
    c = r.candles[grab_bar(r)]
    return abs(c.c - c.o) / max(c.h - c.l, 1e-12)
def f_range(r):
    g = grab_bar(r)
    if g < 24: return None
    pre = r.candles[g - 24:g]
    return (max(c.h for c in pre) - min(c.l for c in pre)) / (atr_at(r) or 1e-12)
def f_age(r):
    return (r.candles[r.bar].t - r.signal.anchor_time) / 3600
def f_hour(r):
    return (r.candles[r.bar].t // 3600) % 24
def f_gap(r):
    return L(r) * (r.candles[r.bar].c - r.signal.entry) / abs(r.signal.entry - r.signal.stop)
def f_displace(r):
    g = grab_bar(r)
    leg = r.candles[g:r.bar + 1]
    if not leg: return None
    return (max(c.h for c in leg) - min(c.l for c in leg)) / (atr_at(r) or 1e-12)
def f_gapshare(r):
    b = r.bar
    if b < 2: return None
    g = (r.candles[b].l - r.candles[b - 2].h) if r.signal.is_long \
        else (r.candles[b - 2].l - r.candles[b].h)
    d = f_displace(r)
    return g / (d * atr_at(r)) if d else None
def f_voids(r):
    g, n = grab_bar(r), 0
    for j in range(max(g + 2, 2), r.bar + 1):
        if r.candles[j].l > r.candles[j - 2].h or r.candles[j].h < r.candles[j - 2].l:
            n += 1
    return n
def f_pivots(r):    return r.signal.pivots
def f_day_pool(r):  return r.signal.src == "Day"
def f_conf(r):      return getattr(r.signal, "confluence", 0)
def f_riskpct(r):   return r.risk_pct


FEATURES = [
    ("MACD histogram sign agrees", f_macd_sign),
    ("MACD histogram slope agrees", f_macd_slope),
    ("Stochastic extension our way", f_stoch),
    ("CCI extension our way", f_cci),
    ("raid extreme outside Bollinger", f_boll),
    ("rejection wick / range", f_wick),
    ("raid body / range", f_body),
    ("range width before the raid (ATR)", f_range),
    ("pool age (hours)", f_age),
    ("hour of day (UTC)", f_hour),
    ("price past entry at signal (R)", f_gap),
    ("displacement (ATR)", f_displace),
    ("gap share of the leg", f_gapshare),
    ("imbalances in the leg", f_voids),
    ("swings in the pool", f_pivots),
    ("Day pool (vs Pivot)", f_day_pool),
    ("confluence score", f_conf),
    ("stop size (% risk)", f_riskpct),
]


async def main():
    rows = await load()
    print(f"{len(rows)} signals "
          f"({sum(1 for r in rows if r.filled)} filled), "
          f"scorer: research/harness.py")
    for kind in ("confirmed", "early"):
        sub = [r for r in rows if r.kind == kind]
        print(f"\n{'='*70}\n{kind.upper()}  n={len(sub)}\n{'='*70}")
        for name, fn in FEATURES:
            try:
                report(name, sub, fn, control=risk_terciles)
            except Exception as e:
                print(f"\n{name}\n  skipped: {e}")

asyncio.run(main())
