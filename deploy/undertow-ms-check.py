"""Is Undertow's market-structure engine still the same engine as v2's?

    python3 deploy/undertow-ms-check.py

WHY. Pine cannot import, so `riptide-undertow.pine` carries a copy of section 12
of `riptide-indicator-v2.pine`. Two copies drift the moment somebody fixes a bug
in one of them, and the symptom is not a crash — it is two charts quietly
disagreeing about what a CHoCH is, which would make every Undertow setup
describe a trend that v2 does not see.

WHY NOT A LINE-FOR-LINE COMPARE, the way deploy/ccp-grab-check.py works. That
copy is verbatim; this one is not. Undertow drops the drawing entirely and
hoists each condition into a named bool so the same test can also be counted:

    v2          if close > msMax and (not msBosNeedsIdm or msSBtmCrossed) ...
    undertow    bool msBosUp = close > msMax and (not msBosNeedsIdm or ...) ...

Identical logic, different text. So this compares the LOGIC: every condition and
every assignment in the engine slab of each file, normalised.

COUNTS, NOT A SET, and that distinction was found by testing the check rather
than by reasoning about it. `msSBtmCrossed := false` appears twice in the
engine, once in the CHoCH reset and once after a BOS. Deleting one of them is a
real behaviour change and a set comparison reports nothing, because the other
occurrence still covers the value. A multiset catches it.

BOTH DIRECTIONS. A statement in Undertow and not v2 means Undertow invented
something; a statement in v2 and not Undertow means a fix landed in v2 and never
came here. The second is the likelier one, and a one-way check would miss it.

WHAT IS EXCLUDED, and this is the only judgement in the file: anything that only
DRAWS. Undertow draws none of the structure v2 draws, so every `msDraw`, every
`msShow` guard and every line/label mutation would otherwise be reported as a
difference on every run — and a check that always reports something is a check
nobody reads. The filter is by symbol, listed in DRAWING below, so it cannot
quietly swallow a condition: a drawing symbol appearing inside a real engine
test would have to be added to that list by hand, in a diff.
"""
from __future__ import annotations

import collections
import re
import sys

V2 = "indicators/riptide_ms/pine/riptide-indicator-v2.pine"
UT = "indicators/undertow/pine/riptide-undertow.pine"

# The engine slab in each file, anchored on CODE rather than on a banner —
# banners are prose and get reworded.
SLABS = {
    V2: ("[msTop, msTopX, msBtm, msBtmX] = msSwings(msLen)",
         "// ── live extensions"),
    UT: ("[msTop, msTopX, msBtm, msBtmX] = msSwings(msLen)",
         "// ══════════════════════ 4. MINOR STRUCTURE"),
}

# Also compare the swing detector itself, which sits in a different place in
# each file — a helper at the top here, mid-section there.
FUNC = "msSwings(simple int msL) =>"

# Symbols that exist only to draw. See the docstring: this is the one judgement
# in the file, so it is a list of names rather than a pattern, and adding to it
# shows up in a diff.
#
# They appear in two shapes and each needs different handling:
#   a whole STATEMENT that draws          -> drop it, and its indented block
#   a drawing GUARD inside a real test    -> drop that conjunct, keep the test
# v2 writes `if <engine test> and msShow and msShowSweeps`; Undertow writes the
# engine test alone. Dropping the whole line would hide the test on one side
# only, which is exactly the difference this check must not invent.
DRAWING = ("msDraw", "msShow", "line.", "label.", "plot", "Liq.",
           "msLineBuf", "msLabelBuf", "msPrune", "labelSlot", "msKeepN",
           "lblSize", "Css")


def slab(path: str, start: str, end: str) -> list[str]:
    lines = open(path).read().splitlines()
    try:
        i = next(k for k, l in enumerate(lines) if l.strip().startswith(start))
    except StopIteration:
        sys.exit(f"{path}: cannot find the slab start {start!r}")
    try:
        j = next(k for k, l in enumerate(lines[i:], i)
                 if l.strip().startswith(end))
    except StopIteration:
        sys.exit(f"{path}: cannot find the slab end {end!r}")
    return lines[i:j]


def func(path: str) -> list[str]:
    """The msSwings body, wherever it sits in the file."""
    lines = open(path).read().splitlines()
    i = next(k for k, l in enumerate(lines) if l.strip().startswith(FUNC))
    out = [lines[i]]
    for l in lines[i + 1:]:
        if l.strip() and not l.startswith((" ", "\t")):
            break
        out.append(l)
    return out


def draws(text: str) -> bool:
    return any(d in text for d in DRAWING)


def undraw(cond: str) -> str:
    """Strip the drawing guards from a condition, keep the engine test.

    Returns "" when nothing but guards is left, which means the whole line was
    a drawing gate.
    """
    if not draws(cond):
        return cond
    keep = [c for c in cond.split(" and ") if not draws(c)]
    return " and ".join(keep)


def statements(lines: list[str]) -> collections.Counter:
    """Every condition and assignment, normalised to its logic.

    `if X`, `else if X` and `bool name = X` all reduce to X, so hoisting a
    condition into a named bool is not a difference. Declarations of the
    engine's own state keep their name, because `var float msMax = na` losing
    its initial value IS a difference.
    """
    out: list = []
    declared: set = set()
    skip_at = None            # indent of a dropped block, None when not in one
    for raw in lines:
        body = raw.split("//")[0].rstrip()
        if not body.strip():
            continue
        indent = len(body) - len(body.lstrip())
        if skip_at is not None:
            if indent > skip_at:
                continue
            skip_at = None
        s = body.strip()
        if s == "else":
            continue
        m = re.match(r"^bool\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$", s)
        if s.startswith(("if ", "else if ")):
            cond = undraw(s.split(" ", 2)[-1] if s.startswith("else if ")
                          else s[3:])
            if not cond.strip():
                skip_at = indent      # a pure drawing gate: drop its block too
                continue
            s = cond
        elif m:
            declared.add(m.group(1))
            s = m.group(2)
        elif draws(s):
            skip_at = indent          # a drawing call, and anything under it
            continue
        out.append(re.sub(r"\s+", " ", s).strip())
    # `if msBosUp` restates a condition this slab already declared, so counting
    # it would report the hoisting itself as a difference.
    return collections.Counter(s for s in out if s not in declared)


def main() -> int:
    a = statements(slab(V2, *SLABS[V2]) + func(V2))
    b = statements(slab(UT, *SLABS[UT]) + func(UT))
    only_v2 = sorted((a - b).elements())
    only_ut = sorted((b - a).elements())
    print(f"v2       {sum(a.values())} engine statements")
    print(f"undertow {sum(b.values())} engine statements")
    if not only_v2 and not only_ut:
        print("\nTHE TWO ENGINES ARE THE SAME LOGIC.")
        print("Not a compile, and not numeric equivalence — it proves that")
        print("every condition and assignment in one is in the other.")
        return 0
    if only_v2:
        print(f"\nIN v2, MISSING FROM UNDERTOW ({len(only_v2)}):")
        print("  a fix that landed in v2 and never reached the copy?")
        for s in only_v2:
            print(f"    {s}")
    if only_ut:
        print(f"\nIN UNDERTOW, MISSING FROM v2 ({len(only_ut)}):")
        print("  the copy invented something, or v2 lost it")
        for s in only_ut:
            print(f"    {s}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
