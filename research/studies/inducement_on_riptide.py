"""WHICH INDUCEMENT DEFINITION, IF ANY, SORTS RIPTIDE'S SETUPS.

Pre-registered in PREREG_inducement_on_riptide.md, committed before this ran.
Read that file first — the bars, the control and the family-wise caveat are
all fixed there.

The short version. Four indicators now define "inducement" four different ways.
Rather than argue about which is right, each one is evaluated as a covariate on
Riptide's OWN bets:

    was an inducement of type X, on the side the raid swept, taken within
    W = 50 bars ending at the raid?

and the answer is compared against what those bets actually paid. A definition
earns the right to be drawn only if it separates the good bets from the bad.

F is the control and the whole point: the most recent plain swing pivot, taken.
No structure, no vocabulary. Every other definition has to beat it.

    PYTHONPATH=. RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/inducement_on_riptide.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import statistics                                       # noqa: E402
import time                                             # noqa: E402
from collections import defaultdict                     # noqa: E402

import aiohttp                                          # noqa: E402

from research.deep import load_deep                     # noqa: E402
from research.harness import simulate                   # noqa: E402
import research.lit_v3 as L                             # noqa: E402
import research.lit_repl as RP                          # noqa: E402
from riptide.config import CFG, BAR_SECONDS             # noqa: E402
from riptide.engine import (atr_series, is_pivot_high,   # noqa: E402
                            is_pivot_low, run_engine)

DAYS = 333
SYMS = RP.DISCOVERY[:40]
TFS = ("Min30", "Min15")

# Every one of these is fixed a priori by the prereg. None is swept.
W = CFG.max_bars_after_grab          # 50 — Riptide's own grab-to-shift window
PL, PR = CFG.pivot_left, CFG.pivot_right      # 1, 2 — Riptide's own pivots
ATR_LEN = 14                         # the reference indicators' ATR
EQ_FACTOR = 0.5                      # mickes' "ATR factor" default
LOOKBACK = 5                         # mickes' "Lookback" default
EQ_LOOKBACK = 3                      # mickes' equal-pivot lookback default
HORIZON_HOURS, FILL_HOURS = 48, 5
TARGET_R = 2.0
FEE = dict(fee_maker=0.02, fee_taker=0.06)

# side of a TAKE event: -1 a low was taken, +1 a high was taken.
LOW, HIGH = -1, 1

DEFS = ("F_PIVOT", "A1_LIT_MAIN", "A2_LIT_INT", "B_RETRACE", "C_EQUAL",
        "D_RANGE", "E_GRAB")
CONTROL = "F_PIVOT"


# ───────────────────────────── pivot stream ─────────────────────────────────
def pivot_stream(cs):
    """Riptide's own pivots, in confirmation order.

    Yields (confirm_bar, pivot_bar, price, side). A pivot at bar p is not
    known until bar p + PR, and every definition below is fed from this one
    stream so that the comparison is between DEFINITIONS and not between
    pivot sensitivities.
    """
    out = []
    for p in range(PL, len(cs) - PR):
        if is_pivot_high(cs, p, PL, PR):
            out.append((p + PR, p, cs[p].h, HIGH))
        if is_pivot_low(cs, p, PL, PR):
            out.append((p + PR, p, cs[p].l, LOW))
    out.sort(key=lambda r: r[0])
    return out


def through(c, px, side):
    """Did this candle trade through the level, in the taking direction?"""
    return (c.h > px) if side == HIGH else (c.l < px)


# ───────────────────────── the seven definitions ────────────────────────────
# Each returns a list of (bar, side) TAKE events.

def d_pivot(cs, piv):
    """F — THE CONTROL. One migrating level per side: the most recent
    confirmed swing. When price trades through it, that is the take."""
    cur = {HIGH: None, LOW: None}
    by_confirm = defaultdict(list)
    for cb, pb, px, sd in piv:
        by_confirm[cb].append((px, sd))
    out = []
    for i, c in enumerate(cs):
        for sd in (HIGH, LOW):
            lv = cur[sd]
            if lv is not None and i > lv[1] and through(c, lv[0], sd):
                out.append((i, sd))
                cur[sd] = None
        for px, sd in by_confirm.get(i, ()):
            cur[sd] = (px, i)        # migration: the newest replaces the old
    return out


def d_lit(ctx):
    """A — LIT-IDM. The engine's own migrating pullback pivot being broken.

    A bull context's IDM sits BELOW price, so breaking it takes a LOW.
    """
    return [(e["bar"], LOW if e["dir"] > 0 else HIGH)
            for e in ctx.events if e["kind"] == "idm_break"]


def d_retrace(cs, piv, breaks):
    """B — RETRACEMENT IDM (mickes). The first pivot confirmed after a
    structure break whose predecessor predates that break. One live level per
    side; a new break invalidates it."""
    brk = sorted(breaks)
    bi = 0
    last_break = None
    prev = {HIGH: None, LOW: None}       # last confirm bar, per side
    live = {HIGH: None, LOW: None}
    by_confirm = defaultdict(list)
    for cb, pb, px, sd in piv:
        by_confirm[cb].append((px, sd))
    out = []
    for i, c in enumerate(cs):
        while bi < len(brk) and brk[bi] <= i:
            last_break = brk[bi]
            bi += 1
            live = {HIGH: None, LOW: None}       # invalidated by the break
        for sd in (HIGH, LOW):
            lv = live[sd]
            if lv is not None and i > lv[1] and through(c, lv[0], sd):
                out.append((i, sd))
                live[sd] = None
        for px, sd in by_confirm.get(i, ()):
            if (last_break is not None and live[sd] is None
                    and prev[sd] is not None and prev[sd] < last_break):
                live[sd] = (px, i)
            prev[sd] = i
    return out


def d_equal(cs, piv, atr):
    """C — EQUAL HIGHS/LOWS (mickes). Two same-side pivots within
    EQ_FACTOR x ATR of each other, with no wick through the line joining
    them. Pending set capped at the source's lookback."""
    recent = {HIGH: [], LOW: []}          # (pivot_bar, price), newest first
    pend = []                             # (price, side, armed_bar)
    by_confirm = defaultdict(list)
    for cb, pb, px, sd in piv:
        by_confirm[cb].append((pb, px, sd))
    out = []
    for i, c in enumerate(cs):
        keep = []
        for px, sd, ab in pend:
            if i > ab and through(c, px, sd):
                out.append((i, sd))
            else:
                keep.append((px, sd, ab))
        pend = keep
        for pb, px, sd in by_confirm.get(i, ()):
            tol = EQ_FACTOR * (atr[i] if i < len(atr) else 0.0)
            for opb, opx in recent[sd][:EQ_LOOKBACK]:
                if tol <= 0 or abs(px - opx) > tol:
                    continue
                span = pb - opb
                if span <= 1 or span > 500:
                    continue
                broken = False
                for k in range(opb + 1, pb):
                    t = opx + (px - opx) * (k - opb) / span
                    if (cs[k].h > t) if sd == HIGH else (cs[k].l < t):
                        broken = True
                        break
                if broken:
                    continue
                pend.append((px, sd, i))
                if len(pend) > LOOKBACK:
                    pend.pop(0)
                break
            recent[sd].insert(0, (pb, px))
            del recent[sd][EQ_LOOKBACK + 2:]
    return out


