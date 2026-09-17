"""How many alerts a day would the Undertow watches send?

BOTH STREAMS: the armed setups (/undertow) and the fills (/utfill).

    PYTHONPATH=. python3 indicators/undertow/studies/undertow_rate.py

THIS IS THE PRODUCT DECISION, NOT A FOOTNOTE TO IT. A heads-up stream is
decided by its volume before it is decided by anything else: forty rows a day
is a stream nobody reads, and a stream nobody reads is worse than no stream,
because it also buries the alerts that ARE measured.

It needs no pre-registration because it tests no hypothesis. It counts events.

THE EXHAUSTION WATCH'S EQUIVALENT TABLE WAS WRITTEN FROM MEMORY ONCE. It was
wrong, in every file that quoted it, and it took a study to find out. So this
exists, the numbers in riptide/watchers/undertow.py come from here, and
indicators/undertow/tests/test_watch_undertow.py pins the module's table to
this script's output rather than to a comment.

Rows, not messages: the watch sends one digest per bar close carrying every
symbol that armed on it, so 1h is at most 24 messages a day however many rows
they hold. Rows are still the unit that decides readability.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

from indicators.undertow.studies.undertow_sweep import TFS, load   # noqa: E402
from research.data import SYMBOLS                                  # noqa: E402
from riptide.config import BAR_SECONDS                             # noqa: E402
from indicators.undertow.port.undertow import P as _P              # noqa: E402
from riptide.watchers.undertow import run_setups                   # noqa: E402

STATES = ("both", "running", "immature")
# The shipped default first -- the row the watcher's RATE tables come from --
# then two wider settings, so the cost of tightening is visible beside it
# rather than needing a second run.
SWINGS = (_P().msLen, 15, 30)


def main():
    argv = [a for a in sys.argv[1:] if a in TFS]
    tfs = argv or list(TFS)
    print("UNDERTOW ALERT RATE — armed setups a day across the universe")
    print(f"{len(SYMBOLS)} symbols, cached 12,000-bar history per symbol")
    print(f"shipped config: swing {SWINGS[0]}/{_P().msShortLen}, endSweep {_P().endSweep}, endStale {_P().endStale}\n")
    print(f"  {'tf':7} {'days':>6} {'swing':>6} "
          + " ".join(f"{s:>10}" for s in STATES)
          + "   | " + " ".join(f"{'f-' + s[:6]:>8}" for s in STATES))
    table, ftable = {}, {}
    for tf in tfs:
        data = load(tf)
        if not data:
            print(f"  {tf}: no cached candles. Run undertow_sweep.py --fetch.")
            continue
        step = BAR_SECONDS[tf]
        for swing in SWINGS:
            tot = {s: 0 for s in STATES}
            fil = {s: 0 for s in STATES}
            days = 0.0
            for sym, cs in data.items():
                if len(cs) < 500:
                    continue
                days += len(cs) * step / 86400.0
                armed, filled = run_setups(cs, ms_len=swing)
                for a in armed:
                    tot["both"] += 1
                    tot[a["state"]] = tot.get(a["state"], 0) + 1
                for f in filled:
                    fil["both"] += 1
                    fil[f["state"]] = fil.get(f["state"], 0) + 1
            # Symbol-days, so the rate is "rows a day across the universe"
            # exactly as the chat would see it.
            span = days / len(data) if data else 1.0
            per = {s: round(tot[s] / span) if span else 0 for s in STATES}
            pef = {s: round(fil[s] / span) if span else 0 for s in STATES}
            if swing == SWINGS[0]:
                table[tf] = per
                ftable[tf] = pef
            print(f"  {tf:7} {span:6.0f} {swing:6} "
                  + " ".join(f"{per[s]:10}" for s in STATES)
                  + "   |" + " ".join(f"{pef[s]:8}" for s in STATES))
    print("\n  Rows a DAY. One digest per bar close, so 1h is at most 24")
    print("  messages however many rows they carry.\n")
    print("  For riptide/watchers/undertow.py — paste over RATE_BOTH / RATE_ONE:")
    print("RATE_BOTH = {" + ", ".join(
        f'"{t}": {v["both"]}' for t, v in table.items()) + "}")
    print("RATE_ONE = {")
    for s in ("running", "immature"):
        print(f'    "{s}": {{'
              + ", ".join(f'"{t}": {v[s]}' for t, v in table.items()) + "},")
    print("}")
    print("\n  ...and FILL_BOTH / FILL_ONE (the /utfill stream):")
    print("FILL_BOTH = {" + ", ".join(
        f'"{t}": {v["both"]}' for t, v in ftable.items()) + "}")
    print("FILL_ONE = {")
    for s in ("running", "immature"):
        print(f'    "{s}": {{'
              + ", ".join(f'"{t}": {v[s]}' for t, v in ftable.items()) + "},")
    print("}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
