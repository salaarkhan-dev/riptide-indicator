"""How much room beyond the raid extreme should the stop have?

`sl_buffer_atr` has been 0.0 since the beginning and has never been swept.
The loser diagnosis says it should be: 25% of losing confirmed trades and 36%
of losing early ones saw price reach the target AFTER stopping them out, and a
quarter to a third die within three bars of filling. Winners also carry WIDER
stops than losers (1.44% against 1.13% on confirmed).

Widening is not free. R is measured in units of risk, so a wider stop shrinks
every win in R terms and costs more in absolute money for the same R. The
question is whether the stop-outs it avoids are worth more than the R it gives
up, and only a sweep answers that.

    PYTHONPATH=. python3 research/studies/stop_buffer.py
"""
import research.env                                     # noqa: F401  MUST be first
import asyncio                                          # noqa: E402

from riptide.config import Cfg, TRACK_TARGET_R          # noqa: E402
from research.data import load                          # noqa: E402
from research.harness import mean_se                    # noqa: E402


async def main():
    print(f"  {'sl_buffer_atr':<16}{'n':>6}{'fill':>7}{'win':>7}{'risk':>8}"
          f"{'R/signal':>10}{'SE':>7}{'total':>9}{'vs 0':>9}")
    base = {}
    for buf in (0.0, 0.1, 0.25, 0.5, 0.75, 1.0):
        rows = await load(cfg=Cfg(sl_buffer_atr=buf), target_r=TRACK_TARGET_R,
                          fee_maker=0.02, fee_taker=0.06)
        for kind in ("confirmed", "early"):
            sub = [r for r in rows if r.kind == kind]
            if not sub:
                continue
            v = [r.r for r in sub]
            fills = [r for r in sub if r.filled]
            wins = [r for r in fills if r.r > 0]
            m, se = mean_se(v)
            risk = sorted(r.risk_pct for r in sub)[len(sub) // 2]
            if buf == 0.0:
                base[kind] = v
            d = ""
            if buf and len(v) == len(base.get(kind, [])):
                dm, ds = mean_se([a - b for a, b in zip(v, base[kind])])
                d = f"{dm:>+9.3f}" + (f" {dm/ds:+.1f}SE" if ds else "")
            elif buf:
                d = f"{m - mean_se(base[kind])[0]:>+9.3f}  (n differs)"
            print(f"  {buf:<6g} {kind:<9}{len(sub):>6}"
                  f"{100*len(fills)/len(sub):>6.0f}%"
                  f"{100*len(wins)/max(len(fills),1):>6.0f}%{risk:>7.2f}%"
                  f"{m:>+10.3f}{se:>7.3f}{sum(v):>+9.1f}{d}")
        print()

asyncio.run(main())
