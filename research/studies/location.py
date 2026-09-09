"""Is the edge in the LOCATION or in the TRIGGER? A nested ladder.

TWO STUDIES AGREED ON SOMETHING AND NEITHER WAS BUILT TO TEST IT

`lez.py` (rejection trigger) and `momentum.py` (acceptance trigger) are exact
opposites on the same pivot levels, and both landed in the same place: the
trigger contributes about +0.05 R with a standard error twice that, while the
CONTROL — a random bar with no trigger at all — goes from about −0.15 to about
+0.11 once you require the daily trend to agree and the raid to sit in a daily
POI.

That is an accident of two studies, observed after the fact, on discovery
halves, never held out. It is exactly the sort of thing this project has twice
found to be a leak. So it gets its own study, its own pre-registration and its
own held-out shot.

THE LADDER. Every rung uses the IDENTICAL trade shape — market entry at the
bar's close, stop 1.5 x ATR(14), target 3R — so `risk_pct` is the same by
construction and the fee cannot masquerade as an edge. `momentum.py` learned
that the hard way: its structural-stop cells showed +4.8 SE purely because the
signal's stop was 50% wider than the control's. The risk column is printed on
every rung so the reader can check rather than trust.

    L0  random bar, no conditions                      the shape's own cost
    L1  + daily trend agrees
    L2  + raid extreme inside a daily POI
    L3  + BOTH                                         <- LOCATION ALONE
    L4  L3 and a Liquidity Entry Zones trigger         rejection
    L5  L3 and a RIPTIDE cluster sweep                 a real pool, taken
    L6  L5 and sweep_worth's distance rule             a VALID sweep

L5 and L6 are the point of the experiment. LEZ calls a 5-bar `ta.pivothigh` a
liquidity level; Riptide does not. Riptide builds a CLUSTER — several pivots
within `tol_atr` of each other, an actual pool of equal highs or lows — and
then asks a second question that LEZ has no notion of: how far is price from
the level a structure shift would have to break? `sweep_worth` puts that cut at
3%, measured over 5098 raids where under-3% raids were 48% of the population
and 87% of the R.

So L4 vs L5 asks whether Riptide's DEFINITION of a level is better than LEZ's,
and L5 vs L6 asks whether the validity test is worth anything on top. Neither
has been measured; both are the user's question.

PRE-REGISTERED, BEFORE THE FIRST NUMBER

    PRIMARY   L3 — location alone, no trigger — is positive net of fees on the
              HELD-OUT half at 2 SE or better.

              Two SE, not "greater than zero". The last two bars in this
              project were "> 0" and a coin flip clears that half the time; I
              said so at the time and this is the correction.

    SECONDARY Does any trigger rung beat L3 by at least +0.05 R on the
              held-out half, with the same sign on discovery? A rung that only
              wins on one half has not shown anything.

    Neither is a sweep. Seven rungs, fixed in advance, one shape. There is no
    best-of-N to correct for because there is nothing being searched.

WHAT A NEGATIVE PRIMARY WOULD MEAN, said now so it cannot be reinterpreted
later: if L3 is flat, then the +0.11 seen in two control groups was the
discovery halves talking, the trend/POI conditions are not tradeable on their
own, and the right conclusion is that neither the location nor the trigger is
carrying anything on this data.

    PYTHONPATH=. python3 research/studies/location.py
"""
from __future__ import annotations

import research.env  # noqa: F401  (must precede riptide.config)

import asyncio
import random
import statistics
from dataclasses import dataclass

import aiohttp

from riptide.config import CFG, BAR_SECONDS, WATCH_MAX_DIST
from riptide.engine import atr_series, run_engine, shift_odds
from riptide.exchange import list_symbols
from riptide.trend import di_direction, supertrend
from research.harness import mean_se, simulate_market
from research.studies.lez import lez_signals
from research.studies.mtf_grid import (fetch_paged, htf_dir_at, in_poi,
                                       zones_of)

HTF = "Day1"
TFS = (("Min30", 2), ("Min15", 4))
SYMBOLS = 30
HORIZON_HOURS = 48
FEE = dict(fee_maker=0.02, fee_taker=0.06)
RANDOM_MULT = 4           # random rungs are cheap; give L0-L3 tight errors

# THE SHAPE, IDENTICAL ON EVERY RUNG. Not swept, not compared — held fixed so
# that risk_pct is constant and the fee cannot be mistaken for an edge.
STOP_ATR = 1.5
TARGET_R = 3.0
ATR_LEN = 14

