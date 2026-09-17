# v3, the corrected anchor: the fourteenth null — and the break-even line was wrong all along

Against [`PREREG_undertow_v3.md`](../prereg/PREREG_undertow_v3.md).
`SYMBOLS_FRESH6`, ranks 226–270, disjoint from the 23 and from all five earlier
fresh sets. One primary — the whole v3 stack — fixed in advance, scored once.

## The verdict

| tf | W1 v3 | W0 v1 | Δ | z | control | n | win% | prio% | bars |
|---|---|---|---|---|---|---|---|---|---|
| Min15 | +0.002 | −0.008 | +0.011 | +0.11 | −0.055 | 736 | 23.5% | 65.8% | PP..P |
| Min30 | +0.014 | +0.009 | +0.004 | +0.05 | −0.017 | 679 | 23.4% | 67.9% | PP..P |
| Min60 | +0.041 | −0.006 | +0.047 | +0.36 | −0.056 | 531 | 23.7% | 70.6% | PP..P |

**Bars 3 and 4 failed on all three.** v3 is *positive* on 3 of 3 and above its
control on 3 of 3 — the first arm in this project to do either — and it clears
neither bar, because every margin is a third of a standard error. Both
pre-registered impossibilities held: `W2 ≠ W0` and `W1 ≠ W4`, so the anchor is
live and the run is not void.

Nothing is promoted. **The prereg's other clause is met**: W2 shows the anchor
is not actively harmful, so it goes on the chart as an input defaulting to the
old behaviour.

## THE FINDING THAT MATTERS MOST IS A CORRECTION TO THIRTEEN PAGES

Every page in this directory says break-even at `rr` 3.5 is **22.2%**, and
notes that every win rate measured lands on it. That is the break-even
**before costs**, and it is the wrong line.

The fee is charged in price and the trade is scored in R, so the drag is
`fee / risk` — and risk is about 1.3% of entry on 15m and 2.4% on 1h. Same
fee, different R:

| tf | median risk | fee drag | **break-even win%** | W0's win% | W0's R |
|---|---|---|---|---|---|
| Min15 | 1.26% | 0.055 R | **23.5%** | 23.6% | −0.008 |
| Min30 | 1.62% | 0.043 R | **23.2%** | 23.6% | +0.009 |
| Min60 | 2.38% | 0.029 R | **22.9%** | 22.9% | −0.006 |

**The shipped rule's win rate matches its own fee-inclusive break-even to a
tenth of a point on all three timeframes**, and its R per trade is zero to
three decimals. That is a cleaner statement of the thirteen nulls than the
22.2% line ever was: the entries are not *near* break-even after costs, they
are *on* it, and the line they sit on moves with the timeframe in exactly the
way the fee arithmetic says it should.

It also retires a small false hope from this study. Every win rate here is
above 22.2%, which under the old line would have read as the first edge in the
project. Against the right line it reads as nothing at all.

## THE 76.7% IN MY OWN PRE-REGISTRATION WAS AN ARTIFACT

The prereg's headline evidence for the anchor was that the priority shape's
share of pins moves from 51.1% to 76.7% with no priority rule applied. **It
does not survive the tolerance the same prereg requires.** FRESH6, Min15, armed
candidates:

| | armed | priority shape |
|---|---|---|
| v1 anchor, `locTol 0` | 4,320 | 50.0% |
| v1 anchor, `locTol 2` | 7,153 | 50.3% |
| **v3 anchor, `locTol 0`** | 1,234 | **75.6%** |
| v3 anchor, `locTol 1` | 3,166 | 53.2% |
| **v3 anchor, `locTol 2`** | 4,352 | **51.5%** |

**One bar of tolerance takes it from 75.6% to 53.2%.** The whole effect lives
at zero tolerance, and at zero tolerance it is close to definitional: the
pinned bar *is* the bar that made the leg low, so a green bar there has its low
below its body by construction — which is what a hammer is. It was never
evidence that the anchor finds a meaningful object. It was the anchor
describing itself.

I wrote that table into the prereg as support. It is the weakest reasoning in
this project's paperwork, and the arm list is what caught it: W2 reports 50.2%
/ 50.8% / 50.1%, which is v1's mix exactly.

