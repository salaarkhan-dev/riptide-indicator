# PRE-REGISTRATION — the complement, and whether the 1h cell replicates

Committed before the first number. Run by
`indicators/undertow/studies/undertow_complement.py`.

## The question, and it is not a new idea — it is a replication

[`UNDERTOW_STRICT.md`](../measurements/UNDERTOW_STRICT.md) measured the priority
shape as a gate. It was an exact subset, so its complement was exact too, and
the page reported the two halves of the same population against each other:

| tf | priority half | **the other half** | diff | z |
|---|---|---|---|---|
| Min15 | −0.067 | −0.129 | −0.062 | −0.66 |
| Min30 | −0.040 | −0.003 | +0.037 | +0.36 |
| **Min60** | **−0.062** | **+0.197** | **+0.258** | **+2.46** |

**On 1h the shapes the strategy calls second-best — the hanging man in a
bullish trend, the inverted hammer in a bearish one — scored +0.197 R per trade
at a 27.3% win rate.** That is the only |z| ≥ 2 in eighteen studies and it
points against the author's stated priority.

That page refused to call it a result and gave the arithmetic: three cells
examined, ~14% chance one crosses |z| = 2 by luck, neighbours at nothing.
**This study is the only honest way to find out.**

## THIS IS A SELECTED CELL, SO THE DESIGN IS A REPLICATION, NOT A SEARCH

Everything about the shape of this study follows from one fact: **the
hypothesis was chosen because it was the largest of three numbers.** So

* **Min60 is the pre-registered PRIMARY timeframe**, named here, before the
  run. Min15 and Min30 are reported and cannot rescue a failed primary. Testing
  "whichever timeframe works" on a fresh set would repeat the original sin at a
  larger scale.
* **the effect size to beat is stated in advance**, not "positive".
* **a null is a real answer here and the most likely one.** Eighteen studies,
  no promotions; the prior on any one cell is what it always was.

## The arms

The complement can be read two ways and both are reported, because they are
genuinely different objects and the difference is informative.

| id | | |
|---|---|---|
| **I0** | what ships — both shapes | **THE BASELINE**, one run |
| **I1** | **the non-priority half of I0, as a SLICE** | **THE PRIMARY** |
| I2 | the priority half of I0, as a slice — `famStrict`'s trades | the contrast partner |
| I3 | the inverse gate as an actual RUN — `famStrict` + `famInvert` | descriptive |
| **C** | matched random gate on I0 at I1's discard rate | **THE CONTROL** |

**Why I1 is the slice and not the run.** The finding was a slice, so the
replication is of a slice. They are not the same object: with the inverse gate
running, priority-shaped pins never enter the candidate pool at all, so
`famPriority`'s rivalry — a non-priority pin does not displace a waiting
priority one — has nothing to act on and the surviving set can differ. I3 is
there to say how much that matters, because **I3 is the version you could
actually put on a chart** and I1 is the version that was measured.

`famInvert` is a **port-only** field. A chart input exists for a rule somebody
wants to trade; this one exists to be tested, and if it clears its bars it can
earn the input then.

## Population

**`SYMBOLS_FRESH11`** — 45 contracts, frozen for this study, disjoint from the
23 and from all ten earlier sets. 91–100k 24h turnover.

**A LIMIT WORTH STATING BEFORE THE RUN, NOT AFTER.** The primary timeframe is
the one with the least data. 12,000 bars of 1h is 500 days and these are
thinner, newer listings — FRESH7 could field only 30 of 45 symbols on Min60.
If Min60 comes back under 20 symbols the prereg's own rule says **NOT
REPORTED**, and this study simply has no primary. That outcome is written down
here so it cannot later be presented as anything other than what it is: the
question unanswered, and one more set of 45 left in the venue to answer it.

* 12,000 bars, Min15 / Min30 / Min60, ≥ 11,000 bars or dropped
* a timeframe with fewer than 20 surviving symbols is **not reported**

## What must be IMPOSSIBLE

* **THE SLICES PARTITION THE BASELINE.** Every trade of I0 is in exactly one of
  I1 and I2, and `|I1| + |I2| == |I0|`. This is the property the original
  finding rests on; if it does not hold, the −0.258 was not comparing two
  halves of one thing.
