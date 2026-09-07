"""Model 1 as a genuine multi-timeframe model, across a grid of pairs.

WHAT MAKES THIS DIFFERENT FROM WHAT WAS ALREADY REJECTED
--------------------------------------------------------
research/studies/sniper.py tested riptide/mtf.py, which takes the FIRST GAP on
a faster chart after the 30m shift and puts the stop on that gap's structure.
It lost 0.525 R per setup because a Min15 stop sits inside Min30 noise.

The model described here is not that. The lower timeframe forms its OWN
complete setup — its own liquidity sweep, its own change of character, its own
gap — and the stop goes beyond the LOWER timeframe's raid extreme. That is a
real invalidation level on its own chart, not an arbitrary nearby structure.
Every stop this project has refuted so far (gap far edge, 5-bar swing, first
LTF gap, constant-risk) shared one property: none of them sat beyond a
liquidity raid. This one does. So the prior is bad but the construction is
untested, and it deserves its own measurement rather than an argument.

THE FIVE STRICT STEPS, AND WHERE EACH LIVES
-------------------------------------------
  1 HTF narrative     supertrend + DI on the HTF, must agree with the trade
  2 HTF POI           the LTF raid must land inside an aligned HTF order block
                      or fair value gap, formed recently
  3 patience          implicit: the raid IS the tap. Nothing fires until then.
  4 LTF shift         run_engine on the LTF gives sweep -> MSS -> gap, which is
                      exactly sweep -> CHOCH -> entry
  5 execution         the engine's entry, at the LTF gap edge, LTF stop

Reported as an ABLATION so each step is priced separately: the LTF alone, then
+POI, then +narrative, then both. A model that only works with all four filters
on and 30 signals left has not been shown to work.

DATA
----
2000 bars is 41 days of Min30 but only 6.9 days of Min5 and 33 hours of Min1,
so the faster charts are paged backwards to get a comparable window. Min1 is
still hopeless and is excluded; 5m gets ~28 days.

Windows are matched in WALL CLOCK, not bars: the shipped 10-bar fill window and
60-bar horizon on Min30 are 5 and 30 hours, so on Min5 they are 60 and 360.
"""
from __future__ import annotations

import research.env  # noqa: F401  (must precede riptide.config)

import asyncio
import statistics
import time

import aiohttp

from riptide.config import CFG, BAR_SECONDS
from riptide.engine import Candle, atr_series, run_engine
from riptide.exchange import BASE, get_json
from riptide.trend import supertrend, di_direction
from research.data import SYMBOLS
from research.harness import simulate, mean_se

FEE = dict(fee_maker=0.02, fee_taker=0.06)
FILL_HOURS, HORIZON_HOURS = 5, 30
ZONE_MAX_AGE_BARS = 30            # a POI older than this is not the POI
PAIRS = (("Day1", "Min30"), ("Hour4", "Min30"), ("Hour4", "Min15"),
         ("Hour4", "Min5"), ("Min60", "Min5"), ("Min60", "Min15"), ("Day1", "Min15"))
SYMS = SYMBOLS[:14]               # the grid is 6 pairs x 4 arms; keep it finite


# ------------------------------------------------------------------- fetching

async def fetch_paged(sess, symbol, interval, pages=1):
    """Candles, oldest first, paged backwards. One request caps at 2000 bars,
    which is 6.9 days of Min5 — not enough window to say anything."""
    step = BAR_SECONDS[interval]
    end = int(time.time())
    out: dict[int, Candle] = {}
    for _ in range(pages):
        start = end - 2000 * step
        d = await get_json(sess, f"{BASE}/api/v1/contract/kline/{symbol}",
                           {"interval": interval, "start": start, "end": end})
        k = (d or {}).get("data") or {}
        if not k.get("time"):
            break
        vol = k.get("vol") or [0] * len(k["time"])
        now = int(time.time())
        for t, o, h, l, c, v in zip(k["time"], k["open"], k["high"], k["low"],
                                    k["close"], vol):
            if int(t) + step <= now:
                out[int(t)] = Candle(int(t), float(o), float(h), float(l),
                                     float(c), float(v))
        end = min(k["time"]) - step
    return [out[t] for t in sorted(out)]


# ----------------------------------------------------------------- HTF pieces

def zones_of(cs, atr):
    """(formed_at, is_bull, lo, hi) for 4h/1h/daily order blocks and gaps."""
    out = []
    for j in range(2, len(cs)):
        a = atr[j] if j < len(atr) else 0.0
        if a <= 0:
            continue
        if cs[j].l > cs[j - 2].h:
            out.append((cs[j].t, True, cs[j - 2].h, cs[j].l))
        elif cs[j].h < cs[j - 2].l:
            out.append((cs[j].t, False, cs[j].h, cs[j - 2].l))
        if cs[j].c - cs[j].o > a and cs[j - 1].c < cs[j - 1].o:
            out.append((cs[j].t, True, cs[j - 1].l, cs[j - 1].h))
        elif cs[j].o - cs[j].c > a and cs[j - 1].c > cs[j - 1].o:
            out.append((cs[j].t, False, cs[j - 1].l, cs[j - 1].h))
    return out


