"""Is the one surviving cell a real edge, or is it five coins?

THE QUESTION THIS ANSWERS. `report.py` showed the alert stream as a whole is
+0.034 ± 0.027 R per bet — indistinguishable from zero — and that the best five
symbols out of sixty supply 107% of net R, so removing them turns the year
negative. Thirteen hypotheses have been measured on this project and exactly
one survived: CONFIRMED setups whose stop sits 1.2%-2.6% from the entry, at
+0.226 ± 0.087 R per bet, which cleared its circular-shift null and held its
sign in three quarters of four.

Both of those things cannot be comfortable at once. If the survivor is ALSO
five coins, then it is the same concentration artefact wearing a filter, the
null it cleared was answering the wrong question, and the honest conclusion is
that this strategy has no edge worth trading. That is a conclusion I would
rather reach on purpose than avoid.

WHY A SYMBOL BOOTSTRAP AND NOT "DROP THE TOP FIVE". Deleting the best names
always hurts and proves nothing — do it to a genuinely broad edge and it still
looks worse. The question is not "what happens without the winners" but "how
much of this number depends on WHICH coins happened to be in the universe".
The instrument for that is resampling SYMBOLS with replacement: draw sixty
symbols from the sixty, keep every bet belonging to a drawn symbol, recompute.
A result carried by five names collapses the moment a draw misses them; a
result spread over forty survives almost every draw. The interval that comes
back is a symbol-clustered confidence interval, and it is strictly wider and
more honest than the per-bet standard error quoted everywhere else in this
project, which assumes symbols are interchangeable.

THE SECOND CHECK IS THE FAT TAIL. A 2R target means one trade can be a
thirtieth of a cell's total R. Trimming the best five TRADES is reported for
the same reason: not as a verdict, but so the reader can see how much of the
number rests on a handful of fills.

AND THE MULTIPLE-COMPARISONS DEBT IS REAL. The 1.2-2.6 band was not handed
down; it was chosen by looking at data. `risk_band.py` pre-registered the TEST
but not the BAND, so some of the 2.6 SE is selection. Nothing below removes
that debt. It is stated so the number is read at its true strength.

    PYTHONPATH=. RIPTIDE_MIN_GRADE=B RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/survivor.py

RESULT, 10 Sep 2026 — THE CELL SEPARATES FROM EVERYTHING AROUND IT

                                  R/bet     bootstrap 5th    draws <= 0
    everything tradeable         +0.033        -0.014           14.2%
    confirmed, any stop          +0.058        -0.028           15.4%
    confirmed, stop 1.2-2.6%     +0.202        +0.072            0.5%
    confirmed, stop outside      -0.113        -0.210           97.5%

  The two halves fail in OPPOSITE directions, which is the part that is hard
  to explain as noise: the excluded arm is negative in 97.5% of universe draws
  while the kept arm is positive in 99.5% of them. A concentration artefact
  does not usually arrange itself into a matched pair.

  It is also the only cell in this project whose quarters agree: +0.209,
  +0.260, +0.132, +0.207. The confirmed stream it comes from swings -0.069 to
  +0.261 over the same four. And it is tradeable in a way the full stream is
  not — 0.94 fills a day, 14.0 R max drawdown against +55.6 R net, recovery
  factor 3.97, under water 74 trades of 312 against the stream's 2706 of 4322.
  On 300 USDT at 1% risk: +66% at a 13.4% drawdown, and the concurrency cap
  barely moves it because there is nothing to cap.

WHAT IS STILL WRONG WITH IT, AND THE FIRST ONE IS A FLAW IN MY OWN INSTRUMENT

  THE BOOTSTRAP IS WEAKER THAN IT LOOKS. Five of 57 symbols still supply 79%
  of the cell's R. A resample of 57 from 57 misses any given symbol with
  probability (1-1/57)^57 = 36.5%, so it misses all five at once only 0.65% of
  the time — and 0.5% of draws came back non-positive. The "0.5%" is therefore
  close to a restatement of "it is rare to miss all five", not independent
  evidence that the edge is broad. What the bootstrap DOES establish is the
  contrast with the other three rows, which were run on the same instrument and
  failed it. Read it as a relative verdict, not an absolute one.

  Deleting those five outright still leaves +11.5 R, which is the one thing
  none of the other cells manage — every one of them goes negative. Weak, but
  the right sign.

  THE BAND WAS CHOSEN BY LOOKING AT DATA. `risk_band.py` pre-registered the
  test, not the 1.2 and the 2.6. Some of this is selection and no amount of
  re-slicing the same 333 days removes it.

  SURVIVORSHIP IS UNTOUCHED. Levels are optimistic; the contrast between the
  two arms, measured on the same rows, is what to believe.

  ONE YEAR, 312 TRADES. Only forward time fixes that.
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import random                                           # noqa: E402
import statistics                                       # noqa: E402
from collections import defaultdict                     # noqa: E402
from datetime import datetime, timezone                 # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.exchange import list_symbols               # noqa: E402
from research.deep import load_universe                 # noqa: E402
from research.harness import mean_se                    # noqa: E402
from research.studies.report import (DAYS, INTERVAL, START, bets_of, collect,
                                     compound, drawdown)  # noqa: E402

LO, HI = 1.2, 2.6
DRAWS = 4000


def cell(trades):
    return [t for t in trades
            if t.kind == "confirmed" and t.filled and t.exit_t is not None
            and LO <= t.risk_pct <= HI]


def symbol_bootstrap(trades, draws=DRAWS):
    """Resample SYMBOLS with replacement; recompute R per bet each time.

    Bets are formed inside the draw, not before it, so a symbol drawn twice
    contributes twice to the bars it fired on — which is the point: the
    uncertainty being measured is over the universe, not over the bars.
    """
    bysym = defaultdict(list)
    for t in trades:
        bysym[t.sym].append(t)
    syms = sorted(bysym)
    rnd = random.Random(20260910)
    out = []
    for _ in range(draws):
        pick = [syms[rnd.randrange(len(syms))] for _ in syms]
        g = defaultdict(list)
        for s in pick:
            for t in bysym[s]:
                g[t.t].append(t.r)
        if len(g) < 20:
            continue
        out.append(statistics.fmean(statistics.fmean(v) for v in g.values()))
    return sorted(out)


def describe(name, trades):
    if len(trades) < 20:
        print(f"\n{name}: {len(trades)} trades — too few.")
        return
    rs = [t.r for t in trades]
    b = bets_of(trades)
    m, se = mean_se(b)
    boot = symbol_bootstrap(trades)
    p5 = boot[int(0.05 * (len(boot) - 1))]
    p95 = boot[int(0.95 * (len(boot) - 1))]
    neg = sum(1 for x in boot if x <= 0) / len(boot)

    bysym = defaultdict(float)
    for t in trades:
        bysym[t.sym] += t.r
    rank = sorted(bysym.items(), key=lambda kv: -kv[1])
    pos = sum(1 for v in bysym.values() if v > 0)
    top5 = sum(v for _, v in rank[:5])
    tot = sum(rs)

    print(f"\n{name}")
    print(f"  {len(trades)} trades · {len(b)} bets · "
          f"{sum(1 for r in rs if r > 0) / len(rs):.0%} win · "
          f"{tot:+.1f} R total · {m:+.3f} ± {se:.3f} R/bet "
          f"({abs(m / se) if se else 0:.1f} SE, bets only)")
    print(f"  SYMBOL BOOTSTRAP   5th {p5:+.3f}   median "
          f"{boot[len(boot) // 2]:+.3f}   95th {p95:+.3f} R/bet")
    print(f"                     {neg:.1%} of universe draws come back "
          f"{'<= 0' if neg else 'positive'}"
          f"   ->  {'SURVIVES resampling' if p5 > 0 else 'DOES NOT survive resampling'}")
    print(f"  concentration      {pos} of {len(bysym)} symbols positive "
          f"({pos / len(bysym):.0%});  best 5 supply {top5 / tot:.0%} of net R; "
          f"without them {tot - top5:+.1f} R")
    trimmed = sorted(rs)[:-5]
    print(f"  fat tail           drop the 5 best TRADES -> "
          f"{statistics.fmean(trimmed):+.3f} R/trade "
          f"(from {statistics.fmean(rs):+.3f}), {sum(trimmed):+.1f} R total")
    dd, dl = drawdown([t.r for t in sorted(trades, key=lambda t: t.exit_t)])
    print(f"  drawdown           {dd:.1f} R max against {tot:+.1f} R net "
          f"(recovery {tot / dd if dd else 0:.2f}), under water "
          f"{dl} of {len(rs)} trades")
    byq = defaultdict(list)
    for t in trades:
        d = datetime.fromtimestamp(t.t, timezone.utc)
        byq[f"{d.year}Q{(d.month - 1) // 3 + 1}"].append(t)
    cells = []
    for q in sorted(byq):
        bq = bets_of(byq[q])
        cells.append(f"{q} {statistics.fmean(bq):+.3f}" if len(bq) >= 10
                     else f"{q}  thin ")
    print("  by quarter         " + "   ".join(cells))


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = await list_symbols(sess)
        candles = await load_universe(sess, syms, INTERVAL, DAYS)
        trades = await collect(sess, candles)

    conf = [t for t in trades if t.kind == "confirmed" and t.filled
            and t.exit_t is not None]
    keep = cell(trades)

    print("THE ONE SURVIVOR, RESAMPLED OVER THE UNIVERSE")
    print(f"{DAYS} days · {len(candles)} symbols · {DRAWS} symbol draws\n"
          "the per-bet SE assumes symbols are interchangeable. the bootstrap "
          "does not.\nwhere they disagree, believe the bootstrap.")

    describe("EVERYTHING the bot alerts as tradeable",
             [t for t in trades if t.filled and t.exit_t is not None])
    describe("CONFIRMED setups, all stop distances", conf)
    describe(f"CONFIRMED, stop {LO}%-{HI}%   <- the survivor", keep)
    describe(f"CONFIRMED, stop outside {LO}%-{HI}%   <- what it excludes",
             [t for t in conf if not (LO <= t.risk_pct <= HI)])

    print("\n\nCOULD YOU ACTUALLY TRADE THE SURVIVOR?")
    print(f"  {len(keep)} fills over {DAYS} days = "
          f"{len(keep) / DAYS:.2f} a day. concurrency is the binding constraint")
    print("  on the full stream; at this rate it is not.")
    src = [t for t in trades if t.kind == "confirmed"
           and LO <= t.risk_pct <= HI]
    for cap in (None, 5, 3, 2):
        bal, dd, sk = compound(src, cap)
        lab = "unlimited" if cap is None else f"max {cap} open"
        print(f"  {lab:<14} 300 USDT at 1% risk -> {bal:>8,.0f} USDT "
              f"({bal / START - 1:>+6.0%})   max drawdown {dd:>5.1%}"
              f"   {sk} skipped")


if __name__ == "__main__":
    asyncio.run(main())
