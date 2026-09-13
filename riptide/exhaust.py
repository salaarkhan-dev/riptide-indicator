"""Exhaustion-count heads-up alerts. A watch list, not a strategy.

WHAT THIS IS FOR. riptide-reversal.pine draws a 9-bar Momentum count and a
13-bar Terminal count on whatever chart you have open. Nobody can keep a
hundred charts open. This is the same answer the trendline watch gives:
one message per bar close saying which symbols just completed a count, with a
link straight to each chart at the right timeframe. "Which chart should I open"
— nothing more.

IT IS NOT A TRADE, AND UNLIKE THE TRENDLINE THE MEASUREMENT IS NOT MERELY
ABSENT — IT CAME BACK NEGATIVE. research/studies/exhaustion.py joined these
counts to Riptide's own signals over 333 days and 9118 trades. A 🎯 landing
near a completed count scored no better, and the control settles it: the
OPPOSITE direction benefited MORE (+0.273 against +0.093 on the picks, +0.281
against +0.096 on the full stream), and the only cells clearing 2 SE anywhere
in the table were control cells. Whatever these counts mark, it is not
exhaustion — it is a regime both sides ride.

So there is no entry, no stop, no target, no grade, and — deliberately — NO
OUTCOME TRACKING. Arming these would put rows with an invented entry into the
table that decides whether Riptide's strategies work.

COMPLETELY SEPARATE FROM RIPTIDE. Its own loop, its own timeframes, its own
dedupe table, its own message, its own on/off switch. It shares the candle
fetcher and the Telegram sender and nothing else. The loop body is wrapped
whole — a failure in a watch list must never cost a trade alert.

──────────────────────────────────────────────────────────────────────────────
THE VOLUME PROBLEM, WHICH DECIDED EVERY DEFAULT IN THIS FILE

Rows a day across the real universe, 59 symbols over 333 days, from
research/studies/exhaust_rate.py — rerun it rather than trusting this comment,
which is what the first version of this table needed and did not get:

    tf     M9/day   M9★/day   T13/day    both   both★
    15m      128        96        40      167     136
    30m       66        49        19       85      68
    1h        34        24         9       43      34
    ALL      227       169        68      295     237

These are ROWS, not messages — the watch sends one digest per bar close
carrying every symbol that completed on it, so 1h is at most 24 messages. Rows
are still the unit that decides anything, because a forty-row digest is the one
that does not get read.

Everything on is 295 rows a day: three and a half times Riptide's entire alert
volume and sixteen times the number of 🎯 picks. Shipping that would drown the
one thing in this chat with a measured effect, to add a stream that has none.

SO IT SHIPS OFF. RIPTIDE_EXHAUST_ALERTS defaults to 0 and this loop starts but
never sends until /exhaust on. When it is switched on it begins in the quiet
corner of the table — 1h only, and a plain M9 must be PERFECTED to count:
24 + 9 = 33 a day, beside the trendline digest's ~37. Everything else is one
config key or one /exhaust away; see riptide.conf.
"""

from __future__ import annotations

import asyncio
import time

from . import storage
from . import telegram as tg
from .config import (BAR_SECONDS, CONCURRENCY, EXHAUST_ALERTS,
                     EXHAUST_FRESH_BARS, EXHAUST_INTERVALS, EXHAUST_KINDS,
                     EXHAUST_MAX_LINES, EXHAUST_PERFECT_ONLY, log)
from .exchange import fetch_candles

# `from . import storage` rather than a direct import: storage.db_init()
# creates this module's table, so storage imports this module, and at that
# moment this module is only half-executed. Every use below is at call time.

# How far back to look for a completed count. Anything older cannot pass the
# freshness gate, so walking further would only fill the dedupe table.
RECENT_BARS = 6

# What the last close did, for /status. Empty until the first cycle — which is
# itself the answer when the watch has never woken.
last_cycle: dict = {}


