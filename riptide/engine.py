"""The engine: liquidity pool -> sweep -> market structure shift -> fair value gap.

A single pass over closed candles, mirroring the Pine bar loop. Pure and
synchronous: no I/O, no clock, no network. Everything it needs arrives as
arguments, which is what makes it testable against recorded data.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .config import (CFG, Cfg, DI_INTERVAL, MAX_SWEEP_RVOL, POI_INTERVAL,
                     TREND_INTERVAL, WATCH_MAX_DIST)

@dataclass
class Candle:
    t: int
    o: float
    h: float
    l: float
    c: float
    v: float = 0.0        # contract volume. Defaulted so every existing
                          # construction still works; only research reads it.


@dataclass
class Cluster:
    is_high: bool
    level: float
    oldest_bar: int
    created_bar: int
    src: str = "Pivot"
    prices: list = field(default_factory=list)
    bars: list = field(default_factory=list)
    active: bool = False
    swept: bool = False
    mss: bool = False
    done: bool = False
    expired: bool = False
    sweep_bar: int = -1
    grab_bar: int = -1
    grab_high: float = 0.0
    grab_low: float = 0.0
    grab_close: float = 0.0
    run_min: float = 0.0
    run_max: float = 0.0
    run_min_bar: int = -1
    run_max_bar: int = -1
    struct_level: float = 0.0
    mss_bar: int = -1
    early_done: bool = False      # the no-shift signal has fired, or timed out


@dataclass
class Setup:
    symbol: str
    is_long: bool
    src: str
    level: float
    entry: float
    stop: float
    risk: float
    grab_bar: int
    mss_bar: int
    mss_time: int
    anchor_time: int
    pivots: int
    sweep_time: int = 0    # bar that took the pool
    grab_time: int = 0     # deepest bar of the raid — NOT the sweep bar.
                           # trail_grab_extreme moves this to the extreme, and
                           # it is what the stop is measured from.
    fvg_time: int = 0      # bar the entry gap closed on
    entry_tf: str = "HTF"  # "LTF" once mtf.refine has moved the entry
    trend_dir: int = 0     # higher-timeframe trend at the shift:
                           # +1 up, -1 down, 0 unknown. Set by the
                           # scanner, never by the engine.
    last_price: float = 0.0  # latest close, for the alert footer only. Also
                             # set by the scanner; the engine never reads it.
    confluence: int = 0      # how many of {order block, breaker} share the
                             # gap's price area. 0-2. See confluence_of.
    pools: int = 0           # how many clusters reached this same gap. Set by
                             # collapse(), not by detection.
    tf: str = ""             # the structure timeframe this was found on.
                             # Blank means RIPTIDE_INTERVAL; the scanner sets
                             # it explicitly once more than one is scanned.
    span: float = 0.0        # price distance between the cluster's highest and
                             # lowest pivot — how COMPRESSED the pool was. Set
                             # at construction, read by nothing in production;
                             # research/studies/zones.py measures it. Defaulted
                             # so no existing construction changes.
    poi: bool = False        # the raid landed inside an aligned order block
                             # or fair value gap on POI_INTERVAL. Set by the
                             # scanner, never by the engine. See daily_zones,
                             # whose name is older than its behaviour.
    poi_known: bool = True   # False when the context bars could not be read,
                             # so `poi` is a default rather than an answer. The
                             # POI gate sends on unknown rather than muting.
    di_dir: int = 0          # DI+/DI- direction on DI_INTERVAL at detection:
                             # +1 up, -1 down, 0 unknown. Set by the scanner,
                             # like trend_dir — the engine has no HTF bars.
    rsi_ext: float = 0.0     # RSI stretch at the raid, in the trade's favour.
                             # See rsi_extension.
    btc_dir: int = 0         # BTC's own trend at detection, +1 up / -1 down.
                             # Market context, set by the scanner. Never
                             # suppresses anything — see trend.btc_at.
    also_early: int = 0      # bars from raid to gap, when this exact trade
                             # also fired as an Early on the same bar. Set by
                             # the scanner when it pairs the two, so one trade
                             # is one message. 0 means it did not.

    @property
    def detected_time(self) -> int:
        """
        Bar on which this setup first became knowable — the one an alert can
        honestly be timed from, and the earliest bar a person could act on.

        Not the same as the shift bar. scan_leg searches backwards from the
        grab, so a gap that formed BEFORE the shift is picked up the instant
        the shift confirms (fvg_time < mss_time, detected at the shift). And
        when no gap exists yet, the engine retries each bar for
        max_bars_after_mss, so the gap can arrive well after the shift
        (fvg_time > mss_time, detected at the gap).

        Either way it is the later of the two, because a setup needs both.
        Freshness, the age shown on the alert, and the bar outcome tracking
        starts scoring from all measure from here; measuring from the shift
        instead silently drops the slow-gap setups and back-dates the rest.
        """
        return max(self.mss_time, self.fvg_time)


@dataclass
class Early:
    """
    Sweep -> first imbalance, with NO structure shift.

    A deliberately more aggressive pattern than Setup. The engine's normal
    path waits for the shift to confirm the reversal, which is the safer
    read and also the slow one: by the time the shift prints, the move it
    confirms has already happened, and the gap left behind is often far from
    price. This fires on the first imbalance inside cfg.early_max_bars of the
    raid instead, entering at the gap edge with the stop just beyond the raid
    extreme.

    The trade-off is not subtle. There is no confirmation that the sweep
    reversed anything, so a pool taken in a trend keeps going and the signal
    is simply wrong. What buys that back is geometry: the stop sits at the
    raid extreme, a few candles away rather than a whole leg, so risk per
    signal is small and the winners are worth many multiples of it.

    Emitted alongside Setup, never instead of it. The two are independent
    reads of the same sweep and both may fire.
    """
    symbol: str
    is_long: bool          # a swept low implies a long, and vice versa
    src: str
    level: float           # the pool that was taken
    entry: float           # proximal edge of the gap
    stop: float            # beyond the raid extreme
    risk: float
    sweep_bar: int
    sweep_time: int
    grab_time: int         # the trailed raid extreme the stop is measured from
    fvg_bar: int
    fvg_time: int          # the bar the gap completed on — this IS the signal
    anchor_time: int
    pivots: int
    bars_from_sweep: int
    pools: int = 0         # how many separate pools raided into this one gap.
                           # Set when duplicates are collapsed, not by detection.
    confluence: int = 0    # order-block agreement only, 0-1: with no shift
                           # there is no breaker to agree with.
    trend_dir: int = 0
    tf: str = ""              # as on Setup
    poi: bool = False         # as on Setup
    poi_known: bool = True    # as on Setup
    di_dir: int = 0           # as on Setup
    rsi_ext: float = 0.0      # as on Setup
    btc_dir: int = 0          # as on Setup
    last_price: float = 0.0   # display only, as on Setup

    @property
    def detected_time(self) -> int:
        """The gap bar. Nothing else has to happen for this signal to exist,
        so unlike Setup there is no second condition to take the later of."""
        return self.fvg_time


@dataclass
class Sweep:
    """
    The liquidity grab on its own — the X on the chart, on a closed bar.

    Emitted the moment a pool is taken out, long before the engine knows
    whether a structure shift and an FVG will follow. Most sweeps never
    become setups; this is a heads-up to go and watch the chart, not a
    signal.
    """
    symbol: str
    is_high: bool          # a swept high implies a short bias, and vice versa
    src: str
    level: float
    sweep_bar: int
    sweep_time: int
    struct_level: float    # price must break this for the shift to confirm
    sweep_extreme: float
    anchor_time: int
    pivots: int
    pools: int = 0         # how many pools this one bar took out. Set when
                           # duplicates are collapsed, not by detection.
    rvol: float = 0.0      # raid-bar turnover against the median of the 50
                           # bars before it. 0 means it could not be computed
                           # (too early in the series), which is NOT the same
                           # as a quiet raid and must not gate like one.
    trend_dir: int = 0     # as above
    tf: str = ""           # as above
    poi: bool = False      # as above
    poi_known: bool = True # as above
    di_dir: int = 0        # as above
    rsi_ext: float = 0.0   # as above
    btc_dir: int = 0       # as above
    last_price: float = 0.0   # display only, as above


def rma(values: list[float], length: int) -> list[float]:
    """Wilder's smoothing, as used by ta.atr."""
    out: list[float] = []
    acc = 0.0
    for i, v in enumerate(values):
        if i < length:
            acc += v
            out.append(acc / (i + 1))
        else:
            out.append((out[-1] * (length - 1) + v) / length)
    return out


