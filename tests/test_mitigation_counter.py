"""poi_state must count zone visits the way the pre-registration says.

The BTC sign bug survived a correct pre-registration because nothing ever
checked that the code computed the variable the document described. This is
that check, run BEFORE the held-out numbers are read.

    PYTHONPATH=. python3 tests/test_mitigation_counter.py
"""
import os
import sys

os.environ.setdefault("TELEGRAM_TOKEN", "x")
os.environ.setdefault("TELEGRAM_CHAT_ID", "1")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import research.env                                      # noqa: E402,F401
from riptide.engine import Candle                        # noqa: E402
from research.studies.mitigation import poi_state        # noqa: E402

DAY = 86400
ZONE = (10 * DAY, True, 100.0, 110.0)      # formed day 10, bull, 100-110
RAID = 20 * DAY                            # raid on day 20
STEP = DAY


def bar(day, lo, hi, close):
    return Candle(day * DAY, (lo + hi) / 2, hi, lo, close, 1.0)


def run(name, bars, want_wick, want_close):
    got = poi_state(bars, [ZONE], RAID, 105.0, True, STEP)
    if got is None:
        print(f"  FAIL  {name}: no zone matched")
        return False
    _, wick, close_ = got
    ok = wick == want_wick and close_ == want_close
    print(f"  {'PASS' if ok else 'FAIL'}  {name:<46}"
          f"wick {wick} (want {want_wick})  close {close_} (want {want_close})")
    return ok


# Bars far from the zone, used as filler.
FAR = [bar(d, 200.0, 210.0, 205.0) for d in range(11, 20)]

cases = [
    ("never approached -> 0 and 0", FAR, 0, 0),
    ("one wick in, closes outside -> 1 wick, 0 close",
     [bar(11, 95.0, 105.0, 90.0)] + FAR[1:], 1, 0),
    ("one close inside -> 1 and 1",
     [bar(11, 95.0, 112.0, 105.0)] + FAR[1:], 1, 1),
    ("three separate visits -> 3 and 3",
     [bar(11, 95.0, 112.0, 105.0), bar(13, 95.0, 112.0, 106.0),
      bar(15, 95.0, 112.0, 107.0)] + [bar(d, 200.0, 210.0, 205.0)
                                      for d in (12, 14, 16, 17, 18, 19)], 3, 3),
    # The two exclusions that are the entire fix.
    ("visit ONLY on the formation bar -> 0 and 0",
     [bar(10, 95.0, 112.0, 105.0)] + FAR, 0, 0),
    ("visit ONLY on the raid bar -> 0 and 0",
     FAR + [bar(20, 95.0, 112.0, 105.0)], 0, 0),
    ("visit AFTER the raid does not count -> 0 and 0",
     FAR + [bar(25, 95.0, 112.0, 105.0)], 0, 0),
    ("touching the exact zone edge counts as a wick",
     [bar(11, 110.0, 120.0, 118.0)] + FAR[1:], 1, 0),
]

ok = all(run(n, sorted(b, key=lambda c: c.t), w, c) for n, b, w, c in cases)

# A zone older than the age cap must not match, same as the shipped filter.
# The raid is moved out rather than the zone back: 60 days after a day-10 zone
# is 50 bars, comfortably past the 30-bar cap. An earlier version of this case
# put the raid at day 20 and asserted no match -- 20 bars is INSIDE the cap, so
# the test was wrong and the code was right.
far_raid = poi_state(FAR, [ZONE], 60 * DAY, 105.0, True, STEP)
near_raid = poi_state(FAR, [ZONE], 35 * DAY, 105.0, True, STEP)
print(f"  {'PASS' if far_raid is None else 'FAIL'}  "
      f"zone 50 bars old is past the cap and does not match")
print(f"  {'PASS' if near_raid is not None else 'FAIL'}  "
      f"zone 25 bars old is inside the cap and still matches")
ok = ok and far_raid is None and near_raid is not None

print()
if not ok:
    print("poi_state does NOT compute the variable the pre-registration describes")
    sys.exit(1)
print("poi_state computes visits as PREREG_mitigation.md describes")
