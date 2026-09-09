"""The author's own three filters: sweep distance, candle range, Strong Reclaim.

From the indicator's author, replying to a user asking how to raise the win
rate: *"You can try increasing the Minimum Sweep Distance, increasing the
Minimum Candle Range, keeping the EMA Trend Filter enabled, using Strong
Reclaim instead of Close Back Inside, and requiring bullish/bearish
confirmation bodies."*

Of the five, the EMA is already measured and is a null (`ema_len.py`: seven
lengths, best arm a different length in every panel, whole ladder inside 1.5
SE), and the confirmation bodies are already ON by default. The other three
have never been touched here and are the subject of this file.

    minSweepDistanceAtr   0.10 shipped  ->  how far past the level price ran
    minCandleRangeAtr     0.20 shipped  ->  how big the sweep candle is
    reclaimRule           Close Back Inside -> Strong Reclaim also demands the
                          close beat the candle's own midpoint

The author is right that these will raise the win rate and cut the signal
count, and right again that "a higher win rate does not always mean a better
system" — `winrate.py` measured exactly that. So the win rate is reported and
is NOT what anything is judged on.

THE BAR, AND WHY IT IS DIFFERENT THIS TIME

Three studies in this sequence used "beats the baseline", and every one of them
was too weak, because the baseline is NEGATIVE and beating it only means losing
less. That is recorded in MEASUREMENTS.md three times. So:

    PRIMARY   The winning cell must be POSITIVE on the HELD-OUT half.
              Not better than base. Positive.

    Selection is made on the discovery half alone — highest R per signal among
    cells with n >= 150 — and that ONE cell gets one shot at the older half,
    which nothing in this study has looked at.

THE NOISE FLOOR, MEASURED WITH A PLACEBO FILTER

Forty cells will produce a good-looking one out of noise. The control here
cannot be a random ENTRY, because these filters do not change the entry — they
change which signals survive. So the placebo is a filter that keeps the same
FRACTION of signals at random. For every real cell, a placebo cell accepting
the identical share is scored, and the best of the forty placebos is what
"best of forty filters that cut this much" is worth when the filtering is known
to be meaningless.

A real cell that does not beat its placebo grid has found nothing, however
pretty its win rate.

    PYTHONPATH=. python3 research/studies/lez_strict.py
"""
from __future__ import annotations

import research.env  # noqa: F401  (must precede riptide.config)

import asyncio
import random
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
MIN_N = 150

SWEEPS = (0.10, 0.25, 0.50, 0.75, 1.00)      # 0.10 ships
RANGES = (0.20, 0.50, 0.80, 1.20)            # 0.20 ships
RECLAIMS = ((False, "close-inside"), (True, "STRONG"))
SHIPPED = (0.10, 0.20, False)


def cells():
    for sw in SWEEPS:
        for rg in RANGES:
            for st, lab in RECLAIMS:
                yield (sw, rg, st), f"sweep {sw:.2f} · range {rg:.2f} · {lab}"


