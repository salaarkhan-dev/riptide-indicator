"""The risk band crossed with the POI, on 1h, for all / confirmed / early.

READ THE POWER PARAGRAPH BEFORE THE GRID OR THE GRID WILL MISLEAD YOU.
Crossing three streams by three risk zones by six POI arms is fifty-four cells
drawn from 2037 bets. A typical cell holds 150-400 bets, so its standard error
is 0.07 to 0.11 and the smallest detectable difference between two is ~0.35 R
— larger than any effect this project has ever measured, on any question. The
best cell in a grid this size is the best by chance. `universe_size.py` is the
cautionary tale: nine symbols reversed a verdict there, and that was a two-arm
split, not a fifty-four-cell table.

SO THE GRID IS DESCRIPTION AND THE TESTS BELOW IT ARE THE STUDY. Two contrasts
are pre-registered because both are two-arm comparisons inside a stratum, which
is where the bets actually are.

THE BOUNDARIES ARE NOT REFITTED. LO=1.2 and HI=2.6 come from survivor.py,
fitted on Min30 confirmed. Re-deriving them on Min60 would be fitting and
scoring on the same rows. They are used exactly as deployed, which on Min60 —
median stop 1.97% against Min30's 1.39% — keeps a larger share of the stream
than it does on the timeframe it was fitted on.

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

WIN RATE AND RR, ADDED AFTERWARDS — AND THEY SAY THE POI COSTS WIN RATE AND
BUYS NOTHING. R per trade is (win - breakeven) x the average round trip, so a
difference in R has to appear in one of the two blades. Inside the band, all
signals:

                     win      RR   margin over break-even
    in an 8h zone    37%    1.91          +3.0 points
    not in one       40%    1.89          +5.7 points

The RR is IDENTICAL. The whole difference is three points of win rate, in the
filter's disfavour. Same pattern for the daily zone (37%/40%, RR 1.92/1.89).
A naive binomial SE on 1400 trades would make three points look like 2.3 SE;
these trades cluster about two to a bet, so the effective count is nearer half
that and it is ~1.6 SE — consistent with the |z| 0.3 on R, not in conflict with
it. Do not quote the binomial number.

RR IS A CONSTANT AT 1.90 EVERYWHERE EXCEPT THE WIDE TAIL. Every cell in the
tight and band columns lands between 1.86 and 1.93 regardless of POI, stream or
zone. Every cell in the wide column lands between 1.69 and 1.85. That is
mechanical and it explains the whole table: the target is 2R, so a >2.6% stop
needs a >5.2% move inside 60 bars, which often does not arrive — the trade
times out below 2R (RR falls) and stops out more often (win falls). The wide
tail fails on BOTH blades at once, which is why it fails so completely.

    zone     win    RR    margin
    tight    39%   1.91    +4.7
    band     39%   1.90    +4.3
    wide     35%   1.72    -1.3

DRAWDOWN IS WHERE THE REAL ANSWER IS, AND IT IS ALL IN THE WIDE TAIL. On the R
curve in exit order, all signals, no POI:

    tight   +143.2 R   maxDD  41.9   recov  3.42
    band    +280.1 R   maxDD  55.3   recov  5.07
    wide     -50.7 R   maxDD 141.9   recov -0.36

141.9 of the 150.0 R maximum drawdown of the whole 1h stream sits in a bucket
that makes NO money. That is the finding this study exists for. It is not a new
filter — it is the deployed risk band, seen from the drawdown side rather than
the expectancy side, on a timeframe it was not fitted on.

THE POLICY TABLE, 300 USDT at 1% risk, at most 10 positions open:

    policy                 /day    R/bet     total  maxDD  recov   acct  accDD
    everything             28.8   +0.125    +372.5  150.0   2.48  +204%    55%
    POI on (= deployed)    14.6   +0.088    +158.1   91.2   1.73  +140%    52%
    band only, no POI      13.5   +0.188    +280.1   55.3   5.07  +446%    42%
    band + POI on           6.9   +0.159     +98.5   40.4   2.44   +99%    32%
    band, confirmed only    2.2   +0.235     +78.0   19.0   4.10  +103%    18%
    band, early only       11.3   +0.180    +202.1   53.9   3.75  +377%    41%
    post hoc:
    not wide (<2.6%)       19.7   +0.183    +423.3   86.7   4.88  +454%    48%
    tight only (<1.2%)      6.2   +0.153    +143.2   41.9   3.42  +232%    35%
    wide only (>2.6%)       9.2   -0.005     -50.7  141.9  -0.36   -57%    74%

READ THE ACCOUNT COLUMN AS A RANKING, NEVER AS A FORECAST. Levels here carry
the full survivorship premium of walking today's liquid symbols back a year,
and the account is simulated on 59 symbols while the live universe is 120 —
more symbols means more same-bar clustering and more trades refused at the
ten-position cap, so the live figure would be lower than any of these.

THE POST HOC ROWS EXIST BECAUSE THE TIGHT ZONE IS ALIVE ON 1h AND IS NOT ON
Min30. +0.153±0.056 on 619 bets, 2.7 SE from zero, +143 R at recovery 3.42 —
against -0.051 for the same bucket on Min30 confirmed, where the 1.2 floor was
fitted. So on Min60 only the UPPER boundary is doing work, and "not wide" beats
"in band" on total R (+423 against +280) while "in band" beats it on drawdown
(55 against 87). Both readings were taken AFTER seeing the grid. They are
printed to be measured forward, not shipped off this table, and the 1.2 floor
stays where it is until forward data on Min60 says otherwise.

WHAT IT MEANS FOR THE 1h QUESTION. If the 1h stream is turned on, the risk-band
label is the thing to carry over to it and the POI gate is not. The band
transfers; the POI, on this timeframe, has now failed to show a benefit under
three framings and costs half the stream. The band's transfer is the strongest
result in this file precisely because it was NOT fitted here: boundaries from
Min30 confirmed, applied unchanged to Min60 early, still separating in all
eighteen arms. That is out-of-sample, and almost nothing else in this project
is.
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import statistics                                       # noqa: E402
from collections import defaultdict                     # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import BAR_SECONDS                  # noqa: E402
from research.deep import load_universe                 # noqa: E402
from research.harness import mean_se                    # noqa: E402
from research.studies.report import (START, compound,      # noqa: E402
                                     drawdown)              # noqa: E402
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


def shape(rows):
    """(win rate, realised RR, break-even win rate, margin) over TRADES.

    Win rate is a trade statistic, not a bet statistic — a bet is an average
    over symbols firing together and has no win or loss of its own. So this
    deliberately uses a different denominator from the R/bet grid, and the two
    are not two views of one number.

    RR is avg win over avg loss, both NET of fees, so the break-even it implies
    is the after-cost one: 1 / (1 + RR). The margin is the whole story of
    whether a cell makes money — R per trade is almost exactly
    (win - breakeven) x (avg win + avg loss), so a cell is positive if and only
    if its margin is.
    """
    w = [t.r for t in rows if t.r > 0]
    ls = [t.r for t in rows if t.r <= 0]
    if not w or not ls:
        return None
    aw, al = statistics.fmean(w), -statistics.fmean(ls)
    if al <= 0:
        return None
    rr = aw / al
    win = len(w) / len(rows)
    be = 1.0 / (1.0 + rr)
    return win, rr, be, 100 * (win - be)


def cell2(rows):
    sh = shape(rows)
    if len(rows) < 40 or sh is None:
        return f"{'—':>17}"
    win, rr, _, margin = sh
    return f"{win:>6.0%}{rr:>6.2f}{margin:>+5.1f}"


def cell3(rows):
    if len(rows) < 40:
        return f"{'—':>19}"
    rs = [t.r for t in sorted(rows, key=lambda x: x.exit_t)]
    dd, _ = drawdown(rs)
    return f"{sum(rs):>+7.1f}{dd:>6.1f}{sum(rs) / dd if dd else 0:>6.2f}"


def grid(name, rows):
    print(f"\n-- {name} " + "-" * max(0, 74 - len(name)))
    print(f"  {'':<18}" + "".join(f"{z:>18}" for z, _ in ZONES))
    for label, keep in POIS:
        got = [t for t in rows if keep(t)]
        print(f"  {label:<18}" + "".join(cell([t for t in got if z(t)])
                                        for _, z in ZONES))
    print("  R/bet ± SE (bets). a dash means under 25 bets.")

    print(f"\n  {'':<18}" + "".join(f"{z:>17}" for z, _ in ZONES))
    print(f"  {'':<18}" + "".join(f"{'win':>6}{'RR':>6}{'±BE':>5}"
                                  for _ in ZONES))
    for label, keep in POIS:
        got = [t for t in rows if keep(t)]
        print(f"  {label:<18}" + "".join(cell2([t for t in got if z(t)])
                                        for _, z in ZONES))
    print("  win rate and realised RR over TRADES, and win rate MINUS the")
    print("  break-even 1/(1+RR), in points. positive margin = positive cell.")

    print(f"\n  {'':<18}" + "".join(f"{z:>19}" for z, _ in ZONES))
    print(f"  {'':<18}" + "".join(f"{'total':>7}{'maxDD':>6}{'recov':>6}"
                                  for _ in ZONES))
    for label, keep in POIS:
        got = [t for t in rows if keep(t)]
        print(f"  {label:<18}" + "".join(cell3([t for t in got if z(t)])
                                        for _, z in ZONES))
    print("  total R, peak-to-trough drawdown in R, and total/maxDD. the")
    print("  drawdown is on the R curve in EXIT order, so it is what a")
    print("  one-unit-per-trade account would have lived through.")


def test(label, a, b, shapes=False):
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
    if not shapes:
        return
    # WHICH HALF OF THE EDGE MOVED. R per trade is (win - breakeven) times the
    # average round trip, so a difference in R has to show up as a difference
    # in win rate, in RR, or in both — and which one it is says what changed.
    sa_, sb_ = shape(a), shape(b)
    if sa_ and sb_:
        print(f"  {'':<46}{sa_[0]:>6.0%} vs {sb_[0]:>6.0%} win   "
              f"{sa_[1]:>5.2f} vs {sb_[1]:>5.2f} RR   "
              f"{sa_[3]:>+5.1f} vs {sb_[3]:>+5.1f} margin")


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

    print("\n== PRIMARY: does the band survive inside each POI arm? "
          + "=" * 21)
    for name, sk in STREAMS:
        s = [t for t in rows if sk(t)]
        print(f"\n  {name}")
        for label, pk in POIS:
            got = [t for t in s if pk(t)]
            inb = [t for t in got if LO <= t.risk_pct <= HI]
            out = [t for t in got if not (LO <= t.risk_pct <= HI)]
            test(f"    {label}: band vs outside", inb, out,
                 shapes=(label in ("no POI at all", "in 8h zone (LIVE)")))

    print("\n== SECONDARY: inside the band, does the POI add anything? "
          + "=" * 18)
    for name, sk in STREAMS:
        s = [t for t in rows if sk(t) and LO <= t.risk_pct <= HI]
        print(f"\n  {name}  ({len(s)} trades in the band)")
        test("    8h zone vs no 8h zone",
             [t for t in s if t.h8], [t for t in s if not t.h8], shapes=True)
        test("    daily zone vs no daily zone",
             [t for t in s if t.day], [t for t in s if not t.day], shapes=True)
        test("    both zones vs neither",
             [t for t in s if t.h8 and t.day],
             [t for t in s if not t.h8 and not t.day])

    verdict(rows)


def policy(name, rows, everything):
    """One candidate 1h stream, priced the way an account experiences it."""
    if len(rows) < 40:
        return
    rs = [t.r for t in sorted(rows, key=lambda x: x.exit_t)]
    dd, under = drawdown(rs)
    b = bets_of(rows)
    m, se = mean_se(b)
    sh = shape(rows)
    win, rr, _, margin = sh if sh else (0.0, 0.0, 0.0, 0.0)
    # Per 120 symbols, the deployed universe, not the 59 measured here.
    perday = len(rows) / DAYS / 59 * 120
    _, ddu, _ = compound(rows)
    bal, ddc, skipped = compound(rows, max_open=10)
    print(f"  {name:<24}{perday:>6.1f}{m:>+8.3f}±{se:.3f}{sum(rs):>+8.1f}"
          f"{dd:>7.1f}{sum(rs) / dd if dd else 0:>7.2f}{win:>6.0%}{rr:>6.2f}"
          f"{margin:>+6.1f}{100 * (bal / START - 1):>+8.0f}%{ddc:>6.0%}")


def verdict(rows):
    print("\n== IS THE 1h STREAM WORTH IT " + "=" * 47)
    print("  every row is the SAME 333 days and the same 59 symbols, on the")
    print("  same engine. /day is scaled to the 120-symbol live universe.")
    print("  acct% and accDD compound 300 USDT at 1% risk with at most 10")
    print("  positions open at once — the constraint a small account actually")
    print("  hits, and the number that killed the unfiltered Min30 stream.")
    print(f"\n  {'policy':<24}{'/day':>6}{'R/bet':>16}{'total':>8}"
          f"{'maxDD':>7}{'recov':>7}{'win':>6}{'RR':>6}"
          f"{'±BE':>6}{'acct':>9}{'accDD':>6}")
    inband = [t for t in rows if LO <= t.risk_pct <= HI]
    everything = rows
    policy("everything", rows, everything)
    policy("POI on (= deployed)", [t for t in rows if t.h8], everything)
    policy("band only, no POI", inband, everything)
    policy("band + POI on", [t for t in inband if t.h8], everything)
    policy("band, confirmed only",
           [t for t in inband if t.kind == "confirmed"], everything)
    policy("band, early only",
           [t for t in inband if t.kind == "early"], everything)

    # POST HOC AND LABELLED AS SUCH. These rows exist because the grid showed
    # the TIGHT zone alive on Min60 (+0.153 on 619 bets) where it is flat on
    # Min30, which would mean only the band's UPPER boundary is doing work
    # here. Choosing a policy after seeing that is exactly the selection this
    # file warns about in its opening paragraph, so the rows are printed to be
    # measured forward, not to be shipped off this table.
    print("\n  post hoc — chosen AFTER seeing the grid, not pre-registered:")
    policy("not wide (<2.6%)", [t for t in rows if t.risk_pct <= HI],
           everything)
    policy("tight only (<1.2%)", [t for t in rows if t.risk_pct < LO],
           everything)
    policy("wide only (>2.6%)", [t for t in rows if t.risk_pct > HI],
           everything)
    policy("not wide + POI on",
           [t for t in rows if t.risk_pct <= HI and t.h8], everything)


if __name__ == "__main__":
    asyncio.run(main())
