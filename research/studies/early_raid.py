"""Was the raid FINISHED when the early signal fired? Four ways of asking.

THE COMPLAINT, stated as a mechanism. The early strategy fires on the FIRST
3-bar imbalance within `early_max_bars` of the raid (engine.py, "No-shift
entry"). Nothing anywhere asks whether the raid has stopped extending. The gap
can form entirely BELOW the level that was swept — price poked under the pool,
bounced two bars, printed a gap, and is still under the level it raided. And
the moment it fires, `early_done` is set and the stop is frozen at
`grab_low - sl_buffer`, so any further extension takes it out.

Confirmed setups already have a guard for this: `c.expired` when price retakes
the raid extreme, added after 7 of 1219 setups came out with an inverted stop
at -0.857 R. Early has no equivalent. This asks whether it should.

FOUR FEATURES, all of them geometry the engine already computes and then throws
away. Deliberately not another context hunt — sweep-bar volume (+0.7 SE), gap
volume (+0.2), RSI extension (+0.4), ADX and volatility regime were all
measured on this exact population in `context.py` and are dead.

  1  RECLAIM      where the gap sits relative to the SWEPT LEVEL, in ATR.
                  Positive means the whole gap is back on the right side of
                  the pool that was raided. This is the missing middle tier:
                  early takes any gap, confirmed needs the structure break,
                  and reclaiming the swept level sits between them.

  2  NEXT BAR     did the bar AFTER the gap make a new raid extreme? This is
                  the complaint in its most literal form. It is also the only
                  one of the four that costs something to act on, so it is
                  scored twice: once as a bucket, and once RE-SIMULATED with
                  the entry delayed a bar, which is what acting on it means.

  3  GRAB CLOSE   did the raid bar CLOSE back inside the level, or close
                  beyond it? A wick through a pool is a rejection; a body
                  through it is a breakdown. `grab_close` is recorded in
                  engine.py and read by nothing.

  4  BARS FROM    how many bars between the raid and the gap. Already on every
     SWEEP        Early and already in the tracker table, so this one needed
                  no new data at all.

PRE-REGISTERED, BEFORE THE FIRST NUMBER

  The bar is `research.harness.report`'s, unchanged and deliberately high:
  3 SE on top-minus-bottom, MONOTONE across buckets, and the SAME SIGN on
  every split. A batch of four features at 2 SE hands you one false positive
  by construction, which is exactly how the trendline slope study produced
  +4.4 SE on one half and the opposite sign on the other.

  For feature 2 the bar is harder and it is the honest one: the delayed-entry
  arm must beat the unfiltered population's mean R, not merely beat its own
  rejected half. A filter that improves R per signal while the delay gives
  back more than it gains has done nothing.

  EXPECTATION, recorded so it cannot be revised afterwards: every one of these
  is a rearrangement of OHLC geometry this project has already mined hard, and
  a dozen filters have died in it. The honest prior is that none of the four
  clears the bar. What makes them worth running anyway is that they are free —
  three are already-recorded fields and the fourth is two candles.

    PYTHONPATH=. python3 research/studies/early_raid.py
"""
import research.env                                     # noqa: F401  MUST be first

import statistics                                       # noqa: E402

from research.data import atr_at, load_sync             # noqa: E402
from research.harness import mean_se, report, simulate  # noqa: E402


def gap_edges(r):
    """(near_edge, far_edge) of the imbalance, in the engine's own terms.

    `near` is the edge closest to the swept level — the one that has to clear
    it for the raid to count as reclaimed. Recomputed from the candles rather
    than stored, because Early keeps only the derived entry price and the
    entry mode can put that anywhere between the two edges.
    """
    cs, i = r.candles, r.bar
    if i - 2 < 0:
        return None, None
    if r.signal.is_long:
        return cs[i - 2].h, cs[i].l          # bull gap: bot, top
    return cs[i - 2].l, cs[i].h              # bear gap: top, bot


def reclaim_atr(r):
    """How far the gap's near edge is PAST the swept level, in ATR.

    Positive: the whole imbalance is back on the reversal side of the pool.
    Negative: the gap formed while price was still beyond the level — the
    bounce inside an unfinished raid.
    """
    near, _ = gap_edges(r)
    a = atr_at(r)
    if near is None or not a:
        return None
    sgn = 1 if r.signal.is_long else -1
    return sgn * (near - r.signal.level) / a


def grab_bar(r):
    idx = {c.t: i for i, c in enumerate(r.candles)}
    return idx.get(getattr(r.signal, "grab_time", 0) or r.signal.sweep_time)


def grab_close_atr(r):
    """Where the raid bar CLOSED relative to the level it raided, in ATR.

    Positive: closed back inside — a wick through the pool. Negative: closed
    beyond it — a body through the pool, which is a breakdown rather than a
    grab.
    """
    g = grab_bar(r)
    a = atr_at(r)
    if g is None or not a:
        return None
    sgn = 1 if r.signal.is_long else -1
    return sgn * (r.candles[g].c - r.signal.level) / a


def raid_extreme(r):
    """The furthest the raid got between the sweep bar and the gap bar."""
    cs = r.candles
    g = grab_bar(r)
    if g is None:
        return None
    lo, hi = g, r.bar
    if hi < lo:
        return None
    if r.signal.is_long:
        return min(cs[k].l for k in range(lo, hi + 1))
    return max(cs[k].h for k in range(lo, hi + 1))


