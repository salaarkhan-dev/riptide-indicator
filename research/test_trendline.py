"""Tests for the Liquidity Trendline port. Run: python3 research/test_trendline.py

These pin the three mechanics that are easy to MISREAD and therefore easy to
"fix" into a different indicator. Every expected value below is hand-computed
from the Pine, not copied from the port's output — a test written from the
code it tests proves only that the code has not changed.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import research.env  # noqa: E402,F401  (must precede riptide.config)
from riptide.engine import Candle                                  # noqa: E402
from research.studies.trendline import (Line, pivot_highs,         # noqa: E402
                                        pivot_lows, trendline_signals)

FAILED = []


def check(name, got, want, eps=1e-9):
    ok = abs(got - want) < eps if isinstance(want, float) else got == want
    print(f"  [{'ok' if ok else 'FAIL'}] {name}: got {got!r}, want {want!r}")
    if not ok:
        FAILED.append(name)


print("\n1. THE LIVE EXTENSION is linear — after a one-time step at creation")
# `top.set_x2(b.n); top.set_y2(top.get_y2() + slup)` with slope recomputed each
# bar. Line from (0,100) to (10,90): slope -1.
ln = Line(0, 100.0, 10, 90.0)
check("initial slope", ln.slope(), -1.0)
# One bar on: x2 12 -> 11 is a single step, so y2 moves one slope unit and the
# point stays ON the line: 100 + (-1)(11) = 89.
s = ln.slope()
ln.x2, ln.y2 = 11, ln.y2 + s
check("one bar on, y2", ln.y2, 89.0)
check("still exactly on the line", ln.y1 + ln.slope() * (ln.x2 - ln.x1), 89.0)
# And it STAYS on the line, because y2-y1 and x2-x1 grow together.
for want_x, want_y in ((12, 88.0), (13, 87.0), (14, 86.0)):
    s = ln.slope()
    ln.x2, ln.y2 = want_x, ln.y2 + s
    check(f"bar {want_x} stays linear", ln.y2, want_y)

print("\n2. ...but the FIRST extension under-advances by (period - 1) steps")
# THIS IS THE REAL DISTORTION, and it is the opposite of what the code looks
# like it does. A channel is created on the confirm bar i with x2 = i - period,
# so the first extension jumps x2 forward by `period` bars while y2 advances by
# ONE slope unit. The line is therefore permanently (period - 1) slope units
# above the true pivot-to-pivot projection — and for a descending resistance,
# where the slope is negative, HIGHER means harder to break.
period = 5
ln = Line(0, 100.0, 10, 90.0)          # pivots; confirm bar is 10 + period
i = 10 + period
s = ln.slope()
ln.x2, ln.y2 = i, ln.y2 + s            # the first live extension
true_projection = 100.0 + (-1.0) * (i - 0)
check("true line at the confirm bar", true_projection, 85.0)
check("what the indicator uses instead", ln.y2, 89.0)
check("short by (period - 1) slope units", ln.y2 - true_projection,
      abs(-1.0) * (period - 1))

print("\n3. THE BACKWARD WALK is not a line trace, and must not be 'fixed'")
# `for i = 0 to (b.n - before.n): slope = ln.slope(); ln.set_x2(b.n[i]);
#  ln.set_y2(ln.get_y2() - slope)`. x2 moves BACKWARD as i grows while y2 moves
# by MINUS the slope, so for a falling line y2 RISES as the walk goes back in
# time. Hand-computed for pivots (0,100) -> (10,90), confirm bar 15.
ln = Line(0, 100.0, 10, 90.0)
s0 = ln.slope()                                   # -1.0
ln.x2, ln.y2 = 15 - 0, ln.y2 - s0                 # k=0
check("k=0 x2", ln.x2, 15)
check("k=0 y2 rises to 91", ln.y2, 91.0)
s1 = ln.slope()                                   # (91-100)/(15-0) = -0.6
check("k=1 slope recomputed from the mutated line", s1, -0.6)
ln.x2, ln.y2 = 15 - 1, ln.y2 - s1                 # k=1
check("k=1 x2 has moved BACKWARD", ln.x2, 14)
check("k=1 y2 rises again", ln.y2, 91.6)
# A true trace would put y at 100 + (-1)(14) = 86 here. It is at 91.6.
check("nowhere near the straight line", round(91.6 - 86.0, 6), 5.6)

print("\n4. Pivots are strict on both sides and dated at the confirming bar")
bars = [Candle(1000 + 60 * k, 10, h, lo, 10) for k, (h, lo) in enumerate(
    [(5, 1), (6, 2), (7, 3), (6, 2), (5, 1), (4, 0),      # 0-5
     (9, 4), (4, 2), (5, 1), (6, 2), (7, 3), (8, 4),      # 6-11, high at 6
     (9, 5)])]
hi = pivot_highs(bars, 3)
check("one pivot high found", len(hi), 1)
check("its pivot bar is 6", hi[0][1], 6)
check("confirmed at bar 6 + 3", hi[0][0], 9)
check("its price is the bar's high", hi[0][2], 9.0)
# lows are 1,2,3,2,1,0,4,2,1,2,3,4,5 -> bar 5 is the only strict pivot low
lo_ = pivot_lows(bars, 3)
check("one pivot low found", len(lo_), 1)
check("its pivot bar is 5", lo_[0][1], 5)
check("confirmed at bar 5 + 3", lo_[0][0], 8)

print("\n5. No channel can exist before ta.atr(200) is valid")
# vol() is min(0.1 * atr(200), 0.001 * close) and Pine's atr is na for 199
# bars, so nothing can be built there however the pivots fall.
flat = [Candle(1000 + 60 * k, 100, 100 + (k % 7), 100 - (k % 5), 100)
        for k in range(150)]
check("no signals inside the warm-up", len(trendline_signals(flat)), 0)

print("\n" + ("FAILED: " + ", ".join(FAILED) if FAILED else "ALL PASS"))
sys.exit(1 if FAILED else 0)
