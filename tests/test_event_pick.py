"""One signal per market event: the grouping, the ranking, and the promise
that nothing is suppressed.

WHY THIS IS TESTED RATHER THAN EYEBALLED. The rule is the largest measured
effect in the bot — recovery 0.13 taking every alert against 5.46 taking one
per event — and every way it can break is silent. A ranking that is not
deterministic names a different symbol on a re-scan of the same hour. A
grouping keyed wrongly names three picks for one market move. And a label that
accidentally becomes a gate would suppress alerts the evidence is nowhere near
strong enough to suppress.

REWRITTEN 11 SEP, AND THREE OF ITS OLD ASSERTIONS NOW ASSERT THE OPPOSITE.
That is the point of the rewrite rather than an embarrassment, so the three are
named here and each is tested in its new direction below:

  "a 30m close is also a 15m close — the timeframes stay separate" is now
  FALSE. They are one event. Keeping them separate is what produced a target
  chip on three messages for one raid, and grouping them is worth +3.46
  recovery (research/studies/pick_rule.py).

  "different bars are different events" is now FALSE for bars inside the same
  window. The window is one bar of the SLOWEST scanned timeframe, so two Min30
  signals half an hour apart are one event.

  "when EVERY member is a skip there is no pick at all" is now FALSE. A pick is
  always named. Withholding it scores 4.08 against 4.85, and the entire gap
  comes from those clusters. The endorsement worry that motivated the old
  behaviour is handled by changing the chip's WORDS, which is tested.

The band is still the first key WHEN THE TIMEFRAMES MATCH, which is what most
of the ranking assertions below exercise; the timeframe only outranks it when
two different charts are in the same event.

    PYTHONPATH=. python3 tests/test_event_pick.py     # exit 1 on any failure
"""
import re
import sys

sys.path.insert(0, ".")

from riptide.decide import describe, event_span         # noqa: E402
from riptide.decide import decide as decide_decide     # noqa: E402
from riptide.decide import reset as decide_reset       # noqa: E402
from riptide.engine import Early, Setup                 # noqa: E402
from riptide.scanner import event_rank, tag_event_pick  # noqa: E402
from riptide.telegram import marks, setup_message       # noqa: E402

fails = []

# EACH SCENARIO BELOW IS INDEPENDENT, so the standing pick from the previous one
# must not leak into it. Live that memory is the entire point — decide._LAST is
# what lets a 1h signal at 12:00 defer to a 15m pick sent at 11:30 — but a test
# that shared it would be testing the order its own cases happen to be written
# in rather than the rule.
_raw_tag = tag_event_pick


def tag_event_pick(results, *a, **k):                   # noqa: F811
    decide_reset()
    return _raw_tag(results, *a, **k)




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

print("\noutside the band is not one thing")
a, b = setup("ZZZ_USDT", 0.6), setup("AAA_USDT", 3.4)
check(min([a, b], key=event_rank) is a,
      "a tight 'flat' beats a wide 'skip' — the skip bootstrap is entirely "
      "below zero, the flat one straddles it")

print("\nan all-skip cluster still gets a pick, in different words")
grp = [setup("AAA_USDT", 3.4), setup("BBB_USDT", 4.1), setup("CCC_USDT", 5.0)]
for x in grp:
    x.breadth = 3
tag_event_pick([(grp, [], [], [])])
check(sum(1 for x in grp if x.event_pick) == 1,
      "one pick even when every member is a skip — withholding it measured "
      "4.08 recovery against 4.85")
check(all(x.event_of == "AAA_USDT" for x in grp),
      "and every sibling names it")
check(all(x.event_weak for x in grp), "the cluster is flagged weak")
check("best of a wide cluster" in (marks(grp[0]) or ""),
      "the chip names it WITHOUT a bare target — the endorsement worry is "
      "answered by wording, not by silence")
check("🎯 the pick" not in (marks(grp[0]) or ""),
      "and the confident chip is reserved for clusters that have one")
check("🔗 3 on this close" in (marks(grp[0]) or ""),
      "size-once still warns about the cluster")

print("\na cluster with one good member gets the confident chip")
mix = [setup("AAA_USDT", 4.0), setup("BBB_USDT", 2.0)]
for x in mix:
    x.breadth = 2
tag_event_pick([(mix, [], [], [])])
check(mix[1].event_pick and not mix[1].event_weak,
      "the in-band member is the pick and the cluster is not weak")
check("🎯 the pick" in (marks(mix[1]) or ""), "so the chip is the plain one")

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
check(all(x.event_size == 2 for x in tfs),
      "timeframes are now ONE event — a 30m raid and the 15m read of it are "
      "the same market move")

