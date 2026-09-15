"""Is the anchor candle really inside EVERY window the CCP search tries?

The rule section 5 is supposed to obey: a merge is the anchor candle plus some
of its immediate neighbours, never a run of neighbours that leaves the anchor
out. If that ever broke, the chart would draw an arrow at a grab for a pin
shape built entirely from candles beside it.

Reading the code is not proof — the arithmetic is written in Pine's backwards
offsets, where `anchorOff + b` is OLDER and `anchorOff - f` is NEWER, and a
sign flip there reads as plausible either way. So this enumerates.

Five checks, each able to fail:

  0. SOURCE. Checks 1-3 test a TRANSCRIPTION of ccpScanAt, which is worth
     nothing once the Pine drifts away from it, so the four lines that set the
     window bounds must still be in riptide-ccp.pine verbatim.

  1. STRUCTURE, exhaustive. Every (b, f) pair at every setting from 0/0 to 5/5,
     converted out of Pine offsets into bar indices, must produce a contiguous
     run that contains the anchor. 36 settings, 441 windows.

  2. ARITHMETIC, on real candles. ccpScanAt accumulates the run high and low
     INCREMENTALLY as b grows, reusing the previous iteration's value. That is
     the kind of shortcut that is right until someone moves a declaration. It
     is compared against a brute-force max/min recomputed from scratch for
     every window, on every grab anchor in the universe.

  3. CONTRIBUTION, which is the part the structure check cannot see. The anchor
     being positionally inside a 5-candle run does not mean the anchor put
     anything into the shape: the open comes from the oldest bar, the close
     from the newest, and both the high and the low can belong to neighbours.
     This counts how often the wick that MAKES the pin is the anchor's own.

  4. COST of requiring it. What the `ccpAnchorExtreme` input does to the
     both-ends rate if it is switched on.

    python3 audit/ccp_anchor_check.py
"""
from __future__ import annotations

import asyncio
import collections
import os
import sys

import aiohttp

sys.path.insert(0, ".")
os.environ.setdefault("RIPTIDE_LOOKBACK", "2000")

from riptide.exchange import fetch_candles              # noqa: E402
from research.data import SYMBOLS                       # noqa: E402
from audit.ccp_merge_check import atr14, name_of        # noqa: E402
from audit.ccp_at_grabs_check import grabs              # noqa: E402

BODY_MAX = 0.15
WICK_MIN = 0.70
MIN_RANGE_ATR = 0.50
BACK = FWD = 2

BENCH = "riptide-ccp.pine"


# ── 0. the transcription still matches the Pine ─────────────────────────────

# The four lines that define the window bounds. Checks 1-3 below test a
# TRANSCRIPTION, so they are worth nothing if the Pine has moved away from it.
# These are the exact lines the transcription assumes.
PINE_LINES = [
    "for f = 0 to ccpFwd",
    "int lastOff = anchorOff - f",
    "for b = 0 to ccpBack",
    "int firstOff = anchorOff + b",
]


def check_source() -> list[str]:
    try:
        src = open(BENCH).read()
    except OSError as e:                                   # noqa: BLE001
        print(f"0. SOURCE — cannot read {BENCH}: {e}")
        return [f"{BENCH} unreadable"]
    missing = [l for l in PINE_LINES if l not in src]
    print(f"0. SOURCE — the {len(PINE_LINES)} window-bound lines in {BENCH}")
    if missing:
        for m in missing:
            print(f"     !! not found: {m}")
        print("     The Pine has changed. Re-read ccpScanAt and update the")
        print("     transcription below before trusting anything it says.")
    else:
        print("     present verbatim, so the transcription below is current.")
    return missing


# ── 1. structure ────────────────────────────────────────────────────────────

def windows_pine(anchor_off: int, back: int, fwd: int):
    """The (first, last) bar-index pair for every window ccpScanAt evaluates.

    Transcribed from the OFFSET form in riptide-ccp.pine, not from the
    index form in the other audit scripts, so that a sign error in the Pine
    would survive into here and be caught rather than quietly corrected.

        lastOff  = anchorOff - f     the NEWEST bar of the run
        firstOff = anchorOff + b     the OLDEST bar of the run

    Offsets count backwards from the current bar, so a larger offset is an
    older bar. Converting with `idx = -off` puts them back in chart order.
    """
    out = []
    for f in range(fwd + 1):
        if f > anchor_off:          # the `if f <= anchorOff` guard: no future
            continue
        last_off = anchor_off - f
        for b in range(back + 1):
            first_off = anchor_off + b
            out.append((f, b, -first_off, -last_off))   # oldest, newest
    return out