def in_poi(zones, when, price, is_long, step):
    for t, bull, lo, hi in zones:
        if (t <= when and bull == is_long and lo <= price <= hi
                and when - t <= ZONE_MAX_AGE_BARS * step):
            return True
    return False


def htf_dir_at(cs, st, di, when):
    """HTF narrative on the last CLOSED higher-timeframe bar at `when`.
    Bisect on bar-open times, then step back one: a bar whose open is at or
    before `when` may still be forming, and using it would look ahead."""
    lo, hi = 0, len(cs) - 1
    if not cs or when < cs[0].t:
        return 0
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if cs[mid].t <= when:
            lo = mid
        else:
            hi = mid - 1
    i = lo - 1
    if i < 0:
        return 0
    return st[i] if st[i] == di[i] else 0


# --------------------------------------------------------------------- scoring

def arm(sigs, ltf, need_poi, need_dir, zones, hcs, hst, hdi, hstep, fill, hor):
    outs, risks = [], []
    for x, i in sigs:
        if need_poi and not in_poi(zones, ltf[i].t, x.stop, x.is_long, hstep):
            continue
        if need_dir:
            d = htf_dir_at(hcs, hst, hdi, ltf[i].t)
            if d != (1 if x.is_long else -1):
                continue
        outs.append(simulate(ltf, i, x.entry, x.stop, x.is_long,
                             fill_bars=fill, horizon_bars=hor, **FEE))
        risks.append(100 * abs(x.entry - x.stop) / x.entry)
    return outs, risks


def show(lab, outs, risks):
    if len(outs) < 25:
        print(f"  {lab:<28} n={len(outs):<5} too few")
        return
    rs = [o.r for o in outs]
    fill = sum(o.filled for o in outs) / len(outs)
    won = [o for o in outs if o.filled]
    win = sum(o.r > 0 for o in won) / len(won) if won else 0.0
    m, se = mean_se(rs)
    print(f"  {lab:<28} n={len(outs):<5} fill {fill:5.1%}  win {win:5.1%}"
          f"  risk {statistics.fmean(risks):4.2f}%  {m:+.3f} ± {se:.3f}"
          f"  tot {sum(rs):+7.1f}")


async def run_pair(sess, htf_name, ltf_name):
    step_l, step_h = BAR_SECONDS[ltf_name], BAR_SECONDS[htf_name]
    fill = max(1, FILL_HOURS * 3600 // step_l)
    hor = max(1, HORIZON_HOURS * 3600 // step_l)
    pages = max(1, min(6, (41 * 86400) // (2000 * step_l)))
    print(f"\n{'=' * 96}\nHTF {htf_name}  ->  LTF {ltf_name}    "
          f"(fill {fill} bars = {FILL_HOURS}h, horizon {hor} bars = "
          f"{HORIZON_HOURS}h, {pages} page(s))\n{'=' * 96}")

    acc = {k: ([], []) for k in ("ltf", "poi", "dir", "both")}
    acc_e = {k: ([], []) for k in ("ltf", "poi", "dir", "both")}
    days = []
    for sym in SYMS:
        try:
            ltf = await fetch_paged(sess, sym, ltf_name, pages)
            hcs = await fetch_paged(sess, sym, htf_name, 1)
        except Exception:
            continue
        if len(ltf) < 300 or len(hcs) < 60:
            continue
        days.append((ltf[-1].t - ltf[0].t) / 86400)
        zones = zones_of(hcs, atr_series(hcs, CFG.atr_len))
        hst, hdi = supertrend(hcs), di_direction(hcs)
        early: list = []
        setups = run_engine(sym, ltf, CFG, early_out=early)
        idx = {c.t: i for i, c in enumerate(ltf)}
        for sigs, store in (([(s, idx.get(s.detected_time)) for s in setups], acc),
                            ([(e, idx.get(e.detected_time)) for e in early], acc_e)):
            sigs = [(x, i) for x, i in sigs if i is not None]
            for key, (p, d) in (("ltf", (0, 0)), ("poi", (1, 0)),
                                ("dir", (0, 1)), ("both", (1, 1))):
                o, r = arm(sigs, ltf, p, d, zones, hcs, hst, hdi, step_h,
                           fill, hor)
                store[key][0].extend(o)
                store[key][1].extend(r)

    if days:
        print(f"  window: {statistics.median(days):.0f} days of {ltf_name} "
              f"across {len(days)} symbols")
    for lab, store in (("CONFIRMED", acc), ("EARLY", acc_e)):
        print(f"  -- {lab} --")
        for key, name in (("ltf", "LTF setup alone"),
                          ("poi", "+ step 2: HTF POI"),
                          ("dir", "+ step 1: HTF narrative"),
                          ("both", "+ both (the full model)")):
            show(name, *store[key])


async def main():
    async with aiohttp.ClientSession() as sess:
        for htf, ltf in PAIRS:
            await run_pair(sess, htf, ltf)


if __name__ == "__main__":
    asyncio.run(main())
