"""Where the strategy actually stands, on the shipped configuration.

Gross first (no fees, no slippage) because that is what was asked, net beside
it because that is what a trade returns.

    PYTHONPATH=. python3 research/studies/standing.py
"""
import research.env                                     # noqa: F401  MUST be first
import asyncio, statistics                              # noqa: E402
from bisect import bisect_right                         # noqa: E402

import aiohttp                                          # noqa: E402
from riptide.config import (BAR_SECONDS, BTC_REGIME_INTERVAL, CFG,  # noqa: E402
                            TRACK_TARGET_R)
from riptide.exchange import fetch_candles              # noqa: E402
from riptide.trend import supertrend                    # noqa: E402
from research.data import load                          # noqa: E402
from research.harness import mean_se                    # noqa: E402

BTC = {}


def stats(rows):
    if not rows:
        return None
    v = [r.r for r in rows]
    fills = [r for r in rows if r.filled]
    wins = [r for r in fills if r.r > 0]
    m, se = mean_se(v)
    return dict(n=len(rows), fill=100 * len(fills) / len(rows),
                win=100 * len(wins) / max(len(fills), 1),
                r=m, se=se, total=sum(v),
                risk=statistics.median([r.risk_pct for r in rows]))


def show(label, g, n_):
    if not g:
        return
    print(f"  {label:<22}{g['n']:>6}{g['fill']:>7.0f}%{g['win']:>7.0f}%"
          f"{g['risk']:>8.2f}%{g['r']:>+9.3f}{g['total']:>+9.1f}"
          f"{n_['r']:>+9.3f}{n_['total']:>+9.1f}")


HDR = (f"  {'':<22}{'n':>6}{'fill':>8}{'win':>7}{'risk':>9}"
       f"{'GROSS R':>9}{'total':>9}{'net R':>9}{'total':>9}")


async def main():
    gross = await load(target_r=TRACK_TARGET_R, fee_pct=0.0)
    net = await load(target_r=TRACK_TARGET_R)
    real = await load(target_r=TRACK_TARGET_R,
                      fee_maker=0.02, fee_taker=0.06)
    async with aiohttp.ClientSession() as s:
        cs = await fetch_candles(s, "BTC_USDT", BTC_REGIME_INTERVAL)
        if len(cs) > 40:
            BTC["x"] = ([c.t for c in cs], supertrend(cs))

    span = (gross[0].candles[-1].t - gross[0].candles[0].t) / 86400
    print(f"Riptide as shipped — Min30, {span:.1f} days, 23 symbols\n"
          f"target {TRACK_TARGET_R:g}R · cap {CFG.max_risk_atr:g} ATR confirmed / "
          f"{CFG.early_max_risk_atr:g} early · break-even off\n"
          f"'win' is the share of FILLED trades that ended positive.\n")
    print(HDR)
    for kind in ("confirmed", "early"):
        show(kind.upper(), stats([r for r in gross if r.kind == kind]),
             stats([r for r in real if r.kind == kind]))
    show("BOTH", stats(gross), stats(real))
    print("\n  same, with the pessimistic flat 0.08% on every trade")
    for kind in ("confirmed", "early"):
        show(kind.upper(), stats([r for r in gross if r.kind == kind]),
             stats([r for r in net if r.kind == kind]))

    print(f"\n  EARLY split by BTC {BTC_REGIME_INTERVAL} agreement")
    print(HDR)
    def agrees(r):
        t, st = BTC["x"]
        j = bisect_right(t, r.candles[r.bar].t - BAR_SECONDS[BTC_REGIME_INTERVAL]) - 1
        return None if not (0 <= j < len(st) and st[j]) else (st[j] > 0) == r.signal.is_long
    for lab, want in (("BTC agrees", True), ("BTC against", False)):
        show(lab, stats([r for r in gross if r.kind == "early" and agrees(r) is want]),
             stats([r for r in real if r.kind == "early" and agrees(r) is want]))

    print("\n  Per symbol, GROSS R per signal (confirmed / early)")
    print(f"  {'symbol':<14}{'conf n':>8}{'conf R':>9}{'conf tot':>10}"
          f"{'early n':>9}{'early R':>9}{'early tot':>11}")
    syms = sorted({r.symbol for r in gross})
    tot = []
    for sym in syms:
        c = stats([r for r in gross if r.symbol == sym and r.kind == "confirmed"])
        e = stats([r for r in gross if r.symbol == sym and r.kind == "early"])
        tot.append((sym, (c["total"] if c else 0) + (e["total"] if e else 0)))
        print(f"  {sym:<14}{(c['n'] if c else 0):>8}"
              f"{(c['r'] if c else 0):>+9.3f}{(c['total'] if c else 0):>+10.1f}"
              f"{(e['n'] if e else 0):>9}{(e['r'] if e else 0):>+9.3f}"
              f"{(e['total'] if e else 0):>+11.1f}")
    tot.sort(key=lambda x: -x[1])
    print(f"\n  best 5:  " + ", ".join(f"{s} {t:+.0f}" for s, t in tot[:5]))
    print(f"  worst 5: " + ", ".join(f"{s} {t:+.0f}" for s, t in tot[-5:]))

asyncio.run(main())