def atr_series(cs: list[Candle], length: int) -> list[float]:
    tr = []
    for i, c in enumerate(cs):
        if i == 0:
            tr.append(c.h - c.l)
        else:
            pc = cs[i - 1].c
            tr.append(max(c.h - c.l, abs(c.h - pc), abs(c.l - pc)))
    return rma(tr, length)


def rsi_series(cs: list[Candle], length: int = 14) -> list[float]:
    """Wilder's RSI, one value per bar. Pure, like everything else here."""
    up, dn = [0.0], [0.0]
    for i in range(1, len(cs)):
        d = cs[i].c - cs[i - 1].c
        up.append(max(d, 0.0))
        dn.append(max(-d, 0.0))
    au, ad = rma(up, length), rma(dn, length)
    out = []
    for u, d in zip(au, ad):
        out.append(100.0 if d == 0 and u > 0 else
                   50.0 if d == 0 else
                   100.0 - 100.0 / (1.0 + u / d))
    return out


def rsi_extension(rsi: float, is_long: bool) -> float:
    """
    How stretched RSI is IN THE TRADE'S FAVOUR at the raid: oversold for a
    long, overbought for a short. Positive means stretched the right way.

    The zero point is RSI 50 and nothing else. A median split of this sample
    put the cut at +7.00 and measured stronger (+3.1 SE against +2.1), which
    is exactly why it is not used — that threshold was read off the same data
    it would then be judged on.
    """
    return (50.0 - rsi) if is_long else (rsi - 50.0)


def is_pivot_high(cs: list[Candle], i: int, left: int, right: int) -> bool:
    if i - left < 0 or i + right >= len(cs):
        return False
    h = cs[i].h
    for j in range(i - left, i):
        if cs[j].h >= h:
            return False
    for j in range(i + 1, i + right + 1):
        if cs[j].h >= h:
            return False
    return True


def is_pivot_low(cs: list[Candle], i: int, left: int, right: int) -> bool:
    if i - left < 0 or i + right >= len(cs):
        return False
    l = cs[i].l
    for j in range(i - left, i):
        if cs[j].l <= l:
            return False
    for j in range(i + 1, i + right + 1):
        if cs[j].l <= l:
            return False
    return True


def entry_of(is_long: bool, top: float, bot: float, mode: str) -> float:
    if mode == "mid":
        return (top + bot) / 2.0
    if mode == "distal":
        return bot if is_long else top
    return top if is_long else bot


# The point of interest. A raid that lands inside a recent order block or fair
# value gap on POI_INTERVAL is the largest single separation this project has
# measured, and the only filter to pass a pre-registered held-out test on
# symbols it was not found on. See MEASUREMENTS.md, "The multi-timeframe model".
#
# ZONES EXPIRE. Without an age limit this flags 90% of raids and means nothing:
# a year of daily bars accumulates enough blocks and gaps to cover most of the
# price range. Thirty days is what was measured, and it is a real parameter, not
# a rounding — the unconstrained version pointed the WRONG way.
POI_MAX_AGE_BARS = 30


def daily_zones(cs: list[Candle], atr: list[float]) -> list[tuple]:
    """(formed_at, is_bull, lo, hi) for every order block and gap in `cs`.

    NOT DAILY, DESPITE THE NAME. The name is from when the only caller passed
    daily candles; it reads whatever series it is given, and trend.poi_at has
    passed POI_INTERVAL bars -- Hour8 by default -- since 9 Sep.

    formed_at is the bar the zone COMPLETED on, not the bar it started from.
    A three-candle gap is not knowable until the third candle closes, and an
    order block is not identifiable until the displacement that names it has
    printed; dating either one earlier would let a signal react to a zone that
    did not yet exist.
    """
    out = []
    for j in range(2, len(cs)):
        a = atr[j] if j < len(atr) else 0.0
        if a <= 0:
            continue
        if cs[j].l > cs[j - 2].h:
            out.append((cs[j].t, True, cs[j - 2].h, cs[j].l))
        elif cs[j].h < cs[j - 2].l:
            out.append((cs[j].t, False, cs[j].h, cs[j - 2].l))
        # Order block: the last opposite-closing candle before a displacement
        # of more than one ATR.
        if cs[j].c - cs[j].o > a and cs[j - 1].c < cs[j - 1].o:
            out.append((cs[j].t, True, cs[j - 1].l, cs[j - 1].h))
        elif cs[j].o - cs[j].c > a and cs[j - 1].c > cs[j - 1].o:
            out.append((cs[j].t, False, cs[j - 1].l, cs[j - 1].h))
    return out


