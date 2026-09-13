"""The printed entry and stop must agree with the printed risk %.

A LINK alert read "Entry 12.71 · Stop 12.57 · 1.15% risk". Those prices give
1.10%: the percentage came from the real values and fmt() had rounded the
prices under it. Anyone placing the order from the message was 3% of the risk
away from the intended entry.

This checks the invariant that failure broke — risk recomputed from the
PRINTED prices must match the printed percentage — across the price ranges
the bot actually alerts on.

    PYTHONPATH=. python3 tests/test_price_precision.py
"""
import os
import sys

os.environ.setdefault("TELEGRAM_TOKEN", "x")
os.environ.setdefault("TELEGRAM_CHAT_ID", "1")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from riptide.telegram import fmt          # noqa: E402

# (entry, stop) pairs spanning the ranges MEXC perps live in, each a realistic
# 0.4%-2% stop with digits past what 4 significant figures could hold.
CASES = [
    (0.0804812, 0.0795034),      # sub-1: was already fine
    (0.172371, 0.169962),
    (3.14159, 3.10182),
    (12.7149, 12.5687),          # the LINK case
    (47.8231, 47.2044),
    (127.1493, 125.6152),        # the expensive end of the broken range
    (884.2617, 873.1044),
    (3421.887, 3378.114),        # >= 1000 branch
    (78664.93, 77930.41),
]

fails = 0
print(f"  {'entry':>12}{'stop':>12}{'true %':>9}{'printed %':>11}"
      f"{'err':>9}   verdict")
for entry, stop in CASES:
    true_pct = 100 * (entry - stop) / entry
    pe, ps = float(fmt(entry).replace(",", "")), float(fmt(stop).replace(",", ""))
    shown_pct = 100 * (pe - ps) / pe
    # Error expressed in units of RISK, which is what it costs a trader.
    err_r = abs(shown_pct - true_pct) / true_pct
    ok = err_r < 0.01                     # under 1% of the risk
    fails += not ok
    print(f"  {fmt(entry):>12}{fmt(stop):>12}{true_pct:>8.2f}%"
          f"{shown_pct:>10.2f}%{err_r:>8.1%}   {'PASS' if ok else 'FAIL'}")

print()
if fails:
    print(f"{fails} case(s) print a risk that disagrees with the printed prices")
    sys.exit(1)
print("printed prices reproduce the printed risk to within 1% of risk")
