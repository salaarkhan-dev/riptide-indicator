"""Outcome tracking: what actually happened to each alert.

Every strategy conclusion in this project rests on one 41-day backtest over
symbols picked by their turnover *today* — survivorship bias, a single ranging
regime, and no out-of-sample data. The trend-filter estimate moved 35% in a few
hours of fresh candles, which is the sample telling you how much it can be
trusted. More variants tested against that same window cannot fix it; only
forward data can.

So this module scores live alerts against the candles the scanner already
fetches. Nothing extra is requested from the exchange, and nothing here changes
which alerts are sent — it observes and records, and the engine cannot see it.

There is still no exchange key and no order path anywhere in the bot. A "fill"
here is a price level being touched on a chart. No position exists.

The simulated rule is deliberately the plain one the alert leads with: a limit
at the entry, the stop where the alert puts it, a fixed target, stop taken
first when a single bar contains both. MFE and MAE are stored in R alongside
the result, so a fixed-target rule other than the one being scored can be
reconstructed later from the same rows without re-running anything.

Two things it does not model, both of which flatter the numbers: fees, and
slippage on the stop. Read the results as an upper bound.

Scoring always uses RIPTIDE_INTERVAL bars, even when RIPTIDE_ENTRY_INTERVAL
moves entries to a lower timeframe. Fills are unaffected — a coarse bar
touches the entry exactly when some finer bar inside it did. What a coarse
bar loses is the order of events within it, and stop-first resolves that
against the trade, so an entry timeframe makes the results pessimistic rather
than optimistic. Between that and the fees above, neither bound is tight.
"""

from __future__ import annotations

import statistics
import time

from .config import (BAR_SECONDS, INTERVAL, TRACK, TRACK_FILL_BARS,
                     TRACK_HORIZON_BARS, TRACK_TARGET_R, log)
from .engine import Candle, Setup

PENDING, OPEN = "pending", "open"          # still live
WON, LOST, TIMEOUT = "won", "lost", "timeout"   # filled and finished
EXPIRED = "expired"                        # never filled inside the window
STALE = "stale"                            # ran out of candles, not scored

LIVE = (PENDING, OPEN)
RESOLVED = (WON, LOST, TIMEOUT)

_COLUMNS = ("sig, symbol, side, src, entry, stop, risk, trend_dir, "
            "mss_time, armed_time, armed_at, status, fill_time, exit_time, "
            "r, mfe_r, mae_r, last_bar, updated_at")


def init(db) -> None:
    """Created alongside the dedupe tables, so an existing riptide.db picks
    this up on the next restart without a migration."""
    db.execute("""CREATE TABLE IF NOT EXISTS outcomes(
        sig TEXT PRIMARY KEY, symbol TEXT, side TEXT, src TEXT,
        entry REAL, stop REAL, risk REAL, trend_dir INT,
        mss_time INT, armed_time INT, armed_at INT,
        status TEXT, fill_time INT, exit_time INT,
        r REAL, mfe_r REAL, mae_r REAL,
        last_bar INT, updated_at INT)""")
    db.execute("CREATE INDEX IF NOT EXISTS outcomes_live "
               "ON outcomes(symbol, status)")
    db.commit()


def last_closed_bar(now: int | None = None) -> int:
    """Open time of the most recently closed RIPTIDE_INTERVAL bar."""
    now = int(time.time()) if now is None else now
    step = BAR_SECONDS[INTERVAL]
    return now - (now % step) - step


def arm(db, sid: str, s: Setup, from_bar: int | None = None) -> None:
    """
    Start scoring one setup.

    Called only for setups that passed the freshness gate, whether or not the
    alert was actually sent — a paused bot should still learn, and a muted
    first run should not backfill 600 bars of history into what is meant to be
    forward data.

    Scoring begins after the LATER of two bars: the one the gap closed on (it
    is not known to exist before that) and the one that had just closed when
    the alert fired. The second matters because RIPTIDE_FRESH_BARS allows a
    shift from a few bars back to still alert — and counting a fill from a bar
    that closed before the alert existed would be scoring a trade nobody could
    have taken. That is lookahead, and it only ever flatters the result.

    The fill window still runs from the gap bar, so a late alert has fewer
    bars left to fill in. That is the right way round: being late costs you
    the bars you were late by.

    from_bar overrides that floor. It exists for replaying recorded candles,
    where wall-clock time is meaningless; live callers must not pass it.
    """
    if not TRACK or s.risk <= 0 or not s.fvg_time:
        return
    now = int(time.time())
    start = from_bar if from_bar is not None \
        else max(s.fvg_time, last_closed_bar(now))
    db.execute(f"INSERT OR IGNORE INTO outcomes({_COLUMNS}) "
               "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (sid, s.symbol, "long" if s.is_long else "short", s.src,
                s.entry, s.stop, s.risk, s.trend_dir,
                s.mss_time, s.fvg_time, now,
                PENDING, 0, 0, None, 0.0, 0.0, start, now))
    db.commit()


