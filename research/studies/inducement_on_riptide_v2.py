"""INDUCEMENT COUNT vs RIPTIDE'S R — the corrected covariate.

Pre-registered in PREREG_inducement_on_riptide_v2.md, committed before this
ran and before v1's full numbers had printed.

v1 asked "was an inducement taken before the raid" and the control answered
"yes" on 99% of bets, because Riptide's raid IS a pivot being taken. v2 asks
HOW MANY were taken, strictly before the bar that took the pool, and regresses
the bet's R on that count.

Every definition, the population, the scoring, the fees and the window are
imported unchanged from the v1 study. Only the covariate and the statistics
are new.

    PYTHONPATH=. RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/inducement_on_riptide_v2.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import statistics                                       # noqa: E402
import time                                             # noqa: E402
from collections import defaultdict                     # noqa: E402

import aiohttp                                          # noqa: E402

from research.deep import load_deep                     # noqa: E402
from research.harness import simulate                   # noqa: E402
import research.lit_v3 as L                             # noqa: E402
from riptide.config import CFG, BAR_SECONDS             # noqa: E402
from riptide.engine import atr_series, run_engine       # noqa: E402

from research.studies.inducement_on_riptide import (     # noqa: E402
    CONTROL, DEFS, FEE, FILL_HOURS, HIGH, HORIZON_HOURS, LOW, SYMS,
    TARGET_R, TFS, W, ATR_LEN, DAYS, d_equal, d_grab, d_lit, d_pivot,
    d_range, d_retrace, pivot_stream, take_index)

KCAP = 3        # k is capped at 3; fixed by the prereg


def count(idx, side, anchor):
    """How many takes of this side in [anchor - W, anchor) — the raid bar
    itself EXCLUDED, because the raid's own take is what Riptide trades."""
    lo_, hi_ = anchor - W, anchor
    return sum(1 for b in idx[side] if lo_ <= b < hi_)


def slope(rows):
    """OLS of r on min(k, KCAP). rows: (k, r). Returns beta, SE, z, n."""
    if len(rows) < 30:
        return None
    ks = [min(k, KCAP) for k, _r in rows]
    rs = [r for _k, r in rows]
    n = len(ks)
    kb, rb = statistics.fmean(ks), statistics.fmean(rs)
    sxx = sum((k - kb) ** 2 for k in ks)
    if sxx <= 0:
        return None
    sxy = sum((k - kb) * (r - rb) for k, r in zip(ks, rs))
    b = sxy / sxx
    a = rb - b * kb
    sse = sum((r - a - b * k) ** 2 for k, r in zip(ks, rs))
    se = ((sse / (n - 2)) / sxx) ** 0.5 if n > 2 else 0.0
    return dict(b=b, se=se, z=(b / se) if se else 0.0, n=n)


def buckets(rows):
    """Mean R per k bucket, 0 / 1 / 2 / 3+."""
    by = defaultdict(list)
    for k, r in rows:
        by[min(k, KCAP)].append(r)
    return {k: (len(v), statistics.fmean(v)) for k, v in sorted(by.items())}


