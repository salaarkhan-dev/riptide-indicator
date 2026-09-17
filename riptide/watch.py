"""The heads-up watch: one engine, any number of indicators.

WHAT A WATCH IS FOR. TradingView will alert on a line you drew yourself; it
will not alert on an indicator across sixty pairs, and nobody can keep sixty
charts open to see which one just did something. That is the entire product:
one message per bar close saying which symbols did something, with a link
straight to each chart at the right timeframe. The answer to "which chart
should I open" — nothing more.

NOTHING HERE IS A TRADE, AND EVERY DIGEST SAYS SO IN ITS OWN SUBTITLE. There is
no entry, no stop, no target, no grade, and — deliberately, not by oversight —
NO OUTCOME TRACKING. Riptide arms every signal it sends so /stats can score it
forward; that machinery exists to judge trades, and arming a heads-up would put
rows with an invented entry and an invented stop into the same table that
decides whether Riptide's strategies work. A heads-up has no outcome. It is not
scored because there is nothing to score.

COMPLETELY SEPARATE FROM RIPTIDE. Its own loops, its own timeframes, its own
dedupe table, its own messages, its own on/off switches. It shares the candle
fetcher and the Telegram sender and nothing else: no cluster, no POI, no grade,
no sweep_worth, and none of Riptide's settings reach it. Each loop body is
wrapped whole — a failure in a watch list must never be able to cost a trade
alert, which is the same reasoning that already wraps `_arm` and the market
logger in the scanner.

ONE DIGEST PER BAR CLOSE, NOT ONE MESSAGE PER HIT, AND NOT ONE PER TIMEFRAME.
Bar closes are synchronised across the universe, so hits do not arrive spread
out — they arrive together. Measured over 60 symbols, the worst single 4h close
had 20 symbols fire at once. Twenty separate messages in one second is
unreadable and is past Telegram's per-chat rate limit; one message listing
twenty symbols is a glance. A 30m close is also a 15m close, so those go in the
same message too. A quiet close sends nothing at all.

WHY EACH RUNS ON ITS OWN TIMER rather than inside the scan cycle: the scanner
wakes on the fastest structure timeframe and fetches Riptide's intervals. A
watch needs a different interval on a different schedule, and hanging it off
the scan cycle would mean either fetching 4h candles every few minutes and
throwing them away, or letting a watch list decide when Riptide scans. At Hour4
one watch is 6 wakes a day x 60 symbols = 360 requests, against the scanner's
thousands.

──────────────────────────────────────────────────────────────────────────────
THIS FILE IS THE PLUMBING AND NOTHING ELSE. It used to be the trendline watch,
and `exhaust.py` was a copy of it with the nouns changed — ~300 duplicated
lines, fixed twice, including the digest character budget which was found and
fixed a month apart in each copy. What varies between indicators is the
detector, the digest row and the grouping; everything below is what they all
need. See `riptide/watchers/__init__.py` for what an indicator declares.
"""

from __future__ import annotations

import asyncio
import time

from . import storage
from . import telegram as tg
from .config import BAR_SECONDS, CONCURRENCY, log
from .exchange import fetch_candles
from .watchers import Hit, Indicator

# `from . import storage` rather than `from .storage import meta_get`, and the
# reason is a circular import: storage.db_init() creates this module's table,
# so storage imports watch, and by the time watch runs, storage is only
# half-executed — meta_get does not exist yet to be bound. The module object
# does exist, and every use below is at call time, long after both are loaded.

# What each watch's last close actually did, keyed by indicator name. Empty
# until that watch first wakes — which is itself the answer when it never has.
last_cycle: dict = {}


# ------------------------------------------------------------------ state


def init(db) -> None:
    """The dedupe table. ONE table for every watch, keyed by indicator.

    Its own table, and deliberately not part of any of Riptide's: nothing in it
    is a trade and none of it may reach the tables /stats scores.

    The primary key is (watcher, sig) rather than sig alone, so two indicators
    that happen to build the same signature string cannot suppress each other —
    an indicator only has to be unique within itself.
    """
    db.execute("""CREATE TABLE IF NOT EXISTS seen_watch(
        watcher TEXT, sig TEXT, symbol TEXT, side TEXT, tf TEXT,
        bar_time INT, price REAL, detail TEXT, sent_at INT,
        PRIMARY KEY(watcher, sig))""")
    # The exhaustion watch had its own table before this one existed. Its rows
    # are carried over rather than abandoned: dropping them would re-send every
    # count on the most recent bar of every watched timeframe on the first
    # close after an update, which is precisely the flood the dedupe exists to
    # stop. INSERT OR IGNORE, so running it again is free.
    if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND "
                  "name='seen_exhaust'").fetchone():
        db.execute("""INSERT OR IGNORE INTO seen_watch
                      SELECT 'exhaust', sig, symbol, side, tf, bar_time, price,
                             kind || (CASE WHEN perfect THEN '*' ELSE '' END),
                             sent_at FROM seen_exhaust""")
    # `seen_trendline` may also exist. It is NOT migrated and NOT dropped: the
    # trendline indicator was removed, so its dedupe keys describe an indicator
    # nothing can produce any more, and dropping a user's table to tidy up is
    # not worth the one thing it could ever cost.
    db.commit()


