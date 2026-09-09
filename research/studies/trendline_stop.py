"""A trendline as the stop, on Riptide's real early signals.

FROM A LIVE TRADE, AND THAT IS BOTH THE STRENGTH AND THE PROBLEM. The idea came
from one TAO trade: an early alert filled on the retest, an ascending Liquidity
Trendline support underneath, the stop parked under the line and dragged up with
it as the line rose. It worked. One trade that worked is the weakest possible
evidence for a rule and the strongest possible reason to test one, because the
rule is specific enough to be wrong in a measurable way.

THREE CLAIMS ARE BUNDLED IN THAT DESCRIPTION AND THEY ARE NOT THE SAME CLAIM.

  A  "price came back to the FVG and I entered on the retest"
     THIS IS ALREADY WHAT THE BOT DOES and it is worth saying plainly rather
     than testing. Early signals enter with a LIMIT at the gap edge; the
     scorer fills only when price returns to touch it. The retest IS the fill.
     Nothing to add and nothing to change.

  B  INITIAL stop under the line instead of beyond the raid extreme.
     This changes the RISK, so it changes what one R means, and the fee is
     charged as a fraction of risk — `fee / risk_pct` — which is the dominant
     cost in every measurement this project has made. A tighter stop is more
     expensive per unit of R before it is anything else.

  C  TRAIL the stop up the line after entry, never down.
     This leaves R fixed at entry and only changes exits. It is a different
     question from B and has to be scored separately or the two effects are
     confounded.

B and C are tested here as separate arms. A is not tested because it is not a
proposal, it is a description of the existing mechanism.

THE PRIOR IS NOT GOOD, and pretending otherwise would waste the reader's time.
`research/studies/stops.py` already asked whether any stop management beats a
plain fixed stop and found none did, on either strategy, in either half — and
that break-even, the closest relative of this idea, "loses at every arm level,
and the earlier the arm the worse it is". A trendline trail is a more
aggressive relative of break-even: it moves the stop toward price on a schedule
set by a line rather than by an R multiple.

What is genuinely different, and why this is worth running anyway: the
trendline is STRUCTURAL. Break-even at 1R moves the stop to a level chosen by
arithmetic that has nothing to do with the chart. A rising support line is
where price has actually been turning. If any trailing rule is going to work,
it is this shape of rule, and nobody has tested it here.

PRE-REGISTERED, BEFORE THE FIRST NUMBER

  PRIMARY   Net R per signal must BEAT the plain fixed stop on the HELD-OUT
            half at 2 SE, on the same trades. Not beat zero — beat the thing
            it would replace.

  SECONDARY Win rate and full stop-outs, reported whatever the primary does,
            because those are what the idea was reached for. `stops.py` found
            a partial buys a large win-rate gain for a small R cost; if the
            trail does the same that is worth knowing even when the primary
            fails, and it is worth knowing precisely rather than by feel.

  COVERAGE is reported first and can settle the question on its own. The rule
  only exists when a live line is under the trade. On TAO 15m only 28% of bars
  had a live support line at all. A rule that applies to a fifth of trades
  cannot move the aggregate much whatever it does to those trades.

  EXPECTATION, recorded so it cannot be revised afterwards: the trail raises
  the win rate, cuts full stop-outs, and LOSES net R — the same shape every
  stop-management rule in this project has produced. The interesting number is
  the price, not the direction.

    PYTHONPATH=. python3 research/studies/trendline_stop.py
"""
import research.env                                     # noqa: F401  MUST be first

import statistics                                       # noqa: E402

from riptide.trendline import trendline_signals         # noqa: E402
from research.data import atr_at, load_sync             # noqa: E402
from research.harness import mean_se, simulate          # noqa: E402

# How far under the line the stop sits, in ATR. A stop exactly ON a support
# line is hit by every wick that tests it; the line is where price turns, not
# a floor it never pierces. 0.25 ATR is the same order as the engine's own
# sl_buffer_atr and is NOT swept — one value, fixed in advance, because
# sweeping it and reporting the best would be fitting.
BUFFER_ATR = 0.25
TARGET_R = 2.0          # what the bot actually tracks
_LEVELS: dict = {}


def levels(r):
    """Per-bar (support, resistance) for this symbol's candles, cached."""
    k = id(r.candles)
    if k not in _LEVELS:
        out: list = []
        trendline_signals(r.candles, levels_out=out)
        _LEVELS[k] = out
    return _LEVELS[k]


def trail_for(r):
    """The stop level to rest under, per bar, or None where there is no line.

    A long rests under the ascending SUPPORT line; a short rests above the
    descending RESISTANCE line. A line on the wrong side of the trade is not a
    stop, it is a target, so it is ignored.
    """
    a = atr_at(r)
    if not a:
        return None
    lv = levels(r)
    buf = a * BUFFER_ATR
    out = []
    for sup, res in lv:
        v = sup if r.signal.is_long else res
        out.append(None if v is None else (v - buf if r.signal.is_long
                                           else v + buf))
    return out


def line_at_entry(r):
    """The line level on the signal bar, on the correct side of the trade.

    None when no channel is live, or when the line is on the wrong side —
    above a long's entry, or below a short's. A support line sitting ABOVE the
    entry cannot hold a stop.
    """
    t = trail_for(r)
    if t is None or r.bar >= len(t):
        return None
    v = t[r.bar]
    if v is None:
        return None
    e = r.signal.entry
    if (v >= e) if r.signal.is_long else (v <= e):
        return None
    return v


