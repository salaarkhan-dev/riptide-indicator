"""ARE THE ENTRY-MODEL RESULTS REAL? Two checks before believing any of them.

Run after ms_entry_models.py beside it, and read with it. Its verdict
column says E3_CHOCH PASSES at z ~ 10. This is the script that says not to
believe that, and why.

A  IS THE STOP DEGENERATE? Median risk as a % of price, per model. Stage A of
   the LIT work died of a 0.42% median stop: too tight to survive a gap, so
   losses land far beyond -1R and the mean stops describing the trigger. The
   entry-model prereg held ONE stop rule constant across every model, which is
   constant in definition — but not necessarily in effect, because for some
   triggers the stop level sits adjacent to the entry by construction.

B  IS THE WINNER POSITIONAL? The bet is grouped BY CHoCH cycle, and E3_CHOCH
   enters at bar 0 of its own cycle by definition, while the control enters at
   a random later bar. If the control's R declines with position in the cycle,
   then E3 vs E0 measures "early in a cycle beats late in a cycle" and not the
   trigger at all. That would be circular: the thing being tested defines the
   window it is tested in.

    PYTHONPATH=. RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 indicators/riptide_ms/studies/ms_entry_diag.py
"""

import research.env  # noqa: F401
import asyncio, random, statistics                      # noqa: E402
from collections import defaultdict                     # noqa: E402
import aiohttp                                          # noqa: E402
from research.deep import load_deep                     # noqa: E402
from research.harness import simulate_market            # noqa: E402
import indicators.riptide_ms.port.ms_struct as MS  # noqa: E402
import research.discovery_symbols as RP              # noqa: E402
from riptide.config import BAR_SECONDS                  # noqa: E402
from indicators.riptide_ms.studies.ms_entry_models import (  # noqa: E402
    FEE, MS_LEN, MS_SHORT, TARGET_R, signals, stop_for)

SYMS = RP.DISCOVERY[:14]
HOR = 48


async def main():
    risk = defaultdict(list)
    bydec = defaultdict(list)
    async with aiohttp.ClientSession() as sess:
        for tf in ("Min30", "Min15"):
            horizon = max(1, HOR * 3600 // BAR_SECONDS[tf])
            for sym in SYMS:
                try:
                    cs = await load_deep(sess, sym, tf, days=333)
                except Exception:
                    continue
                if len(cs) < 3000:
                    continue
                n = len(cs)
                ev, st = MS.engine(cs, MS_LEN, MS_SHORT)
                for (model, cyc, d), rows in signals(ev, st, n).items():
                    for bar, entry, stop in rows:
                        if entry and entry > 0:
                            risk[model].append(abs(entry - stop) / entry * 100)

                # B: the control, but recording WHERE in the cycle it entered
                bars = defaultdict(list)
                for i in range(n):
                    bars[st["cyc"][i]].append(i)
                for cyc, idx in bars.items():
                    if len(idx) < 12:
                        continue
                    rng = random.Random(f"diag|{sym}|{tf}|{cyc}")
                    for _ in range(3):
                        i = rng.choice(idx[:-1])
                        d = st["os"][i]
                        e = cs[i].c
                        s = stop_for(d, st["sBtmY"][i], st["sTopY"][i], e)
                        if s is None or i + 1 + horizon > n:
                            continue
                        o = simulate_market(cs, i, e, s, d > 0,
                                            target_r=TARGET_R,
                                            horizon_bars=horizon, **FEE)
                        if o is None or not o.filled:
                            continue
                        pos = (idx.index(i)) / (len(idx) - 1)
                        bydec[min(9, int(pos * 10))].append(o.r)

    print("=" * 74)
    print("  A. MEDIAN RISK AS A % OF PRICE, per model")
    print("=" * 74)
    print(f"  {'model':<14}{'n':>7}{'median':>10}{'p25':>9}{'p75':>9}")
    for m in sorted(risk):
        v = sorted(risk[m])
        if len(v) < 10:
            continue
        q = lambda p: v[int(p * (len(v) - 1))]          # noqa: E731
        print(f"  {m:<14}{len(v):>7}{statistics.median(v):>10.2f}"
              f"{q(.25):>9.2f}{q(.75):>9.2f}")
    print()
    print("  Stage A died at a 0.42% median stop. Anything near that is the")
    print("  same failure: a stop too tight to survive a gap, so losses land")
    print("  far beyond -1R and the mean says nothing about the trigger.")

    print("\n" + "=" * 74)
    print("  B. THE CONTROL'S R BY POSITION IN ITS CYCLE")
    print("=" * 74)
    print(f"  {'decile':<10}{'n':>8}{'mean R':>10}")
    for k in range(10):
        v = bydec[k]
        if len(v) < 20:
            continue
        print(f"  {k/10:<10.1f}{len(v):>8}{statistics.fmean(v):>10.3f}")
    early = [r for k in (0, 1, 2) for r in bydec[k]]
    late = [r for k in (7, 8, 9) for r in bydec[k]]
    if early and late:
        print()
        print(f"  first 30% of a cycle: {statistics.fmean(early):>7.3f} R  "
              f"(n={len(early)})")
        print(f"  last  30% of a cycle: {statistics.fmean(late):>7.3f} R  "
              f"(n={len(late)})")
        print(f"  gap                 : {statistics.fmean(early)-statistics.fmean(late):>7.3f} R")
        print()
        print("  E3_CHOCH enters at position 0.0 of every cycle BY DEFINITION.")
        print("  If that gap is large and positive, E3's delta vs a random")
        print("  bar is measuring the gap, not the trigger.")


asyncio.run(main())
