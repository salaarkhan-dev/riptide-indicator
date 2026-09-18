# PRE-REGISTRATION — the priority shape as a GATE

Committed before the first number. Run by
`indicators/undertow/studies/undertow_strict.py`.

## The question

The strategy's author states the priority shape and it has now shipped as a
RANKING: in a bearish trend the hammer outranks the inverted hammer, in a
bullish trend the shooting star outranks the hanging man, and the second choice
still trades when the priority one is absent.

`famStrict` makes the ranking a **GATE**. The second choice never trades. With
the colour rule already fixing the candle's colour, what survives is exactly
one code per direction — **HAM short, SS long** — and the four-code taxonomy of
[`SPEC.md`](../SPEC.md) §2.1 collapses to two.

It is on the chart, **off by default**, and unmeasured.

## Why this is NOT shipped as a correction like W→F

W→F, the priority pairing and the inclusive failure test all went out without a
measurement, because each changes *which event arms* and costs nothing.

**This one discards 45% of the population.** A rule that throws away nearly half
the setups is not a free correction, whoever stated it, and it gets measured
before it becomes a default. That is the standard
[`UNDERTOW_ANCHOR.md`](../measurements/UNDERTOW_ANCHOR.md) set.

## THE GATE IS AN EXACT SUBSET, WHICH FIXES THE CONTROL

`SYMBOLS`, the spent 23, at `maxLive 64`, as a design input:

| tf | what ships | strict | shared | **strict only** |
|---|---|---|---|---|
| Min15 | 1,685 | 929 | 929 | **0** |
| Min30 | 1,748 | 969 | 969 | **0** |
| Min60 | 1,706 | 999 | 999 | **0** |

**Every trade the gate takes, the shipped rule also takes, and it invents
none.** It keeps 55 / 55 / 59%.

So the control is a **matched random GATE**, not a seeded random entry. A rule
that throws away half a population moves the mean whatever it is, and half of
all such rules move it up; the thing to beat is a coin refusing as often. This
is the same reasoning as [`PREREG_undertow_pin.md`](PREREG_undertow_pin.md) and
the **opposite** of the anchor and scale studies, where the rule RELOCATED the
population and a random entry was the honest control.

**And it makes the complement free and exact.** Because S1 is precisely the
priority-coded half of S0, `S0 − S1` is precisely the non-priority half. No
second run and no rivalry caveat: the two halves partition the baseline.

## The arms

| id | | |
|---|---|---|
| **S0** | what ships — `famStrict` off | **THE BASELINE** |
| **S1** | **`famStrict` on** | **THE PRIMARY** |
| S2 | the complement, `S0 − S1` | descriptive — the non-priority half |
| **C** | matched random gate on S0 at S1's discard rate | **THE CONTROL** |

Everything else is the shipped configuration and identical across arms: SMC
14/5, W→F, the inclusive failure test, `pinNewest` and `famPriority` on,
`pinAt` the pullback extreme at `locTol 0`, `endMinor` on the flip, retrace 70,
`rr` 3.5, 7bp, `armWins` off, `maxLive 64`.

S2 may not be promoted. It is a slice reported so the reader can see whether
the SHAPE carried anything, and a best-of-three is the selection that
[`UNDERTOW_PARAMS.md`](../measurements/UNDERTOW_PARAMS.md) priced at −0.31 R.

## Population — and FRESH7 is RELEASED to this study

**`SYMBOLS_FRESH7`** — 45 contracts, disjoint from the 23 and from every other
fresh set. 42 / 39 / 30 symbols carry the bars.

**It was claimed by [`PREREG_undertow_pin.md`](PREREG_undertow_pin.md), which
is retired unrun.** That study asked whether `pinNewest` and `famPriority`
should ship. They shipped — as corrections, on the footing W→F went out on —
so its `P0`, labelled "what ships today", is now false and the study as written
cannot run. **No number was ever computed on FRESH7**, by that study or any
other; the candles were fetched and nothing was scored. A set is spent when
someone has seen a result from it, not when it has been named, so it is
genuinely fresh and it is used here rather than cutting a FRESH11 out of a
thinner tail.

