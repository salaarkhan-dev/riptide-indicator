# Does the FVG gradient continue above 1h? No — it goes flat.

Pre-registered in `PREREG_fvg_higher_tf.md`. Study:
`research/studies/fvg_higher_tf.py`.

## The numbers

```
arm     tf      syms  days   n FVG  gross R     SE       Δ      z    ctlΔ  risk%
anchor  Min60     85  1197   18630   +0.053  0.010  +0.076  +6.69  +0.036   1.78
H4      Hour4     81  1190    4508   +0.037  0.021  +0.041  +1.77  -0.008   3.78
H8      Hour8     67  1179    2092   +0.067  0.031  +0.105  +3.01  +0.051   5.45
```

| bar | | |
|---|---|---|
| 1 | 300+ bets and 300+ days, both | PASS |
| 2 | gross R positive at both | PASS |
| 3 | mean of H4 and H8 ≥ the anchor | **FAIL** |
| 4 | gross Δ beats the random-bar control, both | PASS |
| 5 | \|z\| ≥ 2.0 on gross Δ, both | **FAIL** |

**Verdict: the gradient does not continue.** Recorded as a failure.

## But read how it failed

**Bar 3 failed by 0.001 R.** Mean of H4 and H8 is **+0.052** against the
anchor's **+0.053**. The bar was a hard threshold and a hard threshold is what
it did — but 0.052 against 0.053 is not a difference, it is a tie.

**Bar 5 failed on H4 alone**, at z +1.77 on 4,508 bets. H8 is z +3.01.

So the shape of the result is not "the edge disappears above 1h". It is **"the
edge stops rising and stays roughly where it is"**.

## The prereg wrote a conclusion for a failure that did not happen

`PREREG_fvg_higher_tf.md` says, under *If it fails*:

> Then the leading explanation for the whole FVG line is that the Min60 cell
> was noise, re-measured on overlapping data until it looked solid.

**That paragraph assumed one failure mode — H4 and H8 scattering around zero —
and that is not what occurred.** Both are positive. Both beat their random-bar
control. **H8 is +0.067 at z +3.01 on Hour8 data that no run in this sequence
has ever touched**, which is the opposite of what the noise explanation
predicts.

I am therefore **not applying my own pre-written conclusion**, and that is a
judgement call which deserves to be flagged rather than made quietly. The
defence is narrow: the prereg's failure paragraph was conditional on a specific
pattern in the data, that pattern did not appear, and applying its conclusion
anyway would be asserting something the run contradicts. The script now checks
that condition before printing it, instead of asserting it unconditionally.

**What the prereg got right, and what I am accepting from it:** the hypothesis
it tested — that the edge keeps rising with the bar interval — is **refuted**.
Bar 3 is the hypothesis and bar 3 failed.

## So where does that leave it

Three explanations have now been tested and two are dead:

| explanation | status |
|---|---|
| fees explain the timeframe spread | **refuted** — `FVG_GROSS_EDGE` |
| the forward horizon in bars explains it | **refuted** — `FVG_WHY_1H` arm D |
| the edge rises with the bar interval | **refuted** — bar 3 here |
| the Min60 cell is noise | **not supported** — H8 at z +3.01 on fresh data |
| the edge exists at and above 1h and is flat | **fits, and is post-hoc** |

That last row is the only reading left standing, and it was arrived at by
looking at the numbers, so it carries no weight until someone tests it. It also
has an obvious problem: **nothing explains why 1h is the floor.** Min15 and
Min30 have real negative and zero readings on large samples, and a step change
between 30m and 1h is not what a smooth mechanism looks like.

## One number worth carrying forward

Median risk climbs steeply with the timeframe — **1.78%, 3.78%, 5.45%** of
price. Fees in R go as 1/risk, so the same fee costs about **three times less**
at Hour8 than at Min60. A gross edge that is merely flat across those
timeframes is a **net** edge that improves substantially with them.

That is arithmetic, not a finding, and it is the first thing a further test
should measure rather than assume.

## Status, unchanged

Outcome C stands. No forward run, no signal, no alert, no production code. What
has changed is only that the noise explanation is now the weaker of the two
live readings rather than the leading one.
