"""The momentum mirror of Liquidity Entry Zones: break and retest, not sweep
and reclaim.

WHY THIS MODEL, AND WHY THIS SHAPE

`lez_sweep.py` produced one finding that pointed somewhere rather than nowhere:
**the daily-trend filter helps RANDOM entries more than it helps LEZ.** At
Min15 it took coin flips from −0.179 to −0.040 and LEZ from −0.227 to only
−0.139; at Min30, random −0.152 → +0.026 against LEZ −0.126 → +0.006.

That is not a filter failing. It is `which_trend.py`'s +4.5 SE daily-trend
effect reproducing cleanly inside the control while the strategy fails to
collect it — because LEZ is the wrong SHAPE for it. LEZ buys after a low is
swept, which is a mean-reversion trigger; the daily trend is a momentum filter.
A random long in an uptrend rides the trend. A LEZ long in an uptrend has
specifically bought a flush.

So this is the same machinery pointed the other way. Same stored pivot levels,
same ATR margin, same cooldown, same scorer. The trigger is inverted:

    LEZ         price takes a level and CLOSES BACK INSIDE it   (rejection)
    this        price takes a level and CLOSES BEYOND it        (acceptance)

and the level, once broken, becomes the thing price is expected to retest and
hold.

WHAT IS FIXED BY EVIDENCE RATHER THAN SWEPT

- **Direction comes from the DAILY trend, and it is a requirement, not a
  filter.** `which_trend.py`: daily +4.5 SE, the chart's own trend −0.0 SE.
  Longs only in a daily uptrend, shorts only in a downtrend, flat days sit out.
  This is the whole premise, so it does not get a knob.
- **No chart EMA.** It is the measured null. Adding it would be superstition.
- **A decisive close, not a poke**: body ≥ 50% of the bar's range. The direct
  mirror of LEZ's `maxBodyPercent = 0.65`, and fixed at that for the same
  reason — it defines the model rather than tunes it.
- **The level must be freshly broken**: the previous bar closed on the other
  side of it. Without this, one level fires on every bar that stays beyond it,
  which is the stale-level flaw §1.9 of STRATEGIES.md found in the Pine.

THE PRE-REGISTRATION — written before a single number was produced

    PRIMARY, and the only cell that carries the verdict:
        market entry at the breakout close, stop 1.5 x ATR(14), target 3R,
        no POI requirement.
    Chosen because it is the exact mirror of LEZ's shipped settings, so the
    comparison LEZ vs this is ONE variable: rejection against acceptance.

    THE BAR, on the HELD-OUT half:
        EDGE > 0 AND R/signal > 0, on the PRIMARY cell.

    Last time the bar was "EDGE > 0 and R > 0" on the BEST OF 360 cells, which
    a coin flip clears about half the time. Naming the cell in advance is what
    fixes that — best-of-N cannot touch a cell chosen before the run. The other
    23 cells are printed and are DESCRIPTIVE ONLY; if the primary fails, a
    prettier cell elsewhere does not rescue it, and saying so now is the point
    of saying it now.

    Grid (descriptive): entry market/retest x stop 1/1.5/structural x
    target 2R/3R x POI off/on = 24 cells. Small on purpose. The same 24
    questions are asked of the matched control to measure this grid's own
    noise floor, exactly as in lez_sweep.py — where the floor turned out to be
    the entire result.

THE CONTROL IS MATCHED, which is more work than it sounds

A coin flip is not the right control here, because this strategy only trades
in the direction of the daily trend. So the control takes a random bar, trades
in the DAILY TREND'S OWN DIRECTION at that bar, sits out flat days, and — for
the retest arm — places its limit at an entry offset drawn from the real
signals' offsets. Same stop, same target, same POI test. It isolates the
trigger and nothing else.

    PYTHONPATH=. python3 research/studies/momentum.py
"""
from __future__ import annotations

import research.env  # noqa: F401  (must precede riptide.config)

import asyncio
import random
import statistics
from dataclasses import dataclass

import aiohttp

from riptide.config import CFG, BAR_SECONDS
from riptide.engine import atr_series
from riptide.exchange import list_symbols
from riptide.trend import di_direction, supertrend
from research.harness import mean_se, simulate, simulate_market
from research.studies.lez import pivots
from research.studies.mtf_grid import (fetch_paged, htf_dir_at, in_poi,
                                       zones_of)

HTF = "Day1"
TFS = (("Min30", 2), ("Min15", 4))
SYMBOLS = 30
HORIZON_HOURS, FILL_HOURS = 48, 5
FEE = dict(fee_maker=0.02, fee_taker=0.06)
RANDOM_MULT = 3

