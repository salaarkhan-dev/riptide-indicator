#!/usr/bin/env python3
"""Assert every Pine input default equals the matching Cfg field.

The chart and the bot are two implementations of one strategy, and they drift
silently: nothing errors when the indicator draws an entry the alert would
never have sent. That drift is invisible until you compare a chart against a
Telegram message and find different prices on the same candle, which is
precisely how the "Look for entry zones from" mismatch was found — the bot ran
"mss", the Pine still shipped "Grab candle".

Only settings that exist on both sides are listed. Pine-only inputs (colours,
what to draw, session boxes) and Cfg-only fields (the tracker, anything the
reference indicator has no notion of) are deliberately absent rather than
faked into a pair.

early_max_bars used to be on that Cfg-only list because the Pine had no early
path at all. It has one now — the low-opacity zone drawn before the shift — so
the window is shared and is checked here. A chart drawing early zones on a
wider window than the bot alerts on is the same silent drift as the
"fvg_scan_from" mismatch this file was written for.

    python deploy/check-parity.py        # exit 1 on any mismatch
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from riptide.config import Cfg, TREND_INTERVAL             # noqa: E402

PINE = Path(__file__).resolve().parent.parent / "riptide-indicator.pine"

# Pine input name -> Cfg field name.
NUMERIC = {
    "usePivotLiq": "use_pivot",
    "useDailyLiq": "use_daily",
    "useWeeklyLiq": "use_weekly",
    "pivotLeft": "pivot_left",
    "pivotRight": "pivot_right",
    "atrLength": "atr_len",
    "liquidityToleranceATR": "tol_atr",
    "minPivotsForLiquidity": "min_pivots",
    "minFvgSizeATR": "min_fvg_atr",
    "maxFvgSizeATR": "max_fvg_atr",
    "maxRiskATR": "max_risk_atr",
    "slBufferATR": "sl_buffer_atr",
    "beArmR": "be_arm_r",
    "beLockR": "be_lock_r",
    "maxBarsAfterGrab": "max_bars_after_grab",
    "mssCooldownBars": "mss_cooldown_bars",
    "maxBarsAfterMss": "max_bars_after_mss",
    "earlyMaxBars": "early_max_bars",
    "earlyMaxRiskATR": "early_max_risk_atr",
}

# Pine input name -> (Cfg field, {Pine option string: Cfg value}).
CHOICE = {
    "fvgScanFrom": ("fvg_scan_from",
                    {"Grab candle": "grab", "MSS candle only": "mss"}),
    "entryMode": ("entry_mode",
                  {"Proximal": "proximal", "Mid": "mid", "Distal": "distal"}),
    "mssMode": ("mss_close", {"close": True, "wick": False}),
}


def strip_code(line: str) -> str:
    """Line with string literals and trailing comments removed, so bracket
    counting is not fooled by punctuation inside a tooltip."""
    out, i, in_str = [], 0, False
    while i < len(line):
        ch = line[i]
        if in_str:
            if ch == "\\":
                i += 2
                continue
            if ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            i += 1
            continue
        if ch == "/" and i + 1 < len(line) and line[i + 1] == "/":
            break
        out.append(ch)
        i += 1
    return "".join(out)


def check_brackets(src: str) -> list[str]:
    """Every bracket balanced, and no top-level statement left hanging.

    Pine reports an unclosed call as CE10015 on the line where the NEXT
    statement starts, which points at innocent code and hides a missing ')'
    several lines up. This finds it directly: a new top-level assignment can
    only begin at depth zero.
    """
    problems, depth, opened_at = [], 0, None
    for n, raw in enumerate(src.split("\n"), 1):
        code = strip_code(raw)
        if depth > 0 and re.match(r"^[A-Za-z_]\w*\s*=[^=]", code):
            problems.append(f"line {n}: statement starts while {depth} "
                            f"bracket(s) opened on line {opened_at} are still "
                            f"unclosed — likely a missing ')' above")
            depth = 0
        for ch in code:
            if ch in "([":
                if depth == 0:
                    opened_at = n
                depth += 1
            elif ch in ")]":
                depth -= 1
                if depth < 0:
                    problems.append(f"line {n}: unmatched closing bracket")
                    depth = 0
    if depth:
        problems.append(f"end of file: {depth} bracket(s) never closed "
                        f"(opened on line {opened_at})")
    return problems


# Series built-ins a local may not shadow once the file reads them. Type and
# namespace names (color, label, line, math, ta) are NOT here: those are
# legitimate type keywords and `color col = ...` is ordinary Pine.
#
# The trap this catches is that shadowing stays LEGAL until something reads the
# built-in, so adding one `open[n]` anywhere breaks a local named `open`
# written months earlier. That is exactly how CE10190 arrived in this file.
PINE_SERIES = {
    "open", "high", "low", "close", "volume", "time", "time_close",
    "hl2", "hlc3", "ohlc4", "hlcc4", "bar_index", "last_bar_index",
    "dayofmonth", "dayofweek", "hour", "minute", "month", "second",
    "weekofyear", "year",
}

DECL = re.compile(
    r"^\s+(?:(?:var|varip)\s+)?"
    r"(?:(?:bool|int|float|string|color|line|label|box|table|array|matrix)\s+)?"
    r"([A-Za-z_]\w*)\s*:?=(?!=)")


def check_shadowing(src: str) -> list[str]:
    """Locals shadowing a series built-in the file also reads.

    Only lines at bracket depth zero are declarations; anything deeper is a
    named argument inside a multi-line call, where `color = ...` is normal.
    """
    used = {n for n in PINE_SERIES if re.search(rf"\b{n}\s*\[", src)}
    problems, depth = [], 0
    for n, raw in enumerate(src.split("\n"), 1):
        code = strip_code(raw)
        if depth == 0:
            m = DECL.match(code)
            if m and m.group(1) in used:
                problems.append(f"line {n}: local '{m.group(1)}' shadows a Pine "
                                f"series built-in the file reads — CE10190")
        depth = max(0, depth + code.count("(") + code.count("[")
                    - code.count(")") - code.count("]"))
    return problems


def pine_default(src: str, name: str) -> str | None:
    m = re.search(rf'^{name}\s*=\s*input\.\w+\(\s*("[^"]*"|[^,]+?)\s*,', src, re.M)
    return m.group(1).strip() if m else None


def main() -> int:
    src = PINE.read_text()
    cfg = Cfg()
    problems = []

    for pine, field in NUMERIC.items():
        raw = pine_default(src, pine)
        if raw is None:
            problems.append(f"{pine}: no input found in the Pine")
            continue
        got = {"true": True, "false": False}.get(raw)
        if got is None:
            try:
                got = float(raw) if "." in raw else int(raw)
            except ValueError:
                problems.append(f"{pine}: default {raw!r} is not a literal")
                continue
        want = getattr(cfg, field)
        if float(got) != float(want):
            problems.append(f"{pine} = {raw}   but   Cfg.{field} = {want!r}")

    for pine, (field, options) in CHOICE.items():
        raw = pine_default(src, pine)
        if raw is None or not raw.startswith('"'):
            problems.append(f"{pine}: no string default found in the Pine")
            continue
        choice = raw.strip('"')
        if choice not in options:
            problems.append(f"{pine}: default {choice!r} is not a known option")
            continue
        want = getattr(cfg, field)
        if options[choice] != want:
            problems.append(f"{pine} = {choice!r} -> {options[choice]!r}   "
                            f"but   Cfg.{field} = {want!r}")

    # Not a Cfg field, so it gets its own comparison rather than being faked
    # into the NUMERIC table.
    TF = {'"D"': "Day1", '"240"': "Hour4", '"480"': "Hour8", '"60"': "Min60"}
    raw = pine_default(src, "trendFilterTf")
    if raw is None:
        problems.append("trendFilterTf: no input found in the Pine")
    elif TF.get(raw) != TREND_INTERVAL:
        problems.append(f"trendFilterTf = {raw} -> {TF.get(raw)!r}   but   "
                        f"TREND_INTERVAL = {TREND_INTERVAL!r}")

    shadow = check_shadowing(src)
    if shadow:
        print(f"PINE SYNTAX: {len(shadow)} shadowed built-in(s)\n")
        for s_ in shadow:
            print("  " + s_)
        return 1

    bracket = check_brackets(src)
    if bracket:
        print(f"PINE SYNTAX: {len(bracket)} bracket problem(s)\n")
        for b in bracket:
            print("  " + b)
        print("\nTradingView reports these as CE10015 on the wrong line.")
        return 1

    n = len(NUMERIC) + len(CHOICE) + 1
    if problems:
        print(f"PINE / ENGINE PARITY: {len(problems)} of {n} settings disagree\n")
        for p in problems:
            print("  " + p)
        print("\nThe chart would show a different trade than the bot alerts.")
        return 1
    print(f"pine: brackets balanced, no shadowed built-ins · "
          f"parity: all {n} shared settings agree")
    return 0


if __name__ == "__main__":
    sys.exit(main())
