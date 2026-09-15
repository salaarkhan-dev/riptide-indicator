"""Semantic diff: is section 12 of riptide-indicator-v2.pine a faithful port?

The static checker proves the Pine is well-formed. It cannot prove the port
says the same thing as the script it came from. This does, mechanically:

  * pull every conditional and every assignment out of both sources
  * rename the original's identifiers to the port's
  * compare the two sets

A condition present in one and not the other is a transcription error — a
flipped comparison, a dropped guard, a swapped label style. Those are exactly
the mistakes that survive a compile and show up as wrong lines on a chart.

    python3 deploy/ms-port-check.py <original.pine> <ported.pine>
"""
from __future__ import annotations

import re
import sys

# original identifier -> ported identifier
RENAME = {
    "shortLen": "msShortLen", "len": "msLen",
    "top_crossed": "msTopCrossed", "btm_crossed": "msBtmCrossed",
    "stop_crossed": "msSTopCrossed", "sbtm_crossed": "msSBtmCrossed",
    "topx": "msTopX", "btmx": "msBtmX",
    "stopx": "msSTopX", "sbtmx": "msSBtmX",
    "topy": "msTopY", "btmy": "msBtmY",
    "stopy": "msSTopY", "sbtmy": "msSBtmY",
    "stop": "msSTop", "sbtm": "msSBtm",
    "top": "msTop", "btm": "msBtm",
    "max_x1": "msMaxX", "min_x1": "msMinX",
    "max": "msMax", "min": "msMin",
    "os": "msOs", "n": "bar_index",
    "bullCss": "msBullCss", "bearCss": "msBearCss",
    "idmCss": "msIdmCss", "sweepsCss": "msSweepCss",
    "color.gray": "msIdmCss",          # the original hard-codes it once
    "showChoch": "msShowChoch", "showBos": "msShowBos",
    "showIdm": "msShowIdm", "showSweeps": "msShowSweeps",
}
# Longest first, so "top_crossed" is not eaten by "top".
ORDER = sorted(RENAME, key=len, reverse=True)


def rename(s: str) -> str:
    for k in ORDER:
        s = re.sub(rf"(?<![A-Za-z0-9_.]){re.escape(k)}(?![A-Za-z0-9_])",
                   "\0" + RENAME[k] + "\0", s)
    return s.replace("\0", "")


def norm(s: str) -> str:
    s = s.split("//")[0]
    s = re.sub(r"\s+", " ", s).strip()
    # the port gates every draw on the master switch; that is an addition, not
    # a change of meaning, so it is normalised away before comparing.
    s = s.replace("msShow and ", "")
    return s


# A top-level section banner, e.g.
#   // ═════════════ 13. BIG GRABS (CONTEXT ONLY) ═════════════
# Used as the END of the ported section. This was a hard-coded "13. MARKET
# STRUCTURE" string, which silently stopped bounding anything the moment a
# section with a different name was added after the port — every statement in
# it then came back as a port bug. The bound's PURPOSE was always "stop at the
# next section", so that is what it now says.
BANNER = re.compile(r"^// ═+ *\d+\. ", re.M)