# The model. Not swept — see the docstring.
PIVOT_LEN = 5
STORED = 20
BREAK_ATR = 0.10          # a close beyond the level by at least this much ATR
MIN_BODY_PCT = 0.50       # decisive, the mirror of LEZ's max body 0.65
COOLDOWN = 10
ATR_LEN = 14
# A STOP CLOSER THAN THIS IS NOT A TRADE, IT IS A ROUNDING ARTEFACT.
#
# The structural stop sits at the breakout bar's extreme, and the retest limit
# sits at the broken level. Nothing stops those two from landing a hair apart —
# and when they do, risk_pct goes to almost zero while fee in R is
# fee / risk_pct, so a single such row books a loss of tens of R. The first run
# of this study had the eight `struct` cells at the TOP of the table with
# control means near -4.7 R, entirely from a handful of these.
#
# 0.25 ATR is the floor: below a quarter of one bar's typical range the stop is
# inside the noise of the candle that triggered the trade and no exchange fill
# would survive it. Applied identically to the signal and the control.
MIN_RISK_ATR = 0.25

# The descriptive grid.
ENTRIES = ("market", "retest")
STOPS = ("1.0", "1.5", "struct")
TARGETS = (2.0, 3.0)
POIS = (False, True)
PRIMARY = ("market", "1.5", 3.0, False)      # declared above, before the run
MIN_N = 100


@dataclass
class Row:
    is_long: bool
    poi: bool
    outs: dict           # (entry, stop, target) -> Outcome
    risk: dict           # (entry, stop) -> risk %


# ---------------------------------------------------------------- the trigger

def breakouts(cs, atr, hcs, hst, hdi):
    """(bar, is_long, level, break_low, break_high) for every fresh, decisive
    close beyond a stored pivot level, in the daily trend's direction.

    Levels enter the store only on the bar their pivot CONFIRMS, so nothing
    consults a level before it exists.
    """
    hi_piv, lo_piv = pivots(cs, PIVOT_LEN)
    hi_at, lo_at = {}, {}
    for c, j, px in hi_piv:
        hi_at.setdefault(c, []).append(px)
    for c, j, px in lo_piv:
        lo_at.setdefault(c, []).append(px)

    stored_hi: list[float] = []
    stored_lo: list[float] = []
    last_bar = None
    out = []
    for i, c in enumerate(cs):
        for px in hi_at.get(i, []):
            stored_hi.append(px)
            del stored_hi[:-STORED]
        for px in lo_at.get(i, []):
            stored_lo.append(px)
            del stored_lo[:-STORED]
        a = atr[i]
        rng = c.h - c.l
        if a <= 0 or rng <= 0 or i == 0:
            continue
        if abs(c.c - c.o) / rng < MIN_BODY_PCT:
            continue
        d = htf_dir_at(hcs, hst, hdi, c.t)
        if d == 0:
            continue                       # flat day: the premise is absent
        if last_bar is not None and i - last_bar <= COOLDOWN:
            continue
        prev = cs[i - 1].c
        margin = BREAK_ATR * a
        if d > 0 and c.c > c.o:
            # The HIGHEST level this close cleared that the previous close did
            # not: the most significant liquidity actually taken this bar.
            cand = [px for px in stored_hi
                    if c.c - px >= margin and prev <= px]
            if cand:
                out.append((i, True, max(cand), c.l, c.h))
                last_bar = i
        elif d < 0 and c.c < c.o:
            cand = [px for px in stored_lo
                    if px - c.c >= margin and prev >= px]
            if cand:
                out.append((i, False, min(cand), c.l, c.h))
                last_bar = i
    return out


# ---------------------------------------------------------------------- score

def arms(cs, bar, is_long, level, blow, bhigh, atr_v, horizon, fill_bars):
    """Every (entry, stop, target) arm for one candidate, or None."""
    if atr_v <= 0 or bar + 1 + horizon > len(cs):
        return None, None
    close = cs[bar].c
    struct = blow if is_long else bhigh
    outs, risk = {}, {}
    for ent in ENTRIES:
        # market: taken at the breakout close. retest: a LIMIT resting at the
        # level that was just broken, which is the whole idea — old resistance
        # as new support. It also pays MAKER, halving the fee that sank LEZ.
        entry = close if ent == "market" else level
        if entry <= 0:
            continue
        for sl in STOPS:
            if sl == "struct":
                stop = struct
            else:
                d = atr_v * float(sl)
                stop = entry - d if is_long else entry + d
            if stop <= 0 or ((stop >= entry) if is_long else (stop <= entry)):
                continue
            if abs(entry - stop) < MIN_RISK_ATR * atr_v:
                continue
            risk[(ent, sl)] = 100 * abs(entry - stop) / entry
            for tr in TARGETS:
                if ent == "market":
                    o = simulate_market(cs, bar, entry, stop, is_long,
                                        target_r=tr, horizon_bars=horizon,
                                        **FEE)
                else:
                    o = simulate(cs, bar, entry, stop, is_long, target_r=tr,
                                 fill_bars=fill_bars, horizon_bars=horizon,
                                 fee_pct=0.0, **FEE)
                if o is not None:
                    outs[(ent, sl, tr)] = o
    return (outs, risk) if outs else (None, None)