def in_zone(zones, when: int, price: float, is_long: bool, step: int) -> bool:
    """Did `price` at `when` sit inside an aligned zone still inside its life?

    `price` is the STOP, which sits just beyond the raid extreme — the raid is
    what has to land in the zone, not the entry, and the stop is the closest
    thing to the extreme that every signal type carries.
    """
    # t + step, NOT t. `daily_zones` dates a zone by the bar that COMPLETED
    # it, and that bar is not knowable until it closes one step later. Live
    # this changed nothing — fetch_candles drops the forming bar, so the newest
    # zone the bot can see already closed — but the research path fed the full
    # daily history in and the same comparison there let a signal match a zone
    # built from the candle it was sitting inside. Correct in principle here,
    # and it keeps the two paths honest about the same rule.
    for t, bull, lo, hi in zones:
        if (t + step <= when and bull == is_long and lo <= price <= hi
                and when - t <= POI_MAX_AGE_BARS * step):
            return True
    return False


def last_opposing(cs: list[Candle], before: int, is_bull: bool,
                  max_back: int = 20) -> int:
    """
    Index of the last candle closing against the move, scanning back from
    `before`. For a bullish leg that is the last down-close candle — the
    order block. -1 if none within max_back.
    """
    for k in range(before, max(-1, before - max_back), -1):
        if is_bull and cs[k].c < cs[k].o:
            return k
        if not is_bull and cs[k].c > cs[k].o:
            return k
    return -1


def ranges_overlap(a1: float, a2: float, b1: float, b2: float) -> bool:
    lo1, hi1 = min(a1, a2), max(a1, a2)
    lo2, hi2 = min(b1, b2), max(b1, b2)
    return not (lo1 >= hi2 or hi1 <= lo2)


def breaker_of(cs: list[Candle], grab_bar: int, mss_bar: int,
               is_bull: bool, max_back: int = 20) -> int:
    """
    The block price broke THROUGH — a breaker in the sense ICT means.

    A breaker is an order block on the OPPOSITE side that failed. For a long,
    the decline into the raid was loaded by the last UP-close candle before it;
    when the shift breaks back above that candle, it flips from resistance to
    support. That makes it a different candle from the order block by
    construction, which is the whole point — two independent votes rather than
    one counted twice.

    The previous rule looked for the SAME polarity as the order block, anchored
    near the break extreme, and landed on the identical candle 60% of the time
    over 244 setups. So "2 of 2 zones agree" frequently meant one candle agreed
    with itself, and the chart drew two lines on top of each other.

    -1 when no opposite-polarity candle is found within max_back, or when the
    shift never actually traded through it — an unbroken block is not a
    breaker, it is just an order block facing the other way.
    """
    if not (0 <= grab_bar < mss_bar):
        return -1
    for k in range(grab_bar, max(-1, grab_bar - max_back), -1):
        if (cs[k].c > cs[k].o) if is_bull else (cs[k].c < cs[k].o):
            seg = range(k, mss_bar + 1)
            broke = (max(cs[i].h for i in seg) > cs[k].h if is_bull
                     else min(cs[i].l for i in seg) < cs[k].l)
            return k if broke else -1
    return -1


def confluence_of(cs: list[Candle], fvg_bar: int, is_bull: bool,
                  grab_bar: int = -1, mss_bar: int = -1) -> int:
    """
    How many of {order block, breaker} sit in the same price area as the gap.

    Observation only — it never changes which setups exist or what they enter
    at. Both zones were separately tested as ALTERNATIVE entries and both came
    back flat; the open question is whether their AGREEMENT with the gap grades
    a setup, which is a different thing and is what this counts.

      order block  the last opposing candle before the impulse that made the gap
      breaker      the OPPOSITE-side block the shift broke through — see
                   breaker_of. Needs an MSS, so an early signal scores 0-1.

    Measured, 1982 setups: 0 of 2 scored +0.043, 2 of 2 scored +0.106 — but
    +1.4 SE, and NOT monotonic (1 of 2 came in below 0 of 2). Not a finding.
    Recorded on every alert so /stats can settle it out of sample.
    """
    if fvg_bar < 2 or fvg_bar >= len(cs):
        return 0
    top, bot = ((cs[fvg_bar].l, cs[fvg_bar - 2].h) if is_bull
                else (cs[fvg_bar - 2].l, cs[fvg_bar].h))
    n = 0
    ob = last_opposing(cs, fvg_bar - 1, is_bull)
    if ob >= 0 and ranges_overlap(top, bot, cs[ob].h, cs[ob].l):
        n += 1
    brk = breaker_of(cs, grab_bar, mss_bar, is_bull)
    if brk >= 0 and ranges_overlap(top, bot, cs[brk].h, cs[brk].l):
        n += 1
    return n


