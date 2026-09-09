"""Does the STEEPNESS of the broken trendline separate anything, at 15m/30m?

THE QUESTION, and why it is not the trading question. The break has already
been scored as a trade and it has no edge (`trendline_measure.py`, and
MEASUREMENTS.md). This asks something different and much weaker, because it is
what a heads-up actually promises: after this alert, did the chart DO anything?
Not "was it profitable" — "was it worth opening".

The intuition being tested is the reader's own: a steeply descending resistance
broken upward is a trend changing, while a nearly FLAT line is just a
horizontal level, and price crossing a horizontal level is the most ordinary
thing a chart does. If that intuition is right, steep breaks should follow
through more often than flat ones. If it is wrong, the slope filter is still
useful — but only as a VOLUME control, and it has to be labelled as one rather
than sold as significance.

HOW STEEPNESS IS MEASURED. The raw slope is price per bar, which is not
comparable between a 100000-dollar symbol and a 0.008-dollar one, nor between
a quiet week and a violent one. Two scale-free forms are computed:

    slope_atr   |slope| / ATR(200) at the break   — steepness in units of the
                                                    symbol's own volatility
    fall        |slope| * run / price             — how far the line travelled
                                                    over its whole span, in
                                                    percent of price

`slope_atr` is the primary. It is the one a trader is really eyeing: a line
falling half an ATR per bar looks steep on any chart, a line falling a
hundredth of one looks flat on any chart.

WHAT COUNTS AS FOLLOW-THROUGH. No fees, no stop, no R — there is no trade here
to charge fees on. Two plain readings over the next H bars:

    cont    is the close H bars later further in the break direction than the
            close at the break? A coin flip is 50%.
    mfe     furthest the price got in the break direction, in ATR
    mae     furthest it got the other way, in ATR

`cont` is primary because it is the one with a known null: 50%. A filter that
cannot beat 50% on continuation is not selecting significance.

PRE-REGISTERED, BEFORE THE FIRST NUMBER

  PRIMARY   The steepest bucket's continuation rate beats the flattest
            bucket's by at least 2 SE, on the HELD-OUT half, at both Min15 and
            Min30. Anything less and the slope filter is a volume control and
            gets described as one.

  The threshold is picked on the DISCOVERY half only and then read off the
  held-out half. A cut chosen after seeing the number it is judged by is not a
  cut, it is a description.

  EXPECTATION, recorded so it cannot be revised afterwards: twelve studies in
  this project have looked for a filter on this kind of signal and found
  nothing. The honest prior is that this finds nothing either, and the useful
  output is then the VOLUME table — how many alerts each threshold leaves —
  which is a real answer to a real question regardless.

    PYTHONPATH=. python3 research/studies/trendline_slope.py
"""
from __future__ import annotations

import research.env  # noqa: F401  (must precede riptide.config)

import asyncio
import statistics

import aiohttp

from riptide.engine import atr_series
from riptide.exchange import list_symbols
from riptide.trendline import ATR_LEN, trendline_signals
from research.harness import mean_se
from research.studies.mtf_grid import fetch_paged

TFS = (("Min15", 4), ("Min30", 2))
SYMBOLS = 60
HORIZON = 8          # bars of follow-through; 2 hours at 15m, 4 at 30m
# The thresholds swept, in |slope| / ATR. 0 is "every break", which is what
# ships today, and it is in the table so every row has something to be
# compared against.
CUTS = (0.0, 0.02, 0.05, 0.10, 0.15, 0.20, 0.30, 0.50)


class Row:
    __slots__ = ("half", "is_long", "slope_atr", "fall", "cont", "mfe", "mae",
                 "gap")


def follow(cs, s, atr, horizon):
    """Continuation, MFE and MAE over the next `horizon` bars, in ATR."""
    end = s.bar + horizon
    if end >= len(cs):
        return None
    a = atr[s.bar]
    if not a or a <= 0:
        return None
    sgn = 1 if s.is_long else -1
    base = cs[s.bar].c
    fwd = cs[end].c
    hi = max(c.h for c in cs[s.bar + 1:end + 1])
    lo = min(c.l for c in cs[s.bar + 1:end + 1])
    mfe = (hi - base) / a if s.is_long else (base - lo) / a
    mae = (base - lo) / a if s.is_long else (hi - base) / a
    return (fwd - base) * sgn > 0, mfe, mae


async def collect(sess, syms, tf, pages):
    rows, days = [], []
    for sym in syms:
        try:
            cs = await fetch_paged(sess, sym, tf, pages)
        except Exception:
            continue
        if len(cs) < 400:
            continue
        days.append((cs[-1].t - cs[0].t) / 86400)
        atr = atr_series(cs, ATR_LEN)
        cut = len(cs) // 2
        for s in trendline_signals(cs):
            f = follow(cs, s, atr, HORIZON)
            if f is None:
                continue
            a = atr[s.bar]
            r = Row()
            # OLDER half is held out and NEWER half is discovery, matching
            # every other study here — so a threshold picked on the recent
            # regime is checked against a regime it never saw.
            r.half = "held" if s.bar < cut else "disc"
            r.is_long = s.is_long
            r.slope_atr = abs(s.slope) / a if a > 0 else 0.0
            r.fall = (100 * abs(s.slope) * max(s.run, 0) / s.price
                      if s.price else 0.0)
            r.gap = 100 * abs(s.price - s.line_y) / s.line_y if s.line_y else 0
            r.cont, r.mfe, r.mae = f
            rows.append(r)
    return rows, days


