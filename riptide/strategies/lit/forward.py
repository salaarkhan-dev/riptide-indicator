"""LIT_FORWARD_V1 — prospective collection. Not a backtest, not production.

WHAT THIS DOES. Records LIT setups that occur AFTER activation and scores two
exits on the SAME setup: the frozen control (BOS_TARGET) and the primary arm
(T6_PIVOT). The experiment's primary variable is the difference:

    paired_delta_R = t6_r - control_r

WHY PAIRED, AND WHY STANDALONE T6 IS SECONDARY. Stage C found T6 standalone
positive (+0.114 R/bet) while the control was ALSO positive (+0.047). A
standalone number therefore cannot say whether the trail adds anything. Only
the same-setup difference isolates it, and on that measure Stage C returned
+0.068 at z=1.5 — short of its own bar. That is why the historical family is
closed and why this collects forward instead of re-slicing.

WHAT IT REFUSES TO DO.
  * No backfill. A setup whose signal_time predates activation is rejected,
    not recorded. Old candles cannot manufacture "forward" evidence.
  * No rewriting. Identity, entry, stop, version and rules_hash are written
    once. Only outcome fields transition, and only pending -> terminal.
  * No optimising on the way. V1 is frozen until a pre-registered checkpoint.
  * No private scorer. research.harness.simulate_market scores both arms, so
    the conservative same-bar rule and the fee model are the repo's, not ours.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from typing import Any, Sequence

from . import signals, structure
from .types import (AMBIGUOUS, PENDING, RESOLVED, TIMED_OUT, FWD_FAMILY,
                    FWD_VERSION, RULES, ForwardSetup, rules_hash)

log = logging.getLogger("riptide.lit.forward")

TABLE = "lit_forward"
META_START = "lit_forward_v1_start"

_COLS = list(ForwardSetup.__dataclass_fields__.keys())


def init(db: sqlite3.Connection) -> None:
    """Additive, IF NOT EXISTS, and it touches no existing table.

    Follows the same pattern watch.init and exhaust.init use, so an existing
    riptide.db picks it up without a migration and nothing in /stats or the
    production tracker is rewritten.
    """
    cols = ", ".join(f"{c} {_sql_type(c)}" for c in _COLS)
    db.execute(f"CREATE TABLE IF NOT EXISTS {TABLE} ({cols}, "
               f"PRIMARY KEY (setup_id))")
    db.execute(f"CREATE INDEX IF NOT EXISTS {TABLE}_state ON {TABLE}(state)")
    db.execute(f"CREATE INDEX IF NOT EXISTS {TABLE}_ver ON "
               f"{TABLE}(strategy_version)")
    db.commit()


def _sql_type(col: str) -> str:
    f = ForwardSetup.__dataclass_fields__[col]
    t = str(f.type)
    if "int" in t and "float" not in t:
        return "INT"
    if "float" in t:
        return "REAL"
    if "bool" in t:
        return "INT"
    return "TEXT"


# ── activation ──────────────────────────────────────────────────────────────

def start_ts(db: sqlite3.Connection) -> int | None:
    r = db.execute("SELECT v FROM meta WHERE k=?", (META_START,)).fetchone()
    return int(r[0]) if r else None


def activate(db: sqlite3.Connection, ts: int | None = None) -> int:
    """Stamp the forward start. IDEMPOTENT — a restart must not move it, or
    every setup recorded before the restart would fall outside the window it
    was collected under."""
    cur = start_ts(db)
    if cur is not None:
        return cur
    t = int(ts if ts is not None else time.time())
    db.execute("INSERT OR REPLACE INTO meta(k, v) VALUES(?, ?)",
               (META_START, str(t)))
    db.execute("INSERT OR REPLACE INTO meta(k, v) VALUES(?, ?)",
               ("lit_forward_v1_rules", json.dumps(
                   {"version": FWD_VERSION, "rules_hash": rules_hash(),
                    "rules": RULES}, sort_keys=True)))
    db.commit()
    log.info("LIT FWD activated at %d rules_hash=%s", t, rules_hash())
    return t


def eligible(sig_time: int, start: int | None) -> bool:
    """The whole point of the experiment lives in this function.

    A setup is forward evidence only if it happened after collection began.
    Anything at or before the start timestamp is history, and history is what
    the closed stages already measured.
    """
    return start is not None and int(sig_time) > int(start)


# ── recording ───────────────────────────────────────────────────────────────

def exists(db: sqlite3.Connection, setup_id: str) -> bool:
    return db.execute(f"SELECT 1 FROM {TABLE} WHERE setup_id=?",
                      (setup_id,)).fetchone() is not None


def record(db: sqlite3.Connection, s: ForwardSetup) -> bool:
    """Insert once. A repeated scanner pass over the same bar is a no-op.

    Returns True only if a NEW row was written, so the caller can alert exactly
    once per setup.
    """
    if exists(db, s.setup_id):
        return False
    row = s.as_row()
    row["created_at"] = row["updated_at"] = int(time.time())
    ph = ",".join("?" * len(_COLS))
    db.execute(f"INSERT INTO {TABLE} ({','.join(_COLS)}) VALUES ({ph})",
               [_enc(row[c]) for c in _COLS])
    db.commit()
    log.info("LIT FWD setup created %s entry=%.8g stop=%.8g active=%.8g",
             s.setup_id, s.entry_price, s.initial_stop, s.active_price)
    return True


def _enc(v):
    return int(v) if isinstance(v, bool) else v


def pending(db: sqlite3.Connection) -> list[dict]:
    cur = db.execute(f"SELECT {','.join(_COLS)} FROM {TABLE} "
                     f"WHERE state=? AND strategy_version=?",
                     (PENDING, FWD_VERSION))
    return [dict(zip(_COLS, r)) for r in cur.fetchall()]


def resolved(db: sqlite3.Connection) -> list[dict]:
    cur = db.execute(f"SELECT {','.join(_COLS)} FROM {TABLE} "
                     f"WHERE state IN (?,?) AND strategy_version=?",
                     (RESOLVED, TIMED_OUT, FWD_VERSION))
    return [dict(zip(_COLS, r)) for r in cur.fetchall()]


# ── the paired score ────────────────────────────────────────────────────────

def score_pair(candles: Sequence[Any], bar: int, entry: float, stop: float,
               is_long: bool, bos: float, trail: list) -> dict | None:
    """Both arms, ONE entry and ONE stop, through the SHARED scorer.

    Returns None while the pair is still open. A trade is only resolved when it
    actually ended: a `timeout` from simulate_market means "ran out of candles",
    which at the live edge is NOT the same as reaching the horizon. Treating it
    as an exit would mark open positions to market — the exact artefact that
    produced a false +0.360 earlier in this project — so it is only accepted
    once HORIZON bars have genuinely elapsed.
    """
    from research.harness import simulate_market

    risk = abs(entry - stop)
    if risk <= 0:
        return None
    horizon = int(RULES["horizon_bars"])
    avail = len(candles) - 1 - bar
    if avail < 1:
        return None

    ctrl = simulate_market(candles, bar, entry, stop, is_long,
                           target_px=bos, target_r=abs(bos - entry) / risk,
                           horizon_bars=horizon)
    t6 = simulate_market(candles, bar, entry, stop, is_long,
                         target_r=1e9, trail=trail,
                         trail_arm_r=float(RULES["trail_arm_r"]),
                         horizon_bars=horizon)
    if ctrl is None or t6 is None or not ctrl.filled or not t6.filled:
        return None

    def done(o):
        if o.exit in ("stop", "target"):
            return True
        return o.exit == "timeout" and avail >= horizon

    if not (done(ctrl) and done(t6)):
        return None

    state = TIMED_OUT if "timeout" in (ctrl.exit, t6.exit) else RESOLVED
    return {
        "control_r": ctrl.r, "control_exit_reason": ctrl.exit,
        "control_exit_bar": ctrl.exit_bar,
        "t6_r": t6.r, "t6_exit_reason": t6.exit, "t6_exit_bar": t6.exit_bar,
        "paired_delta_r": t6.r - ctrl.r,
        "mfe_r": max(ctrl.mfe, t6.mfe), "mae_r": min(ctrl.mae, t6.mae),
        "state": state,
    }


def resolve(db: sqlite3.Connection, row: dict, candles: Sequence[Any],
            events: list[dict]) -> bool:
    """Try to close one pending setup. Never recomputes its identity.

    The entry, stop and direction come from the STORED row, not from the engine
    — a re-derived setup could differ if the window slid, and the recorded
    hypothesis is the thing being tested.
    """
    bar = _bar_of(candles, int(row["signal_time"]))
    if bar is None:
        return False
    is_long = int(row["direction"]) > 0
    trail = structure.trail_levels(candles, events)[1 if is_long else -1]
    out = score_pair(candles, bar, float(row["entry_price"]),
                     float(row["initial_stop"]), is_long,
                     float(row["bos_price"]), trail)
    if out is None:
        return False

    risk = float(row["initial_risk_price"])
    ex_bar = out["control_exit_bar"] or bar
    worst = min(out["control_r"], out["t6_r"])
    db.execute(
        f"UPDATE {TABLE} SET state=?, resolution_time=?, control_r=?, "
        f"control_exit_reason=?, control_exit_time=?, t6_r=?, "
        f"t6_exit_reason=?, t6_exit_time=?, paired_delta_r=?, mfe_r=?, "
        f"mae_r=?, bars_held=?, realized_loss_r=?, stop_gap_r=?, "
        f"active_reached=?, updated_at=? WHERE setup_id=? AND state=?",
        (out["state"], int(candles[min(ex_bar, len(candles) - 1)].t),
         out["control_r"], out["control_exit_reason"],
         int(candles[min(ex_bar, len(candles) - 1)].t),
         out["t6_r"], out["t6_exit_reason"],
         int(candles[min(out["t6_exit_bar"] or bar,
                        len(candles) - 1)].t),
         out["paired_delta_r"], out["mfe_r"], out["mae_r"],
         int(ex_bar - bar), (worst if worst < 0 else None),
         (abs(worst) - 1.0 if worst < -1.0 else 0.0) if risk > 0 else None,
         1 if out["mfe_r"] >= float(RULES["min_rr"]) else 0,
         int(time.time()), row["setup_id"], PENDING))
    db.commit()
    log.info("LIT FWD pair resolved %s control=%+.3fR t6=%+.3fR delta=%+.3fR",
             row["setup_id"], out["control_r"], out["t6_r"],
             out["paired_delta_r"])
    return True


def _bar_of(candles: Sequence[Any], t: int) -> int | None:
    for i in range(len(candles) - 1, -1, -1):
        if int(candles[i].t) == int(t):
            return i
    return None


# ── reporting ───────────────────────────────────────────────────────────────

def bets(rows: list[dict], field: str) -> list[float]:
    """The repo's unit of evidence: one bar's worth of correlated signals is
    ONE observation. Same grouping as research/studies/fvg_continuation.py."""
    by: dict[str, list[float]] = {}
    for r in rows:
        v = r.get(field)
        if v is None:
            continue
        by.setdefault(r.get("market_event_id") or str(r["signal_time"]),
                      []).append(float(v))
    return [sum(v) / len(v) for v in by.values()]


def summary(db: sqlite3.Connection, checkpoints: tuple[int, ...] = (100, 250,
                                                                    500)) -> dict:
    """Numbers only. No verdict, and no badge for a temporarily positive R."""
    rows = resolved(db)
    d = bets(rows, "paired_delta_r")
    t6 = bets(rows, "t6_r")
    ct = bets(rows, "control_r")
    n = len(d)
    mean = sum(d) / n if n else 0.0
    se = 0.0
    if n > 1:
        var = sum((x - mean) ** 2 for x in d) / (n - 1)
        se = (var / n) ** 0.5
    nxt = next((c for c in checkpoints if n < c), None)
    return {
        "setups": len(rows),
        "pending": len(pending(db)),
        "bets": n,
        "t6_per_bet": (sum(t6) / len(t6)) if t6 else 0.0,
        "control_per_bet": (sum(ct) / len(ct)) if ct else 0.0,
        "paired_delta": mean,
        "paired_se": se,
        "paired_z": (mean / se) if se else 0.0,
        "next_checkpoint": nxt,
        # COLLECTING until a pre-registered checkpoint is reached. There is no
        # code path here that can emit "validated".
        "status": "COLLECTING" if nxt is not None else "EVALUABLE",
        "version": FWD_VERSION,
        "family": FWD_FAMILY,
        "rules_hash": rules_hash(),
        "start": start_ts(db),
    }
