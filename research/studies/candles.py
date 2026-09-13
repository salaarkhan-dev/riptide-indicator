"""Reversal candlestick patterns at the raid, and at the signal bar.

    PYTHONPATH=. python3 research/studies/candles.py
"""
import research.env                                     # noqa: F401  MUST be first
import asyncio                                          # noqa: E402

from research.data import load                          # noqa: E402
from research.harness import report, risk_terciles      # noqa: E402
from research.patterns import PATTERNS, any_pattern     # noqa: E402


def grab_bar(r):
    idx = {c.t: i for i, c in enumerate(r.candles)}
    return idx.get(getattr(r.signal, "grab_time", 0) or r.signal.sweep_time, r.bar)


def at(fn, where):
    def f(r):
        i = grab_bar(r) if where == "raid" else r.bar
        return fn(r.candles, i, r.signal.is_long) if i >= 2 else None
    return f


def window(fn):
    """Anywhere from the raid bar to the signal bar — the 'zone area'."""
    def f(r):
        g = grab_bar(r)
        return any(fn(r.candles, i, r.signal.is_long)
                   for i in range(max(g, 2), r.bar + 1))
    return f


async def main():
    rows = await load(fee_maker=0.02, fee_taker=0.06)
    for kind in ("confirmed", "early"):
        sub = [r for r in rows if r.kind == kind]
        print(f"\n{'='*64}\n{kind.upper()}  n={len(sub)}\n{'='*64}")
        for name, fn in PATTERNS.items():
            report(f"{name} — on the RAID bar", sub, at(fn, "raid"),
                   control=risk_terciles)
        for name, fn in PATTERNS.items():
            report(f"{name} — anywhere raid→signal", sub, window(fn),
                   control=risk_terciles)
        report("ANY reversal pattern — on the RAID bar", sub,
               at(any_pattern, "raid"), control=risk_terciles)
        report("ANY reversal pattern — anywhere raid→signal", sub,
               window(any_pattern), control=risk_terciles)

asyncio.run(main())