def rate(rows):
    """Continuation rate and its standard error. Bernoulli, so the SE is
    exact rather than estimated from a spread."""
    n = len(rows)
    if n < 25:
        return None
    p = sum(1 for r in rows if r.cont) / n
    return p, (p * (1 - p) / n) ** 0.5, n


def report(tf, rows, days, per_day_all):
    span = statistics.median(days) if days else 0
    print(f"\n{'=' * 92}\n{tf}   {span:.0f} days x {len(days)} symbols   "
          f"({len(rows)} breaks with {HORIZON} bars of follow-through)"
          f"\n{'=' * 92}")

    disc = [r for r in rows if r.half == "disc"]
    held = [r for r in rows if r.half == "held"]

    print(f"\n  HOW STEEP ARE THEY — |slope| / ATR(200), all breaks")
    vals = sorted(r.slope_atr for r in rows)
    qs = [vals[int(q * (len(vals) - 1))] for q in (.1, .25, .5, .75, .9)]
    print("    " + "  ".join(f"p{int(q * 100)} {v:.3f}"
                             for q, v in zip((.1, .25, .5, .75, .9), qs)))

    print(f"\n  VOLUME AND CONTINUATION by threshold "
          f"(continuation's null is 50%)")
    print(f"  {'|slope|/ATR >=':<16}{'kept':>7}{'% kept':>8}"
          f"{'alerts/day':>12}{'cont DISC':>12}{'cont HELD':>12}"
          f"{'MFE':>7}{'MAE':>7}")
    for c in CUTS:
        keep = [r for r in rows if r.slope_atr >= c]
        if not keep:
            continue
        frac = len(keep) / len(rows)
        d = rate([r for r in keep if r.half == "disc"])
        h = rate([r for r in keep if r.half == "held"])
        mfe = statistics.fmean(r.mfe for r in keep)
        mae = statistics.fmean(r.mae for r in keep)
        print(f"  {c:<16.2f}{len(keep):>7}{100 * frac:>7.0f}%"
              f"{per_day_all * frac:>12.0f}"
              f"{f'{100 * d[0]:.1f}% ±{100 * d[1]:.1f}' if d else '  —':>12}"
              f"{f'{100 * h[0]:.1f}% ±{100 * h[1]:.1f}' if h else '  —':>12}"
              f"{mfe:>7.2f}{mae:>7.2f}")

    # The pre-registered test: steepest quartile against flattest quartile, cut
    # on DISCOVERY and read on HELD OUT.
    dv = sorted(r.slope_atr for r in disc)
    if len(dv) < 100:
        print("\n  too few discovery breaks for the pre-registered test")
        return
    lo_cut, hi_cut = dv[len(dv) // 4], dv[3 * len(dv) // 4]
    print(f"\n  PRE-REGISTERED TEST — quartiles cut on DISCOVERY "
          f"(flat < {lo_cut:.3f}, steep >= {hi_cut:.3f}), read on HELD OUT")
    for name, sub in (("discovery", disc), ("HELD OUT", held)):
        flat = rate([r for r in sub if r.slope_atr < lo_cut])
        steep = rate([r for r in sub if r.slope_atr >= hi_cut])
        if not (flat and steep):
            print(f"    {name:<12} too few")
            continue
        d = steep[0] - flat[0]
        dse = (steep[1] ** 2 + flat[1] ** 2) ** 0.5
        print(f"    {name:<12} flat {100 * flat[0]:.1f}% (n={flat[2]})   "
              f"steep {100 * steep[0]:.1f}% (n={steep[2]})   "
              f"diff {100 * d:+.1f}pp ± {100 * dse:.1f}   "
              f"{d / dse if dse else 0:+.1f} SE")

    # A second, independent reading of the same idea, in case continuation is
    # simply the wrong lens: does the steep bucket move FURTHER either way?
    print(f"\n  MFE - MAE by quartile, held out (a bigger number means the "
          f"break went\n  somewhere rather than nowhere, in either direction)")
    for lab, pred in (("flat ", lambda r: r.slope_atr < lo_cut),
                      ("steep", lambda r: r.slope_atr >= hi_cut)):
        g = [r.mfe - r.mae for r in held if pred(r)]
        if len(g) < 25:
            continue
        m, se = mean_se(g)
        print(f"    {lab}  n={len(g):<6} {m:+.3f} ± {se:.3f} ATR")


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = (await list_symbols(sess))[:SYMBOLS]
        print(f"Trendline break — does the SLOPE separate anything?\n"
              f"{len(syms)} symbols · follow-through over {HORIZON} bars · "
              f"no fees, no stop: this is not a trade, it is 'was the chart "
              f"worth opening'")
        # Measured in trendline_rate.py, on this same universe.
        per_day = {"Min15": 109, "Min30": 52}
        for tf, pages in TFS:
            rows, days = await collect(sess, syms, tf, pages)
            if rows:
                report(tf, rows, days, per_day.get(tf, 0))


if __name__ == "__main__":
    asyncio.run(main())
