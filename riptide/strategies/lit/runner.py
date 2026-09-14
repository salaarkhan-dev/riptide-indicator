"""One forward cycle: observe, record, try to resolve. Nothing else.

This is the only place LIT touches the running bot, and it is guarded by
`RIPTIDE_LIT_FORWARD`, which ships OFF. When that flag is 0 the function
returns immediately and the production scanner is exactly what it was.

It shares candle loading, the symbol universe, the scheduler and the tracker
database with production, and shares NO strategy state with it: nothing here
reads or writes a production table, a production signal, or a production alert.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from typing import Any, Callable, Sequence

from . import forward, signals, structure
from .types import FWD_FAMILY, FWD_VERSION, ForwardSetup, rules_hash

log = logging.getLogger("riptide.lit.forward")


def event_id(signal_time: int, is_long: bool) -> str:
    """The project's existing event definition, not a second one.

    riptide/decide.py::event_span is the same window production uses, and
    event_key buckets by (window, direction) across every symbol AND every
    timeframe — because a 15m signal at 10:15 and the 1h signal at 10:00 that
    contains it are one raid with two timestamps, not two bets.
    """
    from ...decide import event_span
    step = max(1, event_span())
    t = int(signal_time)
    return f"{t - (t % step)}|{'L' if is_long else 'S'}"


async def cycle(db: sqlite3.Connection, symbols: Sequence[str],
                timeframes: Sequence[str],
                load: Callable[..., Any],
                alert: Callable[[ForwardSetup], Any] | None = None,
                now: int | None = None) -> dict:
    """Observe every symbol/timeframe once.

    `load(symbol, tf)` is injected rather than imported so the tests can drive
    this with fixtures and so production candle loading stays the caller's.
    Returns a small counter dict for logging and tests.
    """
    start = forward.start_ts(db)
    if start is None:
        log.warning("LIT FWD cycle skipped: not activated")
        return {"skipped": True}

    st = {"seen": 0, "created": 0, "pre_start": 0, "resolved": 0}
    rh = rules_hash()
    nowts = int(now if now is not None else time.time())

    for sym in symbols:
        for tf in timeframes:
            try:
                cs = await load(sym, tf)
            except Exception as e:                       # noqa: BLE001
                log.debug("LIT FWD load failed %s %s: %s", sym, tf, e)
                continue
            if not cs or len(cs) < structure.WARMUP + 10:
                continue
            cs = structure.window(cs)
            main, events = structure.run(cs)
            found = signals.detect(cs, events)

            for raw in found:
                st["seen"] += 1
                # THE GATE. Before activation is history, and history is what
                # the closed stages already measured.
                if not forward.eligible(raw.signal_time, start):
                    st["pre_start"] += 1
                    continue
                sid = signals.setup_id(FWD_VERSION, sym, tf, raw.direction,
                                       raw.signal_time)
                if forward.exists(db, sid):
                    continue
                s = _build(sid, sym, tf, raw, rh, nowts)
                if forward.record(db, s):
                    st["created"] += 1
                    if alert is not None:
                        try:
                            await alert(s)
                        except Exception as e:           # noqa: BLE001
                            log.warning("LIT FWD alert failed %s: %s", sid, e)

            # resolve whatever is pending on THIS symbol/timeframe
            for row in forward.pending(db):
                if row["symbol"] != sym or row["timeframe"] != tf:
                    continue
                if forward.resolve(db, row, cs, events):
                    st["resolved"] += 1

    if st["created"] or st["resolved"]:
        log.info("LIT FWD cycle: %d created, %d resolved, %d pre-start",
                 st["created"], st["resolved"], st["pre_start"])
    return st


def _build(sid: str, sym: str, tf: str, raw, rh: str, nowts: int
           ) -> ForwardSetup:
    is_long = raw.direction > 0
    return ForwardSetup(
        setup_id=sid, strategy_family=FWD_FAMILY,
        strategy_version=FWD_VERSION, rules_hash=rh,
        symbol=sym, timeframe=tf, direction=raw.direction,
        structure_time=raw.structure_time, signal_time=raw.signal_time,
        entry_time=raw.signal_time,
        structure_depth="MAIN", lit_direction=raw.direction,
        idm_price=raw.idm_price, idm_break_time=raw.signal_time,
        bos_price=raw.bos, choch_price=raw.choch,
        relevant_pivot=raw.stop, raid_extreme=raw.raid_extreme,
        entry_price=raw.entry, initial_stop=raw.stop,
        initial_risk_price=raw.risk,
        initial_risk_pct=100.0 * raw.risk / raw.entry if raw.entry else 0.0,
        active_price=raw.active, bos_distance_r=raw.bos_distance_r,
        market_event_id=event_id(raw.signal_time, is_long),
        event_direction=raw.direction,
        created_at=nowts, updated_at=nowts)
