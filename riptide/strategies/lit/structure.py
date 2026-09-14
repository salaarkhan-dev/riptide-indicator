"""Adapter over the FROZEN LIT structure engine. It holds no rules of its own.

THERE IS ONE ENGINE AND THIS FILE IS NOT A SECOND COPY OF IT. The structure
definition lives in `research/lit_v3.py` — persistent inside bars, pullback
formation, pivot derivation, IDM creation/migration/break, BOS lock and break,
CHoCH creation and break, Hidden Shadow, Body & Sweep. That code was validated
against the reference indicator's own published statistics (ZEC 30m IDM→BOS
65.6% against the reference's 65.0%) and it is imported, never reimplemented.

`research/harness.py` says why, about a different scorer, and it applies here
word for word: "research/studies/mss_entry.py kept its own copy of a scorer and
got the entry bar wrong, silently, for as long as nobody compared them."

COST. Measured before choosing this shape: engine() over 2000 bars is 7.7 ms,
so 60 symbols across three timeframes is ~1.4 s of CPU per cycle at 42 MB peak.
That is affordable on the Oracle free tier, which is why the frozen engine is
re-run over a BOUNDED window rather than refactored into an incremental
stepper. Refactoring it would risk changing its behaviour, and its behaviour is
the only thing making forward evidence comparable to the historical work.

!! PINE <-> PYTHON PARITY IS NOT ESTABLISHED !!

There is no Pine compiler in this environment and `riptide-lit-v2.pine` has
never been compiled here. This module therefore makes NO parity claim.
PREREG_lit_forward_v1.md §0 records it as the open precondition on activation.
"""

from __future__ import annotations

import os
from typing import Any, Sequence

# research/env must be imported before riptide.config is touched by the
# research modules; importing it here keeps that ordering rule in one place.
import research.env  # noqa: F401
import research.lit_v3 as _engine
from research.studies.lit_stage_a import trails as _trails

#: Bars fed to the engine each pass. Bounded so a cycle never costs more than
#: the measurement above, and generous enough that MAIN structure is warm.
WINDOW = int(os.getenv("RIPTIDE_LIT_WINDOW", "1200"))

#: Bars of warm-up before a setup is eligible, matching the research.
WARMUP = 500


def run(candles: Sequence[Any]) -> tuple[Any, list[dict]]:
    """MAIN context and its event list, from the frozen engine.

    Returns (main_ctx, events). Internal and Deep are computed by the engine
    and deliberately discarded: the pre-registrations measured MAIN depth and
    nothing else publishes a setup.
    """
    main, _internal, _deep, _g = _engine.engine(candles)
    return main, main.events


def trail_levels(candles: Sequence[Any], events: list[dict]) -> dict:
    """Per-bar T6_PIVOT trail levels, keyed by direction.

    Imported from the Stage C harness rather than rewritten, because the two
    accumulators here are easy to conflate and doing so would silently break
    parity with the historical result:

      * the TRAIL pivot forward-fills ACROSS structural cycles — it is simply
        the most recent confirmed pullback pivot of that direction;
      * the STOP pivot is scoped to the CURRENT cycle and is the one BEHIND
        the IDM (see signals.py).

    They are different levels and they are not interchangeable.
    """
    piv, _stc = _trails(candles, events)
    return piv


def window(candles: Sequence[Any]) -> Sequence[Any]:
    """The bounded slice actually fed to the engine."""
    return candles[-WINDOW:] if len(candles) > WINDOW else candles
