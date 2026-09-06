#!/usr/bin/env python3
"""Assert every Pine input default equals the matching Cfg field.

The chart and the bot are two implementations of one strategy, and they drift
silently: nothing errors when the indicator draws an entry the alert would
never have sent. That drift is invisible until you compare a chart against a
Telegram message and find different prices on the same candle, which is
precisely how the "Look for entry zones from" mismatch was found — the bot ran
"mss", the Pine still shipped "Grab candle".

Only settings that exist on both sides are listed. Pine-only inputs (colours,
what to draw, session boxes) and Cfg-only fields (early_max_bars, the tracker,
anything the reference indicator has no notion of) are deliberately absent
rather than faked into a pair.

    python deploy/check-parity.py        # exit 1 on any mismatch
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from riptide.config import Cfg                             # noqa: E402

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
}

# Pine input name -> (Cfg field, {Pine option string: Cfg value}).
CHOICE = {
    "fvgScanFrom": ("fvg_scan_from",
                    {"Grab candle": "grab", "MSS candle only": "mss"}),
    "entryMode": ("entry_mode",
                  {"Proximal": "proximal", "Mid": "mid", "Distal": "distal"}),
    "mssMode": ("mss_close", {"close": True, "wick": False}),
}


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

    n = len(NUMERIC) + len(CHOICE)
    if problems:
        print(f"PINE / ENGINE PARITY: {len(problems)} of {n} settings disagree\n")
        for p in problems:
            print("  " + p)
        print("\nThe chart would show a different trade than the bot alerts.")
        return 1
    print(f"pine / engine parity: all {n} shared settings agree")
    return 0


if __name__ == "__main__":
    sys.exit(main())
