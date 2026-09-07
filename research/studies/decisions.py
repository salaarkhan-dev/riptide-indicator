"""Re-measure every decision that was SHIPPED, plus the exit policies.

    PYTHONPATH=. python3 research/studies/decisions.py
"""
import research.env                                     # noqa: F401  MUST be first
import asyncio, statistics                              # noqa: E402
from bisect import bisect_right                         # noqa: E402

import aiohttp                                          # noqa: E402
from riptide.config import BAR_SECONDS, Cfg             # noqa: E402
from riptide.exchange import fetch_candles              # noqa: E402
from riptide.trend import di_direction, supertrend      # noqa: E402
from research.data import load, SYMBOLS                 # noqa: E402
from research.harness import mean_se                    # noqa: E402


def line(lab, v, base=None):
    m, se = mean_se(v)
    out = f"  {lab:<32}{len(v):>6}{m:>+9.3f}{se:>7.3f}{sum(v):>+9.1f}"
    if base is not None and len(v) == len(base):
        pair = [a - b for a, b in zip(v, base)]
        d, sd = mean_se(pair)
        out += f"{d:>+9.3f}" + (f"  {d/sd:+.1f}SE" if sd else "")
    print(out)
    return v


HDR = f"  {'':<32}{'n':>6}{'R/sig':>9}{'SE':>7}{'total':>9}{'vs base':>9}"


async def main():
    # ---------- 1. risk cap, shipped as 2.5 on confirmed ----------
    print("1. RISK CAP on confirmed setups   (shipped 2.5 ATR)")
    print(HDR)
    for cap in (1.5, 2.0, 2.5, 3.0, 4.0):
        rows = await load(cfg=Cfg(max_risk_atr=cap))
        line(f"{cap:g} ATR" + ("   <- shipped" if cap == 2.5 else ""),
             [r.r for r in rows if r.kind == "confirmed"])

    # ---------- 2. exits ----------
    base_rows = await load()
    conf = [r for r in base_rows if r.kind == "confirmed"]
    early = [r for r in base_rows if r.kind == "early"]
    print(f"\n2. EXITS   ({len(conf)} confirmed, {len(early)} early)")
    for kind in ("confirmed", "early"):
        print(f"\n  -- {kind} --")
        print(HDR)
        base = None
        for t in (1.0, 1.5, 2.0, 2.5, 3.0):
            rows = await load(target_r=t)
            v = [r.r for r in rows if r.kind == kind]
            if t == 1.5:
                base = v
            line(f"target {t:g}R" + ("   (baseline)" if t == 1.5 else ""), v,
                 base if t != 1.5 else None)
        for arm, lock in ((1.0, 0.1), (1.5, 0.1), (2.0, 0.1)):
            rows = await load(target_r=1.5, be_arm_r=arm, be_lock_r=lock)
            line(f"BE arm {arm:g}R lock {lock:g}R"
                 + ("   <- shipped advice" if arm == 1.5 else ""),
                 [r.r for r in rows if r.kind == kind], base)
        for at, to in ((1.5, 3.0), (1.0, 3.0)):
            rows = await load(target_r=3.0, part_at_r=at, part_to_r=to,
                              be_lock_r=0.1)
            line(f"half {at:g}R, half {to:g}R, BE",
                 [r.r for r in rows if r.kind == kind], base)
        for h in (20, 40, 60):
            rows = await load(target_r=1.5, horizon_bars=h)
            line(f"horizon {h} bars" + ("   (baseline)" if h == 60 else ""),
                 [r.r for r in rows if r.kind == kind], base)

    # ---------- 3. trend timeframe, shipped 4h ST + daily DI ----------
    print("\n3. TREND TIMEFRAME   (shipped: SuperTrend 4h, DI daily)")
    tf = {}
    async with aiohttp.ClientSession() as s:
        for sym in SYMBOLS:
            for name in ("Hour4", "Day1"):
                try:
                    cs = await fetch_candles(s, sym, name)
                except Exception:
                    continue
                if len(cs) > 40:
                    tf[(sym, name)] = ([c.t for c in cs], supertrend(cs),
                                       di_direction(cs))
    print(f"  {'reading':<24}{'with':>9}{'against':>10}{'sep':>9}{'SE':>7}")
    for name, which, lab in (("Hour4", 1, "4h SuperTrend"),
                             ("Day1", 1, "daily SuperTrend"),
                             ("Hour4", 2, "4h DI"), ("Day1", 2, "daily DI")):
        step = BAR_SECONDS[name]
        w, a = [], []
        for r in conf:
            got = tf.get((r.symbol, name))
            if not got:
                continue
            times, sv, dv = got
            arr = sv if which == 1 else dv
            j = bisect_right(times, r.candles[r.bar].t - step) - 1
            d = arr[j] if 0 <= j < len(arr) else 0
            if not d:
                continue
            (w if (d > 0) == r.signal.is_long else a).append(r.r)
        if len(w) < 20 or len(a) < 20:
            continue
        m1, s1 = mean_se(w)
        m0, s0 = mean_se(a)
        sep, sd = m1 - m0, (s0 ** 2 + s1 ** 2) ** 0.5
        print(f"  {lab:<24}{m1:>+9.3f}{m0:>+10.3f}{sep:>+9.3f}{sd:>7.3f}"
              + (f"  {sep/sd:+.1f} SE" if sd else ""))

    # ---------- 4. structure timeframe ----------
    print("\n4. STRUCTURE TIMEFRAME")
    print(HDR)
    for iv in ("Min15", "Min30"):
        rows = await load(interval=iv)
        for kind in ("confirmed", "early"):
            line(f"{iv} {kind}", [r.r for r in rows if r.kind == kind])

asyncio.run(main())
