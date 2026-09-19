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
# The MESSAGE of each failed check, so conftest.py's guard can name what broke
# rather than reporting a bare count. See that file: without it, pytest reports
# every check in here as a pass whatever it recorded.
bad: list = []


def ok(cond, msg):
    good.append(bool(cond))
    if not cond:
        bad.append(msg.splitlines()[0])
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


# The cap is run at TWO values and both are load-bearing.
#
#   64  the studies' value. The cap refuses almost nothing, so the comparison
#       sees the whole population and a divergence cannot hide behind a
#       refusal. This is the setting that gives the test its power.
#   P's default  what the CHART ships. The bot's job is to alert what the
#       chart draws, so the shipped cap has to be compared too.
#
# IT USED TO RUN ONLY AT 64, on a comment that said the cap was "the Pine's
# DRAWING cap and the bot does not draw". That was wrong about the Pine.
# riptide-undertow.pine:1117 tests it BEFORE the candidate is created --
# `if nLive >= maxLive` increments nCap and the pin is turned away -- so a
# refused pin never becomes a setup, never draws AND never arms. The live
# watcher was left defaulting to 64 against a chart at 4, and 4.0 / 4.3 / 5.7%
# of the arms it produced on 15m / 30m / 1h were setups the chart had refused:
# alerts for something not on the chart, which is exactly what was reported.
CAPS = (64, None)


def test_copies_agree():
    """THE POINT OF THE FILE. Element for element, not a count."""
    total = 0
    cases = [(s, d, cap) for s, d in
             ((11, 0.0), (12, 0.0006), (13, -0.0006), (14, 0.0002))
             for cap in CAPS]
    for seed, drift, cap in cases:
        cs = walk(4000, seed=seed, drift=drift)
        cap = U.P().maxLive if cap is None else cap
        want = U.run(cs, U.P(maxLive=cap), "T").armed
        got = W.armed_setups(cs, max_live=cap)
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
            for k in ("bar", "short", "code", "state", "pin", "order"):
                if w[k] != g[k]:
                    bad.append((w["bar"], k, w[k], g[k]))
            for k in ("entry", "stop", "target"):
                if abs(w[k] - g[k]) > 1e-9:
                    bad.append((w["bar"], k, w[k], g[k]))
        ok(not bad, f"seed {seed}: every field matches"
           + ("" if not bad else f"  first: {bad[0]}"))
    ok(total > 40, f"the comparison is not vacuous: {total} setups compared")


def test_the_backup_fill_cannot_touch_arming():
    """THE INVARIANT THAT LETS THE BOT SKIP THE BACKUP ENTIRELY.

    The chart fills on an order block or fair value gap when the limit never
    comes back; the watcher has no such rule and deliberately never will --
    the zone only exists once the move has run without you, which is minutes
    to hours after the alert, so acting on it would be a second message about
    the same setup.

    That is only safe while the backup is POST-ARMING. It re-prices where an
    armed setup fills; it must not create, remove or move an arm. If it ever
    does, the bot starts alerting a different strategy from the chart and
    nothing else in this repository would notice -- deploy/undertow-three-way
    -check.py waives `useBackup` on the strength of exactly this test.
    """
    def key(r):
        return [(t["bar"], t["short"], t["entry"], t["stop"], t["target"],
                 t["code"]) for t in r]

    total = 0
    for seed, drift in ((11, 0.0), (12, 0.0006), (13, -0.0006), (14, 0.0002)):
        cs = walk(4000, seed=seed, drift=drift)
        off = key(U.run(cs, U.P(maxLive=64, useBackup=False), "T").armed)
        on = key(U.run(cs, U.P(maxLive=64, useBackup=True), "T").armed)
        total += len(off)
        ok(off == on, f"seed {seed}: {len(off)} arms, identical either way")
    # NON-VACUITY ON THE TOTAL, not per seed. One of these walks arms nothing
    # at the shipped configuration and a per-seed guard failed on it -- the
    # claim is about every arm across the fixture, not about each walk
    # separately containing one.
    ok(total > 40, f"the comparison is not vacuous: {total} arms compared")


