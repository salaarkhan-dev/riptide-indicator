"""RSI divergence — the concept extracted from a strategy that does not survive.

THE STRATEGY ITSELF IS NOT MEASURABLE FROM ITS OWN TESTER, and that is settled
by arithmetic rather than opinion. Reported: +213.92%, 64.04% wins, profit
factor 1.561, 89 trades, BTC 15m over ten weeks. What the settings actually say:

  `default_qty_value=2, strategy.fixed` on BTC near 78,000 is a $157,000
  position on $10,000 of capital — 15.7x, and up to 31.4x with `pyramiding=2`.
  The 62.54% max drawdown is that leverage, not the edge.

  The `strategy()` call sets NO COMMISSION AND NO SLIPPAGE. Average profit is
  $240 a trade, which is 0.153% of notional. A MEXC round trip is 0.08% maker
  to taker, 0.12% taker both ways. Charging it:

      shown              +214%   profit factor 1.561
      at 0.08%           +102%   profit factor 1.207
      at 0.12%            +46%   profit factor 1.084

  Two thirds to four fifths of the result is the fee it was not charged. The
  same conclusion this project reached from six other directions.

  IT IS LONG ONLY, over a window in which the equity curve's own shape shows a
  large rally. `Buy and hold` is the one comparison that would settle whether
  that is the strategy or the market — and in the screenshot it is toggled OFF.

  THERE IS NO STOP. `sl_type` defaults to "NONE", so a losing long is held
  until RSI crosses 80 or a bear divergence prints. That is what makes the win
  rate 64%, and the tester says so itself: average win $1,044 against average
  loss $1,192, a ratio of 0.88. Wins are smaller than losses, which is the
  signature of a no-stop system, not a good one.

  The header comments publish different tuned parameters per symbol — GOOGL at
  5/3/1, SPY at 5/3/3 — which is curve fitting stated openly by the author.

SO WHY THIS FILE EXISTS. The strategy is not worth porting. The CONCEPT is
worth one measurement, because it is genuinely untested here and it is not what
was tested before: `context.py` measured RSI EXTENSION at the raid (+0.025,
+0.4 SE, dead). Extension is "RSI is far from 50". DIVERGENCE is "price made a
lower low while RSI made a higher low" — a relationship between two series, not
a level in one. Riptide already computes an RSI and already looks for exactly
the price structure a divergence needs: a raid making a lower low. Nobody has
asked whether the RSI agreed.

PRE-REGISTERED, BEFORE THE FIRST NUMBER

  PRIMARY   Early signals whose raid carried a REGULAR BULLISH divergence for a
            long (bearish for a short) must beat those without, on the HELD-OUT
            half, at 2 SE, and clear a 25-seed placebo floor.

  SECONDARY Hidden divergence, which the author's own defaults leave half
            switched off (`plotHiddenBear=false`) — a tell that it was never
            the point. And a standalone score, for comparability with the four
            indicators already in MEASUREMENTS.md.

  The port keeps the author's parameters exactly: RSI 9, pivots (1 left,
  3 right), and a previous pivot 5 to 60 bars back. Not swept — sweeping the
  parameters of a concept whose own author publishes different ones per symbol
  would be fitting a fit.

  EXPECTATION: null. RSI is the single most-tested oscillator in existence and
  this population has already rejected its level form.

    PYTHONPATH=. python3 research/studies/divergence.py
"""
import research.env                                     # noqa: F401  MUST be first

import random                                           # noqa: E402
import statistics                                       # noqa: E402

from riptide.config import BAR_SECONDS, CFG, INTERVAL   # noqa: E402
from riptide.engine import atr_series, rsi_series       # noqa: E402
from research.data import load_sync                     # noqa: E402
from research.harness import mean_se, simulate_market   # noqa: E402

RSI_LEN, LB_L, LB_R = 9, 1, 3
RANGE_LO, RANGE_HI = 5, 60
WINDOW = CFG.early_max_bars       # how near the signal a divergence must be
SEEDS = 25
FEE = dict(fee_maker=0.02, fee_taker=0.06)
_DIV: dict = {}


def _pivots(vals, left, right, low=True):
    """(confirm_bar, pivot_bar) for pivotlow/pivothigh on a series."""
    out = []
    for j in range(left, len(vals) - right):
        v = vals[j]
        if v is None:
            continue
        w = [vals[k] for k in range(j - left, j + right + 1) if k != j]
        if any(x is None for x in w):
            continue
        if (all(v < x for x in w) if low else all(v > x for x in w)):
            out.append((j + right, j))
    return out


