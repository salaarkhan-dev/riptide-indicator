"""ENTRY VARIANT 4 — the obstacle check, and zone classification.

The last two untested source filters. Everything else has been measured:

    Stage A   chase the IDM break        no stop distance works at all
    Variant 2 retrace to zone            -0.46R
    + FVG     [SRC Ch.14]                -0.11R   armed% 33% -> 55%
    + SCOB    [SRC Ch.16]                -0.085R  gross -0.016 -> +0.10

Baseline here is Variant 3's best arm: FVG zones only, SCOB shadow confirmation,
stop at the zone's far edge, exit at BOS.

1. THE OBSTACLE CHECK  [SRC Ch.18]

    "Before entry, Index Algo also checks whether the path from Entry Price to
     Active Price is clear of meaningful structural obstacles. These may
     include: BOS levels, Opposing Pullbacks, Zones that have changed nature
     after a break, Other relevant broken structural levels. If Active Price is
     invalid or a structural obstacle blocks the path toward it, the setup is
     rejected EVEN IF SCOB HAS BEEN CONFIRMED."

  This is the one filter in the whole source with no §72 counterpart, and the
  design flagged it as the most likely to change a distribution rather than
  shave it - it removes setups that are structurally fine but have no room to
  pay. It is also the only filter so far that can reject a trade for a reason
  unrelated to the zone's own quality.

2. ZONE CLASSIFICATION  [SRC Ch.15]

  Decisional  a still-valid pullback carrying an FVG, born at the IDM break.
              That is every zone tested so far.
  Extreme     "the last defensive point of the current market structure. After
              BOS is broken and Choch is formed, the final valid high or low of
              the PRIOR structure." A different object from "the deepest zone
              in this leg" - it is created BY THE FLIP, in the new direction.

  Breaker and Flip are NOT built. Both require an Extreme to be broken with a
  Jump, so they are a chain that needs Extreme to work first, and building them
  before that is exactly the mistake this project keeps refusing to make.

A NOTE ON WHAT WOULD COUNT. The rank split died at scale and the Min30 cell was
not claimed. For either of these to be a finding it has to hold at n in the
hundreds, and the obstacle check has to improve what REMAINS - not merely
remove trades. A filter that removes setups without lifting the remainder is
pure cost.

    PYTHONPATH=. RIPTIDE_DEEP_CACHE=/tmp/deep python3 research/lit_entry4.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import statistics                                       # noqa: E402

import aiohttp                                          # noqa: E402

from research.deep import load_universe                 # noqa: E402
import research.lit_v3 as L                             # noqa: E402

COMMISSION = 0.0005
MIN_RR = 0.5
MAX_WAIT = 400
SCOB_WAIT = 12


class Zone:
    def __init__(self, ev, bornBar, fvg=False, kind="decisional"):
        self.kind = kind
        self.fvg = fvg
        self.dir = ev["dir"]
        self.top = max(ev["px"], ev["edge"])
        self.bot = min(ev["px"], ev["edge"])
        self.born = bornBar
        self.dead = False
        self.inside = False
        self.since = 0
        self.scobLvl = None

    def near(self):
        return self.top if self.dir > 0 else self.bot

    def far(self):
        return self.bot if self.dir > 0 else self.top

    def touched(self, h, l):
        return l <= self.top and h >= self.bot

    def feed(self, o, h, l, c):
        """SCOB shadow mode - Variant 3's best arm."""
        up = self.dir > 0
        entry = None
        if self.scobLvl is not None:
            if (h > self.scobLvl) if up else (l < self.scobLvl):
                entry = c
        if (c < o) if up else (c > o):
            self.scobLvl = h if up else l
        return entry