def d_range(cs, piv):
    """D — RANGE IDM (Inducement Engine). A pivot strictly inside the running
    structure range qualifies as an inducement.

    The range is reproduced as the source has it — last_high only rises and
    last_low only falls — because that IS the rule under test. See finding 4
    in audit/INDUCEMENT_ENGINE_AUDIT.md for why it widens toward degeneracy.
    """
    hi = lo = None
    pend = []
    by_confirm = defaultdict(list)
    for cb, pb, px, sd in piv:
        by_confirm[cb].append((px, sd))
    out = []
    for i, c in enumerate(cs):
        keep = []
        for px, sd, ab in pend:
            if i > ab and through(c, px, sd):
                out.append((i, sd))
            else:
                keep.append((px, sd, ab))
        pend = keep
        for px, sd in by_confirm.get(i, ()):
            inside = (hi is not None and lo is not None and lo < px < hi)
            if inside:
                pend.append((px, sd, i))
                if len(pend) > LOOKBACK:
                    pend.pop(0)
            if sd == HIGH and (hi is None or px > hi):
                hi = px
            if sd == LOW and (lo is None or px < lo):
                lo = px
    return out


def d_grab(cs, piv):
    """E — GRAB (mickes). A pivot wicked through and closed back inside. A
    close BEYOND the pivot invalidates it instead."""
    pend = []
    by_confirm = defaultdict(list)
    for cb, pb, px, sd in piv:
        by_confirm[cb].append((px, sd))
    out = []
    for i, c in enumerate(cs):
        keep = []
        for px, sd, ab in pend:
            if i <= ab:
                keep.append((px, sd, ab))
                continue
            if sd == LOW:
                if c.l <= px and c.c >= px:
                    out.append((i, sd))
                    continue
                if c.c < px:
                    continue                 # invalidated
            else:
                if c.h >= px and c.c <= px:
                    out.append((i, sd))
                    continue
                if c.c > px:
                    continue                 # invalidated
            keep.append((px, sd, ab))
        pend = keep
        for px, sd in by_confirm.get(i, ()):
            pend.append((px, sd, i))
            if len(pend) > LOOKBACK:
                pend.pop(0)
    return out