**What is not an artifact**: W1 and W3 sit at 66–71% and 57–63%, so inside the
v2 stack the anchor does shift the mix. And **the v2 stack anchors the priority
shape only 16–20% of the time.** v2 was not neutral about the rule its author
stated; it was the reverse of it.

### Why v2 pins the second-choice shape, and the attribution I got wrong

The first version of this section said `pinNewest` causes it. One change at a
time on v1 says otherwise — FRESH6, Min15, bearish armed candidates, where the
priority shape is the hammer:

| | armed | hammer | inv. hammer |
|---|---|---|---|
| v1 as shipped | 2,881 | 48.9% | 51.1% |
| + `pinNewest` only | 461 | 43.2% | 56.8% |
| + W→F only | 1,953 | **60.1%** | 39.9% |
| + both | 279 | **30.1%** | 69.9% |
| the whole v2 stack | 723 | **18.0%** | 82.0% |

**`pinNewest` alone moves it six points. W→F alone moves it the other way.**
Only the two together collapse the mix, so the cause is an interaction and not
a component — which is what naming one without isolating it costs.

The mechanism is visible in how far each confirmation sits from the pin's own
close, as a fraction of that candle's range:

| | to W — a close above its high | to F — a close below its low |
|---|---|---|
| hammer | **0.11** | 0.89 |
| inverted hammer | 0.44 | 0.56 |

A green hammer closes near its high, so **W is nearly free**. Under W→F it
almost always gets its W in first and then waits for the F, while an inverted
hammer is a coin flip on which side arrives first and half are disqualified for
arriving F-first. That is the +11 points.

`pinNewest` then cancels that selection, because it leaves **one** candidate per
pullback chosen by recency rather than shape — so W→F never gets to do the
choosing, and the recency pick leans to the inverted hammer at the pullback
top. The remaining 30% → 18% is the rest of the stack, mostly `needBos`
(17.4% without it, so it is not the cause either).

### AND THAT MEANS v2 MEASURED THE ONE FORM OF THE RULE ITS AUTHOR DID NOT STATE

`famPriority` has effect only **inside** the `pinNewest` branch, by
construction, so there are three configurations and not two. FRESH6, Min15,
W→F throughout, bearish armed candidates:

| | armed | hammer | R per trade |
|---|---|---|---|
| neither — what ships | 1,953 | 60.1% | +0.046 ±0.069 |
| `pinNewest` only — pure recency | 279 | **30.1%** | **−0.115 ±0.137** |
| `famPriority` only | 1,953 | 60.1% | +0.046 ±0.069 — bit-identical, inert |
| **both — priority shape, newest of it** | 812 | **62.2%** | **+0.061 ±0.089** |

**Pure recency is the defective form**: the only row that pins the
second-choice shape 70% of the time, and the only negative one. The pairing is
the rule as stated — *"priority shape wins, newest of that shape"* — and it
holds the mix at 62% while halving the trade count rather than cutting it
sevenfold.

**`UNDERTOW_V2.md` therefore concluded against a rule nobody proposed.** L5
removed `pinNewest` from a stack that never had `famPriority` in it, so what it
scored was recency-only. That conclusion is correct about what it tested and
does not transfer to the pairing.

**NOTHING IS PROMOTED ON THIS TABLE AND IT MAY NOT BE.** +0.061 ±0.089 is 0.7
SE on one timeframe, and FRESH6 is a **spent universe** — this study used it for
its primary. Acting on a number found by looking again at data already scored
is the −0.31 R per trade [`UNDERTOW_PARAMS.md`](UNDERTOW_PARAMS.md) measured.
The pairing needs a fresh universe and a prereg of its own, and until it has
one both switches stay off.

## The anchor on its own — W2, and the only number worth another look

`W2 − W0` is **+0.023 / +0.023 / +0.054 R**, positive on 3 of 3 and inside one
SE on 3 of 3. That summary hides the interesting part, because W2 is not a
filter on W0 — it is a different population that happens to overlap:

| tf | shared | W0 only | **W2 only** |
|---|---|---|---|
| Min15 | −0.008 ±0.069, n 1836 | −0.008 ±0.096, n 1087 | **+0.054 ±0.076, n 1100** |
| Min30 | −0.012 ±0.043, n 1822 | +0.067 ±0.089, n 674 | **+0.107 ±0.081, n 1089** |
| Min60 | +0.025 ±0.077, n 1738 | −0.151 ±0.094, n 377 | **+0.089 ±0.092, n 987** |

