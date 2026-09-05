#!/usr/bin/env python3
"""
Riptide scanner - phase 1 (alerts only, no API key, no orders).

Port of the Riptide Pine indicator: liquidity pool -> sweep -> market structure
shift -> fair value gap. Polls MEXC futures candles just after each bar close,
runs the same engine, and sends new setups to Telegram.

Deliberately read-only. There is no exchange key anywhere in this file and no
code path that can place an order.

Sources: pivot pools, previous day high/low, previous week high/low. Sessions
are not implemented here; they are off by default in the indicator too.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import sys
import time
from zoneinfo import ZoneInfo
from dataclasses import dataclass, field
from datetime import datetime, timezone

import aiohttp

# ── configuration ───────────────────────────────────────────────────────────
# Futures API moved from contract.mexc.com to api.mexc.com in Jan 2026.
BASE = os.getenv("MEXC_BASE", "https://api.mexc.com")

TG_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID", "")

INTERVAL = os.getenv("RIPTIDE_INTERVAL", "Min30")     # Min15 Min30 Min60 Hour4
BAR_SECONDS = {"Min1": 60, "Min5": 300, "Min15": 900, "Min30": 1800,
               "Min60": 3600, "Hour4": 14400, "Hour8": 28800, "Day1": 86400}
LOOKBACK = int(os.getenv("RIPTIDE_LOOKBACK", "600"))   # bars fetched per symbol
FRESH_BARS = int(os.getenv("RIPTIDE_FRESH_BARS", "3"))  # only alert if the shift
                                                        # is this recent
DB_PATH = os.getenv("RIPTIDE_DB", "riptide.db")
CONCURRENCY = int(os.getenv("RIPTIDE_CONCURRENCY", "8"))
QUOTE = os.getenv("RIPTIDE_QUOTE", "USDT")
SYMBOLS_ENV = os.getenv("RIPTIDE_SYMBOLS", "")          # comma list, or blank
MIN_VOL_USDT = float(os.getenv("RIPTIDE_MIN_VOL", "3000000"))  # 24h turnover
ALERT_ON_FIRST_RUN = os.getenv("RIPTIDE_ALERT_FIRST_RUN", "0") == "1"
# Scan immediately on startup instead of waiting for the next bar close.
SCAN_ON_START = os.getenv("RIPTIDE_SCAN_ON_START", "1") == "1"
TG_RETRIES = int(os.getenv("RIPTIDE_TG_RETRIES", "4"))
# Listen for commands from TELEGRAM_CHAT_ID. Read-only status plus service
# control; there is still no exchange key and no order path anywhere.
TG_COMMANDS = os.getenv("RIPTIDE_TG_COMMANDS", "1") == "1"
# IANA name, e.g. Asia/Karachi. Display only — every internal calculation
# stays on UTC epoch seconds.
DISPLAY_TZ = os.getenv("RIPTIDE_TZ", "")
# Heads-up alerts on the liquidity grab itself, ahead of the structure shift.
SWEEP_ALERTS = os.getenv("RIPTIDE_SWEEP_ALERTS", "1") == "1"
# Must be at least 2. Candle.t is the bar's OPEN time, so a bar that has just
# closed is already one full step old, and the scan wakes another 10s after
# that. A window of 1 * step can never contain the sweep that just confirmed,
# so 1 silently suppresses every alert.
SWEEP_FRESH_BARS = int(os.getenv("RIPTIDE_SWEEP_FRESH_BARS", "2"))
# Which pool types raise a heads-up. Unset means all of them — the right
# default while the output is being checked against the chart, since
# filtering would hide part of what is being verified.
#
# For reference when tuning later: over 12.5 days on 20 symbols the share of
# sweeps that went on to produce a setup was Pivot 28%, Day 9%, Week 2%. The
# intuition that daily and weekly levels are the significant ones is not what
# the numbers show.
_sweep_src = os.getenv("RIPTIDE_SWEEP_SRC", "").strip()
SWEEP_SRC = ({s.strip() for s in _sweep_src.split(",") if s.strip()}
             if _sweep_src else None)


@dataclass
class Cfg:
    """Defaults mirror the Pine inputs. Change here, not in the engine."""
    pivot_left: int = 1
    pivot_right: int = 2
    atr_len: int = 28
    tol_atr: float = 0.25
    max_pool_span_bars: int = 60
    max_cluster_span_atr: float = 0.80
    min_pivots: int = 2
    max_overshoot_atr: float = 0.25
    allow_join_after_sweep: bool = True
    pending_expiry_bars: int = 500
    pending_invalidate_atr: float = 0.50
    grab_buffer_atr: float = 0.0
    trail_grab_extreme: bool = True
    max_bars_after_grab: int = 50
    mss_close: bool = True
    mss_cooldown_bars: int = 5
    min_fvg_atr: float = 0.05
    max_fvg_atr: float = 2.0
    max_risk_atr: float = 4.0
    max_bars_after_mss: int = 10
    sl_buffer_atr: float = 0.0
    entry_mode: str = "proximal"          # proximal | mid | distal
    use_pivot: bool = True
    use_daily: bool = True
    use_weekly: bool = True
    be_arm_r: float = 1.5


CFG = Cfg()

log = logging.getLogger("riptide")


def build_id() -> str:
    """Short commit the running file came from, written by deploy/update.sh."""
    try:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "BUILD")
        with open(p) as f:
            return f.read().strip()[:12] or "unknown"
    except OSError:
        return "unknown"


# ── engine ──────────────────────────────────────────────────────────────────
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


# ── exchange ────────────────────────────────────────────────────────────────
async def get_json(sess, url, params=None, tries=3):
    for k in range(tries):
        try:
            async with sess.get(url, params=params, timeout=aiohttp.ClientTimeout(total=20)) as r:
                if r.status == 429:
                    await asyncio.sleep(2 * (k + 1))
                    continue
                r.raise_for_status()
                return await r.json()
        except Exception as e:
            if k == tries - 1:
                log.warning("GET %s failed: %s", url, e)
                return None
            await asyncio.sleep(1.5 * (k + 1))
    return None


async def list_symbols(sess) -> list[str]:
    # An explicit list is a deliberate choice; never second-guess it.
    if SYMBOLS_ENV:
        return [s.strip() for s in SYMBOLS_ENV.split(",") if s.strip()]
    d = await get_json(sess, f"{BASE}/api/v1/contract/detail")
    if not d or not d.get("data"):
        return []
    out = []
    for c in d["data"]:
        if c.get("quoteCoin") != QUOTE:
            continue
        if c.get("state") != 0:            # 0 = enabled
            continue
        if c.get("apiAllowed") is False:
            continue
        out.append(c["symbol"])
    return await filter_by_turnover(sess, out)


async def filter_by_turnover(sess, symbols: list[str]) -> list[str]:
    """
    Drop symbols below MIN_VOL_USDT of 24h turnover.

    contract/detail carries no volume, so this needs contract/ticker, where
    amount24 is turnover in the quote currency (volume24 is contract count,
    which is not comparable across symbols).

    Falls back to the unfiltered list on any failure. This runs at startup
    and on the 6-hourly refresh, and an alerting service that stays up on a
    stale symbol list is better than one that exits because a secondary
    endpoint blipped.
    """
    if MIN_VOL_USDT <= 0 or not symbols:
        return symbols

    t = await get_json(sess, f"{BASE}/api/v1/contract/ticker")
    rows = (t or {}).get("data") or []
    if not rows:
        log.warning("ticker unavailable; volume filter skipped, keeping %d symbols",
                    len(symbols))
        return symbols

    turnover = {}
    for r in rows:
        try:
            turnover[r["symbol"]] = float(r.get("amount24") or 0.0)
        except (KeyError, TypeError, ValueError):
            continue

    kept = [s for s in symbols if turnover.get(s, 0.0) >= MIN_VOL_USDT]
    if not kept:
        log.warning("volume filter (%.0f USDT) matched no symbols; "
                    "threshold looks too high, keeping %d unfiltered",
                    MIN_VOL_USDT, len(symbols))
        return symbols

    log.info("volume filter: %d/%d symbols at or above %.0f USDT 24h turnover",
             len(kept), len(symbols), MIN_VOL_USDT)
    return kept


async def fetch_candles(sess, symbol: str) -> list[Candle]:
    step = BAR_SECONDS[INTERVAL]
    now = int(time.time())
    params = {"interval": INTERVAL, "start": now - LOOKBACK * step, "end": now}
    d = await get_json(sess, f"{BASE}/api/v1/contract/kline/{symbol}", params)
    if not d or not d.get("data"):
        return []
    k = d["data"]
    try:
        rows = list(zip(k["time"], k["open"], k["high"], k["low"], k["close"]))
    except (KeyError, TypeError):
        return []
    # Drop the forming bar. This is the confirmOnBarClose rule: the engine only
    # ever sees finished candles, so its output matches the chart.
    return [Candle(int(t), float(o), float(h), float(l), float(c))
            for t, o, h, l, c in rows if int(t) + step <= now]


# ── storage ─────────────────────────────────────────────────────────────────
def db_init():
    db = sqlite3.connect(DB_PATH)
    db.execute("""CREATE TABLE IF NOT EXISTS seen(
        sig TEXT PRIMARY KEY, symbol TEXT, side TEXT, src TEXT,
        entry REAL, stop REAL, level REAL, mss_time INT, sent_at INT)""")
    db.execute("CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT)")
    # Separate table so sweep dedupe cannot collide with setup dedupe, and so
    # an existing riptide.db picks this up without a migration.
    db.execute("""CREATE TABLE IF NOT EXISTS seen_sweeps(
        sig TEXT PRIMARY KEY, symbol TEXT, side TEXT, src TEXT,
        level REAL, struct_level REAL, sweep_time INT, sent_at INT)""")
    db.commit()
    return db


def sig_id(s: Setup) -> str:
    return f"{s.symbol}|{INTERVAL}|{s.anchor_time}|{s.mss_time}|{'L' if s.is_long else 'S'}"


def already_sent(db, sid) -> bool:
    return db.execute("SELECT 1 FROM seen WHERE sig=?", (sid,)).fetchone() is not None


def record(db, sid, s: Setup):
    db.execute("INSERT OR IGNORE INTO seen VALUES(?,?,?,?,?,?,?,?,?)",
               (sid, s.symbol, "long" if s.is_long else "short", s.src,
                s.entry, s.stop, s.level, s.mss_time, int(time.time())))
    db.commit()


def first_run(db) -> bool:
    return db.execute("SELECT COUNT(*) FROM seen").fetchone()[0] == 0


def meta_get(db, k: str, default: str = "") -> str:
    row = db.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone()
    return row[0] if row else default


def meta_set(db, k: str, v) -> None:
    db.execute("INSERT INTO meta(k, v) VALUES(?, ?) "
               "ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, str(v)))
    db.commit()


def sweep_sig(s: Sweep) -> str:
    return (f"SWP|{s.symbol}|{INTERVAL}|{s.anchor_time}|{s.sweep_time}|"
            f"{'H' if s.is_high else 'L'}")


def sweep_already_sent(db, sid) -> bool:
    return db.execute("SELECT 1 FROM seen_sweeps WHERE sig=?",
                      (sid,)).fetchone() is not None


def record_sweep(db, sid, s: Sweep):
    db.execute("INSERT OR IGNORE INTO seen_sweeps VALUES(?,?,?,?,?,?,?,?)",
               (sid, s.symbol, "short" if s.is_high else "long", s.src,
                s.level, s.struct_level, s.sweep_time, int(time.time())))
    db.commit()


# ── telegram ────────────────────────────────────────────────────────────────
async def tg_send(sess, text: str) -> bool:
    """
    Send one alert. Returns True only if Telegram acknowledged it.

    sendMessage is not idempotent — there is no request id to deduplicate on —
    so a blind retry can deliver the same alert twice. Retries are therefore
    limited to failures where the message provably did not arrive:

      429  Telegram states it did not deliver and says how long to wait.
      5xx  the request was not processed; Telegram's own docs say to retry.
      connect errors  the request never reached Telegram at all.

    Everything else stops. A read timeout or a reset mid-request is ambiguous:
    Telegram may have sent the message and lost the reply, so retrying risks a
    duplicate. Those are logged as possibly-delivered and dropped, which is the
    quieter failure of the two.
    """
    if not TG_TOKEN or not TG_CHAT:
        log.info("[no telegram configured]\n%s", text)
        return False

    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {"chat_id": TG_CHAT, "text": text, "parse_mode": "HTML",
               "disable_web_page_preview": True}

    for attempt in range(1, TG_RETRIES + 1):
        try:
            async with sess.post(
                    url, json=payload,
                    timeout=aiohttp.ClientTimeout(total=20, sock_connect=10)) as r:
                if r.status == 200:
                    if attempt > 1:
                        log.info("telegram delivered on attempt %d", attempt)
                    return True

                body = await r.text()

                if r.status == 429:
                    wait = 1.0
                    try:
                        wait = float(json.loads(body)
                                     .get("parameters", {}).get("retry_after", 1))
                    except (ValueError, AttributeError, TypeError):
                        pass
                    wait = min(max(wait, 1.0), 60.0)
                    log.warning("telegram rate limited, waiting %.0fs "
                                "(attempt %d/%d)", wait, attempt, TG_RETRIES)
                    await asyncio.sleep(wait)
                    continue

                if 500 <= r.status < 600:
                    back = min(2 ** attempt, 30)
                    log.warning("telegram %s, retrying in %ds (attempt %d/%d)",
                                r.status, back, attempt, TG_RETRIES)
                    await asyncio.sleep(back)
                    continue

                # 400 bad request, 403 blocked by the user, and friends. These
                # do not improve on a retry.
                log.error("telegram %s, not retried: %s", r.status, body[:300])
                return False

        except aiohttp.ClientConnectorError as e:
            back = min(2 ** attempt, 30)
            log.warning("telegram unreachable, retrying in %ds (attempt %d/%d): %s",
                        back, attempt, TG_RETRIES, e)
            await asyncio.sleep(back)
            continue

        except (asyncio.TimeoutError, aiohttp.ClientError) as e:
            log.error("telegram send outcome unknown (%s) — not retried, since "
                      "Telegram may already have delivered it. This alert may "
                      "or may not have arrived.", e)
            return False

    log.error("telegram gave up after %d attempts; alert NOT delivered", TG_RETRIES)
    return False


def fmt(v: float) -> str:
    if v >= 1000:
        return f"{v:,.1f}"
    if v >= 1:
        return f"{v:.4g}"
    return f"{v:.8g}"


def local_clock() -> str:
    """Current time in RIPTIDE_TZ, e.g. '08:30 PKT'. Empty if unset or bad."""
    if not DISPLAY_TZ:
        return ""
    try:
        now = datetime.now(ZoneInfo(DISPLAY_TZ))
    except Exception:
        log.warning("RIPTIDE_TZ=%r is not a valid IANA zone, ignoring", DISPLAY_TZ)
        return ""
    return now.strftime("%H:%M %Z")


def bar_label(t: int) -> str:
    """UTC bar-open time, matching how TradingView labels the bar."""
    return datetime.fromtimestamp(t, timezone.utc).strftime("%H:%M")


def setup_message(s: Setup) -> str:
    side = "LONG" if s.is_long else "SHORT"
    sign = 1 if s.is_long else -1
    t1 = s.entry + sign * s.risk
    t15 = s.entry + sign * s.risk * CFG.be_arm_r
    t3 = s.entry + sign * s.risk * 3
    riskpct = s.risk / s.entry * 100 if s.entry else 0
    tv = f"https://www.tradingview.com/chart/?symbol=MEXC%3A{s.symbol.replace('_', '')}.P"
    return (
        f"<b>{side}  {s.symbol}</b>  ({INTERVAL})\n"
        f"{s.src} liquidity @ {fmt(s.level)}"
        f"{f' · {s.pivots} swings' if s.src == 'Pivot' else ''}\n\n"
        f"Entry  <code>{fmt(s.entry)}</code>\n"
        f"Stop   <code>{fmt(s.stop)}</code>   ({riskpct:.2f}% risk)\n"
        f"1R     {fmt(t1)}\n"
        f"BE at  {fmt(t15)}  ({CFG.be_arm_r}R)\n"
        f"3R     {fmt(t3)}\n\n"
        f"<a href='{tv}'>chart</a>"
    )


def sweep_message(s: Sweep) -> str:
    """Heads-up on the grab. Deliberately carries no entry or stop: there is
    no setup yet, and the shift may never come."""
    bias = "SHORT" if s.is_high else "LONG"
    took = "high" if s.is_high else "low"
    direction = "below" if s.is_high else "above"
    tv = f"https://www.tradingview.com/chart/?symbol=MEXC%3A{s.symbol.replace('_', '')}.P"
    return (
        f"⚠️ <b>SWEEP  {s.symbol}</b>  ({INTERVAL})\n"
        f"{s.src} {took} @ {fmt(s.level)} taken"
        f"{f' · {s.pivots} swings' if s.src == 'Pivot' else ''}\n\n"
        f"Watching for  <b>{bias}</b>\n"
        f"Shift confirms {direction} <code>{fmt(s.struct_level)}</code>\n"
        f"Sweep {took}   {fmt(s.sweep_extreme)}\n\n"
        f"No entry yet — the FVG forms after the shift.\n"
        f"<a href='{tv}'>chart</a>"
    )


# ── scan cycle ──────────────────────────────────────────────────────────────
async def scan_symbol(sess, sem, symbol):
    """Returns (setups, sweeps). sweeps is empty unless RIPTIDE_SWEEP_ALERTS."""
    async with sem:
        cs = await fetch_candles(sess, symbol)
        if len(cs) < 100:
            return [], []
        sweeps: list[Sweep] = [] if SWEEP_ALERTS else None
        try:
            setups = run_engine(symbol, cs, sweeps_out=sweeps)
            return setups, (sweeps or [])
        except Exception as e:
            log.warning("engine failed on %s: %s", symbol, e)
            return [], []


async def cycle(sess, db, symbols):
    sem = asyncio.Semaphore(CONCURRENCY)
    results = await asyncio.gather(*(scan_symbol(sess, sem, s) for s in symbols))

    bootstrap = first_run(db) and not ALERT_ON_FIRST_RUN
    # /pause records everything as usual but sends nothing, so resuming does
    # not replay the backlog.
    paused = meta_get(db, "alerts_paused", "0") == "1"
    mute = bootstrap or paused
    step = BAR_SECONDS[INTERVAL]
    now = int(time.time())
    sent = 0

    # Sweeps first: the grab precedes the shift, so the heads-up should land
    # before the setup message when both fall in the same cycle.
    swept = 0
    for _, sweeps in results:
        for w in sweeps:
            if SWEEP_SRC is not None and w.src not in SWEEP_SRC:
                continue
            fresh = (now - w.sweep_time) <= SWEEP_FRESH_BARS * step
            sid = sweep_sig(w)
            if sweep_already_sent(db, sid):
                continue
            record_sweep(db, sid, w)
            if fresh and not mute:
                if await tg_send(sess, sweep_message(w)):
                    swept += 1

    for setups, _ in results:
        for s in setups:
            # Only shifts from the last few bars are actionable. Older ones are
            # recorded so a restart cannot re-alert the whole history.
            fresh = (now - s.mss_time) <= FRESH_BARS * step
            sid = sig_id(s)
            if already_sent(db, sid):
                continue
            record(db, sid, s)
            if fresh and not mute:
                if await tg_send(sess, setup_message(s)):
                    sent += 1
    if bootstrap:
        log.info("first run: history recorded, nothing sent")
    elif paused:
        log.info("alerts paused; recorded but not sent")
    if SWEEP_ALERTS:
        log.info("scanned %d symbols, sent %d alerts, %d sweep heads-ups",
                 len(symbols), sent, swept)
    else:
        log.info("scanned %d symbols, sent %d alerts", len(symbols), sent)
    return sent + swept


# ── telegram commands ───────────────────────────────────────────────────────
HELP = (
    "<b>Riptide</b>\n\n"
    "/status — build, symbols, last and next scan\n"
    "/scan — run a scan now\n"
    "/pause — record setups but stop sending\n"
    "/resume — start sending again\n"
    "/update — check GitHub for a new build now\n"
    "/restart — restart the service\n"
    "/help — this\n\n"
    "<i>Symbols and settings are edited in riptide.conf on GitHub; the box "
    "picks them up within about five minutes.</i>"
)


def _fmt_ago(seconds: float) -> str:
    seconds = int(max(seconds, 0))
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h {(seconds % 3600) // 60}m"
    return f"{seconds // 86400}d {(seconds % 86400) // 3600}h"


async def _run(*argv) -> tuple[int, str]:
    """Run a command, capturing output. Used only for systemctl."""
    p = await asyncio.create_subprocess_exec(
        *argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    out, _ = await p.communicate()
    return p.returncode, out.decode(errors="replace").strip()


def status_text(db, state) -> str:
    step = BAR_SECONDS[INTERVAL]
    paused = meta_get(db, "alerts_paused", "0") == "1"
    seen_n = db.execute("SELECT COUNT(*) FROM seen").fetchone()[0]
    swp_n = db.execute("SELECT COUNT(*) FROM seen_sweeps").fetchone()[0]
    last = state.get("last_cycle", 0)
    if last:
        scan_line = f"{_fmt_ago(time.time() - last)} ago · {state.get('last_sent', 0)} sent"
    else:
        scan_line = "none yet"
    sweeps = "on" if SWEEP_ALERTS else "off"
    return (
        f"<b>Riptide status</b>\n\n"
        f"build      <code>{build_id()}</code>\n"
        f"symbols    {len(state.get('symbols', []))} · {INTERVAL}\n"
        f"alerts     {'PAUSED' if paused else 'on'} · sweeps {sweeps}\n"
        f"uptime     {_fmt_ago(time.time() - state.get('started', time.time()))}\n"
        f"last scan  {scan_line}\n"
        f"next scan  in {int(seconds_to_next_close(step) // 60)}m\n"
        f"recorded   {seen_n} setups · {swp_n} sweeps\n"
        f"clock      {local_clock() or 'UTC only'}"
    )


async def handle_command(sess, db, state, text: str) -> None:
    cmd = text.strip().split()[0].lower().lstrip("/").split("@")[0]

    if cmd in ("start", "help"):
        await tg_send(sess, HELP)

    elif cmd == "status":
        await tg_send(sess, status_text(db, state))

    elif cmd == "scan":
        await tg_send(sess, "Scanning…")
        n = await cycle(sess, db, state.get("symbols", []))
        state["last_cycle"] = time.time()
        state["last_sent"] = n
        await tg_send(sess, f"Scan done · {n} alert(s) sent")

    elif cmd == "pause":
        meta_set(db, "alerts_paused", "1")
        await tg_send(sess, "Paused. Setups are still recorded, so /resume "
                            "will not replay the backlog.")

    elif cmd == "resume":
        meta_set(db, "alerts_paused", "0")
        await tg_send(sess, "Resumed.")

    elif cmd == "update":
        await tg_send(sess, "Checking GitHub…")
        rc, out = await _run("sudo", "-n", "systemctl", "start",
                             "riptide-update.service")
        if rc != 0:
            await tg_send(sess, f"Could not start the updater:\n<code>"
                                f"{out[:300]}</code>")
        # A real update restarts the service and reports separately. Silence
        # here means the branch had nothing new.

    elif cmd == "restart":
        # Reply first — the restart kills this process.
        await tg_send(sess, "Restarting…")
        rc, out = await _run("sudo", "-n", "systemctl", "restart", "riptide")
        if rc != 0:
            await tg_send(sess, f"Restart failed:\n<code>{out[:300]}</code>")

    else:
        await tg_send(sess, f"Unknown command /{cmd}\n\n{HELP}")


async def command_loop(sess, db, state) -> None:
    """
    Long-poll getUpdates and act on commands from TELEGRAM_CHAT_ID only.

    The offset is persisted and advanced BEFORE the command runs. /restart
    would otherwise be replayed by the process it just started, forever.
    """
    if not (TG_TOKEN and TG_CHAT):
        return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/getUpdates"
    offset = int(meta_get(db, "tg_offset", "0") or 0)

    # No stored offset means a fresh database. Skip whatever is already queued
    # rather than acting on commands sent before this process existed.
    if offset == 0:
        try:
            async with sess.get(url, params={"offset": -1, "timeout": 0},
                                timeout=aiohttp.ClientTimeout(total=20)) as r:
                for u in (await r.json()).get("result", []):
                    offset = max(offset, int(u["update_id"]))
        except Exception as e:
            log.warning("telegram command backlog check failed: %s", e)
        meta_set(db, "tg_offset", offset)
        log.info("telegram commands ready (backlog skipped to %d)", offset)

    while True:
        try:
            async with sess.get(url,
                                params={"offset": offset + 1, "timeout": 25},
                                timeout=aiohttp.ClientTimeout(total=45)) as r:
                if r.status != 200:
                    log.warning("getUpdates %s", r.status)
                    await asyncio.sleep(10)
                    continue
                updates = (await r.json()).get("result", [])
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.warning("getUpdates failed: %s", e)
            await asyncio.sleep(15)
            continue

        for u in updates:
            offset = max(offset, int(u["update_id"]))
            meta_set(db, "tg_offset", offset)      # commit before acting

            msg = u.get("message") or u.get("edited_message") or {}
            text = (msg.get("text") or "").strip()
            chat = str((msg.get("chat") or {}).get("id", ""))
            who = str((msg.get("from") or {}).get("id", ""))

            if not text.startswith("/"):
                continue
            # Both must match: the configured chat, and a sender who is that
            # same account. Anyone else is ignored without a reply, so the bot
            # does not confirm it exists.
            if chat != str(TG_CHAT) or who != str(TG_CHAT):
                log.warning("ignoring command from chat=%s user=%s", chat, who)
                continue

            log.info("telegram command: %s", text.split()[0])
            try:
                await handle_command(sess, db, state, text)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.exception("command failed: %s", e)
                await tg_send(sess, f"Command failed: {e}")


def seconds_to_next_close(step: int, pad: int = 10) -> float:
    now = time.time()
    return (step - (now % step)) + pad


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stdout)
    if INTERVAL not in BAR_SECONDS:
        log.error("bad interval %s", INTERVAL)
        return
    db = db_init()
    step = BAR_SECONDS[INTERVAL]

    async with aiohttp.ClientSession() as sess:
        symbols = await list_symbols(sess)
        if not symbols:
            log.error("no symbols; check MEXC_BASE or RIPTIDE_SYMBOLS")
            return
        log.info("riptide up: %d symbols, %s bars, build %s",
                 len(symbols), INTERVAL, build_id())
        await tg_send(sess, f"Riptide scanner started\n"
                            f"{len(symbols)} symbols · {INTERVAL} bars")

        # Scan once before entering the loop. The loop sleeps first, so without
        # this a restart is blind until the next close — up to a full bar. That
        # is not just a delay: a sweep on the bar that closed just before the
        # restart is 2*step + pad old by the first scheduled cycle, past the
        # 2-bar window, so it would never be sent at all.
        #
        # Safe to repeat work: dedupe skips anything the previous process
        # already recorded, the freshness gate still applies, and an empty
        # database still bootstraps silently.
        # Shared with the command listener so /status reports live values.
        state = {"symbols": symbols, "started": time.time(),
                 "last_cycle": 0.0, "last_sent": 0}

        if SCAN_ON_START:
            n = await cycle(sess, db, symbols)
            state["last_cycle"], state["last_sent"] = time.time(), n

        tasks = [asyncio.create_task(scan_loop(sess, db, state), name="scan")]
        if TG_COMMANDS:
            tasks.append(asyncio.create_task(
                command_loop(sess, db, state), name="commands"))
            log.info("telegram commands enabled")

        # If either loop dies the process should exit and let systemd restart
        # it, rather than limp along with half its behaviour missing.
        try:
            done, pending = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED)
            for t in pending:
                t.cancel()
            for t in done:
                t.result()          # re-raise whatever stopped it
        except asyncio.CancelledError:
            raise


async def scan_loop(sess, db, state) -> None:
    step = BAR_SECONDS[INTERVAL]
    last_symbol_refresh = time.time()
    # Persisted, so "alive" means a day has genuinely passed rather than
    # "the process restarted". Survives updates; a deleted riptide.db
    # resets it, which only costs one extra heartbeat.
    try:
        last_heartbeat = float(meta_get(db, "last_heartbeat", "0") or 0)
    except ValueError:
        last_heartbeat = 0.0

    while True:
        try:
            await asyncio.sleep(seconds_to_next_close(step))
            n = await cycle(sess, db, state["symbols"])
            state["last_cycle"], state["last_sent"] = time.time(), n

            if time.time() - last_symbol_refresh > 21600:      # 6h
                fresh = await list_symbols(sess)
                if fresh:
                    state["symbols"] = fresh
                last_symbol_refresh = time.time()

            # Daily heartbeat, so silence means something is broken rather
            # than that nothing set up.
            if time.time() - last_heartbeat > 86400:
                when = local_clock()
                await tg_send(sess, f"Riptide alive · {len(state['symbols'])} symbols"
                                    + (f" · {when}" if when else ""))
                last_heartbeat = time.time()
                meta_set(db, "last_heartbeat", last_heartbeat)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.exception("cycle error: %s", e)
            await asyncio.sleep(30)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
