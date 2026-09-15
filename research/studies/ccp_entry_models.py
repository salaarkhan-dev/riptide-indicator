"""Is there a tradeable entry in the CCP-at-grab mark?

Pre-registered in PREREG_ccp_entry_models.md, committed before this ran.

    python3 research/studies/ccp_entry_models.py

THE DESIGN IN ONE SENTENCE: every grab gets the same entry bar, the same stop
rule and the same target, so the arms differ by WHICH GRABS THEY ACCEPT and by
nothing else. Anything that separates them is selection, not execution.

Arms, all on that identical entry:

    B     every grab — the reference, not under test
    A1    CCP fires at BOTH ends, direction-gated (the shipped default)
    A2    CCP fires at the RIGHT end only
    A3    A1 plus ccpAnchorExtreme — the long wick must be the anchor's own
    C0    control: same grabs as B, entry bar drawn at random from the 20 bars
          after the signal bar, seeded so it cannot be re-rolled

The primary metric is Δ = mean R(accepted) − mean R(rejected) inside a panel.
The number that decides whether anything is TRADEABLE is the standalone net R,
and it is reported next to Δ so the two cannot be confused.
"""
from __future__ import annotations

import asyncio
import collections
import math
import os
import random
import sys

import aiohttp

sys.path.insert(0, ".")

# research.deep reads this at IMPORT time, so it has to be set before the
# import below, not inside main(). Without it every re-run refetches 333 days
# on three timeframes.
os.environ.setdefault("RIPTIDE_DEEP_CACHE", ".cache/deep")
os.makedirs(os.environ["RIPTIDE_DEEP_CACHE"], exist_ok=True)

from research.data import SYMBOLS                        # noqa: E402
from research.deep import load_universe                  # noqa: E402
from research.harness import simulate_market             # noqa: E402
from audit.ccp_merge_check import atr14                  # noqa: E402
from audit.ccp_at_grabs_check import grabs               # noqa: E402
from audit.ccp_anchor_check import scan_incremental      # noqa: E402

# Every one of these is the shipped Pine default. None is swept — the prereg
# forbids it, and a sweep here is how a study becomes a fit.
PIVOT = 3
CCP_BACK = CCP_FWD = 2
BODY_MAX = 0.15
WICK_MIN = 0.70
MIN_RANGE_ATR = 0.50

TARGET_R = 2.0
STOP_FLOOR_ATR = 0.25          # prereg: the guard against MS_ENTRY_MODELS' E1/E4
RISK_FLOOR_PCT = 0.42          # prereg: below this a panel is unmeasurable
MIN_BETS = 200                 # prereg bar 1
MDE_CEILING = 0.25             # prereg: above this a panel is UNDERPOWERED
RANDOM_SPAN = 20               # C0 draws from the 20 bars after the signal bar

DAYS = 333
TFS = (("Min15", 192), ("Min30", 96), ("Min60", 48))
ARMS = ("A1", "A2", "A3")

# `--gross` zeroes the fees. This is a POST-HOC DIAGNOSTIC and is NOT one of
# the pre-registered arms: it does not get a verdict and cannot rescue one. It
# answers a single question the net numbers cannot — is a losing arm losing
# because the edge is absent, or because the edge is smaller than the cost of
# taking it? Those have completely different next steps.
GROSS = "--gross" in sys.argv
FEE_KW = {"fee_pct": 0.0} if GROSS else {}


def clustered(rows, key) -> tuple[float, float, int]:
    """Mean and a cluster-robust SE, clustering by `key`.

    Grabs on one symbol on one day share a level, a session and a move. Taking
    a plain SE over them treats that correlation as independent evidence, which
    is how a z-score gets manufactured out of autocorrelation. Declared as the
    primary SE in the prereg, before any of these numbers existed.
    """
    v = [r["r"] for r in rows]
    n = len(v)
    if n < 2:
        return (v[0] if v else 0.0), float("inf"), n
    m = sum(v) / n
    by = collections.defaultdict(list)
    for r in rows:
        by[key(r)].append(r["r"] - m)
    g = len(by)
    if g < 2:
        return m, float("inf"), n
    meat = sum(sum(d) ** 2 for d in by.values())
    # CR1 small-sample correction, the usual one.
    se = math.sqrt(meat * g / max(g - 1, 1)) / n
    return m, se, n


def diff_z(acc, rej, key) -> tuple[float, float]:
    ma, sa, na = clustered(acc, key)
    mr, sr, nr = clustered(rej, key)
    if not na or not nr or math.isinf(sa) or math.isinf(sr):
        return float("nan"), float("nan")
    se = math.sqrt(sa * sa + sr * sr)
    d = ma - mr
    return d, (d / se if se > 0 else float("nan"))


