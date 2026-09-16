"""Could ANY exit rule rescue a grab entry? An exit-free look at the path.

    python3 indicators/ccp/studies/ccp_excursion.py

A POST-HOC DIAGNOSTIC, not a pre-registered study. It gets no verdict and
cannot rescue one. It exists because `research/CCP_ENTRY_MODELS.md` found a
null against ONE exit — 2R target, 48-hour horizon — and that leaves a fair
objection open: maybe the entry is fine and the exit is wrong.

THE STATISTIC is exit-free. For each entry, walk forward and record which
happens first: price touches +1R, or −1R, where R is the same stop distance
the entry study used. On a driftless path that race is fair however you choose
to leave it — optional stopping — so a fair race means no stop-and-target
scheme can extract anything, and the 2R/48h null is about the ENTRY.

**50% IS NOT THE REFERENCE, AND READING IT AS ONE IS A MISTAKE THIS FILE MADE
ONCE.** Bars are discrete: a bar that spans both levels is scored adverse, the
pessimistic convention, so the statistic sits below 50% even on a perfectly
driftless path. The first run of this diagnostic read 48% against 50% and
called it symmetric, which was wrong twice over — wrong reference, and the
control it was compared against was mis-sized.

**THE RANDOM CONTROL IS THE REFERENCE.** It carries the same discreteness, the
same tie-break and — since the fix below — the same risk size. Read the GAP
between the two rows. Never read a row against 50%.

    grabs ≈ control   →   the path after a grab is like the path anywhere.
                          No exit rule helps; the entry is the problem.
    grabs >> control  →   there is an asymmetry, and whether any exit can
                          harvest it is then an OPEN question needing a prereg.

Reported alongside it:

  * MFE and MAE over the horizon, uncapped by any exit, which is what a
    trailing or partial scheme would be trying to capture. These are in units
    of R, so they are only comparable between groups that share a risk size —
    which the accepted/rejected split does and nothing else here does.
  * the same split by whether the CCP filter accepted the grab

None of this is scored in R and none of it pays fees. It is about the shape of
the path, and fees are what turn a fair path into a losing one.
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

os.environ.setdefault("RIPTIDE_DEEP_CACHE", ".cache/deep")
os.makedirs(os.environ["RIPTIDE_DEEP_CACHE"], exist_ok=True)

from research.data import SYMBOLS                        # noqa: E402
from research.deep import load_universe                  # noqa: E402
from indicators.ccp.tools.ccp_merge_check import atr14  # noqa: E402
from indicators.ccp.tools.ccp_at_grabs_check import grabs  # noqa: E402
from indicators.ccp.tools.ccp_anchor_check import (  # noqa: E402
    scan_incremental)

PIVOT = 3
CCP_BACK = CCP_FWD = 2
BODY_MAX = 0.15
WICK_MIN = 0.70
MIN_RANGE_ATR = 0.50
STOP_FLOOR_ATR = 0.25
DAYS = 333
TFS = (("Min15", 192), ("Min30", 96), ("Min60", 48))


def race(cs, sig: int, entry: float, risk: float, is_long: bool,
         horizon: int):
    """Which comes first over the horizon: +1R or −1R? And the excursions.

    Returns (first, mfe, mae). `first` is +1, −1, or 0 for neither inside the
    horizon. A bar that spans BOTH levels is scored as −1: the adverse side is
    assumed to trade first, which is the convention the harness uses and the
    pessimistic one. Being generous here is how a symmetric path is made to
    look like an edge.
    """
    up = entry + risk if is_long else entry - risk
    dn = entry - risk if is_long else entry + risk
    mfe = mae = 0.0
    first = 0
    for k in range(sig + 1, min(sig + horizon + 1, len(cs))):
        c = cs[k]
        f = ((c.h - entry) if is_long else (entry - c.l)) / risk
        a = ((entry - c.l) if is_long else (c.h - entry)) / risk
        mfe = max(mfe, f)
        mae = max(mae, a)
        if first == 0:
            hit_dn = (c.l <= dn) if is_long else (c.h >= dn)
            hit_up = (c.h >= up) if is_long else (c.l <= up)
            if hit_dn:
                first = -1
            elif hit_up:
                first = 1
    return first, mfe, mae


def stop_of(cs, lo_i: int, hi_i: int, entry: float, atr: float,
            is_long: bool) -> float | None:
    struct = (min(cs[k].l for k in range(lo_i, hi_i + 1)) if is_long
              else max(cs[k].h for k in range(lo_i, hi_i + 1)))
    floor = atr * STOP_FLOOR_ATR
    stop = (min(struct, entry - floor) if is_long
            else max(struct, entry + floor))
    if (stop >= entry) if is_long else (stop <= entry):
        return None
    return stop


def collect(cs, a, sym: str, horizon: int):
    """(grab rows, random-bar rows). Same stop shape, same race, same horizon."""
    rows, ctrl = [], []
    for pv, gb, is_high in grabs(cs, PIVOT, PIVOT):
        sig = gb + CCP_FWD
        lo_i, hi_i = gb - CCP_BACK, gb + CCP_FWD
        if lo_i < 0 or sig >= len(cs) - 1 or pv - CCP_BACK < 0:
            continue
        if a[sig] is None or a[gb] is None:
            continue
        is_long = not is_high
        entry = cs[sig].c
        stop = stop_of(cs, lo_i, hi_i, entry, a[sig], is_long)
        if stop is None:
            continue
        first, mfe, mae = race(cs, sig, entry, abs(entry - stop), is_long,
                               horizon)
        mn = a[gb] * MIN_RANGE_ATR
        left = scan_incremental(cs, pv, CCP_BACK, CCP_FWD, mn, is_long)
        right = scan_incremental(cs, gb, CCP_BACK, CCP_FWD, mn, is_long)
        rows.append({"first": first, "mfe": mfe, "mae": mae,
                     "A1": bool(left and right), "A2": bool(right)})

        # One random bar per grab, same direction, and — this is the part the
        # first version got wrong — the SAME RISK as a fraction of price.
        #
        # Matching the stop SHAPE instead of the stop SIZE was a confound, not
        # a control. A grab's stop sits behind the grab wick, so its R is large;
        # a random bar's 5-bar extreme is small. The +1R/-1R race is far more
        # sensitive to the pessimistic both-touched rule when R is small, because
        # more single bars span both levels. The control was therefore penalised
        # by its own sizing and the grabs looked better for a reason that had
        # nothing to do with grabs.
        risk_frac = abs(entry - stop) / entry
        rnd = random.Random(f"x|{sym}|{gb}")
        for _ in range(4):                       # a few tries, then give up
            j = rnd.randrange(CCP_BACK + 20, len(cs) - horizon - 1)
            if a[j] is None:
                continue
            e2 = cs[j].c
            f2, mf2, ma2 = race(cs, j, e2, e2 * risk_frac, is_long, horizon)
            ctrl.append({"first": f2, "mfe": mf2, "mae": ma2})
            break
    return rows, ctrl


def med(v):
    s = sorted(v)
    return s[len(s) // 2] if s else float("nan")


def line(label: str, rows) -> None:
    if not rows:
        print(f"    {label:<28} no rows")
        return
    n = len(rows)
    dec = [r for r in rows if r["first"] != 0]
    win = sum(1 for r in dec if r["first"] == 1)
    p = win / len(dec) if dec else float("nan")
    # SE on a proportion. Not clustered — this is a diagnostic and the
    # clustering only widens it, so a symmetric result stays symmetric.
    se = math.sqrt(p * (1 - p) / len(dec)) if dec else float("nan")
    z = (p - 0.5) / se if dec and se > 0 else float("nan")
    print(f"    {label:<28}{n:>7}   +1R first {100*p:5.1f}% ± {100*se:.1f}"
          f"   z {z:+5.2f}   undecided {100*(n-len(dec))/n:4.1f}%"
          f"   MFE {med(r['mfe'] for r in rows):.2f}"
          f"   MAE {med(r['mae'] for r in rows):.2f}")


async def main() -> None:
    print(__doc__.split("\n\n")[0])
    print("\nPOST-HOC DIAGNOSTIC. No verdict, no prereg, no fees.")
    print("Read the GAP between 'every grab' and 'random bars'. A row read")
    print("against 50% means nothing — see the module docstring.\n")

    async with aiohttp.ClientSession() as sess:
        for tf, horizon in TFS:
            uni = await load_universe(sess, SYMBOLS, tf, DAYS)
            rows, ctrl = [], []
            for sym, cs in uni.items():
                r, c = collect(cs, atr14(cs), sym, horizon)
                rows += r
                ctrl += c
            print(f"═══ {tf}  ({horizon} bars = 48h) ═══")
            line("every grab", rows)
            line("random bars, RISK-MATCHED", ctrl)
            line("CCP accepted (A1)", [r for r in rows if r["A1"]])
            line("CCP rejected", [r for r in rows if not r["A1"]])
            line("right end only (A2)", [r for r in rows if r["A2"]])
            print()

    print("READING IT: 50% is NOT the reference. Bars are discrete and a bar")
    print("spanning both levels is scored adverse, so the statistic is biased")
    print("below 50% even on a driftless path. THE RANDOM CONTROL IS THE")
    print("REFERENCE — it carries the same bias at the same risk size. Read")
    print("only the gap between the two rows, never a row against 50%.")


asyncio.run(main())
