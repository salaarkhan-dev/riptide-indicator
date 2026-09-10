"""What YOU actually traded, as opposed to what the bot sent.

`tracker.py` scores every alert whether or not anyone acted on it — that is
the strategy's record. This is the other book: the positions you took, the
slot rule applied to them, and your own R. The two disagreeing is information,
not a bug.

WHY IT LIVES IN THE BOT. It could have been a web page, but the box makes
outbound connections only and opens no inbound port (DEPLOY.md, ORACLE_SETUP.md),
and a page served from a public IP with no authentication would be a trade
journal anyone could read and write. Telegram already carries the alerts, is
already authenticated, and already long-polls for commands, so the buttons ride
in on a transport that exists.

THE ONE MEASURED RULE. Concurrency, not daily count: at most MAX_OPEN positions
at once, of which RESERVE are held for confirmed setups. Measured at 3.67
return per unit of drawdown against 2.21 for a plain cap of 8, and it works
because confirmed setups are worth 3.4x an early one per signal while early
ones outnumber them 5.6 to 1 — without the reservation the worse signal
crowds out the better one purely by arriving first.

NOTHING HERE CAPS YOUR DAY. No measurement in this project ever produced a
"take N per day" rule, and inventing one would dress a guess in the authority
of the backtest.

Going over the cap WARNS and still logs. A journal that refuses to record a
position you actually took gives you a record that is wrong, and every number
downstream inherits it. Friction, not fiction.
"""

from __future__ import annotations

import sqlite3
import time

from .config import log

MAX_OPEN = 8            # measured: drawdown falls monotonically as this tightens
RESERVE = 3             # of those, held for confirmed setups
FEE_WIN = 0.04          # maker in, maker out, % of notional
FEE_LOSS = 0.08         # maker in, taker out
TARGET_R = 2.0


def init(db) -> None:
    """One table. `sig` is UNIQUE and carries the alert's own dedupe id, so a
    double tap on the button cannot produce two positions — the second insert
    is a no-op and the row is already open."""
    db.execute("""CREATE TABLE IF NOT EXISTS journal(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sig TEXT UNIQUE, symbol TEXT, tf TEXT, grade TEXT, side TEXT,
        entry REAL, stop REAL, target REAL, risk_pct REAL,
        status TEXT, outcome TEXT, r REAL,
        offered_at INT, opened_at INT, closed_at INT)""")
    db.execute("CREATE INDEX IF NOT EXISTS journal_status ON journal(status)")
    db.commit()


def offer(db, sig: str, x, grade: str, tf: str) -> int | None:
    """Record that an alert was sent and could be logged. Returns the row id
    for the button's callback data, which Telegram caps at 64 bytes — hence an
    integer rather than the trade itself.

    Never raises into the send path: an alert that arrives without a working
    button is a small loss, an alert that does not arrive is a large one.
    """
    try:
        risk = abs(x.entry - x.stop)
        if not x.entry or not risk:
            return None
        tgt = x.entry + (1 if x.is_long else -1) * risk * TARGET_R
        cur = db.execute(
            """INSERT OR IGNORE INTO journal(
                 sig, symbol, tf, grade, side, entry, stop, target, risk_pct,
                 status, offered_at)
               VALUES(?,?,?,?,?,?,?,?,?,'offered',?)""",
            (sig, x.symbol, tf, grade, "long" if x.is_long else "short",
             x.entry, x.stop, tgt, 100 * risk / x.entry, int(time.time())))
        db.commit()
        if cur.lastrowid:
            return cur.lastrowid
        row = db.execute("SELECT id FROM journal WHERE sig = ?", (sig,)).fetchone()
        return row[0] if row else None
    except sqlite3.Error as e:
        log.warning("journal offer failed for %s: %s", sig, e)
        return None


def counts(db) -> tuple[int, int]:
    """(open A's, open B's). Grade letters other than A are counted as B —
    only A is reserved, so the rule needs no finer split."""
    rows = db.execute(
        "SELECT grade, COUNT(*) FROM journal WHERE status='open' GROUP BY grade"
    ).fetchall()
    a = sum(n for g, n in rows if g == "A")
    return a, sum(n for _, n in rows) - a


def slots(db) -> tuple[int, int, int]:
    """(open, free, free to an early signal).

    The early figure is clamped by the total. Without the clamp, seven open
    A's report "1 free · 5 of them open to an early" — the decision is right
    but the sentence is nonsense, and a number that contradicts the one beside
    it is how a reader stops trusting the whole panel.
    """
    a, b = counts(db)
    used = a + b
    free = max(0, MAX_OPEN - used)
    return used, free, max(0, min(free, MAX_OPEN - RESERVE - b))