def take_index(events, n):
    """events -> per-side sorted bar lists, for the window test."""
    idx = {HIGH: [], LOW: []}
    for b, sd in events:
        if 0 <= b < n:
            idx[sd].append(b)
    for sd in idx:
        idx[sd].sort()
    return idx


def fired(idx, side, anchor):
    """Was there a take of this side in [anchor - W, anchor]?"""
    lo_, hi_ = anchor - W, anchor
    xs = idx[side]
    j = 0
    k = len(xs)
    while j < k:                                     # first >= lo_
        m = (j + k) // 2
        if xs[m] < lo_:
            j = m + 1
        else:
            k = m
    return j < len(xs) and xs[j] <= hi_


# ───────────────────────────── statistics ───────────────────────────────────
def contrast(rows):
    """rows: (fired, r). Returns n_on, n_off, mean_on, mean_off, delta, se, z."""
    on = [r for f, r in rows if f]
    off = [r for f, r in rows if not f]
    if len(on) < 2 or len(off) < 2:
        return None
    mo, mf = statistics.fmean(on), statistics.fmean(off)
    se = ((statistics.variance(on) / len(on))
          + (statistics.variance(off) / len(off))) ** 0.5
    d = mo - mf
    return dict(n_on=len(on), n_off=len(off), m_on=mo, m_off=mf, d=d, se=se,
                z=(d / se) if se else 0.0,
                cov=len(on) / (len(on) + len(off)))


