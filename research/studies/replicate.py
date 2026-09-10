"""PHASE A — the deployed model on 333 days. Nothing changed, nothing tuned.

THE CLAIM BEING TRADED ON RESTS ON 23 BETS. "Take Min30 confirmed" came from a
held-out half containing twenty-three separate bets. That is the recommendation
a person is acting on with real money, and it is the thinnest load-bearing
number in the project. Before another hypothesis is tested, that one gets a
proper sample.

NOTHING IS TUNED HERE AND THAT IS THE ENTIRE DESIGN. Same config, same gates,
same fee model, same 2R exit, same one-bet-per-close unit. The only thing that
changes is how much history goes in. A replication that quietly improves a
parameter is not a replication, it is a new study with a familiar name.

WHAT WOULD FALSIFY THE DEPLOYED RULE

  Min30 confirmed failing to stay clearly positive over 333 days. At roughly
  650 signals the standard error should fall to about 0.06, so +0.5 R per bet
  would read at 8 SE and a true zero would read as a zero. Either way the
  question stops being open.

SURVIVORSHIP IS THE THING TO WATCH, NOT THE RESULT

  The universe is the sixty most liquid perpetuals TODAY, walked backwards a
  year. Coins that went up are in it; coins that died are not. So the deep
  window is biased optimistic, and more so for LONGS than shorts.

  A REPLICATION THAT COMES BACK BETTER THAN THE 42-DAY RESULT IS THEREFORE A
  WARNING, NOT A CONFIRMATION. The bias check is the long/short split: if the
  edge over the deep window lives disproportionately in longs, that is the
  survivorship talking. The 42-day window has the same bias but far less room
  to express it, since a coin cannot have 10x'd inside six weeks as often.

  Quarter-by-quarter is the regime check. Forty-two days is one market mood;
  an edge that only exists in one quarter of the year is not an edge, it is a
  season.

  PRE-REGISTERED READING: trust the SIGN and the long/short SYMMETRY. Distrust
  the LEVEL. Distrust any improvement over the 42-day number entirely.

    PYTHONPATH=. RIPTIDE_MIN_GRADE=B RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/replicate.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import statistics                                       # noqa: E402
from collections import defaultdict                     # noqa: E402
from datetime import datetime, timezone                 # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import CFG, MIN_GRADE, TRACK_TARGET_R  # noqa: E402
from riptide.engine import grade_of, run_engine         # noqa: E402
from riptide.exchange import fetch_candles, list_symbols  # noqa: E402
from riptide.trend import di_at, direction_at, poi_at   # noqa: E402
from research.deep import load_universe                 # noqa: E402
from research.harness import mean_se, simulate          # noqa: E402

TF = "Min30"
DAYS = 333
BANDS = "ABCD"
CUT = BANDS.index(MIN_GRADE)


class Sig:
    __slots__ = ("sym", "t", "r", "kind", "is_long", "risk")


async def collect(sess, candles):
    """Every SENT signal over the deep window, exactly as the bot would send it."""
    out = []
    for sym, cs in candles.items():
        early = []
        try:
            setups = run_engine(sym, cs, CFG, early_out=early)
        except Exception:
            continue
        idx = {c.t: i for i, c in enumerate(cs)}
        for kind, sigs, key in (("confirmed", setups, "detected_time"),
                                ("early", early, "fvg_time")):
            for x in sigs:
                i = idx.get(getattr(x, key))
                if i is None or x.entry <= 0 or abs(x.entry - x.stop) <= 0:
                    continue
                o = simulate(cs, i, x.entry, x.stop, x.is_long,
                             target_r=TRACK_TARGET_R)
                if not o.filled or o.exit_bar is None:
                    continue
                when = getattr(x, key)
                poi = await poi_at(sess, sym, when, x.stop, x.is_long,
                                   fetch_candles)
                poi = True if poi is None else bool(poi)
                if not poi:
                    continue                   # POI_REQUIRED, as deployed
                d = await direction_at(sess, sym, when, fetch_candles)
                di = await di_at(sess, sym, when, fetch_candles)
                if BANDS.index(grade_of(kind == "early", poi, d or 0,
                                        x.is_long, di or 0)[0]) > CUT:
                    continue                   # MIN_GRADE, as deployed
                s = Sig()
                s.sym, s.t, s.r, s.kind = sym, when, o.r, kind
                s.is_long = x.is_long
                s.risk = 100 * abs(x.entry - x.stop) / x.entry
                out.append(s)
    return out


def bets(sigs):
    """One bet per close, averaged — the deployed sizing rule."""
    bybar = defaultdict(list)
    for s in sigs:
        bybar[s.t].append(s.r)
    return [(t, statistics.fmean(v)) for t, v in bybar.items()]


def dd_r(pairs):
    bal = peak = dd = 0.0
    for _, r in sorted(pairs):
        bal += r
        peak = max(peak, bal)
        dd = max(dd, peak - bal)
    return dd


def row(label, sigs, days, note=""):
    b = bets(sigs)
    if len(b) < 20:
        print(f"  {label:<32}{len(b):>6}   too few")
        return None
    rs = [r for _, r in b]
    m, se = mean_se(rs)
    d = dd_r(b)
    tot = sum(rs)
    print(f"  {label:<32}{len(b):>6}{len(b) / days:>7.1f}"
          f"{sum(1 for r in rs if r > 0) / len(rs):>6.0%}{m:>+9.3f}{se:>7.3f}"
          f"{tot:>+8.1f}{d:>7.1f}{(tot / d) if d else 0:>7.2f}  {note}")
    return dict(n=len(b), m=m, se=se)


def header(title):
    print(f"\n{title}")
    print(f"  {'':<32}{'bets':>6}{'/day':>7}{'win':>6}{'R/bet':>9}{'SE':>7}"
          f"{'total':>8}{'maxDD':>7}{'R/DD':>7}")


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = await list_symbols(sess)
        candles = await load_universe(sess, syms, TF, DAYS)
        if not candles:
            print("no deep history")
            return
        spans = [(cs[-1].t - cs[0].t) / 86400 for cs in candles.values()]
        print(f"PHASE A — the DEPLOYED model, unchanged, on deep history\n"
              f"{len(candles)} symbols · median {statistics.median(spans):.0f} "
              f"days (shortest {min(spans):.0f}, longest {max(spans):.0f}) · "
              f"POI required · grade {MIN_GRADE}+ · target {TRACK_TARGET_R:g}R\n"
              f"one bet per close · nothing tuned, nothing chosen — this is a "
              f"replication")
        sigs = await collect(sess, candles)

    conf = [s for s in sigs if s.kind == "confirmed"]
    early = [s for s in sigs if s.kind == "early"]
    days = statistics.median(spans)

    header("THE DEPLOYED POLICY, over the whole deep window")
    base = row("Min30 CONFIRMED (the rule)", conf, days)
    row("Min30 EARLY", early, days)
    row("everything sent", sigs, days)

    print(f"\n  42-day reference, for comparison only:")
    print(f"  {'Min30 confirmed, 42d full window':<32}{74:>6}{1.8:>7.1f}"
          f"{0.52:>6.0%}{0.509:>+9.3f}{0.172:>7.3f}")
    print(f"  {'Min30 confirmed, 42d held out':<32}{23:>6}{1.1:>7.1f}"
          f"{0.61:>6.0%}{0.801:>+9.3f}{0.315:>7.3f}")
    if base:
        d = base["m"] - 0.509
        print(f"\n  deep vs the 42-day full window: {d:+.3f} R per bet. "
              f"{'A GAIN HERE IS A SURVIVORSHIP WARNING.' if d > 0 else ''}")

    # ---- does the deep pipeline REPRODUCE the number we already have? ----
    #
    # THIS IS THE VALIDATION AND IT COMES BEFORE ANY CONCLUSION. The 42-day
    # study is a known quantity: +0.509 R per bet at a 52% win rate. If the
    # deep loader, run over the SAME trailing 42 days, does not land near that,
    # then the two pipelines differ and every number below is measuring the
    # difference between them rather than the difference between windows.
    #
    # The ladder then shows the decay directly: the same rule read over
    # progressively more history, with nothing else changed.
    header("TRAILING-WINDOW LADDER — the same rule, more history each row")
    now = max(s.t for s in sigs)
    for w in (42, 90, 180, 270, DAYS):
        cut = now - w * 86400
        note = "<-- must match the known +0.509 / 52%" if w == 42 else ""
        row(f"Min30 confirmed · last {w}d", [s for s in conf if s.t >= cut],
            float(w), note)

    # ---- the survivorship check -----------------------------------------
    header("SURVIVORSHIP CHECK — longs against shorts")
    lo = row("Min30 confirmed · LONG", [s for s in conf if s.is_long], days)
    sh = row("Min30 confirmed · SHORT", [s for s in conf if not s.is_long],
             days)
    if lo and sh:
        d = lo["m"] - sh["m"]
        se = (lo["se"] ** 2 + sh["se"] ** 2) ** 0.5
        print(f"\n  long minus short: {d:+.3f} R per bet, {d / se if se else 0:+.1f} SE")
        print(f"  Walking today's most liquid coins backwards a year "
              f"over-samples winners,\n  so a large POSITIVE number here is the "
              f"bias, not the edge. Symmetry is what\n  a real edge looks like.")

    # ---- the regime check ------------------------------------------------
    header("REGIME CHECK — by calendar quarter")
    byq = defaultdict(list)
    for s in conf:
        dt = datetime.fromtimestamp(s.t, timezone.utc)
        byq[f"{dt.year}Q{(dt.month - 1) // 3 + 1}"].append(s)
    for q in sorted(byq):
        row(f"Min30 confirmed · {q}", byq[q], 91.0)
    print(f"\n  Forty-two days is one market mood. An edge that lives in one "
          f"quarter and\n  nowhere else is a season, not an edge.")


if __name__ == "__main__":
    asyncio.run(main())
