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
# Pine's own capitalised type-ish names, which are not user-defined types.
BUILTIN_TYPES = {"Inf", "Nan"}
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
    # USER-DEFINED TYPES, which this checker did not know about until a `type`
    # block was DELETED WHOLE by an edit meant to remove two functions above it
    # and the file still passed every check here. TradingView caught it:
    # "Cand is not a valid type keyword". A type is declared before use exactly
    # as a function is, and a type that is not declared at all is not a subtle
    # failure -- it is the compile error a green preflight promised would not
    # happen.
    udt: dict[str, int] = {}
    # Its own pass: `type_body()` marks the type's LINES, and depending on how
    # it counts, the `type X` header can be among them -- reading udt inside
    # the loop that skips those lines found nothing and called every use
    # undeclared.
    for i, ln in enumerate(lines):
        mt = TYPE.match(code_of(ln))
        if mt:
            udt[mt.group(1)] = i
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

        # A TYPE USED BEFORE — OR WITHOUT — ITS DECLARATION. The three ways a
        # UDT name appears: `array<T>`, `T.new(`, and `T name = ...` as the
        # type of a declaration.
        for m2 in re.finditer(
                r"array<([A-Z]\w*)>|(?<![\w.])([A-Z]\w*)\.new\s*\(|"
                r"^\s*(?:var\s+|varip\s+)?([A-Z]\w*)\s+\w+\s*=", c):
            name = m2.group(1) or m2.group(2) or m2.group(3)
            if name in BUILTIN_TYPES:
                continue
            if name not in udt:
                bad(i, f"type {name} is used at line {i+1} and never declared "
                       f"-- TradingView will say it is not a valid type "
                       f"keyword")
            elif udt[name] > i:
                bad(i, f"type {name} used at line {i+1} but declared at "
                       f"{udt[name]+1}")

    if depth != 0:
        found.append(f"{path}: file ends with bracket depth {depth}")
    # ── a table.cell past the declared height ───────────────────────────────
    # A RUNTIME ERROR, WHICH IN PINE KILLS THE WHOLE INDICATOR. Same class as
    # reading a series by a runtime index without max_bars_back, which this
    # repository shipped once and the user found on TradingView.
    #
    # It was nearly shipped a second time: three rows were added to Undertow's
    # panel, taking the highest index to 21 against a table declared with 17
    # rows, and every other check here passed.
    #
    # THE HELPER HAS TO BE RESOLVED TO ITS TABLE. Rows are written through
    # `row(r, ...) => table.cell(pnl, 0, r, ...)`, so the indices live at the
    # CALL sites and the table name lives in the DEFINITION. A first version
    # skipped that step and applied one table's row numbers to another, which
    # reported a one-row badge as overflowing at index 21.
    #
    # Text-level, so only LITERAL indices are seen. A row index built from a
    # variable is invisible here and that is stated rather than papered over.
    src = "\n".join(lines)
    for m in re.finditer(r"table\.new\([^,]+,\s*\d+\s*,\s*(\d+)", src):
        height = int(m.group(1))
        decl = src[:m.start()].count("\n")
        nm = re.search(r"(\w+)\s*=\s*$", src[:m.start()].rstrip()[:m.start()])
        tname = None
        head = lines[decl]
        mn = re.search(r"(?:var\s+)?table\s+(\w+)\s*=", head)
        if mn:
            tname = mn.group(1)
        if not tname:
            continue
        used = [int(x.group(1)) for x in
                re.finditer(rf"table\.cell\(\s*{tname}\s*,\s*\d+\s*,\s*(\d+)",
                            src)]
        used += [int(x.group(1)) for x in
                 re.finditer(rf"\b{tname}\.cell\(\s*\d+\s*,\s*(\d+)", src)]
        # helpers whose BODY writes this table, and whose first argument is the
        # row: collect their call sites' literal first arguments.
        for fm in re.finditer(r"^(\w+)\(int (\w+)[^)]*\)\s*=>", src, re.M):
            fn, arg = fm.group(1), fm.group(2)
            body = src[fm.end():]
            body = body[:body.find("\n\n") if "\n\n" in body else len(body)]
            if re.search(rf"table\.cell\(\s*{tname}\s*,\s*\d+\s*,\s*{arg}\b",
                         body):
                used += [int(x.group(1)) for x in
                         re.finditer(rf"^\s*{fn}\((\d+),", src, re.M)]
        if used and max(used) >= height:
            bad(decl, f"table {tname} is declared with {height} rows and row "
                      f"index {max(used)} is written -- table.cell past the "
                      f"declared height is a RUNTIME error and kills the "
                      f"whole indicator")

    return found


# NOTHING IS WAIVED, and the list is kept because it earned its place once.
#
# When preflight started making every Pine file a target instead of only the
# first, two old findings surfaced in the PRODUCTION indicator -- :721 and
# :744, both an array read guarded only by `and`/`or`, which Pine does not
# guarantee to short-circuit. They were waived here, with the analysis written
# out rather than silenced, because that file is frozen and a static-check
# finding is not authorisation to edit it. The owner then gave it, both are
# fixed, and the entries are gone.
#
# THE SHAPE OF THAT IS THE POINT. A waiver records a decision somebody has to
# make; it is not a way to make a check quiet. An entry added here says who has
# to decide and what happens if they decide nothing.
WAIVED: list[tuple[str, str]] = []


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