# Grade bands, read off measured cells rather than invented. Rebuilt on the
# two axes that survived out-of-sample splits, replacing the SuperTrend x
# confluence ladder that preceded them.
#
#   DI      daily DI+ vs DI- direction. +0.222 R, +4.7 SE on 1185 confirmed
#           setups, and it replicates on every split: symbols A +2.9 SE,
#           symbols B +3.8 SE, first half of the window +4.0, second +2.6.
#           Stronger than the daily SuperTrend it displaces (+3.1 SE), and not
#           a restatement of it — the two agree on only 78% of signals and DI
#           still separates after conditioning on it.
#
#   RSI     stretch at the raid, in the trade's favour, split at RSI 50. Only
#           used INSIDE the counter-DI band, because that is the only place it
#           does anything: +2.1 SE there, -0.1 SE where DI already agrees.
#           Splitting the DI-with band by RSI would be inventing a step the
#           data says is not there.
#
# Measured bands, 50 symbols, 41.6 days, 1R target:
#
#     band     n    fill   win% of fills   R per setup
#     A      587     70%       61% ± 2     +0.158 ± 0.033
#     B      486     74%       47% ± 3     -0.030 ± 0.037
#     C      112     71%       35% ± 5     -0.206 ± 0.076
#
# Three bands, not five. The win rate ladder is clean and monotonic, and every
# step is a comparison that survived both splits. Confluence is still recorded
# on every signal but no longer sets the letter: it measured +1.4 SE and never
# replicated, so it was decorating a letter with a number that did not hold.
#
# READ THE NUMBERS AS HISTORY, NOT AS A FORECAST. They come from one 41.6-day
# window; this project has watched the LEVEL of an effect move from -0.05 to
# +0.32 across windows while the separation between bands held. The ordering
# is the finding. The percentages are context for it.
# THE GRADE, REBUILT — see MEASUREMENTS.md, "The cell table".
#
# The previous version graded on daily DI with an RSI tiebreak. It was the best
# available when it was written and it is now two findings out of date: the
# POI turned out to be a larger separation than DI, and the two are
# MULTIPLICATIVE rather than additive, which no letter built on one axis can
# express.
#
#   POI    the raid landed inside an order block or fair value gap on
#          POI_INTERVAL, less than POI_MAX_AGE_BARS bars of that timeframe
#          old. Measured on DAILY zones with a thirty-day life; it has read
#          Hour8 with a ten-day life since 9 Sep, which poi_tf.py finds
#          indistinguishable on Min60 and which nothing has checked on
#          Min30. Discovered on 14 symbols, held out on 9 it had never seen,
#          and it then improved every arm of two other entry models built on a
#          different premise. The only filter here to survive a pre-registered
#          held-out test.
#   TREND  the SuperTrend and the DI, each on its own interval, agree with
#          the trade. Both Hour8 since 9 Sep. Stricter
#          than the old DI-alone reading and measured on the same cells.
#
# Measured, 23 symbols, 41 days, 2R target, maker/taker fees, from the FILL bar:
#
#     kind        POI  trend     n    fill   win     R per signal
#     confirmed   yes  yes      43     67%   76%     +0.822 ± 0.187   <- A
#     confirmed   no   yes      66     73%   46%     +0.206 ± 0.157   <- B
#     early       yes  yes     214     78%   46%     +0.188 ± 0.087   <- B
#     confirmed   yes  no       38     61%   43%     +0.105 ± 0.189   <- C
#     confirmed   no   no      100     72%   44%     +0.082 ± 0.119   <- C
#     early       no   yes     331     80%   40%     +0.048 ± 0.070   <- C
#     early       yes  no      228     78%   38%     +0.018 ± 0.084   <- C
#     early       no   no      624     80%   36%     -0.050 ± 0.049   <- D
#
# Four bands now, and D is new and deliberate. It is the only cell measuring
# NEGATIVE, and it is 38% of everything the bot sends. A letter that never says
# "this one is worse than not trading" was hiding the most useful thing it knew.
#
# The bands are cut on measured R, not on a points system. A points scheme —
# two for confirmed, one each for POI and trend — would put confirmed-with-POI
# and confirmed-with-trend in the same band, and they measure +0.105 against
# +0.206. The table is the finding; a formula would be a tidier lie.
#
# READ THE NUMBERS AS HISTORY, NOT AS A FORECAST. One 41-day window. This
# project has watched the LEVEL of an effect move from -0.05 to +0.32 across
# windows while the separation between bands held. The ordering is the finding.
# Band A rests on 43 signals and has never been held out on its own.
# One word for a timeframe, in prose register rather than the chip register
# telegram.TF_LABEL uses -- "daily", not "1D".
_TF_WORD = {"Day1": "daily", "Hour8": "8h", "Hour4": "4h", "Min60": "1h",
            "Min30": "30m", "Min15": "15m"}


def tf_word(interval: str) -> str:
    return _TF_WORD.get(interval, interval)


# BOTH HALVES OF THE GRADE NAME THEIR OWN TIMEFRAME, AND THE POI HALF DID NOT
# UNTIL 11 SEP. The trend half was made dynamic when the default first moved,
# with the note below. The POI half was left as the literal string "daily POI"
# -- and on 9 Sep it became wrong in exactly the way that note predicted:
# poi_at reads POI_INTERVAL, which defaults to TREND_INTERVAL, which moved to
# Hour8. For two days every alert, /help and /stats said "daily POI" about an
# 8h filter. Nothing behaved wrongly; every description of it did.
#
# The grade's trend half is whatever TREND_INTERVAL says it is. It used to be
# the literal word "daily" in eight places, which was correct only for as long
# as the default never moved -- and the moment it did, every alert would have
# named a timeframe the bot was not reading.
_TL = tf_word(TREND_INTERVAL)
_POI = f"{tf_word(POI_INTERVAL)} POI"

# (letter, why) keyed by (early?, in a POI?, trend agrees?)
GRADES = {
    (False, True,  True):  ("A", f"{_POI} · {_TL} trend agrees"),
    (False, False, True):  ("B", f"{_TL} trend agrees · no POI"),
    (True,  True,  True):  ("B", f"{_POI} · {_TL} trend agrees"),
    (False, True,  False): ("C", f"{_POI} · against the {_TL} trend"),
    (False, False, False): ("C", f"no POI · against the {_TL} trend"),
    (True,  False, True):  ("C", f"{_TL} trend agrees · no POI"),
    (True,  True,  False): ("C", f"{_POI} · against the {_TL} trend"),
    (True,  False, False): ("D", f"no POI · against the {_TL} trend"),
}

# Historical rate for each band: (signals, fill %, win % of fills, R, SE).
# Shown on the alert so a letter is never a bare assertion, and replaced by the
# live figure from /stats as soon as a band has enough settled rows. Bands
# pool the cells above, so these are the pooled figures, not one cell's.
BAND_STATS = {
    "A": (43, 67, 76, +0.822, 0.187),
    "B": (66, 73, 46, +0.206, 0.157),
    "C": (138, 68, 44, +0.089, 0.100),
    "D": (0, 0, 0, 0.0, 0.0),          # no confirmed signal can reach D
}

# The same bands on early signals. Unlike the old table these are NOT flat:
# the POI is the first thing ever measured to sort early signals, and it sorts
# them from -0.050 to +0.188. That is the single biggest change here — an early
# alert's letter used to mean almost nothing and now carries most of what is
# known about it.
EARLY_BAND_STATS = {
    "A": (0, 0, 0, 0.0, 0.0),          # no early signal can reach A
    "B": (214, 78, 46, +0.188, 0.087),
    "C": (559, 79, 39, +0.036, 0.054),
    "D": (624, 80, 36, -0.050, 0.049),
}


