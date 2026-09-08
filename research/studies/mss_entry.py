"""Enter at the MSS close instead of waiting for the pullback into the gap.

Asked after an XPL long that missed its limit by 0.12R and then ran 3%. The
question is fair and it has NOT been measured: `fills.py` tested a market entry
at the SIGNAL bar — the gap — which is later and a different price. This is the
entry taken the moment structure shifts, before the retracement that may never
come.

WHAT CHANGES, AND WHY IT IS NOT FREE

  fill rate     100%. That is the whole appeal and it is real.
  entry price   worse, always: the MSS close sits further from the stop than
                the gap does, because the gap IS the pullback.
  risk          therefore larger. The stop does not move — it is the raid
                extreme, the price at which the setup is wrong — so a worse
                entry inflates risk rather than tightening the stop.
  the target    2R of a LARGER R is further away in price. The same market
                move that paid 2R on the shipped entry pays less than 2R here.

So this is not "the same trade with a better fill". It is a different trade,
and the honest comparison needs both of the ways it can be scored:

  MSS market, 2R    keep the 2R shape, accept that the target is further away
  MSS market, same  keep the ORIGINAL target PRICE, accept an RR below 2
                    target price  — this is the version that asks "would I
                    have caught the move", which is what the missed chart
                    actually shows

ORDERING MATTERS. `detected_time` is max(mss_time, fvg_time): sometimes the
gap forms BEFORE the shift confirms, in which case "after the MSS candle" is
already the alert bar and there is nothing new to test. Those are reported
separately rather than blended, because averaging two different questions is
how a null becomes a finding.

Split by POI, which is what was asked, and by grade.

    PYTHONPATH=. python3 research/studies/mss_entry.py
"""
from __future__ import annotations

import research.env  # noqa: F401  (must precede riptide.config)

import asyncio
import statistics

import aiohttp

from riptide.config import CFG, BAR_SECONDS
from riptide.engine import atr_series, grade_of, run_engine
from riptide.exchange import list_symbols
from riptide.trend import supertrend, di_direction
from research.harness import Outcome, mean_se, simulate
from research.studies.mtf_grid import (FEE, FILL_HOURS, HORIZON_HOURS,
                                       fetch_paged, zones_of, in_poi,
                                       htf_dir_at)

HTF = "Day1"
TFS = ("Min30", "Min15")


def market_at(cs, bar: int, entry: float, stop: float, is_long: bool, *,
              target_r: float = 2.0, target_px: float | None = None,
              horizon_bars: int = 60, fee_maker: float = 0.02,
              fee_taker: float = 0.06) -> Outcome | None:
    """A MARKET entry filled at `entry` on `bar`, scored like harness.simulate.

    simulate() cannot do this: it fills a LIMIT by waiting for price to touch
    the level, which for a long means waiting for a move DOWN. A market entry
    is filled at that price immediately, and it pays TAKER on the way in —
    which is the second cost of this idea and is easy to forget.

    Mirrors simulate's conventions exactly so the two are comparable: stop
    wins a bar that spans both, the target cannot resolve on the entry bar,
    and fees are charged in R as fee / risk_pct.
    """
    risk = abs(entry - stop)
    if risk <= 0 or entry <= 0 or bar >= len(cs) - 1:
        return None
    sgn = 1 if is_long else -1
    tgt = target_px if target_px is not None else entry + sgn * risk * target_r
    # Entry is a market order: taker in. Out is maker on a target, taker on a
    # stop — the same split simulate uses.
    to_r = 1.0 / (100 * risk / entry)
    fee_win = (fee_taker + fee_maker) * to_r
    fee_lose = (fee_taker + fee_taker) * to_r
    mfe = mae = 0.0
    for k in range(bar, min(bar + horizon_bars, len(cs))):
        c = cs[k]
        fav = (c.h - entry) / risk if is_long else (entry - c.l) / risk
        adv = (c.l - entry) / risk if is_long else (entry - c.h) / risk
        mfe, mae = max(mfe, fav), min(mae, adv)
        if (c.l <= stop) if is_long else (c.h >= stop):
            return Outcome(-1.0 - fee_lose, True, bar, mfe, mae, k)
        if k == bar:
            continue
        if (c.h >= tgt) if is_long else (c.l <= tgt):
            return Outcome(sgn * (tgt - entry) / risk - fee_win,
                           True, bar, mfe, mae, k)
    last = min(bar + horizon_bars, len(cs)) - 1
    return Outcome(sgn * (cs[last].c - entry) / risk - fee_lose,
                   True, bar, mfe, mae, last)


