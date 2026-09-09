"""An EXACT port of `halftrend.pine` — the signal engine AND its own scoreboard.

Separate from Riptide entirely. It shares the candle fetcher and the scorer and
nothing else: no cluster, no POI, no grade, no `sweep_worth`. Riptide's settings
do not reach it and its results do not reach Riptide's.

WHY THE INDICATOR'S OWN WIN COUNTER IS PORTED TOO

The chart reports a win rate. That number is what prompted the measurement, so
reproducing it is not a curiosity — it is the only way to show, on the same
candles, what the difference between it and an honest score actually is. Both
are computed here from one pass, and `halftrend_measure.py` prints them side by
side.

WHAT THE DASHBOARD COUNTER DOES, read off the source line by line

    if high >= activeTP1:  wins += 1; activeTP1 := na; longTPHit1 := true
    else if high >= activeTP2: wins += 1; activeTP2 := na
    else if high >= activeTP3: wins += 1; activeTP3 := na; tradeState := 0
    if low <= activeSL:
        losses += 1; tradeState := 0
        if longTPHit1:  wins -= 1; losses -= 1

Three consequences, none of them a matter of opinion:

  ONE TRADE CAN BOOK THREE WINS. The targets are cleared to `na` one per bar,
  so a move that runs to TP3 credits +1 at TP1, then +1 at TP2 on a later bar,
  then +1 at TP3. Three entries in the counter, one trade.

  A TRADE THAT HITS TP1 AND THEN STOPS OUT VANISHES. `longTPHit1` is set at
  TP1, and on the stop the correction subtracts one from BOTH counters — so the
  win it booked is removed and the loss is never recorded. The trade leaves no
  trace in either column. That is the single largest effect: it deletes exactly
  the marginal losers.

  THE HEADLINE R:R IS 1:3 BUT THE WIN IS COUNTED AT 1R. `activeTP1` is one
  risk unit away. The dashboard prints "Target R:R  1 : 3" beside a win rate
  earned at TP1.

None of that is repainting or lookahead — the signal engine is clean on both
counts (see below). It is an accounting artefact, and it is reproduced exactly
rather than described, so the size of it is measured rather than asserted.

REPAINT AND LOOKAHEAD — the engine is clean

  `buySignal = trend == 0 and trend[1] == 1 and barstate.isconfirmed`. The
  `barstate.isconfirmed` guard means a signal exists only on a closed bar.

  `ta.highestbars` / `ta.lowestbars` / `ta.sma` / `ta.atr` all read backwards
  only. `high[math.abs(ta.highestbars(high, amplitude))]` is the high of the
  highest bar in the last `amplitude` bars — past bars, no future.

  The one `request.security` call feeds the multi-asset dashboard, not the
  signal, and uses `timeframe.period` with v6's default `lookahead_off`.

  So the trend state machine is path-dependent but never forward-looking.

THE ONE PLACE THIS PORT CANNOT BE CERTAIN, stated rather than buried

Pine seeds `var float maxLowPrice = low` and `var float minHighPrice = high` on
bar 0, where `ta.highestbars` is still `na`, and then folds `na` into them with
`math.max`/`math.min`. What Pine does with `na` there is not something this
file can resolve without a Pine interpreter. The port instead starts the state
machine at bar `amplitude`, where every input is valid, and seeds the two
extremes from that bar. It affects the first 20 bars of a series of thousands
and cannot touch the trend state once it has converged — but it is a
difference, and `halftrend.py` prints a diffable signal list so the chart can
settle it.

    PYTHONPATH=. python3 research/studies/halftrend.py ETH_USDT Min30
"""
from __future__ import annotations

import research.env  # noqa: F401  (must precede riptide.config)

from dataclasses import dataclass

from riptide.engine import atr_series

AMPLITUDE = 20          # `amplitude`
CHANNEL_DEV = 2.0       # `channelDeviation` — bands only, no signal effect
BASE_RISK_MULT = 3.0    # `baseRiskMult`
ATR_LEN = 100           # ta.atr(100); the engine uses atr/2 throughout


