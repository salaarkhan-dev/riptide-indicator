# Trendpin — market-structure bias + a single-candle pin

**Status: SPEC ONLY.** No Pine, no measurement, no alerts. Read
[`SPEC.md`](SPEC.md) — it is the whole design and it is what v1 gets built
against.

## In one paragraph

Find the trend from major/minor market structure and refuse to trade a trend
that is ending. Inside it, wait for the counter-trend-coloured pin at the top
of a pullback — green in a downtrend, red in an uptrend — and take its high,
low and open as three levels. When price has closed beyond **both** the high
and the low, in either order, place a limit at the open. Stop above the
pullback, target 3R.

## What is NOT claimed

Nothing. Nothing here has been measured, and the two nearest measurements in
this repository both came back negative:

* `indicators/ccp/measurements/CCP_PATTERN_EXPLORE.md` — the same single-candle
  pins, scored at liquidity grabs: no edge, and **the pin added nothing** over
  the location alone.
* `indicators/ccp/measurements/CCP_CONTEXT_FILTERS.md` — EMA / ADX / Supertrend
  trend filters as gates: all failed, and they improved *seeded random entries*
  more than real ones.

Neither refutes this. The bias here is market structure rather than a moving
average, the pin sits at a pullback extreme rather than at a grab, and the pin
is not being asked to predict anything — it supplies the levels. But they are
the closest priors, they point the same way, and the reason v1 is built to be
measurable from the first line is that this design has to clear a bar those two
did not.

The strategy's own evidence so far is manual bar-replay: ~65% win at roughly
1:3. If that held it would be about **+1.6 R per trade**, which is very large —
and a claim that size is an argument for measuring it properly, not for
relaxing.

## Layout

```
SPEC.md     the design, and the only thing to argue with before Pine exists
pine/       (empty — v1 not written)
tests/      (empty — v1 not written)
```