async def main():
    print("=" * 100)
    print("  WHICH INDUCEMENT DEFINITION SORTS RIPTIDE'S SETUPS?")
    print("=" * 100)
    print(f"  population   every confirmed Riptide setup, its real limit "
          f"entry and real stop, target {TARGET_R}R")
    print(f"  unit         the BET — one per sweep_time; unfilled scores "
          f"0.0 R and stays in")
    print(f"  window       W = {W} bars ending at the raid "
          f"(CFG.max_bars_after_grab, not swept)")
    print(f"  pivots       left {PL} right {PR} (Riptide's own), shared by "
          f"every definition except A")
    print(f"  symbols      {len(SYMS)}   timeframes {', '.join(TFS)}   "
          f"days {DAYS}")
    print(f"  control      {CONTROL} — a plain swing pivot being taken")
    print("=" * 100)

    # panel[(tf, half)][defn] -> list of (fired, r)
    panel = defaultdict(lambda: defaultdict(list))
    counts = defaultdict(int)
    t0 = time.time()

    async with aiohttp.ClientSession() as sess:
        for tf in TFS:
            horizon = max(1, HORIZON_HOURS * 3600 // BAR_SECONDS[tf])
            fill_bars = max(1, FILL_HOURS * 3600 // BAR_SECONDS[tf])
            done = 0
            for sym in SYMS:
                try:
                    cs = await load_deep(sess, sym, tf, days=DAYS)
                except Exception:
                    continue
                if len(cs) < 3000:
                    continue
                n = len(cs)
                atr = atr_series(cs, ATR_LEN)
                piv = pivot_stream(cs)
                m, inter, _d, _g = L.engine(cs)
                breaks = [e["bar"] for e in inter.events
                          if e["kind"] in ("bos_break", "choch_break")]

                idxs = {
                    "F_PIVOT": take_index(d_pivot(cs, piv), n),
                    "A1_LIT_MAIN": take_index(d_lit(m), n),
                    "A2_LIT_INT": take_index(d_lit(inter), n),
                    "B_RETRACE": take_index(d_retrace(cs, piv, breaks), n),
                    "C_EQUAL": take_index(d_equal(cs, piv, atr), n),
                    "D_RANGE": take_index(d_range(cs, piv), n),
                    "E_GRAB": take_index(d_grab(cs, piv), n),
                }

                try:
                    setups = run_engine(sym, cs, CFG)
                except Exception:
                    continue
                at = {c.t: i for i, c in enumerate(cs)}
                cut = n // 2

                bets = defaultdict(list)     # sweep_time -> [(r, anchor, sd)]
                for s in setups:
                    i = at.get(s.detected_time)
                    if i is None or i + 1 + horizon > n:
                        continue
                    if s.entry <= 0 or abs(s.entry - s.stop) <= 0:
                        continue
                    anchor = at.get(s.sweep_time or s.detected_time, i)
                    o = simulate(cs, i, s.entry, s.stop, s.is_long,
                                 target_r=TARGET_R, fill_bars=fill_bars,
                                 horizon_bars=horizon, fee_pct=0.0, **FEE)
                    want = LOW if s.is_long else HIGH
                    bets[s.sweep_time or s.detected_time].append(
                        (o.r, anchor, want))

                half = None
                for _k, rows in bets.items():
                    r = statistics.fmean(x[0] for x in rows)
                    anchor, want = rows[0][1], rows[0][2]
                    half = "older" if anchor < cut else "newer"
                    counts[(tf, half)] += 1
                    for name in DEFS:
                        panel[(tf, half)][name].append(
                            (fired(idxs[name], want, anchor), r))
                done += 1
            print(f"\n  {tf}: {done} symbols, "
                  f"{counts[(tf,'older')] + counts[(tf,'newer')]} bets "
                  f"({time.time()-t0:.0f}s elapsed)")

    # ── per-panel table ─────────────────────────────────────────────────────
    res = {}
    for tf in TFS:
        for half in ("older", "newer"):
            print("\n" + "=" * 100)
            print(f"  {tf}  {half.upper()} HALF   "
                  f"{counts[(tf, half)]} bets")
            print("=" * 100)
            print(f"  {'definition':<14}{'fires on':>10}{'n on':>7}"
                  f"{'n off':>7}{'R | fired':>11}{'R | not':>10}"
                  f"{'delta':>9}{'SE':>8}{'z':>7}")
            for name in DEFS:
                c = contrast(panel[(tf, half)][name])
                res[(tf, half, name)] = c
                if c is None:
                    print(f"  {name:<14}{'—':>10}   too few on one side")
                    continue
                print(f"  {name:<14}{c['cov']:>9.1%}{c['n_on']:>7}"
                      f"{c['n_off']:>7}{c['m_on']:>11.3f}{c['m_off']:>10.3f}"
                      f"{c['d']:>9.3f}{c['se']:>8.3f}{c['z']:>7.2f}")

    # ── the pre-registered verdict ──────────────────────────────────────────
    print("\n" + "=" * 100)
    print("  VERDICT AGAINST THE FOUR PRE-REGISTERED BARS")
    print("=" * 100)
    print("   1 coverage 15-85%   2 one sign in all four panels")
    print("   3 beats the control in both halves   4 z >= 2.0 on the newer "
          "half (pooled)")
    print()
    print(f"  {'definition':<14}{'1 cov':>8}{'2 sign':>9}{'3 ctrl':>9}"
          f"{'4 z':>8}   verdict")
    panels = [(tf, h) for tf in TFS for h in ("older", "newer")]
    for name in DEFS:
        cs_ = [res.get((tf, h, name)) for tf, h in panels]
        if any(c is None for c in cs_):
            print(f"  {name:<14}{'—':>8}{'—':>9}{'—':>9}{'—':>8}   "
                  f"NOT COMPUTABLE")
            continue
        b1 = all(0.15 <= c["cov"] <= 0.85 for c in cs_)
        ds = [c["d"] for c in cs_]
        b2 = all(d > 0 for d in ds) or all(d < 0 for d in ds)
        b3 = True
        for tf in TFS:
            for h in ("older", "newer"):
                ctl = res.get((tf, h, CONTROL))
                cur = res.get((tf, h, name))
                if ctl and cur and cur["d"] <= ctl["d"]:
                    b3 = False
        # pooled newer half across timeframes
        rows = []
        for tf in TFS:
            rows += panel[(tf, "newer")][name]
        pc = contrast(rows)
        b4 = bool(pc and pc["z"] >= 2.0)
        ok = b1 and b2 and b3 and b4
        if name == CONTROL:
            verdict = "CONTROL — the bar everything else must clear"
        else:
            verdict = "PASSES" if ok else "INCONCLUSIVE"
        zs = f"{pc['z']:.2f}" if pc else "—"
        print(f"  {name:<14}{('yes' if b1 else 'NO'):>8}"
              f"{('yes' if b2 else 'NO'):>9}{('yes' if b3 else 'NO'):>9}"
              f"{zs:>8}   {verdict}")

    print()
    print("=" * 100)
    print("  READ")
    print("=" * 100)
    print("  Column 3 is the one that matters. Every definition here fires")
    print("  after a pullback, and so does the plain-pivot control, so a")
    print("  positive delta on its own says only that Riptide's setups do")
    print("  better when something got taken first. Beating F is what")
    print("  separates an inducement from a swing low with a name on it.")
    print()
    print("  With seven candidates the family-wise false-positive rate at")
    print("  z >= 2.0 alone is about 28%. Bars 1-3 are what carry any pass.")
    print()
    print("  Nothing here licenses a filter on Riptide's alerts. A pass earns")
    print("  one thing: the right to be the definition drawn in the v2 layer.")


if __name__ == "__main__":
    asyncio.run(main())