def build(cs, a, tf: str, sym: str, horizon: int) -> list[dict]:
    """One row per grab: the identical trade, plus which arms accepted it."""
    out = []
    for pv, gb, is_high in grabs(cs, PIVOT, PIVOT):
        sig = gb + CCP_FWD
        lo_i, hi_i = gb - CCP_BACK, gb + CCP_FWD
        if lo_i < 0 or sig >= len(cs) - 1 or pv - CCP_BACK < 0:
            continue
        if a[sig] is None or a[gb] is None:
            continue

        is_long = not is_high
        entry = cs[sig].c
        # The extreme of the widest window the right-end search can see. The
        # same rule whether or not CCP fired, which is the whole point.
        struct = (min(cs[k].l for k in range(lo_i, hi_i + 1)) if is_long
                  else max(cs[k].h for k in range(lo_i, hi_i + 1)))
        floor = a[sig] * STOP_FLOOR_ATR
        stop = (min(struct, entry - floor) if is_long
                else max(struct, entry + floor))
        if (stop >= entry) if is_long else (stop <= entry):
            continue                                   # wrong side: SKIP

        o = simulate_market(cs, sig, entry, stop, is_long,
                            target_r=TARGET_R, horizon_bars=horizon,
                            **FEE_KW)
        if o is None:
            continue

        # The three filters, on the identical trade.
        mn = a[gb] * MIN_RANGE_ATR
        want = is_long
        left = scan_incremental(cs, pv, CCP_BACK, CCP_FWD, mn, want)
        right = scan_incremental(cs, gb, CCP_BACK, CCP_FWD, mn, want)
        right_x = scan_incremental(cs, gb, CCP_BACK, CCP_FWD, mn, want, True)
        left_x = scan_incremental(cs, pv, CCP_BACK, CCP_FWD, mn, want, True)

        row = {
            "sym": sym, "bar": sig, "t": cs[sig].t, "r": o.r,
            "exit": o.exit, "long": is_long,
            "risk_pct": 100.0 * abs(entry - stop) / entry,
            "A1": bool(left and right),
            "A2": bool(right),
            "A3": bool(left_x and right_x),
        }

        # C0 — the timing control. Same grab, same direction, same stop RULE,
        # a different bar. Seeded on the grab so a re-run cannot re-roll it.
        rnd = random.Random(f"{sym}|{tf}|{gb}")
        csig = sig + rnd.randrange(RANDOM_SPAN + 1)
        row["c0"] = None
        if csig < len(cs) - 1 and a[csig] is not None:
            centry = cs[csig].c
            cfloor = a[csig] * STOP_FLOOR_ATR
            cstop = (min(struct, centry - cfloor) if is_long
                     else max(struct, centry + cfloor))
            if ((cstop < centry) if is_long else (cstop > centry)):
                co = simulate_market(cs, csig, centry, cstop, is_long,
                                     target_r=TARGET_R, horizon_bars=horizon,
                                     **FEE_KW)
                if co is not None:
                    row["c0"] = co.r
        out.append(row)
    return out


