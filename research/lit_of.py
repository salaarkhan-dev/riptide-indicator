"""MainOrderFlowState - EXPERIMENTAL, measured before any Pine is written.

The architecture is agreed: MainStructureState owns BOS/CHoCH, MainOrderFlowState
owns the external pullback, its pivot and the IDM, and boundary lock gates IDM
PUBLICATION only - never the flow itself.

THE ONE THING THE BRIEF DOES NOT SETTLE IS WHAT ORIENTS THE FLOW, and that is
the whole experiment. §8 forbids inventing a new trigger and allows exactly two
readings of the minimum model:

  OF-A  the flow keeps the structural direction, and only the CYCLE is
        decoupled - impulse, correction, confirm, pivot, IDM, reseed, all of it
        running underneath a locked structure.

  OF-B  OF-1 taken literally: "completion of an opposite-direction valid
        pullback" re-orients the flow. Both orientations are tracked and
        whichever confirms first sets the direction.

Everything else is held identical: the same analytical stream, the same
normalizer, the same break engine, the documented two-level tracker, the frozen
confirmation level, pivot = the extreme of the whole correction. No pivot
length, no ATR, no minimum bars, no percentage, no significance test.

§20 IS THE GATE AND IT CUTS BOTH WAYS. One giant pullback is a reject. Hundreds
of two-bar pullbacks are equally a reject. The reference shows a middle
structural scale - roughly eight external corrections across six days - and
this file exists to find out whether either minimum model lands there.

    PYTHONPATH=. RIPTIDE_DEEP_CACHE=/tmp/deep python3 research/lit_of.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import datetime as dt                                   # noqa: E402

import aiohttp                                          # noqa: E402

from research.deep import load_universe                 # noqa: E402
import research.lit_v02 as L                            # noqa: E402


class OrderFlow:
    """Owns flow direction, the impulse tracker, the live external pullback,
    its pivot and the IDM. Owns no structural level and can mutate none.

    OF-INV-1/2 hold by construction: this class has no reference to a Ctx.
    """

    def __init__(self, mode):
        self.mode = mode          # "A" or "B"
        self.dir = 0
        self.det = L.PBDet()
        self.alt = L.PBDet()      # OF-B only: the opposite orientation
        self.cycle = 0
        self.pbs = []             # confirmed external pullbacks, immutable
        self.idmPx = None
        self.idmBar = None
        self.idmOn = False
        self.nCreate = 0
        self.nMove = 0
        self.nTaken = 0
        self.flips = 0
        self.openFrom = None
        self.idmBrk = L.Brk()

    def _seed(self, d, h, l):
        self.dir = d
        self.det.reorient(d, h, l)
        self.alt.reorient(-d, h, l)

    def _confirm(self, hit, i, phaseAllows):
        """A correction completed. Freeze it, take its pivot, publish or cache
        the IDM. OF-INV-4: the record is appended and never touched again."""
        px, bar, start, _edge = hit
        self.cycle += 1
        self.pbs.append(dict(id=self.cycle, dir=self.dir, start=start,
                             confirm=i, pivot=px, pivotBar=bar))
        # OF-INV-3: every IDM originates from a confirmed external PB pivot.
        if phaseAllows:
            if self.idmOn:
                self.nMove += 1
            else:
                self.nCreate += 1
            self.idmPx, self.idmBar, self.idmOn = px, bar, i
            L.arm(self.idmBrk, px, -1 if self.dir > 0 else 1, L.M_IDM,
                  L.HS_IDM)

    def step(self, structDir, phaseAllows, i, o, h, l, c, hiBar, loBar):
        if self.dir == 0:
            if structDir == 0:
                return
            self._seed(structDir, h, l)
            return
        if self.mode == "A" and structDir != 0 and structDir != self.dir:
            # OF-A: the flow carries the structural direction, so a structural
            # flip re-seeds it. Nothing else does.
            self._seed(structDir, h, l)
            self.flips += 1
            return

        hit = self.det.feed(i, h, l, o, c, hiBar, loBar)
        if hit:
            self._confirm(hit, i, phaseAllows)
        if self.mode == "B":
            # OF-1 literally: an opposite-direction correction completing turns
            # the flow. Track it concurrently and hand over when it confirms.
            other = self.alt.feed(i, h, l, o, c, hiBar, loBar)
            if other and not hit:
                self.dir = -self.dir
                self.flips += 1
                self._confirm(other, i, phaseAllows)
                self.det.reorient(self.dir, h, l)
                self.alt.reorient(-self.dir, h, l)

        # the inducement is taken on its own break - structure never does it
        if self.idmOn and i > self.idmOn:
            if L.brk_step(self.idmBrk, o, h, l, c):
                self.idmOn = False
                self.nTaken += 1
                L.disarm(self.idmBrk)


def pctl(v, p):
    return sorted(v)[int(p * (len(v) - 1))] if v else 0


async def main():
    async with aiohttp.ClientSession() as sess:
        cs = await load_universe(sess, ["ZEC_USDT"], "Min15", 120,
                                 min_bars=2000)
    k = cs["ZEC_USDT"]
    f = lambda i: dt.datetime.utcfromtimestamp(k[i].t).strftime("%d %b %H:%M")
    win = [i for i in range(len(k))
           if dt.datetime.utcfromtimestamp(k[i].t).month == 9
           and dt.datetime.utcfromtimestamp(k[i].t).day >= 8]
    LO, HI = win[0], win[-1]

    m, it, dp = L.Ctx(0), L.Ctx(1), L.Ctx(2)
    for x in (m, it, dp):
        x.det.reorient(L.DIR_BULL, k[0].h, k[0].l)
        x.boot.reorient(L.DIR_BEAR, k[0].h, k[0].l)
    ofA, ofB = OrderFlow("A"), OrderFlow("B")
    rI = rD = False
    ctlPb = []
    pbStart = None
    prevSt = L.PB_IMPULSE

    for i, c in enumerate(k):
        g1 = dp.norm.feed(c.o, c.h, c.l, c.c, i, i)
        if not g1:
            continue
        gi, gh, gl, gc, ghb, glb = g1
        # canonical engine, untouched - OF-INV-7 holds because nothing below
        # writes back into it
        L.ctx_step(dp, rD, True, i, gi, gh, gl, gc, ghb, glb)
        rInt = L.ctx_step(it, rI, True, i, gi, gh, gl, gc, ghb, glb)
        rMain = L.ctx_step(m, False, True, i, gi, gh, gl, gc, ghb, glb)
        rI, rD = rMain, rInt
        if m.det.state == L.PB_ACTIVE and prevSt != L.PB_ACTIVE:
            pbStart = m.det.startBar
        if m.det.state != L.PB_ACTIVE and prevSt == L.PB_ACTIVE and pbStart:
            ctlPb.append((pbStart, i))
            pbStart = None
        prevSt = m.det.state
        # OF-INV-5: boundary lock gates PUBLICATION, never the flow
        allows = m.phase in (L.PH_DISCOVER, L.PH_TRACK)
        ofA.step(m.dir, allows, i, gi, gh, gl, gc, ghb, glb)
        ofB.step(m.dir, allows, i, gi, gh, gl, gc, ghb, glb)

    print("MainOrderFlowState - EXPERIMENTAL, ZEC 15m")
    print(f"fixture window {f(LO)} .. {f(HI)}   bars {LO}..{HI}\n")

    ctlWin = [p for p in ctlPb if p[1] >= LO]
    openTail = len(k) - 1 - pbStart if pbStart else 0
    print(f"{'=' * 92}\nCONTROL - canonical Main\n{'=' * 92}")
    print(f"  external PB confirmed in window : {len(ctlWin)}")
    print(f"  IDM published / taken (all data): "
          f"{m.ev['idm_create'] + m.ev['idm_move']} / {m.ev['idm_break']}")
    print(f"  open PB still running at the right edge: {openTail} bars")

    for nm, of in (("OF-A  flow carries structural direction", ofA),
                   ("OF-B  opposite confirmation re-orients (OF-1 literal)",
                    ofB)):
        w = [p for p in of.pbs if p["confirm"] >= LO]
        durs = [p["confirm"] - p["start"] for p in of.pbs]
        wd = [p["confirm"] - p["start"] for p in w]
        print(f"\n{'=' * 92}\n{nm}\n{'=' * 92}")
        print(f"  external PB confirmed  in window {len(w):>5}   "
              f"whole data {len(of.pbs):>6}")
        print(f"  per 2000 bars          {len(of.pbs) * 2000 / len(k):>8.1f}")
        print(f"  IDM create {of.nCreate}  migrate {of.nMove}  "
              f"taken {of.nTaken}   flow direction changes {of.flips}")
        if durs:
            print(f"  PB duration  median {pctl(durs, .5):>4}  "
                  f"p90 {pctl(durs, .9):>5}  p95 {pctl(durs, .95):>5}  "
                  f"p99 {pctl(durs, .99):>6}  max {max(durs):>6}")
        if wd:
            print(f"  in-window    median {pctl(wd, .5):>4}  max {max(wd):>5}")
        print(f"  the reference shows roughly 8 external corrections across "
              f"this window.")
        # §16 longest silent interval - the metric that actually decides,
        # because the defect is a 255-bar stretch with NO external correction,
        # not a wrong total count.
        marks = sorted(p["confirm"] for p in of.pbs)
        gaps = [(b - a, a, b) for a, b in zip(marks, marks[1:])]
        tail = len(k) - 1 - (marks[-1] if marks else 0)
        worst = max(gaps)[0] if gaps else 0
        wg = max([g for g in gaps if g[2] >= LO], default=(0, 0, 0))
        print(f"  longest silent interval: {worst} bars (whole data)   "
              f"in-window {wg[0]} bars"
              + (f" from {f(wg[1])} to {f(wg[2])}" if wg[0] else ""))
        print(f"  silent tail to the right edge: {tail} bars")
        covers = wg[0] < 150 and tail < 150
        verdict = ("REJECT - collapses to one giant correction"
                   if len(w) <= 2 else
                   "REJECT - raw swing noise, not a structural scale"
                   if len(of.pbs) * 2000 / len(k) > 45 else
                   "REJECT - leaves the problem region silent"
                   if not covers else
                   "IN THE REFERENCE RANGE - worth building in Pine")
        print(f"  §20 GATE: {verdict}")
        if w:
            print(f"  first 10 in window:")
            for p in w[:10]:
                print(f"    #{p['id']:<5}{'bear' if p['dir'] < 0 else 'bull'}"
                      f"  {f(p['start']):>14} -> {f(p['confirm']):<14}"
                      f"  pivot {p['pivot']:>8.2f}  "
                      f"{p['confirm'] - p['start']:>4} bars")


if __name__ == "__main__":
    asyncio.run(main())
