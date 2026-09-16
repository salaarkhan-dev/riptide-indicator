"""Inventory every `input.*` in a Pine file, and say what each one is worth.

Written because "there are too many inputs" is an impression until it is
counted. This counts:

  * every input, its type, default, group, inline and whether it has a tooltip
  * how many times the variable is READ anywhere else in the file — an input
    read zero times is dead, and one read once may be doing very little
  * which inputs are LOCKED by deploy/check-parity.py, because those are
    matched to riptide.conf by VARIABLE NAME and renaming one silently breaks
    the bot-to-chart guarantee

    python3 deploy/pine-input-audit.py \
        indicators/riptide_ms/pine/riptide-indicator-v2.pine
    python3 deploy/pine-input-audit.py --diff BEFORE.pine AFTER.pine
"""
from __future__ import annotations

import re
import sys
from collections import Counter, defaultdict

INPUT = re.compile(
    r"^(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*input"
    r"(?:\.(?P<kind>[a-z_]+))?\s*\(")


def locked_names(path="deploy/check-parity.py") -> set[str]:
    try:
        s = open(path).read()
    except OSError:
        return set()
    out: set[str] = set()
    for blk in ("NUMERIC", "CHOICE", "BOOLEAN", "BOOL"):
        m = re.search(rf"^{blk}\s*[:=].*?\n\}}", s, re.S | re.M)
        if m:
            out |= set(re.findall(r'^\s*"([A-Za-z_][A-Za-z0-9_]*)"\s*:',
                                  m.group(0), re.M))
    return out


def logical_lines(path: str):
    """Pine wraps an input over several lines. Rejoin by bracket depth so each
    declaration is one string, and keep the line number it started on."""
    raw = open(path).read().splitlines()
    buf, start, depth = "", 0, 0
    for i, ln in enumerate(raw):
        code = ln.split("//")[0] if not ln.lstrip().startswith("//") else ""
        if not buf:
            start = i
        buf = (buf + " " + ln.strip()) if buf else ln
        # depth over the RAW line so strings containing brackets still balance
        # closely enough for this purpose
        depth += ln.count("(") - ln.count(")")
        if depth <= 0:
            yield start + 1, buf
            buf, depth = "", 0
        del code


def field(decl: str, key: str) -> str | None:
    m = re.search(rf"\b{key}\s*=\s*([A-Za-z_][A-Za-z0-9_]*|'[^']*'|\"[^\"]*\")",
                  decl)
    return m.group(1).strip("'\"") if m else None


def title_of(decl: str) -> str:
    """The title is a POSITIONAL string — the second one for a string input,
    the first otherwise.

    It used to be "the second quoted string anywhere in the declaration", which
    printed the whole tooltip as the title of every bool input that has one:
    `input.bool(false, "Grabs", tooltip = "...")` has two quoted strings and
    the second is the tooltip. Named arguments are now skipped, so only real
    positional strings are considered.
    """
    body = decl[decl.index("(", decl.index("input")) + 1:]
    args, buf, depth = [], "", 0
    for ch in body:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            if depth == 0:
                break
            depth -= 1
        if ch == "," and depth == 0:
            args.append(buf)
            buf = ""
            continue
        buf += ch
    args.append(buf)
    pos = [a.strip() for a in args
           if not re.match(r"^\s*[A-Za-z_][A-Za-z0-9_]*\s*=[^=]", a)]
    strs = [a[1:-1] for a in pos
            if len(a) > 1 and a[0] in "\"'" and a[-1] == a[0]]
    return strs[1] if len(strs) > 1 else (strs[0] if strs else "")


def inventory(path: str) -> dict:
    """name -> the things that MUST NOT change when inputs are reorganised.

    Reordering, regrouping, retitling and adding tooltips are presentation.
    Changing a name, a type or a DEFAULT is behaviour, and for the 23
    parity-locked inputs a changed default silently desynchronises the chart
    from riptide.conf. This is what the --diff mode compares.
    """
    out = {}
    for lineno, decl in logical_lines(path):
        m = INPUT.match(decl.strip())
        if not m:
            continue
        body = decl[decl.index("(", decl.index("input")) + 1:]
        first = body.split(",")[0].strip()
        out[m.group("name")] = (m.group("kind") or "(untyped)", first)
    return out


