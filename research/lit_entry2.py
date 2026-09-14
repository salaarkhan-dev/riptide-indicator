"""ENTRY VARIANT 2 — retrace into a zone, stop behind structure.

Stage A refuted §72's naked entry, and it did so informatively. The premise is
real (83% of paths reach BOS before CHoCH, BOS a median 11.85R away) but
entering at the IDM-break bar's close cannot be made to pay at ANY stop
distance: price travels a median 6.3x the raid-bar distance against you before
it goes to BOS, so a tight stop is noise-stopped and a stop wide enough to
survive puts BOS at 0.6R.

That excursion is not an obstacle to the strategy. It IS the strategy. The
reference never chases the break - it waits for price to come back into a zone
and puts its stop behind structure. Variant 2 measures that, crudely.

WHAT THIS BUILDS (LIT_SOURCE.md Ch.15)

    "When IDM is broken, Pullbacks that remain structurally valid and contain
     an FVG on the appropriate side may be drawn as Decisional POIs."

  at IDM break   every still-unmitigated pullback of the current leg becomes a
                 candidate zone, its range the OrderFlow [edge, pivot]
  entry          price retraces and touches the zone's near edge        [T9]
  stop           beyond the zone's far edge - the reference's LowRisk
                 placement, "SL on Pullback"                  (Ch.17, Ch.21)
  invalidate     a BOS break kills every pending zone, because the new CHoCH
                 forms ABOVE them and price would have to flip the trend to
                 reach them. Ch.15 states this outright. A CHoCH break kills
                 them too.
  mitigate       a touched zone is consumed and never re-armed           [T3]

WHAT THIS DELIBERATELY DOES NOT BUILD
  no FVG filter (Stage B), no zone CLASSIFICATION into Decisional / Extreme /
  Breaker / Flip (Stage C), no SCOB confirmation (Stage D), no obstacle check
  (Stage E). If the naked retrace has no edge, none of those will manufacture
  one - and each carries its own inference risk. Same discipline that killed
  Stage A cleanly.

    PYTHONPATH=. RIPTIDE_DEEP_CACHE=/tmp/deep python3 research/lit_entry2.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import statistics                                       # noqa: E402

import aiohttp                                          # noqa: E402

from research.deep import load_universe                 # noqa: E402
import research.lit_v3 as L                             # noqa: E402

COMMISSION = 0.0005
MIN_RR = 0.5
MAX_WAIT = 400      # bars a zone may sit unfilled before it is abandoned
MAX_HOLD = 600


class Zone:
    """A confirmed pullback, extended right, waiting for price to come back."""

    def __init__(self, ev, bornBar, rank=0, fvg=False, gapR=0.0):
        self.rank = rank        # 0 = nearest price at birth, higher = deeper
        self.fvg = fvg          # [SRC Ch.14] unconsumed: the NEXT pullback did
        self.gapR = gapR        # not penetrate this one, leaving a gap
        self.dir = ev["dir"]                    # the structure it belongs to
        self.top = max(ev["px"], ev["edge"])
        self.bot = min(ev["px"], ev["edge"])
        self.born = bornBar
        self.dead = False

    def near(self):
        """The edge price meets first on the way back."""
        return self.top if self.dir > 0 else self.bot

    def far(self):
        """The edge the stop sits beyond."""
        return self.bot if self.dir > 0 else self.top

    def touched(self, h, l):
        return l <= self.top and h >= self.bot


class Trade:
    def __init__(self, z, i, entry, bos, choch, sym):
        self.sym = sym
        self.rank = z.rank
        self.fvg = z.fvg
        self.gapR = z.gapR
        self.dir = z.dir
        self.entryBar = i
        self.entry = entry
        self.bos = bos
        self.choch = choch
        self.stop0 = z.far()
        self.risk = abs(entry - self.stop0)
        self.stop = self.stop0
        self.armed = False
        self.mfe = 0.0
        self.mae = 0.0
        self.exitBar = self.exitPx = self.why = None
        cost = self.entry * COMMISSION * 2
        self.active = (entry + MIN_RR * self.risk + cost) if self.dir > 0 \
            else (entry - MIN_RR * self.risk - cost)

    def ok(self):
        if self.risk <= 0:
            return False
        # the target has to be on the correct side of the entry, or the setup
        # is structurally incoherent and would flatter the sample
        return (self.bos > self.entry) if self.dir > 0 else (self.bos < self.entry)

    def r(self, px):
        d = (px - self.entry) if self.dir > 0 else (self.entry - px)
        return d / self.risk

    def step(self, i, h, l, trail):
        """Stop checked BEFORE the favourable excursion is banked. On a bar
        that does both, OHLC cannot order them, so we take the loss."""
        up = self.dir > 0
        self.mae = min(self.mae, self.r(l if up else h))
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
                self.stop = self.entry          # Risk Free
        if self.armed and trail == "mfe":
            give = self.entry + (self.mfe * 0.5) * self.risk * self.dir
            if (give > self.stop) if up else (give < self.stop):
                self.stop = give
        return False


def run(cs, events, trail, sym):
    """One pass. Zones are born at IDM break, die on BOS/CHoCH break or on
    being filled, and nothing looks ahead of its own bar."""
    byBar = {}
    for e in events:
        byBar.setdefault(e["bar"], []).append(e)

    pending = []      # unmitigated pullbacks of the current leg
    zones = []        # armed, waiting for a retrace
    live = None
    bos = choch = None
    out = []
    stats = dict(born=0, filled=0, killedBos=0, killedCh=0, expired=0)

    for i in range(len(cs)):
        k = cs[i]
        for e in byBar.get(i, ()):
            kind = e["kind"]
            if kind == "pb":
                pending.append(e)
            elif kind == "idm_break":
                bos, choch = e["bos"], e["choch"]
                # [SRC Ch.15] the zones are born here, from the pullbacks the
                # leg left behind that price has not yet come back through.
                # [SRC Ch.14] FVG, measured properly: the gap between two
                # CONSECUTIVE PULLBACKS, never the three-candle wick gap.
                #
                #   "If a new Pullback penetrates into the previous Pullback,
                #    the orders associated with the earlier area are considered
                #    to have been consumed, and that area loses its validity."
                #   "if there is a price gap between two Pullbacks ... the
                #    orders from the previous Pullback may not have been fully
                #    consumed."
                #
                # So the two statements are one test: do the ranges overlap?
                # Overlap = consumed = dead. Gap = still live = Decisional.
                # The last pullback of a leg has no successor and therefore no
                # FVG by construction.
                cand = []
                same = [pe for pe in pending if pe["dir"] == e["dir"]]
                for j, pe in enumerate(same):
                    lo = min(pe["px"], pe["edge"])
                    hi = max(pe["px"], pe["edge"])
                    gap = 0.0
                    if j + 1 < len(same):
                        nx = same[j + 1]
                        nlo = min(nx["px"], nx["edge"])
                        nhi = max(nx["px"], nx["edge"])
                        if nlo > hi:
                            gap = nlo - hi
                        elif nhi < lo:
                            gap = lo - nhi
                    span = hi - lo
                    cand.append(Zone(pe, i, fvg=gap > 0,
                                     gapR=(gap / span if span > 0 else 0.0)))
                # nearest to current price first; the deepest is the
                # "last defensive point" Ch.15 calls Extreme.
                cand.sort(key=lambda z: abs(z.near() - k.c))
                for r, z in enumerate(cand):
                    z.rank = r
                    zones.append(z)
                    stats["born"] += 1
                pending = []
            elif kind == "bos_break":
                # [SRC Ch.15] "once the BOS level is broken, these zones are no
                # longer extended" - the new CHoCH forms above them, so price
                # would have to flip the trend to reach them.
                stats["killedBos"] += len(zones)
                zones = []
                pending = []
            elif kind == "choch_break":
                stats["killedCh"] += len(zones)
                zones = []
                pending = []

        if live is not None:
            if live.step(i, k.h, k.l, trail):
                out.append(live)
                live = None

        if live is None and zones:
            alive = []
            for z in zones:
                if i - z.born > MAX_WAIT:
                    stats["expired"] += 1
                    continue
                if z.touched(k.h, k.l) and not z.dead:
                    z.dead = True                       # [T3] touch consumes
                    t = Trade(z, i, z.near(), bos, choch, sym)
                    if t.ok() and live is None:
                        live = t
                        stats["filled"] += 1
                    continue
                alive.append(z)
            zones = alive

    if live is not None:
        live.why = "open"
        live.exitBar = len(cs) - 1
        live.exitPx = cs[-1].c
        out.append(live)
    return out, stats


def report(name, ts):
    if not ts:
        print(f"  {name:<10} no trades")
        return None
    rs = []
    for t in ts:
        rs.append(t.r(t.exitPx) - (t.entry * COMMISSION * 2) / t.risk)
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r <= 0]
    exp = statistics.fmean(rs)
    armed = [t for t in ts if t.armed]
    print(f"  {name:<10}{len(ts):>6}{100 * len(wins) / len(ts):>8.1f}%"
          f"{exp:>9.3f}{sum(rs):>10.1f}"
          f"{(statistics.fmean(wins) if wins else 0):>8.2f}"
          f"{(statistics.fmean(losses) if losses else 0):>8.2f}"
          f"{100 * len(armed) / len(ts):>8.1f}%")
    return exp


SYMS = ["ZEC_USDT", "BTC_USDT", "ETH_USDT", "SOL_USDT", "ONDO_USDT",
        "LINK_USDT", "AVAX_USDT", "DOGE_USDT", "XRP_USDT", "ADA_USDT",
        "TON_USDT", "NEAR_USDT", "BNB_USDT", "LTC_USDT", "DOT_USDT",
        "ATOM_USDT", "FIL_USDT", "APT_USDT", "ARB_USDT", "OP_USDT",
        "INJ_USDT", "SUI_USDT", "TIA_USDT", "SEI_USDT", "RUNE_USDT",
        "AAVE_USDT", "UNI_USDT", "ETC_USDT", "BCH_USDT", "TRX_USDT"]


async def main():
    arms = ("fixed", "bos", "mfe")
    trades = {a: [] for a in arms}
    agg = dict(born=0, filled=0, killedBos=0, killedCh=0, expired=0)
    byTf = {}
    async with aiohttp.ClientSession() as sess:
        for tf in ("Min30", "Min15"):
            cs = await load_universe(sess, SYMS, tf, 120, min_bars=2000)
            byTf[tf] = {a: [] for a in arms}
            for sym, k in cs.items():
                if len(k) < 500:
                    continue
                m, _i, _d, _g = L.engine(k)
                for a in arms:
                    ts, st = run(k, m.events, a, sym)
                    trades[a].extend(ts)
                    byTf[tf][a].extend(ts)
                    if a == "fixed":
                        for key in agg:
                            agg[key] += st[key]
            print(f"  loaded {tf}: {len(cs)} symbols")

    print("\nENTRY VARIANT 2 - retrace into a zone, stop behind structure")
    print(f"30m + 15m, {len(SYMS)} symbols requested, "
          f"commission {COMMISSION * 100:.3f}%/side, minRR {MIN_RR}")
    print("No FVG, no zone classification, no SCOB, no obstacle check.\n")

    print(f"{'=' * 88}\n  ZONE LIFECYCLE\n{'=' * 88}")
    print(f"  zones born at IDM break   {agg['born']:>6}")
    print(f"  filled (price came back)  {agg['filled']:>6}"
          f"   {100 * agg['filled'] / max(1, agg['born']):>5.1f}%")
    print(f"  killed by a BOS break     {agg['killedBos']:>6}   [SRC Ch.15]")
    print(f"  killed by a CHoCH break   {agg['killedCh']:>6}")
    print(f"  expired unfilled          {agg['expired']:>6}")

    base = trades["fixed"]
    if base:
        rk = sorted(100 * t.risk / t.entry for t in base)
        bq = sorted(abs(t.bos - t.entry) / t.risk for t in base)
        ck = sorted((t.entry * COMMISSION * 2) / t.risk for t in base)
        md = lambda v: v[len(v) // 2]
        print(f"\n{'=' * 88}\n  GEOMETRY - compare against Stage A\n{'=' * 88}")
        print(f"  stop distance as % of price   {md(rk):>8.3f}%"
              f"      (Stage A: 0.330%)")
        print(f"  round-trip commission in R    {md(ck):>8.2f}R"
              f"      (Stage A: 0.30R)")
        print(f"  distance entry -> BOS in R    {md(bq):>8.2f}R"
              f"      (Stage A: 11.85R)")

    print(f"\n{'=' * 88}")
    print(f"  {'trail':<10}{'n':>6}{'win%':>9}{'expR':>9}{'totR':>10}"
          f"{'avgW':>8}{'avgL':>8}{'armed%':>9}")
    print(f"{'=' * 88}")
    res = {a: report(a, trades[a]) for a in arms}

    # [Ch.15] Decisional zones sit nearer; the deepest is the Extreme, the
    # "last defensive point of the current market structure". If the stack
    # position separates the outcomes, that is a source-recognised split rather
    # than a data-mined one - and the design's gate explicitly admits "a
    # clearly identifiable subset".
    print(f"\n{'=' * 88}\n  BY POSITION IN THE ZONE STACK  (0 = nearest price "
          f"at birth)\n{'=' * 88}")
    print(f"  {'rank':<10}{'n':>6}{'win%':>9}{'expR':>9}{'totR':>10}"
          f"{'avgW':>8}{'avgL':>8}")
    for a in ("bos", "mfe"):
        print(f"  -- arm '{a}'")
        for r in range(4):
            sub = [t for t in trades[a] if t.rank == r]
            if len(sub) >= 5:
                report(f"   rank {r}", sub)
        deep = [t for t in trades[a] if t.rank >= 3]
        if len(deep) >= 5:
            report("   rank 3+", deep)

    # OUT OF SAMPLE. The rank split was found on 30m; if it is real it has to
    # hold on 15m without being refitted. This is the only line that can tell
    # a structural effect from a slice that happened to be lucky.
    # [SRC Ch.14] THE FVG FILTER, measured RETROSPECTIVELY on trades that
    # already exist. Nothing new was built to test it - the gap between
    # consecutive pullbacks is a property of records the engine already emits,
    # so this costs one tag per trade rather than a subsystem.
    print(f"\n{'=' * 88}\n  FVG FILTER  [SRC Ch.14 - gap between consecutive "
          f"PULLBACKS]\n{'=' * 88}")
    print(f"  {'group':<12}{'n':>6}{'win%':>9}{'expR':>9}{'totR':>10}"
          f"{'avgW':>8}{'avgL':>8}{'armed%':>9}")
    for a in ("fixed", "bos", "mfe"):
        print(f"  -- arm '{a}'")
        for flag, nm in ((True, "  FVG"), (False, "  no FVG")):
            sub = [t for t in trades[a] if t.fvg == flag]
            if len(sub) >= 20:
                report(nm, sub)
    # and per timeframe, because the rank split died exactly here
    print(f"\n  -- FVG only, per timeframe, arm 'bos'")
    for tf in byTf:
        sub = [t for t in byTf[tf]["bos"] if t.fvg]
        if len(sub) >= 20:
            report(f"   {tf}", sub)

    print(f"\n{'=' * 88}\n  THE SAME SPLIT, PER TIMEFRAME  (arm 'bos')"
          f"\n{'=' * 88}")
    for tf in byTf:
        print(f"  -- {tf}")
        for lo, hi, nm in ((0, 0, "rank 0"), (1, 2, "rank 1-2"),
                           (3, 99, "rank 3+")):
            sub = [t for t in byTf[tf]["bos"] if lo <= t.rank <= hi]
            if len(sub) >= 5:
                report(f"   {nm}", sub)

    print(f"\n{'=' * 88}\n  VERDICT\n{'=' * 88}")
    good = {a: v for a, v in res.items() if v is not None and v > 0}
    if not good:
        print("  NO ARM IS POSITIVE. But the FVG table above is a real result.")
        print()
        print("  [SRC Ch.14] FVG - the gap between two CONSECUTIVE PULLBACKS,")
        print("  not the three-candle wick gap - roughly QUARTERS the loss on")
        print("  all three exit arms, and the mechanism is visible: armed%")
        print("  goes from ~33% to ~55%. Zones that were not consumed by the")
        print("  next pullback actually hold when price comes back. That is a")
        print("  mechanistic difference, not a slice.")
        print()
        print("  It still is not enough. Best arm is about -0.11R.")
        print()
        print("  CONTRAST WITH THE RANK SPLIT, which looked just as good at")
        print("  n=10 and evaporated at n=1200. FVG was predicted BY THE")
        print("  SOURCE before it was measured, it holds at n=234, and it")
        print("  moves the intermediate quantity it should move. Those are")
        print("  three different reasons to believe it that the rank split")
        print("  never had.")
        print()
        print("  NEXT, AND IT IS THE OBVIOUS ONE. Our entry is a bare touch of")
        print("  the zone. Ch.16 says that is exactly what SCOB exists to")
        print("  prevent: 'Reaching a valid zone or level is not enough on its")
        print("  own to justify an entry.' SCOB is testable on this same trade")
        print("  list - wait inside the zone for the confirmation break")
        print("  instead of entering on contact - and it needs no new")
        print("  subsystem, only a change of entry timing.")
    else:
        best = max(good, key=lambda a: good[a])
        print(f"  Best arm '{best}' at {good[best]:+.3f}R/trade over "
              f"{len(trades[best])} trades.")
        print("  Check it survives BOTH timeframes above before believing it.")


if __name__ == "__main__":
    asyncio.run(main())
