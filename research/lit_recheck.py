"""Two errors in my own LIT measurements, corrected and quantified separately.

Both were found by checking the LIT research against the repository's existing
conventions rather than against itself. They push in OPPOSITE directions, so
each has to be isolated before either is read.

ERROR 1 — THE FEE MODEL WAS THE REFERENCE'S, NOT THE REPOSITORY'S.

  Every LIT measurement used COMMISSION = 0.0005 per side, 0.10% round trip,
  taken from the reference document's own Ch.24 default. research/harness.py
  defines the repo's assumption:

      FEE_MAKER = 0.010%   FEE_TAKER = 0.022%
      "Fees are charged once per filled trade, in R: FEE_PCT / risk_pct."

  so the conservative round trip is maker+taker = 0.032%, not 0.10%. Every LIT
  result was charged roughly 3x the repo's fee. This made everything look
  WORSE than it is.

  harness.py is also explicit that the fee is not a constant: "it moves with
  VIP tier and the MX deduction, and the exchange runs ZERO-FEE promotions on
  many pairs at once - so the true cost is a distribution... and every
  conclusion that turns on the fee should be read as a range rather than a
  point." Both columns are therefore reported, not just the corrected one.

ERROR 2 — EVERY TRADE WAS COUNTED AS AN INDEPENDENT OBSERVATION.

  The repo's convention (research/studies/fvg_continuation.py and six others)
  is the BET, not the trade:

      def bets(rows):
          bybar = defaultdict(list)
          for r in rows: bybar[r.t].append(r.r)
          return [statistics.fmean(v) for v in bybar.values()]

  Thirty crypto perpetuals firing long in the same hour are one bet on one
  move, not thirty. Treating them as thirty understates the standard error,
  which made my negative results look MORE significant than they are. The
  t = -4.5 on the older window was inflated by exactly this.

So: correction 1 lifts the point estimate, correction 2 widens the interval.
The question is whether the conclusion survives both.

    PYTHONPATH=. RIPTIDE_DEEP_CACHE=/tmp/deep python3 research/lit_recheck.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import statistics                                       # noqa: E402
from collections import defaultdict                     # noqa: E402

import aiohttp                                          # noqa: E402

from research.deep import load_deep                     # noqa: E402
import research.lit_v3 as L                             # noqa: E402
import research.lit_exit as X                           # noqa: E402
import research.lit_repl as RP                          # noqa: E402

RULES = (("bos", 0.0, "exit at BOS"),
         ("struct", 0.0, "structure trail"),
         ("mfe", 1.5, "mfe - 1.5R"))


def bets(rows):
    """The repo's unit of evidence. rows are (timestamp, R)."""
    bybar = defaultdict(list)
    for t, r in rows:
        bybar[t].append(r)
    return [statistics.fmean(v) for v in bybar.values()]


def line(label, rows, asBets):
    vals = bets(rows) if asBets else [r for _t, r in rows]
    if len(vals) < 20:
        print(f"    {label:<24}{len(vals):>6}   too few to read")
        return
    m = statistics.fmean(vals)
    se = statistics.stdev(vals) / (len(vals) ** 0.5)
    t = m / se if se else 0.0
    print(f"    {label:<24}{len(vals):>6}{m:>9.3f}{se:>8.3f}{t:>8.1f}"
          f"{'   >2se' if abs(t) > 2 else ''}")


async def gather(sess, fee):
    """The same 2x2 as lit_repl, rebuilt at a given fee."""
    import time
    cut = time.time() - RP.RECENT_DAYS * 86400
    held = (await RP.heldout(sess, skip=len(RP.DISCOVERY), want=70))[:30]
    book = {}
    for tf in RP.TFS:
        for nm, syms in (("discovery", RP.DISCOVERY), ("held-out", held)):
            older, recent = [], []
            for sym in syms:
                try:
                    cs = await load_deep(sess, sym, tf, days=RP.DAYS)
                except Exception:
                    continue
                if len(cs) < 2000:
                    continue
                m, _i, _d, _g = L.engine(cs)
                su, bb = X.collect(cs, m.events, fee)
                for s in su:
                    if s.bar < RP.WARMUP:
                        continue
                    tgt = recent if cs[s.bar].t >= cut else older
                    tgt.append((cs, bb, s))
            book[(tf, nm)] = (older, recent)
    return book


def pooled(book, wi, rule, k):
    out = []
    for tf in RP.TFS:
        for nm in ("discovery", "held-out"):
            for cs, bb, s in book[(tf, nm)][wi]:
                out.append((cs[s.bar].t, X.simulate(cs, bb, s, rule, k)[0]))
    return out


async def main():
    async with aiohttp.ClientSession() as sess:
        books = {}
        for lab, fee in (("source 0.10%", X.COMMISSION_SRC),
                         ("repo 0.032%", X.COMMISSION_REPO)):
            books[lab] = await gather(sess, fee)
            n = sum(len(o) + len(r) for o, r in books[lab].values())
            print(f"  built at fee {lab}: {n} setups")

    print("\n" + "=" * 80)
    print("  RECHECK — both corrections, isolated")
    print("  Correction 1 (fee) moves the ESTIMATE. Correction 2 (bets) moves")
    print("  the INTERVAL. Read them one at a time, then together.")
    print("=" * 80)

    for rule, k, rn in RULES:
        print(f"\n  {rn}")
        print(f"    {'cell':<24}{'n':>6}{'NET R':>9}{'se':>8}{'t':>8}")
        for wi, wlab in ((1, "recent 120d"), (0, "older window")):
            for flab in ("source 0.10%", "repo 0.032%"):
                rows = pooled(books[flab], wi, rule, k)
                for asBets, ulab in ((False, "trades"), (True, "BETS")):
                    line(f"{wlab} {flab.split()[0]} {ulab}", rows, asBets)

    print("\n" + "=" * 80)
    print("  READ")
    print("=" * 80)
    print("  The row that supersedes every earlier LIT number is")
    print("  'older window repo BETS' — the repo's fee and the repo's unit of")
    print("  evidence. It is the only row that violates neither convention.")


if __name__ == "__main__":
    asyncio.run(main())
