"""An EXACT port of "Support and Resistance Levels with Breaks" (Pine v4).

IT LIVES IN research/ RATHER THAN riptide/ BECAUSE NOTHING IN THE BOT USES IT.
The trendline port sits in `riptide/` only because `watch.py` sends alerts from
it, and one implementation is the point. If this ever ships it moves; until
then a port under research is the honest place for it.

WHAT IT DOES

    highUsePivot = fixnan(pivothigh(15, 15)[1])     last CONFIRMED pivot high
    lowUsePivot  = fixnan(pivotlow (15, 15)[1])     last CONFIRMED pivot low
    osc = 100 * (ema(volume,5) - ema(volume,10)) / ema(volume,10)

    clean break UP    crossover(close, highUsePivot)
                      and not (open - low > close - open)      no big lower tail
                      and osc > 20                             volume expanding
    clean break DOWN  crossunder(close, lowUsePivot)
                      and not (open - close < high - open)     no big upper tail
                      and osc > 20
    "Bull Wick"       crossover  + the big lower tail, VOLUME NOT REQUIRED
    "Bear Wick"       crossunder + the big upper tail, VOLUME NOT REQUIRED

THREE THINGS THE SOURCE DOES THAT ARE WORTH KNOWING BEFORE TRUSTING THE CHART

  THE LINES ARE DRAWN 16 BARS TO THE LEFT OF WHERE THEY BECAME KNOWN.
  `plot(..., offset = -(rightBars + 1))` shifts the drawing back in time. The
  level itself is honest — `pivothigh(15,15)` is na until 15 bars after the
  pivot prints, and the extra `[1]` costs one more — so a level is knowable
  only at pivot_bar + 16. But on the chart it appears to stretch back to the
  pivot itself, which makes every break look like a break of a level that was
  already sitting there. It was not. The SIGNAL is unaffected and is
  non-repainting; the picture is what misleads.

  A LOW-VOLUME BREAK WITH NO WICK PRINTS NOTHING AT ALL. The clean label needs
  `osc > 20`; the wick labels do not test volume. So a quiet, clean break falls
  through every branch and leaves no mark — which is easy to read as "that
  never happened" rather than "that was filtered".

  THE ALERTS AND THE ARROWS ARE DIFFERENT CONDITIONS. `alertcondition` tests
  only the cross plus `osc > volumeThresh` — no wick test at all. So an alert
  fires on breaks that print a Wick label, and on some that print nothing.
  Anyone wiring these alerts up is not subscribing to what they see.

REPAINT AND LOOKAHEAD: the signal is CLEAN. Pivots are confirmed, `fixnan`
only carries a past value forward, `crossover` reads the current and previous
bar, and the volume EMAs read backwards. The one caveat is intrabar: `osc`
moves while a bar is forming because `volume` is still accumulating. On closed
bars — all this project ever uses — it is fixed.

PINE'S ema SEEDS WITH AN SMA and that is reproduced, because `osc` is a ratio
of two EMAs of different lengths and a different seed shifts the early values
of both. It decays within a few dozen bars and cannot matter hundreds of bars
in, but the port should not have to argue that.

    PYTHONPATH=. python3 research/studies/srbreak.py BTC_USDT Min15
"""
import research.env  # noqa: F401  (must precede riptide.config)

from dataclasses import dataclass                        # noqa: E402

LEFT = RIGHT = 15
VOL_THRESH = 20.0
FAST, SLOW = 5, 10


@dataclass
class Break:
    bar: int
    is_long: bool          # crossover -> up, crossunder -> down
    kind: str              # "clean" | "wick"
    price: float           # the bar's close
    level: float           # the pivot level that was crossed
    osc: float             # volume oscillator on that bar


def ema(vals, n):
    """Pine's ta.ema: seeded with an SMA over the first n values."""
    out = [None] * len(vals)
    if len(vals) < n:
        return out
    seed = sum(vals[:n]) / n
    out[n - 1] = seed
    a = 2.0 / (n + 1)
    for i in range(n, len(vals)):
        out[i] = a * vals[i] + (1 - a) * out[i - 1]
    return out


