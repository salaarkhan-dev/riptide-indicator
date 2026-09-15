"""LIT_FORWARD_V1 — the guards that make forward evidence worth collecting.

Every test here protects one property the pre-registration depends on. If any
of them fails, the experiment is not measuring what it claims to measure.

Run: PYTHONPATH=. python3 tests/test_lit_forward.py
"""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import research.env  # noqa: F401,E402  (must precede riptide.config)

from riptide.engine import Candle                                # noqa: E402
from riptide.strategies.lit import forward, render, signals       # noqa: E402
from riptide.strategies.lit.runner import event_id                # noqa: E402
from riptide.strategies.lit.types import (                        # noqa: E402
    FWD_VERSION, PENDING, RESOLVED, TIMED_OUT, RULES, ForwardSetup,
    rules_hash)

FAILED: list[str] = []


def check(name, got, want):
    ok = got == want
    print(f"  [{'ok' if ok else 'FAIL'}] {name}: got {got!r}, want {want!r}")
    if not ok:
        FAILED.append(name)


def near(name, got, want, tol=1e-9):
    ok = abs(got - want) <= tol
    print(f"  [{'ok' if ok else 'FAIL'}] {name}: got {got!r}, want ~{want!r}")
    if not ok:
        FAILED.append(name)


def fresh_db():
    path = tempfile.mktemp(suffix=".db")
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT)")
    forward.init(db)
    return db, path


def bars(rows, t0=1_700_000_000, step=1800):
    return [Candle(t0 + i * step, o, h, l, c, 0.0)
            for i, (o, h, l, c) in enumerate(rows)]


def mk(sid="s1", direction=1, entry=100.0, stop=90.0, sig_t=1_700_000_000):
    return ForwardSetup(
        setup_id=sid, strategy_family="lit", strategy_version=FWD_VERSION,
        rules_hash=rules_hash(), symbol="BTC_USDT", timeframe="Min30",
        direction=direction, structure_time=sig_t - 3600, signal_time=sig_t,
        entry_time=sig_t, entry_price=entry, initial_stop=stop,
        initial_risk_price=abs(entry - stop), bos_price=130.0,
        active_price=105.0, market_event_id=event_id(sig_t, direction > 0))


print("\n1. the frozen rules cannot change silently")
h1 = rules_hash()
check("rules_hash is stable across calls", rules_hash(), h1)
check("version is V2", FWD_VERSION, "LIT_FORWARD_V2")
check("primary arm is T6_PIVOT", RULES["primary_arm"], "T6_PIVOT")
check("control arm is BOS_TARGET", RULES["control_arm"], "BOS_TARGET")
check("stop is the prior pullback pivot", RULES["stop"],
      "prior_confirmed_pullback_pivot")
check("a missing stop is a SKIP", RULES["stop_missing"], "skip")
check("no stop buffer", RULES["stop_buffer"], 0.0)
check("horizon matches Stage C", RULES["horizon_bars"], 500)
check("min_rr matches Stage C", RULES["min_rr"], 0.5)

# THE POLICIES ARE PART OF THE RULES. Before this block, flipping a policy
# inside research.lit_v3 left rules_hash() unmoved — the rules named the engine
# module but not how it was configured, so the one thing this file promises to
# make impossible was possible. P9 is the policy that carried V1 to V2.
import research.lit_v3 as _lit                                   # noqa: E402
check("P9 is on", RULES["policies"]["seekCh"], "leg")
for _p in ("outside", "reseed", "eqBreak", "seekCh"):
    check(f"RULES records the engine's real {_p}",
          RULES["policies"][_p], getattr(_lit.POL, _p))
_sp = RULES["policies"]["seekCh"]
RULES["policies"]["seekCh"] = "none"
check("flipping a POLICY changes the hash too", rules_hash() != h1, True)
RULES["policies"]["seekCh"] = _sp
check("and restoring it restores the hash", rules_hash(), h1)

_saved = RULES["min_rr"]
RULES["min_rr"] = 0.6
check("changing a rule CHANGES the hash", rules_hash() != h1, True)
RULES["min_rr"] = _saved
check("and restoring it restores the hash", rules_hash(), h1)

print("\n2. activation timestamp, and it survives a restart")
db, path = fresh_db()
check("no start before activation", forward.start_ts(db), None)
t0 = forward.activate(db, 1_700_000_000)
check("activate stamps the start", t0, 1_700_000_000)
check("activate is IDEMPOTENT", forward.activate(db, 1_999_999_999), t0)
db.close()
db = sqlite3.connect(path)
check("start survives a reconnect", forward.start_ts(db), 1_700_000_000)

