"""WHERE to enter, not whether to. Eleven entries on the same raids.

EVERY TEST IN THIS PROJECT SO FAR HAS BEEN A FILTER — twenty-one attempts in
MEASUREMENTS.md, thirty-one more in `feature_batch.py`, all asking "should this
signal be taken". One survivor. This asks something structurally different:
given the raid, WHERE should the entry sit?

The loser anatomy is why it is worth asking. Not one loser failed to go green
first; 62% reached 0.5R and 26% reached a full 1R before dying. A filter cannot
reach those — at entry they looked exactly like the winners, because they WERE
winners for a while. But a better price gives the same trade more room, and
that is a lever a filter does not have.

THE ENTRIES, all on the same signals with the SAME STOP at the raid extreme:

    market at the FVG close     no waiting, taker in — the "just take it" floor
    FVG near edge               what the bot does today
    FVG mid / far edge          deeper into the same gap
    Fib 0.5 / 0.618 / 0.786     of the RECLAIM LEG — raid extreme to leg high
    order block                 last opposite-close candle before the leg,
                                at its extreme and at its midpoint
    volumetric OB               the same candle, but only when it traded above
                                its own recent median
    the swept level             retest of the pool that was raided

FIBONACCI IS HERE BECAUSE THE FIRST ATTEMPT AT IT WAS BROKEN. `feature_batch.py`
measured entry position against the raid leg and found 97% of entries on one
side of 50% — a degenerate split that divided nothing. The fault was the anchor:
it measured from the raid extreme to the SWEPT LEVEL, and the FVG forms on the
reclaim by construction, so almost every entry lands past halfway. Anchoring on
the reclaim leg — raid extreme to the high the bounce actually made — is the
anchor a trader draws, and it makes the levels distinct.

THE METRIC IS R PER SIGNAL, NOT R PER FILL, AND THIS IS THE WHOLE TRAP.

A deeper entry fills less often, and it fills only on the trades that came back
to it — which is a selection, not an edge. Scored per FILL, a deep entry looks
wonderful because the trades that ran away without it are invisible. Scored per
SIGNAL, with an unfilled signal counting as zero, the missed opportunity is
paid for. This project already has the shape of that trade recorded: Min15
entries fill 85% of the time against 45% for Min30, at the same hit rate.

Risk% is printed beside every row for the same reason. A deeper entry sits
closer to the stop, so its risk shrinks and the fee — charged as a fraction of
risk — grows in R terms. That is the dominant cost in every measurement here
and it is exactly what a "better price" quietly buys with.

PRE-REGISTERED, BEFORE THE FIRST NUMBER

  PRIMARY   R PER SIGNAL must beat the deployed FVG-edge entry on the HELD-OUT
            half at 2 SE. Per-fill numbers are reported but decide nothing.

  SECONDARY Fill rate, risk%, and win rate for each, since a rule that trades
            a third as often is a different product even when its R matches.

  EXPECTATION: the deep entries win per fill and lose per signal. That is what
  the fill-rate arithmetic predicts and what the Min15/Min30 result already
  showed. If any entry beats the current one PER SIGNAL, that is a genuine
  finding and the first structural improvement this project would have made.

    PYTHONPATH=. python3 research/studies/entry_zones.py
"""
import research.env                                     # noqa: F401  MUST be first

import statistics                                       # noqa: E402

from riptide.config import TRACK_FILL_BARS, TRACK_TARGET_R  # noqa: E402
from research.data import atr_at, load_sync             # noqa: E402
from research.harness import mean_se, simulate, simulate_market  # noqa: E402

TGT = TRACK_TARGET_R
# A stop closer than this to the entry is not a trade, it is a rounding error.
# The swept-level entry makes the point: its stop sits at the raid extreme,
# which by definition is only the raid's OVERSHOOT away from the level — often
# a fraction of a tick. R = profit/risk then explodes, and the first run of
# this study printed -11565162145 for exactly that reason. The same floor was
# needed in the LEZ work for the same arithmetic.
MIN_RISK_ATR = 0.25
# One MEXC round trip, maker in and maker out. Printed as a column because the
# whole result turns out to be this number divided by risk.
FEE_PCT = 0.04


def legs(r):
    """(raid_extreme, leg_peak, grab_bar) for the reclaim leg, or None.

    The leg is from the bar that took the pool to the bar the gap formed on.
    Its extreme is where the raid ended and its peak is how far the bounce got
    — the two points a trader anchors a retracement between.
    """
    cs = r.candles
    idx = {c.t: i for i, c in enumerate(cs)}
    g = idx.get(getattr(r.signal, "grab_time", 0) or r.signal.sweep_time)
    if g is None or g >= r.bar:
        return None
    seg = cs[g:r.bar + 1]
    if r.signal.is_long:
        return min(c.l for c in seg), max(c.h for c in seg), g
    return max(c.h for c in seg), min(c.l for c in seg), g


