"""IS THE CONFIRMED CELL REAL, OR IS IT THE BEST OF FOUR ARMS?

lit_trend.py measured the structure indicator's trend as a gate on Riptide
signals. Its pre-registered primary passed everything and still should not
ship, because the group it excludes makes +0.004 — filtering something that is
merely less positive costs alerts and returns nothing.

ONE ARM LOOKED DIFFERENT. On CONFIRMED signals the excluded group is -0.110
against +0.152 kept, |SE| 3.1, and cutting it gains +43.5R while dropping 31%
of confirmed alerts. That is the only cell in the study whose excluded group
loses money, which is the only shape that justifies a gate.

IT IS POST-HOC AND THIS FILE SAYS SO IN ITS TITLE. It was a pre-registered
SECONDARY, not the primary; it inverts the direction lit_trend.py recorded in
advance (the effect was predicted on EARLY signals, by analogy with SMT); its
excluded side is 395 rows; and no null was run on it. A 3.1 on a subgroup
found after reading four arms is the exact shape rotation kills — it is how
pivot_tune.py's three-touch finding died.

──────────────────────────────────────────────────────────────────────────────
WHAT THIS RUN ADDS, FIXED BEFORE THE FIRST NUMBER

  THE PLAIN NULL. 300 circular shifts of each symbol's trend series, scored on
  the confirmed cell alone. Rotation preserves the run lengths and the up/down
  balance and breaks only the link to the outcome.

  THE FAMILY-WISE NULL, WHICH IS THE ONE THAT SETTLES IT. A plain null asks
  "could this arm alone have come out this far by chance?" That is the wrong
  question once the arm was CHOSEN by looking. The right question is "could
  the BEST OF THE FOUR ARMS I read have come out this far by chance?" So each
  rotation scores all four — A/B pooled, A/B early, A/B confirmed, C/D pooled
  — and keeps the maximum |SE|. The confirmed cell has to beat the p95 of
  THAT distribution, not of its own. This is the honest price of having gone
  looking, and it is a materially higher bar.

  BOTH HALVES, with the decision arithmetic on each — R gained and alerts lost
  — because a gate that only works in one half is a window effect and the flat
  3R finding died exactly there.

  SYMBOL BOOTSTRAP, 2000 draws, on the confirmed cell.

  WHAT WOULD FALSIFY IT. Failing the family-wise null; or a bootstrap 5th
  percentile below zero; or a half in which the excluded group is not
  negative, since a gate that does not cut losses in a half is not cutting
  losses.

  EXPECTATION, recorded so it cannot be revised. I expect the plain null to
  clear and the FAMILY-WISE null to fail, on the grounds that 3.1 is not far
  past a max-of-four distribution when the single-arm p95 was already 2.1. I
  also expect one of the two halves to show a non-negative excluded group at
  n≈200. If it survives both, this is the first gate in this project whose
  excluded group actually loses money and it is worth a shadow-mode trial.

    PYTHONPATH=. RIPTIDE_MIN_GRADE=B RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/lit_trend_conf.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import json                                             # noqa: E402
import os                                               # noqa: E402
import random                                           # noqa: E402
import statistics                                       # noqa: E402
from bisect import bisect_right                         # noqa: E402
from collections import defaultdict                     # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import BAR_SECONDS                  # noqa: E402
from research.deep import load_universe                 # noqa: E402
from research.harness import mean_se                    # noqa: E402
from research.studies.poi_tf import DAY, DAYS, H8       # noqa: E402
from research.studies.poi_tf import collect, context, universe  # noqa: E402
from research.studies.lit_trend import INTERVAL, gap, split  # noqa: E402
from research.studies.lit_trend import trend_series     # noqa: E402

SHIFTS = 300
BOOT = 2000
CACHE = "/tmp/lit_trend_rows.json"


def sep(rows):
    """|SE| of the agrees-vs-disagrees difference on one arm, or None."""
    a, b = [r for ok, r in rows if ok], [r for ok, r in rows if not ok]
    if len(a) < 25 or len(b) < 25:
        return None
    ma, sa = mean_se(a)
    mb, sb = mean_se(b)
    se = (sa ** 2 + sb ** 2) ** 0.5
    return abs((ma - mb) / se) if se else None


def decide(a, b, label):
    """The arithmetic that decides, not the one that separates."""
    ma = statistics.fmean([r for _, r in a]) if a else 0.0
    mb = statistics.fmean([r for _, r in b]) if b else 0.0
    tot = len(a) * ma + len(b) * mb
    print(f"  {label:<20}{'kept':>8}{len(a):>6}{ma:>+8.3f}"
          f"{'   cut':>8}{len(b):>6}{mb:>+8.3f}"
          f"   total {tot:>+7.1f}R  gated {len(a) * ma:>+7.1f}R"
          f"   delta {len(a) * ma - tot:>+6.1f}R"
          f"   alerts {-len(b) / max(len(a) + len(b), 1):>4.0%}"
          + ("" if mb < 0 else "   CUT GROUP IS NOT NEGATIVE"))


async def build():
    if os.path.exists(CACHE):
        return json.load(open(CACHE))
    async with aiohttp.ClientSession() as sess:
        syms = await universe(sess)
        cs = await load_universe(
            sess, syms, INTERVAL, DAYS,
            min_bars=int(0.8 * DAYS * 86400 // BAR_SECONDS[INTERVAL]))
        zday = await context(sess, cs, DAY)
        z8h = await context(sess, cs, H8)
        rows = await collect(sess, cs, zday, z8h, interval=INTERVAL,
                             require_ab=False)
    tr = {s: ([c.t for c in cs[s]], trend_series(cs[s])) for s in cs}
    data = []
    for t in rows:
        if not t.filled or t.exit_t is None or t.sym not in tr:
            continue
        times, tser = tr[t.sym]
        i = bisect_right(times, t.t) - 1
        if i < 0 or tser[i] == 0:
            continue
        data.append([t.sym, (tser[i] > 0) == t.is_long, t.r, t.kind, t.t,
                     t.trend_ok, i, bool(t.is_long)])
    out = {"data": data, "trend": {s: tr[s][1] for s in tr}}
    json.dump(out, open(CACHE, "w"))
    return out


def main():
    blob = asyncio.run(build())
    data = [tuple(d) for d in blob["data"]]
    trend = blob["trend"]

    # The four arms that were READ in lit_trend.py, in the order they were
    # read. The family-wise null has to span exactly these and no others --
    # adding arms here would inflate the null and adding none would be the
    # plain null under a different name.
    ARMS = {
        "A/B pooled":   lambda d: d[5],
        "A/B early":    lambda d: d[5] and d[3] == "early",
        "A/B confirmed": lambda d: d[5] and d[3] == "confirmed",
        "C/D pooled":   lambda d: not d[5],
    }
    conf = [d for d in data if ARMS["A/B confirmed"](d)]

    print("IS THE CONFIRMED CELL REAL, OR THE BEST OF FOUR ARMS?")
    print(f"{len(data)} filled signals, {DAYS} days, {INTERVAL}. "
          f"{len(conf)} of them grade A/B and CONFIRMED.\n")
    print(f"  {'':<44}{'R/sig':>8}{'n':>7}    {'R/sig':>8}{'n':>7}")
    a, b = split([(s, ok, r) for s, ok, r, *_ in conf])
    got = gap("  confirmed, structure agrees vs disagrees", a, b)

    print(f"\n{'=' * 100}\nWHAT THE GATE WOULD ACTUALLY DO\n{'=' * 100}")
    print("  separation is not a decision. a gate only pays if the group it")
    print("  CUTS loses money -- less positive is not the same as negative.")
    decide(a, b, "confirmed, all")

    print(f"\n{'=' * 100}\nBOTH HALVES\n{'=' * 100}")
    ts = sorted(d[4] for d in conf)
    mid = ts[len(ts) // 2] if ts else 0
    for lab, sel in (("half 1", lambda t: t <= mid),
                     ("half 2", lambda t: t > mid)):
        sub = [(s, ok, r) for s, ok, r, _, tt, *_ in conf if sel(tt)]
        x, y = split(sub)
        gap(f"  {lab}", x, y)
        decide(x, y, f"  {lab}")

    print(f"\n{'=' * 100}\nTHE TWO NULLS — {SHIFTS} rotations\n{'=' * 100}")
    per_sym = defaultdict(list)
    for d in data:
        per_sym[d[0]].append(d)
    rnd = random.Random(20260913)
    plain, family = [], []
    for _ in range(SHIFTS):
        arms = {k: [] for k in ARMS}
        for sym, hits in per_sym.items():
            tser = trend.get(sym)
            if not tser or len(tser) < 200:
                continue
            n = len(tser)
            off = rnd.randrange(100, n - 100)
            for d in hits:
                v = tser[(d[6] + off) % n]
                if v == 0:
                    continue
                # The rotated trend replaces the real one and the AGREEMENT is
                # recomputed against the signal's own direction, so the null
                # statistic is built exactly the way the real one is. Grouping
                # by raw trend direction instead would be a different, weaker
                # null -- it would not mix longs and shorts the same way.
                ok = (v > 0) == d[7]
                for k, keep in ARMS.items():
                    if keep(d):
                        arms[k].append((ok, d[2]))
        scores = {k: sep(v) for k, v in arms.items()}
        if scores["A/B confirmed"] is not None:
            plain.append(scores["A/B confirmed"])
        live = [v for v in scores.values() if v is not None]
        if len(live) == len(ARMS):
            family.append(max(live))
    real = abs(got[1]) if got else 0.0
    for name, dist in (("plain, confirmed arm alone", plain),
                       ("FAMILY-WISE, max of the four arms read", family)):
        if not dist:
            print(f"  {name:<42} no usable rotations")
            continue
        dist.sort()
        p95 = dist[int(0.95 * (len(dist) - 1))]
        print(f"  {name:<42} p95 {p95:>4.1f}   max {dist[-1]:>4.1f}   "
              f"real {real:>4.1f}   "
              f"{'CLEARS' if real > p95 else 'FAILS - inside the null'}")

    print(f"\n{'=' * 100}\nSYMBOL BOOTSTRAP — {BOOT} draws\n{'=' * 100}")
    bysym = defaultdict(list)
    for s, ok, r, *_ in conf:
        bysym[s].append((ok, r))
    names = sorted(bysym)
    rnd = random.Random(20260913)
    out = []
    for _ in range(BOOT):
        pick = [rnd.choice(names) for _ in names]
        x = [r for s in pick for ok, r in bysym[s] if ok]
        y = [r for s in pick for ok, r in bysym[s] if not ok]
        if len(x) > 25 and len(y) > 25:
            out.append(statistics.fmean(x) - statistics.fmean(y))
    if out:
        out.sort()
        p5 = out[int(0.05 * (len(out) - 1))]
        p95 = out[int(0.95 * (len(out) - 1))]
        print(f"  [{p5:+.3f}, {p95:+.3f}]   median {statistics.median(out):+.3f}"
              + ("   all above zero" if p5 > 0 else "   STRADDLES ZERO"))


if __name__ == "__main__":
    main()
