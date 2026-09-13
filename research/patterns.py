"""Candlestick reversal patterns, in the direction the trade needs.

Every function takes (candles, i) and returns True when the pattern completes
ON bar i and points the way `is_long` wants. Definitions use the relaxed
open-versus-prior-close form rather than the textbook gap form: crypto trades
continuously and almost never gaps, so the strict version would fire perhaps
twice a year and measure nothing.
"""


def _b(c):
    return abs(c.c - c.o)


def _rng(c):
    return max(c.h - c.l, 1e-12)


def bull(c):
    return c.c > c.o


def engulfing(cs, i, is_long):
    """Body fully covers the previous body, opposite colour."""
    if i < 1:
        return False
    p, c = cs[i - 1], cs[i]
    if is_long:
        return (not bull(p)) and bull(c) and c.c >= p.o and c.o <= p.c
    return bull(p) and (not bull(c)) and c.c <= p.o and c.o >= p.c


def engulf_small(cs, i, is_long, max_body=0.35):
    """The user's 'positive/negative engulfing' — an engulfing whose victim is
    a SMALL-bodied candle (a hammer, doji or spinning top) rather than a full
    one. A different claim from plain engulfing: it says the prior bar showed
    indecision and this one resolved it."""
    if not engulfing(cs, i, is_long):
        return False
    p = cs[i - 1]
    return _b(p) / _rng(p) <= max_body


def piercing_or_darkcloud(cs, i, is_long):
    """Textbook Piercing Line / Dark Cloud Cover — and it CANNOT FIRE HERE.

    The definition requires the bar to open beyond the previous close, which
    means a gap. A 24/7 perpetual has no gaps: bar i opens where bar i-1
    closed, to the tick. Measured, this returned 0 of 1638 signals and 0 of
    1999 bars scanned in either direction.

    Kept, unused, because a pattern that is structurally impossible on this
    market is worth stating once rather than rediscovering. Any indicator
    LABELLING these on a crypto chart has dropped the gap condition, which is
    what piercing_gapless does below — and that is a different pattern
    wearing the same name.
    """
    if i < 1:
        return False
    p, c = cs[i - 1], cs[i]
    mid = (p.o + p.c) / 2
    if is_long:
        return (not bull(p)) and bull(c) and c.o < p.c and c.c > mid and c.c < p.o
    return bull(p) and (not bull(c)) and c.o > p.c and c.c < mid and c.c > p.o


def piercing_gapless(cs, i, is_long):
    """The version a crypto chart actually draws: closes back past the
    midpoint of the previous opposing body, without engulfing it. No gap
    required."""
    if i < 1:
        return False
    p, c = cs[i - 1], cs[i]
    mid = (p.o + p.c) / 2
    if is_long:
        return (not bull(p)) and bull(c) and c.c > mid and c.c < p.o
    return bull(p) and (not bull(c)) and c.c < mid and c.c > p.o


def hammer_or_star(cs, i, is_long, wick_mult=2.0, opp_max=1.0):
    """Hammer for longs, Shooting Star for shorts: a long wick INTO the raid
    direction and a small body at the other end."""
    c = cs[i]
    body = _b(c)
    if body <= 0:
        body = _rng(c) * 0.01
    lower = min(c.o, c.c) - c.l
    upper = c.h - max(c.o, c.c)
    if is_long:
        return lower >= wick_mult * body and upper <= opp_max * body
    return upper >= wick_mult * body and lower <= opp_max * body


def star(cs, i, is_long):
    """Morning Star / Evening Star: a big opposing bar, a small-bodied bar,
    then a bar closing back past the midpoint of the first."""
    if i < 2:
        return False
    a, b, c = cs[i - 2], cs[i - 1], cs[i]
    if _b(b) / _rng(b) > 0.35:
        return False
    mid = (a.o + a.c) / 2
    if is_long:
        return (not bull(a)) and bull(c) and c.c > mid
    return bull(a) and (not bull(c)) and c.c < mid


PATTERNS = {
    "engulfing": engulfing,
    "engulfing of a small body": engulf_small,
    "piercing / dark cloud (gapless)": piercing_gapless,
    "hammer / shooting star": hammer_or_star,
    "morning / evening star": star,
}


def any_pattern(cs, i, is_long):
    return any(f(cs, i, is_long) for f in PATTERNS.values())