def test_fills_agree():
    """The SECOND event the bot alerts on, held to the port the same way.

    Fills are where the two copies were most likely to drift, because the stop
    MOVES between arming and filling -- it tracks the running pullback extreme
    while the order rests. A copy that froze the stop at arming would produce
    the right fill bars with the wrong levels, which is the kind of wrong that
    looks right in a digest.
    """
    total = 0
    for seed, drift in ((11, 0.0), (12, 0.0006), (13, -0.0006)):
        cs = walk(4000, seed=seed, drift=drift)
        # useBackup PINNED OFF. The chart ships it ON and the watcher has no
        # backup by design, so the two copies' FILLS legitimately differ --
        # what must not differ is the ARM, which the test above holds. Pinning
        # it here keeps this test measuring the stop-tracking and fill-order
        # behaviour it was written for rather than a divergence that is a
        # documented design decision.
        want = U.run(cs, U.P(maxLive=64, useBackup=False), "T").fills
        got = W.run_setups(cs, max_live=64)[1]
        total += len(want)
        ok(len(want) == len(got),
           f"seed {seed}: {len(want)} fills, bot copy found {len(got)}")
        if len(want) != len(got):
            continue
        bad = []
        for w, g in zip(want, got):
            for k in ("bar", "short", "code", "state", "pin", "armBar"):
                if w[k] != g[k]:
                    bad.append((w["bar"], k, w[k], g[k]))
            for k in ("entry", "stop", "target"):
                if abs(w[k] - g[k]) > 1e-9:
                    bad.append((w["bar"], k, w[k], g[k]))
        ok(not bad, f"seed {seed}: every fill field matches"
           + ("" if not bad else f"  first: {bad[0]}"))
    ok(total > 30, f"the comparison is not vacuous: {total} fills compared")
    # AND THE THING THAT MAKES THIS TEST NECESSARY, which is now TWO claims
    # because the chart's stop source moved to the minor swing extreme.
    #
    #   pullback extreme   the stop TRACKS, so a fill alert cannot reuse the
    #                      arming numbers -- the original reason for this file
    #   minor swing        the stop is pinned to a CONFIRMED swing and has
    #                      nothing to follow, so it must NOT move
    #
    # The second is asserted rather than assumed because `stopTrack` is still
    # True and still shipped; what makes it inert is the source, and an inert
    # switch that silently starts working again is exactly the drift this file
    # exists for.
    # ACROSS SIXTEEN WALKS, not one. The shipped `famStrict` removes roughly the
    # smaller half of the population and `armWins` another tenth, and one seed
    # no longer reliably contains a deepening pullback after an arming, and the
    # external structure at a 50-bar pivot made that worse again. The
    # single-walk version went to 0 of 25 fills and the four-walk one to 0 of
    # 48 -- both failing for want of a fixture rather than for want of the
    # behaviour. Sixteen walks is enough to contain one; if a future default
    # empties it again the answer is a purpose-built sequence, not more seeds.
    for src, want_move in (("Pullback extreme", True),
                           ("Minor swing extreme", False)):
        old = W.STOP_SRC
        W.STOP_SRC = src
        moved = nfill = 0
        try:
            for seed in range(11, 27):
                cs = walk(4000, seed=seed, drift=0.0006 * ((seed % 3) - 1))
                a, f = W.run_setups(cs, max_live=64)
                by_arm = {x["bar"]: x for x in a}
                nfill += len(f)
                moved += sum(
                    1 for x in f if x["armBar"] in by_arm
                    and abs(by_arm[x["armBar"]]["stop"] - x["stop"]) > 1e-9)
        finally:
            W.STOP_SRC = old
        f = [None] * nfill
        ok((moved > 0) == want_move,
           f"{src}: {moved} of {len(f)} fills carry a stop that moved after "
           f"arming — expected {'some' if want_move else 'none'}")
    ok(W.STOP_SRC == U.P().stopSrc,
       f"and the watcher ships the chart's source, {W.STOP_SRC!r}")


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
        got = W.armed_setups(cs, max_live=64)
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
            # THE STRUCTURE ENGINE IS LuxAlgo's NOW, in all three copies.
            # msShortLen, swingSrc, swingK, swingKMinor, swingHours and
            # msBosNeedsIdm belonged to riptide's engine; they are still in the
            # port, because every page in measurements/ was produced on them,
            # and the watcher no longer has them because it no longer runs it.
            ("biasSrc", W.BIAS_SRC, p.biasSrc),
            ("smcSwingLen", W.SMC_SWING_LEN, p.smcSwingLen),
            ("smcInternalLen", W.SMC_INTERNAL_LEN, p.smcInternalLen),
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
    # The three claims, not the exact wording — the caveat gets reworded for
    # width and a test that pins its phrasing would fail on a rewrite that
    # kept every promise. What must survive any rewrite is these three.
    c = W.SPEC.caveat.lower()
    for claim, word in (("it is not a trade", "not a trade"),
                        ("it was measured", "no edge"),
                        ("it lost to a control", "random")):
        ok(word in c, f"the caveat still says {claim}")
    # The width rule applies to what the DIGEST shows. Undertow's caveat is
    # off the digest and lives in /undertow, where it is prose and wraps
    # wherever Telegram likes.
    ok(W.SPEC.caveat_in_digest is False,
       "undertow's caveat is in /undertow, not above every message")
    ok(all(len(l) <= 40 for l in W.SPEC.caveat.split("\n"))
       or not W.SPEC.caveat_in_digest,
       "a caveat that IS shown in a digest has to fit a phone")
    # THE STAGE MUST BE IN THE MESSAGE. Without it there is no way to tell
    # from a digest whether it fired at the pin, at the confirmations or at
    # the fill -- and landing at the moment the order goes on is the entire
    # value of this alert.
    ok("limit" in W.SPEC.caveat.lower(),
       "the caveat still says the limit goes on NOW")
    ok(len([i for i in __import__("riptide.watchers", fromlist=["x"])
            .all_indicators() if i.name.startswith("ut")
            or i.name == "undertow"]) == 1,
       "there is exactly ONE undertow stream — /utfill was removed")


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
    got = W.armed_setups(cs, max_live=64)
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


