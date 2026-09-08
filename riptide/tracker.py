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

from .config import (BAR_SECONDS, INTERVAL, INTERVALS, TRACK, TRACK_FILL_BARS,
                     TRACK_HORIZON_BARS, TRACK_TARGET_R, log)
from .engine import Candle, Setup, grade_of

PENDING, OPEN = "pending", "open"          # still live
WON, LOST, TIMEOUT = "won", "lost", "timeout"   # filled and finished
EXPIRED = "expired"                        # never filled inside the window
STALE = "stale"                            # ran out of candles, not scored

LIVE = (PENDING, OPEN)
RESOLVED = (WON, LOST, TIMEOUT)

_COLUMNS = ("sig, symbol, side, src, entry, stop, risk, trend_dir, "
            "mss_time, armed_time, armed_at, status, fill_time, exit_time, "
            "r, mfe_r, mae_r, last_bar, updated_at, kind, confluence, "
            "di_dir, rsi_ext, poi, regraded, tf")

CONFIRMED, EARLY = "setup", "early"      # which strategy produced the signal


def init(db) -> None:
    """Created alongside the dedupe tables, so an existing riptide.db picks
    this up on the next restart."""
    db.execute("""CREATE TABLE IF NOT EXISTS outcomes(
        sig TEXT PRIMARY KEY, symbol TEXT, side TEXT, src TEXT,
        entry REAL, stop REAL, risk REAL, trend_dir INT,
        mss_time INT, armed_time INT, armed_at INT,
        status TEXT, fill_time INT, exit_time INT,
        r REAL, mfe_r REAL, mae_r REAL,
        last_bar INT, updated_at INT,
        kind TEXT DEFAULT 'setup', confluence INT DEFAULT 0,
        di_dir INT DEFAULT 0, rsi_ext REAL DEFAULT 0.0)""")
    have = {r[1] for r in db.execute("PRAGMA table_info(outcomes)")}
    # ONE ENTRY PER COLUMN, EACH CHECKED INDEPENDENTLY.
    #
    # This was a list of hand-written `if col not in have` blocks, and two of
    # them shared a guard: `tf` was added inside `if "poi" not in have`. Any
    # database that had already taken the poi migration therefore skipped the
    # tf one forever. The result was not a missing column in the abstract —
    # tracker.arm INSERTs tf, so on those databases arming ANY signal raised
    # "no such column: tf", and because arm() is called just before the send,
    # the exception aborted the whole cycle. Sweeps are sent earlier in the
    # cycle than setups and early signals, so sweeps kept arriving and no
    # trade alert ever did. That cost most of a day and never reproduced
    # locally, because a fresh database is created with the full schema and
    # never runs a migration at all.
    #
    # Grouping migrations is what made it possible. A table cannot: every
    # column carries its own condition, so adding one can never depend on
    # whether some earlier one had already been applied.
    base = INTERVAL if INTERVAL in BAR_SECONDS else "Min30"
    for col, decl, note in (
        ("kind", "TEXT DEFAULT 'setup'",
         "existing rows came from the confirmed path, which the default gives"),
        ("confluence", "INT DEFAULT 0", "existing rows are 0"),
        # Rows armed before the grade moved to DI have no di_dir. They backfill
        # to 0, which is honest: it genuinely was not recorded, and that beats
        # back-dating a letter onto rows that never carried one.
        ("di_dir", "INT DEFAULT 0", "rows armed earlier stay ungraded"),
        ("rsi_ext", "REAL DEFAULT 0.0", "rows armed earlier stay ungraded"),
        # poi = 0 on an old row is indistinguishable from a genuine "not in a
        # zone", so `regraded` marks which rows can be regraded at all and
        # live_band skips the rest rather than inventing a letter for them.
        ("poi", "INT DEFAULT 0", "old rows are excluded via regraded"),
        ("regraded", "INT DEFAULT 0", "0 means this row predates the cell table"),
        # Interpolated rather than bound: SQLite requires a literal in
        # ALTER TABLE ... DEFAULT. INTERVAL is checked against BAR_SECONDS
        # first, so nothing from the environment reaches the statement
        # unvalidated. Rows predating multi-timeframe scanning were all on
        # RIPTIDE_INTERVAL, so unlike poi this backfill is simply correct.
        ("tf", f"TEXT DEFAULT '{base}'", f"existing rows are {base}"),
    ):
        if col not in have:
            db.execute(f"ALTER TABLE outcomes ADD COLUMN {col} {decl}")
            log.info("outcomes: added %s — %s", col, note)
    db.execute("CREATE INDEX IF NOT EXISTS outcomes_live "
               "ON outcomes(symbol, status)")
    db.commit()


