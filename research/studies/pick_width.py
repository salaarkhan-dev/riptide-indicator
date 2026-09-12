"""POST-HOC: what do the picks look like by how wide the stop actually is?

Not pre-registered. Answers one practical question — a 10.51% stop arrived as
a 🎯 and the measured 'wide' bucket is everything over 2.6%, which may be
nothing like 10%. A bucket's average cannot speak for its tail.
"""
import research.env  # noqa: F401
import asyncio, statistics                               # noqa: E402
import aiohttp                                           # noqa: E402
from riptide.config import BAR_SECONDS                   # noqa: E402
from research.deep import load_universe                  # noqa: E402
from research.studies.poi_tf import DAY, DAYS, H8, collect, context, universe  # noqa: E402
from research.studies.report import drawdown             # noqa: E402
from research.studies.survivor import symbol_bootstrap   # noqa: E402
from research.studies.band_key import COOLDOWN, KEYS, pick_rolling, pct  # noqa: E402
from research.studies.pick_rule import TFS               # noqa: E402

BUCKETS = [(0, 1.2, "tight   <1.2%"), (1.2, 2.6, "normal  1.2-2.6%"),
           (2.6, 4.0, "wide    2.6-4%"), (4.0, 6.0, "wide    4-6%"),
           (6.0, 10.0, "wide    6-10%"), (10.0, 999, "wide    10%+")]

async def main():
    by_tf = {}
    async with aiohttp.ClientSession() as sess:
        syms = await universe(sess)
        zday = await context(sess, syms, DAY); z8h = await context(sess, syms, H8)
        for tf in TFS:
            cs = await load_universe(sess, syms, tf, DAYS,
                min_bars=int(0.8*DAYS*86400//BAR_SECONDS[tf]))
            by_tf[tf] = [t for t in await collect(sess, cs, zday, z8h, interval=tf)
                         if t.filled and t.exit_t is not None]
    rows = [t for tf in TFS for t in by_tf[tf] if t.day]
    pick = pick_rolling(rows, KEYS["A  tf > band > confd  (shipped)"], COOLDOWN)
    print(f"{len(pick)} picks. stop width: median {statistics.median(t.risk_pct for t in pick):.2f}%"
          f"  90th {pct(sorted(t.risk_pct for t in pick),0.90):.2f}%"
          f"  99th {pct(sorted(t.risk_pct for t in pick),0.99):.2f}%"
          f"  max {max(t.risk_pct for t in pick):.2f}%")
    print(f"\n  {'bucket':<20}{'n':>6}{'% of picks':>12}{'win':>7}{'R/trade':>10}"
          f"{'boot 5th':>11}{'boot 95th':>11}{'needs move':>12}")
    for lo, hi, name in BUCKETS:
        g = [t for t in pick if lo <= t.risk_pct < hi]
        if not g:
            print(f"  {name:<20}{0:>6}"); continue
        rs = [t.r for t in g]
        m = sum(rs)/len(rs)
        w = sum(1 for r in rs if r > 0)/len(rs)
        med_move = 2*statistics.median(t.risk_pct for t in g)
        if len(g) >= 40:
            b = symbol_bootstrap(g)
            lo5, hi95 = (pct(b,0.05), pct(b,0.95)) if b else (0,0)
            bs = f"{lo5:>+11.3f}{hi95:>+11.3f}"
        else:
            bs = f"{'too thin':>22}"
        print(f"  {name:<20}{len(g):>6}{100*len(g)/len(pick):>11.1f}%{w:>7.0%}"
              f"{m:>+10.3f}{bs}{med_move:>11.1f}%")
    # and the same for everything SENT, for context
    print(f"\n  the same buckets across every alert sent ({len(rows)}):")
    for lo, hi, name in BUCKETS:
        g = [t for t in rows if lo <= t.risk_pct < hi]
        if len(g) < 40:
            print(f"  {name:<20}{len(g):>6}  too thin"); continue
        rs = [t.r for t in g]
        print(f"  {name:<20}{len(g):>6}{100*len(g)/len(rows):>11.1f}%"
              f"{sum(1 for r in rs if r>0)/len(rs):>7.0%}{sum(rs)/len(rs):>+10.3f}")
asyncio.run(main())