class Trade:
    def __init__(self, z, i, entry, stop, bos):
        self.kind = z.kind
        self.dir = z.dir
        self.entry = entry
        self.bos = bos
        self.stop0 = stop
        self.risk = abs(entry - stop)
        self.stop = stop
        self.armed = False
        self.rejected = False
        self.exitPx = self.why = None
        cost = entry * COMMISSION * 2
        self.active = (entry + MIN_RR * self.risk + cost) if self.dir > 0 \
            else (entry - MIN_RR * self.risk - cost)

    def ok(self):
        if self.risk <= 0:
            return False
        up = self.dir > 0
        if (self.stop0 >= self.entry) if up else (self.stop0 <= self.entry):
            return False
        return (self.bos > self.entry) if up else (self.bos < self.entry)

    def step(self, h, l):
        up = self.dir > 0
        if (l <= self.stop) if up else (h >= self.stop):
            self.exitPx, self.why = self.stop, "stop"
            return True
        if (h >= self.bos) if up else (l <= self.bos):
            self.exitPx, self.why = self.bos, "bos"
            self.armed = True
            return True
        if not self.armed:
            if (h >= self.active) if up else (l <= self.active):
                self.armed = True
        return False

    def r(self):
        d = (self.exitPx - self.entry) if self.dir > 0 \
            else (self.entry - self.exitPx)
        return d / self.risk - (self.entry * COMMISSION * 2) / self.risk


def blocked(t, obstacles):
    """[SRC Ch.18] Is anything structural sitting between the entry and Active
    Price? Strictly between - a level AT either end is not in the path."""
    lo, hi = min(t.entry, t.active), max(t.entry, t.active)
    for px in obstacles:
        if px is not None and lo < px < hi:
            return True
    return False


def build(pending, dirn, bar):
    """[SRC Ch.14] Consecutive pullbacks that do not overlap left a gap."""
    same = [p for p in pending if p["dir"] == dirn]
    out = []
    for j, pe in enumerate(same):
        lo, hi = min(pe["px"], pe["edge"]), max(pe["px"], pe["edge"])
        gap = 0.0
        if j + 1 < len(same):
            nx = same[j + 1]
            nlo, nhi = min(nx["px"], nx["edge"]), max(nx["px"], nx["edge"])
            gap = (nlo - hi) if nlo > hi else ((lo - nhi) if nhi < lo else 0.0)
        if gap > 0:
            out.append(Zone(pe, bar, fvg=True))
    return out