**The trades the new anchor ADDS are positive on 3 of 3 and beat the shared
pool on 3 of 3.** None is significant — 0.7, 1.3 and 1.0 SE — and the trades it
DROPS are not consistently bad, which is the part that argues against reading
too much into it: on Min30 the dropped trades are *better* than the pool.

So the honest reading is that the anchor moves the population somewhere
slightly better, by an amount this study cannot separate from zero, and that
the effect would need roughly four times the data to resolve. **It is not
promoted and it is not a finding. It is the first thing here that is worth
measuring again rather than filing.**

## Leave-one-out and the descriptive arms

Distance from W0, the shipped rule:

| tf | W2 anchor only | W3 v3 without famPriority | W4 the v2 stack |
|---|---|---|---|
| Min15 | +0.023 | +0.063 | −0.045 |
| Min30 | +0.023 | −0.025 | −0.141 |
| Min60 | +0.054 | +0.148 | +0.051 |

**`famPriority` is the component that does nothing recoverable.** W1 − W3 is
−0.052 / +0.030 / −0.101: forcing the priority shape is *worse* on two of three,
on 354–490 trades, which is noise either way. The prereg predicted it would
barely move R per trade and that is the one prediction that came out clean.

**W4 confirms v2 on a sixth universe** — negative on two of three, and the one
positive is 0.5 SE. Two universes now agree that the v2 stack is not an
improvement on v1.

Descriptive arms may not be promoted. Best-of-five is selection, and it is the
−0.31 R per trade [`UNDERTOW_PARAMS.md`](UNDERTOW_PARAMS.md) measured as the
cost of picking from a chart.

## THE HONEST LIMIT

**v3 takes a quarter of v1's trades** — 0.15 / 0.07 / 0.04 a day per symbol
against 0.60 / 0.27 / 0.14 — so with n of 531–736 and SEs of 0.073–0.107 the
minimum detectable effect is about **±0.20 R per trade**, not the ±0.10 bar 3
asks for. This has the same power problem `UNDERTOW_V2.md` recorded, for the
same reason: a stricter rule needs more history to prove itself.

**What this study excludes is an edge of the size the strategy is supposed to
have.** It does not exclude +0.05 R.

## Against the prediction

| predicted | actual | |
|---|---|---|
| W1 fails bar 4 | failed 3 of 3 | right |
| W2 − W0 — "the number I genuinely cannot call", ±0.10 plausible | +0.023 / +0.023 / +0.054 | right to not call it |
| `famPriority` barely moves R per trade | −0.05 to +0.10 on 354–490 trades | right |
| v3 trades LESS than v1 and MORE than v2 | 0.15 vs 0.60 and vs 0.16 — **about the same as v2** | half right |
| the win rate stays on the 22.2% line | 23.4–23.7%, and **the line is 22.9–23.5%** | the prediction was right, the line was wrong |
| **the 76.7% family mix is evidence for the anchor** | it is an artifact of `locTol 0` | **wrong, and it was in the prereg** |

## What changes

**No default changes.** The promotion rule required bars 3, 4, 5 and 6; v3
cleared 5 and 6 and neither of the two that matter.

**`pinAt` goes on the chart**, defaulting to the pullback extreme — the prereg's
clause for exactly this outcome: W2 shows the anchor is not actively harmful,
so it becomes drawable and selectable, not default. `famPriority` and `locTol`
stay port-only; neither earned a control on the chart.

**Every page's break-even line is restated.** 22.2% is the pre-cost figure. The
line a trade has to beat is 22.9–23.5% depending on the timeframe, and the
thirteen nulls are all sitting on it rather than just below it.

## Where this leaves it

Fourteen studies. Six symbol universes. Three versions of the rule. The entries
are break-even after costs on every one of them, against a line that now
accounts for the costs.

The one explanation no backtest reaches is unchanged: **whether a human
choosing which setups to take beats the machine taking all of them.** That
needs a prospective record — alerts fired forward, taken or skipped, outcomes
written down — which is what `riptide/watchers/undertow.py` exists to build.
