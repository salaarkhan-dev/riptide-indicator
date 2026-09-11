"""The take / skip / flat label on the alert.

WHY THIS FILE EXISTS AT ALL. The verdict is three words that tell a reader
whether to put money on a setup, derived from a measurement they cannot see, and
until now nothing checked it. It shipped one-sided for months, quietly said
nothing on the most common alert of all, and printed its 30m-measured verdict on
15m alerts without anyone noticing. Every one of those is a silent failure — the
message still sends, still looks right, and is simply wrong. So the boundaries,
the timeframe gate and the confirmed-only rule are pinned here.

    PYTHONPATH=. python3 tests/test_risk_verdict.py     # exit 1 on any failure
"""
import re
import sys

sys.path.insert(0, ".")

from riptide.engine import Early, Setup                 # noqa: E402
from riptide.telegram import (RISK_TIGHT, RISK_WIDE, early_message,  # noqa: E402
                              risk_verdict, setup_message)

fails = []


def check(ok, what):
    print(f"  {'PASS' if ok else 'FAIL'}  {what}")
    if not ok:
        fails.append(what)


def plain(msg, needle):
    line = [x for x in msg.split("\n") if needle in x]
    return re.sub(r"<[^>]+>", "", line[0]) if line else ""


def setup(risk_pct, tf="Min30"):
    entry = 1.0
    return Setup(symbol="APT_USDT", is_long=True, src="Pivot", level=0.9,
                 entry=entry, stop=entry - risk_pct / 100,
                 risk=entry * risk_pct / 100, grab_bar=0, mss_bar=0,
                 mss_time=0, anchor_time=0, pivots=2, fvg_time=1789000000,
                 tf=tf, poi=True, trend_dir=1, di_dir=1, last_price=entry)


print("the three zones, on the timeframe the band was measured on")
for pct, want in ((0.50, "flat"), (1.19, "flat"), (1.20, "take"),
                  (2.34, "take"), (2.60, "take"), (2.61, "skip"),
                  (9.00, "skip")):
    got = risk_verdict(pct, "Min30")
    check(got == want, f"{pct:>5.2f}% -> {got!r} (want {want!r})")

print("\nthe boundaries are inclusive at the bottom, exclusive at the top")
check(risk_verdict(RISK_TIGHT, "Min30") == "take",
      f"exactly {RISK_TIGHT}% is inside the band, not below it")
check(risk_verdict(RISK_WIDE, "Min30") == "take",
      f"exactly {RISK_WIDE}% is inside the band, not skipped")

print("\nno verdict on a timeframe the band was never measured on")
for tf in ("Min15", "Min5", "Hour1", "Hour4"):
    check(risk_verdict(2.34, tf) == "",
          f"{tf} stays silent rather than borrowing the 30m number")
check(risk_verdict(2.34) == "",
      "a caller that passes no timeframe gets nothing, so a new call site "
      "cannot acquire a verdict by accident")
check(risk_verdict(9.0, "Min15") == "",
      "even 'skip' is withheld off-timeframe — the gate is not one-sided")

print("\nthe rendered alert")
check("2.34% risk · take" in plain(setup_message(setup(2.34)), "Stop"),
      "a 30m confirmed setup inside the band prints the verdict")
check(plain(setup_message(setup(2.34, "Min15")), "Stop").strip()
      == "Stop   0.9766  2.34% risk",
      "the same setup on 15m prints the risk and no verdict")
check("· skip" in plain(setup_message(setup(3.12)), "Stop"),
      "a wide stop still prints skip")
check("· flat" in plain(setup_message(setup(0.90)), "Stop"),
      "a tight stop prints flat rather than nothing")

print("\nthe alert is still SENT whatever the verdict says — it labels, it "
      "does not filter")
for pct in (0.9, 2.34, 3.12):
    msg = setup_message(setup(pct))
    check("Entry" in msg and "2R" in msg,
          f"{pct}% risk still sends a complete setup message")

print("\nearly signals get no verdict at any distance")
e = Early(symbol="APT_USDT", is_long=True, src="Pivot", level=0.9, entry=1.0,
          stop=0.9766, risk=0.0234, sweep_bar=0, sweep_time=0, grab_time=0,
          fvg_bar=0, fvg_time=1789000000, anchor_time=0, pivots=2,
          bars_from_sweep=2,
          tf="Min30", poi=True, trend_dir=1, di_dir=1, last_price=1.0)
line = plain(early_message(e), "Stop")
check("take" not in line and "skip" not in line and "flat" not in line,
      f"early on 30m inside the band says nothing: {line.strip()!r}")

print("\n" + ("ALL PASS" if not fails
               else f"{len(fails)} FAILED:\n  " + "\n  ".join(fails)))
sys.exit(1 if fails else 0)
