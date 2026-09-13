"""VALIDATION HARNESS FOR riptide-lit.pine v0.1 - NOT a strategy, not bot code.

This exists for one reason: there is no Pine compiler here, and the last
structure engine built in this project deadlocked THREE separate times in ways
that only showed up as a level the chart said price had to break sitting
80,000 points away. Each one cost a round trip through screenshots.

So the state machine is transcribed here line for line from the Pine and run
over real candles before the Pine is ever pasted into TradingView. What it can
prove:

  - the engine terminates: no phase is entered and never left
  - every level it publishes is reachable, not an all-history extreme
  - the event counts per depth are sane rather than zero or runaway
  - the three depths genuinely disagree, which is the point of having three

What it cannot prove: that the Pine COMPILES, or that the drawing is right.
Those still need a chart.

The transcription is deliberately literal - same names, same order, same
branches - so that any divergence between the two files is a diff rather than
an argument. The master prompt's phase 2 requires Pine and Python structure to
match on historical windows; this is the beginning of that, not a port of the
trading logic, of which there is none.

    PYTHONPATH=. RIPTIDE_DEEP_CACHE=/tmp/deep python3 research/lit_v01.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
from collections import Counter                         # noqa: E402
from dataclasses import dataclass, field                # noqa: E402

import aiohttp                                          # noqa: E402

from research.deep import load_universe                 # noqa: E402

DIR_NONE, DIR_BULL, DIR_BEAR = 0, 1, -1
PH_IDLE, PH_TRACK, PH_SEEK, PH_LOCK = 0, 1, 2, 3
BRK_SHADOW, BRK_BODY, BRK_SWEEP = 0, 1, 2
PB_NONE, PB_IMPULSE, PB_ACTIVE = 0, 1, 2

PHASE = {PH_IDLE: "idle", PH_TRACK: "track", PH_SEEK: "seek", PH_LOCK: "lock"}

# The Pine defaults, so the two files describe the same chart.
M_PB, M_IDM, M_BOS, M_CH = BRK_SHADOW, BRK_SHADOW, BRK_SWEEP, BRK_SWEEP
HS_PB, HS_IDM, HS_BOS, HS_CH = False, False, True, True
STRICT_INSIDE = True


@dataclass
class Brk:
    base: float = None
    act: float = None
    dir: int = 0
    mode: int = 0
    useHS: bool = False
    pend: bool = False
    hsLvl: float = None
    hsHi: float = None
    hsLo: float = None
    hsMomHi: float = None
    hsMomLo: float = None
    fired: bool = False


@dataclass
class PB:
    state: int = PB_NONE
    dir: int = 0
    startBar: int = None
    trkHi: float = None
    trkLo: float = None
    conf: float = None
    rngHi: float = None
    rngHiBar: int = None
    rngLo: float = None
    rngLoBar: int = None
    swept: float = None
    b: Brk = field(default_factory=Brk)


@dataclass
class Ctx:
    depth: int = 0
    dir: int = DIR_NONE
    phase: int = PH_IDLE
    legBar: int = None
    legPx: float = None
    idmPx: float = None
    idmBar: int = None
    idmOn: bool = False
    bosPx: float = None
    bosBar: int = None
    bosOn: bool = False
    chPx: float = None
    chBar: int = None
    chOn: bool = False
    legHi: float = None
    legHiBar: int = None
    legLo: float = None
    legLoBar: int = None
    phHi: float = None
    phHiBar: int = None
    phLo: float = None
    phLoBar: int = None
    bIdm: Brk = field(default_factory=Brk)
    bBos: Brk = field(default_factory=Brk)
    bCh: Brk = field(default_factory=Brk)
    latDem: float = None
    latDemBar: int = None
    latSup: float = None
    latSupBar: int = None
    racing: bool = False
    sawBos: bool = False
    sawCh: bool = False
    # harness-only instrumentation, with no counterpart in the Pine
    ev: Counter = field(default_factory=Counter)
    phaseBar: int = 0
    worst: dict = field(default_factory=dict)
    far: float = 0.0
    # every BOS ever locked: [distance from price, lock bar, outcome]
    bosLog: list = field(default_factory=list)


def arm(b, lvl, d, mode, useHS):
    b.base = lvl
    b.act = lvl
    b.dir = d
    b.mode = mode
    b.useHS = useHS
    b.pend = False
    b.fired = False
    b.hsLvl = None


def disarm(b):
    b.base = None
    b.act = None
    b.pend = False
    b.fired = False


def step(b, ok, o, h, l, c):
    done = False
    b.fired = False
    if b.base is not None and ok:
        up = b.dir > 0
        if b.pend:
            contained = h < b.hsMomHi and l > b.hsMomLo
            if not contained:
                b.hsHi = max(b.hsHi, h)
                b.hsLo = min(b.hsLo, l)
                b.pend = False
                if (c > b.hsLvl) if up else (c < b.hsLvl):
                    done = True
                else:
                    b.fired = True
        else:
            if b.mode == BRK_SHADOW:
                raw = h > b.base if up else l < b.base
            elif b.mode == BRK_BODY:
                raw = c > b.base if up else c < b.base
            else:
                if up and h > b.act and c <= b.act:
                    b.act = h
                elif not up and l < b.act and c >= b.act:
                    b.act = l
                raw = c > b.act if up else c < b.act
            if raw:
                if b.useHS and b.mode != BRK_SHADOW:
                    b.pend = True
                    b.hsLvl = b.act if b.mode == BRK_SWEEP else b.base
                    b.hsHi, b.hsLo = h, l
                    b.hsMomHi, b.hsMomLo = h, l
                else:
                    done = True
    return done


def leg_start(c, px, bar, fh, fl, i):
    c.legPx, c.legBar = px, bar
    c.legHi, c.legHiBar = fh, i
    c.legLo, c.legLoBar = fl, i


def run(ctx, resetMe, st):
    """One bar of one depth. `st` carries this bar's shared series."""
    i, fh, fl, real = st["i"], st["fh"], st["fl"], st["real"]
    o, h, l, c = st["o"], st["h"], st["l"], st["c"]
    pivLo, pivLoBar = st["pivLo"], st["pivLoBar"]
    pivHi, pivHiBar = st["pivHi"], st["pivHiBar"]
    resolved = False

    if resetMe:
        ctx.dir = DIR_NONE
        ctx.phase = PH_IDLE
        ctx.idmOn = ctx.bosOn = ctx.chOn = False
        ctx.racing = False
        disarm(ctx.bIdm)
        disarm(ctx.bBos)
        disarm(ctx.bCh)
        ctx.ev["reset"] += 1

    if real:
        if ctx.legHi is None or fh > ctx.legHi:
            ctx.legHi, ctx.legHiBar = fh, i
        if ctx.legLo is None or fl < ctx.legLo:
            ctx.legLo, ctx.legLoBar = fl, i
        if ctx.phase in (PH_SEEK, PH_LOCK):
            if ctx.phHi is None or fh > ctx.phHi:
                ctx.phHi, ctx.phHiBar = fh, i
            if ctx.phLo is None or fl < ctx.phLo:
                ctx.phLo, ctx.phLoBar = fl, i

    if pivLo is not None:
        ctx.latDem, ctx.latDemBar = pivLo, pivLoBar
    if pivHi is not None:
        ctx.latSup, ctx.latSupBar = pivHi, pivHiBar

    if ctx.dir == DIR_NONE:
        if pivLo is not None:
            ctx.dir = DIR_BULL
            leg_start(ctx, pivLo, pivLoBar, fh, fl, i)
        elif pivHi is not None:
            ctx.dir = DIR_BEAR
            leg_start(ctx, pivHi, pivHiBar, fh, fl, i)

    if ctx.dir != DIR_NONE and ctx.phase != PH_LOCK:
        cand = pivLo if ctx.dir == DIR_BULL else pivHi
        candBar = pivLoBar if ctx.dir == DIR_BULL else pivHiBar
        if cand is not None:
            ctx.idmPx, ctx.idmBar, ctx.idmOn = cand, candBar, True
            ctx.phase = PH_TRACK
            arm(ctx.bIdm, cand, -1 if ctx.dir == DIR_BULL else 1, M_IDM, HS_IDM)
            ctx.ev["idm_published"] += 1

    if ctx.idmOn and step(ctx.bIdm, real, o, h, l, c):
        ctx.idmOn = False
        disarm(ctx.bIdm)
        ctx.bosPx = ctx.legHi if ctx.dir == DIR_BULL else ctx.legLo
        ctx.bosBar = ctx.legHiBar if ctx.dir == DIR_BULL else ctx.legLoBar
        ctx.bosOn = True
        arm(ctx.bBos, ctx.bosPx, 1 if ctx.dir == DIR_BULL else -1, M_BOS, HS_BOS)
        ctx.phHi, ctx.phHiBar = fh, i
        ctx.phLo, ctx.phLoBar = fl, i
        ctx.phase = PH_LOCK if ctx.chOn else PH_SEEK
        ctx.racing = ctx.chOn
        ctx.ev["idm_taken"] += 1
        # A BOS still open when the next IDM break locks another one was
        # SUPERSEDED, not stranded. Recording it as open would invent a
        # deadlock that is not there.
        if ctx.bosLog and ctx.bosLog[-1][2] is None:
            ctx.bosLog[-1][2] = "replaced"
        ctx.bosLog.append([abs(ctx.bosPx - c) / c, i, None])
        # How far away is the level the chart now says price must break? A
        # deadlocked engine announces an unreachable one; this records the
        # worst case so the claim can be checked instead of asserted.
        ctx.far = max(ctx.far, abs(ctx.bosPx - c) / c)

    if ctx.racing and real:
        tBos = h >= ctx.bosPx if ctx.dir == DIR_BULL else l <= ctx.bosPx
        tCh = l <= ctx.chPx if ctx.dir == DIR_BULL else h >= ctx.chPx
        if tBos and tCh:
            ctx.racing = False
            ctx.ev["race_ambiguous"] += 1
        elif tBos:
            ctx.sawBos = True
            ctx.racing = False
        elif tCh:
            ctx.sawCh = True
            ctx.racing = False

    if ctx.bosOn and step(ctx.bBos, real, o, h, l, c):
        ctx.bosOn = False
        disarm(ctx.bBos)
        ctx.chPx = ctx.phLo if ctx.dir == DIR_BULL else ctx.phHi
        ctx.chBar = ctx.phLoBar if ctx.dir == DIR_BULL else ctx.phHiBar
        ctx.chOn = True
        arm(ctx.bCh, ctx.chPx, -1 if ctx.dir == DIR_BULL else 1, M_CH, HS_CH)
        leg_start(ctx, ctx.chPx, ctx.chBar, fh, fl, i)
        ctx.phase = PH_IDLE
        resolved = True
        ctx.ev["bos_broken"] += 1
        if ctx.bosLog and ctx.bosLog[-1][2] is None:
            ctx.bosLog[-1][2] = i - ctx.bosLog[-1][1]
        lat = ctx.latDem if ctx.dir == DIR_BULL else ctx.latSup
        latBar = ctx.latDemBar if ctx.dir == DIR_BULL else ctx.latSupBar
        if lat is not None and latBar is not None and latBar > ctx.chBar:
            ctx.idmPx, ctx.idmBar, ctx.idmOn = lat, latBar, True
            ctx.phase = PH_TRACK
            arm(ctx.bIdm, lat, -1 if ctx.dir == DIR_BULL else 1, M_IDM, HS_IDM)
            ctx.ev["idm_reused"] += 1

    if ctx.chOn and step(ctx.bCh, real, o, h, l, c):
        ctx.chOn = False
        disarm(ctx.bCh)
        was = ctx.dir
        ctx.dir = -was
        if ctx.bosOn:
            oldBos, oldBar = ctx.bosPx, ctx.bosBar
        else:
            oldBos = ctx.legHi if was == DIR_BULL else ctx.legLo
            oldBar = ctx.legHiBar if was == DIR_BULL else ctx.legLoBar
        if ctx.bosOn:
            ctx.bosOn = False
            disarm(ctx.bBos)
            if ctx.bosLog and ctx.bosLog[-1][2] is None:
                ctx.bosLog[-1][2] = "abandoned"   # the CHoCH resolved first
        ctx.chPx, ctx.chBar, ctx.chOn = oldBos, oldBar, True
        arm(ctx.bCh, oldBos, 1 if was == DIR_BULL else -1, M_CH, HS_CH)
        leg_start(ctx, oldBos, oldBar, fh, fl, i)
        ctx.idmOn = False
        disarm(ctx.bIdm)
        ctx.phase = PH_IDLE
        resolved = True
        ctx.ev["trend_flip"] += 1

    # instrumentation: how long has this depth sat in one phase?
    if ctx.phase != ctx.worst.get("cur"):
        ctx.worst["cur"] = ctx.phase
        ctx.phaseBar = i
    held = i - ctx.phaseBar
    key = PHASE[ctx.phase]
    if held > ctx.worst.get(key, 0):
        ctx.worst[key] = held
    return resolved