print("\n3. the start gate — no backfill, ever")
check("pre-start setup rejected", forward.eligible(1_699_999_999, t0), False)
check("setup AT the start rejected", forward.eligible(t0, t0), False)
check("post-start setup accepted", forward.eligible(t0 + 1, t0), True)
check("no start means nothing is eligible",
      forward.eligible(t0 + 1, None), False)

print("\n4. recording is idempotent, and identity is immutable")
s = mk(sig_t=t0 + 1800)
check("first record writes", forward.record(db, s), True)
check("second record is a no-op", forward.record(db, s), False)
s2 = mk(sig_t=t0 + 1800)
s2.entry_price = 999.0
forward.record(db, s2)
row = forward.pending(db)[0]
near("entry NOT overwritten by a repeat pass", row["entry_price"], 100.0)
check("one row only", len(forward.pending(db)), 1)
check("stored version", row["strategy_version"], FWD_VERSION)
check("stored rules_hash", row["rules_hash"], rules_hash())

print("\n5. the same setup_id is produced deterministically")
a = signals.setup_id(FWD_VERSION, "BTC_USDT", "Min30", 1, 1700)
b = signals.setup_id(FWD_VERSION, "BTC_USDT", "Min30", 1, 1700)
check("deterministic", a, b)
check("direction is part of the key",
      a != signals.setup_id(FWD_VERSION, "BTC_USDT", "Min30", -1, 1700), True)
# Named V1 explicitly rather than "some other version": this is the guard that
# stops a V2 setup colliding with the V1 row for the same bar of the same
# symbol, which is what "never pooled" rests on.
check("version is part of the key — V1 and V2 cannot collide",
      a != signals.setup_id("LIT_FORWARD_V1", "BTC_USDT", "Min30", 1, 1700),
      True)

print("\n6. ONE entry and ONE stop, TWO independent exits")
# Long: entry 100, stop 90 (risk 10), BOS 130. Price runs to 131 (control
# takes its target), then falls back through the trailed stop at 110.
cs = bars([(100, 101, 99, 100),        # 0 signal bar - resolves nothing
           (100, 115, 99, 114),        # 1 +1.5R, arms the trail
           (114, 131, 113, 130),       # 2 control target hit
           (130, 130, 105, 106)])      # 3 trailed stop at 110 hit
trail = [None, 110.0, 110.0, 110.0]
out = forward.score_pair(cs, 0, 100.0, 90.0, True, 130.0, trail)
check("the pair resolved", out is not None, True)
check("control exited at its target", out["control_exit_reason"], "target")
check("T6 exited at the trailed stop", out["t6_exit_reason"], "stop")
check("the two arms disagree", out["control_r"] != out["t6_r"], True)
near("paired delta is exactly t6 - control", out["paired_delta_r"],
     out["t6_r"] - out["control_r"])
check("control beat T6 here", out["control_r"] > out["t6_r"], True)
check("state is resolved", out["state"], RESOLVED)

print("\n7. same-bar ambiguity resolves conservatively")
cs2 = bars([(100, 101, 99, 100),
            (100, 131, 89, 120)])      # target AND stop on one bar
out2 = forward.score_pair(cs2, 0, 100.0, 90.0, True, 130.0, [None, None])
check("the loss is taken, not the win", out2["control_exit_reason"], "stop")
check("control R is negative", out2["control_r"] < 0, True)

print("\n8. an open pair is NOT marked to market")
flat = bars([(100, 101, 99, 100)] + [(100, 101, 99, 100)] * 30)
check("still open -> no result", forward.score_pair(
    flat, 0, 100.0, 90.0, True, 130.0, [None] * 31), None)
long_flat = bars([(100, 101, 99, 100)] * 520)
out3 = forward.score_pair(long_flat, 0, 100.0, 90.0, True, 130.0,
                          [None] * 520)
check("only a GENUINE horizon closes it", out3 is not None, True)
check("and it is flagged as timed out", out3["state"], TIMED_OUT)

print("\n9. pending -> resolved transition persists")
db2, path2 = fresh_db()
forward.activate(db2, 1_600_000_000)
s3 = mk(sid="pair1", sig_t=cs[0].t)
forward.record(db2, s3)
check("starts pending", forward.pending(db2)[0]["state"], PENDING)
check("resolve reports success",
      forward.resolve(db2, forward.pending(db2)[0], cs,
                      [{"kind": "pb", "dir": 1, "px": 110.0, "bar": 1}]), True)
