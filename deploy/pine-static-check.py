"""Static checks for Pine v6 sources. No compiler exists in CI or in the
agent environment, so these encode the mistakes that have actually cost a
compile round-trip on this project, each one learned from a real error:

    CE10088  a function may MUTATE an object but may not ASSIGN a global
    CE10150  a reserved word used as an identifier ("to" is the one that bit)
             comma-separated declarations or statements
             a continuation line landing on a multiple-of-4 indent
             a function used before it is declared
             unbalanced brackets on a logical line

Run it against a KNOWN-GOOD file as well as the one under test. A finding that
appears in both is a false positive of this checker; a finding unique to the
new file is a real regression.

    python3 deploy/pine-static-check.py riptide-lit-v3.pine riptide-lit-v2.pine
"""
from __future__ import annotations

import re
import sys

# Pine v6 keywords that cannot be identifiers.
RESERVED = {
    "if", "else", "for", "to", "by", "while", "switch", "and", "or", "not",
    "var", "varip", "true", "false", "na", "series", "simple", "const",
    "input", "import", "export", "method", "type", "enum", "continue",
    "break", "return", "in", "int", "float", "bool", "string", "color",
    "line", "label", "box", "table", "array", "matrix", "map", "linefill",
}

DECL = re.compile(
    r"^\s*(?:var\s+|varip\s+)?"
    r"(?:int|float|bool|string|color|line|label|box|table|linefill)\s+"
    r"([A-Za-z_][A-Za-z0-9_]*)\s*=")
FUNC = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*\([^)]*\)\s*=>")
METH = re.compile(r"^method\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")
# A Pine v6 user-defined type. Its body is a block of indented FIELD
# declarations — `float focus = na` — which are neither continuation lines nor
# top-level variables. Both of those rules fired on the first UDT written in
# this project, so the block is skipped whole.
TYPE = re.compile(r"^type\s+([A-Za-z_][A-Za-z0-9_]*)\s*$")
ASSIGN = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:=")

# A TOP-LEVEL variable declaration: at column 0, so not inside a function or an
# if-block. Pine needs these before first use exactly as it needs functions
# before first use, and this checker only had the function half of that rule
# until a compile error found the gap — a `bool ccpBarOk = ...` declared in one
# section and read by a block inserted above it.
TOPVAR = re.compile(
    r"^(?:var\s+|varip\s+)?"
    r"(?:(?:int|float|bool|string|color|line|label|box|table|linefill"
    r"|array<[^>]+>)\s+)?"
    r"([A-Za-z_][A-Za-z0-9_]*)\s*=(?!=|>)")


def strip_strings(s: str) -> str:
    """Blank out string literals so their contents never match a rule."""
    out, i, n = [], 0, len(s)
    while i < n:
        ch = s[i]
        if ch in "\"'":
            q, i = ch, i + 1
            out.append(" ")
            while i < n:
                if s[i] == "\\":
                    i += 2
                    out.append("  ")
                    continue
                if s[i] == q:
                    break
                out.append(" ")
                i += 1
            out.append(" ")
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def code_of(line: str) -> str:
    c = strip_strings(line)
    return c.split("//")[0].rstrip()


def outer(s: str) -> str:
    """Only what sits OUTSIDE brackets. A call's named arguments look exactly
    like a comma-separated declaration otherwise — `input.int(1, group = g)`
    would be flagged on every input line in the file."""
    out, d = [], 0
    for ch in s:
        if ch in "([":
            d += 1
        elif ch in ")]":
            d = max(0, d - 1)
        elif d == 0:
            out.append(ch)
    return "".join(out)