def init(db) -> None:
    """The dedupe table. Its own, so an exhaustion count and a Riptide signal
    on the same symbol at the same minute cannot suppress each other."""
    db.execute("""CREATE TABLE IF NOT EXISTS seen_exhaust(
        sig TEXT PRIMARY KEY, symbol TEXT, side TEXT, kind TEXT, tf TEXT,
        bar_time INT, price REAL, perfect INT, sent_at INT)""")
    db.commit()


def sig_of(symbol: str, tf: str, bar_time: int, kind: str, is_long: bool) -> str:
    return f"EX|{symbol}|{tf}|{bar_time}|{kind}|{'U' if is_long else 'D'}"


def already_sent(db, sid: str) -> bool:
    return db.execute("SELECT 1 FROM seen_exhaust WHERE sig=?",
                      (sid,)).fetchone() is not None


def record(db, sid: str, h) -> None:
    db.execute("INSERT OR IGNORE INTO seen_exhaust VALUES(?,?,?,?,?,?,?,?,?)",
               (sid, h.symbol, "long" if h.is_long else "short", h.kind, h.tf,
                h.bar_time, h.price, 1 if h.perfect else 0, int(time.time())))
    db.commit()


def enabled(db) -> bool:
    """Live on/off: the /exhaust override if one is set, else the config."""
    v = storage.meta_get(db, "exhaust_alerts", "")
    return v == "1" if v in ("0", "1") else EXHAUST_ALERTS


def intervals(db) -> tuple:
    """Live timeframes: the /exhaust override if one is set, else the config.

    Validated on read rather than on write, so a database carrying a value this
    build no longer knows falls back instead of taking the loop down.
    """
    v = [i.strip() for i in
         storage.meta_get(db, "exhaust_tf", "").split(",") if i.strip()]
    good = tuple(dict.fromkeys(i for i in v if i in BAR_SECONDS))
    return good or tuple(i for i in EXHAUST_INTERVALS if i in BAR_SECONDS) \
        or ("Min60",)


def kinds(db) -> str:
    """'both', 'momentum' or 'terminal'. The single biggest volume control
    after the timeframe — terminal alone is a quarter of the traffic."""
    v = storage.meta_get(db, "exhaust_kinds", "")
    return v if v in ("both", "momentum", "terminal") else EXHAUST_KINDS


def perfect_only(db) -> bool:
    """Whether a plain M9 counts, or only a perfected one.

    On by default, and it is the cheapest useful filter here: a perfected count
    is 74% of all M9s, so this is not the volume lever the timeframe is — but
    an unperfected 9 is the weakest thing the indicator prints and it is the
    one most likely to be read as a signal.
    """
    v = storage.meta_get(db, "exhaust_perfect", "")
    return v == "1" if v in ("0", "1") else EXHAUST_PERFECT_ONLY


class Hit:
    """One completed count, with everything the digest line needs."""
    __slots__ = ("symbol", "tf", "is_long", "kind", "perfect", "bar_time",
                 "price", "level", "sig")


