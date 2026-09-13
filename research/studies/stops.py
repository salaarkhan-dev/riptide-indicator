"""The stop: where to put it, and what to do with it once you are in.

Two questions, one collection pass, because they are two halves of the same
cost and they need the identical rows to be comparable.

    A  A MINIMUM RISK FLOOR.  Fee in R is fee / risk_pct, so a stop worth
       0.4% of price pays three times what one worth 1.2% pays. Six studies
       have now arrived at that from six directions and nothing in the
       codebase acts on it: `Cfg.max_risk_atr` caps risk in ATR UNITS, which
       cannot see the percent axis the fee lives on.

    B  STOP MANAGEMENT.  Break-even and partial exits. The user's ask is
       "improve the win rate and the stop losses", and this is the only honest
       version of it — the win rate is a dial the target sets, but the number
       of FULL stop-outs is a real thing a rule can change.

THE TENSION IN (A), NAMED BEFORE THE RUN BECAUSE IT DECIDES THE ANSWER

Two forces point opposite ways and the measurement has to separate them.

  the fee says a floor HELPS       cost in R falls as the stop widens
  the harness says it HURTS        research/harness.py's standard control is
                                   `risk_terciles`, whose docstring reads
                                   "wide stops score worse" — because on a
                                   REAL signal the stop sits at the raid
                                   extreme, so a wide stop means a big messy
                                   raid, which is a worse setup

Both can be true at once, and they are not in conflict: widening a stop
EXOGENOUSLY (an ATR multiple you choose) is not the same as observing an
ENDOGENOUSLY wide stop (a raid that happened to be huge). So this study reports
GROSS and NET R in every bucket:

    gross            the setup-quality effect alone
    net              quality plus the fee
    net minus gross  the fee, printed

If gross falls with risk while net rises, the fee dominates and a floor is
justified. If both fall, the floor is measuring setup quality and would be
throwing away good trades to save a fee it never pays back.

PRE-REGISTERED, BEFORE THE FIRST NUMBER

  A-PRIMARY   NET R rises monotonically across the risk_pct quintiles, in BOTH
              halves, on Riptide's own confirmed setups. A floor is recommended
              only if that holds AND gross does not rise with it — a gradient
              present in gross too is setup quality, not fee, and a floor is
              the wrong instrument for it.

  B-PRIMARY   Does any management rule beat the plain fixed stop on NET R, in
              BOTH halves? Reported alongside the count of FULL LOSSES (r <=
              -0.5R), because cutting those is the thing actually being asked
              for and it is worth knowing its price even when the price is
              positive.

              Prior: `MEASUREMENTS.md`, "Break-even, measured properly at
              last" — on Riptide it lost at every arm level, worst at the
              earliest arm, -2.5 SE at a 1R arm, because it converts trades
              that would have reached target into +0.1R scratches. This
              re-tests it on LEZ, which has never been measured, and re-checks
              Riptide on a window that study did not have.

  Neither is a sweep. Five buckets and six rules, fixed in advance.

    PYTHONPATH=. python3 research/studies/stops.py
"""
from __future__ import annotations

import research.env  # noqa: F401  (must precede riptide.config)

import asyncio
import statistics
from dataclasses import dataclass

import aiohttp

from riptide.config import CFG, BAR_SECONDS
from riptide.engine import atr_series, run_engine
from riptide.exchange import list_symbols
from research.harness import mean_se, simulate, simulate_market
from research.studies.lez import lez_signals
from research.studies.mtf_grid import fetch_paged

TFS = (("Min30", 2), ("Min15", 4))
SYMBOLS = 30
HORIZON_HOURS, FILL_HOURS = 48, 5
FEE = dict(fee_maker=0.02, fee_taker=0.06)
NO_FEE = dict(fee_maker=0.0, fee_taker=0.0)
STOP_ATR, ATR_LEN = 1.5, 14
TARGET_R = 2.0            # what the user is actually running on the chart

# A "full loss" is a stop taken with the stop still where it started. Anything
# above this is a scratch or a managed exit, which is the distinction the whole
# of study B is about.
FULL_LOSS_R = -0.5

# The management rules. Fixed in advance, and deliberately few.
RULES = (
    ("plain (fixed stop)",      dict()),
    ("BE at 1R, lock 0",        dict(be_arm_r=1.0, be_lock_r=0.0)),
    ("BE at 1R, lock +0.1R",    dict(be_arm_r=1.0, be_lock_r=0.1)),
    ("BE at 1.5R, lock +0.1R",  dict(be_arm_r=1.5, be_lock_r=0.1)),
    ("half at 1R, rest to tgt", dict(part_at_r=1.0, part_to_r=TARGET_R,
                                     be_lock_r=0.0)),
    ("half at 1R, lock +0.1R",  dict(part_at_r=1.0, part_to_r=TARGET_R,
                                     be_lock_r=0.1)),
)