def diff(a_path: str, b_path: str) -> int:
    a, b = inventory(a_path), inventory(b_path)
    print(f"  before: {len(a)} inputs   after: {len(b)} inputs\n")
    bad = []
    for n in sorted(set(a) - set(b)):
        bad.append(f"REMOVED  {n}")
    for n in sorted(set(b) - set(a)):
        bad.append(f"ADDED    {n}   ({b[n][0]}, default {b[n][1]})")
    for n in sorted(set(a) & set(b)):
        if a[n][0] != b[n][0]:
            bad.append(f"TYPE     {n}: {a[n][0]} -> {b[n][0]}")
        if a[n][1] != b[n][1]:
            bad.append(f"DEFAULT  {n}: {a[n][1]} -> {b[n][1]}")
    if not bad:
        print("  EVERY INPUT KEEPS ITS NAME, TYPE AND DEFAULT.")
        print("  The change is presentation only.")
        return 0
    print(f"  {len(bad)} behavioural difference(s):")
    for x in bad:
        print(f"    {x}")
    return 1


def main(argv):
    if len(argv) >= 4 and argv[1] == "--diff":
        return diff(argv[2], argv[3])
    if len(argv) < 2:
        print(__doc__)
        return 2
    path = argv[1]
    src = open(path).read()
    lock = locked_names()

    rows = []
    for lineno, decl in logical_lines(path):
        m = INPUT.match(decl.strip())
        if not m:
            continue
        name = m.group("name")
        kind = m.group("kind") or "(untyped)"
        grp = field(decl, "group") or "(no group)"
        rows.append(dict(line=lineno, name=name, kind=kind, group=grp,
                         inline=field(decl, "inline"),
                         tip="tooltip" in decl,
                         title=title_of(decl)))

    # how often is each input READ elsewhere?
    for r in rows:
        n = len(re.findall(rf"(?<![A-Za-z0-9_.]){re.escape(r['name'])}"
                           rf"(?![A-Za-z0-9_])", src))
        r["uses"] = n - 1              # minus the declaration itself

    print("=" * 92)
    print(f"  INPUT AUDIT — {path}")
    print("=" * 92)
    print(f"  {len(rows)} inputs")
    print(f"  {sum(1 for r in rows if r['tip'])} have a tooltip, "
          f"{sum(1 for r in rows if not r['tip'])} do not")
    print(f"  {sum(1 for r in rows if r['name'] in lock)} are LOCKED by "
          f"check-parity (renaming one breaks chart-to-bot parity)")
    print()

    by = defaultdict(list)
    for r in rows:
        by[r["group"]].append(r)

    print(f"  {'group':<44}{'inputs':>8}{'locked':>8}{'no tip':>8}{'dead':>7}")
    print("  " + "-" * 73)
    for g, v in sorted(by.items(), key=lambda kv: -len(kv[1])):
        print(f"  {g[:43]:<44}{len(v):>8}"
              f"{sum(1 for r in v if r['name'] in lock):>8}"
              f"{sum(1 for r in v if not r['tip']):>8}"
              f"{sum(1 for r in v if r['uses'] == 0):>7}")
    print("  " + "-" * 73)
    print(f"  {'TOTAL':<44}{len(rows):>8}"
          f"{sum(1 for r in rows if r['name'] in lock):>8}"
          f"{sum(1 for r in rows if not r['tip']):>8}"
          f"{sum(1 for r in rows if r['uses'] == 0):>7}")

    dead = [r for r in rows if r["uses"] == 0]
    if dead:
        print(f"\n  DEAD — declared and never read ({len(dead)}):")
        for r in dead:
            print(f"    {path}:{r['line']}  {r['name']}  "
                  f"[{r['group'][:30]}]  \"{r['title'][:34]}\"")

    thin = [r for r in rows if r["uses"] == 1]
    if thin:
        print(f"\n  READ EXACTLY ONCE ({len(thin)}) — candidates for folding "
              f"into a preset or a constant:")
        for r in thin:
            print(f"    {r['name']:<24} [{r['group'][:32]:<34}] "
                  f"\"{r['title'][:30]}\"")

    notip = [r for r in rows if not r["tip"] and r["name"] not in lock]
    if notip:
        print(f"\n  NO TOOLTIP and not parity-locked ({len(notip)}):")
        print("    " + ", ".join(r["name"] for r in notip))

    print(f"\n  {'':<4}groups: {len(by)}   "
          f"largest: {max(len(v) for v in by.values())} inputs")
    kinds = Counter(r["kind"] for r in rows)
    print(f"      by type: " + ", ".join(f"{k} {v}" for k, v in
                                         kinds.most_common()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
