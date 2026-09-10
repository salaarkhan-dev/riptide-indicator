"""Can the PIVOT POOL be tuned into better entries? A sweep, read honestly.

THE POOL IS UPSTREAM OF EVERYTHING. A pivot pool decides which price level
counts as liquidity worth raiding, and every later stage — the sweep, the
shift, the gap the entry sits in, the stop at the raid extreme — inherits it.
So a better pool would not be a filter that deletes bad trades; it would
change WHICH TRADES EXIST. That is a genuinely different lever from everything
tried so far in this project, and worth one careful pass.

WHAT IS SWEPT, one parameter at a time around the shipped defaults:

    pivot_left / pivot_right   what confirms a swing at all
    tol_atr                    how near two pivots must be to pool together
    min_pivots                 how many touches make a level
    max_pool_span_bars         how far apart in time those touches may sit
    max_cluster_span_atr       how wide the finished pool may be
    max_overshoot_atr          how far past the pool a raid may run

THE PRIOR IS STRONGLY AGAINST THIS AND SAYING SO FIRST IS THE POINT. Every
sweep this project has run over a grid of settings has died: 31 features, 12
entry locations, 25 exit policies, the trendline stop, the SR break, RSI
divergence. One survived — the sweep volume gate — out of dozens. A grid of
twenty-two configs will hand back a best-on-discovery cell no matter what,
because that is what maximising over twenty-two noisy numbers does.

PRE-REGISTERED, BEFORE THE FIRST NUMBER

  PRIMARY   The config chosen on the DISCOVERY half by R per bet must beat
            the shipped default on the HELD-OUT half by 2 SE on R per bet.
            Chosen blind, read once. That estimates the DECISION PROCEDURE —
            "run this sweep and adopt the winner" — rather than the winning
            cell, which is the number a person actually gets.

  SECONDARY Win rate and separate bets per day for every config, because the
            request was for better entries and a setting that improves R by
            halving the traffic has not improved the entries.

  UNIT      One bet per candle close, as priority.py established: same-close
            alerts are one market event, and counting them separately inflates
            both the sample and the significance.

  GATES     The deployed ones — POI required, grade B+, target 2R — because a
            pool that only helps signals the bot never sends is not an
            improvement to anything.

  EXPECTATION: nothing clears. The defaults mirror a reference indicator that
  was itself tuned, and the honest outcome of this study is most likely
  "leave it alone". Recorded so it cannot be revised afterwards.

    PYTHONPATH=. RIPTIDE_MIN_GRADE=B python3 research/studies/pivot_tune.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import dataclasses                                      # noqa: E402
import statistics                                       # noqa: E402
import time                                             # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import CFG, MIN_GRADE, TRACK_TARGET_R  # noqa: E402
from riptide.engine import grade_of, run_engine         # noqa: E402
from riptide.exchange import fetch_candles, list_symbols  # noqa: E402
from riptide.trend import di_at, direction_at, poi_at   # noqa: E402
from research.harness import mean_se, simulate          # noqa: E402

TF = "Min30"
KIND = "confirmed"
BANDS = "ABCD"
CUT = BANDS.index(MIN_GRADE)

# One parameter at a time. The default sits in each list so the comparison is
# always against the shipped value measured on the SAME rows, never against a
# number carried over from another run.
SWEEP = (
    ("pivot_left", (1, 2, 3)),
    ("pivot_right", (1, 2, 3, 4)),
    ("tol_atr", (0.15, 0.25, 0.35, 0.50)),
    ("min_pivots", (2, 3, 4)),
    ("max_pool_span_bars", (30, 60, 120, 200)),
    ("max_cluster_span_atr", (0.50, 0.80, 1.20)),
    ("max_overshoot_atr", (0.15, 0.25, 0.40, 0.60)),
)


def variants():
    """(label, cfg) for every point in the sweep, the default first and once."""
    out = [("DEFAULT (shipped)", CFG)]
    seen = {tuple(dataclasses.astuple(CFG))}
    for name, values in SWEEP:
        for v in values:
            cfg = dataclasses.replace(CFG, **{name: v})
            key = tuple(dataclasses.astuple(cfg))
            if key in seen:
                continue
            seen.add(key)
            out.append((f"{name} = {v}", cfg))
    return out


async def score(sess, candles, cfg, kind=KIND):
    """Run the engine at one config and return the SENT confirmed signals.

    The trend series are cached inside riptide.trend per (symbol, interval),
    so the daily and Hour8 reads cost one request each for the whole sweep
    rather than one per config. Only the engine re-runs.
    """
    rows = []
    for sym, cs in candles.items():
        early = []
        try:
            setups = run_engine(sym, cs, cfg, early_out=early)
        except Exception:
            continue
        sigs, key = ((setups, "detected_time") if kind == "confirmed"
                     else (early, "fvg_time"))
        idx = {c.t: i for i, c in enumerate(cs)}
        mid = cs[len(cs) // 2].t
        for x in sigs:
            i = idx.get(getattr(x, key))
            if i is None or x.entry <= 0 or abs(x.entry - x.stop) <= 0:
                continue
            o = simulate(cs, i, x.entry, x.stop, x.is_long,
                         target_r=TRACK_TARGET_R)
            if not o.filled or o.exit_bar is None:
                continue
            when = getattr(x, key)
            poi = await poi_at(sess, sym, when, x.stop, x.is_long,
                               fetch_candles)
            poi = True if poi is None else bool(poi)
            if not poi:
                continue                       # POI_REQUIRED, as deployed
            d = await direction_at(sess, sym, when, fetch_candles)
            di = await di_at(sess, sym, when, fetch_candles)
            if BANDS.index(grade_of(kind == "early", poi, d or 0, x.is_long,
                                    di or 0)[0]) > CUT:
                continue                       # MIN_GRADE, as deployed
            rows.append((when, o.r, when < mid))
    return rows


def bets(rows):
    """One bet per close, averaged — the unit priority.py settled on."""
    bybar = {}
    for t, r, held in rows:
        bybar.setdefault(t, []).append((r, held))
    return [(t, statistics.fmean(r for r, _ in v), v[0][1])
            for t, v in bybar.items()]


def stat(rows):
    b = bets(rows)
    if len(b) < 15:
        return None
    m, se = mean_se([r for _, r, _ in b])
    return dict(n=len(b), win=sum(1 for _, r, _ in b if r > 0) / len(b),
                m=m, se=se, tot=sum(r for _, r, _ in b))


def show(label, full, disc, held, days, star=""):
    def cell(s):
        return (f"{s['n']:>5}{s['win']:>6.0%}{s['m']:>+8.3f}{s['se']:>6.3f}"
                if s else f"{'--':>25}")
    print(f"  {label:<26}{full['n'] / days:>6.1f}{cell(full)}  |{cell(disc)}"
          f"  |{cell(held)}{star}")


async def main():
    t0 = time.time()
    async with aiohttp.ClientSession() as sess:
        syms = await list_symbols(sess)
        candles = {}
        for s in syms:
            try:
                cs = await fetch_candles(sess, s, TF)
            except Exception:
                continue
            if len(cs) >= 300:
                candles[s] = cs
        days = statistics.median((cs[-1].t - cs[0].t) / 86400
                                 for cs in candles.values())

        vs = variants()
        print(f"PIVOT POOL SWEEP — {len(vs)} configs · {len(candles)} symbols "
              f"· {days:.0f} days\n{TF} {KIND} · POI required · grade "
              f"{MIN_GRADE}+ · target {TRACK_TARGET_R:g}R · one bet per close\n"
              f"CHOSEN on discovery, READ on held out. The held-out column is "
              f"the only one that counts.\n")
        print(f"  {'config':<26}{'/day':>6}{'  FULL WINDOW':<25}"
              f"  |{'  DISCOVERY (choose here)':<25}  |  HELD OUT (read here)")
        print(f"  {'':<26}{'':>6}{'n':>5}{'win':>6}{'R/bet':>8}{'SE':>6}"
              f"  |{'n':>5}{'win':>6}{'R/bet':>8}{'SE':>6}"
              f"  |{'n':>5}{'win':>6}{'R/bet':>8}{'SE':>6}")

        results = {}
        for label, cfg in vs:
            rows = await score(sess, candles, cfg)
            full = stat(rows)
            if not full:
                print(f"  {label:<26}   too few")
                continue
            disc = stat([r for r in rows if not r[2]])
            held = stat([r for r in rows if r[2]])
            results[label] = (full, disc, held, cfg)
            show(label, full, disc, held, days,
                 "  <-- shipped" if label.startswith("DEFAULT") else "")

    base = results.get("DEFAULT (shipped)")
    if not base:
        return
    pool = {k: v for k, v in results.items() if not k.startswith("DEFAULT")
            and v[1]}
    if not pool:
        return

    # Chosen on DISCOVERY only, blind to the held-out column above.
    win = max(pool, key=lambda k: pool[k][1]["m"])
    winw = max(pool, key=lambda k: pool[k][1]["win"])
    print(f"\n  chosen on DISCOVERY by R per bet:   {win}")
    print(f"  chosen on DISCOVERY by win rate:    {winw}")

    print(f"\n  THE PRE-REGISTERED READ — held out, against the shipped "
          f"default")
    for k in dict.fromkeys((win, winw)):
        c, b = results[k][2], base[2]
        if not (c and b):
            print(f"    {k:<26} too few held out")
            continue
        d = c["m"] - b["m"]
        se = (c["se"] ** 2 + b["se"] ** 2) ** 0.5
        print(f"    {k:<26}{c['m']:>+8.3f} vs {b['m']:>+7.3f}"
              f"   diff {d:>+7.3f}  {d / se if se else 0:>+5.1f} SE"
              f"   win {c['win']:>4.0%} vs {b['win']:>4.0%}")
    print(f"\n  PASSES only at +2 SE or better. Anything less is the sweep "
          f"finding\n  the largest of twenty-two noisy numbers, which it will "
          f"do every time.")
    # ---- the better-powered sample -------------------------------------
    #
    # THE POOL IS UPSTREAM OF BOTH SIGNAL TYPES, so a pool setting that
    # genuinely helps must show up in the EARLY stream too — and early carries
    # roughly six times the traffic, which is six times the power to detect an
    # effect that is really there. A setting that looks good only on the 74
    # confirmed bets and does nothing across 400+ early ones is the small
    # sample talking. This is corroboration, not a second bite: the
    # pre-registered verdict above stands whatever this says.
    print(f"\n{'=' * 100}\nTHE SAME SWEEP ON EARLY SIGNALS — six times the "
          f"traffic, six times the power\n{'=' * 100}")
    print(f"  {'config':<26}{'/day':>6}{'  FULL WINDOW':<25}"
          f"  |{'  DISCOVERY':<25}  |  HELD OUT")
    async with aiohttp.ClientSession() as sess:
        for label, cfg in vs:
            rows = await score(sess, candles, cfg, kind="early")
            full = stat(rows)
            if not full:
                print(f"  {label:<26}   too few")
                continue
            show(label, full, stat([r for r in rows if not r[2]]),
                 stat([r for r in rows if r[2]]), days,
                 "  <-- shipped" if label.startswith("DEFAULT") else "")

    # ---- the independent check ------------------------------------------
    #
    # min_pivots = 3 is the only setting in the sweep that improves every
    # panel it can be read on, and the ONLY one that turns the early stream's
    # held-out half from negative to positive. That is either a real
    # structural fact — a level touched three times has actually been defended,
    # where two touches is close to any two highs within tolerance — or it is
    # the largest of eighteen noisy numbers wearing a plausible story.
    #
    # THE WAY TO TELL IS A SAMPLE IT WAS NOT CHOSEN ON. Min15 is a different
    # signal set on the same symbols: if three touches is a real property of a
    # level, it must help there too, and nothing about the Min30 sweep can
    # have leaked into it.
    print(f"\n{'=' * 100}\nINDEPENDENT CHECK — min_pivots on Min15, a "
          f"timeframe the setting was NOT chosen on\n{'=' * 100}")
    print(f"  {'config':<26}{'/day':>6}{'  FULL WINDOW':<25}"
          f"  |{'  DISCOVERY':<25}  |  HELD OUT")
    async with aiohttp.ClientSession() as sess:
        c15 = {}
        for sym in candles:
            try:
                cs = await fetch_candles(sess, sym, "Min15")
            except Exception:
                continue
            if len(cs) >= 300:
                c15[sym] = cs
        d15 = statistics.median((cs[-1].t - cs[0].t) / 86400
                                for cs in c15.values())
        for kind in ("early", "confirmed"):
            print(f"\n  Min15 {kind}  ({d15:.0f} days)")
            for mp in (2, 3, 4):
                cfg = dataclasses.replace(CFG, min_pivots=mp)
                rows = await score(sess, c15, cfg, kind=kind)
                full = stat(rows)
                if not full:
                    print(f"  {'min_pivots = ' + str(mp):<26}   too few")
                    continue
                show(f"min_pivots = {mp}", full,
                     stat([r for r in rows if not r[2]]),
                     stat([r for r in rows if r[2]]), d15,
                     "  <-- shipped" if mp == CFG.min_pivots else "")

    print(f"\n  ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    asyncio.run(main())
