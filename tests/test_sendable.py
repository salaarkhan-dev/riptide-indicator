"""A pick must name an alert that was actually sent.

THE BUG THIS PINS, VERBATIM FROM THE CHAT:

    ⚡ EARLY B 🟢 LONG SOL_USDT 15m
    🔗 5 on this close, size once · 1000BONK took this move 7m ago

and no 1000BONK alert ever arrived. The scanner had restarted seven minutes
earlier, rescanned its 600 bars of history, and rediscovered every signal in
it — almost all already in `seen` from before the restart. tag_event_pick ran
over that whole rediscovered backlog, so a message that went out hours ago, or
was recorded and never sent at all, claimed the 120-minute window. Every
sibling for the next two hours then deferred to a symbol the reader could not
look up.

The class of bug is bigger than the one chip. Three taggers made claims about
the alert STREAM while looking at the signal LIST, and six gates sit between
the two. "5 on this close" counted messages that never came; "also 30m"
pointed at one that did not exist.

WHAT IS ASSERTED: that each of the six gates removes a signal from the taggers'
view, that a gated signal can never become the pick, and — the part that is
easy to lose in a later refactor — that the view is a FILTER and not a
suppressor: every signal is still in `results`, still recorded, still armed.

    PYTHONPATH=. python3 tests/test_sendable.py     # exit 1 on any failure
"""
import sys

sys.path.insert(0, ".")

from riptide import decide                               # noqa: E402
from riptide.config import BAR_SECONDS, FRESH_BARS       # noqa: E402
from riptide.engine import Early, Setup                  # noqa: E402
from riptide.scanner import (pair_early, sendable,       # noqa: E402
                             tag_event_pick, will_send)
from riptide.storage import early_sig, sig_id            # noqa: E402

fails = []
NOW = 1789000000


def check(ok, what):
    print(f"  {'PASS' if ok else 'FAIL'}  {what}")
    if not ok:
        fails.append(what)


class FakeDB:
    """Only the two dedupe queries the predicate makes. Nothing is faked about
    WHICH queries those are — sig_id and early_sig are the real ones."""

    def __init__(self, seen=()):
        self.seen = set(seen)
        self.queries = 0

    def execute(self, sql, args=()):
        self.queries += 1
        hit = args and args[0] in self.seen
        return type("C", (), {"fetchone": lambda _s: (1,) if hit else None})()


def setup(sym, tf="Min30", t=NOW, poi=True, trend=1, is_long=True):
    s = Setup(symbol=sym, is_long=is_long, src="Pivot", level=0.9, entry=1.0,
              stop=0.98, risk=0.02, grab_bar=0, mss_bar=0, mss_time=t,
              anchor_time=0, pivots=2, fvg_time=t, poi=poi, trend_dir=trend,
              di_dir=trend, last_price=1.0)
    s.tf = tf
    return s


def early(sym, tf="Min30", t=NOW, poi=True, trend=1, is_long=True):
    e = Early(symbol=sym, is_long=is_long, src="Pivot", level=0.9, entry=1.0,
              stop=0.98, risk=0.02, sweep_bar=0, sweep_time=t, grab_time=t,
              fvg_bar=0, fvg_time=t, anchor_time=0, pivots=2,
              bars_from_sweep=2, poi=poi, trend_dir=trend, di_dir=trend,
              last_price=1.0)
    e.tf = tf
    return e


def wrap(setups=(), early_sigs=()):
    return [(list(setups), [], list(early_sigs), [])]


# The freshness clock the signals above are measured against. detected_time is
# derived from the signal, so "now" has to sit at a known distance from it.
FRESH = NOW + 1
STALE = NOW + FRESH_BARS * BAR_SECONDS["Min30"] + BAR_SECONDS["Min30"] + 10

print("each of the six gates removes a signal from the taggers' view")

db = FakeDB()
s = setup("AAA_USDT")
check(will_send(db, s, False, FRESH, False, set()),
      "a fresh, in-POI, well-graded setup with nothing paused is sendable")

seen_db = FakeDB([sig_id(s)])
check(not will_send(seen_db, s, False, FRESH, False, set()),
      "DUPE: already in `seen` — the restart case that produced the bug")

e = early("BBB_USDT")
check(not will_send(FakeDB([early_sig(e)]), e, True, FRESH, False, set()),
      "DUPE: the early table is checked with the early key, not the setup one")

check(not will_send(db, s, False, STALE, False, set()),
      "STALE: outside the freshness window")

check(not will_send(db, setup("CCC_USDT", poi=False), False, FRESH, False,
                    set()),
      "POI: not in a zone, with POI_REQUIRED on")

# GRADE is asserted at the end of the file: with the default MIN_GRADE=C it
# cannot be reached without also failing POI, so isolating it needs a reload.

check(not will_send(db, s, False, FRESH, True, set()),
      "MUTE: /pause, or the first run")

paired_e = early("EEE_USDT")
key = (paired_e.symbol, paired_e.tf, paired_e.fvg_time, paired_e.is_long)
check(not will_send(db, paired_e, True, FRESH, False, {key}),
      "PAIRED: the confirmed setup on the same gap will carry this one")