def score(r, stop=None, trail=None):
    o = simulate(r.candles, r.bar, r.signal.entry,
                 stop if stop is not None else r.signal.stop,
                 r.signal.is_long, target_r=TARGET_R, trail=trail)
    return o if not (o.exit_bar is None and o.filled) else None


def table(name, rows, get, stop_of=None):
    """One arm: net R, win rate and full stop-outs on the same trades.

    `stop_of` is the stop this arm ACTUALLY used. It has to be passed in
    rather than read off the signal: arm B replaces the stop, so reporting
    the signal's original risk for it would hide the one thing that arm
    changes — and the fee is charged as a fraction of risk, which is the
    dominant cost in every measurement here. Caught by the risk column
    reading an identical 1.74% for four arms that cannot all have it.
    """
    out = [(r, get(r)) for r in rows]
    out = [(r, o) for r, o in out if o is not None]
    filled = [(r, o) for r, o in out if o.filled]
    if len(filled) < 25:
        print(f"  {name:<28}   too few")
        return None
    rs = [o.r for _, o in filled]
    m, se = mean_se(rs)
    wins = sum(1 for _, o in filled if o.r > 0)
    stops = sum(1 for _, o in filled if o.exit == "stop" and o.r < -0.5)
    stop_of = stop_of or (lambda r: r.signal.stop)
    risk = statistics.fmean(100 * abs(r.signal.entry - stop_of(r))
                            / r.signal.entry for r, _ in filled)
    print(f"  {name:<28}{len(filled):>6}{wins / len(filled):>7.0%}"
          f"{stops / len(filled):>9.0%}{risk:>8.2f}%{m:>+9.3f}{se:>7.3f}")
    return m, se, rs


def arms(title, rows):
    print(f"\n{title}   n={len(rows)}")
    print(f"  {'':<28}{'filled':>6}{'win':>7}{'full SL':>9}{'risk':>9}"
          f"{'R/signal':>9}{'SE':>7}")
    base = table("plain fixed stop", rows, lambda r: score(r))
    c = table("C  trail up the line", rows,
              lambda r: score(r, trail=trail_for(r)))
    b = table("B  initial stop AT the line", rows,
              lambda r: score(r, stop=line_at_entry(r)), line_at_entry)
    bc = table("B+C  at the line, trailed", rows,
               lambda r: score(r, stop=line_at_entry(r), trail=trail_for(r)),
               line_at_entry)
    for lab, arm in (("C", c), ("B", b), ("B+C", bc)):
        if not (base and arm):
            continue
        n = min(len(base[2]), len(arm[2]))
        d, dse = arm[0] - base[0], (arm[1] ** 2 + base[1] ** 2) ** 0.5
        print(f"  {lab + ' vs plain':<28}{'':>31}{d:>+9.3f}{dse:>7.3f}"
              f"   {d / dse if dse else 0:+.1f} SE")


def main():
    # The full scanned universe, not research.data's 23-symbol default. The
    # rule only applies where a line exists — 18% of signals — so the default
    # corpus left 81 trades in the held-out half, which cannot separate
    # anything. Widening the symbol list is the only lever: the window is
    # already the maximum the exchange serves.
    import asyncio
    import aiohttp
    from riptide.exchange import list_symbols

    async def _syms():
        async with aiohttp.ClientSession() as sess:
            return await list_symbols(sess)
    syms = asyncio.run(_syms()) or None
    rows = [r for r in load_sync(symbols=syms) if r.kind == "early"]
    have = [r for r in rows if line_at_entry(r) is not None]
    print(f"A TRENDLINE AS THE STOP — Riptide early signals, target "
          f"{TARGET_R:g}R\n{len(rows)} early signals · buffer "
          f"{BUFFER_ATR} ATR under the line · fixed, not swept\n")

    print("COVERAGE — the rule only exists when a line is under the trade")
    print(f"  early signals                              {len(rows)}")
    print(f"  ...with a live line on the correct side    {len(have)}"
          f"   ({len(have) / len(rows):.0%})")
    def has_any(r):
        t = trail_for(r)
        return t is not None and r.bar < len(t) and t[r.bar] is not None
    anyline = sum(1 for r in rows if has_any(r))
    print(f"  ...with any line at all on that side       {anyline}"
          f"   ({anyline / len(rows):.0%})")
    if len(have) < 50:
        print("\n  Too few to score. That IS the answer for now: whatever the "
              "rule\n  does to a trade, it applies to too few of them to "
              "matter.")
        return

    arms("ALL SIGNALS WITH A LINE", have)
    disc = [r for r in have if not r.split_window]
    held = [r for r in have if r.split_window]
    if len(disc) >= 50:
        arms("DISCOVERY (newer half)", disc)
    if len(held) >= 50:
        arms("HELD OUT (older half) — this is the pre-registered one", held)
    print(f"\nPRE-REGISTERED: an arm passes only by beating the PLAIN stop on "
          f"the\nheld-out half at 2 SE. Beating zero is not the test; the "
          f"plain stop is\nwhat it would replace.")


if __name__ == "__main__":
    main()