That reasoning is written down because it is the kind that can be abused. The
test of it is the one above: **no result from FRESH7 has been read by anybody.**

* 12,000 bars, Min15 / Min30 / Min60, ≥ 11,000 bars or dropped
* a timeframe with fewer than 20 surviving symbols is **not reported**

## What must be IMPOSSIBLE

Written to assert the thing being checked, which two preregs ago it did not.

* **THE GATE REACHES THE PIN.** *Every* armed trade in S1 carries the priority
  code — `HAM` when short, `SS` when long. **Zero `HGM` and zero `IH`.** Not a
  threshold: the gate admits nothing else by construction, so a single one
  means `famStrict` is not being read.
* **S1 IS A STRICT SUBSET OF S0.** Zero trades in S1 that S0 does not take. If
  it invents trades it is not a selector, and the matched gate is the wrong
  control.
* **S1 IS SMALLER THAN S0.** Identical counts mean the field is dead.
* **`nCap` is 0 in every arm.**

Any of these firing makes the run **VOID** and the numbers are not published.

## Pre-registered bars, on S1

1. **COVERAGE.** ≥ 200 closed trades.
2. **NOT CONFOUNDED.** All four impossibilities hold.
3. **BEATS WHAT SHIPS.** S1 − S0 ≥ **+0.10 R per trade**, clustered |z| ≥ 2.
4. **BEATS ITS CONTROL.** ≥ 1 SE above the matched random gate.
5. **POSITIVE.** Mean R per trade > 0 after fees.
6. **NOT ONE TIMEFRAME.** Positive on ≥ 2 of 3.

## The decision rule

* **S1 clears 3, 4, 5 and 6** → `famStrict` becomes the default in the port,
  the chart and the watch. It would be the first component in this project to
  beat its control.
* **S1 beats the GATE but not what ships** → the weaker outcome, named in
  advance. It stays an input defaulting to OFF, the way `pinAt` did. That is
  not a promotion and the page does not get to call it one.
* **NULL** → the stated gate costs **45% of the setups for no measurable
  gain**. It stays selectable, the page says plainly what it costs, and the
  decision belongs to the chart's owner with the number in front of them.
* **WORSE by more than 0.10 R at |z| ≥ 2 on ≥ 2 timeframes** → it stays off and
  the page says so.

## My prediction, recorded before the run

* **S1 fails bar 4.** Seventeen components measured, none has beaten a control.
* **S1 − S0 lands between −0.05 and +0.05**, and I hold this one TIGHTER than
  the anchor's ±0.10. This is a pure subset of the same trades at the same
  levels, not a relocation, so the only thing that can move the mean is whether
  the shape sorts winners from losers.
* **The subset and code impossibilities hold**, the first at exactly 0 outside
  and the second at exactly 0 non-priority codes. If either fires it is a
  plumbing fault, not a finding.
* **S1 − S2 is within ±0.05 of zero — the sharpest prediction here.** If the
  shape carries information the priority half must beat the non-priority half,
  and [`UNDERTOW_PIN_VALUE.md`](../measurements/UNDERTOW_PIN_VALUE.md) already
  found that removing the candle taxonomy entirely scored HIGHER on two of
  three. I expect the two halves to be indistinguishable, which would say the
  taxonomy is a naming scheme rather than a signal.
* **Win rates near the fee-inclusive line**, 22.9–23.5% by timeframe.
* **I expect this to be a cleaner negative than the anchor**, for the same
  reason: the mechanism cannot fail here. The anchor could at least be accused
  of pointing at the wrong bar. A gate that admits one code by construction
  either pays or it does not.

## What cannot happen

* **No second gate and no partial gate** beyond the fixed arms above — no
  "priority shape unless none appeared within N bars".
* **No promotion of S2.**
* **No falling back to another universe.** FRESH8, FRESH9 and FRESH10 are
  spent; FRESH7 is this study's and is released above.
* **No change to the taxonomy, the levels, the exit or the bias.**
* **No exchange API key and no order placement.**
* **One study, one run.**
