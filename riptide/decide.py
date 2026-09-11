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

The window is one bar of the SLOWEST SCANNED timeframe, which is an hour while
INTERVALS ends at Min60 and would become four hours if Hour4 were added. Tying
it to the configuration rather than hardcoding 3600 is deliberate: the whole
point is "one market move", and what counts as one move scales with the slowest
chart being watched.

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

from collections import defaultdict

from .config import BAR_SECONDS, INTERVAL, INTERVALS, PICK_ORDER, log

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
    """One market event, in seconds: one bar of the slowest scanned timeframe.

    Derived from INTERVALS rather than hardcoded, because "one market move"
    scales with the slowest chart being watched. With Min30+Min15+Min60 this is
    3600; adding Hour4 would make it 14400 without another edit here.
    """
    steps = [BAR_SECONDS[i] for i in INTERVALS if i in BAR_SECONDS]
    return max(steps) if steps else BAR_SECONDS.get(INTERVAL, 1800)


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


def decide(results) -> None:
    """Tag every signal in this cycle with its event and whether it is the pick.

    Sets four attributes and reads none of its own output:

        event_size  how many signals share this market event
        event_pick  True on exactly one member
        event_of    the picked symbol, on every member including the pick
        event_weak  True when even the best member is a "skip" band

    Suppresses nothing. Raises nothing that matters — the caller wraps it, and
    a failure here must cost a chip, never an alert.
    """
    span = event_span()
    groups = defaultdict(list)
    for setups, _, early, _ in results:
        for x in list(setups) + list(early):
            if not signal_time(x):
                # No timestamp means no event. Tag it as a singleton rather
                # than dropping it, so downstream getattr defaults never have
                # to distinguish "not grouped" from "grouped alone".
                x.event_size, x.event_pick = 1, False
                x.event_of, x.event_weak = "", False
                continue
            groups[event_key(x, span)].append(x)

    for members in groups.values():
        best = min(members, key=rank_key)
        weak = band_of(best) == SKIP
        for x in members:
            x.event_size = len(members)
            x.event_pick = x is best
            x.event_of = best.symbol
            x.event_weak = weak


def describe() -> str:
    """One line for /status, so the live ordering is never a guess."""
    order = ("band → tf → confirmed" if PICK_ORDER == "band"
             else "tf → band → confirmed")
    return f"one pick per {event_span() // 60}m across all tfs · {order}"


if PICK_ORDER not in ("tf", "band"):                      # pragma: no cover
    log.warning("RIPTIDE_PICK_ORDER=%r is not 'tf' or 'band', using 'tf'",
                PICK_ORDER)
