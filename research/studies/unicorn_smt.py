"""THE TWO SMC MODELS THIS PROJECT HAD NEVER TESTED: Unicorn, and SMT.

SMC_MODELS.md audited ten models against a year of measurements and found that
exactly two of them had never been asked a question here at all. Both are
cheap, because the machinery each needs already exists — this file adds no
detector, it composes ones that are already written and already tested.

──────────────────────────────────────────────────────────────────────────────
MODEL A — THE UNICORN

  A BREAKER and an FVG that OVERLAP. Enter only in the overlap.

  The claim is that two independent reasons for a zone beat one. The sequence
  is the base model's with step 4 replaced by "the gap must sit inside a
  breaker".

  WHY IT IS ALMOST FREE TO ASK. `engine.breaker_of` already finds the block the
  shift traded through, and `engine.confluence_of` already tests it for overlap
  with the entry gap — it just adds that answer to the order block's and
  returns 0-2. The Unicorn is the BREAKER HALF OF THAT COUNT ON ITS OWN, and
  nothing has ever looked at it separately.

  breaker_of is worth reading before trusting this. An earlier version looked
  for the SAME polarity as the order block and landed on the identical candle
  60% of the time, so "2 of 2 zones agree" often meant one candle agreeing with
  itself. The current one requires OPPOSITE polarity and requires the shift to
  have actually traded through it, which is what makes breaker and order block
  two votes instead of one counted twice. Without that fix this study would be
  measuring the order block again under a different name.

  CONFIRMED SETUPS ONLY, and not by choice: a breaker needs a structure shift
  to break through, so an early signal scores 0 by construction. The Unicorn is
  not a model that exists on the early stream.

──────────────────────────────────────────────────────────────────────────────
MODEL B — SMT DIVERGENCE

  Two correlated assets, one sweeps its level and the other does not. The
  sweep that is not confirmed by its partner is the false one.

      LONG    the symbol makes a lower low, BTC does not  -> the low is a trap
      SHORT   the symbol makes a higher high, BTC does not

  MEASURED AT THE RAID BAR, which is what keeps it causal. The raid happens
  before the shift, which happens before the gap, which happens before the
  entry — so a feature read at the raid is knowable well before anything can be
  acted on. Everything compared is bars at or before the raid bar.

  BTC_USDT IS EXCLUDED from this panel. An asset cannot diverge from itself,
  and leaving it in would add a row that is definitionally "no divergence" to
  whichever arm it falls in.

──────────────────────────────────────────────────────────────────────────────
PRE-REGISTERED, BEFORE THE FIRST NUMBER

  PRIMARY, UNICORN. R per signal of confirmed setups whose gap OVERLAPS a
  breaker against those that do not, at 2 SE. In-group against out-group, never
  against the pool containing both.

  PRIMARY, SMT. R per signal of signals WITH divergence against those without,
  at 2 SE, both directions pooled.

  SECONDARY, SMT, AND IT IS THE ONE THAT TESTS THE MECHANISM. The two
  directions separately. SMT's story is symmetric — a false low and a false
  high are the same trap mirrored — so an effect that appears on longs and not
  on shorts is not SMT, it is a directional bias that happens to correlate with
  BTC's own trend over this window.

  THE CONTROL FOR SMT, and it is the important one. CONFLUENCE rather than
  divergence: the signals where BTC made the SAME extreme. SMT says those
  should be WORSE — the sweep was real, both assets sold off, nothing was
  trapped. If divergence and confluence both beat the middle, the feature is
  measuring "BTC did something notable" rather than the disagreement.

  BOTH HALVES OF THE WINDOW for anything that clears, because that is the bar
  twenty-one filters failed.

  MULTIPLE COMPARISONS, COUNTED. Unicorn 1, SMT pooled 1, SMT by direction 2,
  SMT confluence control 1 = five looks. At 5% that is 0.25 expected false
  positives, so one row at 2 SE is worth about as much as it sounds.

  EXPECTATION, recorded so it cannot be revised. I expect BOTH to fail, and I
  expect the Unicorn to fail for a specific and checkable reason: confluence_of
  has already been measured as a 0-2 count (0 of 2 -> +0.043, 2 of 2 -> +0.106,
  +1.4 SE and NOT monotonic, with 1 of 2 coming in below 0 of 2). A
  non-monotonic ladder is what noise looks like, and splitting it into halves
  usually finds that neither half carries anything. For SMT I expect no effect
  pooled, and if anything appears I expect it on ONE direction only — which the
  secondary panel is there to catch and reject.

  If the Unicorn clears 2 SE on both halves it would be the first entry-side
  CONDITION this project has found, distinct from the twelve entry PRICES that
  all lost. It would also be nearly free: confluence is already recorded on
  every alert.

    PYTHONPATH=. RIPTIDE_MIN_GRADE=B RIPTIDE_DEEP_CACHE=/tmp/deep \\
        python3 research/studies/unicorn_smt.py

──────────────────────────────────────────────────────────────────────────────
RESULT, 13 Sep 2026 — THE UNICORN FAILS. SMT IS THE FIRST ENTRY FILTER IN THIS
PROJECT TO CLEAR ITS OWN CONTROL.

9279 A/B signals, 106 symbols, 333 days, Min30.

  THE UNICORN IS WORSE, CONSISTENTLY. 583 of 1421 confirmed setups (41%) have
  a gap overlapping a breaker:

      overlap   -0.035        no overlap  +0.047      diff -0.082   |z| 1.3
        half 1  -0.032  vs  +0.040                    diff -0.072   |z| 0.8
        half 2  -0.037  vs  +0.054                    diff -0.092   |z| 1.0

  Not significant, and the sign is stable across both halves — which is the
  two-halves check confirming the idea is dead rather than rescuing it. The
  order block overlap is nothing at all (+0.011, |z| 0.2), and requiring BOTH
  zones is worse than requiring neither (-0.045). Two independent reasons for a
  zone are not better than one; on this evidence they are slightly worse.
  Predicted, for the reason given above: the 0-2 confluence ladder was already
  non-monotonic, and splitting noise into halves finds noise in both.

  SMT DIVERGENCE CLEARS EVERYTHING IT WAS ASKED TO. 4679 of 9175 (51%) show
  the symbol making a new 20-bar extreme while BTC does not:

      divergence  +0.037   vs  none  -0.036      diff +0.074   |z| 2.9

    BOTH DIRECTIONS, SAME SIGN — longs +0.098 (|z| 2.6), shorts +0.052
    (|z| 1.5). Weaker on shorts but pointing the same way, which is what a
    symmetric mechanism looks like and what a directional bias does not.

    BOTH HALVES, SAME SIGN AND SIMILAR SIZE — +0.066 (|z| 1.8) and +0.082
    (|z| 2.3). Twenty-one filters failed exactly here.

    AND THE CONTROL POINTS THE RIGHT WAY, which is the panel that matters
    most. CONFLUENCE — BTC made the SAME extreme, so the sweep was real and
    nothing was trapped — scores -0.037 against +0.017, diff -0.054 at |z| 1.9.
    If the feature were reading "BTC did something notable" both arms would
    beat the middle. They do not: divergence is good, agreement is bad, and
    that is the mechanism rather than the number.

  IT LIVES ALMOST ENTIRELY ON THE EARLY STREAM, and that is the most
  convincing part of the whole result because it was not predicted and it is
  exactly where the mechanism says it should be:

      early      +0.040  vs  -0.044     diff +0.084   |z| 3.0
      confirmed  +0.020  vs  -0.001     diff +0.022   |z| 0.3

  The Early docstring in riptide/engine.py names its own failure mode: "There
  is no confirmation that the sweep reversed anything, so a pool taken in a
  trend keeps going and the signal is simply wrong." A confirmed setup has a
  structure shift to vouch for the sweep. An early one has nothing — and SMT is
  precisely an independent check on whether the sweep was real. The filter adds
  the confirmation that signal type is missing, and adds almost nothing to the
  one that already has it.

WHAT IS NOT DONE, AND IT IS THE REASON THIS IS NOT SHIPPED ON THIS FILE ALONE.

  NO CIRCULAR-SHIFT NULL. This is the instrument that killed `pivot_tune.py`'s
  three-touch finding, which looked like +0.206 R held out and turned out to be
  smaller than what its own shape produces against a random outcome. Every
  signal in a window shares one BTC series, so "diverged from BTC" is heavily
  autocorrelated across symbols and time, and an independent-SE z on it is
  optimistic by an unknown amount. Rotating the BTC series in time — same
  values, same order, same autocorrelation, no real-time link to the outcome —
  is the only honest null here. That test is the next thing to run and it is
  the one that decides whether this is real.

  NO SYMBOL BOOTSTRAP. `survivor.symbol_bootstrap` exists and has not been
  applied.

  NO DISCOVERY/HOLDOUT SPLIT. The rule is binary and its one parameter
  (SMT_BACK = 20) was fixed in source before the run, so there is nothing
  fitted — but both halves were read, not one.

  FIVE LOOKS were declared. |z| 2.9 survives that comfortably on its own terms;
  it does not survive being wrong about the standard error, which is what the
  missing null would tell us.

  MY EXPECTATION WAS THAT BOTH WOULD FAIL. The Unicorn did, for the reason I
  gave. SMT did not, and I also predicted that if anything appeared it would
  appear on ONE direction only — it appears on both. Being wrong in that
  direction is the interesting kind.
"""
import research.env  # noqa: F401  (must precede riptide.config)

