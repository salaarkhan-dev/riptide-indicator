"""Tests for the scorer. Run: python3 research/test_harness.py

The first test is the regression for the bug that invalidated a session of
measurements. If it ever passes trivially again, everything below it is
worthless, so it is written to fail loudly rather than quietly.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from riptide.engine import Candle                          # noqa: E402
from research.harness import (Outcome, simulate, simulate_market,  # noqa: E402
                              mean_se, buckets)

FAILED = []


def check(name, got, want, eps=1e-9):
    ok = abs(got - want) < eps if isinstance(want, float) else got == want
    print(f"  [{'ok' if ok else 'FAIL'}] {name}: got {got!r}, want {want!r}")
    if not ok:
        FAILED.append(name)


def bars(rows):
    return [Candle(1000 + 60 * i, o, h, l, c)
            for i, (o, h, l, c) in enumerate(rows)]


print("\n1. THE REGRESSION — an outcome before the fill must not count")
# Long, entry 100, stop 90, target 110 (1R).
#  bar0 signal.  bar1 spikes to 115 — ABOVE target, but the entry at 100 has
#  not been touched, so no position exists.  bar2 dips to 100 and fills.
#  bar3 drops to 90 and stops out.  The honest answer is -1R.
cs = bars([(105, 106, 104, 105),      # 0 signal
           (105, 115, 104, 112),      # 1 target level, NOT filled
           (112, 113,  99, 101),      # 2 fills at 100
           (101, 102,  89,  90)])     # 3 stop
o = simulate(cs, 0, 100.0, 90.0, True, target_r=1.0, fee_pct=0.0)
check("filled", o.filled, True)
check("fill bar is 2 not 1", o.fill_bar, 2)
check("scored as a LOSS, not the pre-fill win", o.r, -1.0)

print("\n2. Unfilled scores 0.0 and pays no fee")
cs = bars([(105, 106, 104, 105)] + [(105, 108, 103, 106)] * 20)
o = simulate(cs, 0, 90.0, 85.0, True, target_r=1.0)
check("not filled", o.filled, False)
check("r is exactly zero", o.r, 0.0)

print("\n3. Stop wins when one bar spans both")
cs = bars([(100, 100, 100, 100),
           (100, 100,  99, 100),          # fills at 100
           (100, 120,  85, 110)])         # spans target 110 AND stop 90
o = simulate(cs, 0, 100.0, 90.0, True, target_r=1.0, fee_pct=0.0)
check("pessimistic: stop", o.r, -1.0)

print("\n4. Fee is charged in R, and scales inversely with stop size")
cs = bars([(100, 100, 100, 100), (100, 100, 99.5, 100), (100, 111, 100, 110)])
tight = simulate(cs, 0, 100.0, 99.0, True, target_r=1.0, fee_pct=0.08)
wide = simulate(cs, 0, 100.0, 90.0, True, target_r=1.0, fee_pct=0.08)
check("1% stop pays 0.08R", round(tight.r, 4), round(1 - 0.08, 4))
check("10% stop pays 0.008R", round(wide.r, 4), round(1 - 0.008, 4))

print("\n5. Break-even arms on the CLOSE, not intrabar")
# bar2 wicks to 115 (past the 1.5R arm at 115) but closes at 104, so the stop
# must NOT have moved; bar3 then trades to 95, which is above the original
# stop of 90 and below a break-even stop — the trade must still be open.
cs = bars([(100, 100, 100, 100),
           (100, 100,  99, 100),
           (100, 116, 100, 104),
           (104, 105,  95, 100),
           (100, 121, 100, 120)])
o = simulate(cs, 0, 100.0, 90.0, True, target_r=2.0,
             be_arm_r=1.5, be_lock_r=0.1, fee_pct=0.0)
check("survived to the 2R target", o.r, 2.0)

print("\n6. Partial: half at 1R, remainder to 3R, stop to +0.1R")
cs = bars([(100, 100, 100, 100),
           (100, 100,  99, 100),
           (100, 111, 100, 110),          # 1R -> half out, stop to 100.1
           (110, 111, 100,  100)])        # back to the break-even stop
o = simulate(cs, 0, 100.0, 90.0, True, target_r=3.0, part_at_r=1.0,
             part_to_r=3.0, be_lock_r=0.1, fee_pct=0.0)
check("0.5*1R banked + 0.5*0.1R", round(o.r, 6), round(0.5 * 1.0 + 0.5 * 0.1, 6))

print("\n7. Shorts mirror longs exactly")
# short: entry 100 stop 110, fills on the bar that reaches up to 100,
# then falls to the 90 target.
sw = bars([(95, 95, 95, 95), (95, 100, 95, 98), (98, 99, 89, 90)])
# long: entry 100 stop 90, fills, then stops out.
ll = bars([(105, 105, 105, 105), (105, 105, 99, 101), (101, 102, 89, 90)])
check("short reaches its target", 
      simulate(sw, 0, 100.0, 110.0, False, target_r=1.0, fee_pct=0.0).r, 1.0)
check("long stops out",
      simulate(ll, 0, 100.0, 90.0, True, target_r=1.0, fee_pct=0.0).r, -1.0)

print("\n8. MFE and MAE are measured from the FILL, not the signal")
cs = bars([(100, 130, 100, 100),          # huge move BEFORE the fill
           (100, 100,  99, 100),
           (100, 105,  95, 100),
           (100, 100,  89,  90)])
o = simulate(cs, 0, 100.0, 90.0, True, target_r=5.0, fee_pct=0.0)
check("mfe ignores the pre-fill spike", round(o.mfe, 3), 0.5)

print("\n9. Helpers")
m, se = mean_se([1.0, -1.0, 1.0, -1.0])
check("mean of a symmetric set", m, 0.0)
bs = buckets([Outcome(1.0, True, 1, 0, 0, 2), Outcome(-1.0, True, 1, 0, 0, 2)],
             lambda x: x.r > 0)
check("binary feature makes two buckets", len(bs), 2)

print("\n10. Outcome.exit says WHY, so a timeout stops passing as a win")
cs = bars([(100, 101, 99, 100), (100, 101, 99, 100), (100, 101, 89, 90)])
check("stop", simulate(cs, 0, 100.0, 90.0, True, target_r=5.0,
                       fee_pct=0.0).exit, "stop")
cs = bars([(100, 101, 99, 100), (100, 101, 99, 100), (100, 111, 99, 110)])
check("target", simulate(cs, 0, 100.0, 90.0, True, target_r=1.0,
                         fee_pct=0.0).exit, "target")
cs = bars([(100, 101, 99, 100), (100, 101, 99, 100), (100, 101, 99, 100)])
check("timeout", simulate(cs, 0, 100.0, 90.0, True, target_r=5.0,
                          fee_pct=0.0).exit, "timeout")
check("unfilled says nothing",
      simulate(bars([(200, 201, 199, 200)] * 3), 0, 100.0, 90.0, True,
               fee_pct=0.0).exit, "")

print("\n11. simulate_market: the ENTRY BAR resolves nothing")
# THE POINT OF THIS SCORER. Entry is bar 0's CLOSE of 100. That bar's low of
# 80 is far below the 90 stop — but it printed BEFORE the position existed,
# so it is not a stop-out. mss_entry.py's local copy gets this wrong.
cs = bars([(120, 121, 80, 100),       # 0 entry at the close; low is pre-entry
           (100, 101, 95, 100),
           (100, 131, 99, 130)])      # 3R target at 130
o = simulate_market(cs, 0, 100.0, 90.0, True, target_r=3.0, fee_maker=0.0,
                    fee_taker=0.0)
check("not stopped by its own entry bar", o.exit, "target")
check("and it pays 3R", round(o.r, 6), 3.0)
# ...and the target is equally barred from the entry bar.
cs = bars([(100, 140, 99, 100), (100, 101, 89, 90)])
o = simulate_market(cs, 0, 100.0, 90.0, True, target_r=3.0, fee_maker=0.0,
                    fee_taker=0.0)
check("nor filled by its own entry bar's high", o.exit, "stop")
# Stop wins a bar that spans both, exactly as simulate does.
cs = bars([(100, 101, 99, 100), (100, 131, 89, 120)])
check("stop wins a bar spanning both",
      simulate_market(cs, 0, 100.0, 90.0, True, target_r=3.0, fee_maker=0.0,
                      fee_taker=0.0).exit, "stop")
# No room to score is None, not a zero. A zero would be a real trade that
# broke even; this is a trade that cannot be measured.
check("no bar after the entry is None",
      simulate_market(bars([(100, 101, 99, 100)]), 0, 100.0, 90.0, True), None)
# Market in pays TAKER, and the cost is fee/risk_pct — 10% risk here.
o = simulate_market(bars([(100, 101, 99, 100), (100, 101, 89, 90)]), 0,
                    100.0, 90.0, True, fee_maker=0.02, fee_taker=0.06)
check("a stopped market trade pays taker both ways",
      round(o.r, 6), round(-1.0 - 0.12 / 10.0, 6))
# Shorts mirror.
cs = bars([(100, 101, 99, 100), (100, 101, 69, 70)])
check("short reaches its target",
      round(simulate_market(cs, 0, 100.0, 110.0, False, target_r=3.0,
                            fee_maker=0.0, fee_taker=0.0).r, 6), 3.0)

print("\n12. simulate_market manages the stop exactly as simulate does")
# Long, entry 100, stop 90 (1R = 10). Bar 1 CLOSES at 110 = +1R, arming the
# break-even stop at +0.1R = 101. Bar 2 collapses to 89 — a full stop without
# the arm, a +0.1R scratch with it.
cs = bars([(100, 101,  99, 100),      # 0 entry at the close
           (100, 111,  99, 110),      # 1 closes at +1R -> arms
           (110, 111,  89,  90)])     # 2 would have been a full stop
plain = simulate_market(cs, 0, 100.0, 90.0, True, target_r=3.0,
                        fee_maker=0.0, fee_taker=0.0)
armed = simulate_market(cs, 0, 100.0, 90.0, True, target_r=3.0, be_arm_r=1.0,
                        be_lock_r=0.1, fee_maker=0.0, fee_taker=0.0)
check("without a break-even it is a full loss", round(plain.r, 6), -1.0)
check("with one it is a +0.1R scratch", round(armed.r, 6), 0.1)
check("and still reports exit=stop", armed.exit, "stop")
# The arm is on the CLOSE, not intrabar: a bar that only WICKS to +1R and
# closes back must not arm, or the scratch would be manufactured.
cs = bars([(100, 101,  99, 100),
           (100, 115,  99, 100),      # wicks past +1R, closes at entry
           (100, 101,  89,  90)])
check("a wick to +1R does not arm",
      round(simulate_market(cs, 0, 100.0, 90.0, True, target_r=3.0,
                            be_arm_r=1.0, be_lock_r=0.1, fee_maker=0.0,
                            fee_taker=0.0).r, 6), -1.0)
# Partial: half out at 1R, stop to +0.1R, remainder aiming at 3R and stopped.
cs = bars([(100, 101,  99, 100),
           (100, 111,  99, 110),      # 1R -> half banked, stop to 101
           (110, 111, 100, 100)])     # back to the moved stop
o = simulate_market(cs, 0, 100.0, 90.0, True, target_r=3.0, part_at_r=1.0,
                    part_to_r=3.0, be_lock_r=0.1, fee_maker=0.0, fee_taker=0.0)
check("0.5*1R banked + 0.5*0.1R", round(o.r, 6), round(0.5 + 0.05, 6))
# Defaults must not change anything: the old behaviour is still the default.
cs = bars([(100, 101, 99, 100), (100, 101, 89, 90)])
check("defaults are unchanged",
      round(simulate_market(cs, 0, 100.0, 90.0, True, fee_maker=0.0,
                            fee_taker=0.0).r, 6), -1.0)

print("\n" + ("FAILED: " + ", ".join(FAILED) if FAILED else "ALL PASS"))
sys.exit(1 if FAILED else 0)
