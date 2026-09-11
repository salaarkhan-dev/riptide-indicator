"""The same strategy on 15m, 30m, 1h and 4h, measured independently.

THE SAME SIXTY-ODD SYMBOLS ON ALL FOUR, DELIBERATELY. Comparing timeframes on
different symbol sets would confound the answer with composition — the 1h
result would partly be "which coins happened to be in it". The universe here is
whichever symbols have a Min15 cache, and every timeframe is measured on
exactly those, over the same 333 days.

THREE THINGS ARE NOT EQUAL ACROSS THE ROWS AND PRETENDING OTHERWISE WOULD MAKE
THE TABLE MEANINGLESS.

  BAR COUNT. 333 days is about 32000 Min15 bars, 16000 Min30, 8000 Min60 and
  2000 Hour4. Signal counts scale with that, so the 4h row rests on a fraction
  of the evidence and its error bar says so. A 4h number that looks better is
  not better until its SE is read.

  THE WINDOWS ARE IN BARS, NOT HOURS. TRACK_FILL_BARS is 10 and
  TRACK_HORIZON_BARS is 60 on every timeframe, so a 15m trade gets 15 hours to
  resolve and a 4h trade gets 10 days. That is not a bug — the strategy is
  bar-relative and the engine's pivots, ATR and cooldowns are too — but it does
  mean the rows are not the same trade held for the same time. Median hold is
  printed in BOTH bars and hours so the difference is visible rather than
  buried.

  THE FEE IS NOT SCALE-FREE. Fee in R is fee_pct / risk_pct, and risk_pct grows
  with the timeframe because a 4h raid is bigger than a 15m one. So the higher
  timeframes pay materially less fee per trade, and any edge they show has to
  be read with that in mind — part of it is simply cost.

WHAT IS HELD FIXED: the engine, the config, the POI gate, the A/B grade floor,
the near-edge entry, the raid-extreme stop and the 2R target. Only the candle
series changes.

    PYTHONPATH=. RIPTIDE_MIN_GRADE=B RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/timeframes.py

RESULT, 11 Sep 2026 — NO TIMEFRAME BEATS ANOTHER; THE ONLY REAL GAP IS THE FEE.

59 symbols, 333 days, the same set on every row. All signals, confirmed+early:

    Min15  4279 bets  +0.018±0.020  total  -7.3 R  maxDD 214.8  recov -0.03
    Min30  2422 bets  +0.030±0.027  total +147.2 R  maxDD 133.4  recov  1.10
    Min60  1279 bets  +0.088±0.037  total +158.1 R  maxDD  91.2  recov  1.73
    Hour4   398 bets  +0.126±0.067  total   -7.5 R  maxDD  87.9  recov -0.09

Confirmed only: +0.017±0.052, +0.066±0.062, +0.106±0.077, +0.017±0.093.

NOTHING SEPARATES. Min60 minus Min30 on confirmed is +0.040 against a combined
SE of 0.099 — four tenths of one SE. No adjacent pair on either panel reaches
1 SE.

AND THE MONOTONE CLIMB IS ONLY IN THE ALL-SIGNAL COLUMN. Confirmed-only runs
+0.017, +0.066, +0.106, +0.017 — an arch, not a ramp, with the two ends exactly
equal. The tidy left-to-right story that the first table tells does not survive
dropping early signals, which is the stream the bot actually asks to be traded.
Report the arch, not the ramp.

AND THE FOUR ROWS ARE NOT FOUR SAMPLES. Same coins, same 333 days, same
regimes, only the sampling rate differs. A 15m signal and the 1h signal that
straddles it are frequently the same raid read twice. So "the gradient shows up
on all four" is one observation, not four, and the risk-band panel below is the
same one observation four times over.

HALF THE GRADIENT IS THE FEE AND HALF IS NOT, WHICH IS THE ONE FINDING HERE.
Switching the fee off (identical trades, fee_pct=0.0):

    tf       stop    fee in R    net      GROSS    fee share
    Min15   0.97%      0.036     0.018     0.054       67%
    Min30   1.39%      0.025     0.030     0.055       45%
    Min60   1.97%      0.017     0.088     0.105       16%
    Hour4   4.12%      0.007     0.126     0.133        6%

GROSS Min15 is 0.054 and gross Min30 is 0.055. Identical. The entire Min15
deficit is cost: the setup finds the same edge per bet at 15m, and the taker
fee, which is fee_pct/risk_pct and therefore inflated by a 0.97% stop, eats
two thirds of it. That is a fixable-looking problem and it is not fixable by
any research here — it is a fee schedule.

The Min60/Hour4 step is NOT cost. Gross rises 0.055 → 0.105 → 0.133 after the
fee is removed, so whatever the higher timeframes have, they have it before
paying. It still does not clear 2 SE. Both statements are true at once and
neither rescues the other.

R PER BET AND TOTAL R DISAGREE IN SIGN ON TWO ROWS, and the disagreement is the
clustering story, not an error. Min15 is +0.018 per bet and -7.3 R in total;
Hour4 is +0.126 per bet and -7.5 R. A bet is the mean of every symbol firing on
one bar, so a 40-symbol cluster counts once in the bet average and forty times
in the trade sum. The sign flip says the big simultaneous clusters are the
losers. Anyone reading the per-bet column as an account curve is reading the
wrong number: Min15 and Hour4 both LOST money over 333 days as actually traded.
This is the strongest single argument in the repository for the event-pick rule
already shipped.

HOUR4'S HEADLINE IS AN EARLY-SIGNAL ARTEFACT. +0.126 all-signal against +0.017
confirmed-only on the same 4h candles. The 4h row also rests on 398 bets — an
eleventh of the Min15 row — and its ±0.067 is wider than every effect this
project has ever measured. There is no 4h result here, only a 4h error bar.

THE RISK BAND HOLDS ON ALL FOUR, WITH A CAVEAT THAT MATTERS MOST WHERE THE
NUMBER LOOKS BEST:

    Min15   in +0.115±0.086   out -0.046±0.065   diff +0.160  |z| 1.5
    Min30   in +0.212±0.088   out -0.108±0.082   diff +0.320  |z| 2.7
    Min60   in +0.244±0.117   out -0.016±0.095   diff +0.260  |z| 1.7
    Hour4   in +0.355±0.257   out -0.038±0.096   diff +0.392  |z| 1.4

LO=1.2 and HI=2.6 were fitted on Min30 and reused verbatim, so on 4h — median
stop 4.12% — the band keeps 38 of 310 fills, 12%. On Min30 it keeps 51%. The
4h "band" is not the same filter; it is a thin-stop tail selected by a
threshold that has nothing to do with 4h structure, on 38 trades. Treat the
Hour4 row as absent. The band is established on Min30, consistent on Min15 and
Min60, and untested at 4h.

WHAT THIS DOES AND DOES NOT CHANGE. It does not justify moving the bot's
timeframe: the gaps are inside their error bars and the deployed Min30 is the
only row where the shipped filter is measured rather than assumed. It does
establish that the 15m stream is gross-equivalent and fee-crippled, which is
the correct reason to treat 15m alerts as watch-only, and it puts an eleven-
fold sample penalty on any future 4h proposal before that proposal is made.
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import json                                             # noqa: E402
import statistics                                       # noqa: E402
from collections import defaultdict                     # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import BAR_SECONDS, CFG, TRACK_TARGET_R  # noqa: E402
from riptide.engine import grade_of, run_engine         # noqa: E402
from riptide.exchange import fetch_candles, list_symbols  # noqa: E402
from riptide.trend import di_at, direction_at, poi_at   # noqa: E402
from research.deep import load_universe                 # noqa: E402
from research.harness import mean_se, simulate          # noqa: E402
from research.studies.report import drawdown            # noqa: E402
from research.studies.survivor import LO, HI, symbol_bootstrap  # noqa: E402

DAYS = 333
TFS = ("Min15", "Min30", "Min60", "Hour4")
SYMS = "/tmp/tf_syms.json"


class T:
    __slots__ = ("sym", "t", "r", "gross", "kind", "risk_pct", "filled",
                 "hold", "exit_t")


async def collect(sess, candles, tf):
    bar = BAR_SECONDS[tf]
    out = []
    for sym, cs in candles.items():
        early = []
        try:
            setups = run_engine(sym, cs, CFG, early_out=early)
        except Exception:
            continue
        idx = {c.t: i for i, c in enumerate(cs)}
        for kind, batch in (("confirmed", setups), ("early", early)):
            for x in batch:
                i = idx.get(x.detected_time)
                if i is None or x.entry <= 0 or abs(x.entry - x.stop) <= 0:
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
                o = simulate(cs, i, x.entry, x.stop, x.is_long,
                             target_r=TRACK_TARGET_R)
                # The same trade with the fee switched off. Fee in R is
                # fee_pct / risk_pct and risk_pct QUADRUPLES from 15m to 4h, so
                # a gradient across timeframes could be nothing but cost. This
                # is how to tell.
                g = simulate(cs, i, x.entry, x.stop, x.is_long,
                             target_r=TRACK_TARGET_R, fee_pct=0.0)
                z = T()
                z.sym, z.t, z.kind = sym, w, kind
                z.r, z.filled, z.gross = o.r, o.filled, g.r
                z.risk_pct = 100 * abs(x.entry - x.stop) / x.entry
                z.hold = (o.exit_bar - o.fill_bar
                          if o.filled and o.exit_bar and o.fill_bar else None)
                z.exit_t = (w + bar * (o.exit_bar - i)
                            if o.filled and o.exit_bar else None)
                out.append(z)
    return out


def bets_of(rows, gross=False):
    g = defaultdict(list)
    for t in rows:
        g[t.t].append(t.gross if gross else t.r)
    return [statistics.fmean(g[k]) for k in sorted(g)]


def line(tf, rows, bar_h):
    f = [t for t in rows if t.filled and t.exit_t is not None]
    if len(f) < 30:
        print(f"  {tf:<8}{len(rows):>8}{len(f):>8}   too few to read")
        return
    rs = [t.r for t in f]
    b = bets_of(f)
    m, se = mean_se(b)
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r < 0]
    gp, gl = sum(wins), -sum(losses)
    dd, _ = drawdown([t.r for t in sorted(f, key=lambda x: x.exit_t)])
    hold = statistics.median(t.hold for t in f if t.hold is not None)
    print(f"  {tf:<8}{len(rows):>8}{len(f):>8}{len(b):>7}"
          f"{len(f) / len(rows):>7.0%}{len(wins) / len(f):>6.0%}"
          f"{m:>+8.3f}±{se:.3f}{sum(rs):>+8.1f}"
          f"{gp / gl if gl else 0:>7.2f}{dd:>7.1f}"
          f"{sum(rs) / dd if dd else 0:>7.2f}"
          f"{statistics.median(t.risk_pct for t in rows):>7.2f}%"
          f"{hold:>6.0f}{hold * bar_h:>8.0f}h")


async def candidates(sess):
    """The symbols to try. SYMS is a convenience, not a requirement.

    The run that produced the RESULT above read a pinned list so that a
    re-run months later is scored on the same coins rather than on whatever
    the exchange happens to list that day. Without it the study still works —
    it asks the exchange — but the universe is then a moving part and the
    numbers are not comparable to the ones in the docstring.
    """
    try:
        return json.load(open(SYMS))
    except OSError:
        print(f"  ({SYMS} absent — falling back to the live symbol list; "
              f"results will NOT be comparable to the docstring)")
        return await list_symbols(sess)


async def main():
    # min_bars IS AN ABSOLUTE FLOOR AND IT SILENTLY DELETED THE 4h ROW.
    # load_universe defaults to 2000 bars, written when everything here ran on
    # Min30 where that is six weeks. 333 days of Hour4 is 1998 bars — three
    # short — so the first run of this study returned an empty 4h universe and
    # reported "could not load" for a timeframe whose files were on disk and
    # perfectly good. The floor has to scale with the bar, so it is expressed
    # as a fraction of the window each interval should contain.
    loaded = {}
    async with aiohttp.ClientSession() as sess:
        want = await candidates(sess)
        print(f"THE SAME STRATEGY ON FOUR TIMEFRAMES\n{len(want)} symbols, "
              f"{DAYS} days, identical set on every row.\nengine, config, POI "
              f"gate, A/B floor, near-edge entry, raid stop and 2R all "
              f"unchanged —\nonly the candle series differs.")
        print(f"\n  {'tf':<8}{'signals':>8}{'filled':>8}{'bets':>7}{'fill':>7}"
              f"{'win':>6}{'R/bet':>16}{'total':>8}{'PF':>7}{'maxDD':>7}"
              f"{'recov':>7}{'stop':>8}{'hold':>6}{'':>9}")
        for tf in TFS:
            expect = DAYS * 86400 // BAR_SECONDS[tf]
            try:
                loaded[tf] = await load_universe(sess, want, tf, DAYS,
                                                 min_bars=int(0.8 * expect))
            except Exception as e:
                print(f"  {tf:<8}could not load: {e}")

        # IDENTICAL COMPOSITION OR THE TABLE MEANS NOTHING. A symbol that
        # cleared the floor on 15m but not on 4h would otherwise appear in one
        # row and not another, and the comparison would carry a quiet symbol
        # selection on top of the timeframe.
        common = set.intersection(*(set(v) for v in loaded.values())) \
            if loaded else set()
        print(f"  ({len(common)} symbols clear the history floor on ALL four; "
              f"every row below uses exactly those)\n")

        keep = {}
        for tf in TFS:
            if tf not in loaded:
                continue
            cs = {k: v for k, v in loaded[tf].items() if k in common}
            rows = await collect(sess, cs, tf)
            keep[tf] = rows
            line(tf, rows, BAR_SECONDS[tf] / 3600)

    print("\n  hold is shown in BARS then HOURS. the windows are fixed in "
          "bars, so a\n  4h trade is given sixteen times the wall clock a 15m "
          "trade gets.")

    print("\n-- CONFIRMED ONLY " + "-" * 59)
    print(f"  {'tf':<8}{'signals':>8}{'filled':>8}{'bets':>7}{'fill':>7}"
          f"{'win':>6}{'R/bet':>16}{'total':>8}{'PF':>7}{'maxDD':>7}"
          f"{'recov':>7}{'stop':>8}{'hold':>6}{'':>9}")
    for tf, rows in keep.items():
        line(tf, [t for t in rows if t.kind == "confirmed"],
             BAR_SECONDS[tf] / 3600)

    print("\n-- IS THE GRADIENT JUST THE FEE? " + "-" * 44)
    print("  fee in R is fee_pct / risk_pct, and risk_pct quadruples across "
          "these rows.")
    print(f"  {'tf':<8}{'stop':>8}{'fee in R':>10}{'net R/bet':>12}"
          f"{'GROSS R/bet':>14}{'fee share':>12}")
    for tf, rows in keep.items():
        f = [t for t in rows if t.filled and t.exit_t is not None]
        if len(f) < 30:
            continue
        net = statistics.fmean(bets_of(f))
        gro = statistics.fmean(bets_of(f, gross=True))
        stop = statistics.median(t.risk_pct for t in rows)
        print(f"  {tf:<8}{stop:>7.2f}%{gro - net:>10.3f}{net:>12.3f}"
              f"{gro:>14.3f}{(gro - net) / abs(gro) if gro else 0:>11.0%}")

    print("\n-- THE RISK BAND, PER TIMEFRAME " + "-" * 45)
    print("  does the one surviving filter hold at every scale?")
    for tf, rows in keep.items():
        f = [t for t in rows if t.filled and t.kind == "confirmed"]
        band = [t for t in f if LO <= t.risk_pct <= HI]
        out = [t for t in f if not (LO <= t.risk_pct <= HI)]
        if len(band) < 30 or len(out) < 30:
            print(f"  {tf:<8}{len(band):>5} in / {len(out):>5} out — too few")
            continue
        mb, sb = mean_se(bets_of(band))
        mo, so = mean_se(bets_of(out))
        bo = symbol_bootstrap(band, 2000)
        p5 = bo[int(0.05 * (len(bo) - 1))] if bo else float("nan")
        se = (sb ** 2 + so ** 2) ** 0.5
        print(f"  {tf:<8}in {mb:>+7.3f}±{sb:.3f} ({len(band):>4} tr)   "
              f"out {mo:>+7.3f}±{so:.3f} ({len(out):>4} tr)   "
              f"diff {mb - mo:>+6.3f} "
              f"|z| {abs(mb - mo) / se if se else 0:>4.1f}"
              f"   boot5th {p5:>+6.3f}")


if __name__ == "__main__":
    asyncio.run(main())
