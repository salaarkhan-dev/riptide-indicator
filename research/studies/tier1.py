"""Tier 1 of the research plan, measured now, from bars already on disk.

WHY THIS EXISTS INSTEAD OF THE SCHEMA MIGRATION. A research plan proposed
instrumenting every setup with some eighty fields across Pine, the alert JSON
and the database, then running twelve hypotheses. Every feature in its Tier 1
and most of its Tier 2 is a deterministic function of candles this repository
already caches and of fields the engine already puts on `Setup`. None of it
needs a new column anywhere. So the hypotheses are run here, today, against the
same 333 days, and the plan can be judged on results rather than on design.

    H1  sweep penetration       |raid extreme - pool| / ATR
    H2  sweep to MSS speed      bars between them
    H3  raid rejection          where the raid candle closed in its own range
    H4  displacement quality    MSS bar range / ATR, and body / range
    H7  pool age                bars from the oldest pivot to the sweep
    H8  pivot count             how many swings formed the pool
    H9  FVG timing              bars from MSS to the entry gap
        liquidity source        Pivot / Day / Week / Session

EACH IS READ ON THE LARGEST POPULATION WHERE IT IS DEFINED. Penetration,
rejection, pool age, pivot count and source exist on early signals too, so they
get all 2395 bets. The three that need a structure shift — MSS speed,
displacement, FVG delay — exist only on confirmed setups, and get 489.

AND EVERY ROW PRINTS THE MDE IT HAD TO BEAT. `power.py` established that the
confirmed stream resolves nothing below about 0.35 R/bet and the full stream
nothing below 0.15, against a largest-ever-measured effect of +0.292. A spread
smaller than its own minimum detectable effect is not a weak finding, it is an
unreadable one, and printing the two side by side is the only way to stop a
number like "+0.11" being discussed as though it meant something.

THREE FILTERS, IN ORDER, AND A ROW MUST PASS ALL THREE.

    1. the high-low spread exceeds the population's MDE
    2. the best bucket's SYMBOL BOOTSTRAP is clear of zero, so it is not five
       coins (survivor.py established that instrument)
    3. the spread holds its SIGN in both halves of the window

Any row failing 1 cannot be believed at any strength. Failing 2 means it is a
handful of symbols. Failing 3 means it is a period.

    PYTHONPATH=. RIPTIDE_MIN_GRADE=B RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/tier1.py

RESULT, 11 Sep 2026 — NINE HYPOTHESES, NONE SURVIVE

  EIGHT DIED ON READABILITY, WHICH IS THE POWER ARGUMENT MADE CONCRETE. The
  full-stream hypotheses produced spreads of 0.096, 0.150, 0.104, 0.096 and
  0.106 against an MDE of 0.152. The confirmed-only ones produced 0.162, 0.151
  and 0.098 against an MDE of 0.351. Those are not weak findings; they are
  numbers the sample cannot distinguish from zero however they are sliced.

  Several share a shape — second or third bucket best, both tails worse, sign
  holding across halves. It is tempting. It is also what four random buckets
  drawn from a common mean do more often than intuition suggests, and every one
  of them is under the noise floor.

  H2, SWEEP-TO-MSS SPEED, CLEARED ALL THREE FILTERS AND THEN FAILED ANYWAY.

    Min30, by bars from sweep to shift:
        1-3    +0.015      4-6    +0.323  (46% win, bootstrap 5th +0.163)
        7-11   -0.044      >11    +0.016
    spread +0.367 against an MDE of 0.351, bootstrap clear, split-half holds.

  The plan predicted the opposite: "fast rejection = better trade", Grade S at
  1-2 bars. The fastest bucket is the second WORST. Whatever this is, it is not
  what was hypothesised.

  It is also NOT the risk band in disguise, which was the obvious way for it to
  be spurious. 4-6 bars is 53% in-band against 40/58/57% for the others, and
  the effect survives conditioning both ways:

        in band + MSS 4-6     78 tr  51% win  +0.476
        in band + MSS other  226 tr  41% win  +0.163
        out     + MSS 4-6     70 tr  41% win  +0.197
        out     + MSS other  219 tr  28% win  -0.206

  A clean additive 2x2. At that point it looked like the first new survivor in
  this project since the risk band.

  THEN IT WAS ASKED TO PREDICT SOMETHING IT HAD NOT BEEN FITTED TO. One
  pre-registered test, one direction, on Min15 — an independent timeframe with
  788 confirmed trades:

        4-6 bars   211 tr  32% win  -0.088        rest  +0.031
        difference -0.119, WRONG SIGN.

  And the Min15 shape is not the Min30 shape at all: -0.074, -0.088, -0.065,
  then +0.248 at 12-20 bars and +0.221 beyond. Slow-is-better, which is neither
  the plan's hypothesis nor the Min30 result. Matching wall-clock instead of
  bar count (8-12 Min15 bars = the same 2-3 hours) gives +0.038 at |z| 0.30,
  which is nothing.

  So the one cell that passed MDE, bootstrap and split-half on 34 cells of
  searching died the moment it had to generalise. That is what the third
  filter is for, and it is why "found among 34 cells" belongs in the write-up
  of anything that passes the first two.

  WHAT THIS SAYS ABOUT THE PLAN. Its Tier 1 is measurable today without the
  schema work, and measured, it is empty. The bottleneck was never
  instrumentation. It is that 489 confirmed bets cannot resolve effects of the
  size these features carry, and no amount of recording makes a past year
  bigger.
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import statistics                                       # noqa: E402
from collections import defaultdict                     # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import BAR_SECONDS, CFG, TRACK_TARGET_R   # noqa: E402
from riptide.engine import atr_series, grade_of, run_engine   # noqa: E402
from riptide.exchange import fetch_candles, list_symbols  # noqa: E402
from riptide.trend import di_at, direction_at, poi_at   # noqa: E402
from research.deep import load_universe                 # noqa: E402
from research.harness import mean_se, simulate          # noqa: E402
from research.studies.power import mde                  # noqa: E402
from research.studies.report import bets_of             # noqa: E402
from research.studies.survivor import symbol_bootstrap  # noqa: E402

DAYS = 333
INTERVAL = "Min30"
DRAWS = 2000


class Row:
    __slots__ = ("sym", "t", "r", "kind", "src", "pen", "reject", "raid_body",
                 "mss_bars", "disp", "disp_body", "fvg_delay", "pool_age",
                 "pivots")


def _loc(c, is_long):
    """Where the candle closed inside its own range, from the trade's side.

    1.0 is a perfect rejection of the raided level — a low sweep closing on its
    high, or a high sweep closing on its low. 0.0 closed at the extreme it just
    made, which is continuation rather than reversal.
    """
    rng = c.h - c.l
    if rng <= 0:
        return 0.5
    return (c.c - c.l) / rng if is_long else (c.h - c.c) / rng


async def collect(sess, candles):
    bar = BAR_SECONDS[INTERVAL]
    out = []
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
                o = simulate(cs, i, x.entry, x.stop, x.is_long,
                             target_r=TRACK_TARGET_R)
                if not o.filled or o.exit_bar is None:
                    continue

                gi = idx.get(x.grab_time)
                a = atr[gi] if gi is not None and gi < len(atr) else 0.0
                if gi is None or not a:
                    continue
                g = cs[gi]
                rng = g.h - g.l

                row = Row()
                row.sym, row.t, row.r, row.kind = sym, w, o.r, kind
                row.src = x.src
                # THE RAID EXTREME IS THE TRAILED ONE, which is why grab_time
                # rather than sweep_time is used: it is the bar the stop is
                # actually measured from, so it is the penetration the trade
                # pays for.
                ext = g.h if not x.is_long else g.l
                row.pen = abs(ext - x.level) / a
                row.reject = _loc(g, x.is_long)
                row.raid_body = abs(g.c - g.o) / rng if rng > 0 else 0.0
                row.pool_age = max(0, (x.sweep_time - x.anchor_time) // bar) \
                    if x.sweep_time and x.anchor_time else 0
                row.pivots = x.pivots
                row.mss_bars = row.disp = row.disp_body = row.fvg_delay = None
                if kind == "confirmed" and x.mss_time and x.sweep_time:
                    row.mss_bars = (x.mss_time - x.sweep_time) // bar
                    mi = idx.get(x.mss_time)
                    if mi is not None and mi < len(atr) and atr[mi]:
                        m = cs[mi]
                        mr = m.h - m.l
                        row.disp = mr / atr[mi]
                        row.disp_body = abs(m.c - m.o) / mr if mr > 0 else 0.0
                    if x.fvg_time:
                        row.fvg_delay = (x.fvg_time - x.mss_time) // bar
                out.append(row)
    return out


def cellstat(rows, draws=DRAWS):
    b = bets_of(rows)
    m, se = mean_se(b)
    bo = symbol_bootstrap(rows, draws)
    p5 = bo[int(0.05 * (len(bo) - 1))] if bo else float("nan")
    return len(rows), len(b), m, se, p5


def hypothesis(name, rows, key, edges, pop_mde, labels=None):
    """One feature, bucketed, against the three filters."""
    rows = [r for r in rows if key(r) is not None]
    if len(rows) < 90:
        print(f"\n{name}: {len(rows)} trades — too few to read.")
        return
    vals = sorted(key(r) for r in rows)
    cuts = [vals[int(e * len(vals))] for e in edges]
    groups, prev = [], None
    for j, c in enumerate(cuts + [None]):
        g = [r for r in rows
             if (prev is None or key(r) > prev) and (c is None or key(r) <= c)]
        lab = (labels[j] if labels else
               (f"<= {c:g}" if c is not None else f"> {prev:g}"))
        groups.append((lab, g))
        prev = c

    print(f"\n{name}   ({len(rows)} trades, MDE {pop_mde:.3f} R/bet)")
    stats = []
    for lab, g in groups:
        if len(g) < 25:
            print(f"    {lab:<16} {len(g):>4} tr — thin")
            stats.append(None)
            continue
        n, nb, m, se, p5 = cellstat(g)
        wins = sum(1 for r in g if r.r > 0) / n
        stats.append((m, p5, g))
        print(f"    {lab:<16} {n:>4} tr {nb:>4} bets  {wins:>3.0%} win  "
              f"{m:>+6.3f}±{se:.3f}  boot5th {p5:>+6.3f}"
              f"{'  OK' if p5 > 0 else ''}")

    live = [s for s in stats if s]
    if len(live) < 2:
        return
    hi = max(live, key=lambda s: s[0])
    lo = min(live, key=lambda s: s[0])
    spread = hi[0] - lo[0]

    ts = sorted(r.t for r in rows)
    mid = ts[len(ts) // 2]
    signs = []
    for pick in (lambda r: r.t < mid, lambda r: r.t >= mid):
        a = [r for r in hi[2] if pick(r)]
        b = [r for r in lo[2] if pick(r)]
        if len(a) < 12 or len(b) < 12:
            signs.append(None)
            continue
        signs.append(statistics.fmean(bets_of(a)) - statistics.fmean(bets_of(b)))
    held = (len(signs) == 2 and all(s is not None for s in signs)
            and (signs[0] > 0) == (signs[1] > 0))

    f1 = spread >= pop_mde
    f2 = hi[1] > 0
    print(f"    spread {spread:>+6.3f} vs MDE {pop_mde:.3f} "
          f"[{'pass' if f1 else 'FAIL — unreadable'}]   "
          f"best bucket bootstrap [{'pass' if f2 else 'FAIL — few symbols'}]   "
          f"split-half [{'holds' if held else 'FLIPS'}]"
          f"   ->  {'SURVIVES' if (f1 and f2 and held) else 'no'}")


async def transfer(sess, fast, label):
    """The pre-registered Min15 test, run last so it cannot steer anything.

    WRITTEN BEFORE THE NUMBERS: the 4-6 bar bucket beats every other MSS speed
    on Min15 confirmed setups, with a POSITIVE difference. One test, one
    direction. The wall-clock variant below is descriptive and is not a second
    bite at the same cherry — if the pre-registered form fails, the hypothesis
    has failed, whatever the alternative says.
    """
    global INTERVAL
    keep, INTERVAL = INTERVAL, "Min15"
    try:
        syms = await list_symbols(sess)
        cs = await load_universe(sess, syms, "Min15", DAYS)
        rows = await collect(sess, cs)
    finally:
        INTERVAL = keep
    conf = [r for r in rows if r.kind == "confirmed" and r.mss_bars is not None]
    if len(conf) < 100:
        print(f"\n{label}: {len(conf)} Min15 trades — cannot test.")
        return
    a = [r for r in conf if fast(r)]
    b = [r for r in conf if not fast(r)]
    ma, sa = mean_se(bets_of(a))
    mb, sb = mean_se(bets_of(b))
    se = (sa ** 2 + sb ** 2) ** 0.5
    bo = symbol_bootstrap(a, DRAWS)
    p5 = bo[int(0.05 * (len(bo) - 1))] if bo else float("nan")
    d = ma - mb
    print(f"\n{label}   ({len(conf)} Min15 confirmed trades)")
    print(f"    in   {len(a):>4} tr  "
          f"{sum(1 for r in a if r.r > 0) / len(a):>3.0%} win  {ma:>+6.3f}±{sa:.3f}"
          f"   bootstrap 5th {p5:>+6.3f}")
    print(f"    out  {len(b):>4} tr  "
          f"{sum(1 for r in b if r.r > 0) / len(b):>3.0%} win  {mb:>+6.3f}±{sb:.3f}")
    print(f"    difference {d:>+6.3f}  |z| {abs(d) / se if se else 0:.2f}"
          f"   ->  " + ("CONFIRMS" if d > 0 and abs(d) / se >= 2
                        else "same sign, not significant" if d > 0
                        else "FAILS — WRONG SIGN"))
    print("    Min15 shape, for comparison with Min30's:")
    for lab, f in (("1-3", lambda r: r.mss_bars <= 3),
                   ("4-6", lambda r: 4 <= r.mss_bars <= 6),
                   ("7-11", lambda r: 7 <= r.mss_bars <= 11),
                   ("12-20", lambda r: 12 <= r.mss_bars <= 20),
                   (">20", lambda r: r.mss_bars > 20)):
        g = [r for r in conf if f(r)]
        if len(g) < 25:
            continue
        mm, ss = mean_se(bets_of(g))
        print(f"      {lab:<8}{len(g):>4} tr  "
              f"{sum(1 for r in g if r.r > 0) / len(g):>3.0%} win  "
              f"{mm:>+6.3f}±{ss:.3f}")


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = await list_symbols(sess)
        candles = await load_universe(sess, syms, INTERVAL, DAYS)
        rows = await collect(sess, candles)

    conf = [r for r in rows if r.kind == "confirmed"]
    ball, bconf = bets_of(rows), bets_of(conf)
    m_all = mde(statistics.pstdev(ball), len(ball) / 2)
    m_conf = mde(statistics.pstdev(bconf), len(bconf) / 2)

    print("TIER 1, MEASURED\n"
          f"{len(rows)} filled A/B trades ({len(ball)} bets) · "
          f"{len(conf)} confirmed ({len(bconf)} bets) · {DAYS} days\n"
          f"MDE: {m_all:.3f} R/bet on the full stream, {m_conf:.3f} on "
          f"confirmed alone.\nthe largest effect this project has ever "
          f"measured is +0.292 R/bet.")

    T = [0.25, 0.5, 0.75]
    hypothesis("H1  sweep penetration / ATR", rows, lambda r: r.pen,
               T, m_all)
    hypothesis("H3  raid rejection (close location)", rows,
               lambda r: r.reject, T, m_all)
    hypothesis("H3b raid body / range", rows, lambda r: r.raid_body, T, m_all)
    hypothesis("H7  pool age, bars", rows, lambda r: r.pool_age, T, m_all)
    hypothesis("H8  pivot count", rows, lambda r: float(r.pivots),
               [0.5, 0.8], m_all)
    hypothesis("H2  sweep to MSS, bars", conf, lambda r: float(r.mss_bars),
               T, m_conf)
    hypothesis("H4  displacement range / ATR", conf, lambda r: r.disp,
               T, m_conf)
    hypothesis("H4b displacement body / range", conf, lambda r: r.disp_body,
               T, m_conf)
    hypothesis("H9  MSS to FVG, bars", conf, lambda r: float(r.fvg_delay),
               [0.4, 0.7], m_conf)

    print(f"\nliquidity source   ({len(rows)} trades, MDE {m_all:.3f})")
    bysrc = defaultdict(list)
    for r in rows:
        bysrc[r.src].append(r)
    for s in sorted(bysrc, key=lambda k: -len(bysrc[k])):
        g = bysrc[s]
        if len(g) < 25:
            print(f"    {s:<16} {len(g):>4} tr — thin")
            continue
        n, nb, m, se, p5 = cellstat(g)
        print(f"    {s:<16} {n:>4} tr {nb:>4} bets  "
              f"{sum(1 for r in g if r.r > 0) / n:>3.0%} win  "
              f"{m:>+6.3f}±{se:.3f}  boot5th {p5:>+6.3f}"
              f"{'  OK' if p5 > 0 else ''}")

    # Run LAST, on a timeframe nothing above was fitted to.
    async with aiohttp.ClientSession() as sess:
        await transfer(sess, lambda r: 4 <= r.mss_bars <= 6,
                       "TRANSFER TEST — H2's 4-6 bar bucket, pre-registered")


if __name__ == "__main__":
    asyncio.run(main())
