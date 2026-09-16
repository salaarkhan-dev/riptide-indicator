# "We just need more filtering conditions" — what that actually buys

    python3 indicators/ccp/studies/ccp_filter_overfit.py

A method diagnostic, not a study of the market. No prereg, no verdict. It runs
the procedure the phrase describes — look at which trades failed, find a
condition that excludes them — and then checks the result on data that
condition has never seen.

Fourteen ordinary conditions, every single and every pair, **105 candidates**
that keep at least 150 bets a side. Best one chosen on the OLDER half, then
looked at on the NEWER half.

## The result

| | Min15 | Min30 | Min60 |
|---|---|---|---|
| no filter, older | −0.080 | −0.059 | −0.003 |
| no filter, newer | −0.089 | −0.071 | −0.068 |
| **best filter, in-sample** | −0.003 | **+0.089** | **+0.078** |
| **the same filter, out-of-sample** | −0.038 | **−0.082** | **−0.032** |
| what it gave back | −0.035 | **−0.171** | **−0.110** |
| candidates beating zero, older half | 0 / 105 | 26 / 105 | 50 / 105 |
| candidates beating zero, newer half | 4 / 105 | 1 / 105 | 5 / 105 |
| rank correlation, in vs out | +0.573 | +0.031 | +0.067 |

**On Min60, half of all candidate filters looked profitable on the older half.
Five survived on the newer half — about what chance alone produces.** The best
of them, "grab wick big + grab closed back hard", went **+0.078 → −0.032**. On
Min30, "EMA50 rising + level held long" went **+0.089 → −0.082**, giving back
nearly twice what it appeared to make.

Neither of those is a bad filter. Both are things a reasonable person would
reach for after looking at a losing trade. That is the point: **the conditions
are not the problem, the selection is.** Choosing the best of 105 candidates on
past data is choosing the luckiest one, and luck does not repeat.

## Where I was wrong

I said filter selection here would be "a coin flip wearing a rationale", and
predicted a rank correlation near zero everywhere. **Min15 came back at
+0.573**, which is not near zero, and the claim as stated was too strong.

The explanation does not rescue the idea, but it is worth having right.
On Min15 **not one candidate out of 105 beat zero in-sample.** With nothing
positive to select, what the correlation measures is that the conditions rank
consistently by *how bad* they are — real information, and information that
"lose less" is all that is on offer. On Min30 and Min60, where selection
actually had winners to pick from, the correlation is **+0.031 and +0.067**:
essentially zero, exactly where it matters.

So the accurate statement is narrower and, I think, worse for the idea:
**relative ranking persists; profitability does not.** The ordering of
conditions carries signal. What it consistently orders is degrees of losing.

## Why no filter can fix this one

`research/CCP_ENTRY_MODELS.md` measured gross expectancy at a grab at about
**zero**. A filter partitions a population; it cannot add to its total. On a
set averaging zero, every profitable subset is exactly balanced by an
unprofitable one, so a positive subset always exists in any sample and finding
it is free. Whether the same split is positive next year is the only question,
and the table above is the answer for this family of conditions.

`indicators/ccp/studies/ccp_excursion.py` puts a ceiling on it independently: after a
grab, price beats a risk-matched random entry by about **1.5 points** on the
+1R-first race — roughly **+0.03 R** — against a measured fee drag of **0.05 to
0.14 R**. That is the entire edge budget in the population. A filter
redistributes it. It cannot mint more.

## What would be different

A filter with a **mechanism**, named before anyone looks at which trades it
excludes, and tested on held-out data. That is a different object from a
condition mined out of the failures, and it gets a prereg, a fixed arm list and
a stated family size — the same treatment `PREREG_ccp_entry_models.md` and
`PREREG_ccp_exit_models.md` got.

The honest prior for such a study, given the two ceilings above, is that it has
to **create** edge rather than sort an average of zero. Order blocks and FVGs
are the named candidates. Nothing here says they cannot work; it says they do
not get to be chosen by looking at this study's residuals.