print("\npair_early is what supplies that set, and it still stamps the setup")
pair = setup("FFF_USDT")
pe = early("FFF_USDT")
res = wrap([pair], [pe])
p = pair_early(res)
check((pe.symbol, pe.tf, pe.fvg_time, pe.is_long) in p,
      "the early on the same gap is in the suppress set")
check(getattr(pair, "also_early", 0), "and the setup carries it")

print("\nTHE BUG ITSELF: a gated signal cannot become the pick")
# 1000BONK ranks first on every key — same timeframe, same band, confirmed —
# so under the old code it won the window. It is already in `seen`.
bonk = setup("1000BONK_USDT", tf="Min60")
sol = early("SOL_USDT", tf="Min15")
res = wrap([bonk], [sol])
db = FakeDB([sig_id(bonk)])
live = sendable(res, db, FRESH, False, pair_early(res))
check(live[0][0] == [] and live[0][2] == [sol],
      "the already-sent setup is out of the view, the early one is in")

decide.reset()
tag_event_pick(live)
check(sol.event_pick, "so the alert that WILL be sent is the pick")
check(sol.event_of == "SOL_USDT",
      "and it names itself, not a symbol with no message behind it")
check(not getattr(bonk, "event_pick", False),
      "the gated signal is not the pick")
check(getattr(bonk, "event_of", "") == "",
      "and was not tagged at all — it is never rendered")

print("\nthe view is a FILTER, not a suppressor")
res = wrap([bonk], [sol])
db = FakeDB([sig_id(bonk)])
before = [list(res[0][0]), list(res[0][2])]
sendable(res, db, FRESH, False, set())
check([list(res[0][0]), list(res[0][2])] == before,
      "`results` is untouched, so the send loop still records and arms every "
      "signal exactly as before — only the TAGGERS see less")

print("\nthe cluster count now counts messages, not signals")
sent_1 = early("GGG_USDT")
sent_2 = early("HHH_USDT")
muted = early("III_USDT", poi=False)
res = wrap([], [sent_1, sent_2, muted])
live = sendable(res, FakeDB(), FRESH, False, set())
check(len(live[0][2]) == 2,
      "three early signals found, two of them sendable")
decide.reset()
tag_event_pick(live)
check(sent_1.event_size == 2,
      f"'N symbols' says 2, not 3: got {sent_1.event_size}")
check(getattr(muted, "event_size", None) is None,
      "and the muted one carries no count to render")

print("\nnothing is sendable while paused, so no pick claims the window")
decide.reset()
res = wrap([setup("JJJ_USDT")], [])
live = sendable(res, FakeDB(), FRESH, True, set())
tag_event_pick(live)
check(live[0][0] == [], "a paused cycle offers the tagger nothing")
after = setup("KKK_USDT")
tag_event_pick(wrap([after]))
check(after.event_pick,
      "so the next unpaused signal claims a window that was never taken")

print("\nGRADE, isolated — it needs its own config to be reachable at all")
# With MIN_GRADE=C the only failing grade is D, and D requires no POI, so the
# POI gate always fires first and the grade gate is never the reason. Raising
# the floor to A makes a B signal fail on grade ALONE, which is the only way to
# show the gate is wired. config reads the key at IMPORT time, so the whole
# chain is reloaded — the same trap test_poi_interval documents.
import importlib                                         # noqa: E402
import os                                                # noqa: E402
os.environ["RIPTIDE_MIN_GRADE"] = "A"
for m in ("riptide.scanner", "riptide.decide", "riptide.telegram",
          "riptide.engine", "riptide.config"):
    sys.modules.pop(m, None)
strict = importlib.import_module("riptide.scanner")
strict_early = importlib.import_module("riptide.engine").Early
# In a POI with the trend agreeing: grade B as an early signal, which is the
# best an early signal can be, and still under a floor of A.
b_grade = strict_early(
    symbol="LLL_USDT", is_long=True, src="Pivot", level=0.9, entry=1.0,
    stop=0.98, risk=0.02, sweep_bar=0, sweep_time=NOW, grab_time=NOW,
    fvg_bar=0, fvg_time=NOW, anchor_time=0, pivots=2, bars_from_sweep=2,
    poi=True, trend_dir=1, di_dir=1, last_price=1.0)
b_grade.tf = "Min30"
check(not strict.will_send(FakeDB(), b_grade, True, FRESH, False, set()),
      "a grade-B early signal, in a POI and fresh, is held back by the grade "
      "floor alone")
os.environ.pop("RIPTIDE_MIN_GRADE", None)
for m in ("riptide.scanner", "riptide.decide", "riptide.telegram",
          "riptide.engine", "riptide.config"):
    sys.modules.pop(m, None)

print("\n" + ("ALL PASS" if not fails
               else f"{len(fails)} FAILED:\n  " + "\n  ".join(fails)))
sys.exit(1 if fails else 0)
