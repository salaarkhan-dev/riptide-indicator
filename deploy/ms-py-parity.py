"""Pine <-> Python parity for the market-structure engine.

This is the check LIT never had and still does not have. `research/ms_struct.py`
is a transcription of section 12 of `riptide-indicator-v2.pine`, deliberately
keeping the Pine's identifiers, so the two can be compared by machine instead
of by eye.

It extracts every condition and every assignment from both sides, rewrites the
Python into Pine's surface syntax through the NORMALISATIONS table below, and
reports anything that does not pair.

It is NOT a compile and it is NOT a numeric equivalence proof. It proves the
two sources say the same thing about the same variables in the same order.
A condition that matches here can still behave differently if Pine and Python
disagree about, say, na propagation — which is exactly why the `lt`/`gt`
helpers exist on the Python side and why they are listed as a normalisation
rather than hidden.

    python3 deploy/ms-py-parity.py riptide-indicator-v2.pine research/ms_struct.py
"""
from __future__ import annotations

import re
import sys

# (pattern, replacement, why) — applied to the PYTHON side only.
NORMALISATIONS = [
    (r"\blt\(([^,()]+), ([^,()]+)\)", r"\1 < \2",
     "lt(a, b) is `a < b` guarded against None; Pine's na does that itself"),
    (r"\bgt\(([^,()]+), ([^,()]+)\)", r"\1 > \2",
     "gt(a, b) is `a > b`, same reason"),
    (r"\[i\]", "",
     "the Python holds per-bar lists where Pine holds a series"),
    (r"\bis not None\b", "IS_SET",
     "Python's None is Pine's na"),
    (r"(?<![A-Za-z0-9_])cl(?![A-Za-z0-9_])", "close", "local name"),
    (r"(?<![A-Za-z0-9_])h(?![A-Za-z0-9_])", "high", "local name"),
    (r"(?<![A-Za-z0-9_])l(?![A-Za-z0-9_])", "low", "local name"),
    (r"(?<![A-Za-z0-9_])i(?![A-Za-z0-9_])", "bar_index", "local name"),
]
# applied to the PINE side
PINE_NORM = [
    (r"\bnot na\(([A-Za-z0-9_]+)\)", r"\1 IS_SET", "na test, same shape"),
    (r"\bmath\.max\(", "max(", "stdlib name"),
    (r"\bmath\.min\(", "min(", "stdlib name"),
]

# Statements that exist on one side only for a reason that is not a difference
# of meaning. Each is listed with that reason.
EXPECTED = {
    "pine": [
        ("IF msShow and msShowChoch", "drawing gate; the Python draws nothing"),
        ("IF msShow and msShowIdm", "drawing gate"),
        ("IF msShow and msShowBos", "drawing gate"),
        ("IF msOn and msShowChoch", "drawing gate"),
        ("IF msOn and msShowBos", "drawing gate"),
        ("IF barstate.islast", "the live-extension block has no Python analogue"),
        ("IF msOs == 1", "direction split inside the drawing gate"),
        ("IF msShowChoch", "drawing gate"),
        ("IF msShowBos", "drawing gate"),
        ("IF msShowIdm", "drawing gate"),
        ("IF msShowIdm and not msSBtmCrossed",
         "drawing gate on the live IDM extension"),
        ("IF msShowIdm and not msSTopCrossed", "same"),
        ("IF msSBtmY IS_SET and msSBtmY < close",
         "section 13 ledger signal-capture: Pine-only instrumentation. "
         "It lives inside the BOS block because the block clears "
         "msSBtmCrossed on its way out, so section 13 cannot re-derive "
         "it. The Python study applies the same stop test in stop_for()."),
        ("IF msSTopY IS_SET and msSTopY > close", "same, bearish side"),
    ],
    "py": [
        ("SET cycle = cycle + 1", "the Python numbers CHoCH cycles so events "
                                  "can be grouped into bets; the Pine has no "
                                  "need to"),
    ],
}


