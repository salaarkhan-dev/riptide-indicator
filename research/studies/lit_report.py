"""LIT_FORWARD_V1 — a full sequential backtest report, 15m and 30m.

Written to answer "is the R real, or is it three lucky trades?" — so every
statistic that can hide concentration is reported next to one that exposes it.

WHAT MAKES THIS A BAR-REPLAY-SHAPED TEST RATHER THAN A SUMMARY

  * Trades are ordered CHRONOLOGICALLY and the equity curve is walked forward
    one trade at a time, so drawdown is a real peak-to-trough on a real
    sequence rather than a statistic computed from a bag of numbers.
  * ONE POSITION AT A TIME PER SYMBOL. A setup that appears while that symbol
    already has a live trade is SKIPPED, exactly as it would be on a chart you
    are watching. This is what a replay does and what a pooled average does
    not.
  * The entry bar resolves nothing, the stop is tested before the target, and
    where OHLC cannot order two events the loss is taken. That is the repo's
    conservative rule, unchanged.
  * Fees are charged on every trade at the repo's model.

CONCENTRATION, WHICH IS THE POINT OF THE REQUEST

  Total R is reported beside: R without the single best trade, R without the
  best five, the share of all gross profit held by the top trade and top five,
  and the median trade. A number that collapses when one trade is removed was
  one trade, not an edge.

  A per-MONTH table then shows whether the result accumulated steadily or
  arrived in one window. Both are needed: a strategy can be unconcentrated in
  trades and completely concentrated in time.

STREAKS are reported because they are what actually gets people to stop: the
longest losing run, the distribution of runs, and the deepest drawdown in both
R and in consecutive losers.

    PYTHONPATH=. RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/lit_report.py > lit_report_out.txt
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import statistics                                       # noqa: E402
import time                                             # noqa: E402
from collections import defaultdict                     # noqa: E402
from datetime import datetime, timezone                 # noqa: E402

import aiohttp                                          # noqa: E402

from research.deep import load_deep                     # noqa: E402
from research.harness import simulate_market            # noqa: E402
import research.lit_v3 as L                             # noqa: E402
import research.lit_repl as RP                          # noqa: E402
from research.studies.lit_stage_a import trails         # noqa: E402

DAYS = 333
WARMUP = 500
HORIZON = 500
MIN_RR = 0.5
TFS = ("Min15", "Min30")
SYMS = RP.DISCOVERY


def collect(cs):
    """Frozen V1 setups, in bar order."""
    main, _i, _d, _g = L.engine(cs)
    ev = main.events
    piv, _s = trails(cs, ev)
    pbs = {1: [], -1: []}
    out = []
    for e in ev:
        d = 1 if e["dir"] > 0 else -1
        if e["kind"] == "pb":
            pbs[d].append(e["px"])
            continue
        if e["kind"] != "idm_break":
            continue
        i, up, en, bos = e["bar"], d > 0, e["entry"], e["bos"]
        prior = pbs[d][-2] if len(pbs[d]) > 1 else None
        pbs[d] = []
        if i < WARMUP or bos is None or en is None or en <= 0:
            continue
        if (bos <= en) if up else (bos >= en):
            continue
        if prior is None or ((prior >= en) if up else (prior <= en)):
            continue
        if abs(en - prior) <= 0:
            continue
        out.append((i, up, en, prior, bos, piv[d]))
    return out


def replay(cs, rows, arm):
    """Walk the symbol forward taking ONE position at a time.

    A setup arriving while a trade is open is skipped, which is what happens on
    a chart. Returns (trade R, entry time, exit bar) per taken trade.
    """
    taken = []
    busy_until = -1
    for i, up, en, stop, bos, trail in rows:
        if i <= busy_until:
            continue                        # already in a trade on this symbol
        risk = abs(en - stop)
        if arm == "t6":
            o = simulate_market(cs, i, en, stop, up, target_r=1e9, trail=trail,
                                trail_arm_r=MIN_RR, horizon_bars=HORIZON)
        else:
            o = simulate_market(cs, i, en, stop, up, target_px=bos,
                                target_r=abs(bos - en) / risk,
                                horizon_bars=HORIZON)
        if o is None or not o.filled:
            continue
        ex = o.exit_bar if o.exit_bar is not None else i
        busy_until = ex
        taken.append((o.r, cs[i].t, o.exit))
    return taken


def drawdown(rs):
    """Peak-to-trough on the walked-forward equity curve, in R."""
    peak = cum = mdd = 0.0
    dd_len = worst_len = 0
    for r in rs:
        cum += r
        if cum > peak:
            peak, dd_len = cum, 0
        else:
            dd_len += 1
            worst_len = max(worst_len, dd_len)
        mdd = min(mdd, cum - peak)
    return cum, -mdd, worst_len


def streaks(rs):
    runs_w, runs_l = [], []
    cur, sign = 0, 0
    for r in rs:
        s = 1 if r > 0 else -1
        if s == sign:
            cur += 1
        else:
            if sign > 0:
                runs_w.append(cur)
            elif sign < 0:
                runs_l.append(cur)
            cur, sign = 1, s
    if sign > 0:
        runs_w.append(cur)
    elif sign < 0:
        runs_l.append(cur)
    return runs_w, runs_l


def q(v, p):
    if not v:
        return 0.0
    s = sorted(v)
    return s[min(len(s) - 1, int(p * (len(s) - 1)))]


def report(name, trades):
    """trades: list of (R, entry_ts, exit_reason) in chronological order."""
    if len(trades) < 20:
        print(f"\n  {name}: {len(trades)} trades — too few to report")
        return
    rs = [t[0] for t in trades]
    n = len(rs)
    wins = [r for r in rs if r > 0]
    loss = [r for r in rs if r <= 0]
    tot, mdd, ddlen = drawdown(rs)
    mean = statistics.fmean(rs)
    sd = statistics.stdev(rs) if n > 1 else 0.0
    se = sd / (n ** 0.5) if n > 1 else 0.0
    gp = sum(wins)
    gl = abs(sum(loss))
    srt = sorted(rs, reverse=True)

    print(f"\n{'─' * 78}\n  {name}\n{'─' * 78}")
    print(f"  trades              {n}")
    print(f"  win rate            {100 * len(wins) / n:.1f}%  "
          f"({len(wins)}W / {len(loss)}L)")
    print(f"  TOTAL R             {tot:+.1f}")
    print(f"  R per trade         {mean:+.3f}  ± {se:.3f}   t = "
          f"{(mean / se if se else 0):.2f}"
          f"{'   <-- below 2, consistent with zero' if abs(mean / se if se else 0) < 2 else ''}")
    print(f"  median trade        {statistics.median(rs):+.3f}")
    print(f"  avg win / avg loss  {(statistics.fmean(wins) if wins else 0):+.2f}"
          f" / {(statistics.fmean(loss) if loss else 0):+.2f}")
    print(f"  profit factor       {(gp / gl) if gl else float('inf'):.2f}")
    print(f"  expectancy          {mean:+.3f} R per trade")
    print()
    print(f"  MAX DRAWDOWN        {mdd:.1f} R   "
          f"(longest {ddlen} trades below the prior peak)")
    print(f"  recovery factor     {(tot / mdd) if mdd else float('inf'):.2f}"
          f"   (total R / max DD)")

    print("\n  CONCENTRATION — is the R real, or a few trades?")
    print(f"    best trade            {srt[0]:+.2f} R   "
          f"= {100 * srt[0] / gp:.0f}% of all gross profit")
    print(f"    top 5 trades          {sum(srt[:5]):+.2f} R   "
          f"= {100 * sum(srt[:5]) / gp:.0f}% of all gross profit")
    print(f"    TOTAL without best    {tot - srt[0]:+.1f} R   "
          f"({(tot - srt[0]) / (n - 1):+.3f} per trade)")
    print(f"    TOTAL without top 5   {tot - sum(srt[:5]):+.1f} R   "
          f"({(tot - sum(srt[:5])) / (n - 5):+.3f} per trade)")
    print(f"    trades needed for 50% of gross profit: "
          f"{_half(srt, gp)} of {len(wins)} winners")

    rw, rl = streaks(rs)
    print("\n  STREAKS")
    print(f"    longest win run     {max(rw) if rw else 0}")
    print(f"    longest LOSS run    {max(rl) if rl else 0}"
          f"   <- the one that makes people stop")
    print(f"    avg win run         {(statistics.fmean(rw) if rw else 0):.1f}"
          f"     avg loss run {(statistics.fmean(rl) if rl else 0):.1f}")
    print(f"    loss runs >= 5      {sum(1 for x in rl if x >= 5)}"
          f" of {len(rl)} losing runs")

    print("\n  BY MONTH — steady, or one good window?")
    bym = defaultdict(list)
    for r, ts, _w in trades:
        bym[datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m")].append(r)
    months = sorted(bym)
    pos = sum(1 for m in months if sum(bym[m]) > 0)
    print(f"    {len(months)} months, {pos} positive "
          f"({100 * pos / len(months):.0f}%)")
    line = "    "
    for m in months:
        line += f"{m[2:]} {sum(bym[m]):+6.1f}   "
        if len(line) > 66:
            print(line.rstrip())
            line = "    "
    if line.strip():
        print(line.rstrip())
    best_m = max(months, key=lambda m: sum(bym[m]))
    print(f"    best month {best_m} {sum(bym[best_m]):+.1f} R = "
          f"{100 * sum(bym[best_m]) / tot if tot else 0:.0f}% of total R")

    ex = defaultdict(int)
    for _r, _t, w in trades:
        ex[w] += 1
    print("\n  EXITS  " + "  ".join(
        f"{k}={v} ({100*v/n:.0f}%)" for k, v in sorted(ex.items())))


def _half(srt, gp):
    c = 0.0
    for i, r in enumerate(srt, 1):
        c += r
        if c >= gp * 0.5:
            return i
    return len(srt)


async def main():
    print("=" * 78)
    print("LIT_FORWARD_V1 — SEQUENTIAL BACKTEST, 15m and 30m")
    print("=" * 78)
    print(f"population   {len(SYMS)} symbols, {DAYS} days")
    print("rules        the frozen V1 setup, unchanged. Entry at the")
    print("             IDM-break close, stop at the prior pullback pivot,")
    print("             Active Price arms the trail at 0.5R.")
    print("execution    ONE POSITION AT A TIME PER SYMBOL, chronological.")
    print("             A setup during an open trade is SKIPPED, as on a")
    print("             chart. Entry bar resolves nothing; stop before")
    print("             target; fees charged every trade.")
    print("arms         T6 PIVOT TRAIL (the candidate) and BOS TARGET (the")
    print("             frozen control), scored on the SAME setups.")
    print(f"generated    {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}")
    print("=" * 78)

    book = {tf: {"t6": [], "ctl": []} for tf in TFS}
    async with aiohttp.ClientSession() as sess:
        for tf in TFS:
            nsym = 0
            for sym in SYMS:
                try:
                    cs = await load_deep(sess, sym, tf, days=DAYS)
                except Exception:
                    continue
                if len(cs) < 2000:
                    continue
                nsym += 1
                rows = collect(cs)
                for arm in ("t6", "ctl"):
                    book[tf][arm].extend(replay(cs, rows, arm))
            print(f"  {tf}: {nsym} symbols, "
                  f"{len(book[tf]['t6'])} trades taken")

    for tf in TFS:
        print(f"\n\n{'=' * 78}\n  {tf}\n{'=' * 78}")
        for arm, lab in (("t6", "T6 PIVOT TRAIL  (the candidate)"),
                         ("ctl", "BOS TARGET  (the frozen control)")):
            tr = sorted(book[tf][arm], key=lambda x: x[1])
            report(f"{tf} · {lab}", tr)

    print(f"\n\n{'=' * 78}\n  HOW TO READ THIS\n{'=' * 78}")
    print("  1. t below 2 means R per trade is not distinguishable from zero,")
    print("     however good the total looks.")
    print("  2. 'TOTAL without best' and 'without top 5' are the honest")
    print("     version of total R. If they collapse, the total was a handful")
    print("     of trades and will not repeat.")
    print("  3. 'best month as % of total' is the same test in time. A")
    print("     strategy can be spread across trades and still be one month.")
    print("  4. Longest LOSS run and max drawdown are what you would actually")
    print("     have had to sit through.")
    print("  5. These are HISTORICAL bars the candidate was developed on.")
    print("     Stage C already showed the effect halves out of sample. Read")
    print("     this as a description of the past, not a forecast.")


if __name__ == "__main__":
    asyncio.run(main())
