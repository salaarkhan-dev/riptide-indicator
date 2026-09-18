# The priority shape is a perfect gate, and the half it throws away scored better

Against [`PREREG_undertow_strict.md`](../prereg/PREREG_undertow_strict.md).
`SYMBOLS_FRESH7`, 42 / 39 / 30 symbols, scored once. All four pre-registered
impossibilities hold.

## The verdict

| tf | S1 gate | S0 ships | Δ | z | control | n | win% | **prio%** | kept | bars |
|---|---|---|---|---|---|---|---|---|---|---|
| Min15 | −0.067 | −0.090 | +0.024 | +0.29 | −0.126 | 1196 | 22.3% | **100.0%** | 62% | PP... |
| Min30 | −0.040 | −0.026 | −0.014 | −0.18 | +0.038 | 1109 | 22.5% | **100.0%** | 63% | PP... |
| Min60 | −0.062 | +0.038 | −0.099 | −1.23 | +0.058 | 852 | 21.6% | **100.0%** | 62% | PP... |

**Negative on 3 of 3, and beaten by its own control on 2 of 3.** Bars 3, 4, 5
and 6 all fail. `famStrict` stays off.

## The mechanism is not merely good, it is exact

The pre-registered impossibility was not a threshold. The anchor study asked
for ≥ 70% because an anchor points at a bar and can point slightly wrong; a
gate admits one code by construction, so the honest assertion was **zero**
hanging men and **zero** inverted hammers.

**It came in at 100.0%, 100.0% and 100.0%** — 3,157 armed trades, not one of
them anything but a hammer short or a shooting star long.

So this cannot be read the way a reader might want to read the earlier nulls.
There is no mistuning, no mis-attachment, no "the rule didn't find what it
claimed". The gate admits precisely the candle the strategy names, every time,
and **the trades are worse than the ones it replaced on two of three
timeframes and worse than a coin on two of three.**

## THE ONE CELL THAT DESERVES CARE

The complement is free here and exact: because S1 is precisely the
priority-coded half of S0, `S0 − S1` is precisely the non-priority half. The
two halves partition the same population, at the same levels, with the same
exits. So this is the most direct test the candle taxonomy has ever had:

| tf | S1 priority half | S2 the other half | S1 − S2 | ± | z |
|---|---|---|---|---|---|
| Min15 | −0.067 | −0.129 | **+0.062** | 0.094 | +0.66 |
| Min30 | −0.040 | −0.003 | **−0.037** | 0.104 | −0.36 |
| Min60 | −0.062 | **+0.197** | **−0.258** | 0.105 | **−2.46** |

**On 1h the hanging man and the inverted hammer — the shapes this gate exists
to remove — scored +0.197 R per trade at a 27.3% win rate, against the stated
priority shape's −0.062.** That is the only |z| ≥ 2 anywhere in eighteen
studies, and it points against the author's stated rule.

**Do not read it as a result, and here is why in numbers.** Three cells were
examined. The chance that at least one of three independent cells crosses
|z| = 2 by luck alone is about **14%**, and the other two sit at +0.66 and
−0.36 — squarely nothing. A single cell at −2.46 out of three, with no support
from its neighbours, is what noise looks like when you look at three things.

**What it IS: the best-supported candidate this project has produced for its
own pre-registration.** Every other lever came from a diagram or an opinion.
This one came from a measurement on a universe that had never been read, in a
slice that was pre-registered as descriptive before the number existed. That
earns it a prereg and a fresh universe, not a promotion. Testing it here would
be selecting the best of three cells, which is exactly the −0.31 R that
[`UNDERTOW_PARAMS.md`](UNDERTOW_PARAMS.md) priced.

## Against the prediction

| predicted | actual | |
|---|---|---|
| S1 fails bar 4 | failed 3 of 3 | right |
| both impossibilities hold exactly | 0 outside, 0 off-shape | right |
| S1 − S0 between −0.05 and +0.05 | +0.024 / −0.014 / **−0.099** | **wrong on 1h** |
| S1 − S2 within ±0.05 of zero | +0.062 / −0.037 / **−0.258** | **wrong on 1h, badly** |
| win rates near the fee-inclusive line | 22.3 / 22.5 / 21.6 against 23.5 / 23.2 / 22.9 | under it on all three |

Two predictions wrong and both on the same timeframe. The one I got most
wrong — "the two halves will be indistinguishable, the taxonomy is a naming
scheme" — is the one that produced the only interesting number on the page. I
had the direction of the surprise backwards as well: I expected the taxonomy to
be worth nothing, and 1h says it may be worth something *the other way round*.

The discard rate also came in lighter than the design input said. 45% was
measured on the spent 23; on FRESH7 the gate keeps 62 / 63 / 62%. The
population differs, and the prereg's "45%" should be read as "roughly the
smaller half" rather than a constant.

## What changes

**Nothing ships.** By the prereg's decision rule this null is the anchor's
kind, not the scale's:

* the scale's null meant *a preference is free — keep it*
* **this null means the stated gate costs nearly 40% of the setups and, as far
  as 3,157 trades can tell, does not improve them**

`famStrict` stays on the chart as a toggle defaulting to off, this page is what
it costs, and the decision belongs to the chart's owner with the number in
front of them.

**What this does NOT say** is that the author's reading of the pullback is
wrong. It says a mechanical gate that takes every instance of the named candle
does not trade better than one that takes both shapes. Those are different
claims, and the second is the only one 3,157 trades can speak to.

## The bookkeeping

`SYMBOLS_FRESH7` was released to this study from
[`PREREG_undertow_pin.md`](../prereg/PREREG_undertow_pin.md), which is retired
unrun: `pinNewest` and `famPriority` shipped as corrections, so its baseline —
labelled "what ships today" — became false. No number had been computed on
FRESH7 by that study or any other. **It is spent now.** FRESH8, FRESH9 and
FRESH10 are spent; 122 unused contracts remain, which is at most two more sets.

Eighteen components measured. None promoted.
