# MTF as the default loses to what ships — and the baseline is the interesting number

Against [`PREREG_undertow_mtf_default.md`](../prereg/PREREG_undertow_mtf_default.md).
`SYMBOLS_FRESH3`, ranks 91–135, disjoint from the 23 and from both earlier
fresh sets. One arm fixed in advance, scored once.

**Context: the alternative bias sources were removed from the chart by hand
while this was running.** The decision did not wait for the number and did not
need to. The run is published anyway, because a committed prereg with no result
is the file-drawer problem the discipline exists to stop.

## The verdict

| tf | D1 (MTF) | D0 (ships) | Δ | z | random gate | n | D1 trades/d | D0 trades/d | bars |
|---|---|---|---|---|---|---|---|---|---|
| Min15 | −0.053 | **+0.063** | −0.116 | −1.74 | −0.060 | 8045 | 1.61 | 0.60 | PP... |
| Min30 | −0.023 | **+0.016** | −0.039 | −0.61 | −0.033 | 7125 | 0.77 | 0.27 | PP... |
| Min60 | −0.057 | −0.067 | +0.010 | +0.12 | −0.033 | 4271 | 0.41 | 0.15 | PP... |

**Bars 3, 4, 5 and 6 all failed. MTF does not earn the default**, and on the
two timeframes where it matters most it is *worse* than the shipped
configuration rather than merely no better.

## The impossibility held, which validates the previous page

D1 (MTF, shipped Ending) and D1b (MTF, retrace-only) were **bit-identical on
all three timeframes** — same trades, same mean, same setup count.

That was pre-registered as a void condition, and it confirms the thing it was
written to confirm: for a non-structure source the structure-reading Ending
rules are inert, so `UNDERTOW_MTF_EMA.md`'s decision to match Ending rules
across arms did not distort its MTF arm. Only the baseline moved between that
study and this one.

## THE NUMBER I DID NOT EXPECT, and why it is not yet a finding

**D0 — the structure engine in its shipped configuration — is positive on two
of three timeframes on a universe nothing here had seen**: +0.063, +0.016,
−0.067. Nothing in ten studies has done that.

And the shipped Ending rules appear to be what does it:

| D0 − D2 (shipped Ending vs retrace-only) | Min15 | Min30 | Min60 |
|---|---|---|---|
| **here, on `SYMBOLS_FRESH3`** | **+0.104** | **+0.035** | +0.005 |
| `UNDERTOW_BIAS_SOURCE.md`, on the original 23 | **−0.142** | **+0.149** | −0.028 |

**Four reasons not to believe it, and they are the whole point of writing it
down rather than acting on it:**

1. **It is uncontrolled.** `endMinor = "on the flip"` cuts trades from 8,451 to
   3,002 on 15m — it discards **64%** of them. Any rule discarding 64% moves
   the mean, and about half of all such rules move it up. This study built a
   matched random-gate control and pointed it at D1, not at D0. The contrast
   that looks interesting is the one without a control.
2. **It is not significant.** +0.063 ± 0.059 is z ≈ 1.07 against zero. The
   other two are z ≈ 0.29 and −0.92.
3. **It flips sign against its own previous measurement.** The same contrast on
   the original 23 gave −0.142 on 15m where this gives +0.104. That is the
   fourth time a number in this project has inverted between populations, and
   the prereg predicted "a fourth uninformative answer" — this is what
   uninformative looks like.
4. **It contradicts the ablation.** `UNDERTOW_PIN_VALUE.md` arm A5 removed
   *all* the Ending rules and scored **better** than keeping them on two of
   three timeframes, over 11,000–12,000 trades. That is a bigger sample saying
   the opposite.

**What it earns is a prereg, not a default change**, and the shape is already
clear: `endMinor` on / off, scored on a fourth fresh universe, against a random
gate matched on its 64% rejection rate. That control is the whole question. If
`endMinor` beats a coin discarding the same count, it is the first thing in
this project to beat a control; if it does not, then "the bias gate helps" is
finally settled as "trading less helps", which is a fact about position count.

## Against the prediction

| predicted | actual | |
|---|---|---|
| D1 == D1b | held on 3 of 3 | right |
| nothing clears bar 3 or 4 | nothing did | right |
| D0 − D2 is a fourth uninformative answer | it inverted in sign against the first | right |
| D1 − D0 within ±0.05 of the published M1 − M0 | out by −0.125, −0.089, +0.083 | **wrong** |
| D1 produces FEWER trades/day than D0 | **more** — 1.61 vs 0.60 on 15m | **wrong** |

Both misses have one cause: I treated the baseline's Ending rules as a small
correction. They are not. `endMinor` is the largest single filter in this
strategy — bigger than the candle, bigger than the location, bigger than MTF's
abstain state — and I had been comparing against a baseline with it switched
off without registering how much that changed.

## Coverage note

Min60 kept only **21 of 45** symbols at the 11,000-bar floor; ranks 91–135 are
newer listings and many do not have 500 days of hourly history. Min15 kept 40
and Min30 kept 37. The Min60 row is thin and should be read as the weakest of
the three.

## What changes

**Nothing, and the chart had already changed for other reasons.** `biasSrc`
would have stayed `structure` on this result alone; separately, every
alternative source was removed from the Pine while this ran. The port keeps
them so this page and the three before it keep reproducing.

**One thing is added to the queue**: the `endMinor` contrast above, with the
control it needs. It is the first number in this project that looked
interesting for a reason other than a maximum being taken, and it is also the
first one where the obvious confound is measurable rather than structural.
