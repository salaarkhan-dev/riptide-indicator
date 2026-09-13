"""Is "pool touched 3+ times" a real filter, or one good-looking panel?

WHERE THIS CAME FROM, AND WHY THAT MATTERS. `pivot_tune.py` bucketed the
shipped config's own signals by the touch count of the pool behind them, and
Min30 EARLY separated hard: two-touch pools ran -0.141 R held out at a 34% win
rate, three-or-more ran +0.206 at 46%. That is the strongest separation
anywhere in the early stream, which is otherwise worth about zero.

IT IS ALSO ONE PANEL OF FOUR. Min15 early did not reproduce it — two touches is
the better bucket there — and Min30 CONFIRMED reversed it outright, two-touch
pools running 61% wins against three-touch at 36%. So the honest status of this
idea is: a discovery finding on one cell, with two of its three siblings
disagreeing. Adopting it on that basis is precisely the mistake this project
has made three times.

A FILTER IS A SMALLER CLAIM THAN A CONFIG CHANGE, which is the one thing in its
favour. Raising `min_pivots` changes which pools FORM, so a different level gets
raided and a different trade appears — that is why the sweep and the bucket test
disagreed by 0.86 R on Min30 confirmed. Filtering changes no pool and invents no
level; it only declines to send some of what the engine already found. Whatever
it is worth, it is at least worth what it measures.

THE INSTRUMENT HAS TO BE THE STRICT ONE. Pool touch count is heavily
autocorrelated — a pool persists for hundreds of bars, so consecutive signals on
a symbol share its count almost always. `feature_batch2.py` showed what that
does to a naive null: an independent coin flip cleared 2 SE only 2% of the time
against a textbook 4.6%, handing every real feature an unearned advantage. So
the null here is the CIRCULAR SHIFT — each symbol's touch-count series rotated
in time, preserving the autocorrelation and the keep-rate exactly while
destroying any link to the outcome.

PRE-REGISTERED, BEFORE THE FIRST NUMBER

  The filter survives only if it passes ALL THREE. Any one alone has already
  been shown to admit noise.

  1  STRICT NULL   Its separation clears the circular-shift null's p95 on the
                   panel it was found on.

  2  BOTH SPLITS   It holds its SIGN on the time split AND on an independent
                   SYMBOL split (odd against even symbols). A finding that
                   survives only the partition it was discovered under is a
                   property of that partition.

  3  FRESH SAMPLE  It reproduces on at least one timeframe it was NOT chosen
                   on. Min60 and Hour4 have never been looked at in this
                   project, so nothing about them can have leaked in.

  REPORTED REGARDLESS: the traffic it costs and the win rate it buys, because
  a filter that doubles R per bet by discarding three quarters of the stream
  has not improved the entries, it has picked a smaller product.

  UNIT: one bet per candle close, as priority.py settled. The filter is applied
  per SIGNAL — which is how it would be deployed, since the pool count belongs
  to a signal — and the survivors are then clustered.

  EXPECTATION: it fails condition 3. The Min30-early result is most likely the
  largest of four panels, and Min15 already declined to reproduce it. Recorded
  so it cannot be revised afterwards.

    PYTHONPATH=. RIPTIDE_MIN_GRADE=B python3 research/studies/pivot_filter.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import random                                           # noqa: E402
import statistics                                       # noqa: E402
from collections import defaultdict                     # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import CFG, MIN_GRADE, TRACK_TARGET_R  # noqa: E402
from riptide.engine import grade_of, run_engine         # noqa: E402
from riptide.exchange import fetch_candles, list_symbols  # noqa: E402
from riptide.trend import di_at, direction_at, poi_at   # noqa: E402
from research.harness import mean_se, simulate          # noqa: E402

BANDS = "ABCD"
CUT = BANDS.index(MIN_GRADE)
MIN_TOUCHES = 3                 # the filter under test
SHIFTS = 300                    # circular-shift rotations
TFS = ("Min30", "Min15", "Min60", "Hour4")
FOUND_ON = ("Min30", "early")   # where the idea came from; everything else is fresh


class Sig:
    __slots__ = ("sym", "t", "r", "held", "pivots", "odd")


async def collect(sess, candles, kind):
    """Every SENT signal at the shipped config, carrying its pool touch count."""
    out = []
    for n, (sym, cs) in enumerate(candles.items()):
        early = []
        try:
            setups = run_engine(sym, cs, CFG, early_out=early)
        except Exception:
            continue
        sigs, key = ((setups, "detected_time") if kind == "confirmed"
                     else (early, "fvg_time"))
        idx = {c.t: i for i, c in enumerate(cs)}
        mid = cs[len(cs) // 2].t
        for x in sigs:
            i = idx.get(getattr(x, key))
            if i is None or x.entry <= 0 or abs(x.entry - x.stop) <= 0:
                continue
            o = simulate(cs, i, x.entry, x.stop, x.is_long,
                         target_r=TRACK_TARGET_R)
            if not o.filled or o.exit_bar is None:
                continue
            when = getattr(x, key)
            poi = await poi_at(sess, sym, when, x.stop, x.is_long,
                               fetch_candles)
            poi = True if poi is None else bool(poi)
            if not poi:
                continue
            d = await direction_at(sess, sym, when, fetch_candles)
            di = await di_at(sess, sym, when, fetch_candles)
            if BANDS.index(grade_of(kind == "early", poi, d or 0, x.is_long,
                                    di or 0)[0]) > CUT:
                continue
            s = Sig()
            s.sym, s.t, s.r = sym, when, o.r
            s.held, s.pivots, s.odd = when < mid, getattr(x, "pivots", 0), n % 2
            out.append(s)
    return out


def bets(sigs):
    """One bet per close, averaged. Applied AFTER the filter, as deployed."""
    bybar = defaultdict(list)
    for s in sigs:
        bybar[s.t].append(s.r)
    return [statistics.fmean(v) for v in bybar.values()]


def split(sigs, keepfn):
    """(kept, dropped) summaries and the difference between them, in R per bet."""
    keep = bets([s for s in sigs if keepfn(s)])
    drop = bets([s for s in sigs if not keepfn(s)])
    if len(keep) < 15 or len(drop) < 15:
        return None
    mk, sk = mean_se(keep)
    md, sd = mean_se(drop)
    se = (sk ** 2 + sd ** 2) ** 0.5
    return dict(nk=len(keep), nd=len(drop), mk=mk, md=md,
                wk=sum(1 for r in keep if r > 0) / len(keep),
                wd=sum(1 for r in drop if r > 0) / len(drop),
                diff=mk - md, se=se, z=(mk - md) / se if se else 0.0)


def circular_null(sigs, seeds=SHIFTS):
    """|z| when each symbol's touch-count series is rotated in time.

    Same values, same order, same keep-rate, same autocorrelation — only the
    alignment with the outcome is destroyed. Whatever this produces is what a
    feature shaped like this one can manufacture against an outcome it cannot
    possibly know, and it is the bar the real number has to clear.
    """
    bysym = defaultdict(list)
    for s in sorted(sigs, key=lambda z: z.t):
        bysym[s.sym].append(s)
    out = []
    for k in range(seeds):
        rnd = random.Random(4400 + k)
        rot = {}
        for sym, group in bysym.items():
            if len(group) < 2:
                continue
            j = rnd.randrange(len(group))
            for i, s in enumerate(group):
                rot[id(s)] = group[(i + j) % len(group)].pivots
        got = split([s for s in sigs if id(s) in rot],
                    lambda s: rot[id(s)] >= MIN_TOUCHES)
        if got:
            out.append(abs(got["z"]))
    return sorted(out)


def line(label, got, days=0.0):
    if not got:
        print(f"  {label:<30}   too few")
        return
    rate = f"{got['nk'] / days:>5.1f}" if days else "     "
    print(f"  {label:<30}{rate}{got['nk']:>6}{got['wk']:>6.0%}"
          f"{got['mk']:>+8.3f}   |{got['nd']:>6}{got['wd']:>6.0%}"
          f"{got['md']:>+8.3f}   |{got['diff']:>+8.3f}{got['z']:>+6.1f} SE")


def header():
    print(f"  {'panel':<30}{'/day':>5}{'  KEPT (3+ touches)':<20}"
          f"   |{'  DROPPED (2 touches)':<20}   |  DIFFERENCE")
    print(f"  {'':<30}{'':>5}{'bets':>6}{'win':>6}{'R/bet':>8}"
          f"   |{'bets':>6}{'win':>6}{'R/bet':>8}   |{'R':>8}{'':>9}")


async def main():
    keepfn = (lambda s: s.pivots >= MIN_TOUCHES)
    async with aiohttp.ClientSession() as sess:
        syms = await list_symbols(sess)
        data = {}
        for tf in TFS:
            cands = {}
            for sym in syms:
                try:
                    cs = await fetch_candles(sess, sym, tf)
                except Exception:
                    continue
                if len(cs) >= 300:
                    cands[sym] = cs
            if not cands:
                continue
            days = statistics.median((cs[-1].t - cs[0].t) / 86400
                                     for cs in cands.values())
            data[tf] = (cands, days)

        print(f"THE 3+ TOUCH FILTER — three conditions, all of which must "
              f"pass\n{len(syms)} symbols · POI required · grade {MIN_GRADE}+ "
              f"· target {TRACK_TARGET_R:g}R · one bet per close\n"
              f"found on {FOUND_ON[0]} {FOUND_ON[1]}; every other row is a "
              f"sample it was not chosen on")

        found = None
        for tf in TFS:
            if tf not in data:
                continue
            cands, days = data[tf]
            for kind in ("early", "confirmed"):
                sigs = await collect(sess, cands, kind)
                tag = ("  <-- FOUND HERE" if (tf, kind) == FOUND_ON
                       else "  (fresh)" if tf in ("Min60", "Hour4") else "")
                print(f"\n{tf} {kind}  ·  {days:.0f} days  ·  {len(sigs)} "
                      f"signals{tag}")
                header()
                line("full window", split(sigs, keepfn), days)
                line("time split · discovery",
                     split([s for s in sigs if not s.held], keepfn))
                line("time split · HELD OUT",
                     split([s for s in sigs if s.held], keepfn))
                line("symbol split · odd",
                     split([s for s in sigs if s.odd], keepfn))
                line("symbol split · even",
                     split([s for s in sigs if not s.odd], keepfn))
                if (tf, kind) == FOUND_ON:
                    found = sigs

    if not found:
        return
    print(f"\n{'=' * 96}\nCONDITION 1 — THE STRICT NULL, on the panel it was "
          f"found on\n{'=' * 96}")
    real = split(found, keepfn)
    null = circular_null(found)
    if real and null:
        p95 = null[int(0.95 * (len(null) - 1))]
        print(f"  real separation                {abs(real['z']):>6.2f} SE")
        print(f"  circular-shift null p95        {p95:>6.2f} SE   "
              f"(max over {len(null)} rotations {null[-1]:.2f})")
        print(f"  {'CLEARS' if abs(real['z']) >= p95 else 'DOES NOT CLEAR'} "
              f"the null")
        print(f"\n  A coin-flip null would have been far easier to beat here: "
              f"the touch\n  count persists for the life of a pool, so "
              f"consecutive signals on a symbol\n  share it, and only a "
              f"rotation preserves that while breaking the link to R.")
    print(f"\n  CONDITION 2 is the four split rows above holding one sign.")
    print(f"  CONDITION 3 is Min60 and Hour4 reproducing it. Neither has been "
          f"looked at\n  before in this project, so neither can have leaked "
          f"into the finding.")


if __name__ == "__main__":
    asyncio.run(main())
