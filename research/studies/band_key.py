"""IS THE RISK BAND EARNING ITS PLACE AS THE SECOND KEY OF THE PICK RULE?

WHY THIS IS BEING ASKED NOW. research/studies/scorecard.py scored the stream
the bot actually sends — daily POI, 8h trend agreeing, grade A or B — and the
band did not order it:

    sent    tight +0.013   normal -0.018   wide +0.036
    picked  tight +0.071   normal +0.060   wide +0.106

The deployed ranking is tf -> BAND -> confirmed -> symbol, so if the band does
not sort this population then the rule's second key is breaking ties on noise,
and every tie it breaks is a real decision about which alert gets the 🎯.

WHY THAT IS NOT YET A CONCLUSION. The band's evidence was never gathered on
this population. survivor.py measured it on ALL 595 confirmed Min30 signals
with a symbol bootstrap; the rows above are the ~340 of those that also sit in
a daily zone with the trend agreeing. Two filters that overlap can absorb each
other, and a descriptive table on a subset is exactly the weakest instrument
this project owns. One table does not overturn a bootstrap.

So this asks the question two ways, and only one of them decides anything.

──────────────────────────────────────────────────────────────────────────────
PRE-REGISTERED, BEFORE THE FIRST NUMBER

PRIMARY — THE OPERATIONAL TEST, and the only one with the power to change the
code. Hold everything else fixed and swap ONLY the ranking key, then score the
picked stream causally at the shipped 120m cooldown:

    A  tf -> band -> confirmed -> sym     the shipped rule
    B  tf -> confirmed -> sym             band removed entirely
    C  tf -> confirmed -> band -> sym     band demoted below confirmed
    D  band -> tf -> confirmed -> sym     band promoted to first
    E  tf -> RANDOM                       the null: a coin toss in the band's
                                          seat, over many seeds

E IS THE TEST THAT MATTERS AND IT IS WHY THIS FILE EXISTS. Comparing A to B
only says whether the band beats a different arbitrary tiebreak (alphabetical).
Comparing A to the DISTRIBUTION of E says whether the band beats no information
at all. If A lands inside E's spread, the band key is decoration however good
A's absolute number looks.

SECONDARY — the descriptive question, with the strict instrument. Band against
outside on the deployed stream, per stream and per timeframe, under
survivor.py's SYMBOL bootstrap rather than a per-bet standard error. The per-bet
SE assumes symbols are interchangeable; the bootstrap does not, and where they
disagree this project believes the bootstrap.

BOTH ARE REPORTED ACROSS BOTH HALVES OF THE WINDOW. An advantage sitting in one
half is a non-result here exactly as everywhere else.

DECISION RULE, fixed now so it cannot be chosen after seeing the table:

    KEEP the band where it is    if A beats the 90th percentile of E, in both
                                 halves.
    DEMOTE it below confirmed    if C >= A and A is inside E's spread.
    REMOVE it from the key       if B >= A and A is inside E's spread, AND the
                                 symbol bootstrap fails to order the bands on
                                 this population.

    Anything ambiguous CHANGES NOTHING. The shipped rule has 6.52 recovery
    measured; replacing a key on a tie would be trading evidence for novelty.

EXPECTATION, on record so it can be wrong. I expect A to beat B and C by a
little and to sit at or just above the middle of E — i.e. the band is worth
something but much less than its place in the docstring implies. I expect the
symbol bootstrap to straddle zero on the deployed stream, because that is what
the point estimates already suggest and the bootstrap is the wider instrument.

WHAT WOULD CHANGE MY MIND ABOUT THE WHOLE FRAMING: if E's spread turns out to
be very wide, then no tiebreak is distinguishable from any other, and the
correct reading is that the SECOND KEY DOES NOT MATTER AT ALL — the value is in
the timeframe key and in taking one. That is a different conclusion from "the
band is wrong" and it would be reported as such.

    PYTHONPATH=. python3 research/studies/band_key.py
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
from research.studies.survivor import LO, HI, symbol_bootstrap  # noqa: E402
from research.studies.pick_rule import NSYM, TFS, arrival, band_of  # noqa: E402

COOLDOWN = 7200          # the shipped window
SEEDS = 40               # draws of the random-tiebreak null


def confd(t):
    return 0 if t.kind == "confirmed" else 1


def slow(t):
    return -BAR_SECONDS[t.tf]


# The five keys. Each is a plain function of one trade so the ranking is the
# ONLY thing that differs between arms — same population, same cooldown, same
# arrival clock, same everything else.
KEYS = {
    "A  tf > band > confd  (shipped)":
        lambda t: (slow(t), band_of(t), confd(t), t.sym),
    "B  tf > confd         (no band)":
        lambda t: (slow(t), confd(t), t.sym),
    "C  tf > confd > band":
        lambda t: (slow(t), confd(t), band_of(t), t.sym),
    "D  band > tf > confd":
        lambda t: (band_of(t), slow(t), confd(t), t.sym),
}


def rand_key(seed):
    """tf first, then a COIN TOSS in the band's seat.

    The toss is deterministic per (seed, trade) rather than drawn at compare
    time, because `min` over an unstable key is not a ranking — it would make
    the arm's result depend on iteration order and quietly stop being a
    comparison of rules.
    """
    def key(t):
        rnd = random.Random(f"{seed}|{t.sym}|{t.t}|{t.tf}|{t.kind}")
        return (slow(t), rnd.random(), t.sym)
    return key


def pick_rolling(rows, key, cooldown=COOLDOWN):
    """The shipped rule: causal, arrival order, separate window per direction.
    Identical to decide.decide's behaviour and to pick_rule.pick_rolling."""
    byscan = defaultdict(list)
    for t in rows:
        byscan[(arrival(t.t + BAR_SECONDS[t.tf]), t.is_long)].append(t)
    last, out = {}, []
    for seen, up in sorted(byscan):
        if seen - last.get(up, -(1 << 40)) < cooldown:
            continue
        out.append(min(byscan[(seen, up)], key=key))
        last[up] = seen
    return out


