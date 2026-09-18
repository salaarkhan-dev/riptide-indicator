# The shipped configuration is not supported by anything measured

Against [`PREREG_undertow_default.md`](../prereg/PREREG_undertow_default.md).
`SYMBOLS_FRESH12`, 44 / 40 / 30 symbols, scored once. **The last set of this
size.** All five pre-registered impossibilities hold — after a correction that
this page has to lead with.

## THE RUN WAS DECLARED VOID FIRST, AND THE CHECK WAS WRONG, NOT THE STRATEGY

Read this before the numbers.

The prereg registered: *"**THE STOP IS THE MINOR SWING.** D1 ≠ L3. If the two
agree the stop source is not being read and L3 is measuring nothing."*

The code tested **trade count**. On Min30 both arms armed exactly 588 setups
and scored **−0.037 against −0.105** — the setting plainly read, doing exactly
what a stop source does, which is move the stop rather than change how many
setups arm. The proxy fired and the run printed VOID.

**This is the third proxy-check incident in this project, and the prereg for
this very study contains a line warning against it.** The check now compares
the stop LEVELS on the trades the two arms share, which is the unambiguous
reading of `D1 ≠ L3` and cannot fire for the wrong reason.

Three things a reader is owed:

* **the arms are bit-identical across the two runs** — diffed, not asserted.
  The correction changed a check, not a number.
* **the numbers were seen before the correction was made.** That is the honest
  hazard here and no amount of reasoning removes it. The precedent followed is
  [`UNDERTOW_SCALE.md`](UNDERTOW_SCALE.md)'s second void, where the registered
  condition held and the implementation tested a different proposition; it was
  corrected and re-run.
* **a run that had genuinely fired an impossibility could not be re-run at
  all.** There is no universe left. That is the price of a careless check, and
  it was nearly paid here.

## The verdict

| tf | D1 today | D0 was | Δ | z | control | gate | n | win% | bars |
|---|---|---|---|---|---|---|---|---|---|
| Min15 | +0.061 | +0.029 | +0.032 | +0.33 | **+0.064** | +0.063 | 721 | 24.5% | PP..P |
| Min30 | −0.037 | −0.022 | −0.015 | −0.14 | **+0.011** | +0.015 | 588 | 22.1% | PP... |
| Min60 | −0.126 | −0.060 | −0.066 | −0.61 | **−0.108** | −0.079 | 402 | 19.9% | PP... |

**NULL.** Bars 3, 4 and 6 fail; bar 5 passes on one timeframe. The shipped
configuration is indistinguishable from the one it replaced, and **it loses to
a seeded random entry on all three timeframes.**

That is twenty components and now one whole configuration, and not one of them
has beaten a control.

## THE LADDER, and one of the four changes does nothing at all

D1 minus the arm without each change. Positive means the change helps.

| tf | shape gate | **armWins** | swing stop | engine |
|---|---|---|---|---|
| Min15 | +0.014 | **+0.000** | −0.027 | +0.080 |
| Min30 | +0.007 | **+0.000** | +0.068 | +0.012 |
| Min60 | −0.081 | **+0.000** | +0.020 | −0.019 |

**`armWins` contributes exactly zero on all three timeframes — same R, same
trade count, same everything.** It is not broken: with the gate OFF it moves
205 trades to 219 on a spent subset. It is **inert when `famStrict` is on**,
and the mechanism is clean:

> With the shape gate on, every admitted pin is the priority shape. So
> `famPriority`'s "a non-priority pin does not displace a waiting priority one"
> never protects anything, every new pin clears all unarmed same-direction
> rivals, and **at most one unarmed candidate exists per direction at a time.**
> First-to-confirm-wins has nothing left to drop.

Two of the four changes were turned on the same day and one of them cancels
the other. Nothing on the chart said so, and no single-component study could
have found it — which is the argument for measuring configurations rather than
only parts.

The other three are all inside one standard error of zero (±0.07 to ±0.12) and
none holds its sign across timeframes. The gate is +0.014 / +0.007 / −0.081;
the engine +0.080 / +0.012 / −0.019. **There is no change here to point at.**

## Against the prediction

| predicted | actual | |
|---|---|---|
| NULL, D1 fails bar 4 | failed 3 of 3 | right |
| D1 − D0 between −0.10 and +0.10 | +0.032 / −0.015 / −0.066 | right |
| Min60 fields 25–32 symbols | 30 | right |
| the engine (L4) near zero | +0.080 / +0.012 / −0.019 | roughly, but +0.080 is not "near zero" |
| **the shape gate is the largest contributor and NEGATIVE** | +0.014 / +0.007 / −0.081 — mixed, and not the largest | **wrong** |
| win rates near the fee-inclusive line | 24.5 / 22.1 / 19.9 vs 23.5 / 23.2 / 22.9 | above on 15m, under on the others |

The prediction I got most wrong is the one I was most confident about. I
expected `famStrict` to drag the package down because
[`UNDERTOW_STRICT.md`](UNDERTOW_STRICT.md) measured that gate below its own
control on two of three timeframes. On this universe it is positive on two of
three. Both readings are inside noise; what the pair of pages actually shows is
that a component measured twice on two universes gives two different signs,
which is the most useful thing either of them says about how much to trust one.

## What changes

**Nothing ships, and the defaults stay.** They are the chart owner's to set,
they were set deliberately with a spent-universe table in view, and this page
does not overrule that. What it does is put the title on the file: *nothing
measured supports them.*

If one is to be reconsidered first, the ladder says **`armWins`** — not because
it is harmful but because it is doing nothing, and a switch that cannot change
an outcome is one fewer thing to reason about. It becomes live again the moment
`famStrict` goes off.

## The bookkeeping, and the end of a method

`SYMBOLS_FRESH12` is spent. **Twenty-nine contracts remain** and they cannot
field 20 symbols on Min60, so the disjoint-holdout method this repository has
run twelve times is finished.

What is left, stated plainly so the next question is asked honestly:

* **walk-forward on the spent sets** — weaker, and it re-reads data that has
  been read, but it is a real design
* **the prospective forward record** — alerts fired in real time, taken or
  skipped, outcomes written down. The watch was built for exactly this and it
  is the only instrument here that can answer the one question twenty
  measurements could not: whether a human choosing which one in ten to take
  beats the machine taking all of them
* **not a thirteenth set of 45.** There isn't one.

Twenty components and one configuration measured. None promoted.
