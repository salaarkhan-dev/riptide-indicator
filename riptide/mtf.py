"""
Multi-timeframe entry refinement.

The structure — pool, sweep, shift — is found on the higher timeframe exactly
as before. Only the entry moves: instead of taking the gap left on the HTF leg,
this looks for the first gap on a lower timeframe after the shift confirms, and
places the stop on the lower timeframe's own structure.

Why, measured over 12.5 days on 20 symbols:

    Min30 gap + Min30 stop   45% of setups filled, 48% of fills reached 1R
    Min15 gap + Min15 stop   85% of setups filled, 51% of fills reached 1R

The gain is almost entirely fill rate. A Min30 gap sits where price has already
been and often does not return; a Min15 gap forms next to where price is now.
The tighter structural stop (median 0.68x the HTF stop distance) does not cost
hit rate.

Caveats worth remembering when reading those numbers: one market regime, fewer
than a hundred filled samples per variant, and no fees, slippage or the
break-even rule. It is enough to justify the feature, not to size a position.

Nothing here mutates the engine. It reads a finished Setup and returns a
replacement entry and stop, or None.
"""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import replace

from .config import BAR_SECONDS, CFG, ENTRY_INTERVAL, INTERVAL, Cfg, log
from .engine import Candle, Setup, entry_of


def _first_gap(cs: list[Candle], start: int, is_long: bool, min_size: float,
               max_size: float, horizon: int) -> tuple[int, float, float] | None:
    """
    First three-candle gap at or after `start`, in the trade's direction.

    Returns (bar index of the third candle, top, bottom). The gap is only
    complete when that third candle closes, which is what makes this
    non-repainting: the caller only ever passes closed candles.
    """
    for j in range(start + 2, min(start + horizon, len(cs))):
        if is_long:
            top, bot = cs[j].l, cs[j - 2].h
            ok = cs[j].l > cs[j - 2].h
        else:
            top, bot = cs[j - 2].l, cs[j].h
            ok = cs[j].h < cs[j - 2].l
        if not ok:
            continue
        size = top - bot
        if size < min_size or (max_size > 0 and size > max_size):
            continue
        return j, top, bot
    return None


def refine(s: Setup, ltf: list[Candle], atr_ref: float,
           cfg: Cfg = CFG, horizon: int = 0) -> Setup | None:
    """
    Move a setup's entry and stop onto the lower timeframe.

    `atr_ref` is the HTF ATR at the shift, so gap-size limits stay on the same
    scale the engine calibrated them at. Returns None when the lower timeframe
    offers nothing usable, in which case the caller keeps the HTF setup rather
    than dropping the signal.
    """
    if not ltf or atr_ref <= 0:
        return None

    # The lower timeframe covers less wall-clock time for the same bar count —
    # 600 Min15 bars is 6 days against 12.5 for Min30 — so roughly half the
    # structure window has no lower-timeframe data at all. Without this,
    # bisect_left returns 0 for those and the scan starts at the beginning of
    # the lower-timeframe series, returning a gap days after the shift as if
    # it belonged to the setup.
    if s.mss_time < ltf[0].t:
        return None

    # Where the shift lands on the lower timeframe. Anything at or after this
    # bar is information the engine already had when it emitted the setup.
    times = [c.t for c in ltf]
    start = bisect_left(times, s.mss_time)
    if start >= len(ltf) - 2:
        return None

    # Look no further than the engine's own patience. It gives up on a setup
    # max_bars_after_mss higher-timeframe bars after the shift; the lower
    # timeframe should not still be offering entries long after that.
    if horizon <= 0:
        htf_step = BAR_SECONDS[INTERVAL]
        ltf_step = BAR_SECONDS[ENTRY_INTERVAL] if ENTRY_INTERVAL else htf_step
        horizon = max(3, cfg.max_bars_after_mss * max(1, htf_step // ltf_step))

    found = _first_gap(ltf, start, s.is_long,
                       atr_ref * cfg.min_fvg_atr,
                       atr_ref * cfg.max_fvg_atr if cfg.max_fvg_atr > 0 else 0.0,
                       horizon)
    if not found:
        return None
    j, top, bot = found

    entry = entry_of(s.is_long, top, bot, cfg.entry_mode)

    # Stop on the lower timeframe's own structure: the extreme price reached
    # between the shift and the gap. That is the level the move would have to
    # undo for the idea to be wrong.
    seg = ltf[start:j + 1]
    if not seg:
        return None
    stop = (min(c.l for c in seg) - atr_ref * cfg.sl_buffer_atr) if s.is_long \
        else (max(c.h for c in seg) + atr_ref * cfg.sl_buffer_atr)

    risk = abs(entry - stop)
    if risk <= 0:
        return None
    if cfg.max_risk_atr > 0 and risk > atr_ref * cfg.max_risk_atr:
        log.debug("%s: LTF entry rejected, risk %.4f over %.1f ATR",
                  s.symbol, risk, cfg.max_risk_atr)
        return None
    # A stop on the wrong side of the entry means the lower timeframe never
    # actually turned; treat it as no signal.
    if (s.is_long and stop >= entry) or (not s.is_long and stop <= entry):
        return None

    return replace(s, entry=entry, stop=stop, risk=risk,
                   fvg_time=ltf[j].t, entry_tf="LTF")
