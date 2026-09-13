"""The account simulator must close every position it opens.

WHY THIS FILE EXISTS. research/studies/portfolio.py produced the whole
"Per portfolio" section of TRADING.md — the concurrency cap, the confirmed-slot
reservation, the claim that drawdown falls monotonically as the cap tightens.
Every one of those numbers was wrong, and the cause was four lines of event
ordering.

Events were sorted so a CLOSE (kind 0) precedes an OPEN (kind 1) at the same
timestamp, which is right: a slot should be freed before that instant's new
entries compete for it. But for a trade whose own fill and exit land on the
same timestamp — filled and stopped out inside one bar — its own close was
therefore processed FIRST, found nothing in open_pos, and silently returned.
The open that followed added a position that nothing would ever close.

353 of 9071 real rows are same-bar stop-outs. The first `max_open` of them
pinned every slot permanently. The account took 195 trades in month one and
then nothing for eleven months, and reported +34% on a 7% drawdown.

THAT IS THE FAILURE MODE WORTH A TEST. Not a crash, not an exception — a
plausible number. The output looked like a result for as long as anyone cared
to read it. The one visible tell was that `max 12 open` and `everything, no
rules` returned byte-identical rows, which no real cap does, and that went past
two separate reruns unnoticed.

So this asserts the invariant no report can show you: every position opened is
eventually closed, and a cap actually caps.

    PYTHONPATH=. python3 tests/test_portfolio_sim.py     # exit 1 on any failure
"""
import sys

sys.path.insert(0, ".")

from research.studies.portfolio import Rules, simulate, START  # noqa: E402

fails = []


def check(ok, what):
    print(f"  {'PASS' if ok else 'FAIL'}  {what}")
    if not ok:
        fails.append(what)


class Sig:
    __slots__ = ("is_long",)

    def __init__(self, is_long):
        self.is_long = is_long


class Row:
    """The fields simulate() reads, and nothing else."""
    __slots__ = ("filled", "fill_time", "exit_time", "r", "risk_pct",
                 "kind", "signal")

    def __init__(self, fill, exit, r, risk=1.0, kind="confirmed", up=True):
        self.filled = True
        self.fill_time = fill
        self.exit_time = exit
        self.r = r
        self.risk_pct = risk
        self.kind = kind
        self.signal = Sig(up)


DAY = 86400


def spaced(n, r=1.0, same_bar=False, start=1_600_000_000):
    """n trades, one per day, each closing before the next opens.

    With same_bar=True every trade fills and exits on the SAME timestamp — the
    exact shape that leaked.
    """
    out = []
    for i in range(n):
        t = start + i * DAY
        out.append(Row(t, t if same_bar else t + 3600, r))
    return out


print("EVERY POSITION OPENED IS EVENTUALLY CLOSED")
# THE REGRESSION. Before the fix this took max_open trades and then nothing:
# each same-bar trade leaked a slot and the cap never recovered.
for cap in (1, 3, 8):
    rows = spaced(60, r=-1.0, same_bar=True)
    res = simulate(rows, Rules(name="x", max_open=cap, risk_pct=0.5))
    got = res["n"] if res else -1
    check(got == 60 or res is None,
          f"cap {cap}: all 60 same-bar stop-outs are taken, not {cap} "
          f"then frozen (took {got})")

# A same-bar stop-out must still cost money. If it were merely skipped rather
# than leaked, the count would look right and the P&L would be a lie.
win = simulate(spaced(20, r=+2.0, same_bar=True),
               Rules(name="w", max_open=8, risk_pct=0.5))
lose = simulate(spaced(20, r=-1.0, same_bar=True),
                Rules(name="l", max_open=8, risk_pct=0.5))
check(win and win["ret"] > 0, f"20 same-bar winners end up ahead: {win['ret']:+.1f}%")
check(lose and lose["ret"] < 0, f"20 same-bar losers end up behind: {lose['ret']:+.1f}%")
check(win and win["win"] == 100, "and they are counted as wins")
check(lose and lose["win"] == 0, "and as losses")

print("\nA CAP ACTUALLY CAPS")
# 40 trades all open at once and close much later, so the cap is the only
# thing that can limit them.
t0 = 1_600_000_000
overlap = [Row(t0 + i, t0 + 100 * DAY, -1.0) for i in range(40)]
for cap in (1, 3, 8, 20):
    res = simulate(overlap, Rules(name="c", max_open=cap, risk_pct=0.5))
    check(res is not None and res["n"] <= cap,
          f"max_open={cap} never holds more than {cap} at once "
          f"(took {res['n'] if res else 'BLEW UP'})")

# THE TELL THAT WAS MISSED. Two different caps must not return identical rows
# on a population big enough to bind. That equality is what a leak looks like.
a = simulate(overlap, Rules(name="a", max_open=3, risk_pct=0.5))
b = simulate(overlap, Rules(name="b", max_open=12, risk_pct=0.5))
check(a["n"] != b["n"],
      f"different caps give different trade counts: {a['n']} vs {b['n']} — "
      f"equality here is the signature of the 12 Sep leak")

print("\nTHE ARITHMETIC STILL ADDS UP")
res = simulate(spaced(10, r=+2.0), Rules(name="p", max_open=8, risk_pct=1.0,
                                         compound=False))
# Flat sizing, 1% risk, +2R each: 10 trades * 2R * 1% = +20% of START.
check(res is not None and abs(res["ret"] - 20.0) < 0.01,
      f"flat 1% risk, ten +2R trades = +20%: got {res['ret']:+.2f}%")
res = simulate(spaced(10, r=-1.0), Rules(name="q", max_open=8, risk_pct=1.0,
                                         compound=False))
check(res is not None and abs(res["ret"] + 10.0) < 0.01,
      f"and ten -1R trades = -10%: got {res['ret']:+.2f}%")

blown = simulate([Row(t0 + i * DAY, t0 + i * DAY + 3600, -1.0, risk=100.0)
                  for i in range(5)],
                 Rules(name="z", max_open=8, risk_pct=100.0, compound=False))
check(blown is None, "an account taken to zero returns None rather than "
                     "reporting a negative balance as a result")

print("\n" + ("ALL PASS" if not fails
               else f"{len(fails)} FAILED:\n  " + "\n  ".join(fails)))
sys.exit(1 if fails else 0)
