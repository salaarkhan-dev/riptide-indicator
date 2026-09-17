"""Every indicator the watch can run, and the registry that describes one.

`registry.py` holds the contract — `Hit`, `Option`, `Indicator`, `register` —
and is where to read what an indicator has to provide. The imports at the
bottom of this file are what actually puts an indicator on the air: a module
that is never imported never calls `register`, so its loop never starts and
its `/name` command does not exist.

THE IMPORT LIST IS THE DEPLOYED SET. Adding an indicator is a module beside
this one and one line below; removing one is deleting that line. That is the
whole switch — there is no wiring in `app.py`, `storage.py` or `commands.py`
to remember, which is exactly what went wrong the last time a watch was added
by copying the previous one.

The split between this package and `indicators/<name>/` at the repo root is
deliberate and is explained in `indicators/README.md`. The short version: the
bot package must stay self-contained, because it is what systemd runs, so the
LIVE adapter lives here and the Pine source, the studies, the measurements and
the pre-registrations live in the research tree.
"""

from .registry import (Hit, Indicator, Option, all_indicators, get,  # noqa: F401
                       register, unregister)

# ---- the deployed set. One line per indicator; order is /status order. ----
from . import exhaust            # noqa: F401,E402
from . import undertow           # noqa: F401,E402
