"""Does the CCP search in riptide-ccp.pine actually do what it says?

A TRANSCRIPTION of section 5's ccpScan/ccpName, run over real candles. Pine
cannot be executed here, so this is how the arithmetic gets checked before a
chart is loaded: same window search, same scoring, same four names, same
volume control.

It answers the questions the chart cannot answer at a glance:

  * how often does anything match at all
  * how many candles do the matches actually need — if "smallest run" almost
    always picks one candle, the merge is decoration and the search is not
    earning its cost
  * do the three tie-break modes disagree, and by how much

    python3 audit/ccp_merge_check.py
"""
from __future__ import annotations

import asyncio
import collections
import os
import sys

import aiohttp

sys.path.insert(0, ".")
os.environ.setdefault("RIPTIDE_LOOKBACK", "2000")

from riptide.exchange import fetch_candles        # noqa: E402
from research.data import SYMBOLS                 # noqa: E402

# The Pine defaults, so this measures what ships.
BACK, FWD = 3, 3
BODY_MAX = 0.35
WICK_MIN = 0.50
MIN_RANGE_ATR = 0.50
MODES = ("Smallest run", "Strongest wick", "Most centred")


def atr14(cs, n=14):
    tr, out, prev = [], [], None
    for i, c in enumerate(cs):
        t = c.h - c.l if i == 0 else max(c.h - c.l, abs(c.h - cs[i - 1].c),
                                         abs(c.l - cs[i - 1].c))
        tr.append(t)
        if i + 1 < n:
            out.append(None)
            continue
        prev = sum(tr[:n]) / n if prev is None else (prev * (n - 1) + t) / n
        out.append(prev)
    return out


def name_of(bull: bool, green: bool) -> str:
    """ccpName(). Shape decides direction; colour only picks the label."""
    if bull:
        return "Hammer" if green else "Hanging man"
    return "Inverted hammer" if green else "Shooting star"


def scan(cs, i: int, min_range: float, mode: str):
    """ccpScan() for anchor bar `i`. Returns (b, f, name, bull) or None.

    `i` is the ANCHOR, already `FWD` bars in the past relative to the bar the
    Pine evaluates on — the whole point being that every bar the search reads
    is closed by then.
    """
    if i - BACK < 0 or i + FWD >= len(cs):
        return None
    best = None
    best_score = -1e18
    for f in range(FWD + 1):
        hi = max(cs[k].h for k in range(i, i + f + 1))
        lo = min(cs[k].l for k in range(i, i + f + 1))
        cc = cs[i + f].c
        for b in range(BACK + 1):
            if b > 0:
                hi = max(hi, cs[i - b].h)
                lo = min(lo, cs[i - b].l)
            oo = cs[i - b].o
            rng = hi - lo
            if rng <= 0 or rng < min_range:
                continue
            body = abs(cc - oo) / rng
            up = (hi - max(oo, cc)) / rng
            dn = (min(oo, cc) - lo) / rng
            big = max(up, dn)
            if body > BODY_MAX or big < WICK_MIN:
                continue
            if mode == "Strongest wick":
                sc = big
            elif mode == "Most centred":
                sc = big - abs(b - f) * 100
            else:
                sc = big - (b + f) * 100
            if sc > best_score:
                best_score = sc
                best = (b, f, name_of(dn > up, cc >= oo), dn > up)
    return best


async def main():
    per_mode = {m: collections.Counter() for m in MODES}
    sizes = {m: collections.Counter() for m in MODES}
    anchors = 0
    agree = 0
    compared = 0

    async with aiohttp.ClientSession() as s:
        for sym in SYMBOLS:
            try:
                cs = await fetch_candles(s, sym, "Min15")
            except Exception:                                  # noqa: BLE001
                continue
            if len(cs) < 300:
                continue
            a = atr14(cs)
            for i in range(BACK + 20, len(cs) - FWD):
                if a[i] is None:
                    continue
                anchors += 1
                got = {}
                for m in MODES:
                    r = scan(cs, i, a[i] * MIN_RANGE_ATR, m)
                    got[m] = r
                    if r:
                        per_mode[m][r[2]] += 1
                        sizes[m][r[0] + r[1] + 1] += 1
                if got["Smallest run"] and got["Strongest wick"]:
                    compared += 1
                    if got["Smallest run"][:2] == got["Strongest wick"][:2]:
                        agree += 1

    print(f"{anchors} anchors, 23 symbols, Min15, pivot window "
          f"{BACK} before / {FWD} after")
    print(f"body <= {BODY_MAX}, longer wick >= {WICK_MIN}, "
          f"min range {MIN_RANGE_ATR} ATR\n")

    print(f"  {'mode':<16}{'matches':>9}{'rate':>8}   by name")
    print("  " + "-" * 74)
    for m in MODES:
        tot = sum(per_mode[m].values())
        by = "  ".join(f"{k.split()[0][:4]} {v}" for k, v in
                       per_mode[m].most_common())
        print(f"  {m:<16}{tot:>9}{100*tot/anchors:>7.1f}%   {by}")

    print(f"\n  HOW MANY CANDLES THE MATCH ACTUALLY NEEDED")
    print(f"  {'mode':<16}" + "".join(f"{n:>7}" for n in range(1, 8)))
    print("  " + "-" * 62)
    for m in MODES:
        tot = sum(sizes[m].values()) or 1
        row = "".join(f"{100*sizes[m][n]/tot:>6.0f}%" for n in range(1, 8))
        print(f"  {m:<16}{row}")
    print("\n  If 'Smallest run' is almost all 1, the merge is decoration on")
    print("  this data and the search is not earning its cost.")

    if compared:
        print(f"\n  'Smallest run' and 'Strongest wick' pick the SAME window "
              f"{100*agree/compared:.0f}% of the time ({agree}/{compared}).")
        print("  Far below 100% means the tie-break is a real choice, not a "
              "formality.")


if __name__ == "__main__":
    # Guarded because audit/ccp_anchor_check.py imports atr14 and name_of from
    # here. Without it, the import re-ran this whole study.
    asyncio.run(main())