async def main():
    print("=" * 104)
    print("  INDUCEMENT COUNT vs RIPTIDE'S R   (pre-registered v2)")
    print("=" * 104)
    print(f"  covariate    k = distinct takes of type X, matching side, in "
          f"[raid - {W}, raid) — the raid bar EXCLUDED")
    print(f"  metric       OLS slope of a bet's R on min(k, {KCAP})")
    print(f"  population   Riptide's own setups, real entry and stop, "
          f"target {TARGET_R}R; unit = the bet")
    print(f"  symbols      {len(SYMS)} requested   timeframes "
          f"{', '.join(TFS)}   days {DAYS}")
    print(f"  control      {CONTROL}")
    print("=" * 104)

    panel = defaultdict(lambda: defaultdict(list))     # (tf,half)[defn]=(k,r)
    counts = defaultdict(int)
    t0 = time.time()

    async with aiohttp.ClientSession() as sess:
        for tf in TFS:
            horizon = max(1, HORIZON_HOURS * 3600 // BAR_SECONDS[tf])
            fill_bars = max(1, FILL_HOURS * 3600 // BAR_SECONDS[tf])
            done = 0
            for sym in SYMS:
                try:
                    cs = await load_deep(sess, sym, tf, days=DAYS)
                except Exception:
                    continue
                if len(cs) < 3000:
                    continue
                n = len(cs)
                atr = atr_series(cs, ATR_LEN)
                piv = pivot_stream(cs)
                m, inter, _d, _g = L.engine(cs)
                brk = [e["bar"] for e in inter.events
                       if e["kind"] in ("bos_break", "choch_break")]
                idxs = {
                    "F_PIVOT": take_index(d_pivot(cs, piv), n),
                    "A1_LIT_MAIN": take_index(d_lit(m), n),
                    "A2_LIT_INT": take_index(d_lit(inter), n),
                    "B_RETRACE": take_index(d_retrace(cs, piv, brk), n),
                    "C_EQUAL": take_index(d_equal(cs, piv, atr), n),
                    "D_RANGE": take_index(d_range(cs, piv), n),
                    "E_GRAB": take_index(d_grab(cs, piv), n),
                }
                try:
                    setups = run_engine(sym, cs, CFG)
                except Exception:
                    continue
                at = {c.t: i for i, c in enumerate(cs)}
                cut = n // 2

                bets = defaultdict(list)
                for s in setups:
                    i = at.get(s.detected_time)
                    if i is None or i + 1 + horizon > n:
                        continue
                    if s.entry <= 0 or abs(s.entry - s.stop) <= 0:
                        continue
                    anchor = at.get(s.sweep_time or s.detected_time, i)
                    o = simulate(cs, i, s.entry, s.stop, s.is_long,
                                 target_r=TARGET_R, fill_bars=fill_bars,
                                 horizon_bars=horizon, fee_pct=0.0, **FEE)
                    want = LOW if s.is_long else HIGH
                    bets[s.sweep_time or s.detected_time].append(
                        (o.r, anchor, want))

                for _k, rows in bets.items():
                    r = statistics.fmean(x[0] for x in rows)
                    anchor, want = rows[0][1], rows[0][2]
                    half = "older" if anchor < cut else "newer"
                    counts[(tf, half)] += 1
                    for name in DEFS:
                        panel[(tf, half)][name].append(
                            (count(idxs[name], want, anchor), r))
                done += 1
            print(f"\n  {tf}: {done} symbols, "
                  f"{counts[(tf,'older')] + counts[(tf,'newer')]} bets "
                  f"({time.time()-t0:.0f}s elapsed)")

    res, bks = {}, {}
    for tf in TFS:
        for half in ("older", "newer"):
            rows_all = panel[(tf, half)]
            print("\n" + "=" * 104)
            print(f"  {tf}  {half.upper()} HALF   {counts[(tf, half)]} bets"
                  f"      mean R per k bucket, then the slope")
            print("=" * 104)
            print(f"  {'definition':<14}{'k=0':>16}{'k=1':>16}{'k=2':>16}"
                  f"{'k=3+':>16}{'beta':>9}{'SE':>8}{'z':>7}")
            for name in DEFS:
                rows = rows_all[name]
                b = buckets(rows)
                s = slope(rows)
                res[(tf, half, name)] = s
                bks[(tf, half, name)] = b
                cells = ""
                for k in range(KCAP + 1):
                    if k in b:
                        cnt, mu = b[k]
                        cells += f"{mu:>9.3f}({cnt:<5d}"[:16].ljust(16)
                    else:
                        cells += f"{'—':>16}"
                zs = f"{s['z']:>7.2f}" if s else f"{'—':>7}"
                bs = f"{s['b']:>9.3f}{s['se']:>8.3f}" if s \
                    else f"{'—':>9}{'—':>8}"
                print(f"  {name:<14}{cells}{bs}{zs}")

    print("\n" + "=" * 104)
    print("  VERDICT AGAINST THE FOUR PRE-REGISTERED BARS")
    print("=" * 104)
    print("   1 k takes >=3 values each holding >=5% of bets, every panel")
    print("   2 beta keeps one sign in all four panels")
    print("   3 beta exceeds the control's, same direction, in both halves")
    print("   4 |z| >= 2.0 on the pooled newer half")
    print()
    print(f"  {'definition':<14}{'1 spread':>10}{'2 sign':>9}{'3 ctrl':>9}"
          f"{'4 z':>8}   verdict")
    panels = [(tf, h) for tf in TFS for h in ("older", "newer")]
    for name in DEFS:
        ss = [res.get((tf, h, name)) for tf, h in panels]
        if any(s is None for s in ss):
            print(f"  {name:<14}{'—':>10}{'—':>9}{'—':>9}{'—':>8}   "
                  f"NOT COMPUTABLE")
            continue
        b1 = True
        for tf, h in panels:
            b = bks[(tf, h, name)]
            tot = sum(c for c, _ in b.values())
            if sum(1 for c, _ in b.values() if c >= 0.05 * tot) < 3:
                b1 = False
        betas = [s["b"] for s in ss]
        b2 = all(x > 0 for x in betas) or all(x < 0 for x in betas)
        b3 = True
        for tf, h in panels:
            ctl, cur = res.get((tf, h, CONTROL)), res.get((tf, h, name))
            if not ctl or not cur:
                b3 = False
                continue
            if abs(cur["b"]) <= abs(ctl["b"]) or \
                    (cur["b"] > 0) != (ctl["b"] > 0):
                b3 = False
        pooled = []
        for tf in TFS:
            pooled += panel[(tf, "newer")][name]
        ps = slope(pooled)
        b4 = bool(ps and abs(ps["z"]) >= 2.0)
        if name == CONTROL:
            verdict = "CONTROL — the bar everything else must clear"
        else:
            verdict = "PASSES" if (b1 and b2 and b3 and b4) \
                else "INCONCLUSIVE"
        zs = f"{ps['z']:.2f}" if ps else "—"
        print(f"  {name:<14}{('yes' if b1 else 'NO'):>10}"
              f"{('yes' if b2 else 'NO'):>9}{('yes' if b3 else 'NO'):>9}"
              f"{zs:>8}   {verdict}")

    print()
    print("=" * 104)
    print("  READ")
    print("=" * 104)
    print("  The control is computable this time, so bar 3 means something.")
    print("  In v1 it was reported as satisfied while the control had no")
    print("  variance at all, which made it vacuous — that is corrected here.")
    print()
    print("  A negative beta would say Riptide's setups get WORSE the more")
    print("  minor levels were cleared on the way in, which is the opposite")
    print("  of the usual claim and would be just as useful if it held up.")
    print()
    print("  Per the prereg there is no v3 of this covariate. If nothing")
    print("  passes, the finding is that inducement does not sort Riptide's")
    print("  setups, and any structure layer ships as context with no claim.")


if __name__ == "__main__":
    asyncio.run(main())
