"""T6 — what the trailing stop trails.

The last large hole on the trading side, and now the only road left open: the
obstacle check turned out to be untestable under a BOS exit (Variant 4), and
the source is explicit that a BOS exit is not what the reference does.

    [SRC Ch.20] "For trade management, Index Algo relies on a Trailing Stop
    logic rather than fixed take-profit targets. This approach allows a trade to
    retain room for further expansion as long as price continues to move in line
    with the confirmed scenario."

    [SRC Ch.20] "This CONTRADICTS master prompt §74, which names BOS as 'the
    natural structural target'. The reference does not target BOS."

    [SRC Ch.24] "Active Price is where the trailing stop ARMS. The trade does
    not close there. Winners run past it; 0.5R is the threshold at which the
    setup is judged to have enough room to be worth taking at all."

    [GAP Ch.20/Ch.21] What the trailing stop actually TRAILS is never stated.

So every number measured so far — Stage A, Variants 2/3/4 — used an exit the
source rules out. This is not a refinement of those results, it is a different
question, and the fixed-R controls below are what says whether trailing is
worth anything at all.

HARNESS CHANGE THAT MATTERS. Every prior variant allowed ONE live trade at a
time, so an exit that holds longer blocks later entries and n differs between
arms. That is the same slot-competition confound that muddied the obstacle
check. Here the setups are collected ONCE and every exit rule runs over the
identical set, so n is equal across arms by construction and the exit is the
only thing that varies.

Entry is Variant 3's best arm, unchanged: FVG zones, SCOB shadow confirmation,
stop at the zone's far edge.

    PYTHONPATH=. RIPTIDE_DEEP_CACHE=/tmp/deep python3 research/lit_exit.py
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
MAX_HOLD = 500          # a trailing trade has no target; it must be capped


class Zone:
    def __init__(self, ev, bornBar):
        self.dir = ev["dir"]
        self.top = max(ev["px"], ev["edge"])
        self.bot = min(ev["px"], ev["edge"])
        self.born = bornBar
        self.dead = False
        self.inside = False
        self.since = 0
        self.scobLvl = None

    def far(self):
        return self.bot if self.dir > 0 else self.top

    def touched(self, h, l):
        return l <= self.top and h >= self.bot

    def feed(self, o, h, l, c):
        """SCOB shadow mode — Variant 3's best arm."""
        up = self.dir > 0
        entry = None
        if self.scobLvl is not None:
            if (h > self.scobLvl) if up else (l < self.scobLvl):
                entry = c
        if (c < o) if up else (c > o):
            self.scobLvl = h if up else l
        return entry


class Setup:
    """A confirmed entry. Exit-rule agnostic — this is what every arm shares."""
    __slots__ = ("bar", "entry", "stop0", "dir", "bos", "risk", "active",
                 "blocked")

    def __init__(self, bar, entry, stop0, dirn, bos):
        self.blocked = False
        self.bar, self.entry, self.stop0, self.dir, self.bos = \
            bar, entry, stop0, dirn, bos
        self.risk = abs(entry - stop0)
        cost = entry * COMMISSION * 2
        self.active = (entry + MIN_RR * self.risk + cost) if dirn > 0 \
            else (entry - MIN_RR * self.risk - cost)


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
            out.append(Zone(pe, bar))
    return out


def collect(cs, events):
    """One pass. Every confirmed setup, with NO exit simulated and therefore no
    slot competition — a setup is recorded even if an earlier one is still open
    under some exit rule. That is the point: the arms must share a trade set."""
    byBar = {}
    for e in events:
        byBar.setdefault(e["bar"], []).append(e)
    pending, zones = [], []
    bos = choch = None
    broken = []
    out = []

    for i in range(len(cs)):
        k = cs[i]
        for e in byBar.get(i, ()):
            kd = e["kind"]
            if kd == "pb":
                pending.append(e)
            elif kd == "idm_break":
                bos, choch = e["bos"], e["choch"]
                zones.extend(build(pending, e["dir"], i))
                pending = []
            elif kd in ("bos_break", "choch_break"):
                lv = e.get("bos") if kd == "bos_break" else e.get("choch")
                if lv is not None:
                    broken.append((i, lv))
                zones, pending = [], []

        if not zones:
            continue
        alive = []
        for z in zones:
            if i - z.born > MAX_WAIT or z.dead:
                continue
            if not z.touched(k.h, k.l) and not z.inside:
                alive.append(z)
                continue
            if not z.inside:
                z.inside, z.since = True, i
            px = z.feed(k.o, k.h, k.l, k.c)
            if px is not None:
                z.dead = True
                s = Setup(i, px, z.far(), z.dir, bos)
                if s.risk > 0 and (
                        (s.stop0 < px and bos is not None and bos > px)
                        if z.dir > 0 else
                        (s.stop0 > px and bos is not None and bos < px)):
                    # [SRC Ch.18/22] The obstacle check, NOW UNCONFOUNDED:
                    # under a trailing exit BOS is no longer the target, so
                    # "BOS in the corridor" is no longer a restatement of
                    # "the target is near".
                    lo, hi = min(px, s.active), max(px, s.active)
                    obs = [bos, choch]
                    obs += [(o.top if o.dir > 0 else o.bot)
                            for o in zones if o is not z]
                    obs += [p["px"] for p in pending if p["dir"] != z.dir]
                    obs += [q for b, q in broken if i - b <= MAX_WAIT]
                    s.blocked = any(o is not None and lo < o < hi for o in obs)
                    out.append(s)
                continue
            if i - z.since > SCOB_WAIT:
                z.dead = True
                continue
            alive.append(z)
        zones = alive
    return out, byBar


