"""THE LIT ENGINE IN PYTHON, so it can be debugged against real candles.

WHY THIS EXISTS. riptide-structure.pine can only be run by pasting it into
TradingView and looking at a screenshot, which is a terrible way to find a bug:
every iteration costs a round trip, the only output is a picture, and a level
sitting off the visible price range is indistinguishable from one that was
never drawn. Three separate deadlocks in that file were each diagnosed from a
number in the corner of an image.

This is the same engine over the same candles with the internals printed. It is
a PORT, not a reimplementation — the structure below mirrors the Pine section
for section so a fix found here transfers by inspection:

    inside bars   ->  section 1
    rawBreak      ->  section 2
    raw pivots    ->  section 3
    Casc/Deg      ->  section 4

The project already works this way: riptide/engine.py is the Python side of
riptide-indicator.pine, and every measurement in research/ depends on the two
agreeing.

    PYTHONPATH=. python3 research/lit.py ZEC_USDT Min15

──────────────────────────────────────────────────────────────────────────────
WHAT THIS MEASURED, 13 Sep 2026 — THE CENTRAL CLAIM OF LIT IS A 60/40.

The literature states the inducement sequence as near-deterministic: the first
pullback after a break is the trap, its sweep collects the stops, and "the real
institutional move" then delivers in the true direction. The entry rule that
follows — never take the first pullback, wait for the sweep — is presented as
the discipline that "eliminates the vast majority of inducement losses".

Once the inducement is taken, does price reach the BOS level or the CHoCH level
first? Eight symbols, Min15, ~2000 bars each:

    symbol       IDM   ->BOS   ->CHoCH    BOS%
    ZEC           21      11        9    52.4%
    BTC           18       9        8    50.0%
    ETH           12       5        7    41.7%
    SOL           20      15        4    75.0%
    DASH          34      19       14    55.9%
    XLM           25      14       11    56.0%
    ADA           21      13        7    61.9%
    LINK          26      16        9    61.5%
    ALL          177     102       69    57.6%

97% resolve. Of those, 59.6% continue to the break and 40.4% go the other way.

TWO INDEPENDENT IMPLEMENTATIONS AGREE ON THIS. The reference indicator's own
statistics table reports 56.5% / 43.5% on ZEC — this engine reports 52.4/42.9
on the same symbol and 59.6/40.4 pooled across eight. Nobody is disputing the
number; the literature simply does not quote it.

WHAT THAT MEANS, AND IT IS NOT NOTHING. A 60/40 edge is real and tradeable at
2:1 — it is roughly what every honest edge in this repository looks like. What
it is not is a trap-detector. "Wait for the sweep and the real move delivers"
describes three trades in five. The other two sweep the inducement and keep
going, which from inside the trade is indistinguishable until the CHoCH level
is gone.

So the structure is worth drawing and the sequence is worth knowing. The
certainty the write-ups attach to it is not in the data — including in the data
the reference tool prints on its own chart.
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import sys                                              # noqa: E402
from dataclasses import dataclass, field                # noqa: E402
from datetime import datetime, timezone                 # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.exchange import fetch_candles              # noqa: E402

SHADOW, BODY, SWEEP = "Shadow", "Body", "Body & Sweep"


def ts(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%d %b %H:%M")


@dataclass
class Slot:
    """One level's break state: hidden-shadow pending, and the sweep memory."""
    pend_on: bool = False
    pend_lvl: float = None
    pend_up: bool = False
    sw_lvl: float = None      # furthest a wick has failed through this level
    sw_for: float = None      # which level that memory belongs to