def _counts(cs):
    """The 9-count and the 13-count over a candle list.

    A PORT OF A PORT, AND DELIBERATELY SO. research/td.py already holds this
    logic, checked line by line against the Pine and covered by invariants —
    but research/ is not importable from the live bot and must not become so:
    it pulls in the whole study stack, and a research refactor must never be
    able to break a running scanner. The two are kept in step by hand, and the
    shared test (tests/test_exhaust.py) runs BOTH and asserts they agree bar
    for bar, so a drift fails rather than hides.
    """
    n = len(cs)
    out = [(0, 0, 0, 0, False, False, 0.0, 0.0)] * n
    if n < 6:
        return out
    buy = sell = buy_cd = sell_cd = 0
    buy_res = sell_sup = 0.0
    start_buy = start_sell = False
    buy_ref8 = sell_ref8 = 0.0
    res = []
    for i in range(n):
        c, h, lo = cs[i].c, cs[i].h, cs[i].l
        falling = i >= 4 and c < cs[i - 4].c
        rising = i >= 4 and c > cs[i - 4].c
        buy_flip = i >= 5 and falling and cs[i - 1].c > cs[i - 5].c
        sell_flip = i >= 5 and rising and cs[i - 1].c < cs[i - 5].c

        if falling:
            buy = (1 if buy_flip else 0) if buy in (0, 9) else buy + 1
            sell = 0
        elif rising:
            sell = (1 if sell_flip else 0) if sell in (0, 9) else sell + 1
            buy = 0
        else:
            buy = sell = 0

        if i >= 3:
            bperf = ((lo <= cs[i - 3].l and lo <= cs[i - 2].l)
                     or (cs[i - 1].l <= cs[i - 3].l
                         and cs[i - 1].l <= cs[i - 2].l))
            sperf = ((h >= cs[i - 3].h and h >= cs[i - 2].h)
                     or (cs[i - 1].h >= cs[i - 3].h
                         and cs[i - 1].h >= cs[i - 2].h))
        else:
            bperf = sperf = False

        if buy == 9:
            buy_res = max(x.h for x in cs[max(0, i - 8): i + 1])
        elif c > buy_res:
            buy_res = 0.0
        if sell == 9:
            sell_sup = min(x.l for x in cs[max(0, i - 8): i + 1])
        elif c < sell_sup:
            sell_sup = 0.0

        cd_buy = i >= 2 and c <= cs[i - 2].l
        cd_sell = i >= 2 and c >= cs[i - 2].h

        if buy == 9 and buy_cd == 0:
            start_buy = True
        elif sell == 9 or buy_cd == 13 or c > buy_res:
            start_buy = False
        if sell == 9 and sell_cd == 0:
            start_sell = True
        elif buy == 9 or sell_cd == 13 or c < sell_sup:
            start_sell = False

        if start_buy:
            if buy == 9:
                buy_cd = 1 if cd_buy else 0
            elif cd_buy:
                buy_cd += 1
        else:
            buy_cd = 0
        if start_sell:
            if sell == 9:
                sell_cd = 1 if cd_sell else 0
            elif cd_sell:
                sell_cd += 1
        else:
            sell_cd = 0

        if buy_cd == 13 and cd_buy and lo >= buy_ref8:
            buy_cd = 12
        if sell_cd == 13 and cd_sell and h <= sell_ref8:
            sell_cd = 12
        if buy_cd == 8 and (not res or res[-1][2] != 8):
            buy_ref8 = c
        if sell_cd == 8 and (not res or res[-1][3] != 8):
            sell_ref8 = c

        res.append((buy, sell, buy_cd, sell_cd,
                    bperf and buy == 9, sperf and sell == 9,
                    buy_res, sell_sup))
    return res


async def scan_symbol(sess, sem, symbol: str, tf: str, want: str,
                      perfect: bool) -> list:
    """Completed counts on this symbol in the last RECENT_BARS bars."""
    async with sem:
        cs = await fetch_candles(sess, symbol, tf)
    # The counts need history to be meaningful at all. Under this it is not a
    # quiet symbol, it is a symbol with no answer, and returning nothing
    # silently would look identical.
    if len(cs) < 60:
        return []
    k = _counts(cs)
    step = BAR_SECONDS[tf]
    out = []
    for i in range(max(0, len(cs) - RECENT_BARS), len(cs)):
        buy, sell, bcd, scd, bperf, sperf, _, _ = k[i]
        for kind, is_long, done, perf in (
                ("momentum", True, buy == 9, bperf),
                ("momentum", False, sell == 9, sperf),
                ("terminal", True, bcd == 13, False),
                ("terminal", False, scd == 13, False)):
            if not done:
                continue
            if want != "both" and want != kind:
                continue
            if kind == "momentum" and perfect and not perf:
                continue
            h = Hit()
            h.symbol, h.tf, h.is_long, h.kind, h.perfect = symbol, tf, is_long, kind, perf
            # Candle.t is the bar's OPEN and a count is only true once the bar
            # has CLOSED, so the moment it became real is t + step. That is
            # what the freshness gate and the "Nm ago" both measure from.
            h.bar_time = cs[i].t + step
            h.price = cs[i].c
            h.level = k[i][6] if is_long else k[i][7]
            h.sig = sig_of(symbol, tf, cs[i].t, kind, is_long)
            out.append(h)
    return out