def grade_of(is_early: bool, poi: bool, trend_dir: int, is_long: bool,
             di_dir: int = 0) -> tuple[str, str]:
    """
    (letter, why) for one signal. Presentation only — nothing decides on it,
    and no signal is suppressed by it.

    "Trend agrees" means the SuperTrend AND the DI both agree, each read on
    its configured interval (TREND_INTERVAL and DI_INTERVAL, both Hour8 since
    9 Sep -- they are separate keys and must move together),
    which is how the cells were measured. When either reading is missing the
    trend cannot agree, so the signal grades as though it did not — that is
    the conservative direction, and unlike the old "?" it still gives the POI
    axis somewhere to show up.
    """
    trend_ok = bool(trend_dir) and (trend_dir > 0) == is_long
    if di_dir:
        trend_ok = trend_ok and (di_dir > 0) == is_long
    return GRADES[(bool(is_early), bool(poi), trend_ok)]


def band_stats(letter: str, kind_early: bool = False):
    """Historical (n, fill %, win %, R, SE) for a band, or None."""
    table = EARLY_BAND_STATS if kind_early else BAND_STATS
    return table.get(letter)


# How often a raid goes on to produce a CONFIRMED setup, by how far away the
# level price must break sits at the moment of the raid. (upper bound %, rate,
# n), measured on 23 symbols over 41.6 days.
#
# The gradient is steep and it is not a subtlety: 37% down to 3%. A raid whose
# shift level is 6% away is not a weaker version of a good raid, it is a raid
# that will almost certainly never confirm, because confirming means price
# travelling 6% in the opposite direction inside the grab window.
#
# This is mostly a story about Day pools. The engine keeps EVERY unswept
# previous-day high and low, not just yesterday's, so a level can be days old
# by the time it is taken — and its shift level is the opposing extreme
# measured all the way back from the bar that set it, which drifts further
# away every day the level survives. Day raids: median shift distance 4.56%
# and 6.4% convert, against Pivot's 2.59% and 19.5%.
#
# It is deliberately NOT a filter. Early signals off the same raids show no
# gradient at all (+0.211 / +0.206 / +0.194 / +0.104 / +0.222 R across the
# same buckets), so a far shift level says the CONFIRMED path is unlikely and
# says nothing against the early one. Suppressing these raids would cost real
# early signals to remove a mark that is merely uninformative.
# Re-measured 8 Sep on the live 60-symbol universe, Min30, 8984 raids —
# against 3702 on 23 hand-picked symbols before. Every band converts LESS
# often than the old table said (37/25/17/7/3 became 24/13/6/2/1). The shape
# is identical and the gradient is if anything steeper; the level moved
# because the wider universe is thinner, which is the same finding the POI
# work produced from the other direction.
SHIFT_ODDS = ((1.0, 24, 652), (2.0, 13, 1962), (4.0, 6, 2807),
              (8.0, 2, 2155), (float("inf"), 1, 1408))


def shift_odds(extreme: float, struct_level: float):
    """(distance %, historical conversion %, n) for one raid, or None.

    Distance is measured from the raid's extreme to the level the shift needs,
    which is the move price still has to make — not from the pool, which it
    has already taken.
    """
    if not extreme:
        return None
    dist = abs(extreme - struct_level) / extreme * 100
    for upper, rate, n in SHIFT_ODDS:
        if dist < upper:
            return dist, rate, n
    return None


# WATCH_MAX_DIST (config, default 3.0) is the one number behind the verdict,
# and the one number behind the filter — riptide.scanner sends only sweeps
# this returns True for, so the label and the gate cannot drift apart.
#
# A sweep answers exactly one question: is this chart worth looking at. So it
# gets one answer, yes or no, rather than a tier the reader has to interpret.
# The cut is where the value stops arriving. Measured over 5098 raids that
# landed in a POI, by how far the shift level still was:
#
#     band     share of raids   convert   total R produced
#     <1%            8%          22.7%         +15.9
#     1-2%          22%          14.8%         +16.5
#     2-3%          18%           6.6%         +10.8
#     3-4%          13%           3.1%          +0.6
#     4-6%          14%           1.8%          +2.9
#     >6%           25%           0.7%          +3.0
#
#     cumulative:  under 2% = 30% of raids, 65% of the R
#                  under 3% = 48% of raids, 87% of the R   <- the knee
#                  under 4% = 61% of raids, 88% of the R
#
# Three per cent is where the curve flattens: the next band adds 13% more
# raids and 1% more value. Half the raids carry seven eighths of everything
# that follows from any of them.
def rvol_at(cs, bar: int, lookback: int = 50) -> float:
    """Raid-bar turnover against the MEDIAN of the `lookback` bars before it.

    Median rather than mean, because volume is heavy-tailed: one spike in the
    window drags a mean up and makes every later bar look quiet by comparison.
    This is `context.py`'s definition, kept identical so the live gate and the
    measurement that justifies it are the same quantity.

    Returns 0.0 when there is not enough history — a value that means UNKNOWN,
    and which sweep_worth is careful not to treat as quiet.
    """
    lo = bar - lookback
    if lo < 0 or bar >= len(cs):
        return 0.0
    prev = [cs[k].v for k in range(lo, bar) if cs[k].v > 0]
    if len(prev) < lookback // 2:
        return 0.0
    med = statistics.median(prev)
    return (cs[bar].v / med) if med > 0 else 0.0