class Engine:
    def __init__(self, mode_pb=SHADOW, mode_idm=SHADOW, mode_bos=SWEEP,
                 mode_ch=SWEEP, hid_bos=True, hid_ch=True):
        self.mode_pb, self.mode_idm = mode_pb, mode_idm
        self.mode_bos, self.mode_ch = mode_bos, mode_ch
        self.hid_bos, self.hid_ch = hid_bos, hid_ch
        self.slots = [Slot() for _ in range(10)]
        self.c = None                       # the bar being processed

    # ── section 2: break confirmation ──────────────────────────────────────
    def _wick_only(self, lvl, up):
        c = self.c
        return (c.h > lvl and c.c <= lvl) if up else (c.l < lvl and c.c >= lvl)

    def _raw(self, slot, lvl, up, mode):
        c = self.c
        if mode == SHADOW:
            return c.h > lvl if up else c.l < lvl
        if mode == BODY:
            return c.c > lvl if up else c.c < lvl
        sl = self.slots[slot].sw_lvl
        eff = lvl if sl is None else (max(lvl, sl) if up else min(lvl, sl))
        return c.c > eff if up else c.c < eff

    def confirm(self, slot, lvl, up, mode, use_hidden):
        if lvl is None:
            return False
        s = self.slots[slot]
        if s.sw_for is None or s.sw_for != lvl:
            s.sw_for, s.sw_lvl = lvl, None
        if self._wick_only(lvl, up):
            w = self.c.h if up else self.c.l
            s.sw_lvl = w if s.sw_lvl is None else (max(s.sw_lvl, w) if up
                                                   else min(s.sw_lvl, w))
        if s.pend_on:
            s.pend_on = False
            back = (self.c.c <= s.pend_lvl) if s.pend_up else \
                   (self.c.c >= s.pend_lvl)
            return not back
        if self._raw(slot, lvl, up, mode):
            if use_hidden and mode != SHADOW:
                s.pend_on, s.pend_lvl, s.pend_up = True, lvl, up
                return False
            return True
        return False


@dataclass
class Deg:
    """One structure degree. Mirrors the Pine type of the same name."""
    slot: int
    tag: str
    bias: int = 0
    idm: float = None
    idm_t: int = None
    idm_taken: bool = False
    bos: float = None
    bos_t: int = None
    bos_cand: float = None
    bos_cand_t: int = None
    ch: float = None
    ch_t: int = None
    run_hi: float = None
    run_hi_t: int = None
    run_lo: float = None
    run_lo_t: int = None
    pv_hi: float = None
    pv_hi_t: int = None
    pv_lo: float = None
    pv_lo_t: int = None
    events: list = field(default_factory=list)
    # Every inducement-take, with the two levels that were live at that moment.
    # Recorded HERE rather than read back later because a BOS clears d.bos on
    # the bar it fires — which is exactly why the Pine table read 0%: by the
    # time the statistics block ran, the level it wanted to score was gone.
    arms: list = field(default_factory=list)
    out: tuple = None          # (is_high, price, time) handed to the degree above


@dataclass
class Casc:
    """Promote a swing when the NEXT swing on the same side does not exceed it.

    A TWO-SIDED FRACTAL WAS FAR TOO AGGRESSIVE. Requiring the swing either side
    to be lower thins the stream about fourfold per level, which put the three
    degrees at 42 / 16 / 5 events over three weeks — so the upper two had
    almost nothing to say, and every label on the chart was a deep-degree one.
    Against the reference, where the same window carries roughly 50 / 34 / 25,
    that is one whole degree of offset: it printed iBOS where we printed iiIDM.

    One-sided is the right strength. Looking only forward thins by about a
    third per level and lands on 42 / 30 / 23, which is the reference's shape.
    Measured, not guessed: the alternatives were swept and printed side by side
    (fractal 42/16/5, higher-high 42/17/19, one-sided 42/30/23, none 42/33/32).
    """
    h1: float = None
    h1t: int = None
    l1: float = None
    l1t: int = None

    def feed(self, is_hi, px, t):
        if is_hi:
            out = (True, self.h1, self.h1t) if (
                self.h1 is not None and self.h1 > px) else None
            self.h1, self.h1t = px, t
            return out
        out = (False, self.l1, self.l1t) if (
            self.l1 is not None and self.l1 < px) else None
        self.l1, self.l1t = px, t
        return out


