"""The event_pick column: the migration, the six states, and the INSERT.

WHY A REAL DATABASE AND A REAL MIGRATION. `riptide/tracker.py` carries a long
comment about the day two migrations shared a guard, `tf` was never added to
databases that had already taken the `poi` one, and `arm()` then raised "no
such column" on every trade signal — which, because arm() runs just before the
send, aborted the cycle and stopped every trade alert for most of a day while
sweeps kept arriving normally. It never reproduced locally because a fresh
database is created with the full schema and runs no migration at all.

So this test does what that day needed: builds an OLD database without the
column, migrates it, and arms into it. A fresh-schema test alone would pass
while the deployed database broke.

    PYTHONPATH=. python3 tests/test_tracker_event.py   # exit 1 on any failure
"""
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, ".")
os.environ.setdefault("RIPTIDE_TRACK", "1")

from riptide import tracker                             # noqa: E402
from riptide.engine import Setup                        # noqa: E402
from riptide.scanner import tag_event_pick              # noqa: E402

fails = []


def check(ok, what):
    print(f"  {'PASS' if ok else 'FAIL'}  {what}")
    if not ok:
        fails.append(what)


def setup(sym, risk_pct, t=1789000000):
    entry = 1.0
    s = Setup(symbol=sym, is_long=True, src="Pivot", level=0.9, entry=entry,
              stop=entry - risk_pct / 100, risk=entry * risk_pct / 100,
              grab_bar=0, mss_bar=0, mss_time=t, anchor_time=0, pivots=2,
              fvg_time=t, poi=True, trend_dir=1, di_dir=1, last_price=entry)
    s.tf = "Min30"
    return s


def fresh_db():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    tracker.init(db)
    return db


# 3 AND 4 CHANGED MEANING ON 11 SEP. 3 used to mark a cluster the rule
# declined to pick from; decide.py now always names a pick, because withholding
# measured 4.08 recovery against 4.85 (research/studies/pick_rule.py). The two
# codes now carry the WEAK flag — the cluster whose best member is still a
# "skip" — so the forward data can answer whether best-of-a-wide-cluster is
# worth taking. Rows written either side of 11 Sep mean different things and
# any analysis crossing it must filter on armed_time.
print("the six states")
for label, build, want in (
        ("solo signal -> 0", lambda: [setup("AAA_USDT", 2.0)], 0),
        ("the pick -> 1", lambda: [setup("AAA_USDT", 2.0),
                                   setup("BBB_USDT", 4.0)], 1),
        ("a sibling -> 2", lambda: [setup("AAA_USDT", 4.0),
                                    setup("BBB_USDT", 2.0)], 2),
        ("pick of a WEAK cluster -> 3", lambda: [setup("AAA_USDT", 3.4),
                                                 setup("BBB_USDT", 4.1)], 3),
        ("sibling of a weak cluster -> 4", lambda: [setup("BBB_USDT", 4.1),
                                                    setup("AAA_USDT", 3.4)],
         4)):
    g = build()
    tag_event_pick([(g, [], [], [])])
    check(tracker._event_state(g[0]) == want,
          f"{label}  (got {tracker._event_state(g[0])})")

check(tracker._event_state(setup("AAA_USDT", 2.0)) == -1,
      "a signal the scanner never tagged -> -1, not 0: 'no cluster' and "
      "'nobody asked' are different facts")

print("\nit reaches the database, on a FRESH schema")
db = fresh_db()
g = [setup("AAA_USDT", 4.0), setup("BBB_USDT", 2.0)]
for x in g:
    x.breadth = 2
tag_event_pick([(g, [], [], [])])
for i, x in enumerate(g):
    tracker.arm(db, f"sig{i}", x, from_bar=1789000000)
rows = {r["symbol"]: r for r in db.execute("SELECT * FROM outcomes")}
check(len(rows) == 2, f"both rows armed ({len(rows)})")
check(rows["BBB_USDT"]["event_pick"] == 1, "the pick stored 1")
check(rows["AAA_USDT"]["event_pick"] == 2, "the sibling stored 2")
check(rows["AAA_USDT"]["breadth"] == 2, "breadth still stored alongside it")

print("\nand on a database MIGRATED from one without the column")
with tempfile.TemporaryDirectory() as d:
    path = os.path.join(d, "old.db")
    old = sqlite3.connect(path)
    # The schema as it stood before this change: everything except event_pick.
    cols = [c.strip() for c in tracker._COLUMNS.split(",")
            if c.strip() != "event_pick"]
    old.execute(f"CREATE TABLE outcomes({', '.join(cols)})")
    old.execute(f"INSERT INTO outcomes({cols[0]}) VALUES('ancient')")
    old.commit()
    old.close()

    db2 = sqlite3.connect(path)
    db2.row_factory = sqlite3.Row
    have_before = {r[1] for r in db2.execute("PRAGMA table_info(outcomes)")}
    check("event_pick" not in have_before,
          "the old database genuinely lacks the column before migrating")

    tracker.init(db2)
    have_after = {r[1] for r in db2.execute("PRAGMA table_info(outcomes)")}
    check("event_pick" in have_after, "init() adds it")

    old_row = db2.execute("SELECT event_pick FROM outcomes "
                          "WHERE sig='ancient'").fetchone()
    check(old_row["event_pick"] == -1,
          "the pre-existing row backfills to -1, not 0 — it was never recorded")

    g = [setup("CCC_USDT", 2.0)]
    tag_event_pick([(g, [], [], [])])
    tracker.arm(db2, "after-migration", g[0], from_bar=1789000000)
    r = db2.execute("SELECT event_pick, symbol FROM outcomes "
                    "WHERE sig='after-migration'").fetchone()
    check(r is not None and r["symbol"] == "CCC_USDT",
          "arming into the MIGRATED database works — this is the case that "
          "broke the bot once and never reproduced on a fresh schema")
    check(r is not None and r["event_pick"] == 0, "and stores the solo state")

print("\nthe column count and the placeholder count agree")
import inspect  # noqa: E402
import re  # noqa: E402
src = inspect.getsource(tracker.arm)
ph = re.search(r"VALUES\((\?(?:,\?)*)\)", src).group(1).count("?")
n = len([c.strip() for c in tracker._COLUMNS.split(",")])
check(ph == n, f"{n} columns, {ph} placeholders — a mismatch here is a silent "
               f"shift of every value into the wrong column")

print("\n" + ("ALL PASS" if not fails
               else f"{len(fails)} FAILED:\n  " + "\n  ".join(fails)))
sys.exit(1 if fails else 0)
