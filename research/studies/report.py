"""The whole strategy report, in the shape TradingView's Strategy Tester prints.

WHAT THIS IS AND WHAT IT IS NOT. This replays recorded candles and does
arithmetic. There is no exchange key and no order path anywhere in this
project and this file adds neither. It is a measurement of the ALERT STREAM
the bot already sends: Min30, POI required, grade A or B, entry at the gap,
stop beyond the sweep, target 2R — the deployed numbers from riptide.conf. Both
tradeable streams are reported, CONFIRMED and EARLY, separately and together,
because they turn out to be different strategies wearing the same name.

THREE THINGS THAT MAKE THIS DIFFER FROM A TRADINGVIEW REPORT, ALL IN THE
DIRECTION OF FLATTERING THE STRATEGY. Say them before the numbers, not after.

  SURVIVORSHIP. The universe is the sixty most liquid perpetuals TODAY, walked
  backwards 333 days. Every coin that died, delisted or fell out of the top
  sixty in that year is missing, and the ones that remain are disproportionately
  the ones that went up. `research/deep.py` sets this out at length. LEVELS here
  are biased optimistic and more so for longs than shorts. Comparisons between
  arms measured on the same rows are much safer.

  FUNDING AND SLIPPAGE ARE NOT MODELLED. Fees are, at the rates derived from a
  real settlement (0.010% maker in, 0.022% taker out). The same settlement
  showed funding running about a further 25% on top of the trading fee, and
  stop slippage is not modelled at all. Both are real costs this report omits.

  ONE BAR CANNOT ORDER ITSELF. When a single bar spans both the stop and the
  target, the STOP is taken. That is the pessimistic read and the only honest
  one, and it is the single assumption pulling the other way.

WHY THE T-STATISTICS BELOW ARE PER-BAR AND THE REPORT IS PER-TRADE. A strategy
report counts trades, so the report does. But sixty perpetuals move together,
and twelve signals in one half hour are not twelve independent draws — so every
standard error and every significance claim in this project is computed on BETS
(the mean R of all symbols firing on the same bar), never on trades. Both units
appear here, labelled. Read the trade counts as volume and the bet counts as
evidence.

    PYTHONPATH=. RIPTIDE_MIN_GRADE=B RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/report.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import math                                             # noqa: E402
import statistics                                       # noqa: E402
from collections import defaultdict                     # noqa: E402
from datetime import datetime, timezone                 # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import BAR_SECONDS, CFG, TRACK_TARGET_R   # noqa: E402
from riptide.engine import grade_of, run_engine         # noqa: E402
from riptide.exchange import fetch_candles, list_symbols  # noqa: E402
from riptide.trend import di_at, direction_at, poi_at   # noqa: E402
from research.deep import load_universe                 # noqa: E402
from research.harness import mean_se, simulate          # noqa: E402

DAYS = 333
INTERVAL = "Min30"
START = 300.0          # the account the bot was sized for
RISK_PCT = 1.0         # of balance at entry, so it compounds
YEAR = 365.25 * 86400


class Trade:
    __slots__ = ("sym", "t", "grade", "kind", "is_long", "risk_pct", "r",
                 "filled", "fill_t", "exit_t", "fill_bars", "hold_bars",
                 "exit", "mfe", "mae")


async def collect(sess, candles):
    """Both streams the bot actually sends, at the deployed gates.

    GRADE B DOES NOT EXIST ON THE CONFIRMED STREAM AND THAT IS NOT A BUG IN
    THIS SCRIPT. With RIPTIDE_POI_REQUIRED=1 a confirmed setup has poi=True by
    construction, and GRADES maps (early=False, poi=True, trend agrees) to A
    and (…, trend disagrees) to C. There is no cell left for B. So on confirmed
    alerts, RIPTIDE_MIN_GRADE=B is doing exactly what MIN_GRADE=A would do —
    the setting only bites on EARLY signals, where (early, poi, trend) is the B
    cell. Reporting the two streams separately is the only way that fact shows.
    """
    out = []
    bar = BAR_SECONDS[INTERVAL]
    for sym, cs in candles.items():
        early = []
        try:
            setups = run_engine(sym, cs, CFG, early_out=early)
        except Exception:
            continue
        idx = {c.t: i for i, c in enumerate(cs)}
        for kind, batch in (("confirmed", setups), ("early", early)):
            for x in batch:
                i = idx.get(x.detected_time)
                if i is None or x.entry <= 0 or abs(x.entry - x.stop) <= 0:
                    continue
                w = x.detected_time
                poi = await poi_at(sess, sym, w, x.stop, x.is_long,
                                   fetch_candles)
                if not (True if poi is None else bool(poi)):
                    continue
                d = await direction_at(sess, sym, w, fetch_candles)
                di = await di_at(sess, sym, w, fetch_candles)
                g = grade_of(kind == "early", True, d or 0, x.is_long,
                             di or 0)[0]
                if g not in "AB":
                    continue
                o = simulate(cs, i, x.entry, x.stop, x.is_long,
                             target_r=TRACK_TARGET_R)
                tr = Trade()
                tr.sym, tr.t, tr.grade, tr.kind = sym, w, g, kind
                tr.is_long = x.is_long
                tr.risk_pct = 100 * abs(x.entry - x.stop) / x.entry
                tr.r, tr.filled, tr.exit = o.r, o.filled, o.exit
                tr.mfe, tr.mae = o.mfe, o.mae
                tr.fill_bars = (o.fill_bar - i
                                if o.filled and o.fill_bar else None)
                tr.hold_bars = (o.exit_bar - o.fill_bar
                                if o.filled and o.exit_bar and o.fill_bar
                                else None)
                tr.fill_t = (w + bar * tr.fill_bars
                             if tr.fill_bars is not None else None)
                tr.exit_t = (tr.fill_t + bar * tr.hold_bars
                             if tr.fill_t is not None
                             and tr.hold_bars is not None else None)
                out.append(tr)
    return out


# ---------------------------------------------------------------- statistics

def streaks(rs):
    """Longest run of wins and of losses, in trade order."""
    bw = bl = cw = cl = 0
    for r in rs:
        if r > 0:
            cw, cl = cw + 1, 0
        elif r < 0:
            cw, cl = 0, cl + 1
        else:
            cw = cl = 0
        bw, bl = max(bw, cw), max(bl, cl)
    return bw, bl


def drawdown(rs):
    """Peak-to-trough on the cumulative R curve, and how long it lasted."""
    eq = peak = 0.0
    worst = 0.0
    since = longest = 0
    for i, r in enumerate(rs):
        eq += r
        if eq >= peak:
            peak, since = eq, i
        else:
            worst = max(worst, peak - eq)
            longest = max(longest, i - since)
    return worst, longest


def compound(trades, max_open=None):
    """A 300 USDT account risking 1% of balance per fill, replayed in time.

    Realised P&L lands at the EXIT, not the entry, which is what makes the
    drawdown here differ from the R curve's: several positions can be open and
    underwater at once. max_open is the margin constraint a small account
    actually hits; None means unlimited and is the optimistic bound.
    """
    ev = []
    for t in trades:
        if t.filled and t.exit_t is not None:
            ev.append((t.fill_t, 0, t))
            ev.append((t.exit_t, 1, t))
    ev.sort(key=lambda e: (e[0], e[1]))
    bal = peak = START
    dd = 0.0
    open_now, stake_of, skipped = set(), {}, 0
    for _, kind, t in ev:
        if kind == 0:
            if max_open is not None and len(open_now) >= max_open:
                skipped += 1
                continue
            open_now.add(id(t))
            stake_of[id(t)] = bal * RISK_PCT / 100
        elif id(t) in open_now:
            open_now.discard(id(t))
            bal += stake_of.pop(id(t)) * t.r
            peak = max(peak, bal)
            dd = max(dd, (peak - bal) / peak)
    return bal, dd, skipped


def sharpe(rs, span_seconds, n_periods):
    """Annualised, on the per-trade R series. TradingView annualises an equity
    curve; this annualises trades by their realised frequency, which is the
    same idea and is stated rather than implied."""
    if len(rs) < 3:
        return float("nan"), float("nan")
    m = statistics.fmean(rs)
    sd = statistics.pstdev(rs)
    down = [min(0.0, r) for r in rs]
    dsd = (statistics.fmean(x * x for x in down)) ** 0.5
    per_year = n_periods / (span_seconds / YEAR)
    k = math.sqrt(per_year)
    return (m / sd * k if sd else float("nan"),
            m / dsd * k if dsd else float("nan"))


def bets_of(trades):
    g = defaultdict(list)
    for t in trades:
        g[t.t].append(t.r)
    return [statistics.fmean(g[k]) for k in sorted(g)]


def block(name, trades, span):
    """One cell of the distribution tables: trades, win rate, R, and evidence."""
    f = [t for t in trades if t.filled]
    if not f:
        return f"  {name:<22} —"
    rs = [t.r for t in f]
    b = bets_of(f)
    m, se = mean_se(b)
    return (f"  {name:<22} {len(f):>5} trades  {len(b):>4} bets  "
            f"{sum(1 for r in rs if r > 0) / len(rs):>4.0%} win  "
            f"{statistics.fmean(rs):>+7.3f} R/trade  {sum(rs):>+8.1f} R total  "
            f"{m:>+6.3f}±{se:.3f} R/bet")


def full(label, trades, note=""):
    """One complete Strategy-Tester report over whatever set is handed in."""
    trades = sorted(trades, key=lambda t: (t.exit_t if t.exit_t is not None
                                           else t.t))
    filled = [t for t in trades if t.filled and t.exit_t is not None]
    if len(filled) < 20:
        print(f"\n\n{'=' * 78}\n{label}: {len(filled)} filled trades — too "
              f"few to report.\n")
        return
    rs = [t.r for t in filled]
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r < 0]
    lo = min(t.t for t in trades)
    hi = max(t.exit_t or t.t for t in trades)
    span = hi - lo
    bar_h = BAR_SECONDS[INTERVAL] / 3600
    b = bets_of(filled)
    mb, sb = mean_se(b)

    print(f"\n\n{'=' * 78}\n{label}")
    if note:
        print(note)
    print(f"{datetime.fromtimestamp(lo, timezone.utc):%Y-%m-%d} to "
          f"{datetime.fromtimestamp(hi, timezone.utc):%Y-%m-%d} · "
          f"{DAYS} days · {INTERVAL} · target {TRACK_TARGET_R:g}R")

    gp, gl = sum(wins), -sum(losses)
    print("\n-- PERFORMANCE " + "-" * 62)
    print(f"  Net profit                {sum(rs):>+10.1f} R")
    print(f"  Gross profit              {gp:>+10.1f} R")
    print(f"  Gross loss                {-gl:>+10.1f} R")
    print(f"  Profit factor             {gp / gl if gl else float('inf'):>10.2f}")
    print(f"  Expectancy per trade      {statistics.fmean(rs):>+10.3f} R")
    print(f"  Expectancy per BET        {mb:>+10.3f} R   +/- {sb:.3f} SE"
          f"   ({abs(mb / sb) if sb else 0:.1f} SE from zero)")

    print("\n-- TRADES " + "-" * 67)
    unf = len(trades) - len([t for t in trades if t.filled])
    ex = defaultdict(int)
    for t in filled:
        ex[t.exit] += 1
    print(f"  Signals sent              {len(trades):>10}")
    print(f"  Filled                    {len(filled):>10}   "
          f"({len(filled) / len(trades):.0%} of signals)")
    print(f"  Never filled              {unf:>10}   "
          f"({unf / len(trades):.0%}) - costs nothing, scores 0.0")
    print(f"  Independent bets (bars)   {len(b):>10}")
    print(f"  Percent profitable        {len(wins) / len(filled):>10.1%}")
    print(f"  Winning trades            {len(wins):>10}")
    print(f"  Losing trades             {len(losses):>10}")
    for k in ("target", "stop", "timeout"):
        if ex[k]:
            print(f"    exit by {k:<17}{ex[k]:>10}   "
                  f"({ex[k] / len(filled):.0%})")

    aw = statistics.fmean(wins) if wins else 0.0
    al = statistics.fmean(losses) if losses else 0.0
    rr = abs(aw / al) if al else 0.0
    print("\n-- RISK / REWARD " + "-" * 60)
    print(f"  Target R (planned)        {TRACK_TARGET_R:>+10.2f} R")
    print(f"  Average winning trade     {aw:>+10.3f} R")
    print(f"  Average losing trade      {al:>+10.3f} R")
    print(f"  Realised reward/risk      {rr:>10.2f} : 1")
    print(f"  Break-even win rate needed{1 / (1 + rr) if rr else 0:>10.1%}"
          f"   (actual {len(wins) / len(filled):.1%}, margin "
          f"{len(wins) / len(filled) - 1 / (1 + rr) if rr else 0:+.1%})")
    print(f"  Largest winning trade     {max(rs):>+10.3f} R")
    print(f"  Largest losing trade      {min(rs):>+10.3f} R")
    print(f"  Average MFE (best excursion){statistics.fmean(t.mfe for t in filled):>+8.3f} R")
    print(f"  Average MAE (worst)       {statistics.fmean(t.mae for t in filled):>+10.3f} R")
    print(f"  Median stop distance      {statistics.median(t.risk_pct for t in trades):>10.2f}% of price")

    dd_r, dd_len = drawdown(rs)
    sh, so = sharpe(rs, span, len(rs))
    bw, bl = streaks(rs)
    print("\n-- DRAWDOWN AND RATIOS " + "-" * 54)
    print(f"  Max drawdown              {dd_r:>10.1f} R")
    print(f"  Max drawdown vs net profit{dd_r / sum(rs) if sum(rs) else float('inf'):>10.2f} x"
          "   ( >1 means the worst run erased more than the year made )")
    print(f"  Longest time under water  {dd_len:>10} trades of {len(rs)}")
    print(f"  Recovery factor           {sum(rs) / dd_r if dd_r else float('inf'):>10.2f}"
          "   (net profit / max drawdown)")
    print(f"  Sharpe (annualised)       {sh:>10.2f}"
          "   per-trade series, annualised by realised trade frequency;")
    print(f"  Sortino (annualised)      {so:>10.2f}"
          "   positions overlap, so both read higher than a single-position")
    print(f"{'':<28}       equity curve would give. Not comparable to TradingView's.")
    print(f"  Max consecutive wins      {bw:>10}")
    print(f"  Max consecutive losses    {bl:>10}")

    print("\n-- ON A 300 USDT ACCOUNT, 1% OF BALANCE PER TRADE " + "-" * 27)
    for cap in (None, 10, 5, 3):
        bal, dd, sk = compound(trades, cap)
        lab = "unlimited" if cap is None else f"max {cap} open"
        print(f"  {lab:<16} final {bal:>10,.0f} USDT   "
              f"{(bal / START - 1):>+8.0%}   max drawdown {dd:>5.1%}"
              f"   {sk} skipped for margin")

    print("\n-- DIRECTION " + "-" * 64)
    print(block("Long", [t for t in filled if t.is_long], span))
    print(block("Short", [t for t in filled if not t.is_long], span))
    lb = bets_of([t for t in filled if t.is_long])
    sbt = bets_of([t for t in filled if not t.is_long])
    if len(lb) > 20 and len(sbt) > 20:
        ml, sl = mean_se(lb)
        ms, ss = mean_se(sbt)
        se = (sl ** 2 + ss ** 2) ** 0.5
        print(f"  long minus short          {ml - ms:>+7.3f} R/bet   "
              f"|z| {abs(ml - ms) / se if se else 0:.2f}"
              "   - survivorship inflates LONGS")
        print("                            specifically, so distrust this axis most.")

    print("\n-- GRADE " + "-" * 68)
    for g in "AB":
        got = [t for t in filled if t.grade == g]
        if got:
            print(block(f"Grade {g}", got, span))

    print("\n-- STOP DISTANCE (the one shipped filter) " + "-" * 35)
    for lab, f in (("under 1.2%", lambda t: t.risk_pct < 1.2),
                   ("1.2% - 2.6%  take", lambda t: 1.2 <= t.risk_pct <= 2.6),
                   ("over 2.6%    skip", lambda t: t.risk_pct > 2.6)):
        print(block(lab, [t for t in filled if f(t)], span))

    print("\n-- HOLDING TIME " + "-" * 61)
    fb = [t.fill_bars for t in filled if t.fill_bars is not None]
    hb = [t.hold_bars for t in filled if t.hold_bars is not None]
    print(f"  Bars signal to fill       {statistics.median(fb):>10.0f} median"
          f"   {statistics.fmean(fb):>6.1f} mean   "
          f"({statistics.fmean(fb) * bar_h:.1f} h)")
    print(f"  Bars held                 {statistics.median(hb):>10.0f} median"
          f"   {statistics.fmean(hb):>6.1f} mean   "
          f"({statistics.fmean(hb) * bar_h:.1f} h)")

    print("\n-- BY QUARTER " + "-" * 63)
    byq = defaultdict(list)
    for t in filled:
        d = datetime.fromtimestamp(t.t, timezone.utc)
        byq[f"{d.year}Q{(d.month - 1) // 3 + 1}"].append(t)
    for q in sorted(byq):
        print(block(q, byq[q], span))

    print("\n-- SYMBOLS " + "-" * 66)
    bysym = defaultdict(list)
    for t in filled:
        bysym[t.sym].append(t.r)
    rank = sorted(bysym.items(), key=lambda kv: -sum(kv[1]))
    for sym, v in rank[:5]:
        print(f"  best   {sym:<16} {len(v):>4} trades  {sum(v):>+7.1f} R")
    for sym, v in rank[-5:]:
        print(f"  worst  {sym:<16} {len(v):>4} trades  {sum(v):>+7.1f} R")
    pos = sum(1 for v in bysym.values() if sum(v) > 0)
    top5 = sum(sum(v) for _, v in rank[:5])
    print(f"  {pos} of {len(bysym)} symbols positive ({pos / len(bysym):.0%})."
          f"  The best 5 supply {top5 / sum(rs) if sum(rs) else 0:.0%} of net R"
          f" - remove them and the year is {sum(rs) - top5:+.1f} R.")


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = await list_symbols(sess)
        candles = await load_universe(sess, syms, INTERVAL, DAYS)
        trades = await collect(sess, candles)

    print("RIPTIDE - FULL STRATEGY REPORT")
    print(f"the deployed gates from riptide.conf: {INTERVAL} structure, POI "
          f"required, grade A-B,\nentry at the gap, stop beyond the raid, "
          f"target {TRACK_TARGET_R:g}R, {len(candles)} symbols, {DAYS} days.")
    print("fees charged at measured rates; FUNDING AND SLIPPAGE ARE NOT "
          "MODELLED and the\nuniverse is survivorship-biased, so every level "
          "below is optimistic.")

    conf = [t for t in trades if t.kind == "confirmed"]
    ear = [t for t in trades if t.kind == "early"]
    full("CONFIRMED SETUPS  (grade A - the stream the risk band was fitted on)",
         conf)
    full("EARLY SIGNALS  (grade B - the gap before the shift confirms)", ear,
         note="the bot sends these too, RIPTIDE_EARLY_ALERTS=1. About 15% of\n"
              "them describe the same trade as a confirmed setup and are\n"
              "collapsed into one message live; here they are counted whole.")
    full("BOTH STREAMS TOGETHER  (everything the bot alerts as tradeable)",
         trades)


if __name__ == "__main__":
    asyncio.run(main())
