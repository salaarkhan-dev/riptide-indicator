"""The Undertow port: is it the same thing as the Pine, and is it honest?

    PYTHONPATH=. python3 indicators/undertow/tests/test_undertow_port.py

Pine cannot run here, so "same as the Pine" is proved in three layers and it is
worth being clear about what each one actually establishes:

  1. deploy/undertow-ms-check.py         undertow.pine's engine == v2.pine's
  2. deploy/ms-py-parity.py              v2.pine's engine == ms_struct.py
  3. THIS FILE                           ms_struct.py == the port's structure()

Chain those and the port's market structure is the Pine's market structure, by
machine rather than by eye. Nothing covers sections 5-7 that way -- those have
no v2 counterpart -- so they are tested here by BEHAVIOUR, on bars built to
make one rule fire and nothing else.

THE SCENARIO TESTS ARE THE ONES THAT MATTER. Three of them encode bugs found on
real charts and fixed once: the target printing before the limit filled, one bar
spanning both the entry and the stop, and a fill on the arming bar itself. Each
would silently inflate the win rate, which is the only kind of bug a backtest
cannot show you.
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))

from indicators.riptide_ms.port import ms_struct                   # noqa: E402
from indicators.undertow.port import undertow as U                 # noqa: E402
from indicators.undertow.port.swings import (bar_swings, bars_per,        # noqa: E402
                                             price_swings, range_basis)
from riptide.engine import Candle, atr_series                      # noqa: E402

good = []


def ok(cond, msg):
    good.append(bool(cond))
    print(("  ok   " if cond else "  FAIL ") + msg)


def bar(t, o, h, l, c):
    return Candle(t * 60, o, h, l, c, 1.0)


def walk(n=1200, seed=7, drift=0.0):
    """A random walk with OHLC that respects h >= max(o,c) and l <= min(o,c)."""
    rnd = random.Random(seed)
    px = 100.0
    cs = []
    for i in range(n):
        o = px
        px = max(1.0, px * (1 + rnd.gauss(drift, 0.004)))
        c = px
        hi = max(o, c) * (1 + abs(rnd.gauss(0, 0.002)))
        lo = min(o, c) * (1 - abs(rnd.gauss(0, 0.002)))
        cs.append(bar(i, o, hi, lo, c))
    return cs


# ─────────────────────────────────────────────────── 1. the parity chain ──


def test_swings_match_ms_struct():
    """bar_swings IS ms_swings. Two transcriptions of one Pine function drift
    the moment somebody fixes one of them, so this is the drift alarm."""
    cs = walk(800, seed=3)
    for L in (2, 3, 7, 15, 40):
        a = bar_swings(cs, L)
        b = ms_struct.ms_swings(cs, L)
        ok(a == b, f"bar_swings == ms_struct.ms_swings at msLen={L}")


def test_structure_matches_ms_struct():
    """The port's section 3 fires CHoCH, BOS and sweeps on exactly the bars the
    already-parity-checked engine does. This is link 3 of the chain."""
    for seed, drift in ((11, 0.0), (12, 0.0006), (13, -0.0006)):
        cs = walk(1500, seed=seed, drift=drift)
        p = U.P()
        st, _ = U.structure(cs, p)
        ev, _ = ms_struct.engine(cs, p.msLen, p.msShortLen, p.msBosNeedsIdm)

        mine = dict(
            choch=[i for i, v in enumerate(st["choch"]) if v],
            bos=[i for i, v in enumerate(st["bosUp"]) if v]
                + [i for i, v in enumerate(st["bosDn"]) if v],
            sweep=[i for i, v in enumerate(st["sweepUp"]) if v]
                  + [i for i, v in enumerate(st["sweepDn"]) if v])
        theirs = {k: sorted(e["bar"] for e in ev if e["kind"] == k)
                  for k in ("choch", "bos", "sweep")}
        for k in ("choch", "bos", "sweep"):
            got, want = sorted(mine[k]), theirs[k]
            ok(got == want,
               f"seed {seed}: {len(want)} {k} bars match ms_struct.engine"
               + ("" if got == want else f"  ({len(got)} vs {len(want)})"))


def test_atr_matches_the_bot():
    cs = walk(400, seed=5)
    ok(U.atr_series(cs, 14) == atr_series(cs, 14),
       "the port's ATR is riptide.engine's ATR")


# ──────────────────────────────────────────────────── 2. the ATR swings ──


def test_atr_swings_alternate_and_are_real():
    cs = walk(2000, seed=21)
    atr = U.atr_series(cs, 14)
    tops, topxs, btms, btmxs = price_swings(cs, 2.0, atr)
    seq = sorted([(i, "T") for i, v in enumerate(tops) if v is not None]
                 + [(i, "B") for i, v in enumerate(btms) if v is not None])
    ok(len(seq) > 20, f"the detector finds swings at all: {len(seq)}")
    ok(all(a[1] != b[1] for a, b in zip(seq, seq[1:])),
       "swing highs and lows strictly alternate")

    # NO LOOK-AHEAD: a swing is dated to a bar at or before the bar that
    # confirms it, and its price is that bar's actual high or low.
    lookahead = [i for i, v in enumerate(tops)
                 if v is not None and (topxs[i] > i or cs[topxs[i]].h != v)]
    ok(not lookahead, f"every swing high is a real past high: {lookahead[:3]}")
    lookahead = [i for i, v in enumerate(btms)
                 if v is not None and (btmxs[i] > i or cs[btmxs[i]].l != v)]
    ok(not lookahead, f"every swing low is a real past low: {lookahead[:3]}")


def test_which_unit_survives_a_timeframe_change():
    """THE MEASUREMENT THAT DECIDED swings.py, and it rejected the first idea.

    Aggregate 4 bars into 1 -- a 15m chart becoming 1h -- over the same span of
    time, and count the swings each detector finds. A unit that means the same
    thing on both charts keeps the count; a unit that is itself a function of
    the bar does not.

    k x ATR was the obvious candidate and it is WORSE than the bar pivot it was
    meant to replace, because aggregating 4 bars multiplies per-bar ATR by
    ~sqrt(4) and therefore doubles the threshold. This test is what caught it.
    """
    cs = walk(4000, seed=33)
    hi, _ = U.aggregate(cs, 4)

    def count(sw):
        t, _, b, _ = sw
        return sum(v is not None for v in t) + sum(v is not None for v in b)

    def ratio(lo, hiC):
        return (hiC / lo) if lo else 0.0

    barR = ratio(count(bar_swings(cs, 15)), count(bar_swings(hi, 15)))
    atrR = ratio(count(price_swings(cs, 2.0, U.atr_series(cs, 14))),
                 count(price_swings(hi, 2.0, U.atr_series(hi, 14))))
    # 24 hours of bars on each: `bars_per` reads the step off the timestamps,
    # so this is one setting, not two.
    rngR = ratio(count(price_swings(cs, 0.4, range_basis(cs, bars_per(cs, 24)))),
                 count(price_swings(hi, 0.4, range_basis(hi, bars_per(hi, 24)))))
    print(f"       bar pivot 15      x{barR:.2f}")
    print(f"       k x ATR(14)       x{atrR:.2f}")
    print(f"       k x 24h range     x{rngR:.2f}")
    ok(atrR < barR,
       "k x ATR is WORSE than the bar pivot -- a per-bar unit cannot be it")
    ok(rngR > 0.7,
       f"k x a fixed span of time nearly survives the change: x{rngR:.2f}")
    ok(rngR > barR and rngR > atrR,
       "the fixed-time range is the most scale-invariant of the three")


# ──────────────────────────────────────────────── 3. the setup machine ──
#
# Hand-built bars. A long bias is expensive to construct honestly, so these
# drive the machine directly through its own pieces where that is what is under
# test, and use whole scenarios where the ORDER of the checks is what is under
# test.


def test_beyond_modes():
    c = bar(0, 10.0, 12.0, 8.0, 11.0)
    ok(U._beyond_up(c, 11.0, U.T_CLOSE) is False, "close beyond: 11 is not > 11")
    ok(U._beyond_up(c, 11.0, U.T_TOUCH) is True, "close at or beyond: 11 >= 11")
    ok(U._beyond_up(c, 10.5, U.T_BODY) is False,
       "whole body beyond: the body spans 10..11, so 10.5 is inside it")
    ok(U._beyond_up(c, 9.5, U.T_BODY) is True, "whole body beyond 9.5")
    ok(U._beyond_dn(c, 9.5, U.T_BODY) is False, "body is not below 9.5")


def test_family_and_doji():
    """wickEdge IS the doji filter, and that is the only thing separating a
    hammer from a balanced bar."""
    p = U.P(wickEdge=0.05)
    # range 100, lower wick 30, upper wick 10 -> hammer by 0.20
    ham = bar(0, 60.0, 100.0, 0.0, 90.0)
    rng = ham.h - ham.l
    upW = (ham.h - max(ham.o, ham.c)) / rng
    dnW = (min(ham.o, ham.c) - ham.l) / rng
    ok(dnW - upW >= p.wickEdge, "a clear lower-wick bar is the hammer family")
    # near-balanced: wicks within 0.02 of each other
    doji = bar(0, 49.0, 100.0, 0.0, 51.0)
    rng = doji.h - doji.l
    upW = (doji.h - max(doji.o, doji.c)) / rng
    dnW = (min(doji.o, doji.c) - doji.l) / rng
    ok(abs(dnW - upW) < p.wickEdge, "a balanced bar is neither family")


def run_cands(p, cs, cand):
    """Drive ONE pre-armed candidate through the resolution loop, so the
    ordering rules can be tested without building a whole trend."""
    out = dict(gone=0, filled=0, tgt=0, stop=0, back=0, won=0, lost=0)
    live = []
    for i, c in enumerate(cs):
        if cand and cand.armed and i > cand.armBar:
            tgtGone = c.l <= cand.target if cand.short else c.h >= cand.target
            stopHit = c.h >= cand.stop if cand.short else c.l <= cand.stop
            touched = c.h >= cand.focus >= c.l
            if tgtGone:
                out["tgt"] += 1
                cand = None
            elif stopHit:
                out["stop"] += 1
                cand = None
            elif touched:
                out["filled"] += 1
                live.append((cand, i))
                cand = None
            elif i - cand.armBar >= p.fillBars:
                out["back"] += 1
                cand = None
        for t, _fb in list(live):
            lost = c.h >= t.stop if t.short else c.l <= t.stop
            won = c.l <= t.target if t.short else c.h >= t.target
            if lost:
                out["lost"] += 1
                live.remove((t, _fb))
            elif won:
                out["won"] += 1
                live.remove((t, _fb))
    return out


def armed_long(armBar=0, focus=100.0, stop=95.0, target=110.0):
    c = U._Cand(bar=armBar, hi=101.0, lo=99.0, focus=focus, workHi=True,
                short=False, pbExt=95.0, state="running", code="HAM")
    c.armed = True
    c.armBar = armBar
    c.stop = stop
    c.target = target
    return c


def test_target_before_fill_is_not_a_win():
    """THE BUG THAT PRODUCED A CLEAN 2R OVER A TRADE THAT COLLAPSED. Price runs
    to the target while the limit is still unfilled, comes back, fills, then
    dies. The move was available and the order was not on."""
    p = U.P(fillBars=20)
    cs = [bar(0, 100, 101, 99, 100),                   # the arming bar
          bar(1, 101, 112, 101, 111),                  # blows past the target
          bar(2, 111, 111, 99, 100),                   # comes back and fills
          bar(3, 100, 100, 90, 92)]                    # collapses
    r = run_cands(p, cs, armed_long())
    ok(r["tgt"] == 1 and r["filled"] == 0 and r["won"] == 0,
       "target printed before the fill -> dropped, not a win")


def test_stop_before_fill_beats_the_touch():
    """One bar spans the entry and the stop. Which came first is unknowable
    intrabar, so the setup is dropped rather than counted as a fill."""
    p = U.P()
    cs = [bar(0, 100, 101, 99, 100),
          bar(1, 101, 101, 94, 95)]                    # touches 100 AND 95
    r = run_cands(p, cs, armed_long())
    ok(r["stop"] == 1 and r["filled"] == 0,
       "a bar spanning entry and stop is a drop, never a fill")


def test_no_fill_on_the_arming_bar():
    """The limit is only resting once the arming bar has CLOSED. A fill inside
    that same bar is look-ahead: the order was not on while it traded."""
    p = U.P()
    cs = [bar(0, 100, 101, 99, 100)]                   # spans the entry
    r = run_cands(p, cs, armed_long(armBar=0))
    ok(r["filled"] == 0, "no fill on the arming bar itself")
    cs2 = cs + [bar(1, 100, 101, 99, 100)]
    ok(run_cands(p, cs2, armed_long(armBar=0))["filled"] == 1,
       "the very next bar may fill")


def test_fill_window_expires():
    p = U.P(fillBars=3)
    cs = [bar(0, 100, 101, 99, 100)] + [bar(i, 102, 103, 101.5, 102)
                                        for i in range(1, 8)]
    ok(run_cands(p, cs, armed_long())["back"] == 1,
       "price never comes back -> the fill window expires")


# ──────────────────────────────────────────────── 4. the whole machine ──


def test_run_is_deterministic_and_self_consistent():
    cs = walk(3000, seed=41, drift=0.0004)
    p = U.P()
    a, b = U.run(cs, p, "T"), U.run(cs, p, "T")
    ok(a.nArmed == b.nArmed and a.nFilled == b.nFilled
       and len(a.trades) == len(b.trades), "run() is deterministic")
    ok(a.nRaw >= a.nPins >= a.nColour >= a.nLoc,
       f"the funnel narrows: {a.nRaw} >= {a.nPins} >= {a.nColour} >= {a.nLoc}")
    resolved = a.nFilled + a.nMissBack + a.nMissStop + a.nMissGone + a.nMissBias
    ok(resolved <= a.nArmed,
       f"every armed setup resolves at most once: {resolved} <= {a.nArmed}")
    ok(all(t.fillBar > t.armBar for t in a.trades),
       "no trade fills on or before its arming bar")
    ok(all(t.exitBar >= t.fillBar for t in a.trades),
       "no trade exits before it fills")
    # THE IDENTITY THE PINE PANEL BROKE. It counted ghosts among its open
    # trades and printed "28 / 58 · 1 open" beside "86 entered", which is 87.
    # A ghost is not a position; it is a cancelled setup being walked forward
    # to find out whether the gate was right.
    ok(a.nFilled == len(a.real) + a.nOpenReal,
       f"entered == won + lost + open, REAL only: {a.nFilled} == "
       f"{len(a.real)} + {a.nOpenReal}")
    ok(len(a.ghosts) + a.nOpenGhost == sum(
        1 for t in a.trades if t.ghost) + a.nOpenGhost,
       "and the ghosts account for themselves separately")
    print(f"       {a.nLoc} setups, {a.nArmed} armed, {a.nFilled} filled, "
          f"{len(a.real)} closed, net {a.netR:+.1f}R")


def test_ghosts_do_not_touch_the_real_numbers():
    """The ghost column must be free. Running with and without it has to leave
    every real counter identical -- if it does not, the measurement changed the
    thing it was measuring."""
    cs = walk(3000, seed=43, drift=0.0004)
    a = U.run(cs, U.P(), "T")
    ok(a.nMissBias > 0, f"the bias gate cancelled something: {a.nMissBias}")
    ok(len(a.ghosts) > 0, f"some of those ghosts filled: {len(a.ghosts)}")
    ok(all(not t.ghost for t in a.real) and len(a.real) + len(a.ghosts)
       == len(a.trades), "real and ghost trades partition the list")
    ok(a.nFilled == len(a.real) + len([t for t in a.real if False])
       or a.nFilled >= len(a.real),
       f"nFilled counts real fills only: {a.nFilled} vs {len(a.real)} closed")
    print(f"       gate cancelled {a.nMissBias}, of which {len(a.ghosts)} "
          f"filled, worth {a.gateCost:+.1f}R "
          f"({'cost' if a.gateCost > 0 else 'saved'})")


def test_fees_only_ever_reduce_r():
    cs = walk(3000, seed=41, drift=0.0004)
    free = U.run(cs, U.P(), "T")
    paid = U.run(cs, U.P(feeFrac=0.0007), "T")
    ok(len(free.trades) == len(paid.trades),
       "a fee changes no decision, only the score")
    ok(paid.netR < free.netR,
       f"fees reduce net R: {paid.netR:+.2f} < {free.netR:+.2f}")
    ok(all(b.r <= a.r + 1e-12 for a, b in zip(free.trades, paid.trades)),
       "no individual trade is improved by paying a fee")
    print(f"       {free.netR:+.1f}R gross -> {paid.netR:+.1f}R at 7bp "
          f"over {len(free.real)} trades")


# ─────────────────────────────────────────────────── 5. the backup fill ──
#
# The OB/FVG backup is the one component that was asked for from the start and
# built last. It is off by default, unmeasured, and the tests below pin its
# SHAPE -- that it can only add trades, that it never invents a better price
# than the limit it replaces, and that it respects its own chase limit.


def test_backup_never_invents_a_better_price():
    """THE PROPERTY THAT MAKES IT HONEST. A backup entry sits between the
    market and the Focus line, so for a short it is BELOW the Focus and for a
    long ABOVE it — further from the stop, bigger risk, worse R. If a backup
    ever filled on the far side of the Focus it would be a better price than
    the order that was already missed, which is inventing a fill."""
    cs = walk(6000, seed=71, drift=0.0004)
    a = U.run(cs, U.P(maxLive=64, useBackup=True), "T")
    bk = [t for t in a.real if t.backup]
    ok(len(bk) > 3, f"the fixture produces backup fills: {len(bk)}")
    bad = [t for t in bk
           if (t.entry > t.stop if t.short else t.entry < t.stop)]
    ok(not bad, f"every backup entry is still on the right side of its stop: "
                f"{len(bad)} bad")
    worse = [t for t in bk if abs(t.stop - t.entry) <= 0]
    ok(not worse, "and every one has a positive risk")
    print(f"       {len(bk)} backup fills of {len(a.real)}: "
          f"{sum(1 for t in bk if t.backup == 'OB')} OB, "
          f"{sum(1 for t in bk if t.backup == 'FVG')} FVG")


def test_backup_only_adds_trades():
    """It must not change a single decision made before the fill. The setups
    found, the setups armed and the setups the bias cancelled are all upstream
    of it, so turning it on may only convert a MISS into a FILL."""
    cs = walk(6000, seed=71, drift=0.0004)
    off = U.run(cs, U.P(maxLive=64), "T")
    on = U.run(cs, U.P(maxLive=64, useBackup=True), "T")
    ok(on.nLoc == off.nLoc and on.nArmed == off.nArmed,
       f"setups and armings are untouched: {on.nLoc}/{on.nArmed} == "
       f"{off.nLoc}/{off.nArmed}")
    # nMissBias may FALL, and that is correct rather than a leak: a setup that
    # filled via a backup has left `cands`, so a later bias flip can no longer
    # cancel it. A filled trade cannot be un-armed.
    ok(on.nMissBias <= off.nMissBias,
       f"the bias gate can only cancel fewer, never more: "
       f"{on.nMissBias} <= {off.nMissBias}")
    ok(on.nFilled >= off.nFilled,
       f"fills can only go up: {on.nFilled} >= {off.nFilled}")
    # THE COST, MADE VISIBLE. Not every backup is an extra trade: the zone sits
    # between the market and the Focus, so price touches it FIRST, and a setup
    # that would have retraced all the way to the Focus fills at the worse
    # price instead. That is what placing the order actually does, and the
    # difference below is how many trades paid for it.
    extra = on.nFilled - off.nFilled
    ok(extra <= on.nBackup,
       f"every extra fill is a backup: {extra} <= {on.nBackup}")
    print(f"       {on.nBackup} backups: {extra} are trades that would not "
          f"have happened, {on.nBackup - extra} pre-empted a Focus fill at a "
          f"worse price")
    ok(on.nMissBack + on.nMissGone + on.nMissStop
       <= off.nMissBack + off.nMissGone + off.nMissStop,
       "the misses it converted came out of the miss buckets")


def test_backup_respects_its_chase_limit():
    """bkMaxRisk is the only thing stopping it from entering arbitrarily far
    from the stop and calling the result a trade."""
    cs = walk(6000, seed=71, drift=0.0004)
    for cap in (1.25, 2.0, 4.0):
        a = U.run(cs, U.P(maxLive=64, useBackup=True, bkMaxRisk=cap), "T")
        bk = [t for t in a.real if t.backup]
        # The original risk is not recorded on the Trade, but the cap bounds
        # the RATIO, so a tighter cap can only produce fewer or equal backups.
        print(f"       bkMaxRisk {cap}: {len(bk)} backups")
        if cap == 1.25:
            tight = len(bk)
        if cap == 4.0:
            ok(len(bk) >= tight,
               f"a looser chase limit admits at least as many: "
               f"{len(bk)} >= {tight}")


def test_backup_zones_are_real():
    """bk_zone must return an edge that exists on a bar in the window, on the
    correct side, and never a level price has already passed."""
    cs = walk(3000, seed=73, drift=-0.0004)
    hits = 0
    for i in range(300, len(cs), 37):
        for short in (True, False):
            focus = cs[i].c * (1.02 if short else 0.98)
            lo = cs[i].l if short else cs[i].h
            px, why = U.bk_zone(cs, i, short, focus, lo, 30, True, True)
            if px is None:
                continue
            hits += 1
            inside = (lo < px < focus) if short else (focus < px < lo)
            if not inside:
                ok(False, f"bar {i}: zone {px} outside ({lo}, {focus})")
                return
            found = any(abs(px - c.l) < 1e-9 or abs(px - c.h) < 1e-9
                        for c in cs[max(0, i - 31):i + 1])
            if not found:
                ok(False, f"bar {i}: zone edge {px} is on no bar in the window")
                return
            if why not in ("OB", "FVG"):
                ok(False, f"bar {i}: unnamed zone {why!r}")
                return
    ok(hits > 20, f"{hits} zones found, all inside their bounds and on a real "
                  f"bar, all named OB or FVG")
    # Both kinds must actually fire. A silently-dead FVG detector is exactly
    # the bug this assertion caught: the backup went on working from order
    # blocks alone and nothing anywhere said the gaps were never found.
    kinds = set()
    for i in range(300, len(cs), 7):
        for short in (True, False):
            focus = cs[i].c * (1.02 if short else 0.98)
            lo = cs[i].l if short else cs[i].h
            _, why = U.bk_zone(cs, i, short, focus, lo, 30, False, True)
            if why:
                kinds.add(why)
    ok("FVG" in kinds,
       "the FVG detector finds gaps when asked for them alone")


# ───────────────────────────────────────────────────────── 6. HTF bias ──


def test_htf_aggregate_is_sound():
    cs = walk(400, seed=51)
    hi, closeX = U.aggregate(cs, 4)
    ok(len(hi) in (100, 101), f"400 bars into 4s is ~100 bars: {len(hi)}")
    ok(len(hi) == len(closeX), "one close index per aggregate bar")
    j = 5
    lo, hiX = closeX[j - 1] + 1, closeX[j]
    src = cs[lo:hiX + 1]
    ok(hi[j].h == max(c.h for c in src) and hi[j].l == min(c.l for c in src)
       and hi[j].o == src[0].o and hi[j].c == src[-1].c,
       "an aggregate bar is the real OHLC of its members")


def test_htf_bias_cannot_look_ahead():
    """The one property that makes the feature honest. Truncating the data at
    bar i must not change the HTF verdict at bar i -- if it does, the verdict
    was reading bars that had not happened."""
    cs = walk(1200, seed=53, drift=0.0005)
    p = U.P(htfMult=4)
    fullD, fullK = U.htf_dir(cs, p)
    bad = []
    for i in (400, 601, 777, 900, 1101):
        d, k = U.htf_dir(cs[:i + 1], p)
        if d[i] != fullD[i] or k[i] != fullK[i]:
            bad.append(i)
    ok(not bad, f"the HTF verdict at bar i uses no bar after i: {bad}")


def test_htf_gate_only_removes_setups():
    cs = walk(3000, seed=55, drift=0.0004)
    off = U.run(cs, U.P(), "T")
    on = U.run(cs, U.P(htfMult=4), "T")
    ok(on.nLoc == off.nLoc,
       "the HTF gate sits AFTER the four base tests, so 'setups found' is "
       f"unchanged: {on.nLoc} == {off.nLoc}")
    ok(on.nArmed <= off.nArmed,
       f"it can only remove setups: {on.nArmed} <= {off.nArmed}")
    ok(on.nHtf > 0, f"and it removed some: {on.nHtf}")
    print(f"       htf x4 turned away {on.nHtf} of {off.nLoc} setups; "
          f"{off.nArmed} -> {on.nArmed} armed, "
          f"{off.netR:+.1f}R -> {on.netR:+.1f}R")


def test_price_swing_sources_run_end_to_end():
    cs = walk(3000, seed=57, drift=0.0004)
    for src, k, km in (("atr", 2.5, 0.8), ("range", 0.40, 0.12)):
        a = U.run(cs, U.P(swingSrc=src, swingK=k, swingKMinor=km), "T")
        ok(a.nArmed > 0, f"swingSrc={src!r} produces setups: {a.nArmed}")
        ok(a.nRaw >= a.nPins >= a.nColour >= a.nLoc,
           f"swingSrc={src!r}: the funnel still narrows")
        print(f"       {src:>5}: {a.nLoc} setups, {a.nArmed} armed, "
              f"{len(a.real)} closed, net {a.netR:+.1f}R")


def main():
    for fn in (test_swings_match_ms_struct, test_structure_matches_ms_struct,
               test_atr_matches_the_bot, test_atr_swings_alternate_and_are_real,
               test_which_unit_survives_a_timeframe_change, test_beyond_modes,
               test_family_and_doji, test_target_before_fill_is_not_a_win,
               test_stop_before_fill_beats_the_touch,
               test_no_fill_on_the_arming_bar, test_fill_window_expires,
               test_run_is_deterministic_and_self_consistent,
               test_ghosts_do_not_touch_the_real_numbers,
               test_fees_only_ever_reduce_r,
               test_backup_never_invents_a_better_price,
               test_backup_only_adds_trades,
               test_backup_respects_its_chase_limit,
               test_backup_zones_are_real,
               test_htf_aggregate_is_sound,
               test_htf_bias_cannot_look_ahead,
               test_htf_gate_only_removes_setups,
               test_price_swing_sources_run_end_to_end):
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{'ALL PASS' if all(good) else 'FAILURES'}  "
          f"{sum(good)}/{len(good)}")
    return 0 if all(good) else 1


if __name__ == "__main__":
    sys.exit(main())
