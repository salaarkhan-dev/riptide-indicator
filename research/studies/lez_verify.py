"""Is the Python port actually the same script as the Pine? A diffable list.

Every number in `MEASUREMENTS.md` about Liquidity Entry Zones rests on
`research/studies/lez.py` being a faithful port of
`liquidity-entry-zones.pine`. That has been argued from a careful reading and
never CHECKED against the chart, and this project's own history says a comment
is not evidence — the sign bug survived a correct pre-registration because
nobody verified that `supertrend()` meant what its comment said.

So this prints what the port thinks, in a form that can be put next to
TradingView and diffed by eye in two minutes.

WHAT TO COMPARE, in order of what would matter most if it disagrees

  1  THE COUNT. Set the chart to the same symbol and timeframe, switch
     `showStoppedTrades` ON and `blockSignalsInTrade` OFF, and count the BUY
     and SELL labels over the window this prints. The `unblocked` figure is
     the one to match; `blocked` is what the chart shows with the default
     `blockSignalsInTrade = true` and is printed for the same reason.

  2  THE TIMESTAMPS. Every signal is listed with its bar's UTC open time. One
     that exists here and not on the chart, or vice versa, is a real
     discrepancy and worth more than any statistic in this repo.

  3  THE PRICES. Entry is the confirmation bar's close, so it is checkable
     against the candle directly.

  4  THE STAGE COUNTS. If the totals disagree, these say WHERE: pivots stored,
     bars with a valid sweep, confirmations before the cooldown, and signals
     after it. A port that finds the right sweeps and the wrong signals is a
     different bug from one that finds no sweeps.

TWO KNOWN, MEASURED DIFFERENCES, BOTH REPORTED HERE RATHER THAN ASSUMED AWAY

  ATR WARM-UP. Pine's `ta.atr(14)` is `na` for the first 13 bars, so
  `minSweepDistancePx` is `na` and no sweep can be valid. `riptide.engine.rma`
  instead returns a partial average over those bars, so the port CAN fire
  there. It affects only the opening bars of a series and the count is printed.

  PIVOT TIES. `ta.pivothigh` and this port both treat a pivot as strictly
  greater than its neighbours. If TradingView admits ties the level set would
  differ; the number of bars where a tie would have changed the answer is
  counted, so the question stops being theoretical.

    PYTHONPATH=. python3 research/studies/lez_verify.py [SYMBOL] [TF]
    PYTHONPATH=. python3 research/studies/lez_verify.py ETH_USDT Min30
"""
from __future__ import annotations

import research.env  # noqa: F401  (must precede riptide.config)

import asyncio
import sys
from datetime import datetime, timezone

import aiohttp

from riptide.engine import atr_series
from research.studies.lez import P, ema_series, lez_signals, pivots
from research.studies.mtf_grid import fetch_paged

SYMBOL = sys.argv[1] if len(sys.argv) > 1 else "ETH_USDT"
TF = sys.argv[2] if len(sys.argv) > 2 else "Min30"
PAGES = 1
SHOW = 40                 # most recent signals to list


def ts(t: int) -> str:
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d %H:%M")


def stages(cs, p=P):
    """Re-walk the model counting each stage, so a disagreement can be located
    rather than guessed at. Mirrors lez_signals exactly; if the two ever drift
    this file is worthless, so the signal count is asserted against it."""
    atr = atr_series(cs, p.atr_len)
    ema = ema_series(cs, p.ema_len)
    hi_piv, lo_piv = pivots(cs, p.pivot_len)
    hi_at, lo_at = {}, {}
    for c, j, px in hi_piv:
        hi_at.setdefault(c, []).append((j, px))
    for c, j, px in lo_piv:
        lo_at.setdefault(c, []).append((j, px))

    stored_hi, stored_lo = [], []
    n_sweep = n_conf = n_cool = 0
    warm = 0            # bars where Pine's ATR is still na but ours is not
    ties = 0            # bars where a tie would have changed the pivot set
    pend_bull = pend_bear = None
    last = None

    for i, c in enumerate(cs):
        for j, px in hi_at.get(i, []):
            stored_hi.append((j, px))
            del stored_hi[:-p.stored_levels]
        for j, px in lo_at.get(i, []):
            stored_lo.append((j, px))
            del stored_lo[:-p.stored_levels]
        # A tie in the pivot window: strict-vs-loose would disagree here.
        n = p.pivot_len
        if n <= i < len(cs) - n:
            w = [cs[k].h for k in range(i - n, i + n + 1)]
            if w.count(max(w)) > 1:
                ties += 1
        if i < p.atr_len:
            warm += 1
            continue
        a = atr[i]
        rng = c.h - c.l
        if a <= 0 or rng <= 0:
            continue
        body_pct = abs(c.c - c.o) / rng
        up = (c.h - max(c.o, c.c)) / rng
        dn = (min(c.o, c.c) - c.l) / rng
        mid = (c.h + c.l) / 2.0
        ms = p.min_sweep_atr * a
        s_hi = s_lo = None
        for j, px in reversed(stored_hi):
            if j < i and c.h > px and (c.h - px) >= ms:
                s_hi = px
                break
        for j, px in reversed(stored_lo):
            if j < i and c.l < px and (px - c.l) >= ms:
                s_lo = px
                break
        v_sell = (s_hi is not None and c.c < s_hi and up >= p.min_wick_pct
                  and body_pct <= p.max_body_pct and rng >= p.min_range_atr * a)
        v_buy = (s_lo is not None and c.c > s_lo and dn >= p.min_wick_pct
                 and body_pct <= p.max_body_pct and rng >= p.min_range_atr * a)
        n_sweep += v_sell or v_buy
        if v_buy:
            pend_bull = dict(bar=i, mid=mid)
        if v_sell:
            pend_bear = dict(bar=i, mid=mid)
        e = ema[i]
        bull_ema = (not p.use_ema) or (e is not None and c.c > e)
        bear_ema = (not p.use_ema) or (e is not None and c.c < e)
        b_open = pend_bull and (i - pend_bull["bar"] <= p.confirm_window)
        s_open = pend_bear and (i - pend_bear["bar"] <= p.confirm_window)
        buy = bool(b_open and ((not p.require_bull_body) or c.c > c.o)
                   and bull_ema
                   and ((not p.require_midline) or c.c > pend_bull["mid"]))
        sell = bool(s_open and ((not p.require_bear_body) or c.c < c.o)
                    and bear_ema
                    and ((not p.require_midline) or c.c < pend_bear["mid"]))
        n_conf += buy or sell
        cool = last is None or (i - last > p.cooldown_bars)
        fired = (buy or sell) and cool
        n_cool += fired
        if fired:
            last = i
        if (buy and cool) or (pend_bull and i - pend_bull["bar"] > p.confirm_window):
            pend_bull = None
        if (sell and cool and not (buy and cool)) or \
                (pend_bear and i - pend_bear["bar"] > p.confirm_window):
            pend_bear = None
    return dict(pivots=len(hi_piv) + len(lo_piv), sweeps=n_sweep,
                confirms=n_conf, signals=n_cool, warm=warm, ties=ties)


