"""Trendline-break heads-up alerts. A watch list, not a strategy.

WHAT THIS IS FOR. TradingView will alert on a line you drew yourself; it will
not alert on this indicator across sixty pairs, and nobody can keep sixty
charts open to see which one just broke. That is the entire product: one
message per bar close saying which symbols did something, with a link straight
to each chart at the right timeframe. The answer to "which chart should I open"
— nothing more.

IT IS NOT A TRADE AND THE MESSAGE SAYS SO. The identical breakout was scored
through the same harness as everything else here
(research/studies/trendline_measure.py): net R per signal is NEGATIVE on both
halves of the window and statistically indistinguishable from a random entry of
the same shape. So there is no entry, no stop, no target, no grade, and — this
is deliberate and not an oversight — NO OUTCOME TRACKING. Riptide arms every
signal it sends so /stats can score it forward; that machinery exists to judge
trades, and arming these would put rows with a made-up entry and a made-up stop
into the same table that decides whether Riptide's strategies work. A heads-up
has no outcome. It is not scored because there is nothing to score.

COMPLETELY SEPARATE FROM RIPTIDE. Its own loop, its own timeframe, its own
dedupe table, its own message, its own on/off switch. It shares the candle
fetcher and the Telegram sender and nothing else: no cluster, no POI, no grade,
no sweep_worth, and no setting of Riptide's reaches it. The loop body is
wrapped whole — a failure in a watch list must never be able to cost a trade
alert, which is the same reasoning that already wraps `_arm` and the market
logger in the scanner.

ONE DIGEST PER BAR CLOSE, NOT ONE MESSAGE PER BREAK, AND NOT ONE PER
TIMEFRAME. Bar closes are synchronised across the universe, so breaks do not
arrive spread out — they arrive together. Measured over 60 symbols, the worst
single 4h close had 20 symbols break at once
(research/studies/trendline_rate.py). Twenty separate messages in one second is
unreadable and is past Telegram's per-chat rate limit; one message listing
twenty symbols is a glance. A 30m close is also a 15m close, so those go in the
same message too, and a chart that broke on both is listed once. A quiet close
sends nothing at all.

THE STEEPNESS GATE IS A VOLUME CONTROL AND IS LABELLED AS ONE. A flat trendline
is a horizontal level and price crossing one is the most ordinary thing a chart
does, so dropping the flat breaks is what makes 15m+30m readable at all — 161 a
day becomes 32. Whether it also picks BETTER breaks was measured and the answer
is no: research/studies/trendline_slope.py found +9.0pp continuation for steep
breaks on the discovery half at 4.4 SE, and the held-out half reversed it to
-3.1pp. The gate is kept for the readability and nothing in the message claims
more than that. See config.TRENDLINE_MIN_SLOPE for the table.

WHY IT RUNS ON ITS OWN TIMER rather than inside the scan cycle: the scanner
wakes on the fastest structure timeframe and fetches Riptide's intervals. This
needs a different interval on a different schedule, and hanging it off the scan
cycle would mean either fetching 4h candles every few minutes and throwing them
away, or letting the watch decide when Riptide scans. At Hour4 this is 6 wakes
a day x 60 symbols = 360 requests, against the scanner's thousands.
"""

from __future__ import annotations

import asyncio
import time

from . import storage
from . import telegram as tg
from .config import (BAR_SECONDS, CONCURRENCY, TRENDLINE_ALERTS,
                     TRENDLINE_FRESH_BARS, TRENDLINE_INTERVALS,
                     TRENDLINE_MAX_LINES, TRENDLINE_MIN_SLOPE, TRENDLINE_PIVOT,
                     TRENDLINE_SPACE, log)
from .engine import atr_series
from .exchange import fetch_candles
from .trendline import ATR_LEN, trendline_signals

# `from . import storage` rather than `from .storage import meta_get`, and the
# reason is a circular import: storage.db_init() creates this module's table,
# so storage imports watch, and by the time watch runs, storage is only
# half-executed — meta_get does not exist yet to be bound. The module object
# does exist, and every use below is at call time, long after both are loaded.

# How far back in the fetched history to consider a break at all. Anything
# older cannot pass the freshness gate, so walking further would only fill the
# dedupe table with breaks that were never sendable.
RECENT_BARS = 8


def init(db) -> None:
    """The dedupe table. Its own, so a trendline break and a Riptide signal on
    the same symbol at the same minute cannot suppress each other."""
    db.execute("""CREATE TABLE IF NOT EXISTS seen_trendline(
        sig TEXT PRIMARY KEY, symbol TEXT, side TEXT, tf TEXT,
        bar_time INT, price REAL, line_y REAL, sent_at INT)""")
    db.commit()


