"""The exhaustion watch: the two ports agree, and it cannot flood the chat.

WHY THIS FILE EXISTS. The 9-count and 13-count now live in TWO places —
research/td.py, which the measurement ran on, and riptide/exhaust.py, which
the bot runs. They are deliberately not one module: research/ pulls in the
whole study stack and must never be importable from a live scanner, because a
refactor in research must not be able to break a running bot.

The cost of that decision is drift, and drift here is silent. If the bot's
copy quietly stops matching, every number the study produced stops describing
what the bot sends, and nothing anywhere would say so. So this runs BOTH over
the same candles and asserts they agree bar for bar.

The second half asserts the thing that decided every default in exhaust.py:
the volume. 295 rows a day across the universe is three and a half times
Riptide's whole alert volume and sixteen times the 🎯 picks, so the gates that
hold it down are pinned here rather than left to a comment — and so is the fact
that the whole stream ships OFF.

That table was wrong once, in every file that quoted it, because it was written
from memory instead of from a study. research/studies/exhaust_rate.py exists so
it can be rerun, and this pins riptide/commands.py::EXHAUST_RATE to it.

    PYTHONPATH=. python3 tests/test_exhaust.py     # exit 1 on any failure
"""
import random
import sys

sys.path.insert(0, ".")

from riptide.engine import Candle                        # noqa: E402
from riptide.exhaust import _counts, digest, scan_symbol  # noqa: E402
from riptide.exhaust import Hit, _label, sig_of          # noqa: E402
from research.td import counts as td_counts              # noqa: E402

fails = []


def check(ok, what):
    print(f"  {'PASS' if ok else 'FAIL'}  {what}")
    if not ok:
        fails.append(what)


def series(n=4000, seed=11, drift=0.0):
    rnd = random.Random(seed)
    out, p = [], 100.0
    for i in range(n):
        p *= 1 + rnd.gauss(drift, 0.004)
        h = p * (1 + abs(rnd.gauss(0, 0.002)))
        lo = p * (1 - abs(rnd.gauss(0, 0.002)))
        out.append(Candle(t=i * 3600, o=p, h=h, l=lo, c=p, v=1000.0))
    return out


print("THE TWO PORTS AGREE, BAR FOR BAR")
# Three different shapes, because a drifting series and a flat one exercise
# different branches of the countdown's cancel rules.
for name, cs in (("random walk", series(4000, 11, 0.0)),
                 ("uptrend", series(2500, 22, 0.0008)),
                 ("downtrend", series(2500, 33, -0.0008))):
    mine = _counts(cs)
    theirs = td_counts(cs)
    bad = []
    for i in range(len(cs)):
        buy, sell, bcd, scd, bperf, sperf, bres, ssup = mine[i]
        if (buy != theirs.buy_setup[i] or sell != theirs.sell_setup[i]
                or bcd != theirs.buy_cd[i] or scd != theirs.sell_cd[i]
                or bperf != theirs.buy_perfect[i]
                or sperf != theirs.sell_perfect[i]
                or abs(bres - theirs.buy_res[i]) > 1e-9
                or abs(ssup - theirs.sell_sup[i]) > 1e-9):
            bad.append(i)
    n9 = sum(1 for i in range(len(cs))
             if mine[i][0] == 9 or mine[i][1] == 9)
    n13 = sum(1 for i in range(len(cs))
              if mine[i][2] == 13 or mine[i][3] == 13)
    check(not bad,
          f"{name}: {len(cs)} bars identical in both ports "
          f"({n9} nines, {n13} thirteens){'' if not bad else f' — first differs at {bad[0]}'}")

print("\nthe counts obey their own rules")
cs = series(4000, 11)
k = _counts(cs)
check(all(0 <= r[0] <= 9 and 0 <= r[1] <= 9 for r in k), "9-count never exceeds 9")
check(all(0 <= r[2] <= 13 and 0 <= r[3] <= 13 for r in k), "13-count never exceeds 13")
check(not any(r[0] and r[1] for r in k),
      "the two directions are never both counting on one bar")
first9 = next((i for i, r in enumerate(k) if r[0] == 9), None)
firstcd = next((i for i, r in enumerate(k) if r[2] > 0), None)
check(first9 is not None and firstcd is not None and firstcd >= first9,
      "no 13-count can start before a 9-count has completed")
check(all(r[4] is False or r[0] == 9 for r in k),
      "the perfected flag only ever rides on a completed 9")

print("\nTHE GATES THAT HOLD THE VOLUME DOWN")
# Measured across the real universe: 295 rows a day, against Riptide's ~85
# alerts and ~18 picks. Every one of these is a volume control and the defaults
# pick the quiet end; see the table in exhaust.py.
import asyncio                                           # noqa: E402


class FakeSem:
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False