@dataclass
class Row:
    half: str
    src: str              # "riptide" | "lez"
    risk: float           # as a percent of the entry price
    rs: dict              # rule label -> net R
    gross: float          # the plain rule with fees zeroed


async def collect(sess, syms, tf, pages):
    horizon = max(1, HORIZON_HOURS * 3600 // BAR_SECONDS[tf])
    fill_bars = max(1, FILL_HOURS * 3600 // BAR_SECONDS[tf])
    rows: list[Row] = []
    days = []

    for sym in syms:
        try:
            cs = await fetch_paged(sess, sym, tf, pages)
        except Exception:
            continue
        if len(cs) < 800:
            continue
        days.append((cs[-1].t - cs[0].t) / 86400)
        atr = atr_series(cs, ATR_LEN)
        cut = len(cs) // 2
        idx = {c.t: i for i, c in enumerate(cs)}

        # ---- Riptide's own confirmed setups, with its REAL entry and stop:
        # a limit at the gap, the stop just beyond the raid extreme. This is
        # the live strategy, not a synthetic shape, which is the whole point
        # of study A — the floor has to be judged on what actually ships.
        try:
            setups = run_engine(sym, cs, CFG)
        except Exception:
            setups = []
        for s in setups:
            i = idx.get(s.detected_time)
            if i is None or i + 1 + horizon > len(cs):
                continue
            risk = abs(s.entry - s.stop)
            if risk <= 0 or s.entry <= 0:
                continue
            rs = {}
            for lab, kw in RULES:
                o = simulate(cs, i, s.entry, s.stop, s.is_long,
                             target_r=TARGET_R, fill_bars=fill_bars,
                             horizon_bars=horizon, fee_pct=0.0, **FEE, **kw)
                # Unfilled is 0.0 by the project's convention — a trade that
                # did not happen, not a loss. Kept, because dropping it would
                # flatter whichever rule fills least.
                rs[lab] = o.r
            g = simulate(cs, i, s.entry, s.stop, s.is_long, target_r=TARGET_R,
                         fill_bars=fill_bars, horizon_bars=horizon,
                         fee_pct=0.0, **NO_FEE)
            rows.append(Row("held" if i < cut else "disc", "riptide",
                            100 * risk / s.entry, rs, g.r))

        # ---- LEZ, market entry at the close with a 1.5 ATR stop: what the
        # chart in front of the user is running.
        for x in lez_signals(cs):
            if atr[x.bar] <= 0 or x.bar + 1 + horizon > len(cs):
                continue
            entry = x.entry
            d = atr[x.bar] * STOP_ATR
            stop = entry - d if x.is_long else entry + d
            if entry <= 0 or stop <= 0:
                continue
            rs = {}
            ok = True
            for lab, kw in RULES:
                o = simulate_market(cs, x.bar, entry, stop, x.is_long,
                                    target_r=TARGET_R, horizon_bars=horizon,
                                    **FEE, **kw)
                if o is None:
                    ok = False
                    break
                rs[lab] = o.r
            if not ok:
                continue
            g = simulate_market(cs, x.bar, entry, stop, x.is_long,
                                target_r=TARGET_R, horizon_bars=horizon,
                                **NO_FEE)
            rows.append(Row("held" if x.bar < cut else "disc", "lez",
                            100 * d / entry, rs, g.r))
    return rows, days


# --------------------------------------------------------------- study A

def quintiles(vals):
    s = sorted(vals)
    return [s[len(s) * k // 5] for k in (1, 2, 3, 4)]


def study_a(rows, src, tf):
    print(f"\n  A. THE RISK FLOOR — {src}, {tf}")
    print(f"  {'risk_pct bucket':<20}{'n':>6}{'win':>6}{'risk':>7}"
          f"{'fee':>7}{'R net':>9}{'SE':>7}{'R gross':>9}")
    verdict = {}
    for half in ("disc", "held"):
        sub = [x for x in rows if x.half == half and x.src == src]
        if len(sub) < 150:
            print(f"    {half}: too few ({len(sub)})")
            continue
        cuts = quintiles([x.risk for x in sub])
        edges = [0.0] + cuts + [1e9]
        print(f"    -- {half} --")
        nets, grosses = [], []
        for lo, hi in zip(edges, edges[1:]):
            b = [x for x in sub if lo <= x.risk < hi]
            if len(b) < 25:
                nets.append(None)
                continue
            net = [x.rs["plain (fixed stop)"] for x in b]
            gro = [x.gross for x in b]
            m, se = mean_se(net)
            g = statistics.fmean(gro)
            nets.append(m)
            grosses.append(g)
            lab = f"{lo:.2f}-{hi:.2f}%" if hi < 1e8 else f">{lo:.2f}%"
            print(f"    {lab}".ljust(22)
                  + f"{len(b):>6}{sum(r > 0 for r in net) / len(b):>6.0%}"
                  + f"{statistics.fmean(x.risk for x in b):>6.2f}%"
                  + f"{g - m:>7.3f}{m:>+9.3f}{se:>7.3f}{g:>+9.3f}")
        v = [x for x in nets if x is not None]
        up = len(v) >= 4 and all(a <= b for a, b in zip(v, v[1:]))
        gup = (len(grosses) >= 4
               and all(a <= b for a, b in zip(grosses, grosses[1:])))
        verdict[half] = (up, gup)
        print(f"      net {'RISES monotonically' if up else 'not monotone'}"
              f"   ·   gross "
              f"{'also rises (setup quality, not fee)' if gup else 'does not'}")
    return verdict


# --------------------------------------------------------------- study B

def study_b(rows, src, tf):
    print(f"\n  B. STOP MANAGEMENT — {src}, {tf}, target {TARGET_R:g}R")
    print(f"  {'rule':<26}{'n':>6}{'win':>6}{'FULL':>7}{'losses':>8}"
          f"{'R net':>9}{'SE':>7}{'vs plain':>10}")
    base = {}
    for half in ("disc", "held"):
        sub = [x for x in rows if x.half == half and x.src == src]
        if len(sub) < 150:
            print(f"    {half}: too few ({len(sub)})")
            continue
        print(f"    -- {half} --")
        b0 = None
        for lab, _ in RULES:
            v = [x.rs[lab] for x in sub]
            m, se = mean_se(v)
            full = sum(1 for r in v if r <= FULL_LOSS_R)
            if b0 is None:
                b0 = (m, se, full)
            d = m - b0[0]
            print(f"    {lab:<24}{len(v):>6}"
                  f"{sum(r > 0 for r in v) / len(v):>6.0%}"
                  f"{full:>7}{full / len(v):>8.0%}{m:>+9.3f}{se:>7.3f}"
                  + (f"{d:>+10.3f}" if lab != RULES[0][0] else f"{'—':>10}"))
            base.setdefault(lab, {})[half] = m
    return base


def report(tf, rows, days):
    print(f"\n{'=' * 100}\n{tf}   {statistics.median(days):.0f} days across "
          f"{len(days)} symbols, split in half\n{'=' * 100}")
    for src in ("riptide", "lez"):
        n = len([x for x in rows if x.src == src])
        print(f"\n  ---- {src}: {n} signals ----")
        if n < 300:
            print("  too few")
            continue
        va = study_a(rows, src, tf)
        vb = study_b(rows, src, tf)
        print(f"\n  VERDICTS ({src}, {tf})")
        ok_a = (va.get("disc", (False,))[0] and va.get("held", (False,))[0]
                and not (va.get("disc", (0, True))[1]
                         and va.get("held", (0, True))[1]))
        print(f"    A  risk floor: {'RECOMMENDED' if ok_a else 'NOT SUPPORTED'}"
              f"  (net monotone both halves, and not merely setup quality)")
        winners = [lab for lab, d in vb.items()
                   if lab != RULES[0][0] and len(d) == 2
                   and all(v > d0 for v, d0 in
                           zip(d.values(), vb[RULES[0][0]].values()))]
        print(f"    B  management: "
              + (f"beats plain in both halves: {', '.join(winners)}"
                 if winners else "nothing beats the plain fixed stop in both "
                                 "halves"))


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = (await list_symbols(sess))[:SYMBOLS]
        print(f"The stop: where to put it, and what to do with it\n"
              f"{len(syms)} symbols · target {TARGET_R:g}R · riptide uses its "
              f"own limit entry and raid-extreme stop, lez a market entry at "
              f"the close with {STOP_ATR:g} x ATR({ATR_LEN})")
        for tf, pages in TFS:
            rows, days = await collect(sess, syms, tf, pages)
            if days:
                report(tf, rows, days)


if __name__ == "__main__":
    asyncio.run(main())