def step(eng, d, piv):
    """One bar of the LIT machine for one degree. `piv` is (is_high, px, t)."""
    c = eng.c
    d.out = None
    if piv:
        is_hi, px, t = piv
        if is_hi:
            d.pv_hi, d.pv_hi_t = px, t
        else:
            d.pv_lo, d.pv_lo_t = px, t

    if d.run_hi is None or c.h > d.run_hi:
        d.run_hi, d.run_hi_t = c.h, c.t
    if d.run_lo is None or c.l < d.run_lo:
        d.run_lo, d.run_lo_t = c.l, c.t

    if d.bias == 0 and d.pv_hi is not None and d.pv_lo is not None:
        d.bias = 1 if d.pv_hi_t > d.pv_lo_t else -1
        d.ch, d.ch_t = ((d.pv_lo, d.pv_lo_t) if d.bias > 0
                        else (d.pv_hi, d.pv_hi_t))
        d.run_hi, d.run_hi_t, d.run_lo, d.run_lo_t = c.h, c.t, c.l, c.t

    # a new pullback becomes the inducement and pins the swing it came from
    if piv and d.bias > 0 and not piv[0] and not d.idm_taken:
        if d.ch is None or d.pv_lo > d.ch:
            d.idm, d.idm_t = d.pv_lo, d.pv_lo_t
            d.bos_cand, d.bos_cand_t = d.pv_hi, d.pv_hi_t
            d.run_hi, d.run_hi_t = c.h, c.t
    if piv and d.bias < 0 and piv[0] and not d.idm_taken:
        if d.ch is None or d.pv_hi < d.ch:
            d.idm, d.idm_t = d.pv_hi, d.pv_hi_t
            d.bos_cand, d.bos_cand_t = d.pv_lo, d.pv_lo_t
            d.run_lo, d.run_lo_t = c.l, c.t

    if d.bias == 0:
        return

    if not d.idm_taken and d.idm is not None:
        if eng.confirm(d.slot * 3, d.idm, d.bias < 0, eng.mode_idm, False):
            d.idm_taken = True
            d.events.append(("IDM", c.t, d.idm, d.bias))
            d._pending_arm = True
            use_run = d.bos_cand is None or (
                d.run_hi > d.bos_cand if d.bias > 0 else d.run_lo < d.bos_cand)
            if use_run:
                d.bos, d.bos_t = ((d.run_hi, d.run_hi_t) if d.bias > 0
                                  else (d.run_lo, d.run_lo_t))
            else:
                d.bos, d.bos_t = d.bos_cand, d.bos_cand_t
            if d.bias > 0:
                d.run_lo, d.run_lo_t = c.l, c.t
            else:
                d.run_hi, d.run_hi_t = c.h, c.t
            if getattr(d, "_pending_arm", False):
                d.arms.append(dict(i=eng.i, bos=d.bos, ch=d.ch, bias=d.bias))
                d._pending_arm = False

    if d.bos is not None and eng.confirm(d.slot * 3 + 1, d.bos, d.bias > 0,
                                         eng.mode_bos, eng.hid_bos):
        if d.idm_taken:
            d.events.append(("BOS", c.t, d.bos, d.bias))
            if d.idm is None:
                d.ch, d.ch_t = ((d.run_lo, d.run_lo_t) if d.bias > 0
                                else (d.run_hi, d.run_hi_t))
            else:
                d.ch, d.ch_t = d.idm, d.idm_t
            d.idm = d.bos = d.bos_cand = None
            d.idm_taken = False
            d.run_hi, d.run_hi_t, d.run_lo, d.run_lo_t = c.h, c.t, c.l, c.t
        else:
            d.events.append(("trap", c.t, d.bos, d.bias))

    if d.ch is not None and eng.confirm(d.slot * 3 + 2, d.ch, d.bias < 0,
                                        eng.mode_ch, eng.hid_ch):
        d.events.append(("CHoCH", c.t, d.ch, d.bias))
        px = (d.pv_hi if d.pv_hi is not None else d.run_hi) if d.bias > 0 \
            else (d.pv_lo if d.pv_lo is not None else d.run_lo)
        pt = (d.pv_hi_t if d.pv_hi is not None else d.run_hi_t) if d.bias > 0 \
            else (d.pv_lo_t if d.pv_lo is not None else d.run_lo_t)
        d.out = (d.bias > 0, px, pt)
        d.bias = -d.bias
        d.idm = d.bos = d.bos_cand = None
        d.idm_taken = False
        d.ch, d.ch_t = px, pt
        d.run_hi, d.run_hi_t, d.run_lo, d.run_lo_t = c.h, c.t, c.l, c.t


