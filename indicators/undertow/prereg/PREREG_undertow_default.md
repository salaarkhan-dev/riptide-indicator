# PRE-REGISTRATION — the shipped configuration, all of it

Committed before the first number. Run by
`indicators/undertow/studies/undertow_default.py`.

## The question, and twelve studies have not asked it

Every page in [`../measurements`](../measurements) measures a **component**:
one anchor, one gate, one scale, one bias source. Not one of them measures the
**chart somebody would actually trade**, and the chart has moved a long way
from the configuration those pages were produced on.

In a single day the shipped defaults changed in four independent ways:

| | was | now |
|---|---|---|
| `biasSrc` | SMC structure, 14/5 | **market structure + inducement**, 50/3 bar pivots, SMC internal tier |
| `famStrict` | off | **on** — only the priority shape arms |
| `armWins` | off | **on** — first to complete W→F drops its rivals |
| `stopSrc` | pullback extreme | **minor swing extreme** |

**This study measures that package against the one it replaced.** It is the
last question this programme can ask on a fresh universe, and it is the one
worth asking: a chart nobody has measured is not made trustworthy by twelve
pages about its parts.

## THE CONTROL, and the measured fact that decided it

`SYMBOLS`, the spent 23, at `maxLive 64`:

| tf | old default | new default | shared | **new only** |
|---|---|---|---|---|
| Min15 | 1,101 | 395 | 321 | **74 (19%)** |
| Min30 | 1,104 | 374 | 307 | **67 (18%)** |
| Min60 | 1,104 | 402 | 329 | **73 (18%)** |

**81% of the new default's trades are also the old one's, and 19% are not.**
That is the awkward middle: neither the strict subset of
[`PREREG_undertow_strict.md`](PREREG_undertow_strict.md) nor the relocation of
[`PREREG_undertow_anchor.md`](PREREG_undertow_anchor.md).

**So the seeded random ENTRY is the primary control, and the matched random
gate is descriptive — which is the opposite of what 81% suggests.** The reason
is that a gate draws only from the old population, so it can never produce the
19% the new default takes and the old one does not. If those trades are good
the gate comparison flatters the new default by construction. The random entry
has no such bias because it is matched to the arm rather than drawn from the
baseline. The gate is still reported, because for the 81% it is the harder
test, and its bias is named on the page rather than left for a reader to find.

## The arms

| id | | |
|---|---|---|
| **D0** | what the chart shipped yesterday | **THE BASELINE** |
| **D1** | **what the chart ships today** | **THE PRIMARY** |
| **C** | seeded random entry matched to D1 | **THE CONTROL** |
| G | matched random gate on D0 at D1's rate | descriptive — biased toward D1, see above |
| L1 | D1 with `famStrict` off | descriptive — leave-one-out |
| L2 | D1 with `armWins` off | descriptive |
| L3 | D1 with the pullback stop | descriptive |
| L4 | D1 with `biasSrc` back to SMC 14/5 | descriptive |

**THE LEAVE-ONE-OUT LADDER IS NOT A SEARCH AND MAY NOT BE PROMOTED.** Four
things changed at once and a bare null would say nothing about which of them to
reconsider — with no universe left to ask again, that would waste the last set.
Each L arm answers one question fixed in advance: *what does this single change
contribute to the package?* The primary is D1 and only D1, named here, before
the run. Promoting the best L would be a best-of-five selection, which
[`UNDERTOW_PARAMS.md`](../measurements/UNDERTOW_PARAMS.md) priced at −0.31 R per
trade of illusion.

Everything not named in an arm is the shipped configuration and identical
across arms: `rr` 3.5, 7bp, `locTol` 0, `pinAt` the pullback extreme, retrace
70, `endMinor` on the flip, `maxLive 64`.

## Population — and there is no next one

**`SYMBOLS_FRESH12`** — 45 contracts, 86–156k 24h turnover, disjoint from the
23 and from all eleven earlier sets.

**IT IS THE LAST SET OF THIS SIZE.** 592 contracts pass the filter, 518 were
already spoken for, 74 were unused. This takes 45 and leaves **29** — which
will not field 20 symbols on Min60 and so cannot report the timeframe most of
these questions are asked on. The disjoint-holdout method this repository has
run twelve times ends here. A study after this one gets a thin tail that no
longer resembles the population every earlier page measured, or it gets a
different design: walk-forward on the spent sets, or the prospective forward
record the watch was built for.

