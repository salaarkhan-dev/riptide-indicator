"""Where is the knee in the shift distance, and is percent the right unit?

`location.py` left exactly one thing alive: of everything tested across six
studies, the only rung positive in all four panels was Riptide's own
`sweep_worth` validity rule — the level a structure shift must break is within
`WATCH_MAX_DIST` = 3% of the raid extreme. It beat location-alone by +0.042,
+0.092, +0.053 and +0.020, and it did so while paying 0.032–0.038 R MORE fee
per losing trade, because tightening the distance selects quieter symbols.

That last clause is the whole reason this study is shaped the way it is.

THE CONFOUND, NAMED FIRST

Distance is measured as a PERCENT OF PRICE. A quiet symbol's structure sits a
smaller percentage away than a volatile one's, so `dist < 3%` is partly a
volatility filter wearing a geometry filter's clothes. And `risk_pct` here is
`1.5 x ATR / price`, so selecting quiet symbols tightens the stop, and fee in R
is `fee / risk_pct`. Tighten the cut and the fee bill rises.

Two consequences, and they point opposite ways:

  - The fee works AGAINST any improvement from tightening. If R still rises as
    the cut tightens, that is despite a growing handicap, not because of one.
  - But "quiet symbols behave differently" is a separate story from "close to
    structure converts more often", and percent-distance cannot tell them
    apart.

So distance is measured BOTH ways and they are compared head to head:

    dist_pct = |extreme - struct| / extreme * 100      what ships today
    dist_atr = |extreme - struct| / ATR(14)            volatility-neutral

If the ATR version orders the outcome better, that is a concrete, shippable
improvement to a filter already in production. If percent orders better, the
percent cut is measuring something real that ATR misses. Either answer is
useful; "it's 3%, don't touch it" is also an answer.

Net AND GROSS R are printed side by side on every band, so the reader can see
how much of any gradient is the fee rather than the trade.

PRE-REGISTERED, BEFORE THE FIRST NUMBER

  PRIMARY    Does R per signal DECLINE MONOTONICALLY across the four coarse
             bands <1%, 1-2%, 2-3%, >3% — in BOTH halves of the window?

             Monotonicity, not a threshold. `universe.py` was rejected on
             exactly this and was right to be: a variable that is real has a
             dose-response, and a variable that produces one good bucket among
             eight has produced a bucket.

  SECONDARY  Is a cut TIGHTER than 3% better? Measured as <1.5% against
             1.5-3%, and it must hold in both halves to count.

  TERTIARY   Percent vs ATR-normalised, judged on which gives a top-minus-
             bottom gap that is consistent across the two halves.

  ALSO       Re-verify the CONVERSION rate the 3% cut was originally built on —
             does a structure shift and a setup actually follow more often at
             short distances? That table is in riptide/engine.py's docstring,
             measured on a window this project no longer has. A shipped
             constant whose evidence cannot be re-run is a constant on trust.

  NO RECOMMENDATION IS MADE unless the primary passes. A knee found in one
  half is a knee in one half.

    PYTHONPATH=. python3 research/studies/shift_distance.py
"""
from __future__ import annotations

import research.env  # noqa: F401  (must precede riptide.config)

import asyncio
import statistics
from dataclasses import dataclass

import aiohttp

from riptide.config import CFG, BAR_SECONDS, WATCH_MAX_DIST
from riptide.engine import atr_series, run_engine
from riptide.exchange import list_symbols
from riptide.trend import di_direction, supertrend
from research.harness import mean_se, simulate_market
from research.studies.mtf_grid import (fetch_paged, htf_dir_at, in_poi,
                                       zones_of)

HTF = "Day1"
TFS = (("Min30", 2), ("Min15", 4))
SYMBOLS = 30
HORIZON_HOURS = 48
FEE = dict(fee_maker=0.02, fee_taker=0.06)
NO_FEE = dict(fee_maker=0.0, fee_taker=0.0)

STOP_ATR, TARGET_R, ATR_LEN = 1.5, 3.0, 14

PCT_BANDS = ((0.0, 0.5), (0.5, 1.0), (1.0, 1.5), (1.5, 2.0),
             (2.0, 3.0), (3.0, 4.0), (4.0, 6.0), (6.0, 1e9))
COARSE = ((0.0, 1.0), (1.0, 2.0), (2.0, 3.0), (3.0, 1e9))
ATR_BANDS = ((0.0, 1.0), (1.0, 2.0), (2.0, 3.0), (3.0, 5.0),
             (5.0, 8.0), (8.0, 1e9))


@dataclass
class Raid:
    half: str
    dist_pct: float
    dist_atr: float
    risk: float
    r: float           # net of fees
    gross: float       # the same trade with fees zeroed
    converted: bool    # a shift and a setup actually followed
    poi: bool
    agree: bool


