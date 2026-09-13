"""THE WHOLE COST CHAIN, PER TRADE — not just "assume every winner is +2R".

    gross R  -  entry fee  -  exit fee  -  funding  -  spread  =  net R

WHY THIS EXISTS. research/harness.py already charges the two trading fees
correctly, and it charges them with the right STRUCTURE: a limit entry and a
limit target are both MAKER, a stop is TAKER, so a winner pays maker x2 and
only a stopped-out trade pays the taker leg. What it says about the rest is a
comment:

    "WHAT IS STILL NOT MODELLED, so these remain optimistic: FUNDING, which the
     XMR settlement shows is a further 25% on top of the trading fee, and
     SLIPPAGE on the stop."

That was true when it was written because funding was believed to have no
history. It does — /api/v1/contract/funding_rate/history is public and carries
539 days, longer than the window every study here runs on. So funding stops
being a caveat and becomes a column.

FUNDING IS NOT A FEE AND IS NOT SIGNED THE SAME WAY. MEXC does not charge it;
it is a transfer between longs and shorts every 8 hours. A LONG PAYS when the
rate is positive and RECEIVES when it is negative; a short is the mirror. So it
can help a trade, and averaging it across a mixed book hides that. It is
reported per direction.

    funding in R = (signed sum of settlements inside the hold) x 100 / risk_pct

SPREAD IS CHARGED ONLY ON LOSERS, for the same reason the taker fee is. The
entry rests as a limit and the target rests as a limit — neither crosses the
book. The stop is a market order and crosses it. Charging spread on every trade
would overstate it by roughly the win rate, which is the mistake the "$2 in and
$2 out" arithmetic makes.

    spread in R (losers only) = spread% / risk_pct

THE SPREAD FIGURE IS A LIVE SNAPSHOT AND THAT IS ITS WEAKNESS. The book has no
history on this exchange, so there is no way to know what the spread was at any
past fill. One reading per symbol, taken in calm conditions, is applied to
every trade on that symbol. A stop-out happens in the opposite conditions, so
this column is a FLOOR on the true cost and slippage beyond it is still not
modelled at all.

    PYTHONPATH=. RIPTIDE_DEEP_CACHE=/tmp/deep \
        python3 research/studies/cost_chain.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import json                                             # noqa: E402
from bisect import bisect_left, bisect_right            # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import BASE, BAR_SECONDS            # noqa: E402
from research.deep import load_universe                 # noqa: E402
from research.harness import FEE_MAKER, FEE_TAKER       # noqa: E402
from research.studies.poi_tf import DAY, DAYS, H8       # noqa: E402
from research.studies.poi_tf import collect, context, universe  # noqa: E402
from research.studies.pick_rule import TFS, pick_rolling  # noqa: E402
from research.studies.band_key import COOLDOWN, KEYS    # noqa: E402
from research.studies.funding import funding_table      # noqa: E402

TIMEOUT = aiohttp.ClientTimeout(total=25)


def funding_in_r(table, sym, t0, t1, is_long, risk_pct):
    """Signed funding over the hold, expressed in R.

    Every settlement at or after the fill and strictly before the exit. A long
    PAYS a positive rate, a short RECEIVES it, so the sign flips with direction
    and the result can be negative — funding is income on the right side of a
    crowded book.
    """
    got = table.get(sym)
    if not got or risk_pct <= 0:
        return None
    times, rates = got
    i, j = bisect_left(times, t0), bisect_right(times, t1)
    if j <= i:
        return 0.0
    total = sum(rates[i:j])
    return (total if is_long else -total) * 100 / risk_pct


async def live_spreads(sess, syms):
    out = {}
    for s in syms:
        try:
            async with sess.get(f"{BASE}/api/v1/contract/depth/{s}",
                                timeout=TIMEOUT) as r:
                d = (json.loads(await r.text()) or {}).get("data") or {}
        except Exception:
            continue
        b, a = d.get("bids") or [], d.get("asks") or []
        if b and a:
            mid = (b[0][0] + a[0][0]) / 2
            out[s] = 100 * (a[0][0] - b[0][0]) / mid
        await asyncio.sleep(0.35)
    return out


def chain(rows, table, spreads):
    """The decomposition, averaged over the rows handed in."""
    n = 0
    g = fee = fund = spr = 0.0
    fund_long = fund_short = 0.0
    nl = ns = 0
    for t in rows:
        if not t.filled or not t.exit_t or t.risk_pct <= 0:
            continue
        f = funding_in_r(table, t.sym, t.fill_t, t.exit_t, t.is_long,
                         t.risk_pct)
        if f is None:
            continue
        n += 1
        g += t.gross
        fee += t.gross - t.r          # what the harness already charged
        fund += f
        if t.is_long:
            fund_long += f
            nl += 1
        else:
            fund_short += f
            ns += 1
        # Spread crosses the book only when the stop fires.
        sp = spreads.get(t.sym)
        if sp is not None and t.r <= 0:
            spr += sp / t.risk_pct
    if not n:
        return None
    return dict(n=n, gross=g / n, fee=fee / n, fund=fund / n, spread=spr / n,
                net=(g - fee - fund - spr) / n,
                fund_long=fund_long / max(nl, 1),
                fund_short=fund_short / max(ns, 1))


def line(label, rows, table, spreads):
    c = chain(rows, table, spreads)
    if not c:
        print(f"  {label:<26}  no rows")
        return
    print(f"  {label:<26}{c['n']:>7}{c['gross']:>+10.4f}{-c['fee']:>+10.4f}"
          f"{-c['fund']:>+10.4f}{-c['spread']:>+10.4f}{c['net']:>+11.4f}")


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
        table = await funding_table(sess, syms)
        print("  reading live order books…")
        spreads = await live_spreads(sess, syms)

    sent = [t for tf in TFS for t in by_tf[tf] if t.day]
    picks = pick_rolling(sent, KEYS["A  tf > band > confd  (shipped)"], COOLDOWN)
    pick_ids = {id(t) for t in picks}

    print("\nTHE WHOLE COST CHAIN, PER TRADE")
    print(f"{len(syms)} symbols · {DAYS} days · {'+'.join(TFS)} · target 2R")
    print(f"fees: maker {FEE_MAKER:g}% taker {FEE_TAKER:g}% — a winner pays "
          f"maker x2, a loser pays maker + taker")
    print(f"spread: live snapshot on {len(spreads)} symbols, charged ONLY on "
          f"losers (the stop is the only leg that crosses)\n")

    hdr = (f"  {'stream':<26}{'n':>7}{'gross':>10}{'fees':>10}"
           f"{'funding':>10}{'spread':>10}{'NET':>11}")
    def row(lab, rows):
        line(lab, rows, table, spreads)

    print(f"{'=' * 86}\nPRIMARY — THE 🎯 PICKS\n{'=' * 86}")
    print(hdr)
    row("all picks", picks)
    for tf in TFS:
        row(f"  {tf}", [t for t in picks if t.tf == tf])
    row("  longs", [t for t in picks if t.is_long])
    row("  shorts", [t for t in picks if not t.is_long])

    print(f"\n{'=' * 86}\nSECONDARY — EVERY ALERT SENT\n{'=' * 86}")
    print(hdr)
    row("all sent", sent)
    for tf in TFS:
        row(f"  {tf}", [t for t in sent if t.tf == tf])

    print(f"\n{'=' * 86}\nFUNDING IS A TRANSFER, NOT A FEE\n{'=' * 86}")
    c = chain(picks, table, spreads)
    if c:
        print(f"  picks, longs   funding costs {c['fund_long']:+.4f} R")
        print(f"  picks, shorts  funding costs {c['fund_short']:+.4f} R")
        print("\n  A negative number is INCOME. MEXC does not charge funding —")
        print("  longs and shorts pay each other, so the side that is not")
        print("  crowded is paid to hold. Averaging the two hides that, which")
        print("  is why they are split here.")

    print(f"\n{'=' * 86}\nWHAT IS STILL MISSING\n{'=' * 86}")
    print("  SLIPPAGE on the stop. A market order in a fast move fills beyond")
    print("  the spread and there is no way to measure that from candles.")
    print("  SPREAD AT THE TIME OF THE FILL. The book has no history here, so")
    print("  one calm-conditions reading stands in for every past trade. Stops")
    print("  fire in the opposite conditions, so the spread column is a FLOOR.")
    print("  Both keep every net figure above OPTIMISTIC.")


if __name__ == "__main__":
    asyncio.run(main())
