"""SQLite state: what has been sent, and small key/value bookkeeping.

Dedupe lives here. Setups and sweeps get separate tables so their signatures
cannot collide, and both are created with IF NOT EXISTS so an existing
database picks up new ones without a migration.
"""

from __future__ import annotations

import sqlite3
import time

from .config import DB_PATH, INTERVAL
from .engine import Setup, Sweep

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
    db.commit()
    return db


def sig_id(s: Setup) -> str:
    return f"{s.symbol}|{INTERVAL}|{s.anchor_time}|{s.mss_time}|{'L' if s.is_long else 'S'}"


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


def sweep_sig(s: Sweep) -> str:
    return (f"SWP|{s.symbol}|{INTERVAL}|{s.anchor_time}|{s.sweep_time}|"
            f"{'H' if s.is_high else 'L'}")


def sweep_already_sent(db, sid) -> bool:
    return db.execute("SELECT 1 FROM seen_sweeps WHERE sig=?",
                      (sid,)).fetchone() is not None


def record_sweep(db, sid, s: Sweep):
    db.execute("INSERT OR IGNORE INTO seen_sweeps VALUES(?,?,?,?,?,?,?,?)",
               (sid, s.symbol, "short" if s.is_high else "long", s.src,
                s.level, s.struct_level, s.sweep_time, int(time.time())))
    db.commit()