def next_bar_held(r):
    """Did the bar AFTER the gap avoid making a new raid extreme?

    None when there is no next bar. This is the only feature here that a
    filter cannot act on for free: using it means waiting a bar, and the
    delayed-entry arm below is what that costs.
    """
    x = raid_extreme(r)
    cs, i = r.candles, r.bar
    if x is None or i + 1 >= len(cs):
        return None
    return (cs[i + 1].l >= x) if r.signal.is_long else (cs[i + 1].h <= x)


def bars_from_sweep(r):
    return getattr(r.signal, "bars_from_sweep", None)


def main():
    rows = [r for r in load_sync() if r.kind == "early"]
    if not rows:
        print("no early signals")
        return
    m, se = mean_se([r.r for r in rows])
    print(f"EARLY SIGNALS — was the raid finished?\n"
          f"{len(rows)} early signals · baseline {m:+.3f} ± {se:.3f} R "
          f"per signal\n"
          f"bar: 3 SE, monotone, same sign on every split "
          f"(research.harness.report)")

    # 1 — RECLAIM. Thresholds in ATR: below zero the gap never got back past
    # the swept level at all, which is the case the complaint describes.
    report("1. RECLAIM — gap's near edge vs the SWEPT LEVEL, in ATR",
           [r for r in rows if reclaim_atr(r) is not None], reclaim_atr,
           edges=(-0.25, 0.0, 0.5),
           labels=("still beyond", "at the level", "reclaimed",
                   "well past"))

    # 3 — GRAB CLOSE. Same shape, one bar earlier in the story.
    report("3. GRAB CLOSE — where the raid bar closed vs the level, in ATR",
           [r for r in rows if grab_close_atr(r) is not None], grab_close_atr,
           edges=(-0.25, 0.0, 0.5),
           labels=("body through", "closed beyond", "closed inside",
                   "closed well inside"))

    # 4 — BARS FROM SWEEP. Free: already on every Early and in the tracker.
    report("4. BARS FROM SWEEP — how long after the raid the gap formed",
           [r for r in rows if bars_from_sweep(r) is not None],
           bars_from_sweep, edges=(1, 2, 4),
           labels=("next bar", "2 bars", "3-4 bars", "5+ bars"))

    # 2 — NEXT BAR, both ways.
    sub = [r for r in rows if next_bar_held(r) is not None]
    report("2. NEXT BAR — did the bar after the gap avoid a new raid extreme?",
           sub, next_bar_held)

    print("\n2b. THE SAME FILTER, PAID FOR — entry delayed one bar, which is\n"
          "    what acting on it actually means. The limit sits at the same "
          "gap\n    price; only the fill window starts a bar later.")
    held = [r for r in sub if next_bar_held(r)]
    if len(held) < 25:
        print("    too few")
    else:
        delayed = []
        for r in held:
            o = simulate(r.candles, r.bar + 1, r.signal.entry, r.signal.stop,
                         r.signal.is_long)
            if o.exit_bar is None and o.filled:
                continue
            delayed.append(o.r)
        hm, hse = mean_se([r.r for r in held])
        dm, dse = mean_se(delayed)
        print(f"    unfiltered, every early      {m:+.3f} ± {se:.3f}   "
              f"n={len(rows)}")
        print(f"    filtered, entry unchanged    {hm:+.3f} ± {hse:.3f}   "
              f"n={len(held)}   (not actionable — uses the next bar)")
        print(f"    filtered, entry DELAYED 1bar {dm:+.3f} ± {dse:.3f}   "
              f"n={len(delayed)}")
        d, dd = dm - m, (dse ** 2 + se ** 2) ** 0.5
        print(f"    net vs doing nothing         {d:+.3f} ± {dd:.3f}   "
              f"{d / dd if dd else 0:+.1f} SE   "
              f"=> {'PASSES' if dd and d / dd >= 2 else 'FAILS'}")
        kept = len(delayed) / len(rows)
        print(f"    keeps {kept:.0%} of early signals")

    # How often the complaint actually happens, which is worth knowing whether
    # or not any of the four sorts anything.
    print("\nHOW OFTEN THE RAID WAS STILL RUNNING WHEN THE GAP FIRED")
    neg = [r for r in rows if (reclaim_atr(r) or 0) < 0]
    ext = [r for r in sub if not next_bar_held(r)]
    print(f"  gap formed while price was still beyond the swept level   "
          f"{len(neg)}/{len(rows)}  ({len(neg) / len(rows):.0%})")
    print(f"  the very next bar made a NEW raid extreme                 "
          f"{len(ext)}/{len(sub)}  ({len(ext) / len(sub) if sub else 0:.0%})")
    if neg:
        nm, nse = mean_se([r.r for r in neg])
        print(f"  R on the 'still beyond' half   {nm:+.3f} ± {nse:.3f}")
    if ext:
        em, ese = mean_se([r.r for r in ext])
        print(f"  R on the 'raid extended' half  {em:+.3f} ± {ese:.3f}")
    print(f"  median bars from sweep to gap  "
          f"{statistics.median([bars_from_sweep(r) or 0 for r in rows]):.0f}")


if __name__ == "__main__":
    main()
