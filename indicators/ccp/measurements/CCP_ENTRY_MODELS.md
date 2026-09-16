# Entry models on the CCP-at-grab mark

Pre-registered in `PREREG_ccp_entry_models.md`, committed before the run.
Study: `indicators/ccp/studies/ccp_entry_models.py`, outputs
`ccp_entry_models.out` (net) and `ccp_entry_models_gross.out` (the zero-fee
diagnostic).

## Verdict

**Nothing passes. All three arms fail all five bars on all three timeframes.**

And the study says something sharper than "nothing passes", which is the part
worth acting on:

> **Gross of fees, entering on a grab has no edge at all.** Taking *every*
> grab returns −0.002, +0.005, +0.003, −0.000, +0.017, −0.012 R across the six
> panels — every one within about one standard error of zero. The net loss is
> not an edge being eaten by costs. There is no edge underneath the costs.

That closes off a whole family of would-be rescues. A better fee tier, a
minimum-risk filter, a wider stop to cut the fee drag — none of them can turn a
gross expectancy of zero into a positive one. Anything that works here has to
**create** edge, not recover it.

## What was measured

76,297 scored grabs. 23 symbols, 333 days, the 3/3 narrow instance — the same
detector `deploy/ccp-grab-check.py` proves is byte-identical between
`riptide-indicator-v2.pine` and `riptide-ccp.pine`.

| | Min15 | Min30 | Min60 |
|---|---|---|---|
| scored grabs | 43,429 | 22,213 | 10,655 |

Every grab gets the **same entry bar** (`grabBar + 2`, at its close), the
**same stop rule**, the **same 2R target** and the **same 48-hour horizon** —
including the grabs CCP rejects. So the arms differ by which grabs they accept
and by nothing else, and Δ is selection, not execution.

## Results, net of fees

Δ = mean R(accepted) − mean R(rejected), SE clustered by (symbol, day).

| arm | Min15 old | Min15 new | Min30 old | Min30 new | Min60 old | Min60 new |
|---|---|---|---|---|---|---|
| **A1** both ends | +0.020 | +0.004 | +0.051 | **−0.069** | −0.062 | −0.015 |
| **A2** right end | **+0.049** | +0.001 | **+0.090** | −0.015 | +0.001 | −0.042 |
| **A3** + anchor gate | +0.007 | +0.056 | +0.035 | −0.099 | **+0.283** | −0.005 |

Standalone net R, newer half — **the number that decides whether anything is
tradeable**:

| | Min15 | Min30 | Min60 |
|---|---|---|---|
| B every grab | −0.119 | −0.081 | −0.065 |
| A1 | −0.116 | −0.139 | −0.078 |
| A2 | −0.119 | −0.090 | −0.091 |
| A3 | −0.066 | −0.176 | −0.069 |

Every cell negative. No arm beats simply taking every grab by enough to matter,
and two of them are worse than it.

## The three traps the bars caught

**1. The older half looked promising and did not replicate.** A2 reached
z +2.27 on Min15 and z +2.95 on Min30 in the older half. The same two cells in
the newer half are **+0.03 and −0.50**. With 18 tests in the family, two
marginal older-half hits is roughly what noise predicts, and bar 2 — one sign
across six panels — exists for precisely this.

**2. One cell looks like a winner and is the cherry-pick.** A3 on Min60, older
half: **+0.247 R standalone, Δ +0.283, z +2.34**. It has n = 149, fails the
200-bet coverage bar, and the same cell in the newer half is **−0.069**. Quoted
alone it would read as a discovery. It is one small panel out of eighteen.

**3. The stop rule did not degenerate this time.** Risk ran p25 0.27% to p75
2.59% of price, median 0.52–1.37% — above the 0.42% guard in every panel. In
`MS_ENTRY_MODELS.md` two of five models were rendered *unmeasurable* by stops
at 0.16–0.20%, where the losses were gap-throughs rather than information about
the trigger. The pre-declared 0.25 ATR stop floor is what prevented a repeat,
and it means this null is a result rather than an artefact.