RUNGS = ("L0 random, no conditions",
         "L1 + daily trend agrees",
         "L2 + raid in a daily POI",
         "L3 + BOTH (location alone)",
         "L4 L3 + LEZ trigger",
         "L5 L3 + Riptide cluster sweep",
         "L6 L5 + valid (shift < %.0f%%)" % WATCH_MAX_DIST)
PRIMARY = 3


@dataclass
class Row:
    rung: int
    r: float
    risk: float
    win: bool


def score(cs, bar, is_long, atr_v, horizon):
    """The one trade shape. Returns (r, risk%) or None."""
    if atr_v <= 0 or bar + 1 + horizon > len(cs):
        return None
    entry = cs[bar].c
    d = atr_v * STOP_ATR
    stop = entry - d if is_long else entry + d
    if entry <= 0 or stop <= 0:
        return None
    o = simulate_market(cs, bar, entry, stop, is_long, target_r=TARGET_R,
                        horizon_bars=horizon, **FEE)
    if o is None:
        return None
    return o.r, 100 * d / entry


async def collect(sess, syms, tf, pages, hcache):
    horizon = max(1, HORIZON_HOURS * 3600 // BAR_SECONDS[tf])
    hstep = BAR_SECONDS[HTF]
    out = {"disc": [], "held": []}
    days, bars_seen = [], 0

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
        bars_seen += len(cs)
        hst, hdi = supertrend(hcs), di_direction(hcs)
        zones = zones_of(hcs, atr_series(hcs, CFG.atr_len))
        atr = atr_series(cs, ATR_LEN)
        cut = len(cs) // 2
        rnd = random.Random(3000 + n)

        def ctx(bar, is_long):
            """(trend agrees, raid is in a daily POI) for one candidate.

            The POI is tested at the bar's EXTREME in the trade's direction —
            the raid, not the entry — which is the convention riptide/scanner.py
            uses and the same one lez_sweep.py used.
            """
            t = cs[bar].t
            d = htf_dir_at(hcs, hst, hdi, t)
            raid = cs[bar].l if is_long else cs[bar].h
            return d == (1 if is_long else -1), in_poi(zones, t, raid,
                                                       is_long, hstep)

        def add(bar, is_long, rungs):
            s = score(cs, bar, is_long, atr[bar], horizon)
            if s is None:
                return False
            r, risk = s
            half = "held" if bar < cut else "disc"
            for k in rungs:
                out[half].append(Row(k, r, risk, r > 0))
            return True

        # ---- L0..L3, random bars. Direction is the daily trend's own where
        # the trend is required (L1, L3) and a coin toss where it is not (L0,
        # L2) — a control for "trend agrees" that picked its own direction
        # would be measuring the trend twice.
        n_rand = max(200, (len(cs) // 40) * RANDOM_MULT)
        for _ in range(n_rand):
            bar = rnd.randrange(60, len(cs) - horizon - 2)
            if atr[bar] <= 0:
                continue
            # Arm A, coin-toss direction: L0, and L2 when the raid is in a POI.
            is_long = rnd.random() < 0.5
            _, poi = ctx(bar, is_long)
            add(bar, is_long, [0, 2] if poi else [0])
            # Arm B, the DAILY TREND'S own direction: L1, and L3 when in a POI.
            # A "trend agrees" control that chose its own direction and then
            # filtered on agreement would be measuring the trend twice and
            # halving its own sample for nothing. The direction IS the trend.
            d = htf_dir_at(hcs, hst, hdi, cs[bar].t)
            if d != 0:
                is_long = d > 0
                _, poi = ctx(bar, is_long)
                add(bar, is_long, [1, 3] if poi else [1])

        # ---- L4, the LEZ trigger, under the same location requirement
        for s in lez_signals(cs):
            agree, poi = ctx(s.bar, s.is_long)
            if agree and poi:
                add(s.bar, s.is_long, [4])

        # ---- L5 / L6, RIPTIDE's own sweep detection
        # A Sweep is a CLUSTER of equal highs or lows being taken, not a single
        # 5-bar pivot being poked. A swept HIGH implies a SHORT, which is the
        # convention riptide/scanner.py uses.
        sweeps: list = []
        try:
            run_engine(sym, cs, CFG, sweeps_out=sweeps)
        except Exception:
            sweeps = []
        idx = {c.t: i for i, c in enumerate(cs)}
        for w in sweeps:
            bar = idx.get(w.sweep_time)
            if bar is None:
                continue
            is_long = not w.is_high
            agree, poi = ctx(bar, is_long)
            if not (agree and poi):
                continue
            od = shift_odds(w.sweep_extreme, w.struct_level)
            valid = od is not None and od[0] < WATCH_MAX_DIST
            add(bar, is_long, [5, 6] if valid else [5])
    return out, days, bars_seen


def line(lab, rows, base=None):
    if len(rows) < 25:
        print(f"  {lab:<32}{len(rows):>7}   too few")
        return None
    rs = [r.r for r in rows]
    m, se = mean_se(rs)
    risk = statistics.fmean(r.risk for r in rows)
    extra = ""
    if base is not None and base[0] is not None:
        d = m - base[0]
        dse = (se ** 2 + base[1] ** 2) ** 0.5
        extra = f"{d:>+9.3f}{d / dse if dse else 0:>+6.1f}"
    print(f"  {lab:<32}{len(rows):>7}{sum(r.win for r in rows) / len(rows):>7.0%}"
          f"{risk:>7.2f}%{m:>+9.3f}{se:>7.3f}{extra}")
    return m, se


HEAD = (f"  {'rung':<32}{'n':>7}{'win':>7}{'risk':>8}{'R/sig':>9}{'SE':>7}"
        f"{'vs L3':>9}{'SE':>6}")


def report(tf, data, days, bars):
    print(f"\n{'=' * 104}\n{tf}   {statistics.median(days):.0f} days across "
          f"{len(days)} symbols, split in half\n{'=' * 104}")
    for half, title in (("disc", "DISCOVERY (newer half)"),
                        ("held", "HELD OUT (older half) — never looked at")):
        rows = data[half]
        print(f"\n  {title}")
        print(HEAD)
        by = {k: [r for r in rows if r.rung == k] for k in range(len(RUNGS))}
        l3 = mean_se([r.r for r in by[PRIMARY]]) if len(by[PRIMARY]) >= 25 \
            else (None, 0.0)
        for k, lab in enumerate(RUNGS):
            line(lab, by[k], base=l3 if k > PRIMARY else None)
        # RISK IS NOT CONSTANT ACROSS RUNGS EVEN THOUGH THE STOP RULE IS.
        # The stop is always 1.5 x ATR, so risk_pct varies with the symbol's
        # volatility, and a rung that selects quieter symbols carries a
        # SMALLER risk_pct — which means a LARGER fee in R, since fee in R is
        # fee / risk_pct. That is a handicap, not a flattery, and it runs the
        # opposite way to the trap momentum.py fell into. Printed so the
        # direction is checked rather than assumed.
        if l3[0] is not None:
            r3 = statistics.fmean(r.risk for r in by[PRIMARY])
            for k in (4, 5, 6):
                if len(by[k]) < 25:
                    continue
                rk = statistics.fmean(r.risk for r in by[k])
                if abs(rk - r3) / r3 > 0.10:
                    pen = 0.12 / rk - 0.12 / r3
                    note = ("handicap" if pen > 0
                            else "ADVANTAGE - discount its result")
                    print(f"    {RUNGS[k][:2]} risk {rk:.2f}% vs L3 {r3:.2f}%"
                          f"  ->  {abs(pen):.3f} R "
                          f"{'more' if pen > 0 else 'less'} fee per losing "
                          f"trade ({note})")
        # How much filtering each rung actually does — the "too many signals"
        # question, in signals per symbol per day.
        span = statistics.median(days) / 2 * len(days)
        print(f"    trigger rungs, per symbol per day:  "
              + "   ".join(f"{RUNGS[k][:2]} {len(by[k]) / span:.2f}"
                           for k in (4, 5, 6) if span))

    held = data["held"]
    p = [r.r for r in held if r.rung == PRIMARY]
    print(f"\n  VERDICT on the pre-registered primary — L3, location alone, "
          f"held-out half")
    if len(p) < 25:
        print("    too few rows")
        return
    m, se = mean_se(p)
    print(f"    n={len(p)}   R/signal {m:+.3f} ± {se:.3f}   "
          f"{m / se if se else 0:+.1f} SE")
    print(f"    => {'PASSES' if se and m / se >= 2.0 else 'FAILS'} "
          f"— the bar was positive at 2 SE, fixed before the run")


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = (await list_symbols(sess))[:SYMBOLS]
        print("Location or trigger? A nested ladder.\n"
              f"{len(syms)} symbols · one trade shape on every rung: market "
              f"entry at the close, {STOP_ATR:g} x ATR({ATR_LEN}) stop, "
              f"{TARGET_R:g}R target, fees 0.02/0.06%")
        hcache: dict = {}
        for tf, pages in TFS:
            data, days, bars = await collect(sess, syms, tf, pages, hcache)
            if days:
                report(tf, data, days, bars)


if __name__ == "__main__":
    asyncio.run(main())