def divergences(cs, rsi_len=RSI_LEN, lb_l=LB_L, lb_r=LB_R):
    """(confirm_bar, is_bull, hidden) for every divergence label.

    Mirrors the Pine: the comparison is against the PREVIOUS oscillator pivot
    (`valuewhen(plFound, osc[lbR], 1)`), the price leg uses the low/high at the
    same pivot bar, and the previous pivot must sit 5 to 60 bars back.

    The signal fires on the CONFIRMING bar. The Pine draws its label at
    `offset=-lbR`, three bars to the left, which is the same visual shift the
    SR-break indicator has: the picture is early, the signal is not.
    """
    osc = rsi_series(cs, rsi_len)
    out = []
    for low_side in (True, False):
        piv = _pivots(osc, lb_l, lb_r, low=low_side)
        for n in range(1, len(piv)):
            (conf, j), (_, pj) = piv[n], piv[n - 1]
            gap = j - pj
            if not (RANGE_LO <= gap <= RANGE_HI):
                continue
            o_now, o_prev = osc[j], osc[pj]
            p_now = cs[j].l if low_side else cs[j].h
            p_prev = cs[pj].l if low_side else cs[pj].h
            if low_side:
                if o_now > o_prev and p_now < p_prev:
                    out.append((conf, True, False))     # regular bullish
                elif o_now < o_prev and p_now > p_prev:
                    out.append((conf, True, True))      # hidden bullish
            else:
                if o_now < o_prev and p_now > p_prev:
                    out.append((conf, False, False))    # regular bearish
                elif o_now > o_prev and p_now < p_prev:
                    out.append((conf, False, True))     # hidden bearish
    return sorted(out)


def divs(r):
    k = id(r.candles)
    if k not in _DIV:
        _DIV[k] = divergences(r.candles)
    return _DIV[k]


def has(r, hidden=False, agree=True):
    """A matching divergence within WINDOW bars at or before the signal bar."""
    want = r.signal.is_long if agree else (not r.signal.is_long)
    for conf, is_bull, hid in divs(r):
        if hid != hidden or is_bull != want:
            continue
        if 0 <= r.bar - conf <= WINDOW:
            return True
    return False


def line(lab, vals):
    if len(vals) < 20:
        print(f"    {lab:<30}{len(vals):>6}   too few")
        return None
    m, se = mean_se(vals)
    w = sum(1 for v in vals if v > 0) / len(vals)
    print(f"    {lab:<30}{len(vals):>6}{w:>7.0%}{m:>+10.3f}{se:>7.3f}")
    return m, se


def placebo(vals, n):
    if n < 20 or n >= len(vals):
        return None
    return statistics.median(
        statistics.fmean(random.Random(880 + s).sample(vals, n))
        for s in range(SEEDS))


def panel(title, rows):
    print(f"\n{title}   n={len(rows)}")
    print(f"    {'':<30}{'n':>6}{'win':>7}{'R/signal':>10}{'SE':>7}")
    allv = [r.r for r in rows]
    line("all signals", allv)
    for lab, pred in (
            ("REGULAR div agreeing", lambda r: has(r, False, True)),
            ("regular div CONTRADICTING", lambda r: has(r, False, False)),
            ("hidden div agreeing", lambda r: has(r, True, True))):
        hit = [r.r for r in rows if pred(r)]
        miss = [r.r for r in rows if not pred(r)]
        a = line(lab, hit)
        if a and len(miss) >= 20:
            mb, sb = mean_se(miss)
            d, dse = a[0] - mb, (a[1] ** 2 + sb ** 2) ** 0.5
            f = placebo(allv, len(hit))
            print(f"    {'  vs the rest':<30}{'':>13}{d:>+10.3f}{dse:>7.3f}"
                  f"   {d / dse if dse else 0:+.1f} SE"
                  + (f"   placebo {f:+.3f}" if f is not None else ""))


def standalone(rows):
    """The divergence as a trade: market at the confirming close, 1.5 ATR stop,
    2R, MEXC fees. Same shape the other four indicators were scored with."""
    print(f"\n{'=' * 72}\nDIVERGENCE AS A TRADE OF ITS OWN — market at the "
          f"confirming close, 2R\n{'=' * 72}")
    seen, out = set(), {"regular": [], "hidden": []}
    horizon = max(1, 48 * 3600 // BAR_SECONDS[INTERVAL])
    for r in rows:
        k = id(r.candles)
        if k in seen:
            continue
        seen.add(k)
        cs = r.candles
        atr = atr_series(cs, CFG.atr_len)
        for conf, is_bull, hid in divs(r):
            a = atr[conf] if conf < len(atr) else 0
            if not a or conf + horizon >= len(cs):
                continue
            e, d = cs[conf].c, 1.5 * atr[conf]
            o = simulate_market(cs, conf, e, e - d if is_bull else e + d,
                                is_bull, target_r=2.0, horizon_bars=horizon,
                                **FEE)
            if o is not None:
                out["hidden" if hid else "regular"].append(o.r)
    print(f"    {'':<30}{'n':>6}{'win':>7}{'R/signal':>10}{'SE':>7}")
    for k, v in out.items():
        line(k, v)


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
    print(f"RSI DIVERGENCE AS A FILTER — the concept, not the strategy\n"
          f"RSI {RSI_LEN} · pivots {LB_L}/{LB_R} · previous pivot {RANGE_LO}-"
          f"{RANGE_HI} bars back · window {WINDOW}\n"
          f"{len(early)} early · {len(conf)} confirmed")
    n = sum(1 for r in early if has(r, False, True))
    print(f"\nCOVERAGE  agreeing regular divergence within {WINDOW} bars: "
          f"{n}/{len(early)} ({n / len(early):.0%})")
    panel("EARLY — all", early)
    panel("EARLY — HELD OUT (older half), the pre-registered one",
          [r for r in early if r.split_window])
    panel("CONFIRMED — all", conf)
    standalone(early)


if __name__ == "__main__":
    main()
