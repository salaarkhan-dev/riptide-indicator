"""The engine: liquidity pool -> sweep -> market structure shift -> fair value gap.

A single pass over closed candles, mirroring the Pine bar loop. Pure and
synchronous: no I/O, no clock, no network. Everything it needs arrives as
arguments, which is what makes it testable against recorded data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from .config import CFG, Cfg

@dataclass
class Candle:
    t: int
    o: float
    h: float
    l: float
    c: float


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
    trend_dir: int = 0     # as above
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


def confluence_of(cs: list[Candle], fvg_bar: int, is_bull: bool,
                  grab_bar: int = -1, mss_bar: int = -1) -> int:
    """
    How many of {order block, breaker} sit in the same price area as the gap.

    Observation only — it never changes which setups exist or what they enter
    at. Both zones were separately tested as ALTERNATIVE entries and both came
    back flat; the open question is whether their AGREEMENT with the gap grades
    a setup, which is a different thing and is what this counts.

      order block  the last opposing candle before the impulse that made the gap
      breaker      the last opposing candle at or before the extreme the shift
                   broke. Needs an MSS, so an early signal can only score 0-1.

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
    if 0 <= grab_bar < mss_bar:
        rng = range(grab_bar, mss_bar)
        ext = (max(rng, key=lambda x: cs[x].h) if is_bull
               else min(rng, key=lambda x: cs[x].l))
        brk = last_opposing(cs, ext, is_bull)
        if brk >= 0 and ranges_overlap(top, bot, cs[brk].h, cs[brk].l):
            n += 1
    return n


# Grade bands, read off the measured trend x confluence cells rather than
# invented. 50 symbols, 41.6 days, 1R target, R per setup:
#
#                 0 zones            1 zone             2 zones
#   with trend    +0.083 (620)       +0.109 (188)       +0.170 (173)
#   against       +0.001 (625)       -0.025 (204)       +0.047 (189)
#
# Every with-trend cell beats every against-trend cell, and within with-trend
# the confluence ordering is monotonic. That is the ladder below.
#
# READ THE STEPS HONESTLY. Only the trend step is established: +0.110 ± 0.029,
# +3.8 SE, replicated across two windows and two symbol sets. A+ over B is
# +0.087 ± 0.064, which is +1.4 SE and not significant — and against the trend
# the confluence ordering breaks down entirely (1 zone scores below 0). So B
# versus C is a real distinction; A+ versus A versus B is a hypothesis being
# tracked live, and none of the bands is a prediction about one trade.
GRADES = {
    ("with", 2): ("A+", "with the trend · gap, order block and breaker agree"),
    ("with", 1): ("A",  "with the trend · gap and order block agree"),
    ("with", 0): ("B",  "with the trend"),
    ("against", 2): ("C", "AGAINST the trend · zones agree"),
    ("against", 1): ("C", "AGAINST the trend"),
    ("against", 0): ("C", "AGAINST the trend"),
}


def grade_of(trend_dir: int, is_long: bool, confluence: int) -> tuple[str, str]:
    """
    (letter, why) for one signal. Presentation only — nothing decides on it,
    and no signal is suppressed by it.

    Returns ("?", ...) when the higher-timeframe trend is unknown, which is
    honest: the axis carrying almost all of the separation is missing, so
    there is nothing to grade on.
    """
    if not trend_dir:
        return "?", "trend unknown"
    side = "with" if (trend_dir > 0) == is_long else "against"
    return GRADES[(side, max(0, min(2, confluence)))]


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
               collapse_dupes: bool = True) -> list[Setup]:
    """
    Single pass over closed candles, mirroring the Pine bar loop. Returns every
    setup found in the window; the caller decides which are recent enough to
    send.

    Pass a list as sweeps_out to also collect every liquidity grab, or
    early_out to collect the no-shift entries described on Early. Both are
    pure observation: they append to a list and change no decision, so the
    setups returned are identical whether or not either is supplied.
    """
    n = len(cs)
    if n < cfg.atr_len + cfg.pivot_left + cfg.pivot_right + 10:
        return []

    atr = atr_series(cs, cfg.atr_len)
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
                            anchor_time=cs[c.oldest_bar].t,
                            pivots=len(c.prices) or 1))

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
                        if sane and risk > 0 and (
                                cfg.max_risk_atr <= 0
                                or risk <= a * cfg.max_risk_atr):
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