* **I1 CARRIES ONLY THE NON-PRIORITY CODES.** Every I1 trade is `IH` when short
  and `HGM` when long. **Zero `HAM`, zero `SS`.** Not a threshold.
* **I2 CARRIES ONLY THE PRIORITY CODES**, the mirror of the above, and it must
  reproduce `famStrict`'s own arm exactly — same count, same mean to 1e-12. If
  the slice and the gate disagree, one of them is not what
  UNDERTOW_STRICT.md measured.
* **`nCap` is 0 in every arm.**

Any of these firing makes the run **VOID** and the numbers are not published.

## Pre-registered bars, on I1, **on Min60**

1. **COVERAGE.** ≥ 200 closed trades, and ≥ 20 symbols on Min60.
2. **NOT CONFOUNDED.** All four impossibilities hold.
3. **THE CONTRAST REPLICATES.** I1 − I2 ≥ **+0.10 R per trade** at clustered
   |z| ≥ 2. *At the original's standard error of ~0.105 the binding half of
   that is the z, which needs roughly +0.21 — so this bar is asking the effect
   to come back at about four fifths of its original size, not at any size.*
4. **BEATS ITS CONTROL.** I1 ≥ 1 SE above the matched random gate.
5. **POSITIVE.** I1 mean R per trade > 0 after fees.
6. **THE SIGN HOLDS SOMEWHERE ELSE.** I1 − I2 > 0 on at least one of Min15 /
   Min30 — **sign only, significance not required.** On FRESH7 it was positive
   on Min30 and negative on Min15, so this bar is satisfiable and was not
   satisfied by the primary alone.

## The decision rule

* **I1 clears 3, 4, 5 and 6** → the first replicated positive finding in this
  project. `famInvert` goes on the chart as an input, OFF, with this page next
  to it. **It does not become a default on two studies.** A third confirmation
  on the last remaining fresh set is what a default would take, and the prereg
  for it gets written before this one is read a second time.
* **I1 clears 3, 4 and 5 but not 6** → a 1h-only effect. Same outcome, and the
  page says "1h only" in its title.
* **NULL** → the FRESH7 cell was the ~14% coincidence its own page predicted.
  That is worth having: it closes the one open question in the programme and it
  is the cheapest possible price for not trading on it. `famInvert` stays
  port-only and the taxonomy stays a naming scheme.
* **I1 − I2 NEGATIVE at |z| ≥ 2** → the original reversed on fresh data, which
  is stronger evidence against the shapes carrying information than either page
  alone, and it gets said plainly.

## My prediction, recorded before the run

* **NULL. I1 − I2 on Min60 lands between −0.10 and +0.10.** The base rate for
  a selected cell of three is what it is, and I have no mechanism to offer for
  why the second-choice candle should be the better trade. UNDERTOW_PIN_VALUE.md
  found the taxonomy adds nothing in either direction, which is the reading
  most consistent with everything measured so far.
* **I1 fails bar 4** as well, on the same reasoning that has held eighteen
  times.
* **I3 ≈ I1 to within 0.05**, i.e. the rivalry effect is small and the
  tradeable rule behaves like the slice. I hold this loosely — it is the part
  of the design I am least able to predict, which is exactly why I3 is here.
* **Min60 fields 25–35 symbols**, enough to report, on FRESH7's 30 of 45.
* **I would rather be wrong.** Eighteen negatives is a well-run programme and a
  boring one, and this is the only positive number the project has produced. If
  it survives, it is the first thing here worth trading and it arrived by
  measurement rather than from a diagram — which is the outcome the whole
  apparatus was built for.

## What cannot happen

* **No other timeframe may be promoted to primary**, whatever it shows.
* **No third slice, no re-cut of the taxonomy, no "HGM only" or "IH only"
  sub-arm.** Those are four more cells on a page that already paid for looking
  at three.
* **No falling back to an earlier universe.** FRESH7 is where the finding came
  from and is spent; FRESH8, FRESH9 and FRESH10 are spent. 75 unused contracts
  remain after this set, which is one more study and not two.
* **No change to the taxonomy, the levels, the exit or the bias.**
* **No exchange API key and no order placement.**
* **One study, one run.**
