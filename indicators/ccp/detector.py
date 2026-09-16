"""The twelve CCP confirmation patterns, defined once.

Transcribed from the CCP sheet. Every study, and any future Pine port, reads
its definitions from here so the two cannot mean different things by the same
name.

    4 x 1CP   one candle:  a pin
    8 x 2CP   two candles: a pin, then a candle that ENGULFS it
   12 total

SIZE IS NOT PART OF ANY DEFINITION. Every test below is a ratio of the
candle's own range, so a three-tick doji and a whole day's bar classify
identically. That is deliberate: on a real chart no pattern ever looks like
the diagram, and what survives the difference is the proportion.

    rng  = high - low
    body = |close - open| / rng
    up   = (high - max(open, close)) / rng
    dn   = (min(open, close) - low) / rng          body + up + dn == 1

FOUR NAMES, TWO SHAPES. A hammer and a hanging man are the identical candle in
two colours and both are bullish; so are the inverted hammer and the shooting
star, and both are bearish. The WICK sets direction, the body colour only sets
the name. Naming by colour rather than by position is deliberate — colour is in
the data, position is a judgement about where a move "was" and cannot be made
without hindsight.

WHY A SHOOTING STAR CAN OPEN A LONG. In a 2CP the pin's job is to mark that
price was rejected AT ALL, not which way. The engulfing candle settles the
direction. So any of the four pins can appear on either side, which is why
there are eight 2CPs and not four.

ENGULFING IS A BODY RELATION, NOT A PICTURE. The second candle's body must
cover the first candle's body. Wicks are not part of the test — a real
engulfing candle may have long wicks, short ones or none, and demanding a clean
marubozu would reject most of the true cases.
"""
from __future__ import annotations

BODY_MAX = 0.25         # the shipped pin body cap
WICK_MIN = 0.70         # the shipped pin wick floor

PIN_NAMES = {
    (True, True): "Hammer",             # bullish shape, green body
    (True, False): "Hanging man",       # bullish shape, red body
    (False, True): "Inverted hammer",   # bearish shape, green body
    (False, False): "Shooting star",    # bearish shape, red body
}

# The twelve, in the sheet's order. Studies iterate this so a family size is
# never miscounted by hand.
PATTERNS = (
    [f"1CP {n}" for n in ("Hammer", "Hanging man",
                          "Inverted hammer", "Shooting star")]
    + [f"2CP {p} + {c} engulfing"
       for p in ("Hammer", "Hanging man", "Inverted hammer", "Shooting star")
       for c in ("green", "red")]
)


def ratios(c):
    """(body, up, dn, green) as fractions of the candle's own range."""
    rng = c.h - c.l
    if rng <= 0:
        return None
    return (abs(c.c - c.o) / rng,
            (c.h - max(c.o, c.c)) / rng,
            (min(c.o, c.c) - c.l) / rng,
            c.c >= c.o)


def pin(c, body_max: float = BODY_MAX, wick_min: float = WICK_MIN):
    """(bullish, name) if this candle is a pin, else None.

    Bullish means the LONG WICK IS BELOW — price was rejected downward — which
    is true whatever colour the body is.
    """
    r = ratios(c)
    if r is None:
        return None
    body, up, dn, green = r
    if body > body_max or max(up, dn) < wick_min:
        return None
    if up == dn:
        return None                      # no direction; refuse to invent one
    bullish = dn > up
    return bullish, PIN_NAMES[(bullish, green)]


def engulfs(c1, c2) -> bool:
    """Does c2's BODY cover c1's body? Wicks are not part of this."""
    lo1, hi1 = min(c1.o, c1.c), max(c1.o, c1.c)
    lo2, hi2 = min(c2.o, c2.c), max(c2.o, c2.c)
    if hi2 - lo2 <= 0:
        return False                     # a doji engulfs nothing
    return lo2 <= lo1 and hi2 >= hi1


def one_cp(c, body_max: float = BODY_MAX, wick_min: float = WICK_MIN):
    """A 1CP at candle `c`, or None.

    Entry sits at the body edge on the trade side; the stop sits beyond the
    wick that did the rejecting.
    """
    p = pin(c, body_max, wick_min)
    if p is None:
        return None
    bullish, name = p
    return {
        "name": f"1CP {name}",
        "bullish": bullish,
        "entry": max(c.o, c.c) if bullish else min(c.o, c.c),
        "stop": c.l if bullish else c.h,
    }


def two_cp(c1, c2, body_max: float = BODY_MAX, wick_min: float = WICK_MIN):
    """A 2CP across `c1` (the pin) and `c2` (the engulfing candle), or None.

    THE SECOND CANDLE SETS THE DIRECTION, not the pin. Entry sits at the body
    edge of the second candle; the stop sits beyond the furthest wick of the
    PAIR, which is what makes this a different risk from the 1CP even when the
    pin is identical.
    """
    p = pin(c1, body_max, wick_min)
    if p is None or not engulfs(c1, c2):
        return None
    _, pin_name = p
    r2 = ratios(c2)
    if r2 is None:
        return None
    green2 = r2[3]
    bullish = green2
    return {
        "name": f"2CP {pin_name} + {'green' if green2 else 'red'} engulfing",
        "bullish": bullish,
        "entry": max(c2.o, c2.c) if bullish else min(c2.o, c2.c),
        "stop": min(c1.l, c2.l) if bullish else max(c1.h, c2.h),
    }


def engulf_only(c1, c2):
    """THE CONTROL, and the most important function in this file.

    A 2CP is "a pin, then an engulfing candle", and the engulfing candle
    decides everything — direction, entry, and half the stop. So the obvious
    question is whether the pin contributes anything at all. This is the same
    pattern with the pin requirement dropped: any candle, then one that engulfs
    it.

    If 2CPs score like engulf-only, the pin is decoration and eight of the
    twelve patterns collapse into two.
    """
    if not engulfs(c1, c2):
        return None
    r2 = ratios(c2)
    if r2 is None:
        return None
    bullish = r2[3]
    return {
        "name": f"CTL {'green' if bullish else 'red'} engulfing, no pin",
        "bullish": bullish,
        "entry": max(c2.o, c2.c) if bullish else min(c2.o, c2.c),
        "stop": min(c1.l, c2.l) if bullish else max(c1.h, c2.h),
    }
