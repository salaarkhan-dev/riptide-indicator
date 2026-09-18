# The 1h cell kept its sign, lost half its size, and cannot be settled on this venue

Against
[`PREREG_undertow_complement.md`](../prereg/PREREG_undertow_complement.md).
`SYMBOLS_FRESH11`, 45 / 44 / 29 symbols, scored once. All five pre-registered
impossibilities hold. **Min60 was the pre-registered primary, named before the
run.**

## The verdict

| tf | I1 other half | I2 priority half | **I1 − I2** | z | I0 ships | control | n | bars |
|---|---|---|---|---|---|---|---|---|
| Min15 | +0.005 | −0.029 | +0.034 | +0.41 | −0.016 | −0.001 | 812 | PP..P |
| Min30 | −0.110 | −0.008 | −0.101 | −1.20 | −0.048 | −0.088 | 795 | PP... |
| **Min60 ·PRIMARY** | **−0.008** | **−0.125** | **+0.117** | **+1.03** | −0.082 | −0.076 | 422 | PP... |

**NULL.** Bars 3, 4 and 5 fail on the primary. `famInvert` stays port-only.

## What actually happened, and it is not a clean reversal

| tf | FRESH7, where it was found | FRESH11, out of sample |
|---|---|---|
| Min15 | −0.062 | +0.034 |
| Min30 | +0.037 | −0.101 |
| **Min60** | **+0.258 ± 0.105** | **+0.117 ± 0.114** |

**The sign held on the primary and the size halved.** That is the textbook
shape of a cell selected as the largest of three: the winner's curse says a
point estimate chosen for being extreme is biased upward, and the unbiased
reading is whatever the next sample says. The next sample said +0.117.

**Read the bars precisely, because one of them looks closer than it was.** The
pre-registered bar was *+0.10 R **at |z| ≥ 2***. The effect came in at +0.117,
which clears the size half — and at z 1.03, which misses the significance half
by a distance. Both halves were in the prereg for exactly this reason: a bar
with only a size threshold would have passed here on a number that is one
standard error from zero.

Note also bar 5. `I1` itself is **−0.008 R**, a hair below break-even, at a
22.7% win rate against the fee-inclusive line of 22.9%. The half that scored
+0.197 on FRESH7 scores nothing here. What survived is only the *contrast* — the
priority half did worse still, at −0.125.

## THE PART THAT MATTERS MOST: THIS CANNOT BE SETTLED HERE

If the true effect is the replication's +0.117, then detecting it at |z| ≥ 2
needs a standard error of 0.059 — **half of what 422 trades bought, so roughly
four times the trades: about 1,600 on 1h, which is around 110 symbols.**

**There are 75 unused contracts left on the venue.** FRESH11 took the count from
120 to 75, and 1h is the timeframe where the fewest of them carry 500 days of
history — 29 of 45 here, 30 of 45 on FRESH7. One more set of 45 would add
perhaps 30 usable 1h symbols, reaching 59. That is not 110.

So the honest close is not "the effect is absent". It is:

> **An effect of this size at this timeframe is below the resolution of this
> venue, and no further study on it can change that.** A third set would be
> spent producing another number with a standard error near 0.09 — enough to
> re-state the question and not to answer it.

## Do not pool the two studies

Somebody will, so here it is: inverse-variance weighted, FRESH7 and FRESH11
combine to **+0.193 ± 0.077, z +2.50.**

**That number is not valid and should not be quoted.** The first sample was
*selected* as the maximum of three cells; its point estimate carries the
selection bias that the replication exists to remove. Pooling a discovery with
its replication propagates the bias into the combined estimate and manufactures
significance out of the thing being tested. The unbiased estimate of this
effect is the out-of-sample one alone: **+0.117 ± 0.114**.

## Against the prediction

| predicted | actual | |
|---|---|---|
| NULL | null | right |
| I1 − I2 on Min60 between −0.10 and +0.10 | **+0.117** | **wrong, marginally** |
| I1 fails bar 4 | failed, +0.068 ± 0.132 | right |
| I3 ≈ I1 to within 0.05 | −0.042 / −0.027 / −0.033 | right |
| Min60 fields 25–35 symbols | 29 | right |

Two things worth keeping. The prediction I got wrong was wrong in the
*interesting* direction and only just — the effect landed 0.017 outside the
band I called. And `I3 − I1` came in **negative on all three**: the tradeable
inverse gate is consistently a little worse than the slice, so the rivalry
effect the prereg flagged is real, small, and costs rather than pays. That
matters if anyone revisits this: the version you could put on a chart is the
worse of the two objects.

## What changes

**Nothing ships.** `famInvert` stays port-only with no chart input, which is
what the prereg said a null would mean.

**And the open question closes.** [`UNDERTOW_STRICT.md`](UNDERTOW_STRICT.md)
called its 1h cell "the best-supported candidate this project has produced for
its own pre-registration" and gave it a ~14% chance of being coincidence. It
got its pre-registration, on a universe frozen for it, with its primary
timeframe named in advance. The result is a halved effect one standard error
from significance and a venue too small to resolve it.

That is the cheapest possible price for not trading on a number that came from
looking at three cells — one universe, and the question answered as well as it
can be.

Nineteen components measured. None promoted.

## The bookkeeping

`SYMBOLS_FRESH11` is now spent. **75 unused contracts remain**, which is one
more set of 45 and nothing after it, and the band has thinned from FRESH8's
122–1230k to this set's 91–100k. The next study to want a fresh universe is the
last one that can have a full-sized disjoint set.