def type_body(lines: list[str]) -> set[int]:
    """Line numbers inside a `type` block, fields included.

    A UDT's fields look like declarations at indent 4 and like continuation
    lines to the indent rule, and they are neither. Returning the set once is
    simpler than teaching both rules about types separately, and it means a new
    rule cannot rediscover the same false positive.
    """
    out: set[int] = set()
    inside = False
    for i, ln in enumerate(lines):
        c = code_of(ln)
        if TYPE.match(c):
            inside = True
            out.add(i)
            continue
        if inside:
            if not c.strip():
                out.add(i)
                continue
            if c[0].isspace():
                out.add(i)
                continue
            inside = False
    return out


def check(path: str) -> list[str]:
    lines = open(path).read().splitlines()
    in_type = type_body(lines)
    found: list[str] = []

    def bad(i: int, msg: str):
        found.append(f"{path}:{i+1}: {msg}")

    # ── pass 1: declarations, functions, and their first-use lines ──────────
    declared: dict[str, int] = {}
    topvar: dict[str, int] = {}
    for i, ln in enumerate(lines):
        if i in in_type:
            continue
        c = code_of(ln)
        m = FUNC.match(c) or METH.match(c)
        if m:
            declared[m.group(1)] = i
            continue
        # Only column 0 counts. An indented `x = ...` is local to a function or
        # a block and says nothing about what is visible at the top level.
        if c and not c[0].isspace():
            m = TOPVAR.match(c)
            if m and m.group(1) not in declared:
                topvar.setdefault(m.group(1), i)

    depth = 0
    for i, ln in enumerate(lines):
        if i in in_type:
            continue
        c = code_of(ln)
        if not c.strip():
            continue

        # reserved words as names
        for rx in (DECL, ASSIGN):
            m = rx.match(c)
            if m and m.group(1) in RESERVED:
                bad(i, f"reserved word used as an identifier: {m.group(1)!r}")
        m = FUNC.match(c) or METH.match(c)
        if m and m.group(1) in RESERVED:
            bad(i, f"reserved word used as a function name: {m.group(1)!r}")

        # An array read guarded only by a boolean operator. RE10045 was hit
        # live on `size() == 0 or get(size() - 1)`: Pine does not reliably
        # short-circuit, so the read stays reachable on an empty array. The
        # size check has to gate the read through CONTROL FLOW, not `and`/`or`.
        if re.search(r"size\(\) *(?:== *0 *or|> *0 *and|!= *0 *and)"
                     r"[^\n]*(?:\.get\(|\.first\(\)|\.last\(\))", c):
            bad(i, "array read guarded only by and/or — Pine may not "
                   "short-circuit; gate it with an if/else instead")

        # comma-separated declarations, and comma-joined statements
        if DECL.match(c) and re.search(
                r",\s*(?:(?:int|float|bool|string|color)\s+)?"
                r"[A-Za-z_][A-Za-z0-9_]*\s*(?::?=)", outer(c)):
            bad(i, "comma-separated declaration — split onto separate lines")
        if ASSIGN.match(c) and re.search(
                r",\s*[A-Za-z_][A-Za-z0-9_.]*\s*:=", outer(c)):
            bad(i, "comma-separated assignment — split onto separate lines")

        # continuation lines: a line that continues the previous one must not
        # sit on a multiple-of-4 indent, or Pine reads it as a new block.
        prev = code_of(lines[i - 1]) if i else ""
        opens = depth > 0
        # A line that ENDS in a string literal is complete, whatever the
        # stripped copy looks like. `x = c ? f(...) : "no shape"` strips down
        # to something ending in `:` and every following statement was then
        # reported as a mis-indented continuation. The trailing-operator test
        # needs strings stripped (a string ending in "+" is not an operator);
        # this one needs the raw line, so it gets it.
        prev_raw = (lines[i - 1].split("//")[0].rstrip() if i else "")
        ends_str = prev_raw.endswith(("\"", "'"))
        cont = opens or (not ends_str and prev.rstrip().endswith(
            ("+", "-", "*", "/", "?", ":", ",", "and", "or", "(")))
        # Indentation is a property of the RAW line. Measuring it on the
        # string-stripped copy was wrong: strip_strings blanks a literal's
        # contents, so a continuation beginning with a string of spaces —
        # `         "  (pin needs <= " + ...` — lost its quote and its padding
        # to lstrip and reported an indent of 28 for a line indented 9. Every
        # such line was a false positive.
        raw = lines[i]
        ind = len(raw) - len(raw.lstrip())
        if cont and c.strip() and ind % 4 == 0 and ind > 0 and not prev.rstrip().endswith(("=>",)):
            bad(i, f"continuation line at indent {ind} (multiple of 4) — "
                   f"Pine will read it as a new statement")

        depth += c.count("(") - c.count(")")
        depth += c.count("[") - c.count("]")
        if depth < 0:
            bad(i, "unbalanced closing bracket")
            depth = 0

        # function used before declaration
        for name, dl in declared.items():
            if dl > i and re.search(rf"(?<![A-Za-z0-9_.]){name}\s*\(", c):
                bad(i, f"{name}() used at line {i+1} but declared at {dl+1}")

        # top-level variable used before declaration, the same rule
        for name, dl in topvar.items():
            if dl > i and re.search(rf"(?<![A-Za-z0-9_.]){name}(?![A-Za-z0-9_(])", c):
                bad(i, f"{name} read at line {i+1} but declared at {dl+1}")

    if depth != 0:
        found.append(f"{path}: file ends with bracket depth {depth}")
    return found


