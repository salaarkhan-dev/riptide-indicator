"""Add Pine v6's `active =` to every input that depends on another input.

`active` takes an "input bool", so it may be any expression over inputs and
constants — but the input it names must be DECLARED EARLIER in the file, and
this script asserts that rather than trusting the table below.

Nothing else changes: no name, no type, no default, no group.
deploy/pine-input-audit.py --diff proves it.
"""
import pathlib
import re
import sys

P = pathlib.Path("riptide-indicator-v2.pine")
src = P.read_text()

# dependent input -> the "input bool" expression that keeps it enabled.
DEPS = {}
for expr, names in {
    # 2. Trading sessions — a session's name and window are dead when it is off
    "sess1On": "sess1Name sess1Spec",
    "sess2On": "sess2Name sess2Spec",
    "sess3On": "sess3Name sess3Spec",

    # 6. Show — liquidity and raids
    "showPivots": "hideDeadPivots",
    "showGrab": "showGrabTag",
    "showRaidDot": "raidDotKeep",

    # 7. Show — entry zones and blocks
    "showFVGs": "showFvgMidline fvgExtendBars fadeUsedFvg extendFVG fvgFill",
    "showAllFvg": "allFvgMinATR allFvgKeep allFvgFill allFvgRemove "
                  "allFvgOverlap",
    "showOB or showBreaker": "blockLevel blockBars blockWidth",
    "showOB": "obCol",
    "showBreaker": "bbCol",
    "extendFVG": "fvgMaxExtendBars",

    # 8. Early signal — earlyMaxBars and earlyMaxRiskATR are parity-locked and
    # deliberately left alone; see SKIPPED below.
    "showEarly": "earlyFade earlyKeep",

    # 9. Show — day / week / session levels
    "showPrevDayHL or showPrevWeekHL": "staticExtendBars",

    # 10. Colours — the ICT-only diamonds exist under one preset only
    'markStyle == "Riptide + ICT"': "ictBullCol ictBearCol",

    # 11. Higher-timeframe context. trendWidth and the fill belong to the
    # SuperTrend plot; the EMA plot is a separate plot() with linewidth 1.
    'trendMode == "SuperTrend"': "trendWidth showTrendFill",
    'trendMode == "EMA"': "emaLen",
    "showTrendTag": "trendTagSize",
    "trendFilter": "trendFilterTf trendFilterFac trendFilterLen",
    "poiOn": "chartMinGrade",

    # 13. Performance stats
    "trackOutcomes": "fillModel tradeExpiryBars showStats showFillMarker "
                     "showTargets maxTrades",

    # 14. Advanced tuning
    "invalidatePending": "pendingInvalidateATR",

    # 15. Engine and debug
    "debugMode": "debugJoins",

    # 16/17. Market structure and its liquidity lines
    "msShow": "msLen msShortLen msKeepN msShowChoch msShowBos msShowIdm "
              "msShowSweeps msShowSwings msBullCss msBearCss msIdmCss "
              "msSweepCss msLiq",
    "msShow and msLiq": "msLiqSH msLiqSL msLiqDH msLiqDL msLiqSPP msLiqDPP "
                        "msLiqSLLS msLiqDLLS",
}.items():
    for n in names.split():
        assert n not in DEPS, n
        DEPS[n] = expr

# Left alone on purpose. Each reason is a fact about this file, checked.
SKIPPED = """
beLockR earlyMaxBars earlyMaxRiskATR poiMaxAgeDays
    parity-locked by deploy/check-parity.py. Their value must track
    riptide.conf whether or not the chart happens to draw the thing they
    govern, so greying them out would say something untrue about the one
    guarantee this panel carries.
liqCol
    looks like `not liqDirCol`, and is not: lines 1805/1816/1827 colour the
    pool BOXES with it unconditionally.
setupExtendBars setupLevelKeep
    not only the entry/stop lines — the early zones (1424) and the target
    lines (1531) use them too.
showTrendTag
    its own tooltip says it keeps working when the trend line is Off. That is
    deliberate, so it must not be gated on trendMode.
sessTz
    the session windows feed both useSessionLiq and showSessionBox, and
    showSessionBox is declared after it.
"""

# ── where each input is declared, so a `group =` can be attributed to one ────
decl = re.compile(r"(?m)^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*input(?:\.[a-z_]+)?\s*\(")
starts = [(m.start(), m.group(1)) for m in decl.finditer(src)]
order = {n: i for i, (_, n) in enumerate(starts)}


def owning(pos: int) -> str | None:
    best = None
    for s, n in starts:
        if s <= pos:
            best = n
        else:
            break
    return best


# ── the ordering rule, asserted rather than assumed ─────────────────────────
bad = []
for dep, expr in DEPS.items():
    if dep not in order:
        bad.append(f"{dep}: not an input in this file")
        continue
    # string literals are values, not identifiers
    bare = re.sub(r'"[^"]*"', " ", expr)
    for ref in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", bare):
        if ref in ("and", "or", "not"):
            continue
        if ref not in order:
            bad.append(f"{dep}: `{ref}` is not an input")
        elif order[ref] >= order[dep]:
            bad.append(f"{dep}: `{ref}` is declared later — Pine reads "
                       f"top-down, so this would not compile")
if bad:
    print("ORDERING / NAME ERRORS:")
    for b in bad:
        print("  " + b)
    sys.exit(1)

# ── insert, once per input, after its `group = ` argument ───────────────────
out, done, last = [], {}, 0
for m in re.finditer(r"group\s*=\s*(g[A-Za-z]+)", src):
    name = owning(m.start())
    expr = DEPS.get(name)
    if not expr or name in done:
        continue
    out.append(src[last:m.end()])
    out.append(f", active = {expr}")
    done[name] = expr
    last = m.end()
out.append(src[last:])
P.write_text("".join(out))

print(f"{len(done)} inputs gated")
missing = sorted(set(DEPS) - set(done))
if missing:
    print(f"NOT GATED ({len(missing)}): {', '.join(missing)}")
    sys.exit(1)
by = {}
for n, e in done.items():
    by.setdefault(e, []).append(n)
for e in sorted(by, key=lambda k: -len(by[k])):
    print(f"  active = {e:<32} {len(by[e]):>2}  {' '.join(sorted(by[e]))}")
print(SKIPPED)