async def collect(sess, syms, tf, pages, hcache):
    horizon = max(1, HORIZON_HOURS * 3600 // BAR_SECONDS[tf])
    hstep = BAR_SECONDS[HTF]
    raids: list[Raid] = []
    days = []

    for n, sym in enumerate(syms):
        try:
            cs = await fetch_paged(sess, sym, tf, pages)
            if sym not in hcache:
                hcache[sym] = await fetch_paged(sess, sym, HTF, 1)
            hcs = hcache[sym]
        except Exception:
            continue
        if len(cs) < 800 or len(hcs) < 60:
            continue
        days.append((cs[-1].t - cs[0].t) / 86400)
        hst, hdi = supertrend(hcs), di_direction(hcs)
        zones = zones_of(hcs, atr_series(hcs, CFG.atr_len))
        atr = atr_series(cs, ATR_LEN)
        cut = len(cs) // 2

        sweeps: list = []
        try:
            setups = run_engine(sym, cs, CFG, sweeps_out=sweeps)
        except Exception:
            continue
        # Which raids actually produced a setup. This is the conversion rate
        # the 3% cut was built on, re-measured on the current window rather
        # than trusted from a docstring.
        converted = {s.sweep_time for s in setups if s.sweep_time}
        idx = {c.t: i for i, c in enumerate(cs)}

        for w in sweeps:
            bar = idx.get(w.sweep_time)
            if bar is None or atr[bar] <= 0:
                continue
            if bar + 1 + horizon > len(cs):
                continue
            ext = w.sweep_extreme
            if not ext:
                continue
            gap = abs(ext - w.struct_level)
            is_long = not w.is_high      # a swept HIGH implies a short
            entry = cs[bar].c
            d = atr[bar] * STOP_ATR
            stop = entry - d if is_long else entry + d
            if entry <= 0 or stop <= 0:
                continue
            net = simulate_market(cs, bar, entry, stop, is_long,
                                  target_r=TARGET_R, horizon_bars=horizon,
                                  **FEE)
            gro = simulate_market(cs, bar, entry, stop, is_long,
                                  target_r=TARGET_R, horizon_bars=horizon,
                                  **NO_FEE)
            if net is None or gro is None:
                continue
            t = cs[bar].t
            hd = htf_dir_at(hcs, hst, hdi, t)
            raids.append(Raid(
                half="held" if bar < cut else "disc",
                dist_pct=gap / ext * 100, dist_atr=gap / atr[bar],
                risk=100 * d / entry, r=net.r, gross=gro.r,
                converted=w.sweep_time in converted,
                poi=in_poi(zones, t, ext, is_long, hstep),
                agree=hd == (1 if is_long else -1)))
    return raids, days


HEAD = (f"  {'band':<14}{'n':>6}{'share':>7}{'win':>6}{'risk':>7}"
        f"{'conv':>6}{'R net':>9}{'SE':>7}{'R gross':>9}{'fee':>7}")


def table(rows, bands, key, unit):
    """One banded table. Returns the per-band net means, for monotonicity."""
    print(HEAD)
    total = len(rows)
    means = []
    for lo, hi in bands:
        sub = [x for x in rows if lo <= key(x) < hi]
        lab = f"{lo:g}-{hi:g}{unit}" if hi < 1e9 else f">{lo:g}{unit}"
        if len(sub) < 25:
            print(f"  {lab:<14}{len(sub):>6}   too few")
            means.append(None)
            continue
        m, se = mean_se([x.r for x in sub])
        g, _ = mean_se([x.gross for x in sub])
        risk = statistics.fmean(x.risk for x in sub)
        conv = sum(x.converted for x in sub) / len(sub)
        print(f"  {lab:<14}{len(sub):>6}{len(sub) / total:>7.0%}"
              f"{sum(x.r > 0 for x in sub) / len(sub):>6.0%}{risk:>6.2f}%"
              f"{conv:>6.0%}{m:>+9.3f}{se:>7.3f}{g:>+9.3f}{g - m:>7.3f}")
        means.append(m)
    return means


def monotone_down(ms):
    v = [m for m in ms if m is not None]
    return len(v) >= 3 and all(a >= b for a, b in zip(v, v[1:]))


def report(tf, raids, days):
    print(f"\n{'=' * 104}\n{tf}   {statistics.median(days):.0f} days across "
          f"{len(days)} symbols, split in half   ({len(raids)} raids)"
          f"\n{'=' * 104}")
    # sweep_worth ANDs distance with the POI, so the population it governs is
    # raids inside a daily zone. That is the population measured here.
    pool = {h: [x for x in raids if x.half == h and x.poi] for h in
            ("disc", "held")}
    print(f"  population: raids inside a daily POI — "
          f"discovery {len(pool['disc'])}, held out {len(pool['held'])}")

    verdicts = {}
    for h, title in (("disc", "DISCOVERY (newer half)"),
                     ("held", "HELD OUT (older half)")):
        rows = pool[h]
        if len(rows) < 100:
            print(f"\n  {title}: too few raids")
            continue
        print(f"\n  {title} — distance as a PERCENT of price (what ships)")
        table(rows, PCT_BANDS, lambda x: x.dist_pct, "%")
        print(f"  the four coarse bands the primary is judged on:")
        ms = table(rows, COARSE, lambda x: x.dist_pct, "%")
        verdicts[h] = monotone_down(ms)
        print(f"    -> {'MONOTONE down' if verdicts[h] else 'NOT monotone'}")

        print(f"\n  {title} — distance in ATR (volatility-neutral)")
        table(rows, ATR_BANDS, lambda x: x.dist_atr, " ATR")

    print(f"\n  {'=' * 60}\n  VERDICTS, against the bars fixed before the run")
    ok = verdicts.get("disc") and verdicts.get("held")
    print(f"  PRIMARY  monotone decline across <1 / 1-2 / 2-3 / >3 %, "
          f"both halves: {'PASSES' if ok else 'FAILS'}"
          f"   (discovery {verdicts.get('disc')}, held out {verdicts.get('held')})")

    # SECONDARY — is tighter than 3% better? Both halves must agree.
    print(f"  SECONDARY  tighter than the shipped {WATCH_MAX_DIST:g}% cut:")
    signs = []
    for h in ("disc", "held"):
        rows = pool.get(h) or []
        a = [x.r for x in rows if x.dist_pct < 1.5]
        b = [x.r for x in rows if 1.5 <= x.dist_pct < WATCH_MAX_DIST]
        if len(a) < 25 or len(b) < 25:
            print(f"    {h:<6} too few")
            continue
        ma, sa = mean_se(a)
        mb, sb = mean_se(b)
        d = ma - mb
        signs.append(d)
        print(f"    {h:<6} <1.5% {ma:+.3f} (n={len(a)})   "
              f"1.5-{WATCH_MAX_DIST:g}% {mb:+.3f} (n={len(b)})   "
              f"diff {d:+.3f} ± {(sa ** 2 + sb ** 2) ** 0.5:.3f}")
    if len(signs) == 2:
        agree = all(s > 0 for s in signs) or all(s < 0 for s in signs)
        print(f"    -> {'both halves agree' if agree else 'HALVES DISAGREE'}"
              f"; {'tighter is better' if agree and signs[0] > 0 else ''}"
              f"{'tighter is WORSE' if agree and signs[0] < 0 else ''}")

    # TERTIARY — which unit orders the outcome more consistently?
    print(f"  TERTIARY  percent vs ATR, top band minus bottom band:")
    for lab, key, bands in (("percent", lambda x: x.dist_pct, COARSE),
                            ("ATR    ", lambda x: x.dist_atr, ATR_BANDS)):
        gaps = []
        for h in ("disc", "held"):
            rows = pool.get(h) or []
            # The LOWEST POPULATED band, not literally bands[0]. The first ATR
            # band (0-1 ATR) is empty by construction — a raid whose structure
            # level is under one ATR away barely exists — so comparing against
            # it returned n/a and answered nothing. Correcting a comparison
            # that could not be computed is not moving the goalposts; the
            # question, top band against bottom band, is unchanged.
            lo_b = next((b for b in bands
                         if len([x for x in rows if b[0] <= key(x) < b[1]]) >= 25),
                        None)
            hi_b = bands[-1]
            if lo_b is None:
                gaps.append(None)
                continue
            a = [x.r for x in rows if lo_b[0] <= key(x) < lo_b[1]]
            b = [x.r for x in rows if hi_b[0] <= key(x) < hi_b[1]]
            gaps.append(mean_se(a)[0] - mean_se(b)[0]
                        if len(a) >= 25 and len(b) >= 25 else None)
        g = "  ".join(f"{x:+.3f}" if x is not None else "  n/a" for x in gaps)
        same = (all(x is not None for x in gaps)
                and (gaps[0] > 0) == (gaps[1] > 0))
        print(f"    {lab}  disc/held {g}   "
              f"{'consistent' if same else 'INCONSISTENT'}")

    if not ok:
        print("\n  No cut is recommended. The primary was monotonicity in both"
              "\n  halves and it did not hold; a knee visible in one half is a"
              "\n  knee in one half.")


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = (await list_symbols(sess))[:SYMBOLS]
        print("Where is the knee in the shift distance?\n"
              f"{len(syms)} symbols · Riptide's own raids · market entry at "
              f"the close, {STOP_ATR:g} x ATR({ATR_LEN}) stop, {TARGET_R:g}R"
              f"\nshipped cut: WATCH_MAX_DIST = {WATCH_MAX_DIST:g}%")
        hcache: dict = {}
        for tf, pages in TFS:
            raids, days = await collect(sess, syms, tf, pages, hcache)
            if days:
                report(tf, raids, days)


if __name__ == "__main__":
    asyncio.run(main())