def _label(h) -> str:
    return "T13" if h.kind == "terminal" else ("M9★" if h.perfect else "M9")


# The alerts' own label column is 8, which these overrun — the first render
# read "strong longSOL 1h", and 14 still butted "possible short" against the
# symbol because the word is exactly that long. This digest gets its own width
# rather than shortening a label that has to be unambiguous at a glance.
GROUP_W = 16


def _line(h, group: str) -> str:
    """One symbol in the digest. The label column carries the group only on
    its first row, so the rows under it read as a list."""
    return (f"<code>{group:<{GROUP_W}}</code>"
            f"<a href='{tg.tv_link(h.symbol, h.tf)}'>"
            f"<b>{h.symbol.replace('_USDT', '')}</b></a> "
            f"<code>{tg.tf_label(h.tf)}</code>  "
            f"<code>{tg.fmt(h.price)}</code>  <i>{_label(h)}</i>")


# Telegram rejects a body over 4096 characters and a real line is mostly the
# TradingView URL, which carries the symbol twice. Same budget and the same
# reasoning as watch.MAX_CHARS.
MAX_CHARS = 3950


def digest(hits: list, tfs, when: int) -> str:
    """The whole message, grouped by what a reader would do about it.

    Four groups in strength order, strongest first — a 13-count is the rarest
    thing here and a plain 9 the most common, so a reader who only reads the
    top of the message reads the rarest rows.
    """
    order = {("terminal", True): 0, ("terminal", False): 1,
             ("momentum", True): 2, ("momentum", False): 3}
    # The four words a reader actually asked for: a 13-count is the strongest
    # thing here, a 9-count is a maybe, and the arrow says which way without
    # needing the word "buy-side" explained again.
    names = {0: "STRONG LONG", 1: "STRONG SHORT",
             2: "possible long", 3: "possible short"}
    hits = sorted(hits, key=lambda h: (order[(h.kind, h.is_long)],
                                       -BAR_SECONDS[h.tf], h.symbol))
    clock = tg.local_clock()
    label_tf = "+".join(tg.tf_label(t) for t in tfs)
    head = (f"⚖ <b>EXHAUSTION</b> — {len(hits)} "
            f"count{'s' if len(hits) != 1 else ''} · {label_tf}"
            + (f" · {clock}" if clock else ""))
    sub = ("<i>a heads-up, not a trade — measured at no edge, and the "
           "opposite direction scored better. Go look.</i>")
    foot = "\n" + tg.row("when", f"<i>{tg.signal_age(when)}</i>")
    parts = [head, sub]
    used = len(head) + len(sub) + len(foot) + 40   # 40: the "+N more" line
    shown, last_group = 0, None
    for h in hits:
        g = order[(h.kind, h.is_long)]
        row = _line(h, names[g] if g != last_group else "")
        if shown >= EXHAUST_MAX_LINES or used + len(row) > MAX_CHARS:
            break
        if g != last_group:
            parts.append("")
            used += 1
        parts.append(row)
        used += len(row) + 1
        shown += 1
        last_group = g
    left = len(hits) - shown
    if left > 0:
        parts.append(f"<i>+{left} more this close</i>")
    parts.append(foot)
    return "\n".join(parts)


