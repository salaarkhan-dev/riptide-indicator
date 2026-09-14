"""Telegram and /stats rendering for LIT forward research.

LANGUAGE RULE, enforced here rather than left to good intentions. Nothing in
this module may say "edge", "profitable", "validated", "proven", "high
confidence", or "take this trade". The historical family is CLOSED and the
forward experiment has concluded nothing. `check_language()` is exercised by
the test suite so a future edit cannot quietly reintroduce any of it.

The production strategy's vocabulary is also off-limits: Grade A / Grade B /
CONFIRMED / EARLY belong to Riptide's validated signals, and reusing them here
would make a research observation look like one of those at a glance.
"""

from __future__ import annotations

BANNED = (
    "lit edge", "profitable", "validated", "proven", "high confidence",
    "take this trade", "guaranteed", "grade a", "grade b", "confirmed",
    "early", "buy now", "sell now",
)


def check_language(text: str) -> list[str]:
    """Return every banned phrase present. Empty means the text is acceptable."""
    low = text.lower()
    return [w for w in BANNED if w in low]


def _px(v: float) -> str:
    if v is None:
        return "-"
    return f"{v:,.8g}"


def alert_text(s) -> str:
    """The research alert. Deliberately plain, and it says what it is twice."""
    side = "LONG" if s.direction > 0 else "SHORT"
    tf = s.timeframe.replace("Min", "") + "m" if s.timeframe.startswith("Min") \
        else s.timeframe
    return (
        "🧪 <b>LIT RESEARCH</b>\n"
        "\n"
        f"<b>{s.symbol}</b> · {tf} · {side}\n"
        "\n"
        "IDM taken\n"
        f"BOS: {_px(s.bos_price)}\n"
        f"Entry: {_px(s.entry_price)}\n"
        f"Initial SL: {_px(s.initial_stop)}\n"
        f"Active Price: {_px(s.active_price)}\n"
        "\n"
        f"Model: {s.strategy_version}\n"
        "Exit research: T6 Pivot vs Control\n"
        "\n"
        "<i>RESEARCH ONLY — an observation being recorded, not a Riptide "
        "trade signal. The historical LIT family is closed; this experiment "
        "has concluded nothing.</i>"
    )


def stats_block(summary: dict) -> str:
    """The /stats section. Reports numbers and a state, never a verdict.

    There is no code path that prints a winner badge: `status` comes from
    forward.summary() and can only be COLLECTING or EVALUABLE until a human
    closes the experiment at a pre-registered checkpoint.
    """
    d = summary
    if not d.get("start"):
        return ("🧪 <b>LIT FORWARD V1</b>\n\nNot activated. "
                "Collection is off by default.")
    nxt = d.get("next_checkpoint")
    lines = [
        "🧪 <b>LIT FORWARD V1</b>",
        "",
        f"Resolved setups: {d['setups']}",
        f"Pending: {d['pending']}",
        f"Independent bets: {d['bets']}",
        "",
        "T6 Pivot:",
        f"  {d['t6_per_bet']:+.3f} R/bet",
        "",
        "Control (BOS target):",
        f"  {d['control_per_bet']:+.3f} R/bet",
        "",
        "Paired delta (primary):",
        f"  {d['paired_delta']:+.3f} ± {d['paired_se']:.3f} R/bet",
        f"  paired z: {d['paired_z']:.2f}",
        "",
        "Status:",
        f"  {d['status']}",
    ]
    if nxt is not None:
        lines.append(f"  next checkpoint at {nxt} bets — no conclusion yet")
    else:
        lines.append("  checkpoint reached — awaiting a human read against "
                     "PREREG_lit_forward_v1.md")
    lines += ["", f"<i>{d['version']} · rules {d['rules_hash']}</i>"]
    return "\n".join(lines)