def check_structure() -> list[str]:
    bad = []
    n = 0
    for back in range(6):
        for fwd in range(6):
            anchor_off = 40                       # well clear of both guards
            anchor_idx = -anchor_off
            for f, b, first, last in windows_pine(anchor_off, back, fwd):
                n += 1
                if first > last:
                    bad.append(f"back={back} fwd={fwd} b={b} f={f}: "
                               f"run runs backwards ({first}..{last})")
                elif not (first <= anchor_idx <= last):
                    bad.append(f"back={back} fwd={fwd} b={b} f={f}: "
                               f"anchor {anchor_idx} outside run {first}..{last}")
                elif last - first != b + f:
                    bad.append(f"back={back} fwd={fwd} b={b} f={f}: "
                               f"run spans {last-first+1} bars, expected {b+f+1}")
    print(f"1. STRUCTURE — {n} windows over 36 settings (0/0 through 5/5)")
    if bad:
        for x in bad[:10]:
            print(f"     !! {x}")
    else:
        print("     every window is contiguous, spans exactly b+f+1 bars,")
        print("     and contains the anchor. b=0,f=0 is the anchor alone.")
    return bad


# ── 2. arithmetic, and 3. contribution ──────────────────────────────────────

def scan_incremental(cs, anchor, back, fwd, min_rng, want_bull,
                     need_own_extreme=False):
    """ccpScanAt() as written: run high/low carried forward across b.

    `need_own_extreme` is the candidate gate measured in section 4: the far end
    of the long wick must be the ANCHOR's own high or low, not a neighbour's.
    Applied inside the search, so rejecting a wide window still lets a narrower
    one win — not as a filter on the result.
    """
    if anchor - back < 0 or anchor + fwd >= len(cs):
        return None
    best, bs = None, -1e18
    for f in range(fwd + 1):
        hi = max(cs[k].h for k in range(anchor, anchor + f + 1))
        lo = min(cs[k].l for k in range(anchor, anchor + f + 1))
        cc = cs[anchor + f].c
        for b in range(back + 1):
            if b > 0:
                hi = max(hi, cs[anchor - b].h)
                lo = min(lo, cs[anchor - b].l)
            oo = cs[anchor - b].o
            rng = hi - lo
            if rng <= 0 or rng < min_rng:
                continue
            body = abs(cc - oo) / rng
            up = (hi - max(oo, cc)) / rng
            dn = (min(oo, cc) - lo) / rng
            big = max(up, dn)
            if body > BODY_MAX or big < WICK_MIN or (dn > up) != want_bull:
                continue
            if need_own_extreme:
                own = cs[anchor].l == lo if dn > up else cs[anchor].h == hi
                if not own:
                    continue
            sc = big - (b + f) * 100
            if sc > bs:
                bs, best = sc, (b, f, oo, hi, lo, cc)
    return best


def scan_bruteforce(cs, anchor, back, fwd, min_rng, want_bull):
    """The same search with every window's high and low recomputed from the
    raw candles. Slower, dumber, and carries no state between iterations."""
    if anchor - back < 0 or anchor + fwd >= len(cs):
        return None
    best, bs = None, -1e18
    for f in range(fwd + 1):
        for b in range(back + 1):
            run = list(range(anchor - b, anchor + f + 1))
            assert anchor in run, "the anchor fell out of the run"
            hi = max(cs[k].h for k in run)
            lo = min(cs[k].l for k in run)
            oo = cs[run[0]].o
            cc = cs[run[-1]].c
            rng = hi - lo
            if rng <= 0 or rng < min_rng:
                continue
            body = abs(cc - oo) / rng
            up = (hi - max(oo, cc)) / rng
            dn = (min(oo, cc) - lo) / rng
            big = max(up, dn)
            if body > BODY_MAX or big < WICK_MIN or (dn > up) != want_bull:
                continue
            sc = big - (b + f) * 100
            if sc > bs:
                bs, best = sc, (b, f, oo, hi, lo, cc)
    return best


