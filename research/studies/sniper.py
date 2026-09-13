"""The "sniper entry" SMC blueprint, claim by claim.

The blueprint as usually written has five steps. Three of them are already
answered by measurements in this repo, and re-running them would only add
comparisons to the multiple-testing bill, so they are stated here and skipped:

  HTF BIAS            measured. Daily DI separates +0.204 with / -0.062
                      against, 2.5 SE; it beat 4h SuperTrend and 4h DI and is
                      what ships. See "Trend timeframe".
  LTF CONFIRMATION    measured, and it is the largest effect in the project.
                      Waiting for the structure shift IS the confirmed signal:
                      +0.250 R against +0.020 for the early, no-shift version.
                      The blueprint's central claim is already validated.
  TIGHT STOP AT THE   refuted, decisively. See "Why chasing the entry fails".
  INVALIDATION WICK   A stop at the gap's far edge is 0.54% risk against 1.83%
                      and wins 40.1% against 50.0%, for -0.057 R against
                      +0.250. Every stop nearer than the raid extreme tested
                      worse, including a real 5-bar swing low.
  1:3 MINIMUM RR      measured. The target ladder is monotone but each rung is
                      ~1.5 SE: 2R +0.215, 2.5R +0.242, 3R +0.252. 3R is not
                      distinguishable from the shipped 2R.

That leaves three claims that have NOT been tested, and they are the
interesting ones because each adds structure rather than re-filtering price:

  A  HTF ZONE      the sweep should happen inside a higher-timeframe order
                   block or fair value gap, not just anywhere. Our pools come
                   from 30m pivots and day levels; whether the raid lands in a
                   4h zone has never been asked.

  B  LTF REFINED   drop to a faster chart and take the first gap there, with
     ENTRY         the stop on ITS structure. riptide/mtf.py implements this
                   and it is OFF. Its docstring justifies it with "85% of
                   setups filled, 51% of fills reached 1R" — numbers from
                   before the scorer was fixed, measured from the signal bar
                   rather than the fill. They cannot be trusted and this has
                   never been re-run.

  C  STRUCTURAL    exit at the opposing liquidity pool rather than at a fixed
     TARGET        multiple of risk. A real ICT target is a price level, not
                   an R number, and every exit test so far has used fixed R.

Time windows are matched across timeframes rather than bar counts: the shipped
10-bar fill window and 60-bar horizon on 30m are 5 and 30 hours, so on Min5
they become 60 and 360 bars. Comparing 10 bars of Min5 against 10 bars of
Min30 would answer a different question on each chart.
"""
from __future__ import annotations

import research.env  # noqa: F401  (must precede riptide.config)

import asyncio
import statistics

import aiohttp

from riptide.config import CFG, BAR_SECONDS, INTERVAL
from riptide.engine import Candle, atr_series, is_pivot_high, is_pivot_low
from riptide.exchange import fetch_candles
from research.data import load_sync, SYMBOLS, atr_at
from research.harness import (simulate, mean_se, report, risk_terciles,
                              TRACK_FILL_BARS, TRACK_HORIZON_BARS)

FEE = dict(fee_maker=0.02, fee_taker=0.06)
HTF = "Hour4"
LTFS = ("Min15", "Min5")


# --------------------------------------------------------------- A: HTF zones

def htf_zones(cs: list[Candle], atr: list[float]) -> list[tuple]:
    """(start_time, is_bull, lo, hi) for every 4h fair value gap and order
    block. A zone is only usable from the bar it completes on, so start_time
    is that bar's open — using the gap's first bar would let a signal see a
    zone that had not formed yet."""
    out = []
    for j in range(2, len(cs)):
        a = atr[j] if j < len(atr) else 0.0
        if a <= 0:
            continue
        # Fair value gap, both directions.
        if cs[j].l > cs[j - 2].h:
            out.append((cs[j].t, True, cs[j - 2].h, cs[j].l))
        elif cs[j].h < cs[j - 2].l:
            out.append((cs[j].t, False, cs[j].h, cs[j - 2].l))
        # Order block: the last opposite-closing candle before a displacement
        # bar. Bullish OB = a down candle followed by an up bar that travels
        # more than an ATR.
        if cs[j].c - cs[j].o > a and cs[j - 1].c < cs[j - 1].o:
            out.append((cs[j].t, True, cs[j - 1].l, cs[j - 1].h))
        elif cs[j].o - cs[j].c > a and cs[j - 1].c > cs[j - 1].o:
            out.append((cs[j].t, False, cs[j - 1].l, cs[j - 1].h))
    return out


