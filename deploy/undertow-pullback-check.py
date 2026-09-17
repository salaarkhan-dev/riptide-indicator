"""Do the Pine and the port apply the SAME pullback rule?

    python3 deploy/undertow-pullback-check.py

WHY THIS EXISTS. The parity chain covers the structure engine and nothing else:

    undertow-ms-check.py   undertow.pine's section 3 == v2.pine's
    ms-py-parity.py        v2.pine's engine == ms_struct.py
    test_undertow_port.py  ms_struct.py == the port's structure()

Sections 5, 6 and 7 have no v2 counterpart, so they are covered by BEHAVIOUR
tests in the port -- and the Pine is not in those. The pullback rule lives in
section 6. Until this file, the only thing holding the two copies together on
that path was somebody reading them side by side, which is exactly the
arrangement that let `rr` default to 2.0 in one file and 3.0 in the other.

WHAT IT CHECKS, and it is deliberately modest. Not the logic -- a statement
level diff between Pine and Python over this block would need an exception
table longer than the check. What it checks is that **both files mention every
term of the rule**, so a change to one side that is not mirrored fails here
instead of silently making the chart and the studies two different strategies.

That catches the realistic failure. It does NOT catch a term that is present in
both and wrong in one, and it does not pretend to.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PINE = ROOT / "indicators/undertow/pine/riptide-undertow.pine"
PORT = ROOT / "indicators/undertow/port/undertow.py"

# Every term of the pullback rule, with the spelling each file uses. Adding a
# term to one side means adding a row here, which means adding it to the other
# side too -- that is the whole mechanism.
TERMS = [
    ("the pullback resets on a direction flip",
     r"biasDir != nz\(biasDir\[1\]", r"biasDir != prevDir"),
    ("… and on a new extreme in the trend direction",
     r"bMinX != nz\(bMinX\[1\]", r'st\["msMinX"\]\[i\] != prevMinX'),
    ("the extreme is tracked as a RUNNING high in a downtrend",
     r"biasDir < 0 and high >= pbExt", r"biasDir < 0 and c\.h >= pbExt"),
    ("… and a running low in an uptrend",
     r"biasDir > 0 and low <= pbExt", r"biasDir > 0 and c\.l <= pbExt"),
    ("the pullback's START is recorded, and only on a reset",
     r"pbStartX := bar_index", r"pbStartX = i"),
    ("locTol — bars past the ANCHOR a pin may sit",
     r"anchorX <= locTol", r"anchorX\) <= p\.locTol"),
    ("pinAt — the pullback extreme, or the TREND extreme",
     r"pinAt == sAnchTrend \? \(biasDir < 0 \? bMinX : bMaxX\)",
     r"p\.pinAt == PIN_TREND"),
    ("… and the pullback minimums apply to the pullback anchor only",
     r"pinAt != sAnchPull or \(pbAge >= pbMinAge",
     r"p\.pinAt == PIN_PULL:\n\s+locOk = \(locOk and pbAge >= p\.pbMinAge"),
    ("pbMinAge — bars the pullback must have run",
     r"pbAge >= pbMinAge", r"pbAge >= p\.pbMinAge"),
    ("pbMinDepth — fraction of the impulse given back",
     r"pbDepth >= pbMinDepth", r"pbDepth >= p\.pbMinDepth"),
    ("… measured to the pullback extreme, not the close",
     r"\(pbExt - bMin\) / pbLeg", r"\(pbExt - mn\) / leg"),
]

# `pbStartX` must be assigned on the RESET branch and nowhere else. If it were
# also set where pbExtX is updated, the age would restart every time the
# pullback made a new extreme and `pbMinAge` would silently mean nothing.
ONCE = [("pine", PINE, r"pbStartX :="), ("port", PORT, r"pbStartX = i\b")]

# `pinAt` WAS HERE AND IS NOW IN TERMS ABOVE -- UNDERTOW_V3.md measured the
# anchor and its prereg's clause for a null-but-harmless result is that it goes
# on the chart, selectable, defaulting to v1. `famPriority` stays port-only: it
# was measured in the same study, did nothing recoverable, and an input nothing
# supports is the habit that gave group 1 twenty inputs for four settings.
PORT_ONLY_TERMS = [
    ("famPriority — hammer first in bearish, star first in bullish",
     r"p\.famPriority and not isPriority"),
]


def main() -> int:
    pine, port = PINE.read_text(), PORT.read_text()
    bad = []
    for label, pin_re, port_re in TERMS:
        if not re.search(pin_re, pine):
            bad.append((label, f"MISSING FROM THE PINE — /{pin_re}/"))
        if not re.search(port_re, port):
            bad.append((label, f"MISSING FROM THE PORT — /{port_re}/"))

    for label, pat in PORT_ONLY_TERMS:
        if not re.search(pat, port):
            bad.append((label, f"MISSING FROM THE PORT — /{pat}/"))

    for who, path, pat in ONCE:
        n = len(re.findall(pat, path.read_text()))
        if n != 1:
            bad.append((f"pbStartX is assigned {n} times in the {who}",
                        "it must be set on the RESET branch and nowhere else, "
                        "or the pullback's age restarts whenever it makes a "
                        "new extreme and pbMinAge quietly means nothing"))

    print(f"{len(TERMS)} pullback terms compared across "
          f"{PINE.name} and {PORT.name}, plus {len(PORT_ONLY_TERMS)} "
          f"port-only")
    if not bad:
        print("\nBOTH FILES APPLY EVERY TERM OF THE PULLBACK RULE.")
        print("Presence only — the LOGIC of sections 5-7 is held by")
        print("indicators/undertow/tests/test_undertow_port.py, which the")
        print("Pine is not in. This is the guard against the two drifting,")
        print("not proof that they agree.")
        return 0
    print(f"\n{len(bad)} DISAGREEMENT(S):")
    for label, why in bad:
        print(f"    {label}\n        {why}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
