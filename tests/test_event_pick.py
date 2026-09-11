"""One signal per market event: the ranking, the grouping, and the promise
that nothing is suppressed.

WHY THIS IS TESTED RATHER THAN EYEBALLED. The rule is the only positive
portfolio result this project has, and every way it can break is silent. A
ranking that is not deterministic names a different symbol on a re-scan of the
same bar. A grouping keyed wrongly blends a 30m bundle with a 15m one and
picks across timeframes. And a label that accidentally becomes a gate would
suppress alerts the evidence is nowhere near strong enough to suppress.

    PYTHONPATH=. python3 tests/test_event_pick.py     # exit 1 on any failure
"""
import re
import sys

sys.path.insert(0, ".")

from riptide.engine import Early, Setup                 # noqa: E402
from riptide.scanner import event_rank, tag_event_pick  # noqa: E402
from riptide.telegram import marks, setup_message       # noqa: E402

fails = []


def check(ok, what):
    print(f"  {'PASS' if ok else 'FAIL'}  {what}")
    if not ok:
        fails.append(what)


def setup(sym, risk_pct, t=1789000000, is_long=True, tf="Min30"):
    entry = 1.0
    s = Setup(symbol=sym, is_long=is_long, src="Pivot", level=0.9, entry=entry,
              stop=entry - risk_pct / 100, risk=entry * risk_pct / 100,
              grab_bar=0, mss_bar=0, mss_time=t, anchor_time=0, pivots=2,
              fvg_time=t, poi=True, trend_dir=1, di_dir=1, last_price=entry)
    s.tf = tf
    return s


def early(sym, risk_pct, t=1789000000, is_long=True, tf="Min30"):
    entry = 1.0
    e = Early(symbol=sym, is_long=is_long, src="Pivot", level=0.9, entry=entry,
              stop=entry - risk_pct / 100, risk=entry * risk_pct / 100,
              sweep_bar=0, sweep_time=t, grab_time=t, fvg_bar=0, fvg_time=t,
              anchor_time=0, pivots=2, bars_from_sweep=2, poi=True,
              trend_dir=1, di_dir=1, last_price=entry)
    e.tf = tf
    return e


def plain(msg, needle):
    line = [x for x in msg.split("\n") if needle in x]
    return re.sub(r"<[^>]+>", "", line[0]) if line else ""


print("the band beats everything else")
a, b = setup("ZZZ_USDT", 2.0), setup("AAA_USDT", 4.0)
check(min([a, b], key=event_rank) is a,
      "an in-band signal is picked over an out-of-band one with an "
      "alphabetically earlier symbol")
a, b = setup("ZZZ_USDT", 2.0), setup("AAA_USDT", 0.5)
check(min([a, b], key=event_rank) is a, "and over a too-tight one")

print("\nconfirmed beats early, but only as a tie-break")
a, b = early("AAA_USDT", 2.0), setup("ZZZ_USDT", 2.0)
check(min([a, b], key=event_rank) is b,
      "both in band -> the confirmed setup wins")
a, b = early("AAA_USDT", 2.0), setup("ZZZ_USDT", 4.0)
check(min([a, b], key=event_rank) is a,
      "an in-band EARLY beats an out-of-band CONFIRMED: the band outranks "
      "the stream, which is the order of the evidence")

print("\nthe pick is deterministic")
rows = [setup(s, 2.0) for s in ("MMM_USDT", "AAA_USDT", "ZZZ_USDT")]
first = min(rows, key=event_rank).symbol
check(all(min(rows[::-1], key=event_rank).symbol == first for _ in range(5)),
      f"same winner regardless of input order ({first})")

print("\ngrouping")
grp = [setup("AAA_USDT", 4.0), setup("BBB_USDT", 2.0), setup("CCC_USDT", 5.0)]
tag_event_pick([(grp, [], [], [])])
check([x.event_size for x in grp] == [3, 3, 3], "every member knows the size")
check(sum(1 for x in grp if x.event_pick) == 1, "exactly one pick per event")
check(grp[1].event_pick and all(x.event_of == "BBB_USDT" for x in grp),
      "the in-band member is the pick and the others name it")

opp = [setup("AAA_USDT", 2.0), setup("BBB_USDT", 2.0, is_long=False)]
tag_event_pick([(opp, [], [], [])])
check(all(x.event_size == 1 for x in opp),
      "opposite directions on one bar are two events, not one")

tfs = [setup("AAA_USDT", 2.0, tf="Min30"), setup("BBB_USDT", 2.0, tf="Min15")]
tag_event_pick([(tfs, [], [], [])])
check(all(x.event_size == 1 for x in tfs),
      "a 30m close is also a 15m close — the timeframes stay separate")

apart = [setup("AAA_USDT", 2.0, t=1789000000),
         setup("BBB_USDT", 2.0, t=1789000000 + 1800)]
tag_event_pick([(apart, [], [], [])])
check(all(x.event_size == 1 for x in apart),
      "different bars are different events")

print("\nthe rendered chip")
grp = [setup("AAA_USDT", 4.0), setup("BBB_USDT", 2.0)]
for x in grp:
    x.breadth = 2
tag_event_pick([(grp, [], [], [])])
check("🎯 the pick" in (marks(grp[1]) or ""), "the pick says so")
check("pick is BBB" in (marks(grp[0]) or ""),
      "a sibling names the pick, without the quote currency")
check("🔗 2 on this close" in (marks(grp[0]) or ""),
      "the existing size-once chip is untouched")

lone = setup("AAA_USDT", 2.0)
lone.breadth = 1
tag_event_pick([([lone], [], [], [])])
check("pick" not in (marks(lone) or ""),
      "a solo signal gets no pick chip — no clutter when there is no choice")

print("\nIT LABELS, IT DOES NOT GATE")
for x in grp:
    msg = setup_message(x)
    check("Entry" in msg and "2R" in msg and "Stop" in msg,
          f"{x.symbol} still sends a complete setup message"
          f"{'' if x.event_pick else ' even though it is NOT the pick'}")

print("\n" + ("ALL PASS" if not fails
               else f"{len(fails)} FAILED:\n  " + "\n  ".join(fails)))
sys.exit(1 if fails else 0)