async def cycle(sess, db, symbols, tfs=None) -> int:
    """One pass over the universe, across every timeframe that just closed.

    Everything found is RECORDED, sent or not, exactly as the scanner does:
    dedupe has to cover the suppressed ones too, or a restart replays them.
    """
    tfs = tuple(tfs) if tfs else intervals(db)
    tfs = tuple(t for t in tfs if t in BAR_SECONDS)
    if not tfs:
        log.warning("exhaust: no valid interval configured, watch idle")
        return 0
    want, perfect = kinds(db), perfect_only(db)
    sem = asyncio.Semaphore(CONCURRENCY)
    jobs = [(s, tf) for tf in tfs for s in symbols]
    results = await asyncio.gather(
        *(scan_symbol(sess, sem, s, tf, want, perfect) for s, tf in jobs),
        return_exceptions=True)

    now = int(time.time())
    fresh: list = []
    seen = stale = dupe = failed = 0
    for r in results:
        if isinstance(r, Exception):
            failed += 1
            continue
        for h in r:
            seen += 1
            if already_sent(db, h.sig):
                dupe += 1
                continue
            record(db, h.sig, h)
            # Counted in BARS of that count's OWN timeframe. A single global
            # window would either bin the slower timeframe or let the faster
            # one go stale.
            if now - h.bar_time > EXHAUST_FRESH_BARS * BAR_SECONDS[h.tf]:
                stale += 1
                continue
            fresh.append(h)

    # /pause is one switch over everything the bot sends.
    paused = storage.meta_get(db, "alerts_paused", "0") == "1"
    sent = 0
    if fresh and not paused:
        if await tg.tg_send(sess, digest(fresh, tfs,
                                         max(h.bar_time for h in fresh))):
            sent = len(fresh)
    log.info("exhaust %s: %d symbols · %s%s · %d found in the last %d bars · "
             "%d already sent · %d not fresh · %d fetch failed · %d SENT",
             "+".join(tfs), len(symbols), want,
             ", perfected only" if perfect else "", seen, RECENT_BARS,
             dupe, stale, failed, sent)
    # Published for /status. THE ONE QUESTION A QUIET ALERT SERVICE HAS TO
    # ANSWER IS WHY IT WAS QUIET, and a lifetime row count cannot.
    last_cycle.update(at=now, tfs=tfs, kinds=want, perfect=perfect, seen=seen,
                      dupe=dupe, stale=stale, failed=failed, sent=sent)
    return sent


def _seconds_to_next_close(step: int, pad: int = 20) -> float:
    """Wake just after the bar closes. The pad is longer than the scanner's 10s
    because MEXC publishes a bar a little less promptly than the clock does."""
    now = time.time()
    return (step - (now % step)) + pad


def _due(db, seen_bucket: dict, now: float) -> tuple:
    """Which watched timeframes have a bar that closed since the last wake.

    Keyed on `now // step`, so it is self-correcting: a missed wake, a restart
    or a clock jump changes the bucket and the timeframe is simply scanned on
    the next pass rather than being skipped forever.
    """
    out = []
    for tf in intervals(db):
        step = BAR_SECONDS[tf]
        bucket = int(now // step)
        if seen_bucket.get(tf) != bucket:
            seen_bucket[tf] = bucket
            out.append(tf)
    return tuple(out)


async def exhaust_loop(sess, db, state) -> None:
    """Run forever, waking on the fastest watched timeframe's close.

    Never exits on an error. app.py takes the whole process down when any
    supervised task finishes, and a watch list is not worth a restart.

    Every setting is re-read each iteration, so /exhaust takes effect on the
    next close without a restart.
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
            state["exhaust_cycle"] = time.time()
            state["exhaust_sent"] = n
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.exception("exhaustion watch error: %s", e)
            await asyncio.sleep(60)


def set_enabled(db, on: bool) -> None:
    storage.meta_set(db, "exhaust_alerts", "1" if on else "0")


def set_intervals(db, tfs) -> None:
    storage.meta_set(db, "exhaust_tf", ",".join(tfs))


def set_kinds(db, v: str) -> None:
    storage.meta_set(db, "exhaust_kinds", v)


def set_perfect(db, on: bool) -> None:
    storage.meta_set(db, "exhaust_perfect", "1" if on else "0")
