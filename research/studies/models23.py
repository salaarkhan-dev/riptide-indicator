"""Models 2 and 3: the two SMC entry models Riptide does NOT implement.

Model 1 (sweep -> CHOCH -> entry at the gap, stop past the sweep) is what the
engine already is, and it is measured to death. These two are structurally
different in one specific way that makes them worth the work: NEITHER REQUIRES
A LIQUIDITY SWEEP. Every signal this project has ever scored began with a raid.
If the raid is the thing carrying the edge — which five separate stop studies
now suggest, since the raid extreme is the only stop level that survives — then
both of these should be materially worse, and that is a real prediction rather
than a hedge.

  MODEL 2  ORDER BLOCK CONTINUATION
    trend making higher highs and higher lows, a break of structure in the
    trend direction, then entry on the pullback into the unmitigated order
    block that caused the break. Stop behind the block. The "ideally an FVG
    next to it" condition is tested as its own arm rather than assumed.

  MODEL 3  FVG SNIPER
    a displacement large enough to leave a clear gap, entered at the gap edge
    or its 50% mark, stop behind the candle that created it. No structure
    requirement at all beyond the displacement itself.

Both are scored through the same harness, on the same symbols and window, with
the same fees and the same wall-clock exit windows as everything else, so the
numbers sit directly beside Model 1's. Both also get the daily-POI arm, since
that is the one filter that survived a held-out test.

STOP SIZES ARE NOT COMPARABLE ACROSS MODELS, which is why risk% is printed.
Model 3's stop sits behind one candle and will be tight; a tight stop is not a
virtue on its own, it is a bet that the level under it means something, and R
already accounts for the size. The fee in R is FEE/risk%, so a tight stop is
also a dearer stop per unit of risk.
"""
from __future__ import annotations

import research.env  # noqa: F401  (must precede riptide.config)

import asyncio
import statistics

import aiohttp

from riptide.config import CFG, BAR_SECONDS
from riptide.engine import (atr_series, is_pivot_high, is_pivot_low,
                            run_engine)
from riptide.trend import supertrend, di_direction
from research.data import SYMBOLS
from research.harness import mean_se, simulate
from research.studies.mtf_grid import (FEE, FILL_HOURS, HORIZON_HOURS,
                                       fetch_paged, zones_of, in_poi,
                                       htf_dir_at)

LTF, HTF = "Min30", "Day1"
PIV = 3
BUF = 0.1          # stop buffer in ATR, as a fraction of the signal-bar ATR


class Sig:
    __slots__ = ("bar", "is_long", "entry", "stop", "tag")

    def __init__(self, bar, is_long, entry, stop, tag=""):
        self.bar, self.is_long, self.entry = bar, is_long, entry
        self.stop, self.tag = stop, tag


# ------------------------------------------------------- Model 2: OB continuation

def model2(cs, atr):
    """Break of structure in an established trend -> entry at the order block
    that caused it.

    Structure is tracked with confirmed pivots only, so nothing here can see a
    swing before it was confirmable: a pivot at bar i is not known until bar
    i+PIV, and the BOS check runs at the bar that breaks the level.
    """
    highs, lows = [], []          # (bar, price), confirmed pivots only
    out = []
    for i in range(PIV, len(cs)):
        j = i - PIV               # the bar that could now be a confirmed pivot
        if is_pivot_high(cs, j, PIV, PIV):
            highs.append((j, cs[j].h))
        if is_pivot_low(cs, j, PIV, PIV):
            lows.append((j, cs[j].l))
        a = atr[i]
        if a <= 0 or len(highs) < 2 or len(lows) < 2:
            continue

        for is_long in (True, False):
            # Established trend: the last two confirmed swings both ascending
            # (bullish) or both descending (bearish).
            if is_long:
                trend = (highs[-1][1] > highs[-2][1] and lows[-1][1] > lows[-2][1])
                broke = cs[i].c > highs[-1][1] and cs[i - 1].c <= highs[-1][1]
                ref = highs[-1][0]
            else:
                trend = (highs[-1][1] < highs[-2][1] and lows[-1][1] < lows[-2][1])
                broke = cs[i].c < lows[-1][1] and cs[i - 1].c >= lows[-1][1]
                ref = lows[-1][0]
            if not (trend and broke) or ref >= i:
                continue

            # The order block: last opposite-closing candle before the leg
            # that broke structure.
            ob = -1
            for k in range(i, max(ref - 1, i - 20), -1):
                if (cs[k].c < cs[k].o) if is_long else (cs[k].c > cs[k].o):
                    ob = k
                    break
            if ob < 0:
                continue

            entry = cs[ob].h if is_long else cs[ob].l
            stop = (cs[ob].l - a * BUF) if is_long else (cs[ob].h + a * BUF)
            if (stop >= entry) if is_long else (stop <= entry):
                continue
            # Entry must still be a pullback: price has to come BACK to the
            # block. If the break bar already closed on the wrong side there
            # is nothing to wait for.
            if (cs[i].c <= entry) if is_long else (cs[i].c >= entry):
                continue
            if CFG.max_risk_atr > 0 and abs(entry - stop) > a * CFG.max_risk_atr:
                continue

            # Adjacent FVG — the "it should have an FVG next to it" condition,
            # kept as a tag so it can be priced rather than assumed.
            fvg = False
            for k in range(ob + 1, min(ob + 4, len(cs))):
                if k >= 2 and ((cs[k].l > cs[k - 2].h) if is_long
                               else (cs[k].h < cs[k - 2].l)):
                    fvg = True
                    break
            out.append(Sig(i, is_long, entry, stop, "fvg" if fvg else ""))
    return out


# ------------------------------------------------------------ Model 3: FVG sniper

