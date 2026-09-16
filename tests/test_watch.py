"""The watch FRAMEWORK: the plumbing every indicator gets, on a fake one.

WHAT IS UNDER TEST. Not any indicator's arithmetic — each of those has its own
test beside it in `indicators/<name>/tests/`. What is here is everything that
turns a list of hits into one message: the freshness gate, dedupe, the digest's
line cap and character budget, the switches, the per-indicator settings, the
timeframe fallback, and the promise that none of it reaches the tables /stats
scores.

Those are exactly the parts that are expensive to discover live. A broken
freshness gate replays six hundred bars of history into the chat on the next
restart; a broken dedupe repeats every close forever; a digest over Telegram's
4096-character cap fails silently at the worst possible moment, which is a
market-wide move. Every one of those was found here rather than in the chat.

IT RUNS ON A FAKE INDICATOR, AND THAT IS THE POINT. `PROBE` below is a complete
indicator in about thirty lines, registered the same way a real one is. If the
framework only worked for the indicators that happen to ship, the next port
would find out the hard way — and this file is also the shortest worked example
of what adding one takes.

MEXC and Telegram are stubbed; SQLite is real.

    PYTHONPATH=. python3 tests/test_watch.py     # exit 1 on any failure
"""
import asyncio
import os
import sys
import tempfile
import time

os.environ["RIPTIDE_DB"] = tempfile.mktemp(suffix=".db")
os.environ.setdefault("TELEGRAM_TOKEN", "x")
os.environ.setdefault("TELEGRAM_CHAT_ID", "1")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from riptide import storage, watch                          # noqa: E402
from riptide import telegram as tg                          # noqa: E402
from riptide.engine import Candle                           # noqa: E402
from riptide.watchers import Hit, Indicator, Option, register  # noqa: E402

STEP = 14400            # Hour4
NBARS = 400

sent = []


async def fake_send(sess, text, buttons=None):
    sent.append(text)
    return True


tg.tg_send = fake_send
watch.tg.tg_send = fake_send


