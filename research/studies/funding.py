"""Does the CROWD'S POSITIONING predict which raids pay? The first non-price test.

EVERY VARIABLE THIS PROJECT HAS EVER TESTED IS A TRANSFORM OF PRICE. Thirty-one
indicators, five regime readings, pool geometry, gap size, session, breadth —
all of them price rearranged. That is a closed loop: the strategy is built from
price and then conditioned on price, so a failure to find anything might mean
there is nothing to find, or merely that price has already been fully used.

FUNDING IS THE FIRST THING AVAILABLE THAT IS NOT PRICE. It is what longs pay
shorts to hold the perpetual, settled every four or eight hours, and MEXC serves
540 days of it per symbol — enough to cover the whole deep window. It measures
which side is crowded and what they are paying to stay there. (It is not
CLEANLY independent of price: funding tracks the perp-spot basis, which follows
price. Closer to positioning than anything else here, not orthogonal to it.)

THE MECHANISM, WRITTEN DOWN BEFORE MEASURING, AND IT IS DIRECTIONAL

  This strategy FADES a liquidity raid. The claim underneath it is that a sweep
  of the lows is a stop-run — forced selling that exhausts itself — rather than
  the start of a move down. Funding says whether there was anything to force.

    LONG  (the lows were raided)   Funding POSITIVE means the crowd is levered
                                   long and paying to stay there. Sweeping the
                                   lows flushes exactly those positions, and
                                   buying it is buying from forced sellers.

    SHORT (the highs were raided)  Funding NEGATIVE means the crowd is levered
                                   short. Sweeping the highs squeezes them, and
                                   selling it is selling to forced buyers.

  So the signed quantity that should matter is funding AGAINST the trade:

      crowd_against = +funding for a long, -funding for a short

  PREDICTION, PRE-REGISTERED: higher `crowd_against` pays better. A raid into a
  crowded opposite book is a liquidation; a raid in a flat book is just a move.
  If the sign comes out the OTHER way the mechanism is wrong, and a
  wrong-signed result is not a discovery to be reinterpreted afterwards.

NORMALISATION, BECAUSE THE RAW NUMBER IS NOT COMPARABLE

  Symbols settle on different cycles — 8h for BTC, 4h for TAO — so raw rates
  are not comparable across symbols, and the level drifts over the year. Every
  variable is therefore the trailing 30-day PERCENTILE OF THAT SYMBOL'S OWN
  funding, which normalises the cycle, the symbol and the era at once. The
  reading used is the last settlement STRICTLY BEFORE the signal.

PRE-REGISTERED — the same three conditions the regime study used, and it
failed all of them, so the bar is not being lowered here:

  1. Top tercile beats bottom by 2 SE over the whole window.
  2. The sign holds in at least 3 of the 4 quarters — a variable that separates
     only BETWEEN quarters is a relabelling of "it was Q3".
  3. It clears the circular-shift null's p95.

  AND FOR THE SIGNED VARIABLE, a fourth: the effect must appear in LONGS and
  SHORTS separately, in the directions the mechanism predicts. A result that
  lives entirely in one side is a directional bet on the year, not a mechanism.

  EXPECTATION: `crowd_against` clears condition 1 and fails condition 2, like
  everything else. Recorded so it cannot be revised.

    PYTHONPATH=. RIPTIDE_MIN_GRADE=B RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/funding.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import bisect                                           # noqa: E402
import random                                           # noqa: E402
import statistics                                       # noqa: E402
from collections import defaultdict                     # noqa: E402
from datetime import datetime, timezone                 # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import log                          # noqa: E402
from riptide.exchange import BASE, get_json, list_symbols  # noqa: E402
from research.deep import load_universe                 # noqa: E402
from research.harness import mean_se                    # noqa: E402
from research.studies.replicate import DAYS, TF, bets, collect  # noqa: E402

PAGE = 1000             # the endpoint's cap
RANK_DAYS = 30
SHIFTS = 300


async def funding_history(sess, symbol, days=DAYS + 40):
    """[(settle_time, rate)] oldest first, covering `days`.

    Paged newest-first and stopped as soon as the window is covered, so a
    symbol on a 4-hour cycle costs one more request than one on 8 hours rather
    than twice as many.
    """
    import time
    floor = time.time() - days * 86400
    out = {}
    for page in range(1, 8):
        d = await get_json(sess, f"{BASE}/api/v1/contract/funding_rate/history",
                           {"symbol": symbol, "page_num": page,
                            "page_size": PAGE})
        r = d and d.get("data")
        rows = r and r.get("resultList")
        if not rows:
            break
        for x in rows:
            out[int(x["settleTime"]) // 1000] = float(x["fundingRate"])
        if min(int(x["settleTime"]) // 1000 for x in rows) <= floor:
            break
        if page >= (r.get("totalPage") or 1):
            break
    return sorted((t, v) for t, v in out.items() if t >= floor)


def rank_series(hist):
    """{settle_time: percentile within the trailing 30 days} for one symbol.

    A RAW RATE IS NOT COMPARABLE and would not be actionable. Cycles differ per
    symbol, the level drifts across the year, and "funding was 0.01%" is partly
    a statement about which month it is. The trailing percentile asks whether
    positioning is crowded FOR THIS SYMBOL RIGHT NOW, which is stationary and is
    what a live filter could actually read.
    """
    times = [t for t, _ in hist]
    vals = [v for _, v in hist]
    out = {}
    for i, t in enumerate(times):
        lo = bisect.bisect_left(times, t - RANK_DAYS * 86400)
        window = vals[lo:i]
        if len(window) < 20:
            continue
        v = vals[i]
        out[t] = (sum(1 for w in window if w < v) / len(window), v)
    return out


def feature_at(ranks, hist_times, when):
    """The last settlement STRICTLY BEFORE `when`. No look-ahead, by design."""
    i = bisect.bisect_left(hist_times, when) - 1
    if i < 0:
        return None
    return ranks.get(hist_times[i])


def split(sigs, feat, lo=1 / 3, hi=2 / 3):
    vals = [feat[s] for s in sigs if s in feat]
    if len(vals) < 60:
        return None
    q = sorted(vals)
    a, b = q[int(lo * len(q))], q[int(hi * len(q))]
    top = bets([s for s in sigs if s in feat and feat[s] >= b])
    bot = bets([s for s in sigs if s in feat and feat[s] <= a])
    if len(top) < 20 or len(bot) < 20:
        return None
    mt, st = mean_se([r for _, r in top])
    mb, sb = mean_se([r for _, r in bot])
    se = (st ** 2 + sb ** 2) ** 0.5
    return dict(nt=len(top), nb=len(bot), mt=mt, mb=mb,
                wt=sum(1 for _, r in top if r > 0) / len(top),
                wb=sum(1 for _, r in bot if r > 0) / len(bot),
                d=mt - mb, se=se, z=(mt - mb) / se if se else 0.0)


def circular_null(sigs, feat, seeds=SHIFTS):
    """|z| when each symbol's funding-rank series is rotated in time.

    Funding is strongly autocorrelated — a crowded book stays crowded for days
    — so an independent shuffle would be far too lenient, exactly as
    feature_batch2 established. Rotation preserves the persistence and the
    bucket sizes and destroys only the link to the outcome.
    """
    bysym = defaultdict(list)
    for s in sigs:
        if s in feat:
            bysym[s.sym].append(s)
    for v in bysym.values():
        v.sort(key=lambda s: s.t)
    out = []
    for k in range(seeds):
        rnd = random.Random(3300 + k)
        rot = {}
        for group in bysym.values():
            if len(group) < 2:
                continue
            j = rnd.randrange(len(group))
            for i, s in enumerate(group):
                rot[s] = feat[group[(i + j) % len(group)]]
        got = split([s for s in sigs if s in rot], rot)
        if got:
            out.append(abs(got["z"]))
    return sorted(out)


def line(label, got, note=""):
    if not got:
        print(f"  {label:<32}   too few")
        return
    print(f"  {label:<32}{got['nt']:>6}{got['wt']:>6.0%}{got['mt']:>+9.3f}"
          f"   |{got['nb']:>6}{got['wb']:>6.0%}{got['mb']:>+9.3f}"
          f"   |{got['d']:>+8.3f}{got['z']:>+6.1f} SE  {note}")


def header(title):
    print(f"\n{title}")
    print(f"  {'':<32}{'  TOP THIRD':<21}   |{'  BOTTOM THIRD':<21}   |"
          f"  DIFFERENCE")
    print(f"  {'':<32}{'bets':>6}{'win':>6}{'R/bet':>9}   |{'bets':>6}"
          f"{'win':>6}{'R/bet':>9}   |")


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = await list_symbols(sess)
        candles = await load_universe(sess, syms, TF, DAYS)
        sigs = await collect(sess, candles)
        fund = {}
        for sym in candles:
            try:
                h = await funding_history(sess, sym)
            except Exception as e:
                log.warning("%s: funding history failed: %s", sym, e)
                continue
            if len(h) > 60:
                fund[sym] = (rank_series(h), [t for t, _ in h])

    conf = [s for s in sigs if s.kind == "confirmed"]

    # Build the three variables per signal, from the last settlement BEFORE it.
    crowd, extreme, raw = {}, {}, {}
    for s in conf:
        got = fund.get(s.sym)
        if not got:
            continue
        hit = feature_at(got[0], got[1], s.t)
        if hit is None:
            continue
        pct, rate = hit
        # The signed variable: funding AGAINST the trade, so a long wants the
        # crowd long (positive) and a short wants the crowd short (negative).
        # Expressed as a percentile it must be flipped for shorts.
        crowd[s] = pct if s.is_long else 1.0 - pct
        extreme[s] = abs(pct - 0.5) * 2          # crowded either way
        raw[s] = pct                             # unsigned, the control

    print(f"FUNDING RATE — the first NON-PRICE variable tested in this project\n"
          f"{len(fund)} symbols with funding history · {len(conf)} Min30 "
          f"confirmed signals · {len(crowd)} matched\ntrailing 30-day "
          f"percentile of each symbol's OWN funding, last settlement before "
          f"the signal")

    VARS = (("crowd positioned AGAINST us", crowd,
             "the mechanism: higher should pay"),
            ("funding extreme, either way", extreme, ""),
            ("raw funding percentile", raw, "unsigned control"))

    header("WHOLE WINDOW")
    results = {}
    for name, feat, note in VARS:
        got = split(conf, feat)
        results[name] = (got, feat)
        line(name, got, note)

    print(f"\n{'=' * 104}\nWITHIN EACH QUARTER — the test that killed every "
          f"regime variable\n{'=' * 104}")
    byq = defaultdict(list)
    for s in conf:
        dt = datetime.fromtimestamp(s.t, timezone.utc)
        byq[f"{dt.year}Q{(dt.month - 1) // 3 + 1}"].append(s)
    for name, (got, feat) in results.items():
        if not got:
            continue
        header(name)
        signs = []
        for q in sorted(byq):
            g = split(byq[q], feat)
            line(q, g)
            if g:
                signs.append(g["d"] > 0)
        if signs:
            agree = max(sum(signs), len(signs) - sum(signs))
            print(f"    sign holds in {agree} of {len(signs)} quarters"
                  f"{'  <-- passes condition 2' if agree >= 3 else ''}")

    # ---- condition 4: does the mechanism work on BOTH sides? --------------
    got, feat = results["crowd positioned AGAINST us"]
    if got:
        print(f"\n{'=' * 104}\nLONGS AND SHORTS SEPARATELY — the mechanism "
              f"claims BOTH, not one\n{'=' * 104}")
        header("crowd positioned against us")
        line("LONG signals only", split([s for s in conf if s.is_long], feat))
        line("SHORT signals only",
             split([s for s in conf if not s.is_long], feat))
        print(f"    An effect living entirely on one side is a directional bet "
              f"on the year,\n    not the liquidation mechanism the "
              f"pre-registration describes.")

    print(f"\n{'=' * 104}\nTHE CIRCULAR-SHIFT NULL\n{'=' * 104}")
    print(f"  {'variable':<32}{'real |SE|':>11}{'null p95':>10}{'null max':>10}")
    for name, (got, feat) in results.items():
        if not got:
            continue
        null = circular_null(conf, feat)
        if not null:
            continue
        p95 = null[int(0.95 * (len(null) - 1))]
        print(f"  {name:<32}{abs(got['z']):>11.2f}{p95:>10.2f}{null[-1]:>10.2f}"
              f"{'   clears' if abs(got['z']) >= p95 else ''}")

    print(f"\nPRE-REGISTERED: 2 SE on the window · sign in 3 of 4 quarters · "
          f"clears the null ·\nand for the signed variable, present on BOTH "
          f"sides in the predicted direction.")


if __name__ == "__main__":
    asyncio.run(main())
