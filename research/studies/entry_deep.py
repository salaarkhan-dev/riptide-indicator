"""Entry geometry, re-asked on 333 days instead of 42.

WHY THIS IS A RE-RUN AND NOT A NEW IDEA. `research/studies/entry_zones.py`
already asked exactly this question — eleven entry prices on the same raids,
the same stop at the raid extreme, scored per SIGNAL so a deeper entry pays for
the fills it misses. It was designed correctly and its output was regenerated
after the fee correction, so nothing about it is wrong. It was run on 692
signals from 42 days, and that is the only thing wrong with it:

    Fib 0.786 of the leg        +0.011  ±0.055   +0.2 SE
    the swept level             +0.008  ±0.060   +0.1 SE
    order block mid             -0.031  ±0.060   -0.5 SE
    ...
    volumetric OB extreme       -0.098  ±0.066   -1.5 SE

A paired standard error of 0.055 resolves nothing below about 0.11 R per
signal. The two entries that came out ahead did so by a fifth of their own
error bar. That is not a negative result; it is an unreadable one, and
`research/deep.py` exists precisely because most of this project's negatives
were that.

WHAT CHANGES. The deep loader gives 333 days and the universe is now 120
symbols rather than the 20-odd the 42-day pass used. Roughly an order of
magnitude more signals takes the paired error from about 0.055 toward 0.017 —
the difference between being able to see a 0.11 effect and a 0.035 one. Nothing
else moves: same entries, same stop, same scoring rule, same fee.

THE TRAP THAT MAKES THIS MEASURABLE AT ALL, restated because it is the whole
design. A deeper entry FILLS LESS OFTEN, and it fills only on the trades that
came back to it — a selection, not an edge. Scored per fill, every deep entry
looks wonderful because the trades that ran away without it are invisible.
Scored per SIGNAL, with an unfilled signal counting 0.0, the missed opportunity
is paid for. Risk% is printed beside every row for the same reason: a deeper
entry sits closer to the stop, so its risk shrinks and the fee — charged as a
fraction of risk — grows in R terms.

TWO ENTRIES ARE NEW HERE, both from an outside suggestion, both cheap to add
because the machinery already exists: the MSS bar's own extreme, which is where
the displacement began, and the MSS close, which is a market entry the instant
structure shifts. The second duplicates `mss_entry.py`, also a 42-day study, so
it comes along for free.

PRE-REGISTERED, BEFORE THE FIRST NUMBER OF THIS RUN

  PRIMARY. R PER SIGNAL against the deployed FVG near-edge entry, paired on the
  same signals, at 2 SE. Per-fill numbers are printed and decide nothing.

  The 42-day run is NOT the discovery half of a two-stage test — it read
  nothing, so there is nothing to confirm. This is one measurement on a bigger
  sample, and if an entry wins it needs the 2 SE on its own.

  EXPECTATION. Unchanged from the original: the deep entries win per fill and
  lose per signal. The tighter error bar should turn the -1.5 SE rows into
  clearly negative ones rather than reversing them. Of the two that led, I
  expect both to sit near zero with a readable error bar for the first time. A
  genuine winner here would be this project's first structural improvement.

    PYTHONPATH=. RIPTIDE_MIN_GRADE=B RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/entry_deep.py

RESULT, 11 Sep 2026 — THE DEPLOYED ENTRY WINS, AND NOTHING IS CLOSE.

9863 A/B signals, 112 symbols. Paired differences against the near edge, R per
signal:

    FVG mid                 -0.012  ±0.007   -1.8 SE
    Fib 0.5 of the leg      -0.020  ±0.009   -2.3 SE
    FVG far edge            -0.022  ±0.009   -2.4 SE
    volumetric OB extreme   -0.023  ±0.016   -1.4 SE
    order block extreme     -0.027  ±0.012   -2.3 SE
    MSS bar extreme         -0.030  ±0.019   -1.6 SE
    volumetric OB mid       -0.037  ±0.017   -2.2 SE
    Fib 0.618 of the leg    -0.041  ±0.011   -3.9 SE
    order block mid         -0.048  ±0.014   -3.5 SE
    MSS close (market)      -0.058  ±0.025   -2.3 SE
    the swept level         -0.062  ±0.013   -4.7 SE
    Fib 0.786 of the leg    -0.066  ±0.013   -5.0 SE

EVERY alternative is worse and eight of twelve are worse at 2 SE or more. The
paired error is 0.007 to 0.025 against the 42-day run's 0.055, so this resolves
0.013 where that resolved 0.11 — and it is the first question this project has
CLOSED with several significant results rather than a shrug.

THE TWO THAT LED ON 42 DAYS ARE NOW THE TWO WORST ON THE BOARD. Fib 0.786 was
+0.011 and is -0.066 at -5.0 SE; the swept level was +0.008 and is -0.062 at
-4.7 SE. Both led by a fifth of their own error bar and both reversed under an
error bar eight times tighter. Nothing about the old study was wrong except its
sample, and this is what that costs.

MY PRE-REGISTERED EXPECTATION WAS WRONG IN AN INFORMATIVE WAY. I predicted the
deep entries would win PER FILL and lose per signal — the fill-rate selection
argument. They lose on both: Fib 0.786 is -0.132 per fill and the swept level
-0.099, against the near edge's +0.014. So this is not a selection effect at
all.

The mechanism that fits is the opposite of the usual intuition. A deeper entry
only fills when price came BACK further, and price coming back further means
the reclaim was weaker. The trades that retrace deep into the gap are the ones
that were failing. "A better price gives the same trade more room" assumes it
is the same trade. It is not — the depth is itself a signal, and it is a bad
one. The near edge is not merely convenient; it selects for reclaims that do
not come back.

WHAT THIS CLOSES. Entry geometry, as a family. The gap edges, the Fibonacci
levels of the reclaim leg, the order block at two prices, the volumetric
variant, the swept level, the displacement origin and a market entry at the
shift — twelve alternatives, all measured paired on the same signals with the
same stop, none better. This does not need re-running at the next universe
size; the error bar is already small enough to have seen anything worth having.
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
DEPLOYED = "FVG near edge (deployed)"
# A stop closer than this to the entry is not a trade, it is a rounding error.
# Carried over from entry_zones.py, where the swept-level entry printed an R of
# -11565162145 without it: that entry's stop sits at the raid extreme, which is
# only the raid's OVERSHOOT away from the level, often a fraction of a tick.
MIN_RISK_ATR = 0.25


def legs(cs, sg, bar):
    """(raid extreme, leg peak, grab bar index) for the reclaim leg, or None."""
    idx = {c.t: i for i, c in enumerate(cs)}
    g = idx.get(getattr(sg, "grab_time", 0) or getattr(sg, "sweep_time", 0))
    if g is None or g >= bar:
        return None
    seg = cs[g:bar + 1]
    if sg.is_long:
        return min(c.l for c in seg), max(c.h for c in seg), g
    return max(c.h for c in seg), min(c.l for c in seg), g


def order_block(cs, sg, bar, g, volumetric=False):
    """Last opposite-close candle before the reclaim leg took off."""
    for k in range(bar, g - 1, -1):
        down = cs[k].c < cs[k].o
        if down != sg.is_long:
            continue
        if volumetric:
            lo = max(0, k - 20)
            prev = [cs[j].v for j in range(lo, k) if cs[j].v > 0]
            if len(prev) < 10 or cs[k].v <= statistics.median(prev):
                continue
        return cs[k]
    return None


def entries(cs, sg, bar):
    """{name: price}. Same set as entry_zones.py, plus the two MSS entries."""
    out = {DEPLOYED: sg.entry}
    got = legs(cs, sg, bar)
    if not got:
        return out
    ext, peak, g = got
    span = abs(peak - ext)
    sgn = 1 if sg.is_long else -1

    if bar - 2 >= 0:
        a = cs[bar - 2].h if sg.is_long else cs[bar - 2].l
        b = cs[bar].l if sg.is_long else cs[bar].h
        out["FVG mid"] = (a + b) / 2.0
        out["FVG far edge"] = a

    for f in (0.5, 0.618, 0.786):
        out[f"Fib {f:g} of the leg"] = peak - sgn * f * span

    for lab, vol in (("order block", False), ("volumetric OB", True)):
        ob = order_block(cs, sg, bar, g, vol)
        if ob:
            out[f"{lab} extreme"] = ob.l if sg.is_long else ob.h
            out[f"{lab} mid"] = (ob.h + ob.l) / 2.0

    out["the swept level"] = sg.level

    # NEW: the displacement's own origin, and a market entry at the shift.
    mb = getattr(sg, "mss_bar", None)
    if isinstance(mb, int) and 0 <= mb < len(cs):
        out["MSS bar extreme"] = cs[mb].l if sg.is_long else cs[mb].h
        out["MSS close (market)"] = cs[mb].c
    return out


async def collect(sess, candles):
    """Every A/B signal, with every candidate entry scored on the SAME stop."""
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
                for name, px in entries(cs, x, i).items():
                    if px is None or px <= 0:
                        continue
                    # THE STOP NEVER MOVES. That is what makes these the same
                    # trade at a different price rather than different trades.
                    risk = abs(px - x.stop)
                    sane = (px > x.stop) if x.is_long else (px < x.stop)
                    if not sane or risk < MIN_RISK_ATR * a:
                        continue
                    o = simulate(cs, i, px, x.stop, x.is_long,
                                 target_r=TRACK_TARGET_R)
                    scored[name] = (o.r, o.filled, 100 * risk / px)
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
    print(f"ENTRY GEOMETRY ON THE DEEP WINDOW\n{len(rows)} A/B signals, "
          f"{len(candles)} symbols, {DAYS} days.\nR PER SIGNAL — an unfilled "
          f"entry scores 0.0, so a deeper price pays for the fills it misses.")
    print(f"\n  {'entry':<28}{'n':>6}{'fill':>7}{'risk':>8}{'R/fill':>9}"
          f"{'R/signal':>11}")
    stats = {}
    for n in names:
        got = [r[n] for r in rows if n in r]
        if len(got) < 50:
            continue
        fills = [g for g in got if g[1]]
        per_sig = [g[0] for g in got]
        m, se = mean_se(per_sig)
        stats[n] = (per_sig, m, se)
        print(f"  {n:<28}{len(got):>6}{len(fills) / len(got):>7.0%}"
              f"{statistics.median(g[2] for g in got):>7.2f}%"
              f"{statistics.fmean(g[0] for g in fills) if fills else 0:>9.3f}"
              f"{m:>+11.3f}")

    print(f"\n  PAIRED against the deployed entry, on R PER SIGNAL")
    print(f"  (only signals where BOTH entries exist, so the difference is the "
          f"same trade twice)")
    diffs = []
    for n in names:
        if n == DEPLOYED or n not in stats:
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
        print(f"    {n:<28}{md:>+8.3f}  ±{sd:.3f}{z:>+7.1f} SE  ({k} pairs)"
              + ("   BEATS IT" if z >= 2 else ""))
    if diffs:
        best = max(diffs)
        print(f"\n  best is {best[2]} at {best[0]:+.3f} ± {best[1]:.3f}. "
              f"the 42-day run resolved\n  nothing below about 0.11 R; this one "
              f"resolves {2 * best[1]:.3f}.")


if __name__ == "__main__":
    asyncio.run(main())
