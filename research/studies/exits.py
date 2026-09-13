"""The exit half of the plan: items 14 to 18, plus the MFE ladder.

WHY THESE ARE WORTH RUNNING WHEN THE FEATURE HYPOTHESES WERE NOT. `power.py`
put the confirmed stream's minimum detectable effect at 0.351 R per bet, and
`tier1.py` then watched eight feature hypotheses die under it. Exits are a
different statistical animal and the difference is large enough to change what
is worth doing.

A feature test SPLITS the sample: bucket A against bucket B, two independent
arms, each a fraction of the whole. An exit test does not split anything. Every
policy is applied to EVERY trade, so the comparison is PAIRED — the same
signals, the same fills, the same bars, and only the exit rule differs. Most of
the variance is common to both arms and cancels in the difference. Where an
unpaired tercile needed 0.35 R to be readable, a paired policy swap here
resolves a few hundredths, because the standard error is computed on the
per-bet DIFFERENCE rather than on two separate means.

So the exit questions are answerable on this sample and the feature questions
are not. That is not a matter of which is more interesting; it is arithmetic,
and it is the main reason the plan's Tier 4 outranks its Tier 1 in practice.

WHAT IS TESTED

    the ladder     purely observational. Among trades that got to +0.5R, how
                   many went on to +1R, +1.5R, +2R, +3R? Run with the target
                   removed, because a 2R target truncates its own evidence:
                   you cannot observe how often 2R becomes 3R while exiting
                   at 2R.

    targets        1.5R / 2R / 2.5R / 3R. 2R is the incumbent and the control.
    break-even     arm at 1R, lock at 0 and at +0.3R.
    partial        half off at 1R, the rest runs to 3R.
    structure      trail the stop under the last confirmed swing.
    staleness      leave at the close if the trade has not reached +0.5R
                   after 5, 10, 15 or 20 bars.

EVERY ROW IS SCORED AGAINST THE SAME CONTROL AND THE PAIRED SE IS PRINTED. A
policy has to beat plain 2R on expectancy, not on win rate — the plan is right
about that and so is the 25-policy experiment that preceded it.

    PYTHONPATH=. RIPTIDE_MIN_GRADE=B RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/exits.py

RESULT, 11 Sep 2026 — 2R SURVIVES, AND THE PLAN'S FAVOURITE EXIT IS THE WORST

  594 filled confirmed trades, 492 bets. Paired standard errors land between
  0.011 and 0.046, so this sample CAN read exit changes — an unpaired tercile
  on the same rows needed 0.35 R and got nothing.

    policy                        vs 2R      paired SE   |z|
    target 2.5R                 +0.0305       0.0269    1.14
    target 3R                   +0.0099       0.0392    0.25
    2R, out at 5 bars < 0.5R    -0.0021       0.0263    0.08
    2R, out at 10 bars < 0.5R   -0.0033       0.0178    0.19
    2R, out at 20 bars < 0.5R   -0.0074       0.0111    0.66
    2R, out at 15 bars < 0.5R   -0.0084       0.0125    0.67
    2R, out at 10 bars < 1R     -0.0270       0.0316    0.85
    2R + BE at 1R -> 0          -0.0326       0.0219    1.49
    target 1.5R                 -0.0383       0.0275    1.40
    2R + BE at 1R -> +0.3       -0.0393       0.0246    1.60
    half at 1R, rest to 3R      -0.0502       0.0344    1.46
    3R + swing trail            -0.0479       0.0456    1.05
    2R + swing trail            -0.0743       0.0388    1.92

  NOTHING CLEARS 2 SE, and eleven of thirteen are negative. The structure-
  failure exit the plan calls "the most interesting exit I see" is the worst
  row on the board and the closest of any to being significantly WORSE. Its
  logic is sound and the market disagrees: a stop resting under the last
  confirmed swing gets hit on the retracements a 2R trade has to survive.

  Break-even is negative again, at both lock levels, which is the third time
  this project has measured it and the third time it has lost. It remains off.

  THE ONE ROW WORTH A SECOND LOOK IS NOT THE ONE WITH THE BEST NUMBER. The
  staleness exits cost almost nothing — a 20-bar cut at 0.5R gives up 0.0074 R
  a bet — while ending trades far earlier. On an account where CONCURRENCY is
  the binding constraint, and `report.py` showed it is (a 300 USDT account
  capped at five open positions skipped 18 confirmed signals and 1441 across
  both streams), an exit that is free in R and returns margin sooner can be net
  positive in cash even though it is neutral here. That is a portfolio
  question, not an exit question, and it is measured in `portfolio_v2.py`.

  THE LADDER, which is observational and has no significance to claim:

    reached 0.5R (455):  1R 71%   1.5R 55%   2R 45%   2.5R 38%   3R 29%
    reached 1R   (322):  1.5R 78%   2R 64%   2.5R 54%   3R 41%
    reached 1.5R (250):  2R 83%   2.5R 70%   3R 53%
    reached 2R   (207):  2.5R 84%   3R 64%
    23% of fills never reach 0.5R at all.

  Once a trade reaches 2R, 64% of them go on to 3R — which looks like an
  argument for a runner until you notice that the 3R target itself is worth
  +0.0099 at |z| 0.25. The conditional probability is real; the money is not,
  because the 36% that turn back give up two full R to save nothing.
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import statistics                                       # noqa: E402
from collections import defaultdict                     # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import CFG, TRACK_TARGET_R          # noqa: E402
from riptide.engine import grade_of, run_engine         # noqa: E402
from riptide.exchange import fetch_candles, list_symbols  # noqa: E402
from riptide.trend import di_at, direction_at, poi_at   # noqa: E402
from research.deep import load_universe                 # noqa: E402
from research.harness import mean_se, simulate          # noqa: E402

DAYS = 333
INTERVAL = "Min30"
SWING = 3          # bars each side for a confirmed swing, for the structure trail


def swing_trail(cs, is_long, left=SWING, right=SWING):
    """Per-bar last CONFIRMED swing low (long) or high (short).

    Confirmed means the pivot needed `right` further bars to be knowable, so
    the level only appears at index j+right. Publishing it at j would let the
    stop use a line the market had not yet drawn, which is the repainting
    failure in its most ordinary disguise.
    """
    out = [None] * len(cs)
    cur = None
    for j in range(left, len(cs) - right):
        w = cs[j - left:j + right + 1]
        if is_long and cs[j].l == min(c.l for c in w):
            cur = cs[j].l
        elif not is_long and cs[j].h == max(c.h for c in w):
            cur = cs[j].h
        if j + right < len(out):
            out[j + right] = cur
    return out


POLICIES = [
    ("CONTROL  2R", dict(target_r=2.0)),
    ("target 1.5R", dict(target_r=1.5)),
    ("target 2.5R", dict(target_r=2.5)),
    ("target 3R", dict(target_r=3.0)),
    ("2R + BE at 1R -> 0", dict(target_r=2.0, be_arm_r=1.0, be_lock_r=0.0)),
    ("2R + BE at 1R -> +0.3", dict(target_r=2.0, be_arm_r=1.0, be_lock_r=0.3)),
    ("half at 1R, rest to 3R", dict(target_r=3.0, part_at_r=1.0, part_to_r=3.0)),
    ("2R + swing trail", dict(target_r=2.0, _trail=True)),
    ("3R + swing trail", dict(target_r=3.0, _trail=True)),
    ("2R, out at 5 bars < 0.5R", dict(target_r=2.0, stale_bars=5, stale_r=0.5)),
    ("2R, out at 10 bars < 0.5R", dict(target_r=2.0, stale_bars=10, stale_r=0.5)),
    ("2R, out at 15 bars < 0.5R", dict(target_r=2.0, stale_bars=15, stale_r=0.5)),
    ("2R, out at 20 bars < 0.5R", dict(target_r=2.0, stale_bars=20, stale_r=0.5)),
    ("2R, out at 10 bars < 1R", dict(target_r=2.0, stale_bars=10, stale_r=1.0)),
]


async def collect(sess, candles):
    """Every confirmed A/B setup, scored under every policy on the same rows."""
    rows = []
    ladder = []
    for sym, cs in candles.items():
        try:
            setups = run_engine(sym, cs, CFG)
        except Exception:
            continue
        idx = {c.t: i for i, c in enumerate(cs)}
        trails = {True: None, False: None}
        for x in setups:
            i = idx.get(x.detected_time)
            if i is None or x.entry <= 0 or abs(x.entry - x.stop) <= 0:
                continue
            w = x.detected_time
            poi = await poi_at(sess, sym, w, x.stop, x.is_long, fetch_candles)
            if not (True if poi is None else bool(poi)):
                continue
            d = await direction_at(sess, sym, w, fetch_candles)
            di = await di_at(sess, sym, w, fetch_candles)
            if grade_of(False, True, d or 0, x.is_long, di or 0)[0] not in "AB":
                continue
            if trails[x.is_long] is None:
                trails[x.is_long] = swing_trail(cs, x.is_long)

            base = simulate(cs, i, x.entry, x.stop, x.is_long, target_r=2.0)
            if not base.filled:
                continue
            # The ladder needs the UNTRUNCATED path, so the target is moved out
            # of reach rather than removed — simulate has no "no target" mode
            # and inventing one here would be a second scorer.
            free = simulate(cs, i, x.entry, x.stop, x.is_long, target_r=99.0)
            ladder.append(free.mfe)

            got = {}
            for name, kw in POLICIES:
                kw = dict(kw)
                tr = trails[x.is_long] if kw.pop("_trail", False) else None
                got[name] = simulate(cs, i, x.entry, x.stop, x.is_long,
                                     trail=tr, **kw).r
            rows.append((w, got))
    return rows, ladder


def per_bet(rows, name):
    g = defaultdict(list)
    for t, got in rows:
        g[t].append(got[name])
    return [statistics.fmean(g[k]) for k in sorted(g)]


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = await list_symbols(sess)
        candles = await load_universe(sess, syms, INTERVAL, DAYS)
        rows, ladder = await collect(sess, candles)

    print(f"EXIT POLICIES, PAIRED\n{len(rows)} filled confirmed A/B trades, "
          f"{len(set(t for t, _ in rows))} bets, {DAYS} days.\nevery policy is "
          f"scored on THE SAME trades, so the standard error below is on the\n"
          f"per-bet DIFFERENCE against the control, not on two separate means.")

    print("\n-- THE MFE LADDER (observational, target moved to 99R) " + "-" * 23)
    print("  of the trades that reached each level, how many went on:")
    lv = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    for a in lv[:-1]:
        base = [m for m in ladder if m >= a]
        if len(base) < 30:
            continue
        nxt = "   ".join(
            f"{b:g}R {sum(1 for m in base if m >= b) / len(base):>4.0%}"
            for b in lv if b > a)
        print(f"    reached {a:g}R ({len(base):>4} trades):  {nxt}")
    print(f"    never reached 0.5R: "
          f"{sum(1 for m in ladder if m < 0.5) / len(ladder):.0%} of fills")

    ctrl = per_bet(rows, "CONTROL  2R")
    mc, sc = mean_se(ctrl)
    print(f"\n-- POLICIES " + "-" * 65)
    print(f"  {'policy':<28}{'R/bet':>9}{'win':>7}{'total R':>10}"
          f"{'vs control':>12}{'paired SE':>11}{'|z|':>6}")
    for name, _ in POLICIES:
        b = per_bet(rows, name)
        m, _se = mean_se(b)
        diff = [x - y for x, y in zip(b, ctrl)]
        md = statistics.fmean(diff)
        sd = statistics.pstdev(diff) / len(diff) ** 0.5
        wins = sum(1 for x in b if x > 0) / len(b)
        tot = sum(sum(got[name] for got in [g]) for _, g in rows)
        flag = "" if name.startswith("CONTROL") else \
            f"{md:>+12.4f}{sd:>11.4f}{abs(md) / sd if sd else 0:>6.2f}"
        print(f"  {name:<28}{m:>+9.3f}{wins:>7.0%}{tot:>10.1f}{flag}")
    print(f"\n  control absolute: {mc:+.3f} +/- {sc:.3f} R/bet "
          f"(unpaired, for scale)")
    print("  a paired SE near 0.02 resolves effects an unpaired tercile at "
          "0.35 could not.")


if __name__ == "__main__":
    asyncio.run(main())
