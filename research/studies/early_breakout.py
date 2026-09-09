"""Sweep + FVG + a trendline BREAKOUT in the same direction. Confluence, not exit.

The last study asked whether the trendline made a better STOP and the answer was
that it makes a free one. This asks the other question, which is untouched: does
a trendline breakout agreeing with an early signal pick out the better early
signals?

This is a genuinely different shape of question from everything else tried on
this population. Every filter tested so far — POI, trend, volume, RSI, ADX,
reclaim, raid depth, grab close — describes the SETUP. This describes something
else that happened on the same chart at roughly the same time and points the
same way. Two independent constructions agreeing is the one kind of confluence
that has not been measured here.

IT IS ALSO THE FIRST TIME THE TWO PRODUCTS MEET. The trendline watch was built
as a heads-up precisely because the break has no edge as a trade
(`trendline_measure.py`: negative on both halves, indistinguishable from random
entry). A thing with no edge alone can still sort a population — that is what a
filter is — so "the break is worthless" does not settle this. But it is a
reason to expect little.

NO LOOKAHEAD, AND THIS IS THE ONE PLACE IT COULD SNEAK IN. A break is only
counted if it fired at or before the early signal's own bar. A break AFTER the
signal is the future, and the fact that it would look wonderful is exactly why
the check is written down rather than assumed. Both series come from closed
bars on the same candles, so "at or before" is the whole guard.

PRE-REGISTERED, BEFORE THE FIRST NUMBER

  PRIMARY   Early signals WITH a same-direction trendline break in the
            preceding `early_max_bars` bars must beat those WITHOUT, on the
            HELD-OUT half, at 2 SE — AND clear the placebo floor below.

  WINDOW    early_max_bars (10) is fixed in advance and is the engine's own
            notion of "recent enough to be the same event": it is the window
            the early signal itself is allowed to form in. Other windows are
            printed as a SENSITIVITY CURVE, not as candidates. Picking the best
            window after seeing the numbers is how a filter gets fitted, and
            this project has a study that reversed sign between halves to prove
            it.

  PLACEBO   A filter that keeps a small fraction of a noisy population wins
            sometimes by construction. So the same fraction is drawn at random,
            25 times, and the MEDIAN of those draws is the floor the real
            filter has to clear. A single random seed is not a floor — an
            earlier study drew +0.112 from one and it was a 1-in-25 draw.

  SECONDARY A break the OTHER way, as a negative filter. If agreement helps,
            disagreement should hurt, and a filter that only works in one
            direction is usually an artefact of how many signals it kept.

  EXPECTATION, recorded so it cannot be revised afterwards: null. Fourteen
  filter families have died on this population. What makes this one worth the
  run is that it is the first that does not describe the setup itself.

    PYTHONPATH=. python3 research/studies/early_breakout.py
"""
import research.env                                     # noqa: F401  MUST be first

import random                                           # noqa: E402
import statistics                                       # noqa: E402

from riptide.config import CFG                          # noqa: E402
from riptide.trendline import trendline_signals         # noqa: E402
from research.data import load_sync                     # noqa: E402
from research.harness import mean_se                    # noqa: E402

WINDOW = CFG.early_max_bars          # 10 — pre-registered, not swept
CURVE = (3, 5, 10, 20, 40)           # sensitivity only
SEEDS = 25
_BREAKS: dict = {}


def breaks(r):
    """(bar, is_long) for every trendline breakout on this symbol, cached."""
    k = id(r.candles)
    if k not in _BREAKS:
        _BREAKS[k] = [(s.bar, s.is_long) for s in trendline_signals(r.candles)]
    return _BREAKS[k]


def since_break(r, same=True):
    """Bars since the most recent break in the matching direction, or None.

    Only breaks at or before the signal bar count. A break after it is the
    future — see the module docstring.
    """
    want = r.signal.is_long if same else (not r.signal.is_long)
    best = None
    for bar, is_long in breaks(r):
        if bar > r.bar or is_long != want:
            continue
        d = r.bar - bar
        if best is None or d < best:
            best = d
    return best


def split(rows, pred):
    a = [r.r for r in rows if pred(r)]
    b = [r.r for r in rows if not pred(r)]
    return a, b


def line(lab, vals):
    if len(vals) < 25:
        return None
    m, se = mean_se(vals)
    wins = sum(1 for v in vals if v > 0) / len(vals)
    print(f"    {lab:<26}{len(vals):>6}{wins:>7.0%}{m:>+10.3f}{se:>7.3f}")
    return m, se


def placebo(rows, keep_n, seeds=SEEDS):
    """Median mean-R of `seeds` random subsets of the same size.

    The floor a real filter has to clear. Keeping a small slice of a noisy
    population produces a flattering number often enough that the number alone
    means nothing.
    """
    vals = [r.r for r in rows]
    if keep_n < 25 or keep_n >= len(vals):
        return None
    out = []
    for s in range(seeds):
        rnd = random.Random(4200 + s)
        out.append(statistics.fmean(rnd.sample(vals, keep_n)))
    return statistics.median(out)


