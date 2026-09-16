# The twelve CCP patterns at grab right-ends — exploration

`indicators/ccp/studies/ccp_pattern_explore.py`, discovery set only (23 symbols,
333 days). **Exploratory: no prereg, no verdict, nothing here is a finding.**
It exists to produce a shortlist for a pre-registered confirmation on the
holdouts that the FVG work already built.

## The headline: the pin adds nothing

A 2CP is a pin followed by a candle that engulfs it, and the engulfing candle
sets the direction, the entry and half the stop. So the question that decides
whether this is twelve patterns or two is whether requiring the pin changes
anything. Six comparisons, all four 2CPs of a colour against the same
engulfing candle with no pin required:

| | Δ (2CPs − no pin) | z |
|---|---|---|
| Min15 green | +0.032 | +0.90 |
| Min15 red | +0.002 | +0.05 |
| Min30 green | +0.041 | +0.85 |
| Min30 red | −0.088 | −1.78 |
| Min60 green | **−0.162** | **−2.33** |
| Min60 red | +0.040 | +0.54 |

**Five of six inside noise; the sixth significantly negative.** Requiring a pin
before the engulfing candle does not improve the setup and on 1h it makes it
worse. On this evidence **eight of the twelve 2CPs collapse into two** — green
engulfing and red engulfing — and the pin is decoration.

That is not a contradiction of the sheet. The sheet says the pin's job is to
mark that price was rejected at all and that the engulfing candle settles
direction. This says the first half of that job is not worth conditioning on.

## Everything named is negative, except marginally on 1h

Min15 and Min30: **every one of the twelve is negative.** Min60 has five
positives and not one is two standard errors from zero:

```
  2CP Hammer + green engulfing       n   36   +0.192 ± 0.257   thin
  2CP Hammer + red engulfing         n  168   +0.144 ± 0.126
  2CP Inverted hammer + red engulf   n  406   +0.059 ± 0.079
  1CP Inverted hammer                n  896   +0.046 ± 0.056
  CTL red engulfing, no pin          n 3424   +0.044 ± 0.029
```

The largest sample is the one with no pattern in it at all.

## The one consistent thing in the table

**Red engulfing beats green engulfing on all three timeframes**, and improves
as the timeframe rises:

| | red engulfing | green engulfing |
|---|---|---|
| Min15 | −0.032 ± 0.015 | −0.103 ± 0.014 |
| Min30 | −0.010 ± 0.020 | −0.055 ± 0.020 |
| Min60 | **+0.044 ± 0.029** | −0.042 ± 0.027 |

Direction-gated, a red engulfing is a bearish candle at a **buy-side** grab —
price ran a high and was engulfed back down. It is the only row that is
positive with a large sample, and it is still only t ≈ 1.5.

**It may not be a separate finding.** `FVG_H1_TEMPORAL.md` also turns positive
only at Min60, also at grabs. Whether bearish-engulfing grabs and FVG grabs are
two effects or one measurement of the same thing is not answered here, and any
confirmation of this would have to control for FVG presence or the two results
cannot both be counted.

## A bug this run found in itself

The first pass filled **100.0%** of every pattern on every timeframe, which is
not a plausible fill rate for a resting order.

The sheet puts entry at the body edge on the trade side. For a same-colour pin
that is the close — a market fill. For a **hanging man** (bullish, red body)
the body top is the *open*, above the close, so the order is a **stop** that
should fill only if price rises through it; an **inverted hammer** is the
mirror. `research.harness.simulate` fills a long when price comes *down* to the
level, which is right for a limit and exactly wrong for a stop, so both were
being filled on every setup including the ones that never confirmed.

Correcting it moved both rows materially, in the direction that says the bug
was real: **1CP Inverted hammer −0.086 → +0.046**, **1CP Hanging man −0.278 →
−0.143**, with fill rates dropping to 93.9% and 92.0%. All eight 2CPs were
unaffected — an engulfing candle's body edge on the trade side is its close
either way.

## What goes forward

**Nothing yet.** Nothing in this table clears two standard errors, and twelve
patterns on one universe is exactly the setup that produced +0.089 → −0.082 in
`CCP_FILTER_OVERFIT.md`.

The single candidate worth a pre-registered confirmation is **bearish
engulfing at a buy-side grab on Min60, with no pin requirement** — and the
prereg would have to control for FVG presence, because the Min60-only shape of
both results is suspicious in the same direction.

For the Pine: if the pin is decoration, drawing all twelve is drawing ten marks
that mean two things.