def run(cs, events, useObstacle, useExtreme, tagOnly=False,
        obsBos=True):
    byBar = {}
    for e in events:
        byBar.setdefault(e["bar"], []).append(e)
    pending, zones, live = [], [], None
    broken = []
    bos = choch = None
    lastPb = None
    out = []
    st = dict(touched=0, taken=0, rejected=0, extremeBorn=0)

    for i in range(len(cs)):
        k = cs[i]
        for e in byBar.get(i, ()):
            kd = e["kind"]
            if kd == "pb":
                pending.append(e)
                lastPb = e
            elif kd == "idm_break":
                bos, choch = e["bos"], e["choch"]
                zones.extend(build(pending, e["dir"], i))
                pending = []
            elif kd == "bos_break":
                # [SRC Ch.22] A broken level changes nature and leaves a
                # "Breakout Zone" behind - it stays an obstacle afterwards.
                if e.get("bos") is not None:
                    broken.append((i, e["bos"]))
                zones, pending = [], []
            elif kd == "choch_break":
                # [SRC Ch.15] EXTREME. The flip is what creates it: the prior
                # structure's final valid extreme becomes the last defensive
                # point, now facing the NEW direction.
                if e.get("choch") is not None:
                    broken.append((i, e["choch"]))
                if useExtreme and lastPb is not None:
                    z = Zone(lastPb, i, fvg=True, kind="extreme")
                    z.dir = e["dir"]
                    zones = [z]
                    st["extremeBorn"] += 1
                else:
                    zones = []
                pending = []

        if live is not None and live.step(k.h, k.l):
            out.append(live)
            live = None

        if live is None and zones:
            alive = []
            for z in zones:
                if i - z.born > MAX_WAIT or z.dead:
                    continue
                if not z.touched(k.h, k.l) and not z.inside:
                    alive.append(z)
                    continue
                if not z.inside:
                    z.inside, z.since = True, i
                    st["touched"] += 1
                px = z.feed(k.o, k.h, k.l, k.c)
                if px is not None:
                    z.dead = True
                    t = Trade(z, i, px, z.far(), bos)
                    if not t.ok():
                        continue
                    if useObstacle:
                        # [SRC Ch.18/Ch.22] The four named obstacle types:
                        # BOS level, valid OPPOSITE pullback, Breakout Zone
                        # (a broken level, which changed nature), and other
                        # relevant broken structural levels.
                        obs = ([bos] if obsBos else []) + [choch]
                        obs += [o.near() for o in zones if o is not z]
                        obs += [p["px"] for p in pending if p["dir"] != t.dir]
                        obs += [px for b, px in broken if i - b <= MAX_WAIT]
                        if blocked(t, obs):
                            st["rejected"] += 1
                            # tagOnly: take it anyway, but MARK it. This is the
                            # only way to compare the rejected set against the
                            # kept set without the two arms competing for
                            # different trade slots.
                            if not tagOnly:
                                continue
                            t.rejected = True
                    if live is None:
                        live = t
                        st["taken"] += 1
                    continue
                if i - z.since > SCOB_WAIT:
                    z.dead = True
                    continue
                alive.append(z)
            zones = alive

    if live is not None:
        live.exitPx, live.why = cs[-1].c, "open"
        out.append(live)
    return out, st


def report(name, ts):
    if len(ts) < 20:
        print(f"  {name:<28}{len(ts):>6}   too few to read")
        return None
    rs = [t.r() for t in ts]
    w = [r for r in rs if r > 0]
    exp = statistics.fmean(rs)
    gross = statistics.fmean(
        [r + (t.entry * COMMISSION * 2) / t.risk for r, t in zip(rs, ts)])
    print(f"  {name:<28}{len(ts):>6}{100 * len(w) / len(ts):>8.1f}%"
          f"{exp:>9.3f}{gross:>9.3f}"
          f"{(statistics.fmean(w) if w else 0):>7.2f}"
          f"{(statistics.fmean([r for r in rs if r <= 0]) if len(w) < len(rs) else 0):>7.2f}")
    return exp


SYMS = ["ZEC_USDT", "BTC_USDT", "ETH_USDT", "SOL_USDT", "ONDO_USDT",
        "LINK_USDT", "AVAX_USDT", "DOGE_USDT", "XRP_USDT", "ADA_USDT",
        "TON_USDT", "NEAR_USDT", "BNB_USDT", "LTC_USDT", "DOT_USDT",
        "ATOM_USDT", "FIL_USDT", "APT_USDT", "ARB_USDT", "OP_USDT",
        "INJ_USDT", "SUI_USDT", "TIA_USDT", "SEI_USDT", "RUNE_USDT",
        "AAVE_USDT", "UNI_USDT", "ETC_USDT", "BCH_USDT", "TRX_USDT"]