def _key(ind: Indicator, suffix: str) -> str:
    """A meta key for one indicator's setting.

    `<name>_alerts` and `<name>_tf` deliberately match the keys the exhaustion
    watch already used, so an existing database keeps its switch positions
    across this refactor instead of silently reverting to the config.
    """
    return f"{ind.name}_{suffix}"


def enabled(db, ind: Indicator) -> bool:
    """Live on/off: the /name override if one is set, else the config."""
    v = storage.meta_get(db, _key(ind, "alerts"), "")
    return v == "1" if v in ("0", "1") else ind.default_enabled


def set_enabled(db, ind: Indicator, on: bool) -> None:
    storage.meta_set(db, _key(ind, "alerts"), "1" if on else "0")


def intervals(db, ind: Indicator) -> tuple:
    """Live timeframes: the /name override if one is set, else the config.

    Validated on read rather than on write, so a database carrying a value this
    build no longer knows falls back instead of taking the loop down.
    """
    v = [i.strip() for i in
         storage.meta_get(db, _key(ind, "tf"), "").split(",") if i.strip()]
    good = tuple(dict.fromkeys(i for i in v if i in BAR_SECONDS))
    return good or tuple(i for i in ind.default_intervals if i in BAR_SECONDS) \
        or (ind.fallback_interval,)


def set_intervals(db, ind: Indicator, tfs) -> None:
    storage.meta_set(db, _key(ind, "tf"), ",".join(tfs))


def setting(db, ind: Indicator, key: str):
    """One declared Option's live value, falling back to its default."""
    o = ind.option(key)
    if o is None:
        raise KeyError(f"{ind.name} has no option {key!r}")
    return o.read(storage.meta_get(db, _key(ind, key), ""))


def set_setting(db, ind: Indicator, key: str, value) -> None:
    o = ind.option(key)
    if o is None:
        raise KeyError(f"{ind.name} has no option {key!r}")
    raw = ("1" if value else "0") if o.kind == "bool" else str(value)
    storage.meta_set(db, _key(ind, key), raw)


def settings(db, ind: Indicator) -> dict:
    """Every declared Option at once — what gets handed to `detect`."""
    return {o.key: setting(db, ind, o.key) for o in ind.options}


def already_sent(db, ind: Indicator, sig: str) -> bool:
    return db.execute("SELECT 1 FROM seen_watch WHERE watcher=? AND sig=?",
                      (ind.name, sig)).fetchone() is not None


def record(db, ind: Indicator, h: Hit) -> None:
    db.execute("INSERT OR IGNORE INTO seen_watch VALUES(?,?,?,?,?,?,?,?,?)",
               (ind.name, h.key, h.symbol, "up" if h.is_long else "down", h.tf,
                h.bar_time, h.price, h.detail, int(time.time())))
    db.commit()


def recorded(db, ind: Indicator) -> int:
    """Lifetime rows, for /status."""
    return db.execute("SELECT COUNT(*) FROM seen_watch WHERE watcher=?",
                      (ind.name,)).fetchone()[0]


# ------------------------------------------------------------------ scan


async def scan_symbol(sess, sem, ind: Indicator, symbol: str,
                      tf: str, opts: dict) -> tuple:
    """(hits, dropped_by_the_indicator's_own_gates) for one symbol.

    The drop count comes back rather than being discarded because it is the
    answer to the only question a quiet watch list ever raises: is it broken,
    or was there nothing to say? "18 found, all below the gate" and "0 found"
    look identical from the chat and mean completely different things.

    A symbol with too little history returns nothing AND is logged, because an
    indicator that needs 260 bars on a pair listed last week is not quiet, it
    is unanswerable, and the two look the same from here.
    """
    async with sem:
        cs = await fetch_candles(sess, symbol, tf)
    if len(cs) < ind.min_bars:
        if cs:
            log.debug("%s: %s %s only %d bars, skipped", ind.name, symbol, tf,
                      len(cs))
        return [], 0
    return ind.detect(cs, symbol, tf, opts)


# --------------------------------------------------------------- digest


