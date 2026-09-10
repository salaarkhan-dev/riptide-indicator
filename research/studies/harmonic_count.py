"""How many harmonic patterns are even THERE — counts only, no returns.

THIS RUNS BEFORE THE DETECTOR IS WORTH BUILDING, AND IT MAY END THE QUESTION.

A harmonic is five pivots whose four legs sit at particular Fibonacci ratios,
each ratio carrying a tolerance band. That construction has roughly ten free
parameters, which is exactly the shape that manufactures findings: loosen the
bands and patterns appear everywhere, tighten them and none survive. Nothing in
the ratios offers a mechanism — there is no story for why 0.786 should matter
and 0.75 should not — so the only thing that can settle it is a sample.

SO THE FIRST QUESTION IS WHETHER A SAMPLE EXISTS. The deployed stream is 500
bets at a standard error of 0.062, which took 333 days across the whole
universe. Harmonics are far rarer than raids. If a strict Gartley yields forty
instances, its standard error is near 0.30 — wide enough that a genuinely good
edge and a genuinely dead one are the same number, and no amount of care in the
backtest afterwards fixes that.

WHAT THIS PRINTS

  For each pattern, at four tolerance bands: how many instances exist, how often
  per symbol-day, and THE STANDARD ERROR THOSE COUNTS IMPLY. The last column is
  the one that decides whether to carry on.

  The implied SE uses the dispersion the deployed stream actually shows — sd
  about 1.39 R per bet, from 500 bets at SE 0.062 — because a harmonic entry
  would be traded the same way, to the same 2R target, with the same stop
  discipline. It is an estimate of the test's power, not of its result.

  Two pivot settings are run, not one. A harmonic is built on swings, and the
  swing rule is itself a free parameter — if the counts swing wildly between two
  reasonable settings, that is the degrees-of-freedom problem showing up before
  a single ratio has been tested.

PRE-REGISTERED READING, WRITTEN BEFORE THE FIRST NUMBER

  Under 100 instances    the measurement cannot settle it. Say so and stop.
  100 to 300             borderline. Only a large effect would be visible.
  Over 300               worth building the detector and testing properly.

  And the count is not the only failure. If the tolerance band has to be opened
  past about 8% to reach a usable count, whatever is being counted is no longer
  a harmonic — it is "a retracement roughly near a Fibonacci level", and the
  ratios have stopped doing work.

    PYTHONPATH=. RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/harmonic_count.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import statistics                                       # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.exchange import list_symbols               # noqa: E402
from research.deep import load_universe                 # noqa: E402

TF = "Min30"
DAYS = 333

# The dispersion the deployed stream shows: 500 bets at SE 0.062 implies an sd
# of 0.062 * sqrt(500). Used only to turn a count into a power estimate.
R_SD = 1.39

# Tolerance as a fraction of the ratio itself, so a 5% band on 0.618 is
# 0.587-0.649. Quoting it in absolute terms would make the same band mean
# something different for a 0.382 leg than for a 1.618 one.
TOLERANCES = (0.03, 0.05, 0.08, 0.12)


# ── the patterns ────────────────────────────────────────────────────────────
# Each is a set of constraints on the four legs. A single float is a point
# ratio that must be hit within tolerance; a pair is a range the ratio must
# fall inside, and ranges are NOT widened by the tolerance sweep — only the
# point ratios are, because those are the ones the pattern is actually named
# for and the ones a practitioner argues about.
#
# XA is the impulse. B retraces XA. C retraces AB. D extends BC and, in every
# pattern except the Cypher, also sits at a defined ratio of XA.
PATTERNS = {
    "Gartley":   dict(b_xa=0.618, c_ab=(0.382, 0.886), d_bc=(1.13, 1.618), d_xa=0.786),
    "Bat":       dict(b_xa=(0.382, 0.50), c_ab=(0.382, 0.886), d_bc=(1.618, 2.618), d_xa=0.886),
    "Butterfly": dict(b_xa=0.786, c_ab=(0.382, 0.886), d_bc=(1.618, 2.24), d_xa=1.27),
    "Crab":      dict(b_xa=(0.382, 0.618), c_ab=(0.382, 0.886), d_bc=(2.618, 3.618), d_xa=1.618),
    "Shark":     dict(b_xa=(0.382, 0.618), c_ab=(1.13, 1.618), d_bc=(1.618, 2.24), d_xa=(0.886, 1.13)),
    "Cypher":    dict(b_xa=(0.382, 0.618), c_ab=(1.272, 1.414), d_bc=(1.272, 2.0), d_xa=None),
}


def hits(value, spec, tol):
    """A leg ratio against its constraint. None means unconstrained."""
    if spec is None:
        return True
    if isinstance(spec, tuple):
        return spec[0] <= value <= spec[1]
    return abs(value - spec) <= spec * tol


# ── swings ──────────────────────────────────────────────────────────────────
def zigzag(cs, left, right):
    """Confirmed alternating pivots: (index, price, is_high).

    CONFIRMED MEANS CONFIRMED. A pivot is only accepted once `right` bars have
    closed after it, and it is recorded at the bar it happened on rather than
    the bar it became known on. Detecting a swing from bars that had not printed
    yet is the single easiest way to make any pattern study look profitable, and
    a harmonic is five pivots deep — five chances to do it.

    Alternation is enforced: two highs in a row are one turn seen twice, so the
    higher replaces the lower rather than both being kept.
    """
    out = []
    n = len(cs)
    for i in range(left, n - right):
        hi = all(cs[i].h >= cs[j].h for j in range(i - left, i + right + 1))
        lo = all(cs[i].l <= cs[j].l for j in range(i - left, i + right + 1))
        if hi == lo:                      # neither, or a flat bar that is both
            continue
        px = cs[i].h if hi else cs[i].l
        if out and out[-1][2] == hi:
            if (hi and px > out[-1][1]) or (not hi and px < out[-1][1]):
                out[-1] = (i, px, hi)
        else:
            out.append((i, px, hi))
    return out


def scan(piv, tol, tally=None):
    """Every XABCD in the pivot sequence that satisfies a pattern."""
    found = {k: 0 for k in PATTERNS}
    for s in range(len(piv) - 4):
        X, A, B, C, D = piv[s:s + 5]
        # A harmonic alternates by construction: X and B and D on one side, A
        # and C on the other. The zigzag already alternates, so this only has to
        # confirm the window starts on the right foot.
        if not (X[2] != A[2] and A[2] != B[2] and B[2] != C[2] and C[2] != D[2]):
            continue
        xa = abs(A[1] - X[1])
        ab = abs(B[1] - A[1])
        bc = abs(C[1] - B[1])
        cd = abs(D[1] - C[1])
        # THE D RATIO IS MEASURED FROM A, NOT FROM X, and getting that backwards
        # is why the first run of this returned zero for five of the six. "D at
        # 0.786 of XA" means D has retraced 786 thousandths of the XA leg back
        # from A — so it is |A-D| / |A-X|. Measured from X instead it comes out
        # as 1 - 0.786 = 0.214, which no pattern's band contains, and every
        # retracement harmonic reads as absent rather than as mis-measured.
        ad = abs(A[1] - D[1])
        if min(xa, ab, bc, cd) <= 0:
            continue
        r_b = ab / xa
        r_c = bc / ab
        r_d = cd / bc
        r_x = ad / xa
        for name, p in PATTERNS.items():
            ok_b = hits(r_b, p["b_xa"], tol)
            ok_c = hits(r_c, p["c_ab"], tol)
            ok_d = hits(r_d, p["d_bc"], tol)
            ok_x = hits(r_x, p["d_xa"], tol)
            # PER-CONSTRAINT PASS RATES, so a zero is explainable rather than
            # just absent. A count of nought with all four constraints showing
            # healthy individual pass rates means the combination is genuinely
            # rare; a count of nought with ONE constraint at zero means that
            # constraint is mis-specified, which is exactly what happened here.
            if tally is not None:
                tally[name][0] += 1 if ok_b else 0
                tally[name][1] += 1 if ok_c else 0
                tally[name][2] += 1 if ok_d else 0
                tally[name][3] += 1 if ok_x else 0
                tally[name][4] += 1
            if ok_b and ok_c and ok_d and ok_x:
                found[name] += 1
    return found


def se_for(n):
    return R_SD / (n ** 0.5) if n else float("inf")


def verdict(n):
    return "cannot settle" if n < 100 else "borderline" if n < 300 else "usable"


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = await list_symbols(sess)
        candles = await load_universe(sess, syms, TF, DAYS)

    spans = [(cs[-1].t - cs[0].t) / 86400 for cs in candles.values()]
    days = statistics.median(spans)
    symdays = sum(spans)

    print(f"HOW MANY HARMONICS ARE THERE — counts only\n"
          f"{len(candles)} symbols · median {days:.0f} days · {symdays:,.0f} "
          f"symbol-days · {TF}\n"
          f"pivots are CONFIRMED and recorded at the bar they happened on, not "
          f"the bar they\nbecame known on — a harmonic is five pivots deep, so "
          f"that is five chances to peek\n")

    for left, right in ((3, 3), (5, 5)):
        piv_all = {s: zigzag(cs, left, right) for s, cs in candles.items()}
        npiv = sum(len(v) for v in piv_all.values())
        print(f"{'=' * 92}\nSWING RULE {left} bars each side — {npiv:,} confirmed "
              f"pivots, {npiv / symdays:.2f} per symbol-day\n{'=' * 92}")
        print(f"  {'pattern':<12}" + "".join(f"{f'±{t:.0%}':>17}" for t in TOLERANCES))
        print(f"  {'':<12}" + "".join(f"{'count   SE':>17}" for _ in TOLERANCES))

        totals = {t: 0 for t in TOLERANCES}
        rows = {}
        tally = {k: [0, 0, 0, 0, 0] for k in PATTERNS}
        for t in TOLERANCES:
            agg = {k: 0 for k in PATTERNS}
            tl = tally if t == TOLERANCES[-1] else None
            for s, piv in piv_all.items():
                for k, v in scan(piv, t, tl).items():
                    agg[k] += v
            rows[t] = agg
            totals[t] = sum(agg.values())

        for name in PATTERNS:
            cells = ""
            for t in TOLERANCES:
                n = rows[t][name]
                cells += f"{n:>10}{se_for(n):>7.2f}"
            print(f"  {name:<12}{cells}")

        cells = ""
        for t in TOLERANCES:
            cells += f"{totals[t]:>10}{se_for(totals[t]):>7.2f}"
        print(f"  {'ALL POOLED':<12}{cells}")
        print(f"  {'verdict':<12}"
              + "".join(f"{verdict(totals[t]):>17}" for t in TOLERANCES))

        # WHICH CONSTRAINT IS DOING THE KILLING, at the loosest band. A zero
        # with four healthy pass rates means the combination is genuinely rare.
        # A zero with ONE rate at nought means that constraint is mis-specified
        # — which is what the first run of this was, and what it could not say.
        print(f"\n  pass rate per constraint at the loosest band, of "
              f"{tally['Gartley'][4]:,} windows:")
        print(f"  {'pattern':<12}{'B/XA':>9}{'C/AB':>9}{'D/BC':>9}{'D/XA':>9}")
        for name in PATTERNS:
            t4 = tally[name]
            n = t4[4] or 1
            print(f"  {name:<12}" + "".join(f"{t4[i] / n:>8.1%} " for i in range(4)))

    print(f"\nPRE-REGISTERED: under 100 instances the measurement cannot settle "
          f"it — say so and\nstop. 100-300 is borderline. Over 300 is worth "
          f"building the detector for.\n\n"
          f"AND THE COUNT IS NOT THE ONLY FAILURE. If the band has to open past "
          f"8% to reach a\nusable count, what is being counted is no longer a "
          f"harmonic — it is a retracement\nroughly near a Fibonacci level, and "
          f"the ratios have stopped doing any work.\n\n"
          f"The SE column assumes a harmonic entry is traded like every other "
          f"signal here, to\nthe same 2R target with the same stop discipline, "
          f"and takes the dispersion the\ndeployed stream shows (sd {R_SD} R per "
          f"bet). It estimates the test's POWER, not its\nresult.")


if __name__ == "__main__":
    asyncio.run(main())