def may_take(db, grade: str) -> tuple[bool, str]:
    """The slot rule as a yes/no and the sentence explaining it."""
    used, free, free_b = slots(db)
    if free <= 0:
        return False, f"all {MAX_OPEN} slots are open"
    if grade != "A" and free_b <= 0:
        return False, f"{RESERVE} slots are held for confirmed setups"
    return True, (f"{free} free" if grade == "A"
                  else f"{free} free · {free_b} of them open to an early")


def take(db, row_id: int) -> tuple[str, dict | None]:
    """Log an offered alert as an open position.

    Returns (outcome, row) where outcome is one of taken / over / already /
    missing. `over` still opens the position — see the module docstring.
    """
    r = get(db, row_id)
    if not r:
        return "missing", None
    if r["status"] != "offered":
        return "already", r
    ok, _ = may_take(db, r["grade"])
    db.execute("UPDATE journal SET status='open', opened_at=? WHERE id=?",
               (int(time.time()), row_id))
    db.commit()
    return ("taken" if ok else "over"), get(db, row_id)


def close(db, row_id: int, outcome: str) -> dict | None:
    """Settle a position. R is realised, not planned: fees are charged in units
    of risk, which is why a tight stop costs more per trade than a wide one.

      win    +2R less a maker/maker round trip
      loss   -1R less a maker-in/taker-out round trip
      zero    the limit never filled — no position, no fee
    """
    r = get(db, row_id)
    if not r or r["status"] != "open":
        return None
    rp = r["risk_pct"] or 1.0
    val = (0.0 if outcome == "zero"
           else TARGET_R - FEE_WIN / rp if outcome == "win"
           else -1.0 - FEE_LOSS / rp)
    db.execute("""UPDATE journal SET status='closed', outcome=?, r=?, closed_at=?
                  WHERE id=?""", (outcome, val, int(time.time()), row_id))
    db.commit()
    return get(db, row_id)


def get(db, row_id: int) -> dict | None:
    cur = db.execute("SELECT * FROM journal WHERE id=?", (row_id,))
    row = cur.fetchone()
    if not row:
        return None
    return dict(zip([c[0] for c in cur.description], row))


def open_rows(db) -> list[dict]:
    cur = db.execute("""SELECT * FROM journal WHERE status='open'
                        ORDER BY CASE grade WHEN 'A' THEN 0 ELSE 1 END,
                                 opened_at""")
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def open_sides(db) -> tuple[int, int]:
    """(long, short) positions currently open, from the reader's own journal.

    THIS IS INFORMATION, NOT A VERDICT, and the distinction is the whole reason
    it is a plain count. `research/studies/sizing.py` measured R per bet against
    how many same-direction positions were already open and found it FLAT
    across the pooled stream — -0.011, +0.015, +0.080, +0.040, +0.031, +0.051
    from zero open through five or more. Later positions in a cluster are not
    worse bets, so nothing here is a signal to skip one.

    What does change is VARIANCE. Six correlated longs move together, so one
    market event decides all six, and the size of a bad session scales with how
    many are open rather than averaging out. That is arithmetic, not a
    measurement, which is why this ships as a count for the reader to size
    against instead of a filter that declines the alert.
    """
    rows = open_rows(db)
    longs = sum(1 for r in rows if (r["side"] or "").lower() == "long")
    return longs, len(rows) - longs


def since(db, cutoff: int) -> list[dict]:
    """Positions opened at or after `cutoff`, newest last."""
    cur = db.execute("""SELECT * FROM journal WHERE status IN ('open','closed')
                        AND opened_at >= ? ORDER BY opened_at""", (cutoff,))
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def record(db) -> dict:
    """Settled totals, overall and per grade."""
    out = {"n": 0, "wins": 0, "fills": 0, "total_r": 0.0, "by": {}}
    cur = db.execute("""SELECT grade, outcome, r FROM journal
                        WHERE status='closed' AND r IS NOT NULL""")
    for grade, outcome, r in cur.fetchall():
        g = out["by"].setdefault(grade or "?",
                                 {"n": 0, "wins": 0, "fills": 0, "r": 0.0})
        for d in (out, g):
            d["n"] += 1
            d["r" if d is g else "total_r"] += r
            if outcome != "zero":
                d["fills"] += 1
                if r > 0:
                    d["wins"] += 1
    return out
