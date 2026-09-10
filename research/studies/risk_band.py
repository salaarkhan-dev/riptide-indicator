"""The risk band, against the strict null — and split into its two halves.

THE CLAIM. Min30 confirmed setups whose stop sits 1.2% to 2.6% from the entry
run 41-46% win rates and positive R, while both tails run 25-38% and lose. The
middle half beats the extremes by +0.318 R at +2.7 SE over 333 days, and it now
prints `take` / `marginal` / `skip` on the alert. This study is the test that
could kill it.

WHY THE NULL HAS TO BE THE ROTATION. Risk-to-price is not an independent draw
per signal: it tracks the symbol's volatility regime, which persists for weeks,
so consecutive raids on one symbol carry similar risk. A per-signal shuffle
would therefore be far too lenient, exactly as `feature_batch2.py` established
when its coin-flip null cleared 2 SE only 2% of the time against a textbook
4.6%. Rotating each symbol's risk series in time keeps the persistence, the
distribution and the band sizes intact and destroys only the alignment with R.

AND THE CLAIM MUST BE SPLIT, BECAUSE ONE HALF IS NEARLY TAUTOLOGICAL.

  THE LOWER EDGE — under 1.2% — has a mechanism that is arithmetic rather than
  behavioural. Fee in R is fee_pct / risk_pct, so a tight stop mathematically
  pays more of its R to costs. That half of the finding is close to guaranteed
  and clearing the null there proves little. The interesting question is
  whether it survives WITH FEES TURNED OFF; if it does not, the lower edge is
  the fee and nothing else, which is worth knowing exactly.

  THE UPPER EDGE — over 2.6% — has no such guarantee. Fees are NEGLIGIBLE on a
  wide stop, so nothing arithmetic explains a 25% win rate there. Its only
  story is behavioural: a raid that large was a violent move, and a violent
  move is continuing rather than exhausting. That is the half worth testing and
  the half that would be a genuine finding.

PRE-REGISTERED

  Each edge is tested separately against its own circular-shift null, and each
  is also read one quarter at a time. An edge survives only if it clears p95
  AND holds its sign in at least 3 of 4 quarters.

  The lower edge is additionally re-run at ZERO FEES. Losing its significance
  there does not kill it — it identifies it as the fee, which is a real effect
  a reader still pays. Keeping it would mean something beyond cost.

  EXPECTATION: the lower edge clears with fees and collapses without them; the
  upper edge is the coin toss and I do not have a prior on it. Recorded before
  the first number.

    PYTHONPATH=. RIPTIDE_MIN_GRADE=B RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/risk_band.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import random                                           # noqa: E402
import statistics                                       # noqa: E402
from collections import defaultdict                     # noqa: E402
from datetime import datetime, timezone                 # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import CFG, TRACK_TARGET_R          # noqa: E402
from riptide.engine import grade_of, run_engine         # noqa: E402
from riptide.exchange import fetch_candles, list_symbols  # noqa: E402
from riptide.trend import di_at, direction_at, poi_at   # noqa: E402
from research.deep import load_universe                 # noqa: E402
from research.harness import mean_se, simulate          # noqa: E402

DAYS = 333
LO, HI = 1.2, 2.6       # the deployed band, fixed in advance
SHIFTS = 300


class Sig:
    __slots__ = ("sym", "t", "risk", "r", "r0")


async def collect(sess, candles):
    """SENT confirmed signals, scored with fees and again without them."""
    out = []
    for sym, cs in candles.items():
        try:
            setups = run_engine(sym, cs, CFG)
        except Exception:
            continue
        idx = {c.t: i for i, c in enumerate(cs)}
        for x in setups:
            i = idx.get(x.detected_time)
            if i is None or x.entry <= 0 or abs(x.entry - x.stop) <= 0:
                continue
            o = simulate(cs, i, x.entry, x.stop, x.is_long,
                         target_r=TRACK_TARGET_R)
            if not o.filled or o.exit_bar is None:
                continue
            z = simulate(cs, i, x.entry, x.stop, x.is_long,
                         target_r=TRACK_TARGET_R, fee_pct=0.0)
            w = x.detected_time
            poi = await poi_at(sess, sym, w, x.stop, x.is_long, fetch_candles)
            if not (True if poi is None else bool(poi)):
                continue
            d = await direction_at(sess, sym, w, fetch_candles)
            di = await di_at(sess, sym, w, fetch_candles)
            if grade_of(False, True, d or 0, x.is_long, di or 0)[0] not in "AB":
                continue
            s = Sig()
            s.sym, s.t = sym, w
            s.risk = 100 * abs(x.entry - x.stop) / x.entry
            s.r, s.r0 = o.r, z.r
            out.append(s)
    return out


def bets(sigs, zero=False):
    g = defaultdict(list)
    for s in sigs:
        g[s.t].append(s.r0 if zero else s.r)
    return [statistics.fmean(v) for v in g.values()]


def contrast(sigs, keep, risk_of, zero=False):
    """R per bet inside the kept set against outside it, as a z."""
    a = bets([s for s in sigs if keep(risk_of(s))], zero)
    b = bets([s for s in sigs if not keep(risk_of(s))], zero)
    if len(a) < 20 or len(b) < 20:
        return None
    ma, sa = mean_se(a)
    mb, sb = mean_se(b)
    se = (sa ** 2 + sb ** 2) ** 0.5
    return dict(na=len(a), nb=len(b), ma=ma, mb=mb, d=ma - mb, se=se,
                wa=sum(1 for r in a if r > 0) / len(a),
                wb=sum(1 for r in b if r > 0) / len(b),
                z=(ma - mb) / se if se else 0.0)


def circular_null(sigs, keep, zero=False, seeds=SHIFTS):
    """|z| when each symbol's RISK series is rotated in time against its R.

    Same risks, same order, same band sizes, same persistence — only the pairing
    with the outcome is destroyed. Anything this produces is what a variable
    shaped like risk-to-price can manufacture against an outcome it cannot know.
    """
    bysym = defaultdict(list)
    for s in sorted(sigs, key=lambda z: z.t):
        bysym[s.sym].append(s)
    out = []
    for k in range(seeds):
        rnd = random.Random(5100 + k)
        rot = {}
        for group in bysym.values():
            if len(group) < 2:
                continue
            j = rnd.randrange(len(group))
            for i, s in enumerate(group):
                rot[id(s)] = group[(i + j) % len(group)].risk
        sub = [s for s in sigs if id(s) in rot]
        got = contrast(sub, keep, lambda s: rot[id(s)], zero)
        if got:
            out.append(abs(got["z"]))
    return sorted(out)


def report(name, sigs, keep, zero=False):
    real = contrast(sigs, keep, lambda s: s.risk, zero)
    if not real:
        print(f"\n{name}: too few")
        return
    null = circular_null(sigs, keep, zero)
    p95 = null[int(0.95 * (len(null) - 1))] if null else float("nan")
    tag = "  (ZERO FEES)" if zero else ""
    print(f"\n{name}{tag}")
    print(f"  in band   {real['na']:>4} bets  {real['wa']:>3.0%} win  "
          f"{real['ma']:>+7.3f} R      out {real['nb']:>4} bets  "
          f"{real['wb']:>3.0%} win  {real['mb']:>+7.3f} R")
    print(f"  difference {real['d']:>+8.3f}   real |z| {abs(real['z']):>5.2f}"
          f"   null p95 {p95:>5.2f}   null max {null[-1]:>5.2f}"
          f"   {'CLEARS' if abs(real['z']) >= p95 else 'does not clear'}")
    byq = defaultdict(list)
    for s in sigs:
        d = datetime.fromtimestamp(s.t, timezone.utc)
        byq[f"{d.year}Q{(d.month - 1) // 3 + 1}"].append(s)
    signs = []
    cells = []
    for q in sorted(byq):
        g = contrast(byq[q], keep, lambda s: s.risk, zero)
        cells.append(f"{q} {g['d']:>+6.3f}" if g else f"{q}  thin ")
        if g:
            signs.append(g["d"] > 0)
    agree = max(sum(signs), len(signs) - sum(signs)) if signs else 0
    print(f"  by quarter  " + "   ".join(cells)
          + f"   -> sign holds {agree} of {len(signs)}")


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = await list_symbols(sess)
        candles = await load_universe(sess, syms, "Min30", DAYS)
        sigs = await collect(sess, candles)

    print(f"THE RISK BAND AGAINST THE STRICT NULL\n{len(sigs)} Min30 confirmed "
          f"signals · {DAYS} days · band {LO}%-{HI}% · {SHIFTS} rotations\n"
          f"the null rotates each SYMBOL'S OWN risk series in time, keeping its "
          f"persistence\nand the band sizes and destroying only the pairing "
          f"with the outcome")

    report("THE WHOLE BAND — 1.2%-2.6% against both tails",
           sigs, lambda r: LO <= r <= HI)
    report("UPPER EDGE ONLY — at or under 2.6% against over 2.6% "
           "(no fee explanation)", sigs, lambda r: r <= HI)
    report("LOWER EDGE ONLY — at or over 1.2% against under 1.2% "
           "(the fee half)", sigs, lambda r: r >= LO)
    report("LOWER EDGE ONLY — at or over 1.2% against under 1.2%",
           sigs, lambda r: r >= LO, zero=True)

    print(f"\nPRE-REGISTERED: clear p95 AND hold the sign in 3 of 4 quarters. "
          f"The lower edge\nlosing its significance at zero fees identifies it "
          f"as the fee — still real, but\nnot a fact about the market.")


if __name__ == "__main__":
    asyncio.run(main())
