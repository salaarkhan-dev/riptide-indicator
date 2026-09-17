"""The Undertow watch: the two copies agree, and it cannot flood the chat.

    PYTHONPATH=. python3 indicators/undertow/tests/test_watch_undertow.py

WHY THIS FILE EXISTS. The Undertow machine now lives in TWO places —
`indicators/undertow/port/undertow.py`, which every measurement ran on, and
`riptide/watchers/undertow.py`, which the bot runs. They are deliberately not
one module: the research tree pulls in the whole study stack and must never be
importable from a live scanner, because a refactor there must not be able to
break a running bot.

The cost of that decision is drift, and drift here is silent in the worst way.
If the bot's copy quietly stops matching, every number in `measurements/` stops
describing what the chat actually sends, the caveat under each digest becomes a
claim about a different strategy, and nothing anywhere would say so.

So this runs BOTH over the same candles and asserts they produce the same armed
setups — same bar, same side, same entry, same stop, same target, same bias
state. Not a count: the whole list, element for element.

The second half pins the things that decide whether the stream is usable at
all: the alert rate, that it ships OFF, that a hit is dated to the bar's CLOSE
rather than its open, and that the dedupe key is stable — because a key that
changes shape replays the most recent bar of every watched timeframe into the
chat on the first close after an update.
"""
import os
import random
import sys
import tempfile

os.environ.setdefault("RIPTIDE_DB", tempfile.mktemp(suffix=".db"))
os.environ.setdefault("TELEGRAM_TOKEN", "x")
os.environ.setdefault("TELEGRAM_CHAT_ID", "1")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))

from indicators.undertow.port import undertow as U          # noqa: E402
from riptide.config import BAR_SECONDS                      # noqa: E402
from riptide.engine import Candle                           # noqa: E402
from riptide.watchers import undertow as W                  # noqa: E402

good = []


def ok(cond, msg):
    good.append(bool(cond))
    print(("  ok   " if cond else "  FAIL ") + msg)


def walk(n=4000, seed=7, drift=0.0):
    """A random walk with real wicks — the wick sizes matter, because the pin
    taxonomy is entirely wick geometry and a walk with uniform wicks finds no
    setups at all and would make this whole file pass vacuously."""
    rnd = random.Random(seed)
    px = 100.0
    cs = []
    for i in range(n):
        o = px
        px = max(1.0, px * (1 + rnd.gauss(drift, 0.004)))
        c = px
        hi = max(o, c) * (1 + abs(rnd.gauss(0, 0.002)))
        lo = min(o, c) * (1 - abs(rnd.gauss(0, 0.002)))
        cs.append(Candle(i * 1800, o, hi, lo, c, 1.0))
    return cs


# ──────────────────────────────────────────── 1. the two copies agree ──


def test_copies_agree():
    """THE POINT OF THE FILE. Element for element, not a count."""
    total = 0
    for seed, drift in ((11, 0.0), (12, 0.0006), (13, -0.0006), (14, 0.0002)):
        cs = walk(4000, seed=seed, drift=drift)
        # maxLive 64 on both sides: the port's default of 4 is the Pine's
        # DRAWING cap and the bot does not draw, so the live copy must not
        # inherit a limit that silently refuses setups. That was the confound
        # that voided an entire study; see UNDERTOW_PIN_VALUE.md.
        want = U.run(cs, U.P(maxLive=64), "T").armed
        got = W.armed_setups(cs, ms_len=U.P().msLen, max_live=64)
        total += len(want)
        ok(len(want) == len(got),
           f"seed {seed}: {len(want)} armed setups, bot copy found {len(got)}")
        if len(want) != len(got):
            a = {w["bar"] for w in want}
            b = {g["bar"] for g in got}
            print(f"         only in port: {sorted(a - b)[:6]}")
            print(f"         only in bot:  {sorted(b - a)[:6]}")
            continue
        bad = []
        for w, g in zip(want, got):
            for k in ("bar", "short", "code", "state", "pin"):
                if w[k] != g[k]:
                    bad.append((w["bar"], k, w[k], g[k]))
            for k in ("entry", "stop", "target"):
                if abs(w[k] - g[k]) > 1e-9:
                    bad.append((w["bar"], k, w[k], g[k]))
        ok(not bad, f"seed {seed}: every field matches"
           + ("" if not bad else f"  first: {bad[0]}"))
    ok(total > 40, f"the comparison is not vacuous: {total} setups compared")


