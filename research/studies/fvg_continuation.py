"""A SECOND STRATEGY: buy the gap in a trend, with no liquidity raid at all.

EVERYTHING THIS PROJECT HAS TESTED SO FAR IS THE SAME TRADE. Twelve entry
locations, twenty-five exits, seven pool parameters, order blocks, breakers,
sessions, liquidity targets — all of them variations on ONE model: liquidity
gets raided, structure shifts, price returns to a gap. When the variations all
come back inside noise, the honest reading is not that the variations were
badly chosen. It is that the model is what it is, and the remaining headroom is
somewhere else entirely.

SO THIS IS A DIFFERENT MODEL. No sweep, no pool, no shift. A displacement in
the direction of the higher-timeframe trend leaves a gap; price retraces into
it; you go with the trend. Reversal versus continuation — genuinely different
trades, at different times, on different bars, and potentially uncorrelated
with everything already deployed. That last part is worth as much as the edge:
a second stream that pays half as well but loses on different days is worth
more to an equity curve than a marginal improvement to the first.

THE TRAP IS OBVIOUS AND THE STUDY IS BUILT AROUND IT. "Enter with the Hour8
trend" is already the strongest filter in this system — the grade requires it,
and the daily POI gate that outranks everything is the same idea one timeframe
up. So a trend-continuation model will look profitable FOR REASONS THAT ARE
ALREADY DEPLOYED, and the gap will take credit for the trend filter's work.

  THE CONTROL IS THEREFORE THE PRIMARY TEST. Against every FVG entry sits a
  "any dip in the same trend" entry — a limit half an ATR below the close, stop
  one ATR under it, on bars sampled from the same trending population, with no
  gap required at all. If the FVG does not beat that, the FVG is decoration and
  the result is the Hour8 filter wearing a new hat.

PRE-REGISTERED, BEFORE THE FIRST NUMBER

  PRIMARY   The FVG continuation entry must beat the no-FVG control on R per
            bet, HELD OUT, by 2 SE. Being merely profitable is not enough and
            never was: the trend filter alone is profitable.

  SECOND    It must reproduce on Hour4, which carries 333 days against Min30's
            42. This check has now killed two candidates and it is the
            strongest one available.

  THIRD     Its OVERLAP with the deployed sweep model is reported. A second
            strategy that fires on the same bars as the first is not a second
            strategy, whatever it scores.

  REPORTED REGARDLESS: bets per day, because "every gap in a trend" is a very
  large number of signals and an untradeable stream is not a strategy either.

  EXPECTATION: it is profitable and it does NOT beat the control — the trend
  does the work and the gap is decoration. Recorded so it cannot be revised.

    PYTHONPATH=. RIPTIDE_MIN_GRADE=B python3 research/studies/fvg_continuation.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import statistics                                       # noqa: E402
from collections import defaultdict                     # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import CFG, TRACK_TARGET_R          # noqa: E402
from riptide.engine import (atr_series, entry_of,       # noqa: E402
                            run_engine)
from riptide.exchange import fetch_candles, list_symbols  # noqa: E402
from riptide.trend import direction_at                  # noqa: E402
from research.harness import mean_se, simulate          # noqa: E402

TFS = ("Min30", "Hour4")
CONTROL_EVERY = 10      # sample the control population, or it swamps everything
OVERLAP_BARS = 3        # how near a sweep signal counts as the same event


class Row:
    __slots__ = ("t", "r", "held", "overlap", "risk")


def gaps(cs, atr, lo=0):
    """Every FVG on the chart, by the engine's own definition.

    Deliberately the SAME construction as run_engine's gap search — bullish
    when cs[j].l > cs[j-2].h, bounded by min_fvg_atr and max_fvg_atr — so any
    difference between this model and the deployed one is the MODEL and not two
    slightly different ideas of what a gap is.
    """
    out = []
    for j in range(max(2, lo), len(cs)):
        a = atr[j]
        if not a:
            continue
        if cs[j].l > cs[j - 2].h:
            top, bot, bull = cs[j].l, cs[j - 2].h, True
        elif cs[j].h < cs[j - 2].l:
            top, bot, bull = cs[j - 2].l, cs[j].h, False
        else:
            continue
        size = top - bot
        if size < a * CFG.min_fvg_atr:
            continue
        if CFG.max_fvg_atr > 0 and size > a * CFG.max_fvg_atr:
            continue
        out.append((j, bull, top, bot, size / a))
    return out


def stops(cs, j, bull, top, bot):
    """{name: stop} — the two defensible places to put it for this model."""
    leg_lo = min(cs[k].l for k in range(j - 2, j + 1))
    leg_hi = max(cs[k].h for k in range(j - 2, j + 1))
    return {"stop at the gap's far edge": bot if bull else top,
            "stop under the whole leg": leg_lo if bull else leg_hi}


ARMS = (
    # (label, minimum gap size in ATR, stop key)
    ("gap >= 0.05 ATR (engine default)", 0.05, "stop at the gap's far edge"),
    ("gap >= 0.25 ATR", 0.25, "stop at the gap's far edge"),
    ("gap >= 0.50 ATR", 0.50, "stop at the gap's far edge"),
    ("gap >= 0.25 ATR, stop under leg", 0.25, "stop under the whole leg"),
)
CONTROL = "CONTROL: any dip in the trend, no gap"
COUNTER = "counter-trend gaps (the mirror)"


async def collect(sess, candles, tf, **fee):
    """Every continuation signal, its controls, and its overlap with the engine."""
    out = defaultdict(list)
    for sym, cs in candles.items():
        atr = atr_series(cs, CFG.atr_len)
        mid = cs[len(cs) // 2].t

        # Where the DEPLOYED model fired, so overlap is a fact and not a guess.
        early = []
        try:
            setups = run_engine(sym, cs, CFG, early_out=early)
        except Exception:
            setups = []
        idx = {c.t: i for i, c in enumerate(cs)}
        fired = set()
        for x in list(setups) + list(early):
            i = idx.get(getattr(x, "detected_time", 0)
                        or getattr(x, "fvg_time", 0))
            if i is not None:
                fired.update(range(i - OVERLAP_BARS, i + OVERLAP_BARS + 1))

        async def add(lab, j, entry, stop, is_long):
            if entry <= 0 or abs(entry - stop) <= 0:
                return
            if (entry <= stop) if is_long else (entry >= stop):
                return
            o = simulate(cs, j, entry, stop, is_long, target_r=TRACK_TARGET_R,
                         **fee)
            if not o.filled or o.exit_bar is None:
                return
            r = Row()
            r.t, r.r = cs[j].t, o.r
            r.held, r.overlap = cs[j].t < mid, j in fired
            r.risk = 100 * abs(entry - stop) / entry
            out[lab].append(r)

        for j, bull, top, bot, size_atr in gaps(cs, atr):
            d = await direction_at(sess, sym, cs[j].t, fetch_candles)
            if not d:
                continue
            agrees = (d > 0) == bull
            st = stops(cs, j, bull, top, bot)
            ent = entry_of(bull, top, bot, CFG.entry_mode)
            if agrees:
                for lab, floor, key in ARMS:
                    if size_atr >= floor:
                        await add(lab, j, ent, st[key], bull)
            else:
                await add(COUNTER, j, ent, st["stop at the gap's far edge"],
                          bull)

        # THE CONTROL. Same trending population, same timeframe, no gap
        # required: a limit half an ATR below the close with the stop one ATR
        # under it. If a gap entry cannot beat this, the gap is doing nothing
        # and what is being measured is the Hour8 trend filter.
        for j in range(CFG.atr_len, len(cs), CONTROL_EVERY):
            a = atr[j]
            if not a:
                continue
            d = await direction_at(sess, sym, cs[j].t, fetch_candles)
            if not d:
                continue
            bull = d > 0
            sgn = 1 if bull else -1
            ent = cs[j].c - sgn * 0.5 * a
            await add(CONTROL, j, ent, ent - sgn * a, bull)
    return out


def bets(rows):
    bybar = defaultdict(list)
    for r in rows:
        bybar[r.t].append(r.r)
    return [statistics.fmean(v) for v in bybar.values()]


def stat(rows):
    b = bets(rows)
    if len(b) < 20:
        return None
    m, se = mean_se(b)
    return dict(n=len(b), win=sum(1 for r in b if r > 0) / len(b), m=m, se=se,
                tot=sum(b),
                ov=sum(1 for r in rows if r.overlap) / len(rows),
                risk=statistics.fmean(r.risk for r in rows))


def panel(title, byl, days):
    print(f"\n{title}")
    print(f"  {'arm':<36}{'/day':>7}{'bets':>7}{'risk':>7}{'win':>6}"
          f"{'R/bet':>9}{'SE':>7}{'overlap':>9}   vs CONTROL")
    base = stat(byl.get(CONTROL, []))
    order = [lab for lab, _, _ in ARMS] + [COUNTER, CONTROL]
    for lab in order:
        s = stat(byl.get(lab, []))
        if not s:
            print(f"  {lab:<36}   too few")
            continue
        cmp = ""
        if base and lab != CONTROL:
            d = s["m"] - base["m"]
            se = (s["se"] ** 2 + base["se"] ** 2) ** 0.5
            cmp = f"{d:>+8.3f}  {d / se if se else 0:>+5.1f} SE"
        print(f"  {lab:<36}{s['n'] / days:>7.1f}{s['n']:>7}{s['risk']:>6.2f}%"
              f"{s['win']:>6.0%}{s['m']:>+9.3f}{s['se']:>7.3f}"
              f"{s['ov']:>8.0%}{cmp}")


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = await list_symbols(sess)
        for tf in TFS:
            cands = {}
            for sym in syms:
                try:
                    cs = await fetch_candles(sess, sym, tf)
                except Exception:
                    continue
                if len(cs) >= 300:
                    cands[sym] = cs
            if not cands:
                continue
            days = statistics.median((cs[-1].t - cs[0].t) / 86400
                                     for cs in cands.values())
            fresh = "  (FRESH — the out-of-sample check)" if tf == "Hour4" \
                else ""
            print(f"\n{'=' * 108}\nFVG CONTINUATION · {tf} · {len(cands)} "
                  f"symbols · {days:.0f} days · Hour8 trend must agree · "
                  f"target {TRACK_TARGET_R:g}R{fresh}\n{'=' * 108}")
            byl = await collect(sess, cands, tf)
            panel(f"{tf} — FULL WINDOW", byl, days)
            panel(f"{tf} — HELD OUT (older half)",
                  {k: [r for r in v if r.held] for k, v in byl.items()},
                  days / 2)
            # THE FEE DIAGNOSTIC, and it is not optional here. A 0.05 ATR gap
            # puts the stop about 0.025% away, where a 0.032% round trip costs
            # more than a whole R — so the ranking of these arms could be
            # nothing but the fee, ordered by how wide each one's stop happens
            # to be. Re-running at zero fees separates "this arm trades better"
            # from "this arm pays less to trade".
            zero = await collect(sess, cands, tf, fee_pct=0.0)
            panel(f"{tf} — HELD OUT, ZERO FEES (the diagnostic)",
                  {k: [r for r in v if r.held] for k, v in zero.items()},
                  days / 2)

    print(f"\nPRE-REGISTERED: beating the CONTROL held out by 2 SE is the test. "
          f"Being merely\nprofitable is not — the Hour8 trend filter is "
          f"profitable on its own, which is why\nit is already deployed. "
          f"'overlap' is the share of signals landing within "
          f"{OVERLAP_BARS} bars\nof a signal the existing engine already sent.")


if __name__ == "__main__":
    asyncio.run(main())
