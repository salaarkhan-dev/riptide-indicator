"""Which ONE signal to take when a raid fires on many symbols and timeframes.

THE PROBLEM IS NOW THREE TIMES BIGGER THAN THE RULE THAT SOLVES IT. A market
move raids pools on dozens of perpetuals inside the same hour, and since Min60
was added on 11 Sep each of those can print on 15m, 30m and 1h. The deployed
`tag_event_pick` groups on (tf, bar, direction) — strictly INSIDE one timeframe
— so it names three picks for one market event and the reader sees three
targets. That is the failure the "size once" chip exists to prevent, arriving
through a door the chip does not watch.

`portfolio_v2.py` already established that picking ONE matters more than which
one: over 2445 same-bar events, taking everything returned +180.7 R at a 135.9
drawdown (recovery 1.33), one ARBITRARY symbol returned +98.7 at 69.2 (1.43),
and one chosen by risk band returned +112.7 at 61.4 (1.84). Halving the return
while nearly halving the drawdown is worth nothing; moving the RATIO is the
whole game.

So this file asks the next question: across symbols AND timeframes AND streams,
what ORDER should the tiebreaks go in?

WHAT THE EVIDENCE SAYS ABOUT EACH CANDIDATE AXIS, before any rule is scored:

  THE RISK BAND is the strongest thing this project has. matrix.py: band
  against outside separates on 6 of 6 timeframe/stream combinations, two of
  them at 2 SE, with nothing refitted — the 1.2/2.6 boundaries come from Min30
  confirmed and were applied unchanged to Min15 and to early.

  THE TIMEFRAME has no statistical support and a structural argument. No pair
  of timeframes separates at even 1 SE (timeframes.py), so "1h beats 30m" is
  not a claim. But fee in R is fee_pct/risk_pct and the median stop doubles
  from 15m to 1h, so the fee eats 67% of the gross edge on 15m and 16% on 1h —
  arithmetic, not noise. Preferring the slower timeframe is a COST argument.

  CONFIRMED OVER EARLY is weak. matrix.py: confirmed leads early in 5 of 6
  comparisons and clears 1 SE in none of them.

  THE POI is nearly worthless as a tiebreak. poi_recheck.py: of twelve cells it
  helps in exactly one, Min30 confirmed on the daily map, and every early cell
  is negative in both maps. It is included as a variant so that "nearly" is a
  measurement rather than an assumption.

PRE-REGISTERED, BEFORE THE FIRST NUMBER

  PRIMARY. Recovery factor (total R / max drawdown) of the picked stream, per
  rule, on the same events. Recovery rather than total R, for the reason
  portfolio_v2.py gives: any rule that simply trades less shrinks both and is
  worth nothing.

  SECONDARY. The compounded account at 1% risk with at most ten open, alerts a
  day, and win rate — the three things a reader actually feels.

  EXPECTATION. Every pick rule beats taking everything on recovery, by a wide
  margin, because that is what portfolio_v2.py already found within one
  timeframe and the cross-timeframe case only adds duplicates. Among the pick
  rules I expect band-first to beat every other ordering, because the band is
  the only axis with replicated evidence, and I expect the orderings that
  differ only in where TF and CONFIRMED sit to land within noise of each other.
  Confirmed-only should have the best recovery and much the lowest volume.

  WHAT WOULD CHANGE MY MIND. If an ordering that puts TF or CONFIRMED above the
  band wins on recovery by more than its own spread across the two halves of
  the window, the band is not the dominant axis and the deployed rule is wrong.

    PYTHONPATH=. RIPTIDE_MIN_GRADE=B RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/pick_rule.py

RESULT, 11 Sep 2026 — THE PICK RULE IS WORTH MORE THAN EVERY FILTER THIS
PROJECT HAS EVER FOUND, COMBINED.

9071 filled trades in 4200 market events, 59 symbols, 333 days, on the stream
the bot actually sends. Median event holds 1 signal, mean 2.2, largest 27, and
54% are singletons where no rule does anything at all.

   rule                            /day  total  maxDD  recov  1st½  2nd½   acct
   take everything                 55.4   52.9  410.7   0.13 -0.48  1.31   -51%
   one at random                   25.7  180.6   80.3   2.25  0.45  2.03  +234%
   band only                       25.7  228.9   78.1   2.93  0.72  2.26  +367%
   band -> confirmed -> tf         25.7  288.8   59.6   4.85  1.27  3.64  +580%
   band -> tf -> confirmed         25.7  291.8   60.7   4.80  1.18  3.69  +593%
   confirmed -> band -> tf         25.7  280.5   61.5   4.56  1.32  3.35  +545%
   tf -> band -> confirmed         25.7  318.6   58.4   5.46  1.68  3.87  +860%
   top 2 per event                 37.4  248.3  141.5   1.75 -0.12  2.51  +188%
   top 3 per event                 43.5  188.7  236.6   0.80 -0.51  2.71   +75%

RECOVERY 0.13 TO 5.46 FROM A LABEL. Nothing else measured on this project moves
a number forty-fold. Taking every signal the bot sends compounds a 300 USDT
account to MINUS 51% at a 95% drawdown; taking one per market event compounds
it to +860% at 49%. Even a RANDOM pick gets 2.25 and +234% — most of the value
is in taking one, exactly as portfolio_v2.py found within a single timeframe,
and the ordering is the smaller half of the prize.

MY PRE-REGISTERED EXPECTATION WAS WRONG ABOUT WHICH ORDERING WINS. I predicted
band-first, because the band is the only axis with replicated evidence.
TF-first won, 5.46 against 4.85, in BOTH halves of the window (1.68 vs 1.27,
3.87 vs 3.64), which is the check that was supposed to catch a fluke.

READ THAT WITH ITS WEAKNESS ATTACHED. TF-first wins by preferring the 1h
signal whenever one exists, and no pair of timeframes separates at even 1 SE
(timeframes.py). So the winning rule leans hardest on the axis with the least
statistical support. What it does have is a STRUCTURAL argument that is
arithmetic rather than inference: fee in R is fee_pct/risk_pct, the median stop
doubles from 15m to 1h, and the fee eats 67% of the gross edge on 15m against
16% on 1h. Band-first is 0.66 recovery behind and rests on better evidence.
Both are rankings, not filters — nothing is suppressed either way, and the cost
of choosing wrong is picking a different member of the same event.

THREE THINGS THAT SOUND RIGHT AND MEASURE WRONG.

  TAKING THE TOP TWO OR THREE undoes almost all of it: 1.75 and 0.80 against
  5.46. Strictly one.

  DROPPING THE "skip" BAND from the pick HURTS — 4.08 against 4.85. An all-skip
  event then contributes nothing, and the best-of-a-bad-event turns out to
  carry more edge than sitting out. The band is a good ORDERING and a bad GATE,
  which is the same conclusion the deployed advisory label already reached.

  CONFIRMED-ONLY IS NOT THE SAFE CHOICE IT LOOKS LIKE. Confirmed only, band
  then tf, scores 1.17 — against 4.85 for the mixed pick — and its halves are
  -0.40 and +4.04, so all of its apparent quality sits in the second half of
  the window. EARLY only, band then tf, scores 3.76 and +403%. Early
  signals are not the problem. Taking many at once is the problem, and early is
  simply where most of the many are.

  The confirmed-only variant worth keeping in view is band -> tf with skip
  dropped: 4.1 alerts a day, recovery 2.70, a 24% account drawdown against 49%
  for the mixed pick. Ten times less return for half the pain and a sixth of
  the messages. That is a product decision, not a measurement.

TF-FIRST ALSO WINS INSIDE EACH STREAM SEPARATELY, which the mixed table could
not show. In a mixed event the confirmed/early axis is doing work, so "tf beats
band" there might be tf standing in for something else. Held constant:

    EARLY  take all    48.8/day  recov -0.02   acct  -44%
    EARLY  at random   24.5/day  recov  2.50   acct +190%
    EARLY  band only   24.5/day  recov  2.45   acct +271%
    EARLY  band -> tf  24.5/day  recov  3.76   acct +403%
    EARLY  tf -> band  24.5/day  recov  4.71   acct +655%   1st half 1.45
    CONFD  take all     6.7/day  recov  0.96   acct  +48%
    CONFD  at random    5.2/day  recov  1.20   acct  +73%
    CONFD  band only    5.2/day  recov  1.12   acct  +65%
    CONFD  band -> tf   5.2/day  recov  1.17   acct  +68%
    CONFD  tf -> band   5.2/day  recov  1.33   acct  +82%
    CONFD  band->tf, no skip  4.1/day  recov 2.70  acct +86%

TF-first wins in both streams and in both halves of each. So the ordering
result is not an artefact of mixing streams.

THE EARLY STREAM IS WORTH -44% TAKEN WHOLE AND +655% TAKEN ONE PER HOUR. That
single pair of numbers is the clearest statement in this repository of what the
pick rule is for. Early signals are not bad signals; they arrive in crowds, and
a crowd taken whole is a correlated bet with no diversification in it at all.

AND HERE IS THE UNCOMFORTABLE PART, WHICH EXPLAINS WHY TF BEATS BAND. R per
TRADE by timeframe and band, on the deployed stream:

    stream     tf     take     flat     skip
    early      15m  -0.038   -0.025   +0.058
    early      30m  -0.023   +0.011   +0.150
    early      1h   +0.066   +0.066   -0.027
    confirmed  15m  +0.183   -0.127   -0.198
    confirmed  30m  +0.241   -0.049   +0.103
    confirmed  1h   +0.095        -   +0.059

THE RISK BAND IS A CONFIRMED-SIGNAL FILTER. On confirmed it orders the cells
the way it is supposed to — take best on all three timeframes, and on Min15 the
spread is +0.183 against -0.198. On EARLY at 15m and 30m it is INVERTED: the
"skip" cell is the best one, +0.058 and +0.150. Only on 1h early does it point
the right way.

That is not a contradiction of matrix.py, which measured the band on early at
+0.002 (15m) and +0.020 (30m) per bet — near zero, with the real effect only on
1h at +0.108. Near-zero and inverted-on-a-subsample are the same statement made
twice. It does mean the band carries little information inside the early
stream, which is exactly why ordering by TF beats ordering by band there: the
band is close to a coin toss on 83% of the pick candidates, while the fee
argument for the slower timeframe holds everywhere.

DO NOT READ THE INVERSION AS "TAKE WIDE-STOP EARLY SIGNALS". These are cells of
a 18-cell table on 40 to 2576 trades each, scored per trade rather than per
bet, so the same clustering that ruins the raw stream inflates their apparent
precision. What is safe to conclude is the negative: the band does not order
early signals, so it should not be the first key when early signals are in the
pool.

WHAT THE PICK CHOOSES under band -> confirmed -> tf: 49% Min15, 30% Min30, 20%
Min60; 17% confirmed, 83% early; 47% take band, 41% flat, 12% skip. Under
tf-first the timeframe mix inverts, which is the whole mechanism.

THE POI VARIANT IS DEGENERATE AND IS LEFT IN AS A NOTE. The scored stream is
already POI-filtered, because that is what the bot sends, so a POI tiebreak is
constant across every member of every event and the row is identical to
band -> confirmed -> tf by construction. It measures nothing; it is not
evidence that the POI is a useless tiebreak.

CROSS-TIMEFRAME DUPLICATION IS REAL BUT SMALL: 845 of 7547 symbol-events print
on two or more timeframes, 11%. So the 🔁 chip shipped today marks about one
alert in nine, and the cross-timeframe half of the pick rule matters much less
than the cross-SYMBOL half, which is most of the mean event size of 2.2.

WHAT A BOT CAN ACTUALLY DO, AND WHY 5.46 IS NOT IT. Every row above keys on
the signal's own bar time, which quietly uses hindsight: a Min60 setup on the
10:00 bar is not knowable until 11:00, while a Min15 setup on the 10:15 bar is
knowable at 10:30. Both floor into the 10:00 hour, so an hour-keyed grouping
puts them in one event — but they arrive in different scan cycles, and the
earlier one's message has already been sent by the time the later one exists.

    per bar per tf (before 11 Sep)       36.0/day  recov 1.39  acct +104%
    AS SHIPPED 11 Sep (scan+hour key)    33.8/day  recov 2.46  acct +396%
    per SCAN cycle, across tfs           33.8/day  recov 2.46  acct +396%
    per hour, first arrival claims it    25.7/day  recov 3.60  acct +394%
    per hour, WITH hindsight              25.7/day  recov 5.46  acct +860%

THE SHIPPED RULE SCORES 2.46, NOT 5.46, and the gap is mine to own: decide()
groups on the hour but only ever sees ONE scan cycle, because the scanner hands
it that cycle's signals and keeps no memory. Its effective key is (scan, hour,
direction) — identical to keying on the scan alone, to every decimal, since
nothing merges beyond a cycle. Still a large win over the 1.39 it replaced, and
still not what the hindsight row promised.

THE REACHABLE VERSION IS 3.60 AND IT NEEDS ONE HOUR OF MEMORY. If a pick has
already been named this hour, a later signal in the same hour defers to it
rather than claiming its own; the ranking then only orders signals that arrived
in the same cycle. That is causal, needs no unsend, and recovers 1.14 of the
1.86 lost to hindsight. Note the account column barely moves (+394% against
+396%) while recovery goes 2.46 to 3.60 — fewer, less correlated trades at the
same compounded return, which is exactly the trade portfolio_v2.py described.

BAND-FIRST IS WORSE HERE TOO: per scan it scores 2.16 against 2.46, so the
tf-first ordering survives the move from hindsight to causal.

THE EVENT WINDOW MATTERS MORE THAN THE RANKING, and this was the open question
until it was measured. The deployed tag_event_pick groups by one BAR of one
timeframe, four times finer than an hour on Min15 and blind across timeframes:

    per bar per tf (DEPLOYED today)   36.0/day   recov 1.39   acct +104%
    per slowest bar, across tfs       25.7/day   recov 4.85   acct +580%
    per hour, across tfs              25.7/day   recov 4.85   acct +580%

Widening the window is worth +3.46 recovery. Changing the ordering INSIDE the
wide window is worth +0.61. So the grouping is the change and the tiebreak is
the polish, which is the opposite of where the argument usually goes.

The middle two rows are identical because the slowest scanned bar IS an hour
while INTERVALS ends at Min60; they are printed separately so that if a Hour4
stream is ever added, the two stop agreeing and the difference is visible
rather than assumed.

ONE ROW THAT LOOKS LIKE A BUG AND IS NOT. "per bar per tf, tf-first" scores
exactly what "per bar per tf" scores, to every decimal. Inside a single
(tf, bar, direction) group the timeframe is constant, so a tf-first key
degenerates to the band-first key. That identity is the cleanest demonstration
in the file of why the deployed grouping cannot benefit from a timeframe
tiebreak at all: it never sees two timeframes in the same group.
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import random                                           # noqa: E402
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
HOUR = 3600          # one market event = one hour, one direction, any symbol


def band_of(t):
    """0 take, 1 flat, 2 skip — the deployed three-tier ordering."""
    if LO <= t.risk_pct <= HI:
        return 0
    return 1 if t.risk_pct < LO else 2


def key_band(t):
    return (band_of(t), 0 if t.kind == "confirmed" else 1,
            -BAR_SECONDS[t.tf], t.sym)


def key_band_tf(t):
    return (band_of(t), -BAR_SECONDS[t.tf],
            0 if t.kind == "confirmed" else 1, t.sym)


def key_confd_first(t):
    return (0 if t.kind == "confirmed" else 1, band_of(t),
            -BAR_SECONDS[t.tf], t.sym)


def key_tf_first(t):
    return (-BAR_SECONDS[t.tf], band_of(t),
            0 if t.kind == "confirmed" else 1, t.sym)


def key_poi_first(t):
    return (0 if t.day else 1, band_of(t),
            0 if t.kind == "confirmed" else 1, -BAR_SECONDS[t.tf], t.sym)


def key_bandonly(t):
    return (band_of(t), t.sym)


def by_event(rows):
    """{hour: [signals]} — one market event is one hour and one direction,
    across every symbol and every timeframe that expressed it.

    The hour, not the bar, because the timeframes do not share bar boundaries:
    a 15m signal at 10:15 and the 1h signal at 10:00 containing it are the same
    raid with two timestamps. Direction is part of the key because a long raid
    and a short raid in the same hour are genuinely two events.
    """
    g = defaultdict(list)
    for t in rows:
        g[(t.t - (t.t % HOUR), t.is_long)].append(t)
    return g


def by_bar(rows):
    """The DEPLOYED grouping: one bar of one timeframe, one direction.

    Four times finer than an hour on Min15, and blind across timeframes — a
    raid printing on 15m, 30m and 1h lands in three different groups and gets
    three picks. This is what tag_event_pick does today.
    """
    g = defaultdict(list)
    for t in rows:
        step = BAR_SECONDS[t.tf]
        g[(t.tf, t.t - (t.t % step), t.is_long)].append(t)
    return g


SCAN = 900          # SCAN_INTERVAL: the bot wakes on every Min15 close


def arrival(t):
    """When the SCANNER first sees a signal, not when its bar opened.

    THIS IS THE DIFFERENCE BETWEEN A BACKTEST AND A BOT AND IT IS EASY TO MISS.
    A Min60 setup completing on the 10:00 bar is not knowable until 11:00, and
    the bot notices it on the next scan after that. A Min15 setup on the 10:15
    bar is knowable at 10:30. Both floor into the 10:00 HOUR, so an hour-keyed
    grouping puts them in one event — but they arrive 30 minutes apart, in
    different scan cycles, and the earlier one has already been SENT by the
    time the later one exists.

    So "one pick per hour" as scored above quietly uses hindsight. These rows
    price what a bot can actually do.
    """
    return -(-t // SCAN) * SCAN


def by_arrival(rows):
    """Fully causal: one pick per SCAN CYCLE, across symbols and timeframes.

    No memory, no hindsight, no retroactive edit to a message already sent.
    This is the cheapest correct implementation of the rule.
    """
    g = defaultdict(list)
    for t in rows:
        seen = arrival(t.t + BAR_SECONDS[t.tf])
        g[(seen, t.is_long)].append(t)
    return g


def by_scan_and_hour(rows):
    """EXACTLY WHAT decide.py SHIPPED ON 11 SEP, and it is not what was scored.

    decide() groups on the hour — but it only ever sees ONE scan cycle's
    results, because the scanner hands it the signals found in that cycle and
    keeps no memory. Two signals in the same hour that arrive in different
    scans therefore never meet, and the earlier one's message has already been
    sent by the time the later one exists.

    The effective key is (scan, hour, direction), which merges nothing beyond
    the scan and can still SPLIT inside it when a fresh-but-older signal floors
    into the previous hour. This row prices that honestly instead of letting
    the hindsight row stand in for it.
    """
    g = defaultdict(list)
    for t in rows:
        seen = arrival(t.t + BAR_SECONDS[t.tf])
        g[(seen, t.t - (t.t % 3600), t.is_long)].append(t)
    return g


def pick_first_in_hour(rows, key):
    """Hour-keyed, but the EARLIEST-ARRIVING member claims the pick.

    What a bot with one hour of memory and no ability to unsend could do. The
    key still ranks, but only among signals that arrived in the same scan as
    the claimant; anything later in the hour defers to a pick already sent.
    """
    g = defaultdict(list)
    for t in rows:
        g[(t.t - (t.t % 3600), t.is_long)].append(t)
    out = []
    for members in g.values():
        first = min(arrival(t.t + BAR_SECONDS[t.tf]) for t in members)
        same = [t for t in members
                if arrival(t.t + BAR_SECONDS[t.tf]) == first]
        out.append(min(same, key=key))
    return out


def by_slow_bar(rows):
    """One bar of the SLOWEST scanned timeframe, across timeframes. Same
    coarseness as the hour here, kept separate so the grouping and the window
    length are not conflated if INTERVALS changes."""
    step = max(BAR_SECONDS[tf] for tf in TFS)
    g = defaultdict(list)
    for t in rows:
        g[(t.t - (t.t % step), t.is_long)].append(t)
    return g


def pick(rows, key, take=1, drop_skip=False, group=None):
    """One (or `take`) signals per market event, chosen by `key`."""
    out = []
    for members in (group or by_event)(rows).values():
        ranked = sorted(members, key=key)
        if drop_skip:
            ranked = [t for t in ranked if band_of(t) != 2]
        out.extend(ranked[:take])
    return out


def rand_pick(rows, seed=20260911):
    rnd = random.Random(seed)
    out = []
    for members in by_event(rows).values():
        out.append(members[rnd.randrange(len(members))])
    return out


def score(name, rows, events_total):
    if len(rows) < 40:
        print(f"  {name:<34}{len(rows):>6}   too thin")
        return
    rs = [t.r for t in sorted(rows, key=lambda x: x.exit_t)]
    dd, _ = drawdown(rs)
    wins = sum(1 for r in rs if r > 0)
    bal, ddc, _ = compound(rows, max_open=10)
    # Two halves of the window, so a recovery factor that only exists in one
    # of them is visible rather than averaged away. A rule whose whole
    # advantage sits in one half has not been demonstrated, it has been found.
    order = sorted(rows, key=lambda x: x.exit_t)
    halves = []
    for part in (order[:len(order) // 2], order[len(order) // 2:]):
        h = [t.r for t in part]
        d, _ = drawdown(h)
        halves.append(sum(h) / d if d else 0.0)
    print(f"  {name:<34}{len(rows) / DAYS / NSYM * 120:>7.1f}"
          f"{len(rows):>7}{sum(rs):>9.1f}{dd:>8.1f}"
          f"{sum(rs) / dd if dd else 0:>8.2f}"
          f"{halves[0]:>7.2f}{halves[1]:>7.2f}"
          f"{wins / len(rs):>7.0%}"
          f"{100 * (bal / START - 1):>+9.0f}%{ddc:>6.0%}")


async def main():
    by_tf = {}
    async with aiohttp.ClientSession() as sess:
        syms = await universe(sess)
        zday = await context(sess, syms, DAY)
        z8h = await context(sess, syms, H8)
        for tf in TFS:
            cs = await load_universe(
                sess, syms, tf, DAYS,
                min_bars=int(0.8 * DAYS * 86400 // BAR_SECONDS[tf]))
            r = await collect(sess, cs, zday, z8h, interval=tf)
            by_tf[tf] = [t for t in r if t.filled and t.exit_t is not None]

    # THE DEPLOYED STREAM, not the raw pool. POI_REQUIRED=1 and MIN_GRADE=B
    # means what actually sends is grade A or B, and with poi=True in the grade
    # that is exactly "in a daily zone AND trend agrees". Scoring a rule on
    # signals the bot does not send would answer a different question.
    rows = [t for tf in TFS for t in by_tf[tf] if t.day]
    ev = by_event(rows)
    sizes = [len(v) for v in ev.values()]

    print("WHICH ONE TO TAKE, ACROSS SYMBOLS AND TIMEFRAMES")
    print(f"{len(syms)} symbols, {DAYS} days, 15m+30m+1h, the stream the bot")
    print("actually sends: in a daily POI, 8h trend agreeing, grade A or B.")
    print(f"\n  {len(rows)} filled trades in {len(ev)} market events")
    print("  (one hour, one direction, any symbol, any timeframe)")
    print(f"  event size: median {statistics.median(sizes):.0f}, "
          f"mean {statistics.fmean(sizes):.1f}, "
          f"largest {max(sizes)}, "
          f"{sum(1 for s in sizes if s == 1) / len(sizes):.0%} are singletons")

    print(f"\n  {'rule':<34}{'/day':>7}{'trades':>7}"
          f"{'total':>9}{'maxDD':>8}"
         f"{'recov':>8}{'1st½':>7}{'2nd½':>7}"
          f"{'win':>7}{'acct':>10}{'accDD':>6}")
    score("take everything", rows, len(ev))
    score("one at random", rand_pick(rows), len(ev))
    print()
    score("band only", pick(rows, key_bandonly), len(ev))
    score("band -> confirmed -> tf", pick(rows, key_band), len(ev))
    score("band -> tf -> confirmed", pick(rows, key_band_tf), len(ev))
    score("confirmed -> band -> tf", pick(rows, key_confd_first), len(ev))
    score("tf -> band -> confirmed", pick(rows, key_tf_first), len(ev))
    score("POI -> band -> confirmed -> tf",
          pick(rows, key_poi_first), len(ev))
    print("  -- THE SAME RULE, DIFFERENT EVENT WINDOW " + "-" * 35)
    score("per bar per tf (DEPLOYED today)",
          pick(rows, key_band, group=by_bar), len(ev))
    score("per slowest bar, across tfs",
          pick(rows, key_band, group=by_slow_bar), len(ev))
    score("per hour, across tfs", pick(rows, key_band), len(ev))
    score("per bar per tf, tf-first",
          pick(rows, key_tf_first, group=by_bar), len(ev))
    print("  -- WHAT A BOT CAN ACTUALLY DO (no hindsight) " + "-" * 31)
    score("AS SHIPPED 11 Sep (scan+hour key)",
          pick(rows, key_tf_first, group=by_scan_and_hour), len(ev))
    score("per SCAN cycle, across tfs",
          pick(rows, key_tf_first, group=by_arrival), len(ev))
    score("per scan, band-first",
          pick(rows, key_band, group=by_arrival), len(ev))
    score("per hour, first arrival claims it",
          pick_first_in_hour(rows, key_tf_first), len(ev))
    score("per hour, WITH hindsight (scored above)",
          pick(rows, key_tf_first), len(ev))
    print()
    score("band->confd->tf, skip dropped",
          pick(rows, key_band, drop_skip=True), len(ev))
    score("top 2 per event", pick(rows, key_band, take=2), len(ev))
    score("top 3 per event", pick(rows, key_band, take=3), len(ev))
    print()

    confd = [t for t in rows if t.kind == "confirmed"]
    early = [t for t in rows if t.kind == "early"]
    ce, ee = by_event(confd), by_event(early)

    # DOES THE ORDERING THAT WON ON THE MIXED STREAM ALSO WIN INSIDE EARLY?
    # The mixed result cannot answer that: in a mixed event the confirmed/early
    # axis is doing work, so "tf beats band" there could be tf standing in for
    # something else. Scored inside each stream separately, the confirmed/early
    # axis is constant and only band and tf remain.
    print("  -- EARLY ONLY, every ordering " + "-" * 45)
    score("EARLY take all", early, len(ee))
    score("EARLY one at random", rand_pick(early, 20260912), len(ee))
    score("EARLY band only", pick(early, key_bandonly), len(ee))
    score("EARLY band -> tf", pick(early, key_band_tf), len(ee))
    score("EARLY tf -> band", pick(early, key_tf_first), len(ee))
    score("EARLY band -> tf, no skip",
          pick(early, key_band_tf, drop_skip=True), len(ee))
    print()
    print("  -- CONFIRMED ONLY, every ordering " + "-" * 41)
    score("CONFD take all", confd, len(ce))
    score("CONFD one at random", rand_pick(confd, 20260912), len(ce))
    score("CONFD band only", pick(confd, key_bandonly), len(ce))
    score("CONFD band -> tf", pick(confd, key_band_tf), len(ce))
    score("CONFD tf -> band", pick(confd, key_tf_first), len(ce))
    score("CONFD band -> tf, no skip",
          pick(confd, key_band_tf, drop_skip=True), len(ce))

    print("\n-- EARLY, BY TIMEFRAME AND BAND " + "-" * 44)
    print("  where the early stream is strong, so the mix is taken with eyes")
    print("  open rather than because the pooled number came out fine.")
    print(f"  {'stream':<10}{'tf':<6}{'band':<8}{'trades':>7}{'R/trade':>10}"
          f"{'total':>9}{'win':>7}")
    for label, pool in (("early", early), ("confirmed", confd)):
        for tf in TFS:
            for bi, bname in enumerate(("take", "flat", "skip")):
                g = [t for t in pool if t.tf == tf and band_of(t) == bi]
                if len(g) < 40:
                    continue
                r = [t.r for t in g]
                print(f"  {label:<10}{tf:<6}{bname:<8}{len(g):>7}"
                      f"{statistics.fmean(r):>+10.3f}{sum(r):>9.1f}"
                      f"{sum(1 for x in r if x > 0) / len(r):>7.0%}")
        print()

    print("\n-- WHAT THE PICK ACTUALLY CHOOSES " + "-" * 42)
    chosen = pick(rows, key_band)
    for label, f in (("timeframe", lambda t: t.tf),
                     ("stream", lambda t: t.kind),
                     ("band", lambda t: ("take", "flat", "skip")[band_of(t)])):
        c = defaultdict(int)
        for t in chosen:
            c[f(t)] += 1
        tot = sum(c.values())
        print(f"  {label:<11}" + "  ".join(
            f"{k} {v / tot:.0%}" for k, v in sorted(c.items())))

    print("\n-- HOW OFTEN A RAID SHOWS UP ON 2+ TIMEFRAMES " + "-" * 31)
    multi = one = 0
    for members in by_event(rows).values():
        bysym = defaultdict(set)
        for t in members:
            bysym[t.sym].add(t.tf)
        for tfs in bysym.values():
            if len(tfs) > 1:
                multi += 1
            else:
                one += 1
    print(f"  {multi} of {multi + one} symbol-events print on 2+ timeframes "
          f"({multi / (multi + one):.0%})")


if __name__ == "__main__":
    asyncio.run(main())
