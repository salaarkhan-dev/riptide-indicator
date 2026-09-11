"""The risk band crossed with the POI, on 1h, for all / confirmed / early.

READ THE POWER PARAGRAPH BEFORE THE GRID OR THE GRID WILL MISLEAD YOU. Crossing
three streams by three risk zones by six POI arms is fifty-four cells drawn from
2037 bets. A typical cell holds 150-400 bets, so its standard error is 0.07 to
0.11 and the minimum detectable difference between two of them is around 0.35 R
— larger than any effect this project has ever measured, on any question. The
best cell in a grid this size is the best by chance. `universe_size.py` is the
cautionary tale: nine symbols reversed a verdict there, and that was a two-arm
split, not a fifty-four-cell table.

SO THE GRID IS DESCRIPTION AND THE TESTS BELOW IT ARE THE STUDY. Two contrasts
are pre-registered because both are two-arm comparisons inside a stratum, which
is where the bets actually are.

THE BOUNDARIES ARE NOT REFITTED. LO=1.2 and HI=2.6 come from survivor.py, fitted
on Min30 confirmed. Re-deriving them on Min60 would be fitting and scoring on
the same rows. They are used exactly as deployed, which on Min60 — median stop
1.97% against Min30's 1.39% — keeps a larger share of the stream than it does on
the timeframe it was fitted on.

THE POI IS READ ON Hour8 IN PRODUCTION, NOT Day1. See poi_tf.py: TREND_INTERVAL
moved on 9 Sep and took the point of interest with it, and every description in
the repository still says daily. The arms here are labelled by what they
actually are.

SAME PIPELINE AS poi_tf.py, IMPORTED RATHER THAN COPIED. Identical pool,
identical symbols, identical 333 days, so the two studies cannot disagree for
reasons of plumbing.

PRE-REGISTERED, BEFORE THE FIRST NUMBER

  PRIMARY. Inside each POI arm, R per bet in the 1.2-2.6% band against
  everything outside it, at 2 SE. The band is the one filter this project has
  established; the question is whether the POI changes it, breaks it, or is
  redundant with it. Reported for all / confirmed / early separately.

  SECONDARY. Inside the band only, in an 8h zone against not in one, and the
  same for daily. This is the question that would change the config: given that
  a 1h alert is already in the band, does the POI add anything?

  EXPECTATION. The band survives in every POI arm at roughly the +0.26 it
  showed on Min60 in timeframes.py, and is detectable there (band cells hold
  enough bets for an SE near 0.09, so +0.26 clears 2 SE). The POI adds nothing
  inside the band, and is not detectable either way at the ~0.04 seen in
  poi_tf.py. If the band DIES inside one POI arm that is the interesting
  outcome, and it would most likely mean the two filters are selecting the same
  trades rather than that either stopped working.

    PYTHONPATH=. RIPTIDE_MIN_GRADE=B RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/poi_risk.py

RESULT, 11 Sep 2026 — THE BAND IS THE STRUCTURE IN THIS TABLE AND THE POI IS
NOT IN IT ANYWHERE.

4723 filled Min60 A/B trades, 2037 bets, 59 symbols, 333 days. All signals:

    arm                  tight <1.2%      band 1.2-2.6%       wide >2.6%
    no POI at all     +0.153 ( 619)      +0.188 (1130)     -0.005 ( 875)
    in 8h zone (LIVE) +0.075 ( 358)      +0.159 ( 686)     -0.011 ( 499)
    NOT in 8h zone    +0.217 ( 355)      +0.185 ( 667)     +0.007 ( 487)
    in daily zone     +0.068 ( 230)      +0.153 ( 520)     -0.034 ( 392)
    NOT in daily zone +0.163 ( 478)      +0.178 ( 823)     +0.015 ( 572)
    in BOTH zones     +0.007 ( 152)      +0.060 ( 339)     -0.094 ( 256)

READ IT DOWN THE COLUMNS AND NOTHING MOVES. Read it ACROSS and the band beats
the wide tail in every single row, by +0.15 to +0.19. The wide column is at or
below zero in five rows of six whatever the POI says.

PRIMARY: THE BAND SURVIVES IN ALL EIGHTEEN ARMS. Band against everything
outside it, per POI arm, per stream: eighteen tests, eighteen POSITIVE
differences, from +0.068 to +0.313. Three clear 2 SE — no POI/all (+0.125,
|z| 2.3), no POI/confirmed (+0.226, |z| 2.0) and not-in-daily/confirmed
(+0.313, |z| 2.3). The arms overlap heavily, so eighteen is not eighteen
independent replications; the honest count is nearer five. Even so, not one
arm points the wrong way, and the filter fitted on Min30 confirmed transfers
to Min60 early, which is a different stream on a different timeframe.

MY PREDICTION WAS DIRECTIONALLY RIGHT AND NUMERICALLY OPTIMISTIC. I said the
band would hold at roughly +0.26 and be detectable. It holds everywhere but at
+0.10 to +0.14 on the all-signal rows, so most of these arms sit BELOW their
own MDE and are consistent rather than conclusive.

SECONDARY: INSIDE THE BAND THE POI IS WORTH NOTHING, NINE TESTS OUT OF NINE.

    ALL         8h vs no 8h     +0.159 vs +0.185   |z| 0.3
                daily vs none   +0.153 vs +0.178   |z| 0.3
                both vs neither +0.060 vs +0.169   |z| 1.1
    CONFIRMED   8h vs no 8h     +0.244 vs +0.166   |z| 0.5
                daily vs none   +0.164 vs +0.257   |z| 0.5
                both vs neither +0.210 vs +0.240   |z| 0.1
    EARLY       8h vs no 8h     +0.141 vs +0.188   |z| 0.6
                daily vs none   +0.155 vs +0.167   |z| 0.2
                both vs neither +0.047 vs +0.168   |z| 1.2

Seven of the nine point the WRONG way. None is significant and the MDEs here
are 0.21 to 0.76, so this rules out the POI being a large help inside the band
and nothing more. But it is the third independent framing — after poi_tf.py's
in-zone-vs-out and its timeframe sweep — in which the POI on 1h fails to show
a benefit, and the first two were on the same rows, so call it one finding
seen three ways rather than three findings.

NO INTERACTION. The band's lift inside an 8h zone is +0.137 and outside one is
+0.092; inside a daily zone +0.138, outside +0.098. The difference of those
differences is about +0.045 against SEs of that size, i.e. nothing. The band
works the same whether or not the raid is in a zone, which is what you would
expect from two filters that are not measuring the same thing — and it is also
why stacking them buys nothing.

"IN BOTH ZONES" IS THE WORST ROW OF THE GRID IN ALL THREE STREAMS. Band cell
+0.060 on all signals and +0.047 on early, against +0.169 and +0.168 for
neither zone. Requiring two context readings agree keeps selecting the worse
half, exactly as poi_tf.py found. Three streams is not three samples — early is
81% of the pool — but the confirmed row does not contradict it.

THE ONE CELL THAT WILL TEMPT SOMEBODY: confirmed, in a daily zone, tight stop
reads +0.377±0.270 on 32 bets. It is the largest number in the file, it is 1.4
SE from zero, its neighbours in the same column are -0.041 and -0.098, and
cell-against-cell here needs 0.366 R to be readable. That is what a 54-cell
grid drawn from 2037 bets produces, and it is why the grid above is labelled
DESCRIPTION.

DISTRUST THE LEVELS, READ THE DIFFERENCES. Every level in this table is
inflated by survivorship — the universe is the symbols liquid TODAY, walked
back a year — so "early in the band is +0.180 at 4.3 SE from zero" is not a
forecast of +0.180. The band-minus-outside differences are common-mode on that
bias and are what this study is for.

WHAT IT MEANS FOR THE 1h QUESTION. If the 1h stream is turned on, the risk-band
label is the thing to carry over to it and the POI gate is not. The band
transfers; the POI, on this timeframe, has now failed to show a benefit under
three framings and costs half the stream.
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import statistics                                       # noqa: E402
from collections import defaultdict                     # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import BAR_SECONDS                  # noqa: E402
from research.deep import load_universe                 # noqa: E402
from research.harness import mean_se                    # noqa: E402
from research.studies.poi_tf import DAY, DAYS, H8, INTERVAL  # noqa: E402
from research.studies.poi_tf import collect, context, universe  # noqa: E402
from research.studies.power import mde                  # noqa: E402
from research.studies.survivor import LO, HI            # noqa: E402

ZONES = (("tight <1.2%", lambda t: t.risk_pct < LO),
         ("band 1.2-2.6%", lambda t: LO <= t.risk_pct <= HI),
         ("wide >2.6%", lambda t: t.risk_pct > HI))

POIS = (("no POI at all", lambda t: True),
        ("in 8h zone (LIVE)", lambda t: t.h8),
        ("NOT in 8h zone", lambda t: not t.h8),
        ("in daily zone", lambda t: t.day),
        ("NOT in daily zone", lambda t: not t.day),
        ("in BOTH zones", lambda t: t.h8 and t.day))

STREAMS = (("ALL SIGNALS", lambda t: True),
           ("CONFIRMED ONLY", lambda t: t.kind == "confirmed"),
           ("EARLY ONLY", lambda t: t.kind == "early"))


def bets_of(rows):
    g = defaultdict(list)
    for t in rows:
        g[t.t].append(t.r)
    return [statistics.fmean(g[k]) for k in sorted(g)]


def cell(rows):
    """R per bet ± SE and the bet count, or blanks when too thin to print."""
    b = bets_of(rows)
    if len(b) < 25:
        return f"{'—':>11}({len(b):>4})"
    m, se = mean_se(b)
    return f"{m:>+6.3f}±{se:.3f}({len(b):>4})"


def grid(name, rows):
    print(f"\n-- {name} " + "-" * max(0, 74 - len(name)))
    print(f"  {'':<18}" + "".join(f"{z:>18}" for z, _ in ZONES))
    for label, keep in POIS:
        got = [t for t in rows if keep(t)]
        print(f"  {label:<18}" + "".join(cell([t for t in got if z(t)])
                                        for _, z in ZONES))
    print(f"  {'cell = R/bet ± SE (bets). a dash means under 25 bets.':<18}")


def test(label, a, b):
    if len(a) < 25 or len(b) < 25:
        print(f"  {label:<46} too thin")
        return
    ba, bb = bets_of(a), bets_of(b)
    ma, sa = mean_se(ba)
    mb, sb = mean_se(bb)
    se = (sa ** 2 + sb ** 2) ** 0.5
    z = abs(ma - mb) / se if se else 0.0
    n = min(len(ba), len(bb))
    sd = statistics.pstdev(ba + bb) if len(ba) + len(bb) > 1 else 1.31
    print(f"  {label:<46}{ma:>+7.3f} vs {mb:>+7.3f}  diff {ma - mb:>+6.3f}"
          f"  |z| {z:>4.1f}  MDE {mde(sd, n):>5.3f}"
          + ("  SEPARATES" if z >= 2 else ""))


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = await universe(sess)
        candles = await load_universe(
            sess, syms, INTERVAL, DAYS,
            min_bars=int(0.8 * DAYS * 86400 // BAR_SECONDS[INTERVAL]))
        rows = await collect(sess, candles,
                             await context(sess, candles, DAY),
                             await context(sess, candles, H8))
    rows = [t for t in rows if t.filled and t.exit_t is not None]

    print(f"THE RISK BAND CROSSED WITH THE POI, ON 1h\n{len(rows)} filled "
          f"Min60 A/B trades, {len(candles)} symbols, {DAYS} days.\nband "
          f"boundaries {LO}/{HI} are survivor.py's, fitted on Min30 and NOT "
          f"refitted here.\nthe live POI is read on Hour8; 'daily' below is "
          f"the alternative, not the status quo.")
    allb = bets_of(rows)
    sd = statistics.pstdev(allb)
    print(f"\n  POWER. {len(allb)} bets, sd {sd:.2f}. A grid cell holding 200 "
          f"bets has SE {sd / 200 ** 0.5:.3f},\n  and telling two such cells "
          f"apart needs {mde(sd, 200):.3f} R — bigger than any effect ever "
          f"measured\n  on this project. The grid DESCRIBES. Only the tests "
          f"below it decide anything.")

    for name, keep in STREAMS:
        grid(name, [t for t in rows if keep(t)])

    print("\n== PRIMARY: does the band survive inside each POI arm? " + "=" * 21)
    for name, sk in STREAMS:
        s = [t for t in rows if sk(t)]
        print(f"\n  {name}")
        for label, pk in POIS:
            got = [t for t in s if pk(t)]
            inb = [t for t in got if LO <= t.risk_pct <= HI]
            out = [t for t in got if not (LO <= t.risk_pct <= HI)]
            test(f"    {label}: band vs outside", inb, out)

    print("\n== SECONDARY: inside the band, does the POI add anything? "
          + "=" * 18)
    for name, sk in STREAMS:
        s = [t for t in rows if sk(t) and LO <= t.risk_pct <= HI]
        print(f"\n  {name}  ({len(s)} trades in the band)")
        test("    8h zone vs no 8h zone",
             [t for t in s if t.h8], [t for t in s if not t.h8])
        test("    daily zone vs no daily zone",
             [t for t in s if t.day], [t for t in s if not t.day])
        test("    both zones vs neither",
             [t for t in s if t.h8 and t.day],
             [t for t in s if not t.h8 and not t.day])


if __name__ == "__main__":
    asyncio.run(main())