@dataclass
class Signal:
    bar: int            # the bar the flip is confirmed on; entry is its close
    is_long: bool
    entry: float        # close of that bar, as the Pine sets entryPx
    stop: float         # entry -/+ atr2 * baseRiskMult
    tp1: float
    tp2: float
    tp3: float
    atr2: float


def sma(vals, n):
    out, run = [None] * len(vals), 0.0
    for i, v in enumerate(vals):
        run += v
        if i >= n:
            run -= vals[i - n]
        out[i] = run / n if i >= n - 1 else None
    return out


def halftrend_signals(cs, amplitude=AMPLITUDE, atr_len=ATR_LEN,
                      risk_mult=BASE_RISK_MULT) -> list[Signal]:
    """Every LONG/SHORT flip the indicator prints, in bar order.

    Mirrors the Pine's per-bar order: the trend matrix first, then the baseline
    paths, then the signal test. `trend == 0` is bullish and `trend == 1` is
    bearish, which is the opposite of the intuitive reading and is why the
    signal test looks inverted.
    """
    n = len(cs)
    atr = atr_series(cs, atr_len)
    highs = [c.h for c in cs]
    lows = [c.l for c in cs]
    highma, lowma = sma(highs, amplitude), sma(lows, amplitude)

    trend = next_trend = 0
    prev_trend = None
    up = down = 0.0
    prev_up = prev_down = None
    max_low = min_high = None
    out: list[Signal] = []

    for i in range(n):
        # Every input valid: highestbars/lowestbars need `amplitude` bars, the
        # SMAs need `amplitude`, the ATR needs `atr_len`.
        if i < amplitude or i < atr_len - 1 or highma[i] is None:
            continue
        if max_low is None:                 # seed, see the module docstring
            max_low, min_high = cs[i].l, cs[i].h

        a2 = atr[i] / 2.0
        if a2 <= 0:
            continue
        win = range(i - amplitude + 1, i + 1)
        high_price = max(cs[k].h for k in win)     # high[abs(highestbars)]
        low_price = min(cs[k].l for k in win)      # low[abs(lowestbars)]
        c = cs[i]
        prev_low = cs[i - 1].l if i else c.l       # nz(low[1], low)
        prev_high = cs[i - 1].h if i else c.h

        # --- the trend matrix
        if next_trend == 1:
            max_low = max(low_price, max_low)
            if highma[i] < max_low and c.c < prev_low:
                trend, next_trend = 1, 0
                min_high = high_price
        else:
            min_high = min(high_price, min_high)
            if lowma[i] > min_high and c.c > prev_high:
                trend, next_trend = 0, 1
                max_low = low_price

        # --- the baseline paths. `up`/`down` are `var float ... = 0.0`, so
        # they are never na after the first bar; only the [1] reference on the
        # very first evaluated bar can be.
        if trend == 0:
            if prev_trend is not None and prev_trend != 0:
                up = prev_down if prev_down is not None else down
            else:
                up = max_low if prev_up is None else max(max_low, prev_up)
        else:
            if prev_trend is not None and prev_trend != 1:
                down = prev_up if prev_up is not None else up
            else:
                down = min_high if prev_down is None else min(min_high,
                                                              prev_down)

        # --- the signal. trend 0 is BULLISH, so 1 -> 0 is the long.
        if prev_trend is not None and trend != prev_trend:
            is_long = trend == 0
            dist = a2 * risk_mult
            entry = c.c
            if entry > 0 and dist > 0:
                sgn = 1 if is_long else -1
                out.append(Signal(
                    bar=i, is_long=is_long, entry=entry,
                    stop=entry - sgn * dist,
                    tp1=entry + sgn * dist,
                    tp2=entry + sgn * dist * 2,
                    tp3=entry + sgn * dist * 3, atr2=a2))
        prev_trend, prev_up, prev_down = trend, up, down
    return out


