"""SMT DIVERGENCE AGAINST A CIRCULAR-SHIFT NULL. The test that decides it.

`unicorn_smt.py` found SMT divergence at +0.074 R per signal, |z| 2.9 — same
sign on both directions, same sign and size in both window halves, and with the
confluence control pointing the right way. On this project's usual standards
that is the best entry-side result it has produced.

IT IS ALSO THE EXACT SHAPE OF SOMETHING THAT HAS FAILED HERE BEFORE, AND THE
REASON IS STRUCTURAL RATHER THAN A HUNCH. Every signal in the universe is
compared to ONE BTC series. When BTC is quiet, thousands of signals across a
hundred symbols all score "divergence" together; when BTC is making extremes,
they all score "none" together. The feature is therefore massively
autocorrelated across symbols AND across time, and an independent-SE z computed
on it is optimistic by an amount no amount of staring at the number reveals.

`pivot_tune.py` is the precedent and it is worth stating in full. Its
three-touch pool finding scored +0.206 R per bet on a held-out half at a 46%
win rate — the strongest separation anywhere in the early stream. Against a
circular-shift null:

    real separation          1.69 SE
    null p95                 2.56 SE
    null max over 300        3.86 SE

Rotating the feature in time — same values, same order, same keep rate, same
autocorrelation, no link to the outcome — manufactured a LARGER separation than
the real one more than 5% of the time. The finding was smaller than what its
own shape produces against a random outcome, and it died.

WHAT IS ROTATED HERE, AND WHY IT IS THE RIGHT THING. Not the feature and not
the outcome: the BTC SERIES ITSELF. Its highs and lows are rolled by a random
offset while the timestamps stay put, then divergence is recomputed against
that rolled series. BTC keeps its own volatility clustering, its own run
lengths, its own rate of making 20-bar extremes — everything except its real-
time relationship to the symbol that was raided. If "the symbol swept and BTC
did not" carries information, a BTC series from a different week must not
reproduce it.

THE REAL NUMBER IS RECOMPUTED HERE TOO, through the identical code path. The
rolling-extreme window is applied in BTC's own bar space rather than mapped
through each symbol's timestamps, which is a hair different from how
unicorn_smt.py did it. A null is only a null if the statistic it nulls is
computed the same way, so both go through this file's machinery and the
original number is printed beside it as a cross-check.

──────────────────────────────────────────────────────────────────────────────
PRE-REGISTERED, BEFORE THE FIRST NUMBER

  PRIMARY. The real separation between SMT-divergence and no-divergence
  signals, in SE, against the p95 of 300 circular-shift rotations. It must
  clear that p95. Reported on the EARLY stream, which is where unicorn_smt.py
  found the effect lives, and pooled.

  SECONDARY. The symbol bootstrap, 2000 draws, resampling the UNIVERSE. A level
  that depends on a handful of symbols is not a property of the market.

  THE CONFLUENCE CONTROL, re-run against the same null. Divergence should clear
  it and confluence should not — and confluence pointing the WRONG way inside
  the null would tell us the null itself is mis-specified.

  WHAT WOULD FALSIFY IT. Real separation below the null's p95, in either the
  early panel or pooled. Or a symbol bootstrap whose 5th percentile straddles
  zero.

  EXPECTATION, recorded so it cannot be revised. I think it clears, and I am
  less sure than the |z| 2.9 makes it sound. The reason to expect it to survive
  is that the confluence control already moved the OPPOSITE way — a shared-
  regime artefact would push both arms the same direction, and it did not. The
  reason to expect it to die is pivot_tune.py: a feature every symbol shares at
  once is exactly what this null exists to punish, and BTC's 20-bar extremes
  are far more persistent than a pool's touch count ever was. If I had to put a
  number on it: 60/40 that it clears, which is not the confidence |z| 2.9
  implies and is why this file exists.

    PYTHONPATH=. RIPTIDE_MIN_GRADE=B RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/smt_null.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import random                                           # noqa: E402
import statistics                                       # noqa: E402
from bisect import bisect_right                         # noqa: E402
from collections import defaultdict, deque              # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import CFG, TRACK_TARGET_R          # noqa: E402
from riptide.engine import atr_series, grade_of, run_engine  # noqa: E402
from riptide.exchange import fetch_candles, list_symbols  # noqa: E402
from riptide.trend import di_at, direction_at, poi_at   # noqa: E402
from research.deep import load_deep, load_universe      # noqa: E402
from research.harness import mean_se, simulate          # noqa: E402

DAYS = 333
INTERVAL = "Min30"
REF = "BTC_USDT"
SMT_BACK = 20
SHIFTS = 300
BOOT = 2000


class Row:
    __slots__ = ("sym", "t", "kind", "is_long", "r", "mine", "j", "half")


def rolling_extremes(lo, hi, n):
    """(is a new n-bar low at i, is a new n-bar high at i) for every i.

    Monotonic deques, so the whole series costs O(len) rather than O(len * n) —
    which is what makes 300 rotations affordable at all.
    """
    N = len(lo)
    newlo = [False] * N
    newhi = [False] * N
    dlo, dhi = deque(), deque()
    for i in range(N):
        while dlo and dlo[0] < i - n:
            dlo.popleft()
        while dhi and dhi[0] < i - n:
            dhi.popleft()
        # Compare against the window BEFORE this bar, then admit this bar.
        newlo[i] = (not dlo) or lo[i] <= lo[dlo[0]]
        newhi[i] = (not dhi) or hi[i] >= hi[dhi[0]]
        while dlo and lo[dlo[-1]] >= lo[i]:
            dlo.pop()
        dlo.append(i)
        while dhi and hi[dhi[-1]] <= hi[i]:
            dhi.pop()
        dhi.append(i)
    return newlo, newhi


async def collect(sess, candles, ref_t):
    """One expensive pass. Records only what the null needs to be cheap."""
    rows = []
    for sym, cs in candles.items():
        if sym == REF:
            continue
        early = []
        try:
            setups = run_engine(sym, cs, CFG, early_out=early)
        except Exception:
            continue
        idx = {c.t: i for i, c in enumerate(cs)}
        atr = atr_series(cs, CFG.atr_len)
        for kind, batch in (("confirmed", setups), ("early", early)):
            for x in batch:
                i = idx.get(x.detected_time)
                if i is None or x.entry <= 0 or abs(x.entry - x.stop) <= 0:
                    continue
                if not (atr[i] if i < len(atr) else 0.0):
                    continue
                w = x.detected_time
                poi = await poi_at(sess, sym, w, x.stop, x.is_long,
                                   fetch_candles)
                if not (True if poi is None else bool(poi)):
                    continue
                d = await direction_at(sess, sym, w, fetch_candles)
                di = await di_at(sess, sym, w, fetch_candles)
                if grade_of(kind == "early", True, d or 0, x.is_long,
                            di or 0)[0] not in "AB":
                    continue
                g = idx.get(getattr(x, "grab_time", 0) or 0)
                if g is None or g < SMT_BACK:
                    continue
                j = bisect_right(ref_t, cs[g].t) - 1
                if j < SMT_BACK:
                    continue
                o = simulate(cs, i, x.entry, x.stop, x.is_long,
                             target_r=TRACK_TARGET_R)
                z = Row()
                z.sym, z.t, z.kind, z.is_long = sym, w, kind, bool(x.is_long)
                z.r = o.r
                z.j = j
                # The symbol's own half of the comparison never rotates.
                z.mine = (cs[g].l <= min(c.l for c in cs[g - SMT_BACK:g])
                          if x.is_long
                          else cs[g].h >= max(c.h for c in cs[g - SMT_BACK:g]))
                rows.append(z)
    return rows


def separation(rows, newlo, newhi, confluence=False):
    """(diff, SE units, n_yes) for divergence — or for confluence."""
    yes, no = [], []
    for z in rows:
        theirs = newlo[z.j] if z.is_long else newhi[z.j]
        flag = (z.mine and theirs) if confluence else (z.mine and not theirs)
        (yes if flag else no).append(z.r)
    if len(yes) < 30 or len(no) < 30:
        return None
    ma, sa = mean_se(yes)
    mb, sb = mean_se(no)
    se = (sa ** 2 + sb ** 2) ** 0.5
    return (ma - mb, (ma - mb) / se if se else 0.0, len(yes), ma, mb)


def null_dist(rows, lo, hi, confluence=False):
    """|SE| of the separation when the BTC series is rolled in time."""
    rnd = random.Random(20260913)
    N = len(lo)
    out = []
    for _ in range(SHIFTS):
        off = rnd.randrange(SMT_BACK * 5, N - SMT_BACK * 5)
        rlo = lo[off:] + lo[:off]
        rhi = hi[off:] + hi[:off]
        nl, nh = rolling_extremes(rlo, rhi, SMT_BACK)
        got = separation(rows, nl, nh, confluence)
        if got:
            out.append(abs(got[1]))
    return sorted(out)


def boot(rows, newlo, newhi):
    """Resample SYMBOLS with replacement; recompute the difference each draw."""
    bysym = defaultdict(list)
    for z in rows:
        bysym[z.sym].append(z)
    syms = sorted(bysym)
    rnd = random.Random(20260913)
    out = []
    for _ in range(BOOT):
        pick = [rnd.choice(syms) for _ in syms]
        sub = [z for s in pick for z in bysym[s]]
        got = separation(sub, newlo, newhi)
        if got:
            out.append(got[0])
    return sorted(out)


def panel(name, rows, lo, hi, newlo, newhi, confluence=False):
    got = separation(rows, newlo, newhi, confluence)
    if not got:
        print(f"  {name:<34} too few")
        return
    diff, se, ny, ma, mb = got
    nd = null_dist(rows, lo, hi, confluence)
    if not nd:
        print(f"  {name:<34} null failed")
        return
    p95 = nd[int(0.95 * (len(nd) - 1))]
    clears = abs(se) > p95
    print(f"  {name:<34}{ma:>+8.3f}{ny:>7}  vs{mb:>+8.3f}"
          f"{len(rows) - ny:>7}   diff {diff:>+6.3f}  |SE| {abs(se):>4.1f}")
    print(f"  {'':<34}null p95 {p95:>4.1f}   null max {nd[-1]:>4.1f}   "
          f"{'CLEARS' if clears else 'FAILS — inside the null'}")


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = await list_symbols(sess)
        candles = await load_universe(sess, syms, INTERVAL, DAYS)
        ref = await load_deep(sess, REF, INTERVAL, DAYS)
        ref_t = [c.t for c in ref]
        rows = await collect(sess, candles, ref_t)

    lo = [c.l for c in ref]
    hi = [c.h for c in ref]
    newlo, newhi = rolling_extremes(lo, hi, SMT_BACK)

    rows.sort(key=lambda z: z.t)
    mid = rows[len(rows) // 2].t
    for z in rows:
        z.half = 0 if z.t <= mid else 1
    early = [z for z in rows if z.kind == "early"]
    conf = [z for z in rows if z.kind == "confirmed"]

    print("SMT DIVERGENCE AGAINST A CIRCULAR-SHIFT NULL")
    print(f"{len(rows)} A/B signals, {len(candles)} symbols, {DAYS} days, "
          f"{INTERVAL}.  {REF} rolled {SHIFTS} times.")
    print(f"\n  The null rolls BTC's highs and lows in time and leaves the")
    print(f"  timestamps alone, so BTC keeps its own volatility clustering and")
    print(f"  its own rate of making {SMT_BACK}-bar extremes — everything but")
    print(f"  its real-time link to the symbol that was raided.\n")

    print(f"  {'panel':<34}{'R/sig':>8}{'n':>7}    {'R/sig':>8}{'n':>7}")
    panel("PRIMARY  early, divergence", early, lo, hi, newlo, newhi)
    panel("         pooled, divergence", rows, lo, hi, newlo, newhi)
    panel("         confirmed, divergence", conf, lo, hi, newlo, newhi)
    print()
    panel("CONTROL  early, CONFLUENCE", early, lo, hi, newlo, newhi, True)

    print(f"\n{'=' * 96}\nBOTH HALVES, against the same null\n{'=' * 96}")
    print(f"  {'panel':<34}{'R/sig':>8}{'n':>7}    {'R/sig':>8}{'n':>7}")
    for h in (0, 1):
        panel(f"  early, half {h + 1}", [z for z in early if z.half == h],
              lo, hi, newlo, newhi)

    print(f"\n{'=' * 96}\nSYMBOL BOOTSTRAP — {BOOT} draws over the universe"
          f"\n{'=' * 96}")
    for lab, sub in (("early", early), ("pooled", rows)):
        b = boot(sub, newlo, newhi)
        if not b:
            continue
        p5 = b[int(0.05 * (len(b) - 1))]
        p95 = b[int(0.95 * (len(b) - 1))]
        print(f"  {lab:<12}[{p5:>+7.3f}, {p95:>+7.3f}]   median "
              f"{statistics.median(b):>+7.3f}"
              + ("   all above zero" if p5 > 0 else "   STRADDLES ZERO"))
    print("\n  a difference that depends on a handful of symbols is not a")
    print("  property of the market. the 5th percentile has to clear zero.")


if __name__ == "__main__":
    asyncio.run(main())
