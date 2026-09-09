"""Three untested ideas in one pass: BTC regime, MTF agreement, pool memory.

Collected together because they share a corpus and nothing else. Running them
in one load is a third of the fetching; keeping their pre-registrations separate
is what stops that from becoming a fishing trip. Each has its own bar and each
is judged alone — three tests, not one test with three chances.

3. BTC 30m REGIME — a 3.6 SE result that has never been used

   `context.py` found BTC's 30m trend AGAINST the trade worth +0.174 at 3.6 SE,
   monotone, surviving all four splits and the risk-tercile control, and taking
   early signals from -0.033 to +0.045. It was flagged CANDIDATE and then
   nothing happened — plausibly because the BTC sign bug landed in the middle
   of it and every reading had to be re-derived. `btc_dir` is recorded on every
   signal and printed on every alert, and it gates nothing and grades nothing.

   PRE-REGISTERED: BTC 30m AGAINST the trade must beat BTC WITH it, on the
   HELD-OUT half, at 2 SE. The direction is fixed by the earlier finding and a
   result the other way is a failure, not a rediscovery.

4. INTERNAL MTF AGREEMENT — the same engine, twice

   Riptide scans Min30 and Min15. When one symbol fires the same direction on
   both within a short window, that is two confirmations from a construction
   already calibrated — unlike the four borrowed indicators, which all failed.
   Never measured.

   PRE-REGISTERED: Min30 signals with a same-direction Min15 signal inside the
   window must beat those without, HELD OUT, at 2 SE, above a placebo floor.

5. POOL MEMORY — is the second raid of a level different from the first?

   The engine expires a cluster once raided, and nobody has asked whether a
   level being taken for the SECOND time behaves differently. Folk wisdom says
   a defended level weakens with each test. `pivots` — how many swings formed
   the pool — is already recorded and already printed on the alert, and has
   never been tested against R either.

   PRE-REGISTERED: R must differ across raid-count buckets, HELD OUT, at 2 SE,
   monotone. `pivots` is reported beside it as a second, independent reading of
   the same "how well-used is this level" idea.

   EXPECTATION for all three: null. Two of them are re-readings of things
   already recorded and never looked at, which is the cheapest kind of test
   worth running and also the kind most likely to have been left alone because
   there is nothing there.

    PYTHONPATH=. python3 research/studies/three_ideas.py
"""
import research.env                                     # noqa: F401  MUST be first

import random                                           # noqa: E402
import statistics                                       # noqa: E402
from collections import defaultdict                     # noqa: E402

from riptide.config import BAR_SECONDS, CFG, INTERVAL   # noqa: E402
from riptide.trend import supertrend                    # noqa: E402
from research.data import load_sync                     # noqa: E402
from research.harness import mean_se                    # noqa: E402

WINDOW = CFG.early_max_bars
SEEDS = 25
_BTC = {}


def line(lab, vals, n_all=None):
    if len(vals) < 25:
        print(f"    {lab:<28}{len(vals):>6}   too few")
        return None
    m, se = mean_se(vals)
    w = sum(1 for v in vals if v > 0) / len(vals)
    print(f"    {lab:<28}{len(vals):>6}{w:>7.0%}{m:>+10.3f}{se:>7.3f}")
    return m, se


def compare(a, b, all_vals=None, n=None):
    if not (a and b):
        return
    d, dse = a[0] - b[0], (a[1] ** 2 + b[1] ** 2) ** 0.5
    extra = ""
    if all_vals and n and 25 <= n < len(all_vals):
        f = statistics.median(
            statistics.fmean(random.Random(2100 + s).sample(all_vals, n))
            for s in range(SEEDS))
        extra = f"   placebo {f:+.3f}"
    print(f"    {'  difference':<28}{'':>13}{d:>+10.3f}{dse:>7.3f}"
          f"   {d / dse if dse else 0:+.1f} SE{extra}")


# ---------------------------------------------------------------- 3. BTC
def btc_dir_at(rows, t):
    """BTC's 30m SuperTrend direction at time t, from BTC's own candles.

    Read off the same corpus rather than re-fetched, so the regime and the
    signals come from one snapshot of the market and cannot disagree about
    what happened.
    """
    if not _BTC:
        for r in rows:
            if r.symbol.startswith("BTC_"):
                cs = r.candles
                _BTC["cs"] = cs
                _BTC["st"] = supertrend(cs)
                _BTC["idx"] = {c.t: i for i, c in enumerate(cs)}
                break
    if "cs" not in _BTC:
        return None
    step = BAR_SECONDS[INTERVAL]
    i = _BTC["idx"].get(t - (t % step))
    if i is None or i >= len(_BTC["st"]):
        return None
    return _BTC["st"][i]


def sig_time(r):
    return (getattr(r.signal, "fvg_time", 0)
            or getattr(r.signal, "mss_time", 0) or r.signal.sweep_time)