def cell(rows, ent, sl, tr, need_poi):
    sel = [r for r in rows if (not need_poi or r.poi)
           and (ent, sl, tr) in r.outs]
    if not sel:
        return 0, 0.0, 0.0, 0.0, 0.0
    rs = [r.outs[(ent, sl, tr)].r for r in sel]
    m, se = mean_se(rs)
    risk = statistics.fmean(r.risk[(ent, sl)] for r in sel)
    return len(rs), m, se, sum(x > 0 for x in rs) / len(rs), risk


def grid(lez_rows, ctl_rows):
    res = []
    for ent in ENTRIES:
        for sl in STOPS:
            for tr in TARGETS:
                for poi in POIS:
                    n, m, se, win, risk = cell(lez_rows, ent, sl, tr, poi)
                    rn, rm, rse, _, rrisk = cell(ctl_rows, ent, sl, tr, poi)
                    if not n or not rn:
                        continue
                    res.append(dict(
                        key=(ent, sl, tr, poi), n=n, m=m, se=se, win=win,
                        risk=risk, rn=rn, rm=rm, rrisk=rrisk,
                        lab=f"{ent:<7}{sl:<7}{tr:g}R  "
                            f"{'POI' if poi else '---'}",
                        edge=m - rm,
                        edge_se=(se ** 2 + rse ** 2) ** 0.5))
    return sorted(res, key=lambda c: -c["edge"])


# ------------------------------------------------------------------ collection