def last_closed_bar(now: int | None = None, interval: str = "") -> int:
    """Open time of the most recently closed bar on `interval`."""
    now = int(time.time()) if now is None else now
    step = BAR_SECONDS[interval or INTERVAL]
    return now - (now % step) - step


def arm(db, sid: str, s, from_bar: int | None = None,
        kind: str = CONFIRMED) -> None:
    """
    Start scoring one setup.

    Called only for setups that passed the freshness gate, whether or not the
    alert was actually sent — a paused bot should still learn, and a muted
    first run should not backfill 600 bars of history into what is meant to be
    forward data.

    Scoring begins after the LATER of two bars: Setup.detected_time, the bar
    on which both the shift and the gap existed, and the bar that had just
    closed when the alert fired. The second matters because RIPTIDE_FRESH_BARS
    allows a setup from a few bars back to still alert — and counting a fill
    from a bar that closed before the alert existed would be scoring a trade
    nobody could have taken. That is lookahead, and it only ever flatters the
    result; measured at 0.229 R per setup on 41.6 days.

    The fill window runs from detected_time too, so a late alert has fewer
    bars left to fill in. That is the right way round: being late costs you
    the bars you were late by. (Running it from the alert instead was measured
    at +0.004 R, +0.8 SE — the choice does not matter, so take the simpler
    one.)

    from_bar overrides that floor. It exists for replaying recorded candles,
    where wall-clock time is meaningless; live callers must not pass it.
    """
    if not TRACK or s.risk <= 0 or not s.fvg_time:
        return
    now = int(time.time())
    detected = s.detected_time
    start = from_bar if from_bar is not None \
        else max(detected, last_closed_bar(now, getattr(s, "tf", "")))
    db.execute(f"INSERT OR IGNORE INTO outcomes({_COLUMNS}) "
               "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (sid, s.symbol, "long" if s.is_long else "short", s.src,
                s.entry, s.stop, s.risk, s.trend_dir,
                # Early has no shift; its sweep bar is the comparable anchor.
                getattr(s, "mss_time", 0) or s.sweep_time, detected, now,
                PENDING, 0, 0, None, 0.0, 0.0, start, now, kind,
                getattr(s, "confluence", 0),
                getattr(s, "di_dir", 0), getattr(s, "rsi_ext", 0.0),
                int(getattr(s, "poi", False)), 1,
                getattr(s, "tf", "") or INTERVAL))
    db.commit()


def update(db, symbol: str, cs: list[Candle], interval: str = "") -> None:
    """
    Advance every live row for one symbol over the candles just fetched.

    last_bar makes this idempotent: a bar is only ever walked once per row, so
    a re-scan, a restart, or a manual /scan cannot double-count an excursion.

    `interval` scopes the walk to rows found on the SAME timeframe as `cs`.
    Without it, 15m candles would advance a 30m row four bars at a time and
    expire it in a quarter of its fill window — and the fill and horizon
    windows are counted in bars, so a row must only ever be walked by its own.
    """
    if not TRACK or not cs:
        return
    interval = interval or INTERVAL
    rows = db.execute(
        "SELECT sig, side, entry, stop, risk, status, armed_time, fill_time, "
        "mfe_r, mae_r, last_bar FROM outcomes "
        "WHERE symbol=? AND status IN (?,?) AND tf=?",
        (symbol, PENDING, OPEN, interval)).fetchall()
    if not rows:
        return

    step = BAR_SECONDS[interval]
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
    bars = TRACK_FILL_BARS + TRACK_HORIZON_BARS + 4
    # Per timeframe: a 15m row goes stale in a quarter of the wall-clock time a
    # 30m one does, and using the slowest deadline for all of them would leave
    # fast rows live for days after they could no longer resolve.
    total = 0
    for tf in INTERVALS:
        cur = db.execute(
            "UPDATE outcomes SET status=?, exit_time=?, updated_at=? "
            "WHERE status IN (?,?) AND tf=? AND armed_time < ?",
            (STALE, now, now, PENDING, OPEN, tf,
             now - bars * BAR_SECONDS[tf]))
        total += cur.rowcount or 0
    db.commit()
    if total:
        log.info("%d tracked setup(s) went stale — no candles to score them "
                 "against, probably a symbol that left the scan list", total)
    return total


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