def idea3(rows, title):
    print(f"\n3. BTC 30m REGIME — {title}   n={len(rows)}")
    print(f"    {'':<28}{'n':>6}{'win':>7}{'R/signal':>10}{'SE':>7}")
    agree, against = [], []
    for r in rows:
        d = btc_dir_at(rows, sig_time(r))
        if not d:
            continue
        (agree if (d > 0) == r.signal.is_long else against).append(r.r)
    line("all with a BTC reading", agree + against)
    a = line("BTC AGAINST the trade", against)
    b = line("BTC with the trade", agree)
    compare(a, b)


# ------------------------------------------------------- 4. MTF agreement
def idea4(rows30, rows15, title):
    print(f"\n4. MTF AGREEMENT — {title}   n={len(rows30)} on Min30")
    print(f"    {'':<28}{'n':>6}{'win':>7}{'R/signal':>10}{'SE':>7}")
    by_sym = defaultdict(list)
    for r in rows15:
        by_sym[r.symbol].append((sig_time(r), r.signal.is_long))
    span = WINDOW * BAR_SECONDS[INTERVAL]
    hit, miss = [], []
    for r in rows30:
        t, want = sig_time(r), r.signal.is_long
        ok = any(lg == want and 0 <= t - t15 <= span
                 for t15, lg in by_sym.get(r.symbol, ()))
        (hit if ok else miss).append(r.r)
    allv = hit + miss
    line("all Min30 signals", allv)
    a = line("with a Min15 signal too", hit)
    b = line("without", miss)
    compare(a, b, allv, len(hit))


# ----------------------------------------------------------- 5. pool memory
def idea5(rows, title):
    print(f"\n5. POOL MEMORY — {title}   n={len(rows)}")
    print(f"    {'':<28}{'n':>6}{'win':>7}{'R/signal':>10}{'SE':>7}")
    # How many times this symbol had already raided a level within a hair of
    # this one, before this signal. The pool level is what identifies it.
    seen = defaultdict(list)
    for r in sorted(rows, key=sig_time):
        lv = getattr(r.signal, "level", 0.0)
        key = (r.symbol, r.signal.is_long)
        n = sum(1 for p in seen[key] if lv and abs(p - lv) / lv < 0.002)
        r.raid_n = n
        seen[key].append(lv)
    line("all signals", [r.r for r in rows])
    stats = []
    for lab, lo, hi in (("1st raid of the level", 0, 1),
                        ("2nd", 1, 2), ("3rd", 2, 3), ("4th or later", 3, 99)):
        stats.append((lab, line(lab, [r.r for r in rows
                                      if lo <= r.raid_n < hi])))
    ok = [s for _, s in stats if s]
    if len(ok) >= 2:
        mids = [x[0] for x in ok]
        mono = (all(a <= b for a, b in zip(mids, mids[1:]))
                or all(a >= b for a, b in zip(mids, mids[1:])))
        compare(ok[-1], ok[0])
        print(f"    {'  ':<28}{'':>13}{'':>10}{'':>7}   "
              f"{'monotone' if mono else 'NOT monotone'}")
    print(f"\n   and the same idea read off `pivots`, the swing count already "
          f"on the alert")
    for lab, lo, hi in (("2 swings", 0, 3), ("3 swings", 3, 4),
                        ("4+ swings", 4, 99)):
        line(lab, [r.r for r in rows
                   if lo <= getattr(r.signal, "pivots", 0) < hi])


def main():
    import asyncio
    import aiohttp
    from riptide.exchange import list_symbols

    async def _s():
        async with aiohttp.ClientSession() as sess:
            return await list_symbols(sess)
    syms = asyncio.run(_s()) or None
    m30 = load_sync(symbols=syms)
    m15 = load_sync(symbols=syms, interval="Min15")
    early = [r for r in m30 if r.kind == "early"]
    held = [r for r in early if r.split_window]
    print(f"THREE IDEAS — {len(m30)} signals on Min30, {len(m15)} on Min15")

    idea3(early, "early, all")
    idea3(held, "early, HELD OUT (pre-registered)")
    # THE TWO CORPORA DO NOT COVER THE SAME WINDOW, and the first run of this
    # study reported "0 rows" for the held-out MTF panel because of it. Both
    # fetch 2000 bars, so Min30 spans ~42 days and Min15 only ~21 — and the
    # held-out half of Min30 is the OLDER half, which the Min15 data does not
    # reach at all. That is not a null result, it is an impossible test.
    #
    # Restricting Min30 to the window Min15 actually covers, and splitting THAT
    # in half, gives a smaller but valid test. Paging Min15 back another 2000
    # bars would be the alternative; this is the honest one available now.
    e15 = [r for r in m15 if r.kind == "early"]
    lo15 = min(sig_time(r) for r in e15) if e15 else 0
    over = [r for r in early if sig_time(r) >= lo15]
    mid = (min(sig_time(r) for r in over) + max(sig_time(r) for r in over)) / 2
    idea4(early, e15, "early, all Min30 — NOT held out, windows differ")
    idea4(over, e15, "early, OVERLAPPING window only")
    idea4([r for r in over if sig_time(r) < mid], e15,
          "early, OLDER half of the overlap (pre-registered)")
    idea5(early, "early, all")
    idea5(held, "early, HELD OUT (pre-registered)")


if __name__ == "__main__":
    main()
