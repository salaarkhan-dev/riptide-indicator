"""What a higher win rate COSTS, on Riptide's own signals.

THE GOAL IS MORE WINS AND FEWER STOP-OUTS. This project has two ways to chase
that and only one of them has ever worked.

  FILTER THEM OUT BEFORE THE FACT — twenty-one attempts recorded in
  MEASUREMENTS.md, plus six more in this session (trendline slope, SR break,
  RSI divergence, BTC regime, MTF agreement, pool memory). One survivor in
  twenty-seven: the daily POI. Three of this session's six produced a large
  standard error on pooled data that REVERSED on the held-out half. The base
  rate for this approach is now known and it is dreadful.

  CHANGE THE EXIT — and here the losers' own anatomy says something specific
  that no filter can. From `losers.py`:

      never got into profit          0%
      peaked under 0.5R             36% confirmed / 38% early
      peaked 0.5 - 1R               35% / 35%
      peaked 1 - 1.5R               17% / 17%
      peaked past 1.5R and lost     11% / 9%

  NOT ONE LOSER FAILED TO GO GREEN FIRST. Around 28% of them reached a full 1R
  before dying, and 64% reached 0.5R. Those are not bad entries that a filter
  could have caught — they are trades that worked and then stopped working.
  A filter cannot reach them. An exit can.

WHY THIS IS NOT A NEW IDEA, AND WHY IT IS STILL WORTH RUNNING. `stops.py`
already measured a partial and found it buys a large win-rate gain almost free
— 33% to 50% win, 66% to 50% full stop-outs, for 0.007 R. But that was measured
on LEZ, a strategy this project later discarded. It has never been run on
Riptide's own signals, and NO PARTIAL IS DEPLOYED ANYWHERE IN THE BOT.

WIN RATE AND MONEY ARE DIFFERENT THINGS AND THIS REPORTS BOTH. `winrate.py`
already established that the win rate is mostly a dial the target sets: moving
the target from 1.5R to 4R takes it from 40% to 19% while R moves 0.015. So a
rule that raises the win rate has to be priced, not celebrated. The primary
output here is therefore not "which variant wins" but:

    HOW MANY R DOES ONE POINT OF WIN RATE COST?

PRE-REGISTERED, BEFORE THE FIRST NUMBER

  Every variant is reported on the same trades: win rate, full stop-out rate,
  and net R, on both halves. No variant is recommended on the discovery half
  alone.

  A variant is worth deploying if it raises the win rate materially AND its
  net-R cost is inside 1 SE of the plain rule on the HELD-OUT half. That is a
  deliberately different bar from every other study here: this is buying a
  property, not finding an edge, and the question is the price.

  EXPECTATION: the partial raises the win rate a lot and costs a little;
  break-even raises nothing and costs more, because a break-even exit scores
  0.0 and `r > 0` does not count it as a win. Both are recorded so they cannot
  be revised afterwards.

    PYTHONPATH=. python3 research/studies/win_rate_price.py
"""
import research.env                                     # noqa: F401  MUST be first

import statistics                                       # noqa: E402

from riptide.config import TRACK_TARGET_R               # noqa: E402
from research.data import load_sync                     # noqa: E402
from research.harness import mean_se, simulate          # noqa: E402

TGT = TRACK_TARGET_R

# Every variant scored on the SAME signals. `part_at_r` banks half the position
# at that level and moves the stop to `be_lock_r`; the remainder runs to
# `part_to_r`.
VARIANTS = (
    ("plain, target 2R", {}),
    ("half at 0.5R, rest 2R", dict(part_at_r=0.5, part_to_r=TGT,
                                   be_lock_r=0.0)),
    ("half at 1R, rest 2R", dict(part_at_r=1.0, part_to_r=TGT,
                                 be_lock_r=0.0)),
    ("half at 1R, rest 3R", dict(part_at_r=1.0, part_to_r=3.0,
                                 be_lock_r=0.0)),
    ("half at 1R, stop to +0.2R", dict(part_at_r=1.0, part_to_r=TGT,
                                       be_lock_r=0.2)),
    ("break-even at 1R", dict(be_arm_r=1.0, be_lock_r=0.0)),
    ("break-even at 1.5R", dict(be_arm_r=1.5, be_lock_r=0.0)),
)


