"""The held-out test for Hour8. One prediction, two fresh datasets, no search.

`riptide_filters.py` found that an Hour8 trend bias sorts Riptide's own setups
better than the shipped Day1: agree-minus-against positive in all four panels
under both conventions, beating Day1 in 4/4 on SuperTrend alone, pooling to
+0.127 and +0.142. Hour4 and Min60 both flipped sign. That was a comparison of
eight arms, so it earns a confirmation and not a deployment.

WHAT IS DELIBERATELY ABSENT

No new intervals. No new conventions. No thresholds, no buckets, no sweep. The
only thing this file can do is agree or disagree with a prediction that was
fixed before it was written — which is the whole reason to run it, and the
reason the previous eleven studies could not settle anything.

TWO HELD-OUT SETS, BOTH UNTOUCHED

  TIME    Twice the candles are fetched and the OLDER half is used — roughly
          days 83 to 166 back. `riptide_filters.py` saw the most recent 83 days
          and nothing in this project has looked further back than that.

  SYMBOL  Ranks 61-120 of the same turnover-ordered universe, on the recent
          window. Riptide scans the top 60 and every study here has used them,
          so these sixty symbols are new to the project entirely.

They test different things and both are reported. A fresh WINDOW asks whether
the effect was a property of one regime. Fresh SYMBOLS ask whether it was a
property of one set of instruments. An effect that is real should survive both;
one that survives only the symbol split is a regime effect wearing a disguise.

THE PREDICTION, FIXED BEFORE THE FIRST NUMBER

    On each held-out set, Hour8's agree-minus-against gap is POSITIVE on both
    timeframes under both conventions — four cells, all positive — AND larger
    than Day1's gap in at least three of the four.

    Both conventions, because the discovery claim was that Hour8 passed under
    both. Choosing the better one now would be best-of-two on a test whose only
    job is to not be a search.

WHAT WOULD REFUTE IT: any negative cell. Shrinkage is expected and is not
failure — the effect was found where it was measured and will be smaller
elsewhere. A sign flip is failure, and it is the thing Hour4 did that put it
out.

Nothing is shipped by this file either way. It reports; the decision is the
user's.

    PYTHONPATH=. python3 research/studies/trend_holdout.py
"""
from __future__ import annotations

import research.env  # noqa: F401  (must precede riptide.config)

import asyncio
import statistics

import aiohttp

from riptide.config import CFG, BAR_SECONDS, TREND_INTERVAL
from riptide.engine import run_engine
from riptide.exchange import list_symbols
from riptide.trend import di_direction, supertrend
from research.harness import mean_se, simulate
from research.studies.mtf_grid import fetch_paged, htf_dir_at
from research.studies.riptide_filters import st_only

SYMBOLS = 60
HORIZON_HOURS, FILL_HOURS = 48, 5
FEE = dict(fee_maker=0.02, fee_taker=0.06)
TARGET_R = 2.0

# Only the incumbent and the candidate. Adding a third would make this a search
# again, and a search is exactly what a held-out test must not be.
ARMS = ("Day1", "Hour8")
CONVS = ("st", "st+di")

# Doubling the pages and taking the older half puts the test on ~days 83-166
# back. riptide_filters.py used the recent 83 days at half these pages.
TIME_TFS = (("Min30", 4), ("Min15", 8))
SYM_TFS = (("Min30", 2), ("Min15", 4))


