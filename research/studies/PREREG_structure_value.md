# Prereg — does our structure mark anything, and at which period?

Committed **before** the run. Nothing below is adjusted after seeing a number.

## What this study is NOT, and why

The question asked was "which structure is better, ours or the reference's".
**That comparison cannot be run and this study does not attempt it.**

The reference's structure engine is inside `mickes/PriceAction/4`:

    PriceAction.Pivot()   PriceAction.BreakOfStructure()
    PriceAction.ChangeOfCharacter()   priceAction.Swing.Trend

That library is not fetchable from this environment
(`audit/LIQUIDITY_INDUCEMENTS_AUDIT.md` §0). To compare against it I would
have to re-implement it from its call sites and its behaviour on a few
screenshots — that is a *guess at their code*, and a head-to-head against a
guess would produce a number with no meaning attached to it. Whichever way it
came out, it would be a measurement of my reconstruction, not of their
indicator.

So the comparison is declared impossible up front rather than approximated.

## What is measurable, and is what this runs

Whether **our** structure events mark anything, and at which detection period
they mark it best.

An event is a claim about direction: a bullish CHoCH says up from here. So the
testable version is — **after the event bar closes, does price move in the
event's direction more than zero?**

## Events, arms and data — fixed now

Events: `choch`, `bos`, `idm`, each tested separately, from
`research/ms_struct.py`, which is the statement-for-statement transcription of
section 12 that `deploy/ms-py-parity.py` checks against the Pine.

Arms: `msLen` ∈ **{20, 15, 12, 10, 8, 6, 5}**, `msShortLen` fixed at **3**.
Seven arms.

Data: the 23 symbols of `research.data.SYMBOLS`, `Min15`,
`RIPTIDE_LOOKBACK = 2000`, fetched once per symbol and reused across all arms.

## Outcome — one primary, fixed now

For an event at bar *i* with direction *d* (+1 bull, −1 bear):

    fwd = d * (close[i + 20] - close[i]) / atr14[i]

**Horizon 20 bars, five hours on 15m. That is the primary and the only one
the decision may use.** Horizons 10 and 40 are computed and printed as
descriptive context and are explicitly barred from the verdict — naming the
horizon after seeing three of them is how a null becomes a finding.

Events with fewer than 20 bars of data after them are dropped, not scored as
zero.

## Controls

* **C1 — sign-randomised.** The same event bars, `d` replaced by a seeded coin
  flip. Expectation exactly zero, so it isolates *direction* from *timing* and
  from the volatility of the bars events happen to land on.
* **C2 — random bars.** Seeded uniform bars, `d` drawn from the same marginal
  mix of bull/bear as the real events, same count per symbol.

Seed fixed at **20260915**. One draw, not a best-of.

## Decision rule — stated before the run

Seven arms × three event types = twenty-one comparisons. At 2 SE that family
yields roughly one false positive by construction, so:

> An (event, `msLen`) pair **passes** only if its mean `fwd` exceeds zero by
> **≥ 3.0 SE**, exceeds **both** controls, **and** holds its sign on the
> held-out half.

**Held-out split, fixed now:** symbols at an even index in `SYMBOLS` are the
decision set; odd-index symbols are held out. The verdict is read off the even
set and must survive on the odd set. No arm is chosen on the held-out data.

## Power — with the escape hatch

> Report the achieved SE per arm. If 3.0 SE corresponds to a mean `fwd` larger
> than **0.60 ATR** at the 20-bar horizon, that arm is declared
> **UNDERPOWERED** and reports a bound, not a verdict. An underpowered null is
> not evidence of no effect and will not be written up as one.

0.60 ATR over 20 bars is chosen because it is roughly the move that would make
a structure event worth acting on at all; anything the study cannot resolve
below that is not a useful answer either way.

## Overlap — named now, not excused later

At short `msLen` events come faster than the 20-bar horizon, so windows
overlap and the effective sample is smaller than the event count. This is not
corrected for. It inflates significance at the short end, so **a pass at
`msLen` 5 or 6 is to be treated as the weakest kind of pass**, and the report
must print events-per-1000-bars alongside so the reader can see it.

## What a pass would license

One thing: choosing the `msLen` default from evidence instead of from the
ported script's shipped value.

It would **not** license reading a CHoCH as a reason to take or skip a Riptide
signal. That is a different question, and
`research/INDUCEMENT_ON_RIPTIDE.md` already answered the IDM half of it
negatively on 6,663 bets.

## Expected result

Negative for all three event types at all seven periods. The prior is that
structure labels describe what price has already done and carry no forward
information, which is what every previous study on this repo has found for
every context feature tested. Recorded now so a null cannot be presented later
as a disappointment and a pass has to clear the bar above.