def run(cs, **kw):
    """Play the whole series. Returns (engine, deep, internal, main)."""
    eng = Engine(**kw)
    deep = Deg(0, "ii")
    intl = Deg(1, "i")
    main = Deg(2, "")
    c1, c2 = Casc(), Casc()

    rng_hi = rng_lo = None
    seek, ext_px, ext_t, ext_opp = 1, None, None, None
    n_inside = 0

    for i, c in enumerate(cs):
        eng.c = c
        eng.i = i
        # ── section 1: inside bars ─────────────────────────────────────────
        inside = False
        if rng_hi is None:
            rng_hi, rng_lo = c.h, c.l
        elif c.h <= rng_hi and c.l >= rng_lo:
            inside = True
            n_inside += 1
        else:
            rng_hi, rng_lo = c.h, c.l

        # ── section 3: raw pivots from pullbacks ───────────────────────────
        raw = None
        if not inside:
            if ext_px is None:
                ext_px = c.h if seek > 0 else c.l
                ext_t = c.t
                ext_opp = c.l if seek > 0 else c.h
            elif seek > 0:
                if c.h > ext_px:
                    ext_px, ext_t, ext_opp = c.h, c.t, c.l
                if eng.confirm(9, ext_opp, False, eng.mode_pb, False):
                    raw = (True, ext_px, ext_t)
                    seek, ext_px, ext_t, ext_opp = -1, c.l, c.t, c.h
            else:
                if c.l < ext_px:
                    ext_px, ext_t, ext_opp = c.l, c.t, c.h
                if eng.confirm(9, ext_opp, True, eng.mode_pb, False):
                    raw = (False, ext_px, ext_t)
                    seek, ext_px, ext_t, ext_opp = 1, c.h, c.t, c.l

        step(eng, deep, raw)
        p1 = c1.feed(*raw) if raw else None
        step(eng, intl, p1)
        p2 = c2.feed(*p1) if p1 else None
        step(eng, main, p2)

    return eng, deep, intl, main, n_inside


def stats(cs, d, near=0.25):
    """The reference's six rates, reproduced.

    TWO DEFINITIONS MATTER AND ONE OF THEM I GOT WRONG FIRST TIME.

    "Touch" means price reached the level — a wick is enough. That is the right
    reading for the IDM rows, which ask which level price got to first, and
    those rows land on the reference almost exactly.

    "Break" does NOT mean touch. It means the structural break actually
    confirmed under the chosen breakout mode, which on Body & Sweep is far
    rarer than reaching the price. Scoring a touch as a break put 77.8% where
    the reference has 33.3% — it was measuring how often price arrives, not how
    often it gets through.

    A level is also armed EACH TIME IT CHANGES, not once per inducement cycle:
    the pinned BOS candidate moves with every new pullback, so one cycle can
    present several different levels to be near.
    """
    ev = {t: k for k, t, _, _ in d.events}
    r = dict(idm=0, idm_bos=0, idm_ch=0,
             bn=0, bn_brk=0, bn_opp=0, cn=0, cn_brk=0, cn_opp=0)
    for a in d.arms:
        bos, ch, bull = a["bos"], a["ch"], a["bias"] > 0
        if bos is None or ch is None or abs(bos - ch) <= 0:
            continue
        span = abs(bos - ch)
        r["idm"] += 1
        hit = None
        nb = nc = False
        for c in cs[a["i"] + 1:]:
            tb = c.h >= bos if bull else c.l <= bos
            tc = c.l <= ch if bull else c.h >= ch
            if hit is None and (tb or tc):
                hit = 1
                r["idm_bos" if tb else "idm_ch"] += 1
            # A CONFIRMED break, read off the engine's own event stream rather
            # than inferred from price touching the level.
            brk = ev.get(c.t)
            inB = (c.h >= bos - span * near if bull
                   else c.l <= bos + span * near)
            inC = (c.l <= ch + span * near if bull
                   else c.h >= ch - span * near)
            if not nb and inB:
                nb, r["bn"] = True, r["bn"] + 1
            if not nc and inC:
                nc, r["cn"] = True, r["cn"] + 1
            # RE-ARMABLE. Scored once per APPROACH, not once per inducement
            # cycle: price can leave the band and come back several times
            # before the level resolves. This is what lets the count exceed the
            # number of cycles, which the reference's does — 36 and 39 against
            # its own 23 inducements — and a per-cycle counter cannot.
            if nb:
                if brk == "BOS":
                    r["bn_brk"] += 1
                    nb = False
                elif tc:
                    r["bn_opp"] += 1
                    nb = False
            if nc:
                if brk == "CHoCH":
                    r["cn_brk"] += 1
                    nc = False
                elif tb:
                    r["cn_opp"] += 1
                    nc = False
            if brk in ("BOS", "CHoCH"):
                break
    return r


