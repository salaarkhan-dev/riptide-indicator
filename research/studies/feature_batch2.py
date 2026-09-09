"""The two things `feature_batch.py` left unfinished.

ONE — ITS NULL WAS TOO LENIENT, AND THAT IS A FLAW IN MY OWN INSTRUMENT.

The random controls there were an independent coin flip per signal. A real
indicator is nothing like that: an EMA state persists for hundreds of bars, so
consecutive signals on one symbol share a feature value almost always. That
autocorrelation inflates the spread of a REAL feature's result without
inflating a coin flip's, so the coin-flip null under-states how large a number
noise can produce and hands every real feature an unearned advantage. The tell
was in the output: only 2% of the random controls cleared 2 SE, where the
textbook two-sided rate is 4.6%. A null that is tighter than theory is not a
strict null, it is a broken one.

THE FIX IS A CIRCULAR SHIFT. Each symbol's real feature values are rotated in
time by a random offset, per symbol, and the rotated feature is scored against
the unrotated R. That preserves the feature's own autocorrelation and its
keep-rate EXACTLY — it is the same values in the same order — while destroying
any relationship with the outcome. It is the strictest null available here and
it needs no assumption about what the feature looks like.

TWO — THE SURVIVORS MAY ALREADY BE DEPLOYED.

Six features cleared the old p95 and every one was an EMA on a higher
timeframe, all pointing the same way. A coherent family rather than one lucky
cell is encouraging — but the grade ALREADY filters on the Hour8 SuperTrend and
Hour8 DI agreeing with the trade. "Price above its Hour8 EMA100, agreeing with
the trade" is close to a restatement of that. So the family is tested again
INSIDE each existing trend bucket: if it only separates where the deployed
filter already separates, it is the deployed filter wearing a different hat.

PRE-REGISTERED

  A feature survives only if it clears the CIRCULAR-SHIFT null's p95, holds its
  sign held out, AND still separates within the group where the Hour8 trend
  already agrees. Three conditions, because the first batch showed the first
  one alone admits six.

    PYTHONPATH=. python3 research/studies/feature_batch2.py
"""
import research.env                                     # noqa: F401  MUST be first

import asyncio                                          # noqa: E402
import random                                           # noqa: E402
from collections import defaultdict                     # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.trend import supertrend                    # noqa: E402
from research.data import load_sync                     # noqa: E402
from research.harness import mean_se                    # noqa: E402
from research.studies.feature_batch import (            # noqa: E402
    HTFS, build_features, htf_at, load_htf, sig_time, split_se)

SHIFTS = 300


def circular_null(rows, fn, seeds=SHIFTS):
    """|SE| when each symbol's feature series is rotated in time.

    Same values, same order, same keep-rate, same autocorrelation — only the
    alignment with R is destroyed. Anything this produces is what the feature's
    own shape can manufacture against an outcome it cannot possibly know.
    """
    by_sym = defaultdict(list)
    for r in sorted(rows, key=sig_time):
        v = fn(r)
        if v is not None:
            by_sym[r.symbol].append((r, v))
    out = []
    for s in range(seeds):
        rnd = random.Random(9100 + s)
        mapped = {}
        for sym, pairs in by_sym.items():
            n = len(pairs)
            if n < 2:
                continue
            k = rnd.randrange(n)
            for i, (r, _) in enumerate(pairs):
                mapped[id(r)] = pairs[(i + k) % n][1]
        got = split_se([r for r in rows if id(r) in mapped],
                       lambda r: mapped.get(id(r)))
        if got:
            out.append(abs(got[2]))
    return sorted(out)


def main():
    from riptide.exchange import list_symbols

    async def go():
        async with aiohttp.ClientSession() as sess:
            syms = await list_symbols(sess)
            await load_htf(sess, syms)
            return syms
    syms = asyncio.run(go())
    rows = [r for r in load_sync(symbols=syms) if r.kind == "early"]
    held = [r for r in rows if r.split_window]
    F = dict(build_features())

    # The six that cleared the old, too-lenient null, plus the two deployed
    # trend readings for comparison.
    NAMES = [n for n in F if "EMA" in n and any(t in n for t in HTFS)]
    NAMES += [n for n in F if "SuperTrend" in n and "Hour8" in n]

    print(f"THE CIRCULAR-SHIFT NULL — the strict one\n{len(rows)} early "
          f"signals · {SHIFTS} rotations per feature\n")
    print(f"  {'feature':<40}{'SE':>7}{'null p95':>10}{'null max':>10}"
          f"{'held out':>11}")
    survivors = []
    for name in NAMES:
        fn = F[name]
        got = split_se(rows, fn)
        if not got:
            continue
        null = circular_null(rows, fn)
        if not null:
            continue
        p95 = null[int(0.95 * (len(null) - 1))]
        h = split_se(held, fn)
        hs = f"{h[2]:+.1f} SE" if h else "too few"
        ok = abs(got[2]) >= p95
        print(f"  {name:<40}{got[2]:>+7.1f}{p95:>10.2f}{null[-1]:>10.2f}"
              f"{hs:>11}{'  <-- clears' if ok else ''}")
        if ok:
            survivors.append(name)

    if not survivors:
        print(f"\n  NOTHING clears the strict null. The six that cleared the "
              f"coin-flip\n  null were beating a broken instrument.")
        return

    # ---- conditional test: is it the deployed Hour8 trend in disguise?
    print(f"\nCONDITIONAL ON THE DEPLOYED FILTER — the grade already requires "
          f"the Hour8\ntrend to agree, so a survivor must still separate "
          f"INSIDE each bucket.")
    st8 = F.get(f"SuperTrend(10,1.8) with  [Hour8]")
    for name in survivors:
        fn = F[name]
        print(f"\n  {name}")
        print(f"    {'':<28}{'n':>6}{'diff':>9}{'SE':>7}")
        for lab, want in (("Hour8 trend AGREES", True),
                          ("Hour8 trend against", False)):
            sub = [r for r in rows if st8(r) is want]
            got = split_se(sub, fn)
            if not got:
                print(f"    {lab:<28}{len(sub):>6}   too few")
                continue
            print(f"    {lab:<28}{got[3]:>6}{got[0]:>+9.3f}{got[2]:>+7.1f}")


if __name__ == "__main__":
    main()
