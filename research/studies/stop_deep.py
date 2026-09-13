"""Stop geometry, on 333 days instead of 42.

THE COMPANION TO entry_deep.py AND A CLEANER TEST THAN IT. Moving the entry
changes the fill rate, so that study had to score per SIGNAL and carry the
unfilled rows as zeros. Moving the STOP does not: the entry is unchanged, so
the same signals fill on the same bars at the same price, and only what happens
afterwards differs. Every row below is the identical trade with the stop in a
different place — about as close to a controlled experiment as this data gets.

WHY RE-RUN. `stops.py` and `stop_buffer.py` asked this on the 42-day window,
like every other entry and exit study in this repository. `entry_deep.py` has
just shown what that costs: its 42-day predecessor's two leading entries, which
led by a fifth of their own error bar, came back as the two WORST on the board
at -5.0 and -4.7 SE once the error bar shrank eightfold. Nothing was wrong with
those studies except the sample.

THE PRIOR HERE IS UNUSUALLY STRONG AND IT POINTS AT A BUFFER. `stop_buffer.py`
recorded that 25% of losing confirmed trades and 36% of losing early ones saw
price reach the target AFTER stopping them out, and that winners carry wider
stops than losers — 1.44% against 1.13% on confirmed. `sl_buffer_atr` has been
0.0 since the beginning and has never been swept on real data.

WIDENING IS NOT FREE, AND R IS WHERE THE COST LANDS. R is measured in units of
risk, so a wider stop shrinks every win in R terms: the same price move is
worth less R because the denominator grew. Sizing to a constant percent of the
account, which is what the bot's entry/stop pair implies, makes that exactly the
right accounting. So the question is whether the stop-outs a buffer avoids are
worth more than the R it gives up, and only a sweep answers it.

THE VARIANTS, all with the DEPLOYED ENTRY:

    raid extreme            what the bot does today, buffer 0.0
    raid +0.25/+0.5/+1.0 ATR   progressively more room
    raid -0.25 ATR          tighter, to probe the other direction rather than
                            only the one the prior favours
    sweep bar extreme       the bar that FIRST took the pool, not the deepest
                            one the trail moved to — usually tighter
    the swept level         the pool itself; tighter than the raid extreme by
                            exactly the overshoot
    FVG far edge            gap invalidation
    MSS bar extreme         where the displacement began

PRE-REGISTERED, BEFORE THE FIRST NUMBER

  PRIMARY. R per signal against the deployed stop, paired on the same signals,
  at 2 SE. Win rate is reported and decides nothing — a wider stop buys win
  rate by construction and that is not the question.

  EXPECTATION. A small buffer (0.25 ATR) roughly neutral to slightly positive,
  larger buffers negative as the R denominator grows faster than the rescues,
  and every TIGHTER stop clearly negative. If 0.25 ATR wins at 2 SE it is the
  first shippable change this project has found since the risk band, and it is
  one config line.

    PYTHONPATH=. RIPTIDE_MIN_GRADE=B RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/stop_deep.py

RESULT, 11 Sep 2026 — THE RAID EXTREME SITS ON THE EDGE OF A PLATEAU.

10142 A/B signals, 115 symbols. Paired against the deployed stop:

    raid +0.25 ATR      +0.007  ±0.006   +1.1 SE
    raid +0.5 ATR       +0.005  ±0.008   +0.6 SE
    raid +1 ATR         +0.004  ±0.010   +0.4 SE
    raid -0.25 ATR      -0.010  ±0.007   -1.3 SE
    the swept level     -0.020  ±0.011   -1.8 SE
    MSS bar extreme     -0.023  ±0.051   -0.4 SE
    sweep bar extreme   -0.026  ±0.007   -3.6 SE
    FVG far edge        -0.119  ±0.019   -6.1 SE

TIGHTER IS CLEARLY WORSE. Every tighter variant is negative and two clear 2 SE,
the gap-invalidation stop catastrophically so at -6.1. WIDER IS FLAT: all three
buffers are positive and none clears 2 SE.

MY EXPECTATION WAS HALF WRONG, AND THE HALF THAT WAS WRONG IS THE INTERESTING
ONE. I predicted tighter stops would lose (they do) and that LARGER buffers
would turn negative as the R denominator outgrew the rescues. They do not —
+1 ATR is still +0.004. The cancellation is near exact across a fourfold range
of buffer, which is a stronger statement than either arm alone: over this whole
span, the stop-outs a wider stop avoids are worth almost precisely the R it
gives up.

THE WIN RATE MAKES THE POINT CONCRETE. At +1 ATR the stop is 65% wider, stop-
outs fall from 62% of fills to 54%, and the win rate rises 36% to 39% — and R
does not move. Three points of win rate, bought honestly, worth zero. Any study
that judged stops on win rate would have shipped +1 ATR and gained nothing.

AND IT PRICES A STATISTIC THAT SOUNDED DECISIVE. `stop_buffer.py` recorded that
25% of losing confirmed trades saw the target AFTER being stopped out. True,
and fully paid for: those rescues are exactly what the buffer buys, and the
denominator takes it all back.

THE ONE ROW WORTH NOT DISMISSING, stated with its weakness first. +0.25 ATR is
+1.1 SE and therefore NOT established. But its point estimate is economically
large: +0.007 across 10142 signals is +71 R, against the deployed stop's +81 R
total. Nearly double the net, on a difference the sample cannot confirm. That
combination — big effect, weak evidence — is precisely what forward data is for
and precisely what must not be shipped on a backtest. `sl_buffer_atr` stays 0.0.

WHAT THIS CLOSES. Stop geometry as a family, in the same sense entry_deep.py
closed entry geometry: the deployed choice cannot be beaten at 2 SE by any of
eight alternatives, and the structural stops an ICT reading would reach for
first — gap invalidation, the swept level, the sweep bar — are the worst of
them.
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import statistics                                       # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import CFG, TRACK_TARGET_R          # noqa: E402
from riptide.engine import atr_series, grade_of, run_engine  # noqa: E402
from riptide.exchange import fetch_candles, list_symbols  # noqa: E402
from riptide.trend import di_at, direction_at, poi_at   # noqa: E402
from research.deep import load_universe                 # noqa: E402
from research.harness import mean_se, simulate          # noqa: E402

DAYS = 333
INTERVAL = "Min30"
DEPLOYED = "raid extreme (deployed)"
MIN_RISK_ATR = 0.25          # same floor as entry_deep, same reason


def stops(cs, sg, bar, a):
    """{name: stop price} for one signal. a is the ATR at the signal bar."""
    idx = {c.t: i for i, c in enumerate(cs)}
    sgn = 1 if sg.is_long else -1          # a long's stop sits BELOW
    out = {DEPLOYED: sg.stop}

    for mult in (0.25, 0.5, 1.0):
        out[f"raid +{mult:g} ATR"] = sg.stop - sgn * mult * a
    out["raid -0.25 ATR"] = sg.stop + sgn * 0.25 * a

    # The bar that FIRST took the pool. `grab_time` is the deepest bar the
    # trail moved to, so this is the same or shallower — a tighter stop.
    s = idx.get(getattr(sg, "sweep_time", 0))
    if s is not None:
        out["sweep bar extreme"] = cs[s].l if sg.is_long else cs[s].h

    out["the swept level"] = sg.level

    if bar - 2 >= 0:
        out["FVG far edge"] = cs[bar - 2].h if sg.is_long else cs[bar - 2].l

    mb = getattr(sg, "mss_bar", None)
    if isinstance(mb, int) and 0 <= mb < len(cs):
        out["MSS bar extreme"] = cs[mb].l if sg.is_long else cs[mb].h
    return out


async def collect(sess, candles):
    rows = []
    for sym, cs in candles.items():
        early = []
        try:
            setups = run_engine(sym, cs, CFG, early_out=early)
        except Exception:
            continue
        idx = {c.t: i for i, c in enumerate(cs)}
        atr = atr_series(cs, CFG.atr_len)
        for kind, batch in (("confirmed", setups), ("early", early)):
            for x in batch:
                i = idx.get(x.detected_time)
                if i is None or x.entry <= 0 or abs(x.entry - x.stop) <= 0:
                    continue
                a = atr[i] if i < len(atr) else 0.0
                if not a:
                    continue
                w = x.detected_time
                poi = await poi_at(sess, sym, w, x.stop, x.is_long,
                                   fetch_candles)
                if not (True if poi is None else bool(poi)):
                    continue
                d = await direction_at(sess, sym, w, fetch_candles)
                di = await di_at(sess, sym, w, fetch_candles)
                if grade_of(kind == "early", True, d or 0, x.is_long,
                            di or 0)[0] not in "AB":
                    continue

                scored = {}
                for name, sl in stops(cs, x, i, a).items():
                    if sl is None or sl <= 0:
                        continue
                    risk = abs(x.entry - sl)
                    sane = (x.entry > sl) if x.is_long else (x.entry < sl)
                    if not sane or risk < MIN_RISK_ATR * a:
                        continue
                    # THE ENTRY NEVER MOVES, so the fill is identical across
                    # every variant and only the outcome after it differs.
                    o = simulate(cs, i, x.entry, sl, x.is_long,
                                 target_r=TRACK_TARGET_R)
                    scored[name] = (o.r, o.filled, 100 * risk / x.entry,
                                    o.exit)
                if DEPLOYED in scored:
                    rows.append(scored)
    return rows


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = await list_symbols(sess)
        candles = await load_universe(sess, syms, INTERVAL, DAYS)
        rows = await collect(sess, candles)

    names = sorted({k for r in rows for k in r},
                   key=lambda n: (n != DEPLOYED, n))
    print(f"STOP GEOMETRY ON THE DEEP WINDOW\n{len(rows)} A/B signals, "
          f"{len(candles)} symbols, {DAYS} days.\nthe ENTRY never moves, so "
          f"every variant fills on the same bar at the same price.\nR per "
          f"signal; an unfilled signal scores 0.0 for every variant alike.")
    print(f"\n  {'stop':<26}{'n':>6}{'risk':>8}{'stopped':>9}{'target':>8}"
          f"{'win':>6}{'R/signal':>11}")
    for n in names:
        got = [r[n] for r in rows if n in r]
        if len(got) < 50:
            continue
        f = [g for g in got if g[1]]
        m, se = mean_se([g[0] for g in got])
        st = sum(1 for g in f if g[3] == "stop") / len(f) if f else 0
        tg = sum(1 for g in f if g[3] == "target") / len(f) if f else 0
        print(f"  {n:<26}{len(got):>6}"
              f"{statistics.median(g[2] for g in got):>7.2f}%{st:>9.0%}"
              f"{tg:>8.0%}{sum(1 for g in f if g[0] > 0) / len(f):>6.0%}"
              f"{m:>+11.3f}")

    print(f"\n  PAIRED against the deployed stop, on R PER SIGNAL")
    diffs = []
    for n in names:
        if n == DEPLOYED:
            continue
        pairs = [(r[n][0], r[DEPLOYED][0]) for r in rows if n in r]
        if len(pairs) < 50:
            continue
        d = [a - b for a, b in pairs]
        md = statistics.fmean(d)
        sd = statistics.pstdev(d) / len(d) ** 0.5
        diffs.append((md, sd, n, len(d)))
    for md, sd, n, k in sorted(diffs, reverse=True):
        z = md / sd if sd else 0.0
        print(f"    {n:<26}{md:>+8.3f}  ±{sd:.3f}{z:>+7.1f} SE  ({k} pairs)"
              + ("   BEATS IT" if z >= 2 else ""))


if __name__ == "__main__":
    asyncio.run(main())