def hits(want, perfect, data=None):
    async def fake_fetch(sess, symbol, tf):
        return data if data is not None else cs
    import riptide.exhaust as ex
    real, ex.fetch_candles = ex.fetch_candles, fake_fetch
    try:
        return asyncio.run(scan_symbol(None, FakeSem(), "AAA_USDT", "Min60",
                                       want, perfect))
    finally:
        ex.fetch_candles = real


# THE SERIES IS CUT SO A COMPLETION LANDS INSIDE THE WINDOW. scan_symbol only
# reads the last RECENT_BARS, and on a raw random walk nothing finishes there —
# so the first version of these assertions read "0 <= 0" and passed without
# testing anything. Truncating to end just after a 9 and a 13 is what makes
# them mean something.
def ending_at(kind_idx, want_val):
    for seed in range(200):
        c = series(1500, seed)
        k = _counts(c)
        for i in range(len(c) - 1, 80, -1):
            if k[i][kind_idx] == want_val:
                return c[:i + 2]          # that bar, plus one, inside the window
    raise AssertionError("no completion found to build the fixture from")


ends_on_9 = ending_at(0, 9)               # a buy-side 9 near the end
ends_on_13 = ending_at(2, 13)             # a buy-side 13 near the end
check(len(hits("both", False, data=ends_on_9)) > 0,
      "the fixture actually contains a completed count in the window")

both_all = hits("both", False, data=ends_on_9) + hits("both", False, data=ends_on_13)
both_perf = hits("both", True, data=ends_on_9) + hits("both", True, data=ends_on_13)
term_only = hits("terminal", False, data=ends_on_9) + hits("terminal", False, data=ends_on_13)
mom_only = hits("momentum", False, data=ends_on_9) + hits("momentum", False, data=ends_on_13)
check(len(both_all) >= 2,
      f"and enough of them to compare the gates against: {len(both_all)}")
check(len(term_only) > 0 and len(mom_only) > 0,
      f"both kinds are represented: {len(term_only)} terminal, "
      f"{len(mom_only)} momentum")
check(len(both_perf) <= len(both_all),
      f"requiring a perfected 9 never adds hits: {len(both_perf)} <= {len(both_all)}")
check(all(h.kind == "terminal" for h in term_only),
      "kinds='terminal' yields only 13-counts")
check(all(h.kind == "momentum" for h in mom_only),
      "kinds='momentum' yields only 9-counts")
check(len(term_only) + len(mom_only) == len(both_all),
      f"and the two partition 'both': {len(term_only)} + {len(mom_only)} "
      f"== {len(both_all)}")
check(all(h.perfect or h.kind == "terminal" for h in both_perf),
      "under perfect-only every 9-count reported is a perfected one")

print("\na short series is a symbol with no answer, not a quiet one")
check(hits("both", False, data=series(40)) == [],
      "under 60 bars nothing is reported rather than a partial count")

print("\nthe digest")


def mk(kind, is_long, perfect=False, sym="AAA_USDT", tf="Min60"):
    h = Hit()
    h.symbol, h.tf, h.is_long, h.kind, h.perfect = sym, tf, is_long, kind, perfect
    h.bar_time, h.price, h.level = 1789000000, 1.2345, 1.3
    h.sig = sig_of(sym, tf, 1789000000, kind, is_long)
    return h


msg = digest([mk("momentum", True, True, "AAA_USDT"),
              mk("terminal", True, sym="BBB_USDT"),
              mk("momentum", False, True, "CCC_USDT"),
              mk("terminal", False, sym="DDD_USDT")],
             ("Min60",), 1789000000)
plain = msg
check(plain.index("STRONG LONG") < plain.index("STRONG SHORT")
      < plain.index("possible long") < plain.index("possible short"),
      "groups run strongest first, so the top of the message is the rarest")
# The collision that took two goes to fix: a group label longer than its
# column runs straight into the symbol.
for g in ("STRONG LONG", "STRONG SHORT", "possible long", "possible short"):
    i = plain.index(g) + len(g)
    check(plain[i] == " ",
          f"{g!r} is followed by whitespace, not by the symbol")
check("BBB" in plain and "AAA" in plain, "every hit is listed")
check("M9★" in plain and "T13" in plain, "each row says which count it was")
check("no edge" in plain,
      "and the message says on its face that this was measured at nothing")
check(_label(mk("momentum", True, True)) == "M9★"
      and _label(mk("momentum", True, False)) == "M9"
      and _label(mk("terminal", True)) == "T13",
      "the labels match the chart indicator's own wording")

print("\nthe line cap holds")
many = [mk("momentum", True, True, f"S{i:02d}_USDT") for i in range(60)]
big = digest(many, ("Min60",), 1789000000)
check(big.count("tradingview.com") <= 20, f"capped: {big.count('tradingview.com')} rows")
check("more this close" in big, "and it says how many it left out")
check(len(big) < 4096, f"under Telegram's limit: {len(big)} chars")