# FINDINGS THAT ARE REAL, IN A FILE THAT MAY NOT BE TOUCHED.
#
# `indicators/riptide/pine/riptide-indicator.pine` is the PRODUCTION indicator
# and is frozen by tests/test_control_frozen.py; changing it needs the owner's
# say-so, and a static-check finding is not that. These two are recorded here
# rather than silenced, so the finding stays visible and the decision stays
# open. They surfaced the day preflight started making every Pine file a
# target instead of only the first, so they are OLD, not new.
#
#   :721  `d3t.size() == 0 or d3t.get(d3t.size() - 1) != dTm`
#   :744  `zTm.size() > 0 and (dTm - zTm.get(0)) > poiMaxAgeDays * 86400000`
#
# BOTH ARE THE SAME HAZARD. Pine does not guarantee short-circuit evaluation
# of `and`/`or`, so the guard may not stop the array read, and an empty array
# read raises at runtime. 721 is the safer of the two: `size() == 0 or ...`
# reads `size() - 1`, which is -1 on an empty array. 744 reads `get(0)`.
#
# Whether either has ever fired is unknown and that is the point -- it would
# fire as a chart error, not as a wrong number, so nobody would see it in a
# backtest. The fix is a nested `if`, it is three lines, and it needs
# authorisation on a frozen file.
WAIVED = [
    ("indicators/riptide/pine/riptide-indicator.pine", ":721:"),
    ("indicators/riptide/pine/riptide-indicator.pine", ":744:"),
]


def waived(finding: str) -> bool:
    return any(path in finding and tag in finding for path, tag in WAIVED)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    target, *controls = argv[1:]
    tf = check(target)
    ctrl: set[str] = set()
    for c in controls:
        ctrl |= {f.split(": ", 1)[1] for f in check(c)}

    new = [f for f in tf if f.split(": ", 1)[1] not in ctrl]
    held = [f for f in new if waived(f)]
    new = [f for f in new if not waived(f)]
    print(f"{target}: {len(tf)} findings, {len(tf) - len(new) - len(held)} "
          f"also present in the control file(s)"
          + (f", {len(held)} WAIVED" if held else ""))
    if controls:
        print(f"controls: {', '.join(controls)}")
    for f in held:
        print(f"  WAIVED (frozen file, see WAIVED in this script)\n    {f}")
    print()
    if not new:
        print("NO FINDINGS UNIQUE TO THE TARGET.")
        return 0
    print(f"{len(new)} finding(s) unique to {target}:")
    for f in new:
        print(f"  {f}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