def engine(cs):
    """Run all three depths over one symbol. Returns the three contexts."""
    main, inter, deep = Ctx(0), Ctx(1), Ctx(2)
    dem, sup = PB(dir=DIR_BULL), PB(dir=DIR_BEAR)
    momHi = momLo = None
    fh = fl = None
    nInside = nOutBoth = 0

    for i, k in enumerate(cs):
        o, h, l, c = k.o, k.h, k.l, k.c
        inside = False
        if momHi is None:
            momHi, momLo = h, l
        else:
            over = h >= momHi if STRICT_INSIDE else h > momHi
            under = l <= momLo if STRICT_INSIDE else l < momLo
            if over and under:
                nOutBoth += 1
                momHi, momLo = h, l
            elif over or under:
                momHi, momLo = h, l
            else:
                inside = True
                nInside += 1
        fh = fh if inside else h
        fl = fl if inside else l
        real = not inside

        pivLo = pivLoBar = pivHi = pivHiBar = None
        if real:
            if dem.state == PB_NONE:
                dem.state, dem.trkHi, dem.trkLo = PB_IMPULSE, fh, fl
            elif dem.state == PB_IMPULSE:
                if fl < dem.trkLo:
                    dem.state, dem.startBar, dem.conf = PB_ACTIVE, i, fh
                    dem.rngHi, dem.rngHiBar = fh, i
                    dem.rngLo, dem.rngLoBar = fl, i
                    dem.swept = None
                    arm(dem.b, fh, 1, M_PB, HS_PB)
                elif fh > dem.trkHi:
                    dem.trkHi, dem.trkLo = fh, fl
            else:
                if fh > dem.rngHi:
                    dem.rngHi, dem.rngHiBar = fh, i
                if fl < dem.rngLo:
                    # [CORRECTION to the spec] The level that confirms a low is
                    # the high of the candle that MADE that low, so it tracks
                    # down as the correction deepens. Fixed at the bar the
                    # correction began - which is what the spec text says - a
                    # single correction stayed open for 9200 bars and the
                    # engine starved. See the note in riptide-lit.pine.
                    dem.rngLo, dem.rngLoBar = fl, i
                    dem.conf = fh
                    dem.swept = None
                    arm(dem.b, fh, 1, M_PB, HS_PB)
                if h > dem.conf and c <= dem.conf:
                    dem.swept = h if dem.swept is None else max(dem.swept, h)
                if step(dem.b, True, o, h, l, c):
                    pivLo, pivLoBar = dem.rngLo, dem.rngLoBar
                    dem.state, dem.trkHi, dem.trkLo = PB_IMPULSE, fh, fl
                    disarm(dem.b)

            if sup.state == PB_NONE:
                sup.state, sup.trkHi, sup.trkLo = PB_IMPULSE, fh, fl
            elif sup.state == PB_IMPULSE:
                if fh > sup.trkHi:
                    sup.state, sup.startBar, sup.conf = PB_ACTIVE, i, fl
                    sup.rngHi, sup.rngHiBar = fh, i
                    sup.rngLo, sup.rngLoBar = fl, i
                    sup.swept = None
                    arm(sup.b, fl, -1, M_PB, HS_PB)
                elif fl < sup.trkLo:
                    sup.trkHi, sup.trkLo = fh, fl
            else:
                if fl < sup.rngLo:
                    sup.rngLo, sup.rngLoBar = fl, i
                if fh > sup.rngHi:
                    sup.rngHi, sup.rngHiBar = fh, i
                    sup.conf = fl
                    sup.swept = None
                    arm(sup.b, fl, -1, M_PB, HS_PB)
                if l < sup.conf and c >= sup.conf:
                    sup.swept = l if sup.swept is None else min(sup.swept, l)
                if step(sup.b, True, o, h, l, c):
                    pivHi, pivHiBar = sup.rngHi, sup.rngHiBar
                    sup.state, sup.trkHi, sup.trkLo = PB_IMPULSE, fh, fl
                    disarm(sup.b)

        st = dict(i=i, fh=fh, fl=fl, real=real, o=o, h=h, l=l, c=c,
                  pivLo=pivLo, pivLoBar=pivLoBar,
                  pivHi=pivHi, pivHiBar=pivHiBar)
        rMain = run(main, False, st)
        rInt = run(inter, rMain, st)
        run(deep, rInt, st)
        for ctx in (main, inter, deep):
            if ctx.sawBos:
                ctx.ev["race_bos"] += 1
                ctx.sawBos = False
            if ctx.sawCh:
                ctx.ev["race_choch"] += 1
                ctx.sawCh = False
    return main, inter, deep, nInside, nOutBoth, len(cs)