def model3(cs, atr, min_disp=1.0, mode="proximal"):
    """A displacement bar big enough to leave a gap; entry at the gap, stop
    behind the candle that created it."""
    out = []
    for j in range(2, len(cs)):
        a = atr[j]
        if a <= 0:
            continue
        body = abs(cs[j - 1].c - cs[j - 1].o)
        if body < min_disp * a:
            continue
        if cs[j].l > cs[j - 2].h and cs[j - 1].c > cs[j - 1].o:
            is_long, top, bot = True, cs[j].l, cs[j - 2].h
        elif cs[j].h < cs[j - 2].l and cs[j - 1].c < cs[j - 1].o:
            is_long, top, bot = False, cs[j - 2].l, cs[j].h
        else:
            continue
        entry = (top if is_long else bot) if mode == "proximal" else \
                (top + bot) / 2.0
        # "Behind the candle that created the gap" — the displacement bar.
        stop = (cs[j - 1].l - a * BUF) if is_long else (cs[j - 1].h + a * BUF)
        if (stop >= entry) if is_long else (stop <= entry):
            continue
        if CFG.max_risk_atr > 0 and abs(entry - stop) > a * CFG.max_risk_atr:
            continue
        out.append(Sig(j, is_long, entry, stop))
    return out


# --------------------------------------------------------------------- scoring

def score(sigs, cs, fill, hor, zones=None, hcs=None, hst=None, hdi=None,
          hstep=0, need_poi=False, need_dir=False, need_tag=""):
    outs, risks = [], []
    for s in sigs:
        if need_tag and s.tag != need_tag:
            continue
        if need_poi and not in_poi(zones, cs[s.bar].t, s.stop, s.is_long, hstep):
            continue
        if need_dir:
            if htf_dir_at(hcs, hst, hdi, cs[s.bar].t) != (1 if s.is_long else -1):
                continue
        outs.append(simulate(cs, s.bar, s.entry, s.stop, s.is_long,
                             fill_bars=fill, horizon_bars=hor, **FEE))
        risks.append(100 * abs(s.entry - s.stop) / s.entry)
    return outs, risks


def show(lab, outs, risks):
    if len(outs) < 25:
        print(f"  {lab:<34} n={len(outs):<5} too few")
        return
    rs = [o.r for o in outs]
    fill = sum(o.filled for o in outs) / len(outs)
    won = [o for o in outs if o.filled]
    win = sum(o.r > 0 for o in won) / len(won) if won else 0.0
    m, se = mean_se(rs)
    print(f"  {lab:<34} n={len(outs):<5} fill {fill:5.1%}  win {win:5.1%}"
          f"  risk {statistics.fmean(risks):4.2f}%  {m:+.3f} ± {se:.3f}"
          f"  tot {sum(rs):+7.1f}")


async def main():
    step_l, step_h = BAR_SECONDS[LTF], BAR_SECONDS[HTF]
    fill = FILL_HOURS * 3600 // step_l
    hor = HORIZON_HOURS * 3600 // step_l
    acc = {}

    def add(key, o, r):
        a, b = acc.setdefault(key, ([], []))
        a.extend(o)
        b.extend(r)

    async with aiohttp.ClientSession() as sess:
        for sym in SYMBOLS:
            try:
                cs = await fetch_paged(sess, sym, LTF, 1)
                hcs = await fetch_paged(sess, sym, HTF, 1)
            except Exception:
                continue
            if len(cs) < 300 or len(hcs) < 60:
                continue
            atr = atr_series(cs, CFG.atr_len)
            zones = zones_of(hcs, atr_series(hcs, CFG.atr_len))
            hst, hdi = supertrend(hcs), di_direction(hcs)
            ctx = dict(zones=zones, hcs=hcs, hst=hst, hdi=hdi, hstep=step_h)

            m1 = run_engine(sym, cs, CFG)
            idx = {c.t: i for i, c in enumerate(cs)}
            m1s = [Sig(idx[s.detected_time], s.is_long, s.entry, s.stop)
                   for s in m1 if s.detected_time in idx]
            m2 = model2(cs, atr)
            m3p = model3(cs, atr, 1.0, "proximal")
            m3m = model3(cs, atr, 1.0, "mid")
            m3big = model3(cs, atr, 1.5, "proximal")

            for name, sigs, tag in (
                    ("M1 sweep->CHOCH  <- shipped", m1s, ""),
                    ("M2 OB continuation", m2, ""),
                    ("M2 OB + adjacent FVG", m2, "fvg"),
                    ("M3 FVG sniper, gap edge", m3p, ""),
                    ("M3 FVG sniper, 50% of gap", m3m, ""),
                    ("M3 FVG, displacement >1.5 ATR", m3big, "")):
                for arm, kw in (("", {}), (" + daily POI", dict(need_poi=True)),
                                (" + trend", dict(need_dir=True)),
                                (" + both", dict(need_poi=True, need_dir=True))):
                    o, r = score(sigs, cs, fill, hor, need_tag=tag, **ctx, **kw)
                    add(name + arm, o, r)

    print(f"\n{LTF} structure, {HTF} context, {len(SYMBOLS)} symbols, "
          f"fill {fill} bars, horizon {hor} bars\n")
    for name in ("M1 sweep->CHOCH  <- shipped", "M2 OB continuation",
                 "M2 OB + adjacent FVG", "M3 FVG sniper, gap edge",
                 "M3 FVG sniper, 50% of gap", "M3 FVG, displacement >1.5 ATR"):
        for arm in ("", " + daily POI", " + trend", " + both"):
            key = name + arm
            if key in acc:
                show(key, *acc[key])
        print()


if __name__ == "__main__":
    asyncio.run(main())