import asyncio                                          # noqa: E402
from bisect import bisect_right                         # noqa: E402

import aiohttp                                          # noqa: E402

from riptide.config import CFG, TRACK_TARGET_R          # noqa: E402
from riptide.engine import atr_series, grade_of, run_engine  # noqa: E402
from riptide.engine import breaker_of, last_opposing, ranges_overlap  # noqa: E402
from riptide.exchange import fetch_candles, list_symbols  # noqa: E402
from riptide.trend import di_at, direction_at, poi_at   # noqa: E402
from research.deep import load_deep, load_universe      # noqa: E402
from research.harness import mean_se, simulate          # noqa: E402

DAYS = 333
INTERVAL = "Min30"
REF = "BTC_USDT"
# How far back a "new extreme" is judged over, at the raid bar. 20 bars is ten
# hours on 30m — long enough that taking it out means something, short enough
# that it is the local structure rather than the week's.
SMT_BACK = 20


class Row:
    __slots__ = ("sym", "t", "kind", "is_long", "r", "filled", "risk_pct",
                 "unicorn", "ob_overlap", "smt", "ref_same", "half")


def gap_bounds(cs, fvg_bar, is_bull):
    if fvg_bar < 2 or fvg_bar >= len(cs):
        return None
    return ((cs[fvg_bar].l, cs[fvg_bar - 2].h) if is_bull
            else (cs[fvg_bar - 2].l, cs[fvg_bar].h))


