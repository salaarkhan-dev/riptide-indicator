"""THE TABLE THAT GOES ON THE REFERENCE CARD: what each kind of alert scored.

WHAT THIS IS FOR, AND THE TRAP IN IT.

The card asks a reader to take the 🎯 and ignore the rest. That is a big ask on
trust, and the honest way to earn it is to show what each kind of alert has
actually done. So: by stream (confirmed / early) and by timeframe (15m / 30m /
1h), the numbers a person uses to decide whether to believe a signal — how
often it wins, what a win pays against what a loss costs, what it made per
trade, and how deep a hole it dug getting there.

THE TRAP IS THAT A TABLE OF POINT ESTIMATES CREATES CONFIDENCE IT HAS NOT
EARNED. research/studies/timeframes.py measured 15m, 30m, 1h and 4h against
each other and found NO PAIR separating at even one standard error. If this
table prints "1h +0.21, 15m +0.09" with nothing beside it, a reader will stop
taking 15m picks — on a difference the data cannot support, throwing away most
of the stream (64% of picks are 15m) for noise.

So every row carries its STANDARD ERROR, and the file ends by stating in words
which differences are real and which are not. A cell without an interval beside
it is not a measurement, it is a rumour with a decimal point.

WHAT IS MEASURED, AND ON WHICH POPULATION. Two populations, because they answer
different questions and mixing them is how a table lies:

  SENT      every alert the bot delivers, under the deployed policy —
            POI_REQUIRED=1 and MIN_GRADE=B, so in a daily zone with the 8h
            trend agreeing. This says what a signal of that kind is worth.

  PICKED    only the alerts carrying 🎯, under the shipped rule: one per
            direction per rolling 120 minutes, ranked tf → band → confirmed.
            This is what the reader actually experiences, and it is the column
            that belongs on the card.

The gap between them is the pick rule's whole contribution and is printed
rather than described.

DEFINITIONS, because "RR" means three different things in three places:

  win %       fraction of filled trades that ended positive
  avg win     mean R of the winners.   At a 2R target with fees this lands
              under 2.00, and how far under is the fee drag made visible.
  avg loss    mean R of the losers, as a positive number. Above 1.00 means
              stops are slipping past the level — gaps, not modelling error.
  RR          avg win / avg loss. The payoff ratio a reader means by "RR".
  R/trade     expectancy. win% x avg win - (1-win%) x avg loss, and it is the
              only column that decides anything.
  +/-         standard error of R/trade. Roughly: a difference smaller than
              the two errors added together is not a difference.
  maxDD       deepest peak-to-trough run in R, in EXIT order.
  recovery    total R / maxDD. The project's primary metric everywhere else,
              because any rule that simply trades less shrinks both terms.

NOT PRE-REGISTERED, AND THAT IS DELIBERATE. This is a descriptive scorecard of
populations already fixed by earlier pre-registered work — it proposes no rule
and changes no setting. Nothing here is a discovery, and if a cell here looks
like one, it needs its own study before it reaches anything.

    PYTHONPATH=. python3 research/studies/scorecard.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import math                                             # noqa: E402
from collections import defaultdict                     # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import BAR_SECONDS                  # noqa: E402
from research.deep import load_universe                 # noqa: E402
from research.studies.poi_tf import DAY, DAYS, H8       # noqa: E402
from research.studies.poi_tf import collect, context, universe  # noqa: E402
from research.studies.report import drawdown            # noqa: E402
from research.studies.pick_rule import (TFS, arrival,   # noqa: E402
                                        band_of, key_tf_first)

LABEL = {"Min15": "15m", "Min30": "30m", "Min60": "1h"}
COOLDOWN = 7200          # the shipped window, riptide/config.py


def picked(rows, cooldown=COOLDOWN):
    """The shipped pick rule, causal, in arrival order. Copied from
    pick_rule.pick_rolling rather than imported so that a later change to the
    study's variants cannot silently redefine what 'PICKED' means here."""
    byscan = defaultdict(list)
    for t in rows:
        byscan[(arrival(t.t + BAR_SECONDS[t.tf]), t.is_long)].append(t)
    last, out = {}, []
    for seen, up in sorted(byscan):
        if seen - last.get(up, -(1 << 40)) < cooldown:
            continue
        out.append(min(byscan[(seen, up)], key=key_tf_first))
        last[up] = seen
    return out


def stats(rows):
    """Everything the table prints, or None when there is not enough to say.

    THE FLOOR IS 40 TRADES and it is not arbitrary: per-bet sd is 1.31 on every
    timeframe here, so 40 trades gives a standard error of 0.21 R — wider than
    the entire measured spread between the best and worst cell. Under that, a
    row would be printing noise in a format that looks like knowledge.
    """
    if len(rows) < 40:
        return None
    rs = [t.r for t in sorted(rows, key=lambda x: x.exit_t)]
    wins = [r for r in rs if r > 0]
    losses = [-r for r in rs if r <= 0]
    dd, _ = drawdown(rs)
    mean = sum(rs) / len(rs)
    sd = math.sqrt(sum((r - mean) ** 2 for r in rs) / (len(rs) - 1))
    aw = sum(wins) / len(wins) if wins else 0.0
    al = sum(losses) / len(losses) if losses else 0.0
    return dict(n=len(rs), win=len(wins) / len(rs), avg_win=aw, avg_loss=al,
                rr=aw / al if al else 0.0, r=mean, se=sd / math.sqrt(len(rs)),
                total=sum(rs), dd=dd, recov=sum(rs) / dd if dd else 0.0)