def order_block(r, volumetric=False):
    """The last opposite-close candle before the reclaim leg took off.

    For a long that is the last DOWN candle — the one supply came from — and
    the classic entry is its extreme or its midpoint. `volumetric` additionally
    requires it to have traded above the median of the 20 bars before it, which
    is the only thing "volumetric OB" adds that is well defined.
    """
    got = legs(r)
    if not got:
        return None
    _, _, g = got
    cs = r.candles
    for k in range(r.bar, g - 1, -1):
        down = cs[k].c < cs[k].o
        if down != r.signal.is_long:          # opposite-colour candle
            continue
        if volumetric:
            lo = max(0, k - 20)
            prev = [cs[j].v for j in range(lo, k) if cs[j].v > 0]
            if len(prev) < 10 or cs[k].v <= statistics.median(prev):
                continue
        return cs[k]
    return None


def entries(r):
    """{name: entry price} for one signal. None where the zone does not exist."""
    sg, cs = r.signal, r.candles
    out = {"FVG near edge (deployed)": sg.entry}
    got = legs(r)
    if not got:
        return out
    ext, peak, _ = got
    span = abs(peak - ext)
    sgn = 1 if sg.is_long else -1

    # The gap itself, deeper.
    if r.bar - 2 >= 0:
        a = cs[r.bar - 2].h if sg.is_long else cs[r.bar - 2].l
        b = cs[r.bar].l if sg.is_long else cs[r.bar].h
        out["FVG mid"] = (a + b) / 2.0
        out["FVG far edge"] = a

    # Fibonacci of the RECLAIM LEG — the anchor the first attempt got wrong.
    for f in (0.5, 0.618, 0.786):
        out[f"Fib {f:g} of the leg"] = peak - sgn * f * span

    for lab, vol in (("order block extreme", False),
                     ("volumetric OB extreme", True)):
        ob = order_block(r, vol)
        if ob is not None:
            out[lab] = ob.h if sg.is_long else ob.l
            out[lab.replace("extreme", "mid")] = (ob.h + ob.l) / 2.0

    lv = getattr(sg, "level", 0.0)
    if lv:
        out["the swept level"] = lv
    return out


def score_limit(r, px):
    """A LIMIT at `px`, same stop, same target. Unfilled returns None."""
    sg = r.signal
    if px is None or px <= 0:
        return None
    risk = abs(px - sg.stop)
    if risk <= 0 or not ((px > sg.stop) if sg.is_long else (px < sg.stop)):
        return None                        # entry on the wrong side of the stop
    a = atr_at(r)
    if a and risk < MIN_RISK_ATR * a:
        return None                        # see MIN_RISK_ATR
    o = simulate(r.candles, r.bar, px, sg.stop, sg.is_long, target_r=TGT,
                 fill_bars=TRACK_FILL_BARS)
    if o.exit_bar is None and o.filled:
        return None                        # ran out of candles, not an outcome
    return o, 100 * risk / px


def retest_reject(r, zone_lo, zone_hi):
    """Wait for price to come back INTO the zone and be REJECTED, then enter
    at that bar's close, market.

    "Rejected" is operationalised the way it is drawn: the bar trades into the
    zone, closes back OUT of it on the correct side, and the wick that did the
    testing is longer than the body. That is the candle a chart reader points
    at, and it is the only version of "rejection" that is checkable from OHLC.

    A market entry, because a rejection is only known once the bar closes —
    there is no limit to rest, and pretending otherwise would be lookahead.
    """
    sg, cs = r.signal, r.candles
    for k in range(r.bar + 1, min(r.bar + 1 + TRACK_FILL_BARS, len(cs))):
        c = cs[k]
        touched = c.l <= zone_hi if sg.is_long else c.h >= zone_lo
        if not touched:
            continue
        out = c.c > zone_hi if sg.is_long else c.c < zone_lo
        wick = (c.o - c.l if sg.is_long else c.h - c.o)
        body = abs(c.c - c.o)
        if out and wick > body:
            return k, c.c
        # Price entered the zone and did NOT reject: the setup is gone, and
        # waiting further would be waiting for a different trade.
        if (c.c <= zone_lo) if sg.is_long else (c.c >= zone_hi):
            return None
    return None


def row(lab, got, n_signals):
    """One entry rule. R PER SIGNAL is the column that decides."""
    # score_limit returns None for an unusable entry, so the Nones are
    # dropped before unpacking rather than inside it.
    ok = [x for x in got if x is not None]
    if len(ok) < 40:
        print(f"  {lab:<26}{len(ok):>7}   too few")
        return None
    filled = [(o, rk) for o, rk in ok if o.filled]
    if len(filled) < 30:
        print(f"  {lab:<26}{len(ok):>7}   too few fills")
        return None
    # An unfilled signal is a zero, not an absence. That is the whole point.
    per_signal = [(o.r if o.filled else 0.0) for o, _ in ok]
    m, se = mean_se(per_signal)
    pf, _ = mean_se([o.r for o, _ in filled])
    win = sum(1 for o, _ in filled if o.r > 0) / len(filled)
    risk = statistics.fmean(rk for _, rk in filled)
    print(f"  {lab:<26}{len(ok):>7}{len(filled) / len(ok):>7.0%}{risk:>7.2f}%"
          f"{2 * FEE_PCT / risk:>8.3f}{win:>6.0%}{pf:>+9.3f}{m:>+11.3f}"
          f"{se:>7.3f}")
    return m, se


