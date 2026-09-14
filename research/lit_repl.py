"""Does the Min30 cell replicate? Different window, different symbols.

THE CLAIM UNDER TEST. Min30 has come up as the best cell twice: Variant 3
(+0.071, n=88) and T6 (+0.245 on se 0.240 at the BOS exit, n=91). Neither was
claimed, because both readings came from the SAME 30 symbols over the SAME 120
days - one observation seen twice, not two confirmations.

The rank split is the cautionary precedent in this project: it looked positive
at n=102 on two agreeing arms with a source story behind it, and every rank
went negative at n=1214. So the test is a 2x2, and the cell that matters is the
one that is new in BOTH dimensions:

                        RECENT 120d          OLDER window
    discovery syms      the original         new window
    held-out syms       new symbols          NEW BOTH  <-- the real test

Held-out symbols are turnover ranks below the discovery set, built the same way
research/studies/trend_holdout.py builds its hold-out - the ones the bot does
not scan. The older window is everything in 333 days of deep history that ends
before the recent 120 begin, so the two windows share no bars.

TWO WARNINGS FROM research/deep.py, both of which apply here:

  "SURVIVORSHIP IS THE PRICE AND IT MUST BE PAID KNOWINGLY. The universe is the
   sixty most liquid perpetuals TODAY. Walking those same sixty back a year
   over-samples coins that went up. A replication that comes back BETTER than
   the 42-day result is evidence of that bias, not of a stronger edge."

  "Read differences here; distrust levels."

The older window is further back, so it carries MORE survivorship bias, not
less. If the older cells come back stronger, that is the bias talking.

    PYTHONPATH=. RIPTIDE_DEEP_CACHE=/tmp/deep python3 research/lit_repl.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import statistics                                       # noqa: E402

import aiohttp                                          # noqa: E402

from research.deep import load_deep                     # noqa: E402
import research.lit_v3 as L                             # noqa: E402
import research.lit_exit as X                           # noqa: E402

DAYS = 333
RECENT_DAYS = 120           # the window every earlier measurement used
WARMUP = 500                # bars the engine needs before a setup is eligible
TFS = ("Min15", "Min30", "Min60")

DISCOVERY = X.SYMS          # the original 30, unchanged


async def heldout(sess, skip, want):
    """Turnover ranks skip+1 .. skip+want — symbols the discovery set excludes.

    Same construction as research/studies/trend_holdout.py: rebuilt from
    contract detail rather than taken from list_symbols, which truncates at
    Riptide's TOP_N and so cannot express 'the ones the bot does not scan'.
    """
    from riptide.exchange import BASE, QUOTE, filter_by_turnover, get_json
    d = await get_json(sess, f"{BASE}/api/v1/contract/detail")
    if not d or not d.get("data"):
        return []
    pool = [c["symbol"] for c in d["data"]
            if c.get("quoteCoin") == QUOTE and c.get("state") == 0
            and c.get("apiAllowed") is not False
            and not any("tradfi" in p for p in (c.get("conceptPlate") or []))]
    import riptide.exchange as ex
    keep = ex.TOP_N
    try:
        ex.TOP_N = skip + want
        ranked = await filter_by_turnover(sess, pool)
    finally:
        ex.TOP_N = keep
    return [s for s in ranked[skip:skip + want] if s not in DISCOVERY]


async def cells(sess, syms, tf, cut):
    """One engine pass over the full history per symbol, then setups are split
    by timestamp. Running the engine per-slice instead would deny the older
    window its warm-up and make the two windows structurally different."""
    older, recent = [], []
    for sym in syms:
        try:
            cs = await load_deep(sess, sym, tf, days=DAYS)
        except Exception:
            continue
        if len(cs) < 2000:
            continue
        m, _i, _d, _g = L.engine(cs)
        su, bb = X.collect(cs, m.events)
        for s in su:
            if s.bar < WARMUP:
                continue
            (recent if cs[s.bar].t >= cut else older).append((cs, bb, s))
    return older, recent


def score(rows, rule, k=0.0):
    return [X.simulate(cs, bb, s, rule, k)[0] for cs, bb, s in rows]


def line(label, rs):
    if len(rs) < 20:
        print(f"    {label:<22}{len(rs):>6}   too few to read")
        return
    se = statistics.stdev(rs) / (len(rs) ** 0.5)
    net = statistics.fmean(rs)
    w = [r for r in rs if r > 0]
    flag = "  <-- >2se" if abs(net) > 2 * se else ""
    print(f"    {label:<22}{len(rs):>6}{100 * len(w) / len(rs):>8.1f}%"
          f"{net:>9.3f}{se:>8.3f}{net / se if se else 0:>8.1f}{flag}")


async def main():
    import time
    cut = time.time() - RECENT_DAYS * 86400      # Candle.t is SECONDS

    async with aiohttp.ClientSession() as sess:
        held = await heldout(sess, skip=len(DISCOVERY), want=70)
        held = held[:30]
        print(f"held-out symbols ({len(held)}): {', '.join(held[:8])} ...")

        book = {}
        for tf in TFS:
            for nm, syms in (("discovery", DISCOVERY), ("held-out", held)):
                o, r = await cells(sess, syms, tf, cut)
                book[(tf, nm)] = (o, r)
                print(f"  {tf} {nm}: {len(o)} older setups, "
                      f"{len(r)} recent setups")

    print("\n" + "=" * 88)
    print("  REPLICATION OF THE Min30 CELL")
    print("  The original reading is [discovery / recent]. The test is")
    print("  [held-out / older] - new symbols AND a window with no shared bars.")
    print("=" * 88)

    for rule, k, rn in (("bos", 0.0, "exit at BOS (where the Min30 claim came "
                                     "from)"),
                        ("struct", 0.0, "structure trail"),
                        ("mfe", 1.5, "mfe - 1.5R")):
        print(f"\n  {rn}")
        print(f"    {'cell':<22}{'n':>6}{'win%':>8}{'NET R':>9}{'se':>8}"
              f"{'t':>8}")
        for tf in TFS:
            print(f"  {tf}")
            for nm in ("discovery", "held-out"):
                o, r = book[(tf, nm)]
                line(f"{nm} / recent", score(r, rule, k))
                line(f"{nm} / older", score(o, rule, k))

    # The cells do not separate by TIMEFRAME, they separate by WINDOW. Test
    # that directly: pool every timeframe and both symbol sets, split only on
    # recent vs older. If the split is there, "Min30 is good" was never a
    # timeframe finding - it was "the recent 120 days were good".
    print("\n" + "=" * 88)
    print("  POOLED ON WINDOW ALONE - every timeframe, both symbol sets")
    print("=" * 88)
    print(f"    {'cell':<22}{'n':>6}{'win%':>8}{'NET R':>9}{'se':>8}{'t':>8}")
    for rule, k, rn in (("bos", 0.0, "exit at BOS"),
                        ("struct", 0.0, "structure trail"),
                        ("mfe", 1.5, "mfe - 1.5R")):
        print(f"  {rn}")
        for wi, lab in ((1, "recent 120d"), (0, "older window")):
            rs = []
            for tf in TFS:
                for nm in ("discovery", "held-out"):
                    rs += score(book[(tf, nm)][wi], rule, k)
            line(lab, rs)
        for dirn, dl in ((1, "  recent LONG"), (-1, "  recent SHORT")):
            rs = []
            for tf in TFS:
                for nm in ("discovery", "held-out"):
                    rows = [x for x in book[(tf, nm)][1] if x[2].dir == dirn]
                    rs += score(rows, rule, k)
            line(dl, rs)

    print("\n" + "=" * 88)
    print("  READ")
    print("=" * 88)
    print("  A cell is only worth discussing if |NET| exceeds about 2 se. The")
    print("  t column is NET/se; anything under 2 is consistent with zero, and")
    print("  a positive cell next to a negative one at t<2 is what noise looks")
    print("  like. Per research/deep.py, an OLDER cell that comes back")
    print("  STRONGER is evidence of survivorship bias, not of an edge.")


if __name__ == "__main__":
    asyncio.run(main())
