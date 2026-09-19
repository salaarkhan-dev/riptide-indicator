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

import ast
import pathlib
import re
import sys


def _assignments(path: pathlib.Path, name: str) -> int:
    """How many times `name` is ASSIGNED, tuple targets included.

    A regex cannot tell `pbStartX = i` from `pbStartX=pbStartX` in a call, and
    the version of this check that tried counted five writes where there are
    three. The AST is the only reading that answers the question asked.
    """
    n = 0
    for node in ast.walk(ast.parse(path.read_text())):
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
            targets = [node.target]
        for t in targets:
            for sub in ast.walk(t):
                if isinstance(sub, ast.Name) and sub.id == name:
                    n += 1
    return n

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
]

# `pbStartX` must not be assigned where the pullback makes a NEW EXTREME. If it
# were, the age would restart on every new extreme and `pbMinAge` -- port-only
# now -- would silently mean nothing. The Pine still records the start for the
# panel's pullback row.
#
# TWO SITES ARE LEGITIMATE and there were two all along: the reset branch, and
# the `local pullback` anchor, which replaces the structural pullback outright
# with one it found itself. This rule counted ONE and passed anyway, because
# the port pattern was `pbStartX = i` and the port's anchor line reads
# `pbExtX, pbStartX, anchorX = locExX, locLoX, locExX` -- a tuple assignment
# the regex could not see. So the check was enforcing the count on the Pine
# only and calling it a two-copy invariant.
#
# Counting ANY assignment in both copies is the stronger reading, and it is
# what a third site would have to get past. The pair is named rather than the
# number loosened: each copy must set it on the reset AND at the local anchor,
# and nowhere else.
# The port is counted through the AST, not a regex. The first attempt at
# widening this used /pbStartX\s*[,=]/ and got FIVE, because `pbStartX = None`,
# `pbStartX=pbStartX` and the tuple target all match a pattern that cannot tell
# a write from a read. Counting assignment TARGETS is the question being asked.
ONCE_PINE = (PINE, r"pbStartX :=", 2)
ONCE_PORT = (PORT, "pbStartX", 3)          # + the `= None` initialiser
# The two sites, asserted by shape so "two assignments" cannot be satisfied by
# two of the wrong kind.
SITES = [
    ("the reset branch records the pullback's start",
     r"pbStartX := bar_index", r"pbStartX = i\b"),
    ("the local anchor replaces it with the pullback IT found",
     r"pbStartX := locLoX", r"pbExtX, pbStartX, anchorX = locExX, locLoX"),
]

# `pinAt` WAS HERE AND IS NOW IN TERMS ABOVE -- UNDERTOW_V3.md measured the
# anchor and its prereg's clause for a null-but-harmless result is that it goes
# on the chart, selectable, defaulting to v1. `famPriority` stays port-only: it
# was measured in the same study, did nothing recoverable, and an input nothing
# supports is the habit that gave group 1 twenty inputs for four settings.
PORT_ONLY_TERMS = [
    ("famPriority — hammer first in bearish, star first in bullish",
     r"p\.famPriority and not isPriority"),
    # THE TWO PULLBACK MINIMUMS ARE PORT-ONLY NOW. They came off the chart
    # after UNDERTOW_PULLBACK.md measured them: the setups they remove are not
    # systematically worse, and both shipped at 0. The port still applies them
    # under PIN_PULL only, which is the branch these two patterns hold.
    ("pbMinAge — bars the pullback must have run",
     r"pbAge >= p\.pbMinAge"),
    ("pbMinDepth — fraction of the impulse given back",
     r"pbDepth >= p\.pbMinDepth"),
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

    WHY = ("the only two legitimate sites are the RESET branch and the local "
           "anchor. Anywhere the pullback makes a new extreme, the age "
           "restarts and pbMinAge quietly means nothing")
    path, pat, want = ONCE_PINE
    n = len(re.findall(pat, path.read_text()))
    if n != want:
        bad.append((f"pbStartX is assigned {n} times in the pine, "
                    f"expected {want}", WHY))
    path, name, want = ONCE_PORT
    n = _assignments(path, name)
    if n != want:
        bad.append((f"pbStartX is assigned {n} times in the port, "
                    f"expected {want} (the two sites plus the initialiser)",
                    WHY))

    for label, pine_re, port_re in SITES:
        if not re.search(pine_re, pine):
            bad.append((label, f"MISSING FROM THE PINE — /{pine_re}/"))
        if not re.search(port_re, port):
            bad.append((label, f"MISSING FROM THE PORT — /{port_re}/"))

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