check("no longer pending", len(forward.pending(db2)), 0)
r = forward.resolved(db2)[0]
check("state is terminal", r["state"] in (RESOLVED, TIMED_OUT), True)
near("paired delta stored exactly", r["paired_delta_r"],
     r["t6_r"] - r["control_r"], 1e-9)
near("entry unchanged by resolution", r["entry_price"], 100.0)
near("stop unchanged by resolution", r["initial_stop"], 90.0)
db2.close()
db2 = sqlite3.connect(path2)
r2 = forward.resolved(db2)[0]
near("outcome survives a restart", r2["paired_delta_r"], r["paired_delta_r"])
check("a resolved setup is not re-recorded",
      forward.record(db2, mk(sid="pair1", sig_t=cs[0].t)), False)

print("\n10. market-event grouping reuses the production definition")
e1 = event_id(1_700_000_000, True)
e2 = event_id(1_700_000_000 + 5, True)
e3 = event_id(1_700_000_000, False)
check("same window + direction is ONE bet", e1, e2)
check("opposite direction is a different bet", e1 != e3, True)
rows = [{"market_event_id": "w|L", "paired_delta_r": 1.0, "signal_time": 1},
        {"market_event_id": "w|L", "paired_delta_r": 3.0, "signal_time": 2},
        {"market_event_id": "x|L", "paired_delta_r": 5.0, "signal_time": 3}]
check("correlated signals average into one observation",
      forward.bets(rows, "paired_delta_r"), [2.0, 5.0])

print("\n11. reporting never emits a verdict")
summ = forward.summary(db2)
check("status is a collection state",
      summ["status"] in ("COLLECTING", "EVALUABLE"), True)
txt = render.stats_block(summ)
check("no banned language in /stats", render.check_language(txt), [])
alert = render.alert_text(mk())
check("no banned language in the alert", render.check_language(alert), [])
check("alert is marked research", "LIT RESEARCH" in alert, True)
check("alert names the version", FWD_VERSION in alert, True)
check("alert disclaims", "RESEARCH ONLY" in alert, True)
check("banned list actually bites",
      render.check_language("this is a validated profitable strategy"),
      ["profitable", "validated"])

print("\n12. production is untouched")
from riptide import config                                        # noqa: E402
check("collection ships OFF", config.LIT_FORWARD, False)
check("alerts ship OFF", config.LIT_FORWARD_ALERTS, False)
check("structure ships OFF", config.LIT_STRUCTURE, False)
db3, _ = fresh_db()
before = {r[0] for r in db3.execute(
    "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
forward.activate(db3, 1)
forward.record(db3, mk(sid="x1", sig_t=2))
after = {r[0] for r in db3.execute(
    "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
check("LIT adds no table beyond its own", after - before, set())
check("LIT writes only to its own table and meta",
      all(t in ("meta", forward.TABLE) or t.startswith("sqlite")
          for t in after), True)

print("\n13. the production hook exists and is inert when the flag is off")
import asyncio                                                    # noqa: E402
import inspect                                                    # noqa: E402
from riptide.strategies.lit import runner                          # noqa: E402
from riptide import scanner                                        # noqa: E402
src = inspect.getsource(scanner.cycle)
check("scanner.cycle calls the hook", "run_if_enabled" in src, True)
check("the hook is exception-guarded so research cannot break alerting",
      "production unaffected" in src, True)
check("hook returns inert with LIT_FORWARD off",
      asyncio.get_event_loop().run_until_complete(
          runner.run_if_enabled(None, None, [])), {"enabled": False})

print("\n14. an UNOBSERVED setup leaves the sample, it is not invented")
db4, _ = fresh_db()
forward.activate(db4, 1)
old = mk(sid="stale1", sig_t=1_600_000_000)
forward.record(db4, old)
n = forward.sweep_stale(db4, {"Min30": 1800}, now=1_600_000_000 + 10**7)
check("the stale pending was swept", n, 1)
check("nothing left pending", len(forward.pending(db4)), 0)
check("and it is NOT counted as an outcome", len(forward.resolved(db4)), 0)
row = db4.execute(
    f"SELECT state, paired_delta_r FROM {forward.TABLE} "
    f"WHERE setup_id='stale1'").fetchone()
check("state is ambiguous", row[0], "ambiguous")
check("it carries no R", row[1], None)
fresh_pending = mk(sid="young1", sig_t=1_600_000_000)
forward.record(db4, fresh_pending)
check("a young pending setup is left alone",
      forward.sweep_stale(db4, {"Min30": 1800}, now=1_600_000_000 + 100), 0)

print("\n" + ("FAILED: " + ", ".join(FAILED) if FAILED else "ALL PASS"))
sys.exit(1 if FAILED else 0)
