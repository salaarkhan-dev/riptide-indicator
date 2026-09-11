"""Closing the gap between what a bot can pick and what hindsight would pick.

THE GAP IS REAL AND IT IS 1.75 RECOVERY. `pick_rule.py` scored one pick per
market event two ways. With hindsight — knowing at 11:30 what will arrive at
12:00 — it reaches 5.46 recovery and +860% on a 300 USDT account. Causally,
with a rolling 60-minute cooldown and the first arrival claiming the pick, it
reaches 3.71 and +375%. No bot can have the first number. The question this
file asks is how much of the difference is reachable by ENGINEERING rather than
by clairvoyance.

WHERE THE LOSS COMES FROM, precisely. A Min60 setup on the 11:00 bar is not
knowable until 12:00. A Min15 setup on the 11:15 bar is knowable at 11:30. Both
belong to the same market move. The causal rule names the 15m signal at 11:30,
because it is the only candidate that exists; hindsight names the 1h one. The
loss is therefore concentrated in a specific case — a WEAK early candidate
burning the event's pick before a strong late one can arrive — and that is a
case a rule can be written about.

TWO LEVERS, AND ONLY ONE OF THEM IS FREE.

  LEVER 1, A QUALITY GATE ON CLAIMING. A signal that does not meet a bar does
  not claim the pick; it defers and the event stays open for something better.
  Costs nothing in fills, because nothing is delayed — the alert still sends at
  the same instant, it simply does not wear the target. The risk is the
  opposite one: if the bar is set too high the event closes with no pick at all
  and a tradeable signal went unmarked.

  LEVER 2, A DELAYED DECISION. Hold the pick back for N minutes, then name the
  best of everything that arrived. This is NOT free and the cost is easy to
  hide: the entry is a limit at the gap edge, and a fill that happened during
  the wait is a fill you did not take. So every delayed variant here is scored
  from the DELAYED bar — `poi_tf.collect(delays=...)` re-simulates the trade as
  if the order were placed that much later, missing whatever filled meanwhile.
  A study that delayed the decision but kept the original fill would be
  measuring a bot that can place orders in the past.

  LEVER 3 IS NOT TESTED AND SHOULD BE NAMED ANYWAY. "Send an upgrade message
  when something better arrives" does not work: you have already taken the
  first trade, so an upgrade means either holding two positions — which
  pick_rule.py measured at 1.75 recovery against 4.85, a disaster — or closing
  a trade on a signal, which this project has never measured and has no exit
  model for.

PRE-REGISTERED, BEFORE THE FIRST NUMBER

  BASELINE. The causal rolling-60m rule at 3.71, and the hindsight ceiling at
  5.46. Every variant is judged against the first and measured against the
  second.

  PRIMARY. Recovery factor, with the two halves of the window printed beside
  it, because a parameter chosen from four options on one window is exactly
  where this project has been burned before.

  EXPECTATION. The quality gate helps and the delay does not. A gate costs
  nothing and targets the failure directly; a delay pays a fill-rate tax on
  EVERY trade to fix a minority of events. I expect "only a take-band signal
  may claim" to land between 3.71 and 4.5, and every delayed variant to come
  in BELOW 3.71 once the missed fills are counted. If a delay wins anyway, the
  fill tax is smaller than I think and that is worth knowing.

  WHAT WOULD MAKE ME DISTRUST A WINNER. A variant whose advantage sits in one
  half of the window, or one that only wins at the most permissive of the
  parameters tried. Both are recorded per row rather than argued about after.

    PYTHONPATH=. RIPTIDE_MIN_GRADE=B RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/pick_hybrid.py

RESULT, 11 Sep 2026 — THE GAP IS NOT ENGINEERABLE. NOTHING BEATS THE BASELINE,
AND THE REASON IS WORTH MORE THAN THE ANSWER.

Eighteen variants, every one causal, every delayed one scored from its delayed
bar. Baseline is the shipped-next rolling 60m rule at 3.71 recovery.

    rule                              /day  recov  1st½  2nd½    acct
    rolling 60m (the baseline)        23.6   3.71  1.21  3.20   +348%
    claim needs: not a skip           20.7   3.15  0.98  3.19   +311%
    claim needs: take band            11.4   2.82  0.03  6.64   +238%
    claim needs: take band AND 30m+    7.3   2.81  0.17  5.54   +176%
    claim needs: 1h only               5.9   2.64  0.18  2.66   +118%
    claim needs: 30m or slower        13.7   2.60 -0.23  5.41   +191%
    claim needs: take band OR 1h      13.7   2.44 -0.53  6.88   +204%
    claim needs: confirmed             5.0   2.08 -0.16  5.91   +102%
    wait 15m, then pick the best      13.3   0.38 -0.66  1.74      +3%
    wait 30m                          12.5  -0.50 -0.82  0.63     -57%
    wait 60m                          11.0  -0.69 -0.86  0.44     -70%
    1h now, else wait 30m              4.6   0.40 -0.30  1.60     +10%
    take-band now, else wait 15m       8.0   0.51 -0.69  2.32     +14%

EIGHTEEN FOR EIGHTEEN, ALL WORSE. That is not a near miss to be tuned; it is a
clean negative, and the hindsight ceiling of 5.46 should be struck from any
future argument as unreachable rather than kept as a target.

MY EXPECTATION WAS HALF RIGHT AND THE HALF I GOT WRONG IS THE INTERESTING ONE.
I predicted the delay would fail and the quality gate would help. The delay
failed harder than predicted. The gate failed too, and the mechanism is simple:
an event nobody is allowed to claim contributes NOTHING, and the trades a gate
refuses to start on are worth more than the better ones it occasionally waits
for. "Claim needs: take band" cuts the stream from 23.6 a day to 11.4 and the
recovery from 3.71 to 2.82 — half the alerts for three quarters of the quality.
This is the same shape as pick_rule.py's finding that dropping the skip band
hurts: on this strategy, a rule that sometimes takes NOTHING loses to a rule
that always takes SOMETHING.

THE DELAY TABLE IS THE REAL FINDING AND IT IS NOT ABOUT PICKING AT ALL. The
same trades, scored at each delay, with no pick rule involved:

    delay    still fills   R per trade   total R
      0m           100%        +0.006      +52.9
     15m            96%        -0.054     -469.7
     30m            94%        -0.082     -704.4
     60m            91%       -0.141    -1166.5

ONLY 4% OF FILLS ARE LOST AT FIFTEEN MINUTES. The collapse is not missed
fills. It is that the SAME trades, entered a quarter hour later, are worth
-0.054 instead of +0.006 — the remaining 96% each lose about 0.06 R. Placing
the order late means buying into a move that has already happened: these are
reversal setups off a liquidity sweep, the gap fills fast or not at all, and
by the next bar the edge has been paid out to whoever was already there.

That reframes the whole question. The bot is not slow at choosing. The strategy
has no tolerance for waiting, which is also why `mtf.py`'s lower-timeframe
entry was retired and why FRESH_BARS is 2. Any future proposal that involves
holding a signal back — for confirmation, for confluence, for a better
candidate — now has a measured price on it: about 0.06 R per trade per fifteen
minutes, which is ten times the strategy's entire per-trade edge.

THE ONE ROW THAT WILL TEMPT SOMEBODY, flagged before it does. "Claim needs:
take band" scores 6.64 in the second half of the window against the baseline's
3.20 — nearly double. Its first half is 0.03. A rule whose whole advantage
sits in one half of one window is the exact pattern entry_deep.py and
universe_size.py were written about, and four of the eight gate variants show
the same split. Read the first-half column first.

WHAT THIS CLOSES. The pick rule as a family. The grouping is settled (rolling
60m), the ordering is settled (tf first, which has now won under hindsight, per
scan, and under a cooldown), and the gap to hindsight is closed as
unreachable. The remaining open question is the 120m cooldown from
pick_rule.py, which is a length parameter and not a mechanism.
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import statistics                                       # noqa: E402
from collections import defaultdict                     # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import BAR_SECONDS                  # noqa: E402
from research.deep import load_universe                 # noqa: E402
from research.studies.poi_tf import DAY, DAYS, H8       # noqa: E402
from research.studies.poi_tf import collect, context, universe  # noqa: E402
from research.studies.report import START, compound, drawdown  # noqa: E402
from research.studies.survivor import LO, HI            # noqa: E402

TFS = ("Min15", "Min30", "Min60")
NSYM = 59
SCAN = 900                      # the bot wakes on every Min15 close
COOLDOWN = 3600                 # the shipped rolling window
DELAYS = (900, 1800, 3600)      # decision held back by 1, 2 or 4 scans


def band_of(t):
    if LO <= t.risk_pct <= HI:
        return 0
    return 1 if t.risk_pct < LO else 2


def key_tf(t):
    return (-BAR_SECONDS[t.tf], band_of(t),
            0 if t.kind == "confirmed" else 1, t.sym)


def arrival(t):
    """The scan cycle that first SEES this signal — its bar close, rounded up
    to the next wake."""
    seen = t.t + BAR_SECONDS[t.tf]
    return -(-seen // SCAN) * SCAN


def run(rows, claim=None, delay=0, cooldown=COOLDOWN):
    """One causal pass in arrival order.

    `claim` is the quality gate: a predicate a signal must satisfy to START an
    event. Signals that fail it still exist and can still be PICKED once an
    event is open — they simply cannot open one, which is the whole point.

    `delay` holds the decision back that many seconds after the event opens,
    and the chosen trade is then scored from its delayed bar.
    """
    byscan = defaultdict(list)
    for t in rows:
        byscan[(arrival(t), t.is_long)].append(t)

    last, out = {}, []
    open_at, pending = {}, defaultdict(list)
    for seen, up in sorted(byscan):
        here = byscan[(seen, up)]

        # Anything already waiting on an open event collects the new arrivals.
        if up in open_at:
            pending[up].extend(here)
            if seen - open_at[up] >= delay:
                best = min(pending[up], key=key_tf)
                r = best.rd.get(delay) if delay else best.r
                if r is not None:
                    out.append((best, r, seen))
                    last[up] = seen
                open_at.pop(up)
                pending.pop(up, None)
            continue

        if seen - last.get(up, -(1 << 40)) < cooldown:
            continue
        starters = [t for t in here if claim is None or claim(t)]
        if not starters:
            continue
        if delay:
            open_at[up] = seen
            pending[up] = list(here)
            continue
        best = min(starters, key=key_tf)
        out.append((best, best.r, seen))
        last[up] = seen
    return out


def score(name, picked):
    if len(picked) < 40:
        print(f"  {name:<38}{len(picked):>6}   too thin")
        return
    order = sorted(picked, key=lambda p: p[0].exit_t)
    rs = [r for _, r, _ in order]
    dd, _ = drawdown(rs)
    halves = []
    for part in (order[:len(order) // 2], order[len(order) // 2:]):
        h = [r for _, r, _ in part]
        d, _ = drawdown(h)
        halves.append(sum(h) / d if d else 0.0)
    # compound() reads .r, so hand it a shim carrying the SCORED return rather
    # than the undelayed one. Anything else would price the delay for free.
    shim = [type("P", (), {"filled": True, "fill_t": t.fill_t,
                           "exit_t": t.exit_t, "r": r})()
            for t, r, _ in order]
    bal, ddc, _ = compound(shim, max_open=10)
    print(f"  {name:<38}{len(picked) / DAYS / NSYM * 120:>6.1f}"
          f"{len(picked):>7}{sum(rs):>8.1f}{dd:>7.1f}"
          f"{sum(rs) / dd if dd else 0:>7.2f}{halves[0]:>7.2f}"
          f"{halves[1]:>7.2f}{100 * (bal / START - 1):>+8.0f}%{ddc:>6.0%}")


async def main():
    rows = []
    async with aiohttp.ClientSession() as sess:
        syms = await universe(sess)
        zday = await context(sess, syms, DAY)
        z8h = await context(sess, syms, H8)
        for tf in TFS:
            cs = await load_universe(
                sess, syms, tf, DAYS,
                min_bars=int(0.8 * DAYS * 86400 // BAR_SECONDS[tf]))
            got = await collect(sess, cs, zday, z8h, interval=tf,
                                delays=DELAYS)
            rows += [t for t in got
                     if t.filled and t.exit_t is not None and t.day]

    print("CLOSING THE GAP TO THE HINDSIGHT PICK")
    print(f"{len(syms)} symbols, {DAYS} days, 15m+30m+1h, the stream the bot")
    print("sends. every row is CAUSAL; a delayed row is scored from the")
    print("delayed bar, so a fill missed while waiting is a fill lost.")
    print(f"\n  {'rule':<38}{'/day':>6}{'trades':>7}{'total':>8}{'maxDD':>7}"
          f"{'recov':>7}{'1st½':>7}{'2nd½':>7}{'acct':>9}{'accDD':>6}")

    print("  -- the baseline it has to beat " + "-" * 45)
    score("rolling 60m, first arrival claims", run(rows))

    print("  -- LEVER 1: only some signals may CLAIM the event " + "-" * 26)
    score("claim needs: take band", run(rows, lambda t: band_of(t) == 0))
    score("claim needs: not a skip", run(rows, lambda t: band_of(t) != 2))
    score("claim needs: 30m or slower",
          run(rows, lambda t: BAR_SECONDS[t.tf] >= 1800))
    score("claim needs: 1h only",
          run(rows, lambda t: BAR_SECONDS[t.tf] >= 3600))
    score("claim needs: confirmed",
          run(rows, lambda t: t.kind == "confirmed"))
    score("claim needs: take band AND 30m+",
          run(rows, lambda t: band_of(t) == 0 and BAR_SECONDS[t.tf] >= 1800))
    score("claim needs: take band OR 1h",
          run(rows, lambda t: band_of(t) == 0 or BAR_SECONDS[t.tf] >= 3600))

    print("  -- LEVER 2: hold the decision back, and pay for it " + "-" * 25)
    for d in DELAYS:
        score(f"wait {d // 60}m, then pick the best", run(rows, delay=d))

    print("  -- HYBRID: strong signals go now, weak ones wait " + "-" * 27)
    for d in DELAYS:
        score(f"1h goes now, else wait {d // 60}m",
              run(rows, lambda t: BAR_SECONDS[t.tf] >= 3600, delay=d))
    for d in DELAYS:
        score(f"take-band goes now, else wait {d // 60}m",
              run(rows, lambda t: band_of(t) == 0, delay=d))

    print("\n-- IF WE MUTED PART OF THE STREAM ENTIRELY " + "-" * 33)
    print("  not a claim gate — these signals would not be SENT at all, so")
    print("  they cannot be picked either. cooldown 120m throughout.")
    print(f"  {'stream kept':<38}{'/day':>6}{'trades':>7}{'total':>8}"
          f"{'maxDD':>7}{'recov':>7}{'1st½':>7}{'2nd½':>7}{'acct':>9}"
          f"{'accDD':>6}")
    slow = {"Min30": 1800, "Min60": 3600}
    for name, keep in (
            ("everything", lambda t: True),
            ("mute early 15m", lambda t: not (t.kind == "early"
                                              and t.tf == "Min15")),
            ("mute early 15m+30m", lambda t: not (t.kind == "early"
                                                  and t.tf != "Min60")),
            ("mute ALL early", lambda t: t.kind == "confirmed"),
            ("mute 15m entirely", lambda t: t.tf != "Min15"),
            ("confirmed + early 1h only",
             lambda t: t.kind == "confirmed" or t.tf == "Min60")):
        score(name, run([t for t in rows if keep(t)], cooldown=7200))

    print("\n-- WHAT THE DELAY COSTS, ON ITS OWN " + "-" * 40)
    print("  the same trades, scored at each delay, ignoring any pick rule.")
    print(f"  {'delay':<10}{'still fills':>12}{'R/trade':>10}{'total':>9}")
    base = [t for t in rows]
    for d in (0,) + DELAYS:
        got = [(t.r if not d else t.rd.get(d)) for t in base]
        ok = [r for r in got if r is not None]
        print(f"  {d // 60:>3}m{'':<6}{len(ok) / len(got):>11.0%}"
              f"{statistics.fmean(ok):>+10.3f}{sum(ok):>9.1f}")


if __name__ == "__main__":
    asyncio.run(main())