# ---------------------------------------------------------------- exit rules

def simulate(cs, byBar, s, rule, k=0.0, bodyStop=False):
    """Run ONE setup under ONE exit rule. Returns (R, mfeR, bars, why)."""
    up = s.dir > 0
    stop = s.stop0
    armed = False
    mfe = 0.0
    lastStruct = lastPiv = None
    n = len(cs)

    for i in range(s.bar + 1, min(n, s.bar + 1 + MAX_HOLD)):
        c = cs[i]
        # running MFE, in R, before any exit test
        ext = (c.h - s.entry) / s.risk if up else (s.entry - c.l) / s.risk
        if ext > mfe:
            mfe = ext

        # --- the stop. [SRC Ch.22/23] the break can be judged on the wick or
        # on the body; the body reading is the one the source draws, and the
        # author's own worked example says it can realise 2.5x the planned loss.
        if bodyStop:
            hit = (c.c <= stop) if up else (c.c >= stop)
            fill = c.c
        else:
            hit = (c.l <= stop) if up else (c.h >= stop)
            fill = stop
        if hit:
            return rOf(s, fill, up), mfe, i - s.bar, "stop"

        # --- fixed-target controls
        if rule == "bos":
            if (c.h >= s.bos) if up else (c.l <= s.bos):
                return rOf(s, s.bos, up), mfe, i - s.bar, "bos"
        elif rule == "fixed":
            tgt = (s.entry + k * s.risk) if up else (s.entry - k * s.risk)
            if (c.h >= tgt) if up else (c.l <= tgt):
                return rOf(s, tgt, up), mfe, i - s.bar, "target"

        # --- arming. [SRC Ch.18/24] the trail starts at Active Price.
        if not armed:
            if (c.h >= s.active) if up else (c.l <= s.active):
                armed = True
                if rule in ("be", "pivot", "struct", "mfe"):
                    be = s.entry + (s.entry * COMMISSION * 2) * (1 if up else -1)
                    stop = max(stop, be) if up else min(stop, be)

        # --- the trail itself, only once armed
        # Two DIFFERENT things to trail behind, kept apart on purpose:
        #   pivot   each newly confirmed pullback pivot in the trade direction
        #   struct  the most recent structural level (the IDM raid extreme)
        for e in byBar.get(i, ()):
            if e["kind"] == "pb" and e["dir"] == s.dir:
                lastPiv = e["px"]
            elif e["kind"] == "idm_break" and e["dir"] == s.dir:
                lastStruct = e["stop"]
        if armed:
            if rule == "pivot" and lastPiv is not None:
                stop = max(stop, lastPiv) if up else min(stop, lastPiv)
            elif rule == "struct" and lastStruct is not None:
                stop = max(stop, lastStruct) if up else min(stop, lastStruct)
            elif rule == "mfe":
                t = (s.entry + (mfe - k) * s.risk) if up \
                    else (s.entry - (mfe - k) * s.risk)
                stop = max(stop, t) if up else min(stop, t)

    j = min(n, s.bar + 1 + MAX_HOLD) - 1
    return rOf(s, cs[j].c, up), mfe, j - s.bar, "cap"


def rOf(s, px, up):
    d = (px - s.entry) if up else (s.entry - px)
    return d / s.risk - (s.entry * COMMISSION * 2) / s.risk


