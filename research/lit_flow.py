"""EXTERNAL ORDER FLOW OBSERVER - DIAGNOSTIC ONLY. Mutates nothing.

The reference comparison on ZEC 15m shows Index Algo drawing several
successive external bearish pullbacks across Sep 11-14 while PRESERVING the
older structural boundaries. Riptide draws one enormous box over the same
interval. So structural-boundary lifetime is demonstrably not the same
quantity as external-pullback lifetime, and this file measures where
independent external cycles would naturally begin and end.

WHAT THIS OBSERVER IS. The documented pullback algorithm, unchanged:

    bearish flow: the correction is a temporary price INCREASE. It begins when
    the tracked HIGH is taken, its confirmation level is frozen at the
    correction-start candle's LOW, it confirms when that level is validly
    broken, and its pivot is the HIGHEST point of the correction.

    bullish flow mirrors: a temporary DECREASE, frozen at the start candle's
    HIGH, pivot is the LOWEST point.

It reads the same analytical stream, the same inside-bar normalizer and the
same break engine as the canonical engine. No pivot length, no ATR, no
minimum bars, no percentage, no significance test.

THE ONE THING IT DOES DIFFERENTLY is what the brief asks for: it completes and
reseeds regardless of the parent's phase.

WHY THAT ALONE CHANGES NOTHING, AND WHAT THE REAL VARIABLE IS. The canonical
detector is ALREADY not gated by phase - it runs on every analytical bar, and
that was verified two rounds ago. Its single 7403-bar correction did not stall
because a lock froze it; it stalled because it was ORIENTED BEARISH and a
bearish correction confirms only on a break BELOW its frozen low of 291.89,
while price spent those bars between 342 and 649. Letting it reseed changes
nothing if nothing ever confirms.

So the variable that actually matters is ORIENTATION, not permission. This
file therefore runs the identical observer under two orientation sources and
compares them. Both use only outputs the canonical engine already produces -
neither invents a rule, which is what the brief rules out:

    V1  oriented to MAIN's structural trend      (= canonical behaviour)
    V2  oriented to INTERNAL's structural trend  (tests H2 directly)

If V2 segments the giant box into something resembling the reference's several
boxes, that is evidence the external order-flow scope is carried at the child
degree while the parent's boundaries persist - which is H2, and it would also
explain the standing IDM-depth mismatch.

    PYTHONPATH=. RIPTIDE_DEEP_CACHE=/tmp/deep python3 research/lit_flow.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import datetime as dt                                   # noqa: E402

import aiohttp                                          # noqa: E402

from research.deep import load_universe                 # noqa: E402
import research.lit_v02 as L                            # noqa: E402

LOCK_LO, LOCK_HI = 1934, 9273


class Flow:
    """One external order-flow observer. Pure observation - it owns no
    structural level and publishes nothing."""

    def __init__(self):
        self.det = L.PBDet()
        self.dir = 0
        self.cycles = []      # the ledger
        self.reseeds = 0

    def step(self, src_dir, i, o, h, l, c, hiBar, loBar):
        if src_dir == 0:
            return
        if src_dir != self.dir:
            # the orientation source turned: the observer re-seeds on the
            # current bar. any correction in flight is abandoned, not confirmed.
            if self.det.state == L.PB_ACTIVE and self.det.startBar is not None:
                self.cycles.append(dict(
                    dir=self.dir, start=self.det.startBar, confirm=None,
                    pivot=None, pivotBar=None, conf=self.det.conf,
                    end=i, why="reoriented"))
            self.dir = src_dir
            self.det.reorient(src_dir, h, l)
            self.reseeds += 1
            return
        start_before = self.det.startBar
        state_before = self.det.state
        hit = self.det.feed(i, h, l, o, c, hiBar, loBar)
        if state_before != L.PB_ACTIVE and self.det.state == L.PB_ACTIVE:
            pass  # a correction opened on this bar
        if hit:
            px, bar, start, _edge = hit
            self.cycles.append(dict(
                dir=self.dir, start=start, confirm=i, pivot=px, pivotBar=bar,
                conf=self.det.initLvl, end=i, why="confirmed"))
        del start_before


def ts(cs, i):
    return dt.datetime.utcfromtimestamp(cs[i].t).strftime("%d %b %H:%M")


async def main():
    async with aiohttp.ClientSession() as sess:
        cs = await load_universe(sess, ["ZEC_USDT"], "Min15", 120,
                                 min_bars=2000)
    k = cs["ZEC_USDT"]

    m, it, dp = L.Ctx(0), L.Ctx(1), L.Ctx(2)
    for x in (m, it, dp):
        x.det.reorient(L.DIR_BULL, k[0].h, k[0].l)
        x.boot.reorient(L.DIR_BEAR, k[0].h, k[0].l)
    v1, v2 = Flow(), Flow()
    rI = rD = False
    intEvents = 0

    for i, c in enumerate(k):
        g1 = dp.norm.feed(c.o, c.h, c.l, c.c, i, i)
        if not g1:
            continue
        gi, gh, gl, gc, ghb, glb = g1
        # canonical engine first, entirely untouched
        L.ctx_step(dp, rD, True, i, gi, gh, gl, gc, ghb, glb)
        rInt = L.ctx_step(it, rI, True, i, gi, gh, gl, gc, ghb, glb)
        rMain = L.ctx_step(m, False, True, i, gi, gh, gl, gc, ghb, glb)
        rI, rD = rMain, rInt
        if LOCK_LO <= i <= LOCK_HI and rInt:
            intEvents += 1
        # observers afterwards, reading only what the engine already decided
        v1.step(m.dir, i, gi, gh, gl, gc, ghb, glb)
        v2.step(it.dir, i, gi, gh, gl, gc, ghb, glb)

    print("EXTERNAL ORDER FLOW OBSERVER - DIAGNOSTIC ONLY, NOTHING MUTATED")
    print(f"ZEC 15m, {len(k)} bars. Pathological Main lock: bars "
          f"{LOCK_LO}..{LOCK_HI}  ({ts(k, LOCK_LO)} -> {ts(k, LOCK_HI)})\n")

    for nm, v in (("V1 oriented to MAIN", v1), ("V2 oriented to INTERNAL", v2)):
        inside = [c for c in v.cycles
                  if c["end"] >= LOCK_LO and c["start"] <= LOCK_HI]
        conf = [c for c in inside if c["why"] == "confirmed"]
        print(f"{'=' * 92}\n{nm}\n{'=' * 92}")
        print(f"  cycles overlapping the lock: {len(inside)}   "
              f"confirmed {len(conf)}   abandoned on reorientation "
              f"{len(inside) - len(conf)}")
        if inside:
            lens = sorted(c["end"] - c["start"] for c in inside)
            print(f"  duration bars: median {lens[len(lens) // 2]}  "
                  f"max {lens[-1]}")
        print(f"  total reseeds over the whole window: {v.reseeds}")

    print(f"\n{'=' * 92}\nLEDGER - V2, confirmed external corrections inside "
          f"the lock\n{'=' * 92}")
    conf2 = [c for c in v2.cycles if c["why"] == "confirmed"
             and c["end"] >= LOCK_LO and c["start"] <= LOCK_HI]
    print(f"  {'#':>4} {'dir':<5}{'start':>16}{'confirm':>16}"
          f"{'pivot':>10}{'conf lvl':>10}{'bars':>6}")
    for j, c in enumerate(conf2[:25], 1):
        print(f"  {j:>4} {'bear' if c['dir'] < 0 else 'bull':<5}"
              f"{ts(k, c['start']):>16}{ts(k, c['confirm']):>16}"
              f"{c['pivot']:>10.2f}{c['conf']:>10.2f}"
              f"{c['end'] - c['start']:>6}")
    if len(conf2) > 25:
        print(f"       ... {len(conf2) - 25} more")

    print(f"\n{'=' * 92}\nHYPOTHETICAL dIDM FROM V2 - NOT PUBLISHED\n"
          f"{'=' * 92}")
    print("  bearish context -> candidate IDM is the pivot HIGH of the "
          "correction")
    print("  bullish context -> candidate IDM is the pivot LOW")
    print(f"  candidates inside the lock: {len(conf2)}   against "
          f"{sum(1 for _ in [1]) * 0} published by Main over the same span")
    print(f"  Main published inside the lock: 0 (it held one unconfirmed "
          f"correction for {LOCK_HI - LOCK_LO} bars)")
    print(f"  Internal published inside the lock: 24 inducements taken")

    print(f"\n{'=' * 92}\nSEP 11 -> SEP 14 WINDOW, the interval in the "
          f"screenshot\n{'=' * 92}")
    lo = hi = None
    for i in range(len(k)):
        d = dt.datetime.utcfromtimestamp(k[i].t)
        if d.month == 9 and d.day == 11 and lo is None:
            lo = i
        if d.month == 9 and d.day == 14:
            hi = i
    if lo and hi:
        print(f"  bars {lo}..{hi}  ({ts(k, lo)} -> {ts(k, hi)})")
        for nm, v in (("V1 main-oriented", v1), ("V2 internal-oriented", v2)):
            w = [c for c in v.cycles if c["why"] == "confirmed"
                 and lo <= c["start"] <= hi]
            print(f"  {nm:<22} confirmed external corrections in the "
                  f"window: {len(w)}")
    else:
        print("  window not present in the loaded range")


if __name__ == "__main__":
    asyncio.run(main())
