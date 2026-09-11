"""Does the PATH a trade takes to 1R predict whether letting it run pays?

THE QUESTION `exits.py` LEFT OPEN. That study tested thirteen exit policies
paired on the same trades and 2R beat all of them; nothing cleared 2 SE and
eleven of thirteen were negative. It also recorded a ladder that looks like it
contradicts the conclusion:

    reached 2R (207 trades)  ->  2.5R 84%   3R 64%

Sixty-four percent of trades that reach 2R go on to 3R, and yet a flat 3R
target is worth +0.0099 at |z| 0.25. Both are true, and the reason is the 36%:
holding past 2R with the ORIGINAL stop risks the whole two R to win one more.
The conditional probability is real; the bet attached to it is not.

That leaves two questions worth asking, and they are different.

  1. IS THERE A BETTER BET AT 2R? Holding with the stop moved TO +2R changes
     the arithmetic completely: 0.64 x 3 + 0.36 x 2 = 2.64 against a flat 2.
     `exits.py` never tested it — it tested break-even at 1R, which is a
     different and much worse trade. simulate expresses it directly as
     be_arm_r=2.0, be_lock_r=2.0, target_r=3.0.

  2. DOES THE PATH SELECT THE 64%? A trade that reached 1R in two bars without
     giving anything back is not obviously the same animal as one that took
     twenty bars and dipped half an R on the way. If the path separates them,
     a conditional target is worth more than a flat one.

NO LOOKAHEAD, AND THE REASON IS WORTH STATING BECAUSE IT IS WHAT MAKES THIS
TESTABLE AT ALL. The path features are read at the moment 1R is first touched.
The 2R-versus-3R decision only changes an outcome AFTER 2R is reached, and 1R
is always touched before 2R. So the feature is known strictly before the
policies can diverge. A trade that reaches 1R and then reverses is stopped
identically under every policy here, because the stop never moves for it.

THAT ALSO KEEPS THE SHARED SCORER. Nothing here re-implements the outcome loop
— `research/harness.py` runs every policy, and the study only computes a
FEATURE from the candles and then selects which of two scored outcomes applies.
That distinction is the whole reason this project has one scorer.

THE POLICIES

    CONTROL             plain 2R
    flat 3R             the reference exits.py already measured
    2R -> lock 2R, run 3R      the runner that was never tested
    2R -> lock 1.5R, run 3R    the same, conceding more back
    fast to 1R -> 3R           path-conditional, else 2R
    clean to 1R -> 3R          small give-back on the way, else 2R
    slow to 1R -> take 1R      cut the laggards, else 2R

PRE-REGISTERED, BEFORE THE FIRST NUMBER

  PRIMARY. R per signal against plain 2R, paired, at 2 SE. Win rate decides
  nothing, for the reason `stop_deep.py` demonstrated: at +1 ATR the win rate
  rose three points and R did not move at all.

  The thresholds for "fast" and "clean" are the MEDIANS of their own
  distributions, fixed that way in advance so there is no sweep and nothing to
  tune. A median split is the weakest possible version of the hypothesis and
  that is deliberate — if the path matters, a median split should show it.

  EXPECTATION. The locked runner is favoured by arithmetic and I expect it to
  be the only positive row; whether it clears 2 SE is the open question. I
  expect the path-conditional rules to do nothing, because `exits.py` and
  `tier1.py` between them have now produced twelve buckets whose "shape" was
  noise, and because a 64% base rate leaves little room for a splitter to
  improve on.

    PYTHONPATH=. RIPTIDE_MIN_GRADE=B RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/path_exit.py

RESULT, 11 Sep 2026 — THE PATH PREDICTS POWERFULLY AND IS WORTH NOTHING.

9699 A/B signals, 110 symbols. 5656 reached 1R.

  OBSERVATIONALLY THE SPLIT IS HUGE:

    fast to 1R (<= 7 bars)   2969   reach 2R 57%   reach 3R 41%
    slow to 1R (>  7 bars)   2687   reach 2R 29%   reach 3R 17%
    clean give-back          2829   reach 2R 60%   reach 3R 41%
    choppy give-back         2828   reach 2R 28%   reach 3R 19%

  A trade that reaches 1R quickly and cleanly is TWICE as likely to reach 2R.
  That is not a marginal separation and it is not noise at these counts.

  AND IT DOES NOT CONVERT:

    flat 3R                      +0.016  ±0.008   +2.1 SE
    fast to 1R -> 3R             +0.013  ±0.007   +1.9 SE
    fast AND clean -> 3R         +0.011  ±0.006   +1.8 SE
    2R -> lock 2R, run 3R        +0.010  ±0.005   +1.9 SE
    clean to 1R -> 3R            +0.009  ±0.007   +1.5 SE
    2R -> lock 1.5R, run 3R      +0.009  ±0.006   +1.6 SE
    fast to 1R -> lock 2R run 3R +0.006  ±0.005   +1.2 SE
    slow to 1R -> take 1R        -0.009  ±0.005   -1.9 SE
    choppy to 1R -> take 1R      -0.010  ±0.005   -2.2 SE

  EVERY path-conditional rule is WORSE than applying 3R to everything. That is
  the finding, and it is not the one the conditional probabilities suggest.

  THE REASON IS THE SLOW BUCKET STILL PAYS. Slow trades reach 2R 29% of the
  time and 3R 17% of the time; those are worse odds, not bad ones. A rule that
  gives them a 2R target to protect them takes their 3R upside away as well,
  and the upside it forfeits is larger than the downside it avoids. Filtering
  on a predictor only helps when the excluded group is NEGATIVE, and this one
  is merely less positive. A prediction is not a decision.

  Cutting the laggards is the same mistake with the sign flipped: taking 1R off
  the slow and choppy trades is the worst row on the board, -2.2 SE for the
  choppy split. Those trades are not failing, they are slower.

WHAT I GOT WRONG, AGAIN IN THE USEFUL DIRECTION. I expected the locked runner
to be the only positive row. It is positive (+0.010, +1.9 SE) and it is not the
best — flat 3R beats it. Locking at +2R protects the 36% that turn back, and
protecting them costs more than it saves, because the stop at +2R gets clipped
by noise on trades that would have carried on.

THE ROW THAT NEEDS A WARNING RATHER THAN A CELEBRATION. Flat 3R is +2.1 SE and
it is the ONLY row past 2. Three reasons to discount it and one not to:

  - it is one of nine policies, and nine tests produce about 0.4 exceedances of
    2 SE by chance, so a single 2.1 is close to what noise delivers;
  - it is not a path finding at all, it is the reference row;
  - `exits.py` measured the same policy at +0.0099 ± 0.0392 on 594 confirmed
    Min30 trades — consistent with this, but that is agreement between a
    measurement and a much better-resolved version of itself, not replication;
  - against all that: it was pre-registered as the reference, not fished for,
    and the direction matches the ladder's mechanism.

  NOT SHIPPED. It joins the +0.25 ATR stop buffer from `stop_deep.py` as the
  second economically interesting, statistically marginal result of the day.
  Both belong in forward data, not in riptide.conf.

A LIMITATION IN THE FEATURE, STATED PLAINLY. "Give-back" still correlates
heavily with plain adverse excursion: a trade need only be barely ahead before
dipping, so the measure is dominated by how far below entry it went. Clean-vs-
choppy is therefore close to small-MAE-vs-large-MAE, which is why it splits
almost identically to fast-vs-slow. The two path features are largely the same
information, and neither converts.
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import statistics                                       # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import CFG                          # noqa: E402
from riptide.engine import grade_of, run_engine         # noqa: E402
from riptide.exchange import fetch_candles, list_symbols  # noqa: E402
from riptide.trend import di_at, direction_at, poi_at   # noqa: E402
from research.deep import load_universe                 # noqa: E402
from research.harness import mean_se, simulate          # noqa: E402

DAYS = 333
INTERVAL = "Min30"
CONTROL = "CONTROL  plain 2R"


def path_to(cs, fill, entry, stop, is_long, level=1.0, horizon=60):
    """(bars to first touch `level` R, deepest give-back in R before it).

    Give-back is what the trade handed back ON ITS WAY UP, not how far
    underwater it started — and getting that distinction wrong is easy. The
    first version of this accumulated `peak - adv` from bar one, where peak was
    still 0 and adv was the opening drawdown, so it was measuring the initial
    adverse excursion. The tell was the median coming out at exactly 1.00 R:
    that is the stop, and it said only that a typical trade dips most of the
    way to its stop before it works, which is true and is a different fact.

    So give-back only accumulates once the trade has actually been ahead. Both
    values are read at the bar `level` is first touched and are therefore
    knowable before any policy below can diverge.
    """
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    peak = dip = 0.0
    for k in range(fill, min(fill + horizon, len(cs))):
        c = cs[k]
        fav = (c.h - entry) / risk if is_long else (entry - c.l) / risk
        adv = (c.l - entry) / risk if is_long else (entry - c.h) / risk
        if peak > 0:                        # only once it HAS been ahead
            dip = max(dip, peak - adv)
        peak = max(peak, fav)
        if fav >= level:
            return k - fill, dip
    return None


async def collect(sess, candles):
    rows = []
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

                a = dict(cs=cs, signal_bar=i, entry=x.entry, stop=x.stop,
                         is_long=x.is_long)
                base = simulate(**a, target_r=2.0)
                row = {
                    "r2": base.r,
                    "r1": simulate(**a, target_r=1.0).r,
                    "r3": simulate(**a, target_r=3.0).r,
                    "lock2": simulate(**a, target_r=3.0, be_arm_r=2.0,
                                      be_lock_r=2.0).r,
                    "lock15": simulate(**a, target_r=3.0, be_arm_r=2.0,
                                       be_lock_r=1.5).r,
                    # MFE from an UNCONSTRAINED run. Reading it off the 2R
                    # simulation truncates it at the target, so "reached 3R"
                    # came out at 7% when it is really a third of that bucket —
                    # a trade that exits at 2R cannot record an excursion past
                    # it. Only the observational table used this; the policy
                    # rows never did.
                    "filled": base.filled, "path": None,
                    "mfe": simulate(**a, target_r=99.0).mfe,
                }
                if base.filled and base.fill_bar is not None:
                    row["path"] = path_to(cs, base.fill_bar, x.entry, x.stop,
                                          x.is_long)
                rows.append(row)
    return rows


def report(name, series, ctrl):
    m, se = mean_se(series)
    d = [a - b for a, b in zip(series, ctrl)]
    md = statistics.fmean(d)
    sd = statistics.pstdev(d) / len(d) ** 0.5
    z = md / sd if sd else 0.0
    tag = "   BEATS IT" if z >= 2 else ("   worse" if z <= -2 else "")
    print(f"  {name:<28}{m:>+8.3f}{md:>+9.3f}  ±{sd:.3f}{z:>+7.1f} SE{tag}")


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = await list_symbols(sess)
        candles = await load_universe(sess, syms, INTERVAL, DAYS)
        rows = await collect(sess, candles)

    reached = [r for r in rows if r["path"] is not None]
    bars = sorted(r["path"][0] for r in reached)
    dips = sorted(r["path"][1] for r in reached)
    b_med = bars[len(bars) // 2]
    d_med = dips[len(dips) // 2]

    print(f"PATH-DEPENDENT EXITS\n{len(rows)} A/B signals, {len(candles)} "
          f"symbols, {DAYS} days.\n{len(reached)} reached 1R "
          f"({len(reached) / len(rows):.0%}); median {b_med} bars to get there, "
          f"median give-back {d_med:.2f} R.")

    print("\n-- the conditional probabilities, observational " + "-" * 29)
    for lo, hi, lab in ((0, b_med, f"fast to 1R (<= {b_med} bars)"),
                        (b_med + 1, 10 ** 9, f"slow to 1R (> {b_med} bars)")):
        g = [r for r in reached if lo <= r["path"][0] <= hi]
        if len(g) < 50:
            continue
        print(f"  {lab:<28}{len(g):>6}   reach 2R "
              f"{sum(1 for r in g if r['mfe'] >= 2) / len(g):>4.0%}   "
              f"reach 3R {sum(1 for r in g if r['mfe'] >= 3) / len(g):>4.0%}")
    for lo, hi, lab in ((0.0, d_med, f"clean (give-back <= {d_med:.2f}R)"),
                        (d_med, 10 ** 9, f"choppy (give-back > {d_med:.2f}R)")):
        g = [r for r in reached if lo <= r["path"][1] <= hi]
        if len(g) < 50:
            continue
        print(f"  {lab:<28}{len(g):>6}   reach 2R "
              f"{sum(1 for r in g if r['mfe'] >= 2) / len(g):>4.0%}   "
              f"reach 3R {sum(1 for r in g if r['mfe'] >= 3) / len(g):>4.0%}")

    # ---- the policies, every one scored on every signal
    ctrl = [r["r2"] for r in rows]

    def cond(pick, otherwise="r2"):
        """Path-conditional: `pick` applies where the predicate holds."""
        key, pred = pick
        return [r[key] if (r["path"] is not None and pred(r["path"]))
                else r[otherwise] for r in rows]

    print(f"\n-- policies, paired on all {len(rows)} signals " + "-" * 27)
    print(f"  {'policy':<28}{'R/sig':>8}{'vs 2R':>9}{'':>8}{'':>7}")
    report(CONTROL, ctrl, ctrl)
    report("flat 3R", [r["r3"] for r in rows], ctrl)
    report("2R -> lock 2R, run 3R", [r["lock2"] for r in rows], ctrl)
    report("2R -> lock 1.5R, run 3R", [r["lock15"] for r in rows], ctrl)
    report(f"fast to 1R -> 3R",
           cond(("r3", lambda p: p[0] <= b_med)), ctrl)
    report(f"clean to 1R -> 3R",
           cond(("r3", lambda p: p[1] <= d_med)), ctrl)
    report(f"fast AND clean -> 3R",
           cond(("r3", lambda p: p[0] <= b_med and p[1] <= d_med)), ctrl)
    report(f"slow to 1R -> take 1R",
           cond(("r1", lambda p: p[0] > b_med)), ctrl)
    report(f"choppy to 1R -> take 1R",
           cond(("r1", lambda p: p[1] > d_med)), ctrl)
    report(f"fast to 1R -> lock 2R run 3R",
           cond(("lock2", lambda p: p[0] <= b_med)), ctrl)


if __name__ == "__main__":
    asyncio.run(main())
