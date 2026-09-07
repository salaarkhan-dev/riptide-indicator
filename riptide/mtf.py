"""
Multi-timeframe entry refinement.

The structure — pool, sweep, shift — is found on the higher timeframe exactly
as before. Only the entry moves: instead of taking the gap left on the HTF leg,
this looks for the first gap on a lower timeframe after the shift confirms, and
places the stop on the lower timeframe's own structure.

DO NOT ENABLE THIS. Re-measured 7 Sep and it loses badly.

The numbers that used to sit here — "Min15: 85% of setups filled, 51% of fills
reached 1R" against 45%/48% for Min30 — came from the scoring loop that ran
from the SIGNAL bar rather than the FILL bar. That bug manufactured wins for
exactly this kind of comparison, and the conclusion it supported was wrong.

Re-run through research/harness.py on matched wall-clock windows
(research/studies/sniper.py), 80 comparable confirmed setups:

    Min30 gap + Min30 stop   fill 57.5%   win 56.5%   +0.304 R per setup
    Min15 gap + Min15 stop   fill 82.5%   win 27.3%   -0.221 R per setup
                                          paired difference -0.525, 3.2 SE

The fill-rate gain was real and is reproduced almost exactly. What the old
scorer hid is what it costs: the win rate falls by more than half. The tighter
structural stop does not "not cost hit rate" — it is the whole problem. A
Min15 stop sits inside ordinary Min30 retracement noise, so the pullback the
setup was always going to have takes it out. research/studies/decouple.py
found the same thing four other ways: every stop nearer than the raid extreme
tested worse, and the raid extreme is not merely a convenient level, it is the
price beyond which the setup is wrong.

Min5 was inconclusive rather than bad (-0.067, 0.2 SE) but only 30 setups fall
inside the range 2000 Min5 bars can reach, so that is an absence of evidence.

Kept in the tree because ENTRY_INTERVAL is documented and someone may want to
re-test on a different structure timeframe, where the noise argument could
come out differently. It is off by default and should stay off.

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