**This is not an underpowered null.** No panel tripped the 0.25 R
minimum-detectable-effect ceiling, so the escape hatch was not needed. On the
big arms SE(Δ) is 0.017–0.034, so the run could have resolved effects of
0.05–0.10 R. It found none.

## Where the money actually goes

Fees are charged in R as `fee% / risk%`, so cost per trade goes as **1/risk**
and is convex. The small-risk tail, not the median, sets the mean drag:

| | median risk | fee at the median | **actual mean drag** |
|---|---|---|---|
| Min15 new | 0.52% | 0.085 R | **0.136 R** |
| Min30 new | 0.78% | 0.056 R | **0.088 R** |
| Min60 new | 1.17% | 0.038 R | **0.058 R** |

Quoting the median understates the real cost by about 60%. That drag accounts
for essentially the whole net loss — which is exactly why the gross diagnostic
below is the informative one.

## The zero-fee diagnostic — post-hoc, and it decides what to try next

Not a pre-registered arm. It gets no verdict. It answers one question: is a
losing arm losing because the edge is absent, or because the edge is smaller
than the cost of taking it?

Standalone R gross, newer half:

| | Min15 | Min30 | Min60 |
|---|---|---|---|
| **B every grab** | **+0.005** | **−0.000** | **−0.012** |
| A1 | −0.023 | −0.076 | −0.036 |
| A2 | −0.022 | −0.027 | −0.049 |
| A3 | +0.043 | −0.105 | −0.020 |

Two readings, and both matter.

**The grab itself is a coin flip.** B is flat to four decimal places on Min30.
Whatever a grab is, it does not tilt the next 48 hours.

**The CCP filter, if anything, selects worse grabs.** Pooled on the newer half,
A1 is Δ −0.049 at z −2.34 and A2 is Δ −0.045 at z −2.62. Both arms, same
direction, gross. Read with the 18-test caveat this is suggestive rather than
established — but it is the opposite of the hypothesis, and nothing in the data
points the other way.

> A note on the output: bar 5 is a **two-sided** |z| ≥ 2 test, so it prints
> PASS on those two cells. It is registering a significant effect in the
> **wrong direction**. Direction is bar 3's job, and bar 3 fails.

## Limitations, stated rather than buried

* **C0 is not a clean timing control.** It keeps the same structural stop level
  but enters later, so its risk size differs — it varies timing *and* sizing.
  B beats C0 by roughly +0.03 to +0.06 R in five of six panels, and that gap
  must not be read as pure timing information. It is the one comparison in this
  study with a confound in it, and it is the one I am least willing to lean on.
* **One target, one horizon, one stop rule.** 2R / 48h / structural-extreme.
  The prereg fixed them so a losing arm could not be handed a second stop rule,
  which also means this says nothing about other exits.
* **One exchange, 333 days, 23 symbols.** The window includes one broad regime.
* **Fees are the harness's**, taker in, maker out on a win, taker out on a
  loss. A worse fill or any slippage makes the net numbers worse, never better.

## What this does not say

It does not say the CCP mark is meaningless to look at, and it does not say
grabs are not real. It says that **this** entry — market at `grabBar + 2`, stop
at the grab extreme, 2R, 48 hours — has no edge on this data, with or without
the CCP filter, and that the filter does not sort the grabs.

## Consequence

`riptide-ccp.pine` stays what it is: a bench that draws a classification. **No
entry layer, no stop, no target, no grade, no outcome tracking, no alerts** —
the same terms `riptide/watch.py` already set for the trendline, and for the
same reason.

Order blocks and FVGs get **their own prereg and their own run**. They are not
folded into this study to rescue it: a filter chosen after seeing these
residuals is a fit, not a filter. And the gross diagnostic sets the bar they
have to clear — since expectancy at a grab is zero before costs, an order-block
or FVG condition has to *manufacture* edge, not merely select where it already
lives. On this evidence the first thing such a study should test is whether its
own control, entering at every grab with the same rules, is distinguishable
from it at all.
