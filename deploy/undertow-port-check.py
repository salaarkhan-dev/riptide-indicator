"""Do the Pine and the Python port agree on their INPUTS?

    python3 deploy/undertow-port-check.py

WHAT THIS IS, AND WHAT IT IS NOT. It is not a logic parity check. Sections 5, 6
and 7 of riptide-undertow.pine have no v2 counterpart, so there is no second
copy to diff them against, and a statement-level comparison between Pine and
Python across a state machine that size would need an exception table longer
than the check. That guard is behavioural instead and lives in
indicators/undertow/tests/test_undertow_port.py.

What this IS: every `input.*` in the Pine must have a field of the same name in
the port's `P`, with the SAME DEFAULT, and every `options = [...]` list must
match the string constants the port compares against.

That sounds small. It is the drift that actually happens. The port and the Pine
are edited on different days for different reasons, and the failure is silent
in the worst possible way: a study reports a number for `retraceMax = 70` while
the chart the number is supposed to describe is running 50. Nothing crashes,
nothing looks wrong, and the conclusion is about a strategy nobody is trading.

The string options matter for the same reason and worse. Both sides compare
these by VALUE -- Pine does `stopSrc == "Pullback extreme"` and the port does
`p.stopSrc == S_PULL`. Change the wording of a dropdown in the Pine and the
port's comparison silently stops matching, every branch falls through to its
else, and the machine still runs.

DELIBERATELY NOT COMPARED: the display group (showZones, showUnfilled,
showStruct, keepN, the colours, the two debug toggles). Those drive drawing,
and the port draws nothing. They are listed in DISPLAY_ONLY below by name, so
adding to that list shows up in a diff rather than quietly widening the hole.
"""
from __future__ import annotations

import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PINE = ROOT / "indicators/undertow/pine/riptide-undertow.pine"
PORT = ROOT / "indicators/undertow/port/undertow.py"

# Pine inputs that only ever reach a drawing call. The port has no analogue and
# must not grow one.
DISPLAY_ONLY = {"showZones", "showUnfilled", "showStruct", "keepN",
                "overlapMode",
                "colLong", "colShort", "colLine", "dbgOn", "dbgRejects"}

# input.color / input.string defaults that are Pine expressions rather than
# literals are not comparable as values; none of the non-display inputs are.
INPUT = re.compile(
    r"^\s*(\w+)\s*=\s*input\.(int|float|bool|string|color)\s*\(\s*(.+)$")


def pine_inputs():
    """(name, kind, default, options) for every input in the Pine.

    Reads the FIRST argument by scanning to the first top-level comma, because
    a default can be a string containing a comma and a naive split eats it.
    """
    out = {}
    src = PINE.read_text().splitlines()
    for n, line in enumerate(src):
        m = INPUT.match(line)
        if not m:
            continue
        name, kind, rest = m.group(1), m.group(2), m.group(3)
        # the call can wrap; join until the parens balance
        buf, depth, k = rest, 0, n
        while True:
            depth = buf.count("(") - buf.count(")")
            if depth < 0 or k >= len(src) - 1:
                break
            k += 1
            buf += " " + src[k].strip()
        default = _first_arg(buf)
        opts = None
        mo = re.search(r"options\s*=\s*\[([^\]]*)\]", buf)
        if mo:
            opts = [s.strip().strip('"') for s in mo.group(1).split(",")]
        out[name] = (kind, default, opts)
    return out


def _first_arg(buf: str) -> str:
    depth = 0
    quote = False
    for i, ch in enumerate(buf):
        if ch == '"':
            quote = not quote
        elif not quote:
            if ch in "([":
                depth += 1
            elif ch in ")]":
                if depth == 0:
                    return buf[:i].strip()
                depth -= 1
            elif ch == "," and depth == 0:
                return buf[:i].strip()
    return buf.strip()


def port_defaults():
    """P's field defaults, plus the module-level string constants, by AST so a
    comment or a reordering cannot fool it."""
    tree = ast.parse(PORT.read_text())
    consts, fields = {}, {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    consts[t.id] = node.value.value
        if isinstance(node, ast.ClassDef) and node.name == "P":
            for st in node.body:
                if isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name):
                    v = st.value
                    if isinstance(v, ast.Constant):
                        fields[st.target.id] = v.value
                    elif isinstance(v, ast.Name):
                        fields[st.target.id] = consts.get(v.id, f"<{v.id}>")
    return fields, consts


def as_py(kind: str, default: str):
    """The Pine literal as the Python value it should equal."""
    if kind == "bool":
        return default == "true"
    if kind == "int":
        return int(default)
    if kind == "float":
        return float(default)
    if kind == "string":
        return default.strip('"')
    return None


