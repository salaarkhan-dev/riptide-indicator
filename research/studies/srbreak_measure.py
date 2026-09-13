"""The SR break against Riptide — because they are OPPOSITE BETS on one event.

THE COLLISION, which is the reason this is worth measuring at all.

Riptide sees price take out a pivot low and reads it as a RAID: the pool got
run, the move is exhausted, look for the reversal — a LONG. This indicator sees
close cross under a pivot low on expanding volume and reads it as a BREAKDOWN:
support gave way, the move continues — a SHORT. Same candle, same level,
opposite conclusion. One of them is wrong on any given bar, and which one is an
empirical question nobody here has asked directly.

IT IS NOT AN OPEN QUESTION IN THE ABSTRACT, EITHER — this project already has
the answer from the other side. `research/studies/context.py` measured
sweep-to-setup conversion against raid volume over 7869 sweeps:

    Q1 quietest raids   26.4% went on to produce a setup
    Q5 loudest raids     6.5%
    monotonic, +15.6 SE

A quiet raid is four times likelier to reverse than a loud one. Volume surging
through a level is a BREAKOUT, not a stop run. Which is precisely this
indicator's premise, arrived at independently, and it is the strongest single
result in this project's file.

So the interesting use is almost certainly NOT a new long/short strategy. It is
a NEGATIVE filter on Riptide: when the SR break says "this level broke, with
volume", that is a reason to distrust the reversal Riptide is about to alert
on. This measures exactly that.

WHY THIS IS NOT JUST THE VOLUME TEST AGAIN. `context.py` also measured raid
volume against R on the SAME early signals and got +0.049, +0.7 SE — nothing.
Conversion and expectancy are different questions and it found a huge effect on
one and none on the other. What is new here is the CONDITION: not "was the raid
loud" but "did close cross a confirmed pivot with an expanding volume
oscillator", which is a different, stricter, and structurally anchored event.
It may well come to the same nothing. It is not the same test.

THREE ARMS

  CONTRADICTING   a clean break the OTHER way within the window. The
                  pre-registered primary: these should score WORSE.
  AGREEING        a clean break the SAME way. Confluence, as asked.
  WICK            the indicator's own "Bull Wick"/"Bear Wick" class — a break
                  whose candle has a tail bigger than its body. The author
                  treats it as a different animal and excludes it from the
                  clean label; whether that split means anything is testable
                  and has never been tested.

PRE-REGISTERED, BEFORE THE FIRST NUMBER

  PRIMARY   Early signals with a CONTRADICTING clean break in the preceding
            `early_max_bars` bars must score WORSE than those without, on the
            HELD-OUT half, at 2 SE, AND clear a 25-seed placebo floor.

  A result in the other direction — contradicted signals scoring BETTER — is a
  FAILED test, not a discovery. The direction is fixed by the +15.6 SE
  conversion result and is not up for reinterpretation afterwards.

  SECONDARY The agreeing arm and the wick arm, plus a standalone score of the
            break as a trade in its own right, for completeness.

  EXPECTATION, recorded so it cannot be revised: the standalone will fail like
  the other four indicators. The contradicting arm is the one with a real prior
  behind it, and it is still more likely null than not — but if anything here
  works, it is that.

    PYTHONPATH=. python3 research/studies/srbreak_measure.py
"""
import research.env                                     # noqa: F401  MUST be first

import random                                           # noqa: E402
import statistics                                       # noqa: E402

from riptide.config import BAR_SECONDS, CFG, INTERVAL   # noqa: E402
from riptide.engine import atr_series                   # noqa: E402
from research.data import load_sync                     # noqa: E402
from research.harness import mean_se, simulate_market   # noqa: E402
from research.studies.srbreak import srbreak_signals    # noqa: E402

WINDOW = CFG.early_max_bars           # 10, same as the trendline study
SEEDS = 25
FEE = dict(fee_maker=0.02, fee_taker=0.06)
_SR: dict = {}


def sr(r):
    k = id(r.candles)
    if k not in _SR:
        _SR[k] = srbreak_signals(r.candles)
    return _SR[k]


def near(r, same: bool, kind: str = "clean"):
    """Bars since the most recent matching break at or before the signal bar."""
    want = r.signal.is_long if same else (not r.signal.is_long)
    best = None
    for b in sr(r):
        if b.bar > r.bar or b.is_long != want or b.kind != kind:
            continue
        d = r.bar - b.bar
        if best is None or d < best:
            best = d
    return best


