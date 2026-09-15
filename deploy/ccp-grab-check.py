"""Is riptide-ccp.pine's grab engine still the same code as v2's section 13?

The CCP bench carries a VERBATIM copy of the grab detector so that anything it
learns transfers back to riptide-indicator-v2.pine without a translation step.
A copy is only worth that while it stays a copy, and two files drift the moment
somebody fixes a bug in one of them.

So this compares them line for line, after stripping the section headers (which
say different things on purpose) and blank lines. Any difference is either a
fix that belongs in both, or a deliberate divergence that has to be declared
here with a reason.

    python3 deploy/ccp-grab-check.py

The CCP merge logic itself is NOT compared — it exists only in the bench, and
that is the point of having a bench. Only the shared engine is gated.
"""
from __future__ import annotations

import re
import sys

V2 = "riptide-indicator-v2.pine"
BENCH = "riptide-ccp.pine"

# The engine starts at the first instance construction and runs to the end of
# its section. Anchored on code, not on a line number or a banner's wording.
START = "var GrabSet gsNarrow = GrabSet.new("
# In the bench the engine is followed by the CCP design stub; in v2 it is the
# end of the file.
BENCH_END = "5. COMBINED CANDLE PATTERNS"

# Blocks shared beyond the engine proper, each with the marker that ends it in
# each file — they sit next to different things, so the end marker differs
# while the block between them must not.
#   (name, start, end in v2, end in the bench, include the end line)
SHARED = [
    ("the BigGrab / GrabSet types",
     "// One untaken swing waiting to be run",
     "// Pine functions can mutate",
     "// ═════════════════════════ 3. HELPERS",
     False),
    ("the label-crowding helper",
     "// ── label size and label crowding",
     "    dupe ? na : x",
     "    dupe ? na : x",
     True),
]

# Differences that are deliberate. Each entry is a run of lines present ONLY
# in the bench, lifted out before the line-for-line compare so the rest still
# lines up. Keep this list to one or two entries: a copy needing many
# exceptions is not a copy and should become a single source of truth instead.
DECLARED: list[tuple[list[str], str]] = [
    ([
        "// THE ONE LINE THIS FILE ADDS to v2's copy of the detector. Hands the",
        "// grab's two ends to section 5. Declared in deploy/ccp-grab-check.py.",
        "ccpOnGrab(fromBar, isHigh, s.col)",
     ],
     "the bench hands each grab's swing bar and grab bar to section 5, which "
     "looks for a candle shape at both ends. v2 has no section 5 and nothing "
     "to hand them to, so the same line would be dead code there. It reads no "
     "engine value, changes no condition and draws nothing."),
]


def slab(path: str, start: str, end: str, inclusive_end: bool = False) -> list[str]:
    lines = open(path).read().splitlines()
    try:
        i = next(k for k, l in enumerate(lines) if l.startswith(start)
                 or l.strip().startswith(start))
    except StopIteration:
        print(f"  !! {path}: could not find the start marker {start!r}")
        sys.exit(2)
    j = len(lines)
    for k in range(i + 1, len(lines)):
        if lines[k].startswith(end) or end in lines[k]:
            j = k + 1 if inclusive_end else k
            break
    return [l.rstrip() for l in lines[i:j] if l.strip()]


def compare(name: str, a: list[str], b: list[str]) -> list[str]:
    out = []
    if len(a) != len(b):
        out.append(f"{name}: {len(a)} code lines in {V2}, {len(b)} in {BENCH}")
    for n, (x, y) in enumerate(zip(a, b), 1):
        if x != y:
            out.append(f"{name}: line {n} differs\n"
                       f"     v2    {x.strip()}\n"
                       f"     bench {y.strip()}")
    return out


def main() -> int:
    findings: list[str] = []

    eng_v2 = slab(V2, START, "\uffff")          # to end of file
    eng_b = slab(BENCH, START, BENCH_END)

    # Lift the declared bench-only lines out before comparing, so the rest is
    # still a line-for-line match rather than an offset diff that buries the
    # real differences under a hundred shifted ones.
    for lines_, why in DECLARED:
        want = [x.strip() for x in lines_]
        have = [y.strip() for y in eng_b]
        missing = [x for x in want if x not in have]
        if missing:
            findings.append("DECLARED but absent from the bench: "
                            + "; ".join(missing))
        eng_b = [y for y in eng_b if y.strip() not in want]
        print(f"DECLARED DIVERGENCE, {len(lines_)} line(s) — {why}\n")

    findings += compare("engine", eng_v2, eng_b)

    for name, start, end_v2, end_b, inc in SHARED:
        # The SAME inclusivity on both sides. Passing it on one only was the
        # first thing this checker got wrong, and it reported a one-line
        # difference that did not exist.
        findings += compare(name,
                            slab(V2, start, end_v2, inclusive_end=inc),
                            slab(BENCH, start, end_b, inclusive_end=inc))

    print(f"{V2}: {len(eng_v2)} engine lines")
    print(f"{BENCH}: {len(eng_b)} engine lines\n")
    if not findings:
        print("THE GRAB ENGINE IS IDENTICAL IN BOTH FILES.")
        print("Not a compile and not a proof either works — it proves that a")
        print("fix applied to one of them was applied to the other.")
        return 0
    print(f"{len(findings)} difference(s):")
    for f in findings:
        print(f"  {f}")
    print("\nEach is a fix that belongs in both files, or a divergence that")
    print("needs declaring in DECLARED above with a reason.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
