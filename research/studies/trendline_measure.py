"""Liquidity Trendline, measured the way Riptide is: whole universe, alerts out.

The port lives in `trendline.py` and is verified by `research/test_trendline.py`.
This file only scores it, and it asks the four questions an ALERTING service
has to answer before it sends anything:

    SIGNALS   how many, per symbol per day, on the same universe Riptide scans
    WIN RATE  and — printed beside it, because it is meaningless alone — the
              win rate this configuration needs just to break even after fees
    RR        the target ladder, because the win rate is a dial the target
              sets rather than a property of the strategy (`winrate.py`)
    QUALITY   is there anything on a signal that sorts the good from the bad?
              Without one there can be no grade, and without a grade every
              alert has to be sent or none of them do.

THE SHAPE, held fixed so this is comparable to everything else measured here:
market entry at the breakout bar's close (taker in), stop 1.5 x ATR(14), MEXC
fees 0.02 maker / 0.06 taker. Nothing about the indicator suggests an entry or
a stop, so the shape has to come from somewhere, and it comes from the last
nine studies so the numbers sit on the same axis.

THE CONTROL. Random bars, coin-toss direction, identical stop and target and
fees. Every study in this sequence has needed it: the trade shape has a cost of
its own, and R per signal without a control cannot tell "the signal is good"
from "the shape is cheap". EDGE = strategy minus control is the number that
means something.

PRE-REGISTERED, BEFORE THE FIRST NUMBER

    PRIMARY   Net R per signal POSITIVE on the HELD-OUT half at 2 SE or better,
              at the 2R target.

              Positive, not "better than a baseline". Four studies in this
              sequence used the weaker form and all four were wrong to.

    SECONDARY Does any quality variable sort the outcome — same sign on both
              halves and both timeframes? A variable that only orders one panel
              is a bucket, not a grade.

    The quality variables are fixed here in advance and there are five:
    break distance past the line in ATR, the channel's age in bars, the slope
    in ATR per bar, whether the 4h trend agrees, whether the daily trend
    agrees. No others will be added after the numbers are seen.

    PYTHONPATH=. python3 research/studies/trendline_measure.py
"""
from __future__ import annotations

import research.env  # noqa: F401  (must precede riptide.config)

import asyncio
import random
import statistics

import aiohttp

from riptide.config import BAR_SECONDS
from riptide.engine import atr_series
from riptide.exchange import list_symbols
from riptide.trend import di_direction, supertrend
from research.harness import mean_se, simulate_market
from research.studies.mtf_grid import fetch_paged, htf_dir_at
from research.studies.trendline import trendline_signals

TFS = (("Min30", 2), ("Min15", 4), ("Min5", 12))   # ~83 days each, split in two
SYMBOLS = 60                       # the universe Riptide actually scans
HORIZON_HOURS = 48
FEE = dict(fee_maker=0.02, fee_taker=0.06)
STOP_ATR, ATR_LEN = 1.5, 14
TARGET_R = 2.0                     # the primary; the ladder is below
LADDER = (1.5, 2.0, 3.0, 4.0)
RANDOM_MULT = 3


class Row:
    __slots__ = ("half", "sym_split", "is_long", "risk", "rs", "dist_atr",
                 "age", "slope_atr", "agree_4", "agree_d")


def breakeven_win(target_r: float, risk_pct: float) -> float:
    """The win rate this configuration must beat to break even, after fees.

    Market in (taker), limit out on a target (maker), market out on a stop
    (taker). Cost in R is fee / risk_pct — so this rises as the stop tightens,
    which is why it is printed per bucket rather than quoted once.
    """
    if risk_pct <= 0:
        return float("nan")
    win = target_r - (0.06 + 0.02) / risk_pct
    lose = 1.0 + (0.06 + 0.06) / risk_pct
    return 100 * lose / (win + lose) if (win + lose) > 0 else float("nan")