def live_band(db, letter: str, kind: str, min_n: int = 30):
    """
    (n, fill %, win %, R, SE) for one band from FORWARD data, or None until
    the band has at least min_n settled rows.

    This is the number that eventually replaces the backtest figure on an
    alert. It is worth strictly more than the historical one — it is out of
    sample by construction, it includes whatever the market has done since,
    and it cannot have been fitted. min_n exists because a band with nine
    settled trades would print a win rate swinging 30 points on one outcome,
    which is worse than saying nothing.
    """
    rows = db.execute(
        "SELECT status, r, side, di_dir, poi, trend_dir, regraded "
        "FROM outcomes WHERE kind=?", (kind,)).fetchall()
    mine = [r for r in rows if r[6]
            and grade_of(kind == EARLY, bool(r[4]), r[5], r[2] == "long",
                         r[3])[0] == letter]
    settled = [r for r in mine if r[0] in RESOLVED or r[0] == EXPIRED]
    if len(settled) < min_n:
        return None
    fills = [r for r in settled if r[0] in RESOLVED and r[1] is not None]
    if not fills:
        return None
    wins = sum(1 for r in fills if r[1] > 0)
    scored = [r[1] for r in fills] + [0.0 for r in settled if r[0] == EXPIRED]
    m, se = _mean_se(scored)
    return (len(settled), round(100 * len(fills) / len(settled)),
            round(100 * wins / len(fills)), m, se)


def summary(db, kind: str | None = None) -> dict:
    """Pass a kind to describe one strategy alone; omit it for both together."""
    sql = ("SELECT status, r, trend_dir, side, mfe_r, mae_r, armed_at, kind, "
           "confluence, di_dir, rsi_ext, poi, regraded FROM outcomes")
    rows = (db.execute(sql + " WHERE kind=?", (kind,)).fetchall() if kind
            else db.execute(sql).fetchall())
    if not rows:
        return {"armed": 0}

    # Indexed rather than unpacked: this loop has been broken twice by a
    # column being added to the SELECT above, and a fixed-width unpack gives
    # no hint which end is wrong.
    aligned, against = [], []
    for r_ in rows:
        st, r, td, side = r_[0], r_[1], r_[2], r_[3]
        if not td:
            continue
        (aligned if (td > 0) == (side == "long") else against).append((st, r))

    filled = [(r_[4], r_[5]) for r_ in rows if r_[0] in RESOLVED]
    return {
        "armed": len(rows),
        "since": min(r[6] for r in rows),
        "pending": sum(1 for r in rows if r[0] == PENDING),
        "open": sum(1 for r in rows if r[0] == OPEN),
        "expired": sum(1 for r in rows if r[0] == EXPIRED),
        "stale": sum(1 for r in rows if r[0] == STALE),
        "all": _bucket([(r[0], r[1]) for r in rows]),
        "aligned": _bucket(aligned),
        "against": _bucket(against),
        "mfe": statistics.fmean([m for m, _ in filled]) if filled else 0.0,
        "mae": statistics.fmean([m for _, m in filled]) if filled else 0.0,
        # By grade. Computed from the stored poi and trend_dir columns rather
        # than a saved letter, so a change to the ladder re-grades history
        # instead of stranding it. Rows armed before the POI column existed
        # carry regraded = 0 and are left out: they would all land in the
        # no-POI bands and manufacture a difference that is really just an
        # ordering by arming date.
        "grades": {g: _bucket([(r[0], r[1]) for r in rows if r[12]
                               and grade_of(r[7] == EARLY, bool(r[11]), r[2],
                                            r[3] == "long", r[9])[0] == g])
                   for g in ("A", "B", "C", "D")},
    }
