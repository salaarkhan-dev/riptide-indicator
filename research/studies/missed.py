"""What policy G gives up, and how loud sweep alerts would be.

TWO QUESTIONS, BOTH ABOUT VOLUME RATHER THAN EDGE

  1  Policy G sends only signals inside a daily POI. That is a third of what
     the bot used to send, and "the rest was worse" is true but not the whole
     story: some of the suppressed cells measure POSITIVE. This prints exactly
     which alerts stop arriving, how many a day that is, and what their
     measured R was, so the trade is a number rather than a slogan.

  2  Sweep heads-ups were never in the policy simulation. They are not trades
     — no entry, no stop, nothing to score — so no cell in the table covers
     them, and gating them on the POI was a decision made by the code rather
     than by a measurement. This counts how many arrive per day under each
     option so the choice is made on the real rate.

Both are reported per day at the CURRENT universe size, not at the 23 symbols
the cell table was measured on, because the honest question is how many
messages a phone receives.
"""
from __future__ import annotations

import research.env  # noqa: F401  (must precede riptide.config)

import asyncio
import statistics
from collections import defaultdict

import aiohttp

from riptide.config import CFG, BAR_SECONDS, SWEEP_FRESH_BARS
from riptide.engine import atr_series, run_engine
from riptide.exchange import list_symbols
from riptide.trend import supertrend, di_direction
from research.harness import mean_se, simulate
from research.studies.mtf_grid import (FEE, FILL_HOURS, HORIZON_HOURS,
                                       fetch_paged, zones_of, in_poi,
                                       htf_dir_at)

HTF = "Day1"
TFS = ("Min30", "Min15")


async def gather(symbols):
    rows, sweeps, days = [], [], []
    async with aiohttp.ClientSession() as sess:
        for sym in symbols:
            try:
                hcs = await fetch_paged(sess, sym, HTF, 1)
            except Exception:
                continue
            if len(hcs) < 60:
                continue
            zones = zones_of(hcs, atr_series(hcs, CFG.atr_len))
            hst, hdi = supertrend(hcs), di_direction(hcs)
            for tf in TFS:
                try:
                    cs = await fetch_paged(sess, sym, tf, 1)
                except Exception:
                    continue
                if len(cs) < 300:
                    continue
                step = BAR_SECONDS[tf]
                if tf == TFS[0]:
                    days.append((cs[-1].t - cs[0].t) / 86400)
                idx = {c.t: i for i, c in enumerate(cs)}
                early, sw = [], []
                setups = run_engine(sym, cs, CFG, early_out=early,
                                    sweeps_out=sw)
                for w in sw:
                    sweeps.append((tf, in_poi(zones, w.sweep_time,
                                              w.sweep_extreme, not w.is_high,
                                              BAR_SECONDS[HTF])))
                for kind, sigs in (("confirmed", setups), ("early", early)):
                    for x in sigs:
                        i = idx.get(x.detected_time)
                        if i is None:
                            continue
                        o = simulate(cs, i, x.entry, x.stop, x.is_long,
                                     fill_bars=FILL_HOURS * 3600 // step,
                                     horizon_bars=HORIZON_HOURS * 3600 // step,
                                     **FEE)
                        if o.filled and o.exit_bar is None:
                            continue
                        rows.append((tf, kind,
                                     in_poi(zones, cs[i].t, x.stop, x.is_long,
                                            BAR_SECONDS[HTF]),
                                     htf_dir_at(hcs, hst, hdi, cs[i].t)
                                     == (1 if x.is_long else -1), o.r))
    return rows, sweeps, (statistics.median(days) if days else 41.0)


def main():
    syms = asyncio.run(_syms())
    rows, sweeps, span = asyncio.run(gather(syms))
    n = len(syms)
    print(f"\n{len(rows)} signals and {len(sweeps)} sweeps over {span:.0f} days "
          f"on {n} symbols, both timeframes")

    print("\n" + "=" * 76)
    print("WHAT POLICY G STOPS SENDING  (everything outside a daily POI)")
    print("=" * 76)
    print(f"  {'timeframe':<9}{'kind':<11}{'trend':<7}{'n':>6}{'per day':>9}"
          f"{'R/signal':>18}{'total R':>10}")
    keep = drop = 0.0
    kn = dn = 0
    for tf in TFS:
        for kind in ("confirmed", "early"):
            for tr in (True, False):
                sub = [r[4] for r in rows if r[0] == tf and r[1] == kind
                       and not r[2] and r[3] == tr]
                if not sub:
                    continue
                m, se = mean_se(sub)
                drop += sum(sub)
                dn += len(sub)
                print(f"  {tf:<9}{kind:<11}{'yes' if tr else 'no':<7}"
                      f"{len(sub):>6}{len(sub) / span:>9.1f}"
                      f"{m:>+11.3f} ± {se:.3f}{sum(sub):>+10.1f}")
    for r in rows:
        if r[2]:
            keep += r[4]
            kn += 1
    print(f"\n  suppressed {dn} signals ({dn / span:.1f}/day) worth "
          f"{drop:+.1f} R in total")
    print(f"  kept       {kn} signals ({kn / span:.1f}/day) worth "
          f"{keep:+.1f} R in total")
    print(f"  so G trades {drop:+.1f} R of volume for a book that is "
          f"{kn / max(dn + kn, 1):.0%} the size")
    print("  Total R falls. R PER SIGNAL rises. That is the whole trade, and it\n"
          "  is only right while a position slot is the scarce thing.")

    print("\n  the suppressed cells that measured POSITIVE — the real cost:")
    for tf in TFS:
        for kind in ("confirmed", "early"):
            for tr in (True, False):
                sub = [r[4] for r in rows if r[0] == tf and r[1] == kind
                       and not r[2] and r[3] == tr]
                if len(sub) < 25 or mean_se(sub)[0] <= 0.05:
                    continue
                m, _ = mean_se(sub)
                print(f"    {tf} {kind}, trend {'agrees' if tr else 'against'}"
                      f": {len(sub)} signals at {m:+.3f} "
                      f"({len(sub) / span:.1f}/day)")

    print("\n" + "=" * 76)
    print("SWEEP HEADS-UPS  (not trades — no cell in the table covers them)")
    print("=" * 76)
    by = defaultdict(int)
    for tf, poi in sweeps:
        by[(tf, poi)] += 1
    opts = (("every sweep, both timeframes", lambda tf, p: True),
            ("every sweep, 30m only", lambda tf, p: tf == "Min30"),
            ("in a daily POI, both tf", lambda tf, p: p),
            ("in a daily POI, 30m only", lambda tf, p: p and tf == "Min30"))
    for lab, f in opts:
        c = sum(v for (tf, p), v in by.items() if f(tf, p))
        print(f"  {lab:<32}{c:>6} total{c / span:>9.1f}/day")
    print(f"\n  Only sweeps on the last {SWEEP_FRESH_BARS} bars are ever sent, "
          f"and\n  duplicates on one bar collapse, so the live rate is at or "
          f"below these.")


async def _syms():
    async with aiohttp.ClientSession() as s:
        return await list_symbols(s)


if __name__ == "__main__":
    main()
