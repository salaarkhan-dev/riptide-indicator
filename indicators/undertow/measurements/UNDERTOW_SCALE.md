# The scale study is VOID, and the thing that voided it is a real finding

Against [`PREREG_undertow_scale.md`](../prereg/PREREG_undertow_scale.md).
`SYMBOLS_FRESH8`, 41 / 39 / 31 symbols. **The arm numbers are not published,
because the prereg says a fired impossibility means they are not published.**

## What fired

> **S0 and S2 fire CHoCH on the SAME BARS.** `smc.py` and
> `test_undertow_port.py` both assert the two engines' CHoCH lists are
> identical at a given pivot length; S0 and S2 run both engines at 6/2, so on
> fresh data the count must match.

It fired on all three timeframes, and only just:

| tf | SMC at 6/2 | riptide at 6/2 | differ |
|---|---|---|---|
| Min15 | 11,235 | 11,246 | 11 |
| Min30 | 10,541 | 10,550 | 9 |
| Min60 | 8,419 | 8,432 | 13 |

**0.1%.** Not a wiring failure — which is exactly what the impossibility was
written to catch — but the rule as written is "must match", it did not, and
reinterpreting an impossibility after seeing the numbers is the one thing
pre-registration exists to prevent. **Void.**

## The diagnosis, on a spent universe

`SYMBOLS_FRESH6`, 39 symbols, length 6: **17 divergences out of 10,930 events,
and every single one is the series' FIRST structure break.** Nothing else
differs, on any symbol, anywhere.

| | divergences |
|---|---|
| the series' first structure break | **17** |
| anything else | **0** |

The cause is initialisation, and it is not subtle once seen:

| | at bar 0 | so the first break is |
|---|---|---|
| **LuxAlgo** | `bias = 0`, neither bullish nor bearish | a **BOS** — `bias == BEARISH` is false |
| **riptide** | `msOs = 0`, which *means* bearish | a **CHoCH** if it is upward — the state flipped |

A symbol whose first break is downward agrees exactly. One whose first break is
upward differs by one event, on bar ~13 of 12,000. **After that first break the
two lists are identical.**

## What this falsifies, and it is mine

[`smc.py`](../port/smc.py) has said since it was written that the two engines'
CHoCH bars are *"not 'similar' — the same list"*, and
`test_undertow_port.py` asserted `a == b`. Both were checked on **one
synthetic random walk**, which happens to break downward first, so the only
case where they differ never occurred.

That claim is now corrected in both places. The test asserts what is actually
true — the lists agree except, at most, the first break, and agree exactly
after it — and it would have caught this on the day it was written.

**The impossibility was badly specified and that is the more useful lesson.**
It was meant to say *"a pivot length reached the detector"*. It said *"two
engines agree to the event"*, which is a much stronger claim, and one this
repository had written down without ever testing on real candles. A wiring
check should assert the thing it is checking for.

## What this costs

**`SYMBOLS_FRESH8` is spent for this question.** The numbers were computed and
I have seen them, so re-running the same arms on the same symbols would not be
a fresh test whatever the prereg said. A re-run needs `SYMBOLS_FRESH9` and a
corrected impossibility.

**And the contamination is worth naming rather than managing quietly.** Having
seen a void result, I am no longer a neutral party to the re-run: if the second
answer differs from the first there is an obvious temptation, and the only
protection is that FRESH9 is untouched and the prereg is fixed before it runs.
A reader is entitled to weigh that.

## What is NOT affected

* **No default changed**, on the chart, in the port or in the watch.
* **No published page moves.** Every measurement in this directory pins
  `biasSrc=BS_STRUCT` and runs riptide's engine; the correction above concerns
  one event per symbol at the very start of a series, and none of those pages
  scores a trade in the first fifteen bars.
* **The 50/5 scale is still unmeasured.** That is the whole point of this page:
  the question is open and the attempt to close it failed for a reason that had
  nothing to do with the question.