def conditions(path: str, start: str | None, end: str | None = None) -> set[str]:
    txt = open(path).read()
    if start:
        txt = txt.split(start, 1)[1]
    if end:
        txt = txt.split(end, 1)[0]
    elif start:
        m = BANNER.search(txt)
        if m:
            txt = txt[:m.start()]
    out = set()
    for ln in txt.splitlines():
        c = norm(ln)
        if not c:
            continue
        m = re.match(r"^(?:else )?if (.+)$", c)
        if m:
            out.add("IF " + m.group(1))
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*) := (.+)$", c)
        if m:
            out.add(f"SET {m.group(1)} = {m.group(2)}")
    return out


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    orig, port = argv[1], argv[2]
    a = {norm(rename(x)) for x in conditions(orig, "//Swings detection", None)}
    # Scoped to section 12 — up to the next top-level banner, whatever it is
    # called. Section 13 (big grabs) sits after it and is a port of a
    # different script, so comparing it against this one's original would
    # report every one of its statements as a bug.
    b = conditions(port, "12. MARKET STRUCTURE")

    # KNOWN EQUIVALENCES. Each pair is a difference that is a rename or a
    # restructuring, not a change of meaning. Listing them explicitly — rather
    # than normalising them away inside the matcher — keeps every one of them
    # visible and arguable. Anything NOT on this list is a finding.
    PAIRS = [
        ("IF msTop", "IF not na(msTop)",
         "na-as-falsy made explicit"),
        ("IF msBtm", "IF not na(msBtm)",
         "na-as-falsy made explicit"),
        ("IF msOs == 1 and msShowChoch", "IF msOs == 1",
         "the showChoch guard is hoisted one level and the direction nested"),
        ("IF not msSBtmCrossed and msShowIdm",
         "IF msOn and msShowIdm and not msSBtmCrossed",
         "same conjunction, reordered, plus the master switch"),
        ("IF not msSTopCrossed and msShowIdm",
         "IF msOn and msShowIdm and not msSTopCrossed",
         "same conjunction, reordered, plus the master switch"),
        ("SET msOs = high[msLen] > upper ? 0 : low[msLen] < lower ? 1 : msOs[1]",
         "SET sOs = high[msL] > hh ? 0 : low[msL] < ll ? 1 : was",
         "swings() locals renamed; `was` is nz(sOs[1], 0) — the bar-0 guard"),
        ("SET msTopX = msOs == 0 and msOs[1] != 0 ? bar_index[msLen] : msTopX",
         "SET sTopX = sOs == 0 and was != 0 ? bar_index[msL] : sTopX",
         "swings() locals renamed; `was` is the bar-0 guard"),
        ("SET msBtmX = msOs == 1 and msOs[1] != 1 ? bar_index[msLen] : msBtmX",
         "SET sBtmX = sOs == 1 and was != 1 ? bar_index[msL] : sBtmX",
         "swings() locals renamed; `was` is the bar-0 guard"),
    ]
    # DECLARED DEVIATIONS. These are NOT equivalences and must never be moved
    # into PAIRS above, which is for renames and restructurings only. Each one
    # is a real change of meaning, gated behind a toggle whose DEFAULT
    # reproduces the original. They print under their own loud heading so a
    # reader cannot mistake the port for faithful in these places.
    DEVIATIONS = [
        ("IF close > msMax and msSBtmCrossed and msOs == 1",
         "IF close > msMax and (not msBosNeedsIdm or msSBtmCrossed) and msOs == 1",
         "msBosNeedsIdm. ON (default) = the original exactly. OFF drops the "
         "inducement prerequisite and labels every break of the running "
         "extreme. research/MS_BOS_GATE.md measures what the prerequisite "
         "costs: 30 BOS drawn against 83 suppressed."),
        ("IF close < msMin and msSTopCrossed and msOs == 0",
         "IF close < msMin and (not msBosNeedsIdm or msSTopCrossed) and msOs == 0",
         "the bearish half of the same toggle."),
    ]

    # conditions the port gained by construction, not by changing meaning
    IGNORE_NEW = re.compile(r"^(IF msOn|IF barstate|SET msExt|"
                            r"IF msShowChoch$|IF msShowBos$|IF msShowIdm$|"
                            r"IF msShowSweeps$|IF msShow)")
    only_orig = sorted(x for x in a - b)
    only_port = sorted(x for x in b - a if not IGNORE_NEW.match(x))

    print(f"original: {len(a)} statements   port: {len(b)}")
    print(f"shared:   {len(a & b)}\n")

    # Pair against the FULL port set, not the leftovers: a port-side statement
    # may legitimately also appear elsewhere in the port (`IF msOs == 1` does),
    # in which case it never lands in only_port and the pair would be missed.
    matched = []
    for o, p_, why in PAIRS:
        if o in only_orig and p_ in b:
            only_orig.remove(o)
            if p_ in only_port:
                only_port.remove(p_)
            matched.append((o, p_, why))
    if matched:
        print(f"ACCOUNTED FOR — rename or restructure, not meaning "
              f"({len(matched)}):")
        for o, p_, why in matched:
            print(f"   {why}")
            print(f"     was  {o}")
            print(f"     now  {p_}")
        print()
    declared = []
    for o, p_, why in DEVIATIONS:
        if o in only_orig and p_ in b:
            only_orig.remove(o)
            if p_ in only_port:
                only_port.remove(p_)
            declared.append((o, p_, why))
    if declared:
        print(f"DECLARED DEVIATIONS — a real CHANGE OF MEANING, not a rename "
              f"({len(declared)}):")
        for o, p_, why in declared:
            print(f"   {why}")
            print(f"     original {o}")
            print(f"     port     {p_}")
        print("   Each must also be named in the PORT CHANGES block of "
              "section 12.")
        print()
    if only_orig:
        print(f"IN THE ORIGINAL, NOT IN THE PORT  ({len(only_orig)}):")
        for x in only_orig:
            print(f"   {x}")
        print()
    if only_port:
        print(f"IN THE PORT, NOT IN THE ORIGINAL  ({len(only_port)}):")
        for x in only_port:
            print(f"   {x}")
        print()
    if not only_orig and not only_port:
        if declared:
            print(f"EVERY CONDITION AND ASSIGNMENT MATCHES, apart from the "
                  f"{len(declared)} declared deviation(s) above.")
        else:
            print("EVERY CONDITION AND ASSIGNMENT MATCHES.")
        return 0
    print("Each line above is either a real port bug or a deliberate change "
          "that needs to be named in the file's PORT CHANGES block.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