def in_htf_zone(zones, when: int, price: float, is_long: bool,
                cs=None, max_age: int = 0, fresh: bool = False) -> bool:
    """Did the raid land inside an aligned 4h zone that already existed?

    The naive version of this — every zone ever formed, valid forever — flags
    90% of raids and therefore tests nothing. 333 days of 4h bars accumulate
    thousands of gaps and blocks that between them cover most of the price
    range. Two standard ICT conditions make it a real test:

      max_age  a zone more than N 4h bars old is not what anyone means by
               "the higher-timeframe zone price is reacting to".
      fresh    a zone is spent once price has mitigated it. If price already
               traded into the range after it formed, this raid is not the
               reaction to it.
    """
    for t, bull, lo, hi in zones:
        if t > when or bull != is_long or not (lo <= price <= hi):
            continue
        if max_age and cs is not None:
            if when - t > max_age * BAR_SECONDS[HTF]:
                continue
        if fresh and cs is not None:
            # Untouched between forming and now? The raid itself is the
            # first mitigation, which is the whole premise.
            if any(c.l <= hi and c.h >= lo
                   for c in cs if t < c.t < when):
                continue
        return True
    return False


# (label, max_age in 4h bars, must be unmitigated)
ZONE_RULES = (("any 4h zone, ever", 0, False),
              ("formed in last 30 bars (5d)", 30, False),
              ("last 30 bars AND unmitigated", 30, True),
              ("last 10 bars AND unmitigated", 10, True))


async def add_htf(rows):
    """Attach the HTF-zone flags to every row. One extra fetch per symbol."""
    by = {}
    async with aiohttp.ClientSession() as sess:
        for sym in sorted({r.symbol for r in rows}):
            try:
                cs = await fetch_candles(sess, sym, HTF)
            except Exception:
                cs = []
            by[sym] = (cs, htf_zones(cs, atr_series(cs, CFG.atr_len))
                       if len(cs) > 50 else [])
    hits = {lab: 0 for lab, _, _ in ZONE_RULES}
    for r in rows:
        cs, zones = by.get(r.symbol, ([], []))
        r.htf = {}
        if not zones:
            for lab, _, _ in ZONE_RULES:
                r.htf[lab] = None
            continue
        x = r.signal
        # The raid extreme is the price that took the liquidity — that is what
        # the blueprint says must sit in the HTF zone, not the entry.
        raid = getattr(x, "grab_time", 0) or x.sweep_time
        px = x.stop  # stop sits just beyond the raid extreme; close enough
        for lab, age, fresh in ZONE_RULES:
            v = in_htf_zone(zones, raid, px, x.is_long, cs, age, fresh)
            r.htf[lab] = v
            hits[lab] += v
    for lab, _, _ in ZONE_RULES:
        print(f"  {lab:<32} {hits[lab]:>5} of {len(rows)}"
              f"  ({hits[lab] / len(rows):.0%})")
    return rows


# ------------------------------------------------------- C: structural target

def opposing_pool(row, left: int = 3, right: int = 3, max_back: int = 200):
    """Nearest opposing liquidity above (long) or below (short) the entry:
    the closest confirmed pivot the trade would be running at. Returns the
    implied R multiple, or None when there is nothing to aim at."""
    cs, x = row.candles, row.signal
    risk = abs(x.entry - x.stop)
    if risk <= 0:
        return None
    lo = max(right, row.bar - max_back)
    best = None
    for i in range(lo, row.bar - right):
        if x.is_long and is_pivot_high(cs, i, left, right):
            if cs[i].h > x.entry and (best is None or cs[i].h < best):
                best = cs[i].h
        elif not x.is_long and is_pivot_low(cs, i, left, right):
            if cs[i].l < x.entry and (best is None or cs[i].l > best):
                best = cs[i].l
    if best is None:
        return None
    return abs(best - x.entry) / risk


def structural_target(rows, kind):
    sub = [r for r in rows if r.kind == kind]
    got = [(r, opposing_pool(r)) for r in sub]
    have = [(r, t) for r, t in got if t is not None]
    print(f"\n{kind.upper()}: exit at the opposing pool  "
          f"({len(have)} of {len(sub)} have one)")
    if len(have) < 40:
        print("  too few")
        return
    ts = [t for _, t in have]
    print(f"  implied R at the pool: median {statistics.median(ts):.2f}  "
          f"quartiles {statistics.quantiles(ts, n=4)[0]:.2f} / "
          f"{statistics.quantiles(ts, n=4)[2]:.2f}   "
          f"below 1R: {sum(t < 1 for t in ts) / len(ts):.0%}")

    def score(fn):
        rs = []
        for r, t in have:
            tr = fn(t)
            o = simulate(r.candles, r.bar, r.signal.entry, r.signal.stop,
                         r.signal.is_long, target_r=tr, **FEE)
            rs.append(o.r)
        return rs

    for lab, fn in (("fixed 2R  <- shipped", lambda t: 2.0),
                    ("at the pool", lambda t: t),
                    ("pool, floored at 1.5R", lambda t: max(t, 1.5)),
                    ("pool, capped at 3R", lambda t: min(t, 3.0)),
                    ("pool, 1.5R-3R band", lambda t: min(max(t, 1.5), 3.0))):
        rs = score(fn)
        m, se = mean_se(rs)
        print(f"  {lab:<24} {m:+.3f} ± {se:.3f}   tot {sum(rs):+7.1f}")


