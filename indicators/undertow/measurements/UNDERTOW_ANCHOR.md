# The leg anchor finds exactly the candle it was designed to find, and those trades are worse

Against [`PREREG_undertow_anchor.md`](../prereg/PREREG_undertow_anchor.md).
`SYMBOLS_FRESH10`, 43 / 39 / 28 symbols, scored once. All four pre-registered
impossibilities hold.

## The verdict

| tf | L1 leg | L0 ships | Δ | z | control | n | win% | **prio%** | kept | bars |
|---|---|---|---|---|---|---|---|---|---|---|
| Min15 | −0.066 | −0.010 | −0.056 | −0.69 | −0.038 | 1012 | 22.1% | **85.9%** | 49% | PP... |
| Min30 | −0.058 | −0.049 | −0.009 | −0.13 | −0.041 | 934 | 21.8% | **86.3%** | 52% | PP... |
| Min60 | −0.140 | −0.060 | −0.080 | −0.73 | −0.042 | 622 | 19.8% | **88.1%** | 49% | PP... |

**Negative on 3 of 3, below its control on 3 of 3, worse than the shipped
anchor on 3 of 3** — and every margin inside one standard error. Bars 3, 4, 5
and 6 all fail.

## THE MECHANISM WORKS. THAT IS WHAT MAKES THIS THE CLEANEST NEGATIVE HERE

The pre-registered impossibility demanded ≥ 70% of the anchor's pins be the
priority shape — hammer at the bottom of a down-leg, shooting star at the top
of an up-leg. **It came in at 85.9%, 86.3% and 88.1%**, against the shipped
anchor's 53%.

So the anchor is not broken, mis-attached or mistuned. **It finds the candle
the diagram draws, nearly nine times in ten.** Every previous null in this
project could be read as "the rule didn't detect what it claimed". This one
cannot:

> **The rule did exactly what it said, and the trades it found are worse than
> the ones it replaced.**

The pools say it without ambiguity. These are the trades **unique to the leg
anchor** — the hammers at the leg low, the shooting stars at the leg high, the
candles the whole idea is about:

| tf | shared | ships only | **leg only** |
|---|---|---|---|
| Min15 | −0.029 (430) | −0.005 (1623) | **−0.093 (582)** |
| Min30 | −0.083 (384) | −0.040 (1408) | **−0.040 (550)** |
| Min60 | −0.072 (281) | −0.056 (982) | **−0.196 (341)** |

The worst pool on two of three, and never the best.

## The two anchors turn out to be the same thing at 14/5

`L3` is v3's `trend extreme` — the running extreme since the major CHoCH:

| | priority shape | Δ from ships |
|---|---|---|
| L1 leg extreme | 85.9 / 86.3 / 88.1% | −0.056 / −0.009 / −0.080 |
| L3 trend extreme | 86.2 / 86.2 / 89.1% | −0.015 / +0.005 / −0.071 |

**Indistinguishable.** The distinction that mattered enormously at 50/5 — one
stale point per trend against one per leg, a median of 47 bars apart — is
nearly nothing at 14/5, because a 14-bar pivot updates the major extreme often
enough to sit where the internal one does. The third anchor was worth adding
to diagnose the 50/5 chart; at 14/5 it earns nothing over the one that was
already there.

## What tolerance 2 does, and it is not what v3 found

`L2` is the leg anchor at `locTol 2`: **67.3 / 67.3 / 69.5%** priority shapes
with **2.3× the trades** of `L1`, and Δ from ships of +0.019 / −0.005 / −0.033.

[`UNDERTOW_V3.md`](UNDERTOW_V3.md) found the shape selection collapsed to ~56%
at tolerance 2 and concluded it "lives entirely at zero tolerance". At the LEG
anchor it does not: two bars of tolerance keeps most of the selection and
doubles the coverage. That is a real difference between the two anchors and it
was not predicted.

**L2 may not be promoted** — best-of-four is selection, and the prereg says so.
It is the most interesting cell on the page and that is exactly why it needs
its own prereg and its own universe rather than a promotion from this one.

## Against the prediction

| predicted | actual | |
|---|---|---|
| L1 fails bar 4 | failed 3 of 3 | right |
| L1 − L0 between −0.10 and +0.10 | −0.056 / −0.009 / −0.080 | right |
| the priority impossibility holds at 80–85% | held, at 86–88% | right, slightly under |
| L2 ≈ 3× L1's trades at ~56% priority shapes | 2.3×, at 67–70% | **wrong on the shapes** |
| win rates near the fee-inclusive line | 22.1 / 21.8 / 19.8 against 23.5 / 23.2 / 22.9 | **below it on all three** |

The last row is the one to sit with. Sixteen studies have put win rates *on*
the fee-inclusive line; this is the first arm to come in consistently **under**
it, which is what a negative expectancy looks like rather than a flat one.

## What changes

**Nothing ships.** By the prereg's decision rule a null here is not a null like
the scale study's:

* the scale's null meant *a preference is free — keep it*
* **this null means the stated anchor costs half the setups and, as far as
  1,000 trades a timeframe can tell, makes them slightly worse**

`pinAt` stays at `pullback extreme`. `leg extreme` and `trend extreme` remain
selectable on the chart, this page is what they cost, and the decision belongs
to the chart's owner with the number in front of them rather than to a
measurement that found no reason either way.

**What this does NOT say** is that the author's reading of the strategy is
wrong. It says the candle that reading identifies does not trade better in a
mechanical backtest that takes all of them. Those are different claims, and
the second one is the only one 1,000 trades can speak to.
