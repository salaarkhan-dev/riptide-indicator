"""The exhaustion counts from riptide-reversal.pine, ported line for line.

WHY A SEPARATE MODULE. The Pine version is a chart aid with no measured edge.
The only way that changes is if the identical logic runs over the same 333 days
of candles every other study here uses — so this is a PORT, not a
reimplementation, and it is kept apart from the study that consumes it so the
port can be checked on its own.

WHAT IT IS UNDERNEATH. TD Sequential. `momentum` is the 9-bar Setup, `terminal`
the 13-bar Countdown. The names match the indicator so a reader can hold one
vocabulary; the mechanics match DeMark so the result is comparable to the
public record.

THE ORDER OF EVALUATION IS PART OF THE PORT AND IS EASY TO GET WRONG. Pine runs
a script top to bottom once per bar, and a `var` still holds the PREVIOUS bar's
value until its assignment line is reached. So inside one bar:

    1. the setup counts update
    2. the momentum resistance/support levels update  (this bar's values)
    3. the countdown reads that level and its OWN previous count

Reading the countdown against the same bar's count, or against a level computed
after it, changes which bars qualify. Both were checked against the Pine source
line by line rather than inferred from behaviour.

NAMING, because it trips everyone once: `buy` counts while price is FALLING. It
is counting a decline, looking for it to exhaust into a possible bullish turn.
A completed buy count pairs with a LONG.
"""
from __future__ import annotations


class Counts:
    """Per-bar arrays, all the same length as the candle list handed in.

    `buy_setup[i] == 9` means a buy-side Momentum count COMPLETED on bar i.
    `buy_cd[i] == 13` means a buy-side Terminal count completed on bar i.
    """

    __slots__ = ("buy_setup", "sell_setup", "buy_cd", "sell_cd",
                 "buy_res", "sell_sup", "buy_perfect", "sell_perfect",
                 "buy_stop", "sell_stop")

    def __init__(self, n: int):
        self.buy_setup = [0] * n
        self.sell_setup = [0] * n
        self.buy_cd = [0] * n
        self.sell_cd = [0] * n
        self.buy_res = [0.0] * n          # ME resistance, 0 when inactive
        self.sell_sup = [0.0] * n         # ME support, 0 when inactive
        self.buy_perfect = [False] * n    # the "ǫ" qualifier
        self.sell_perfect = [False] * n
        self.buy_stop = [0.0] * n         # momentum invalidation, 0 when off
        self.sell_stop = [0.0] * n