def has(r, same, kind="clean"):
    d = near(r, same, kind)
    return d is not None and d <= WINDOW


def line(lab, vals):
    if len(vals) < 20:
        print(f"    {lab:<28}{len(vals):>6}   too few")
        return None
    m, se = mean_se(vals)
    w = sum(1 for v in vals if v > 0) / len(vals)
    print(f"    {lab:<28}{len(vals):>6}{w:>7.0%}{m:>+10.3f}{se:>7.3f}")
    return m, se


def placebo(vals, keep_n):
    if keep_n < 20 or keep_n >= len(vals):
        return None
    return statistics.median(
        statistics.fmean(random.Random(770 + s).sample(vals, keep_n))
        for s in range(SEEDS))


def panel(title, rows):
    print(f"\n{title}   n={len(rows)}")
    print(f"    {'':<28}{'n':>6}{'win':>7}{'R/signal':>10}{'SE':>7}")
    allv = [r.r for r in rows]
    base = line("all signals", allv)
    for lab, pred in (
            ("CONTRADICTING clean break", lambda r: has(r, False)),
            ("agreeing clean break", lambda r: has(r, True)),
            ("contradicting WICK", lambda r: has(r, False, "wick")),
            ("agreeing WICK", lambda r: has(r, True, "wick"))):
        hit = [r.r for r in rows if pred(r)]
        miss = [r.r for r in rows if not pred(r)]
        a = line(lab, hit)
        if a and base and len(miss) >= 20:
            mb, sb = mean_se(miss)
            d, dse = a[0] - mb, (a[1] ** 2 + sb ** 2) ** 0.5
            f = placebo(allv, len(hit))
            print(f"    {'  vs the rest':<28}{'':>13}{d:>+10.3f}{dse:>7.3f}"
                  f"   {d / dse if dse else 0:+.1f} SE"
                  + (f"   placebo {f:+.3f}" if f is not None else ""))


def standalone(rows):
    """The break as a trade in its own right: market entry at its close,
    1.5 ATR stop, 2R target, MEXC fees. Same shape every other indicator in
    this file was scored with, so the numbers are comparable."""
    print(f"\n{'=' * 70}\nTHE BREAK AS A TRADE OF ITS OWN — market at the "
          f"close, 1.5 ATR stop, 2R\n{'=' * 70}")
    seen, out = set(), {"clean": [], "wick": []}
    horizon = max(1, 48 * 3600 // BAR_SECONDS[INTERVAL])
    for r in rows:
        k = id(r.candles)
        if k in seen:
            continue
        seen.add(k)
        cs = r.candles
        atr = atr_series(cs, CFG.atr_len)
        for b in sr(r):
            a = atr[b.bar] if b.bar < len(atr) else 0
            if not a or b.bar + horizon >= len(cs):
                continue
            e = cs[b.bar].c
            d = 1.5 * a
            o = simulate_market(cs, b.bar, e, e - d if b.is_long else e + d,
                                b.is_long, target_r=2.0,
                                horizon_bars=horizon, **FEE)
            if o is not None:
                out[b.kind].append(o.r)
    print(f"    {'':<28}{'n':>6}{'win':>7}{'R/signal':>10}{'SE':>7}")
    for k, v in out.items():
        line(k, v)


def main():
    import asyncio
    import aiohttp
    from riptide.exchange import list_symbols

    async def _s():
        async with aiohttp.ClientSession() as sess:
            return await list_symbols(sess)
    syms = asyncio.run(_s()) or None
    everything = load_sync(symbols=syms)
    early = [r for r in everything if r.kind == "early"]
    conf = [r for r in everything if r.kind == "confirmed"]
    print(f"SR BREAK vs RIPTIDE — opposite bets on the same event\n"
          f"{len(early)} early · {len(conf)} confirmed · window {WINDOW} bars"
          f"\nPRE-REGISTERED: a CONTRADICTING clean break must score WORSE. "
          f"Better is a FAIL.")

    n = sum(1 for r in early if has(r, False))
    print(f"\nCOVERAGE  contradicting clean break within {WINDOW} bars: "
          f"{n}/{len(early)} ({n / len(early):.0%})")

    panel("EARLY — all", early)
    panel("EARLY — HELD OUT (older half), the pre-registered one",
          [r for r in early if r.split_window])
    panel("CONFIRMED — all", conf)
    standalone(early)


if __name__ == "__main__":
    main()