def dashboard_counter(cs, sigs) -> tuple[int, int]:
    """THE INDICATOR'S OWN SCOREBOARD, reproduced statement for statement.

    Returns (wins, losses) exactly as the Pine's dashboard would print them, so
    the number on the chart can be put beside an honest one on the same trades.
    Not a scoring model — a reproduction of a specific piece of arithmetic.
    """
    wins = losses = 0
    state = 0
    sl = tp1 = tp2 = tp3 = None
    hit1 = False
    by_bar = {s.bar: s for s in sigs}

    for i, c in enumerate(cs):
        # The Pine evaluates the open trade BEFORE the new signal, so a flip
        # bar first resolves whatever was running.
        if state != 0 and sl is not None:
            if state == 1:
                if tp1 is not None and c.h >= tp1:
                    wins += 1; tp1 = None; hit1 = True
                elif tp2 is not None and c.h >= tp2:
                    wins += 1; tp2 = None
                elif tp3 is not None and c.h >= tp3:
                    wins += 1; tp3 = None; state = 0; sl = None
                if sl is not None and c.l <= sl:
                    losses += 1; state = 0; sl = None
                    if hit1:
                        wins -= 1; losses -= 1
            else:
                if tp1 is not None and c.l <= tp1:
                    wins += 1; tp1 = None; hit1 = True
                elif tp2 is not None and c.l <= tp2:
                    wins += 1; tp2 = None
                elif tp3 is not None and c.l <= tp3:
                    wins += 1; tp3 = None; state = 0; sl = None
                if sl is not None and c.h >= sl:
                    losses += 1; state = 0; sl = None
                    if hit1:
                        wins -= 1; losses -= 1
        s = by_bar.get(i)
        if s is not None:
            hit1 = False
            state = 1 if s.is_long else -1
            sl, tp1, tp2, tp3 = s.stop, s.tp1, s.tp2, s.tp3
    return wins, losses


if __name__ == "__main__":
    import asyncio
    import sys
    from datetime import datetime, timezone

    import aiohttp

    from research.studies.mtf_grid import fetch_paged

    sym = sys.argv[1] if len(sys.argv) > 1 else "ETH_USDT"
    tf = sys.argv[2] if len(sys.argv) > 2 else "Min30"

    async def main():
        async with aiohttp.ClientSession() as sess:
            cs = await fetch_paged(sess, sym, tf, 1)
        sigs = halftrend_signals(cs)
        w, l = dashboard_counter(cs, sigs)
        ts = lambda t: datetime.fromtimestamp(t, timezone.utc).strftime(
            "%Y-%m-%d %H:%M")
        print(f"PORT — HalfTrend Long/Short Signal Engine — {sym} {tf}")
        print(f"window  {ts(cs[0].t)} -> {ts(cs[-1].t)} UTC  ({len(cs)} bars)")
        print(f"amplitude {AMPLITUDE} · ATR({ATR_LEN})/2 · base risk "
              f"{BASE_RISK_MULT:g}")
        up = sum(1 for s in sigs if s.is_long)
        days = (cs[-1].t - cs[0].t) / 86400
        print(f"\nSIGNALS  {len(sigs)}   long {up}   short {len(sigs) - up}"
              f"   ({len(sigs) / days:.2f} per day)")
        tot = w + l
        print(f"\nTHE DASHBOARD'S OWN COUNTER, reproduced:  "
              f"{w}W / {l}L  =  {100 * w / tot if tot else 0:.2f}%")
        print(f"  put this next to the chart's PERFORMANCE panel — if it "
              f"matches, the port is right")
        print(f"\n  {'bar time (UTC)':<18}{'signal':<8}{'entry':>12}"
              f"{'stop':>12}{'TP1':>12}{'TP3':>12}")
        for s in sigs[-25:]:
            print(f"  {ts(cs[s.bar].t):<18}"
                  f"{'LONG' if s.is_long else 'SHORT':<8}"
                  f"{s.entry:>12.6g}{s.stop:>12.6g}{s.tp1:>12.6g}"
                  f"{s.tp3:>12.6g}")

    asyncio.run(main())