def panel(title, rows):
    print(f"\n{title}   n={len(rows)}")
    print(f"  {'entry':<26}{'n':>7}{'fill':>7}{'risk':>8}{'fee R':>8}"
          f"{'win':>6}{'R/fill':>9}{'R/SIGNAL':>11}{'SE':>7}")
    # Market at the close, as a floor: no waiting, no missed fills, taker in.
    mk = []
    for r in rows:
        o = simulate_market(r.candles, r.bar, r.candles[r.bar].c,
                            r.signal.stop, r.signal.is_long, target_r=TGT)
        if o is not None:
            mk.append((o, 100 * abs(r.candles[r.bar].c - r.signal.stop)
                       / r.candles[r.bar].c))
    row("market at the FVG close", mk, len(rows))

    # Retest + rejection of the FVG, as asked. Not a price but a RULE: it is
    # part location and part confirmation, so it is scored beside the prices
    # rather than among them.
    rr = []
    for r in rows:
        if r.bar - 2 < 0:
            continue
        a = r.candles[r.bar - 2].h if r.signal.is_long else r.candles[r.bar - 2].l
        b = r.candles[r.bar].l if r.signal.is_long else r.candles[r.bar].h
        lo, hi = min(a, b), max(a, b)
        got_ = retest_reject(r, lo, hi)
        if got_ is None:
            # No rejection came. The signal still happened, so it counts as a
            # zero rather than vanishing — the same rule as an unfilled limit.
            rr.append((None, 0.0))
            continue
        k, px = got_
        risk = abs(px - r.signal.stop)
        a_ = atr_at(r)
        if risk <= 0 or (a_ and risk < MIN_RISK_ATR * a_):
            rr.append((None, 0.0))
            continue
        o = simulate_market(r.candles, k, px, r.signal.stop, r.signal.is_long,
                            target_r=TGT)
        rr.append((o, 100 * risk / px) if o is not None else (None, 0.0))
    ok = [x for x in rr if x[0] is not None]
    if len(ok) >= 40:
        per = [(o.r if o else 0.0) for o, _ in rr]
        m, se = mean_se(per)
        pf, _ = mean_se([o.r for o, _ in ok])
        win = sum(1 for o, _ in ok if o.r > 0) / len(ok)
        rk = statistics.fmean(x[1] for x in ok)
        print(f"  {'retest + rejection':<26}{len(rr):>7}{len(ok) / len(rr):>7.0%}"
              f"{rk:>7.2f}%{2 * FEE_PCT / rk:>8.3f}{win:>6.0%}{pf:>+9.3f}"
              f"{m:>+11.3f}{se:>7.3f}")

    names, per = [], {}
    for r in rows:
        for k, px in entries(r).items():
            per.setdefault(k, []).append(score_limit(r, px))
    base = None
    for k in ("FVG near edge (deployed)", "FVG mid", "FVG far edge",
              "Fib 0.5 of the leg", "Fib 0.618 of the leg",
              "Fib 0.786 of the leg", "order block extreme", "order block mid",
              "volumetric OB extreme", "volumetric OB mid",
              "the swept level"):
        if k not in per:
            continue
        got = row(k, per[k], len(rows))
        if k.startswith("FVG near"):
            base = got
        elif got and base:
            d = got[0] - base[0]
            dse = (got[1] ** 2 + base[1] ** 2) ** 0.5
            names.append((k, d, dse))
    if names:
        print(f"\n  vs the deployed entry, on R PER SIGNAL:")
        for k, d, dse in sorted(names, key=lambda x: -x[1]):
            print(f"    {k:<26}{d:>+9.3f}{dse:>7.3f}"
                  f"   {d / dse if dse else 0:+.1f} SE")


def main():
    import asyncio
    import aiohttp
    from riptide.exchange import list_symbols

    async def _s():
        async with aiohttp.ClientSession() as sess:
            return await list_symbols(sess)
    syms = asyncio.run(_s()) or None
    every = load_sync(symbols=syms)
    early = [r for r in every if r.kind == "early"]
    conf = [r for r in every if r.kind == "confirmed"]
    print(f"WHERE TO ENTER — same raids, same stop, eleven entries\n"
          f"{len(early)} early · {len(conf)} confirmed · target {TGT:g}R\n"
          f"R PER SIGNAL counts an unfilled signal as ZERO. That is the "
          f"honest column;\nR/fill flatters any entry price never reached by "
          f"the trades that ran away.")
    panel("EARLY — all", early)
    panel("EARLY — HELD OUT (older half), the pre-registered one",
          [r for r in early if r.split_window])
    panel("CONFIRMED — all", conf)


if __name__ == "__main__":
    main()
