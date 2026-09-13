"""HalfTrend on the whole universe, and where its 64% actually comes from.

Entirely separate from Riptide. Shares the candle fetcher and `research.harness`
and nothing else — no cluster, no POI, no grade, no `sweep_worth`, and none of
Riptide's settings.

TWO SCOREBOARDS ON THE SAME TRADES

The indicator prints a win rate on the chart, and that number is why this is
being measured. So it is reproduced (`halftrend.dashboard_counter`, verified
against the chart at 64.00% on ETH 30m) and printed beside an honest score of
the identical signals. The gap between them is the result, and it is arithmetic
rather than opinion.

THE DECOMPOSITION IS THE POINT. For every trade the honest pass records which
of TP1/TP2/TP3 it reached and whether it was stopped, so the three specific
things the dashboard does can be counted rather than argued:

    triple counting   a trade running to TP3 books +1 at TP1, +1 at TP2 and
                      +1 at TP3 — three entries, one trade
    erased losers     a trade that touches TP1 and then stops out has its win
                      removed AND its loss removed; it leaves no trace
    1R wins on a      the panel reads "Target R:R 1 : 3" while the win is
    3R headline       credited at TP1, one risk unit away

THE HONEST SCORE. Market entry at the flip bar's close (taker in, which is what
the Pine does — `entryPx := close`), stop at `atr2 * baseRiskMult`, MEXC fees.
Stop wins a bar spanning both, and the entry bar resolves nothing. Scored
separately at 1R, 2R and 3R, because "60% at 1:3" is two claims and they need
separating.

REPAINT AND LOOKAHEAD were checked in `halftrend.py` and the engine is clean:
signals are `barstate.isconfirmed`, every input reads backwards, and the one
`request.security` feeds the dashboard rather than the signal.

PRE-REGISTERED, BEFORE THE FIRST NUMBER

  PRIMARY   Net R per signal POSITIVE on the HELD-OUT half at 2 SE, at the 3R
            target — the RR the indicator claims.

  SECONDARY The same at 1R, since that is where its win rate is actually
            earned, and a control of random entries with the identical shape.

  A trade counted three times by the dashboard is counted ONCE here, and a
  trade the dashboard erases is counted as what it was.

    PYTHONPATH=. python3 research/studies/halftrend_measure.py
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
from research.harness import mean_se, simulate_market
from research.studies.halftrend import (ATR_LEN, BASE_RISK_MULT,
                                        dashboard_counter, halftrend_signals)
from research.studies.mtf_grid import fetch_paged

TFS = (("Min30", 2), ("Min15", 4), ("Min5", 12))
SYMBOLS = 60
HORIZON_HOURS = 48
FEE = dict(fee_maker=0.02, fee_taker=0.06)
LADDER = (1.0, 2.0, 3.0)
PRIMARY_R = 3.0
RANDOM_MULT = 3


class Row:
    __slots__ = ("half", "sym_split", "is_long", "risk", "rs", "reached",
                 "stopped_after_tp1")


def outcome_facts(cs, s, horizon):
    """Which targets a trade reached and whether it stopped — walked ONCE, so
    a run to TP3 is one trade rather than three, and a stop after TP1 is a
    loss rather than a deletion."""
    sgn = 1 if s.is_long else -1
    hit = 0
    for k in range(s.bar + 1, min(s.bar + 1 + horizon, len(cs))):
        c = cs[k]
        if (c.l <= s.stop) if s.is_long else (c.h >= s.stop):
            return hit, hit >= 1          # stopped; did it touch TP1 first?
        for lvl, n in ((s.tp1, 1), (s.tp2, 2), (s.tp3, 3)):
            if n > hit and ((c.h >= lvl) if s.is_long else (c.l <= lvl)):
                hit = n
        if hit >= 3:
            return 3, False
    return hit, False


async def collect(sess, syms, tf, pages):
    horizon = max(1, HORIZON_HOURS * 3600 // BAR_SECONDS[tf])
    rows, ctrl, days = [], [], []
    dash_w = dash_l = 0

    for n, sym in enumerate(syms):
        try:
            cs = await fetch_paged(sess, sym, tf, pages)
        except Exception:
            continue
        if len(cs) < 600:
            continue
        days.append((cs[-1].t - cs[0].t) / 86400)
        atr = atr_series(cs, ATR_LEN)
        cut = len(cs) // 2
        rnd = random.Random(9000 + n)
        sigs = halftrend_signals(cs)
        w, l = dashboard_counter(cs, sigs)
        dash_w += w
        dash_l += l

        def build(bar, is_long, entry, stop, into, facts=None):
            if entry <= 0 or stop <= 0 or bar + 1 + horizon > len(cs):
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
            r.risk = 100 * abs(entry - stop) / entry
            r.rs = rs
            r.reached, r.stopped_after_tp1 = facts or (0, False)
            into.append(r)

        for s in sigs:
            build(s.bar, s.is_long, s.entry, s.stop, rows,
                  outcome_facts(cs, s, horizon))
        # The control takes the same shape at random bars: same stop rule
        # (atr2 * baseRiskMult), same targets, coin-toss direction.
        for _ in range(len(sigs) * RANDOM_MULT):
            b = rnd.randrange(ATR_LEN + 5, max(ATR_LEN + 6,
                                               len(cs) - horizon - 2))
            a2 = atr[b] / 2.0
            if a2 <= 0:
                continue
            is_long = rnd.random() < 0.5
            e = cs[b].c
            d = a2 * BASE_RISK_MULT
            build(b, is_long, e, e - d if is_long else e + d, ctrl)
    return rows, ctrl, days, dash_w, dash_l


HEAD = (f"  {'':<26}{'n':>7}{'/day':>7}{'win':>6}{'risk':>7}"
        f"{'R/signal':>10}{'SE':>7}{'total R':>9}")


def line(lab, rows, t, span):
    if len(rows) < 25:
        print(f"  {lab:<26}{len(rows):>7}   too few")
        return None
    rs = [r.rs[t].r for r in rows]
    wins = sum(1 for r in rows if r.rs[t].exit == "target")
    m, se = mean_se(rs)
    print(f"  {lab:<26}{len(rows):>7}{len(rows) / span if span else 0:>7.2f}"
          f"{wins / len(rows):>6.0%}"
          f"{statistics.fmean(r.risk for r in rows):>6.2f}%"
          f"{m:>+10.3f}{se:>7.3f}{sum(rs):>+9.1f}")
    return m, se


def report(tf, rows, ctrl, days, dw, dl):
    span = statistics.median(days) / 2 * len(days) if days else 0
    tot = dw + dl
    print(f"\n{'=' * 100}\n{tf}   {statistics.median(days):.0f} days x "
          f"{len(days)} symbols   ({len(rows)} signals)\n{'=' * 100}")
    print(f"\n  THE DASHBOARD'S OWN COUNTER, reproduced over the whole "
          f"universe:  {dw}W / {dl}L = {100 * dw / tot if tot else 0:.1f}%")

    # Where that number comes from, counted rather than argued.
    n = len(rows)
    if n:
        reached = {k: sum(1 for r in rows if r.reached == k)
                   for k in (0, 1, 2, 3)}
        erased = sum(1 for r in rows if r.stopped_after_tp1)
        print(f"  on the SAME {n} trades, walked once each:")
        print(f"    never reached TP1, stopped        {reached[0]:>6}"
              f"  ({reached[0] / n:.0%})   the dashboard counts these, "
              f"correctly, as losses")
        print(f"    reached TP1 then stopped out      {erased:>6}"
              f"  ({erased / n:.0%})   the dashboard DELETES these entirely")
        print(f"    reached TP1/TP2 and ran out       "
              f"{reached[1] + reached[2] - erased:>6}")
        print(f"    reached TP3                       {reached[3]:>6}"
              f"  ({reached[3] / n:.0%})   the dashboard counts each of these "
              f"THREE times")

    for half, title in (("disc", "DISCOVERY (newer half)"),
                        ("held", "HELD OUT (older half)")):
        sub = [r for r in rows if r.half == half]
        csub = [r for r in ctrl if r.half == half]
        print(f"\n  {title} — honest score, one count per trade")
        print(HEAD)
        for t in LADDER:
            line(f"  target {t:g}R", sub, t, span)
        a = line(f"CONTROL random, {PRIMARY_R:g}R", csub, PRIMARY_R, span)
        s3 = [r.rs[PRIMARY_R].r for r in sub]
        if a and len(s3) >= 25:
            m, se = mean_se(s3)
            d, dse = m - a[0], (se ** 2 + a[1] ** 2) ** 0.5
            print(f"  {'EDGE over the control':<26}{'':>37}{d:>+10.3f}"
                  f"{dse:>7.3f}   {d / dse if dse else 0:+.1f} SE")
        print(f"  splits at {PRIMARY_R:g}R")
        for lab, pred in (("symbols A", lambda r: r.sym_split == 0),
                          ("symbols B", lambda r: r.sym_split == 1),
                          ("longs", lambda r: r.is_long),
                          ("shorts", lambda r: not r.is_long)):
            g = [r.rs[PRIMARY_R].r for r in sub if pred(r)]
            if len(g) < 25:
                print(f"    {lab:<22} n={len(g)} too few")
                continue
            m, se = mean_se(g)
            print(f"    {lab:<22} n={len(g):<6} {m:+.3f} ± {se:.3f}")

    held = [r.rs[PRIMARY_R].r for r in rows if r.half == "held"]
    print(f"\n  VERDICT — pre-registered: positive at 2 SE, held out, "
          f"{PRIMARY_R:g}R")
    if len(held) < 25:
        print("    too few held-out signals")
        return
    m, se = mean_se(held)
    print(f"    {m:+.3f} ± {se:.3f}   {m / se if se else 0:+.1f} SE   "
          f"=> {'PASSES' if se and m / se >= 2.0 else 'FAILS'}")


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = (await list_symbols(sess))[:SYMBOLS]
        print(f"HalfTrend Long/Short Signal Engine — full universe\n"
              f"{len(syms)} symbols · market entry at the flip close · stop "
              f"{BASE_RISK_MULT:g} x ATR({ATR_LEN})/2 · fees 0.02/0.06%\n"
              f"separate from Riptide: no POI, no grade, no sweep_worth")
        for tf, pages in TFS:
            rows, ctrl, days, dw, dl = await collect(sess, syms, tf, pages)
            if days:
                report(tf, rows, ctrl, days, dw, dl)


if __name__ == "__main__":
    asyncio.run(main())
