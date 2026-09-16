# PRE-REGISTRATION — can an exit rule rescue an entry with no edge?

Committed before the first number. Run by
`indicators/ccp/studies/ccp_exit_models.py`.

## The decision this is for

`research/CCP_ENTRY_MODELS.md` found that entering on a grab has **no edge
gross of fees** — taking every grab returns between −0.012 and +0.017 R across
six panels, every one inside about a standard error of zero — and loses net.
`indicators/ccp/studies/ccp_excursion.py` then found the path after a grab is not
quite symmetric: grabs beat a risk-matched random entry by about 1.5 points on
the +1R-first race, worth roughly **+0.03 R** against a measured fee drag of
**0.05–0.14 R**.

That leaves one honest objection open, and this run exists to close it:
**maybe the entry is fine and the 2R exit was the wrong instrument.** A partial
at 1.5R with the stop to breakeven is the specific alternative asked for.

`PREREG_ccp_entry_models.md` forbade exactly this — *"a losing arm does not get
a second stop rule"* — which is why this is a separate prereg and a separate
run rather than an extra column on that study.

## My prediction, recorded before the run

**X3 will show a higher win rate and a lower net R than X1.** On a path with
near-zero drift, optional stopping says no stop-and-target scheme changes
expectancy; a partial reshapes the distribution — more small wins, a few
runners given up — and adds a fee. If that is what comes back, the result is
uninformative about grabs and informative about exits. If X3 beats X1 by more
than the control does, I am wrong and it matters.

## Population

Identical to `PREREG_ccp_entry_models.md`: every grab from the **3/3 narrow
instance**, 23 symbols, **Min15 / Min30 / Min60**, 333-day window, older/newer
halves → **six panels**.

## Held constant across every arm

| | |
|---|---|
| **direction** | grab of a HIGH → SHORT; grab of a LOW → LONG |
| **signal bar** | `grabBar + ccpFwd`, entry at its close, market |
| **stop** | the extreme of the grab window **minus `0.25 x ATR`** — past the wick, not floored at it |
| **horizon** | 48 hours — 192 / 96 / 48 bars |
| **fees** | `research.harness` defaults, taker in, maker out on a target, taker out on a stop |
| **scorer** | `research.harness.simulate_market` |

**The stop rule differs from the entry study**, which used the 0.25 ATR as a
*floor* rather than a buffer beyond the extreme. This one is strictly wider.
That is deliberate — it is the rule being built on the bench — and **X1 is the
bridge**: it is the 2R plain exit under the new stop, so any difference between
X1 here and the entry study's base is the stop change and nothing else.

## Arms, fixed in advance

| id | exit |
|---|---|
| **X1** | 2R target, no partial — the bridge |
| **X2** | 1.5R target, no partial |
| **X3** | partial 50% at 1.5R, stop to breakeven, remainder to 2R |
| **C1 / C2 / C3** | the same three exits on a **seeded random bar**, same direction, same stop shape, same risk fraction |

The C arms are the control that matters. If X3 beats X1 by the same margin
that C3 beats C1, the partial is not doing anything grab-specific — it is a
property of the exit on any path, and the comparison says nothing about grabs.

**Not varied.** Partial size is **50%**, because `simulate_market` hardcodes
half; the Pine input's other values are drawn but unmeasured and this run does
not cover them. Breakeven is `be_lock_r = 0.0` exactly. CCP settings are the
shipped defaults and are not swept. No arm gets a second stop rule.

## Unit of evidence

**The bet = one grab.** Standard errors clustered by **(symbol, calendar day)**,
the same choice as the entry study, made before seeing which is kinder.

## Primary metric

X1 and X3 are the same trade with a different exit, so this is a **paired**
difference on the same grab:

    Δ = mean( R(X3, grab) − R(X1, grab) )

That cancels the common variance and is far more powerful than the entry
study's unpaired selection test. Standalone net R is reported for every arm,
and **it is the standalone number that decides whether anything is tradeable.**

## The fee undercount, stated in advance

`simulate_market` charges **one fee per trade even when a partial is taken**
(`research/harness.py`, "One fee per trade, charged by how it ENDS — including
for a partial"). A real partial exits twice, so **X3's cost is understated by
roughly half an exit leg.**

Both numbers will be reported: the harness figure, and a corrected figure that
charges X3 an extra `0.5 x fee_maker` in R. If X3 loses on the harness number
it loses by more in reality. If X3 wins by less than the correction, it does
not win.

## Pre-registered bars — all six

1. **COVERAGE.** ≥ 200 bets in every panel, else the panel is not measurable.
2. **SIGN STABILITY.** Δ keeps one sign across all six panels.
3. **BEATS THE PLAIN EXIT.** Δ > 0 on the newer half of all three timeframes.
4. **MAKES MONEY.** X3 standalone net R > 0 after fees on the newer half of all
   three timeframes, **after the fee correction above.**
5. **NOT JUST THE EXIT SHAPE.** Δ on grabs exceeds Δ on the random control —
   the partial must help *more* at a grab than it does anywhere.
6. **SIGNIFICANCE.** Clustered |z| ≥ 2.0 on the pooled newer half.

### Family-wise inflation, stated before the run

Two comparisons (X3−X1, X2−X1) x three timeframes x two halves = **12 tests**,
plus the control arms. At z ≥ 2.0 each the chance of at least one false
positive is roughly **45%**. Bars 1–5 carry any pass. **Bar 6 alone carries
nothing and no result will be quoted with its z-score and without this
sentence.**

### Power, and the escape hatch

Paired differences on tens of thousands of grabs should give SE(Δ) near 0.01 R.
If any panel's minimum detectable effect exceeds **0.10 R** — tighter than the
entry study's 0.25, because pairing removes most of the variance — that panel
is declared **UNDERPOWERED** and reported as a bound rather than a verdict.

## What cannot happen

* **No production change.** Nothing under `riptide/`;
  `tests/test_control_frozen.py` must still pass.
* **No exchange API key, no order placement, no execution code.** Measurement
  only, as in phase 1.
* **No further exit variants.** Three exits, fixed above. If a partial at 1.5R
  fails, a partial at 1.2R does not get a turn — that is the search inflation
  this repo already has a file about.
* **No retrospective filtering** of symbols, timeframes, halves or grabs.
* **One study.** There is no v2 of this prereg.

## If nothing passes

Then the exit question is closed the way the entry question was: the geometry
stays drawable on the bench, off by default, carrying no claim, and the next
idea — order blocks, FVGs — gets its own prereg and has to **create** edge
rather than reshape a distribution that averages zero.