def report(name, rs, extra=""):
    if len(rs) < 20:
        print(f"  {name:<26}{len(rs):>6}   too few to read")
        return
    w = [r for r in rs if r > 0]
    # The standard error is the column that has been missing all along. A NET
    # of +0.026 against a control's -0.020 is not a result if se is 0.09.
    se = statistics.stdev(rs) / (len(rs) ** 0.5) if len(rs) > 1 else 0.0
    print(f"  {name:<26}{len(rs):>6}{100 * len(w) / len(rs):>8.1f}%"
          f"{statistics.fmean(rs):>9.3f}{se:>8.3f}"
          f"{(statistics.fmean(w) if w else 0):>7.2f}"
          f"{(statistics.fmean([r for r in rs if r <= 0]) if w != rs else 0):>7.2f}"
          f"{min(rs):>8.2f}{extra}")


SYMS = ["ZEC_USDT", "BTC_USDT", "ETH_USDT", "SOL_USDT", "ONDO_USDT",
        "LINK_USDT", "AVAX_USDT", "DOGE_USDT", "XRP_USDT", "ADA_USDT",
        "TON_USDT", "NEAR_USDT", "BNB_USDT", "LTC_USDT", "DOT_USDT",
        "ATOM_USDT", "FIL_USDT", "APT_USDT", "ARB_USDT", "OP_USDT",
        "INJ_USDT", "SUI_USDT", "TIA_USDT", "SEI_USDT", "RUNE_USDT",
        "AAVE_USDT", "UNI_USDT", "ETC_USDT", "BCH_USDT", "TRX_USDT"]

ARMS = [
    ("CONTROL initial stop only", "raw",    0.0),
    ("CONTROL exit at BOS",      "bos",    0.0),
    ("CONTROL fixed 1R",         "fixed",  1.0),
    ("CONTROL fixed 2R",         "fixed",  2.0),
    ("CONTROL fixed 3R",         "fixed",  3.0),
    ("T6 break-even only",       "be",     0.0),
    ("T6 pivot trail",           "pivot",  0.0),
    ("T6 structure trail",       "struct", 0.0),
    ("T6 mfe - 0.5R",            "mfe",    0.5),
    ("T6 mfe - 1.0R",            "mfe",    1.0),
    ("T6 mfe - 1.5R",            "mfe",    1.5),
]