def recovery(rows):
    if len(rows) < 40:
        return None
    order = sorted(rows, key=lambda x: x.exit_t)
    rs = [t.r for t in order]
    dd, _ = drawdown(rs)
    halves = []
    for part in (order[:len(order) // 2], order[len(order) // 2:]):
        h = [t.r for t in part]
        d, _ = drawdown(h)
        halves.append(sum(h) / d if d else 0.0)
    bal, ddc, _ = compound(rows, max_open=10)
    return dict(n=len(rs), total=sum(rs), dd=dd,
                recov=sum(rs) / dd if dd else 0.0,
                h1=halves[0], h2=halves[1],
                acct=100 * (bal / START - 1))


def show(name, s):
    if s is None:
        print(f"  {name:<34}   too thin")
        return
    print(f"  {name:<34}{s['n']:>7}{s['total']:>9.1f}{s['dd']:>8.1f}"
          f"{s['recov']:>8.2f}{s['h1']:>7.2f}{s['h2']:>7.2f}"
          f"{s['acct']:>+9.0f}%")


def pct(sorted_vals, p):
    return sorted_vals[int(p * (len(sorted_vals) - 1))]


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

    rows = [t for tf in TFS for t in by_tf[tf] if t.day]
    print("IS THE BAND EARNING ITS PLACE AS THE SECOND KEY?")
    print(f"{len(syms)} symbols · {DAYS} days · 15m+30m+1h · {len(rows)} "
          f"filled trades")
    print("The stream the bot sends: daily POI, 8h trend agreeing, grade A/B.")

    # ---------------------------------------------------------------- PRIMARY
    print(f"\n{'=' * 88}")
    print("PRIMARY — swap ONLY the ranking key, 120m cooldown, causal")
    print("=" * 88)
    print(f"  {'key':<34}{'n':>7}{'R':>9}{'maxDD':>8}{'recov':>8}"
          f"{'1st':>7}{'2nd':>7}{'acct':>10}")
    arms = {}
    for name, key in KEYS.items():
        s = recovery(pick_rolling(rows, key))
        arms[name] = s
        show(name, s)

    print(f"\n  -- E: a COIN TOSS in the band's seat, {SEEDS} draws " + "-" * 26)
    nulls = []
    for seed in range(SEEDS):
        s = recovery(pick_rolling(rows, rand_key(seed)))
        if s:
            nulls.append(s)
    recs = sorted(x["recov"] for x in nulls)
    h1s = sorted(x["h1"] for x in nulls)
    h2s = sorted(x["h2"] for x in nulls)
    print(f"  {'random tiebreak':<34}{'':>7}{'':>9}{'':>8}"
          f"{'recov':>8}{'1st':>7}{'2nd':>7}")
    for label, p in (("5th pct", 0.05), ("median", 0.50), ("90th pct", 0.90),
                     ("95th pct", 0.95)):
        print(f"  {'  ' + label:<34}{'':>7}{'':>9}{'':>8}"
              f"{pct(recs, p):>8.2f}{pct(h1s, p):>7.2f}{pct(h2s, p):>7.2f}")

    a = arms["A  tf > band > confd  (shipped)"]
    if a:
        beat = sum(1 for x in recs if x < a["recov"]) / len(recs)
        print(f"\n  the shipped rule beats {beat:.0%} of coin tosses "
              f"({a['recov']:.2f} against a median of {pct(recs, 0.5):.2f})")
        print(f"  1st half: {a['h1']:.2f} vs median {pct(h1s, 0.5):.2f}   "
              f"2nd half: {a['h2']:.2f} vs median {pct(h2s, 0.5):.2f}")

    # -------------------------------------------------------------- SECONDARY
    print(f"\n{'=' * 88}")
    print("SECONDARY — does the band order this population at all?")
    print("symbol bootstrap, 4000 draws, resampling the universe not the bars")
    print("=" * 88)
    print(f"  {'cell':<30}{'n':>7}{'R/bet':>9}{'boot 5th':>11}"
          f"{'boot 95th':>11}{'P(<=0)':>9}")

    def band_line(label, trades):
        if len(trades) < 40:
            print(f"  {label:<30}{len(trades):>7}   too thin")
            return
        boot = symbol_bootstrap(trades)
        if not boot:
            print(f"  {label:<30}{len(trades):>7}   bootstrap empty")
            return
        bets = defaultdict(list)
        for t in trades:
            bets[t.t].append(t.r)
        m = statistics.fmean(statistics.fmean(v) for v in bets.values())
        neg = sum(1 for x in boot if x <= 0) / len(boot)
        print(f"  {label:<30}{len(trades):>7}{m:>+9.3f}{pct(boot, 0.05):>+11.3f}"
              f"{pct(boot, 0.95):>+11.3f}{neg:>9.0%}")

    for scope, pop in (("ALL", rows),
                       ("confirmed", [t for t in rows if t.kind == "confirmed"]),
                       ("early", [t for t in rows if t.kind == "early"])):
        print(f"\n  {scope}")
        for i, w in enumerate(("tight", "normal", "wide")):
            band_line(f"    {w}", [t for t in pop if band_of(t) == i])
        band_line("    normal vs the rest",
                  [t for t in pop if band_of(t) == 1])

    print("\n  per timeframe, normal band only")
    for tf in TFS:
        band_line(f"    {tf} normal",
                  [t for t in rows if t.tf == tf and band_of(t) == 1])

    print(f"\n  band boundaries in use: {LO}% and {HI}%")


if __name__ == "__main__":
    asyncio.run(main())
