"""The shape of an alert, and the one word on it that describes the stop.

WHY THIS FILE EXISTS AT ALL. Every failure this layer has ever had was silent:
the message still sent, still looked right, and was simply wrong. The stop
label shipped one-sided for months, said nothing at all on the most common
alert, and printed its 30m-measured verdict on 15m alerts without anyone
noticing. So the boundaries are pinned here — and since 11 Sep, so is the
LAYOUT, because the alert stopped being a pile of optional chips and became a
fixed table that a reference card teaches people to read. A row that silently
stops rendering breaks the card, not just the message.

RENAMED FROM test_risk_verdict.py, WITH THE THING IT TESTS. take/flat/skip
became tight/normal/wide and the timeframe gate came off; see the block above
stop_width in riptide/telegram.py for why. The old name described a verdict
that no longer exists.

    PYTHONPATH=. python3 tests/test_alert_layout.py     # exit 1 on any failure
"""
import re
import sys

sys.path.insert(0, ".")

from riptide.config import POI_INTERVAL, TREND_INTERVAL   # noqa: E402
from riptide.engine import Early, Setup, Sweep, tf_word    # noqa: E402
from riptide.telegram import (LABEL_W, RISK_TIGHT, RISK_WIDE,  # noqa: E402
                              early_message, stop_width, setup_message,
                              sweep_message)

fails = []


def check(ok, what):
    print(f"  {'PASS' if ok else 'FAIL'}  {what}")
    if not ok:
        fails.append(what)


def strip(s):
    return re.sub(r"<[^>]+>", "", s)


def rows(msg):
    """The message as {label: rest}, using the same fixed-width label column
    the renderer writes. A row that stops rendering disappears from here."""
    out = {}
    for line in strip(msg).split("\n"):
        m = re.match(rf"^(\S+)\s{{0,{LABEL_W}}}(.*)$", line)
        if m and len(m.group(1)) < LABEL_W:
            out[m.group(1)] = m.group(2).strip()
    return out


def setup(risk_pct, tf="Min30"):
    entry = 1.0
    s = Setup(symbol="APT_USDT", is_long=True, src="Pivot", level=0.9,
              entry=entry, stop=entry - risk_pct / 100,
              risk=entry * risk_pct / 100, grab_bar=0, mss_bar=0,
              mss_time=0, anchor_time=0, pivots=2, fvg_time=1789000000,
              tf=tf, poi=True, trend_dir=1, di_dir=1, last_price=entry)
    return s


def early_sig(risk_pct=2.34, tf="Min30"):
    return Early(symbol="APT_USDT", is_long=True, src="Pivot", level=0.9,
                 entry=1.0, stop=1.0 - risk_pct / 100, risk=risk_pct / 100,
                 sweep_bar=0, sweep_time=0, grab_time=0, fvg_bar=0,
                 fvg_time=1789000000, anchor_time=0, pivots=2,
                 bars_from_sweep=2, tf=tf, poi=True, trend_dir=1, di_dir=1,
                 last_price=1.0)


print("the three zones")
for pct, want in ((0.50, "tight"), (1.19, "tight"), (1.20, "normal"),
                  (2.34, "normal"), (2.60, "normal"), (2.61, "wide"),
                  (9.00, "wide")):
    got = stop_width(pct)
    check(got == want, f"{pct:>5.2f}% -> {got!r} (want {want!r})")

print("\nthe boundaries are inclusive at the bottom, exclusive at the top")
check(stop_width(RISK_TIGHT) == "normal",
      f"exactly {RISK_TIGHT}% is inside the band, not below it")
check(stop_width(RISK_WIDE) == "normal",
      f"exactly {RISK_WIDE}% is inside the band, not above it")

print("\nNO TIMEFRAME GATE, and that is the change of 11 Sep")
for tf in ("Min15", "Min30", "Min60", "Hour4", "Day1"):
    check("normal" in rows(setup_message(setup(2.34, tf)))["Stop"],
          f"{tf} says 'normal' — the word describes the STOP, and a stop has "
          f"a width on every timeframe")
check("wide" in rows(setup_message(setup(4.0, "Hour4")))["Stop"],
      "including a timeframe the band's RETURNS were never measured on: the "
      "old gate existed to stop a verdict travelling, and there is no verdict")

print("\nEARLY SIGNALS GET THE WORD TOO, which they never did before")
line = rows(early_message(early_sig(2.34)))["Stop"]
check("normal" in line, f"an early 30m signal in the band says so: {line!r}")
check("wide" in rows(early_message(early_sig(4.2)))["Stop"],
      "and a 4.2% early stop is called wide rather than left unlabelled")

print("\nthe fixed layout: every trade alert has all three labelled rows")
for name, msg in (("confirmed", setup_message(setup(2.34))),
                  ("early", early_message(early_sig())),
                  ("sweep", sweep_message(Sweep(
                      symbol="LINK_USDT", is_high=False, src="Day",
                      level=21.4, sweep_bar=0, sweep_time=1789000000,
                      struct_level=22.1, sweep_extreme=21.28, anchor_time=0,
                      pivots=0, pools=1, rvol=0.7, trend_dir=1, tf="Min30",
                      poi=True, di_dir=1, last_price=21.55)))):
    r = rows(msg)
    for label in ("move", "context", "when"):
        check(label in r, f"{name}: the {label!r} row is present")
    check("chart" in r.get("when", ""),
          f"{name}: the chart link is on the 'when' row")

print("\nthe number rows")
r = rows(setup_message(setup(2.34)))
for label in ("Entry", "Stop", "Target"):
    check(label in r, f"a confirmed setup has a {label!r} row")
check("3R" not in strip(setup_message(setup(2.34))),
      "3R is gone — the tracker scores at 2R and so does every study, so a "
      "second unmeasured target beside the measured one is not printed")
check("2R" in r["Target"], "the target row names the R multiple it is")

print("\na sweep has no order levels and does not pretend to")
sw = rows(sweep_message(Sweep(
    symbol="LINK_USDT", is_high=False, src="Day", level=21.4, sweep_bar=0,
    sweep_time=1789000000, struct_level=22.1, sweep_extreme=21.28,
    anchor_time=0, pivots=0, pools=1, rvol=0.7, trend_dir=1, tf="Min30",
    poi=True, di_dir=1, last_price=21.55)))
check("Entry" not in sw and "Stop" not in sw and "Target" not in sw,
      "no Entry, Stop or Target on a raid that has not confirmed anything")
check("Level" in sw and "Needs" in sw,
      "it carries where the raid went and what the shift would need instead")

print("\nthe context row names the timeframes it actually read")
ctx = rows(setup_message(setup(2.34)))["context"]
check(tf_word(POI_INTERVAL) in ctx,
      f"the POI's own timeframe ({tf_word(POI_INTERVAL)}), not a literal word "
      f"that goes stale when the key moves")
check(tf_word(TREND_INTERVAL) in ctx,
      f"and the trend's ({tf_word(TREND_INTERVAL)})")

print("\nIT LABELS, IT DOES NOT GATE — every width still sends in full")
for pct in (0.9, 2.34, 3.12, 9.0):
    r = rows(setup_message(setup(pct)))
    check(all(k in r for k in ("Entry", "Stop", "Target", "move", "context",
                               "when")),
          f"{pct}% risk still sends a complete alert")

print("\n" + ("ALL PASS" if not fails
               else f"{len(fails)} FAILED:\n  " + "\n  ".join(fails)))
sys.exit(1 if fails else 0)
