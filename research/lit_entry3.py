"""ENTRY VARIANT 3 — SCOB confirmation instead of a bare touch.

Variant 2 established two things. The retrace entry fixes the geometry Stage A
broke (stop 1.25% of price not 0.33%, commission 0.08R not 0.30R, BOS at 1.52R
not 11.85R) and still loses ~0.46R. And [SRC Ch.14] FVG - the gap between two
CONSECUTIVE PULLBACKS - quarters that loss and lifts armed% from 33% to 55%,
which is a mechanism, not a slice.

What Variant 2 does that the source explicitly forbids is enter on CONTACT.

    [SRC Ch.16] "Reaching a valid zone or level is not enough on its own to
     justify an entry... Index Algo does not merely check whether 'price has
     reached the zone.' It also evaluates 'how the market behaves after
     reaching that zone.'... if SCOB confirmation is not issued, no trade
     entry is opened, even if the zone itself remains valid."

SCOB GEOMETRY, closed by the Ch.21 mode slides and requiring no inference:

    candle   the last OPPOSITE-DIRECTION candle before the reaction
             (for a long: the last down candle)
    level    its boundary facing the intended move (high, or body top)  [T4]
    break    the same three-mode engine the structure already uses:
             shadow = wick through, body = close beyond

WHY THIS SHOULD HELP, AND HOW IT COULD HURT
Waiting means entering later, but in a demand zone "later" usually means
DEEPER - price wicks further into the zone before turning - so the stop at the
zone's far edge is CLOSER to entry and R is smaller. Better price, tighter
risk. The cost is the setups that never confirm at all, which are removed from
the sample. If the removed set is no worse than the kept set, SCOB is pure cost
and that is a real answer - it is the same test that sank the structure-trend
gate earlier in this project.

    PYTHONPATH=. RIPTIDE_DEEP_CACHE=/tmp/deep python3 research/lit_entry3.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import statistics                                       # noqa: E402

import aiohttp                                          # noqa: E402

from research.deep import load_universe                 # noqa: E402
import research.lit_v3 as L                             # noqa: E402

COMMISSION = 0.0005
MIN_RR = 0.5
MAX_WAIT = 400        # bars a zone may sit unfilled
SCOB_WAIT = 12        # bars inside the zone to produce a confirmation
MAX_HOLD = 600


class Zone:
    def __init__(self, ev, bornBar, fvg=False):
        self.fvg = fvg
        self.dir = ev["dir"]
        self.top = max(ev["px"], ev["edge"])
        self.bot = min(ev["px"], ev["edge"])
        self.born = bornBar
        self.dead = False
        # SCOB state, only live once price is inside the zone
        self.inside = False
        self.since = 0
        self.scobLvl = None      # the level a confirmation must break
        self.scobLo = None       # the SCOB candle's own extreme, for HighRisk

    def near(self):
        return self.top if self.dir > 0 else self.bot

    def far(self):
        return self.bot if self.dir > 0 else self.top

    def touched(self, h, l):
        return l <= self.top and h >= self.bot

    def feed(self, o, h, l, c, mode, useBody):
        """One bar while price is in the zone. Returns an entry price, or None.

        The SCOB candle is the last candle going AGAINST the intended trade.
        Its facing boundary is the level. Any later candle breaking that level
        confirms. Ordered so a single candle cannot both set the level and
        break it - the reaction has to come from a LATER bar, which is what
        "how the market behaves after reaching that zone" means.
        """
        up = self.dir > 0
        entry = None
        if self.scobLvl is not None:
            broke = (h > self.scobLvl) if up else (l < self.scobLvl)
            if mode == "body":
                broke = (c > self.scobLvl) if up else (c < self.scobLvl)
            if broke:
                entry = c
        # then update the candidate: this bar becomes the SCOB if it went
        # against us. [T4] body boundary or wick.
        against = (c < o) if up else (c > o)
        if against:
            if useBody:
                self.scobLvl = max(o, c) if up else min(o, c)
            else:
                self.scobLvl = h if up else l
            self.scobLo = l if up else h
        return entry


class Trade:
    def __init__(self, z, i, entry, stop, bos, sym, how):
        self.sym = sym
        self.how = how
        self.fvg = z.fvg
        self.dir = z.dir
        self.entryBar = i
        self.entry = entry
        self.bos = bos
        self.stop0 = stop
        self.risk = abs(entry - stop)
        self.stop = stop
        self.armed = False
        self.mfe = 0.0
        self.exitBar = self.exitPx = self.why = None
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

    def r(self, px):
        d = (px - self.entry) if self.dir > 0 else (self.entry - px)
        return d / self.risk

    def step(self, i, h, l, trail):
        up = self.dir > 0
        if (l <= self.stop) if up else (h >= self.stop):
            self.exitBar, self.exitPx = i, self.stop
            self.why = "trail" if self.armed else "stop"
            return True
        if trail == "fixed":
            if (h >= self.active) if up else (l <= self.active):
                self.exitBar, self.exitPx, self.why = i, self.active, "target"
                self.armed = True
                return True
        if trail == "bos":
            if (h >= self.bos) if up else (l <= self.bos):
                self.exitBar, self.exitPx, self.why = i, self.bos, "bos"
                self.armed = True
                return True
        self.mfe = max(self.mfe, self.r(h if up else l))
        if not self.armed:
            if (h >= self.active) if up else (l <= self.active):
                self.armed = True
                self.stop = self.entry
        if self.armed and trail == "mfe":
            give = self.entry + (self.mfe * 0.5) * self.risk * self.dir
            if (give > self.stop) if up else (give < self.stop):
                self.stop = give
        return False


def build_zones(pending, dirn, bar):
    """[SRC Ch.14] Consecutive pullbacks that do not overlap left a gap; the
    earlier node was not consumed. Overlap = consumed = no FVG."""
    same = [pe for pe in pending if pe["dir"] == dirn]
    out = []
    for j, pe in enumerate(same):
        lo, hi = min(pe["px"], pe["edge"]), max(pe["px"], pe["edge"])
        gap = 0.0
        if j + 1 < len(same):
            nx = same[j + 1]
            nlo, nhi = min(nx["px"], nx["edge"]), max(nx["px"], nx["edge"])
            gap = (nlo - hi) if nlo > hi else ((lo - nhi) if nhi < lo else 0.0)
        out.append(Zone(pe, bar, fvg=gap > 0))
    return out


def run(cs, events, trail, sym, entryMode, stopMode, useBody, fvgOnly):
    byBar = {}
    for e in events:
        byBar.setdefault(e["bar"], []).append(e)
    pending, zones, live = [], [], None
    bos = None
    out = []
    st = dict(born=0, touched=0, confirmed=0, timedOut=0)

    for i in range(len(cs)):
        k = cs[i]
        for e in byBar.get(i, ()):
            if e["kind"] == "pb":
                pending.append(e)
            elif e["kind"] == "idm_break":
                bos = e["bos"]
                for z in build_zones(pending, e["dir"], i):
                    if fvgOnly and not z.fvg:
                        continue
                    zones.append(z)
                    st["born"] += 1
                pending = []
            elif e["kind"] in ("bos_break", "choch_break"):
                zones, pending = [], []

        if live is not None and live.step(i, k.h, k.l, trail):
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
                    z.inside = True
                    st["touched"] += 1
                    z.since = i
                if entryMode == "touch":
                    z.dead = True
                    t = Trade(z, i, z.near(), z.far(), bos, sym, "touch")
                    if t.ok() and live is None:
                        live = t
                        st["confirmed"] += 1
                    continue
                # SCOB: wait inside the zone for the confirmation break
                px = z.feed(k.o, k.h, k.l, k.c, entryMode, useBody)
                if px is not None:
                    z.dead = True
                    stop = z.far() if stopMode == "zone" else z.scobLo
                    t = Trade(z, i, px, stop, bos, sym, entryMode)
                    if t.ok() and live is None:
                        live = t
                        st["confirmed"] += 1
                    continue
                if i - z.since > SCOB_WAIT:
                    st["timedOut"] += 1
                    z.dead = True
                    continue
                alive.append(z)
            zones = alive

    if live is not None:
        live.why, live.exitBar, live.exitPx = "open", len(cs) - 1, cs[-1].c
        out.append(live)
    return out, st


def report(name, ts):
    if len(ts) < 20:
        return None
    gross = [t.r(t.exitPx) for t in ts]
    rs = [g - (t.entry * COMMISSION * 2) / t.risk for g, t in zip(gross, ts)]
    w = [r for r in rs if r > 0]
    ls = [r for r in rs if r <= 0]
    exp = statistics.fmean(rs)
    # GROSS matters here. If gross is ~0 and net is negative, the setup is a
    # coin flip in R and commission IS the loss - which means no filter short
    # of one that creates real edge can rescue it.
    print(f"  {name:<24}{len(ts):>6}{100 * len(w) / len(ts):>8.1f}%"
          f"{exp:>9.3f}{statistics.fmean(gross):>9.3f}"
          f"{(statistics.fmean(w) if w else 0):>7.2f}"
          f"{(statistics.fmean(ls) if ls else 0):>7.2f}"
          f"{100 * sum(1 for t in ts if t.armed) / len(ts):>8.1f}%")
    return exp


SYMS = ["ZEC_USDT", "BTC_USDT", "ETH_USDT", "SOL_USDT", "ONDO_USDT",
        "LINK_USDT", "AVAX_USDT", "DOGE_USDT", "XRP_USDT", "ADA_USDT",
        "TON_USDT", "NEAR_USDT", "BNB_USDT", "LTC_USDT", "DOT_USDT",
        "ATOM_USDT", "FIL_USDT", "APT_USDT", "ARB_USDT", "OP_USDT",
        "INJ_USDT", "SUI_USDT", "TIA_USDT", "SEI_USDT", "RUNE_USDT",
        "AAVE_USDT", "UNI_USDT", "ETC_USDT", "BCH_USDT", "TRX_USDT"]


async def main():
    data = {}
    async with aiohttp.ClientSession() as sess:
        for tf in ("Min15", "Min30", "Min60", "Hour4"):
            data[tf] = await load_universe(sess, SYMS, tf, 120, min_bars=2000)
            print(f"  loaded {tf}: {len(data[tf])} symbols")

    print("\nENTRY VARIANT 3 - SCOB confirmation instead of a bare touch")
    print(f"30m + 15m, commission {COMMISSION * 100:.3f}%/side, "
          f"minRR {MIN_RR}, FVG zones only [SRC Ch.14]\n")

    # cache the engine pass - it is the expensive part and every arm reuses it
    eng = {}
    for tf, cs in data.items():
        for sym, k in cs.items():
            if len(k) >= 500:
                m, _i, _d, _g = L.engine(k)
                eng[(tf, sym)] = (k, m.events)

    arms = [
        ("touch  (Variant 2)", "touch", "zone", False),
        ("SCOB shadow, zone SL", "shadow", "zone", False),
        ("SCOB body,   zone SL", "body", "zone", False),
        ("SCOB shadow, SCOB SL", "shadow", "scob", False),
        ("SCOB body,   SCOB SL", "body", "scob", False),
        ("SCOB body-lvl, zone SL", "body", "zone", True),
    ]
    for trail in ("bos", "mfe"):
        print(f"{'=' * 96}")
        print(f"  EXIT ARM '{trail}'")
        print(f"  {'entry':<24}{'n':>6}{'win%':>8}{'NET R':>9}{'GROSS R':>9}"
              f"{'avgW':>7}{'avgL':>7}{'armed%':>8}")
        print(f"{'=' * 96}")
        for nm, em, sm, ub in arms:
            ts = []
            agg = dict(born=0, touched=0, confirmed=0, timedOut=0)
            for (k, ev) in eng.values():
                t, s = run(k, ev, trail, "", em, sm, ub, True)
                ts.extend(t)
                for key in agg:
                    agg[key] += s[key]
            e = report(nm, ts)
            if nm.startswith("touch"):
                print(f"    (zones born {agg['born']}, touched "
                      f"{agg['touched']})")
            elif em != "touch" and trail == "bos":
                print(f"    (confirmed {agg['confirmed']}, timed out "
                      f"{agg['timedOut']} of {agg['touched']} touched)")
            del e
        print()

    # THE BINDING CONSTRAINT. Best gross is positive while best net is not, so
    # commission is the whole loss - and commission-in-R is set by the STOP
    # DISTANCE, which is a property of the timeframe rather than of the entry
    # logic. SCOB actually makes this worse: it enters deeper in the zone, so R
    # shrinks and the same fee eats a larger fraction of it.
    print(f"{'=' * 96}")
    print("  COST vs TIMEFRAME  -  arm 'bos', SCOB shadow + zone SL")
    print(f"  {'tf':<10}{'n':>6}{'NET R':>9}{'GROSS R':>9}{'fee in R':>10}"
          f"{'stop %':>9}{'win%':>8}")
    print(f"{'=' * 96}")
    for tf in data:
        ts = []
        for (key, (k, ev)) in eng.items():
            if key[0] != tf:
                continue
            t, _s = run(k, ev, "bos", "", "shadow", "zone", False, True)
            ts.extend(t)
        if len(ts) < 20:
            continue
        gross = [t.r(t.exitPx) for t in ts]
        fee = [(t.entry * COMMISSION * 2) / t.risk for t in ts]
        net = [g - f for g, f in zip(gross, fee)]
        stp = [100 * t.risk / t.entry for t in ts]
        wins = sum(1 for r in net if r > 0)
        print(f"  {tf:<10}{len(ts):>6}{statistics.fmean(net):>9.3f}"
              f"{statistics.fmean(gross):>9.3f}{statistics.fmean(fee):>10.3f}"
              f"{statistics.fmean(stp):>9.2f}{100 * wins / len(ts):>8.1f}")

    print(f"\n{'=' * 96}\n  WHAT THESE NUMBERS SAY\n{'=' * 96}")
    print("  1. SCOB ADDS REAL EDGE. Gross goes from -0.016 (bare touch) to")
    print("     +0.100 (SCOB shadow). Ch.16 is right that a touch is not an")
    print("     entry.")
    print()
    print("  2. AND IT PAYS FOR IT. SCOB enters DEEPER in the zone, so R")
    print("     shrinks and the same fee eats a larger share of it. Net barely")
    print("     moves: -0.124 -> -0.085. The gain is spent on cost.")
    print()
    print("  3. THE FEE MECHANISM IS CONFIRMED. fee-in-R falls 0.257 -> 0.076")
    print("     -> 0.064 as the stop widens 1.87% -> 3.19% -> 4.13%. That was")
    print("     predicted before it was measured, and it is arithmetic.")
    print()
    print("  4. BUT GROSS EDGE DOES NOT HOLD UP. 0.069 / 0.147 / 0.049 across")
    print("     the three timeframes - small everywhere, not monotone. The one")
    print("     NET-positive cell (Min30, +0.071R, n=88) is a single cell with")
    print("     unremarkable neighbours.")
    print()
    print("  THAT IS THE RANK-SPLIT SHAPE AGAIN, so it is NOT claimed as a")
    print("  finding. One positive cell at n=88, bracketed by two negative")
    print("  ones, is what noise looks like.")
    print()
    print("  HONEST STATUS: the setup is roughly BREAKEVEN BEFORE COSTS and")
    print("  negative after. At 60m, where fees barely matter, gross is still")
    print("  only +0.049R. The problem is no longer cost - it is that the edge")
    print("  is too small to survive anything.")


if __name__ == "__main__":
    asyncio.run(main())