def _pivots(cs, left, right, high=True):
    """bar -> pivot value, dated at the bar `pivothigh` RETURNS it on.

    Pine's pivothigh(left, right) is na until `right` bars after the pivot, so
    the value appears at pivot_bar + right. Ties: Pine requires the centre to
    be strictly greater than the right side and greater-or-equal is not used,
    so both sides are strict here.
    """
    out = {}
    for j in range(left, len(cs) - right):
        v = cs[j].h if high else cs[j].l
        ok = (all((cs[k].h < v) if high else (cs[k].l > v)
                  for k in range(j - left, j))
              and all((cs[k].h < v) if high else (cs[k].l > v)
                      for k in range(j + 1, j + right + 1)))
        if ok:
            out[j + right] = v
    return out


def levels(cs, left=LEFT, right=RIGHT):
    """(highUsePivot, lowUsePivot) per bar — fixnan of the pivot, lagged one."""
    ph, pl = _pivots(cs, left, right, True), _pivots(cs, left, right, False)
    hi = lo = None
    raw_h, raw_l = [], []
    for i in range(len(cs)):
        if i in ph:
            hi = ph[i]
        if i in pl:
            lo = pl[i]
        raw_h.append(hi)
        raw_l.append(lo)
    # The `[1]`: the value as of the PREVIOUS bar.
    return ([None] + raw_h[:-1]), ([None] + raw_l[:-1])


def srbreak_signals(cs, left=LEFT, right=RIGHT, thresh=VOL_THRESH):
    """Every label the indicator prints, in bar order."""
    hi, lo = levels(cs, left, right)
    vol = [c.v for c in cs]
    f, s = ema(vol, FAST), ema(vol, SLOW)
    out = []
    for i in range(1, len(cs)):
        c, p = cs[i], cs[i - 1]
        if f[i] is None or s[i] is None or not s[i]:
            continue
        osc = 100.0 * (f[i] - s[i]) / s[i]
        up = (hi[i] is not None and hi[i - 1] is not None
              and c.c > hi[i] and p.c <= hi[i - 1])
        dn = (lo[i] is not None and lo[i - 1] is not None
              and c.c < lo[i] and p.c >= lo[i - 1])
        if up:
            wick = (c.o - c.l) > (c.c - c.o)
            if wick:
                out.append(Break(i, True, "wick", c.c, hi[i], osc))
            elif osc > thresh:
                out.append(Break(i, True, "clean", c.c, hi[i], osc))
        elif dn:
            wick = (c.o - c.c) < (c.h - c.o)
            if wick:
                out.append(Break(i, False, "wick", c.c, lo[i], osc))
            elif osc > thresh:
                out.append(Break(i, False, "clean", c.c, lo[i], osc))
    return out


if __name__ == "__main__":
    import asyncio
    import sys
    from datetime import datetime, timezone

    import aiohttp

    from research.studies.mtf_grid import fetch_paged

    sym = sys.argv[1] if len(sys.argv) > 1 else "BTC_USDT"
    tf = sys.argv[2] if len(sys.argv) > 2 else "Min15"

    async def main():
        async with aiohttp.ClientSession() as sess:
            cs = await fetch_paged(sess, sym, tf, 1)
        sigs = srbreak_signals(cs)
        ts = lambda t: datetime.fromtimestamp(t, timezone.utc).strftime(
            "%Y-%m-%d %H:%M")
        print(f"PORT — Support and Resistance Levels with Breaks — {sym} {tf}")
        print(f"window {ts(cs[0].t)} -> {ts(cs[-1].t)} UTC ({len(cs)} bars)")
        days = (cs[-1].t - cs[0].t) / 86400
        for k in ("clean", "wick"):
            g = [x for x in sigs if x.kind == k]
            up = sum(1 for x in g if x.is_long)
            print(f"  {k:<6} {len(g):>4}   up {up:<4} down {len(g) - up:<4}"
                  f"   {len(g) / days:.2f}/day")
        print(f"\n  {'bar time (UTC)':<18}{'label':<14}{'close':>12}"
              f"{'level':>12}{'osc':>9}")
        for x in sigs[-25:]:
            lab = ("Break UP" if x.is_long else "Break DN") + \
                  ("" if x.kind == "clean" else " wick")
            print(f"  {ts(cs[x.bar].t):<18}{lab:<14}{x.price:>12.6g}"
                  f"{x.level:>12.6g}{x.osc:>9.1f}")

    asyncio.run(main())