async def collect():
    out, days = [], []
    async with aiohttp.ClientSession() as sess:
        for sym in await list_symbols(sess):
            try:
                hcs = await fetch_paged(sess, sym, HTF, 1)
            except Exception:
                continue
            if len(hcs) < 60:
                continue
            zones = zones_of(hcs, atr_series(hcs, CFG.atr_len))
            hst, hdi = supertrend(hcs), di_direction(hcs)
            for tf in TFS:
                try:
                    cs = await fetch_paged(sess, sym, tf, 1)
                except Exception:
                    continue
                if len(cs) < 300:
                    continue
                step = BAR_SECONDS[tf]
                if tf == TFS[0]:
                    days.append((cs[-1].t - cs[0].t) / 86400)
                idx = {c.t: i for i, c in enumerate(cs)}
                # Confirmed setups only. An EARLY signal has no structure
                # shift at all — "after the MSS candle" does not exist for it.
                for x in run_engine(sym, cs, CFG):
                    i = idx.get(x.detected_time)
                    m = idx.get(x.mss_time)
                    if i is None or m is None:
                        continue
                    poi = in_poi(zones, cs[i].t, x.stop, x.is_long,
                                 BAR_SECONDS[HTF])
                    d = htf_dir_at(hcs, hst, hdi, cs[i].t)
                    risk0 = abs(x.entry - x.stop)
                    mss_px = cs[m].c
                    risk1 = abs(mss_px - x.stop)
                    if risk0 <= 0 or risk1 <= 0:
                        continue
                    # Entering the wrong side of the stop is not a trade.
                    if (mss_px <= x.stop) if x.is_long else (mss_px >= x.stop):
                        continue
                    hb = HORIZON_HOURS * 3600 // step
                    shipped = simulate(cs, i, x.entry, x.stop, x.is_long,
                                       fill_bars=FILL_HOURS * 3600 // step,
                                       horizon_bars=hb, **FEE)
                    if shipped.filled and shipped.exit_bar is None:
                        continue
                    sgn = 1 if x.is_long else -1
                    a = market_at(cs, m, mss_px, x.stop, x.is_long,
                                  target_r=2.0, horizon_bars=hb)
                    b = market_at(cs, m, mss_px, x.stop, x.is_long,
                                  target_px=x.entry + sgn * risk0 * 2.0,
                                  horizon_bars=hb)
                    if a is None or b is None:
                        continue
                    out.append(dict(
                        tf=tf, poi=bool(poi),
                        grade=grade_of(False, poi, d, x.is_long, d)[0],
                        gap_first=x.fvg_time < x.mss_time,
                        shipped=shipped, mss2r=a, mss_px=b,
                        inflate=risk1 / risk0))
    return out, (statistics.median(days) if days else 42.0)


def line(lab, rows, key, filled_only=False):
    if len(rows) < 20:
        print(f"  {lab:<30}{len(rows):>6}   too few")
        return
    os_ = [r[key] for r in rows]
    rs = [o.r for o in os_]
    fills = [o for o in os_ if o.filled]
    wins = [o for o in fills if o.r > 0]
    losses = [o for o in fills if o.r <= 0]
    aw = statistics.fmean([o.r for o in wins]) if wins else 0.0
    al = statistics.fmean([o.r for o in losses]) if losses else 0.0
    m, se = mean_se(rs)
    print(f"  {lab:<30}{len(rows):>6}{len(fills) / len(rows):>7.0%}"
          f"{(len(wins) / len(fills) if fills else 0):>7.0%}"
          f"{(aw / abs(al) if al else 0):>6.2f}"
          f"{m:>+11.3f} ± {se:.3f}{sum(rs):>+9.1f}")


HEAD = (f"  {'':<30}{'n':>6}{'fill':>7}{'win':>7}{'RR':>6}"
        f"{'R/signal':>17}{'total':>9}")


def block(title, rows):
    print(f"\n{title}  ({len(rows)} setups)")
    print(HEAD)
    line("shipped: limit at the gap", rows, "shipped")
    line("MSS close, 2R of new risk", rows, "mss2r")
    line("MSS close, same target px", rows, "mss_px")
    if rows:
        infl = statistics.median([r["inflate"] for r in rows])
        print(f"  {'':<30}risk is {infl:.2f}x larger entering at the MSS close")


def main():
    rows, span = asyncio.run(collect())
    fresh = [r for r in rows if not r["gap_first"]]
    same = [r for r in rows if r["gap_first"]]
    print(f"\n{len(rows)} confirmed setups over {span:.0f} days · fees in · "
          f"unfilled shipped entries counted as zero")
    print(f"{len(same)} of them had the gap form BEFORE the shift, where the "
          f"MSS close IS\nthe alert bar — reported separately, not blended.\n")

    print("=" * 82)
    print("THE SHIFT CONFIRMED LAST — the real question")
    print("=" * 82)
    block("all", fresh)
    block("inside a daily POI", [r for r in fresh if r["poi"]])
    block("outside a POI", [r for r in fresh if not r["poi"]])
    for g in ("A", "C"):
        sub = [r for r in fresh if r["poi"] and r["grade"] == g]
        if len(sub) >= 20:
            block(f"grade {g} (POI + graded)", sub)

    print("\n" + "=" * 82)
    print("THE GAP CAME FIRST — here the MSS close is the alert bar")
    print("=" * 82)
    block("all", same)


if __name__ == "__main__":
    main()