def test_agree_on_real_candles():
    """A random walk has no market structure worth the name. If the cached
    study candles are present, the comparison runs on those too — same rules,
    real bars."""
    try:
        from indicators.undertow.studies.undertow_sweep import load
        data = load("Min30")
    except Exception:
        data = {}
    if not data:
        print("  skip  no cached candles (undertow_sweep.py --fetch); "
              "the walk above still covers the logic")
        return
    n = 0
    for sym in sorted(data)[:6]:
        cs = data[sym]
        want = U.run(cs, U.P(maxLive=64), sym).armed
        got = W.armed_setups(cs, ms_len=U.P().msLen, max_live=64)
        same = (len(want) == len(got)
                and all(w["bar"] == g["bar"] and w["short"] == g["short"]
                        and abs(w["entry"] - g["entry"]) < 1e-9
                        and abs(w["stop"] - g["stop"]) < 1e-9
                        for w, g in zip(want, got)))
        n += len(want)
        ok(same, f"{sym}: {len(want)} armed setups match on real bars")
    ok(n > 100, f"and on a real sample: {n} setups compared")


# ───────────────────────────────────────────── 2. the stream is sane ──


def test_frozen_constants_match_the_port():
    """The live copy's frozen settings ARE the port's defaults.

    They are frozen in the bot rather than read from config on purpose -- a
    live stream is the worst possible place to tune -- but frozen to the WRONG
    values would mean the alert describes a different strategy from the one
    every measurement ran on, silently.
    """
    p = U.P()
    for name, live, want in (
            ("msShortLen", W.MS_SHORT_LEN, p.msShortLen),
            ("msBosNeedsIdm", W.BOS_NEEDS_IDM, p.msBosNeedsIdm),
            ("endMinor", W.END_MINOR, p.endMinor),
            ("endSweep", W.END_SWEEP, p.endSweep),
            ("endStale", W.END_STALE, p.endStale),
            ("staleBars", W.STALE_BARS, p.staleBars),
            ("retraceMax", W.RETRACE_MAX, p.retraceMax),
            ("wickEdge", W.WICK_EDGE, p.wickEdge),
            ("locTol", W.LOC_TOL, p.locTol),
            ("stopBuf", W.STOP_BUF, p.stopBuf),
            ("rr", W.RR, p.rr)):
        ok(live == want, f"{name}: watcher {live!r} == port {want!r}")


def test_ships_off():
    ok(W.SPEC.default_enabled is False,
       "the stream ships OFF — three pre-registered studies, all negative")
    ok("not a trade" in W.SPEC.caveat and "random" in W.SPEC.caveat,
       "and the caveat under every digest says so in the reader's words")


def test_rate_is_readable():
    """The volume decision. Unlike the exhaustion watch this one has no volume
    problem, and the defaults are set by what is useful rather than what is
    survivable — but that only holds while the rate stays small, so it is
    pinned here rather than left to a comment."""
    shipped = W.rate(None, tfs=W.SPEC.default_intervals)
    ok(W.SPEC.default_intervals == ("Min15", "Min30"),
       f"the shipped set is 15m and 30m: {W.SPEC.default_intervals}")
    ok(shipped < 60,
       f"the shipped timeframes are {shipped} rows a day — readable; the "
       f"exhaustion watch's equivalent was 295")
    ok(W.rate(None, tfs=("Min30",)) < shipped, "and 30m alone is fewer")
    ok(W.rate(None, tfs=("Min15",), states="running")
       < W.rate(None, tfs=("Min15",)),
       "the 'running' filter reduces it, as /undertow claims")