def counts(cs) -> Counts:
    """Run both phases over a candle list. `cs[i]` needs .h .l .c only.

    Bars before index 5 cannot form a momentum shift (it reads close[5]), so
    the counts stay at 0 there — the same as Pine, where the history reference
    is na and the comparison is false.
    """
    n = len(cs)
    out = Counts(n)
    if n < 6:
        return out

    buy = sell = 0
    buy_res = sell_sup = 0.0
    buy_cd = sell_cd = 0
    start_buy_cd = start_sell_cd = False
    buy_ref8 = sell_ref8 = 0.0
    # The extremes each phase tracks. Carried across bars exactly as the Pine
    # `var` declarations do, including the fact that they are NOT reset when a
    # phase ends — only when a new one starts at count 1.
    buy_lowest = buy_high = buy_stop = 0.0
    sell_highest = sell_low = sell_stop = 0.0

    for i in range(n):
        c, h, lo = cs[i].c, cs[i].h, cs[i].l

        # ── 1. MOMENTUM (TD Setup) ────────────────────────────────────────
        if i >= 4:
            falling = c < cs[i - 4].c
            rising = c > cs[i - 4].c
        else:
            falling = rising = False
        if i >= 5:
            buy_flip = falling and cs[i - 1].c > cs[i - 5].c
            sell_flip = rising and cs[i - 1].c < cs[i - 5].c
        else:
            buy_flip = sell_flip = False

        if falling:
            buy = (1 if buy_flip else 0) if buy in (0, 9) else buy + 1
            sell = 0
        elif rising:
            sell = (1 if sell_flip else 0) if sell in (0, 9) else sell + 1
            buy = 0
        else:
            buy = sell = 0

        # "Perfection": bar 8 or 9 undercut bars 6 and 7 (low[3] and low[2]).
        if i >= 3:
            buy_perf = ((lo <= cs[i - 3].l and lo <= cs[i - 2].l)
                        or (cs[i - 1].l <= cs[i - 3].l
                            and cs[i - 1].l <= cs[i - 2].l))
            sell_perf = ((h >= cs[i - 3].h and h >= cs[i - 2].h)
                         or (cs[i - 1].h >= cs[i - 3].h
                             and cs[i - 1].h >= cs[i - 2].h))
        else:
            buy_perf = sell_perf = False

        # ── 2. MOMENTUM LEVELS, before the countdown reads them ───────────
        # ta.highest(9) / ta.lowest(9) default to high / low.
        if buy == 9:
            lookback = cs[max(0, i - 8): i + 1]
            buy_res = max(x.h for x in lookback)
        elif c > buy_res:
            buy_res = 0.0

        if sell == 9:
            lookback = cs[max(0, i - 8): i + 1]
            sell_sup = min(x.l for x in lookback)
        elif c < sell_sup:
            sell_sup = 0.0

        # The phase extremes and the invalidation levels built from them:
        # (2 x extreme) - the opposing price of the bar that set it. Carried
        # through so the port is the whole indicator rather than the half of it
        # this particular study happens to consume.
        if buy == 1:
            buy_lowest = lo
        if buy > 0:
            buy_lowest = min(lo, buy_lowest)
            if lo == buy_lowest:
                buy_high = h
        if sell == 1:
            sell_highest = h
        if sell > 0:
            sell_highest = max(h, sell_highest)
            if h == sell_highest:
                sell_low = lo

        if buy == 9:
            buy_stop = 2 * buy_lowest - buy_high
        elif c < buy_stop:
            buy_stop = 0.0
        if sell == 9:
            sell_stop = 2 * sell_highest - sell_low
        elif c > sell_stop:
            sell_stop = 0.0

        # ── 3. TERMINAL (TD Countdown) ────────────────────────────────────
        # Reads buy_res from THIS bar (step 2 above) and buy_cd from the
        # PREVIOUS bar, which is where the Pine `var` still stands at this
        # point in its own evaluation.
        cd_cond_buy = c <= cs[i - 2].l if i >= 2 else False
        cd_cond_sell = c >= cs[i - 2].h if i >= 2 else False

        if buy == 9 and buy_cd == 0:
            start_buy_cd = True
        elif sell == 9 or buy_cd == 13 or c > buy_res:
            start_buy_cd = False

        if sell == 9 and sell_cd == 0:
            start_sell_cd = True
        elif buy == 9 or sell_cd == 13 or c < sell_sup:
            start_sell_cd = False

        if start_buy_cd:
            if buy == 9:
                buy_cd = 1 if cd_cond_buy else 0
            elif cd_cond_buy:
                buy_cd += 1
        else:
            buy_cd = 0

        if start_sell_cd:
            if sell == 9:
                sell_cd = 1 if cd_cond_sell else 0
            elif cd_cond_sell:
                sell_cd += 1
        else:
            sell_cd = 0

        # Bar 13 must also take out the close of bar 8, or the count defers.
        if buy_cd == 13 and cd_cond_buy and lo >= buy_ref8:
            buy_cd = 12
        if sell_cd == 13 and cd_cond_sell and h <= sell_ref8:
            sell_cd = 12

        if buy_cd == 8 and (i == 0 or out.buy_cd[i - 1] != 8):
            buy_ref8 = c
        if sell_cd == 8 and (i == 0 or out.sell_cd[i - 1] != 8):
            sell_ref8 = c

        out.buy_setup[i] = buy
        out.sell_setup[i] = sell
        out.buy_cd[i] = buy_cd
        out.sell_cd[i] = sell_cd
        out.buy_res[i] = buy_res
        out.sell_sup[i] = sell_sup
        out.buy_perfect[i] = buy_perf and buy == 9
        out.sell_perfect[i] = sell_perf and sell == 9
        out.buy_stop[i] = buy_stop
        out.sell_stop[i] = sell_stop

    return out


def bars_since(flags, window: int) -> list:
    """For each bar, how many bars since the most recent True, or None.

    CAUSAL BY CONSTRUCTION. It only ever looks backwards, so a completion that
    happens AFTER a signal can never mark it. That is the whole reason this is
    a separate function rather than a comprehension inside the study: a
    lookahead here would make every number that follows meaningless, and it is
    the single easiest mistake to make in this kind of join.
    """
    out = [None] * len(flags)
    last = None
    for i, f in enumerate(flags):
        if f:
            last = i
        if last is not None and i - last <= window:
            out[i] = i - last
    return out


def demark_pivot(o: float, h: float, lo: float, c: float):
    """(R, P, S) for one completed range. The same weighting the Pine uses:
    an up-close range and a down-close range give different levels."""
    x = (h + 2 * lo + c) if c < o else (2 * h + lo + c) if c > o else (h + lo + 2 * c)
    return x / 2 - lo, x / 4, x / 2 - h