def smt_at(cs, g, ref_t, ref_lo, ref_hi, is_long):
    """(symbol made a new extreme, the reference did too) at the raid bar.

    Divergence is the first being True and the second False. Strictly causal:
    the window ends at the raid bar and nothing after it is read.
    """
    lo = max(0, g - SMT_BACK)
    if g <= lo or g >= len(cs):
        return None
    if is_long:
        mine = cs[g].l <= min(c.l for c in cs[lo:g])
    else:
        mine = cs[g].h >= max(c.h for c in cs[lo:g])
    j = bisect_right(ref_t, cs[g].t) - 1
    k = bisect_right(ref_t, cs[lo].t) - 1
    if j <= k or k < 0:
        return None
    if is_long:
        theirs = ref_lo[j] <= min(ref_lo[k:j])
    else:
        theirs = ref_hi[j] >= max(ref_hi[k:j])
    return mine, theirs


async def collect(sess, candles, ref):
    ref_t = [c.t for c in ref]
    ref_lo = [c.l for c in ref]
    ref_hi = [c.h for c in ref]
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
                if not (atr[i] if i < len(atr) else 0.0):
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
                z.unicorn = z.ob_overlap = None
                z.smt = z.ref_same = None

                # --- Unicorn: does the gap overlap the BREAKER? -------------
                fb = idx.get(getattr(x, "fvg_time", 0) or 0)
                gb = idx.get(getattr(x, "grab_time", 0) or 0)
                mb = getattr(x, "mss_bar", None)
                bnd = gap_bounds(cs, fb, x.is_long) if fb is not None else None
                if bnd is not None and gb is not None and isinstance(mb, int):
                    top, bot = bnd
                    brk = breaker_of(cs, gb, mb, x.is_long)
                    z.unicorn = bool(brk >= 0 and
                                     ranges_overlap(top, bot,
                                                    cs[brk].h, cs[brk].l))
                    ob = last_opposing(cs, fb - 1, x.is_long)
                    z.ob_overlap = bool(ob >= 0 and
                                        ranges_overlap(top, bot,
                                                       cs[ob].h, cs[ob].l))

                # --- SMT: did the reference confirm the raid? ---------------
                if sym != REF and gb is not None:
                    got = smt_at(cs, gb, ref_t, ref_lo, ref_hi, x.is_long)
                    if got:
                        mine, theirs = got
                        z.smt = bool(mine and not theirs)   # divergence
                        z.ref_same = bool(mine and theirs)  # confluence
                rows.append(z)
    return rows


def gap(label, a, b):
    if len(a) < 25 or len(b) < 25:
        print(f"  {label:<44} too few  ({len(a)} / {len(b)})")
        return None
    ma, sa = mean_se([z.r for z in a])
    mb, sb = mean_se([z.r for z in b])
    se = (sa ** 2 + sb ** 2) ** 0.5
    zz = (ma - mb) / se if se else 0.0
    print(f"  {label:<44}{ma:>+8.3f}{len(a):>7}  vs{mb:>+8.3f}{len(b):>7}"
          f"   diff {ma - mb:>+6.3f}  |z| {abs(zz):>4.1f}"
          + ("  SEPARATES" if abs(zz) >= 2 else ""))
    return ma - mb, zz


