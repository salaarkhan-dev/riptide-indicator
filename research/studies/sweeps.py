"""Does a sweep inside a daily POI convert better than one outside?

A sweep has no entry and no stop, so it can never be scored as a trade and no
cell in the grade table covers it. But "more chances" is still a measurable
claim, and it means three separate things that are worth keeping apart:

  1  CONVERSION. What fraction of raids go on to produce a confirmed setup —
     sweep, then structure shift, then gap? Most raids never do. If POI raids
     convert more often, the label on the sweep alert is telling you something
     about what is likely to follow.

  2  QUALITY OF WHAT FOLLOWS. Conversion is not the same as profit. A raid
     could convert more often and produce worse setups. So the setups born
     from POI raids are scored against those born from non-POI raids.

  3  DOES IT ADD ANYTHING? The engine already predicts conversion from the
     SHIFT DISTANCE — how far price must travel back for the shift to confirm
     — and that gradient is steep, 37% at 1% away down to 3% beyond 8%. If POI
     raids are simply raids that happen to sit closer to their shift level,
     the POI label adds nothing the existing number does not already say. So
     the two are crossed, which is the only way to tell a real second axis
     from a restatement of the first.

Linking a setup back to its raid uses (anchor_time, sweep_time), the same pair
storage.py uses to build a sweep's dedupe id.
"""
from __future__ import annotations

import research.env  # noqa: F401  (must precede riptide.config)

import asyncio
import statistics
from collections import defaultdict

import aiohttp

from riptide.config import CFG, BAR_SECONDS
from riptide.engine import atr_series, run_engine
from riptide.exchange import list_symbols
from research.harness import mean_se, simulate
from research.studies.mtf_grid import (FEE, FILL_HOURS, HORIZON_HOURS,
                                       fetch_paged, zones_of, in_poi)

HTF = "Day1"
TFS = ("Min30", "Min15")


def dist_pct(w):
    """How far price must travel back for the shift to confirm, from the raid
    extreme. This is the engine's existing conversion predictor."""
    if not w.sweep_extreme:
        return None
    return abs(w.struct_level - w.sweep_extreme) / w.sweep_extreme * 100


async def gather():
    out = []
    async with aiohttp.ClientSession() as sess:
        syms = await list_symbols(sess)
        for sym in syms:
            try:
                hcs = await fetch_paged(sess, sym, HTF, 1)
            except Exception:
                continue
            if len(hcs) < 60:
                continue
            zones = zones_of(hcs, atr_series(hcs, CFG.atr_len))
            for tf in TFS:
                try:
                    cs = await fetch_paged(sess, sym, tf, 1)
                except Exception:
                    continue
                if len(cs) < 300:
                    continue
                step = BAR_SECONDS[tf]
                idx = {c.t: i for i, c in enumerate(cs)}
                early, sw = [], []
                setups = run_engine(sym, cs, CFG, early_out=early, sweeps_out=sw)

                # Which raids produced what. Keyed the way storage.py keys a
                # sweep, so a setup and its originating raid agree.
                conf = {}
                for x in setups:
                    conf.setdefault((x.anchor_time, x.sweep_time), []).append(x)
                earl = defaultdict(list)
                for e in early:
                    earl[(e.anchor_time, e.sweep_time)].append(e)

                for w in sw:
                    key = (w.anchor_time, w.sweep_time)
                    got = conf.get(key, [])
                    rs = []
                    for x in got:
                        i = idx.get(x.detected_time)
                        if i is None:
                            continue
                        o = simulate(cs, i, x.entry, x.stop, x.is_long,
                                     fill_bars=FILL_HOURS * 3600 // step,
                                     horizon_bars=HORIZON_HOURS * 3600 // step,
                                     **FEE)
                        if o.filled and o.exit_bar is None:
                            continue
                        rs.append(o.r)
                    out.append(dict(
                        tf=tf,
                        poi=in_poi(zones, w.sweep_time, w.sweep_extreme,
                                   not w.is_high, BAR_SECONDS[HTF]),
                        dist=dist_pct(w),
                        converted=bool(got),
                        early=bool(earl.get(key)),
                        r=rs))
    return out


def rate(rows, pred=lambda r: True):
    sub = [r for r in rows if pred(r)]
    if not sub:
        return None
    conv = sum(r["converted"] for r in sub)
    earl = sum(r["early"] for r in sub)
    rs = [x for r in sub for x in r["r"]]
    m, se = mean_se(rs) if rs else (0.0, 0.0)
    return len(sub), conv / len(sub), earl / len(sub), m, se, len(rs)


def line(lab, v):
    if v is None or v[0] < 25:
        print(f"  {lab:<34} too few")
        return
    n, c, e, m, se, nr = v
    print(f"  {lab:<34}{n:>7}{c:>10.1%}{e:>10.1%}"
          + (f"{m:>+11.3f} ± {se:.3f}  (n={nr})" if nr >= 25 else "         —"))


def main():
    rows = asyncio.run(gather())
    print(f"\n{len(rows)} sweeps\n")
    hdr = f"  {'':<34}{'sweeps':>7}{'-> setup':>10}{'-> early':>10}" \
          f"{'R of the setups':>20}"

    print("=" * 84)
    print("1. CONVERSION — does a POI raid become a setup more often?")
    print("=" * 84)
    print(hdr)
    line("all sweeps", rate(rows))
    line("outside a daily POI", rate(rows, lambda r: not r["poi"]))
    line("inside a daily POI", rate(rows, lambda r: r["poi"]))
    for tf in TFS:
        print(f"\n  -- {tf} --")
        line("outside a POI", rate(rows, lambda r, t=tf: r["tf"] == t and not r["poi"]))
        line("inside a POI", rate(rows, lambda r, t=tf: r["tf"] == t and r["poi"]))

    print("\n" + "=" * 84)
    print("2. CROSSED WITH SHIFT DISTANCE — is the POI a second axis, or the")
    print("   same one wearing a different name?")
    print("=" * 84)
    print(hdr)
    bands = ((0, 1.0, "under 1% away"), (1.0, 2.0, "1-2% away"),
             (2.0, 4.0, "2-4% away"), (4.0, 8.0, "4-8% away"),
             (8.0, 1e9, "over 8% away"))
    for lo, hi, lab in bands:
        for poi in (False, True):
            v = rate(rows, lambda r, l=lo, h=hi, p=poi:
                     r["dist"] is not None and l <= r["dist"] < h
                     and r["poi"] == p)
            line(f"{lab:<16}{'in POI' if poi else 'no POI'}", v)
        print()

    d_in = [r["dist"] for r in rows if r["poi"] and r["dist"] is not None]
    d_out = [r["dist"] for r in rows if not r["poi"] and r["dist"] is not None]
    if d_in and d_out:
        print(f"  median shift distance: in a POI "
              f"{statistics.median(d_in):.2f}%, outside "
              f"{statistics.median(d_out):.2f}%")
        print("  If those are close, the two axes are measuring different\n"
              "  things and the POI label is worth its place on the alert.")


if __name__ == "__main__":
    main()
