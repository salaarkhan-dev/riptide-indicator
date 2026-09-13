"""Sweep volume as the heads-up gate — using the biggest number in the file.

THE UNUSED RESULT. `context.py` measured sweep-to-setup CONVERSION against the
raid bar's relative volume over 7869 sweeps and found it falls monotonically
from 26.4% in the quietest quintile to 6.5% in the loudest: **+15.6 SE**. That
is by far the largest effect this project has ever measured, it inverts the folk
premise — volume surging through a level is a breakout, not a stop run — and it
is used NOWHERE in the bot. It survives only as a paragraph in market.py.

Meanwhile `SWEEP_WATCH_ONLY` gates the heads-up alerts on POI plus a shift
distance under 3%, and that rule came from a much weaker table (48% of raids,
87% of the R that followed).

CONVERSION IS EXACTLY WHAT A HEADS-UP IS FOR. A sweep alert makes no trade
claim: it says "a pool was taken, this chart may be about to set up, go look".
The question it has to answer is whether a setup follows. That is conversion,
and conversion is the axis volume is enormous on and distance is modest on.

So this asks one practical question: if the sweep alert gated on volume instead
of — or as well as — distance, how many alerts would it send and how many of
them would go on to produce a setup?

NOT AN EDGE CLAIM, AND THE DISTINCTION MATTERS. `context.py` also measured raid
volume against R on the setups that DO follow and got nothing (+0.7 SE on early,
an inverted U on confirmed). Conversion and expectancy are different questions
and volume is huge on one and silent on the other. Nothing here claims the
surviving sweeps lead to better trades — only that more of them lead to a trade
at all, which is the whole job of a heads-up.

PRE-REGISTERED, BEFORE THE FIRST NUMBER

  FIRST   Reproduce the +15.6 SE conversion gradient on this corpus. If the
          quintile table does not come back monotone and large, the pipeline is
          wrong and nothing after it means anything.

  THEN    Compare gates head to head on the two numbers a heads-up lives by:
          conversion rate, and alerts per day. A gate is better if it reaches a
          higher conversion at the same or lower volume of messages.

  The volume threshold is the QUINTILE BOUNDARY from the reproduction, not a
  swept value. Picking the cut that maximises the outcome after seeing it is
  how the trendline slope study produced +4.4 SE that reversed on the other
  half.

    PYTHONPATH=. python3 research/studies/sweep_vol_gate.py
"""
import research.env                                     # noqa: F401  MUST be first

import asyncio                                          # noqa: E402
import statistics                                       # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import CFG, WATCH_MAX_DIST          # noqa: E402
from riptide.engine import run_engine, sweep_worth      # noqa: E402
from riptide.exchange import fetch_candles, list_symbols  # noqa: E402

VOL_LOOKBACK = 50        # context.py's definition: median of the 50 bars before


def rvol(cs, bar):
    """Raid-bar turnover against the median of the 50 bars before it."""
    lo = bar - VOL_LOOKBACK
    if lo < 0:
        return None
    prev = [cs[k].v for k in range(lo, bar) if cs[k].v > 0]
    if len(prev) < VOL_LOOKBACK // 2:
        return None
    med = statistics.median(prev)
    return cs[bar].v / med if med > 0 else None


class Row:
    __slots__ = ("rvol", "converted", "early", "dist_ok", "days")


async def collect(sess, syms):
    rows, days = [], []
    for sym in syms:
        try:
            cs = await fetch_candles(sess, sym, "")
        except Exception:
            continue
        if len(cs) < 400:
            continue
        sweeps, early = [], []
        try:
            setups = run_engine(sym, cs, CFG, sweeps_out=sweeps,
                                early_out=early)
        except Exception:
            continue
        days.append((cs[-1].t - cs[0].t) / 86400)
        # A sweep converted if a setup or an early signal came off the SAME
        # raid. Both carry sweep_time, so the link is exact rather than a
        # time-window guess that could pair a raid with an unrelated setup.
        conf_at = {s.sweep_time for s in setups if s.sweep_time}
        early_at = {e.sweep_time for e in early}
        for w in sweeps:
            v = rvol(cs, w.sweep_bar)
            if v is None:
                continue
            r = Row()
            r.rvol = v
            r.converted = w.sweep_time in conf_at
            r.early = w.sweep_time in early_at
            # POI is held at True so this isolates the DISTANCE half of the
            # live gate. POI is orthogonal, already measured, and fetching
            # daily bars for every symbol would cost an hour for a number
            # already known.
            r.dist_ok = sweep_worth(w.sweep_extreme, w.struct_level, True)
            rows.append(r)
    return rows, days