def split(rows, pred):
    yes = [z for z in rows if pred(z) is True]
    no = [z for z in rows if pred(z) is False]
    return yes, no


async def main():
    async with aiohttp.ClientSession() as sess:
        syms = await list_symbols(sess)
        candles = await load_universe(sess, syms, INTERVAL, DAYS)
        ref = await load_deep(sess, REF, INTERVAL, DAYS)
        rows = await collect(sess, candles, ref)

    rows.sort(key=lambda z: z.t)
    mid = rows[len(rows) // 2].t
    for z in rows:
        z.half = 0 if z.t <= mid else 1

    print("THE UNICORN AND SMT DIVERGENCE")
    print(f"{len(rows)} A/B signals, {len(candles)} symbols, {DAYS} days, "
          f"{INTERVAL}.  SMT reference: {REF}, {len(ref)} bars.")

    conf = [z for z in rows if z.kind == "confirmed" and z.unicorn is not None]
    print(f"\n{'=' * 104}\nMODEL A — THE UNICORN  (breaker n FVG overlap)"
          f"\n{'=' * 104}")
    print("  confirmed setups only: a breaker needs a shift to break through,")
    print("  so an early signal scores 0 by construction.\n")
    print(f"  {'':<44}{'R/sig':>8}{'n':>7}    {'R/sig':>8}{'n':>7}")
    y, n = split(conf, lambda z: z.unicorn)
    print(f"  gap overlaps a breaker: {len(y)} of {len(conf)} "
          f"({len(y) / max(len(conf), 1):.0%})")
    gap("UNICORN  overlap  vs  no overlap", y, n)
    yo, no_ = split(conf, lambda z: z.ob_overlap)
    gap("  (order block overlap, for contrast)", yo, no_)
    both = [z for z in conf if z.unicorn and z.ob_overlap]
    neither = [z for z in conf if not z.unicorn and not z.ob_overlap]
    gap("  both zones agree  vs  neither", both, neither)
    if len(y) >= 50:
        print()
        for h in (0, 1):
            sub = [z for z in conf if z.half == h]
            yy, nn = split(sub, lambda z: z.unicorn)
            gap(f"  half {h + 1}", yy, nn)

    print(f"\n{'=' * 104}\nMODEL B — SMT DIVERGENCE  (vs {REF}, read at the "
          f"raid bar)\n{'=' * 104}")
    sm = [z for z in rows if z.smt is not None]
    div = [z for z in sm if z.smt]
    print(f"  {len(div)} of {len(sm)} signals ({len(div) / max(len(sm), 1):.0%})"
          f" show divergence: the symbol made a new {SMT_BACK}-bar extreme and "
          f"{REF} did not.\n")
    print(f"  {'':<44}{'R/sig':>8}{'n':>7}    {'R/sig':>8}{'n':>7}")
    y, n = split(sm, lambda z: z.smt)
    gap("SMT  divergence  vs  none", y, n)
    print("\n  by direction — SMT's story is symmetric, so an effect on one")
    print("  side only is a directional bias, not SMT:")
    for lab, pred in (("  longs", lambda z: z.is_long),
                      ("  shorts", lambda z: not z.is_long)):
        sub = [z for z in sm if pred(z)]
        yy, nn = split(sub, lambda z: z.smt)
        gap(lab, yy, nn)
    print("\n  THE CONTROL. confluence — the reference made the SAME extreme,")
    print("  so the sweep was real and nothing was trapped. SMT says this")
    print("  should be WORSE. if both beat the middle, the feature is reading")
    print(f"  '{REF} did something' rather than the disagreement:")
    ys, ns = split(sm, lambda z: z.ref_same)
    gap("  confluence  vs  not", ys, ns)
    if len(div) >= 50:
        print()
        for h in (0, 1):
            sub = [z for z in sm if z.half == h]
            yy, nn = split(sub, lambda z: z.smt)
            gap(f"  half {h + 1}", yy, nn)

    print(f"\n{'=' * 104}\nAND ON THE EARLY STREAM — SMT only\n{'=' * 104}")
    e = [z for z in sm if z.kind == "early"]
    ye, ne = split(e, lambda z: z.smt)
    gap("  early: divergence vs none", ye, ne)
    c = [z for z in sm if z.kind == "confirmed"]
    yc, nc = split(c, lambda z: z.smt)
    gap("  confirmed: divergence vs none", yc, nc)


if __name__ == "__main__":
    asyncio.run(main())