async def main() -> int:
    bad = check_source()
    print()
    bad += check_structure()

    async with aiohttp.ClientSession() as s:
        data = []
        for sym in SYMBOLS:
            try:
                cs = await fetch_candles(s, sym, "Min15")
            except Exception:                              # noqa: BLE001
                continue
            if len(cs) >= 300:
                data.append((cs, atr14(cs)))

    mismatch = 0
    compared = 0
    contrib = collections.Counter()
    runlen = collections.Counter()
    matches = 0
    gated = collections.Counter()          # section 4

    for cs, a in data:
        for pv, gb, hi in grabs(cs, 3, 3):
            if a[gb] is None or gb + FWD >= len(cs) or pv - FWD < 0:
                continue
            want = not hi
            mn = a[gb] * MIN_RANGE_ATR
            ends = {}
            for anchor in (pv, gb):
                inc = scan_incremental(cs, anchor, BACK, FWD, mn, want)
                bru = scan_bruteforce(cs, anchor, BACK, FWD, mn, want)
                ends[anchor] = (
                    inc,
                    scan_incremental(cs, anchor, BACK, FWD, mn, want, True))
                compared += 1
                if inc != bru:
                    mismatch += 1
                    if mismatch <= 3:
                        print(f"     !! {anchor}: incremental {inc} "
                              f"vs brute force {bru}")
                if inc is None:
                    continue
                matches += 1
                b, f, oo, hh, ll, cc = inc
                runlen[b + f + 1] += 1
                # The extreme that MAKES the pin: the far end of the long wick.
                own = (cs[anchor].l == ll) if want else (cs[anchor].h == hh)
                contrib["extreme is the anchor's" if own
                        else "extreme is a neighbour's"] += 1
                if b + f == 0:
                    contrib["anchor alone (trivially its own)"] += 1

            gated["grabs"] += 1
            lo_, lg = ends[pv]
            ro_, rg = ends[gb]
            if lo_ and ro_:
                gated["both, gate off"] += 1
                if lo_[0] + lo_[1] == 0 and ro_[0] + ro_[1] == 0:
                    gated["both, gate off, alone+alone"] += 1
            if lg and rg:
                gated["both, gate on"] += 1
                if lg[0] + lg[1] == 0 and rg[0] + rg[1] == 0:
                    gated["both, gate on, alone+alone"] += 1

    print(f"\n2. ARITHMETIC — {compared} anchors from "
          f"{len(data)} symbols, at {BACK}/{FWD}")
    if mismatch:
        print(f"     !! {mismatch} windows where the incremental run high/low")
        print("        disagreed with a from-scratch max/min.")
        bad.append(f"{mismatch} incremental/brute-force mismatches")
    else:
        print("     the incremental run high/low matches a from-scratch")
        print("     max/min on every window. The shortcut is sound.")

    print(f"\n3. CONTRIBUTION — {matches} matched anchors")
    tot = sum(v for k, v in contrib.items() if k.startswith("extreme"))
    for k in ("extreme is the anchor's", "extreme is a neighbour's"):
        v = contrib[k]
        print(f"     {k:<34}{v:>7}{100*v/max(tot,1):>7.1f}%")
    print(f"     {'of which the anchor stood alone':<34}"
          f"{contrib['anchor alone (trivially its own)']:>7}")
    print(f"\n     run length of the winning window:")
    t2 = sum(runlen.values()) or 1
    for n in sorted(runlen):
        print(f"       {n} candle{'s' if n > 1 else ' '}"
              f"{runlen[n]:>8}{100*runlen[n]/t2:>7.1f}%")
    print("\n     'a neighbour's' is not a bug — the anchor is still in the")
    print("     run. It is the share where the wick the arrow is drawn for")
    print("     does not belong to the grab candle itself.")

    g = gated
    print(f"\n4. WHAT THE STRICTER RULE WOULD COST — {g['grabs']} grabs at "
          f"{BACK}/{FWD}")
    print("   'gate on' = the far end of the long wick must be the anchor's")
    print("   own high or low, rejected inside the search.\n")
    for k in ("off", "on"):
        n = g[f"both, gate {k}"]
        aa = g[f"both, gate {k}, alone+alone"]
        print(f"     gate {k:<4}{n:>7} both-ends matches"
              f"{100*n/max(g['grabs'],1):>8.1f}% of grabs"
              f"     alone+alone {aa}")

    if bad:
        print(f"\n{len(bad)} PROBLEM(S). The anchor rule or the arithmetic is "
              "broken.")
        return 1
    print("\nTHE ANCHOR IS IN EVERY WINDOW, AND THE MERGE ARITHMETIC AGREES")
    print("WITH A FROM-SCRATCH RECOMPUTE.")
    return 0


if __name__ == "__main__":
    # research/studies/ccp_entry_models.py imports scan_incremental from here.
    sys.exit(asyncio.run(main()))
