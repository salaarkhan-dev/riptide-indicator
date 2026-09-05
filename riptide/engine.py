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


def run_engine(symbol: str, cs: list[Candle], cfg: Cfg = CFG,
               sweeps_out: list | None = None) -> list[Setup]:
    """
    Single pass over closed candles, mirroring the Pine bar loop. Returns every
    setup found in the window; the caller decides which are recent enough to
    send.

    Pass a list as sweeps_out to also collect every liquidity grab. That is
    pure observation: it appends to the list and changes no decision, so the
    setups returned are identical whether or not it is supplied.
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

            if c.mss and not c.done and not c.expired:
                found = scan_leg(c, c.grab_bar, i, i, a)
                if found:
                    ent, sl, fvg_bar = found
                    setups.append(Setup(
                        symbol=symbol, is_long=not c.is_high, src=c.src,
                        level=c.level, entry=ent, stop=sl, risk=abs(ent - sl),
                        grab_bar=c.grab_bar, mss_bar=c.mss_bar,
                        mss_time=cs[c.mss_bar].t, anchor_time=cs[c.oldest_bar].t,
                        pivots=len(c.prices) or 1,
                        sweep_time=cs[c.sweep_bar].t if c.sweep_bar >= 0 else 0,
                        grab_time=cs[c.grab_bar].t, fvg_time=cs[fvg_bar].t))
                    c.done = True
                elif i - c.mss_bar >= cfg.max_bars_after_mss:
                    c.done = True

    return setups