def day(r) -> tuple:
    return (r["sym"], r["t"] // 86400)


def panel(rows, label: str) -> None:
    if not rows:
        print(f"  {label:<10} no rows")
        return
    key = day
    mb, sb, nb = clustered(rows, key)
    c0 = [{"r": r["c0"], "sym": r["sym"], "t": r["t"]}
          for r in rows if r["c0"] is not None]
    mc, sc, nc = clustered(c0, key) if c0 else (float("nan"), float("nan"), 0)
    risk = sorted(r["risk_pct"] for r in rows)
    med = risk[len(risk) // 2]
    p25, p75 = risk[len(risk) // 4], risk[3 * len(risk) // 4]
    # Fees are charged in R as fee% / risk%, so the cost of a trade is 1/risk
    # — convex. The small-risk tail, not the median, is what sets the mean
    # drag, and quoting only the median hides that by a factor of two.
    drag = sum(0.044 / r["risk_pct"] for r in rows) / len(rows)

    print(f"  {label}")
    print(f"    {'B  every grab':<34}{nb:>7} bets   "
          f"R {mb:+.3f} ± {sb:.3f}")
    print(f"    {'C0 random bar within 20':<34}{nc:>7} bets   "
          f"R {mc:+.3f} ± {sc:.3f}")
    print(f"    risk % of price: p25 {p25:.2f}  median {med:.2f}  "
          f"p75 {p75:.2f}   mean fee drag {drag:.3f} R"
          + ("   << MEDIAN BELOW 0.42%, UNMEASURABLE ON ITS STOP"
             if med < RISK_FLOOR_PCT else ""))

    for arm in ARMS:
        acc = [r for r in rows if r[arm]]
        rej = [r for r in rows if not r[arm]]
        ma, sa, na = clustered(acc, key) if acc else (float("nan"),
                                                     float("inf"), 0)
        d, z = diff_z(acc, rej, key) if acc and rej else (float("nan"),
                                                         float("nan"))
        mde = 2.0 * math.sqrt(sa * sa + (clustered(rej, key)[1] ** 2)) \
            if acc and rej and not math.isinf(sa) else float("inf")
        flags = []
        if na < MIN_BETS:
            flags.append(f"BAR 1 FAIL: {na} < {MIN_BETS} bets")
        if mde > MDE_CEILING:
            flags.append(f"UNDERPOWERED: MDE {mde:.2f} R")
        print(f"    {arm:<4}{na:>7} accepted   R {ma:+.3f} ± {sa:.3f}"
              f"   Δ {d:+.3f}   z {z:+.2f}"
              + ("   " + " | ".join(flags) if flags else ""))
    print()


async def main() -> None:
    print(__doc__.split("\n\n")[0])
    print(f"\n{len(SYMBOLS)} symbols, {DAYS} days, pivot {PIVOT}/{PIVOT}, "
          f"CCP {CCP_BACK}/{CCP_FWD}, body ≤ {BODY_MAX}, wick ≥ {WICK_MIN}")
    print(f"target {TARGET_R}R, stop floor {STOP_FLOOR_ATR} ATR, "
          f"SE clustered by (symbol, day)\n")

    store: dict[str, list[dict]] = {}
    async with aiohttp.ClientSession() as sess:
        for tf, horizon in TFS:
            uni = await load_universe(sess, SYMBOLS, tf, DAYS)
            rows: list[dict] = []
            for sym, cs in uni.items():
                rows += build(cs, atr14(cs), tf, sym, horizon)
            store[tf] = rows
            print(f"{tf}: {len(uni)} symbols, {len(rows)} scored grabs")

    print()
    for tf, _ in TFS:
        rows = store[tf]
        if not rows:
            print(f"{tf}: nothing scored\n")
            continue
        rows.sort(key=lambda r: r["t"])
        cut = len(rows) // 2
        print(f"═══ {tf} ═══")
        panel(rows[:cut], "OLDER half")
        panel(rows[cut:], "NEWER half")

    print("═══ VERDICT AGAINST THE PRE-REGISTERED BARS ═══")
    print("Family: 3 arms x 3 timeframes x 2 halves = 18 tests. At z >= 2.0")
    print("each, the chance of at least one false positive is about 60%, so")
    print("bar 5 alone carries nothing.\n")
    for arm in ARMS:
        signs, pos_r, cov, lines = set(), [], [], []
        pooled_new: list[dict] = []
        pooled_rej: list[dict] = []
        for tf, _ in TFS:
            rows = store[tf]
            if not rows:
                continue
            cut = len(rows) // 2
            for half, sl in (("old", rows[:cut]), ("new", rows[cut:])):
                acc = [r for r in sl if r[arm]]
                rej = [r for r in sl if not r[arm]]
                if not acc or not rej:
                    continue
                d, z = diff_z(acc, rej, day)
                m = clustered(acc, day)[0]
                cov.append(len(acc) >= MIN_BETS)
                if not math.isnan(d):
                    signs.add(d > 0)
                if half == "new":
                    pos_r.append((d > 0, m > 0))
                    # Pooled across timeframes for bar 5, which the prereg
                    # states on "the pooled newer half".
                    pooled_new += acc
                    pooled_rej += rej
                lines.append(f"      {tf} {half}: Δ {d:+.3f}  z {z:+.2f}  "
                             f"R {m:+.3f}  n {len(acc)}")
        print(f"  {arm}")
        for l in lines:
            print(l)
        b1 = all(cov) and bool(cov)
        b2 = len(signs) == 1
        b3 = bool(pos_r) and all(d for d, _ in pos_r)
        b4 = bool(pos_r) and all(r for _, r in pos_r)
        pd, pz = (diff_z(pooled_new, pooled_rej, day)
                  if pooled_new and pooled_rej else (float("nan"),
                                                     float("nan")))
        b5 = (not math.isnan(pz)) and abs(pz) >= 2.0
        for n, ok, what in ((1, b1, "200+ bets in every panel"),
                            (2, b2, "one sign across six panels"),
                            (3, b3, "beats what it rejected, newer half"),
                            (4, b4, "positive standalone R, newer half"),
                            (5, b5, f"clustered |z| >= 2 pooled newer half "
                                    f"(Δ {pd:+.3f}, z {pz:+.2f})")):
            print(f"      bar {n}  {'PASS' if ok else 'FAIL'}  {what}")
        print(f"      → {'PASSES ALL FIVE' if all((b1,b2,b3,b4,b5)) else 'FAILS'}"
              f"   (and bar 5 alone carries nothing — 18 tests)")
        print()


asyncio.run(main())