def main() -> int:
    pin = pine_inputs()
    fields, consts = port_defaults()
    bad, checked = [], 0

    for name, (kind, default, opts) in sorted(pin.items()):
        if name in DISPLAY_ONLY or kind == "color":
            continue
        checked += 1
        if name not in fields:
            bad.append((name, f"the Pine has this input; P has no field. "
                              f"Pine default {default}"))
            continue
        want = as_py(kind, default)
        got = fields[name]
        if want is None:
            continue
        if isinstance(want, float) or isinstance(got, float):
            same = abs(float(want) - float(got)) < 1e-9
        else:
            same = want == got
        if not same:
            bad.append((name, f"DEFAULT DIFFERS — pine {want!r}, port {got!r}"))
        if opts:
            missing = [o for o in opts if o not in consts.values()]
            if missing:
                bad.append((name, "OPTION STRING NOT IN THE PORT: "
                            + ", ".join(repr(m) for m in missing)
                            + " — both sides compare these by value, so a "
                              "reworded dropdown makes every branch fall "
                              "through in silence"))

    # The other direction: a field in P with no Pine input behind it means
    # either a deliberate port-only feature or an input the Pine has LOST.
    # Fields the Pine deliberately does not have. The first group is the three
    # things Pine cannot do (a scale-invariant swing, an HTF bias without
    # breaking the v2 parity check, and a cost model). The second is the
    # ablation switches, which are not settings anyone should trade -- they
    # exist so a study can remove one gate at a time. Adding to this set is how
    # the check gets quietly widened, so each entry is here in a diff, with a
    # reason above it.
    # The swing source is NO LONGER port-only: `range` became the default and
    # the chart has to be able to show what the studies measured, so all four
    # of its inputs now exist in the Pine and are compared like any other.
    # THE THREE RETIRED BIAS SOURCES. EMA cross, Slope and Range midpoint were
    # on the chart to be measured; UNDERTOW_BIAS_SOURCE.md measured them, none
    # beat the baseline, and they cost fifteen inputs in group 1 to offer
    # settings the page warns against. They came OFF THE CHART and stayed in
    # the port, because undertow_bias.py (S2, S4, S5) and undertow_slope.py
    # (A1, A2) still run them and those pages must keep reproducing. Supertrend
    # is still on the chart, so stAtrLen/stMult are NOT in here.
    RETIRED = {"emaFast", "emaSlow", "donLen",
               "slopeUnit", "slopeLen", "slopeMin",
               "slopeHours", "slopeMinPerHr",
               # Supertrend and MTF EMA align went the same way, and with them
               # `matureBars`, which only ever meant anything for a source with
               # no BOS to count. The CHART NOW OFFERS STRUCTURE AND NOTHING
               # ELSE: five measured alternatives, none of which beat it, were
               # costing seven inputs in group 1. They stay in the port because
               # undertow_bias, undertow_slope and undertow_mtf have to keep
               # reproducing their pages.
               "biasSrc", "stAtrLen", "stMult", "matureBars",
               "mtfFast", "mtfSlow", "mtfMult",
               # THE v2 RULE CORRECTIONS, SPEC.md section 8. They are the
               # strategy's author saying v1 detected the wrong thing, so they
               # go to the port first and to the chart only once measured --
               # putting them on the chart now would repeat exactly the habit
               # that gave group 1 twenty inputs for four settings nothing
               # supported. All three default to v1 meanwhile.
               "confirmOrder", "needBos", "pinNewest"}
    # htfUnit/htfHours join htfMult for the same reason the port's docstring
    # gives: an honest HTF bias in Pine needs the whole structure slab inside a
    # function so request.security can evaluate it on higher-timeframe bars,
    # and that refactor would break undertow-ms-check.py's anchor against v2.
    # If the gate ever clears its prereg, that refactor is the price of putting
    # it on the chart.
    PORT_ONLY = {"htfMult", "htfUnit", "htfHours", "feeFrac",
                 "useFamily", "useColour", "bkMode"} | RETIRED
    for name in sorted(fields):
        if name not in pin and name not in PORT_ONLY:
            bad.append((name, "P has this field and the Pine has no such "
                              "input — was an input removed from the Pine?"))

    print(f"{checked} shared inputs compared "
          f"({len(DISPLAY_ONLY)} display-only inputs skipped by name, "
          f"{len(PORT_ONLY)} port-only fields allowed)")
    if not bad:
        print("\nTHE PINE AND THE PORT AGREE ON EVERY INPUT.")
        print("Defaults and dropdown strings only — the LOGIC is held by")
        print("indicators/undertow/tests/test_undertow_port.py.")
        return 0
    print(f"\n{len(bad)} DISAGREEMENT(S):")
    for name, why in bad:
        print(f"    {name}\n        {why}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
