"""Which timeframe should the point of interest be read on, for a 1h setup?

THE FIRST ANSWER IS THAT THE PREMISE OF THE QUESTION IS WRONG, AND SO WAS MINE.
The POI is ALREADY read on Hour8. It has been since 9 Sep, when TREND_INTERVAL
moved Day1 -> Hour8 for the SuperTrend and silently took the point of
interest with it: trend.poi_at reads TREND_INTERVAL, not a key of its own.
Nothing in the repository says so: poi_at's docstring still opens "Did the raid
land inside an aligned DAILY order block", the builder is still called
daily_zones, config.py says "daily POI" in six places — and engine._POI, the
string printed on every alert's grade line, is literally "daily POI". The bot
tells its user daily and means 8h.

Verified rather than inferred: poi_at agrees with an Hour8 / 30-bar lookup on
100.0% of 1038 signals across BTC, SOL and ONDO, and with a Day1 / 30-bar
lookup on 62%. This study was designed believing Day1 was the incumbent, so
read its "8h" column as the STATUS QUO and its "daily" column as the change.

THE RATIO ARGUMENT THAT MOTIVATED THE STUDY SURVIVES, POINTED THE OTHER WAY.
A Min30 structure against a Day1 context is 48 structure bars to one context
bar. Against Hour8 it is 16:1, and a Min60 structure against Hour8 is 8:1 —
by far the tightest context this project has run, and it got there by accident
rather than by measurement. Whether that is too tight is exactly what the arms
below test.

TWO THINGS CHANGE AT ONCE WHEN THE POI TIMEFRAME MOVES, AND SEPARATING THEM IS
MOST OF THE VALUE OF THIS STUDY.

  GRANULARITY. Hour8 has three times as many bars in the same span, so it
  builds more zones and each is narrower (311 against 117 on BTC over 420
  days). Whether that raises or lowers the fraction of raids landing in one is
  genuinely not obvious in advance.

  LIFETIME. POI_MAX_AGE_BARS is 30 and it is counted in BARS of the POI
  timeframe, so a daily zone lives thirty days and an 8h zone lives TEN. The
  9 Sep change therefore shortened the memory of the filter by two thirds as a
  side effect, and engine.py's own note says the thirty-day life is a measured
  parameter whose unconstrained version "pointed the WRONG way". So Hour8 is
  run at two lifetimes: 30 bars (10 days, what is deployed) and 90 bars (30
  days, the daily lifetime held fixed). Only the second isolates granularity.

ONE SIGNAL POOL, SEVERAL LABELS. Every Min60 A/B signal on the same 59 symbols
and the same 333 days as timeframes.py is collected ONCE with no POI filter at
all, and each POI definition is then applied as a label to that one pool. No
arm sees a signal another arm does not.

COMPARE AN ARM TO ITS COMPLEMENT, NEVER TO THE POOL. A subset and the pool
containing it are not two samples; an independent-SE z on that pair is
meaningless and biased toward zero. Every filter question below is asked as
in-zone against OUT-of-zone.

WHAT IS HELD FIXED: engine, config, A/B grade floor, near-edge entry,
raid-extreme stop, 2R target, the same symbols as timeframes.py.

PRE-REGISTERED, BEFORE THE FIRST NUMBER

  POWER FIRST. Expect roughly 9000 signals and ~3500 bets in the unfiltered
  pool; a filter keeping a third leaves ~1200 bets against ~2300, and the MDE
  for that split at sd 1.4 is about 0.13 R. The POI effect on record is large
  (Min15 went from -0.095 to +0.417 inside one), so filter-versus-nothing is
  answerable. The 8h-versus-daily question is NOT independent of it: the two
  labels overlap heavily by construction, so their difference is small and
  correlated, and I expect it to land inside noise. Say so either way.

  PRIMARY. R per bet for "in an 8h POI" against "in a daily POI", at 2 SE.

  SECONDARY. Within the daily-POI signals only, does the 8h label add anything?

  EXPECTATION. Daily at least as good as 8h, and probably better, because the
  POI thesis is about HIGHER timeframe context and 8:1 is barely higher. 8h at
  90 bars better than 8h at 30 bars, because a ten-day memory is untested.

    PYTHONPATH=. RIPTIDE_MIN_GRADE=B RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/poi_tf.py

RESULT, 11 Sep 2026 — THE POI TIMEFRAME DOES NOT MATTER ON 1h, AND NEITHER,
APPARENTLY, DOES THE POI.

6015 Min60 A/B signals, 59 symbols, 333 days, 2037 bets in the unfiltered pool.

    label                     signals  kept  /day   bets     R/bet   total R
    no POI, A/B by trend         6015  100%  36.7   2037  +0.125     +372.5
    8h/30 bars — DEPLOYED        3057   51%  18.7   1279  +0.088     +158.1
    8h/90 bars (30d life)        3714   62%  22.7   1473  +0.095     +194.0
    daily/30 bars (30d)          2154   36%  13.2    962  +0.092      +79.6
    8h AND daily                 1315   22%   8.0    655  +0.030       -2.5
    8h only, not daily           1742   29%  10.6    836  +0.129     +160.6
    daily only, not 8h            839   14%   5.1    448  +0.153      +82.0

THE PRE-REGISTERED QUESTION IS A DEAD HEAT AND NOT A NARROW ONE. 8h at a
matched 30-day life against daily is +0.095 vs +0.092, |z| 0.1. The deployed
10-day 8h against daily is -0.004, |z| 0.1. The two 8h lifetimes against each
other are +0.007, |z| 0.1. Three separate framings of "does the POI timeframe
matter" all land within a tenth of a standard error of no difference. My
expectation that daily would be better was wrong, and so was the smaller
prediction that a 30-day memory would beat a 10-day one.

THE UNPLANNED RESULT IS THE ONE THAT MATTERS, and it points against the filter
itself. Asked correctly — in-zone against OUT-of-zone, not against the pool:

    in the DEPLOYED 8h zone   +0.088   vs  not in one   +0.132   |z| 0.8
    in a daily zone           +0.092   vs  not in one   +0.125   |z| 0.6

Both point the WRONG way. Neither is significant, and that is the whole finding
rather than a hedge on it: on Min60 the POI filter halves the stream (36.7
alerts a day to 18.7) and cuts total R by 58% (+372.5 to +158.1) in exchange
for an R-per-bet difference that is negative and unmeasurable. The excluded
half bootstraps to [+0.080, +0.169], entirely above zero — on Min30 it was the
excluded arm being NEGATIVE that earned this filter its place.

STACKING THE TWO CONTEXTS IS THE WORST THING ON THE BOARD. "8h AND daily" is
+0.030 with a total of -2.5 R, a profit factor of exactly 1.00, a recovery
factor of -0.03 and the only bootstrap interval here that straddles zero
[-0.058, +0.097]. Requiring BOTH readings agree selects the worse half of
either one alone. Within the daily-POI signals, those also in an 8h zone score
+0.030 against +0.153 for those not — a -0.124 gap at |z| 1.5, the largest
effect in the study and still not significant.

WHAT TURNING THE FILTER OFF WOULD ACTUALLY DO, which is not what the pool row
says. Grades above hold poi=True so the A/B floor is a constant. Production
grades on the REAL poi, and there the switch is asymmetric: a CONFIRMED signal
outside a zone falls A -> B and still sends, an EARLY one falls B -> C and is
muted by MIN_GRADE=B. So POI_REQUIRED=0 does not release the 6015-signal pool.
It releases 536 signals — the confirmed ones with no zone — and nothing else:

    POI on   (deployed today)   3057   18.7/day   +0.088±0.037   +158.1 R
    POI off  (regraded at B)    3593   21.9/day   +0.092±0.035   +197.2 R
      the difference             536    3.3/day   +0.100±0.079    +39.1 R

Three more alerts a day, +39 R over the year, R per bet unchanged at |z| 0.1,
recovery factor 1.73 -> 2.05. A small, cheap, unproven improvement — the exact
profile that must not be shipped on a backtest and is worth watching forward.

HONEST POWER STATEMENT. Combined SEs here are about 0.05, so 2 SE is roughly
0.11 R. A POI benefit of +0.10 would not have been detected. What is ruled out
is a LARGE benefit on 1h, not a modest one. But the asymmetry is the decision:
the filter's cost is certain and measured — half the alerts, 58% of the total
R — while its benefit on this timeframe is unmeasurable and negative in point
estimate.

WHAT THIS DOES AND DOES NOT CLOSE. It does not touch Min30, where the POI's
held-out pre-registered win was found and where it stays on. It closes the POI
TIMEFRAME as a knob — three framings at |z| 0.1 — so there is nothing to be
gained by giving a 1h stream its own POI interval. And it says that if the 1h
stream is enabled, the case for gating it on a POI at all has not been made.

A DEFECT THIS TURNED UP, WORTH FIXING SEPARATELY. engine._POI is "daily POI"
and telegram.py prints " in a daily POI"; both have said 8h since 9 Sep. The
alert, /help, /stats and six config comments all misdescribe the live filter.
No behaviour is wrong — only every description of it, including the one the
user reads.
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import json                                             # noqa: E402
import os                                               # noqa: E402
import statistics                                       # noqa: E402
from collections import defaultdict                     # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import BAR_SECONDS, CFG, TRACK_TARGET_R  # noqa: E402
from riptide.engine import atr_series, daily_zones      # noqa: E402
from riptide.engine import grade_of, run_engine         # noqa: E402
from riptide.exchange import fetch_candles, list_symbols  # noqa: E402
from riptide.trend import di_at, direction_at           # noqa: E402
from research.deep import load_deep, load_universe      # noqa: E402
from research.harness import mean_se, simulate          # noqa: E402
from research.studies.power import mde                  # noqa: E402
from research.studies.report import drawdown            # noqa: E402
from research.studies.survivor import symbol_bootstrap  # noqa: E402

DAYS = 333
# Lead-in for the CONTEXT series only. A zone needs atr_len bars before it can
# form and lives POI_MAX_AGE_BARS after it, so the context series has to start
# well before the measurement window or the first weeks of it see no zones and
# the earliest signals are scored against an empty map.
CTX_DAYS = 420
INTERVAL = "Min60"
TFS = ("Min15", "Min30", "Min60", "Hour4")
SYMS = "/tmp/tf_syms.json"
COMMON = "/tmp/tf_common.json"

DAY, H8 = "Day1", "Hour8"

# THE DEPLOYED POI IS READ ON Hour8, NOT ON Day1, AND EVERY COMMENT IN THIS
# REPOSITORY THAT CALLS IT "the daily POI" IS STALE. trend.poi_at reads
# TREND_INTERVAL, which moved Day1 -> Hour8 on 9 Sep for the SuperTrend and
# took the point of interest with it silently; poi_at's own docstring, the
# daily_zones name, and four comment blocks in config.py all still say daily.
# Verified rather than assumed: poi_at agrees with an Hour8/30-bar lookup on
# 100.0% of 1038 signals across BTC, SOL and ONDO, and with a Day1/30-bar
# lookup on 62%.
#
# This study was pre-registered believing Day1 was the incumbent. The arms were
# fixed before any number was seen, so the comparison stands untouched — but
# the reading of it inverts: the "8h" column is the STATUS QUO and the "daily"
# column is the proposed change.
DEPLOYED = "8h/30 bars — DEPLOYED"
POOL = "no POI, A/B by trend"

ARMS = {
    POOL: lambda t: True,
    DEPLOYED: lambda t: t.h8,
    "8h/90 bars (30d life)": lambda t: t.h8long,
    "daily/30 bars (30d)": lambda t: t.day,
    "8h AND daily": lambda t: t.h8 and t.day,
    "8h only, not daily": lambda t: t.h8 and not t.day,
    "daily only, not 8h": lambda t: t.day and not t.h8,
    "NO 8h zone": lambda t: not t.h8,
    "NO daily zone": lambda t: not t.day,
}

# WHAT THE CONFIG SWITCH WOULD ACTUALLY DO, which is not what the pool row
# says. Grades above are computed with poi=True so that the A/B floor is a
# constant and only the POI label varies. In production the grade table reads
# the REAL poi: with POI_REQUIRED off, a confirmed signal outside a zone drops
# A -> B and still sends, but an EARLY one drops B -> C and is muted by
# MIN_GRADE=B. So turning the filter off does not release the whole pool — it
# releases exactly the confirmed signals that have no zone, and nothing else.
SHIP = {
    "POI on   (deployed today)": lambda t: t.h8,
    "POI off  (regraded at B)": lambda t: t.kind == "confirmed" or t.h8,
    "  the difference: confirmed, no 8h zone":
        lambda t: t.kind == "confirmed" and not t.h8,
}


class T:
    __slots__ = ("sym", "t", "r", "gross", "tf", "filled", "fill_t",
                 "exit_t", "risk_pct", "kind", "day", "h8", "h8long",
                 "trend_ok", "is_long")


def zone_hit(zones, when, price, is_long, step, max_age_bars):
    """engine.in_zone with the lifetime exposed.

    Identical logic — including the `t + step` rule that stops a signal
    matching a zone built from the bar it is sitting inside — except that
    POI_MAX_AGE_BARS is a parameter here instead of a constant, because the
    lifetime is one of the two things this study has to hold still.
    """
    for t, bull, lo, hi in zones:
        if (t + step <= when and bull == is_long and lo <= price <= hi
                and when - t <= max_age_bars * step):
            return True
    return False


async def context(sess, symbols, interval):
    """{symbol: zones} on `interval`, built from deep history.

    NOT trend.poi_at, and the reason is a silent truncation. poi_at reads
    fetch_candles, which returns LOOKBACK (600) bars — 600 days on Day1, which
    covers this window twice over, but only 200 days on Hour8. Used naively the
    8h arm would have had NO zones for the oldest 133 days of the window and
    would have scored those signals as "not in a zone" rather than "unknown".
    """
    out = {}
    for s in symbols:
        cs = await load_deep(sess, s, interval, CTX_DAYS)
        out[s] = daily_zones(cs, atr_series(cs, CFG.atr_len)) if cs else []
    return out


async def collect(sess, candles, zday, z8h, interval=INTERVAL,
                  require_ab=True):
    """One pool of A/B signals with every POI applied as a LABEL, not a filter.

    `interval` is a parameter rather than the module constant so that
    matrix.py can run the identical pipeline on Min15 and Min30 — one code
    path, three timeframes, which is the same argument the frozen-control test
    makes about research never forking the engine.

    `require_ab=False` keeps the trend-DISAGREEING signals too, recording the
    answer on each row instead of dropping it. poi_recheck.py needs them: the
    original POI finding was an interaction with the trend, so a study that
    only ever looks inside the trend-agrees half cannot see the other half of
    the claim it is arguing with.
    """
    bar = BAR_SECONDS[interval]
    rows = []
    for sym, cs in candles.items():
        early = []
        try:
            setups = run_engine(sym, cs, CFG, early_out=early)
        except Exception:
            continue
        idx = {c.t: i for i, c in enumerate(cs)}
        zd, z8 = zday.get(sym, []), z8h.get(sym, [])
        for kind, batch in (("confirmed", setups), ("early", early)):
            for x in batch:
                i = idx.get(x.detected_time)
                if i is None or x.entry <= 0 or abs(x.entry - x.stop) <= 0:
                    continue
                w = x.detected_time
                d = await direction_at(sess, sym, w, fetch_candles)
                di = await di_at(sess, sym, w, fetch_candles)
                # poi=True for EVERY signal on purpose: the A/B floor must be
                # the same constant in all arms or the POI comparison would be
                # partly a grade comparison. See the caveat in the docstring.
                ok = grade_of(kind == "early", True, d or 0, x.is_long,
                              di or 0)[0] in "AB"
                if require_ab and not ok:
                    continue
                o = simulate(cs, i, x.entry, x.stop, x.is_long,
                             target_r=TRACK_TARGET_R)
                # The same trade with the fee switched off. Fee in R is
                # fee_pct / risk_pct, and risk_pct doubles from Min15 to
                # Min60, so any gradient across timeframes could be nothing
                # but cost. This is how to tell.
                g = simulate(cs, i, x.entry, x.stop, x.is_long,
                             target_r=TRACK_TARGET_R, fee_pct=0.0)
                z = T()
                z.sym, z.t, z.kind, z.tf = sym, w, kind, interval
                z.trend_ok, z.is_long = ok, bool(x.is_long)
                z.r, z.filled, z.gross = o.r, o.filled, g.r
                z.risk_pct = 100 * abs(x.entry - x.stop) / x.entry
                # Wall-clock fill and exit, so report.compound can replay the
                # account in time with several positions open at once.
                z.fill_t = (w + bar * (o.fill_bar - i)
                            if o.filled and o.fill_bar is not None else None)
                z.exit_t = (w + bar * (o.exit_bar - i)
                            if o.filled and o.exit_bar else None)
                z.day = zone_hit(zd, w, x.stop, x.is_long,
                                 BAR_SECONDS[DAY], 30)
                z.h8 = zone_hit(z8, w, x.stop, x.is_long, BAR_SECONDS[H8], 30)
                z.h8long = zone_hit(z8, w, x.stop, x.is_long,
                                    BAR_SECONDS[H8], 90)
                rows.append(z)
    return rows


def bets_of(rows):
    g = defaultdict(list)
    for t in rows:
        g[t.t].append(t.r)
    return [statistics.fmean(g[k]) for k in sorted(g)]


def arm(rows, name):
    keep = ARMS.get(name) or SHIP[name]
    return [t for t in rows if keep(t)]


def line(name, all_rows, rows, syms):
    f = [t for t in rows if t.filled and t.exit_t is not None]
    if len(f) < 30:
        print(f"  {name:<39}{len(rows):>8}   too few to read")
        return
    b = bets_of(f)
    m, se = mean_se(b)
    rs = [t.r for t in f]
    wins = [r for r in rs if r > 0]
    gl = -sum(r for r in rs if r < 0)
    dd, _ = drawdown([t.r for t in sorted(f, key=lambda x: x.exit_t)])
    print(f"  {name:<39}{len(rows):>8}{len(rows) / len(all_rows):>7.0%}"
          f"{len(rows) / DAYS / syms * 120:>7.1f}{len(b):>7}"
          f"{len(wins) / len(f):>6.0%}{m:>+8.3f}±{se:.3f}{sum(rs):>+8.1f}"
          f"{sum(wins) / gl if gl else 0:>7.2f}"
          f"{sum(rs) / dd if dd else 0:>7.2f}")


def gap(label, a, b):
    """Unpaired difference between two SUBSETS of the same pool."""
    if len(a) < 30 or len(b) < 30:
        print(f"  {label:<44} too few")
        return
    ma, sa = mean_se(bets_of(a))
    mb, sb = mean_se(bets_of(b))
    se = (sa ** 2 + sb ** 2) ** 0.5
    print(f"  {label:<44}{ma:>+7.3f}  vs {mb:>+7.3f}   "
          f"diff {ma - mb:>+6.3f}  |z| {abs(ma - mb) / se if se else 0:>4.1f}"
          + ("   SEPARATES" if se and abs(ma - mb) / se >= 2 else ""))


async def universe(sess):
    """The same 59 symbols timeframes.py used, cached after the first run."""
    if os.path.exists(COMMON):
        return json.load(open(COMMON))
    try:
        want = json.load(open(SYMS))
    except OSError:
        want = await list_symbols(sess)
    sets = []
    for tf in TFS:
        expect = DAYS * 86400 // BAR_SECONDS[tf]
        sets.append(set(await load_universe(sess, want, tf, DAYS,
                                            min_bars=int(0.8 * expect))))
    common = sorted(set.intersection(*sets))
    json.dump(common, open(COMMON, "w"))
    return common


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = await universe(sess)
        candles = await load_universe(
            sess, syms, INTERVAL, DAYS,
            min_bars=int(0.8 * DAYS * 86400 // BAR_SECONDS[INTERVAL]))
        zday = await context(sess, candles, DAY)
        z8h = await context(sess, candles, H8)
        rows = await collect(sess, candles, zday, z8h)

    n = len(syms)
    print(f"WHICH TIMEFRAME SHOULD THE POI BE READ ON, FOR A 1h SETUP\n"
          f"{len(rows)} Min60 A/B signals, {len(candles)} symbols, {DAYS} "
          f"days, NO POI filter applied.\neach row below is a LABEL on that "
          f"one pool, not a separate backtest.\nzones/day are per 120 symbols "
          f"— the deployed universe, not the {n} measured here.")

    pool = bets_of([t for t in rows if t.filled and t.exit_t is not None])
    sd = statistics.pstdev(pool) if len(pool) > 1 else 1.4
    print(f"\n  POWER. {len(pool)} bets, sd {sd:.2f}. A filter keeping a "
          f"third is scored\n  against the other two thirds: MDE "
          f"{mde(sd, len(pool) // 3):.3f} R. Anything smaller than that is "
          f"unreadable\n  here however tidy it looks.")

    print(f"\n  {'label':<39}{'signals':>8}{'kept':>7}{'/day':>7}{'bets':>7}"
          f"{'win':>6}{'R/bet':>16}{'total':>8}{'PF':>7}{'recov':>7}")
    for a in ARMS:
        line(a, rows, arm(rows, a), n)

    print("\n-- CONFIRMED ONLY " + "-" * 59)
    conf = [t for t in rows if t.kind == "confirmed"]
    print(f"  {'label':<39}{'signals':>8}{'kept':>7}{'/day':>7}{'bets':>7}"
          f"{'win':>6}{'R/bet':>16}{'total':>8}{'PF':>7}{'recov':>7}")
    for a in ARMS:
        line(a, conf, arm(conf, a), n)

    print("\n-- WHAT THE CONFIG SWITCH WOULD ACTUALLY SEND " + "-" * 32)
    print("  grades above hold poi=True so the A/B floor is constant. "
          "here the grade\n  table reads the REAL poi, which is what "
          "production would do.")
    print(f"  {'':<39}{'signals':>8}{'kept':>7}{'/day':>7}{'bets':>7}"
          f"{'win':>6}{'R/bet':>16}{'total':>8}{'PF':>7}{'recov':>7}")
    for a in SHIP:
        line(a, rows, arm(rows, a), n)

    print("\n-- HOW MUCH DO THE TWO LABELS EVEN DISAGREE " + "-" * 33)
    d = sum(1 for t in rows if t.day)
    h = sum(1 for t in rows if t.h8)
    both = sum(1 for t in rows if t.day and t.h8)
    print(f"  daily {d} ({d / len(rows):.0%})   8h {h} ({h / len(rows):.0%})"
          f"   both {both}   either {d + h - both}")
    print(f"  of the daily-POI signals, {both / d if d else 0:.0%} are also "
          f"in an 8h zone.\n  the two labels are far from independent, which "
          f"caps how much new\n  information the second one can carry.")

    print("\n-- THE COMPARISONS THAT WERE PRE-REGISTERED " + "-" * 34)
    fil = [t for t in rows if t.filled and t.exit_t is not None]
    gap("PRIMARY  8h at 30d life vs daily",
        arm(fil, "8h/90 bars (30d life)"), arm(fil, "daily/30 bars (30d)"))
    gap("         8h at 10d life (DEPLOYED) vs daily",
        arm(fil, DEPLOYED), arm(fil, "daily/30 bars (30d)"))
    gap("         8h at 30d life vs 8h at 10d life",
        arm(fil, "8h/90 bars (30d life)"), arm(fil, DEPLOYED))
    # AGAINST THE COMPLEMENT, NOT AGAINST THE POOL. An arm and the pool that
    # contains it are not two samples — the subset is inside the thing it is
    # being compared to, so an independent-SE z on that pair is meaningless and
    # biased toward zero. A filter's question is always in-zone against
    # OUT-of-zone.
    gap("         in a daily zone vs NOT in one",
        arm(fil, "daily/30 bars (30d)"), arm(fil, "NO daily zone"))
    gap("SECONDARY within daily POI: 8h too vs 8h not",
        arm(fil, "8h AND daily"), arm(fil, "daily only, not 8h"))
    # POST HOC, and flagged as such. The pre-registration named the daily arm
    # as the incumbent because that is what the comments said. This is the same
    # question aimed at the filter that is actually deployed.
    gap("post hoc  in the DEPLOYED 8h zone vs NOT in one",
        arm(fil, DEPLOYED), arm(fil, "NO 8h zone"))
    gap("post hoc  what POI off would add vs what it keeps",
        arm(fil, "  the difference: confirmed, no 8h zone"),
        arm(fil, "POI on   (deployed today)"))

    print("\n-- SYMBOL BOOTSTRAP, 2000 draws " + "-" * 45)
    print("  a level is only worth reading if it survives resampling the "
          "universe.")
    for a in ARMS:
        g = [t for t in arm(fil, a)]
        if len(g) < 60:
            continue
        bo = symbol_bootstrap(g, 2000)
        if not bo:
            continue
        p5 = bo[int(0.05 * (len(bo) - 1))]
        p95 = bo[int(0.95 * (len(bo) - 1))]
        print(f"  {a:<26}[{p5:>+7.3f}, {p95:>+7.3f}]"
              + ("   all above zero" if p5 > 0 else ""))


if __name__ == "__main__":
    asyncio.run(main())