async def main():
    syms = ["BTC_USDT", "ETH_USDT", "SOL_USDT", "ONDO_USDT", "ZEC_USDT",
            "LINK_USDT", "AVAX_USDT", "DOGE_USDT"]
    async with aiohttp.ClientSession() as sess:
        cs = await load_universe(sess, syms, "Min15", 120, min_bars=2000)

    print("RIPTIDE LIT v0.1 - ENGINE VALIDATION")
    print(f"{len(cs)} symbols, Min15, 120 days. Pine defaults: pullback and "
          f"IDM on Shadow,\nBOS and CHoCH on Body & Sweep with Hidden Shadow, "
          f"strict inside bars.\n")

    tot = Counter()
    engines = {}
    worstPhase = Counter()
    farthest = 0.0
    nbars = nins = nout = 0
    print(f"  {'symbol':<11}{'bars':>7}{'inside':>8}{'IDM':>6}{'taken':>7}"
          f"{'BOS brk':>9}{'flips':>7}{'main':>7}{'int':>6}{'deep':>6}"
          f"{'worst hold':>12}")
    for s, k in cs.items():
        m, it, d, ins, ob, n = engine(k)
        engines[s] = m
        nbars += n
        nins += ins
        nout += ob
        for ctx, nm in ((m, "main"), (it, "int"), (d, "deep")):
            for key, v in ctx.ev.items():
                tot[f"{nm}.{key}"] += v
            for ph in ("seek", "lock", "track", "idle"):
                worstPhase[f"{nm}.{ph}"] = max(worstPhase[f"{nm}.{ph}"],
                                               ctx.worst.get(ph, 0))
            farthest = max(farthest, ctx.far)
        hold = max(m.worst.get(p, 0) for p in ("seek", "lock", "track", "idle"))
        print(f"  {s:<11}{n:>7}{ins / n:>8.0%}"
              f"{m.ev['idm_published']:>6}{m.ev['idm_taken']:>7}"
              f"{m.ev['bos_broken']:>9}{m.ev['trend_flip']:>7}"
              f"{m.ev['idm_taken']:>7}{it.ev['idm_taken']:>6}"
              f"{d.ev['idm_taken']:>6}{hold:>10} bars")

    print(f"\n{'=' * 92}\nDOES IT TERMINATE\n{'=' * 92}")
    print("  the previous engine deadlocked by locking a BOS at an "
          "all-history extreme.")
    print("  a phase held for thousands of bars is that failure; a few "
          "hundred is a quiet market.")
    for nm in ("main", "int", "deep"):
        print(f"  {nm:<6}" + "  ".join(
            f"{ph} {worstPhase[f'{nm}.{ph}']:>5}" for ph in
            ("idle", "track", "seek", "lock")))
    print(f"\n  farthest BOS ever locked, as a fraction of price at the time: "
          f"{farthest:.1%}")
    print("  an unreachable level is the symptom; anything in single-digit "
          "percent is a real level.")

    print(f"\n{'=' * 92}\nDO THE THREE DEPTHS ACTUALLY DIFFER\n{'=' * 92}")
    print("  if Internal and Deep merely echo Main, the scope hierarchy is "
          "decorative.")
    for nm in ("main", "int", "deep"):
        print(f"  {nm:<6} IDM published {tot[f'{nm}.idm_published']:>6}"
              f"   taken {tot[f'{nm}.idm_taken']:>6}"
              f"   BOS broken {tot[f'{nm}.bos_broken']:>6}"
              f"   flips {tot[f'{nm}.trend_flip']:>6}"
              f"   resets {tot[f'{nm}.reset']:>6}"
              f"   reused PB {tot[f'{nm}.idm_reused']:>5}")

    print(f"\n{'=' * 92}\nFIRST PASSAGE AFTER THE INDUCEMENT IS TAKEN\n"
          f"{'=' * 92}")
    print("  the model's central claim: inducement taken, then the move "
          "continues to the BOS")
    print("  more often than it turns and takes the CHoCH. bars touching both "
          "are excluded.")
    for nm in ("main", "int", "deep"):
        b, c2 = tot[f"{nm}.race_bos"], tot[f"{nm}.race_choch"]
        t = b + c2
        if t:
            print(f"  {nm:<6} BOS first {b:>5} ({b / t:>4.0%})   "
                  f"CHoCH first {c2:>5} ({c2 / t:>4.0%})   "
                  f"ambiguous {tot[f'{nm}.race_ambiguous']:>4}   n {t}")
        else:
            print(f"  {nm:<6} no completed races")

    print(f"\n{'=' * 92}\nWHAT HAPPENS TO EVERY BOS THAT IS LOCKED\n{'=' * 92}")
    print("  'farthest' above is a headline without a denominator. a level far")
    print("  from price is only a bug if it STRANDS the engine - if it is")
    print("  superseded by the next IDM break it cost nothing.")
    logs = [e for s2 in cs for e in engines[s2].bosLog]
    nb = len(logs)
    broke = [e for e in logs if isinstance(e[2], int)]
    kinds = Counter(e[2] if not isinstance(e[2], int) else "broke" for e in logs)
    for k, lab in (("broke", "broke"), ("abandoned", "abandoned - CHoCH went first"),
                   ("replaced", "superseded by a nearer one"), (None, "STILL OPEN at window end")):
        print(f"    {lab:<34}{kinds[k]:>6} ({kinds[k] / nb:>4.0%})")
    ds = sorted(e[0] for e in logs)
    qq = lambda x: ds[int(x * (len(ds) - 1))]
    print(f"\n  distance from price when locked:  median {qq(.5):.2%}   "
          f"p90 {qq(.90):.2%}   p99 {qq(.99):.2%}   max {ds[-1]:.2%}")
    bs = sorted(e[2] for e in broke)
    print(f"  bars to break, of those that broke:  median {bs[len(bs) // 2]}  "
          f" p90 {bs[int(.9 * (len(bs) - 1))]}   max {bs[-1]}")
    far = [e for e in logs if e[0] > 0.10]
    fk = Counter(e[2] if not isinstance(e[2], int) else "broke" for e in far)
    print(f"  locked more than 10% away: {len(far)} ({len(far) / nb:.1%}) - "
          f"{fk['replaced']} superseded, {fk['broke']} broke, "
          f"{fk['abandoned']} abandoned, {fk[None]} stranded")

    print(f"\n{'=' * 92}\nINSIDE BARS\n{'=' * 92}")
    print(f"  {nins} of {nbars} bars inside a live mother range "
          f"({nins / nbars:.0%}); {nout} took out both sides at once "
          f"({nout / nbars:.2%}).")
    print("  the both-sides case is the one OHLC cannot order. it is counted "
          "rather than guessed.")


if __name__ == "__main__":
    asyncio.run(main())
