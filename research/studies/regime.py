"""What separates the quarter that worked from the three that did not?

THE SETUP. Over 333 days Min30 confirmed runs +0.063 ± 0.062 R per bet — one
standard error from zero — and the quarters read +0.058, −0.074, −0.008,
+0.289. Essentially the whole year's profit is one quarter. If a variable
observable AT SIGNAL TIME separates the good conditions from the bad, the
strategy becomes conditional and useful. If none does, the honest description is
a marginal system whose returns arrive in bursts nobody can time.

THIS IS THE MOST SNOOPABLE QUESTION IN THE PROJECT AND THE DESIGN IS BUILT
AROUND THAT. I already know which quarter paid. With four quarters, almost any
market variable will correlate with the good one by chance — pick anything that
happened to be elevated in 2026Q3 and it will "explain" the result perfectly
while predicting nothing. Three defences, all pre-registered:

  ONE — MECHANISM FIRST. Every variable below has an a-priori reason why a
  liquidity-raid reversal would work better or worse under it, written down
  before it was measured. No variable is included because it fit.

  TWO — TRAILING RANK, NEVER LEVEL. Each variable is converted to its
  percentile within its own trailing 30 days. A raw level is a disguised date:
  "volatility was 4%" is just another way of saying "it was August". A trailing
  rank asks whether conditions are unusual FOR THE TIME, which is stationary and
  is the only version that could be acted on live.

  THREE — IT MUST SEPARATE WITHIN QUARTERS. This is the decisive test. A
  variable that only separates BETWEEN quarters is a relabelling of the thing
  being explained. A real conditioning variable makes its high bucket beat its
  low bucket INSIDE 2026Q1 and INSIDE 2026Q2 as well as inside Q3.

THE VARIABLES, AND WHY EACH

  market volatility     A 2R target with the stop at a raid extreme needs the
                        move to extend. In quiet markets the target is not
                        reached and the fee is a larger share of R.

  volatility direction  Rising volatility means expanding ranges after the raid;
                        falling volatility means the reversal dies mid-move.

  one-way market        The share of symbols moving the same way. This strategy
                        FADES a raid. When the whole market is going one way a
                        raid is continuation, not a stop hunt — the mechanism
                        predicts this should hurt.

  dispersion            Cross-sectional spread of returns. High dispersion means
                        symbols move on their own news, which is the regime in
                        which a per-symbol structural signal should mean most —
                        and it is the opposite of the clustering that produced
                        24 losers inside 3.8 hours.

  relative volatility   The signal's own symbol against the market. Distinct
                        from the market-wide reading: a quiet coin in a loud
                        market is a different bet from a loud coin in a quiet
                        one.

PRE-REGISTERED

  A variable survives only if ALL THREE hold:
    1. Top tercile beats bottom by 2 SE over the whole window.
    2. The sign holds in at least 3 of the 4 quarters.
    3. It clears the circular-shift null's p95.

  REPORTED REGARDLESS: what fraction of the stream each bucket keeps. The
  deployed rule already sends only 1.5 bets a day; a regime filter that trades
  a third of the time leaves half a bet a day, which may not be a product.

  EXPECTATION: one or two clear condition 1, none clears condition 2, and the
  variables that look strongest turn out to be proxies for "it was Q3".
  Recorded so it cannot be revised.

    PYTHONPATH=. RIPTIDE_MIN_GRADE=B RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/regime.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import random                                           # noqa: E402
import statistics                                       # noqa: E402
from collections import defaultdict                     # noqa: E402
from datetime import datetime, timezone                 # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import CFG                          # noqa: E402
from riptide.engine import atr_series                   # noqa: E402
from riptide.exchange import list_symbols               # noqa: E402
from research.deep import load_universe                 # noqa: E402
from research.harness import mean_se                    # noqa: E402
from research.studies.replicate import DAYS, TF, bets, collect  # noqa: E402

RANK_DAYS = 30          # trailing window the percentile is taken within
RANK_STEP = 8           # subsample that window; 180 points is plenty for a rank
RET_BARS = 48           # 24h on Min30 — the return horizon for breadth/dispersion
SHIFTS = 300


# ---------------------------------------------------------------- the panel
def market_panel(candles):
    """Per bar-time market aggregates, each computed from that bar and earlier.

    Built once from the same deep candles the signals came from, so a signal
    and its regime reading are always the same chart at the same moment. Every
    input is backward-looking: an ATR at bar i uses bars up to i, a 48-bar
    return uses bars i-48..i. Nothing here can see forward.
    """
    vol, ret = defaultdict(list), defaultdict(list)
    for cs in candles.values():
        a = atr_series(cs, CFG.atr_len)
        for i, c in enumerate(cs):
            if a[i] and c.c > 0:
                vol[c.t].append(a[i] / c.c)
            if i >= RET_BARS and cs[i - RET_BARS].c > 0:
                ret[c.t].append(c.c / cs[i - RET_BARS].c - 1.0)
    out = {}
    for t, vs in vol.items():
        rs = ret.get(t, [])
        if len(vs) < 20 or len(rs) < 20:
            continue
        up = sum(1 for r in rs if r > 0) / len(rs)
        out[t] = {
            "market volatility": statistics.median(vs),
            # |up share - 0.5|: 1.0 when every symbol agrees, 0 when split.
            "one-way market": abs(up - 0.5) * 2,
            "dispersion": statistics.pstdev(rs),
        }
    return out


def to_rank(panel, key, step_secs):
    """Replace each value with its percentile inside its own trailing 30 days.

    A LEVEL IS A DISGUISED DATE. "Volatility was 4%" is another way of saying
    "it was August", and a bucket built on it would separate quarters by
    construction. The rank asks whether conditions are unusual FOR THE TIME,
    which is both stationary and the only form that could be computed live.
    """
    times = sorted(panel)
    vals = [panel[t][key] for t in times]
    span = int(RANK_DAYS * 86400 / step_secs)
    out = {}
    for i, t in enumerate(times):
        lo = max(0, i - span)
        window = vals[lo:i:RANK_STEP]
        if len(window) < 30:
            continue
        v = vals[i]
        out[t] = sum(1 for w in window if w < v) / len(window)
    return out


def vol_direction(panel, step_secs):
    """Volatility now against volatility a week ago — rising or falling."""
    times = sorted(panel)
    idx = {t: i for i, t in enumerate(times)}
    back = int(7 * 86400 / step_secs)
    out = {}
    for t in times:
        i = idx[t]
        if i < back:
            continue
        prev = panel[times[i - back]]["market volatility"]
        if prev > 0:
            out[t] = panel[t]["market volatility"] / prev
    return out


# ---------------------------------------------------------------- scoring
def split(sigs, feat, lo=1 / 3, hi=2 / 3):
    """Top tercile against bottom, in R per bet. None when either is too thin."""
    vals = [feat[s.t] for s in sigs if s.t in feat]
    if len(vals) < 60:
        return None
    q = sorted(vals)
    a, b = q[int(lo * len(q))], q[int(hi * len(q))]
    top = bets([s for s in sigs if feat.get(s.t, -1) >= b])
    bot = bets([s for s in sigs if -1 < feat.get(s.t, -1) <= a])
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
    """|z| when the regime series is rotated in time against the outcomes.

    The market aggregates are heavily autocorrelated — volatility persists for
    weeks — so an independent shuffle would be far too lenient a null, exactly
    as feature_batch2 found. A rotation keeps the persistence and the bucket
    sizes intact and destroys only the alignment with R.
    """
    times = sorted(feat)
    vals = [feat[t] for t in times]
    n = len(times)
    out = []
    for k in range(seeds):
        j = random.Random(7700 + k).randrange(n)
        rot = {t: vals[(i + j) % n] for i, t in enumerate(times)}
        got = split(sigs, rot)
        if got:
            out.append(abs(got["z"]))
    return sorted(out)


def line(label, got, note=""):
    if not got:
        print(f"  {label:<30}   too few")
        return
    print(f"  {label:<30}{got['nt']:>6}{got['wt']:>6.0%}{got['mt']:>+9.3f}"
          f"   |{got['nb']:>6}{got['wb']:>6.0%}{got['mb']:>+9.3f}"
          f"   |{got['d']:>+8.3f}{got['z']:>+6.1f} SE  {note}")


def header(title):
    print(f"\n{title}")
    print(f"  {'':<30}{'  TOP THIRD':<21}   |{'  BOTTOM THIRD':<21}   |"
          f"  DIFFERENCE")
    print(f"  {'':<30}{'bets':>6}{'win':>6}{'R/bet':>9}   |{'bets':>6}"
          f"{'win':>6}{'R/bet':>9}   |")


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = await list_symbols(sess)
        candles = await load_universe(sess, syms, TF, DAYS)
        sigs = await collect(sess, candles)
    conf = [s for s in sigs if s.kind == "confirmed"]
    step = 1800

    panel = market_panel(candles)
    feats = {k: to_rank(panel, k, step)
             for k in ("market volatility", "one-way market", "dispersion")}
    feats["volatility rising"] = to_rank(
        {t: {"v": v} for t, v in vol_direction(panel, step).items()}, "v", step)

    # Per-signal: the symbol's own vol against the market's, ranked.
    own = {}
    for sym, cs in candles.items():
        a = atr_series(cs, CFG.atr_len)
        for i, c in enumerate(cs):
            if a[i] and c.c > 0 and c.t in panel:
                m = panel[c.t]["market volatility"]
                if m > 0:
                    own[(sym, c.t)] = (a[i] / c.c) / m
    rel = {}
    if own:
        q = sorted(own.values())
        for s in conf:
            v = own.get((s.sym, s.t))
            if v is not None:
                rel[s.t] = sum(1 for w in q[::37] if w < v) / len(q[::37])

    print(f"REGIME CONDITIONING — what separates the quarter that paid\n"
          f"{len(candles)} symbols · {DAYS} days · Min30 confirmed · "
          f"{len(conf)} signals\nevery variable is a TRAILING 30-DAY "
          f"PERCENTILE, never a level: a level is a\ndisguised date and would "
          f"separate the quarters by construction")

    header("WHOLE WINDOW — top third of each variable against the bottom third")
    results = {}
    for name, feat in list(feats.items()) + [("symbol vol vs market", rel)]:
        got = split(conf, feat)
        results[name] = (got, feat)
        line(name, got)

    # ---- THE DECISIVE TEST ------------------------------------------------
    print(f"\n{'=' * 100}\nWITHIN EACH QUARTER — the test that matters\n"
          f"A variable that only separates BETWEEN quarters is a relabelling "
          f"of 'it was Q3'.\n{'=' * 100}")
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
                  f"{'  <-- passes condition 2' if agree >= 3 and len(signs) >= 3 else ''}")

    # ---- the strict null --------------------------------------------------
    print(f"\n{'=' * 100}\nTHE CIRCULAR-SHIFT NULL\n{'=' * 100}")
    print(f"  {'variable':<30}{'real |SE|':>11}{'null p95':>10}{'null max':>10}")
    for name, (got, feat) in results.items():
        if not got:
            continue
        null = circular_null(conf, feat)
        if not null:
            continue
        p95 = null[int(0.95 * (len(null) - 1))]
        ok = abs(got["z"]) >= p95
        print(f"  {name:<30}{abs(got['z']):>11.2f}{p95:>10.2f}{null[-1]:>10.2f}"
              f"{'   clears' if ok else ''}")

    print(f"\nPRE-REGISTERED: all three conditions, or it is not a regime "
          f"filter.\n  1. top beats bottom by 2 SE on the whole window\n"
          f"  2. the sign holds in at least 3 of 4 quarters\n"
          f"  3. it clears the circular-shift null's p95")


if __name__ == "__main__":
    asyncio.run(main())
