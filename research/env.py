"""Import this FIRST in every study, before anything from riptide.

riptide.config reads RIPTIDE_LOOKBACK at import time, so setting it after the
import silently leaves you on the 600-bar live default. A study that quietly
runs on a quarter of the data still prints a confident table — which is the
same class of failure as the scorer bug: wrong in a way that looks fine.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

RESEARCH_LOOKBACK = os.environ.setdefault("RIPTIDE_LOOKBACK", "2000")

if "riptide.config" in sys.modules:                     # pragma: no cover
    raise RuntimeError(
        "research.env was imported after riptide.config. The lookback is "
        "already fixed at import time, so this study would run on live "
        "defaults. Move 'import research.env' to the top of the file.")