def sweep_worth(extreme: float, struct_level: float, poi: bool = True,
                rvol: float = 0.0) -> bool:
    """Is this raid worth opening the chart for? Yes or no, nothing else.

    BOTH measured axes have to agree, and they are independent — see
    MEASUREMENTS.md, "Sweeps in a POI":

      distance  how likely a setup is to appear at all. Under 3% away, 7-23%
                of raids convert; beyond it, 1-3%.
      POI       whether that setup is worth taking when it comes. Raids inside
                a POI zone produce setups worth +0.141 R; those outside
                produce -0.055.
      VOLUME    how likely a setup is to appear at all, again — and far more
                strongly than distance does.

    A near raid outside a zone converts often into something that loses money,
    and a far raid inside one almost never converts at all. Neither is worth a
    look, which is why this is an AND rather than a score.

    THE VOLUME TEST IS THE STRONGEST OF THE THREE AND WAS THE LAST TO ARRIVE.
    `research/studies/sweep_vol_gate.py`, 9419 sweeps over 60 symbols,
    conversion by raid-bar volume quintile:

        Q1  rvol < 0.98    14.3% converted
        Q2  0.98 - 1.55     9.7%
        Q3  1.55 - 2.37     6.1%
        Q4  2.37 - 4.12     4.6%
        Q5  rvol > 4.12     2.4%
        Q1 minus Q5  +11.9pp, +13.5 SE, monotone

    which reproduces `context.py`'s +15.6 SE on an independent pass. It
    INVERTS the folk premise: a liquidity grab is supposed to print a volume
    spike, and the raids that actually reverse are the QUIET ones. Volume
    surging through a level is a breakout, and the classic grab that snaps
    back drifts through on thin participation.

    Head to head with the distance rule it had to earn its place against:

        every sweep                        7.4% convert   3.8 per symbol-day
        distance only (the old live rule) 13.3%           1.7
        VOLUME only                       14.3%           0.8
        both                              18.0%           0.5

    Volume alone beats distance on BOTH axes — more conversion at half the
    messages — and the two together are better than either. So this is an AND
    of three now.

    NOTHING HERE CLAIMS THE SURVIVORS ARE BETTER TRADES. `context.py` measured
    raid volume against R on the setups that do follow and found nothing
    (+0.7 SE). Conversion and expectancy are different questions; volume is
    enormous on one and silent on the other, and a heads-up is asked only the
    first. The POI term is what speaks to the second.

    rvol == 0.0 means UNKNOWN — too early in the series to compute — and is
    deliberately allowed through rather than treated as quiet. Muting a symbol
    because its history is short is the wrong failure for an alerting service,
    and it is the same choice poi_known already makes.
    """
    odds = shift_odds(extreme, struct_level)
    quiet = (rvol <= 0.0) or (rvol < MAX_SWEEP_RVOL)
    return (bool(poi) and quiet
            and odds is not None and odds[0] < WATCH_MAX_DIST)


def collapse(items: list, key, better) -> list:
    """
    One entry per event. `key` says what makes two items the same event;
    `better(new, cur)` says which to keep. The kept item's `pools` counts the
    whole group, so nothing is silently discarded — the count survives.

    Only ever merges items that are the same TRADE: same bar, same direction,
    and therefore the same entry. What differs between members is which pool
    was named and how far back its raid extreme sat, so the group collapses to
    the tightest stop and the pool count.
    """
    if len(items) < 2:
        return items
    best: dict = {}
    for it in items:
        k = key(it)
        cur = best.get(k)
        if cur is None or better(it, cur):
            if cur is not None:
                it.pools = cur.pools
            best[k] = it
        best[k].pools += 1
    return list(best.values())


