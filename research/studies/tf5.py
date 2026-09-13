"""DOES THE MODEL WORK ON 5 MINUTES? The timeframe ladder, extended down.

`timeframes.py` measured Min15 / Min30 / Min60 / Hour4. Min5 was never on the
ladder, and the one time this project went below Min15 it went all the way to
1m — where MEXC serves about 31 days of history, which was not enough to read
anything, and where the median hold turned out to be 58 minutes, which killed
the premise that it was a scalp at all.

Min5 is the rung that was skipped. It serves **278 days** on this exchange,
against 31 for 1m, so for the first time the question is answerable.

THE MECHANISM THAT DECIDES IT IS ARITHMETIC, NOT MARKET STRUCTURE, AND IT IS
WORTH STATING BEFORE THE RUN. R is measured in units of risk, and the trading
fee is charged as a percentage of notional, so:

    fee in R  =  fee_pct / risk_pct

The fee RATE does not change with the timeframe. `risk_pct` does — the stop
sits at the raid extreme, and a raid on a 5-minute chart is a fraction of the
distance a raid on a 30-minute chart covers. Every step down the ladder shrinks
the denominator and inflates the fee in R terms. That is the whole reason a
model can be perfectly good on structure and still lose money faster the
shorter the timeframe.

SO THE DECISIVE PANEL IS GROSS AGAINST NET, NOT NET ALONE. If Min5 is negative
gross, the structure does not work down there and fees are irrelevant. If Min5
is positive gross and negative net, the structure works and the cost eats it —
a completely different finding with a completely different remedy.

AND THE ZERO-FEE COLUMN IS NOT HYPOTHETICAL HERE. `exchange_surface.py`
measured MEXC's live schedule across the scanned universe: **maker is 0% on 118
of 120 symbols and taker is 0% on 82 of 120**. The entry is a resting limit and
the target is a resting limit, so a winning trade on most of this universe pays
nothing at all. The honest reading of any fee-sensitive result is therefore a
RANGE between the measured rate and zero, and on this account zero is closer to
the truth than the list rate is.

EVERY TIMEFRAME IS RUN ON THE SAME SYMBOLS AND THE SAME WINDOW, through the
same `poi_tf.collect`. A ladder assembled from studies that each chose their own
universe is not a ladder.

──────────────────────────────────────────────────────────────────────────────
PRE-REGISTERED, BEFORE THE FIRST NUMBER

  PRIMARY. Net R per signal on Min5, against the same figure on Min15 / Min30 /
  Min60 measured on identical symbols and dates, at 2 SE.

  THE MECHANISM PANEL, and it decides how to read the primary. Gross R, fee in
  R, net R and median risk_pct per timeframe. The prediction below is specific
  and falsifiable.

  VOLUME, because it is an operational answer and not only a statistical one.
  Signals per day scaled to 120 symbols. A timeframe that is mildly profitable
  and fires 400 times a day is not deployable on a Telegram bot a person reads.

  BOTH HALVES of the window for anything that looks positive.

  WHAT WOULD FALSIFY "MIN5 IS TRADEABLE". Net R per signal negative, or
  indistinguishable from zero, at the measured fee AND at zero fee. Zero fee is
  the generous case; failing there is unambiguous.

  EXPECTATION, recorded so it cannot be revised. I expect median risk_pct to
  fall roughly with the square root of the bar length, so Min5 should sit near
  0.5% against Min30's ~1.3% — which would make the fee in R about 2.5x worse
  than Min30's. I expect Min5 GROSS to be positive and smaller than Min30's,
  and Min5 NET to be at or below zero at the measured fee. At zero fee I expect
  it to be positive but thin, and for volume rather than edge to be what rules
  it out. If Min5 is negative GROSS, my model of why short timeframes fail here
  is wrong and the finding is about structure, not cost.

    PYTHONPATH=. RIPTIDE_MIN_GRADE=B RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/tf5.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import statistics                                       # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import BAR_SECONDS                  # noqa: E402
from riptide.exchange import list_symbols               # noqa: E402
from research.deep import load_universe                 # noqa: E402
from research.harness import mean_se                    # noqa: E402
from research.studies.poi_tf import DAY, H8             # noqa: E402
from research.studies.poi_tf import collect, context    # noqa: E402

# Min5 serves 278 days on MEXC, so the window is set by the SHORTEST series on
# the ladder rather than by the 333 the other studies use. Every timeframe gets
# the same 270 days; a ladder measured over different spans is not a ladder.
DAYS = 270
TFS = ("Min5", "Min15", "Min30", "Min60")
# Fewer symbols than the 103 the Min30 studies use, because Min5 is 80k bars
# per symbol and the engine pass is the expensive part. 40 symbols on Min5
# still yields several times the signal count of a full Min30 run.
NSYM = 40


def line(tf, rows, nsym):
    f = [t for t in rows if t.filled and t.exit_t is not None]
    if len(f) < 40:
        print(f"  {tf:<8}{len(rows):>8}   too few filled to read")
        return None
    net = [t.r for t in f]
    gross = [t.gross for t in f]
    mn, sn = mean_se(net)
    mg, _ = mean_se(gross)
    risk = statistics.median(t.risk_pct for t in f)
    perday = len(rows) / DAYS / nsym * 120
    wins = sum(1 for r in net if r > 0)
    print(f"  {tf:<8}{len(rows):>8}{len(f) / len(rows):>7.0%}{perday:>9.1f}"
          f"{risk:>8.2f}%{mg:>+9.3f}{mg - mn:>+9.3f}{mn:>+9.3f}±{sn:.3f}"
          f"{wins / len(f):>7.0%}{sum(net):>+9.1f}")
    return dict(tf=tf, n=len(rows), net=net, gross=gross, m=mn, se=sn,
                mg=mg, risk=risk, perday=perday)


def halves(tf, rows):
    f = sorted([t for t in rows if t.filled and t.exit_t is not None],
               key=lambda t: t.t)
    if len(f) < 80:
        print(f"    {tf:<8} too few")
        return
    mid = len(f) // 2
    for lab, sub in (("half 1", f[:mid]), ("half 2", f[mid:])):
        mn, sn = mean_se([t.r for t in sub])
        mg, _ = mean_se([t.gross for t in sub])
        print(f"    {tf:<8}{lab:<9}{len(sub):>7}   gross {mg:>+7.3f}"
              f"   net {mn:>+7.3f} ±{sn:.3f}")


async def main():
    by_tf = {}
    async with aiohttp.ClientSession() as sess:
        want = (await list_symbols(sess))[:NSYM]
        # One symbol set for every rung: whatever has enough bars on ALL of
        # them. Taking each timeframe's own survivors would let Min5 be scored
        # on a different, quieter universe.
        sets = []
        cache = {}
        for tf in TFS:
            need = int(0.8 * DAYS * 86400 // BAR_SECONDS[tf])
            cache[tf] = await load_universe(sess, want, tf, DAYS,
                                            min_bars=need)
            sets.append(set(cache[tf]))
        common = sorted(set.intersection(*sets))
        print(f"universe: {len(common)} symbols with {DAYS} days on all of "
              f"{'/'.join(TFS)}")
        zday = await context(sess, common, DAY)
        z8h = await context(sess, common, H8)
        for tf in TFS:
            cs = {s: cache[tf][s] for s in common}
            by_tf[tf] = await collect(sess, cs, zday, z8h, interval=tf)

    n = len(common)
    print("\nDOES THE MODEL WORK ON 5 MINUTES")
    print(f"{n} symbols, {DAYS} days, A/B signals, target 2R, same engine and "
          f"same gates on every rung.")
    print("'/day' is scaled to 120 symbols — the deployed universe.")
    print("'fee' is gross minus net: fee_pct / risk_pct, which is why it grows "
          "as the stop shrinks.\n")
    print(f"  {'tf':<8}{'signals':>8}{'fill':>7}{'/day':>9}{'risk':>9}"
          f"{'GROSS':>9}{'fee':>9}{'NET':>16}{'win':>7}{'total':>9}")
    stats = {}
    for tf in TFS:
        got = line(tf, by_tf[tf], n)
        if got:
            stats[tf] = got

    print(f"\n{'=' * 104}\nMIN5 AGAINST EACH OTHER RUNG — unpaired, different "
          f"signals\n{'=' * 104}")
    if "Min5" in stats:
        a = stats["Min5"]
        for tf in TFS[1:]:
            if tf not in stats:
                continue
            b = stats[tf]
            se = (a["se"] ** 2 + b["se"] ** 2) ** 0.5
            d = a["m"] - b["m"]
            print(f"  Min5 vs {tf:<8}net {a['m']:>+7.3f} vs {b['m']:>+7.3f}"
                  f"   diff {d:>+7.3f}   |z| {abs(d) / se if se else 0:>4.1f}"
                  + ("   SEPARATES" if se and abs(d) / se >= 2 else ""))

    print(f"\n{'=' * 104}\nTHE FEE IS THE WHOLE QUESTION — gross against net"
          f"\n{'=' * 104}")
    print("  maker is 0% on 118 of 120 MEXC symbols and taker 0% on 82, so the")
    print("  GROSS column is not a fantasy — it is what most of this universe")
    print("  actually pays on a winning trade. read the pair as a range.\n")
    print(f"  {'tf':<8}{'risk%':>8}{'fee in R':>10}{'gross':>9}{'net':>9}"
          f"{'net/gross':>11}")
    for tf in TFS:
        if tf not in stats:
            continue
        s = stats[tf]
        fee = s["mg"] - s["m"]
        ratio = s["m"] / s["mg"] if s["mg"] else 0.0
        print(f"  {tf:<8}{s['risk']:>7.2f}%{fee:>10.3f}{s['mg']:>+9.3f}"
              f"{s['m']:>+9.3f}{ratio:>10.0%}")

    print(f"\n{'=' * 104}\nBOTH HALVES\n{'=' * 104}")
    for tf in TFS:
        halves(tf, by_tf[tf])

    print(f"\n{'=' * 104}\nOPERATIONAL\n{'=' * 104}")
    for tf in TFS:
        if tf not in stats:
            continue
        s = stats[tf]
        print(f"  {s['tf']:<8}{s['perday']:>8.1f} alerts/day at 120 symbols"
              f"   total {sum(s['net']):>+8.1f} R over {DAYS} days")
    print("\n  a timeframe that is mildly profitable and fires hundreds of")
    print("  times a day is not deployable on a bot a person reads.")


if __name__ == "__main__":
    asyncio.run(main())