def panel(title, rows):
    print(f"\n{title}   n={len(rows)}")
    print(f"    {'':<26}{'n':>6}{'win':>7}{'R/signal':>10}{'SE':>7}")
    base = line("all signals in this panel", [r.r for r in rows])
    with_, without = split(rows, lambda r: (since_break(r) or 99) <= WINDOW)
    a = line(f"WITH a break <= {WINDOW} bars", with_)
    b = line("without one", without)
    if a and b:
        d, dse = a[0] - b[0], (a[1] ** 2 + b[1] ** 2) ** 0.5
        print(f"    {'difference':<26}{'':>13}{d:>+10.3f}{dse:>7.3f}"
              f"   {d / dse if dse else 0:+.1f} SE")
    if base and len(with_) >= 25:
        f = placebo(rows, len(with_))
        if f is not None:
            print(f"    {'placebo floor (25 seeds)':<26}{len(with_):>6}"
                  f"{'':>7}{f:>+10.3f}")
            if a:
                print(f"    {'vs the floor':<26}{'':>13}"
                      f"{a[0] - f:>+10.3f}")
    opp, _ = split(rows, lambda r: (since_break(r, same=False) or 99) <= WINDOW)
    line(f"break the OTHER way", opp)
    return len(with_)


def curve(rows):
    print(f"\nSENSITIVITY — other windows, NOT candidates. Printed so the "
          f"pre-registered\n  choice can be seen in context rather than "
          f"trusted blind.")
    print(f"  {'window':>8}{'kept':>7}{'% kept':>8}{'R with':>10}"
          f"{'R without':>11}{'diff':>9}{'SE':>7}")
    for w in CURVE:
        a, b = split(rows, lambda r, w=w: (since_break(r) or 99) <= w)
        if len(a) < 25 or len(b) < 25:
            print(f"  {w:>8}{len(a):>7}   too few")
            continue
        ma, sa = mean_se(a)
        mb, sb = mean_se(b)
        d, dse = ma - mb, (sa ** 2 + sb ** 2) ** 0.5
        print(f"  {w:>8}{len(a):>7}{len(a) / len(rows):>7.0%}{ma:>+10.3f}"
              f"{mb:>+11.3f}{d:>+9.3f}{dse:>7.3f}")


def main():
    import asyncio
    import aiohttp
    from riptide.exchange import list_symbols

    async def _syms():
        async with aiohttp.ClientSession() as sess:
            return await list_symbols(sess)
    syms = asyncio.run(_syms()) or None
    everything = load_sync(symbols=syms)
    rows = [r for r in everything if r.kind == "early"]
    confirmed = [r for r in everything if r.kind == "confirmed"]
    print(f"SWEEP + FVG + TRENDLINE BREAKOUT — confluence, not an exit\n"
          f"{len(rows)} early signals · break must fire AT OR BEFORE the "
          f"signal bar\nwindow {WINDOW} bars = CFG.early_max_bars, fixed in "
          f"advance")

    have = sum(1 for r in rows if (since_break(r) or 99) <= WINDOW)
    print(f"\nCOVERAGE  {have}/{len(rows)}  ({have / len(rows):.0%}) of early "
          f"signals had a same-direction\n          break within {WINDOW} bars")

    panel("ALL", rows)
    disc = [r for r in rows if not r.split_window]
    held = [r for r in rows if r.split_window]
    panel("DISCOVERY (newer half)", disc)
    panel("HELD OUT (older half) — this is the pre-registered one", held)
    curve(rows)

    # An INDEPENDENT population, and the cheapest real check available. The
    # confirmed setup is a different signal — it needs the structure shift the
    # early does not — built from the same raid by different rules. If the
    # confluence is a property of the market it should appear here too. If it
    # only exists on early signals it is far more likely to be one of the 3%
    # slices that a noisy population hands out for free.
    print(f"\n{'=' * 68}\nREPLICATION ON CONFIRMED SETUPS — a different "
          f"signal, same filter\n{'=' * 68}")
    if len(confirmed) < 200:
        print("  too few confirmed setups")
    else:
        cov = sum(1 for r in confirmed if (since_break(r) or 99) <= WINDOW)
        print(f"COVERAGE  {cov}/{len(confirmed)}  "
              f"({cov / len(confirmed):.0%})")
        panel("ALL confirmed", confirmed)
        panel("HELD OUT confirmed",
              [r for r in confirmed if r.split_window])

    print(f"\nPRE-REGISTERED: WITH must beat WITHOUT on the HELD-OUT half at "
          f"2 SE\nand clear the placebo floor. Both, not either.")


if __name__ == "__main__":
    main()