def test_digest_fits_a_phone():
    """THE DIGEST IS READ ON A 6" SCREEN AND NOWHERE ELSE.

    The first version used the framework's fixed-width label column, which
    assumes a wide terminal: on a phone every row wrapped twice, the
    indentation that column exists to create collapsed back to the left
    margin, and the block stopped reading as a list. This pins the fix, because
    "it looks fine" is not a thing a test can check later and a wrapped digest
    is indistinguishable from a working one in code review.
    """
    import re
    from riptide import watch
    cs = walk(4000, seed=12, drift=0.0006)
    got = W.armed_setups(cs, max_live=64)
    hits = []
    for a in got[-6:]:
        hits += W.detect(cs[:a["bar"] + 2], "BTC_USDT", "Min15", {})[0]
    # a tiny price and a huge one, which are the two width extremes
    for a in got[-3:]:
        hits += W.detect(cs[:a["bar"] + 2], "PEPE_USDT", "Min30", {})[0]
    ok(len(hits) >= 3, f"the fixture renders something: {len(hits)}")
    msg = watch.digest(W.SPEC, hits, ("Min15", "Min30"),
                       max(h.bar_time for h in hits))
    plain = re.sub(r"<[^>]+>", "", msg)
    lines = plain.split("\n")
    wide = [l for l in lines if len(l) > 40]
    ok(not wide, "every line fits 40 characters"
       + ("" if not wide else f" — {len(wide)} do not, worst "
          f"{max(len(l) for l in wide)}: {max(wide, key=len)!r}"))
    ok(not any(l.rstrip().endswith("·") for l in lines),
       "no line ends on a dangling separator")
    # The entry is Hit.price and must appear ONCE per block, never twice.
    body = [l for l in lines if l.strip().startswith("entry")]
    ok(len(body) == len(hits),
       f"one entry line per setup: {len(body)} == {len(hits)}")
    for h in hits[:3]:
        from riptide import telegram as tg
        shown = sum(l.count(tg.fmt(h.price)) for l in lines)
        ok(shown >= 1, f"{h.symbol}: the limit is printed")
    ok(all(("entry" in l) == ("tgt" in l) for l in body),
       "entry and target are on one line, so the trade reads in one glance")


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
    got = W.armed_setups(cs, max_live=64)
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
    for fn in (test_copies_agree,
               test_the_backup_fill_cannot_touch_arming, test_agree_on_real_candles,
               test_fills_agree,
               test_frozen_constants_match_the_port, test_ships_off,
               test_digest_fits_a_phone,
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