async def gaps(sess, syms, tf, pages, older_half, cache):
    """agree-minus-against for each (interval, convention), on one dataset."""
    horizon = max(1, HORIZON_HOURS * 3600 // BAR_SECONDS[tf])
    fill_bars = max(1, FILL_HOURS * 3600 // BAR_SECONDS[tf])
    rs = {(h, c): ([], []) for h in ARMS for c in CONVS}
    days, n_set = [], 0

    for sym in syms:
        try:
            cs = await fetch_paged(sess, sym, tf, pages)
            for h in ARMS:
                if (sym, h) not in cache:
                    cache[(sym, h)] = await fetch_paged(sess, sym, h, 1)
        except Exception:
            continue
        if len(cs) < 600:
            continue
        htfs = {h: cache[(sym, h)] for h in ARMS}
        if any(len(v) < 40 for v in htfs.values()):
            continue
        # THE HOLD-OUT ITSELF. The engine runs on the whole series so its
        # warm-up and cluster state are the same as live, and only signals in
        # the older half are SCORED — slicing the candles instead would give
        # the engine a different history from the one it had.
        cut = len(cs) // 2
        lo, hi = (0, cut) if older_half else (cut, len(cs))
        days.append((cs[min(hi, len(cs)) - 1].t - cs[lo].t) / 86400)
        trends = {h: (supertrend(v), di_direction(v)) for h, v in htfs.items()}
        idx = {c.t: i for i, c in enumerate(cs)}
        try:
            setups = run_engine(sym, cs, CFG)
        except Exception:
            continue
        for s in setups:
            i = idx.get(s.detected_time)
            if i is None or not (lo <= i < hi) or i + 1 + horizon > len(cs):
                continue
            if abs(s.entry - s.stop) <= 0 or s.entry <= 0:
                continue
            o = simulate(cs, i, s.entry, s.stop, s.is_long, target_r=TARGET_R,
                         fill_bars=fill_bars, horizon_bars=horizon,
                         fee_pct=0.0, **FEE)
            n_set += 1
            want = 1 if s.is_long else -1
            for h in ARMS:
                st, di = trends[h]
                for conv, d in (("st", st_only(htfs[h], st, di, cs[i].t)),
                                ("st+di", htf_dir_at(htfs[h], st, di,
                                                     cs[i].t))):
                    rs[(h, conv)][0 if d == want else 1].append(o.r)
    out = {}
    for k, (a, b) in rs.items():
        if len(a) < 25 or len(b) < 25:
            out[k] = None
            continue
        (ma, sa), (mb, sb) = mean_se(a), mean_se(b)
        out[k] = (ma - mb, (sa ** 2 + sb ** 2) ** 0.5, ma, mb, len(a), len(b))
    return out, days, n_set


def show(title, res):
    print(f"\n  {title}")
    print(f"  {'interval':<10}{'conv':<8}{'agree':>9}{'against':>9}"
          f"{'gap':>9}{'SE':>7}{'':>6}{'n agree':>9}{'n against':>11}")
    for h in ARMS:
        for c in CONVS:
            v = res.get((h, c))
            if v is None:
                print(f"  {h:<10}{c:<8}   too few")
                continue
            g, se, ma, mb, na, nb = v
            print(f"  {h:<10}{c:<8}{ma:>+9.3f}{mb:>+9.3f}{g:>+9.3f}{se:>7.3f}"
                  f"{g / se if se else 0:>+6.1f}{na:>9}{nb:>11}")


def verdict(name, per_tf):
    """Four cells: two timeframes x two conventions. All positive, and better
    than Day1 in at least three."""
    cells, better = [], 0
    for tf, res in per_tf.items():
        for c in CONVS:
            v, d = res.get(("Hour8", c)), res.get(("Day1", c))
            if v is None or d is None:
                cells.append(None)
                continue
            cells.append(v[0])
            better += v[0] > d[0]
    good = [x for x in cells if x is not None]
    all_pos = len(good) == 4 and all(x > 0 for x in good)
    print(f"\n  {name}: " + "  ".join(f"{x:+.3f}" if x is not None else "n/a"
                                      for x in cells))
    print(f"    all four positive: {all_pos}    beats Day1: {better}/4"
          f"    => {'PASSES' if all_pos and better >= 3 else 'FAILS'}")
    return all_pos and better >= 3


async def main():
    async with aiohttp.ClientSession() as sess:
        allsyms = await list_symbols(sess)
        top = allsyms[:SYMBOLS]
        fresh = allsyms[SYMBOLS:SYMBOLS * 2]
        print("HELD-OUT TEST for Hour8 — one prediction, no new arms")
        print(f"discovery said: all four panels positive, pooled +0.127 (st) "
              f"and +0.142 (st+di), beating the shipped {TREND_INTERVAL}")
        print(f"prediction: four cells positive on each held-out set, and "
              f"better than Day1 in >= 3")

        cache: dict = {}
        print(f"\n{'=' * 96}\n  SET 1 — FRESH WINDOW: the older half of a "
              f"doubled fetch, ~days 83-166 back\n  (the same top "
              f"{len(top)} symbols; nothing here has been scored before)"
              f"\n{'=' * 96}")
        per_tf = {}
        for tf, pages in TIME_TFS:
            res, days, n = await gaps(sess, top, tf, pages, True, cache)
            if not days:
                continue
            per_tf[tf] = res
            show(f"{tf} — {statistics.median(days):.0f} days x {len(days)} "
                 f"symbols, {n} setups", res)
        ok_time = verdict("FRESH WINDOW", per_tf) if per_tf else False

        cache2: dict = {}
        print(f"\n{'=' * 96}\n  SET 2 — FRESH SYMBOLS: ranks "
              f"{SYMBOLS + 1}-{SYMBOLS * 2} by turnover, recent window\n  "
              f"(Riptide scans the top {SYMBOLS}; these sixty are new to the "
              f"project)\n{'=' * 96}")
        per_tf2 = {}
        for tf, pages in SYM_TFS:
            res, days, n = await gaps(sess, fresh, tf, pages, False, cache2)
            if not days:
                continue
            per_tf2[tf] = res
            show(f"{tf} — {statistics.median(days):.0f} days x {len(days)} "
                 f"symbols, {n} setups", res)
        ok_sym = verdict("FRESH SYMBOLS", per_tf2) if per_tf2 else False

        print(f"\n{'=' * 96}\n  BOTH: window {'PASS' if ok_time else 'FAIL'}"
              f"   symbols {'PASS' if ok_sym else 'FAIL'}\n{'=' * 96}")
        if ok_time and ok_sym:
            print("  Hour8 replicated on a window and a symbol set it was not "
                  "found on.")
        elif ok_time or ok_sym:
            print("  Split. One set replicated and the other did not, which is "
                  "weaker than\n  either taken alone would suggest — read the "
                  "failing set as the binding one.")
        else:
            print("  Not replicated. The discovery was best-of-eight after "
                  "all, and Day1 stays.")


if __name__ == "__main__":
    asyncio.run(main())
