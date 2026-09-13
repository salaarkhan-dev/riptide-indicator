"""Is Min15 worth scanning — measured on the signals actually SENT.

THE RAW NUMBER LOOKS DAMNING AND THE RAW NUMBER IS THE WRONG ONE.
`exit_grid.py` put held-out Min15 early at -0.012 R with a 75.8 R drawdown
against Min30's +0.020 R at 34.7 — twice the drawdown for a negative return.
But that is EVERY Min15 signal the engine finds, and the bot does not send
every signal. It sends what survives POI_REQUIRED and MIN_GRADE=B.

That distinction is not a technicality here, it is the entire question. This
project's own cell table already says so: "Min15 alone is NEGATIVE (-0.095
confirmed, -0.039 early) and only turns positive inside a daily POI (+0.417
and +0.159). So a second timeframe is worth having ONLY with POI_REQUIRED on,
and turning one on without the other makes the bot worse."

So the honest test replicates the deployed gates — daily POI on the raid, and
grade B or better — and asks whether Min15 still earns its place among what
actually reaches the phone. Answering with ungated numbers would be answering
a question nobody is asking.

TWO REASONS THIS IS WORTH RE-RUNNING NOW

  THE FEE WAS WRONG. Every earlier reading of this question charged twice the
  real rate, and Min15's raids are TIGHTER — a smaller risk_pct means a larger
  fee as a fraction of R, so an overstated fee punishes the faster timeframe
  hardest and disproportionately. Correcting it should help Min15 more than
  Min30, and by how much is the thing to find out.

  THE DRAWDOWN INSTRUMENT WAS CHAOTIC. The old comparison leaned on
  portfolio.simulate, whose eight-slot cap is path-dependent. Drawdown here is
  the uncapped R equity curve — deterministic, so Min30-alone and Min30+Min15
  can actually be compared.

THE DECIDING COMPARISON IS THE COMBINED STREAM, not the two timeframes side by
side. Min15 does not replace Min30; it is ADDED to it. So what matters is
whether Min30+Min15 beats Min30 alone on total R and on drawdown — a
timeframe can be individually mediocre and still worth adding if its trades
land when the other's do not, and individually fine yet not worth adding if
they arrive together.

PRE-REGISTERED, BEFORE THE FIRST NUMBER

  PRIMARY   Among SENT signals (POI required, grade B+), the combined
            Min30+Min15 stream must beat Min30 alone on TOTAL R over the
            held-out half. If it does not, Min15 is costing money.

  SECONDARY R per signal for each timeframe inside each gate, the deterministic
            drawdown of each stream, and how much of the traffic Min15 is.

  EXPECTATION: gated Min15 is positive but weaker than Min30, and adding it
  raises total R while also raising drawdown. Recorded so it cannot be revised.

    PYTHONPATH=. python3 research/studies/min15_worth.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import statistics                                       # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import CFG, MIN_GRADE, TRACK_TARGET_R  # noqa: E402
from riptide.engine import grade_of, run_engine         # noqa: E402
from riptide.exchange import fetch_candles, list_symbols  # noqa: E402
from riptide.trend import di_at, direction_at, poi_at   # noqa: E402
from research.harness import mean_se, simulate          # noqa: E402

TGT = TRACK_TARGET_R
BANDS = "ABCD"


class Row:
    __slots__ = ("tf", "kind", "r", "filled", "poi", "grade", "t", "risk",
                 "half")


async def collect(sess, syms):
    rows, spans = [], []
    for sym in syms:
        per_tf = {}
        for tf in ("Min30", "Min15"):
            try:
                cs = await fetch_candles(sess, sym, tf)
            except Exception:
                continue
            if len(cs) < 300:
                continue
            per_tf[tf] = cs
        if "Min30" not in per_tf:
            continue
        spans.append((per_tf["Min30"][0].t, per_tf["Min30"][-1].t))
        for tf, cs in per_tf.items():
            early = []
            try:
                setups = run_engine(sym, cs, CFG, early_out=early)
            except Exception:
                continue
            idx = {c.t: i for i, c in enumerate(cs)}
            mid = cs[len(cs) // 2].t
            for kind, sigs, key in (("early", early, "fvg_time"),
                                    ("confirmed", setups, "detected_time")):
                for x in sigs:
                    i = idx.get(getattr(x, key))
                    if i is None or abs(x.entry - x.stop) <= 0 or x.entry <= 0:
                        continue
                    o = simulate(cs, i, x.entry, x.stop, x.is_long,
                                 target_r=TGT)
                    if o.exit_bar is None and o.filled:
                        continue
                    when = getattr(x, key)
                    # The DEPLOYED gates, computed the way the scanner does:
                    # POI on the raid extreme (the stop), and the grade from
                    # POI plus the two Hour8 trend readings.
                    poi = await poi_at(sess, sym, when, x.stop, x.is_long,
                                       fetch_candles)
                    d = await direction_at(sess, sym, when, fetch_candles)
                    di = await di_at(sess, sym, when, fetch_candles)
                    r = Row()
                    r.tf, r.kind = tf, kind
                    r.r, r.filled = o.r, o.filled
                    # poi_at returns None on a failed daily fetch, and the
                    # scanner SENDS in that case rather than muting a symbol
                    # for a transient failure. Same rule here.
                    r.poi = True if poi is None else bool(poi)
                    r.grade = grade_of(kind == "early", r.poi, d or 0,
                                       x.is_long, di or 0)[0]
                    r.t = when
                    r.risk = 100 * abs(x.entry - x.stop) / x.entry
                    r.half = "held" if when < mid else "disc"
                    rows.append(r)
    return rows, spans


def dd_r(rows):
    """Deterministic max drawdown of the R equity curve, one unit per trade."""
    bal = peak = dd = 0.0
    for x in sorted(rows, key=lambda z: z.t):
        bal += x.r
        peak = max(peak, bal)
        dd = max(dd, peak - bal)
    return dd


def line(lab, rows):
    if len(rows) < 30:
        print(f"  {lab:<34}{len(rows):>7}   too few")
        return None
    m, se = mean_se([x.r for x in rows])
    win = sum(1 for x in rows if x.r > 0) / len(rows)
    risk = statistics.fmean(x.risk for x in rows)
    d = dd_r(rows)
    tot = sum(x.r for x in rows)
    print(f"  {lab:<34}{len(rows):>7}{win:>7.0%}{risk:>7.2f}%{m:>+10.3f}"
          f"{se:>7.3f}{tot:>+9.1f}{d:>8.1f}{(tot / d) if d else 0:>7.2f}")
    return m, se, tot, d


def sent(rows):
    """What the deployed config would actually send: POI required, grade B+."""
    cut = BANDS.index(MIN_GRADE)
    return [x for x in rows
            if x.filled and x.poi and BANDS.index(x.grade) <= cut]


def panel(title, rows):
    print(f"\n{title}")
    print(f"  {'':<34}{'n':>7}{'win':>7}{'risk':>8}{'R/sig':>10}{'SE':>7}"
          f"{'total R':>9}{'maxDD':>8}{'R/DD':>7}")
    for tf in ("Min30", "Min15"):
        for kind in ("early", "confirmed"):
            line(f"{tf} {kind}",
                 [x for x in rows if x.tf == tf and x.kind == kind])
    a = line("Min30 ALONE (both kinds)", [x for x in rows if x.tf == "Min30"])
    b = line("Min30 + Min15 COMBINED", rows)
    if a and b:
        print(f"  {'adding Min15 changes':<34}{'':>22}"
              f"{b[2] - a[2]:>+22.1f}{b[3] - a[3]:>+8.1f}"
              f"{b[2] / b[3] - a[2] / a[3] if a[3] and b[3] else 0:>+7.2f}")


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = await list_symbols(sess)
        rows, spans = await collect(sess, syms)
    if not rows:
        print("no signals")
        return
    days = statistics.median((b - a) / 86400 for a, b in spans)
    print(f"IS Min15 WORTH SCANNING — on the signals actually SENT\n"
          f"{len(syms)} symbols · {days:.0f} days of Min30 history · "
          f"POI required, grade {MIN_GRADE}+ · target {TGT:g}R\n"
          f"drawdown is the UNCAPPED R equity curve, so it is deterministic")

    s = sent(rows)
    n15 = sum(1 for x in s if x.tf == "Min15")
    print(f"\nTRAFFIC  {len(s)} sent signals · Min15 is {n15} of them "
          f"({n15 / len(s):.0%})")

    panel("ALL — everything the engine finds, both gates OFF",
          [x for x in rows if x.filled])
    panel(f"SENT — POI required, grade {MIN_GRADE}+ "
          f"(RIPTIDE_MIN_GRADE)", s)
    panel(f"SENT · HELD OUT (older half) — the pre-registered panel "
          f"(grade {MIN_GRADE}+)",
          [x for x in s if x.half == "held"])
    print(f"\nPRE-REGISTERED: among SENT signals on the HELD-OUT half, "
          f"Min30+Min15\nmust beat Min30 alone on TOTAL R. If it does not, "
          f"Min15 is costing money.")


if __name__ == "__main__":
    asyncio.run(main())