def show_stats(r, label):
    def line(name, tot, cnt):
        pc = 100.0 * cnt / tot if tot else 0.0
        print(f"  {name:<26}{tot:>6}{cnt:>7}{pc:>8.1f}%")
    print(f"\n  {label}")
    print(f"  {'statistic':<26}{'Total':>6}{'Count':>7}{'Rate':>9}")
    line("IDM -> BOS touch",        r["idm"], r["idm_bos"])
    line("IDM -> Choch touch",      r["idm"], r["idm_ch"])
    line("BOS near -> Opp PB",      r["bn"],  r["bn_opp"])
    line("BOS near -> BOS break",   r["bn"],  r["bn_brk"])
    line("Choch near -> Opp PB",    r["cn"],  r["cn_opp"])
    line("Choch near -> Choch brk", r["cn"],  r["cn_brk"])


def report(sym, tf, cs, deep, intl, main, n_inside):
    print(f"LIT ENGINE — {sym} {tf}, {len(cs)} bars "
          f"({ts(cs[0].t)} -> {ts(cs[-1].t)})")
    print(f"inside bars: {n_inside} ({n_inside / len(cs):.0%} of the series "
          f"ignored by structure)\n")
    print(f"  {'degree':<16}{'IDM':>6}{'BOS':>6}{'CHoCH':>7}{'trap':>6}"
          f"{'bias':>8}{'  live levels'}")
    for d, name in ((main, "main"), (intl, "internal"), (deep, "deep")):
        k = {x: sum(1 for e in d.events if e[0] == x)
             for x in ("IDM", "BOS", "CHoCH", "trap")}
        live = []
        if d.idm is not None:
            live.append(f"IDM {d.idm:.2f}{'✓' if d.idm_taken else ''}")
        if d.bos is not None:
            live.append(f"BOS {d.bos:.2f}")
        if d.ch is not None:
            live.append(f"CH {d.ch:.2f}")
        print(f"  {name:<16}{k['IDM']:>6}{k['BOS']:>6}{k['CHoCH']:>7}"
              f"{k['trap']:>6}"
              f"{('bull' if d.bias > 0 else 'bear' if d.bias < 0 else '-'):>8}"
              f"  {', '.join(live) if live else '—'}")

    print(f"\n  last price {cs[-1].c:.2f}")
    for d, name in ((main, "main"), (intl, "internal"), (deep, "deep")):
        print(f"\n  -- {name} events, last 8 " + "-" * 40)
        for kind, t, px, bias in d.events[-8:]:
            print(f"     {ts(t)}  {kind:<6}{px:>10.2f}  "
                  f"{'bull' if bias > 0 else 'bear'}")


async def main():
    sym = sys.argv[1] if len(sys.argv) > 1 else "ZEC_USDT"
    tf = sys.argv[2] if len(sys.argv) > 2 else "Min15"
    async with aiohttp.ClientSession() as s:
        cs = await fetch_candles(s, sym, tf)
    if not cs:
        print("no candles")
        return
    eng, deep, intl, main_, n_inside = run(cs)
    report(sym, tf, cs, deep, intl, main_, n_inside)
    print("\n" + "=" * 60)
    print("REFERENCE, ZEC 15m:  IDM 23 (56.5/43.5)   "
          "BOS near 36 (66.7/33.3)   Choch near 39 (79.5/20.5)")
    for d, nm in ((deep, "deep"), (intl, "internal"), (main_, "main")):
        show_stats(stats(cs, d), f"{nm} degree")


if __name__ == "__main__":
    asyncio.run(main())