def candles(n=NBARS, step=STEP):
    """Flat bars ending on the last CLOSED bar of that step's own grid.

    Each timeframe needs its own grid. A 4h-aligned series read as Min15 puts
    the newest bar's close hours in the past, so a 15m freshness window can
    never contain it and every multi-timeframe test would fail for a reason
    that has nothing to do with the code under test. Found exactly that way.
    """
    last = (int(time.time()) // step) * step - step
    t0 = last - (n - 1) * step
    return [Candle(t0 + i * step, 100.0, 101.0, 99.0, 100.0, 1.0)
            for i in range(n)]


CS = candles()
BY_TF = {"Min15": candles(step=900), "Min30": candles(step=1800), "Hour4": CS}

# What each symbol reports, as (bars_back, is_long, strength). Set per test.
# `strength` stands in for whatever volume gate a real indicator has — the
# trendline had a slope floor, the exhaustion count has a perfected-only gate.
PLAN: dict = {}


# ─────────────────────────────────────────────────────────────────────────
# A COMPLETE INDICATOR. This is the whole contract; everything else in this
# file is the framework exercising it.


def probe_detect(cs, symbol, tf, opts):
    """Hits from PLAN, with anything under the `floor` option thrown away.

    Returns (hits, dropped) — the second number is what lets /status tell "18
    found, all below the gate" from "the loop never woke".
    """
    out, dropped = [], 0
    for bars_back, is_long, strength in PLAN.get(symbol, []):
        if strength < opts["floor"]:
            dropped += 1
            continue
        i = len(cs) - 1 - bars_back
        out.append(Hit(
            key=f"PR|{symbol}|{tf}|{cs[i].t}|{'U' if is_long else 'D'}",
            symbol=symbol, tf=tf, is_long=is_long,
            # The bar's CLOSE, not its open: a hit is only true once the bar
            # has closed. Both real detectors got this wrong first.
            bar_time=cs[i].t + BAR_SEC[tf], price=100.0 + strength,
            detail=f"{strength:.2f}", strength=strength))
    return out, dropped


def probe_row(h, group):
    return (watch.label(PROBE, group) + watch.chart(h)
            + f"  <i>str {h.extra['strength']:.2f}</i>")


def probe_classify(h):
    # Ups first, then downs; strongest first inside each. The only
    # recommendation a digest makes is its order.
    return (not h.is_long, -h.extra["strength"]), ("up" if h.is_long
                                                   else "down")


PROBE = register(Indicator(
    name="probe", title="PROBE", glyph="🧪", unit="hit",
    caveat="a test fixture, not a trade and not an indicator",
    detect=probe_detect, row=probe_row, classify=probe_classify,
    min_bars=260, recent_bars=8, fresh_bars=2, max_lines=20, label_w=8,
    default_enabled=False, default_intervals=("Hour4",),
    tf_counted=("Min15", "Min30", "Hour4"),
    options=(Option("floor", "number", 0.15, "the volume gate", hi=10.0),),
    rate=lambda db, tfs=None, **kw: 7,
))

from riptide.config import BAR_SECONDS as BAR_SEC          # noqa: E402


async def _fetch_router(sess, symbol, interval=""):
    return BY_TF.get(interval, CS) if symbol in PLAN else []


watch.fetch_candles = _fetch_router

STEEP, FLAT = 0.5, 0.1      # either side of the 0.15 default floor


def sig(bars_back: int, is_long=True, strength=STEEP):
    return (bars_back, is_long, strength)


def key(symbol, tf, bars_back, is_long):
    cs = BY_TF.get(tf, CS)
    i = len(cs) - 1 - bars_back
    return f"PR|{symbol}|{tf}|{cs[i].t}|{'U' if is_long else 'D'}"


def run(db, symbols, tfs=None):
    sent.clear()
    return asyncio.run(watch.cycle(None, db, PROBE, symbols, tfs)), list(sent)


def main():
    db = storage.db_init()
    watch.set_intervals(db, PROBE, ["Hour4"])
    watch.set_enabled(db, PROBE, True)
    watch.set_setting(db, PROBE, "floor", 0.15)
    good = []

    def ok(cond, msg):
        good.append(bool(cond))
        print(("  PASS  " if cond else "  FAIL  ") + msg)

    print("\n1. The freshest hit is sent; an old one is recorded, not sent")
    PLAN.clear()
    PLAN["AAA_USDT"] = [sig(0, True)]        # the bar that just closed
    PLAN["BBB_USDT"] = [sig(6, False)]       # six bars ago, inside recent_bars
    n, msgs = run(db, list(PLAN))
    ok(n == 1, f"one hit sent, not two: got {n}")
    ok(len(msgs) == 1, f"exactly one message: got {len(msgs)}")
    ok("AAA" in msgs[0] and "BBB" not in msgs[0],
       "the fresh symbol is in it and the stale one is not")
    ok(watch.already_sent(db, PROBE, key("BBB_USDT", "Hour4", 6, False)),
       "the STALE hit was still recorded — otherwise a restart replays it")

    print("\n2. The same hit twice sends once")
    n, msgs = run(db, list(PLAN))
    ok(n == 0 and not msgs, f"second pass is silent: got {n} sent, "
                            f"{len(msgs)} message(s)")

    print("\n3. bar_time is the bar's CLOSE, not its open")
    hits, _dropped = asyncio.run(watch.scan_symbol(
        None, asyncio.Semaphore(1), PROBE, "AAA_USDT", "Hour4",
        {"floor": 0.0}))
    ok(len(hits) == 1, f"one hit parsed: got {len(hits)}")
    ok(hits[0].bar_time == CS[-1].t + STEP,
       f"close, not open: got {hits[0].bar_time}, "
       f"want {CS[-1].t + STEP} (open is {CS[-1].t})")

    print("\n4. Both groups in one digest, in the indicator's own order")
    PLAN.clear()
    PLAN["UPA_USDT"] = [sig(0, True)]
    PLAN["DNA_USDT"] = [sig(0, False)]
    n, msgs = run(db, list(PLAN))
    ok(n == 2 and len(msgs) == 1,
       f"two hits, ONE message: got {n} hits in {len(msgs)} message(s)")
    body = msgs[0]
    ok(body.index("UPA") < body.index("DNA"), "ups are listed before downs")
    ok("not a trade" in body, "the caveat is in the message")

    print("\n5. A burst is capped and says how many were left out")
    PLAN.clear()
    for i in range(40):
        PLAN[f"S{i:02d}_USDT"] = [sig(0, i % 2 == 0)]
    n, msgs = run(db, list(PLAN))
    ok(len(msgs) == 1, f"forty hits still make ONE message: got {len(msgs)}")
    body = msgs[0]
    shown = body.count("tradingview.com")
    ok(shown == PROBE.max_lines,
       f"capped at {PROBE.max_lines} lines: got {shown}")
    ok(f"+{40 - PROBE.max_lines} more" in body,
       "it says how many it left out")
    ok(len(body) < 4096, f"under Telegram's cap: {len(body)} chars")

    print("\n5b. The CHARACTER budget, not just the line count, keeps it "
          "under\n    Telegram's cap — the line count alone does not. Real "
          "names are long\n    and the URL carries each one twice.")
    PLAN.clear()
    for i in range(60):
        PLAN[f"VERYLONGTICKERNAME{i:02d}_USDT"] = [sig(0, i % 2 == 0)]
    n, msgs = run(db, list(PLAN))
    body = msgs[0]
    ok(len(body) < 4096,
       f"still under the cap with 18-character symbols: {len(body)} chars")
    ok(body.count("tradingview.com") < PROBE.max_lines,
       f"and it trimmed BELOW the line cap to get there: "
       f"{body.count('tradingview.com')} of {PROBE.max_lines}")
    ok("more this close" in body, "it still says how many it left out")

    print("\n6. /pause silences it, and off means off")
    PLAN.clear()
    PLAN["CCC_USDT"] = [sig(0, True)]
    storage.meta_set(db, "alerts_paused", "1")
    n, msgs = run(db, list(PLAN))
    ok(not msgs, f"paused sends nothing: got {len(msgs)} message(s)")
    ok(watch.already_sent(db, PROBE, key("CCC_USDT", "Hour4", 0, True)),
       "and still records it, so /resume does not replay the backlog")
    storage.meta_set(db, "alerts_paused", "0")
    watch.set_enabled(db, PROBE, False)
    ok(not watch.enabled(db, PROBE), "the switch reads off")
    watch.set_enabled(db, PROBE, True)

    print("\n7. A symbol that fails to fetch cannot take the cycle down")

    async def boom(sess, symbol, interval=""):
        if symbol == "BAD_USDT":
            raise RuntimeError("exchange said no")
        return BY_TF.get(interval, CS)
    keep, watch.fetch_candles = watch.fetch_candles, boom
    PLAN.clear()
    PLAN["DDD_USDT"] = [sig(0, True)]
    n, msgs = run(db, ["BAD_USDT", "DDD_USDT"])
    watch.fetch_candles = keep
    ok(n == 1 and len(msgs) == 1,
       f"the good symbol still alerts: got {n} sent, {len(msgs)} message(s)")
    ok(watch.last_cycle["probe"]["failed"] == 1,
       "and /status can see that one symbol failed")

    print("\n8. Nothing here reaches the tables /stats scores")
    rows = db.execute("SELECT COUNT(*) FROM outcomes").fetchone()[0]
    ok(rows == 0, f"no outcome rows armed: got {rows}")
    for t in ("seen", "seen_sweeps", "seen_early"):
        c = db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        ok(c == 0, f"{t} untouched: got {c}")
    c = db.execute("SELECT COUNT(*) FROM seen_watch WHERE watcher='probe'"
                   ).fetchone()[0]
    ok(c > 0, f"and the watch's own table has the hits: {c}")

    print("\n8b. Two indicators cannot suppress each other, even on an "
          "identical\n     signature — the dedupe key is (watcher, sig), not "
          "sig")
    watch.record(db, PROBE, Hit(key="SHARED", symbol="ZZZ_USDT", tf="Hour4",
                                is_long=True, bar_time=1, price=1.0))
    other = Indicator(name="probe2", title="P2", glyph="x", unit="hit",
                      caveat="fixture", detect=probe_detect, row=probe_row,
                      classify=probe_classify)
    ok(watch.already_sent(db, PROBE, "SHARED")
       and not watch.already_sent(db, other, "SHARED"),
       "the same signature under another watcher is still unsent")

    print("\n9. The indicator's own gate drops weak hits — and does NOT "
          "record\n   them (recording a hit the gate rejected would make "
          "lowering the gate\n   later silent, because dedupe would already "
          "have claimed every one)")
    PLAN.clear()
    PLAN["STEEP_USDT"] = [sig(0, True, STEEP)]
    PLAN["FLAT_USDT"] = [sig(0, True, FLAT)]
    n, msgs = run(db, list(PLAN))
    ok(n == 1, f"only the strong one is sent: got {n}")
    ok("STEEP" in msgs[0] and "FLAT" not in msgs[0],
       "the weak hit is not in the message")
    ok(not watch.already_sent(db, PROBE, key("FLAT_USDT", "Hour4", 0, True)),
       "and the weak hit is NOT recorded, so a lower gate would still find it")
    watch.set_setting(db, PROBE, "floor", 0.0)
    n, msgs = run(db, ["FLAT_USDT"])
    ok(n == 1, f"with the gate at 0 the same weak hit now sends: got {n}")
    watch.set_setting(db, PROBE, "floor", 0.15)

    print("\n10. Two timeframes make ONE digest")
    PLAN.clear()
    PLAN["BOTH_USDT"] = [sig(0, True)]
    PLAN["ONLY_USDT"] = [sig(0, False)]
    n, msgs = run(db, list(PLAN), ("Min15", "Min30"))
    ok(len(msgs) == 1, f"one message for two timeframes: got {len(msgs)}")
    ok("15m+30m" in msgs[0], "the header names both timeframes")

    print("\n10b. EVERY line carries its own timeframe, including in a "
          "single-timeframe\n     digest — the tag answers 'which chart am I "
          "opening', and a tag that\n     comes and goes moves the columns "
          "between messages")
    PLAN.clear()
    PLAN["SOLO_USDT"] = [sig(0, True)]
    n, msgs = run(db, list(PLAN), ("Min30",))
    ok("<code>30m</code>" in msgs[0],
       "the timeframe is on the line even when the digest has only one")

    print("\n11. The digest is ordered by the indicator's classify(), because "
          "that\n    is the only recommendation it makes")
    PLAN.clear()
    PLAN["MILD_USDT"] = [sig(0, True, 0.4)]
    PLAN["SHARP_USDT"] = [sig(0, True, 0.9)]
    n, msgs = run(db, list(PLAN))
    ok(msgs[0].index("SHARP") < msgs[0].index("MILD"),
       "the stronger hit is listed first")

    print("\n11b. A quiet close SAYS WHY it was quiet — 'found, all below the "
          "gate'\n     and 'nothing happened' are the two things worth "
          "telling apart when\n     nothing has arrived, and they look "
          "identical from the chat")
    PLAN.clear()
    PLAN["ALLFLAT_USDT"] = [sig(0, True, FLAT), sig(1, False, FLAT)]
    n, msgs = run(db, list(PLAN))
    c = watch.last_cycle["probe"]
    ok(not msgs and c["sent"] == 0, "a close with only weak hits is silent")
    ok(c["dropped"] == 2 and c["seen"] == 0,
       f"and it counted them: {c['dropped']} dropped, {c['seen']} through")
    PLAN.clear()
    PLAN["NOTHING_USDT"] = []
    n, msgs = run(db, list(PLAN))
    c = watch.last_cycle["probe"]
    ok(c["dropped"] == 0 and c["seen"] == 0,
       "a genuinely quiet close reads zero and zero — a different answer")

    print("\n12. An unknown timeframe falls back rather than crashing")
    storage.meta_set(db, "probe_tf", "Fortnight")
    ok(watch.intervals(db, PROBE) == PROBE.default_intervals,
       f"falls back to the indicator's default {PROBE.default_intervals}: "
       f"got {watch.intervals(db, PROBE)}")
    storage.meta_set(db, "probe_tf", "Fortnight,Min30")
    ok(watch.intervals(db, PROBE) == ("Min30",),
       f"and a partly-bad list keeps the good half: got "
       f"{watch.intervals(db, PROBE)}")
    watch.set_intervals(db, PROBE, ["Hour4"])

    print("\n12b. So does an unreadable Option — validated on READ, so a "
          "database\n     carrying a value this build no longer understands "
          "cannot take the\n     loop down")
    storage.meta_set(db, "probe_floor", "banana")
    ok(watch.setting(db, PROBE, "floor") == 0.15,
       f"a junk value reads back as the default: "
       f"{watch.setting(db, PROBE, 'floor')}")
    watch.set_setting(db, PROBE, "floor", 0.15)

    print("\n13. A symbol with too little history is unanswerable, not quiet")
    short = {"Hour4": candles(n=10)}
    keep, watch.fetch_candles = watch.fetch_candles, (
        lambda sess, symbol, interval="": _short(short, interval))
    PLAN.clear()
    PLAN["TINY_USDT"] = [sig(0, True)]
    n, msgs = run(db, list(PLAN))
    watch.fetch_candles = keep
    ok(n == 0 and not msgs,
       f"under min_bars nothing is reported: got {n}")

    print(f"\n{'ALL PASS' if all(good) else 'FAILURES'}  "
          f"{sum(good)}/{len(good)}")
    return 0 if all(good) else 1


async def _short(table, interval):
    return table.get(interval, table["Hour4"])


if __name__ == "__main__":
    sys.exit(main())
