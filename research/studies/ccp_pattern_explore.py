"""Which of the twelve CCP patterns pay at the right end of a grab?

    python3 research/studies/ccp_pattern_explore.py

EXPLORATORY. No prereg, no verdict, no pass. It runs on the DISCOVERY set only
— the 23 symbols in research.data.SYMBOLS — precisely so that the two holdouts
built for the FVG work stay clean: 84 unseen symbols, and the 862-day window
before the discovery window. Anything that looks real here gets a
pre-registered confirmation there, family size one, exactly as the FVG result
did. Nothing found here is a finding.

Twelve patterns is a family of twelve. Six arms produced three non-replicating
cells in CCP_CONTEXT_FILTERS, so the expectation is that several of these will
look good and that most of those will be noise. Reading this table as a
shortlist is the only safe way to read it.

THE RIGHT END, as asked: the pattern must sit in the grab window itself —
[grabBar - ccpBack, grabBar + ccpFwd] — the candles that ran the level. A 2CP
needs its engulfing candle inside that window too.

DIRECTION-GATED, per the sheet: only a bearish pattern at a buy-side grab and
only a bullish one at a sell-side grab.

ENTRY AND STOP COME FROM THE SHEET, not from the grab. That means a LIMIT
entry at the body edge, which may never fill — research.harness.simulate models
exactly that and scores an unfilled setup as 0.0 rather than as a loss. Both
numbers are reported, because "R per fill" flatters a pattern that rarely
fills and "R per signal" is what the account would see.
"""
from __future__ import annotations

import collections
import asyncio
import math
import os
import sys

import aiohttp

sys.path.insert(0, ".")
os.environ.setdefault("RIPTIDE_DEEP_CACHE", ".cache/deep")
os.makedirs(os.environ["RIPTIDE_DEEP_CACHE"], exist_ok=True)

from research.data import SYMBOLS                        # noqa: E402
from research.deep import load_universe                  # noqa: E402
from research.harness import simulate                    # noqa: E402
from audit.ccp_merge_check import atr14                  # noqa: E402
from audit.ccp_at_grabs_check import grabs               # noqa: E402
from research.studies.ccp_context_filters import clustered  # noqa: E402
from research.ccp_patterns import one_cp, two_cp, engulf_only  # noqa: E402

PIVOT = 3
CCP_BACK = CCP_FWD = 2
DAYS = 333
TFS = (("Min15", 192), ("Min30", 96), ("Min60", 48))
MIN_N = 100            # below this a row is printed but marked thin


def found(cs, gb: int, is_long: bool):
    """Every pattern in the grab window, direction-gated. (bar, spec) pairs."""
    out = []
    lo, hi = max(gb - CCP_BACK, 1), min(gb + CCP_FWD, len(cs) - 2)
    for i in range(lo, hi + 1):
        s = one_cp(cs[i])
        if s and s["bullish"] == is_long:
            out.append((i, s))
        if i + 1 <= hi + 1 and i + 1 < len(cs):
            for fn in (two_cp, engulf_only):
                s2 = fn(cs[i], cs[i + 1])
                if s2 and s2["bullish"] == is_long:
                    out.append((i + 1, s2))
    return out


def build(cs, a, sym: str, horizon: int):
    rows = []
    for pv, gb, is_high in grabs(cs, PIVOT, PIVOT):
        if gb - CCP_BACK < 1 or gb + CCP_FWD >= len(cs) - 2:
            continue
        is_long = not is_high
        for bar, s in found(cs, gb, is_long):
            risk = abs(s["entry"] - s["stop"])
            if risk <= 0 or bar >= len(cs) - 1:
                continue
            if (s["stop"] >= s["entry"]) if is_long else (s["stop"] <= s["entry"]):
                continue
            o = simulate(cs, bar, s["entry"], s["stop"], is_long,
                         target_r=2.0, horizon_bars=horizon)
            if o is None:
                continue
            rows.append({"sym": sym, "t": cs[bar].t, "name": s["name"],
                         "r": o.r, "filled": o.filled,
                         "risk_pct": 100.0 * risk / s["entry"]})
    return rows


async def main():
    print(__doc__.split("\n\n")[0])
    print("\nEXPLORATORY — discovery set only, 23 symbols. No verdict.")
    print("Twelve patterns plus two controls; expect several to look good by "
          "chance.\n")

    async with aiohttp.ClientSession() as sess:
        for tf, horizon in TFS:
            uni = await load_universe(sess, SYMBOLS, tf, DAYS)
            rows = []
            for sym, cs in uni.items():
                rows += build(cs, atr14(cs), sym, horizon)
            if not rows:
                continue
            by = collections.defaultdict(list)
            for r in rows:
                by[r["name"]].append(r)

            print(f"═══ {tf} — {len(rows)} pattern instances at grab ends ═══")
            print(f"  {'pattern':<38}{'n':>7}{'fill%':>7}"
                  f"{'R/signal':>10}{'SE':>7}{'R/fill':>9}{'risk%':>7}")
            print("  " + "-" * 85)
            order = sorted(by, key=lambda k: -sum(x["r"] for x in by[k])
                           / max(len(by[k]), 1))
            for name in order:
                g = by[name]
                keys = [(x["sym"], x["t"] // 86400) for x in g]
                m, se, n = clustered([x["r"] for x in g], keys)
                fil = [x for x in g if x["filled"]]
                rf = sum(x["r"] for x in fil) / len(fil) if fil else float("nan")
                med = sorted(x["risk_pct"] for x in g)[len(g) // 2]
                mark = "" if n >= MIN_N else "  thin"
                print(f"  {name:<38}{n:>7}{100*len(fil)/n:>7.1f}"
                      f"{m:>10.3f}{se:>7.3f}{rf:>9.3f}{med:>7.2f}{mark}")

            # The question that decides whether this is 12 patterns or 2.
            print()
            for col in ("green", "red"):
                ctl = by.get(f"CTL {col} engulfing, no pin")
                pins = [k for k in by if k.startswith("2CP")
                        and k.endswith(f"{col} engulfing")]
                if not ctl or not pins:
                    continue
                cm, cse, cn = clustered(
                    [x["r"] for x in ctl],
                    [(x["sym"], x["t"] // 86400) for x in ctl])
                allp = [x for k in pins for x in by[k]]
                pm, pse, pn = clustered(
                    [x["r"] for x in allp],
                    [(x["sym"], x["t"] // 86400) for x in allp])
                d = pm - cm
                se = math.sqrt(pse * pse + cse * cse)
                print(f"  DOES THE PIN ADD ANYTHING, {col} engulfing?")
                print(f"    all 2CPs   n {pn:>6}  R {pm:+.3f} ± {pse:.3f}")
                print(f"    no pin     n {cn:>6}  R {cm:+.3f} ± {cse:.3f}")
                print(f"    Δ {d:+.3f} ± {se:.3f}   z "
                      f"{d / se if se > 0 else float('nan'):+.2f}")
            print()

    print("READ THIS AS A SHORTLIST, NOT A RESULT. Anything here that looks")
    print("worth having goes to a pre-registered confirmation on the 84 unseen")
    print("symbols and the 862-day older window, family size one. That is the")
    print("path that turned the FVG hunch into three passes; the alternative")
    print("is the path CCP_FILTER_OVERFIT measured at +0.089 becoming -0.082.")


if __name__ == "__main__":
    asyncio.run(main())
