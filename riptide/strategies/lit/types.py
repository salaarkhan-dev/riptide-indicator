"""The frozen LIT_FORWARD_V1 definition, and the record it produces.

EVERY VALUE IN `RULES` IS FROZEN. They are copied literally from the Stage C
code and pre-registration, not reconstructed from memory:

    research/studies/lit_stage_c.py   the rule as executed
    PREREG_lit_stage_c.md §3, §4      the rule as registered

Changing any of them is not an edit. It is a new experiment, and it requires a
new `FWD_VERSION` — LIT_FORWARD_V2 — whose results are never pooled with V1's.
`rules_hash()` exists so that a silent change cannot happen: every stored setup
carries the hash of the rules that produced it, and a mismatch is visible.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict, field

FWD_FAMILY = "lit"
FWD_VERSION = "LIT_FORWARD_V1"

# ── the frozen rules ────────────────────────────────────────────────────────
# Sources, so a reader can check each line rather than trust it:
#   entry/stop/with-trend   research/studies/lit_stage_c.py::run_symbol
#   MIN_RR, HORIZON         research/studies/lit_stage_a.py (inherited by C)
#   arms                    research/studies/lit_stage_c.py::ARMS/PRIMARY/CONTROL
#   fees                    research/harness.py FEE_MAKER / FEE_TAKER, applied
#                           by simulate_market's maker/taker split
RULES: dict = {
    "family": FWD_FAMILY,
    "version": FWD_VERSION,
    # structure
    "depth": "MAIN",                 # Internal and Deep publish no setups
    "engine": "research.lit_v3",     # the frozen engine, imported not copied
    # entry
    "entry": "close_of_idm_break_bar",
    "direction": "with_trend_only",  # the locked BOS must lie beyond the entry
    "order_type": "market",          # no limit-fill assumption, no unfilled state
    # stop
    "stop": "prior_confirmed_pullback_pivot",
    "stop_buffer": 0.0,
    "stop_missing": "skip",          # never substituted by another level
    # active price — arms a trail, is NOT a target
    "min_rr": 0.5,
    # exits, both scored on the SAME setup
    "primary_arm": "T6_PIVOT",
    "control_arm": "BOS_TARGET",
    "trail_arm_r": 0.5,              # equals min_rr: the trail arms at Active Price
    # scoring
    "scorer": "research.harness.simulate_market",
    "horizon_bars": 500,
    "same_bar": "stop_before_target",
    "entry_bar_resolves": False,
    "fee_model": "harness.FEE_MAKER=0.010%,FEE_TAKER=0.022%,maker_taker_split",
    # inference
    "unit_of_evidence": "market_event_bet",
    "primary_outcome": "paired_delta_R",
}


def rules_hash() -> str:
    """Stable over the frozen rules, and over nothing else.

    Deliberately NOT hashed over the source file: formatting a comment must not
    invalidate a live experiment, while changing a rule must.
    """
    blob = json.dumps(RULES, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


# ── resolution states ───────────────────────────────────────────────────────
# A setup may only ever move PENDING -> RESOLVED or PENDING -> TIMED_OUT.
# AMBIGUOUS is terminal and is scored as nothing: it leaves the sample rather
# than having a path invented for it.
PENDING = "pending"
RESOLVED = "resolved"
TIMED_OUT = "timed_out"
AMBIGUOUS = "ambiguous"
TERMINAL = (RESOLVED, TIMED_OUT, AMBIGUOUS)


@dataclass
class ForwardSetup:
    """One prospective observation. Identity and hypothesis are IMMUTABLE once
    written; only the outcome fields may transition."""

    # identity
    setup_id: str
    strategy_family: str
    strategy_version: str
    rules_hash: str
    # market
    symbol: str
    timeframe: str
    direction: int                   # +1 long, -1 short
    # times (epoch seconds)
    structure_time: int              # the IDM pivot's own bar
    signal_time: int                 # the IDM-break bar — entry bar
    entry_time: int
    resolution_time: int | None = None
    # structure
    structure_depth: str = "MAIN"
    lit_direction: int = 0
    idm_price: float | None = None
    idm_break_time: int | None = None
    bos_price: float | None = None
    choch_price: float | None = None
    relevant_pivot: float | None = None   # the stop level, before it is a stop
    raid_extreme: float | None = None     # Stage A's stop, recorded not used
    # execution hypothesis
    entry_price: float = 0.0
    initial_stop: float = 0.0
    initial_risk_price: float = 0.0
    initial_risk_pct: float = 0.0
    active_price: float = 0.0
    bos_distance_r: float = 0.0
    # control arm
    control_exit_price: float | None = None
    control_exit_time: int | None = None
    control_exit_reason: str | None = None
    control_r: float | None = None
    # primary arm
    t6_exit_price: float | None = None
    t6_exit_time: int | None = None
    t6_exit_reason: str | None = None
    t6_r: float | None = None
    # THE PRIMARY OUTCOME
    paired_delta_r: float | None = None
    # diagnostics
    mfe_r: float | None = None
    mae_r: float | None = None
    bars_held: int | None = None
    active_reached: bool = False
    bos_reached: bool = False
    choch_reached: bool = False
    # risk guards
    planned_loss_r: float = -1.0
    realized_loss_r: float | None = None
    stop_gap_r: float | None = None
    # event grouping — the unit of inference
    market_event_id: str = ""
    event_size: int = 1
    event_direction: int = 0
    # universe membership AS IT WAS, so no survivorship can be applied later
    universe_rank: int | None = None
    universe_size: int | None = None
    # state
    state: str = PENDING
    created_at: int = 0
    updated_at: int = 0
    notes: str = ""

    def as_row(self) -> dict:
        return asdict(self)