async def collect(sess, syms, tf, pages, cache):
    horizon = max(1, HORIZON_HOURS * 3600 // BAR_SECONDS[tf])
    rows: list[Row] = []
    ctrl: list[Row] = []
    days = []

    for n, sym in enumerate(syms):
        try:
            cs = await fetch_paged(sess, sym, tf, pages)
            for htf in ("Day1", "Hour4"):
                if (sym, htf) not in cache:
                    cache[(sym, htf)] = await fetch_paged(sess, sym, htf, 1)
        except Exception:
            continue
        hd, h4 = cache[(sym, "Day1")], cache[(sym, "Hour4")]
        if len(cs) < 600 or len(hd) < 40 or len(h4) < 40:
            continue
        days.append((cs[-1].t - cs[0].t) / 86400)
        atr = atr_series(cs, ATR_LEN)
        cut = len(cs) // 2
        sd, dd = supertrend(hd), di_direction(hd)
        s4, d4 = supertrend(h4), di_direction(h4)
        rnd = random.Random(7000 + n)

        def build(bar, is_long, dist_atr, age, slope_atr, into):
            a = atr[bar]
            if a <= 0 or bar + 1 + horizon > len(cs):
                return
            entry = cs[bar].c
            d = a * STOP_ATR
            stop = entry - d if is_long else entry + d
            if entry <= 0 or stop <= 0:
                return
            rs = {}
            for t in LADDER:
                o = simulate_market(cs, bar, entry, stop, is_long, target_r=t,
                                    horizon_bars=horizon, **FEE)
                if o is None:
                    return
                rs[t] = o
            r = Row()
            r.half = "held" if bar < cut else "disc"
            r.sym_split = n % 2
            r.is_long = is_long
            r.risk = 100 * d / entry
            r.rs = rs
            r.dist_atr = dist_atr
            r.age = age
            r.slope_atr = slope_atr
            want = 1 if is_long else -1
            r.agree_4 = htf_dir_at(h4, s4, d4, cs[bar].t) == want
            r.agree_d = htf_dir_at(hd, sd, dd, cs[bar].t) == want
            into.append(r)

        sigs = trendline_signals(cs)
        for s in sigs:
            a = atr[s.bar]
            if a <= 0:
                continue
            # How decisively price cleared the line, how old the channel was,
            # and how steep it ran — the only things a signal carries.
            dist = abs(cs[s.bar].c - s.line_y) / a
            age = s.bar - s.x1
            slope = abs(s.line_y - s.y1) / max(age, 1) / a
            build(s.bar, s.is_long, dist, age, slope, rows)

        for _ in range(len(sigs) * RANDOM_MULT):
            b = rnd.randrange(ATR_LEN + 5, max(ATR_LEN + 6,
                                               len(cs) - horizon - 2))
            build(b, rnd.random() < 0.5, 0.0, 0, 0.0, ctrl)
    return rows, ctrl, days


HEAD = (f"  {'':<26}{'n':>7}{'/day':>7}{'win':>6}{'need':>7}{'risk':>7}"
        f"{'R/signal':>10}{'SE':>7}{'total R':>9}")


def line(lab, rows, t, span):
    if len(rows) < 25:
        print(f"  {lab:<26}{len(rows):>7}   too few")
        return None
    rs = [r.rs[t].r for r in rows]
    wins = sum(1 for r in rows if r.rs[t].exit == "target")
    risk = statistics.fmean(r.risk for r in rows)
    m, se = mean_se(rs)
    print(f"  {lab:<26}{len(rows):>7}{len(rows) / span if span else 0:>7.2f}"
          f"{wins / len(rows):>6.0%}{breakeven_win(t, risk):>6.0f}%"
          f"{risk:>6.2f}%{m:>+10.3f}{se:>7.3f}{sum(rs):>+9.1f}")
    return m, se


def bucket(lab, rows, key, edges, labels, t):
    """Terciles or named bands of one quality variable."""
    print(f"    {lab}")
    for lo, hi, nm in zip([-1e18] + edges, edges + [1e18], labels):
        sub = [r for r in rows if lo <= key(r) < hi]
        if len(sub) < 25:
            print(f"      {nm:<22} n={len(sub)} too few")
            continue
        m, se = mean_se([r.rs[t].r for r in sub])
        w = sum(1 for r in sub if r.rs[t].exit == "target") / len(sub)
        print(f"      {nm:<22} n={len(sub):<6} win {w:>3.0%}   "
              f"{m:+.3f} ± {se:.3f}")


def quality(rows, half, t):
    sub = [r for r in rows if r.half == half]
    if len(sub) < 100:
        return
    print(f"\n  QUALITY VARIABLES ({half}) — pre-registered, five of them")
    for lab, key in (("break distance past the line, ATR",
                      lambda r: r.dist_atr),
                     ("channel age, bars", lambda r: float(r.age)),
                     ("slope, ATR per bar", lambda r: r.slope_atr)):
        vals = sorted(key(r) for r in sub)
        e = [vals[len(vals) // 3], vals[2 * len(vals) // 3]]
        bucket(lab, sub, key, e, ["low", "mid", "high"], t)
    for lab, key in (("4h trend agrees", lambda r: r.agree_4),
                     ("daily trend agrees", lambda r: r.agree_d)):
        print(f"    {lab}")
        for want, nm in ((False, "against/flat"), (True, "agrees")):
            g = [r for r in sub if key(r) == want]
            if len(g) < 25:
                print(f"      {nm:<22} n={len(g)} too few")
                continue
            m, se = mean_se([r.rs[t].r for r in g])
            w = sum(1 for r in g if r.rs[t].exit == "target") / len(g)
            print(f"      {nm:<22} n={len(g):<6} win {w:>3.0%}   "
                  f"{m:+.3f} ± {se:.3f}")


def report(tf, rows, ctrl, days):
    span = statistics.median(days) / 2 * len(days) if days else 0
    print(f"\n{'=' * 104}\n{tf}   {statistics.median(days):.0f} days x "
          f"{len(days)} symbols, split in half   "
          f"({len(rows)} signals, {len(ctrl)} control)\n{'=' * 104}")
    for half, title in (("disc", "DISCOVERY (newer half)"),
                        ("held", "HELD OUT (older half)")):
        sub = [r for r in rows if r.half == half]
        csub = [r for r in ctrl if r.half == half]
        print(f"\n  {title}   — 'need' is the win rate to break even after fees")
        print(HEAD)
        a = line(f"trendline, {TARGET_R:g}R", sub, TARGET_R, span)
        b = line("CONTROL random entries", csub, TARGET_R, span)
        if a and b:
            d, dse = a[0] - b[0], (a[1] ** 2 + b[1] ** 2) ** 0.5
            print(f"  {'EDGE over the control':<26}{'':>7}{'':>7}{'':>6}"
                  f"{'':>7}{'':>7}{d:>+10.3f}{dse:>7.3f}"
                  f"   {d / dse if dse else 0:+.1f} SE")
        print(f"\n  THE RR LADDER — the win rate is the target, not the model")
        print(HEAD)
        for t in LADDER:
            line(f"  target {t:g}R", sub, t, span)
        print(f"\n  SPLITS at {TARGET_R:g}R")
        for lab, pred in (("symbols A", lambda r: r.sym_split == 0),
                          ("symbols B", lambda r: r.sym_split == 1),
                          ("longs", lambda r: r.is_long),
                          ("shorts", lambda r: not r.is_long)):
            g = [r for r in sub if pred(r)]
            if len(g) < 25:
                print(f"    {lab:<22} n={len(g)} too few")
                continue
            m, se = mean_se([r.rs[TARGET_R].r for r in g])
            print(f"    {lab:<22} n={len(g):<6} {m:+.3f} ± {se:.3f}")
        quality(rows, half, TARGET_R)

    held = [r.rs[TARGET_R].r for r in rows if r.half == "held"]
    print(f"\n  VERDICT — the pre-registered primary")
    if len(held) < 25:
        print("    too few held-out signals")
        return
    m, se = mean_se(held)
    print(f"    held-out, {TARGET_R:g}R: {m:+.3f} ± {se:.3f}   "
          f"{m / se if se else 0:+.1f} SE")
    print(f"    => {'PASSES' if se and m / se >= 2.0 else 'FAILS'} — the bar "
          f"was POSITIVE at 2 SE, fixed before the run")


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = (await list_symbols(sess))[:SYMBOLS]
        print(f"Liquidity Trendline With Signals — full universe\n"
              f"{len(syms)} symbols · market entry at the breakout close · "
              f"stop {STOP_ATR:g} x ATR({ATR_LEN}) · fees 0.02/0.06%")
        cache: dict = {}
        for tf, pages in TFS:
            rows, ctrl, days = await collect(sess, syms, tf, pages, cache)
            if days:
                report(tf, rows, ctrl, days)


if __name__ == "__main__":
    asyncio.run(main())