def sig_of(symbol: str, tf: str, bar_time: int, is_long: bool) -> str:
    return f"TL|{symbol}|{tf}|{bar_time}|{'U' if is_long else 'D'}"


def already_sent(db, sid: str) -> bool:
    return db.execute("SELECT 1 FROM seen_trendline WHERE sig=?",
                      (sid,)).fetchone() is not None


def record(db, sid: str, symbol: str, tf: str, bar_time: int, is_long: bool,
           price: float, line_y: float) -> None:
    db.execute("INSERT OR IGNORE INTO seen_trendline VALUES(?,?,?,?,?,?,?,?)",
               (sid, symbol, "up" if is_long else "down", tf, bar_time,
                price, line_y, int(time.time())))
    db.commit()


def enabled(db) -> bool:
    """Live on/off: the /trendline override if one is set, else the config."""
    v = storage.meta_get(db, "trendline_alerts", "")
    return v == "1" if v in ("0", "1") else TRENDLINE_ALERTS


def intervals(db) -> tuple:
    """Live timeframes: the /trendline override if one is set, else the config.

    Validated on read rather than on write, so a database carrying a value this
    build no longer knows falls back instead of taking the loop down.
    """
    v = [i.strip() for i in
         storage.meta_get(db, "trendline_tf", "").split(",") if i.strip()]
    good = tuple(dict.fromkeys(i for i in v if i in BAR_SECONDS))
    return good or tuple(i for i in TRENDLINE_INTERVALS if i in BAR_SECONDS) \
        or ("Hour4",)


def min_slope(db) -> float:
    """Live steepness gate, in |slope| / ATR(200). 0 means every break."""
    v = storage.meta_get(db, "trendline_min_slope", "")
    try:
        return max(0.0, float(v)) if v else TRENDLINE_MIN_SLOPE
    except ValueError:
        return TRENDLINE_MIN_SLOPE


class Break:
    """One symbol's break, with everything the digest line needs."""
    __slots__ = ("symbol", "tf", "is_long", "bar_time", "price", "line_y",
                 "age_bars", "slope_atr", "sig")


async def scan_symbol(sess, sem, symbol: str, tf: str,
                      floor: float = 0.0) -> list[Break]:
    """Breaks on this symbol in the last RECENT_BARS bars, newest last.

    `floor` is the steepness gate, in |slope| / ATR(200). It is applied HERE
    rather than in the digest so a break that never qualified is never recorded
    either — otherwise lowering the gate later would find every one of them
    already marked as sent and stay silent.
    """
    async with sem:
        cs = await fetch_candles(sess, symbol, tf)
    # The port needs ATR(200) valid before any channel can exist, plus room for
    # pivots either side. Under that it is not a quiet symbol, it is a symbol
    # with no answer, and returning nothing silently would look identical.
    if len(cs) < 260:
        if cs:
            log.debug("trendline: %s %s only %d bars, skipped", symbol, tf,
                      len(cs))
        return []
    sigs = trendline_signals(cs, pivot_len=TRENDLINE_PIVOT,
                             space=TRENDLINE_SPACE)
    atr = atr_series(cs, ATR_LEN)
    step = BAR_SECONDS[tf]
    cutoff = len(cs) - RECENT_BARS
    out = []
    for s in sigs:
        if s.bar < cutoff:
            continue
        # Steepness in the symbol's own volatility, so a 100000-dollar chart
        # and a 0.008-dollar one are on the same scale. The sign is guaranteed
        # by construction — an up channel is built only from descending pivot
        # highs — so only the magnitude carries information.
        a = atr[s.bar] if s.bar < len(atr) else 0.0
        slope_atr = abs(s.slope) / a if a and a > 0 else 0.0
        if slope_atr < floor:
            continue
        b = Break()
        b.symbol, b.tf, b.is_long = symbol, tf, s.is_long
        # Candle.t is the bar's OPEN, and a break is only true once the bar has
        # closed — so the moment it became real is t + step, which is what the
        # freshness gate and the "Nm ago" both have to measure from.
        b.bar_time = cs[s.bar].t + step
        b.price, b.line_y = s.price, s.line_y
        b.age_bars = len(cs) - 1 - s.bar
        b.slope_atr = slope_atr
        b.sig = sig_of(symbol, tf, cs[s.bar].t, s.is_long)
        out.append(b)
    return out


