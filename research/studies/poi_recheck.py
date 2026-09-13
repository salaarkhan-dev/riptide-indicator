"""Reconciling the two POI results instead of picking one.

THE OBJECTION THIS FILE TAKES SERIOUSLY. matrix.py found the point of interest
doing nothing across eighteen contrasts on 333 days, and the honest reply to
that is: "but the POI was pre-registered, held out on symbols it had never
seen, and it improved every arm of three different models — that is better
evidence than almost anything else in this repository." That objection is
correct about the provenance. Dismissing it because a newer, larger study
disagrees is not analysis, it is recency.

So the question here is not "which study is right". It is: WHAT WOULD HAVE TO
BE TRUE for both to be right, and can that be checked?

Four things could be true at once. Each is a section below.

  WINDOW. The original ran on 41-42 days. If the POI effect is real but
  unstable, a 42-day window is a draw from a wide distribution and +0.6 is one
  draw. Non-overlapping 42-day windows over the deep year measure that
  distribution directly. If +0.6 sits comfortably inside its spread, both
  studies are describing the same world and only one of them had the sample to
  see it.

  POWER. The original cells hold 28 to 43 signals (Min15 confirmed in a POI:
  n=31, +0.417 ± 0.222). The held-out arms ran n=30, n=170, n=122 and scored
  +1.4, +1.3 and +1.8 SE — MEASUREMENTS.md says so itself: "No single arm
  clears 2 SE, let alone the 3 SE bar a single-comparison filter has to clear
  here." What carried it was SIGN CONSISTENCY across cells, not any one cell.
  That is a legitimate form of evidence and it is also the form most exposed to
  a common cause, because the cells were not independent: same 41 days, same
  market, and Min15 and Min30 signals frequently describing the same raid.

  TREND INTERACTION. The original headline was not the POI alone. It was
  MULTIPLICATIVE: Min30 confirmed with neither +0.082, trend alone +0.206, POI
  alone +0.105, BOTH +0.822. matrix.py restricted to trend-agrees throughout,
  so it tested the POI inside the good half and never looked at the other one.
  That is the right slice for a deployment question and the wrong slice for
  arguing with an interaction claim. Here the trend-disagreeing signals are
  kept and the full 2x2 is rebuilt.

  UNIVERSE. 23 symbols then, 59 now, and the 23 were the most liquid. If the
  POI works on majors and not on the tail, both results hold and the filter
  needs a liquidity condition rather than retirement.

WHAT WOULD VINDICATE THE POI HERE. Any of: a 42-day window distribution whose
centre is clearly positive; a trend-disagrees half where the POI works; a
liquidity split where the top symbols carry it. Those are real outcomes and
this file is written to find them if they are there.

WHAT WOULD NOT. "+0.6 is inside the spread of 42-day windows" does not prove
the POI is worthless — it proves the original study could not have told the
difference between +0.6 and 0, which is a statement about the instrument.

NOT A/B FILTERED. collect() runs with require_ab=False so the trend-disagrees
signals are present, which is the one thing matrix.py could not offer.

PRE-REGISTERED, BEFORE THE FIRST NUMBER

  PRIMARY. The distribution of the POI gap (in-zone minus out-of-zone, per bet)
  across eight non-overlapping 42-day windows, per timeframe per stream. The
  question it answers is not "is the POI real" but "could a 42-day study have
  known". Reported with the count of positive windows and the spread.

  SECONDARY. The full POI x trend 2x2 rebuilt on 333 days, against the original
  cell table. And the same POI gap split by liquidity rank.

  EXPECTATION. The 42-day windows scatter widely — I predict a spread of 0.5 R
  or more between the best and worst window on the confirmed cells — with a
  centre near zero and several individually positive windows. I expect the 2x2
  to show the trend axis surviving and the POI axis not, because the trend axis
  is the one matrix.py has never contradicted. I do NOT expect the liquidity
  split to rescue it, but it is the cheapest of the four checks and the only
  one that would leave the filter deployable in a narrowed form.

    PYTHONPATH=. RIPTIDE_MIN_GRADE=B RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/poi_recheck.py

RESULT, 11 Sep 2026 — THE OBJECTION WAS RIGHT AND matrix.py OVERSTATED. THE POI
SURVIVES IN EXACTLY ONE CELL, AND IT IS THE CELL THE FILTER WAS BUILT ON.

TWELVE CELLS, THREE TIMEFRAMES, BOTH ZONE MAPS, ONE WINNER. Trend agreeing,
same rows throughout; the only thing that changes inside a pair is which map
is read. "win+" is how many of eight non-overlapping 42-day windows came out
positive, where 4/8 is a coin toss.

    tf   stream     POI          in     out     gap     SE  |z|   win+
    15m  confirmed  daily    -0.010  +0.055  -0.065  0.075  0.9    5/8
    15m  confirmed  8h       +0.017  +0.072  -0.055  0.067  0.8    4/8
    15m  early      daily    +0.004  +0.032  -0.028  0.030  0.9    3/8
    15m  early      8h       +0.011  +0.045  -0.034  0.028  1.2    4/8
    30m  confirmed  daily    +0.174  +0.014  +0.160  0.099  1.6    6/8  <-- the
    30m  confirmed  8h       +0.066  +0.060  +0.006  0.087  0.1    4/8      only
    30m  early      daily    +0.047  +0.105  -0.058  0.041  1.4    3/8      one
    30m  early      8h       +0.032  +0.117  -0.085  0.039  2.2    2/8
    1h   confirmed  daily    +0.132  +0.086  +0.046  0.117  0.4    3/8
    1h   confirmed  8h       +0.106  +0.100  +0.006  0.110  0.1    5/8
    1h   early      daily    +0.079  +0.129  -0.051  0.057  0.9    4/8
    1h   early      8h       +0.088  +0.126  -0.038  0.055  0.7    3/8

ONE CELL IS POSITIVE WITH ANY STRENGTH AND IT NEEDS THE DAILY MAP. Min30
confirmed on Day1: +0.160, six of eight windows, median +0.331. Its Hour8 twin
is +0.006 on four of eight with a median of +0.019 — a coin toss. The live
configuration is the coin toss.

THE 1h CONFIRMED CELL LOOKS SUPPORTIVE AND IS NOT, and that is worth saying
because an earlier reading of mine leaned on it. Daily is +0.046, which is the
right sign, but it is positive in only THREE of eight windows with a median of
-0.042 — the level is carried by two good windows out of eight. Point estimate
and window count disagree, and when they disagree the window count is the
honest one. There is no 1h POI effect in either map.

EVERY EARLY CELL IS NEGATIVE IN BOTH MAPS, all six of them, and 30m early on
Hour8 reaches -0.085 at |z| 2.2 — the only cell in the study that clears 2 SE,
and it says the filter HURTS there. Early signals are roughly 80% of the alert
stream, so "the POI improves signal quality" is true of about a fifth of what
the bot sends and false of the rest.

DAY1 AGAINST HOUR8, COUNTED FAIRLY. Daily is better in three of six cells and
Hour8 in the other three, so on a show of hands it is a tie. On MAGNITUDE it is
not close: daily's win in the one cell that matters is +0.154, and the largest
of Hour8's three wins is +0.013. Reverting POI_INTERVAL to Day1 buys the one
working cell and costs a rounding error everywhere else.

THE SHAPE REPLICATES. THE SIZE IS A QUARTER. Min30 confirmed, the original's
headline square, rebuilt on 333 days against what was reported on 41:

    POI  trend    bets        333 days      original
    no   no       1247   -0.050±0.037        +0.082
    no   yes       696   +0.014±0.051        +0.206
    yes  no        556   -0.094±0.057        +0.105
    yes  yes       282   +0.174±0.084        +0.822

Every cell shrank and the ORDERING IS PRESERVED EXACTLY: worst is POI-without-
trend, best is both. The interaction the original described is still there —
both agreeing is +0.174 against +0.014 for trend alone, a +0.160 gap where the
original measured +0.616. So the claim "the POI improves the signal" is not
refuted. It is refuted at the size it was reported.

AND IT IS NOT ONE WINDOW'S LUCK. The POI gap on Min30 confirmed, measured in
eight NON-OVERLAPPING 42-day windows:

    -0.114  +0.450  -0.608  +0.077  +0.429  +0.379  +0.918  +0.282
    6/8 positive, median +0.331, whole year +0.160 ± 0.099

Six of eight independent windows positive with a median of +0.331 is a real
pattern, not a sampling artefact. This is the strongest thing said about the
POI on the deep window anywhere in this repository, and matrix.py did not say
it — see the correction below.

WHERE IT DOES NOT SURVIVE, and this is most of the bot:

    15m confirmed   -0.065 ± 0.075     5/8 windows positive, median +0.033
    15m early       -0.028 ± 0.030     3/8 positive, median -0.021
    30m early       -0.058 ± 0.041     3/8 positive, median -0.076

Early signals are about 80% of the alert stream and the POI does nothing for
them on either timeframe. The original's Min15 claims — confirmed +0.417,
early +0.281 — come back as -0.010 and +0.004 in the same 2x2 cells. So the
part of the finding that generalised to a second timeframe and to the early
stream is the part that did not hold.

WHY matrix.py READ IT AS A FLAT FAILURE, stated plainly because it is my error.
Two reasons, both avoidable. Its primary was the LIVE 8h POI, where Min30
confirmed is +0.006; the DAILY POI on the same cell is +0.160. And its
summary line pooled six rows and took a median, which buries one strong cell
under five flat ones when five of the six are early or 15m. "2/6 positive,
median -0.036" is true arithmetic and the wrong summary of what is in the rows.
matrix.py's docstring has been corrected.

THE ORIGINAL COULD NOT HAVE KNOWN THE SIZE, and that is the reconciliation.

    cell                              n   reported        MDE
    discovery Min15 confd in POI     31   +0.417±0.222   0.932
    discovery Min30 confd POI+trend  43   +0.822±0.187   0.791
    held out  Min30 confirmed        30   +0.429 +1.4SE  0.947
    held out  Min15 early           122   +0.201 +1.8SE  0.470
    held out  Min30 early           170   +0.066 +1.3SE  0.398

Every arm needed an effect of 0.4 to 0.9 R to reach 2 SE. The largest effect
this project has measured on any question is +0.32. So the original design
could not distinguish +0.16 from +0.82 from zero, and MEASUREMENTS.md said as
much at the time — "No single arm clears 2 SE, let alone the 3 SE bar a
single-comparison filter has to clear here." What carried it was sign
consistency
across cells, which was the correct call on that evidence and which has now
turned out to be right about the SIGN and wrong about the MAGNITUDE by 5x. The
42-day window spread on this cell is 1.526 R, from -0.608 to +0.918: the
original's +0.616 sits comfortably inside it.

THE CONSEQUENTIAL FINDING IS ABOUT THE INTERVAL, NOT THE FILTER. The POI works
on Day1 in this cell (+0.160) and not on Hour8 (+0.006). The bot has read the
POI on Hour8 since 9 Sep — not because anything measured it there, but because
poi_at read TREND_INTERVAL and the SuperTrend moved. The one configuration with
a held-out pedigree is the one that was silently switched off, and the switch
also cut the zone lifetime from thirty days to ten. Restoring Day1 for the POI
alone is now one line, RIPTIDE_POI_INTERVAL, and it is a REVERT of an
unmeasured accident rather than a new optimisation — a much lower bar than
adding a filter.

THE TREND AXIS IS THE ROBUST HALF, AND IT WAS NEVER IN QUESTION. Trend agrees
against trend against, all four cells, all clearing 2 SE:

    15m confirmed  +0.057 vs -0.054   |z| 2.6
    15m early      +0.030 vs -0.036   |z| 3.5
    30m confirmed  +0.071 vs -0.052   |z| 2.2
    30m early      +0.094 vs +0.019   |z| 2.9

Four for four, on the deployed Hour8 reading. The original called POI and trend
multiplicative; the deep window says the trend is the filter and the POI is a
weak add-on visible in one cell.

LIQUIDITY DOES NOT RESCUE IT AND MILDLY CONTRADICTS THE ORIGINAL. On Min30
confirmed the POI gap is +0.033 on the top 23 symbols and +0.223 on the rest —
the opposite of where the original found it. Not significant either way, and
enough to refuse "it only works on majors" as an escape hatch.

MY EXPECTATIONS, SCORED. I predicted a wide 42-day spread (right: 1.526 on the
key cell), a trend axis that survives (right, 4/4), no liquidity rescue
(right), and that the POI axis would not survive — WRONG, in the one cell that
matters. The prediction I got wrong is the one the objection was about.
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import statistics                                       # noqa: E402
from collections import defaultdict                     # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import BAR_SECONDS                  # noqa: E402
from research.deep import load_universe                 # noqa: E402
from research.harness import mean_se                    # noqa: E402
from research.studies.poi_tf import DAY, DAYS, H8       # noqa: E402
from research.studies.poi_tf import collect, context, universe  # noqa: E402
from research.studies.power import mde                  # noqa: E402

TFS = ("Min15", "Min30", "Min60")
SHORT = {"Min15": "15m", "Min30": "30m", "Min60": "1h"}
WINDOW = 42 * 86400                # the original study's window, to the day
SD = 1.31                          # per-bet, stable across every timeframe


def bets_of(rows):
    g = defaultdict(list)
    for t in rows:
        g[t.t].append(t.r)
    return [statistics.fmean(g[k]) for k in sorted(g)]


def gap(rows, zone="day"):
    """(in minus out, SE, mean_in, mean_out) for one POI definition.

    `zone` picks which map: "day" is the ORIGINAL configuration the filter was
    found on, "h8" is what the bot has actually read since 9 Sep. They are
    measured on the same rows so the comparison between them is paired at the
    population level even though each contrast is unpaired.
    """
    pick = (lambda t: t.day) if zone == "day" else (lambda t: t.h8)
    a = [t for t in rows if pick(t)]
    b = [t for t in rows if not pick(t)]
    if len(a) < 15 or len(b) < 15:
        return None
    ba, bb = bets_of(a), bets_of(b)
    if len(ba) < 10 or len(bb) < 10:
        return None
    ma, sa = mean_se(ba)
    mb, sb = mean_se(bb)
    return ma - mb, (sa ** 2 + sb ** 2) ** 0.5, ma, mb


def windows(rows):
    """Non-overlapping 42-day windows, oldest first."""
    if not rows:
        return []
    lo = min(t.t for t in rows)
    hi = max(t.t for t in rows)
    out = []
    s = lo
    while s + WINDOW <= hi + WINDOW:
        out.append([t for t in rows if s <= t.t < s + WINDOW])
        s += WINDOW
    return [w for w in out if w]


async def main():
    by_tf = {}
    async with aiohttp.ClientSession() as sess:
        syms = await universe(sess)
        zday = await context(sess, syms, DAY)
        z8h = await context(sess, syms, H8)
        for tf in TFS:
            cs = await load_universe(
                sess, syms, tf, DAYS,
                min_bars=int(0.8 * DAYS * 86400 // BAR_SECONDS[tf]))
            rows = await collect(sess, cs, zday, z8h, interval=tf,
                                 require_ab=False)
            by_tf[tf] = [t for t in rows
                         if t.filled and t.exit_t is not None]

    print("RECONCILING THE TWO POI RESULTS")
    print(f"{len(syms)} symbols, {DAYS} days, trend-disagreeing signals KEPT.")
    print("the DAILY zone throughout — the original configuration, not the "
          "live 8h one.")
    for tf in TFS:
        n = len(by_tf[tf])
        ok = sum(1 for t in by_tf[tf] if t.trend_ok)
        print(f"  {SHORT[tf]}  {n:>6} filled trades, {ok} trend-agrees, "
              f"{n - ok} trend-against")

    print("\n== 1. DAILY POI vs 8h POI, EVERY TIMEFRAME, EVERY STREAM " + "="*18)
    print("  same rows, same 333 days, trend agreeing. the only thing that")
    print("  changes between the two rows of a pair is WHICH zone map is read.")
    print("  windows+ counts how many of eight non-overlapping 42-day windows")
    print("  came out positive — 4/8 is a coin toss, 6/8 or better is a signal.")
    print(f"\n  {'tf':<5}{'stream':<11}{'POI':<7}{'in':>8}{'out':>8}"
          f"{'gap':>8}{'SE':>7}{'|z|':>6}{'win+':>7}")
    for tf in TFS:
        for stream in ("confirmed", "early"):
            rows = [t for t in by_tf[tf]
                    if t.kind == stream and t.trend_ok]
            for zone, label in (("day", "daily"), ("h8", "8h")):
                g = gap(rows, zone)
                if g is None:
                    continue
                d, se, mi, mo = g
                ws = [gap(w, zone) for w in windows(rows)]
                ws = [w for w in ws if w]
                pos = sum(1 for w in ws if w[0] > 0)
                z = abs(d) / se if se else 0
                print(f"  {SHORT[tf]:<5}{stream:<11}{label:<7}{mi:>+8.3f}"
                      f"{mo:>+8.3f}{d:>+8.3f}{se:>7.3f}{z:>6.1f}"
                      f"{pos:>5}/{len(ws)}"
                      + ("   BETTER IN ZONE" if d > 0 and z >= 1.5 else ""))
        print()

    print("  the same thing again, per 42-day window, for the cells that")
    print("  come out positive above.")
    for tf in TFS:
        for stream in ("confirmed", "early"):
            rows = [t for t in by_tf[tf]
                    if t.kind == stream and t.trend_ok]
            for zone, label in (("day", "daily"), ("h8", "8h")):
                g = gap(rows, zone)
                if g is None or g[0] <= 0:
                    continue
                ws = [gap(w, zone) for w in windows(rows)]
                vals = [w[0] for w in ws if w]
                if len(vals) < 3:
                    continue
                print(f"    {SHORT[tf]:<4}{stream:<11}{label:<7}"
                      + " ".join(f"{v:>+6.2f}" for v in vals)
                      + f"   median {statistics.median(vals):+.3f}")

    print("\n== 2. WHAT THE ORIGINAL STUDY COULD DETECT " + "=" * 33)
    print("  MDE = 2.80 x sd x sqrt(2/n), sd = 1.31 per bet.")
    print("  the original cells and held-out arms, with the effect each")
    print("  could have resolved at 80% power:\n")
    print(f"  {'cell':<34}{'n':>6}{'reported':>11}{'MDE':>9}")
    for name, n, got in (
            ("discovery Min15 confd in POI", 31, "+0.417±0.222"),
            ("discovery Min15 confd no POI", 28, "-0.177"),
            ("discovery Min30 confd POI+trend", 43, "+0.822±0.187"),
            ("held out Min30 confirmed", 30, "+0.429  +1.4SE"),
            ("held out Min15 early", 122, "+0.201  +1.8SE"),
            ("held out Min30 early", 170, "+0.066  +1.3SE")):
        print(f"  {name:<34}{n:>6}{got:>11}{mde(SD, n):>9.3f}")
    print("\n  every one of those needed an effect of 0.4 to 0.9 R to reach")
    print("  2 SE. the largest effect this project has measured anywhere,")
    print("  on any question, is +0.32.")

    print("\n== 3. THE POI x TREND 2x2, REBUILT ON 333 DAYS " + "=" * 29)
    print("  the original's headline was the INTERACTION, so here is the")
    print("  whole square rather than the trend-agrees half matrix.py used.")
    print(f"\n  {'tf':<5}{'stream':<11}{'POI':<5}{'trend':<7}{'bets':>6}"
          f"{'R/bet':>16}{'   original':>13}")
    orig = {("Min30", "confirmed", False, False): "+0.082",
            ("Min30", "confirmed", False, True): "+0.206",
            ("Min30", "confirmed", True, False): "+0.105",
            ("Min30", "confirmed", True, True): "+0.822",
            ("Min30", "early", False, False): "-0.050",
            ("Min30", "early", False, True): "+0.048",
            ("Min30", "early", True, False): "+0.018",
            ("Min30", "early", True, True): "+0.188",
            ("Min15", "confirmed", True, True): "+0.417",
            ("Min15", "early", True, True): "+0.281",
            ("Min15", "early", False, False): "-0.131"}
    for tf in TFS:
        for stream in ("confirmed", "early"):
            for poi in (False, True):
                for tr in (False, True):
                    g = [t for t in by_tf[tf] if t.kind == stream
                         and bool(t.day) == poi and bool(t.trend_ok) == tr]
                    b = bets_of(g)
                    if len(b) < 25:
                        continue
                    m, se = mean_se(b)
                    was = orig.get((tf, stream, poi, tr), "")
                    print(f"  {SHORT[tf]:<5}{stream:<11}"
                          f"{'yes' if poi else 'no':<5}"
                          f"{'yes' if tr else 'no':<7}{len(b):>6}"
                          f"{m:>+8.3f}±{se:.3f}{was:>13}")
        print()

    print("== 4. DOES THE TREND AXIS SURVIVE WHERE THE POI DOES NOT " + "="*18)
    print("  the same two-arm question, asked of the OTHER axis.")
    for tf in TFS:
        for stream in ("confirmed", "early"):
            rows = [t for t in by_tf[tf] if t.kind == stream]
            a = bets_of([t for t in rows if t.trend_ok])
            b = bets_of([t for t in rows if not t.trend_ok])
            if len(a) < 25 or len(b) < 25:
                continue
            ma, sa = mean_se(a)
            mb, sb = mean_se(b)
            se = (sa ** 2 + sb ** 2) ** 0.5
            z = abs(ma - mb) / se if se else 0
            print(f"  {SHORT[tf]:<5}{stream:<11}trend agrees {ma:>+7.3f} vs "
                  f"against {mb:>+7.3f}  diff {ma - mb:>+6.3f}  |z| {z:>4.1f}"
                  + ("  SEPARATES" if z >= 2 else ""))

    print("\n== 5. DOES LIQUIDITY RESCUE IT " + "=" * 44)
    print("  the original ran on 23 symbols, the most liquid. universe() is")
    print("  ordered by the exchange's own ranking, so the first 23 are the")
    print("  nearest available stand-in for that set.")
    top = set(syms[:23])
    for tf in TFS:
        for stream in ("confirmed", "early"):
            for label, keep in (("top 23", lambda t: t.sym in top),
                                ("the rest", lambda t: t.sym not in top)):
                rows = [t for t in by_tf[tf] if t.kind == stream
                        and t.trend_ok and keep(t)]
                g = gap(rows)
                if g is None:
                    continue
                d, se, mi, mo = g
                print(f"  {SHORT[tf]:<5}{stream:<11}{label:<9}"
                      f"POI gap {d:>+7.3f} ± {se:.3f}"
                      f"   (in {mi:>+6.3f} / out {mo:>+6.3f})"
                      + ("  SEPARATES" if abs(d) >= 2 * se else ""))


if __name__ == "__main__":
    asyncio.run(main())
