"""Everything crossed: 15m/30m/1h x early/confirmed x risk band x POI.

THE ONE TABLE THIS PROJECT HAS BEEN CIRCLING, AND THE ONE MOST LIKELY TO BE
MISREAD. Three timeframes by two streams by three risk zones by four POI arms
is seventy-two cells drawn from roughly seven thousand bets. Somebody will look
at it and pick the biggest number. That number will be noise. Read the rules
below before the tables or do not read the tables.

RULE 1 — THE TIMEFRAMES ARE NOT THREE SAMPLES. Same 59 symbols, same 333 days,
same market. A 15m raid and the 1h raid containing it are frequently the same
event read at two resolutions. "It replicates on 3 of 3 timeframes" is ONE
observation seen three times, and it is worth much less than it looks. What the
three rows DO buy is a robustness check: an effect that reverses sign between
resolutions was never real.

RULE 2 — WITHIN-TIMEFRAME CONTRASTS ARE THE EVIDENCE; ACROSS-TIMEFRAME CELL
COMPARISONS ARE NOT. timeframes.py already established that no pair of
timeframes separates at even 1 SE on overall R per bet. Nothing in a finer
slice of the same data can fix that — slicing only shrinks the arms. So "who
wins on early" has an honest answer and it is "nobody, measurably", and the
useful question underneath it is "does the same FILTER work on all three".

RULE 3 — READ NET AND GROSS TOGETHER. Fee in R is fee_pct / risk_pct and the
median stop doubles from Min15 to Min60, so the lower timeframes pay far more
of their edge away. timeframes.py found gross Min15 and gross Min30 identical
at +0.054 and +0.055 while net was +0.018 and +0.030. A timeframe that looks
worse NET may be finding exactly the same thing and simply paying for it. Both
columns are printed for every cell.

RULE 4 — DISTRUST LEVELS, READ DIFFERENCES. The universe is the symbols liquid
TODAY walked back a year, so every level carries a survivorship premium. A
difference between two arms measured on the same rows is largely common-mode on
that bias. Levels rank; differences decide.

RULE 5 — COUNT THE COMPARISONS. This file runs about thirty contrasts. At the
usual threshold one or two will clear 2 SE by chance alone, so a lone
"SEPARATES" on a cell nobody predicted is not a finding. The pre-registered
ones are marked; the rest are labelled descriptive.

ONE POOL PER TIMEFRAME, NO POI FILTER ANYWHERE. Every A/B signal is collected
once and each POI definition applied as a LABEL, so no arm sees a signal
another arm does not. Identical pipeline to poi_tf.py, imported rather than
copied — the interval is a parameter of that one collect().

THE POI IS READ ON Hour8 IN PRODUCTION. It has been since 9 Sep; see poi_tf.py.
"daily" below is the alternative, not the status quo.

PRE-REGISTERED, BEFORE THE FIRST NUMBER

  PRIMARY. Does the risk band (1.2-2.6%, survivor.py's boundaries, NOT
  refitted) separate band from outside on all three timeframes and both
  streams? Six tests, each two-arm within one timeframe.

  SECONDARY. Does the POI separate in-zone from out-of-zone on any timeframe or
  stream? Twelve tests (3 tf x 2 streams x 2 POI definitions).

  TERTIARY. Confirmed against early, per timeframe. The bot treats these as one
  stream with a label; if one is reliably better the label should be a filter.

  EXPECTATION. The band separates on Min30 (where it was fitted) and holds with
  the same sign on Min15 and Min60; poi_tf.py and poi_risk.py say it will. The
  POI separates on Min15 and Min30 — MEASUREMENTS.md records Min15 going from
  -0.095 to +0.417 inside one, which is the single largest effect on file — and
  fails on Min60, where three framings have already found nothing. If the POI
  fails on Min15 TOO, the filter is in trouble everywhere and not just on 1h,
  and that would be the most consequential result this project has produced.

    PYTHONPATH=. RIPTIDE_MIN_GRADE=B RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/matrix.py

RESULT, 11 Sep 2026 — THE BAND REPLICATES SIX TIMES OUT OF SIX. THE POI
REPLICATES IN ONE CELL ONLY, AND THIS FILE FIRST READ THAT AS ZERO; SEE THE
CORRECTION BELOW BEFORE QUOTING THE POI SUMMARY.

59 symbols, 333 days. 17104 / 9198 / 4723 filled trades on 15m / 30m / 1h;
8022 / 4097 / 2037 bets. Every A/B signal, no POI filter anywhere.

THE PRE-REGISTERED PRIMARY: THE BAND, band against outside, per tf per stream.

    15m confirmed  +0.064 vs +0.037   +0.026  |z| 0.4
    30m confirmed  +0.167 vs -0.016   +0.184  |z| 2.1  SEPARATES
    1h  confirmed  +0.235 vs +0.009   +0.226  |z| 2.0  SEPARATES
    15m early      +0.034 vs +0.031   +0.002  |z| 0.1
    30m early      +0.095 vs +0.075   +0.020  |z| 0.5
    1h  early      +0.180 vs +0.072   +0.108  |z| 1.9
    -> 6/6 positive, median +0.067

Six for six, and nothing was refitted: 1.2/2.6 comes from Min30 confirmed and
was applied unchanged to 15m and 1h and to early. The honest qualifier is that
the effect is concentrated — it is large on 30m and 1h confirmed and nearly
absent on 15m, where band and outside differ by +0.026 and +0.002. The band is
strong on the slower streams and not visibly doing anything on the fastest.

THE PRE-REGISTERED SECONDARY: THE POI, in-zone against out-of-zone.

    live 8h POI     2/6 positive, median -0.036, one row 2 SE AGAINST it
    daily POI       2/6 positive, median -0.040, none significant
    both vs neither 2/6 positive, median -0.076, one row at 2 SE AGAINST it

Eighteen contrasts. Twelve negative. The only two that clear 2 SE both point
against the filter (30m early, in-zone +0.032 against out-of-zone +0.117, and
both-contexts +0.002 against neither +0.116). My pre-registration named this
exact outcome and what it would mean: "If the POI fails on Min15 TOO, the
filter is in trouble everywhere and not just on 1h, and that would be the most
consequential result this project has produced." It failed on all three.

CORRECTION, ADDED 11 SEP AFTER poi_recheck.py — THE SUMMARY ABOVE IS THE WRONG
READING OF ITS OWN ROWS. Two errors, both mine. The table's primary is the LIVE
8h POI, and the POI's provenance is DAILY; on Min30 confirmed the daily gap is
+0.160 where the 8h gap is +0.006. And taking a median across six rows buries
one strong cell under five flat ones when five of the six are early or 15m.
poi_recheck.py rebuilds the original 2x2 on these rows and finds Min30
confirmed with POI and trend at +0.174 +/- 0.084 against +0.014 for trend
alone — the original's ordering preserved exactly, at a quarter of its reported
size, and positive in 6 of 8 non-overlapping 42-day windows. The POI is not
dead. It is alive in one cell, the cell it was built on, at Day1, and flat
everywhere else — which on this bot is about 80% of the stream, because early
signals dominate it. Read the rows below with that correction.

SAY WHAT THIS IS AND IS NOT. It is NOT a significant negative — under rule 5,
two 2 SE rows out of thirty contrasts is what chance produces, and the eighteen
rows are heavily correlated, so call it three to six independent looks all
leaning the same way. It IS a comprehensive failure to reproduce. The POI is on
record as "the single largest separation measured here and the only filter to
pass a pre-registered held-out test", measured over 42 days on 14 symbols with
9 held out. On 333 days and 59 symbols it shows no benefit anywhere, and the
daily arm tested here is the ORIGINAL configuration — 30-bar life, Day1 — so
this is not an artefact of the 9 Sep move to Hour8.

THE PRECEDENT IS EXACT AND IT IS IN THIS REPOSITORY. entry_deep.py re-ran the
42-day entry study on 333 days and the two leading entries came back as the two
WORST on the board at -5.0 and -4.7 SE. Nothing was wrong with those studies
except the sample. The POI is now the leading candidate for the same story, and
it is the most expensive setting the bot has: it halves the stream.

THE PRE-REGISTERED TERTIARY: CONFIRMED AGAINST EARLY. Nothing, anywhere.
+0.027 / -0.022 / +0.000 on all signals, |z| 0.7 / 0.4 / 0.0; inside the band
+0.030 / +0.073 / +0.055, |z| 0.5 / 1.0 / 0.6. Confirmed leads in five of six
and clears 1 SE in none. Early is not worse; it is not better either.

WHO WINS, TIMEFRAME BY TIMEFRAME — nobody, measurably, and 1h nominally. 1h has
the highest R per bet in eight of twelve cells and the ordering 15m < 30m < 1h
holds in nine of twelve, but NOT ONE CELL has a spread exceeding its own MDE.
The closest is early/band, spread 0.146 against MDE 0.163. Read rule 2: this is
the same non-result timeframes.py reached, re-confirmed at finer slicing, which
is what finer slicing always does to it.

    stream     zone         15m      30m       1h   spread    MDE
    confirmed  band      +0.064   +0.167   +0.235    0.171  0.336
    early      band      +0.034   +0.095   +0.180    0.146  0.163
    both       ALL       +0.036   +0.089   +0.125    0.088  0.115

GROSS SAYS THE GRADIENT IS NOT ONLY THE FEE. Net 15m/30m/1h on all signals is
+0.036 / +0.089 / +0.125 and gross is +0.072 / +0.114 / +0.141. The fee
explains about half the 15m deficit and none of the 30m-to-1h step. Note this
DISAGREES with timeframes.py, which found gross Min15 and Min30 identical at
+0.054 and +0.055 — because that study ran POI-FILTERED and this one does not.
The POI costs 30m more than it costs 15m, which is one more way of saying the
same thing as the section above.

RR IS A CONSTANT AND THE WIDE TAIL IS WHERE IT BREAKS. Every tight and band
cell on every timeframe sits between 1.75 and 1.91; every wide cell between
1.62 and 1.79. Mechanical: the target is 2R, so a wide stop needs a move that
often does not arrive inside the horizon, and the trade times out below 2R.
Win rate is 33-42% everywhere. The break-even margin is the whole story — 1h
confirmed band is 42% win against a 34.6% break-even, +7.5 points; 15m early
band is 37% against 36.4%, +0.4 points, which is why it earns nothing.

THE POLICY TABLE, and the starred rows are not policies.

Grades here hold poi=True so the A/B floor is constant across arms. Production
grades on the REAL poi and the table is asymmetric: a confirmed signal with no
zone falls A->B and still sends, an early one falls B->C and is muted at
MIN_GRADE=B. So POI_REQUIRED=0 releases the confirmed-with-no-zone signals and
nothing else. The achievable comparison is "POI off, regraded" vs "POI on":

    15m  POI off regraded  52.2/day  +0.031  +34.3 R   acct -68%
    15m  POI on   (live)   44.1/day  +0.018   -7.3 R   acct -77%
    30m  POI off regraded  30.4/day  +0.040 +208.3 R   acct  +5%
    30m  POI on   (live)   26.4/day  +0.030 +147.2 R   acct -44%
    1h   POI off regraded  16.9/day  +0.092 +197.2 R   acct +79%
    1h   POI on   (live)   14.6/day  +0.088 +158.1 R   acct +140%

Better on R per bet and total R in all three, never significantly, and WORSE on
the compounded account on 1h — more trades means more refused at the ten-
position cap and a different path. Turning the filter off is not the obvious
win the in-zone-against-out-of-zone rows suggest.

THE NUMBER THAT MATTERS MOST IN THIS FILE. What the bot sends TODAY — three
timeframes, POI on, everything above grade C — compounds a 300 USDT account at
1% risk with at most ten open to MINUS 88% at a 97% drawdown. Not "modest".
Untradeable. The unfiltered version is +59% at 92%, which is also untradeable.
The alert stream at 85 a day is a watchlist, and reading it as a trade list
loses the account.

    15m+30m+1h POI on (LIVE)  85.1/day  +0.039  +298.0 R  DD 373.5  acct -88%
    15m+30m+1h band only*     68.7/day  +0.104  +652.6 R  DD 245.4  acct +925%
    15m+30m+1h band + POI     31.7/day  +0.062  +266.5 R  DD 139.9  acct +158%
    15m+30m+1h band, confd    10.8/day  +0.137  +237.1 R  DD  44.2  acct +420%
    30m+1h band, POI off      21.1/day  +0.110  +277.2 R  DD 102.4  acct +301%
    1h band, confirmed         2.2/day  +0.235   +78.0 R  DD  19.0  acct +103%

Cross-timeframe bets are keyed on the floored hour so a raid printing on two
resolutions counts once; keying on the raw timestamp inflated the combined
R/bet upward by pretending to an independence that is not there.

THE BEST POLICY IN THIS TABLE IS ONE THE BOT ALREADY LABELS. "band, confirmed"
across all three timeframes: 10.8 alerts a day, +0.137 R per bet, a 5.37
recovery factor — the highest anywhere in this project — and a 33% account
drawdown against 97% for what is sent today. It needs no code: the alert
already prints "take" and already says CONFIRMED. It is a reading discipline,
not a feature.

AND IT IS STILL A SELECTION FROM A TABLE. The band half is pre-registered and
replicated 6/6. The confirmed half is NOT: confirmed beats early inside the
band on all three timeframes and clears 1 SE on none of them, so "confirmed
only" is chosen here because it looks best and because fewer, less correlated
trades is a mechanism that makes sense — not because it was demonstrated. Read
the account column as a ranking, never a forecast (rule 4): every level carries
the survivorship premium of walking today's liquid symbols back a year.
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
from research.studies.report import (START, compound,   # noqa: E402
                                     drawdown)          # noqa: E402
from research.studies.survivor import LO, HI            # noqa: E402

TFS = ("Min15", "Min30", "Min60")
SHORT = {"Min15": "15m", "Min30": "30m", "Min60": "1h"}
ZONES = (("tight", lambda t: t.risk_pct < LO),
         ("band", lambda t: LO <= t.risk_pct <= HI),
         ("wide", lambda t: t.risk_pct > HI),
         ("ALL", lambda t: True))
STREAMS = (("confirmed", lambda t: t.kind == "confirmed"),
           ("early", lambda t: t.kind == "early"),
           ("both", lambda t: True))
NSYM = 59
HOUR = 3600                    # the slowest scanned bar, for cross-tf bets


def regrade(rows):
    """What POI_REQUIRED=0 would ACTUALLY send at MIN_GRADE=B.

    engine.GRADES is asymmetric in the POI axis. Without a zone a confirmed
    signal is B and still sends; an early one is C and is muted. So turning
    the filter off adds the confirmed signals that have no zone and nothing
    else — a far smaller change than the unfiltered pool suggests, and the
    only version of "POI off" that is a real option.
    """
    return [t for t in rows if t.kind == "confirmed" or t.h8]


def bets_of(rows, gross=False, bucket=0):
    """Mean R over every trade firing on one bar. `bucket` coarsens the key.

    WITHIN one timeframe the detected_time IS the bar and bucket stays 0.
    ACROSS timeframes it is not: a Min15 signal at 10:15 and the Min60 signal
    at 10:00 that contains it are the same raid with different timestamps, so
    keying on the raw time would count one idea as two bets and shrink the
    standard error of the combined stream by pretending to independence it
    does not have. For the combined rows the key is floored to the slowest
    bar instead.
    """
    g = defaultdict(list)
    for t in rows:
        k = t.t - (t.t % bucket) if bucket else t.t
        g[k].append(t.gross if gross else t.r)
    return [statistics.fmean(g[k]) for k in sorted(g)]


def shape(rows):
    """(win, realised RR, break-even, margin in points) over TRADES."""
    w = [t.r for t in rows if t.r > 0]
    ls = [t.r for t in rows if t.r <= 0]
    if not w or not ls:
        return None
    aw, al = statistics.fmean(w), -statistics.fmean(ls)
    if al <= 0:
        return None
    rr = aw / al
    win = len(w) / len(rows)
    return win, rr, 1 / (1 + rr), 100 * (win - 1 / (1 + rr))


def money(tf, stream, zone, rows):
    if len(rows) < 40:
        print(f"  {SHORT[tf]:<5}{stream:<11}{zone:<7}{len(rows):>6}"
              f"   too thin")
        return
    b = bets_of(rows)
    m, se = mean_se(b)
    g, _ = mean_se(bets_of(rows, gross=True))
    rs = [t.r for t in sorted(rows, key=lambda x: x.exit_t)]
    dd, _ = drawdown(rs)
    print(f"  {SHORT[tf]:<5}{stream:<11}{zone:<7}{len(b):>6}"
          f"{m:>+8.3f}±{se:.3f}{g:>+8.3f}{sum(rs):>+8.1f}{dd:>7.1f}"
          f"{sum(rs) / dd if dd else 0:>7.2f}")


def form(tf, stream, zone, rows):
    sh = shape(rows) if len(rows) >= 40 else None
    if sh is None:
        return
    win, rr, _, margin = sh
    print(f"  {SHORT[tf]:<5}{stream:<11}{zone:<7}{len(rows):>7}"
          f"{len(rows) / DAYS / NSYM * 120:>7.1f}{win:>7.0%}{rr:>7.2f}"
          f"{margin:>+7.1f}")


def contrast(label, a, b, pre=False):
    """Two arms of the SAME pool. Never an arm against the pool."""
    if len(a) < 30 or len(b) < 30:
        print(f"  {label:<44}      too thin ({len(a)}/{len(b)})")
        return None
    ba, bb = bets_of(a), bets_of(b)
    ma, sa = mean_se(ba)
    mb, sb = mean_se(bb)
    se = (sa ** 2 + sb ** 2) ** 0.5
    z = abs(ma - mb) / se if se else 0.0
    sd = statistics.pstdev(ba + bb)
    n = min(len(ba), len(bb))
    print(f"  {label:<44}{ma:>+7.3f} vs {mb:>+7.3f}  diff {ma - mb:>+6.3f}"
          f"  |z| {z:>4.1f}  MDE {mde(sd, n):>5.3f}"
          + ("  SEPARATES" if z >= 2 else ""))
    return ma - mb, z


def replicate(name, rows_by_tf, pick_a, pick_b, pre=False):
    """The same two-arm question asked on every timeframe and stream.

    This is the shape of evidence that survives rule 1: not "the effect is
    large somewhere" but "the effect keeps its SIGN when the resolution
    changes". A row that flips sign was never real.
    """
    tag = "   [pre-registered]" if pre else "   [descriptive]"
    print(f"\n  {name}{tag}")
    got = []
    for stream, sk in STREAMS[:2]:
        for tf in TFS:
            rows = [t for t in rows_by_tf[tf] if sk(t)]
            r = contrast(f"    {SHORT[tf]:<4} {stream:<10}",
                         [t for t in rows if pick_a(t)],
                         [t for t in rows if pick_b(t)])
            if r:
                got.append(r)
    if got:
        pos = sum(1 for d, _ in got if d > 0)
        sep = sum(1 for _, z in got if z >= 2)
        print(f"    -> {pos}/{len(got)} positive, {sep} clear 2 SE. "
              f"median diff {statistics.median(d for d, _ in got):+.3f}")


def policy(name, rows, bucket=0):
    if len(rows) < 40:
        return
    rs = [t.r for t in sorted(rows, key=lambda x: x.exit_t)]
    dd, _ = drawdown(rs)
    m, se = mean_se(bets_of(rows, bucket=bucket))
    sh = shape(rows) or (0, 0, 0, 0)
    bal, ddc, _ = compound(rows, max_open=10)
    print(f"  {name:<26}{len(rows) / DAYS / NSYM * 120:>6.1f}"
          f"{m:>+8.3f}±{se:.3f}{sum(rs):>+8.1f}{dd:>7.1f}"
          f"{sum(rs) / dd if dd else 0:>7.2f}{sh[0]:>6.0%}{sh[1]:>6.2f}"
          f"{100 * (bal / START - 1):>+8.0f}%{ddc:>6.0%}")


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
            rows = await collect(sess, cs, zday, z8h, interval=tf)
            by_tf[tf] = [t for t in rows
                         if t.filled and t.exit_t is not None]

    print(f"THE FULL CROSS: TIMEFRAME x STREAM x RISK BAND x POI\n"
          f"{len(syms)} symbols, {DAYS} days, identical set on every row, no "
          f"POI filter applied.\nband boundaries {LO}/{HI} are survivor.py's, "
          f"fitted on Min30 confirmed and NOT\nrefitted. the live POI is "
          f"Hour8; 'daily' is the alternative, not the status quo.")
    for tf in TFS:
        b = bets_of(by_tf[tf])
        print(f"  {SHORT[tf]:<4} {len(by_tf[tf]):>5} filled trades, "
              f"{len(b):>4} bets, sd {statistics.pstdev(b):.2f}, "
              f"cell-vs-cell MDE at 200 bets "
              f"{mde(statistics.pstdev(b), 200):.3f}")

    print("\n== THE MONEY TABLE " + "=" * 57)
    print(f"  {'tf':<5}{'stream':<11}{'zone':<7}{'bets':>6}{'NET R/bet':>16}"
          f"{'GROSS':>8}{'total':>8}{'maxDD':>7}{'recov':>7}")
    for tf in TFS:
        for stream, sk in STREAMS:
            for zone, zk in ZONES:
                money(tf, stream, zone,
                      [t for t in by_tf[tf] if sk(t) and zk(t)])
        print()

    print("== THE SHAPE TABLE " + "=" * 57)
    print(f"  {'tf':<5}{'stream':<11}{'zone':<7}{'trades':>7}{'/day':>7}"
          f"{'win':>7}{'RR':>7}{'±BE':>7}")
    for tf in TFS:
        for stream, sk in STREAMS:
            for zone, zk in ZONES:
                form(tf, stream, zone,
                     [t for t in by_tf[tf] if sk(t) and zk(t)])
        print()

    print("== DOES IT REPLICATE ACROSS RESOLUTIONS " + "=" * 36)
    print("  the same two-arm question asked six times. sign stability is the")
    print("  evidence; significance on any one row is not, see rules 1 and 5.")
    replicate("THE RISK BAND: in band vs outside it",
              by_tf, lambda t: LO <= t.risk_pct <= HI,
              lambda t: not (LO <= t.risk_pct <= HI), pre=True)
    replicate("THE LIVE POI: in an 8h zone vs not in one",
              by_tf, lambda t: t.h8, lambda t: not t.h8, pre=True)
    replicate("THE ALTERNATIVE POI: in a daily zone vs not",
              by_tf, lambda t: t.day, lambda t: not t.day, pre=True)
    replicate("BOTH CONTEXTS vs NEITHER",
              by_tf, lambda t: t.h8 and t.day,
              lambda t: not t.h8 and not t.day)
    replicate("INSIDE THE BAND ONLY: 8h zone vs not",
              {k: [t for t in v if LO <= t.risk_pct <= HI]
               for k, v in by_tf.items()},
              lambda t: t.h8, lambda t: not t.h8)

    print("\n== CONFIRMED AGAINST EARLY, PER TIMEFRAME   [pre-registered] "
          + "=" * 15)
    for tf in TFS:
        contrast(f"    {SHORT[tf]:<4} all signals",
                 [t for t in by_tf[tf] if t.kind == "confirmed"],
                 [t for t in by_tf[tf] if t.kind == "early"])
    for tf in TFS:
        b = [t for t in by_tf[tf] if LO <= t.risk_pct <= HI]
        contrast(f"    {SHORT[tf]:<4} inside the band",
                 [t for t in b if t.kind == "confirmed"],
                 [t for t in b if t.kind == "early"])

    print("\n== WHO WINS, CELL BY CELL   [descriptive, rule 2] "
          + "=" * 25)
    print("  the best timeframe in each cell, and whether it beats the worst")
    print("  by more than the MDE. it almost never does.")
    print(f"  {'stream':<11}{'zone':<7}{'15m':>9}{'30m':>9}{'1h':>9}"
          f"{'best':>7}{'spread':>8}{'MDE':>7}")
    for stream, sk in STREAMS:
        for zone, zk in ZONES:
            vals, sds, ns = {}, [], []
            for tf in TFS:
                g = [t for t in by_tf[tf] if sk(t) and zk(t)]
                if len(g) < 40:
                    continue
                b = bets_of(g)
                vals[tf] = statistics.fmean(b)
                sds.append(statistics.pstdev(b))
                ns.append(len(b))
            if len(vals) < 3:
                continue
            best = max(vals, key=vals.get)
            spread = max(vals.values()) - min(vals.values())
            m = mde(statistics.fmean(sds), min(ns))
            print(f"  {stream:<11}{zone:<7}"
                  + "".join(f"{vals[tf]:>+9.3f}" for tf in TFS)
                  + f"{SHORT[best]:>7}{spread:>8.3f}{m:>7.3f}"
                  + ("  REAL" if spread > m else ""))

    print("\n== THE POLICY TABLE, PER TIMEFRAME " + "=" * 41)
    print("  300 USDT at 1% risk, at most 10 open. /day per 120 symbols.")
    print("  acct is a RANKING, never a forecast — see rule 4.")
    print("\n  * IS NOT A POLICY YOU CAN SELECT. Grades here hold poi=True so")
    print("  the A/B floor is constant across arms. Production grades on the")
    print("  REAL poi and the table is asymmetric: a CONFIRMED signal with no")
    print("  zone falls A->B and still sends, an EARLY one falls B->C and is")
    print("  muted at MIN_GRADE=B. So POI_REQUIRED=0 does not release the")
    print("  starred row — it releases the confirmed-with-no-zone signals and")
    print("  nothing else. That achievable stream is the 'regraded' row, and")
    print("  it is the one to compare against 'POI on'.")
    print(f"\n  {'policy':<26}{'/day':>6}{'R/bet':>16}{'total':>8}{'maxDD':>7}"
          f"{'recov':>7}{'win':>6}{'RR':>6}{'acct':>9}{'accDD':>6}")
    for tf in TFS:
        rows = by_tf[tf]
        band = [t for t in rows if LO <= t.risk_pct <= HI]
        policy(f"{SHORT[tf]}  everything*", rows)
        policy(f"{SHORT[tf]}  POI off, regraded", regrade(rows))
        policy(f"{SHORT[tf]}  POI on (live)", [t for t in rows if t.h8])
        policy(f"{SHORT[tf]}  band only*", band)
        policy(f"{SHORT[tf]}  band, POI off regr.", regrade(band))
        policy(f"{SHORT[tf]}  band + POI on", [t for t in band if t.h8])
        policy(f"{SHORT[tf]}  band, confirmed",
               [t for t in band if t.kind == "confirmed"])
        print()

    print("== THE COMBINED STREAM " + "=" * 53)
    print("  what the bot would actually send with all three timeframes on.")
    print("  CLUSTERING ACROSS TIMEFRAMES IS REAL and the raw timestamps do")
    print("  not capture it — a 15m signal at 10:15 and the 1h signal at")
    print("  10:00 containing it are one raid with two times. Bets below are")
    print("  therefore keyed on the floored HOUR, so a duplicate counts once")
    print("  and the standard errors do not borrow independence that is not")
    print("  there. Rows marked * are not selectable; see the note above.")
    allrows = [t for tf in TFS for t in by_tf[tf]]
    band = [t for t in allrows if LO <= t.risk_pct <= HI]
    print(f"\n  {'policy':<26}{'/day':>6}{'R/bet':>16}{'total':>8}{'maxDD':>7}"
          f"{'recov':>7}{'win':>6}{'RR':>6}{'acct':>9}{'accDD':>6}")
    policy("15m+30m+1h everything*", allrows, HOUR)
    policy("15m+30m+1h POI off regr.", regrade(allrows), HOUR)
    policy("15m+30m+1h POI on (LIVE)", [t for t in allrows if t.h8], HOUR)
    policy("15m+30m+1h band only*", band, HOUR)
    policy("15m+30m+1h band POI off", regrade(band), HOUR)
    policy("15m+30m+1h band + POI", [t for t in band if t.h8], HOUR)
    policy("15m+30m+1h band, confd",
           [t for t in band if t.kind == "confirmed"], HOUR)
    print()
    policy("30m+1h band, POI off", regrade(
        [t for t in band if t.tf in ("Min30", "Min60")]), HOUR)
    policy("30m+1h band + POI on",
           [t for t in band if t.tf in ("Min30", "Min60") and t.h8], HOUR)
    policy("1h band + POI on",
           [t for t in band if t.tf == "Min60" and t.h8], HOUR)
    policy("1h band, confirmed",
           [t for t in band if t.tf == "Min60"
            and t.kind == "confirmed"], HOUR)


if __name__ == "__main__":
    asyncio.run(main())
