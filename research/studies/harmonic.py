"""Do the Fibonacci ratios do anything, or is a harmonic just a retracement?

THE COUNT STUDY ANSWERED THE ONLY QUESTION THAT COMES FIRST. There are 1,037
harmonics at a five per cent band over 333 days — an implied standard error of
0.04, better than the deployed stream's 0.062. The sample-size objection I
raised before that ran was wrong, and it was the objection I most expected to
end this. So the measurement is possible and it is worth doing properly.

WHAT MAKES THIS A TEST RATHER THAN A BACKTEST. "Do harmonics make money" is a
question any sufficiently tuned detector answers yes to: ten free parameters and
a tolerance band will find whatever is asked of them. The sharp question is
whether the RATIOS add anything over the shape they sit on, and that needs a
control drawn from the same population.

  HARMONIC   a five-pivot window whose four leg ratios all satisfy one of the
             named patterns at ±5%
  NEAR MISS  the same window shape, satisfying THREE of the four and failing
             one. Same swings, same neighbourhood, same everything a harmonic
             has except the ratio that names it. This is the control that
             matters — if it scores the same, the ratios are decoration
  ANY WINDOW every other five-pivot window. The loose control, included because
             a near miss is itself a selected object and could carry its own bias

Every arm is traded IDENTICALLY: enter at D, stop beyond the pattern's extreme,
2R target, the same fee model as everything else here. Nothing about the trade
management differs between arms, so a difference between them is a difference
between the ratios and nothing else.

NON-REPAINTING, AND A HARMONIC IS FIVE PIVOTS DEEP SO THIS MATTERS FIVE TIMES.
A pivot is confirmed only after `right` bars have closed. The trade is therefore
signalled on D's CONFIRMATION bar, not on D itself, and the entry is a limit at
D's price that may never fill. Filling at D on the bar D happened would be
reading the future, and it is the single easiest way to make this look good.

PRE-REGISTERED, BEFORE THE FIRST NUMBER

  PRIMARY   harmonic minus near-miss, in R per bet, against a circular-shift
            null that rotates each symbol's harmonic LABEL in time. The null is
            the rotation and not a coin flip because pattern occurrence clusters
            — volatile regimes throw more pivots and therefore more windows —
            and a per-signal shuffle would be far too lenient, as
            feature_batch2.py established.

  SECOND    the sign must hold in at least 3 of 4 quarters. A ratio that only
            worked in one quarter is a season.

  EXPECTATION: no separation. The ratios have no mechanism — there is no story
  for why 0.786 should matter and 0.75 should not — and eleven of the twelve
  hypotheses tested in this project so far have come back empty. Recorded so it
  cannot be revised afterwards.

    PYTHONPATH=. RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/harmonic.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import random                                           # noqa: E402
import statistics                                       # noqa: E402
from collections import defaultdict                     # noqa: E402
from datetime import datetime, timezone                 # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import TRACK_TARGET_R               # noqa: E402
from riptide.exchange import list_symbols               # noqa: E402
from research.deep import load_universe                 # noqa: E402
from research.harness import mean_se, simulate          # noqa: E402
from research.studies.harmonic_count import (           # noqa: E402
    PATTERNS, TOLERANCES, hits, zigzag)

TF = "Min30"
DAYS = 333
TOL = 0.05
LEFT, RIGHT = 3, 3
SHIFTS = 300

# The stop sits beyond the pattern's extreme by a tenth of the XA leg. Scaled to
# the pattern's own size rather than to ATR, so a big harmonic and a small one
# are given the same proportional room and the arms cannot differ just because
# one class of window is wider than another.
STOP_PAD = 0.10


class Sig:
    __slots__ = ("sym", "t", "r", "cls", "name", "is_long", "risk", "filled")


def classify(r_b, r_c, r_d, r_x):
    """(class, name). Three of four is a near miss; four is the pattern."""
    best = None
    for name, p in PATTERNS.items():
        n = (hits(r_b, p["b_xa"], TOL) + hits(r_c, p["c_ab"], TOL)
             + hits(r_d, p["d_bc"], TOL) + hits(r_x, p["d_xa"], TOL))
        if n == 4:
            return "harmonic", name
        if n == 3 and best is None:
            best = name
    return ("near", best) if best else ("any", "")


async def collect(candles):
    out = []
    for sym, cs in candles.items():
        piv = zigzag(cs, LEFT, RIGHT)
        for s in range(len(piv) - 4):
            X, A, B, C, D = piv[s:s + 5]
            xa = abs(A[1] - X[1])
            ab = abs(B[1] - A[1])
            bc = abs(C[1] - B[1])
            cd = abs(D[1] - C[1])
            if min(xa, ab, bc, cd) <= 0:
                continue
            cls, name = classify(ab / xa, bc / ab, cd / bc, abs(A[1] - D[1]) / xa)

            # D is a low -> the pattern completes a decline -> buy it.
            is_long = not D[2]
            entry = D[1]
            # Beyond whichever of X and D is further out on the risk side, which
            # covers retracement patterns (X is the extreme) and extension ones
            # (D is) with one rule.
            edge = min(X[1], D[1]) if is_long else max(X[1], D[1])
            stop = edge - xa * STOP_PAD if is_long else edge + xa * STOP_PAD
            if entry <= 0 or abs(entry - stop) <= 0:
                continue

            # THE CONFIRMATION BAR, NOT D. A pivot needs `right` bars after it
            # before it is a pivot at all.
            sb = D[0] + RIGHT
            if sb >= len(cs) - 2:
                continue
            o = simulate(cs, sb, entry, stop, is_long, target_r=TRACK_TARGET_R)
            if o.exit_bar is None and o.filled:
                continue
            g = Sig()
            g.sym, g.t, g.cls, g.name = sym, cs[sb].t, cls, name
            g.is_long, g.r, g.filled = is_long, o.r, o.filled
            g.risk = 100 * abs(entry - stop) / entry
            out.append(g)
    return out


def bets(sigs):
    """One bet per close and direction — the unit of account used throughout."""
    g = defaultdict(list)
    for s in sigs:
        g[(s.t, s.is_long)].append(s.r)
    return [statistics.fmean(v) for v in g.values()]


def contrast(a_sigs, b_sigs):
    a, b = bets(a_sigs), bets(b_sigs)
    if len(a) < 20 or len(b) < 20:
        return None
    ma, sa = mean_se(a)
    mb, sb = mean_se(b)
    se = (sa ** 2 + sb ** 2) ** 0.5
    return dict(na=len(a), nb=len(b), ma=ma, mb=mb, d=ma - mb, se=se,
                z=(ma - mb) / se if se else 0.0,
                wa=sum(1 for r in a if r > 0) / len(a),
                wb=sum(1 for r in b if r > 0) / len(b))


def circular_null(sigs, keep_cls, other_cls, seeds=SHIFTS):
    """|z| when each symbol's CLASS labels are rotated in time against R.

    Pattern occurrence clusters — a volatile stretch throws more pivots and
    therefore more windows — so the labels are not independent draws and a
    per-signal shuffle would be far too lenient. Rotating keeps the clustering,
    the counts and the ordering, and destroys only the alignment with outcome.
    """
    bysym = defaultdict(list)
    for s in sorted(sigs, key=lambda z: z.t):
        bysym[s.sym].append(s)
    out = []
    for k in range(seeds):
        rnd = random.Random(9100 + k)
        a, b = [], []
        for group in bysym.values():
            if len(group) < 2:
                continue
            j = rnd.randrange(len(group))
            for i, s in enumerate(group):
                lab = group[(i + j) % len(group)].cls
                if lab == keep_cls:
                    a.append(s)
                elif lab in other_cls:
                    b.append(s)
        got = contrast(a, b)
        if got:
            out.append(abs(got["z"]))
    return sorted(out)


def row(label, sigs, days):
    b = bets(sigs)
    if len(b) < 15:
        print(f"  {label:<34}{len(b):>6}   too few")
        return
    m, se = mean_se(b)
    fill = sum(1 for s in sigs if s.filled) / len(sigs)
    print(f"  {label:<34}{len(b):>6}{len(b) / days:>7.2f}{fill:>7.0%}"
          f"{sum(1 for r in b if r > 0) / len(b):>6.0%}{m:>+9.3f}{se:>7.3f}"
          f"{statistics.median(s.risk for s in sigs):>7.2f}%")


def header(title):
    print(f"\n{title}")
    print(f"  {'':<34}{'bets':>6}{'/day':>7}{'fill':>7}{'win':>6}{'R/bet':>9}"
          f"{'SE':>7}{'risk':>8}")


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = await list_symbols(sess)
        candles = await load_universe(sess, syms, TF, DAYS)
        sigs = await collect(candles)

    days = statistics.median((cs[-1].t - cs[0].t) / 86400 for cs in candles.values())
    harm = [s for s in sigs if s.cls == "harmonic"]
    near = [s for s in sigs if s.cls == "near"]
    anyw = [s for s in sigs if s.cls == "any"]

    print(f"DO THE RATIOS DO ANYTHING — harmonics against the shape they sit on\n"
          f"{len(candles)} symbols · {days:.0f} days · {TF} · band ±{TOL:.0%} · "
          f"pivots {LEFT}/{RIGHT} · target {TRACK_TARGET_R:g}R\n"
          f"entry at D on its CONFIRMATION bar, stop beyond the pattern extreme "
          f"by {STOP_PAD:.0%} of XA\n"
          f"{len(sigs):,} windows: {len(harm):,} harmonic · {len(near):,} near "
          f"miss · {len(anyw):,} other")

    header("THE THREE ARMS, traded identically")
    row("HARMONIC (4 of 4 ratios)", harm, days)
    row("NEAR MISS (3 of 4)", near, days)
    row("ANY OTHER WINDOW", anyw, days)

    header("BY PATTERN")
    for name in PATTERNS:
        row(name, [s for s in harm if s.name == name], days)

    header("HARMONIC, LONG against SHORT")
    row("long", [s for s in harm if s.is_long], days)
    row("short", [s for s in harm if not s.is_long], days)

    # ---- the primary contrast, against the strict null --------------------
    print(f"\n{'=' * 92}\nPRIMARY — harmonic against near miss\n{'=' * 92}")
    real = contrast(harm, near)
    if not real:
        print("  too few")
        return
    null = circular_null(sigs, "harmonic", ("near",))
    p95 = null[int(0.95 * (len(null) - 1))] if null else float("nan")
    print(f"  harmonic  {real['na']:>5} bets  {real['wa']:>3.0%} win  "
          f"{real['ma']:>+7.3f} R      near miss {real['nb']:>5} bets  "
          f"{real['wb']:>3.0%} win  {real['mb']:>+7.3f} R")
    print(f"  difference {real['d']:>+8.3f}   real |z| {abs(real['z']):>5.2f}"
          f"   null p95 {p95:>5.2f}   null max {null[-1] if null else 0:>5.2f}"
          f"   {'CLEARS' if abs(real['z']) >= p95 else 'does not clear'}")

    byq = defaultdict(list)
    for s in sigs:
        d = datetime.fromtimestamp(s.t, timezone.utc)
        byq[f"{d.year}Q{(d.month - 1) // 3 + 1}"].append(s)
    cells, signs = [], []
    for q in sorted(byq):
        g = contrast([s for s in byq[q] if s.cls == "harmonic"],
                     [s for s in byq[q] if s.cls == "near"])
        cells.append(f"{q} {g['d']:>+6.3f}" if g else f"{q}  thin ")
        if g:
            signs.append(g["d"] > 0)
    agree = max(sum(signs), len(signs) - sum(signs)) if signs else 0
    print("  by quarter  " + "   ".join(cells)
          + f"   -> sign holds {agree} of {len(signs)}")

    print(f"\nPRE-REGISTERED: clear the null's p95 AND hold the sign in 3 of 4 "
          f"quarters.\nExpectation recorded before the run was NO separation — "
          f"the ratios have no mechanism,\nand eleven of the twelve hypotheses "
          f"tested here so far have come back empty.")


if __name__ == "__main__":
    asyncio.run(main())