async def main():
    eng = {}
    async with aiohttp.ClientSession() as sess:
        for tf in ("Min15", "Min30", "Min60"):
            cs = await load_universe(sess, SYMS, tf, 120, min_bars=2000)
            for sym, k in cs.items():
                if len(k) >= 500:
                    m, _i, _d, _g = L.engine(k)
                    eng[(tf, sym)] = (k, m.events)
            print(f"  loaded {tf}: {len(cs)} symbols")

    print("\nENTRY VARIANT 4 - obstacle check and zone classification")
    print("Baseline: FVG zones, SCOB shadow, zone SL, exit at BOS "
          "(Variant 3's best arm)\n")

    arms = [
        ("baseline (V3 best)", False, False),
        ("+ obstacle check", True, False),
        ("+ Extreme zones", False, True),
        ("+ both", True, True),
    ]
    print(f"{'=' * 88}")
    print(f"  {'arm':<28}{'n':>6}{'win%':>8}{'NET R':>9}{'GROSS R':>9}"
          f"{'avgW':>7}{'avgL':>7}")
    print(f"{'=' * 88}")
    keep = {}
    for nm, ob, ex in arms:
        ts = []
        agg = dict(touched=0, taken=0, rejected=0, extremeBorn=0)
        for (k, ev) in eng.values():
            t, s = run(k, ev, ob, ex)
            ts.extend(t)
            for key in agg:
                agg[key] += s[key]
        keep[nm] = ts
        report(nm, ts)
        if ob:
            print(f"    (rejected by obstacle: {agg['rejected']} of "
                  f"{agg['rejected'] + agg['taken']} confirmed)")
        if ex:
            print(f"    (Extreme zones born: {agg['extremeBorn']})")

    # The direct test. Run the obstacle check but TAKE the rejects anyway, so
    # kept and rejected come from ONE run and cannot differ merely because the
    # two arms filled different trade slots.
    tag = []
    for (k, ev) in eng.values():
        t, _s = run(k, ev, True, False, tagOnly=True)
        tag.extend(t)
    print(f"\n{'=' * 88}\n  OBSTACLE CHECK - KEPT vs REJECTED, one run"
          f"\n{'=' * 88}")
    report("  kept (path clear)", [t for t in tag if not t.rejected])
    report("  REJECTED (path blocked)", [t for t in tag if t.rejected])
    # Is the filter really a proxy for TARGET DISTANCE? If the rejected trades
    # simply have a nearer BOS, their high hit rate is mechanical - and it is
    # an artefact of OUR exit rule, not a verdict on the source's filter.
    for lbl, sel in (("kept", False), ("rejected", True)):
        rr = [abs(t.bos - t.entry) / t.risk for t in tag if t.rejected is sel]
        if rr:
            rr.sort()
            print(f"    {lbl:<22} target distance: median "
                  f"{rr[len(rr) // 2]:.2f}R   mean {statistics.fmean(rr):.2f}R")

    # BOS is BOTH our exit and an obstacle, so "blocked" is close to a
    # restatement of "the target is nearer than 0.5R". Drop BOS from the
    # obstacle set to see what the NON-circular obstacles do on their own.
    tag2 = []
    for (k, ev) in eng.values():
        t, _s = run(k, ev, True, False, tagOnly=True, obsBos=False)
        tag2.extend(t)
    print(f"\n{'=' * 88}\n  OBSTACLE CHECK WITHOUT BOS - the non-circular part"
          f"\n{'=' * 88}")
    report("  kept (path clear)", [t for t in tag2 if not t.rejected])
    report("  REJECTED (path blocked)", [t for t in tag2 if t.rejected])

    base = keep["baseline (V3 best)"]
    ext = keep["+ Extreme zones"]
    if ext:
        print(f"\n{'=' * 88}\n  BY ZONE KIND  [SRC Ch.15]\n{'=' * 88}")
        for kd in ("decisional", "extreme"):
            report(f"  {kd}", [t for t in ext if t.kind == kd])

    print(f"\n{'=' * 88}\n  READ\n{'=' * 88}")
    print("  The obstacle check must improve WHAT REMAINS, not merely remove")
    print("  trades. Compare its NET against the baseline's: if n falls and")
    print("  NET does not rise, the rejected set was no worse than the kept")
    print("  set and the filter is pure cost.")
    print()
    print("  GROSS is the column that says whether there is anything here at")
    print("  all. Variant 3 left it at +0.10 on the best arm and roughly zero")
    print("  everywhere else, which is why none of this has been claimed.")
    del base


if __name__ == "__main__":
    asyncio.run(main())
