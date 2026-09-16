"""When an end says "no shape", which test actually rejected it?

    python3 audit/ccp_reject_reasons.py

The Pine answer is a tooltip on one setup. This is the same question asked of
the whole universe, because "no shape" hides four completely different
verdicts and they do not mean the same thing:

  RANGE      the window was smaller than ccpMinRangeATR. That is a VOLUME
             CONTROL, not part of the shape test — the ratios are scale-free,
             so this is the one rejection that is purely about size. Set the
             input to 0 and it goes away.
  BODY       the body was too big a fraction of the range.
  WICK       the longer wick was too short a fraction of the range.
  DIRECTION  it WAS a pin, and it pointed the way the grab does not imply.
             Nothing about the shape is wrong; it is the wrong shape to want.

A candle that obviously looks like a hammer and comes back "no shape" is
almost always DIRECTION or RANGE, and neither means the classifier is broken.
Knowing which is the difference between changing a threshold and changing
nothing.
"""
from __future__ import annotations

import asyncio
import collections
import os
import sys

import aiohttp

sys.path.insert(0, ".")
os.environ.setdefault("RIPTIDE_DEEP_CACHE", ".cache/deep")

from research.data import SYMBOLS                        # noqa: E402
from research.deep import load_universe                  # noqa: E402
from audit.ccp_merge_check import atr14                  # noqa: E402
from audit.ccp_at_grabs_check import grabs               # noqa: E402

PIVOT = 3
BACK = FWD = 2
BODY_MAX = 0.15
WICK_MIN = 0.70
MIN_RANGE_ATR = 0.50
DAYS = 333


def why(cs, anchor, min_rng, want_bull):
    """(reasons Counter, closest window) for an anchor that matched nothing.

    Mirrors ccpWhy() in riptide-ccp.pine. A window can fail several tests at
    once and every failure is counted, because "it failed on the body AND
    pointed the wrong way" is a different situation from either alone.
    """
    n = collections.Counter()
    best, best_w = -1.0, None
    if anchor - BACK < 0 or anchor + FWD >= len(cs):
        return n, None
    for f in range(FWD + 1):
        hi = max(cs[k].h for k in range(anchor, anchor + f + 1))
        lo = min(cs[k].l for k in range(anchor, anchor + f + 1))
        cc = cs[anchor + f].c
        for b in range(BACK + 1):
            if b > 0:
                hi = max(hi, cs[anchor - b].h)
                lo = min(lo, cs[anchor - b].l)
            oo = cs[anchor - b].o
            rng = hi - lo
            n["tried"] += 1
            if rng <= 0 or rng < min_rng:
                n["RANGE"] += 1
                continue
            body = abs(cc - oo) / rng
            up = (hi - max(oo, cc)) / rng
            dn = (min(oo, cc) - lo) / rng
            big = max(up, dn)
            if body > BODY_MAX:
                n["BODY"] += 1
            if big < WICK_MIN:
                n["WICK"] += 1
            if (dn > up) != want_bull:
                n["DIRECTION"] += 1
            if big > best:
                best, best_w = big, (b, f, body, up, dn)
    return n, best_w


def sole_reason(n) -> str:
    """The ONE test that, if lifted, would have let something through.

    A window failing only on direction is a different animal from one failing
    on direction and body together — lifting the gate saves the first and not
    the second. This reports the reason that is sufficient on its own.
    """
    hit = [k for k in ("RANGE", "BODY", "WICK", "DIRECTION")
           if n[k] == n["tried"]]
    if len(hit) == 1:
        return hit[0] + " alone"
    if hit:
        return "+".join(hit)
    return "mixed"


async def main():
    async with aiohttp.ClientSession() as sess:
        for tf in ("Min15", "Min30", "Min60"):
            uni = await load_universe(sess, SYMBOLS, tf, DAYS)
            per = {"LEFT": collections.Counter(), "RIGHT": collections.Counter()}
            sole = {"LEFT": collections.Counter(), "RIGHT": collections.Counter()}
            miss = {"LEFT": 0, "RIGHT": 0}
            tot = 0
            for sym, cs in uni.items():
                a = atr14(cs)
                for pv, gb, is_high in grabs(cs, PIVOT, PIVOT):
                    if a[gb] is None or gb + FWD >= len(cs) or pv - BACK < 0:
                        continue
                    tot += 1
                    want = not is_high
                    mn = a[gb] * MIN_RANGE_ATR
                    for tag, anchor in (("LEFT", pv), ("RIGHT", gb)):
                        n, _ = why(cs, anchor, mn, want)
                        if not n["tried"]:
                            continue
                        # matched = at least one window passed everything
                        passed = n["tried"] - max(
                            n["RANGE"] + n["BODY"] + n["WICK"] + n["DIRECTION"],
                            0)
                        if n["RANGE"] + n["BODY"] + n["WICK"] + n["DIRECTION"] \
                                == 0:
                            continue                     # something matched
                        if passed > 0:
                            continue                     # something matched
                        miss[tag] += 1
                        for k in ("RANGE", "BODY", "WICK", "DIRECTION"):
                            if n[k]:
                                per[tag][k] += 1
                        sole[tag][sole_reason(n)] += 1

            print(f"═══ {tf} — {tot} grabs ═══")
            for tag in ("LEFT", "RIGHT"):
                m = miss[tag] or 1
                print(f"  {tag} end found nothing on {miss[tag]} grabs")
                print("    at least one window failed on …")
                for k in ("RANGE", "BODY", "WICK", "DIRECTION"):
                    print(f"      {k:<10}{per[tag][k]:>7}{100*per[tag][k]/m:>7.1f}%")
                print("    the ONE test that, if lifted, would have let "
                      "something through:")
                for k, v in sole[tag].most_common(5):
                    print(f"      {k:<22}{v:>7}{100*v/m:>7.1f}%")
            print()


if __name__ == "__main__":
    asyncio.run(main())
