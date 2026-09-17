# The overlapping trades are not a drawing bug. Three in four of them overlap.

Run by [`undertow_overlap.py`](../studies/undertow_overlap.py). 23 symbols,
12,000 bars each, shipped settings, `maxLive` 64, 7bp fees.

**Descriptive. No arms, no selection, no holdout, and therefore no prereg** —
it reports a property of the configuration that ships and chooses nothing.

## The question

A chart of ETH on 15m showed four LONGs inside ten dollars of each other, their
zone boxes and price labels piled on top of one another. The first thing worth
knowing is whether that is a drawing problem or something the strategy does.

## The answer

A **group** is a maximal set of trades on one symbol, in one direction, whose
`[fill, exit]` intervals transitively overlap — the operational meaning of "I am
in four of these at once".

| tf | trades | groups | per group | biggest | % of trades in a group of 2+ | groups that resolve UNANIMOUSLY | median group span |
|---|---|---|---|---|---|---|---|
| Min15 | 1714 | 844 | 2.03 | **13** | **73.7%** | **77.6%** | 8.5 h |
| Min30 | 1571 | 924 | 1.70 | 8 | 65.6% | 84.6% | 14.0 h |
| Min60 | 1658 | 1081 | 1.53 | 8 | 56.6% | 87.0% | 22.0 h |

**On 15m, three trades in four are running alongside another in the same
direction, up to thirteen at once — and when they overlap, four in five win or
lose together.** That is not four trades. It is one idea at four times the
size, and the risk is four times what the R figures imply.

The unanimity is the number that matters. Two overlapping longs on the same
symbol share a stop region and a target region; price resolves both or neither.
The 78–87% is the measurement of exactly that.

## What this does NOT mean

**It does not mean the measurements are wrong.** Every study here clusters its
standard error by **symbol**, and a symbol's trades are a superset of its
time-overlapping groups — the coarser clustering already absorbs this one. The
published SEs are, if anything, conservative.

What has no clustering at all is **the panel on the chart**, which reads
`26 / 58` as though those were 84 independent draws. Grouping instead of
counting widens the error bar by:

| tf | mean | SE per trade | SE per group | ratio |
|---|---|---|---|---|
| Min15 | −0.021 | 0.046 (n 1714) | 0.059 (n 844) | **×1.27** |
| Min30 | +0.017 | 0.048 (n 1571) | 0.059 (n 924) | ×1.21 |
| Min60 | −0.007 | 0.046 (n 1658) | 0.055 (n 1081) | ×1.17 |

So the panel's win rate is real, and it is about 20% less certain than its
sample size suggests.

## What changed, and what deliberately did not

**Changed — the chart only.** A new display setting, `Overlapping setups`,
default `collapse`: the first fill of a group draws in full, the rest keep a
faint entry line and a small `▲ ×3` badge. **No counter moves.** `entered`,
`won / lost` and `net R` count every fill either way, which is why the badge
carries the group size instead of hiding it.

**Not changed — the strategy.** Collapsing is cosmetic. It does not stop
Undertow taking four correlated longs. Taking fewer of them is a rule change, it
would alter every number on every page here, and it has not been measured.

## The tempting number, and why it decides nothing

Keeping only the **first** trade of each group:

| tf | all trades | first of each group | delta |
|---|---|---|---|
| Min15 | −0.021 ± 0.065 (n 1714) | **+0.071** ± 0.062 (n 844) | +0.092 |
| Min30 | +0.017 ± 0.063 (n 1571) | +0.054 ± 0.050 (n 924) | +0.037 |
| Min60 | −0.007 ± 0.058 (n 1658) | +0.005 ± 0.049 (n 1081) | +0.012 |

Positive on all three, and it turns every timeframe from roughly zero to
positive. **It is not evidence.** It is in-sample on the entire dataset, there
is no holdout, and it was computed *after* the overlap was already known to be
worth investigating. Adopting a rule on a number found this way is precisely
the error [`CCP_FILTER_OVERFIT.md`](../../ccp/measurements/CCP_FILTER_OVERFIT.md)
records: +0.089 in sample, −0.082 out.

There is also a mechanical reason to expect *some* of it for free. Later
entries in a group are worse prices in the same move, so dropping them should
raise mean R per trade a little whether or not the rule is any good. Separating
that from a real effect needs a control, which this does not have.

**If it is worth pursuing, it is worth a prereg** — arms, a holdout quadrant, a
random-entry control, and bars fixed before the run, like the other seven. The
denominator would have to be R per GROUP rather than per trade, since the whole
point is that the group is the bet.