def _line(b: Break) -> str:
    """One symbol in the digest: where it broke, how steep the line was,
    clickable.

    THE TIMEFRAME IS ON EVERY LINE, always, even when the whole digest is one
    timeframe. It used to appear only when a digest mixed two, on the reasoning
    that a header saying "15m+30m" plus a single tag was the same fact twice —
    which was wrong in the way that matters. The tag answers "which chart am I
    opening", and the reader is looking at one line, not auditing the header
    against it. A conditional tag is also worse than either choice on its own:
    the lines change shape between messages, so the eye has to re-find the
    price column each time.

    The two numbers after it are the two reasons to open one chart before
    another. The slope is how steep the broken line was in the symbol's own
    volatility — a flat line is a horizontal level and breaking one is the most
    ordinary thing a chart does. The gap is how far past the line it closed.
    """
    gap = 100 * abs(b.price - b.line_y) / b.line_y if b.line_y else 0.0
    return (f"{'🟢' if b.is_long else '🔴'} <a href='"
            f"{tg.tv_link(b.symbol, b.tf)}'><b>{b.symbol.replace('_USDT', '')}"
            f"</b></a> <code>{tg.tf_label(b.tf)}</code>  "
            f"<code>{tg.fmt(b.price)}</code>  "
            f"<i>slope {b.slope_atr:.2f} · {gap:.2f}% past</i>")


def collapse(breaks: list[Break]) -> list[Break]:
    """One line per symbol per direction, keeping the SLOWEST timeframe.

    A 30m close is also a 15m close, so when both are watched the same chart
    can print an arrow on both at once. They are genuinely two different lines,
    but to a reader they are one event — "this chart just broke" — and listing
    it twice is the kind of noise that makes a digest stop being read.

    The slower timeframe is the one kept because it is the larger structure and
    because its chart link is the one worth opening first. Both are still
    RECORDED; this only decides what the message shows.
    """
    best: dict = {}
    for b in breaks:
        k = (b.symbol, b.is_long)
        cur = best.get(k)
        if cur is None or BAR_SECONDS[b.tf] > BAR_SECONDS[cur.tf]:
            best[k] = b
    return list(best.values())


# Telegram rejects a sendMessage body over 4096 characters. This leaves room
# for the footer and for the "+N more" line that gets appended after the budget
# is spent.
#
# THE LINE COUNT ALONE IS NOT ENOUGH TO STAY UNDER IT, and the test that found
# this used three-letter symbols and came out at 3876 characters for 25 lines —
# comfortably inside the cap, and wrong. A real line is mostly the TradingView
# URL, which carries the symbol twice, so TRUMPOFFICIAL costs about 20
# characters more than XRP. Twenty-five of those is over the cap, and the way
# Telegram says so is by refusing the message: the digest that fails is the
# market-wide one, which is the only digest anybody urgently wanted.
MAX_CHARS = 3800


def digest(breaks: list[Break], tfs, when: int) -> str:
    """The whole message. Ups first, then downs, steepest line first.

    Deliberately flat and short. Every line is a link, and the ordering is the
    only recommendation offered: the steepest break at the top, because a flat
    line is a horizontal level and breaking one says the least.

    Trimmed by BOTH a line count and a character budget; see MAX_CHARS.
    """
    breaks = sorted(collapse(breaks),
                    key=lambda b: (not b.is_long, -b.slope_atr))
    ups = [b for b in breaks if b.is_long]
    dns = [b for b in breaks if not b.is_long]
    clock = tg.local_clock()
    label_tf = "+".join(tg.tf_label(t) for t in tfs)
    head = (f"📐 <b>TRENDLINE BREAKS</b>  {label_tf}  ·  "
            f"{len(breaks)} symbol{'s' if len(breaks) != 1 else ''}"
            + (f"  ·  {clock}" if clock else ""))
    foot = f"\n<i>{tg.signal_age(when)}</i>"
    parts = [head, "<i>a heads-up, not a trade — no entry, no stop, "
                   "no edge measured. Go look.</i>"]
    used = len(head) + len(parts[1]) + len(foot) + 40   # 40: the "+N more" line
    shown = 0
    for label, group in (("break UP through resistance", ups),
                         ("break DOWN through support", dns)):
        if not group or shown >= TRENDLINE_MAX_LINES:
            continue
        header = f"<b>{label}</b>"
        parts += ["", header]
        used += len(header) + 2
        for b in group:
            row = _line(b)
            if shown >= TRENDLINE_MAX_LINES or used + len(row) > MAX_CHARS:
                break
            parts.append(row)
            used += len(row) + 1
            shown += 1
    left = len(breaks) - shown
    if left > 0:
        parts.append(f"<i>+{left} more this close</i>")
    parts.append(foot)
    return "\n".join(parts)