def serialise(sigs, cs, horizon=96):
    """Which signals the chart would actually PRINT with the shipped default
    `blockSignalsInTrade = true`: a signal is suppressed while the previous
    simulated trade is still open. Resolved with the same rules the Pine uses —
    stop wins a bar spanning both, and the entry bar resolves nothing."""
    out, busy = [], -1
    for s in sigs:
        if s.bar <= busy:
            continue
        out.append(s)
        tgt = s.entry + (1 if s.is_long else -1) * abs(s.entry - s.stop) * P.target_r
        end = min(s.bar + 1 + horizon, len(cs))
        busy = end - 1
        for k in range(s.bar + 1, end):
            c = cs[k]
            if (c.l <= s.stop) if s.is_long else (c.h >= s.stop):
                busy = k
                break
            if (c.h >= tgt) if s.is_long else (c.l <= tgt):
                busy = k
                break
    return out


async def main():
    async with aiohttp.ClientSession() as sess:
        cs = await fetch_paged(sess, SYMBOL, TF, PAGES)
    if len(cs) < 300:
        print(f"only {len(cs)} candles for {SYMBOL} {TF}")
        return
    st = stages(cs)
    sigs = lez_signals(cs)
    blocked = serialise(sigs, cs)

    print(f"PORT vs PINE — {SYMBOL} {TF}")
    print(f"window   {ts(cs[0].t)}  ->  {ts(cs[-1].t)} UTC   ({len(cs)} bars)")
    print(f"settings pivot {P.pivot_len} · stored {P.stored_levels} · sweep "
          f">= {P.min_sweep_atr:g} ATR · wick >= {P.min_wick_pct:g} · body <= "
          f"{P.max_body_pct:g}\n         range >= {P.min_range_atr:g} ATR · "
          f"window {P.confirm_window} · cooldown {P.cooldown_bars} · EMA "
          f"{P.ema_len}{'' if P.use_ema else ' (OFF)'} · reclaim "
          f"{'Strong' if P.strong_reclaim else 'Close Back Inside'}")
    print(f"\nSTAGE COUNTS — where to look if the totals disagree")
    print(f"  pivots stored                 {st['pivots']}")
    print(f"  bars with a valid sweep       {st['sweeps']}")
    print(f"  confirmations before cooldown {st['confirms']}")
    print(f"  signals after cooldown        {st['signals']}")
    assert st["signals"] == len(sigs), (st["signals"], len(sigs))
    print(f"\nSIGNAL COUNT")
    print(f"  unblocked  {len(sigs):>4}   <- match this with blockSignalsInTrade OFF")
    print(f"  blocked    {len(blocked):>4}   <- what the chart shows by default")
    print(f"\nKNOWN DIFFERENCES, counted rather than assumed")
    print(f"  bars where Pine's ATR is still na but ours is not: {st['warm']}"
          f"   (no signal can fire there in Pine)")
    print(f"  bars where a pivot TIE could change the level set: {st['ties']}"
          f"   ({st['ties'] / len(cs):.2%} of bars)")

    print(f"\nLAST {SHOW} SIGNALS — put these next to the chart")
    print(f"  {'bar time (UTC)':<18}{'side':<6}{'entry':>12}{'stop':>12}"
          f"{'target 2R':>12}{'Q':>5}{'confirm':>9}")
    for s in sigs[-SHOW:]:
        risk = abs(s.entry - s.stop)
        tgt = s.entry + (1 if s.is_long else -1) * risk * 2.0
        print(f"  {ts(cs[s.bar].t):<18}{'LONG' if s.is_long else 'SHORT':<6}"
              f"{s.entry:>12.6g}{s.stop:>12.6g}{tgt:>12.6g}"
              f"{s.score:>5.0f}"
              f"{('same bar' if s.bars_to_confirm == 0 else '+%d bars' % s.bars_to_confirm):>9}")


if __name__ == "__main__":
    asyncio.run(main())
