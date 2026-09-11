"""The decision system: which ONE signal to take out of a market event.

THIS IS THE HIGHEST-VALUE RULE IN THE BOT AND IT IS WORTH SAYING WHY BEFORE
SAYING HOW. `research/studies/pick_rule.py`, 9071 filled trades in 4200 market
events over 333 days, scored on the stream the bot actually sends:

    take every alert          55.4/day   recovery  0.13   account  -51%
    one per event, at random  25.7/day   recovery  2.25   account +234%
    one per event, ranked     25.7/day   recovery  5.46   account +860%

Recovery 0.13 to 5.46 from a LABEL. Nothing else measured on this project moves
a number forty-fold, and no filter here comes close. Most of the value is in
taking ONE — even a random pick reaches 2.25 — and the ranking is the smaller
half of the prize. Taking the top TWO instead of one drops it back to 1.75, and
the top three to 0.80, so "one" is the rule and not a preference.

NOTHING HERE SUPPRESSES ANYTHING. Every alert still sends, in full, with its
own entry, stop and targets. This module decides which one gets the target
chip. It is a reading aid with a measured effect, not a gate.

──────────────────────────────────────────────────────────────────────────────
THE GROUPING, WHICH MATTERS MORE THAN THE RANKING

A market move raids pools on dozens of perpetuals inside the same hour, and
since Min60 was added each of those can print on 15m, 30m and 1h. That is ONE
event. The rule this module replaces grouped on (timeframe, bar, direction) and
so named up to three picks for one move — the exact failure the "size once"
chip exists to prevent, arriving through a door that chip does not watch.

    per bar per timeframe (the old rule)   36.0/day   recovery 1.39   +104%
    per SLOWEST bar, across timeframes     25.7/day   recovery 4.85   +580%

Widening the window is worth +3.46 recovery. Re-ordering inside the wide window
is worth +0.61. The grouping is the change; the tiebreak is the polish.

THE WINDOW IS ROLLING, AND MEASURED CAUSALLY. The rows above use hindsight —
they know at 11:30 what will arrive at 12:00 — and no bot can. Scored the way
a bot has to run, in arrival order, with the pick standing for a fixed time
afterwards (research/studies/pick_rule.py):

    cooldown  30m   29.8/day   recovery 3.04   1st half 0.49   +410%
    cooldown  60m   23.6/day   recovery 3.71   1st half 1.21   +375%
    cooldown 120m   17.7/day   recovery 6.66   1st half 3.31   +501%
    cooldown 240m   12.5/day   recovery 7.68   1st half 3.46   +282%

120 minutes is the default. It beats 60 in both halves and is not winning by
trading less: total R is flat from 60 to 120 (212.6 against 209.7) while the
drawdown nearly halves. 240 has the better raw ratio and pays a quarter of the
return for it, which the compounded account prices at +282% against +501%.

Rolling rather than clock-aligned because a bucket has an edge a reader hits: a
pick at 11:59 and another at 12:01 are two minutes apart and in two different
hours.

──────────────────────────────────────────────────────────────────────────────
THE RANKING, KEY BY KEY, WITH THE EVIDENCE FOR EACH

  1. TIMEFRAME, slowest first.  Measured best, and the weakest evidence.
     tf-first scores 5.46 against 4.85 for band-first, and wins in BOTH halves
     of the window (1.68 vs 1.27, 3.87 vs 3.64) and inside BOTH streams
     separately (early 4.71 vs 3.76, confirmed 1.33 vs 1.17). Against that:
     no pair of timeframes separates at even 1 SE (timeframes.py), so "1h beats
     30m" is not a claim this repo can make. What it has instead is arithmetic.
     Fee in R is fee_pct / risk_pct; the median stop doubles from 15m to 1h; so
     the fee takes 67% of the gross edge on 15m and 16% on 1h. Preferring the
     slower chart is a COST argument, not an edge argument, and cost arguments
     do not need a significance test.

  2. RISK BAND, take then flat then skip.  The best-evidenced axis and the
     reason it is second rather than first is specific. matrix.py: band against
     outside separates on 6 of 6 timeframe/stream combinations with nothing
     refitted. But pick_rule.py's cell table shows it is a CONFIRMED-signal
     filter — on confirmed it orders the cells correctly on all three
     timeframes (+0.183 against -0.198 on Min15), while on EARLY at 15m and 30m
     it is inverted and only points the right way at 1h. Early is 83% of the
     pick candidates, so band-first would be ordering most of the field by
     something close to a coin toss.

     Three tiers, not two: a tight "flat" beats a wide "skip" because the skip
     bootstrap is entirely below zero while the flat one straddles it.

  3. CONFIRMED before EARLY.  Weak and kept only as a tiebreak. matrix.py:
     confirmed leads early in 5 of 6 comparisons and clears 1 SE in none of
     them. pick_rule.py is blunter — confirmed-only scores 1.17 against 4.85
     for the mix, and early-only scores 3.76. Early signals are not worse
     signals; they arrive in crowds, and a crowd taken whole is one correlated
     bet. The early stream is worth -44% taken whole and +655% taken one per
     hour.

  4. SYMBOL, alphabetically.  Not a quality claim at all. It is there so the
     pick is DETERMINISTIC: a re-scan of the same hour must name the same
     symbol, or the chip contradicts itself between messages.

WHAT IS DELIBERATELY NOT A KEY:

  THE POI. poi_recheck.py: of twelve timeframe/stream/zone-map cells it helps
  in exactly one — Min30 confirmed on the daily map — and every early cell is
  negative in both maps. A tiebreak that is right once in twelve is noise with
  a good story attached.

  LAST YEAR'S PER-SYMBOL RETURNS. symbols.py: a leaderboard built on the first
  half of the window is worth -0.004 R per trade in the second. Ranking on past
  R does not persist and using it here would be the overfit this rule exists to
  avoid.

──────────────────────────────────────────────────────────────────────────────
AN ALL-SKIP EVENT NOW GETS A PICK, AND IT USED NOT TO

The previous rule withheld the pick when every member's stop was beyond 2.6%,
on the reasoning that naming a best-of-a-bad-lot reads as an endorsement. That
reasoning was sound and the measurement disagrees with it: withholding scores
4.08 against 4.85, and the whole difference comes from those all-skip events,
because withholding means contributing nothing where best-of-a-bad-lot still
carries edge. So a pick is always named — and when the best available is a
skip, the chip says so in words rather than showing a bare target.
"""

