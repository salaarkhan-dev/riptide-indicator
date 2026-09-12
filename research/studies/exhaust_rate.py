"""HOW MANY MESSAGES A DAY WOULD THE EXHAUSTION WATCH SEND?

THE QUESTION, AND WHY IT IS A SEPARATE FILE. research/studies/exhaustion.py
asked whether a completed count predicts anything and answered no — worse than
no, the opposite direction scored three times better. That settled whether the
counts are a TRADE. It said nothing about whether they are a readable HEADS-UP,
and those fail differently: a heads-up fails by arriving too often to read.

So this counts completions. It is descriptive, not a hypothesis test, and there
is nothing here to pre-register — but the number it produces is what set every
default in riptide/exhaust.py, so it needs to be reproducible rather than
remembered. riptide/commands.py::EXHAUST_RATE is this table, and
tests/test_exhaust.py asserts the two still agree.

WHAT COUNTS AS ONE MESSAGE. Nothing here: the watch sends ONE DIGEST per bar
close carrying every symbol that completed. So the per-day numbers below are
ROWS, not messages, and the true message count is at most 96 a day at 15m, 48
at 30m and 24 at 1h. Rows are still the right unit, because a digest with
forty rows in it is the thing that does not get read.

    PYTHONPATH=. RIPTIDE_DEEP_CACHE=/tmp/deep \
        python3 research/studies/exhaust_rate.py

RIPTIDE_DEEP_CACHE IS A DIRECTORY, NOT A FLAG. Setting it to 1 does not enable
anything — it writes 48MB of candles into a folder called "1" next to the repo.
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                           # noqa: E402

import aiohttp                                           # noqa: E402

from riptide.config import BAR_SECONDS                   # noqa: E402
from research.deep import load_universe                  # noqa: E402
from research.td import counts                           # noqa: E402
from research.studies.poi_tf import DAYS, universe       # noqa: E402
from research.studies.pick_rule import TFS               # noqa: E402


def tally(cs_by_symbol) -> tuple:
    """(M9, M9 perfected, T13) completions per day across the universe.

    A completion is a bar where the count REACHES its terminal value, which is
    what the watch fires on — not a bar where the count is merely active.
    """
    nine = perf = thirteen = 0
    span = 0.0
    for sym, cs in cs_by_symbol.items():
        if len(cs) < 60:
            continue
        k = counts(cs)
        # Each symbol contributes its own covered span, so a pair listed late
        # is not counted as if it had been there the whole window.
        span = max(span, (cs[-1].t - cs[0].t) / 86400.0)
        for i in range(len(cs)):
            if k.buy_setup[i] == 9 or k.sell_setup[i] == 9:
                nine += 1
                if k.buy_perfect[i] or k.sell_perfect[i]:
                    perf += 1
            if k.buy_cd[i] == 13 or k.sell_cd[i] == 13:
                thirteen += 1
    days = span or DAYS
    return nine / days, perf / days, thirteen / days


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = await universe(sess)
        rows = {}
        for tf in TFS:
            cs = await load_universe(
                sess, syms, tf, DAYS,
                min_bars=int(0.8 * DAYS * 86400 // BAR_SECONDS[tf]))
            rows[tf] = (tally(cs), len(cs))

    print("EXHAUSTION WATCH — COMPLETED COUNTS PER DAY ACROSS THE UNIVERSE")
    print(f"{len(syms)} symbols requested · {DAYS} days · "
          f"{'+'.join(TFS)}\n")
    print("Rows in a digest, not messages: the watch sends one digest per bar")
    print("close carrying every symbol that completed on it.\n")
    print(f"{'tf':<8}{'symbols':>9}{'M9/day':>10}{'M9*/day':>10}{'T13/day':>10}"
          f"{'both':>9}{'both*':>9}")
    tot = [0.0] * 3
    for tf in TFS:
        (n9, np9, n13), nsym = rows[tf]
        tot = [tot[0] + n9, tot[1] + np9, tot[2] + n13]
        print(f"{tf:<8}{nsym:>9}{n9:>10.0f}{np9:>10.0f}{n13:>10.0f}"
              f"{n9 + n13:>9.0f}{np9 + n13:>9.0f}")
    print(f"{'ALL':<8}{'':>9}{tot[0]:>10.0f}{tot[1]:>10.0f}{tot[2]:>10.0f}"
          f"{tot[0] + tot[2]:>9.0f}{tot[1] + tot[2]:>9.0f}")

    print("\nWHAT THE COLUMNS MEAN FOR THE SETTINGS")
    print("  'both'   = RIPTIDE_EXHAUST_KINDS=both with PERFECT_ONLY=0")
    print("  'both*'  = RIPTIDE_EXHAUST_KINDS=both with PERFECT_ONLY=1")
    print("  M9*      = KINDS=momentum, PERFECT_ONLY=1")
    print("  T13      = KINDS=terminal  (the perfected gate does not apply)")

    ship = rows["Min60"][0]
    print(f"\nTHE SHIPPED DEFAULT is 1h + both + perfected only: "
          f"{ship[1] + ship[2]:.0f} a day.")
    print(f"EVERYTHING ON is {tot[0] + tot[2]:.0f} a day, against roughly 85")
    print("alerts and 18 picks from the bot itself. That ratio is the whole")
    print("reason the default is the quiet corner of this table.")


if __name__ == "__main__":
    asyncio.run(main())