def score(rows, opts):
    out = []
    for r in rows:
        o = simulate(r.candles, r.bar, r.signal.entry, r.signal.stop,
                     r.signal.is_long, target_r=TGT, **opts)
        if o.exit_bar is None and o.filled:
            continue
        if o.filled:
            out.append(o)
    return out


def panel(title, rows):
    print(f"\n{title}   n={len(rows)}")
    print(f"  {'':<26}{'filled':>7}{'win':>7}{'full SL':>9}{'R/signal':>10}"
          f"{'SE':>7}{'vs plain':>10}{'R per win pt':>14}")
    base = None
    for lab, opts in VARIANTS:
        os_ = score(rows, opts)
        if len(os_) < 30:
            print(f"  {lab:<26}{len(os_):>7}   too few")
            continue
        rs = [o.r for o in os_]
        m, se = mean_se(rs)
        win = sum(1 for o in os_ if o.r > 0) / len(os_)
        # A FULL stop-out, not any stop: after a partial the remainder can stop
        # at a profit, and counting that as a loss would flatter the rule that
        # created it.
        full = sum(1 for o in os_ if o.exit == "stop" and o.r < -0.5) / len(os_)
        if base is None:
            base = (m, se, win)
            print(f"  {lab:<26}{len(os_):>7}{win:>7.0%}{full:>9.0%}"
                  f"{m:>+10.3f}{se:>7.3f}")
            continue
        d = m - base[0]
        dwin = 100 * (win - base[2])
        # The number the whole study exists to produce.
        price = (-d / dwin) if dwin > 0.5 else float("nan")
        print(f"  {lab:<26}{len(os_):>7}{win:>7.0%}{full:>9.0%}"
              f"{m:>+10.3f}{se:>7.3f}{d:>+10.3f}"
              + (f"{price:>14.4f}" if price == price else f"{'—':>14}"))
    return base


def main():
    import asyncio
    import aiohttp
    from riptide.exchange import list_symbols

    async def _s():
        async with aiohttp.ClientSession() as sess:
            return await list_symbols(sess)
    syms = asyncio.run(_s()) or None
    every = load_sync(symbols=syms)
    early = [r for r in every if r.kind == "early"]
    conf = [r for r in every if r.kind == "confirmed"]
    print(f"WHAT A HIGHER WIN RATE COSTS — Riptide's own signals, target "
          f"{TGT:g}R\n{len(early)} early · {len(conf)} confirmed\n"
          f"'R per win pt' = net R given up for each percentage point of win "
          f"rate bought.\nLower is cheaper. Negative would mean free, which "
          f"would be suspicious.")

    for name, rows in (("EARLY", early), ("CONFIRMED", conf)):
        panel(f"{name} — all", rows)
        panel(f"{name} — HELD OUT (older half)",
              [r for r in rows if r.split_window])

    # The anatomy that motivates all of it, recomputed here rather than quoted,
    # so the argument and the numbers come from one pass.
    print(f"\nWHY AN EXIT AND NOT A FILTER — how far losers got before dying")
    for name, rows in (("early", early), ("confirmed", conf)):
        os_ = [o for o in score(rows, {}) if o.r < 0]
        if not os_:
            continue
        mfe = [o.mfe for o in os_]
        print(f"  {name:<11}{len(os_):>5} losers   "
              f"never green {sum(1 for x in mfe if x <= 0) / len(mfe):.0%}   "
              f"reached 0.5R {sum(1 for x in mfe if x >= 0.5) / len(mfe):.0%}"
              f"   reached 1R {sum(1 for x in mfe if x >= 1.0) / len(mfe):.0%}"
              f"   median peak {statistics.median(mfe):.2f}R")


if __name__ == "__main__":
    main()