# Telegram rejects a sendMessage body over 4096 characters. This leaves room
# for the footer and for the "+N more" line appended after the budget is spent.
#
# THE LINE COUNT ALONE IS NOT ENOUGH TO STAY UNDER IT, and the test that found
# this used three-letter symbols and came out at 3876 characters for 25 lines —
# comfortably inside the cap, and wrong. A real line is mostly the TradingView
# URL, which carries the symbol twice, so TRUMPOFFICIAL costs about 20
# characters more than XRP. Twenty-five of those is over the cap, and the way
# Telegram says so is by refusing the message: the digest that fails is the
# market-wide one, which is the only digest anybody urgently wanted.
#
# The margin is larger than it looks: this counts RAW HTML, and Telegram's 4096
# applies to the message after entity parsing, where every tag and every href
# has become an entity and costs nothing. A row's ~180 raw characters are about
# 50 of text. 3950 is therefore still conservative by a wide margin, and is
# kept below 4096 anyway so the arithmetic never has to be trusted.
#
# THIS NUMBER WAS FIXED TWICE, once in each copy of this file, a month apart.
# That is the whole argument for there being one copy of it.
MAX_CHARS = 3950


def digest(ind: Indicator, hits: list, tfs, when: int) -> str:
    """The whole message: a header, the caveat, grouped rows, one footer.

    Deliberately flat and short. Every row is a link, and the ordering is the
    only recommendation offered — the indicator's `classify` decides it.

    Trimmed by BOTH a line count and a character budget; see MAX_CHARS.
    """
    tagged = sorted(((ind.classify(h), h) for h in hits), key=lambda p: p[0])
    clock = tg.local_clock()
    label_tf = "+".join(tg.tf_label(t) for t in tfs)
    head = (f"{ind.glyph} <b>{ind.title}</b> — {len(hits)} "
            f"{ind.unit}{'s' if len(hits) != 1 else ''} · {label_tf}"
            + (f" · {clock}" if clock else ""))
    # See Indicator.caveat_in_digest. The caveat always exists and /name
    # always prints it; this is only whether every message repeats it.
    sub = f"<i>{ind.caveat}</i>" if ind.caveat_in_digest else ""
    # The same `when` row every other alert ends on, so a digest is not the one
    # message in the bot with its own footer shape.
    foot = "\n" + tg.row("when", f"<i>{tg.signal_age(when)}</i>")
    parts = [head, sub] if sub else [head]
    used = len(head) + len(sub) + len(foot) + 40    # 40: the "+N more" line
    shown, last_group = 0, None
    for (_sort, group), h in tagged:
        row = ind.row(h, group if group != last_group else "")
        if shown >= ind.max_lines or used + len(row) > MAX_CHARS:
            break
        if group != last_group:
            parts.append("")
            used += 1
        parts.append(row)
        used += len(row) + 1
        shown += 1
        last_group = group
    left = len(hits) - shown
    if left > 0:
        parts.append(f"<i>+{left} more this close</i>")
    parts.append(foot)
    return "\n".join(parts)


def label(ind: Indicator, text: str) -> str:
    """The fixed-width group column every digest row starts with.

    Every row has one, blank on all but the first of its block, so the rows
    under a label indent into the same column — which is what a list looks like
    once its header has been read.
    """
    return f"<code>{text:<{ind.label_w}}</code>"


def chart(h: Hit) -> str:
    """The clickable symbol and its timeframe.

    THE TIMEFRAME IS ON EVERY LINE, always, even when the whole digest is one
    timeframe. It used to appear only when a digest mixed two, on the reasoning
    that a header saying "15m+30m" plus a single tag was the same fact twice —
    which was wrong in the way that matters. The tag answers "which chart am I
    opening", and the reader is looking at one line, not auditing the header
    against it. A conditional tag is also worse than either choice on its own:
    the lines change shape between messages, so the eye has to re-find the
    price column each time.
    """
    return (f"<a href='{tg.tv_link(h.symbol, h.tf)}'>"
            f"<b>{h.symbol.replace('_USDT', '')}</b></a> "
            f"<code>{tg.tf_label(h.tf)}</code>  "
            f"<code>{tg.fmt(h.price)}</code>")


# ---------------------------------------------------------------- cycle