def update(db, symbol: str, cs: list[Candle]) -> None:
    """
    Advance every live row for one symbol over the candles just fetched.

    last_bar makes this idempotent: a bar is only ever walked once per row, so
    a re-scan, a restart, or a manual /scan cannot double-count an excursion.
    """
    if not TRACK or not cs:
        return
    rows = db.execute(
        "SELECT sig, side, entry, stop, risk, status, armed_time, fill_time, "
        "mfe_r, mae_r, last_bar FROM outcomes "
        "WHERE symbol=? AND status IN (?,?)",
        (symbol, PENDING, OPEN)).fetchall()
    if not rows:
        return

    step = BAR_SECONDS[INTERVAL]
    now = int(time.time())
    writes = []

    for (sig, side, entry, stop, risk, status, armed_time, fill_time,
         mfe_r, mae_r, last_bar) in rows:
        is_long = side == "long"
        sgn = 1.0 if is_long else -1.0
        target = entry + sgn * risk * TRACK_TARGET_R
        r = None
        exit_time = 0
        moved = False

        for c in cs:
            if c.t <= last_bar:
                continue
            last_bar = c.t
            moved = True

            if status == PENDING:
                if c.t - armed_time > TRACK_FILL_BARS * step:
                    status, exit_time = EXPIRED, c.t
                    break
                touched = c.l <= entry if is_long else c.h >= entry
                if not touched:
                    continue
                status, fill_time = OPEN, c.t
                # fall through: a bar can fill and resolve at once

            # Excursions use the whole bar. On the fill bar that is generous
            # to MFE and harsh to MAE in equal measure, and bar data cannot
            # say which came first.
            if is_long:
                fav, adv = (c.h - entry) / risk, (c.l - entry) / risk
            else:
                fav, adv = (entry - c.l) / risk, (entry - c.h) / risk
            mfe_r, mae_r = max(mfe_r, fav), min(mae_r, adv)

            # Stop before target when one bar contains both. The pessimistic
            # read: it is the one that cannot flatter the result.
            if (c.l <= stop) if is_long else (c.h >= stop):
                status, r, exit_time = LOST, -1.0, c.t
                break
            if (c.h >= target) if is_long else (c.l <= target):
                status, r, exit_time = WON, TRACK_TARGET_R, c.t
                break
            if c.t - fill_time >= TRACK_HORIZON_BARS * step:
                status, exit_time = TIMEOUT, c.t
                r = sgn * (c.c - entry) / risk
                break

        if moved:
            writes.append((status, fill_time, exit_time, r, mfe_r, mae_r,
                           last_bar, now, sig))

    if writes:
        db.executemany("UPDATE outcomes SET status=?, fill_time=?, exit_time=?, "
                       "r=?, mfe_r=?, mae_r=?, last_bar=?, updated_at=? "
                       "WHERE sig=?", writes)
        db.commit()
        done = sum(1 for w in writes if w[0] not in LIVE)
        if done:
            log.info("%s: %d tracked setup(s) resolved", symbol, done)


def expire_stale(db) -> int:
    """
    Retire live rows that can no longer resolve.

    Deliberately separate from update(): a row goes stale precisely when its
    symbol stops being scanned — dropped from RIPTIDE_SYMBOLS, or below the
    turnover floor on a refresh — and update() is never called for a symbol
    that is not in the scan. Checking it there would mean the rows that need
    this are the only ones that never reach it.

    Keeping update() free of the wall clock also makes it purely a function of
    the candles it is given, which is what lets it be replayed and tested.
    """
    if not TRACK:
        return 0
    now = int(time.time())
    deadline = (TRACK_FILL_BARS + TRACK_HORIZON_BARS + 4) * BAR_SECONDS[INTERVAL]
    cur = db.execute(
        "UPDATE outcomes SET status=?, exit_time=?, updated_at=? "
        "WHERE status IN (?,?) AND armed_time < ?",
        (STALE, now, now, PENDING, OPEN, now - deadline))
    db.commit()
    if cur.rowcount:
        log.info("%d tracked setup(s) went stale — no candles to score them "
                 "against, probably a symbol that left the scan list",
                 cur.rowcount)
    return cur.rowcount


def _mean_se(values: list[float]) -> tuple[float, float]:
    """Mean and its standard error. SE is 0.0 below two samples — which is a
    missing number, not a certain one, so callers must check n."""
    if not values:
        return 0.0, 0.0
    m = statistics.fmean(values)
    if len(values) < 2:
        return m, 0.0
    return m, statistics.stdev(values) / (len(values) ** 0.5)


def _bucket(rows) -> dict:
    """rows: (status, r). Per-trade counts only fills; per-setup counts every
    armed setup, scoring an unfilled one at zero — the number the backtests
    reported, so the two are comparable."""
    trades = [r for st, r in rows if st in RESOLVED and r is not None]
    setups = trades + [0.0 for st, _ in rows if st == EXPIRED]
    t_mean, t_se = _mean_se(trades)
    s_mean, s_se = _mean_se(setups)
    wins = sum(1 for r in trades if r > 0)
    return {"trades": len(trades), "setups": len(setups),
            "r_trade": t_mean, "se_trade": t_se,
            "r_setup": s_mean, "se_setup": s_se,
            "wins": wins,
            "win_pct": 100.0 * wins / len(trades) if trades else 0.0}


def summary(db) -> dict:
    rows = db.execute(
        "SELECT status, r, trend_dir, side, mfe_r, mae_r, armed_at "
        "FROM outcomes").fetchall()
    if not rows:
        return {"armed": 0}

    aligned, against = [], []
    for st, r, td, side, _, _, _ in rows:
        if not td:
            continue
        (aligned if (td > 0) == (side == "long") else against).append((st, r))

    filled = [(mfe, mae) for st, _, _, _, mfe, mae, _ in rows
              if st in RESOLVED]
    return {
        "armed": len(rows),
        "since": min(a for *_, a in rows),
        "pending": sum(1 for st, *_ in rows if st == PENDING),
        "open": sum(1 for st, *_ in rows if st == OPEN),
        "expired": sum(1 for st, *_ in rows if st == EXPIRED),
        "stale": sum(1 for st, *_ in rows if st == STALE),
        "all": _bucket([(st, r) for st, r, *_ in rows]),
        "aligned": _bucket(aligned),
        "against": _bucket(against),
        "mfe": statistics.fmean([m for m, _ in filled]) if filled else 0.0,
        "mae": statistics.fmean([m for _, m in filled]) if filled else 0.0,
    }
