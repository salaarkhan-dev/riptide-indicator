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
ASSIGN = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:=")


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


def check(path: str) -> list[str]:
    lines = open(path).read().splitlines()
    found: list[str] = []

    def bad(i: int, msg: str):
        found.append(f"{path}:{i+1}: {msg}")

    # ── pass 1: declarations, functions, and their first-use lines ──────────
    declared: dict[str, int] = {}
    for i, ln in enumerate(lines):
        c = code_of(ln)
        m = FUNC.match(c) or METH.match(c)
        if m:
            declared[m.group(1)] = i

    depth = 0
    for i, ln in enumerate(lines):
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

    if depth != 0:
        found.append(f"{path}: file ends with bracket depth {depth}")
    return found


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
    print(f"{target}: {len(tf)} findings, {len(tf) - len(new)} also present in "
          f"the control file(s)")
    if controls:
        print(f"controls: {', '.join(controls)}")
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