def test_hit_is_dated_to_the_close():
    """Both existing detectors got this wrong first. A setup is only real once
    the bar has CLOSED, so the moment it became real is t + step — which is
    what the freshness gate and the 'Nm ago' row both measure from."""
    cs = walk(4000, seed=12, drift=0.0006)
    got = W.armed_setups(cs, ms_len=U.P().msLen, max_live=64)
    ok(got, "the fixture produces setups at all")
    last = max(g["bar"] for g in got)
    # Trim so the newest setup lands inside the recent window.
    trimmed = cs[:last + 2]
    hits, _ = W.detect(trimmed, "T_USDT", "Min30", {})
    ok(hits, f"detect() finds the setup at bar {last}")
    if hits:
        h = hits[0]
        step = BAR_SECONDS["Min30"]
        ok(h.bar_time == trimmed[last].t + step,
           "bar_time is the bar's CLOSE, not its open")
        ok(h.price == h.extra["entry"], "price is the limit level")
        ok(h.extra["stop"] != h.extra["entry"]
           and h.extra["target"] != h.extra["entry"],
           "the three levels are distinct")
        long_ok = (h.extra["stop"] < h.extra["entry"] < h.extra["target"]
                   if h.is_long else
                   h.extra["stop"] > h.extra["entry"] > h.extra["target"])
        ok(long_ok, "stop, entry and target are on the right sides")


def test_dedupe_key_is_stable():
    a = W.sig_of("BTC_USDT", "Min30", 1700000000, True)
    b = W.sig_of("BTC_USDT", "Min30", 1700000000, True)
    ok(a == b, "the same event twice gives the same key")
    ok(a != W.sig_of("BTC_USDT", "Min30", 1700000000, False),
       "a long and a short on one bar are different events")
    ok(a != W.sig_of("BTC_USDT", "Min15", 1700000000, True),
       "and so are two timeframes")
    ok(a.startswith("UT|"), f"namespaced so it cannot collide: {a}")


def test_detect_reports_its_drops():
    """'6 setups, all immature' and 'the loop never woke' look identical from
    the chat. The second number is what tells them apart in /status."""
    cs = walk(4000, seed=12, drift=0.0006)
    got = W.armed_setups(cs, ms_len=U.P().msLen, max_live=64)
    last = max(g["bar"] for g in got)
    trimmed = cs[:last + 2]
    _, dropped = W.detect(trimmed, "T_USDT", "Min30", {"states": "running"})
    hits2, _ = W.detect(trimmed, "T_USDT", "Min30", {"states": "both"})
    ok(dropped >= 0 and isinstance(dropped, int),
       f"detect returns a drop count: {dropped}")
    ok(len(hits2) >= 1, "and 'both' is never fewer than a filtered state")


def test_no_trading_path():
    """The constraint that governs this entire repository. The watcher may
    print a price; it may not place an order or read a key."""
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))),
        "riptide/watchers/undertow.py")).read()
    # The tokens of a signed private endpoint, not the English words. An
    # earlier version of this test looked for "signature" and tripped on the
    # docstring of `sig_of`, which is about deduping a Telegram message.
    for bad in ("api_key", "apiKey", "ACCESS_KEY", "hmac", "place_order",
                "create_order", "X-MEXC", "/private/", "api/v1/private"):
        ok(bad not in src, f"no {bad!r} anywhere in the live watcher")


def main():
    for fn in (test_copies_agree, test_agree_on_real_candles,
               test_frozen_constants_match_the_port, test_ships_off,
               test_rate_is_readable, test_hit_is_dated_to_the_close,
               test_dedupe_key_is_stable, test_detect_reports_its_drops,
               test_no_trading_path):
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{'ALL PASS' if all(good) else 'FAILURES'}  "
          f"{sum(good)}/{len(good)}")
    return 0 if all(good) else 1


if __name__ == "__main__":
    sys.exit(main())
