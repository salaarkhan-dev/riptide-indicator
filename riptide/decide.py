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
     30m" is not a claim this repo can make.

     THIS KEY'S STATED JUSTIFICATION WAS A FEE ARGUMENT AND THE FEE ARGUMENT
     IS WITHDRAWN AS A JUSTIFICATION, though not as a fact. It used to read:
     "the fee takes 67% of the gross edge on 15m and 16% on 1h, so preferring
     the slower chart is a COST argument and cost arguments do not need a
     significance test."

     Both halves of that are wrong. research/studies/fee_key.py, on the
     deployed stream at the rates harness.py measured from a real settlement:

         15m   median stop 1.01%   gross +0.0064   net -0.0268   fee 521% of gross
         30m   median stop 1.45%   gross +0.0486   net +0.0255   fee  47%
         1h    median stop 2.04%   gross +0.0594   net +0.0435   fee  27%

     The 67% was computed at the old 0.02/0.06 list rates and never recomputed;
     the true figure on 15m is not 67% but FIVE TIMES the gross edge, because
     the gross edge there is nearly zero and fee in R is fee_pct / risk_pct.
     So the cost gradient is far steeper than the docstring claimed.

     And it still does not justify this key, because the key does not depend on
     it. Re-scored with fees switched OFF entirely, tf-first leads by the same
     margin it does with them on — 10.72 against 9.04 for no-band, 9.48 for
     band-demoted, 10.26 for band-first — and beats 78% of random tiebreaks
     without fees against 80% with them. If the fee were what made this key
     work, removing it would collapse the arm. It does not move.

     What is left is honest and thin: tf-first leads every alternative tried,
     in both halves, with and without fees, and it has never been shown to beat
     a coin toss in that seat (see the note under key 2). It is kept because it
     leads, not because there is a mechanism behind it.

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

     THIS KEY IS NOT DOING MEASURABLE WORK AND THE PARAGRAPH ABOVE IS KEPT ONLY
     AS THE HISTORY OF WHY IT IS HERE. research/studies/band_key.py held the
     population, the cooldown and the arrival clock fixed and swapped only the
     key, then put a COIN TOSS in this seat over 40 seeds:

         A  tf > band > confd  (shipped)      recovery 6.52   halves 3.23 / 3.57
         B  tf > confd (band removed)                  5.46          3.48 / 2.75
         C  tf > confd > band                          5.91          3.50 / 3.18
         D  band > tf > confd                          6.18          3.30 / 3.33
         E  tf > coin toss        5th 3.93   median 5.72   90th 6.99   95th 8.24

     Every arm lands inside the coin toss's spread. The shipped rule beats 80%
     of tosses, short of the 90th percentile its pre-registration required, and
     it is BELOW the random median in the first half. Nothing else beat it
     either, so the pre-registered default applied and nothing changed.

     AND ON THIS STREAM THE ORDER APPEARS TO BE INVERTED. Under survivor.py's
     symbol bootstrap, on confirmed alerts the bot actually sends:

         tight   +0.218   boot [+0.115, +0.289]    0% of draws <= 0
         normal  -0.019   boot [-0.120, +0.048]   76%
         wide    -0.060   boot [-0.199, +0.071]   74%

     This key ranks normal FIRST. survivor.py measured the band on all 595
     confirmed Min30 signals; the rows above are the subset also sitting in a
     daily POI with the trend agreeing, and the two filters evidently overlap.
     Not acted on: a cell found after looking does not get to reorder a
     ranking, and it needs its own pre-registered forward test first.

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
# PERSISTED SINCE 11 SEP, AND THE REASON IS THAT THE OLD NOTE HERE WAS WRONG.
#
# It said: in process, not in the database; a restart forgets; the cost is one
# extra target chip after a restart, which is rare, because the service
# restarts on a conf commit.
#
# Both halves were wrong. Restarts are NOT rare — deploy/update.sh restarts the
# service on every auto-update, which is every push to the branch, and a live
# chat showed two inside thirty minutes. And the cost is not one chip: the
# window is cleared for BOTH directions, so the very next scan claims a fresh
# long pick and a fresh short pick regardless of what was sent minutes earlier.
# Reported from the chat as three 🎯 alerts, all 15m, all early, inside one
# 120-minute window — which is three times the position the rule exists to
# hold, and the rule's entire measured value (recovery 0.13 against 6.66) is in
# holding it.
#
# So it is stored, as one string in the `meta` table the bot already keeps.
# There is no table and no migration — that was the other half of the old
# excuse. The scanner owns the read and the write, which keeps this module free
# of storage and testable on stubs; see dump() and load().
_LAST: dict[bool, tuple[int, str]] = {}


def reset() -> None:
    """Forget the standing picks. For tests, and for /scan to behave the same
    way twice."""
    _LAST.clear()


def dump() -> str:
    """The standing picks as one short string, for the caller to persist.

    "1:1789002000:SOL_USDT|0:1789003000:PEPE_USDT" — direction, when, symbol.
    Not JSON: it goes into a single `meta` value that a human reads with sqlite
    when a pick looks wrong, and a quoted dict is harder to read there than
    three fields and two separators.
    """
    return "|".join(f"{int(up)}:{when}:{sym}"
                    for up, (when, sym) in sorted(_LAST.items()))


def load(text: str) -> None:
    """Restore what dump() wrote. Never raises.

    LEAVES THE CURRENT STATE ALONE on empty or unparseable input, rather than
    clearing it. The two are not symmetric: keeping a window the bot may
    already have released costs at most one delayed pick, while clearing one it
    should still be holding costs an extra position in a move — which is the
    exact failure this whole mechanism exists to prevent. So the safe direction
    on any doubt is to keep holding.

    A window older than the cooldown needs no special handling here: decide()
    already tests `0 <= now - when < span`, so a stale entry simply is not
    standing, and a clock that went backwards fails the same test.
    """
    if not text:
        return
    fresh: dict[bool, tuple[int, str]] = {}
    try:
        for part in text.split("|"):
            if not part:
                continue
            up, when, sym = part.split(":", 2)
            fresh[bool(int(up))] = (int(when), sym)
    except (ValueError, TypeError) as e:
        log.warning("pick window %r is unreadable, keeping the one in "
                    "memory: %s", text[:80], e)
        return
    # A NON-EMPTY STRING THAT PARSES TO NOTHING IS NOT AN EMPTY WINDOW. "|||"
    # splits into four blank fields, every one of them skipped, and an earlier
    # version of this took that as "no picks standing" and cleared the window —
    # the one direction this function is not allowed to fail in. Caught by
    # tests/test_event_pick.py, which feeds it exactly that.
    if not fresh:
        log.warning("pick window %r parsed to nothing, keeping the one in "
                    "memory", text[:80])
        return
    _LAST.clear()
    _LAST.update(fresh)


def standing(now: int | None = None) -> list:
    """[(direction, symbol, seconds held)] for the windows still running.

    For /status. A rule whose whole value is in NOT naming a second pick is
    invisible when it is working, so there has to be somewhere that says it is.
    """
    now = int(time.time()) if now is None else int(now)
    span = event_span()
    return [("long" if up else "short", sym, now - when)
            for up, (when, sym) in sorted(_LAST.items(), reverse=True)
            if 0 <= now - when < span]


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