async def main():
    book = {}
    async with aiohttp.ClientSession() as sess:
        for tf in ("Min15", "Min30", "Min60"):
            cs = await load_universe(sess, SYMS, tf, 120, min_bars=2000)
            for sym, k in cs.items():
                if len(k) >= 500:
                    m, _i, _d, _g = L.engine(k)
                    su, bb = collect(k, m.events)
                    if su:
                        book[(tf, sym)] = (k, bb, su)
            print(f"  loaded {tf}: {len(cs)} symbols")

    tot = sum(len(v[2]) for v in book.values())
    print(f"\nT6 - WHAT THE TRAILING STOP TRAILS")
    print(f"Entry: V3 best arm (FVG zones, SCOB shadow, zone SL). "
          f"{tot} setups, SHARED by every arm.\n")
    print("=" * 96)
    print(f"  {'exit rule':<26}{'n':>6}{'win%':>8}{'NET R':>9}{'se':>8}"
          f"{'avgW':>7}{'avgL':>7}{'worst':>8}")
    print("=" * 96)

    mfeAll = None
    keep = {}
    for nm, rule, k in ARMS:
        rs, mf, tfs = [], [], []
        for (tf, _sym), (cs, bb, su) in book.items():
            for s in su:
                r, m, _b, _w = simulate(cs, bb, s, rule, k)
                rs.append(r)
                mf.append(m)
                tfs.append(tf)
        report(nm, rs)
        keep[nm] = (rs, mf, tfs)
        if rule == "raw":
            mfeAll = mf
        if nm == "CONTROL fixed 3R":
            print("  " + "-" * 92)

    # [SRC Ch.24] "Stage A must measure MFE past Active Price, not first
    # passage to a target." MFE is a property of the setup, not of the exit,
    # so it is identical across arms - it is the CEILING any exit can reach.
    mf = sorted(mfeAll)
    q = lambda p: mf[int(p * (len(mf) - 1))]        # noqa: E731
    print(f"\n{'=' * 96}\n  MFE CEILING  [SRC Ch.24]\n{'=' * 96}")
    print(f"  reached Active Price (0.5R): "
          f"{100 * sum(1 for x in mf if x >= MIN_RR) / len(mf):.1f}%")
    for lab, v in (("1R", 1.0), ("2R", 2.0), ("3R", 3.0), ("5R", 5.0)):
        print(f"  reached {lab:<3}                  "
              f"{100 * sum(1 for x in mf if x >= v) / len(mf):.1f}%")
    print(f"  median MFE {q(0.5):.2f}R   p75 {q(0.75):.2f}R   "
          f"p90 {q(0.90):.2f}R   mean {statistics.fmean(mf):.2f}R")

    # A trail that never arms is just the initial stop. On the ~38% that never
    # reach Active Price EVERY trailing arm is identical to the control, which
    # dilutes the comparison. Restrict to the setups where the trail actually
    # engaged - that is the only population where T6 can possibly matter.
    print(f"\n{'=' * 96}\n  ARMED SUBSET ONLY - where the trail actually "
          f"engaged\n{'=' * 96}")
    print(f"  {'exit rule':<26}{'n':>6}{'win%':>8}{'NET R':>9}{'se':>8}"
          f"{'avgW':>7}{'avgL':>7}{'worst':>8}")
    for nm, _r, _k in ARMS:
        rs, mfl, _tf = keep[nm]
        report(nm, [r for r, m in zip(rs, mfl) if m >= MIN_RR])

    # The user asked about 30m specifically.
    print(f"\n{'=' * 96}\n  BY TIMEFRAME\n{'=' * 96}")
    for nm in ("CONTROL exit at BOS", "T6 structure trail", "T6 mfe - 1.5R"):
        rs, _mf, tfs = keep[nm]
        print(f"  {nm}")
        for tf in ("Min15", "Min30", "Min60"):
            report(f"    {tf}", [r for r, t in zip(rs, tfs) if t == tf])
    diagnose(book)

    # Variant 4 left this open: the obstacle check could not be read under a
    # BOS exit because BOS was both the obstacle and the target. Under the
    # structure trail that circularity is gone, so this is the real test.
    print(f"\n{'=' * 96}\n  OBSTACLE CHECK, RE-TESTED UNDER A TRAILING EXIT"
          f"  [SRC Ch.18]\n{'=' * 96}")
    print(f"  {'set':<26}{'n':>6}{'win%':>8}{'NET R':>9}{'se':>8}"
          f"{'avgW':>7}{'avgL':>7}{'worst':>8}")
    for rule, k, lab in (("struct", 0.0, "structure trail"),
                         ("mfe", 1.5, "mfe - 1.5R")):
        clear, blk = [], []
        for (cs, bb, su) in book.values():
            for s in su:
                r, _m, _b, _w = simulate(cs, bb, s, rule, k)
                (blk if s.blocked else clear).append(r)
        print(f"  {lab}")
        report("    path clear (kept)", clear)
        report("    path blocked (rejected)", blk)





def diagnose(book):
    """'Hold with no target' posting the best NET is the classic shape of a
    result that is really market drift. If the wins are longs that ran to the
    MAX_HOLD cap, it is beta over a bullish sample, not edge."""
    rows = []
    for (tf, _s), (cs, bb, su) in book.items():
        for s in su:
            r, m, b, w = simulate(cs, bb, s, "raw", 0.0)
            rows.append((r, s.dir, w, b, tf))
    print(f"\n{'=' * 96}\n  IS 'HOLD WITH NO TARGET' EDGE OR DRIFT?\n{'=' * 96}")
    for w in ("stop", "cap"):
        sel = [r for r, _d, ww, _b, _t in rows if ww == w]
        print(f"  exit={w:<5} {len(sel):>4} trades  "
              f"{100 * len(sel) / len(rows):>5.1f}% of set   "
              f"NET {statistics.fmean(sel):>7.3f}")
    for d, lab in ((1, "LONG"), (-1, "SHORT")):
        sel = [r for r, dd, _w, _b, _t in rows if dd == d]
        if len(sel) > 5:
            se = statistics.stdev(sel) / (len(sel) ** 0.5)
            print(f"  {lab:<6} {len(sel):>4} trades   NET "
                  f"{statistics.fmean(sel):>7.3f}  se {se:.3f}")
    hold = [b for _r, _d, _w, b, _t in rows]
    hold.sort()
    print(f"  median hold {hold[len(hold) // 2]} bars, "
          f"mean {statistics.fmean(hold):.0f} bars  (cap is {MAX_HOLD})")


if __name__ == "__main__":
    asyncio.run(main())