async def cycle(sess, db, ind: Indicator, symbols, tfs=None) -> int:
    """One pass over the universe, across every timeframe that just closed.

    ONE DIGEST covering all of them, not one per timeframe: a 30m close is also
    a 15m close, and two messages arriving in the same second is the thing the
    digest exists to prevent.

    Everything the indicator returns is RECORDED, sent or not, exactly as the
    scanner does: dedupe has to cover the hits that were suppressed too, or a
    restart replays them. What the indicator's OWN gates dropped is NOT
    recorded — recording those would make lowering a gate later silent, because
    dedupe would already have claimed every one of them.
    """
    tfs = tuple(tfs) if tfs else intervals(db, ind)
    tfs = tuple(t for t in tfs if t in BAR_SECONDS)
    if not tfs:
        log.warning("%s: no valid interval configured, watch idle", ind.name)
        return 0
    opts = settings(db, ind)
    sem = asyncio.Semaphore(CONCURRENCY)
    jobs = [(s, tf) for tf in tfs for s in symbols]
    results = await asyncio.gather(
        *(scan_symbol(sess, sem, ind, s, tf, opts) for s, tf in jobs),
        return_exceptions=True)

    now = int(time.time())
    fresh: list = []
    seen = stale = dupe = failed = dropped = 0
    for r in results:
        if isinstance(r, Exception):
            failed += 1
            continue
        hits, n_dropped = r
        dropped += n_dropped
        for h in hits:
            seen += 1
            if already_sent(db, ind, h.key):
                dupe += 1
                continue
            record(db, ind, h)
            # Counted in BARS of that hit's OWN timeframe — a 30m hit gets a
            # 30m window, a 15m hit a 15m one. A single global window would
            # either bin the slower timeframe or let the faster one go stale.
            if now - h.bar_time > ind.fresh_bars * BAR_SECONDS[h.tf]:
                stale += 1
                continue
            fresh.append(h)

    # /pause is one switch over everything the bot sends, and a watch list that
    # kept talking through it would make the switch useless. `/pause riptide`
    # is the narrower one: silence the measured alerts and leave the watches
    # running, which is what switching a watch on is usually for.
    paused = storage.paused_for(db, "watch")
    sent = 0
    if fresh and not paused:
        if await tg.tg_send(sess, digest(ind, fresh, tfs,
                                         max(h.bar_time for h in fresh))):
            sent = len(fresh)
    log.info("%s %s: %d symbols · %d %s(s) in the last %d bars · %d below its "
             "own gates · %d already sent · %d not fresh · %d fetch failed · "
             "%d SENT", ind.name, "+".join(tfs), len(symbols), seen, ind.unit,
             ind.recent_bars, dropped, dupe, stale, failed, sent)
    # Published for /status. THE ONE QUESTION A QUIET ALERT SERVICE HAS TO BE
    # ABLE TO ANSWER IS WHY IT WAS QUIET, and a lifetime row count cannot: "18
    # found, all below the gate" and "the loop is not running" look the same
    # from the chat. The scanner already learned this and keeps `state_gate`
    # for the same reason.
    last_cycle[ind.name] = dict(at=now, tfs=tfs, seen=seen, dropped=dropped,
                                dupe=dupe, stale=stale, failed=failed,
                                sent=sent, opts=opts)
    return sent


# ----------------------------------------------------------------- loop


def _seconds_to_next_close(step: int, pad: int = 20) -> float:
    """Wake just after the bar closes. The pad is longer than the scanner's 10s
    because MEXC publishes a bar a little less promptly than the clock does,
    and a wake that lands before the close simply finds nothing."""
    now = time.time()
    return (step - (now % step)) + pad


def _due(db, ind: Indicator, seen_bucket: dict, now: float) -> tuple:
    """Which watched timeframes have a bar that closed since the last wake.

    Keyed on `now // step`, so it is self-correcting: a missed wake, a restart
    or a clock jump changes the bucket and the timeframe is simply scanned on
    the next pass rather than being skipped forever. On the very first wake
    every bucket is new, so everything is scanned once — and the freshness gate
    then decides whether any of it was recent enough to send.
    """
    out = []
    for tf in intervals(db, ind):
        step = BAR_SECONDS[tf]
        bucket = int(now // step)
        if seen_bucket.get(tf) != bucket:
            seen_bucket[tf] = bucket
            out.append(tf)
    return tuple(out)


async def watch_loop(sess, db, ind: Indicator, state) -> None:
    """Run one indicator forever, waking on its fastest timeframe's close.

    Never exits on an error. app.py takes the whole process down when any
    supervised task finishes, and a watch list is not worth a restart — so the
    loop logs, sleeps and comes back, exactly like scan_loop.

    Every setting is re-read each iteration, so `/exhaust 30m` takes effect on
    the next close without a restart.
    """
    seen_bucket: dict = {}
    while True:
        tfs = intervals(db, ind)
        step = min(BAR_SECONDS[t] for t in tfs)
        try:
            await asyncio.sleep(_seconds_to_next_close(step))
            if not enabled(db, ind):
                continue
            due = _due(db, ind, seen_bucket, time.time())
            if not due:
                continue
            n = await cycle(sess, db, ind, state.get("symbols", []), due)
            state[f"{ind.name}_cycle"] = time.time()
            state[f"{ind.name}_sent"] = n
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.exception("%s watch error: %s", ind.name, e)
            await asyncio.sleep(60)