async def cycle(sess, db, symbols, tfs=None) -> int:
    """One pass over the universe, across every timeframe that just closed.

    ONE DIGEST covering all of them, not one per timeframe: a 30m close is also
    a 15m close, and two messages arriving in the same second is the thing the
    digest exists to prevent.

    Everything that clears the steepness gate is RECORDED, sent or not, exactly
    as the scanner does: dedupe has to cover the breaks that were suppressed
    too, or a restart replays them.
    """
    tfs = tuple(tfs) if tfs else intervals(db)
    tfs = tuple(t for t in tfs if t in BAR_SECONDS)
    if not tfs:
        log.warning("trendline: no valid interval configured, watch idle")
        return 0
    floor = min_slope(db)
    sem = asyncio.Semaphore(CONCURRENCY)
    jobs = [(s, tf) for tf in tfs for s in symbols]
    results = await asyncio.gather(
        *(scan_symbol(sess, sem, s, tf, floor) for s, tf in jobs),
        return_exceptions=True)

    now = int(time.time())
    fresh: list[Break] = []
    seen = stale = dupe = failed = 0
    for r in results:
        if isinstance(r, Exception):
            failed += 1
            continue
        for b in r:
            seen += 1
            if already_sent(db, b.sig):
                dupe += 1
                continue
            record(db, b.sig, b.symbol, b.tf, b.bar_time, b.is_long, b.price,
                   b.line_y)
            # Counted in BARS of that break's OWN timeframe — a 30m break gets
            # a 30m window, a 15m break a 15m one. A single global window would
            # either bin the slower timeframe or let the faster one go stale.
            if now - b.bar_time > TRENDLINE_FRESH_BARS * BAR_SECONDS[b.tf]:
                stale += 1
                continue
            fresh.append(b)

    # /pause is one switch over everything the bot sends. A watch list that
    # kept talking through a pause would make the switch useless.
    paused = storage.meta_get(db, "alerts_paused", "0") == "1"
    sent = 0
    if fresh and not paused:
        if await tg.tg_send(sess, digest(fresh, tfs,
                                         max(b.bar_time for b in fresh))):
            sent = len(fresh)
    log.info("trendline %s: %d symbols · slope >= %.2f · %d break(s) in the "
             "last %d bars · %d already sent · %d not fresh · %d fetch failed "
             "· %d SENT", "+".join(tfs), len(symbols), floor, seen,
             RECENT_BARS, dupe, stale, failed, sent)
    return sent


def _seconds_to_next_close(step: int, pad: int = 20) -> float:
    """Wake just after the bar closes. The pad is longer than the scanner's 10s
    because MEXC publishes a bar a little less promptly than the clock does,
    and a wake that lands before the close simply finds nothing."""
    now = time.time()
    return (step - (now % step)) + pad


def _due(db, seen_bucket: dict, now: float) -> tuple:
    """Which watched timeframes have a bar that closed since the last wake.

    Keyed on `now // step`, so it is self-correcting: a missed wake, a restart
    or a clock jump changes the bucket and the timeframe is simply scanned on
    the next pass rather than being skipped forever. On the very first wake
    every bucket is new, so everything is scanned once — and the freshness gate
    then decides whether any of it was recent enough to send.
    """
    out = []
    for tf in intervals(db):
        step = BAR_SECONDS[tf]
        bucket = int(now // step)
        if seen_bucket.get(tf) != bucket:
            seen_bucket[tf] = bucket
            out.append(tf)
    return tuple(out)


async def watch_loop(sess, db, state) -> None:
    """Run forever, waking on the fastest watched timeframe's close.

    Never exits on an error. app.py takes the whole process down when any
    supervised task finishes, and a watch list is not worth a restart — so the
    loop logs, sleeps and comes back, exactly like scan_loop.

    Every setting is re-read each iteration, so `/trendline 30m` or
    `/trendline slope 0.2` takes effect on the next close without a restart.
    """
    seen_bucket: dict = {}
    while True:
        tfs = intervals(db)
        step = min(BAR_SECONDS[t] for t in tfs)
        try:
            await asyncio.sleep(_seconds_to_next_close(step))
            if not enabled(db):
                continue
            due = _due(db, seen_bucket, time.time())
            if not due:
                continue
            n = await cycle(sess, db, state.get("symbols", []), due)
            state["trendline_cycle"] = time.time()
            state["trendline_sent"] = n
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.exception("trendline watch error: %s", e)
            await asyncio.sleep(60)


def set_enabled(db, on: bool) -> None:
    storage.meta_set(db, "trendline_alerts", "1" if on else "0")


def set_intervals(db, tfs) -> None:
    storage.meta_set(db, "trendline_tf", ",".join(tfs))


def set_min_slope(db, v: float) -> None:
    storage.meta_set(db, "trendline_min_slope", f"{max(0.0, v):.4f}")
