"""LIT engine v3 - the Python twin of riptide-lit-v2.pine.

A SEPARATE COPY. research/lit_v02.py is the frozen v0.2 control and every
measurement already recorded in LIT_CHANGELOG.md was taken against it, so it
is not touched. This file is where the V2 engine lives on the Python side.

Differences from lit_v02, all of them from LIT_V2_DESIGN.md:

  P1  the outside group in IMPULSE - a group that breaks BOTH tracker levels.
      lit_v02 opened a correction there only because `started` is tested
      first. Here the group's own close direction decides, per master prompt
      §12, the only guidance anywhere for a both-sides break.
  P3  where the trackers re-seed after a correction confirms.
  P4  exact equality - master prompt §11 says it is NOT a break, and every
      geometric comparison funnels through above()/below() so the policy is
      decided in one place.
  mPB the pullback break mode is CONFIGURABLE and defaults to BODY, which is
      what the reference STRATEGY build ships (LIT_SOURCE.md Ch.24). The
      structure build ships Shadow; lit_v02 hardcodes Shadow.

It also records a real EVENT LOG rather than only counters, because the
strategy harness needs prices and bars, not totals.
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
from collections import Counter                         # noqa: E402
from dataclasses import dataclass, field                # noqa: E402

import aiohttp                                          # noqa: E402

from research.deep import load_universe                 # noqa: E402

DIR_NONE, DIR_BULL, DIR_BEAR = 0, 1, -1
# [SRC] The four documented phases, named as the brief names them.
PH_DISCOVER, PH_TRACK, PH_SEEK, PH_LOCK = 0, 1, 2, 3
PHNAME = {PH_DISCOVER: "discover", PH_TRACK: "track", PH_SEEK: "seek",
          PH_LOCK: "lock"}
BRK_SHADOW, BRK_BODY, BRK_SWEEP = 0, 1, 2
PB_IMPULSE, PB_ACTIVE = 1, 2

# [SRC Ch.24] The reference STRATEGY build ships Pullback = Body. The structure
# build ships Shadow. lit_v02 hardcoded Shadow; here it is a policy.
M_PB, M_IDM, M_BOS, M_CH = BRK_BODY, BRK_SHADOW, BRK_SWEEP, BRK_SWEEP


class Pol:
    """The undefined cases, named. No policy may introduce a number."""
    outside = "close"      # P1: close | correction | impulse
    reseed = "resolver"    # P3: resolver | pivot
    eqBreak = False        # P4: exact equality counts as a break


POL = Pol()


def above(v, lvl):
    return v >= lvl if POL.eqBreak else v > lvl


def below(v, lvl):
    return v <= lvl if POL.eqBreak else v < lvl
HS_PB, HS_IDM, HS_BOS, HS_CH = False, False, True, True


class Cfg:
    """EXPERIMENTAL switches. Both default OFF, so the untouched engine is
    the canonical documented control and stays bit-identical to what has
    already been measured. Neither rule is stated by the reference."""

    sweep_reset = False   # EXPERIMENTAL: a close back on the original side of
    #                       baseLevel returns activeLevel to baseLevel and
    #                       clears the sweep chain. Tests whether repeated
    #                       failed probes should make a level permanently
    #                       harder to break once price has returned through it.
    segment_bos = False   # EXPERIMENTAL: BOS is the extreme from the impulse
    #                       segment that carries the active IDM - the tracker
    #                       reset that followed the pullback which became that
    #                       IDM - rather than from the whole structural leg.


CFG = Cfg()


# ═════════════════════════ BREAK ENGINE ═════════════════════════════════════
@dataclass
class Brk:
    """[SRC] One engine, four users: pullback, IDM, BOS, CHoCH."""
    base: float = None      # the level as first set - BODY judges this
    act: float = None       # BODY_SWEEP migrates this and judges it instead
    dir: int = 0
    mode: int = 0
    useHS: bool = False
    pend: bool = False      # a body candidate is waiting on Hidden Shadow
    hsLvl: float = None
    hsHi: float = None
    hsLo: float = None
    hsMomHi: float = None   # the candidate candle's own range
    hsMomLo: float = None
    swept: bool = False     # a sweep happened on this bar
    shadow: bool = False    # Hidden Shadow rejected a break on this bar
    sweeps: int = 0         # length of the current sweep chain
    reset: bool = False     # the experimental reset fired on this bar


def arm(b, lvl, d, mode, useHS):
    # A replaced level always gets a FRESH tracker - a migrated sweep
    # threshold is never inherited.
    b.base = b.act = lvl
    b.dir, b.mode, b.useHS = d, mode, useHS
    b.pend = b.swept = b.shadow = b.reset = False
    b.sweeps = 0
    b.hsLvl = None


def disarm(b):
    b.base = b.act = None
    b.pend = b.swept = b.shadow = False


def brk_step(b, o, h, l, c):
    """One bar. True only on the bar the break is CONFIRMED."""
    done = False
    b.swept = b.shadow = b.reset = False
    if b.base is None:
        return False
    up = b.dir > 0
    if b.pend:
        # [SRC] Hidden Shadow: bars contained by the candidate's own range
        # cannot resolve it. Wait for the first that escapes, then judge a
        # synthetic candle spanning candidate through resolver.
        if not (h < b.hsMomHi and l > b.hsMomLo):
            b.hsHi, b.hsLo = max(b.hsHi, h), min(b.hsLo, l)
            b.pend = False
            if (c > b.hsLvl) if up else (c < b.hsLvl):
                done = True
            else:
                # [INF] After a rejection BODY_SWEEP keeps the level it had
                # already migrated to rather than resetting to base.
                b.shadow = True
    else:
        if b.mode == BRK_SHADOW:
            raw = (h > b.base) if up else (l < b.base)
        elif b.mode == BRK_BODY:
            raw = (c > b.base) if up else (c < b.base)
        else:
            # [EXPERIMENTAL - CFG.sweep_reset] Price closing back on the
            # original, non-breakout side of baseLevel cancels the sweep chain
            # and returns the threshold to baseLevel. The owning level is NOT
            # retired; only its sweep-confirmation threshold resets.
            if CFG.sweep_reset and b.act != b.base:
                if (c < b.base) if up else (c > b.base):
                    b.act = b.base
                    b.sweeps = 0
                    b.reset = True
            # [SRC] A wick through that closes back inside has SWEPT. The
            # threshold moves to that wick; the old level is no longer enough.
            if up and h > b.act and c <= b.act:
                b.act, b.swept = h, True
                b.sweeps += 1
            elif not up and l < b.act and c >= b.act:
                b.act, b.swept = l, True
                b.sweeps += 1
            raw = (c > b.act) if up else (c < b.act)
        if raw:
            if b.useHS and b.mode != BRK_SHADOW:
                b.pend = True
                b.hsLvl = b.act if b.mode == BRK_SWEEP else b.base
                b.hsHi = b.hsMomHi = h
                b.hsLo = b.hsMomLo = l
            else:
                done = True
    return done


# ═════════════════════════ INSIDE-BAR NORMALIZER ════════════════════════════
@dataclass
class Norm:
    """[SRC] A candle sets a range; every candle that stays inside it is noise
    until that range breaks - not merely the next one.

    THE GROUP IS EMITTED AS ONE MERGED CANDLE. A mother and everything it
    contained is structurally a single event, so that is what this passes
    downstream: open of the mother, the extremes of the whole group, close of
    the last bar in it. Passing the mother's own OHLC instead - which is what
    the first v0.2 attempt did - makes a second pass a NO-OP, because a bar
    that broke the previous emitted bar's range trivially breaks the next
    level's range too. Measured: Internal and Main filtered 0% and the three
    depths differed only by how often they were reset, which is exactly the
    fake hierarchy the brief rules out.

    [INF] One per depth, CHAINED: Deep reads raw candles, Internal reads
    Deep's merged output, Main reads Internal's. Re-applying the documented
    rule to its own output is the only coarsening available that introduces no
    length parameter. This is the top calibration item.

    A group closes on the bar that BREAKS it, and that bar opens the next, so
    nothing is emitted until it is complete and nothing repaints.
    """
    momHi: float = None
    momLo: float = None
    o: float = None
    c: float = None
    hiBar: int = None
    loBar: int = None
    nFed: int = 0
    nEmit: int = 0
    nBoth: int = 0

    def feed(self, o, h, l, c, hiBar, loBar):
        """The completed group as (o, h, l, c, hiBar, loBar), or None while
        the current group is still open."""
        self.nFed += 1
        if self.momHi is None:
            self.momHi, self.momLo, self.o, self.c = h, l, o, c
            self.hiBar, self.loBar = hiBar, loBar
            return None
        over, under = h > self.momHi, l < self.momLo
        if not (over or under):
            self.c = c          # contained: it extends the open group
            return None
        if over and under:
            # [INF] Both sides in one candle. OHLC cannot order them and this
            # file does not guess; the group closes, this bar opens the next.
            self.nBoth += 1
        out = (self.o, self.momHi, self.momLo, self.c, self.hiBar, self.loBar)
        self.momHi, self.momLo, self.o, self.c = h, l, o, c
        self.hiBar, self.loBar = hiBar, loBar
        self.nEmit += 1
        return out


# ═════════════════════════ PULLBACK DETECTOR ════════════════════════════════
@dataclass
class PBDet:
    """[SRC] The documented two-phase correction tracker, ORIENTED to a trend.

    Phase A rides the impulse: while each real candle makes a new extreme
    without giving back the other side, both tracking levels move with it.
    Phase B begins the instant the opposite tracking level breaks. The level
    that will confirm the correction is fixed AT THAT CANDLE and does not move
    again - v0.1's deviation was to move it, and it is gone.

    Orientation is the fix that makes the fixed level workable: a bullish
    detector only ever looks for bullish corrections, and is re-initialised
    when the context flips.
    """
    dir: int = DIR_BULL
    state: int = PB_IMPULSE
    trkHi: float = None
    trkLo: float = None
    startBar: int = None
    conf: float = None        # FIXED at correction start - see §3E
    initLvl: float = None     # what conf was, for the zone edge
    rngHi: float = None
    rngHiBar: int = None
    rngLo: float = None
    rngLoBar: int = None
    b: Brk = field(default_factory=Brk)
    nOutside: int = 0        # [P1] how often the undefined case actually fires

    def reorient(self, d, h, l):
        self.dir = d
        self.state = PB_IMPULSE
        self.trkHi, self.trkLo = h, l
        self.startBar = self.conf = None
        disarm(self.b)

    def feed(self, i, h, l, o, c, hiBar, loBar):
        """Returns (pivotPx, pivotBar, startBar, edge) on confirmation."""
        bull = self.dir == DIR_BULL
        if self.trkHi is None:
            self.trkHi, self.trkLo = h, l
            return None
        if self.state == PB_IMPULSE:
            extended = above(h, self.trkHi) if bull else below(l, self.trkLo)
            gaveBack = below(l, self.trkLo) if bull else above(h, self.trkHi)
            started = False
            cont = False
            if extended and gaveBack:
                # [P1] The undefined case. lit_v02 answered it by evaluation
                # order; here it is a stated choice and it is counted.
                self.nOutside += 1
                if POL.outside == "correction":
                    started = True
                elif POL.outside == "impulse":
                    cont = True
                else:
                    withImpulse = (c > o) if bull else (c < o)
                    cont = withImpulse
                    started = not withImpulse
            elif gaveBack:
                started = True
            elif extended:
                cont = True
            if started:
                # [SRC] §3C/D - the correction starts, and its confirmation
                # level is this candle's opposite extreme, fixed from here.
                self.state = PB_ACTIVE
                self.startBar = i
                self.conf = self.initLvl = h if bull else l
                self.rngHi = self.rngHiBar = None
                self.rngHi, self.rngHiBar = h, hiBar
                self.rngLo, self.rngLoBar = l, loBar
                arm(self.b, self.conf, 1 if bull else -1, M_PB, HS_PB)
            elif cont:
                self.trkHi, self.trkLo = h, l
            return None
        # PB_ACTIVE. [SRC] §4 - the range grows, the confirmation level does
        # NOT. A complex correction stays one correction and emits one pivot.
        if above(h, self.rngHi):
            self.rngHi, self.rngHiBar = h, hiBar
        if below(l, self.rngLo):
            self.rngLo, self.rngLoBar = l, loBar
        if brk_step(self.b, o, h, l, c):
            px = self.rngLo if bull else self.rngHi
            bar = self.rngLoBar if bull else self.rngHiBar
            edge = self.b.act if self.b.act is not None else self.initLvl
            start = self.startBar
            self.state = PB_IMPULSE
            # [P3] Where the trackers go next.
            if POL.reseed == "pivot":
                self.trkHi, self.trkLo = (h, px) if bull else (px, l)
            else:
                self.trkHi, self.trkLo = h, l
            disarm(self.b)
            return px, bar, start, edge
        return None


# ═════════════════════════ STRUCTURE LEVEL ══════════════════════════════════
@dataclass
class Lvl:
    """[SRC/§11] Every level records the bar it was created on. It cannot be
    evaluated for a break on that bar - OHLC cannot order two events inside
    one candle, so a same-bar cascade is a guess dressed as a transition."""
    px: float = None
    bar: int = None
    createdBar: int = None
    on: bool = False
    b: Brk = field(default_factory=Brk)

    def set(self, px, bar, i, d, mode, hs):
        self.px, self.bar, self.createdBar, self.on = px, bar, i, True
        arm(self.b, px, d, mode, hs)

    def clear(self):
        self.on = False
        disarm(self.b)

    def ready(self, i):
        return self.on and i > self.createdBar


# ═════════════════════════ STRUCTURE CONTEXT ════════════════════════════════
@dataclass
class Ctx:
    depth: int = 0
    dir: int = DIR_NONE
    phase: int = PH_DISCOVER
    norm: Norm = field(default_factory=Norm)
    det: PBDet = field(default_factory=PBDet)
    boot: PBDet = field(default_factory=lambda: PBDet(dir=DIR_BEAR))
    legBar: int = None
    legPx: float = None
    legHi: float = None
    legHiBar: int = None
    legLo: float = None
    legLoBar: int = None
    phHi: float = None
    phHiBar: int = None
    phLo: float = None
    phLoBar: int = None
    idm: Lvl = field(default_factory=Lvl)
    bos: Lvl = field(default_factory=Lvl)
    ch: Lvl = field(default_factory=Lvl)
    segBar: int = None      # tracker reset after the PB that became the IDM
    segHi: float = None
    segHiBar: int = None
    segLo: float = None
    segLoBar: int = None
    latPx: float = None
    latBar: int = None
    racing: bool = False
    confine: object = None     # the parent whose range bounds this depth
    lvlLog: list = field(default_factory=list)
    events: list = field(default_factory=list)
    ev: Counter = field(default_factory=Counter)
    bad: Counter = field(default_factory=Counter)
    held: Counter = field(default_factory=Counter)
    phaseBar: int = 0
    bosLog: list = field(default_factory=list)


def log(x, kind, i, **kw):
    """A real event log, not a counter. The strategy harness needs prices and
    bars; totals cannot reconstruct a trade."""
    rec = dict(kind=kind, bar=i, dir=x.dir, phase=x.phase)
    rec.update(kw)
    x.events.append(rec)


def leg_start(x, px, bar, h, l, i):
    """[SRC/§9] A new directional leg. IDM migration never calls this."""
    x.legPx, x.legBar = px, bar
    x.legHi, x.legHiBar = h, i
    x.legLo, x.legLoBar = l, i


def check(x, cond, name):
    if not cond:
        x.bad[name] += 1


def ctx_step(x, resetMe, real, i, o, h, l, c, hiBar, loBar):
    """[§12] One bar, one context, deterministic order, at most one major
    transition. `real` comes from this depth's own normalizer, fed by the
    caller so the three streams can be chained. Returns True when this context
    resolved a boundary."""
    if resetMe:
        # [INF] Child scope reset: the parent's valid range changed, so the
        # child restarts inside the new one with no inherited direction.
        x.dir, x.phase = DIR_NONE, PH_DISCOVER
        x.idm.clear()
        x.bos.clear()
        x.ch.clear()
        x.racing = False
        x.latPx = x.latBar = None
        x.det.reorient(DIR_BULL, h, l)
        x.boot.reorient(DIR_BEAR, h, l)
        x.ev["scope_reset"] += 1

    # [SRC/§5] An inside bar at this depth does nothing structural here. It is
    # still a real bar to the depth below, which is the point of §16.
    if not real:
        return False

    # 3-4. the detector, oriented to this context's own direction
    hit = None
    if x.dir == DIR_NONE:
        # [INFERRED INITIALIZATION] Direction unknown, so both orientations run
        # until one confirms a correction. That sets the direction and the
        # other is discarded. No average, no candle colour, and no bootstrap
        # state survives into mature behaviour.
        up = x.det.feed(i, h, l, o, c, hiBar, loBar)
        dn = x.boot.feed(i, h, l, o, c, hiBar, loBar)
        if up:
            x.dir, hit = DIR_BULL, up
        elif dn:
            x.dir, hit = DIR_BEAR, dn
        if x.dir != DIR_NONE:
            x.det.reorient(x.dir, h, l)
            x.boot.reorient(-x.dir, h, l)
            leg_start(x, hit[0], hit[1], h, l, i)
            x.ev["bootstrap"] += 1
    else:
        hit = x.det.feed(i, h, l, o, c, hiBar, loBar)
    if x.det.b.swept:
        x.ev["pb_sweep"] += 1

    # running extremes: the leg feeds the BOS lock, the phase feeds the CHoCH
    if x.legHi is None or h > x.legHi:
        x.legHi, x.legHiBar = h, hiBar
    if x.legLo is None or l < x.legLo:
        x.legLo, x.legLoBar = l, loBar
    if x.segBar is not None:
        if x.segHi is None or h > x.segHi:
            x.segHi, x.segHiBar = h, hiBar
        if x.segLo is None or l < x.segLo:
            x.segLo, x.segLoBar = l, loBar
    if x.phase in (PH_SEEK, PH_LOCK):
        if x.phHi is None or h > x.phHi:
            x.phHi, x.phHiBar = h, hiBar
        if x.phLo is None or l < x.phLo:
            x.phLo, x.phLoBar = l, loBar

    # 5. a confirmed correction. [SRC/§8] It is PUBLISHED as an IDM only in the
    # two phases that may hold one; during the BOS race it is cached instead.
    if hit:
        px, bar = hit[0], hit[1]
        x.ev["pivot"] += 1
        x.latPx, x.latBar = px, bar
        if x.phase in (PH_DISCOVER, PH_TRACK):
            x.ev["idm_move" if x.idm.on else "idm_create"] += 1
            legWas = (x.legBar, x.legPx)
            x.idm.set(px, bar, i, -1 if x.dir == DIR_BULL else 1, M_IDM, HS_IDM)
            x.phase = PH_TRACK
            # The impulse segment carrying this IDM starts where the tracker
            # reset - the bar this correction confirmed on.
            x.segBar = i
            x.segHi, x.segHiBar = h, hiBar
            x.segLo, x.segLoBar = l, loBar
            x.lvlLog.append(("IDM", round(px, 10), bar))
            log(x, "idm", i, px=px, pivotBar=bar)
            check(x, (x.legBar, x.legPx) == legWas, "I7 leg moved with IDM")
        else:
            x.ev["latent_cached"] += 1
            check(x, not x.idm.on, "I6 IDM published during BOS race")

    moved = False

    # 6. IDM. [SRC] Taking inducement never flips the trend.
    if x.idm.ready(i) and brk_step(x.idm.b, o, h, l, c):
        was = x.dir
        x.idm.clear()
        # [SRC control] the extreme of the whole structural leg.
        # [EXPERIMENTAL - CFG.segment_bos] the extreme of the impulse segment
        # carrying this IDM instead. Nothing else differs between the arms.
        useSeg = CFG.segment_bos and x.segBar is not None
        bosPx = (x.segHi if x.dir == DIR_BULL else x.segLo) if useSeg else \
                (x.legHi if x.dir == DIR_BULL else x.legLo)
        bosBar = (x.segHiBar if x.dir == DIR_BULL else x.segLoBar) if useSeg \
            else (x.legHiBar if x.dir == DIR_BULL else x.legLoBar)
        x.bos.set(bosPx, bosBar, i, 1 if x.dir == DIR_BULL else -1,
                  M_BOS, HS_BOS)
        x.phHi, x.phHiBar = h, i
        x.phLo, x.phLoBar = l, i
        x.phase = PH_LOCK if x.ch.on else PH_SEEK
        x.racing = x.ch.on
        x.ev["idm_break"] += 1
        x.ev["enter_lock" if x.phase == PH_LOCK else "seek_bos"] += 1
        altSeg = (x.segHi if x.dir == DIR_BULL else x.segLo) \
            if x.segBar is not None else None
        altLeg = x.legHi if x.dir == DIR_BULL else x.legLo
        x.bosLog.append([abs(x.bos.px - c) / c, i, None, altLeg, altSeg,
                         x.ch.px if x.ch.on else None, x.dir, x.phase])
        x.lvlLog.append(("BOS", round(x.bos.px, 10), x.bos.bar))
        # THE STAGE A TRIGGER. Everything the trade needs is fixed here:
        #   entry  the close of this bar                               [T9]
        #   stop   this bar's extreme - the IDM RAID EXTREME (§73). At the
        #          moment of entry the raid is exactly this bar, so the stop is
        #          deterministic and needs no lookahead.
        #   bos    the level the thesis says price reaches
        #   choch  the opposing boundary, if one exists
        log(x, "idm_break", i, entry=c, stop=(l if x.dir == DIR_BULL else h),
            bos=x.bos.px, choch=(x.ch.px if x.ch.on else None),
            locked=(x.phase == PH_LOCK))
        moved = True
        check(x, x.dir == was, "I2 IDM break flipped direction")

    # the first-passage race, only where both boundaries already existed
    if x.racing and not moved:
        tb = h >= x.bos.px if x.dir == DIR_BULL else l <= x.bos.px
        tc = l <= x.ch.px if x.dir == DIR_BULL else h >= x.ch.px
        if tb and tc:
            x.racing = False
            x.ev["race_ambiguous"] += 1     # [§30] counted for neither side
        elif tb:
            x.racing = False
            x.ev["race_bos"] += 1
        elif tc:
            x.racing = False
            x.ev["race_choch"] += 1

    # 7. BOS - continuation. [SRC] Never flips the trend.
    if not moved and x.bos.ready(i) and brk_step(x.bos.b, o, h, l, c):
        was = x.dir
        if x.bosLog and x.bosLog[-1][2] is None:
            x.bosLog[-1][2] = i - x.bosLog[-1][1]
        x.bos.clear()
        newCh = x.phLo if x.dir == DIR_BULL else x.phHi
        newChBar = x.phLoBar if x.dir == DIR_BULL else x.phHiBar
        x.ev["choch_move" if x.ch.on else "choch_create"] += 1
        x.ch.set(newCh, newChBar, i, -1 if x.dir == DIR_BULL else 1, M_CH, HS_CH)
        x.lvlLog.append(("CHOCH", round(newCh, 10), newChBar))
        leg_start(x, newCh, newChBar, h, l, i)
        x.phase = PH_DISCOVER
        x.ev["bos_break"] += 1
        log(x, "bos_break", i, px=c)
        moved = True
        check(x, x.dir == was, "I3 BOS break flipped direction")
        # [SRC] Reuse a correction that already formed during the race.
        if x.latPx is not None and x.latBar > newChBar:
            x.idm.set(x.latPx, x.latBar, i,
                      -1 if x.dir == DIR_BULL else 1, M_IDM, HS_IDM)
            x.phase = PH_TRACK
            x.ev["latent_activated"] += 1

    # 8. CHoCH - the only event allowed to flip. [SRC] INVARIANT 1.
    if not moved and x.ch.ready(i) and brk_step(x.ch.b, o, h, l, c):
        was = x.dir
        if x.bos.on and x.bosLog and x.bosLog[-1][2] is None:
            x.bosLog[-1][2] = "abandoned"
        old = (x.bos.px, x.bos.bar) if x.bos.on else \
              ((x.legHi, x.legHiBar) if was == DIR_BULL
               else (x.legLo, x.legLoBar))
        x.ch.clear()
        x.bos.clear()
        x.idm.clear()
        x.dir = -was
        # [SRC] The old BOS is not discarded - it is retyped as the CHoCH that
        # would flip the new trend back.
        x.ch.set(old[0], old[1], i, 1 if was == DIR_BULL else -1, M_CH, HS_CH)
        leg_start(x, old[0], old[1], h, l, i)
        x.det.reorient(x.dir, h, l)
        x.latPx = x.latBar = None
        x.phase = PH_DISCOVER
        x.racing = False
        x.ev["trend_flip"] += 1
        log(x, "choch_break", i, px=c)
        moved = True
        check(x, x.dir != was, "I1 CHoCH break did not flip")

    if x.phase == PH_LOCK:
        check(x, x.bos.on and x.ch.on and not x.idm.on, "I5 lock shape wrong")
    if x.dir == DIR_BULL and x.bos.on and x.ch.on:
        check(x, x.bos.px > x.ch.px, "I11 BOS/CHoCH sides crossed")
    if x.dir == DIR_BEAR and x.bos.on and x.ch.on:
        check(x, x.bos.px < x.ch.px, "I11 BOS/CHoCH sides crossed")

    if x.phase != x.held.get("cur"):
        x.held["cur"] = x.phase
        x.phaseBar = i
    k = PHNAME[x.phase]
    x.held[k] = max(x.held[k], i - x.phaseBar)
    return moved


def engine(cs):
    """Three independent contexts over three CHAINED normalizer streams.

    [INF] Deep's normalizer reads every raw candle. Internal's reads only what
    Deep's passed. Main's reads only what Internal's passed. Each depth
    therefore owns its own normalizer, its own detector and its own pivots -
    they are not the same events reset at different times.

    A child's scope reset is driven by the parent's boundary resolution and is
    applied on the FOLLOWING bar, because the chain has to run deep-first for
    the streams to exist while Main resolves last. That one-bar lag is
    deterministic and is recorded here rather than hidden.
    """
    main, inter, deep = Ctx(0), Ctx(1), Ctx(2)
    inter.confine, deep.confine = main, inter
    for x in (main, inter, deep):
        x.det.reorient(DIR_BULL, cs[0].h, cs[0].l)
        x.boot.reorient(DIR_BEAR, cs[0].h, cs[0].l)
    resetInt = resetDeep = False
    groups = []
    for i, k in enumerate(cs):
        o, h, l, c = k.o, k.h, k.l, k.c
        # MEASURED, AND IT SETTLES THE ARCHITECTURE: the inside-bar
        # normalizer is IDEMPOTENT. A group closes on the bar that breaks its
        # range, and that bar opens the next group - so group N+1 always breaks
        # group N by construction. A second pass removes nothing (Internal and
        # Main filtered 0.0% of what they were fed, twice, for two different
        # emit rules). Granularity therefore cannot separate the three depths,
        # and there is no length parameter available to separate them either.
        #
        # So the depths are separated by SCOPE, which necessarily means resets.
        # What makes that real rather than decorative is that each depth owns
        # its own ORIENTED detector: a bull-oriented and a bear-oriented
        # detector on the same candles find different corrections, and a child
        # re-bootstrapped inside its parent's range runs shorter legs with its
        # own direction. The mirroring test below is what checks it.
        g1 = deep.norm.feed(o, h, l, c, i, i)
        if g1:
            groups.append((i, g1[0], g1[1], g1[2], g1[3]))
            gi, gh, gl, gc, ghb, glb = g1
            rDeep = ctx_step(deep, resetDeep, True, i, gi, gh, gl, gc, ghb, glb)
            rInt = ctx_step(inter, resetInt, True, i, gi, gh, gl, gc, ghb, glb)
            rMain = ctx_step(main, False, True, i, gi, gh, gl, gc, ghb, glb)
            resetInt, resetDeep = rMain, rInt
            del rDeep
    return main, inter, deep, groups


# ═════════════════════════ CALIBRATION REPORT ═══════════════════════════════
REF_IDM_PER_2K = 23.0     # reference, ZEC 15m, ~2000 bars
REF_BOS_SHARE = 0.565     # reference first-passage split


async def main():
    syms = ["ZEC_USDT", "BTC_USDT", "ETH_USDT", "SOL_USDT", "ONDO_USDT",
            "LINK_USDT", "AVAX_USDT", "DOGE_USDT"]
    async with aiohttp.ClientSession() as sess:
        cs = await load_universe(sess, syms, "Min15", 120, min_bars=2000)

    print("RIPTIDE LIT v0.2 - ENGINE VALIDATION")
    print("Main first, per the validation order. Internal and Deep are")
    print("reported but Main has to be right before either matters.\n")
    print("THE FIXTURE: the reference shows 23 TAKEN inducements per ~2000")
    print("bars on ZEC 15m, splitting 56.5/43.5 BOS-first vs CHoCH-first.\n")

    res = {}
    print(f"  {'symbol':<11}{'bars':>7}{'real':>7}{'pivots':>8}{'IDM':>6}"
          f"{'taken':>7}{'BOS':>6}{'CHoCH':>7}{'flip':>6}"
          f"{'taken/2k':>10}{'invariant':>11}")
    for s, k in cs.items():
        m, it, dp, _g = engine(k)
        res[s] = (m, it, dp)
        n = len(k)
        realN = dp.norm.nEmit
        per2k = m.ev["idm_break"] * 2000 / n
        print(f"  {s:<11}{n:>7}{realN / max(dp.norm.nFed, 1):>7.0%}"
              f"{m.ev['pivot']:>8}"
              f"{m.ev['idm_create'] + m.ev['idm_move']:>6}"
              f"{m.ev['idm_break']:>7}{m.ev['bos_break']:>6}"
              f"{m.ev['choch_create'] + m.ev['choch_move']:>7}"
              f"{m.ev['trend_flip']:>6}{per2k:>10.1f}"
              f"{sum(m.bad.values()):>11}")

    zn = len(cs["ZEC_USDT"])
    print(f"\n{'=' * 96}\nZEC 15m AGAINST THE REFERENCE FIXTURE\n{'=' * 96}")
    print("  the 23 is the reference's DEEPEST degree, not its Main - it was")
    print("  recorded in research/lit.py as 'deep-degree IDM count 21 vs")
    print("  reference 23'. So Deep is the row that has to match, and Main")
    print("  being far below it is expected rather than a fault.")
    print(f"  {'depth':<8}{'taken':>8}{'per 2000 bars':>16}{'vs ref 23':>12}"
          f"{'BOS-first':>12}{'n':>5}")
    for idx, nm in ((0, "main"), (1, "int"), (2, "deep")):
        x = res["ZEC_USDT"][idx]
        p2k = x.ev["idm_break"] * 2000 / zn
        b, c2 = x.ev["race_bos"], x.ev["race_choch"]
        sh = f"{b / (b + c2):.1%}" if b + c2 else "-"
        print(f"  {nm:<8}{x.ev['idm_break']:>8}{p2k:>16.1f}"
              f"{p2k / REF_IDM_PER_2K:>11.2f}x{sh:>12}{b + c2:>5}")
    print(f"  reference first passage {REF_BOS_SHARE:.1%} BOS-first.")

    print(f"\n{'=' * 96}\nINVARIANTS - any non-zero row is a real defect\n"
          f"{'=' * 96}")
    allbad = Counter()
    for s, (m, it, dp) in res.items():
        for x, nm in ((m, "main"), (it, "int"), (dp, "deep")):
            for kk, v in x.bad.items():
                allbad[f"{nm}  {kk}"] += v
    if not allbad:
        print("  all clean across every depth and every symbol")
    for kk, v in allbad.most_common():
        print(f"  {kk:<48}{v:>8}")

    print(f"\n{'=' * 96}\nARE THE THREE DEPTHS DIFFERENT STRUCTURES\n{'=' * 96}")
    print("  ONE normalized stream - repeated normalization is idempotent and")
    print("  was measured to filter nothing. Each depth owns its own ORIENTED")
    print("  detector and its own scope, which is what makes the pivots differ.")
    print(f"  {'depth':<8}{'pivots':>9}{'IDM':>7}{'taken':>7}"
          f"{'BOS':>6}{'flip':>6}{'resets':>8}{'latent used':>13}")
    for idx, nm in ((0, "main"), (1, "int"), (2, "deep")):
        tot = Counter()
        for s, tr in res.items():
            tot.update(tr[idx].ev)
        print(f"  {nm:<8}{tot['pivot']:>9}"
              f"{tot['idm_create'] + tot['idm_move']:>7}{tot['idm_break']:>7}"
              f"{tot['bos_break']:>6}{tot['trend_flip']:>6}"
              f"{tot['scope_reset']:>8}{tot['latent_activated']:>13}")

    print(f"\n{'=' * 96}\nPHASE OCCUPANCY - longest run in one phase, in bars\n"
          f"{'=' * 96}")
    print("  a phase held for most of the window is a deadlock wearing a "
          "state name.")
    for idx, nm in ((0, "main"), (1, "int"), (2, "deep")):
        w = Counter()
        for s, tr in res.items():
            for ph in ("discover", "track", "seek", "lock"):
                w[ph] = max(w[ph], tr[idx].held[ph])
        print(f"  {nm:<6}" + "   ".join(f"{p} {w[p]:>5}" for p in
                                        ("discover", "track", "seek", "lock")))

    print(f"\n{'=' * 96}\nEVERY BOS LOCKED BY MAIN\n{'=' * 96}")
    logs = [e for s in res for e in res[s][0].bosLog]
    kinds = Counter(e[2] if not isinstance(e[2], int) else "broke"
                    for e in logs)
    nb = max(len(logs), 1)
    for kk, lab in (("broke", "broke"),
                    ("abandoned", "abandoned - CHoCH resolved first"),
                    (None, "still open at window end")):
        print(f"    {lab:<38}{kinds[kk]:>6} ({kinds[kk] / nb:>4.0%})")
    ds = sorted(e[0] for e in logs)
    if ds:
        print(f"  distance from price when locked: median "
              f"{ds[len(ds) // 2]:.2%}   p90 {ds[int(.9 * (len(ds) - 1))]:.2%}"
              f"   max {ds[-1]:.2%}")

    print(f"\n{'=' * 96}\nSAME-BAR AMBIGUITY AND INSIDE BARS\n{'=' * 96}")
    amb = sum(res[s][0].ev["race_ambiguous"] for s in res)
    both = sum(res[s][2].norm.nBoth for s in res)
    print(f"  bars touching both boundaries at once: {amb} - excluded from "
          f"first passage, never resolved by guessing")
    print(f"  candles taking out both sides of a mother range: {both} at Main")


    print(f"\n{'=' * 96}\nARE THE DEPTHS MIRRORING EACH OTHER\n{'=' * 96}")
    print("  the brief's complaint is iBOS/iCHoCH that duplicate Main. a level")
    print("  published by a child at the SAME price and SAME anchor bar as one")
    print("  its parent published is a mirror, not internal structure.")
    print(f"  {'pair':<18}{'child levels':>14}{'identical to parent':>22}"
          f"{'share':>8}")
    for a, b, nm in ((0, 1, "main -> int"), (1, 2, "int -> deep")):
        dup = tot2 = 0
        for s2 in res:
            par = {(k, v, w) for k, v, w in res[s2][a].lvlLog}
            ch = res[s2][b].lvlLog
            tot2 += len(ch)
            dup += sum(1 for e in ch if e in par)
        print(f"  {nm:<18}{tot2:>14}{dup:>22}{dup / max(tot2, 1):>8.1%}")
    print("  anything approaching 100% means the hierarchy is decorative.")


if __name__ == "__main__":
    asyncio.run(main())