def rate(rows, field="converted"):
    if len(rows) < 30:
        return None
    p = sum(1 for r in rows if getattr(r, field)) / len(rows)
    return p, (p * (1 - p) / len(rows)) ** 0.5, len(rows)


def show(lab, rows, span, n_all, field="converted"):
    x = rate(rows, field)
    if not x:
        print(f"  {lab:<34}{len(rows):>7}   too few")
        return None
    p, se, n = x
    print(f"  {lab:<34}{n:>7}{n / n_all:>8.0%}{n / span:>11.1f}"
          f"{100 * p:>10.1f}%{100 * se:>7.1f}")
    return p, se, n


def main():
    async def go():
        async with aiohttp.ClientSession() as sess:
            syms = await list_symbols(sess)
            return await collect(sess, syms), len(syms)
    (rows, days), nsym = asyncio.run(go())
    if not rows:
        print("no sweeps")
        return
    span = statistics.median(days) * len(days)      # symbol-days
    print(f"SWEEP VOLUME AS THE HEADS-UP GATE\n{len(rows)} sweeps · "
          f"{len(days)} symbols · {statistics.median(days):.0f} days\n"
          f"conversion = a confirmed setup or an early signal came off the "
          f"SAME raid")

    print(f"\n1. REPRODUCTION — conversion by raid-bar volume quintile\n"
          f"   (context.py: 26.4% -> 6.5%, monotone, +15.6 SE over 7869 "
          f"sweeps)")
    vals = sorted(r.rvol for r in rows)
    q = [vals[int(f * (len(vals) - 1))] for f in (.2, .4, .6, .8)]
    print(f"  {'':<34}{'n':>7}{'share':>8}{'per day':>11}{'converts':>11}"
          f"{'SE':>7}")
    buckets = []
    for i, (lo, hi) in enumerate(zip([0] + q, q + [float("inf")])):
        sub = [r for r in rows if lo <= r.rvol < hi]
        buckets.append(show(f"Q{i + 1}  rvol {lo:.2f}-"
                            + ("inf" if hi == float("inf") else f"{hi:.2f}"),
                            sub, span, len(rows)))
    ok = [b for b in buckets if b]
    if len(ok) >= 2:
        d = ok[0][0] - ok[-1][0]
        dse = (ok[0][1] ** 2 + ok[-1][1] ** 2) ** 0.5
        mono = all(a[0] >= b[0] for a, b in zip(ok, ok[1:]))
        print(f"  {'Q1 minus Q5':<34}{'':>26}{100 * d:>+9.1f}pp"
              f"   {d / dse if dse else 0:+.1f} SE"
              f"   {'monotone' if mono else 'NOT monotone'}")

    print(f"\n2. GATES HEAD TO HEAD — the two numbers a heads-up lives by")
    print(f"  {'':<34}{'n':>7}{'share':>8}{'per day':>11}{'converts':>11}"
          f"{'SE':>7}")
    # The threshold is the Q1/Q2 boundary from the table above, not a swept
    # value: "the quietest fifth" is a definition, not a fitted number.
    cut = q[0]
    show("every sweep", rows, span, len(rows))
    show(f"distance only (<{WATCH_MAX_DIST:g}%, live rule)",
         [r for r in rows if r.dist_ok], span, len(rows))
    show(f"volume only (rvol < {cut:.2f})",
         [r for r in rows if r.rvol < cut], span, len(rows))
    show("both", [r for r in rows if r.dist_ok and r.rvol < cut],
         span, len(rows))
    print(f"\n  'per day' is per SYMBOL-day; multiply by {nsym} for the chat.")
    print(f"  A gate is better if it converts more at the same or fewer "
          f"messages.")


if __name__ == "__main__":
    main()
