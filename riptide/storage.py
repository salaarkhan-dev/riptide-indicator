"""SQLite state: what has been sent, and small key/value bookkeeping.

Dedupe lives here. Setups and sweeps get separate tables so their signatures
cannot collide, and both are created with IF NOT EXISTS so an existing
database picks up new ones without a migration.
"""

from __future__ import annotations

import sqlite3
import time

from . import journal, market, tracker, watch
from .config import DB_PATH, INTERVAL
from .engine import Early, Setup, Sweep

def db_init():
    db = sqlite3.connect(DB_PATH)
    db.execute("""CREATE TABLE IF NOT EXISTS seen(
        sig TEXT PRIMARY KEY, symbol TEXT, side TEXT, src TEXT,
        entry REAL, stop REAL, level REAL, mss_time INT, sent_at INT)""")
    db.execute("CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT)")
    # Separate table so sweep dedupe cannot collide with setup dedupe, and so
    # an existing riptide.db picks this up without a migration.
    db.execute("""CREATE TABLE IF NOT EXISTS seen_sweeps(
        sig TEXT PRIMARY KEY, symbol TEXT, side TEXT, src TEXT,
        level REAL, struct_level REAL, sweep_time INT, sent_at INT)""")
    # The no-shift strategy dedupes separately: it and the confirmed setup can
    # both fire off one sweep, and neither should suppress the other.
    db.execute("""CREATE TABLE IF NOT EXISTS seen_early(
        sig TEXT PRIMARY KEY, symbol TEXT, side TEXT, src TEXT,
        entry REAL, stop REAL, level REAL, sweep_time INT, fvg_time INT,
        sent_at INT)""")
    db.commit()
    tracker.init(db)
    market.init(db)
    journal.init(db)
    # Every heads-up watch shares one table, and it is deliberately not part of
    # any of the above: nothing in it is a trade, and none of it may reach the
    # tables /stats scores. One call covers every registered indicator, so
    # adding one does not mean remembering to add a line here.
    watch.init(db)
    return db


def tf_of(s) -> str:
    """The timeframe a signal was found on. Part of every dedupe key, so the
    same structure seen on 30m and on 15m stays two signals rather than one
    silently suppressing the other."""
    return getattr(s, "tf", "") or INTERVAL


def sig_id(s: Setup) -> str:
    return (f"{s.symbol}|{tf_of(s)}|{s.anchor_time}|{s.mss_time}|"
            f"{'L' if s.is_long else 'S'}")


def already_sent(db, sid) -> bool:
    return db.execute("SELECT 1 FROM seen WHERE sig=?", (sid,)).fetchone() is not None


def record(db, sid, s: Setup):
    db.execute("INSERT OR IGNORE INTO seen VALUES(?,?,?,?,?,?,?,?,?)",
               (sid, s.symbol, "long" if s.is_long else "short", s.src,
                s.entry, s.stop, s.level, s.mss_time, int(time.time())))
    db.commit()


def first_run(db) -> bool:
    return db.execute("SELECT COUNT(*) FROM seen").fetchone()[0] == 0


def meta_get(db, k: str, default: str = "") -> str:
    row = db.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone()
    return row[0] if row else default


def meta_set(db, k: str, v) -> None:
    db.execute("INSERT INTO meta(k, v) VALUES(?, ?) "
               "ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, str(v)))
    db.commit()


# ── the pause, and why it has a SCOPE ───────────────────────────────────────
# `/pause` used to be one switch over everything, and a watch list that kept
# talking through a pause would have made it useless. That is still the
# default. But the bot now sends two unrelated streams -- the measured Riptide
# alerts and the watch digests -- and the reason to silence one is almost never
# a reason to silence the other: a watch is switched on precisely to be
# observed for a while, which is the moment its owner most wants the rest quiet.
#
# ONE KEY, THREE VALUES, AND THE OLD ONE STILL MEANS WHAT IT MEANT. "1" is the
# value already on disk in every running install; it has to keep meaning "all"
# or the first update after this change un-pauses somebody silently.
PAUSE_ALL = ("1", "all")


def paused_for(db, who: str) -> bool:
    """Is `who` ("riptide" or "watch") currently muted?

    Reads one key so the two callers cannot disagree about what is paused,
    which two keys would eventually let them do.
    """
    v = meta_get(db, "alerts_paused", "0").strip().lower()
    return v in PAUSE_ALL or v == who


def sweep_sig(s: Sweep) -> str:
    return (f"SWP|{s.symbol}|{tf_of(s)}|{s.anchor_time}|{s.sweep_time}|"
            f"{'H' if s.is_high else 'L'}")


def sweep_already_sent(db, sid) -> bool:
    return db.execute("SELECT 1 FROM seen_sweeps WHERE sig=?",
                      (sid,)).fetchone() is not None


def early_sig(s: Early) -> str:
    return (f"EAR|{s.symbol}|{tf_of(s)}|{s.anchor_time}|{s.sweep_time}|"
            f"{s.fvg_time}|{'L' if s.is_long else 'S'}")


def early_already_sent(db, sid) -> bool:
    return db.execute("SELECT 1 FROM seen_early WHERE sig=?",
                      (sid,)).fetchone() is not None


def record_early(db, sid, s: Early):
    db.execute("INSERT OR IGNORE INTO seen_early VALUES(?,?,?,?,?,?,?,?,?,?)",
               (sid, s.symbol, "long" if s.is_long else "short", s.src,
                s.entry, s.stop, s.level, s.sweep_time, s.fvg_time,
                int(time.time())))
    db.commit()


def record_sweep(db, sid, s: Sweep):
    db.execute("INSERT OR IGNORE INTO seen_sweeps VALUES(?,?,?,?,?,?,?,?)",
               (sid, s.symbol, "short" if s.is_high else "long", s.src,
                s.level, s.struct_level, s.sweep_time, int(time.time())))
    db.commit()
