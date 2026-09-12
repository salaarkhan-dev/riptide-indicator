"""IF FEES ARE NEGLIGIBLE, WHAT IS LEFT HOLDING UP THE TIMEFRAME KEY?

WHY THIS IS BEING ASKED. The pick ranking is tf -> band -> confirmed, and
riptide/decide.py is explicit that the FIRST key rests on cost and nothing
else:

    "no pair of timeframes separates at even 1 SE (timeframes.py), so '1h beats
    30m' is not a claim this repo can make. What it has instead is arithmetic.
    Fee in R is fee_pct / risk_pct; the median stop doubles from 15m to 1h; so
    the fee takes 67% of the gross edge on 15m and 16% on 1h. Preferring the
    slower chart is a COST argument, not an edge argument, and cost arguments
    do not need a significance test."

band_key.py has since shown the SECOND key is not doing measurable work — a
coin toss in its seat spans 3.93 to 8.24 recovery and the shipped rule's 6.52
sits inside that. So the timeframe key is now the only part of the ranking with
a stated reason, and that reason is entirely a fee claim.

The account holder says fees on MEXC are negligible. The rates in harness.py
were already corrected on 10 Sep from a real settlement — 0.010% maker, 0.022%
taker, against the 0.02/0.06 list rates every earlier study used — so the
question is not whether the fee is small in absolute terms. It plainly is. The
question is whether what remains of it still justifies ordering the picks.

THE TRAP IN BOTH DIRECTIONS. "Negligible" is about the fee as a fraction of
PRICE. The ranking claim is about the fee as a fraction of RISK, and those
differ by a factor of 1/risk_pct — 80x on a 0.4% stop. A fee can be genuinely
negligible per trade and still be most of a thin edge. Equally, the 67% figure
may simply be left over from the old rates and never recomputed, in which case
the docstring is quoting a number that was withdrawn.

Neither guess is worth anything, so both are measured.

PRE-REGISTERED, BEFORE THE FIRST NUMBER

  A. THE ARITHMETIC, on the deployed stream: fee drag in R per timeframe, at
     the corrected rates, as a fraction of the GROSS edge. poi_tf already
     stores every trade twice — `r` with fees and `gross` without — so this is
     a subtraction, not a model.

  B. THE OPERATIONAL TEST, which is the one that decides: re-run the same
     ranking arms band_key.py used, scored on GROSS R. If fees were the only
     thing making tf-first work, tf-first collapses toward the alternatives
     when they are switched off. If it holds up at zero fee, the docstring's
     stated reason is wrong but the key is doing something else.

  C. A SENSITIVITY RUN at three fee levels — zero, the measured pair, and
     MEXC's list rates — because the schedule is a RANGE that moves with VIP
     tier and promotions, so any conclusion turning on the fee is a range and
     not a point. harness.py says this in its own comment; this acts on it.

  DECISION RULE, fixed now. If tf-first still leads at ZERO fee, leave the key
  alone and rewrite the docstring's justification, because the stated reason
  would be false even though the key is fine. If tf-first collapses at zero fee
  AND the fee drag difference is under a tenth of the measured +0.071 R/trade,
  then the ranking rests on nothing measurable at either key and that is the
  finding — reported, not acted on, because band_key.py already established
  that no tiebreak beats any other and there is nothing better to put there.

  EXPECTATION, on record. I expect the 67% figure to be stale and the true
  drag at the corrected rates to be roughly a third of it. I expect tf-first to
  survive at zero fee, because band_key.py's coin-toss spread was wide enough
  that all these arms are probably indistinguishable anyway — in which case the
  honest answer to "do fees justify the timeframe key" is that NOTHING
  justifies any key, and the value is entirely in taking one signal per window.

    PYTHONPATH=. python3 research/studies/fee_key.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import statistics                                       # noqa: E402
from collections import defaultdict                     # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import BAR_SECONDS                  # noqa: E402
from research.deep import load_universe                 # noqa: E402
from research.harness import FEE_MAKER, FEE_TAKER       # noqa: E402
from research.studies.poi_tf import DAY, DAYS, H8       # noqa: E402
from research.studies.poi_tf import collect, context, universe  # noqa: E402
from research.studies.report import drawdown            # noqa: E402
from research.studies.band_key import (COOLDOWN, KEYS,  # noqa: E402
                                       pick_rolling, rand_key, pct)
from research.studies.pick_rule import TFS, band_of     # noqa: E402

SEEDS = 40
LABEL = {"Min15": "15m", "Min30": "30m", "Min60": "1h"}


def score(rows, attr="r"):
    """Recovery on `r` (fees in) or `gross` (fees out), in exit order."""
    if len(rows) < 40:
        return None
    order = sorted(rows, key=lambda x: x.exit_t)
    rs = [getattr(t, attr) for t in order]
    dd, _ = drawdown(rs)
    halves = []
    for part in (order[:len(order) // 2], order[len(order) // 2:]):
        h = [getattr(t, attr) for t in part]
        d, _ = drawdown(h)
        halves.append(sum(h) / d if d else 0.0)
    return dict(n=len(rs), total=sum(rs), dd=dd,
                recov=sum(rs) / dd if dd else 0.0,
                mean=sum(rs) / len(rs), h1=halves[0], h2=halves[1])


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
    print("WHAT IS LEFT HOLDING UP THE TIMEFRAME KEY?")
    print(f"{len(syms)} symbols · {DAYS} days · {len(rows)} filled trades")
    print(f"rates in force: maker {FEE_MAKER}% · taker {FEE_TAKER}% "
          f"(measured from a settlement, not quoted)")

    # ------------------------------------------------------------------- A
    print(f"\n{'=' * 92}")
    print("A — THE ARITHMETIC: what the fee actually costs, per timeframe")
    print("=" * 92)
    print(f"  {'tf':<8}{'n':>7}{'med stop':>10}{'gross R':>10}{'net R':>9}"
          f"{'fee R':>9}{'fee as % of gross':>20}")
    for tf in TFS:
        pop = [t for t in rows if t.tf == tf]
        if not pop:
            continue
        g = sum(t.gross for t in pop) / len(pop)
        n = sum(t.r for t in pop) / len(pop)
        med = statistics.median(t.risk_pct for t in pop)
        share = 100 * (g - n) / g if g > 0 else float("nan")
        print(f"  {LABEL[tf]:<8}{len(pop):>7}{med:>9.2f}%{g:>+10.4f}{n:>+9.4f}"
              f"{g - n:>9.4f}{share:>19.0f}%")
    print("\n  'fee as % of gross' is the number decide.py quotes as 67% on 15m")
    print("  and 16% on 1h. Those were computed at the OLD 0.02/0.06 rates.")

    # ------------------------------------------------------------------- B
    print(f"\n{'=' * 92}")
    print("B — THE OPERATIONAL TEST: the same ranking arms, scored WITHOUT fees")
    print("=" * 92)
    for attr, title in (("r", "fees IN (the shipped world)"),
                        ("gross", "fees OFF entirely")):
        print(f"\n  -- {title} " + "-" * (66 - len(title)))
        print(f"  {'key':<34}{'n':>7}{'R':>9}{'maxDD':>8}{'recov':>8}"
              f"{'1st':>7}{'2nd':>7}")
        for name, key in KEYS.items():
            s = score(pick_rolling(rows, key, COOLDOWN), attr)
            if s:
                print(f"  {name:<34}{s['n']:>7}{s['total']:>9.1f}"
                      f"{s['dd']:>8.1f}{s['recov']:>8.2f}{s['h1']:>7.2f}"
                      f"{s['h2']:>7.2f}")
        nulls = [score(pick_rolling(rows, rand_key(sd), COOLDOWN), attr)
                 for sd in range(SEEDS)]
        recs = sorted(x["recov"] for x in nulls if x)
        print(f"  {'E  coin toss: 5th / median / 90th':<34}{'':>7}{'':>9}"
              f"{'':>8}{pct(recs, 0.05):>8.2f}{pct(recs, 0.50):>7.2f}"
              f"{pct(recs, 0.90):>7.2f}")
        a = score(pick_rolling(rows, KEYS["A  tf > band > confd  (shipped)"],
                               COOLDOWN), attr)
        if a:
            beat = sum(1 for x in recs if x < a["recov"]) / len(recs)
            print(f"  -> shipped beats {beat:.0%} of coin tosses")

    # ------------------------------------------------------------------- C
    print(f"\n{'=' * 92}")
    print("C — SENSITIVITY: the fee is a RANGE, so the answer is one too")
    print("=" * 92)
    print("  The gross/net pair above brackets it. Interpolating linearly in")
    print("  the fee rate, since fee in R is exactly fee_pct / risk_pct:")
    print(f"\n  {'rates':<34}{'fee R/trade':>13}{'as % of the':>14}"
          f"{'':>3}")
    print(f"  {'':<34}{'':>13}{'+0.071 edge':>14}")
    base = [t for t in rows]
    g = sum(t.gross for t in base) / len(base)
    n = sum(t.r for t in base) / len(base)
    unit = (g - n) / (FEE_MAKER + FEE_TAKER)    # fee R per 1% of round trip
    for label, rate in (("zero (promo pairs)", 0.0),
                        (f"measured ({FEE_MAKER}+{FEE_TAKER})",
                         FEE_MAKER + FEE_TAKER),
                        ("MEXC list (0.02+0.06)", 0.08),
                        ("list, no MX discount (0.04+0.10)", 0.14)):
        drag = unit * rate
        print(f"  {label:<34}{drag:>13.4f}{100 * drag / 0.071:>13.0f}%")

    # Composition, so a change in what gets picked is visible rather than
    # inferred from a single ratio.
    print(f"\n  what the shipped key picks, fees in vs fees off:")
    print(f"  {'':<18}{'15m':>8}{'30m':>8}{'1h':>8}{'early':>8}{'normal':>8}")
    p = pick_rolling(rows, KEYS["A  tf > band > confd  (shipped)"], COOLDOWN)
    tot = len(p)
    print(f"  {'shipped picks':<18}"
          + "".join(f"{sum(1 for t in p if t.tf == tf) / tot:>8.0%}"
                    for tf in TFS)
          + f"{sum(1 for t in p if t.kind == 'early') / tot:>8.0%}"
          + f"{sum(1 for t in p if band_of(t) == 1) / tot:>8.0%}")
    bysym = defaultdict(int)
    for t in p:
        bysym[t.tf] += 1
    print("\n  (the picks are the same either way — the fee changes what each")
    print("   trade SCORES, never which one the ranking names.)")


if __name__ == "__main__":
    asyncio.run(main())