HEAD = (f"  {'':<22}{'n':>6}{'win':>7}{'avg win':>9}{'avg loss':>10}"
        f"{'RR':>7}{'R/trade':>10}{'+/-':>8}{'total R':>9}{'maxDD':>8}"
        f"{'recov':>7}")


def line(label, rows):
    s = stats(rows)
    if s is None:
        print(f"  {label:<22}{len(rows):>6}   too thin to report")
        return
    print(f"  {label:<22}{s['n']:>6}{s['win']:>7.0%}{s['avg_win']:>9.2f}"
          f"{s['avg_loss']:>10.2f}{s['rr']:>7.2f}{s['r']:>+10.3f}"
          f"{s['se']:>8.3f}{s['total']:>+9.1f}{s['dd']:>8.1f}"
          f"{s['recov']:>7.2f}")


def separable(a, b, rows_a, rows_b):
    """Do two cells differ by more than their errors combined?

    The crude test on purpose: the difference against the square root of the
    summed squared errors, which is the standard error OF the difference. A |z|
    under 2 is reported as "not separable" with no hedging, because the point
    of this whole file is to stop a reader believing a gap that is not there.
    """
    sa, sb = stats(rows_a), stats(rows_b)
    if not sa or not sb:
        return None
    diff = sb["r"] - sa["r"]
    se = math.sqrt(sa["se"] ** 2 + sb["se"] ** 2)
    return diff, se, abs(diff) / se if se else 0.0


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

    sent = [t for tf in TFS for t in by_tf[tf] if t.day]
    pick = picked(sent)

    print("WHAT EACH KIND OF ALERT HAS ACTUALLY SCORED")
    print(f"{len(syms)} symbols · {DAYS} days · 15m+30m+1h · target 2R, fees in")
    print("The stream the bot sends: in a daily POI, 8h trend agreeing, "
          "grade A or B.")

    for title, pop in (("EVERY ALERT SENT", sent),
                       ("ONLY THE 🎯 PICKS  (one per direction per 120m)",
                        pick)):
        print(f"\n{'=' * 96}\n{title}\n{'=' * 96}")
        print(HEAD)
        line("ALL", pop)
        print()
        for kind in ("confirmed", "early"):
            for tf in TFS:
                line(f"{kind:<10}{LABEL[tf]}",
                     [t for t in pop if t.kind == kind and t.tf == tf])
            line(f"{kind} — all tfs", [t for t in pop if t.kind == kind])
            print()
        for tf in TFS:
            line(f"{LABEL[tf]} — both streams", [t for t in pop if t.tf == tf])

    print(f"\n{'=' * 96}\nWHICH DIFFERENCES ARE REAL\n{'=' * 96}")
    print("  A gap smaller than the standard error OF THE DIFFERENCE is not a")
    print("  gap. |z| under 2 means the two cells cannot be told apart, and a")
    print("  reader who favours one over the other is acting on noise.\n")
    print(f"  {'comparison':<34}{'diff':>9}{'se':>8}{'|z|':>7}   verdict")
    pairs = [("15m vs 30m", "Min15", "Min30"), ("30m vs 1h", "Min30", "Min60"),
             ("15m vs 1h", "Min15", "Min60")]
    for pop_name, pop in (("sent", sent), ("picked", pick)):
        for label, a, b in pairs:
            got = separable(a, b, [t for t in pop if t.tf == a],
                            [t for t in pop if t.tf == b])
            if not got:
                continue
            d, se, z = got
            print(f"  {pop_name + ' · ' + label:<34}{d:>+9.3f}{se:>8.3f}"
                  f"{z:>7.1f}   "
                  f"{'SEPARABLE' if z >= 2 else 'not separable'}")
        got = separable("c", "e", [t for t in pop if t.kind == "confirmed"],
                        [t for t in pop if t.kind == "early"])
        if got:
            d, se, z = got
            print(f"  {pop_name + ' · confirmed vs early':<34}{d:>+9.3f}"
                  f"{se:>8.3f}{z:>7.1f}   "
                  f"{'SEPARABLE' if z >= 2 else 'not separable'}")
        print()

    print(f"{'=' * 96}\nAND BY STOP WIDTH, since that is the one axis the card")
    print(f"asks a reader to size against\n{'=' * 96}")
    print(HEAD)
    for pop_name, pop in (("sent", sent), ("picked", pick)):
        for i, w in enumerate(("tight", "normal", "wide")):
            line(f"{pop_name:<7}{w}", [t for t in pop if band_of(t) == i])
        print()


if __name__ == "__main__":
    asyncio.run(main())