# ---------------------------------------------------------- B: LTF refinement

async def ltf_refine(rows, ltf_name):
    """Take the first gap on the faster chart after the 30m shift, with the
    stop on the faster chart's own structure — mtf.refine's idea, scored
    through the fixed harness on matched wall-clock windows."""
    from riptide import mtf

    step_h, step_l = BAR_SECONDS[INTERVAL], BAR_SECONDS[ltf_name]
    scale = step_h // step_l
    fill_bars = TRACK_FILL_BARS * scale
    horizon = TRACK_HORIZON_BARS * scale

    sub = [r for r in rows if r.kind == "confirmed"]
    cache = {}
    async with aiohttp.ClientSession() as sess:
        for sym in sorted({r.symbol for r in sub}):
            try:
                cache[sym] = await fetch_candles(sess, sym, ltf_name)
            except Exception:
                cache[sym] = []

    base, alt, skipped = [], [], 0
    for r in sub:
        ltf = cache.get(r.symbol) or []
        x = r.signal
        # Only signals the faster chart actually covers can be compared. The
        # rest are dropped from BOTH arms, never just the refined one.
        if not ltf or getattr(x, "mss_time", 0) < ltf[0].t:
            skipped += 1
            continue
        a = atr_at(r)
        ref = mtf.refine(x, ltf, a) if a > 0 else None
        if ref is None:
            skipped += 1
            continue
        idx = {c.t: i for i, c in enumerate(ltf)}
        i = idx.get(getattr(ref, "fvg_time", 0))
        if i is None:
            skipped += 1
            continue
        base.append(simulate(r.candles, r.bar, x.entry, x.stop, x.is_long,
                             **FEE))
        alt.append(simulate(ltf, i, ref.entry, ref.stop, ref.is_long,
                            fill_bars=fill_bars, horizon_bars=horizon, **FEE))

    print(f"\nCONFIRMED: entry refined onto {ltf_name}  "
          f"(n={len(base)} comparable, {skipped} skipped)")
    if len(base) < 30:
        print("  too few — the faster chart does not reach back far enough")
        return
    for lab, outs in ((f"{INTERVAL} gap + {INTERVAL} stop  <- shipped", base),
                      (f"{ltf_name} gap + {ltf_name} stop", alt)):
        rs = [o.r for o in outs]
        fill = sum(o.filled for o in outs) / len(outs)
        won = [o for o in outs if o.filled]
        win = sum(o.r > 0 for o in won) / len(won) if won else 0.0
        m, se = mean_se(rs)
        print(f"  {lab:<34} fill {fill:5.1%}  win {win:5.1%}  "
              f"{m:+.3f} ± {se:.3f}  tot {sum(rs):+7.1f}")
    d = [b.r - a_.r for a_, b in zip(base, alt)]
    dm = statistics.fmean(d)
    dse = statistics.stdev(d) / len(d) ** 0.5 if len(d) > 1 else 0.0
    print(f"  {'paired difference':<34} {dm:+.3f}"
          + (f"  {dm / dse:+.1f} SE" if dse else ""))


def main():
    rows = load_sync(**FEE)
    print(f"loaded {len(rows)} signals")

    print("\n" + "=" * 74 + "\nA. THE RAID INSIDE A 4h ORDER BLOCK / FVG\n"
          + "=" * 74)
    asyncio.run(add_htf(rows))
    for lab, _, _ in ZONE_RULES:
        for kind in ("confirmed", "early"):
            sub = [r for r in rows
                   if r.kind == kind and r.htf.get(lab) is not None]
            report(f"{kind}: raid in a zone — {lab}", sub,
                   lambda r, l=lab: r.htf[l], control=risk_terciles)

    print("\n" + "=" * 74 + "\nC. TARGET AT THE OPPOSING LIQUIDITY POOL\n"
          + "=" * 74)
    for kind in ("confirmed", "early"):
        structural_target(rows, kind)

    print("\n" + "=" * 74 + "\nB. ENTRY REFINED ONTO A FASTER CHART\n"
          + "=" * 74)
    for ltf in LTFS:
        asyncio.run(ltf_refine(rows, ltf))


if __name__ == "__main__":
    main()