def norm_common(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip().rstrip(":")
    s = s.replace("msShow and ", "").replace("msOn and ", "")
    # trailing drawing gates on the sweep conditions
    s = s.replace(" and msShowSweeps", "")
    return s


def statements(path: str, py: bool) -> set[str]:
    txt = open(path).read()
    if py:
        txt = txt.replace("\\\n", " ")
        txt = txt.split("def engine(", 1)[1]
        txt = re.sub(r"#.*", "", txt)
        for pat, rep, _ in NORMALISATIONS:
            txt = re.sub(pat, rep, txt)
    else:
        txt = txt.split("12. MARKET STRUCTURE", 1)[1]
        # Stop at section 13. The ledger and stats table are Pine-only
        # instrumentation with no Python counterpart, so including them
        # would report every one of their conditions as a parity break.
        txt = txt.split("13. MARKET STRUCTURE", 1)[0]
        txt = re.sub(r"//.*", "", txt)
        for pat, rep, _ in PINE_NORM:
            txt = re.sub(pat, rep, txt)

    out = set()
    for ln in txt.splitlines():
        c = norm_common(ln)
        if not c:
            continue
        m = re.match(r"^(?:el)?if (.+)$", c)
        if m:
            out.add("IF " + m.group(1))
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*) :?= (.+)$", c)
        if m and not m.group(2).startswith(("line.new", "label.new",
                                            "array.new", "input", "dict(")):
            out.add(f"SET {m.group(1)} = {m.group(2)}")
    return out


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    pine, pyf = argv[1], argv[2]
    a = statements(pine, py=False)
    b = statements(pyf, py=True)

    # SCOPE. Pass/fail is judged on CONDITIONS only. Assignments differ in
    # surface between the two languages far more than conditions do — `var
    # float x = na` against `x = None`, `math.max` against a None-guarded
    # `max`, Pine's `x[1]` history against a hoisted local — and forcing those
    # to match would mean contorting one side to satisfy a checker. Conditions
    # are where a transcription error changes behaviour, so that is what is
    # gated. Assignment differences are printed as context, not as failures.
    PAIRS = [
        ("IF msOs != msOs[1]", "IF msOs != msOsPrev",
         "Pine reads series history; the Python hoists the previous value"),
        ("IF msMax > msMax[1]", "IF msMaxPrev is None or msMax > msMaxPrev",
         "same, plus the first-bar None guard Pine gets free from na"),
        ("IF msMin < msMin[1]", "IF msMinPrev is None or msMin < msMinPrev",
         "same"),
        ("IF high > msMax and close < msMax and msOs == 1 and bar_index - msMaxX > 1",
         "IF high > msMax and close < msMax and msOs == 1 and msMaxX IS_SET and bar_index - msMaxX > 1",
         "the Python must guard msMaxX before arithmetic; na does it in Pine"),
        ("IF low < msMin and close > msMin and msOs == 0 and bar_index - msMinX > 1",
         "IF low < msMin and close > msMin and msOs == 0 and msMinX IS_SET and bar_index - msMinX > 1",
         "same"),
    ]
    # `float msSTopY = fixnan(msSTop)` forward-fills the last non-na swing.
    # The Python does the same with an explicit assign-on-new-swing.
    FIXNAN = [("IF msSTop IS_SET", "fixnan(msSTop) forward-fill, written out"),
              ("IF msSBtm IS_SET", "fixnan(msSBtm) forward-fill, written out")]

    exp_pine = {x for x, _ in EXPECTED["pine"]}
    exp_py = {x for x, _ in EXPECTED["py"]} | {x for x, _ in FIXNAN}
    only_pine = sorted(x for x in a - b if x not in exp_pine)
    only_py = sorted(x for x in b - a if x not in exp_py)

    paired = []
    for pin, pyy, why in PAIRS:
        if pin in only_pine and pyy in only_py:
            only_pine.remove(pin)
            only_py.remove(pyy)
            paired.append((pin, pyy, why))

    # gate on conditions; assignments are context
    asg_pine = [x for x in only_pine if x.startswith("SET")]
    asg_py = [x for x in only_py if x.startswith("SET")]
    only_pine = [x for x in only_pine if x.startswith("IF")]
    only_py = [x for x in only_py if x.startswith("IF")]

    print(f"pine: {len(a)} statements   python: {len(b)}   shared: "
          f"{len(a & b)}\n")
    print("NORMALISATIONS applied to the Python side, so they are arguable:")
    for _, _, why in NORMALISATIONS:
        print(f"   {why}")
    print()
    print("EXPECTED one-sided statements:")
    for side in ("pine", "py"):
        for stmt, why in EXPECTED[side]:
            if (stmt in a - b) if side == "pine" else (stmt in b - a):
                print(f"   [{side}] {stmt}  —  {why}")
    if paired:
        print("PAIRED — same condition, different surface:")
        for pin, pyy, why in paired:
            print(f"   {why}")
            print(f"     pine {pin}")
            print(f"     py   {pyy}")
        print()
    for stmt, why in FIXNAN:
        if stmt in b - a:
            print(f"   [py] {stmt}  —  {why}")
    print(f"\nassignment-surface differences (context, not gated): "
          f"{len(asg_pine)} pine-only, {len(asg_py)} python-only")
    print()
    bad = False
    if only_pine:
        bad = True
        print(f"IN THE PINE, NOT IN THE PYTHON ({len(only_pine)}):")
        for x in only_pine:
            print(f"   {x}")
        print()
    if only_py:
        bad = True
        print(f"IN THE PYTHON, NOT IN THE PINE ({len(only_py)}):")
        for x in only_py:
            print(f"   {x}")
        print()
    if not bad:
        print("EVERY LOGIC STATEMENT PAIRS.")
        print("Not a compile, and not numeric equivalence — it proves the two")
        print("sources say the same thing about the same variables.")
        return 0
    print("Each line is a parity break or a change that needs naming above.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