from __future__ import annotations

import time
from collections import defaultdict

from .config import (BAR_SECONDS, INTERVAL, INTERVALS, PICK_COOLDOWN_MIN,
                     PICK_ORDER, log)

TAKE, FLAT, SKIP = 0, 1, 2
BAND_NAMES = ("take", "flat", "skip")

# The band's boundaries, as percent of price from entry to stop. Fitted on
# Min30 confirmed in research/studies/survivor.py and NOT refitted since;
# telegram.RISK_TIGHT / RISK_WIDE are the same two numbers and the same source.
# They live there because that is where the user-facing label is built, and are
# imported rather than duplicated so the chip and the ranking can never drift.
from .telegram import RISK_TIGHT, RISK_WIDE     # noqa: E402


def band_of(x) -> int:
    """TAKE / FLAT / SKIP for one signal, from its stop distance."""
    entry = getattr(x, "entry", 0.0) or 0.0
    risk = getattr(x, "risk", 0.0) or 0.0
    pct = 100.0 * risk / entry if entry else 0.0
    if RISK_TIGHT <= pct <= RISK_WIDE:
        return TAKE
    return FLAT if pct < RISK_TIGHT else SKIP


def is_early(x) -> bool:
    """Without importing Early, so this module stays free of engine types and
    can be unit-tested on stubs."""
    return type(x).__name__ == "Early"


def event_span() -> int:
    """How long a pick holds, in seconds. A ROLLING window, not a bucket.

    A clock-aligned bucket has an edge a reader hits: a pick at 11:59 and one
    at 12:01 are two minutes apart and in two different hours. Counting from
    the LAST PICK has no boundary to fall the wrong side of, and it is what
    "one trade per move" means when said out loud.

    PICK_COOLDOWN_MIN is the setting; 0 falls back to one bar of the slowest
    scanned timeframe, which is what this returned before the cooldown existed.
    """
    if PICK_COOLDOWN_MIN > 0:
        return PICK_COOLDOWN_MIN * 60
    steps = [BAR_SECONDS[i] for i in INTERVALS if i in BAR_SECONDS]
    return max(steps) if steps else BAR_SECONDS.get(INTERVAL, 1800)


