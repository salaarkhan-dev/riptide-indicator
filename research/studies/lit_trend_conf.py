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

──────────────────────────────────────────────────────────────────────────────
RESULT — 1261 confirmed A/B signals of 27040, 59 symbols, 333 days, Min30.
Full output in lit_trend_conf.out.

IT SURVIVED ALL FOUR FALSIFIERS, AND THE RECORDED EXPECTATION ABOVE WAS WRONG
ON BOTH COUNTS.

  plain null        p95 2.0   real 3.1   p 0.003
  FAMILY-WISE null  p95 2.7   real 3.1   p 0.018      <- the one that settles it
  bootstrap         [+0.103, +0.424]  median +0.259, entirely above zero
  half 1            +0.158 kept vs -0.092 cut   |SE| 2.0   +15.6R   alerts -27%
  half 2            +0.145 kept vs -0.123 cut   |SE| 2.3   +27.9R   alerts -36%
  all               +0.152 kept vs -0.110 cut   |SE| 3.1   +43.5R   alerts -31%

I expected the family-wise null to fail, on the argument that 3.1 is not far
past a max-of-four distribution when the single-arm p95 was 2.1. It is past
it: at 2000 rotations the exceedance rate is 0.018, so this is not a threshold
scraped by a rounding. I also expected one of the two halves to show a
non-negative cut group at n≈200. Both halves cut a LOSING group, at almost
identical effect size — +0.250 and +0.268 — which is the most convincing line
in the table and the one the flat-3R finding failed.

WHY THIS ONE IS DIFFERENT FROM EVERY OTHER FILTER TESTED HERE. The group it
excludes makes -0.110. Twenty-odd filters have separated by keeping the better
half of a pool that was positive throughout, which buys nothing: a prediction
is not a decision. This is the first that removes signals which lose money.
The arithmetic is therefore a gain and not a cost, in both halves
independently.

WHAT IT IS WORTH, SCALED TO THE DEPLOYED 120 SYMBOLS. Confirmed A/B alerts run
7.7/day; the gate cuts 2.4/day and adds about +88R over 333 days. It touches
only 14% of the A/B stream, because confirmed signals are 1261 of 9159 — this
is a narrow instrument, not a rewrite of the grade.

FOUR THINGS THAT SHOULD TEMPER IT, NONE OF THEM FATAL.
  n on the cut side is 395, and 169/226 per half. Small.
  The family-wise null spans the four arms read in lit_trend.py. It does NOT
  span every filter tested across this project; each study is pre-registered
  separately, which is the standard being applied, but a reader who wants the
  project-wide correction will not find it here.
  There is no mechanism. lit_trend.py predicted the effect on EARLY signals
  and it landed on CONFIRMED ones, so the story that motivated the test is not
  the story the data tells. A surviving finding without a mechanism is still
  only a finding.
  It has never run forward. Everything above is in-sample over one 333-day
  window on one timeframe.

SO THE RECOMMENDATION IS SHADOW MODE, NOT A SHIPPED GATE: label confirmed
alerts with whether the structural trend agrees, change nothing about which
alerts are sent, and compare the two groups forward until the live n on the
cut side reaches the low hundreds. That is the only test left that this
window cannot fake.
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

SHIFTS = 2000
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
        # The exact exceedance rate, not just the p95 verdict. Clearing a p95
        # by 0.2 and clearing it by 1.0 are different findings and the
        # threshold hides which one this is.
        pv = sum(1 for v in dist if v >= real) / len(dist)
        print(f"  {name:<42} p95 {p95:>4.1f}   max {dist[-1]:>4.1f}   "
              f"real {real:>4.1f}   p {pv:>6.3f}   "
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
