"""The trendline watch: the plumbing around the port, not the port itself.

`research/test_trendline.py` already checks the indicator's arithmetic against
values worked out by hand from the Pine. What is new here is everything that
turns a list of breakouts into one message: the freshness gate, dedupe, the
digest, the switches, and the promise that none of it reaches the tables
/stats scores.

Those are exactly the parts that are expensive to discover live. A broken
freshness gate replays six hundred bars of history into the chat on the next
restart; a broken dedupe repeats every close forever; a digest over Telegram's
4096-character cap fails silently at the worst possible moment, which is a
market-wide move.

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
from riptide.trendline import Signal                        # noqa: E402

STEP = 14400            # Hour4
NBARS = 400             # over the 260-bar floor scan_symbol requires

sent = []


async def fake_send(sess, text, buttons=None):
    sent.append(text)
    return True


tg.tg_send = fake_send
watch.tg.tg_send = fake_send

# A bar close far enough in the past to be deterministic, aligned to the step.
LAST_OPEN = (int(time.time()) // STEP) * STEP - STEP


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
# Same bars on each watched grid, so a break can be fresh on more than one.
BY_TF = {"Min15": candles(step=900), "Min30": candles(step=1800),
         "Hour4": CS}
# Which canned breakouts each symbol reports. Set per test.
PLAN: dict = {}


async def fake_fetch(sess, symbol, interval=""):
    return CS if symbol in PLAN else []


def fake_signals(cs, **kw):
    return PLAN.get(fake_signals.symbol, [])


watch.fetch_candles = fake_fetch
watch.trendline_signals = fake_signals


async def _fetch_router(sess, symbol, interval=""):
    fake_signals.symbol = symbol
    return BY_TF.get(interval, CS)


watch.fetch_candles = _fetch_router


# The fixture bars are flat — high 101, low 99, close 100 — so every true range
# is 2.0 and ATR(200) is exactly 2.0. A slope of 0.5 is therefore 0.25 ATR per
# bar, comfortably over the 0.15 default gate, and a slope of 0.1 is 0.05 ATR,
# comfortably under it. Both thresholds are exercised below.
STEEP, FLAT = 0.5, 0.1


def sig(bars_back: int, is_long=True, price=100.0, line=98.0,
        slope=STEEP) -> Signal:
    """A breakout on the bar `bars_back` before the newest one."""
    i = len(CS) - 1 - bars_back
    # Sign is guaranteed by construction in the real port — an up channel comes
    # only from descending pivot highs — so the fixture matches that and the
    # gate reads the magnitude.
    return Signal(bar=i, is_long=is_long, price=price, line_y=line,
                  x1=i - 30, y1=line, pivots=4,
                  slope=-slope if is_long else slope, run=30)


def run(db, symbols, tfs=None):
    sent.clear()
    return asyncio.run(watch.cycle(None, db, symbols, tfs)), list(sent)


def main():
    db = storage.db_init()
    watch.set_intervals(db, ["Hour4"])
    watch.set_enabled(db, True)
    watch.set_min_slope(db, 0.15)
    good = []

    def ok(cond, msg):
        good.append(bool(cond))
        print(("  PASS  " if cond else "  FAIL  ") + msg)

    print("\n1. The freshest break is sent; an old one is recorded, not sent")
    PLAN.clear()
    PLAN["AAA_USDT"] = [sig(0, True)]        # the bar that just closed
    PLAN["BBB_USDT"] = [sig(6, False)]       # six bars ago, inside RECENT_BARS
    n, msgs = run(db, list(PLAN))
    ok(n == 1, f"one break sent, not two: got {n}")
    ok(len(msgs) == 1, f"exactly one message: got {len(msgs)}")
    ok("AAA" in msgs[0] and "BBB" not in msgs[0],
       "the fresh symbol is in it and the stale one is not")
    ok(watch.already_sent(db, watch.sig_of("BBB_USDT", "Hour4",
                                           CS[len(CS) - 7].t, False)),
       "the STALE break was still recorded — otherwise a restart replays it")

    print("\n2. The same break twice sends once")
    n, msgs = run(db, list(PLAN))
    ok(n == 0 and not msgs, f"second pass is silent: got {n} sent, "
                            f"{len(msgs)} message(s)")

    print("\n3. bar_time is the bar's CLOSE, not its open")
    breaks = asyncio.run(watch.scan_symbol(None, asyncio.Semaphore(1),
                                           "AAA_USDT", "Hour4", 0.0))
    ok(len(breaks) == 1, f"one break parsed: got {len(breaks)}")
    ok(breaks[0].bar_time == CS[-1].t + STEP,
       f"close, not open: got {breaks[0].bar_time}, "
       f"want {CS[-1].t + STEP} (open is {CS[-1].t})")

    print("\n4. Both sides in one digest, ups first")
    PLAN.clear()
    PLAN["UPA_USDT"] = [sig(0, True)]
    PLAN["DNA_USDT"] = [sig(0, False)]
    n, msgs = run(db, list(PLAN))
    ok(n == 2 and len(msgs) == 1,
       f"two breaks, ONE message: got {n} breaks in {len(msgs)} message(s)")
    body = msgs[0]
    ok(body.index("UPA") < body.index("DNA"), "ups are listed before downs")
    ok("not a trade" in body, "the message says it is not a trade")

    print("\n5. A burst is capped and says how many were left out")
    PLAN.clear()
    for i in range(40):
        PLAN[f"S{i:02d}_USDT"] = [sig(0, i % 2 == 0)]
    n, msgs = run(db, list(PLAN))
    ok(len(msgs) == 1, f"forty breaks still make ONE message: got {len(msgs)}")
    body = msgs[0]
    shown = body.count("tradingview.com")
    ok(shown == watch.TRENDLINE_MAX_LINES,
       f"capped at {watch.TRENDLINE_MAX_LINES} lines: got {shown}")
    ok(f"+{40 - watch.TRENDLINE_MAX_LINES} more" in body,
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
    ok(body.count("tradingview.com") < watch.TRENDLINE_MAX_LINES,
       f"and it trimmed BELOW the line cap to get there: "
       f"{body.count('tradingview.com')} of {watch.TRENDLINE_MAX_LINES}")
    ok("more this close" in body, "it still says how many it left out")

    print("\n6. /pause silences it, and off means off")
    PLAN.clear()
    PLAN["CCC_USDT"] = [sig(0, True)]
    storage.meta_set(db, "alerts_paused", "1")
    n, msgs = run(db, list(PLAN))
    ok(not msgs, f"paused sends nothing: got {len(msgs)} message(s)")
    ok(watch.already_sent(db, watch.sig_of("CCC_USDT", "Hour4", CS[-1].t,
                                           True)),
       "and still records it, so /resume does not replay the backlog")
    storage.meta_set(db, "alerts_paused", "0")
    watch.set_enabled(db, False)
    ok(not watch.enabled(db), "the switch reads off")
    watch.set_enabled(db, True)

    print("\n7. A symbol that fails to fetch cannot take the cycle down")
    async def boom(sess, symbol, interval=""):
        if symbol == "BAD_USDT":
            raise RuntimeError("exchange said no")
        fake_signals.symbol = symbol
        return BY_TF.get(interval, CS)
    keep, watch.fetch_candles = watch.fetch_candles, boom
    PLAN.clear()
    PLAN["DDD_USDT"] = [sig(0, True)]
    n, msgs = run(db, ["BAD_USDT", "DDD_USDT"])
    watch.fetch_candles = keep
    ok(n == 1 and len(msgs) == 1,
       f"the good symbol still alerts: got {n} sent, {len(msgs)} message(s)")

    print("\n8. Nothing here reaches the tables /stats scores")
    rows = db.execute("SELECT COUNT(*) FROM outcomes").fetchone()[0]
    ok(rows == 0, f"no outcome rows armed: got {rows}")
    for t in ("seen", "seen_sweeps", "seen_early"):
        c = db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        ok(c == 0, f"{t} untouched: got {c}")
    c = db.execute("SELECT COUNT(*) FROM seen_trendline").fetchone()[0]
    ok(c > 0, f"and its own table has the breaks: {c}")

    print("\n9. The steepness gate drops flat lines — and does NOT record "
          "them\n   (recording a break the gate rejected would make lowering "
          "the gate\n   later silent, because dedupe would already have "
          "claimed every one)")
    PLAN.clear()
    PLAN["STEEP_USDT"] = [sig(0, True, slope=STEEP)]
    PLAN["FLAT_USDT"] = [sig(0, True, slope=FLAT)]
    n, msgs = run(db, list(PLAN))
    ok(n == 1, f"only the steep one is sent: got {n}")
    ok("STEEP" in msgs[0] and "FLAT" not in msgs[0],
       "the flat line is not in the message")
    flat_sig = watch.sig_of("FLAT_USDT", "Hour4", CS[-1].t, True)
    ok(not watch.already_sent(db, flat_sig),
       "and the flat break is NOT recorded, so a lower gate would still find "
       "it")
    watch.set_min_slope(db, 0.0)
    n, msgs = run(db, ["FLAT_USDT"])
    ok(n == 1, f"with the gate at 0 the same flat break now sends: got {n}")
    watch.set_min_slope(db, 0.15)

    print("\n10. Two timeframes make ONE digest, and a symbol on both is "
          "listed\n    once, on the slower one")
    PLAN.clear()
    PLAN["BOTH_USDT"] = [sig(0, True)]
    PLAN["ONLY_USDT"] = [sig(0, False)]
    n, msgs = run(db, list(PLAN), ("Min15", "Min30"))
    ok(len(msgs) == 1, f"one message for two timeframes: got {len(msgs)}")
    body = msgs[0]
    # Counting the bare name would count it twice per line — the TradingView
    # URL carries the symbol as well as the label. The label is the line.
    ok(body.count("<b>BOTH</b>") == 1,
       f"the doubled symbol appears once: got {body.count('<b>BOTH</b>')}")
    ok("interval=30" in body and "BOTHUSDT.P&interval=15" not in body,
       "and the link it kept is the SLOWER timeframe's")
    ok("15m+30m" in body, "the header names both timeframes")

    print("\n10b. EVERY line carries its own timeframe, including in a "
          "single-timeframe\n     digest — the tag answers 'which chart am I "
          "opening', and a tag that\n     comes and goes moves the columns "
          "between messages")
    PLAN.clear()
    PLAN["SOLO_USDT"] = [sig(0, True)]
    n, msgs = run(db, list(PLAN), ("Min30",))
    ok("<code>30m</code>" in msgs[0],
       "the timeframe is on the line even when the digest has only one")

    print("\n11. The digest is ordered steepest first, because that is the "
          "only\n    recommendation it makes")
    PLAN.clear()
    PLAN["MILD_USDT"] = [sig(0, True, slope=0.4)]
    PLAN["SHARP_USDT"] = [sig(0, True, slope=0.9)]
    n, msgs = run(db, list(PLAN))
    body = msgs[0]
    ok(body.index("SHARP") < body.index("MILD"),
       "the steeper break is listed first")

    print("\n12. An unknown timeframe falls back rather than crashing")
    storage.meta_set(db, "trendline_tf", "Fortnight")
    ok(watch.intervals(db) == watch.TRENDLINE_INTERVALS,
       f"falls back to the config {watch.TRENDLINE_INTERVALS}: "
       f"got {watch.intervals(db)}")
    storage.meta_set(db, "trendline_tf", "Fortnight,Min30")
    ok(watch.intervals(db) == ("Min30",),
       f"and a partly-bad list keeps the good half: got "
       f"{watch.intervals(db)}")
    watch.set_intervals(db, ["Hour4"])

    print(f"\n{'ALL PASS' if all(good) else 'FAILURES'}  "
          f"{sum(good)}/{len(good)}")
    return 0 if all(good) else 1


if __name__ == "__main__":
    sys.exit(main())