# THE PICK HAS TO OUTLIVE THE SCAN CYCLE, and the first version of this module
# did not. decide() is handed one cycle's signals and nothing else, so a 1h
# setup arriving at 12:00 could not see the 15m pick already sent at 11:30 —
# they share an hour but not a scan. That made the shipped rule behave like
# "one pick per scan" (recovery 2.46) rather than the "one per hour" that was
# measured (3.71 causally, 6.66 at a 120m cooldown).
#
# So the last pick per DIRECTION is remembered here, in process. Longs and
# shorts hold separate cooldowns for the same reason they are separate events
# everywhere else: an up-raid and a down-raid in the same hour are two moves.
#
# IN PROCESS, NOT IN THE DATABASE, and the limitation is stated rather than
# hidden. A restart forgets, so the first signal after one may claim a pick
# while an earlier pick is still inside its window. The cost is one extra
# target chip after a restart, which is rare — the service restarts on a conf
# commit — and cheap. Persisting it would need a table and a migration for a
# failure worth one chip.
_LAST: dict[bool, tuple[int, str]] = {}


def reset() -> None:
    """Forget the standing picks. For tests, and for /scan to behave the same
    way twice."""
    _LAST.clear()


def signal_time(x) -> int:
    """The bar the signal became knowable. Same fallback order the tracker and
    the breadth tagger use, so all three agree on when a signal happened."""
    return (getattr(x, "fvg_time", 0) or getattr(x, "mss_time", 0)
            or getattr(x, "sweep_time", 0) or 0)


def event_key(x, span: int | None = None):
    """(window, direction) — across every symbol and every timeframe.

    Deliberately NOT keyed on the timeframe. A 15m signal at 10:15 and the 1h
    signal at 10:00 that contains it are one raid with two timestamps, and
    keying on the timeframe is what produced three picks for one move.
    """
    t = signal_time(x)
    step = event_span() if span is None else span
    return (t - (t % step), bool(getattr(x, "is_long", False)))


def rank_key(x):
    """Sort key for one signal. Lower is better. See the module docstring for
    the evidence behind each term and the order they sit in."""
    band = band_of(x)
    slow = -BAR_SECONDS.get(getattr(x, "tf", "") or INTERVAL, 0)
    early = 1 if is_early(x) else 0
    sym = getattr(x, "symbol", "")
    if PICK_ORDER == "band":
        return (band, slow, early, sym)
    return (slow, band, early, sym)


def decide(results, now: int | None = None) -> None:
    """Tag every signal in this cycle with its event and whether it is the pick.

    Sets five attributes and reads none of its own output:

        event_size  how many signals share this direction in this cycle
        event_pick  True on the one signal that claimed the window
        event_of    the symbol holding the pick, whether named now or earlier
        event_weak  True when the claiming signal is a "skip" band
        event_age   seconds since the pick was named; 0 when named just now

    ONCE A PICK IS NAMED IT STANDS. A later signal inside the cooldown never
    overrides it — it points back at the one already sent. That is not a
    limitation, it is the requirement: a target you acted on at 11:30 must not
    be contradicted at 12:00, and research/studies/pick_hybrid.py established
    that every scheme for doing better — quality gates on claiming, delaying
    the decision to see more candidates — measures WORSE, eighteen for
    eighteen.

    Suppresses nothing. Raises nothing that matters — the caller wraps it, and
    a failure here must cost a chip, never an alert.
    """
    span = event_span()
    now = int(time.time()) if now is None else int(now)

    groups = defaultdict(list)
    for setups, _, early, _ in results:
        for x in list(setups) + list(early):
            if not signal_time(x):
                # No timestamp means no event. Tag it as a singleton rather
                # than dropping it, so downstream getattr defaults never have
                # to distinguish "not grouped" from "grouped alone".
                x.event_size, x.event_pick = 1, False
                x.event_of, x.event_weak, x.event_age = "", False, 0
                continue
            groups[bool(getattr(x, "is_long", False))].append(x)

    for up, members in groups.items():
        when, held = _LAST.get(up, (None, ""))
        standing = when is not None and 0 <= now - when < span
        best = min(members, key=rank_key)
        if not standing:
            _LAST[up] = (now, best.symbol)
            when, held = now, best.symbol
        for x in members:
            x.event_size = len(members)
            x.event_pick = (not standing) and x is best
            x.event_of = held
            x.event_weak = (not standing) and band_of(best) == SKIP
            x.event_age = max(0, now - when)


def describe() -> str:
    """One line for /status, so the live rule is never a guess."""
    order = ("band → tf → confirmed" if PICK_ORDER == "band"
             else "tf → band → confirmed")
    return (f"one pick per {event_span() // 60}m, rolling, across all tfs "
            f"· {order}")


if PICK_ORDER not in ("tf", "band"):                      # pragma: no cover
    log.warning("RIPTIDE_PICK_ORDER=%r is not 'tf' or 'band', using 'tf'",
                PICK_ORDER)
