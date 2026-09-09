"""Does the EMA trend filter's LENGTH matter? A ladder, not a point test.

Asked directly: try 21 instead of 50.

THE PRIOR, STATED BEFORE THE RUN

`which_trend.py`, 6,970 signals: the DAILY trend sorts at +4.5 SE (agreeing
+0.056, against −0.083) and **the chart's own trend sorts at +0.002, −0.0 SE**
— a pure null. `useLocalEmaFilter` is the chart's own trend. So the prior is
that its length is a knob on a filter that does nothing, and the honest
expectation is a flat ladder.

That prior is exactly why this is run as a LADDER and not as "21 versus 50".
A two-arm comparison of a null variable has a 50% chance of favouring whichever
arm was asked about, and no way to tell that apart from an effect. Six arms
with a shape to them can.

    off · 9 · 21 · 34 · 50 (shipped) · 100 · 200

THE BAR, FIXED BEFORE THE FIRST NUMBER

    EMA 21 beats EMA 50 on net R in BOTH halves of the window and on BOTH
    timeframes — four panels, same sign.

    Anything less is not a change. A length that wins on one half is the half
    talking, and this project has had that lesson twice.

    Reported alongside: signal COUNT per arm, because a filter that merely
    trades less can look better by variance alone, and n is the first thing to
    check when a shorter EMA "improves" anything.

Everything else is held fixed at what the chart is actually running: market
entry at the confirmation close, 1.5 x ATR(14) stop, 2R target, MEXC fees. Only
`ema_len` moves.

    PYTHONPATH=. python3 research/studies/ema_len.py
"""
from __future__ import annotations

import research.env  # noqa: F401  (must precede riptide.config)

import asyncio
import statistics
from dataclasses import replace

import aiohttp

from riptide.config import BAR_SECONDS
from riptide.engine import atr_series
from riptide.exchange import list_symbols
from research.harness import mean_se, simulate_market
from research.studies.lez import FEE, P, lez_signals
from research.studies.mtf_grid import fetch_paged

TFS = (("Min30", 2), ("Min15", 4))
SYMBOLS = 30
HORIZON_HOURS = 48
STOP_ATR, TARGET_R, ATR_LEN = 1.5, 2.0, 14

# (label, Params). "off" is the control the ladder needs: if no length beats
# switching the filter off, the filter is the null which_trend.py says it is.
ARMS = [("off", replace(P, use_ema=False))] + [
    (f"EMA {n}", replace(P, use_ema=True, ema_len=n))
    for n in (9, 21, 34, 50, 100, 200)]
SHIPPED, ASKED = "EMA 50", "EMA 21"


async def collect(sess, syms, tf, pages):
    horizon = max(1, HORIZON_HOURS * 3600 // BAR_SECONDS[tf])
    out = {(h, lab): [] for h in ("disc", "held") for lab, _ in ARMS}
    days = []
    for sym in syms:
        try:
            cs = await fetch_paged(sess, sym, tf, pages)
        except Exception:
            continue
        if len(cs) < 800:
            continue
        days.append((cs[-1].t - cs[0].t) / 86400)
        atr = atr_series(cs, ATR_LEN)
        cut = len(cs) // 2
        for lab, params in ARMS:
            for x in lez_signals(cs, params):
                a = atr[x.bar]
                if a <= 0 or x.bar + 1 + horizon > len(cs):
                    continue
                entry = x.entry
                d = a * STOP_ATR
                stop = entry - d if x.is_long else entry + d
                if entry <= 0 or stop <= 0:
                    continue
                o = simulate_market(cs, x.bar, entry, stop, x.is_long,
                                    target_r=TARGET_R, horizon_bars=horizon,
                                    **FEE)
                if o is None:
                    continue
                out[("held" if x.bar < cut else "disc", lab)].append(o.r)
    return out, days


def report(tf, out, days):
    span = statistics.median(days) / 2 * len(days) if days else 0
    print(f"\n{'=' * 88}\n{tf}   {statistics.median(days):.0f} days across "
          f"{len(days)} symbols, split in half\n{'=' * 88}")
    print(f"  {'arm':<10}" + "".join(f"{h:>34}" for h in
                                     ("DISCOVERY (newer)", "HELD OUT (older)")))
    print(f"  {'':<10}" + f"{'n':>8}{'/day':>7}{'win':>6}{'R/sig':>8}{'SE':>7}"
          * 2)
    means = {}
    for lab, _ in ARMS:
        line = f"  {lab:<10}"
        for half in ("disc", "held"):
            v = out[(half, lab)]
            if len(v) < 25:
                line += f"{len(v):>8}   too few                "
                means.setdefault(lab, {})[half] = None
                continue
            m, se = mean_se(v)
            means.setdefault(lab, {})[half] = m
            line += (f"{len(v):>8}{len(v) / span if span else 0:>7.2f}"
                     f"{sum(r > 0 for r in v) / len(v):>6.0%}{m:>+8.3f}"
                     f"{se:>7.3f}")
        print(line)
    return means


def verdict(all_means):
    print(f"\n{'=' * 88}\n  THE PRE-REGISTERED BAR: {ASKED} beats {SHIPPED} on "
          f"net R in all four panels\n{'=' * 88}")
    wins, panels = 0, 0
    for tf, means in all_means.items():
        for half in ("disc", "held"):
            a, b = means.get(ASKED, {}).get(half), means.get(SHIPPED, {}).get(half)
            if a is None or b is None:
                print(f"    {tf:<7} {half:<5} incomparable")
                continue
            panels += 1
            wins += a > b
            print(f"    {tf:<7} {half:<5} {ASKED} {a:+.3f}   {SHIPPED} "
                  f"{b:+.3f}   diff {a - b:+.3f}"
                  f"   {'BETTER' if a > b else 'worse'}")
    print(f"\n  => {ASKED} wins {wins} of {panels} panels — "
          f"{'PASSES' if panels == 4 and wins == 4 else 'FAILS'}")

    # The ladder's own shape is the real evidence. A null variable produces a
    # flat ladder with no ordering; a real one produces a gradient.
    print(f"\n  THE LADDER — spread across all seven arms, per panel:")
    for tf, means in all_means.items():
        for half in ("disc", "held"):
            v = [means[l][half] for l, _ in ARMS if means.get(l, {}).get(half)
                 is not None]
            if len(v) < 4:
                continue
            best = max((means[l][half], l) for l, _ in ARMS
                       if means.get(l, {}).get(half) is not None)
            print(f"    {tf:<7} {half:<5} range {min(v):+.3f} to {max(v):+.3f}"
                  f"  (spread {max(v) - min(v):.3f})   best: {best[1]}")
    print("\n  If the best arm is a different length in every panel, the "
          "ladder is flat\n  and the length is a knob on a filter that does "
          "nothing — which is what\n  which_trend.py measured the chart's own "
          "trend to be.")


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = (await list_symbols(sess))[:SYMBOLS]
        print(f"EMA trend-filter length — a ladder\n{len(syms)} symbols · "
              f"market entry at the close, {STOP_ATR:g} x ATR({ATR_LEN}) stop, "
              f"{TARGET_R:g}R target · only ema_len moves")
        all_means = {}
        for tf, pages in TFS:
            out, days = await collect(sess, syms, tf, pages)
            if days:
                all_means[tf] = report(tf, out, days)
        if all_means:
            verdict(all_means)


if __name__ == "__main__":
    asyncio.run(main())
