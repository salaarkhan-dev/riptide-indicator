"""DOES THE STRUCTURE INDICATOR'S TREND ADD ANYTHING TO A RIPTIDE SIGNAL?

THE QUESTION. riptide-structure.pine and riptide-indicator.pine can sit on the
same chart, and the obvious way to make them work together is to let the
structure supply the bias and Riptide supply the trade. This asks whether that
is worth doing or merely looks tidy.

Riptide already has a bias gate: a SuperTrend(14, 5.0) AND a DI reading, both
on Hour8, ANDed inside grade_of. That is an INDICATOR-derived bias. The
structure indicator's trend is a different animal — it flips on a change of
character and on nothing else, so it is STRUCTURAL. Whether that difference
carries information is the whole question.

THE PRIOR IS BAD AND IT IS WORTH SAYING SO FIRST. Twenty-one entry filters have
been tested in this project and one survived. There is also a specific reason
to expect redundancy here: Riptide's own MSS and the structure's BoS are close
to the same event, so the "new" bias may already be inside the grade. The
control panel below measures exactly that rather than assuming it.

Two things argue the other way. The one filter that did survive — the
higher-timeframe point of interest — was STRUCTURAL rather than
indicator-derived, which is the same category as this. And SMT divergence
recently cleared a circular-shift null at about 60/40, so the well is not dry.

THE STRUCTURE IS READ ON THE SIGNAL'S OWN TIMEFRAME, Min30, because that is
what a person running both indicators on one chart would see. A higher-timeframe
variant is a different study and is not this one.

NO LOOKAHEAD. ta.pivothigh(left, right) does not exist until `right` bars after
the pivot, so the trend at bar i is rebuilt here from pivots CONFIRMED by bar i
only. Getting that wrong would hand the filter the future and produce exactly
the kind of result this file exists to avoid.

──────────────────────────────────────────────────────────────────────────────
PRE-REGISTERED, BEFORE THE FIRST NUMBER

  PRIMARY. On the SHIPPED pool (grade A/B), R per signal where the structural
  trend AGREES with the signal's direction against where it DISAGREES —
  in-group versus out-group, never against the pool containing both — at 2 SE.
  The A/B pool is the primary because a gate can only be applied to signals
  that are being sent; the C/D arm below is secondary and exploratory.

  THE CONTROL THAT MATTERS MOST IS REDUNDANCY. How often does the structural
  trend agree with the SuperTrend/DI bias the grade already uses? If the two
  agree on nearly every signal, any effect here is the existing gate wearing a
  different hat, and the honest reading is "no new information" even if the
  number looks good.

  MEASURING REDUNDANCY NEEDS THE WHOLE POOL, NOT THE SHIPPED ONE. Grade A/B
  REQUIRES the SuperTrend and the DI to agree with the direction, so on the
  A/B pool the incumbent bias agrees on 100% of rows by construction and a
  redundancy number computed there would be a tautology. This runs
  collect(require_ab=False) and keeps the C/D rows as a labelled arm, which
  buys two things: an honest agreement rate, and the one question the A/B pool
  cannot ask — does the structural trend RESCUE the signals the existing gate
  throws away?

  CIRCULAR-SHIFT NULL. The trend is a state that persists for many bars, so
  consecutive signals on a symbol share it and an independent-SE z is
  optimistic. Rotating each symbol's trend series in time preserves its run
  lengths and its up/down balance while breaking the link to the outcome. This
  is the instrument that killed pivot_tune.py's three-touch finding.

  SYMBOL BOOTSTRAP, 2000 draws. A difference carried by a few symbols is not a
  property of the market.

  BOTH HALVES of the window, sign and size.

  WHAT WOULD FALSIFY IT. Separation inside the null's p95; or a bootstrap whose
  5th percentile straddles zero; or agreement with the existing gate so high
  that there is nothing new being measured.

  EXPECTATION, recorded so it cannot be revised. I expect it to fail, and I
  expect it to fail on REDUNDANCY rather than on significance — that the
  structural trend agrees with the SuperTrend/DI bias on 80%+ of signals and
  the remaining disagreements are too few to read. If it does separate, I
  expect the effect to be larger on EARLY signals than confirmed ones, for the
  same reason SMT was: an early signal has no structure shift of its own to
  vouch for it, so an external read of structure is the confirmation it lacks.

    PYTHONPATH=. RIPTIDE_MIN_GRADE=B RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/lit_trend.py
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import random                                           # noqa: E402
import statistics                                       # noqa: E402
from bisect import bisect_right                         # noqa: E402
from collections import defaultdict                     # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import BAR_SECONDS                  # noqa: E402
from research.deep import load_universe                 # noqa: E402
from research.harness import mean_se                    # noqa: E402
from research.studies.poi_tf import DAY, DAYS, H8       # noqa: E402
from research.studies.poi_tf import collect, context, universe  # noqa: E402

INTERVAL = "Min30"
# riptide-structure.pine defaults: ChoCh period 30 with the Fast Trend Detector
# on, which makes the left arm int(30/2).
LONG_P = 30
LEFT_P = LONG_P // 2
SHIFTS = 300
BOOT = 2000


def trend_series(cs):
    """The structure indicator's Trend state, per bar, strictly causal.

    Ports the ChoCh block of riptide-structure.pine: inside bars are carried
    forward, pivots are found on that filtered series, the bullish ChoCh level
    tracks the highest pivot high while bearish and only rises while bullish
    (mirrored for the bearish level), and the trend flips when close crosses
    one of them.

    Returns a list of +1 / -1 / 0, one per bar, where the value at bar i uses
    only pivots CONFIRMED by bar i.
    """
    n = len(cs)
    fh, fl = [0.0] * n, [0.0] * n
    rng_hi = rng_lo = None
    for i, c in enumerate(cs):
        inside = False
        if rng_hi is None:
            rng_hi, rng_lo = c.h, c.l
        elif c.h <= rng_hi and c.l >= rng_lo:
            inside = True
        else:
            rng_hi, rng_lo = c.h, c.l
        fh[i] = fh[i - 1] if (inside and i) else c.h
        fl[i] = fl[i - 1] if (inside and i) else c.l

    out = [0] * n
    trend = 0
    bu_p = be_p = 0.0
    for i in range(n):
        # A pivot at bar i-LONG_P is confirmed here: LONG_P bars to its right,
        # LEFT_P to its left. Nothing later than bar i is consulted.
        p = i - LONG_P
        if p - LEFT_P >= 0:
            w = fh[p - LEFT_P:i + 1]
            if w and fh[p] == max(w):
                if trend <= 0:
                    bu_p = fh[p]
                elif fh[p] > bu_p:
                    bu_p = fh[p]
            w = fl[p - LEFT_P:i + 1]
            if w and fl[p] == min(w):
                if trend >= 0:
                    be_p = fl[p]
                elif fl[p] < be_p:
                    be_p = fl[p]
        if bu_p > 0 and be_p > 0:
            # Two separate ifs, not if/elif: the Pine evaluates the bearish
            # block against the trend the bullish block may have just set.
            if cs[i].c > bu_p and trend <= 0:
                trend = 1
            if cs[i].c < be_p and trend >= 0:
                trend = -1
        out[i] = trend
    return out


def gap(label, a, b):
    if len(a) < 25 or len(b) < 25:
        print(f"  {label:<44} too few  ({len(a)} / {len(b)})")
        return None
    ma, sa = mean_se([r for _, r in a])
    mb, sb = mean_se([r for _, r in b])
    se = (sa ** 2 + sb ** 2) ** 0.5
    z = (ma - mb) / se if se else 0.0
    print(f"  {label:<44}{ma:>+8.3f}{len(a):>7}  vs{mb:>+8.3f}{len(b):>7}"
          f"   diff {ma - mb:>+6.3f}  |SE| {abs(z):>4.1f}"
          + ("  SEPARATES" if abs(z) >= 2 else ""))
    return ma - mb, z


def split(rows):
    return ([(s, r) for s, ok, r in rows if ok],
            [(s, r) for s, ok, r in rows if not ok])


def null_test(rows, tr, label):
    """Circular-shift null on one arm. `rows` are (sym, agree, r, bar_index)."""
    got = gap(f"  {label}", *split([(s, ok, r) for s, ok, r, _ in rows]))
    if not got:
        return
    per_sym = defaultdict(list)
    for s, _ok, r, i in rows:
        per_sym[s].append((r, i))
    rnd = random.Random(20260913)
    nulls = []
    for _ in range(SHIFTS):
        x, y = [], []
        for sym, hits in per_sym.items():
            tser = tr[sym][1]
            if len(tser) < 200:
                continue
            off = rnd.randrange(100, len(tser) - 100)
            n = len(tser)
            for r, i in hits:
                v = tser[(i + off) % n]
                if v > 0:
                    x.append(r)
                elif v < 0:
                    y.append(r)
        if len(x) < 25 or len(y) < 25:
            continue
        ma, sa = mean_se(x)
        mb, sb = mean_se(y)
        se = (sa ** 2 + sb ** 2) ** 0.5
        if se:
            nulls.append(abs((ma - mb) / se))
    if nulls:
        nulls.sort()
        p95 = nulls[int(0.95 * (len(nulls) - 1))]
        print(f"    null p95 {p95:.1f}   null max {nulls[-1]:.1f}   "
              f"real {abs(got[1]):.1f}   "
              f"{'CLEARS' if abs(got[1]) > p95 else 'FAILS - inside the null'}")


def bootstrap(rows, label):
    bysym = defaultdict(list)
    for s, ok, r, *_ in rows:
        bysym[s].append((ok, r))
    names = sorted(bysym)
    rnd = random.Random(20260913)
    out = []
    for _ in range(BOOT):
        pick = [rnd.choice(names) for _ in names]
        x = [r for s in pick for ok, r in bysym[s] if ok]
        y = [r for s in pick for ok, r in bysym[s] if not ok]
        if len(x) > 25 and len(y) > 25:
            out.append(statistics.fmean(x) - statistics.fmean(y))
    if not out:
        print(f"  {label:<24} too few")
        return
    out.sort()
    p5 = out[int(0.05 * (len(out) - 1))]
    p95 = out[int(0.95 * (len(out) - 1))]
    print(f"  {label:<24} [{p5:+.3f}, {p95:+.3f}]   "
          f"median {statistics.median(out):+.3f}"
          + ("   all above zero" if p5 > 0 else "   STRADDLES ZERO"))


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = await universe(sess)
        cs = await load_universe(
            sess, syms, INTERVAL, DAYS,
            min_bars=int(0.8 * DAYS * 86400 // BAR_SECONDS[INTERVAL]))
        zday = await context(sess, cs, DAY)
        z8h = await context(sess, cs, H8)
        # require_ab=False: the C/D rows are kept as a LABEL so the redundancy
        # control has something to measure. See the docstring.
        rows = await collect(sess, cs, zday, z8h, interval=INTERVAL,
                             require_ab=False)
    tr = {s: ([c.t for c in cs[s]], trend_series(cs[s])) for s in cs}

    data = []
    for t in rows:
        if not t.filled or t.exit_t is None or t.sym not in tr:
            continue
        times, tser = tr[t.sym]
        i = bisect_right(times, t.t) - 1
        if i < 0 or tser[i] == 0:
            continue
        data.append((t.sym, (tser[i] > 0) == t.is_long, t.r, t.kind, t.t,
                     t.trend_ok, i))

    ab = [d for d in data if d[5]]
    cd = [d for d in data if not d[5]]
    print("THE STRUCTURE INDICATOR'S TREND AS A GATE ON RIPTIDE SIGNALS")
    print(f"{len(data)} filled signals with a known structural trend, "
          f"{len(cs)} symbols, {DAYS} days, {INTERVAL}.")
    print(f"{len(ab)} of them are grade A/B — the shipped pool, where the "
          f"SuperTrend/DI bias already agrees.\n")
    print(f"  {'':<44}{'R/sig':>8}{'n':>7}    {'R/sig':>8}{'n':>7}")

    base = [(s, ok, r) for s, ok, r, *_ in ab]
    gap("PRIMARY  A/B, structure agrees vs disagrees", *split(base))
    for kind in ("early", "confirmed"):
        sub = [(s, ok, r) for s, ok, r, k, *_ in ab if k == kind]
        gap(f"  {kind}", *split(sub))

    print(f"\n{'=' * 100}\nTHE REDUNDANCY CONTROL — is this the gate we "
          f"already have?\n{'=' * 100}")
    same = sum(1 for d in data if d[1] == d[5])
    print(f"  the structural trend and the SuperTrend/DI bias give the same "
          f"answer on\n  {same} of {len(data)} signals "
          f"({100 * same / len(data):.0f}%), measured on the WHOLE pool.")
    print("  a high number here means any effect above is the existing gate")
    print("  wearing a different hat, whatever its significance.\n")
    print(f"  the {len(cd)} signals the existing gate THROWS AWAY (grade C/D) "
          f"— does structure rescue them?")
    gap("    C/D, structure agrees vs disagrees",
        *split([(s, ok, r) for s, ok, r, *_ in cd]))

    print(f"\n{'=' * 100}\nBOTH HALVES — A/B pool\n{'=' * 100}")
    ts = sorted(d[4] for d in ab)
    mid = ts[len(ts) // 2] if ts else 0
    for lab, sel in (("half 1", lambda t: t <= mid),
                     ("half 2", lambda t: t > mid)):
        sub = [(s, ok, r) for s, ok, r, _, tt, *_ in ab if sel(tt)]
        gap(f"  {lab}", *split(sub))

    print(f"\n{'=' * 100}\nCIRCULAR-SHIFT NULL — {SHIFTS} rotations of the "
          f"trend series\n{'=' * 100}")
    print("  rotating the trend keeps its run lengths and its up/down balance")
    print("  and breaks only the link to the outcome.")
    null_test([(s, ok, r, i) for s, ok, r, _, _, _, i in ab], tr, "A/B")
    null_test([(s, ok, r, i) for s, ok, r, _, _, _, i in cd], tr, "C/D")

    print(f"\n{'=' * 100}\nSYMBOL BOOTSTRAP — {BOOT} draws\n{'=' * 100}")
    bootstrap(ab, "A/B")
    bootstrap(cd, "C/D")


if __name__ == "__main__":
    asyncio.run(main())
