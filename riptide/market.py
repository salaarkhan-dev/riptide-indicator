"""Open interest and funding, recorded per bar so they can be tested later.

This module answers a question nothing else in the bot can. Every strategy
input so far comes from OHLC — and thirteen families of variation on it have
come back inside noise. Open interest is different information: it says
whether the contracts behind a price move were being OPENED or CLOSED.

That distinction is exactly the one the strategy rests on and cannot currently
see. When price runs a liquidity pool:

    OI falling   positions are being closed — forced exits, a stop run. The
                 raid is what the strategy assumes it is, and a reversal is
                 the reasonable read.
    OI rising    new money is positioning into the move. That is a breakout
                 with participation, and the reversal is wrong.

Two identical-looking candles, opposite meanings. The volume work already
hinted at this from the outside: sweep-to-setup conversion falls monotonically
from 26% to 6.5% as sweep volume rises (+15.6 SE), which says loud raids are
breakouts. Open interest would say so directly.

WHY THIS IS A LOGGER AND NOT A FILTER. MEXC serves holdVol and fundingRate
only as a live snapshot from contract/ticker; there is no history endpoint for
either. They cannot be backtested at all — not with more effort, not with a
better script. The only way they ever become measurable is to start recording
now and wait. Six weeks of this file is the difference between testing the
idea and guessing at it.

Nothing here can affect an alert. It writes to its own table, is wrapped so a
failure is logged and swallowed, and no other module reads it yet. There is
still no exchange key and no order path anywhere in the bot — contract/ticker
is a public, unsigned GET.
"""

from __future__ import annotations

import time

from .config import BASE, LOG_MARKET, MARKET_KEEP_DAYS, log
from .exchange import get_json
from .tracker import last_closed_bar


def init(db) -> None:
    """Created alongside the other tables, so an existing riptide.db picks it
    up on the next restart with no migration."""
    db.execute("""CREATE TABLE IF NOT EXISTS market(
        symbol TEXT, t INT,
        hold_vol REAL,      -- open interest, in contracts
        funding REAL,       -- funding rate at the snapshot
        price REAL,         -- last price, to convert OI to notional later
        amount24 REAL,      -- 24h quote turnover, for context
        PRIMARY KEY(symbol, t))""")
    db.execute("CREATE INDEX IF NOT EXISTS market_t ON market(t)")
    db.commit()


def _num(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


async def snapshot(sess, db, symbols) -> int:
    """
    Record one row per symbol for the bar that just closed.

    Stamped with last_closed_bar() rather than wall-clock time so rows line up
    with the candles they will eventually be joined against, and so a re-scan
    within the same bar overwrites rather than duplicating — the primary key
    does that, and INSERT OR REPLACE keeps the freshest reading of the bar.

    ONE request for all of them — contract/ticker returns every symbol in a
    single response, and the rows are filtered from it locally. The previous
    sentence here said "one request for every symbol", which was wrong and
    cost an hour of chasing a rate-limit theory that could not have been true.
    Returns how many rows were written.
    """
    if not LOG_MARKET or not symbols:
        return 0

    d = await get_json(sess, f"{BASE}/api/v1/contract/ticker")
    rows = (d or {}).get("data") or []
    if not rows:
        log.debug("market: ticker unavailable this cycle, nothing logged")
        return 0

    want = set(symbols)
    t = last_closed_bar()
    out = []
    for r in rows:
        if not isinstance(r, dict) or r.get("symbol") not in want:
            continue
        hold = _num(r.get("holdVol"))
        if hold is None:
            continue                      # no open interest, nothing to log
        out.append((r["symbol"], t, hold, _num(r.get("fundingRate")),
                    _num(r.get("lastPrice")), _num(r.get("amount24"))))

    if not out:
        log.debug("market: ticker carried none of the scanned symbols")
        return 0

    db.executemany("INSERT OR REPLACE INTO market VALUES(?,?,?,?,?,?)", out)
    db.commit()
    return len(out)


def prune(db) -> int:
    """Drop snapshots past the retention window. Cheap, and keeps a database
    that is otherwise append-forever from growing without bound."""
    if MARKET_KEEP_DAYS <= 0:
        return 0
    cur = db.execute("DELETE FROM market WHERE t < ?",
                     (int(time.time()) - MARKET_KEEP_DAYS * 86400,))
    if cur.rowcount:
        db.commit()
        log.info("market: pruned %d snapshots past %d days",
                 cur.rowcount, MARKET_KEEP_DAYS)
    return cur.rowcount


def coverage(db) -> tuple[int, int, float]:
    """(rows, symbols, days spanned) — what /status reports so the sample is
    visible while it accumulates rather than being discovered later."""
    row = db.execute("SELECT COUNT(*), COUNT(DISTINCT symbol), "
                     "MIN(t), MAX(t) FROM market").fetchone()
    n, syms, lo, hi = row or (0, 0, None, None)
    days = ((hi - lo) / 86400.0) if (lo and hi) else 0.0
    return n or 0, syms or 0, days