def run_engine(symbol: str, cs: list[Candle], cfg: Cfg = CFG,
               sweeps_out: list | None = None,
               early_out: list | None = None,
               clusters_out: list | None = None,
               collapse_dupes: bool = True) -> list[Setup]:
    """
    Single pass over closed candles, mirroring the Pine bar loop. Returns every
    setup found in the window; the caller decides which are recent enough to
    send.

    Pass a list as sweeps_out to also collect every liquidity grab, or
    early_out to collect the no-shift entries described on Early. Both are
    pure observation: they append to a list and change no decision, so the
    setups returned are identical whether or not either is supplied.

    clusters_out hands back every pool the engine built, in the same spirit.
    It exists because a pool that reached min_pivots is exactly what the Pine
    draws a diamond for, so this is the only way to count the markers a chart
    will carry without reading them off a screenshot.
    """
    n = len(cs)
    if n < cfg.atr_len + cfg.pivot_left + cfg.pivot_right + 10:
        return []

    atr = atr_series(cs, cfg.atr_len)
    # RSI at the raid feeds the grade, never a decision. One pass, reused.
    rsi = rsi_series(cs)
    clusters: list[Cluster] = []
    setups: list[Setup] = []
    last_mss = {True: -10 ** 9, False: -10 ** 9}   # keyed by is_high

    # previous day / week trackers: extreme, its bar, and the opposing extreme
    # since that bar (which is the structure level for that level).
    def new_tracker(i):
        return {"hi": cs[i].h, "hi_bar": i, "lo": cs[i].l, "lo_bar": i,
                "min_since_hi": cs[i].l, "min_bar": i,
                "max_since_lo": cs[i].h, "max_bar": i}

    day = new_tracker(0)
    week = new_tracker(0)

    def inject(is_high, price, anchor, opp, opp_bar, src, i):
        c = Cluster(is_high=is_high, level=price, oldest_bar=anchor,
                    created_bar=i, src=src, active=True)
        c.run_min = opp if is_high else price
        c.run_max = price if is_high else opp
        c.run_min_bar = opp_bar if is_high else anchor
        c.run_max_bar = anchor if is_high else opp_bar
        clusters.append(c)

    def close_period(tr, src, i):
        inject(True, tr["hi"], tr["hi_bar"], tr["min_since_hi"], tr["min_bar"], src, i)
        inject(False, tr["lo"], tr["lo_bar"], tr["max_since_lo"], tr["max_bar"], src, i)

    def track(tr, i):
        if cs[i].h > tr["hi"]:
            tr["hi"], tr["hi_bar"] = cs[i].h, i
            tr["min_since_hi"], tr["min_bar"] = cs[i].l, i
        elif cs[i].l < tr["min_since_hi"]:
            tr["min_since_hi"], tr["min_bar"] = cs[i].l, i
        if cs[i].l < tr["lo"]:
            tr["lo"], tr["lo_bar"] = cs[i].l, i
            tr["max_since_lo"], tr["max_bar"] = cs[i].h, i
        elif cs[i].h > tr["max_since_lo"]:
            tr["max_since_lo"], tr["max_bar"] = cs[i].h, i

    def register_pivot(is_high, price, pbar, i, a):
        tol = a * cfg.tol_atr
        best, target = None, None
        for c in clusters:
            if c.src != "Pivot" or c.expired or c.mss:
                continue
            if c.swept and not cfg.allow_join_after_sweep:
                continue
            if c.is_high != is_high:
                continue
            d = min(abs(p - price) for p in c.prices) if c.prices else abs(c.level - price)
            if d > tol:
                continue
            lo = min(c.prices + [price])
            hi = max(c.prices + [price])
            if hi - lo > a * cfg.max_cluster_span_atr:
                continue
            ext = max(c.prices) if is_high else min(c.prices)
            allow = a * cfg.max_overshoot_atr
            if is_high and price > ext + allow:
                continue
            if not is_high and price < ext - allow:
                continue
            if pbar - c.oldest_bar > cfg.max_pool_span_bars:
                continue
            if best is None or d < best:
                best, target = d, c
        if target is None:
            c = Cluster(is_high=is_high, level=price, oldest_bar=pbar, created_bar=i)
            c.prices, c.bars = [price], [pbar]
            lo = max(0, i - cfg.pivot_right)
            c.run_min = min(x.l for x in cs[lo:i + 1])
            c.run_max = max(x.h for x in cs[lo:i + 1])
            c.run_min_bar = min(range(lo, i + 1), key=lambda k: cs[k].l)
            c.run_max_bar = max(range(lo, i + 1), key=lambda k: cs[k].h)
            clusters.append(c)
        else:
            target.prices.append(price)
            target.bars.append(pbar)
            target.level = sum(target.prices) / len(target.prices)
            if not target.active and len(target.prices) >= cfg.min_pivots:
                target.active = True

    def scan_leg(c, frm, to, i, a):
        """Newest window first; returns (entry, stop, fvg_bar) or None."""
        for off in range(0, min(to - frm, 120) + 1):
            j = to - off
            if j - 2 < 0 or j < frm:
                break
            is_bull = not c.is_high
            if is_bull:
                top, bot = cs[j].l, cs[j - 2].h
                ok = cs[j].l > cs[j - 2].h
            else:
                top, bot = cs[j - 2].l, cs[j].h
                ok = cs[j].h < cs[j - 2].l
            if not ok or top - bot < a * cfg.min_fvg_atr:
                continue
            if cfg.max_fvg_atr > 0 and top - bot > a * cfg.max_fvg_atr:
                continue
            ent = entry_of(is_bull, top, bot, cfg.entry_mode)
            sl = (c.grab_low - a * cfg.sl_buffer_atr) if is_bull else \
                 (c.grab_high + a * cfg.sl_buffer_atr)
            if cfg.max_risk_atr > 0 and abs(ent - sl) > a * cfg.max_risk_atr:
                continue
            return ent, sl, j
        return None

    start = cfg.atr_len
    for i in range(start, n):
        a = atr[i]
        if a <= 0:
            continue

        # period levels
        d_prev = datetime.fromtimestamp(cs[i - 1].t, timezone.utc)
        d_now = datetime.fromtimestamp(cs[i].t, timezone.utc)
        if cfg.use_daily and d_now.date() != d_prev.date():
            close_period(day, "Day", i)
            day = new_tracker(i)
        elif cfg.use_daily:
            track(day, i)
        if cfg.use_weekly and d_now.isocalendar()[1] != d_prev.isocalendar()[1]:
            close_period(week, "Week", i)
            week = new_tracker(i)
        elif cfg.use_weekly:
            track(week, i)

        # pivots confirmed on this bar
        if cfg.use_pivot:
            pb = i - cfg.pivot_right
            if pb >= 0:
                if is_pivot_high(cs, pb, cfg.pivot_left, cfg.pivot_right):
                    register_pivot(True, cs[pb].h, pb, i, a)
                if is_pivot_low(cs, pb, cfg.pivot_left, cfg.pivot_right):
                    register_pivot(False, cs[pb].l, pb, i, a)

        for c in clusters:
            if c.expired or c.done:
                continue

            if not c.swept:
                if cs[i].l < c.run_min:
                    c.run_min, c.run_min_bar = cs[i].l, i
                if cs[i].h > c.run_max:
                    c.run_max, c.run_max_bar = cs[i].h, i

            was_active, was_swept, was_mss = c.active, c.swept, c.mss

            if not was_active:
                buf = a * cfg.pending_invalidate_atr
                ran = cs[i].h > c.level + buf if c.is_high else cs[i].l < c.level - buf
                if ran or i - c.created_bar > cfg.pending_expiry_bars:
                    c.expired = True

            if was_active and not was_swept and not c.expired:
                b = a * cfg.grab_buffer_atr
                hit = cs[i].h > c.level + b if c.is_high else cs[i].l < c.level - b
                if hit:
                    c.swept = True
                    c.sweep_bar = c.grab_bar = i
                    c.grab_high, c.grab_low, c.grab_close = cs[i].h, cs[i].l, cs[i].c
                    c.struct_level = c.run_min if c.is_high else c.run_max
                    if sweeps_out is not None:
                        sweeps_out.append(Sweep(
                            symbol=symbol, is_high=c.is_high, src=c.src,
                            level=c.level, sweep_bar=i, sweep_time=cs[i].t,
                            struct_level=c.struct_level,
                            sweep_extreme=cs[i].h if c.is_high else cs[i].l,
                            rvol=rvol_at(cs, i),
                            anchor_time=cs[c.oldest_bar].t,
                            pivots=len(c.prices) or 1,
                            rsi_ext=rsi_extension(rsi[i], not c.is_high)))

            if was_swept and not was_mss and not c.expired:
                if i - c.sweep_bar > cfg.max_bars_after_grab:
                    c.expired = True
                else:
                    if cfg.trail_grab_extreme:
                        if c.is_high and cs[i].h > c.grab_high:
                            c.grab_bar, c.grab_high, c.grab_low = i, cs[i].h, cs[i].l
                            c.grab_close = cs[i].c
                        if not c.is_high and cs[i].l < c.grab_low:
                            c.grab_bar, c.grab_low, c.grab_high = i, cs[i].l, cs[i].h
                            c.grab_close = cs[i].c
                    px = cs[i].c if cfg.mss_close else (cs[i].l if c.is_high else cs[i].h)
                    broke = px < c.struct_level if c.is_high else px > c.struct_level
                    if broke:
                        c.mss, c.mss_bar = True, i
                        if i - last_mss[c.is_high] < cfg.mss_cooldown_bars:
                            c.done = True
                        else:
                            last_mss[c.is_high] = i
                            for o in clusters:
                                if (o is not c and o.src == c.src and o.is_high == c.is_high
                                        and o.active and not o.mss and not o.expired
                                        and abs(o.level - c.level) <= a * cfg.tol_atr * 2):
                                    o.expired = True

            # The raid extreme stops trailing the moment the shift confirms —
            # the block above only runs while `not was_mss` — but the gap
            # search below keeps going for max_bars_after_mss bars. If price
            # trades back through the raid extreme during that window, the stop
            # a setup would carry has already been breached, and when the gap
            # forms beyond it the stop lands on the WRONG SIDE of the entry: a
            # long stopped above its own entry, which loses by construction.
            # Measured before this check: 7 of 1219 setups inverted that way
            # (-0.857 R), and 37 more carried a stop price had already taken.
            #
            # Expiring is the right response, not re-trailing the stop. For a
            # long, price back below the swept low means that low has been
            # taken a second time and the reversal the shift claimed did not
            # hold. There is no setup left to re-price — the premise is gone.
            if c.mss and not c.done and not c.expired:
                if (cs[i].h > c.grab_high) if c.is_high else (cs[i].l < c.grab_low):
                    c.expired = True

            # No-shift entry: the FIRST imbalance within early_max_bars of the
            # raid, entered at the gap edge with the stop beyond the raid
            # extreme. Runs after the block above so grab_low/grab_high have
            # already trailed for this bar, and only ever looks at a gap
            # ending on bar i — the point is to fire as it forms, not to hunt
            # backwards through the leg for one that fits.
            if (early_out is not None and c.swept and not c.early_done
                    and not c.expired and i - 2 >= 0):
                if i - c.sweep_bar > cfg.early_max_bars:
                    c.early_done = True
                else:
                    is_bull = not c.is_high
                    if is_bull:
                        top, bot = cs[i].l, cs[i - 2].h
                        ok = cs[i].l > cs[i - 2].h
                    else:
                        top, bot = cs[i - 2].l, cs[i].h
                        ok = cs[i].h < cs[i - 2].l
                    size = top - bot
                    fits = (ok and size >= a * cfg.min_fvg_atr
                            and (cfg.max_fvg_atr <= 0
                                 or size <= a * cfg.max_fvg_atr))
                    if fits:
                        ent = entry_of(is_bull, top, bot, cfg.entry_mode)
                        sl = (c.grab_low - a * cfg.sl_buffer_atr) if is_bull \
                            else (c.grab_high + a * cfg.sl_buffer_atr)
                        risk = abs(ent - sl)
                        # A gap sitting on the wrong side of the raid extreme
                        # would give a zero or inverted stop.
                        sane = (ent > sl) if is_bull else (ent < sl)
                        # early_max_risk_atr, not max_risk_atr: the caps are
                        # separate because the two signal types measured in
                        # opposite directions. See config.py.
                        if sane and risk > 0 and (
                                cfg.early_max_risk_atr <= 0
                                or risk <= a * cfg.early_max_risk_atr):
                            early_out.append(Early(
                                symbol=symbol, is_long=is_bull, src=c.src,
                                level=c.level, entry=ent, stop=sl, risk=risk,
                                sweep_bar=c.sweep_bar,
                                sweep_time=cs[c.sweep_bar].t,
                                grab_time=cs[c.grab_bar].t,
                                fvg_bar=i, fvg_time=cs[i].t,
                                anchor_time=cs[c.oldest_bar].t,
                                pivots=len(c.prices) or 1,
                                bars_from_sweep=i - c.sweep_bar,
                                rsi_ext=rsi_extension(rsi[c.sweep_bar], is_bull),
                                # No shift yet, so no breaker to agree with:
                                # the order block is the only vote available.
                                confluence=confluence_of(cs, i, is_bull)))
                            c.early_done = True

            if c.mss and not c.done and not c.expired:
                # "grab" searches the whole leg from the raid; "mss" only the
                # break bar onwards. Mirrors fvgScanFrom in the Pine.
                frm = c.grab_bar if cfg.fvg_scan_from == "grab" else i
                found = scan_leg(c, frm, i, i, a)
                if found:
                    ent, sl, fvg_bar = found
                    setups.append(Setup(
                        symbol=symbol, is_long=not c.is_high, src=c.src,
                        level=c.level, entry=ent, stop=sl, risk=abs(ent - sl),
                        grab_bar=c.grab_bar, mss_bar=c.mss_bar,
                        mss_time=cs[c.mss_bar].t, anchor_time=cs[c.oldest_bar].t,
                        pivots=len(c.prices) or 1,
                        sweep_time=cs[c.sweep_bar].t if c.sweep_bar >= 0 else 0,
                        grab_time=cs[c.grab_bar].t, fvg_time=cs[fvg_bar].t,
                        span=(max(c.prices) - min(c.prices)) if c.prices else 0.0,
                        rsi_ext=rsi_extension(rsi[c.sweep_bar], not c.is_high)
                                if c.sweep_bar >= 0 else 0.0,
                        confluence=confluence_of(cs, fvg_bar, not c.is_high,
                                                 c.grab_bar, c.mss_bar)))
                    c.done = True
                elif i - c.mss_bar >= cfg.max_bars_after_mss:
                    c.done = True

    # A single bar can run through several pools stacked in the same area, and
    # several clusters can reach the same gap with different raid extremes. In
    # both cases the entry is identical and only the named pool and the stop
    # differ — one trade, told once. Measured before this: 18% of sweep alerts
    # and 49% of early signals were repeats.
    #
    # collapse_dupes=False returns the raw stream. It exists so a test can
    # prove the collapse only ever merges items that are the same trade,
    # rather than that claim being an assertion in a comment.
    if clusters_out is not None:
        clusters_out[:] = clusters

    if collapse_dupes:
        if sweeps_out is not None:
            sweeps_out[:] = sorted(
                # struct_level is part of the key, not incidental: two pools
                # taken by the same bar can need DIFFERENT levels broken for
                # the shift to confirm, and then they are two setups in
                # waiting, not one. Measured: 37 same-bar groups disagreed on
                # it, and merging those would have dropped a real alert.
                collapse(sweeps_out,
                         lambda w: (w.sweep_bar, w.is_high, w.struct_level),
                         lambda n, c: (n.pivots, -abs(n.level - n.sweep_extreme))
                                      > (c.pivots, -abs(c.level - c.sweep_extreme))),
                key=lambda w: w.sweep_bar)
        if early_out is not None:
            early_out[:] = sorted(
                collapse(early_out, lambda e: (e.fvg_bar, e.is_long),
                         lambda n, c: (n.risk, n.bars_from_sweep)
                                      < (c.risk, c.bars_from_sweep)),
                key=lambda e: e.fvg_bar)
        setups = sorted(
            collapse(setups, lambda s: (s.fvg_time, s.is_long),
                     lambda n, c: n.risk < c.risk),
            key=lambda s: s.detected_time)

    return setups
