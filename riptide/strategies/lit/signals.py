"""The frozen LIT_FORWARD_V1 setup. Copied literally from Stage C, not recalled.

THE SOURCE OF TRUTH, line for line, is `research/studies/lit_stage_c.py`:

    i, up, entry, bos = e["bar"], d > 0, e["entry"], e["bos"]
    prior = pbs[d][-2] if len(pbs[d]) > 1 else None
    pbs[d] = []
    if i < RP.WARMUP or bos is None or entry <= 0:      continue
    if (bos <= entry) if up else (bos >= entry):        continue   # with-trend
    if prior is None or ((prior >= entry) if up else (prior <= entry)): continue
    risk = abs(entry - prior)

and PREREG_lit_stage_c.md §3, which fixes the stop at PRIOR_PB, the primary at
T6_PIVOT and the control at BOS_TARGET.

The two were compared before this file was written and they AGREE. Had they
disagreed the task instruction was to stop and report rather than pick one.

NOTHING HERE MAY BE TUNED. Not after ten setups, not after a hundred, not
because a regime changed, not because one symbol looks strong. A rule change is
LIT_FORWARD_V2 and its results are never pooled with V1's.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from .structure import WARMUP
from .types import RULES


@dataclass(frozen=True)
class RawSetup:
    """The hypothesis at the moment it is born. Frozen by construction: once
    built, no later bar may change any of it."""

    bar: int
    direction: int
    signal_time: int
    entry: float
    stop: float
    bos: float
    choch: float | None
    idm_price: float | None
    raid_extreme: float
    structure_time: int
    risk: float
    active: float
    bos_distance_r: float


def _fee_fraction() -> float:
    """The round trip as a FRACTION of price, from the repo's own model.

    research/harness.py: FEE_MAKER 0.010% + FEE_TAKER 0.022%, quoted in
    percent. Stage C used simulate_market's maker/taker split for the R
    calculation; Active Price uses the conservative round trip, exactly as the
    historical harness did when it placed the level.
    """
    from research.harness import FEE_MAKER, FEE_TAKER
    return (FEE_MAKER + FEE_TAKER) / 100.0


def detect(candles: Sequence[Any], events: list[dict]) -> list[RawSetup]:
    """Every V1 setup in this window, oldest first.

    The caller decides which of them are eligible for the forward experiment;
    this function applies the STRUCTURE rules only and knows nothing about
    activation time. Keeping the two apart is what makes the start-time gate
    testable on its own.
    """
    out: list[RawSetup] = []
    pbs: dict[int, list[float]] = {1: [], -1: []}
    idm: dict[int, float | None] = {1: None, -1: None}
    idm_bar: dict[int, int | None] = {1: None, -1: None}
    fee = _fee_fraction()
    rr = float(RULES["min_rr"])

    for e in events:
        d = 1 if e["dir"] > 0 else -1
        kind = e["kind"]
        if kind == "pb":
            pbs[d].append(e["px"])
            continue
        if kind == "idm":
            idm[d] = e["px"]
            idm_bar[d] = e.get("pivotBar")
            continue
        if kind != "idm_break":
            continue

        i = e["bar"]
        up = d > 0
        entry = e["entry"]
        bos = e["bos"]
        # The most recent pivot IS the IDM being broken, so the stop is the one
        # BEHIND it. Scoped to this cycle, and the cycle ends here.
        prior = pbs[d][-2] if len(pbs[d]) > 1 else None
        this_idm = idm[d]
        this_idm_bar = idm_bar[d]
        pbs[d] = []
        idm[d] = None
        idm_bar[d] = None

        if i < WARMUP or bos is None or entry is None or entry <= 0:
            continue
        # with-trend only: the BOS the thesis targets must lie beyond the entry
        if (bos <= entry) if up else (bos >= entry):
            continue
        # PREREG §3: no prior pivot, or one on the wrong side, is a SKIP. It is
        # never given a substitute level.
        if prior is None or ((prior >= entry) if up else (prior <= entry)):
            continue
        risk = abs(entry - prior)
        if risk <= 0:
            continue

        # [SRC Ch.18] Active Price ARMS the trail. It is not a target.
        active = entry + (1 if up else -1) * (rr * risk + entry * fee)
        st = candles[this_idm_bar].t if this_idm_bar is not None and \
            0 <= this_idm_bar < len(candles) else candles[i].t
        out.append(RawSetup(
            bar=i, direction=d, signal_time=candles[i].t, entry=entry,
            stop=prior, bos=bos, choch=e.get("choch"), idm_price=this_idm,
            raid_extreme=e.get("stop"), structure_time=st, risk=risk,
            active=active, bos_distance_r=abs(bos - entry) / risk))
    return out


def setup_id(version: str, symbol: str, tf: str, direction: int,
             signal_time: int) -> str:
    """A deterministic key, so repeated scanner passes cannot duplicate a setup.

    Includes the VERSION, so a future V2 observing the same bar records its own
    row rather than colliding with V1's and silently overwriting history.
    """
    side = "L" if direction > 0 else "S"
    return f"{version}|{symbol}|{tf}|{side}|{int(signal_time)}"