async def collect(sess, syms, tf, pages, hcache):
    horizon = max(1, HORIZON_HOURS * 3600 // BAR_SECONDS[tf])
    fill_bars = max(1, FILL_HOURS * 3600 // BAR_SECONDS[tf])
    hstep = BAR_SECONDS[HTF]
    out = {(h, k): [] for h in ("disc", "held") for k in ("sig", "ctl")}
    days, offsets_seen = [], []

    for n, sym in enumerate(syms):
        try:
            cs = await fetch_paged(sess, sym, tf, pages)
            if sym not in hcache:
                hcache[sym] = await fetch_paged(sess, sym, HTF, 1)
            hcs = hcache[sym]
        except Exception:
            continue
        if len(cs) < 800 or len(hcs) < 60:
            continue
        days.append((cs[-1].t - cs[0].t) / 86400)
        hst, hdi = supertrend(hcs), di_direction(hcs)
        zones = zones_of(hcs, atr_series(hcs, CFG.atr_len))
        atr = atr_series(cs, ATR_LEN)
        cut = len(cs) // 2
        rnd = random.Random(2000 + n)

        sigs = breakouts(cs, atr, hcs, hst, hdi)
        counts = {"held": 0, "disc": 0}
        offs = []
        for bar, is_long, level, blow, bhigh in sigs:
            o, r = arms(cs, bar, is_long, level, blow, bhigh, atr[bar],
                        horizon, fill_bars)
            if o is None:
                continue
            half = "held" if bar < cut else "disc"
            counts[half] += 1
            # The retest offset, in ATR, so the control can be matched on it.
            offs.append(abs(cs[bar].c - level) / atr[bar])
            poi = in_poi(zones, cs[bar].t, level, is_long, hstep)
            out[(half, "sig")].append(Row(is_long, poi, o, r))
        offsets_seen += offs
        pool = offs or [0.5]

        # THE MATCHED CONTROL. Random bar, but the DAILY TREND'S direction —
        # this strategy never trades against it, so a control that did would
        # be measuring the trend rather than the trigger. Flat days sit out
        # for the same reason. The retest limit is placed at an offset drawn
        # from the real signals, so the retracement geometry is held constant
        # too and only the trigger differs.
        for half, lo, hi in (("held", 60, cut), ("disc", cut, len(cs))):
            hi = min(hi, len(cs) - horizon - 2)
            want = counts[half] * RANDOM_MULT
            tries = 0
            while want > 0 and hi > lo and tries < want * 40:
                tries += 1
                i = rnd.randrange(lo, hi)
                a = atr[i]
                if a <= 0:
                    continue
                d = htf_dir_at(hcs, hst, hdi, cs[i].t)
                if d == 0:
                    continue
                is_long = d > 0
                off = rnd.choice(pool) * a
                level = cs[i].c - off if is_long else cs[i].c + off
                if level <= 0:
                    continue
                o, r = arms(cs, i, is_long, level, cs[i].l, cs[i].h, a,
                            horizon, fill_bars)
                if o is None:
                    continue
                poi = in_poi(zones, cs[i].t, level, is_long, hstep)
                out[(half, "ctl")].append(Row(is_long, poi, o, r))
                want -= 1
    return out, days, offsets_seen


HEAD = (f"  {'cell':<26}{'n':>6}{'win':>6}{'risk':>7}{'ctl risk':>9}"
        f"{'R/sig':>9}{'control':>9}{'EDGE':>9}{'SE':>7}")


def show(c, mark=""):
    # `ctl risk` is not decoration. EDGE only isolates the trigger when the
    # signal and the control take the SAME risk, because fee in R is
    # fee / risk_pct. The ATR stops are identical by construction. The
    # STRUCTURAL stop is not: a breakout bar has a big body by definition, so
    # its close-to-low distance is wider than a random bar's, and a wider stop
    # pays less fee. Where these two columns diverge, the EDGE is the fee gap
    # rather than the trigger, and the row must not be read as a finding.
    gap = abs(c["risk"] - c["rrisk"]) / max(c["risk"], 1e-9)
    print(f"  {c['lab']:<26}{c['n']:>6}{c['win']:>6.0%}{c['risk']:>6.2f}%"
          f"{c['rrisk']:>8.2f}%{c['m']:>+9.3f}{c['rm']:>+9.3f}"
          f"{c['edge']:>+9.3f}"
          f"{c['edge'] / c['edge_se'] if c['edge_se'] else 0:>+6.1f}  "
          f"{'RISK MISMATCH' if gap > 0.10 else ''}{mark}")


def report(tf, data, days, offs):
    d_s, d_c = data[("disc", "sig")], data[("disc", "ctl")]
    h_s, h_c = data[("held", "sig")], data[("held", "ctl")]
    print(f"\n{'=' * 100}\n{tf}   {statistics.median(days):.0f} days across "
          f"{len(days)} symbols, split in half\n{'=' * 100}")
    print(f"  discovery {len(d_s)} signals / {len(d_c)} control      "
          f"held out {len(h_s)} / {len(h_c)}")
    if offs:
        print(f"  median retest depth {statistics.median(offs):.2f} ATR "
              f"below the breakout close")
    if len(d_s) < MIN_N:
        print("  too few signals")
        return

    g = grid(d_s, d_c)
    print(f"\n  ALL {len(g)} CELLS on the discovery half, by EDGE "
          f"(descriptive — the primary below is what counts)")
    print(HEAD)
    for c in g:
        show(c, "<- PRIMARY" if c["key"] == PRIMARY else "")

    fl = grid(d_c[0::2], d_c[1::2])
    fl = [c for c in fl if c["n"] >= MIN_N // 2]
    if fl:
        b = max(fl, key=lambda c: c["edge"])
        print(f"\n  NOISE FLOOR — the same {len(fl)} questions asked of the "
              f"control, one half against the other:")
        print(f"    best cell scores EDGE {b['edge']:+.3f}  ({b['lab'].strip()})")

    ent, sl, tr, poi = PRIMARY
    n, m, se, win, risk = cell(h_s, ent, sl, tr, poi)
    rn, rm, rse, _, _ = cell(h_c, ent, sl, tr, poi)
    print(f"\n  HELD OUT — the older half, one shot, on the PRE-DECLARED "
          f"primary cell only")
    if n < 25 or rn < 25:
        print(f"    n={n} control={rn}: too few to read")
        return
    edge, ese = m - rm, (se ** 2 + rse ** 2) ** 0.5
    print(f"    {'cell':<12}{ent} entry, {sl} ATR stop, {tr:g}R, no POI")
    print(f"    {'n':<12}{n}   win {win:.0%}")
    print(f"    {'R/signal':<12}{m:+.3f} ± {se:.3f}")
    print(f"    {'control':<12}{rm:+.3f}")
    print(f"    {'EDGE':<12}{edge:+.3f} ± {ese:.3f}"
          + (f"   {edge / ese:+.1f} SE" if ese else ""))
    print(f"    => {'PASSES' if edge > 0 and m > 0 else 'FAILS'} — the bar was "
          f"EDGE > 0 AND R/signal > 0, fixed before the run")


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = (await list_symbols(sess))[:SYMBOLS]
        print("Break-and-retest — the momentum mirror of Liquidity Entry Zones"
              f"\n{len(syms)} symbols · daily trend REQUIRED, not filtered · "
              f"24 descriptive cells, one pre-declared primary")
        hcache: dict = {}
        for tf, pages in TFS:
            data, days, offs = await collect(sess, syms, tf, pages, hcache)
            if days:
                report(tf, data, days, offs)


if __name__ == "__main__":
    asyncio.run(main())