print("\ndedupe keys separate everything that must stay separate")
keys = {sig_of("A_USDT", "Min60", 1, "momentum", True),
        sig_of("A_USDT", "Min60", 1, "momentum", False),
        sig_of("A_USDT", "Min60", 1, "terminal", True),
        sig_of("A_USDT", "Min30", 1, "momentum", True),
        sig_of("A_USDT", "Min60", 2, "momentum", True),
        sig_of("B_USDT", "Min60", 1, "momentum", True)}
check(len(keys) == 6,
      "symbol, timeframe, bar, kind and direction are all part of the key")

print("\nTHE COMMAND QUOTES THE MEASURED RATE, NOT A GUESS")
# /exhaust prints a per-day number next to every change it offers, and that
# number is the only thing telling the reader what they are turning on. If the
# table behind it drifts from research/studies/exhaustion.py, the command keeps
# answering confidently and wrongly — so the arithmetic is pinned here.
import sqlite3                                            # noqa: E402

import riptide.exhaust as _ex                              # noqa: E402
from riptide.commands import EXHAUST_RATE, _ex_rate, exhaust_cmd  # noqa: E402
from riptide.config import EXHAUST_ALERTS                  # noqa: E402

_db = sqlite3.connect(":memory:")
_db.execute("CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT)")
_ex.init(_db)

check(EXHAUST_RATE == {"Min15": (128, 96, 40), "Min30": (66, 49, 19),
                       "Min60": (34, 24, 9)},
      "the rate table still matches research/studies/exhaust_rate.out")
# WITHIN ONE, not exactly: EXHAUST_RATE stores each cell already rounded, so
# summing it and rounding the study's float sum can differ in the last digit
# (296 here against the study's 295). Demanding equality would make this fail
# on arithmetic rather than on drift, which is the only thing it is for.
_all = _ex_rate(_db, tfs=("Min15", "Min30", "Min60"), want="both",
                perfect=False)
check(abs(_all - 295) <= 1,
      f"everything on, unfiltered, is the ~295 rows a day the gates exist "
      f"for: {_all}")
_quiet = _ex_rate(_db, tfs=("Min60",), want="both", perfect=True)
check(abs(_quiet - 34) <= 1,
      f"and the quiet corner it starts in is ~34 a day: {_quiet}")
check(_ex_rate(_db, tfs=("Min60",), want="terminal") == 9
      and _ex_rate(_db, tfs=("Min60",), want="momentum", perfect=True) == 24,
      "the two kinds partition that rate")
check(_ex_rate(_db, perfect=True) <= _ex_rate(_db, perfect=False),
      "perfected-only can never raise the rate")

_ = exhaust_cmd(_db, "/exhaust 30m,1h")
check(_ex.intervals(_db) == ("Min30", "Min60"), "/exhaust sets the timeframes")
_ = exhaust_cmd(_db, "/exhaust terminal")
check(_ex.kinds(_db) == "terminal", "/exhaust sets the kind")
_ = exhaust_cmd(_db, "/exhaust perfect off")
check(_ex.perfect_only(_db) is False, "/exhaust perfect off clears the gate")
# IT SHIPS OFF: the counts measured negative, so the stream is built and
# dormant until someone asks for it. A default flipped back to on by an edit
# would be silent, so it is asserted rather than trusted.
check(EXHAUST_ALERTS is False,
      "the stream is OFF by default — it is opt-in, not opt-out")
check(_ex.enabled(_db) is False, "and a fresh database agrees")
_ = exhaust_cmd(_db, "/exhaust on")
check(_ex.enabled(_db) is True, "/exhaust on starts it")
_ = exhaust_cmd(_db, "/exhaust off")
check(_ex.enabled(_db) is False, "/exhaust off stops it again")
bad = exhaust_cmd(_db, "/exhaust 5m")
check("must come from" in bad and _ex.intervals(_db) == ("Min30", "Min60"),
      "an unmeasured timeframe is refused and changes nothing")
body = exhaust_cmd(_db, "/exhaust")
check("+0.273" in body and "not a trade" in body.lower(),
      "the status body states the negative control rather than burying it")
for m in (exhaust_cmd(_db, "/exhaust"), exhaust_cmd(_db, "/exhaust on"),
          exhaust_cmd(_db, "/exhaust both")):
    check(len(m) < 4096, f"the reply fits Telegram's cap: {len(m)} chars")

print("\n" + ("ALL PASS" if not fails
               else f"{len(fails)} FAILED:\n  " + "\n  ".join(fails)))
sys.exit(1 if fails else 0)
