"""DOES A SLOPPY POOL MAKE A BAD SIGNAL? Pool width, re-asked on 333 days.

WHERE THIS CAME FROM. Looking at the reference indicator and Riptide side by
side on BTC 30m, the reference's live pools are tight horizontal shelves and
Riptide's are visibly wider bands. The observation that followed was specific
and mechanical, and it is the hypothesis this study tests:

    "their live liquidity is on top and ours is on the bottom going with the
     market direction, causing early long alerts and if I take it goes more
     down"

That is a claim about SLOPE masquerading as width. A genuine pool is price
coming back to the same level twice. If the cap on pool width is loose enough,
two pivots on a descending staircase — 76,700 then 76,560 — are inside it and
get called one pool. Raiding that "level" is just price continuing down, the
structure shift that follows is noise, and the long it produces is a
counter-trend bet on a trend that has not finished.

MEASURED FIRST, BECAUSE THE PREMISE HAS TO BE TRUE BEFORE THE TEST IS WORTH
RUNNING. On 5 symbols of Min30, Riptide pool width in ATR:

    p50 0.000   p75 0.055   p90 0.243   p95 0.365   p99 0.754   max 3.283

    13% of ALL pools are wider than the reference's 0.2 ATR cap
    40% of the STILL-LIVE, UNRAIDED pools are

The second number is the one that matters and it is not the first. Live pools
are disproportionately the wide ones, which is exactly what the mechanism
predicts: a tight real level gets raided quickly and clears off the chart,
while a wide band that no single move can take sits there being drawn. So the
chart in front of a person at any moment is enriched in the sloppy pools, far
beyond their 13% share of the population.

WHAT IS ALREADY KNOWN, AND WHY IT DOES NOT CLOSE THIS.

  `zones.py` measured pool span as item 7 and got "spread +0.175, unreadable"
  against an MDE of 0.350 — on 594 confirmed trades. Half the noise floor. That
  is not a negative result, it is an absent one.

  `pivot_tune.py` swept `max_cluster_span_atr` at 0.50 / 0.80 / 1.20 and found
  nothing. The reference's 0.2 is BELOW the bottom of that grid, so the tight
  end was never reached.

  The whole reference configuration was run against Riptide's over 41.6 days
  and came in 0.071 R behind at 1.4 SE — indistinguishable. But that compared
  SETUPS, and a pool that is never raided produces no setup at all. A change
  that only affects which pools are DRAWN is invisible to that comparison by
  construction. "Indistinguishable in R" and "wrong on the chart" are both able
  to be true, and here they may both be.

  None of the three asked the question conditioned on SIGNAL TYPE, and the
  observation above is specifically about EARLY alerts.

This is `entry_zones.py` → `entry_deep.py` again: a correctly designed study
whose only fault was its sample, re-run on the deep window where the error bar
is small enough to see something. That re-run turned two "unreadable" leaders
into the two worst rows on the board at -5.0 and -4.7 SE.

──────────────────────────────────────────────────────────────────────────────
PRE-REGISTERED, BEFORE THE FIRST NUMBER

  PRIMARY. R per signal of pools NARROWER than the reference's 0.2 ATR cap
  against pools WIDER than it — in-band against out-of-band, never against the
  pool that contains them — reported for EARLY and CONFIRMED separately,
  at 2 SE. Early is the arm the observation is about.

  SECONDARY, AND IT IS THE DIRECTIONAL HALF OF THE CLAIM. The mechanism says a
  wide pool is a staircase, so raiding it is continuation and the signal it
  produces fights the prevailing move. If that is right, the damage should be
  concentrated in signals that DISAGREE with the higher-timeframe trend, and a
  wide pool inside the trend should be much less harmful. Reported as the
  four-cell interaction. A width effect that is the same size in both trend
  cells is a width effect, not the staircase mechanism.

  THE CONTROL THAT MATTERS MOST HERE, and it is stop size. Riptide's stop sits
  at the raid extreme, so a wider pool means a deeper raid means a WIDER STOP,
  and wider stops score better in R for a purely mechanical reason the project
  has already documented: the fee is charged as fee_pct / risk_pct, so a wide
  stop dilutes it. Any width effect must therefore be re-read inside stop-size
  terciles, or it is measuring the fee. `harness.risk_terciles` exists for
  exactly this and it is why this study cannot be run as a one-line bucket.

  BOTH HALVES OF THE WINDOW, sign and magnitude, because that is the bar every
  filter here is held to and twenty-one of them failed it.

  WHAT WOULD FALSIFY IT. Narrow pools failing to beat wide ones at 2 SE on the
  early stream; or the gap vanishing inside stop-size terciles; or the effect
  being as large on trend-agreeing signals as on trend-disagreeing ones, which
  would mean the staircase story is wrong even if the number survives.

  EXPECTATION, recorded so it cannot be revised. I expect a real effect on
  EARLY and little or nothing on confirmed, because an early signal has no
  structure shift to validate the pool and is therefore the one that a fake
  level can fool. I expect roughly half of whatever effect appears to survive
  the stop-size control. And I expect the trend interaction to be the weakest
  of the three panels, because the trend axis is already inside the grade.

  If narrow beats wide on early at 2 SE, holds in both halves, survives the
  stop-size control AND concentrates in trend-disagreeing signals, that is the
  first entry-side finding this project has had and it is a two-character
  config change.

    PYTHONPATH=. RIPTIDE_MIN_GRADE=B RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/pool_span.py

──────────────────────────────────────────────────────────────────────────────
RESULT, 13 Sep 2026 — THE HYPOTHESIS IS WRONG, AND IT IS WRONG IN SIGN.

9116 A/B signals, 103 symbols, 333 days, Min30. 29% come from a pool wider than
the reference's cap, so there was no shortage of rows to see it with.

  ON EARLY — the arm the observation was specifically about — WIDE POOLS ARE
  MILDLY BETTER, NOT WORSE:

      pool <  0.2 ATR   +0.000   n 5549
      pool >= 0.2 ATR   +0.028   n 2160      diff -0.028   |z| 0.9

  Not significant, and pointing the opposite way to the prediction. Both halves
  of the window agree on that wrong sign (-0.034 and -0.021), which is the
  two-halves check passing in the direction that kills the idea rather than
  rescuing it.

  THE STOP-SIZE CONTROL WAS THE ONE I EXPECTED TO EAT HALF THE EFFECT, and
  there is nothing for it to eat. All three terciles show wide pools ahead by
  a similar margin (-0.035, -0.025, -0.048). So this is not the fee denominator
  in a costume; there is simply no effect of the predicted kind.

  WHAT CAPPING WOULD ACTUALLY DO, and this is the number that settles it:

      early       keeps 72%   R/sig +0.008 -> +0.000   total  +63.7 ->   +2.2
      confirmed   keeps 64%   R/sig +0.018 -> +0.042   total  +25.7 ->  +37.9

  On the early stream a 0.2 ATR cap destroys 97% of the total R. That is the
  textbook profile of a filter deleting winners, and it is why this file prints
  both columns.

  CONFIRMED LEANS THE OTHER WAY and it does not survive inspection. Tight beats
  wide by +0.066 at |z| 1.0, and capping would raise total R from +25.7 to
  +37.9 — tempting. But the band breakdown is not monotone: 0.20-0.40 ATR is
  the worst band on the board (-0.090, |z| 2.3) while 0.40+ is the BEST (+0.251
  on 99 rows). A real property of pool geometry does not improve again past the
  band that is supposedly too wide. That shape is noise, the |z| 2.3 is one
  of eight bands looked at, and confirmed was not the hypothesis anyway.

A DESIGN FLAW IN THIS STUDY, AND IT IS MINE. The staircase panel — the one
that was supposed to test the MECHANISM rather than its symptom — returned
"too few (0 / 0)" on the trend-fighting row. The reason is structural and I
should have seen it while writing the file: `grade_of` only returns A or B when
the signal AGREES with the higher-timeframe trend, so gating on A/B leaves
exactly zero trend-fighting signals to compare against. The panel could never
have produced a number. Answering it needs `require_ab=False`, the route
`poi_tf.collect` already takes for precisely this reason.

AND THE OBSERVATION THAT STARTED THIS IS NOT DEAD — IT WAS AIMED AT THE WRONG
AXIS, PARTLY BY ME. The chart it came from reads "Trend: BUY" in the corner
while price falls on the 30m. So the signal AGREED with the Hour8 trend and
fought the immediate local move. Every arm above is about HTF trend agreement,
which was constant at 100% by construction. LOCAL direction against HTF trend
is a different question and this study does not touch it.

WHAT THIS CLOSES. Pool width as a predictor of early-signal quality, on 9116
signals with the error bar small enough to have seen it: it is not there, it is
mildly reversed, it holds that reversal in both halves and in all three stop
terciles, and acting on it would cost 97% of the early stream's total R. The
visual complaint that prompted it is real and separately measured — 40% of
still-live unraided pools exceed the reference cap — but a pool being ugly on
the chart and a pool making a bad trade turn out to be different things.
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
import statistics                                       # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import CFG, TRACK_TARGET_R          # noqa: E402
from riptide.engine import atr_series, grade_of, run_engine  # noqa: E402
from riptide.exchange import fetch_candles, list_symbols  # noqa: E402
from riptide.trend import di_at, direction_at, poi_at   # noqa: E402
from research.deep import load_universe                 # noqa: E402
from research.harness import mean_se, simulate          # noqa: E402

DAYS = 333
INTERVAL = "Min30"
# The reference indicator's "Pivot H/Ls Maximum Range by X ATR". Riptide ships
# max_cluster_span_atr = 0.80, four times looser. This is the cut, and it is
# fixed here because it comes from the reference panel rather than from this
# data — there is no threshold search anywhere in this file.
REF_CAP = 0.2


class Row:
    __slots__ = ("sym", "t", "kind", "is_long", "r", "filled", "risk_pct",
                 "span_atr", "trend_ok", "half")


async def collect(sess, candles):
    """Every A/B signal with its pool width recorded. Same gates as entry_deep."""
    rows = []
    for sym, cs in candles.items():
        early = []
        try:
            setups = run_engine(sym, cs, CFG, early_out=early)
        except Exception:
            continue
        idx = {c.t: i for i, c in enumerate(cs)}
        atr = atr_series(cs, CFG.atr_len)
        for kind, batch in (("confirmed", setups), ("early", early)):
            for x in batch:
                i = idx.get(x.detected_time)
                if i is None or x.entry <= 0 or abs(x.entry - x.stop) <= 0:
                    continue
                a = atr[i] if i < len(atr) else 0.0
                if not a:
                    continue
                w = x.detected_time
                poi = await poi_at(sess, sym, w, x.stop, x.is_long,
                                   fetch_candles)
                if not (True if poi is None else bool(poi)):
                    continue
                d = await direction_at(sess, sym, w, fetch_candles)
                di = await di_at(sess, sym, w, fetch_candles)
                if grade_of(kind == "early", True, d or 0, x.is_long,
                            di or 0)[0] not in "AB":
                    continue
                o = simulate(cs, i, x.entry, x.stop, x.is_long,
                             target_r=TRACK_TARGET_R)
                z = Row()
                z.sym, z.t, z.kind, z.is_long = sym, w, kind, bool(x.is_long)
                z.r, z.filled = o.r, o.filled
                z.risk_pct = 100 * abs(x.entry - x.stop) / x.entry
                z.span_atr = x.span / a
                # Does the signal agree with the higher-timeframe trend? The
                # staircase mechanism says a wide pool is continuation, so the
                # signal it produces should fight the prevailing move.
                z.trend_ok = None if not d else ((d > 0) == z.is_long)
                rows.append(z)
    return rows


def band(rows, lo, hi):
    return [z for z in rows if lo <= z.span_atr < hi]


def gap(label, a, b, note=""):
    """In-band against OUT-of-band. Never a subset against its own pool."""
    if len(a) < 25 or len(b) < 25:
        print(f"  {label:<42} too few  ({len(a)} / {len(b)})")
        return None
    ma, sa = mean_se([z.r for z in a])
    mb, sb = mean_se([z.r for z in b])
    se = (sa ** 2 + sb ** 2) ** 0.5
    z = (ma - mb) / se if se else 0.0
    print(f"  {label:<42}{ma:>+8.3f}{len(a):>7}  vs{mb:>+8.3f}{len(b):>7}"
          f"   diff {ma - mb:>+6.3f}  |z| {abs(z):>4.1f}"
          + ("  SEPARATES" if abs(z) >= 2 else "") + note)
    return ma - mb, z


def panel(title, rows):
    print(f"\n{'=' * 104}\n{title}\n{'=' * 104}")
    if len(rows) < 60:
        print("  too few rows")
        return
    print(f"  {'':<42}{'R/sig':>8}{'n':>7}    {'R/sig':>8}{'n':>7}")
    tight = [z for z in rows if z.span_atr < REF_CAP]
    wide = [z for z in rows if z.span_atr >= REF_CAP]
    gap(f"pool < {REF_CAP} ATR (ref cap)  vs  >= {REF_CAP}", tight, wide)

    print(f"\n  by width band, each against everything else:")
    edges = [(0.0, 0.05), (0.05, 0.2), (0.2, 0.4), (0.4, 9.9)]
    for lo, hi in edges:
        inb = band(rows, lo, hi)
        out = [z for z in rows if not (lo <= z.span_atr < hi)]
        gap(f"  {lo:.2f} - {hi:.2f} ATR", inb, out)


def control_panel(rows):
    """The stop-size control. A wider pool means a deeper raid means a wider
    stop, and wider stops score better in R because the fee is fee/risk_pct."""
    print(f"\n{'=' * 104}\nTHE STOP-SIZE CONTROL — is width just the fee "
          f"denominator?\n{'=' * 104}")
    f = [z for z in rows if z.filled]
    if len(f) < 90:
        print("  too few")
        return
    qs = sorted(z.risk_pct for z in f)
    a, b = qs[len(qs) // 3], qs[2 * len(qs) // 3]
    print(f"  stop terciles at {a:.2f}% and {b:.2f}% of price")
    for lab, sub in (("tight stops", [z for z in f if z.risk_pct < a]),
                     ("mid stops", [z for z in f if a <= z.risk_pct < b]),
                     ("wide stops", [z for z in f if z.risk_pct >= b])):
        gap(f"  {lab}: pool < {REF_CAP} vs >=",
            [z for z in sub if z.span_atr < REF_CAP],
            [z for z in sub if z.span_atr >= REF_CAP])
    print("\n  the width effect must hold INSIDE each tercile. if it only")
    print("  appears across them, it is the fee denominator wearing a costume.")


def trend_panel(rows):
    print(f"\n{'=' * 104}\nTHE STAIRCASE TEST — does width hurt most AGAINST "
          f"the trend?\n{'=' * 104}")
    known = [z for z in rows if z.trend_ok is not None]
    if len(known) < 120:
        print("  too few with a known trend")
        return
    for lab, sub in (("signal AGREES with HTF trend",
                      [z for z in known if z.trend_ok]),
                     ("signal FIGHTS the HTF trend",
                      [z for z in known if not z.trend_ok])):
        gap(f"  {lab}",
            [z for z in sub if z.span_atr < REF_CAP],
            [z for z in sub if z.span_atr >= REF_CAP])
    print("\n  the mechanism predicts a BIGGER gap on the fighting row. equal")
    print("  gaps mean width matters but the staircase story does not.")


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = await list_symbols(sess)
        candles = await load_universe(sess, syms, INTERVAL, DAYS)
        rows = await collect(sess, candles)

    rows.sort(key=lambda z: z.t)
    mid = rows[len(rows) // 2].t
    for z in rows:
        z.half = 0 if z.t <= mid else 1

    spans = sorted(z.span_atr for z in rows)
    def q(p):
        return spans[int(p * (len(spans) - 1))] if spans else 0.0

    print("DOES A SLOPPY POOL MAKE A BAD SIGNAL")
    print(f"{len(rows)} A/B signals, {len(candles)} symbols, {DAYS} days, "
          f"{INTERVAL}. cap under test: {REF_CAP} ATR (the reference's).")
    print(f"\n  pool width in ATR:  p50 {q(.5):.3f}   p75 {q(.75):.3f}   "
          f"p90 {q(.9):.3f}   p95 {q(.95):.3f}   p99 {q(.99):.3f}")
    over = sum(1 for z in rows if z.span_atr >= REF_CAP)
    print(f"  {over} of {len(rows)} signals ({over / len(rows):.0%}) come from "
          f"a pool wider than the reference would allow.")

    for kind in ("early", "confirmed"):
        panel(f"{kind.upper()} SIGNALS — the arm the observation is about"
              if kind == "early" else "CONFIRMED SIGNALS",
              [z for z in rows if z.kind == kind])

    early = [z for z in rows if z.kind == "early"]
    print(f"\n{'=' * 104}\nBOTH HALVES OF THE WINDOW — early stream\n{'=' * 104}")
    for h in (0, 1):
        sub = [z for z in early if z.half == h]
        gap(f"  half {h + 1}: pool < {REF_CAP} vs >=",
            [z for z in sub if z.span_atr < REF_CAP],
            [z for z in sub if z.span_atr >= REF_CAP])
    print("\n  an effect in one half only is a non-result. that is the bar")
    print("  twenty-one entry filters failed.")

    control_panel(early)
    trend_panel(early)

    print(f"\n{'=' * 104}\nWHAT IT WOULD COST — capping the pool at "
          f"{REF_CAP} ATR\n{'=' * 104}")
    for kind in ("early", "confirmed"):
        sub = [z for z in rows if z.kind == kind]
        keep = [z for z in sub if z.span_atr < REF_CAP]
        if not sub:
            continue
        mk, _ = mean_se([z.r for z in keep]) if keep else (0.0, 0.0)
        ma, _ = mean_se([z.r for z in sub])
        print(f"  {kind:<12}keeps {len(keep):>5} of {len(sub):>5} "
              f"({len(keep) / len(sub):.0%})   R/sig {ma:+.3f} -> {mk:+.3f}"
              f"   total {sum(z.r for z in sub):>+8.1f} -> "
              f"{sum(z.r for z in keep):>+8.1f}")
    print("\n  a filter that raises R per signal while cutting total R is")
    print("  deleting winners. read both columns, never just the first.")


if __name__ == "__main__":
    asyncio.run(main())