async def collect(sess, syms, tf, pages):
    """For every cell, the outcome of every signal it admits.

    Outcomes are cached per (bar, direction): the three filters change WHICH
    signals fire, never the entry, the stop or the target, so the same bar
    scores identically in every cell that admits it. Forty cells is then forty
    filtered views of one set of simulations rather than forty backtests.
    """
    horizon = max(1, HORIZON_HOURS * 3600 // BAR_SECONDS[tf])
    out = {(h, k): [] for h in ("disc", "held") for k, _ in cells()}
    days = []

    for n, sym in enumerate(syms):
        try:
            cs = await fetch_paged(sess, sym, tf, pages)
        except Exception:
            continue
        if len(cs) < 800:
            continue
        days.append((cs[-1].t - cs[0].t) / 86400)
        atr = atr_series(cs, ATR_LEN)
        cut = len(cs) // 2
        cache: dict = {}

        def outcome(bar, is_long):
            key = (bar, is_long)
            if key not in cache:
                a = atr[bar]
                if a <= 0 or bar + 1 + horizon > len(cs):
                    cache[key] = None
                else:
                    entry = cs[bar].c
                    d = a * STOP_ATR
                    stop = entry - d if is_long else entry + d
                    cache[key] = (None if entry <= 0 or stop <= 0 else
                                  simulate_market(cs, bar, entry, stop, is_long,
                                                  target_r=TARGET_R,
                                                  horizon_bars=horizon, **FEE))
            return cache[key]

        for (sw, rg, st), _ in cells():
            p = replace(P, min_sweep_atr=sw, min_range_atr=rg,
                        strong_reclaim=st)
            for x in lez_signals(cs, p):
                o = outcome(x.bar, x.is_long)
                if o is None:
                    continue
                out[("held" if x.bar < cut else "disc", (sw, rg, st))].append(o.r)
    return out, days


def placebo_floor(base_rs, keeps, seeds=25):
    """The best of forty filters that keep the same fractions AT RANDOM.

    Each real cell admits some share of the base signals. A placebo cell keeps
    that same share by coin toss. Whatever the best placebo scores is what
    best-of-forty is worth when the filtering carries no information — and any
    real cell at or below it has found nothing.

    REPEATED OVER MANY SEEDS, and that is not fussiness. One draw of
    best-of-forty is itself a random variable: the first version of this used a
    single seed and returned +0.112, which is about 3 SE above the population
    mean and roughly a 1-in-25 outcome. Reporting it as "the floor" would have
    been quoting one lucky sample as a constant — the same error the whole
    control exists to prevent. The median across seeds is the floor; the max is
    printed beside it so the tail is visible rather than hidden.
    """
    out = []
    for sd in range(seeds):
        rnd = random.Random(1000 + sd)
        best = -9.9
        for k, frac in keeps.items():
            if frac <= 0:
                continue
            v = [r for r in base_rs if rnd.random() < frac]
            if len(v) < MIN_N:
                continue
            best = max(best, mean_se(v)[0])
        if best > -9.0:
            out.append(best)
    if not out:
        return None, None
    return statistics.median(out), max(out)


HEAD = (f"  {'cell':<34}{'n':>6}{'kept':>7}{'/day':>7}{'win':>6}"
        f"{'R/signal':>10}{'SE':>7}")


def line(lab, v, base_n, span):
    m, se = mean_se(v)
    print(f"  {lab:<34}{len(v):>6}{len(v) / base_n if base_n else 0:>7.0%}"
          f"{len(v) / span if span else 0:>7.2f}"
          f"{sum(r > 0 for r in v) / len(v):>6.0%}{m:>+10.3f}{se:>7.3f}")
    return m


def ladder(out, half, span, base_n):
    """One knob at a time, from the shipped defaults. The readable part."""
    print(f"\n  ONE KNOB AT A TIME ({half}), from the shipped "
          f"{SHIPPED[0]:.2f}/{SHIPPED[1]:.2f}/close-inside")
    print(HEAD)
    for lab, keys in (
            ("sweep distance", [((s, SHIPPED[1], SHIPPED[2]),
                                 f"  sweep {s:.2f} ATR") for s in SWEEPS]),
            ("candle range", [((SHIPPED[0], r, SHIPPED[2]),
                               f"  range {r:.2f} ATR") for r in RANGES]),
            ("reclaim rule", [((SHIPPED[0], SHIPPED[1], s),
                               f"  {l}") for s, l in RECLAIMS])):
        print(f"   -- {lab} --")
        for k, name in keys:
            v = out[(half, k)]
            if len(v) < 25:
                print(f"  {name:<34}{len(v):>6}   too few")
                continue
            line(name, v, base_n, span)


def report(tf, out, days):
    span = statistics.median(days) / 2 * len(days) if days else 0
    print(f"\n{'=' * 92}\n{tf}   {statistics.median(days):.0f} days across "
          f"{len(days)} symbols, split in half\n{'=' * 92}")
    base_n = {h: len(out[(h, SHIPPED)]) for h in ("disc", "held")}
    for h in ("disc", "held"):
        ladder(out, h, span, base_n[h])

    scored = []
    keeps = {}
    for k, lab in cells():
        v = out[("disc", k)]
        keeps[k] = len(v) / base_n["disc"] if base_n["disc"] else 0
        if len(v) >= MIN_N:
            scored.append((mean_se(v)[0], k, lab, len(v)))
    scored.sort(reverse=True)
    print(f"\n  THE GRID on the discovery half — {len(scored)} cells with "
          f"n >= {MIN_N}, best 8")
    print(HEAD)
    for m, k, lab, n in scored[:8]:
        line(lab, out[("disc", k)], base_n["disc"], span)

    floor, worst = placebo_floor(out[("disc", SHIPPED)], keeps)
    print(f"\n  PLACEBO FLOOR — the same 40 filters, keeping the same shares "
          f"AT RANDOM, over 25 seeds:")
    print(f"    median best-of-40 placebo  {floor:+.3f}"
          f"        worst case seen  {worst:+.3f}")
    print(f"    the shipped cell itself is "
          f"{mean_se(out[('disc', SHIPPED)])[0]:+.3f} on "
          f"{len(out[('disc', SHIPPED)])} signals")

    if not scored:
        print("\n  no cell reaches the minimum count")
        return
    m, k, lab, n = scored[0]
    print(f"\n  WINNER by the pre-declared rule (highest R on discovery, "
          f"n >= {MIN_N}):\n    {lab}   {m:+.3f} on {n} signals")
    if floor is not None and m <= floor:
        print(f"    ^ does NOT clear the placebo floor of {floor:+.3f}. A "
              f"filter cutting the same share AT RANDOM does as well.")

    v = out[("held", k)]
    print(f"\n  HELD OUT — the older half, one cell, one shot")
    if len(v) < 25:
        print(f"    n={len(v)}: too few to read")
        return
    hm, hse = mean_se(v)
    print(f"    n={len(v)}   kept {len(v) / base_n['held']:.0%}   "
          f"win {sum(r > 0 for r in v) / len(v):.0%}   "
          f"R/signal {hm:+.3f} ± {hse:.3f}")
    print(f"    shipped defaults on the same half: "
          f"{mean_se(out[('held', SHIPPED)])[0]:+.3f}")
    print(f"    => {'PASSES' if hm > 0 else 'FAILS'} — the bar was POSITIVE on "
          f"the held-out half, not merely better than base")


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = (await list_symbols(sess))[:SYMBOLS]
        print(f"The author's three filters — sweep distance, candle range, "
              f"Strong Reclaim\n{len(syms)} symbols · "
              f"{len(list(cells()))} cells · market entry at the close, "
              f"{STOP_ATR:g} x ATR({ATR_LEN}) stop, {TARGET_R:g}R target")
        for tf, pages in TFS:
            out, days = await collect(sess, syms, tf, pages)
            if days:
                report(tf, out, days)


if __name__ == "__main__":
    asyncio.run(main())
