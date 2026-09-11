"""Stop distance in the coin's own ATR — the pre-registered test.

READ `research/studies/PREREG_stop_atr.md` FIRST. It was committed at e2f16b0
before this variable was computed on any row, and it fixes the variable, the
direction, the bucketing, the two sets and the three pass criteria. This file
executes it and nothing more. Where the two disagree, the prereg is the record.

In brief, so this file is readable on its own:

    R_ATR = |entry - stop| / ATR(28) at the signal bar

    predicted: LOW beats HIGH. That follows arithmetically from the one
    symbols.py result that held across both halves — inside the 1.2-2.6% stop
    band, the WILD volatility tercile beat the calm one by +0.300 then +0.298 —
    because holding stop-percent fixed and raising ATR IS lowering this ratio.
    A naive reading predicts the opposite: a stop close in ATR terms is more
    exposed to ordinary noise.

    discovery: the original 60 symbols. held-out: crypto symbols ranked 60th to
    120th by turnover, loaded for MEASUREMENT ONLY — production still scans the
    3M floor and no thinner coin reaches an alert.

    pass = (1) discovery spread >= discovery MDE and in the predicted
    direction, (2) winning tercile's symbol bootstrap 5th percentile above
    zero, (3) held-out reproduces the SIGN with the FROZEN boundaries at at
    least half the discovery spread. Criterion 3 is sign-and-magnitude, not
    significance: at ~440 bets the held-out set could not reach significance
    even if the effect were entirely real.

TWO SANITY CHECKS THE PREREG DEMANDED IN ADVANCE, both printed below whatever
the result: the correlation between R_ATR and plain stop-percent, because above
about 0.8 they are the same variable and this adds nothing; and the median
turnover of each set, because the held-out symbols are thinner by construction
and liquidity is a live alternative explanation if that arm disagrees.

    PYTHONPATH=. RIPTIDE_MIN_GRADE=B RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/stop_atr.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import json                                             # noqa: E402
import math                                             # noqa: E402
import os                                               # noqa: E402
import statistics                                       # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import CFG, TRACK_TARGET_R          # noqa: E402
from riptide.engine import atr_series, grade_of, run_engine  # noqa: E402
from riptide.exchange import fetch_candles              # noqa: E402
from riptide.trend import di_at, direction_at, poi_at   # noqa: E402
from research.deep import load_universe                 # noqa: E402
from research.harness import mean_se, simulate          # noqa: E402
from research.studies.power import mde                  # noqa: E402
from research.studies.report import bets_of             # noqa: E402
from research.studies.survivor import LO, HI, symbol_bootstrap  # noqa: E402

DAYS = 333
INTERVAL = "Min30"
DRAWS = 4000
HOLDOUT_FILE = "/tmp/holdout.json"      # written by the loader, see prereg


class Row:
    __slots__ = ("sym", "t", "r", "ratio", "risk_pct")


async def collect(sess, candles):
    out = []
    for sym, cs in candles.items():
        try:
            setups = run_engine(sym, cs, CFG)
        except Exception:
            continue
        idx = {c.t: i for i, c in enumerate(cs)}
        atr = atr_series(cs, CFG.atr_len)
        for x in setups:
            i = idx.get(x.detected_time)
            if i is None or x.entry <= 0 or abs(x.entry - x.stop) <= 0:
                continue
            a = atr[i] if i < len(atr) else 0.0
            if not a:
                continue
            w = x.detected_time
            poi = await poi_at(sess, sym, w, x.stop, x.is_long, fetch_candles)
            if not (True if poi is None else bool(poi)):
                continue
            d = await direction_at(sess, sym, w, fetch_candles)
            di = await di_at(sess, sym, w, fetch_candles)
            if grade_of(False, True, d or 0, x.is_long, di or 0)[0] not in "AB":
                continue
            o = simulate(cs, i, x.entry, x.stop, x.is_long,
                         target_r=TRACK_TARGET_R)
            if not o.filled or o.exit_bar is None:
                continue
            z = Row()
            z.sym, z.t, z.r = sym, w, o.r
            z.ratio = abs(x.entry - x.stop) / a
            z.risk_pct = 100 * abs(x.entry - x.stop) / x.entry
            out.append(z)
    return out


def cell(rows, draws=DRAWS):
    b = bets_of(rows)
    m, se = mean_se(b)
    bo = symbol_bootstrap(rows, draws)
    p5 = bo[int(0.05 * (len(bo) - 1))] if bo else float("nan")
    return len(rows), len(b), m, se, p5


def show(name, rows, cuts):
    """Three frozen buckets, low to high. Returns (low mean, high mean)."""
    lo_, mid, hi_ = ([r for r in rows if r.ratio <= cuts[0]],
                     [r for r in rows if cuts[0] < r.ratio <= cuts[1]],
                     [r for r in rows if r.ratio > cuts[1]])
    print(f"\n  {name}")
    means = {}
    for lab, g in (("LOW  (tight vs ATR)", lo_), ("mid", mid),
                   ("HIGH (wide vs ATR)", hi_)):
        if len(g) < 25:
            print(f"    {lab:<22} {len(g):>4} tr — thin")
            continue
        n, nb, m, se, p5 = cell(g)
        means[lab[:3]] = m
        print(f"    {lab:<22} {n:>4} tr {nb:>4} bets  "
              f"{sum(1 for r in g if r.r > 0) / n:>3.0%} win  "
              f"{m:>+6.3f}±{se:.3f}  boot5th {p5:>+6.3f}"
              f"{'  OK' if p5 > 0 else ''}")
    return means.get("LOW"), means.get("HIG"), lo_, hi_


def pearson(xs, ys):
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    den = math.sqrt(sum((a - mx) ** 2 for a in xs)
                    * sum((b - my) ** 2 for b in ys))
    return num / den if den else float("nan")


async def main():
    meta = json.load(open(HOLDOUT_FILE))
    ranked, turn = meta["ranked"], meta["turnover"]
    have = {f.split(".")[0] for f in os.listdir(os.environ["RIPTIDE_DEEP_CACHE"])
            if ".Min30." in f}
    disc_syms = [s for s in ranked[:60] if s in have]
    hold_syms = [s for s in ranked[60:] if s in have]

    async with aiohttp.ClientSession() as sess:
        disc = await collect(sess, await load_universe(
            sess, disc_syms, INTERVAL, DAYS))
        hold = await collect(sess, await load_universe(
            sess, hold_syms, INTERVAL, DAYS))

    bd = bets_of(disc)
    m_disc = mde(statistics.pstdev(bd), len(bd) / 2)
    bh = bets_of(hold)
    m_hold = mde(statistics.pstdev(bh), len(bh) / 2) if len(bh) > 40 else float("nan")

    print("STOP DISTANCE IN ATR — the pre-registered test\n"
          f"discovery {len(disc_syms)} symbols, {len(disc)} trades, {len(bd)} "
          f"bets, MDE {m_disc:.3f}\n"
          f"held-out  {len(hold_syms)} symbols, {len(hold)} trades, {len(bh)} "
          f"bets, MDE {m_hold:.3f}\n"
          "predicted before the data: LOW beats HIGH")

    print("\n-- THE TWO CHECKS THE PREREG DEMANDED IN ADVANCE " + "-" * 28)
    c = pearson([r.ratio for r in disc], [r.risk_pct for r in disc])
    print(f"  correlation of R_ATR with plain stop-% : {c:+.3f}"
          f"   ({'SAME VARIABLE, this adds nothing' if abs(c) > 0.8 else 'distinct enough to be worth testing'})")
    print(f"  median 24h turnover  discovery {statistics.median(turn[s] for s in disc_syms)/1e6:>6.1f}M"
          f"   held-out {statistics.median(turn[s] for s in hold_syms)/1e6:>6.1f}M"
          if hold_syms else "  held-out set empty")

    # Boundaries cut on DISCOVERY ONLY, then frozen.
    vals = sorted(r.ratio for r in disc)
    cuts = (vals[len(vals) // 3], vals[2 * len(vals) // 3])
    print(f"\n  frozen tercile boundaries from discovery: "
          f"{cuts[0]:.3f} and {cuts[1]:.3f} (stop / ATR)")

    print("\n-- DISCOVERY " + "-" * 64)
    d_lo, d_hi, lo_rows, _ = show("all confirmed A/B", disc, cuts)
    show(f"secondary: stop {LO}-{HI}% only (MDE 0.497, underpowered by design)",
         [r for r in disc if LO <= r.risk_pct <= HI], cuts)

    print("\n-- HELD-OUT (frozen boundaries, symbols never fitted on) " + "-" * 20)
    h_lo, h_hi, _, _ = show("all confirmed A/B", hold, cuts)

    print("\n-- VERDICT AGAINST THE THREE PRE-REGISTERED CRITERIA " + "-" * 24)
    if d_lo is None or d_hi is None:
        print("  discovery buckets too thin — no verdict.")
        return
    d_spread = d_lo - d_hi
    _, _, _, _, p5 = cell(lo_rows)
    c1 = d_spread >= m_disc
    c2 = p5 > 0
    c3 = (h_lo is not None and h_hi is not None
          and (h_lo - h_hi) >= 0.5 * d_spread and d_spread > 0)
    print(f"  1. discovery LOW-HIGH {d_spread:>+7.3f} vs MDE {m_disc:.3f}"
          f"          [{'PASS' if c1 else 'FAIL'}]")
    print(f"  2. LOW tercile bootstrap 5th {p5:>+7.3f} above zero"
          f"          [{'PASS' if c2 else 'FAIL'}]")
    if h_lo is None or h_hi is None:
        print("  3. held-out too thin to read                            [FAIL]")
    else:
        print(f"  3. held-out LOW-HIGH {(h_lo - h_hi):>+7.3f} vs half of "
              f"discovery {0.5 * d_spread:>+6.3f}   "
              f"[{'PASS' if c3 else 'FAIL'}]")
    print(f"\n  -> {'SURVIVES' if (c1 and c2 and c3) else 'DOES NOT SURVIVE'}"
          "  (all three were required; see PREREG_stop_atr.md)")


if __name__ == "__main__":
    asyncio.run(main())