Spending it on the shipped configuration rather than on one more component is
the right last use of it, and the reason is in the first section.

* 12,000 bars, Min15 / Min30 / Min60, ≥ 11,000 bars or dropped
* a timeframe with fewer than 20 surviving symbols is **not reported**
* 1h is the one at risk again: FRESH7 fielded 30 of 45 and FRESH11 fielded 29

## What must be IMPOSSIBLE

Five, each asserting one shipped element is actually live. Written to assert
the thing being checked, which two preregs ago they did not.

* **THE CONFIGURATION IS READ.** D1 ≠ D0 on trade count.
* **THE SHAPE GATE IS LIVE.** Every D1 trade carries the priority code — `HAM`
  when short, `SS` when long. **Zero `HGM`, zero `IH`.** Not a threshold: the
  gate admits nothing else by construction.
* **THE INDUCEMENT IS LIVE.** D1's trade count differs from the same
  configuration with `msBosNeedsIdm` off. If it does not, the rule that
  motivated the whole engine swap is not being read.
* **THE STOP IS THE MINOR SWING.** D1 ≠ L3. If the two agree the stop source
  is not being read and L3 is measuring nothing.
* **`nCap` is 0 in every arm.**

Any of these firing makes the run **VOID** and the numbers are not published —
and there is no universe left to re-run it on, which is the strongest reason
yet to have written them carefully.

## Pre-registered bars, on D1

1. **COVERAGE.** ≥ 200 closed trades.
2. **NOT CONFOUNDED.** All five impossibilities hold.
3. **BEATS WHAT IT REPLACED.** D1 − D0 ≥ **+0.10 R per trade**, clustered
   |z| ≥ 2.
4. **BEATS ITS CONTROL.** ≥ 1 SE above the seeded random entry.
5. **POSITIVE.** Mean R per trade > 0 after fees.
6. **NOT ONE TIMEFRAME.** Positive on ≥ 2 of 3.

## The decision rule

* **D1 clears 3, 4, 5 and 6** → the first *configuration* in this project to
  clear its bars, on a universe frozen for it. It stays the default and the
  page says so plainly.
* **NULL** → the defaults were set from a chart owner's preference against a
  spent-universe table, and nothing measured supports them. They stay, because
  they are the owner's to set, and the page says in its title that they are
  unsupported. The L ladder then says which one to reconsider first.
* **D1 is WORSE than D0 by more than 0.10 R at |z| ≥ 2 on ≥ 2 timeframes** →
  **the page recommends reverting**, names the L arm carrying the damage, and
  says so in the first line. That branch is written down here because a study
  that cannot recommend against the thing it measures is not a measurement.

## My prediction, recorded before the run

* **NULL, and D1 fails bar 4.** Nineteen components measured, none has beaten a
  control.
* **D1 − D0 lands between −0.10 and +0.10.** The spent-23 table that prompted
  this gave +0.128 / −0.050 / +0.080 for the same contrast — disagreeing across
  timeframes, which is what noise looks like at n≈400.
* **L1 is the largest single contributor and it is NEGATIVE** — i.e. turning
  `famStrict` off IMPROVES D1. [`UNDERTOW_STRICT.md`](../measurements/UNDERTOW_STRICT.md)
  already measured that gate on its own universe at −0.067 / −0.040 / −0.062,
  below its matched control on two of three, and nothing since has argued the
  other way.
* **L4 is near zero.** The engine swap is the change I have least reason to
  expect anything from: UNDERTOW_V2.md scored an engine swap at +0.002 / +0.065
  / +0.006 and the detectors are the same expression.
* **Win rates near the fee-inclusive line**, 22.9–23.5%.
* **Min60 fields 25–32 symbols.**

## What cannot happen

* **No promotion of any L arm**, and no fifth L.
* **No re-tuning.** Not the pivot lengths, not the RSI levels, not `rr`.
* **No falling back to an earlier universe.** All twelve are spent.
* **No exchange API key and no order placement.**
* **One study, one run.**
