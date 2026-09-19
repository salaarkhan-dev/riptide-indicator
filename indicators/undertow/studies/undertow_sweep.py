"""Undertow parameter study. Runs exactly what prereg/PREREG_undertow_params.md
pre-registered, and nothing else.

    PYTHONPATH=. python3 indicators/undertow/studies/undertow_sweep.py
    PYTHONPATH=. python3 indicators/undertow/studies/undertow_sweep.py Min30
    PYTHONPATH=. python3 indicators/undertow/studies/undertow_sweep.py --fetch

THE SHAPE, and it is the whole point:

    TRAIN      even-indexed symbols, OLDER half of their bars.  48 configs run.
    pick       the best mean R per trade on TRAIN. One config per timeframe.
    HOLDOUT    odd-indexed symbols, NEWER half.  That one config, scored once.
    control    seeded random entries matched on symbol, direction, risk, rr and
               holding window. Same counts, so the SEs compare.

The two quadrants that are neither train nor holdout are never scored. The
holdout is scored once. The train number is printed only to show what selection
bought, and it is not evidence of anything -- with 48 configs the expected
maximum under the null is about 2.4 SE above zero.

DATA. 12,000 bars per symbol per timeframe, by paging the kline endpoint
backwards, cached under .cache/ (gitignored). `--fetch` refreshes; without it a
cached run is offline and takes seconds.

This is a STUDY, not a check. deploy/preflight.py never runs it: it costs a data
feed and several minutes, and a measurement is not a gate.
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import pathlib
import random
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

from indicators.undertow.port import undertow as U          # noqa: E402
from research.data import SYMBOLS                           # noqa: E402
from riptide.config import BAR_SECONDS, BASE                # noqa: E402
from riptide.engine import Candle                           # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[3]
CACHE = ROOT / ".cache" / "undertow"
TFS = ("Min15", "Min30", "Min60")
BARS = 12000
FEE = 0.0007
SEED = 20260917

# ── THE GRID, exactly as pre-registered. 4 x 3 x 2 x 2 = 48. ────────────────
SWINGS = (dict(swingSrc=U.SW_BAR, msLen=15, msShortLen=3),
          dict(swingSrc=U.SW_BAR, msLen=30, msShortLen=5),
          dict(swingSrc=U.SW_RANGE, swingK=0.25, swingKMinor=0.08),
          dict(swingSrc=U.SW_RANGE, swingK=0.40, swingKMinor=0.12))
END_MINOR = (U.E_OFF, U.E_FLIP, U.E_OPPOSED)
HTF = (0, 4)
RRS = (2.0, 3.0)


def grid():
    for sw in SWINGS:
        for em in END_MINOR:
            for h in HTF:
                for rr in RRS:
                    # endSweep/endStale were True when UNDERTOW_PARAMS.md
                    # was run and are False now; pinned so the page still
                    # reproduces. See test_studies_pin_their_settings.py.
                    yield U.P(pinAt=U.PIN_PULL, pinLag=0, biasGate=U.BG_TRADEABLE, famStrict=False, armWins=False, stopSrc=U.S_PULL, useBackup=False, pinNewest=False, famPriority=False, failTest=U.T_CLOSE, biasSrc=U.BS_STRUCT, endMinor=em, htfMult=h, rr=rr, feeFrac=FEE,
                              confirmOrder=U.C_EITHER,
                              endSweep=True, endStale=True, **sw)


# ───────────────────────────────────────────────────────────────── data ──


async def _page(sess, sym, tf, bars):
    """Backwards through the kline endpoint, 2000 rows at a time.

    The endpoint caps a response at ~2000 bars, which is 21 days on 15m -- not a
    population. It does honour an arbitrary start/end, so this walks back.
    """
    from riptide.exchange import get_json
    step = BAR_SECONDS[tf]
    end = int(time.time())
    seen: dict[int, tuple] = {}
    while len(seen) < bars:
        d = await get_json(sess, f"{BASE}/api/v1/contract/kline/{sym}",
                           {"interval": tf, "start": end - 2000 * step,
                            "end": end})
        k = (d or {}).get("data") or {}
        ts = k.get("time") or []
        if not ts:
            break
        for t, o, h, l, c, v in zip(ts, k["open"], k["high"], k["low"],
                                    k["close"], k.get("vol") or [0] * len(ts)):
            seen[int(t)] = (float(o), float(h), float(l), float(c), float(v))
        nxt = min(ts) - step
        if nxt >= end:               # the endpoint stopped going back
            break
        end = nxt
        await asyncio.sleep(0.12)    # not a rate limit we own; be polite
    now = int(time.time())
    return [Candle(t, *seen[t]) for t in sorted(seen) if t + step <= now]


async def _fetch_all(symbols=None):
    import aiohttp
    CACHE.mkdir(parents=True, exist_ok=True)
    async with aiohttp.ClientSession() as sess:
        for tf in TFS:
            for sym in (symbols or SYMBOLS):
                f = CACHE / f"{sym}-{tf}.json"
                try:
                    cs = await _page(sess, sym, tf, BARS)
                except Exception as e:
                    print(f"  {sym:14} {tf:6} FAILED {e}")
                    continue
                if len(cs) < 500:
                    print(f"  {sym:14} {tf:6} only {len(cs)} bars, skipped")
                    continue
                f.write_text(json.dumps([[c.t, c.o, c.h, c.l, c.c, c.v]
                                         for c in cs]))
                span = (cs[-1].t - cs[0].t) / 86400
                print(f"  {sym:14} {tf:6} {len(cs):6} bars  {span:6.1f} days")


def load(tf, symbols=None) -> dict:
    out = {}
    for sym in (symbols or SYMBOLS):
        f = CACHE / f"{sym}-{tf}.json"
        if f.exists():
            out[sym] = [Candle(*r) for r in json.loads(f.read_text())]
    return out


# ────────────────────────────────────────────────────── split and score ──


def quadrant(cs, older: bool):
    """The older or newer half of one symbol's bars.

    The halves OVERLAP BY A WARMUP on the newer side only: the structure engine
    needs history before its first CHoCH means anything, and starting the newer
    half cold would score its opening weeks against a bias that had not formed.
    The warmup bars are fed to the engine and no trade from them is counted --
    `skip` below is what enforces that.
    """
    mid = len(cs) // 2
    if older:
        return cs[:mid], 0
    warm = min(600, mid)
    return cs[mid - warm:], warm


def run_split(tf, symbols, p, older):
    """Every trade from one quadrant, as a flat list plus the funnel."""
    data = LOADED[tf]
    agg = U.Result()
    for sym in symbols:
        cs = data.get(sym)
        if not cs or len(cs) < 1200:
            continue
        seg, skip = quadrant(cs, older)
        r = U.run(seg, p, sym)
        r.trades = [t for t in r.trades if t.fillBar >= skip]
        agg.add(r)
    return agg


def clustered(trades, key=lambda t: t.symbol):
    """Mean R and a clustered SE. One symbol's trades are not independent of
    each other, so the cluster is the symbol and the SE is over cluster sums --
    which is what stops 400 trades from three symbols reading as 400 draws."""
    if not trades:
        return 0.0, 0.0, 0
    n = len(trades)
    mean = sum(t.r for t in trades) / n
    groups: dict = {}
    for t in trades:
        groups.setdefault(key(t), []).append(t.r)
    if len(groups) < 2:
        return mean, float("inf"), n
    # Clustered SE of the mean: var of the sum of (r - mean) within a cluster.
    tot = sum((sum(v) - mean * len(v)) ** 2 for v in groups.values())
    g = len(groups)
    se = math.sqrt(tot * g / (g - 1)) / n
    return mean, se, n


def control(trades, tf, symbols, older, p, seed=SEED):
    """One seeded random entry per real trade, matched as the prereg says.

    Same symbol, same quadrant, same direction, same risk in price, same rr,
    same maximum holding window. Resolved with the same rules -- stop first when
    one bar spans both -- so the only difference is WHEN it entered.
    """
    rnd = random.Random(seed)
    data = LOADED[tf]
    out = []
    for t in trades:
        cs = data.get(t.symbol)
        if not cs:
            continue
        seg, skip = quadrant(cs, older)
        hold = max(1, t.exitBar - t.fillBar)
        lo, hi = skip, len(seg) - hold - 2
        if hi <= lo:
            continue
        i = rnd.randint(lo, hi)
        entry = seg[i].c
        risk = abs(t.stop - t.entry)
        if risk <= 0:
            continue
        stop = entry + risk if t.short else entry - risk
        tgt = entry - p.rr * risk if t.short else entry + p.rr * risk
        r = None
        for j in range(i + 1, min(i + 1 + hold, len(seg))):
            b = seg[j]
            lost = b.h >= stop if t.short else b.l <= stop
            won = b.l <= tgt if t.short else b.h >= tgt
            if lost:
                r = -1.0
                break
            if won:
                r = p.rr
                break
        if r is None:
            # Unresolved inside the same window the real trade had. Marked to
            # market, which is the only reading that does not quietly discard
            # the control's losers.
            b = seg[min(i + hold, len(seg) - 1)]
            r = ((entry - b.c) if t.short else (b.c - entry)) / risk
        out.append(U.Trade(symbol=t.symbol, r=r - FEE * entry / risk))
    return out


# ───────────────────────────────────────────────────────────── the run ──


LOADED: dict = {}


def bars_verdict(tf, p, hold, ctl):
    """The six pre-registered bars, on the holdout. No bar is negotiable here;
    they were written down before the data was touched."""
    m, se, n = clustered(hold)
    cm, cse, _ = clustered(ctl)
    z = m / se if se > 0 else 0.0
    dse = math.sqrt(se ** 2 + cse ** 2) if (se and cse) else float("inf")
    lines = []
    b1 = n >= 150
    b2 = m > 0
    b3 = z >= 2.0
    b4 = dse > 0 and (m - cm) >= dse
    lines.append(f"  1 COVERAGE       {n} closed trades          "
                 f"{'PASS' if b1 else 'FAIL — UNDERPOWERED, read as a bound'}")
    lines.append(f"  2 POSITIVE       {m:+.3f} R per trade        "
                 f"{'PASS' if b2 else 'FAIL'}")
    lines.append(f"  3 SIGNIFICANCE   z = {z:+.2f} clustered      "
                 f"{'PASS' if b3 else 'FAIL'}")
    lines.append(f"  4 BEATS CONTROL  {m:+.3f} vs {cm:+.3f}, "
                 f"diff {m - cm:+.3f} +/- {dse:.3f}   "
                 f"{'PASS' if b4 else 'FAIL'}")
    # bar 6 here; bar 5 is across timeframes and is decided by the caller
    worst = max({t.symbol for t in hold},
                key=lambda s: sum(t.r for t in hold if t.symbol == s),
                default=None)
    rest = [t for t in hold if t.symbol != worst]
    rm = sum(t.r for t in rest) / len(rest) if rest else 0.0
    b6 = rm > 0
    lines.append(f"  6 NOT ONE SYMBOL without {worst}: {rm:+.3f} R over "
                 f"{len(rest)}   {'PASS' if b6 else 'FAIL'}")
    return [b1, b2, b3, b4, b6], lines, (m, se, n, cm)


def one_tf(tf):
    evens = [s for i, s in enumerate(SYMBOLS) if i % 2 == 0]
    odds = [s for i, s in enumerate(SYMBOLS) if i % 2 == 1]
    have = set(LOADED[tf])
    evens = [s for s in evens if s in have]
    odds = [s for s in odds if s in have]
    print(f"\n{'=' * 78}\n{tf}   train {len(evens)} symbols / older half   "
          f"holdout {len(odds)} symbols / newer half\n{'=' * 78}")

    rows = []
    for p in grid():
        r = run_split(tf, evens, p, older=True)
        m, se, n = clustered(r.real)
        rows.append((m, se, n, p, r))
    rows.sort(key=lambda x: -x[0])

    print("\nTRAIN — 48 configs. THIS TABLE IS NOT EVIDENCE: with 48 draws the")
    print("expected maximum under the null is ~2.4 SE above zero. It exists")
    print("only to select one configuration.\n")
    print(f"  {'mean R':>8} {'+/-':>6} {'n':>5}  config")
    for m, se, n, p, _ in rows[:8]:
        print(f"  {m:+8.3f} {se:6.3f} {n:5}  {p.tag()}")
    print("  ...")
    for m, se, n, p, _ in rows[-2:]:
        print(f"  {m:+8.3f} {se:6.3f} {n:5}  {p.tag()}")

    eligible = [r for r in rows if r[2] >= 60]
    if not eligible:
        print("\nno TRAIN config reached 60 trades; nothing to carry over.")
        return None
    m0, se0, n0, p, tr = eligible[0]
    print(f"\nCARRIED OVER: {p.tag()}")
    print(f"  train {m0:+.3f} R +/- {se0:.3f} over {n0} trades   "
          f"(ghosts {tr.gateCost:+.1f}R over {len(tr.ghosts)})")

    hr = run_split(tf, odds, p, older=False)
    ctl = control(hr.real, tf, odds, False, p)
    passed, lines, stats = bars_verdict(tf, p, hr.real, ctl)
    print("\nHOLDOUT — scored once.\n")
    for l in lines:
        print(l)
    m, se, n, cm = stats
    print(f"\n  shrinkage      train {m0:+.3f}  ->  holdout {m:+.3f}   "
          f"({m - m0:+.3f})")
    gm, gse, gn = clustered(hr.ghosts)
    if gn:
        print(f"  the bias gate  cancelled {hr.nMissBias} armed setups; the "
              f"{gn} that would have filled are worth {gm:+.3f} R each "
              f"({'COST' if gm > 0 else 'SAVED'} {abs(sum(t.r for t in hr.ghosts)):.1f}R)")
        print(f"                 by rule: minor {hr.nEndMinor} · sweep "
              f"{hr.nEndSweep} · stale {hr.nEndStale} · retrace {hr.nEndRetr} "
              f"· adx {hr.nEndAdx}")
    return dict(tf=tf, p=p, train=m0, hold=m, se=se, n=n, ctl=cm,
                passed=passed)


def main():
    argv = sys.argv[1:]
    if "--fetch" in argv:
        print(f"fetching {BARS} bars x {len(SYMBOLS)} symbols x {len(TFS)} "
              f"timeframes into {CACHE.relative_to(ROOT)}/")
        asyncio.run(_fetch_all())
        argv = [a for a in argv if a != "--fetch"]
    # THE SECOND UNIVERSE. research/symbols_fresh.py, 45 crypto perps disjoint
    # from these 23. It is not fetched by --fetch, because nothing in this file
    # scores it -- it exists so a NEW question gets a holdout that eight
    # previous studies have not already looked at.
    if "--fetch-fresh" in argv:
        from research.symbols_fresh import SYMBOLS_FRESH, assert_disjoint
        assert_disjoint()
        print(f"fetching {BARS} bars x {len(SYMBOLS_FRESH)} FRESH symbols x "
              f"{len(TFS)} timeframes into {CACHE.relative_to(ROOT)}/")
        asyncio.run(_fetch_all(SYMBOLS_FRESH))
        argv = [a for a in argv if a != "--fetch-fresh"]
    if "--fetch-fresh2" in argv:
        from research.symbols_fresh import SYMBOLS_FRESH2, assert_disjoint
        assert_disjoint()
        print(f"fetching {BARS} bars x {len(SYMBOLS_FRESH2)} FRESH-2 symbols x "
              f"{len(TFS)} timeframes into {CACHE.relative_to(ROOT)}/")
        asyncio.run(_fetch_all(SYMBOLS_FRESH2))
        argv = [a for a in argv if a != "--fetch-fresh2"]
    if "--fetch-fresh3" in argv:
        from research.symbols_fresh import SYMBOLS_FRESH3, assert_disjoint
        assert_disjoint()
        print(f"fetching {BARS} bars x {len(SYMBOLS_FRESH3)} FRESH-3 symbols x "
              f"{len(TFS)} timeframes into {CACHE.relative_to(ROOT)}/")
        asyncio.run(_fetch_all(SYMBOLS_FRESH3))
        argv = [a for a in argv if a != "--fetch-fresh3"]
    if "--fetch-fresh4" in argv:
        from research.symbols_fresh import SYMBOLS_FRESH4, assert_disjoint
        assert_disjoint()
        print(f"fetching {BARS} bars x {len(SYMBOLS_FRESH4)} FRESH-4 symbols x "
              f"{len(TFS)} timeframes into {CACHE.relative_to(ROOT)}/")
        asyncio.run(_fetch_all(SYMBOLS_FRESH4))
        argv = [a for a in argv if a != "--fetch-fresh4"]
    if "--fetch-fresh5" in argv:
        from research.symbols_fresh import SYMBOLS_FRESH5, assert_disjoint
        assert_disjoint()
        print(f"fetching {BARS} bars x {len(SYMBOLS_FRESH5)} FRESH-5 symbols x "
              f"{len(TFS)} timeframes into {CACHE.relative_to(ROOT)}/")
        asyncio.run(_fetch_all(SYMBOLS_FRESH5))
        argv = [a for a in argv if a != "--fetch-fresh5"]
    if "--fetch-fresh6" in argv:
        from research.symbols_fresh import SYMBOLS_FRESH6, assert_disjoint
        assert_disjoint()
        print(f"fetching {BARS} bars x {len(SYMBOLS_FRESH6)} FRESH-6 symbols x "
              f"{len(TFS)} timeframes into {CACHE.relative_to(ROOT)}/")
        asyncio.run(_fetch_all(SYMBOLS_FRESH6))
        argv = [a for a in argv if a != "--fetch-fresh6"]
    if "--fetch-fresh7" in argv:
        from research.symbols_fresh import SYMBOLS_FRESH7, assert_disjoint
        assert_disjoint()
        print(f"fetching {BARS} bars x {len(SYMBOLS_FRESH7)} FRESH-7 symbols x "
              f"{len(TFS)} timeframes into {CACHE.relative_to(ROOT)}/")
        asyncio.run(_fetch_all(SYMBOLS_FRESH7))
        argv = [a for a in argv if a != "--fetch-fresh7"]
    if "--fetch-fresh8" in argv:
        from research.symbols_fresh import SYMBOLS_FRESH8, assert_disjoint
        assert_disjoint()
        print(f"fetching {BARS} bars x {len(SYMBOLS_FRESH8)} FRESH-8 symbols x "
              f"{len(TFS)} timeframes into {CACHE.relative_to(ROOT)}/")
        asyncio.run(_fetch_all(SYMBOLS_FRESH8))
        argv = [a for a in argv if a != "--fetch-fresh8"]
    if "--fetch-fresh9" in argv:
        from research.symbols_fresh import SYMBOLS_FRESH9, assert_disjoint
        assert_disjoint()
        print(f"fetching {BARS} bars x {len(SYMBOLS_FRESH9)} FRESH-9 symbols x "
              f"{len(TFS)} timeframes into {CACHE.relative_to(ROOT)}/")
        asyncio.run(_fetch_all(SYMBOLS_FRESH9))
        argv = [a for a in argv if a != "--fetch-fresh9"]
    if "--fetch-fresh10" in argv:
        from research.symbols_fresh import SYMBOLS_FRESH10, assert_disjoint
        assert_disjoint()
        print(f"fetching {BARS} bars x {len(SYMBOLS_FRESH10)} FRESH-10 x "
              f"{len(TFS)} timeframes into {CACHE.relative_to(ROOT)}/")
        asyncio.run(_fetch_all(SYMBOLS_FRESH10))
        argv = [a for a in argv if a != "--fetch-fresh10"]
    if "--fetch-fresh11" in argv:
        from research.symbols_fresh import SYMBOLS_FRESH11, assert_disjoint
        assert_disjoint()
        print(f"fetching {BARS} bars x {len(SYMBOLS_FRESH11)} FRESH-11 x "
              f"{len(TFS)} timeframes into {CACHE.relative_to(ROOT)}/")
        asyncio.run(_fetch_all(SYMBOLS_FRESH11))
        argv = [a for a in argv if a != "--fetch-fresh11"]
    if "--fetch-fresh12" in argv:
        from research.symbols_fresh import SYMBOLS_FRESH12, assert_disjoint
        assert_disjoint()
        print(f"fetching {BARS} bars x {len(SYMBOLS_FRESH12)} FRESH-12 x "
              f"{len(TFS)} timeframes into {CACHE.relative_to(ROOT)}/")
        asyncio.run(_fetch_all(SYMBOLS_FRESH12))
        argv = [a for a in argv if a != "--fetch-fresh12"]
    tfs = [a for a in argv if a in TFS] or list(TFS)

    for tf in tfs:
        LOADED[tf] = load(tf)
        if not LOADED[tf]:
            print(f"{tf}: no cached candles. Run with --fetch first.")
            return 2

    print("UNDERTOW PARAMETER STUDY")
    print("prereg: indicators/undertow/prereg/PREREG_undertow_params.md")
    print(f"fees {FEE * 1e4:.0f}bp round trip, seed {SEED}")

    out = [one_tf(tf) for tf in tfs]
    out = [o for o in out if o]
    print(f"\n{'=' * 78}\nVERDICT\n{'=' * 78}\n")
    print(f"  {'tf':7} {'train':>8} {'holdout':>8} {'control':>8} {'n':>5}  bars")
    for o in out:
        marks = "".join("P" if b else "." for b in o["passed"])
        print(f"  {o['tf']:7} {o['train']:+8.3f} {o['hold']:+8.3f} "
              f"{o['ctl']:+8.3f} {o['n']:5}  {marks}")
    pos = [o for o in out if o["hold"] > 0]
    b5 = len(pos) >= 2
    print(f"\n  5 NOT ONE TIMEFRAME  {len(pos)} of {len(out)} holdouts "
          f"positive   {'PASS' if b5 else 'FAIL'}")
    allpass = [o for o in out if all(o["passed"]) and b5]
    print()
    if allpass:
        print("  CLEARS EVERY PRE-REGISTERED BAR on: "
              + ", ".join(o["tf"] for o in allpass))
        print("  That earns a forward-tracking run. It does not earn a "
              "deployment,\n  and it does not earn a second pass over this "
              "holdout.")
    else:
        print("  NOTHING CLEARS ALL SIX BARS.")
        print("  Per the prereg: Undertow stays a research bench. No alert, no")
        print("  watcher module. The result goes in INDICATOR.md beside the")
        print("  other two negatives, and this holdout is now spent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