tfs = [setup("SLOW_USDT", 2.4, tf="Min60"), setup("AAA_USDT", 2.0, tf="Min15")]
tag_event_pick([(tfs, [], [], [])])
check(tfs[0].event_pick,
      "and the SLOWER timeframe wins even against an alphabetically earlier "
      "symbol in the same band")

tfs = [setup("SLOW_USDT", 3.9, tf="Min60"), setup("AAA_USDT", 2.0, tf="Min15")]
tag_event_pick([(tfs, [], [], [])])
check(tfs[0].event_pick,
      "the timeframe outranks the band: a 1h skip beats a 15m take. this is "
      "the measured ordering and the one with the weakest evidence — "
      "RIPTIDE_PICK_ORDER=band flips it")

span = event_span()
near = [setup("AAA_USDT", 2.0, t=1789002000),
        setup("BBB_USDT", 2.0, t=1789002000 + span // 2)]
tag_event_pick([(near, [], [], [])])
check(all(x.event_size == 2 for x in near),
      "everything of one direction in one scan is one event")

print("\nthe cooldown is a ROLLING window, held across scan cycles")
now = 1789002000
first = setup("AAA_USDT", 2.0)
tag_event_pick([([first], [], [], [])], now=now)
check(first.event_pick, "the first signal claims the window")

# The case the whole cooldown exists for: a 1h setup is not knowable until its
# bar closes, so it arrives in a LATER scan than the 15m read of the same move.
# Without memory it would claim a second pick and contradict a message already
# sent; with it, it points back.
later = setup("BBB_USDT", 2.0, tf="Min60")
decide_decide([([later], [], [], [])], now=now + span // 2)
check(not later.event_pick,
      "a signal arriving mid-window does NOT claim a second pick")
check(later.event_of == "AAA_USDT",
      "it names the pick already sent, so nothing is contradicted")
check(later.event_age == span // 2,
      "and carries its age, so the chip can say how long ago")
check(f"{span // 120}m ago" in (marks(later) or "") or later.event_age < 300,
      "which the chip renders as an age, not as a live instruction")

after = setup("CCC_USDT", 2.0)
decide_decide([([after], [], [], [])], now=now + span + 60)
check(after.event_pick, "once the window passes, a new pick is named")

decide_reset()
fresh = setup("DDD_USDT", 2.0)
decide_decide([([fresh], [], [], [])], now=now + 1)
check(fresh.event_pick,
      "reset() forgets the standing pick — a restart costs one extra chip, "
      "which decide.py documents rather than hides")

print("\nthe rendered chip")
grp = [setup("AAA_USDT", 4.0), setup("BBB_USDT", 2.0)]
for x in grp:
    x.breadth = 2
tag_event_pick([(grp, [], [], [])])
check(f"{event_span() // 60}m" in describe() and "tf" in describe(),
      f"/status can state the live rule: {describe()}")
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

print("\nRIPTIDE_PICK_ORDER=band flips the first key and nothing else")
import importlib                                        # noqa: E402
import os                                               # noqa: E402
os.environ["RIPTIDE_PICK_ORDER"] = "band"
# config reads the key at IMPORT time, so reloading decide alone would keep the
# old value — the same trap test_poi_interval documents.
for m in ("riptide.scanner", "riptide.decide", "riptide.telegram",
          "riptide.config"):
    sys.modules.pop(m, None)
band_first = importlib.import_module("riptide.decide")
flip = [setup("SLOW_USDT", 3.9, tf="Min60"),
        setup("AAA_USDT", 2.0, tf="Min15")]
band_first.decide([(flip, [], [], [])])
check(flip[1].event_pick,
      "under 'band' the 15m take beats the 1h skip — the exact case that "
      "inverts under 'tf'")
check("band" in band_first.describe(),
      f"and /status says so: {band_first.describe()}")
os.environ.pop("RIPTIDE_PICK_ORDER", None)
for m in ("riptide.scanner", "riptide.decide", "riptide.telegram",
          "riptide.config"):
    sys.modules.pop(m, None)

print("\nIT LABELS, IT DOES NOT GATE")
for x in grp:
    msg = setup_message(x)
    check("Entry" in msg and "2R" in msg and "Stop" in msg,
          f"{x.symbol} still sends a complete setup message"
          f"{'' if x.event_pick else ' even though it is NOT the pick'}")

print("\n" + ("ALL PASS" if not fails
               else f"{len(fails)} FAILED:\n  " + "\n  ".join(fails)))
sys.exit(1 if fails else 0)
